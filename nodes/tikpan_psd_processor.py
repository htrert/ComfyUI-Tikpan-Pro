"""
Tikpan PSD 分层处理器（商业级）
- 经济档: BiRefNet 抠图 + cv2 连通域 + PaddleOCR
- 标准档: BiRefNet + SAM2 自动多尺度 + PaddleOCR
- 极致档: BiRefNet + GroundingDINO+SAM2 语义分割 + SAM2 补漏 + LaMa Inpainting + PaddleOCR
"""
import os
import re
import numpy as np
import torch
from PIL import Image, ImageDraw

from .tikpan_segmentation_models import (
    birefnet_matting,
    birefnet_portrait_matting,
    get_sam2_predictor,
    get_sam2_auto_generator,
    gdino_detect,
    paddle_ocr_detect,
    detect_qrcodes,
    cluster_text_by_size,
    extract_color_blocks,
    color_name,
    get_scene_prompt,
    auto_detect_scene,
    GDINO_PROMPT_PRODUCT,
)


class PSDLayerProcessor:
    """PSD 分层处理器 - 三档统一接口"""

    def __init__(self, output_dir):
        self.output_dir = output_dir

    # ===================== 三档入口 =====================

    def process_economy(self, pil_image, min_area, blur, detect_text, pbar, scene="auto"):
        """经济档：BiRefNet 抠主体 + cv2 连通域分元素 + PaddleOCR"""
        scene = self._resolve_scene(pil_image, scene)
        print(f"[Tikpan PSD] 经济档（BiRefNet + cv2）处理中... 场景={scene}")
        pbar.update(10)

        subject_mask = self._matting(pil_image, scene=scene)
        pbar.update(25)

        bg_layer = self._make_background_from_mask(pil_image, subject_mask, do_inpaint=False)
        elements = self._cv2_split_subject(pil_image, subject_mask, min_area, blur)
        pbar.update(50)

        # 场景增强（经济档只做轻量级：二维码 + 文字分组）
        qr_elements = self._qrcode_layers(pil_image) if scene in ("ecom_item", "all") else []
        elements = elements + qr_elements
        pbar.update(60)

        texts = self._ocr_text_layers(pil_image, group_by_size=(scene in ("ecom_banner", "all"))) if detect_text else []
        pbar.update(75)

        return self._build_layer_list(pil_image, bg_layer, None, elements, texts)

    def process_standard(self, pil_image, min_area, blur, detect_text, do_inpaint, pbar, premium=False, scene="auto"):
        """标准档：BiRefNet + SAM2 自动多尺度 + PaddleOCR + 场景增强"""
        scene = self._resolve_scene(pil_image, scene)
        print(f"[Tikpan PSD] 标准档（BiRefNet + SAM2 自动）处理中... 场景={scene}")
        pbar.update(10)

        subject_mask = self._matting(pil_image, scene=scene)
        pbar.update(25)

        elements_masks = self._sam2_auto_segment(pil_image, min_area, premium=False)
        elements_masks = self._dedupe_masks(elements_masks, iou_threshold=0.6)
        pbar.update(50)

        elements = self._masks_to_elements(pil_image, elements_masks, blur, do_inpaint=do_inpaint)
        bg_layer = self._make_background_from_all(
            pil_image, subject_mask, elements_masks, do_inpaint=do_inpaint
        )
        pbar.update(60)

        # 场景增强
        elements = elements + self._scene_extras(pil_image, scene, min_area, blur, premium=False)
        pbar.update(65)

        texts = self._ocr_text_layers(pil_image, group_by_size=(scene in ("ecom_banner", "all"))) if detect_text else []
        pbar.update(75)

        return self._build_layer_list(pil_image, bg_layer, None, elements, texts)

    def process_premium(self, pil_image, min_area, blur, detect_text, pbar, scene="auto"):
        """极致档：BiRefNet + GroundingDINO+SAM2 语义分割 + LaMa + 全场景增强"""
        scene = self._resolve_scene(pil_image, scene)
        print(f"[Tikpan PSD] 极致档（BiRefNet + GroundingDINO+SAM2 + LaMa）处理中... 场景={scene}")
        pbar.update(10)

        subject_mask = self._matting(pil_image, scene=scene)
        pbar.update(20)

        # 1) 语义分割（带 label），用对应场景的 prompt
        scene_prompt = get_scene_prompt(scene) if scene != "auto" else GDINO_PROMPT_PRODUCT
        try:
            semantic = self._gdino_sam2_segment(pil_image, min_area, prompt=scene_prompt)
            print(f"[Tikpan PSD] GroundingDINO 语义分割: {len(semantic)} 个元素")
        except Exception as e:
            print(f"[Tikpan PSD] GroundingDINO 失败，跳过语义分割: {e}")
            semantic = []
        pbar.update(40)

        # 2) SAM2 密集自动分割补漏
        auto = self._sam2_auto_segment(pil_image, min_area, premium=True)
        pbar.update(50)

        # 3) 合并去重（语义优先）
        all_masks = self._dedupe_masks(semantic + auto, iou_threshold=0.6)
        print(f"[Tikpan PSD] 合并去重后: {len(all_masks)} 个元素")
        pbar.update(60)

        elements = self._masks_to_elements(pil_image, all_masks, blur, do_inpaint=True)
        bg_layer = self._make_background_from_all(
            pil_image, subject_mask, all_masks, do_inpaint=True
        )
        pbar.update(65)

        # 4) 场景增强（极致档全量启用）
        elements = elements + self._scene_extras(pil_image, scene, min_area, blur, premium=True)
        pbar.update(75)

        texts = self._ocr_text_layers(
            pil_image,
            group_by_size=(scene in ("ecom_banner", "all", "ecom_item"))
        ) if detect_text else []
        pbar.update(82)

        return self._build_layer_list(pil_image, bg_layer, None, elements, texts)

    # ===================== 场景路由 =====================

    def _resolve_scene(self, pil_image, scene):
        """auto 时调用 auto_detect_scene，否则原样返回。"""
        if scene != "auto":
            return scene
        try:
            detected = auto_detect_scene(pil_image)
            print(f"[Tikpan PSD] 自动检测场景: {detected}")
            return detected
        except Exception as e:
            print(f"[Tikpan PSD] 场景自动检测失败 ({e})，回退到 ecom_item")
            return "ecom_item"

    def _scene_extras(self, pil_image, scene, min_area, blur, premium=False):
        """根据场景启用对应增强模块，返回额外的 elements 列表。"""
        extras = []

        # 二维码 - 电商场景启用
        if scene in ("ecom_item", "ecom_banner", "all"):
            extras.extend(self._qrcode_layers(pil_image))

        # 品牌色块 - 海报/Banner 启用（极致档才做，否则太多色块层）
        if premium and scene in ("ecom_banner", "all"):
            extras.extend(self._color_block_layers(pil_image, n_clusters=5))

        return extras

    # ===================== 抠图 =====================

    def _matting(self, pil_image, scene=None):
        """主体抠图。人物场景用 BiRefNet-Portrait，其他用通用版。失败降级 rembg。"""
        if scene == "portrait":
            try:
                return birefnet_portrait_matting(pil_image)
            except Exception as e:
                print(f"[Tikpan PSD] BiRefNet-Portrait 不可用 ({e})，降级通用 BiRefNet")
        try:
            return birefnet_matting(pil_image)
        except Exception as e:
            print(f"[Tikpan PSD] BiRefNet 不可用 ({e})，降级到 rembg")
            return self._rembg_matting(pil_image)

    def _rembg_matting(self, pil_image):
        from rembg import remove, new_session
        session = new_session("isnet-general-use")
        subject_rgba = remove(pil_image, session=session).convert("RGBA")
        return np.array(subject_rgba)[:, :, 3]

    # ===================== SAM2 自动分割 =====================

    def _sam2_auto_segment(self, pil_image, min_area, premium=False):
        """返回 list[{segmentation, bbox(x,y,w,h), area}]"""
        try:
            generator = get_sam2_auto_generator(premium=premium, min_area=min_area)
        except Exception as e:
            print(f"[Tikpan PSD] SAM2 不可用 ({e})")
            return []

        img_array = np.array(pil_image.convert("RGB"))
        raw = generator.generate(img_array)
        print(f"[Tikpan PSD] SAM2 原始候选: {len(raw)} 个")

        h, w = img_array.shape[:2]
        full_area = h * w
        filtered = []
        for m in raw:
            area = int(m.get("area", 0))
            if area < min_area:
                continue
            if area > full_area * 0.9:
                continue
            seg = m["segmentation"].astype(bool)
            bbox = m.get("bbox", [0, 0, w, h])
            filtered.append({
                "segmentation": seg,
                "bbox": [int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])],
                "area": area,
                "source": "sam2_auto",
            })
        return filtered

    # ===================== GroundingDINO + SAM2 语义分割 =====================

    def _gdino_sam2_segment(self, pil_image, min_area, prompt=None):
        """文本提示驱动的精确分割。返回 list[{segmentation, bbox, area, label, score}]"""
        detections = gdino_detect(
            pil_image,
            prompt or GDINO_PROMPT_PRODUCT,
            box_threshold=0.30,
            text_threshold=0.25,
        )
        print(f"[Tikpan PSD] GroundingDINO 检测到 {len(detections)} 个候选框")

        if not detections:
            return []

        predictor = get_sam2_predictor()
        img_array = np.array(pil_image.convert("RGB"))
        predictor.set_image(img_array)

        h, w = img_array.shape[:2]
        full_area = h * w
        results = []

        # SAM2 支持批量 box prompt
        boxes_xyxy = np.array([d["box"] for d in detections], dtype=np.float32)
        try:
            masks, scores, _ = predictor.predict(
                point_coords=None,
                point_labels=None,
                box=boxes_xyxy,
                multimask_output=False,
            )
            # masks shape: (N, 1, H, W) 或 (N, H, W)
            if masks.ndim == 4:
                masks = masks[:, 0]
        except Exception as e:
            print(f"[Tikpan PSD] SAM2 批量预测失败 ({e})，逐个回退")
            masks = []
            for box in boxes_xyxy:
                try:
                    m, _, _ = predictor.predict(
                        point_coords=None, point_labels=None,
                        box=box, multimask_output=False,
                    )
                    masks.append(m[0] if m.ndim == 3 else m)
                except Exception:
                    masks.append(np.zeros((h, w), dtype=bool))
            masks = np.stack(masks) if masks else np.zeros((0, h, w), dtype=bool)

        for det, mask in zip(detections, masks):
            seg = mask.astype(bool)
            area = int(seg.sum())
            if area < min_area or area > full_area * 0.9:
                continue
            x1, y1, x2, y2 = det["box"]
            results.append({
                "segmentation": seg,
                "bbox": [int(x1), int(y1), int(x2 - x1), int(y2 - y1)],
                "area": area,
                "label": det["label"],
                "score": det["score"],
                "source": "gdino_sam2",
            })

        return results

    # ===================== Mask 去重 =====================

    def _dedupe_masks(self, masks, iou_threshold=0.6):
        """按 area 降序，去除高 IoU 重叠；保留"大物体里的小细节"。"""
        if not masks:
            return []
        masks = sorted(masks, key=lambda m: m["area"], reverse=True)

        kept = []
        for m in masks:
            seg = m["segmentation"]
            area = m["area"]
            is_dup = False
            for k in kept:
                kseg = k["segmentation"]
                inter = np.logical_and(seg, kseg).sum()
                if inter == 0:
                    continue
                union = np.logical_or(seg, kseg).sum()
                iou = inter / union if union else 0
                containment = inter / area if area else 0

                if iou > 0.85:
                    is_dup = True
                    break
                if iou > iou_threshold and containment < 0.85:
                    is_dup = True
                    break
            if not is_dup:
                kept.append(m)
        return kept

    # ===================== Mask -> Elements =====================

    def _masks_to_elements(self, pil_image, masks, blur, do_inpaint=False):
        """把 mask 列表转成图层元素。带 label 用语义名，否则走位置/大小命名。"""
        elements = []
        img_w, img_h = pil_image.size
        img_rgba = np.array(pil_image.convert("RGBA"))

        for idx, m in enumerate(masks):
            seg = m["segmentation"].astype(np.uint8) * 255
            if blur > 0:
                import cv2
                seg = cv2.GaussianBlur(seg, (blur*2+1, blur*2+1), 0)

            elem_arr = img_rgba.copy()
            elem_arr[:, :, 3] = seg

            if do_inpaint:
                elem_arr = self._inpaint_element(pil_image, seg, elem_arr)

            elem_img = Image.fromarray(elem_arr, "RGBA")

            bbox = m.get("bbox", [0, 0, img_w, img_h])
            x, y = int(bbox[0]), int(bbox[1])
            w = int(bbox[2]) if len(bbox) >= 4 else int(bbox[2] - x)
            h = int(bbox[3]) if len(bbox) >= 4 else int(bbox[3] - y)

            label = m.get("label")
            elem_dict = {
                "image": elem_img,
                "type": "element",
                "x": x, "y": y, "width": w, "height": h,
                "area": m.get("area", 0),
                "label": label,
                "score": m.get("score"),
            }
            elem_dict["name"] = self._name_element(elem_dict, idx, img_w, img_h)
            elements.append(elem_dict)

        elements.sort(key=lambda l: l["area"], reverse=True)
        return elements

    def _name_element(self, elem, idx, img_w, img_h):
        """带 label 用语义名（如 logo_左上_1），否则走位置/大小启发式命名"""
        label = elem.get("label")
        if label:
            label_clean = re.sub(r'\s+', '_', label.strip())
            pos = self._position_label(elem, img_w, img_h)
            return f"{label_clean}_{pos}_{idx+1}"
        return self._generate_smart_name(elem, idx, img_w, img_h)

    def _position_label(self, elem, img_w, img_h):
        x = elem.get("x", 0)
        y = elem.get("y", 0)
        x_center = x + elem.get("width", 0) / 2
        y_center = y + elem.get("height", 0) / 2
        x_ratio = x_center / img_w if img_w else 0.5
        y_ratio = y_center / img_h if img_h else 0.5

        if 0.35 < x_ratio < 0.65 and 0.35 < y_ratio < 0.65:
            return "中心"
        if x_ratio < 0.35 and y_ratio < 0.35:
            return "左上"
        if x_ratio > 0.65 and y_ratio < 0.35:
            return "右上"
        if x_ratio < 0.35 and y_ratio > 0.65:
            return "左下"
        if x_ratio > 0.65 and y_ratio > 0.65:
            return "右下"
        if x_ratio < 0.35:
            return "左侧"
        if x_ratio > 0.65:
            return "右侧"
        if y_ratio < 0.35:
            return "顶部"
        if y_ratio > 0.65:
            return "底部"
        return "中部"

    # ===================== 背景层 =====================

    def _make_background_from_mask(self, pil_image, subject_mask, do_inpaint=False):
        """单 mask 取反作为背景。"""
        bg_alpha = 255 - subject_mask.astype(np.uint8)
        bg_arr = np.array(pil_image.convert("RGBA"))
        bg_arr[:, :, 3] = bg_alpha
        if do_inpaint:
            bg_arr = self._inpaint_element(pil_image, 255 - bg_alpha, bg_arr, fill_holes=True)
        return Image.fromarray(bg_arr, "RGBA")

    def _make_background_from_all(self, pil_image, subject_mask, masks, do_inpaint=False):
        """合并所有前景 mask 后取反。"""
        h, w = pil_image.size[1], pil_image.size[0]
        combined = subject_mask.astype(bool) if subject_mask is not None else np.zeros((h, w), dtype=bool)
        for m in masks:
            combined = np.logical_or(combined, m["segmentation"])

        bg_alpha = (~combined).astype(np.uint8) * 255
        bg_arr = np.array(pil_image.convert("RGBA"))
        bg_arr[:, :, 3] = bg_alpha
        if do_inpaint:
            fg_mask = combined.astype(np.uint8) * 255
            bg_arr = self._inpaint_element(pil_image, fg_mask, bg_arr, fill_holes=True)
        return Image.fromarray(bg_arr, "RGBA")

    # ===================== cv2 连通域（经济档） =====================

    def _cv2_split_subject(self, pil_image, subject_mask, min_area, blur):
        """在 BiRefNet 主体 mask 内做连通域分块。"""
        import cv2
        _, binary = cv2.threshold(subject_mask, 127, 255, cv2.THRESH_BINARY)
        kernel = np.ones((3, 3), np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=2)

        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
        elements = []
        img_w, img_h = pil_image.size
        img_rgba = np.array(pil_image.convert("RGBA"))

        for label_id in range(1, num_labels):
            area = int(stats[label_id, cv2.CC_STAT_AREA])
            if area < min_area:
                continue

            mask = (labels == label_id).astype(np.uint8) * 255
            if blur > 0:
                mask = cv2.GaussianBlur(mask, (blur*2+1, blur*2+1), 0)

            elem_arr = img_rgba.copy()
            elem_arr[:, :, 3] = mask
            elem_img = Image.fromarray(elem_arr, "RGBA")

            x = int(stats[label_id, cv2.CC_STAT_LEFT])
            y = int(stats[label_id, cv2.CC_STAT_TOP])
            w = int(stats[label_id, cv2.CC_STAT_WIDTH])
            h = int(stats[label_id, cv2.CC_STAT_HEIGHT])

            elem = {
                "image": elem_img,
                "type": "element",
                "x": x, "y": y, "width": w, "height": h,
                "area": area,
                "label": None,
            }
            elem["name"] = self._name_element(elem, len(elements), img_w, img_h)
            elements.append(elem)

        elements.sort(key=lambda l: l["area"], reverse=True)
        return elements

    # ===================== OCR =====================

    def _ocr_text_layers(self, pil_image, group_by_size=False):
        """优先 PaddleOCR（中文准），失败降级 EasyOCR。group_by_size=True 时按字号分组。"""
        results = []
        try:
            results = paddle_ocr_detect(pil_image)
        except Exception as e:
            print(f"[Tikpan PSD] PaddleOCR 不可用 ({e})，降级 EasyOCR")
            results = self._easyocr_raw(pil_image)

        if not results:
            return []

        if group_by_size:
            return self._build_text_layers_grouped(pil_image, results)
        return self._build_text_layers(pil_image, results)

    def _easyocr_raw(self, pil_image):
        try:
            import easyocr
            reader = easyocr.Reader(['ch_sim', 'en'], gpu=torch.cuda.is_available())
            raw = reader.readtext(np.array(pil_image))
            results = []
            for bbox, text, conf in raw:
                if conf < 0.5:
                    continue
                xs = [int(p[0]) for p in bbox]
                ys = [int(p[1]) for p in bbox]
                results.append({
                    "bbox": [min(xs), min(ys), max(xs), max(ys)],
                    "text": text,
                    "score": float(conf),
                })
            return results
        except Exception as e:
            print(f"[Tikpan PSD] OCR 全部失败: {e}")
            return []

    def _build_text_layers(self, pil_image, results):
        """每条 OCR 一个图层。"""
        text_layers = []
        img_rgba = pil_image.convert("RGBA")
        for idx, r in enumerate(results):
            text = r.get("text", "").strip()
            score = r.get("score", 1.0)
            if not text or score < 0.5:
                continue
            x1, y1, x2, y2 = r["bbox"]
            x_min = max(0, x1 - 5)
            y_min = max(0, y1 - 5)
            x_max = min(pil_image.width, x2 + 5)
            y_max = min(pil_image.height, y2 + 5)

            text_layer = Image.new("RGBA", pil_image.size, (0, 0, 0, 0))
            region = img_rgba.crop((x_min, y_min, x_max, y_max))
            text_layer.paste(region, (x_min, y_min))

            text_layers.append({
                "name": f"文字_{idx+1}_{text[:8]}",
                "image": text_layer,
                "type": "text",
                "x": x_min,
                "y": y_min,
            })
        return text_layers

    def _build_text_layers_grouped(self, pil_image, results):
        """按字号分组：标题/副标题/正文/价格/小字 → 每组一个合并图层。"""
        groups = cluster_text_by_size(results, pil_image.height)
        if not groups:
            return []

        text_layers = []
        img_rgba = pil_image.convert("RGBA")

        # 固定顺序，让 PS 里看着自然
        order = ["标题", "副标题", "正文", "价格", "小字"]
        for tier in order:
            items = groups.get(tier)
            if not items:
                continue

            tier_layer = Image.new("RGBA", pil_image.size, (0, 0, 0, 0))
            texts_preview = []
            for r in items:
                text = r.get("text", "").strip()
                if not text:
                    continue
                x1, y1, x2, y2 = r["bbox"]
                x_min = max(0, x1 - 5)
                y_min = max(0, y1 - 5)
                x_max = min(pil_image.width, x2 + 5)
                y_max = min(pil_image.height, y2 + 5)
                region = img_rgba.crop((x_min, y_min, x_max, y_max))
                tier_layer.paste(region, (x_min, y_min))
                texts_preview.append(text[:4])

            preview = "_".join(texts_preview[:2]) if texts_preview else ""
            text_layers.append({
                "name": f"文字_{tier}_{preview}",
                "image": tier_layer,
                "type": "text",
                "x": 0,
                "y": 0,
            })
        return text_layers

    # ===================== 二维码层 =====================

    def _qrcode_layers(self, pil_image):
        """检测二维码/条形码，每个独立成层。"""
        try:
            qrcodes = detect_qrcodes(pil_image)
        except Exception as e:
            print(f"[Tikpan PSD] 二维码检测失败: {e}")
            return []
        if not qrcodes:
            return []

        elements = []
        img_rgba = pil_image.convert("RGBA")
        for idx, q in enumerate(qrcodes):
            x1, y1, x2, y2 = q["bbox"]
            pad = 4
            x1 = max(0, x1 - pad); y1 = max(0, y1 - pad)
            x2 = min(pil_image.width, x2 + pad); y2 = min(pil_image.height, y2 + pad)

            layer = Image.new("RGBA", pil_image.size, (0, 0, 0, 0))
            region = img_rgba.crop((x1, y1, x2, y2))
            layer.paste(region, (x1, y1))

            kind = q.get("type", "qrcode")
            preview = q.get("text", "")[:12]
            name = f"{kind}_{idx+1}_{preview}" if preview else f"{kind}_{idx+1}"
            elements.append({
                "name": name,
                "image": layer,
                "type": "element",
                "x": x1, "y": y1,
                "width": x2 - x1,
                "height": y2 - y1,
                "area": (x2 - x1) * (y2 - y1),
                "label": kind,
            })
        return elements

    # ===================== 品牌色块层 =====================

    def _color_block_layers(self, pil_image, n_clusters=5):
        """k-means 色块。每个主色块独立成层。"""
        try:
            blocks = extract_color_blocks(pil_image, n_clusters=n_clusters, min_area_ratio=0.03)
        except Exception as e:
            print(f"[Tikpan PSD] 色块提取失败: {e}")
            return []
        if not blocks:
            return []

        elements = []
        img_rgba = np.array(pil_image.convert("RGBA"))
        for idx, b in enumerate(blocks):
            mask = b["mask"]
            elem_arr = img_rgba.copy()
            elem_arr[:, :, 3] = (mask.astype(np.uint8) * 255)

            ys, xs = np.where(mask)
            if len(xs) == 0:
                continue
            x1, y1 = int(xs.min()), int(ys.min())
            x2, y2 = int(xs.max()), int(ys.max())

            elements.append({
                "name": f"色块_{color_name(b['color'])}_{idx+1}",
                "image": Image.fromarray(elem_arr, "RGBA"),
                "type": "element",
                "x": x1, "y": y1,
                "width": x2 - x1, "height": y2 - y1,
                "area": int(b["area"]),
                "label": "color_block",
            })
        return elements

    # ===================== Inpainting =====================

    def _inpaint_element(self, pil_image, mask, elem_array, fill_holes=False):
        """使用 LaMa 补全被遮挡区域。失败原样返回。"""
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

    # ===================== 图层列表与命名 =====================

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

        for elem in elements:
            layers.append({
                "name": elem["name"],
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
        """无 label 时的命名启发式：根据位置、大小、索引。"""
        area = elem.get("area", 0)
        total_pixels = img_width * img_height
        size_ratio = area / total_pixels if total_pixels else 0

        if size_ratio > 0.3:
            size_label = "主产品"
        elif size_ratio > 0.1:
            size_label = "大元素"
        elif size_ratio > 0.02:
            size_label = "元素"
        else:
            size_label = "小装饰"

        pos_label = self._position_label(elem, img_width, img_height)
        if size_ratio > 0.3:
            return f"{size_label}_{pos_label}"
        return f"{size_label}_{pos_label}_{idx+1}"

    # ===================== PSD 输出 =====================

    def save_as_psd(self, layers, filename, image_size):
        """使用 psd-tools 保存为分层 PSD（PS 2023 兼容）"""
        from psd_tools import PSDImage
        from psd_tools.api.layers import PixelLayer, Group
        from psd_tools.constants import Compression

        counter = 1
        base = self._sanitize_filename(filename)
        filepath = os.path.join(self.output_dir, f"{base}.psd")
        while os.path.exists(filepath):
            filepath = os.path.join(self.output_dir, f"{base}_{counter:04d}.psd")
            counter += 1

        width, height = image_size
        psd = PSDImage.new(mode="RGB", size=(width, height), color=255)

        grouped = {"背景层": [], "产品元素": [], "文字层": []}
        ungrouped = []
        for layer_info in layers:
            group_name = layer_info.get("group")
            if group_name in grouped:
                grouped[group_name].append(layer_info)
            else:
                ungrouped.append(layer_info)

        for layer_info in ungrouped:
            self._add_pixel_layer(psd, psd, layer_info, width, height, Compression, PixelLayer)

        for group_name in ["背景层", "产品元素", "文字层"]:
            if not grouped[group_name]:
                continue
            group = Group.new(parent=psd, name=group_name, open_folder=True)
            for layer_info in grouped[group_name]:
                self._add_pixel_layer(psd, group, layer_info, width, height, Compression, PixelLayer)

        psd.save(filepath, encoding="utf-8")
        return filepath

    def _add_pixel_layer(self, psd, parent, layer_info, width, height, Compression, PixelLayer):
        layer_img = layer_info["image"]
        if layer_img.mode != "RGBA":
            layer_img = layer_img.convert("RGBA")
        if layer_img.size != (width, height):
            canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            canvas.paste(layer_img, (0, 0))
            layer_img = canvas

        layer = PixelLayer.frompil(
            image=layer_img,
            parent=parent,
            name=layer_info["name"],
            top=0,
            left=0,
            compression=Compression.RLE,
        )
        layer.visible = layer_info.get("visible", True)
        return layer

    def create_preview(self, layers, image_size):
        """生成图层信息预览图"""
        width, height = image_size
        preview_width = max(800, width)
        preview_height = max(600, len(layers) * 80 + 50)

        preview = Image.new("RGB", (preview_width, preview_height), (45, 47, 52))
        draw = ImageDraw.Draw(preview)

        try:
            draw.text((20, 15), "PSD Layer Preview", fill=(255, 255, 255))
            draw.text((20, 35), "=" * 80, fill=(100, 100, 100))
        except Exception as e:
            print(f"[Tikpan PSD] 预览图标题绘制失败: {e}")

        y = 60
        colors = [(255,100,100),(100,255,100),(100,200,255),(255,200,50),(200,100,255),(100,220,200)]

        for i, layer in enumerate(layers):
            if layer["type"] == "reference":
                continue
            thumb_size = 60
            try:
                layer_img = layer["image"]
                if layer_img.mode != "RGBA":
                    layer_img = layer_img.convert("RGBA")
                layer_img.thumbnail((thumb_size, thumb_size), Image.Resampling.LANCZOS)
                thumb_bg = Image.new("RGBA", (thumb_size, thumb_size), (60, 62, 67))
                offset_x = (thumb_size - layer_img.width) // 2
                offset_y = (thumb_size - layer_img.height) // 2
                thumb_bg.paste(layer_img, (offset_x, offset_y), layer_img)
                preview.paste(thumb_bg, (15, y), thumb_bg)
                draw.rectangle([15, y, 15+thumb_size, y+thumb_size], outline=(100, 100, 100), width=1)
            except Exception:
                color = colors[i % len(colors)]
                draw.rectangle([15, y, 15+thumb_size, y+thumb_size], fill=color)

            x_text = 90
            try:
                ascii_name = layer['name'].encode('ascii', 'ignore').decode('ascii') or f"Layer_{i}"
                draw.text((x_text, y+5), f"L{i}: {ascii_name}", fill=(255, 255, 255))
                draw.text((x_text, y+25), f"Type: {layer.get('type', '-')}", fill=(180, 180, 180))
                vis_text = "Visible" if layer.get('visible', True) else "Hidden"
                draw.text((x_text, y+45), vis_text, fill=(100, 255, 100) if layer.get('visible', True) else (255, 100, 100))
            except Exception:
                pass
            y += 75

        arr = np.array(preview).astype(np.float32) / 255.0
        return torch.from_numpy(arr).unsqueeze(0)

    def _sanitize_filename(self, filename):
        filename = os.path.splitext(filename)[0]
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        return filename.strip() or "output"
