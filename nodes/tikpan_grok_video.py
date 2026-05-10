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

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HARDCODED_BASE_URL = "https://tikpan.com/v1"

class TikpanExclusiveVideoNode:
    @classmethod
    def INPUT_TYPES(cls):
        inputs = {
            "required": {
                "获取密钥请访问": (["👉 https://tikpan.com (官方授权Key获取点)"], ),
                "Tikpan_API密钥": ("STRING", {"default": "sk-"}),
                # 名字已同步为你画布上的输入名，强制连线防呆
                "Grok3专属提示词": ("STRING", {"multiline": True, "forceInput": True}),
                # 🚀 10s 选项藏在这里！下拉选择它就是 10s 长视频！
                "模型选择": (["grok-video-3", "grok-video-3-10s"], {"default": "grok-video-3"}),
                "比例": (["9:16", "16:9", "1:1", "4:3", "3:4", "21:9", "9:21"], {"default": "9:16"}),
                "分辨率": (["1080P", "720P", "480P"], {"default": "720P"}),
                "seed": ("INT", {"default": 888888, "min": 0, "max": 0xffffffffffffffff}),
            },
            "optional": {}
        }
        
        # 支持 7 张参考图
        for i in range(1, 8):
            inputs["optional"][f"参考图_{i}"] = ("IMAGE",)
            
        return inputs

    # 🚀 4 个标准输出口，绝对不会再报 tuple index out of range 错
    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "VIDEO")
    RETURN_NAMES = ("📁_本地保存路径", "🏷️_任务ID", "🔗_视频云端直链", "📄_完整日志", "🎬_视频输出")
    OUTPUT_NODE = True 
    FUNCTION = "execute"
    CATEGORY = "👑 Tikpan 官方独家节点"

    def execute(self, 获取密钥请访问, Tikpan_API密钥, Grok3专属提示词, 模型选择, 比例, 分辨率, seed, **kwargs):
        comfy.model_management.throw_exception_if_processing_interrupted()
        
        if not Tikpan_API密钥 or len(Tikpan_API密钥) < 10:
            return ("❌ 请填写API密钥", "失败", "无", "请填写密钥", None)

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

        # 2. 组装请求 (保持原厂底层协议绝对不变)
        payload = {
            "model": 模型选择, 
            "prompt": Grok3专属提示词, 
            "aspect_ratio": 比例, 
            "size": 分辨率,
            "seed": seed
        }
        if imgs_b64:
            payload["images"] = [f"data:image/jpeg;base64,{b}" for b in imgs_b64]

        # 3. 发起创建任务
        try:
            res = session.post(f"{HARDCODED_BASE_URL}/video/create", json=payload, headers=headers, verify=False, timeout=60).json()
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
                status_res = session.get(f"{HARDCODED_BASE_URL}/video/query?id={task_id}", headers=headers, verify=False, timeout=30).json()
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
            response = requests.get(video_url, verify=False, timeout=300)
            safe_id = str(task_id).replace(":", "_")
            filename = f"Tikpan_{safe_id}.mp4"
            out_dir = folder_paths.get_output_directory()
            path = os.path.join(out_dir, filename)
            
            with open(path, "wb") as f: f.write(response.content)
            print(f"[Tikpan Grok3] 🎉 下载成功！赶快去 output 文件夹看吧！路径: {path}\n")
            return (path, str(task_id), video_url, json.dumps(final_data, ensure_ascii=False, indent=2), video_from_path(path))
        except Exception as e:
            return (f"❌ 下载失败: {e}", str(task_id), video_url, f"下载错误: {e}", None)
