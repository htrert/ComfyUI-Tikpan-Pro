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
                    ["chirp-v3-0", "chirp-v3-5", "chirp-v4", "chirp-v5", "chirp-fenix"],
                    {"default": "chirp-fenix"},
                ),
                "生成纯音乐": ("BOOLEAN", {"default": False}),
            },
            "optional": {
                "🎤_续写_歌曲ID": ("STRING", {"default": ""}),
                "⏱️_续写起始秒数": ("FLOAT", {"default": 0.0, "min": 0, "max": 600}),
                "🎭_歌手风格_PersonaID": ("STRING", {"default": ""}),
                "🎙️_歌手风格_参考音频ID": ("STRING", {"default": ""}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "STRING")
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
        尽量兼容多种返回结构，统一提取:
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
        candidates = [status_json]

        if isinstance(data_field, dict):
            candidates.append(data_field)
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

    def build_payload(self, mode, title, prompt, tags, mv, make_instrumental, continue_clip_id, continue_at, persona_id, artist_clip_id):
        payload = {
            "mv": mv,
            "make_instrumental": make_instrumental,
        }

        if mode == "灵感模式":
            payload["gpt_description_prompt"] = prompt
            payload["prompt"] = prompt
            payload["task"] = "generate"

        elif mode == "自定义模式":
            payload["title"] = self.normalize_title(title, "命中注定")
            payload["prompt"] = prompt
            payload["tags"] = tags if tags else "pop"
            payload["generation_type"] = "text"
            payload["task"] = "generate"

        elif mode == "续写模式":
            if not continue_clip_id:
                raise ValueError("续写模式需要提供歌曲ID")
            payload["title"] = self.normalize_title(title, "续写歌曲")
            payload["prompt"] = prompt
            payload["tags"] = tags if tags else "pop"
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
            payload["generation_type"] = "text"
            payload["persona_id"] = persona_id
            payload["artist_clip_id"] = artist_clip_id
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

    def generate_music(self, **kwargs):
        api_key = str(kwargs.get("API_密钥") or "").strip()
        mode = kwargs.get("🎵_生成模式", "自定义模式")
        title = str(kwargs.get("歌曲标题") or "").strip()
        prompt = str(kwargs.get("创作提示词") or "").strip()
        tags = str(kwargs.get("风格标签") or "").strip()
        mv = kwargs.get("模型版本", "chirp-fenix")
        make_instrumental = bool(kwargs.get("生成纯音乐", False))

        continue_clip_id = str(kwargs.get("🎤_续写_歌曲ID") or "").strip()
        continue_at = float(kwargs.get("⏱️_续写起始秒数") or 0.0)

        persona_id = str(kwargs.get("🎭_歌手风格_PersonaID") or "").strip()
        artist_clip_id = str(kwargs.get("🎙️_歌手风格_参考音频ID") or "").strip()

        pbar = comfy.utils.ProgressBar(100)

        if not api_key or api_key == "sk-":
            return ("", "", "", "", prompt, "", "❌ 错误：请填写有效的 API 密钥", "", "", tags, title)

        if not prompt:
            return ("", "", "", "", prompt, "", "❌ 错误：创作提示词不能为空", "", "", tags, title)

        print(f"[Tikpan-Suno] 🎵 启动音乐生成引擎 | 模式: {mode} | 模型: {mv}", flush=True)

        try:
            payload = self.build_payload(
                mode=mode,
                title=title,
                prompt=prompt,
                tags=tags,
                mv=mv,
                make_instrumental=make_instrumental,
                continue_clip_id=continue_clip_id,
                continue_at=continue_at,
                persona_id=persona_id,
                artist_clip_id=artist_clip_id,
            )
        except ValueError as e:
            return ("", "", "", "", prompt, "", f"❌ 错误：{str(e)}", "", "", tags, title)

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
                return ("", "", "", "", prompt, "", f"❌ HTTP {response.status_code}: {error_text}", "", "", tags, title)

            try:
                res_json = response.json()
            except Exception:
                return ("", "", "", "", prompt, "", f"❌ 提交接口返回非 JSON: {response.text[:500]}", "", "", tags, title)

            task_id = self.extract_task_id(res_json)

            if not task_id:
                print(f"[Tikpan-Suno] ❌ 任务创建失败：未获取到任务ID", flush=True)
                return ("", "", "", "", prompt, "", f"❌ 未获取到任务ID: {self.safe_json_text(res_json, 500)}", "", "", tags, title)

            print(f"[Tikpan-Suno] ✅ 任务创建成功！Task ID: {task_id}", flush=True)
            print(f"[Tikpan-Suno] ⏳ 开始轮询任务状态 (每5秒)...", flush=True)

            for poll_count in range(240):
                time.sleep(5)
                comfy.model_management.throw_exception_if_processing_interrupted()

                try:
                    status_response = session.get(
                        f"{API_BASE_URL}/suno/fetch?id={task_id}",
                        headers=headers,
                        timeout=(15, 30),
                        verify=False,
                    )

                    if status_response.status_code != 200:
                        print(f"[Tikpan-Suno] ⚠️ 查询状态失败: HTTP {status_response.status_code}", flush=True)
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
                            return ("", "", "", "", prompt, task_id, "❌ 未获取到音频数据", "", "", tags, title)

                        audio_url1 = ""
                        audio_url2 = ""
                        clip_id1 = ""
                        clip_id2 = ""
                        out_tags = tags

                        if len(clips) >= 1:
                            clip1 = clips[0]
                            if isinstance(clip1, dict):
                                audio_url1 = str(clip1.get("audio_url") or clip1.get("url") or "").strip()
                                clip_id1 = str(clip1.get("id") or clip1.get("clip_id") or "").strip()
                                out_tags = str(clip1.get("tags") or out_tags).strip()
                            elif isinstance(clip1, str):
                                audio_url1 = clip1.strip()

                        if len(clips) >= 2:
                            clip2 = clips[1]
                            if isinstance(clip2, dict):
                                audio_url2 = str(clip2.get("audio_url") or clip2.get("url") or "").strip()
                                clip_id2 = str(clip2.get("id") or clip2.get("clip_id") or "").strip()
                            elif isinstance(clip2, str):
                                audio_url2 = clip2.strip()

                        print(f"[Tikpan-Suno] 🔗 音频1地址: {audio_url1}", flush=True)
                        print(f"[Tikpan-Suno] 🔗 音频2地址: {audio_url2}", flush=True)

                        audio_path1 = self.download_audio(session, audio_url1, task_id, "1")
                        audio_path2 = self.download_audio(session, audio_url2, task_id, "2")

                        if audio_path1 or audio_path2:
                            log_text = (
                                f"✅ 音乐生成成功！\n"
                                f"📁 音频1: {audio_path1}\n"
                                f"📁 音频2: {audio_path2}\n"
                                f"💡 请用 LoadAudio 节点加载后连接 SaveAudio"
                            )
                        else:
                            log_text = f"⚠️ 音乐生成完成但下载失败，请查看上方日志 | Task ID: {task_id}"

                        print(f"[Tikpan-Suno] ✅ 音乐生成流程完成！", flush=True)

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
                            out_tags,
                            title,
                        )

                    # --- ✅ 优化点 1：补全失败状态处理分支 ---
                    elif state in ["failed", "error", "cancelled", "failure", "timeout"]:
                        error_msg = fail_reason if fail_reason else "未知服务端错误 (上游未返回具体原因)"
                        log_text = f"❌ 音乐生成失败 | 状态: {state} | 原因: {error_msg}"
                        print(f"[Tikpan-Suno] {log_text}", flush=True)
                        return ("", "", "", "", prompt, task_id, log_text, "", "", tags, title)

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
            return ("", "", "", "", prompt, task_id, timeout_msg, "", "", tags, title)

        # --- ✅ 优化点 3：最外层抛出完整 Traceback，方便前端调试 ---
        except Exception as e:
            tb = traceback.format_exc()
            print(tb, flush=True)
            err_msg = f"❌ 节点运行期发生异常: {str(e)}\n{tb}"
            return ("", "", "", "", prompt, "", err_msg, "", "", tags, title)

# ====================== 节点注册 ======================
NODE_CLASS_MAPPINGS = {
    "TikpanSunoMusicNode": TikpanSunoMusicNode
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TikpanSunoMusicNode": "🎵 Tikpan: Suno 音乐生成"
}
