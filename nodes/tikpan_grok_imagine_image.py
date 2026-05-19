import base64
import json
import time
import traceback
import urllib3
from io import BytesIO

import numpy as np
import requests
import torch
from PIL import Image, ImageFile
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import comfy.utils

from .tikpan_gpt_image_recovery import get_with_retry, make_idempotency_key
from .tikpan_node_options import API_HOST_OPTIONS, RESPONSE_FORMAT_OPTIONS, normalize_api_host, option_value, pick


ImageFile.LOAD_TRUNCATED_IMAGES = True
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


ASPECT_RATIO_OPTIONS = ["auto", "1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "2:1", "1:2", "19.5:9", "9:19.5", "20:9", "9:20"]
RESOLUTION_OPTIONS = ["auto", "1k", "2k"]
SIZE_OPTIONS = ["Auto", "1024x1024", "1792x1024", "1024x1792"]


class _TikpanGrokImagineBase:
    MODEL_ID = ""
    MODEL_NAME = ""
    PRICE_TEXT = ""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "💰_福利_💰": (["🔥 0.6元RMB兑1美元余额 | 全网底价 👉 https://tikpan.com"],),
                "获取密钥请访问": (["👉 https://tikpan.com (官方授权Key获取点)"],),
                "节点说明": ([f"{cls.MODEL_NAME} | /v1/images/generations | 文生图 | 官方参数: n / aspect_ratio / resolution / response_format | {cls.PRICE_TEXT}"],),
                "API_密钥": ("STRING", {"default": "sk-"}),
                "生成指令": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "A cinematic product poster with precise details, realistic lighting, high-end commercial photography.",
                    },
                ),
                "模型": ([cls.MODEL_ID], {"default": cls.MODEL_ID}),
                "生成张数": ("INT", {"default": 1, "min": 1, "max": 10, "step": 1}),
                "画面比例": (ASPECT_RATIO_OPTIONS, {"default": "auto"}),
                "清晰度": (RESOLUTION_OPTIONS, {"default": "auto"}),
            },
            "optional": {
                "兼容尺寸": (SIZE_OPTIONS, {"default": "Auto"}),
                "中转站地址": (API_HOST_OPTIONS, {"default": API_HOST_OPTIONS[0]}),
                "返回方式": (RESPONSE_FORMAT_OPTIONS, {"default": RESPONSE_FORMAT_OPTIONS[0]}),
                "跳过错误": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "Return a black image instead of stopping the workflow when the API request fails.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("Image", "Log")
    FUNCTION = "generate"
    CATEGORY = "👑 Tikpan 官方独家节点"

    def generate(self, **kwargs):
        start_time = time.time()
        api_key = str(pick(kwargs, "API_Key", "API_密钥", "api_key", default="") or "").strip()
        prompt = str(pick(kwargs, "Prompt", "生成指令", "prompt", default="") or "").strip()
        model = str(pick(kwargs, "Model", "模型", "model", default=self.MODEL_ID) or self.MODEL_ID).strip()
        size = str(pick(kwargs, "Size", "尺寸", "兼容尺寸", "size", default="Auto") or "Auto").strip()
        aspect_ratio = self.build_aspect_ratio(option_value(
            pick(kwargs, "Aspect_Ratio", "画面比例", "aspect_ratio", default="auto"),
            "auto",
        ))
        resolution = self.build_resolution(option_value(
            pick(kwargs, "Resolution", "清晰度", "resolution", default="auto"),
            "auto",
        ))
        try:
            count = int(pick(kwargs, "Count", "生成张数", "n", default=1) or 1)
        except Exception:
            count = 1
        response_format = self.build_response_format(option_value(
            pick(kwargs, "Response_Format", "返回方式", "response_format", default=RESPONSE_FORMAT_OPTIONS[0]),
            "url",
        ))
        api_host = normalize_api_host(pick(kwargs, "Relay_Host", "中转站地址", "api_host", default=API_HOST_OPTIONS[0]))
        skip_error = bool(pick(kwargs, "Skip_Error", "跳过错误", "skip_error", default=False))

        pbar = comfy.utils.ProgressBar(100)
        width, height = self.size_from_options(size, aspect_ratio, resolution)

        try:
            if not api_key or api_key == "sk-":
                return (self.black_image(width, height), "ERROR: API key is empty.")
            if not prompt:
                return (self.black_image(width, height), "ERROR: Prompt is empty.")

            if model != self.MODEL_ID:
                model = self.MODEL_ID
            if size not in SIZE_OPTIONS:
                size = "Auto"
                width, height = self.size_from_options(size, aspect_ratio, resolution)
            response_format = self.build_response_format(response_format)
            count = max(1, min(int(count), 10))
            context = self.request_context(model, size, count, response_format, api_host, start_time, aspect_ratio, resolution)

            print(f"[Tikpan-GrokImagine] Start | model={model} | aspect_ratio={aspect_ratio} | resolution={resolution} | size={size} | n={count}", flush=True)
            pbar.update(8)

            session = self.create_session()
            payload = {
                "model": model,
                "prompt": prompt,
                "n": count,
                "response_format": response_format,
            }
            if aspect_ratio != "auto":
                payload["aspect_ratio"] = aspect_ratio
            if resolution != "auto":
                payload["resolution"] = resolution
            if size != "Auto":
                payload["size"] = size
            idempotency_key = make_idempotency_key("grok-imagine-image", payload)
            url = f"{api_host}/v1/images/generations"
            payload_preview = json.dumps(payload, ensure_ascii=False, default=str)[:1200]
            print(f"[Tikpan-GrokImagine] Payload: {payload_preview}", flush=True)

            pbar.update(18)
            try:
                response = session.post(
                    url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "User-Agent": "Tikpan-ComfyUI-GrokImagine/1.0",
                        "Idempotency-Key": idempotency_key,
                    },
                    timeout=(15, 240),
                    verify=False,
                )
            except (requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError) as exc:
                msg = (
                    "ERROR: Submit connection failed without automatic POST retry to avoid duplicate billing. "
                    f"{context()} | idempotency_key={idempotency_key} | {exc}"
                )
                if not skip_error:
                    raise RuntimeError(msg) from exc
                return (self.black_image(width, height), self.skip_error_message(msg))
            pbar.update(62)

            if response.status_code != 200:
                msg = self.format_http_error(response, context())
                print(f"[Tikpan-GrokImagine] {msg}", flush=True)
                if not skip_error:
                    raise RuntimeError(msg)
                return (self.black_image(width, height), self.skip_error_message(msg))

            try:
                res_json = response.json()
            except Exception:
                msg = f"ERROR: API returned non-JSON response | {context()} | {self.safe_response_text(response)}"
                if not skip_error:
                    raise RuntimeError(msg)
                return (self.black_image(width, height), self.skip_error_message(msg))

            api_error = self.extract_api_error(res_json)
            if api_error:
                msg = f"ERROR: Upstream rejected the image request | {context()} | {api_error}"
                if not skip_error:
                    raise RuntimeError(msg)
                return (self.black_image(width, height), self.skip_error_message(msg))

            image_items = self.extract_image_items(res_json)
            if not image_items:
                msg = f"ERROR: No image URL or base64 image was found in the API response | {context()}"
                if not skip_error:
                    raise RuntimeError(msg)
                return (self.black_image(width, height), self.skip_error_message(msg))

            pbar.update(76)
            tensors = []
            source_logs = []
            for idx, (img_raw, raw_type) in enumerate(image_items, start=1):
                image = self.load_result_image(session, img_raw, raw_type)
                tensor = self.pil_to_tensor(image)
                tensors.append(tensor)
                source_logs.append(f"{idx}:{raw_type}")
                pbar.update(76 + int(idx * 18 / max(len(image_items), 1)))

            image_batch = self.normalize_batch(tensors)
            cost_time = round(time.time() - start_time, 2)
            log_text = (
                f"SUCCESS: {self.MODEL_NAME} generated {len(tensors)} image(s). "
                f"model={model}, host={api_host}, aspect_ratio={aspect_ratio}, resolution={resolution}, size={size}, n={count}, response_format={response_format}, "
                f"sources={','.join(source_logs)}, elapsed={cost_time}s"
            )
            print(f"[Tikpan-GrokImagine] {log_text}", flush=True)
            pbar.update(100)
            return (image_batch, log_text)

        except Exception as exc:
            tb = traceback.format_exc()
            msg = f"ERROR: {exc}\n{tb[:1000]}"
            print(f"[Tikpan-GrokImagine] {msg}", flush=True)
            if not skip_error:
                raise
            return (self.black_image(width, height), self.skip_error_message(msg))

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

    def parse_size(self, size):
        try:
            width_text, height_text = str(size).split("x", 1)
            return int(width_text), int(height_text)
        except Exception:
            return 1024, 1024

    def safe_response_text(self, response, max_len=1000):
        try:
            return response.text[:max_len].strip()
        except Exception:
            return "Unable to parse upstream response."

    def build_response_format(self, value):
        return value if value in {"url", "b64_json"} else "url"

    def build_aspect_ratio(self, value):
        return value if value in set(ASPECT_RATIO_OPTIONS) else "auto"

    def build_resolution(self, value):
        return value if value in set(RESOLUTION_OPTIONS) else "auto"

    def size_from_options(self, size, aspect_ratio="auto", resolution="auto"):
        if size and size != "Auto":
            return self.parse_size(size)
        long_side = 2048 if resolution == "2k" else 1024
        if aspect_ratio in {"16:9", "3:2", "2:1", "19.5:9", "20:9"}:
            return long_side, max(512, int(long_side * 9 / 16))
        if aspect_ratio in {"9:16", "2:3", "1:2", "9:19.5", "9:20"}:
            return max(512, int(long_side * 9 / 16)), long_side
        if aspect_ratio == "4:3":
            return long_side, int(long_side * 3 / 4)
        if aspect_ratio == "3:4":
            return int(long_side * 3 / 4), long_side
        return long_side, long_side

    def request_context(self, model, size, count, response_format, api_host, start_time, aspect_ratio="auto", resolution="auto"):
        def _context():
            elapsed = round(time.time() - start_time, 2)
            return f"model={model} | aspect_ratio={aspect_ratio} | resolution={resolution} | size={size} | n={count} | rf={response_format} | host={api_host} | elapsed={elapsed}s"

        return _context

    def skip_error_message(self, msg):
        return f"{msg}\nSkip_Error=True, returned a black placeholder image to keep workflow running."

    def format_http_error(self, response, context=""):
        err_text = self.safe_response_text(response)
        err_lower = err_text.lower()
        prefix = f"ERROR: HTTP {response.status_code}"
        if context:
            prefix += f" | {context}"
        if "insufficient_quota" in err_lower:
            return f"{prefix} | API balance or quota is insufficient."
        if "rate limit" in err_lower or "too many requests" in err_lower:
            return f"{prefix} | API rate limit hit. Please retry later."
        if "unknown_parameter" in err_lower or "unknown parameter" in err_lower:
            return f"{prefix} | The upstream channel does not support one submitted parameter. If n > 1, try Count=1. | {err_text}"
        return f"{prefix} | {err_text}"

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

        if isinstance(res_json, dict):
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
        image_bytes = base64.b64decode(clean)
        return Image.open(BytesIO(image_bytes)).convert("RGB")

    def pil_to_tensor(self, image):
        arr = np.array(image).astype(np.float32) / 255.0
        return torch.from_numpy(arr)[None, ...]

    def tensor_to_pil(self, tensor):
        if tensor is None:
            raise ValueError("Image input is empty.")
        if len(tensor.shape) == 4:
            tensor = tensor[0]
        arr = tensor.detach().cpu().numpy()
        arr = np.clip(arr * 255.0, 0, 255).astype(np.uint8)
        return Image.fromarray(arr).convert("RGB")

    def image_to_data_url(self, tensor, quality=92):
        image = self.tensor_to_pil(tensor)
        buf = BytesIO()
        image.save(buf, format="JPEG", quality=int(quality), optimize=True)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")

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


