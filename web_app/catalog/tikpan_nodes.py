from __future__ import annotations

import ast
from pathlib import Path


def field(
    key,
    field_type,
    label,
    default="",
    *,
    placeholder="",
    required=0,
    options=None,
    max_count=0,
    rows=4,
    sort_order=0,
    hint="",
    min_value=None,
    max_value=None,
    step=None,
):
    item = {
        "field_key": key,
        "field_type": field_type,
        "label": label,
        "placeholder": placeholder,
        "default_value": default,
        "required": required,
        "options": options or [],
        "max_count": max_count,
        "rows": rows,
        "sort_order": sort_order,
        "hint": hint,
    }
    if min_value is not None:
        item["min"] = min_value
    if max_value is not None:
        item["max"] = max_value
    if step is not None:
        item["step"] = step
    return item


def usage(*steps):
    return [step for step in steps if step]


NODE_DIR = Path(__file__).resolve().parents[2] / "nodes"


def _node_constant(filename, constant_name, fallback):
    path = NODE_DIR / filename
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if any(isinstance(target, ast.Name) and target.id == constant_name for target in node.targets):
                return ast.literal_eval(node.value)
    except Exception:
        return fallback
    return fallback


def _minimax_voice_label(item):
    language, name, desc, voice_id = item
    return f"{language}｜{name}｜{desc}｜{voice_id}"


def _gemini_voice_label(item):
    voice_name, style, zh_style, usage_text = item
    return f"{voice_name}｜{zh_style}｜{style}｜{usage_text}"


def _doubao_voice_label(item):
    group, name, gender, desc, voice_type = item
    return f"{group}｜{name}｜{gender}｜{desc}｜{voice_type}"


MINIMAX_SYSTEM_VOICES = _node_constant(
    "tikpan_minimax_speech.py",
    "MINIMAX_SYSTEM_VOICES",
    [
        ("中文普通话", "可靠管理者", "稳重商务男声，适合企业旁白", "Chinese (Mandarin)_Reliable_Executive"),
        ("中文普通话", "新闻主播", "标准播报风格，适合资讯解说", "Chinese (Mandarin)_News_Anchor"),
        ("英语", "Magnetic Male", "磁性男声", "English_magnetic_voiced_man"),
    ],
)
MINIMAX_VOICE_OPTIONS = [_minimax_voice_label(item) for item in MINIMAX_SYSTEM_VOICES] + ["自定义 voice_id｜在高级参数填写"]

GEMINI_TTS_VOICES = _node_constant(
    "tikpan_gemini_tts.py",
    "GEMINI_TTS_VOICES",
    [
        ("Kore", "Firm", "坚定清晰", "适合商务说明、教程、权威旁白"),
        ("Puck", "Upbeat", "活泼明快", "适合短视频、欢迎语、轻松口播"),
        ("Charon", "Informative", "信息型", "适合知识讲解、产品介绍"),
    ],
)
GEMINI_VOICE_OPTIONS = [_gemini_voice_label(item) for item in GEMINI_TTS_VOICES] + ["自定义 voice_name｜在高级参数填写"]

DOUBAO_VOICES_2_0 = _node_constant(
    "tikpan_doubao_tts.py",
    "DOUBAO_VOICES_2_0",
    [
        ("通用场景", "VV 2.0", "女", "多语种、方言支持", "zh_female_vv_uranus_bigtts"),
        ("通用场景", "小何 2.0", "女", "清新自然", "zh_female_xiaohe_uranus_bigtts"),
        ("通用场景", "云舟 2.0", "男", "成熟稳重", "zh_male_yunzhou_uranus_bigtts"),
    ],
)
DOUBAO_LEGACY_VOICES = _node_constant(
    "tikpan_doubao_tts.py",
    "LEGACY_VOICES",
    [("旧版兼容", "通用女声", "女", "旧版 BV 音色", "BV001_streaming")],
)
DOUBAO_VOICE_OPTIONS = [_doubao_voice_label(item) for item in DOUBAO_VOICES_2_0] + [
    _doubao_voice_label(item) for item in DOUBAO_LEGACY_VOICES
] + ["自定义 voice_type｜在高级参数填写"]

SUNO_STYLE_OPTIONS = _node_constant(
    "tikpan_node_options.py",
    "SUNO_STYLE_OPTIONS",
    [
        "流行｜Pop｜pop",
        "电影感｜Cinematic｜cinematic, orchestral, emotional",
        "短视频爆款｜Viral Short｜catchy pop, upbeat, hook, modern",
        "国风流行｜Chinese Pop｜mandopop, chinese pop, emotional",
        "电子舞曲｜EDM｜edm, dance, electronic, energetic",
        "自定义风格｜custom",
    ],
)
SUNO_MODEL_OPTIONS = _node_constant(
    "tikpan_node_options.py",
    "SUNO_MODEL_OPTIONS",
    ["V5 最新通用｜chirp-v5", "Fenix 高质量实验｜chirp-fenix", "V4 稳定通用｜chirp-v4"],
)
SUNO_VOCAL_GENDER_OPTIONS = _node_constant(
    "tikpan_node_options.py",
    "SUNO_VOCAL_GENDER_OPTIONS",
    ["默认不传｜", "女声倾向｜f", "男声倾向｜m"],
)

QUALITY_OPTIONS = _node_constant(
    "tikpan_node_options.py",
    "QUALITY_OPTIONS",
    ["自动｜auto", "快速低消耗｜low", "均衡质量｜medium", "高质量细节｜high"],
)
MODERATION_OPTIONS = _node_constant(
    "tikpan_node_options.py",
    "MODERATION_OPTIONS",
    ["自动审核｜auto", "宽松审核｜low", "严格审核｜high"],
)
BACKGROUND_OPTIONS = _node_constant(
    "tikpan_node_options.py",
    "BACKGROUND_OPTIONS",
    ["自动背景｜auto", "不透明背景｜opaque", "透明背景｜transparent"],
)
IMAGE_FORMAT_OPTIONS = _node_constant(
    "tikpan_node_options.py",
    "IMAGE_FORMAT_OPTIONS",
    ["PNG｜png", "JPEG｜jpeg", "WEBP｜webp"],
)
RESPONSE_FORMAT_OPTIONS = _node_constant(
    "tikpan_node_options.py",
    "RESPONSE_FORMAT_OPTIONS",
    ["云端链接｜url", "Base64｜b64_json"],
)
WATERMARK_OPTIONS = _node_constant("tikpan_node_options.py", "WATERMARK_OPTIONS", ["无水印", "有水印"])
ON_OFF_AUTO_OPTIONS = _node_constant("tikpan_node_options.py", "ON_OFF_AUTO_OPTIONS", ["关闭", "自动"])
VIDEO_DURATION_OPTIONS = _node_constant(
    "tikpan_node_options.py",
    "VIDEO_DURATION_OPTIONS",
    ["3秒｜3", "5秒｜5", "8秒｜8", "10秒｜10", "15秒｜15"],
)
GROK_DURATION_OPTIONS = _node_constant("tikpan_node_options.py", "GROK_DURATION_OPTIONS", ["6秒｜6s", "10秒｜10s"])
GROK_ASPECT_OPTIONS = _node_constant(
    "tikpan_node_options.py",
    "GROK_ASPECT_OPTIONS",
    ["16:9 横屏｜16:9", "9:16 竖屏｜9:16", "1:1 方形｜1024x1024"],
)

