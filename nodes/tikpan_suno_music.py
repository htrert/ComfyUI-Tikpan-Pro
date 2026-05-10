import json
import time
import os
import traceback
import mimetypes

import requests
import urllib3
import folder_paths

import comfy.utils
import comfy.model_management

# 屏蔽 verify=False 告警
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 🔐 Tikpan 官方聚合站
API_BASE_URL = "https://tikpan.com/v1"


class TikpanSunoMusicNode:
    """
    🎵 Tikpan：Suno 音乐生成节点

    支持模式：
    - 灵感模式：只需描述，AI自动生成歌词
    - 自定义模式：完整歌词+标题+风格
    - 续写模式：基于已有歌曲继续创作
    - 歌手风格：模仿特定歌手风格创作
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "💰_福利_💰": (["🔥 0.6元RMB兑1虚拟美元余额 | 全网底价 👉 https://tikpan.com"],),
                "获取密钥请访问": (["👉 https://tikpan.com (官方授权Key获取点)"],),
                "API_密钥": ("STRING", {"default": "sk-"}),
                "🎵_生成模式": (["灵感模式", "自定义模式", "续写模式", "歌手风格"], {"default": "自定义模式"}),
                "歌曲标题": ("STRING", {"default": "命中注定"}),
                "创作提示词": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "写一首伤感的粤语情歌",
                    },
                ),
                "风格标签": ("STRING", {"default": "pop, romantic"}),
                "模型版本": (
                    ["chirp-v3-0", "chirp-v3-5", "chirp-v4", "chirp-auk", "chirp-v5", "chirp-fenix"],
                    {"default": "chirp-fenix"},
                ),
                "生成纯音乐": ("BOOLEAN", {"default": False}),
            },
            "optional": {
                "负面风格标签": ("STRING", {"default": ""}),
                "🎤_续写_歌曲ID": ("STRING", {"default": ""}),
                "⏱️_续写起始秒数": ("FLOAT", {"default": 0.0, "min": 0, "max": 600}),
                "🎭_歌手风格_PersonaID": ("STRING", {"default": ""}),
                "🎙️_歌手风格_参考音频ID": ("STRING", {"default": ""}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "AUDIO", "AUDIO")
    RETURN_NAMES = (
        "📁_音频路径1",
        "📁_音频路径2",
        "🔗_音频链接1",
        "🔗_音频链接2",
        "📝_创作提示词",
        "🆔_任务ID",
        "📄_状态信息",
        "🆔_片段ID1",
        "🆔_片段ID2",
        "🏷️_标签",
        "📋_歌曲标题",
        "🎧_音频流1",
        "🎧_音频流2",
    )
    OUTPUT_NODE = True
    FUNCTION = "generate_music"
    CATEGORY = "👑 Tikpan 官方独家节点"

    def safe_json_text(self, obj, max_len=800):
        try:
            s = json.dumps(obj, ensure_ascii=False)
        except Exception:
            s = str(obj)
        return s[:max_len] + ("..." if len(s) > max_len else "")

    def extract_task_id(self, res_json):
        if not isinstance(res_json, dict):
            return ""

        data_field = res_json.get("data")
        if isinstance(data_field, str):
            return data_field.strip()

        if isinstance(data_field, dict):
            return str(
                data_field.get("task_id")
                or data_field.get("id")
                or data_field.get("taskId")
                or ""
            ).strip()

        return str(
            res_json.get("task_id")
            or res_json.get("id")
            or res_json.get("taskId")
            or ""
        ).strip()

    def parse_status_payload(self, status_json):
        """
        兼容多种返回结构，统一提取:
        - state
        - clips
        - fail_reason
        """
        state = ""
        clips = []
        fail_reason = ""

        if not isinstance(status_json, dict):
            return state, clips, fail_reason

        data_field = status_json.get("data")

        # 🔑 关键修复：data 可能是数组（如 tikpan 中转站返回格式）
        if isinstance(data_field, list):
            clips = data_field
            if clips and isinstance(clips[0], dict):
                state = str(
                    clips[0].get("status")
                    or clips[0].get("state")
                    or ""
                ).lower().strip()
                fail_reason = str(
                    clips[0].get("error_message")
                    or clips[0].get("failReason")
                    or clips[0].get("msg")
                    or ""
                ).strip()
                nested_clips = clips[0].get("data")
                if isinstance(nested_clips, list):
                    clips = nested_clips
            return state, clips, fail_reason

        # 处理 data 是 dict 的情况。云雾 Task 对象里 data.data 才是真正的音乐数组。
        candidates = [status_json]

        if isinstance(data_field, dict):
            candidates.append(data_field)
            nested_data = data_field.get("data")
            if isinstance(nested_data, list):
                clips = nested_data
            elif isinstance(nested_data, dict):
                candidates.append(nested_data)
            response_field = data_field.get("response")
            if isinstance(response_field, dict):
                candidates.append(response_field)

        for obj in candidates:
            if not state:
                state = str(
                    obj.get("status")
                    or obj.get("state")
                    or obj.get("task_status")
                    or ""
                ).lower().strip()

            if not clips:
                maybe_clips = obj.get("clips") or obj.get("items") or []
                if isinstance(maybe_clips, list):
                    clips = maybe_clips

            if not fail_reason:
                fail_reason = str(
                    obj.get("failReason")
                    or obj.get("error")
                    or obj.get("message")
                    or ""
                ).strip()

        return state, clips, fail_reason

    def normalize_title(self, title, default_title="未命名歌曲"):
        title = str(title or "").strip()
        return title if title else default_title

    def build_payload(self, mode, title, prompt, tags, negative_tags, mv, make_instrumental, continue_clip_id, continue_at, persona_id, artist_clip_id):
        payload = {
            "mv": mv,
            "make_instrumental": make_instrumental,
        }

        if mode == "灵感模式":
            payload["gpt_description_prompt"] = prompt
            payload["prompt"] = prompt

        elif mode == "自定义模式":
            payload["title"] = self.normalize_title(title, "命中注定")
            payload["prompt"] = prompt
            payload["tags"] = tags if tags else "pop"
            payload["negative_tags"] = negative_tags
            payload["generation_type"] = "TEXT"

        elif mode == "续写模式":
            if not continue_clip_id:
                raise ValueError("续写模式需要提供歌曲ID")
            payload["title"] = self.normalize_title(title, "续写歌曲")
            payload["prompt"] = prompt
            payload["tags"] = tags if tags else "pop"
            payload["negative_tags"] = negative_tags
            payload["continue_clip_id"] = continue_clip_id
            payload["continue_at"] = continue_at
            payload["task"] = "extend"

        elif mode == "歌手风格":
            if not artist_clip_id:
                raise ValueError("歌手风格模式需要提供参考音频ID")
            if not persona_id:
                raise ValueError("歌手风格模式需要提供PersonaID")

            payload["title"] = self.normalize_title(title, "歌手风格歌曲")
            payload["prompt"] = prompt
            payload["tags"] = tags if tags else "pop"
            payload["negative_tags"] = negative_tags
            payload["generation_type"] = "TEXT"
            payload["persona_id"] = persona_id
            payload["artist_clip_id"] = artist_clip_id
            payload["vocal_gender"] = ""
            payload["task"] = "artist_consistency"

            tau_map = {
                "chirp-v3-0": "chirp-v3-0-tau",
                "chirp-v3-5": "chirp-v3-5-tau",
                "chirp-v4": "chirp-v4-tau",
                "chirp-v5": "chirp-v5-tau",
            }
            payload["mv"] = tau_map.get(mv, mv)

        else:
            raise ValueError(f"不支持的生成模式: {mode}")

        return payload

    def empty_audio(self):
        try:
            import torch
            return {"waveform": torch.zeros((1, 1, 1), dtype=torch.float32), "sample_rate": 44100}
        except Exception:
            return {"waveform": None, "sample_rate": 44100}

    def make_return(self, audio_path1="", audio_path2="", audio_url1="", audio_url2="", prompt="", task_id="", log_text="", clip_id1="", clip_id2="", tags="", title="", audio1=None, audio2=None):
        return (
            audio_path1,
            audio_path2,
            audio_url1,
            audio_url2,
            prompt,
            task_id,
            log_text,
            clip_id1,
            clip_id2,
            tags,
            title,
            audio1 if audio1 is not None else self.empty_audio(),
            audio2 if audio2 is not None else self.empty_audio(),
        )

    def get_audio_extension(self, url, response):
        content_type = str(response.headers.get("Content-Type", "")).lower()

        if "audio/mpeg" in content_type or "audio/mp3" in content_type:
            return ".mp3"
        if "audio/wav" in content_type or "audio/x-wav" in content_type:
            return ".wav"
        if "audio/mp4" in content_type or "audio/m4a" in content_type:
            return ".m4a"
        if "audio/flac" in content_type:
            return ".flac"
        if "audio/ogg" in content_type:
            return ".ogg"

        guessed_ext = os.path.splitext(str(url).split("?")[0])[1].strip()
        if guessed_ext and len(guessed_ext) <= 8:
            return guessed_ext

        mime_guess, _ = mimetypes.guess_type(str(url))
        if mime_guess:
            ext = mimetypes.guess_extension(mime_guess)
            if ext:
                return ext

        return ".mp3"

    def download_audio(self, session, url, task_id, index):
        if not url:
            return ""

        try:
            print(f"[Tikpan-Suno] 📥 正在下载音频{index}...", flush=True)
            audio_response = session.get(url, timeout=(15, 300), verify=False)
            audio_response.raise_for_status()

            safe_id = str(task_id).replace(":", "_").replace("/", "_")
            ext = self.get_audio_extension(url, audio_response)
            filename = f"Tikpan_Suno_{safe_id}_{index}{ext}"
            out_dir = folder_paths.get_output_directory()
            save_path = os.path.join(out_dir, filename)

            with open(save_path, "wb") as f:
                f.write(audio_response.content)

            print(f"[Tikpan-Suno] 💾 音频{index}已保存到: {save_path}", flush=True)
            return save_path

        except Exception as e:
            print(f"[Tikpan-Suno] ⚠️ 下载音频{index}失败: {e}", flush=True)
            return ""

    def audio_from_path(self, audio_path):
        if not audio_path or not os.path.exists(audio_path):
            return self.empty_audio()

        try:
            from comfy_extras.nodes_audio import load as load_audio_file
            waveform, sample_rate = load_audio_file(audio_path)
            return {"waveform": waveform.unsqueeze(0), "sample_rate": sample_rate}
        except Exception as e:
            print(f"[Tikpan-Suno] ⚠️ 音频流解码失败，只返回文件路径: {e}", flush=True)
            return self.empty_audio()

    def fetch_status(self, session, headers, task_id):
        fetch_urls = [
            f"{API_BASE_URL}/suno/fetch/{task_id}",
            f"{API_BASE_URL}/suno/fetch?id={task_id}",
        ]

        last_response = None
        for url in fetch_urls:
            response = session.get(
                url,
                headers=headers,
                timeout=(15, 30),
                verify=False,
            )
            last_response = response
            if response.status_code != 200:
                print(f"[Tikpan-Suno] ⚠️ 查询状态失败: HTTP {response.status_code} | URL: {url}", flush=True)
                continue
            try:
                status_json = response.json()
                state, clips, _ = self.parse_status_payload(status_json)
                if state or clips or status_json.get("code") == "success" or status_json.get("data") is not None:
                    return response
                print(f"[Tikpan-Suno] ⚠️ 查询地址无有效任务数据，尝试备用查询: {url}", flush=True)
            except Exception:
                return response

        response = session.post(
            f"{API_BASE_URL}/suno/fetch",
            json={"ids": [task_id]},
            headers=headers,
            timeout=(15, 30),
            verify=False,
        )
        last_response = response
        if response.status_code != 200:
            print(f"[Tikpan-Suno] ⚠️ 批量查询状态失败: HTTP {response.status_code}", flush=True)
        else:
            return response

        return last_response

    def extract_clip_audio(self, clip):
        if isinstance(clip, str):
            return clip.strip(), "", ""

        if not isinstance(clip, dict):
            return "", "", ""

        audio_url = str(
            clip.get("audio_url")
            or clip.get("audioUrl")
            or clip.get("stream_audio_url")
            or clip.get("source_audio_url")
            or clip.get("download_url")
            or clip.get("url")
            or ""
        ).strip()

        audio_field = clip.get("audio")
        if not audio_url and isinstance(audio_field, str):
            audio_url = audio_field.strip()
        elif not audio_url and isinstance(audio_field, dict):
            audio_url = str(audio_field.get("url") or audio_field.get("audio_url") or "").strip()

        clip_id = str(
            clip.get("id")
            or clip.get("clip_id")
            or clip.get("clipId")
            or ""
        ).strip()
        out_tags = str(clip.get("tags") or "").strip()
        return audio_url, clip_id, out_tags

    def generate_music(self, **kwargs):
        api_key = str(kwargs.get("API_密钥") or "").strip()
        mode = kwargs.get("🎵_生成模式", "自定义模式")
        title = str(kwargs.get("歌曲标题") or "").strip()
        prompt = str(kwargs.get("创作提示词") or "").strip()
        tags = str(kwargs.get("风格标签") or "").strip()
        negative_tags = str(kwargs.get("负面风格标签") or "").strip()
        mv = kwargs.get("模型版本", "chirp-fenix")
        make_instrumental = bool(kwargs.get("生成纯音乐", False))

        continue_clip_id = str(kwargs.get("🎤_续写_歌曲ID") or "").strip()
        continue_at = float(kwargs.get("⏱️_续写起始秒数") or 0.0)

        persona_id = str(kwargs.get("🎭_歌手风格_PersonaID") or "").strip()
        artist_clip_id = str(kwargs.get("🎙️_歌手风格_参考音频ID") or "").strip()

        pbar = comfy.utils.ProgressBar(100)

        if not api_key or api_key == "sk-":
            return self.make_return(prompt=prompt, log_text="❌ 错误：请填写有效的 API 密钥", tags=tags, title=title)

        if not prompt:
            return self.make_return(prompt=prompt, log_text="❌ 错误：创作提示词不能为空", tags=tags, title=title)

        print(f"[Tikpan-Suno] 🎵 启动音乐生成引擎 | 模式: {mode} | 模型: {mv}", flush=True)

        try:
            payload = self.build_payload(
                mode=mode,
                title=title,
                prompt=prompt,
                tags=tags,
                negative_tags=negative_tags,
                mv=mv,
                make_instrumental=make_instrumental,
                continue_clip_id=continue_clip_id,
                continue_at=continue_at,
                persona_id=persona_id,
                artist_clip_id=artist_clip_id,
            )
        except ValueError as e:
            return self.make_return(prompt=prompt, log_text=f"❌ 错误：{str(e)}", tags=tags, title=title)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Tikpan-ComfyUI-Suno/1.0",
        }

        session = requests.Session()
        session.trust_env = False

        try:
            pbar.update(5)
            print(f"[Tikpan-Suno] 📡 正在提交音乐生成任务...", flush=True)
            print(f"[Tikpan-Suno] 📋 请求参数: {self.safe_json_text(payload, 400)}", flush=True)

            response = session.post(
                f"{API_BASE_URL}/suno/submit/music",
                json=payload,
                headers=headers,
                timeout=(15, 60),
                verify=False,
            )

            pbar.update(10)

            if response.status_code != 200:
                error_text = response.text[:500]
                print(f"[Tikpan-Suno] ❌ 任务创建失败: HTTP {response.status_code} | {error_text}", flush=True)
                return self.make_return(prompt=prompt, log_text=f"❌ HTTP {response.status_code}: {error_text}", tags=tags, title=title)

            try:
                res_json = response.json()
            except Exception:
                return self.make_return(prompt=prompt, log_text=f"❌ 提交接口返回非 JSON: {response.text[:500]}", tags=tags, title=title)

            task_id = self.extract_task_id(res_json)

            if not task_id:
                print(f"[Tikpan-Suno] ❌ 任务创建失败：未获取到任务ID", flush=True)
                return self.make_return(prompt=prompt, log_text=f"❌ 未获取到任务ID: {self.safe_json_text(res_json, 500)}", tags=tags, title=title)

            print(f"[Tikpan-Suno] ✅ 任务创建成功！Task ID: {task_id}", flush=True)
            print(f"[Tikpan-Suno] ⏳ 开始轮询任务状态 (每5秒)...", flush=True)

            for poll_count in range(240):
                time.sleep(5)
                comfy.model_management.throw_exception_if_processing_interrupted()

                try:
                    status_response = self.fetch_status(session, headers, task_id)

                    if status_response is None or status_response.status_code != 200:
                        continue

                    try:
                        status_json = status_response.json()
                    except Exception:
                        print(f"[Tikpan-Suno] ⚠️ 查询返回非 JSON: {status_response.text[:500]}", flush=True)
                        continue

                    print(f"[Tikpan-Suno] 📦 查询响应: {self.safe_json_text(status_json, 600)}", flush=True)

                    state, clips, fail_reason = self.parse_status_payload(status_json)

                    progress_percent = min(10 + ((poll_count + 1) * 90) // 100, 95)
                    pbar.update(progress_percent)

                    print(f"[Tikpan-Suno] 🔄 轮询中... (第{poll_count + 1}次) | 状态: {state}", flush=True)

                    if state in ["success", "succeeded", "completed", "finished", "done"]:
                        pbar.update_absolute(100, 100)
                        print(f"[Tikpan-Suno] ✅ 音乐生成完成！正在处理音频...", flush=True)

                        if not clips:
                            print(f"[Tikpan-Suno] ❌ 任务完成但未获取到音频数据", flush=True)
                            return self.make_return(prompt=prompt, task_id=task_id, log_text="❌ 未获取到音频数据", tags=tags, title=title)

                        audio_url1 = ""
                        audio_url2 = ""
                        clip_id1 = ""
                        clip_id2 = ""
                        out_tags = tags

                        if len(clips) >= 1:
                            audio_url1, clip_id1, clip_tags = self.extract_clip_audio(clips[0])
                            out_tags = clip_tags or out_tags

                        if len(clips) >= 2:
                            audio_url2, clip_id2, _ = self.extract_clip_audio(clips[1])

                        print(f"[Tikpan-Suno] 🔗 音频1地址: {audio_url1}", flush=True)
                        print(f"[Tikpan-Suno] 🔗 音频2地址: {audio_url2}", flush=True)

                        audio_path1 = self.download_audio(session, audio_url1, task_id, "1")
                        audio_path2 = self.download_audio(session, audio_url2, task_id, "2")
                        audio1 = self.audio_from_path(audio_path1)
                        audio2 = self.audio_from_path(audio_path2)

                        if audio_path1 or audio_path2:
                            log_text = (
                                f"✅ 音乐生成成功！\n"
                                f"📁 音频1: {audio_path1}\n"
                                f"📁 音频2: {audio_path2}\n"
                                f"💡 已同时输出 AUDIO 音频流，可直接连接 PreviewAudio 或 SaveAudio"
                            )
                        else:
                            log_text = f"⚠️ 音乐生成完成但下载失败，请查看上方日志 | Task ID: {task_id}"

                        print(f"[Tikpan-Suno] ✅ 音乐生成流程完成！", flush=True)

                        return self.make_return(audio_path1, audio_path2, audio_url1, audio_url2, prompt, task_id, log_text, clip_id1, clip_id2, out_tags, title, audio1, audio2)

                    # --- ✅ 优化点 1：补全失败状态处理分支 ---
                    elif state in ["failed", "error", "cancelled", "failure", "timeout"]:
                        error_msg = fail_reason if fail_reason else "未知服务端错误 (上游未返回具体原因)"
                        log_text = f"❌ 音乐生成失败 | 状态: {state} | 原因: {error_msg}"
                        print(f"[Tikpan-Suno] {log_text}", flush=True)
                        return self.make_return(prompt=prompt, task_id=task_id, log_text=log_text, tags=tags, title=title)

                    # --- ✅ 优化点 2：显式增加处理中状态分支，提升日志可读性和稳定性 ---
                    elif state in ["not_start", "submitted", "queued", "pending", "in_progress", "processing", "running", "creating"]:
                        continue

                    # --- 兜底未知状态 ---
                    else:
                        print(f"[Tikpan-Suno] ⚠️ 未识别状态: {state} | 继续轮询", flush=True)
                        continue

                except Exception as e:
                    print(f"[Tikpan-Suno] ⚠️ 轮询单次执行发生错误: {e}", flush=True)

            timeout_msg = f"❌ 任务超时：经过 20 分钟轮询仍未完成 | Task ID: {task_id}"
            print(f"[Tikpan-Suno] {timeout_msg}", flush=True)
            return self.make_return(prompt=prompt, task_id=task_id, log_text=timeout_msg, tags=tags, title=title)

        # --- ✅ 优化点 3：最外层抛出完整 Traceback，方便前端调试 ---
        except Exception as e:
            tb = traceback.format_exc()
            print(tb, flush=True)
            err_msg = f"❌ 节点运行期发生异常: {str(e)}\n{tb}"
            return self.make_return(prompt=prompt, log_text=err_msg, tags=tags, title=title)

# ====================== 节点注册 ======================
NODE_CLASS_MAPPINGS = {
    "TikpanSunoMusicNode": TikpanSunoMusicNode
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TikpanSunoMusicNode": "🎵 Tikpan: Suno 音乐生成"
}
