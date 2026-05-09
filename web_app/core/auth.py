"""
🔐 认证模块 — JWT 登录/注册/鉴权
"""
import jwt
import datetime
from flask import request, jsonify
from functools import wraps
from config import FLASK_SECRET

JWT_EXPIRE_HOURS = 72


def create_token(user_id, role="user"):
    payload = {
        "user_id": user_id,
        "role": role,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=JWT_EXPIRE_HOURS)
    }
    return jwt.encode(payload, FLASK_SECRET, algorithm="HS256")


def decode_token(token):
    try:
        return jwt.decode(token, FLASK_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]

        if not token:
            # 也检查 cookie
            token = request.cookies.get("token")

        if not token:
            return jsonify({"error": "请先登录"}), 401

        data = decode_token(token)
        if not data:
            return jsonify({"error": "登录已过期，请重新登录"}), 401

        request.user_id = data["user_id"]
        request.user_role = data.get("role", "user")
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if request.user_role not in ("admin", "agent"):
            return jsonify({"error": "权限不足"}), 403
        return f(*args, **kwargs)
    return decorated
