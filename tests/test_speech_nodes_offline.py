import importlib.util
import sys
import types
from pathlib import Path


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


def load_node_module(filename, module_name):
    install_comfy_stubs()
    spec = importlib.util.spec_from_file_location(module_name, ROOT / "nodes" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def all_input_keys(input_types):
    return set(input_types["required"].keys()) | set(input_types.get("optional", {}).keys())


def test_gemini_tts_is_bound_to_tikpan_and_uses_dropdowns():
    module = load_node_module("tikpan_gemini_tts.py", "gemini_tts_node")
    node = module.TikpanGemini31FlashTTSNode()
    inputs = node.INPUT_TYPES()
    keys = all_input_keys(inputs)

    assert module.API_HOST == "https://tikpan.com"
    assert "接口基础地址" not in keys
    assert "POST重试策略" in keys
    assert "校验HTTPS证书" in keys

    payload = node.build_gemini_payload("你好", "Kore", "自动", "自然地说", None)
    speech_config = payload["generationConfig"]["speechConfig"]
    assert "languageCode" not in speech_config
    assert payload["generationConfig"]["responseModalities"] == ["AUDIO"]

    openai_payload = node.build_openai_payload("hello", "Kore", "zh-CN", "", None)
    assert openai_payload["audio"]["language_code"] == "zh-CN"


def test_minimax_speech_is_bound_to_tikpan_and_builds_payload():
    module = load_node_module("tikpan_minimax_speech.py", "minimax_speech_node")
    node = module.TikpanMiniMaxSpeech28TurboNode()
    inputs = node.INPUT_TYPES()
    keys = all_input_keys(inputs)

    assert module.API_HOST == "https://tikpan.com"
    assert module.MINIMAX_API_BASE_URL == "https://tikpan.com/minimax/v1"
    assert "接口基础地址" not in keys
    assert "POST重试策略" in keys
    assert "校验HTTPS证书" in keys

    payload = node.build_payload(
        {
            "合成文本": "欢迎使用 Tikpan。",
            "音色ID": "Chinese (Mandarin)_Reliable_Executive",
            "音频格式": "wav",
            "采样率": "32000",
            "比特率": "128000",
            "声道数": "1",
        },
        async_mode=False,
    )
    assert payload["model"] == "speech-2.8-turbo"
    assert payload["audio_setting"]["format"] == "wav"
    assert payload["stream"] is False
    assert payload["output_format"] == "hex"


if __name__ == "__main__":
    test_gemini_tts_is_bound_to_tikpan_and_uses_dropdowns()
    test_minimax_speech_is_bound_to_tikpan_and_builds_payload()
    print("speech nodes offline tests passed")
