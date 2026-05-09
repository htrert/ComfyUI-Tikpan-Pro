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
