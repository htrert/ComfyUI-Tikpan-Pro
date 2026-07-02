from .tikpan_categories import CATEGORY_CANGYUAN

import base64
import json
import mimetypes
import os
import time
import traceback
from io import BytesIO
from urllib.parse import quote

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

CANGYUAN_API_HOST = "https://ai.cangyuansuanli.cn"
CANGYUAN_VIDEOS_ENDPOINT = "/v1/videos"
CANGYUAN_VIDEO_GENERATIONS_ENDPOINT = "/v1/video/generations"

SEEDANCE_MODEL_OPTIONS = [
    "Seedance-2.0",
    "seedance-2.0-mini-480p",
    "seedance-2.0-mini-720p",
    "seedance-2.0-fast-480p",
    "seedance-2.0-fast-720p",
    "seedance-2.0-480p",
    "seedance-2.0-720p",
    "seedance-2.0-1080p",
    "seedance-2.0-4k",
]
SEEDANCE_DURATION_OPTIONS = [f"{i}秒｜{i}" for i in range(4, 16)]
SEEDANCE_ASPECT_OPTIONS = [
    "16:9 横屏｜16:9",
    "9:16 竖屏｜9:16",
    "1:1 方形｜1:1",
    "21:9 宽银幕｜21:9",
    "3:4 竖屏｜3:4",
    "4:3 横屏｜4:3",
]
SEEDANCE_RESOLUTION_OPTIONS = ["480p｜480p", "720p｜720p", "1080p｜1080p", "4K｜4k"]

VEO_MODEL_OPTIONS = ["veo-3-1", "veo-3-1-fast"]
VEO_DURATION_OPTIONS = ["4秒｜4", "6秒｜6", "8秒｜8", "10秒｜10", "12秒｜12", "15秒｜15"]
VEO_ASPECT_OPTIONS = ["16:9 横屏｜16:9", "9:16 竖屏｜9:16"]

OMNI_IMAGE_MODEL_OPTIONS = ["omni-fast", "omni-fast-no-water"]
OMNI_V2V_MODEL_OPTIONS = ["omni-v2v", "omni-v2v-no-water"]
OMNI_ASPECT_OPTIONS = ["16:9 横屏｜16:9", "9:16 竖屏｜9:16"]

GROK_MODEL_OPTIONS = ["grok-video"]
GROK_DURATION_OPTIONS = ["4秒｜4s", "6秒｜6s", "8秒｜8s", "10秒｜10s", "12秒｜12s", "15秒｜15s"]
GROK_ASPECT_OPTIONS = [
    "1:1 方形｜1:1",
    "16:9 横屏｜16:9",
    "9:16 竖屏｜9:16",
    "4:3 横屏｜4:3",
    "3:4 竖屏｜3:4",
    "3:2 横屏｜3:2",
    "2:3 竖屏｜2:3",
]
GROK_RESOLUTION_OPTIONS = ["480p 标清｜480p", "720p 高清｜720p"]


def _video_path_from_input(value):
    if value is None:
        return ""
    if isinstance(value, (list, tuple)) and value:
        return _video_path_from_input(value[0])
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("filename", "path", "video", "file"):
            candidate = value.get(key)
            if isinstance(candidate, str):
                return candidate
    return str(value)


