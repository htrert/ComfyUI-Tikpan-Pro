"""集管理 API"""
from flask import Blueprint, jsonify, request
import database as db
import tikpan_client as tc

bp = Blueprint("episodes", __name__, url_prefix="/api/episodes")


@bp.route("/by-project/<pid>", methods=["GET"])
def list_episodes(pid):
    episodes = db.list_episodes(pid)
    conn = db.get_db()
    for ep in episodes:
        ep["storyboard_count"] = conn.execute(
            "SELECT COUNT(*) FROM storyboards WHERE episode_id=?", (ep["id"],)
        ).fetchone()[0]
        ep["rendered_count"] = conn.execute(
            "SELECT COUNT(*) FROM storyboards WHERE episode_id=? AND image_url!=''",
            (ep["id"],)
        ).fetchone()[0]
    conn.close()
    return jsonify(episodes)


@bp.route("/by-project/<pid>", methods=["POST"])
def create_episode(pid):
    data = request.get_json(force=True) or {}
    # 自动计算集数
    conn = db.get_db()
    max_num = conn.execute(
        "SELECT COALESCE(MAX(episode_num),0) FROM episodes WHERE project_id=?", (pid,)
    ).fetchone()[0]
    conn.close()
    ep = db.create_episode(
        project_id=pid,
        title=data.get("title", f"第{max_num+1}集"),
        episode_num=max_num + 1,
        synopsis=data.get("synopsis", ""),
    )
    return jsonify(ep), 201


@bp.route("/<eid>", methods=["GET"])
def get_episode(eid):
    ep = db.get_episode(eid)
    if not ep:
        return jsonify({"error": "集不存在"}), 404
    ep["storyboards"] = db.list_storyboards(eid)
    return jsonify(ep)


@bp.route("/<eid>", methods=["PATCH"])
def update_episode(eid):
    data = request.get_json(force=True) or {}
    db.update_episode(eid, **data)
    return jsonify(db.get_episode(eid))


@bp.route("/<eid>", methods=["DELETE"])
def delete_episode(eid):
    db.delete_episode(eid)
    return jsonify({"ok": True})


@bp.route("/<eid>/generate-script", methods=["POST"])
def generate_script(eid):
    """AI 生成剧本"""
    ep = db.get_episode(eid)
    if not ep:
        return jsonify({"error": "集不存在"}), 404

    data = request.get_json(force=True) or {}
    story_idea = data.get("story_idea", ep.get("synopsis", ""))
    if not story_idea.strip():
        return jsonify({"error": "请先填写本集梗概或提供故事创意"}), 400

    proj = db.get_project(ep["project_id"])
    characters = db.list_characters(ep["project_id"])

    result, err = tc.generate_script(
        story_idea=story_idea,
        genre=proj.get("genre", "comic"),
        episode_count=1,
        world_setting=proj.get("world_setting", ""),
        characters=characters,
        model=data.get("model", "gemini-3.5-flash"),
    )
    if err:
        return jsonify({"error": f"AI 生成失败: {err}"}), 502

    # 保存剧本
    import json
    script_text = json.dumps(result, ensure_ascii=False, indent=2)
    db.update_episode(eid, script=script_text,
                      title=result.get("title", ep["title"]) if result.get("title") else ep["title"])

    # 从剧本自动创建分镜
    created = []
    episodes_data = result.get("episodes", [result])
    if episodes_data:
        ep_data = episodes_data[0]
        storyboards_data = ep_data.get("storyboards", ep_data.get("scenes", []))
        for i, sb in enumerate(storyboards_data, start=1):
            # 解析角色名 → 角色 ID
            char_names = sb.get("character_names", sb.get("characters", []))
            char_ids = []
            for ch in characters:
                if ch["name"] in char_names:
                    char_ids.append(ch["id"])

            new_sb = db.create_storyboard(
                episode_id=eid,
                seq_num=i,
                scene_desc=sb.get("scene_desc", sb.get("description", "")),
                dialogue=sb.get("dialogue", ""),
                shot_type=sb.get("shot_type", "medium"),
                camera_move=sb.get("camera_move", "static"),
                character_ids=char_ids,
                emotion=sb.get("emotion", ""),
            )
            created.append(new_sb)

    return jsonify({
        "script": result,
        "storyboards_created": len(created),
        "storyboards": created,
    })
