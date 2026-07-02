from .tikpan_categories import CATEGORY_VIDEO
import json
import base64
import time
import os
import requests
import urllib3
import folder_paths
import numpy as np
from io import BytesIO
from PIL import Image

import comfy.utils
import comfy.model_management
from .tikpan_happyhorse_common import video_from_path
from .tikpan_node_options import (
    API_HOST_OPTIONS,
    GROK_10_15_ASPECT_OPTIONS,
    GROK_DURATION_OPTIONS,
    GROK_VIDEO_MODEL_OPTIONS,
    GROK_VIDEO_RESOLUTION_OPTIONS,
    normalize_api_host,
    normalize_seed,
    option_int,
    option_value,
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HARDCODED_BASE_URL = "https://tikpan.com/v1"

class TikpanExclusiveVideoNode:
    @classmethod
    def INPUT_TYPES(cls):
        inputs = {
            "required": {
                "获取密钥请访问": (["👉 https://tikpan.com (官方授权Key获取点)"], ),
                "Tikpan_API密钥": ("STRING", {"default": "sk-", "tooltip": "Tikpan 平台的 API 密钥，以 sk- 开头，从 https://tikpan.com 获取"}),
                # 名字已同步为你画布上的输入名，强制连线防呆
                "Grok3专属提示词": ("STRING", {"multiline": True, "forceInput": True, "tooltip": "Grok3 视频提示词；建议接 Grok 提示词优化节点输出"}),
                "模型选择": (GROK_VIDEO_MODEL_OPTIONS + ["旧版 Grok Video 3｜grok-video-3", "旧版 Grok Video 3 10秒｜grok-video-3-10s"], {"default": GROK_VIDEO_MODEL_OPTIONS[0], "tooltip": "Grok 1.0 支持文生、单图和最多 7 张参考图；Grok 1.5 必须且只能 1 张参考图"}),
                "视频时长": (GROK_DURATION_OPTIONS, {"default": "6秒｜6s", "tooltip": "Grok 1.0/1.5 支持 6/8/10/12/15 秒"}),
                "比例": (GROK_10_15_ASPECT_OPTIONS, {"default": "9:16 竖屏｜9:16", "tooltip": "Grok 1.0 支持 16:9 / 9:16 / 1:1；Grok 1.5 仅支持 16:9 / 9:16"}),
                "分辨率": (GROK_VIDEO_RESOLUTION_OPTIONS, {"default": GROK_VIDEO_RESOLUTION_OPTIONS[1], "tooltip": "Grok 1.0/1.5 支持 480p、720p"}),
                "随机种子": ("INT", {"default": 888888, "min": 0, "max": 0xffffffffffffffff, "tooltip": "同种子+同提示词可复现视频；改种子可换不同结果"}),
            },
            "optional": {
                "中转站地址": (API_HOST_OPTIONS, {"default": API_HOST_OPTIONS[0], "tooltip": "Tikpan 中转站地址，一般保持默认即可"}),
                "校验HTTPS证书": ("BOOLEAN", {"default": True, "tooltip": "默认开启；遇到本地证书问题再关闭（不推荐关闭）"}),
            }
        }

        # 支持 7 张参考图
        for i in range(1, 8):
            inputs["optional"][f"参考图_{i}"] = ("IMAGE", {"tooltip": f"参考图 {i}：作为视觉参考，最多 7 张"})

        return inputs

    # 🚀 4 个标准输出口，绝对不会再报 tuple index out of range 错
    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "VIDEO")
    RETURN_NAMES = ("📁_本地保存路径", "🏷️_任务ID", "🔗_视频云端直链", "📄_完整日志", "🎬_视频输出")
    OUTPUT_NODE = True
    FUNCTION = "execute"
    CATEGORY = CATEGORY_VIDEO
    DESCRIPTION = "📝 Grok 直出视频生成：支持 grok-video-1.0 / grok-video-1.5，时长 6/8/10/12/15 秒，480p/720p，最多 7 张参考图。配合 Grok 提示词优化节点效果更佳。"

    def execute(self, 获取密钥请访问, Tikpan_API密钥, Grok3专属提示词, 模型选择, 视频时长="6秒｜6s", 比例="9:16", 分辨率="720p", 随机种子=888888, **kwargs):
        comfy.model_management.throw_exception_if_processing_interrupted()

        if not Tikpan_API密钥 or len(Tikpan_API密钥) < 10:
            return ("❌ 请填写API密钥", "失败", "无", "请填写密钥", None)
        verify_tls = bool(kwargs.get("校验HTTPS证书", True))
        api_base_url = f"{normalize_api_host(kwargs.get('中转站地址', API_HOST_OPTIONS[0]))}/v1"
        seed = normalize_seed(kwargs.get("seed", 随机种子), default=888888, maximum=2147483647)
        model = option_value(模型选择, "grok-video-1.0")
        duration = option_value(视频时长, "6s")
        duration_seconds = option_int(duration, default=6, minimum=6, maximum=15)
        aspect_ratio = option_value(比例, "9:16")
        resolution = option_value(分辨率, "720p")

        headers = {"Authorization": f"Bearer {Tikpan_API密钥}", "Content-Type": "application/json"}
        session = requests.Session()
        session.trust_env = False

        # 1. 处理参考图 (自动压缩防内存爆炸)
        imgs_b64 = []
        for i in range(1, 8):
            img_tensor = kwargs.get(f"参考图_{i}")
            if img_tensor is not None:
                i_arr = 255. * img_tensor[0].cpu().numpy()
                p_img = Image.fromarray(np.clip(i_arr, 0, 255).astype(np.uint8))
                buf = BytesIO()
                p_img.save(buf, format="JPEG", quality=85)
                imgs_b64.append(base64.b64encode(buf.getvalue()).decode("utf-8"))

        if model == "grok-video-1.5" and len(imgs_b64) != 1:
            return ("❌ grok-video-1.5 必须且只能连接 1 张参考图", "无", "无", f"当前参考图数量: {len(imgs_b64)}", None)
        if model == "grok-video-1.5" and aspect_ratio not in {"16:9", "9:16"}:
            return ("❌ grok-video-1.5 仅支持 16:9 或 9:16", "无", "无", f"不支持的画面比例: {aspect_ratio}", None)
        if model == "grok-video-1.0" and len(imgs_b64) > 1 and duration_seconds > 10:
            return ("❌ grok-video-1.0 多参考图模式最长支持 10 秒", "无", "无", f"当前参考图数量: {len(imgs_b64)}，时长: {duration_seconds}s", None)

        # 2. 组装请求
        payload = {
            "model": model,
            "prompt": Grok3专属提示词,
            "duration": duration_seconds if model in {"grok-video-1.0", "grok-video-1.5"} else duration,
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
            "size": resolution,
            "seed": seed
        }
        if imgs_b64:
            images = [f"data:image/jpeg;base64,{b}" for b in imgs_b64]
            if model in {"grok-video-1.0", "grok-video-1.5"}:
                if len(images) == 1:
                    payload["image"] = {"url": images[0]}
                else:
                    payload["reference_images"] = [{"url": image_url} for image_url in images]
            else:
                payload["images"] = images
                payload["input_reference"] = images[0]

        # 3. 发起创建任务
        try:
            res = session.post(f"{api_base_url}/video/create", json=payload, headers=headers, verify=verify_tls, timeout=60).json()
            task_id = res.get("id") or res.get("task_id")
            if not task_id: return ("❌ 任务创建失败", "无", "无", json.dumps(res, ensure_ascii=False), None)
        except Exception as e: return (f"❌ 网络错误: {e}", "无", "无", str(e), None)

        print(f"\n[Tikpan Grok3] 🚀 任务创建成功！ID: {task_id}")
        pbar = comfy.utils.ProgressBar(100)
        video_url = ""
        last_progress = 0
        final_data = {}

        # 4. 轮询状态 (加入防焦虑心跳系统)
        wait_time = 0
        for _ in range(240): # 放宽到最多等 20 分钟
            for _ in range(5):
                time.sleep(1)
                comfy.model_management.throw_exception_if_processing_interrupted()
            wait_time += 5

            try:
                status_res = session.get(f"{api_base_url}/video/query?id={task_id}", headers=headers, verify=verify_tls, timeout=30).json()
                final_data = status_res
                data = status_res.get("data", status_res)

                # 🚀 心跳日志：每 15 秒报一次平安，让你知道它没卡死！
                if wait_time % 15 == 0:
                    print(f"[Tikpan Grok3] ⏳ 云端渲染中，没卡死，请耐心等待... (已耗时: {wait_time} 秒)")

                raw_prog = data.get("progress", 0)
                try:
                    prog_val = int(str(raw_prog).replace('%', ''))
                    if prog_val > last_progress:
                        pbar.update_absolute(prog_val, 100)
                        print(f"[Tikpan Grok3] 📈 进度更新: {prog_val}%")
                        last_progress = prog_val
                except: pass

                state = str(data.get("status") or data.get("state")).lower()
                if state in ["success", "succeeded", "finished", "completed"]:
                    pbar.update_absolute(100, 100)
                    print(f"[Tikpan Grok3] ✅ 渲染完成！总耗时: {wait_time} 秒")
                    video_url = data.get("video_url") or data.get("url")
                    break
                if state in ["failed", "error"]:
                    return ("❌ 渲染失败", str(task_id), "无", json.dumps(status_res, ensure_ascii=False), None)
            except Exception as e:
                print(f"[Tikpan Grok3] ⚠️ 查询状态遇到网络波动 (自动重试中): {e}")

        if not video_url:
            return ("⚠️ 轮询超时", str(task_id), "无", "任务在云端排队太久，请稍后使用ID自行查询", None)

        # 5. 自动下载成品
        comfy.model_management.throw_exception_if_processing_interrupted()
        print(f"[Tikpan Grok3] 📥 正在极速下载大片到本地...")
        try:
            response = requests.get(video_url, verify=verify_tls, timeout=300)
            safe_id = str(task_id).replace(":", "_")
            filename = f"Tikpan_{safe_id}.mp4"
            out_dir = folder_paths.get_output_directory()
            path = os.path.join(out_dir, filename)

            with open(path, "wb") as f: f.write(response.content)
            print(f"[Tikpan Grok3] 🎉 下载成功！赶快去 output 文件夹看吧！路径: {path}\n")
            return (path, str(task_id), video_url, json.dumps(final_data, ensure_ascii=False, indent=2), video_from_path(path))
        except Exception as e:
            return (f"❌ 下载失败: {e}", str(task_id), video_url, f"下载错误: {e}", None)