class _CangyuanVideoBase:
    CATEGORY = CATEGORY_CANGYUAN
    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "VIDEO")
    RETURN_NAMES = ("本地保存路径", "任务ID", "视频云端直链", "完整日志", "视频输出")
    OUTPUT_NODE = True

    def create_session(self, trust_env=False):
        session = requests.Session()
        session.trust_env = trust_env
        retry = Retry(
            total=3,
            connect=3,
            read=1,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=frozenset(["GET"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def headers(self, api_key, json_body=True):
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": "Tikpan-ComfyUI-Cangyuan-Video/1.0",
        }
        if json_body:
            headers["Content-Type"] = "application/json"
        return headers

    def tensor_to_data_url(self, tensor, quality=92):
        if tensor is None:
            return ""
        if len(tensor.shape) == 4:
            tensor = tensor[0]
        arr = 255.0 * tensor.detach().cpu().numpy()
        image = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGB")
        buf = BytesIO()
        image.save(buf, format="JPEG", quality=int(quality), optimize=True)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")

    def local_video_to_data_url(self, value, max_bytes=64 * 1024 * 1024):
        path = _video_path_from_input(value)
        if not path:
            return ""
        if not os.path.exists(path):
            raise RuntimeError(f"本地视频文件不存在: {path}")
        size = os.path.getsize(path)
        if size > max_bytes:
            raise RuntimeError(f"本地视频 {size / 1024 / 1024:.1f}MB 过大，请改用公开视频URL。")
        mime = mimetypes.guess_type(path)[0] or "video/mp4"
        with open(path, "rb") as f:
            return f"data:{mime};base64," + base64.b64encode(f.read()).decode("utf-8")

    def collect_images(self, kwargs, prefix, count):
        images = []
        for index in range(1, count + 1):
            tensor = pick(kwargs, f"{prefix}{index}", f"{prefix}_{index}", default=None)
            if tensor is not None:
                images.append(self.tensor_to_data_url(tensor))
        return images

    def split_urls(self, text, limit):
        values = []
        for token in str(text or "").replace("\n", ",").replace("，", ",").split(","):
            token = token.strip()
            if token and token.startswith(("http://", "https://", "data:")):
                values.append(token)
            if len(values) >= limit:
                break
        return values

    def submit_json_task(self, endpoint, payload, api_key, verify_tls):
        session = self.create_session(trust_env=False)
        response = session.post(
            f"{CANGYUAN_API_HOST}{endpoint}",
            json=payload,
            headers=self.headers(api_key, json_body=True),
            timeout=(20, 180),
            verify=verify_tls,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"任务创建失败: HTTP {response.status_code}\n{self.safe_text(response.text, 1800)}")
        try:
            create_json = response.json()
        except Exception as exc:
            raise RuntimeError(f"任务创建失败：响应不是 JSON\n{self.safe_text(response.text, 1800)}") from exc
        return session, create_json

    def poll_task(self, session, task_id, api_key, max_wait, poll_interval, verify_tls, pbar, endpoint=CANGYUAN_VIDEOS_ENDPOINT):
        task = quote(str(task_id or "").strip(), safe="")
        urls = [
            f"{CANGYUAN_API_HOST}{endpoint}/{task}",
            f"{CANGYUAN_API_HOST}{endpoint}/query?id={task}",
            f"{CANGYUAN_API_HOST}/v1/video/query?id={task}",
        ]
        start = time.time()
        poll_count = 0
        last_json = {}
        while time.time() - start < max_wait:
            comfy.model_management.throw_exception_if_processing_interrupted()
            time.sleep(poll_interval)
            poll_count += 1
            for url in urls:
                try:
                    resp = session.get(url, headers=self.headers(api_key, json_body=False), timeout=(15, 60), verify=verify_tls)
                    if resp.status_code in {404, 405}:
                        continue
                    if resp.status_code >= 400:
                        continue
                    res_json = resp.json()
                    last_json = res_json
                    status = extract_task_status(res_json)
                    video_url = extract_video_url(res_json)
                    elapsed = int(time.time() - start)
                    if pbar:
                        pbar.update_absolute(min(88, 25 + int(elapsed * 60 / max(max_wait, 1))), 100)
                    print(f"[Tikpan-Cangyuan-Video] poll={poll_count} status={status or 'unknown'} task_id={task_id}", flush=True)
                    if is_success_status(status):
                        if video_url:
                            return True, video_url, res_json
                        return False, "任务成功但响应里没有视频链接", res_json
                    if is_failure_status(status):
                        return False, f"任务失败: {json.dumps(res_json, ensure_ascii=False)[:1200]}", res_json
                    if video_url and not status:
                        return True, video_url, res_json
                    break
                except Exception:
                    continue
        return False, f"轮询超时：任务仍在处理中 | task_id={task_id}", last_json

    def extract_task_id(self, data):
        if isinstance(data, dict):
            for key in ("request_id", "task_id", "taskId", "id", "task", "operation_id", "operationId"):
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

    def download_video(self, session, video_url, prefix, task_id, verify_tls):
        resp = session.get(video_url, timeout=(20, 900), verify=verify_tls)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")
        if not resp.content or len(resp.content) < 1024:
            raise RuntimeError(f"视频下载内容为空或过短: {len(resp.content) if resp.content else 0} bytes")
        if "text/html" in content_type.lower() or resp.content[:20].lstrip().lower().startswith(b"<!doctype"):
            raise RuntimeError(f"视频链接返回 HTML，不是视频文件: {self.safe_text(resp.text)}")
        safe_id = str(task_id or int(time.time())).replace("/", "_").replace(":", "_")
        save_path = os.path.join(folder_paths.get_output_directory(), f"{prefix}_{safe_id}.mp4")
        with open(save_path, "wb") as f:
            f.write(resp.content)
        return save_path

    def redact_payload(self, payload):
        def redact(value):
            if isinstance(value, str) and value.startswith(("data:image", "data:video", "data:audio")):
                return value.split(",", 1)[0] + ",[base64 omitted]"
            if isinstance(value, list):
                return [redact(item) for item in value]
            if isinstance(value, dict):
                return {key: redact(child) for key, child in value.items()}
            return value

        return redact(payload)

    def safe_text(self, value, max_len=1000):
        try:
            return str(value or "")[:max_len].strip()
        except Exception:
            return ""

    def error_return(self, message, skip_error=False, task_id="", video_url=""):
        if not skip_error:
            raise RuntimeError(message)
        return ("", task_id, video_url, message, None)

    def finish_async_video(self, session, create_json, payload, api_key, max_wait, poll_interval, verify_tls, pbar, prefix, endpoint=CANGYUAN_VIDEOS_ENDPOINT):
        video_url = extract_video_url(create_json)
        task_id = self.extract_task_id(create_json)
        final_json = create_json
        if not video_url:
            if not task_id:
                raise RuntimeError(f"未获取到任务ID或视频链接\n{json.dumps(create_json, ensure_ascii=False)[:2000]}")
            ok, result, final_json = self.poll_task(session, task_id, api_key, max_wait, poll_interval, verify_tls, pbar, endpoint=endpoint)
            if not ok:
                raise RuntimeError(result)
            video_url = result
        else:
            task_id = task_id or "sync"

        if pbar:
            pbar.update_absolute(90, 100)
        save_path = self.download_video(self.create_session(trust_env=True), video_url, prefix, task_id, verify_tls)
        if pbar:
            pbar.update_absolute(100, 100)
        log_text = (
            f"✅ 沧元视频生成成功 | model={payload.get('model')} | endpoint={endpoint}\n"
            f"task_id={task_id}\nvideo_url={video_url}\npath={save_path}\n\n"
            f"payload={json.dumps(self.redact_payload(payload), ensure_ascii=False, indent=2)[:1800]}\n\n"
            f"response={json.dumps(final_json, ensure_ascii=False, indent=2)[:3000]}"
        )
        return (save_path, task_id, video_url, log_text, video_from_path(save_path))


class TikpanCangyuanSeedanceVideoNode(_CangyuanVideoBase):
    @classmethod
    def INPUT_TYPES(cls):
        optional = {
            "首帧图": ("IMAGE", {"tooltip": "可选首帧图。"}),
            "尾帧图": ("IMAGE", {"tooltip": "可选尾帧图。"}),
            "视频URL列表": ("STRING", {"multiline": True, "default": "", "tooltip": "可选，最多 3 个视频 URL，每行或逗号分隔。"}),
            "音频URL列表": ("STRING", {"multiline": True, "default": "", "tooltip": "可选，最多 3 个音频 URL，每行或逗号分隔。"}),
            "最长等待秒数": ("INT", {"default": 600, "min": 60, "max": 7200, "step": 30}),
            "查询间隔秒数": ("INT", {"default": 5, "min": 5, "max": 60, "step": 1}),
            "校验HTTPS证书": ("BOOLEAN", {"default": False}),
            "跳过错误": ("BOOLEAN", {"default": False}),
        }
        for index in range(1, 10):
            optional[f"参考图{index}"] = ("IMAGE", {"tooltip": f"可选参考图 {index}，Seedance 最多 9 张。"})
        return {
            "required": {
                "沧元说明": (["Seedance 2.0 | /v1/videos JSON 异步 | 支持 4-15 秒、多参考图/视频/音频、首尾帧"],),
                "获取密钥请访问": (["https://ai.cangyuansuanli.cn"],),
                "API_密钥": ("STRING", {"default": "sk-"}),
                "生成指令": ("STRING", {"multiline": True, "default": "A cinematic short video with smooth motion, realistic lighting, and coherent subject consistency."}),
                "模型": (SEEDANCE_MODEL_OPTIONS, {"default": SEEDANCE_MODEL_OPTIONS[0]}),
                "视频时长": (SEEDANCE_DURATION_OPTIONS, {"default": "6秒｜6"}),
                "画面比例": (SEEDANCE_ASPECT_OPTIONS, {"default": SEEDANCE_ASPECT_OPTIONS[0]}),
                "分辨率": (SEEDANCE_RESOLUTION_OPTIONS, {"default": "720p｜720p"}),
            },
            "optional": optional,
        }

    FUNCTION = "generate"
    DESCRIPTION = "沧元 Seedance 2.0 视频：同规格模型合并为下拉选择。"

    def build_payload(self, model, prompt, duration, aspect_ratio, resolution, images, first_frame, last_frame, videos, audios):
        payload = {
            "model": model,
            "prompt": prompt,
            "duration": int(duration),
            "seconds": int(duration),
            "aspect_ratio": aspect_ratio,
            "ratio": aspect_ratio,
            "resolution": resolution,
        }
        if first_frame:
            payload["image"] = first_frame
            payload["first_frame_image"] = first_frame
        if last_frame:
            payload["image_end"] = last_frame
            payload["last_frame_image"] = last_frame
        if images:
            payload["images"] = images[:9]
            payload["image_urls"] = images[:9]
        if videos:
            payload["videos"] = videos[:3]
            payload["video_urls"] = videos[:3]
        if audios:
            payload["audios"] = audios[:3]
            payload["audio_urls"] = audios[:3]
        return payload

    def generate(self, **kwargs):
        pbar = comfy.utils.ProgressBar(100)
        task_id = ""
        video_url = ""
        try:
            api_key = str(pick(kwargs, "API_密钥", "api_key", default="") or "").strip()
            prompt = str(pick(kwargs, "生成指令", "prompt", default="") or "").strip()
            model = str(pick(kwargs, "模型", "model", default=SEEDANCE_MODEL_OPTIONS[0]) or SEEDANCE_MODEL_OPTIONS[0])
            duration = option_int(pick(kwargs, "视频时长", "duration", default="6秒｜6"), default=6, minimum=4, maximum=15)
            aspect_ratio = option_value(pick(kwargs, "画面比例", "aspect_ratio", default=SEEDANCE_ASPECT_OPTIONS[0]), "16:9")
            resolution = option_value(pick(kwargs, "分辨率", "resolution", default="720p｜720p"), "720p")
            max_wait = int(pick(kwargs, "最长等待秒数", "max_wait_seconds", default=600) or 600)
            poll_interval = int(pick(kwargs, "查询间隔秒数", "poll_interval", default=5) or 5)
            verify_tls = bool(pick(kwargs, "校验HTTPS证书", "verify_tls", default=False))
            skip_error = bool(pick(kwargs, "跳过错误", "skip_error", default=False))
            if not api_key or api_key == "sk-" or len(api_key) < 10:
                return self.error_return("❌ 请填写有效的沧元 API 密钥", skip_error)
            if not prompt:
                return self.error_return("❌ 生成指令不能为空", skip_error)
            images = self.collect_images(kwargs, "参考图", 9)
            first_frame = self.tensor_to_data_url(pick(kwargs, "首帧图", "first_frame", default=None))
            last_frame = self.tensor_to_data_url(pick(kwargs, "尾帧图", "last_frame", default=None))
            videos = self.split_urls(pick(kwargs, "视频URL列表", "video_urls", default=""), 3)
            audios = self.split_urls(pick(kwargs, "音频URL列表", "audio_urls", default=""), 3)
            payload = self.build_payload(model, prompt, duration, aspect_ratio, resolution, images, first_frame, last_frame, videos, audios)
            pbar.update_absolute(10, 100)
            session, create_json = self.submit_json_task(CANGYUAN_VIDEOS_ENDPOINT, payload, api_key, verify_tls)
            pbar.update_absolute(25, 100)
            return self.finish_async_video(session, create_json, payload, api_key, max_wait, poll_interval, verify_tls, pbar, "cangyuan_seedance")
        except Exception as exc:
            task_id = task_id or ""
            msg = f"❌ 沧元 Seedance 节点异常: {exc}\n{traceback.format_exc()[:1800]}"
            skip_error = bool(pick(kwargs, "跳过错误", "skip_error", default=False))
            if not skip_error:
                raise RuntimeError(msg) from exc
            return ("", task_id, video_url, msg, None)


class TikpanCangyuanVeoVideoNode(_CangyuanVideoBase):
    @classmethod
    def INPUT_TYPES(cls):
        optional = {
            "最长等待秒数": ("INT", {"default": 600, "min": 60, "max": 7200, "step": 30}),
            "查询间隔秒数": ("INT", {"default": 5, "min": 5, "max": 60, "step": 1}),
            "校验HTTPS证书": ("BOOLEAN", {"default": False}),
            "跳过错误": ("BOOLEAN", {"default": False}),
        }
        for index in range(1, 6):
            optional[f"参考图{index}"] = ("IMAGE", {"tooltip": f"可选参考图 {index}，Veo 最多 5 张。"})
        return {
            "required": {
                "沧元说明": (["Veo 3.1 | /v1/videos JSON 异步 | 文生/图生，1280x720 或 720x1280"],),
                "获取密钥请访问": (["https://ai.cangyuansuanli.cn"],),
                "API_密钥": ("STRING", {"default": "sk-"}),
                "生成指令": ("STRING", {"multiline": True, "default": "A cinematic video with smooth camera movement and realistic lighting."}),
                "模型": (VEO_MODEL_OPTIONS, {"default": VEO_MODEL_OPTIONS[0]}),
                "视频时长": ("INT", {"default": 8, "min": 1, "max": 30, "step": 1, "tooltip": "沧元 Veo 规格：1-30 秒整数；常用 8/10 秒。"}),
                "画面比例": (VEO_ASPECT_OPTIONS, {"default": VEO_ASPECT_OPTIONS[0]}),
            },
            "optional": optional,
        }

    FUNCTION = "generate"
    DESCRIPTION = "沧元 Veo 3.1 视频：标准和 Fast 参数相同，用模型下拉选择。"

    def build_payload(self, model, prompt, duration, aspect_ratio, images):
        payload = {
            "model": model,
            "prompt": prompt,
            "duration": int(duration),
            "seconds": int(duration),
            "aspect_ratio": aspect_ratio,
        }
        if images:
            payload["images"] = images[:5]
            payload["image_urls"] = images[:5]
            payload["image"] = images[0]
        return payload

    def generate(self, **kwargs):
        pbar = comfy.utils.ProgressBar(100)
        try:
            api_key = str(pick(kwargs, "API_密钥", "api_key", default="") or "").strip()
            prompt = str(pick(kwargs, "生成指令", "prompt", default="") or "").strip()
            model = str(pick(kwargs, "模型", "model", default=VEO_MODEL_OPTIONS[0]) or VEO_MODEL_OPTIONS[0])
            duration = option_int(pick(kwargs, "视频时长", "duration", default=8), default=8, minimum=1, maximum=30)
            aspect_ratio = option_value(pick(kwargs, "画面比例", "aspect_ratio", default=VEO_ASPECT_OPTIONS[0]), "16:9")
            max_wait = int(pick(kwargs, "最长等待秒数", "max_wait_seconds", default=600) or 600)
            poll_interval = int(pick(kwargs, "查询间隔秒数", "poll_interval", default=5) or 5)
            verify_tls = bool(pick(kwargs, "校验HTTPS证书", "verify_tls", default=False))
            skip_error = bool(pick(kwargs, "跳过错误", "skip_error", default=False))
            if not api_key or api_key == "sk-" or len(api_key) < 10:
                return self.error_return("❌ 请填写有效的沧元 API 密钥", skip_error)
            if not prompt:
                return self.error_return("❌ 生成指令不能为空", skip_error)
            images = self.collect_images(kwargs, "参考图", 5)
            payload = self.build_payload(model, prompt, duration, aspect_ratio, images)
            pbar.update_absolute(10, 100)
            session, create_json = self.submit_json_task(CANGYUAN_VIDEOS_ENDPOINT, payload, api_key, verify_tls)
            pbar.update_absolute(25, 100)
            return self.finish_async_video(session, create_json, payload, api_key, max_wait, poll_interval, verify_tls, pbar, "cangyuan_veo")
        except Exception as exc:
            msg = f"❌ 沧元 Veo 节点异常: {exc}\n{traceback.format_exc()[:1800]}"
            skip_error = bool(pick(kwargs, "跳过错误", "skip_error", default=False))
            if not skip_error:
                raise RuntimeError(msg) from exc
            return ("", "", "", msg, None)


class TikpanCangyuanOmniVideoNode(_CangyuanVideoBase):
    @classmethod
    def INPUT_TYPES(cls):
        optional = {
            "首帧图": ("IMAGE", {"tooltip": "可选首帧图。"}),
            "尾帧图": ("IMAGE", {"tooltip": "可选尾帧图。"}),
            "最长等待秒数": ("INT", {"default": 600, "min": 60, "max": 7200, "step": 30}),
            "查询间隔秒数": ("INT", {"default": 5, "min": 5, "max": 60, "step": 1}),
            "校验HTTPS证书": ("BOOLEAN", {"default": False}),
            "跳过错误": ("BOOLEAN", {"default": False}),
        }
        for index in range(1, 6):
            optional[f"参考图{index}"] = ("IMAGE", {"tooltip": f"可选参考图 {index}，Omni 最多 5 张。"})
        return {
            "required": {
                "沧元说明": (["Omni 文生/图生视频 | 固定约 10 秒、720p | 支持首尾帧和最多 5 张参考图"],),
                "获取密钥请访问": (["https://ai.cangyuansuanli.cn"],),
                "API_密钥": ("STRING", {"default": "sk-"}),
                "生成指令": ("STRING", {"multiline": True, "default": "A cinematic commercial video with natural motion and clean details."}),
                "模型": (OMNI_IMAGE_MODEL_OPTIONS, {"default": OMNI_IMAGE_MODEL_OPTIONS[0]}),
                "画面比例": (OMNI_ASPECT_OPTIONS, {"default": OMNI_ASPECT_OPTIONS[0]}),
            },
            "optional": optional,
        }

    FUNCTION = "generate"
    DESCRIPTION = "沧元 Omni 文生/图生视频：omni-fast 与无水印版合并为下拉选择。"

    def build_payload(self, model, prompt, aspect_ratio, images, first_frame, last_frame):
        payload = {"model": model, "prompt": prompt, "aspect_ratio": aspect_ratio, "resolution": "720p"}
        if first_frame:
            payload["image"] = first_frame
            payload["first_frame_image"] = first_frame
        if last_frame:
            payload["image_end"] = last_frame
            payload["last_frame_image"] = last_frame
        if images:
            payload["images"] = images[:5]
            payload["image_urls"] = images[:5]
        return payload

    def generate(self, **kwargs):
        pbar = comfy.utils.ProgressBar(100)
        try:
            api_key = str(pick(kwargs, "API_密钥", "api_key", default="") or "").strip()
            prompt = str(pick(kwargs, "生成指令", "prompt", default="") or "").strip()
            model = str(pick(kwargs, "模型", "model", default=OMNI_IMAGE_MODEL_OPTIONS[0]) or OMNI_IMAGE_MODEL_OPTIONS[0])
            aspect_ratio = option_value(pick(kwargs, "画面比例", "aspect_ratio", default=OMNI_ASPECT_OPTIONS[0]), "16:9")
            max_wait = int(pick(kwargs, "最长等待秒数", "max_wait_seconds", default=600) or 600)
            poll_interval = int(pick(kwargs, "查询间隔秒数", "poll_interval", default=5) or 5)
            verify_tls = bool(pick(kwargs, "校验HTTPS证书", "verify_tls", default=False))
            skip_error = bool(pick(kwargs, "跳过错误", "skip_error", default=False))
            if not api_key or api_key == "sk-" or len(api_key) < 10:
                return self.error_return("❌ 请填写有效的沧元 API 密钥", skip_error)
            if not prompt:
                return self.error_return("❌ 生成指令不能为空", skip_error)
            images = self.collect_images(kwargs, "参考图", 5)
            first_frame = self.tensor_to_data_url(pick(kwargs, "首帧图", "first_frame", default=None))
            last_frame = self.tensor_to_data_url(pick(kwargs, "尾帧图", "last_frame", default=None))
            payload = self.build_payload(model, prompt, aspect_ratio, images, first_frame, last_frame)
            pbar.update_absolute(10, 100)
            session, create_json = self.submit_json_task(CANGYUAN_VIDEOS_ENDPOINT, payload, api_key, verify_tls)
            pbar.update_absolute(25, 100)
            return self.finish_async_video(session, create_json, payload, api_key, max_wait, poll_interval, verify_tls, pbar, "cangyuan_omni")
        except Exception as exc:
            msg = f"❌ 沧元 Omni 节点异常: {exc}\n{traceback.format_exc()[:1800]}"
            skip_error = bool(pick(kwargs, "跳过错误", "skip_error", default=False))
            if not skip_error:
                raise RuntimeError(msg) from exc
            return ("", "", "", msg, None)


class TikpanCangyuanOmniV2VNode(_CangyuanVideoBase):
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "沧元说明": (["Omni V2V 视频转视频 | 固定约 10 秒、720p | 需要 1 个视频输入"],),
                "获取密钥请访问": (["https://ai.cangyuansuanli.cn"],),
                "API_密钥": ("STRING", {"default": "sk-"}),
                "生成指令": ("STRING", {"multiline": True, "default": "Transform this video into a polished cinematic version while preserving the main subject."}),
                "模型": (OMNI_V2V_MODEL_OPTIONS, {"default": OMNI_V2V_MODEL_OPTIONS[0]}),
                "视频URL": ("STRING", {"default": "", "tooltip": "公开可访问的视频 URL；如连接本地视频，可留空。"}),
                "画面比例": (OMNI_ASPECT_OPTIONS, {"default": OMNI_ASPECT_OPTIONS[0]}),
            },
            "optional": {
                "本地视频": ("VIDEO", {"tooltip": "可选本地 VIDEO 输入；较大视频请使用视频URL。"}),
                "最长等待秒数": ("INT", {"default": 600, "min": 60, "max": 7200, "step": 30}),
                "查询间隔秒数": ("INT", {"default": 5, "min": 5, "max": 60, "step": 1}),
                "校验HTTPS证书": ("BOOLEAN", {"default": False}),
                "跳过错误": ("BOOLEAN", {"default": False}),
            },
        }

    FUNCTION = "generate"
    DESCRIPTION = "沧元 Omni V2V：视频转视频模型单独节点，避免和图生视频参数混淆。"

    def build_payload(self, model, prompt, video_ref, aspect_ratio):
        return {
            "model": model,
            "prompt": prompt,
            "video": video_ref,
            "video_url": video_ref,
            "videos": [video_ref],
            "aspect_ratio": aspect_ratio,
            "resolution": "720p",
        }

    def generate(self, **kwargs):
        pbar = comfy.utils.ProgressBar(100)
        try:
            api_key = str(pick(kwargs, "API_密钥", "api_key", default="") or "").strip()
            prompt = str(pick(kwargs, "生成指令", "prompt", default="") or "").strip()
            model = str(pick(kwargs, "模型", "model", default=OMNI_V2V_MODEL_OPTIONS[0]) or OMNI_V2V_MODEL_OPTIONS[0])
            video_ref = str(pick(kwargs, "视频URL", "video_url", default="") or "").strip()
            local_video = pick(kwargs, "本地视频", "local_video", default=None)
            aspect_ratio = option_value(pick(kwargs, "画面比例", "aspect_ratio", default=OMNI_ASPECT_OPTIONS[0]), "16:9")
            max_wait = int(pick(kwargs, "最长等待秒数", "max_wait_seconds", default=600) or 600)
            poll_interval = int(pick(kwargs, "查询间隔秒数", "poll_interval", default=5) or 5)
            verify_tls = bool(pick(kwargs, "校验HTTPS证书", "verify_tls", default=False))
            skip_error = bool(pick(kwargs, "跳过错误", "skip_error", default=False))
            if not api_key or api_key == "sk-" or len(api_key) < 10:
                return self.error_return("❌ 请填写有效的沧元 API 密钥", skip_error)
            if not prompt:
                return self.error_return("❌ 生成指令不能为空", skip_error)
            if not video_ref and local_video is not None:
                video_ref = self.local_video_to_data_url(local_video)
            if not video_ref:
                return self.error_return("❌ Omni V2V 需要填写视频URL或连接本地视频", skip_error)
            payload = self.build_payload(model, prompt, video_ref, aspect_ratio)
            pbar.update_absolute(10, 100)
            session, create_json = self.submit_json_task(CANGYUAN_VIDEOS_ENDPOINT, payload, api_key, verify_tls)
            pbar.update_absolute(25, 100)
            return self.finish_async_video(session, create_json, payload, api_key, max_wait, poll_interval, verify_tls, pbar, "cangyuan_omni_v2v")
        except Exception as exc:
            msg = f"❌ 沧元 Omni V2V 节点异常: {exc}\n{traceback.format_exc()[:1800]}"
            skip_error = bool(pick(kwargs, "跳过错误", "skip_error", default=False))
            if not skip_error:
                raise RuntimeError(msg) from exc
            return ("", "", "", msg, None)