class TikpanGrokImagineImageNode(_TikpanGrokImagineBase):
    MODEL_ID = "grok-imagine-image"
    MODEL_NAME = "Grok Imagine Image"
    PRICE_TEXT = "0.208 RMB per image"


class TikpanGrokImagineImageProNode(_TikpanGrokImagineBase):
    MODEL_ID = "grok-imagine-image-pro"
    MODEL_NAME = "Grok Imagine Image Pro"
    PRICE_TEXT = "0.728 RMB per image"


class _TikpanGrokImagineEditBase(_TikpanGrokImagineBase):
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "💰_福利_💰": (["🔥 0.6元RMB兑1美元余额 | 全网底价 👉 https://tikpan.com"],),
                "获取密钥请访问": (["👉 https://tikpan.com (官方授权Key获取点)"],),
                "节点说明": ([f"{cls.MODEL_NAME} | /v1/images/edits | 参考图/修图 | 官方最多3张参考图 | {cls.PRICE_TEXT}"],),
                "API_密钥": ("STRING", {"default": "sk-"}),
                "参考图1": ("IMAGE",),
                "编辑指令": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "Keep the main subject consistent, improve the composition, lighting, details, and commercial product quality.",
                    },
                ),
                "模型": ([cls.MODEL_ID], {"default": cls.MODEL_ID}),
                "生成张数": ("INT", {"default": 1, "min": 1, "max": 10, "step": 1}),
                "画面比例": (ASPECT_RATIO_OPTIONS, {"default": "auto"}),
                "清晰度": (RESOLUTION_OPTIONS, {"default": "auto"}),
            },
            "optional": {
                "参考图2": ("IMAGE",),
                "参考图3": ("IMAGE",),
                "中转站地址": (API_HOST_OPTIONS, {"default": API_HOST_OPTIONS[0]}),
                "返回方式": (RESPONSE_FORMAT_OPTIONS, {"default": RESPONSE_FORMAT_OPTIONS[0]}),
                "跳过错误": ("BOOLEAN", {"default": False}),
            },
        }

    RETURN_NAMES = ("编辑结果", "渲染日志")
    FUNCTION = "edit"

    def edit(self, **kwargs):
        start_time = time.time()
        api_key = str(pick(kwargs, "API_Key", "API_密钥", "api_key", default="") or "").strip()
        prompt = str(pick(kwargs, "Prompt", "编辑指令", "prompt", default="") or "").strip()
        model = str(pick(kwargs, "Model", "模型", "model", default=self.MODEL_ID) or self.MODEL_ID).strip()
        try:
            count = int(pick(kwargs, "Count", "生成张数", "n", default=1) or 1)
        except Exception:
            count = 1
        aspect_ratio = self.build_aspect_ratio(option_value(pick(kwargs, "Aspect_Ratio", "画面比例", "aspect_ratio", default="auto"), "auto"))
        resolution = self.build_resolution(option_value(pick(kwargs, "Resolution", "清晰度", "resolution", default="auto"), "auto"))
        response_format = self.build_response_format(option_value(pick(kwargs, "Response_Format", "返回方式", "response_format", default=RESPONSE_FORMAT_OPTIONS[0]), "url"))
        api_host = normalize_api_host(pick(kwargs, "Relay_Host", "中转站地址", "api_host", default=API_HOST_OPTIONS[0]))
        skip_error = bool(pick(kwargs, "Skip_Error", "跳过错误", "skip_error", default=False))
        width, height = self.size_from_options("Auto", aspect_ratio, resolution)
        pbar = comfy.utils.ProgressBar(100)

        try:
            if not api_key or api_key == "sk-":
                return (self.black_image(width, height), "ERROR: API key is empty.")
            if not prompt:
                return (self.black_image(width, height), "ERROR: Edit prompt is empty.")
            if kwargs.get("参考图1") is None:
                return (self.black_image(width, height), "ERROR: 请至少连接 参考图1。")
            if model != self.MODEL_ID:
                model = self.MODEL_ID

            refs = [kwargs.get("参考图1"), kwargs.get("参考图2"), kwargs.get("参考图3")]
            images = []
            for ref in refs:
                if ref is not None:
                    images.append({"type": "image_url", "url": self.image_to_data_url(ref)})
            images = images[:3]
            count = max(1, min(count, 10))
            context = self.request_context(model, "Auto", count, response_format, api_host, start_time, aspect_ratio, resolution)

            payload = {
                "model": model,
                "prompt": prompt,
                "n": count,
                "response_format": response_format,
            }
            if len(images) == 1:
                payload["image"] = images[0]
            else:
                payload["images"] = images
            if aspect_ratio != "auto":
                payload["aspect_ratio"] = aspect_ratio
            if resolution != "auto":
                payload["resolution"] = resolution

            idempotency_key = make_idempotency_key("grok-imagine-image-edit", {
                "model": model,
                "prompt": prompt,
                "n": count,
                "aspect_ratio": aspect_ratio,
                "resolution": resolution,
                "image_count": len(images),
            })
            session = self.create_session()
            url = f"{api_host}/v1/images/edits"
            payload_preview = dict(payload)
            if "image" in payload_preview:
                payload_preview["image"] = {"type": "image_url", "url": "[data:image omitted]"}
            if "images" in payload_preview:
                payload_preview["images"] = [{"type": "image_url", "url": "[data:image omitted]"} for _ in payload_preview["images"]]
            print(f"[Tikpan-GrokImagineEdit] Payload: {json.dumps(payload_preview, ensure_ascii=False, default=str)[:1200]}", flush=True)
            pbar.update(20)

            try:
                response = session.post(
                    url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "User-Agent": "Tikpan-ComfyUI-GrokImagineEdit/1.0",
                        "Idempotency-Key": idempotency_key,
                    },
                    timeout=(20, 420),
                    verify=False,
                )
            except (requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError) as exc:
                msg = (
                    "ERROR: Submit connection failed without automatic POST retry to avoid duplicate billing. "
                    f"{context()} | idempotency_key={idempotency_key} | {exc}"
                )
                if not skip_error:
                    raise RuntimeError(msg) from exc
                return (self.black_image(width, height), self.skip_error_message(msg))
            pbar.update(62)

            if response.status_code != 200:
                msg = self.format_http_error(response, context())
                if not skip_error:
                    raise RuntimeError(msg)
                return (self.black_image(width, height), self.skip_error_message(msg))

            try:
                res_json = response.json()
            except Exception:
                msg = f"ERROR: API returned non-JSON response | {context()} | {self.safe_response_text(response)}"
                if not skip_error:
                    raise RuntimeError(msg)
                return (self.black_image(width, height), self.skip_error_message(msg))

            api_error = self.extract_api_error(res_json)
            if api_error:
                msg = f"ERROR: Upstream rejected the Grok edit request | {context()} | {api_error}"
                if not skip_error:
                    raise RuntimeError(msg)
                return (self.black_image(width, height), self.skip_error_message(msg))

            image_items = self.extract_image_items(res_json)
            if not image_items:
                msg = f"ERROR: No image URL or base64 image was found in the Grok edit response | {context()}"
                if not skip_error:
                    raise RuntimeError(msg)
                return (self.black_image(width, height), self.skip_error_message(msg))

            tensors = []
            source_logs = []
            for idx, (img_raw, raw_type) in enumerate(image_items, start=1):
                image = self.load_result_image(session, img_raw, raw_type)
                tensors.append(self.pil_to_tensor(image))
                source_logs.append(f"{idx}:{raw_type}")
                pbar.update(62 + int(idx * 34 / max(len(image_items), 1)))

            batch = self.normalize_batch(tensors)
            cost_time = round(time.time() - start_time, 2)
            log_text = (
                f"SUCCESS: {self.MODEL_NAME} edited/generated {len(tensors)} image(s). "
                f"refs={len(images)}, model={model}, host={api_host}, aspect_ratio={aspect_ratio}, "
                f"resolution={resolution}, n={count}, response_format={response_format}, "
                f"sources={','.join(source_logs)}, elapsed={cost_time}s"
            )
            print(f"[Tikpan-GrokImagineEdit] {log_text}", flush=True)
            pbar.update(100)
            return (batch, log_text)

        except Exception as exc:
            tb = traceback.format_exc()
            msg = f"ERROR: {exc}\n{tb[:1000]}"
            print(f"[Tikpan-GrokImagineEdit] {msg}", flush=True)
            if not skip_error:
                raise
            return (self.black_image(width, height), self.skip_error_message(msg))


class TikpanGrokImagineImageEditNode(_TikpanGrokImagineEditBase):
    MODEL_ID = "grok-imagine-image"
    MODEL_NAME = "Grok Imagine Image Edit"
    PRICE_TEXT = "0.208 RMB per image"


class TikpanGrokImagineImageProEditNode(_TikpanGrokImagineEditBase):
    MODEL_ID = "grok-imagine-image-pro"
    MODEL_NAME = "Grok Imagine Image Pro Edit"
    PRICE_TEXT = "0.728 RMB per image"
