import importlib.util
import json
import sys
import types
from pathlib import Path
from tempfile import NamedTemporaryFile


ROOT = Path(__file__).resolve().parents[1]
NODE_PATH = ROOT / "nodes" / "tikpan_gemini3_flash_preview_analyst.py"


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
    sys.modules["folder_paths"] = types.ModuleType("folder_paths")


def load_node_module():
    install_comfy_stubs()
    spec = importlib.util.spec_from_file_location("gemini3_analyst_node", NODE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def find_key(keys, name):
    matches = [key for key in keys if name in key]
    assert matches, f"missing input key containing {name}"
    return matches[0]


def test_payload_urls_hash_and_json_split():
    module = load_node_module()
    node = module.TikpanGemini3FlashPreviewAnalystNode()
    inputs = node.INPUT_TYPES()
    keys = list(inputs["required"].keys()) + list(inputs["optional"].keys())
    output_key = find_key(inputs["required"].keys(), "输出格式")
    json_format = [item for item in inputs["required"][output_key][0] if "JSON" in item][0]

    payload = node.build_payload(
        {
            find_key(keys, "图片URL"): "https://example.com/a.jpg\nhttps://example.com/b.png",
            find_key(keys, "视频URL"): "https://example.com/demo.mp4",
        }
    )
    parts = payload["contents"][0]["parts"]

    assert any(part.get("file_data", {}).get("file_uri") == "https://example.com/a.jpg" for part in parts)
    assert any(part.get("file_data", {}).get("file_uri") == "https://example.com/demo.mp4" for part in parts)
    assert payload["generationConfig"]["maxOutputTokens"] == 4096
    assert node.payload_hash(payload) == node.payload_hash(payload)

    prompt, structured = node.split_outputs(
        json.dumps({"summary": "ok", "prompt": "use this prompt"}),
        json_format,
    )
    assert prompt == "use this prompt"
    assert json.loads(structured)["summary"] == "ok"

    standard_response = {
        "candidates": [
            {
                "finishReason": "STOP",
                "content": {"parts": [{"text": "标准候选文本"}]},
            }
        ]
    }
    assert node.extract_text(standard_response) == "标准候选文本"
    assert node.extract_finish_reason(standard_response) == "STOP"


def test_rejects_oversized_local_video_and_bad_url():
    module = load_node_module()
    node = module.TikpanGemini3FlashPreviewAnalystNode()
    keys = list(node.INPUT_TYPES()["required"].keys()) + list(node.INPUT_TYPES()["optional"].keys())

    with NamedTemporaryFile(suffix=".mp4", delete=True) as handle:
        handle.truncate(module.MAX_INLINE_BYTES + 1)
        handle.flush()
        try:
            node.local_video_part(handle.name)
            raise AssertionError("oversized video should be rejected before request")
        except ValueError as exc:
            assert "inline" in str(exc)

    try:
        node.build_payload({find_key(keys, "图片URL"): "ftp://bad.example/file.jpg"})
        raise AssertionError("invalid URL should be rejected before request")
    except ValueError as exc:
        assert "URL" in str(exc)

    node._last_warnings = []
    urls = node.parse_url_lines("ftp://bad.example/file.jpg\nhttps://example.com/ok.jpg", skip_invalid=True, field_name="图片URL列表")
    assert urls == ["https://example.com/ok.jpg"]
    assert "跳过无效链接" in node._last_warnings[0]


def test_frame_sampling_strategies_are_bounded_and_annotated():
    module = load_node_module()
    node = module.TikpanGemini3FlashPreviewAnalystNode()
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

    parts, count = node.frames_to_parts(frames, fps=10, max_frames=4, strategy="混合智能")
    assert count <= 4
    labels = [part["text"] for part in parts if "text" in part]
    assert labels and "策略: 混合智能" in labels[0] and "原帧序号" in labels[0]


if __name__ == "__main__":
    test_payload_urls_hash_and_json_split()
    test_rejects_oversized_local_video_and_bad_url()
    test_frame_sampling_strategies_are_bounded_and_annotated()
    print("gemini3 analyst offline tests passed")