class TikpanCangyuanGrokVideoNode(_CangyuanVideoBase):
    @classmethod
    def INPUT_TYPES(cls):
        optional = {
            "最长等待秒数": ("INT", {"default": 300, "min": 60, "max": 7200, "step": 30}),
            "查询间隔秒数": ("INT", {"default": 5, "min": 5, "max": 60, "step": 1}),
            "校验HTTPS证书": ("BOOLEAN", {"default": False}),
            "跳过错误": ("BOOLEAN", {"default": False}),
        }
        for index in range(1, 8):
            optional[f"参考图{index}"] = ("IMAGE", {"tooltip": f"可选参考图 {index}，grok-video 最多 7 张。"})
        return {
            "required": {
                "沧元说明": (["grok-video 通用视频 | /v1/video/generations | 文生/单图/多参考图，480p/720p"],),
                "获取密钥请访问": (["https://ai.cangyuansuanli.cn"],),
                "API_密钥": ("STRING", {"default": "sk-"}),
                "生成指令": ("STRING", {"multiline": True, "default": "Create a cinematic video with smooth motion and consistent subject details."}),
                "视频时长": (GROK_DURATION_OPTIONS, {"default": "6秒｜6s"}),
                "分辨率": (GROK_RESOLUTION_OPTIONS, {"default": GROK_RESOLUTION_OPTIONS[1]}),
                "画面比例": (GROK_ASPECT_OPTIONS, {"default": GROK_ASPECT_OPTIONS[1]}),
            },
            "optional": optional,
        }

    FUNCTION = "generate"
    DESCRIPTION = "沧元 grok-video 通用视频：支持文生、单图、多参考图。"

    def build_payload(self, model, prompt, duration, resolution, aspect_ratio, images):
        duration = min(int(duration), 10) if len(images or []) > 1 else int(duration)
        payload = {
            "model": model,
            "prompt": prompt,
            "seconds": duration,
            "resolution": resolution,
            "aspect_ratio": aspect_ratio,
        }
        if images:
            payload["image_urls"] = images[:7]
            payload["images"] = images[:7]
        return payload

    def generate(self, **kwargs):
        pbar = comfy.utils.ProgressBar(100)
        try:
            api_key = str(pick(kwargs, "API_密钥", "api_key", default="") or "").strip()
            prompt = str(pick(kwargs, "生成指令", "prompt", default="") or "").strip()
            model = GROK_MODEL_OPTIONS[0]
            duration = option_int(pick(kwargs, "视频时长", "duration", default="6秒｜6s"), default=6, minimum=4, maximum=15)
            resolution = option_value(pick(kwargs, "分辨率", "resolution", default=GROK_RESOLUTION_OPTIONS[1]), "720p")
            aspect_ratio = option_value(pick(kwargs, "画面比例", "aspect_ratio", default=GROK_ASPECT_OPTIONS[1]), "16:9")
            max_wait = int(pick(kwargs, "最长等待秒数", "max_wait_seconds", default=300) or 300)
            poll_interval = int(pick(kwargs, "查询间隔秒数", "poll_interval", default=5) or 5)
            verify_tls = bool(pick(kwargs, "校验HTTPS证书", "verify_tls", default=False))
            skip_error = bool(pick(kwargs, "跳过错误", "skip_error", default=False))
            if not api_key or api_key == "sk-" or len(api_key) < 10:
                return self.error_return("❌ 请填写有效的沧元 API 密钥", skip_error)
            if not prompt:
                return self.error_return("❌ 生成指令不能为空", skip_error)
            images = self.collect_images(kwargs, "参考图", 7)
            payload = self.build_payload(model, prompt, duration, resolution, aspect_ratio, images)
            pbar.update_absolute(10, 100)
            session, create_json = self.submit_json_task(CANGYUAN_VIDEO_GENERATIONS_ENDPOINT, payload, api_key, verify_tls)
            pbar.update_absolute(25, 100)
            return self.finish_async_video(session, create_json, payload, api_key, max_wait, poll_interval, verify_tls, pbar, "cangyuan_grok_video", endpoint=CANGYUAN_VIDEO_GENERATIONS_ENDPOINT)
        except Exception as exc:
            msg = f"❌ 沧元 grok-video 节点异常: {exc}\n{traceback.format_exc()[:1800]}"
            skip_error = bool(pick(kwargs, "跳过错误", "skip_error", default=False))
            if not skip_error:
                raise RuntimeError(msg) from exc
            return ("", "", "", msg, None)


