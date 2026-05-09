"""
🎨 生成 API — 扣费 + 调 API + 记录
"""
from flask import Blueprint, request, jsonify
from core.auth import login_required
from core.billing import deduct_credits
from models import log_generation, get_user, update_balance
from backend.database import get_model
from backend.handlers import API_DISPATCH
from config import generate_image_token

bp = Blueprint("api_generate", __name__, url_prefix="/api")


@bp.route("/generate", methods=["POST"])
@login_required
def generate():
    """带计费的生成接口"""
    data = request.form.to_dict()
    files = request.files
    model_id = data.get("model_id")

    config = get_model(model_id)
    if not config:
        return jsonify({"error": f"未知模型: {model_id}"}), 400

    resolution = data.get("resolution", "2K")

    # 1️⃣ 扣费
    success, credits, error = deduct_credits(request.user_id, model_id, resolution)
    if not success:
        return jsonify({"error": error}), 402

    # 2️⃣ 调 API
    reference_images = []
    for key in files:
        if key.startswith("reference_images"):
            for f in request.files.getlist(key):
                if f and f.filename:
                    reference_images.append(f)

    api_type = config["api_type"]
    handler = API_DISPATCH.get(api_type)
    if not handler:
        return jsonify({"error": f"未知 API 类型: {api_type}"}), 500

    try:
        if api_type == "gemini_native":
            result, error = handler(
                model_id, data.get("prompt", ""),
                data.get("resolution", "2K"), data.get("aspect_ratio", "1:1"),
                reference_images, int(data.get("seed", 0)), None,
            )
        elif api_type == "doubao":
            result, error = handler(
                data.get("prompt", ""), data.get("model_variant", "doubao-seedream-5-0"),
                data.get("size", "1024x1024"), reference_images,
                int(data.get("n", 1)), None,
            )
        elif api_type == "suno":
            extra = {k.replace("suno_", ""): v for k, v in data.items() if k.startswith("suno_")}
            result, error = handler(
                data.get("mode", "灵感模式"), data.get("prompt", ""),
                data.get("model_version", "chirp-v5"), extra, None,
            )
        elif api_type == "grok_video":
            result, error = handler(
                data.get("prompt", ""), data.get("duration", "5s"), None,
            )
        else:
            result, error = None, f"未实现的 API 类型: {api_type}"

        if error:
            # 生成失败，退回额度
            update_balance(request.user_id, credits)
            return jsonify({"error": error}), 500

        # 3️⃣ 记录日志
        prompt = data.get("prompt", "")
        log_generation(request.user_id, model_id, credits, prompt)

        # 4️⃣ 生成安全访问令牌
        if result and result.get("filename"):
            result["token"] = generate_image_token(result["filename"])
            result["secure_url"] = f"/outputs/{result['filename']}?token={result['token']}"

        result["credits_used"] = credits

        user = get_user(request.user_id)
        return jsonify({"success": True, "result": result, "balance": user["balance"]})

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(tb, flush=True)
        # 异常也退回额度
        update_balance(request.user_id, credits)
        return jsonify({"error": f"服务器异常: {str(e)[:500]}"}), 500
