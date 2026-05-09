"""
💳 支付 API — 充值/余额
"""
from flask import Blueprint, request, jsonify
from models import create_order, complete_order
from core.auth import login_required

bp = Blueprint("api_payment", __name__, url_prefix="/api")


def get_recharge_plans():
    """从数据库读取充值方案，如果没有则用默认值"""
    from models import get_setting
    plans = {}
    for amount in [10, 30, 50, 100, 300, 500]:
        val = get_setting(f"recharge_{amount}")
        plans[amount] = int(val) if val else {10: 20, 30: 65, 50: 110, 100: 230, 300: 720, 500: 1250}[amount]
    return plans


@bp.route("/recharge/plans")
def recharge_plans():
    """返回充值方案"""
    plans = get_recharge_plans()
    result = [{"amount": k, "credits": v, "bonus": v - k * 2} for k, v in sorted(plans.items())]
    return jsonify({"success": True, "plans": result})


@bp.route("/recharge/create", methods=["POST"])
@login_required
def create_recharge():
    """
    创建充值订单
    生产环境：对接支付宝/微信支付
    开发环境：直接完成充值
    """
    data = request.json
    amount = int(data.get("amount", 0))
    plans = get_recharge_plans()

    if amount not in plans:
        return jsonify({"error": "无效的充值金额"}), 400

    credits = plans[amount]

    # 创建订单
    order_id = create_order(request.user_id, amount, credits)

    # 开发阶段：直接完成充值
    # 生产环境：这里应该返回支付链接，用户支付后异步回调
    from models import get_db
    conn = get_db()
    conn.execute("UPDATE orders SET status='completed', trade_no=? WHERE id=?", (f"sim_{order_id}", order_id))
    conn.execute("UPDATE users SET balance=balance+? WHERE id=?", (credits, request.user_id))
    conn.commit()
    conn.close()

    from models import get_user
    user = get_user(request.user_id)

    return jsonify({
        "success": True,
        "order_id": order_id,
        "credits": credits,
        "balance": user["balance"],
        "message": f"充值成功！获得 {credits} 额度"
    })
