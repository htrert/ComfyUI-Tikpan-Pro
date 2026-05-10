"""
🎨 Tikpan：豆包图像生成节点（正式发布版最终代码）
模型：doubao-seedream-5-0-260128
已确认对应官方：Doubao-Seedream-5.0-lite

支持：
- 文生图
- 图生图
- 单图 / 多图参考图输入（最多14张）
- ComfyUI IMAGE 输入 + 手动 URL/Base64 输入
- 组图全部输出（Batch IMAGE）
- 联网搜索增强
- response_format 自动兼容（对象 / 字符串）

尺寸模式：
1. 品质档位：2K / 3K
2. 比例尺寸：2K/3K + 宽高比 自动映射到像素

参考图输入规则：
- 单图：image = string
- 多图：image = array[string]
- 支持 URL 或 Base64（data:image/<fmt>;base64,...）
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


SIZE_MAP = {
    "2K": {
        "1:1 正方形": "2048x2048",
        "4:3 横版": "2304x1728",
        "3:4 竖版": "1728x2304",
        "16:9 宽屏": "2848x1600",
        "9:16 手机竖屏": "1600x2848",
        "3:2 海报横版": "2496x1664",
        "2:3 海报竖版": "1664x2496",
        "21:9 超宽屏": "3136x1344",
    },
    "3K": {
        "1:1 正方形": "3072x3072",
        "4:3 横版": "3456x2592",
        "3:4 竖版": "2592x3456",
        "16:9 宽屏": "4096x2304",
        "9:16 手机竖屏": "2304x4096",
        "3:2 海报横版": "3744x2496",
        "2:3 海报竖版": "2496x3744",
        "21:9 超宽屏": "4704x2016",
    }
}


class TikpanDoubaoImageNode:
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
                    ["品质档位", "比例尺寸"],
                    {"default": "品质档位"},
                ),
                "size_quality": (
                    ["2K", "3K"],
                    {"default": "2K"},
                ),
                "aspect_ratio": (
                    [
                        "1:1 正方形",
                        "4:3 横版",
                        "3:4 竖版",
                        "16:9 宽屏",
                        "9:16 手机竖屏",
                        "3:2 海报横版",
                        "2:3 海报竖版",
                        "21:9 超宽屏",
                    ],
                    {"default": "1:1 正方形"},
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
                "最多生成张数": (
                    "INT",
                    {"default": 4, "min": 1, "max": 15},
                ),
                "multi_image_fallback": (
                    ["严格报错", "自动降级为首图"],
                    {"default": "严格报错"},
                ),
            },
            "optional": {
                "input_image": ("IMAGE", {"tooltip": "参考图，支持单张或多张（Batch 最多14张）"}),
                "image_url_or_base64": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "tooltip": "可手动输入参考图 URL 或 Base64；支持多行，一行一个；可与 input_image 合并，最多14张",
                    },
                ),
                "negative_prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                    },
                ),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("🖼️_生成图像Batch", "📄_渲染日志")
    FUNCTION = "generate_image"
    CATEGORY = "👑 Tikpan 官方独家节点"

    def looks_like_base64(self, s):
        if not s:
            return False
        s = s.strip()
        if len(s) < 32:
            return False
        # 使用 set 提升超大字符串的查表速度
        allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=\n\r")
        return all(c in allowed for c in s)

    def tensor_to_base64(self, img_tensor, fmt="PNG"):
        arr = 255.0 * img_tensor[0].cpu().numpy()
        arr = np.clip(arr, 0, 255).astype(np.uint8)
        img = Image.fromarray(arr).convert("RGB")
        buf = BytesIO()
        img.save(buf, format=fmt)
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    def download_image(self, url):
        try:
            response = requests.get(url, timeout=60, verify=False)
            response.raise_for_status()
            return Image.open(BytesIO(response.content)).convert("RGB")
        except Exception as e:
            print(f"[Tikpan-Doubao] ⚠️ 图片下载失败: {e}", flush=True)
            return None

    def black_image(self):
        return torch.zeros((1, 1024, 1024, 3), dtype=torch.float32)

    def pil_to_tensor(self, img_pil):
        img_np = np.array(img_pil).astype(np.float32) / 255.0
        return torch.from_numpy(img_np)[None, ...]

    def resize_tensor_to(self, tensor_img, target_w, target_h):
        if tensor_img.shape[1] == target_h and tensor_img.shape[2] == target_w:
            return tensor_img
        x = tensor_img.permute(0, 3, 1, 2)
        x = torch.nn.functional.interpolate(
            x,
            size=(target_h, target_w),
            mode="bilinear",
            align_corners=False
        )
        return x.permute(0, 2, 3, 1)

    def resolve_size(self, size_mode, size_quality, aspect_ratio):
        if size_mode == "品质档位":
            return size_quality, f"品质档位：{size_quality}"

        pixel_size = SIZE_MAP.get(size_quality, SIZE_MAP["2K"]).get(
            aspect_ratio,
            SIZE_MAP["2K"]["1:1 正方形"]
        )
        return pixel_size, f"{size_quality}｜{aspect_ratio}｜{pixel_size}"

    def normalize_external_image_lines(self, image_url_or_base64, output_format):
        items = []
        if not image_url_or_base64:
            return items

        mime = "png" if output_format == "png" else "jpeg"
        lines = [x.strip() for x in str(image_url_or_base64).splitlines() if x.strip()]

        for line in lines:
            if line.startswith("http://") or line.startswith("https://"):
                items.append(line)
            elif line.startswith("data:image/"):
                items.append(line)
            elif self.looks_like_base64(line):
                items.append(f"data:image/{mime};base64,{line}")
            else:
                print(f"[Tikpan-Doubao] ⚠️ 跳过无效的手动图片输入: {line[:80]}", flush=True)

        return items

    def build_input_image_list(self, input_image, image_url_or_base64, output_format):
        mime = "png" if output_format == "png" else "jpeg"
        save_fmt = "PNG" if output_format == "png" else "JPEG"

        images = []
        source_logs = []

        # 1) ComfyUI IMAGE 输入
        if input_image is not None and isinstance(input_image, torch.Tensor):
            if input_image.dim() == 4:
                for i in range(input_image.shape[0]):
                    img_tensor = input_image[i:i + 1]
                    img_b64 = self.tensor_to_base64(img_tensor, fmt=save_fmt)
                    images.append(f"data:image/{mime};base64,{img_b64}")
                    source_logs.append(f"ComfyUI输入第{i + 1}张")
            elif input_image.dim() == 3:
                img_b64 = self.tensor_to_base64(input_image.unsqueeze(0), fmt=save_fmt)
                images.append(f"data:image/{mime};base64,{img_b64}")
                source_logs.append("ComfyUI输入第1张")

        # 2) 手动 URL/Base64 输入
        external_items = self.normalize_external_image_lines(image_url_or_base64, output_format)
        for idx, item in enumerate(external_items):
            images.append(item)
            if item.startswith("http://") or item.startswith("https://"):
                source_logs.append(f"手动输入URL第{idx + 1}张")
            else:
                source_logs.append(f"手动输入Base64第{idx + 1}张")

        truncated = False
        original_count = len(images)

        if len(images) > 14:
            images = images[:14]
            source_logs = source_logs[:14]
            truncated = True

        return images, source_logs, truncated, original_count

    def build_image_payload(self, image_list):
        if not image_list:
            return None, 0, "none"
        if len(image_list) == 1:
            return image_list[0], 1, "string"
        return image_list, len(image_list), "array"

    def decode_one_image_item(self, img_data, response_format):
        if response_format == "b64_json" and "b64_json" in img_data:
            try:
                img_raw = base64.b64decode(img_data["b64_json"])
                img_pil = Image.open(BytesIO(img_raw)).convert("RGB")
                return img_pil, f"{img_pil.size[0]}x{img_pil.size[1]}", "b64_json"
            except Exception as e:
                print(f"[Tikpan-Doubao] ⚠️ Base64 解码失败: {e}", flush=True)

        if "url" in img_data:
            img_pil = self.download_image(img_data["url"])
            if img_pil is not None:
                return img_pil, f"{img_pil.size[0]}x{img_pil.size[1]}", "url"

        return None, "未知", "unknown"

    def post_with_response_format_fallback(self, url, headers, payload):
        """
        双向智能回退 + 终极兜底
        有些中转站 Chat 层要对象，Image 层要字符串，甚至两层都冲突
        策略：先发标准字符串 → 不行换对象 → 还不行就删除 response_format
        """
        # 提取真正的格式值
        rf_raw = payload.get("response_format", "url")
        if isinstance(rf_raw, dict):
            rf_str = rf_raw.get("type", "url")
        else:
            rf_str = str(rf_raw)

        # 尝试一：发字符串（OpenAI 图像接口标准）
        p1 = dict(payload)
        p1["response_format"] = rf_str
        r1 = requests.post(url, json=p1, headers=headers, timeout=180, verify=False)
        if r1.status_code == 200:
            return r1

        err1 = (r1.text or "")[:500]

        # 尝试二：如果 Chat 层要求对象格式 → 发对象
        if "cannot unmarshal string" in err1 and "ResponseFormat" in err1:
            print("[Tikpan-Doubao] ♻️ Chat层要求对象格式，重试...", flush=True)
            p2 = dict(payload)
            p2["response_format"] = {"type": rf_str}
            r2 = requests.post(url, json=p2, headers=headers, timeout=180, verify=False)
            if r2.status_code == 200:
                return r2
            err2 = (r2.text or "")[:500]

            # 尝试三：如果 Image 层又要字符串 → 再发字符串（避开 Chat 层验证）
            if "cannot unmarshal object" in err2 and "ImageRequest" in err2:
                print("[Tikpan-Doubao] ♻️ Image层又要字符串，最终尝试...", flush=True)
                p3 = dict(payload)
                del p3["response_format"]  # 不传这个字段，让 API 用默认值
                r3 = requests.post(url, json=p3, headers=headers, timeout=180, verify=False)
                if r3.status_code == 200:
                    return r3

        # 终极兜底：删掉 response_format，用 API 默认值
        print("[Tikpan-Doubao] ♻️ 回退失败，删除 response_format 兜底", flush=True)
        p4 = dict(payload)
        p4.pop("response_format", None)
        return requests.post(url, json=p4, headers=headers, timeout=180, verify=False)

    def is_multi_image_not_supported_error(self, response):
        try:
            text = response.text or ""
        except Exception:
            text = ""

        lower_text = text.lower()
        keywords = [
            "multi image",
            "multiple images",
            "expected string",
            "cannot unmarshal array",
            "image must be string",
            "invalid image type",
            "array[string]",
        ]
        return any(k in lower_text for k in keywords)

    def generate_image(self, **kwargs):
        print("[Tikpan-Doubao] 📦 收到参数", flush=True)

        api_key = str(kwargs.get("api_key") or "").strip()
        prompt = str(kwargs.get("prompt") or "").strip()
        size_mode = kwargs.get("size_mode", "品质档位")
        size_quality = str(kwargs.get("size_quality", "2K") or "2K").strip()
        aspect_ratio = str(kwargs.get("aspect_ratio", "1:1 正方形") or "1:1 正方形").strip()
        output_format = str(kwargs.get("output_format", "jpeg") or "jpeg").strip().lower()
        response_format = str(kwargs.get("response_format", "url") or "url").strip()
        watermark = kwargs.get("watermark", "无水印")
        web_search = kwargs.get("联网搜索增强", "关闭")
        multi_image = kwargs.get("多图生成", "关闭")
        max_images = int(kwargs.get("最多生成张数", 4))
        multi_image_fallback = kwargs.get("multi_image_fallback", "严格报错")
        input_image = kwargs.get("input_image")
        image_url_or_base64 = str(kwargs.get("image_url_or_base64") or "").strip()
        negative_prompt = str(kwargs.get("negative_prompt") or "").strip()

        model = "doubao-seedream-5-0-260128"
        size, size_display = self.resolve_size(size_mode, size_quality, aspect_ratio)

        pbar = comfy.utils.ProgressBar(100)

        if not api_key:
            return self.black_image(), "❌ 错误：请填写有效的 API 密钥"
        if not prompt:
            return self.black_image(), "❌ 错误：提示词不能为空"

        print(f"[Tikpan-Doubao] 🚀 启动 | 模型: {model} | 尺寸: {size_display}", flush=True)

        url = "https://tikpan.com/v1/images/generations"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Tikpan-ComfyUI-DoubaoImage/OfficialFinal",
        }

        image_list, input_source_logs, truncated, original_image_count = self.build_input_image_list(
            input_image,
            image_url_or_base64,
            output_format
        )
        image_payload, image_count, image_payload_type = self.build_image_payload(image_list)

        payload = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "output_format": output_format,
            "response_format": response_format,
            "watermark": watermark == "有水印",
        }

        if web_search == "自动":
            payload["tools"] = [{"type": "web_search"}]

        if multi_image == "自动":
            payload["sequential_image_generation"] = "auto"
            payload["sequential_image_generation_options"] = {
                "max_images": max(1, min(15, max_images))
            }

        if image_payload is not None:
            payload["image"] = image_payload
            if image_count == 1:
                print("[Tikpan-Doubao] 🖼️ 已添加单张参考图", flush=True)
            else:
                print(f"[Tikpan-Doubao] 🖼️ 已添加多张参考图，共 {image_count} 张", flush=True)

        payload_preview = dict(payload)
        if "image" in payload_preview:
            payload_preview["image"] = f"<omitted {image_count} image(s), payload_type={image_payload_type}>"

        print(
            f"[Tikpan-Doubao] 📤 请求: {json.dumps(payload_preview, ensure_ascii=False)[:1500]}",
            flush=True
        )

        try:
            pbar.update(10)

            response = self.post_with_response_format_fallback(url, headers, payload)

            # 多图失败时的可选降级
            if (
                response.status_code != 200
                and image_count > 1
                and multi_image_fallback == "自动降级为首图"
                and self.is_multi_image_not_supported_error(response)
            ):
                print("[Tikpan-Doubao] ♻️ 检测到多图可能不被当前接口接受，自动降级为首图重试", flush=True)
                fallback_payload = dict(payload)
                fallback_payload["image"] = image_list[0]
                fallback_preview = dict(fallback_payload)
                fallback_preview["image"] = "<fallback to first image>"

                print(
                    f"[Tikpan-Doubao] 📤 降级重试请求: {json.dumps(fallback_preview, ensure_ascii=False)[:1500]}",
                    flush=True
                )

                response = self.post_with_response_format_fallback(url, headers, fallback_payload)

            pbar.update(50)
            print(f"[Tikpan-Doubao] 📥 响应状态: {response.status_code}", flush=True)

            if response.status_code != 200:
                try:
                    error_detail = json.dumps(response.json(), ensure_ascii=False)
                except Exception:
                    error_detail = response.text[:1000]

                return (
                    self.black_image(),
                    f"❌ API 错误 {response.status_code}\n{error_detail}"
                )

            try:
                res_json = response.json()
            except Exception:
                return (
                    self.black_image(),
                    f"❌ 接口返回非 JSON:\n{response.text[:1000]}"
                )

            print(f"[Tikpan-Doubao] 📋 响应: {json.dumps(res_json, ensure_ascii=False)[:1500]}", flush=True)

            data_list = res_json.get("data", [])
            if not data_list:
                return (
                    self.black_image(),
                    f"❌ 响应中无图像数据\n{json.dumps(res_json, ensure_ascii=False)[:1000]}"
                )

            decoded_tensors = []
            size_logs = []
            source_logs = []

            total_items = len(data_list)
            progress_start = 55
            progress_end = 95
            progress_span = max(1, total_items)

            for idx, img_data in enumerate(data_list):
                img_pil, actual_size, source_type = self.decode_one_image_item(img_data, response_format)

                if img_pil is None:
                    error_info = img_data.get("error", {})
                    if error_info:
                        print(
                            f"[Tikpan-Doubao] ⚠️ 第 {idx + 1} 张生成失败: {error_info.get('message', '未知错误')}",
                            flush=True
                        )
                    else:
                        print(f"[Tikpan-Doubao] ⚠️ 第 {idx + 1} 张图片解析失败，已跳过", flush=True)
                    continue

                tensor_img = self.pil_to_tensor(img_pil)
                decoded_tensors.append(tensor_img)
                size_logs.append(f"第{idx + 1}张: {actual_size}")
                source_logs.append(f"第{idx + 1}张来源: {source_type}")

                pbar.update(progress_start + int((idx + 1) * (progress_end - progress_start) / progress_span))

            if not decoded_tensors:
                return (
                    self.black_image(),
                    f"❌ 所有返回图片均解析失败\n{json.dumps(res_json, ensure_ascii=False)[:1500]}"
                )

            target_h = decoded_tensors[0].shape[1]
            target_w = decoded_tensors[0].shape[2]

            normalized_tensors = []
            resized_count = 0

            for t in decoded_tensors:
                if t.shape[1] != target_h or t.shape[2] != target_w:
                    t = self.resize_tensor_to(t, target_w, target_h)
                    resized_count += 1
                normalized_tensors.append(t)

            image_batch = torch.cat(normalized_tensors, dim=0)

            pbar.update(100)

            log_msg = (
                "✅ 生成成功\n"
                f"🧾 接口: /v1/images/generations\n"
                f"🧾 模型: {model}\n"
                f"📐 尺寸模式: {size_mode}\n"
                f"📐 请求尺寸: {size_display}\n"
                f"🧮 实际提交尺寸参数: {size}\n"
                f"🖼️ 返回图片数量: {len(normalized_tensors)}\n"
                f"📦 返回格式: {response_format}\n"
                f"🎨 图片格式: {output_format}\n"
                f"🧷 水印: {'开启' if watermark == '有水印' else '关闭'}\n"
                f"🖼️ 参考图数量: {image_count}\n"
                f"📏 Batch统一尺寸: {target_w}x{target_h}"
            )

            if resized_count > 0:
                log_msg += f"\n⚠️ 已自动缩放图片数量: {resized_count}"

            if web_search == "自动":
                log_msg += "\n🌐 联网搜索增强: 已开启"
            else:
                log_msg += "\n🌐 联网搜索增强: 已关闭"

            if multi_image == "自动":
                log_msg += f"\n🔄 多图生成: 自动（最大 {max_images} 张）"

            if truncated:
                log_msg += f"\n⚠️ 输入图片超出14张限制，已自动截断（原{original_image_count}张 -> 现14张）"

            for i in range(len(size_logs)):
                log_msg += f"\n  - {size_logs[i]} ({source_logs[i]})"

            return (image_batch, log_msg)

        except Exception as e:
            tb = traceback.format_exc()
            print(f"[Tikpan-Doubao] ❌ 严重错误: {e}\n{tb}", flush=True)
            return (self.black_image(), f"❌ 运行异常\n{e}\n{tb[:1000]}")


NODE_CLASS_MAPPINGS = {
    "TikpanDoubaoImageNode": TikpanDoubaoImageNode
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TikpanDoubaoImageNode": "🎨 Tikpan 豆包图像生成 (Seedream5.0)"
}
