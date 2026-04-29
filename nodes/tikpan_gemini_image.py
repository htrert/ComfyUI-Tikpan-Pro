import json
import requests
import base64
import torch
import re
import numpy as np
from io import BytesIO
from PIL import Image
import comfy.utils

# 🔐 Tikpan 官方聚合站
API_BASE_URL = "https://tikpan.com"

class TikpanGeminiImageMaxNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "获取密钥请访问": (["👉 https://tikpan.com (官方授权Key获取点)"], ),
                "API_密钥": ("STRING", {"default": "sk-"}),
                "修改指令": ("STRING", {"multiline": True, "default": "请结合参考图，进行精准修改..."}),
                "模型": (["gemini-3.1-flash-image-preview", "gemini-2.0-flash-exp"], {"default": "gemini-3.1-flash-image-preview"}),
                "分辨率": (["512", "1K", "2K", "4K"], {"default": "1K"}),
                "画面比例": (["1:1", "16:9", "9:16", "21:9", "4:3"], {"default": "9:16"}),
                "seed": ("INT", {"default": 888888, "min": 0, "max": 0xffffffffffffffff}),
                "生成后控制": (["fixed", "randomize", "increment", "decrement"], {"default": "randomize"}),
            },
            "optional": {
                f"参考图_{i}": ("IMAGE",) for i in range(1, 15)
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("🖼️_生成结果图", "📄_渲染日志")
    FUNCTION = "execute"
    CATEGORY = "👑 Tikpan 官方独家节点"

    def execute(self, 获取密钥请访问, API_密钥, 修改指令, 模型, 分辨率, 画面比例, seed, 生成后控制, **kwargs):
        pbar = comfy.utils.ProgressBar(100)
        print(f"[Tikpan-Gemini] 🚀 暴力解码引擎已启动，正在拦截视觉信号...", flush=True)

        # 1. 分辨率物理映射
        res_map = {"512": "512x512", "1K": "1024x1024", "2K": "2048x2048", "4K": "4096x4096"}
        target_res = res_map.get(分辨率, "1024x1024")

        # 2. 构造指令与 Payload
        final_prompt = f"### TASK: {修改指令} ###\nSpecs: {画面比例}, {target_res}"
        content = [{"type": "text", "text": final_prompt}]
        
        # 3. 压入参考图 (针对你说的输入两张图)
        for i in range(1, 15):
            img_tensor = kwargs.get(f"参考图_{i}")
            if img_tensor is not None:
                i_arr = 255. * img_tensor[0].cpu().numpy()
                p_img = Image.fromarray(np.clip(i_arr, 0, 255).astype(np.uint8))
                buf = BytesIO()
                p_img.save(buf, format="JPEG", quality=70) # 进一步压缩输入图，减少请求压力
                b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
                content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_str}"}})

        headers = {"Authorization": f"Bearer {API_密钥}", "Content-Type": "application/json"}
        payload = {
            "model": 模型,
            "messages": [{"role": "user", "content": content}],
            "size": target_res,
            "seed": seed % 2147483647
        }

        try:
            pbar.update(20)
            url = f"{API_BASE_URL}/v1/chat/completions"
            response = requests.post(url, json=payload, headers=headers, timeout=300)
            
            if response.status_code != 200:
                return (self.black_image(), f"❌ API 报错: {response.status_code} - {response.text}")
            
            res_json = response.json()
            pbar.update(70)

            # 4. ⚡ 核心修复：多重路径抓取图像数据
            raw_data = ""
            if "data" in res_json:
                raw_data = res_json["data"][0].get("url") or res_json["data"][0].get("b64_json")
            elif "choices" in res_json:
                raw_data = res_json["choices"][0]["message"].get("content", "")

            if not raw_data:
                return (self.black_image(), "⚠️ 响应成功但未发现数据")

            # 5. 🛠️ 暴力清洗算法：只保留 Base64 合法字符
            # 这一步会干掉所有的 Markdown 标签、换行符、空格
            print(f"[Tikpan-Gemini] ⚙️ 正在执行暴力字符清洗...", flush=True)
            # 提取 base64 部分（去掉 data:image... 等前缀）
            if "base64," in raw_data:
                raw_data = raw_data.split("base64,")[-1]
            
            # 使用正则剔除非 base64 字符 [A-Za-z0-9+/=]
            b64_clean = re.sub(r'[^A-Za-z0-9+/=]', '', raw_data)
            
            # 强行对齐填充位
            missing_padding = len(b64_clean) % 4
            if missing_padding:
                b64_clean += '=' * (4 - missing_padding)

            # 6. 解码尝试
            try:
                img_raw = base64.b64decode(b64_clean)
                final_img = Image.open(BytesIO(img_raw)).convert("RGB")
                img_np = np.array(final_img).astype(np.float32) / 255.0
                out_tensor = torch.from_numpy(img_np)[None, ...]
                
                pbar.update(100)
                return (out_tensor, f"✅ 渲染成功 ({target_res})")
            except Exception as e:
                # 如果暴力清洗还失败，说明数据真的在传输中被掐断了
                print(f"数据预览(前100字): {b64_clean[:100]}", flush=True)
                return (self.black_image(), f"❌ 致命解码错误: {str(e)}\n提示：数据包过大或网络截断，请尝试降低分辨率至 1K 测试。")

        except Exception as e:
            return (self.black_image(), f"❌ 运行异常: {str(e)}")

    def black_image(self):
        return torch.zeros((1, 512, 512, 3))