class _CangyuanSeedancePerModelNode(_CangyuanVideoBase):
    MODEL_ID = ""
    RESOLUTION_OPTIONS = ["720p｜720p"]
    DEFAULT_RESOLUTION = "720p｜720p"
    NODE_HINT = ""

    @classmethod
    def INPUT_TYPES(cls):
        optional = {
            "首帧图": ("IMAGE", {"tooltip": "可选首帧图。"}),
            "尾帧图": ("IMAGE", {"tooltip": "可选尾帧图。"}),
            "视频URL列表": ("STRING", {"multiline": True, "default": "", "tooltip": "可选，最多 3 个视频 URL，每行或逗号分隔。"}),
            "音频URL列表": ("STRING", {"multiline": True, "default": "", "tooltip": "可选，最多 3 个音频 URL，每行或逗号分隔。"}),
            "最长等待秒数": ("INT", {"default": 600, "min": 60, "max": 7200, "step": 30}),
            "查询间隔秒数": ("INT", {"default": 5, "min": 5, "max": 60, "step": 1}),
            "校验HTTPS证书": ("BOOLEAN", {"default": False}),
            "跳过错误": ("BOOLEAN", {"default": False}),
        }
        for index in range(1, 10):
            optional[f"参考图{index}"] = ("IMAGE", {"tooltip": f"可选参考图 {index}，Seedance 最多 9 张。"})
        return {
            "required": {
                "沧元说明": ([f"{cls.MODEL_ID} | /v1/videos JSON 异步 | {cls.NODE_HINT or 'Seedance 2.0 视频生成'}"],),
                "获取密钥请访问": (["https://ai.cangyuansuanli.cn"],),
                "API_密钥": ("STRING", {"default": "sk-"}),
                "生成指令": ("STRING", {"multiline": True, "default": "A cinematic short video with smooth motion, realistic lighting, and coherent subject consistency."}),
                "视频时长": (SEEDANCE_DURATION_OPTIONS, {"default": "6秒｜6"}),
                "画面比例": (SEEDANCE_ASPECT_OPTIONS, {"default": SEEDANCE_ASPECT_OPTIONS[0]}),
                "分辨率": (cls.RESOLUTION_OPTIONS, {"default": cls.DEFAULT_RESOLUTION}),
            },
            "optional": optional,
        }

    FUNCTION = "generate"
    DESCRIPTION = "沧元 Seedance 2.0 单模型节点。"

    def build_payload(self, prompt, duration, aspect_ratio, resolution, images, first_frame, last_frame, videos, audios):
        payload = {
            "model": self.MODEL_ID,
            "prompt": prompt,
            "duration": int(duration),
            "seconds": int(duration),
            "aspect_ratio": aspect_ratio,
            "ratio": aspect_ratio,
            "resolution": resolution,
        }
        if first_frame:
            payload["image"] = first_frame
            payload["first_frame_image"] = first_frame
        if last_frame:
            payload["image_end"] = last_frame
            payload["last_frame_image"] = last_frame
        if images:
            payload["images"] = images[:9]
            payload["image_urls"] = images[:9]
        if videos:
            payload["videos"] = videos[:3]
            payload["video_urls"] = videos[:3]
        if audios:
            payload["audios"] = audios[:3]
            payload["audio_urls"] = audios[:3]
        return payload

    def generate(self, **kwargs):
        pbar = comfy.utils.ProgressBar(100)
        try:
            api_key = str(pick(kwargs, "API_密钥", "api_key", default="") or "").strip()
            prompt = str(pick(kwargs, "生成指令", "prompt", default="") or "").strip()
            duration = option_int(pick(kwargs, "视频时长", "duration", default="6秒｜6"), default=6, minimum=4, maximum=15)
            aspect_ratio = option_value(pick(kwargs, "画面比例", "aspect_ratio", default=SEEDANCE_ASPECT_OPTIONS[0]), "16:9")
            resolution = option_value(pick(kwargs, "分辨率", "resolution", default=self.DEFAULT_RESOLUTION), "720p")
            max_wait = int(pick(kwargs, "最长等待秒数", "max_wait_seconds", default=600) or 600)
            poll_interval = int(pick(kwargs, "查询间隔秒数", "poll_interval", default=5) or 5)
            verify_tls = bool(pick(kwargs, "校验HTTPS证书", "verify_tls", default=False))
            skip_error = bool(pick(kwargs, "跳过错误", "skip_error", default=False))
            if not api_key or api_key == "sk-" or len(api_key) < 10:
                return self.error_return("❌ 请填写有效的沧元 API 密钥", skip_error)
            if not prompt:
                return self.error_return("❌ 生成指令不能为空", skip_error)
            images = self.collect_images(kwargs, "参考图", 9)
            first_frame = self.tensor_to_data_url(pick(kwargs, "首帧图", "first_frame", default=None))
            last_frame = self.tensor_to_data_url(pick(kwargs, "尾帧图", "last_frame", default=None))
            videos = self.split_urls(pick(kwargs, "视频URL列表", "video_urls", default=""), 3)
            audios = self.split_urls(pick(kwargs, "音频URL列表", "audio_urls", default=""), 3)
            payload = self.build_payload(prompt, duration, aspect_ratio, resolution, images, first_frame, last_frame, videos, audios)
            pbar.update_absolute(10, 100)
            session, create_json = self.submit_json_task(CANGYUAN_VIDEOS_ENDPOINT, payload, api_key, verify_tls)
            pbar.update_absolute(25, 100)
            return self.finish_async_video(session, create_json, payload, api_key, max_wait, poll_interval, verify_tls, pbar, "cangyuan_seedance")
        except Exception as exc:
            msg = f"❌ 沧元 {self.MODEL_ID} 节点异常: {exc}\n{traceback.format_exc()[:1800]}"
            skip_error = bool(pick(kwargs, "跳过错误", "skip_error", default=False))
            if not skip_error:
                raise RuntimeError(msg) from exc
            return ("", "", "", msg, None)


