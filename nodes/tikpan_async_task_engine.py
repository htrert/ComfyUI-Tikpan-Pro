import base64
import hashlib
import json
import os
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path

import numpy as np
import requests
import torch
import urllib3
from PIL import Image, ImageFile
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import folder_paths

from .tikpan_gpt_image_recovery import get_with_retry, make_idempotency_key


ImageFile.LOAD_TRUNCATED_IMAGES = True
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


MAX_WORKERS = int(os.environ.get("TIKPAN_ASYNC_MAX_WORKERS", "4") or "4")
TASK_RETENTION = int(os.environ.get("TIKPAN_ASYNC_TASK_RETENTION", "300") or "300")

_EXECUTOR = ThreadPoolExecutor(max_workers=max(1, min(MAX_WORKERS, 32)), thread_name_prefix="tikpan-async")
_LOCK = threading.RLock()
_TASKS = {}


def _task_dir():
    path = Path(folder_paths.get_output_directory()) / "TikpanAsync"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _task_id(payload):
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str) + str(time.time_ns())
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"tikpan_async_{digest[:24]}"


def _public_task(task):
    return {k: v for k, v in task.items() if k not in {"future"}}


def _write_task_file(task):
    try:
        path = _task_dir() / f"{task['task_id']}.json"
        path.write_text(json.dumps(_public_task(task), ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _trim_tasks():
    if len(_TASKS) <= TASK_RETENTION:
        return
    sorted_items = sorted(_TASKS.items(), key=lambda item: item[1].get("created_at_ts", 0))
    for task_id, task in sorted_items[: max(0, len(_TASKS) - TASK_RETENTION)]:
        if task.get("status") in {"success", "error", "cancelled"}:
            _TASKS.pop(task_id, None)


def submit_image_task(api_key, payload):
    task_id = _task_id(payload)
    task = {
        "task_id": task_id,
        "kind": "image_generation",
        "status": "queued",
        "stage": "server",
        "progress": 0,
        "created_at": _now(),
        "created_at_ts": time.time(),
        "updated_at": _now(),
        "payload": {
            "model": payload.get("model"),
            "relay_host": payload.get("relay_host"),
            "size": payload.get("size"),
            "n": payload.get("n"),
            "response_format": payload.get("response_format"),
        },
        "events": [],
        "image_paths": [],
        "error": "",
    }
    with _LOCK:
        _TASKS[task_id] = task
        _add_event_locked(task, "server", "queued", "Task accepted by local async engine.", progress=1)
        future = _EXECUTOR.submit(_run_image_task, task_id, api_key, payload)
        task["future"] = future
        _trim_tasks()
        _write_task_file(task)
    return task_id


def get_task(task_id):
    task_id = str(task_id or "").strip()
    with _LOCK:
        task = _TASKS.get(task_id)
        if task:
            return _public_task(task)

    path = _task_dir() / f"{task_id}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def list_tasks(limit=50):
    with _LOCK:
        tasks = [_public_task(task) for task in _TASKS.values()]
    tasks.sort(key=lambda item: item.get("created_at_ts", 0), reverse=True)
    return tasks[:limit]


def _add_event_locked(task, stage, status, message, progress=None):
    event = {
        "time": _now(),
        "stage": stage,
        "status": status,
        "message": message,
    }
    task["events"].append(event)
    task["stage"] = stage
    task["updated_at"] = _now()
    if progress is not None:
        task["progress"] = int(progress)
    if status in {"queued", "running"} and task.get("status") not in {"success", "error", "cancelled"}:
        task["status"] = "running" if status == "running" else task["status"]
    print(f"[Tikpan-AsyncEngine] {task['task_id']} {stage}/{status}: {message}", flush=True)


def _finish_task(task_id, status, stage, message, progress):
    with _LOCK:
        task = _TASKS.get(task_id)
        if not task:
            return
        task["status"] = status
        task["stage"] = stage
        task["progress"] = progress
        task["updated_at"] = _now()
        if status == "error":
            task["error"] = message
        _add_event_locked(task, stage, status, message, progress=progress)
        _write_task_file(task)


def _run_image_task(task_id, api_key, payload):
    try:
        with _LOCK:
            task = _TASKS.get(task_id)
            if not task:
                return
            task["status"] = "running"
            _add_event_locked(task, "server", "running", "Background worker started.", progress=8)
            _write_task_file(task)

        session = _create_session()
        relay_host = str(payload["relay_host"]).rstrip("/")
        request_payload = {
            "model": payload["model"],
            "prompt": payload["prompt"],
            "size": payload["size"],
            "n": payload["n"],
            "response_format": payload["response_format"],
        }
        idempotency_key = make_idempotency_key("async-image", request_payload, relay_host)

        with _LOCK:
            task = _TASKS.get(task_id)
            if task:
                task["idempotency_key"] = idempotency_key
                _add_event_locked(task, "upstream", "running", f"Submitting to {relay_host}.", progress=18)
                _write_task_file(task)

        response = session.post(
            f"{relay_host}/v1/images/generations",
            json=request_payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "Tikpan-ComfyUI-AsyncEngine/1.0",
                "Idempotency-Key": idempotency_key,
            },
            timeout=(15, int(payload.get("timeout_seconds", 240))),
            verify=False,
        )

        if response.status_code != 200:
            raise RuntimeError(_format_http_error(response))

        try:
            res_json = response.json()
        except Exception:
            raise RuntimeError(f"Upstream returned non-JSON response: {_safe_response_text(response)}")

        api_error = _extract_api_error(res_json)
        if api_error:
            raise RuntimeError(api_error)

        image_items = _extract_image_items(res_json)
        if not image_items:
            raise RuntimeError("No image URL or base64 image was found in upstream response.")

        with _LOCK:
            task = _TASKS.get(task_id)
            if task:
                task["raw_response_preview"] = json.dumps(res_json, ensure_ascii=False)[:3000]
                _add_event_locked(task, "upstream", "success", f"Received {len(image_items)} image pointer(s).", progress=55)
                _write_task_file(task)

        image_paths = []
        for index, (img_raw, raw_type) in enumerate(image_items, start=1):
            image = _load_result_image(session, img_raw, raw_type).convert("RGB")
            image_path = _save_image(task_id, index, image)
            image_paths.append(image_path)

        with _LOCK:
            task = _TASKS.get(task_id)
            if task:
                task["image_paths"] = image_paths
                _add_event_locked(task, "oss", "success", f"Saved {len(image_paths)} image(s) locally.", progress=88)
                _add_event_locked(task, "cdn", "success", "Images are ready for ComfyUI query nodes.", progress=100)
                task["status"] = "success"
                task["stage"] = "cdn"
                task["progress"] = 100
                task["updated_at"] = _now()
                _write_task_file(task)

    except Exception as exc:
        message = f"{exc}"
        print(f"[Tikpan-AsyncEngine] {task_id} ERROR: {message}\n{traceback.format_exc()}", flush=True)
        _finish_task(task_id, "error", "upstream", message, 100)


def _create_session():
    session = requests.Session()
    session.trust_env = False
    retries = Retry(
        total=3,
        connect=3,
        read=0,
        status=0,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["HEAD", "GET", "OPTIONS"]),
    )
    adapter = HTTPAdapter(max_retries=retries, pool_connections=20, pool_maxsize=20)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def _save_image(task_id, index, image):
    path = _task_dir() / f"{task_id}_{index:02d}.png"
    image.save(path, format="PNG")
    return str(path)


