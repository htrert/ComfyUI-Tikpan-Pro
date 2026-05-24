"""
渲染 API — 图片 / 配音 / 整集批量渲染
"""
import os
import json
import threading
from flask import Blueprint, jsonify, request
import database as db
import tikpan_client as tc

bp = Blueprint("render", __name__)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data", "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ─── 单帧图片渲染 ──────────────────────────────────────────────────────────

@bp.route("/api/storyboards/<sid>/render-image", methods=["POST"])
def render_image(sid):
    sb = db.get_storyboard(sid)
    if not sb:
        return jsonify({"error": "分镜不存在"}), 404

    data = request.get_json(force=True) or {}

    # 确保有提示词
    positive = sb.get("image_prompt") or data.get("positive_prompt", "")
    negative = sb.get("negative_prompt") or data.get("negative_prompt", "ugly, deformed, blurry, watermark, text")
    if not positive:
        return jsonify({"error": "请先生成/填写分镜提示词"}), 400

    # 收集角色参考图
    char_ids = sb.get("character_ids") or []
    reference_images = []
    if char_ids:
        conn = db.get_db()
        for cid in char_ids:
            row = conn.execute("SELECT image_url FROM characters WHERE id=?", (cid,)).fetchone()
            if row and row["image_url"]:
                # 参考图需要转 base64
                img_path = os.path.join(
                    os.path.dirname(os.path.dirname(__file__)), "..",
                    row["image_url"].lstrip("/")
                )
                if os.path.exists(img_path):
                    import base64
                    with open(img_path, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode()
                    reference_images.append(f"data:image/jpeg;base64,{b64}")
        conn.close()

    model = data.get("model", "gpt-image-2-gen" if reference_images else "gpt-image-2-official")
    resolution = data.get("resolution", "2K")
    aspect_ratio = data.get("aspect_ratio", "9:16")

    # 标记渲染中
    db.update_storyboard(sid, render_status="running")

    # 调用 API
    result_url, err = tc.generate_image(
        positive_prompt=positive,
        negative_prompt=negative,
        reference_images=reference_images if reference_images else None,
        resolution=resolution,
        aspect_ratio=aspect_ratio,
        model=model,
        seed=data.get("seed"),
    )

    if err:
        db.update_storyboard(sid, render_status="error")
        return jsonify({"error": f"图片生成失败: {err}"}), 502

    # 保存图片
    filename = f"sb_{sid}.png"
    if result_url.startswith("data:"):
        tc.save_base64_image(result_url, OUTPUT_DIR, filename)
        local_url = f"/outputs/{filename}"
    else:
        saved = tc.download_and_save(result_url, OUTPUT_DIR, filename)
        local_url = f"/outputs/{filename}" if saved else result_url

    db.update_storyboard(sid, image_url=local_url, render_status="done", status="rendered")
    return jsonify({"image_url": local_url, "storyboard_id": sid})


# ─── 单帧 TTS 配音 ─────────────────────────────────────────────────────────

@bp.route("/api/storyboards/<sid>/render-audio", methods=["POST"])
def render_audio(sid):
    sb = db.get_storyboard(sid)
    if not sb:
        return jsonify({"error": "分镜不存在"}), 404

    text = sb.get("dialogue", "").strip()
    if not text:
        return jsonify({"error": "该分镜没有对话文字，无法生成配音"}), 400

    data = request.get_json(force=True) or {}
    voice = data.get("voice", "BV700_V2_streaming")
    model = data.get("model", "doubao-tts-2.0")
    speed = float(data.get("speed", 1.0))

    result_url, err = tc.generate_tts(
        text=text, voice=voice, model=model, speed=speed
    )
    if err:
        return jsonify({"error": f"配音生成失败: {err}"}), 502

    # 保存音频
    filename = f"audio_{sid}.mp3"
    if result_url.startswith("data:"):
        import base64
        _, encoded = result_url.split(",", 1)
        with open(os.path.join(OUTPUT_DIR, filename), "wb") as f:
            f.write(base64.b64decode(encoded))
        local_url = f"/outputs/{filename}"
    else:
        saved = tc.download_and_save(result_url, OUTPUT_DIR, filename)
        local_url = f"/outputs/{filename}" if saved else result_url

    db.update_storyboard(sid, audio_url=local_url)
    return jsonify({"audio_url": local_url, "storyboard_id": sid})


# ─── 整集批量渲染图片（后台线程）─────────────────────────────────────────

@bp.route("/api/episodes/<eid>/render-all-images", methods=["POST"])
def render_all_images(eid):
    data = request.get_json(force=True) or {}
    sbs = db.list_storyboards(eid)
    pending = [s for s in sbs if not s.get("image_url")]

    if not pending:
        return jsonify({"message": "所有分镜都已渲染", "count": 0})

    task_ids = []
    for sb in pending:
        tid = db.create_render_task(
            task_type="image",
            storyboard_id=sb["id"],
            episode_id=eid,
            model_id=data.get("model", "gpt-image-2-official"),
            payload={"resolution": data.get("resolution", "2K"),
                     "aspect_ratio": data.get("aspect_ratio", "9:16")},
        )
        task_ids.append(tid)
        db.update_storyboard(sb["id"], render_status="queued")

    # 后台线程执行
    thread = threading.Thread(
        target=_execute_render_queue,
        args=(task_ids, data),
        daemon=True
    )
    thread.start()

    return jsonify({
        "message": f"已提交 {len(task_ids)} 个渲染任务",
        "task_ids": task_ids,
        "total": len(pending),
    })


def _execute_render_queue(task_ids, options):
    """后台执行批量渲染"""
    import time
    for tid in task_ids:
        task = db.get_render_task(tid)
        if not task:
            continue
        sid = task["storyboard_id"]
        sb = db.get_storyboard(sid)
        if not sb:
            continue
        db.update_render_task(tid, status="running")
        db.update_storyboard(sid, render_status="running")

        positive = sb.get("image_prompt", sb.get("scene_desc", ""))
        negative = sb.get("negative_prompt", "ugly, deformed, blurry")
        if not positive:
            db.update_render_task(tid, status="error", error_msg="无提示词")
            db.update_storyboard(sid, render_status="error")
            continue

        payload = task.get("payload_json", {})
        result_url, err = tc.generate_image(
            positive_prompt=positive,
            negative_prompt=negative,
            resolution=payload.get("resolution", "2K"),
            aspect_ratio=payload.get("aspect_ratio", "9:16"),
            model=task.get("model_id", "gpt-image-2-official"),
        )
        if err:
            db.update_render_task(tid, status="error", error_msg=err)
            db.update_storyboard(sid, render_status="error")
        else:
            filename = f"sb_{sid}.png"
            if result_url.startswith("data:"):
                tc.save_base64_image(result_url, OUTPUT_DIR, filename)
                local_url = f"/outputs/{filename}"
            else:
                saved = tc.download_and_save(result_url, OUTPUT_DIR, filename)
                local_url = f"/outputs/{filename}" if saved else result_url
            db.update_render_task(tid, status="done", result_url=local_url)
            db.update_storyboard(sid, image_url=local_url,
                                  render_status="done", status="rendered")
        time.sleep(0.5)  # 防止过于频繁调用


# ─── 整集批量配音 ──────────────────────────────────────────────────────────

@bp.route("/api/episodes/<eid>/render-all-audio", methods=["POST"])
def render_all_audio(eid):
    data = request.get_json(force=True) or {}
    sbs = db.list_storyboards(eid)
    pending = [s for s in sbs if s.get("dialogue") and not s.get("audio_url")]

    if not pending:
        return jsonify({"message": "没有需要配音的分镜", "count": 0})

    def _run():
        for sb in pending:
            result_url, err = tc.generate_tts(
                text=sb["dialogue"],
                voice=data.get("voice", "BV700_V2_streaming"),
                model=data.get("model", "doubao-tts-2.0"),
                speed=float(data.get("speed", 1.0)),
            )
            if not err and result_url:
                filename = f"audio_{sb['id']}.mp3"
                if result_url.startswith("data:"):
                    import base64
                    _, encoded = result_url.split(",", 1)
                    with open(os.path.join(OUTPUT_DIR, filename), "wb") as f:
                        f.write(base64.b64decode(encoded))
                    local_url = f"/outputs/{filename}"
                else:
                    saved = tc.download_and_save(result_url, OUTPUT_DIR, filename)
                    local_url = f"/outputs/{filename}" if saved else result_url
                db.update_storyboard(sb["id"], audio_url=local_url)
            import time; time.sleep(0.3)

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"message": f"已提交 {len(pending)} 个配音任务", "total": len(pending)})


# ─── 渲染任务状态查询 ──────────────────────────────────────────────────────

@bp.route("/api/render-tasks/<tid>", methods=["GET"])
def get_render_task(tid):
    task = db.get_render_task(tid)
    if not task:
        return jsonify({"error": "任务不存在"}), 404
    return jsonify(task)


@bp.route("/api/episodes/<eid>/render-progress", methods=["GET"])
def render_progress(eid):
    sbs = db.list_storyboards(eid)
    total = len(sbs)
    rendered = sum(1 for s in sbs if s.get("image_url"))
    audio_done = sum(1 for s in sbs if s.get("audio_url"))
    running = sum(1 for s in sbs if s.get("render_status") == "running")
    queued = sum(1 for s in sbs if s.get("render_status") == "queued")
    errors = sum(1 for s in sbs if s.get("render_status") == "error")
    return jsonify({
        "total": total,
        "rendered": rendered,
        "audio_done": audio_done,
        "running": running,
        "queued": queued,
        "errors": errors,
        "image_pct": int(rendered / total * 100) if total else 0,
        "audio_pct": int(audio_done / total * 100) if total else 0,
    })
