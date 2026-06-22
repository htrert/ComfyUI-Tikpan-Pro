from .tikpan_categories import CATEGORY_VIDEO
import base64
import json
import mimetypes
import os
import time
import traceback
from io import BytesIO

import numpy as np
import requests
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
from .tikpan_node_options import (
    API_HOST_OPTIONS,
    GROK_ASPECT_OPTIONS,
    GROK_IMAGINE_VIDEO_MODE_OPTIONS,
    GROK_IMAGINE_VIDEO_RESOLUTION_OPTIONS,
    normalize_api_host,
    normalize_seed,
    option_value,
    pick,
)


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

MAX_INLINE_VIDEO_BYTES = 80 * 1024 * 1024
GROK_IMAGINE_VIDEO_MODEL = "grok-imagine-video"
GROK_IMAGINE_VIDEO_PREVIEW_MODEL = "grok-imagine-video-1.5-preview"


class _TikpanGrokImagineVideoBase:
    MODEL_ID = ""
    MODEL_NAME = ""
    PRICE_TEXT = ""
    DESCRIPTION_TEXT = ""
    DEFAULT_PROMPT = "A cinematic short video with smooth motion, natural sound, realistic lighting, high detail."

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "VIDEO")
    RETURN_NAMES = ("📁_本地保存路径", "🆔_任务ID", "🔗_视频云端直链", "📄_完整日志", "🎬_视频输出")
    OUTPUT_NODE = True
    FUNCTION = "generate_video"
    CATEGORY = CATEGORY_VIDEO

    def generate_video(self, **kwargs):
        pbar = comfy.utils.ProgressBar(100)
        task_id = ""
        video_url = ""
        endpoint = "/v1/videos/generations"
        try:
            api_key = str(pick(kwargs, "API_密钥", "api_key", default="") or "").strip()
            api_host = normalize_api_host(pick(kwargs, "中转站地址", "api_host", default=API_HOST_OPTIONS[0]))
            prompt = str(pick(kwargs, "生成指令", "prompt", default="") or "").strip()
            resolution = option_value(pick(kwargs, "分辨率", "resolution", default=GROK_IMAGINE_VIDEO_RESOLUTION_OPTIONS[0]), "480p")
            aspect_ratio = option_value(pick(kwargs, "画面比例", "aspect_ratio", default=GROK_ASPECT_OPTIONS[0]), "16:9")
            seed = normalize_seed(pick(kwargs, "随机种子", "seed", default=888888), default=888888)
            skip_error = bool(pick(kwargs, "跳过错误", "skip_error", default=False))
            verify_tls = bool(pick(kwargs, "校验HTTPS证书", "verify_tls", default=False))
            max_wait = int(pick(kwargs, "最长等待秒数", "max_wait_seconds", default=1200) or 1200)
            poll_interval = int(pick(kwargs, "查询间隔秒数", "poll_interval", default=8) or 8)

            if not api_key or api_key == "sk-" or len(api_key) < 10:
                return self.error_return("❌ 请填写有效的 API 密钥", skip_error)
            if not prompt:
                return self.error_return("❌ 生成指令不能为空", skip_error)

            payload, endpoint = self.prepare_payload(kwargs, prompt, resolution, aspect_ratio, seed)
            pbar.update_absolute(15, 100)

            session = self.create_session()
            headers = self.headers(api_key)
            print(f"[Tikpan-GrokImagineVideo] POST {endpoint} | Payload: {json.dumps(self.redact_payload(payload), ensure_ascii=False)[:1500]}", flush=True)
            response = session.post(
                f"{api_host}{endpoint}",
                json=payload,
                headers=headers,
                timeout=(20, 180),
                verify=verify_tls,
            )
            if response.status_code >= 400:
                return self.error_return(f"❌ 任务创建失败: HTTP {response.status_code}\n{self.safe_text(response.text)}", skip_error)
            try:
                create_json = response.json()
            except Exception:
                return self.error_return(f"❌ 任务创建失败：响应不是 JSON\n{self.safe_text(response.text)}", skip_error)

            task_id = self.extract_task_id(create_json)
            video_url = extract_video_url(create_json)
            if not video_url and not task_id:
                return self.error_return(f"❌ 任务创建失败：未获取到任务ID或视频链接\n{json.dumps(create_json, ensure_ascii=False)[:1500]}", skip_error)

            pbar.update_absolute(30, 100)
            final_json = create_json
            if not video_url:
                ok, result, final_json = self.poll_task(session, api_host, headers, task_id, max_wait, poll_interval, verify_tls, pbar)
                if not ok:
                    return self.error_return(result, skip_error, task_id=task_id)
                video_url = result

            pbar.update_absolute(88, 100)
            save_path = self.download_video(session, video_url, self.file_prefix(), task_id or "sync", verify_tls)
            pbar.update_absolute(100, 100)
            log = (
                f"✅ {self.MODEL_NAME} 视频生成成功 | model={self.MODEL_ID} | endpoint={endpoint} | resolution={resolution} | aspect_ratio={aspect_ratio}\n"
                f"task_id={task_id or 'sync'}\nvideo_url={video_url}\npath={save_path}\n\n"
                f"{json.dumps(final_json, ensure_ascii=False, indent=2)[:3000]}"
            )
            return (save_path, task_id or "sync", video_url, log, video_from_path(save_path))
        except Exception as exc:
            tb = traceback.format_exc()
            msg = f"❌ {self.MODEL_NAME} 异常: {exc}\n{tb[:2000]}"
            print(f"[Tikpan-GrokImagineVideo] {msg}", flush=True)
            skip_error = bool(pick(kwargs, "跳过错误", "skip_error", default=False))
            if not skip_error:
                raise RuntimeError(msg) from exc
            return ("", task_id, video_url, msg, None)

    def prepare_payload(self, kwargs, prompt, resolution, aspect_ratio, seed):
        raise NotImplementedError

    def build_payload(
        self,
        model,
        prompt,
        resolution,
        aspect_ratio,
        seed=None,
        mode="text_to_video",
        first_frame_image="",
        reference_image="",
        video="",
    ):
        payload = {
            "model": model,
            "prompt": prompt,
            "resolution": resolution,
            "aspect_ratio": aspect_ratio,
        }
        if seed is not None:
            payload["seed"] = int(seed)
        if mode:
            payload["mode"] = mode
        if first_frame_image:
            payload["first_frame_image"] = first_frame_image
        if reference_image:
            payload["reference_image"] = reference_image
        if video:
            payload["video"] = video
        return payload

    def create_session(self):
        session = requests.Session()
        session.trust_env = False
        retry = Retry(total=3, connect=3, read=1, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=frozenset(["GET", "POST"]), raise_on_status=False)
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def headers(self, api_key):
        return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "Accept": "application/json", "User-Agent": "Tikpan-ComfyUI-GrokImagineVideo/1.0"}

    def tensor_to_data_url(self, img_tensor, quality=92):
        if len(img_tensor.shape) == 4:
            img_tensor = img_tensor[0]
        arr = 255.0 * img_tensor.detach().cpu().numpy()
        image = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGB")
        buf = BytesIO()
        image.save(buf, format="JPEG", quality=int(quality), optimize=True)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")

    def video_path_from_input(self, local_video, path_text=""):
        explicit = str(path_text or "").strip().strip('"')
        if explicit:
            return explicit
        if local_video is None:
            return ""
        if isinstance(local_video, (list, tuple)) and local_video:
            return str(local_video[0])
        if isinstance(local_video, str):
            return local_video
        return str(local_video)

    def video_to_data_url(self, video_path):
        if not video_path:
            return ""
        if not os.path.exists(video_path):
            raise ValueError(f"本地视频不存在: {video_path}")
        size = os.path.getsize(video_path)
        if size <= 0:
            raise ValueError(f"本地视频为空: {video_path}")
        if size > MAX_INLINE_VIDEO_BYTES:
            raise ValueError(f"本地视频 {size / 1024 / 1024:.1f}MB，超过 inline 上传限制，请改用 视频URL。")
        mime_type = self.guess_mime_type(video_path)
        with open(video_path, "rb") as f:
            data = f.read()
        return f"data:{mime_type};base64," + base64.b64encode(data).decode("utf-8")

    def media_url_or_data_url(self, video_url, local_video, local_video_path):
        video_url = str(video_url or "").strip()
        if video_url:
            if not video_url.startswith(("http://", "https://")):
                raise ValueError("视频URL 必须是 http/https 公开地址。")
            return video_url
        video_path = self.video_path_from_input(local_video, local_video_path)
        return self.video_to_data_url(video_path) if video_path else ""

    def guess_mime_type(self, path_or_url, fallback="video/mp4"):
        mime_type, _ = mimetypes.guess_type(str(path_or_url or ""))
        return mime_type or fallback

    def poll_task(self, session, api_host, headers, task_id, max_wait, poll_interval, verify_tls, pbar):
        start = time.time()
        last_json = {}
        poll_count = 0
        query_urls = [
            f"{api_host}/v1/videos/{task_id}",
            f"{api_host}/v1/videos/query?id={task_id}",
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
                    output = extract_task_output(res_json)
                    video_url = extract_video_url(res_json)
                    elapsed = int(time.time() - start)
                    if pbar:
                        pbar.update_absolute(min(85, 30 + int(elapsed * 55 / max(max_wait, 1))), 100)
                    print(f"[Tikpan-GrokImagineVideo] 轮询 {poll_count} | status={status or 'unknown'} | task_id={task_id}", flush=True)
                    if is_success_status(status):
                        if video_url:
                            return True, video_url, res_json
                        return False, "❌ 任务成功但响应中没有视频链接", res_json
                    if is_failure_status(status):
                        return False, f"❌ 任务失败: {extract_error_message(output)}", res_json
                    if video_url and not status:
                        return True, video_url, res_json
                except Exception:
                    continue
        return False, f"⚠️ 轮询超时：任务仍在处理中 | task_id={task_id}", last_json

    def download_video(self, session, video_url, prefix, task_id, verify_tls):
        resp = session.get(video_url, timeout=(20, 600), verify=verify_tls)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")
        if not resp.content or len(resp.content) < 1024:
            raise RuntimeError(f"视频下载内容为空或过小: {len(resp.content) if resp.content else 0} bytes")
        if "text/html" in content_type.lower() or resp.content[:20].lstrip().lower().startswith(b"<!doctype"):
            raise RuntimeError(f"视频链接返回 HTML，不是视频文件: {self.safe_text(resp.text)}")
        safe_id = str(task_id or int(time.time())).replace("/", "_").replace(":", "_")
        save_path = os.path.join(folder_paths.get_output_directory(), f"{prefix}_{safe_id}.mp4")
        with open(save_path, "wb") as f:
            f.write(resp.content)
        return save_path

    def extract_task_id(self, res_json):
        if not isinstance(res_json, dict):
            return ""
        for obj in (res_json, res_json.get("data"), res_json.get("result"), res_json.get("output")):
            if isinstance(obj, dict):
                value = obj.get("task_id") or obj.get("taskId") or obj.get("id") or obj.get("task")
                if value:
                    return str(value).strip()
            elif isinstance(obj, str) and obj.strip():
                return obj.strip()
        return ""

    def redact_payload(self, payload):
        redacted = {}
        for key, value in payload.items():
            if isinstance(value, str) and value.startswith("data:image"):
                redacted[key] = "[data:image omitted]"
            elif isinstance(value, str) and value.startswith("data:video"):
                redacted[key] = "[data:video omitted]"
            else:
                redacted[key] = value
        return redacted

    def safe_text(self, value, max_len=1000):
        try:
            return str(value or "")[:max_len].strip()
        except Exception:
            return ""

    def error_return(self, message, skip_error=False, task_id=""):
        if not skip_error:
            raise RuntimeError(message)
        return ("", task_id, "", message, None)

    def file_prefix(self):
        return self.MODEL_ID.replace("-", "_").replace(".", "_")


class TikpanGrokImagineVideoNode(_TikpanGrokImagineVideoBase):
    MODEL_ID = GROK_IMAGINE_VIDEO_MODEL
    MODEL_NAME = "Grok Imagine Video"
    PRICE_TEXT = "优质 Grok 分组按次计费：480p 输入图 0.0120/张、输入视频 0.0600/秒、输出视频 0.3000/秒；720p 输入图 0.0120/张、输入视频 0.0600/秒、输出视频 0.4200/秒。"
    DESCRIPTION = "Grok Imagine Video：支持文生视频、首帧图生视频、参考图生视频、视频编辑，使用 Tikpan 官方格式 /v1/videos/generations 与 /v1/videos/edits。"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "💰_福利_💰": (["🔥 0.6元RMB兑1美元余额 | 全网底价 👉 https://tikpan.com"],),
                "获取密钥请访问": (["👉 https://tikpan.com (官方授权Key获取点)"],),
                "节点说明": ([f"{cls.DESCRIPTION} | {cls.PRICE_TEXT}"],),
                "API_密钥": ("STRING", {"default": "sk-", "tooltip": "Tikpan 平台的 API 密钥，以 sk- 开头，从 https://tikpan.com 获取"}),
                "生成模式": (GROK_IMAGINE_VIDEO_MODE_OPTIONS, {"default": GROK_IMAGINE_VIDEO_MODE_OPTIONS[0], "tooltip": "选择文生、首帧图生、参考图生或视频编辑"}),
                "生成指令": ("STRING", {"multiline": True, "default": cls.DEFAULT_PROMPT, "tooltip": "描述视频主体、动作、镜头、风格和声音氛围，推荐英文或中英混合"}),
                "模型": ([cls.MODEL_ID], {"default": cls.MODEL_ID, "tooltip": "本节点固定使用 grok-imagine-video"}),
                "分辨率": (GROK_IMAGINE_VIDEO_RESOLUTION_OPTIONS, {"default": "480p", "tooltip": "选择 480p 或 720p；720p 输出按秒计费更高"}),
                "画面比例": (GROK_ASPECT_OPTIONS, {"default": GROK_ASPECT_OPTIONS[0], "tooltip": "画面比例参数"}),
                "随机种子": ("INT", {"default": 888888, "min": 0, "max": 2147483647, "step": 1, "tooltip": "固定种子便于复现；旧工作流的 -1 会自动规范化"}),
            },
            "optional": {
                "首帧图": ("IMAGE", {"tooltip": "首帧图生视频模式必填"}),
                "参考图": ("IMAGE", {"tooltip": "参考图生视频模式必填"}),
                "视频URL": ("STRING", {"default": "", "tooltip": "视频编辑模式可填 http/https 视频地址，优先于本地视频"}),
                "本地视频": ("VIDEO", {"tooltip": "视频编辑模式可连接本地视频；大文件建议改用 视频URL"}),
                "本地视频路径": ("STRING", {"default": "", "tooltip": "视频编辑模式可直接填写 mp4/mov/webm 等本地路径"}),
                "中转站地址": (API_HOST_OPTIONS, {"default": API_HOST_OPTIONS[0], "tooltip": "Tikpan 中转站地址，一般保持默认即可"}),
                "最长等待秒数": ("INT", {"default": 1200, "min": 60, "max": 7200, "step": 30, "tooltip": "等待视频生成完成的最长秒数"}),
                "查询间隔秒数": ("INT", {"default": 8, "min": 5, "max": 60, "step": 1, "tooltip": "轮询任务状态的间隔秒数"}),
                "校验HTTPS证书": ("BOOLEAN", {"default": False, "tooltip": "默认关闭以兼容部分网络；遇到 SSL 问题可保持关闭"}),
                "跳过错误": ("BOOLEAN", {"default": False, "tooltip": "开启后异常时返回空，不打断后续工作流"}),
            },
        }

    def prepare_payload(self, kwargs, prompt, resolution, aspect_ratio, seed):
        mode = option_value(pick(kwargs, "生成模式", "mode", default=GROK_IMAGINE_VIDEO_MODE_OPTIONS[0]), "text_to_video")
        first_frame = pick(kwargs, "首帧图", "first_frame_image", default=None)
        reference_image = pick(kwargs, "参考图", "reference_image", default=None)
        endpoint = "/v1/videos/edits" if mode == "video_edit" else "/v1/videos/generations"
        first_frame_data = ""
        reference_data = ""
        video_data = ""

        if mode == "first_frame":
            if first_frame is None:
                raise ValueError("首帧图生视频模式需要连接 首帧图。")
            first_frame_data = self.tensor_to_data_url(first_frame)
        elif mode == "reference_image":
            if reference_image is None:
                raise ValueError("参考图生视频模式需要连接 参考图。")
            reference_data = self.tensor_to_data_url(reference_image)
        elif mode == "video_edit":
            video_data = self.media_url_or_data_url(
                pick(kwargs, "视频URL", "video_url", default=""),
                pick(kwargs, "本地视频", "local_video", default=None),
                pick(kwargs, "本地视频路径", "local_video_path", default=""),
            )
            if not video_data:
                raise ValueError("视频编辑模式需要填写 视频URL 或连接 本地视频。")

        payload = self.build_payload(
            model=self.MODEL_ID,
            prompt=prompt,
            resolution=resolution,
            aspect_ratio=aspect_ratio,
            seed=seed,
            mode=mode,
            first_frame_image=first_frame_data,
            reference_image=reference_data,
            video=video_data,
        )
        return payload, endpoint


