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


def test_cangyuan_gpt_image_2_contract():
    module = load_node_module("tikpan_cangyuan_gpt_image_2.py", "tikpan_cangyuan_gpt_image_2")
    node = module.TikpanCangyuanGptImage2Node()
    inputs = node.INPUT_TYPES()
    keys = all_input_keys(inputs)

    assert module.CANGYUAN_API_HOST == "https://ai.cangyuansuanli.cn"
    assert module.CANGYUAN_IMAGE_ENDPOINT == "/v1/images/generations"
    assert module.CANGYUAN_IMAGE_MODEL == "gpt-image-2"
    assert "沧元说明" in inputs["required"]
    assert "API_密钥" in keys
    assert "生成指令" in keys
    assert "画面比例" in keys
    assert "生成张数" in keys
    assert "校验HTTPS证书" in keys
    assert "模型" not in inputs["required"]
    assert "1:1 方形｜1:1" in module.CANGYUAN_IMAGE_ASPECT_OPTIONS
    assert module.CANGYUAN_IMAGE_SIZE_HINTS["16:9"] == (1536, 864)


def test_cangyuan_grok_video_15_contract():
    module = load_node_module("tikpan_cangyuan_grok_video_15.py", "tikpan_cangyuan_grok_video_15")
    node = module.TikpanCangyuanGrokVideo15Node()
    inputs = node.INPUT_TYPES()
    keys = all_input_keys(inputs)

    assert module.CANGYUAN_API_HOST == "https://ai.cangyuansuanli.cn"
    assert module.CANGYUAN_VIDEO_ENDPOINT == "/v1/video/generations"
    assert module.CANGYUAN_GROK_VIDEO_15_MODEL == "grok-video-1.5"
    assert module.CANGYUAN_GROK_15_DURATION_OPTIONS == [
        "4秒｜4s",
        "6秒｜6s",
        "8秒｜8s",
        "10秒｜10s",
        "12秒｜12s",
        "15秒｜15s",
    ]
    assert "沧元说明" in inputs["required"]
    assert "API_密钥" in keys
    assert "参考图" in keys
    assert "生成指令" in keys
    assert "视频时长" in keys
    assert "分辨率" in keys
    assert "画面比例" in keys

    payload = node.build_payload("grok-video-1.5", "p", "data:image/jpeg;base64,aaa", 4, "480p", "9:16")
    assert payload == {
        "model": "grok-video-1.5",
        "prompt": "p",
        "image_urls": ["data:image/jpeg;base64,aaa"],
        "seconds": 4,
        "resolution": "480p",
        "aspect_ratio": "9:16",
    }


