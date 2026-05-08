"""
🎨 Tikpan：豆包图像生成节点 (doubao-seedream-5-0-260128)
基于官方文档重写，仅支持 5.0 模型
"""
import json
import requests
import base64
import torch
import numpy as np
from io import BytesIO
from PIL import Image
import comfy.utils
import urllib3
import traceback

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class TikpanDoubaoImageNode:
    """
    🎨 Tikpan：豆包图像生成节点
    模型：doubao-seedream-5-0-260128
    支持：文生图、图生图（最多14张参考图）、联网搜索增强
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "💰_福利_💰": (["🔥 0.6元RMB兑1虚拟美元余额 | 全网底价 👉 https://tikpan.com"],),
                "获取密钥请访问": (["👉 https://tikpan.com (官方授权Key获取点)"],),
                "api_key": ("STRING", {"default": ""}),
                "prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "一张极致高清的赛博朋克风格产品展示图，霓虹灯光效果，细腻质感",
                    },
                ),
                "size_mode": (
                    ["品质档位", "具体像素"],
                    {"default": "品质档位"},
                ),
                "size_quality": (
                    ["2K", "4K"],
                    {"default": "2K"},
                ),
                "size_pixel": (
                    ["2048x2048", "2304x1728", "1728x2304", "2560x1440", "1440x2560", "2496x1664", "1664x2496", "3024x1296"],
                    {"default": "2048x2048"},
                ),
                "output_format": (
                    ["jpeg", "png"],
                    {"default": "jpeg"},
                ),
                "response_format": (
                    ["url", "b64_json"],
                    {"default": "url"},
                ),
                "watermark": (
                    ["无水印", "有水印"],
                    {"default": "无水印"},
                ),
                "联网搜索增强": (
                    ["关闭", "自动"],
                    {"default": "关闭"},
                ),
                "多图生成": (
                    ["关闭", "自动"],
                    {"default": "关闭"},
                ),
            },
            "optional": {
                "input_image": ("IMAGE", {"tooltip": "参考图（最多14张，连接 Batch 节点可传多张）"}),
                "negative_prompt": ("STRING", {"multiline": True, "default": "low quality, blurry, distorted, watermark, text"}),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("🖼️_生成图像", "📄_渲染日志")
    FUNCTION = "generate_image"
    CATEGORY = "👑 Tikpan 官方独家节点"

    def tensor_to_base64(self, img_tensor, fmt="PNG"):
        """将ComfyUI图像张量转换为base64编码"""
        arr = 255.0 * img_tensor[0].cpu().numpy()
        arr = np.clip(arr, 0, 255).astype(np.uint8)
        img = Image.fromarray(arr).convert("RGB")
        buf = BytesIO()
        img.save(buf, format=fmt)
        b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
        return b64_str

    def download_image(self, url):
        """下载远程图片"""
        try:
            response = requests.get(url, timeout=30, verify=False)
            if response.status_code == 200:
                return Image.open(BytesIO(response.content)).convert("RGB")
        except Exception as e:
            print(f"[Tikpan-Doubao] ⚠️ 图片下载失败: {e}", flush=True)
        return None

    def black_image(self):
        return torch.zeros((1, 1024, 1024, 3))

    def generate_image(self, **kwargs):
        print(f"[Tikpan-Doubao] 📦 收到参数", flush=True)

        api_key = str(kwargs.get("api_key") or "").strip()
        prompt = str(kwargs.get("prompt") or "").strip()
        size_mode = kwargs.get("size_mode", "品质档位")
        size_quality = kwargs.get("size_quality", "2K")
        size_pixel = str(kwargs.get("size_pixel", "2048x2048") or "")
        output_format = kwargs.get("output_format", "jpeg")
        response_format = kwargs.get("response_format", "url")
        watermark = kwargs.get("watermark", "无水印")
        web_search = kwargs.get("联网搜索增强", "关闭")
        multi_image = kwargs.get("多图生成", "关闭")
        input_image = kwargs.get("input_image")
        negative_prompt = str(kwargs.get("negative_prompt") or "").strip()

        model = "doubao-seedream-5-0-260128"

        # 根据模式决定 size 的值
        if size_mode == "品质档位":
            size = size_quality  # 传 "2K" 或 "4K"
        else:
            size = size_pixel.split(" | ")[0].strip()  # 传具体像素如 "2048x2048"

        pbar = comfy.utils.ProgressBar(100)

        # 参数校验
        if not api_key:
            return (self.black_image(), "❌ 错误：请填写有效的 API 密钥")
        if not prompt:
            return (self.black_image(), "❌ 错误：提示词不能为空")

        print(f"[Tikpan-Doubao] 🚀 启动 | 模型: {model} | 尺寸: {size}", flush=True)

        # ===== 构建请求 =====
        url = "https://tikpan.com/v1/images/generations"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "output_format": output_format,
            "response_format": response_format,
            "watermark": watermark == "有水印",
        }

        # 联网搜索（仅 5.0 支持）
        if web_search == "自动":
            payload["tools"] = [{"type": "web_search"}]

        # 多图生成
        if multi_image == "自动":
            payload["sequential_image_generation"] = "auto"

        # 参考图（API 字段名是 images，不是 image）
        if input_image is not None:
            num_images = len(input_image)
            if num_images > 0:
                print(f"[Tikpan-Doubao] 🖼️ 添加 {num_images} 张参考图", flush=True)
                images_b64 = []
                for i, img_tensor in enumerate(input_image):
                    img_b64 = self.tensor_to_base64(
                        img_tensor.unsqueeze(0) if img_tensor.dim() == 3 else img_tensor,
                        fmt=output_format.upper() if output_format == "png" else "JPEG"
                    )
                    mime = "png" if output_format == "png" else "jpeg"
                    images_b64.append(f"data:image/{mime};base64,{img_b64}")

                payload["images"] = images_b64

        # 负向提示词
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt

        print(f"[Tikpan-Doubao] 📤 请求: {json.dumps({k:v for k,v in payload.items() if k != 'images'}, ensure_ascii=False)[:500]}...", flush=True)

        try:
            pbar.update(10)
            response = requests.post(url, json=payload, headers=headers, timeout=120, verify=False)
            pbar.update(60)

            print(f"[Tikpan-Doubao] 📥 响应状态: {response.status_code}", flush=True)

            if response.status_code != 200:
                error_detail = ""
                try:
                    error_json = response.json()
                    error_detail = json.dumps(error_json, ensure_ascii=False)
                except:
                    error_detail = response.text[:500]
                return (self.black_image(), f"❌ API 错误 {response.status_code}\n{error_detail}")

            res_json = response.json()
            print(f"[Tikpan-Doubao] 📋 响应: {json.dumps(res_json, ensure_ascii=False)[:500]}", flush=True)

            # 解析返回数据
            data_list = res_json.get("data", [])
            if not data_list:
                return (self.black_image(), f"❌ 响应中无图像数据\n{json.dumps(res_json, ensure_ascii=False)[:500]}")

            # 取第一张图
            img_data = data_list[0]

            # 获取图像数据
            image_result = None

            if response_format == "b64_json" and "b64_json" in img_data:
                b64_data = img_data["b64_json"]
                img_raw = base64.b64decode(b64_data)
                img_pil = Image.open(BytesIO(img_raw)).convert("RGB")
                img_np = np.array(img_pil).astype(np.float32) / 255.0
                image_result = torch.from_numpy(img_np)[None, ...]
            elif "url" in img_data:
                img_url = img_data["url"]
                print(f"[Tikpan-Doubao] 🔗 图片URL: {img_url[:100]}...", flush=True)
                downloaded_img = self.download_image(img_url)
                if downloaded_img:
                    img_np = np.array(downloaded_img).astype(np.float32) / 255.0
                    image_result = torch.from_numpy(img_np)[None, ...]

            if image_result is None:
                # 尝试从 error 字段获取信息
                error_info = img_data.get("error", {})
                if error_info:
                    return (self.black_image(), f"❌ 生成失败: {error_info.get('message', '未知错误')}")
                return (self.black_image(), f"❌ 无法获取图像数据\n{json.dumps(img_data, ensure_ascii=False)[:500]}")

            pbar.update(100)

            # 构建日志
            log_msg = f"✅ 生成成功\n🧾 模型: {model}\n📐 尺寸: {size}\n🖼️ 实际输出: {img_data.get('size', '未知')}"
            if web_search == "自动":
                log_msg += "\n🌐 联网搜索: 已开启"
            if multi_image == "自动":
                log_msg += "\n🔄 多图生成: 已开启"

            print(f"[Tikpan-Doubao] ✅ 完成", flush=True)
            return (image_result, log_msg)

        except requests.exceptions.Timeout:
            return (self.black_image(), "❌ 请求超时：API响应超过120秒，请稍后重试")
        except Exception as e:
            tb = traceback.format_exc()
            print(f"[Tikpan-Doubao] ❌ 异常: {tb}", flush=True)
            return (self.black_image(), f"❌ 请求异常: {str(e)}\n{tb}")


# ====================== 节点注册 ======================
NODE_CLASS_MAPPINGS = {
    "TikpanDoubaoImageNode": TikpanDoubaoImageNode
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TikpanDoubaoImageNode": "🎨 Tikpan: 豆包图像生成 5.0"
}
