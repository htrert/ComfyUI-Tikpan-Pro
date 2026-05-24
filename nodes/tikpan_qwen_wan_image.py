import base64
import hashlib
import json
import time
import traceback
from io import BytesIO

import numpy as np
import requests
import torch
import urllib3
from PIL import Image, ImageFile
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import comfy.utils

from .tikpan_gpt_image_recovery import get_with_retry, make_idempotency_key
from .tikpan_node_options import API_HOST_OPTIONS, RESPONSE_FORMAT_OPTIONS, normalize_api_host, option_value, pick


ImageFile.LOAD_TRUNCATED_IMAGES = True
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ASPECT_RATIO_OPTIONS = ["auto", "1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "2:1", "1:2"]
QWEN_RESOLUTION_OPTIONS = ["auto", "1k", "2k"]
WAN_RESOLUTION_OPTIONS = ["auto", "1k", "2k", "4k"]
SIZE_OPTIONS = ["Auto", "1024x1024", "1536x1024", "1024x1536", "1920x1080", "1080x1920", "2048x2048", "4096x4096"]
QUALITY_OPTIONS = ["自动｜auto", "速度优先｜speed", "均衡｜balanced", "高质量｜quality"]
TASK_MODE_OPTIONS = ["自动｜auto", "文生图｜text2image", "图生图/编辑｜image2image", "多图参考｜reference"]
WAN_THINKING_OPTIONS = ["自动｜auto", "关闭｜false", "开启｜true"]


class _TikpanOpenImageBase:
    MODEL_ID = ""
    MODEL_NAME = ""
    PRICE_TEXT = ""
    RESOLUTION_OPTIONS = QWEN_RESOLUTION_OPTIONS
    MAX_REFERENCE_IMAGES = 4
    DEFAULT_PROMPT = "A high quality commercial image, realistic lighting, detailed composition."

    @classmethod
    def INPUT_TYPES(cls):
        optional = {
            "兼容尺寸": (SIZE_OPTIONS, {"default": "Auto"}),
            "中转站地址": (API_HOST_OPTIONS, {"default": API_HOST_OPTIONS[0]}),
            "返回方式": (RESPONSE_FORMAT_OPTIONS, {"default": RESPONSE_FORMAT_OPTIONS[0]}),
            "跳过错误": (
                "BOOLEAN",
                {
                    "default": False,
                    "tooltip": "开启后，请求失败时返回黑图，避免整个工作流中断。",
                },
            ),
            "高级自定义JSON": (
                "STRING",
                {
                    "multiline": True,
                    "default": "",
                    "tooltip": "会深度合并到 /v1/images/generations payload，方便 Tikpan/上游新增参数。",
                },
            ),
        }
        for index in range(1, cls.MAX_REFERENCE_IMAGES + 1):
            optional[f"参考图{index}"] = ("IMAGE",)
        return {
            "required": {
                "💰_福利_💰": (
                    ["🔥 0.6元≈1美金余额 | 全网底价 👉 https://tikpan.com"],
                ),
                "获取密钥请访问": (
                    ["👉 https://tikpan.com (官方授权 Key 获取地址)"],
                ),
                "节点说明": ([f"{cls.MODEL_NAME} | /v1/images/generations | {cls.PRICE_TEXT}"],),
                "API_密钥": ("STRING", {"default": "sk-"}),
                "生成指令": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": cls.DEFAULT_PROMPT,
                    },
                ),
                "模型": ([cls.MODEL_ID], {"default": cls.MODEL_ID}),
                "生成张数": ("INT", {"default": 1, "min": 1, "max": 4, "step": 1}),
                "生成模式": (TASK_MODE_OPTIONS, {"default": TASK_MODE_OPTIONS[0]}),
                "画面比例": (ASPECT_RATIO_OPTIONS, {"default": "auto"}),
                "清晰度": (cls.RESOLUTION_OPTIONS, {"default": "auto"}),
                "画质策略": (QUALITY_OPTIONS, {"default": QUALITY_OPTIONS[0]}),
                "随机种子": ("INT", {"default": 888888, "min": 0, "max": 0xFFFFFFFFFFFFFFFF}),
            },
            "optional": optional,
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("Image", "Log")
    FUNCTION = "generate"
    CATEGORY = "👑 Tikpan 官方独家节点/01 图片 Image"

    def generate(self, **kwargs):
        start_time = time.time()
        api_key = str(pick(kwargs, "API_密钥", "API_Key", "api_key", default="") or "").strip()
        prompt = str(pick(kwargs, "生成指令", "Prompt", "prompt", default="") or "").strip()
        model = str(pick(kwargs, "模型", "Model", "model", default=self.MODEL_ID) or self.MODEL_ID).strip()
        count = self.safe_int(pick(kwargs, "生成张数", "Count", "n", default=1), 1, 1, 4)
        mode = option_value(pick(kwargs, "生成模式", "mode", default=TASK_MODE_OPTIONS[0]), "auto")
        aspect_ratio = self.normalize_choice(pick(kwargs, "画面比例", "aspect_ratio", default="auto"), ASPECT_RATIO_OPTIONS, "auto")
        resolution = self.normalize_choice(pick(kwargs, "清晰度", "resolution", default="auto"), self.RESOLUTION_OPTIONS, "auto")
        quality = option_value(pick(kwargs, "画质策略", "quality", default=QUALITY_OPTIONS[0]), "auto")
        size = str(pick(kwargs, "兼容尺寸", "size", default="Auto") or "Auto").strip()
        seed = self.safe_int(pick(kwargs, "随机种子", "seed", default=888888), 888888, 0, 0x7FFFFFFF)
        response_format = self.build_response_format(option_value(pick(kwargs, "返回方式", "response_format", default=RESPONSE_FORMAT_OPTIONS[0]), "url"))
        api_host = normalize_api_host(pick(kwargs, "中转站地址", "Relay_Host", "api_host", default=API_HOST_OPTIONS[0]))
        skip_error = bool(pick(kwargs, "跳过错误", "Skip_Error", "skip_error", default=False))

        width, height = self.size_from_options(size, aspect_ratio, resolution)
        pbar = comfy.utils.ProgressBar(100)

        try:
            if not api_key or api_key == "sk-" or len(api_key) < 10:
                return (self.black_image(width, height), "ERROR: API key is empty.")
            if not prompt:
                return (self.black_image(width, height), "ERROR: Prompt is empty.")
            if model != self.MODEL_ID:
                model = self.MODEL_ID
            if quality not in {"auto", "speed", "balanced", "quality"}:
                quality = "auto"
            if size not in SIZE_OPTIONS:
                size = "Auto"
                width, height = self.size_from_options(size, aspect_ratio, resolution)

            pbar.update(8)
            session = self.create_session()
            reference_images = self.collect_reference_images(kwargs)
            resolved_mode = self.resolve_mode(mode, reference_images)
            payload = self.build_payload(model, prompt, count, resolved_mode, aspect_ratio, resolution, quality, size, seed, response_format, reference_images, kwargs)
            custom_json = self.parse_custom_json(pick(kwargs, "高级自定义JSON", "custom_json", default=""))
            if custom_json:
                payload = self.deep_merge(payload, custom_json)

            url = f"{api_host}/v1/images/generations"
            idempotency_key = make_idempotency_key(self.MODEL_ID, payload)
            payload_preview = json.dumps(self.redact_payload(payload), ensure_ascii=False, default=str)[:1600]
            print(f"[Tikpan-{self.MODEL_ID}] Payload: {payload_preview}", flush=True)
            pbar.update(18)

            try:
                response = session.post(
                    url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "User-Agent": f"Tikpan-ComfyUI-{self.MODEL_ID}/1.0",
                        "Idempotency-Key": idempotency_key,
                    },
                    timeout=(15, self.timeout_seconds(resolution, size)),
                    verify=False,
                )
            except (requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError) as exc:
                msg = (
                    "ERROR: Submit connection failed without blind POST retry to avoid duplicate billing. "
                    f"model={model} | idempotency_key={idempotency_key} | {exc}"
                )
                if not skip_error:
                    raise RuntimeError(msg) from exc
                return (self.black_image(width, height), self.skip_error_message(msg))

            pbar.update(62)
            if response.status_code >= 400:
                msg = self.format_http_error(response, model, aspect_ratio, resolution, size, count, api_host)
                if not skip_error:
                    raise RuntimeError(msg)
                return (self.black_image(width, height), self.skip_error_message(msg))

            try:
                res_json = response.json()
            except Exception:
                msg = f"ERROR: API returned non-JSON response | {self.safe_response_text(response)}"
                if not skip_error:
                    raise RuntimeError(msg)
                return (self.black_image(width, height), self.skip_error_message(msg))

            api_error = self.extract_api_error(res_json)
            if api_error:
                msg = f"ERROR: Upstream rejected the image request | model={model} | {api_error}"
                if not skip_error:
                    raise RuntimeError(msg)
                return (self.black_image(width, height), self.skip_error_message(msg))

            image_items = self.extract_image_items(res_json)
            if not image_items:
                msg = f"ERROR: No image URL or base64 image was found in the API response | model={model}"
                if not skip_error:
                    raise RuntimeError(msg)
                return (self.black_image(width, height), self.skip_error_message(msg))

            pbar.update(76)
            tensors = []
            source_logs = []
            for idx, (img_raw, raw_type) in enumerate(image_items, start=1):
                image = self.load_result_image(session, img_raw, raw_type)
                tensors.append(self.pil_to_tensor(image))
                source_logs.append(f"{idx}:{raw_type}")
                pbar.update(76 + int(idx * 18 / max(len(image_items), 1)))

            image_batch = self.normalize_batch(tensors)
            elapsed = round(time.time() - start_time, 2)
            log = (
                f"SUCCESS: {self.MODEL_NAME} generated {len(tensors)} image(s). "
                f"model={model}, mode={resolved_mode}, refs={len(reference_images)}, aspect_ratio={aspect_ratio}, "
                f"resolution={resolution}, size={size}, quality={quality}, n={count}, response_format={response_format}, "
                f"sources={','.join(source_logs)}, elapsed={elapsed}s"
            )
            print(f"[Tikpan-{self.MODEL_ID}] {log}", flush=True)
            pbar.update(100)
            return (image_batch, log)
        except Exception as exc:
            tb = traceback.format_exc()
            msg = f"ERROR: {exc}\n{tb[:1400]}"
            print(f"[Tikpan-{self.MODEL_ID}] {msg}", flush=True)
            if not skip_error:
                raise
            return (self.black_image(width, height), self.skip_error_message(msg))

    def build_payload(self, model, prompt, count, mode, aspect_ratio, resolution, quality, size, seed, response_format, reference_images, kwargs):
        payload = {
            "model": model,
            "prompt": prompt,
            "n": count,
            "response_format": response_format,
            "seed": seed,
        }
        if mode != "auto":
            payload["mode"] = mode
        if aspect_ratio != "auto":
            payload["aspect_ratio"] = aspect_ratio
        if resolution != "auto":
            payload["resolution"] = resolution
        if quality != "auto":
            payload["quality"] = quality
        if size != "Auto":
            payload["size"] = size
        if reference_images:
            payload["images"] = reference_images
            payload["reference_images"] = reference_images
            payload["image"] = reference_images[0]
        return payload

    def resolve_mode(self, mode, reference_images):
        if mode != "auto":
            return mode
        if len(reference_images) > 1:
            return "reference"
        if len(reference_images) == 1:
            return "image2image"
        return "text2image"

    def collect_reference_images(self, kwargs):
        images = []
        for index in range(1, self.MAX_REFERENCE_IMAGES + 1):
            tensor = pick(kwargs, f"参考图{index}", f"ref_image_{index}", default=None)
            if tensor is not None:
                images.append(self.tensor_to_data_url(tensor))
        return images

    def tensor_to_data_url(self, img_tensor, quality=92):
        if len(img_tensor.shape) == 4:
            img_tensor = img_tensor[0]
        arr = 255.0 * img_tensor.detach().cpu().numpy()
        arr = np.clip(arr, 0, 255).astype(np.uint8)
        image = Image.fromarray(arr).convert("RGB")
        buf = BytesIO()
        image.save(buf, format="JPEG", quality=int(quality), optimize=True)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")

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

    def parse_custom_json(self, raw):
        raw = str(raw or "").strip()
        if not raw:
            return None
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("高级自定义JSON 顶层必须是 JSON object")
        return parsed

    def deep_merge(self, base, override):
        if not isinstance(base, dict) or not isinstance(override, dict):
            return override
        merged = dict(base)
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = self.deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged

    def safe_int(self, value, default, minimum, maximum):
        try:
            number = int(value)
        except Exception:
            number = int(default)
        return max(minimum, min(maximum, number))

    def normalize_choice(self, value, choices, default):
        raw = option_value(value, default)
        return raw if raw in set(choices) else default

    def build_response_format(self, value):
        return value if value in {"url", "b64_json"} else "url"

    def timeout_seconds(self, resolution, size):
        if resolution == "4k" or str(size).startswith("4096"):
            return 420
        if resolution == "2k" or str(size).startswith("2048"):
            return 300
        return 240

    def size_from_options(self, size, aspect_ratio="auto", resolution="auto"):
        if size and size != "Auto":
            try:
                width_text, height_text = str(size).split("x", 1)
                return int(width_text), int(height_text)
            except Exception:
                pass
        long_edge = {"auto": 1024, "1k": 1024, "2k": 2048, "4k": 4096}.get(str(resolution), 1024)
        ratio_map = {
            "1:1": (1, 1),
            "16:9": (16, 9),
            "9:16": (9, 16),
            "4:3": (4, 3),
            "3:4": (3, 4),
            "3:2": (3, 2),
            "2:3": (2, 3),
            "2:1": (2, 1),
            "1:2": (1, 2),
        }
        w_ratio, h_ratio = ratio_map.get(aspect_ratio, (1, 1))
        if w_ratio >= h_ratio:
            width = long_edge
            height = int(long_edge * h_ratio / w_ratio)
        else:
            height = long_edge
            width = int(long_edge * w_ratio / h_ratio)
        return max(64, (width // 8) * 8), max(64, (height // 8) * 8)

    def black_image(self, width=1024, height=1024):
        width = max(64, int(width or 1024))
        height = max(64, int(height or 1024))
        return torch.zeros((1, height, width, 3), dtype=torch.float32)

    def pil_to_tensor(self, image):
        image = image.convert("RGB")
        arr = np.array(image).astype(np.float32) / 255.0
        return torch.from_numpy(arr)[None, ...]

    def normalize_batch(self, tensors):
        if not tensors:
            return self.black_image()
        max_h = max(t.shape[1] for t in tensors)
        max_w = max(t.shape[2] for t in tensors)
        normalized = []
        for tensor in tensors:
            if tensor.shape[1] == max_h and tensor.shape[2] == max_w:
                normalized.append(tensor)
                continue
            image = Image.fromarray(np.clip(tensor[0].cpu().numpy() * 255, 0, 255).astype(np.uint8)).convert("RGB")
            image = image.resize((max_w, max_h), Image.LANCZOS)
            normalized.append(self.pil_to_tensor(image))
        return torch.cat(normalized, dim=0)

    def load_result_image(self, session, img_raw, raw_type):
        if raw_type == "url" or str(img_raw).startswith("http"):
            response = get_with_retry(session, img_raw, timeout=(15, 180), verify=False, attempts=4)
            return Image.open(BytesIO(response.content)).convert("RGB")
        clean = str(img_raw).split("base64,")[-1]
        return Image.open(BytesIO(base64.b64decode(clean))).convert("RGB")

    def extract_image_items(self, res_json):
        items = []
        seen = set()

        def add(parsed):
            if not parsed:
                return
            key = (parsed[0], parsed[1])
            if key in seen:
                return
            seen.add(key)
            items.append(parsed)

        def walk(obj):
            if isinstance(obj, dict):
                add(self.extract_one_image(obj))
                for key in ("data", "result", "output", "images", "image", "generations"):
                    value = obj.get(key)
                    if isinstance(value, (dict, list)):
                        walk(value)
            elif isinstance(obj, list):
                for item in obj:
                    walk(item)

        walk(res_json)
        return items

    def extract_one_image(self, item):
        if not isinstance(item, dict):
            return None
        url = item.get("url") or item.get("image_url") or item.get("imageUrl") or item.get("output_url") or item.get("result_url")
        if isinstance(url, str) and url.startswith(("http://", "https://")):
            return url, "url"
        b64 = item.get("b64_json") or item.get("image_base64") or item.get("base64") or item.get("image")
        if isinstance(b64, str) and (b64.startswith("data:image") or len(b64) > 200):
            return b64, "base64"
        return None

    def extract_api_error(self, data):
        if not isinstance(data, dict):
            return ""
        error = data.get("error") or data.get("message") or data.get("err_msg") or data.get("error_message")
        if isinstance(error, dict):
            return json.dumps(error, ensure_ascii=False, default=str)[:1000]
        if isinstance(error, str) and error:
            return error[:1000]
        return ""

    def format_http_error(self, response, model, aspect_ratio, resolution, size, count, api_host):
        return (
            f"ERROR: HTTP {response.status_code} | model={model} | host={api_host} | "
            f"aspect_ratio={aspect_ratio} | resolution={resolution} | size={size} | n={count} | "
            f"{self.safe_response_text(response)}"
        )

    def safe_response_text(self, response, max_len=1200):
        try:
            return response.text[:max_len].strip()
        except Exception:
            return "Unable to parse upstream response."

    def skip_error_message(self, message):
        return f"{message}\nSkip_Error=True, returned a black placeholder image to keep workflow running."

    def redact_payload(self, value):
        if isinstance(value, str):
            if value.startswith("data:image"):
                return "data:image/[base64 omitted]"
            if len(value) > 1000:
                return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}:len={len(value)}"
            return value
        if isinstance(value, list):
            return [self.redact_payload(item) for item in value]
        if isinstance(value, dict):
            return {key: self.redact_payload(child) for key, child in value.items()}
        return value


class TikpanQwenImage20Node(_TikpanOpenImageBase):
    MODEL_ID = "qwen-image-2.0-2026-03-03"
    MODEL_NAME = "Qwen-Image-2.0 2026-03-03"
    PRICE_TEXT = "Qwen Image 2.0 加速版 | 文字渲染/真实质感/生图编辑融合"
    RESOLUTION_OPTIONS = QWEN_RESOLUTION_OPTIONS
    MAX_REFERENCE_IMAGES = 4
    DEFAULT_PROMPT = "一张高端商业海报，包含清晰准确的中文标题文字，真实材质，细腻光影，专业排版。"

    def build_payload(self, model, prompt, count, mode, aspect_ratio, resolution, quality, size, seed, response_format, reference_images, kwargs):
        payload = super().build_payload(model, prompt, count, mode, aspect_ratio, resolution, quality, size, seed, response_format, reference_images, kwargs)
        payload["text_rendering"] = True
        payload["instruction_tokens"] = "1k"
        return payload


class TikpanWan27ImageProNode(_TikpanOpenImageBase):
    MODEL_ID = "wan2.7-image-pro"
    MODEL_NAME = "Wan 2.7 Image Pro"
    PRICE_TEXT = "万相 2.7 专业图像 | 4K/编辑/多图参考/成套图/主体一致性"
    RESOLUTION_OPTIONS = WAN_RESOLUTION_OPTIONS
    MAX_REFERENCE_IMAGES = 8
    DEFAULT_PROMPT = "生成一张高端商业产品图，主体一致，真实材质，复杂场景自然融合，4K级细节。"

    @classmethod
    def INPUT_TYPES(cls):
        schema = super().INPUT_TYPES()
        schema["required"]["清晰度"] = (cls.RESOLUTION_OPTIONS, {"default": "2k"})
        schema["optional"]["思考模式"] = (WAN_THINKING_OPTIONS, {"default": WAN_THINKING_OPTIONS[0]})
        schema["optional"]["成套图数量"] = ("INT", {"default": 1, "min": 1, "max": 9, "step": 1})
        schema["optional"]["主体保持"] = ("BOOLEAN", {"default": True})
        schema["optional"]["品牌色/色板"] = ("STRING", {"default": "", "tooltip": "例如 #FF6600, black, gold。会透传为 palette。"})
        schema["optional"]["编辑区域BBOX"] = (
            "STRING",
            {
                "default": "",
                "tooltip": "可选 JSON 数组，例如 [0.1,0.2,0.6,0.8]，用于局部编辑区域。",
            },
        )
        return schema

    def build_payload(self, model, prompt, count, mode, aspect_ratio, resolution, quality, size, seed, response_format, reference_images, kwargs):
        payload = super().build_payload(model, prompt, count, mode, aspect_ratio, resolution, quality, size, seed, response_format, reference_images, kwargs)
        thinking = option_value(pick(kwargs, "思考模式", "thinking", default=WAN_THINKING_OPTIONS[0]), "auto")
        image_set_count = self.safe_int(pick(kwargs, "成套图数量", "image_set_count", default=1), 1, 1, 9)
        consistency = bool(pick(kwargs, "主体保持", "subject_consistency", default=True))
        palette = str(pick(kwargs, "品牌色/色板", "palette", default="") or "").strip()
        bbox_raw = str(pick(kwargs, "编辑区域BBOX", "bbox", default="") or "").strip()
        payload["subject_consistency"] = consistency
        payload["image_set_count"] = image_set_count
        if thinking in {"true", "false"}:
            payload["thinking"] = thinking == "true"
        if palette:
            payload["palette"] = [item.strip() for item in palette.replace("，", ",").split(",") if item.strip()]
        if bbox_raw:
            try:
                bbox = json.loads(bbox_raw)
            except Exception as exc:
                raise ValueError(f"编辑区域BBOX 不是合法 JSON: {exc}") from exc
            payload["bbox"] = bbox
        return payload


NODE_CLASS_MAPPINGS = {
    "TikpanQwenImage20Node": TikpanQwenImage20Node,
    "TikpanWan27ImageProNode": TikpanWan27ImageProNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TikpanQwenImage20Node": "图片｜Qwen-Image-2.0 生图/编辑",
    "TikpanWan27ImageProNode": "图片｜Wan 2.7 Image Pro 生图/编辑",
}
