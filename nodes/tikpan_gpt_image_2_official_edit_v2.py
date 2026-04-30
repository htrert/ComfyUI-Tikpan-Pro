import uuid
import math
import base64
import torch
import numpy as np
from io import BytesIO
from PIL import Image, ImageOps
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import traceback
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_HOST = "https://tikpan.com"


class TikpanGptImage2OfficialEditV2:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "💎_源头拿货价福利_💎": (["🔥 0.6元RMB兑1美元余额全网底价"],),
                "获取密钥请访问": (["👉 https://tikpan.com 官方授权获取Key"],),
                "API_密钥": ("STRING", {"default": "sk-"}),
                "主图像": ("IMAGE",),
                "编辑指令": ("STRING", {
                    "multiline": True,
                    "default": "请根据要求编辑图像；如果提供了遮罩，仅修改遮罩区域并尽量保持未遮罩区域不变。"
                }),
                "生成张数": ("INT", {"default": 1, "min": 1, "max": 10, "step": 1}),
                "分辨率档位": (["Auto", "1K", "2K", "4K"], {"default": "2K"}),
                "画面比例": (["Auto", "1:1", "16:9", "9:16", "4:3", "3:4", "21:9", "9:21"], {"default": "Auto"}),
                "画质": (["auto", "low", "medium", "high"], {"default": "medium"}),
                "背景模式": (["auto", "opaque", "transparent"], {"default": "auto"}),
                "遮罩反相": ("BOOLEAN", {"default": False}),
                "提示增强": ("BOOLEAN", {"default": True}),
                "超时秒数": ("INT", {"default": 300, "min": 30, "max": 1800, "step": 10}),
            },
            "optional": {
                "参考图1": ("IMAGE",),
                "参考图2": ("IMAGE",),
                "参考图3": ("IMAGE",),
                "参考图4": ("IMAGE",),
                "遮罩掩码": ("MASK",),
                "跳过错误": ("BOOLEAN", {"default": False}),
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("编辑结果", "渲染日志")
    FUNCTION = "edit_image"
    CATEGORY = "👑 Tikpan 官方独家节点"

    def edit_image(self, **kwargs):
        w, h = 1024, 1024
        skip_error = kwargs.get("跳过错误", False)

        try:
            api_key = kwargs.get("API_密钥")
            if not api_key or not str(api_key).startswith("sk-"):
                return (self.black_out(), "❌ API Key 格式错误")

            main_img = kwargs.get("主图像")
            if main_img is None:
                return (self.black_out(), "❌ 请提供主图像")

            mask_t = kwargs.get("遮罩掩码")
            prompt = kwargs.get("编辑指令") or ""
            n = int(kwargs.get("生成张数", 1))
            res_tier = kwargs.get("分辨率档位", "2K")
            aspect = kwargs.get("画面比例", "Auto")
            quality = kwargs.get("画质", "medium")
            bg = kwargs.get("背景模式", "auto")
            invert_mask = kwargs.get("遮罩反相", False)
            boost_prompt = kwargs.get("提示增强", True)
            timeout = int(kwargs.get("超时秒数", 300))

            # 以主图决定目标尺寸
            w, h = self.compute_size(main_img, res_tier, aspect)

            # 主图 PIL
            main_pil = self.to_pil(main_img[0])

            # 收集参考图
            ref_inputs = [
                kwargs.get("参考图1"),
                kwargs.get("参考图2"),
                kwargs.get("参考图3"),
                kwargs.get("参考图4"),
            ]
            ref_pils = []
            for ref in ref_inputs:
                if ref is not None:
                    ref_pils.extend(self.batch_to_pil(ref))
            ref_pils = ref_pils[:15]

            # 最多 16 张（主图 + 15参考）
            all_pils = [main_pil] + ref_pils
            all_pils = all_pils[:16]

            files = []
            total_bytes = 0

            # 主图和参考图统一做：等比例缩放 + 补边
            for i, p in enumerate(all_pils):
                prepared = self.fit_with_padding(p, w, h, bg=(255, 255, 255))
                img_bytes = self.to_bytes(prepared)
                total_bytes += len(img_bytes)
                files.append(("image", (f"{i}.png", img_bytes, "image/png")))

            if total_bytes > 50 * 1024 * 1024:
                raise Exception(f"上传图片总大小 {total_bytes / 1024 / 1024:.2f}MB 超过50MB")

            # 遮罩也必须使用和主图完全一致的变换
            if mask_t is not None:
                mask_bytes = self.process_mask_with_main_geometry(
                    mask_t=mask_t,
                    main_pil=main_pil,
                    target_w=w,
                    target_h=h,
                    invert=invert_mask
                )
                files.append(("mask", ("mask.png", mask_bytes, "image/png")))

            final_prompt = self.make_prompt(prompt, mask_t is not None, boost_prompt)

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Idempotency-Key": str(uuid.uuid4()),
                "Accept": "application/json"
            }

            data = {
                "model": "gpt-image-2",
                "prompt": final_prompt,
                "n": str(n),
                "quality": quality,
                "size": f"{w}x{h}",
                "background": bg
            }

            with requests.Session() as sess:
                sess.trust_env = False
                sess.mount(
                    "https://",
                    HTTPAdapter(
                        max_retries=Retry(
                            total=3,
                            backoff_factor=1,
                            status_forcelist=[429, 500, 502, 503, 504],
                            allowed_methods=["GET", "POST"]
                        )
                    )
                )

                resp = sess.post(
                    f"{API_HOST}/v1/images/edits",
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=timeout,
                    verify=False
                )

                if resp.status_code != 200:
                    raise Exception(f"HTTP {resp.status_code}: {resp.text}")

                resj = resp.json()
                imgs = self.parse_images(resj, sess)

            if not imgs:
                raise Exception("❌ 未返回图片")

            base_sz = imgs[0].size
            tlist = []
            for im in imgs:
                im = im.convert("RGB")
                if im.size != base_sz:
                    im = im.resize(base_sz, Image.Resampling.LANCZOS)
                arr = np.array(im).astype(np.float32) / 255.0
                tlist.append(torch.from_numpy(arr))

            batch = torch.stack(tlist, dim=0)

            log = (
                f"✅ 编辑成功 | 结果张数:{len(tlist)} | "
                f"参考图:{len(ref_pils)} | "
                f"目标尺寸:{w}x{h} | "
                f"预处理:等比例缩放+补边"
            )
            return (batch, log)

        except Exception as e:
            tb = traceback.format_exc()
            msg = f"❌ 异常: {e}\n{tb}"
            if skip_error:
                return (self.black_out(w, h), msg)
            raise Exception(msg)

    # =========================
    # Prompt
    # =========================
    def make_prompt(self, p, has_mask, boost):
        base = (p or "").strip()
        if not boost:
            return base
        if has_mask:
            return (
                base +
                " 仅修改遮罩指定区域。未遮罩区域的文字内容、行数、位置、排版、字体风格、主体、构图、颜色和细节必须尽量保持不变，不要改动未遮罩区域。"
            )
        else:
            return base + " 参考所有输入图像融合，但不要过度破坏主图主体结构。"

    # =========================
    # Size
    # =========================
    def compute_size(self, img_t, tier, asp):
        bs, h, w, c = img_t.shape

        if tier == "Auto":
            if asp == "Auto":
                return self.legalize(w, h)
            rw, rh = map(int, asp.split(":"))
            ratio = rw / rh
            pixels = w * h
            hh = math.sqrt(pixels / ratio)
            ww = hh * ratio
            return self.legalize(int(ww), int(hh))

        ratio = (w / h) if asp == "Auto" else (int(asp.split(":")[0]) / int(asp.split(":")[1]))
        tgt = {"1K": 1048576, "2K": 4194304, "4K": 8294400}.get(tier, 4194304)

        hh = math.sqrt(tgt / ratio)
        ww = hh * ratio
        return self.legalize(int(ww), int(hh))

    def legalize(self, w, h):
        w = max(16, int(round(w / 16) * 16))
        h = max(16, int(round(h / 16) * 16))

        if max(w, h) > 3840:
            sc = 3840 / max(w, h)
            w = int(w * sc)
            h = int(h * sc)
            w = max(16, int(round(w / 16) * 16))
            h = max(16, int(round(h / 16) * 16))

        long_side = max(w, h)
        short_side = min(w, h)
        if short_side > 0 and long_side / short_side > 3:
            if w > h:
                w = h * 3
            else:
                h = w * 3
            w = max(16, int(round(w / 16) * 16))
            h = max(16, int(round(h / 16) * 16))

        pixels = w * h
        if pixels < 655360:
            sc = (655360 / pixels) ** 0.5
            w = int(w * sc)
            h = int(h * sc)
            w = max(16, int(round(w / 16) * 16))
            h = max(16, int(round(h / 16) * 16))

        if w * h > 8294400:
            sc = (8294400 / (w * h)) ** 0.5
            w = int(w * sc)
            h = int(h * sc)
            w = max(16, int(round(w / 16) * 16))
            h = max(16, int(round(h / 16) * 16))

        if max(w, h) > 3840:
            sc = 3840 / max(w, h)
            w = int(w * sc)
            h = int(h * sc)

        w = max(16, int(round(w / 16) * 16))
        h = max(16, int(round(h / 16) * 16))
        return w, h

    # =========================
    # Geometry / Padding
    # =========================
    def get_fit_params(self, src_w, src_h, target_w, target_h):
        scale = min(target_w / src_w, target_h / src_h)
        new_w = max(1, int(round(src_w * scale)))
        new_h = max(1, int(round(src_h * scale)))
        x = (target_w - new_w) // 2
        y = (target_h - new_h) // 2
        return new_w, new_h, x, y

    def fit_with_padding(self, img, target_w, target_h, bg=(255, 255, 255)):
        img = img.convert("RGB")
        src_w, src_h = img.size
        new_w, new_h, x, y = self.get_fit_params(src_w, src_h, target_w, target_h)

        resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (target_w, target_h), bg)
        canvas.paste(resized, (x, y))
        return canvas

    # =========================
    # Mask
    # =========================
    def process_mask_with_main_geometry(self, mask_t, main_pil, target_w, target_h, invert=False):
        """
        让 mask 和主图使用完全相同的缩放 + 补边参数，避免错位。
        最终输出 RGBA PNG，alpha 表示可编辑区域。
        """
        m_np = mask_t.cpu().numpy()
        if len(m_np.shape) == 3:
            m_np = m_np[0]

        # 原始 mask（默认和主图同分辨率）
        pil_mask = Image.fromarray(np.clip(m_np * 255, 0, 255).astype(np.uint8)).convert("L")

        src_w, src_h = main_pil.size
        new_w, new_h, x, y = self.get_fit_params(src_w, src_h, target_w, target_h)

        resized_mask = pil_mask.resize((new_w, new_h), Image.Resampling.LANCZOS)

        # 先构造整张遮罩画布
        # 注意：这里先做“语义上的遮罩图”，再按 invert 决定 alpha
        canvas_mask = Image.new("L", (target_w, target_h), 0)
        canvas_mask.paste(resized_mask, (x, y))

        # 兼容你原来逻辑：
        # inv=True  -> alpha = mask本身
        # inv=False -> alpha = 反相mask
        alpha = canvas_mask if invert else ImageOps.invert(canvas_mask)

        rgba = Image.new("RGBA", (target_w, target_h), (255, 255, 255, 255))
        rgba.putalpha(alpha)
        return self.to_bytes(rgba)

    # =========================
    # PIL / Tensor / Bytes
    # =========================
    def to_bytes(self, p):
        b = BytesIO()
        p.save(b, "PNG")
        return b.getvalue()

    def to_pil(self, t):
        a = np.clip(t.cpu().numpy() * 255, 0, 255).astype(np.uint8)
        return Image.fromarray(a).convert("RGB")

    def batch_to_pil(self, b):
        if b is None:
            return []
        if len(b.shape) == 3:
            b = b.unsqueeze(0)
        return [self.to_pil(b[i]) for i in range(b.shape[0])]

    # =========================
    # Response Parse
    # =========================
    def parse_images(self, resj, sess):
        out = []
        for d in resj.get("data", []):
            b64 = d.get("b64_json")
            url = d.get("url")
            if b64:
                b64_clean = str(b64).split("base64,")[-1]
                out.append(Image.open(BytesIO(base64.b64decode(b64_clean))).convert("RGB"))
            elif url:
                resp = sess.get(url, timeout=30, verify=False)
                resp.raise_for_status()
                out.append(Image.open(BytesIO(resp.content)).convert("RGB"))
        return out

    # =========================
    # Fallback
    # =========================
    def black_out(self, w=1024, h=1024):
        return torch.zeros((1, h, w, 3), dtype=torch.float32)