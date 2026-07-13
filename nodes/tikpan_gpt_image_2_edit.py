from .tikpan_categories import CATEGORY_IMAGE

import base64
import json
import re
from io import BytesIO

import comfy.utils
import numpy as np
import requests
import torch
from PIL import Image

from .tikpan_gpt_image_recovery import get_with_retry, make_idempotency_key, safe_json_for_log, save_recovery_record, save_request_snapshot, short_hash
from .tikpan_node_options import API_HOST_OPTIONS, normalize_api_host


GPT_IMAGE_2_C_MODEL = "gpt-image-2-c"


class TikpanGptImage2EditNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "获取密钥请访问": (["https://tikpan.com"],),
                "API_密钥": ("STRING", {"default": "sk-", "tooltip": "Tikpan 平台的 API 密钥，以 sk- 开头。"}),
                "底图": ("IMAGE", {"tooltip": "需要被修改/重绘的原始图像。"}),
                "修改指令": ("STRING", {"multiline": True, "default": "请把背景换成海边，主体保持一致。", "tooltip": "告诉 AI 怎么改这张图。"}),
                "模型": ([GPT_IMAGE_2_C_MODEL], {"default": GPT_IMAGE_2_C_MODEL, "tooltip": "旧版 gpt-image-2-all 修图节点恢复版，当前模型名为 gpt-image-2-c。"}),
                "输出尺寸": (["沿用底图尺寸", "512", "1K", "2K", "4K"], {"default": "沿用底图尺寸", "tooltip": "结果图分辨率。"}),
                "画面比例": (["沿用底图比例", "1:1", "16:9", "9:16", "21:9", "4:3", "3:4"], {"default": "沿用底图比例", "tooltip": "结果图比例。"}),
                "品质": (["标准｜standard", "高清｜hd"], {"default": "高清｜hd", "tooltip": "standard=更快；hd=细节更好。"}),
            },
            "optional": {
                "中转站地址": (API_HOST_OPTIONS, {"default": API_HOST_OPTIONS[0], "tooltip": "Tikpan 中转站地址，一般保持默认即可。"}),
                "遮罩_Mask": ("MASK", {"tooltip": "可选遮罩：白色区域=重绘，黑色区域=保持。"}),
                "产品参考图": ("IMAGE", {"tooltip": "可选参考图：让 AI 把这张图里的物体/风格融入结果。"}),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("重绘结果图", "渲染日志")
    FUNCTION = "edit"
    CATEGORY = CATEGORY_IMAGE
    DESCRIPTION = "GPT-Image-2-C 旧版兼容修图节点：恢复原 gpt-image-2-all 修图入口，模型名改为 gpt-image-2-c。"

    def edit(self, 获取密钥请访问, API_密钥, 底图, 修改指令, 模型, 输出尺寸="沿用底图尺寸", 画面比例="沿用底图比例", 品质="高清｜hd", 遮罩_Mask=None, 产品参考图=None, **kwargs):
        pbar = comfy.utils.ProgressBar(100)
        api_host = normalize_api_host(kwargs.get("中转站地址", API_HOST_OPTIONS[0]))
        session = requests.Session()
        session.trust_env = False
        quality = str(品质).split("｜")[-1].strip()
        model = GPT_IMAGE_2_C_MODEL if 模型 != GPT_IMAGE_2_C_MODEL else 模型

        def tensor_to_pil(tensor):
            arr = 255.0 * tensor[0].cpu().numpy()
            return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

        base_img = tensor_to_pil(底图)
        width, height = base_img.size
        if 输出尺寸 != "沿用底图尺寸":
            res_map = {"512": 512, "1K": 1024, "2K": 2048, "4K": 4096}
            base_val = res_map.get(输出尺寸, 1024)
            if 画面比例 == "沿用底图比例":
                w_ratio, h_ratio = width, height
            else:
                w_ratio, h_ratio = map(int, 画面比例.split(":"))
            if w_ratio >= h_ratio:
                width = base_val
                height = int(base_val * (h_ratio / w_ratio))
            else:
                height = base_val
                width = int(base_val * (w_ratio / h_ratio))

        width, height = max(8, (width // 8) * 8), max(8, (height // 8) * 8)
        base_img = base_img.resize((width, height), Image.LANCZOS)
        if 遮罩_Mask is not None:
            mask_arr = 遮罩_Mask.cpu().numpy()
            mask_img = Image.fromarray((mask_arr * 255).astype(np.uint8)).convert("L")
            mask_img = mask_img.resize((width, height), Image.LANCZOS)
            base_img.putalpha(mask_img)

        buf_base = BytesIO()
        base_img.save(buf_base, format="PNG")
        base_b64 = base64.b64encode(buf_base.getvalue()).decode("utf-8")

        content = [{"type": "text", "text": f"### EDIT TASK ###\n{修改指令}\n[Maintain consistent lighting and perspective]"}]
        content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base_b64}"}})
        if 产品参考图 is not None:
            prod_img = tensor_to_pil(产品参考图)
            buf_prod = BytesIO()
            prod_img.save(buf_prod, format="JPEG", quality=80)
            prod_b64 = base64.b64encode(buf_prod.getvalue()).decode("utf-8")
            content.append({"type": "text", "text": "This is the product/style reference to incorporate:"})
            content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{prod_b64}"}})

        headers = {"Authorization": f"Bearer {API_密钥}", "Content-Type": "application/json"}
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": content}],
            "size": f"{width}x{height}",
            "quality": quality,
        }

        idempotency_key = make_idempotency_key("gpt-image-2-c-chat-edit", payload)
        headers["Idempotency-Key"] = idempotency_key
        request_snapshot_path = save_request_snapshot(
            "gpt_image_2_c_edit",
            idempotency_key,
            payload,
            endpoint="/v1/chat/completions",
            payload_hash=short_hash(payload),
            size=f"{width}x{height}",
        )
        recovery_path = save_recovery_record(
            "gpt_image_2_c_edit",
            idempotency_key,
            "pending",
            endpoint="/v1/chat/completions",
            payload_hash=short_hash(payload),
            size=f"{width}x{height}",
            request_snapshot=request_snapshot_path,
        )

        try:
            pbar.update(30)
            response = self.post_chat_completion_with_retry(
                session,
                f"{api_host}/v1/chat/completions",
                payload,
                headers,
                idempotency_key,
                recovery_path,
            )
            if response.status_code != 200:
                return (self.black_image(width, height), f"ERROR: HTTP {response.status_code}: {response.text[:1200]}")

            res_json = response.json()
            save_recovery_record(
                "gpt_image_2_c_edit",
                idempotency_key,
                "response_received",
                endpoint="/v1/chat/completions",
                http_status=response.status_code,
                response=safe_json_for_log(res_json),
            )
            pbar.update(80)
            img_raw = self.extract_image_pointer(res_json)
            if not img_raw:
                return (self.black_image(width, height), f"No image data found in response: {json.dumps(res_json, ensure_ascii=False)[:1200]}")

            final_img = self.load_result_image(session, img_raw)
            img_np = np.array(final_img).astype(np.float32) / 255.0
            pbar.update(100)
            if str(img_raw).startswith("http"):
                return (torch.from_numpy(img_np)[None, ...], f"success | model={model} | upstream_image_url: {img_raw}")
            return (torch.from_numpy(img_np)[None, ...], f"success | model={model} | source=base64")
        except Exception as e:
            return (self.black_image(width, height), f"ERROR: {str(e)}")

    def post_chat_completion_with_retry(self, session, url, payload, headers, idempotency_key, recovery_path):
        payload_hash = short_hash(payload)
        attempts = [600, 900, 1200]
        last_error = None
        for attempt_index, read_timeout in enumerate(attempts, start=1):
            try:
                response = session.post(url, json=payload, headers=headers, timeout=(15, read_timeout), verify=False)
                if attempt_index > 1:
                    save_recovery_record(
                        "gpt_image_2_c_edit",
                        idempotency_key,
                        "post_recovered_after_retry",
                        endpoint="/v1/chat/completions",
                        payload_hash=payload_hash,
                        retry_attempt=attempt_index,
                        read_timeout_seconds=read_timeout,
                        request_snapshot=recovery_path.replace(".json", ".request.json"),
                    )
                return response
            except requests.exceptions.ConnectTimeout as e:
                last_error = e
                save_recovery_record("gpt_image_2_c_edit", idempotency_key, "connect_timeout", endpoint="/v1/chat/completions", payload_hash=payload_hash, retry_attempt=attempt_index, error=str(e))
                break
            except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
                last_error = e
                save_recovery_record("gpt_image_2_c_edit", idempotency_key, "post_disconnected_retrying" if attempt_index < len(attempts) else "post_disconnected", endpoint="/v1/chat/completions", payload_hash=payload_hash, retry_attempt=attempt_index, read_timeout_seconds=read_timeout, error=str(e))
                if attempt_index < len(attempts):
                    continue
        raise RuntimeError(
            "Upstream may have accepted the edit request, but the local connection dropped while waiting. "
            f"Idempotency-Key: {idempotency_key} | recovery: {recovery_path} | last_error: {last_error}"
        )

    def black_image(self, w, h):
        return torch.zeros((1, h, w, 3), dtype=torch.float32)

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
            for key in ("url", "image_url", "imageUrl", "b64_json", "image_base64", "base64", "image"):
                found = add(item.get(key))
                if found:
                    return found
            nested = item.get("image_url")
            if isinstance(nested, dict):
                found = add(nested.get("url"))
                if found:
                    return found
            content = item.get("content")
            if content is not None:
                found = from_item(content)
                if found:
                    return found
            for key in ("data", "result", "output", "images", "choices", "message"):
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
            img_res = get_with_retry(session, img_raw, timeout=(10, 120), verify=False, attempts=4)
            return Image.open(BytesIO(img_res.content)).convert("RGB")
        clean = re.sub(r"[^A-Za-z0-9+/=]", "", img_raw.split("base64,")[-1])
        missing_padding = len(clean) % 4
        if missing_padding:
            clean += "=" * (4 - missing_padding)
        return Image.open(BytesIO(base64.b64decode(clean))).convert("RGB")


NODE_CLASS_MAPPINGS = {"TikpanGptImage2EditNode": TikpanGptImage2EditNode}
NODE_DISPLAY_NAME_MAPPINGS = {"TikpanGptImage2EditNode": "图片｜GPT-Image-2-C 旧版修图"}
