"""
🐴 Tikpan：HappyHorse 1.0 R2V 参考生视频节点（商业稳定版）
模型：happyhorse-1.0-r2v
功能：支持最多9张图片参考，精准保持创作意图，实现更强表现力的视频生成

API 端点（中转站 tikpan.com）：
  - 提交任务：POST /alibailian/api/v1/services/aigc/video-generation/video-synthesis
  - 查询任务：GET /alibailian/api/v1/tasks/{task_id}

支持：
- ComfyUI 多图输入（最多9张，自动上传获取 URL）
- 手动输入图片 URL（优先级更高）
- 同步 / 异步双模式
- 完整重试、容错、进度反馈
- 视频自动下载到 ComfyUI 输出目录
"""

import json
import time
import os
import re
import requests
import urllib3
import numpy as np
import traceback
from io import BytesIO
from PIL import Image
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import comfy.utils
import comfy.model_management
import folder_paths
from .tikpan_happyhorse_common import (
    extract_error_message,
    extract_task_output,
    extract_task_status,
    extract_video_url,
    is_failure_status,
    is_success_status,
    normalize_resolution,
    video_from_path,
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://tikpan.com"

# ------------------------------------------------------------------
# 通用工具
# ------------------------------------------------------------------

def safe_filename(text: str, max_len=60) -> str:
    """生成安全文件名，保留常用字符，替换文件系统禁止的符号"""
    text = re.sub(r'[\\/*?:?"<>|]', '_', str(text))
    if len(text) > max_len:
        text = text[:max_len]
    return text.strip('_')


def ensure_unique_path(path: str) -> str:
    """若文件已存在，自动追加编号"""
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    counter = 1
    while os.path.exists(f"{base}_{counter}{ext}"):
        counter += 1
    return f"{base}_{counter}{ext}"


def create_retry_session(retries=5, backoff=0.5, status_forcelist=None):
    """带自动重试的 requests 会话"""
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


def normalize_watermark(watermark):
    """水印参数规范化：确保为布尔值"""
    return True if watermark else False


def friendly_error(status_code, body=""):
    """用户友好的错误提示"""
    messages = {
        401: "密钥无效，请检查 API 密钥或前往 https://tikpan.com 获取",
        402: "账号余额不足，请前往 https://tikpan.com 充值",
        403: "无权访问该资源，请检查密钥权限",
        429: "请求过于频繁，系统已自动等待并重试，请稍候",
    }
    if status_code in messages:
        return messages[status_code]
    return f"服务器返回错误 {status_code}，响应内容：{body[:300]}"


# ------------------------------------------------------------------
# R2V 主节点（商业稳定版）
# ------------------------------------------------------------------

class TikpanHappyHorseR2VNode:
    """
    HappyHorse 1.0 R2V 参考生视频节点
    支持最多9张参考图片，精准保持创作意图
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
                        "default": "一只可爱的柴犬在海边奔跑，海浪轻轻拍打沙滩，画面唯美自然",
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
            "optional": {
                "参考图1": ("IMAGE", {"tooltip": "参考图片1（至少提供1张）"}),
                "参考图2": ("IMAGE", {"tooltip": "参考图片2（可选）"}),
                "参考图3": ("IMAGE", {"tooltip": "参考图片3（可选）"}),
                "参考图4": ("IMAGE", {"tooltip": "参考图片4（可选）"}),
                "参考图5": ("IMAGE", {"tooltip": "参考图片5（可选）"}),
                "参考图6": ("IMAGE", {"tooltip": "参考图片6（可选）"}),
                "参考图7": ("IMAGE", {"tooltip": "参考图片7（可选）"}),
                "参考图8": ("IMAGE", {"tooltip": "参考图片8（可选）"}),
                "参考图9": ("IMAGE", {"tooltip": "参考图片9（可选）"}),
                "图片URL列表": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "tooltip": "多行输入，每行一个图片URL（优先级高于图片输入，多个URL用换行分隔）",
                    },
                ),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "VIDEO")
    RETURN_NAMES = ("📁_本地保存路径", "🆔_任务ID", "🔗_视频云端链接", "📄_完整日志", "🎬_视频输出")
    OUTPUT_NODE = True
    FUNCTION = "generate_video"
    CATEGORY = "👑 Tikpan 官方独家节点"

    # ------------------------------------------------------------------
    # 图片处理
    # ------------------------------------------------------------------

    def tensor_to_pil(self, img_tensor):
        """将 ComfyUI IMAGE 张量转换为 PIL Image"""
        arr = 255.0 * img_tensor[0].cpu().numpy()
        arr = np.clip(arr, 0, 255).astype(np.uint8)
        return Image.fromarray(arr).convert("RGB")

    def upload_single_image(self, session, api_key, img_tensor, index, pbar, total_images, completed):
        """上传单张图片，返回 URL（带进度反馈）"""
        try:
            pil_img = self.tensor_to_pil(img_tensor)
            buf = BytesIO()
            pil_img.save(buf, format="JPEG", quality=95)
            img_bytes = buf.getvalue()
        except Exception as e:
            raise RuntimeError(f"图片{index}转换失败: {e}")

        # 检查大小（常见限制 10MB）
        size_mb = len(img_bytes) / (1024 * 1024)
        if size_mb > 10:
            raise RuntimeError(f"图片{index}过大 ({size_mb:.1f}MB)，请压缩后重试（建议≤10MB）")

        upload_headers = {"Authorization": f"Bearer {api_key}"}
        files = {"file": (f"ref_{index}.jpg", img_bytes, "image/jpeg")}
        upload_endpoints = [
            f"{BASE_URL}/alibailian/api/v1/upload",
            f"{BASE_URL}/v1/upload",
            f"{BASE_URL}/upload",
        ]

        last_error = None
        for upload_url in upload_endpoints:
            try:
                print(f"[HappyHorse-R2V] 🔄 上传参考图{index} 到: {upload_url}", flush=True)
                resp = session.post(
                    upload_url,
                    headers=upload_headers,
                    files=files,
                    timeout=120,
                    verify=False,
                )

                if resp.status_code == 429:
                    print(f"[HappyHorse-R2V] ⚠️ 上传限流(429)，等待后重试...", flush=True)
                    time.sleep(5)
                    continue

                if resp.status_code == 200:
                    res_json = resp.json()
                    url = (
                        res_json.get("url")
                        or (res_json.get("data") or {}).get("url")
                        or res_json.get("filename")
                    )
                    if url:
                        if not url.startswith("http"):
                            url = f"{BASE_URL}/{url.lstrip('/')}"
                        print(f"[HappyHorse-R2V] ✅ 参考图{index}上传成功", flush=True)
                        # 更新进度（上传阶段分配 10% 总进度）
                        if pbar is not None:
                            completed[0] += 1
                            progress = int(10.0 * completed[0] / total_images)
                            pbar.update_absolute(min(progress, 10), 100)
                        return url
                    else:
                        last_error = f"上传成功但未返回URL: {json.dumps(res_json, ensure_ascii=False)[:200]}"
                        continue
                else:
                    last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                    continue

            except Exception as e:
                last_error = f"连接异常: {e}"
                continue

        raise RuntimeError(
            f"❌ 参考图{index}上传失败（尝试了 {len(upload_endpoints)} 个端点）。\n"
            f"最后错误: {last_error}\n"
            f"建议：将图片手动上传到公开图床，然后使用「图片URL列表」输入框填入链接。"
        )

    def get_image_urls(self, session, api_key, img_tensors, manual_urls, pbar):
        """获取所有参考图片的 HTTP URL，优先使用手动 URL"""
        urls = []
        completed = [0]  # 已上传计数（用于进度更新）

        # 1. 解析手动 URL 列表
        if manual_urls:
            lines = [l.strip() for l in manual_urls.strip().split('\n') if l.strip()]
            for i, url in enumerate(lines, 1):
                if url.startswith("http"):
                    urls.append(url)
                    print(f"[HappyHorse-R2V] 🖼️ 手动URL {len(urls)}: {url[:60]}", flush=True)
                else:
                    print(f"[HappyHorse-R2V] ⚠️ 第{i}行URL格式不正确: {url}", flush=True)

            if len(urls) >= 9:
                print("[HappyHorse-R2V] ℹ️ 手动URL已满9张，不再上传节点图片", flush=True)
                pbar.update_absolute(10, 100)
                return urls[:9]

        # 2. 收集需要上传的图片
        to_upload = []
        for i in range(1, 10):
            key = f"参考图{i}"
            if key in img_tensors and img_tensors[key] is not None:
                to_upload.append((i, img_tensors[key]))

        remaining = min(9 - len(urls), len(to_upload))
        print(f"[HappyHorse-R2V] 📤 准备上传 {remaining} 张参考图", flush=True)

        # 3. 上传（带进度）
        for idx, (img_index, img_tensor) in enumerate(to_upload[:remaining], 1):
            try:
                url = self.upload_single_image(
                    session, api_key, img_tensor, img_index,
                    pbar, total_images=remaining, completed=completed
                )
                urls.append(url)
            except Exception as e:
                print(f"[HappyHorse-R2V] ⚠️ 忽略参考图{img_index}: {e}", flush=True)

        if not urls:
            raise ValueError("❌ 至少需要提供1张有效参考图片")

        print(f"[HappyHorse-R2V] 📊 最终使用 {len(urls)} 张参考图片", flush=True)
        pbar.update_absolute(10, 100)
        return urls

    # ------------------------------------------------------------------
    # 任务提交
    # ------------------------------------------------------------------

    def submit_task(self, session, api_key, prompt, image_urls, resolution, duration, watermark, seed):
        """提交异步视频生成任务"""
        url = f"{BASE_URL}/alibailian/api/v1/services/aigc/video-generation/video-synthesis"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        }

        media_list = [{"type": "reference", "url": u} for u in image_urls]

        payload = {
            "model": "happyhorse-1.0-r2v",
            "input": {"prompt": prompt, "media": media_list},
            "parameters": {
                "resolution": resolution,
                "duration": duration,
                "watermark": watermark,
            },
        }

        # seed 为 -1 时不传，让 API 随机生成
        if seed >= 0:
            payload["parameters"]["seed"] = seed

        print(f"[HappyHorse-R2V] 🚀 提交任务（{len(image_urls)}张参考图）...", flush=True)
        try:
            resp = session.post(url, headers=headers, json=payload, timeout=180, verify=False)
            print(f"[HappyHorse-R2V] 📥 响应状态: {resp.status_code}", flush=True)

            if resp.status_code == 429:
                print("[HappyHorse-R2V] ⚠️ 触发限流(429)，建议稍后重试", flush=True)
                return False, friendly_error(429)

            if resp.status_code != 200:
                error_text = resp.text[:1000]
                print(f"[HappyHorse-R2V] ❌ 提交失败: {error_text}", flush=True)
                return False, friendly_error(resp.status_code, error_text)

            res_json = resp.json()
            print(
                f"[HappyHorse-R2V] 📋 响应: {json.dumps(res_json, ensure_ascii=False)[:600]}",
                flush=True,
            )

            # 兼容阿里百炼格式与可能的中转站封装格式
            task_id = (
                res_json.get("output", {}).get("task_id")
                or res_json.get("task_id")
                or res_json.get("request_id")
            )
            if not task_id:
                return False, f"响应中未找到 task_id: {json.dumps(res_json, ensure_ascii=False)[:600]}"

            print(f"[HappyHorse-R2V] ✅ 任务已创建，ID: {task_id}", flush=True)
            return True, task_id

        except requests.exceptions.RequestException as e:
            print(f"[HappyHorse-R2V] ❌ 网络异常: {e}", flush=True)
            return False, f"网络异常: {e}"
        except Exception as e:
            print(f"[HappyHorse-R2V] ❌ 提交异常: {e}", flush=True)
            traceback.print_exc()
            return False, f"提交异常: {e}"

    # ------------------------------------------------------------------
    # 轮询
    # ------------------------------------------------------------------

    def poll_task(self, session, api_key, task_id, max_wait_seconds, poll_interval, pbar):
        """轮询任务状态，直至成功/失败/超时（支持 Retry-After 头）"""
        url = f"{BASE_URL}/alibailian/api/v1/tasks/{task_id}"
        headers = {"Authorization": f"Bearer {api_key}"}

        print(f"[HappyHorse-R2V] 🔄 开始轮询（每 {poll_interval} 秒，最长 {max_wait_seconds}s）...", flush=True)
        start_time = time.time()
        poll_count = 0

        while time.time() - start_time < max_wait_seconds:
            poll_count += 1
            try:
                resp = session.get(url, headers=headers, timeout=30, verify=False)

                if resp.status_code == 429:
                    # 读取 Retry-After 头，按服务端建议等待
                    retry_after = resp.headers.get("Retry-After", str(poll_interval * 2))
                    wait = int(retry_after) if retry_after.isdigit() else poll_interval * 2
                    print(f"[HappyHorse-R2V] ⚠️ 轮询限流(429)，服务端建议等待 {wait}s...", flush=True)
                    time.sleep(wait)
                    continue

                if resp.status_code != 200:
                    print(f"[HappyHorse-R2V] ⚠️ 轮询 HTTP {resp.status_code}: {resp.text[:300]}", flush=True)
                    time.sleep(poll_interval)
                    continue

                res_json = resp.json()
                output = extract_task_output(res_json)
                task_status = extract_task_status(res_json)

                elapsed = int(time.time() - start_time)
                # 动态更新进度条（提交占 20%，轮询占 65%）
                progress = 20 + min(elapsed / max_wait_seconds * 65, 65)
                if pbar is not None:
                    pbar.update_absolute(int(progress), 100)

                if poll_count % 3 == 0 or is_success_status(task_status) or is_failure_status(task_status):
                    print(f"[HappyHorse-R2V] ⏳ 轮询中... {elapsed}s, 状态: {task_status}", flush=True)

                if is_success_status(task_status):
                    video_url = extract_video_url(res_json)
                    if video_url:
                        print(f"[HappyHorse-R2V] ✅ 任务完成！总耗时 {elapsed}s", flush=True)
                        return True, video_url, res_json
                    return False, "任务成功但未返回视频链接", res_json

                if is_failure_status(task_status):
                    err = extract_error_message(output)
                    print(f"[HappyHorse-R2V] ❌ 任务终止: {err}", flush=True)
                    return False, f"任务终止（{task_status}）: {err}", res_json

                time.sleep(poll_interval)

            except requests.exceptions.RequestException as e:
                print(f"[HappyHorse-R2V] ⚠️ 轮询网络异常: {e}", flush=True)
                time.sleep(poll_interval)

        return False, f"轮询超时（{max_wait_seconds}s）", {}

    # ------------------------------------------------------------------
    # 下载
    # ------------------------------------------------------------------

    def download_video(self, session, video_url, task_id, pbar):
        """下载视频到 ComfyUI 输出目录"""
        try:
            print("[HappyHorse-R2V] 📥 正在下载视频...", flush=True)
            resp = session.get(video_url, timeout=600, stream=True, verify=False)
            resp.raise_for_status()

            out_dir = folder_paths.get_output_directory()
            safe_id = safe_filename(str(task_id))[:50]
            filename = f"HappyHorse_R2V_{safe_id}.mp4"
            local_path = ensure_unique_path(os.path.join(out_dir, filename))

            total_size = int(resp.headers.get("content-length", 0))
            downloaded = 0
            with open(local_path, "wb") as f:
                for chunk in resp.iter_content(8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size and pbar is not None:
                            dl_progress = 85 + min(downloaded / total_size * 15, 15)
                            pbar.update_absolute(int(dl_progress), 100)

            if os.path.getsize(local_path) == 0:
                os.remove(local_path)
                return False, "下载的视频文件为空"

            print(f"[HappyHorse-R2V] ✅ 视频已保存: {local_path}", flush=True)
            return True, local_path

        except requests.exceptions.RequestException as e:
            print(f"[HappyHorse-R2V] ❌ 下载网络异常: {e}", flush=True)
            return False, f"下载失败: {e}"
        except Exception as e:
            print(f"[HappyHorse-R2V] ❌ 下载异常: {e}", flush=True)
            traceback.print_exc()
            return False, f"下载异常: {e}"

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

    def generate_video(self, **kwargs):
        try:
            # 解析必要参数
            api_key = str(kwargs.get("api_key") or "").strip()
            prompt = str(kwargs.get("prompt") or "").strip()
            mode = str(kwargs.get("mode") or "同步 (等待生成并下载)")
            resolution = normalize_resolution(str(kwargs.get("resolution") or "1080P"))
            duration = int(kwargs.get("duration") or 5)
            watermark = kwargs.get("watermark") == "有水印"
            seed = int(kwargs.get("seed") or -1)
            max_wait = int(kwargs.get("max_wait_seconds") or 600)
            poll_int = int(kwargs.get("poll_interval") or 10)
            manual_urls = str(kwargs.get("图片URL列表") or "").strip()

            # 收集图片张量
            img_tensors = {}
            for i in range(1, 10):
                key = f"参考图{i}"
                if key in kwargs and kwargs[key] is not None:
                    img_tensors[key] = kwargs[key]

            is_async = mode.startswith("异步")

            # 参数校验
            if not api_key or len(api_key) < 10:
                return ("", "", "", "❌ 请填写有效的 API 密钥", None)
            if not prompt:
                return ("", "", "", "❌ 提示词不能为空", None)
            if not (3 <= duration <= 15):
                return ("", "", "", "❌ 时长需在 3–15 秒之间", None)
            if not img_tensors and not manual_urls:
                return ("", "", "", "❌ 至少需要1张参考图片", None)

            # 规范化水印参数
            watermark_norm = normalize_watermark(watermark)

            print(f"\n{'='*60}", flush=True)
            print("[HappyHorse-R2V] 🐴 HappyHorse 1.0 R2V 参考生视频", flush=True)
            print(f"[HappyHorse-R2V] 📝 {prompt[:100]}", flush=True)
            print(f"[HappyHorse-R2V] 📐 {resolution} | ⏱️ {duration}s | 水印:{'开启' if watermark_norm else '关闭'} | Seed:{seed}", flush=True)
            print(f"[HappyHorse-R2V] 🎛️ 模式: {mode}", flush=True)

            session = create_retry_session()
            pbar = comfy.utils.ProgressBar(100)
            pbar.update_absolute(0, 100)

            # 1. 获取图片 URLs（0% → 10%）
            comfy.model_management.throw_exception_if_processing_interrupted()
            try:
                image_urls = self.get_image_urls(session, api_key, img_tensors, manual_urls, pbar)
            except Exception as e:
                return ("", "", "", f"❌ 获取图片URL失败: {e}", None)

            # 2. 提交任务 (10% → 20%)
            comfy.model_management.throw_exception_if_processing_interrupted()
            success, result = self.submit_task(
                session, api_key, prompt, image_urls,
                resolution, duration, watermark_norm, seed
            )
            if not success:
                return ("", "", "", f"❌ 提交失败: {result}", None)

            task_id = result
            pbar.update_absolute(20, 100)

            if is_async:
                log = (
                    f"✅ 异步任务已提交\n"
                    f"🆔 任务 ID: {task_id}\n"
                    f"📁 本地文件尚未生成，请使用「🔍 Tikpan：异步任务查询与下载」获取结果\n"
                    f"🖼️ 参考图: {len(image_urls)}张\n"
                    f"📐 分辨率: {resolution}\n"
                    f"⏱️ 时长: {duration}s\n"
                )
                pbar.update_absolute(100, 100)
                return ("", task_id, "", log, None)

            # 3. 轮询 (20% → 85%)
            comfy.model_management.throw_exception_if_processing_interrupted()
            poll_ok, poll_res, poll_data = self.poll_task(
                session, api_key, task_id, max_wait, poll_int, pbar
            )
            if not poll_ok:
                return (
                    "",
                    task_id,
                    "",
                    f"❌ 任务执行失败: {poll_res}\n{json.dumps(poll_data, ensure_ascii=False)[:1000]}",
                    None,
                )

            video_url = poll_res
            pbar.update_absolute(85, 100)

            # 4. 下载 (85% → 100%)
            comfy.model_management.throw_exception_if_processing_interrupted()
            dl_ok, dl_res = self.download_video(session, video_url, task_id, pbar)
            pbar.update_absolute(100, 100)

            usage = poll_data.get("usage", {})
            log_msg = (
                f"✅ 视频生成成功\n"
                f"🆔 任务 ID: {task_id}\n"
                f"{'📁 本地: ' + dl_res if dl_ok else '⚠️ 下载失败: ' + dl_res}\n"
                f"🔗 {video_url}\n"
                f"🖼️ 参考图: {len(image_urls)}张\n"
                f"📐 {resolution} | ⏱️ {duration}s | 🏷️ {'有水印' if watermark_norm else '无水印'}\n"
                f"📊 实际: {usage.get('output_video_duration','-')}s {usage.get('SR','-')}P\n"
                f"\n📄 完整响应:\n{json.dumps(poll_data, ensure_ascii=False, indent=2)[:2000]}"
            )
            video_output = video_from_path(dl_res) if dl_ok else None
            return (dl_res if dl_ok else "", task_id, video_url, log_msg, video_output)

        except Exception as e:
            tb = traceback.format_exc()
            print(f"[HappyHorse-R2V] ❌ 严重错误: {e}\n{tb}", flush=True)
            return ("", "", "", f"❌ 严重错误: {e}\n{tb[:2000]}", None)


# ------------------------------------------------------------------
# 节点注册
# ------------------------------------------------------------------
NODE_CLASS_MAPPINGS = {
    "TikpanHappyHorseR2VNode": TikpanHappyHorseR2VNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TikpanHappyHorseR2VNode": "🐴 Tikpan：HappyHorse 1.0 R2V 参考生视频",
}
