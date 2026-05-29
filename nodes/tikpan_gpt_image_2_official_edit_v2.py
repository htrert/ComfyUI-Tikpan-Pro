import math
import base64
import hashlib
import json
import re
import socket
import sys
import traceback
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path

import numpy as np
import requests
import torch
import urllib3
import folder_paths
from PIL import Image, ImageOps
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from urllib3.connection import HTTPConnection as _Urllib3HTTPConnection, HTTPSConnection as _Urllib3HTTPSConnection
    from urllib3.connectionpool import HTTPConnectionPool as _Urllib3HTTPConnectionPool, HTTPSConnectionPool as _Urllib3HTTPSConnectionPool
    _URLLIB3_OK = True
except Exception:
    _URLLIB3_OK = False


_KEEPALIVE_SOCKET_OPTIONS = [
    (socket.IPPROTO_TCP, socket.TCP_NODELAY, 1),
    (socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1),
]
for _kn, _kv in (("TCP_KEEPIDLE", 30), ("TCP_KEEPINTVL", 30), ("TCP_KEEPCNT", 4)):
    _kc = getattr(socket, _kn, None)
    if _kc is not None:
        _KEEPALIVE_SOCKET_OPTIONS.append((socket.IPPROTO_TCP, _kc, _kv))


def _apply_win_keepalive(sock):
    if sys.platform != "win32" or sock is None:
        return
    sio = getattr(socket, "SIO_KEEPALIVE_VALS", None)
    if sio is None:
        return
    try:
        sock.ioctl(sio, (1, 30000, 30000))
    except OSError:
        pass


if _URLLIB3_OK:
    class _KeepaliveHTTPConnection(_Urllib3HTTPConnection):
        def connect(self):
            super().connect()
            _apply_win_keepalive(self.sock)

    class _KeepaliveHTTPSConnection(_Urllib3HTTPSConnection):
        def connect(self):
            super().connect()
            _apply_win_keepalive(self.sock)

    class _KeepaliveHTTPConnectionPool(_Urllib3HTTPConnectionPool):
        ConnectionCls = _KeepaliveHTTPConnection

    class _KeepaliveHTTPSConnectionPool(_Urllib3HTTPSConnectionPool):
        ConnectionCls = _KeepaliveHTTPSConnection


class KeepaliveHTTPAdapter(HTTPAdapter):
    """长任务防 NAT 中断：开启 TCP keepalive。

    Why: gpt-image-2 单次绘图常需 5 分钟以上，TCP 在此期间无数据流动，
    国内 NAT/CGNAT 表项 5–10 分钟无活动会被清掉；本地不开 keepalive 时
    系统不会探测，requests 会一直等到 read timeout 才报错，表现为
    「中转站后台已出图但本地没收到」。开 keepalive 后内核每 30s 探测一次，
    既保活又能在被掐断时立刻抛 ConnectionError 而不是傻等到 600s。
    """

    def init_poolmanager(self, *args, **kwargs):
        kwargs["socket_options"] = list(_KEEPALIVE_SOCKET_OPTIONS)
        super().init_poolmanager(*args, **kwargs)
        if not _URLLIB3_OK:
            return
        try:
            self.poolmanager.pool_classes_by_scheme = {
                "http": _KeepaliveHTTPConnectionPool,
                "https": _KeepaliveHTTPSConnectionPool,
            }
        except Exception:
            pass

from .tikpan_gpt_image_recovery import (
    get_with_retry,
    make_idempotency_key,
    safe_json_for_log,
    save_recovery_record,
    short_hash,
)
from .tikpan_node_options import API_HOST_OPTIONS, normalize_api_host, BACKGROUND_OPTIONS, QUALITY_OPTIONS, option_value

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_HOST = "https://tikpan.com"

MODEL_OPTIONS = ["gpt-image-2"]
MODERATION_OPTIONS = ["auto", "low"]
SIZE_OPTIONS = ["Auto", "1024x1024", "1536x1024", "1024x1536", "2048x2048", "2048x1152", "1152x2048", "3840x2160", "2160x3840"]
SIZE_BY_TIER_ASPECT = {
    ("1K", "1:1"): "1024x1024",
    ("1K", "16:9"): "1536x1024",
    ("1K", "9:16"): "1024x1536",
    ("2K", "1:1"): "2048x2048",
    ("2K", "16:9"): "2048x1152",
    ("2K", "9:16"): "1152x2048",
    ("4K", "1:1"): "2880x2880",
    ("4K", "16:9"): "3840x2160",
    ("4K", "9:16"): "2160x3840",
}


