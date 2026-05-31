"""
Tikpan PSD 模型预下载器
让用户可以在画布上提前一次性下载所有依赖和模型，避免首次运行卡顿
"""
import os
import sys
import subprocess
from PIL import Image, ImageDraw
import numpy as np


KEY_TIER = "下载档位"
KEY_INPAINT = "包含补全模型"
RET_LOG = "下载日志"
RET_STATUS = "状态预览"

CHOICE_ECONOMY = "经济档 (300MB)"
CHOICE_STANDARD = "标准档 (300MB)"
CHOICE_PREMIUM = "极致档 (500MB)"
CHOICE_ALL = "全部档位"


class TikpanPSDDependencyDownloaderNode:
    """PSD 依赖与模型预下载器"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                KEY_TIER: (
                    [CHOICE_ECONOMY, CHOICE_STANDARD, CHOICE_PREMIUM, CHOICE_ALL],
                    {"default": CHOICE_STANDARD, "tooltip": "选择要预下载的档位（推荐：标准档）"}
                ),
                KEY_INPAINT: (
                    ["否", "是"],
                    {"default": "否", "tooltip": "是否同时下载 inpainting 补全模型（约 200MB）"}
                ),
            },
        }

    RETURN_TYPES = ("STRING", "IMAGE")
    RETURN_NAMES = (RET_LOG, RET_STATUS)
    FUNCTION = "download"
    CATEGORY = "🏆 Tikpan 官方独家节点/03 工具 Tools"
    OUTPUT_NODE = True
    DESCRIPTION = "📦 PSD 模型预下载器：提前下载分层节点所需的所有依赖和 AI 模型，避免首次使用时等待"

    def download(self, **kwargs):
        tier = str(kwargs.get(KEY_TIER, CHOICE_STANDARD))
        include_inpaint = str(kwargs.get(KEY_INPAINT, "否")) == "是"

        log_lines = []
        log_lines.append(f"🚀 开始预下载: {tier}")
        log_lines.append("=" * 50)

        packages = ["pytoshop", "opencv-python"]

        if CHOICE_ECONOMY in tier or CHOICE_ALL in tier:
            packages.append("rembg")
        if CHOICE_STANDARD in tier or CHOICE_PREMIUM in tier or CHOICE_ALL in tier:
            packages.append("easyocr")
        if include_inpaint or CHOICE_PREMIUM in tier or CHOICE_ALL in tier:
            packages.append("simple-lama-inpainting")

        log_lines.append(f"\n📦 步骤1: 安装 {len(packages)} 个 pip 依赖")
        ok, pip_log = self._install_packages(packages)
        log_lines.append(pip_log)
        if not ok:
            return ("\n".join(log_lines), self._render_status_image(log_lines, success=False))

        log_lines.append("\n🤖 步骤2: 下载 AI 模型")

        if CHOICE_ECONOMY in tier or CHOICE_ALL in tier:
            ok, msg = self._prefetch_rembg_model()
            log_lines.append(msg)

        if CHOICE_STANDARD in tier or CHOICE_PREMIUM in tier or CHOICE_ALL in tier:
            ok, msg = self._prefetch_easyocr_model()
            log_lines.append(msg)

        if include_inpaint or CHOICE_PREMIUM in tier or CHOICE_ALL in tier:
            ok, msg = self._prefetch_lama_model()
            log_lines.append(msg)

        log_lines.append("\n" + "=" * 50)
        log_lines.append("✅ 全部下载完成，可以使用智能分层节点了")

        return ("\n".join(log_lines), self._render_status_image(log_lines, success=True))

    def _install_packages(self, packages):
        python_exe = sys.executable
        log = ""
        try:
            for pkg in packages:
                log += f"  • {pkg} ... "
                try:
                    subprocess.check_call(
                        [python_exe, "-m", "pip", "install", pkg],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    log += "✓\n"
                except Exception as e:
                    log += f"✗ {e}\n"
                    return False, log
            return True, log
        except Exception as e:
            return False, log + f"\n❌ 异常: {e}"

    def _prefetch_rembg_model(self):
        try:
            from rembg import new_session
            print("[Tikpan PSD] 预加载 rembg ISNet 模型...")
            new_session("isnet-general-use")
            return True, "  • rembg ISNet 模型 ✓"
        except Exception as e:
            return False, f"  • rembg 模型下载失败: {e}"

    def _prefetch_easyocr_model(self):
        try:
            import torch
            import easyocr
            print("[Tikpan PSD] 预加载 EasyOCR 中英文模型...")
            easyocr.Reader(['ch_sim', 'en'], gpu=torch.cuda.is_available())
            return True, "  • EasyOCR 中英文模型 ✓"
        except Exception as e:
            return False, f"  • EasyOCR 模型下载失败: {e}"

    def _prefetch_lama_model(self):
        try:
            from simple_lama_inpainting import SimpleLama
            print("[Tikpan PSD] 预加载 LaMa Inpainting 模型...")
            SimpleLama()
            return True, "  • LaMa Inpainting 模型 ✓"
        except Exception as e:
            return False, f"  • LaMa 模型下载失败: {e}"

    def _render_status_image(self, log_lines, success=True):
        img = Image.new("RGB", (900, 600), (30, 32, 38))
        draw = ImageDraw.Draw(img)
        title_color = (100, 220, 100) if success else (255, 100, 100)
        draw.text((20, 20), "Tikpan PSD 预下载状态", fill=title_color)
        draw.text((20, 45), "=" * 60, fill=(100, 100, 100))

        y = 75
        for line in log_lines[-22:]:
            color = (220, 220, 220)
            if "✓" in line or "✅" in line:
                color = (120, 230, 120)
            elif "✗" in line or "❌" in line or "失败" in line:
                color = (255, 130, 130)
            elif line.startswith("📦") or line.startswith("🤖"):
                color = (255, 200, 100)
            draw.text((20, y), line[:100], fill=color)
            y += 22

        arr = np.array(img).astype(np.float32) / 255.0
        import torch
        return torch.from_numpy(arr).unsqueeze(0)


NODE_CLASS_MAPPINGS = {"TikpanPSDDependencyDownloaderNode": TikpanPSDDependencyDownloaderNode}
NODE_DISPLAY_NAME_MAPPINGS = {"TikpanPSDDependencyDownloaderNode": "工具｜PSD 模型预下载器"}
