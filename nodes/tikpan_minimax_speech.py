import base64
import hashlib
import json
import mimetypes
import os
import time
import traceback
from pathlib import Path

import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import comfy.model_management
import comfy.utils
import folder_paths


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_HOST = "https://tikpan.com"
MINIMAX_API_BASE_URL = f"{API_HOST}/minimax/v1"
DEFAULT_API_BASE_URL = MINIMAX_API_BASE_URL
RECOVERY_ROOT = Path(__file__).resolve().parents[1] / "recovery"


MINIMAX_SYSTEM_VOICES = [
    ("中文普通话", "可靠管理者", "稳重商务男声，适合企业旁白", "Chinese (Mandarin)_Reliable_Executive"),
    ("中文普通话", "新闻主播", "标准播报风格，适合资讯解说", "Chinese (Mandarin)_News_Anchor"),
    ("中文普通话", "洒脱青年", "年轻自然男声，适合口播", "Chinese (Mandarin)_Unrestrained_Young_Man"),
    ("中文普通话", "成熟女性", "沉稳女声，适合品牌叙事", "Chinese (Mandarin)_Mature_Woman"),
    ("中文普通话", "傲娇小姐", "角色感女声", "Arrogant_Miss"),
    ("中文普通话", "机甲机器人", "机械质感角色音", "Robot_Armor"),
    ("中文普通话", "热心阿姨", "亲切生活化女声", "Chinese (Mandarin)_Kind-hearted_Antie"),
    ("中文普通话", "港风空乘", "港风服务播报", "Chinese (Mandarin)_HK_Flight_Attendant"),
    ("中文普通话", "幽默老人", "年长幽默角色音", "Chinese (Mandarin)_Humorous_Elder"),
    ("中文普通话", "绅士男声", "礼貌沉稳男声", "Chinese (Mandarin)_Gentleman"),
    ("中文普通话", "暖心闺蜜", "亲近自然女声", "Chinese (Mandarin)_Warm_Bestie"),
    ("中文普通话", "倔强朋友", "个性角色音", "Chinese (Mandarin)_Stubborn_Friend"),
    ("中文普通话", "甜美女声", "甜美自然", "Chinese (Mandarin)_Sweet_Lady"),
    ("中文普通话", "南方青年", "南方口音男声", "Chinese (Mandarin)_Southern_Young_Man"),
    ("中文普通话", "智慧女性", "成熟知性", "Chinese (Mandarin)_Wise_Women"),
    ("中文普通话", "温柔青年", "柔和男声", "Chinese (Mandarin)_Gentle_Youth"),
    ("中文普通话", "暖心女孩", "温暖女声", "Chinese (Mandarin)_Warm_Girl"),
    ("中文普通话", "男播音员", "标准播音男声", "Chinese (Mandarin)_Male_Announcer"),
    ("中文普通话", "慈祥长者", "年长亲切男声", "Chinese (Mandarin)_Kind-hearted_Elder"),
    ("中文普通话", "可爱精灵", "可爱角色音", "Chinese (Mandarin)_Cute_Spirit"),
    ("中文普通话", "电台主持", "电台节目风格", "Chinese (Mandarin)_Radio_Host"),
    ("中文普通话", "抒情声音", "柔和叙事", "Chinese (Mandarin)_Lyrical_Voice"),
    ("中文普通话", "直爽男孩", "清爽男声", "Chinese (Mandarin)_Straightforward_Boy"),
    ("中文普通话", "真诚成年人", "自然真诚", "Chinese (Mandarin)_Sincere_Adult"),
    ("中文普通话", "温和长辈", "温柔年长声线", "Chinese (Mandarin)_Gentle_Senior"),
    ("中文普通话", "清脆女孩", "清亮女声", "Chinese (Mandarin)_Crisp_Girl"),
    ("中文普通话", "纯真男孩", "少年感", "Chinese (Mandarin)_Pure-hearted_Boy"),
    ("中文普通话", "柔软女孩", "轻柔女声", "Chinese (Mandarin)_Soft_Girl"),
    ("中文普通话", "知性女孩", "知性年轻女声", "Chinese (Mandarin)_IntellectualGirl"),
    ("中文普通话", "暖心少女", "温暖甜美", "Chinese (Mandarin)_Warm_HeartedGirl"),
    ("中文普通话", "松弛女孩", "轻松自然", "Chinese (Mandarin)_Laid_BackGirl"),
    ("中文普通话", "探索女孩", "好奇活泼", "Chinese (Mandarin)_ExplorativeGirl"),
    ("中文普通话", "热心阿姨 2", "亲切长辈女声", "Chinese (Mandarin)_Warm-HeartedAunt"),
    ("中文普通话", "害羞女孩", "害羞柔和", "Chinese (Mandarin)_BashfulGirl"),
    ("英语", "Expressive Narrator", "表现力旁白", "English_expressive_narrator"),
    ("英语", "Radiant Girl", "明亮女声", "English_radiant_girl"),
    ("英语", "Magnetic Male", "磁性男声", "English_magnetic_voiced_man"),
    ("英语", "Upbeat Woman", "积极女声", "English_Upbeat_Woman"),
    ("英语", "Trustworthy Man", "可信赖男声", "English_Trustworth_Man"),
    ("英语", "Calm Woman", "冷静女声", "English_CalmWoman"),
    ("英语", "Deep Voice Man", "低沉男声", "English_ManWithDeepVoice"),
    ("英语", "Friendly Guy", "友好男声", "English_FriendlyPerson"),
    ("日语", "知性前辈", "知性成熟", "Japanese_IntellectualSenior"),
    ("日语", "果断公主", "角色女声", "Japanese_DecisivePrincess"),
    ("日语", "忠诚骑士", "角色男声", "Japanese_LoyalKnight"),
    ("日语", "冷静女王", "冷感角色", "Japanese_ColdQueen"),
    ("粤语", "专业女主持", "粤语播报女声", "Cantonese_ProfessionalHost (F)"),
    ("粤语", "温柔女士", "粤语温柔女声", "Cantonese_GentleLady"),
    ("粤语", "专业男主持", "粤语播报男声", "Cantonese_ProfessionalHost (M)"),
    ("粤语", "俏皮男声", "粤语活泼男声", "Cantonese_PlayfulMan"),
    ("韩语", "温柔女士", "韩语温柔女声", "Korean_SoothingLady"),
    ("韩语", "可靠姐姐", "韩语成熟女声", "Korean_ReliableSister"),
    ("西语", "Narrator", "西语旁白", "Spanish_Narrator"),
    ("葡语", "Narrator", "葡语旁白", "Portuguese_Narrator"),
    ("法语", "Male Narrator", "法语男旁白", "French_MaleNarrator"),
    ("印尼语", "Sweet Girl", "印尼语甜美女声", "Indonesian_SweetGirl"),
    ("德语", "Friendly Man", "德语友好男声", "German_FriendlyMan"),
    ("俄语", "Reliable Man", "俄语可靠男声", "Russian_ReliableMan"),
    ("泰语", "Serene Man", "泰语沉静男声", "Thai_male_1_sample8"),
    ("印地语", "News Anchor", "印地语新闻女声", "hindi_female_1_v2"),
]


