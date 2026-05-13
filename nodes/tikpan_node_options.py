"""Shared ComfyUI option helpers for Tikpan nodes.

The UI should be friendly to Chinese users, while payloads still need the raw
provider values.  Dropdown labels use the pattern ``中文说明｜raw_value``.
"""

OPTION_SEPARATOR = "｜"


def option_value(value, default=""):
    """Return the raw API value from a Chinese dropdown label."""
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    if OPTION_SEPARATOR in text:
        return text.split(OPTION_SEPARATOR)[-1].strip() or default
    return text


def pick(kwargs, *keys, default=None):
    """Read the first present ComfyUI argument, keeping old workflow aliases."""
    for key in keys:
        if key in kwargs and kwargs.get(key) is not None:
            return kwargs.get(key)
    return default


def option_int(value, default=0, minimum=None, maximum=None):
    raw = option_value(value, str(default))
    try:
        number = int(float(str(raw).replace("秒", "").replace("s", "").strip()))
    except Exception:
        number = int(default)
    if minimum is not None:
        number = max(minimum, number)
    if maximum is not None:
        number = min(maximum, number)
    return number


def option_bool(value, truthy=("开启", "有水印", "true", "True", "1", True)):
    raw = option_value(value, value)
    return raw in truthy


def normalize_seed(value, default=888888, maximum=2147483647, allow_random_none=False):
    """Normalize legacy seed values while keeping old workflows loadable.

    Older workflows may contain -1 to mean "random". New UI widgets use a
    visible non-negative seed so users are not surprised by hidden randomness.
    """
    try:
        seed = int(value)
    except Exception:
        seed = int(default)
    if seed < 0:
        return None if allow_random_none else int(default)
    if maximum is not None:
        max_seed = int(maximum)
        if seed > max_seed:
            seed = seed % max_seed or max_seed
    return seed


QUALITY_OPTIONS = [
    "自动｜auto",
    "快速低消耗｜low",
    "均衡质量｜medium",
    "高质量细节｜high",
]

MODERATION_OPTIONS = [
    "自动审核｜auto",
    "宽松审核｜low",
    "严格审核｜high",
]

BACKGROUND_OPTIONS = [
    "自动背景｜auto",
    "不透明背景｜opaque",
    "透明背景｜transparent",
]

IMAGE_FORMAT_OPTIONS = [
    "PNG｜png",
    "JPEG｜jpeg",
    "WEBP｜webp",
]

RESPONSE_FORMAT_OPTIONS = [
    "云端链接｜url",
    "Base64｜b64_json",
]

WATERMARK_OPTIONS = ["无水印", "有水印"]
ON_OFF_AUTO_OPTIONS = ["关闭", "自动"]
ON_OFF_OPTIONS = ["关闭", "开启"]

VIDEO_DURATION_OPTIONS = [
    "3秒｜3",
    "5秒｜5",
    "8秒｜8",
    "10秒｜10",
    "15秒｜15",
]

GROK_DURATION_OPTIONS = ["6秒｜6s", "10秒｜10s"]

GROK_ASPECT_OPTIONS = [
    "16:9 横屏｜16:9",
    "9:16 竖屏｜9:16",
    "1:1 方形｜1024x1024",
]

SUNO_STYLE_OPTIONS = [
    "流行｜Pop｜pop",
    "电影感｜Cinematic｜cinematic, orchestral, emotional",
    "短视频爆款｜Viral Short｜catchy pop, upbeat, hook, modern",
    "国风流行｜Chinese Pop｜mandopop, chinese pop, emotional",
    "电子舞曲｜EDM｜edm, dance, electronic, energetic",
    "摇滚｜Rock｜rock, electric guitar, powerful drums",
    "嘻哈说唱｜Hip Hop｜hip hop, rap, trap beat",
    "R&B｜R&B｜r&b, soulful, smooth",
    "民谣｜Folk｜folk, acoustic guitar, warm vocal",
    "爵士｜Jazz｜jazz, swing, smooth, saxophone",
    "Lo-fi｜Lo-fi｜lofi, chill, mellow, warm",
    "城市流行｜City Pop｜city pop, retro, groovy",
    "二次元｜Anime｜anime, j-pop, energetic",
    "史诗配乐｜Epic｜epic, cinematic, orchestral, trailer",
    "纯钢琴｜Piano｜piano, instrumental, emotional",
    "自定义风格｜custom",
]

SUNO_MODEL_OPTIONS = [
    "V5 最新通用｜chirp-v5",
    "Fenix 高质量实验｜chirp-fenix",
    "V4 稳定通用｜chirp-v4",
    "Auk 新版实验｜chirp-auk",
    "V3.5 兼容旧作品｜chirp-v3-5",
    "V3.0 兼容旧作品｜chirp-v3-0",
]

SUNO_VOCAL_GENDER_OPTIONS = [
    "默认不传｜",
    "女声倾向｜f",
    "男声倾向｜m",
]
