"""
📡 API 调用处理器
从 app.py 中分离出来的所有 API 调用函数
"""
import base64
import json
import os
import re
import time
from io import BytesIO
from PIL import Image
import requests
import urllib3
import uuid

from config import API_BASE_URL, API_KEY
from backend.storage import save_image

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ==================== 工具函数 ====================

def clean_base64(raw_data):
    if not raw_data:
        return ""
    raw_data = str(raw_data).strip()
    if raw_data.startswith("data:image"):
        raw_data = raw_data.split("base64,", 1)[-1]
    b64_clean = re.sub(r"[^A-Za-z0-9+/=]", "", raw_data)
    if not b64_clean:
        return ""
    missing_padding = len(b64_clean) % 4
    if missing_padding:
        b64_clean += "=" * (4 - missing_padding)
    return b64_clean


def image_to_base64(img, fmt="JPEG", quality=95):
    buf = BytesIO()
    img.save(buf, format=fmt, quality=quality)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def decode_base64_to_image(b64_data):
    cleaned = clean_base64(b64_data)
    if not cleaned:
        raise ValueError("无效的 base64 数据")
    return Image.open(BytesIO(base64.b64decode(cleaned))).convert("RGB")


def split_label_value(value):
    text = str(value or "").strip()
    return [part.strip() for part in text.split("｜") if part.strip()]


def option_value(value, default=""):
    parts = split_label_value(value)
    if not parts:
        return str(default or "").strip()
    last = parts[-1].strip()
    return last if last else str(default or "").strip()


def bool_value(value):
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "开启"}


def normalize_suno_tags(value, custom_value=""):
    custom = str(custom_value or "").strip()
    if custom:
        return custom
    parts = split_label_value(value)
    if not parts:
        return ""
    if parts[-1].lower() == "custom":
        return ""
    return parts[-1]


def normalize_tts_voice(model_id, value, data):
    text = str(value or "").strip()
    parts = split_label_value(text)
    if not parts:
        return text
    if parts[0].startswith("自定义"):
        if model_id == "gemini-3.1-flash-tts-preview":
            return str(data.get("custom_voice_name") or "").strip()
        if model_id == "doubao-tts-2.0":
            return str(data.get("custom_voice_type") or "").strip()
        return str(data.get("custom_voice_id") or "").strip()
    if model_id == "gemini-3.1-flash-tts-preview":
        return parts[0]
    return parts[-1]


def normalize_tts_style(value, custom_value=""):
    custom = str(custom_value or "").strip()
    if custom:
        return custom
    parts = split_label_value(value)
    if not parts:
        return ""
    if parts[-1].lower() == "custom":
        return ""
    return parts[-1]


