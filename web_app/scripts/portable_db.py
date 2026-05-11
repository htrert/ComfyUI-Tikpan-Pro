from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


WEB_APP_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = WEB_APP_DIR / "data"
DEFAULT_DB_PATH = DATA_DIR / "tikpan.db"
SCHEMA_PATH = DATA_DIR / "schema.sql"
DEFAULT_EXPORT_PATH = DATA_DIR / "config.export.json"
DEFAULT_SEED_PATH = DATA_DIR / "seed.example.json"

EXPORT_TABLES = {
    "categories": ["key", "name", "icon", "sort_order"],
    "models": [
        "id",
        "category_key",
        "name",
        "provider",
        "description",
        "api_type",
        "endpoint",
        "is_active",
        "sort_order",
    ],
    "model_fields": [
        "model_id",
        "field_key",
        "field_type",
        "label",
        "placeholder",
        "default_value",
        "required",
        "options_json",
        "max_count",
        "rows",
        "sort_order",
        "is_group",
        "group_config_json",
    ],
    "models_pricing": [
        "model_id",
        "model_name",
        "credits_1k",
        "credits_2k",
        "credits_4k",
        "billing_mode",
        "unit_name",
        "unit_field",
        "unit_credits",
        "min_credits",
        "cost_per_unit",
        "retail_markup",
        "is_active",
    ],
    "provider_channels": [
        "key",
        "name",
        "provider_type",
        "base_url",
        "api_key",
        "priority",
        "weight",
        "timeout_seconds",
        "is_active",
        "notes",
    ],
    "model_provider_routes": [
        "model_id",
        "channel_key",
        "upstream_model",
        "endpoint",
        "priority",
        "weight",
        "cost_per_unit",
        "is_active",
        "notes",
    ],
    "system_settings": ["key", "value"],
}

SENSITIVE_SETTING_HINTS = ("password", "secret", "token", "api_key", "apikey", "private", "credential")

COMPAT_COLUMNS = {
    "generation_logs": {
        "status": "TEXT DEFAULT 'success'",
        "image_url": "TEXT DEFAULT ''",
        "error_message": "TEXT DEFAULT ''",
        "request_id": "TEXT DEFAULT ''",
        "raw_response": "TEXT DEFAULT ''",
        "refunded_at": "TIMESTAMP",
        "updated_at": "TIMESTAMP DEFAULT ''",
    },
    "models_pricing": {
        "billing_mode": "TEXT DEFAULT 'resolution'",
        "unit_name": "TEXT DEFAULT 'generation'",
        "unit_field": "TEXT DEFAULT ''",
        "unit_credits": "REAL DEFAULT 0",
        "min_credits": "INTEGER DEFAULT 0",
        "cost_per_unit": "REAL DEFAULT 0",
        "retail_markup": "REAL DEFAULT 1.0",
        "is_active": "INTEGER DEFAULT 1",
    },
    "provider_channels": {
        "provider_type": "TEXT DEFAULT ''",
        "base_url": "TEXT DEFAULT ''",
        "api_key": "TEXT DEFAULT ''",
        "priority": "INTEGER DEFAULT 100",
        "weight": "INTEGER DEFAULT 1",
        "timeout_seconds": "INTEGER DEFAULT 120",
        "is_active": "INTEGER DEFAULT 1",
        "notes": "TEXT DEFAULT ''",
        "created_at": "TIMESTAMP DEFAULT ''",
        "updated_at": "TIMESTAMP DEFAULT ''",
    },
    "model_provider_routes": {
        "upstream_model": "TEXT DEFAULT ''",
        "endpoint": "TEXT DEFAULT ''",
        "priority": "INTEGER DEFAULT 100",
        "weight": "INTEGER DEFAULT 1",
        "cost_per_unit": "REAL DEFAULT 0",
        "is_active": "INTEGER DEFAULT 1",
        "notes": "TEXT DEFAULT ''",
        "created_at": "TIMESTAMP DEFAULT ''",
        "updated_at": "TIMESTAMP DEFAULT ''",
    },
}


def parse_db_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB_PATH),
        help=f"SQLite database path. Default: {DEFAULT_DB_PATH}",
    )


def connect(db_path: str | os.PathLike[str]) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def apply_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    ensure_compatible_columns(conn)
    conn.commit()


