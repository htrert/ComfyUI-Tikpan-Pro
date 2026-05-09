"""
🏗️ Tikpan Web - 前端构建脚本
生成纯静态 HTML 文件，可直接上传到阿里云 OSS / 任何 CDN

用法：
  python build.py            → 构建到 build/ 目录
  python build.py --deploy   → 构建后自动上传到 OSS（需配置 OSS 环境变量）
"""
import os
import sys
import re
import shutil

# 配置
BUILD_DIR = os.path.join(os.path.dirname(__file__), "build")
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

# 构建时要替换的 API 地址
# 默认指向同域（前后端同服），如需分离请修改
API_BASE = os.environ.get("API_BASE", "")


def build():
    """生成静态前端文件到 build/ 目录"""
    # 清理旧构建
    if os.path.exists(BUILD_DIR):
        shutil.rmtree(BUILD_DIR)
    os.makedirs(BUILD_DIR)

    # 复制静态文件
    if os.path.exists(STATIC_DIR):
        for item in os.listdir(STATIC_DIR):
            src = os.path.join(STATIC_DIR, item)
            dst = os.path.join(BUILD_DIR, item)
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

    # 处理 HTML 模板
    for filename in os.listdir(TEMPLATES_DIR):
        if not filename.endswith(".html"):
            continue
        src_path = os.path.join(TEMPLATES_DIR, filename)
        dst_path = os.path.join(BUILD_DIR, filename)

        with open(src_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 替换 API 地址
        if API_BASE:
            # 把相对路径的 /api 调用替换为绝对路径
            content = content.replace('fetch(\'/api/', f'fetch(\'{API_BASE}/api/')
            content = content.replace('"/api/', f'"{API_BASE}/api/')

        with open(dst_path, "w", encoding="utf-8") as f:
            f.write(content)

        file_size = os.path.getsize(dst_path) / 1024
        print(f"  📄 {filename} ({file_size:.1f} KB)")

    print(f"\n✅ 构建完成！文件在: {BUILD_DIR}")
    print(f"   共 {len(os.listdir(BUILD_DIR))} 个文件")
    print(f"\n📌 部署方式：")
    print(f"   1. 上传 {BUILD_DIR}/ 目录下所有文件到阿里云 OSS")
    print(f"   2. 配置 CDN（DCDN）绑定你的域名")
    print(f"   3. 后端 API 部署到服务器，设置环境变量 API_BASE=你的后端域名")


def deploy_to_oss():
    """自动上传构建文件到 OSS"""
    try:
        import oss2
    except ImportError:
        print("❌ 请先安装 oss2: pip install oss2")
        sys.exit(1)

    key_id = os.environ.get("OSS_KEY_ID", "")
    key_secret = os.environ.get("OSS_KEY_SECRET", "")
    bucket_name = os.environ.get("OSS_BUCKET", "")
    endpoint = os.environ.get("OSS_ENDPOINT", "oss-cn-hongkong.aliyuncs.com")

    if not all([key_id, key_secret, bucket_name]):
        print("❌ 请设置 OSS_KEY_ID, OSS_KEY_SECRET, OSS_BUCKET 环境变量")
        sys.exit(1)

    auth = oss2.Auth(key_id, key_secret)
    bucket = oss2.Bucket(auth, endpoint, bucket_name)

    for root, dirs, files in os.walk(BUILD_DIR):
        for file in files:
            local_path = os.path.join(root, file)
            oss_path = os.path.relpath(local_path, BUILD_DIR).replace("\\", "/")

            # 设置 Content-Type
            if file.endswith(".html"):
                content_type = "text/html; charset=utf-8"
            elif file.endswith(".css"):
                content_type = "text/css; charset=utf-8"
            elif file.endswith(".js"):
                content_type = "application/javascript"
            elif file.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
                content_type = f"image/{file.rsplit('.', 1)[1]}"
            else:
                content_type = "application/octet-stream"

            bucket.put_object_from_file(oss_path, local_path, headers={"Content-Type": content_type})
            print(f"  ☁️  {oss_path}")

    print(f"\n✅ 部署完成！CDN 刷新后即可生效")
    print(f"   📍 Bucket: {bucket_name}")
    print(f"   🌐 如配置了 CDN，记得刷新缓存")


if __name__ == "__main__":
    build()

    if "--deploy" in sys.argv:
        deploy_to_oss()
