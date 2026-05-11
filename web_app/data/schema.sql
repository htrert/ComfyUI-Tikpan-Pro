PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    icon TEXT DEFAULT '',
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
    error_message TEXT DEFAULT '',
    request_id TEXT DEFAULT '',
    raw_response TEXT DEFAULT '',
    refunded_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT '',
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS models_pricing (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id TEXT UNIQUE NOT NULL,
    model_name TEXT NOT NULL,
    credits_1k INTEGER DEFAULT 5,
    credits_2k INTEGER DEFAULT 8,
    credits_4k INTEGER DEFAULT 15,
    billing_mode TEXT DEFAULT 'resolution',
    unit_name TEXT DEFAULT 'generation',
    unit_field TEXT DEFAULT '',
    unit_credits REAL DEFAULT 0,
    min_credits INTEGER DEFAULT 0,
    cost_per_unit REAL DEFAULT 0,
    retail_markup REAL DEFAULT 1.0,
    is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS provider_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    provider_type TEXT DEFAULT '',
    base_url TEXT DEFAULT '',
    api_key TEXT DEFAULT '',
    priority INTEGER DEFAULT 100,
    weight INTEGER DEFAULT 1,
    timeout_seconds INTEGER DEFAULT 120,
    is_active INTEGER DEFAULT 1,
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS model_provider_routes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id TEXT NOT NULL,
    channel_key TEXT NOT NULL,
    upstream_model TEXT DEFAULT '',
    endpoint TEXT DEFAULT '',
    priority INTEGER DEFAULT 100,
    weight INTEGER DEFAULT 1,
    cost_per_unit REAL DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(model_id, channel_key)
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

CREATE INDEX IF NOT EXISTS idx_models_category ON models(category_key, sort_order);
CREATE INDEX IF NOT EXISTS idx_model_fields_model ON model_fields(model_id, sort_order);
CREATE INDEX IF NOT EXISTS idx_generation_logs_user_created ON generation_logs(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_model_routes_model ON model_provider_routes(model_id, priority);
CREATE INDEX IF NOT EXISTS idx_provider_channels_active ON provider_channels(is_active, priority);
