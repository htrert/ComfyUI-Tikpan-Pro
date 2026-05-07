"""
🗄️ 数据库层 - SQLite模型配置存储
所有模型/分类/字段配置存在数据库里，管理员可通过后台增删改
"""
import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "tikpan.db")


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """初始化数据库表结构"""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            icon TEXT DEFAULT '📦',
            sort_order INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS models (
            id TEXT PRIMARY KEY,
            category_key TEXT NOT NULL,
            name TEXT NOT NULL,
            provider TEXT DEFAULT '',
            description TEXT DEFAULT '',
            api_type TEXT NOT NULL DEFAULT 'gemini_native',
            endpoint TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_key) REFERENCES categories(key)
        );

        CREATE TABLE IF NOT EXISTS model_fields (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id TEXT NOT NULL,
            field_key TEXT NOT NULL,
            field_type TEXT NOT NULL DEFAULT 'textarea',
            label TEXT NOT NULL,
            placeholder TEXT DEFAULT '',
            default_value TEXT DEFAULT '',
            required INTEGER DEFAULT 0,
            options_json TEXT DEFAULT '[]',
            max_count INTEGER DEFAULT 0,
            rows INTEGER DEFAULT 4,
            sort_order INTEGER DEFAULT 0,
            is_group INTEGER DEFAULT 0,
            group_config_json TEXT DEFAULT '{}',
            FOREIGN KEY (model_id) REFERENCES models(id),
            UNIQUE(model_id, field_key)
        );

        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()


# ==================== Categories ====================

