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
                "API_密钥": ("STRING", {"default": "sk-"}),

                "生成指令": ("STRING", {
                    "multiline": True,
                    "default": "一幅写实的极地极光景观，巨大的冰川倒映在平静的海面上，8k超清，电影感。"
                }),

                "模型": (["gpt-image-2"], {"default": "gpt-image-2"}),

                "分辨率档位": (
                    ["512", "1K (1024)", "2K (2048)", "4K (官方极限 3840)"],
                    {"default": "1K (1024)"}
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
                    {"default": "1:1"}
                ),

                "画质与推理强度": (
                    ["auto", "low", "medium", "high"],
                    {
                        "default": "medium",
                        "tooltip": "【auto/low】：速度更快、消耗更低。\n【medium/high】：画面细节更丰富，适合高品质创作。"
                    }
                ),

                "审核强度": (
                    ["auto", "low", "high"],
                    {
                        "default": "auto",
                        "tooltip": "【low】：更宽松。\n【high】：更严格。"
                    }
                ),

                "seed": ("INT", {
                    "default": 888888,
                    "min": 0,
                    "max": 0xffffffffffffffff
                }),
            },
            "optional": {
                "返回格式": (["png", "webp", "jpg"], {"default": "png"}),
                "跳过错误": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "开启后，网络异常、余额不足或接口异常时返回黑图，避免工作流中断。"
                }),
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("🖼️_生成结果图", "📄_渲染日志")
    FUNCTION = "generate"
    CATEGORY = "👑 Tikpan 官方独家节点"

    def generate(self, **kwargs):
        start_time = time.time()

        api_key = (kwargs.get("API_密钥") or "").strip()
        prompt = (kwargs.get("生成指令") or "").strip()
        model = kwargs.get("模型", "gpt-image-2")
        tier = kwargs.get("分辨率档位", "1K (1024)")
        aspect_ratio = kwargs.get("画面比例", "1:1")
        quality = kwargs.get("画质与推理强度", "medium")
        moderation = kwargs.get("审核强度", "auto")
        output_format = kwargs.get("返回格式", "png")
        seed = int(kwargs.get("seed", 0))
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

            url = f"{API_BASE_URL}/v1/images/generations"
            pbar.update(25)

            response = session.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "Tikpan-ComfyUI-GenNode/Final"
                },
                timeout=(connect_timeout, read_timeout),
                verify=False
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

            final_pil = self.load_result_image(session, img_raw, raw_type).convert("RGB")
            pbar.update(92)

            final_np = np.array(final_pil).astype(np.float32) / 255.0
            final_tensor = torch.from_numpy(final_np)[None, ...]

            cost_time = round(time.time() - start_time, 2)
            final_seed = seed & 0x7fffffff
            log_text = (
                f"✅ 渲染成功 | 模型: {model} | 比例: {aspect_ratio} | 尺寸: {target_res} | "
                f"质量: {quality} | 格式: {output_format} | seed: {final_seed} | 耗时: {cost_time}s"
            )

            print(f"[Tikpan-Gen] {log_text}", flush=True)
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
        data = res_json.get("data", [])
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
            item = data[0]
            img_raw = item.get("url") or item.get("b64_json") or item.get("image_base64")
            if img_raw:
                return img_raw, "url" if item.get("url") else "b64"

        if isinstance(res_json.get("result"), dict):
            item = res_json["result"]
            img_raw = item.get("url") or item.get("b64_json") or item.get("image_base64")
            if img_raw:
                return img_raw, "url" if item.get("url") else "b64"

        img_raw = res_json.get("url") or res_json.get("b64_json") or res_json.get("image_base64")
        if img_raw:
            return img_raw, "url" if res_json.get("url") else "b64"

        return None, None

    def load_result_image(self, session, img_raw, raw_type):
        if raw_type == "url" or str(img_raw).startswith("http"):
            r = session.get(img_raw, timeout=(15, 120), verify=False)
            r.raise_for_status()
            return Image.open(BytesIO(r.content))

        b64_clean = img_raw.split("base64,")[-1] if isinstance(img_raw, str) else img_raw
        image_bytes = base64.b64decode(b64_clean)
        return Image.open(BytesIO(image_bytes))

    def black_image(self, w, h):
        return torch.zeros((1, h, w, 3), dtype=torch.float32)