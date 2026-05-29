"""
Tikpan: Gemini Omni 视频生成节点
- 模型：omni-flash（文生视频）、omni-flash-components（参考图生视频）
- 端点：POST https://tikpan.com/v1/video/create（固定，用户不可更改）
- 轮询：GET /v1/video/query?id={task_id}
- 官方均为异步模式，节点内自动轮询直到完成
"""
import base64
import hashlib
import json
import mimetypes
import os
import time
import traceback
import wave
from io import BytesIO

import folder_paths
import numpy as np
import requests
import urllib3
from PIL import Image
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import comfy.model_management
import comfy.utils

from .tikpan_happyhorse_common import video_from_path
from .tikpan_node_options import API_HOST_OPTIONS, normalize_api_host, normalize_seed, pick


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ─── 仅包含 Tikpan 价格页已上线的模型 ─────────────────────────────────────────
MODEL_OPTIONS = [
    "omni-flash",
    "omni-flash-components",
]
COMPONENT_MODELS = {"omni-flash-components"}

ASPECT_OPTIONS = [
    "16:9 横屏｜16:9",
    "9:16 竖屏｜9:16",
    "1:1 方形｜1:1",
    "4:3 经典横屏｜4:3",
    "3:4 经典竖屏｜3:4",
]

RESOLUTION_OPTIONS = [
    "720p｜720p",
    "1080p｜1080p",
]

DURATION_OPTIONS = [
    "5 秒｜5",
    "8 秒｜8",
    "10 秒｜10",
]

# 固定端点 —— 两个模型都走 /v1/video/create
HARDCODED_ENDPOINT = "/v1/video/create"
QUERY_ENDPOINT_TEMPLATE = "/v1/video/query?id={task_id}"

MAX_REFERENCE_IMAGES = 5
MAX_INLINE_VIDEO_BYTES = 48 * 1024 * 1024
MAX_INLINE_AUDIO_BYTES = 24 * 1024 * 1024


def _raw(value, default=""):
    """从 中文说明｜raw_value 格式的下拉值中提取 raw_value。"""
    text = str(value if value is not None else default).strip()
    if not text:
        return default
    for sep in ("｜", "|"):
        if sep in text:
            return text.split(sep)[-1].strip() or default
    return text