def normalize_image_size(data):
    raw_size = data.get("size")
    if raw_size:
        return option_value(raw_size, raw_size)
    resolution = str(option_value(data.get("resolution"), data.get("resolution") or "1024")).strip()
    ratio = option_value(data.get("aspect_ratio"), data.get("aspect_ratio") or "1:1")
    ratio = str(ratio).split("|", 1)[0].strip().split(" ", 1)[0].strip()
    if resolution in {"Auto", "none", "沿用底图尺寸", "沿用底图比例"}:
        return resolution
    base_map = {
        "512": 512,
        "1K": 1024,
        "1K (1024)": 1024,
        "2K": 2048,
        "2K (2048)": 2048,
        "3K": 3072,
        "4K": 4096,
        "4K (官方极限 3840)": 3840,
        "720P": 1280,
        "1080P": 1920,
    }
    if "x" in resolution:
        return resolution
    base = base_map.get(resolution, 1024)
    try:
        w_ratio, h_ratio = [float(part) for part in ratio.split(":", 1)]
    except Exception:
        return "1024x1024"
    if w_ratio >= h_ratio:
        width = base
        height = int(base * h_ratio / w_ratio)
    else:
        height = base
        width = int(base * w_ratio / h_ratio)
    width = max((width // 8) * 8, 8)
    height = max((height // 8) * 8, 8)
    return f"{width}x{height}"


def build_minimax_speech_payload(model_id, data):
    voice_id = normalize_tts_voice(model_id, data.get("voice", ""), data)
    audio_format = str(data.get("audio_format") or "mp3").strip()
    return {
        "model": model_id,
        "text": str(data.get("text") or data.get("prompt") or "").strip(),
        "language_boost": str(data.get("language_boost") or "auto").strip(),
        "voice_setting": {
            "voice_id": voice_id,
            "speed": float(data.get("speed") or 1.0),
            "vol": float(data.get("volume") or 1.0),
            "pitch": int(float(data.get("pitch") or 0)),
        },
        "audio_setting": {
            "sample_rate": int(data.get("sample_rate") or 32000),
            "bitrate": int(data.get("bitrate") or 128000),
            "format": audio_format,
            "channel": int(data.get("channel") or 1),
        },
        "stream": False,
        "output_format": str(data.get("output_format") or "hex").strip(),
    }


def build_doubao_tts_payload(model_id, data):
    voice_type = normalize_tts_voice(model_id, data.get("voice", ""), data)
    return {
        "user": {"uid": str(data.get("user_id") or "tikpan_web_user")},
        "req_params": {
            "text": str(data.get("text") or data.get("prompt") or "").strip(),
            "speaker": voice_type,
            "audio_params": {
                "format": str(data.get("audio_format") or "mp3").strip(),
                "sample_rate": int(data.get("sample_rate") or 24000),
                "speech_rate": int(round((float(data.get("speed") or 1.0) - 1.0) * 100)),
                "loudness_rate": int(round((float(data.get("volume") or 1.0) - 1.0) * 100)),
                "pitch_rate": int(round((float(data.get("pitch") or 1.0) - 1.0) * 100)),
            },
            "request_id": f"web-doubao-{uuid.uuid4().hex}",
        },
    }


def build_gemini_tts_payload(model_id, data):
    voice_name = normalize_tts_voice(model_id, data.get("voice", ""), data)
    style = normalize_tts_style(data.get("style", ""), data.get("custom_style", ""))
    text = str(data.get("text") or data.get("prompt") or "").strip()
    language_code = str(data.get("language_code") or "").strip()
    if language_code == "自动":
        language_code = ""
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": f"{style}: {text}" if style else text}],
            }
        ],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": voice_name}
                }
            },
        },
    }
    if language_code:
        payload["generationConfig"]["speechConfig"]["languageCode"] = language_code
    return payload


def build_catalog_payload(model_id, data, upstream_model):
    if model_id in {"speech-2.8-hd", "speech-2.8-turbo"}:
        return build_minimax_speech_payload(model_id, data)
    if model_id == "doubao-tts-2.0":
        return build_doubao_tts_payload(model_id, data)
    if model_id == "gemini-3.1-flash-tts-preview":
        return build_gemini_tts_payload(model_id, data)
    payload = {
        "model": upstream_model,
        "prompt": data.get("prompt") or data.get("text") or data.get("user_question") or "",
    }
    if model_id in {"gpt-image-2", "gpt-image-2-all", "gpt-image-2-all-simple", "gpt-image-2-all-edit", "gpt-image-2-edit"}:
        payload["size"] = normalize_image_size(data)
    return payload


# ==================== Suno 音乐生成 ====================

def build_suno_payload(model_id, data):
    """构建 Suno 音乐生成请求体
    支持: 普通生成 / 续写 / 歌手风格 / 纯音乐
    model_id -> Suno 内部 mv 参数 映射
    """
    MV_MAP = {
        "suno-v5":    "chirp-v5",
        "suno-v4":    "chirp-v4",
        "suno-fenix": "chirp-fenix",
        "suno-auk":   "chirp-auk",
        "suno-v3.5":  "chirp-v3-5",
        "suno-v3":    "chirp-v3-0",
    }
    mv = MV_MAP.get(model_id, "chirp-v5")
    title = str(data.get("title", "") or "").strip()
    prompt = str(data.get("prompt", "") or data.get("lyrics", "")).strip()
    style = normalize_suno_tags(data.get("style", ""), data.get("custom_style", ""))
    negative_style = normalize_suno_tags(data.get("negative_style", ""), "")
    instrumental = bool_value(data.get("instrumental", False))

    payload = {
        "mv": mv,
        "title": title,
        "prompt": prompt,
        "tags": style,
        "make_instrumental": instrumental,
    }
    if negative_style:
        payload["negative_tags"] = negative_style
    # 续写模式
    continue_at = data.get("continue_at")
    continue_clip_id = str(data.get("continue_clip_id", "") or "").strip()
    if continue_clip_id:
        payload["continue_clip_id"] = continue_clip_id
        if continue_at is not None:
            payload["continue_at"] = float(continue_at)
    # 歌手风格
    persona_id = str(data.get("persona_id", "") or "").strip()
    if persona_id:
        payload["persona_id"] = persona_id
    return payload


