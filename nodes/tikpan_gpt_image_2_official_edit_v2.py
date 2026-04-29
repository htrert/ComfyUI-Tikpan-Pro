import math
import time
import base64
import urllib3
from io import BytesIO

import numpy as np
import requests
import torch
from PIL import Image, ImageFile
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import comfy.utils

# 避免部分图片截断时报错
ImageFile.LOAD_TRUNCATED_IMAGES = True

# 屏蔽 https verify=False 的告警
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_BASE_URL = "https://tikpan.com"


class TikpanGptImage2OfficialEditV2:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "💎_源头拿货价福利_💎": (
                    ["🔥 0.6元 RMB 兑换 👉 1美元余额 | 绝对全网底价"],
                ),
                "获取密钥请访问": (
                    ["👉 https://tikpan.com (官方授权Key获取点)"],
                ),
                "API_密钥": ("STRING", {"default": "sk-"}),

                "参考底图": ("IMAGE",),
                "绘画指令": ("STRING", {
                    "multiline": True,
                    "default": "请描述你希望生成的画面..."
                }),
                "模型": (["gpt-image-2"], {"default": "gpt-image-2"}),

                "分辨率档位": (
                    ["1K (标准修图)", "2K (极致高清)", "4K (官方最大上限)"],
                    {"default": "1K (标准修图)"}
                ),

                "画面比例": (
                    ["Auto (参考原图比例)", "1:1", "4:3", "3:4", "16:9", "9:16", "21:9", "9:21"],
                    {"default": "Auto (参考原图比例)"}
                ),
            },
            "optional": {
                "跳过错误": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "开启后，若网络异常、余额不足或接口异常，将返回黑图，防止工作流中断。"
                }),
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("🖼️_生成结果图", "📄_渲染日志")
    FUNCTION = "generate_image"
    CATEGORY = "👑 Tikpan 官方独家节点"

    def generate_image(self, **kwargs):
        start_time = time.time()

        api_key = (kwargs.get("API_密钥") or "").strip()
        prompt = (kwargs.get("绘画指令") or "").strip()
        image_tensor = kwargs.get("参考底图")
        model = kwargs.get("模型", "gpt-image-2")
        tier = kwargs.get("分辨率档位", "1K (标准修图)")
        aspect_ratio = kwargs.get("画面比例", "Auto (参考原图比例)")
        skip_error = kwargs.get("跳过错误", False)

        pbar = comfy.utils.ProgressBar(100)
        safe_w, safe_h = 1024, 1024

        try:
            # 1) 基础校验
            if not api_key or api_key == "sk-":
                return (self.black_image(1024, 1024), "❌ 错误：API 密钥为空")
            if not prompt:
                return (self.black_image(1024, 1024), "❌ 错误：绘画指令不能为空")

            img_np = self.normalize_image(image_tensor)
            ref_h, ref_w = img_np.shape[0], img_np.shape[1]

            batch = int(image_tensor.shape[0]) if hasattr(image_tensor, "shape") and len(image_tensor.shape) > 0 else 1
            if batch > 1:
                print(f"[Tikpan-Base] ⚠️ 检测到 batch={batch}，仅处理第 1 张图片", flush=True)

            if model not in {"gpt-image-2"}:
                model = "gpt-image-2"

            print(f"[Tikpan-Base] 🚀 开始执行图像生成", flush=True)
            pbar.update(10)

            session = self.create_session()

            # 2) 计算分辨率
            width, height, target_res = self.compute_target_resolution(
                ref_w=ref_w, ref_h=ref_h, tier=tier, aspect_ratio=aspect_ratio
            )
            safe_w, safe_h = width, height
            print(f"[Tikpan-Base] 📐 输出尺寸: {target_res}", flush=True)
            pbar.update(25)

            # 3) 极简预处理
            img_arr = (img_np * 255.0).astype(np.uint8)
            pil_img = Image.fromarray(img_arr).convert("RGB")
            pil_img = pil_img.resize((width, height), Image.Resampling.LANCZOS)

            buf = BytesIO()
            pil_img.save(buf, format="PNG", optimize=True)
            image_bytes = buf.getvalue()

            size_mb = len(image_bytes) / (1024 * 1024)
            print(f"[Tikpan-Base] 📦 上传底图体积: {size_mb:.2f} MB", flush=True)
            if size_mb > 8:
                print(f"[Tikpan-Base] ⚠️ 警告：上传图片体积较大 ({size_mb:.2f} MB)，弱网环境下可能导致上传超时", flush=True)
            pbar.update(40)

            # 4) 超时与请求组装
            connect_timeout, read_timeout = self.compute_timeout_by_tier(tier)
            print(f"[Tikpan-Base] ⏱️ 网络策略: 握手/上传缓冲 {connect_timeout}s | 最大等待 {read_timeout}s", flush=True)

            headers = {
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "Tikpan-ComfyUI-BaseNode/UltraStable"
            }

            files = {"image": ("base_image.png", image_bytes, "image/png")}

            # 极简兼容 payload
            payload = {
                "model": model,
                "prompt": prompt,
                "size": target_res
            }
            print("[Tikpan-Base] 🧷 渠道模式: 极简全兼容模式 (仅发送 model/prompt/size)", flush=True)

            url = f"{API_BASE_URL}/v1/images/edits"
            pbar.update(50)

            # 5) 发起请求
            try:
                response = session.post(
                    url,
                    headers=headers,
                    files=files,
                    data=payload,
                    timeout=(connect_timeout, read_timeout),
                    verify=False
                )
            except requests.exceptions.ConnectTimeout:
                msg = "❌ 网络连接超时：无法连接到服务器，请检查网络。"
                print(f"[Tikpan-Base] {msg}", flush=True)
                if not skip_error:
                    raise RuntimeError(msg)
                return (self.black_image(width, height), msg)
            except requests.exceptions.ReadTimeout:
                msg = "❌ 服务器响应超时：生成耗时过久，请稍后重试。"
                print(f"[Tikpan-Base] {msg}", flush=True)
                if not skip_error:
                    raise RuntimeError(msg)
                return (self.black_image(width, height), msg)
            except requests.exceptions.RequestException as e:
                err_text = str(e).lower()
                if "write operation timed out" in err_text:
                    msg = "❌ 图片上传超时：当前网络过慢，建议稍后重试。"
                elif "read timed out" in err_text:
                    msg = "❌ 服务器响应超时：生成耗时过久，请稍后重试。"
                elif "connect timeout" in err_text or "connection timed out" in err_text:
                    msg = "❌ 网络连接超时：无法连接到服务器，请检查网络。"
                else:
                    msg = f"❌ 网络请求异常：{str(e)}"
                print(f"[Tikpan-Base] {msg}", flush=True)
                if not skip_error:
                    raise RuntimeError(msg)
                return (self.black_image(width, height), msg)

            pbar.update(70)

            # 6) HTTP 非 200 处理
            if response.status_code != 200:
                err_text = self.safe_response_text(response)
                err_lower = err_text.lower()
                msg = f"❌ 接口请求失败 | HTTP {response.status_code} | {err_text}"

                if response.status_code == 413:
                    msg = "❌ 上传失败：图片体积过大，被服务器拦截。建议降低分辨率后重试。"
                elif response.status_code in {408, 504}:
                    msg = "❌ 网络超时：服务器网关等待过久，请稍后重试或降低分辨率。"
                elif "insufficient_quota" in err_lower:
                    msg = "❌ 生成失败：API 余额不足，请充值后重试。"
                elif "unknown_parameter" in err_lower or "unknown parameter" in err_lower or "unrecognized request argument" in err_lower:
                    msg = "❌ 生成失败：当前渠道不兼容请求参数。"
                elif "invalid_request_error" in err_lower:
                    msg = "❌ 生成失败：请求参数、底图或提示词不被上游接受。"
                elif "rate limit" in err_lower or "too many requests" in err_lower:
                    msg = "❌ 生成失败：请求过于频繁，请稍后重试。"

                print(f"[Tikpan-Base] {msg}", flush=True)
                if not skip_error:
                    raise RuntimeError(msg)
                return (self.black_image(width, height), msg)

            # 7) JSON 解析与 body error
            try:
                res_json = response.json()
            except Exception:
                msg = f"❌ 接口返回非 JSON 数据：{self.safe_response_text(response)}"
                print(f"[Tikpan-Base] {msg}", flush=True)
                if not skip_error:
                    raise RuntimeError(msg)
                return (self.black_image(width, height), msg)

            if isinstance(res_json, dict) and res_json.get("error"):
                err_obj = res_json.get("error")
                err_text = err_obj.get("message") if isinstance(err_obj, dict) else str(err_obj)
                err_lower = err_text.lower()
                msg = f"❌ 上游接口拒绝：{err_text}"

                if "insufficient_quota" in err_lower:
                    msg = "❌ 生成失败：API 余额不足。"
                elif "unknown_parameter" in err_lower or "unknown parameter" in err_lower or "unrecognized request argument" in err_lower:
                    msg = "❌ 生成失败：当前渠道不兼容请求参数。"
                elif "invalid_request_error" in err_lower:
                    msg = "❌ 生成失败：请求参数、底图或提示词不被上游接受。"

                print(f"[Tikpan-Base] {msg}", flush=True)
                if not skip_error:
                    raise RuntimeError(msg)
                return (self.black_image(width, height), msg)

            pbar.update(85)

            # 8) 提取与加载结果图
            img_raw, raw_type = self.extract_image_result(res_json)
            if not img_raw:
                msg = "⚠️ 未找到有效图像数据，可能是审核拦截或渠道返回结构异常。"
                print(f"[Tikpan-Base] {msg}", flush=True)
                if not skip_error:
                    raise RuntimeError(msg)
                return (self.black_image(width, height), msg)

            final_pil = self.load_result_image(session, img_raw, raw_type).convert("RGB")
            final_np = np.array(final_pil).astype(np.float32) / 255.0
            final_tensor = torch.from_numpy(final_np)[None, ...]

            cost_time = round(time.time() - start_time, 2)
            log_text = f"✅ 生成成功 | 模型: {model} | 模式: 极简兼容 | 尺寸: {target_res} | 耗时: {cost_time}s"
            print(f"[Tikpan-Base] {log_text}", flush=True)
            pbar.update(100)

            return (final_tensor, log_text)

        except Exception as e:
            err_msg = f"❌ 运行故障 [{type(e).__name__}]: {str(e)}"
            print(f"[Tikpan ERROR] {err_msg}", flush=True)

            try:
                if image_tensor is not None and hasattr(image_tensor, "shape") and len(image_tensor.shape) == 4:
                    safe_w = int(image_tensor.shape[2])
                    safe_h = int(image_tensor.shape[1])
            except Exception:
                pass

            if not skip_error:
                raise
            return (self.black_image(safe_w, safe_h), err_msg)

    def create_session(self):
        session = requests.Session()
        session.trust_env = False
        retries = Retry(
            total=3,
            connect=3,
            read=0,
            status=0,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=frozenset(["HEAD", "GET", "OPTIONS"])
        )
        adapter = HTTPAdapter(max_retries=retries, pool_connections=20, pool_maxsize=20)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def compute_target_resolution(self, ref_w, ref_h, tier, aspect_ratio):
        target_pixels = 1048576
        if "2K" in tier:
            target_pixels = 4194304
        elif "4K" in tier:
            target_pixels = 8294400

        if "Auto" in aspect_ratio:
            final_ratio = ref_w / ref_h if ref_h > 0 else 1.0
        else:
            try:
                wr, hr = aspect_ratio.split(":")
                final_ratio = float(wr) / float(hr)
            except Exception:
                final_ratio = 1.0

        final_ratio = max(0.05, min(final_ratio, 20.0))
        h_calc = math.sqrt(target_pixels / final_ratio)
        w_calc = h_calc * final_ratio

        max_side, min_side = 3840, 256
        if max(w_calc, h_calc) > max_side:
            scale = max_side / max(w_calc, h_calc)
            w_calc *= scale
            h_calc *= scale

        if min(w_calc, h_calc) < min_side:
            scale = min_side / min(w_calc, h_calc)
            w_calc *= scale
            h_calc *= scale

        width = max(256, int(round(w_calc / 16.0)) * 16)
        height = max(256, int(round(h_calc / 16.0)) * 16)
        width = min(width, max_side)
        height = min(height, max_side)
        width = max(256, (width // 16) * 16)
        height = max(256, (height // 16) * 16)

        return width, height, f"{width}x{height}"

    def compute_timeout_by_tier(self, tier):
        if "4K" in tier:
            return 60, 600
        elif "2K" in tier:
            return 45, 480
        return 30, 300

    def normalize_image(self, image_tensor):
        if image_tensor is None:
            raise ValueError("未检测到底图输入")
        if not hasattr(image_tensor, "shape") or len(image_tensor.shape) != 4:
            raise ValueError(f"底图维度异常，期望 [B,H,W,C]，实际为: {getattr(image_tensor, 'shape', None)}")
        if image_tensor.shape[0] < 1:
            raise ValueError("底图 batch 为空，无法处理")
            
        img_np = image_tensor[0].cpu().numpy()
        if img_np.ndim != 3:
            raise ValueError(f"底图格式异常，期望单张图片为 [H,W,C]，实际为: {img_np.shape}")
            
        img_np = np.nan_to_num(img_np, nan=0.0, posinf=1.0, neginf=0.0).astype(np.float32)
        if img_np.size == 0:
            raise ValueError("底图数据为空，无法处理")
            
        if img_np.max() > 1.0:
            img_np = img_np / 255.0
            
        img_np = np.clip(img_np, 0.0, 1.0)
        
        if img_np.shape[-1] == 1:
            img_np = np.repeat(img_np, 3, axis=-1)
        elif img_np.shape[-1] >= 4:
            img_np = img_np[..., :3]
        elif img_np.shape[-1] != 3:
            raise ValueError(f"底图通道数异常，期望 1/3/4 通道，实际为: {img_np.shape[-1]}")
            
        return img_np

    def safe_response_text(self, response, max_len=1000):
        try: return response.text[:max_len].strip()
        except: return "无法解析上游响应"

    def extract_image_result(self, res_json):
        data = res_json.get("data", [])
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
            item = data[0]
            img_raw = item.get("url") or item.get("b64_json") or item.get("image_base64")
            if img_raw: return img_raw, "url" if item.get("url") else "b64"

        if isinstance(res_json.get("result"), dict):
            item = res_json["result"]
            img_raw = item.get("url") or item.get("b64_json") or item.get("image_base64")
            if img_raw: return img_raw, "url" if item.get("url") else "b64"

        img_raw = res_json.get("url") or res_json.get("b64_json") or res_json.get("image_base64")
        if img_raw: return img_raw, "url" if res_json.get("url") else "b64"

        return None, None

    def load_result_image(self, session, img_raw, raw_type):
        if raw_type == "url" or str(img_raw).startswith("http"):
            r = session.get(img_raw, timeout=(15, 120), verify=False)
            r.raise_for_status()
            return Image.open(BytesIO(r.content))

        try:
            b64_clean = img_raw.split("base64,")[-1] if isinstance(img_raw, str) else img_raw
            image_bytes = base64.b64decode(b64_clean)
            return Image.open(BytesIO(image_bytes))
        except Exception as e:
            raise RuntimeError(f"结果图解码失败：{str(e)}")

    def black_image(self, w, h):
        w = max(1, int(w))
        h = max(1, int(h))
        return torch.zeros((1, h, w, 3), dtype=torch.float32)