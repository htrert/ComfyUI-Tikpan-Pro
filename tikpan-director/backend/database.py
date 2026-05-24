"""
Tikpan AI Director — 数据库层
SQLite + 完整 ORM 操作函数
"""
import os
import sqlite3
import json
import uuid
from datetime import datetime

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(_BASE, "data", "director.db")
UPLOAD_DIR = os.path.join(_BASE, "data", "uploads")
OUTPUT_DIR = os.path.join(_BASE, "data", "outputs")


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    conn = get_db()
    conn.executescript("""
        -- 项目
        CREATE TABLE IF NOT EXISTS projects (
            id      TEXT PRIMARY KEY,
            name    TEXT NOT NULL,
            description TEXT DEFAULT '',
            genre   TEXT DEFAULT 'comic',
            style   TEXT DEFAULT '',
            world_setting TEXT DEFAULT '',
            status  TEXT DEFAULT 'active',
            cover_url TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- 角色
        CREATE TABLE IF NOT EXISTS characters (
            id          TEXT PRIMARY KEY,
            project_id  TEXT NOT NULL,
            name        TEXT NOT NULL,
            description TEXT DEFAULT '',
            personality TEXT DEFAULT '',
            appearance  TEXT DEFAULT '',
            prompt_tags TEXT DEFAULT '',
            image_url   TEXT DEFAULT '',
            sort_order  INTEGER DEFAULT 0,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        -- 场景
        CREATE TABLE IF NOT EXISTS scenes (
            id          TEXT PRIMARY KEY,
            project_id  TEXT NOT NULL,
            name        TEXT NOT NULL,
            description TEXT DEFAULT '',
            prompt_tags TEXT DEFAULT '',
            image_url   TEXT DEFAULT '',
            sort_order  INTEGER DEFAULT 0,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        -- 集
        CREATE TABLE IF NOT EXISTS episodes (
            id          TEXT PRIMARY KEY,
            project_id  TEXT NOT NULL,
            episode_num INTEGER NOT NULL DEFAULT 1,
            title       TEXT NOT NULL DEFAULT '第一集',
            synopsis    TEXT DEFAULT '',
            script      TEXT DEFAULT '',
            status      TEXT DEFAULT 'draft',
            sort_order  INTEGER DEFAULT 0,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        -- 分镜
        CREATE TABLE IF NOT EXISTS storyboards (
            id              TEXT PRIMARY KEY,
            episode_id      TEXT NOT NULL,
            seq_num         INTEGER NOT NULL DEFAULT 1,
            scene_desc      TEXT DEFAULT '',
            dialogue        TEXT DEFAULT '',
            shot_type       TEXT DEFAULT 'medium',
            camera_move     TEXT DEFAULT 'static',
            emotion         TEXT DEFAULT '',
            character_ids   TEXT DEFAULT '[]',
            scene_id        TEXT DEFAULT '',
            image_prompt    TEXT DEFAULT '',
            negative_prompt TEXT DEFAULT '',
            image_url       TEXT DEFAULT '',
            audio_url       TEXT DEFAULT '',
            video_url       TEXT DEFAULT '',
            duration_sec    REAL DEFAULT 3.0,
            status          TEXT DEFAULT 'draft',
            render_status   TEXT DEFAULT 'idle',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (episode_id) REFERENCES episodes(id) ON DELETE CASCADE
        );

        -- 渲染任务队列
        CREATE TABLE IF NOT EXISTS render_tasks (
            id              TEXT PRIMARY KEY,
            storyboard_id   TEXT,
            episode_id      TEXT,
            task_type       TEXT NOT NULL,
            upstream_task_id TEXT DEFAULT '',
            model_id        TEXT DEFAULT '',
            status          TEXT DEFAULT 'pending',
            result_url      TEXT DEFAULT '',
            error_msg       TEXT DEFAULT '',
            payload_json    TEXT DEFAULT '{}',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- 系统配置
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()
    print(f"[DB] 数据库初始化完成: {DB_PATH}", flush=True)


# ─── 通用工具 ──────────────────────────────────────────────────────────────

def new_id():
    return uuid.uuid4().hex[:16]


def row_to_dict(row):
    if row is None:
        return None
    d = dict(row)
    # JSON 字段自动解析
    for key in ("character_ids", "payload_json"):
        if key in d and isinstance(d[key], str):
            try:
                d[key] = json.loads(d[key])
            except Exception:
                pass
    return d


def rows_to_list(rows):
    return [row_to_dict(r) for r in rows]


# ─── 项目 ─────────────────────────────────────────────────────────────────

def create_project(name, description="", genre="comic", style="", world_setting=""):
    pid = new_id()
    conn = get_db()
    conn.execute(
        "INSERT INTO projects (id,name,description,genre,style,world_setting) VALUES (?,?,?,?,?,?)",
        (pid, name, description, genre, style, world_setting)
    )
    conn.commit(); conn.close()
    return get_project(pid)


def get_project(pid):
    conn = get_db()
    r = conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    conn.close()
    return row_to_dict(r)


def list_projects():
    conn = get_db()
    rows = conn.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
    conn.close()
    return rows_to_list(rows)


def update_project(pid, **kwargs):
    allowed = {"name","description","genre","style","world_setting","status","cover_url"}
    fields = {k:v for k,v in kwargs.items() if k in allowed}
    if not fields:
        return
    fields["updated_at"] = datetime.now().isoformat()
    sql = "UPDATE projects SET " + ",".join(f"{k}=?" for k in fields) + " WHERE id=?"
    conn = get_db()
    conn.execute(sql, list(fields.values()) + [pid])
    conn.commit(); conn.close()


def delete_project(pid):
    conn = get_db()
    conn.execute("DELETE FROM projects WHERE id=?", (pid,))
    conn.commit(); conn.close()


# ─── 角色 ─────────────────────────────────────────────────────────────────

def create_character(project_id, name, description="", personality="",
                     appearance="", prompt_tags="", image_url=""):
    cid = new_id()
    conn = get_db()
    conn.execute(
        "INSERT INTO characters (id,project_id,name,description,personality,appearance,prompt_tags,image_url) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (cid, project_id, name, description, personality, appearance, prompt_tags, image_url)
    )
    conn.commit(); conn.close()
    return get_character(cid)


def get_character(cid):
    conn = get_db()
    r = conn.execute("SELECT * FROM characters WHERE id=?", (cid,)).fetchone()
    conn.close()
    return row_to_dict(r)


def list_characters(project_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM characters WHERE project_id=? ORDER BY sort_order,created_at",
        (project_id,)
    ).fetchall()
    conn.close()
    return rows_to_list(rows)


def update_character(cid, **kwargs):
    allowed = {"name","description","personality","appearance","prompt_tags","image_url","sort_order"}
    fields = {k:v for k,v in kwargs.items() if k in allowed}
    if not fields: return
    sql = "UPDATE characters SET " + ",".join(f"{k}=?" for k in fields) + " WHERE id=?"
    conn = get_db()
    conn.execute(sql, list(fields.values()) + [cid])
    conn.commit(); conn.close()


def delete_character(cid):
    conn = get_db()
    conn.execute("DELETE FROM characters WHERE id=?", (cid,))
    conn.commit(); conn.close()


# ─── 场景 ─────────────────────────────────────────────────────────────────

def create_scene(project_id, name, description="", prompt_tags="", image_url=""):
    sid = new_id()
    conn = get_db()
    conn.execute(
        "INSERT INTO scenes (id,project_id,name,description,prompt_tags,image_url) VALUES (?,?,?,?,?,?)",
        (sid, project_id, name, description, prompt_tags, image_url)
    )
    conn.commit(); conn.close()
    return get_scene(sid)


def get_scene(sid):
    conn = get_db()
    r = conn.execute("SELECT * FROM scenes WHERE id=?", (sid,)).fetchone()
    conn.close()
    return row_to_dict(r)


def list_scenes(project_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM scenes WHERE project_id=? ORDER BY sort_order,created_at",
        (project_id,)
    ).fetchall()
    conn.close()
    return rows_to_list(rows)


def update_scene(sid, **kwargs):
    allowed = {"name","description","prompt_tags","image_url","sort_order"}
    fields = {k:v for k,v in kwargs.items() if k in allowed}
    if not fields: return
    sql = "UPDATE scenes SET " + ",".join(f"{k}=?" for k in fields) + " WHERE id=?"
    conn = get_db()
    conn.execute(sql, list(fields.values()) + [sid])
    conn.commit(); conn.close()


# ─── 集 ───────────────────────────────────────────────────────────────────

def create_episode(project_id, title="", episode_num=1, synopsis=""):
    eid = new_id()
    conn = get_db()
    conn.execute(
        "INSERT INTO episodes (id,project_id,title,episode_num,synopsis) VALUES (?,?,?,?,?)",
        (eid, project_id, title or f"第{episode_num}集", episode_num, synopsis)
    )
    conn.commit(); conn.close()
    return get_episode(eid)


def get_episode(eid):
    conn = get_db()
    r = conn.execute("SELECT * FROM episodes WHERE id=?", (eid,)).fetchone()
    conn.close()
    return row_to_dict(r)


def list_episodes(project_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM episodes WHERE project_id=? ORDER BY episode_num,sort_order",
        (project_id,)
    ).fetchall()
    conn.close()
    return rows_to_list(rows)


def update_episode(eid, **kwargs):
    allowed = {"title","synopsis","script","status","episode_num","sort_order"}
    fields = {k:v for k,v in kwargs.items() if k in allowed}
    if not fields: return
    fields["updated_at"] = datetime.now().isoformat()
    sql = "UPDATE episodes SET " + ",".join(f"{k}=?" for k in fields) + " WHERE id=?"
    conn = get_db()
    conn.execute(sql, list(fields.values()) + [eid])
    conn.commit(); conn.close()


def delete_episode(eid):
    conn = get_db()
    conn.execute("DELETE FROM episodes WHERE id=?", (eid,))
    conn.commit(); conn.close()


# ─── 分镜 ─────────────────────────────────────────────────────────────────

def create_storyboard(episode_id, seq_num, scene_desc="", dialogue="",
                      shot_type="medium", camera_move="static",
                      character_ids=None, scene_id="", emotion=""):
    sid = new_id()
    conn = get_db()
    conn.execute(
        "INSERT INTO storyboards "
        "(id,episode_id,seq_num,scene_desc,dialogue,shot_type,camera_move,"
        "character_ids,scene_id,emotion) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (sid, episode_id, seq_num, scene_desc, dialogue, shot_type, camera_move,
         json.dumps(character_ids or []), scene_id, emotion)
    )
    conn.commit(); conn.close()
    return get_storyboard(sid)


def get_storyboard(sid):
    conn = get_db()
    r = conn.execute("SELECT * FROM storyboards WHERE id=?", (sid,)).fetchone()
    conn.close()
    return row_to_dict(r)


def list_storyboards(episode_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM storyboards WHERE episode_id=? ORDER BY seq_num",
        (episode_id,)
    ).fetchall()
    conn.close()
    return rows_to_list(rows)


def update_storyboard(sid, **kwargs):
    allowed = {
        "scene_desc","dialogue","shot_type","camera_move","emotion",
        "character_ids","scene_id","image_prompt","negative_prompt",
        "image_url","audio_url","video_url","duration_sec",
        "status","render_status","seq_num"
    }
    fields = {k:v for k,v in kwargs.items() if k in allowed}
    if not fields: return
    # 序列化 JSON 字段
    if "character_ids" in fields and isinstance(fields["character_ids"], list):
        fields["character_ids"] = json.dumps(fields["character_ids"])
    fields["updated_at"] = datetime.now().isoformat()
    sql = "UPDATE storyboards SET " + ",".join(f"{k}=?" for k in fields) + " WHERE id=?"
    conn = get_db()
    conn.execute(sql, list(fields.values()) + [sid])
    conn.commit(); conn.close()


def delete_storyboard(sid):
    conn = get_db()
    conn.execute("DELETE FROM storyboards WHERE id=?", (sid,))
    conn.commit(); conn.close()


def reorder_storyboards(episode_id, ordered_ids):
    """批量重排序"""
    conn = get_db()
    for i, sid in enumerate(ordered_ids, start=1):
        conn.execute(
            "UPDATE storyboards SET seq_num=? WHERE id=? AND episode_id=?",
            (i, sid, episode_id)
        )
    conn.commit(); conn.close()


# ─── 渲染任务 ─────────────────────────────────────────────────────────────

def create_render_task(task_type, storyboard_id=None, episode_id=None,
                       model_id="", payload=None):
    tid = new_id()
    conn = get_db()
    conn.execute(
        "INSERT INTO render_tasks (id,storyboard_id,episode_id,task_type,model_id,payload_json) "
        "VALUES (?,?,?,?,?,?)",
        (tid, storyboard_id, episode_id, task_type, model_id,
         json.dumps(payload or {}))
    )
    conn.commit(); conn.close()
    return tid


def update_render_task(tid, **kwargs):
    allowed = {"status","upstream_task_id","result_url","error_msg"}
    fields = {k:v for k,v in kwargs.items() if k in allowed}
    if not fields: return
    fields["updated_at"] = datetime.now().isoformat()
    sql = "UPDATE render_tasks SET " + ",".join(f"{k}=?" for k in fields) + " WHERE id=?"
    conn = get_db()
    conn.execute(sql, list(fields.values()) + [tid])
    conn.commit(); conn.close()


def get_render_task(tid):
    conn = get_db()
    r = conn.execute("SELECT * FROM render_tasks WHERE id=?", (tid,)).fetchone()
    conn.close()
    return row_to_dict(r)


def list_pending_tasks():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM render_tasks WHERE status IN ('pending','running') ORDER BY created_at"
    ).fetchall()
    conn.close()
    return rows_to_list(rows)


# ─── 设置 ─────────────────────────────────────────────────────────────────

def get_setting(key, default=""):
    conn = get_db()
    r = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return r["value"] if r else default


def set_setting(key, value):
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)",
        (key, str(value))
    )
    conn.commit(); conn.close()
