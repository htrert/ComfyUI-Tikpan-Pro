from .tikpan_categories import CATEGORY_VIDEO
import json
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
from .tikpan_node_options import API_HOST_OPTIONS, normalize_api_host, option_value, pick


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

KLING_MODEL_OPTIONS = [
    "Kling v2.5 Turbo 性价比｜kling-v2-5-turbo",
    "Kling v2.6 新版｜kling-v2-6",
    "Kling v3 最新｜kling-v3",
]
KLING_MODE_OPTIONS = ["标准模式｜std", "高质量模式｜pro"]
KLING_DURATION_OPTIONS = ["5秒｜5", "10秒｜10"]
KLING_ASPECT_OPTIONS = ["16:9 横屏｜16:9", "9:16 竖屏｜9:16", "1:1 方形｜1:1"]


class _TikpanKlingVideoBase:
    CATEGORY = CATEGORY_VIDEO
    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "VIDEO")
    RETURN_NAMES = ("📁_本地保存路径", "🆔_任务ID", "🔗_视频云端直链", "📄_完整日志", "🎬_视频输出")
    OUTPUT_NODE = True

    def create_session(self):
        session = requests.Session()
        session.trust_env = False
        retry = Retry(total=3, connect=3, read=1, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=frozenset(["GET", "POST"]), raise_on_status=False)
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def headers(self, api_key, json_content=True):
        headers = {"Authorization": f"Bearer {api_key}", "User-Agent": "Tikpan-ComfyUI-KlingVideo/1.0"}
        if json_content:
            headers.update({"Content-Type": "application/json", "Accept": "application/json"})
        return headers

    def build_text_payload(self, model_name, prompt, mode, duration, aspect_ratio, negative_prompt="", cfg_scale=None, sound=False, camera_control=""):
        payload = {
            "model_name": model_name,
            "prompt": prompt,
            "mode": mode,
            "duration": int(duration),
            "aspect_ratio": aspect_ratio,
        }
        self.add_optional_fields(payload, negative_prompt, cfg_scale, sound, camera_control)
        return payload

    def build_image_payload(self, model_name, prompt, image, mode, duration, aspect_ratio="", image_tail="", negative_prompt="", cfg_scale=None, sound=False, camera_control=""):
        payload = {
            "model_name": model_name,
            "prompt": prompt,
            "image": image,
            "mode": mode,
            "duration": int(duration),
        }
        if image_tail:
            payload["image_tail"] = image_tail
        if aspect_ratio:
            payload["aspect_ratio"] = aspect_ratio
        self.add_optional_fields(payload, negative_prompt, cfg_scale, sound, camera_control)
        return payload

    def add_optional_fields(self, payload, negative_prompt, cfg_scale, sound, camera_control):
        if negative_prompt:
            payload["negative_prompt"] = str(negative_prompt)
        if cfg_scale is not None:
            try:
                payload["cfg_scale"] = float(cfg_scale)
            except Exception:
                pass
        if sound:
            payload["sound"] = "on"
        camera = self.parse_camera_control(camera_control)
        if camera:
            payload["camera_control"] = camera

    def parse_camera_control(self, value):
        text = str(value or "").strip()
        if not text:
            return {}
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("相机控制JSON必须是对象")
        return parsed

    def tensor_to_jpeg_bytes(self, img_tensor, quality=92):
        if len(img_tensor.shape) == 4:
            img_tensor = img_tensor[0]
        arr = 255.0 * img_tensor.detach().cpu().numpy()
        image = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGB")
        buf = BytesIO()
        image.save(buf, format="JPEG", quality=int(quality), optimize=True)
        return buf.getvalue()

    def upload_image(self, session, api_host, api_key, img_tensor, verify_tls, filename, pbar=None, progress=18):
        img_bytes = self.tensor_to_jpeg_bytes(img_tensor)
        if len(img_bytes) > 12 * 1024 * 1024:
            raise RuntimeError(f"图片过大：{len(img_bytes) / 1024 / 1024:.1f}MB，建议压缩到 12MB 内。")
        return self.upload_file(session, api_host, api_key, filename, img_bytes, "image/jpeg", verify_tls, pbar, progress)

    def upload_file(self, session, api_host, api_key, filename, file_bytes, mime, verify_tls, pbar=None, progress=18):
        files = {"file": (filename, file_bytes, mime)}
        endpoints = [f"{api_host}/alibailian/api/v1/upload", f"{api_host}/v1/upload", f"{api_host}/upload"]
        last_error = ""
        for endpoint in endpoints:
            try:
                print(f"[Tikpan-KlingVideo] 上传文件到: {endpoint}", flush=True)
                resp = session.post(endpoint, headers=self.headers(api_key, json_content=False), files=files, timeout=(20, 600), verify=verify_tls)
                if resp.status_code >= 400:
                    last_error = f"HTTP {resp.status_code}: {self.safe_text(resp.text)}"
                    continue
                res_json = resp.json()
                url = res_json.get("url") or (res_json.get("data") or {}).get("url") or (res_json.get("result") or {}).get("url") or res_json.get("filename")
                if url:
                    if not str(url).startswith(("http://", "https://")):
                        url = f"{api_host}/{str(url).lstrip('/')}"
                    if pbar:
                        pbar.update_absolute(progress, 100)
                    return str(url)
                last_error = f"上传成功但未返回 URL: {json.dumps(res_json, ensure_ascii=False)[:500]}"
            except Exception as exc:
                last_error = str(exc)
        raise RuntimeError(f"文件上传失败: {last_error}")

    def submit_and_wait(self, session, api_host, endpoint, query_endpoint, payload, api_key, max_wait, poll_interval, verify_tls, prefix, pbar):
        response = session.post(f"{api_host}{endpoint}", json=payload, headers=self.headers(api_key), timeout=(20, 120), verify=verify_tls)
        if response.status_code >= 400:
            raise RuntimeError(f"任务创建失败: HTTP {response.status_code}\n{self.safe_text(response.text)}")
        create_json = response.json()
        task_id = self.extract_task_id(create_json)
        video_url = extract_video_url(create_json)
        if not video_url and not task_id:
            raise RuntimeError(f"任务创建失败：未获取到任务ID\n{json.dumps(create_json, ensure_ascii=False)[:1500]}")
        final_json = create_json
        if not video_url:
            ok, result, final_json = self.poll_task(session, api_host, query_endpoint, task_id, api_key, max_wait, poll_interval, verify_tls, pbar)
            if not ok:
                raise RuntimeError(result)
            video_url = result
        save_path = self.download_video(session, video_url, prefix, task_id or "sync", verify_tls)
        return task_id or "sync", video_url, save_path, final_json

    def poll_task(self, session, api_host, query_endpoint, task_id, api_key, max_wait, poll_interval, verify_tls, pbar):
        query_urls = [
            f"{api_host}{query_endpoint}/{task_id}",
            f"{api_host}{query_endpoint}?task_id={task_id}",
            f"{api_host}/v1/videos/{task_id}",
            f"{api_host}/v1/videos/query?id={task_id}",
        ]
        start = time.time()
        poll_count = 0
        last_json = {}
        while time.time() - start < max_wait:
            comfy.model_management.throw_exception_if_processing_interrupted()
            time.sleep(poll_interval)
            poll_count += 1
            for url in query_urls:
                try:
                    resp = session.get(url, headers=self.headers(api_key), timeout=(15, 45), verify=verify_tls)
                    if resp.status_code in {404, 405}:
                        continue
                    if resp.status_code >= 400:
                        continue
                    res_json = resp.json()
                    last_json = res_json
                    status = extract_task_status(res_json)
                    output = extract_task_output(res_json)
                    elapsed = int(time.time() - start)
                    if pbar:
                        pbar.update_absolute(min(85, 25 + int(elapsed * 55 / max(max_wait, 1))), 100)
                    print(f"[Tikpan-KlingVideo] 轮询 {poll_count} | status={status or 'unknown'} | url={url}", flush=True)
                    video_url = extract_video_url(res_json)
                    if is_success_status(status):
                        if video_url:
                            return True, video_url, res_json
                        return False, "❌ 任务成功但响应中没有视频链接", res_json
                    if is_failure_status(status):
                        return False, f"❌ 任务失败: {extract_error_message(output)}", res_json
                    if video_url and not status:
                        return True, video_url, res_json
                    break
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

    def safe_text(self, value, max_len=1000):
        try:
            return str(value or "")[:max_len].strip()
        except Exception:
            return ""

    def error_return(self, message, skip_error=False, task_id="", video_url=""):
        if not skip_error:
            raise RuntimeError(message)
        return ("", task_id, video_url, message, None)

    def read_common(self, kwargs):
        api_key = str(pick(kwargs, "API_密钥", "api_key", default="") or "").strip()
        api_host = normalize_api_host(pick(kwargs, "中转站地址", "api_host", default=API_HOST_OPTIONS[0]))
        skip_error = bool(pick(kwargs, "跳过错误", "skip_error", default=False))
        verify_tls = bool(pick(kwargs, "校验HTTPS证书", "verify_tls", default=False))
        max_wait = int(pick(kwargs, "最长等待秒数", "max_wait_seconds", default=1200) or 1200)
        poll_interval = int(pick(kwargs, "查询间隔秒数", "poll_interval", default=8) or 8)
        if not api_key or api_key == "sk-" or len(api_key) < 10:
            raise RuntimeError("❌ 请填写有效的 API 密钥")
        return api_key, api_host, skip_error, verify_tls, max_wait, poll_interval

    def handle_exception(self, label, exc, kwargs, task_id, video_url):
        tb = traceback.format_exc()
        msg = f"❌ {label}异常: {exc}\n{tb[:2000]}"
        print(f"[Tikpan-KlingVideo] {msg}", flush=True)
        skip_error = bool(pick(kwargs, "跳过错误", "skip_error", default=False))
        if not skip_error:
            raise RuntimeError(msg) from exc
        return ("", task_id, video_url, msg, None)


