"""Settings API — 前端保存 API Key 到后端"""
import os
from flask import Blueprint, jsonify, request
import database as db

bp = Blueprint("settings_api", __name__, url_prefix="/api")

@bp.route("/settings", methods=["POST"])
def save_settings():
    data = request.get_json(force=True) or {}
    if data.get("api_key"):
        db.set_setting("tikpan_api_key", data["api_key"])
        os.environ["TIKPAN_API_KEY"] = data["api_key"]
        # 更新 tikpan_client 的 API_KEY
        import tikpan_client as tc
        tc.API_KEY = data["api_key"]
    if data.get("api_host"):
        db.set_setting("tikpan_api_host", data["api_host"])
        os.environ["TIKPAN_API_HOST"] = data["api_host"]
        import tikpan_client as tc
        tc.API_HOST = data["api_host"]
    return jsonify({"ok": True})

@bp.route("/settings", methods=["GET"])
def get_settings():
    return jsonify({
        "api_key_set": bool(os.environ.get("TIKPAN_API_KEY") or db.get_setting("tikpan_api_key")),
        "api_host": os.environ.get("TIKPAN_API_HOST", db.get_setting("tikpan_api_host", "https://tikpan.com")),
    })
