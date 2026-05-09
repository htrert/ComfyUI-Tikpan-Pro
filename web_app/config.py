"""
⚙️ Tikpan Web - 配置文件 + SMTP + OAuth
"""
import os
import hashlib
import time

ROOT = os.path.dirname(os.path.abspath(__file__))

# ==== API ====
API_BASE_URL = "https://tikpan.com"
API_KEY = os.environ.get("TIKPAN_API_KEY", "sk-xxx")

# ==== Output ====
OUTPUT_DIR = os.path.join(ROOT, "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ==== Security ====
SECRET_KEY = os.environ.get("TIKPAN_SECRET", "tikpan-secret-change-me")
TOKEN_EXPIRE_SECONDS = 3600
FLASK_SECRET = os.environ.get("FLASK_SECRET", "flask-secret-change-me")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

# ==== SMTP 邮件配置（后台管理配置，会覆盖这些默认值）====
SMTP_CONFIG = {
    "server": os.environ.get("SMTP_SERVER", "smtp.qq.com"),
    "port": int(os.environ.get("SMTP_PORT", 465)),
    "use_ssl": os.environ.get("SMTP_USE_SSL", "true").lower() == "true",
    "account": os.environ.get("SMTP_ACCOUNT", "1079396643@qq.com"),
    "sender": os.environ.get("SMTP_SENDER", "1079396643@qq.com"),
    "password": os.environ.get("SMTP_PASSWORD", ""),
}

# ==== OAuth ====
OAUTH_GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
OAUTH_GOOGLE_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
OAUTH_GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
OAUTH_GITHUB_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
OAUTH_REDIRECT_BASE = os.environ.get("OAUTH_REDIRECT_BASE", "http://localhost:5000")


def generate_image_token(filename):
    expire = int(time.time()) + TOKEN_EXPIRE_SECONDS
    raw = f"{filename}:{expire}:{SECRET_KEY}"
    token = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"{token}:{expire}"


def verify_image_token(filename, token_str):
    try:
        token_part, expire_str = token_str.split(":", 1)
        expire = int(expire_str)
        if int(time.time()) > expire:
            return False
        raw = f"{filename}:{expire}:{SECRET_KEY}"
        expected = hashlib.sha256(raw.encode()).hexdigest()[:16]
        return token_part == expected
    except Exception:
        return False
