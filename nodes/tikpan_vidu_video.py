from .tikpan_categories import CATEGORY_VIDEO
import base64
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

from .tikpan_happyhorse_common import video_from_path
from .tikpan_node_options import API_HOST_OPTIONS, normalize_api_host, normalize_seed, pick


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

VIDU_RESOLUTION_OPTIONS = ["540p", "720p", "1080p"]
VIDU_ASPECT_OPTIONS = ["16:9", "9:16", "1:1", "4:3", "3:4"]
VIDU_MOVEMENT_OPTIONS = ["auto", "small", "medium", "large"]
VIDU_AUDIO_TYPE_OPTIONS = ["All", "Speech_only", "Sound-effect_only"]


class _TikpanViduBase:
    CATEGORY = CATEGORY_VIDEO
    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "VIDEO")
    RETURN_NAMES = ("📁_本地保存路径", "🆔_任务ID", "🔗_视频云端直链", "📄_完整日志", "🎬_视频输出")
    OUTPUT_NODE = True

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

    def tensor_to_data_url(self, img_tensor, quality=92):
        if img_tensor is None:
            raise ValueError("图片输入为空")
        if len(img_tensor.shape) == 4:
            img_tensor = img_tensor[0]
        arr = 255.0 * img_tensor.detach().cpu().numpy()
        arr = np.clip(arr, 0, 255).astype(np.uint8)
        image = Image.fromarray(arr).convert("RGB")
        width, height = image.size
        if width < 128 or height < 128:
            raise ValueError(f"图片尺寸过小：{width}x{height}，Vidu 要求至少 128x128")
        ratio = max(width / height, height / width)
        if ratio > 4:
            raise ValueError(f"图片比例过于极端：{width}x{height}，Vidu 要求小于 1:4 或 4:1")
        buf = BytesIO()
        image.save(buf, format="JPEG", quality=int(quality), optimize=True)
        image_bytes = buf.getvalue()
        if len(image_bytes) > 18 * 1024 * 1024:
            raise ValueError(f"图片编码后过大：{len(image_bytes) / 1024 / 1024:.1f}MB，建议压缩后重试")
        return "data:image/jpeg;base64," + base64.b64encode(image_bytes).decode("utf-8")

    def collect_image_inputs(self, kwargs, prefix, count):
        images = []
        for index in range(1, count + 1):
            tensor = pick(kwargs, f"{prefix}{index}", f"{prefix}_{index}", default=None)
            if tensor is not None:
                images.append(self.tensor_to_data_url(tensor))
        return images

    def build_common_payload(self, model, prompt, duration, resolution, seed, movement, off_peak, audio, audio_type):
        payload = {
            "model": model,
            "prompt": prompt,
            "duration": int(duration),
            "resolution": resolution,
            "off_peak": bool(off_peak),
        }
        if seed is not None:
            payload["seed"] = int(seed) % 2147483647
        if movement:
            payload["movement_amplitude"] = movement
        payload["audio"] = bool(audio)
        if audio:
            payload["audio_type"] = audio_type
        return payload

    def headers(self, api_key):
        # Tikpan usually accepts Bearer; official Vidu uses Token. Send both-compatible raw auth is not possible in one header,
        # so keep Bearer for Tikpan relay and let the relay translate upstream if needed.
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Tikpan-ComfyUI-Vidu/1.0",
        }

    def submit_and_wait(self, session, api_host, endpoint, payload, api_key, max_wait, poll_interval, verify_tls, pbar):
        safe_payload = self.redact_payload(payload)
        print(f"[Tikpan-Vidu] POST {endpoint} | payload={json.dumps(safe_payload, ensure_ascii=False)[:1400]}", flush=True)
        response = session.post(
            f"{api_host}{endpoint}",
            json=payload,
            headers=self.headers(api_key),
            timeout=(20, 120),
            verify=verify_tls,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"任务创建失败: HTTP {response.status_code}\n{self.safe_text(response.text)}")
        try:
            create_json = response.json()
        except Exception as exc:
            raise RuntimeError(f"任务创建失败：返回不是合法 JSON\n{self.safe_text(response.text)}") from exc

        task_id = self.extract_task_id(create_json)
        if not task_id:
            video_url = self.extract_video_url(create_json)
            if video_url:
                return "sync", video_url, create_json
            raise RuntimeError(f"任务创建失败：未获取到 task_id\n{json.dumps(create_json, ensure_ascii=False)[:1500]}")

        if pbar:
            pbar.update_absolute(25, 100)
        ok, result, final_json = self.poll_task(session, api_host, task_id, api_key, max_wait, poll_interval, verify_tls, pbar)
        if not ok:
            raise RuntimeError(result)
        return task_id, result, final_json

    def poll_task(self, session, api_host, task_id, api_key, max_wait, poll_interval, verify_tls, pbar):
        urls = [
            f"{api_host}/ent/v2/tasks/{task_id}/creations",
            f"{api_host}/vidu/ent/v2/tasks/{task_id}/creations",
            f"{api_host}/v1/videos/{task_id}",
            f"{api_host}/v1/videos/query?id={task_id}",
        ]
        start = time.time()
        poll_count = 0
        last_json = {}
        headers = self.headers(api_key)
        while time.time() - start < max_wait:
            comfy.model_management.throw_exception_if_processing_interrupted()
            time.sleep(poll_interval)
            poll_count += 1
            for url in urls:
                try:
                    resp = session.get(url, headers=headers, timeout=(15, 45), verify=verify_tls)
                    if resp.status_code in {404, 405}:
                        continue
                    if resp.status_code >= 400:
                        continue
                    res_json = resp.json()
                    last_json = res_json
                    state = str(res_json.get("state") or res_json.get("status") or "").lower()
                    elapsed = int(time.time() - start)
                    if pbar:
                        pbar.update_absolute(min(88, 25 + int(elapsed * 60 / max(max_wait, 1))), 100)
                    print(f"[Tikpan-Vidu] 轮询 {poll_count} | state={state or 'unknown'} | {url}", flush=True)
                    if state in {"success", "succeeded", "completed", "done", "finished"}:
                        video_url = self.extract_video_url(res_json)
                        if video_url:
                            return True, video_url, res_json
                        return False, "任务成功但响应中未找到视频 URL", res_json
                    if state in {"failed", "fail", "error", "canceled", "cancelled"}:
                        return False, f"任务失败: {self.extract_error(res_json)}", res_json
                    video_url = self.extract_video_url(res_json)
                    if video_url and not state:
                        return True, video_url, res_json
                    break
                except Exception:
                    continue
        return False, f"轮询超时：任务仍在处理中 | task_id={task_id}", last_json

    def download_video(self, session, video_url, prefix, task_id, verify_tls):
        resp = session.get(video_url, timeout=(20, 600), verify=verify_tls)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")
        if not resp.content or len(resp.content) < 1024:
            raise RuntimeError(f"视频下载内容为空或过小: {len(resp.content) if resp.content else 0} bytes")
        if "text/html" in content_type.lower() or resp.content[:20].lstrip().lower().startswith(b"<!doctype"):
            raise RuntimeError(f"视频链接返回 HTML，不是视频文件: {self.safe_text(resp.text)}")
        safe_id = str(task_id or int(time.time())).replace("/", "_").replace(":", "_")
        out_dir = folder_paths.get_output_directory()
        save_path = os.path.join(out_dir, f"{prefix}_{safe_id}.mp4")
        with open(save_path, "wb") as f:
            f.write(resp.content)
        return save_path

    def extract_task_id(self, data):
        if not isinstance(data, dict):
            return ""
        for obj in (data, data.get("data"), data.get("result"), data.get("output")):
            if isinstance(obj, dict):
                value = obj.get("task_id") or obj.get("taskId") or obj.get("id")
                if value:
                    return str(value)
            elif isinstance(obj, str) and obj.strip():
                return obj.strip()
        return ""

    def redact_payload(self, payload):
        def redact(value):
            if isinstance(value, str) and value.startswith("data:image"):
                return "[data:image omitted]"
            if isinstance(value, list):
                return [redact(item) for item in value]
            if isinstance(value, dict):
                return {key: redact(child) for key, child in value.items()}
            return value

        safe = redact(dict(payload))
        if isinstance(payload.get("subjects"), list):
            safe["subjects"] = [
                {
                    "name": item.get("name", f"subject_{idx}"),
                    "images": f"{len(item.get('images', []))} image(s)",
                }
                if isinstance(item, dict)
                else "[subject omitted]"
                for idx, item in enumerate(payload.get("subjects", []), start=1)
            ]
        return safe

    def extract_video_url(self, obj):
        if isinstance(obj, dict):
            creations = obj.get("creations")
            if isinstance(creations, list):
                for item in creations:
                    found = self.extract_video_url(item)
                    if found:
                        return found
            for key in ("url", "video_url", "videoUrl", "output_url", "result_url", "file_url", "media_url"):
                value = obj.get(key)
                if isinstance(value, str) and value.startswith(("http://", "https://")):
                    return value
            for value in obj.values():
                found = self.extract_video_url(value)
                if found:
                    return found
        elif isinstance(obj, list):
            for item in obj:
                found = self.extract_video_url(item)
                if found:
                    return found
        return ""

    def extract_error(self, data):
        if not isinstance(data, dict):
            return str(data)
        return (
            data.get("message")
            or data.get("error")
            or data.get("err_code")
            or data.get("reason")
            or json.dumps(data, ensure_ascii=False)[:1000]
        )

    def safe_text(self, value, max_len=1000):
        try:
            return str(value or "")[:max_len].strip()
        except Exception:
            return ""

    def error_return(self, message, skip_error=False, task_id="", video_url=""):
        if not skip_error:
            raise RuntimeError(message)
        return ("", task_id, video_url, message, None)


