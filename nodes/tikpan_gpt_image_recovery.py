import hashlib
import json
import time
import base64
from pathlib import Path

import requests


RECOVERY_DIR = Path(__file__).resolve().parents[1] / "recovery" / "gpt_image_2"


def make_idempotency_key(*parts):
    raw = json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"tikpan-gpt-image-2-{digest[:32]}"


def short_hash(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def save_recovery_record(kind, idempotency_key, status, **fields):
    RECOVERY_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "kind": kind,
        "idempotency_key": idempotency_key,
        "status": status,
        **fields,
    }
    latest_path = RECOVERY_DIR / f"{idempotency_key}.json"
    jsonl_path = RECOVERY_DIR / "events.jsonl"

    latest_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    with jsonl_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return str(latest_path)


def safe_json_for_log(value, max_len=4000):
    try:
        text = json.dumps(value, ensure_ascii=False)
    except Exception:
        text = str(value)
    if len(text) > max_len:
        return text[:max_len] + "...(truncated)"
    return text


def save_base64_image(idempotency_key, img_raw, suffix="png"):
    RECOVERY_DIR.mkdir(parents=True, exist_ok=True)
    clean = img_raw.split("base64,")[-1] if isinstance(img_raw, str) else img_raw
    image_bytes = base64.b64decode(clean)
    ext = suffix.lower().lstrip(".") or "png"
    path = RECOVERY_DIR / f"{idempotency_key}.{ext}"
    path.write_bytes(image_bytes)
    return str(path)


def get_with_retry(session, url, *, timeout=(15, 180), verify=False, proxies=None, attempts=4):
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            kwargs = {"timeout": timeout, "verify": verify}
            if proxies is not None:
                kwargs["proxies"] = proxies
            resp = session.get(url, **kwargs)
            resp.raise_for_status()
            if not resp.content:
                raise requests.RequestException("empty response body")
            return resp
        except requests.RequestException as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(min(2 ** (attempt - 1), 8))
    raise last_error
