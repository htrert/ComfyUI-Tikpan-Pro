from .tikpan_categories import CATEGORY_VIDEO
import base64
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

HAILUO_MODE_OPTIONS = ["文生视频｜text2video", "首帧图生视频｜image2video", "首尾帧视频｜first-last-frame"]
HAILUO_MODEL_OPTIONS = [
    "MiniMax-Hailuo-2.3 最新质量｜MiniMax-Hailuo-2.3",
    "MiniMax-Hailuo-02 稳定旧版｜MiniMax-Hailuo-02",
]
HAILUO_DURATION_OPTIONS = ["6秒｜6", "10秒｜10"]
HAILUO_RESOLUTION_OPTIONS = ["768P", "1080P"]


class TikpanMiniMaxHailuoVideoNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "💰_福利_💰": (["🔥 0.6元RMB兑1美元余额 | 全网底价 👉 https://tikpan.com"],),
                "获取密钥请访问": (["👉 https://tikpan.com (官方授权Key获取点)"],),
                "API_密钥": ("STRING", {"default": "sk-", "tooltip": "Tikpan 平台的 API 密钥，以 sk- 开头，从 https://tikpan.com 获取"}),
                "生成模式": (HAILUO_MODE_OPTIONS, {"default": HAILUO_MODE_OPTIONS[0], "tooltip": "MiniMax/Hailuo 视频模式：文生、首帧图生、首尾帧"}),
                "模型版本": (HAILUO_MODEL_OPTIONS, {"default": HAILUO_MODEL_OPTIONS[0], "tooltip": "默认使用 MiniMax-Hailuo-2.3；首尾帧模式请切换 MiniMax-Hailuo-02"}),
                "生成指令": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "A cinematic short video, smooth camera movement, realistic lighting, high detail.",
                        "tooltip": "描述视频主体、动作、镜头、风格，推荐英文或中英混合",
                    },
                ),
                "视频时长": (HAILUO_DURATION_OPTIONS, {"default": HAILUO_DURATION_OPTIONS[0], "tooltip": "MiniMax/Hailuo duration 参数"}),
                "分辨率": (HAILUO_RESOLUTION_OPTIONS, {"default": "768P", "tooltip": "MiniMax/Hailuo resolution 参数；1080P 更慢更贵"}),
            },
            "optional": {
                "首帧图": ("IMAGE", {"tooltip": "图生视频/首尾帧模式必填：视频第一帧"}),
                "尾帧图": ("IMAGE", {"tooltip": "首尾帧模式必填：视频最后一帧"}),
                "提示词优化": ("BOOLEAN", {"default": True, "tooltip": "MiniMax prompt_optimizer 参数"}),
                "中转站地址": (API_HOST_OPTIONS, {"default": API_HOST_OPTIONS[0], "tooltip": "Tikpan 中转站地址，一般保持默认即可"}),
                "最长等待秒数": ("INT", {"default": 1200, "min": 60, "max": 7200, "step": 30, "tooltip": "等待视频生成完成的最长秒数"}),
                "查询间隔秒数": ("INT", {"default": 8, "min": 5, "max": 60, "step": 1, "tooltip": "轮询任务状态的间隔秒数"}),
                "校验HTTPS证书": ("BOOLEAN", {"default": False, "tooltip": "默认关闭以兼容部分网络；遇到 SSL 问题可保持关闭"}),
                "跳过错误": ("BOOLEAN", {"default": False, "tooltip": "开启后异常时返回空，不打断后续工作流"}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "VIDEO")
    RETURN_NAMES = ("📁_本地保存路径", "🆔_任务ID", "🔗_视频云端直链", "📄_完整日志", "🎬_视频输出")
    OUTPUT_NODE = True
    FUNCTION = "generate_video"
    CATEGORY = CATEGORY_VIDEO
    DESCRIPTION = "📝 MiniMax Hailuo 2.3 视频生成：支持文生视频、首帧图生视频、首尾帧视频，默认 MiniMax-Hailuo-2.3。"

    def generate_video(self, **kwargs):
        pbar = comfy.utils.ProgressBar(100)
        task_id = ""
        video_url = ""
        try:
            api_key = str(pick(kwargs, "API_密钥", "api_key", default="") or "").strip()
            api_host = normalize_api_host(pick(kwargs, "中转站地址", "api_host", default=API_HOST_OPTIONS[0]))
            skip_error = bool(pick(kwargs, "跳过错误", "skip_error", default=False))
            verify_tls = bool(pick(kwargs, "校验HTTPS证书", "verify_tls", default=False))
            mode = option_value(pick(kwargs, "生成模式", "mode", default=HAILUO_MODE_OPTIONS[0]), "text2video")
            model = option_value(pick(kwargs, "模型版本", "model", default=HAILUO_MODEL_OPTIONS[0]), "MiniMax-Hailuo-2.3")
            if model == "MiniMax-Hailuo-2.3-fast":
                print("[Tikpan-Hailuo] MiniMax-Hailuo-2.3-fast 当前未在上游文档支持列表中，已自动改用 MiniMax-Hailuo-2.3。", flush=True)
                model = "MiniMax-Hailuo-2.3"
            prompt = str(pick(kwargs, "生成指令", "prompt", default="") or "").strip()
            duration = int(option_value(pick(kwargs, "视频时长", "duration", default=HAILUO_DURATION_OPTIONS[0]), "6"))
            resolution = str(pick(kwargs, "分辨率", "resolution", default="768P") or "768P")
            prompt_optimizer = bool(pick(kwargs, "提示词优化", "prompt_optimizer", default=True))
            first_frame = pick(kwargs, "首帧图", "first_frame_image", default=None)
            last_frame = pick(kwargs, "尾帧图", "last_frame_image", default=None)
            max_wait = int(pick(kwargs, "最长等待秒数", "max_wait_seconds", default=1200) or 1200)
            poll_interval = int(pick(kwargs, "查询间隔秒数", "poll_interval", default=8) or 8)

            if not api_key or api_key == "sk-" or len(api_key) < 10:
                return self.error_return("❌ 请填写有效的 API 密钥", skip_error)
            if not prompt:
                return self.error_return("❌ 生成指令不能为空", skip_error)
            if mode in {"image2video", "first-last-frame"} and first_frame is None:
                return self.error_return("❌ 当前模式需要连接首帧图", skip_error)
            if mode == "first-last-frame" and last_frame is None:
                return self.error_return("❌ 首尾帧模式需要连接尾帧图", skip_error)
            if mode == "first-last-frame" and model != "MiniMax-Hailuo-02":
                return self.error_return("❌ MiniMax Hailuo 首尾帧视频仅支持 MiniMax-Hailuo-02，请切换模型版本。", skip_error)
            if duration == 10 and resolution == "1080P":
                return self.error_return("❌ MiniMax Hailuo 不支持 10秒 + 1080P，请改用 6秒 + 1080P 或 10秒 + 768P。", skip_error)

            payload = self.build_payload(
                mode=mode,
                model=model,
                prompt=prompt,
                duration=duration,
                resolution=resolution,
                prompt_optimizer=prompt_optimizer,
                first_frame_image=self.tensor_to_data_url(first_frame) if first_frame is not None else "",
                last_frame_image=self.tensor_to_data_url(last_frame) if last_frame is not None else "",
            )
            session = self.create_session()
            headers = self.headers(api_key)
            print(f"[Tikpan-Hailuo] Payload: {json.dumps(self.redact_payload(payload), ensure_ascii=False)[:1200]}", flush=True)
            pbar.update_absolute(20, 100)

            response = session.post(
                f"{api_host}/minimax/v1/video_generation",
                json=payload,
                headers=headers,
                timeout=(20, 120),
                verify=verify_tls,
            )
            if response.status_code >= 400:
                return self.error_return(f"❌ 任务创建失败: HTTP {response.status_code}\n{self.safe_text(response.text)}", skip_error)
            create_json = response.json()
            task_id = self.extract_task_id(create_json)
            video_url = extract_video_url(create_json)
            if not video_url and not task_id:
                return self.error_return(f"❌ 任务创建失败：未获取到任务ID\n{json.dumps(create_json, ensure_ascii=False)[:1500]}", skip_error)

            final_json = create_json
            if not video_url:
                ok, result, final_json = self.poll_task(session, api_host, headers, task_id, max_wait, poll_interval, verify_tls, pbar)
                if not ok:
                    return self.error_return(result, skip_error, task_id=task_id)
                video_url = result

            pbar.update_absolute(88, 100)
            save_path = self.download_video(session, video_url, "Tikpan_Hailuo", task_id or "sync", verify_tls)
            pbar.update_absolute(100, 100)
            log = (
                f"✅ MiniMax Hailuo 视频生成成功 | model={model} | mode={mode} | duration={duration}s | resolution={resolution}\n"
                f"task_id={task_id or 'sync'}\nvideo_url={video_url}\npath={save_path}\n\n"
                f"{json.dumps(final_json, ensure_ascii=False, indent=2)[:2500]}"
            )
            return (save_path, task_id or "sync", video_url, log, video_from_path(save_path))
        except Exception as exc:
            tb = traceback.format_exc()
            msg = f"❌ MiniMax Hailuo 视频异常: {exc}\n{tb[:2000]}"
            print(f"[Tikpan-Hailuo] {msg}", flush=True)
            skip_error = bool(pick(kwargs, "跳过错误", "skip_error", default=False))
            if not skip_error:
                raise RuntimeError(msg) from exc
            return ("", task_id, video_url, msg, None)

    def build_payload(self, mode, model, prompt, duration, resolution, prompt_optimizer, first_frame_image="", last_frame_image=""):
        payload = {
            "model": model,
            "prompt": prompt,
            "duration": int(duration),
            "prompt_optimizer": bool(prompt_optimizer),
        }
        if resolution:
            payload["resolution"] = str(resolution)
        if mode in {"image2video", "first-last-frame"} and first_frame_image:
            payload["first_frame_image"] = first_frame_image
        if mode == "first-last-frame" and last_frame_image:
            payload["last_frame_image"] = last_frame_image
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
        return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "Accept": "application/json", "User-Agent": "Tikpan-ComfyUI-HailuoVideo/1.0"}

    def tensor_to_data_url(self, img_tensor, quality=92):
        if len(img_tensor.shape) == 4:
            img_tensor = img_tensor[0]
        arr = 255.0 * img_tensor.detach().cpu().numpy()
        image = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGB")
        buf = BytesIO()
        image.save(buf, format="JPEG", quality=int(quality), optimize=True)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")

    def poll_task(self, session, api_host, headers, task_id, max_wait, poll_interval, verify_tls, pbar):
        start = time.time()
        last_json = {}
        poll_count = 0
        while time.time() - start < max_wait:
            comfy.model_management.throw_exception_if_processing_interrupted()
            time.sleep(poll_interval)
            poll_count += 1
            try:
                resp = session.get(f"{api_host}/minimax/v1/query/video_generation?task_id={task_id}", headers=headers, timeout=(15, 45), verify=verify_tls)
                if resp.status_code >= 400:
                    continue
                res_json = resp.json()
                last_json = res_json
                status = extract_task_status(res_json)
                output = extract_task_output(res_json)
                elapsed = int(time.time() - start)
                if pbar:
                    pbar.update_absolute(min(85, 25 + int(elapsed * 55 / max(max_wait, 1))), 100)
                print(f"[Tikpan-Hailuo] 轮询 {poll_count} | status={status or 'unknown'}", flush=True)
                video_url = extract_video_url(res_json)
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
        return {key: ("[data:image omitted]" if isinstance(value, str) and value.startswith("data:image") else value) for key, value in payload.items()}

    def safe_text(self, value, max_len=1000):
        try:
            return str(value or "")[:max_len].strip()
        except Exception:
            return ""

    def error_return(self, message, skip_error=False, task_id=""):
        if not skip_error:
            raise RuntimeError(message)
        return ("", task_id, "", message, None)


NODE_CLASS_MAPPINGS = {"TikpanMiniMaxHailuoVideoNode": TikpanMiniMaxHailuoVideoNode}
NODE_DISPLAY_NAME_MAPPINGS = {"TikpanMiniMaxHailuoVideoNode": "视频｜MiniMax Hailuo 视频生成"}
