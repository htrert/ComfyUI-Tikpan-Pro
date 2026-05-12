import importlib.util
import json
import sys
import types
from pathlib import Path
from tempfile import NamedTemporaryFile


ROOT = Path(__file__).resolve().parents[1]
NODE_PATH = ROOT / "nodes" / "tikpan_gpt5_mini_responses.py"


def install_comfy_stubs():
    comfy = types.ModuleType("comfy")
    model_management = types.ModuleType("comfy.model_management")
    utils = types.ModuleType("comfy.utils")
    model_management.throw_exception_if_processing_interrupted = lambda: None

    class ProgressBar:
        def __init__(self, *args, **kwargs):
            pass

        def update_absolute(self, *args, **kwargs):
            pass

    utils.ProgressBar = ProgressBar
    comfy.model_management = model_management
    comfy.utils = utils
    sys.modules["comfy"] = comfy
    sys.modules["comfy.model_management"] = model_management
    sys.modules["comfy.utils"] = utils


def load_node_module():
    install_comfy_stubs()
    spec = importlib.util.spec_from_file_location("gpt5_mini_responses_node", NODE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def find_key(keys, name):
    matches = [key for key in keys if name in key]
    assert matches, f"missing input key containing {name}"
    return matches[0]


def test_responses_payload_contract_and_hash():
    module = load_node_module()
    node = module.TikpanGPT5MiniResponsesNode()
    keys = list(node.INPUT_TYPES()["required"].keys()) + list(node.INPUT_TYPES()["optional"].keys())
    payload = node.build_payload(
        {
            find_key(keys, "用户问题"): "分析这张商品图，并输出 JSON。",
            find_key(keys, "输出格式"): "JSON结构化",
            find_key(keys, "图片URL"): "https://example.com/product.jpg",
            find_key(keys, "文件URL"): "https://example.com/spec.pdf",
            find_key(keys, "启用联网搜索"): True,
        }
    )

    content = payload["input"][0]["content"]
    assert payload["model"] == "gpt-5-mini"
    assert payload["reasoning"]["effort"] == "low"
    assert payload["text"]["format"]["type"] == "json_object"
    assert payload["tools"][0]["type"] == "web_search_preview"
    assert any(item.get("type") == "input_image" and item.get("image_url") == "https://example.com/product.jpg" for item in content)
    assert any(item.get("type") == "input_file" and item.get("file_url") == "https://example.com/spec.pdf" for item in content)
    assert node.payload_hash(payload) == node.payload_hash(payload)


def test_local_file_validation_text_extraction_and_usage():
    module = load_node_module()
    node = module.TikpanGPT5MiniResponsesNode()
    with NamedTemporaryFile(suffix=".txt", delete=False) as handle:
        handle.write(b"hello")
        handle.flush()
        path = handle.name
    try:
        part = node.local_file_part(path)
    finally:
        Path(path).unlink(missing_ok=True)
    assert part["type"] == "input_file"
    assert part["file_data"].startswith("data:text/plain;base64,")

    response = {
        "output": [{"content": [{"type": "output_text", "text": "answer text"}]}],
        "usage": {
            "input_tokens": 10,
            "output_tokens": 5,
            "total_tokens": 15,
            "input_tokens_details": {"cached_tokens": 2},
        },
    }
    assert node.extract_text(response) == "answer text"
    assert node.extract_usage(response) == "input=10 | output=5 | total=15 | cached=2"
    assert node.extract_finish_status({"status": "completed"}) == "completed"


def test_rejects_bad_url_and_oversized_local_file():
    module = load_node_module()
    node = module.TikpanGPT5MiniResponsesNode()
    keys = list(node.INPUT_TYPES()["required"].keys()) + list(node.INPUT_TYPES()["optional"].keys())

    try:
        node.build_payload({find_key(keys, "图片URL"): "ftp://bad.example/file.jpg"})
        raise AssertionError("invalid image URL should be rejected before request")
    except ValueError as exc:
        assert "URL" in str(exc)

    node._last_warnings = []
    urls = node.parse_url_lines("ftp://bad.example/file.jpg\nhttps://example.com/ok.jpg", skip_invalid=True, field_name="图片URL列表")
    assert urls == ["https://example.com/ok.jpg"]
    assert "跳过无效链接" in node._last_warnings[0]

    with NamedTemporaryFile(suffix=".pdf", delete=False) as handle:
        handle.truncate(module.MAX_FILE_INLINE_BYTES + 1)
        handle.flush()
        path = handle.name
    try:
        node.local_file_part(path)
        raise AssertionError("oversized file should be rejected before request")
    except ValueError as exc:
        assert "超过 inline" in str(exc)
    finally:
        Path(path).unlink(missing_ok=True)


def test_frame_sampling_strategies_are_bounded_and_annotated():
    module = load_node_module()
    node = module.TikpanGPT5MiniResponsesNode()
    import torch

    frames = torch.zeros((30, 16, 16, 3), dtype=torch.float32)
    frames[10:] = 0.5
    frames[20:] = 1.0
    uniform = node.select_frame_indices(frames, fps=10, max_frames=6, strategy="均匀覆盖")
    per_second = node.select_frame_indices(frames, fps=10, max_frames=6, strategy="按秒抽帧")
    motion = node.select_frame_indices(frames, fps=10, max_frames=6, strategy="运动变化优先")
    assert len(uniform) <= 6 and len(per_second) <= 6 and len(motion) <= 6
    assert uniform[0] == 0 and uniform[-1] == 29
    assert per_second[0] == 0 and per_second[-1] == 29
    assert motion[0] == 0 and motion[-1] == 29

    items = node.frames_to_image_items(frames, fps=10, max_frames=4, detail="auto", strategy="混合智能")
    labels = [item["text"] for item in items if item.get("type") == "input_text"]
    assert labels and "策略: 混合智能" in labels[0] and "原帧序号" in labels[0]


if __name__ == "__main__":
    test_responses_payload_contract_and_hash()
    test_local_file_validation_text_extraction_and_usage()
    test_rejects_bad_url_and_oversized_local_file()
    test_frame_sampling_strategies_are_bounded_and_annotated()
    print("gpt5 mini responses offline tests passed")
