"""
⚙️ Tikpan Web - 配置文件 + SMTP + OAuth
"""
import os
import hashlib
import time
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.abspath(__file__))


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes", "on")


def env_list(name, default=""):
    raw = os.environ.get(name, default)
    return [item.strip().rstrip("/") for item in raw.split(",") if item.strip()]


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
ENVIRONMENT = os.environ.get("APP_ENV", "development").lower()
IS_PRODUCTION = ENVIRONMENT == "production"
TRUST_PROXY = env_bool("TRUST_PROXY", False)
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://localhost:5000").rstrip("/")
ALLOWED_ORIGINS = env_list("ALLOWED_ORIGINS", PUBLIC_BASE_URL)
ENABLE_DEV_RECHARGE = env_bool("ENABLE_DEV_RECHARGE", not IS_PRODUCTION)
PAYMENT_PROVIDER = os.environ.get("PAYMENT_PROVIDER", "").strip().lower()

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


def _is_local_url(url):
    host = urlparse(url).hostname or ""
    return host in ("localhost", "127.0.0.1", "::1")


def validate_production_config():
    if not IS_PRODUCTION:
        return
    failures = []
    weak_values = {
        "TIKPAN_SECRET": SECRET_KEY,
        "FLASK_SECRET": FLASK_SECRET,
        "ADMIN_PASSWORD": ADMIN_PASSWORD,
    }
    defaults = {
        "TIKPAN_SECRET": {"", "tikpan-secret-change-me", "change-this-secret-key"},
        "FLASK_SECRET": {"", "flask-secret-change-me", "change-this-secret-key"},
        "ADMIN_PASSWORD": {"", "admin123", "password", "changeme"},
    }
    for name, value in weak_values.items():
        if value in defaults[name] or len(value) < 16:
            failures.append(f"{name} must be a strong non-default value")
    if not API_KEY or API_KEY == "sk-xxx":
        failures.append("TIKPAN_API_KEY must be configured")
    if not PUBLIC_BASE_URL.startswith("https://") or _is_local_url(PUBLIC_BASE_URL):
        failures.append("PUBLIC_BASE_URL must be your public HTTPS domain")
    if not ALLOWED_ORIGINS:
        failures.append("ALLOWED_ORIGINS must include your public site origin")
    if failures:
        raise RuntimeError("Unsafe production configuration: " + "; ".join(failures))


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
