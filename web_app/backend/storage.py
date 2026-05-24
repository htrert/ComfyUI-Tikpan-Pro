"""
🖼️ Tikpan Web - 存储抽象层
支持：本地文件系统 / 阿里云 OSS
根据配置自动切换，部署时设置 OSS 相关环境变量即可启用 OSS
"""
import os
import uuid
from io import BytesIO
from PIL import Image

from config import OUTPUT_DIR

# ===== OSS 可选导入 =====
USE_OSS = os.environ.get("OSS_ENABLED", "false").lower() == "true"
OSS_BUCKET = os.environ.get("OSS_BUCKET", "")
OSS_ENDPOINT = os.environ.get("OSS_ENDPOINT", "oss-cn-hongkong.aliyuncs.com")
OSS_KEY_ID = os.environ.get("OSS_KEY_ID", "")
OSS_KEY_SECRET = os.environ.get("OSS_KEY_SECRET", "")
OSS_PREFIX = os.environ.get("OSS_PREFIX", "tikpan-web").strip("/")
OSS_CDN_DOMAIN = os.environ.get("OSS_CDN_DOMAIN", "").rstrip("/")  # 例如 https://cdn.tikpan.com

if USE_OSS:
    try:
        import oss2
        auth = oss2.Auth(OSS_KEY_ID, OSS_KEY_SECRET)
        oss_bucket = oss2.Bucket(auth, OSS_ENDPOINT, OSS_BUCKET)
        print(f"☁️  OSS 存储已启用: {OSS_BUCKET}")
    except Exception as e:
        print(f"⚠️  OSS 初始化失败，回退到本地存储: {e}")
        USE_OSS = False


def _object_name(filename):
    filename = filename.replace("\\", "/").lstrip("/")
    return f"{OSS_PREFIX}/{filename}" if OSS_PREFIX else filename


def _public_url(object_name):
    if OSS_CDN_DOMAIN:
        return f"{OSS_CDN_DOMAIN}/{object_name}"
    return f"https://{OSS_BUCKET}.{OSS_ENDPOINT}/{object_name}"


def save_bytes(data, filename=None, content_type="application/octet-stream"):
    """
    保存任意媒体文件。
    返回 (public_or_local_path, filename)
    - OSS 模式：第一个值是 CDN/OSS URL
    - 本地模式：第一个值是本地绝对路径
    """
    if not filename:
        ext = {
            "image/png": "png",
            "image/jpeg": "jpg",
            "image/webp": "webp",
            "audio/mpeg": "mp3",
            "audio/wav": "wav",
            "video/mp4": "mp4",
        }.get(content_type, "bin")
        filename = f"tikpan_{uuid.uuid4().hex}.{ext}"

    if USE_OSS:
        object_name = _object_name(filename)
        oss_bucket.put_object(object_name, data, headers={"Content-Type": content_type})
        url = _public_url(object_name)
        print(f"☁️  文件已上传 OSS: {url}", flush=True)
        return url, filename

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(data)
    print(f"💾 文件已保存本地: {filepath}", flush=True)
    return filepath, filename


def save_image(img, fmt="PNG"):
    """
    保存生成的图片
    返回 (filepath, filename)
    - OSS 模式: filepath 是 OSS URL
    - 本地模式: filepath 是本地绝对路径
    """
    filename = f"tikpan_{uuid.uuid4().hex}.{fmt.lower()}"
    buf = BytesIO()
    img.save(buf, format=fmt)
    buf.seek(0)

    content_type = "image/png" if fmt.upper() == "PNG" else "image/jpeg"
    return save_bytes(buf.getvalue(), filename=filename, content_type=content_type)


def delete_image(filename):
    """删除图片"""
    if USE_OSS:
        try:
            oss_bucket.delete_object(_object_name(filename))
        except Exception:
            pass
    else:
        filepath = os.path.join(OUTPUT_DIR, filename)
        if os.path.exists(filepath):
            os.remove(filepath)


def get_image_url(filename):
    """获取图片访问 URL（仅 OSS 模式）"""
    if USE_OSS:
        return _public_url(_object_name(filename))
    return None


def save_audio(audio_source, job_id=None):
    """
    保存音频文件。
    audio_source 可以是：
      - HTTP/HTTPS URL（下载后保存）
      - data:audio/...;base64,... 格式的 data URI
      - 原样返回（如果无法下载/解码则直接用）
    返回本地路径或 OSS URL；失败时返回 None
    """
    import base64, requests as _req
    try:
        if str(audio_source).startswith("data:audio"):
            # base64 data URI
            header, encoded = audio_source.split(",", 1)
            mime = header.split(":")[1].split(";")[0]
            ext = {"audio/mpeg": "mp3", "audio/wav": "wav", "audio/flac": "flac"}.get(mime, "mp3")
            audio_bytes = base64.b64decode(encoded)
            filename = f"audio_{job_id or uuid.uuid4().hex}.{ext}"
            url, _ = save_bytes(audio_bytes, filename=filename, content_type=mime)
            return url
        elif str(audio_source).startswith("http"):
            resp = _req.get(audio_source, timeout=120)
            resp.raise_for_status()
            ct = resp.headers.get("Content-Type", "audio/mpeg")
            ext = {"audio/mpeg": "mp3", "audio/wav": "wav", "audio/flac": "flac",
                   "audio/mp4": "m4a"}.get(ct.split(";")[0].strip(), "mp3")
            filename = f"audio_{job_id or uuid.uuid4().hex}.{ext}"
            url, _ = save_bytes(resp.content, filename=filename, content_type=ct)
            return url
    except Exception as e:
        print(f"[storage] save_audio 失败: {e}", flush=True)
    return None


def save_video(video_source, job_id=None):
    """
    保存视频文件（占位接口，后续 v2.0 启用）
    video_source: HTTP URL 或 data URI
    """
    import requests as _req
    try:
        if str(video_source).startswith("http"):
            resp = _req.get(video_source, timeout=600)
            resp.raise_for_status()
            filename = f"video_{job_id or uuid.uuid4().hex}.mp4"
            url, _ = save_bytes(resp.content, filename=filename, content_type="video/mp4")
            return url
    except Exception as e:
        print(f"[storage] save_video 失败: {e}", flush=True)
    return None


def is_oss_enabled():
    return USE_OSS