class TikpanCangyuanSeedance20Node(_CangyuanSeedancePerModelNode):
    MODEL_ID = "Seedance-2.0"
    RESOLUTION_OPTIONS = ["480p｜480p", "720p｜720p"]
    DEFAULT_RESOLUTION = "720p｜720p"
    NODE_HINT = "特惠模型；480p/720p，4-15 秒，支持首尾帧和多参考素材。"


class TikpanCangyuanSeedance20Mini480pNode(_CangyuanSeedancePerModelNode):
    MODEL_ID = "seedance-2.0-mini-480p"
    RESOLUTION_OPTIONS = ["480p｜480p"]
    DEFAULT_RESOLUTION = "480p｜480p"


class TikpanCangyuanSeedance20Mini720pNode(_CangyuanSeedancePerModelNode):
    MODEL_ID = "seedance-2.0-mini-720p"
    RESOLUTION_OPTIONS = ["720p｜720p"]
    DEFAULT_RESOLUTION = "720p｜720p"


class TikpanCangyuanSeedance20Fast480pNode(_CangyuanSeedancePerModelNode):
    MODEL_ID = "seedance-2.0-fast-480p"
    RESOLUTION_OPTIONS = ["480p｜480p"]
    DEFAULT_RESOLUTION = "480p｜480p"


