import importlib.util
import importlib
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
    if "torch" not in sys.modules and importlib.util.find_spec("torch") is None:
        torch = types.ModuleType("torch")
        torch.float32 = "float32"
        torch.zeros = lambda *args, **kwargs: None
        torch.from_numpy = lambda value: value
        sys.modules["torch"] = torch

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

    assert module.CANGYUAN_API_HOST == "https://new.ip233.com"
    assert module.CANGYUAN_IMAGE_ENDPOINT == "/v1/images/generations"
    assert module.CANGYUAN_IMAGE_MODEL == "gpt-image-2"
    assert "new.ip233.com说明" in inputs["required"]
    assert "API_密钥" in keys
    assert "生成指令" in keys
    assert "画面比例" in keys
    assert "生成张数" in keys
    assert "校验HTTPS证书" in keys
    assert "模型" not in inputs["required"]
    assert module.CANGYUAN_IMAGE_ASPECT_OPTIONS == [
        "1:1 方形｜1:1",
        "3:2 横屏｜3:2",
        "2:3 竖屏｜2:3",
        "自动｜auto",
    ]
    assert module.CANGYUAN_IMAGE_SIZE_HINTS["3:2"] == (1536, 1024)
    assert "16:9" not in module.CANGYUAN_IMAGE_SIZE_HINTS


