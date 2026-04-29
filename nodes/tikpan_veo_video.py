import json
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

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 🔐 依然是咱们的官方地址
HARDCODED_BASE_URL = "https://tikpan.com"

class TikpanVeoVideoNode:
    @classmethod
    def INPUT_TYPES(cls):
        inputs = {
            "required": {
                "获取密钥请访问": (["👉 https://tikpan.com (官方授权Key获取点)"], ),
                "API_密钥": ("STRING", {"default": "sk-"}),
                "Veo专属提示词": ("STRING", {"multiline": True, "default": "请在此直接输入您的视频提示词..."}),
                "模型选择": (["veo_3_1-lite-4K", "veo_3_1-lite", "veo_3_1-fast-4K", "veo_3_1"], {"default": "veo_3_1-lite-4K"}),
                "比例": (["16:9", "9:16", "1:1"], {"default": "16:9"}),
                "seed": ("INT", {"default": 888888, "min": 0, "max": 0xffffffffffffffff}),
            },
            "optional": {}
        }
        
        inputs["optional"]["参考图_首帧"] = ("IMAGE",)
        inputs["optional"]["参考图_尾帧"] = ("IMAGE",)
            
        return inputs

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("📁_本地保存路径", "🏷️_任务ID", "🔗_视频云端直链", "📄_完整日志")
    OUTPUT_NODE = True 
    FUNCTION = "execute"
    CATEGORY = "👑 Tikpan 官方独家节点"

    def execute(self, 获取密钥请访问, API_密钥, Veo专属提示词, 模型选择, 比例, seed, **kwargs):
        comfy.model_management.throw_exception_if_processing_interrupted()
        
        if not API_密钥 or len(API_密钥) < 10:
            return ("❌ 请填写API密钥", "无", "无", "请填写密钥")

        # 🚀 重点1：去掉 Content-Type: application/json！让 requests 自动生成表单头
        headers = {"Authorization": f"Bearer {API_密钥}"}
        session = requests.Session()
        session.trust_env = False

        # 🚀 重点2：不再转 Base64，而是提取纯粹的二进制文件流 (Bytes)
        def get_image_bytes(img_tensor):
            if img_tensor is None: return None
            i_arr = 255. * img_tensor[0].cpu().numpy()
            p_img = Image.fromarray(np.clip(i_arr, 0, 255).astype(np.uint8))
            buf = BytesIO()
            p_img.save(buf, format="JPEG", quality=85) 
            return buf.getvalue()

        first_frame_bytes = get_image_bytes(kwargs.get("参考图_首帧"))
        last_frame_bytes = get_image_bytes(kwargs.get("参考图_尾帧"))

        # 🚀 重点3：把文本参数和文件参数分开打包 (data 放文本，files 放图片)
        form_data = {
            "model": 模型选择, 
            "prompt": Veo专属提示词, 
            "aspect_ratio": 比例,
            "seed": str(seed) # 表单要求全是字符串
        }
        
        form_files = {}
        if first_frame_bytes:
            # 格式：("字段名", ("文件名", 文件二进制流, "MIME类型"))
            form_files["image"] = ("first_frame.jpg", first_frame_bytes, "image/jpeg")
        if last_frame_bytes:
            form_files["image_end"] = ("last_frame.jpg", last_frame_bytes, "image/jpeg")

        try:
            # 🚀 重点4：使用 data= 和 files= 提交，而不是 json=
            res = session.post(
                f"{HARDCODED_BASE_URL}/v1/videos", 
                data=form_data, 
                files=form_files if form_files else None,
                headers=headers, 
                verify=False, 
                timeout=120
            ).json()
            
            task_id = res.get("id") or res.get("task_id")
            direct_url = res.get("url") or (res.get("data") and res["data"][0].get("url"))
            
            if direct_url:
                video_url = direct_url
                task_id = task_id or "sync_task"
            elif not task_id: 
                return ("❌ 任务创建失败", "无", "无", json.dumps(res, ensure_ascii=False))
                
        except Exception as e: return (f"❌ 网络/表单错误: {e}", "无", "无", str(e))

        print(f"\n[Veo 3.1] 🚀 任务(表单模式)创建成功！ID: {task_id}")
        pbar = comfy.utils.ProgressBar(100)
        video_url = direct_url if 'direct_url' in locals() and direct_url else ""
        final_data = res
        
        # 轮询状态
        if not video_url:
            wait_time = 0
            for _ in range(240):
                for _ in range(5):
                    time.sleep(1)
                    comfy.model_management.throw_exception_if_processing_interrupted()
                wait_time += 5

                try:
                    status_res = session.get(f"{HARDCODED_BASE_URL}/v1/videos/{task_id}", headers=headers, verify=False, timeout=30).json()
                    final_data = status_res
                    
                    if wait_time % 15 == 0:
                        print(f"[Veo 3.1] ⏳ 云端渲染中，请耐心等待... (已耗时: {wait_time} 秒)")

                    state = str(status_res.get("status") or status_res.get("state") or "").lower()
                    
                    if state in ["success", "succeeded", "finished", "completed"]:
                        pbar.update_absolute(100, 100)
                        print(f"[Veo 3.1] ✅ 渲染完成！总耗时: {wait_time} 秒")
                        video_url = status_res.get("video_url") or status_res.get("url") or (status_res.get("data") and status_res["data"][0].get("url"))
                        break
                    elif state in ["failed", "error"]:
                        return ("❌ 渲染失败", str(task_id), "无", json.dumps(status_res, ensure_ascii=False))
                except Exception: pass 

        if not video_url:
            return ("⚠️ 轮询超时或未找到链接", str(task_id), "无", "请检查聚合站接口格式")

        comfy.model_management.throw_exception_if_processing_interrupted()
        print(f"[Veo 3.1] 📥 正在极速下载大片到本地...")
        try:
            response = requests.get(video_url, verify=False, timeout=600)
            safe_id = str(task_id).replace(":", "_")
            filename = f"Tikpan_Veo_{safe_id}.mp4"
            out_dir = folder_paths.get_output_directory()
            path = os.path.join(out_dir, filename)
            
            with open(path, "wb") as f: f.write(response.content)
            print(f"[Veo 3.1] 🎉 下载成功！路径: {path}\n")
            return (path, str(task_id), video_url, json.dumps(final_data, ensure_ascii=False, indent=2))
        except Exception as e:
            return (f"❌ 下载失败: {e}", str(task_id), video_url, f"下载错误: {e}")