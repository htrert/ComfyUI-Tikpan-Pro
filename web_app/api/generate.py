"""
Generation API: charge user balance, call upstream provider, and keep an
auditable job record for every attempt.
"""
import traceback
import uuid

from flask import Blueprint, jsonify, request

from backend.database import get_model
from backend.handlers import API_DISPATCH
from backend.handlers import normalize_image_size, option_value
from backend.storage import get_image_url, is_oss_enabled
from config import generate_image_token
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

bp = Blueprint("api_generate", __name__, url_prefix="/api")

MAX_PROMPT_CHARS = 8000
MAX_REFERENCE_IMAGES = 16

PROGRESS_STAGES = [
    {"key": "user", "label": "用户", "detail": "登录鉴权与账户识别"},
    {"key": "server", "label": "服务器", "detail": "参数校验与任务建档"},
    {"key": "billing", "label": "计费", "detail": "余额预扣与幂等保护"},
    {"key": "upstream", "label": "上游", "detail": "模型网关请求与生成等待"},
    {"key": "oss", "label": "OSS", "detail": "结果保存到本地或对象存储"},
    {"key": "cdn", "label": "CDN", "detail": "生成可访问结果链接"},
]


def _progress_payload(active="server", failed="", message=""):
    return {
        "active": active,
        "failed": failed,
        "message": message,
        "stages": PROGRESS_STAGES,
    }


def _error_response(error, status=500, stage="server", job_id=None, raw_response=""):
    payload = {
        "error": str(error),
        "stage": stage,
        "progress": _progress_payload(stage, stage, str(error)),
    }
    if job_id:
        payload["job_id"] = job_id
    if raw_response:
        payload["raw_response"] = raw_response[:1200]
    return jsonify(payload), status


def _validate_generation_input(data, files):
    model_id = str(data.get("model_id", "")).strip()
    prompt = str(data.get("prompt", "")).strip()
    if not model_id:
        return None, None, "请选择模型"
    if prompt and len(prompt) > MAX_PROMPT_CHARS:
        return None, None, f"提示词过长，请控制在 {MAX_PROMPT_CHARS} 字符以内"

    reference_images = []
    for key in files:
        if key.startswith("reference_images"):
            for f in files.getlist(key):
                if f and f.filename:
                    reference_images.append(f)
    if len(reference_images) > MAX_REFERENCE_IMAGES:
        return None, None, f"参考图最多 {MAX_REFERENCE_IMAGES} 张"
    return model_id, reference_images, None


@bp.route("/generate", methods=["POST"])
@login_required
def generate():
    """Create one billable generation job."""
    data = request.form.to_dict()
    files = request.files
    model_id, reference_images, validation_error = _validate_generation_input(data, files)
    if validation_error:
        return _error_response(validation_error, 400, "server")
    prompt = data.get("prompt", "")
    resolution = data.get("resolution", "2K")

    config = get_model(model_id)
    if not config:
        return _error_response(f"未知模型: {model_id}", 400, "server")

    idempotency_key = (
        request.headers.get("Idempotency-Key")
        or data.get("idempotency_key")
        or f"web:{request.user_id}:{model_id}:{uuid.uuid4().hex}"
    )
    existing_job = get_generation_by_idempotency(request.user_id, idempotency_key)
    if existing_job:
        if existing_job.get("status") == "success":
            return jsonify({
                "success": True,
                "replayed": True,
                "job_id": existing_job["id"],
                "image_url": existing_job.get("image_url", ""),
                "credits_used": existing_job.get("credits_used", 0),
                "stage": "cdn",
                "progress": _progress_payload("cdn", message="已复用上次成功结果"),
                "message": "检测到重复请求，已返回上一次成功结果，未重复扣费。",
            })
        if existing_job.get("status") == "pending":
            return jsonify({
                "error": "该请求正在处理中，请稍后查看结果，未重复扣费。",
                "job_id": existing_job["id"],
                "stage": "server",
                "progress": _progress_payload("server", message="该请求正在处理中，请稍后查看结果"),
            }), 409
        return jsonify({
            "error": "该幂等请求此前已失败并处理退款。如需重新生成，请重新提交一次新请求。",
            "job_id": existing_job["id"],
            "status": existing_job.get("status"),
            "stage": "server",
            "progress": _progress_payload("server", "server", "此前请求已失败并退款"),
        }), 409

    success, credits, error = deduct_credits(
        request.user_id,
        model_id,
        resolution,
        data,
        idempotency_key=f"debit:{idempotency_key}",
    )
    if not success:
        return _error_response(error, 402, "billing")

    job_id = log_generation(
        request.user_id,
        model_id,
        credits,
        prompt,
        status="pending",
        idempotency_key=idempotency_key,
    )

    try:
        api_type = config["api_type"]
        route = select_model_route(model_id)
        if route:
            data["_channel_key"] = route.get("channel_key", "")
            data["_upstream_model"] = route.get("upstream_model", "")
            data["_route_endpoint"] = route.get("endpoint", "")
        handler = API_DISPATCH.get(api_type)
        if not handler:
            return _refund_and_fail(
                job_id,
                request.user_id,
                credits,
                f"未知 API 类型: {api_type}",
                stage="server",
            )

        result, error = _call_handler(api_type, handler, model_id, data, reference_images)
        if error:
            return _refund_and_fail(job_id, request.user_id, credits, str(error), stage="upstream")

        result = result or {}
        if result.get("filename"):
            cdn_url = get_image_url(result["filename"]) if is_oss_enabled() else ""
            if cdn_url:
                result["secure_url"] = cdn_url
            else:
                result["token"] = generate_image_token(result["filename"])
                result["secure_url"] = f"/outputs/{result['filename']}?token={result['token']}"

        image_url = (
            result.get("secure_url")
            or result.get("filepath")
            or result.get("image_url")
            or result.get("video_url")
            or result.get("audio_url")
            or ""
        )
        request_id = str(result.get("task_id") or result.get("request_id") or result.get("id") or "")

        update_generation_log(
            job_id,
            status="success",
            image_url=image_url,
            request_id=request_id,
            raw_response=str(result)[:4000],
        )

        result["credits_used"] = credits
        result["job_id"] = job_id
        result["progress"] = _progress_payload("cdn", message="结果已生成并完成访问链接")

        user = get_user(request.user_id)
        return jsonify({
            "success": True,
            "result": result,
            "balance": user["balance"],
            "stage": "cdn",
            "progress": result["progress"],
        })

    except Exception as exc:
        tb = traceback.format_exc()
        print(tb, flush=True)
        return _refund_and_fail(
            job_id,
            request.user_id,
            credits,
            f"服务器异常: {str(exc)[:500]}",
            raw_response=tb[:4000],
            stage="server",
        )


