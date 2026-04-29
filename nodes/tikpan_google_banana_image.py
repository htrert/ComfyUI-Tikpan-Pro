import json
import requests
import base64
import torch
import numpy as np
from io import BytesIO
from PIL import Image
import comfy.utils

class TikpanGoogleBananaImageNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "Google_API_Key": ("STRING", {"default": "在此粘贴你的 AI Studio API Key"}),
                "模型选择": ([
                    "gemini-3.1-flash-image-preview", 
                    "gemini-3-pro-image-preview"
                ], {"default": "gemini-3.1-flash-image-preview"}),
                "提示词": ("STRING", {"multiline": True, "default": "一张极致高清的赛博朋克风格产品展示图..."}),
                "画面比例": (["1:1", "16:9", "9:16", "4:3", "3:4"], {"default": "1:1"}),
                "负面提示词": ("STRING", {"multiline": True, "default": "low quality, blurry, distorted"}),
                "seed": ("INT", {"default": 888888, "min": 0, "max": 0xffffffffffffffff}),
                "生成后控制": (["fixed", "randomize", "increment", "decrement"], {"default": "randomize"}),
                
                # 🛠️ 动态代理设置：加入悬浮提示逻辑
                "代理端口": ("STRING", {
                    "default": "10808",
                    "tooltip": "常用默认端口参考：\n- v2rayN: 10808\n- Clash: 7890\n- SSR: 1080\n- 其它: 8889\n若开启TUN模式则可忽略此项。"
                }),
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("🖼️_生成图像", "📄_渲染日志")
    FUNCTION = "generate_image"
    CATEGORY = "👑 Tikpan 官方独家节点"

    def generate_image(self, Google_API_Key, 模型选择, 提示词, 画面比例, 负面提示词, seed, 生成后控制, 代理端口):
        pbar = comfy.utils.ProgressBar(100)
        
        # 🟢 动态配置代理：从 UI 获取用户填写的端口
        proxies = None
        if 代理端口 and 代理端口.strip():
            proxies = {
                "http": f"http://127.0.0.1:{代理端口.strip()}",
                "https": f"http://127.0.0.1:{代理端口.strip()}",
            }
            print(f"[Tikpan-Banana] 📡 正在通过用户指定端口({代理端口})连接 Google...", flush=True)
        else:
            print(f"[Tikpan-Banana] 📡 未设置代理端口，尝试直连或系统全局代理...", flush=True)

        # 🛠️ 核心修复：种子 64位 转 32位（Google API 限制）
        safe_seed = seed % 2147483647

        refined_prompt = f"{提示词}\n\n[Output Specs: Aspect Ratio {画面比例}, Negative Prompt: {负面提示词}]"

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{模型选择}:generateContent?key={Google_API_Key}"
        headers = {'Content-Type': 'application/json'}
        
        payload = {
            "contents": [{"parts": [{"text": refined_prompt}]}],
            "generationConfig": {"candidateCount": 1}
        }

        try:
            pbar.update(20)
            response = requests.post(
                url, json=payload, headers=headers, timeout=180, 
                proxies=proxies, verify=True
            )
            pbar.update(60)
            
            res_json = response.json()

            # 🛠️ 针对 429 错误（额度限制）的特殊友好提示
            if response.status_code == 429:
                wait_time = "稍后再试"
                if "retryDelay" in str(res_json):
                    wait_time = "30-60秒"
                return (self.black_image(), f"❌ API 额度超限 (429)：你跑太快了！请等待 {wait_time} 再点运行。")

            if response.status_code != 200:
                return (self.black_image(), f"❌ 协议报错: {response.status_code}\n{json.dumps(res_json)}")

            # 解析图像数据
            try:
                parts = res_json['candidates'][0]['content']['parts']
                img_b64 = ""
                for part in parts:
                    if 'inlineData' in part:
                        img_b64 = part['inlineData']['data']
                        break
                
                if not img_b64:
                    return (self.black_image(), f"⚠️ 响应成功但没图。FinishReason: {res_json['candidates'][0].get('finishReason')}")

                img_raw = base64.b64decode(img_b64)
                img_pil = Image.open(BytesIO(img_raw)).convert("RGB")
                img_np = np.array(img_pil).astype(np.float32) / 255.0
                img_tensor = torch.from_numpy(img_np)[None, ...]
                
                pbar.update(100)
                return (img_tensor, f"✅ 生成成功 | Seed: {safe_seed}")

            except Exception as e:
                return (self.black_image(), f"❌ 解析失败: {str(e)}")

        except Exception as e:
            return (self.black_image(), f"❌ 请求异常：请检查端口 {代理端口} 是否正确\n{str(e)}")

    def black_image(self):
        return torch.zeros((1, 1024, 1024, 3))