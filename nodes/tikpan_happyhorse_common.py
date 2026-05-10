import os
import sys

try:
    from comfy_api.input_impl import VideoFromFile
except Exception:
    comfy_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    if comfy_root not in sys.path:
        sys.path.append(comfy_root)
    try:
        from comfy_api.input_impl import VideoFromFile
    except Exception:
        VideoFromFile = None


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def extract_task_output(res_json):
    data = _as_dict(res_json)
    output = data.get("output")
    if isinstance(output, dict):
        return output
    nested_data = data.get("data")
    if isinstance(nested_data, dict):
        nested_output = nested_data.get("output")
        if isinstance(nested_output, dict):
            return nested_output
        return nested_data
    return data


def extract_task_status(res_json):
    data = _as_dict(res_json)
    candidates = [
        extract_task_output(data),
        _as_dict(data.get("data")),
        data,
    ]
    for item in candidates:
        status = item.get("task_status") or item.get("status") or item.get("state")
        if status:
            return str(status).upper()
    return ""


def is_success_status(status):
    return str(status).upper() in {
        "SUCCEEDED",
        "SUCCESS",
        "COMPLETED",
        "COMPLETE",
        "DONE",
        "FINISHED",
    }


def is_failure_status(status):
    return str(status).upper() in {
        "FAILED",
        "FAIL",
        "ERROR",
        "CANCELED",
        "CANCELLED",
        "UNKNOWN",
        "TIMEOUT",
        "EXPIRED",
    }


def normalize_resolution(resolution):
    return {
        "720p": "720P",
        "1080p": "1080P",
    }.get(str(resolution), resolution)


def extract_error_message(output):
    data = _as_dict(output)
    return (
        data.get("message")
        or data.get("error")
        or data.get("error_message")
        or data.get("fail_reason")
        or data.get("failure_reason")
        or "未知错误"
    )


def _first_http_url_from(value, key_names):
    if isinstance(value, dict):
        for key in key_names:
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.startswith("http"):
                return candidate
        for child in value.values():
            found = _first_http_url_from(child, key_names)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _first_http_url_from(child, key_names)
            if found:
                return found
    return ""


def extract_video_url(res_json):
    data = _as_dict(res_json)
    key_names = (
        "video_url",
        "videoUrl",
        "url",
        "media_url",
        "file_url",
        "result_url",
        "output_url",
    )
    preferred_roots = [
        extract_task_output(data),
        _as_dict(extract_task_output(data).get("output")),
        _as_dict(data.get("data")),
        data.get("data") if isinstance(data.get("data"), list) else {},
        data,
    ]
    for root in preferred_roots:
        found = _first_http_url_from(root, key_names)
        if found:
            return found
    return ""


def video_from_path(path):
    if not path or not isinstance(path, str) or not os.path.exists(path):
        return None
    if VideoFromFile is None:
        return None
    return VideoFromFile(path)