def minimax_voice_label(item):
    language, name, desc, voice_id = item
    return f"{language}｜{name}｜{desc}｜{voice_id}"


MINIMAX_VOICE_OPTIONS = [minimax_voice_label(item) for item in MINIMAX_SYSTEM_VOICES] + [
    "自定义 voice_id｜在下方填写"
]


class TikpanMiniMaxSpeech28BaseNode:
    MODEL_NAME = "speech-2.8-hd"
    MODEL_TITLE = "speech-2.8-hd 高清语音合成"
    MODEL_DESCRIPTION = "高清语音合成，适合细节更丰富的旁白、广告口播和商业配音。"
    RECOVERY_SUFFIX = "speech_2_8_hd"
    FILE_PREFIX = "Tikpan_Speech_2_8_HD"
    USER_AGENT_SUFFIX = "Speech-2.8-HD"
    CACHE_PREFIX = "tikpan-speech-2-8-hd"
    DISPLAY_NAME = "🎙️ Tikpan: speech-2.8-hd 高清语音合成"

    @classmethod
    def INPUT_TYPES(cls):
        languages = [
            "auto",
            "Chinese",
            "Chinese,Yue",
            "English",
            "Japanese",
            "Korean",
            "Thai",
            "Vietnamese",
            "Indonesian",
            "Spanish",
            "French",
            "Portuguese",
            "German",
            "Arabic",
            "Russian",
            "Italian",
            "Hindi",
            "Malay",
            "Filipino",
            "Tamil",
            "Persian",
        ]
        return {
            "required": {
                "💵_福利_💵": (
                    [f"🔥 {cls.MODEL_TITLE} | 自定义音色/复刻音色按上游规则额外计费"],
                ),
                "获取密钥请访问": (
                    ["👉 https://tikpan.com (官方授权 Key 获取入口)"],
                ),
                "API_密钥": ("STRING", {"default": "sk-"}),
                "合成文本": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": f"欢迎使用 Tikpan {cls.MODEL_NAME}。你可以在文本中加入 <#0.5#> 控制停顿，也可以使用 (laughs) 或 (sighs) 这类音效标签。",
                    },
                ),
                "模型": ([cls.MODEL_NAME], {"default": cls.MODEL_NAME}),
                "调用方式": (
                    ["同步语音 /t2a_v2", "异步语音 /t2a_async_v2"],
                    {"default": "同步语音 /t2a_v2"},
                ),
                "音色": (MINIMAX_VOICE_OPTIONS, {"default": minimax_voice_label(MINIMAX_SYSTEM_VOICES[0])}),
                "语言增强": (languages, {"default": "auto"}),
                "语速": ("FLOAT", {"default": 1.0, "min": 0.5, "max": 2.0, "step": 0.05}),
                "音量": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 10.0, "step": 0.1}),
                "音调": ("INT", {"default": 0, "min": -12, "max": 12}),
                "情绪": (
                    ["默认不传", "happy", "sad", "angry", "fearful", "disgusted", "surprised", "neutral"],
                    {"default": "默认不传"},
                ),
                "采样率": (["32000", "44100", "24000", "22050", "16000", "8000"], {"default": "32000"}),
                "比特率": (["128000", "256000", "64000", "32000"], {"default": "128000"}),
                "音频格式": (["mp3", "wav", "flac"], {"default": "mp3"}),
                "声道数": (["1", "2"], {"default": "1"}),
                "POST重试策略": (["幂等键轻重试", "保守不重试POST"], {"default": "幂等键轻重试"}),
                "校验HTTPS证书": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "自定义voice_id": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "选择“自定义 voice_id”时填写；也兼容复刻音色、音色设计和官方新上线 voice_id。",
                    },
                ),
                "同步返回格式": (["hex", "url"], {"default": "hex"}),
                "发音字典_tone_每行一条": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "tooltip": "示例：燕少飞/(yan4)(shao3)(fei1) 或 omg/oh my god",
                    },
                ),
                "音色混合_JSON": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "tooltip": "高级参数，示例：[{\"voice_id\":\"xxx\",\"weight\":70},{\"voice_id\":\"yyy\",\"weight\":30}]",
                    },
                ),
                "声音效果": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "示例：spacious_echo。留空则不传 sound_effects。",
                    },
                ),
                "音色修饰_pitch": ("INT", {"default": 0, "min": -100, "max": 100}),
                "音色修饰_intensity": ("INT", {"default": 0, "min": -100, "max": 100}),
                "音色修饰_timbre": ("INT", {"default": 0, "min": -100, "max": 100}),
                "开启字幕": ("BOOLEAN", {"default": False}),
                "字幕类型": (["sentence", "word"], {"default": "sentence"}),
                "最长等待秒数": ("INT", {"default": 900, "min": 30, "max": 7200}),
                "轮询间隔秒数": ("INT", {"default": 5, "min": 3, "max": 60}),
                "复用本地缓存": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "相同文本和参数命中缓存时直接返回本地音频，减少误重复扣费。",
                    },
                ),
                "跳过错误": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "批量工作流可开启。失败时返回空音频和错误日志，不中断整个工作流。",
                    },
                ),
                "高级自定义_JSON": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "tooltip": "会深度合并到最终请求体，用于后续上游新增参数时临时透传。",
                    },
                ),
            },
    }

    DEFAULT_OPTIONAL_VALUES = {
        "POST重试策略": "幂等键轻重试",
        "校验HTTPS证书": True,
        "自定义voice_id": "",
        "同步返回格式": "hex",
        "发音字典_tone_每行一条": "",
        "音色混合_JSON": "",
        "声音效果": "",
        "音色修饰_pitch": 0,
        "音色修饰_intensity": 0,
        "音色修饰_timbre": 0,
        "开启字幕": False,
        "字幕类型": "sentence",
        "最长等待秒数": 900,
        "轮询间隔秒数": 5,
        "复用本地缓存": True,
        "跳过错误": False,
        "高级自定义_JSON": "",
    }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "AUDIO")
    RETURN_NAMES = (
        "📁_音频路径",
        "🔗_音频链接",
        "🆔_任务ID",
        "🆔_文件ID",
        "💰_计费字符数",
        "📋_状态日志",
        "🎧_音频流",
    )
    OUTPUT_NODE = True
    FUNCTION = "generate_speech"
    CATEGORY = "👑 Tikpan 官方独家节点"

    def empty_audio(self):
        try:
            import torch

            return {"waveform": torch.zeros((1, 1, 1), dtype=torch.float32), "sample_rate": 44100}
        except Exception:
            return {"waveform": None, "sample_rate": 44100}

    def make_return(self, path="", url="", task_id="", file_id="", usage="", log="", audio=None):
        return (path, url, str(task_id or ""), str(file_id or ""), str(usage or ""), log, audio or self.empty_audio())

    def create_session(self, allow_post_retry=False):
        session = requests.Session()
        session.trust_env = False
        allowed_methods = ["HEAD", "GET", "OPTIONS"]
        if allow_post_retry:
            allowed_methods.append("POST")
        retries = Retry(
            total=2,
            connect=2,
            read=0,
            status=1,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=frozenset(allowed_methods),
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retries, pool_connections=20, pool_maxsize=20)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def audio_from_path(self, audio_path):
        if not audio_path or not os.path.exists(audio_path):
            return self.empty_audio()
        try:
            from comfy_extras.nodes_audio import load as load_audio_file

            waveform, sample_rate = load_audio_file(audio_path)
            return {"waveform": waveform.unsqueeze(0), "sample_rate": sample_rate}
        except Exception as e:
            print(f"[Tikpan-Speech] WARNING 音频流解码失败，只返回文件路径: {e}", flush=True)
            return self.empty_audio()

    def safe_json_text(self, value, max_len=1200):
        try:
            text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        except Exception:
            text = str(value)
        return text[:max_len] + ("...(truncated)" if len(text) > max_len else "")

    def safe_response_text(self, response, max_len=1200):
        try:
            return response.text[:max_len].strip()
        except Exception:
            return "无法解析上游响应"

    def payload_hash(self, payload, call_mode):
        raw = json.dumps({"call_mode": call_mode, "payload": payload}, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def recovery_dir(self):
        return RECOVERY_ROOT / self.RECOVERY_SUFFIX

    def save_recovery_record(self, cache_key, status, **fields):
        recovery_dir = self.recovery_dir()
        recovery_dir.mkdir(parents=True, exist_ok=True)
        record = {
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "model": self.MODEL_NAME,
            "cache_key": cache_key,
            "status": status,
            **fields,
        }
        latest_path = recovery_dir / f"{self.CACHE_PREFIX}-{cache_key[:32]}.json"
        events_path = recovery_dir / "events.jsonl"
        latest_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        with events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return str(latest_path)

    def cache_path(self, cache_key, audio_format):
        ext = self.normalize_audio_ext(audio_format)
        return self.recovery_dir() / f"{self.CACHE_PREFIX}-{cache_key[:32]}{ext}"

    def read_cache(self, cache_key, audio_format):
        path = self.cache_path(cache_key, audio_format)
        if path.exists() and path.stat().st_size > 128:
            return str(path)
        return ""

    def normalize_audio_ext(self, audio_format):
        audio_format = str(audio_format or "mp3").lower().strip()
        if audio_format == "wav":
            return ".wav"
        if audio_format == "flac":
            return ".flac"
        return ".mp3"

    def extension_from_response(self, url, response, fallback_format):
        content_type = str(response.headers.get("Content-Type", "")).lower()
        if "audio/mpeg" in content_type or "audio/mp3" in content_type:
            return ".mp3"
        if "audio/wav" in content_type or "audio/x-wav" in content_type:
            return ".wav"
        if "audio/flac" in content_type:
            return ".flac"
        guessed_ext = os.path.splitext(str(url).split("?")[0])[1].lower()
        if guessed_ext in {".mp3", ".wav", ".flac"}:
            return guessed_ext
        mime_guess, _ = mimetypes.guess_type(str(url))
        if mime_guess:
            ext = mimetypes.guess_extension(mime_guess)
            if ext in {".mp3", ".wav", ".flac"}:
                return ext
        return self.normalize_audio_ext(fallback_format)

    def write_audio_bytes(self, audio_bytes, cache_key, audio_format):
        if not audio_bytes or len(audio_bytes) <= 128:
            raise RuntimeError("上游返回的音频内容为空或过小，疑似错误页/无效文件。")
        self.recovery_dir().mkdir(parents=True, exist_ok=True)
        recovery_path = self.cache_path(cache_key, audio_format)
        recovery_path.write_bytes(audio_bytes)

        out_dir = folder_paths.get_output_directory()
        filename = f"{self.FILE_PREFIX}_{cache_key[:16]}{self.normalize_audio_ext(audio_format)}"
        output_path = os.path.join(out_dir, filename)
        with open(output_path, "wb") as f:
            f.write(audio_bytes)
        return output_path

    def parse_tone_lines(self, tone_text):
        tone_lines = []
        for line in str(tone_text or "").splitlines():
            line = line.strip()
            if line:
                tone_lines.append(line)
        return tone_lines

    def parse_json_field(self, raw, field_name):
        raw = str(raw or "").strip()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception as e:
            raise ValueError(f"{field_name} 不是合法 JSON: {e}")

    def deep_merge(self, base, override):
        if not isinstance(base, dict) or not isinstance(override, dict):
            return override
        merged = dict(base)
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = self.deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged

    def resolve_voice_id(self, selected_voice, custom_voice_id=""):
        selected_voice = str(selected_voice or "").strip()
        custom_voice_id = str(custom_voice_id or "").strip()
        if not selected_voice:
            selected_voice = minimax_voice_label(MINIMAX_SYSTEM_VOICES[0])
        if selected_voice.startswith("自定义"):
            if not custom_voice_id:
                raise ValueError("已选择自定义 voice_id，但没有填写“自定义voice_id”。")
            return custom_voice_id
        if "｜" in selected_voice:
            return selected_voice.split("｜")[-1].strip()
        return selected_voice

    def build_payload(self, kwargs, async_mode):
        values = dict(self.DEFAULT_OPTIONAL_VALUES)
        values.update(kwargs)
        text = str(values.get("合成文本") or "").strip()
        model = values.get("模型", self.MODEL_NAME)
        if model not in {self.MODEL_NAME}:
            model = self.MODEL_NAME
        voice_id = self.resolve_voice_id(
            values.get("音色") or values.get("音色ID"),
            values.get("自定义voice_id"),
        )
        audio_format = values.get("音频格式", "mp3")
        language_boost = values.get("语言增强", "auto")
        emotion = values.get("情绪", "默认不传")

        voice_setting = {
            "voice_id": voice_id,
            "speed": float(values.get("语速", 1.0)),
            "vol": float(values.get("音量", 1.0)),
            "pitch": int(values.get("音调", 0)),
        }
        if emotion != "默认不传":
            voice_setting["emotion"] = emotion

        if async_mode:
            audio_setting = {
                "audio_sample_rate": int(values.get("采样率", "32000")),
                "bitrate": int(values.get("比特率", "128000")),
                "format": audio_format,
                "channel": int(values.get("声道数", "1")),
            }
        else:
            audio_setting = {
                "sample_rate": int(values.get("采样率", "32000")),
                "bitrate": int(values.get("比特率", "128000")),
                "format": audio_format,
                "channel": int(values.get("声道数", "1")),
            }

        voice_modify = {
            "pitch": int(values.get("音色修饰_pitch", 0)),
            "intensity": int(values.get("音色修饰_intensity", 0)),
            "timbre": int(values.get("音色修饰_timbre", 0)),
        }
        sound_effects = str(values.get("声音效果") or "").strip()
        if sound_effects:
            voice_modify["sound_effects"] = sound_effects

        payload = {
            "model": model,
            "text": text,
            "language_boost": language_boost,
            "voice_setting": voice_setting,
            "audio_setting": audio_setting,
            "voice_modify": voice_modify,
            "subtitle_enable": bool(values.get("开启字幕", False)),
            "subtitle_type": values.get("字幕类型", "sentence"),
        }
        if not async_mode:
            payload["stream"] = False
            payload["output_format"] = values.get("同步返回格式", "hex")

        tone_lines = self.parse_tone_lines(values.get("发音字典_tone_每行一条"))
        if tone_lines:
            payload["pronunciation_dict"] = {"tone": tone_lines}

        timbre_weights = self.parse_json_field(values.get("音色混合_JSON"), "音色混合_JSON")
        if timbre_weights is not None:
            payload["timbre_weights"] = timbre_weights

        custom_payload = self.parse_json_field(values.get("高级自定义_JSON"), "高级自定义_JSON")
        if custom_payload is not None:
            if not isinstance(custom_payload, dict):
                raise ValueError("高级自定义_JSON 顶层必须是对象。")
            payload = self.deep_merge(payload, custom_payload)

        return payload

    def check_base_resp(self, res_json):
        if not isinstance(res_json, dict):
            raise RuntimeError("上游返回不是 JSON 对象。")
        base_resp = res_json.get("base_resp")
        if isinstance(base_resp, dict):
            code = base_resp.get("status_code")
            msg = base_resp.get("status_msg") or base_resp.get("message") or ""
            if code not in (None, 0, "0"):
                raise RuntimeError(f"上游返回错误: status_code={code} | {msg}")
        if res_json.get("error"):
            raise RuntimeError(f"上游返回错误: {self.safe_json_text(res_json.get('error'))}")

    def extract_sync_audio(self, res_json):
        data = res_json.get("data") if isinstance(res_json, dict) else {}
        if not isinstance(data, dict):
            data = {}
        audio_value = (
            data.get("audio")
            or data.get("audio_url")
            or data.get("url")
            or res_json.get("audio")
            or res_json.get("audio_url")
            or res_json.get("url")
        )
        if not audio_value:
            return "", ""
        audio_text = str(audio_value).strip()
        if audio_text.startswith("http://") or audio_text.startswith("https://"):
            return audio_text, "url"
        return audio_text, "hex"

    def decode_audio_text(self, audio_text):
        clean = str(audio_text or "").strip()
        if clean.startswith("data:"):
            clean = clean.split(",", 1)[-1]
        try:
            return bytes.fromhex(clean)
        except Exception:
            try:
                return base64.b64decode(clean)
            except Exception as e:
                raise RuntimeError(f"无法解码上游音频数据，既不是 hex 也不是 base64: {e}")

    def download_audio_url(self, session, url, cache_key, audio_format, headers=None, verify_tls=True):
        response = session.get(url, headers=headers or {}, timeout=(15, 300), verify=verify_tls)
        response.raise_for_status()
        content_type = str(response.headers.get("Content-Type", "")).lower()
        if "json" in content_type or response.content[:1] in (b"{", b"["):
            raise RuntimeError(f"下载音频时拿到错误响应: {response.text[:800]}")
        ext = self.extension_from_response(url, response, audio_format)
        return self.write_audio_bytes(response.content, cache_key, ext.lstrip("."))

    def submit_sync(self, session, base_url, headers, payload, cache_key, verify_tls=True):
        url = f"{base_url}/t2a_v2"
        response = session.post(url, json=payload, headers=headers, timeout=(15, 300), verify=verify_tls)
        if response.status_code != 200:
            raise RuntimeError(f"同步语音创建失败 | HTTP {response.status_code} | {self.safe_response_text(response)}")
        try:
            res_json = response.json()
        except Exception:
            raise RuntimeError(f"同步语音接口返回非 JSON: {self.safe_response_text(response)}")

        self.check_base_resp(res_json)
        audio_value, audio_kind = self.extract_sync_audio(res_json)
        if not audio_value:
            raise RuntimeError(f"同步语音成功但未找到 audio 字段: {self.safe_json_text(res_json)}")

        audio_format = payload.get("audio_setting", {}).get("format", "mp3")
        audio_url = ""
        if audio_kind == "url":
            audio_url = audio_value
            audio_path = self.download_audio_url(session, audio_url, cache_key, audio_format, verify_tls=verify_tls)
        else:
            audio_bytes = self.decode_audio_text(audio_value)
            audio_path = self.write_audio_bytes(audio_bytes, cache_key, audio_format)

        extra_info = res_json.get("extra_info") if isinstance(res_json.get("extra_info"), dict) else {}
        usage = extra_info.get("usage_characters") or extra_info.get("word_count") or len(payload.get("text", ""))
        trace_id = res_json.get("trace_id", "")
        return audio_path, audio_url, "", "", usage, trace_id, res_json

    def submit_async(self, session, base_url, headers, payload, cache_key, max_wait_seconds, poll_interval, verify_tls=True):
        create_url = f"{base_url}/t2a_async_v2"
        response = session.post(create_url, json=payload, headers=headers, timeout=(15, 120), verify=verify_tls)
        if response.status_code != 200:
            raise RuntimeError(f"异步语音创建失败 | HTTP {response.status_code} | {self.safe_response_text(response)}")
        try:
            create_json = response.json()
        except Exception:
            raise RuntimeError(f"异步语音创建接口返回非 JSON: {self.safe_response_text(response)}")

        self.check_base_resp(create_json)
        task_id = str(create_json.get("task_id") or create_json.get("id") or "").strip()
        file_id = str(create_json.get("file_id") or "").strip()
        usage = str(create_json.get("usage_characters") or len(payload.get("text", "")))
        if not task_id:
            raise RuntimeError(f"异步语音创建成功但未获取 task_id: {self.safe_json_text(create_json)}")

        print(f"[Tikpan-Speech] OK 异步任务创建成功 | task_id={task_id} | file_id={file_id}", flush=True)
        started = time.time()
        status = "processing"
        query_json = {}
        while time.time() - started <= max_wait_seconds:
            comfy.model_management.throw_exception_if_processing_interrupted()
            time.sleep(poll_interval)
            query_url = f"{base_url}/query/t2a_async_query_v2"
            query_response = session.get(
                query_url,
                params={"task_id": task_id},
                headers=headers,
                timeout=(15, 60),
                verify=verify_tls,
            )
            if query_response.status_code != 200:
                print(
                    f"[Tikpan-Speech] WARNING 查询失败 HTTP {query_response.status_code}: {self.safe_response_text(query_response, 300)}",
                    flush=True,
                )
                continue
            try:
                query_json = query_response.json()
            except Exception:
                print(f"[Tikpan-Speech] WARNING 查询返回非 JSON: {self.safe_response_text(query_response, 300)}", flush=True)
                continue

            self.check_base_resp(query_json)
            status = str(query_json.get("status") or "").lower()
            file_id = str(query_json.get("file_id") or file_id or "").strip()
            print(f"[Tikpan-Speech] POLL 任务轮询 | status={status} | file_id={file_id}", flush=True)
            if status == "success":
                break
            if status in {"failed", "expired"}:
                raise RuntimeError(f"异步语音任务失败 | status={status} | {self.safe_json_text(query_json)}")
        else:
            raise RuntimeError(f"异步语音任务超时 | task_id={task_id} | 已等待 {max_wait_seconds}s")

        if not file_id:
            raise RuntimeError(f"异步任务完成但没有 file_id，无法下载音频: {self.safe_json_text(query_json)}")

        retrieve_url = f"{base_url}/files/retrieve_content"
        retrieve_response = session.get(
            retrieve_url,
            params={"file_id": file_id},
            headers=headers,
            timeout=(15, 300),
            verify=verify_tls,
        )
        if retrieve_response.status_code != 200:
            raise RuntimeError(f"异步音频下载失败 | HTTP {retrieve_response.status_code} | {self.safe_response_text(retrieve_response)}")
        content_type = str(retrieve_response.headers.get("Content-Type", "")).lower()
        if "json" in content_type or retrieve_response.content[:1] in (b"{", b"["):
            raise RuntimeError(f"异步音频下载拿到错误响应: {retrieve_response.text[:800]}")

        audio_format = payload.get("audio_setting", {}).get("format", "mp3")
        audio_path = self.write_audio_bytes(retrieve_response.content, cache_key, audio_format)
        return audio_path, f"{retrieve_url}?file_id={file_id}", task_id, file_id, usage, status, query_json

    def generate_speech(self, **kwargs):
        start_time = time.time()
        values = dict(self.DEFAULT_OPTIONAL_VALUES)
        values.update(kwargs)
        api_key = str(values.get("API_密钥") or "").strip()
        text = str(values.get("合成文本") or "").strip()
        call_mode = values.get("调用方式", "同步语音 /t2a_v2")
        async_mode = "异步" in str(call_mode)
        skip_error = bool(values.get("跳过错误", False))
        use_cache = bool(values.get("复用本地缓存", True))
        audio_format = values.get("音频格式", "mp3")
        base_url = MINIMAX_API_BASE_URL
        post_retry = str(values.get("POST重试策略") or "幂等键轻重试") == "幂等键轻重试"
        verify_tls = bool(values.get("校验HTTPS证书", True))

        try:
            if not api_key or api_key == "sk-":
                return self.make_return(log="ERROR 错误：API 密钥为空，请填写有效 Tikpan API Key。")
            if not text:
                return self.make_return(log="ERROR 错误：合成文本不能为空。")
            if len(text) >= 100000:
                return self.make_return(log="ERROR 错误：异步接口文本需小于 100,000 字符；请拆分文本或改用文件任务链路。")
            if not async_mode and len(text) >= 10000:
                return self.make_return(log="ERROR 错误：同步接口文本需小于 10,000 字符；长文本请切换为异步语音。")

            payload = self.build_payload(values, async_mode=async_mode)
            cache_key = self.payload_hash(payload, "async" if async_mode else "sync")
            pbar = comfy.utils.ProgressBar(100)
            pbar.update(5)

            if use_cache:
                cached_path = self.read_cache(cache_key, audio_format)
                if cached_path:
                    audio = self.audio_from_path(cached_path)
                    log = f"OK 命中本地缓存，未重新请求上游，避免重复扣费 | path={cached_path}"
                    print(f"[Tikpan-Speech] {log}", flush=True)
                    return self.make_return(cached_path, "", "", "", len(text), log, audio)

            print(
                f"[Tikpan-Speech] START 启动 {self.MODEL_NAME} | 模式={'异步' if async_mode else '同步'} | 字符数={len(text)} | 格式={audio_format}",
                flush=True,
            )
            print(f"[Tikpan-Speech] PAYLOAD 请求摘要: {self.safe_json_text({k: v for k, v in payload.items() if k != 'text'}, 800)}", flush=True)
            recovery_path = self.save_recovery_record(
                cache_key,
                "pending",
                endpoint="/t2a_async_v2" if async_mode else "/t2a_v2",
                text_chars=len(text),
                payload_preview=self.safe_json_text({k: v for k, v in payload.items() if k != "text"}, 1600),
            )

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": f"Tikpan-ComfyUI-{self.USER_AGENT_SUFFIX}/1.1",
                "Idempotency-Key": f"{self.CACHE_PREFIX}-{cache_key[:32]}",
            }
            session = self.create_session(allow_post_retry=post_retry)

            try:
                if async_mode:
                    result = self.submit_async(
                        session,
                        base_url,
                        headers,
                        payload,
                        cache_key,
                        int(values.get("最长等待秒数", 900)),
                        int(values.get("轮询间隔秒数", 5)),
                        verify_tls=verify_tls,
                    )
                else:
                    result = self.submit_sync(session, base_url, headers, payload, cache_key, verify_tls=verify_tls)
            except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
                self.save_recovery_record(
                    cache_key,
                    "post_disconnected",
                    endpoint="/t2a_async_v2" if async_mode else "/t2a_v2",
                    error=str(e),
                    recovery_path=recovery_path,
                )
                raise RuntimeError(
                    f"网络在提交后断开：上游可能已经收到并扣费。建议先检查 recovery/{self.RECOVERY_SUFFIX} 中的记录，"
                    f"不要立刻改参数重复提交。cache_key={cache_key[:32]} | recovery={recovery_path}"
                )

            audio_path, audio_url, task_id, file_id, usage, trace_or_status, raw_json = result
            pbar.update(80)
            audio = self.audio_from_path(audio_path)
            elapsed = round(time.time() - start_time, 2)
            log = (
                f"OK {self.MODEL_NAME} 语音生成成功 | 模式={'异步' if async_mode else '同步'} | "
                f"计费字符={usage} | 耗时={elapsed}s | api={base_url} | post_retry={post_retry} | 音频={audio_path}"
            )
            if audio_url:
                log += f" | 链接={audio_url}"
            if task_id:
                log += f" | task_id={task_id}"
            if file_id:
                log += f" | file_id={file_id}"
            if trace_or_status:
                log += f" | trace/status={trace_or_status}"

            self.save_recovery_record(
                cache_key,
                "success",
                audio_path=audio_path,
                audio_url=audio_url,
                task_id=task_id,
                file_id=file_id,
                usage_characters=usage,
                response_preview=self.safe_json_text(raw_json, 2000),
            )
            pbar.update(100)
            print(f"[Tikpan-Speech] {log}", flush=True)
            return self.make_return(audio_path, audio_url, task_id, file_id, usage, log, audio)

        except Exception as e:
            tb = traceback.format_exc()
            err_msg = f"ERROR {self.MODEL_NAME} 节点运行失败: {e}\n{tb}"
            print(err_msg, flush=True)
            if not skip_error:
                raise
            return self.make_return(log=err_msg)


