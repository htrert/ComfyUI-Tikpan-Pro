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
OSS_CDN_DOMAIN = os.environ.get("OSS_CDN_DOMAIN", "")  # 例如 https://cdn.tikpan.com

if USE_OSS:
    try:
        import oss2
        auth = oss2.Auth(OSS_KEY_ID, OSS_KEY_SECRET)
        oss_bucket = oss2.Bucket(auth, OSS_ENDPOINT, OSS_BUCKET)
        print(f"☁️  OSS 存储已启用: {OSS_BUCKET}")
    except Exception as e:
        print(f"⚠️  OSS 初始化失败，回退到本地存储: {e}")
        USE_OSS = False


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

    if USE_OSS:
        # 上传到 OSS
        content_type = "image/png" if fmt.upper() == "PNG" else "image/jpeg"
        oss_bucket.put_object(filename, buf, headers={"Content-Type": content_type})
        # 返回 CDN URL 或 OSS URL
        if OSS_CDN_DOMAIN:
            filepath = f"{OSS_CDN_DOMAIN}/{filename}"
        else:
            filepath = f"https://{OSS_BUCKET}.{OSS_ENDPOINT}/{filename}"
        print(f"☁️  图片已上传 OSS: {filepath}", flush=True)
        return filepath, filename
    else:
        # 保存到本地
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        filepath = os.path.join(OUTPUT_DIR, filename)
        with open(filepath, "wb") as f:
            f.write(buf.getvalue())
        print(f"💾 图片已保存本地: {filepath}", flush=True)
        return filepath, filename


def delete_image(filename):
    """删除图片"""
    if USE_OSS:
        try:
            oss_bucket.delete_object(filename)
        except Exception:
            pass
    else:
        filepath = os.path.join(OUTPUT_DIR, filename)
        if os.path.exists(filepath):
            os.remove(filepath)


def get_image_url(filename):
    """获取图片访问 URL（仅 OSS 模式）"""
    if USE_OSS:
        if OSS_CDN_DOMAIN:
            return f"{OSS_CDN_DOMAIN}/{filename}"
        return f"https://{OSS_BUCKET}.{OSS_ENDPOINT}/{filename}"
    return None


def is_oss_enabled():
    return USE_OSS