def ensure_compatible_columns(conn: sqlite3.Connection) -> None:
    for table, columns in COMPAT_COLUMNS.items():
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        for column, ddl in columns.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def fetch_rows(conn: sqlite3.Connection, table: str, columns: list[str]) -> list[dict[str, Any]]:
    sql = f"SELECT {', '.join(columns)} FROM {table}"
    if table == "model_fields":
        sql += " ORDER BY model_id, sort_order, field_key"
    elif table == "model_provider_routes":
        sql += " ORDER BY model_id, priority, channel_key"
    elif "sort_order" in columns:
        sql += " ORDER BY sort_order"
    elif "key" in columns:
        sql += " ORDER BY key"
    elif "model_id" in columns:
        sql += " ORDER BY model_id"
    return [dict(row) for row in conn.execute(sql).fetchall()]


def is_sensitive_setting(key: str) -> bool:
    lowered = key.lower()
    return any(hint in lowered for hint in SENSITIVE_SETTING_HINTS)


def redact_export(tables: dict[str, list[dict[str, Any]]], include_secrets: bool) -> bool:
    if include_secrets:
        return False

    for row in tables.get("provider_channels", []):
        row["api_key"] = ""

    for row in tables.get("system_settings", []):
        if is_sensitive_setting(str(row.get("key", ""))):
            row["value"] = ""

    return True


def build_export(conn: sqlite3.Connection, include_secrets: bool = False) -> dict[str, Any]:
    tables = {
        table: fetch_rows(conn, table, columns)
        for table, columns in EXPORT_TABLES.items()
    }
    redacted = redact_export(tables, include_secrets)
    return {
        "version": 1,
        "source": "tikpan-web-app",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "redacted": redacted,
        "tables": tables,
    }


def write_json(path: str | os.PathLike[str], payload: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: str | os.PathLike[str]) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _values(row: dict[str, Any], columns: list[str]) -> list[Any]:
    return [row.get(column) for column in columns]


def _upsert(
    conn: sqlite3.Connection,
    table: str,
    columns: list[str],
    conflict: str,
    rows: list[dict[str, Any]],
    preserve_blank: set[str] | None = None,
) -> int:
    if not rows:
        return 0
    preserve_blank = preserve_blank or set()
    conflict_columns = {column.strip() for column in conflict.strip("()").split(",")}
    placeholders = ", ".join("?" for _ in columns)
    assignments = []
    for column in columns:
        if column in preserve_blank:
            assignments.append(f"{column}=CASE WHEN excluded.{column}='' THEN {table}.{column} ELSE excluded.{column} END")
        elif column not in conflict_columns:
            assignments.append(f"{column}=excluded.{column}")
    sql = f"""
        INSERT INTO {table} ({', '.join(columns)})
        VALUES ({placeholders})
        ON CONFLICT{conflict} DO UPDATE SET {', '.join(assignments)}
    """
    conn.executemany(sql, [_values(row, columns) for row in rows])
    return len(rows)


def import_payload(conn: sqlite3.Connection, payload: dict[str, Any]) -> dict[str, int]:
    tables = payload.get("tables", payload)
    imported: dict[str, int] = {}

    imported["categories"] = _upsert(
        conn,
        "categories",
        EXPORT_TABLES["categories"],
        "(key)",
        tables.get("categories", []),
    )
    imported["models"] = _upsert(
        conn,
        "models",
        EXPORT_TABLES["models"],
        "(id)",
        tables.get("models", []),
    )
    imported["model_fields"] = _upsert(
        conn,
        "model_fields",
        EXPORT_TABLES["model_fields"],
        "(model_id, field_key)",
        tables.get("model_fields", []),
    )
    imported["models_pricing"] = _upsert(
        conn,
        "models_pricing",
        EXPORT_TABLES["models_pricing"],
        "(model_id)",
        tables.get("models_pricing", []),
    )
    imported["provider_channels"] = _upsert(
        conn,
        "provider_channels",
        EXPORT_TABLES["provider_channels"],
        "(key)",
        tables.get("provider_channels", []),
        preserve_blank={"api_key"},
    )
    imported["model_provider_routes"] = _upsert(
        conn,
        "model_provider_routes",
        EXPORT_TABLES["model_provider_routes"],
        "(model_id, channel_key)",
        tables.get("model_provider_routes", []),
    )

    settings_count = 0
    for row in tables.get("system_settings", []):
        key = str(row.get("key", ""))
        value = str(row.get("value", ""))
        if not key:
            continue
        if value == "" and is_sensitive_setting(key):
            continue
        conn.execute(
            """
            INSERT INTO system_settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP
            """,
            (key, value),
        )
        settings_count += 1
    imported["system_settings"] = settings_count

    conn.commit()
    return imported
