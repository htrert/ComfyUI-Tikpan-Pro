"""
🤝 代理 API — 代理申请/下级管理/收益
"""
from flask import Blueprint, request, jsonify
from core.auth import login_required
from models import get_user, get_db, create_agent_config, get_agent_config, get_agent_children, get_agent_earnings

bp = Blueprint("api_agent", __name__, url_prefix="/api/agent")


@bp.route("/apply", methods=["POST"])
@login_required
def apply_agent():
    """申请成为代理"""
    data = request.json
    payment_method = data.get("payment_method", "balance")

    # 检查是否已经是代理
    user = get_user(request.user_id)
    if user.get("role") in ("agent", "admin"):
        return jsonify({"error": "您已经是代理了"}), 400

    # 代理门槛：缴纳 88 元（用额度扣，880 额度 ≈ 88元）
    AGENT_FEE_CREDITS = 880

    if payment_method == "balance":
        from models import update_balance
        success, err = update_balance(request.user_id, -AGENT_FEE_CREDITS)
        if not success:
            return jsonify({"error": f"余额不足。成为代理需要 {AGENT_FEE_CREDITS} 额度"}), 402

        # 生成代理邀请码
        import uuid
        agent_code = uuid.uuid4().hex[:8].upper()

        conn = get_db()
        conn.execute("UPDATE users SET role='agent', agent_code=? WHERE id=?", (agent_code, request.user_id))
        conn.commit()
        conn.close()

        create_agent_config(request.user_id)

        return jsonify({
            "success": True,
            "agent_code": agent_code,
            "message": "🎉 恭喜成为代理！您的邀请码已生成"
        })

    return jsonify({"error": "暂只支持余额支付"}), 400


@bp.route("/info")
@login_required
def agent_info():
    """代理信息面板"""
    user = get_user(request.user_id)
    if user.get("role") not in ("agent", "admin"):
        return jsonify({"error": "您还不是代理"}), 403

    config = get_agent_config(request.user_id)
    children = get_agent_children(request.user_id)
    earnings = get_agent_earnings(request.user_id)

    return jsonify({
        "success": True,
        "agent": {
            "agent_code": user.get("agent_code", ""),
            "wholesale_price": config["wholesale_price"] if config else 0.475,
            "profit_share": config["profit_share"] if config else 0.1,
            "is_approved": config["is_approved"] if config else 0,
            "children_count": len(children),
            "children": children,
            "earnings": earnings,
        }
    })