class TikpanMiniMaxSpeech28HDNode(TikpanMiniMaxSpeech28BaseNode):
    MODEL_NAME = "speech-2.8-hd"
    MODEL_TITLE = "speech-2.8-hd 高清语音合成"
    MODEL_DESCRIPTION = "高清语音合成，适合细节更丰富的旁白、广告口播和商业配音。"
    RECOVERY_SUFFIX = "speech_2_8_hd"
    FILE_PREFIX = "Tikpan_Speech_2_8_HD"
    USER_AGENT_SUFFIX = "Speech-2.8-HD"
    CACHE_PREFIX = "tikpan-speech-2-8-hd"
    DISPLAY_NAME = "🎙️ Tikpan: speech-2.8-hd 高清语音合成"


class TikpanMiniMaxSpeech28TurboNode(TikpanMiniMaxSpeech28BaseNode):
    MODEL_NAME = "speech-2.8-turbo"
    MODEL_TITLE = "speech-2.8-turbo 极速语音合成"
    MODEL_DESCRIPTION = "Turbo 语音合成，适合极速响应、短视频口播、批量配音和实时预览。"
    RECOVERY_SUFFIX = "speech_2_8_turbo"
    FILE_PREFIX = "Tikpan_Speech_2_8_Turbo"
    USER_AGENT_SUFFIX = "Speech-2.8-Turbo"
    CACHE_PREFIX = "tikpan-speech-2-8-turbo"
    DISPLAY_NAME = "🎙️ Tikpan: speech-2.8-turbo 极速语音合成"


NODE_CLASS_MAPPINGS = {
    "TikpanMiniMaxSpeech28HDNode": TikpanMiniMaxSpeech28HDNode,
    "TikpanMiniMaxSpeech28TurboNode": TikpanMiniMaxSpeech28TurboNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TikpanMiniMaxSpeech28HDNode": TikpanMiniMaxSpeech28HDNode.DISPLAY_NAME,
    "TikpanMiniMaxSpeech28TurboNode": TikpanMiniMaxSpeech28TurboNode.DISPLAY_NAME,
}