# ==================== API 调用 ====================

def call_gemini_native(model_id, prompt, resolution, aspect_ratio, reference_images, seed, api_key=None):
    key = api_key or API_KEY
    parts = [{"text": prompt}]
    for img_file in reference_images:
        img = Image.open(img_file).convert("RGB")
        b64 = image_to_base64(img)
        parts.append({"inlineData": {"mimeType": "image/jpeg", "data": b64}})

    gen_config = {"responseModalities": ["TEXT", "IMAGE"], "imageConfig": {"aspectRatio": aspect_ratio}}
    resolution = option_value(resolution, resolution)
    aspect_ratio = option_value(aspect_ratio, aspect_ratio)
    gen_config["imageConfig"]["aspectRatio"] = aspect_ratio
    if resolution and resolution != "none" and resolution in ("1K", "2K", "4K"):
        gen_config["imageConfig"]["imageSize"] = resolution
    if seed and seed > 0:
        gen_config["seed"] = int(seed % 2147483647)

    payload = {"contents": [{"role": "user", "parts": parts}], "generationConfig": gen_config}
    url = f"{API_BASE_URL}/v1beta/models/{model_id}:generateContent"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json"}

    resp = requests.post(url, json=payload, headers=headers, timeout=(30, 400), verify=False)
    if resp.status_code != 200:
        return None, f"API 错误 ({resp.status_code}): {resp.text[:500]}"

    res_json = resp.json()
    try:
        candidates = res_json.get("candidates", [])
        for cand in candidates:
            parts_data = cand.get("content", {}).get("parts", [])
            for part in parts_data:
                inline = part.get("inlineData") or part.get("inline_data")
                if inline and inline.get("data"):
                    img = decode_base64_to_image(inline["data"])
                    filepath, filename = save_image(img)
                    text_summary = "".join(p.get("text", "") for p in parts_data if "text" in p)
                    return {"image_b64": image_to_base64(img), "width": img.width, "height": img.height,
                            "filename": filename, "filepath": filepath,
                            "text_summary": text_summary[:500] if text_summary else ""}, None
    except Exception:
        pass
    return None, "未能从响应中提取图片"


def call_doubao(prompt, model_variant, size, reference_images, n, api_key=None):
    key = api_key or API_KEY
    payload = {"model": model_variant, "prompt": prompt, "size": option_value(size, size), "n": int(n)}
    if reference_images:
        urls = []
        for f in reference_images:
            img = Image.open(f).convert("RGB")
            urls.append(f"data:image/jpeg;base64,{image_to_base64(img)}")
        payload["image_urls"] = urls

    url = f"{API_BASE_URL}/v1/images/generations"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    resp = requests.post(url, json=payload, headers=headers, timeout=(30, 120), verify=False)
    if resp.status_code != 200:
        return None, f"API 错误 ({resp.status_code}): {resp.text[:500]}"

    try:
        data_list = resp.json().get("data", [])
        if data_list:
            item = data_list[0]
            for key in ["b64_json", "url"]:
                val = item.get(key)
                if val:
                    if key == "url":
                        img_resp = requests.get(val, timeout=60, verify=False)
                        b64 = base64.b64encode(img_resp.content).decode("utf-8")
                    else:
                        b64 = clean_base64(val)
                    img = decode_base64_to_image(b64)
                    filepath, filename = save_image(img)
                    return {"image_b64": b64, "width": img.width, "height": img.height,
                            "filename": filename, "filepath": filepath}, None
    except Exception:
        pass
    return None, "未能提取图片"


