import math
import time
import base64
import urllib3
from io import BytesIO

import numpy as np
import requests
import torch
from PIL import Image, ImageFile
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import comfy.utils

from .tikpan_gpt_image_recovery import (
    get_with_retry,
    make_idempotency_key,
    save_base64_image,
    safe_json_for_log,
    save_recovery_record,
    short_hash,
)
from .tikpan_node_options import (
    API_HOST_OPTIONS,
    normalize_api_host,
    IMAGE_FORMAT_OPTIONS,
    MODERATION_OPTIONS,
    QUALITY_OPTIONS,
    normalize_seed,
    option_value,
    pick,
)

# 避免部分图片截断时报错
ImageFile.LOAD_TRUNCATED_IMAGES = True

# 屏蔽 verify=False 告警
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 固定绑定你的中转站
API_BASE_URL = "https://tikpan.com"


class TikpanGptImage2OfficialNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "💎_源头拿货价福利_💎": (
                    ["🔥 0.6元 RMB 兑换 👉 1美元余额 | 绝对全网底价"],
                ),
                "获取密钥请访问": (
                    ["👉 https://tikpan.com (官方授权Key获取点)"],
                ),
                "API_密钥": ("STRING", {"default": "sk-", "tooltip": "Tikpan 平台的 API 密钥，以 sk- 开头，从 https://tikpan.com 获取"}),

                "生成指令": ("STRING", {
                    "multiline": True,
                    "default": "一幅写实的极地极光景观，巨大的冰川倒映在平静的海面上，8k超清，电影感。",
                    "tooltip": "描述你想生成的画面，越具体越准确，支持中英文"
                }),

                "模型": (["gpt-image-2"], {"default": "gpt-image-2", "tooltip": "本节点使用的官方生图模型，目前仅 gpt-image-2"}),

                "分辨率档位": (
                    ["512", "1K (1024)", "2K (2048)", "4K (官方极限 3840)"],
                    {"default": "1K (1024)", "tooltip": "分辨率档位：档位越高画面越清晰，但更慢更贵；4K 接近官方极限"}
                ),

                "画面比例": (
                    [
                        "1:1",
                        "3:2",
                        "2:3",
                        "4:3",
                        "3:4",
                        "16:9",
                        "9:16",
                        "21:9",
                        "9:21"
                    ],
                    {"default": "1:1", "tooltip": "画面比例：1:1 通用，16:9 横屏风景，9:16 竖屏短视频"}
                ),

                "画质与推理强度": (
                    QUALITY_OPTIONS,
                    {
                        "default": "均衡质量｜medium",
                        "tooltip": "速度优先选“快速低消耗”，商业成片优先选“均衡质量”或“高质量细节”。"
                    }
                ),

                "审核强度": (
                    MODERATION_OPTIONS,
                    {
                        "default": "自动审核｜auto",
                        "tooltip": "一般保持自动审核；需要更严格的商用内容风控时选严格审核。"
                    }
                ),

                "随机种子": ("INT", {
                    "default": 888888,
                    "min": 0,
                    "max": 0xffffffffffffffff,
                    "tooltip": "同种子+同提示词可复现画面；改种子可换不同结果"
                }),
            },
            "optional": {
                "中转站地址": (API_HOST_OPTIONS, {"default": API_HOST_OPTIONS[0], "tooltip": "Tikpan 中转站地址，一般保持默认即可"}),
                "返回格式": (IMAGE_FORMAT_OPTIONS, {"default": "PNG｜png", "tooltip": "图像编码：PNG 无损画质好，JPEG/WEBP 体积小"}),
                "跳过错误": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "开启后，网络异常、余额不足或接口异常时返回黑图，避免工作流中断。"
                }),
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("🖼️_生成结果图", "📄_渲染日志")
    FUNCTION = "generate"
    CATEGORY = '👑 Tikpan 官方独家节点/01 图片 Image'
    DESCRIPTION = "📝 GPT-Image-2 官方原版生图：直连官方 /v1/images/generations 接口，支持 4K、9 种比例、quality/moderation 全参数控制。适合追求官方原生效果。"

    def generate(self, **kwargs):
        start_time = time.time()

        api_key = (kwargs.get("API_密钥") or "").strip()
        api_host = self.resolve_api_host(kwargs)
        prompt = (kwargs.get("生成指令") or "").strip()
        model = kwargs.get("模型", "gpt-image-2")
        tier = kwargs.get("分辨率档位", "1K (1024)")
        aspect_ratio = kwargs.get("画面比例", "1:1")
        quality = option_value(kwargs.get("画质与推理强度", "均衡质量｜medium"), "medium")
        moderation = option_value(kwargs.get("审核强度", "自动审核｜auto"), "auto")
        output_format = option_value(kwargs.get("返回格式", "PNG｜png"), "png")
        if output_format == "jpeg":
            output_format = "jpg"
        seed = normalize_seed(pick(kwargs, "随机种子", "seed", default=888888), default=888888)
        skip_error = kwargs.get("跳过错误", False)

        pbar = comfy.utils.ProgressBar(100)
        width, height = 1024, 1024

        try:
            if not api_key or api_key == "sk-":
                return (self.black_image(width, height), "❌ 错误：API 密钥为空，请填写有效密钥")

            if not prompt:
                return (self.black_image(width, height), "❌ 错误：生成指令不能为空")

            if model not in {"gpt-image-2"}:
                model = "gpt-image-2"

            if quality not in {"auto", "low", "medium", "high"}:
                quality = "medium"

            if moderation not in {"auto", "low", "high"}:
                moderation = "auto"

            if output_format not in {"png", "webp", "jpg"}:
                output_format = "png"

            print(f"[Tikpan-Gen] 🚀 引擎启动 | 档位: {tier} | 比例: {aspect_ratio}", flush=True)
            print(
                f"[Tikpan-Gen] 🧾 模型: {model} | 质量: {quality} | 审核: {moderation} | 格式: {output_format}",
                flush=True
            )
            pbar.update(5)

            session = self.create_session()

            width, height, target_res = self.compute_target_resolution(
                tier=tier,
                aspect_ratio=aspect_ratio
            )
            print(f"[Tikpan-Gen] 📐 物理输出尺寸: {target_res}", flush=True)
            pbar.update(15)

            connect_timeout, read_timeout = self.compute_timeout_by_tier(tier)
            print(
                f"[Tikpan-Gen] ⏱️ 网络策略: 握手 {connect_timeout}s | 最大等待 {read_timeout}s",
                flush=True
            )

            raw_payload = {
                "model": model,
                "prompt": prompt,
                "size": target_res,
                "quality": quality,
                "moderation": moderation,
                "format": output_format,
                "seed": seed & 0x7fffffff
            }

            allowed_keys = {
                "model",
                "prompt",
                "size",
                "quality",
                "moderation",
                "format",
                "seed"
            }
            payload = {
                k: v for k, v in raw_payload.items()
                if k in allowed_keys and v is not None
            }
            idempotency_key = make_idempotency_key("images/generations", payload)
            recovery_path = save_recovery_record(
                "official_generation",
                idempotency_key,
                "pending",
                endpoint="/v1/images/generations",
                payload_hash=short_hash(payload),
                size=target_res,
            )

            url = f"{api_host}/v1/images/generations"
            pbar.update(25)

            try:
                response = session.post(
                    url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "User-Agent": "Tikpan-ComfyUI-GenNode/Final",
                        "Idempotency-Key": idempotency_key,
                    },
                    timeout=(connect_timeout, read_timeout),
                    verify=False
                )
            except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
                save_recovery_record(
                    "official_generation",
                    idempotency_key,
                    "post_disconnected",
                    endpoint="/v1/images/generations",
                    payload_hash=short_hash(payload),
                    error=str(e),
                )
                raise RuntimeError(
                    "上游可能已经接收并执行了绘图请求，但本地等待响应时断开。"
                    f"请不要直接改参数重跑；可用相同参数重跑以复用幂等键。"
                    f" Idempotency-Key: {idempotency_key} | recovery: {recovery_path}"
                )
            pbar.update(70)

            if response.status_code != 200:
                err_text = self.safe_response_text(response)
                err_lower = err_text.lower()

                msg = f"❌ 接口请求失败 | HTTP {response.status_code} | {err_text}"

                if "insufficient_quota" in err_lower:
                    msg = "❌ 渲染失败：API 余额不足，请充值后重试。"
                elif "unknown_parameter" in err_lower or "unknown parameter" in err_lower:
                    msg = "❌ 渲染失败：上游渠道参数不兼容。"
                elif "invalid_request_error" in err_lower:
                    msg = "❌ 渲染失败：请求参数或提示词不被上游接受。"
                elif "rate limit" in err_lower or "too many requests" in err_lower:
                    msg = "❌ 渲染失败：当前请求过于频繁，请稍后再试。"

                print(f"[Tikpan-Gen] {msg}", flush=True)
                if not skip_error:
                    raise RuntimeError(msg)
                return (self.black_image(width, height), msg)

            try:
                res_json = response.json()
            except Exception:
                msg = f"❌ 接口返回非 JSON 数据：{self.safe_response_text(response)}"
                print(f"[Tikpan-Gen] {msg}", flush=True)
                if not skip_error:
                    raise RuntimeError(msg)
                return (self.black_image(width, height), msg)

            save_recovery_record(
                "official_generation",
                idempotency_key,
                "response_received",
                endpoint="/v1/images/generations",
                http_status=response.status_code,
                response=safe_json_for_log(res_json),
            )

            if isinstance(res_json, dict) and res_json.get("error"):
                err_obj = res_json.get("error")
                if isinstance(err_obj, dict):
                    err_text = err_obj.get("message") or str(err_obj)
                else:
                    err_text = str(err_obj)

                err_lower = err_text.lower()
                msg = f"❌ 上游接口逻辑拒绝：{err_text}"

                if "insufficient_quota" in err_lower:
                    msg = "❌ 渲染失败：API 余额不足。"
                elif "unknown_parameter" in err_lower or "unknown parameter" in err_lower:
                    msg = "❌ 渲染失败：上游渠道参数不兼容。"
                elif "invalid_request_error" in err_lower:
                    msg = "❌ 渲染失败：请求参数或提示词不被上游接受。"

                print(f"[Tikpan-Gen] {msg}", flush=True)
                if not skip_error:
                    raise RuntimeError(msg)
                return (self.black_image(width, height), msg)

            pbar.update(80)

            img_raw, raw_type = self.extract_image_result(res_json)
            if not img_raw:
                msg = "⚠️ 未找到有效图像数据。可能原因：审核拦截、上游返回结构异常或渠道兼容性问题。"
                print(f"[Tikpan-Gen] {msg}", flush=True)
                if not skip_error:
                    raise RuntimeError(msg)
                return (self.black_image(width, height), msg)

            save_recovery_record(
                "official_generation",
                idempotency_key,
                "image_pointer_received",
                endpoint="/v1/images/generations",
                raw_type=raw_type,
                image_url=img_raw if raw_type == "url" else "",
            )
            local_recovery_image = ""
            if raw_type == "b64":
                local_recovery_image = save_base64_image(idempotency_key, img_raw, output_format)
                save_recovery_record(
                    "official_generation",
                    idempotency_key,
                    "image_base64_saved",
                    endpoint="/v1/images/generations",
                    raw_type=raw_type,
                    local_image=local_recovery_image,
                )

            try:
                final_pil = self.load_result_image(session, img_raw, raw_type).convert("RGB")
            except Exception as e:
                save_recovery_record(
                    "official_generation",
                    idempotency_key,
                    "image_download_failed",
                    endpoint="/v1/images/generations",
                    raw_type=raw_type,
                    image_url=img_raw if raw_type == "url" else "",
                    error=str(e),
                )
                raise RuntimeError(
                    "上游已返回图片结果，但本地下载图片时失败；已保存恢复记录。"
                    f" Idempotency-Key: {idempotency_key} | recovery: {recovery_path}"
                    + (f" | image_url: {img_raw}" if raw_type == "url" else "")
                )
            pbar.update(92)

            final_np = np.array(final_pil).astype(np.float32) / 255.0
            final_tensor = torch.from_numpy(final_np)[None, ...]

            cost_time = round(time.time() - start_time, 2)
            final_seed = seed & 0x7fffffff
            log_text = (
                f"✅ 渲染成功 | 模型: {model} | 比例: {aspect_ratio} | 尺寸: {target_res} | "
                f"质量: {quality} | 格式: {output_format} | seed: {final_seed} | 耗时: {cost_time}s"
            )
            if raw_type == "url":
                log_text += f" | 上游图片链接: {img_raw}"
            elif local_recovery_image:
                log_text += f" | 上游未返回URL，已保存本地恢复图片: {local_recovery_image}"

            print(f"[Tikpan-Gen] {log_text}", flush=True)
            save_recovery_record(
                "official_generation",
                idempotency_key,
                "success",
                endpoint="/v1/images/generations",
                raw_type=raw_type,
                image_url=img_raw if raw_type == "url" else "",
                local_image=local_recovery_image,
            )
            pbar.update(100)

            return (final_tensor, log_text)

        except Exception as e:
            err_msg = f"❌ 运行故障: {str(e)}"
            print(f"[Tikpan ERROR] {err_msg}", flush=True)

            if not skip_error:
                raise
            return (self.black_image(width, height), err_msg)

    def create_session(self):
        session = requests.Session()
        session.trust_env = False

        return self.configure_session(session)

    def resolve_api_host(self, kwargs):
        return normalize_api_host(pick(kwargs, "中转站地址", "api_host", default=API_HOST_OPTIONS[0]))

    def configure_session(self, session):
        session.trust_env = False

        retries = Retry(
            total=3,
            connect=3,
            read=0,
            status=0,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=frozenset(["HEAD", "GET", "OPTIONS"])
        )

        adapter = HTTPAdapter(
            max_retries=retries,
            pool_connections=20,
            pool_maxsize=20
        )
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def compute_target_resolution(self, tier, aspect_ratio):
        target_pixels = 1048576
        if "2K" in tier:
            target_pixels = 4194304
        elif "4K" in tier:
            target_pixels = 8294400
        elif "512" in tier:
            target_pixels = 262144

        try:
            wr, hr = aspect_ratio.split(":")
            wr = float(wr)
            hr = float(hr)
            if wr <= 0 or hr <= 0:
                raise ValueError("invalid ratio")
            final_ratio = wr / hr
        except Exception:
            final_ratio = 1.0

        final_ratio = max(0.05, min(final_ratio, 20.0))

        h_calc = math.sqrt(target_pixels / final_ratio)
        w_calc = h_calc * final_ratio

        max_side = 3840
        min_side = 256

        if max(w_calc, h_calc) > max_side:
            scale = max_side / max(w_calc, h_calc)
            w_calc *= scale
            h_calc *= scale

        if min(w_calc, h_calc) < min_side:
            scale = min_side / min(w_calc, h_calc)
            w_calc *= scale
            h_calc *= scale

        width = max(256, int(round(w_calc / 16.0)) * 16)
        height = max(256, int(round(h_calc / 16.0)) * 16)

        width = min(width, max_side)
        height = min(height, max_side)

        width = max(256, (width // 16) * 16)
        height = max(256, (height // 16) * 16)

        return width, height, f"{width}x{height}"

    def compute_timeout_by_tier(self, tier):
        connect_timeout = 15

        if "4K" in tier:
            read_timeout = 480
        elif "2K" in tier:
            read_timeout = 360
        else:
            read_timeout = 240

        return connect_timeout, read_timeout

    def safe_response_text(self, response, max_len=1000):
        try:
            return response.text[:max_len].strip()
        except Exception:
            return "无法解析上游响应"

    def extract_image_result(self, res_json):
        seen = set()

        def extract_one(item):
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

        def add(parsed):
            if not parsed:
                return None
            key = (str(parsed[0]), parsed[1])
            if key in seen:
                return None
            seen.add(key)
            return parsed

        data = res_json.get("data", [])
        if isinstance(data, dict):
            parsed = add(extract_one(data))
            if parsed:
                return parsed
        elif isinstance(data, list):
            for item in data:
                parsed = add(extract_one(item))
                if parsed:
                    return parsed

        for key in ("result", "output", "images"):
            value = res_json.get(key)
            if isinstance(value, dict):
                parsed = add(extract_one(value))
                if parsed:
                    return parsed
            elif isinstance(value, list):
                for item in value:
                    parsed = add(extract_one(item))
                    if parsed:
                        return parsed

        parsed = add(extract_one(res_json))
        if parsed:
            return parsed

        return None, None

    def load_result_image(self, session, img_raw, raw_type):
        if raw_type == "url" or str(img_raw).startswith("http"):
            r = get_with_retry(session, img_raw, timeout=(15, 180), verify=False, attempts=4)
            return Image.open(BytesIO(r.content)).convert("RGB")

        b64_clean = img_raw.split("base64,")[-1] if isinstance(img_raw, str) else img_raw
        image_bytes = base64.b64decode(b64_clean)
        return Image.open(BytesIO(image_bytes)).convert("RGB")

    def black_image(self, w, h):
        return torch.zeros((1, h, w, 3), dtype=torch.float32)
