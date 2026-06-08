from .tikpan_categories import CATEGORY_TEXT_MULTIMODAL
import base64
import hashlib
import json
import mimetypes
import os
import time
import traceback
from io import BytesIO
from pathlib import Path

import numpy as np
import requests
from PIL import Image
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import comfy.model_management
import comfy.utils

from .tikpan_node_options import API_HOST_OPTIONS, normalize_api_host, pick


MODEL_NAME = "gemini-3.5-flash"
MODEL_OPTIONS = [MODEL_NAME]
RECOVERY_DIR = Path(__file__).resolve().parents[1] / "recovery" / "gemini_3_5_flash"

MAX_IMAGE_PARTS = 6
MAX_INLINE_IMAGE_BYTES = 4 * 1024 * 1024
MAX_INLINE_FILE_BYTES = 18 * 1024 * 1024

ENDPOINT_OPTIONS = [
    "Gemini 原生｜/v1beta/models/{model}:generateContent",
    "OpenAI 兼容｜/v1/chat/completions",
]

TASK_OPTIONS = [
    "通用问答",
    "图片理解分析",
    "视频/音频理解",
    "长文档/PDF总结",
    "代码与架构审查",
    "复杂任务规划",
    "提示词优化",
    "结构化JSON抽取",
    "自定义",
]

OUTPUT_FORMAT_OPTIONS = [
    "中文报告",
    "Markdown结构化",
    "JSON结构化",
    "提示词优化",
]

THINKING_OPTIONS = [
    "自动｜auto",
    "关闭｜0",
    "轻量｜1024",
    "中等｜4096",
    "深度｜8192",
]

RETRY_OPTIONS = ["幂等键轻重试", "保守不重试POST"]
URL_ERROR_OPTIONS = ["严格报错", "跳过坏链接并写日志"]


def option_value(value, default=""):
    text = str(value if value is not None else default).strip()
    if not text:
        return default
    for sep in ("｜", "|"):
        if sep in text:
            return text.split(sep)[-1].strip() or default
    return text


