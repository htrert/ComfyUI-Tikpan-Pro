import base64
import hashlib
import json
import os
import time
import traceback
import wave
from pathlib import Path

import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import comfy.utils
import folder_paths


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_HOST = "https://tikpan.com"
API_BASE_URL = API_HOST
MODEL_NAME = "gemini-3.1-flash-tts-preview"
RECOVERY_DIR = Path(__file__).resolve().parents[1] / "recovery" / "gemini_3_1_flash_tts_preview"


class TikpanGemini31FlashTTSNode:
    @classmethod
    def INPUT_TYPES(cls):
        voices = [
            "Kore",
            "Puck",
            "Charon",
            "Zephyr",
            "Fenrir",
            "Aoede",
            "Leda",
            "Orus",
            "Callirrhoe",
            "Autonoe",
            "Enceladus",
            "Iapetus",
            "Umbriel",
            "Algieba",
            "Despina",
            "Erinome",
            "Algenib",
            "Rasalgethi",
            "Laomedeia",
            "Achernar",
            "Alnilam",
            "Schedar",
            "Gacrux",
            "Pulcherrima",
            "Achird",
            "Zubenelgenubi",
            "Vindemiatrix",
            "Sadachbia",
            "Sadaltager",
            "Sulafat",
        ]
        return {
            "required": {
                "💵_福利_💵": (
                    ["🔥 gemini-3.1-flash-tts-preview 文字转语音 | 按输入/输出 token 计费"],
                ),
                "获取密钥请访问": (
                    ["👉 https://tikpan.com (官方授权 Key 获取入口)"],
                ),
                "API_密钥": ("STRING", {"default": "sk-"}),
                "合成文本": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "Say warmly: Welcome to Tikpan Gemini 3.1 Flash TTS preview. This voice is generated for a commercial-ready workflow.",
                    },
                ),
                "模型": ([MODEL_NAME], {"default": MODEL_NAME}),
                "调用方式": (
                    ["geminitts 原生", "gemini 原生", "openai 兼容"],
                    {"default": "geminitts 原生"},
                ),
                "音色": (voices, {"default": "Kore"}),
                "语气指令": (
                    "STRING",
                    {
                        "default": "自然、清晰、商业旁白风格",
                        "tooltip": "会作为自然语言指令合并到文本前面，例如：欢快地说、低声说、像纪录片旁白一样说。",
                    },
                ),
                "语言代码": (["自动", "zh-CN", "en-US", "ja-JP", "ko-KR", "yue-HK", "fr-FR", "de-DE", "es-ES"], {"default": "自动"}),
                "采样率": (["24000"], {"default": "24000"}),
                "POST重试策略": (["幂等键轻重试", "保守不重试POST"], {"default": "幂等键轻重试"}),
                "校验HTTPS证书": ("BOOLEAN", {"default": True}),
            },
            "optional": {
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
        "复用本地缓存": True,
        "跳过错误": False,
        "高级自定义_JSON": "",
    }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING", "AUDIO")
    RETURN_NAMES = (
        "📁_音频路径",
        "🔗_音频链接",
        "💰_输入输出用量",
        "🧾_接口路径",
        "📋_状态日志",
        "🎧_音频流",
    )
    OUTPUT_NODE = True
    FUNCTION = "generate_tts"
    CATEGORY = "👑 Tikpan 官方独家节点"

    def empty_audio(self):
        try:
            import torch

            return {"waveform": torch.zeros((1, 1, 1), dtype=torch.float32), "sample_rate": 24000}
        except Exception:
            return {"waveform": None, "sample_rate": 24000}

    def make_return(self, path="", url="", usage="", api_path="", log="", audio=None):
        return (path, url, str(usage or ""), api_path, log, audio or self.empty_audio())

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
            print(f"[Tikpan-GeminiTTS] WARNING 音频流解码失败，只返回文件路径: {e}", flush=True)
            return self.empty_audio()

    def safe_json_text(self, value, max_len=1600):
        try:
            text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        except Exception:
            text = str(value)
        return text[:max_len] + ("...(truncated)" if len(text) > max_len else "")

    def safe_response_text(self, response, max_len=1600):
        try:
            return response.text[:max_len].strip()
        except Exception:
            return "无法解析上游响应"

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

    def payload_hash(self, payload, call_mode):
        raw = json.dumps({"model": MODEL_NAME, "call_mode": call_mode, "payload": payload}, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def cache_path(self, cache_key):
        return RECOVERY_DIR / f"tikpan-gemini-3-1-flash-tts-preview-{cache_key[:32]}.wav"

    def read_cache(self, cache_key):
        path = self.cache_path(cache_key)
        if path.exists() and path.stat().st_size > 44:
            return str(path)
        return ""

    def save_recovery_record(self, cache_key, status, **fields):
        RECOVERY_DIR.mkdir(parents=True, exist_ok=True)
        record = {
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "model": MODEL_NAME,
            "cache_key": cache_key,
            "status": status,
            **fields,
        }
        latest_path = RECOVERY_DIR / f"tikpan-gemini-3-1-flash-tts-preview-{cache_key[:32]}.json"
        events_path = RECOVERY_DIR / "events.jsonl"
        latest_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        with events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return str(latest_path)

    def pcm_to_wav_bytes(self, pcm_bytes, sample_rate=24000, channels=1, sample_width=2):
        if not pcm_bytes or len(pcm_bytes) <= 16:
            raise RuntimeError("上游返回的音频内容为空或过小，疑似错误页/无效文件。")
        import io

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(int(channels))
            wf.setsampwidth(int(sample_width))
            wf.setframerate(int(sample_rate))
            wf.writeframes(pcm_bytes)
        return buf.getvalue()

    def maybe_wrap_audio_bytes(self, audio_bytes, mime_type, sample_rate):
        mime = str(mime_type or "").lower()
        if audio_bytes[:4] == b"RIFF" or "wav" in mime or "wave" in mime:
            return audio_bytes
        if "pcm" in mime or "l16" in mime or not mime:
            return self.pcm_to_wav_bytes(audio_bytes, sample_rate=sample_rate)
        if "mpeg" in mime or "mp3" in mime or "flac" in mime or "ogg" in mime:
            return audio_bytes
        return self.pcm_to_wav_bytes(audio_bytes, sample_rate=sample_rate)

    def write_audio_bytes(self, audio_bytes, cache_key):
        if not audio_bytes or len(audio_bytes) <= 44:
            raise RuntimeError("生成音频为空或过小，无法保存。")
        RECOVERY_DIR.mkdir(parents=True, exist_ok=True)
        recovery_path = self.cache_path(cache_key)
        recovery_path.write_bytes(audio_bytes)

        out_dir = folder_paths.get_output_directory()
        output_path = os.path.join(out_dir, f"Tikpan_Gemini_3_1_Flash_TTS_{cache_key[:16]}.wav")
        with open(output_path, "wb") as f:
            f.write(audio_bytes)
        return output_path

    def build_prompt_text(self, text, style):
        style = str(style or "").strip()
        text = str(text or "").strip()
        if not style:
            return text
        return f"{style}: {text}"

    def build_gemini_payload(self, text, voice, language_code, style, custom_json):
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": self.build_prompt_text(text, style)}],
                }
            ],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": voice,
                        }
                    }
                },
            },
        }
        language_code = str(language_code or "").strip()
        if language_code == "自动":
            language_code = ""
        if language_code:
            payload["generationConfig"]["speechConfig"]["languageCode"] = language_code
        if custom_json:
            payload = self.deep_merge(payload, custom_json)
        return payload

    def build_openai_payload(self, text, voice, language_code, style, custom_json):
        payload = {
            "model": MODEL_NAME,
            "messages": [
                {
                    "role": "user",
                    "content": self.build_prompt_text(text, style),
                }
            ],
            "modalities": ["audio"],
            "audio": {
                "voice": voice,
                "format": "wav",
            },
        }
        language_code = str(language_code or "").strip()
        if language_code == "自动":
            language_code = ""
        if language_code:
            payload["audio"]["language_code"] = language_code
        if custom_json:
            payload = self.deep_merge(payload, custom_json)
        return payload

    def extract_inline_audio(self, res_json):
        candidates = []

        def add(value, mime_type, source):
            if value:
                candidates.append((value, mime_type or "", source))

        def scan(obj, path="root"):
            if isinstance(obj, dict):
                inline = obj.get("inlineData") or obj.get("inline_data")
                if isinstance(inline, dict):
                    add(inline.get("data"), inline.get("mimeType") or inline.get("mime_type"), f"{path}.inlineData")

                for key in ["audio", "audio_data", "audioData", "data", "b64_json", "base64"]:
                    value = obj.get(key)
                    if isinstance(value, str) and len(value) > 80:
                        add(value, obj.get("mimeType") or obj.get("mime_type") or "", f"{path}.{key}")
                    elif isinstance(value, dict):
                        scan(value, f"{path}.{key}")

                for key, value in obj.items():
                    if key not in {"inlineData", "inline_data", "audio", "audio_data", "audioData", "data", "b64_json", "base64"}:
                        scan(value, f"{path}.{key}")
            elif isinstance(obj, list):
                for idx, item in enumerate(obj):
                    scan(item, f"{path}[{idx}]")

        scan(res_json)
        for raw, mime_type, source in candidates:
            cleaned = str(raw).strip()
            if cleaned.startswith("data:"):
                header, cleaned = cleaned.split(",", 1)
                if not mime_type:
                    mime_type = header.split(";", 1)[0].replace("data:", "")
            try:
                audio_bytes = base64.b64decode(cleaned)
                if len(audio_bytes) > 16:
                    return audio_bytes, mime_type, source
            except Exception:
                continue
        return b"", "", "not_found"

    def extract_usage(self, res_json):
        usage = res_json.get("usageMetadata") or res_json.get("usage") or res_json.get("usage_metadata") or {}
        if not isinstance(usage, dict):
            return ""
        prompt = usage.get("promptTokenCount") or usage.get("prompt_tokens") or usage.get("input_tokens") or ""
        candidates = usage.get("candidatesTokenCount") or usage.get("completion_tokens") or usage.get("output_tokens") or ""
        total = usage.get("totalTokenCount") or usage.get("total_tokens") or ""
        parts = []
        if prompt != "":
            parts.append(f"input={prompt}")
        if candidates != "":
            parts.append(f"output={candidates}")
        if total != "":
            parts.append(f"total={total}")
        return " | ".join(parts) if parts else self.safe_json_text(usage, 500)

    def generate_tts(self, **kwargs):
        start_time = time.time()
        values = dict(self.DEFAULT_OPTIONAL_VALUES)
        values.update(kwargs)

        api_key = str(values.get("API_密钥") or "").strip()
        text = str(values.get("合成文本") or "").strip()
        call_mode = str(values.get("调用方式") or "geminitts 原生")
        voice = str(values.get("音色") or "Kore").strip()
        language_code = str(values.get("语言代码") or "").strip()
        style = str(values.get("语气指令") or "").strip()
        sample_rate = int(values.get("采样率") or 24000)
        base_url = API_HOST
        post_retry = str(values.get("POST重试策略") or "幂等键轻重试") == "幂等键轻重试"
        verify_tls = bool(values.get("校验HTTPS证书", True))
        use_cache = bool(values.get("复用本地缓存", True))
        skip_error = bool(values.get("跳过错误", False))

        try:
            if not api_key or api_key == "sk-":
                return self.make_return(log="ERROR 错误：API 密钥为空，请填写有效 Tikpan API Key。")
            if not text:
                return self.make_return(log="ERROR 错误：合成文本不能为空。")
            if len(text) > 20000:
                return self.make_return(log="ERROR 错误：文本过长，建议拆分后分段生成，避免长音频漂移或请求超时。")

            custom_json = self.parse_json_field(values.get("高级自定义_JSON"), "高级自定义_JSON")
            if custom_json is not None and not isinstance(custom_json, dict):
                raise ValueError("高级自定义_JSON 顶层必须是对象。")

            if "openai" in call_mode.lower():
                api_path = "/v1/chat/completions"
                url = f"{base_url}{api_path}"
                payload = self.build_openai_payload(text, voice, language_code, style, custom_json)
            else:
                api_path = f"/v1beta/models/{MODEL_NAME}:generateContent"
                url = f"{base_url}{api_path}"
                payload = self.build_gemini_payload(text, voice, language_code, style, custom_json)

            cache_key = self.payload_hash(payload, call_mode)
            pbar = comfy.utils.ProgressBar(100)
            pbar.update(5)

            if use_cache:
                cached_path = self.read_cache(cache_key)
                if cached_path:
                    audio = self.audio_from_path(cached_path)
                    log = f"OK 命中本地缓存，未重新请求上游，避免重复扣费 | path={cached_path}"
                    print(f"[Tikpan-GeminiTTS] {log}", flush=True)
                    return self.make_return(cached_path, "", "", api_path, log, audio)

            print(
                f"[Tikpan-GeminiTTS] START 启动 {MODEL_NAME} | 调用方式={call_mode} | voice={voice} | 字符数={len(text)}",
                flush=True,
            )
            print(f"[Tikpan-GeminiTTS] PAYLOAD 请求摘要: {self.safe_json_text({k: v for k, v in payload.items() if k != 'contents'}, 1000)}", flush=True)
            recovery_path = self.save_recovery_record(
                cache_key,
                "pending",
                api_path=api_path,
                text_chars=len(text),
                voice=voice,
                language_code=language_code,
                payload_preview=self.safe_json_text(payload, 2000),
            )

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "Tikpan-ComfyUI-Gemini-3.1-Flash-TTS/1.1",
                "Idempotency-Key": f"tikpan-gemini-3-1-flash-tts-preview-{cache_key[:32]}",
            }
            session = self.create_session(allow_post_retry=post_retry)

            try:
                response = session.post(url, json=payload, headers=headers, timeout=(15, 300), verify=verify_tls)
            except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
                self.save_recovery_record(cache_key, "post_disconnected", api_path=api_path, error=str(e), recovery_path=recovery_path)
                raise RuntimeError(
                    "网络在提交后断开：上游可能已经收到并扣费。建议先检查 recovery/gemini_3_1_flash_tts_preview 中的记录，"
                    f"不要立刻改参数重复提交。cache_key={cache_key[:32]} | recovery={recovery_path}"
                )

            pbar.update(50)
            if response.status_code != 200:
                raise RuntimeError(f"Gemini TTS 请求失败 | HTTP {response.status_code} | {self.safe_response_text(response)}")

            try:
                res_json = response.json()
            except Exception:
                raise RuntimeError(f"Gemini TTS 接口返回非 JSON: {self.safe_response_text(response)}")

            if isinstance(res_json, dict) and res_json.get("error"):
                raise RuntimeError(f"上游返回错误: {self.safe_json_text(res_json.get('error'))}")

            raw_audio, mime_type, source = self.extract_inline_audio(res_json)
            if not raw_audio:
                raise RuntimeError(f"未提取到音频数据 | 响应预览: {self.safe_json_text(res_json, 2200)}")

            wav_bytes = self.maybe_wrap_audio_bytes(raw_audio, mime_type, sample_rate)
            audio_path = self.write_audio_bytes(wav_bytes, cache_key)
            audio = self.audio_from_path(audio_path)
            usage = self.extract_usage(res_json)
            elapsed = round(time.time() - start_time, 2)
            log = (
                f"OK {MODEL_NAME} 语音生成成功 | voice={voice} | source={source} | mime={mime_type or 'pcm'} | "
                f"用量={usage or '上游未返回'} | 耗时={elapsed}s | api={API_HOST}{api_path} | "
                f"post_retry={post_retry} | 音频={audio_path}"
            )
            self.save_recovery_record(
                cache_key,
                "success",
                api_path=api_path,
                audio_path=audio_path,
                usage=usage,
                source=source,
                mime_type=mime_type,
                response_preview=self.safe_json_text(res_json, 2200),
            )
            pbar.update(100)
            print(f"[Tikpan-GeminiTTS] {log}", flush=True)
            return self.make_return(audio_path, "", usage, api_path, log, audio)

        except Exception as e:
            tb = traceback.format_exc()
            err_msg = f"ERROR {MODEL_NAME} 节点运行失败: {e}\n{tb}"
            print(err_msg, flush=True)
            if not skip_error:
                raise
            return self.make_return(log=err_msg)


NODE_CLASS_MAPPINGS = {
    "TikpanGemini31FlashTTSNode": TikpanGemini31FlashTTSNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TikpanGemini31FlashTTSNode": "🎙️ Tikpan: Gemini 3.1 Flash TTS Preview",
}
