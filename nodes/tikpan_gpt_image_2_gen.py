import base64
import json
import re
from io import BytesIO

import comfy.utils
import numpy as np
import requests
import torch
from PIL import Image

from .tikpan_gpt_image_recovery import (
    get_with_retry,
    make_idempotency_key,
    safe_json_for_log,
    save_recovery_record,
    save_request_snapshot,
    short_hash,
)
from .tikpan_node_options import API_HOST_OPTIONS, normalize_api_host, normalize_seed


KEY_INFO = "\u83b7\u53d6\u5bc6\u94a5\u8bf7\u8bbf\u95ee"
KEY_API = "API_\u5bc6\u94a5"
KEY_PROMPT = "\u751f\u6210\u6307\u4ee4"
KEY_MODEL = "\u6a21\u578b"
KEY_TIER = "\u5206\u8fa8\u7387\u6863\u4f4d"
KEY_RATIO = "\u753b\u9762\u6bd4\u4f8b"
KEY_QUALITY = "\u54c1\u8d28"
KEY_SEED = "\u968f\u673a\u79cd\u5b50"
KEY_HOST = "\u4e2d\u8f6c\u7ad9\u5730\u5740"
KEY_REF_PREFIX = "\u53c2\u8003\u56fe_"
RET_IMAGE = "\u751f\u6210\u7ed3\u679c\u56fe"
RET_LOG = "\u6e32\u67d3\u65e5\u5fd7"


