"""
🔍 Tikpan：通用任务查询与下载节点
支持查询任何 Tikpan 异步任务（HappyHorse T2V/I2V、Veo 等）

API 端点（中转站 tikpan.com）：
  - 查询任务：GET /alibailian/api/v1/tasks/{task_id}
"""

import json
import time
import os
import re
import requests
import urllib3
import traceback
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import folder_paths
import comfy.utils
import comfy.model_management
from .tikpan_happyhorse_common import (
    extract_error_message,
    extract_task_output,
    extract_task_status,
    extract_video_url,
    is_failure_status,
    is_success_status,
    video_from_path,
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://tikpan.com"


# ------------------------------------------------------------------
# 工具函数
# ------------------------------------------------------------------

def safe_filename(text: str, max_len=60) -> str:
    """生成安全的文件名，保留中文字符，仅替换危险字符"""
    text = re.sub(r'[\\/*?:?"<>|]', '_', text)
    if len(text) > max_len:
        text = text[:max_len]
    return text.strip('_')


def ensure_unique_path(path: str) -> str:
    """若文件已存在，添加序号避免覆盖"""
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    counter = 1
    while os.path.exists(f"{base}_{counter}{ext}"):
        counter += 1
    return f"{base}_{counter}{ext}"


def create_retry_session(retries=5, backoff=0.5, status_forcelist=None):
    """创建带重试策略的 requests Session"""
    if status_forcelist is None:
        status_forcelist = [500, 502, 503, 504]
    session = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=backoff,
        status_forcelist=status_forcelist,
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def friendly_error(status_code, body=""):
    """将 HTTP 错误码映射为用户友好的提示"""
    messages = {
        401: "密钥无效，请检查 API 密钥或前往 https://tikpan.com 获取",
        402: "账号余额不足，请前往 https://tikpan.com 充值",
        403: "无权访问该资源，请检查密钥权限",
        429: "请求过于频繁(429)，请稍后重试",
    }
    if status_code in messages:
        return messages[status_code]
    return f"服务器返回错误 {status_code}，响应内容：{body[:300]}"


class TikpanTaskFetcherNode:
    """
    通用任务查询节点
    输入 task_id，轮询任务状态，成功后下载视频/图片到本地。
    适用于 HappyHorse T2V/I2V、Veo 等所有异步任务。
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "获取密钥请访问": (["👉 https://tikpan.com (官方授权Key获取点)"],),
                "api_key": ("STRING", {"default": os.environ.get("TIKPAN_API_KEY", "sk-")}),
                "task_id": ("STRING", {"default": ""}),
                "file_prefix": (
                    "STRING",
                    {
                        "default": "Tikpan_Task",
                        "tooltip": "下载文件的前缀名，例如 HappyHorse_T2V、HappyHorse_I2V 等",
                    },
                ),
                "max_wait_seconds": (
                    "INT",
                    {"default": 600, "min": 30, "max": 3600, "step": 10},
                ),
                "poll_interval": (
                    "INT",
                    {"default": 10, "min": 5, "max": 60, "step": 5},
                ),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "VIDEO")
    RETURN_NAMES = ("📁_本地保存路径", "🆔_任务ID", "🔗_云端链接", "📄_完整日志", "🎬_视频输出")
    OUTPUT_NODE = True
    FUNCTION = "fetch_and_download"
    CATEGORY = "👑 Tikpan 官方独家节点"

    def fetch_and_download(
        self, api_key, task_id, file_prefix, max_wait_seconds, poll_interval
    ):
        try:
            api_key = str(api_key or "").strip()
            task_id = str(task_id or "").strip()
            file_prefix = str(file_prefix or "Tikpan_Task").strip()

            if not api_key or len(api_key) < 10:
                return ("", "", "", "❌ 错误：请填写有效的 API 密钥", None)
            if not task_id:
                return ("", "", "", "❌ 错误：任务 ID 不能为空", None)

            session = create_retry_session()
            pbar = comfy.utils.ProgressBar(100)
            pbar.update_absolute(0, 100)
            pbar.update_absolute(0, 100)

            # 轮询
            comfy.model_management.throw_exception_if_processing_interrupted()
            poll_ok, poll_result, poll_data = self._poll(
                session, api_key, task_id, max_wait_seconds, poll_interval, pbar
            )
            if not poll_ok:
                return (
                    "",
                    task_id,
                    "",
                    f"❌ 任务查询失败: {poll_result}\n"
                    f"{json.dumps(poll_data, ensure_ascii=False)[:1000]}",
                    None,
                )

            media_url = poll_result
            pbar.update_absolute(85, 100)

            # 根据 URL 后缀判断文件类型（视频 or 图片）
            is_video = any(
                media_url.lower().endswith(ext)
                for ext in [".mp4", ".mov", ".avi", ".webm"]
            )
            is_image = any(
                media_url.lower().endswith(ext)
                for ext in [".jpg", ".jpeg", ".png", ".webp"]
            )

            # 下载
            comfy.model_management.throw_exception_if_processing_interrupted()
            dl_ok, dl_result = self._download(
                session, media_url, task_id, file_prefix, is_video or not is_image, pbar
            )
            pbar.update_absolute(100, 100)

            # 构建日志
            usage = poll_data.get("usage", {})
            output_section = poll_data.get("output", poll_data)
            log_msg = (
                f"✅ 任务获取成功\n"
                f"🆔 任务 ID: {task_id}\n"
                f"{'📁 本地路径: ' + dl_result if dl_ok else '⚠️ 下载失败: ' + dl_result}\n"
                f"🔗 云端链接: {media_url}\n"
                f"📊 用量信息: {json.dumps(usage, ensure_ascii=False)[:300]}\n"
                f"\n📄 完整响应:\n"
                f"{json.dumps(poll_data, ensure_ascii=False, indent=2)[:2000]}"
            )

            video_output = video_from_path(dl_result) if dl_ok and is_video else None
            return (dl_result if dl_ok else "", task_id, media_url, log_msg, video_output)

        except Exception as e:
            tb = traceback.format_exc()
            print(f"[TikpanFetcher] ❌ 严重错误: {e}\n{tb}", flush=True)
            return ("", "", "", f"❌ 严重错误: {e}\n{tb[:2000]}", None)

    def _poll(self, session, api_key, task_id, max_wait_seconds, poll_interval, pbar):
        """轮询任务状态，返回 (success, media_url_or_error, raw_response)"""
        url = f"{BASE_URL}/alibailian/api/v1/tasks/{task_id}"
        headers = {"Authorization": f"Bearer {api_key}"}

        print(f"[TikpanFetcher] 🔄 开始轮询 task_id={task_id}", flush=True)
        start = time.time()
        poll_count = 0

        while time.time() - start < max_wait_seconds:
            poll_count += 1
            try:
                resp = session.get(url, headers=headers, timeout=30, verify=False)

                if resp.status_code == 429:
                    print(f"[TikpanFetcher] ⚠️ 限流(429)，等待 {poll_interval * 2}s...", flush=True)
                    time.sleep(poll_interval * 2)
                    continue

                if resp.status_code != 200:
                    print(f"[TikpanFetcher] ⚠️ HTTP {resp.status_code}: {resp.text[:300]}", flush=True)
                    time.sleep(poll_interval)
                    continue

                res_json = resp.json()
                output = extract_task_output(res_json)
                task_status = extract_task_status(res_json)

                elapsed = int(time.time() - start)
                progress = 15 + min(elapsed / max_wait_seconds * 70, 70)
                if pbar is not None:
                    pbar.update_absolute(int(progress), 100)

                if poll_count % 3 == 0 or is_success_status(task_status) or is_failure_status(task_status):
                    print(
                        f"[TikpanFetcher] ⏳ 已等待 {elapsed}s，状态: {task_status}",
                        flush=True,
                    )

                if is_success_status(task_status):
                    # 尝试多种可能的字段路径
                    media_url = extract_video_url(res_json) or output.get("image_url")
                    if media_url:
                        print(f"[TikpanFetcher] ✅ 任务完成！耗时 {elapsed}s", flush=True)
                        return True, media_url, res_json
                    return False, "任务成功但响应中未找到 media_url", res_json

                if is_failure_status(task_status):
                    err = extract_error_message(output)
                    print(f"[TikpanFetcher] ❌ 任务终止: {err}", flush=True)
                    return False, f"任务终止（{task_status}）: {err}", res_json

                time.sleep(poll_interval)

            except requests.exceptions.RequestException as e:
                print(f"[TikpanFetcher] ⚠️ 网络异常: {e}", flush=True)
                time.sleep(poll_interval)

        return False, f"轮询超时（{max_wait_seconds}s）", {}

    def _download(self, session, media_url, task_id, file_prefix, is_video, pbar):
        """下载文件到本地，返回 (success, local_path_or_error)"""
        try:
            print(f"[TikpanFetcher] 📥 正在下载...", flush=True)
            resp = session.get(media_url, timeout=600, stream=True, verify=False)
            resp.raise_for_status()

            # 根据 Content-Type 或 URL 后缀判断扩展名
            content_type = resp.headers.get("Content-Type", "")
            if "video" in content_type:
                ext = ".mp4"
            elif "image/jpeg" in content_type:
                ext = ".jpg"
            elif "image/png" in content_type:
                ext = ".png"
            elif "image/webp" in content_type:
                ext = ".webp"
            else:
                # 从 URL 提取扩展名
                import urllib.parse
                path = urllib.parse.urlparse(media_url).path
                ext = os.path.splitext(path)[1] or (".mp4" if is_video else ".jpg")

            out_dir = folder_paths.get_output_directory()
            safe_id = safe_filename(str(task_id))[:50]
            filename = f"{file_prefix}_{safe_id}{ext}"
            local_path = ensure_unique_path(os.path.join(out_dir, filename))

            total = int(resp.headers.get("content-length", 0))
            downloaded = 0
            with open(local_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0 and pbar is not None:
                            dl_progress = 85 + min(downloaded / total * 15, 15)
                            pbar.update_absolute(int(dl_progress), 100)

            if os.path.getsize(local_path) == 0:
                os.remove(local_path)
                return False, "下载的文件为空"

            print(f"[TikpanFetcher] ✅ 已保存: {local_path}", flush=True)
            return True, local_path

        except requests.exceptions.RequestException as e:
            print(f"[TikpanFetcher] ❌ 下载网络异常: {e}", flush=True)
            return False, f"下载失败: {e}"
        except Exception as e:
            print(f"[TikpanFetcher] ❌ 下载异常: {e}", flush=True)
            traceback.print_exc()
            return False, f"下载异常: {e}"


# ------------------------------------------------------------------
# 节点注册
# ------------------------------------------------------------------
NODE_CLASS_MAPPINGS = {
    "TikpanTaskFetcherNode": TikpanTaskFetcherNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TikpanTaskFetcherNode": "🔍 Tikpan：异步任务查询与下载",
}
