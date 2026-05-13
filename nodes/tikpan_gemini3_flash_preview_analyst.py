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
MODEL_NAME = "gemini-3-flash-preview"
MODEL_OPTIONS = [MODEL_NAME]
RECOVERY_DIR = Path(__file__).resolve().parents[1] / "recovery" / "gemini_3_flash_preview_analyst"
MAX_INLINE_BYTES = 18 * 1024 * 1024
MAX_IMAGE_PARTS = 12
MAX_FRAME_PARTS = 48
HIGH_COST_FRAME_WARNING = 24


class TikpanGemini3FlashPreviewAnalystNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "福利说明": (
                    ["gemini-3-flash-preview 图片/视频理解分析 | 按输入/输出 Tokens 计费"],
                ),
                "获取密钥地址": (
                    ["👉 https://tikpan.com 获取 Tikpan API Key"],
                ),
                "API_密钥": ("STRING", {"default": os.environ.get("TIKPAN_API_KEY", "sk-")}),
                "模型": (MODEL_OPTIONS, {"default": MODEL_NAME}),
                "分析任务": (
                    [
                        "通用分析",
                        "视频分镜拆解",
                        "商品卖点分析",
                        "广告素材诊断",
                        "画面提示词反推",
                        "安全与合规检查",
                        "自定义",
                    ],
                    {"default": "通用分析"},
                ),
                "分析要求": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "请分析画面主体、场景、动作、镜头、光线、色彩、文字信息、潜在问题，并给出可复用的生成提示词。",
                    },
                ),
                "输出格式": (
                    ["中文报告", "Markdown结构化", "JSON结构化", "提示词优化"],
                    {"default": "Markdown结构化"},
                ),
                "最大输出Token": ("INT", {"default": 4096, "min": 256, "max": 32768, "step": 256}),
                "创意温度": ("FLOAT", {"default": 0.3, "min": 0.0, "max": 2.0, "step": 0.05}),
                "媒体解析度": (
                    ["默认", "低清省费用｜low", "均衡｜medium", "高清细节｜high"],
                    {"default": "默认"},
                ),
                "抽帧策略": (
                    ["均匀覆盖", "按秒抽帧", "首尾加密", "运动变化优先", "混合智能"],
                    {"default": "混合智能"},
                ),
                "视频帧率FPS": ("INT", {"default": 24, "min": 1, "max": 120, "step": 1}),
                "最大抽帧数": ("INT", {"default": 24, "min": 1, "max": MAX_FRAME_PARTS, "step": 1}),
                "视频输入策略": (
                    ["自动优先抽帧", "只用抽帧", "只用视频原件", "抽帧+视频原件(高成本)"],
                    {"default": "自动优先抽帧"},
                ),
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
                        "tooltip": "每行一个公开图片 URL。会作为 file_data 传给 Gemini。",
                    },
                ),
                "视频帧_IMAGE": (
                    "IMAGE",
                    {
                        "tooltip": "LoadVideo 等节点输出的视频帧 IMAGE。节点会自动抽帧压缩后作为多张图片分析。",
                    },
                ),
                "本地视频": ("VIDEO", {"tooltip": "小于约 18MB 时 inline 直传。更大的视频建议用 视频URL 或 视频帧_IMAGE。"}),
                "本地视频路径": ("STRING", {"default": "", "tooltip": "可选，直接填 mp4/mov/webm 等本地路径。"}),
                "视频URL": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "公开视频 URL 或 YouTube URL。会作为 file_data.file_uri 传给 Gemini。",
                    },
                ),
                "高级自定义JSON": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "tooltip": "可选，会深度合并到 generateContent payload，用于后续 Tikpan/上游扩展参数。",
                    },
                ),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("分析报告", "反推提示词", "结构化JSON", "用量", "状态日志")
    OUTPUT_NODE = True
    FUNCTION = "analyze_media"
    CATEGORY = "👑 Tikpan 官方独家节点"

    def make_return(self, report="", prompt="", structured="", usage="", log=""):
        return (str(report or ""), str(prompt or ""), str(structured or ""), str(usage or ""), str(log or ""))

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

    def parse_url_lines(self, text, skip_invalid=False, field_name="URL列表"):
        urls = []
        for line in str(text or "").replace(",", "\n").splitlines():
            item = line.strip()
            if not item:
                continue
            if not item.startswith(("http://", "https://")):
                if skip_invalid:
                    self._last_warnings.append(f"{field_name} 已跳过无效链接: {item[:100]}")
                    continue
                raise ValueError(f"URL 格式不合法: {item[:100]}")
            urls.append(item)
        return urls

    def tensor_to_jpeg_part(self, image_tensor, label, target_px=1280, quality=88):
        if image_tensor is None:
            return None
        arr = 255.0 * image_tensor[0].cpu().numpy()
        img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGB")
        img.thumbnail((target_px, target_px))
        while quality >= 55:
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            data = buf.getvalue()
            if len(data) < 4 * 1024 * 1024:
                return {
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": base64.b64encode(data).decode("utf-8"),
                    }
                }
            quality -= 10
        raise ValueError(f"{label} 压缩后仍过大，请先缩小图片。")

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
        indices = list(range(0, total, step))
        if total - 1 not in indices:
            indices.append(total - 1)
        if len(indices) > count:
            indices = self.uniform_indices(len(indices), count)
            base = list(range(0, total, step))
            if total - 1 not in base:
                base.append(total - 1)
            indices = [base[i] for i in indices]
        return indices

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

    def frames_to_parts(self, frames_tensor, fps, max_frames, strategy):
        if frames_tensor is None:
            return [], 0
        total = int(frames_tensor.shape[0])
        if total <= 0:
            return [], 0
        indices = self.select_frame_indices(frames_tensor, fps, max_frames, strategy)
        count = len(indices)
        parts = []
        for pos, idx in enumerate(indices, start=1):
            part = self.tensor_to_jpeg_part(frames_tensor[idx:idx + 1], f"视频帧{pos}", target_px=960, quality=78)
            if part:
                timestamp = float(idx) / max(1, int(fps or 1))
                parts.append({"text": f"[视频抽帧 {pos}/{count} | 策略: {strategy} | 原帧序号: {idx}/{total - 1} | 约 {timestamp:.2f}s]"})
                parts.append(part)
        return parts, count

    def video_path_from_input(self, local_video, path_text):
        explicit = str(path_text or "").strip().strip('"')
        if explicit:
            return explicit
        if local_video is None:
            return ""
        if isinstance(local_video, (list, tuple)) and local_video:
            return str(local_video[0])
        if isinstance(local_video, str):
            return local_video
        return str(local_video)

    def guess_mime_type(self, path_or_url, fallback="video/mp4"):
        mime_type, _ = mimetypes.guess_type(str(path_or_url or ""))
        return mime_type or fallback

    def local_video_part(self, video_path):
        if not video_path:
            return None
        if not os.path.exists(video_path):
            raise ValueError(f"本地视频不存在: {video_path}")
        size = os.path.getsize(video_path)
        if size <= 0:
            raise ValueError(f"本地视频为空: {video_path}")
        if size > MAX_INLINE_BYTES:
            raise ValueError(
                f"本地视频 {size / 1024 / 1024:.1f}MB，超过 inline 安全限制。"
                "请改用 视频URL，或用 LoadVideo 输出 视频帧_IMAGE 后抽帧分析。"
            )
        with open(video_path, "rb") as f:
            data = f.read()
        return {
            "inline_data": {
                "mime_type": self.guess_mime_type(video_path),
                "data": base64.b64encode(data).decode("utf-8"),
            }
        }

    def media_url_part(self, url, default_mime="video/mp4"):
        url = str(url or "").strip()
        if not url:
            return None
        if not url.startswith(("http://", "https://")):
            raise ValueError("视频URL 必须是 http/https 公开地址。")
        return {
            "file_data": {
                "file_uri": url,
                "mime_type": self.guess_mime_type(url, default_mime),
            }
        }

    def build_instruction(self, task, requirement, output_format):
        task_templates = {
            "通用分析": "做全面多模态理解，兼顾图片/视频主体、环境、动作、文字、质量问题和可执行建议。",
            "视频分镜拆解": "按时间顺序拆解镜头、景别、运镜、主体动作、转场、节奏，并输出可复刻的视频提示词。",
            "商品卖点分析": "识别商品、使用场景、目标人群、卖点、视觉缺陷，并给出电商转化建议。",
            "广告素材诊断": "诊断素材的钩子、信息密度、视觉吸引力、信任感、风险点和优化方向。",
            "画面提示词反推": "反推出适合生成模型使用的正向提示词、镜头语言、风格词、负面约束。",
            "安全与合规检查": "检查敏感内容、版权/商标/人物肖像/平台合规风险，并给出修改建议。",
            "自定义": "严格按用户的分析要求完成任务。",
        }
        format_hint = {
            "中文报告": "用中文自然段输出，重点清楚，不要空泛。",
            "Markdown结构化": "用 Markdown 标题和列表输出，结构包括：摘要、画面观察、时间/镜头、问题、建议、可复用提示词。",
            "JSON结构化": "输出合法 JSON，字段包含 summary、observations、timeline、risks、recommendations、prompt。",
            "提示词优化": "优先输出可直接用于图像/视频生成模型的提示词，并补充负面提示词和参数建议。",
        }.get(output_format, "用中文结构化输出。")
        marker_protocol = ""
        if output_format != "JSON结构化":
            marker_protocol = (
                "\n请严格使用以下固定分隔标记，方便节点稳定拆分输出："
                "\n【分析报告】\n写完整分析结论。"
                "\n【反推提示词】\n写可直接复用到图像/视频生成模型的提示词。"
                "\n【结构化摘要】\n用 JSON 风格要点列出 summary、risks、recommendations。"
            )
        return (
            "你是商业级 AI 视觉/视频分析专家。"
            f"\n任务类型：{task}。{task_templates.get(task, task_templates['通用分析'])}"
            f"\n用户要求：{str(requirement or '').strip()}"
            f"\n输出要求：{format_hint}"
            f"{marker_protocol}"
            "\n如果输入是多张图片或抽帧，请明确区分每张/每帧的观察。"
            "\n如果信息不足，请说明不确定性，不要编造看不见的内容。"
        )

    def build_payload(self, values):
        self._last_warnings = []
        self._last_media_stats = {
            "image_count": 0,
            "frame_count": 0,
            "video_url": False,
            "local_video": False,
            "parts_count": 0,
        }
        skip_invalid_url = str(values.get("URL错误处理") or "严格报错") == "跳过坏链接并写日志" or bool(values.get("跳过错误", False))
        task = values.get("分析任务", "通用分析")
        requirement = values.get("分析要求", "")
        output_format = values.get("输出格式", "Markdown结构化")
        parts = [{"text": self.build_instruction(task, requirement, output_format)}]

        image_count = 0
        for idx in range(1, 5):
            part = self.tensor_to_jpeg_part(values.get(f"图片{idx}"), f"图片{idx}")
            if part:
                parts.append({"text": f"[图片 {idx}]"})
                parts.append(part)
                image_count += 1

        for idx, url in enumerate(self.parse_url_lines(values.get("图片URL列表", ""), skip_invalid_url, "图片URL列表"), start=1):
            if image_count >= MAX_IMAGE_PARTS:
                raise ValueError(f"图片输入最多支持 {MAX_IMAGE_PARTS} 个。")
            parts.append({"text": f"[图片URL {idx}]"})
            parts.append({"file_data": {"file_uri": url, "mime_type": self.guess_mime_type(url, "image/jpeg")}})
            image_count += 1

        strategy = str(values.get("视频输入策略") or "自动优先抽帧")
        video_url = str(values.get("视频URL") or "").strip()
        video_path = self.video_path_from_input(values.get("本地视频"), values.get("本地视频路径"))
        has_native_video = bool(video_url or video_path)
        has_frame_input = values.get("视频帧_IMAGE") is not None
        use_frames = has_frame_input and strategy != "只用视频原件"
        use_native_video = has_native_video and (
            strategy in ("只用视频原件", "抽帧+视频原件(高成本)")
            or (strategy == "自动优先抽帧" and not has_frame_input)
        )
        if has_native_video and values.get("视频帧_IMAGE") is not None and strategy == "自动优先抽帧":
            self._last_warnings.append("检测到同时提供视频原件和抽帧，已按默认策略优先使用抽帧，避免重复计费。")
        if has_native_video and values.get("视频帧_IMAGE") is not None and strategy == "只用抽帧":
            self._last_warnings.append("已按「只用抽帧」策略忽略视频原件。")
        if has_native_video and values.get("视频帧_IMAGE") is not None and strategy == "抽帧+视频原件(高成本)":
            self._last_warnings.append("已同时提交抽帧和视频原件，输入 tokens 和费用可能明显增加。")

        frame_parts, frame_count = self.frames_to_parts(
            values.get("视频帧_IMAGE"),
            pick(values, "视频帧率FPS", "视频帧率_FPS", default=24),
            values.get("最大抽帧数", 24),
            values.get("抽帧策略", "混合智能"),
        ) if use_frames else ([], 0)
        parts.extend(frame_parts)
        if frame_count > HIGH_COST_FRAME_WARNING:
            self._last_warnings.append(f"当前抽帧 {frame_count} 张，可能显著增加输入 tokens 成本。")

        if video_url and use_native_video:
            parts.append({"text": "[视频URL]"})
            parts.append(self.media_url_part(video_url))
            self._last_media_stats["video_url"] = True

        if video_path and use_native_video:
            parts.append({"text": "[本地视频 inline]"})
            parts.append(self.local_video_part(video_path))
            self._last_media_stats["local_video"] = True

        if len(parts) <= 1:
            raise ValueError("请至少输入一张图片、一个视频 URL、一个本地小视频，或连接 视频帧_IMAGE。")

        generation_config = {
            "temperature": float(pick(values, "创意温度", "temperature", default=0.3)),
            "maxOutputTokens": int(pick(values, "最大输出Token", "max_output_tokens", default=4096)),
        }
        media_resolution = option_value(pick(values, "媒体解析度", "media_resolution", default="默认"), "默认")
        if media_resolution != "默认":
            generation_config["mediaResolution"] = media_resolution

        payload = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": generation_config,
        }
        custom_json = self.parse_json_field(values.get("高级自定义JSON"), "高级自定义JSON")
        if custom_json:
            payload = self.deep_merge(payload, custom_json)
        self._last_media_stats.update({
            "image_count": image_count,
            "frame_count": frame_count,
            "parts_count": len(parts),
        })
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
        path = RECOVERY_DIR / f"tikpan-gemini-3-flash-preview-analyst-{cache_key[:32]}.json"
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
        latest_path = RECOVERY_DIR / f"tikpan-gemini-3-flash-preview-analyst-{cache_key[:32]}.json"
        events_path = RECOVERY_DIR / "events.jsonl"
        latest_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        with events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return str(latest_path)

    def extract_text(self, res_json):
        texts = []
        if isinstance(res_json, dict):
            for candidate in res_json.get("candidates") or []:
                content = candidate.get("content") if isinstance(candidate, dict) else {}
                for part in (content or {}).get("parts") or []:
                    if isinstance(part, dict) and isinstance(part.get("text"), str):
                        texts.append(part["text"])
            if texts:
                return "\n".join(t.strip() for t in texts if t.strip()).strip()

        def scan(obj):
            if isinstance(obj, dict):
                if isinstance(obj.get("text"), str):
                    texts.append(obj["text"])
                for value in obj.values():
                    scan(value)
            elif isinstance(obj, list):
                for item in obj:
                    scan(item)

        candidates = res_json.get("candidates") if isinstance(res_json, dict) else None
        if candidates:
            scan(candidates)
        if not texts:
            scan(res_json)
        return "\n".join(t.strip() for t in texts if t.strip()).strip()

    def extract_finish_reason(self, res_json):
        reasons = []
        if isinstance(res_json, dict):
            for candidate in res_json.get("candidates") or []:
                if isinstance(candidate, dict):
                    reason = candidate.get("finishReason") or candidate.get("finish_reason")
                    if reason:
                        reasons.append(str(reason))
        return ", ".join(dict.fromkeys(reasons))

    def extract_safety_summary(self, res_json):
        ratings = []
        if isinstance(res_json, dict):
            prompt_feedback = res_json.get("promptFeedback") or res_json.get("prompt_feedback") or {}
            block_reason = prompt_feedback.get("blockReason") or prompt_feedback.get("block_reason")
            if block_reason:
                ratings.append(f"prompt_block={block_reason}")
            for candidate in res_json.get("candidates") or []:
                if not isinstance(candidate, dict):
                    continue
                for rating in candidate.get("safetyRatings") or candidate.get("safety_ratings") or []:
                    if isinstance(rating, dict):
                        category = rating.get("category", "unknown")
                        probability = rating.get("probability", "")
                        blocked = rating.get("blocked")
                        if blocked or probability in ("HIGH", "MEDIUM"):
                            ratings.append(f"{category}:{probability}:blocked={blocked}")
        return " | ".join(ratings)

    def explain_empty_response(self, res_json):
        finish_reason = self.extract_finish_reason(res_json)
        safety = self.extract_safety_summary(res_json)
        if safety:
            return f"上游返回了安全/合规拦截信息: {safety}"
        if finish_reason in ("MAX_TOKENS", "LENGTH"):
            return "输出可能被长度限制截断，请提高 max_output_tokens 或拆分任务。"
        if isinstance(res_json, dict) and not res_json.get("candidates"):
            return "上游返回成功 JSON，但 candidates 为空，可能是输入媒体不可访问、审核拦截或模型未产出。"
        return "上游返回 JSON，但没有可用文本。"

    def extract_usage(self, res_json):
        usage = res_json.get("usageMetadata") or res_json.get("usage_metadata") or res_json.get("usage") or {}
        if not isinstance(usage, dict):
            return ""
        prompt = usage.get("promptTokenCount") or usage.get("prompt_tokens") or usage.get("input_tokens") or ""
        output = usage.get("candidatesTokenCount") or usage.get("completion_tokens") or usage.get("output_tokens") or ""
        total = usage.get("totalTokenCount") or usage.get("total_tokens") or ""
        parts = []
        if prompt != "":
            parts.append(f"input={prompt}")
        if output != "":
            parts.append(f"output={output}")
        if total != "":
            parts.append(f"total={total}")
        return " | ".join(parts) if parts else self.safe_json_text(usage, 600)

    def split_outputs(self, text, output_format):
        prompt = ""
        structured = ""
        stripped = text.strip()
        if output_format == "JSON结构化":
            structured = stripped
            try:
                parsed = json.loads(stripped)
                prompt = parsed.get("prompt") or parsed.get("optimized_prompt") or ""
            except Exception:
                structured = json.dumps({"raw_text": stripped}, ensure_ascii=False, indent=2)
        else:
            report = stripped
            if "【分析报告】" in stripped:
                report = stripped.split("【分析报告】", 1)[-1].split("【反推提示词】", 1)[0].strip()
            if "【反推提示词】" in stripped:
                prompt = stripped.split("【反推提示词】", 1)[-1].split("【结构化摘要】", 1)[0].strip()
            if "【结构化摘要】" in stripped:
                structured_text = stripped.split("【结构化摘要】", 1)[-1].strip()
                structured = json.dumps({"report": report, "prompt": prompt, "summary": structured_text}, ensure_ascii=False, indent=2)
                return prompt, structured
            for marker in ["可复用提示词", "生成提示词", "推荐 Prompt", "Optimized Prompt", "正向提示词", "Prompt", "prompt"]:
                if marker in stripped:
                    prompt = stripped[stripped.find(marker):].strip()
                    break
            structured = json.dumps({"report": stripped, "prompt": prompt}, ensure_ascii=False, indent=2)
        return prompt, structured

    def media_summary_text(self):
        stats = getattr(self, "_last_media_stats", {}) or {}
        warnings = getattr(self, "_last_warnings", []) or []
        summary = (
            f"images={stats.get('image_count', 0)} | frames={stats.get('frame_count', 0)} | "
            f"video_url={'yes' if stats.get('video_url') else 'no'} | "
            f"local_video={'yes' if stats.get('local_video') else 'no'} | parts={stats.get('parts_count', 0)}"
        )
        if warnings:
            summary += " | warnings=" + "；".join(warnings)
        return summary

    def analyze_media(self, **kwargs):
        start = time.time()
        values = dict(kwargs)
        api_key = str(values.get("API_密钥") or "").strip()
        base_url = API_HOST
        model = str(values.get("模型") or MODEL_NAME).strip()
        use_cache = bool(values.get("复用本地缓存", True))
        skip_error = bool(values.get("跳过错误", False))
        verify_tls = bool(values.get("校验HTTPS证书", True))
        post_retry = str(values.get("POST重试策略") or "幂等键轻重试") == "幂等键轻重试"
        api_path = f"/v1beta/models/{model}:generateContent"

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
                report = cached.get("report", "")
                prompt = cached.get("prompt", "")
                structured = cached.get("structured_json", "")
                usage = cached.get("usage", "")
                log = f"OK 命中本地缓存，未重新请求上游，避免重复扣费 | cache_key={cache_key[:32]}"
                return self.make_return(report, prompt, structured, usage, log)

            payload_preview = self.safe_json_text(
                {"generationConfig": payload.get("generationConfig"), "parts_count": len(payload["contents"][0]["parts"])},
                1200,
            )
            recovery_path = self.save_recovery_record(cache_key, "pending", api_path=api_path, payload_preview=payload_preview)
            media_summary = self.media_summary_text()
            print(f"[Tikpan-Gemini3FlashAnalyst] START {model} | {media_summary} | recovery={recovery_path}", flush=True)

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "Tikpan-ComfyUI-Gemini-3-Flash-Preview-Analyst/1.1",
                "Idempotency-Key": f"tikpan-gemini-3-flash-preview-analyst-{cache_key[:32]}",
            }
            session = self.create_session(allow_post_retry=post_retry)
            url = f"{base_url}{api_path}"

            try:
                response = session.post(url, json=payload, headers=headers, timeout=(20, 420), verify=verify_tls)
            except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
                self.save_recovery_record(cache_key, "post_disconnected", api_path=api_path, error=str(e), recovery_path=recovery_path)
                raise RuntimeError(
                    "网络在提交后断开：上游可能已经收到并扣费。请先检查 recovery/gemini_3_flash_preview_analyst，"
                    f"不要立刻改参数重复提交。cache_key={cache_key[:32]} | recovery={recovery_path}"
                )

            pbar.update_absolute(60, 100)
            if response.status_code != 200:
                raise RuntimeError(f"Gemini 分析请求失败 | HTTP {response.status_code} | {self.safe_response_text(response)}")
            try:
                res_json = response.json()
            except Exception:
                raise RuntimeError(f"Gemini 分析接口返回非 JSON: {self.safe_response_text(response)}")
            if isinstance(res_json, dict) and res_json.get("error"):
                raise RuntimeError(f"上游返回错误: {self.safe_json_text(res_json.get('error'))}")

            report = self.extract_text(res_json)
            if not report:
                raise RuntimeError(f"{self.explain_empty_response(res_json)} | raw={self.safe_json_text(res_json, 2200)}")
            usage = self.extract_usage(res_json)
            finish_reason = self.extract_finish_reason(res_json) or "未返回"
            safety = self.extract_safety_summary(res_json) or "无明显阻断"
            prompt, structured = self.split_outputs(report, values.get("输出格式", "Markdown结构化"))
            elapsed = round(time.time() - start, 2)
            log = (
                f"OK {model} 分析完成 | {media_summary} | finish_reason={finish_reason} | safety={safety} | "
                f"max_output_tokens={payload.get('generationConfig', {}).get('maxOutputTokens')} | "
                f"usage={usage or '上游未返回'} | elapsed={elapsed}s | api={API_HOST}{api_path} | post_retry={post_retry}"
            )
            self.save_recovery_record(
                cache_key,
                "success",
                api_path=api_path,
                report=report,
                prompt=prompt,
                structured_json=structured,
                usage=usage,
                elapsed=elapsed,
                finish_reason=finish_reason,
                safety=safety,
                media_summary=media_summary,
                response_preview=self.safe_json_text(res_json, 2200),
            )
            pbar.update_absolute(100, 100)
            print(f"[Tikpan-Gemini3FlashAnalyst] {log}", flush=True)
            return self.make_return(report, prompt, structured, usage, log)

        except Exception as e:
            tb = traceback.format_exc()
            err_msg = f"ERROR {model} 分析节点失败: {e}\n{tb}"
            print(err_msg, flush=True)
            if not skip_error:
                raise
            return self.make_return(log=err_msg)


NODE_CLASS_MAPPINGS = {
    "TikpanGemini3FlashPreviewAnalystNode": TikpanGemini3FlashPreviewAnalystNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TikpanGemini3FlashPreviewAnalystNode": "🧠 Tikpan: Gemini 3 Flash Preview 图片/视频分析",
}
