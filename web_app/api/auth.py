"""
User authentication API: email register/login plus Google and GitHub OAuth.
"""
import hmac
import secrets
import time
from urllib.parse import quote_plus

from flask import Blueprint, jsonify, redirect, request, session

from config import IS_PRODUCTION
from core.auth import create_token, login_required
from core.security import client_ip, rate_limit
from models import create_user, get_db, get_smtp_config, get_user, hash_password, verify_user
from services.mail import generate_verify_code, send_verify_code
from services.oauth import (
    github_callback,
    github_login_url,
    google_callback,
    google_login_url,
    oauth_status,
)

bp = Blueprint("api_auth", __name__, url_prefix="/api")

# Development-friendly in-memory cache. Production can replace this with Redis.
verify_codes = {}


@bp.route("/auth/options")
def auth_options():
    status = oauth_status()
    smtp = get_smtp_config()
    smtp_ready = bool(smtp.get("server") and smtp.get("account") and smtp.get("sender") and smtp.get("password"))
    return jsonify({
        "success": True,
        "email": True,
        "smtp_configured": smtp_ready,
        "dev_code_preview": (not smtp_ready and not IS_PRODUCTION),
        "google": status["google"],
        "github": status["github"],
        "callbacks": {
            "google": status["google_callback"],
            "github": status["github_callback"],
        },
    })


@bp.route("/send-code", methods=["POST"])
def send_code():
    ip = client_ip()
    ok, retry_after = rate_limit(f"send-code:{ip}", limit=5, window_seconds=300)
    if not ok:
        return jsonify({"error": f"验证码请求过于频繁，请 {retry_after} 秒后再试"}), 429

    data = request.json or {}
    email = str(data.get("email", "")).strip().lower()
    if "@" not in email or len(email) > 120:
        return jsonify({"error": "请输入有效的邮箱地址"}), 400

    code = generate_verify_code()
    verify_codes[email] = {"code": code, "expires": time.time() + 600}

    if send_verify_code(email, code):
        return jsonify({"success": True, "message": "验证码已发送"})
    if IS_PRODUCTION:
        verify_codes.pop(email, None)
        return jsonify({"error": "邮件服务尚未配置，暂时无法注册"}), 503
    return jsonify({"success": True, "message": "开发模式验证码", "code_preview": code})


@bp.route("/register", methods=["POST"])
def register():
    ip = client_ip()
    ok, retry_after = rate_limit(f"register:{ip}", limit=10, window_seconds=300)
    if not ok:
        return jsonify({"error": f"注册尝试过于频繁，请 {retry_after} 秒后再试"}), 429

    data = request.json or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", "")).strip()
    code = str(data.get("code", "")).strip()
    invite_code = str(data.get("invite_code", "")).strip()

    if not email or "@" not in email or len(email) > 120:
        return jsonify({"error": "请输入有效的邮箱"}), 400
    if len(password) < 8:
        return jsonify({"error": "密码至少 8 个字符"}), 400
    if not code:
        return jsonify({"error": "请输入验证码"}), 400

    cached = verify_codes.get(email)
    if not cached or not hmac.compare_digest(str(cached.get("code", "")), code):
        return jsonify({"error": "验证码错误或已过期"}), 400
    if time.time() > cached["expires"]:
        verify_codes.pop(email, None)
        return jsonify({"error": "验证码已过期"}), 400

    verify_codes.pop(email, None)
    user_id, err = create_user(email, password, email.split("@")[0])
    if err:
        return jsonify({"error": err}), 400

    if invite_code:
        conn = get_db()
        parent = conn.execute(
            "SELECT id FROM users WHERE agent_code=? AND role='agent'",
            (invite_code,),
        ).fetchone()
        if parent:
            conn.execute("UPDATE users SET parent_id=? WHERE id=?", (parent["id"], user_id))
        conn.commit()
        conn.close()

    token = create_token(user_id)
    return jsonify({"success": True, "token": token, "user_id": user_id})


