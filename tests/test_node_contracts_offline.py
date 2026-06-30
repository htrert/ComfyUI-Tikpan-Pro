import importlib.util
import sys
import types
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[1]


def install_comfy_stubs():
    comfy = types.ModuleType("comfy")
    model_management = types.ModuleType("comfy.model_management")
    utils = types.ModuleType("comfy.utils")
    folder_paths = types.ModuleType("folder_paths")
    model_management.throw_exception_if_processing_interrupted = lambda: None
    folder_paths.get_output_directory = lambda: str(ROOT / "tests")

    class ProgressBar:
        def __init__(self, *args, **kwargs):
            pass

        def update(self, *args, **kwargs):
            pass

        def update_absolute(self, *args, **kwargs):
            pass

    utils.ProgressBar = ProgressBar
    comfy.model_management = model_management
    comfy.utils = utils
    sys.modules["comfy"] = comfy
    sys.modules["comfy.model_management"] = model_management
    sys.modules["comfy.utils"] = utils
    sys.modules["folder_paths"] = folder_paths

    package = sys.modules.get("nodes")
    if package is None:
        package = types.ModuleType("nodes")
        package.__path__ = [str(ROOT / "nodes")]
        sys.modules["nodes"] = package


def load_node_module(filename, module_name):
    install_comfy_stubs()
    spec = importlib.util.spec_from_file_location(
        f"nodes.{module_name}",
        ROOT / "nodes" / filename,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def all_input_keys(input_types):
    return set(input_types["required"].keys()) | set(input_types.get("optional", {}).keys())


def test_node_options_keep_raw_values():
    module = load_node_module("tikpan_node_options.py", "tikpan_node_options")

    assert module.OPTION_SEPARATOR == "｜"
    assert module.option_value("高质量细节｜high") == "high"
    assert module.option_int("5秒｜5", default=3, minimum=3, maximum=15) == 5
    assert module.normalize_seed(-1) == 888888
    assert module.normalize_seed("bad") == 888888
    assert module.normalize_seed(2147483647) == 2147483647
    assert module.normalize_seed(2147483648) == 1


def test_grok_video_15_benefit_contract():
    module = load_node_module("tikpan_grok_video_15_benefit.py", "tikpan_grok_video_15_benefit")
    node = module.TikpanGrokVideo15BenefitNode()
    inputs = node.INPUT_TYPES()
    keys = all_input_keys(inputs)

    assert "福利说明" in inputs["required"]
    assert "API_密钥" in keys
    assert "参考图" in keys
    assert "生成指令" in keys
    assert "视频时长" in keys
    assert "跳过错误" in keys
    assert module.BENEFIT_API_HOST == "https://api.manxiaobai.online"
    assert module.BENEFIT_ENDPOINT == "/v1/video/generations"
    assert module.GROK_15_BENEFIT_DURATION_OPTIONS[0] == "4秒｜4s"
    assert module.MODEL_IDS == ["grok-video-1.5", "119337-grok-video-1.5"]

    payload = node.build_payload("grok-video-1.5", "p", "data:image/jpeg;base64,aaa", 15, "720p", "16:9")
    assert payload == {
        "model": "grok-video-1.5",
        "prompt": "p",
        "image_urls": ["data:image/jpeg;base64,aaa"],
        "seconds": "15",
        "resolution": "720p",
        "aspect_ratio": "16:9",
    }
    fallback_payload = node.build_payload("119337-grok-video-1.5", "p", "data:image/jpeg;base64,aaa", 4, "720p", "16:9")
    assert fallback_payload["model"] == "119337-grok-video-1.5"

    download_session = node.create_download_session()
    assert isinstance(download_session, requests.Session)
    assert download_session.trust_env is True


def test_tikpan_registry_still_includes_benefit_node():
    text = (ROOT / "__init__.py").read_text(encoding="utf-8")
    assert "TikpanGrokVideo15BenefitNode" in text
    assert "福利｜Grok Video 1.5 单图生视频" in text


if __name__ == "__main__":
    test_node_options_keep_raw_values()
    test_grok_video_15_benefit_contract()
    test_tikpan_registry_still_includes_benefit_node()
    print("node contract offline tests passed")
