"""
Audio Generation API — TTS + 音乐生成的统一端点
支持同步（短文本TTS）和异步（长文本/音乐）两种模式
预留 video 端点骨架，后续启用只需实现 _dispatch_video
"""
import hashlib
import uuid
import time
from pathlib import Path

from flask import Blueprint, jsonify, request

from backend.database import get_model
from backend.handlers import (
    build_minimax_speech_payload,
    build_gemini_tts_payload,
    build_doubao_tts_payload,
    build_suno_payload,
    option_value,
)
from backend.storage import save_audio
from core.auth import login_required
from core.billing import deduct_credits, quote_credits
from models import (
    get_generation_by_idempotency,
    get_user,
    log_generation,
    select_model_route,
    update_balance,
    update_generation_log,
)
import requests

bp = Blueprint("api_audio", __name__, url_prefix="/api")

MAX_TTS_CHARS = 10_000
MAX_PROMPT_CHARS = 2_000

# ─── 计费辅助 ─────────────────────────────────────────────────────────────

def _tts_credits(model_id: str, char_count: int, pricing) -> int:
    """按字符数计费：unit_credits = 每千字符积分，min_credits = 最低扣费"""
    if not pricing:
        return 2
    per_1k = float(pricing.get("unit_credits") or 2)
    min_c = int(pricing.get("min_credits") or 1)
    computed = max(min_c, int(per_1k * char_count / 1000))
    return computed


def _per_call_credits(pricing) -> int:
    """按次计费"""
    if not pricing:
        return 10
    return int(pricing.get("unit_credits") or pricing.get("credits_1k") or 10)


# ─── 进度阶段定义 ─────────────────────────────────────────────────────────

AUDIO_STAGES = [
    {"key": "user",     "label": "用户",   "detail": "鉴权与账户识别"},
    {"key": "server",   "label": "服务器", "detail": "参数校验与任务建档"},
    {"key": "billing",  "label": "计费",   "detail": "余额预扣"},
    {"key": "upstream", "label": "上游",   "detail": "模型请求与生成等待"},
    {"key": "oss",      "label": "存储",   "detail": "音频保存"},
    {"key": "cdn",      "label": "CDN",    "detail": "生成可访问链接"},
]


def _progress(active="server", failed="", message=""):
    return {"active": active, "failed": failed, "message": message, "stages": AUDIO_STAGES}


def _err(msg, status=500, stage="server", job_id=None):
    p = {"error": str(msg), "stage": stage, "progress": _progress(stage, stage, str(msg))}
    if job_id:
        p["job_id"] = job_id
    return jsonify(p), status


# ─── TTS 端点 ─────────────────────────────────────────────────────────────

