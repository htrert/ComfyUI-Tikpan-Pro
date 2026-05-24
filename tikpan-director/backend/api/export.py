"""导出 API — 整集导出为 ZIP / 视频"""
import os
import io
import json
import zipfile
from flask import Blueprint, jsonify, request, send_file
import database as db

bp = Blueprint("export", __name__)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data", "outputs")
BASE_DIR   = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..")


@bp.route("/api/episodes/<eid>/export-zip", methods=["GET"])
def export_zip(eid):
    """导出整集的图片 + 音频 + 剧本 JSON 为 ZIP"""
    ep = db.get_episode(eid)
    if not ep:
        return jsonify({"error": "集不存在"}), 404

    sbs = db.list_storyboards(eid)
    proj = db.get_project(ep["project_id"])

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # 剧本 JSON
        meta = {
            "project": proj["name"],
            "episode": ep["title"],
            "episode_num": ep["episode_num"],
            "storyboards": sbs,
        }
        zf.writestr("storyboard.json", json.dumps(meta, ensure_ascii=False, indent=2))

        # 每帧图片和音频
        for sb in sbs:
            seq = str(sb["seq_num"]).zfill(3)

            img_url = sb.get("image_url", "")
            if img_url and img_url.startswith("/"):
                img_path = os.path.join(BASE_DIR, img_url.lstrip("/"))
                if os.path.exists(img_path):
                    ext = img_path.rsplit(".", 1)[-1].lower()
                    zf.write(img_path, f"images/{seq}_frame.{ext}")

            audio_url = sb.get("audio_url", "")
            if audio_url and audio_url.startswith("/"):
                audio_path = os.path.join(BASE_DIR, audio_url.lstrip("/"))
                if os.path.exists(audio_path):
                    ext = audio_path.rsplit(".", 1)[-1].lower()
                    zf.write(audio_path, f"audio/{seq}_audio.{ext}")

        # README
        readme = f"""# {proj['name']} - {ep['title']}

## 文件说明
- storyboard.json  — 完整分镜数据
- images/          — 分镜插图（按序号排列）
- audio/           — 分镜配音（按序号排列）

## 使用方法
将 images/ 和 audio/ 导入剪映或 PR，按序号对齐即可合成。
"""
        zf.writestr("README.md", readme)

    buf.seek(0)
    safe_name = f"{proj['name']}_{ep['title']}".replace(" ", "_")
    return send_file(
        buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"{safe_name}.zip",
    )


@bp.route("/api/episodes/<eid>/export-info", methods=["GET"])
def export_info(eid):
    """获取导出状态（有多少帧已渲染）"""
    ep = db.get_episode(eid)
    sbs = db.list_storyboards(eid)
    total = len(sbs)
    images = sum(1 for s in sbs if s.get("image_url"))
    audios = sum(1 for s in sbs if s.get("audio_url"))
    return jsonify({
        "total": total,
        "images_ready": images,
        "audios_ready": audios,
        "ready_to_export": images > 0,
        "full_ready": images == total and audios == total,
    })


@bp.route("/api/projects/<pid>/export-full", methods=["GET"])
def export_full_project(pid):
    """导出整个项目所有集"""
    proj = db.get_project(pid)
    episodes = db.list_episodes(pid)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for ep in episodes:
            sbs = db.list_storyboards(ep["id"])
            ep_prefix = f"EP{str(ep['episode_num']).zfill(2)}_{ep['title']}"
            for sb in sbs:
                seq = str(sb["seq_num"]).zfill(3)
                for field, subdir, label in [
                    ("image_url", "images", "frame"),
                    ("audio_url", "audio", "audio"),
                ]:
                    url = sb.get(field, "")
                    if url and url.startswith("/"):
                        fpath = os.path.join(BASE_DIR, url.lstrip("/"))
                        if os.path.exists(fpath):
                            ext = fpath.rsplit(".", 1)[-1]
                            zf.write(fpath, f"{ep_prefix}/{subdir}/{seq}_{label}.{ext}")
    buf.seek(0)
    return send_file(
        buf, mimetype="application/zip", as_attachment=True,
        download_name=f"{proj['name']}_全集.zip"
    )
