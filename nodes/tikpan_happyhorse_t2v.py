"""
🐴 Tikpan：HappyHorse 1.0 T2V 文生视频节点（稳定版）
模型：happyhorse-1.0-t2v
功能：精准理解文本语义，输出流畅自然、细节丰富的高质量视频

API 端点（中转站 tikpan.com）：
  - 提交任务：POST /alibailian/api/v1/services/aigc/video-generation/video-synthesis
  - 查询任务：GET /alibailian/api/v1/tasks/{task_id}

支持：
- 同步模式（等待生成并下载）和异步模式（仅提交任务）
- 自动重试机制（Session + Retry）
- 实时进度条更新
- 文件安全（避免覆盖、校验非空）
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

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://tikpan.com"


# ------------------------------------------------------------------
# 工具函数
# ------------------------------------------------------------------

def safe_filename(text: str, max_len=60) -> str:
    """生成安全的文件名，保留中文字符，仅替换文件系统禁止的字符"""
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


# ------------------------------------------------------------------
# 主节点：支持同步 / 异步模式
# ------------------------------------------------------------------

class TikpanHappyHorseT2VNode:
    """
    HappyHorse 1.0 T2V 文生视频节点（稳定版）
    支持同步等待下载，也支持仅提交任务以配合查询节点使用。
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "💰_福利_💰": (["🔥 0.6元RMB兑1虚拟美元余额 | 全网底价 👉 https://tikpan.com"],),
                "获取密钥请访问": (["👉 https://tikpan.com (官方授权Key获取点)"],),
                "api_key": ("STRING", {"default": os.environ.get("TIKPAN_API_KEY", "sk-")}),
                "prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "一座由硬纸板和瓶盖搭建的微型城市，在夜晚焕发出生机。一列硬纸板火车缓缓驶过，小灯点缀其间，照亮前路。",
                    },
                ),
                "mode": (
                    ["同步 (等待生成并下载)", "异步 (仅提交任务)"],
                    {"default": "同步 (等待生成并下载)"},
                ),
                "resolution": (
                    ["720P", "1080P"],
                    {"default": "1080P"},
                ),
                "ratio": (
                    ["16:9", "9:16", "1:1", "4:3", "3:4"],
                    {"default": "16:9"},
                ),
                "duration": (
                    "INT",
                    {"default": 5, "min": 3, "max": 15, "step": 1},
                ),
                "watermark": (
                    ["无水印", "有水印"],
                    {"default": "无水印"},
                ),
                "seed": (
                    "INT",
                    {"default": -1, "min": -1, "max": 2147483647},
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

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("📁_本地保存路径", "🆔_任务ID", "🔗_视频云端链接", "📄_完整日志")
    OUTPUT_NODE = True
    FUNCTION = "generate_video"
    CATEGORY = "👑 Tikpan 官方独家节点"

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def submit_task(self, session, api_key, prompt, resolution, ratio, duration, watermark, seed):
        """
        提交异步视频生成任务
        返回 (success: bool, task_id_or_error: str)
        """
        url = f"{BASE_URL}/alibailian/api/v1/services/aigc/video-generation/video-synthesis"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        }

        payload = {
            "model": "happyhorse-1.0-t2v",
            "input": {
                "prompt": prompt,
            },
            "parameters": {
                "resolution": resolution,
                "ratio": ratio,
                "duration": duration,
                "watermark": watermark,
            },
        }

        # seed 为 -1 时不传，让 API 随机生成
        if seed >= 0:
            payload["parameters"]["seed"] = seed

        print(f"[HappyHorse-T2V] 🚀 提交任务...", flush=True)
        try:
            resp = session.post(url, headers=headers, json=payload, timeout=180, verify=False)
            print(f"[HappyHorse-T2V] 📥 响应状态: {resp.status_code}", flush=True)

            if resp.status_code == 429:
                print(f"[HappyHorse-T2V] ⚠️ 触发限流(429)，建议稍后重试", flush=True)
                return False, friendly_error(429)

            if resp.status_code != 200:
                error_text = resp.text[:1000]
                print(f"[HappyHorse-T2V] ❌ 提交失败: {error_text}", flush=True)
                return False, friendly_error(resp.status_code, error_text)

            res_json = resp.json()
            print(
                f"[HappyHorse-T2V] 📋 响应: {json.dumps(res_json, ensure_ascii=False)[:600]}",
                flush=True,
            )

            # 兼容阿里百炼格式与可能的中转站封装格式
            task_id = (
                res_json.get("output", {}).get("task_id")
                or res_json.get("task_id")
                or res_json.get("request_id")
            )

            if not task_id:
                return (
                    False,
                    f"响应中未找到 task_id: {json.dumps(res_json, ensure_ascii=False)[:600]}",
                )

            print(f"[HappyHorse-T2V] ✅ 任务已创建，ID: {task_id}", flush=True)
            return True, task_id

        except requests.exceptions.RequestException as e:
            print(f"[HappyHorse-T2V] ❌ 网络异常: {e}", flush=True)
            return False, f"网络异常: {e}"
        except Exception as e:
            print(f"[HappyHorse-T2V] ❌ 提交异常: {e}", flush=True)
            traceback.print_exc()
            return False, f"提交异常: {e}"

    def poll_task(self, session, api_key, task_id, max_wait_seconds, poll_interval, pbar):
        """
        轮询任务状态，直至成功/失败/超时
        返回 (success: bool, video_url_or_error: str, raw_response: dict)
        """
        url = f"{BASE_URL}/alibailian/api/v1/tasks/{task_id}"
        headers = {"Authorization": f"Bearer {api_key}"}

        print(f"[HappyHorse-T2V] 🔄 开始轮询（每 {poll_interval} 秒，最长 {max_wait_seconds}s）...", flush=True)
        start_time = time.time()
        poll_count = 0

        while time.time() - start_time < max_wait_seconds:
            poll_count += 1
            try:
                resp = session.get(url, headers=headers, timeout=30, verify=False)

                if resp.status_code == 429:
                    print(f"[HappyHorse-T2V] ⚠️ 轮询限流(429)，等待更长时间...", flush=True)
                    time.sleep(poll_interval * 2)
                    continue

                if resp.status_code != 200:
                    print(f"[HappyHorse-T2V] ⚠️ 轮询 HTTP {resp.status_code}: {resp.text[:300]}", flush=True)
                    time.sleep(poll_interval)
                    continue

                res_json = resp.json()
                output = res_json.get("output", res_json)
                task_status = (
                    output.get("task_status") or output.get("status") or ""
                ).upper()

                elapsed = int(time.time() - start_time)
                # 动态更新进度条（提交占 15%，轮询占 70%）
                progress = 15 + min(elapsed / max_wait_seconds * 70, 70)
                if pbar is not None:
                    pbar.update_absolute(int(progress), 100)

                # 每 3 次打印一次，以及最终状态时必打印
                if poll_count % 3 == 0 or task_status in (
                    "SUCCEEDED", "FAILED", "CANCELED", "UNKNOWN",
                ):
                    print(
                        f"[HappyHorse-T2V] ⏳ 轮询中... 已等待 {elapsed}s，状态: {task_status}",
                        flush=True,
                    )

                if task_status == "SUCCEEDED":
                    video_url = (
                        output.get("video_url")
                        or (output.get("output") or {}).get("video_url")
                    )
                    if video_url:
                        print(f"[HappyHorse-T2V] ✅ 任务完成！总耗时 {elapsed}s", flush=True)
                        return True, video_url, res_json
                    return False, "任务成功但响应中未找到 video_url", res_json

                if task_status in ("FAILED", "CANCELED", "ERROR", "UNKNOWN"):
                    err = output.get("message") or output.get("error") or "未知错误"
                    print(f"[HappyHorse-T2V] ❌ 任务终止: {err}", flush=True)
                    return False, f"任务终止（{task_status}）: {err}", res_json

                time.sleep(poll_interval)

            except requests.exceptions.RequestException as e:
                print(f"[HappyHorse-T2V] ⚠️ 轮询网络异常: {e}", flush=True)
                time.sleep(poll_interval)

        return False, f"轮询超时（{max_wait_seconds}s）", {}

    def download_video(self, session, video_url, task_id, pbar):
        """
        下载视频到 ComfyUI 输出目录
        返回 (success: bool, local_path_or_error: str)
        """
        try:
            print(f"[HappyHorse-T2V] 📥 正在下载视频...", flush=True)
            resp = session.get(video_url, timeout=600, stream=True, verify=False)
            resp.raise_for_status()

            out_dir = folder_paths.get_output_directory()
            safe_id = safe_filename(str(task_id))[:50]
            filename = f"HappyHorse_T2V_{safe_id}.mp4"
            local_path = os.path.join(out_dir, filename)
            local_path = ensure_unique_path(local_path)

            total_size = int(resp.headers.get("content-length", 0))
            downloaded = 0
            with open(local_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0 and pbar is not None:
                            dl_progress = 85 + min(downloaded / total_size * 15, 15)
                            pbar.update_absolute(int(dl_progress), 100)

            # 校验文件非空
            if os.path.getsize(local_path) == 0:
                os.remove(local_path)
                return False, "下载的视频文件为空"

            print(f"[HappyHorse-T2V] ✅ 视频已保存: {local_path}", flush=True)
            return True, local_path

        except requests.exceptions.RequestException as e:
            print(f"[HappyHorse-T2V] ❌ 下载网络异常: {e}", flush=True)
            return False, f"下载失败: {e}"
        except Exception as e:
            print(f"[HappyHorse-T2V] ❌ 下载异常: {e}", flush=True)
            traceback.print_exc()
            return False, f"下载异常: {e}"

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

    def generate_video(self, **kwargs):
        try:
            # 解析参数
            api_key = str(kwargs.get("api_key") or "").strip()
            prompt = str(kwargs.get("prompt") or "").strip()
            mode = str(kwargs.get("mode") or "同步 (等待生成并下载)")
            resolution = str(kwargs.get("resolution") or "1080P")
            ratio = str(kwargs.get("ratio") or "16:9")
            duration = int(kwargs.get("duration") or 5)
            watermark = kwargs.get("watermark") == "有水印"
            seed = int(kwargs.get("seed") or -1)
            max_wait_seconds = int(kwargs.get("max_wait_seconds") or 600)
            poll_interval = int(kwargs.get("poll_interval") or 10)

            is_async = mode.startswith("异步")

            # 参数校验
            if not api_key or len(api_key) < 10:
                return ("", "", "", "❌ 错误：请填写有效的 API 密钥")
            if not prompt:
                return ("", "", "", "❌ 错误：提示词不能为空")
            if not (3 <= duration <= 15):
                return ("", "", "", "❌ 错误：时长必须在 3–15 秒之间")

            print(f"\n{'='*60}", flush=True)
            print(f"[HappyHorse-T2V] 🐴 HappyHorse 1.0 T2V 文生视频", flush=True)
            print(f"[HappyHorse-T2V] 📝 Prompt: {prompt[:100]}", flush=True)
            print(f"[HappyHorse-T2V] 📐 分辨率: {resolution} | 比例: {ratio}", flush=True)
            print(f"[HappyHorse-T2V] ⏱️ 时长: {duration}s | 水印: {'开启' if watermark else '关闭'} | Seed: {seed}", flush=True)
            print(f"[HappyHorse-T2V] 🎛️ 模式: {mode}", flush=True)
            print(f"{'='*60}\n", flush=True)

            # 创建带重试的 session
            session = create_retry_session()

            pbar = comfy.utils.ProgressBar(100)
            pbar.update_absolute(0, 100)

            # 步骤 1 — 提交任务
            comfy.model_management.throw_exception_if_processing_interrupted()
            success, result = self.submit_task(
                session, api_key, prompt, resolution, ratio,
                duration, watermark, seed,
            )
            if not success:
                return ("", "", "", f"❌ 任务提交失败: {result}")

            task_id = result
            pbar.update_absolute(15, 100)
            print(f"[HappyHorse-T2V] 🆔 Task ID: {task_id}", flush=True)

            # 如果是异步模式，直接返回任务ID
            if is_async:
                log_msg = (
                    f"✅ 任务已提交（异步模式）\n"
                    f"🆔 任务 ID: {task_id}\n"
                    f"📁 本地文件尚未生成，请使用「🔍 Tikpan：异步任务查询与下载」获取结果\n"
                    f"📐 分辨率: {resolution} | 比例: {ratio}\n"
                    f"⏱️ 时长: {duration}s\n"
                )
                pbar.update_absolute(100, 100)
                return ("", task_id, "", log_msg)

            # 步骤 2 — 轮询状态（同步模式）
            comfy.model_management.throw_exception_if_processing_interrupted()
            poll_ok, poll_result, poll_data = self.poll_task(
                session, api_key, task_id, max_wait_seconds, poll_interval, pbar,
            )

            if not poll_ok:
                return (
                    "",
                    task_id,
                    "",
                    f"❌ 任务执行失败: {poll_result}\n"
                    f"{json.dumps(poll_data, ensure_ascii=False)[:1000]}",
                )

            video_url = poll_result
            pbar.update_absolute(85, 100)

            # 步骤 3 — 下载视频
            comfy.model_management.throw_exception_if_processing_interrupted()
            dl_ok, dl_result = self.download_video(session, video_url, task_id, pbar)

            pbar.update_absolute(100, 100)

            # 构建日志
            usage = poll_data.get("usage", {})
            log_msg = (
                f"✅ 视频生成成功\n"
                f"🆔 任务 ID: {task_id}\n"
                f"{'📁 本地路径: ' + dl_result if dl_ok else '⚠️ 下载失败: ' + dl_result}\n"
                f"🔗 云端链接: {video_url}\n"
                f"📐 分辨率: {resolution} | 比例: {ratio}\n"
                f"⏱️ 时长: {duration}s\n"
                f"🏷️ 水印: {'开启' if watermark else '关闭'}\n"
                f"🎲 Seed: {seed}\n"
                f"📊 实际输出: {usage.get('output_video_duration', '-')}s "
                f"| {usage.get('SR', '-')}P "
                f"| {usage.get('ratio', '-')}\n"
                f"\n📄 完整响应:\n"
                f"{json.dumps(poll_data, ensure_ascii=False, indent=2)[:2000]}"
            )

            return (dl_result if dl_ok else "", task_id, video_url, log_msg)

        except Exception as e:
            tb = traceback.format_exc()
            print(f"[HappyHorse-T2V] ❌ 严重错误: {e}\n{tb}", flush=True)
            return ("", "", "", f"❌ 严重错误: {e}\n{tb[:2000]}")


# ------------------------------------------------------------------
# 节点注册
# ------------------------------------------------------------------
NODE_CLASS_MAPPINGS = {
    "TikpanHappyHorseT2VNode": TikpanHappyHorseT2VNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TikpanHappyHorseT2VNode": "🐴 Tikpan：HappyHorse 1.0 T2V 文生视频",
}
