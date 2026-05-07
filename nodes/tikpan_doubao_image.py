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
    模型：doubao-seedream 系列
    支持：文生图、图生图（最多14张参考图）
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "💰_福利_💰": (["🔥 0.6元RMB兑1美元余额 | 全网底价 👉 https://tikpan.com"],),
                "获取密钥请访问": (["👉 https://tikpan.com (官方授权Key获取点)"],),
                "api_key": ("STRING", {"default": ""}),
                "model": ([
                    "doubao-seedream-5-0-260128 | 2K/4K",
                    "doubao-seedream-4-5-251128 | 2K/4K",
                    "doubao-seedream-4-0-250828 | 1K/2K/4K",
                ], {"default": "doubao-seedream-5-0-260128 | 2K/4K"}),
                "prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "一张极致高清的赛博朋克风格产品展示图，霓虹灯光效果，细腻质感，8K分辨率",
                    },
                ),
                "size_5_0_4_5": ([
                    "2048x2048 | 2K-1:1",
                    "2304x1728 | 2K-4:3",
                    "1728x2304 | 2K-3:4",
                    "2848x1600 | 2K-16:9",
                    "1600x2848 | 2K-9:16",
                    "2496x1664 | 2K-3:2",
                    "1664x2496 | 2K-2:3",
                    "3136x1344 | 2K-21:9",
                    "4096x4096 | 4K-1:1",
                    "4704x3520 | 4K-4:3",
                    "3520x4704 | 4K-3:4",
                    "5504x3040 | 4K-16:9",
                    "3040x5504 | 4K-9:16",
                    "4992x3328 | 4K-3:2",
                    "3328x4992 | 4K-2:3",
                    "6240x2656 | 4K-21:9",
                ], {"default": "2048x2048 | 2K-1:1"}),
                "size_4_0": ([
                    "1024x1024 | 1K-1:1",
                    "1152x864 | 1K-4:3",
                    "864x1152 | 1K-3:4",
                    "1280x720 | 1K-16:9",
                    "720x1280 | 1K-9:16",
                    "1248x832 | 1K-3:2",
                    "832x1248 | 1K-2:3",
                    "1512x648 | 1K-21:9",
                    "2048x2048 | 2K-1:1",
                    "2304x1728 | 2K-4:3",
                    "1728x2304 | 2K-3:4",
                    "2848x1600 | 2K-16:9",
                    "1600x2848 | 2K-9:16",
                    "2496x1664 | 2K-3:2",
                    "1664x2496 | 2K-2:3",
                    "3136x1344 | 2K-21:9",
                    "4096x4096 | 4K-1:1",
                    "4704x3520 | 4K-4:3",
                    "3520x4704 | 4K-3:4",
                    "5504x3040 | 4K-16:9",
                    "3040x5504 | 4K-9:16",
                    "4992x3328 | 4K-3:2",
                    "3328x4992 | 4K-2:3",
                    "6240x2656 | 4K-21:9",
                ], {"default": "2048x2048 | 2K-1:1"}),
                "output_format": (["png", "jpeg"], {"default": "png"}),
                "response_format": (["url", "b64_json"], {"default": "url"}),
                "watermark": (["无水印", "有水印"], {"default": "无水印"}),
                "sequential_image_generation": (["关闭", "自动"], {"default": "关闭"}),
            },
            "optional": {
                "input_image": ("IMAGE", {"tooltip": "图生图：支持单张或多张参考图（最多14张）"}),
                "negative_prompt": ("STRING", {"multiline": True, "default": "low quality, blurry, distorted, watermark, text"}),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("🖼️_生成图像", "📄_渲染日志")
    FUNCTION = "generate_image"
    CATEGORY = "👑 Tikpan 官方独家节点"

    def parse_size(self, size_str):
        """解析尺寸字符串，返回宽高像素值"""
        size_str = str(size_str).split(" | ")[0].strip()
        if "x" in size_str:
            w, h = size_str.split("x")
            return f"{w}x{h}"
        return "2048x2048"

    def tensor_to_base64(self, img_tensor):
        """将ComfyUI图像张量转换为base64编码"""
        arr = 255.0 * img_tensor[0].cpu().numpy()
        arr = np.clip(arr, 0, 255).astype(np.uint8)
        img = Image.fromarray(arr).convert("RGB")
        buf = BytesIO()
        img.save(buf, format="PNG")
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

    def generate_image(self, **kwargs):
        print(f"[Tikpan-Doubao] 📦 收到参数", flush=True)

        api_key = str(kwargs.get("api_key") or "").strip()
        model_raw = str(kwargs.get("model") or "")
        prompt = str(kwargs.get("prompt") or "").strip()
        size_5_0_4_5 = kwargs.get("size_5_0_4_5")
        size_4_0 = kwargs.get("size_4_0")
        output_format = kwargs.get("output_format", "png")
        response_format = kwargs.get("response_format", "url")
        watermark = kwargs.get("watermark", "无水印")
        sequential_image = kwargs.get("sequential_image_generation", "关闭")
        input_image = kwargs.get("input_image")
        negative_prompt = str(kwargs.get("negative_prompt") or "").strip()

        # 解析model名称
        model = model_raw.split(" | ")[0].strip()

        # 根据模型选择对应的尺寸
        if model == "doubao-seedream-4-0-250828":
            size = self.parse_size(size_4_0) if size_4_0 else "2048x2048"
        else:
            size = self.parse_size(size_5_0_4_5) if size_5_0_4_5 else "2048x2048"

        pbar = comfy.utils.ProgressBar(100)

        # 参数校验
        if not api_key:
            return (self.black_image(), "❌ 错误：请填写有效的 API 密钥")

        if not prompt:
            return (self.black_image(), "❌ 错误：提示词不能为空")

        print(f"[Tikpan-Doubao] 🚀 启动图像生成 | 模型: {model} | 尺寸: {size}", flush=True)

        # 构建请求
        url = "https://yunwu.ai/v1/images/generations"
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

        # 添加组图功能（仅5.0/4.5/4.0支持）
        if sequential_image == "自动":
            payload["sequential_image_generation"] = "auto"

        # 添加输入图片（图生图模式，支持最多14张参考图）
        if input_image is not None and len(input_image) > 0:
            num_images = len(input_image)
            print(f"[Tikpan-Doubao] 🖼️ 已添加 {num_images} 张参考图进行图生图", flush=True)
            
            # 转换为base64数组
            images_b64 = []
            for i, img_tensor in enumerate(input_image):
                img_b64 = self.tensor_to_base64(img_tensor.unsqueeze(0) if img_tensor.dim() == 3 else img_tensor)
                images_b64.append(f"data:image/png;base64,{img_b64}")
            
            # 如果只有一张图，用字符串；多张图用数组
            if num_images == 1:
                payload["image"] = images_b64[0]
            else:
                payload["image"] = images_b64

        print(f"[Tikpan-Doubao] 📤 请求 payload: {json.dumps(payload, ensure_ascii=False, indent=2)[:500]}...", flush=True)

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
            print(f"[Tikpan-Doubao] 📋 响应数据: {json.dumps(res_json, ensure_ascii=False)[:500]}", flush=True)

            # 解析返回数据
            data_list = res_json.get("data", [])
            if not data_list:
                return (self.black_image(), f"❌ 响应中无图像数据\n{json.dumps(res_json, ensure_ascii=False)[:500]}")

            # 取第一张图
            img_data = data_list[0]

            # 检查内容过滤
            content_filter = img_data.get("content_filter_results", {})
            filtered = any(
                content_filter.get(category, {}).get("filtered", False)
                for category in ["hate", "self_harm", "sexual", "violence"]
            )
            if filtered:
                print(f"[Tikpan-Doubao] ⚠️ 内容被过滤: {content_filter}", flush=True)

            # 获取图像数据
            image_result = None

            if response_format == "b64_json" and "b64_json" in img_data:
                b64_data = img_data["b64_json"]
                img_raw = base64.b64decode(b64_data)
                img_pil = Image.open(BytesIO(img_raw)).convert("RGB")
                img_np = np.array(img_pil).astype(np.float32) / 255.0
                image_result = torch.from_numpy(img_np)[None, ...]
            elif "url" in img_data:
                # 下载图片
                img_url = img_data["url"]
                print(f"[Tikpan-Doubao] 🔗 图片URL: {img_url[:100]}...", flush=True)
                downloaded_img = self.download_image(img_url)
                if downloaded_img:
                    img_np = np.array(downloaded_img).astype(np.float32) / 255.0
                    image_result = torch.from_numpy(img_np)[None, ...]

            if image_result is None:
                return (self.black_image(), f"❌ 无法获取图像数据\n{json.dumps(img_data, ensure_ascii=False)[:500]}")

            pbar.update(100)

            # 构建日志
            revised_prompt = img_data.get("revised_prompt", "")
            log_msg = f"✅ 生成成功"
            if revised_prompt:
                log_msg += f"\n📝 模型修订后的提示词:\n{revised_prompt[:200]}"
            log_msg += f"\n📐 尺寸: {size}"

            print(f"[Tikpan-Doubao] ✅ 图像生成完成", flush=True)
            return (image_result, log_msg)

        except requests.exceptions.Timeout:
            return (self.black_image(), "❌ 请求超时：API响应超过120秒，请稍后重试")
        except Exception as e:
            tb = traceback.format_exc()
            print(f"[Tikpan-Doubao] ❌ 异常: {tb}", flush=True)
            return (self.black_image(), f"❌ 请求异常: {str(e)}\n{tb}")

    def black_image(self):
        return torch.zeros((1, 1024, 1024, 3))


# ====================== 节点注册 ======================
NODE_CLASS_MAPPINGS = {
    "TikpanDoubaoImageNode": TikpanDoubaoImageNode
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TikpanDoubaoImageNode": "🎨 Tikpan: 豆包图像生成"
}