class TikpanKlingText2VideoNode(_TikpanKlingVideoBase):
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "💰_福利_💰": (["🔥 0.6元RMB兑1美元余额 | 全网底价 👉 https://tikpan.com"],),
                "获取密钥请访问": (["👉 https://tikpan.com (官方授权Key获取点)"],),
                "API_密钥": ("STRING", {"default": "sk-", "tooltip": "Tikpan 平台的 API 密钥，以 sk- 开头，从 https://tikpan.com 获取"}),
                "模型版本": (KLING_MODEL_OPTIONS, {"default": KLING_MODEL_OPTIONS[0], "tooltip": "默认 v2.5 turbo，性价比优先"}),
                "生成指令": ("STRING", {"multiline": True, "default": "A cinematic product video with smooth motion, realistic lighting, high quality.", "tooltip": "描述视频画面、动作、镜头和风格"}),
                "模式": (KLING_MODE_OPTIONS, {"default": KLING_MODE_OPTIONS[0], "tooltip": "std 标准更快更省；pro 更高质量"}),
                "视频时长": (KLING_DURATION_OPTIONS, {"default": KLING_DURATION_OPTIONS[0], "tooltip": "Kling duration 参数"}),
                "画面比例": (KLING_ASPECT_OPTIONS, {"default": KLING_ASPECT_OPTIONS[0], "tooltip": "Kling aspect_ratio 参数"}),
            },
            "optional": {
                "负向提示词": ("STRING", {"multiline": True, "default": "", "tooltip": "不希望出现的内容，留空则不传"}),
                "CFG Scale": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.05, "tooltip": "Kling cfg_scale 参数"}),
                "生成声音": ("BOOLEAN", {"default": False, "tooltip": "开启后发送 sound=on，可能增加耗时/费用"}),
                "相机控制JSON": ("STRING", {"multiline": True, "default": "", "tooltip": "可选，传入 Kling camera_control JSON 对象"}),
                "中转站地址": (API_HOST_OPTIONS, {"default": API_HOST_OPTIONS[0], "tooltip": "Tikpan 中转站地址，一般保持默认即可"}),
                "最长等待秒数": ("INT", {"default": 1200, "min": 60, "max": 7200, "step": 30, "tooltip": "等待视频生成完成的最长秒数"}),
                "查询间隔秒数": ("INT", {"default": 8, "min": 5, "max": 60, "step": 1, "tooltip": "轮询任务状态的间隔秒数"}),
                "校验HTTPS证书": ("BOOLEAN", {"default": False, "tooltip": "默认关闭以兼容部分网络"}),
                "跳过错误": ("BOOLEAN", {"default": False, "tooltip": "开启后异常时返回空，不打断后续工作流"}),
            },
        }

    FUNCTION = "generate_text_video"
    DESCRIPTION = "📝 Kling 文生视频：支持 v2.5 turbo、v2.6、v3，默认性价比模式。"

    def generate_text_video(self, **kwargs):
        pbar = comfy.utils.ProgressBar(100)
        task_id = ""
        video_url = ""
        try:
            api_key, api_host, skip_error, verify_tls, max_wait, poll_interval = self.read_common(kwargs)
            prompt = str(pick(kwargs, "生成指令", "prompt", default="") or "").strip()
            if not prompt:
                return self.error_return("❌ 生成指令不能为空", skip_error)
            payload = self.build_text_payload(
                model_name=option_value(pick(kwargs, "模型版本", "model_name", default=KLING_MODEL_OPTIONS[0]), "kling-v2-5-turbo"),
                prompt=prompt,
                mode=option_value(pick(kwargs, "模式", "mode", default=KLING_MODE_OPTIONS[0]), "std"),
                duration=option_value(pick(kwargs, "视频时长", "duration", default=KLING_DURATION_OPTIONS[0]), "5"),
                aspect_ratio=option_value(pick(kwargs, "画面比例", "aspect_ratio", default=KLING_ASPECT_OPTIONS[0]), "16:9"),
                negative_prompt=str(pick(kwargs, "负向提示词", "negative_prompt", default="") or "").strip(),
                cfg_scale=pick(kwargs, "CFG Scale", "cfg_scale", default=0.5),
                sound=bool(pick(kwargs, "生成声音", "sound", default=False)),
                camera_control=pick(kwargs, "相机控制JSON", "camera_control", default=""),
            )
            session = self.create_session()
            pbar.update_absolute(20, 100)
            task_id, video_url, save_path, final_json = self.submit_and_wait(session, api_host, "/kling/v1/videos/text2video", "/kling/v1/videos/text2video", payload, api_key, max_wait, poll_interval, verify_tls, "Tikpan_Kling_T2V", pbar)
            pbar.update_absolute(100, 100)
            log = f"✅ Kling 文生视频成功\ntask_id={task_id}\nvideo_url={video_url}\npath={save_path}\n\n{json.dumps(final_json, ensure_ascii=False, indent=2)[:2500]}"
            return (save_path, task_id, video_url, log, video_from_path(save_path))
        except Exception as exc:
            return self.handle_exception("Kling 文生视频", exc, kwargs, task_id, video_url)


