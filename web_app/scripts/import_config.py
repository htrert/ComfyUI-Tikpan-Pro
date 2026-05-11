from __future__ import annotations

import argparse

from portable_db import apply_schema, connect, import_payload, parse_db_arg, read_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Import portable Tikpan model/channel/billing configuration.")
    parse_db_arg(parser)
    parser.add_argument(
        "--in",
        dest="input_path",
        required=True,
        help="Input JSON exported by export_config.py.",
    )
    args = parser.parse_args()

    with connect(args.db) as conn:
        apply_schema(conn)
        imported = import_payload(conn, read_json(args.input_path))

    print(f"Imported config into: {args.db}")
    print(", ".join(f"{k}={v}" for k, v in imported.items()))


if __name__ == "__main__":
    main()