def test_cangyuan_grok_video_15_contract():
    module = load_node_module("tikpan_cangyuan_grok_video_15.py", "tikpan_cangyuan_grok_video_15")
    node = module.TikpanCangyuanGrokVideo15Node()
    inputs = node.INPUT_TYPES()
    keys = all_input_keys(inputs)

    assert module.CANGYUAN_API_HOST == "https://new.ip233.com"
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
    assert "new.ip233.com说明" in inputs["required"]
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

    assert module.CANGYUAN_API_HOST == "https://new.ip233.com"
    assert module.CANGYUAN_VIDEOS_ENDPOINT == "/v1/videos"
    assert module.CANGYUAN_VIDEO_GENERATIONS_ENDPOINT == "/v1/video/generations"
    expected_nodes = {
        "TikpanCangyuanSeedance20Node",
        "TikpanCangyuanSeedance20MiniNode",
        "TikpanCangyuanSeedance20Mini480pNode",
        "TikpanCangyuanSeedance20Mini720pNode",
        "TikpanCangyuanSeedance20FastNode",
        "TikpanCangyuanSeedance20Fast480pNode",
        "TikpanCangyuanSeedance20Fast720pNode",
        "TikpanCangyuanSeedance20480pNode",
        "TikpanCangyuanSeedance20720pNode",
        "TikpanCangyuanSeedance201080pNode",
        "TikpanCangyuanSeedance204kNode",
        "TikpanCangyuanVeo31Node",
        "TikpanCangyuanVeo31FastNode",
        "TikpanCangyuanVeo31RefNode",
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
        assert "new.ip233.com说明" in inputs["required"]

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
    assert "seconds" not in seed_payload
    assert seed_payload["reference_image_urls"] == ["img1"]
    assert seed_payload["image_url"] == "img1"
    assert seed_payload["first_image_url"] == "first"
    assert seed_payload["last_image_url"] == "last"
    assert seed_payload["reference_videos"] == ["video1"]
    assert seed_payload["reference_audios"] == ["audio1"]

    seedance_4k_inputs = module.TikpanCangyuanSeedance204kNode.INPUT_TYPES()
    assert seedance_4k_inputs["required"]["分辨率"][0] == ["4K｜4k"]
    seedance_base_inputs = module.TikpanCangyuanSeedance20Node.INPUT_TYPES()
    assert "生成原生音频" in seedance_base_inputs["optional"]
    assert "参考图5" not in seedance_base_inputs["optional"]

    veo = module.TikpanCangyuanVeo31FastNode()
    veo_inputs = veo.INPUT_TYPES()
    assert veo_inputs["required"]["视频时长"][0] == ["4秒｜4", "6秒｜6", "8秒｜8"]
    assert "参考图3" not in veo_inputs["optional"]
    veo_payload = veo.build_payload("veo-3-1-fast", "p", 8, "9:16", ["img"], "1080p", True, "frame", 2)
    assert veo_payload == {
        "model": "veo-3-1-fast",
        "prompt": "p",
        "duration": 8,
        "aspect_ratio": "9:16",
        "resolution": "1080p",
        "generate_audio": True,
        "reference_mode": "frame",
        "images": ["img"],
    }
    veo_ref_inputs = module.TikpanCangyuanVeo31RefNode.INPUT_TYPES()
    assert "参考图3" in veo_ref_inputs["optional"]
    assert "参考图4" not in veo_ref_inputs["optional"]

    omni = module.TikpanCangyuanOmniFastNode()
    omni_payload = omni.build_payload("omni-fast", "p", "16:9", "img1", "first", "last")
    assert omni_payload["model"] == "omni-fast"
    assert "resolution" not in omni_payload
    assert omni_payload["image_url"] == "img1"
    assert omni_payload["first_image_url"] == "first"
    assert omni_payload["last_image_url"] == "last"

    omni_v2v = module.TikpanCangyuanOmniV2VNoWaterNode()
    v2v_payload = omni_v2v.build_payload("omni-v2v", "p", "https://example.com/a.mp4", "16:9")
    assert v2v_payload["video_url"] == "https://example.com/a.mp4"
    assert "videos" not in v2v_payload

    grok = module.TikpanCangyuanGrokVideoNode()
    assert grok.build_payload("grok-video", "p", 15, "720p", "16:9", ["img1", "img2"])["seconds"] == 10
    grok_payload = grok.build_payload("grok-video", "p", 4, "480p", "1:1", ["img1", "img2"], "https://example.com/a.mp4")
    assert grok_payload == {
        "model": "grok-video",
        "prompt": "p",
        "seconds": 4,
        "resolution": "480p",
        "aspect_ratio": "1:1",
        "image_urls": ["img1", "img2"],
        "video_url": "https://example.com/a.mp4",
    }


def test_tikpan_registry_still_includes_benefit_node():
    text = (ROOT / "__init__.py").read_text(encoding="utf-8")
    assert "TikpanGrokVideo15BenefitNode" in text
    assert "福利｜Grok Video 1.5 单图生视频" in text
    assert "TikpanCangyuanGptImage2Node" in text
    assert "TikpanCangyuanGrokVideo15Node" in text
    assert "TikpanCangyuanSeedance20Node" in text
    assert "TikpanCangyuanSeedance20MiniNode" in text
    assert "TikpanCangyuanSeedance20Mini480pNode" in text
    assert "TikpanCangyuanSeedance20Mini720pNode" in text
    assert "TikpanCangyuanSeedance20FastNode" in text
    assert "TikpanCangyuanSeedance20Fast480pNode" in text
    assert "TikpanCangyuanSeedance20Fast720pNode" in text
    assert "TikpanCangyuanSeedance20480pNode" in text
    assert "TikpanCangyuanSeedance20720pNode" in text
    assert "TikpanCangyuanSeedance201080pNode" in text
    assert "TikpanCangyuanSeedance204kNode" in text
    assert "TikpanCangyuanVeo31Node" in text
    assert "TikpanCangyuanVeo31FastNode" in text
    assert "TikpanCangyuanVeo31RefNode" in text
    assert "TikpanCangyuanOmniFastNode" in text
    assert "TikpanCangyuanOmniFastNoWaterNode" in text
    assert "TikpanCangyuanOmniV2VStandardNode" in text
    assert "TikpanCangyuanOmniV2VNoWaterNode" in text
    assert "TikpanCangyuanGrokVideoNode" in text
    assert "TikpanGptImage2GenNode" in text
    assert "TikpanGptImage2EditNode" in text
    assert "GPT-Image-2-C 旧版多参考生图" in text
    assert "GPT-Image-2-C 旧版修图" in text
    assert "new.ip233.com｜GPT-Image-2 生图" in text
    assert "new.ip233.com｜Grok Video 1.5 单图生视频" in text
    assert "new.ip233.com｜Seedance-2.0 视频生成" in text
    assert "new.ip233.com｜seedance-2.0-mini 视频生成" in text
    assert "new.ip233.com｜seedance-2.0-fast 视频生成" in text
    assert "new.ip233.com｜seedance-2.0-4k 视频生成" in text
    assert "new.ip233.com｜veo-3-1 视频生成" in text
    assert "new.ip233.com｜veo-3-1-fast 视频生成" in text
    assert "new.ip233.com｜veo-3-1-ref 参考图视频" in text
    assert "new.ip233.com｜omni-fast 文/图生视频" in text
    assert "new.ip233.com｜omni-fast-no-water 文/图生视频" in text
    assert "new.ip233.com｜omni-v2v 视频转视频" in text
    assert "new.ip233.com｜omni-v2v-no-water 视频转视频" in text
    assert "new.ip233.com｜Grok 通用视频生成" in text


def test_gpt_image_2_c_legacy_nodes_contract():
    gen_module = load_node_module("tikpan_gpt_image_2_gen.py", "tikpan_gpt_image_2_gen")
    edit_module = load_node_module("tikpan_gpt_image_2_edit.py", "tikpan_gpt_image_2_edit")

    gen_inputs = gen_module.TikpanGptImage2GenNode.INPUT_TYPES()
    gen_keys = all_input_keys(gen_inputs)
    assert gen_module.GPT_IMAGE_2_C_MODEL == "gpt-image-2-c"
    assert gen_inputs["required"]["模型"][0] == ["gpt-image-2-c"]
    assert "参考图_1" in gen_keys
    assert "中转站地址" in gen_keys

    edit_inputs = edit_module.TikpanGptImage2EditNode.INPUT_TYPES()
    edit_keys = all_input_keys(edit_inputs)
    assert edit_module.GPT_IMAGE_2_C_MODEL == "gpt-image-2-c"
    assert edit_inputs["required"]["模型"][0] == ["gpt-image-2-c"]
    assert "底图" in edit_keys
    assert "遮罩_Mask" in edit_keys
    assert "产品参考图" in edit_keys


if __name__ == "__main__":
    test_node_options_keep_raw_values()
    test_grok_video_15_benefit_contract()
    test_cangyuan_gpt_image_2_contract()
    test_cangyuan_grok_video_15_contract()
    test_cangyuan_video_model_groups_contract()
    test_tikpan_registry_still_includes_benefit_node()
    test_gpt_image_2_c_legacy_nodes_contract()
    print("node contract offline tests passed")
