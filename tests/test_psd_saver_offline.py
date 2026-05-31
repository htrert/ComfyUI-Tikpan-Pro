"""
测试 PSD 保存节点
"""
import sys
import os
import torch
import numpy as np
from PIL import Image

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 模拟 ComfyUI 的 folder_paths
class MockFolderPaths:
    @staticmethod
    def get_output_directory():
        test_output = os.path.join(project_root, "tests", "test_outputs")
        os.makedirs(test_output, exist_ok=True)
        return test_output

sys.modules['folder_paths'] = MockFolderPaths()

from nodes.tikpan_psd_saver import TikpanPSDSaverNode


def create_test_image_tensor(width=512, height=512, batch_size=1):
    """创建测试用的图片 tensor"""
    # 创建一个渐变图像
    image = np.zeros((height, width, 3), dtype=np.float32)
    for i in range(height):
        for j in range(width):
            image[i, j, 0] = i / height  # Red gradient
            image[i, j, 1] = j / width   # Green gradient
            image[i, j, 2] = 0.5         # Blue constant

    # 转换为 torch tensor (batch, height, width, channels)
    tensor = torch.from_numpy(image).unsqueeze(0)
    if batch_size > 1:
        tensor = tensor.repeat(batch_size, 1, 1, 1)

    return tensor


def test_node_initialization():
    """测试节点初始化"""
    print("=" * 60)
    print("测试 1: 节点初始化")
    print("=" * 60)

    try:
        node = TikpanPSDSaverNode()
        print("✅ 节点初始化成功")
        print(f"   输出目录: {node.output_dir}")
        print(f"   psd-tools 可用: {node.psd_tools_available}")
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
        input_types = TikpanPSDSaverNode.INPUT_TYPES()
        print("✅ 输入类型定义正确")
        print(f"   必需参数: {list(input_types['required'].keys())}")
        print(f"   可选参数: {list(input_types.get('optional', {}).keys())}")
        return True
    except Exception as e:
        print(f"❌ 输入类型定义失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_pillow_mode(node):
    """测试标准模式（Pillow）"""
    print("\n" + "=" * 60)
    print("测试 3: 标准模式（Pillow）保存")
    print("=" * 60)

    try:
        # 创建测试图片
        test_tensor = create_test_image_tensor(256, 256, 1)
        print(f"   创建测试图片: shape={test_tensor.shape}")

        # 调用保存方法
        result_path, log = node.save_psd(
            输入图片=test_tensor,
            文件名="test_pillow_mode",
            PSD质量="标准 (Pillow)",
            自动安装依赖="否",
            保存路径=""
        )

        print(f"✅ 标准模式保存成功")
        print(f"   返回路径: {result_path}")
        print(f"   日志:\n{log}")

        # 验证文件是否存在
        if os.path.exists(result_path):
            file_size = os.path.getsize(result_path)
            print(f"   文件大小: {file_size} bytes")

            # 尝试用 PIL 读取验证
            try:
                psd_img = Image.open(result_path)
                print(f"   PSD 验证: 尺寸={psd_img.size}, 模式={psd_img.mode}")
            except Exception as e:
                print(f"   ⚠️ PSD 读取警告: {e}")
        else:
            print(f"   ⚠️ 文件未找到: {result_path}")

        return True
    except Exception as e:
        print(f"❌ 标准模式保存失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_advanced_mode(node):
    """测试高级模式（psd-tools）"""
    print("\n" + "=" * 60)
    print("测试 4: 高级模式（psd-tools）保存")
    print("=" * 60)

    try:
        # 创建测试图片
        test_tensor = create_test_image_tensor(256, 256, 1)
        print(f"   创建测试图片: shape={test_tensor.shape}")

        # 调用保存方法（允许自动安装）
        result_path, log = node.save_psd(
            输入图片=test_tensor,
            文件名="test_advanced_mode",
            PSD质量="高级 (psd-tools)",
            自动安装依赖="是",
            保存路径=""
        )

        print(f"✅ 高级模式保存完成")
        print(f"   返回路径: {result_path}")
        print(f"   日志:\n{log}")

        # 验证文件是否存在
        if os.path.exists(result_path):
            file_size = os.path.getsize(result_path)
            print(f"   文件大小: {file_size} bytes")
        else:
            print(f"   ⚠️ 文件未找到: {result_path}")

        return True
    except Exception as e:
        print(f"❌ 高级模式保存失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_multi_layer(node):
    """测试多图层保存"""
    print("\n" + "=" * 60)
    print("测试 5: 多图层保存")
    print("=" * 60)

    try:
        # 创建多张测试图片
        test_tensor = create_test_image_tensor(256, 256, batch_size=3)
        print(f"   创建测试图片: shape={test_tensor.shape} (3层)")

        # 调用保存方法
        result_path, log = node.save_psd(
            输入图片=test_tensor,
            文件名="test_multi_layer",
            PSD质量="高级 (psd-tools)",
            自动安装依赖="是",
            保存路径=""
        )

        print(f"✅ 多图层保存完成")
        print(f"   返回路径: {result_path}")
        print(f"   日志:\n{log}")

        # 验证文件是否存在
        if os.path.exists(result_path):
            file_size = os.path.getsize(result_path)
            print(f"   文件大小: {file_size} bytes")
        else:
            print(f"   ⚠️ 文件未找到: {result_path}")

        return True
    except Exception as e:
        print(f"❌ 多图层保存失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_filename_sanitization(node):
    """测试文件名清理"""
    print("\n" + "=" * 60)
    print("测试 6: 文件名清理")
    print("=" * 60)

    try:
        test_tensor = create_test_image_tensor(128, 128, 1)

        # 测试非法文件名
        illegal_name = "test<>:file|name?.psd"
        result_path, log = node.save_psd(
            输入图片=test_tensor,
            文件名=illegal_name,
            PSD质量="标准 (Pillow)",
            自动安装依赖="否",
            保存路径=""
        )

        print(f"✅ 文件名清理成功")
        print(f"   原始文件名: {illegal_name}")
        print(f"   清理后路径: {result_path}")

        if os.path.exists(result_path):
            print(f"   文件已创建")

        return True
    except Exception as e:
        print(f"❌ 文件名清理失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "🧪" * 30)
    print("开始测试 Tikpan PSD 保存节点")
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

    # 测试 3: 标准模式
    results.append(("标准模式保存", test_pillow_mode(node)))

    # 测试 4: 高级模式
    results.append(("高级模式保存", test_advanced_mode(node)))

    # 测试 5: 多图层
    results.append(("多图层保存", test_multi_layer(node)))

    # 测试 6: 文件名清理
    results.append(("文件名清理", test_filename_sanitization(node)))

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


if __name__ == "__main__":
    main()
