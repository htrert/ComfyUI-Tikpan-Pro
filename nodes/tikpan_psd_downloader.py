"""
Tikpan PSD 模型预下载器
让用户可以在画布上提前一次性下载所有依赖和模型，避免首次运行卡顿
"""
import os
import sys
import subprocess
from PIL import Image, ImageDraw
import numpy as np

from .tikpan_categories import CATEGORY_PSD_TOOLS


KEY_TIER = "下载档位"
KEY_INPAINT = "包含补全模型"
RET_LOG = "下载日志"
RET_STATUS = "状态预览"

CHOICE_ECONOMY = "经济档 (300MB)"
CHOICE_STANDARD = "标准档 (500MB)"
CHOICE_PREMIUM = "极致档 (700MB)"
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
    CATEGORY = CATEGORY_PSD_TOOLS
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
            packages.append("git+https://github.com/facebookresearch/sam2.git")
            packages.append("easyocr")
        if include_inpaint or CHOICE_PREMIUM in tier or CHOICE_ALL in tier:
            packages.append("simple-lama-inpainting")

        # 步骤1: 安装依赖
        log_lines.append(f"\n📦 步骤1/2: 安装 {len(packages)} 个 pip 依赖")
        ok, pip_log = self._install_packages(packages)
        log_lines.append(pip_log)
        if not ok:
            log_lines.append("\n" + "=" * 50)
            log_lines.append("❌ 依赖安装失败，请检查网络或手动安装")
            return ("\n".join(log_lines), self._render_status_image(log_lines, success=False))

        # 步骤2: 下载模型
        log_lines.append("\n🤖 步骤2/2: 下载 AI 模型")
        model_success = []
        model_failed = []

        if CHOICE_ECONOMY in tier or CHOICE_ALL in tier:
            ok, msg = self._prefetch_rembg_model()
            log_lines.append(msg)
            if ok:
                model_success.append("rembg")
            else:
                model_failed.append("rembg")

        if CHOICE_STANDARD in tier or CHOICE_PREMIUM in tier or CHOICE_ALL in tier:
            ok, msg = self._prefetch_sam2_model()
            log_lines.append(msg)
            if ok:
                model_success.append("SAM2")
            else:
                model_failed.append("SAM2")

            ok, msg = self._prefetch_easyocr_model()
            log_lines.append(msg)
            if ok:
                model_success.append("EasyOCR")
            else:
                model_failed.append("EasyOCR")

        if include_inpaint or CHOICE_PREMIUM in tier or CHOICE_ALL in tier:
            ok, msg = self._prefetch_lama_model()
            log_lines.append(msg)
            if ok:
                model_success.append("LaMa")
            else:
                model_failed.append("LaMa")

        # 总结
        log_lines.append("\n" + "=" * 50)
        if model_failed:
            log_lines.append(f"⚠️ 部分模型下载失败: {', '.join(model_failed)}")
            log_lines.append(f"✅ 成功下载: {', '.join(model_success)}")
            log_lines.append("\n提示: 失败的模型会在首次使用时自动重试")
            return ("\n".join(log_lines), self._render_status_image(log_lines, success=False))
        else:
            log_lines.append(f"✅ 全部下载完成！共 {len(model_success)} 个模型")
            log_lines.append(f"   成功: {', '.join(model_success)}")
            log_lines.append("\n🎉 现在可以使用智能分层节点了")
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
            session = new_session("isnet-general-use")
            print("[Tikpan PSD] rembg 模型加载成功")
            return True, "  • rembg ISNet 模型 ✓"
        except Exception as e:
            print(f"[Tikpan PSD] rembg 模型加载失败: {e}")
            return False, f"  • rembg 模型 ✗ (失败: {str(e)[:50]})"

    def _prefetch_sam2_model(self):
        try:
            from sam2.build_sam import build_sam2
            import folder_paths
            import os

            models_dir = os.path.join(folder_paths.models_dir, "sam2")
            os.makedirs(models_dir, exist_ok=True)

            ckpt_name = "sam2.1_hiera_small.pt"
            ckpt_path = os.path.join(models_dir, ckpt_name)

            if os.path.exists(ckpt_path):
                file_size = os.path.getsize(ckpt_path) / (1024 * 1024)
                print(f"[Tikpan PSD] SAM2 模型已存在 ({file_size:.1f}MB)")
                return True, f"  • SAM2 模型 ✓ (已存在 {file_size:.1f}MB)"
            else:
                import urllib.request
                url = f"https://dl.fbaipublicfiles.com/segment_anything_2/092824/{ckpt_name}"
                print(f"[Tikpan PSD] 正在下载 SAM2 模型 (~180MB)...")
                print(f"[Tikpan PSD] 下载地址: {url}")

                # 下载并显示进度
                def reporthook(count, block_size, total_size):
                    if total_size > 0:
                        percent = int(count * block_size * 100 / total_size)
                        mb_downloaded = count * block_size / (1024 * 1024)
                        mb_total = total_size / (1024 * 1024)
                        if count % 50 == 0:  # 每50个块打印一次
                            print(f"[Tikpan PSD] 下载进度: {percent}% ({mb_downloaded:.1f}/{mb_total:.1f}MB)")

                urllib.request.urlretrieve(url, ckpt_path, reporthook)
                file_size = os.path.getsize(ckpt_path) / (1024 * 1024)
                print(f"[Tikpan PSD] SAM2 模型下载完成 ({file_size:.1f}MB)")
                return True, f"  • SAM2 模型 ✓ (已下载 {file_size:.1f}MB)"

        except Exception as e:
            print(f"[Tikpan PSD] SAM2 模型下载失败: {e}")
            return False, f"  • SAM2 模型 ✗ (失败: {str(e)[:50]})"

    def _prefetch_easyocr_model(self):
        try:
            import torch
            import easyocr
            print("[Tikpan PSD] 预加载 EasyOCR 中英文模型...")
            print("[Tikpan PSD] 首次运行会下载检测模型和识别模型，请耐心等待...")
            reader = easyocr.Reader(['ch_sim', 'en'], gpu=torch.cuda.is_available())
            print("[Tikpan PSD] EasyOCR 模型加载成功")
            return True, "  • EasyOCR 中英文模型 ✓"
        except Exception as e:
            print(f"[Tikpan PSD] EasyOCR 模型加载失败: {e}")
            return False, f"  • EasyOCR 模型 ✗ (失败: {str(e)[:50]})"

    def _prefetch_lama_model(self):
        try:
            from simple_lama_inpainting import SimpleLama
            print("[Tikpan PSD] 预加载 LaMa Inpainting 模型...")
            SimpleLama()
            print("[Tikpan PSD] LaMa 模型加载成功")
            return True, "  • LaMa Inpainting 模型 ✓"
        except Exception as e:
            print(f"[Tikpan PSD] LaMa 模型加载失败: {e}")
            return False, f"  • LaMa 模型 ✗ (失败: {str(e)[:50]})"

    def _render_status_image(self, log_lines, success=True):
        """生成状态预览图 - 使用默认字体避免崩溃"""
        img = Image.new("RGB", (900, 600), (30, 32, 38))
        draw = ImageDraw.Draw(img)

        # 不使用自定义字体，避免 PIL ImageFont 的内存访问冲突
        # 直接使用 PIL 默认字体（bitmap font），稳定可靠
        try:
            title_color = (100, 220, 100) if success else (255, 100, 100)
            draw.text((20, 20), "Tikpan PSD Download Status", fill=title_color)
            draw.text((20, 45), "=" * 60, fill=(100, 100, 100))

            y = 75
            for line in log_lines[-22:]:
                color = (220, 220, 220)
                # 检查状态标记
                if "OK" in line or "success" in line.lower():
                    color = (120, 230, 120)
                elif "FAIL" in line or "error" in line.lower():
                    color = (255, 130, 130)
                elif "Step" in line or "step" in line.lower():
                    color = (255, 200, 100)

                # 只显示 ASCII 字符，避免编码问题
                try:
                    ascii_line = line.encode('ascii', 'ignore').decode('ascii')
                    if ascii_line.strip():
                        draw.text((20, y), ascii_line[:100], fill=color)
                        y += 22
                except:
                    pass
        except Exception as e:
            # 完全降级：纯色块显示状态
            print(f"[Tikpan PSD] 预览图生成失败: {e}")
            draw.rectangle([20, 20, 880, 80], fill=(100, 220, 100) if success else (255, 100, 100))
            try:
                draw.text((30, 35), "Status: " + ("OK" if success else "ERROR"), fill=(255, 255, 255))
            except:
                pass

        arr = np.array(img).astype(np.float32) / 255.0
        import torch
        return torch.from_numpy(arr).unsqueeze(0)


NODE_CLASS_MAPPINGS = {"TikpanPSDDependencyDownloaderNode": TikpanPSDDependencyDownloaderNode}
NODE_DISPLAY_NAME_MAPPINGS = {"TikpanPSDDependencyDownloaderNode": "工具｜PSD 模型预下载器"}
