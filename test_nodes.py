#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 Tikpan Pro 节点注册

在 ComfyUI 环境中运行此脚本：
cd C:/ComfyUI-aki-v2/ComfyUI
python custom_nodes/ComfyUI-Tikpan-Pro/test_nodes.py
"""

import sys
import os

# 添加 ComfyUI 路径
comfy_path = os.path.dirname(os.path.abspath(__file__))
if comfy_path not in sys.path:
    sys.path.insert(0, comfy_path)

print("=" * 60)
print("Tikpan Pro Nodes Registration Test")
print("=" * 60)

try:
    # 导入节点模块
    from nodes.tikpan_prompts_manager import TikpanPromptsManagerNode
    from nodes.tikpan_prompts_selector import TikpanPromptsSelectorNode, TikpanPromptsSearchNode

    print("\n[OK] Prompts nodes imported successfully")

    # 测试节点类
    nodes = [
        ("TikpanPromptsManagerNode", TikpanPromptsManagerNode),
        ("TikpanPromptsSelectorNode", TikpanPromptsSelectorNode),
        ("TikpanPromptsSearchNode", TikpanPromptsSearchNode),
    ]

    print("\nNode checks:")
    for name, node_class in nodes:
        try:
            # 检查必需的属性
            assert hasattr(node_class, 'INPUT_TYPES'), f"{name} missing INPUT_TYPES"
            assert hasattr(node_class, 'RETURN_TYPES'), f"{name} missing RETURN_TYPES"
            assert hasattr(node_class, 'FUNCTION'), f"{name} missing FUNCTION"
            assert hasattr(node_class, 'CATEGORY'), f"{name} missing CATEGORY"

            # 测试 INPUT_TYPES 调用
            inputs = node_class.INPUT_TYPES()
            assert isinstance(inputs, dict), f"{name} INPUT_TYPES not returning dict"

            print(f"  [OK] {name}")
            print(f"    - Category: {node_class.CATEGORY}")
            print(f"    - Function: {node_class.FUNCTION}")
            print(f"    - Returns: {node_class.RETURN_TYPES}")

        except Exception as e:
            print(f"  [ERROR] {name}: {e}")

    print("\n" + "=" * 60)
    print("Test completed! All nodes are OK.")
    print("=" * 60)

except Exception as e:
    print(f"\n[ERROR] Import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
