from .tikpan_categories import CATEGORY_VIDEO
import json
import os
import time
import traceback
from io import BytesIO

import numpy as np
import requests
import torch
import urllib3
from PIL import Image
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import comfy.model_management
import comfy.utils
import folder_paths

from .tikpan_happyhorse_common import (
    extract_error_message,
    extract_task_output,
    extract_task_status,
    extract_video_url,
    is_failure_status,
    is_success_status,
    video_from_path,
)
from .tikpan_node_options import API_HOST_OPTIONS, normalize_api_host, pick


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://tikpan.com"
KLING_MOTION_MODEL_OPTIONS = [
    "kling-v2-6｜std｜720P",
    "kling-v2-6｜pro｜1080P",
    "kling-v3｜std｜720P",
    "kling-v3｜pro｜1080P",
]
KLING_MOTION_DURATION_OPTIONS = ["自动按参考视频｜auto", "5秒｜5", "10秒｜10", "15秒｜15", "20秒｜20", "30秒｜30"]
KLING_MOTION_ASPECT_OPTIONS = ["自动｜auto", "16:9 横屏｜16:9", "9:16 竖屏｜9:16", "1:1 方形｜1:1"]


class TikpanKlingMotionControlNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "💰_福利_💰": (["🔥 0.6元RMB兑1美元余额 | 全网底价 👉 https://tikpan.com"],),
                "获取密钥请访问": (["👉 https://tikpan.com (官方授权Key获取点)"],),
                "API_密钥": ("STRING", {"default": "sk-", "tooltip": "Tikpan 平台的 API 密钥，以 sk- 开头，从 https://tikpan.com 获取"}),
                "角色图像": ("IMAGE", {"tooltip": "目标角色的静态图像，模型会让这个角色做参考视频里的动作"}),
                "动作参考视频URL": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "公开可访问的视频 URL。也可以在下面填本地视频路径，二选一。",
                    },
                ),
                "动作描述": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "保持角色身份一致，将参考视频中的动作精准迁移到角色图像，生成自然流畅的全身动作视频。",
                        "tooltip": "对动作迁移效果的补充描述，例如『保持人物表情自然』",
                    },
                ),
                "模型版本与模式": (KLING_MOTION_MODEL_OPTIONS, {"default": KLING_MOTION_MODEL_OPTIONS[0], "tooltip": "选择 Kling 版本和质量模式：std 标准 720P；pro 高质 1080P"}),
                "视频时长": (KLING_MOTION_DURATION_OPTIONS, {"default": KLING_MOTION_DURATION_OPTIONS[0], "tooltip": "生成视频秒数；auto=跟随参考视频时长"}),
                "画面比例": (KLING_MOTION_ASPECT_OPTIONS, {"default": KLING_MOTION_ASPECT_OPTIONS[0], "tooltip": "视频比例：auto 跟随参考；常用 16:9 横屏、9:16 竖屏"}),
            },
            "optional": {
                "本地动作视频路径": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "填写本地 mp4/mov/webm 路径后，节点会先上传到 Tikpan，再提交动作控制任务。",
                    },
                ),
                "中转站地址": (API_HOST_OPTIONS, {"default": API_HOST_OPTIONS[0], "tooltip": "Tikpan 中转站地址，一般保持默认即可"}),
                "最长等待秒数": ("INT", {"default": 900, "min": 60, "max": 3600, "step": 30, "tooltip": "等待视频生成完成的最长秒数；长视频/pro 模式建议加大"}),
                "查询间隔秒数": ("INT", {"default": 8, "min": 5, "max": 60, "step": 1, "tooltip": "轮询任务状态的间隔秒数"}),
                "校验HTTPS证书": ("BOOLEAN", {"default": False, "tooltip": "默认关闭以兼容部分网络；遇到 SSL 问题可保持关闭"}),
                "跳过错误": ("BOOLEAN", {"default": False, "tooltip": "开启后异常时返回空，不打断后续工作流"}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "VIDEO")
    RETURN_NAMES = ("📁_本地保存路径", "🆔_任务ID", "🔗_视频云端直链", "📄_完整日志", "🎬_视频输出")
    OUTPUT_NODE = True
    FUNCTION = "generate_motion_video"
    CATEGORY = CATEGORY_VIDEO
    DESCRIPTION = "📝 Kling Motion Control 动作控制：把参考视频里的动作精准迁移到角色图像上，保持角色身份一致。适合 IP 动作复刻、AI 数字人、TikTok 二创。"

    def generate_motion_video(self, **kwargs):
        pbar = comfy.utils.ProgressBar(100)
        task_id = ""
        video_url = ""
        save_path = ""

        try:
            api_key = str(pick(kwargs, "API_密钥", "api_key", default="") or "").strip()
            api_host = normalize_api_host(pick(kwargs, "中转站地址", "api_host", default=API_HOST_OPTIONS[0]))
            verify_tls = bool(pick(kwargs, "校验HTTPS证书", "verify_tls", default=False))
            skip_error = bool(pick(kwargs, "跳过错误", "skip_error", default=False))
            role_image = pick(kwargs, "角色图像", "character_image", default=None)
            prompt = str(pick(kwargs, "动作描述", "prompt", default="") or "").strip()
            motion_video_url = str(pick(kwargs, "动作参考视频URL", "motion_video_url", default="") or "").strip()
            local_video_path = str(pick(kwargs, "本地动作视频路径", "local_motion_video_path", default="") or "").strip()
            model_option = str(pick(kwargs, "模型版本与模式", "model_option", default=KLING_MOTION_MODEL_OPTIONS[0]) or "")
            duration_option = str(pick(kwargs, "视频时长", "duration", default=KLING_MOTION_DURATION_OPTIONS[0]) or "")
            aspect_option = str(pick(kwargs, "画面比例", "aspect_ratio", default=KLING_MOTION_ASPECT_OPTIONS[0]) or "")
            max_wait_seconds = int(pick(kwargs, "最长等待秒数", "max_wait_seconds", default=900) or 900)
            poll_interval = int(pick(kwargs, "查询间隔秒数", "poll_interval", default=8) or 8)

            if not api_key or api_key == "sk-" or len(api_key) < 10:
                return self.error_return("❌ 请填写有效的 API 密钥", skip_error)
            if role_image is None:
                return self.error_return("❌ 请连接角色图像。Motion Control 需要一张静态角色图。", skip_error)
            if not motion_video_url and not local_video_path:
                return self.error_return("❌ 请填写动作参考视频URL，或填写本地动作视频路径。", skip_error)
            if motion_video_url and not motion_video_url.startswith(("http://", "https://")):
                return self.error_return("❌ 动作参考视频URL 必须是 http/https 公开视频链接。", skip_error)

            model_name, mode, resolution = self.parse_model_option(model_option)
            duration = self.option_value(duration_option, "auto")
            aspect_ratio = self.option_value(aspect_option, "auto")
            duration_value = "" if duration == "auto" else int(float(duration))

            session = self.create_session()
            headers = {
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "Tikpan-ComfyUI-KlingMotionControl/1.0",
            }

            pbar.update_absolute(5, 100)
            image_url = self.upload_image(session, api_host, api_key, role_image, verify_tls, pbar)
            if local_video_path and not motion_video_url:
                motion_video_url = self.upload_video(session, api_host, api_key, local_video_path, verify_tls, pbar)
            else:
                pbar.update_absolute(18, 100)

            payload = {
                "model": "kling-motion-control",
                "model_name": model_name,
                "mode": mode,
                "resolution": resolution,
                "prompt": prompt,
                "image_url": image_url,
                "video_url": motion_video_url,
            }
            if duration_value:
                payload["duration"] = duration_value
            if aspect_ratio != "auto":
                payload["aspect_ratio"] = aspect_ratio

            safe_payload = dict(payload)
            print(f"[Tikpan-KlingMotion] Payload: {json.dumps(safe_payload, ensure_ascii=False)[:1200]}", flush=True)
            pbar.update_absolute(25, 100)

            response = session.post(
                f"{api_host}/kling/v1/videos/motion-control",
                json=payload,
                headers={**headers, "Content-Type": "application/json", "Accept": "application/json"},
                timeout=(20, 120),
                verify=verify_tls,
            )
            if response.status_code >= 400:
                return self.error_return(
                    f"❌ 任务创建失败: HTTP {response.status_code}\n{self.safe_text(response.text)}",
                    skip_error,
                )

            try:
                create_json = response.json()
            except Exception:
                return self.error_return(f"❌ 任务创建失败：返回不是合法 JSON\n{self.safe_text(response.text)}", skip_error)

            task_id = self.extract_task_id(create_json)
            direct_url = extract_video_url(create_json)
            if direct_url:
                video_url = direct_url
            elif not task_id:
                return self.error_return(
                    f"❌ 任务创建失败：未获取到任务ID\n{json.dumps(create_json, ensure_ascii=False)[:1500]}",
                    skip_error,
                )

            pbar.update_absolute(35, 100)
            final_json = create_json
            if not video_url:
                ok, result, final_json = self.poll_task(
                    session,
                    api_host,
                    headers,
                    task_id,
                    max_wait_seconds,
                    poll_interval,
                    verify_tls,
                    pbar,
                )
                if not ok:
                    return self.error_return(result, skip_error, task_id=task_id)
                video_url = result

            pbar.update_absolute(88, 100)
            save_path = self.download_video(session, video_url, task_id or "sync", verify_tls)
            pbar.update_absolute(100, 100)

            log_text = (
                f"✅ Kling Motion Control 生成成功\n"
                f"模型版本: {model_name} | 模式: {mode} | 清晰度: {resolution}\n"
                f"时长: {duration} | 比例: {aspect_ratio}\n"
                f"任务ID: {task_id or 'sync'}\n"
                f"角色图: {image_url}\n"
                f"动作视频: {motion_video_url}\n"
                f"云端视频: {video_url}\n"
                f"本地路径: {save_path}\n\n"
                f"完整响应:\n{json.dumps(final_json, ensure_ascii=False, indent=2)[:2500]}"
            )
            return (save_path, task_id or "sync", video_url, log_text, video_from_path(save_path))

        except Exception as exc:
            tb = traceback.format_exc()
            msg = f"❌ Kling Motion Control 异常: {exc}\n{tb[:2000]}"
            print(f"[Tikpan-KlingMotion] {msg}", flush=True)
            skip_error = bool(pick(kwargs, "跳过错误", "skip_error", default=False))
            if not skip_error:
                raise RuntimeError(msg) from exc
            return ("", task_id, video_url, msg, None)

    def create_session(self):
        session = requests.Session()
        session.trust_env = False
        retry = Retry(
            total=3,
            connect=3,
            read=1,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=frozenset(["GET", "POST"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def parse_model_option(self, option):
        parts = [part.strip() for part in str(option or "").split("｜") if part.strip()]
        model_name = parts[0] if len(parts) >= 1 else "kling-v2-6"
        if model_name == "kling-v3-0":
            print("[Tikpan-KlingMotion] kling-v3-0 已按上游文档自动改用 kling-v3。", flush=True)
            model_name = "kling-v3"
        mode = parts[1] if len(parts) >= 2 else "std"
        resolution = parts[2] if len(parts) >= 3 else ("1080P" if mode == "pro" else "720P")
        return model_name, mode, resolution

    def option_value(self, value, default=""):
        parts = [part.strip() for part in str(value or "").split("｜") if part.strip()]
        return parts[-1] if parts else default

    def tensor_to_jpeg_bytes(self, img_tensor, quality=92):
        if len(img_tensor.shape) == 4:
            img_tensor = img_tensor[0]
        arr = 255.0 * img_tensor.detach().cpu().numpy()
        arr = np.clip(arr, 0, 255).astype(np.uint8)
        image = Image.fromarray(arr).convert("RGB")
        buf = BytesIO()
        image.save(buf, format="JPEG", quality=int(quality), optimize=True)
        return buf.getvalue()

    def upload_image(self, session, api_host, api_key, img_tensor, verify_tls, pbar):
        img_bytes = self.tensor_to_jpeg_bytes(img_tensor)
        if len(img_bytes) > 12 * 1024 * 1024:
            raise RuntimeError(f"角色图过大：{len(img_bytes) / 1024 / 1024:.1f}MB，建议压缩到 12MB 内。")
        return self.upload_file(
            session,
            api_host,
            api_key,
            "kling_motion_role.jpg",
            img_bytes,
            "image/jpeg",
            verify_tls,
            pbar,
            progress=12,
        )

    def upload_video(self, session, api_host, api_key, video_path, verify_tls, pbar):
        path = str(video_path).strip().strip('"')
        if not os.path.exists(path):
            raise RuntimeError(f"本地动作视频不存在: {path}")
        ext = os.path.splitext(path)[1].lower()
        mime = {
            ".mp4": "video/mp4",
            ".mov": "video/quicktime",
            ".webm": "video/webm",
            ".m4v": "video/mp4",
        }.get(ext, "video/mp4")
        with open(path, "rb") as f:
            video_bytes = f.read()
        size_mb = len(video_bytes) / 1024 / 1024
        if size_mb <= 0:
            raise RuntimeError("本地动作视频为空。")
        if size_mb > 300:
            raise RuntimeError(f"动作视频过大：{size_mb:.1f}MB，建议先压缩或上传到 OSS/CDN 后填 URL。")
        filename = os.path.basename(path) or "motion.mp4"
        return self.upload_file(session, api_host, api_key, filename, video_bytes, mime, verify_tls, pbar, progress=20)

    def upload_file(self, session, api_host, api_key, filename, file_bytes, mime, verify_tls, pbar, progress):
        headers = {"Authorization": f"Bearer {api_key}"}
        files = {"file": (filename, file_bytes, mime)}
        endpoints = [
            f"{api_host}/alibailian/api/v1/upload",
            f"{api_host}/v1/upload",
            f"{api_host}/upload",
        ]
        last_error = ""
        for endpoint in endpoints:
            try:
                print(f"[Tikpan-KlingMotion] 上传文件到: {endpoint}", flush=True)
                resp = session.post(endpoint, headers=headers, files=files, timeout=(20, 600), verify=verify_tls)
                if resp.status_code >= 400:
                    last_error = f"HTTP {resp.status_code}: {self.safe_text(resp.text)}"
                    continue
                res_json = resp.json()
                url = (
                    res_json.get("url")
                    or (res_json.get("data") or {}).get("url")
                    or (res_json.get("result") or {}).get("url")
                    or res_json.get("filename")
                )
                if url:
                    if not str(url).startswith("http"):
                        url = f"{api_host}/{str(url).lstrip('/')}"
                    if pbar:
                        pbar.update_absolute(progress, 100)
                    return str(url)
                last_error = f"上传成功但未返回 URL: {json.dumps(res_json, ensure_ascii=False)[:500]}"
            except Exception as exc:
                last_error = str(exc)
        raise RuntimeError(f"文件上传失败: {last_error}")

    def poll_task(self, session, api_host, headers, task_id, max_wait_seconds, poll_interval, verify_tls, pbar):
        query_urls = [
            f"{api_host}/kling/v1/videos/motion-control/{task_id}",
            f"{api_host}/kling/v1/videos/motion-control?task_id={task_id}",
            f"{api_host}/kling/v1/videos/motion-control/query?id={task_id}",
            f"{api_host}/v1/videos/{task_id}",
            f"{api_host}/v1/videos/query?id={task_id}",
            f"{api_host}/alibailian/api/v1/tasks/{task_id}",
        ]
        start = time.time()
        poll_count = 0
        last_json = {}
        while time.time() - start < max_wait_seconds:
            comfy.model_management.throw_exception_if_processing_interrupted()
            time.sleep(poll_interval)
            poll_count += 1
            for url in query_urls:
                try:
                    resp = session.get(url, headers=headers, timeout=(15, 45), verify=verify_tls)
                    if resp.status_code in {404, 405}:
                        continue
                    if resp.status_code >= 400:
                        continue
                    res_json = resp.json()
                    last_json = res_json
                    status = extract_task_status(res_json)
                    output = extract_task_output(res_json)
                    elapsed = int(time.time() - start)
                    progress = min(85, 35 + int(elapsed * 50 / max(max_wait_seconds, 1)))
                    if pbar:
                        pbar.update_absolute(progress, 100)
                    print(f"[Tikpan-KlingMotion] 轮询 {poll_count} | status={status or 'unknown'} | url={url}", flush=True)
                    if is_success_status(status):
                        video_url = extract_video_url(res_json)
                        if video_url:
                            return True, video_url, res_json
                        return False, "❌ 任务成功但响应中没有视频链接", res_json
                    if is_failure_status(status):
                        return False, f"❌ 任务失败: {extract_error_message(output)}", res_json
                    video_url = extract_video_url(res_json)
                    if video_url and not status:
                        return True, video_url, res_json
                    break
                except Exception:
                    continue
        return False, f"⚠️ 轮询超时：任务仍在处理中 | task_id={task_id}", last_json

    def download_video(self, session, video_url, task_id, verify_tls):
        resp = session.get(video_url, timeout=(20, 600), verify=verify_tls)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")
        if not resp.content or len(resp.content) < 1024:
            raise RuntimeError(f"视频下载内容为空或过小: {len(resp.content) if resp.content else 0} bytes")
        if "text/html" in content_type.lower() or resp.content[:20].lstrip().lower().startswith(b"<!doctype"):
            raise RuntimeError(f"视频链接返回 HTML，不是视频文件: {self.safe_text(resp.text)}")
        safe_id = str(task_id or int(time.time())).replace("/", "_").replace(":", "_")
        out_dir = folder_paths.get_output_directory()
        save_path = os.path.join(out_dir, f"Tikpan_KlingMotion_{safe_id}.mp4")
        with open(save_path, "wb") as f:
            f.write(resp.content)
        return save_path

    def extract_task_id(self, res_json):
        if not isinstance(res_json, dict):
            return ""
        candidates = [res_json, res_json.get("data"), res_json.get("result"), res_json.get("output")]
        for obj in candidates:
            if isinstance(obj, dict):
                value = obj.get("task_id") or obj.get("taskId") or obj.get("id") or obj.get("task")
                if value:
                    return str(value).strip()
            elif isinstance(obj, str) and obj.strip():
                return obj.strip()
        return ""

    def safe_text(self, text, max_len=1000):
        try:
            return str(text or "")[:max_len].strip()
        except Exception:
            return ""

    def error_return(self, message, skip_error=False, task_id=""):
        if not skip_error:
            raise RuntimeError(message)
        return ("", task_id, "", message, None)


NODE_CLASS_MAPPINGS = {
    "TikpanKlingMotionControlNode": TikpanKlingMotionControlNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TikpanKlingMotionControlNode": "视频｜Kling Motion Control 动作控制",
}