def call_suno(mode, prompt, model_version, extra_params, api_key=None):
    key = api_key or API_KEY
    model_version = option_value(model_version, model_version or "chirp-fenix")
    payload = {"model": model_version}
    if mode == "灵感模式":
        payload["gpt_description_prompt"] = prompt
        payload["make_instrumental"] = bool_value(extra_params.get("make_instrumental"))
    elif mode == "自定义模式":
        payload["prompt"] = prompt
        payload["title"] = extra_params.get("title", "Untitled")
        payload["tags"] = normalize_suno_tags(extra_params.get("tags", ""), extra_params.get("custom_tags", ""))
        if extra_params.get("negative_tags"):
            payload["negative_tags"] = extra_params.get("negative_tags", "")
        payload["generation_type"] = extra_params.get("generation_type", "lyrics")
    elif mode == "续写模式":
        payload["continue_clip_id"] = extra_params.get("continue_clip_id", "")
        payload["continue_at"] = int(extra_params.get("continue_at", 0))
        payload["task"] = "extend"
    elif mode == "歌手风格":
        payload["prompt"] = prompt
        payload["persona_id"] = extra_params.get("persona_id", "")
        if extra_params.get("reference_audio_id"):
            payload["reference_audio_id"] = extra_params.get("reference_audio_id", "")

    if bool_value(extra_params.get("send_advanced")):
        vocal_gender = option_value(extra_params.get("vocal_gender"), "")
        if vocal_gender:
            payload["vocal_gender"] = vocal_gender
        payload["auto_generate_lyrics"] = bool_value(extra_params.get("auto_generate_lyrics"))
        for key_name in ("style_weight", "weirdness"):
            if extra_params.get(key_name) not in (None, ""):
                try:
                    payload[key_name] = float(extra_params.get(key_name))
                except Exception:
                    pass

    url = f"{API_BASE_URL}/v1/suno/submit/music"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    resp = requests.post(url, json=payload, headers=headers, timeout=30, verify=False)
    if resp.status_code != 200:
        return None, f"提交失败 ({resp.status_code}): {resp.text[:500]}"

    task_id = None
    result = resp.json()
    if isinstance(result, dict):
        task_id = result.get("data", {}).get("task_id") or result.get("task_id")
    if not task_id:
        return None, f"未获取到任务ID: {json.dumps(result, ensure_ascii=False)[:500]}"

    for _ in range(60):
        time.sleep(3)
        fetch_resp = requests.get(f"{API_BASE_URL}/v1/suno/fetch?id={task_id}", headers=headers, timeout=30, verify=False)
        if fetch_resp.status_code != 200:
            continue
        data = fetch_resp.json()
        suno_data = data.get("data", []) if isinstance(data, dict) else data
        if isinstance(suno_data, list) and suno_data:
            item = suno_data[0]
            if item.get("status") == "SUCCESS":
                return {"audio_url": item.get("audio_url", ""), "image_url": item.get("image_large_url", ""),
                        "title": item.get("title", ""), "lyric": (item.get("lyric", "") or "")[:500],
                        "clip_id": item.get("id", "")}, None
            elif item.get("status") in ("FAILED", "ERROR"):
                return None, f"生成失败: {item.get('error_message', '未知错误')}"
    return None, "生成超时"


def call_grok_video(prompt, duration, api_key=None, extra_params=None, reference_images=None):
    key = api_key or API_KEY
    extra_params = extra_params or {}
    payload = {
        "model": extra_params.get("model") or "grok-video",
        "prompt": prompt,
        "duration": option_value(duration, duration),
        "aspect_ratio": option_value(extra_params.get("aspect_ratio"), extra_params.get("ratio") or "9:16"),
        "resolution": option_value(extra_params.get("resolution"), "720P"),
    }
    image_urls = []
    for img_file in (reference_images or [])[:7]:
        img = Image.open(img_file).convert("RGB")
        image_urls.append(f"data:image/jpeg;base64,{image_to_base64(img, quality=88)}")
    if image_urls:
        payload["image_urls"] = image_urls
    url = f"{API_BASE_URL}/v1/video/grok"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    resp = requests.post(url, json=payload, headers=headers, timeout=(30, 120), verify=False)
    if resp.status_code != 200:
        return None, f"API 错误 ({resp.status_code}): {resp.text[:500]}"
    res_json = resp.json()
    video_url = None
    if isinstance(res_json, dict):
        video_url = res_json.get("data", {}).get("url") or res_json.get("url")
    if video_url:
        return {"video_url": video_url}, None
    return None, f"未提取到视频: {json.dumps(res_json, ensure_ascii=False)[:500]}"


