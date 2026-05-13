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


def test_shared_option_helpers_normalize_seed_and_dropdown_values():
    module = load_node_module("tikpan_node_options.py", "tikpan_node_options")

    assert module.option_value("高质量细节｜high") == "high"
    assert module.option_int("5秒｜5", default=3, minimum=3, maximum=15) == 5
    assert module.normalize_seed(-1) == 888888
    assert module.normalize_seed("bad") == 888888
    assert module.normalize_seed(2147483647) == 2147483647
    assert module.normalize_seed(2147483648) == 1


def test_suno_uses_dropdowns_and_gates_advanced_parameters():
    module = load_node_module("tikpan_suno_music.py", "tikpan_suno_music")
    node = module.TikpanSunoMusicNode()
    inputs = node.INPUT_TYPES()
    keys = all_input_keys(inputs)

    assert "风格预设" in keys
    assert "模型版本" in keys
    assert "发送高级Suno参数" in keys
    assert any("chirp-fenix" in item for item in inputs["required"]["模型版本"][0])
    assert any("cinematic" in item for item in inputs["required"]["风格预设"][0])

    tags = node.normalize_tags("电影感｜Cinematic｜cinematic, orchestral", "trailer")
    assert tags == "cinematic, orchestral, trailer"

    base_payload = node.build_payload(
        mode="自定义模式",
        title="测试歌曲",
        prompt="写一首歌",
        tags=tags,
        negative_tags="noise",
        mv="chirp-fenix",
        make_instrumental=False,
        continue_clip_id="",
        continue_at=0,
        persona_id="",
        artist_clip_id="",
    )
    assert "style_weight" not in base_payload
    assert "vocal_gender" not in base_payload
    assert base_payload["mv"] == "chirp-fenix"
    assert base_payload["tags"] == tags

    advanced_payload = node.build_payload(
        mode="自定义模式",
        title="测试歌曲",
        prompt="写一首歌",
        tags=tags,
        negative_tags="noise",
        mv="chirp-fenix",
        make_instrumental=False,
        continue_clip_id="",
        continue_at=0,
        persona_id="",
        artist_clip_id="",
        send_advanced=True,
        vocal_gender="f",
        auto_lyrics=True,
        style_weight=0.7,
        weirdness_constraint=0.2,
    )
    assert advanced_payload["custom_mode"] is True
    assert advanced_payload["task_type"] == "create_music"
    assert advanced_payload["vocal_gender"] == "f"
    assert advanced_payload["style_weight"] == 0.7
    assert advanced_payload["weirdness_constraint"] == 0.2


def test_nano_banana_pro_uses_official_gemini_image_config():
    module = load_node_module("tikpan_nano_banana_pro.py", "tikpan_nano_banana_pro")
    node = module.TikpanNanoBananaProNode()
    inputs = node.INPUT_TYPES()
    keys = all_input_keys(inputs)

    assert "随机种子" in keys
    assert "最大输出Token数" in keys
    assert "max_tokens" not in keys

    payload = node.build_gemini_payload(
        prompt="生成一张图",
        image_tensors=[],
        分辨率="2K",
        画面比例="16:9 | 16:9横屏",
        seed=888888,
        温度=0.7,
    )
    generation_config = payload["generationConfig"]
    assert generation_config["responseModalities"] == ["TEXT", "IMAGE"]
    assert generation_config["imageConfig"] == {"aspectRatio": "16:9", "imageSize": "2K"}
    assert generation_config["responseFormat"] == {"image": {"aspectRatio": "16:9", "imageSize": "2K"}}

    chat_payload = node.build_chat_payload(
        model="gemini-3-pro-image-preview",
        prompt="生成一张图",
        image_tensors=[],
        分辨率="4K",
        画面比例="1:1 | 1:1正方形",
        seed=888888,
        温度=0.7,
        max_tokens=4096,
    )
    assert chat_payload["max_tokens"] == 4096
    assert chat_payload["image_config"] == {"aspect_ratio": "1:1", "image_size": "4K"}


def test_gemini_image_native_payload_keeps_rest_and_sdk_image_config_fields():
    text = (ROOT / "nodes" / "tikpan_gemini_image.py").read_text(encoding="utf-8")
    native_block = text.split('if 调用方式 == "gemini原生":', 1)[1].split('elif 调用方式 == "images_generations":', 1)[0]
    assert 'gen_config["imageConfig"] = image_config' in native_block
    assert 'gen_config["responseFormat"] = {"image": image_config}' in native_block


if __name__ == "__main__":
    test_shared_option_helpers_normalize_seed_and_dropdown_values()
    test_suno_uses_dropdowns_and_gates_advanced_parameters()
    test_nano_banana_pro_uses_official_gemini_image_config()
    test_gemini_image_native_payload_keeps_rest_and_sdk_image_config_fields()
    print("node contract offline tests passed")
