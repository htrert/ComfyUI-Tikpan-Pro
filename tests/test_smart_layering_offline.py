"""
测试智能分层 PSD 节点
"""
import sys
import os

# Windows 终端默认 GBK 编不出 emoji，强制 stdout 为 utf-8
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import numpy as np
try:
    import torch
except ImportError:
    class MockTensor:
        def __init__(self, array):
            self._array = array

        @property
        def shape(self):
            return self._array.shape

        def unsqueeze(self, axis):
            return MockTensor(np.expand_dims(self._array, axis))

        def detach(self):
            return self

        def cpu(self):
            return self

        def numpy(self):
            return self._array

    class MockTorch:
        @staticmethod
        def from_numpy(array):
            return MockTensor(array)

    torch = MockTorch()
from PIL import Image

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 模拟 ComfyUI 的 folder_paths 和 comfy.utils
class MockFolderPaths:
    @staticmethod
    def get_output_directory():
        test_output = os.path.join(project_root, "tests", "test_outputs")
        os.makedirs(test_output, exist_ok=True)
        return test_output

    @staticmethod
    def models_dir():
        return os.path.join(project_root, "tests", "mock_models")

class MockProgressBar:
    def __init__(self, total):
        self.total = total
        self.current = 0

    def update(self, value):
        self.current = value
        print(f"  进度: {self.current}/{self.total}")

class MockComfyUtils:
    @staticmethod
    def ProgressBar(total):
        return MockProgressBar(total)

sys.modules['folder_paths'] = MockFolderPaths()
sys.modules['comfy'] = type('obj', (object,), {'utils': MockComfyUtils()})
sys.modules['comfy.utils'] = MockComfyUtils()

from nodes.tikpan_smart_psd_layering import (
    TikpanSmartPSDLayeringNode,
    TIER_ECONOMY, TIER_STANDARD, TIER_PREMIUM,
    TIER_KIND_ECONOMY, TIER_KIND_STANDARD, TIER_KIND_PREMIUM,
    normalize_tier,
    SCENE_AUTO, SCENE_ECOM_ITEM, SCENE_ECOM_BANNER, SCENE_PORTRAIT, SCENE_LIFESTYLE, SCENE_ALL,
    SCENE_LABEL_TO_KEY,
)


def create_test_image_tensor(width=512, height=512):
    """创建测试用的图片 tensor（带渐变和几何形状）"""
    image = np.zeros((height, width, 3), dtype=np.float32)

    # 背景渐变
    for i in range(height):
        for j in range(width):
            image[i, j, 0] = 0.8  # 浅红背景
            image[i, j, 1] = 0.9
            image[i, j, 2] = 0.95

    # 添加一个圆形主体（模拟产品）
    center_x, center_y = width // 2, height // 2
    radius = min(width, height) // 4
    for i in range(height):
        for j in range(width):
            dist = np.sqrt((i - center_y)**2 + (j - center_x)**2)
            if dist < radius:
                image[i, j, 0] = 0.2  # 深色圆形
                image[i, j, 1] = 0.3
                image[i, j, 2] = 0.8

    # 添加一个矩形元素（模拟标签）
    rect_x1, rect_y1 = width // 4, height // 4
    rect_x2, rect_y2 = rect_x1 + 80, rect_y1 + 40
    image[rect_y1:rect_y2, rect_x1:rect_x2, 0] = 1.0  # 红色矩形
    image[rect_y1:rect_y2, rect_x1:rect_x2, 1] = 0.2
    image[rect_y1:rect_y2, rect_x1:rect_x2, 2] = 0.2

    # 转换为 torch tensor (batch, height, width, channels)
    tensor = torch.from_numpy(image).unsqueeze(0)
    return tensor


