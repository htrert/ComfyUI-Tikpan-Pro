import os
import sys
import subprocess
import numpy as np
from PIL import Image
from io import BytesIO
import folder_paths


KEY_IMAGE = "输入图片"
KEY_FILENAME = "文件名"
KEY_QUALITY = "PSD质量"
KEY_SAVE_PATH = "保存路径"
KEY_AUTO_INSTALL = "自动安装依赖"

RET_PATH = "文件路径"
RET_LOG = "保存日志"


class TikpanPSDSaverNode:
    """
    Tikpan PSD 保存节点
    将 ComfyUI 的 IMAGE 类型保存为 PSD 格式
    支持自动安装依赖库
    """

    def __init__(self):
        self.output_dir = folder_paths.get_output_directory()
        self.psd_tools_available = False
        self._check_psd_tools()

    def _check_psd_tools(self):
        """检查 psd-tools 是否可用"""
        try:
            import psd_tools
            self.psd_tools_available = True
        except ImportError:
            self.psd_tools_available = False

    def _install_psd_tools(self):
        """自动安装 psd-tools 库"""
        try:
            python_exe = sys.executable
            subprocess.check_call(
                [python_exe, "-m", "pip", "install", "psd-tools", "--quiet"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            self._check_psd_tools()
            return True
        except Exception as e:
            return False

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                KEY_IMAGE: ("IMAGE", {"tooltip": "要保存为 PSD 的图片"}),
                KEY_FILENAME: (
                    "STRING",
                    {
                        "default": "tikpan_output",
                        "tooltip": "PSD 文件名（不含扩展名）"
                    }
                ),
                KEY_QUALITY: (
                    ["标准 (Pillow)", "高级 (psd-tools)"],
                    {
                        "default": "标准 (Pillow)",
                        "tooltip": "标准模式使用 Pillow 内置支持，高级模式支持多图层（需要安装 psd-tools）"
                    }
                ),
                KEY_AUTO_INSTALL: (
                    ["是", "否"],
                    {
                        "default": "是",
                        "tooltip": "如果缺少依赖库，是否自动安装（仅高级模式需要）"
                    }
                ),
            },
            "optional": {
                KEY_SAVE_PATH: (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "自定义保存路径（留空则使用 ComfyUI 默认输出目录）"
                    }
                ),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = (RET_PATH, RET_LOG)
    FUNCTION = "save_psd"
    CATEGORY = "🏆 Tikpan 官方独家节点/03 工具 Tools"
    OUTPUT_NODE = True
    DESCRIPTION = "💾 将图片保存为 PSD 格式，支持标准模式（Pillow）和高级模式（多图层）"

    def save_psd(self, **kwargs):
        image_tensor = kwargs.get(KEY_IMAGE)
        filename = str(kwargs.get(KEY_FILENAME, "tikpan_output")).strip()
        quality_mode = str(kwargs.get(KEY_QUALITY, "标准 (Pillow)"))
        auto_install = str(kwargs.get(KEY_AUTO_INSTALL, "是"))
        custom_path = str(kwargs.get(KEY_SAVE_PATH, "")).strip()

        # 确定保存目录
        if custom_path and os.path.isdir(custom_path):
            save_dir = custom_path
        else:
            save_dir = self.output_dir

        # 确保文件名安全
        filename = self._sanitize_filename(filename)
        if not filename:
            filename = "tikpan_output"

        # 生成唯一文件名
        counter = 1
        base_filename = filename
        filepath = os.path.join(save_dir, f"{filename}.psd")
        while os.path.exists(filepath):
            filename = f"{base_filename}_{counter:04d}"
            filepath = os.path.join(save_dir, f"{filename}.psd")
            counter += 1

        # 判断使用哪种模式
        use_advanced = "高级" in quality_mode or "psd-tools" in quality_mode

        try:
            if use_advanced:
                # 高级模式：使用 psd-tools
                if not self.psd_tools_available:
                    if auto_install == "是":
                        install_success = self._install_psd_tools()
                        if not install_success:
                            return self._fallback_to_pillow(image_tensor, filepath,
                                "psd-tools 安装失败，已降级为标准模式")
                    else:
                        return self._fallback_to_pillow(image_tensor, filepath,
                            "缺少 psd-tools 库，已降级为标准模式。如需高级功能，请设置'自动安装依赖'为'是'")

                # 使用 psd-tools 保存
                result_path, log = self._save_with_psd_tools(image_tensor, filepath)
                return (result_path, log)
            else:
                # 标准模式：使用 Pillow
                result_path, log = self._save_with_pillow(image_tensor, filepath)
                return (result_path, log)

        except Exception as e:
            error_log = f"ERROR: 保存 PSD 失败: {str(e)}"
            return ("", error_log)

    def _save_with_pillow(self, image_tensor, filepath):
        """使用 Pillow 保存 PSD（标准模式）"""
        # 转换 tensor 为 PIL Image
        if len(image_tensor.shape) == 4:
            image_tensor = image_tensor[0]

        arr = (255.0 * image_tensor.detach().cpu().numpy()).astype(np.uint8)
        pil_image = Image.fromarray(arr).convert("RGB")

        # 保存为 PSD
        pil_image.save(filepath, format="PSD")

        log = f"✅ PSD 保存成功 (标准模式)\n路径: {filepath}\n尺寸: {pil_image.size}"
        return (filepath, log)

    def _save_with_psd_tools(self, image_tensor, filepath):
        """使用 psd-tools 保存 PSD（高级模式，支持多图层）"""
        from psd_tools import PSDImage
        from psd_tools.api.layers import PixelLayer

        # 处理批量图片（多图层）
        if len(image_tensor.shape) == 4 and image_tensor.shape[0] > 1:
            # 多张图片 -> 多图层
            psd = PSDImage.new("RGB", (image_tensor.shape[2], image_tensor.shape[1]))

            for i in range(image_tensor.shape[0]):
                arr = (255.0 * image_tensor[i].detach().cpu().numpy()).astype(np.uint8)
                pil_image = Image.fromarray(arr).convert("RGB")

                # 创建图层
                layer = PixelLayer.frompil(pil_image, psd, f"Layer_{i+1}")
                psd.append(layer)

            psd.save(filepath)
            log = f"✅ PSD 保存成功 (高级模式 - 多图层)\n路径: {filepath}\n图层数: {image_tensor.shape[0]}\n尺寸: {image_tensor.shape[2]}x{image_tensor.shape[1]}"
        else:
            # 单张图片
            if len(image_tensor.shape) == 4:
                image_tensor = image_tensor[0]

            arr = (255.0 * image_tensor.detach().cpu().numpy()).astype(np.uint8)
            pil_image = Image.fromarray(arr).convert("RGB")

            # 使用 psd-tools 创建 PSD
            psd = PSDImage.frompil(pil_image)
            psd.save(filepath)

            log = f"✅ PSD 保存成功 (高级模式)\n路径: {filepath}\n尺寸: {pil_image.size}"

        return (filepath, log)

    def _fallback_to_pillow(self, image_tensor, filepath, reason):
        """降级到 Pillow 模式"""
        try:
            result_path, log = self._save_with_pillow(image_tensor, filepath)
            log = f"⚠️ {reason}\n{log}"
            return (result_path, log)
        except Exception as e:
            return ("", f"ERROR: {reason}，且 Pillow 保存也失败: {str(e)}")

    def _sanitize_filename(self, filename):
        """清理文件名，移除非法字符"""
        import re
        # 移除扩展名
        filename = os.path.splitext(filename)[0]
        # 移除非法字符
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # 移除前后空格
        filename = filename.strip()
        return filename


NODE_CLASS_MAPPINGS = {
    "TikpanPSDSaverNode": TikpanPSDSaverNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TikpanPSDSaverNode": "工具｜PSD 文件保存器",
}
