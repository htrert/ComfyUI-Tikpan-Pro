import json
import re
import time

import comfy.utils
import numpy as np
import torch
from PIL import Image

from .tikpan_gpt_image_2_official import TikpanGptImage2OfficialNode
from .tikpan_gpt_image_recovery import make_idempotency_key, safe_json_for_log, save_recovery_record, short_hash
from .tikpan_node_options import normalize_seed, option_value, pick


BENEFIT_CHANNELS = {
    "福利渠道一": "https://688.qzz.io",
}
DEFAULT_BENEFIT_CHANNEL = "福利渠道一"
BENEFIT_ENDPOINT = "/v1/chat/completions"


class TikpanGptImage2BenefitNode(TikpanGptImage2OfficialNode):
    @classmethod
    def INPUT_TYPES(cls):
        inputs = super().INPUT_TYPES()
        required = dict(inputs.get("required", {}))
        optional = dict(inputs.get("optional", {}))

        required["福利渠道"] = (
            list(BENEFIT_CHANNELS.keys()),
            {"default": DEFAULT_BENEFIT_CHANNEL, "tooltip": "选择内置福利中转渠道；当前为福利渠道一。"},
        )
        required["💎_源头拿货价福利_💎"] = (["福利渠道一"],)
        required["获取密钥请访问"] = (["请使用福利渠道一对应的 API Key"],)
        required["API_密钥"] = (
            "STRING",
            {"default": "sk-", "tooltip": "福利渠道 API 密钥，以 sk- 开头。"},
        )
        optional.pop("中转站地址", None)

        return {"required": required, "optional": optional}

    CATEGORY = "👑 Tikpan 官方独家节点/01 图片 Image"
    DESCRIPTION = ""

    def resolve_api_host(self, kwargs):
        channel = str(kwargs.get("福利渠道") or DEFAULT_BENEFIT_CHANNEL).strip()
        return BENEFIT_CHANNELS.get(channel, BENEFIT_CHANNELS[DEFAULT_BENEFIT_CHANNEL]).rstrip("/")

    def generate(self, **kwargs):
        start_time = time.time()
        api_key = str(kwargs.get("API_密钥") or "").strip()
        api_host = self.resolve_api_host(kwargs)
        prompt = str(kwargs.get("生成指令") or "").strip()
        model = str(kwargs.get("模型") or "gpt-image-2").strip() or "gpt-image-2"
        tier = kwargs.get("分辨率档位", "1K (1024)")
        aspect_ratio = kwargs.get("画面比例", "1:1")
        quality = option_value(kwargs.get("画质与推理强度", "均衡质量｜medium"), "medium")
        moderation = option_value(kwargs.get("审核强度", "自动审核｜auto"), "auto")
        output_format = option_value(kwargs.get("返回格式", "PNG｜png"), "png")
        seed = normalize_seed(pick(kwargs, "随机种子", "seed", default=888888), default=888888)
        skip_error = bool(kwargs.get("跳过错误", False))
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
            if output_format == "jpeg":
                output_format = "jpg"
            if output_format not in {"png", "webp", "jpg"}:
                output_format = "png"

            width, height, target_res = self.compute_target_resolution(tier=tier, aspect_ratio=aspect_ratio)
            connect_timeout, read_timeout = self.compute_timeout_by_tier(tier)
            payload = self.build_chat_payload(
                model=model,
                prompt=prompt,
                target_res=target_res,
                aspect_ratio=aspect_ratio,
                tier=tier,
                quality=quality,
                moderation=moderation,
                output_format=output_format,
                seed=seed,
            )
            idempotency_key = make_idempotency_key("chat/completions-benefit-generation", payload)
            save_recovery_record(
                "benefit_generation",
                idempotency_key,
                "pending",
                endpoint=BENEFIT_ENDPOINT,
                payload_hash=short_hash(payload),
                size=target_res,
                channel=kwargs.get("福利渠道", DEFAULT_BENEFIT_CHANNEL),
            )

            print(f"[Tikpan-Benefit-Gen] 🚀 福利渠道启动 | endpoint: {BENEFIT_ENDPOINT} | 档位: {tier} | 比例: {aspect_ratio}", flush=True)
            print(f"[Tikpan-Benefit-Gen] 🧾 模型: {model} | 质量: {quality} | 审核: {moderation} | 格式: {output_format}", flush=True)
            pbar.update(20)

            session = self.create_session()
            response = session.post(
                f"{api_host}{BENEFIT_ENDPOINT}",
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "Tikpan-ComfyUI-GPT-Image-2-Benefit/1.1",
                    "Idempotency-Key": idempotency_key,
                },
                timeout=(connect_timeout, read_timeout),
                verify=False,
            )
            pbar.update(60)

            if response.status_code != 200:
                err_text = self.safe_response_text(response, max_len=1600)
                msg = self.format_http_error(response.status_code, err_text)
                save_recovery_record(
                    "benefit_generation",
                    idempotency_key,
                    "http_error",
                    endpoint=BENEFIT_ENDPOINT,
                    http_status=response.status_code,
                    error=err_text,
                )
                print(f"[Tikpan-Benefit-Gen] {msg}", flush=True)
                if not skip_error:
                    raise RuntimeError(msg)
                return (self.black_image(width, height), msg)

            try:
                res_json = response.json()
            except Exception:
                msg = f"❌ 接口返回非 JSON 数据：{self.safe_response_text(response)}"
                if not skip_error:
                    raise RuntimeError(msg)
                return (self.black_image(width, height), msg)

            save_recovery_record(
                "benefit_generation",
                idempotency_key,
                "response_received",
                endpoint=BENEFIT_ENDPOINT,
                http_status=response.status_code,
                response=safe_json_for_log(res_json),
            )

            if isinstance(res_json, dict) and res_json.get("error"):
                err_obj = res_json.get("error")
                err_text = err_obj.get("message") if isinstance(err_obj, dict) else str(err_obj)
                msg = f"❌ 上游接口逻辑拒绝：{err_text}"
                if not skip_error:
                    raise RuntimeError(msg)
                return (self.black_image(width, height), msg)

            img_raw, raw_type = self.extract_chat_image_result(res_json)
            if not img_raw:
                msg = f"⚠️ 未找到有效图像数据。接口返回：{json.dumps(res_json, ensure_ascii=False)[:1600]}"
                if not skip_error:
                    raise RuntimeError(msg)
                return (self.black_image(width, height), msg)

            pbar.update(80)
            final_pil = self.load_result_image(session, img_raw, "url" if raw_type == "url" else "b64").convert("RGB")
            raw_size = final_pil.size
            final_pil = self.coerce_output_size(final_pil, width, height)
            final_tensor = torch.from_numpy(np.array(final_pil).astype(np.float32) / 255.0)[None, ...]
            elapsed = round(time.time() - start_time, 2)
            log_text = (
                f"✅ 渲染成功 | 福利渠道: {kwargs.get('福利渠道', DEFAULT_BENEFIT_CHANNEL)} | endpoint: {BENEFIT_ENDPOINT} | "
                f"模型: {model} | 比例: {aspect_ratio} | 尺寸: {target_res} | 质量: {quality} | seed: {seed & 0x7fffffff} | 耗时: {elapsed}s"
            )
            if raw_size != (width, height):
                log_text += f" | 上游原始尺寸: {raw_size[0]}x{raw_size[1]} | 已校正输出尺寸"
            if raw_type == "url":
                log_text += f" | 上游图片链接: {img_raw}"

            save_recovery_record(
                "benefit_generation",
                idempotency_key,
                "success",
                endpoint=BENEFIT_ENDPOINT,
                raw_type=raw_type,
                image_url=img_raw if raw_type == "url" else "",
            )
            pbar.update(100)
            return (final_tensor, log_text)
        except Exception as e:
            err_msg = f"❌ 运行故障: {str(e)}"
            print(f"[Tikpan-Benefit ERROR] {err_msg}", flush=True)
            if not skip_error:
                raise
            return (self.black_image(width, height), err_msg)

    def build_chat_payload(self, model, prompt, target_res, aspect_ratio, tier, quality, moderation, output_format, seed):
        image_size = self.normalize_image_size(tier)
        image_config = {
            "aspect_ratio": str(aspect_ratio),
            "image_size": image_size,
            "size": target_res,
            "format": output_format,
        }
        return {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self.build_prompt_with_size(prompt, target_res, aspect_ratio, image_size)},
                    ],
                }
            ],
            "modalities": ["text", "image"],
            "aspect_ratio": str(aspect_ratio),
            "image_size": image_size,
            "image_config": image_config,
            "response_format": {"image": image_config},
            "requested_size": target_res,
            "requested_resolution": target_res,
            "requested_aspect_ratio": str(aspect_ratio),
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
                "imageConfig": {
                    "aspectRatio": str(aspect_ratio),
                    "imageSize": image_size,
                },
            },
            "size": target_res,
            "quality": quality,
            "moderation": moderation,
            "format": output_format,
            "seed": int(seed) & 0x7fffffff,
        }

    def build_prompt_with_size(self, prompt, target_res, aspect_ratio, image_size):
        return (
            f"{prompt}\n\n"
            f"Output exactly one image. Required aspect ratio: {aspect_ratio}. " 
            f"Required output size: {target_res}. Resolution tier: {image_size}."
        )

    def coerce_output_size(self, image, target_width, target_height):
        target_width = int(target_width)
        target_height = int(target_height)
        if image.size == (target_width, target_height):
            return image

        src_width, src_height = image.size
        if src_width <= 0 or src_height <= 0 or target_width <= 0 or target_height <= 0:
            return image.resize((target_width, target_height), Image.Resampling.LANCZOS)

        target_ratio = target_width / target_height
        src_ratio = src_width / src_height
        if abs(src_ratio - target_ratio) > 0.01:
            if src_ratio > target_ratio:
                crop_width = max(1, int(round(src_height * target_ratio)))
                left = max(0, (src_width - crop_width) // 2)
                image = image.crop((left, 0, left + crop_width, src_height))
            else:
                crop_height = max(1, int(round(src_width / target_ratio)))
                top = max(0, (src_height - crop_height) // 2)
                image = image.crop((0, top, src_width, top + crop_height))

        return image.resize((target_width, target_height), Image.Resampling.LANCZOS)

    def normalize_image_size(self, tier):
        text = str(tier or "1K")
        if "4K" in text:
            return "4K"
        if "2K" in text:
            return "2K"
        if "512" in text:
            return "512"
        return "1K"

    def format_http_error(self, status_code, err_text):
        lower = str(err_text).lower()
        if "model_not_found" in lower or "no available channel" in lower:
            return f"❌ 福利渠道当前没有可用模型通道，或该渠道暂未开放 gpt-image-2。HTTP {status_code} | {err_text}"
        if "insufficient_quota" in lower:
            return "❌ 渲染失败：API 余额不足，请充值后重试。"
        if "rate limit" in lower or "too many requests" in lower:
            return "❌ 渲染失败：当前请求过于频繁，请稍后再试。"
        return f"❌ 接口请求失败 | HTTP {status_code} | {err_text}"

    def extract_chat_image_result(self, res_json):
        seen = set()

        def add(value):
            if not isinstance(value, str):
                return None
            value = value.strip()
            if not value or value in seen:
                return None
            seen.add(value)
            if value.startswith(("http://", "https://")):
                return value, "url"
            if value.startswith("data:image"):
                return value, "b64"
            if len(value) > 80 and re.search(r"^[A-Za-z0-9+/=\s\r\n]+$", value):
                return value, "b64"
            return self.extract_markdown_image(value)

        def scan(obj):
            if isinstance(obj, str):
                return add(obj)
            if isinstance(obj, list):
                for item in obj:
                    found = scan(item)
                    if found:
                        return found
                return None
            if not isinstance(obj, dict):
                return None
            for key in ("url", "image_url", "imageUrl", "output_url", "result_url", "b64_json", "image_base64", "base64", "image"):
                found = add(obj.get(key))
                if found:
                    return found
            nested = obj.get("image_url")
            if isinstance(nested, dict):
                found = add(nested.get("url"))
                if found:
                    return found
            for key in ("data", "result", "output", "images", "choices", "message", "content"):
                found = scan(obj.get(key))
                if found:
                    return found
            return None

        found = scan(res_json)
        if found:
            return found
        return None, None

    def extract_markdown_image(self, text):
        patterns = [
            r"!\[[^\]]*\]\((data:image/[^;\s)]+;base64,[A-Za-z0-9+/=\s\r\n]+)\)",
            r"\[[^\]]*\]\((data:image/[^;\s)]+;base64,[A-Za-z0-9+/=\s\r\n]+)\)",
            r"!\[[^\]]*\]\((https?://[^\s)]+)\)",
            r"\[[^\]]*\]\((https?://[^\s)]+)\)",
            r"(https?://[^\s)]+\.(?:png|jpg|jpeg|webp)(?:\?[^\s)]*)?)",
            r"(https?://t\.filesystem\.site/[^\s)]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = match.group(1).strip().rstrip(".,;")
                return value, "b64" if value.startswith("data:image") else "url"
        return None
