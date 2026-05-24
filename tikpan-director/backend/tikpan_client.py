"""
Tikpan AI Director — tikpan.com API 客户端
所有 AI 调用的统一出口
"""
import os
import json
import base64
import hashlib
import requests
from io import BytesIO
from PIL import Image

API_HOST = os.environ.get("TIKPAN_API_HOST", "https://tikpan.com")
API_KEY  = os.environ.get("TIKPAN_API_KEY", "")


def _headers(extra=None):
    h = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "Tikpan-Director/0.1",
    }
    if extra:
        h.update(extra)
    return h


def _idem(prefix, payload):
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()[:24]
    return f"{prefix}-{digest}"


# ─── LLM 剧本生成 ──────────────────────────────────────────────────────────

def generate_script(story_idea, genre="comic", episode_count=1,
                    world_setting="", characters=None, model="gemini-3.5-flash"):
    """
    输入故事创意 → 输出结构化剧本 JSON
    返回格式:
    {
      "title": "...",
      "episodes": [
        {
          "episode_num": 1,
          "title": "第一集标题",
          "synopsis": "本集梗概",
          "storyboards": [
            {
              "seq": 1,
              "scene_desc": "画面描述（用于分镜图）",
              "dialogue": "角色对话或旁白",
              "shot_type": "close|medium|wide",
              "camera_move": "static|push_in|pull_out|orbit|pan",
              "character_names": ["角色A"],
              "emotion": "excited|sad|calm|angry|surprised"
            }
          ]
        }
      ]
    }
    """
    char_list = ""
    if characters:
        char_list = "\n".join(f"- {c['name']}: {c.get('description', '')}" for c in characters)

    system_prompt = f"""你是一位专业的 AI {"漫剧" if genre == "comic" else "短剧"} 导演助手。
你的任务是根据用户的故事创意，创作结构化的分镜剧本。

要求：
1. 每集包含 6-12 个分镜
2. 每个分镜必须有清晰的画面描述（scene_desc），用于 AI 图片生成
3. 画面描述要包含：人物动作、场景环境、光影氛围、镜头角度
4. 对话要简洁有力，符合角色性格
5. 输出严格的 JSON 格式，不要有任何额外文字

已有角色设定：
{char_list if char_list else "（无，请自行创建角色）"}

世界观设定：
{world_setting if world_setting else "（无特殊设定）"}

剧目类型：{genre}
集数要求：{episode_count}集"""

    user_prompt = f"故事创意：{story_idea}\n\n请按上述格式输出完整的 JSON 剧本，只输出 JSON，不要有其他内容。"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.8,
        "max_tokens": 8000,
        "response_format": {"type": "json_object"},
    }
    idem = _idem("script", {"idea": story_idea[:100], "genre": genre})

    try:
        resp = requests.post(
            f"{API_HOST}/v1/chat/completions",
            json=payload,
            headers=_headers({"Idempotency-Key": idem}),
            timeout=120,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return json.loads(content), None
    except Exception as e:
        return None, str(e)


# ─── 分镜提示词优化 ────────────────────────────────────────────────────────

def optimize_image_prompt(scene_desc, character_descriptions, scene_style,
                          shot_type, emotion, model="gemini-3.5-flash"):
    """把分镜描述优化成精准的图片生成提示词（正向+负向）"""
    char_desc = "\n".join(f"- {c}" for c in character_descriptions) if character_descriptions else "无特定角色"

    prompt = f"""将以下分镜描述优化为高质量的 AI 图片生成提示词。

分镜描述：{scene_desc}
情感基调：{emotion}
景别：{shot_type}（close=特写, medium=中景, wide=全景）
画风风格：{scene_style if scene_style else "漫画风格，精美插画"}
出场角色：
{char_desc}

要求：
- 正向提示词：50词以内，英文，包含人物特征、场景、光效、构图、画风
- 负向提示词：20词以内，英文，排除低质量和不需要的元素
- 输出严格 JSON：{{"positive": "...", "negative": "..."}}"""

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.4,
        "max_tokens": 400,
        "response_format": {"type": "json_object"},
    }
    try:
        resp = requests.post(
            f"{API_HOST}/v1/chat/completions",
            json=payload, headers=_headers(), timeout=30,
        )
        resp.raise_for_status()
        return json.loads(resp.json()["choices"][0]["message"]["content"]), None
    except Exception as e:
        return None, str(e)


# ─── 图片生成 ─────────────────────────────────────────────────────────────

