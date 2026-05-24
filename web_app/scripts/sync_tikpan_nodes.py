from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


WEB_APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WEB_APP_DIR))

from backend.database import add_category, add_field, add_model, get_db, init_db  # noqa: E402
from catalog.tikpan_nodes import CATEGORIES, MODELS  # noqa: E402
from models import init_db as init_business_db  # noqa: E402
from models import seed_provider_channels, upsert_model_route, upsert_pricing  # noqa: E402


def sync_catalog(dry_run=False):
    init_db()
    init_business_db()
    seed_provider_channels()

    if dry_run:
        return {
            "categories": len(CATEGORIES),
            "models": len(MODELS),
            "fields": sum(len(m.get("fields", [])) for m in MODELS),
            "routes": len(MODELS),
        }

    for category in CATEGORIES:
        add_category(
            category["key"],
            category["name"],
            category.get("icon", ""),
            int(category.get("sort_order", 0)),
        )

    for model in MODELS:
        model_id = model["id"]
        add_model(
            model_id,
            model["category_key"],
            model["name"],
            model.get("provider", ""),
            model.get("description", ""),
            model.get("api_type", "tikpan_proxy"),
            model.get("endpoint", ""),
            int(model.get("sort_order", 0)),
            json.dumps(model.get("usage", []), ensure_ascii=False),
            model.get("node_class", ""),
        )

        conn = get_db()
        conn.execute("DELETE FROM model_fields WHERE model_id=?", (model_id,))
        conn.commit()
        conn.close()

        for index, item in enumerate(model.get("fields", []), start=1):
            add_field(
                model_id,
                item["field_key"],
                item.get("field_type", "text"),
                item.get("label", item["field_key"]),
                item.get("placeholder", ""),
                item.get("default_value", ""),
                int(item.get("required", 0)),
                json.dumps(item.get("options", []), ensure_ascii=False),
                int(item.get("max_count", 0)),
                int(item.get("rows", 4)),
                int(item.get("sort_order") or index),
                int(item.get("is_group", 0)),
                json.dumps(item.get("group_config", {}), ensure_ascii=False),
                item.get("hint", ""),
                item.get("min", ""),
                item.get("max", ""),
                item.get("step", ""),
            )

        pricing = dict(model.get("pricing", {}))
        pricing.setdefault("model_id", model_id)
        pricing.setdefault("model_name", model["name"])
        pricing.setdefault("credits_1k", 5)
        pricing.setdefault("credits_2k", 8)
        pricing.setdefault("credits_4k", 15)
        pricing.setdefault("billing_mode", "resolution")
        pricing.setdefault("is_active", 1)
        upsert_pricing(pricing)

        upsert_model_route(
            {
                "model_id": model_id,
                "channel_key": "tikpan-default",
                "upstream_model": model.get("upstream_model", model_id),
                "endpoint": model.get("endpoint", ""),
                "priority": 10,
                "weight": 1,
                "cost_per_unit": pricing.get("cost_per_unit", 0),
                "is_active": 1,
                "notes": f"Synced from ComfyUI node {model.get('node_class', '')}",
            }
        )

    return {
        "categories": len(CATEGORIES),
        "models": len(MODELS),
        "fields": sum(len(m.get("fields", [])) for m in MODELS),
        "routes": len(MODELS),
    }


def main():
    parser = argparse.ArgumentParser(description="Sync local Tikpan ComfyUI nodes into web_app model config.")
    parser.add_argument("--dry-run", action="store_true", help="Only print the number of items that would be synced.")
    args = parser.parse_args()
    summary = sync_catalog(dry_run=args.dry_run)
    mode = "DRY RUN" if args.dry_run else "SYNCED"
    print(f"{mode}: {summary['categories']} categories, {summary['models']} models, {summary['fields']} fields, {summary['routes']} routes")


if __name__ == "__main__":
    main()
