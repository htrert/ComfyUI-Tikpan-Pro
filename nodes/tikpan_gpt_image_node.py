import json
import requests
import torch
import numpy as np
from io import BytesIO
from PIL import Image
import comfy.utils
import comfy.model_management
from .tikpan_node_options import API_HOST_OPTIONS, normalize_api_host, normalize_seed

# 🔐 依然是咱们的硬核中转站地址
API_BASE_URL = "https://tikpan.com"

class TikpanGptImage2Node:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "获取密钥请访问": (["👉 https://tikpan.com (官方授权Key获取点)"], ),
                "API_密钥": ("STRING", {"default": "sk-", "tooltip": "Tikpan 平台的 API 密钥，以 sk- 开头，从 https://tikpan.com 获取"}),
                "提示词": ("STRING", {"multiline": True, "default": "一位穿着赛博朋克装甲的极客，正在操作复杂的全息工作流，4k，大师级画质...", "tooltip": "描述你想生成的画面，越具体越准确，支持中英文"}),
                "模型": (["gpt-image-2-all"], {"default": "gpt-image-2-all", "tooltip": "本节点使用的生图模型，目前仅 gpt-image-2-all"}),
                "尺寸": (["1:1 方图｜1024x1024", "16:9 横图｜1792x1024", "9:16 竖图｜1024x1792"], {"default": "1:1 方图｜1024x1024", "tooltip": "出图尺寸/比例：方图通用、横图适合风景、竖图适合人物或短视频"}),
                "品质": (["标准｜standard", "高清｜hd"], {"default": "高清｜hd", "tooltip": "standard=快且省钱；hd=细节更好但更慢更贵"}),
                "风格": (["鲜艳创意｜vivid", "自然真实｜natural"], {"default": "鲜艳创意｜vivid", "tooltip": "vivid=色彩浓烈有想象力；natural=偏写实自然"}),
                "随机种子": ("INT", {"default": 888888, "min": 0, "max": 0xffffffffffffffff, "tooltip": "同种子+同提示词可复现画面；改种子可换不同结果"}),
            },
            "optional": {
                "中转站地址": (API_HOST_OPTIONS, {"default": API_HOST_OPTIONS[0], "tooltip": "Tikpan 中转站地址，一般保持默认即可"}),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("🖼️_生成图像", "📄_完整日志")
    FUNCTION = "generate_image"
    CATEGORY = "📷 Tikpan 云端模型/01 云端生图"
    DESCRIPTION = "📝 GPT-Image-2-all 简易生图：单张文生图，支持 1024/1792 尺寸、HD 高清画质、vivid/natural 两种风格。适合快速出图测试。"

    def generate_image(self, 获取密钥请访问, API_密钥, 提示词, 模型, 尺寸, 品质, 风格, 随机种子, **kwargs):
        # 1. 进度条初始化
        pbar = comfy.utils.ProgressBar(100)
        print(f"[Tikpan-Img] 🚀 正在调用 GPT-Image-2 核心渲染引擎...", flush=True)
        session = requests.Session()
        session.trust_env = False
        尺寸 = str(尺寸).split("｜")[-1].strip()
        品质 = str(品质).split("｜")[-1].strip()
        风格 = str(风格).split("｜")[-1].strip()
        seed = normalize_seed(随机种子, default=888888, maximum=2147483647)
        api_host = normalize_api_host(kwargs.get("中转站地址", API_HOST_OPTIONS[0]))

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
            "seed": seed,
            "user": "tikpan_geek_user"
        }

        # 3. 发送请求
        try:
            pbar.update(20)
            url = f"{api_host}/v1/images/generations"
            response = session.post(url, json=payload, headers=headers, timeout=120)

            if response.status_code != 200:
                return (self.empty_image(), f"❌ 请求失败: {response.text}")

            res_data = response.json()
            image_url = res_data.get("data", [{}])[0].get("url")

            if not image_url:
                return (self.empty_image(), f"⚠️ 未获取到图像地址: {json.dumps(res_data)}")

            # 4. 下载图像并转换为 Tensor
            pbar.update(50)
            print(f"[Tikpan-Img] 📥 图像渲染完成，正在回传本地...", flush=True)
            img_res = session.get(image_url, timeout=60)
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
