# utils/prompts_library.py - 提示词库管理工具

import os
import json
import re
from typing import List, Dict, Optional, Set
from pathlib import Path
import urllib.request
import urllib.error

# 提示词库存储目录
PROMPTS_LIBRARY_DIR = Path(__file__).parent.parent / "data" / "prompts-library"

# GitHub 提示词仓库列表（复刻自 tikpan-canvas）
PROMPT_REPOS = [
    {"slug": "YouMind-OpenLab/awesome-nano-banana-pro-prompts", "tags": ["nano-banana", "image"]},
    {"slug": "EvoLinkAI/awesome-gpt-image-2-API-and-Prompts", "tags": ["gpt-image-2", "image"]},
    {"slug": "EvoLinkAI/awesome-seedance-2.0-prompts", "tags": ["seedance", "video"]},
    {"slug": "EvoLinkAI/awesome-seedance-2-guide", "tags": ["seedance", "guide"]},
    {"slug": "toki-plus/ai-mixed-cut", "tags": ["video-edit", "mixed-cut"]},
    {"slug": "toki-plus/ai-highlight-clip", "tags": ["video-edit", "highlight"]},
    {"slug": "toki-plus/ai-ttv-workflow", "tags": ["text-to-video", "workflow"]},
    {"slug": "toki-plus/video-mover", "tags": ["video-edit", "mover"]},
    {"slug": "shuyu-labs/BigBanana-AI-Director", "tags": ["director", "orchestration"]},
]


class PromptCard:
    """提示词卡片数据结构"""

    def __init__(self, id: str, repo: str, title: str, prompt: str,
                 body: str = "", tags: List[str] = None, url: str = ""):
        self.id = id
        self.repo = repo
        self.title = title
        self.prompt = prompt
        self.body = body
        self.tags = tags or []
        self.url = url

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "repo": self.repo,
            "title": self.title,
            "prompt": self.prompt,
            "body": self.body,
            "tags": self.tags,
            "url": self.url
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'PromptCard':
        return cls(
            id=data.get("id", ""),
            repo=data.get("repo", ""),
            title=data.get("title", ""),
            prompt=data.get("prompt", ""),
            body=data.get("body", ""),
            tags=data.get("tags", []),
            url=data.get("url", "")
        )


def safe_name(name: str, prefix: str = "") -> str:
    """生成安全的文件名"""
    cleaned = re.sub(r'[^\w\-_.]', '_', name)
    return f"{prefix}_{cleaned}" if prefix else cleaned


def slug_to_filename(slug: str) -> str:
    """将 GitHub slug 转换为文件名"""
    return safe_name(slug.replace("/", "__"), "repo") + ".json"


def fetch_readme(slug: str) -> Optional[Dict[str, str]]:
    """从 GitHub 获取 README 内容"""
    urls = [
        f"https://raw.githubusercontent.com/{slug}/main/README.md",
        f"https://raw.githubusercontent.com/{slug}/master/README.md",
        f"https://raw.githubusercontent.com/{slug}/main/README_zh.md",
        f"https://raw.githubusercontent.com/{slug}/main/README-zh.md",
    ]

    for url in urls:
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "ComfyUI-Tikpan-Pro/1.0"}
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                if response.status == 200:
                    text = response.read().decode('utf-8')
                    if text and len(text) > 50:
                        return {"text": text, "url": url}
        except (urllib.error.URLError, urllib.error.HTTPError, Exception):
            continue

    return None