@bp.route("/audio/tts", methods=["POST"])
@login_required
def tts_generate():
    """文字转语音生成（同步模式，适合 < 3000 字符）"""
    data = request.get_json(force=True) or {}
    user_id = request.user_id  # type: ignore

    model_id = str(data.get("model_id", "")).strip()
    text = str(data.get("text", "") or data.get("prompt", "")).strip()

    if not model_id:
        return _err("请选择语音模型", 400)
    if not text:
        return _err("合成文本不能为空", 400)
    if len(text) > MAX_TTS_CHARS:
        return _err(f"文本过长，最多 {MAX_TTS_CHARS} 字符", 400)

    pricing = get_model(model_id)
    if not pricing:
        return _err(f"未知模型: {model_id}", 400)

    char_count = len(text)
    cost = _tts_credits(model_id, char_count, pricing)

    idempotency_key = (
        request.headers.get("Idempotency-Key")
        or data.get("idempotency_key")
        or hashlib.sha256(f"{user_id}:{model_id}:{text[:200]}:{data.get('voice','')}".encode()).hexdigest()[:32]
    )

    # 幂等检查
    existing = get_generation_by_idempotency(user_id, idempotency_key)
    if existing and existing.get("status") == "success":
        return jsonify({
            "job_id": existing.get("request_id", ""),
            "audio_url": existing.get("image_url", ""),
            "char_count": char_count,
            "credits_used": existing.get("credits_used", cost),
            "cached": True,
            "progress": _progress("cdn"),
        })

    user = get_user(user_id)
    if not user:
        return _err("用户不存在", 401, "user")
    if user["balance"] < cost:
        return _err(f"积分不足，需要 {cost} 积分，当前余额 {user['balance']}", 402, "billing")

    job_id = str(uuid.uuid4())
    log_id = log_generation(
        user_id=user_id, model=model_id,
        credits_used=cost, prompt=text[:500],
        status="pending", request_id=job_id,
        idempotency_key=idempotency_key,
    )

    # 预扣积分
    ok = deduct_credits(user_id, cost, "tts_generation", str(log_id), idempotency_key)
    if not ok:
        update_generation_log(log_id, status="failed", error_message="积分扣减失败")
        return _err("积分扣减失败", 500, "billing", job_id)

    # 选择上游渠道
    route = select_model_route(model_id)
    api_host = (route or {}).get("base_url") or "https://tikpan.com"
    api_key = (route or {}).get("api_key") or ""

    # 构建 payload
    try:
        payload, endpoint, headers_extra = _build_tts_payload(model_id, data, api_host, api_key)
    except Exception as e:
        update_generation_log(log_id, status="failed", error_message=str(e))
        update_balance(user_id, cost, "refund", "generation", str(log_id))
        return _err(f"参数构建失败: {e}", 400, "server", job_id)

    # 调用上游
    try:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        headers.update(headers_extra)
        resp = requests.post(
            f"{api_host}{endpoint}", json=payload, headers=headers, timeout=120
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:600]}")
        result = resp.json()
    except Exception as e:
        update_generation_log(log_id, status="failed", error_message=str(e))
        update_balance(user_id, cost, "refund", "generation", str(log_id))
        return _err(f"上游请求失败: {e}", 502, "upstream", job_id)

    # 提取音频 URL / base64
    audio_url = _extract_audio_url(result)
    if not audio_url:
        update_generation_log(log_id, status="failed", error_message="上游未返回音频")
        update_balance(user_id, cost, "refund", "generation", str(log_id))
        return _err("上游未返回音频数据", 502, "upstream", job_id)

    # 保存
    saved_url = save_audio(audio_url, job_id) or audio_url
    update_generation_log(log_id, status="success", image_url=saved_url)

    return jsonify({
        "job_id": job_id,
        "audio_url": saved_url,
        "char_count": char_count,
        "credits_used": cost,
        "model": model_id,
        "progress": _progress("cdn"),
    })


# ─── 音乐生成端点 ─────────────────────────────────────────────────────────

@bp.route("/audio/music", methods=["POST"])
@login_required
def music_generate():
    """AI 音乐生成（Suno 系列，异步提交 + 轮询）"""
    data = request.get_json(force=True) or {}
    user_id = request.user_id  # type: ignore

    model_id = str(data.get("model_id", "suno-v5")).strip()
    prompt = str(data.get("prompt", "")).strip()
    style = str(data.get("style", "")).strip()

    if not prompt and not style:
        return _err("请填写创作提示词或风格标签", 400)

    pricing = get_model(model_id)
    cost = _per_call_credits(pricing)

    idempotency_key = (
        request.headers.get("Idempotency-Key")
        or hashlib.sha256(f"{user_id}:{model_id}:{prompt[:200]}:{style}".encode()).hexdigest()[:32]
    )

    existing = get_generation_by_idempotency(user_id, idempotency_key)
    if existing and existing.get("status") == "success":
        return jsonify({
            "job_id": existing.get("request_id", ""),
            "audio_url": existing.get("image_url", ""),
            "cached": True,
            "progress": _progress("cdn"),
        })

    user = get_user(user_id)
    if not user or user["balance"] < cost:
        return _err(f"积分不足（需要 {cost} 积分）", 402, "billing")

    job_id = str(uuid.uuid4())
    log_id = log_generation(
        user_id=user_id, model=model_id,
        credits_used=cost, prompt=prompt[:500],
        status="pending", request_id=job_id,
        idempotency_key=idempotency_key,
    )
    deduct_credits(user_id, cost, "music_generation", str(log_id), idempotency_key)

    route = select_model_route(model_id)
    api_host = (route or {}).get("base_url") or "https://tikpan.com"
    api_key = (route or {}).get("api_key") or ""

    payload = build_suno_payload(model_id, data)
    try:
        resp = requests.post(
            f"{api_host}/suno/generate",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=30,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:600]}")
        result = resp.json()
    except Exception as e:
        update_generation_log(log_id, status="failed", error_message=str(e))
        update_balance(user_id, cost, "refund", "generation", str(log_id))
        return _err(f"上游提交失败: {e}", 502, "upstream", job_id)

    task_id = result.get("task_id") or result.get("id") or job_id
    audio_url = _extract_audio_url(result) or ""
    status = "pending" if not audio_url else "success"
    update_generation_log(log_id, status=status, image_url=audio_url, raw_response=str(result)[:2000])

    return jsonify({
        "job_id": job_id,
        "task_id": task_id,
        "audio_url": audio_url,
        "status": status,
        "credits_used": cost,
        "model": model_id,
        "progress": _progress("upstream" if status == "pending" else "cdn"),
    })


