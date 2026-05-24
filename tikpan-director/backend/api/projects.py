"""项目管理 API"""
from flask import Blueprint, jsonify, request
import database as db

bp = Blueprint("projects", __name__, url_prefix="/api/projects")


@bp.route("", methods=["GET"])
def list_projects():
    projects = db.list_projects()
    # 每个项目附带集数和分镜统计
    conn = db.get_db()
    for p in projects:
        p["episode_count"] = conn.execute(
            "SELECT COUNT(*) FROM episodes WHERE project_id=?", (p["id"],)
        ).fetchone()[0]
        p["storyboard_count"] = conn.execute(
            "SELECT COUNT(*) FROM storyboards s JOIN episodes e ON s.episode_id=e.id "
            "WHERE e.project_id=?", (p["id"],)
        ).fetchone()[0]
        p["rendered_count"] = conn.execute(
            "SELECT COUNT(*) FROM storyboards s JOIN episodes e ON s.episode_id=e.id "
            "WHERE e.project_id=? AND s.image_url!=''", (p["id"],)
        ).fetchone()[0]
    conn.close()
    return jsonify(projects)


@bp.route("", methods=["POST"])
def create_project():
    data = request.get_json(force=True) or {}
    name = str(data.get("name", "")).strip()
    if not name:
        return jsonify({"error": "项目名称不能为空"}), 400
    proj = db.create_project(
        name=name,
        description=data.get("description", ""),
        genre=data.get("genre", "comic"),
        style=data.get("style", ""),
        world_setting=data.get("world_setting", ""),
    )
    return jsonify(proj), 201


@bp.route("/<pid>", methods=["GET"])
def get_project(pid):
    proj = db.get_project(pid)
    if not proj:
        return jsonify({"error": "项目不存在"}), 404
    proj["characters"] = db.list_characters(pid)
    proj["scenes"] = db.list_scenes(pid)
    proj["episodes"] = db.list_episodes(pid)
    return jsonify(proj)


@bp.route("/<pid>", methods=["PATCH"])
def update_project(pid):
    data = request.get_json(force=True) or {}
    db.update_project(pid, **data)
    return jsonify(db.get_project(pid))


@bp.route("/<pid>", methods=["DELETE"])
def delete_project(pid):
    db.delete_project(pid)
    return jsonify({"ok": True})