class TikpanVidu3ReferenceVideoNode(_TikpanViduBase):
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "💰_福利_💰": (["🔥 0.6元RMB兑1美元余额 | 全网底价 👉 https://tikpan.com"],),
                "获取密钥请访问": (["👉 https://tikpan.com (官方授权Key获取点)"],),
                "API_密钥": ("STRING", {"default": "sk-", "tooltip": "Tikpan 平台的 API 密钥，以 sk- 开头，从 https://tikpan.com 获取"}),
                "生成指令": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "@1 appears in a cinematic commercial video, natural motion, stable identity, high quality.",
                        "tooltip": "用 @1/@2/... 引用对应序号的参考图；越具体的画面/动作描述效果越好，推荐英文",
                    },
                ),
                "参考图1": ("IMAGE", {"tooltip": "必填的主参考图，对应提示词中的 @1"}),
                "视频时长": ("INT", {"default": 5, "min": 3, "max": 16, "step": 1, "tooltip": "生成视频秒数，越长越慢越贵"}),
                "清晰度": (VIDU_RESOLUTION_OPTIONS, {"default": "720p", "tooltip": "视频分辨率：越高越清晰但更慢更贵"}),
                "画面比例": (VIDU_ASPECT_OPTIONS, {"default": "16:9", "tooltip": "Vidu endpoint 的 aspect_ratio 参数"}),
            },
            "optional": {
                "参考图2": ("IMAGE", {"tooltip": "可选第 2 张参考图，对应 @2"}),
                "参考图3": ("IMAGE", {"tooltip": "可选第 3 张参考图，对应 @3"}),
                "参考图4": ("IMAGE", {"tooltip": "可选第 4 张参考图，对应 @4"}),
                "参考图5": ("IMAGE", {"tooltip": "可选第 5 张参考图，对应 @5"}),
                "参考图6": ("IMAGE", {"tooltip": "可选第 6 张参考图，对应 @6"}),
                "参考图7": ("IMAGE", {"tooltip": "可选第 7 张参考图，对应 @7"}),
                "智能主体库": ("BOOLEAN", {"default": False, "tooltip": "Vidu reference2video 的 auto_subjects 参数"}),
                "音画同步": ("BOOLEAN", {"default": True, "tooltip": "是否生成与画面匹配的环境音/配乐"}),
                "音频类型": (VIDU_AUDIO_TYPE_OPTIONS, {"default": "All", "tooltip": "限定生成的音频类型（环境音/对白/全部）"}),
                "错峰生成": ("BOOLEAN", {"default": False, "tooltip": "Vidu off_peak 参数；开启后任务可能延迟出片"}),
                "最长等待秒数": ("INT", {"default": 1200, "min": 60, "max": 7200, "step": 30, "tooltip": "本地轮询等待最长秒数，不会传给上游模型"}),
                "查询间隔秒数": ("INT", {"default": 8, "min": 5, "max": 60, "step": 1, "tooltip": "本地轮询任务状态的间隔秒数"}),
                "校验HTTPS证书": ("BOOLEAN", {"default": False, "tooltip": "本地网络参数：控制 requests 是否校验证书，不会传给上游模型"}),
                "跳过错误": ("BOOLEAN", {"default": False, "tooltip": "开启后异常时返回空，不打断后续工作流"}),
            },
        }

    FUNCTION = "generate_reference_video"
    DESCRIPTION = "📝 Vidu3 参考生视频：使用 Tikpan /ent/v2/reference2video，UI 隐藏未确认可复现的 seed，保留 Vidu 文档参数和本地轮询参数。"

    def generate_reference_video(self, **kwargs):
        pbar = comfy.utils.ProgressBar(100)
        task_id = ""
        video_url = ""
        try:
            api_key = str(pick(kwargs, "API_密钥", "api_key", default="") or "").strip()
            api_host = normalize_api_host(pick(kwargs, "中转站地址", "api_host", default=API_HOST_OPTIONS[0]))
            skip_error = bool(pick(kwargs, "跳过错误", "skip_error", default=False))
            verify_tls = bool(pick(kwargs, "校验HTTPS证书", "verify_tls", default=False))
            prompt = str(pick(kwargs, "生成指令", "prompt", default="") or "").strip()
            duration = int(pick(kwargs, "视频时长", "duration", default=5) or 5)
            resolution = str(pick(kwargs, "清晰度", "resolution", default="720p") or "720p")
            aspect_ratio = str(pick(kwargs, "画面比例", "aspect_ratio", default="16:9") or "16:9")
            seed_value = pick(kwargs, "随机种子", "seed", default=None)
            seed = normalize_seed(seed_value, default=888888) if seed_value is not None else None
            audio = bool(pick(kwargs, "音画同步", "audio", default=True))
            audio_type = str(pick(kwargs, "音频类型", "audio_type", default="All") or "All")
            off_peak = bool(pick(kwargs, "错峰生成", "off_peak", default=False))
            max_wait = int(pick(kwargs, "最长等待秒数", "max_wait_seconds", default=1200) or 1200)
            poll_interval = int(pick(kwargs, "查询间隔秒数", "poll_interval", default=8) or 8)
            auto_subjects = bool(pick(kwargs, "智能主体库", "auto_subjects", default=False))

            if not api_key or api_key == "sk-" or len(api_key) < 10:
                return self.error_return("❌ 请填写有效的 API 密钥", skip_error)
            if not prompt:
                return self.error_return("❌ 生成指令不能为空", skip_error)
            images = self.collect_image_inputs(kwargs, "参考图", 7)
            if not images:
                return self.error_return("❌ vidu3 参考生视频至少需要 1 张参考图", skip_error)

            pbar.update_absolute(8, 100)
            subjects = [{"name": f"subject_{idx}", "images": [image]} for idx, image in enumerate(images, start=1)]
            payload = self.build_common_payload("viduq3", prompt, duration, resolution, seed, "", off_peak, audio, audio_type)
            payload.update(
                {
                    "aspect_ratio": aspect_ratio,
                    "auto_subjects": auto_subjects,
                    "subjects": subjects,
                }
            )
            session = self.create_session()
            task_id, video_url, final_json = self.submit_and_wait(
                session, api_host, "/ent/v2/reference2video", payload, api_key, max_wait, poll_interval, verify_tls, pbar
            )
            pbar.update_absolute(92, 100)
            save_path = self.download_video(session, video_url, "Tikpan_Vidu3_Reference", task_id, verify_tls)
            pbar.update_absolute(100, 100)
            log = (
                f"✅ Vidu3 参考生视频成功 | model=viduq3 | refs={len(images)} | duration={duration}s | "
                f"resolution={resolution} | aspect_ratio={aspect_ratio} | audio={audio}\n"
                f"task_id={task_id}\nvideo_url={video_url}\npath={save_path}\n\n"
                f"{json.dumps(final_json, ensure_ascii=False, indent=2)[:2500]}"
            )
            return (save_path, task_id, video_url, log, video_from_path(save_path))
        except Exception as exc:
            tb = traceback.format_exc()
            msg = f"❌ Vidu3 参考生视频异常: {exc}\n{tb[:2000]}"
            print(f"[Tikpan-Vidu3] {msg}", flush=True)
            skip_error = bool(pick(kwargs, "跳过错误", "skip_error", default=False))
            if not skip_error:
                raise RuntimeError(msg) from exc
            return ("", task_id, video_url, msg, None)