PROMPT = field("prompt", "textarea", "生成指令 / 提示词", "", placeholder="写清楚主体、场景、风格、镜头、比例和限制。", required=1, rows=5, sort_order=1)
SEED = field("seed", "number", "随机种子", "888888", placeholder="0 或固定正整数；旧工作流的 -1 会在后端规范化。", sort_order=99, min_value=0, step=1)
RATIO = field("aspect_ratio", "select", "画面比例", "1:1", options=["1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "21:9"], sort_order=3)
REFERENCE_IMAGES = field("reference_images", "file_image", "参考图", "", placeholder="支持多张参考图，系统会按模型限制发送。", max_count=14, rows=0, sort_order=80)
GPT_IMAGE_2_REFERENCE_IMAGES = field("reference_images", "file_image", "参考图 1-16", "", placeholder="GPT Image 2 支持最多 16 张输入图，网站会按上传顺序发送。", max_count=16, rows=0, sort_order=80)
GROK_IMAGE_ASPECT_OPTIONS = ["auto", "1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "2:1", "1:2", "19.5:9", "9:19.5", "20:9", "9:20"]
GROK_IMAGE_RESOLUTION_OPTIONS = ["auto", "1k", "2k"]
GROK_REFERENCE_IMAGES = field("reference_images", "file_image", "参考图 1-3", "", placeholder="Grok Imagine 编辑/参考图接口最多 3 张，网站会按上传顺序发送。", max_count=3, rows=0, sort_order=2)
SKIP_ERROR = field("skip_error", "checkbox", "跳过错误", "", sort_order=98, hint="批量任务可开启，单次商业任务建议关闭以便及时发现问题。")


CATEGORIES = [
    {"key": "image_generation", "name": "图像生成", "icon": "IMG", "sort_order": 1},
    {"key": "image_editing", "name": "图像编辑", "icon": "EDIT", "sort_order": 2},
    {"key": "video_generation", "name": "视频生成", "icon": "VID", "sort_order": 3},
    {"key": "audio_generation", "name": "音频/语音", "icon": "AUD", "sort_order": 4},
    {"key": "analysis_tools", "name": "分析与提示词", "icon": "AI", "sort_order": 5},
    {"key": "utility_tools", "name": "任务工具", "icon": "TOOL", "sort_order": 6},
]


MODELS = [
    {
        "id": "gemini-3-pro-image-preview",
        "node_class": "TikpanNanoBananaProNode",
        "name": "Nano Banana Pro / Gemini 3 Pro Image",
        "category_key": "image_generation",
        "provider": "Google / Tikpan",
        "description": "高质量图像生成与多图参考，字段对齐本地 Nano Banana Pro 节点。",
        "api_type": "gemini_native",
        "endpoint": "/v1beta/models/gemini-3-pro-image-preview:generateContent",
        "upstream_model": "gemini-3-pro-image-preview",
        "sort_order": 1,
        "pricing": {"credits_1k": 6, "credits_2k": 10, "credits_4k": 18, "billing_mode": "resolution"},
        "usage": usage(
            "填写生成/修改指令，可上传 1-16 张参考图；纯文生图不上传参考图即可。",
            "分辨率支持 1K/2K/4K/none，画面比例与 ComfyUI 节点一致；随机种子默认 888888，固定后便于复现。",
            "启用谷歌搜索只建议在 Gemini 原生模式下用于需要实时信息的图像任务。",
        ),
        "fields": [
            field("call_mode", "select", "调用方式", "gemini原生", options=["gemini原生", "openai兼容"], sort_order=1),
            field("model", "select", "模型", "gemini-3-pro-image-preview", options=["gemini-3-pro-image-preview", "gemini-3.1-flash-image-preview"], sort_order=2),
            field("prompt", "textarea", "修改指令", "请生成一张高质量图像，增强细节与质感，输出高分辨率结果。", required=1, rows=5, sort_order=3),
            field("resolution", "select", "分辨率", "2K", options=["2K", "4K", "1K", "none"], sort_order=4),
            field("aspect_ratio", "select", "画面比例", "1:1 | 1:1正方形", options=["1:1 | 1:1正方形", "16:9 | 16:9宽屏", "9:16 | 9:16竖屏", "4:3 | 4:3标准", "3:4 | 3:4竖版", "21:9 | 21:9超宽", "2.35:1 | 2.35:1电影", "3:2 | 3:2摄影", "2:3 | 2:3人像"], sort_order=5),
            SEED,
            field("temperature", "number", "温度", "0.7", min_value=0, max_value=2, step=0.1, sort_order=7),
            field("max_tokens", "number", "最大输出Token数", "4096", min_value=1, max_value=32768, step=1, sort_order=8, hint="只控制随图返回的文字预算，不控制图片尺寸。"),
            field("web_search", "checkbox", "启用谷歌搜索", "", sort_order=9),
            REFERENCE_IMAGES,
        ],
    },
    {
        "id": "gemini-3.1-flash-image-preview",
        "node_class": "TikpanGeminiImageMaxNode",
        "name": "Gemini 3.1 Flash 多图生图",
        "category_key": "image_generation",
        "provider": "Google / Tikpan",
        "description": "Gemini 图片生成，支持最多 16 张参考图，适合快速多图参考生图。",
        "api_type": "gemini_native",
        "endpoint": "/v1beta/models/gemini-3.1-flash-image-preview:generateContent",
        "upstream_model": "gemini-3.1-flash-image-preview",
        "sort_order": 2,
        "pricing": {"credits_1k": 4, "credits_2k": 6, "credits_4k": 12, "billing_mode": "resolution"},
        "usage": usage(
            "先写修改指令，再选择模型、分辨率、比例；参考图会按上传顺序进入多模态请求。",
            "调用方式默认 gemini原生，只有需要兼容旧工作流时再切 images_generations 或 chat_completions。",
        ),
        "fields": [
            field("prompt", "textarea", "修改指令", "请参考提供的图片，生成一张高质量竖版海报，主体一致，画面精致，电影感光影。", required=1, rows=5, sort_order=1),
            field("model", "select", "模型", "gemini-3.1-flash-image-preview", options=["gemini-3-pro-image-preview", "gemini-3.1-flash-image-preview", "nano-banana-2", "nano-banana-pro"], sort_order=2),
            field("resolution", "select", "分辨率", "2K", options=["none", "1K", "2K", "4K"], sort_order=3),
            field("aspect_ratio", "select", "画面比例", "9:16", options=["1:1", "16:9", "9:16", "21:9", "4:3", "3:4"], sort_order=4),
            field("call_mode", "select", "调用方式", "gemini原生", options=["gemini原生", "images_generations", "chat_completions"], sort_order=5),
            SEED,
            REFERENCE_IMAGES,
        ],
    },
    {
        "id": "doubao-seedream-5-0-260128",
        "node_class": "TikpanDoubaoImageNode",
        "name": "豆包图像 Seedream 5.0",
        "category_key": "image_generation",
        "provider": "字节跳动 / Tikpan",
        "description": "豆包 Seedream 5.0 图像生成，已补齐尺寸模式、返回方式、水印、联网增强、多图参数。",
        "api_type": "doubao",
        "endpoint": "/v1/images/generations",
        "upstream_model": "doubao-seedream-5-0-260128",
        "sort_order": 3,
        "pricing": {"credits_1k": 3, "credits_2k": 5, "credits_4k": 10, "billing_mode": "resolution"},
        "usage": usage(
            "常规文生图只填生成指令，尺寸模式保持“品质档位”，清晰度选择 2K 或 3K。",
            "需要精确比例时切到“按比例输出精确尺寸”，系统会按清晰度和画面比例映射像素尺寸。",
            "参考图可上传，也可在“图片URL或Base64”中一行一个填写；最多按节点规则合并 16 张。",
        ),
        "fields": [
            field("prompt", "textarea", "生成指令", "一张极致高清的赛博朋克风格产品展示图，霓虹灯光效果，细腻质感", required=1, rows=5, sort_order=1),
            field("size_mode", "select", "尺寸模式", "品质档位", options=["品质档位", "按比例输出精确尺寸"], sort_order=2),
            field("resolution", "select", "清晰度档位", "2K", options=["2K", "3K"], sort_order=3),
            field("aspect_ratio", "select", "画面比例", "1:1 正方形", options=["1:1 正方形", "4:3 横版", "3:4 竖版", "16:9 宽屏", "9:16 手机竖屏", "3:2 海报横版", "2:3 海报竖版", "21:9 超宽屏"], sort_order=4),
            field("output_format", "select", "图片格式", "JPEG｜jpeg", options=IMAGE_FORMAT_OPTIONS[:2], sort_order=5),
            field("response_format", "select", "返回方式", "云端链接｜url", options=RESPONSE_FORMAT_OPTIONS, sort_order=6),
            field("watermark", "select", "水印", "无水印", options=WATERMARK_OPTIONS, sort_order=7),
            field("web_search", "select", "联网搜索增强", "关闭", options=ON_OFF_AUTO_OPTIONS, sort_order=8),
            field("multi_image", "select", "多图生成", "关闭", options=ON_OFF_AUTO_OPTIONS, sort_order=9),
            field("n", "number", "最多生成张数", "4", min_value=1, max_value=15, step=1, sort_order=10),
            field("multi_image_failure", "select", "多图失败处理", "严格报错", options=["严格报错", "自动降级为首图"], sort_order=11),
            REFERENCE_IMAGES,
            field("image_urls", "textarea", "图片URL或Base64", "", placeholder="一行一个公开 URL 或 data:image/base64。", rows=3, sort_order=81),
            field("negative_prompt", "textarea", "负面提示词", "", rows=3, sort_order=82),
        ],
    },
    {
        "id": "gpt-image-2",
        "node_class": "TikpanGptImage2OfficialNode",
        "name": "GPT-Image-2 官方生图",
        "category_key": "image_generation",
        "provider": "OpenAI / Tikpan",
        "description": "GPT-Image-2 官方格式生图，参数与 ComfyUI 官方节点对齐。",
        "api_type": "tikpan_proxy",
        "endpoint": "/v1/images/generations",
        "upstream_model": "gpt-image-2",
        "sort_order": 4,
        "pricing": {"credits_1k": 8, "credits_2k": 14, "credits_4k": 26, "billing_mode": "resolution"},
        "usage": usage(
            "填写生成指令，选择分辨率档位和画面比例；画质与推理强度越高，等待和成本通常越高。",
            "审核强度一般保持自动；返回格式默认 PNG，网页会保存结果并可走 OSS/CDN。",
        ),
        "fields": [
            field("prompt", "textarea", "生成指令", "一幅写实的极地极光景观，巨大的冰川倒映在平静的海面上，8k超清，电影感。", required=1, rows=5, sort_order=1),
            field("model", "select", "模型", "gpt-image-2", options=["gpt-image-2"], sort_order=2),
            field("resolution", "select", "分辨率档位", "1K (1024)", options=["512", "1K (1024)", "2K (2048)", "4K (官方极限 3840)"], sort_order=3),
            field("aspect_ratio", "select", "画面比例", "1:1", options=["1:1", "3:2", "2:3", "4:3", "3:4", "16:9", "9:16", "21:9", "9:21"], sort_order=4),
            field("quality", "select", "画质与推理强度", "均衡质量｜medium", options=QUALITY_OPTIONS, sort_order=5),
            field("moderation", "select", "审核强度", "自动审核｜auto", options=MODERATION_OPTIONS, sort_order=6),
            SEED,
            field("output_format", "select", "返回格式", "PNG｜png", options=IMAGE_FORMAT_OPTIONS, sort_order=8),
            GPT_IMAGE_2_REFERENCE_IMAGES,
            SKIP_ERROR,
        ],
    },
    {
        "id": "gpt-image-2-edit",
        "node_class": "TikpanGptImage2OfficialEditV2",
        "name": "GPT-Image-2 官方修图 V2",
        "category_key": "image_editing",
        "provider": "OpenAI / Tikpan",
        "description": "多参考图修图、遮罩、透明背景和提示增强参数与 ComfyUI V2 节点对齐。",
        "api_type": "tikpan_proxy",
        "endpoint": "/v1/images/edits",
        "upstream_model": "gpt-image-2",
        "sort_order": 1,
        "pricing": {"credits_1k": 8, "credits_2k": 14, "credits_4k": 26, "billing_mode": "resolution"},
        "usage": usage(
            "上传主图像或参考图，填写编辑指令；有局部编辑需求时在 ComfyUI 用遮罩，网页端可先走整图编辑。",
            "生成张数、分辨率档位、画面比例、画质、背景模式都与本地节点一致。",
        ),
        "fields": [
            field("prompt", "textarea", "编辑指令", "请根据要求编辑图像；如果提供了遮罩，仅修改遮罩区域并尽量保持未遮罩区域不变。", required=1, rows=5, sort_order=1),
            field("reference_images", "file_image", "主图像 / 参考图", "", max_count=16, rows=0, sort_order=2),
            field("n", "number", "生成张数", "1", min_value=1, max_value=10, step=1, sort_order=3),
            field("resolution", "select", "分辨率档位", "2K", options=["Auto", "1K", "2K", "4K"], sort_order=4),
            field("aspect_ratio", "select", "画面比例", "Auto", options=["Auto", "1:1", "16:9", "9:16", "4:3", "3:4", "21:9", "9:21"], sort_order=5),
            field("quality", "select", "画质", "均衡质量｜medium", options=QUALITY_OPTIONS, sort_order=6),
            field("background", "select", "背景模式", "自动背景｜auto", options=BACKGROUND_OPTIONS, sort_order=7),
            field("invert_mask", "checkbox", "遮罩反相", "", sort_order=8),
            field("boost_prompt", "checkbox", "提示增强", "true", sort_order=9),
            field("timeout_seconds", "number", "超时秒数", "300", min_value=30, max_value=1800, step=10, sort_order=10),
            SKIP_ERROR,
        ],
    },
    {
        "id": "grok-imagine-image",
        "node_class": "TikpanGrokImagineImageNode",
        "name": "Grok Imagine Image",
        "category_key": "image_generation",
        "provider": "xAI / Tikpan",
        "description": "Grok Imagine 标准文生图，补齐官方 n、画面比例、清晰度和返回格式参数。",
        "api_type": "tikpan_proxy",
        "endpoint": "/v1/images/generations",
        "upstream_model": "grok-imagine-image",
        "sort_order": 7,
        "pricing": {"credits_1k": 4, "credits_2k": 4, "credits_4k": 4, "billing_mode": "flat", "cost_per_unit": 0.208},
        "usage": usage(
            "这是纯文生图入口；需要参考图时请选择 Grok Imagine Image 参考图/修图。",
            "生成张数、画面比例、清晰度和返回格式会直接传给上游；url 返回适合网站保存到 OSS/CDN。",
        ),
        "fields": [
            field("prompt", "textarea", "生成指令", "A cinematic product poster with precise details, realistic lighting.", required=1, rows=5, sort_order=1),
            field("model", "select", "模型", "grok-imagine-image", options=["grok-imagine-image"], sort_order=2),
            field("n", "number", "生成张数", "1", min_value=1, max_value=10, step=1, sort_order=3),
            field("aspect_ratio", "select", "画面比例", "auto", options=GROK_IMAGE_ASPECT_OPTIONS, sort_order=4),
            field("resolution", "select", "清晰度", "auto", options=GROK_IMAGE_RESOLUTION_OPTIONS, sort_order=5),
            field("response_format", "select", "返回方式", "url", options=["url", "b64_json"], sort_order=6),
            SKIP_ERROR,
        ],
    },
    {
        "id": "grok-imagine-image-pro",
        "node_class": "TikpanGrokImagineImageProNode",
        "name": "Grok Imagine Image Pro",
        "category_key": "image_generation",
        "provider": "xAI / Tikpan",
        "description": "Grok Imagine Pro 高质量文生图，补齐官方 n、画面比例、清晰度和返回格式参数。",
        "api_type": "tikpan_proxy",
        "endpoint": "/v1/images/generations",
        "upstream_model": "grok-imagine-image-pro",
        "sort_order": 8,
        "pricing": {"credits_1k": 12, "credits_2k": 12, "credits_4k": 12, "billing_mode": "flat", "cost_per_unit": 0.728},
        "usage": usage(
            "这是 Pro 文生图入口；需要参考图时请选择 Grok Imagine Image Pro 参考图/修图。",
            "如果供应商通道失败，网站会把失败归因到上游/供应商环节，便于排查。",
        ),
        "fields": [
            field("prompt", "textarea", "生成指令", "A cinematic product poster with precise details, realistic lighting.", required=1, rows=5, sort_order=1),
            field("model", "select", "模型", "grok-imagine-image-pro", options=["grok-imagine-image-pro"], sort_order=2),
            field("n", "number", "生成张数", "1", min_value=1, max_value=10, step=1, sort_order=3),
            field("aspect_ratio", "select", "画面比例", "auto", options=GROK_IMAGE_ASPECT_OPTIONS, sort_order=4),
            field("resolution", "select", "清晰度", "auto", options=GROK_IMAGE_RESOLUTION_OPTIONS, sort_order=5),
            field("response_format", "select", "返回方式", "url", options=["url", "b64_json"], sort_order=6),
            SKIP_ERROR,
        ],
    },
    {
        "id": "grok-imagine-image-edit",
        "node_class": "TikpanGrokImagineImageEditNode",
        "name": "Grok Imagine Image 参考图/修图",
        "category_key": "image_editing",
        "provider": "xAI / Tikpan",
        "description": "Grok Imagine 参考图编辑入口，最多 3 张参考图，适合保持主体、风格迁移和局部重绘需求。",
        "api_type": "tikpan_proxy",
        "endpoint": "/v1/images/edits",
        "upstream_model": "grok-imagine-image",
        "sort_order": 9,
        "pricing": {"credits_1k": 4, "credits_2k": 4, "credits_4k": 4, "billing_mode": "flat", "cost_per_unit": 0.208},
        "usage": usage(
            "上传 1-3 张参考图，再写编辑/生成指令；这是 Grok 的参考图入口，不是纯文生图入口。",
            "网站会把参考图转换为上游需要的 image/images 结构；失败时会显示上游或上传环节错误。",
        ),
        "fields": [
            field("prompt", "textarea", "编辑指令", "Keep the main subject consistent, improve lighting, details, and commercial quality.", required=1, rows=5, sort_order=1),
            GROK_REFERENCE_IMAGES,
            field("model", "select", "模型", "grok-imagine-image", options=["grok-imagine-image"], sort_order=3),
            field("n", "number", "生成张数", "1", min_value=1, max_value=10, step=1, sort_order=4),
            field("aspect_ratio", "select", "画面比例", "auto", options=GROK_IMAGE_ASPECT_OPTIONS, sort_order=5),
            field("resolution", "select", "清晰度", "auto", options=GROK_IMAGE_RESOLUTION_OPTIONS, sort_order=6),
            field("response_format", "select", "返回方式", "url", options=["url", "b64_json"], sort_order=7),
            SKIP_ERROR,
        ],
    },
    {
        "id": "grok-imagine-image-pro-edit",
        "node_class": "TikpanGrokImagineImageProEditNode",
        "name": "Grok Imagine Image Pro 参考图/修图",
        "category_key": "image_editing",
        "provider": "xAI / Tikpan",
        "description": "Grok Imagine Pro 参考图编辑入口，最多 3 张参考图，走更高质量的 Pro 通道。",
        "api_type": "tikpan_proxy",
        "endpoint": "/v1/images/edits",
        "upstream_model": "grok-imagine-image-pro",
        "sort_order": 10,
        "pricing": {"credits_1k": 12, "credits_2k": 12, "credits_4k": 12, "billing_mode": "flat", "cost_per_unit": 0.728},
        "usage": usage(
            "上传 1-3 张参考图，再写编辑/生成指令；适合高质量主体保持、产品图优化和风格迁移。",
            "如果某个 Tikpan 上游通道暂不支持 Pro edit，失败信息会显示在上游环节，届时可切换普通 edit。",
        ),
        "fields": [
            field("prompt", "textarea", "编辑指令", "Keep the main subject consistent, improve lighting, details, and commercial quality.", required=1, rows=5, sort_order=1),
            GROK_REFERENCE_IMAGES,
            field("model", "select", "模型", "grok-imagine-image-pro", options=["grok-imagine-image-pro"], sort_order=3),
            field("n", "number", "生成张数", "1", min_value=1, max_value=10, step=1, sort_order=4),
            field("aspect_ratio", "select", "画面比例", "auto", options=GROK_IMAGE_ASPECT_OPTIONS, sort_order=5),
            field("resolution", "select", "清晰度", "auto", options=GROK_IMAGE_RESOLUTION_OPTIONS, sort_order=6),
            field("response_format", "select", "返回方式", "url", options=["url", "b64_json"], sort_order=7),
            SKIP_ERROR,
        ],
    },
    {
        "id": "gpt-image-2-all",
        "node_class": "TikpanGptImage2GenNode",
        "name": "GPT-Image-2-all 兼容生图",
        "category_key": "image_generation",
        "provider": "OpenAI 兼容 / Tikpan",
        "description": "旧版 gpt-image-2-all 多图参考生图入口，已补充分辨率档位与尺寸逻辑。",
        "api_type": "tikpan_proxy",
        "endpoint": "/v1/images/generations",
        "upstream_model": "gpt-image-2-all",
        "sort_order": 5,
        "pricing": {"credits_1k": 6, "credits_2k": 10, "credits_4k": 18, "billing_mode": "resolution"},
        "usage": usage(
            "这个 all 节点有分辨率档位和画面比例：系统会按长边 512/1K/2K/4K 自动算出像素尺寸。",
            "可上传最多 16 张参考图，品质与 ComfyUI 节点保持“标准/高清”。",
        ),
        "fields": [
            field("prompt", "textarea", "生成指令", "请参考提供的 Image_1 到 Image_16 的视觉特征，生成一张极致高清的...", required=1, rows=5, sort_order=1),
            field("model", "select", "模型", "gpt-image-2-all", options=["gpt-image-2-all"], sort_order=2),
            field("resolution", "select", "分辨率档位", "1K", options=["512", "1K", "2K", "4K"], sort_order=3),
            field("aspect_ratio", "select", "画面比例", "1:1", options=["1:1", "16:9", "9:16", "21:9", "4:3", "3:4"], sort_order=4),
            field("quality", "select", "品质", "高清｜hd", options=["标准｜standard", "高清｜hd"], sort_order=5),
            SEED,
            GPT_IMAGE_2_REFERENCE_IMAGES,
        ],
    },
    {
        "id": "gpt-image-2-all-simple",
        "node_class": "TikpanGptImage2Node",
        "name": "GPT-Image-2-all 简易生图",
        "category_key": "image_generation",
        "provider": "OpenAI 兼容 / Tikpan",
        "description": "旧版简易 gpt-image-2-all 节点入口，适合兼容早期工作流。",
        "api_type": "tikpan_proxy",
        "endpoint": "/v1/images/generations",
        "upstream_model": "gpt-image-2-all",
        "sort_order": 6,
        "pricing": {"credits_1k": 6, "credits_2k": 10, "credits_4k": 18, "billing_mode": "resolution"},
        "usage": usage(
            "简易节点只需要提示词、尺寸、品质、风格和随机种子，适合快速出图。",
            "尺寸下拉已经写明比例和像素，用户不需要查 id。",
        ),
        "fields": [
            field("prompt", "textarea", "提示词", "一位穿着赛博朋克装甲的极客，正在操作复杂的全息工作流，4k，大师级画质...", required=1, rows=5, sort_order=1),
            field("model", "select", "模型", "gpt-image-2-all", options=["gpt-image-2-all"], sort_order=2),
            field("size", "select", "尺寸", "1:1 方图｜1024x1024", options=["1:1 方图｜1024x1024", "16:9 横图｜1792x1024", "9:16 竖图｜1024x1792"], sort_order=3),
            field("quality", "select", "品质", "高清｜hd", options=["标准｜standard", "高清｜hd"], sort_order=4),
            field("style", "select", "风格", "鲜艳创意｜vivid", options=["鲜艳创意｜vivid", "自然真实｜natural"], sort_order=5),
            SEED,
        ],
    },
    {
        "id": "gpt-image-2-all-edit",
        "node_class": "TikpanGptImage2EditNode",
        "name": "GPT-Image-2-all 兼容修图",
        "category_key": "image_editing",
        "provider": "OpenAI 兼容 / Tikpan",
        "description": "旧版 gpt-image-2-all 修图节点入口，支持底图、产品参考图和输出尺寸。",
        "api_type": "tikpan_proxy",
        "endpoint": "/v1/images/edits",
        "upstream_model": "gpt-image-2-all",
        "sort_order": 2,
        "pricing": {"credits_1k": 6, "credits_2k": 10, "credits_4k": 18, "billing_mode": "resolution"},
        "usage": usage(
            "上传底图/产品参考图，填写修改指令；输出尺寸选择沿用底图或 512/1K/2K/4K。",
            "画面比例选择沿用底图比例时更适合局部修图。",
        ),
        "fields": [
            field("prompt", "textarea", "修改指令", "请把图中的人物换成一位穿着西装的男士，背景保持不变...", required=1, rows=5, sort_order=1),
            field("reference_images", "file_image", "底图 / 产品参考图", "", max_count=16, rows=0, sort_order=2),
            field("model", "select", "模型", "gpt-image-2-all", options=["gpt-image-2-all"], sort_order=3),
            field("resolution", "select", "输出尺寸", "沿用底图尺寸", options=["沿用底图尺寸", "512", "1K", "2K", "4K"], sort_order=4),
            field("aspect_ratio", "select", "画面比例", "沿用底图比例", options=["沿用底图比例", "1:1", "16:9", "9:16", "21:9", "4:3", "3:4"], sort_order=5),
            field("quality", "select", "品质", "高清｜hd", options=["标准｜standard", "高清｜hd"], sort_order=6),
        ],
    },
    {
        "id": "veo-3-1-video",
        "node_class": "TikpanVeoVideoNode",
        "name": "Veo 3.1 多模型视频生成",
        "category_key": "video_generation",
        "provider": "Google Veo / Tikpan",
        "description": "Veo 3.1 lite/fast/pro/components 视频生成，支持首尾帧和组件垫图。",
        "api_type": "tikpan_proxy",
        "endpoint": "/v1/videos",
        "upstream_model": "veo_3_1-lite",
        "sort_order": 1,
        "pricing": {"credits_1k": 30, "credits_2k": 45, "credits_4k": 80, "billing_mode": "flat"},
        "usage": usage(
            "填写 Veo 专属提示词，选择模型和比例；组件模型才建议上传 1-3 张垫图。",
            "首帧/尾帧图会作为视频约束，普通文本生视频不上传图片即可。",
        ),
        "fields": [
            field("prompt", "textarea", "Veo专属提示词", "请在此直接输入您的视频提示词...", required=1, rows=5, sort_order=1),
            field("model", "select", "模型选择", "veo_3_1-lite", options=["veo_3_1-lite", "veo_3_1-lite-4K", "veo_3_1-fast-4K", "veo3.1-fast-components", "veo3.1-pro", "veo_3_1-components-4K", "veo_3_1-fast-components-4K"], sort_order=2),
            field("aspect_ratio", "select", "比例", "16:9", options=["16:9", "9:16"], sort_order=3),
            SEED,
            field("reference_images", "file_image", "首帧/尾帧/垫图", "", max_count=5, rows=0, sort_order=4),
            field("verify_tls", "checkbox", "校验HTTPS证书", "true", sort_order=20),
        ],
    },
    {
        "id": "grok-video-3",
        "node_class": "TikpanExclusiveVideoNode",
        "name": "Grok3 直出视频生成",
        "category_key": "video_generation",
        "provider": "xAI / Tikpan",
        "description": "Grok3 视频生成，支持模型选择、比例、分辨率和最多 7 张参考图。",
        "api_type": "grok_video",
        "endpoint": "/v1/video/grok",
        "upstream_model": "grok-video-3",
        "sort_order": 2,
        "pricing": {"credits_1k": 12, "credits_2k": 12, "credits_4k": 12, "billing_mode": "flat"},
        "usage": usage(
            "选择 grok-video-3 或 10s 版本；比例和分辨率按节点下拉选择。",
            "需要图生视频时上传参考图，最多按节点规则 7 张。",
        ),
        "fields": [
            field("prompt", "textarea", "Grok3专属提示词", "", required=1, rows=5, sort_order=1),
            field("model", "select", "模型选择", "grok-video-3", options=["grok-video-3", "grok-video-3-10s"], sort_order=2),
            field("aspect_ratio", "select", "比例", "9:16", options=["9:16", "16:9", "1:1", "4:3", "3:4", "21:9", "9:21"], sort_order=3),
            field("resolution", "select", "分辨率", "720P", options=["1080P", "720P", "480P"], sort_order=4),
            SEED,
            field("reference_images", "file_image", "参考图", "", max_count=7, rows=0, sort_order=5),
        ],
    },
    {
        "id": "grok-videos",
        "node_class": "TikpanGrokVideoNode",
        "name": "Grok-Videos 视频生成",
        "category_key": "video_generation",
        "provider": "xAI / Tikpan",
        "description": "新版 Grok-Videos 异步视频节点入口，风格、时长、比例做成下拉。",
        "api_type": "tikpan_proxy",
        "endpoint": "/v1/videos",
        "upstream_model": "grok-videos",
        "sort_order": 3,
        "pricing": {"credits_1k": 12, "credits_2k": 12, "credits_4k": 12, "billing_mode": "flat"},
        "usage": usage(
            "填写生成指令，视频时长选择 6s 或 10s，画面比例选择横屏、竖屏或方形。",
            "可上传最多 4 张参考图。",
        ),
        "fields": [
            field("prompt", "textarea", "生成指令", "一段极具视觉冲击力的赛博朋克城市夜景，霓虹灯闪烁，飞行汽车穿梭...", required=1, rows=5, sort_order=1),
            field("model", "select", "模型", "grok-videos", options=["grok-videos"], sort_order=2),
            field("duration", "select", "视频时长", "6秒｜6s", options=GROK_DURATION_OPTIONS, sort_order=3),
            field("aspect_ratio", "select", "画面比例", "16:9 横屏｜16:9", options=GROK_ASPECT_OPTIONS, sort_order=4),
            SEED,
            field("reference_images", "file_image", "参考图", "", max_count=4, rows=0, sort_order=5),
        ],
    },
    {
        "id": "happyhorse-1.0-t2v",
        "node_class": "TikpanHappyHorseT2VNode",
        "name": "HappyHorse 1.0 文生视频",
        "category_key": "video_generation",
        "provider": "HappyHorse / Tikpan",
        "description": "文生视频，字段对齐执行方式、清晰度、时长、水印、轮询参数。",
        "api_type": "tikpan_proxy",
        "endpoint": "/v1/video/create",
        "upstream_model": "happyhorse-1.0-t2v",
        "sort_order": 4,
        "pricing": {"credits_1k": 18, "credits_2k": 18, "credits_4k": 18, "billing_mode": "flat"},
        "usage": usage(
            "填写生成指令，选择同步等待或异步仅提交任务；网页端建议同步用于立即拿结果，异步可配合任务查询节点。",
            "清晰度、比例、时长、水印和轮询参数都与 ComfyUI 节点一致。",
        ),
        "fields": [
            field("prompt", "textarea", "生成指令", "一座由硬纸板和瓶盖搭建的微型城市，在夜晚焕发出生机。一列硬纸板火车缓缓驶过，小灯点缀其间，照亮前路。", required=1, rows=5, sort_order=1),
            field("execution_mode", "select", "执行方式", "同步 (等待生成并下载)", options=["同步 (等待生成并下载)", "异步 (仅提交任务)"], sort_order=2),
            field("resolution", "select", "清晰度", "1080P", options=["720P", "1080P"], sort_order=3),
            field("aspect_ratio", "select", "画面比例", "16:9", options=["16:9", "9:16", "1:1", "4:3", "3:4"], sort_order=4),
            field("duration", "select", "视频时长", "5秒｜5", options=VIDEO_DURATION_OPTIONS, sort_order=5),
            field("watermark", "select", "水印", "无水印", options=WATERMARK_OPTIONS, sort_order=6),
            SEED,
            field("max_wait_seconds", "number", "最长等待秒数", "600", min_value=30, max_value=3600, step=10, sort_order=8),
            field("poll_interval", "number", "查询间隔秒数", "10", min_value=5, max_value=60, step=5, sort_order=9),
        ],
    },
    {
        "id": "happyhorse-1.0-i2v",
        "node_class": "TikpanHappyHorseI2VNode",
        "name": "HappyHorse 1.0 图生视频",
        "category_key": "video_generation",
        "provider": "HappyHorse / Tikpan",
        "description": "图生视频，支持首帧图片或图片 URL，补齐执行与轮询参数。",
        "api_type": "tikpan_proxy",
        "endpoint": "/v1/video/create",
        "upstream_model": "happyhorse-1.0-i2v",
        "sort_order": 5,
        "pricing": {"credits_1k": 18, "credits_2k": 18, "credits_4k": 18, "billing_mode": "flat"},
        "usage": usage(
            "上传首帧图片或填写图片URL，图片URL优先级更高。",
            "其余参数与文生视频一致：执行方式、清晰度、视频时长、水印、随机种子、轮询设置。",
        ),
        "fields": [
            PROMPT,
            field("execution_mode", "select", "执行方式", "同步 (等待生成并下载)", options=["同步 (等待生成并下载)", "异步 (仅提交任务)"], sort_order=2),
            field("resolution", "select", "清晰度", "1080P", options=["720P", "1080P"], sort_order=3),
            field("duration", "select", "视频时长", "5秒｜5", options=VIDEO_DURATION_OPTIONS, sort_order=4),
            field("watermark", "select", "水印", "无水印", options=WATERMARK_OPTIONS, sort_order=5),
            SEED,
            field("reference_images", "file_image", "首帧图片", "", max_count=1, rows=0, sort_order=7),
            field("image_url", "text", "图片URL", "", sort_order=8),
            field("max_wait_seconds", "number", "最长等待秒数", "600", min_value=30, max_value=3600, step=10, sort_order=9),
            field("poll_interval", "number", "查询间隔秒数", "10", min_value=5, max_value=60, step=5, sort_order=10),
        ],
    },
    {
        "id": "happyhorse-1.0-r2v",
        "node_class": "TikpanHappyHorseR2VNode",
        "name": "HappyHorse 1.0 参考生视频",
        "category_key": "video_generation",
        "provider": "HappyHorse / Tikpan",
        "description": "多参考图生视频，适合产品、角色和场景一致性。",
        "api_type": "tikpan_proxy",
        "endpoint": "/v1/video/create",
        "upstream_model": "happyhorse-1.0-r2v",
        "sort_order": 6,
        "pricing": {"credits_1k": 22, "credits_2k": 22, "credits_4k": 22, "billing_mode": "flat"},
        "usage": usage(
            "上传 1-9 张参考图，或在图片URL列表中一行一个填写公开 URL；URL 优先级更高。",
            "清晰度、视频时长、水印、随机种子、轮询设置与 ComfyUI 节点一致。",
        ),
        "fields": [
            PROMPT,
            field("execution_mode", "select", "执行方式", "同步 (等待生成并下载)", options=["同步 (等待生成并下载)", "异步 (仅提交任务)"], sort_order=2),
            field("resolution", "select", "清晰度", "1080P", options=["720P", "1080P"], sort_order=3),
            field("duration", "select", "视频时长", "5秒｜5", options=VIDEO_DURATION_OPTIONS, sort_order=4),
            field("watermark", "select", "水印", "无水印", options=WATERMARK_OPTIONS, sort_order=5),
            SEED,
            field("reference_images", "file_image", "参考图1-9", "", max_count=9, rows=0, sort_order=7),
            field("image_urls", "textarea", "图片URL列表", "", rows=3, sort_order=8),
            field("max_wait_seconds", "number", "最长等待秒数", "600", min_value=30, max_value=3600, step=10, sort_order=9),
            field("poll_interval", "number", "查询间隔秒数", "10", min_value=5, max_value=60, step=5, sort_order=10),
        ],
    },
    {
        "id": "happyhorse-1.0-video-edit",
        "node_class": "TikpanHappyHorseVideoEditNode",
        "name": "HappyHorse 1.0 视频编辑",
        "category_key": "video_generation",
        "provider": "HappyHorse / Tikpan",
        "description": "视频编辑与重绘，支持视频 URL、本地视频和最多 5 张参考图。",
        "api_type": "tikpan_proxy",
        "endpoint": "/v1/video/edit",
        "upstream_model": "happyhorse-1.0-video-edit",
        "sort_order": 7,
        "pricing": {"credits_1k": 25, "credits_2k": 25, "credits_4k": 25, "billing_mode": "flat"},
        "usage": usage(
            "填写编辑指令，优先填写视频URL；需要参考风格或主体时上传参考图或填写参考图URL列表。",
            "同步模式会等待并下载结果，异步模式只返回任务 ID，后续用任务查询节点取回。",
        ),
        "fields": [
            field("prompt", "textarea", "编辑指令", "将背景替换为日落海滩，保持人物动作不变，添加暖色调滤镜", required=1, rows=5, sort_order=1),
            field("execution_mode", "select", "执行方式", "同步 (等待生成并下载)", options=["同步 (等待生成并下载)", "异步 (仅提交任务)"], sort_order=2),
            field("resolution", "select", "清晰度", "1080P", options=["720P", "1080P"], sort_order=3),
            field("duration", "select", "视频时长", "5秒｜5", options=VIDEO_DURATION_OPTIONS, sort_order=4),
            field("watermark", "select", "水印", "无水印", options=WATERMARK_OPTIONS, sort_order=5),
            SEED,
            field("video_url", "text", "视频URL", "", sort_order=7),
            field("reference_images", "file_image", "参考图1-5", "", max_count=5, rows=0, sort_order=8),
            field("image_urls", "textarea", "参考图URL列表", "", rows=3, sort_order=9),
            field("max_wait_seconds", "number", "最长等待秒数", "600", min_value=30, max_value=3600, step=10, sort_order=10),
            field("poll_interval", "number", "查询间隔秒数", "10", min_value=5, max_value=60, step=5, sort_order=11),
        ],
    },
    {
        "id": "suno-music",
        "node_class": "TikpanSunoMusicNode",
        "name": "Suno 音乐生成",
        "category_key": "audio_generation",
        "provider": "Suno / Tikpan",
        "description": "Suno 灵感、自定义、续写和歌手风格音乐生成；风格、模型、人声性别均为下拉。",
        "api_type": "suno",
        "endpoint": "/v1/suno/submit/music",
        "upstream_model": "chirp-fenix",
        "sort_order": 1,
        "pricing": {"credits_1k": 10, "credits_2k": 10, "credits_4k": 10, "billing_mode": "flat"},
        "usage": usage(
            "灵感模式：写创作提示词，可选纯音乐，Suno 自动写歌。",
            "自定义模式：填写标题、歌词/提示词、风格预设或风格标签。",
            "续写模式：填写续写歌曲ID和起始秒数；歌手风格：填写 PersonaID 或参考音频ID。",
            "风格预设、模型版本、人声性别均已做下拉，用户不需要手查 id。",
        ),
        "fields": [
            field("mode", "select", "生成模式", "自定义模式", options=["灵感模式", "自定义模式", "续写模式", "歌手风格"], sort_order=1),
            field("title", "text", "歌曲标题", "命中注定", sort_order=2),
            field("prompt", "textarea", "创作提示词 / 歌词", "写一首伤感的粤语情歌", required=1, rows=6, sort_order=3),
            field("tags", "select", "风格预设", "流行｜Pop｜pop", options=SUNO_STYLE_OPTIONS, sort_order=4),
            field("custom_tags", "text", "风格标签", "pop, romantic", placeholder="选择自定义风格时填写，或直接写 pop, cinematic, female vocal。", sort_order=5),
            field("model_version", "select", "模型版本", "Fenix 高质量实验｜chirp-fenix", options=SUNO_MODEL_OPTIONS, sort_order=6),
            field("make_instrumental", "checkbox", "生成纯音乐", "", sort_order=7),
            field("negative_tags", "text", "负面风格标签", "", sort_order=8),
            field("send_advanced", "checkbox", "发送高级Suno参数", "", sort_order=9, hint="开启后透传人声性别、自动歌词、风格权重、创意随机度等高级字段。"),
            field("vocal_gender", "select", "人声性别", "默认不传｜", options=SUNO_VOCAL_GENDER_OPTIONS, sort_order=10),
            field("auto_generate_lyrics", "checkbox", "自动生成歌词", "", sort_order=11),
            field("style_weight", "number", "风格权重", "0.65", min_value=0, max_value=1, step=0.05, sort_order=12),
            field("weirdness", "number", "创意随机度", "0.3", min_value=0, max_value=1, step=0.05, sort_order=13),
            field("continue_clip_id", "text", "续写_歌曲ID", "", sort_order=14),
            field("continue_at", "number", "续写起始秒数", "0", min_value=0, max_value=600, step=1, sort_order=15),
            field("persona_id", "text", "歌手风格_PersonaID", "", sort_order=16),
            field("reference_audio_id", "text", "歌手风格_参考音频ID", "", sort_order=17),
        ],
    },
    {
        "id": "speech-2.8-hd",
        "node_class": "TikpanMiniMaxSpeech28HDNode",
        "name": "MiniMax Speech 2.8 HD",
        "category_key": "audio_generation",
        "provider": "MiniMax / Tikpan",
        "description": "高清语音合成，官方音色下拉和高级音频参数已对齐。",
        "api_type": "tikpan_proxy",
        "endpoint": "/minimax/v1/t2a_v2",
        "upstream_model": "speech-2.8-hd",
        "sort_order": 2,
        "pricing": {"billing_mode": "per_unit", "unit_field": "text_chars", "unit_name": "字符", "unit_credits": 0.01, "min_credits": 1},
        "usage": usage(
            "填写合成文本，选择音色；若选自定义 voice_id，在高级参数中填写自定义voice_id。",
            "语速、音量、音调、采样率、比特率、格式、声道数与 ComfyUI 节点一致。",
        ),
        "fields": [],
    },
    {
        "id": "speech-2.8-turbo",
        "node_class": "TikpanMiniMaxSpeech28TurboNode",
        "name": "MiniMax Speech 2.8 Turbo",
        "category_key": "audio_generation",
        "provider": "MiniMax / Tikpan",
        "description": "极速语音合成，适合批量配音和低延迟场景。",
        "api_type": "tikpan_proxy",
        "endpoint": "/minimax/v1/t2a_v2",
        "upstream_model": "speech-2.8-turbo",
        "sort_order": 3,
        "pricing": {"billing_mode": "per_unit", "unit_field": "text_chars", "unit_name": "字符", "unit_credits": 0.006, "min_credits": 1},
        "usage": usage(
            "使用方法与 HD 版一致，Turbo 更偏速度和批量任务。",
            "长文本建议分段提交，避免单次请求过大造成等待时间过长。",
        ),
        "fields": [],
    },
    {
        "id": "gemini-3.1-flash-tts-preview",
        "node_class": "TikpanGemini31FlashTTSNode",
        "name": "Gemini 3.1 Flash TTS Preview",
        "category_key": "audio_generation",
        "provider": "Google / Tikpan",
        "description": "Gemini TTS 预览模型，内置官方 30+ 音色下拉。",
        "api_type": "tikpan_proxy",
        "endpoint": "/v1beta/models/gemini-3.1-flash-tts-preview:generateContent",
        "upstream_model": "gemini-3.1-flash-tts-preview",
        "sort_order": 4,
        "pricing": {"billing_mode": "per_unit", "unit_field": "text_chars", "unit_name": "字符", "unit_credits": 0.008, "min_credits": 1},
        "usage": usage(
            "填写合成文本，选择音色和语气指令；语言代码默认自动即可。",
            "如果官方新增音色但下拉还没有，选择自定义 voice_name 并填写高级参数。",
        ),
        "fields": [
            field("text", "textarea", "合成文本", "Say warmly: Welcome to Tikpan Gemini 3.1 Flash TTS preview. This voice is generated for a commercial-ready workflow.", required=1, rows=6, sort_order=1),
            field("model", "select", "模型", "gemini-3.1-flash-tts-preview", options=["gemini-3.1-flash-tts-preview"], sort_order=2),
            field("call_mode", "select", "调用方式", "geminitts 原生", options=["geminitts 原生", "gemini 原生", "openai 兼容"], sort_order=3),
            field("voice", "select", "音色", GEMINI_VOICE_OPTIONS[0], options=GEMINI_VOICE_OPTIONS, sort_order=4),
            field("style", "text", "语气指令", "自然、清晰、商业旁白风格", sort_order=5),
            field("language_code", "select", "语言代码", "自动", options=["自动", "zh-CN", "en-US", "ja-JP", "ko-KR", "yue-HK", "fr-FR", "de-DE", "es-ES"], sort_order=6),
            field("sample_rate", "select", "采样率", "24000", options=["24000"], sort_order=7),
            field("post_retry", "select", "POST重试策略", "幂等键轻重试", options=["幂等键轻重试", "保守不重试POST"], sort_order=8),
            field("verify_tls", "checkbox", "校验HTTPS证书", "true", sort_order=9),
            field("custom_voice_name", "text", "自定义voice_name", "", sort_order=10),
            field("use_cache", "checkbox", "复用本地缓存", "true", sort_order=11),
            SKIP_ERROR,
            field("advanced_json", "textarea", "高级自定义_JSON", "", rows=3, sort_order=13),
        ],
    },
    {
        "id": "doubao-tts-2.0",
        "node_class": "TikpanDoubaoTTS20Node",
        "name": "豆包语音合成 2.0",
        "category_key": "audio_generation",
        "provider": "火山/豆包 / Tikpan",
        "description": "豆包语音合成 2.0，官方音色和旧版兼容音色均已做下拉。",
        "api_type": "tikpan_proxy",
        "endpoint": "/api/v3/tts/unidirectional/sse",
        "upstream_model": "doubao-tts-2.0",
        "sort_order": 5,
        "pricing": {"billing_mode": "per_unit", "unit_field": "text_chars", "unit_name": "字符", "unit_credits": 0.005, "min_credits": 1},
        "usage": usage(
            "填写合成文本，选择官方音色；若选自定义 voice_type，在高级参数中填写。",
            "情感、采样率、资源ID、接口路径和高级 JSON 与本地节点一致，默认接口路径绑定 Tikpan 中转站。",
        ),
        "fields": [
            field("text", "textarea", "合成文本", "欢迎使用 Tikpan 豆包语音合成 2.0。现在音色已经整理成下拉框，普通用户不用再手动查 voice_type。", required=1, rows=6, sort_order=1),
            field("model", "select", "模型", "doubao-tts-2.0", options=["doubao-tts-2.0"], sort_order=2),
            field("voice", "select", "音色", DOUBAO_VOICE_OPTIONS[0], options=DOUBAO_VOICE_OPTIONS, sort_order=3),
            field("speed", "number", "语速", "1.0", min_value=0.5, max_value=2.0, step=0.05, sort_order=4),
            field("volume", "number", "音量", "1.0", min_value=0.1, max_value=3.0, step=0.05, sort_order=5),
            field("pitch", "number", "音调", "1.0", min_value=0.5, max_value=2.0, step=0.05, sort_order=6),
            field("emotion", "select", "情感", "默认不传", options=["默认不传", "happy", "sad", "angry", "fearful", "surprised", "neutral"], sort_order=7),
            field("audio_format", "select", "音频格式", "mp3", options=["mp3", "wav", "pcm"], sort_order=8),
            field("sample_rate", "select", "采样率", "24000", options=["24000", "16000", "22050", "32000", "44100", "48000"], sort_order=9),
            field("post_retry", "select", "POST重试策略", "幂等键轻重试", options=["幂等键轻重试", "保守不重试POST"], sort_order=10),
            field("verify_tls", "checkbox", "校验HTTPS证书", "true", sort_order=11),
            field("custom_voice_type", "text", "自定义voice_type", "", sort_order=12),
            field("volc_app_id", "text", "火山AppID_可选", "", sort_order=13),
            field("resource_id", "select", "资源ID", "seed-tts-2.0", options=["seed-tts-2.0", "seed-tts-1.0", "volc.service_type.10029", "seed-icl-2.0", "seed-icl-1.0"], sort_order=14),
            field("api_path", "text", "接口路径", "/api/v3/tts/unidirectional/sse", sort_order=15),
            field("user_id", "text", "用户ID", "tikpan_comfyui_user", sort_order=16),
            field("use_cache", "checkbox", "复用本地缓存", "true", sort_order=17),
            SKIP_ERROR,
            field("advanced_json", "textarea", "高级自定义_JSON", "", rows=3, sort_order=19),
        ],
    },
    {
        "id": "gpt-5-mini",
        "node_class": "TikpanGPT5MiniResponsesNode",
        "name": "GPT-5 Mini 多模态推理",
        "category_key": "analysis_tools",
        "provider": "OpenAI / Tikpan",
        "description": "文本、图片、视频帧、文件 URL 分析，适合提示词优化、素材分析和结构化输出。",
        "api_type": "openai_responses",
        "endpoint": "/v1/responses",
        "upstream_model": "gpt-5.4-mini",
        "sort_order": 1,
        "pricing": {"billing_mode": "per_unit", "unit_field": "max_output_tokens", "unit_name": "token预算", "unit_credits": 0.002, "min_credits": 2},
        "usage": usage(
            "选择任务类型，填写用户问题和系统指令；图片可上传，也可在图片URL列表中填写。",
            "输出格式可选中文报告、Markdown、JSON 或提示词优化；最大输出 Token 默认 4096，可按任务调大。",
            "Pro/mini 的 Token 上限取决于上游官方模型和 Tikpan 中转站限制，网页只做预算输入，不会突破官方限制。",
        ),
        "fields": [
            field("model", "select", "模型", "gpt-5.4-mini", options=["gpt-5.4-mini"], sort_order=1),
            field("task_type", "select", "任务类型", "通用问答", options=["通用问答", "图片理解分析", "视频抽帧分析", "商品卖点提炼", "广告文案与落地页优化", "代码/JSON/数据分析", "提示词优化", "安全合规检查", "自定义"], sort_order=2),
            field("prompt", "textarea", "用户问题", "请分析输入内容，给出清晰、可执行、适合商业使用的中文结论。", required=1, rows=6, sort_order=3),
            field("system_prompt", "textarea", "系统指令", "你是 Tikpan 的商业级 AI 助手，回答要准确、结构化、可执行。信息不足时说明不确定性，不要编造。", rows=3, sort_order=4),
            field("output_format", "select", "输出格式", "Markdown结构化", options=["中文报告", "Markdown结构化", "JSON结构化", "提示词优化"], sort_order=5),
            field("reasoning_effort", "select", "推理强度", "低｜low", options=["最省｜minimal", "低｜low", "中｜medium", "高｜high"], sort_order=6),
            field("verbosity", "select", "回答详细度", "适中｜medium", options=["简洁｜low", "适中｜medium", "详细｜high"], sort_order=7),
            field("max_output_tokens", "number", "最大输出Token", "4096", min_value=256, max_value=32768, step=256, sort_order=8),
            field("temperature", "number", "创意温度", "1.0", min_value=0, max_value=2, step=0.05, sort_order=9),
            field("image_detail", "select", "图片细节", "自动｜auto", options=["自动｜auto", "低清省费用｜low", "高清细节｜high"], sort_order=10),
            field("frame_strategy", "select", "抽帧策略", "混合智能", options=["均匀覆盖", "按秒抽帧", "首尾加密", "运动变化优先", "混合智能"], sort_order=11),
            field("video_fps", "number", "视频帧率FPS", "24", min_value=1, max_value=120, step=1, sort_order=12),
            field("max_frames", "number", "最大抽帧数", "12", min_value=1, max_value=48, step=1, sort_order=13),
            field("web_search", "checkbox", "启用联网搜索", "", sort_order=14),
            field("url_error_policy", "select", "URL错误处理", "严格报错", options=["严格报错", "跳过坏链接并写日志"], sort_order=15),
            field("post_retry", "select", "POST重试策略", "幂等键轻重试", options=["幂等键轻重试", "保守不重试POST"], sort_order=16),
            field("use_cache", "checkbox", "复用本地缓存", "true", sort_order=17),
            SKIP_ERROR,
            field("verify_tls", "checkbox", "校验HTTPS证书", "true", sort_order=19),
            REFERENCE_IMAGES,
            field("image_urls", "textarea", "图片URL列表", "", rows=3, sort_order=81),
            field("file_urls", "textarea", "文件URL列表", "", rows=3, sort_order=82),
            field("local_file_paths", "textarea", "本地文件路径", "", rows=3, sort_order=83),
            field("advanced_json", "textarea", "高级自定义JSON", "", rows=3, sort_order=84),
        ],
    },
    {
        "id": "gemini-3-flash-preview",
        "node_class": "TikpanGemini3FlashPreviewAnalystNode",
        "name": "Gemini 3 Flash Preview 图片/视频分析",
        "category_key": "analysis_tools",
        "provider": "Google / Tikpan",
        "description": "图片、视频和多媒体分析，适合画面反推、视频拆解和结构化报告。",
        "api_type": "gemini_analysis",
        "endpoint": "/v1beta/models/gemini-3-flash-preview:generateContent",
        "upstream_model": "gemini-3-flash-preview",
        "sort_order": 2,
        "pricing": {"billing_mode": "per_unit", "unit_field": "max_output_tokens", "unit_name": "token预算", "unit_credits": 0.002, "min_credits": 2},
        "usage": usage(
            "选择分析任务，填写分析要求；上传图片或填写视频URL即可分析。",
            "视频任务建议先控制最大抽帧数，成本更稳定；需要原视频理解时再选择高成本输入策略。",
        ),
        "fields": [
            field("model", "select", "模型", "gemini-3-flash-preview", options=["gemini-3-flash-preview"], sort_order=1),
            field("analysis_task", "select", "分析任务", "通用分析", options=["通用分析", "视频分镜拆解", "商品卖点分析", "广告素材诊断", "画面提示词反推", "安全与合规检查", "自定义"], sort_order=2),
            field("prompt", "textarea", "分析要求", "请分析画面主体、场景、动作、镜头、光线、色彩、文字信息、潜在问题，并给出可复用的生成提示词。", required=1, rows=6, sort_order=3),
            field("output_format", "select", "输出格式", "Markdown结构化", options=["中文报告", "Markdown结构化", "JSON结构化", "提示词优化"], sort_order=4),
            field("max_output_tokens", "number", "最大输出Token", "4096", min_value=256, max_value=32768, step=256, sort_order=5),
            field("temperature", "number", "创意温度", "0.3", min_value=0, max_value=2, step=0.05, sort_order=6),
            field("media_resolution", "select", "媒体解析度", "默认", options=["默认", "低清省费用｜low", "均衡｜medium", "高清细节｜high"], sort_order=7),
            field("frame_strategy", "select", "抽帧策略", "混合智能", options=["均匀覆盖", "按秒抽帧", "首尾加密", "运动变化优先", "混合智能"], sort_order=8),
            field("video_fps", "number", "视频帧率FPS", "24", min_value=1, max_value=120, step=1, sort_order=9),
            field("max_frames", "number", "最大抽帧数", "24", min_value=1, max_value=48, step=1, sort_order=10),
            field("video_input_strategy", "select", "视频输入策略", "自动优先抽帧", options=["自动优先抽帧", "只用抽帧", "只用视频原件", "抽帧+视频原件(高成本)"], sort_order=11),
            field("url_error_policy", "select", "URL错误处理", "严格报错", options=["严格报错", "跳过坏链接并写日志"], sort_order=12),
            field("post_retry", "select", "POST重试策略", "幂等键轻重试", options=["幂等键轻重试", "保守不重试POST"], sort_order=13),
            field("use_cache", "checkbox", "复用本地缓存", "true", sort_order=14),
            SKIP_ERROR,
            field("verify_tls", "checkbox", "校验HTTPS证书", "true", sort_order=16),
            REFERENCE_IMAGES,
            field("image_urls", "textarea", "图片URL列表", "", rows=3, sort_order=81),
            field("video_url", "text", "视频URL", "", sort_order=82),
            field("local_video_path", "text", "本地视频路径", "", sort_order=83),
            field("advanced_json", "textarea", "高级自定义JSON", "", rows=3, sort_order=84),
        ],
    },
    {
        "id": "grok-prompt-optimizer",
        "node_class": "TikpanGrokPromptOptimizerNode",
        "name": "Grok 多图剧本重构专家",
        "category_key": "analysis_tools",
        "provider": "Tikpan",
        "description": "把分析报告重构为适合视频/图像模型的提示词。",
        "api_type": "tikpan_proxy",
        "endpoint": "/v1/chat/completions",
        "upstream_model": "gpt-5.4-mini",
        "sort_order": 3,
        "pricing": {"credits_1k": 2, "credits_2k": 2, "credits_4k": 2, "billing_mode": "flat"},
        "usage": usage(
            "粘贴 Gemini 原片拆解报告，填写核心产品与植入场景，系统会重构成更适合生成模型的提示词。",
            "可在图1-图7主体描述中说明参考图对应物体，便于脚本中用 @img 标注。",
        ),
        "fields": [
            field("model", "select", "文本处理模型", "gpt-5.4-mini", options=["gpt-5.4-mini", "gpt-4o", "gpt-4-turbo", "claude-3.5-sonnet"], sort_order=1),
            field("prompt", "textarea", "Gemini原片拆解报告", "", required=1, rows=6, sort_order=2),
            field("product_context", "textarea", "核心产品与植入场景", "【产品名称】：\n【核心功能/卖点】：\n【期望植入的场景或动作】：", rows=4, sort_order=3),
            field("style_adjustment", "textarea", "氛围与运镜微调", "保留原片的丝滑运镜，将背景的色调改为具有未来科技感的赛博朋克风。", rows=3, sort_order=4),
            *[field(f"image_{i}_subject", "text", f"图{i}_对应的主体描述", "", sort_order=10 + i) for i in range(1, 8)],
        ],
    },
    {
        "id": "gemini-video-analyst-legacy",
        "node_class": "TikpanGeminiVideoAnalystNode",
        "name": "AI 音视频双轨智能解析",
        "category_key": "analysis_tools",
        "provider": "Google / Tikpan",
        "description": "旧版 Gemini 视频帧和音频分析节点入口，保留给已有工作流迁移。",
        "api_type": "gemini_analysis",
        "endpoint": "/v1beta/models/gemini-3.1-flash:generateContent",
        "upstream_model": "gemini-3.1-flash",
        "sort_order": 4,
        "pricing": {"billing_mode": "per_unit", "unit_field": "max_output_tokens", "unit_name": "token预算", "unit_credits": 0.002, "min_credits": 2},
        "usage": usage(
            "上传视频帧图片，填写重点分析要求；视频帧率用于估算真实物理时长。",
            "这是旧版兼容入口，新项目优先使用 Gemini 3 Flash Preview 分析节点。",
        ),
        "fields": [
            field("prompt", "textarea", "重点分析要求", "请重点关注物理规律、光影变化和人物微表情。", rows=4, sort_order=1),
            field("video_fps", "number", "视频帧率FPS", "24", min_value=8, max_value=60, step=1, sort_order=2),
            field("model", "select", "分析模型", "gemini-3.1-flash", options=["gemini-3.1-flash", "gemini-3.1-pro", "gpt-5.4-mini", "gpt-4o"], sort_order=3),
            field("reference_images", "file_image", "视频帧_IMAGE", "", max_count=24, rows=0, sort_order=4),
            field("verify_tls", "checkbox", "校验HTTPS证书", "true", sort_order=5),
        ],
    },
    {
        "id": "tikpan-task-fetcher",
        "node_class": "TikpanTaskFetcherNode",
        "name": "异步任务查询与下载",
        "category_key": "utility_tools",
        "provider": "Tikpan",
        "description": "查询异步视频/音频任务并下载结果，字段对齐任务查询节点。",
        "api_type": "tikpan_proxy",
        "endpoint": "/v1/tasks/{task_id}",
        "upstream_model": "task-fetcher",
        "sort_order": 1,
        "pricing": {"credits_1k": 0, "credits_2k": 0, "credits_4k": 0, "billing_mode": "flat"},
        "usage": usage(
            "填写异步提交返回的任务ID，设置文件名前缀、最长等待秒数和查询间隔。",
            "用于 HappyHorse、Suno、Veo 等异步任务的后续取回；该节点本身不产生新计费。",
        ),
        "fields": [
            field("task_id", "text", "任务ID", "", required=1, sort_order=1),
            field("file_prefix", "text", "文件名前缀", "Tikpan_Task", sort_order=2),
            field("max_wait_seconds", "number", "最长等待秒数", "600", min_value=30, max_value=3600, step=10, sort_order=3),
            field("poll_interval", "number", "查询间隔秒数", "10", min_value=5, max_value=60, step=5, sort_order=4),
        ],
    },
]


MINIMAX_COMMON_FIELDS = [
    field("text", "textarea", "合成文本", "欢迎使用 Tikpan 语音合成。你可以在文本中加入 <#0.5#> 控制停顿，也可以使用 (laughs) 或 (sighs) 这类音效标签。", required=1, rows=6, sort_order=1),
    field("model", "select", "模型", "", options=[], sort_order=2),
    field("call_mode", "select", "调用方式", "同步语音 /t2a_v2", options=["同步语音 /t2a_v2", "异步语音 /t2a_async_v2"], sort_order=3),
    field("voice", "select", "音色", MINIMAX_VOICE_OPTIONS[0], options=MINIMAX_VOICE_OPTIONS, sort_order=4),
    field("language_boost", "select", "语言增强", "auto", options=["auto", "Chinese", "Chinese,Yue", "English", "Japanese", "Korean", "Thai", "Vietnamese", "Indonesian", "Spanish", "French", "Portuguese", "German", "Arabic", "Russian", "Italian", "Hindi", "Malay", "Filipino", "Tamil", "Persian"], sort_order=5),
    field("speed", "number", "语速", "1.0", min_value=0.5, max_value=2.0, step=0.05, sort_order=6),
    field("volume", "number", "音量", "1.0", min_value=0, max_value=10, step=0.1, sort_order=7),
    field("pitch", "number", "音调", "0", min_value=-12, max_value=12, step=1, sort_order=8),
    field("emotion", "select", "情绪", "默认不传", options=["默认不传", "happy", "sad", "angry", "fearful", "disgusted", "surprised", "neutral"], sort_order=9),
    field("sample_rate", "select", "采样率", "32000", options=["32000", "44100", "24000", "22050", "16000", "8000"], sort_order=10),
    field("bitrate", "select", "比特率", "128000", options=["128000", "256000", "64000", "32000"], sort_order=11),
    field("audio_format", "select", "音频格式", "mp3", options=["mp3", "wav", "flac"], sort_order=12),
    field("channel", "select", "声道数", "1", options=["1", "2"], sort_order=13),
    field("post_retry", "select", "POST重试策略", "幂等键轻重试", options=["幂等键轻重试", "保守不重试POST"], sort_order=14),
    field("verify_tls", "checkbox", "校验HTTPS证书", "true", sort_order=15),
    field("custom_voice_id", "text", "自定义voice_id", "", sort_order=16),
    field("output_format", "select", "同步返回格式", "hex", options=["hex", "url"], sort_order=17),
    field("pronunciation_dict", "textarea", "发音字典_tone_每行一条", "", rows=3, sort_order=18),
    field("use_cache", "checkbox", "复用本地缓存", "true", sort_order=19),
    SKIP_ERROR,
    field("advanced_json", "textarea", "高级自定义_JSON", "", rows=3, sort_order=21),
]

for model in MODELS:
    if model["id"] in {"speech-2.8-hd", "speech-2.8-turbo"}:
        model_fields = []
        for item in MINIMAX_COMMON_FIELDS:
            copied = dict(item)
            if copied["field_key"] == "model":
                copied["default_value"] = model["id"]
                copied["options"] = [model["id"]]
            model_fields.append(copied)
        model["fields"] = model_fields