def generate_image(
    positive_prompt, negative_prompt="",
    reference_images=None,   # list of base64 data URLs
    resolution="2K",
    aspect_ratio="9:16",
    model="gpt-image-2-gen",
    seed=None,
):
    """
    调用攀升AI图片生成接口
    reference_images: 角色参考图列表（data URL 格式）
    返回: (image_url_or_b64, error)
    """
    if reference_images and len(reference_images) > 0:
        # 多参考图用 GPT-Image-2-all 或 Gemini
        endpoint = "/v1/images/generations"
        payload = {
            "model": model,
            "prompt": positive_prompt,
            "n": 1,
            "aspect_ratio": aspect_ratio,
            "resolution": resolution.lower().replace("k", "K"),
            "response_format": "b64_json",
        }
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        if seed:
            payload["seed"] = int(seed) % 2147483647
        # 参考图
        if len(reference_images) == 1:
            payload["image"] = {"type": "image_url", "url": reference_images[0]}
        else:
            payload["images"] = [{"type": "image_url", "url": img} for img in reference_images[:14]]
    else:
        # 无参考图用官方生图
        endpoint = "/v1/images/generations"
        payload = {
            "model": "gpt-image-2-official" if "official" in model else model,
            "prompt": positive_prompt,
            "n": 1,
            "aspect_ratio": aspect_ratio,
            "resolution": resolution.lower().replace("k", "K"),
            "response_format": "b64_json",
        }
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        if seed:
            payload["seed"] = int(seed) % 2147483647

    idem = _idem("img", {"prompt": positive_prompt[:80], "model": model, "ar": aspect_ratio})
    try:
        resp = requests.post(
            f"{API_HOST}{endpoint}",
            json=payload,
            headers=_headers({"Idempotency-Key": idem}),
            timeout=180,
        )
        resp.raise_for_status()
        data = resp.json()

        # 提取结果
        items = data.get("data", [])
        if items:
            item = items[0]
            if item.get("b64_json"):
                return f"data:image/png;base64,{item['b64_json']}", None
            if item.get("url"):
                return item["url"], None
        return None, f"上游未返回图片: {json.dumps(data)[:400]}"
    except Exception as e:
        return None, str(e)


# ─── TTS 配音 ─────────────────────────────────────────────────────────────

def generate_tts(
    text, voice="BV700_V2_streaming", model="doubao-tts-2.0",
    speed=1.0, audio_format="mp3"
):
    """调用攀升AI TTS 接口生成配音"""
    payload = {
        "user": {"uid": "director_user"},
        "req_params": {
            "text": text,
            "speaker": voice,
            "audio_params": {
                "format": audio_format,
                "sample_rate": 24000,
                "speech_rate": int((speed - 1.0) * 100),
                "loudness_rate": 0,
                "pitch_rate": 0,
            },
            "request_id": _idem("tts", {"text": text[:100], "voice": voice}),
        },
    }
    try:
        resp = requests.post(
            f"{API_HOST}/api/v3/tts/unidirectional/sse",
            json=payload, headers=_headers(), timeout=120,
        )
        resp.raise_for_status()
        result = resp.json()
        # 豆包 TTS 返回 audio 字段（base64 hex 或直链）
        audio_data = result.get("data", {}).get("audio")
        if audio_data:
            if isinstance(audio_data, str) and audio_data.startswith("http"):
                return audio_data, None
            # hex or base64 → data URL
            try:
                raw = bytes.fromhex(audio_data)
            except Exception:
                raw = base64.b64decode(audio_data)
            b64 = base64.b64encode(raw).decode()
            return f"data:audio/{audio_format};base64,{b64}", None
        return None, f"TTS 未返回音频: {str(result)[:400]}"
    except Exception as e:
        return None, str(e)


# ─── Suno 音乐 ─────────────────────────────────────────────────────────────

def generate_music(prompt, style="cinematic, background music", model="chirp-v5"):
    """生成剧集背景音乐"""
    payload = {
        "mv": model,
        "prompt": prompt,
        "tags": style,
        "make_instrumental": True,
    }
    try:
        resp = requests.post(
            f"{API_HOST}/suno/generate",
            json=payload, headers=_headers(), timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()
        task_id = result.get("task_id") or result.get("id")
        return task_id, None
    except Exception as e:
        return None, str(e)


def poll_music_task(task_id):
    """轮询 Suno 音乐任务"""
    try:
        resp = requests.get(
            f"{API_HOST}/suno/fetch/{task_id}",
            headers=_headers(), timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()
        # 提取音频 URL
        for key in ("audio_url", "url"):
            url = result.get(key)
            if url and url.startswith("http"):
                return url, True, None
        # 嵌套结构
        for item in (result.get("data") or []):
            url = item.get("audio_url") or item.get("url")
            if url:
                return url, True, None
        return None, False, None
    except Exception as e:
        return None, False, str(e)


# ─── 图片保存工具 ──────────────────────────────────────────────────────────

def save_base64_image(b64_data_url, output_dir, filename=None):
    """保存 base64 图片到本地，返回相对路径"""
    import uuid, os
    if not filename:
        filename = f"{uuid.uuid4().hex[:12]}.png"
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)
    if b64_data_url.startswith("data:"):
        _, encoded = b64_data_url.split(",", 1)
        raw = base64.b64decode(encoded)
    else:
        raw = base64.b64decode(b64_data_url)
    with open(filepath, "wb") as f:
        f.write(raw)
    return filename


def download_and_save(url, output_dir, filename=None):
    """从 URL 下载文件到本地，返回相对路径"""
    import uuid, os
    try:
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        if not filename:
            ext = url.split(".")[-1].split("?")[0].lower()
            ext = ext if ext in ("png","jpg","jpeg","webp","mp3","wav","mp4") else "bin"
            filename = f"{uuid.uuid4().hex[:12]}.{ext}"
        os.makedirs(output_dir, exist_ok=True)
        with open(os.path.join(output_dir, filename), "wb") as f:
            f.write(resp.content)
        return filename
    except Exception:
        return None
