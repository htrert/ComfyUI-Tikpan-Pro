import json
import time

import comfy.model_management

from .tikpan_categories import CATEGORY_ASYNC_ENGINE
from .tikpan_async_task_engine import black_image, get_task, list_tasks, load_images_as_tensor, submit_image_task
from .tikpan_node_options import API_HOST_OPTIONS, RESPONSE_FORMAT_OPTIONS, normalize_api_host, option_value, pick


MODEL_OPTIONS = [
    "grok-imagine-image",
    "grok-imagine-image-pro",
    "gpt-image-2",
    "gpt-image-2-all",
    "doubao-seedream-5-0-260128",
]

SIZE_OPTIONS = ["1024x1024", "1792x1024", "1024x1792"]
WAIT_MODE_OPTIONS = ["return_now", "wait_until_done"]


def _task_json(task):
    return json.dumps(task or {}, ensure_ascii=False, indent=2)


def _task_log(task):
    if not task:
        return "Task not found."
    lines = [
        f"Task ID: {task.get('task_id', '')}",
        f"Status: {task.get('status', '')}",
        f"Stage: {task.get('stage', '')}",
        f"Progress: {task.get('progress', 0)}%",
    ]
    if task.get("error"):
        lines.append(f"Error: {task.get('error')}")
    lines.append("Events:")
    for item in task.get("events", []):
        lines.append(f"- [{item.get('status')}] {item.get('stage')}: {item.get('message')}")
    return "\n".join(lines)


class TikpanAsyncImageSubmitNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "API_Key": ("STRING", {"default": "sk-", "tooltip": "Tikpan 平台的 API 密钥，以 sk- 开头，从 https://tikpan.com 获取"}),
                "Prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "A cinematic commercial product image, precise details, realistic lighting.",
                        "tooltip": "提交给异步任务池的提示词",
                    },
                ),
                "Model": (MODEL_OPTIONS, {"default": "grok-imagine-image", "tooltip": "选择要异步出图的模型"}),
                "Relay_Host": (API_HOST_OPTIONS, {"default": API_HOST_OPTIONS[0], "tooltip": "Tikpan 中转站地址，一般保持默认即可"}),
                "Size": (SIZE_OPTIONS, {"default": "1024x1024", "tooltip": "出图尺寸"}),
                "Images": ("INT", {"default": 1, "min": 1, "max": 4, "tooltip": "本次任务生成几张"}),
            },
            "optional": {
                "Response_Format": (RESPONSE_FORMAT_OPTIONS, {"default": RESPONSE_FORMAT_OPTIONS[0], "tooltip": "url=云端链接（推荐）；b64_json=直接返回 Base64"}),
                "Timeout_Seconds": ("INT", {"default": 240, "min": 30, "max": 1800, "tooltip": "单任务超时秒数"}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("Task_ID", "Stage_Log", "Task_JSON")
    FUNCTION = "submit"
    CATEGORY = CATEGORY_ASYNC_ENGINE
    DESCRIPTION = "📝 异步提交图片任务：把生图请求推到本地任务池后立刻返回 Task_ID，不阻塞工作流。配合『异步查询』节点取结果。适合长时间任务、批量并行。"

    def submit(self, **kwargs):
        api_key = str(pick(kwargs, "API_Key", "api_key", default="") or "").strip()
        prompt = str(pick(kwargs, "Prompt", "prompt", default="") or "").strip()
        model = str(pick(kwargs, "Model", "model", default="grok-imagine-image") or "grok-imagine-image").strip()
        relay_host = normalize_api_host(pick(kwargs, "Relay_Host", "relay_host", default=API_HOST_OPTIONS[0]))
        size = str(pick(kwargs, "Size", "size", default="1024x1024") or "1024x1024").strip()
        images = int(pick(kwargs, "Images", "images", default=1) or 1)
        response_format = option_value(pick(kwargs, "Response_Format", "response_format", default=RESPONSE_FORMAT_OPTIONS[0]), "url")
        timeout_seconds = int(pick(kwargs, "Timeout_Seconds", "timeout_seconds", default=240) or 240)

        if not api_key or api_key == "sk-":
            task = {"status": "error", "stage": "user", "error": "API key is empty."}
            return ("", _task_log(task), _task_json(task))
        if not prompt:
            task = {"status": "error", "stage": "user", "error": "Prompt is empty."}
            return ("", _task_log(task), _task_json(task))

        payload = {
            "model": model,
            "relay_host": relay_host,
            "prompt": prompt,
            "size": size if size in SIZE_OPTIONS else "1024x1024",
            "n": max(1, min(images, 4)),
            "response_format": response_format if response_format in {"url", "b64_json"} else "url",
            "timeout_seconds": max(30, min(timeout_seconds, 1800)),
        }
        task_id = submit_image_task(api_key, payload)
        task = get_task(task_id)
        return (task_id, _task_log(task), _task_json(task))


class TikpanAsyncImageResultNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "Task_ID": ("STRING", {"default": "", "tooltip": "上一步『异步提交』返回的任务 ID"}),
                "Wait_Mode": (WAIT_MODE_OPTIONS, {"default": "return_now", "tooltip": "return_now=立刻返回当前状态；wait_until_done=阻塞等待出片"}),
                "Max_Wait_Seconds": ("INT", {"default": 600, "min": 0, "max": 3600, "tooltip": "wait_until_done 模式的最长等待秒数"}),
                "Poll_Interval_Seconds": ("INT", {"default": 3, "min": 1, "max": 60, "tooltip": "轮询任务状态的间隔秒数"}),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("Images", "Stage_Log", "Task_JSON", "Image_Paths")
    FUNCTION = "query"
    CATEGORY = CATEGORY_ASYNC_ENGINE
    DESCRIPTION = "📝 异步查询图片结果：根据 Task_ID 查询出图状态。可选立刻返回当前状态，或阻塞等待出图完成。"

    def query(self, **kwargs):
        task_id = str(pick(kwargs, "Task_ID", "task_id", default="") or "").strip()
        wait_mode = str(pick(kwargs, "Wait_Mode", "wait_mode", default="return_now") or "return_now")
        max_wait = int(pick(kwargs, "Max_Wait_Seconds", "max_wait_seconds", default=600) or 600)
        poll_interval = int(pick(kwargs, "Poll_Interval_Seconds", "poll_interval_seconds", default=3) or 3)

        task = self.wait_for_one(task_id, wait_mode, max_wait, poll_interval)
        if task and task.get("status") == "success" and task.get("image_paths"):
            return (
                load_images_as_tensor(task.get("image_paths", [])),
                _task_log(task),
                _task_json(task),
                "\n".join(task.get("image_paths", [])),
            )
        return (black_image(), _task_log(task), _task_json(task), "")

    def wait_for_one(self, task_id, wait_mode, max_wait, poll_interval):
        start = time.time()
        while True:
            comfy.model_management.throw_exception_if_processing_interrupted()
            task = get_task(task_id)
            if wait_mode != "wait_until_done":
                return task
            if task and task.get("status") in {"success", "error", "cancelled"}:
                return task
            if time.time() - start >= max_wait:
                return task or {"task_id": task_id, "status": "timeout", "stage": "server", "error": "Task wait timed out."}
            time.sleep(max(1, poll_interval))


class TikpanAsyncImageJoinNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "Task_ID_1": ("STRING", {"default": "", "tooltip": "必填的第 1 个任务 ID"}),
                "Wait_All": ("BOOLEAN", {"default": True, "tooltip": "True=等所有任务结束；False=任一成功即返回"}),
                "Max_Wait_Seconds": ("INT", {"default": 900, "min": 0, "max": 7200, "tooltip": "全部任务的最长等待秒数"}),
                "Poll_Interval_Seconds": ("INT", {"default": 3, "min": 1, "max": 60, "tooltip": "轮询任务状态的间隔秒数"}),
            },
            "optional": {
                "Task_ID_2": ("STRING", {"default": "", "tooltip": "可选第 2 个任务 ID"}),
                "Task_ID_3": ("STRING", {"default": "", "tooltip": "可选第 3 个任务 ID"}),
                "Task_ID_4": ("STRING", {"default": "", "tooltip": "可选第 4 个任务 ID"}),
                "Task_ID_5": ("STRING", {"default": "", "tooltip": "可选第 5 个任务 ID"}),
                "Task_ID_6": ("STRING", {"default": "", "tooltip": "可选第 6 个任务 ID"}),
                "Task_ID_7": ("STRING", {"default": "", "tooltip": "可选第 7 个任务 ID"}),
                "Task_ID_8": ("STRING", {"default": "", "tooltip": "可选第 8 个任务 ID"}),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("Images", "Stage_Log", "Tasks_JSON", "Image_Paths")
    FUNCTION = "join"
    CATEGORY = CATEGORY_ASYNC_ENGINE
    DESCRIPTION = "📝 合并异步图片任务：最多输入 8 个 Task_ID，等待全部完成（或任一成功）后合并所有图片到一个 IMAGE 批次。适合多任务并行后汇总。"

    def join(self, **kwargs):
        task_ids = []
        for index in range(1, 9):
            value = str(pick(kwargs, f"Task_ID_{index}", f"task_id_{index}", default="") or "").strip()
            if value:
                task_ids.append(value)

        wait_all = bool(pick(kwargs, "Wait_All", "wait_all", default=True))
        max_wait = int(pick(kwargs, "Max_Wait_Seconds", "max_wait_seconds", default=900) or 900)
        poll_interval = int(pick(kwargs, "Poll_Interval_Seconds", "poll_interval_seconds", default=3) or 3)

        tasks = self.wait_for_tasks(task_ids, wait_all, max_wait, poll_interval)
        image_paths = []
        for task in tasks:
            if task and task.get("status") == "success":
                image_paths.extend(task.get("image_paths", []))

        if image_paths:
            image_batch = load_images_as_tensor(image_paths)
        else:
            image_batch = black_image()

        lines = [
            f"Joined tasks: {len(task_ids)}",
            f"Success: {sum(1 for task in tasks if task and task.get('status') == 'success')}",
            f"Error: {sum(1 for task in tasks if task and task.get('status') == 'error')}",
            f"Running: {sum(1 for task in tasks if task and task.get('status') in {'queued', 'running'})}",
        ]
        for task in tasks:
            lines.append("")
            lines.append(_task_log(task))
        return (image_batch, "\n".join(lines), json.dumps(tasks, ensure_ascii=False, indent=2), "\n".join(image_paths))

    def wait_for_tasks(self, task_ids, wait_all, max_wait, poll_interval):
        start = time.time()
        while True:
            comfy.model_management.throw_exception_if_processing_interrupted()
            tasks = [get_task(task_id) for task_id in task_ids]
            terminal = [task for task in tasks if task and task.get("status") in {"success", "error", "cancelled"}]
            success = [task for task in tasks if task and task.get("status") == "success"]
            if wait_all and len(terminal) >= len(task_ids):
                return tasks
            if not wait_all and success:
                return tasks
            if time.time() - start >= max_wait:
                return tasks
            time.sleep(max(1, poll_interval))


class TikpanAsyncTaskListNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "Limit": ("INT", {"default": 20, "min": 1, "max": 200, "tooltip": "返回最近 N 个任务"}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("Tasks_JSON",)
    FUNCTION = "list_recent"
    CATEGORY = CATEGORY_ASYNC_ENGINE
    DESCRIPTION = "📝 最近异步任务列表：返回最近 N 个异步任务的元数据 JSON（状态/参数/结果）。用于查看历史、断线恢复、调试。"

    def list_recent(self, **kwargs):
        limit = int(pick(kwargs, "Limit", "limit", default=20) or 20)
        return (json.dumps(list_tasks(limit), ensure_ascii=False, indent=2),)
