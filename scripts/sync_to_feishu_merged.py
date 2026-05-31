"""
飞书文档合并同步脚本：把多个 Markdown 文件合并到一个飞书文档
"""
import json
import os
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from scripts.sync_to_feishu import FeishuClient, load_config


def merge_markdown_files():
    """合并多个 Markdown 文件为一个大文档"""
    files_to_merge = [
        ("节点使用教程", "docs/节点使用教程.md"),
        ("节点速查表", "docs/节点速查表.md"),
        ("节点功能分类", "docs/Tikpan_ComfyUI_节点功能分类.md"),
        ("更新日志", "CHANGELOG.md"),
    ]

    merged_content = "# ComfyUI-Tikpan-Pro 完整文档\n\n"
    merged_content += "> 📚 本文档由多个 Markdown 文件自动合并生成  \n"
    merged_content += f"> 🕐 生成时间：{__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n"
    merged_content += "> 🔗 官方网站：https://tikpan.com\n\n"

    # 添加目录
    merged_content += "## 📑 文档目录\n\n"
    for idx, (title, _) in enumerate(files_to_merge, 1):
        merged_content += f"{idx}. [{title}](#{title})\n"
    merged_content += "\n---\n\n"

    for title, file_path in files_to_merge:
        full_path = project_root / file_path
        if not full_path.exists():
            print(f"[WARN] File not found, skipping: {file_path}")
            continue

        print(f"[READ] {file_path}")
        content = full_path.read_text(encoding="utf-8")

        # 移除原文档的一级标题（避免重复）
        lines = content.splitlines()
        cleaned_lines = []
        skip_first_h1 = True

        for line in lines:
            # 跳过第一个一级标题
            if skip_first_h1 and line.strip().startswith("# "):
                skip_first_h1 = False
                continue
            # 跳过顶部的引用块（> 开头的元信息）
            if line.strip().startswith(">") and len(cleaned_lines) < 10:
                continue
            cleaned_lines.append(line)

        cleaned_content = "\n".join(cleaned_lines).strip()

        # 添加章节标题（使用一级标题）
        merged_content += f"# {title}\n\n"
        merged_content += cleaned_content
        merged_content += "\n\n---\n\n"

    return merged_content


def sync_merged_document(document_id: str):
    """同步合并后的文档到飞书"""
    print("=" * 60)
    print("Feishu Document Merge Sync")
    print("=" * 60)

    # 加载配置
    config = load_config()
    app_id = config.get("app_id", "").strip()
    app_secret = config.get("app_secret", "").strip()

    if not app_id or not app_secret:
        print("[ERROR] Missing app_id or app_secret in config")
        return False

    # 创建客户端
    client = FeishuClient(app_id, app_secret)

    # 合并 Markdown 文件
    print("\n[STEP 1] Merging Markdown files...")
    merged_markdown = merge_markdown_files()
    print(f"[OK] Merged, total length: {len(merged_markdown)} chars\n")

    # 清空旧内容
    print(f"[STEP 2] Syncing to document: {document_id[:8]}...")
    try:
        blocks = client.get_document_blocks(document_id)
        if len(blocks) > 1:
            root = blocks[0]
            children = root.get("children", [])
            if children:
                client.delete_blocks(document_id, root["block_id"], 0, len(children))
                print(f"  [OK] Cleared old content: {len(children)} blocks")
    except Exception as e:
        print(f"  [WARN] Failed to clear old content (maybe new doc): {e}")

    # 写入新内容
    print("  [STEP 3] Writing new content...")
    try:
        client.create_blocks_from_markdown(document_id, merged_markdown)
        print("  [OK] Sync completed")
        return True
    except Exception as e:
        print(f"  [ERROR] Sync failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python scripts/sync_to_feishu_merged.py <飞书文档ID>")
        print("\n示例:")
        print("  python scripts/sync_to_feishu_merged.py doxcABCdefGHIjklMNOpqrSTUvwx")
        print("\n说明:")
        print("  将会把以下 4 个文件合并同步到一个飞书文档:")
        print("    - docs/节点使用教程.md")
        print("    - docs/节点速查表.md")
        print("    - docs/Tikpan_ComfyUI_节点功能分类.md")
        print("    - CHANGELOG.md")
        sys.exit(1)

    document_id = sys.argv[1].strip()

    if not document_id:
        print("❌ 文档 ID 不能为空")
        sys.exit(1)

    success = sync_merged_document(document_id)

    if success:
        print("\n[SUCCESS] Merge sync completed!")
        print(f"[LINK] Open in Feishu: https://feishu.cn/docx/{document_id}")
    else:
        print("\n[ERROR] Sync failed, please check error messages")
        sys.exit(1)


if __name__ == "__main__":
    main()
