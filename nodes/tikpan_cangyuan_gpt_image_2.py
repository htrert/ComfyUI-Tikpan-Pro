import json
import time

import numpy as np
import torch

from .tikpan_categories import CATEGORY_CANGYUAN
from .tikpan_gpt_image_2_official import TikpanGptImage2OfficialNode
from .tikpan_gpt_image_recovery import make_idempotency_key, safe_json_for_log, save_recovery_record, short_hash
from .tikpan_node_options import normalize_seed, option_value, pick


CANGYUAN_API_HOST = "https://new.ip233.com"
CANGYUAN_IMAGE_ENDPOINT = "/v1/images/generations"
CANGYUAN_IMAGE_MODEL = "gpt-image-2"
CANGYUAN_IMAGE_ASPECT_OPTIONS = [
    "1:1 方形｜1:1",
    "3:2 横屏｜3:2",
    "2:3 竖屏｜2:3",
    "自动｜auto",
]
CANGYUAN_IMAGE_SIZE_HINTS = {
    "1:1": (1024, 1024),
    "3:2": (1536, 1024),
    "2:3": (1024, 1536),
    "auto": (1024, 1024),
}


class TikpanCangyuanGptImage2Node(TikpanGptImage2OfficialNode):
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "new.ip233.com说明": (["gpt-image-2 | JSON 异步生图 | 支持 1:1、3:2、2:3、auto，单次 1-10 张"],),
                "获取密钥请访问": (["https://new.ip233.com"],),
                "API_密钥": ("STRING", {"default": "sk-", "tooltip": "new.ip233.com API Key，以 sk- 开头。"}),
                "生成指令": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "一幅写实的极地极光景观，巨大的冰川倒映在平静的海面上，电影感，细节丰富。",
                        "tooltip": "描述你想生成的画面，支持中英文。",
                    },
                ),
                "画面比例": (
                    CANGYUAN_IMAGE_ASPECT_OPTIONS,
                    {"default": CANGYUAN_IMAGE_ASPECT_OPTIONS[0], "tooltip": "模型广场仅开放 1:1、3:2、2:3、auto。"},
                ),
                "生成张数": ("INT", {"default": 1, "min": 1, "max": 10, "step": 1, "tooltip": "new.ip233.com 模型广场规格：1-10 张。"}),
            },
            "optional": {
                "随机种子": ("INT", {"default": 888888, "min": 0, "max": 2147483647, "step": 1}),
                "最长等待秒数": ("INT", {"default": 360, "min": 30, "max": 7200, "step": 30, "tooltip": "异步任务最多等待多久。"}),
                "查询间隔秒数": ("INT", {"default": 5, "min": 5, "max": 60, "step": 1}),
                "校验HTTPS证书": ("BOOLEAN", {"default": False, "tooltip": "是否校验 new.ip233.com 站点 HTTPS 证书。"}),
                "跳过错误": ("BOOLEAN", {"default": False, "tooltip": "开启后接口异常时返回黑图，避免工作流中断。"}),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("🖼️_生成结果图", "📄_渲染日志")
    FUNCTION = "generate"
    CATEGORY = CATEGORY_CANGYUAN
    DESCRIPTION = "new.ip233.com gpt-image-2 生图：POST /v1/images/generations，size 按比例传入。"

    def generate(self, **kwargs):
        start_time = time.time()
        api_key = str(pick(kwargs, "API_密钥", "api_key", default="") or "").strip()
        prompt = str(pick(kwargs, "生成指令", "prompt", default="") or "").strip()
        model = CANGYUAN_IMAGE_MODEL
        aspect_ratio = option_value(pick(kwargs, "画面比例", "aspect_ratio", default="1:1"), "1:1")
        count = int(pick(kwargs, "生成张数", "n", default=1) or 1)
        seed = normalize_seed(pick(kwargs, "随机种子", "seed", default=888888), default=888888)
        max_wait = int(pick(kwargs, "最长等待秒数", "max_wait_seconds", default=360) or 360)
        poll_interval = int(pick(kwargs, "查询间隔秒数", "poll_interval", default=5) or 5)
        verify_tls = bool(pick(kwargs, "校验HTTPS证书", "verify_tls", default=False))
        skip_error = bool(pick(kwargs, "跳过错误", "skip_error", default=False))
        width, height = CANGYUAN_IMAGE_SIZE_HINTS.get(aspect_ratio, (1024, 1024))

        try:
            if not api_key or api_key == "sk-" or len(api_key) < 10:
                return (self.black_image(width, height), "❌ 请填写有效的 new.ip233.com API 密钥")
            if not prompt:
                return (self.black_image(width, height), "❌ 生成指令不能为空")
            if aspect_ratio not in CANGYUAN_IMAGE_SIZE_HINTS:
                aspect_ratio = "1:1"
            count = max(1, min(10, count))

            payload = {
                "model": model,
                "prompt": prompt,
                "size": aspect_ratio,
                "n": count,
                "async": True,
                "stream": False,
                "seed": int(seed) & 0x7fffffff,
            }
            idempotency_key = make_idempotency_key("new-ip233-images/generations", payload)
            save_recovery_record(
                "new_ip233_image_generation",
                idempotency_key,
                "pending",
                endpoint=CANGYUAN_IMAGE_ENDPOINT,
                payload_hash=short_hash(payload),
                size=aspect_ratio,
            )

            session = self.create_session()
            response = session.post(
                f"{CANGYUAN_API_HOST}{CANGYUAN_IMAGE_ENDPOINT}",
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "Tikpan-ComfyUI-new-ip233-GPT-Image-2/1.0",
                    "Idempotency-Key": idempotency_key,
                },
                timeout=(15, 300),
                verify=verify_tls,
            )

            if response.status_code != 200:
                msg = f"❌ new.ip233.com 图片任务请求失败 | HTTP {response.status_code} | {self.safe_response_text(response, 1600)}"
                if not skip_error:
                    raise RuntimeError(msg)
                return (self.black_image(width, height), msg)

            try:
                res_json = response.json()
            except Exception:
                msg = f"❌ new.ip233.com 图片接口返回非 JSON：{self.safe_response_text(response, 1600)}"
                if not skip_error:
                    raise RuntimeError(msg)
                return (self.black_image(width, height), msg)

            save_recovery_record(
                "new_ip233_image_generation",
                idempotency_key,
                "response_received",
                endpoint=CANGYUAN_IMAGE_ENDPOINT,
                http_status=response.status_code,
                response=safe_json_for_log(res_json),
            )
            if isinstance(res_json, dict) and res_json.get("error"):
                err_obj = res_json.get("error")
                err_text = err_obj.get("message") if isinstance(err_obj, dict) else str(err_obj)
                msg = f"❌ new.ip233.com 图片接口拒绝：{err_text}"
                if not skip_error:
                    raise RuntimeError(msg)
                return (self.black_image(width, height), msg)

            image_refs = self.extract_image_results(res_json)
            task_id = self.extract_task_id(res_json)
            if not image_refs and task_id:
                res_json = self.poll_image_task(session, api_key, task_id, max_wait, poll_interval, verify_tls)
                image_refs = self.extract_image_results(res_json)
            if not image_refs:
                msg = f"⚠️ 未找到有效图像数据。接口返回：{json.dumps(res_json, ensure_ascii=False)[:1600]}"
                if not skip_error:
                    raise RuntimeError(msg)
                return (self.black_image(width, height), msg)

            tensors = []
            urls = []
            for img_raw, raw_type in image_refs[:count]:
                final_pil = self.load_result_image(session, img_raw, raw_type).convert("RGB")
                final_np = np.array(final_pil).astype(np.float32) / 255.0
                tensors.append(torch.from_numpy(final_np)[None, ...])
                if raw_type == "url":
                    urls.append(img_raw)

            final_tensor = torch.cat(tensors, dim=0)
            elapsed = round(time.time() - start_time, 2)
            log_text = (
                f"✅ new.ip233.com gpt-image-2 渲染成功 | endpoint={CANGYUAN_IMAGE_ENDPOINT} | "
                f"比例/size={aspect_ratio} | 张数={len(tensors)} | seed={int(seed) & 0x7fffffff} | 耗时={elapsed}s"
            )
            if urls:
                log_text += f" | 上游图片链接: {urls[0]}"

            save_recovery_record(
                "new_ip233_image_generation",
                idempotency_key,
                "success",
                endpoint=CANGYUAN_IMAGE_ENDPOINT,
                raw_count=len(tensors),
                first_image_url=urls[0] if urls else "",
            )
            return (final_tensor, log_text)
        except Exception as exc:
            msg = f"❌ new.ip233.com 图片节点异常: {exc}"
            if not skip_error:
                raise
            return (self.black_image(width, height), msg)

    def extract_task_id(self, data):
        if isinstance(data, dict):
            for key in ("id", "task_id", "taskId", "request_id", "operation_id", "operationId"):
                value = data.get(key)
                if value:
                    return str(value).strip()
            for key in ("data", "result", "output", "task", "operation"):
                found = self.extract_task_id(data.get(key))
                if found:
                    return found
        elif isinstance(data, list):
            for item in data:
                found = self.extract_task_id(item)
                if found:
                    return found
        elif isinstance(data, str) and data.strip():
            return data.strip()
        return ""

    def poll_image_task(self, session, api_key, task_id, max_wait, poll_interval, verify_tls):
        task = str(task_id or "").strip()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": "Tikpan-ComfyUI-new-ip233-GPT-Image-2/1.0",
        }
        start_time = time.time()
        last_json = {}
        while time.time() - start_time < max_wait:
            time.sleep(poll_interval)
            for url in (
                f"{CANGYUAN_API_HOST}{CANGYUAN_IMAGE_ENDPOINT}/{task}",
                f"{CANGYUAN_API_HOST}{CANGYUAN_IMAGE_ENDPOINT}/query?id={task}",
            ):
                try:
                    response = session.get(url, headers=headers, timeout=(15, 60), verify=verify_tls)
                    if response.status_code in {404, 405}:
                        continue
                    if response.status_code >= 400:
                        continue
                    data = response.json()
                    last_json = data
                    if self.extract_image_results(data):
                        return data
                    status = str(data.get("status") or data.get("state") or "").lower() if isinstance(data, dict) else ""
                    if status in {"failed", "error", "cancelled", "canceled"}:
                        raise RuntimeError(f"图片任务失败：{json.dumps(data, ensure_ascii=False)[:1600]}")
                    break
                except RuntimeError:
                    raise
                except Exception:
                    continue
        raise RuntimeError(f"图片任务轮询超时：task_id={task} | last={json.dumps(last_json, ensure_ascii=False)[:1200]}")

    def extract_image_results(self, res_json):
        results = []
        seen = set()

        def add(value, raw_type):
            if not isinstance(value, str):
                return
            value = value.strip()
            if not value or value in seen:
                return
            seen.add(value)
            results.append((value, raw_type))

        def scan(obj):
            if isinstance(obj, dict):
                url = obj.get("url") or obj.get("image_url") or obj.get("imageUrl") or obj.get("output_url")
                if url:
                    add(url, "url")
                b64 = obj.get("b64_json") or obj.get("image_base64") or obj.get("base64")
                image_value = obj.get("image")
                if not b64 and isinstance(image_value, str) and not image_value.startswith(("http://", "https://")):
                    b64 = image_value
                if b64:
                    add(b64, "b64")
                if isinstance(image_value, str) and image_value.startswith(("http://", "https://")):
                    add(image_value, "url")
                for key in ("data", "result", "output", "images"):
                    scan(obj.get(key))
            elif isinstance(obj, list):
                for item in obj:
                    scan(item)

        scan(res_json)
        if not results:
            first, raw_type = self.extract_image_result(res_json)
            if first:
                results.append((first, raw_type))
        return results


NODE_CLASS_MAPPINGS = {"TikpanCangyuanGptImage2Node": TikpanCangyuanGptImage2Node}
NODE_DISPLAY_NAME_MAPPINGS = {"TikpanCangyuanGptImage2Node": "new.ip233.com｜GPT-Image-2 生图"}