class TikpanCangyuanSeedance20Fast720pNode(_CangyuanSeedancePerModelNode):
    MODEL_ID = "seedance-2.0-fast-720p"
    RESOLUTION_OPTIONS = ["720p｜720p"]
    DEFAULT_RESOLUTION = "720p｜720p"


class TikpanCangyuanSeedance20480pNode(_CangyuanSeedancePerModelNode):
    MODEL_ID = "seedance-2.0-480p"
    RESOLUTION_OPTIONS = ["480p｜480p"]
    DEFAULT_RESOLUTION = "480p｜480p"


class TikpanCangyuanSeedance20720pNode(_CangyuanSeedancePerModelNode):
    MODEL_ID = "seedance-2.0-720p"
    RESOLUTION_OPTIONS = ["720p｜720p"]
    DEFAULT_RESOLUTION = "720p｜720p"


class TikpanCangyuanSeedance201080pNode(_CangyuanSeedancePerModelNode):
    MODEL_ID = "seedance-2.0-1080p"
    RESOLUTION_OPTIONS = ["1080p｜1080p"]
    DEFAULT_RESOLUTION = "1080p｜1080p"


class TikpanCangyuanSeedance204kNode(_CangyuanSeedancePerModelNode):
    MODEL_ID = "seedance-2.0-4k"
    RESOLUTION_OPTIONS = ["4K｜4k"]
    DEFAULT_RESOLUTION = "4K｜4k"


