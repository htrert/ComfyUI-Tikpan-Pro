"""
Tikpan 智能分层 PSD 节点 - 三档分级方案

档位说明：
- 经济档 (Economy): rembg + OpenCV 连通域检测，~300MB，5-10秒
- 标准档 (Standard): SAM2 + EasyOCR，~2.4GB，15-30秒，识别复杂场景
- 极致档 (Premium): SAM2 + LaMa Inpainting 补全，~5GB+，60-120秒，被遮挡区域智能补全
"""
import os
import sys
import subprocess
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFilter
from io import BytesIO
import folder_paths
import comfy.utils


KEY_IMAGE = "输入图片"
KEY_FILENAME = "文件名"
KEY_TIER = "分层档位"
KEY_INPAINT = "补全被遮挡区域"
KEY_DETECT_TEXT = "检测文字"
KEY_MIN_AREA = "最小元素面积"
KEY_BLUR_THRESHOLD = "边缘羽化"
KEY_AUTO_INSTALL = "自动安装依赖"

RET_PATH = "PSD文件路径"
RET_LOG = "分层日志"
RET_PREVIEW = "预览图"

TIER_ECONOMY = "经济档 (300MB) - 简单商品图"
TIER_STANDARD = "标准档 (2.4GB) - 复杂场景 推荐"
TIER_PREMIUM = "极致档 (5GB+) - 商业级分层"


