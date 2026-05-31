# nodes/tikpan_prompts_selector.py - 提示词选择器节点

import sys
from pathlib import Path

# 添加父目录到路径以导入 utils
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.prompts_library import (
    read_all_prompt_cards,
    filter_cards,
    PROMPT_REPOS
)


class TikpanPromptsSelectorNode:
    """
    提示词选择器节点

    功能：
    - 从本地提示词库中选择提示词
    - 支持按标签、仓库过滤
    - 支持搜索关键词
    - 输出提示词文本供其他节点使用
    """

    @classmethod
    def INPUT_TYPES(cls):
        # 读取所有卡片用于生成选项
        try:
            data = read_all_prompt_cards()
            cards = data["cards"]

            # 生成卡片选项（显示标题）
            card_options = ["(请先同步提示词库)"]
            if cards:
                card_options = [f"{i+1}. {card.title[:60]}" for i, card in enumerate(cards[:200])]

            # 生成仓库选项
            repo_options = ["全部"] + [repo["slug"] for repo in PROMPT_REPOS]

            # 生成标签选项
            all_tags = set()
            for card in cards:
                all_tags.update(card.tags)
            tag_options = ["全部"] + sorted(list(all_tags))

        except Exception as e:
            print(f"读取提示词库失败: {e}")
            card_options = ["(请先同步提示词库)"]
            repo_options = ["全部"]
            tag_options = ["全部"]

        return {
            "required": {
                "选择提示词": (card_options, {"default": card_options[0]}),
            },
            "optional": {
                "过滤_仓库": (repo_options, {"default": "全部"}),
                "过滤_标签": (tag_options, {"default": "全部"}),
                "搜索关键词": ("STRING", {"default": "", "multiline": False}),
                "显示详情": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("提示词文本", "卡片标题", "卡片详情")
    FUNCTION = "execute"
    CATEGORY = "Tikpan Pro/工具"

    def execute(self, 选择提示词, 过滤_仓库="全部", 过滤_标签="全部", 搜索关键词="", 显示详情=True):
        """执行提示词选择"""
        try:
            # 读取所有卡片
            data = read_all_prompt_cards()
            cards = data["cards"]

            if not cards:
                return (
                    "请先使用'提示词库管理器'节点同步提示词库",
                    "未找到提示词",
                    "提示词库为空"
                )

            # 应用过滤
            filtered_cards = cards

            # 按仓库过滤
            if 过滤_仓库 != "全部":
                filtered_cards = [c for c in filtered_cards if c.repo == 过滤_仓库]

            # 按标签过滤
            if 过滤_标签 != "全部":
                filtered_cards = [c for c in filtered_cards if 过滤_标签 in c.tags]

            # 按搜索关键词过滤
            if 搜索关键词.strip():
                search_lower = 搜索关键词.lower()
                filtered_cards = [
                    c for c in filtered_cards
                    if search_lower in c.title.lower()
                    or search_lower in c.prompt.lower()
                    or search_lower in c.body.lower()
                ]

            if not filtered_cards:
                return (
                    "未找到匹配的提示词",
                    "无结果",
                    f"过滤条件: 仓库={过滤_仓库}, 标签={过滤_标签}, 关键词={搜索关键词}"
                )

            # 解析选择的卡片索引
            try:
                # 从 "1. 标题" 格式中提取索引
                index_str = 选择提示词.split(".")[0]
                card_index = int(index_str) - 1

                # 确保索引在范围内
                if card_index < 0 or card_index >= len(filtered_cards):
                    card_index = 0

            except (ValueError, IndexError):
                card_index = 0

            # 获取选中的卡片
            selected_card = filtered_cards[card_index]

            # 生成详情信息
            details_lines = [
                "=" * 60,
                f"📝 {selected_card.title}",
                "=" * 60,
                f"来源: {selected_card.repo}",
                f"标签: {', '.join(selected_card.tags)}",
                f"链接: {selected_card.url}",
                "",
                "提示词内容:",
                "-" * 60,
                selected_card.prompt,
                "",
            ]

            if selected_card.body:
                details_lines.extend([
                    "上下文:",
                    "-" * 60,
                    selected_card.body[:300] + ("..." if len(selected_card.body) > 300 else ""),
                    ""
                ])

            details_lines.append("=" * 60)
            details = "\n".join(details_lines)

            if 显示详情:
                print(details)

            return (
                selected_card.prompt,
                selected_card.title,
                details
            )

        except Exception as e:
            error_msg = f"❌ 选择提示词失败: {str(e)}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            return (error_msg, "错误", error_msg)


class TikpanPromptsSearchNode:
    """
    提示词搜索节点（高级版）

    功能：
    - 更灵活的搜索和过滤
    - 返回多个匹配结果
    - 支持按相关度排序
    """

    @classmethod
    def INPUT_TYPES(cls):
        # 生成仓库和标签选项
        try:
            data = read_all_prompt_cards()
            cards = data["cards"]

            repo_options = ["全部"] + [repo["slug"] for repo in PROMPT_REPOS]

            all_tags = set()
            for card in cards:
                all_tags.update(card.tags)
            tag_options = ["全部"] + sorted(list(all_tags))

        except Exception:
            repo_options = ["全部"]
            tag_options = ["全部"]

        return {
            "required": {
                "搜索关键词": ("STRING", {"default": "", "multiline": False}),
            },
            "optional": {
                "过滤_仓库": (repo_options, {"default": "全部"}),
                "过滤_标签": (tag_options, {"default": "全部"}),
                "最多返回数量": ("INT", {"default": 10, "min": 1, "max": 50}),
                "结果索引": ("INT", {"default": 0, "min": 0, "max": 49}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "INT")
    RETURN_NAMES = ("提示词文本", "卡片标题", "搜索结果列表", "结果总数")
    FUNCTION = "execute"
    CATEGORY = "Tikpan Pro/工具"

    def execute(self, 搜索关键词, 过滤_仓库="全部", 过滤_标签="全部", 最多返回数量=10, 结果索引=0):
        """执行提示词搜索"""
        try:
            # 读取所有卡片
            data = read_all_prompt_cards()
            cards = data["cards"]

            if not cards:
                return (
                    "请先使用'提示词库管理器'节点同步提示词库",
                    "未找到提示词",
                    "提示词库为空",
                    0
                )

            # 应用过滤
            filtered_cards = filter_cards(
                cards,
                repo=过滤_仓库 if 过滤_仓库 != "全部" else None,
                tags=[过滤_标签] if 过滤_标签 != "全部" else None,
                search=搜索关键词 if 搜索关键词.strip() else None
            )

            if not filtered_cards:
                return (
                    "未找到匹配的提示词",
                    "无结果",
                    f"搜索条件: 关键词='{搜索关键词}', 仓库={过滤_仓库}, 标签={过滤_标签}",
                    0
                )

            # 限制返回数量
            result_cards = filtered_cards[:最多返回数量]
            total_count = len(filtered_cards)

            # 生成结果列表
            result_lines = [
                "=" * 60,
                f"🔍 搜索结果 (共 {total_count} 条，显示前 {len(result_cards)} 条)",
                "=" * 60,
            ]

            for i, card in enumerate(result_cards):
                result_lines.append(f"\n[{i}] {card.title}")
                result_lines.append(f"    仓库: {card.repo}")
                result_lines.append(f"    标签: {', '.join(card.tags)}")
                result_lines.append(f"    预览: {card.prompt[:100]}...")

            result_lines.append("\n" + "=" * 60)
            result_list = "\n".join(result_lines)

            # 获取指定索引的卡片
            if 结果索引 < len(result_cards):
                selected_card = result_cards[结果索引]
                print(f"✅ 选中第 {结果索引} 条: {selected_card.title}")
                return (
                    selected_card.prompt,
                    selected_card.title,
                    result_list,
                    total_count
                )
            else:
                print(f"⚠️ 索引 {结果索引} 超出范围，返回第一条结果")
                selected_card = result_cards[0]
                return (
                    selected_card.prompt,
                    selected_card.title,
                    result_list,
                    total_count
                )

        except Exception as e:
            error_msg = f"❌ 搜索失败: {str(e)}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            return (error_msg, "错误", error_msg, 0)


# ComfyUI 节点注册
NODE_CLASS_MAPPINGS = {
    "TikpanPromptsSelectorNode": TikpanPromptsSelectorNode,
    "TikpanPromptsSearchNode": TikpanPromptsSearchNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TikpanPromptsSelectorNode": "工具｜提示词选择器",
    "TikpanPromptsSearchNode": "工具｜提示词搜索",
}
