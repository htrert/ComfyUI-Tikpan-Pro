from __future__ import annotations

import argparse

from portable_db import DEFAULT_SEED_PATH, apply_schema, connect, import_payload, parse_db_arg, read_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize Tikpan web_app database schema.")
    parse_db_arg(parser)
    parser.add_argument(
        "--seed",
        default=str(DEFAULT_SEED_PATH),
        help="Optional portable seed JSON to import after schema creation. Use empty string to skip.",
    )
    args = parser.parse_args()

    with connect(args.db) as conn:
        apply_schema(conn)
        imported = {}
        if args.seed:
            imported = import_payload(conn, read_json(args.seed))

    print(f"Database initialized: {args.db}")
    if imported:
        print("Seed imported: " + ", ".join(f"{k}={v}" for k, v in imported.items()))


if __name__ == "__main__":
    main()
