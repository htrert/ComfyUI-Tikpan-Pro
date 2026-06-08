"""
Tikpan 智能分层 PSD 节点 - 三档可选（商业级管线）

档位说明：
- 经济档: BiRefNet 抠图 + cv2 连通域 + PaddleOCR，5-15秒
- 标准档: BiRefNet + SAM2 自动多尺度 + PaddleOCR，20-60秒
- 极致档: BiRefNet + GroundingDINO+SAM2 语义分割 + LaMa 补全 + PaddleOCR，60-180秒
"""
import os
import sys
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from io import BytesIO
import folder_paths
import comfy.utils

from .tikpan_categories import CATEGORY_PSD_TOOLS


def torch_cuda_available():
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


KEY_IMAGE = "输入图片"
KEY_FILENAME = "文件名"
KEY_TIER = "分层档位"
KEY_SCENE = "场景类型"
KEY_INPAINT = "补全被遮挡区域"
KEY_DETECT_TEXT = "检测文字"
KEY_MIN_AREA = "最小元素面积"
KEY_BLUR_THRESHOLD = "边缘羽化"
KEY_AUTO_INSTALL = "自动安装依赖"

RET_PATH = "PSD文件路径"
RET_LOG = "分层日志"
RET_PREVIEW = "预览图"

TIER_ECONOMY = "经济档 - BiRefNet 快速分层"
TIER_STANDARD = "标准档 - BiRefNet+SAM2 高精度 推荐"
TIER_PREMIUM = "极致档 - BiRefNet+GroundingDINO+SAM2 商业级"

TIER_KIND_ECONOMY = "economy"
TIER_KIND_STANDARD = "standard"
TIER_KIND_PREMIUM = "premium"


def normalize_tier(tier):
    tier_text = str(tier or "")
    if TIER_ECONOMY in tier_text or "经济档" in tier_text:
        return TIER_KIND_ECONOMY
    if TIER_STANDARD in tier_text or "标准档" in tier_text:
        return TIER_KIND_STANDARD
    if TIER_PREMIUM in tier_text or "极致档" in tier_text:
        return TIER_KIND_PREMIUM
    return TIER_KIND_STANDARD


SCENE_AUTO = "自动检测（推荐）"
SCENE_ECOM_ITEM = "电商商品图（白底/主图）"
SCENE_ECOM_BANNER = "电商详情页/海报/Banner"
SCENE_PORTRAIT = "人物/生活方式图"
SCENE_LIFESTYLE = "生活场景图（食物/家居）"
SCENE_ALL = "全场景（最多层）"

SCENE_LABEL_TO_KEY = {
    SCENE_AUTO: "auto",
    SCENE_ECOM_ITEM: "ecom_item",
    SCENE_ECOM_BANNER: "ecom_banner",
    SCENE_PORTRAIT: "portrait",
    SCENE_LIFESTYLE: "lifestyle",
    SCENE_ALL: "all",
}


