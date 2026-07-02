import base64
import json
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path

import folder_paths
import numpy as np
import requests
import torch
import urllib3
from PIL import Image, ImageFile
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import comfy.utils

from .tikpan_categories import CATEGORY_PARALLEL_ENGINE
from .tikpan_gpt_image_recovery import get_with_retry, make_idempotency_key
from .tikpan_node_options import API_HOST_OPTIONS, RESPONSE_FORMAT_OPTIONS, normalize_api_host, option_value, pick


ImageFile.LOAD_TRUNCATED_IMAGES = True
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


MODEL_OPTIONS = [
    "grok-imagine-image",
    "grok-imagine-image-pro",
    "gpt-image-2",
    "doubao-seedream-5-0-260128",
]

SIZE_OPTIONS = [
    "1024x1024",
    "1792x1024",
    "1024x1792",
]

STRATEGY_OPTIONS = [
    "failover",
    "parallel_all",
    "race_first_success",
]


class TikpanParallelImageEngineNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "API_Key": ("STRING", {"default": "sk-", "tooltip": "Tikpan 平台的 API 密钥，以 sk- 开头，从 https://tikpan.com 获取"}),
                "Prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "A cinematic commercial product image, precise details, realistic lighting.",
                        "tooltip": "对所有模型/中转站同时下发的提示词",
                    },
                ),
                "Models": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "grok-imagine-image\ngrok-imagine-image-pro",
                        "tooltip": "每行一个模型 ID；以 # 开头的行会被忽略",
                    },
                ),
                "Relay_Hosts": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "\n".join(API_HOST_OPTIONS),
                        "tooltip": "每行一个中转站地址；引擎会用每个模型轮流尝试每个中转站",
                    },
                ),
                "Size": (SIZE_OPTIONS, {"default": "1024x1024", "tooltip": "出图尺寸（统一应用到所有模型）"}),
                "Images_Per_Model": ("INT", {"default": 1, "min": 1, "max": 4, "tooltip": "每个模型在每个中转站生成几张"}),
                "Max_Concurrency": ("INT", {"default": 3, "min": 1, "max": 12, "tooltip": "最大并发请求数；越大越快但更容易触发限流"}),
                "Strategy": (STRATEGY_OPTIONS, {"default": "failover", "tooltip": "failover=失败再轮下一个；parallel_all=全部一起跑；race_first_success=谁先成功用谁"}),
            },
            "optional": {
                "Response_Format": (RESPONSE_FORMAT_OPTIONS, {"default": RESPONSE_FORMAT_OPTIONS[0], "tooltip": "url=返回云端链接（推荐）；b64_json=返回 Base64"}),
                "Timeout_Seconds": ("INT", {"default": 240, "min": 30, "max": 1800, "tooltip": "单个请求等待上限秒数"}),
                "Skip_Error": ("BOOLEAN", {"default": True, "tooltip": "开启后异常时跳过坏任务，不打断整批"}),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING", "STRING")
    RETURN_NAMES = ("Images", "Stage_Log", "Result_JSON")
    FUNCTION = "run"
    CATEGORY = CATEGORY_PARALLEL_ENGINE
    DESCRIPTION = "📝 API 多模型并发生图引擎：一次任务跨多个模型 + 多个中转站并发出图，支持 failover/race/parallel_all 三种策略。适合 A/B 测试、批量出图、容灾备份。"

    def run(self, **kwargs):
        start_time = time.time()
        pbar = comfy.utils.ProgressBar(100)

        api_key = str(pick(kwargs, "API_Key", "api_key", default="") or "").strip()
        prompt = str(pick(kwargs, "Prompt", "prompt", default="") or "").strip()
        models = self.parse_lines(pick(kwargs, "Models", "models", default=""))
        relay_hosts = self.parse_hosts(pick(kwargs, "Relay_Hosts", "relay_hosts", default=""))
        size = str(pick(kwargs, "Size", "size", default="1024x1024") or "1024x1024").strip()
        images_per_model = self.clamp_int(pick(kwargs, "Images_Per_Model", "images_per_model", default=1), 1, 4)
        max_concurrency = self.clamp_int(pick(kwargs, "Max_Concurrency", "max_concurrency", default=3), 1, 12)
        strategy = str(pick(kwargs, "Strategy", "strategy", default="failover") or "failover")
        response_format = option_value(pick(kwargs, "Response_Format", "response_format", default=RESPONSE_FORMAT_OPTIONS[0]), "url")
        timeout_seconds = self.clamp_int(pick(kwargs, "Timeout_Seconds", "timeout_seconds", default=240), 30, 1800)
        skip_error = bool(pick(kwargs, "Skip_Error", "skip_error", default=True))

        width, height = self.parse_size(size)
        stage_events = []
        result_records = []
        tensors = []

        try:
            self.add_event(stage_events, "user", "running", "Validating ComfyUI inputs.")
            if not api_key or api_key == "sk-":
                raise ValueError("API key is empty.")
            if not prompt:
                raise ValueError("Prompt is empty.")
            if not models:
                raise ValueError("Models is empty. Add one model id per line.")
            if not relay_hosts:
                raise ValueError("Relay_Hosts is empty. Add at least one relay host.")
            if size not in SIZE_OPTIONS:
                size = "1024x1024"
                width, height = self.parse_size(size)
            if response_format not in {"url", "b64_json"}:
                response_format = "url"
            if strategy not in STRATEGY_OPTIONS:
                strategy = "failover"
            self.add_event(stage_events, "user", "success", f"Accepted {len(models)} model(s), {len(relay_hosts)} relay host(s).")
            pbar.update(8)

            jobs = []
            for model in models:
                for relay_host in relay_hosts:
                    jobs.append(
                        {
                            "model": model,
                            "relay_host": relay_host,
                            "prompt": prompt,
                            "size": size,
                            "n": images_per_model,
                            "response_format": response_format,
                            "timeout_seconds": timeout_seconds,
                        }
                    )

            if strategy == "failover":
                self.add_event(
                    stage_events,
                    "server",
                    "running",
                    f"Failover mode: trying {len(jobs)} job(s) one by one until the first success.",
                )
                pbar.update(15)
                self.run_failover_jobs(api_key, jobs, stage_events, result_records, tensors, pbar)
            else:
                self.add_event(stage_events, "server", "running", f"Dispatching {len(jobs)} API job(s) with max concurrency {max_concurrency}.")
                pbar.update(15)
                self.run_parallel_jobs(api_key, jobs, strategy, max_concurrency, stage_events, result_records, tensors, pbar)

            if not tensors:
                self.add_event(stage_events, "cdn", "skipped", "No successful image, CDN/output stage skipped.")
                summary = self.build_summary(stage_events, result_records, start_time)
                if not skip_error:
                    raise RuntimeError(summary)
                return (self.black_image(width, height), summary, json.dumps(result_records, ensure_ascii=False, indent=2))

            self.add_event(stage_events, "oss", "success", "Image bytes were decoded locally. Website mode can upload these to OSS.")
            image_batch = self.normalize_batch(tensors)
            self.add_event(stage_events, "cdn", "success", f"Prepared {image_batch.shape[0]} image(s) for ComfyUI output.")
            pbar.update(100)

            summary = self.build_summary(stage_events, result_records, start_time)
            return (image_batch, summary, json.dumps(result_records, ensure_ascii=False, indent=2))

        except Exception as exc:
            self.add_event(stage_events, "server", "error", str(exc))
            summary = self.build_summary(stage_events, result_records, start_time)
            print(f"[Tikpan-ParallelEngine] ERROR: {exc}\n{traceback.format_exc()}", flush=True)
            if not skip_error:
                raise
            return (self.black_image(width, height), summary, json.dumps(result_records, ensure_ascii=False, indent=2))

    def run_failover_jobs(self, api_key, jobs, stage_events, result_records, tensors, pbar):
        for index, job in enumerate(jobs, start=1):
            self.add_event(
                stage_events,
                "upstream",
                "running",
                f"Failover attempt {index}/{len(jobs)}: {job['model']} @ {job['relay_host']}",
            )
            try:
                record = self.run_one_job(api_key, job)
            except Exception as exc:
                record = self.error_record(job, "upstream", str(exc))

            result_records.append(record)
            self.add_event(
                stage_events,
                record.get("stage", "upstream"),
                record.get("status", "error"),
                f"{record.get('model')} @ {record.get('relay_host')} -> {record.get('message')}",
            )
            pbar.update(15 + int(index * 70 / max(len(jobs), 1)))

            if record.get("status") == "success":
                tensors.extend(record.pop("_tensors", []))
                self.add_event(stage_events, "server", "success", "Failover stopped after the first successful upstream response.")
                break

    def run_parallel_jobs(self, api_key, jobs, strategy, max_concurrency, stage_events, result_records, tensors, pbar):
        completed = 0
        stop_after_first = strategy == "race_first_success"
        with ThreadPoolExecutor(max_workers=min(max_concurrency, len(jobs))) as executor:
            future_map = {executor.submit(self.run_one_job, api_key, job): job for job in jobs}
            for future in as_completed(future_map):
                job = future_map[future]
                completed += 1
                try:
                    record = future.result()
                except Exception as exc:
                    record = self.error_record(job, "upstream", str(exc))

                result_records.append(record)
                self.add_event(
                    stage_events,
                    record.get("stage", "upstream"),
                    record.get("status", "error"),
                    f"{record.get('model')} @ {record.get('relay_host')} -> {record.get('message')}",
                )

                if record.get("status") == "success":
                    tensors.extend(record.pop("_tensors", []))

                progress = 15 + int(completed * 70 / max(len(jobs), 1))
                pbar.update(progress)

                if stop_after_first and tensors:
                    for pending in future_map:
                        pending.cancel()
                    break

    def run_one_job(self, api_key, job):
        model = job["model"]
        relay_host = job["relay_host"]
        payload = {
            "model": model,
            "prompt": job["prompt"],
            "size": job["size"],
            "n": job["n"],
            "response_format": job["response_format"],
        }
        idempotency_key = make_idempotency_key("parallel-image", payload, relay_host)
        session = self.create_session()
        response = session.post(
            f"{relay_host}/v1/images/generations",
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "Tikpan-ComfyUI-ParallelEngine/1.0",
                "Idempotency-Key": idempotency_key,
            },
            timeout=(15, job["timeout_seconds"]),
            verify=False,
        )

        if response.status_code != 200:
            return self.error_record(job, "upstream", self.format_http_error(response))

        try:
            res_json = response.json()
        except Exception:
            return self.error_record(job, "upstream", f"Non-JSON response: {self.safe_response_text(response)}")

        api_error = self.extract_api_error(res_json)
        if api_error:
            return self.error_record(job, "upstream", api_error)

        image_items = self.extract_image_items(res_json)
        if not image_items:
            return self.error_record(job, "upstream", "No image URL or base64 image was found.")

        tensors = []
        sources = []
        saved_paths = []
        failures = []
        for index, (img_raw, raw_type) in enumerate(image_items, start=1):
            try:
                image = self.load_result_image(session, img_raw, raw_type).convert("RGB")
                saved_paths.extend(self.save_result_image(image, model, index, idempotency_key, raw_type))
                tensors.append(self.pil_to_tensor(image))
                sources.append(raw_type)
            except Exception as exc:
                failures.append({"index": index, "source": raw_type, "reason": str(exc)})
                print(f"[Tikpan-ParallelEngine] WARNING: job image {index} failed, skipped: {exc}", flush=True)

        if not tensors:
            return self.error_record(job, "upstream", f"All returned image pointers failed to download/decode: {failures}")

        return {
            "status": "success",
            "stage": "upstream",
            "model": model,
            "relay_host": relay_host,
            "message": f"Generated {len(tensors)} image(s), skipped {len(failures)} failed item(s).",
            "sources": sources,
            "saved_paths": saved_paths,
            "failures": failures,
            "idempotency_key": idempotency_key,
            "_tensors": tensors,
        }

    def create_session(self):
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

    def parse_lines(self, value):
        items = []
        for raw in str(value or "").replace(",", "\n").splitlines():
            item = raw.strip()
            if not item or item.startswith("#"):
                continue
            items.append(item)
        return items

    def parse_hosts(self, value):
        hosts = []
        for item in self.parse_lines(value):
            host = normalize_api_host(item, default=item).rstrip("/")
            if host and host not in hosts:
                hosts.append(host)
        return hosts

    def clamp_int(self, value, minimum, maximum):
        try:
            number = int(value)
        except Exception:
            number = minimum
        return max(minimum, min(number, maximum))

    def parse_size(self, size):
        try:
            width_text, height_text = str(size).split("x", 1)
            return int(width_text), int(height_text)
        except Exception:
            return 1024, 1024

    def add_event(self, events, stage, status, message):
        event = {
            "time": time.strftime("%H:%M:%S"),
            "stage": stage,
            "status": status,
            "message": message,
        }
        events.append(event)
        print(f"[Tikpan-ParallelEngine] {stage}/{status}: {message}", flush=True)

    def build_summary(self, events, records, start_time):
        elapsed = round(time.time() - start_time, 2)
        ok = sum(1 for item in records if item.get("status") == "success")
        failed = sum(1 for item in records if item.get("status") != "success")
        saved_paths = []
        skipped_items = []
        for record in records:
            saved_paths.extend(record.get("saved_paths") or [])
            skipped_items.extend(record.get("failures") or [])
        lines = [
            f"Tikpan Parallel Engine finished in {elapsed}s",
            f"Success jobs: {ok} | Failed jobs: {failed}",
            f"Saved files: {len(saved_paths)} | Skipped image items: {len(skipped_items)}",
            "Stages:",
        ]
        lines.extend(f"- [{item['status']}] {item['stage']}: {item['message']}" for item in events)
        if saved_paths:
            lines.append("Saved file paths:")
            lines.extend(f"- {path}" for path in saved_paths[:40])
        if skipped_items:
            lines.append("Skipped item reasons:")
            lines.extend(
                f"- item {item.get('index')} source={item.get('source')} reason={item.get('reason')}"
                for item in skipped_items[:40]
            )
        return "\n".join(lines)

    def error_record(self, job, stage, message):
        return {
            "status": "error",
            "stage": stage,
            "model": job.get("model"),
            "relay_host": job.get("relay_host"),
            "message": message,
        }

    def safe_response_text(self, response, max_len=1000):
        try:
            return response.text[:max_len].strip()
        except Exception:
            return "Unable to parse upstream response."

    def format_http_error(self, response):
        text = self.safe_response_text(response)
        lower = text.lower()
        if "insufficient_quota" in lower:
            return "API balance or quota is insufficient."
        if "rate limit" in lower or "too many requests" in lower:
            return "API rate limit hit."
        if "unknown_parameter" in lower or "unknown parameter" in lower:
            return "The upstream channel does not support one submitted parameter."
        return f"HTTP {response.status_code}: {text}"

    def extract_api_error(self, res_json):
        if not isinstance(res_json, dict):
            return ""
        err_obj = res_json.get("error")
        if not err_obj:
            return ""
        if isinstance(err_obj, dict):
            return err_obj.get("message") or json.dumps(err_obj, ensure_ascii=False)
        return str(err_obj)

    def extract_image_items(self, res_json):
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
            add_item(self.extract_one_image(data))
        elif isinstance(data, list):
            for item in data:
                add_item(self.extract_one_image(item))
        for key in ("result", "output", "images"):
            value = res_json.get(key)
            if isinstance(value, dict):
                add_item(self.extract_one_image(value))
            elif isinstance(value, list):
                for item in value:
                    add_item(self.extract_one_image(item))
        add_item(self.extract_one_image(res_json))
        return items

    def extract_one_image(self, item):
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

    def load_result_image(self, session, img_raw, raw_type):
        if raw_type == "url" or str(img_raw).startswith("http"):
            response = get_with_retry(session, img_raw, timeout=(15, 180), verify=False, attempts=4)
            return Image.open(BytesIO(response.content)).convert("RGB")
        clean = img_raw.split("base64,")[-1] if isinstance(img_raw, str) else img_raw
        return Image.open(BytesIO(base64.b64decode(clean))).convert("RGB")

    def save_result_image(self, image, model, index, idempotency_key, source):
        stamp = time.strftime("%Y%m%d-%H%M%S")
        safe_model = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in str(model or "model"))[:80]
        safe_key = str(idempotency_key or "job")[-8:]
        filename = f"tikpan_parallel_{safe_model}_{stamp}_{index:02d}_{safe_key}.png"
        paths = []
        for base in (
            Path(folder_paths.get_output_directory()),
            Path(__file__).resolve().parents[1] / "recovery" / "parallel_image_engine" / "images",
        ):
            try:
                base.mkdir(parents=True, exist_ok=True)
                path = base / filename
                image.save(path, "PNG")
                paths.append(str(path))
            except Exception as exc:
                print(f"[Tikpan-ParallelEngine] WARNING: save {source} image failed: {exc}", flush=True)
        return paths

    def pil_to_tensor(self, image):
        arr = np.array(image).astype(np.float32) / 255.0
        return torch.from_numpy(arr)[None, ...]

    def normalize_batch(self, tensors):
        if not tensors:
            return self.black_image()
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
            normalized.append(self.pil_to_tensor(pil))
        return torch.cat(normalized, dim=0)

    def black_image(self, width=1024, height=1024):
        return torch.zeros((1, height, width, 3), dtype=torch.float32)
