from __future__ import annotations

import argparse

from portable_db import DEFAULT_EXPORT_PATH, apply_schema, build_export, connect, parse_db_arg, write_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Export portable Tikpan model/channel/billing configuration.")
    parse_db_arg(parser)
    parser.add_argument(
        "--out",
        default=str(DEFAULT_EXPORT_PATH),
        help=f"Output JSON path. Default: {DEFAULT_EXPORT_PATH}",
    )
    parser.add_argument(
        "--include-secrets",
        action="store_true",
        help="Export provider API keys and sensitive settings. Keep the file private and do not commit it.",
    )
    args = parser.parse_args()

    with connect(args.db) as conn:
        apply_schema(conn)
        payload = build_export(conn, include_secrets=args.include_secrets)

    write_json(args.out, payload)
    mode = "private with secrets" if args.include_secrets else "portable redacted"
    print(f"Exported {mode} config: {args.out}")


if __name__ == "__main__":
    main()
