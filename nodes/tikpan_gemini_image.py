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

# 🔐 Tikpan 官方聚合站
API_BASE_URL = "https://tikpan.com"


class TikpanGeminiImageMaxNode:
    """
    Tikpan Nano Banana 2 / 聚合图片接口适配版
    - 走 /v1/chat/completions 进行图片输出
    - 重点修复：完美支持从 markdown 和各种嵌套结构中精准提取图片
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "获取密钥请访问": (["👉 https://tikpan.com (官方授权Key获取点)"],),
                "API_密钥": ("STRING", {"default": "sk-"}),
                "修改指令": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "请参考提供的图片，生成一张高质量竖版海报，主体一致，画面精致，电影感光影。",
                    },
                ),
                "模型": (
                    ["gemini-3-pro-image-preview", "gemini-3.1-flash-image-preview", "nano-banana-2", "nano-banana-pro"],
                    {"default": "gemini-3-pro-image-preview"},
                ),
                "分辨率": (
                    ["none", "1K", "2K", "4K"],
                    {"default": "2K"},
                ),
                "画面比例": (
                    ["1:1", "16:9", "9:16", "21:9", "4:3", "3:4"],
                    {"default": "9:16"},
                ),
                "调用方式": (
                    ["gemini原生", "images_generations", "chat_completions"],
                    {"default": "gemini原生"},
                ),
                "随机种子": ("INT", {"default": 888888, "min": 0, "max": 0xffffffffffffffff}),
            },
            "optional": {
                f"参考图_{i}": ("IMAGE",) for i in range(1, 15)
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("🖼️_生成结果图", "📄_渲染日志")
    FUNCTION = "execute"
    CATEGORY = "👑 Tikpan 官方独家节点"

    def black_image(self):
        return torch.zeros((1, 512, 512, 3), dtype=torch.float32)

    def calc_pixel_size(self, 分辨率, 画面比例):
        """将 '2K'/'4K' + 比例 转换为具体像素值"""
        # 如果分辨率已经是像素格式，直接返回
        if "x" in 分辨率:
            return 分辨率

        # 基础分辨率：长边像素
        base_map = {"512": 512, "1K": 1024, "2K": 2048, "4K": 4096}
        base = base_map.get(分辨率, 2048)

        w_r, h_r = map(int, 画面比例.split(":"))

        if w_r >= h_r:
            width = base
            height = int(base * h_r / w_r)
        else:
            height = base
            width = int(base * w_r / h_r)

        width = (width // 8) * 8
        height = (height // 8) * 8

        return f"{width}x{height}"

    def tensor_to_pil(self, img_tensor):
        arr = 255.0 * img_tensor[0].cpu().numpy()
        return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGB")

    def tensor_to_base64_data_url(self, img_tensor, fmt="JPEG", quality=90):
        img = self.tensor_to_pil(img_tensor)
        buf = BytesIO()
        img.save(buf, format=fmt, quality=quality)
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        mime = "image/jpeg" if fmt.upper() == "JPEG" else "image/png"
        return f"data:{mime};base64,{b64}"

    def tensor_to_inline_data_part(self, img_tensor, fmt="JPEG", quality=95):
        """Gemini原生格式：inlineData + 驼峰字段"""
        img = self.tensor_to_pil(img_tensor)
        buf = BytesIO()
        img.save(buf, format=fmt, quality=quality)
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        mime = "image/jpeg" if fmt.upper() == "JPEG" else "image/png"
        return {
            "inlineData": {
                "mimeType": mime,
                "data": b64,
            }
        }

    def extract_image_from_gemini_response(self, res_json):
        """从 Gemini 原生响应中提取图片"""
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

                    text = part.get("text")
                    if text:
                        extracted, source = self.extract_markdown_or_dataurl_from_text(text)
                        if extracted:
                            return extracted, f"candidates.content.parts[{idx}].text:{source}"
        except Exception:
            pass

        return "", "not_found"

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

    def safe_json_text(self, obj, max_len=5000):
        try:
            s = json.dumps(obj, ensure_ascii=False)
        except Exception:
            s = str(obj)
        return s[:max_len] + ("..." if len(s) > max_len else "")

    def extract_markdown_or_dataurl_from_text(self, text):
        """
        优先提取：
        1. markdown 中的 data:image/...;base64,... (例如 ![image](data:image/jpeg;base64,xxxx))
        2. 普通 data:image/...;base64,...
        3. markdown/http 图片链接
        4. 裸 http/https 链接
        """
        if not text or not isinstance(text, str):
            return None, None

        s = text.strip()

        # 1) Markdown 包裹的 data URL
        md_dataurl_pattern = re.compile(
            r'!\[[^\]]*\]\((data:image/[^;]+;base64,[A-Za-z0-9+/=\s]+)\)',
            re.IGNORECASE | re.DOTALL
        )
        m = md_dataurl_pattern.search(s)
        if m:
            return m.group(1), "markdown_data_url"

        # 2) 直接 data URL
        dataurl_pattern = re.compile(
            r'(data:image/[^;]+;base64,[A-Za-z0-9+/=\s]+)',
            re.IGNORECASE | re.DOTALL
        )
        m = dataurl_pattern.search(s)
        if m:
            return m.group(1), "data_url"

        # 3) Markdown 包裹的 http/https
        md_http_pattern = re.compile(
            r'!\[[^\]]*\]\((https?://[^)\s]+)\)',
            re.IGNORECASE
        )
        m = md_http_pattern.search(s)
        if m:
            return m.group(1), "markdown_url"

        # 4) 裸 http/https
        http_pattern = re.compile(r'(https?://[^\s\)]+)', re.IGNORECASE)
        m = http_pattern.search(s)
        if m:
            return m.group(1), "url"

        return None, None

    def extract_image_from_response(self, res_json, session):
        candidates = []

        def add_candidate(value, source):
            if value:
                candidates.append((value, source))

        def scan_any(obj, path="root"):
            if obj is None:
                return

            if isinstance(obj, str):
                s = obj.strip()

                # 优先从 markdown / dataurl / url 中精准提取
                extracted, extracted_type = self.extract_markdown_or_dataurl_from_text(s)
                if extracted:
                    add_candidate(extracted, f"{path}:{extracted_type}")
                    return

                # 再尝试整段为 URL
                if s.startswith("http://") or s.startswith("https://"):
                    add_candidate(s, f"{path}:url")
                    return

                # 最后才把整段当可疑 base64 (需要足够长，排除普通文本)
                cleaned = self.clean_base64(s)
                if cleaned and len(cleaned) > 500:
                    add_candidate(cleaned, f"{path}:base64")
                return

            if isinstance(obj, dict):
                # 针对常见含图字段快速提取
                for key in [
                    "b64_json", "base64", "image_base64", "image",
                    "data", "url", "image_url", "output_image", "result_image",
                ]:
                    if key in obj:
                        val = obj.get(key)
                        if key in ["url", "image_url"] and isinstance(val, dict):
                            if "url" in val:
                                add_candidate(val["url"], f"{path}.{key}.url")
                        else:
                            scan_any(val, f"{path}.{key}")

                # 深入特定嵌套层级
                for key in ["choices", "message", "content", "parts", "output"]:
                    if key in obj:
                        scan_any(obj[key], f"{path}.{key}")

                # 遍历其他未知字段
                for k, v in obj.items():
                    if k not in [
                        "b64_json", "base64", "image_base64", "image", "data", "url", "image_url",
                        "output_image", "result_image", "choices", "message", "content", "parts", "output"
                    ]:
                        scan_any(v, f"{path}.{k}")
                return

            if isinstance(obj, list):
                for idx, item in enumerate(obj):
                    scan_any(item, f"{path}[{idx}]")
                return

        # 启动扫描
        scan_any(res_json)

        # 验证与下载
        for value, source in candidates:
            if not value:
                continue

            value = str(value).strip()

            # URL 下载
            if value.startswith("http://") or value.startswith("https://"):
                try:
                    img_resp = session.get(value, timeout=120, verify=False)
                    img_resp.raise_for_status()
                    return base64.b64encode(img_resp.content).decode("utf-8"), source
                except Exception:
                    continue

            # data URL / base64
            cleaned = self.clean_base64(value)
            if cleaned:
                return cleaned, source

        return "", "not_found"

    def extract_image_from_images_response(self, res_json, session):
        """从 /v1/images/generations 响应中提取图片
        标准格式: { "data": [ { "url": "...", "b64_json": "..." } ] }
        """
        try:
            data_list = res_json.get("data", [])
            if not data_list:
                # 尝试其他可能的结构
                return self.extract_image_from_response(res_json, session)

            for idx, item in enumerate(data_list):
                if not isinstance(item, dict):
                    continue

                # b64_json 直接返回
                b64 = item.get("b64_json")
                if b64:
                    cleaned = self.clean_base64(b64)
                    if cleaned:
                        return cleaned, f"data[{idx}].b64_json"

                # url 下载
                url = item.get("url")
                if url and isinstance(url, str):
                    if url.startswith("http"):
                        try:
                            img_resp = session.get(url, timeout=120, verify=False)
                            img_resp.raise_for_status()
                            return base64.b64encode(img_resp.content).decode("utf-8"), f"data[{idx}].url"
                        except Exception:
                            continue
                    # data URL
                    if url.startswith("data:image"):
                        cleaned = self.clean_base64(url)
                        if cleaned:
                            return cleaned, f"data[{idx}].url(data_url)"

            # fallback: 交给通用提取器
            return self.extract_image_from_response(res_json, session)
        except Exception:
            return self.extract_image_from_response(res_json, session)

    def build_messages(self, prompt, image_data_urls):
        if image_data_urls:
            content = [{"type": "text", "text": prompt}]
            for data_url in image_data_urls:
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": data_url
                    }
                })
            return [{"role": "user", "content": content}]
        else:
            return [{"role": "user", "content": prompt}]

    def execute(self, 获取密钥请访问, API_密钥, 修改指令, 模型, 分辨率, 画面比例, 调用方式, 随机种子=888888, **kwargs):
        pbar = comfy.utils.ProgressBar(100)
        print("[Tikpan-ChatProbe] 🚀 节点已启动...", flush=True)

        api_key = str(API_密钥 or "").strip()
        if not api_key or api_key == "sk-":
            return (self.black_image(), "❌ 请填写有效的 API 密钥")

        prompt = str(修改指令 or "").strip()
        if not prompt:
            return (self.black_image(), "❌ 修改指令不能为空")

        seed = normalize_seed(kwargs.get("seed", 随机种子), default=888888, maximum=2147483647)

        image_size_val = 分辨率 if 分辨率 in ("1K", "2K", "4K") else "2K" if 分辨率 != "none" else None

        image_data_urls = []
        gemini_image_tensors = []
        for i in range(1, 15):
            img_tensor = kwargs.get(f"参考图_{i}")
            if img_tensor is not None:
                try:
                    image_data_urls.append(self.tensor_to_base64_data_url(img_tensor, fmt="JPEG", quality=90))
                    gemini_image_tensors.append(img_tensor)
                except Exception as e:
                    print(f"[Tikpan-ChatProbe] ⚠️ 参考图_{i} 转换失败: {e}", flush=True)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Tikpan-ComfyUI-ChatProbe/2.0",
        }

        session = requests.Session()
        session.trust_env = False

        image_size_val = 分辨率 if 分辨率 in ("1K", "2K", "4K") else None

        # 🔑 根据调用方式构建不同的 payload 和 URL
        if 调用方式 == "gemini原生":
            # ===== /v1beta/models/{model}:generateContent 端点（Gemini原生）=====
            url = f"{API_BASE_URL}/v1beta/models/{模型}:generateContent"

            parts = [{"text": prompt}]
            for img_tensor in gemini_image_tensors:
                parts.append(self.tensor_to_inline_data_part(img_tensor))

            gen_config = {
                "responseModalities": ["TEXT", "IMAGE"],
            }
            image_config = {"aspectRatio": 画面比例}
            if image_size_val:
                image_config["imageSize"] = image_size_val
            gen_config["imageConfig"] = image_config
            gen_config["responseFormat"] = {"image": image_config}

            payload = {
                "contents": [{"role": "user", "parts": parts}],
                "generationConfig": gen_config,
            }

            api_name = f"/v1beta/models/{模型}:generateContent"
        elif 调用方式 == "images_generations":
            # ===== /v1/images/generations 端点 =====
            url = f"{API_BASE_URL}/v1/images/generations"
            payload = {
                "model": 模型,
                "prompt": prompt,
                "size": 画面比例,
                "n": 1,
            }
            if image_size_val:
                payload["resolution"] = image_size_val
            if image_data_urls:
                payload["image_urls"] = image_data_urls
            api_name = "/v1/images/generations"
        else:
            # ===== /v1/chat/completions 端点（兼容模式，全格式覆盖）=====
            url = f"{API_BASE_URL}/v1/chat/completions"
            messages = self.build_messages(prompt, image_data_urls)

            payload = {
                "model": 模型,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 2048,
                "modalities": ["text", "image"],
                "aspect_ratio": 画面比例,
            }

            image_config = {"aspect_ratio": 画面比例}
            if image_size_val:
                image_config["image_size"] = image_size_val
            payload["image_config"] = image_config
            payload["response_format"] = {"image": image_config}

            if image_size_val:
                payload["image_size"] = image_size_val

            gen_config = {
                "responseModalities": ["TEXT", "IMAGE"],
                "aspectRatio": 画面比例,
            }
            if image_size_val:
                gen_config["imageConfig"] = {"aspectRatio": 画面比例, "imageSize": image_size_val}
                gen_config["image_size"] = image_size_val
            payload["generationConfig"] = gen_config

            api_name = "/v1/chat/completions"

        if seed > 0:
            payload["seed"] = int(seed % 2147483647)

        print(f"[Tikpan-ChatProbe] 📋 URL: {url}", flush=True)
        print(f"[Tikpan-ChatProbe] 📋 调用方式: {调用方式} | 模型: {模型}", flush=True)
        print(f"[Tikpan-ChatProbe] 📋 分辨率: {分辨率} | 比例: {画面比例} | 参考图: {len(image_data_urls)}", flush=True)
        print(f"[Tikpan-ChatProbe] 📋 完整payload: {json.dumps(payload, ensure_ascii=False)[:3000]}", flush=True)

        try:
            pbar.update(20)

            response = session.post(
                url,
                json=payload,
                headers=headers,
                timeout=(30, 400),
                verify=False,
            )

            pbar.update(50)

            raw_text_preview = response.text[:4000]

            if response.status_code != 200:
                print(f"[Tikpan-ChatProbe] ❌ HTTP错误: {response.status_code} | {raw_text_preview}", flush=True)
                return (
                    self.black_image(),
                    f"❌ API 报错\nHTTP: {response.status_code}\n返回: {raw_text_preview}",
                )

            try:
                res_json = response.json()
            except Exception:
                print(f"[Tikpan-ChatProbe] ❌ 返回非 JSON: {raw_text_preview}", flush=True)
                return (
                    self.black_image(),
                    f"❌ 接口返回非 JSON:\n{raw_text_preview}",
                )

            pbar.update(75)

            # --- 提取图片 ---
            if 调用方式 == "gemini原生":
                image_b64, source_type = self.extract_image_from_gemini_response(res_json)
            elif 调用方式 == "images_generations":
                image_b64, source_type = self.extract_image_from_images_response(res_json, session)
            else:
                image_b64, source_type = self.extract_image_from_response(res_json, session)

            text_summary = ""
            try:
                if 调用方式 == "gemini原生":
                    candidates = res_json.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        texts = [p.get("text", "") for p in parts if "text" in p]
                        text_summary = "\n".join(texts)[:1200]
                elif isinstance(res_json, dict):
                    if "choices" in res_json and isinstance(res_json["choices"], list) and len(res_json["choices"]) > 0:
                        c0 = res_json["choices"][0]
                        if isinstance(c0, dict):
                            msg = c0.get("message")
                            if isinstance(msg, dict):
                                content = msg.get("content")
                                if isinstance(content, str):
                                    text_summary = content[:1200]
                                elif isinstance(content, list):
                                    text_summary = self.safe_json_text(content, 1200)
            except Exception:
                pass

            if not image_b64:
                return (
                    self.black_image(),
                    "⚠️ 未提取到图片。\n\n"
                    f"🧾 接口: {api_name}\n"
                    f"🧾 模型: {模型}\n"
                    f"🧾 分辨率: {分辨率} | 比例: {画面比例}\n"
                    f"🧾 参考图数量: {len(image_data_urls)}\n"
                    f"💬 附带文本回复:\n{text_summary if text_summary else '无'}\n\n"
                    f"响应预览:\n{self.safe_json_text(res_json, 3000)}"
                )

            # --- 图片解码 ---
            try:
                final_img, out_tensor, actual_width, actual_height = self.decode_image_base64(image_b64)
            except Exception as e:
                tb = traceback.format_exc()
                print(f"[Tikpan-ChatProbe] ❌ 图片解码失败: {e}\n{tb}", flush=True)
                return (
                    self.black_image(),
                    f"❌ 图片解码失败: {e}\n\n提取来源: {source_type}\n\n"
                    f"响应预览:\n{self.safe_json_text(res_json, 2000)}"
                )

            # 🔑 保底：如果API返回的图片分辨率不足，自动上采样到目标分辨率
            orig_w, orig_h = actual_width, actual_height
            final_img, out_tensor, actual_width, actual_height, was_upscaled = self.ensure_target_resolution(
                final_img, out_tensor, actual_width, actual_height, 分辨率, 画面比例
            )

            pbar.update(100)

            # --- 成功返回 ---
            requested_pixel = self.calc_pixel_size(分辨率, 画面比例) if 分辨率 != "none" else "原始"
            upscale_info = f"\n📈 上采样: {orig_w}x{orig_h} → {actual_width}x{actual_height} (Lanczos)" if was_upscaled else ""
            log_text = (
                f"✅ 渲染成功\n"
                f"🧾 接口: {api_name}\n"
                f"🧾 模型: {模型}\n"
                f"🧾 请求尺寸: {requested_pixel} ({分辨率}) | 比例: {画面比例}\n"
                f"🧾 图片提取来源: {source_type}\n"
                f"📐 实际输出尺寸: {actual_width}x{actual_height}{upscale_info}\n\n"
                f"💬 附带文本回复:\n{text_summary if text_summary else '无'}"
            )

            return (out_tensor, log_text)

        except requests.exceptions.Timeout:
            return (
                self.black_image(),
                "❌ 请求超时\n💡 建议减少参考图数量，或稍后重试。",
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
