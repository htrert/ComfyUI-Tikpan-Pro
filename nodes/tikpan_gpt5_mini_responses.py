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

try:
    from .tikpan_node_options import option_value, pick
except Exception:
    import importlib.util

    _options_spec = importlib.util.spec_from_file_location(
        "tikpan_node_options", Path(__file__).with_name("tikpan_node_options.py")
    )
    _options_module = importlib.util.module_from_spec(_options_spec)
    _options_spec.loader.exec_module(_options_module)
    option_value = _options_module.option_value
    pick = _options_module.pick


API_HOST = "https://tikpan.com"
API_BASE_URL = API_HOST
MODEL_NAME = "gpt-5.4-mini"
MODEL_OPTIONS = [MODEL_NAME]
RECOVERY_DIR = Path(__file__).resolve().parents[1] / "recovery" / "gpt5_4_mini_responses"
MAX_INLINE_IMAGE_BYTES = 4 * 1024 * 1024
MAX_FILE_INLINE_BYTES = 16 * 1024 * 1024
MAX_IMAGE_PARTS = 16
MAX_FRAME_PARTS = 48
MAX_FILE_PARTS = 8
HIGH_COST_FRAME_WARNING = 18


class TikpanGPT5MiniResponsesNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "福利说明": (
                    ["gpt-5.4-mini 多模态文本/图片推理 | /v1/responses | 按输入/输出/缓存命中 Tokens 计费"],
                ),
                "获取密钥地址": (
                    ["👉 https://tikpan.com 获取 Tikpan API Key"],
                ),
                "API_密钥": ("STRING", {"default": os.environ.get("TIKPAN_API_KEY", "sk-")}),
                "模型": (MODEL_OPTIONS, {"default": MODEL_NAME}),
                "任务类型": (
                    [
                        "通用问答",
                        "图片理解分析",
                        "视频抽帧分析",
                        "商品卖点提炼",
                        "广告文案与落地页优化",
                        "代码/JSON/数据分析",
                        "提示词优化",
                        "安全合规检查",
                        "自定义",
                    ],
                    {"default": "通用问答"},
                ),
                "用户问题": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "请分析输入内容，给出清晰、可执行、适合商业使用的中文结论。",
                    },
                ),
                "系统指令": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "你是 Tikpan 的商业级 AI 助手，回答要准确、结构化、可执行。信息不足时说明不确定性，不要编造。",
                    },
                ),
                "输出格式": (
                    ["中文报告", "Markdown结构化", "JSON结构化", "提示词优化"],
                    {"default": "Markdown结构化"},
                ),
                "推理强度": (
                    ["最省｜minimal", "低｜low", "中｜medium", "高｜high"],
                    {"default": "低｜low"},
                ),
                "回答详细度": (
                    ["简洁｜low", "适中｜medium", "详细｜high"],
                    {"default": "适中｜medium"},
                ),
                "最大输出Token": ("INT", {"default": 4096, "min": 256, "max": 32768, "step": 256}),
                "创意温度": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.05}),
                "图片细节": (["自动｜auto", "低清省费用｜low", "高清细节｜high"], {"default": "自动｜auto"}),
                "抽帧策略": (
                    ["均匀覆盖", "按秒抽帧", "首尾加密", "运动变化优先", "混合智能"],
                    {"default": "混合智能"},
                ),
                "视频帧率FPS": ("INT", {"default": 24, "min": 1, "max": 120, "step": 1}),
                "最大抽帧数": ("INT", {"default": 12, "min": 1, "max": MAX_FRAME_PARTS, "step": 1}),
                "启用联网搜索": ("BOOLEAN", {"default": False}),
                "URL错误处理": (["严格报错", "跳过坏链接并写日志"], {"default": "严格报错"}),
                "POST重试策略": (["幂等键轻重试", "保守不重试POST"], {"default": "幂等键轻重试"}),
                "复用本地缓存": ("BOOLEAN", {"default": True}),
                "跳过错误": ("BOOLEAN", {"default": False}),
                "校验HTTPS证书": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "图片1": ("IMAGE",),
                "图片2": ("IMAGE",),
                "图片3": ("IMAGE",),
                "图片4": ("IMAGE",),
                "图片URL列表": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "tooltip": "每行一个公开图片 URL。Responses API 会作为 input_image.image_url 传递。",
                    },
                ),
                "视频帧_IMAGE": (
                    "IMAGE",
                    {
                        "tooltip": "LoadVideo 等节点输出的视频帧 IMAGE。gpt-5.4-mini 会按抽帧图片进行视频内容分析。",
                    },
                ),
                "文件URL列表": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "tooltip": "每行一个公开文件 URL。适合 PDF、文本、CSV 等可由上游读取的文件。",
                    },
                ),
                "本地文件路径": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "tooltip": "每行一个本地文件路径。小文件会 inline 为 input_file，适合 PDF/TXT/CSV/JSON。",
                    },
                ),
                "高级自定义JSON": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "tooltip": "可选，深度合并到 /v1/responses payload，用于临时透传 Tikpan/上游新参数。",
                    },
                ),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("回答文本", "优化提示词", "结构化JSON", "用量", "状态日志")
    OUTPUT_NODE = True
    FUNCTION = "run_responses"
    CATEGORY = "👑 Tikpan 官方独家节点"

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
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def safe_json_text(self, value, max_len=2400):
        try:
            text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        except Exception:
            text = str(value)
        return text[:max_len] + ("...(truncated)" if len(text) > max_len else "")

    def safe_response_text(self, response, max_len=1800):
        try:
            return response.text[:max_len].strip()
        except Exception:
            return "无法读取上游响应"

    def parse_json_field(self, raw, field_name):
        raw = str(raw or "").strip()
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
        except Exception as e:
            raise ValueError(f"{field_name} 不是合法 JSON: {e}")
        if not isinstance(parsed, dict):
            raise ValueError(f"{field_name} 顶层必须是 JSON object。")
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

    def parse_lines(self, text):
        items = []
        for line in str(text or "").replace(",", "\n").splitlines():
            item = line.strip().strip('"')
            if item:
                items.append(item)
        return items

    def parse_url_lines(self, text, skip_invalid=False, field_name="URL列表"):
        urls = []
        for item in self.parse_lines(text):
            if not item.startswith(("http://", "https://")):
                if skip_invalid:
                    self._last_warnings.append(f"{field_name} 已跳过无效链接: {item[:100]}")
                    continue
                raise ValueError(f"URL 格式不合法: {item[:100]}")
            urls.append(item)
        return urls

    def guess_mime_type(self, path_or_url, fallback="application/octet-stream"):
        mime_type, _ = mimetypes.guess_type(str(path_or_url or ""))
        return mime_type or fallback

    def image_tensor_to_data_url(self, image_tensor, label, target_px=1280, quality=88):
        if image_tensor is None:
            return ""
        arr = 255.0 * image_tensor[0].cpu().numpy()
        img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGB")
        img.thumbnail((target_px, target_px))
        while quality >= 55:
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            data = buf.getvalue()
            if len(data) <= MAX_INLINE_IMAGE_BYTES:
                b64 = base64.b64encode(data).decode("utf-8")
                return f"data:image/jpeg;base64,{b64}"
            quality -= 10
        raise ValueError(f"{label} 压缩后仍超过 4MB，请先缩小图片。")

    def unique_sorted_indices(self, indices, total, limit):
        clean = []
        seen = set()
        for raw in indices:
            idx = max(0, min(total - 1, int(raw)))
            if idx not in seen:
                clean.append(idx)
                seen.add(idx)
            if len(clean) >= limit:
                break
        return sorted(clean)

    def uniform_indices(self, total, count):
        if count <= 1:
            return [0]
        return np.linspace(0, total - 1, count, dtype=int).tolist()

    def per_second_indices(self, total, fps, count):
        step = max(1, int(round(float(fps or 1))))
        base = list(range(0, total, step))
        if total - 1 not in base:
            base.append(total - 1)
        if len(base) <= count:
            return base
        return [base[i] for i in self.uniform_indices(len(base), count)]

    def head_tail_dense_indices(self, total, count):
        if count <= 3 or total <= 3:
            return self.uniform_indices(total, count)
        head_count = max(2, int(count * 0.3))
        tail_count = max(2, int(count * 0.3))
        mid_count = max(1, count - head_count - tail_count)
        head_end = max(1, int(total * 0.18))
        tail_start = min(total - 2, int(total * 0.82))
        indices = []
        indices.extend(np.linspace(0, head_end, head_count, dtype=int).tolist())
        indices.extend(np.linspace(head_end, tail_start, mid_count + 2, dtype=int).tolist()[1:-1])
        indices.extend(np.linspace(tail_start, total - 1, tail_count, dtype=int).tolist())
        return indices

    def motion_priority_indices(self, frames_tensor, count):
        total = int(frames_tensor.shape[0])
        if total <= 2 or count <= 2:
            return self.uniform_indices(total, min(count, total))
        candidate_count = min(total, max(count * 8, 48), 240)
        candidates = self.uniform_indices(total, candidate_count)
        scores = []
        prev = None
        for idx in candidates:
            arr = frames_tensor[idx].detach().float().cpu().numpy()
            arr = arr[:: max(1, arr.shape[0] // 64), :: max(1, arr.shape[1] // 64), :3]
            if prev is not None:
                scores.append((float(np.mean(np.abs(arr - prev))), idx))
            prev = arr
        top = [idx for _, idx in sorted(scores, reverse=True)[: max(0, count - 2)]]
        return [0, *top, total - 1]

    def select_frame_indices(self, frames_tensor, fps, max_frames, strategy):
        total = int(frames_tensor.shape[0])
        count = min(max(1, int(max_frames)), total, MAX_FRAME_PARTS)
        strategy = str(strategy or "混合智能")
        if strategy == "按秒抽帧":
            raw = self.per_second_indices(total, fps, count)
        elif strategy == "首尾加密":
            raw = self.head_tail_dense_indices(total, count)
        elif strategy == "运动变化优先":
            raw = self.motion_priority_indices(frames_tensor, count)
        elif strategy == "混合智能":
            uniform_count = max(2, count // 2)
            motion_count = max(2, count - uniform_count + 2)
            raw = self.uniform_indices(total, uniform_count) + self.motion_priority_indices(frames_tensor, motion_count)
        else:
            raw = self.uniform_indices(total, count)
        return self.unique_sorted_indices(raw, total, count)

    def frames_to_image_items(self, frames_tensor, fps, max_frames, detail, strategy):
        if frames_tensor is None:
            return []
        total = int(frames_tensor.shape[0])
        if total <= 0:
            return []
        indices = self.select_frame_indices(frames_tensor, fps, max_frames, strategy)
        count = len(indices)
        items = []
        for pos, idx in enumerate(indices, start=1):
            timestamp = float(idx) / max(1, int(fps or 1))
            items.append({"type": "input_text", "text": f"[视频抽帧 {pos}/{count} | 策略: {strategy} | 原帧序号: {idx}/{total - 1} | 约 {timestamp:.2f}s]"})
            data_url = self.image_tensor_to_data_url(frames_tensor[idx:idx + 1], f"视频帧{pos}", target_px=960, quality=78)
            items.append({"type": "input_image", "image_url": data_url, "detail": detail})
        return items

    def local_file_part(self, file_path):
        file_path = str(file_path or "").strip().strip('"')
        if not file_path:
            return None
        if not os.path.exists(file_path):
            raise ValueError(f"本地文件不存在: {file_path}")
        if not os.path.isfile(file_path):
            raise ValueError(f"本地文件路径不是文件: {file_path}")
        size = os.path.getsize(file_path)
        if size <= 0:
            raise ValueError(f"本地文件为空: {file_path}")
        if size > MAX_FILE_INLINE_BYTES:
            raise ValueError(f"本地文件 {size / 1024 / 1024:.1f}MB，超过 inline 安全限制。请先上传为 URL 再传入。")
        with open(file_path, "rb") as handle:
            data = base64.b64encode(handle.read()).decode("utf-8")
        return {
            "type": "input_file",
            "filename": os.path.basename(file_path),
            "file_data": f"data:{self.guess_mime_type(file_path)};base64,{data}",
        }

    def output_instruction(self, output_format):
        if output_format == "JSON结构化":
            return (
                "请输出合法 JSON，不要包 Markdown 代码块。字段建议包含 summary、analysis、risks、recommendations、"
                "optimized_prompt、next_steps。"
            )
        if output_format == "提示词优化":
            return "优先输出可直接用于图像/视频/文案模型的优化提示词，并补充负面提示词、参数建议和使用注意事项。"
        if output_format == "中文报告":
            return (
                "用中文自然段输出，结论先行，重点清晰，避免空话。"
                "\n请严格使用固定分隔标记：【回答文本】、【优化提示词】、【结构化摘要】。"
            )
        return (
            "用 Markdown 标题、列表和表格输出，结构包括摘要、观察/推理、问题、建议、可复用提示词。"
            "\n请严格使用固定分隔标记：【回答文本】、【优化提示词】、【结构化摘要】。"
        )

    def task_instruction(self, task):
        templates = {
            "通用问答": "完成用户问题，必要时结合输入图片/文件进行推理。",
            "图片理解分析": "分析图片主体、场景、文字、风格、质量问题、风险点和可执行建议。",
            "视频抽帧分析": "把抽帧当作时间序列，分析镜头、动作、节奏、分镜变化和可复用视频提示词。",
            "商品卖点提炼": "识别商品、目标人群、核心卖点、场景价值、转化阻力和营销话术。",
            "广告文案与落地页优化": "诊断广告素材/文案/页面结构，输出更适合转化的改写方案。",
            "代码/JSON/数据分析": "检查代码、JSON 或数据内容，指出问题、边界情况和修复建议。",
            "提示词优化": "把用户要求改写为更清晰、可执行、适合模型调用的提示词。",
            "安全合规检查": "识别敏感内容、版权、商标、肖像、平台政策和商业合规风险。",
            "自定义": "严格按用户问题完成任务。",
        }
        return templates.get(task, templates["通用问答"])

    def build_content_items(self, values):
        self._last_warnings = []
        self._last_media_stats = {
            "image_count": 0,
            "frame_count": 0,
            "file_count": 0,
            "content_count": 0,
        }
        task = values.get("任务类型", "通用问答")
        user_question = str(values.get("用户问题") or "").strip()
        output_format = values.get("输出格式", "Markdown结构化")
        detail = option_value(values.get("图片细节", "自动｜auto"), "auto")
        skip_invalid_url = str(values.get("URL错误处理") or "严格报错") == "跳过坏链接并写日志" or bool(values.get("跳过错误", False))
        content = [
            {
                "type": "input_text",
                "text": (
                    f"任务类型：{task}\n"
                    f"任务说明：{self.task_instruction(task)}\n"
                    f"输出要求：{self.output_instruction(output_format)}\n"
                    f"用户问题：{user_question}"
                ),
            }
        ]

        image_count = 0
        for idx in range(1, 5):
            data_url = self.image_tensor_to_data_url(values.get(f"图片{idx}"), f"图片{idx}")
            if data_url:
                content.append({"type": "input_text", "text": f"[图片 {idx}]"})
                content.append({"type": "input_image", "image_url": data_url, "detail": detail})
                image_count += 1

        for idx, url in enumerate(self.parse_url_lines(values.get("图片URL列表", ""), skip_invalid_url, "图片URL列表"), start=1):
            if image_count >= MAX_IMAGE_PARTS:
                raise ValueError(f"图片输入最多支持 {MAX_IMAGE_PARTS} 个。")
            content.append({"type": "input_text", "text": f"[图片URL {idx}]"})
            content.append({"type": "input_image", "image_url": url, "detail": detail})
            image_count += 1

        frame_items = self.frames_to_image_items(
            values.get("视频帧_IMAGE"),
            pick(values, "视频帧率FPS", "视频帧率_FPS", default=24),
            values.get("最大抽帧数", 12),
            detail,
            values.get("抽帧策略", "混合智能"),
        )
        frame_count = sum(1 for item in frame_items if item.get("type") == "input_image")
        if frame_count > HIGH_COST_FRAME_WARNING:
            self._last_warnings.append(f"当前抽帧 {frame_count} 张，可能显著增加输入 tokens 成本。")
        content.extend(frame_items)

        file_count = 0
        for idx, url in enumerate(self.parse_url_lines(values.get("文件URL列表", ""), skip_invalid_url, "文件URL列表"), start=1):
            if file_count >= MAX_FILE_PARTS:
                raise ValueError(f"文件输入最多支持 {MAX_FILE_PARTS} 个。")
            content.append({"type": "input_text", "text": f"[文件URL {idx}]"})
            content.append({"type": "input_file", "file_url": url})
            file_count += 1

        for path in self.parse_lines(values.get("本地文件路径", "")):
            if file_count >= MAX_FILE_PARTS:
                raise ValueError(f"文件输入最多支持 {MAX_FILE_PARTS} 个。")
            part = self.local_file_part(path)
            if part:
                content.append(part)
                file_count += 1

        self._last_media_stats.update({
            "image_count": image_count,
            "frame_count": frame_count,
            "file_count": file_count,
            "content_count": len(content),
        })
        return content

    def build_payload(self, values):
        system_prompt = str(values.get("系统指令") or "").strip()
        content = self.build_content_items(values)
        model = str(values.get("模型") or MODEL_NAME).strip()
        payload = {
            "model": model,
            "instructions": system_prompt,
            "input": [
                {
                    "role": "user",
                    "content": content,
                }
            ],
            "reasoning": {"effort": option_value(pick(values, "推理强度", "reasoning_effort", default="低｜low"), "low")},
            "text": {"verbosity": option_value(pick(values, "回答详细度", "verbosity", default="适中｜medium"), "medium")},
            "max_output_tokens": int(pick(values, "最大输出Token", "max_output_tokens", default=4096)),
        }
        temperature = float(pick(values, "创意温度", "temperature", default=1.0))
        if temperature != 1.0:
            payload["temperature"] = temperature
        if values.get("输出格式") == "JSON结构化":
            payload["text"]["format"] = {"type": "json_object"}
        if bool(values.get("启用联网搜索", False)):
            payload["tools"] = [{"type": "web_search_preview"}]

        custom_json = self.parse_json_field(values.get("高级自定义JSON"), "高级自定义JSON")
        if custom_json:
            payload = self.deep_merge(payload, custom_json)
        return payload

    def payload_hash(self, payload, model=MODEL_NAME):
        def compact(value):
            if isinstance(value, str) and len(value) > 2048:
                return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}:len={len(value)}"
            if isinstance(value, dict):
                return {k: compact(v) for k, v in value.items()}
            if isinstance(value, list):
                return [compact(v) for v in value]
            return value

        raw = json.dumps({"model": model, "payload": compact(payload)}, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def read_cache(self, cache_key):
        path = RECOVERY_DIR / f"tikpan-gpt-5-4-mini-responses-{cache_key[:32]}.json"
        if path.exists() and path.stat().st_size > 16:
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return None
        return None

    def save_recovery_record(self, cache_key, status, **fields):
        RECOVERY_DIR.mkdir(parents=True, exist_ok=True)
        record = {
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "model": MODEL_NAME,
            "cache_key": cache_key,
            "status": status,
            **fields,
        }
        latest_path = RECOVERY_DIR / f"tikpan-gpt-5-4-mini-responses-{cache_key[:32]}.json"
        events_path = RECOVERY_DIR / "events.jsonl"
        latest_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        with events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return str(latest_path)

    def extract_text(self, res_json):
        if not isinstance(res_json, dict):
            return ""
        if isinstance(res_json.get("output_text"), str) and res_json["output_text"].strip():
            return res_json["output_text"].strip()
        texts = []
        for output in res_json.get("output") or []:
            if not isinstance(output, dict) or output.get("type") not in ("message", "response.output_message"):
                continue
            for item in output.get("content") or []:
                if isinstance(item, dict) and item.get("type") in ("output_text", "text") and isinstance(item.get("text"), str):
                    texts.append(item["text"])
        if texts:
            return "\n".join(text.strip() for text in texts if text.strip()).strip()

        def scan(obj):
            if isinstance(obj, dict):
                if obj.get("type") == "output_text" and isinstance(obj.get("text"), str):
                    texts.append(obj["text"])
                for value in obj.values():
                    scan(value)
            elif isinstance(obj, list):
                for item in obj:
                    scan(item)

        scan(res_json.get("output") or res_json)
        return "\n".join(text.strip() for text in texts if text.strip()).strip()

    def extract_finish_status(self, res_json):
        if not isinstance(res_json, dict):
            return ""
        status = res_json.get("status") or ""
        incomplete = res_json.get("incomplete_details") or res_json.get("incompleteDetails") or {}
        if isinstance(incomplete, dict) and incomplete:
            reason = incomplete.get("reason") or incomplete.get("message") or self.safe_json_text(incomplete, 300)
            return f"{status or 'incomplete'}:{reason}"
        return str(status or "")

    def explain_empty_response(self, res_json):
        if not isinstance(res_json, dict):
            return "上游响应不是 JSON object。"
        if res_json.get("error"):
            return f"上游返回错误: {self.safe_json_text(res_json.get('error'))}"
        finish_status = self.extract_finish_status(res_json)
        if "max_output" in finish_status or "tokens" in finish_status:
            return "输出可能达到长度限制，请提高 max_output_tokens 或拆分任务。"
        if res_json.get("output") == []:
            return "上游返回 output 为空，可能是安全策略、工具调用未完成或模型未产出文本。"
        return "上游返回 JSON，但没有可用输出文本。"

    def extract_usage(self, res_json):
        usage = {}
        if isinstance(res_json, dict):
            usage = res_json.get("usage") or res_json.get("usage_metadata") or {}
        if not isinstance(usage, dict):
            return ""
        input_tokens = usage.get("input_tokens") or usage.get("prompt_tokens") or ""
        output_tokens = usage.get("output_tokens") or usage.get("completion_tokens") or ""
        total_tokens = usage.get("total_tokens") or ""
        cached_tokens = ""
        details = usage.get("input_tokens_details") or usage.get("prompt_tokens_details") or {}
        if isinstance(details, dict):
            cached_tokens = details.get("cached_tokens") or ""
        parts = []
        if input_tokens != "":
            parts.append(f"input={input_tokens}")
        if output_tokens != "":
            parts.append(f"output={output_tokens}")
        if total_tokens != "":
            parts.append(f"total={total_tokens}")
        if cached_tokens != "":
            parts.append(f"cached={cached_tokens}")
        return " | ".join(parts) if parts else self.safe_json_text(usage, 600)

    def split_outputs(self, text, output_format):
        prompt = ""
        structured = ""
        stripped = text.strip()
        if output_format == "JSON结构化":
            structured = stripped
            try:
                parsed = json.loads(stripped)
                prompt = parsed.get("optimized_prompt") or parsed.get("prompt") or ""
            except Exception:
                structured = json.dumps({"raw_text": stripped}, ensure_ascii=False, indent=2)
        else:
            answer = stripped
            if "【回答文本】" in stripped:
                answer = stripped.split("【回答文本】", 1)[-1].split("【优化提示词】", 1)[0].strip()
            if "【优化提示词】" in stripped:
                prompt = stripped.split("【优化提示词】", 1)[-1].split("【结构化摘要】", 1)[0].strip()
            if "【结构化摘要】" in stripped:
                structured_text = stripped.split("【结构化摘要】", 1)[-1].strip()
                structured = json.dumps({"answer": answer, "optimized_prompt": prompt, "summary": structured_text}, ensure_ascii=False, indent=2)
                return prompt, structured
            for marker in ["优化提示词", "可复用提示词", "生成提示词", "推荐 Prompt", "Optimized Prompt", "正向提示词", "Prompt", "prompt"]:
                if marker in stripped:
                    prompt = stripped[stripped.find(marker):].strip()
                    break
            structured = json.dumps({"answer": stripped, "optimized_prompt": prompt}, ensure_ascii=False, indent=2)
        return prompt, structured

    def media_summary_text(self):
        stats = getattr(self, "_last_media_stats", {}) or {}
        warnings = getattr(self, "_last_warnings", []) or []
        summary = (
            f"images={stats.get('image_count', 0)} | frames={stats.get('frame_count', 0)} | "
            f"files={stats.get('file_count', 0)} | content={stats.get('content_count', 0)}"
        )
        if warnings:
            summary += " | warnings=" + "；".join(warnings)
        return summary

    def run_responses(self, **kwargs):
        start = time.time()
        values = dict(kwargs)
        api_key = str(values.get("API_密钥") or "").strip()
        base_url = API_HOST
        model = str(values.get("模型") or MODEL_NAME).strip()
        use_cache = bool(values.get("复用本地缓存", True))
        skip_error = bool(values.get("跳过错误", False))
        verify_tls = bool(values.get("校验HTTPS证书", True))
        post_retry = str(values.get("POST重试策略") or "幂等键轻重试") == "幂等键轻重试"
        api_path = "/v1/responses"

        try:
            comfy.model_management.throw_exception_if_processing_interrupted()
            if not api_key or api_key == "sk-" or len(api_key) < 10:
                return self.make_return(log="ERROR 请填写有效 Tikpan API Key。")

            payload = self.build_payload(values)
            cache_key = self.payload_hash(payload, model)
            pbar = comfy.utils.ProgressBar(100)
            pbar.update_absolute(5, 100)

            cached = self.read_cache(cache_key) if use_cache else None
            if cached and cached.get("status") == "success":
                answer = cached.get("answer", "")
                prompt = cached.get("prompt", "")
                structured = cached.get("structured_json", "")
                usage = cached.get("usage", "")
                log = f"OK 命中本地缓存，未重新请求上游，避免重复扣费 | cache_key={cache_key[:32]}"
                return self.make_return(answer, prompt, structured, usage, log)

            content_count = len(payload["input"][0]["content"])
            payload_preview = self.safe_json_text(
                {
                    "model": payload.get("model"),
                    "reasoning": payload.get("reasoning"),
                    "text": payload.get("text"),
                    "tools": payload.get("tools"),
                    "content_count": content_count,
                    "max_output_tokens": payload.get("max_output_tokens"),
                },
                1600,
            )
            recovery_path = self.save_recovery_record(cache_key, "pending", api_path=api_path, payload_preview=payload_preview)
            media_summary = self.media_summary_text()
            print(f"[Tikpan-GPT54MiniResponses] START {model} | {media_summary} | recovery={recovery_path}", flush=True)

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "Tikpan-ComfyUI-GPT-5.4-Mini-Responses/1.2",
                "Idempotency-Key": f"tikpan-gpt-5-4-mini-responses-{cache_key[:32]}",
            }
            session = self.create_session(allow_post_retry=post_retry)
            url = f"{base_url}{api_path}"

            try:
                response = session.post(url, json=payload, headers=headers, timeout=(20, 420), verify=verify_tls)
            except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
                self.save_recovery_record(cache_key, "post_disconnected", api_path=api_path, error=str(e), recovery_path=recovery_path)
                raise RuntimeError(
                    "网络在提交后断开：上游可能已经收到并扣费。请先检查 recovery/gpt5_4_mini_responses，"
                    f"不要立刻改参数重复提交。cache_key={cache_key[:32]} | recovery={recovery_path}"
                )

            pbar.update_absolute(60, 100)
            if response.status_code != 200:
                raise RuntimeError(f"GPT-5.4 Mini Responses 请求失败 | HTTP {response.status_code} | {self.safe_response_text(response)}")
            try:
                res_json = response.json()
            except Exception:
                raise RuntimeError(f"GPT-5.4 Mini Responses 接口返回非 JSON: {self.safe_response_text(response)}")
            if isinstance(res_json, dict) and res_json.get("error"):
                raise RuntimeError(f"上游返回错误: {self.safe_json_text(res_json.get('error'))}")

            answer = self.extract_text(res_json)
            if not answer:
                raise RuntimeError(f"{self.explain_empty_response(res_json)} | raw={self.safe_json_text(res_json, 2200)}")
            usage = self.extract_usage(res_json)
            finish_status = self.extract_finish_status(res_json) or "未返回"
            prompt, structured = self.split_outputs(answer, values.get("输出格式", "Markdown结构化"))
            elapsed = round(time.time() - start, 2)
            log = (
                f"OK {model} Responses 完成 | {media_summary} | status={finish_status} | "
                f"max_output_tokens={payload.get('max_output_tokens')} | usage={usage or '上游未返回'} | "
                f"elapsed={elapsed}s | api={API_HOST}{api_path} | post_retry={post_retry}"
            )
            self.save_recovery_record(
                cache_key,
                "success",
                api_path=api_path,
                answer=answer,
                prompt=prompt,
                structured_json=structured,
                usage=usage,
                elapsed=elapsed,
                finish_status=finish_status,
                media_summary=media_summary,
                response_preview=self.safe_json_text(res_json, 2200),
            )
            pbar.update_absolute(100, 100)
            print(f"[Tikpan-GPT54MiniResponses] {log}", flush=True)
            return self.make_return(answer, prompt, structured, usage, log)

        except Exception as e:
            tb = traceback.format_exc()
            err_msg = f"ERROR {model} Responses 节点失败: {e}\n{tb}"
            print(err_msg, flush=True)
            if not skip_error:
                raise
            return self.make_return(log=err_msg)


NODE_CLASS_MAPPINGS = {
    "TikpanGPT5MiniResponsesNode": TikpanGPT5MiniResponsesNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TikpanGPT5MiniResponsesNode": "🧠 Tikpan: GPT-5.4 Mini 多模态推理",
}