class _CangyuanVeoPerModelNode(TikpanCangyuanVeoVideoNode):
    MODEL_ID = ""

    @classmethod
    def INPUT_TYPES(cls):
        inputs = super().INPUT_TYPES()
        required = dict(inputs["required"])
        required.pop("模型", None)
        required["沧元说明"] = ([f"{cls.MODEL_ID} | /v1/videos JSON 异步 | 文生/图生，1-30 秒，16:9/9:16"],)
        inputs["required"] = required
        return inputs

    def generate(self, **kwargs):
        kwargs = dict(kwargs)
        kwargs["模型"] = self.MODEL_ID
        return super().generate(**kwargs)


class TikpanCangyuanVeo31Node(_CangyuanVeoPerModelNode):
    MODEL_ID = "veo-3-1"


class TikpanCangyuanVeo31FastNode(_CangyuanVeoPerModelNode):
    MODEL_ID = "veo-3-1-fast"


class _CangyuanOmniPerModelNode(TikpanCangyuanOmniVideoNode):
    MODEL_ID = ""

    @classmethod
    def INPUT_TYPES(cls):
        inputs = super().INPUT_TYPES()
        required = dict(inputs["required"])
        required.pop("模型", None)
        required["沧元说明"] = ([f"{cls.MODEL_ID} | /v1/videos JSON 异步 | 固定约 10 秒、720p，支持文生/图生/首尾帧"],)
        inputs["required"] = required
        return inputs

    def generate(self, **kwargs):
        kwargs = dict(kwargs)
        kwargs["模型"] = self.MODEL_ID
        return super().generate(**kwargs)