# ─── 任务查询端点（TTS 异步 / 音乐轮询）──────────────────────────────────

@bp.route("/audio/task/<task_id>", methods=["GET"])
@login_required
def audio_task_status(task_id: str):
    """查询音频任务状态"""
    model_id = request.args.get("model_id", "suno-v5")
    route = select_model_route(model_id)
    api_host = (route or {}).get("base_url") or "https://tikpan.com"
    api_key = (route or {}).get("api_key") or ""

    try:
        resp = requests.get(
            f"{api_host}/suno/fetch/{task_id}",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30,
        )
        result = resp.json()
    except Exception as e:
        return _err(str(e), 502)

    audio_url = _extract_audio_url(result) or ""
    done = bool(audio_url) or str(result.get("status", "")).lower() in {"complete", "success", "done"}
    return jsonify({"task_id": task_id, "done": done, "audio_url": audio_url, "raw": result})


# ─── VIDEO 骨架端点（后续启用，现在返回 501）────────────────────────────

@bp.route("/video/generate", methods=["POST"])
@login_required
def video_generate():
    """视频生成端点（骨架，v2.0 启用）"""
    return jsonify({
        "error": "视频生成功能即将开放，敬请期待",
        "code": "VIDEO_COMING_SOON",
    }), 501


@bp.route("/video/task/<task_id>", methods=["GET"])
@login_required
def video_task_status(task_id: str):
    """视频任务查询（骨架，v2.0 启用）"""
    return jsonify({"error": "VIDEO_COMING_SOON"}), 501


# ─── 内部工具函数 ─────────────────────────────────────────────────────────

def _build_tts_payload(model_id, data, api_host, api_key):
    """根据 model_id 构建 TTS payload、endpoint 和额外 headers"""
    if "minimax" in model_id or "speech-2.8" in model_id:
        payload = build_minimax_speech_payload(model_id, data)
        endpoint = "/minimax/v1/t2a_v2"
        return payload, endpoint, {}
    elif "gemini" in model_id and "tts" in model_id:
        payload = build_gemini_tts_payload(model_id, data)
        endpoint = "/v1beta/models/gemini-3.1-flash-tts-preview:generateContent"
        return payload, endpoint, {}
    elif "doubao" in model_id or "tts-2.0" in model_id:
        payload = build_doubao_tts_payload(model_id, data)
        endpoint = "/api/v3/tts/unidirectional/sse"
        return payload, endpoint, {}
    else:
        # 通用 OpenAI TTS 兼容
        payload = {
            "model": model_id,
            "input": str(data.get("text", "") or data.get("prompt", "")).strip(),
            "voice": str(data.get("voice", "alloy")).strip(),
            "response_format": str(data.get("audio_format", "mp3")).strip(),
        }
        return payload, "/v1/audio/speech", {}


def _extract_audio_url(result):
    """从各种上游返回结构中提取音频 URL"""
    if not isinstance(result, dict):
        return ""
    # 直接 URL 字段
    for key in ("audio_url", "audioUrl", "url", "file_url", "download_url"):
        v = result.get(key)
        if isinstance(v, str) and v.startswith("http"):
            return v
    # 嵌套结构
    for key in ("data", "output", "result", "clips"):
        sub = result.get(key)
        if isinstance(sub, dict):
            found = _extract_audio_url(sub)
            if found:
                return found
        elif isinstance(sub, list) and sub:
            for item in sub:
                found = _extract_audio_url(item) if isinstance(item, dict) else ""
                if found:
                    return found
    # base64 音频（直接返回 data URL）
    b64 = result.get("audio_data") or result.get("b64_json")
    if b64:
        fmt = result.get("format", "mp3")
        return f"data:audio/{fmt};base64,{b64}"
    return ""