class TikpanGptImage2GenNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                KEY_INFO: (["https://tikpan.com"],),
                KEY_API: ("STRING", {"default": "sk-"}),
                KEY_PROMPT: (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "Create a high quality image. Use any connected reference images as visual references.",
                    },
                ),
                KEY_MODEL: (["gpt-image-2-all"], {"default": "gpt-image-2-all"}),
                KEY_TIER: (["512", "1K", "2K", "4K"], {"default": "1K"}),
                KEY_RATIO: (["1:1", "16:9", "9:16", "21:9", "4:3", "3:4"], {"default": "1:1"}),
                KEY_QUALITY: (["standard", "hd"], {"default": "hd"}),
                KEY_SEED: ("INT", {"default": 888888, "min": 0, "max": 0xFFFFFFFFFFFFFFFF}),
            },
            "optional": {
                KEY_HOST: (API_HOST_OPTIONS, {"default": API_HOST_OPTIONS[0]}),
                **{f"{KEY_REF_PREFIX}{i}": ("IMAGE",) for i in range(1, 6)},
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = (RET_IMAGE, RET_LOG)
    FUNCTION = "generate"
    CATEGORY = "\U0001f451 Tikpan \u5b98\u65b9\u72ec\u5bb6\u8282\u70b9/01 \u56fe\u7247 Image"

    def generate(self, **kwargs):
        pbar = comfy.utils.ProgressBar(100)
        session = requests.Session()
        session.trust_env = False

        api_key = str(self.pick(kwargs, "API_Key", KEY_API, default="") or "").strip()
        prompt = str(self.pick(kwargs, "Prompt", KEY_PROMPT, "prompt", default="") or "").strip()
        model = str(self.pick(kwargs, "Model", KEY_MODEL, default="gpt-image-2-all") or "gpt-image-2-all").strip()
        tier = str(self.pick(kwargs, "Resolution_Tier", KEY_TIER, default="1K") or "1K").strip()
        aspect_ratio = str(self.pick(kwargs, "Aspect_Ratio", KEY_RATIO, default="1:1") or "1:1").strip()
        quality = self.option_value(self.pick(kwargs, "Quality", KEY_QUALITY, default="hd"), "hd")
        seed = normalize_seed(self.pick(kwargs, "Seed", KEY_SEED, "seed", default=888888), default=888888, maximum=2147483647)
        api_host = normalize_api_host(self.pick(kwargs, "Relay_Host", KEY_HOST, default=API_HOST_OPTIONS[0]))

        width, height, target_res = self.compute_target_resolution(tier, aspect_ratio)
        try:
            if not api_key or api_key == "sk-":
                return (self.black_image(width, height), "ERROR: API key is empty.")
            if not prompt:
                return (self.black_image(width, height), "ERROR: prompt is empty.")
            if model != "gpt-image-2-all":
                model = "gpt-image-2-all"
            if quality not in {"standard", "hd"}:
                quality = "hd"

            pbar.update(10)
            reference_images = self.collect_reference_images(kwargs)
            payload = {
                "model": model,
                "prompt": f"{prompt}\n\n[Format: {aspect_ratio}, Size: {target_res}, Quality: {quality}]",
                "n": 1,
                "size": target_res,
            }
            if reference_images:
                payload["image"] = reference_images

            endpoint = "/v1/images/generations"
            idempotency_key = make_idempotency_key("images/generations", payload)
            request_snapshot_path = save_request_snapshot(
                "all_generation",
                idempotency_key,
                payload,
                endpoint=endpoint,
                payload_hash=short_hash(payload),
                size=target_res,
            )
            recovery_path = save_recovery_record(
                "all_generation",
                idempotency_key,
                "pending",
                endpoint=endpoint,
                payload_hash=short_hash(payload),
                size=target_res,
                request_snapshot=request_snapshot_path,
            )

            pbar.update(20)
            response = self.post_images_generation_with_retry(
                session,
                f"{api_host}{endpoint}",
                payload,
                api_key,
                idempotency_key,
                recovery_path,
            )
            if response.status_code >= 400:
                return (self.black_image(width, height), f"ERROR: HTTP {response.status_code}: {response.text[:1200]}")

            res_json = response.json()
            save_recovery_record(
                "all_generation",
                idempotency_key,
                "response_received",
                endpoint=endpoint,
                http_status=response.status_code,
                response=safe_json_for_log(res_json),
            )
            pbar.update(70)

            img_raw = self.extract_image_pointer(res_json)
            if not img_raw:
                return (self.black_image(width, height), f"ERROR: no image URL/base64 found: {json.dumps(res_json, ensure_ascii=False)[:1600]}")

            save_recovery_record(
                "all_generation",
                idempotency_key,
                "image_pointer_received",
                endpoint=endpoint,
                image_url=img_raw if str(img_raw).startswith("http") else "",
            )
            final_img = self.load_result_image(session, img_raw)
            out_tensor = torch.from_numpy(np.array(final_img).astype(np.float32) / 255.0)[None, ...]
            pbar.update(100)
            source = "url" if str(img_raw).startswith("http") else "base64"
            log = (
                f"success | endpoint={endpoint} | model={model} | size={target_res} | "
                f"quality={quality} | refs={len(reference_images)} | source={source} | idempotency_key={idempotency_key}"
            )
            if source == "url":
                log += f" | upstream_image_url: {img_raw}"
            return (out_tensor, log)
        except Exception as e:
            return (self.black_image(width, height), f"ERROR: {e}")

    def post_images_generation_with_retry(self, session, url, payload, api_key, idempotency_key, recovery_path):
        payload_hash = short_hash(payload)
        attempts = [600, 900, 1200]
        last_error = None
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Tikpan-ComfyUI-gpt-image-2-all/2.0",
            "Idempotency-Key": idempotency_key,
        }
        for attempt_index, read_timeout in enumerate(attempts, start=1):
            try:
                response = session.post(url, json=payload, headers=headers, timeout=(15, read_timeout), verify=False)
                if attempt_index > 1:
                    save_recovery_record(
                        "all_generation",
                        idempotency_key,
                        "post_recovered_after_retry",
                        endpoint="/v1/images/generations",
                        payload_hash=payload_hash,
                        retry_attempt=attempt_index,
                        read_timeout_seconds=read_timeout,
                        request_snapshot=recovery_path.replace(".json", ".request.json"),
                    )
                return response
            except requests.exceptions.ConnectTimeout as e:
                last_error = e
                save_recovery_record(
                    "all_generation",
                    idempotency_key,
                    "connect_timeout",
                    endpoint="/v1/images/generations",
                    payload_hash=payload_hash,
                    retry_attempt=attempt_index,
                    request_snapshot=recovery_path.replace(".json", ".request.json"),
                    error=str(e),
                )
                break
            except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
                last_error = e
                save_recovery_record(
                    "all_generation",
                    idempotency_key,
                    "post_disconnected_retrying" if attempt_index < len(attempts) else "post_disconnected",
                    endpoint="/v1/images/generations",
                    payload_hash=payload_hash,
                    retry_attempt=attempt_index,
                    read_timeout_seconds=read_timeout,
                    request_snapshot=recovery_path.replace(".json", ".request.json"),
                    error=str(e),
                )
                if attempt_index < len(attempts):
                    continue
        raise RuntimeError(
            "Upstream accepted the image request, but the local connection dropped while waiting for the result. "
            f"Retried with the same Idempotency-Key {len(attempts)} times. "
            f"Idempotency-Key: {idempotency_key} | recovery: {recovery_path} | last_error: {last_error}"
        )

    def compute_target_resolution(self, tier, aspect_ratio):
        if str(aspect_ratio) in {"16:9", "21:9", "4:3"}:
            width, height = 1536, 1024
        elif str(aspect_ratio) in {"9:16", "3:4"}:
            width, height = 1024, 1536
        else:
            width, height = 1024, 1024
        return width, height, f"{width}x{height}"

    def collect_reference_images(self, kwargs):
        images = []
        for i in range(1, 6):
            tensor = self.pick(kwargs, f"Reference_Image_{i}", f"{KEY_REF_PREFIX}{i}", f"ref_image_{i}", default=None)
            if tensor is not None:
                images.append(self.tensor_to_data_url(tensor))
        return images

    def tensor_to_data_url(self, img_tensor, quality=75):
        if len(img_tensor.shape) == 4:
            img_tensor = img_tensor[0]
        arr = 255.0 * img_tensor.detach().cpu().numpy()
        image = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGB")
        image.thumbnail((1024, 1024))
        buf = BytesIO()
        image.save(buf, format="JPEG", quality=int(quality), optimize=True)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")

    def extract_image_pointer(self, res_json):
        seen = set()

        def add(value):
            if not isinstance(value, str):
                return ""
            value = value.strip()
            if not value or value in seen:
                return ""
            seen.add(value)
            if value.startswith(("http://", "https://", "data:image")):
                return value
            if len(value) > 80 and re.search(r"^[A-Za-z0-9+/=\s\r\n]+$", value):
                return value
            return ""

        def from_item(item):
            if isinstance(item, str):
                found = add(item)
                if found:
                    return found
                return self.extract_markdown_image_url(item)
            if isinstance(item, list):
                for part in item:
                    found = from_item(part)
                    if found:
                        return found
                return ""
            if not isinstance(item, dict):
                return ""
            for key in ("url", "image_url", "imageUrl", "output_url", "result_url", "b64_json", "image_base64", "base64", "image"):
                found = add(item.get(key))
                if found:
                    return found
            nested = item.get("image_url")
            if isinstance(nested, dict):
                found = add(nested.get("url"))
                if found:
                    return found
            for key in ("data", "result", "output", "images", "generations", "choices", "message", "content"):
                found = from_item(item.get(key))
                if found:
                    return found
            return ""

        return from_item(res_json)

    def extract_markdown_image_url(self, text):
        if not isinstance(text, str):
            return ""
        patterns = [
            r"!\[[^\]]*\]\((https?://[^\s)]+)\)",
            r"\[[^\]]*\]\((https?://[^\s)]+)\)",
            r"(https?://[^\s)]+\.(?:png|jpg|jpeg|webp)(?:\?[^\s)]*)?)",
            r"(https?://t\.filesystem\.site/[^\s)]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip().rstrip(".,;")
        return ""

    def load_result_image(self, session, img_raw):
        img_raw = str(img_raw).strip()
        if img_raw.startswith(("http://", "https://")):
            img_res = get_with_retry(session, img_raw, timeout=(10, 180), verify=False, attempts=4)
            return Image.open(BytesIO(img_res.content)).convert("RGB")
        clean = re.sub(r"\s+", "", img_raw.split("base64,")[-1])
        missing_padding = len(clean) % 4
        if missing_padding:
            clean += "=" * (4 - missing_padding)
        return Image.open(BytesIO(base64.b64decode(clean))).convert("RGB")

    def black_image(self, width=512, height=512):
        return torch.zeros((1, int(height), int(width), 3), dtype=torch.float32)

    def option_value(self, value, default):
        raw = str(value or default)
        if "|" in raw:
            return raw.split("|")[-1].strip()
        return raw.strip() or default

    def pick(self, data, *keys, default=None):
        for key in keys:
            if key in data:
                return data.get(key)
        return default
