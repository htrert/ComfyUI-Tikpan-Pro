import base64
import hashlib
import json
import os
import re
import time
from io import BytesIO
from pathlib import Path

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
    extract_task_status,
    extract_video_url,
    is_failure_status,
    is_success_status,
    video_from_path,
)


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_BASE_URL = "https://tikpan.com"
RECOVERY_ROOT = Path(__file__).resolve().parents[1] / "recovery" / "vidu_q3_video"


def safe_filename(text, max_len=72):
    text = re.sub(r'[\\/*?:"<>|]', "_", str(text or ""))
    text = text.strip("._ ")
    return (text[:max_len] or "vidu_video")


def ensure_unique_path(path):
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    counter = 1
    while os.path.exists(f"{base}_{counter}{ext}"):
        counter += 1
    return f"{base}_{counter}{ext}"


def truthy_choice(value):
    return str(value).strip() in {"开启", "是", "true", "True", "1", "有音频", "有水印"}


class TikpanViduQ3BaseNode:
    MODEL_NAME = "viduq3"
    MODEL_TITLE = "Vidu Q3"
    MODEL_DESCRIPTION = "Vidu Q3 视频生成"
    FILE_PREFIX = "Tikpan_ViduQ3"
    CACHE_PREFIX = "tikpan-vidu-q3"
    ALLOWED_MODES = ("参考生视频",)
    RESOLUTIONS = ("540p", "720p", "1080p")
    DURATION_MIN = 3
    DURATION_MAX = 16
    DEFAULT_DURATION = 5
    DEFAULT_RESOLUTION = "720p"
    DEFAULT_AUDIO = "开启"
    SUPPORTS_AUDIO_TYPE = True
    SUPPORTS_540P = True

    @classmethod
    def INPUT_TYPES(cls):
        required = {
            "获取密钥地址": (["👉 https://tikpan.com 获取 Tikpan API Key"],),
            "api_key": ("STRING", {"default": os.environ.get("TIKPAN_API_KEY", "sk-")}),
            "生成模式": (list(cls.ALLOWED_MODES), {"default": cls.ALLOWED_MODES[0]}),
            "prompt": (
                "STRING",
                {
                    "multiline": True,
                    "default": "一个人物在城市街头自然走动，镜头平稳推进，画面真实、有电影感。",
                },
            ),
            "mode": (
                ["同步等待并下载", "异步只提交任务"],
                {"default": "同步等待并下载"},
            ),
            "resolution": (list(cls.RESOLUTIONS), {"default": cls.DEFAULT_RESOLUTION}),
            "aspect_ratio": (
                ["16:9", "9:16", "1:1", "4:3", "3:4"],
                {"default": "16:9"},
            ),
            "duration": (
                "INT",
                {"default": cls.DEFAULT_DURATION, "min": cls.DURATION_MIN, "max": cls.DURATION_MAX, "step": 1},
            ),
            "audio": (["开启", "关闭"], {"default": cls.DEFAULT_AUDIO}),
            "audio_type": (
                ["all", "Speech_only", "Sound-effect_only"],
                {"default": "all"},
            ),
            "seed": ("INT", {"default": -1, "min": -1, "max": 2147483647}),
            "off_peak": (["关闭", "开启"], {"default": "关闭"}),
            "复用本地缓存": ("BOOLEAN", {"default": True}),
            "最长等待秒数": ("INT", {"default": 900, "min": 30, "max": 7200, "step": 30}),
            "轮询间隔秒数": ("INT", {"default": 8, "min": 3, "max": 60, "step": 1}),
            "接口基础地址": ("STRING", {"default": API_BASE_URL}),
        }
        optional = {
            "参考图1": ("IMAGE",),
            "参考图2": ("IMAGE",),
            "参考图3": ("IMAGE",),
            "参考图4": ("IMAGE",),
            "参考图5": ("IMAGE",),
            "参考图6": ("IMAGE",),
            "参考图7": ("IMAGE",),
            "首帧图": ("IMAGE",),
            "尾帧图": ("IMAGE",),
            "图片URL列表": (
                "STRING",
                {
                    "multiline": True,
                    "default": "",
                    "tooltip": "每行一个图片 URL。参考生视频最多 7 张；图生视频取第一张；首尾帧模式取前两张。",
                },
            ),
            "payload透传JSON": (
                "STRING",
                {
                    "multiline": True,
                    "default": "",
                    "tooltip": "可选。会合并到 Vidu payload 顶层，用于后续 Tikpan 上游扩展参数。",
                },
            ),
        }
        return {"required": required, "optional": optional}

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "VIDEO")
    RETURN_NAMES = ("本地保存路径", "任务ID", "视频云端直链", "完整日志", "视频输出")
    OUTPUT_NODE = True
    FUNCTION = "generate_video"
    CATEGORY = "👑 Tikpan 官方独家节点"

    def create_session(self):
        session = requests.Session()
        session.trust_env = False
        retry = Retry(
            total=4,
            connect=4,
            read=4,
            backoff_factor=0.8,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def fail_return(self, title, task_id="", video_url="", detail="", skip_error=False):
        message = f"{title}\n{detail}".strip()
        if skip_error:
            print(f"[Tikpan-Vidu] {message}", flush=True)
            return ("", str(task_id or ""), str(video_url or ""), message, None)
        return (message, str(task_id or ""), str(video_url or ""), message, None)

    def auth_headers(self, api_key, auth_prefix="Bearer", idempotency_key=""):
        token = str(api_key or "").strip()
        if token.lower().startswith(("bearer ", "token ")):
            authorization = token
        else:
            authorization = f"{auth_prefix} {token}"
        headers = {
            "Authorization": authorization,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"Tikpan-ComfyUI-{self.MODEL_NAME}/1.0",
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    def safe_response_text(self, response, limit=1000):
        try:
            text = response.text
        except Exception:
            text = "<无法读取响应文本>"
        return text[:limit]

    def parse_extra_json(self, text):
        raw = str(text or "").strip()
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except Exception as e:
            raise ValueError(f"payload透传JSON 不是合法 JSON: {e}")
        if not isinstance(data, dict):
            raise ValueError("payload透传JSON 必须是 JSON object。")
        return data

    def image_to_data_url(self, image_tensor, label="image"):
        if image_tensor is None:
            return ""
        arr = 255.0 * image_tensor[0].cpu().numpy()
        img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGB")
        width, height = img.size
        if width < 128 or height < 128:
            raise ValueError(f"{label} 分辨率太小：{width}x{height}，Vidu 要求至少 128x128。")
        ratio = max(width / height, height / width)
        if ratio >= 4:
            raise ValueError(f"{label} 宽高比过极端：{width}x{height}，需要小于 1:4 或 4:1。")

        quality = 90
        while quality >= 55:
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            image_bytes = buf.getvalue()
            if len(image_bytes) <= 9_500_000:
                return "data:image/jpeg;base64," + base64.b64encode(image_bytes).decode("utf-8")
            quality -= 10
        raise ValueError(f"{label} 压缩后仍超过 10MB，请先缩小图片。")

    def parse_url_list(self, text):
        urls = []
        for line in str(text or "").replace(",", "\n").splitlines():
            item = line.strip()
            if not item:
                continue
            if not item.startswith(("http://", "https://", "data:image/")):
                raise ValueError(f"图片URL不合法: {item[:80]}")
            urls.append(item)
        return urls

    def collect_reference_images(self, kwargs):
        images = self.parse_url_list(kwargs.get("图片URL列表", ""))
        for idx in range(1, 8):
            image_tensor = kwargs.get(f"参考图{idx}")
            if image_tensor is not None:
                images.append(self.image_to_data_url(image_tensor, f"参考图{idx}"))
        if len(images) > 7:
            raise ValueError("Vidu 参考生视频最多支持 7 张参考图，请减少输入。")
        return images

    def collect_first_last_images(self, kwargs):
        url_images = self.parse_url_list(kwargs.get("图片URL列表", ""))
        first = url_images[0] if len(url_images) >= 1 else ""
        last = url_images[1] if len(url_images) >= 2 else ""
        if kwargs.get("首帧图") is not None:
            first = self.image_to_data_url(kwargs.get("首帧图"), "首帧图")
        if kwargs.get("尾帧图") is not None:
            last = self.image_to_data_url(kwargs.get("尾帧图"), "尾帧图")
        return first, last

    def collect_image_to_video_image(self, kwargs):
        url_images = self.parse_url_list(kwargs.get("图片URL列表", ""))
        if kwargs.get("首帧图") is not None:
            return self.image_to_data_url(kwargs.get("首帧图"), "首帧图")
        if kwargs.get("参考图1") is not None:
            return self.image_to_data_url(kwargs.get("参考图1"), "参考图1")
        return url_images[0] if url_images else ""

    def normalize_resolution(self, resolution):
        value = str(resolution or self.DEFAULT_RESOLUTION).lower()
        if value not in {"540p", "720p", "1080p"}:
            raise ValueError(f"不支持的清晰度: {resolution}")
        if value == "540p" and not self.SUPPORTS_540P:
            raise ValueError(f"{self.MODEL_NAME} 不支持 540p，请选择 720p 或 1080p。")
        return value

    def endpoint_for_mode(self, generation_mode):
        if generation_mode == "文生视频":
            return "/ent/v2/text2video"
        if generation_mode == "图生视频":
            return "/ent/v2/img2video"
        if generation_mode == "首尾帧":
            return "/ent/v2/start-end2video"
        return "/ent/v2/reference2video"

    def validate_mode(self, generation_mode):
        if generation_mode not in self.ALLOWED_MODES:
            raise ValueError(f"{self.MODEL_NAME} 不支持生成模式：{generation_mode}")

    def build_payload(self, values, kwargs):
        generation_mode = values["生成模式"]
        self.validate_mode(generation_mode)
        prompt = str(values.get("prompt") or "").strip()
        if not prompt:
            raise ValueError("prompt 不能为空。")
        if len(prompt) > 5000:
            raise ValueError("prompt 不能超过 5000 字符。")

        duration = int(values.get("duration") or self.DEFAULT_DURATION)
        if duration < self.DURATION_MIN or duration > self.DURATION_MAX:
            raise ValueError(f"{self.MODEL_NAME} 时长范围是 {self.DURATION_MIN}-{self.DURATION_MAX} 秒。")

        payload = {
            "model": self.MODEL_NAME,
            "prompt": prompt,
            "duration": duration,
            "resolution": self.normalize_resolution(values.get("resolution")),
            "aspect_ratio": values.get("aspect_ratio") or "16:9",
            "off_peak": truthy_choice(values.get("off_peak")),
        }

        seed = int(values.get("seed", -1))
        if seed >= 0:
            payload["seed"] = seed

        if generation_mode in {"参考生视频", "文生视频"}:
            audio_enabled = truthy_choice(values.get("audio"))
            payload["audio"] = audio_enabled
            if audio_enabled and self.SUPPORTS_AUDIO_TYPE:
                payload["audio_type"] = values.get("audio_type") or "all"

        if generation_mode == "参考生视频":
            images = self.collect_reference_images(kwargs)
            if not images:
                raise ValueError("参考生视频至少需要 1 张参考图，或在 图片URL列表 填入图片 URL。")
            payload["images"] = images
        elif generation_mode == "图生视频":
            image = self.collect_image_to_video_image(kwargs)
            if not image:
                raise ValueError("图生视频至少需要 1 张首帧/参考图，或在 图片URL列表 填入图片 URL。")
            payload["images"] = [image]
        elif generation_mode == "首尾帧":
            first, last = self.collect_first_last_images(kwargs)
            if not first or not last:
                raise ValueError("首尾帧模式需要同时提供首帧图和尾帧图，或在 图片URL列表 填入两张图片 URL。")
            payload["images"] = [first, last]

        payload.update(self.parse_extra_json(kwargs.get("payload透传JSON", "")))
        return payload

    def payload_hash(self, endpoint, payload):
        def compact(value):
            if isinstance(value, str) and value.startswith("data:"):
                return f"data-sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"
            if isinstance(value, list):
                return [compact(item) for item in value]
            if isinstance(value, dict):
                return {key: compact(val) for key, val in value.items()}
            return value

        raw = json.dumps(
            {"endpoint": endpoint, "payload": compact(payload)},
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def recovery_dir(self):
        path = RECOVERY_ROOT / self.MODEL_NAME.replace("-", "_")
        path.mkdir(parents=True, exist_ok=True)
        return path

    def recovery_record_path(self, cache_key):
        return self.recovery_dir() / f"{self.CACHE_PREFIX}-{cache_key[:32]}.json"

    def cache_video_path(self, cache_key):
        return self.recovery_dir() / f"{self.CACHE_PREFIX}-{cache_key[:32]}.mp4"

    def save_recovery_record(self, cache_key, status, **fields):
        record = {
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "model": self.MODEL_NAME,
            "cache_key": cache_key,
            "status": status,
            **fields,
        }
        latest_path = self.recovery_record_path(cache_key)
        latest_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        with (self.recovery_dir() / "events.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return str(latest_path)

    def read_cached_video(self, cache_key):
        path = self.cache_video_path(cache_key)
        if path.exists() and path.stat().st_size > 1024:
            return str(path)
        return ""

    def extract_task_id(self, data):
        if not isinstance(data, dict):
            return ""
        nested = data.get("data") if isinstance(data.get("data"), dict) else {}
        return (
            data.get("task_id")
            or data.get("id")
            or data.get("taskId")
            or nested.get("task_id")
            or nested.get("id")
            or nested.get("taskId")
            or ""
        )

    def extract_generation_state(self, data):
        status = extract_task_status(data)
        if status:
            return status.lower()
        if isinstance(data, dict):
            return str(data.get("state") or data.get("status") or "").lower()
        return ""

    def extract_creation_url(self, data):
        direct = extract_video_url(data)
        if direct:
            return direct
        if not isinstance(data, dict):
            return ""
        creations = data.get("creations")
        if isinstance(creations, list):
            for item in creations:
                if isinstance(item, dict):
                    url = item.get("url") or item.get("video_url")
                    if isinstance(url, str) and url.startswith("http"):
                        return url
        nested = data.get("data")
        if isinstance(nested, dict):
            return self.extract_creation_url(nested)
        return ""

    def submit_task(self, session, base_url, api_key, endpoint, payload, cache_key):
        url = f"{base_url.rstrip('/')}{endpoint}"
        headers = self.auth_headers(api_key, "Bearer", f"{self.CACHE_PREFIX}-{cache_key[:32]}")
        response = session.post(url, json=payload, headers=headers, timeout=(15, 180), verify=False)
        if response.status_code in {401, 403}:
            token_headers = self.auth_headers(api_key, "Token", f"{self.CACHE_PREFIX}-{cache_key[:32]}")
            response = session.post(url, json=payload, headers=token_headers, timeout=(15, 180), verify=False)
        if response.status_code >= 400:
            raise RuntimeError(f"任务创建失败 | HTTP {response.status_code} | {self.safe_response_text(response)}")
        try:
            data = response.json()
        except Exception:
            raise RuntimeError(f"任务创建响应不是 JSON: {self.safe_response_text(response)}")
        task_id = self.extract_task_id(data)
        video_url = self.extract_creation_url(data)
        if not task_id and not video_url:
            raise RuntimeError(f"任务创建成功但没有 task_id/url: {json.dumps(data, ensure_ascii=False)[:1000]}")
        return task_id or "sync_task", video_url, data

    def poll_task(self, session, base_url, api_key, task_id, max_wait_seconds, poll_interval, pbar):
        url = f"{base_url.rstrip('/')}/ent/v2/tasks/{task_id}/creations"
        headers = self.auth_headers(api_key, "Bearer")
        start = time.time()
        last_data = {}
        while time.time() - start < max_wait_seconds:
            for _ in range(max(1, int(poll_interval))):
                time.sleep(1)
                comfy.model_management.throw_exception_if_processing_interrupted()

            elapsed = int(time.time() - start)
            try:
                response = session.get(url, headers=headers, timeout=(10, 45), verify=False)
                if response.status_code in {401, 403}:
                    response = session.get(url, headers=self.auth_headers(api_key, "Token"), timeout=(10, 45), verify=False)
                if response.status_code >= 400:
                    print(f"[Tikpan-Vidu] 查询失败 HTTP {response.status_code}: {self.safe_response_text(response, 300)}", flush=True)
                    continue
                data = response.json()
                last_data = data
                state = self.extract_generation_state(data)
                print(f"[Tikpan-Vidu] 云端渲染中 | task={task_id} | state={state or '-'} | elapsed={elapsed}s", flush=True)

                progress = min(95, 15 + int(elapsed / max(1, max_wait_seconds) * 75))
                pbar.update_absolute(progress, 100)

                if is_success_status(state) or state == "success":
                    video_url = self.extract_creation_url(data)
                    if video_url:
                        pbar.update_absolute(100, 100)
                        return video_url, data
                    raise RuntimeError(f"任务成功但未找到视频 URL: {json.dumps(data, ensure_ascii=False)[:1000]}")
                if is_failure_status(state) or state == "failed":
                    raise RuntimeError(f"任务失败: {extract_error_message(data)} | {json.dumps(data, ensure_ascii=False)[:1000]}")
            except requests.exceptions.RequestException as e:
                print(f"[Tikpan-Vidu] 查询网络波动，继续等待: {e}", flush=True)
                continue

        raise TimeoutError(f"轮询超时，任务可能仍在云端生成。task_id={task_id} | last={json.dumps(last_data, ensure_ascii=False)[:1000]}")

    def download_video(self, session, video_url, cache_key):
        response = session.get(video_url, timeout=(15, 600), stream=True, verify=False)
        response.raise_for_status()
        content_type = str(response.headers.get("Content-Type", "")).lower()
        content = response.content
        if not content or len(content) < 1024:
            raise RuntimeError(f"下载结果为空或过小 | Content-Type={content_type} | bytes={len(content) if content else 0}")
        if "json" in content_type or "text/html" in content_type or content[:1] in (b"{", b"["):
            preview = content[:800].decode("utf-8", errors="ignore")
            raise RuntimeError(f"下载视频时拿到错误页/JSON: {preview}")

        recovery_path = self.cache_video_path(cache_key)
        recovery_path.write_bytes(content)

        filename = f"{self.FILE_PREFIX}_{safe_filename(self.MODEL_NAME)}_{cache_key[:16]}.mp4"
        output_path = ensure_unique_path(os.path.join(folder_paths.get_output_directory(), filename))
        with open(output_path, "wb") as f:
            f.write(content)
        return output_path, str(recovery_path), len(content), content_type

    def build_log(self, status, payload, endpoint, task_id="", video_url="", raw=None, extra=""):
        safe_payload = dict(payload)
        if "images" in safe_payload:
            safe_payload["images"] = [f"<image:{idx + 1}>" for idx, _ in enumerate(safe_payload.get("images") or [])]
        log = {
            "status": status,
            "model": self.MODEL_NAME,
            "endpoint": endpoint,
            "task_id": task_id,
            "video_url": video_url,
            "payload_preview": safe_payload,
            "raw": raw or {},
        }
        text = json.dumps(log, ensure_ascii=False, indent=2)
        if extra:
            text += f"\n\n{extra}"
        return text

    def generate_video(self, **kwargs):
        start_time = time.time()
        values = dict(kwargs)
        api_key = str(values.get("api_key") or "").strip()
        skip_error = bool(values.get("跳过错误", False))

        try:
            comfy.model_management.throw_exception_if_processing_interrupted()
            if not api_key or api_key == "sk-" or len(api_key) < 10:
                raise ValueError("请填写 Tikpan API Key。")

            payload = self.build_payload(values, kwargs)
            endpoint = self.endpoint_for_mode(values["生成模式"])
            cache_key = self.payload_hash(endpoint, payload)
            pbar = comfy.utils.ProgressBar(100)
            pbar.update_absolute(5, 100)

            if bool(values.get("复用本地缓存", True)):
                cached_path = self.read_cached_video(cache_key)
                if cached_path:
                    video = video_from_path(cached_path)
                    log = f"OK 命中本地缓存，未重新请求上游，避免重复扣费 | path={cached_path}"
                    return (cached_path, "", "", log, video)

            recovery_path = self.save_recovery_record(
                cache_key,
                "pending",
                endpoint=endpoint,
                payload_preview=self.build_log("pending", payload, endpoint),
            )
            print(f"[Tikpan-Vidu] START {self.MODEL_NAME} | endpoint={endpoint} | recovery={recovery_path}", flush=True)

            base_url = str(values.get("接口基础地址") or API_BASE_URL).strip().rstrip("/")
            session = self.create_session()

            try:
                task_id, direct_url, create_json = self.submit_task(session, base_url, api_key, endpoint, payload, cache_key)
            except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
                self.save_recovery_record(cache_key, "post_disconnected", endpoint=endpoint, error=str(e), recovery_path=recovery_path)
                raise RuntimeError(
                    f"网络在提交后断开：上游可能已经收到并扣费。建议先检查 recovery/vidu_q3_video/{self.MODEL_NAME.replace('-', '_')} "
                    f"中的记录，不要立刻改参数重复提交。cache_key={cache_key[:32]} | recovery={recovery_path}"
                )

            self.save_recovery_record(cache_key, "submitted", endpoint=endpoint, task_id=task_id, create_response=create_json)
            pbar.update_absolute(12, 100)

            if "异步" in str(values.get("mode")):
                log = self.build_log("submitted", payload, endpoint, task_id=task_id, video_url=direct_url, raw=create_json)
                return ("", str(task_id), direct_url or "", log, None)

            video_url = direct_url
            final_json = create_json
            if not video_url:
                video_url, final_json = self.poll_task(
                    session,
                    base_url,
                    api_key,
                    task_id,
                    int(values.get("最长等待秒数") or 900),
                    int(values.get("轮询间隔秒数") or 8),
                    pbar,
                )

            pbar.update_absolute(96, 100)
            output_path, recovery_video_path, bytes_count, content_type = self.download_video(session, video_url, cache_key)
            video = video_from_path(output_path)
            elapsed = round(time.time() - start_time, 2)
            log = self.build_log(
                "success",
                payload,
                endpoint,
                task_id=task_id,
                video_url=video_url,
                raw=final_json,
                extra=f"下载信息: bytes={bytes_count} | content_type={content_type or 'unknown'} | output={output_path} | cache={recovery_video_path} | elapsed={elapsed}s",
            )
            self.save_recovery_record(
                cache_key,
                "success",
                endpoint=endpoint,
                task_id=task_id,
                video_url=video_url,
                output_path=output_path,
                recovery_video_path=recovery_video_path,
                elapsed=elapsed,
            )
            pbar.update_absolute(100, 100)
            return (output_path, str(task_id), video_url, log, video)

        except Exception as e:
            detail = str(e)
            try:
                self.save_recovery_record("error-" + hashlib.sha256(detail.encode("utf-8")).hexdigest(), "error", error=detail)
            except Exception:
                pass
            return self.fail_return("❌ Vidu Q3 视频节点执行失败", "", "", detail, skip_error=skip_error)


class TikpanViduQ3Node(TikpanViduQ3BaseNode):
    MODEL_NAME = "viduq3"
    MODEL_TITLE = "viduq3 参考生视频"
    MODEL_DESCRIPTION = "画面质量强，支持智能切镜、动态效果好，支持 540p/720p/1080p。"
    FILE_PREFIX = "Tikpan_ViduQ3"
    CACHE_PREFIX = "tikpan-vidu-q3"
    ALLOWED_MODES = ("参考生视频",)
    RESOLUTIONS = ("540p", "720p", "1080p")
    DURATION_MIN = 3
    DURATION_MAX = 16
    DEFAULT_DURATION = 5
    DEFAULT_RESOLUTION = "720p"
    SUPPORTS_540P = True


class TikpanViduQ3MixNode(TikpanViduQ3BaseNode):
    MODEL_NAME = "viduq3-mix"
    MODEL_TITLE = "viduq3-mix 参考生视频"
    MODEL_DESCRIPTION = "智能切镜，多机位一致性更出色，支持 720p/1080p。"
    FILE_PREFIX = "Tikpan_ViduQ3_Mix"
    CACHE_PREFIX = "tikpan-vidu-q3-mix"
    ALLOWED_MODES = ("参考生视频",)
    RESOLUTIONS = ("720p", "1080p")
    DURATION_MIN = 1
    DURATION_MAX = 16
    DEFAULT_DURATION = 5
    DEFAULT_RESOLUTION = "720p"
    SUPPORTS_540P = False


class TikpanViduQ3TurboNode(TikpanViduQ3BaseNode):
    MODEL_NAME = "viduq3-turbo"
    MODEL_TITLE = "viduq3-turbo 多模式视频"
    MODEL_DESCRIPTION = "支持文生视频、图生视频、首尾帧和参考生视频，速度快、性价比高。"
    FILE_PREFIX = "Tikpan_ViduQ3_Turbo"
    CACHE_PREFIX = "tikpan-vidu-q3-turbo"
    ALLOWED_MODES = ("文生视频", "图生视频", "首尾帧", "参考生视频")
    RESOLUTIONS = ("540p", "720p", "1080p")
    DURATION_MIN = 3
    DURATION_MAX = 16
    DEFAULT_DURATION = 5
    DEFAULT_RESOLUTION = "720p"
    SUPPORTS_540P = True


NODE_CLASS_MAPPINGS = {
    "TikpanViduQ3Node": TikpanViduQ3Node,
    "TikpanViduQ3MixNode": TikpanViduQ3MixNode,
    "TikpanViduQ3TurboNode": TikpanViduQ3TurboNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TikpanViduQ3Node": "🎬 Tikpan: viduq3 参考生视频",
    "TikpanViduQ3MixNode": "🎬 Tikpan: viduq3-mix 参考生视频",
    "TikpanViduQ3TurboNode": "🎬 Tikpan: viduq3-turbo 多模式视频",
}
