from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path
from urllib.parse import urlparse


WEB_APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WEB_APP_DIR))

from config import (  # noqa: E402
    ADMIN_PASSWORD,
    ALLOWED_ORIGINS,
    API_KEY,
    ENABLE_DEV_RECHARGE,
    ENVIRONMENT,
    FLASK_SECRET,
    IS_PRODUCTION,
    OUTPUT_DIR,
    PAYMENT_PROVIDER,
    PUBLIC_BASE_URL,
    SECRET_KEY,
)
from models import DB_PATH, get_provider_channels, get_pricing, init_db  # noqa: E402


def check(name: str, ok: bool, detail: str = "") -> bool:
    marker = "OK" if ok else "FAIL"
    print(f"[{marker}] {name}" + (f" - {detail}" if detail else ""))
    return ok


def is_public_https(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname not in ("localhost", "127.0.0.1", "::1")


def strong_secret(value: str, *blocked: str) -> bool:
    value = value or ""
    return len(value) >= 16 and value not in set(blocked)


def main() -> int:
    failures = 0
    init_db()

    checks = [
        ("APP_ENV=production", ENVIRONMENT == "production", ENVIRONMENT),
        ("FLASK_SECRET 已替换", strong_secret(FLASK_SECRET, "flask-secret-change-me", "change-this-secret-key")),
        ("TIKPAN_SECRET 已替换", strong_secret(SECRET_KEY, "tikpan-secret-change-me", "change-this-secret-key")),
        ("ADMIN_PASSWORD 已替换", strong_secret(ADMIN_PASSWORD, "admin123", "password", "changeme")),
        ("TIKPAN_API_KEY 已配置", bool(API_KEY and API_KEY != "sk-xxx")),
        ("PUBLIC_BASE_URL 为公网 HTTPS", is_public_https(PUBLIC_BASE_URL), PUBLIC_BASE_URL),
        ("ALLOWED_ORIGINS 已配置", bool(ALLOWED_ORIGINS), ",".join(ALLOWED_ORIGINS)),
    ]
    for name, ok, *detail in checks:
        failures += 0 if check(name, ok, detail[0] if detail else "") else 1

    if IS_PRODUCTION:
        failures += 0 if check(
            "生产环境未开启模拟充值",
            not ENABLE_DEV_RECHARGE,
            f"ENABLE_DEV_RECHARGE={ENABLE_DEV_RECHARGE}",
        ) else 1
        failures += 0 if check(
            "生产支付渠道已声明",
            bool(PAYMENT_PROVIDER),
            PAYMENT_PROVIDER or "未配置",
        ) else 1

    data_dir = Path(DB_PATH).parent
    output_dir = Path(OUTPUT_DIR)
    failures += 0 if check("数据库目录可写", os.access(data_dir, os.W_OK), str(data_dir)) else 1
    output_dir.mkdir(parents=True, exist_ok=True)
    failures += 0 if check("输出目录可写", os.access(output_dir, os.W_OK), str(output_dir)) else 1

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("SELECT 1")
        conn.close()
        db_ok = True
    except Exception as exc:
        db_ok = False
        print(f"[FAIL] 数据库连接失败 - {exc}")
    failures += 0 if db_ok else 1

    channels = get_provider_channels(active_only=True)
    pricing = get_pricing(active_only=True)
    failures += 0 if check("至少一个启用渠道", bool(channels), f"{len(channels)} 个") else 1
    failures += 0 if check("至少一个启用定价", bool(pricing), f"{len(pricing)} 个") else 1

    print("")
    if failures:
        print(f"部署检查未通过：{failures} 项需要处理。")
        return 1
    print("部署检查通过，可以进入预发/正式发布流程。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