def load_images_as_tensor(image_paths):
    tensors = []
    for path in image_paths:
        image = Image.open(path).convert("RGB")
        arr = np.array(image).astype(np.float32) / 255.0
        tensors.append(torch.from_numpy(arr)[None, ...])
    return normalize_tensor_batch(tensors)


def normalize_tensor_batch(tensors):
    if not tensors:
        return black_image()
    target_h = tensors[0].shape[1]
    target_w = tensors[0].shape[2]
    normalized = []
    for tensor in tensors:
        if tensor.shape[1] == target_h and tensor.shape[2] == target_w:
            normalized.append(tensor)
            continue
        image = tensor[0].cpu().numpy()
        image = np.clip(image * 255.0, 0, 255).astype(np.uint8)
        resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS", Image.LANCZOS)
        pil = Image.fromarray(image).resize((target_w, target_h), resample)
        arr = np.array(pil).astype(np.float32) / 255.0
        normalized.append(torch.from_numpy(arr)[None, ...])
    return torch.cat(normalized, dim=0)


def black_image(width=1024, height=1024):
    return torch.zeros((1, height, width, 3), dtype=torch.float32)


def _safe_response_text(response, max_len=1000):
    try:
        return response.text[:max_len].strip()
    except Exception:
        return "Unable to parse upstream response."


def _format_http_error(response):
    text = _safe_response_text(response)
    lower = text.lower()
    if "insufficient_quota" in lower:
        return "API balance or quota is insufficient."
    if "rate limit" in lower or "too many requests" in lower:
        return "API rate limit hit."
    if "unknown_parameter" in lower or "unknown parameter" in lower:
        return "The upstream channel does not support one submitted parameter."
    return f"HTTP {response.status_code}: {text}"


def _extract_api_error(res_json):
    if not isinstance(res_json, dict):
        return ""
    err_obj = res_json.get("error")
    if not err_obj:
        return ""
    if isinstance(err_obj, dict):
        return err_obj.get("message") or json.dumps(err_obj, ensure_ascii=False)
    return str(err_obj)


def _extract_image_items(res_json):
    items = []
    seen = set()

    def add_item(parsed):
        if not parsed:
            return
        key = (str(parsed[0]), parsed[1])
        if key in seen:
            return
        seen.add(key)
        items.append(parsed)

    if not isinstance(res_json, dict):
        return items
    data = res_json.get("data")
    if isinstance(data, dict):
        add_item(_extract_one_image(data))
    elif isinstance(data, list):
        for item in data:
            add_item(_extract_one_image(item))
    for key in ("result", "output", "images"):
        value = res_json.get(key)
        if isinstance(value, dict):
            add_item(_extract_one_image(value))
        elif isinstance(value, list):
            for item in value:
                add_item(_extract_one_image(item))
    add_item(_extract_one_image(res_json))
    return items


def _extract_one_image(item):
    if not isinstance(item, dict):
        return None
    url = item.get("url") or item.get("image_url") or item.get("imageUrl")
    if url:
        return url, "url"
    image_value = item.get("image")
    if isinstance(image_value, str) and image_value.startswith("http"):
        return image_value, "url"
    b64 = item.get("b64_json") or item.get("image_base64") or item.get("base64")
    if not b64 and isinstance(image_value, str):
        b64 = image_value
    data_value = item.get("data")
    if not b64 and isinstance(data_value, str) and data_value.startswith("data:image"):
        b64 = data_value
    if b64:
        return b64, "b64"
    return None


def _load_result_image(session, img_raw, raw_type):
    if raw_type == "url" or str(img_raw).startswith("http"):
        response = get_with_retry(session, img_raw, timeout=(15, 180), verify=False, attempts=4)
        return Image.open(BytesIO(response.content)).convert("RGB")
    clean = img_raw.split("base64,")[-1] if isinstance(img_raw, str) else img_raw
    return Image.open(BytesIO(base64.b64decode(clean))).convert("RGB")