def test_cangyuan_video_model_groups_contract():
    module = load_node_module("tikpan_cangyuan_video_models.py", "tikpan_cangyuan_video_models")

    assert module.CANGYUAN_API_HOST == "https://ai.cangyuansuanli.cn"
    assert module.CANGYUAN_VIDEOS_ENDPOINT == "/v1/videos"
    assert module.CANGYUAN_VIDEO_GENERATIONS_ENDPOINT == "/v1/video/generations"
    expected_nodes = {
        "TikpanCangyuanSeedance20Node",
        "TikpanCangyuanSeedance20Mini480pNode",
        "TikpanCangyuanSeedance20Mini720pNode",
        "TikpanCangyuanSeedance20Fast480pNode",
        "TikpanCangyuanSeedance20Fast720pNode",
        "TikpanCangyuanSeedance20480pNode",
        "TikpanCangyuanSeedance20720pNode",
        "TikpanCangyuanSeedance201080pNode",
        "TikpanCangyuanSeedance204kNode",
        "TikpanCangyuanVeo31Node",
        "TikpanCangyuanVeo31FastNode",
        "TikpanCangyuanOmniFastNode",
        "TikpanCangyuanOmniFastNoWaterNode",
        "TikpanCangyuanOmniV2VStandardNode",
        "TikpanCangyuanOmniV2VNoWaterNode",
        "TikpanCangyuanGrokVideoNode",
    }
    assert set(module.NODE_CLASS_MAPPINGS.keys()) == expected_nodes

    for class_name in expected_nodes:
        inputs = module.NODE_CLASS_MAPPINGS[class_name].INPUT_TYPES()
        assert "模型" not in inputs["required"]
        assert "沧元说明" in inputs["required"]

    seedance = module.TikpanCangyuanSeedance20720pNode()
    seed_payload = seedance.build_payload(
        "p",
        6,
        "16:9",
        "720p",
        ["img1"],
        "first",
        "last",
        ["video1"],
        ["audio1"],
    )
    assert seed_payload["model"] == "seedance-2.0-720p"
    assert seed_payload["duration"] == 6
    assert seed_payload["seconds"] == 6
    assert seed_payload["images"] == ["img1"]
    assert seed_payload["image"] == "first"
    assert seed_payload["image_end"] == "last"
    assert seed_payload["videos"] == ["video1"]
    assert seed_payload["audios"] == ["audio1"]

    seedance_4k_inputs = module.TikpanCangyuanSeedance204kNode.INPUT_TYPES()
    assert seedance_4k_inputs["required"]["分辨率"][0] == ["4K｜4k"]

    veo = module.TikpanCangyuanVeo31FastNode()
    veo_inputs = veo.INPUT_TYPES()
    assert veo_inputs["required"]["视频时长"][0] == "INT"
    assert veo_inputs["required"]["视频时长"][1]["min"] == 1
    assert veo_inputs["required"]["视频时长"][1]["max"] == 30
    veo_payload = veo.build_payload("veo-3-1-fast", "p", 8, "9:16", ["img"])
    assert veo_payload == {
        "model": "veo-3-1-fast",
        "prompt": "p",
        "duration": 8,
        "seconds": 8,
        "aspect_ratio": "9:16",
        "images": ["img"],
        "image_urls": ["img"],
        "image": "img",
    }

    omni = module.TikpanCangyuanOmniFastNode()
    omni_payload = omni.build_payload("omni-fast", "p", "16:9", ["img1", "img2"], "first", "last")
    assert omni_payload["model"] == "omni-fast"
    assert omni_payload["resolution"] == "720p"
    assert omni_payload["images"] == ["img1", "img2"]

    omni_v2v = module.TikpanCangyuanOmniV2VNoWaterNode()
    v2v_payload = omni_v2v.build_payload("omni-v2v", "p", "https://example.com/a.mp4", "16:9")
    assert v2v_payload["video_url"] == "https://example.com/a.mp4"
    assert v2v_payload["videos"] == ["https://example.com/a.mp4"]

    grok = module.TikpanCangyuanGrokVideoNode()
    assert grok.build_payload("grok-video", "p", 15, "720p", "16:9", ["img1", "img2"])["seconds"] == 10
    grok_payload = grok.build_payload("grok-video", "p", 4, "480p", "1:1", ["img1", "img2"])
    assert grok_payload == {
        "model": "grok-video",
        "prompt": "p",
        "seconds": 4,
        "resolution": "480p",
        "aspect_ratio": "1:1",
        "image_urls": ["img1", "img2"],
        "images": ["img1", "img2"],
    }


def test_tikpan_registry_still_includes_benefit_node():
    text = (ROOT / "__init__.py").read_text(encoding="utf-8")
    assert "TikpanGrokVideo15BenefitNode" in text
    assert "福利｜Grok Video 1.5 单图生视频" in text
    assert "TikpanCangyuanGptImage2Node" in text
    assert "TikpanCangyuanGrokVideo15Node" in text
    assert "TikpanCangyuanSeedance20Node" in text
    assert "TikpanCangyuanSeedance20Mini480pNode" in text
    assert "TikpanCangyuanSeedance20Mini720pNode" in text
    assert "TikpanCangyuanSeedance20Fast480pNode" in text
    assert "TikpanCangyuanSeedance20Fast720pNode" in text
    assert "TikpanCangyuanSeedance20480pNode" in text
    assert "TikpanCangyuanSeedance20720pNode" in text
    assert "TikpanCangyuanSeedance201080pNode" in text
    assert "TikpanCangyuanSeedance204kNode" in text
    assert "TikpanCangyuanVeo31Node" in text
    assert "TikpanCangyuanVeo31FastNode" in text
    assert "TikpanCangyuanOmniFastNode" in text
    assert "TikpanCangyuanOmniFastNoWaterNode" in text
    assert "TikpanCangyuanOmniV2VStandardNode" in text
    assert "TikpanCangyuanOmniV2VNoWaterNode" in text
    assert "TikpanCangyuanGrokVideoNode" in text
    assert "沧元｜GPT-Image-2 生图" in text
    assert "沧元｜Grok Video 1.5 单图生视频" in text
    assert "沧元｜Seedance-2.0 视频生成" in text
    assert "沧元｜seedance-2.0-4k 视频生成" in text
    assert "沧元｜veo-3-1 视频生成" in text
    assert "沧元｜veo-3-1-fast 视频生成" in text
    assert "沧元｜omni-fast 文/图生视频" in text
    assert "沧元｜omni-fast-no-water 文/图生视频" in text
    assert "沧元｜omni-v2v 视频转视频" in text
    assert "沧元｜omni-v2v-no-water 视频转视频" in text
    assert "沧元｜Grok 通用视频生成" in text


if __name__ == "__main__":
    test_node_options_keep_raw_values()
    test_grok_video_15_benefit_contract()
    test_cangyuan_gpt_image_2_contract()
    test_cangyuan_grok_video_15_contract()
    test_cangyuan_video_model_groups_contract()
    test_tikpan_registry_still_includes_benefit_node()
    print("node contract offline tests passed")
