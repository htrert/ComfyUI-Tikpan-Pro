"""
💰 计费模块 — 余额扣费/额度校验
"""
from models import get_model_price, update_balance, log_generation, get_user


def deduct_credits(user_id, model_id, resolution="2K"):
    """
    扣费流程：检查余额 → 扣费 → 记录日志
    返回 (success, credits_used, error_msg)
    """
    user = get_user(user_id)
    if not user:
        return False, 0, "用户不存在"

    credits = get_model_price(model_id, resolution)

    if user["balance"] < credits:
        return False, credits, f"余额不足（需要 {credits} 额度，当前 {user['balance']} 额度）"

    success, error = update_balance(user_id, -credits)
    if not success:
        return False, credits, error

    return True, credits, None


def get_pricing_list():
    """返回所有模型的定价列表"""
    from models import get_all_pricing
    return get_all_pricing()