class TikpanCangyuanOmniFastNode(_CangyuanOmniPerModelNode):
    MODEL_ID = "omni-fast"


class TikpanCangyuanOmniFastNoWaterNode(_CangyuanOmniPerModelNode):
    MODEL_ID = "omni-fast-no-water"


class _CangyuanOmniV2VPerModelNode(TikpanCangyuanOmniV2VNode):
    MODEL_ID = ""

    @classmethod
    def INPUT_TYPES(cls):
        inputs = super().INPUT_TYPES()
        required = dict(inputs["required"])
        required.pop("模型", None)
        required["沧元说明"] = ([f"{cls.MODEL_ID} | /v1/videos JSON 异步 | 固定约 10 秒、720p，视频转视频"],)
        inputs["required"] = required
        return inputs

    def generate(self, **kwargs):
        kwargs = dict(kwargs)
        kwargs["模型"] = self.MODEL_ID
        return super().generate(**kwargs)


class TikpanCangyuanOmniV2VStandardNode(_CangyuanOmniV2VPerModelNode):
    MODEL_ID = "omni-v2v"


class TikpanCangyuanOmniV2VNoWaterNode(_CangyuanOmniV2VPerModelNode):
    MODEL_ID = "omni-v2v-no-water"


NODE_CLASS_MAPPINGS = {
    "TikpanCangyuanSeedance20Node": TikpanCangyuanSeedance20Node,
    "TikpanCangyuanSeedance20Mini480pNode": TikpanCangyuanSeedance20Mini480pNode,
    "TikpanCangyuanSeedance20Mini720pNode": TikpanCangyuanSeedance20Mini720pNode,
    "TikpanCangyuanSeedance20Fast480pNode": TikpanCangyuanSeedance20Fast480pNode,
    "TikpanCangyuanSeedance20Fast720pNode": TikpanCangyuanSeedance20Fast720pNode,
    "TikpanCangyuanSeedance20480pNode": TikpanCangyuanSeedance20480pNode,
    "TikpanCangyuanSeedance20720pNode": TikpanCangyuanSeedance20720pNode,
    "TikpanCangyuanSeedance201080pNode": TikpanCangyuanSeedance201080pNode,
    "TikpanCangyuanSeedance204kNode": TikpanCangyuanSeedance204kNode,
    "TikpanCangyuanVeo31Node": TikpanCangyuanVeo31Node,
    "TikpanCangyuanVeo31FastNode": TikpanCangyuanVeo31FastNode,
    "TikpanCangyuanOmniFastNode": TikpanCangyuanOmniFastNode,
    "TikpanCangyuanOmniFastNoWaterNode": TikpanCangyuanOmniFastNoWaterNode,
    "TikpanCangyuanOmniV2VStandardNode": TikpanCangyuanOmniV2VStandardNode,
    "TikpanCangyuanOmniV2VNoWaterNode": TikpanCangyuanOmniV2VNoWaterNode,
    "TikpanCangyuanGrokVideoNode": TikpanCangyuanGrokVideoNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TikpanCangyuanSeedance20Node": "沧元｜Seedance-2.0 视频生成",
    "TikpanCangyuanSeedance20Mini480pNode": "沧元｜seedance-2.0-mini-480p 视频生成",
    "TikpanCangyuanSeedance20Mini720pNode": "沧元｜seedance-2.0-mini-720p 视频生成",
    "TikpanCangyuanSeedance20Fast480pNode": "沧元｜seedance-2.0-fast-480p 视频生成",
    "TikpanCangyuanSeedance20Fast720pNode": "沧元｜seedance-2.0-fast-720p 视频生成",
    "TikpanCangyuanSeedance20480pNode": "沧元｜seedance-2.0-480p 视频生成",
    "TikpanCangyuanSeedance20720pNode": "沧元｜seedance-2.0-720p 视频生成",
    "TikpanCangyuanSeedance201080pNode": "沧元｜seedance-2.0-1080p 视频生成",
    "TikpanCangyuanSeedance204kNode": "沧元｜seedance-2.0-4k 视频生成",
    "TikpanCangyuanVeo31Node": "沧元｜veo-3-1 视频生成",
    "TikpanCangyuanVeo31FastNode": "沧元｜veo-3-1-fast 视频生成",
    "TikpanCangyuanOmniFastNode": "沧元｜omni-fast 文/图生视频",
    "TikpanCangyuanOmniFastNoWaterNode": "沧元｜omni-fast-no-water 文/图生视频",
    "TikpanCangyuanOmniV2VStandardNode": "沧元｜omni-v2v 视频转视频",
    "TikpanCangyuanOmniV2VNoWaterNode": "沧元｜omni-v2v-no-water 视频转视频",
    "TikpanCangyuanGrokVideoNode": "沧元｜Grok 通用视频生成",
}