def parse_readme_prompts(markdown: str, repo: str, base_tags: List[str] = None) -> List[PromptCard]:
    """解析 README markdown 为提示词卡片列表"""
    if not markdown:
        return []

    base_tags = base_tags or []
    lines = markdown.split('\n')
    sections = []
    current = None

    # 按 H2 标题分段
    for line in lines:
        h2_match = re.match(r'^##\s+(.+?)\s*$', line)
        if h2_match:
            if current:
                sections.append(current)
            current = {"title": h2_match.group(1).strip(), "lines": []}
            continue
        if current:
            current["lines"].append(line)

    if current:
        sections.append(current)

    cards = []
    counter = 0

    for sec in sections:
        title = sec["title"]

        # 跳过目录、许可证等章节
        if re.search(r'^(目录|Table of Contents|Contents|License|Star History|贡献者|Contributors)',
                     title, re.IGNORECASE):
            continue

        text = '\n'.join(sec["lines"])

        # 提取 prompt（优先级：代码块 > blockquote > 长段落）
        prompt = ""

        # 1. 尝试提取代码块
        fence_match = re.search(r'```[a-zA-Z0-9_+-]*\n([\s\S]*?)```', text)
        if fence_match:
            prompt = fence_match.group(1).strip()

        # 2. 尝试提取 blockquote
        if not prompt:
            quoted_match = re.search(r'(?:^|\n)>\s+([^\n]+(?:\n>\s+[^\n]+)*)', text)
            if quoted_match:
                prompt = re.sub(r'\n>\s+', '\n', quoted_match.group(1)).strip()

        # 3. 尝试提取第一个有效段落
        if not prompt:
            paragraphs = re.split(r'\n{2,}', text)
            for para in paragraphs:
                cleaned = para.strip()
                if len(cleaned) < 30:
                    continue
                if re.match(r'^!\[', cleaned):  # 图片
                    continue
                if re.match(r'^\[.+?\]\(.+?\)$', cleaned):  # 纯链接
                    continue
                if re.match(r'^(#|<|---|\|)', cleaned):  # 标题/HTML/分隔符/表格
                    continue
                prompt = cleaned
                break

        if not prompt:
            continue

        # 提取额外标签
        extra_tags: Set[str] = set()
        tag_match = re.search(r'^\s*(?:Tags?|标签|Model|模型)[:：]\s*(.+)$', text, re.IGNORECASE | re.MULTILINE)
        if tag_match:
            tag_parts = re.split(r'[,，、|/]', tag_match.group(1))
            for t in tag_parts:
                cleaned_tag = t.strip().lower()
                if cleaned_tag:
                    extra_tags.add(cleaned_tag)

        # 生成卡片 ID
        counter += 1
        card_id = f"{safe_name(repo.replace('/', '_'), 'repo')}-{counter}"

        # 清理标题（移除 emoji）
        clean_title = re.sub(r'^[\U0001F300-\U0001F9FF\s]+', '', title)[:160]

        # 生成 GitHub 锚点链接
        anchor = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
        url = f"https://github.com/{repo}#{anchor}"

        # 合并标签
        all_tags = list(set(base_tags + list(extra_tags)))

        cards.append(PromptCard(
            id=card_id,
            repo=repo,
            title=clean_title,
            prompt=prompt[:4000],
            body=text.strip()[:600],
            tags=all_tags,
            url=url
        ))

    return cards


def sync_prompt_repo(repo_entry: Dict) -> Dict:
    """同步单个提示词仓库"""
    slug = repo_entry["slug"]
    tags = repo_entry.get("tags", [])

    result = {
        "slug": slug,
        "cardCount": 0,
        "updatedAt": "",
        "error": None
    }

    try:
        # 获取 README
        readme_data = fetch_readme(slug)
        if not readme_data:
            raise Exception(f"无法获取 README: {slug}")

        # 解析提示词卡片
        cards = parse_readme_prompts(readme_data["text"], slug, tags)

        # 保存到本地
        PROMPTS_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
        filename = slug_to_filename(slug)
        filepath = PROMPTS_LIBRARY_DIR / filename

        from datetime import datetime
        updated_at = datetime.utcnow().isoformat() + "Z"

        data = {
            "slug": slug,
            "sourceUrl": readme_data["url"],
            "updatedAt": updated_at,
            "cards": [card.to_dict() for card in cards]
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        result["cardCount"] = len(cards)
        result["updatedAt"] = updated_at

    except Exception as e:
        result["error"] = str(e)

    return result


def read_all_prompt_cards() -> Dict:
    """读取所有本地提示词卡片"""
    cards = []
    repos = []

    for repo_entry in PROMPT_REPOS:
        slug = repo_entry["slug"]
        tags = repo_entry.get("tags", [])
        filename = slug_to_filename(slug)
        filepath = PROMPTS_LIBRARY_DIR / filename

        if not filepath.exists():
            repos.append({
                "slug": slug,
                "cardCount": 0,
                "tags": tags
            })
            continue

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            repo_cards = [PromptCard.from_dict(c) for c in data.get("cards", [])]
            cards.extend(repo_cards)

            repos.append({
                "slug": slug,
                "cardCount": len(repo_cards),
                "updatedAt": data.get("updatedAt", ""),
                "tags": tags
            })
        except Exception as e:
            repos.append({
                "slug": slug,
                "cardCount": 0,
                "error": str(e),
                "tags": tags
            })

    return {
        "cards": cards,
        "repos": repos
    }


def filter_cards(cards: List[PromptCard],
                 repo: str = None,
                 tags: List[str] = None,
                 search: str = None) -> List[PromptCard]:
    """过滤提示词卡片"""
    filtered = cards

    # 按仓库过滤
    if repo:
        filtered = [c for c in filtered if c.repo == repo]

    # 按标签过滤
    if tags:
        filtered = [c for c in filtered if any(t in c.tags for t in tags)]

    # 按搜索关键词过滤
    if search:
        search_lower = search.lower()
        filtered = [
            c for c in filtered
            if search_lower in c.title.lower()
            or search_lower in c.prompt.lower()
            or search_lower in c.body.lower()
        ]

    return filtered


def get_card_by_id(card_id: str) -> Optional[PromptCard]:
    """根据 ID 获取提示词卡片"""
    data = read_all_prompt_cards()
    for card in data["cards"]:
        if card.id == card_id:
            return card
    return None
