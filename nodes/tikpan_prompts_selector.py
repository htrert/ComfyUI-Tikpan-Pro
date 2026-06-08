# nodes/tikpan_prompts_selector.py - 提示词选择器节点

import sys
import os
import re
from pathlib import Path

from .tikpan_categories import CATEGORY_PROMPT_LIBRARY

# 添加父目录到路径以导入 utils
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

try:
    from utils.prompts_library import (
        read_all_prompt_cards,
        filter_cards,
        PROMPT_REPOS
    )
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    import importlib.util
    utils_path = parent_dir / "utils" / "prompts_library.py"
    spec = importlib.util.spec_from_file_location("prompts_library", utils_path)
    prompts_library = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prompts_library)

    read_all_prompt_cards = prompts_library.read_all_prompt_cards
    filter_cards = prompts_library.filter_cards
    PROMPT_REPOS = prompts_library.PROMPT_REPOS


class TikpanPromptsSelectorNode:
    """
    提示词选择器节点

    功能：
    - 从本地提示词库中选择提示词
    - 支持按标签、仓库过滤
    - 支持搜索关键词
    - 输出提示词文本供其他节点使用

    子类可通过 CARD_TYPE_FILTER 限定只显示某类卡片(image/video)
    """

    # None = 不过滤(显示全部);"image" = 只显示图片卡片;"video" = 只显示视频卡片
    CARD_TYPE_FILTER = None
    EMPTY_HINT = "(请先同步提示词库)"

    @classmethod
    def _scoped_cards(cls):
        """读取并按 CARD_TYPE_FILTER 过滤后的卡片列表"""
        data = read_all_prompt_cards()
        cards = data["cards"]
        if cls.CARD_TYPE_FILTER:
            cards = [c for c in cards if cls.CARD_TYPE_FILTER in c.tags]
        return cards

    @classmethod
    def INPUT_TYPES(cls):
        try:
            cards = cls._scoped_cards()

            # 生成卡片选项(优先中文,回退英文)
            card_options = [cls.EMPTY_HINT]
            if cards:
                card_options = []
                for i, card in enumerate(cards[:800]):
                    title = (card.title_zh or card.title or "Untitled")[:50]
                    raw_preview = card.prompt_preview_zh or card.prompt or ""
                    preview = re.sub(r'\s+', ' ', raw_preview.strip())[:40]
                    label = f"{i+1}. {title} — {preview}" if preview else f"{i+1}. {title}"
                    card_options.append(label[:140])

            # 仓库选项:专用选择器只列含该类型卡片的仓库
            if cls.CARD_TYPE_FILTER:
                involved_repos = sorted(set(c.repo for c in cards))
                repo_options = ["全部"] + involved_repos
            else:
                repo_options = ["全部"] + [repo["slug"] for repo in PROMPT_REPOS]

            # 标签选项:专用选择器排除自身定位标签,避免冗余
            all_tags = set()
            for card in cards:
                all_tags.update(card.tags)
            if cls.CARD_TYPE_FILTER:
                all_tags.discard(cls.CARD_TYPE_FILTER)
            tag_options = ["全部"] + sorted(list(all_tags))

        except Exception as e:
            print(f"读取提示词库失败: {e}")
            card_options = [cls.EMPTY_HINT]
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
    CATEGORY = CATEGORY_PROMPT_LIBRARY

    def execute(self, 选择提示词, 过滤_仓库="全部", 过滤_标签="全部", 搜索关键词="", 显示详情=True):
        """执行提示词选择"""
        try:
            # 同 INPUT_TYPES 使用相同的卡片范围,确保索引一致
            cards = self._scoped_cards()

            if not cards:
                scope = f"({self.CARD_TYPE_FILTER})" if self.CARD_TYPE_FILTER else ""
                return (
                    f"请先使用'提示词库管理器'节点同步提示词库{scope}",
                    "未找到提示词",
                    "提示词库为空"
                )

            # 优先按下拉选择的索引精确取卡片(索引基于过滤后的卡片列表,与 INPUT_TYPES 一致)
            selected_card = None
            m = re.match(r'^(\d+)\.', 选择提示词)
            if m:
                idx = int(m.group(1)) - 1
                if 0 <= idx < len(cards):
                    selected_card = cards[idx]

            # 下拉为占位符时,按过滤条件返回第一个匹配(兼容旧用法)
            if selected_card is None:
                filtered_cards = cards
                if 过滤_仓库 != "全部":
                    filtered_cards = [c for c in filtered_cards if c.repo == 过滤_仓库]
                if 过滤_标签 != "全部":
                    filtered_cards = [c for c in filtered_cards if 过滤_标签 in c.tags]
                if 搜索关键词.strip():
                    s = 搜索关键词.lower()
                    filtered_cards = [
                        c for c in filtered_cards
                        if s in c.title.lower() or s in c.prompt.lower() or s in c.body.lower()
                    ]
                if not filtered_cards:
                    return (
                        "未找到匹配的提示词",
                        "无结果",
                        f"过滤条件: 仓库={过滤_仓库}, 标签={过滤_标签}, 关键词={搜索关键词}"
                    )
                selected_card = filtered_cards[0]

            # 生成详情信息
            title_line = selected_card.title
            if selected_card.title_zh and selected_card.title_zh != selected_card.title:
                title_line = f"{selected_card.title_zh}  ({selected_card.title})"
            details_lines = [
                "=" * 60,
                f"📝 {title_line}",
                "=" * 60,
                f"来源: {selected_card.repo}",
                f"标签: {', '.join(selected_card.tags)}",
                f"链接: {selected_card.url}",
                "",
            ]
            if selected_card.prompt_preview_zh:
                details_lines.extend([
                    "中文预览:",
                    "-" * 60,
                    selected_card.prompt_preview_zh,
                    "",
                ])
            details_lines.extend([
                "提示词内容(原文):",
                "-" * 60,
                selected_card.prompt,
                "",
            ])

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
    CATEGORY = CATEGORY_PROMPT_LIBRARY

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


class TikpanPromptsImageSelectorNode(TikpanPromptsSelectorNode):
    """图片提示词选择器:下拉框只显示带 image 标签的卡片
    (覆盖 GPT-Image-2 / Nano Banana 等图像生成模型)
    """
    CARD_TYPE_FILTER = "image"
    EMPTY_HINT = "(请先同步提示词库,或当前无图片类卡片)"


class TikpanPromptsVideoSelectorNode(TikpanPromptsSelectorNode):
    """视频提示词选择器:下拉框只显示带 video 标签的卡片
    (覆盖 Seedance 等视频生成模型)
    """
    CARD_TYPE_FILTER = "video"
    EMPTY_HINT = "(请先同步提示词库,或当前无视频类卡片)"


# ComfyUI 节点注册
NODE_CLASS_MAPPINGS = {
    "TikpanPromptsSelectorNode": TikpanPromptsSelectorNode,
    "TikpanPromptsImageSelectorNode": TikpanPromptsImageSelectorNode,
    "TikpanPromptsVideoSelectorNode": TikpanPromptsVideoSelectorNode,
    "TikpanPromptsSearchNode": TikpanPromptsSearchNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TikpanPromptsSelectorNode": "工具｜提示词选择器·全部",
    "TikpanPromptsImageSelectorNode": "工具｜提示词选择器·图片",
    "TikpanPromptsVideoSelectorNode": "工具｜提示词选择器·视频",
    "TikpanPromptsSearchNode": "工具｜提示词搜索",
}
