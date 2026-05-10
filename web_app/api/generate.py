"""
Generation API: charge user balance, call upstream provider, and keep an
auditable job record for every attempt.
"""
import traceback

from flask import Blueprint, jsonify, request

from backend.database import get_model
from backend.handlers import API_DISPATCH
from config import generate_image_token
from core.auth import login_required
from core.billing import deduct_credits
from models import get_user, log_generation, update_balance, update_generation_log

bp = Blueprint("api_generate", __name__, url_prefix="/api")


@bp.route("/generate", methods=["POST"])
@login_required
def generate():
    """Create one billable generation job."""
    data = request.form.to_dict()
    files = request.files
    model_id = data.get("model_id")
    prompt = data.get("prompt", "")
    resolution = data.get("resolution", "2K")

    config = get_model(model_id)
    if not config:
        return jsonify({"error": f"未知模型: {model_id}"}), 400

    success, credits, error = deduct_credits(request.user_id, model_id, resolution)
    if not success:
        return jsonify({"error": error}), 402

    job_id = log_generation(
        request.user_id,
        model_id,
        credits,
        prompt,
        status="pending",
    )

    try:
        reference_images = []
        for key in files:
            if key.startswith("reference_images"):
                for f in request.files.getlist(key):
                    if f and f.filename:
                        reference_images.append(f)

        api_type = config["api_type"]
        handler = API_DISPATCH.get(api_type)
        if not handler:
            return _refund_and_fail(
                job_id,
                request.user_id,
                credits,
                f"未知 API 类型: {api_type}",
            )

        result, error = _call_handler(api_type, handler, model_id, data, reference_images)
        if error:
            return _refund_and_fail(job_id, request.user_id, credits, str(error))

        result = result or {}
        if result.get("filename"):
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

        user = get_user(request.user_id)
        return jsonify({"success": True, "result": result, "balance": user["balance"]})

    except Exception as exc:
        tb = traceback.format_exc()
        print(tb, flush=True)
        return _refund_and_fail(
            job_id,
            request.user_id,
            credits,
            f"服务器异常: {str(exc)[:500]}",
            raw_response=tb[:4000],
        )


def _call_handler(api_type, handler, model_id, data, reference_images):
    if api_type == "gemini_native":
        return handler(
            model_id,
            data.get("prompt", ""),
            data.get("resolution", "2K"),
            data.get("aspect_ratio", "1:1"),
            reference_images,
            int(data.get("seed", 0)),
            None,
        )
    if api_type == "doubao":
        return handler(
            data.get("prompt", ""),
            data.get("model_variant", "doubao-seedream-5-0"),
            data.get("size", "1024x1024"),
            reference_images,
            int(data.get("n", 1)),
            None,
        )
    if api_type == "suno":
        extra = {k.replace("suno_", ""): v for k, v in data.items() if k.startswith("suno_")}
        return handler(
            data.get("mode", "灵感模式"),
            data.get("prompt", ""),
            data.get("model_version", "chirp-v5"),
            extra,
            None,
        )
    if api_type == "grok_video":
        return handler(
            data.get("prompt", ""),
            data.get("duration", "5s"),
            None,
        )
    return None, f"未实现的 API 类型: {api_type}"


def _refund_and_fail(job_id, user_id, credits, error, raw_response=""):
    update_balance(user_id, credits)
    update_generation_log(
        job_id,
        status="refunded",
        error_message=str(error)[:1000],
        raw_response=raw_response,
        refunded_at="now",
    )
    return jsonify({"error": error, "job_id": job_id}), 500
