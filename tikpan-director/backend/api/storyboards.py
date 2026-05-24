"""分镜管理 + AI 提示词优化 API"""
from flask import Blueprint, jsonify, request
import database as db
import tikpan_client as tc

bp = Blueprint("storyboards", __name__)


@bp.route("/api/episodes/<eid>/storyboards", methods=["GET"])
def list_storyboards(eid):
    return jsonify(db.list_storyboards(eid))


@bp.route("/api/episodes/<eid>/storyboards", methods=["POST"])
def create_storyboard(eid):
    data = request.get_json(force=True) or {}
    conn = db.get_db()
    max_seq = conn.execute(
        "SELECT COALESCE(MAX(seq_num),0) FROM storyboards WHERE episode_id=?", (eid,)
    ).fetchone()[0]
    conn.close()

    sb = db.create_storyboard(
        episode_id=eid,
        seq_num=data.get("seq_num", max_seq + 1),
        scene_desc=data.get("scene_desc", ""),
        dialogue=data.get("dialogue", ""),
        shot_type=data.get("shot_type", "medium"),
        camera_move=data.get("camera_move", "static"),
        character_ids=data.get("character_ids", []),
        scene_id=data.get("scene_id", ""),
        emotion=data.get("emotion", ""),
    )
    return jsonify(sb), 201


@bp.route("/api/storyboards/<sid>", methods=["GET"])
def get_storyboard(sid):
    sb = db.get_storyboard(sid)
    if not sb:
        return jsonify({"error": "分镜不存在"}), 404
    return jsonify(sb)


@bp.route("/api/storyboards/<sid>", methods=["PATCH"])
def update_storyboard(sid):
    data = request.get_json(force=True) or {}
    db.update_storyboard(sid, **data)
    return jsonify(db.get_storyboard(sid))


@bp.route("/api/storyboards/<sid>", methods=["DELETE"])
def delete_storyboard(sid):
    db.delete_storyboard(sid)
    return jsonify({"ok": True})


@bp.route("/api/episodes/<eid>/storyboards/reorder", methods=["POST"])
def reorder_storyboards(eid):
    data = request.get_json(force=True) or {}
    ordered_ids = data.get("ids", [])
    db.reorder_storyboards(eid, ordered_ids)
    return jsonify({"ok": True})


@bp.route("/api/storyboards/<sid>/optimize-prompt", methods=["POST"])
def optimize_prompt(sid):
    """AI 优化分镜提示词"""
    sb = db.get_storyboard(sid)
    if not sb:
        return jsonify({"error": "分镜不存在"}), 404

    data = request.get_json(force=True) or {}

    # 拉取角色描述
    char_ids = sb.get("character_ids", [])
    char_descriptions = []
    if char_ids:
        conn = db.get_db()
        for cid in char_ids:
            row = conn.execute("SELECT name,appearance,prompt_tags FROM characters WHERE id=?", (cid,)).fetchone()
            if row:
                desc = f"{row['name']}: {row['appearance']} {row['prompt_tags']}".strip()
                char_descriptions.append(desc)
        conn.close()

    # 拉取场景风格
    scene_style = ""
    if sb.get("scene_id"):
        scene = db.get_scene(sb["scene_id"])
        if scene:
            scene_style = scene.get("prompt_tags", "")

    result, err = tc.optimize_image_prompt(
        scene_desc=sb["scene_desc"],
        character_descriptions=char_descriptions,
        scene_style=scene_style or data.get("style", ""),
        shot_type=sb["shot_type"],
        emotion=sb["emotion"],
    )
    if err:
        return jsonify({"error": f"提示词优化失败: {err}"}), 502

    # 保存优化结果
    db.update_storyboard(sid,
        image_prompt=result.get("positive", ""),
        negative_prompt=result.get("negative", ""),
    )
    return jsonify({
        "positive": result.get("positive", ""),
        "negative": result.get("negative", ""),
    })


@bp.route("/api/episodes/<eid>/storyboards/batch-optimize", methods=["POST"])
def batch_optimize_prompts(eid):
    """批量优化本集所有分镜提示词"""
    sbs = db.list_storyboards(eid)
    ep = db.get_episode(eid)
    proj = db.get_project(ep["project_id"])
    characters = {c["id"]: c for c in db.list_characters(ep["project_id"])}

    results = []
    for sb in sbs:
        if sb.get("image_prompt"):
            results.append({"id": sb["id"], "status": "skipped"})
            continue
        char_descriptions = [
            f"{characters[cid]['name']}: {characters[cid].get('appearance','')} {characters[cid].get('prompt_tags','')}".strip()
            for cid in (sb.get("character_ids") or [])
            if cid in characters
        ]
        style = proj.get("style", "")
        result, err = tc.optimize_image_prompt(
            scene_desc=sb["scene_desc"],
            character_descriptions=char_descriptions,
            scene_style=style,
            shot_type=sb["shot_type"],
            emotion=sb["emotion"],
        )
        if err:
            results.append({"id": sb["id"], "status": "error", "error": err})
        else:
            db.update_storyboard(sb["id"],
                image_prompt=result.get("positive", ""),
                negative_prompt=result.get("negative", ""),
            )
            results.append({"id": sb["id"], "status": "ok",
                            "positive": result.get("positive","")})
    return jsonify({"results": results})
