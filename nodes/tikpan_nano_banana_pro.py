import base64
import json
import re
import traceback
from io import BytesIO

import numpy as np
import requests
import torch
import urllib3
from PIL import Image

import comfy.utils
from .tikpan_node_options import normalize_seed

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_BASE_URL = "https://tikpan.com"


class TikpanNanoBananaProNode:
    """
    🍌 Tikpan：Nano Banana Pro 图像生成节点
    模型：gemini-3-pro-image-preview
    支持：文生图、图生图、多图参考、Gemini原生/OpenAI兼容、2K/4K请求参数
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "获取密钥请访问": (["👉 https://tikpan.com (官方授权Key获取点)"],),
                "API_密钥": ("STRING", {"default": "sk-"}),
                "调用方式": (["gemini原生", "openai兼容"], {"default": "gemini原生"}),
                "模型": (
                    ["gemini-3-pro-image-preview", "gemini-3.1-flash-image-preview"],
                    {"default": "gemini-3-pro-image-preview"},
                ),
                "修改指令": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "请生成一张高质量图像，增强细节与质感，输出高分辨率结果。",
                    },
                ),
                "分辨率": (
                    ["2K", "4K", "1K", "none"],
                    {"default": "2K"},
                ),
                "画面比例": (
                    [
                        "1:1 | 1:1正方形",
                        "16:9 | 16:9宽屏",
                        "9:16 | 9:16竖屏",
                        "4:3 | 4:3标准",
                        "3:4 | 3:4竖版",
                        "21:9 | 21:9超宽",
                        "2.35:1 | 2.35:1电影",
                        "3:2 | 3:2摄影",
                        "2:3 | 2:3人像",
                    ],
                    {"default": "1:1 | 1:1正方形"},
                ),
                "随机种子": ("INT", {"default": 888888, "min": 0, "max": 0xffffffffffffffff}),
                "温度": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 2.0, "step": 0.1}),
                "最大输出Token数": (
                    "INT",
                    {
                        "default": 4096,
                        "min": 1,
                        "max": 32768,
                        "tooltip": "仅控制随图返回的文字预算；图片尺寸由“分辨率/画面比例”控制。",
                    },
                ),
                "启用谷歌搜索": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "仅 Gemini 原生模式透传 google_search 工具；图像任务通常保持关闭。",
                    },
                ),
            },
            "optional": {
                f"参考图_{i}": ("IMAGE",) for i in range(1, 15)
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("🖼️_生成结果图", "📄_渲染日志")
    FUNCTION = "execute"
    CATEGORY = "👑 Tikpan 官方独家节点"

    def parse_aspect_ratio(self, ratio_str):
        return str(ratio_str).split(" | ")[0].strip()

    def calc_pixel_size(self, 分辨率, 画面比例):
        """将 '2K'/'4K' + 比例 转换为具体像素值，如 '1152x2048'"""
        aspect_ratio = self.parse_aspect_ratio(画面比例)
        w_r, h_r = aspect_ratio.split(":")

        # 如果分辨率已经是像素格式，直接返回
        if "x" in 分辨率:
            return 分辨率

        # 基础分辨率：长边像素
        base_map = {"512": 512, "1K": 1024, "2K": 2048, "4K": 4096}
        base = base_map.get(分辨率, 2048)

        w_ratio = float(w_r)
        h_ratio = float(h_r)

        if w_ratio >= h_ratio:
            # 横向或正方形：宽=base
            width = base
            height = int(base * h_ratio / w_ratio)
        else:
            # 竖向：高=base
            height = base
            width = int(base * w_ratio / h_ratio)

        # 对齐到8的倍数
        width = (width // 8) * 8
        height = (height // 8) * 8

        return f"{width}x{height}"

    def black_image(self):
        return torch.zeros((1, 512, 512, 3), dtype=torch.float32)

    def tensor_to_pil(self, img_tensor):
        arr = 255.0 * img_tensor[0].cpu().numpy()
        return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGB")

    def tensor_to_inline_data_part(self, img_tensor, fmt="JPEG", quality=95):
        img = self.tensor_to_pil(img_tensor)
        buf = BytesIO()
        img.save(buf, format=fmt, quality=quality)
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        mime = "image/jpeg" if fmt.upper() == "JPEG" else "image/png"
        return {
            "inlineData": {
                "mimeType": mime,
                "data": b64
            }
        }

    def tensor_to_data_url(self, img_tensor, fmt="JPEG", quality=95):
        img = self.tensor_to_pil(img_tensor)
        buf = BytesIO()
        img.save(buf, format=fmt, quality=quality)
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        mime = "image/jpeg" if fmt.upper() == "JPEG" else "image/png"
        return f"data:{mime};base64,{b64}"

    def ensure_target_resolution(self, final_img, out_tensor, actual_width, actual_height, 分辨率, 画面比例):
        """如果API返回的图片分辨率低于请求分辨率，进行Lanczos高质量上采样到目标分辨率"""
        if 分辨率 == "none":
            return final_img, out_tensor, actual_width, actual_height, False

        target_pixel = self.calc_pixel_size(分辨率, 画面比例)
        target_w, target_h = map(int, target_pixel.split("x"))

        # 如果实际分辨率已经达到或超过目标，不需要上采样
        if actual_width >= target_w and actual_height >= target_h:
            return final_img, out_tensor, actual_width, actual_height, False

        # Lanczos 高质量上采样
        upscaled_img = final_img.resize((target_w, target_h), Image.LANCZOS)
        img_np = np.array(upscaled_img).astype(np.float32) / 255.0
        upscaled_tensor = torch.from_numpy(img_np)[None, ...]

        return upscaled_img, upscaled_tensor, target_w, target_h, True

    def clean_base64(self, raw_data):
        if not raw_data:
            return ""

        raw_data = str(raw_data).strip()

        if raw_data.startswith("data:image"):
            raw_data = raw_data.split("base64,", 1)[-1]

        b64_clean = re.sub(r"[^A-Za-z0-9+/=]", "", raw_data)
        if not b64_clean:
            return ""

        missing_padding = len(b64_clean) % 4
        if missing_padding:
            b64_clean += "=" * (4 - missing_padding)

        return b64_clean

    def decode_image_base64(self, b64_data):
        cleaned = self.clean_base64(b64_data)
        if not cleaned:
            raise ValueError("未提取到有效的 base64 图像数据")

        img_raw = base64.b64decode(cleaned)
        final_img = Image.open(BytesIO(img_raw)).convert("RGB")
        actual_width, actual_height = final_img.size
        img_np = np.array(final_img).astype(np.float32) / 255.0
        out_tensor = torch.from_numpy(img_np)[None, ...]
        return final_img, out_tensor, actual_width, actual_height

    def safe_json_text(self, obj, max_len=5000):
        try:
            s = json.dumps(obj, ensure_ascii=False)
        except Exception:
            s = str(obj)
        return s[:max_len] + ("..." if len(s) > max_len else "")

    def extract_markdown_or_dataurl_from_text(self, text):
        if not text or not isinstance(text, str):
            return None, None

        s = text.strip()

        md_dataurl_pattern = re.compile(
            r'!\[([^\]]*)\]\((data:image/[^;]+;base64,[A-Za-z0-9+/=\s]+)\)',
            re.IGNORECASE | re.DOTALL
        )
        m = md_dataurl_pattern.search(s)
        if m:
            return m.group(2), "markdown_data_url"

        dataurl_pattern = re.compile(
            r'(data:image/[^;]+;base64,[A-Za-z0-9+/=\s]+)',
            re.IGNORECASE | re.DOTALL
        )
        m = dataurl_pattern.search(s)
        if m:
            return m.group(1), "data_url"

        md_http_pattern = re.compile(
            r'!\[([^\]]*)\]\((https?://[^\s\)]+)\)',
            re.IGNORECASE
        )
        m = md_http_pattern.search(s)
        if m:
            return m.group(2), "markdown_url"

        http_pattern = re.compile(r'(https?://[^\s\)]+)', re.IGNORECASE)
        m = http_pattern.search(s)
        if m:
            return m.group(1), "url"

        return None, None

    def extract_image_from_chat_response(self, res_json, session):
        candidates = []

        def add_candidate(value, source):
            if value:
                candidates.append((value, source))

        def scan_any(obj, path="root"):
            if obj is None:
                return

            if isinstance(obj, str):
                extracted, extracted_type = self.extract_markdown_or_dataurl_from_text(obj)
                if extracted:
                    add_candidate(extracted, f"{path}:{extracted_type}")
                    return

                s = obj.strip()
                if s.startswith("http://") or s.startswith("https://"):
                    add_candidate(s, f"{path}:url")
                    return

                cleaned = self.clean_base64(s)
                if cleaned and len(cleaned) > 500:
                    add_candidate(cleaned, f"{path}:base64")
                return

            if isinstance(obj, dict):
                for key in [
                    "b64_json",
                    "base64",
                    "image_base64",
                    "image",
                    "data",
                    "url",
                    "image_url",
                    "output_image",
                    "result_image",
                ]:
                    if key in obj:
                        val = obj.get(key)
                        if key in ["url", "image_url"] and isinstance(val, dict):
                            if "url" in val:
                                add_candidate(val["url"], f"{path}.{key}.url")
                        else:
                            scan_any(val, f"{path}.{key}")

                for k, v in obj.items():
                    scan_any(v, f"{path}.{k}")
                return

            if isinstance(obj, list):
                for idx, item in enumerate(obj):
                    scan_any(item, f"{path}[{idx}]")

        scan_any(res_json)

        for value, source in candidates:
            value = str(value).strip()

            if value.startswith("http://") or value.startswith("https://"):
                try:
                    img_resp = session.get(value, timeout=120, verify=False)
                    img_resp.raise_for_status()
                    return base64.b64encode(img_resp.content).decode("utf-8"), source
                except Exception:
                    continue

            cleaned = self.clean_base64(value)
            if cleaned:
                return cleaned, source

        return "", "not_found"

    def extract_image_from_gemini_response(self, res_json):
        try:
            candidates = res_json.get("candidates", [])
            for cand in candidates:
                content = cand.get("content", {})
                parts = content.get("parts", [])

                for idx, part in enumerate(parts):
                    for key in ["inlineData", "inline_data"]:
                        inline_data = part.get(key)
                        if inline_data and isinstance(inline_data, dict):
                            data = inline_data.get("data")
                            if data:
                                return data, f"candidates.content.parts[{idx}].{key}.data"

                    for key in ["data", "image", "image_base64"]:
                        val = part.get(key)
                        if isinstance(val, str) and len(val) > 100:
                            cleaned = self.clean_base64(val)
                            if cleaned:
                                return cleaned, f"candidates.content.parts[{idx}].{key}"

                    text = part.get("text")
                    if text:
                        extracted, source = self.extract_markdown_or_dataurl_from_text(text)
                        if extracted:
                            return extracted, f"candidates.content.parts[{idx}].text:{source}"
        except Exception:
            pass

        return "", "not_found"

    def build_gemini_payload(self, prompt, image_tensors, 分辨率, 画面比例, seed, 温度, 启用谷歌搜索=False):
        aspect_ratio = self.parse_aspect_ratio(画面比例)

        parts = [{"text": prompt}]

        for img_tensor in image_tensors:
            parts.append(self.tensor_to_inline_data_part(img_tensor))

        # REST examples use responseFormat.image; SDK examples expose the same
        # controls as imageConfig, so keep both for Tikpan gateway compatibility.
        image_size_val = 分辨率 if 分辨率 in ("1K", "2K", "4K") else None

        image_config = {"aspectRatio": aspect_ratio}
        if image_size_val:
            image_config["imageSize"] = image_size_val

        generation_config = {
            "responseModalities": ["TEXT", "IMAGE"],
            "responseFormat": {"image": image_config},
            "imageConfig": image_config,
        }

        if 温度 is not None:
            generation_config["temperature"] = float(温度)

        if seed > 0:
            generation_config["seed"] = int(seed % 2147483647)

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": parts
                }
            ],
            "generationConfig": generation_config,
        }
        if 启用谷歌搜索:
            payload["tools"] = [{"google_search": {}}]

        return payload

    def build_chat_payload(self, model, prompt, image_tensors, 分辨率, 画面比例, seed, 温度, max_tokens):
        aspect_ratio = self.parse_aspect_ratio(画面比例)
        image_size_val = 分辨率 if 分辨率 in ("1K", "2K", "4K") else None

        if image_tensors:
            content = [{"type": "text", "text": prompt}]
            for img_tensor in image_tensors:
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": self.tensor_to_data_url(img_tensor)
                    }
                })
            messages = [{"role": "user", "content": content}]
        else:
            messages = [{"role": "user", "content": prompt}]

        image_config = {"aspect_ratio": aspect_ratio}
        if image_size_val:
            image_config["image_size"] = image_size_val

        payload = {
            "model": model,
            "messages": messages,
            "temperature": float(温度),
            "max_tokens": int(max_tokens),
            "modalities": ["text", "image"],
            "image_config": image_config,
            "response_format": {"image": image_config},
        }

        if seed > 0:
            payload["seed"] = int(seed % 2147483647)

        return payload

    def extract_text_summary(self, res_json, 调用方式):
        try:
            if 调用方式 == "openai兼容":
                choices = res_json.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "")
                    if isinstance(content, str):
                        return content[:1200]
                    return self.safe_json_text(content, 1200)
            else:
                candidates = res_json.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    texts = []
                    for p in parts:
                        if "text" in p:
                            texts.append(str(p["text"]))
                    return "\n".join(texts)[:1200]
        except Exception:
            pass
        return ""

    def execute(
        self,
        获取密钥请访问,
        API_密钥,
        调用方式,
        模型,
        修改指令,
        分辨率,
        画面比例,
        随机种子=888888,
        温度=0.7,
        最大输出Token数=4096,
        **kwargs
    ):
        pbar = comfy.utils.ProgressBar(100)
        print("[Tikpan-NanoBananaPro] 🍌 开始请求...", flush=True)

        api_key = str(API_密钥 or "").strip()
        if not api_key or api_key == "sk-":
            return (self.black_image(), "❌ 请填写有效的 API 密钥")

        prompt = str(修改指令 or "").strip()
        if not prompt:
            return (self.black_image(), "❌ 修改指令不能为空")

        随机种子 = normalize_seed(kwargs.get("seed", 随机种子), default=888888, maximum=2147483647)
        最大输出Token数 = int(kwargs.get("max_tokens", kwargs.get("最大Token数", 最大输出Token数)) or 4096)
        启用谷歌搜索 = bool(kwargs.get("启用谷歌搜索", False))
        aspect_ratio = self.parse_aspect_ratio(画面比例)

        image_tensors = []
        for i in range(1, 15):
            img_tensor = kwargs.get(f"参考图_{i}")
            if img_tensor is not None:
                image_tensors.append(img_tensor)

        session = requests.Session()
        session.trust_env = False

        try:
            pbar.update(15)

            if 调用方式 == "gemini原生":
                url = f"{API_BASE_URL}/v1beta/models/{模型}:generateContent"
                payload = self.build_gemini_payload(prompt, image_tensors, 分辨率, 画面比例, 随机种子, 温度, 启用谷歌搜索)
                api_name = f"/v1beta/models/{模型}:generateContent"
            else:
                url = f"{API_BASE_URL}/v1/chat/completions"
                payload = self.build_chat_payload(模型, prompt, image_tensors, 分辨率, 画面比例, 随机种子, 温度, 最大输出Token数)
                api_name = "/v1/chat/completions"

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "Tikpan-ComfyUI-NanoBananaPro/Final",
            }

            print(f"[Tikpan-NanoBananaPro] URL: {url}", flush=True)
            print(f"[Tikpan-NanoBananaPro] 调用方式: {调用方式}", flush=True)
            print(f"[Tikpan-NanoBananaPro] 模型: {模型}", flush=True)
            print(f"[Tikpan-NanoBananaPro] 参考图数量: {len(image_tensors)}", flush=True)
            print(f"[Tikpan-NanoBananaPro] 分辨率: {分辨率} | 比例: {aspect_ratio}", flush=True)
            if 调用方式 == "gemini原生":
                print(f"[Tikpan-NanoBananaPro] generationConfig: {json.dumps(payload.get('generationConfig', {}), ensure_ascii=False)}", flush=True)
            else:
                print(f"[Tikpan-NanoBananaPro] image_config: {json.dumps(payload.get('image_config', {}), ensure_ascii=False)}", flush=True)
            print(f"[Tikpan-NanoBananaPro] Payload预览: {self.safe_json_text(payload, 6000)}", flush=True)

            response = session.post(
                url,
                json=payload,
                headers=headers,
                timeout=(30, 400),
                verify=False,
            )

            pbar.update(50)

            raw_text_preview = response.text[:5000]
            if response.status_code != 200:
                return (
                    self.black_image(),
                    f"❌ API 报错\nHTTP: {response.status_code}\n返回:\n{raw_text_preview}"
                )

            try:
                res_json = response.json()
            except Exception:
                return (
                    self.black_image(),
                    f"❌ 接口返回非 JSON:\n{raw_text_preview}"
                )

            print(f"[Tikpan-NanoBananaPro] 响应预览: {self.safe_json_text(res_json, 8000)}", flush=True)

            pbar.update(75)

            if 调用方式 == "gemini原生":
                image_b64, source_type = self.extract_image_from_gemini_response(res_json)
            else:
                image_b64, source_type = self.extract_image_from_chat_response(res_json, session)

            text_summary = self.extract_text_summary(res_json, 调用方式)

            if not image_b64:
                return (
                    self.black_image(),
                    "⚠️ 未提取到图片。\n\n"
                    f"🧾 接口: {api_name}\n"
                    f"🧾 模型: {模型}\n"
                    f"🧾 请求尺寸: {self.calc_pixel_size(分辨率, 画面比例)} ({分辨率})\n"
                    f"🧾 画面比例: {aspect_ratio}\n"
                    f"🧾 参考图数量: {len(image_tensors)}\n"
                    f"💬 附带文本回复:\n{text_summary if text_summary else '无'}\n\n"
                    f"响应预览:\n{self.safe_json_text(res_json, 3000)}"
                )

            try:
                final_img, out_tensor, actual_width, actual_height = self.decode_image_base64(image_b64)
            except Exception as e:
                tb = traceback.format_exc()
                return (
                    self.black_image(),
                    f"❌ 提取到疑似图片数据，但解码失败: {str(e)}\n"
                    f"来源: {source_type}\n\n"
                    f"异常详情:\n{tb}\n\n"
                    f"响应预览:\n{self.safe_json_text(res_json, 3000)}"
                )

            # 🔑 核心修复：如果API返回的图片分辨率不足，自动上采样到目标分辨率
            orig_w, orig_h = actual_width, actual_height
            final_img, out_tensor, actual_width, actual_height, was_upscaled = self.ensure_target_resolution(
                final_img, out_tensor, actual_width, actual_height, 分辨率, 画面比例
            )

            pbar.update(100)

            requested_pixel = self.calc_pixel_size(分辨率, 画面比例) if 分辨率 != "none" else "原始"
            upscale_info = f"\n📈 上采样: {orig_w}x{orig_h} → {actual_width}x{actual_height} (Lanczos)" if was_upscaled else ""
            log_text = (
                "✅ 渲染成功\n"
                f"🧾 接口: {api_name}\n"
                f"🧾 模型: {模型}\n"
                f"🧾 请求尺寸: {requested_pixel} ({分辨率}) | 比例: {aspect_ratio}\n"
                f"🧾 图片提取来源: {source_type}\n"
                f"📐 实际输出尺寸: {actual_width}x{actual_height}{upscale_info}\n\n"
                f"💬 附带文本回复:\n{text_summary if text_summary else '无'}"
            )

            return (out_tensor, log_text)

        except requests.exceptions.Timeout:
            return (
                self.black_image(),
                "❌ 请求超时\n💡 建议检查网络或稍后重试。"
            )
        except requests.exceptions.ConnectionError as e:
            return (self.black_image(), f"❌ 连接错误: {str(e)[:500]}")
        except requests.exceptions.RequestException as e:
            return (self.black_image(), f"❌ 网络请求异常: {str(e)[:500]}")
        except Exception as e:
            tb = traceback.format_exc()
            print(tb, flush=True)
            return (self.black_image(), f"❌ 节点运行异常: {str(e)}\n{tb[:2000]}")
        finally:
            try:
                session.close()
            except Exception:
                pass