class TikpanGptImage2OfficialEditV2:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "💎_源头拿货价福利_💎": (["🔥 0.6元RMB兑1美元余额全网底价"],),
                "获取密钥请访问": (["👉 https://tikpan.com 官方授权获取Key"],),
                "API_密钥": ("STRING", {"default": "sk-", "tooltip": "Tikpan 平台的 API 密钥，以 sk- 开头，从 https://tikpan.com 获取"}),
                "主图像": ("IMAGE", {"tooltip": "要被编辑的原始图像（必填）"}),
                "编辑指令": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "请根据要求编辑图像；如果提供了遮罩，仅修改遮罩区域并尽量保持未遮罩区域不变。",
                        "tooltip": "告诉 AI 怎么改图，例如『把背景换成海边』『增加一只猫』。如果上传了遮罩，仅修改遮罩区域。",
                    },
                ),
                "生成张数": ("INT", {"default": 1, "min": 1, "max": 10, "step": 1, "tooltip": "一次生成几张结果；张数越多越慢越贵"}),
                "分辨率档位": (["Auto", "1K", "2K", "4K"], {"default": "2K", "tooltip": "结果分辨率：Auto 跟随主图；档位越高越清晰但更慢更贵"}),
                "画面比例": (
                    ["Auto", "1:1", "16:9", "9:16", "4:3", "3:4", "21:9", "9:21"],
                    {"default": "Auto", "tooltip": "结果比例：Auto 跟随主图；选定后会缩放/补边到目标比例"},
                ),
                "尺寸": (SIZE_OPTIONS, {"default": "Auto", "tooltip": "强制指定输出尺寸（覆盖档位+比例）；一般选 Auto 由前两项决定"}),
                "画质": (QUALITY_OPTIONS, {"default": "均衡质量｜medium", "tooltip": "low=快且省钱；medium=日常推荐；high=精细但更慢更贵"}),
                "背景模式": (BACKGROUND_OPTIONS, {"default": "自动背景｜auto", "tooltip": "auto=由模型决定；opaque=不透明；transparent=透明背景（PNG）"}),
                "审核等级": (MODERATION_OPTIONS, {"default": "auto", "tooltip": "内容审核严格度：auto=默认；low=宽松"}),
                "遮罩反相": ("BOOLEAN", {"default": False, "tooltip": "开启后把遮罩的黑白对调（让原本要保留的变成要编辑的）"}),
                "提示增强": ("BOOLEAN", {"default": True, "tooltip": "开启后会自动给指令加补充描述，提升画面质量"}),
                "并发请求数": ("INT", {"default": 2, "min": 1, "max": 4, "step": 1, "tooltip": "同时发起的请求数；越大越快但更容易触发频率限制"}),
                "超时秒数": ("INT", {"default": 600, "min": 30, "max": 1800, "step": 10, "tooltip": "等待单次出图的最长秒数；4K/复杂场景建议加大"}),
            },
            "optional": {
                "中转站地址": (API_HOST_OPTIONS, {"default": API_HOST_OPTIONS[0], "tooltip": "Tikpan 中转站地址，一般保持默认即可"}),
                **{f"参考图{i}": ("IMAGE", {"tooltip": f"参考图 {i}：模型会基于这些图片作为视觉参考"}) for i in range(1, 16)},
                "参考流": ("IMAGE", {"tooltip": "批量参考图（接入一个 IMAGE 批次即可）"}),
                "遮罩掩码": ("MASK", {"tooltip": "可选遮罩：白色区域=要重绘，黑色区域=保持不变"}),
                "跳过错误": ("BOOLEAN", {"default": False, "tooltip": "开启后异常时返回黑图，不打断后续工作流"}),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("编辑结果", "渲染日志")
    FUNCTION = "edit_image"
    CATEGORY = '👑 Tikpan 官方独家节点/01 图片 Image'
    DESCRIPTION = "📝 GPT-Image-2 官方修图 V2：批量并发修图引擎，最多 15 张参考图 + 主图 + 遮罩，支持 4K、断线保活、幂等键、错误恢复。商业项目首选。"

    def edit_image(self, **kwargs):
        start_time = time.time()
        w, h = 1024, 1024
        skip_error = bool(kwargs.get("跳过错误", False))

        try:
            api_key = str(kwargs.get("API_密钥", "")).strip()
            api_host = normalize_api_host(kwargs.get("中转站地址", API_HOST_OPTIONS[0]))
            if not api_key or not api_key.startswith("sk-"):
                return (self.black_out(), "❌ API Key 格式错误")

            main_img = kwargs.get("主图像")
            if main_img is None:
                return (self.black_out(), "❌ 请提供主图像")

            mask_t = kwargs.get("遮罩掩码")
            prompt = str(kwargs.get("编辑指令") or "").strip()
            n = int(kwargs.get("生成张数", 1))
            res_tier = kwargs.get("分辨率档位", "2K")
            aspect = kwargs.get("画面比例", "Auto")
            size_option = kwargs.get("尺寸", "Auto")
            quality = option_value(kwargs.get("画质", "均衡质量｜medium"), "medium")
            bg = option_value(kwargs.get("背景模式", "自动背景｜auto"), "auto")
            moderation = kwargs.get("审核等级", "auto")
            if bg == "transparent":
                bg = "auto"
            invert_mask = bool(kwargs.get("遮罩反相", False))
            boost_prompt = bool(kwargs.get("提示增强", True))
            max_workers = max(1, min(int(kwargs.get("并发请求数", 2) or 2), max(1, min(n, 4))))
            timeout = int(kwargs.get("超时秒数", 600))

            self.validate_image_tensor(main_img, "主图像")
            w, h, size_label = self.compute_size(main_img, res_tier, aspect, size_option)
            main_pil = self.to_pil(main_img[0])

            ref_inputs = [kwargs.get(f"参考图{i}") for i in range(1, 16)]

            ref_pils = []
            for idx, ref in enumerate(ref_inputs, start=1):
                if ref is not None:
                    self.validate_image_tensor(ref, f"参考图{idx}")
                    ref_pils.extend(self.batch_to_pil(ref))

            ref_stream = kwargs.get("参考流")
            ref_stream_pils = []
            if ref_stream is not None:
                self.validate_image_tensor(ref_stream, "参考流")
                ref_stream_pils.extend(self.batch_to_pil(ref_stream))

            extra_refs = ref_pils + ref_stream_pils
            extra_refs = extra_refs[:15]
            all_pils = [main_pil] + extra_refs
            all_pils = all_pils[:16]

            files = []
            total_bytes = 0

            for i, p in enumerate(all_pils):
                prepared = self.fit_with_padding(p, w, h, bg=(255, 255, 255))
                img_bytes = self.to_bytes(prepared)
                total_bytes += len(img_bytes)
                files.append(("image", (f"{i}.png", img_bytes, "image/png")))

            has_mask = mask_t is not None
            if has_mask:
                self.validate_mask_tensor(mask_t, "遮罩掩码")
                mask_bytes = self.process_mask_with_main_geometry(
                    mask_t=mask_t,
                    main_pil=main_pil,
                    target_w=w,
                    target_h=h,
                    invert=invert_mask,
                )
                total_bytes += len(mask_bytes)
                files.append(("mask", ("mask.png", mask_bytes, "image/png")))

            if total_bytes > 50 * 1024 * 1024:
                raise Exception(f"上传图片总大小 {total_bytes / 1024 / 1024:.2f}MB 超过50MB")

            final_prompt = self.make_prompt(prompt, has_mask, boost_prompt)

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
            }

            data = {
                "model": "gpt-image-2",
                "prompt": final_prompt,
                "n": "1",
                "quality": quality,
                "size": size_label,
                "background": bg,
                "moderation": moderation,
            }
            content_hasher = hashlib.sha256()
            for _field, (_name, blob, _mime) in files:
                content_hasher.update(blob)
                content_hasher.update(b"|")
            files_hash = content_hasher.hexdigest()[:16]
            imgs = []
            saved_paths = []
            failed_items = []
            failed_reports = []
            successful_requests = 0
            recovery_keys = []
            response_count = 0
            timing_items = []
            preprocess_elapsed = round(time.time() - start_time, 2)
            with requests.Session() as sess:
                sess.trust_env = False
                sess.proxies = {"http": None, "https": None}

                get_retry = Retry(
                    total=2,
                    connect=2,
                    read=2,
                    backoff_factor=1,
                    status_forcelist=[500, 502, 503, 504],
                    allowed_methods=frozenset(["GET"]),
                    raise_on_status=False,
                )
                adapter = KeepaliveHTTPAdapter(max_retries=get_retry)
                sess.mount("https://", adapter)
                sess.mount("http://", adapter)

                job_specs = []
                for request_index in range(max(1, n)):
                    loop_data = dict(data)
                    idempotency_payload = dict(loop_data)
                    idempotency_payload["request_index"] = request_index + 1
                    idempotency_key = make_idempotency_key("images/edits", idempotency_payload, files_hash)
                    loop_headers = dict(headers)
                    loop_headers["Idempotency-Key"] = idempotency_key
                    recovery_keys.append(idempotency_key)
                    job_specs.append((request_index + 1, loop_headers, loop_data, idempotency_key, idempotency_payload))
                    save_recovery_record(
                        "official_edit_v2",
                        idempotency_key,
                        "pending",
                        endpoint="/v1/images/edits",
                        payload_hash=short_hash(idempotency_payload),
                        files_hash=files_hash,
                        size=size_label,
                    )

                def run_one_request(spec):
                    request_no, loop_headers, loop_data, idempotency_key, _idempotency_payload = spec
                    local_session = self.create_download_session()
                    request_start = time.time()
                    resj = self.post_edit_once(local_session, api_host, loop_headers, files, loop_data, timeout, idempotency_key, files_hash)
                    post_elapsed = round(time.time() - request_start, 2)
                    parse_start = time.time()
                    parsed, paths, errors = self.parse_images(resj, local_session, idempotency_key, request_no)
                    parse_elapsed = round(time.time() - parse_start, 2)
                    timing = {
                        "request_index": request_no,
                        "post_wait_seconds": post_elapsed,
                        "download_parse_save_seconds": parse_elapsed,
                        "request_total_seconds": round(time.time() - request_start, 2),
                    }
                    return request_no, idempotency_key, parsed, paths, errors, timing

                if max_workers == 1:
                    iterator = ((spec, None) for spec in job_specs)
                    for spec, _future in iterator:
                        request_no, _headers, _data, idempotency_key, _payload = spec
                        if len(imgs) >= n:
                            break
                        try:
                            request_no, idempotency_key, parsed, paths, errors, timing = run_one_request(spec)
                            response_count += 1
                            timing_items.append(timing)
                            imgs.extend(parsed)
                            saved_paths.extend(paths)
                            if parsed:
                                successful_requests += 1
                            for error in errors:
                                failed_items.append({
                                    "request_index": request_no,
                                    "idempotency_key": idempotency_key,
                                    "stage": "parse_or_download",
                                    "reason": error,
                                    "recoverable": "maybe",
                                    "hint": "中转站已返回响应但本地解析或下载失败；recovery JSON 通常含完整 URL/Base64，可重跑节点或检查 recovery/gpt_image_2 目录。",
                                })
                            save_recovery_record(
                                "official_edit_v2",
                                idempotency_key,
                                "local_saved" if parsed else "parse_failed",
                                endpoint="/v1/images/edits",
                                saved_paths=paths,
                                parse_errors=errors,
                                parsed_count=len(parsed),
                            )
                        except Exception as e:
                            failure = {
                                "request_index": request_no,
                                "idempotency_key": idempotency_key,
                                "stage": "request_or_upstream_response",
                                "reason": str(e),
                                "recoverable": "maybe",
                                "hint": "请求已送达中转站但未拿到结果；为避免重复扣费节点不会自动重发。请到中转站后台核实是否已扣费，并联系客服协助查询/补图。",
                            }
                            failed_items.append(failure)
                            report_paths = self.save_failure_report(failure)
                            failed_reports.extend(report_paths)
                            save_recovery_record(
                                "official_edit_v2",
                                idempotency_key,
                                "request_failed_after_submit",
                                endpoint="/v1/images/edits",
                                error=str(e),
                                failure_report_paths=report_paths,
                            )
                            print(f"[Tikpan GPT-Image-2 Edit V2] 第 {request_no} 次请求失败，继续处理后续批次: {e}", flush=True)

                else:
                    with ThreadPoolExecutor(max_workers=max_workers) as executor:
                        future_map = {executor.submit(run_one_request, spec): spec for spec in job_specs}
                        for future in as_completed(future_map):
                            spec = future_map[future]
                            request_no, _headers, _data, idempotency_key, _payload = spec
                            try:
                                request_no, idempotency_key, parsed, paths, errors, timing = future.result()
                                response_count += 1
                                timing_items.append(timing)
                                imgs.extend(parsed)
                                saved_paths.extend(paths)
                                if parsed:
                                    successful_requests += 1
                                for error in errors:
                                    failed_items.append({
                                        "request_index": request_no,
                                        "idempotency_key": idempotency_key,
                                        "stage": "parse_or_download",
                                        "reason": error,
                                        "recoverable": "maybe",
                                        "hint": "中转站已返回响应但本地解析或下载失败；recovery JSON 通常含完整 URL/Base64，可重跑节点或检查 recovery/gpt_image_2 目录。",
                                    })
                                save_recovery_record(
                                    "official_edit_v2",
                                    idempotency_key,
                                    "local_saved" if parsed else "parse_failed",
                                    endpoint="/v1/images/edits",
                                    saved_paths=paths,
                                    parse_errors=errors,
                                    parsed_count=len(parsed),
                                )
                            except Exception as e:
                                failure = {
                                    "request_index": request_no,
                                    "idempotency_key": idempotency_key,
                                    "stage": "request_or_upstream_response",
                                    "reason": str(e),
                                    "recoverable": "maybe",
                                    "hint": "请求已送达中转站但未拿到结果；为避免重复扣费节点不会自动重发。请到中转站后台核实是否已扣费，并联系客服协助查询/补图。",
                                }
                                failed_items.append(failure)
                                report_paths = self.save_failure_report(failure)
                                failed_reports.extend(report_paths)
                                save_recovery_record(
                                    "official_edit_v2",
                                    idempotency_key,
                                    "request_failed_after_submit",
                                    endpoint="/v1/images/edits",
                                    error=str(e),
                                    failure_report_paths=report_paths,
                                )
                                print(f"[Tikpan GPT-Image-2 Edit V2] 第 {request_no} 次请求失败，继续处理后续批次: {e}", flush=True)



            if not imgs:
                raise Exception(
                    "❌ 未解析到有效结果图。若中转站已扣费，请联系中转站客服协助核实/补图；"
                    f"本次幂等键: {', '.join(recovery_keys)}；失败详情: {self.format_failures(failed_items[:6])}"
                )

            tensor_start = time.time()
            base_sz = imgs[0].size
            tlist = []
            for i, im in enumerate(imgs):
                try:
                    im = im.convert("RGB")
                    if im.size != base_sz:
                        im = im.resize(base_sz, Image.Resampling.LANCZOS)
                    arr = np.array(im).astype(np.float32) / 255.0
                    tlist.append(torch.from_numpy(arr))
                except Exception as e:
                    failure = {
                        "request_index": i + 1,
                        "idempotency_key": recovery_keys[i] if i < len(recovery_keys) else "",
                        "stage": "tensor_conversion",
                        "reason": str(e),
                        "recoverable": "yes",
                        "hint": "图片已先落盘，可直接打开成功文件路径；这里只是 ComfyUI Batch 转换失败。",
                    }
                    failed_items.append(failure)
                    failed_reports.extend(self.save_failure_report(failure))
                    continue

            if not tlist:
                raise Exception("❌ 未得到可用结果图")

            batch = torch.stack(tlist, dim=0)
            tensor_elapsed = round(time.time() - tensor_start, 2)
            total_elapsed = round(time.time() - start_time, 2)
            requested_count = max(1, n)
            success_count = len(tlist)
            failed_count = max(requested_count - success_count, len(failed_items))
            recovery_dir = Path(__file__).resolve().parents[1] / "recovery" / "gpt_image_2"

            log = (
                f"✅ 编辑完成 | 请求:{requested_count} | 成功:{success_count} | 失败:{failed_count} | "
                f"请求次数:{response_count} | "
                f"成功请求:{successful_requests} | "
                f"参考图:{len(ref_pils)} | "
                f"参考流:{len(ref_stream_pils)} | "
                f"遮罩:{'有' if has_mask else '无'} | "
                f"目标尺寸:{size_label} | "
                f"上传总大小:{total_bytes / 1024 / 1024:.2f}MB | "
                f"本地保存:{len(saved_paths)}个文件 | "
                f"调试日志目录:{recovery_dir} | "
                f"预处理:等比例缩放+补边"
            )
            if saved_paths:
                log += "\n\n📁 成功文件保存位置:\n" + "\n".join(saved_paths[:40])
            if failed_reports:
                log += "\n\n🧯 失败记录保存位置:\n" + "\n".join(failed_reports[:40])
            if failed_items:
                log += "\n\n⚠️ 失败原因与恢复建议:\n" + self.format_failures(failed_items[:20])
                log += (
                    "\n\n🔁 处理说明:\n"
                    "1. 只有 TCP 连不通（请求未发出）才会自动重试，避免重复扣费。\n"
                    "2. 请求已送达中转站后的超时/异常不会自动重发——请先到中转站后台确认是否已扣费，再决定是否重跑。\n"
                    "3. 如果是经常超时，建议：① 排查代理是否绕路（tikpan.com 是国内中转站，最好直连）；② 把节点上「超时秒数」调大；③ 联系中转站客服核实通道速度。"
                )
            if recovery_keys:
                log += "\n\n🧾 本次请求 Idempotency-Key（调试/客服反查用）:\n" + "\n".join(recovery_keys)
            return (batch, log)

        except Exception as e:
            tb = traceback.format_exc()
            msg = f"❌ 异常: {e}\n{tb}"
            if skip_error:
                return (self.black_out(w, h), msg)
            raise Exception(msg)

    def make_prompt(self, p, has_mask, boost):
        base = (p or "").strip()
        if not boost:
            return base
        if has_mask:
            return (
                base
                + " 仅修改遮罩指定区域。未遮罩区域的文字内容、行数、位置、排版、字体风格、主体、构图、颜色和细节必须尽量保持不变，不要改动未遮罩区域。"
            )
        return base + " 参考所有输入图像融合，但不要过度破坏主图主体结构。"

    def validate_image_tensor(self, img_t, name):
        if not hasattr(img_t, "shape"):
            raise Exception(f"{name} 不是有效图像张量")
        if len(img_t.shape) != 4:
            raise Exception(f"{name} 维度异常，应为 [B,H,W,C]")
        bs, h, w, c = img_t.shape
        if bs < 1:
            raise Exception(f"{name} batch 为空")
        if h < 1 or w < 1:
            raise Exception(f"{name} 尺寸异常：{w}x{h}")
        if c not in (3, 4):
            raise Exception(f"{name} 通道数异常：{c}")

    def validate_mask_tensor(self, mask_t, name):
        if not hasattr(mask_t, "shape"):
            raise Exception(f"{name} 不是有效遮罩张量")
        if len(mask_t.shape) not in (2, 3):
            raise Exception(f"{name} 维度异常，应为 [B,H,W] 或 [H,W]")

    def safe_text(self, text, max_len=200):
        text = "" if text is None else str(text)
        if len(text) > max_len:
            return text[:max_len] + "..."
        return text

    def post_edit_once(self, sess, api_host, headers, files, data, timeout, idempotency_key, files_hash):
        # 重试策略：只对 ConnectTimeout（请求未发出，0 扣费风险）做有限重试；
        # ReadTimeout/ConnectionError/HTTP 5xx 等"请求已送达上游"的错误一律不重试，
        # 避免在中转站未实现 Idempotency-Key 幂等缓存的情况下造成重复扣费。
        max_connect_attempts = 3
        connect_backoff = [3, 6]

        for attempt_index in range(1, max_connect_attempts + 1):
            try:
                resp = sess.post(
                    f"{api_host}/v1/images/edits",
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=(15, timeout),
                    verify=False,
                    proxies={"http": None, "https": None},
                )
                break
            except requests.exceptions.ConnectTimeout:
                if attempt_index < max_connect_attempts:
                    wait_s = connect_backoff[attempt_index - 1]
                    print(
                        f"[Tikpan GPT-Image-2 Edit V2] TCP 连接超时（第 {attempt_index}/{max_connect_attempts} 次，请求未发出，无扣费风险），{wait_s}s 后重连",
                        flush=True,
                    )
                    time.sleep(wait_s)
                    continue
                raise Exception("连接上游超时：本地网络无法在 15 秒内与中转站建立 TCP 连接，请检查网络或代理设置")
            except requests.exceptions.ReadTimeout:
                save_recovery_record(
                    "official_edit_v2",
                    idempotency_key,
                    "post_read_timeout",
                    endpoint="/v1/images/edits",
                    payload_hash=short_hash(data),
                    files_hash=files_hash,
                    error=f"ReadTimeout after {timeout}s",
                )
                raise Exception(
                    f"上游响应等待超时：请求已送达中转站，但 {timeout} 秒内未收到结果。"
                    f"为避免重复扣费，节点不会自动重发。建议先到中转站后台核实是否已扣费、能否补图，"
                    f"或在节点上把「超时秒数」调大后再手动重跑。本次幂等键：{idempotency_key}"
                )
            except requests.exceptions.ProxyError as e:
                raise Exception(f"代理连接异常：{e}（如开启了系统代理/TUN，请把 tikpan.com 加入直连规则）")
            except requests.exceptions.SSLError as e:
                raise Exception(f"TLS/SSL 握手异常：{e}")
            except requests.exceptions.ConnectionError as e:
                raise Exception(f"网络连接失败：{e}（请求可能已部分送达，为避免重复扣费不自动重试）")
            except requests.exceptions.RequestException as e:
                raise Exception(f"请求发送失败：{e}")

        if resp.status_code == 429:
            raise Exception("HTTP 429: 当前分组/通道限流或繁忙，请稍后再试，或切换更稳定的令牌分组")
        if resp.status_code == 401:
            raise Exception(f"HTTP 401: API Key 无效或鉴权失败。响应: {self.safe_text(resp.text)}")
        if resp.status_code == 403:
            raise Exception(f"HTTP 403: 当前令牌无权限访问该接口。响应: {self.safe_text(resp.text)}")
        if resp.status_code != 200:
            raise Exception(f"HTTP {resp.status_code}: {self.safe_text(resp.text)}")

        try:
            resj = resp.json()
        except Exception:
            raise Exception(f"接口返回不是合法 JSON：{self.safe_text(resp.text)}")

        save_recovery_record(
            "official_edit_v2",
            idempotency_key,
            "response_received",
            endpoint="/v1/images/edits",
            http_status=resp.status_code,
            response=safe_json_for_log(resj),
        )
        upstream_urls = self.extract_result_urls(resj)
        if upstream_urls:
            save_recovery_record(
                "official_edit_v2",
                idempotency_key,
                "image_pointer_received",
                endpoint="/v1/images/edits",
                image_urls=upstream_urls,
            )
        return resj

    def compute_size(self, img_t, tier, asp, size_option="Auto"):
        bs, h, w, c = img_t.shape
        explicit = str(size_option or "Auto").strip()
        if explicit and explicit != "Auto":
            ew, eh = self.parse_size_label(explicit)
            return ew, eh, f"{ew}x{eh}"

        if tier != "Auto" and asp in ("1:1", "16:9", "9:16"):
            mapped = SIZE_BY_TIER_ASPECT.get((tier, asp))
            if mapped:
                ew, eh = self.parse_size_label(mapped)
                return ew, eh, mapped

        if tier == "Auto":
            if asp == "Auto":
                ww, hh = self.legalize(w, h)
                return ww, hh, f"{ww}x{hh}"
            rw, rh = map(int, asp.split(":"))
            ratio = rw / rh
            pixels = max(1, w * h)
            hh = math.sqrt(pixels / ratio)
            ww = hh * ratio
            ww, hh = self.legalize(int(ww), int(hh))
            return ww, hh, f"{ww}x{hh}"

        ratio = (w / h) if asp == "Auto" else (int(asp.split(":")[0]) / int(asp.split(":")[1]))
        tgt = {"1K": 1048576, "2K": 4194304, "4K": 8294400}.get(tier, 4194304)

        hh = math.sqrt(tgt / ratio)
        ww = hh * ratio
        ww, hh = self.legalize(int(ww), int(hh))
        return ww, hh, f"{ww}x{hh}"

    def parse_size_label(self, size_label):
        try:
            w_text, h_text = str(size_label).lower().split("x", 1)
            w = int(w_text.strip())
            h = int(h_text.strip())
        except Exception as exc:
            raise Exception(f"尺寸格式非法：{size_label}") from exc
        lw, lh = self.legalize(w, h)
        if (lw, lh) != (w, h):
            raise Exception(f"尺寸不符合上游限制：{size_label}，建议选择尺寸下拉中的合法值")
        return w, h

    def legalize(self, w, h):
        w = max(16, int(round(w / 16) * 16))
        h = max(16, int(round(h / 16) * 16))

        if max(w, h) > 3840:
            sc = 3840 / max(w, h)
            w = int(w * sc)
            h = int(h * sc)
            w = max(16, int(round(w / 16) * 16))
            h = max(16, int(round(h / 16) * 16))

        long_side = max(w, h)
        short_side = min(w, h)
        if short_side > 0 and long_side / short_side > 3:
            if w > h:
                w = h * 3
            else:
                h = w * 3
            w = max(16, int(round(w / 16) * 16))
            h = max(16, int(round(h / 16) * 16))

        pixels = w * h
        if pixels < 655360:
            sc = (655360 / max(1, pixels)) ** 0.5
            w = int(w * sc)
            h = int(h * sc)
            w = max(16, int(round(w / 16) * 16))
            h = max(16, int(round(h / 16) * 16))

        if w * h > 8294400:
            sc = (8294400 / (w * h)) ** 0.5
            w = int(w * sc)
            h = int(h * sc)
            w = max(16, int(round(w / 16) * 16))
            h = max(16, int(round(h / 16) * 16))

        if max(w, h) > 3840:
            sc = 3840 / max(w, h)
            w = int(w * sc)
            h = int(h * sc)

        w = max(16, int(round(w / 16) * 16))
        h = max(16, int(round(h / 16) * 16))
        return w, h

    def get_fit_params(self, src_w, src_h, target_w, target_h):
        if src_w <= 0 or src_h <= 0:
            raise Exception(f"原图尺寸非法：{src_w}x{src_h}")
        if target_w <= 0 or target_h <= 0:
            raise Exception(f"目标尺寸非法：{target_w}x{target_h}")

        scale = min(target_w / src_w, target_h / src_h)
        new_w = max(1, int(round(src_w * scale)))
        new_h = max(1, int(round(src_h * scale)))
        x = (target_w - new_w) // 2
        y = (target_h - new_h) // 2
        return new_w, new_h, x, y

    def fit_with_padding(self, img, target_w, target_h, bg=(255, 255, 255)):
        img = img.convert("RGB")
        src_w, src_h = img.size
        new_w, new_h, x, y = self.get_fit_params(src_w, src_h, target_w, target_h)
        resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (target_w, target_h), bg)
        canvas.paste(resized, (x, y))
        return canvas

    def process_mask_with_main_geometry(self, mask_t, main_pil, target_w, target_h, invert=False):
        m_np = mask_t.detach().cpu().numpy()
        if len(m_np.shape) == 3:
            m_np = m_np[0]

        pil_mask = Image.fromarray(np.clip(m_np * 255, 0, 255).astype(np.uint8)).convert("L")

        src_w, src_h = main_pil.size
        new_w, new_h, x, y = self.get_fit_params(src_w, src_h, target_w, target_h)

        resized_mask = pil_mask.resize((new_w, new_h), Image.Resampling.LANCZOS)

        canvas_mask = Image.new("L", (target_w, target_h), 0)
        canvas_mask.paste(resized_mask, (x, y))

        alpha = canvas_mask if invert else ImageOps.invert(canvas_mask)

        rgba = Image.new("RGBA", (target_w, target_h), (255, 255, 255, 255))
        rgba.putalpha(alpha)
        return self.to_bytes(rgba)

    def to_bytes(self, p):
        b = BytesIO()
        p.save(b, "PNG")
        return b.getvalue()

    def to_pil(self, t):
        a = np.clip(t.cpu().numpy() * 255, 0, 255).astype(np.uint8)
        return Image.fromarray(a).convert("RGB")

    def batch_to_pil(self, b):
        if b is None:
            return []
        if len(b.shape) == 3:
            b = b.unsqueeze(0)
        return [self.to_pil(b[i]) for i in range(b.shape[0])]

    def create_download_session(self):
        session = requests.Session()
        session.trust_env = False
        session.proxies = {"http": None, "https": None}
        get_retry = Retry(
            total=2,
            connect=2,
            read=2,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=frozenset(["GET"]),
            raise_on_status=False,
        )
        adapter = KeepaliveHTTPAdapter(max_retries=get_retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def parse_images(self, resj, sess, idempotency_key="", request_index=1):
        out = []
        saved_paths = []
        errors = []
        seen = set()

        for item_index, (raw_type, raw_value) in enumerate(self.extract_image_items(resj), start=1):
            marker = (raw_type, raw_value)
            if marker in seen:
                continue
            seen.add(marker)
            b64 = raw_value if raw_type == "base64" else ""
            url = raw_value if raw_type == "url" else ""
            if b64:
                try:
                    b64_clean = "".join(str(b64).split("base64,")[-1].split())
                    image_bytes = base64.b64decode(b64_clean)
                    img = Image.open(BytesIO(image_bytes)).convert("RGB")
                    out.append(img)
                    saved_paths.extend(self.save_result_image(img, idempotency_key, request_index, item_index, source="base64"))
                except Exception as e:
                    msg = f"Base64 图片解析失败: {e}"
                    errors.append(msg)
                    print(msg, flush=True)
            elif url:
                try:
                    resp = get_with_retry(sess, url, timeout=(5, 90), verify=False, attempts=4)
                    img = Image.open(BytesIO(resp.content)).convert("RGB")
                    out.append(img)
                    saved_paths.extend(self.save_result_image(img, idempotency_key, request_index, item_index, source="url", source_url=url))
                except Exception as e:
                    msg = f"URL 图片下载失败 ({url}): {e}"
                    errors.append(msg)
                    print(msg, flush=True)
        return out, saved_paths, errors

    def save_result_image(self, img, idempotency_key, request_index, item_index, source="", source_url=""):
        safe_key = str(idempotency_key or f"request-{request_index}").replace(":", "_").replace("/", "_")
        stamp = time.strftime("%Y%m%d-%H%M%S")
        filename = f"tikpan_gpt_image_2_edit_v2_{stamp}_{request_index:02d}_{item_index:02d}_{safe_key[-8:]}.png"
        paths = []

        try:
            output_dir = Path(folder_paths.get_output_directory())
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / filename
            img.save(output_path, "PNG")
            paths.append(str(output_path))
        except Exception as e:
            print(f"ComfyUI output save failed: {e}", flush=True)

        save_recovery_record(
            "official_edit_v2",
            idempotency_key or safe_key,
            "image_saved",
            request_index=request_index,
            item_index=item_index,
            source=source,
            source_url=source_url,
            saved_paths=paths,
        )
        return paths

    def save_failure_report(self, failure):
        idempotency_key = str(failure.get("idempotency_key") or "unknown")
        request_index = int(failure.get("request_index") or 0)
        safe_key = idempotency_key.replace(":", "_").replace("/", "_")
        stamp = time.strftime("%Y%m%d-%H%M%S")
        base_name = f"failed_{stamp}_{request_index:02d}_{safe_key[-8:]}"
        failure_dir = Path(__file__).resolve().parents[1] / "recovery" / "gpt_image_2" / "failures"
        failure_dir.mkdir(parents=True, exist_ok=True)
        json_path = failure_dir / f"{base_name}.json"
        txt_path = failure_dir / f"{base_name}.txt"
        payload = {
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            **failure,
            "recovery_dir": str(Path(__file__).resolve().parents[1] / "recovery" / "gpt_image_2"),
        }
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        txt_path.write_text(
            "Tikpan GPT-Image-2 Edit V2 失败记录\n"
            f"时间: {payload['time']}\n"
            f"批次: {failure.get('request_index')}\n"
            f"幂等Key: {idempotency_key}\n"
            f"阶段: {failure.get('stage')}\n"
            f"失败原因: {failure.get('reason')}\n"
            f"处理建议: {failure.get('hint')}\n",
            encoding="utf-8",
        )
        return [str(json_path), str(txt_path)]

    def format_failures(self, failures):
        lines = []
        for item in failures:
            if isinstance(item, dict):
                lines.append(
                    f"- 第 {item.get('request_index', '?')} 次 | 阶段:{item.get('stage', 'unknown')} | "
                    f"可恢复:{item.get('recoverable', 'unknown')} | 原因:{item.get('reason', '')} | "
                    f"建议:{item.get('hint', '')} | Key:{item.get('idempotency_key', '')}"
                )
            else:
                lines.append(f"- {item}")
        return "\n".join(lines)

    def extract_result_urls(self, resj):
        return [value for raw_type, value in self.extract_image_items(resj) if raw_type == "url"]

    def extract_image_items(self, resj):
        items = []
        seen = set()

        def add(raw_type, value):
            if not isinstance(value, str):
                return
            value = value.strip()
            if not value:
                return
            if value.startswith(("http://", "https://")):
                raw_type = "url"
            elif value.startswith("data:image"):
                raw_type = "base64"
            marker = (raw_type, value)
            if marker in seen:
                return
            seen.add(marker)
            items.append(marker)

        def scan(obj):
            if isinstance(obj, str):
                text = obj.strip()
                for pattern in (
                    r"!\[[^\]]*\]\((https?://[^\s)]+)\)",
                    r"\[[^\]]*\]\((https?://[^\s)]+)\)",
                    r"(https?://[^\s)]+\.(?:png|jpg|jpeg|webp)(?:\?[^\s)]*)?)",
                    r"(https?://t\.filesystem\.site/[^\s)]+)",
                ):
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        add("url", match.group(1).strip().rstrip(".,;"))
                        return
                if text.startswith(("http://", "https://")):
                    add("url", text)
                elif text.startswith("data:image"):
                    add("base64", text)
                return
            if isinstance(obj, list):
                for item in obj:
                    scan(item)
                return
            if not isinstance(obj, dict):
                return

            for key in ("url", "image_url", "imageUrl"):
                add("url", obj.get(key))
            for key in ("b64_json", "image_base64", "base64", "image"):
                add("base64", obj.get(key))
            nested_image_url = obj.get("image_url")
            if isinstance(nested_image_url, dict):
                add("url", nested_image_url.get("url"))
            for key in ("message", "content"):
                scan(obj.get(key))

        if not isinstance(resj, dict):
            return items

        for key in ("data", "result", "output", "images", "choices"):
            scan(resj.get(key))
        scan(resj)
        return items

    def black_out(self, w=1024, h=1024):
        return torch.zeros((1, h, w, 3), dtype=torch.float32)