class TikpanGemini35FlashNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "💰_福利_💰": (
                    ["🔥 0.6元≈1美金余额 | 全网底价 👉 https://tikpan.com"],
                ),
                "获取密钥请访问": (
                    ["👉 https://tikpan.com (官方授权 Key 获取地址)"],
                ),
                "API_密钥": ("STRING", {"default": os.environ.get("TIKPAN_API_KEY", "sk-"), "tooltip": "Tikpan 平台的 API 密钥，以 sk- 开头，从 https://tikpan.com 获取"}),
                "模型": (MODEL_OPTIONS, {"default": MODEL_NAME, "tooltip": "选择对应版本的 Gemini 模型"}),
                "接口模式": (ENDPOINT_OPTIONS, {"default": ENDPOINT_OPTIONS[0], "tooltip": "走 Gemini 原生接口（更稳）或 OpenAI 兼容接口（更通用）"}),
                "任务类型": (TASK_OPTIONS, {"default": "通用问答", "tooltip": "预设场景，会自动调整 system prompt 模板"}),
                "用户问题": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "请根据输入内容，给出清晰、准确、可执行的中文回答。",
                        "tooltip": "本次对话的提问内容；可结合上方的图片/视频/URL 输入",
                    },
                ),
                "系统指令": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": (
                            "你是 Tikpan 的商业级多模态 AI 助手。回答要准确、结构化、可执行；"
                            "不确定的信息要说明不确定，不要编造。"
                        ),
                        "tooltip": "system prompt：约束 AI 的角色、口吻和回答风格",
                    },
                ),
                "输出格式": (OUTPUT_FORMAT_OPTIONS, {"default": "Markdown结构化", "tooltip": "回答的呈现形式：自由文本 / Markdown / JSON 等"}),
                "思考预算": (THINKING_OPTIONS, {"default": "自动｜auto", "tooltip": "思考链长度：auto 自适应；预算越大越擅长复杂推理但更慢更贵"}),
                "最大输出Token": ("INT", {"default": 8192, "min": 256, "max": 65536, "step": 256, "tooltip": "回答最长字数上限（约 1 token≈0.7 个汉字）"}),
                "创意温度": ("FLOAT", {"default": 0.4, "min": 0.0, "max": 2.0, "step": 0.05, "tooltip": "0=最稳，1=均衡，>1=更发散；写作可调高，事实问答调低"}),
                "Top_P": ("FLOAT", {"default": 0.95, "min": 0.0, "max": 1.0, "step": 0.01, "tooltip": "核采样概率，一般保持默认 0.95"}),
                "启用搜索工具": ("BOOLEAN", {"default": False, "tooltip": "开启后允许模型联网检索最新信息（部分模型支持）"}),
                "启用代码执行": ("BOOLEAN", {"default": False, "tooltip": "开启后允许模型在沙箱里跑 Python 验证答案"}),
                "启用URL上下文": ("BOOLEAN", {"default": False, "tooltip": "开启后模型会读取你提供的网页 URL 内容"}),
                "POST重试策略": (RETRY_OPTIONS, {"default": "幂等键轻重试", "tooltip": "网络异常时的重试方式；带幂等键更安全"}),
                "跳过错误": ("BOOLEAN", {"default": False, "tooltip": "开启后异常时返回空，不打断后续工作流"}),
                "校验HTTPS证书": ("BOOLEAN", {"default": True, "tooltip": "默认开启；遇到本地证书问题再关闭（不推荐关闭）"}),
            },
            "optional": {
                "中转站地址": (API_HOST_OPTIONS, {"default": API_HOST_OPTIONS[0], "tooltip": "Tikpan 中转站地址，一般保持默认即可"}),
                "图片1": ("IMAGE", {"tooltip": "可选输入图 1，用于图文混合提问"}),
                "图片2": ("IMAGE", {"tooltip": "可选输入图 2"}),
                "图片3": ("IMAGE", {"tooltip": "可选输入图 3"}),
                "图片4": ("IMAGE", {"tooltip": "可选输入图 4"}),
                "图片5": ("IMAGE", {"tooltip": "可选输入图 5"}),
                "图片6": ("IMAGE", {"tooltip": "可选输入图 6"}),
                "图片URL列表": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "tooltip": "每行一个公网图片 URL。Gemini 原生会作为 file_data，OpenAI 兼容会作为 image_url。",
                    },
                ),
                "视频URL列表": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "tooltip": "每行一个公网视频 URL，用于视频理解、分镜分析、广告素材分析等。",
                    },
                ),
                "音频URL列表": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "tooltip": "每行一个公网音频 URL，用于口播、音乐、音效、会议录音等理解任务。",
                    },
                ),
                "文件URL列表": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "tooltip": "每行一个公网文件 URL，适合 PDF/TXT/CSV/JSON 等长文档理解。",
                    },
                ),
                "本地文件路径": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "tooltip": "每行一个本地文件路径；小文件会 base64 内联上传，大文件建议先上传 OSS/CDN 后填 URL。",
                    },
                ),
                "URL错误处理": (URL_ERROR_OPTIONS, {"default": "严格报错", "tooltip": "URL 拉取失败时的策略：严格报错=立即中断；其它=跳过失败项继续"}),
                "高级自定义JSON": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "tooltip": "会深度合并到最终请求 payload，用于 Tikpan/上游新增参数。",
                    },
                ),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("回答文本", "优化提示词", "结构化JSON", "用量", "状态日志")
    OUTPUT_NODE = True
    FUNCTION = "run"
    CATEGORY = CATEGORY_TEXT_MULTIMODAL
    DESCRIPTION = "📝 Gemini 3.5 Flash 多模态推理：支持图/视频/音频/PDF 输入，思考预算可调，可启用联网搜索和代码执行。适合复杂分析、报告生成、知识问答。"

    def make_return(self, answer="", prompt="", structured="", usage="", log=""):
        return (str(answer or ""), str(prompt or ""), str(structured or ""), str(usage or ""), str(log or ""))

    def create_session(self, allow_post_retry=False):
        session = requests.Session()
        session.trust_env = False
        allowed_methods = ["GET", "HEAD", "OPTIONS"]
        if allow_post_retry:
            allowed_methods.append("POST")
        retry = Retry(
            total=2,
            connect=2,
            read=0,
            status=1,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=frozenset(allowed_methods),
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def parse_lines(self, text):
        items = []
        for line in str(text or "").replace(",", "\n").splitlines():
            item = line.strip().strip('"').strip("'")
            if item:
                items.append(item)
        return items

    def parse_url_lines(self, text, skip_invalid=False, field_name="URL列表"):
        urls = []
        for item in self.parse_lines(text):
            if not item.startswith(("http://", "https://")):
                if skip_invalid:
                    self._last_warnings.append(f"{field_name} 已跳过无效链接: {item[:120]}")
                    continue
                raise ValueError(f"{field_name} 包含非法 URL: {item[:120]}")
            urls.append(item)
        return urls

    def guess_mime_type(self, path_or_url, fallback="application/octet-stream"):
        mime_type, _ = mimetypes.guess_type(str(path_or_url or ""))
        return mime_type or fallback

    def image_tensor_to_jpeg(self, image_tensor, target_px=1280, quality=88):
        if image_tensor is None:
            return b""
        arr = 255.0 * image_tensor[0].detach().cpu().numpy()
        img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGB")
        img.thumbnail((target_px, target_px))
        while quality >= 55:
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=int(quality), optimize=True)
            data = buf.getvalue()
            if len(data) <= MAX_INLINE_IMAGE_BYTES:
                return data
            quality -= 8
        raise ValueError("图片压缩后仍超过 4MB，请降低分辨率后再试")

    def image_part_native(self, image_tensor):
        data = self.image_tensor_to_jpeg(image_tensor)
        return {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(data).decode("utf-8")}}

    def image_part_openai(self, image_tensor):
        data = self.image_tensor_to_jpeg(image_tensor)
        data_url = "data:image/jpeg;base64," + base64.b64encode(data).decode("utf-8")
        return {"type": "image_url", "image_url": {"url": data_url}}

    def local_file_part_native(self, path):
        if not os.path.exists(path):
            raise ValueError(f"本地文件不存在: {path}")
        size = os.path.getsize(path)
        if size <= 0:
            raise ValueError(f"本地文件为空: {path}")
        if size > MAX_INLINE_FILE_BYTES:
            raise ValueError(f"本地文件超过 {MAX_INLINE_FILE_BYTES // 1024 // 1024}MB，请上传 OSS/CDN 后填写文件URL: {path}")
        with open(path, "rb") as f:
            data = f.read()
        return {
            "inline_data": {
                "mime_type": self.guess_mime_type(path),
                "data": base64.b64encode(data).decode("utf-8"),
            }
        }

    def build_instruction(self, task, question, output_format):
        task_hint = {
            "通用问答": "回答用户问题，优先给出结论、依据和可执行建议。",
            "图片理解分析": "分析图片主体、场景、文字、风格、潜在问题和可复用提示词。",
            "视频/音频理解": "分析音视频内容、时间线、镜头/声音结构、情绪节奏和可执行建议。",
            "长文档/PDF总结": "总结文档结构、关键事实、风险点、行动项和可引用要点。",
            "代码与架构审查": "从正确性、安全性、可维护性、性能和测试缺口审查代码或架构。",
            "复杂任务规划": "拆解目标、依赖、步骤、风险、验收标准和下一步行动。",
            "提示词优化": "把用户需求改写成可直接用于图像/视频/文本模型的高质量提示词。",
            "结构化JSON抽取": "从输入中抽取稳定 JSON，字段清晰，缺失值用 null，不要输出解释文字。",
            "自定义": "严格按用户问题完成任务。",
        }.get(task, "严格按用户问题完成任务。")
        format_hint = {
            "中文报告": "用中文自然段回答，重点清楚，不空泛。",
            "Markdown结构化": "用 Markdown 标题和列表输出，结构清晰，便于复制到文档。",
            "JSON结构化": "只输出合法 JSON，不要 Markdown 代码块，不要额外解释。",
            "提示词优化": "优先输出可直接复用的优化提示词，并补充参数建议、负面约束和注意事项。",
        }.get(output_format, "用中文结构化输出。")
        return f"任务类型：{task}\n任务要求：{task_hint}\n输出要求：{format_hint}\n\n用户问题：\n{question}"

    def collect_media_native(self, values, skip_invalid):
        parts = []
        stats = {"images": 0, "image_urls": 0, "video_urls": 0, "audio_urls": 0, "file_urls": 0, "local_files": 0}
        for index in range(1, MAX_IMAGE_PARTS + 1):
            tensor = pick(values, f"图片{index}", f"image_{index}", default=None)
            if tensor is not None:
                parts.append({"text": f"[图片{index}]"})
                parts.append(self.image_part_native(tensor))
                stats["images"] += 1

        for url in self.parse_url_lines(values.get("图片URL列表"), skip_invalid, "图片URL列表"):
            parts.append({"file_data": {"file_uri": url, "mime_type": self.guess_mime_type(url, "image/jpeg")}})
            stats["image_urls"] += 1
        for url in self.parse_url_lines(values.get("视频URL列表"), skip_invalid, "视频URL列表"):
            parts.append({"file_data": {"file_uri": url, "mime_type": self.guess_mime_type(url, "video/mp4")}})
            stats["video_urls"] += 1
        for url in self.parse_url_lines(values.get("音频URL列表"), skip_invalid, "音频URL列表"):
            parts.append({"file_data": {"file_uri": url, "mime_type": self.guess_mime_type(url, "audio/mpeg")}})
            stats["audio_urls"] += 1
        for url in self.parse_url_lines(values.get("文件URL列表"), skip_invalid, "文件URL列表"):
            parts.append({"file_data": {"file_uri": url, "mime_type": self.guess_mime_type(url, "application/pdf")}})
            stats["file_urls"] += 1
        for path in self.parse_lines(values.get("本地文件路径")):
            parts.append({"text": f"[本地文件: {os.path.basename(path)}]"})
            parts.append(self.local_file_part_native(path))
            stats["local_files"] += 1
        return parts, stats

    def collect_media_openai(self, values, skip_invalid):
        content = []
        stats = {"images": 0, "image_urls": 0, "video_urls": 0, "audio_urls": 0, "file_urls": 0, "local_files": 0}
        for index in range(1, MAX_IMAGE_PARTS + 1):
            tensor = pick(values, f"图片{index}", f"image_{index}", default=None)
            if tensor is not None:
                content.append({"type": "text", "text": f"[图片{index}]"})
                content.append(self.image_part_openai(tensor))
                stats["images"] += 1
        for url in self.parse_url_lines(values.get("图片URL列表"), skip_invalid, "图片URL列表"):
            content.append({"type": "image_url", "image_url": {"url": url}})
            stats["image_urls"] += 1
        unsupported = []
        for field in ("视频URL列表", "音频URL列表", "文件URL列表", "本地文件路径"):
            items = self.parse_lines(values.get(field))
            if items:
                unsupported.append(f"{field}={len(items)}")
        if unsupported:
            self._last_warnings.append("OpenAI兼容模式主要支持文本/图片；以下素材只会作为文本链接传入: " + ", ".join(unsupported))
            for field in ("视频URL列表", "音频URL列表", "文件URL列表", "本地文件路径"):
                for item in self.parse_lines(values.get(field)):
                    content.append({"type": "text", "text": f"[{field}] {item}"})
        return content, stats

    def build_native_payload(self, values):
        task = values.get("任务类型") or "通用问答"
        output_format = values.get("输出格式") or "Markdown结构化"
        question = str(values.get("用户问题") or "").strip()
        system_instruction = str(values.get("系统指令") or "").strip()
        skip_invalid = str(values.get("URL错误处理") or "严格报错") != "严格报错"
        media_parts, stats = self.collect_media_native(values, skip_invalid)
        instruction = self.build_instruction(task, question, output_format)
        parts = [{"text": instruction}] + media_parts

        generation_config = {
            "maxOutputTokens": int(values.get("最大输出Token") or 8192),
            "temperature": float(values.get("创意温度") or 0.4),
            "topP": float(values.get("Top_P") or 0.95),
        }
        if output_format == "JSON结构化":
            generation_config["responseMimeType"] = "application/json"

        thinking_budget = option_value(values.get("思考预算"), "auto")
        if thinking_budget != "auto":
            generation_config["thinkingConfig"] = {"thinkingBudget": int(thinking_budget)}

        payload = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": generation_config,
        }
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        tools = []
        if values.get("启用搜索工具"):
            tools.append({"google_search": {}})
        if values.get("启用代码执行"):
            tools.append({"code_execution": {}})
        if values.get("启用URL上下文"):
            tools.append({"url_context": {}})
        if tools:
            payload["tools"] = tools
        return payload, stats

    def build_openai_payload(self, values, model):
        task = values.get("任务类型") or "通用问答"
        output_format = values.get("输出格式") or "Markdown结构化"
        question = str(values.get("用户问题") or "").strip()
        system_instruction = str(values.get("系统指令") or "").strip()
        skip_invalid = str(values.get("URL错误处理") or "严格报错") != "严格报错"
        media_content, stats = self.collect_media_openai(values, skip_invalid)
        user_content = [{"type": "text", "text": self.build_instruction(task, question, output_format)}] + media_content
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": user_content})
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": int(values.get("最大输出Token") or 8192),
            "temperature": float(values.get("创意温度") or 0.4),
            "top_p": float(values.get("Top_P") or 0.95),
        }
        if output_format == "JSON结构化":
            payload["response_format"] = {"type": "json_object"}
        return payload, stats

    def parse_custom_json(self, raw):
        raw = str(raw or "").strip()
        if not raw:
            return None
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("高级自定义JSON 顶层必须是 JSON object")
        return parsed

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

    def payload_hash(self, model, endpoint, payload):
        def compact(value):
            if isinstance(value, str) and len(value) > 800:
                return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}:len={len(value)}"
            if isinstance(value, list):
                return [compact(item) for item in value]
            if isinstance(value, dict):
                return {key: compact(child) for key, child in value.items()}
            return value

        raw = json.dumps({"model": model, "endpoint": endpoint, "payload": compact(payload)}, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def save_recovery_record(self, cache_key, status, **fields):
        RECOVERY_DIR.mkdir(parents=True, exist_ok=True)
        record = {
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "model": MODEL_NAME,
            "cache_key": cache_key,
            "status": status,
            **fields,
        }
        latest_path = RECOVERY_DIR / f"tikpan-gemini-3-5-flash-{cache_key[:32]}.json"
        events_path = RECOVERY_DIR / "events.jsonl"
        latest_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        with events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return str(latest_path)

    def safe_json_text(self, value, max_len=2400):
        try:
            text = json.dumps(self.redact_payload(value), ensure_ascii=False, sort_keys=True, default=str)
        except Exception:
            text = str(value)
        return text[:max_len] + ("...(truncated)" if len(text) > max_len else "")

    def safe_response_text(self, response, max_len=1800):
        try:
            return response.text[:max_len].strip()
        except Exception:
            return "无法读取上游响应"

    def redact_payload(self, value):
        if isinstance(value, str):
            if len(value) > 512 and (value.startswith("data:") or self.looks_like_base64(value)):
                return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}:len={len(value)}"
            return value
        if isinstance(value, list):
            return [self.redact_payload(item) for item in value]
        if isinstance(value, dict):
            return {key: self.redact_payload(child) for key, child in value.items()}
        return value

    def looks_like_base64(self, value):
        return len(value) > 1200 and all(char.isalnum() or char in "+/=\n\r" for char in value[:1200])

    def extract_text_native(self, res_json):
        texts = []
        if isinstance(res_json, dict):
            for candidate in res_json.get("candidates") or []:
                content = candidate.get("content") if isinstance(candidate, dict) else {}
                for part in (content or {}).get("parts") or []:
                    if isinstance(part, dict) and isinstance(part.get("text"), str):
                        texts.append(part["text"])
        if texts:
            return "\n".join(text.strip() for text in texts if text.strip()).strip()
        return self.scan_text(res_json)

    def extract_text_openai(self, res_json):
        try:
            message = res_json["choices"][0]["message"]
            content = message.get("content", "")
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list):
                texts = [part.get("text", "") for part in content if isinstance(part, dict)]
                return "\n".join(text for text in texts if text).strip()
        except Exception:
            pass
        return self.scan_text(res_json)

    def scan_text(self, obj):
        texts = []

        def scan(value):
            if isinstance(value, dict):
                if isinstance(value.get("text"), str):
                    texts.append(value["text"])
                for child in value.values():
                    scan(child)
            elif isinstance(value, list):
                for child in value:
                    scan(child)

        scan(obj)
        return "\n".join(text.strip() for text in texts if text.strip()).strip()

    def extract_usage(self, res_json):
        if not isinstance(res_json, dict):
            return ""
        usage = res_json.get("usageMetadata") or res_json.get("usage_metadata") or res_json.get("usage") or {}
        if not isinstance(usage, dict):
            return ""
        input_tokens = usage.get("promptTokenCount") or usage.get("prompt_tokens") or usage.get("input_tokens") or ""
        output_tokens = usage.get("candidatesTokenCount") or usage.get("completion_tokens") or usage.get("output_tokens") or ""
        total_tokens = usage.get("totalTokenCount") or usage.get("total_tokens") or ""
        parts = []
        if input_tokens != "":
            parts.append(f"input={input_tokens}")
        if output_tokens != "":
            parts.append(f"output={output_tokens}")
        if total_tokens != "":
            parts.append(f"total={total_tokens}")
        return " | ".join(parts) if parts else self.safe_json_text(usage, 700)

    def split_outputs(self, text, output_format):
        stripped = text.strip()
        prompt = ""
        structured = ""
        if output_format == "JSON结构化":
            try:
                parsed = json.loads(stripped)
                structured = json.dumps(parsed, ensure_ascii=False, indent=2)
                prompt = parsed.get("prompt") or parsed.get("optimized_prompt") or ""
            except Exception:
                structured = json.dumps({"raw_text": stripped}, ensure_ascii=False, indent=2)
        else:
            for marker in ("优化提示词", "可复用提示词", "生成提示词", "Prompt", "prompt"):
                if marker in stripped:
                    prompt = stripped[stripped.find(marker):].strip()
                    break
            structured = json.dumps({"answer": stripped, "prompt": prompt}, ensure_ascii=False, indent=2)
        return prompt, structured

    def finish_summary_native(self, res_json):
        reasons = []
        safety = []
        if isinstance(res_json, dict):
            for candidate in res_json.get("candidates") or []:
                if not isinstance(candidate, dict):
                    continue
                reason = candidate.get("finishReason") or candidate.get("finish_reason")
                if reason:
                    reasons.append(str(reason))
                for rating in candidate.get("safetyRatings") or candidate.get("safety_ratings") or []:
                    if isinstance(rating, dict) and (rating.get("blocked") or rating.get("probability") in ("HIGH", "MEDIUM")):
                        safety.append(f"{rating.get('category')}:{rating.get('probability')}:blocked={rating.get('blocked')}")
        return ", ".join(dict.fromkeys(reasons)) or "unknown", " | ".join(safety) or "none"

    def media_summary(self, stats):
        warnings = getattr(self, "_last_warnings", []) or []
        summary = " | ".join(f"{key}={value}" for key, value in stats.items())
        if warnings:
            summary += " | warnings=" + "；".join(warnings)
        return summary

    def run(self, **kwargs):
        start = time.time()
        values = dict(kwargs)
        self._last_warnings = []
        model = str(values.get("模型") or MODEL_NAME).strip()
        endpoint_mode = option_value(values.get("接口模式"), "/v1beta/models/{model}:generateContent")
        skip_error = bool(values.get("跳过错误", False))
        try:
            comfy.model_management.throw_exception_if_processing_interrupted()
            api_key = str(values.get("API_密钥") or values.get("API_密钥".encode("utf-8", "ignore").decode("utf-8")) or "").strip()
            if not api_key or api_key == "sk-" or len(api_key) < 10:
                return self.make_return(log="ERROR 请填写有效 Tikpan API Key")

            question = str(values.get("用户问题") or "").strip()
            if not question:
                return self.make_return(log="ERROR 用户问题不能为空")

            base_url = normalize_api_host(pick(values, "中转站地址", "api_host", default=API_HOST_OPTIONS[0]))
            verify_tls = bool(values.get("校验HTTPS证书", True))
            post_retry = str(values.get("POST重试策略") or "幂等键轻重试") == "幂等键轻重试"

            if endpoint_mode == "/v1/chat/completions":
                endpoint = endpoint_mode
                payload, stats = self.build_openai_payload(values, model)
                text_extractor = self.extract_text_openai
            else:
                endpoint = endpoint_mode.replace("{model}", model)
                payload, stats = self.build_native_payload(values)
                text_extractor = self.extract_text_native

            custom_json = self.parse_custom_json(values.get("高级自定义JSON"))
            if custom_json:
                payload = self.deep_merge(payload, custom_json)

            cache_key = self.payload_hash(model, endpoint, payload)
            recovery_path = self.save_recovery_record(
                cache_key,
                "pending",
                endpoint=endpoint,
                payload_preview=self.safe_json_text(payload, 1800),
            )
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "Tikpan-ComfyUI-Gemini-3.5-Flash/1.0",
                "Idempotency-Key": f"tikpan-gemini-3-5-flash-{cache_key[:32]}",
            }
            session = self.create_session(allow_post_retry=post_retry)
            url = f"{base_url}{endpoint}"
            pbar = comfy.utils.ProgressBar(100)
            pbar.update_absolute(10, 100)
            print(
                f"[Tikpan-Gemini35Flash] START model={model} | endpoint={endpoint} | {self.media_summary(stats)} | recovery={recovery_path}",
                flush=True,
            )

            try:
                response = session.post(url, json=payload, headers=headers, timeout=(20, 420), verify=verify_tls)
            except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as exc:
                self.save_recovery_record(cache_key, "post_disconnected", endpoint=endpoint, error=str(exc), recovery_path=recovery_path)
                raise RuntimeError(
                    "网络在提交后断开：上游可能已经收到请求。为避免重复扣费，请先检查 recovery/gemini_3_5_flash 里的记录，"
                    f"不要立刻改参数重复提交。cache_key={cache_key[:32]} | recovery={recovery_path}"
                ) from exc

            pbar.update_absolute(70, 100)
            if response.status_code >= 400:
                raise RuntimeError(f"Gemini 3.5 Flash 请求失败 | HTTP {response.status_code} | {self.safe_response_text(response, 2200)}")
            try:
                res_json = response.json()
            except Exception as exc:
                raise RuntimeError(f"Gemini 3.5 Flash 返回非 JSON: {self.safe_response_text(response, 2200)}") from exc
            if isinstance(res_json, dict) and res_json.get("error"):
                raise RuntimeError(f"上游返回错误: {self.safe_json_text(res_json.get('error'), 1800)}")

            answer = text_extractor(res_json)
            if not answer:
                raise RuntimeError(f"上游返回成功但没有可用文本 | raw={self.safe_json_text(res_json, 2200)}")
            usage = self.extract_usage(res_json)
            prompt, structured = self.split_outputs(answer, values.get("输出格式", "Markdown结构化"))
            finish_reason, safety = self.finish_summary_native(res_json) if endpoint != "/v1/chat/completions" else ("chat_completion", "n/a")
            elapsed = round(time.time() - start, 2)
            log = (
                f"OK Gemini 3.5 Flash 完成 | model={model} | endpoint={endpoint} | "
                f"{self.media_summary(stats)} | usage={usage or '上游未返回'} | "
                f"finish={finish_reason} | safety={safety} | elapsed={elapsed}s | post_retry={post_retry}"
            )
            self.save_recovery_record(
                cache_key,
                "success",
                endpoint=endpoint,
                answer=answer,
                prompt=prompt,
                structured_json=structured,
                usage=usage,
                finish_reason=finish_reason,
                safety=safety,
                media_summary=self.media_summary(stats),
                elapsed=elapsed,
                response_preview=self.safe_json_text(res_json, 2400),
            )
            pbar.update_absolute(100, 100)
            print(f"[Tikpan-Gemini35Flash] {log}", flush=True)
            return self.make_return(answer, prompt, structured, usage, log)
        except Exception as exc:
            tb = traceback.format_exc()
            msg = f"ERROR Gemini 3.5 Flash 节点失败: {exc}\n{tb}"
            print(f"[Tikpan-Gemini35Flash] {msg}", flush=True)
            if not skip_error:
                raise RuntimeError(msg) from exc
            return self.make_return(log=msg)


NODE_CLASS_MAPPINGS = {
    "TikpanGemini35FlashNode": TikpanGemini35FlashNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TikpanGemini35FlashNode": "多模态｜Gemini 3.5 Flash 推理",
}