class TikpanSmartPSDLayeringNode:
    """智能分层 PSD 节点 - 三档可选"""

    def __init__(self):
        self.output_dir = folder_paths.get_output_directory()
        self.deps_status = {}
        self._check_all_dependencies()

    def _check_all_dependencies(self):
        """检查所有可能的依赖（新版商业级管线）"""
        deps = {
            "psd_tools": False,
            "cv2": False,
            "birefnet": False,     # transformers + timm + kornia + einops
            "sam2": False,
            "gdino": False,        # transformers 自带，检测 ZeroShot 检测器
            "paddleocr": False,
            "pyzbar": False,       # 二维码/条形码（电商场景增强）
            "rembg": False,        # 降级
            "easyocr": False,      # 降级
            "lama": False,
        }

        try:
            import psd_tools
            deps["psd_tools"] = True
        except ImportError:
            pass

        try:
            import cv2
            deps["cv2"] = True
        except ImportError:
            pass

        try:
            import transformers
            import timm
            import kornia
            import einops
            deps["birefnet"] = True
        except ImportError:
            pass

        try:
            from sam2.build_sam import build_sam2
            deps["sam2"] = True
        except ImportError:
            pass

        try:
            from transformers import AutoModelForZeroShotObjectDetection
            deps["gdino"] = True
        except ImportError:
            pass

        try:
            from paddleocr import PaddleOCR
            deps["paddleocr"] = True
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
            from simple_lama_inpainting import SimpleLama
            deps["lama"] = True
        except ImportError:
            pass

        try:
            from pyzbar.pyzbar import decode
            deps["pyzbar"] = True
        except ImportError:
            pass

        self.deps_status = deps

    def _install_for_tier(self, tier, do_inpaint):
        """根据档位安装对应依赖"""
        python_exe = sys.executable
        packages = []
        special_steps = []  # 需要特殊命令的步骤

        # 共需
        if not self.deps_status["psd_tools"]:
            packages.append("psd-tools")
        if not self.deps_status["cv2"]:
            packages.append("opencv-python")

        # BiRefNet 依赖（所有档位都用）
        if not self.deps_status["birefnet"]:
            packages.extend(["transformers", "timm", "kornia", "einops", "torchvision"])

        # PaddleOCR（所有档位都用）
        if not self.deps_status["paddleocr"]:
            # paddlepaddle GPU 必须从官方源拉
            if torch_cuda_available():
                special_steps.append((
                    "paddlepaddle-gpu",
                    [python_exe, "-m", "pip", "install",
                     "paddlepaddle-gpu==3.2.0",
                     "-i", "https://www.paddlepaddle.org.cn/packages/stable/cu118/"]
                ))
            else:
                packages.append("paddlepaddle")
            packages.append("paddleocr")

        # 降级方案（rembg / easyocr 在 BiRefNet/PaddleOCR 失败时兜底）
        if not self.deps_status["rembg"]:
            packages.append("rembg")

        # 二维码/条形码（电商场景增强）
        if not self.deps_status["pyzbar"]:
            packages.append("pyzbar")

        tier_kind = normalize_tier(tier)

        # 标准档/极致档需要 SAM2
        if tier_kind in {TIER_KIND_STANDARD, TIER_KIND_PREMIUM}:
            if not self.deps_status["sam2"]:
                packages.append("git+https://github.com/facebookresearch/sam2.git")
            if not self.deps_status["easyocr"]:
                packages.append("easyocr")

        if (tier_kind == TIER_KIND_PREMIUM or do_inpaint) and not self.deps_status["lama"]:
            packages.append("simple-lama-inpainting")

        if not packages and not special_steps:
            return True, "所有依赖已就绪"

        log = f"📦 正在安装 {len(packages) + len(special_steps)} 个依赖包...\n"
        try:
            # 普通包
            if packages:
                for pkg in packages:
                    print(f"[Tikpan PSD] 安装 {pkg}...")
                    log += f"  • {pkg}\n"
                    subprocess.check_call(
                        [python_exe, "-m", "pip", "install", pkg],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
            # 特殊源
            for name, cmd in special_steps:
                print(f"[Tikpan PSD] 安装 {name}（特殊源）...")
                log += f"  • {name} (官方源)\n"
                subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            self._check_all_dependencies()
            log += "✅ 依赖安装完成\n"
            return True, log
        except Exception as e:
            cmd_hint = ' '.join(packages) if packages else ''
            return False, f"❌ 依赖安装失败: {e}\n请手动执行: pip install {cmd_hint}"

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
                        "tooltip": "经济档：BiRefNet+cv2 快速；标准档：BiRefNet+SAM2 高精度；极致档：BiRefNet+GroundingDINO+SAM2+LaMa 商业级"
                    }
                ),
                KEY_SCENE: (
                    [SCENE_AUTO, SCENE_ECOM_ITEM, SCENE_ECOM_BANNER, SCENE_PORTRAIT, SCENE_LIFESTYLE, SCENE_ALL],
                    {
                        "default": SCENE_AUTO,
                        "tooltip": "选场景类型，自动切换 GroundingDINO 提示词、人物专用模型、二维码/色块/字号分组等增强。自动检测会先粗识别再判断"
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
    CATEGORY = CATEGORY_PSD_TOOLS
    OUTPUT_NODE = True
    DESCRIPTION = "🤖 智能分层 PSD：三档可选（经济/标准/极致），自动识别产品、背景、文字并保存为分层 PSD"

    def smart_layer(self, **kwargs):
        from .tikpan_psd_processor import PSDLayerProcessor

        image_tensor = kwargs.get(KEY_IMAGE)
        filename = str(kwargs.get(KEY_FILENAME, "smart_layered")).strip()
        tier = str(kwargs.get(KEY_TIER, TIER_STANDARD))
        tier_kind = normalize_tier(tier)
        scene_label = str(kwargs.get(KEY_SCENE, SCENE_AUTO))
        scene = SCENE_LABEL_TO_KEY.get(scene_label, "auto")
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

            print(f"[Tikpan PSD] 使用档位: {tier} | 场景: {scene_label}")
            if tier_kind == TIER_KIND_ECONOMY:
                layers = processor.process_economy(pil_image, min_area, blur_threshold, detect_text, pbar, scene=scene)
            elif tier_kind == TIER_KIND_STANDARD:
                layers = processor.process_standard(pil_image, min_area, blur_threshold, detect_text, do_inpaint, pbar, scene=scene)
            else:
                layers = processor.process_premium(pil_image, min_area, blur_threshold, detect_text, pbar, scene=scene)

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
        if not self.deps_status["psd_tools"]: missing.append("psd-tools")
        if not self.deps_status["cv2"]: missing.append("opencv-python")
        if not self.deps_status["birefnet"]: missing.append("transformers+timm+kornia+einops (BiRefNet)")
        if not self.deps_status["paddleocr"]: missing.append("paddleocr+paddlepaddle")
        tier_kind = normalize_tier(tier)
        if tier_kind in {TIER_KIND_STANDARD, TIER_KIND_PREMIUM}:
            if not self.deps_status["sam2"]: missing.append("sam2")
        if (tier_kind == TIER_KIND_PREMIUM or do_inpaint) and not self.deps_status["lama"]:
            missing.append("simple-lama-inpainting")
        return missing

    def _create_error_image(self, error_msg=""):
        """生成错误提示图 - 使用默认字体避免崩溃"""
        img = Image.new("RGB", (768, 512), (45, 45, 50))
        draw = ImageDraw.Draw(img)

        # 不使用自定义字体，避免 PIL ImageFont 的内存访问冲突
        try:
            draw.text((20, 20), "ERROR:", fill=(255, 100, 100))
            lines = error_msg.split("\n")[:18]
            y = 60
            for line in lines:
                try:
                    # 只显示 ASCII 字符
                    ascii_line = line.encode('ascii', 'ignore').decode('ascii')
                    if ascii_line.strip():
                        draw.text((20, y), ascii_line[:90], fill=(220, 220, 220))
                        y += 22
                except:
                    pass
        except Exception as e:
            print(f"[Tikpan PSD] 错误图生成失败: {e}")
            draw.text((20, 20), "ERROR", fill=(255, 100, 100))

        arr = np.array(img).astype(np.float32) / 255.0
        import torch
        return torch.from_numpy(arr).unsqueeze(0)


NODE_CLASS_MAPPINGS = {"TikpanSmartPSDLayeringNode": TikpanSmartPSDLayeringNode}
NODE_DISPLAY_NAME_MAPPINGS = {"TikpanSmartPSDLayeringNode": "工具｜智能分层 PSD 生成器"}