# 调用分发表
API_DISPATCH = {
    "gemini_native": call_gemini_native,
    "doubao": call_doubao,
    "suno": call_suno,
    "grok_video": call_grok_video,
}


def _safe_json_preview(value, max_len=1200):
    try:
        text = json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        text = str(value)
    return text[:max_len]


def _extract_response_text(res_json):
    if isinstance(res_json, dict) and isinstance(res_json.get("output_text"), str):
        return res_json["output_text"].strip()
    texts = []

    def scan(obj):
        if isinstance(obj, dict):
            if obj.get("type") in {"output_text", "text"} and isinstance(obj.get("text"), str):
                texts.append(obj["text"])
            if isinstance(obj.get("content"), str):
                texts.append(obj["content"])
            for value in obj.values():
                scan(value)
        elif isinstance(obj, list):
            for item in obj:
                scan(item)

    scan(res_json.get("output") if isinstance(res_json, dict) else res_json)
    return "\n".join(t.strip() for t in texts if t.strip()).strip()


def _extract_usage_text(res_json):
    usage = res_json.get("usage") if isinstance(res_json, dict) else {}
    if not isinstance(usage, dict):
        return ""
    parts = []
    for source, label in [("input_tokens", "input"), ("output_tokens", "output"), ("total_tokens", "total")]:
        if usage.get(source) is not None:
            parts.append(f"{label}={usage.get(source)}")
    details = usage.get("input_tokens_details") or {}
    if isinstance(details, dict) and details.get("cached_tokens") is not None:
        parts.append(f"cached={details.get('cached_tokens')}")
    return " | ".join(parts)


def call_openai_responses(prompt, system_prompt="", reference_images=None, extra_params=None, api_key=None):
    key = api_key or API_KEY
    extra_params = extra_params or {}
    reference_images = reference_images or []
    model = extra_params.get("model") or extra_params.get("_upstream_model") or "gpt-5-mini"
    endpoint = extra_params.get("_route_endpoint") or "/v1/responses"
    content = [{"type": "input_text", "text": prompt}]

    for img_file in reference_images[:4]:
        img = Image.open(img_file).convert("RGB")
        b64 = image_to_base64(img, quality=88)
        content.append({"type": "input_image", "image_url": f"data:image/jpeg;base64,{b64}", "detail": extra_params.get("image_detail", "auto")})

    for url in str(extra_params.get("image_urls") or "").replace(",", "\n").splitlines()[:12]:
        url = url.strip()
        if url:
            content.append({"type": "input_image", "image_url": url, "detail": extra_params.get("image_detail", "auto")})

    for url in str(extra_params.get("file_urls") or "").replace(",", "\n").splitlines()[:8]:
        url = url.strip()
        if url:
            content.append({"type": "input_file", "file_url": url})

    payload = {
        "model": model,
        "instructions": system_prompt or "你是 Tikpan 的商业级 AI 助手，回答要准确、结构化、可执行。",
        "input": [{"role": "user", "content": content}],
        "reasoning": {"effort": extra_params.get("reasoning_effort", "low")},
        "text": {"verbosity": extra_params.get("verbosity", "medium")},
        "max_output_tokens": int(extra_params.get("max_output_tokens", 4096) or 4096),
    }
    if extra_params.get("output_format") == "json":
        payload["text"]["format"] = {"type": "json_object"}
    if str(extra_params.get("web_search", "")).lower() in {"1", "true", "yes", "on"}:
        payload["tools"] = [{"type": "web_search_preview"}]

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Idempotency-Key": f"web-gpt5-mini-{uuid.uuid4().hex}",
    }
    resp = requests.post(f"{API_BASE_URL}{endpoint}", json=payload, headers=headers, timeout=(20, 420), verify=True)
    if resp.status_code != 200:
        return None, f"API 错误 ({resp.status_code}): {resp.text[:800]}"
    try:
        res_json = resp.json()
    except Exception:
        return None, f"接口返回非 JSON: {resp.text[:800]}"
    if isinstance(res_json, dict) and res_json.get("error"):
        return None, f"上游返回错误: {_safe_json_preview(res_json.get('error'))}"
    answer = _extract_response_text(res_json)
    if not answer:
        return None, f"未提取到回答文本: {_safe_json_preview(res_json)}"
    return {
        "text": answer,
        "usage": _extract_usage_text(res_json),
        "request_id": res_json.get("id", "") if isinstance(res_json, dict) else "",
        "raw_preview": _safe_json_preview(res_json, 2000),
    }, None


