"""
Payment API: recharge plans, order creation, and balance crediting.

Production must credit balances only after a verified payment provider callback.
"""
from flask import Blueprint, jsonify, request

from config import ENABLE_DEV_RECHARGE, IS_PRODUCTION, PAYMENT_PROVIDER
from core.auth import login_required
from models import complete_order, create_order, get_user

bp = Blueprint("api_payment", __name__, url_prefix="/api")


def get_recharge_plans():
    """Read recharge plans from settings, with local defaults for development."""
    from models import get_setting

    defaults = {10: 20, 30: 65, 50: 110, 100: 230, 300: 720, 500: 1250}
    plans = {}
    for amount, default_credits in defaults.items():
        val = get_setting(f"recharge_{amount}")
        plans[amount] = int(val) if val else default_credits
    return plans


@bp.route("/recharge/plans")
def recharge_plans():
    plans = get_recharge_plans()
    result = [{"amount": k, "credits": v, "bonus": v - k * 2} for k, v in sorted(plans.items())]
    return jsonify({"success": True, "plans": result})


@bp.route("/recharge/create", methods=["POST"])
@login_required
def create_recharge():
    data = request.json or {}
    try:
        amount = int(data.get("amount", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "无效的充值金额"}), 400

    plans = get_recharge_plans()
    if amount not in plans:
        return jsonify({"error": "无效的充值金额"}), 400

    credits = plans[amount]
    payment_method = str(data.get("payment_method", "alipay")).strip() or "alipay"
    order_id = create_order(request.user_id, amount, credits, payment_method)

    if IS_PRODUCTION and not ENABLE_DEV_RECHARGE:
        if not PAYMENT_PROVIDER:
            return jsonify({
                "error": "生产支付尚未配置，订单已创建但不会入账。请先接入支付宝、微信或 Stripe 回调。",
                "order_id": order_id,
                "status": "pending",
                "payment_required": True,
            }), 503
        return jsonify({
            "error": f"支付渠道 {PAYMENT_PROVIDER} 尚未实现回调验签，订单已创建但不会入账。",
            "order_id": order_id,
            "status": "pending",
            "payment_required": True,
        }), 501

    # Development-only shortcut. Never enable this for production money flow.
    from models import get_db

    conn = get_db()
    conn.execute("UPDATE orders SET trade_no=? WHERE id=?", (f"sim_{order_id}", order_id))
    conn.commit()
    conn.close()
    complete_order(order_id)
    user = get_user(request.user_id)

    return jsonify({
        "success": True,
        "order_id": order_id,
        "credits": credits,
        "balance": user["balance"],
        "message": f"充值成功，获得 {credits} 额度",
        "dev_recharge": True,
    })