@bp.route("/request-preview", methods=["POST"])
def request_preview():
    """Preview the normalized upstream request without charging or generating."""
    data = request.form.to_dict()
    model_id, reference_images, validation_error = _validate_generation_input(data, request.files)
    if validation_error:
        return jsonify({"error": validation_error}), 400
    config = get_model(model_id)
    if not config:
        return _error_response(f"未知模型: {model_id}", 400, "server")

    preview = {
        "version": "2026-05-11",
        "model_id": model_id,
        "model_name": config.get("name", ""),
        "provider": config.get("provider", ""),
        "api_type": config.get("api_type", ""),
        "endpoint": config.get("endpoint", ""),
        "estimated_credits": quote_credits(model_id, data.get("resolution", "2K"), data),
        "route": select_model_route(model_id),
        "parameters": {
            key: value
            for key, value in data.items()
            if key not in ("api_key",)
        },
        "reference_images": [f.filename for f in reference_images],
        "progress_stages": PROGRESS_STAGES,
        "execution": {
            "mode": "upstream",
            "billing": "preview_only_no_charge",
            "note": "前端表单会在真实生成时由后端转换为对应上游 API 请求；这些字段也可以继续映射为 ComfyUI workflow 参数。",
        },
    }
    return jsonify({"success": True, "preview": preview})


def _call_handler(api_type, handler, model_id, data, reference_images):
    api_key = str(data.get("api_key") or "").strip() or None
    if api_type == "gemini_native":
        return handler(
            model_id,
            data.get("prompt", ""),
            data.get("resolution", "2K"),
            data.get("aspect_ratio", "1:1"),
            reference_images,
            int(data.get("seed", 0)),
            api_key,
        )
    if api_type == "doubao":
        data["size"] = normalize_image_size(data)
        return handler(
            data.get("prompt", ""),
            data.get("model_variant", "doubao-seedream-5-0"),
            data.get("size", "1024x1024"),
            reference_images,
            int(data.get("n", 1)),
            api_key,
        )
    if api_type == "suno":
        extra = {k.replace("suno_", ""): v for k, v in data.items() if k.startswith("suno_")}
        for key in ("title", "tags", "custom_tags", "negative_tags", "make_instrumental", "generation_type", "continue_clip_id", "continue_at", "persona_id", "send_advanced", "vocal_gender", "auto_generate_lyrics", "style_weight", "weirdness", "reference_audio_id"):
            if key in data and key not in extra:
                extra[key] = data.get(key)
        return handler(
            data.get("mode", "灵感模式"),
            data.get("prompt", ""),
            data.get("model_version", "chirp-v5"),
            extra,
            api_key,
        )
    if api_type == "grok_video":
        grok_model = data.get("model", "grok-video-3")
        duration = "10s" if str(grok_model).endswith("10s") else "6s"
        return handler(
            data.get("prompt", ""),
            option_value(data.get("duration"), duration),
            None,
            data,
            reference_images,
            api_key,
        )
    if api_type == "openai_responses":
        return handler(
            data.get("prompt", "") or data.get("user_question", ""),
            data.get("system_prompt", ""),
            reference_images,
            data,
            api_key,
        )
    if api_type == "gemini_analysis":
        return handler(
            data.get("prompt", "") or data.get("analysis_requirement", ""),
            reference_images,
            data,
            api_key,
        )
    if api_type == "tikpan_proxy":
        return handler(model_id, data, reference_images, api_key)
    return None, f"未实现的 API 类型: {api_type}"


def _refund_and_fail(job_id, user_id, credits, error, raw_response="", stage="upstream"):
    update_balance(
        user_id,
        credits,
        entry_type="generation_refund",
        reference_type="generation",
        reference_id=job_id,
        idempotency_key=f"refund:generation:{job_id}",
        note=f"生成失败自动退回 {credits} 额度",
        metadata={"error": str(error)[:500]},
    )
    update_generation_log(
        job_id,
        status="refunded",
        error_message=str(error)[:1000],
        raw_response=raw_response,
        refunded_at="now",
    )
    return jsonify({
        "error": error,
        "job_id": job_id,
        "stage": stage,
        "progress": _progress_payload(stage, stage, str(error)),
    }), 500