def call_gemini_analysis(prompt, reference_images=None, extra_params=None, api_key=None):
    key = api_key or API_KEY
    extra_params = extra_params or {}
    reference_images = reference_images or []
    model = extra_params.get("model") or extra_params.get("_upstream_model") or "gemini-3-flash-preview"
    endpoint = extra_params.get("_route_endpoint") or f"/v1beta/models/{model}:generateContent"
    parts = [{"text": prompt}]

    for img_file in reference_images[:4]:
        img = Image.open(img_file).convert("RGB")
        b64 = image_to_base64(img, quality=88)
        parts.append({"inlineData": {"mimeType": "image/jpeg", "data": b64}})

    for url in str(extra_params.get("image_urls") or "").replace(",", "\n").splitlines()[:12]:
        url = url.strip()
        if url:
            parts.append({"file_data": {"file_uri": url, "mime_type": "image/jpeg"}})

    video_url = str(extra_params.get("video_url") or "").strip()
    if video_url:
        parts.append({"file_data": {"file_uri": video_url, "mime_type": "video/mp4"}})

    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature": float(extra_params.get("temperature", 0.3) or 0.3),
            "maxOutputTokens": int(extra_params.get("max_output_tokens", 4096) or 4096),
        },
    }
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Idempotency-Key": f"web-gemini-analysis-{uuid.uuid4().hex}",
    }
    resp = requests.post(f"{API_BASE_URL}{endpoint}", json=payload, headers=headers, timeout=(20, 420), verify=True)
    if resp.status_code != 200:
        return None, f"API 错误 ({resp.status_code}): {resp.text[:800]}"
    try:
        res_json = resp.json()
    except Exception:
        return None, f"接口返回非 JSON: {resp.text[:800]}"
    if isinstance(res_json, dict) and res_json.get("error"):
        return None, f"上游返回错误: {_safe_json_preview(res_json.get('error'))}"

    texts = []

    def scan(obj):
        if isinstance(obj, dict):
            if isinstance(obj.get("text"), str):
                texts.append(obj["text"])
            for value in obj.values():
                scan(value)
        elif isinstance(obj, list):
            for item in obj:
                scan(item)

    scan(res_json.get("candidates") if isinstance(res_json, dict) else res_json)
    answer = "\n".join(t.strip() for t in texts if t.strip()).strip()
    if not answer:
        return None, f"未提取到分析文本: {_safe_json_preview(res_json)}"
    return {
        "text": answer,
        "usage": _extract_usage_text(res_json),
        "request_id": res_json.get("id", "") if isinstance(res_json, dict) else "",
        "raw_preview": _safe_json_preview(res_json, 2000),
    }, None


def _extract_first_url(obj):
    if isinstance(obj, dict):
        for key in ("secure_url", "url", "image_url", "video_url", "audio_url", "output_url"):
            value = obj.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                return value
        for value in obj.values():
            found = _extract_first_url(value)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _extract_first_url(item)
            if found:
                return found
    return ""


def _extract_first_b64(obj):
    if isinstance(obj, dict):
        for key in ("b64_json", "image_b64", "base64", "data"):
            value = obj.get(key)
            if isinstance(value, str) and len(value) > 200:
                return clean_base64(value)
        for value in obj.values():
            found = _extract_first_b64(value)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _extract_first_b64(item)
            if found:
                return found
    return ""

def reference_image_limit(model_id):
    if model_id in {"gpt-image-2", "gpt-image-2-all", "gpt-image-2-all-edit", "gpt-image-2-edit"}:
        return 16
    if model_id in {"grok-imagine-image-edit", "grok-imagine-image-pro-edit", "grok-imagine-image", "grok-imagine-image-pro"}:
        return 3
    return 14

