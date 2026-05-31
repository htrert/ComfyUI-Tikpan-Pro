#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ComfyUI Tikpan Pro 节点诊断脚本

请在 ComfyUI 根目录运行：
cd C:/ComfyUI-aki-v2/ComfyUI
python custom_nodes/ComfyUI-Tikpan-Pro/diagnose.py
"""

import sys
import os

print("=" * 70)
print("ComfyUI Tikpan Pro Node Diagnostics")
print("=" * 70)

# 1. 检查文件是否存在
print("\n[1] Checking files...")
base_path = "custom_nodes/ComfyUI-Tikpan-Pro"
files_to_check = [
    "__init__.py",
    "utils/__init__.py",
    "utils/prompts_library.py",
    "nodes/tikpan_prompts_manager.py",
    "nodes/tikpan_prompts_selector.py",
]

for file in files_to_check:
    filepath = os.path.join(base_path, file)
    exists = os.path.exists(filepath)
    status = "[OK]" if exists else "[MISSING]"
    print(f"  {status} {file}")

# 2. 尝试导入模块
print("\n[2] Testing imports...")
sys.path.insert(0, base_path)

try:
    from utils.prompts_library import PROMPT_REPOS, read_all_prompt_cards
    print("  [OK] utils.prompts_library")
except Exception as e:
    print(f"  [ERROR] utils.prompts_library: {e}")

try:
    from nodes.tikpan_prompts_manager import TikpanPromptsManagerNode
    print("  [OK] nodes.tikpan_prompts_manager")
except Exception as e:
    print(f"  [ERROR] nodes.tikpan_prompts_manager: {e}")

try:
    from nodes.tikpan_prompts_selector import TikpanPromptsSelectorNode, TikpanPromptsSearchNode
    print("  [OK] nodes.tikpan_prompts_selector")
except Exception as e:
    print(f"  [ERROR] nodes.tikpan_prompts_selector: {e}")

# 3. 检查 __init__.py 注册
print("\n[3] Checking __init__.py registration...")
try:
    init_file = os.path.join(base_path, "__init__.py")
    with open(init_file, 'r', encoding='utf-8') as f:
        content = f.read()

    nodes_to_check = [
        "TikpanPromptsManagerNode",
        "TikpanPromptsSelectorNode",
        "TikpanPromptsSearchNode"
    ]

    for node in nodes_to_check:
        in_import = f"from .nodes.tikpan_prompts" in content and node in content
        in_mapping = f'"{node}": {node}' in content
        in_display = f'"{node}":' in content and "工具" in content

        status = "[OK]" if (in_import and in_mapping and in_display) else "[ERROR]"
        print(f"  {status} {node}")
        if not (in_import and in_mapping and in_display):
            print(f"       Import: {in_import}, Mapping: {in_mapping}, Display: {in_display}")

except Exception as e:
    print(f"  [ERROR] Failed to check __init__.py: {e}")

# 4. 模拟 ComfyUI 加载
print("\n[4] Simulating ComfyUI node loading...")
try:
    # 清除可能的缓存
    if 'ComfyUI-Tikpan-Pro' in sys.modules:
        del sys.modules['ComfyUI-Tikpan-Pro']

    # 尝试导入
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'tikpan_test',
        os.path.join(base_path, '__init__.py')
    )
    module = importlib.util.module_from_spec(spec)

    # 设置包名（重要！）
    module.__package__ = 'tikpan_test'
    sys.modules['tikpan_test'] = module

    spec.loader.exec_module(module)

    print(f"  [OK] Module loaded")
    print(f"  Total nodes: {len(module.NODE_CLASS_MAPPINGS)}")

    # 检查提示词节点
    prompts_nodes = [k for k in module.NODE_CLASS_MAPPINGS.keys() if 'Prompts' in k]
    print(f"  Prompts nodes found: {len(prompts_nodes)}")
    for node in prompts_nodes:
        display_name = module.NODE_DISPLAY_NAME_MAPPINGS.get(node, "N/A")
        print(f"    - {node}: {display_name}")

except Exception as e:
    print(f"  [ERROR] Module loading failed: {e}")
    import traceback
    traceback.print_exc()

# 5. 检查 Python 缓存
print("\n[5] Checking Python cache...")
pycache_dirs = []
for root, dirs, files in os.walk(base_path):
    if '__pycache__' in dirs:
        pycache_path = os.path.join(root, '__pycache__')
        pycache_dirs.append(pycache_path)

if pycache_dirs:
    print(f"  Found {len(pycache_dirs)} __pycache__ directories")
    print("  Suggestion: Delete these to clear cache:")
    for d in pycache_dirs:
        print(f"    - {d}")
else:
    print("  [OK] No __pycache__ found")

print("\n" + "=" * 70)
print("Diagnostics complete!")
print("=" * 70)
print("\nIf nodes are still not showing in ComfyUI:")
print("1. Delete all __pycache__ directories")
print("2. Restart ComfyUI completely")
print("3. Check ComfyUI console for error messages")
print("4. Try: Ctrl+F5 to refresh browser cache")
