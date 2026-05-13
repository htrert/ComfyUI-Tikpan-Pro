# nodes/tikpan_gemini_video_analyst.py
import json
import base64
import time
import requests
import urllib3
import numpy as np
import io
import wave
from io import BytesIO
from PIL import Image
import torch

import comfy.utils
import comfy.model_management

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 🔐 核心：写死中转站地址
HARDCODED_BASE_URL = "https://tikpan.com/v1"

def _comfy_waveform_to_wav_base64(waveform, sample_rate):
    wf = waveform.detach().cpu().float()
    if wf.dim() == 3: wf = wf.squeeze(0)
    if wf.dim() == 1: wf = wf.unsqueeze(0)
    channels, _ = wf.shape
    wf = wf.clamp(-1.0, 1.0)
    pcm = (wf.numpy() * 32767.0).astype(np.int16)
    if channels == 1:
        interleaved = pcm[0]
    else:
        interleaved = np.transpose(pcm, (1, 0)).reshape(-1)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(int(channels))
        wav.setsampwidth(2)
        wav.setframerate(int(sample_rate))
        wav.writeframes(interleaved.tobytes())
    return base64.b64encode(buf.getvalue()).decode("utf-8")

class TikpanGeminiVideoAnalystNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "获取密钥地址": (["👉 https://tikpan.com (官方授权Key获取点)"], ),
                "API_密钥": ("STRING", {"default": "sk-"}),
                "视频流_IMAGE": ("IMAGE",),
                "视频帧率FPS": ("INT", {"default": 24, "min": 8, "max": 60, "tooltip": "用于计算视频真实物理时长"}),
                "分析模型": (["gemini-3.1-flash", "gemini-3.1-pro", "gpt-5.4-mini", "gpt-4o"], {"default": "gemini-3.1-flash"}),
            },
            "optional": {
                "音频流_AUDIO": ("AUDIO",),
                "重点分析要求": ("STRING", {"multiline": True, "default": "请重点关注物理规律、光影变化和人物微表情。"}),
                "校验HTTPS证书": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("📄_专业分镜与脚本报告",)
    FUNCTION = "analyze_video"
    CATEGORY = "👑 Tikpan 官方独家节点"

    def analyze_video(
        self,
        获取密钥地址,
        API_密钥=None,
        视频流_IMAGE=None,
        视频帧率FPS=24,
        分析模型="gemini-3.1-flash",
        音频流_AUDIO=None,
        重点分析要求="",
        校验HTTPS证书=True,
        **kwargs,
    ):
        API_密钥 = API_密钥 or kwargs.get("Tikpan_API密钥") or kwargs.get("API密钥")
        视频帧率FPS = kwargs.get("视频帧率_FPS", 视频帧率FPS)
        重点分析要求 = 重点分析要求 or kwargs.get("特定关注点", "")
        comfy.model_management.throw_exception_if_processing_interrupted()

        if not API_密钥 or len(API_密钥) < 10:
            return ("❌ 请填写API密钥: 请前往 https://tikpan.com 获取", )

        headers = {"Authorization": f"Bearer {API_密钥}", "Content-Type": "application/json"}
        session = requests.Session()
        session.trust_env = False

        # ====================================================================
        # 1. 🧠 AI 极限体积熔断与动态降质算法 (完美规避 10MB 限制)
        # ====================================================================
        total_frames = 视频流_IMAGE.shape[0]
        duration_seconds = total_frames / float(视频帧率FPS)
        
        # 策略：强制 1秒 1帧，最高 60 帧
        extract_count = max(4, int(duration_seconds))
        extract_count = min(extract_count, 60)
        
        # 根据帧数动态调整压缩率和分辨率
        if extract_count > 30:
            target_res, jpeg_quality = 480, 65
        elif extract_count > 15:
            target_res, jpeg_quality = 512, 75
        else:
            target_res, jpeg_quality = 768, 85

        print(f"\n[Tikpan Analyst] 🎬 视频时长: {duration_seconds:.1f}秒 (共{total_frames}帧)。")
        print(f"[Tikpan Analyst] ⚙️ 计划抽取: {extract_count} 帧，动态分辨率: {target_res}px，压缩率: {jpeg_quality}")
        
        indices = np.linspace(0, total_frames - 1, extract_count, dtype=int)
        base64_images = []
        current_payload_size = 0
        MAX_SAFE_SIZE = 8 * 1024 * 1024 # 绝对安全线：8 MB (留出 2MB 空间给音频和文本)
        
        for idx in indices:
            i_arr = 255. * 视频流_IMAGE[idx:idx+1].cpu().numpy()[0]
            pil_img = Image.fromarray(np.clip(i_arr, 0, 255).astype(np.uint8))
            pil_img.thumbnail((target_res, target_res))
            buf = BytesIO()
            pil_img.save(buf, format="JPEG", quality=jpeg_quality)
            b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
            
            # 体积熔断检测
            str_size = len(b64_str)
            if current_payload_size + str_size > MAX_SAFE_SIZE:
                print(f"[Tikpan Analyst] ⚠️ 触发 8MB 极限熔断保护！提前截断，最终使用 {len(base64_images)} 帧以保证请求成功。")
                break
                
            base64_images.append(b64_str)
            current_payload_size += str_size

        actual_size_mb = current_payload_size / (1024 * 1024)
        print(f"[Tikpan Analyst] 📦 图像装载完毕，实际帧数: {len(base64_images)}，总体积: {actual_size_mb:.2f} MB (安全通过)")

        # ====================================================================
        # 2. 🎼 处理音频流
        # ====================================================================
        audio_b64 = None
        if 音频流_AUDIO is not None:
            try:
                audio_b64 = _comfy_waveform_to_wav_base64(音频流_AUDIO["waveform"], 音频流_AUDIO["sample_rate"])
                audio_size_mb = len(audio_b64) / (1024 * 1024)
                print(f"[Tikpan Analyst] 🎧 音频打包成功，体积: {audio_size_mb:.2f} MB")
            except Exception as e:
                print(f"[Tikpan Analyst] ⚠️ 音频处理失败，将仅依赖视觉分析: {e}")

        # ====================================================================
        # 3. 🎯 构建高阶 Prompt
        # ====================================================================
        system_prompt = f"""
        你是一位顶级的好莱坞电影解析师、AI视频提示词专家和编剧。
        请你从以下维度深度解构视频，为 Sora/Grok3 级别的模型提供绝佳的重绘提示词素材：
        
        【1. 摄影机与运镜 (Camera & Motion)】：推、拉、摇、移，焦段与景深。
        【2. 主体物理动作 (Physics & Actions)】：主体行为细节，材质/衣物的物理互动。
        【3. 光影与美学 (Lighting & Color)】：光源方向、质感、色彩基调。
        【4. 场景与氛围 (Environment)】：微小环境细节、年代感。
        【5. 视听双轨脚本 (Script & Audio)】：如提供音频，请提取对白/情绪；如无音频，请通过唇语和动作**反向推演虚构一段剧情脚本**。
        
        用户重点关注：{重点分析要求}
        """

        content_list = [{"type": "text", "text": system_prompt}]
        
        for b64 in base64_images:
            content_list.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
            
        if audio_b64:
            content_list.append({
                "type": "input_audio",
                "input_audio": {"data": audio_b64, "format": "wav"}
            })

        payload = {
            "model": 分析模型,
            "messages": [{"role": "user", "content": content_list}],
            "temperature": 0.4
        }

        print(f"[Tikpan Analyst] 🚀 正在呼叫 {分析模型} 发起突击...")
        
        try:
            res = session.post(
                f"{HARDCODED_BASE_URL}/chat/completions",
                json=payload,
                headers=headers,
                verify=bool(校验HTTPS证书),
                timeout=180,
            )
            res.raise_for_status()
            res_json = res.json()
            analysis_report = res_json.get("choices", [{}])[0].get("message", {}).get("content", str(res_json))
        except Exception as e:
            return (f"❌ 解析失败: {str(e)}", )

        comfy.model_management.throw_exception_if_processing_interrupted()
        print(f"[Tikpan Analyst] ✅ 深度解析完成！")
        
        return (analysis_report.strip(), )
