from .tikpan_categories import CATEGORY_CANGYUAN

import base64
import json
import os
import time
import traceback
from io import BytesIO

import comfy.model_management
import comfy.utils
import folder_paths
import numpy as np
import requests
import urllib3
from PIL import Image
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .tikpan_happyhorse_common import extract_task_status, extract_video_url, is_failure_status, is_success_status, video_from_path
from .tikpan_node_options import option_int, option_value, pick

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CANGYUAN_API_HOST = "https://new.ip233.com"
CANGYUAN_VIDEO_ENDPOINT = "/v1/video/generations"
CANGYUAN_GROK_VIDEO_15_MODEL = "grok-video-1.5"
CANGYUAN_GROK_15_DURATION_OPTIONS = [
    "4秒｜4s",
    "6秒｜6s",
    "8秒｜8s",
    "10秒｜10s",
    "12秒｜12s",
    "15秒｜15s",
]
CANGYUAN_GROK_15_RESOLUTION_OPTIONS = ["480p 标清｜480p", "720p 高清｜720p"]
CANGYUAN_GROK_15_ASPECT_OPTIONS = ["16:9 横屏｜16:9", "9:16 竖屏｜9:16"]


class TikpanCangyuanGrokVideo15Node:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "new.ip233.com说明": (["grok-video-1.5 | 必须且只能 1 张参考图 | 4-15 秒，480p/720p，16:9/9:16"],),
                "获取密钥请访问": (["https://new.ip233.com"],),
                "API_密钥": ("STRING", {"default": "sk-", "tooltip": "new.ip233.com API Key，以 sk- 开头。"}),
                "参考图": ("IMAGE", {"tooltip": "必填且只能 1 张参考图。"}),
                "生成指令": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "Turn this image into a cinematic video with smooth natural motion, realistic lighting, and coherent camera movement.",
                        "tooltip": "视频提示词。",
                    },
                ),
                "视频时长": (CANGYUAN_GROK_15_DURATION_OPTIONS, {"default": CANGYUAN_GROK_15_DURATION_OPTIONS[1], "tooltip": "new.ip233.com 规格：4/6/8/10/12/15 秒。"}),
                "分辨率": (CANGYUAN_GROK_15_RESOLUTION_OPTIONS, {"default": CANGYUAN_GROK_15_RESOLUTION_OPTIONS[1], "tooltip": "new.ip233.com 规格：480p / 720p。"}),
                "画面比例": (CANGYUAN_GROK_15_ASPECT_OPTIONS, {"default": CANGYUAN_GROK_15_ASPECT_OPTIONS[0], "tooltip": "new.ip233.com grok-video-1.5 仅支持 16:9 或 9:16。"}),
            },
            "optional": {
                "最长等待秒数": ("INT", {"default": 300, "min": 60, "max": 7200, "step": 30, "tooltip": "默认按 new.ip233.com 模型广场 5s × 60 次轮询。"}),
                "查询间隔秒数": ("INT", {"default": 5, "min": 5, "max": 60, "step": 1}),
                "校验HTTPS证书": ("BOOLEAN", {"default": False, "tooltip": "是否校验 new.ip233.com 站点 HTTPS 证书。"}),
                "跳过错误": ("BOOLEAN", {"default": False, "tooltip": "出错时返回空值。"}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "VIDEO")
    RETURN_NAMES = ("本地保存路径", "任务ID", "视频云端直链", "完整日志", "视频输出")
    OUTPUT_NODE = True
    FUNCTION = "generate_video"
    CATEGORY = CATEGORY_CANGYUAN
    DESCRIPTION = "new.ip233.com grok-video-1.5：POST /v1/video/generations，单图生视频。"

    def generate_video(self, **kwargs):
        pbar = comfy.utils.ProgressBar(100)
        task_id = ""
        video_url = ""
        try:
            api_key = str(pick(kwargs, "API_密钥", "api_key", default="") or "").strip()
            prompt = str(pick(kwargs, "生成指令", "prompt", default="") or "").strip()
            image_tensor = pick(kwargs, "参考图", "image", "reference_image", default=None)
            duration = option_int(pick(kwargs, "视频时长", "duration", default=CANGYUAN_GROK_15_DURATION_OPTIONS[1]), default=6, minimum=4, maximum=15)
            resolution = option_value(pick(kwargs, "分辨率", "resolution", default=CANGYUAN_GROK_15_RESOLUTION_OPTIONS[1]), "720p")
            aspect_ratio = option_value(pick(kwargs, "画面比例", "aspect_ratio", default=CANGYUAN_GROK_15_ASPECT_OPTIONS[0]), "16:9")
            max_wait = int(pick(kwargs, "最长等待秒数", "max_wait_seconds", default=300) or 300)
            poll_interval = int(pick(kwargs, "查询间隔秒数", "poll_interval", default=5) or 5)
            verify_tls = bool(pick(kwargs, "校验HTTPS证书", "verify_tls", default=False))
            skip_error = bool(pick(kwargs, "跳过错误", "skip_error", default=False))

            if not api_key or api_key == "sk-" or len(api_key) < 10:
                return self.error_return("❌ 请填写有效的 new.ip233.com API 密钥", skip_error)
            if not prompt:
                return self.error_return("❌ 生成提示词不能为空", skip_error)
            if image_tensor is None:
                return self.error_return("❌ new.ip233.com grok-video-1.5 必须连接 1 张参考图", skip_error)
            if aspect_ratio not in {"16:9", "9:16"}:
                return self.error_return(f"❌ new.ip233.com grok-video-1.5 仅支持 16:9 或 9:16，当前为 {aspect_ratio}", skip_error)
            if resolution not in {"480p", "720p"}:
                resolution = "720p"

            image_data_url = self.tensor_to_data_url(image_tensor)
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "Tikpan-ComfyUI-new-ip233-GrokVideo15/1.0",
            }
            session = requests.Session()
            session.trust_env = False

            pbar.update_absolute(10, 100)
            payload = self.build_payload(CANGYUAN_GROK_VIDEO_15_MODEL, prompt, image_data_url, duration, resolution, aspect_ratio)
            response = session.post(
                f"{CANGYUAN_API_HOST}{CANGYUAN_VIDEO_ENDPOINT}",
                json=payload,
                headers=headers,
                timeout=(20, 180),
                verify=verify_tls,
            )
            if response.status_code >= 400:
                return self.error_return(f"❌ new.ip233.com 视频任务创建失败: HTTP {response.status_code}\n{self.safe_text(response.text, 1600)}", skip_error)
            try:
                create_json = response.json()
            except Exception:
                return self.error_return(f"❌ new.ip233.com 视频任务创建失败：响应不是 JSON\n{self.safe_text(response.text, 1600)}", skip_error)

            task_id = self.extract_task_id(create_json)
            video_url = self.extract_video_url_from_response(create_json)
            if not video_url and not task_id:
                return self.error_return(f"❌ 未获取到任务ID或视频链接\n{json.dumps(create_json, ensure_ascii=False)[:2000]}", skip_error)

            pbar.update_absolute(25, 100)
            final_json = create_json
            if not video_url:
                ok, result, final_json = self.poll_task(session, headers, task_id, max_wait, poll_interval, verify_tls, pbar)
                if not ok:
                    return self.error_return(result, skip_error, task_id=task_id)
                video_url = result

            pbar.update_absolute(88, 100)
            save_path = self.download_video(self.create_download_session(), video_url, task_id or "sync", verify_tls)
            pbar.update_absolute(100, 100)
            log_text = (
                f"✅ new.ip233.com grok-video-1.5 视频生成成功 | endpoint={CANGYUAN_VIDEO_ENDPOINT} | "
                f"duration={duration}s | resolution={resolution} | aspect_ratio={aspect_ratio}\n"
                f"task_id={task_id or 'sync'}\nvideo_url={video_url}\npath={save_path}\n\n"
                f"{json.dumps(final_json, ensure_ascii=False, indent=2)[:3000]}"
            )
            return (save_path, task_id or "sync", video_url, log_text, video_from_path(save_path))
        except Exception as exc:
            tb = traceback.format_exc()
            msg = f"❌ new.ip233.com grok-video-1.5 节点异常: {exc}\n{tb[:2000]}"
            skip_error = bool(pick(kwargs, "跳过错误", "skip_error", default=False))
            if not skip_error:
                raise RuntimeError(msg) from exc
            return ("", task_id, video_url, msg, None)

    def build_payload(self, model_id, prompt, image_data_url, duration, resolution, aspect_ratio):
        return {
            "model": model_id,
            "prompt": prompt,
            "image_urls": [image_data_url],
            "seconds": int(duration),
            "resolution": str(resolution),
            "aspect_ratio": str(aspect_ratio),
        }

    def tensor_to_data_url(self, img_tensor, quality=92):
        if len(img_tensor.shape) == 4:
            img_tensor = img_tensor[0]
        arr = 255.0 * img_tensor.detach().cpu().numpy()
        image = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGB")
        buf = BytesIO()
        image.save(buf, format="JPEG", quality=int(quality), optimize=True)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")

    def poll_task(self, session, headers, task_id, max_wait, poll_interval, verify_tls, pbar):
        start = time.time()
        last_json = {}
        poll_count = 0
        query_urls = [
            f"{CANGYUAN_API_HOST}{CANGYUAN_VIDEO_ENDPOINT}/{task_id}",
            f"{CANGYUAN_API_HOST}{CANGYUAN_VIDEO_ENDPOINT}/{task_id}?model={CANGYUAN_GROK_VIDEO_15_MODEL}",
        ]
        while time.time() - start < max_wait:
            comfy.model_management.throw_exception_if_processing_interrupted()
            time.sleep(poll_interval)
            poll_count += 1
            for query_url in query_urls:
                try:
                    resp = session.get(query_url, headers=headers, timeout=(15, 60), verify=verify_tls)
                    if resp.status_code >= 400:
                        continue
                    res_json = resp.json()
                    last_json = res_json
                    status = extract_task_status(res_json)
                    video_url = self.extract_video_url_from_response(res_json)
                    elapsed = int(time.time() - start)
                    if pbar:
                        pbar.update_absolute(min(85, 25 + int(elapsed * 60 / max(max_wait, 1))), 100)
                    print(f"[Tikpan-new-ip233-GrokVideo15] poll={poll_count} status={status or 'unknown'} task_id={task_id}", flush=True)
                    if is_success_status(status):
                        if video_url:
                            return True, video_url, res_json
                        return False, "❌ 任务成功但响应里没有视频链接", res_json
                    if is_failure_status(status):
                        return False, f"❌ 任务失败: {json.dumps(res_json, ensure_ascii=False)[:1200]}", res_json
                    if video_url and not status:
                        return True, video_url, res_json
                except Exception:
                    continue
        return False, f"❌ 轮询超时：任务仍在处理中 | task_id={task_id}", last_json

    def download_video(self, session, video_url, task_id, verify_tls):
        resp = session.get(video_url, timeout=(20, 900), verify=verify_tls)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")
        if not resp.content or len(resp.content) < 1024:
            raise RuntimeError(f"视频下载内容为空或过短: {len(resp.content) if resp.content else 0} bytes")
        if "text/html" in content_type.lower() or resp.content[:20].lstrip().lower().startswith(b"<!doctype"):
            raise RuntimeError(f"视频链接返回 HTML，不是视频文件: {self.safe_text(resp.text)}")
        safe_id = str(task_id or int(time.time())).replace("/", "_").replace(":", "_")
        save_path = os.path.join(folder_paths.get_output_directory(), f"new_ip233_grok_video_15_{safe_id}.mp4")
        with open(save_path, "wb") as f:
            f.write(resp.content)
        return save_path

    def create_download_session(self):
        session = requests.Session()
        session.trust_env = True
        session.proxies = {}
        retry = Retry(total=3, connect=3, read=2, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=frozenset(["GET"]), raise_on_status=False)
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def extract_task_id(self, res_json):
        if not isinstance(res_json, dict):
            return ""
        for obj in (res_json, res_json.get("data"), res_json.get("result"), res_json.get("output")):
            if isinstance(obj, dict):
                value = obj.get("request_id") or obj.get("task_id") or obj.get("taskId") or obj.get("id") or obj.get("task")
                if value:
                    return str(value).strip()
            elif isinstance(obj, str) and obj.strip():
                return obj.strip()
        return ""

    def extract_video_url_from_response(self, res_json):
        if not isinstance(res_json, dict):
            return ""
        found = extract_video_url(res_json)
        if found:
            return found
        for obj in (res_json.get("data"), res_json.get("result"), res_json.get("output")):
            found = extract_video_url(obj)
            if found:
                return found
        for choice in res_json.get("choices", []) or []:
            message = choice.get("message", {}) if isinstance(choice, dict) else {}
            found = extract_video_url(message)
            if found:
                return found
            content = message.get("content")
            if isinstance(content, str):
                found = self.first_http_video_url(content)
                if found:
                    return found
            elif isinstance(content, list):
                found = extract_video_url({"content": content})
                if found:
                    return found
        return ""

    def first_http_video_url(self, text):
        for token in str(text or "").replace(")", " ").replace("]", " ").split():
            cleaned = token.strip("<>,;\"'")
            if cleaned.startswith(("http://", "https://")):
                return cleaned
        return ""

    def safe_text(self, value, max_len=1000):
        try:
            return str(value or "")[:max_len].strip()
        except Exception:
            return ""

    def error_return(self, message, skip_error=False, task_id=""):
        if not skip_error:
            raise RuntimeError(message)
        return ("", task_id, "", message, None)


NODE_CLASS_MAPPINGS = {"TikpanCangyuanGrokVideo15Node": TikpanCangyuanGrokVideo15Node}
NODE_DISPLAY_NAME_MAPPINGS = {"TikpanCangyuanGrokVideo15Node": "new.ip233.com｜Grok Video 1.5 单图生视频"}