class TikpanGrokImagineVideo15PreviewNode(_TikpanGrokImagineVideoBase):
    MODEL_ID = GROK_IMAGINE_VIDEO_PREVIEW_MODEL
    MODEL_NAME = "Grok Imagine Video 1.5 Preview"
    PRICE_TEXT = "优质 Grok 分组按次计费：480p 输入图 0.0600/张、输出视频 0.4800/秒；720p 输出视频 0.8400/秒。"
    DESCRIPTION = "Grok Imagine Video 1.5 Preview：预览版首帧图生短视频模型，使用 Tikpan 官方格式 /v1/videos/generations。"
    DEFAULT_PROMPT = "Turn this image into a cinematic short video with natural motion, expressive atmosphere, and matching sound."

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "💰_福利_💰": (["🔥 0.6元RMB兑1美元余额 | 全网底价 👉 https://tikpan.com"],),
                "获取密钥请访问": (["👉 https://tikpan.com (官方授权Key获取点)"],),
                "节点说明": ([f"{cls.DESCRIPTION} | {cls.PRICE_TEXT}"],),
                "API_密钥": ("STRING", {"default": "sk-", "tooltip": "Tikpan 平台的 API 密钥，以 sk- 开头，从 https://tikpan.com 获取"}),
                "首帧图": ("IMAGE", {"tooltip": "1.5 preview 必填：作为视频第一帧/图像提示"}),
                "生成指令": ("STRING", {"multiline": True, "default": cls.DEFAULT_PROMPT, "tooltip": "描述图片要动起来的方式、镜头、节奏和声音氛围"}),
                "模型": ([cls.MODEL_ID], {"default": cls.MODEL_ID, "tooltip": "本节点固定使用 grok-imagine-video-1.5-preview"}),
                "分辨率": (GROK_IMAGINE_VIDEO_RESOLUTION_OPTIONS, {"default": "480p", "tooltip": "选择 480p 或 720p；720p 输出按秒计费更高"}),
                "画面比例": (GROK_ASPECT_OPTIONS, {"default": GROK_ASPECT_OPTIONS[0], "tooltip": "画面比例参数"}),
                "随机种子": ("INT", {"default": 888888, "min": 0, "max": 2147483647, "step": 1, "tooltip": "固定种子便于复现；旧工作流的 -1 会自动规范化"}),
            },
            "optional": {
                "中转站地址": (API_HOST_OPTIONS, {"default": API_HOST_OPTIONS[0], "tooltip": "Tikpan 中转站地址，一般保持默认即可"}),
                "最长等待秒数": ("INT", {"default": 1200, "min": 60, "max": 7200, "step": 30, "tooltip": "等待视频生成完成的最长秒数"}),
                "查询间隔秒数": ("INT", {"default": 8, "min": 5, "max": 60, "step": 1, "tooltip": "轮询任务状态的间隔秒数"}),
                "校验HTTPS证书": ("BOOLEAN", {"default": False, "tooltip": "默认关闭以兼容部分网络；遇到 SSL 问题可保持关闭"}),
                "跳过错误": ("BOOLEAN", {"default": False, "tooltip": "开启后异常时返回空，不打断后续工作流"}),
            },
        }

    def prepare_payload(self, kwargs, prompt, resolution, aspect_ratio, seed):
        first_frame = pick(kwargs, "首帧图", "first_frame_image", default=None)
        if first_frame is None:
            raise ValueError("Grok Imagine Video 1.5 Preview 需要连接 首帧图。")
        payload = self.build_payload(
            model=self.MODEL_ID,
            prompt=prompt,
            resolution=resolution,
            aspect_ratio=aspect_ratio,
            seed=seed,
            mode="first_frame",
            first_frame_image=self.tensor_to_data_url(first_frame),
        )
        return payload, "/v1/videos/generations"


NODE_CLASS_MAPPINGS = {
    "TikpanGrokImagineVideoNode": TikpanGrokImagineVideoNode,
    "TikpanGrokImagineVideo15PreviewNode": TikpanGrokImagineVideo15PreviewNode,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "TikpanGrokImagineVideoNode": "视频｜Grok Imagine Video 音视频生成/编辑",
    "TikpanGrokImagineVideo15PreviewNode": "视频｜Grok Imagine Video 1.5 Preview 首帧生视频",
}
