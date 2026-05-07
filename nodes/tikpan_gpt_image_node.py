import json
import requests
import torch
import numpy as np
from io import BytesIO
from PIL import Image
import comfy.utils
import comfy.model_management

# 🔐 依然是咱们的硬核中转站地址
API_BASE_URL = "https://tikpan.com"

class TikpanGptImage2Node:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "获取密钥请访问": (["👉 https://tikpan.com (官方授权Key获取点)"], ),
                "API_密钥": ("STRING", {"default": "sk-"}),
                "提示词": ("STRING", {"multiline": True, "default": "一位穿着赛博朋克装甲的极客，正在操作复杂的全息工作流，4k，大师级画质..."}),
                "模型": (["gpt-image-2-all"], {"default": "gpt-image-2-all"}),
                "尺寸": (["1024x1024", "1792x1024", "1024x1792"], {"default": "1024x1024"}),
                "品质": (["standard", "hd"], {"default": "hd"}),
                "风格": (["vivid", "natural"], {"default": "vivid"}),
                "seed": ("INT", {"default": 888888, "min": 0, "max": 0xffffffffffffffff}),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("🖼️_生成图像", "📄_完整日志")
    FUNCTION = "generate_image"
    CATEGORY = "👑 Tikpan 官方独家节点"

    def generate_image(self, 获取密钥请访问, API_密钥, 提示词, 模型, 尺寸, 品质, 风格, seed):
        # 1. 进度条初始化
        pbar = comfy.utils.ProgressBar(100)
        print(f"[Tikpan-Img] 🚀 正在调用 GPT-Image-2 核心渲染引擎...", flush=True)
        
        if not API_密钥 or len(API_密钥) < 10:
            return (self.empty_image(), "❌ 请填写有效的 API 密钥")

        # 2. 构造 DALL-E 3 格式的 Payload
        headers = {
            "Authorization": f"Bearer {API_密钥}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": 模型,
            "prompt": 提示词,
            "n": 1,
            "size": 尺寸,
            "quality": 品质,
            "style": 风格,
            "user": "tikpan_geek_user"
        }

        # 3. 发送请求
        try:
            pbar.update(20)
            url = f"{API_BASE_URL}/v1/images/generations"
            response = requests.post(url, json=payload, headers=headers, timeout=120)
            
            if response.status_code != 200:
                return (self.empty_image(), f"❌ 请求失败: {response.text}")
            
            res_data = response.json()
            image_url = res_data.get("data", [{}])[0].get("url")
            
            if not image_url:
                return (self.empty_image(), f"⚠️ 未获取到图像地址: {json.dumps(res_data)}")

            # 4. 下载图像并转换为 Tensor
            pbar.update(50)
            print(f"[Tikpan-Img] 📥 图像渲染完成，正在回传本地...", flush=True)
            img_res = requests.get(image_url, timeout=60)
            img = Image.open(BytesIO(img_res.content)).convert("RGB")
            
            # 转换为 ComfyUI 要求的 Tensor 格式 [B, H, W, C]
            image_np = np.array(img).astype(np.float32) / 255.0
            image_tensor = torch.from_numpy(image_np)[None, ...]
            
            pbar.update(100)
            print(f"[Tikpan-Img] 🎉 图像处理成功！尺寸: {尺寸}", flush=True)
            
            return (image_tensor, json.dumps(res_data, indent=2, ensure_ascii=False))

        except Exception as e:
            print(f"[Tikpan-Img] ❌ 发生严重错误: {e}", flush=True)
            return (self.empty_image(), f"❌ 运行错误: {str(e)}")

    def empty_image(self):
        """生成一个黑色占位图防止节点红屏"""
        return torch.zeros((1, 1024, 1024, 3))