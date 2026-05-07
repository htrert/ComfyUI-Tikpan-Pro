import json
import requests
import base64
import torch
import re
import numpy as np
from io import BytesIO
from PIL import Image, ImageOps
import comfy.utils

# 🔐 Tikpan 官方聚合路由
API_BASE_URL = "https://tikpan.com"

class TikpanGptImage2EditNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "获取密钥请访问": (["👉 https://tikpan.com (官方授权Key获取点)"], ),
                "API_密钥": ("STRING", {"default": "sk-"}),
                "底图": ("IMAGE",), # 需要修改的原图
                "修改指令": ("STRING", {"multiline": True, "default": "请把图中的人物换成一位穿着西装的男士，背景保持不变..."}),
                "模型": (["gpt-image-2-all"], {"default": "gpt-image-2-all"}),
                "品质": (["standard", "hd"], {"default": "hd"}),
                "代理端口": ("STRING", {"default": "10808"}),
            },
            "optional": {
                "遮罩_Mask": ("MASK",), # 告诉 AI 哪里需要动手术（可选）
                "产品参考图": ("IMAGE",), # 如果要把某个具体产品放进去
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("🖼️_重绘结果图", "📄_渲染日志")
    FUNCTION = "edit"
    CATEGORY = "👑 Tikpan 官方独家节点"

    def edit(self, 获取密钥请访问, API_密钥, 底图, 修改指令, 模型, 品质, 代理端口, 遮罩_Mask=None, 产品参考图=None):
        pbar = comfy.utils.ProgressBar(100)
        print(f"[Tikpan-Edit] 💉 视觉整形医生正在手术室就位...", flush=True)

        # 🟢 1. 代理隧道
        proxies = {"http": f"http://127.0.0.1:{代理端口}", "https": f"http://127.0.0.1:{代理端口}"} if 代理端口 else None

        # 🟢 2. 图像预处理
        # GPT-Image-2 Edit 要求底图和遮罩尺寸一致
        def tensor_to_pil(tensor):
            arr = 255. * tensor[0].cpu().numpy()
            return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

        base_img = tensor_to_pil(底图)
        width, height = base_img.size
        # 工业对齐
        width, height = (width // 8) * 8, (height // 8) * 8
        base_img = base_img.resize((width, height), Image.LANCZOS)

        # 处理遮罩 (如果有)
        mask_img = None
        if 遮罩_Mask is not None:
            mask_arr = 遮罩_Mask.cpu().numpy()
            mask_img = Image.fromarray((mask_arr * 255).astype(np.uint8)).convert("L")
            mask_img = mask_img.resize((width, height), Image.LANCZOS)
            # OpenAI 规范：遮罩中透明/黑色代表保留，白色代表修改
            # 我们将 PIL 图像转为带有 Alpha 通道的 RGBA，这是 Edit 接口的标准
            base_img.putalpha(mask_img)

        # 🟢 3. 构造 Payload
        # Edit 接口通常使用 multipart/form-data，但中转站一般会将其封装为 JSON/Base64
        buf_base = BytesIO()
        base_img.save(buf_base, format="PNG") # Edit 必须传 PNG 才能带 Alpha 通道
        base_b64 = base64.b64encode(buf_base.getvalue()).decode("utf-8")

        content = [{"type": "text", "text": f"### EDIT TASK ###\n{修改指令}\n[Maintain consistent lighting and perspective]"}]
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{base_b64}"}
        })

        if 产品参考图 is not None:
            prod_img = tensor_to_pil(产品参考图)
            buf_prod = BytesIO()
            prod_img.save(buf_prod, format="JPEG", quality=80)
            prod_b64 = base64.b64encode(buf_prod.getvalue()).decode("utf-8")
            content.append({"type": "text", "text": "This is the product to be placed in the target area:"})
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{prod_b64}"}
            })

        headers = {"Authorization": f"Bearer {API_密钥}", "Content-Type": "application/json"}
        payload = {
            "model": 模型,
            "messages": [{"role": "user", "content": content}],
            "size": f"{width}x{height}",
            "quality": 品质,
        }

        try:
            pbar.update(30)
            url = f"{API_BASE_URL}/v1/chat/completions" # 使用统一聊天绘图路由
            response = requests.post(url, json=payload, headers=headers, timeout=300, proxies=proxies)
            
            if response.status_code != 200:
                return (self.black_image(width, height), f"❌ 手术失败: {response.text}")
            
            res_json = response.json()
            pbar.update(80)

            # 抓取数据
            img_raw = ""
            if "choices" in res_json:
                img_raw = res_json["choices"][0]["message"].get("content", "")
            elif "data" in res_json:
                img_raw = res_json["data"][0].get("url") or res_json["data"][0].get("b64_json")

            # 暴力清洗与解码
            b64_clean = re.sub(r'[^A-Za-z0-9+/=]', '', img_raw.split("base64,")[-1])
            missing_padding = len(b64_clean) % 4
            if missing_padding: b64_clean += '=' * (4 - missing_padding)
            
            img_bytes = base64.b64decode(b64_clean)
            final_img = Image.open(BytesIO(img_bytes)).convert("RGB")
            
            img_np = np.array(final_img).astype(np.float32) / 255.0
            pbar.update(100)
            return (torch.from_numpy(img_np)[None, ...], "✅ 手术成功：局部重绘完成")

        except Exception as e:
            return (self.black_image(width, height), f"❌ 运行异常: {str(e)}")

    def black_image(self, w, h):
        return torch.zeros((1, h, w, 3))