class TikpanVidu3TurboVideoNode(_TikpanViduBase):
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "💰_福利_💰": (["🔥 0.6元RMB兑1美元余额 | 全网底价 👉 https://tikpan.com"],),
                "获取密钥请访问": (["👉 https://tikpan.com (官方授权Key获取点)"],),
                "API_密钥": ("STRING", {"default": "sk-", "tooltip": "Tikpan 平台的 API 密钥，以 sk- 开头，从 https://tikpan.com 获取"}),
                "生成模式": (["文生视频｜text2video", "图生视频｜img2video", "首尾帧｜start-end2video"], {"default": "文生视频｜text2video", "tooltip": "三种模式：纯文字、首帧图驱动、首尾帧双图驱动"}),
                "生成指令": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "A cinematic product video with stable camera movement, realistic lighting, and smooth motion.",
                        "tooltip": "描述视频画面/动作/氛围，推荐英文",
                    },
                ),
                "视频时长": ("INT", {"default": 5, "min": 1, "max": 16, "step": 1, "tooltip": "生成视频秒数；越长越慢越贵"}),
                "清晰度": (VIDU_RESOLUTION_OPTIONS, {"default": "720p", "tooltip": "视频分辨率：越高越清晰但更慢更贵"}),
                "画面比例": (VIDU_ASPECT_OPTIONS, {"default": "16:9", "tooltip": "Vidu endpoint 的 aspect_ratio 参数"}),
            },
            "optional": {
                "首帧图": ("IMAGE", {"tooltip": "图生视频/首尾帧模式必填：视频的第一帧"}),
                "尾帧图": ("IMAGE", {"tooltip": "首尾帧模式必填：视频的最后一帧"}),
                "运动幅度": (VIDU_MOVEMENT_OPTIONS, {"default": "auto", "tooltip": "Vidu movement_amplitude 参数：auto 自动；small 微动；large 大幅运动"}),
                "音画同步": ("BOOLEAN", {"default": True, "tooltip": "是否生成与画面匹配的环境音/配乐"}),
                "音频类型": (VIDU_AUDIO_TYPE_OPTIONS, {"default": "All", "tooltip": "限定生成的音频类型（环境音/对白/全部）"}),
                "错峰生成": ("BOOLEAN", {"default": False, "tooltip": "开启后任务可能延迟出片，但费用更低"}),
                "最长等待秒数": ("INT", {"default": 1200, "min": 60, "max": 7200, "step": 30, "tooltip": "等待视频生成完成的最长秒数"}),
                "查询间隔秒数": ("INT", {"default": 8, "min": 5, "max": 60, "step": 1, "tooltip": "轮询任务状态的间隔秒数"}),
                "校验HTTPS证书": ("BOOLEAN", {"default": False, "tooltip": "默认关闭以兼容部分网络；遇到 SSL 问题可保持关闭"}),
                "跳过错误": ("BOOLEAN", {"default": False, "tooltip": "开启后异常时返回空，不打断后续工作流"}),
            },
        }

    FUNCTION = "generate_turbo_video"
    DESCRIPTION = "📝 Vidu3 Turbo 视频：使用 Tikpan /ent/v2/text2video、img2video、start-end2video，隐藏未确认可复现的 seed。"

    def generate_turbo_video(self, **kwargs):
        pbar = comfy.utils.ProgressBar(100)
        task_id = ""
        video_url = ""
        try:
            api_key = str(pick(kwargs, "API_密钥", "api_key", default="") or "").strip()
            api_host = normalize_api_host(pick(kwargs, "中转站地址", "api_host", default=API_HOST_OPTIONS[0]))
            skip_error = bool(pick(kwargs, "跳过错误", "skip_error", default=False))
            verify_tls = bool(pick(kwargs, "校验HTTPS证书", "verify_tls", default=False))
            mode_value = str(pick(kwargs, "生成模式", "mode", default="文生视频｜text2video") or "")
            mode = mode_value.split("｜")[-1] if "｜" in mode_value else mode_value
            prompt = str(pick(kwargs, "生成指令", "prompt", default="") or "").strip()
            duration = int(pick(kwargs, "视频时长", "duration", default=5) or 5)
            resolution = str(pick(kwargs, "清晰度", "resolution", default="720p") or "720p")
            aspect_ratio = str(pick(kwargs, "画面比例", "aspect_ratio", default="16:9") or "16:9")
            movement = str(pick(kwargs, "运动幅度", "movement_amplitude", default="auto") or "auto")
            seed_value = pick(kwargs, "随机种子", "seed", default=None)
            seed = normalize_seed(seed_value, default=888888) if seed_value is not None else None
            audio = bool(pick(kwargs, "音画同步", "audio", default=True))
            audio_type = str(pick(kwargs, "音频类型", "audio_type", default="All") or "All")
            off_peak = bool(pick(kwargs, "错峰生成", "off_peak", default=False))
            max_wait = int(pick(kwargs, "最长等待秒数", "max_wait_seconds", default=1200) or 1200)
            poll_interval = int(pick(kwargs, "查询间隔秒数", "poll_interval", default=8) or 8)

            if not api_key or api_key == "sk-" or len(api_key) < 10:
                return self.error_return("❌ 请填写有效的 API 密钥", skip_error)
            if not prompt:
                return self.error_return("❌ 生成指令不能为空", skip_error)

            payload = self.build_common_payload("viduq3-turbo", prompt, duration, resolution, seed, movement, off_peak, audio, audio_type)
            endpoint = "/ent/v2/text2video"
            if mode == "text2video":
                payload["aspect_ratio"] = aspect_ratio
            elif mode == "img2video":
                first = pick(kwargs, "首帧图", "image", default=None)
                if first is None:
                    return self.error_return("❌ 图生视频模式需要连接「首帧图」", skip_error)
                payload["images"] = [self.tensor_to_data_url(first)]
                endpoint = "/ent/v2/img2video"
            elif mode == "start-end2video":
                first = pick(kwargs, "首帧图", "image", default=None)
                last = pick(kwargs, "尾帧图", "end_image", default=None)
                if first is None or last is None:
                    return self.error_return("❌ 首尾帧模式需要同时连接「首帧图」和「尾帧图」", skip_error)
                payload["images"] = [self.tensor_to_data_url(first), self.tensor_to_data_url(last)]
                endpoint = "/ent/v2/start-end2video"
            else:
                return self.error_return(f"❌ 未知生成模式: {mode}", skip_error)

            pbar.update_absolute(8, 100)
            session = self.create_session()
            task_id, video_url, final_json = self.submit_and_wait(
                session, api_host, endpoint, payload, api_key, max_wait, poll_interval, verify_tls, pbar
            )
            pbar.update_absolute(92, 100)
            save_path = self.download_video(session, video_url, "Tikpan_Vidu3_Turbo", task_id, verify_tls)
            pbar.update_absolute(100, 100)
            log = (
                f"✅ Vidu3 Turbo 视频成功 | mode={mode} | model=viduq3-turbo | duration={duration}s | "
                f"resolution={resolution} | aspect_ratio={aspect_ratio} | audio={audio}\n"
                f"task_id={task_id}\nvideo_url={video_url}\npath={save_path}\n\n"
                f"{json.dumps(final_json, ensure_ascii=False, indent=2)[:2500]}"
            )
            return (save_path, task_id, video_url, log, video_from_path(save_path))
        except Exception as exc:
            tb = traceback.format_exc()
            msg = f"❌ Vidu3 Turbo 视频异常: {exc}\n{tb[:2000]}"
            print(f"[Tikpan-Vidu3Turbo] {msg}", flush=True)
            skip_error = bool(pick(kwargs, "跳过错误", "skip_error", default=False))
            if not skip_error:
                raise RuntimeError(msg) from exc
            return ("", task_id, video_url, msg, None)


NODE_CLASS_MAPPINGS = {
    "TikpanVidu3ReferenceVideoNode": TikpanVidu3ReferenceVideoNode,
    "TikpanVidu3TurboVideoNode": TikpanVidu3TurboVideoNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TikpanVidu3ReferenceVideoNode": "视频｜Vidu3 参考生视频",
    "TikpanVidu3TurboVideoNode": "视频｜Vidu3 Turbo 文生/图生/首尾帧",
}
