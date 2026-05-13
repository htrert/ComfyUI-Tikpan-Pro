import base64
import hashlib
import json
import os
import time
import traceback
import uuid
from pathlib import Path

import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import folder_paths


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_HOST = "https://tikpan.com"
API_PATH = "/api/v3/tts/unidirectional/sse"
DEFAULT_RESOURCE_ID = "seed-tts-2.0"
RECOVERY_DIR = Path(__file__).resolve().parents[1] / "recovery" / "doubao_tts_2_0"


DOUBAO_VOICES_2_0 = [
    ("通用场景", "VV 2.0", "女", "多语种、方言支持", "zh_female_vv_uranus_bigtts"),
    ("通用场景", "小何 2.0", "女", "清新自然", "zh_female_xiaohe_uranus_bigtts"),
    ("通用场景", "云舟 2.0", "男", "成熟稳重", "zh_male_yunzhou_uranus_bigtts"),
    ("通用场景", "小天 2.0", "男", "年轻活力", "zh_male_xiaotian_uranus_bigtts"),
    ("通用场景", "刘飞 2.0", "男", "磁性低沉", "zh_male_liufei_uranus_bigtts"),
    ("通用场景", "魅力苏菲 2.0", "男", "温柔魅力", "zh_male_sunfei_uranus_bigtts"),
    ("通用场景", "清新女声 2.0", "女", "清新自然", "zh_female_qingxinnvsheng_uranus_bigtts"),
    ("通用场景", "甜美小源 2.0", "女", "甜美可爱", "zh_female_tianmeixiaoyuan_uranus_bigtts"),
    ("通用场景", "甜美桃子 2.0", "女", "甜美活泼", "zh_female_tianmeitaozi_uranus_bigtts"),
    ("通用场景", "爽快思思 2.0", "女", "爽朗大方", "zh_female_shuangkuaisisi_uranus_bigtts"),
    ("通用场景", "邻家女孩 2.0", "女", "亲切温和", "zh_female_linjianvhai_uranus_bigtts"),
    ("通用场景", "少年梓辛 2.0", "男", "少年感", "zh_male_shaonianzixin_uranus_bigtts"),
    ("通用场景", "魅力女友 2.0", "女", "温柔亲切", "zh_female_meilinvyou_uranus_bigtts"),
    ("角色扮演", "知性姐姐 2.0", "女", "知性优雅", "zh_female_zhixingjiejie_uranus_bigtts"),
    ("角色扮演", "撒娇学妹 2.0", "女", "可爱撒娇", "zh_female_sajiaoxuemei_uranus_bigtts"),
    ("角色扮演", "可爱女生", "女", "可爱活泼", "zh_female_keainvsheng_uranus_bigtts"),
    ("角色扮演", "调皮公主", "女", "调皮可爱", "zh_female_tiaopigongzhu_uranus_bigtts"),
    ("角色扮演", "爽朗少年", "男", "少年感", "zh_male_shuanglangshaonian_uranus_bigtts"),
    ("广告营销", "广告解说 2.0", "男", "广告宣传", "zh_male_guanggaojieshuo_uranus_bigtts"),
    ("广告营销", "促销女声 2.0", "女", "电商促销", "zh_female_cuxiaonvsheng_uranus_bigtts"),
]

LEGACY_VOICES = [
    ("旧版兼容", "通用女声", "女", "旧版 BV 音色", "BV001_streaming"),
    ("旧版兼容", "通用男声", "男", "旧版 BV 音色", "BV002_streaming"),
    ("旧版兼容", "知性女声", "女", "旧版 BV 音色", "BV005_streaming"),
    ("旧版兼容", "灿灿 2.0", "女", "旧版 BV2 音色", "BV700_V2_streaming"),
]


def voice_label(item):
    group, name, gender, desc, voice_type = item
    return f"{group}｜{name}｜{gender}｜{desc}｜{voice_type}"


VOICE_OPTIONS = [voice_label(item) for item in DOUBAO_VOICES_2_0] + [voice_label(item) for item in LEGACY_VOICES] + [
    "自定义 voice_type｜在下方填写"
]


