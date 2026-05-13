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
    assert "自定义voice_name" in keys
    assert any("Kore" in item and "坚定清晰" in item for item in inputs["required"]["音色"][0])

    selected_voice = inputs["required"]["音色"][0][0]
    payload = node.build_gemini_payload("你好", selected_voice, "自动", "自然地说", None)
    speech_config = payload["generationConfig"]["speechConfig"]
    assert "languageCode" not in speech_config
    assert payload["generationConfig"]["responseModalities"] == ["AUDIO"]
    assert speech_config["voiceConfig"]["prebuiltVoiceConfig"]["voiceName"] == "Kore"

    openai_payload = node.build_openai_payload("hello", selected_voice, "zh-CN", "", None)
    assert openai_payload["audio"]["language_code"] == "zh-CN"
    assert openai_payload["audio"]["voice"] == "Kore"


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
    assert "音色" in keys
    assert "自定义voice_id" in keys
    assert any("可靠管理者" in item and "Chinese (Mandarin)_Reliable_Executive" in item for item in inputs["required"]["音色"][0])

    selected_voice = inputs["required"]["音色"][0][0]
    payload = node.build_payload(
        {
            "合成文本": "欢迎使用 Tikpan。",
            "音色": selected_voice,
            "音频格式": "wav",
            "采样率": "32000",
            "比特率": "128000",
            "声道数": "1",
        },
        async_mode=False,
    )
    assert payload["model"] == "speech-2.8-turbo"
    assert payload["voice_setting"]["voice_id"] == "Chinese (Mandarin)_Reliable_Executive"
    assert payload["audio_setting"]["format"] == "wav"
    assert payload["stream"] is False
    assert payload["output_format"] == "hex"

    legacy_payload = node.build_payload(
        {
            "合成文本": "兼容旧工作流。",
            "音色ID": "Chinese (Mandarin)_Reliable_Executive",
            "音频格式": "mp3",
            "采样率": "32000",
            "比特率": "128000",
            "声道数": "1",
        },
        async_mode=False,
    )
    assert legacy_payload["voice_setting"]["voice_id"] == "Chinese (Mandarin)_Reliable_Executive"


def test_doubao_tts_uses_official_voice_dropdown_and_builds_payload():
    module = load_node_module("tikpan_doubao_tts.py", "doubao_tts_node")
    node = module.TikpanDoubaoTTS20Node()
    inputs = node.INPUT_TYPES()
    keys = all_input_keys(inputs)

    assert module.API_HOST == "https://tikpan.com"
    assert "音色" in keys
    assert "自定义voice_type" in keys
    assert "接口基础地址" not in keys
    assert any("VV 2.0" in item and "zh_female_vv_uranus_bigtts" in item for item in inputs["required"]["音色"][0])

    selected_voice = inputs["required"]["音色"][0][0]
    payload, voice_type = node.build_payload(
        {
            "合成文本": "欢迎使用 Tikpan 豆包语音。",
            "音色": selected_voice,
            "语速": 1.0,
            "音量": 1.0,
            "音调": 1.0,
            "情感": "默认不传",
            "音频格式": "mp3",
            "采样率": "24000",
            "用户ID": "test-user",
        },
        request_id="test-request",
    )
    assert voice_type == "zh_female_vv_uranus_bigtts"
    assert payload["user"]["uid"] == "test-user"
    assert payload["req_params"]["speaker"] == voice_type
    assert payload["req_params"]["audio_params"]["format"] == "mp3"


if __name__ == "__main__":
    test_gemini_tts_is_bound_to_tikpan_and_uses_dropdowns()
    test_minimax_speech_is_bound_to_tikpan_and_builds_payload()
    test_doubao_tts_uses_official_voice_dropdown_and_builds_payload()
    print("speech nodes offline tests passed")
