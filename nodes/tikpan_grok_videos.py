import json
import time
import os
import base64
import traceback
from io import BytesIO

import requests
import urllib3
import folder_paths
import numpy as np
from PIL import Image

import comfy.utils
import comfy.model_management
from .tikpan_happyhorse_common import video_from_path
from .tikpan_node_options import GROK_ASPECT_OPTIONS, GROK_DURATION_OPTIONS, normalize_seed, option_value, pick

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_BASE_URL = "https://tikpan.com/v1"


class TikpanGrokVideoNode:
    """
    🎬 Tikpan：Grok-Videos 视频生成节点
    模型：grok-videos
    支持：文生视频、图生视频
    时长：6秒、10秒
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "💰_福利_💰": (["🔥 0.6元RMB兑1美元余额 | 全网底价 👉 https://tikpan.com"],),
                "获取密钥请访问": (["👉 https://tikpan.com (官方授权Key获取点)"],),
                "API_密钥": ("STRING", {"default": "sk-"}),
                "生成指令": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "一段极具视觉冲击力的赛博朋克城市夜景，霓虹灯闪烁，飞行汽车穿梭...",
                    },
                ),
                "模型": (["grok-videos"], {"default": "grok-videos"}),
                "视频时长": (GROK_DURATION_OPTIONS, {"default": "6秒｜6s"}),
                "画面比例": (GROK_ASPECT_OPTIONS, {"default": "16:9 横屏｜16:9"}),
                "随机种子": ("INT", {"default": 888888, "min": 0, "max": 0xFFFFFFFFFFFFFFFF}),
            },
            "optional": {
                "参考图1": ("IMAGE",),
                "参考图2": ("IMAGE",),
                "参考图3": ("IMAGE",),
                "参考图4": ("IMAGE",),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "VIDEO")
    RETURN_NAMES = ("📁_本地保存路径", "🎬_视频云端直链", "📄_渲染日志", "🎬_视频输出")
    OUTPUT_NODE = True
    FUNCTION = "generate_video"
    CATEGORY = "👑 Tikpan 官方独家节点"

    def normalize_size(self, aspect_ratio):
        s = str(aspect_ratio or "").strip()
        if s in ["16:9", "9:16", "1024x1024"]:
            return s
        return "16:9"

    def tensor_to_jpeg_data_url(self, img_tensor, quality=85):
        arr = 255.0 * img_tensor[0].cpu().numpy()
        arr = np.clip(arr, 0, 255).astype(np.uint8)
        img = Image.fromarray(arr).convert("RGB")
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
        return f"data:image/jpeg;base64,{b64_str}"

    def generate_video(self, **kwargs):
        print(f"[Tikpan-GrokVideo] 📦 收到参数: {list(kwargs.keys())}", flush=True)

        api_key = str(pick(kwargs, "API_密钥", "api_key", default="") or "").strip()
        prompt = str(pick(kwargs, "生成指令", "prompt", default="") or "").strip()
        model = pick(kwargs, "模型", "model", default="grok-videos") or "grok-videos"
        duration = option_value(pick(kwargs, "视频时长", "duration", default="6秒｜6s"), "6s")
        aspect_ratio = option_value(pick(kwargs, "画面比例", "aspect_ratio", default="16:9 横屏｜16:9"), "16:9")
        size = self.normalize_size(aspect_ratio)
        seed = normalize_seed(pick(kwargs, "随机种子", "seed", default=888888), default=888888)

        pbar = comfy.utils.ProgressBar(100)

        if not api_key or api_key == "sk-":
            return ("❌ 错误：请填写有效的 API 密钥", "无", "API密钥为空", None)

        if not prompt:
            return ("❌ 错误：生成指令不能为空", "无", "提示词为空", None)

        if not duration or str(duration).strip() == "":
            duration = "6s"

        print(f"[Tikpan-GrokVideo] 🚀 启动视频生成引擎 | 模型: {model} | 时长: {duration}", flush=True)
        print(f"[Tikpan-GrokVideo] 📐 画面比例: '{aspect_ratio}' -> size: '{size}' | Seed: {seed}", flush=True)

        images_b64 = []
        for i in range(1, 5):
            img_tensor = pick(kwargs, f"参考图{i}", f"ref_image_{i}", default=None)
            if img_tensor is not None:
                try:
                    images_b64.append(self.tensor_to_jpeg_data_url(img_tensor, quality=85))
                    print(f"[Tikpan-GrokVideo] 🖼️ 加载参考图_{i} 完成", flush=True)
                except Exception as e:
                    print(f"[Tikpan-GrokVideo] ⚠️ 参考图_{i} 处理失败: {e}", flush=True)

        payload = {
            "model": model,
            "prompt": prompt,
            "duration": duration,
            "size": size,
            "seed": seed % 2147483647,
        }

        print(f"[Tikpan-GrokVideo] 📤 发送Payload: {json.dumps(payload, ensure_ascii=False)}", flush=True)

        if images_b64:
            payload["input_reference"] = images_b64[0]
            print(f"[Tikpan-GrokVideo] 🖼️ 图生视频模式已启用（仅使用第1张参考图）", flush=True)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Tikpan-ComfyUI-GrokVideo/1.0",
        }

        session = requests.Session()
        session.trust_env = False

        try:
            pbar.update(10)
            print(f"[Tikpan-GrokVideo] 📡 正在提交视频生成任务...", flush=True)

            response = session.post(
                f"{API_BASE_URL}/videos",
                json=payload,
                headers=headers,
                timeout=(15, 60),
                verify=False,
            )

            if response.status_code != 200:
                error_text = response.text[:500]
                return (f"❌ 任务创建失败: HTTP {response.status_code}", "无", error_text, None)

            try:
                res_json = response.json()
            except Exception:
                return ("❌ 任务创建失败：返回不是合法 JSON", "无", response.text[:500], None)

            task_id = res_json.get("id") or res_json.get("task_id")

            if not task_id:
                return ("❌ 任务创建失败：未获取到任务ID", "无", json.dumps(res_json, ensure_ascii=False), None)

            print(f"[Tikpan-GrokVideo] ✅ 任务创建成功！Task ID: {task_id}", flush=True)
            pbar.update(20)

            print(f"[Tikpan-GrokVideo] ⏳ 开始轮询任务状态...", flush=True)

            for poll_count in range(240):
                time.sleep(5)
                comfy.model_management.throw_exception_if_processing_interrupted()

                try:
                    status_response = session.get(
                        f"{API_BASE_URL}/videos/query?id={task_id}",
                        headers=headers,
                        timeout=(15, 30),
                        verify=False,
                    )

                    if status_response.status_code != 200:
                        print(f"[Tikpan-GrokVideo] ⚠️ 查询状态失败: HTTP {status_response.status_code}", flush=True)
                        continue

                    try:
                        status_json = status_response.json()
                    except Exception:
                        print(f"[Tikpan-GrokVideo] ⚠️ 查询返回非 JSON: {status_response.text[:300]}", flush=True)
                        continue

                    state = str(status_json.get("status", "")).lower()

                    progress = status_json.get("progress", 0)
                    if isinstance(progress, str):
                        progress = progress.replace("%", "").strip()
                    try:
                        prog_val = int(float(progress))
                        pbar.update_absolute(min(max(prog_val, 0), 99), 100)
                    except Exception:
                        pass

                    print(f"[Tikpan-GrokVideo] 🔄 轮询中... (第{poll_count + 1}次) | 状态: {state}", flush=True)

                    if state in ["success", "succeeded", "completed", "finished"]:
                        pbar.update_absolute(100, 100)
                        video_url = status_json.get("video_url") or status_json.get("url")
                        if not video_url:
                            return ("❌ 任务完成但未获取到视频地址", "无", json.dumps(status_json, ensure_ascii=False), None)

                        print(f"[Tikpan-GrokVideo] ✅ 视频生成完成！正在下载...", flush=True)
                        print(f"[Tikpan-GrokVideo] 🔗 视频地址: {video_url}", flush=True)

                        video_response = session.get(video_url, timeout=(15, 300), verify=False)
                        video_response.raise_for_status()

                        safe_id = str(task_id).replace(":", "_").replace("/", "_")
                        filename = f"Tikpan_GrokVideo_{safe_id}.mp4"
                        out_dir = folder_paths.get_output_directory()
                        save_path = os.path.join(out_dir, filename)

                        with open(save_path, "wb") as f:
                            f.write(video_response.content)

                        print(f"[Tikpan-GrokVideo] 💾 视频已保存到: {save_path}", flush=True)

                        log_text = (
                            f"✅ 视频生成成功 | 模型: {model} | 时长: {duration} | "
                            f"尺寸: {size} | Task ID: {task_id}"
                        )
                        return (save_path, video_url, log_text, video_from_path(save_path))

                    elif state in ["failed", "error", "cancelled"]:
                        error_msg = status_json.get("error", "未知错误")
                        return (f"❌ 视频生成失败: {error_msg}", "无", json.dumps(status_json, ensure_ascii=False), None)

                except Exception as e:
                    print(f"[Tikpan-GrokVideo] ⚠️ 轮询异常: {e}", flush=True)
                    continue

            return (f"⚠️ 轮询超时：任务仍在处理中 | Task ID: {task_id}", "无", "超时：请稍后手动查询", None)

        except Exception as e:
            tb = traceback.format_exc()
            print(f"[Tikpan-GrokVideo] ❌ 异常: {e}\n{tb}", flush=True)
            return (f"❌ 运行异常: {str(e)}", "无", tb, None)


NODE_CLASS_MAPPINGS = {
    "TikpanGrokVideoNode": TikpanGrokVideoNode
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TikpanGrokVideoNode": "🎬 Tikpan: Grok-Videos 视频生成"
}
