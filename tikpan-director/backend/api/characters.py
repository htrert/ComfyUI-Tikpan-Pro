"""角色 & 场景资源库 API"""
import os
import uuid
from flask import Blueprint, jsonify, request, current_app
import database as db

bp = Blueprint("characters", __name__)

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data", "uploads")


def _save_upload(file_obj, subdir=""):
    """保存上传文件，返回相对路径 URL"""
    ext = (file_obj.filename or "img").rsplit(".", 1)[-1].lower()
    ext = ext if ext in ("jpg", "jpeg", "png", "webp") else "jpg"
    filename = f"{uuid.uuid4().hex[:12]}.{ext}"
    save_dir = os.path.join(UPLOAD_DIR, subdir) if subdir else UPLOAD_DIR
    os.makedirs(save_dir, exist_ok=True)
    file_obj.save(os.path.join(save_dir, filename))
    return f"/uploads/{subdir + '/' if subdir else ''}{filename}"


# ─── 角色 ─────────────────────────────────────────────────────────────────

@bp.route("/api/projects/<pid>/characters", methods=["GET"])
def list_characters(pid):
    return jsonify(db.list_characters(pid))


@bp.route("/api/projects/<pid>/characters", methods=["POST"])
def create_character(pid):
    # 支持 multipart（有图片）和 JSON（无图片）
    if request.content_type and "multipart" in request.content_type:
        data = request.form.to_dict()
        image_url = ""
        if "image" in request.files:
            image_url = _save_upload(request.files["image"], "characters")
    else:
        data = request.get_json(force=True) or {}
        image_url = data.get("image_url", "")

    name = str(data.get("name", "")).strip()
    if not name:
        return jsonify({"error": "角色名不能为空"}), 400

    char = db.create_character(
        project_id=pid,
        name=name,
        description=data.get("description", ""),
        personality=data.get("personality", ""),
        appearance=data.get("appearance", ""),
        prompt_tags=data.get("prompt_tags", ""),
        image_url=image_url,
    )
    return jsonify(char), 201


@bp.route("/api/characters/<cid>", methods=["PATCH"])
def update_character(cid):
    if request.content_type and "multipart" in request.content_type:
        data = request.form.to_dict()
        if "image" in request.files:
            data["image_url"] = _save_upload(request.files["image"], "characters")
    else:
        data = request.get_json(force=True) or {}
    db.update_character(cid, **data)
    return jsonify(db.get_character(cid))


@bp.route("/api/characters/<cid>", methods=["DELETE"])
def delete_character(cid):
    db.delete_character(cid)
    return jsonify({"ok": True})


# ─── 场景 ─────────────────────────────────────────────────────────────────

@bp.route("/api/projects/<pid>/scenes", methods=["GET"])
def list_scenes(pid):
    return jsonify(db.list_scenes(pid))


@bp.route("/api/projects/<pid>/scenes", methods=["POST"])
def create_scene(pid):
    if request.content_type and "multipart" in request.content_type:
        data = request.form.to_dict()
        image_url = ""
        if "image" in request.files:
            image_url = _save_upload(request.files["image"], "scenes")
    else:
        data = request.get_json(force=True) or {}
        image_url = data.get("image_url", "")

    name = str(data.get("name", "")).strip()
    if not name:
        return jsonify({"error": "场景名不能为空"}), 400

    scene = db.create_scene(
        project_id=pid,
        name=name,
        description=data.get("description", ""),
        prompt_tags=data.get("prompt_tags", ""),
        image_url=image_url,
    )
    return jsonify(scene), 201


@bp.route("/api/scenes/<sid>", methods=["PATCH"])
def update_scene(sid):
    if request.content_type and "multipart" in request.content_type:
        data = request.form.to_dict()
        if "image" in request.files:
            data["image_url"] = _save_upload(request.files["image"], "scenes")
    else:
        data = request.get_json(force=True) or {}
    db.update_scene(sid, **data)
    return jsonify(db.get_scene(sid))


@bp.route("/api/scenes/<sid>", methods=["DELETE"])
def delete_scene(sid):
    conn = db.get_db()
    conn.execute("DELETE FROM scenes WHERE id=?", (sid,))
    conn.commit(); conn.close()
    return jsonify({"ok": True})