def get_categories():
    conn = get_db()
    rows = conn.execute("SELECT * FROM categories ORDER BY sort_order, id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_category(key, name, icon="📦", sort_order=0):
    conn = get_db()
    conn.execute("INSERT OR IGNORE INTO categories (key, name, icon, sort_order) VALUES (?, ?, ?, ?)",
                 (key, name, icon, sort_order))
    conn.commit()
    conn.close()


def update_category(cat_id, **kwargs):
    conn = get_db()
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [cat_id]
    conn.execute(f"UPDATE categories SET {sets} WHERE id=?", vals)
    conn.commit()
    conn.close()


def delete_category(cat_id):
    conn = get_db()
    conn.execute("DELETE FROM categories WHERE id=?", (cat_id,))
    conn.commit()
    conn.close()


# ==================== Models ====================

def get_models(category_key=None, active_only=True):
    conn = get_db()
    if category_key:
        if active_only:
            rows = conn.execute("SELECT * FROM models WHERE category_key=? AND is_active=1 ORDER BY sort_order, id", (category_key,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM models WHERE category_key=? ORDER BY sort_order, id", (category_key,)).fetchall()
    else:
        if active_only:
            rows = conn.execute("SELECT * FROM models WHERE is_active=1 ORDER BY sort_order, id").fetchall()
        else:
            rows = conn.execute("SELECT * FROM models ORDER BY sort_order, id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_model(model_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM models WHERE id=?", (model_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_model(model_id, category_key, name, provider="", description="", api_type="gemini_native", endpoint="", sort_order=0):
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO models (id, category_key, name, provider, description, api_type, endpoint, sort_order) VALUES (?,?,?,?,?,?,?,?)",
        (model_id, category_key, name, provider, description, api_type, endpoint, sort_order))
    conn.commit()
    conn.close()


def update_model(model_id, **kwargs):
    conn = get_db()
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [model_id]
    conn.execute(f"UPDATE models SET {sets} WHERE id=?", vals)
    conn.commit()
    conn.close()


def delete_model(model_id):
    conn = get_db()
    conn.execute("DELETE FROM model_fields WHERE model_id=?", (model_id,))
    conn.execute("DELETE FROM models WHERE id=?", (model_id,))
    conn.commit()
    conn.close()


# ==================== Fields ====================

def get_fields(model_id):
    conn = get_db()
    rows = conn.execute("SELECT * FROM model_fields WHERE model_id=? ORDER BY sort_order, id", (model_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_field(model_id, field_key, field_type="textarea", label="", placeholder="", default_value="",
              required=0, options_json="[]", max_count=0, rows=4, sort_order=0,
              is_group=0, group_config_json="{}"):
    conn = get_db()
    conn.execute(
        "INSERT OR IGNORE INTO model_fields (model_id, field_key, field_type, label, placeholder, default_value, required, options_json, max_count, rows, sort_order, is_group, group_config_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (model_id, field_key, field_type, label, placeholder, default_value, required, options_json, max_count, rows, sort_order, is_group, group_config_json))
    conn.commit()
    conn.close()


def update_field(field_id, **kwargs):
    conn = get_db()
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [field_id]
    conn.execute(f"UPDATE model_fields SET {sets} WHERE id=?", vals)
    conn.commit()
    conn.close()


def delete_field(field_id):
    conn = get_db()
    conn.execute("DELETE FROM model_fields WHERE id=?", (field_id,))
    conn.commit()
    conn.close()


# ==================== 构建带字段的完整模型树 ====================

def get_full_model_tree():
    """返回完整的分类→模型→字段树结构（前端使用）"""
    categories = get_categories()
    result = {}
    for cat in categories:
        models = get_models(cat["key"])
        model_list = []
        for m in models:
            fields = get_fields(m["id"])
            # 将字段转换成前端需要的格式
            field_list = []
            for f in fields:
                entry = {
                    "key": f["field_key"],
                    "type": f["field_type"],
                    "label": f["label"],
                    "placeholder": f["placeholder"],
                    "default": f["default_value"],
                    "required": bool(f["required"]),
                    "rows": f["rows"],
                }
                if f["field_type"] == "select" or f["field_type"] == "file_image":
                    try:
                        entry["options"] = json.loads(f["options_json"]) if f["options_json"] else []
                    except:
                        entry["options"] = []
                if f["field_type"] == "file_image":
                    entry["multiple"] = True
                    entry["max_count"] = f["max_count"]
                    entry["accept"] = "image/*"
                if f["field_type"] == "select":
                    entry["options"] = entry.get("options", [])
                if f["is_group"]:
                    try:
                        entry["groups"] = json.loads(f["group_config_json"]) if f["group_config_json"] else {}
                    except:
                        entry["groups"] = {}
                field_list.append(entry)
            model_list.append({
                "id": m["id"],
                "name": m["name"],
                "provider": m["provider"],
                "description": m["description"],
                "api_type": m["api_type"],
                "endpoint": m["endpoint"],
                "fields": field_list,
            })
        if model_list:
            result[cat["key"]] = {
                "name": cat["name"],
                "icon": cat["icon"],
                "models": model_list,
            }
    return result


# ==================== 种子数据 ====================

def seed_default_data():
    """初始化默认的分类和模型数据"""
    init_db()

    # 分类
    add_category("image_generation", "🖼️ 图像生成", "🖼️", 1)
    add_category("music_generation", "🎵 音乐生成", "🎵", 2)
    add_category("video_generation", "🎬 视频生成", "🎬", 3)

    # Gemini 3 Pro
    add_model("gemini-3-pro-image-preview", "image_generation",
              "Gemini 3 Pro Image", "Google / Tikpan",
              "最强图像生成模型，支持2K/4K高清出图",
              "gemini_native", "/v1beta/models/gemini-3-pro-image-preview:generateContent", 1)
    add_field("gemini-3-pro-image-preview", "prompt", "textarea", "📝 提示词",
              "描述你想要生成的画面...", "", 1, "[]", 0, 4, 1)
    add_field("gemini-3-pro-image-preview", "resolution", "select", "📐 分辨率",
              "", "2K", 0, '["1K","2K","4K"]', 0, 0, 2)
    add_field("gemini-3-pro-image-preview", "aspect_ratio", "select", "📏 画面比例",
              "", "1:1", 0, '["1:1","16:9","9:16","21:9","4:3","3:4","3:2","2:3"]', 0, 0, 3)
    add_field("gemini-3-pro-image-preview", "reference_images", "file_image", "🖼️ 参考图（可选）",
              "", "", 0, "[]", 14, 0, 4)
    add_field("gemini-3-pro-image-preview", "seed", "number", "🎲 随机种子",
              "", "888888", 0, "[]", 0, 0, 5)

    # Gemini Flash
    add_model("gemini-3.1-flash-image-preview", "image_generation",
              "Gemini 3.1 Flash", "Google / Tikpan",
              "快速轻量版，同样支持2K/4K，适合高频生成",
              "gemini_native", "/v1beta/models/gemini-3.1-flash-image-preview:generateContent", 2)
    add_field("gemini-3.1-flash-image-preview", "prompt", "textarea", "📝 提示词",
              "描述你想要生成的画面...", "", 1, "[]", 0, 4, 1)
    add_field("gemini-3.1-flash-image-preview", "resolution", "select", "📐 分辨率",
              "", "2K", 0, '["1K","2K","4K"]', 0, 0, 2)
    add_field("gemini-3.1-flash-image-preview", "aspect_ratio", "select", "📏 画面比例",
              "", "1:1", 0, '["1:1","16:9","9:16","21:9","4:3","3:4","3:2","2:3"]', 0, 0, 3)
    add_field("gemini-3.1-flash-image-preview", "reference_images", "file_image", "🖼️ 参考图（可选）",
              "", "", 0, "[]", 14, 0, 4)
    add_field("gemini-3.1-flash-image-preview", "seed", "number", "🎲 随机种子",
              "", "888888", 0, "[]", 0, 0, 5)

    # 豆包
    add_model("doubao", "image_generation",
              "豆包图像 (Seedream)", "字节跳动 / Tikpan",
              "字节豆包系列模型，5.0支持高清组图",
              "doubao", "/v1/images/generations", 3)
    add_field("doubao", "prompt", "textarea", "📝 提示词",
              "描述你想要生成的画面...", "", 1, "[]", 0, 4, 1)
    add_field("doubao", "model_variant", "select", "🧬 模型版本",
              "", "doubao-seedream-5-0", 0,
              '["doubao-seedream-5-0","doubao-seedream-4-5","doubao-seedream-4-0","doubao-seededit-3-0-i2i"]', 0, 0, 2)
    add_field("doubao", "size", "select", "📐 图片尺寸",
              "", "1024x1024", 0, '["1024x1024","1152x2048","2048x2048"]', 0, 0, 3)
    add_field("doubao", "reference_images", "file_image", "🖼️ 参考图（可选）",
              "", "", 0, "[]", 14, 0, 4)
    add_field("doubao", "n", "number", "生成张数",
              "", "1", 0, "[]", 0, 0, 5)

    # Suno
    suno_groups = json.dumps({
        "灵感模式": {"desc": "只需描述，AI自动生成歌词", "fields_extra": [{"key": "make_instrumental", "type": "checkbox", "label": "纯音乐（无歌词）", "default": False}]},
        "自定义模式": {"desc": "完整歌词 + 标题 + 风格", "fields_extra": [{"key": "title", "type": "text", "label": "歌曲标题", "placeholder": "输入标题"}, {"key": "tags", "type": "text", "label": "风格标签", "placeholder": "pop, rock, 电子"}]},
        "续写模式": {"desc": "基于已有歌曲继续创作", "fields_extra": [{"key": "continue_clip_id", "type": "text", "label": "续写片段ID", "placeholder": "输入已有片段ID"}, {"key": "continue_at", "type": "number", "label": "续写位置(秒)", "default": 0}]},
        "歌手风格": {"desc": "模仿特定歌手的风格", "fields_extra": [{"key": "persona_id", "type": "text", "label": "歌手ID", "placeholder": "输入歌手ID"}]}
    }, ensure_ascii=False)

    add_model("suno-music", "music_generation",
              "Suno AI 音乐", "Suno / Tikpan",
              "AI音乐生成，支持灵感/自定义/续写/模仿多种模式",
              "suno", "", 1)
    add_field("suno-music", "mode", "select_group", "🎯 生成模式",
              "", "灵感模式", 0, '["灵感模式","自定义模式","续写模式","歌手风格"]', 0, 0, 1, 1, suno_groups)
    add_field("suno-music", "prompt", "textarea", "📝 描述/歌词",
              "灵感模式：描述你想要的音乐风格", "", 1, "[]", 0, 4, 2)
    add_field("suno-music", "model_version", "select", "🧬 模型版本",
              "", "chirp-v5", 0, '["chirp-v3-0","chirp-v3-5","chirp-v4","chirp-v5","chirp-fenix"]', 0, 0, 3)

    # Grok 视频
    add_model("grok-video", "video_generation",
              "Grok 视频", "xAI / Tikpan",
              "AI视频生成，输入提示词生成短视频",
              "grok_video", "/v1/video/grok", 1)
    add_field("grok-video", "prompt", "textarea", "📝 视频描述",
              "描述你想要的视频画面...", "", 1, "[]", 0, 4, 1)
    add_field("grok-video", "duration", "select", "⏱️ 时长",
              "", "5s", 0, '["5s","10s"]', 0, 0, 2)


if __name__ == "__main__":
    seed_default_data()
    print("✅ 数据库初始化完成")