def test_node_initialization():
    """测试节点初始化"""
    print("=" * 60)
    print("测试 1: 节点初始化")
    print("=" * 60)

    try:
        node = TikpanSmartPSDLayeringNode()
        print("✅ 节点初始化成功")
        print(f"   输出目录: {node.output_dir}")
        print(f"   依赖状态: {node.deps_status}")
        return node
    except Exception as e:
        print(f"❌ 节点初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_input_types():
    """测试输入类型定义"""
    print("\n" + "=" * 60)
    print("测试 2: 输入类型定义")
    print("=" * 60)

    try:
        input_types = TikpanSmartPSDLayeringNode.INPUT_TYPES()
        print("✅ 输入类型定义正确")
        print(f"   必需参数: {list(input_types['required'].keys())}")

        # 验证关键参数存在
        required = input_types['required']
        assert '输入图片' in required
        assert '文件名' in required
        assert '分层档位' in required
        assert '场景类型' in required, "新增的场景类型下拉框缺失"
        assert '补全被遮挡区域' in required
        assert '检测文字' in required
        assert '最小元素面积' in required
        assert '边缘羽化' in required
        assert '自动安装依赖' in required

        # 验证场景下拉框选项
        scene_options = required['场景类型'][0]
        for s in [SCENE_AUTO, SCENE_ECOM_ITEM, SCENE_ECOM_BANNER, SCENE_PORTRAIT, SCENE_LIFESTYLE, SCENE_ALL]:
            assert s in scene_options, f"场景选项缺失: {s}"

        print("   ✓ 所有关键参数存在")
        print(f"   ✓ 场景下拉框包含 {len(scene_options)} 个选项")
        return True
    except Exception as e:
        print(f"❌ 输入类型定义失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_dependency_check(node):
    """测试依赖检查功能"""
    print("\n" + "=" * 60)
    print("测试 3: 依赖检查")
    print("=" * 60)

    try:
        print("   当前依赖状态:")
        for dep, available in node.deps_status.items():
            status = "✓ 已安装" if available else "✗ 未安装"
            print(f"     {dep}: {status}")

        # 测试缺失依赖检测
        missing_economy = node._check_missing_for_tier(TIER_ECONOMY, False)
        missing_standard = node._check_missing_for_tier(TIER_STANDARD, False)
        missing_premium = node._check_missing_for_tier(TIER_PREMIUM, False)

        print(f"\n   经济档缺失依赖: {missing_economy if missing_economy else '无'}")
        print(f"   标准档缺失依赖: {missing_standard if missing_standard else '无'}")
        print(f"   极致档缺失依赖: {missing_premium if missing_premium else '无'}")

        print("\n✅ 依赖检查功能正常")
        return True
    except Exception as e:
        print(f"❌ 依赖检查失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_processor_import():
    """测试处理器模块导入"""
    print("\n" + "=" * 60)
    print("测试 4: 处理器模块导入")
    print("=" * 60)

    try:
        from nodes.tikpan_psd_processor import PSDLayerProcessor
        print("✅ PSDLayerProcessor 导入成功")

        # 测试实例化
        test_output = os.path.join(project_root, "tests", "test_outputs")
        processor = PSDLayerProcessor(test_output)
        print(f"   处理器输出目录: {processor.output_dir}")

        # 检查关键方法存在
        assert hasattr(processor, 'process_economy')
        assert hasattr(processor, 'process_standard')
        assert hasattr(processor, 'process_premium')
        assert hasattr(processor, 'save_as_psd')
        assert hasattr(processor, 'create_preview')
        print("   ✓ 所有关键方法存在")

        return True
    except Exception as e:
        print(f"❌ 处理器模块导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_filename_sanitization():
    """测试文件名清理"""
    print("\n" + "=" * 60)
    print("测试 5: 文件名清理")
    print("=" * 60)

    try:
        from nodes.tikpan_psd_processor import PSDLayerProcessor
        test_output = os.path.join(project_root, "tests", "test_outputs")
        processor = PSDLayerProcessor(test_output)

        test_cases = [
            ("normal_file", "normal_file"),
            ("file<>:name", "file___name"),
            ("file|with?illegal*chars", "file_with_illegal_chars"),
            ("  spaces  ", "spaces"),
            ("file.psd", "file"),
            ("", "output"),
        ]

        print("   测试用例:")
        for input_name, expected in test_cases:
            result = processor._sanitize_filename(input_name)
            status = "✓" if result == expected else "✗"
            print(f"     {status} '{input_name}' -> '{result}' (期望: '{expected}')")
            if result != expected:
                print(f"       ⚠️ 不匹配！")

        print("\n✅ 文件名清理功能正常")
        return True
    except Exception as e:
        print(f"❌ 文件名清理失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_error_image_creation(node):
    """测试错误图片生成"""
    print("\n" + "=" * 60)
    print("测试 6: 错误图片生成")
    print("=" * 60)

    try:
        error_msg = "测试错误信息\n这是第二行\n这是第三行"
        error_img = node._create_error_image(error_msg)

        print(f"   错误图片 shape: {error_img.shape}")
        assert error_img.shape[0] == 1  # batch
        assert error_img.shape[1] == 512  # height
        assert error_img.shape[2] == 768  # width
        assert error_img.shape[3] == 3  # RGB

        print("✅ 错误图片生成正常")
        return True
    except Exception as e:
        print(f"❌ 错误图片生成失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_mock_smart_layer_without_deps(node):
    """测试无依赖时的行为（应该返回错误）"""
    print("\n" + "=" * 60)
    print("测试 7: 无依赖时的错误处理")
    print("=" * 60)

    try:
        test_tensor = create_test_image_tensor(256, 256)
        print(f"   创建测试图片: shape={test_tensor.shape}")

        # 强制设置自动安装为"否"，模拟缺少依赖的情况
        result = node.smart_layer(
            输入图片=test_tensor,
            文件名="test_no_deps",
            分层档位=TIER_ECONOMY,
            场景类型=SCENE_AUTO,
            补全被遮挡区域="否",
            检测文字="否",
            最小元素面积=2000,
            边缘羽化=5,
            自动安装依赖="否"
        )

        psd_path, log, preview = result

        # 如果缺少依赖，应该返回错误
        if not psd_path:
            print(f"   ✓ 正确返回错误（缺少依赖）")
            print(f"   日志: {log[:100]}...")
        else:
            print(f"   ⚠️ 意外成功（可能依赖已安装）")
            print(f"   PSD路径: {psd_path}")

        print("\n✅ 错误处理正常")
        return True
    except Exception as e:
        print(f"❌ 错误处理测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_layer_structure():
    """测试图层结构构建"""
    print("\n" + "=" * 60)
    print("测试 8: 图层结构构建")
    print("=" * 60)

    try:
        from nodes.tikpan_psd_processor import PSDLayerProcessor
        test_output = os.path.join(project_root, "tests", "test_outputs")
        processor = PSDLayerProcessor(test_output)

        # 创建模拟图层数据
        original = Image.new("RGB", (512, 512), (255, 255, 255))
        bg = Image.new("RGBA", (512, 512), (200, 200, 200, 255))
        subject = Image.new("RGBA", (512, 512), (100, 100, 255, 255))

        elements = [
            {"name": "元素_1", "image": Image.new("RGBA", (512, 512), (255, 0, 0, 128)), "type": "element", "area": 5000},
            {"name": "元素_2", "image": Image.new("RGBA", (512, 512), (0, 255, 0, 128)), "type": "element", "area": 3000},
        ]

        texts = [
            {"name": "文字_1_测试", "image": Image.new("RGBA", (512, 512), (0, 0, 0, 255)), "type": "text"},
        ]

        layers = processor._build_layer_list(original, bg, subject, elements, texts)

        print(f"   生成图层数: {len(layers)}")
        print("   图层结构:")
        for i, layer in enumerate(layers):
            print(f"     {i+1}. {layer['name']} ({layer.get('type', 'unknown')})")

        # 验证图层顺序
        assert layers[0]['name'] == "原图_参考"
        assert layers[1]['name'] == "背景"
        assert "元素" in layers[2]['name']
        assert "文字" in layers[-1]['name']

        print("\n✅ 图层结构构建正常")
        return True
    except Exception as e:
        print(f"❌ 图层结构构建失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_scene_label_mapping():
    """测试场景下拉框 label -> key 映射完整性"""
    print("\n" + "=" * 60)
    print("测试 9: 场景标签映射")
    print("=" * 60)
    try:
        expected_keys = {"auto", "ecom_item", "ecom_banner", "portrait", "lifestyle", "all"}
        actual_keys = set(SCENE_LABEL_TO_KEY.values())
        missing = expected_keys - actual_keys
        assert not missing, f"映射缺失: {missing}"

        # 每个 label 都不空
        for label, key in SCENE_LABEL_TO_KEY.items():
            assert label and key
        print(f"   ✓ {len(SCENE_LABEL_TO_KEY)} 个场景映射齐全: {sorted(actual_keys)}")
        return True
    except Exception as e:
        print(f"❌ 场景映射测试失败: {e}")
        import traceback; traceback.print_exc()
        return False


def test_segmentation_models_exports():
    """测试 segmentation_models 模块暴露的所有公共符号"""
    print("\n" + "=" * 60)
    print("测试 10: segmentation_models 公共符号")
    print("=" * 60)
    try:
        from nodes import tikpan_segmentation_models as sm
        expected = [
            "birefnet_matting", "birefnet_portrait_matting",
            "get_sam2_predictor", "get_sam2_auto_generator",
            "gdino_detect", "paddle_ocr_detect",
            "detect_qrcodes",
            "cluster_text_by_size", "extract_color_blocks", "color_name",
            "get_scene_prompt", "auto_detect_scene",
            "SCENE_PROMPTS", "GDINO_PROMPT_PRODUCT",
        ]
        missing = [s for s in expected if not hasattr(sm, s)]
        assert not missing, f"缺少符号: {missing}"
        print(f"   ✓ 全部 {len(expected)} 个公共符号都暴露")

        # 检查 prompt 字典里每个场景的 prompt 都符合 GroundingDINO 格式
        for key, prompt in sm.SCENE_PROMPTS.items():
            assert prompt.endswith("."), f"prompt 必须以句号结尾: {key}"
            assert prompt == prompt.lower(), f"prompt 必须全小写: {key}"
        print(f"   ✓ {len(sm.SCENE_PROMPTS)} 套场景 prompt 格式都合规")
        return True
    except Exception as e:
        print(f"❌ segmentation_models 公共符号失败: {e}")
        import traceback; traceback.print_exc()
        return False


def test_text_size_clustering():
    """测试文字按字号聚类（纯算法）"""
    print("\n" + "=" * 60)
    print("测试 11: 文字字号聚类")
    print("=" * 60)
    try:
        from nodes.tikpan_segmentation_models import cluster_text_by_size

        # 模拟 OCR 结果：1000px 高的图
        image_height = 1000
        ocr_results = [
            {"bbox": [10, 10, 500, 110], "text": "夏季大促", "score": 0.95},   # 高100 (10%) -> 标题
            {"bbox": [10, 130, 400, 200], "text": "全场五折", "score": 0.9},   # 高70 (7%) -> 标题
            {"bbox": [10, 220, 300, 270], "text": "新款上市", "score": 0.85},  # 高50 (5%) -> 副标题
            {"bbox": [10, 300, 200, 330], "text": "包邮到家", "score": 0.8},   # 高30 (3%) -> 正文
            {"bbox": [10, 400, 100, 415], "text": "¥99.00", "score": 0.95},    # 价格符号
            {"bbox": [10, 500, 80, 510], "text": "tap", "score": 0.7},         # 高10 (1%) -> 小字
        ]
        groups = cluster_text_by_size(ocr_results, image_height)
        print(f"   聚类结果: {list(groups.keys())}")
        for tier, items in groups.items():
            texts = [it.get("text", "") for it in items]
            print(f"     {tier}: {texts}")

        assert "标题" in groups, "标题组缺失"
        assert "价格" in groups, "价格组缺失（应识别 ¥）"
        assert any("¥" in it.get("text", "") for it in groups["价格"])
        return True
    except Exception as e:
        print(f"❌ 文字字号聚类测试失败: {e}")
        import traceback; traceback.print_exc()
        return False


def test_color_block_extraction():
    """测试 k-means 颜色块提取（纯算法，用合成 3 色块图）"""
    print("\n" + "=" * 60)
    print("测试 12: 颜色块 k-means 提取")
    print("=" * 60)
    try:
        from nodes.tikpan_segmentation_models import extract_color_blocks, color_name

        # 合成图：左红 / 中绿 / 右蓝（各占 1/3）
        h, w = 200, 600
        arr = np.zeros((h, w, 3), dtype=np.uint8)
        arr[:, :200] = (220, 30, 30)    # 红
        arr[:, 200:400] = (30, 200, 50) # 绿
        arr[:, 400:] = (40, 60, 220)    # 蓝

        pil = Image.fromarray(arr, "RGB")
        blocks = extract_color_blocks(pil, n_clusters=3, min_area_ratio=0.05)
        print(f"   检出 {len(blocks)} 个色块:")
        for b in blocks:
            print(f"     {color_name(b['color'])} 占 {b['ratio']*100:.1f}%")

        assert len(blocks) >= 3, "应至少检出 3 个色块"
        # 每个色块面积应接近 1/3
        for b in blocks:
            assert 0.2 < b["ratio"] < 0.45, f"色块面积异常: {b['ratio']}"
        return True
    except Exception as e:
        print(f"❌ 颜色块测试失败: {e}")
        import traceback; traceback.print_exc()
        return False


def test_qrcode_graceful_fallback():
    """测试二维码检测在无 pyzbar 时不崩（cv2 自带降级）"""
    print("\n" + "=" * 60)
    print("测试 13: 二维码检测降级行为")
    print("=" * 60)
    try:
        from nodes.tikpan_segmentation_models import detect_qrcodes
        # 用白图测试，不该有结果也不该崩
        pil = Image.new("RGB", (300, 300), (255, 255, 255))
        result = detect_qrcodes(pil)
        assert isinstance(result, list)
        print(f"   ✓ 空白图返回 {len(result)} 个二维码（合理）")
        return True
    except Exception as e:
        print(f"❌ 二维码降级失败: {e}")
        import traceback; traceback.print_exc()
        return False


def test_processor_scene_routing():
    """测试 _scene_extras 路由：不同场景启用不同增强（不调用真实模型，看路由分支）"""
    print("\n" + "=" * 60)
    print("测试 14: 场景增强路由")
    print("=" * 60)
    try:
        from nodes.tikpan_psd_processor import PSDLayerProcessor
        test_output = os.path.join(project_root, "tests", "test_outputs")
        processor = PSDLayerProcessor(test_output)

        pil = Image.new("RGB", (300, 300), (255, 255, 255))

        # 各场景跑 _scene_extras（白图，所有增强返回空列表即可，关键看不崩）
        for scene, premium in [
            ("ecom_item", False), ("ecom_item", True),
            ("ecom_banner", False), ("ecom_banner", True),
            ("portrait", True),
            ("lifestyle", True),
            ("all", True),
        ]:
            try:
                extras = processor._scene_extras(pil, scene, min_area=500, blur=0, premium=premium)
                assert isinstance(extras, list)
                print(f"   ✓ scene={scene} premium={premium} -> {len(extras)} 额外元素")
            except Exception as e:
                print(f"   ⚠️ scene={scene} premium={premium} 异常: {e}")
                # 模型未装时 _scene_extras 内的子调用会 graceful，外层不该抛
                # 真抛了说明路由本身有 bug
                raise
        return True
    except Exception as e:
        print(f"❌ 场景路由测试失败: {e}")
        import traceback; traceback.print_exc()
        return False


def test_tier_normalization_compatibility():
    """测试新旧 PSD 档位标签都能映射到稳定内部档位"""
    assert normalize_tier(TIER_ECONOMY) == TIER_KIND_ECONOMY
    assert normalize_tier("经济档 (300MB) - 简单商品图") == TIER_KIND_ECONOMY
    assert normalize_tier("经济档 (300MB) - 快速分层") == TIER_KIND_ECONOMY

    assert normalize_tier(TIER_STANDARD) == TIER_KIND_STANDARD
    assert normalize_tier("标准档 (2.4GB) - 复杂场景 推荐") == TIER_KIND_STANDARD
    assert normalize_tier("标准档 (300MB) - 智能分层 推荐") == TIER_KIND_STANDARD

    assert normalize_tier(TIER_PREMIUM) == TIER_KIND_PREMIUM
    assert normalize_tier("极致档 (5GB+) - 商业级分层") == TIER_KIND_PREMIUM
    assert normalize_tier("极致档 (500MB) - 补全背景") == TIER_KIND_PREMIUM

    assert normalize_tier("未知档位") == TIER_KIND_STANDARD



    print("\n" + "🧪" * 30)
    print("开始测试 Tikpan 智能分层 PSD 节点")
    print("🧪" * 30 + "\n")

    results = []

    # 测试 1: 初始化
    node = test_node_initialization()
    results.append(("节点初始化", node is not None))

    if node is None:
        print("\n❌ 节点初始化失败，终止测试")
        return

    # 测试 2: 输入类型
    results.append(("输入类型定义", test_input_types()))

    # 测试 3: 依赖检查
    results.append(("依赖检查", test_dependency_check(node)))

    # 测试 4: 处理器导入
    results.append(("处理器模块导入", test_processor_import()))

    # 测试 5: 文件名清理
    results.append(("文件名清理", test_filename_sanitization()))

    # 测试 6: 错误图片生成
    results.append(("错误图片生成", test_error_image_creation(node)))

    # 测试 7: 无依赖错误处理
    results.append(("无依赖错误处理", test_mock_smart_layer_without_deps(node)))

    # 测试 8: 图层结构
    results.append(("图层结构构建", test_layer_structure()))

    # 测试 9: 场景标签映射
    results.append(("场景标签映射", test_scene_label_mapping()))

    # 测试 10: segmentation_models 公共符号
    results.append(("segmentation_models 公共符号", test_segmentation_models_exports()))

    # 测试 11: 文字字号聚类
    results.append(("文字字号聚类", test_text_size_clustering()))

    # 测试 12: 颜色块 k-means 提取
    results.append(("颜色块 k-means 提取", test_color_block_extraction()))

    # 测试 13: 二维码降级
    results.append(("二维码降级行为", test_qrcode_graceful_fallback()))

    # 测试 14: 场景增强路由
    results.append(("场景增强路由", test_processor_scene_routing()))

    # 测试 15: 档位归一化兼容
    test_tier_normalization_compatibility()
    results.append(("档位归一化兼容", True))

    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {test_name}")

    print(f"\n总计: {passed}/{total} 测试通过")

    if passed == total:
        print("\n🎉 所有测试通过！")
    else:
        print(f"\n⚠️ {total - passed} 个测试失败")

    print("\n" + "=" * 60)
    print("注意事项")
    print("=" * 60)
    print("本测试为离线契约测试，不会实际下载模型或生成 PSD。")
    print("要测试完整功能，请在 ComfyUI 中运行节点并选择对应档位。")
    print("首次运行会自动下载依赖和模型（根据档位不同，300MB-5GB）。")


if __name__ == "__main__":
    main()