@bp.route("/login", methods=["POST"])
def login():
    ip = client_ip()
    ok, retry_after = rate_limit(f"login:{ip}", limit=20, window_seconds=300)
    if not ok:
        return jsonify({"error": f"登录尝试过于频繁，请 {retry_after} 秒后再试"}), 429

    data = request.json or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", "")).strip()

    user = verify_user(email, password)
    if not user:
        return jsonify({"error": "邮箱或密码错误"}), 401

    token = create_token(user["id"], user["role"])
    return jsonify({
        "success": True,
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["username"],
            "nickname": user["nickname"],
            "balance": user["balance"],
            "role": user["role"],
        },
    })


def _oauth_error(message):
    return redirect(f"/?error={quote_plus(message)}")


def _start_oauth(provider, url_factory):
    state = secrets.token_urlsafe(32)
    session[f"oauth_{provider}_state"] = state
    try:
        return redirect(url_factory(state))
    except ValueError as exc:
        return _oauth_error(str(exc))


def _verify_oauth_state(provider):
    expected = session.pop(f"oauth_{provider}_state", "")
    received = request.args.get("state", "")
    return bool(expected and received and hmac.compare_digest(expected, received))


@bp.route("/oauth/google")
def oauth_google():
    return _start_oauth("google", google_login_url)


@bp.route("/oauth/google/callback")
def oauth_google_callback():
    if not _verify_oauth_state("google"):
        return _oauth_error("Google 登录状态已失效，请重新尝试")
    code = request.args.get("code")
    if not code:
        return _oauth_error("Google 登录未返回授权码")

    info, error = google_callback(code)
    if error:
        return _oauth_error(error)
    return _oauth_login(info)


@bp.route("/oauth/github")
def oauth_github():
    return _start_oauth("github", github_login_url)


@bp.route("/oauth/github/callback")
def oauth_github_callback():
    if not _verify_oauth_state("github"):
        return _oauth_error("GitHub 登录状态已失效，请重新尝试")
    code = request.args.get("code")
    if not code:
        return _oauth_error("GitHub 登录未返回授权码")

    info, error = github_callback(code)
    if error:
        return _oauth_error(error)
    return _oauth_login(info)


def _oauth_login(info):
    if not info or not info.get("provider") or not info.get("provider_id"):
        return _oauth_error("第三方账号信息不完整")

    provider_id = f"{info['provider']}_{info['provider_id']}"
    email = (info.get("email") or f"{provider_id}@oauth.local").strip().lower()
    nickname = info.get("name") or info.get("provider") or email.split("@")[0]

    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username=?", (email,)).fetchone()
    if not user:
        conn.execute(
            "INSERT INTO users (username, password_hash, nickname) VALUES (?,?,?)",
            (email, hash_password(secrets.token_urlsafe(24)), nickname),
        )
        conn.commit()
        user = conn.execute("SELECT * FROM users WHERE username=?", (email,)).fetchone()

    token = create_token(user["id"], user["role"])
    conn.close()
    return redirect(f"/?token={token}")


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
    conn = get_db()
    orders = conn.execute(
        "SELECT id, amount, credits, status, created_at, 'recharge' as type FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT 20",
        (request.user_id,),
    ).fetchall()
    logs = conn.execute(
        "SELECT id, model, CASE WHEN status='success' THEN credits_used ELSE 0 END as credits, status, created_at, 'usage' as type FROM generation_logs WHERE user_id=? ORDER BY created_at DESC LIMIT 20",
        (request.user_id,),
    ).fetchall()
    conn.close()

    items = []
    for order in orders:
        items.append({
            "type": "充值",
            "amount": order["credits"],
            "detail": f"¥{order['amount']}",
            "time": order["created_at"][:19],
            "status": order["status"],
        })
    for log in logs:
        items.append({
            "type": "消费",
            "amount": -log["credits"],
            "detail": log["model"],
            "time": log["created_at"][:19],
            "status": log["status"],
        })

    items.sort(key=lambda x: x["time"], reverse=True)
    return jsonify({"success": True, "items": items[:30]})
