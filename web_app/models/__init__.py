"""
🗄️ 数据库模型 — 用户/订单/生成记录/代理
"""
import sqlite3
import json
import os
import hashlib
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "tikpan.db")


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """初始化所有业务表"""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            nickname TEXT DEFAULT '',
            balance INTEGER DEFAULT 0,
            role TEXT DEFAULT 'user',
            agent_code TEXT UNIQUE,
            parent_id INTEGER,
            api_key_custom TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (parent_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            credits INTEGER NOT NULL,
            payment_method TEXT DEFAULT 'alipay',
            status TEXT DEFAULT 'pending',
            trade_no TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS generation_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            model TEXT NOT NULL,
            credits_used INTEGER NOT NULL,
            prompt TEXT DEFAULT '',
            status TEXT DEFAULT 'success',
            image_url TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS models_pricing (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id TEXT UNIQUE NOT NULL,
            model_name TEXT NOT NULL,
            credits_1k INTEGER DEFAULT 5,
            credits_2k INTEGER DEFAULT 8,
            credits_4k INTEGER DEFAULT 15,
            is_active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS agent_configs (
            user_id INTEGER PRIMARY KEY,
            wholesale_price REAL DEFAULT 0.475,
            markup_limit_min REAL DEFAULT 0.5,
            markup_limit_max REAL DEFAULT 5.0,
            profit_share REAL DEFAULT 0.1,
            is_approved INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    _ensure_generation_log_columns(conn)
    conn.commit()
    conn.close()


def _ensure_generation_log_columns(conn):
    """Keep old SQLite databases compatible with newer generation tracking."""
    rows = conn.execute("PRAGMA table_info(generation_logs)").fetchall()
    existing = {row["name"] for row in rows}
    columns = {
        "status": "TEXT DEFAULT 'success'",
        "image_url": "TEXT DEFAULT ''",
        "error_message": "TEXT DEFAULT ''",
        "request_id": "TEXT DEFAULT ''",
        "raw_response": "TEXT DEFAULT ''",
        "refunded_at": "TIMESTAMP",
        "updated_at": "TIMESTAMP DEFAULT ''",
    }
    for name, ddl in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE generation_logs ADD COLUMN {name} {ddl}")


def seed_pricing():
    """初始化模型定价"""
    pricing = [
        ("gemini-3-pro-image-preview", "Gemini 3 Pro", 6, 10, 18),
        ("gemini-3.1-flash-image-preview", "Gemini 3.1 Flash", 4, 6, 12),
        ("doubao-seedream-5-0-260128", "豆包图像 5.0", 3, 5, 10),
        ("suno-music", "Suno 音乐", 10, 10, 10),
        ("grok-video", "Grok 视频", 12, 12, 12),
    ]
    conn = get_db()
    for pid, name, p1, p2, p4 in pricing:
        conn.execute(
            "INSERT OR IGNORE INTO models_pricing (model_id, model_name, credits_1k, credits_2k, credits_4k) VALUES (?,?,?,?,?)",
            (pid, name, p1, p2, p4)
        )
    conn.commit()
    conn.close()


# ==================== 用户操作 ====================

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def create_user(username, password, nickname=""):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, nickname) VALUES (?,?,?)",
            (username, hash_password(password), nickname)
        )
        conn.commit()
        user_id = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()["id"]
        return user_id, None
    except sqlite3.IntegrityError:
        return None, "用户名已存在"
    finally:
        conn.close()


def verify_user(username, password):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    if user and user["password_hash"] == hash_password(password):
        return dict(user)
    return None


def get_user(user_id):
    conn = get_db()
    user = conn.execute("SELECT id, username, nickname, balance, role, agent_code, parent_id, created_at FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return dict(user) if user else None


def update_balance(user_id, delta):
    """增加/扣除余额（delta 为正数增加，负数扣除）"""
    conn = get_db()
    user = conn.execute("SELECT balance FROM users WHERE id=?", (user_id,)).fetchone()
    if not user:
        conn.close()
        return False, "用户不存在"
    new_balance = user["balance"] + delta
    if new_balance < 0:
        conn.close()
        return False, "余额不足"
    conn.execute("UPDATE users SET balance=? WHERE id=?", (new_balance, user_id))
    conn.commit()
    conn.close()
    return True, None


# ==================== 订单 ====================

def create_order(user_id, amount, credits, payment_method="alipay", trade_no=""):
    conn = get_db()
    conn.execute(
        "INSERT INTO orders (user_id, amount, credits, payment_method, status, trade_no) VALUES (?,?,?,?,?,?)",
        (user_id, amount, credits, payment_method, "pending", trade_no)
    )
    order_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    conn.close()
    return order_id


def complete_order(order_id):
    """完成订单，增加用户余额"""
    conn = get_db()
    order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if not order or order["status"] != "pending":
        conn.close()
        return False
    conn.execute("UPDATE orders SET status='completed' WHERE id=?", (order_id,))
    conn.execute("UPDATE users SET balance=balance+? WHERE id=?", (order["credits"], order["user_id"]))
    conn.commit()
    conn.close()
    return True


# ==================== 生成记录 ====================

def log_generation(
    user_id,
    model,
    credits_used,
    prompt,
    image_url="",
    status="success",
    error_message="",
    request_id="",
    raw_response="",
):
    conn = get_db()
    cur = conn.execute(
        """
        INSERT INTO generation_logs
            (user_id, model, credits_used, prompt, image_url, status, error_message, request_id, raw_response, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
        """,
        (user_id, model, credits_used, prompt, image_url, status, error_message, request_id, raw_response)
    )
    log_id = cur.lastrowid
    conn.commit()
    conn.close()
    return log_id


def update_generation_log(log_id, **kwargs):
    allowed = {
        "status",
        "image_url",
        "error_message",
        "request_id",
        "raw_response",
        "refunded_at",
    }
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    if updates.get("refunded_at") == "now":
        updates["refunded_at"] = now
    updates["updated_at"] = now
    sets = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [log_id]

    conn = get_db()
    conn.execute(f"UPDATE generation_logs SET {sets} WHERE id=?", values)
    conn.commit()
    conn.close()


def get_user_logs(user_id, limit=20):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM generation_logs WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ==================== 定价 ====================

def get_model_price(model_id, resolution="2K"):
    conn = get_db()
    price_row = conn.execute("SELECT * FROM models_pricing WHERE model_id=?", (model_id,)).fetchone()
    conn.close()
    if not price_row:
        return 5  # 默认 5 额度
    if resolution == "4K":
        return price_row["credits_4k"]
    elif resolution == "1K":
        return price_row["credits_1k"]
    else:
        return price_row["credits_2k"]


def get_all_pricing():
    conn = get_db()
    rows = conn.execute("SELECT * FROM models_pricing WHERE is_active=1").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ==================== 代理 ====================

def create_agent_config(user_id, wholesale_price=0.475):
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO agent_configs (user_id, wholesale_price) VALUES (?,?)",
        (user_id, wholesale_price)
    )
    conn.execute("UPDATE users SET role='agent' WHERE id=?", (user_id,))
    conn.commit()
    conn.close()


def get_agent_config(user_id):
    conn = get_db()
    config = conn.execute("SELECT * FROM agent_configs WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return dict(config) if config else None


def get_agent_children(agent_id):
    conn = get_db()
    rows = conn.execute("SELECT id, username, nickname, balance, created_at FROM users WHERE parent_id=?", (agent_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_agent_earnings(agent_id):
    """计算代理收益 = 下级用户的消费 * (1 - 平台抽成比例)"""
    conn = get_db()
    config = conn.execute("SELECT profit_share FROM agent_configs WHERE user_id=?", (agent_id,)).fetchone()
    conn.close()
    if not config:
        return 0
    share = config["profit_share"]
    logs = conn.execute(
        "SELECT SUM(l.credits_used) as total FROM generation_logs l JOIN users u ON l.user_id=u.id WHERE u.parent_id=? AND l.status='success'",
        (agent_id,)
    ).fetchone()
    total_credits = logs["total"] or 0
    # 代理收益 = 下级消费额度 * (1 - 平台抽成)
    earnings = total_credits * (1 - share)
    return round(earnings, 2)


# ==================== 系统设置 ====================

def get_setting(key, default=""):
    conn = get_db()
    row = conn.execute("SELECT value FROM system_settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key, value):
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO system_settings (key, value, updated_at) VALUES (?,?, datetime('now'))",
        (key, str(value))
    )
    conn.commit()
    conn.close()


def get_all_settings():
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM system_settings").fetchall()
    conn.close()
    return {row["key"]: row["value"] for row in rows}


def get_smtp_config():
    settings = get_all_settings()
    return {
        "server": settings.get("smtp_server", "smtp.qq.com"),
        "port": int(settings.get("smtp_port", 465)),
        "use_ssl": settings.get("smtp_use_ssl", "true") == "true",
        "account": settings.get("smtp_account", ""),
        "sender": settings.get("smtp_sender", ""),
        "password": settings.get("smtp_password", ""),
    }


def get_oauth_config():
    settings = get_all_settings()
    return {
        "google_client_id": settings.get("oauth_google_client_id", ""),
        "google_secret": settings.get("oauth_google_secret", ""),
        "github_client_id": settings.get("oauth_github_client_id", ""),
        "github_secret": settings.get("oauth_github_secret", ""),
    }
