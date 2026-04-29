import json
import requests
import comfy.utils
import comfy.model_management

class TikpanGoogleGeminiNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "Google_API_Key": ("STRING", {"default": "在此粘贴你的 AI Studio API Key"}),
                "模型选择": (["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash-exp"], {"default": "gemini-1.5-flash"}),
                "提示词": ("STRING", {"multiline": True, "default": "请简要描述这张图的构图..."}),
                "最高Token数": ("INT", {"default": 2048, "min": 1, "max": 8192}),
                "温度_Temperature": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 2.0, "step": 0.1}),
            },
            "optional": {
                "上下文参考": ("STRING", {"forceInput": True}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("📄_生成文本", "📄_完整响应")
    FUNCTION = "call_gemini"
    CATEGORY = "👑 Tikpan 官方独家节点"

    def call_gemini(self, Google_API_Key, 模型选择, 提示词, 最高Token数, 温度_Temperature, 上下文参考=""):
        pbar = comfy.utils.ProgressBar(100)
        print(f"[Tikpan-Gemini] 📡 正在连接 Google AI Studio 核心节点...", flush=True)

        # 1. 组装提示词
        full_prompt = 提示词
        if 上下文参考:
            full_prompt = f"参考背景: {上下文参考}\n\n任务指令: {提示词}"

        # 2. 构建符合官方 CURL 格式的 URL 和 Payload
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{模型选择}:generateContent?key={Google_API_Key}"
        headers = {'Content-Type': 'application/json'}
        
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": full_prompt}
                    ]
                }
            ],
            "generationConfig": {
                "maxOutputTokens": 最高Token数,
                "temperature": 温度_Temperature,
            }
        }

        try:
            pbar.update(30)
            # 发送请求
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            
            pbar.update(70)
            res_json = response.json()

            if response.status_code != 200:
                error_msg = res_json.get("error", {}).get("message", "未知错误")
                return (f"❌ API 报错: {error_msg}", json.dumps(res_json, indent=2))

            # 3. 解析 Google 特有的嵌套 JSON 结构
            # 路径: candidates[0].content.parts[0].text
            try:
                generated_text = res_json['candidates'][0]['content']['parts'][0]['text']
            except (KeyError, IndexError):
                return ("❌ 响应解析失败，请检查模型是否支持或内容是否触发安全策略", json.dumps(res_json, indent=2))

            pbar.update(100)
            print(f"[Tikpan-Gemini] ✅ 生成成功！", flush=True)
            return (generated_text, json.dumps(res_json, indent=2, ensure_ascii=False))

        except Exception as e:
            return (f"❌ 网络异常: {str(e)}", str(e))