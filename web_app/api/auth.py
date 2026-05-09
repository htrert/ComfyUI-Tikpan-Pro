"""
👤 用户 API — 邮箱注册 / OAuth / 验证码
"""
from flask import Blueprint, request, jsonify, redirect
from models import create_user, verify_user, get_user, get_db
from core.auth import create_token, login_required
from services.mail import send_verify_code, generate_verify_code
from services.oauth import google_login_url, google_callback, github_login_url, github_callback

bp = Blueprint("api_auth", __name__, url_prefix="/api")

# 验证码缓存（生产环境应使用 Redis）
verify_codes = {}


# ===== 邮箱注册 =====

@bp.route("/send-code", methods=["POST"])
def send_code():
    """发送邮箱验证码"""
    data = request.json
    email = str(data.get("email", "")).strip()

    if "@" not in email:
        return jsonify({"error": "请输入有效的邮箱地址"}), 400

    code = generate_verify_code()
    verify_codes[email] = {"code": code, "expires": __import__("time").time() + 600}
    print(f"[Auth] 📧 验证码 {code} → {email}", flush=True)

    success = send_verify_code(email, code)
    if success:
        return jsonify({"success": True, "message": "验证码已发送"})
    else:
        # SMTP 未配置时，开发模式直接返回验证码
        return jsonify({"success": True, "message": "开发模式", "code_preview": code})


@bp.route("/register", methods=["POST"])
def register():
    data = request.json
    email = str(data.get("email", "")).strip()
    password = str(data.get("password", "")).strip()
    code = str(data.get("code", "")).strip()
    invite_code = str(data.get("invite_code", "")).strip()

    if not email or "@" not in email:
        return jsonify({"error": "请输入有效的邮箱"}), 400
    if not password or len(password) < 6:
        return jsonify({"error": "密码至少6个字符"}), 400
    if not code:
        return jsonify({"error": "请输入验证码"}), 400

    # 校验验证码
    cached = verify_codes.get(email)
    if not cached or cached["code"] != code:
        return jsonify({"error": "验证码错误或已过期"}), 400
    if __import__("time").time() > cached["expires"]:
        return jsonify({"error": "验证码已过期"}), 400

    del verify_codes[email]

    user_id, err = create_user(email, password, email.split("@")[0])
    if err:
        return jsonify({"error": err}), 400

    # 邀请码绑定
    if invite_code:
        conn = get_db()
        parent = conn.execute("SELECT id FROM users WHERE agent_code=? AND role='agent'", (invite_code,)).fetchone()
        if parent:
            conn.execute("UPDATE users SET parent_id=? WHERE id=?", (parent["id"], user_id))
        conn.commit()
        conn.close()

    token = create_token(user_id)
    return jsonify({"success": True, "token": token, "user_id": user_id})


@bp.route("/login", methods=["POST"])
def login():
    """邮箱密码登录"""
    data = request.json
    email = str(data.get("email", "")).strip()
    password = str(data.get("password", "")).strip()

    user = verify_user(email, password)
    if not user:
        return jsonify({"error": "邮箱或密码错误"}), 401

    token = create_token(user["id"], user["role"])
    return jsonify({"success": True, "token": token, "user": {
        "id": user["id"],
        "email": user["username"],
        "nickname": user["nickname"],
        "balance": user["balance"],
        "role": user["role"],
    }})


# ===== OAuth =====

@bp.route("/oauth/google")
def oauth_google():
    return redirect(google_login_url())


@bp.route("/oauth/google/callback")
def oauth_google_callback():
    code = request.args.get("code")
    if not code:
        return redirect("/?error=google_auth_failed")

    info, error = google_callback(code)
    if error:
        return redirect(f"/?error={error}")

    return _oauth_login(info)


@bp.route("/oauth/github")
def oauth_github():
    return redirect(github_login_url())


@bp.route("/oauth/github/callback")
def oauth_github_callback():
    code = request.args.get("code")
    if not code:
        return redirect("/?error=github_auth_failed")

    info, error = github_callback(code)
    if error:
        return redirect(f"/?error={error}")

    return _oauth_login(info)


def _oauth_login(info):
    """OAuth 登录/注册统一处理"""
    provider_id = f"{info['provider']}_{info['provider_id']}"
    email = info.get("email", f"{provider_id}@oauth.local")

    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username=?", (email,)).fetchone()

    if not user:
        # 自动注册
        import hashlib
        import random
        rand_pass = hashlib.sha256(f"{provider_id}_{random.random()}".encode()).hexdigest()[:16]
        conn.execute(
            "INSERT INTO users (username, password_hash, nickname) VALUES (?,?,?)",
            (email, hashlib.sha256(rand_pass.encode()).hexdigest(), info.get("name", ""))
        )
        conn.commit()
        user_id = conn.execute("SELECT id FROM users WHERE username=?", (email,)).fetchone()["id"]
    else:
        user_id = user["id"]

    conn.close()
    token = create_token(user_id)
    return redirect(f"/?token={token}")


# ===== 用户信息 =====

@bp.route("/user/info")
@login_required
def user_info():
    user = get_user(request.user_id)
    if not user:
        return jsonify({"error": "用户不存在"}), 404
    return jsonify({"success": True, "user": user})


@bp.route("/user/balance/history")
@login_required
def balance_history():
    from models import get_db
    conn = get_db()
    orders = conn.execute(
        "SELECT id, amount, credits, status, created_at, 'recharge' as type FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT 20",
        (request.user_id,)
    ).fetchall()
    logs = conn.execute(
        "SELECT id, model, credits_used as credits, status, created_at, 'usage' as type FROM generation_logs WHERE user_id=? ORDER BY created_at DESC LIMIT 20",
        (request.user_id,)
    ).fetchall()
    conn.close()

    items = []
    for o in orders:
        items.append({"type": "充值", "amount": o["credits"], "detail": f"¥{o['amount']}", "time": o["created_at"][:19]})
    for l in logs:
        items.append({"type": "消费", "amount": -l["credits"], "detail": l["model"], "time": l["created_at"][:19]})

    items.sort(key=lambda x: x["time"], reverse=True)
    return jsonify({"success": True, "items": items[:30]})
