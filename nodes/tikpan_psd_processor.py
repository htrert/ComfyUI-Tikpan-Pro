"""
Tikpan PSD 分层处理器
封装三档分层逻辑：经济档（rembg）/ 标准档（SAM2）/ 极致档（SAM2 + Inpainting）
"""
import os
import re
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFilter


class PSDLayerProcessor:
    """PSD 分层处理器 - 三档统一接口"""

    def __init__(self, output_dir):
        self.output_dir = output_dir

    def process_economy(self, pil_image, min_area, blur, detect_text, pbar):
        """经济档：rembg + OpenCV 连通域"""
        print("[Tikpan PSD] 经济档处理中...")
        from rembg import remove, new_session

        pbar.update(20)
        session = new_session("isnet-general-use")
        subject_rgba = remove(pil_image, session=session).convert("RGBA")
        pbar.update(40)

        bg = self._make_background_layer(pil_image, subject_rgba)
        elements = self._cv2_extract_elements(pil_image, subject_rgba, min_area, blur)
        pbar.update(60)

        text_layers = []
        if detect_text:
            text_layers = self._easyocr_text_layers(pil_image)
        pbar.update(75)

        return self._build_layer_list(pil_image, bg, subject_rgba, elements, text_layers)

    def process_standard(self, pil_image, min_area, blur, detect_text, do_inpaint, pbar):
        """标准档：SAM2 自动分割所有物体"""
        print("[Tikpan PSD] 标准档（SAM2）处理中...")
        pbar.update(15)

        masks = self._sam2_auto_mask(pil_image, min_area)
        pbar.update(45)

        elements = []
        bg_alpha = np.ones(pil_image.size[::-1], dtype=np.uint8) * 255

        for idx, mask_dict in enumerate(masks):
            mask = mask_dict["segmentation"].astype(np.uint8) * 255
            if blur > 0:
                import cv2
                mask = cv2.GaussianBlur(mask, (blur*2+1, blur*2+1), 0)

            elem_array = np.array(pil_image.convert("RGBA")).copy()
            elem_array[:, :, 3] = mask

            if do_inpaint:
                elem_array = self._inpaint_element(pil_image, mask, elem_array)

            elem_img = Image.fromarray(elem_array, "RGBA")
            bbox = mask_dict.get("bbox", [0, 0, pil_image.width, pil_image.height])

            elements.append({
                "name": f"元素_{idx+1}",
                "image": elem_img,
                "type": "element",
                "x": int(bbox[0]),
                "y": int(bbox[1]),
                "width": int(bbox[2]) if len(bbox) > 2 else 0,
                "height": int(bbox[3]) if len(bbox) > 3 else 0,
                "area": int(mask_dict.get("area", 0)),
            })
            bg_alpha = np.minimum(bg_alpha, 255 - mask)

        pbar.update(65)

        bg_array = np.array(pil_image.convert("RGBA"))
        bg_array[:, :, 3] = bg_alpha
        if do_inpaint:
            combined_mask = 255 - bg_alpha
            bg_array = self._inpaint_element(pil_image, combined_mask, bg_array, fill_holes=True)
        bg_layer = Image.fromarray(bg_array, "RGBA")

        text_layers = []
        if detect_text:
            text_layers = self._easyocr_text_layers(pil_image)
        pbar.update(80)

        elements.sort(key=lambda l: l.get("area", 0), reverse=True)
        return self._build_layer_list(pil_image, bg_layer, None, elements, text_layers)

    def process_premium(self, pil_image, min_area, blur, detect_text, pbar):
        """极致档：标准档 + 强制 inpainting 补全"""
        print("[Tikpan PSD] 极致档（SAM2 + Inpainting）处理中...")
        return self.process_standard(pil_image, min_area, blur, detect_text, True, pbar)

    def _sam2_auto_mask(self, pil_image, min_area):
        """SAM2 自动生成所有物体的 mask"""
        try:
            from sam2.build_sam import build_sam2
            from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator
            import folder_paths
        except ImportError:
            print("[Tikpan PSD] SAM2 未安装，降级到 rembg")
            return self._fallback_to_rembg_masks(pil_image, min_area)

        models_dir = os.path.join(folder_paths.models_dir, "sam2")
        os.makedirs(models_dir, exist_ok=True)

        ckpt_name = "sam2.1_hiera_small.pt"
        cfg_name = "sam2.1_hiera_s.yaml"
        ckpt_path = os.path.join(models_dir, ckpt_name)

        if not os.path.exists(ckpt_path):
            self._download_sam2_model(ckpt_path, ckpt_name)

        try:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            sam2_model = build_sam2(cfg_name, ckpt_path, device=device)
            generator = SAM2AutomaticMaskGenerator(
                model=sam2_model,
                points_per_side=24,
                pred_iou_thresh=0.85,
                stability_score_thresh=0.92,
                min_mask_region_area=min_area,
            )

            img_array = np.array(pil_image)
            masks = generator.generate(img_array)
            masks.sort(key=lambda m: m["area"], reverse=True)
            return masks[:20]
        except Exception as e:
            print(f"[Tikpan PSD] SAM2 推理失败: {e}，降级到 rembg")
            return self._fallback_to_rembg_masks(pil_image, min_area)

    def _download_sam2_model(self, ckpt_path, ckpt_name):
        """下载 SAM2 模型"""
        import urllib.request
        url = f"https://dl.fbaipublicfiles.com/segment_anything_2/092824/{ckpt_name}"
        print(f"[Tikpan PSD] 首次下载 SAM2 模型 (~180MB): {url}")
        urllib.request.urlretrieve(url, ckpt_path)
        print(f"[Tikpan PSD] 下载完成: {ckpt_path}")

    def _fallback_to_rembg_masks(self, pil_image, min_area):
        """SAM2 不可用时降级到 rembg"""
        from rembg import remove, new_session
        import cv2

        session = new_session("isnet-general-use")
        subject = remove(pil_image, session=session).convert("RGBA")
        alpha = np.array(subject)[:, :, 3]
        _, binary = cv2.threshold(alpha, 127, 255, cv2.THRESH_BINARY)
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)

        masks = []
        for label_id in range(1, num_labels):
            area = stats[label_id, cv2.CC_STAT_AREA]
            if area < min_area:
                continue
            mask = (labels == label_id)
            x = stats[label_id, cv2.CC_STAT_LEFT]
            y = stats[label_id, cv2.CC_STAT_TOP]
            w = stats[label_id, cv2.CC_STAT_WIDTH]
            h = stats[label_id, cv2.CC_STAT_HEIGHT]
            masks.append({
                "segmentation": mask,
                "bbox": [x, y, w, h],
                "area": int(area),
            })
        return masks

    def _inpaint_element(self, pil_image, mask, elem_array, fill_holes=False):
        """使用 LaMa inpainting 补全被遮挡区域"""
        try:
            from simple_lama_inpainting import SimpleLama
            lama = SimpleLama()

            img_for_inpaint = pil_image.convert("RGB")
            mask_pil = Image.fromarray(mask).convert("L")

            if fill_holes:
                inpainted = lama(img_for_inpaint, mask_pil)
                result_array = np.array(inpainted.convert("RGBA"))
                result_array[:, :, 3] = elem_array[:, :, 3]
                return result_array
            return elem_array
        except Exception as e:
            print(f"[Tikpan PSD] Inpainting 跳过: {e}")
            return elem_array

    def _make_background_layer(self, pil_image, subject_rgba):
        """提取背景层（主体外的部分）"""
        subject_alpha = np.array(subject_rgba)[:, :, 3]
        bg_array = np.array(pil_image.convert("RGBA"))
        bg_array[:, :, 3] = 255 - subject_alpha
        return Image.fromarray(bg_array, "RGBA")

    def _cv2_extract_elements(self, pil_image, subject_rgba, min_area, blur):
        """使用 OpenCV 连通域分离主体内的独立元素"""
        import cv2

        alpha = np.array(subject_rgba)[:, :, 3]
        _, binary = cv2.threshold(alpha, 127, 255, cv2.THRESH_BINARY)
        kernel = np.ones((3, 3), np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=2)

        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
        elements = []

        for label_id in range(1, num_labels):
            area = stats[label_id, cv2.CC_STAT_AREA]
            if area < min_area:
                continue

            mask = (labels == label_id).astype(np.uint8) * 255
            if blur > 0:
                mask = cv2.GaussianBlur(mask, (blur*2+1, blur*2+1), 0)

            elem_array = np.array(pil_image.convert("RGBA")).copy()
            elem_array[:, :, 3] = mask
            elem_img = Image.fromarray(elem_array, "RGBA")

            x = int(stats[label_id, cv2.CC_STAT_LEFT])
            y = int(stats[label_id, cv2.CC_STAT_TOP])
            w = int(stats[label_id, cv2.CC_STAT_WIDTH])
            h = int(stats[label_id, cv2.CC_STAT_HEIGHT])

            elements.append({
                "name": f"元素_{label_id}",
                "image": elem_img,
                "type": "element",
                "x": x,
                "y": y,
                "width": w,
                "height": h,
                "area": int(area),
            })

        elements.sort(key=lambda l: l["area"], reverse=True)
        return elements

    def _easyocr_text_layers(self, pil_image):
        """使用 EasyOCR 检测文字区域并独立成层"""
        try:
            import easyocr
            reader = easyocr.Reader(['ch_sim', 'en'], gpu=torch.cuda.is_available())
            results = reader.readtext(np.array(pil_image))

            text_layers = []
            img_rgba = pil_image.convert("RGBA")

            for idx, (bbox, text, conf) in enumerate(results):
                if conf < 0.5:
                    continue

                xs = [int(p[0]) for p in bbox]
                ys = [int(p[1]) for p in bbox]
                x_min = max(0, min(xs) - 5)
                y_min = max(0, min(ys) - 5)
                x_max = min(pil_image.width, max(xs) + 5)
                y_max = min(pil_image.height, max(ys) + 5)

                text_layer = Image.new("RGBA", pil_image.size, (0, 0, 0, 0))
                text_region = img_rgba.crop((x_min, y_min, x_max, y_max))
                text_layer.paste(text_region, (x_min, y_min))

                text_layers.append({
                    "name": f"文字_{idx+1}_{text[:8]}",
                    "image": text_layer,
                    "type": "text",
                    "x": x_min,
                    "y": y_min,
                })
            return text_layers
        except Exception as e:
            print(f"[Tikpan PSD] 文字检测失败: {e}")
            return []

    def _build_layer_list(self, original, bg, subject, elements, texts):
        """构建完整图层列表（自下而上）"""
        layers = [{
            "name": "原图_参考",
            "image": original.convert("RGBA"),
            "type": "reference",
            "visible": False,
            "group": None,
        }]

        if bg is not None:
            layers.append({
                "name": "背景",
                "image": bg,
                "type": "background",
                "visible": True,
                "group": "背景层",
            })

        # 智能命名元素
        img_width, img_height = original.size
        for idx, elem in enumerate(elements):
            smart_name = self._generate_smart_name(elem, idx, img_width, img_height)
            layers.append({
                "name": smart_name,
                "image": elem["image"],
                "type": elem.get("type", "element"),
                "visible": True,
                "group": "产品元素",
            })

        if not elements and subject is not None:
            layers.append({
                "name": "主体",
                "image": subject,
                "type": "subject",
                "visible": True,
                "group": "产品元素",
            })

        for text in texts:
            layers.append({
                "name": text["name"],
                "image": text["image"],
                "type": "text",
                "visible": True,
                "group": "文字层",
            })

        return layers

    def _generate_smart_name(self, elem, idx, img_width, img_height):
        """智能生成图层名称：根据位置、大小、索引"""
        area = elem.get("area", 0)
        x = elem.get("x", 0)
        y = elem.get("y", 0)

        # 判断大小
        total_pixels = img_width * img_height
        size_ratio = area / total_pixels if total_pixels > 0 else 0

        if size_ratio > 0.3:
            size_label = "主产品"
        elif size_ratio > 0.1:
            size_label = "大元素"
        elif size_ratio > 0.02:
            size_label = "元素"
        else:
            size_label = "小装饰"

        # 判断位置（九宫格）
        x_center = x + elem.get("width", 0) / 2 if "width" in elem else x
        y_center = y + elem.get("height", 0) / 2 if "height" in elem else y

        x_ratio = x_center / img_width if img_width > 0 else 0.5
        y_ratio = y_center / img_height if img_height > 0 else 0.5

        if 0.35 < x_ratio < 0.65 and 0.35 < y_ratio < 0.65:
            pos_label = "中心"
        elif x_ratio < 0.35 and y_ratio < 0.35:
            pos_label = "左上"
        elif x_ratio > 0.65 and y_ratio < 0.35:
            pos_label = "右上"
        elif x_ratio < 0.35 and y_ratio > 0.65:
            pos_label = "左下"
        elif x_ratio > 0.65 and y_ratio > 0.65:
            pos_label = "右下"
        elif x_ratio < 0.35:
            pos_label = "左侧"
        elif x_ratio > 0.65:
            pos_label = "右侧"
        elif y_ratio < 0.35:
            pos_label = "顶部"
        elif y_ratio > 0.65:
            pos_label = "底部"
        else:
            pos_label = "中部"

        # 组合名称
        if size_ratio > 0.3:
            return f"{size_label}_{pos_label}"
        else:
            return f"{size_label}_{pos_label}_{idx+1}"

    def save_as_psd(self, layers, filename, image_size):
        """使用 pytoshop 保存为分层 PSD（支持图层分组）"""
        from pytoshop import enums
        from pytoshop.user import nested_layers
        import pytoshop.packbits  # 确保 packbits 模块被导入

        counter = 1
        base = self._sanitize_filename(filename)
        filepath = os.path.join(self.output_dir, f"{base}.psd")
        while os.path.exists(filepath):
            filepath = os.path.join(self.output_dir, f"{base}_{counter:04d}.psd")
            counter += 1

        width, height = image_size

        # 按分组组织图层
        grouped_layers = self._organize_layers_by_group(layers, width, height)

        psd_data = nested_layers.nested_layers_to_psd(
            layers=grouped_layers,
            color_mode=enums.ColorMode.rgb,
            size=(height, width),
        )
        with open(filepath, 'wb') as f:
            psd_data.write(f)
        return filepath

    def _organize_layers_by_group(self, layers, width, height):
        """将图层按分组组织成嵌套结构"""
        from pytoshop.user import nested_layers

        # 收集所有分组
        groups = {}
        ungrouped = []

        for layer_info in layers:
            group_name = layer_info.get("group")
            if group_name:
                if group_name not in groups:
                    groups[group_name] = []
                groups[group_name].append(layer_info)
            else:
                ungrouped.append(layer_info)

        # 构建 PSD 图层列表（自下而上）
        psd_layers = []

        # 先添加未分组的图层
        for layer_info in ungrouped:
            psd_layer = self._create_psd_layer(layer_info, width, height)
            psd_layers.append(psd_layer)

        # 添加分组图层
        for group_name in ["背景层", "产品元素", "文字层"]:
            if group_name in groups:
                group_layers = []
                for layer_info in groups[group_name]:
                    psd_layer = self._create_psd_layer(layer_info, width, height)
                    group_layers.append(psd_layer)

                # 创建图层组
                if group_layers:
                    group = nested_layers.Group(
                        name=group_name,
                        visible=True,
                        layers=group_layers
                    )
                    psd_layers.append(group)

        return psd_layers

    def _create_psd_layer(self, layer_info, width, height):
        """创建单个 PSD 图层"""
        from pytoshop.user import nested_layers

        layer_img = layer_info["image"]
        if layer_img.mode != "RGBA":
            layer_img = layer_img.convert("RGBA")
        if layer_img.size != (width, height):
            canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            canvas.paste(layer_img, (0, 0))
            layer_img = canvas

        arr = np.array(layer_img)
        psd_layer = nested_layers.Image(
            name=layer_info["name"],
            visible=layer_info.get("visible", True),
            opacity=255,
            top=0, left=0, bottom=height, right=width,
            channels={
                -1: arr[:, :, 3],
                0: arr[:, :, 0],
                1: arr[:, :, 1],
                2: arr[:, :, 2],
            }
        )
        return psd_layer

    def create_preview(self, layers, image_size):
        """生成图层信息预览图（带缩略图）"""
        width, height = image_size

        # 计算预览图尺寸
        preview_width = max(800, width)
        preview_height = max(600, len(layers) * 80 + 50)

        preview = Image.new("RGB", (preview_width, preview_height), (45, 47, 52))
        draw = ImageDraw.Draw(preview)

        # 标题
        draw.text((20, 15), "PSD 图层预览", fill=(255, 255, 255))
        draw.text((20, 35), "=" * 80, fill=(100, 100, 100))

        y = 60
        colors = [(255,100,100),(100,255,100),(100,200,255),(255,200,50),(200,100,255),(100,220,200)]

        for i, layer in enumerate(layers):
            if layer["type"] == "reference":
                continue

            # 绘制缩略图
            thumb_size = 60
            try:
                layer_img = layer["image"]
                if layer_img.mode != "RGBA":
                    layer_img = layer_img.convert("RGBA")

                # 缩放到缩略图大小
                layer_img.thumbnail((thumb_size, thumb_size), Image.Resampling.LANCZOS)

                # 创建带边框的缩略图背景
                thumb_bg = Image.new("RGBA", (thumb_size, thumb_size), (60, 62, 67))

                # 居中粘贴缩略图
                offset_x = (thumb_size - layer_img.width) // 2
                offset_y = (thumb_size - layer_img.height) // 2
                thumb_bg.paste(layer_img, (offset_x, offset_y), layer_img)

                # 粘贴到预览图
                preview.paste(thumb_bg, (15, y), thumb_bg)

                # 绘制边框
                draw.rectangle([15, y, 15+thumb_size, y+thumb_size], outline=(100, 100, 100), width=1)
            except Exception as e:
                # 如果缩略图生成失败，显示颜色块
                color = colors[i % len(colors)]
                draw.rectangle([15, y, 15+thumb_size, y+thumb_size], fill=color)

            # 图层信息
            color = colors[i % len(colors)]
            x_text = 90

            # 图层名称
            layer_name = layer['name']
            draw.text((x_text, y+5), f"L{i}: {layer_name}", fill=(255, 255, 255))

            # 图层类型和分组
            layer_type = layer.get('type', '-')
            layer_group = layer.get('group', '未分组')
            info_text = f"类型: {layer_type} | 分组: {layer_group}"
            draw.text((x_text, y+25), info_text, fill=(180, 180, 180))

            # 可见性
            visible = "✓ 可见" if layer.get('visible', True) else "✗ 隐藏"
            draw.text((x_text, y+45), visible, fill=(100, 255, 100) if layer.get('visible', True) else (255, 100, 100))

            y += 75

        arr = np.array(preview).astype(np.float32) / 255.0
        return torch.from_numpy(arr).unsqueeze(0)

    def _sanitize_filename(self, filename):
        filename = os.path.splitext(filename)[0]
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        return filename.strip() or "output"
