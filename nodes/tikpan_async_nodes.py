import json
import time

import comfy.model_management

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
                "API_Key": ("STRING", {"default": "sk-"}),
                "Prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "A cinematic commercial product image, precise details, realistic lighting.",
                    },
                ),
                "Model": (MODEL_OPTIONS, {"default": "grok-imagine-image"}),
                "Relay_Host": (API_HOST_OPTIONS, {"default": API_HOST_OPTIONS[0]}),
                "Size": (SIZE_OPTIONS, {"default": "1024x1024"}),
                "Images": ("INT", {"default": 1, "min": 1, "max": 4}),
            },
            "optional": {
                "Response_Format": (RESPONSE_FORMAT_OPTIONS, {"default": RESPONSE_FORMAT_OPTIONS[0]}),
                "Timeout_Seconds": ("INT", {"default": 240, "min": 30, "max": 1800}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("Task_ID", "Stage_Log", "Task_JSON")
    FUNCTION = "submit"
    CATEGORY = '👑 Tikpan 官方独家节点/06 任务与并发 Tools/异步任务池 Async Engine'

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
                "Task_ID": ("STRING", {"default": ""}),
                "Wait_Mode": (WAIT_MODE_OPTIONS, {"default": "return_now"}),
                "Max_Wait_Seconds": ("INT", {"default": 600, "min": 0, "max": 3600}),
                "Poll_Interval_Seconds": ("INT", {"default": 3, "min": 1, "max": 60}),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("Images", "Stage_Log", "Task_JSON", "Image_Paths")
    FUNCTION = "query"
    CATEGORY = "👑 Tikpan 官方独家节点/异步任务池 Async Engine"

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
                "Task_ID_1": ("STRING", {"default": ""}),
                "Wait_All": ("BOOLEAN", {"default": True}),
                "Max_Wait_Seconds": ("INT", {"default": 900, "min": 0, "max": 7200}),
                "Poll_Interval_Seconds": ("INT", {"default": 3, "min": 1, "max": 60}),
            },
            "optional": {
                "Task_ID_2": ("STRING", {"default": ""}),
                "Task_ID_3": ("STRING", {"default": ""}),
                "Task_ID_4": ("STRING", {"default": ""}),
                "Task_ID_5": ("STRING", {"default": ""}),
                "Task_ID_6": ("STRING", {"default": ""}),
                "Task_ID_7": ("STRING", {"default": ""}),
                "Task_ID_8": ("STRING", {"default": ""}),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("Images", "Stage_Log", "Tasks_JSON", "Image_Paths")
    FUNCTION = "join"
    CATEGORY = "👑 Tikpan 官方独家节点/异步任务池 Async Engine"

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
                "Limit": ("INT", {"default": 20, "min": 1, "max": 200}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("Tasks_JSON",)
    FUNCTION = "list_recent"
    CATEGORY = "👑 Tikpan 官方独家节点/异步任务池 Async Engine"

    def list_recent(self, **kwargs):
        limit = int(pick(kwargs, "Limit", "limit", default=20) or 20)
        return (json.dumps(list_tasks(limit), ensure_ascii=False, indent=2),)