class TikpanKlingImage2VideoNode(_TikpanKlingVideoBase):
    @classmethod
    def INPUT_TYPES(cls):
        inputs = TikpanKlingText2VideoNode.INPUT_TYPES()
        required = dict(inputs["required"])
        required["首帧图"] = ("IMAGE", {"tooltip": "Kling image2video 必填首帧图"})
        optional = dict(inputs["optional"])
        optional["尾帧图"] = ("IMAGE", {"tooltip": "可选尾帧图，会发送 image_tail"})
        return {"required": required, "optional": optional}

    FUNCTION = "generate_image_video"
    DESCRIPTION = "📝 Kling 图生视频：支持首帧和可选尾帧，默认 v2.5 turbo 性价比模式。"

    def generate_image_video(self, **kwargs):
        pbar = comfy.utils.ProgressBar(100)
        task_id = ""
        video_url = ""
        try:
            api_key, api_host, skip_error, verify_tls, max_wait, poll_interval = self.read_common(kwargs)
            prompt = str(pick(kwargs, "生成指令", "prompt", default="") or "").strip()
            first_frame = pick(kwargs, "首帧图", "image", default=None)
            if first_frame is None:
                return self.error_return("❌ 请连接首帧图", skip_error)
            if not prompt:
                return self.error_return("❌ 生成指令不能为空", skip_error)
            session = self.create_session()
            image_url = self.upload_image(session, api_host, api_key, first_frame, verify_tls, "kling_i2v_first.jpg", pbar, 15)
            tail_tensor = pick(kwargs, "尾帧图", "image_tail", default=None)
            tail_url = self.upload_image(session, api_host, api_key, tail_tensor, verify_tls, "kling_i2v_tail.jpg", pbar, 22) if tail_tensor is not None else ""
            payload = self.build_image_payload(
                model_name=option_value(pick(kwargs, "模型版本", "model_name", default=KLING_MODEL_OPTIONS[0]), "kling-v2-5-turbo"),
                prompt=prompt,
                image=image_url,
                mode=option_value(pick(kwargs, "模式", "mode", default=KLING_MODE_OPTIONS[0]), "std"),
                duration=option_value(pick(kwargs, "视频时长", "duration", default=KLING_DURATION_OPTIONS[0]), "5"),
                aspect_ratio=option_value(pick(kwargs, "画面比例", "aspect_ratio", default=KLING_ASPECT_OPTIONS[0]), "16:9"),
                image_tail=tail_url,
                negative_prompt=str(pick(kwargs, "负向提示词", "negative_prompt", default="") or "").strip(),
                cfg_scale=pick(kwargs, "CFG Scale", "cfg_scale", default=0.5),
                sound=bool(pick(kwargs, "生成声音", "sound", default=False)),
                camera_control=pick(kwargs, "相机控制JSON", "camera_control", default=""),
            )
            task_id, video_url, save_path, final_json = self.submit_and_wait(session, api_host, "/kling/v1/videos/image2video", "/kling/v1/videos/image2video", payload, api_key, max_wait, poll_interval, verify_tls, "Tikpan_Kling_I2V", pbar)
            pbar.update_absolute(100, 100)
            log = f"✅ Kling 图生视频成功\ntask_id={task_id}\nvideo_url={video_url}\npath={save_path}\n首帧图={image_url}\n尾帧图={tail_url}\n\n{json.dumps(final_json, ensure_ascii=False, indent=2)[:2500]}"
            return (save_path, task_id, video_url, log, video_from_path(save_path))
        except Exception as exc:
            return self.handle_exception("Kling 图生视频", exc, kwargs, task_id, video_url)

NODE_CLASS_MAPPINGS = {
    "TikpanKlingText2VideoNode": TikpanKlingText2VideoNode,
    "TikpanKlingImage2VideoNode": TikpanKlingImage2VideoNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TikpanKlingText2VideoNode": "视频｜Kling 文生视频",
    "TikpanKlingImage2VideoNode": "视频｜Kling 图生视频",
}
