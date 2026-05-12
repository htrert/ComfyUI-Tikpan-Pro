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


# ==================== API 调用 ====================

def call_gemini_native(model_id, prompt, resolution, aspect_ratio, reference_images, seed, api_key=None):
    key = api_key or API_KEY
    parts = [{"text": prompt}]
    for img_file in reference_images:
        img = Image.open(img_file).convert("RGB")
        b64 = image_to_base64(img)
        parts.append({"inlineData": {"mimeType": "image/jpeg", "data": b64}})

    gen_config = {"responseModalities": ["TEXT", "IMAGE"], "imageConfig": {"aspectRatio": aspect_ratio}}
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
    payload = {"model": model_variant, "prompt": prompt, "size": size, "n": int(n)}
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
    payload = {"model": model_version}
    if mode == "灵感模式":
        payload["gpt_description_prompt"] = prompt
        payload["make_instrumental"] = extra_params.get("make_instrumental", "false") == "true"
    elif mode == "自定义模式":
        payload["prompt"] = prompt
        payload["title"] = extra_params.get("title", "Untitled")
        payload["tags"] = extra_params.get("tags", "")
        payload["generation_type"] = extra_params.get("generation_type", "lyrics")
    elif mode == "续写模式":
        payload["continue_clip_id"] = extra_params.get("continue_clip_id", "")
        payload["continue_at"] = int(extra_params.get("continue_at", 0))
        payload["task"] = "extend"
    elif mode == "歌手风格":
        payload["prompt"] = prompt
        payload["persona_id"] = extra_params.get("persona_id", "")

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


def call_grok_video(prompt, duration, api_key=None):
    key = api_key or API_KEY
    payload = {"model": "grok-video", "prompt": prompt, "duration": duration}
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


API_DISPATCH["openai_responses"] = call_openai_responses
API_DISPATCH["gemini_analysis"] = call_gemini_analysis