class TikpanGeminiOmniVideoNode:
    @classmethod
    def INPUT_TYPES(cls):
        optional = {
            "负面提示词": (
                "STRING",
                {
                    "multiline": True,
                    "default": "",
                    "tooltip": "告诉模型不要出现什么内容，例如：blurry, text overlay, watermark, low quality",
                },
            ),
        }
        # 参考图（仅 omni-flash-components 有效）
        for i in range(1, MAX_REFERENCE_IMAGES + 1):
            optional[f"参考图{i}"] = ("IMAGE", {"tooltip": f"参考图 {i}：作为视觉参考输入，仅 omni-flash-components 模型有效"})

        optional["视频URL"] = (
            "STRING",
            {
                "multiline": False,
                "default": "",
                "tooltip": "用于视频编辑/视频参考。优先使用公开可访问 URL；本字段会透传为 video_url/input_video 等兼容字段。",
            },
        )
        optional["本地视频"] = (
            "VIDEO",
            {"tooltip": "用于视频编辑/视频参考。小于约 48MB 时会 inline 直传为 data:video。更大的视频请使用视频URL。"},
        )
        optional["参考音频URL"] = (
            "STRING",
            {
                "multiline": False,
                "default": "",
                "tooltip": "用于音频驱动或参考音色。优先使用公开可访问 URL；会透传为 audio_url/reference_audio 等兼容字段。",
            },
        )
        optional["参考音频"] = (
            "AUDIO",
            {"tooltip": "用于音频驱动或参考音色。会打包为 wav data URL；体积建议小于 24MB。"},
        )
        optional["参考音色ID"] = (
            "STRING",
            {
                "multiline": False,
                "default": "",
                "tooltip": "如果 Tikpan/上游已返回音色 ID，可填入这里；会透传为 voice_id/reference_voice_id。",
            },
        )
        optional["保留原视频声音"] = ("BOOLEAN", {"default": True, "tooltip": "做视频编辑时是否保留原视频音轨"})

        optional["高级自定义JSON"] = (
            "STRING",
            {
                "multiline": True,
                "default": "",
                "tooltip": "深度合并到 POST /v1/video/create payload，用于 Tikpan 后续新增参数或临时调试。",
            },
        )
        optional["最长等待秒数"] = ("INT", {"default": 1200, "min": 60, "max": 7200, "step": 30, "tooltip": "等待视频生成完成的最长时间；长视频/高清建议加大"})
        optional["查询间隔秒数"] = ("INT", {"default": 8, "min": 3, "max": 60, "step": 1, "tooltip": "轮询任务状态的间隔；过小会浪费请求，过大响应慢"})
        optional["校验HTTPS证书"] = ("BOOLEAN", {"default": False, "tooltip": "默认关闭以兼容部分网络；遇到 SSL 问题可保持关闭"})
        optional["跳过错误"] = ("BOOLEAN", {"default": False, "tooltip": "开启后异常时返回空，不打断后续工作流"})

        return {
            "required": {
                "💰_福利_💰": (["🔥 0.6元≈1美金余额 | 全网底价 👉 https://tikpan.com"],),
                "获取密钥请访问": (["👉 https://tikpan.com (官方授权 Key 获取地址)"],),
                "API_密钥": ("STRING", {"default": "sk-", "tooltip": "Tikpan 平台的 API 密钥，以 sk- 开头，从 https://tikpan.com 获取"}),
                "生成指令": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": (
                            "A cinematic commercial video. Natural lighting, smooth camera motion, "
                            "high quality, subject remains consistent throughout."
                        ),
                        "tooltip": "描述你想生成的视频画面/动作/氛围，越具体越准确",
                    },
                ),
                "模型": (MODEL_OPTIONS, {"default": "omni-flash", "tooltip": "选择 omni 视频模型：flash 快，components 支持参考图"}),
                "视频时长": (DURATION_OPTIONS, {"default": "8 秒｜8", "tooltip": "生成视频的秒数；越长越慢越贵"}),
                "画面比例": (ASPECT_OPTIONS, {"default": "16:9 横屏｜16:9", "tooltip": "视频比例：16:9 横屏，9:16 竖屏短视频，1:1 方屏"}),
                "清晰度": (RESOLUTION_OPTIONS, {"default": "720p｜720p", "tooltip": "视频分辨率：1080p 更清晰但更贵更慢"}),
                "生成原生音频": ("BOOLEAN", {"default": True, "tooltip": "是否同步生成对白/环境音"}),
                "随机种子": ("INT", {"default": 888888, "min": 0, "max": 0xFFFFFFFFFFFFFFFF, "tooltip": "同种子+同提示词可复现视频；改种子可换不同结果"}),
            },
            "optional": optional,
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "VIDEO")
    RETURN_NAMES = ("📁_本地保存路径", "🆔_任务ID", "🔗_视频云端直链", "📋_完整日志", "🎬_视频输出")
    OUTPUT_NODE = True
    FUNCTION = "generate"
    CATEGORY = "👑 Tikpan 官方独家节点/02 视频 Video"
    DESCRIPTION = "📝 Gemini Omni Flash 视频：Google Gemini 视频模型，支持 720P/1080P、原生音频生成、视频编辑、参考音色驱动。适合带原生对白/音效的视频。"

    # ─── Session ────────────────────────────────────────────────────────────────
    def _create_session(self):
        session = requests.Session()
        session.trust_env = False
        # POST 不加入自动重试列表，避免双重扣费
        retry = Retry(
            total=2,
            connect=2,
            read=0,
            status=0,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=frozenset(["GET", "HEAD", "OPTIONS"]),
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _headers(self, api_key, payload=None):
        h = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Tikpan-ComfyUI-GeminiOmni/1.3",
        }
        if payload is not None:
            digest = hashlib.sha256(
                json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode()
            ).hexdigest()[:32]
            h["Idempotency-Key"] = f"tikpan-gemini-omni-{digest}"
        return h

    # ─── 图片工具 ────────────────────────────────────────────────────────────────
    def _tensor_to_data_url(self, tensor, quality=90):
        if tensor is None:
            return ""
        if len(tensor.shape) == 4:
            tensor = tensor[0]
        arr = np.clip(255.0 * tensor.detach().cpu().numpy(), 0, 255).astype(np.uint8)
        buf = BytesIO()
        Image.fromarray(arr).convert("RGB").save(buf, format="JPEG", quality=int(quality), optimize=True)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()

    def _collect_images(self, kwargs):
        images = []
        for i in range(1, MAX_REFERENCE_IMAGES + 1):
            t = pick(kwargs, f"参考图{i}", f"ref_image_{i}", default=None)
            if t is not None:
                images.append(self._tensor_to_data_url(t))
        return images

    def _guess_mime(self, path, fallback):
        mime, _ = mimetypes.guess_type(str(path or ""))
        return mime or fallback

    def _video_path_from_input(self, value):
        if value is None:
            return ""
        if isinstance(value, (list, tuple)) and value:
            return self._video_path_from_input(value[0])
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            for key in ("filename", "path", "video", "file"):
                candidate = value.get(key)
                if isinstance(candidate, str):
                    return candidate
        return str(value)

    def _video_to_data_url(self, local_video):
        path = self._video_path_from_input(local_video)
        if not path:
            return ""
        if not os.path.exists(path):
            raise ValueError(f"本地视频文件不存在: {path}")
        size = os.path.getsize(path)
        if size > MAX_INLINE_VIDEO_BYTES:
            raise ValueError(
                f"本地视频 {size / 1024 / 1024:.1f}MB 超过 inline 限制，"
                f"请上传到公开地址后填写“视频URL”。"
            )
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")
        return f"data:{self._guess_mime(path, 'video/mp4')};base64,{data}"

    def _audio_to_wav_data_url(self, audio):
        if audio is None:
            return ""
        waveform = audio.get("waveform") if isinstance(audio, dict) else None
        sample_rate = audio.get("sample_rate") if isinstance(audio, dict) else None
        if waveform is None or sample_rate is None:
            raise ValueError("参考音频不是有效的 ComfyUI AUDIO 对象")
        wf = waveform.detach().cpu().float()
        if wf.dim() == 3:
            wf = wf.squeeze(0)
        if wf.dim() == 1:
            wf = wf.unsqueeze(0)
        channels, _ = wf.shape
        wf = wf.clamp(-1.0, 1.0)
        pcm = (wf.numpy() * 32767.0).astype(np.int16)
        if channels == 1:
            interleaved = pcm[0]
        else:
            interleaved = np.transpose(pcm, (1, 0)).reshape(-1)
        buf = BytesIO()
        with wave.open(buf, "wb") as wav:
            wav.setnchannels(int(channels))
            wav.setsampwidth(2)
            wav.setframerate(int(sample_rate))
            wav.writeframes(interleaved.tobytes())
        raw = buf.getvalue()
        if len(raw) > MAX_INLINE_AUDIO_BYTES:
            raise ValueError(
                f"参考音频 {len(raw) / 1024 / 1024:.1f}MB 超过 inline 限制，"
                f"请上传到公开地址后填写“参考音频URL”。"
            )
        return "data:audio/wav;base64," + base64.b64encode(raw).decode("utf-8")

    # ─── Payload 构建 ───────────────────────────────────────────────────────────
    def _build_payload(self, model, prompt, duration, aspect_ratio, resolution,
                       generate_audio, seed, negative_prompt, images, video_ref,
                       audio_ref, voice_id, keep_original_sound, custom_json_str):
        payload = {
            "model": model,
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "duration": int(duration),
            "resolution": resolution,
            "seed": int(seed) % 2147483647,
            "generate_audio": bool(generate_audio),
        }
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt

        if video_ref:
            payload["video_url"] = video_ref
            payload["input_video"] = video_ref
            payload["reference_video"] = video_ref
            payload["video_list"] = [{
                "video_url": video_ref,
                "refer_type": "base",
                "keep_original_sound": "yes" if keep_original_sound else "no",
            }]

        if audio_ref:
            payload["audio_url"] = audio_ref
            payload["input_audio"] = audio_ref
            payload["reference_audio"] = audio_ref

        if voice_id:
            payload["voice_id"] = voice_id
            payload["reference_voice_id"] = voice_id
            payload["element_voice_id"] = voice_id

        if images:
            if model in COMPONENT_MODELS:
                # components 模型：传参考图列表
                payload["images"] = images
                # 同时保留 reference_images 作为别名，适配 Tikpan 不同上游路由
                payload["reference_images"] = images
            else:
                # omni-flash 文生视频，如果用户误接了参考图也忽略
                pass

        # 高级 JSON 合并
        if custom_json_str:
            custom_json_str = custom_json_str.strip()
            if custom_json_str:
                try:
                    payload = self._deep_merge(payload, json.loads(custom_json_str))
                except Exception as exc:
                    raise ValueError(f"高级自定义JSON 不是合法 JSON: {exc}") from exc
        return payload

    def _deep_merge(self, base, override):
        if not isinstance(base, dict) or not isinstance(override, dict):
            return override
        merged = dict(base)
        for k, v in override.items():
            if isinstance(v, dict) and isinstance(merged.get(k), dict):
                merged[k] = self._deep_merge(merged[k], v)
            else:
                merged[k] = v
        return merged

    # ─── 提交任务 ───────────────────────────────────────────────────────────────
    def _submit(self, session, api_host, payload, api_key, verify_tls):
        url = f"{api_host}{HARDCODED_ENDPOINT}"
        safe = self._redact(payload)
        print(f"[Tikpan-GeminiOmni] POST {url}\n"
              f"  payload={json.dumps(safe, ensure_ascii=False, default=str)[:1600]}", flush=True)
        response = session.post(
            url,
            json=payload,
            headers=self._headers(api_key, payload),
            timeout=(20, 180),
            verify=verify_tls,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"任务创建失败: HTTP {response.status_code}\n{response.text[:1600]}"
            )
        try:
            return response.json()
        except Exception as exc:
            raise RuntimeError(f"任务创建失败：返回不是合法 JSON\n{response.text[:1600]}") from exc

    # ─── 轮询 ────────────────────────────────────────────────────────────────────
    def _poll(self, session, api_host, task_id, api_key, max_wait, poll_interval, verify_tls, pbar):
        task = str(task_id or "").strip()
        # 优先查 /v1/video/query，再 fallback
        candidate_urls = []
        candidate_urls.append(f"{api_host}{QUERY_ENDPOINT_TEMPLATE.format(task_id=task)}")
        candidate_urls.append(f"{api_host}/v1/videos/{task}")
        candidate_urls.append(f"{api_host}/v1/videos/query?id={task}")
        # 去重
        seen = set()
        query_urls = [u for u in candidate_urls if not (u in seen or seen.add(u))]

        headers = self._headers(api_key)
        start = time.time()
        last_json = {}
        poll_count = 0

        while time.time() - start < max_wait:
            comfy.model_management.throw_exception_if_processing_interrupted()
            time.sleep(poll_interval)
            poll_count += 1
            for url in query_urls:
                try:
                    resp = session.get(url, headers=headers, timeout=(15, 60), verify=verify_tls)
                    if resp.status_code in {404, 405}:
                        continue
                    if resp.status_code >= 400:
                        continue
                    data = resp.json()
                    last_json = data
                    status = self._extract_status(data)
                    elapsed = int(time.time() - start)
                    if pbar:
                        prog = self._extract_progress(data)
                        fallback = 25 + int(elapsed * 60 / max(1, max_wait))
                        pbar.update_absolute(min(90, max(prog, fallback)), 100)
                    if poll_count % 3 == 0 or elapsed < poll_interval * 2:
                        print(f"[Tikpan-GeminiOmni] poll={poll_count} | {elapsed}s | status={status or 'pending'}", flush=True)
                    video_url = self._extract_video_url(data)
                    if self._is_success(status) or (video_url and not status):
                        if video_url:
                            return True, video_url, data
                        return False, "任务成功但响应里未找到视频 URL", data
                    if self._is_failure(status):
                        return False, f"任务失败: {self._extract_error(data)}", data
                    break
                except Exception:
                    continue

        return False, f"轮询超时（{max_wait}s），任务可能仍在上游处理中 | task_id={task_id}", last_json

    # ─── 下载 ────────────────────────────────────────────────────────────────────
    def _download(self, session, video_url, task_id, model, verify_tls):
        resp = session.get(video_url, timeout=(20, 600), verify=verify_tls)
        resp.raise_for_status()
        ct = resp.headers.get("Content-Type", "").lower()
        content = resp.content or b""
        if len(content) < 1024:
            raise RuntimeError(f"视频下载内容过小: {len(content)} bytes")
        if "text/html" in ct or content[:80].lstrip().lower().startswith((b"<!doctype", b"<html")):
            raise RuntimeError(f"视频链接返回 HTML 而非视频文件: {resp.text[:800]}")
        safe_id = str(task_id or int(time.time())).replace("/", "_").replace(":", "_")
        safe_model = model.replace("-", "_")
        save_path = os.path.join(
            folder_paths.get_output_directory(),
            f"Tikpan_GeminiOmni_{safe_model}_{safe_id}.mp4",
        )
        with open(save_path, "wb") as f:
            f.write(content)
        return save_path

    # ─── 主函数 ─────────────────────────────────────────────────────────────────
    def generate(self, **kwargs):
        pbar = comfy.utils.ProgressBar(100)
        task_id = ""
        video_url = ""
        try:
            api_key = str(pick(kwargs, "API_密钥", "api_key", default="") or "").strip()
            api_host = normalize_api_host(pick(kwargs, "中转站地址", "api_host", default=API_HOST_OPTIONS[0]))
            skip_error = bool(pick(kwargs, "跳过错误", "skip_error", default=False))
            verify_tls = bool(pick(kwargs, "校验HTTPS证书", "verify_tls", default=False))
            prompt = str(pick(kwargs, "生成指令", "prompt", default="") or "").strip()
            model = _raw(pick(kwargs, "模型", "model", default="omni-flash"), "omni-flash")
            duration = _raw(pick(kwargs, "视频时长", "duration", default="8 秒｜8"), "8")
            aspect_ratio = _raw(pick(kwargs, "画面比例", "aspect_ratio", default="16:9 横屏｜16:9"), "16:9")
            resolution = _raw(pick(kwargs, "清晰度", "resolution", default="720p｜720p"), "720p")
            generate_audio = bool(pick(kwargs, "生成原生音频", "generate_audio", default=True))
            seed = normalize_seed(pick(kwargs, "随机种子", "seed", default=888888), default=888888)
            negative_prompt = str(pick(kwargs, "负面提示词", "negative_prompt", default="") or "").strip()
            video_url = str(pick(kwargs, "视频URL", "video_url", default="") or "").strip()
            local_video = pick(kwargs, "本地视频", "local_video", default=None)
            audio_url = str(pick(kwargs, "参考音频URL", "audio_url", "reference_audio_url", default="") or "").strip()
            audio = pick(kwargs, "参考音频", "reference_audio", default=None)
            voice_id = str(pick(kwargs, "参考音色ID", "voice_id", "reference_voice_id", default="") or "").strip()
            keep_original_sound = bool(pick(kwargs, "保留原视频声音", "keep_original_sound", default=True))
            custom_json_str = str(pick(kwargs, "高级自定义JSON", "custom_json", default="") or "").strip()
            max_wait = int(pick(kwargs, "最长等待秒数", "max_wait_seconds", default=1200) or 1200)
            poll_interval = int(pick(kwargs, "查询间隔秒数", "poll_interval", default=8) or 8)

            if not api_key or api_key == "sk-" or len(api_key) < 10:
                return self._err("❌ 请填写有效的 Tikpan API 密钥", skip_error)
            if not prompt:
                return self._err("❌ 生成指令不能为空", skip_error)
            if model not in MODEL_OPTIONS:
                model = "omni-flash"

            images = self._collect_images(kwargs)
            video_ref = video_url if video_url.startswith(("http://", "https://", "data:video")) else ""
            if not video_ref and local_video is not None:
                video_ref = self._video_to_data_url(local_video)

            audio_ref = audio_url if audio_url.startswith(("http://", "https://", "data:audio")) else ""
            if not audio_ref and audio is not None:
                audio_ref = self._audio_to_wav_data_url(audio)

            if images and model not in COMPONENT_MODELS:
                print(
                    f"[Tikpan-GeminiOmni] ⚠️ 当前模型 {model} 不是 components 版本，"
                    f"参考图输入将被忽略。请切换到 omni-flash-components 以使用参考图生视频。",
                    flush=True,
                )
                images = []

            pbar.update_absolute(8, 100)
            payload = self._build_payload(
                model, prompt, duration, aspect_ratio, resolution,
                generate_audio, seed, negative_prompt, images, video_ref,
                audio_ref, voice_id, keep_original_sound, custom_json_str,
            )
            session = self._create_session()
            pbar.update_absolute(15, 100)

            create_json = self._submit(session, api_host, payload, api_key, verify_tls)
            pbar.update_absolute(25, 100)

            video_url = self._extract_video_url(create_json)
            task_id = self._extract_task_id(create_json)
            final_json = create_json

            if not video_url:
                if not task_id:
                    raise RuntimeError(
                        f"任务创建后未获取到 task_id 或视频 URL\n"
                        f"{json.dumps(create_json, ensure_ascii=False, default=str)[:1800]}"
                    )
                ok, result, final_json = self._poll(
                    session, api_host, task_id, api_key, max_wait, poll_interval, verify_tls, pbar
                )
                if not ok:
                    raise RuntimeError(result)
                video_url = result
            else:
                task_id = task_id or "sync"

            pbar.update_absolute(92, 100)
            save_path = self._download(session, video_url, task_id, model, verify_tls)
            pbar.update_absolute(100, 100)

            log = (
                f"✅ Gemini Omni 视频生成成功\n"
                f"model={model} | duration={duration}s | aspect={aspect_ratio} | resolution={resolution} | "
                f"audio={generate_audio} | refs={len(images)} | video_ref={bool(video_ref)} | "
                f"audio_ref={bool(audio_ref)} | voice_id={bool(voice_id)} | endpoint={HARDCODED_ENDPOINT}\n"
                f"task_id={task_id}\nvideo_url={video_url}\npath={save_path}\n\n"
                f"{json.dumps(self._redact(final_json), ensure_ascii=False, indent=2, default=str)[:3000]}"
            )
            print(f"[Tikpan-GeminiOmni] {log[:1200]}", flush=True)
            return (save_path, task_id, video_url, log, video_from_path(save_path))

        except Exception as exc:
            tb = traceback.format_exc()
            msg = f"❌ Gemini Omni 视频节点异常: {exc}\n{tb[:2400]}"
            print(f"[Tikpan-GeminiOmni] {msg}", flush=True)
            skip_error = bool(pick(kwargs, "跳过错误", "skip_error", default=False))
            if not skip_error:
                raise RuntimeError(msg) from exc
            return ("", task_id, video_url, msg, None)

    # ─── 工具方法 ────────────────────────────────────────────────────────────────
    def _extract_task_id(self, obj):
        if isinstance(obj, dict):
            for k in ("task_id", "taskId", "id", "operation_id", "operationId", "name"):
                v = obj.get(k)
                if isinstance(v, (str, int)) and str(v).strip():
                    return str(v).strip()
            for k in ("data", "result", "output", "task", "operation"):
                found = self._extract_task_id(obj.get(k))
                if found:
                    return found
        elif isinstance(obj, list):
            for item in obj:
                found = self._extract_task_id(item)
                if found:
                    return found
        elif isinstance(obj, str) and obj.strip():
            return obj.strip()
        return ""

    def _extract_video_url(self, obj):
        KEYS = ("video_url", "videoUrl", "output_video_url", "outputVideoUrl",
                "result_url", "output_url", "file_url", "media_url", "url", "uri",
                "fileUri", "file_uri")
        if isinstance(obj, dict):
            for k in KEYS:
                v = obj.get(k)
                if isinstance(v, str) and v.startswith(("http://", "https://")):
                    return v
            for v in obj.values():
                found = self._extract_video_url(v)
                if found:
                    return found
        elif isinstance(obj, list):
            for item in obj:
                found = self._extract_video_url(item)
                if found:
                    return found
        return ""

    def _extract_status(self, obj):
        if isinstance(obj, dict):
            for k in ("task_status", "status", "state", "phase", "job_status"):
                v = obj.get(k)
                if v:
                    return str(v).upper()
            for k in ("data", "result", "output", "task", "operation"):
                found = self._extract_status(obj.get(k))
                if found:
                    return found
        return ""

    def _extract_progress(self, obj):
        if not isinstance(obj, dict):
            return 0
        for k in ("progress", "percent", "percentage"):
            v = obj.get(k)
            if v is None:
                continue
            try:
                return max(0, min(99, int(float(str(v).replace("%", "").strip()))))
            except Exception:
                continue
        for k in ("data", "result", "output"):
            val = self._extract_progress(obj.get(k))
            if val:
                return val
        return 0

    def _extract_error(self, obj):
        if isinstance(obj, dict):
            for k in ("message", "error_message", "error", "reason", "fail_reason"):
                v = obj.get(k)
                if v:
                    return str(v)[:1200]
            return json.dumps(self._redact(obj), ensure_ascii=False, default=str)[:1200]
        return str(obj)[:1200]

    def _is_success(self, status):
        return str(status or "").upper() in {
            "SUCCESS", "SUCCEEDED", "COMPLETED", "COMPLETE", "DONE", "FINISHED"
        }

    def _is_failure(self, status):
        return str(status or "").upper() in {
            "FAILED", "FAIL", "ERROR", "CANCELED", "CANCELLED", "TIMEOUT", "EXPIRED"
        }

    def _redact(self, value):
        if isinstance(value, str):
            if value.startswith(("data:image", "data:video", "data:audio")):
                return value.split(",", 1)[0] + ",[base64 omitted]"
            return value
        if isinstance(value, list):
            return [self._redact(v) for v in value]
        if isinstance(value, dict):
            return {k: self._redact(v) for k, v in value.items()}
        return value

    def _err(self, msg, skip_error=False):
        if not skip_error:
            raise RuntimeError(msg)
        return ("", "", "", msg, None)


NODE_CLASS_MAPPINGS = {
    "TikpanGeminiOmniVideoNode": TikpanGeminiOmniVideoNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TikpanGeminiOmniVideoNode": "视频｜Gemini Omni 视频生成",
}