class TikpanSmartPSDLayeringNode:
    """智能分层 PSD 节点 - 三档可选"""

    def __init__(self):
        self.output_dir = folder_paths.get_output_directory()
        self.deps_status = {}
        self._check_all_dependencies()

    def _check_all_dependencies(self):
        """检查所有可能的依赖"""
        deps = {
            "pytoshop": False,
            "cv2": False,
            "rembg": False,
            "easyocr": False,
            "sam2": False,
            "lama": False,
        }

        try:
            import pytoshop
            deps["pytoshop"] = True
        except ImportError:
            pass

        try:
            import cv2
            deps["cv2"] = True
        except ImportError:
            pass

        try:
            from rembg import remove
            deps["rembg"] = True
        except ImportError:
            pass

        try:
            import easyocr
            deps["easyocr"] = True
        except ImportError:
            pass

        try:
            from sam2.build_sam import build_sam2
            deps["sam2"] = True
        except ImportError:
            pass

        try:
            from simple_lama_inpainting import SimpleLama
            deps["lama"] = True
        except ImportError:
            pass

        self.deps_status = deps

    def _install_for_tier(self, tier, do_inpaint):
        """根据档位安装对应依赖"""
        python_exe = sys.executable
        packages = []

        if not self.deps_status["pytoshop"]:
            packages.append("pytoshop")
        if not self.deps_status["cv2"]:
            packages.append("opencv-python")

        if TIER_ECONOMY in tier:
            if not self.deps_status["rembg"]:
                packages.append("rembg")
        elif TIER_STANDARD in tier or TIER_PREMIUM in tier:
            if not self.deps_status["sam2"]:
                packages.append("git+https://github.com/facebookresearch/sam2.git")
            if not self.deps_status["easyocr"]:
                packages.append("easyocr")

        if (TIER_PREMIUM in tier or do_inpaint) and not self.deps_status["lama"]:
            packages.append("simple-lama-inpainting")

        if not packages:
            return True, "所有依赖已就绪"

        log = f"📦 正在安装 {len(packages)} 个依赖包...\n"
        try:
            for pkg in packages:
                print(f"[Tikpan PSD] 安装 {pkg}...")
                log += f"  • {pkg}\n"
                subprocess.check_call(
                    [python_exe, "-m", "pip", "install", pkg],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            self._check_all_dependencies()
            log += "✅ 依赖安装完成\n"
            return True, log
        except Exception as e:
            return False, f"❌ 依赖安装失败: {e}\n请手动执行: pip install {' '.join(packages)}"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                KEY_IMAGE: ("IMAGE", {"tooltip": "要进行智能分层的图片"}),
                KEY_FILENAME: ("STRING", {"default": "smart_layered", "tooltip": "PSD 文件名"}),
                KEY_TIER: (
                    [TIER_ECONOMY, TIER_STANDARD, TIER_PREMIUM],
                    {
                        "default": TIER_STANDARD,
                        "tooltip": "经济档：快速但效果一般；标准档：SAM2 精准识别；极致档：被遮挡区域智能补全"
                    }
                ),
                KEY_INPAINT: (
                    ["否", "是"],
                    {
                        "default": "否",
                        "tooltip": "标准档+开启此项 = 极致档效果。补全被其他元素遮挡的部分（速度变慢约2倍）"
                    }
                ),
                KEY_DETECT_TEXT: (
                    ["是", "否"],
                    {"default": "是", "tooltip": "是否单独分离文字图层"}
                ),
                KEY_MIN_AREA: (
                    "INT",
                    {"default": 2000, "min": 100, "max": 100000, "tooltip": "过滤小于此面积的元素"}
                ),
                KEY_BLUR_THRESHOLD: (
                    "INT",
                    {"default": 5, "min": 0, "max": 30, "tooltip": "边缘羽化程度"}
                ),
                KEY_AUTO_INSTALL: (
                    ["是", "否"],
                    {"default": "是", "tooltip": "首次使用自动安装依赖（推荐）"}
                ),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "IMAGE")
    RETURN_NAMES = (RET_PATH, RET_LOG, RET_PREVIEW)
    FUNCTION = "smart_layer"
    CATEGORY = "🏆 Tikpan 官方独家节点/03 工具 Tools"
    OUTPUT_NODE = True
    DESCRIPTION = "🤖 智能分层 PSD：三档可选（经济/标准/极致），自动识别产品、背景、文字并保存为分层 PSD"

    def smart_layer(self, **kwargs):
        from .tikpan_psd_processor import PSDLayerProcessor

        image_tensor = kwargs.get(KEY_IMAGE)
        filename = str(kwargs.get(KEY_FILENAME, "smart_layered")).strip()
        tier = str(kwargs.get(KEY_TIER, TIER_STANDARD))
        do_inpaint = str(kwargs.get(KEY_INPAINT, "否")) == "是"
        detect_text = str(kwargs.get(KEY_DETECT_TEXT, "是")) == "是"
        min_area = int(kwargs.get(KEY_MIN_AREA, 2000))
        blur_threshold = int(kwargs.get(KEY_BLUR_THRESHOLD, 5))
        auto_install = str(kwargs.get(KEY_AUTO_INSTALL, "是")) == "是"

        pbar = comfy.utils.ProgressBar(100)

        if auto_install:
            ok, install_log = self._install_for_tier(tier, do_inpaint)
            if not ok:
                return ("", install_log, self._create_error_image(install_log))
        else:
            missing = self._check_missing_for_tier(tier, do_inpaint)
            if missing:
                msg = f"ERROR: 缺少依赖: {', '.join(missing)}\n请将'自动安装依赖'设为'是'"
                return ("", msg, self._create_error_image(msg))

        pbar.update(10)

        if len(image_tensor.shape) == 4:
            image_tensor = image_tensor[0]
        arr = (255.0 * image_tensor.detach().cpu().numpy()).astype(np.uint8)
        pil_image = Image.fromarray(arr).convert("RGB")

        try:
            processor = PSDLayerProcessor(self.output_dir)

            print(f"[Tikpan PSD] 使用档位: {tier}")
            if TIER_ECONOMY in tier:
                layers = processor.process_economy(pil_image, min_area, blur_threshold, detect_text, pbar)
            elif TIER_STANDARD in tier:
                layers = processor.process_standard(pil_image, min_area, blur_threshold, detect_text, do_inpaint, pbar)
            else:
                layers = processor.process_premium(pil_image, min_area, blur_threshold, detect_text, pbar)

            pbar.update(85)

            psd_path = processor.save_as_psd(layers, filename, pil_image.size)
            preview = processor.create_preview(layers, pil_image.size)
            pbar.update(100)

            log = f"✅ 智能分层成功 | 档位: {tier.split(' ')[0]}\n"
            log += f"📁 文件: {psd_path}\n"
            log += f"📊 共 {len(layers)} 个图层:\n"
            for i, layer in enumerate(layers):
                log += f"  {i+1}. {layer['name']} ({layer.get('type', 'element')})\n"

            return (psd_path, log, preview)

        except Exception as e:
            import traceback
            error_log = f"ERROR: 智能分层失败\n{e}\n{traceback.format_exc()[:1000]}"
            return ("", error_log, self._create_error_image(error_log))

    def _check_missing_for_tier(self, tier, do_inpaint):
        missing = []
        if not self.deps_status["pytoshop"]: missing.append("pytoshop")
        if not self.deps_status["cv2"]: missing.append("opencv-python")
        if TIER_ECONOMY in tier and not self.deps_status["rembg"]:
            missing.append("rembg")
        if (TIER_STANDARD in tier or TIER_PREMIUM in tier):
            if not self.deps_status["sam2"]: missing.append("sam2")
            if not self.deps_status["easyocr"]: missing.append("easyocr")
        if (TIER_PREMIUM in tier or do_inpaint) and not self.deps_status["lama"]:
            missing.append("simple-lama-inpainting")
        return missing

    def _create_error_image(self, error_msg=""):
        img = Image.new("RGB", (768, 512), (45, 45, 50))
        draw = ImageDraw.Draw(img)
        draw.text((20, 20), "⚠ Error:", fill=(255, 100, 100))
        lines = error_msg.split("\n")[:18]
        y = 60
        for line in lines:
            draw.text((20, y), line[:90], fill=(220, 220, 220))
            y += 22
        arr = np.array(img).astype(np.float32) / 255.0
        return torch.from_numpy(arr).unsqueeze(0)


NODE_CLASS_MAPPINGS = {"TikpanSmartPSDLayeringNode": TikpanSmartPSDLayeringNode}
NODE_DISPLAY_NAME_MAPPINGS = {"TikpanSmartPSDLayeringNode": "工具｜智能分层 PSD 生成器"}
