from __future__ import annotations

import argparse
import base64
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECOVERY_DIR = ROOT / "recovery" / "gpt_image_2"
DEFAULT_OUTPUT_DIR = DEFAULT_RECOVERY_DIR / "images_recovered"


def load_embedded_response(record):
    response = record.get("response")
    if isinstance(response, dict):
        return response
    if isinstance(response, str):
        cleaned = response.strip()
        if cleaned.endswith("...(truncated)"):
            return {"_truncated": True, "_raw": cleaned}
        try:
            return json.loads(cleaned)
        except Exception:
            return {"_raw": cleaned}
    return record


def scan_image_items(obj):
    items = []
    seen = set()

    def add(kind, value):
        if not isinstance(value, str):
            return
        value = value.strip()
        if not value:
            return
        if value.startswith(("http://", "https://")):
            kind = "url"
        elif value.startswith("data:image"):
            kind = "base64"
        elif kind == "base64" and len(value) < 512:
            return
        marker = (kind, value[:160])
        if marker in seen:
            return
        seen.add(marker)
        items.append((kind, value))

    def walk(value):
        if isinstance(value, str):
            if value.startswith(("http://", "https://")):
                add("url", value)
            elif value.startswith("data:image"):
                add("base64", value)
            return
        if isinstance(value, list):
            for item in value:
                walk(item)
            return
        if not isinstance(value, dict):
            return
        for key in ("url", "image_url", "imageUrl"):
            add("url", value.get(key))
        for key in ("b64_json", "image_base64", "base64", "image"):
            add("base64", value.get(key))
        nested = value.get("image_url")
        if isinstance(nested, dict):
            add("url", nested.get("url"))
        for child in value.values():
            walk(child)

    walk(obj)
    return items


def extension_from_bytes(data):
    if data.startswith(b"\x89PNG"):
        return "png"
    if data.startswith(b"\xff\xd8"):
        return "jpg"
    if data.startswith(b"RIFF") and b"WEBP" in data[:16]:
        return "webp"
    return "png"


def decode_base64_image(value):
    if "base64," in value:
        value = value.split("base64,", 1)[1]
    clean = re.sub(r"\s+", "", value)
    if clean.endswith("...(truncated)") or "(truncated)" in clean:
        raise ValueError("base64 was truncated by the old recovery logger")
    missing_padding = len(clean) % 4
    if missing_padding:
        clean += "=" * (4 - missing_padding)
    return base64.b64decode(clean, validate=True)


def download_url(url):
    request = Request(url, headers={"User-Agent": "Tikpan-Recovery/1.0"})
    with urlopen(request, timeout=90) as resp:
        return resp.read()


def recover_file(path, output_dir, dry_run=False):
    record = json.loads(path.read_text(encoding="utf-8"))
    response = load_embedded_response(record)
    key = record.get("idempotency_key") or path.stem
    if isinstance(response, dict) and response.get("_truncated"):
        return {"saved": [], "errors": ["response field is truncated; cannot decode image from this JSON"]}

    saved = []
    errors = []
    items = scan_image_items(response)
    for index, (kind, value) in enumerate(items, start=1):
        try:
            data = download_url(value) if kind == "url" else decode_base64_image(value)
            ext = extension_from_bytes(data)
            target = output_dir / f"{key}_{index:02d}.{ext}"
            if not dry_run:
                output_dir.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            saved.append(str(target))
        except Exception as exc:
            errors.append(f"{kind} item {index}: {exc}")
    if not items:
        errors.append("no image URL/base64 found")
    return {"saved": saved, "errors": errors}


def main():
    parser = argparse.ArgumentParser(description="Recover GPT-Image-2 images from Tikpan recovery JSON files.")
    parser.add_argument("--recovery-dir", default=str(DEFAULT_RECOVERY_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    recovery_dir = Path(args.recovery_dir)
    output_dir = Path(args.output_dir)
    json_files = sorted(recovery_dir.glob("*.json"))
    total_saved = 0
    total_errors = 0
    for path in json_files:
        result = recover_file(path, output_dir, dry_run=args.dry_run)
        if result["saved"]:
            print(f"OK {path.name}: {len(result['saved'])} image(s)")
            for item in result["saved"]:
                print(f"  {item}")
        if result["errors"]:
            print(f"SKIP {path.name}: {'; '.join(result['errors'][:3])}")
        total_saved += len(result["saved"])
        total_errors += len(result["errors"])
    print(f"DONE files={len(json_files)} saved={total_saved} errors={total_errors} output={output_dir}")


if __name__ == "__main__":
    main()