def is_grok_image_edit(model_id, endpoint):
    return (
        str(endpoint).rstrip("/") == "/v1/images/edits"
        and model_id in {"grok-imagine-image-edit", "grok-imagine-image-pro-edit", "grok-imagine-image", "grok-imagine-image-pro"}
    )

def call_tikpan_proxy(model_id, data, reference_images=None, api_key=None):
    """Generic Tikpan JSON proxy for catalog-backed models.

    Specific handlers remain preferred for mature models. This fallback lets new
    catalog entries be previewed and tested before a dedicated handler exists.
    """
    key = api_key or API_KEY
    reference_images = reference_images or []
    endpoint = data.get("_route_endpoint") or data.get("endpoint") or "/v1/responses"
    upstream_model = data.get("_upstream_model") or data.get("model") or model_id
    normalized_voice = normalize_tts_voice(model_id, data.get("voice", ""), data)
    normalized_style = normalize_tts_style(data.get("style", ""), data.get("custom_style", ""))
    payload = build_catalog_payload(model_id, data, upstream_model)
    structured_tts_payload = model_id in {"speech-2.8-hd", "speech-2.8-turbo", "doubao-tts-2.0", "gemini-3.1-flash-tts-preview"}
    for key_name, value in data.items():
        if key_name.startswith("_") or key_name in {"api_key", "idempotency_key"}:
            continue
        if structured_tts_payload:
            continue
        if key_name == "voice":
            value = normalized_voice or value
        elif key_name == "style":
            value = normalized_style
        elif key_name in {"quality", "moderation", "background", "output_format", "response_format", "duration", "aspect_ratio", "watermark"}:
            value = option_value(value, value)
        elif key_name in {"custom_voice_id", "custom_voice_name", "custom_voice_type", "custom_style"}:
            continue
        payload[key_name] = value

    image_payloads = []
    for img_file in reference_images[:reference_image_limit(model_id)]:
        img = Image.open(img_file).convert("RGB")
        image_payloads.append(f"data:image/jpeg;base64,{image_to_base64(img, quality=88)}")
    if image_payloads:
        if is_grok_image_edit(model_id, endpoint):
            grok_images = [{"type": "image_url", "url": image_url} for image_url in image_payloads[:3]]
            if len(grok_images) == 1:
                payload["image"] = grok_images[0]
            else:
                payload["images"] = grok_images
        else:
            payload["image_urls"] = image_payloads

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Idempotency-Key": f"web-tikpan-proxy-{uuid.uuid4().hex}",
    }
    url = f"{API_BASE_URL}{endpoint if str(endpoint).startswith('/') else '/' + str(endpoint)}"
    resp = requests.post(url, json=payload, headers=headers, timeout=(20, 420), verify=True)
    if resp.status_code >= 400:
        return None, f"API 错误 ({resp.status_code}): {resp.text[:1000]}"
    try:
        res_json = resp.json()
    except Exception:
        text = resp.text.strip()
        if text.startswith(("http://", "https://")):
            return {"url": text, "raw_preview": text[:1000]}, None
        return {"text": text[:4000], "raw_preview": text[:1000]}, None

    b64 = _extract_first_b64(res_json)
    if b64:
        try:
            img = decode_base64_to_image(b64)
            filepath, filename = save_image(img)
            return {
                "image_b64": b64,
                "width": img.width,
                "height": img.height,
                "filename": filename,
                "filepath": filepath,
                "raw_preview": _safe_json_preview(res_json, 2000),
            }, None
        except Exception:
            pass

    first_url = _extract_first_url(res_json)
    result = {
        "request_id": res_json.get("id", "") if isinstance(res_json, dict) else "",
        "raw_preview": _safe_json_preview(res_json, 2000),
    }
    if first_url:
        if any(part in first_url.lower() for part in (".mp4", ".mov", ".webm", "video")):
            result["video_url"] = first_url
        elif any(part in first_url.lower() for part in (".mp3", ".wav", ".flac", "audio")):
            result["audio_url"] = first_url
        else:
            result["image_url"] = first_url
    else:
        result["text"] = _extract_response_text(res_json) or _safe_json_preview(res_json, 2000)
    return result, None


API_DISPATCH["openai_responses"] = call_openai_responses
API_DISPATCH["gemini_analysis"] = call_gemini_analysis
API_DISPATCH["tikpan_proxy"] = call_tikpan_proxy
