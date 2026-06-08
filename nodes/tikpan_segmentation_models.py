"""
Tikpan PSD 分层节点 - 模型单例加载器
所有模型按需懒加载，跨节点调用复用，避免反复占用 GPU 显存。
"""
import os
import re
import threading
import numpy as np
import torch
from PIL import Image

import folder_paths


_lock = threading.Lock()
_birefnet = None       # (model, transform)
_gdino = None          # (processor, model)
_paddleocr = None      # PaddleOCR 实例
_sam2_predictor = None # 复用给 AutomaticMaskGenerator 和 box predict


def _device():
    return "cuda" if torch.cuda.is_available() else "cpu"


def _models_dir(sub):
    path = os.path.join(folder_paths.models_dir, sub)
    os.makedirs(path, exist_ok=True)
    return path


# ---------- BiRefNet ----------

def get_birefnet():
    """返回 (model, transform)。失败抛 ImportError，由调用方决定降级。"""
    global _birefnet
    if _birefnet is not None:
        return _birefnet

    with _lock:
        if _birefnet is not None:
            return _birefnet

        try:
            from transformers import AutoModelForImageSegmentation
            from torchvision import transforms
        except ImportError as e:
            raise ImportError(f"BiRefNet 需要 transformers + torchvision: {e}")

        print("[Tikpan PSD] 加载 BiRefNet（首次约 900MB）...")
        cache_dir = _models_dir("birefnet")
        model = AutoModelForImageSegmentation.from_pretrained(
            "ZhengPeng7/BiRefNet",
            trust_remote_code=True,
            cache_dir=cache_dir,
        )
        model = model.to(_device()).eval()

        tfm = transforms.Compose([
            transforms.Resize((1024, 1024)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])

        _birefnet = (model, tfm)
        print("[Tikpan PSD] BiRefNet 加载完成")
        return _birefnet


def birefnet_matting(pil_image):
    """返回 (h, w) uint8 alpha mask（0-255）。"""
    model, tfm = get_birefnet()
    device = _device()

    pil_rgb = pil_image.convert("RGB")
    x = tfm(pil_rgb).unsqueeze(0).to(device)

    with torch.no_grad():
        pred = model(x)[-1].sigmoid().float().cpu()[0, 0].numpy()

    # resize 回原图尺寸
    pred_img = Image.fromarray((pred * 255).astype(np.uint8))
    pred_img = pred_img.resize(pil_image.size, Image.LANCZOS)
    return np.array(pred_img)


# ---------- SAM2 Predictor (共享) ----------

def get_sam2_predictor():
    global _sam2_predictor
    if _sam2_predictor is not None:
        return _sam2_predictor

    with _lock:
        if _sam2_predictor is not None:
            return _sam2_predictor

        try:
            from sam2.sam2_image_predictor import SAM2ImagePredictor
        except ImportError as e:
            raise ImportError(f"SAM2 未安装: {e}")

        print("[Tikpan PSD] 加载 SAM2 predictor...")
        # 缓存到 models/sam2
        os.environ.setdefault("HF_HOME", _models_dir("sam2_hf_cache"))
        _sam2_predictor = SAM2ImagePredictor.from_pretrained(
            "facebook/sam2.1-hiera-small",
            local_files_only=False,
            device=_device(),
        )
        print("[Tikpan PSD] SAM2 predictor 加载完成")
        return _sam2_predictor


def get_sam2_auto_generator(premium=False, min_area=2000):
    """返回 SAM2AutomaticMaskGenerator 实例。premium=True 用密集多尺度。"""
    try:
        from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator
    except ImportError as e:
        raise ImportError(f"SAM2 未安装: {e}")

    predictor = get_sam2_predictor()
    sam2_model = predictor.model

    if premium:
        return SAM2AutomaticMaskGenerator(
            model=sam2_model,
            points_per_side=64,
            pred_iou_thresh=0.7,
            stability_score_thresh=0.85,
            box_nms_thresh=0.5,
            crop_n_layers=1,
            crop_n_points_downscale_factor=2,
            min_mask_region_area=max(100, min_area // 4),
        )
    return SAM2AutomaticMaskGenerator(
        model=sam2_model,
        points_per_side=32,
        pred_iou_thresh=0.75,
        stability_score_thresh=0.88,
        box_nms_thresh=0.6,
        min_mask_region_area=max(50, min_area // 8),
    )


# ---------- GroundingDINO ----------

def get_gdino():
    """返回 (processor, model)。"""
    global _gdino
    if _gdino is not None:
        return _gdino

    with _lock:
        if _gdino is not None:
            return _gdino

        try:
            from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection
        except ImportError as e:
            raise ImportError(f"GroundingDINO 需要 transformers: {e}")

        print("[Tikpan PSD] 加载 GroundingDINO（首次约 700MB）...")
        cache_dir = _models_dir("grounding_dino")
        proc = AutoProcessor.from_pretrained(
            "IDEA-Research/grounding-dino-tiny",
            cache_dir=cache_dir,
        )
        model = AutoModelForZeroShotObjectDetection.from_pretrained(
            "IDEA-Research/grounding-dino-tiny",
            cache_dir=cache_dir,
        ).to(_device()).eval()

        _gdino = (proc, model)
        print("[Tikpan PSD] GroundingDINO 加载完成")
        return _gdino


def gdino_detect(pil_image, prompt, box_threshold=0.30, text_threshold=0.25):
    """
    返回 list[{box: [x1,y1,x2,y2], score: float, label: str}]
    prompt 必须全小写、句号分隔、末尾带句号
    """
    proc, model = get_gdino()
    device = _device()

    inputs = proc(images=pil_image, text=prompt, return_tensors="pt").to(device)
    with torch.no_grad():
        outputs = model(**inputs)

    results = proc.post_process_grounded_object_detection(
        outputs,
        inputs.input_ids,
        box_threshold=box_threshold,
        text_threshold=text_threshold,
        target_sizes=[(pil_image.height, pil_image.width)],
    )[0]

    detections = []
    for box, score, label in zip(results["boxes"], results["scores"], results["labels"]):
        b = box.cpu().numpy().astype(int)
        detections.append({
            "box": [int(b[0]), int(b[1]), int(b[2]), int(b[3])],
            "score": float(score.cpu()),
            "label": str(label).strip(),
        })
    return detections


# ---------- PaddleOCR ----------

def get_paddleocr(lang="ch"):
    """返回 PaddleOCR 实例。失败抛 ImportError，由调用方降级到 EasyOCR。"""
    global _paddleocr
    if _paddleocr is not None:
        return _paddleocr

    with _lock:
        if _paddleocr is not None:
            return _paddleocr

        try:
            from paddleocr import PaddleOCR
        except ImportError as e:
            raise ImportError(f"PaddleOCR 未安装: {e}")

        print("[Tikpan PSD] 加载 PaddleOCR（首次约 200MB）...")
        # 3.x API
        device = "gpu" if torch.cuda.is_available() else "cpu"
        try:
            _paddleocr = PaddleOCR(
                lang=lang,
                device=device,
                use_textline_orientation=False,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
            )
        except TypeError:
            # 2.x fallback
            _paddleocr = PaddleOCR(
                lang=lang,
                use_angle_cls=False,
                use_gpu=torch.cuda.is_available(),
                show_log=False,
            )
        print("[Tikpan PSD] PaddleOCR 加载完成")
        return _paddleocr


def paddle_ocr_detect(pil_image):
    """返回 list[{bbox: [x1,y1,x2,y2], text: str, score: float}]"""
    ocr = get_paddleocr()
    img_arr = np.array(pil_image.convert("RGB"))

    # 兼容 PaddleOCR 2.x 和 3.x
    try:
        # 3.x: predict() 返回 list[dict]
        result = ocr.predict(img_arr)
        if isinstance(result, list) and len(result) > 0 and isinstance(result[0], dict):
            r = result[0]
            polys = r.get("rec_polys", r.get("dt_polys", []))
            texts = r.get("rec_texts", [])
            scores = r.get("rec_scores", [])
            out = []
            for poly, txt, s in zip(polys, texts, scores):
                arr = np.asarray(poly)
                x1, y1 = arr.min(0)
                x2, y2 = arr.max(0)
                out.append({
                    "bbox": [int(x1), int(y1), int(x2), int(y2)],
                    "text": str(txt),
                    "score": float(s),
                })
            return out
    except AttributeError:
        pass

    # 2.x: ocr() 返回嵌套结构
    raw = ocr.ocr(img_arr, cls=False)
    if not raw or not raw[0]:
        return []
    out = []
    for line in raw[0]:
        bbox_poly, (txt, s) = line[0], line[1]
        arr = np.asarray(bbox_poly)
        x1, y1 = arr.min(0)
        x2, y2 = arr.max(0)
        out.append({
            "bbox": [int(x1), int(y1), int(x2), int(y2)],
            "text": str(txt),
            "score": float(s),
        })
    return out


# ---------- 场景化 GroundingDINO 提示词 ----------

# 通用产品（向后兼容）
GDINO_PROMPT_PRODUCT = (
    "product. logo. badge. button. icon. sticker. "
    "text. label. decoration. tag. character. illustration."
)

# 电商商品图（主图/白底图）：重点抓价格标/促销/二维码/包装
GDINO_PROMPT_ECOM_ITEM = (
    "product. logo. brand. label. tag. price tag. sale sticker. discount badge. "
    "coupon. promo label. qr code. barcode. box. package. bottle. container. jar. "
    "icon. button. sticker. decoration."
)

# 电商详情页/海报/Banner：重点抓 CTA/装饰/标题等版式元素
GDINO_PROMPT_ECOM_BANNER = (
    "title. headline. subtitle. text block. button. cta button. price. badge. "
    "logo. icon. ribbon. banner. frame. border. divider. ornament. pattern. "
    "decoration. illustration. character. product."
)

# 人物/生活方式：重点抓人/服饰/配件
GDINO_PROMPT_PORTRAIT = (
    "person. face. hair. hand. clothing. shirt. dress. pants. shoes. hat. "
    "glasses. jewelry. accessory. bag. watch. logo. text. decoration."
)

# 生活场景图（食物/家居）
GDINO_PROMPT_LIFESTYLE = (
    "food. dish. plate. bowl. cup. drink. bottle. plant. flower. "
    "furniture. chair. table. lamp. window. door. book. text. logo. decoration."
)

# 全场景（最大召回，会出更多层但也更多误检）
GDINO_PROMPT_ALL = (
    "product. logo. badge. button. icon. sticker. text. label. "
    "price tag. sale sticker. qr code. barcode. box. package. "
    "title. headline. subtitle. cta button. ribbon. frame. border. ornament. pattern. "
    "person. face. clothing. shoes. jewelry. accessory. "
    "food. drink. plate. cup. furniture. plant. lamp. decoration."
)

SCENE_PROMPTS = {
    "ecom_item": GDINO_PROMPT_ECOM_ITEM,
    "ecom_banner": GDINO_PROMPT_ECOM_BANNER,
    "portrait": GDINO_PROMPT_PORTRAIT,
    "lifestyle": GDINO_PROMPT_LIFESTYLE,
    "all": GDINO_PROMPT_ALL,
    "product": GDINO_PROMPT_PRODUCT,
}

# 自动场景检测用的粗类
GDINO_PROMPT_SCENE_PROBE = "person. product. food. furniture. text. logo. button."


def get_scene_prompt(scene_key):
    """根据场景 key 返回对应的 GDINO prompt。"""
    return SCENE_PROMPTS.get(scene_key, GDINO_PROMPT_PRODUCT)


def auto_detect_scene(pil_image):
    """
    用 GDINO 粗识别一遍，按检出物体的标签和占比判断场景。
    返回 scene key: ecom_item / ecom_banner / portrait / lifestyle / all
    """
    try:
        detections = gdino_detect(
            pil_image,
            GDINO_PROMPT_SCENE_PROBE,
            box_threshold=0.30,
            text_threshold=0.25,
        )
    except Exception as e:
        print(f"[Tikpan PSD] 场景自动检测失败 ({e})，回退到 all")
        return "all"

    if not detections:
        return "ecom_item"

    img_area = pil_image.width * pil_image.height
    labels = {}  # label -> total_area
    for d in detections:
        x1, y1, x2, y2 = d["box"]
        area = max(0, x2 - x1) * max(0, y2 - y1)
        labels[d["label"]] = labels.get(d["label"], 0) + area

    def ratio(name):
        return labels.get(name, 0) / img_area

    person_r = ratio("person") + ratio("face")
    food_r = ratio("food")
    furniture_r = ratio("furniture")
    text_r = ratio("text") + ratio("logo") + ratio("button")
    product_r = ratio("product")

    if person_r > 0.15:
        return "portrait"
    if food_r > 0.1 or furniture_r > 0.1:
        return "lifestyle"
    if text_r > 0.2 and product_r < 0.3:
        return "ecom_banner"
    return "ecom_item"


# ---------- 二维码/条形码检测 ----------

def detect_qrcodes(pil_image):
    """
    返回 list[{bbox: [x1,y1,x2,y2], text: str, type: 'qrcode'|'barcode'}]
    优先 pyzbar（支持二维码+条形码），失败用 cv2 QRCodeDetector。
    """
    import numpy as np
    img_arr = np.array(pil_image.convert("RGB"))

    # 1) 优先 pyzbar
    try:
        from pyzbar.pyzbar import decode, ZBarSymbol
        results = decode(img_arr)
        out = []
        for r in results:
            x, y, w, h = r.rect
            kind = "qrcode" if r.type == "QRCODE" else "barcode"
            text = r.data.decode("utf-8", errors="ignore") if r.data else ""
            out.append({
                "bbox": [int(x), int(y), int(x + w), int(y + h)],
                "text": text,
                "type": kind,
            })
        if out:
            return out
    except Exception as e:
        print(f"[Tikpan PSD] pyzbar 不可用 ({e})，尝试 cv2 QRCodeDetector")

    # 2) cv2 QRCodeDetector 降级
    try:
        import cv2
        detector = cv2.QRCodeDetector()
        retval, decoded_info, points, _ = detector.detectAndDecodeMulti(img_arr)
        if not retval or points is None:
            return []
        out = []
        for txt, pts in zip(decoded_info, points):
            pts = pts.astype(int)
            x1, y1 = pts[:, 0].min(), pts[:, 1].min()
            x2, y2 = pts[:, 0].max(), pts[:, 1].max()
            out.append({
                "bbox": [int(x1), int(y1), int(x2), int(y2)],
                "text": str(txt or ""),
                "type": "qrcode",
            })
        return out
    except Exception as e:
        print(f"[Tikpan PSD] 二维码检测失败: {e}")
        return []


# ---------- 人物专用抠图 (BiRefNet-Portrait) ----------

_birefnet_portrait = None


def get_birefnet_portrait():
    """BiRefNet 人物专用 finetune 版，发丝/皮肤边缘更准。"""
    global _birefnet_portrait
    if _birefnet_portrait is not None:
        return _birefnet_portrait

    with _lock:
        if _birefnet_portrait is not None:
            return _birefnet_portrait

        try:
            from transformers import AutoModelForImageSegmentation
            from torchvision import transforms
        except ImportError as e:
            raise ImportError(f"BiRefNet-Portrait 需要 transformers + torchvision: {e}")

        print("[Tikpan PSD] 加载 BiRefNet-Portrait（首次约 900MB）...")
        cache_dir = _models_dir("birefnet")
        model = AutoModelForImageSegmentation.from_pretrained(
            "ZhengPeng7/BiRefNet-portrait",
            trust_remote_code=True,
            cache_dir=cache_dir,
        ).to(_device()).eval()

        tfm = transforms.Compose([
            transforms.Resize((1024, 1024)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])

        _birefnet_portrait = (model, tfm)
        print("[Tikpan PSD] BiRefNet-Portrait 加载完成")
        return _birefnet_portrait


def birefnet_portrait_matting(pil_image):
    """返回 (h, w) uint8 alpha mask。人物专用，发丝/皮肤边缘更准。"""
    model, tfm = get_birefnet_portrait()
    device = _device()

    pil_rgb = pil_image.convert("RGB")
    x = tfm(pil_rgb).unsqueeze(0).to(device)

    with torch.no_grad():
        pred = model(x)[-1].sigmoid().float().cpu()[0, 0].numpy()

    pred_img = Image.fromarray((pred * 255).astype(np.uint8))
    pred_img = pred_img.resize(pil_image.size, Image.LANCZOS)
    return np.array(pred_img)


# ---------- 文字按字号聚类 ----------

def cluster_text_by_size(text_results, image_height):
    """
    输入 _ocr_text_layers 那种结果：list[{bbox: [x1,y1,x2,y2], text, score}]
    按 bbox 高度做层级聚类，返回 {tier_name: [results]}
    tier_name 取值: 标题/副标题/正文/价格/小字
    """
    if not text_results:
        return {}

    # 计算每条的高度比例
    enriched = []
    for r in text_results:
        x1, y1, x2, y2 = r["bbox"]
        h = max(1, y2 - y1)
        h_ratio = h / image_height if image_height else 0
        enriched.append({**r, "h": h, "h_ratio": h_ratio})

    # 简单阈值分级（h_ratio 比 image_height）
    groups = {"标题": [], "副标题": [], "正文": [], "小字": []}
    for r in enriched:
        text = r.get("text", "")
        if r["h_ratio"] > 0.08:
            groups["标题"].append(r)
        elif r["h_ratio"] > 0.04:
            groups["副标题"].append(r)
        elif r["h_ratio"] > 0.02:
            groups["正文"].append(r)
        else:
            groups["小字"].append(r)

    # 单独抽取「价格」组（含￥/$/¥ 或纯数字+元/折/off）
    price_pattern = re.compile(r'[¥$￥€]|\d+\.?\d*\s*(元|折|off|%)', re.IGNORECASE)
    price_group = []
    for tier in list(groups.keys()):
        keep = []
        for r in groups[tier]:
            if price_pattern.search(r.get("text", "")):
                price_group.append(r)
            else:
                keep.append(r)
        groups[tier] = keep
    if price_group:
        groups["价格"] = price_group

    # 移除空组
    return {k: v for k, v in groups.items() if v}


# ---------- 品牌色块/背景色块提取（k-means） ----------

def extract_color_blocks(pil_image, n_clusters=5, min_area_ratio=0.02):
    """
    k-means 颜色聚类。返回 list[{mask: np.bool_(h,w), color: (r,g,b), area: int, ratio: float}]
    每个聚类色，找出该颜色覆盖的像素 mask。过滤面积小于 min_area_ratio 的小色块。
    """
    import cv2
    import numpy as np

    img = np.array(pil_image.convert("RGB"))
    h, w = img.shape[:2]
    full_area = h * w

    # 降采样加速
    scale = 1.0
    if max(h, w) > 800:
        scale = 800 / max(h, w)
        img_small = cv2.resize(img, (int(w * scale), int(h * scale)))
    else:
        img_small = img

    pixels = img_small.reshape(-1, 3).astype(np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 0.5)
    _, labels, centers = cv2.kmeans(
        pixels, n_clusters, None, criteria, 3, cv2.KMEANS_PP_CENTERS
    )
    centers = centers.astype(np.uint8)

    # 对原图按最近聚类中心打 label
    pixels_full = img.reshape(-1, 3).astype(np.float32)
    dists = np.linalg.norm(pixels_full[:, None] - centers[None], axis=2)
    labels_full = dists.argmin(axis=1).reshape(h, w)

    blocks = []
    for k in range(n_clusters):
        mask = (labels_full == k)
        area = int(mask.sum())
        if area / full_area < min_area_ratio:
            continue
        # 形态学清理碎片
        mask_u8 = mask.astype(np.uint8) * 255
        kernel = np.ones((5, 5), np.uint8)
        mask_u8 = cv2.morphologyEx(mask_u8, cv2.MORPH_OPEN, kernel, iterations=1)
        mask_u8 = cv2.morphologyEx(mask_u8, cv2.MORPH_CLOSE, kernel, iterations=2)
        cleaned = mask_u8 > 127

        cleaned_area = int(cleaned.sum())
        if cleaned_area / full_area < min_area_ratio:
            continue

        rgb = tuple(int(c) for c in centers[k])
        blocks.append({
            "mask": cleaned,
            "color": rgb,
            "area": cleaned_area,
            "ratio": cleaned_area / full_area,
        })

    blocks.sort(key=lambda b: b["area"], reverse=True)
    return blocks


# 用于 color hex 命名
def color_name(rgb):
    return "#{:02X}{:02X}{:02X}".format(*rgb)


