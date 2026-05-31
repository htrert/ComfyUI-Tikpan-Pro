# nodes/tikpan_prompts_manager.py - 提示词库管理器节点

import sys
import os
from pathlib import Path

# 添加父目录到路径以导入 utils
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

try:
    from utils.prompts_library import (
        PROMPT_REPOS,
        sync_prompt_repo,
        read_all_prompt_cards
    )
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    import importlib.util
    utils_path = parent_dir / "utils" / "prompts_library.py"
    spec = importlib.util.spec_from_file_location("prompts_library", utils_path)
    prompts_library = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prompts_library)

    PROMPT_REPOS = prompts_library.PROMPT_REPOS
    sync_prompt_repo = prompts_library.sync_prompt_repo
    read_all_prompt_cards = prompts_library.read_all_prompt_cards


class TikpanPromptsManagerNode:
    """
    提示词库管理器节点

    功能：
    - 同步 GitHub 提示词库（9个仓库）
    - 查看库状态和统计信息
    - 触发同步操作
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "操作": (["查看状态", "同步全部仓库"], {"default": "查看状态"}),
            },
            "optional": {
                "同步单个仓库": ([
                    "全部",
                    "YouMind-OpenLab/awesome-nano-banana-pro-prompts",
                    "EvoLinkAI/awesome-gpt-image-2-API-and-Prompts",
                    "EvoLinkAI/awesome-seedance-2.0-prompts",
                    "EvoLinkAI/awesome-seedance-2-guide",
                    "toki-plus/ai-mixed-cut",
                    "toki-plus/ai-highlight-clip",
                    "toki-plus/ai-ttv-workflow",
                    "toki-plus/video-mover",
                    "shuyu-labs/BigBanana-AI-Director",
                ], {"default": "全部"}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("状态报告",)
    FUNCTION = "execute"
    CATEGORY = "Tikpan Pro/工具"
    OUTPUT_NODE = True

    def execute(self, 操作, 同步单个仓库="全部"):
        """执行提示词库管理操作"""

        if 操作 == "查看状态":
            return self.view_status()
        elif 操作 == "同步全部仓库":
            if 同步单个仓库 == "全部":
                return self.sync_all_repos()
            else:
                return self.sync_single_repo(同步单个仓库)

        return ("未知操作",)

    def view_status(self):
        """查看提示词库状态"""
        try:
            data = read_all_prompt_cards()
            cards = data["cards"]
            repos = data["repos"]

            total_cards = len(cards)

            report_lines = [
                "=" * 60,
                "📚 提示词库状态报告",
                "=" * 60,
                f"总卡片数: {total_cards}",
                f"仓库数量: {len(repos)}",
                "",
                "各仓库详情:",
                "-" * 60
            ]

            for repo in repos:
                slug = repo["slug"]
                count = repo.get("cardCount", 0)
                updated = repo.get("updatedAt", "未同步")
                error = repo.get("error")
                tags = ", ".join(repo.get("tags", []))

                status = "✅" if count > 0 else "⚠️"
                report_lines.append(f"{status} {slug}")
                report_lines.append(f"   卡片数: {count}")
                report_lines.append(f"   标签: {tags}")
                if updated != "未同步":
                    report_lines.append(f"   更新时间: {updated}")
                if error:
                    report_lines.append(f"   ❌ 错误: {error}")
                report_lines.append("")

            report_lines.append("=" * 60)
            report_lines.append("💡 提示: 使用'同步全部仓库'操作来更新提示词库")
            report_lines.append("=" * 60)

            report = "\n".join(report_lines)
            print(report)
            return (report,)

        except Exception as e:
            error_msg = f"❌ 查看状态失败: {str(e)}"
            print(error_msg)
            return (error_msg,)

    def sync_all_repos(self):
        """同步所有仓库"""
        try:
            print("🔄 开始同步所有提示词仓库...")
            print(f"共 {len(PROMPT_REPOS)} 个仓库")

            results = []
            success_count = 0
            total_cards = 0

            for i, repo_entry in enumerate(PROMPT_REPOS, 1):
                slug = repo_entry["slug"]
                print(f"\n[{i}/{len(PROMPT_REPOS)}] 同步: {slug}")

                result = sync_prompt_repo(repo_entry)
                results.append(result)

                if result["error"]:
                    print(f"  ❌ 失败: {result['error']}")
                else:
                    success_count += 1
                    card_count = result["cardCount"]
                    total_cards += card_count
                    print(f"  ✅ 成功: {card_count} 张卡片")

            # 生成报告
            report_lines = [
                "=" * 60,
                "📚 提示词库同步完成",
                "=" * 60,
                f"成功: {success_count}/{len(PROMPT_REPOS)} 个仓库",
                f"总卡片数: {total_cards}",
                "",
                "详细结果:",
                "-" * 60
            ]

            for result in results:
                slug = result["slug"]
                if result["error"]:
                    report_lines.append(f"❌ {slug}: {result['error']}")
                else:
                    report_lines.append(f"✅ {slug}: {result['cardCount']} 张卡片")

            report_lines.append("=" * 60)

            report = "\n".join(report_lines)
            print(f"\n{report}")
            return (report,)

        except Exception as e:
            error_msg = f"❌ 同步失败: {str(e)}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            return (error_msg,)

    def sync_single_repo(self, slug):
        """同步单个仓库"""
        try:
            print(f"🔄 同步单个仓库: {slug}")

            # 查找仓库配置
            repo_entry = None
            for entry in PROMPT_REPOS:
                if entry["slug"] == slug:
                    repo_entry = entry
                    break

            if not repo_entry:
                return (f"❌ 未找到仓库: {slug}",)

            result = sync_prompt_repo(repo_entry)

            if result["error"]:
                msg = f"❌ 同步失败: {result['error']}"
                print(msg)
                return (msg,)
            else:
                msg = f"✅ 同步成功: {slug}\n卡片数: {result['cardCount']}\n更新时间: {result['updatedAt']}"
                print(msg)
                return (msg,)

        except Exception as e:
            error_msg = f"❌ 同步失败: {str(e)}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            return (error_msg,)


# ComfyUI 节点注册
NODE_CLASS_MAPPINGS = {
    "TikpanPromptsManagerNode": TikpanPromptsManagerNode
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TikpanPromptsManagerNode": "工具｜提示词库管理器"
}
