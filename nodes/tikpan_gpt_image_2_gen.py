import json
import requests
import base64
import torch
import re
import numpy as np
from io import BytesIO
from PIL import Image
import comfy.utils

# 🔐 Tikpan 官方聚合路由
API_BASE_URL = "https://tikpan.com"

class TikpanGptImage2GenNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "获取密钥请访问": (["👉 https://tikpan.com (官方授权Key获取点)"], ),
                "API_密钥": ("STRING", {"default": "sk-"}),
                "生成指令": ("STRING", {"multiline": True, "default": "请参考提供的 Image_1 到 Image_14 的视觉特征，生成一张极致高清的..."}),
                "模型": (["gpt-image-2-all"], {"default": "gpt-image-2-all"}),
                "分辨率档位": (["512", "1K", "2K", "4K"], {"default": "1K"}),
                "画面比例": (["1:1", "16:9", "9:16", "21:9", "4:3", "3:4"], {"default": "1:1"}),
                "品质": (["standard", "hd"], {"default": "hd"}),
                "seed": ("INT", {"default": 888888, "min": 0, "max": 0xffffffffffffffff}),
                "代理端口": ("STRING", {"default": "10808"}),
            },
            "optional": {
                f"参考图_{i}": ("IMAGE",) for i in range(1, 15)
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("🖼️_生成结果图", "📄_渲染日志")
    FUNCTION = "generate"
    CATEGORY = "👑 Tikpan 官方独家节点"

    def generate(self, 获取密钥请访问, API_密钥, 生成指令, 模型, 分辨率档位, 画面比例, 品质, seed, 代理端口, **kwargs):
        pbar = comfy.utils.ProgressBar(100)
        print(f"[Tikpan-Gen] 🚀 GPT-Image-2 视觉建筑师正在构筑画面...", flush=True)

        # 🟢 1. 代理隧道配置
        proxies = {"http": f"http://127.0.0.1:{代理端口}", "https": f"http://127.0.0.1:{代理端口}"} if 代理端口 else None

        # 🟢 2. 智能尺寸动态计算 (老板最关心的逻辑)
        res_map = {"512": 512, "1K": 1024, "2K": 2048, "4K": 4096}
        base_val = res_map.get(分辨率档位, 1024)
        w_ratio, h_ratio = map(int, 画面比例.split(':'))
        
        # 以 base_val 为长边进行缩放
        if w_ratio >= h_ratio:
            width = base_val
            height = int(base_val * (h_ratio / w_ratio))
        else:
            height = base_val
            width = int(base_val * (w_ratio / h_ratio))
        
        # 对齐到 8 的倍数（工业标准）
        width, height = (width // 8) * 8, (height // 8) * 8
        target_res = f"{width}x{height}"

        # 🟢 3. 构造多模态 Payload (支持 14 路图)
        content = [{"type": "text", "text": f"### GENERATE TASK ###\n{生成指令}\n\n[Format: {画面比例}, Size: {target_res}, Quality: {品质}]"}]
        
        for i in range(1, 15):
            img_tensor = kwargs.get(f"参考图_{i}")
            if img_tensor is not None:
                # 转换参考图
                i_arr = 255. * img_tensor[0].cpu().numpy()
                p_img = Image.fromarray(np.clip(i_arr, 0, 255).astype(np.uint8))
                # 预缩放参考图以防 Payload 过大 (GPT-Image-2 对输入图质量敏感但体积有限制)
                p_img.thumbnail((1024, 1024))
                buf = BytesIO()
                p_img.save(buf, format="JPEG", quality=75)
                b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
                
                content.append({"type": "text", "text": f"Reference Image_{i}:"})
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64_str}"}
                })

        headers = {"Authorization": f"Bearer {API_密钥}", "Content-Type": "application/json"}
        # 兼容 OpenAI v1/chat/completions 新标准
        payload = {
            "model": 模型,
            "messages": [{"role": "user", "content": content}],
            "size": target_res,
            "quality": 品质,
            "seed": seed % 2147483647
        }

        try:
            pbar.update(20)
            url = f"{API_BASE_URL}/v1/chat/completions"
            response = requests.post(url, json=payload, headers=headers, timeout=300, proxies=proxies)
            
            if response.status_code != 200:
                return (self.black_image(), f"❌ API 报错: {response.text}")
            
            res_json = response.json()
            pbar.update(70)

            # 🟢 4. 暴力解码与清洗 (解决断流与格式混乱)
            img_raw = ""
            if "choices" in res_json:
                img_raw = res_json["choices"][0]["message"].get("content", "")
            elif "data" in res_json:
                img_raw = res_json["data"][0].get("url") or res_json["data"][0].get("b64_json")

            if not img_raw:
                return (self.black_image(), f"⚠️ 未捕捉到图像数据: {json.dumps(res_json)}")

            # 如果返回的是 URL，则通过隧道下载
            if img_raw.startswith("http"):
                img_res = requests.get(img_raw, timeout=60, proxies=proxies)
                final_img = Image.open(BytesIO(img_res.content)).convert("RGB")
            else:
                # 执行暴力字符清洗
                b64_clean = re.sub(r'[^A-Za-z0-9+/=]', '', img_raw.split("base64,")[-1])
                missing_padding = len(b64_clean) % 4
                if missing_padding: b64_clean += '=' * (4 - missing_padding)
                img_bytes = base64.b64decode(b64_clean)
                final_img = Image.open(BytesIO(img_bytes)).convert("RGB")
            
            # 转换回 ComfyUI Tensor
            img_np = np.array(final_img).astype(np.float32) / 255.0
            out_tensor = torch.from_numpy(img_np)[None, ...]
            
            pbar.update(100)
            print(f"[Tikpan-Gen] 🎉 画面构筑完成！尺寸: {target_res}", flush=True)
            return (out_tensor, f"✅ 生成成功 | 物理分辨率: {target_res}")

        except Exception as e:
            return (self.black_image(), f"❌ 运行异常: {str(e)}")

    def black_image(self):
        return torch.zeros((1, 512, 512, 3))

# 注册映射
NODE_CLASS_MAPPINGS = {"TikpanGptImage2GenNode": TikpanGptImage2GenNode}
NODE_DISPLAY_NAME_MAPPINGS = {"TikpanGptImage2GenNode": "🎨 Tikpan: GPT-Image-2 视觉建筑师(生成)"}