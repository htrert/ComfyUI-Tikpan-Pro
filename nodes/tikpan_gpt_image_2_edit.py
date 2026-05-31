import json
import requests
import base64
import torch
import re
import numpy as np
from io import BytesIO
from PIL import Image, ImageOps
import comfy.utils
from .tikpan_node_options import API_HOST_OPTIONS, normalize_api_host
from .tikpan_gpt_image_recovery import get_with_retry, make_idempotency_key, safe_json_for_log, save_recovery_record, save_request_snapshot, short_hash

# 🔐 Tikpan 官方聚合路由
API_BASE_URL = "https://tikpan.com"

class TikpanGptImage2EditNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "获取密钥请访问": (["👉 https://tikpan.com (官方授权Key获取点)"], ),
                "API_密钥": ("STRING", {"default": "sk-", "tooltip": "Tikpan 平台的 API 密钥，以 sk- 开头，从 https://tikpan.com 获取"}),
                "底图": ("IMAGE", {"tooltip": "需要被修改/重绘的原始图像"}),
                "修改指令": ("STRING", {"multiline": True, "default": "请把图中的人物换成一位穿着西装的男士，背景保持不变...", "tooltip": "告诉 AI 怎么改这张图，例如『把背景换成海边』『去掉左侧的杯子』"}),
                "模型": (["gpt-image-2-all"], {"default": "gpt-image-2-all", "tooltip": "本节点使用的修图模型，目前仅 gpt-image-2-all"}),
                "输出尺寸": (["沿用底图尺寸", "512", "1K", "2K", "4K"], {"default": "沿用底图尺寸", "tooltip": "结果图分辨率：沿用底图最稳；档位越高越清晰但更慢更贵"}),
                "画面比例": (["沿用底图比例", "1:1", "16:9", "9:16", "21:9", "4:3", "3:4"], {"default": "沿用底图比例", "tooltip": "结果图比例：沿用底图最不容易变形"}),
                "品质": (["标准｜standard", "高清｜hd"], {"default": "高清｜hd", "tooltip": "standard=快且省钱；hd=细节更好但更慢更贵"}),
            },
            "optional": {
                "中转站地址": (API_HOST_OPTIONS, {"default": API_HOST_OPTIONS[0], "tooltip": "Tikpan 中转站地址，一般保持默认即可"}),
                "遮罩_Mask": ("MASK", {"tooltip": "可选遮罩：白色区域=要重绘，黑色区域=保持不变"}),
                "产品参考图": ("IMAGE", {"tooltip": "可选参考图：让 AI 把这张图里的物体/风格融入结果"}),
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("🖼️_重绘结果图", "📄_渲染日志")
    FUNCTION = "edit"
    CATEGORY = "📷 Tikpan 云端模型/01 云端生图"
    DESCRIPTION = "📝 GPT-Image-2-all 修图节点：基于底图做指令式重绘，支持遮罩局部修改、参考图融合。适合换背景/换主体/产品融入。"

    def edit(self, 获取密钥请访问, API_密钥, 底图, 修改指令, 模型, 输出尺寸="沿用底图尺寸", 画面比例="沿用底图比例", 品质="高清｜hd", 遮罩_Mask=None, 产品参考图=None, **kwargs):
        pbar = comfy.utils.ProgressBar(100)
        api_host = normalize_api_host(kwargs.get("中转站地址", API_HOST_OPTIONS[0]))
        print(f"[Tikpan-Edit] 💉 视觉整形医生正在手术室就位...", flush=True)

        session = requests.Session()
        session.trust_env = False
        品质 = str(品质).split("｜")[-1].strip()

        # 🟢 2. 图像预处理
        # GPT-Image-2 Edit 要求底图和遮罩尺寸一致
        def tensor_to_pil(tensor):
            arr = 255. * tensor[0].cpu().numpy()
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

        # 工业对齐
        width, height = (width // 8) * 8, (height // 8) * 8
        base_img = base_img.resize((width, height), Image.LANCZOS)

        # 处理遮罩 (如果有)
        mask_img = None
        if 遮罩_Mask is not None:
            mask_arr = 遮罩_Mask.cpu().numpy()
            mask_img = Image.fromarray((mask_arr * 255).astype(np.uint8)).convert("L")
            mask_img = mask_img.resize((width, height), Image.LANCZOS)
            # OpenAI 规范：遮罩中透明/黑色代表保留，白色代表修改
            # 我们将 PIL 图像转为带有 Alpha 通道的 RGBA，这是 Edit 接口的标准
            base_img.putalpha(mask_img)

        # 🟢 3. 构造 Payload
        # Edit 接口通常使用 multipart/form-data，但中转站一般会将其封装为 JSON/Base64
        buf_base = BytesIO()
        base_img.save(buf_base, format="PNG") # Edit 必须传 PNG 才能带 Alpha 通道
        base_b64 = base64.b64encode(buf_base.getvalue()).decode("utf-8")

        content = [{"type": "text", "text": f"### EDIT TASK ###\n{修改指令}\n[Maintain consistent lighting and perspective]"}]
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{base_b64}"}
        })

        if 产品参考图 is not None:
            prod_img = tensor_to_pil(产品参考图)
            buf_prod = BytesIO()
            prod_img.save(buf_prod, format="JPEG", quality=80)
            prod_b64 = base64.b64encode(buf_prod.getvalue()).decode("utf-8")
            content.append({"type": "text", "text": "This is the product to be placed in the target area:"})
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{prod_b64}"}
            })

        headers = {"Authorization": f"Bearer {API_密钥}", "Content-Type": "application/json"}
        payload = {
            "model": 模型,
            "messages": [{"role": "user", "content": content}],
            "size": f"{width}x{height}",
            "quality": 品质,
        }

        idempotency_key = make_idempotency_key("chat/completions-edit", payload)
        headers["Idempotency-Key"] = idempotency_key
        request_snapshot_path = save_request_snapshot(
            "all_edit",
            idempotency_key,
            payload,
            endpoint="/v1/chat/completions",
            payload_hash=short_hash(payload),
            size=f"{width}x{height}",
        )
        recovery_path = save_recovery_record(
            "all_edit",
            idempotency_key,
            "pending",
            endpoint="/v1/chat/completions",
            payload_hash=short_hash(payload),
            size=f"{width}x{height}",
            request_snapshot=request_snapshot_path,
        )

        try:
            pbar.update(30)
            url = f"{api_host}/v1/chat/completions" # 使用统一聊天绘图路由
            response = self.post_chat_completion_with_retry(
                session,
                url,
                payload,
                headers,
                idempotency_key,
                recovery_path,
            )

            if response.status_code != 200:
                return (self.black_image(width, height), f"❌ 手术失败: {response.text}")

            res_json = response.json()
            save_recovery_record(
                "all_edit",
                idempotency_key,
                "response_received",
                endpoint="/v1/chat/completions",
                http_status=response.status_code,
                response=safe_json_for_log(res_json),
            )
            pbar.update(80)

            # 抓取数据
            img_raw = self.extract_image_pointer(res_json)
            if not img_raw:
                return (self.black_image(width, height), f"No image data found in response: {json.dumps(res_json, ensure_ascii=False)[:1200]}")

            # 暴力清洗与解码
            save_recovery_record(
                "all_edit",
                idempotency_key,
                "image_pointer_received",
                endpoint="/v1/chat/completions",
                image_url=img_raw if img_raw.startswith("http") else "",
            )

            if img_raw.startswith("http"):
                final_img = self.load_result_image(session, img_raw)
            else:
                final_img = self.load_result_image(session, img_raw)

            img_np = np.array(final_img).astype(np.float32) / 255.0
            pbar.update(100)
            if img_raw.startswith("http"):
                return (torch.from_numpy(img_np)[None, ...], f"success | upstream_image_url: {img_raw}")
            return (torch.from_numpy(img_np)[None, ...], "✅ 手术成功：局部重绘完成")

        except Exception as e:
            return (self.black_image(width, height), f"❌ 运行异常: {str(e)}")

    def post_chat_completion_with_retry(self, session, url, payload, headers, idempotency_key, recovery_path):
        payload_hash = short_hash(payload)
        attempts = [600, 900, 1200]
        last_error = None
        for attempt_index, read_timeout in enumerate(attempts, start=1):
            try:
                response = session.post(url, json=payload, headers=headers, timeout=(15, read_timeout))
                if attempt_index > 1:
                    save_recovery_record(
                        "all_edit",
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
                save_recovery_record(
                    "all_edit",
                    idempotency_key,
                    "connect_timeout",
                    endpoint="/v1/chat/completions",
                    payload_hash=payload_hash,
                    retry_attempt=attempt_index,
                    request_snapshot=recovery_path.replace(".json", ".request.json"),
                    error=str(e),
                )
                break
            except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
                last_error = e
                save_recovery_record(
                    "all_edit",
                    idempotency_key,
                    "post_disconnected_retrying" if attempt_index < len(attempts) else "post_disconnected",
                    endpoint="/v1/chat/completions",
                    payload_hash=payload_hash,
                    retry_attempt=attempt_index,
                    read_timeout_seconds=read_timeout,
                    request_snapshot=recovery_path.replace(".json", ".request.json"),
                    error=str(e),
                )
                if attempt_index < len(attempts):
                    continue
        raise RuntimeError(
            "上游可能已经接收并执行了修图请求，但本地多次等待响应时断开。"
            f"已使用相同 Idempotency-Key 自动重试 {len(attempts)} 次。"
            "请在中转站后台按 Idempotency-Key 或请求时间反查原始响应。"
            f"Idempotency-Key: {idempotency_key} | recovery: {recovery_path} | "
            f"request_snapshot: {recovery_path.replace('.json', '.request.json')} | last_error: {last_error}"
        )

    def black_image(self, w, h):
        return torch.zeros((1, h, w, 3))

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
                found = self.extract_markdown_image_url(item)
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
            if isinstance(content, str):
                found = from_item(content)
                if found:
                    return found
            if isinstance(content, list):
                for part in content:
                    found = from_item(part)
                    if found:
                        return found
            return ""

        if not isinstance(res_json, dict):
            return ""

        for choice in res_json.get("choices", []) or []:
            message = choice.get("message", {}) if isinstance(choice, dict) else {}
            found = from_item(message)
            if found:
                return found

        data = res_json.get("data")
        if isinstance(data, list):
            for item in data:
                found = from_item(item)
                if found:
                    return found
        else:
            found = from_item(data)
            if found:
                return found

        for key in ("result", "output", "images"):
            value = res_json.get(key)
            if isinstance(value, list):
                for item in value:
                    found = from_item(item)
                    if found:
                        return found
            else:
                found = from_item(value)
                if found:
                    return found

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
                return match.group(1).strip().rstrip('.,;')
        return ""

    def load_result_image(self, session, img_raw):
        img_raw = str(img_raw).strip()
        if img_raw.startswith(("http://", "https://")):
            img_res = get_with_retry(session, img_raw, timeout=(10, 120), attempts=4)
            return Image.open(BytesIO(img_res.content)).convert("RGB")

        b64_clean = re.sub(r"[^A-Za-z0-9+/=]", "", img_raw.split("base64,")[-1])
        missing_padding = len(b64_clean) % 4
        if missing_padding:
            b64_clean += "=" * (4 - missing_padding)
        img_bytes = base64.b64decode(b64_clean)
        return Image.open(BytesIO(img_bytes)).convert("RGB")
