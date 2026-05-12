import json
import time
import os
import base64
import requests
import urllib3
import folder_paths
import numpy as np
from io import BytesIO
from PIL import Image

import comfy.utils
import comfy.model_management
from .tikpan_happyhorse_common import (
    extract_task_status,
    extract_video_url,
    is_failure_status,
    is_success_status,
    video_from_path,
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 🔐 依然是咱们的官方地址
HARDCODED_BASE_URL = "https://tikpan.com"
VEO_MODEL_OPTIONS = [
    "veo_3_1-lite",
    "veo_3_1-lite-4K",
    "veo_3_1-fast-4K",
    "veo3.1-fast-components",
    "veo3.1-pro",
    "veo_3_1-components-4K",
    "veo_3_1-fast-components-4K",
]
VEO_CREATE_ENDPOINT_MODELS = {"veo3.1-fast-components", "veo3.1-pro"}
VEO_REFERENCE_IMAGE_MODELS = {
    "veo3.1-fast-components",
    "veo_3_1-components-4K",
    "veo_3_1-fast-components-4K",
}

class TikpanVeoVideoNode:
    @classmethod
    def INPUT_TYPES(cls):
        inputs = {
            "required": {
                "获取密钥请访问": (["👉 https://tikpan.com (官方授权Key获取点)"], ),
                "API_密钥": ("STRING", {"default": "sk-"}),
                "Veo专属提示词": ("STRING", {"multiline": True, "default": "请在此直接输入您的视频提示词..."}),
                "模型选择": (VEO_MODEL_OPTIONS, {"default": "veo_3_1-lite"}),
                "比例": (["16:9", "9:16"], {"default": "16:9"}),
                "seed": ("INT", {"default": 888888, "min": 0, "max": 0xffffffffffffffff}),
            },
            "optional": {}
        }
        
        inputs["optional"]["参考图_首帧"] = ("IMAGE",)
        inputs["optional"]["参考图_尾帧"] = ("IMAGE",)
        for i in range(1, 4):
            inputs["optional"][f"垫图_{i}"] = ("IMAGE",)
        inputs["optional"]["校验HTTPS证书"] = ("BOOLEAN", {"default": True})
            
        return inputs

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "VIDEO")
    RETURN_NAMES = ("📁_本地保存路径", "🏷️_任务ID", "🔗_视频云端直链", "📄_完整日志", "🎬_视频输出")
    OUTPUT_NODE = True 
    FUNCTION = "execute"
    CATEGORY = "👑 Tikpan 官方独家节点"

    def execute(self, 获取密钥请访问, API_密钥, Veo专属提示词, 模型选择, 比例, seed, **kwargs):
        comfy.model_management.throw_exception_if_processing_interrupted()
        
        if not API_密钥 or len(API_密钥) < 10:
            return ("❌ 请填写API密钥", "无", "无", "请填写密钥", None)
        if 模型选择 not in VEO_MODEL_OPTIONS:
            return ("❌ 模型选择无效", "无", "无", f"不支持的模型: {模型选择}", None)
        verify_tls = bool(kwargs.get("校验HTTPS证书", True))

        # /v1/videos 使用 multipart form；/v1/video/create 使用项目内旧视频统一 JSON 格式。
        headers = {"Authorization": f"Bearer {API_密钥}"}
        session = requests.Session()
        session.trust_env = False

        # 🚀 重点2：不再转 Base64，而是提取纯粹的二进制文件流 (Bytes)
        def get_image_bytes(img_tensor):
            if img_tensor is None: return None
            i_arr = 255. * img_tensor[0].cpu().numpy()
            p_img = Image.fromarray(np.clip(i_arr, 0, 255).astype(np.uint8))
            buf = BytesIO()
            p_img.save(buf, format="JPEG", quality=85) 
            return buf.getvalue()

        def bytes_to_data_url(image_bytes):
            return "data:image/jpeg;base64," + base64.b64encode(image_bytes).decode("utf-8")

        first_frame_bytes = get_image_bytes(kwargs.get("参考图_首帧"))
        last_frame_bytes = get_image_bytes(kwargs.get("参考图_尾帧"))
        reference_images = [
            get_image_bytes(kwargs.get(f"垫图_{i}"))
            for i in range(1, 4)
            if kwargs.get(f"垫图_{i}") is not None
        ]
        if reference_images and 模型选择 not in VEO_REFERENCE_IMAGE_MODELS:
            return (
                "❌ 当前模型不支持三张垫图",
                "无",
                "无",
                f"{模型选择} 不支持垫图_1~3。请切换到 components 模型。",
                None,
            )

        # 🚀 重点3：把文本参数和文件参数分开打包 (data 放文本，files 放图片)
        form_data = {
            "model": 模型选择, 
            "prompt": Veo专属提示词, 
            "aspect_ratio": 比例,
            "seed": str(seed) # 表单要求全是字符串
        }
        endpoint_path = "/v1/video/create" if 模型选择 in VEO_CREATE_ENDPOINT_MODELS else "/v1/videos"
        
        form_files = []
        if first_frame_bytes:
            # 格式：("字段名", ("文件名", 文件二进制流, "MIME类型"))
            form_files.append(("image", ("first_frame.jpg", first_frame_bytes, "image/jpeg")))
        if last_frame_bytes:
            form_files.append(("image_end", ("last_frame.jpg", last_frame_bytes, "image/jpeg")))
        for idx, image_bytes in enumerate(reference_images, start=1):
            form_files.append(("images", (f"reference_{idx}.jpg", image_bytes, "image/jpeg")))

        try:
            if endpoint_path == "/v1/video/create":
                json_headers = {**headers, "Content-Type": "application/json"}
                payload = {
                    "model": 模型选择,
                    "prompt": Veo专属提示词,
                    "aspect_ratio": 比例,
                    "seed": seed,
                }
                if first_frame_bytes:
                    payload["image"] = bytes_to_data_url(first_frame_bytes)
                if last_frame_bytes:
                    payload["image_end"] = bytes_to_data_url(last_frame_bytes)
                if reference_images:
                    payload["images"] = [bytes_to_data_url(image_bytes) for image_bytes in reference_images]
                create_resp = session.post(
                    f"{HARDCODED_BASE_URL}{endpoint_path}",
                    json=payload,
                    headers=json_headers,
                    verify=verify_tls,
                    timeout=120,
                )
            else:
                create_resp = session.post(
                    f"{HARDCODED_BASE_URL}{endpoint_path}",
                    data=form_data,
                    files=form_files if form_files else None,
                    headers=headers,
                    verify=verify_tls,
                    timeout=120,
                )
            if create_resp.status_code >= 400:
                return (
                    "❌ 任务创建失败",
                    "无",
                    "无",
                    f"HTTP {create_resp.status_code}: {create_resp.text[:1000]}",
                    None,
                )
            res = create_resp.json()
            
            task_id = (
                res.get("id")
                or res.get("task_id")
                or res.get("taskId")
                or (res.get("data") if isinstance(res.get("data"), str) else None)
            )
            if isinstance(res.get("data"), dict):
                task_id = task_id or res["data"].get("id") or res["data"].get("task_id") or res["data"].get("taskId")

            direct_url = extract_video_url(res)
            
            if direct_url:
                video_url = direct_url
                task_id = task_id or "sync_task"
            elif not task_id: 
                return ("❌ 任务创建失败", "无", "无", json.dumps(res, ensure_ascii=False), None)
                
        except Exception as e:
            return (f"❌ 网络/表单错误: {e}", "无", "无", str(e), None)

        print(f"\n[Veo 3.1] 🚀 任务(表单模式)创建成功！模型: {模型选择} | 接口: {endpoint_path} | ID: {task_id}")
        pbar = comfy.utils.ProgressBar(100)
        video_url = direct_url if 'direct_url' in locals() and direct_url else ""
        final_data = res
        
        # 轮询状态
        if not video_url:
            wait_time = 0
            for _ in range(240):
                for _ in range(5):
                    time.sleep(1)
                    comfy.model_management.throw_exception_if_processing_interrupted()
                wait_time += 5

                try:
                    query_url = (
                        f"{HARDCODED_BASE_URL}/v1/video/query?id={task_id}"
                        if endpoint_path == "/v1/video/create"
                        else f"{HARDCODED_BASE_URL}/v1/videos/{task_id}"
                    )
                    status_resp = session.get(query_url, headers=headers, verify=verify_tls, timeout=30)
                    status_res = status_resp.json()
                    final_data = status_res
                    
                    if wait_time % 15 == 0:
                        print(f"[Veo 3.1] ⏳ 云端渲染中，请耐心等待... 模型: {模型选择} | 已耗时: {wait_time} 秒")

                    state = extract_task_status(status_res)
                    
                    if is_success_status(state):
                        pbar.update_absolute(100, 100)
                        print(f"[Veo 3.1] ✅ 渲染完成！总耗时: {wait_time} 秒")
                        video_url = extract_video_url(status_res)
                        break
                    elif is_failure_status(state):
                        return ("❌ 渲染失败", str(task_id), "无", json.dumps(status_res, ensure_ascii=False), None)
                except Exception as e:
                    print(f"[Veo 3.1] ⚠️ 查询状态遇到网络波动 (自动重试中): {e}")

        if not video_url:
            return ("⚠️ 轮询超时或未找到链接", str(task_id), "无", "请检查聚合站接口格式", None)

        comfy.model_management.throw_exception_if_processing_interrupted()
        print(f"[Veo 3.1] 📥 正在极速下载大片到本地...")
        try:
            response = requests.get(video_url, verify=verify_tls, timeout=600)
            if response.status_code >= 400:
                return (
                    f"❌ 下载失败: HTTP {response.status_code}",
                    str(task_id),
                    video_url,
                    f"下载地址返回 HTTP {response.status_code}: {response.text[:500]}",
                    None,
                )
            content_type = response.headers.get("Content-Type", "")
            if not response.content or len(response.content) < 1024:
                return (
                    "❌ 下载失败: 文件内容为空或过小",
                    str(task_id),
                    video_url,
                    f"Content-Type: {content_type} | bytes={len(response.content) if response.content else 0}",
                    None,
                )
            if "text/html" in content_type.lower() or response.content[:20].lstrip().lower().startswith(b"<!doctype"):
                return (
                    "❌ 下载失败: 直链返回的不是视频文件",
                    str(task_id),
                    video_url,
                    f"Content-Type: {content_type} | body={response.text[:500]}",
                    None,
                )
            safe_id = str(task_id).replace(":", "_")
            safe_model = str(模型选择).replace("/", "_").replace(":", "_")
            filename = f"Tikpan_Veo_{safe_model}_{safe_id}.mp4"
            out_dir = folder_paths.get_output_directory()
            path = os.path.join(out_dir, filename)
            
            with open(path, "wb") as f: f.write(response.content)
            video_output = video_from_path(path)
            log_text = (
                json.dumps(final_data, ensure_ascii=False, indent=2)
                + f"\n\n下载信息: Content-Type={content_type or 'unknown'} | bytes={len(response.content)} | path={path}"
            )
            if video_output is None:
                return (
                    path,
                    str(task_id),
                    video_url,
                    log_text + "\n\n⚠️ 本地文件已保存，但 ComfyUI VIDEO 对象创建失败。可直接使用本地路径或云端直链。",
                    None,
                )
            print(f"[Veo 3.1] 🎉 下载成功！路径: {path}\n")
            return (path, str(task_id), video_url, log_text, video_output)
        except Exception as e:
            return (f"❌ 下载失败: {e}", str(task_id), video_url, f"下载错误: {e}", None)