class TikpanDoubaoTTS20Node:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "💵_福利_💵": (
                    ["🔥 豆包语音合成 2.0 | Tikpan 中转站 | 官方音色下拉 | 按字符计费"],
                ),
                "获取密钥请访问": (
                    ["👉 https://tikpan.com (官方授权 Key 获取入口)"],
                ),
                "API_密钥": ("STRING", {"default": "sk-"}),
                "合成文本": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "欢迎使用 Tikpan 豆包语音合成 2.0。现在音色已经整理成下拉框，普通用户不用再手动查 voice_type。",
                    },
                ),
                "模型": (["doubao-tts-2.0"], {"default": "doubao-tts-2.0"}),
                "音色": (VOICE_OPTIONS, {"default": voice_label(DOUBAO_VOICES_2_0[0])}),
                "语速": ("FLOAT", {"default": 1.0, "min": 0.5, "max": 2.0, "step": 0.05}),
                "音量": ("FLOAT", {"default": 1.0, "min": 0.1, "max": 3.0, "step": 0.05}),
                "音调": ("FLOAT", {"default": 1.0, "min": 0.5, "max": 2.0, "step": 0.05}),
                "情感": (
                    ["默认不传", "happy", "sad", "angry", "fearful", "surprised", "neutral"],
                    {"default": "默认不传"},
                ),
                "音频格式": (["mp3", "wav", "pcm"], {"default": "mp3"}),
                "采样率": (["24000", "16000", "22050", "32000", "44100", "48000"], {"default": "24000"}),
                "POST重试策略": (["幂等键轻重试", "保守不重试POST"], {"default": "幂等键轻重试"}),
                "校验HTTPS证书": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "自定义voice_type": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "当“音色”选择自定义时使用；也可填写复刻音色或官方新上线音色的 voice_type。",
                    },
                ),
                "火山AppID_可选": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "Tikpan 中转通常只需要 Tikpan API Key；如你的中转要求透传火山 AppID，可填写。",
                    },
                ),
                "资源ID": (
                    ["seed-tts-2.0", "seed-tts-1.0", "volc.service_type.10029", "seed-icl-2.0", "seed-icl-1.0"],
                    {"default": "seed-tts-2.0"},
                ),
                "接口路径": (
                    "STRING",
                    {
                        "default": API_PATH,
                        "tooltip": "默认绑定 Tikpan 中转站的豆包 V3 单向 SSE 路径；一般不要改。",
                    },
                ),
                "用户ID": ("STRING", {"default": "tikpan_comfyui_user"}),
                "复用本地缓存": ("BOOLEAN", {"default": True}),
                "跳过错误": ("BOOLEAN", {"default": False}),
                "高级自定义_JSON": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "tooltip": "会深度合并到最终请求体，例如透传 context_language、emotion 等后续新增参数。",
                    },
                ),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING", "AUDIO")
    RETURN_NAMES = ("📁_音频路径", "🔗_音频链接", "🎙️_voice_type", "💰_计费字符数", "📋_状态日志", "🎧_音频流")
    OUTPUT_NODE = True
    FUNCTION = "generate_tts"
    CATEGORY = "👑 Tikpan 官方独家节点"

    DEFAULT_OPTIONAL_VALUES = {
        "自定义voice_type": "",
        "火山AppID_可选": "",
        "资源ID": DEFAULT_RESOURCE_ID,
        "接口路径": API_PATH,
        "用户ID": "tikpan_comfyui_user",
        "复用本地缓存": True,
        "跳过错误": False,
        "高级自定义_JSON": "",
    }

    def empty_audio(self):
        try:
            import torch

            return {"waveform": torch.zeros((1, 1, 1)), "sample_rate": 24000}
        except Exception:
            return {"waveform": None, "sample_rate": 24000}

    def make_return(self, path="", url="", voice_type="", usage="", log="", audio=None):
        return (path, url, voice_type, str(usage or ""), log, audio or self.empty_audio())

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

    def audio_from_path(self, audio_path, sample_rate=24000):
        if not audio_path or not os.path.exists(audio_path):
            return self.empty_audio()
        try:
            from comfy_extras.nodes_audio import load as load_audio_file

            waveform, rate = load_audio_file(audio_path)
            return {"waveform": waveform.unsqueeze(0), "sample_rate": rate}
        except Exception as e:
            print(f"[Tikpan-DoubaoTTS] WARNING 音频流解码失败，只返回文件路径: {e}", flush=True)
            return {"waveform": None, "sample_rate": sample_rate}

    def deep_merge(self, base, extra):
        if not isinstance(base, dict) or not isinstance(extra, dict):
            return extra
        merged = dict(base)
        for key, value in extra.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = self.deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged

    def parse_json_field(self, text, field_name):
        if not text or not str(text).strip():
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"{field_name} 不是合法 JSON: {e}")

    def safe_response_text(self, response, max_len=1200):
        try:
            return response.text[:max_len]
        except Exception:
            return f"<{len(response.content)} bytes>"

    def resolve_voice_type(self, selected, custom_voice_type=""):
        selected = str(selected or "").strip()
        custom_voice_type = str(custom_voice_type or "").strip()
        if selected.startswith("自定义"):
            if not custom_voice_type:
                raise ValueError("已选择自定义 voice_type，但没有填写“自定义voice_type”。")
            return custom_voice_type
        if "｜" in selected:
            return selected.split("｜")[-1].strip()
        return selected

    def build_payload(self, values, request_id):
        voice_type = self.resolve_voice_type(values.get("音色"), values.get("自定义voice_type"))
        audio_params = {
            "format": str(values.get("音频格式", "mp3")),
            "sample_rate": int(values.get("采样率", "24000")),
            "speech_rate": int(round((float(values.get("语速", 1.0)) - 1.0) * 100)),
            "loudness_rate": int(round((float(values.get("音量", 1.0)) - 1.0) * 100)),
            "pitch_rate": int(round((float(values.get("音调", 1.0)) - 1.0) * 100)),
        }
        req_params = {
            "text": str(values.get("合成文本", "")),
            "speaker": voice_type,
            "audio_params": audio_params,
            "request_id": request_id,
        }
        emotion = str(values.get("情感", "默认不传"))
        if emotion and emotion != "默认不传":
            req_params["emotion"] = emotion
        payload = {
            "user": {"uid": str(values.get("用户ID") or "tikpan_comfyui_user")},
            "req_params": req_params,
        }
        custom = self.parse_json_field(values.get("高级自定义_JSON"), "高级自定义_JSON")
        if custom:
            payload = self.deep_merge(payload, custom)
        return payload, voice_type

    def cache_key(self, payload, resource_id, api_path):
        raw = json.dumps({"payload": payload, "resource_id": resource_id, "api_path": api_path}, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def output_path(self, cache_key, audio_format):
        out_dir = folder_paths.get_output_directory()
        os.makedirs(out_dir, exist_ok=True)
        ext = "wav" if audio_format == "wav" else ("pcm" if audio_format == "pcm" else "mp3")
        return os.path.join(out_dir, f"Tikpan_Doubao_TTS_2_0_{cache_key[:16]}.{ext}")

    def save_recovery(self, cache_key, record):
        RECOVERY_DIR.mkdir(parents=True, exist_ok=True)
        path = RECOVERY_DIR / f"tikpan-doubao-tts-2-0-{cache_key[:32]}.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)

    def decode_audio_string(self, value):
        if not value:
            return b"", ""
        if isinstance(value, bytes):
            return value, ""
        text = str(value).strip()
        if text.startswith("http://") or text.startswith("https://"):
            return b"", text
        if all(ch in "0123456789abcdefABCDEF" for ch in text[:64]) and len(text) % 2 == 0:
            try:
                return bytes.fromhex(text), ""
            except Exception:
                pass
        try:
            return base64.b64decode(text), ""
        except Exception:
            return b"", ""

    def extract_audio_from_json(self, value):
        chunks = []
        audio_url = ""

        def scan(obj):
            nonlocal audio_url
            if isinstance(obj, dict):
                for key in ("audio", "data", "audio_base64", "audio_data"):
                    if isinstance(obj.get(key), str):
                        audio_bytes, url = self.decode_audio_string(obj[key])
                        if url:
                            audio_url = url
                        elif audio_bytes:
                            chunks.append(audio_bytes)
                for child in obj.values():
                    scan(child)
            elif isinstance(obj, list):
                for child in obj:
                    scan(child)

        scan(value)
        return b"".join(chunks), audio_url

    def extract_audio(self, response):
        content_type = response.headers.get("Content-Type", "")
        if "audio/" in content_type or content_type.startswith("application/octet-stream"):
            return response.content, ""
        text = response.text.strip()
        chunks = []
        audio_url = ""
        parsed_any = False
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("data:"):
                line = line[5:].strip()
            if line in ("[DONE]", "DONE"):
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            parsed_any = True
            audio_bytes, url = self.extract_audio_from_json(obj)
            if url:
                audio_url = url
            if audio_bytes:
                chunks.append(audio_bytes)
        if chunks or audio_url:
            return b"".join(chunks), audio_url
        if not parsed_any:
            try:
                obj = json.loads(text)
                return self.extract_audio_from_json(obj)
            except Exception:
                pass
        return b"", ""

    def download_audio_url(self, session, url, verify):
        response = session.get(url, timeout=120, verify=verify)
        response.raise_for_status()
        return response.content

    def generate_tts(self, **kwargs):
        values = dict(self.DEFAULT_OPTIONAL_VALUES)
        values.update(kwargs)
        text = str(values.get("合成文本", "")).strip()
        if not text:
            return self.make_return(log="ERROR 错误：合成文本不能为空。")
        if len(text) > 10000:
            return self.make_return(log="ERROR 错误：当前节点适合短文本同步合成；超长文本建议使用豆包异步长文本接口。")

        try:
            request_id = str(uuid.uuid4())
            payload, voice_type = self.build_payload(values, request_id)
            resource_id = str(values.get("资源ID") or DEFAULT_RESOURCE_ID)
            api_path = str(values.get("接口路径") or API_PATH)
            url = f"{API_HOST}{api_path if api_path.startswith('/') else '/' + api_path}"
            audio_format = str(values.get("音频格式") or "mp3")
            verify = bool(values.get("校验HTTPS证书", True))
            cache_key = self.cache_key(payload, resource_id, api_path)
            output_path = self.output_path(cache_key, audio_format)
            if values.get("复用本地缓存", True) and os.path.exists(output_path):
                log = f"CACHE 命中本地缓存 | voice_type={voice_type} | path={output_path}"
                return self.make_return(output_path, "", voice_type, len(text), log, self.audio_from_path(output_path, int(values.get("采样率", "24000"))))

            allow_post_retry = values.get("POST重试策略") == "幂等键轻重试"
            session = self.create_session(allow_post_retry=allow_post_retry)
            api_key = str(values.get("API_密钥") or "").strip()
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "X-Api-Access-Key": api_key,
                "X-Api-Resource-Id": resource_id,
                "X-Api-Request-Id": request_id,
                "X-Api-Connect-Id": request_id,
                "Idempotency-Key": f"tikpan-doubao-tts-2-0-{cache_key[:32]}",
                "User-Agent": "Tikpan-ComfyUI-Doubao-TTS-2.0/1.0",
            }
            app_id = str(values.get("火山AppID_可选") or "").strip()
            if app_id:
                headers["X-Api-App-Id"] = app_id

            self.save_recovery(
                cache_key,
                {
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "url": url,
                    "headers_preview": {k: ("***" if "Key" in k or k == "Authorization" else v) for k, v in headers.items()},
                    "payload": payload,
                },
            )
            print(f"[Tikpan-DoubaoTTS] START {url} | resource={resource_id} | voice={voice_type} | chars={len(text)}", flush=True)
            response = session.post(url, headers=headers, json=payload, timeout=240, verify=verify)
            if response.status_code >= 400:
                raise RuntimeError(f"豆包语音请求失败 | HTTP {response.status_code} | {self.safe_response_text(response)}")

            audio_bytes, audio_url = self.extract_audio(response)
            if audio_url and not audio_bytes:
                audio_bytes = self.download_audio_url(session, audio_url, verify=verify)
            if not audio_bytes:
                raise RuntimeError(f"豆包语音成功响应中未找到音频数据: {self.safe_response_text(response)}")

            with open(output_path, "wb") as f:
                f.write(audio_bytes)
            log = (
                f"OK 豆包语音合成 2.0 成功 | voice_type={voice_type} | resource={resource_id} | "
                f"chars={len(text)} | bytes={len(audio_bytes)} | path={output_path}"
            )
            print(f"[Tikpan-DoubaoTTS] {log}", flush=True)
            return self.make_return(output_path, audio_url, voice_type, len(text), log, self.audio_from_path(output_path, int(values.get("采样率", "24000"))))
        except Exception as e:
            tb = traceback.format_exc()
            log = f"ERROR 豆包语音合成失败：{e}\n{tb}"
            print(f"[Tikpan-DoubaoTTS] {log}", flush=True)
            if values.get("跳过错误"):
                return self.make_return(log=log)
            raise RuntimeError(log)


NODE_CLASS_MAPPINGS = {
    "TikpanDoubaoTTS20Node": TikpanDoubaoTTS20Node,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TikpanDoubaoTTS20Node": "🎙️ Tikpan: 豆包语音合成 2.0",
}
