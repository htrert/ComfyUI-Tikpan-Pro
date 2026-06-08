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
                 body: str = "", tags: List[str] = None, url: str = "",
                 title_zh: str = "", prompt_preview_zh: str = ""):
        self.id = id
        self.repo = repo
        self.title = title
        self.prompt = prompt
        self.body = body
        self.tags = tags or []
        self.url = url
        # 中文翻译缓存（由翻译流程填充,选择器下拉框优先显示）
        self.title_zh = title_zh
        self.prompt_preview_zh = prompt_preview_zh

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "repo": self.repo,
            "title": self.title,
            "prompt": self.prompt,
            "body": self.body,
            "tags": self.tags,
            "url": self.url,
            "title_zh": self.title_zh,
            "prompt_preview_zh": self.prompt_preview_zh,
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
            url=data.get("url", ""),
            title_zh=data.get("title_zh", ""),
            prompt_preview_zh=data.get("prompt_preview_zh", ""),
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


# 非提示词章节黑名单（按 H2 标题匹配，大小写不敏感、支持 emoji 前缀）
_H2_BLACKLIST_PATTERNS = [
    r'目录', r'菜单', r'索引', r'导航',
    r'介绍', r'简介', r'前言', r'关于',
    r'新闻', r'公告', r'更新日志', r'更新记录', r'版本',
    r'核心功能', r'功能特性', r'功能说明', r'特性',
    r'快速开始', r'快速上手', r'快速入门', r'入门',
    r'安装', r'部署', r'配置', r'环境要求', r'系统要求',
    r'使用指南', r'使用方法', r'使用说明', r'文档',
    r'软件截图', r'截图', r'演示', r'示例视频', r'演示视频',
    r'参与贡献', r'贡献指南', r'如何贡献', r'路线图',
    r'我的其他开源项目', r'相关项目', r'相关链接',
    r'致谢', r'鸣谢', r'感谢', r'赞助', r'打赏', r'支持',
    r'版权', r'许可', r'声明', r'免责声明', r'统计',
    r'Table of Contents', r'Contents', r'Menu', r'Index', r'Navigation',
    r'Introduction', r'Intro', r'About', r'Overview', r'Background',
    r'What is ', r'Why ',
    r'News', r'Announcement', r'Changelog', r'Release Notes', r'Versions?',
    r'Features?', r'Core Features?', r'Capabilities',
    r'Quick ?Start', r'Getting Started',
    r'Installation', r'Install', r'Setup', r'Deployment', r'Deploy',
    r'Configuration', r'Configure', r'Requirements',
    r'Usage', r'Guide', r'How to Use', r'How to ', r'Documentation', r'Docs',
    r'Screenshots?', r'Demo', r'Showcase',
    r'Contributing', r'Contribute', r'How to Contribute', r'Roadmap',
    r'My Other Projects?', r'Related Projects?', r'Related Links?',
    r'Acknowledge', r'Acknowledgements?', r'Credits?', r'Thanks?', r'Sponsor', r'Support',
    r'License', r'Copyright', r'Notice', r'Disclaimer',
    r'Star History', r'Contributors?', r'Statistics?', r'Stats',
    r'Parameter Specifications?', r'Repository Structure', r'Interaction Method',
    r'Advanced Techniques?', r'Gateway Service',
    r'View in Web Gallery', r'Web Gallery', r'Featured Prompts',
]
_H2_BLACKLIST_RE = re.compile(
    r'^[\W_]*(?:' + '|'.join(_H2_BLACKLIST_PATTERNS) + r')',
    re.IGNORECASE
)


def _is_non_prompt_content(text: str) -> bool:
    """判断一段文本是否明显不是提示词（安装命令、纯链接等）"""
    if not text or len(text) < 20:
        return True
    first_line = text.strip().splitlines()[0].strip()
    if re.match(r'^(npx|npm|yarn|pnpm|pip|pip3|python|python3|node|git|curl|wget|cd|mkdir|export|brew|apt|docker)\s+',
                first_line, re.IGNORECASE):
        return True
    if re.match(r'^(https?://|ftp://)', first_line) and len(text) < 200:
        return True
    if re.match(r'^(Welcome to|Learn more|This (repository|repo|project)|See the|Click the|Please refer)',
                first_line, re.IGNORECASE):
        return True
    return False


def _clean_title(raw: str) -> str:
    """清理标题：去 emoji、markdown 链接、Case 编号方括号"""
    title = raw.strip()
    title = re.sub(r'^[\U0001F300-\U0001FAFF☀-➿\s]+', '', title)
    # ### Case 151: [E-commerce Main Image](url)  ->  Case 151: E-commerce Main Image
    m = re.match(r'^(.*?)\[([^\]]+)\]\([^)]+\)\s*$', title)
    if m:
        prefix = m.group(1).strip()
        bracket = m.group(2).strip()
        title = f"{prefix} {bracket}".strip() if prefix else bracket
    title = re.sub(r'\s+', ' ', title).strip(' :：-')
    return title[:160]


def _extract_prompt(text: str) -> str:
    """从一段文本中提取最可能的提示词内容（代码块 > blockquote > 长段落）"""
    fence_match = re.search(r'```[a-zA-Z0-9_+-]*\n([\s\S]*?)```', text)
    if fence_match:
        return fence_match.group(1).strip()

    quoted_match = re.search(r'(?:^|\n)>\s+([^\n]+(?:\n>\s+[^\n]+)*)', text)
    if quoted_match:
        return re.sub(r'\n>\s+', '\n', quoted_match.group(1)).strip()

    for para in re.split(r'\n{2,}', text):
        cleaned = para.strip()
        if len(cleaned) < 30:
            continue
        if re.match(r'^!\[', cleaned):
            continue
        if re.match(r'^\[.+?\]\(.+?\)$', cleaned):
            continue
        if re.match(r'^(#|<|---|\|)', cleaned):
            continue
        return cleaned
    return ""


def _split_by_heading(lines: List[str], level: int):
    """按指定级别的标题切片，返回 [(title, sub_lines), ...]，标题前的内容用 None 作为 title"""
    pattern = re.compile(r'^#{' + str(level) + r'}\s+(.+?)\s*$')
    sections = []
    current_title = None
    current_lines = []
    for line in lines:
        m = pattern.match(line)
        if m:
            if current_title is not None or current_lines:
                sections.append((current_title, current_lines))
            current_title = m.group(1).strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_title is not None or current_lines:
        sections.append((current_title, current_lines))
    return sections


def parse_readme_prompts(markdown: str, repo: str, base_tags: List[str] = None) -> List[PromptCard]:
    """解析 README markdown 为提示词卡片列表

    策略：
    1. 按 H2 切分；用黑名单跳过非提示词章节
    2. 若 H2 下有 H3，每个 H3 拆成独立卡片（颗粒度更细）
    3. 若 H3 下有 `#### 📝 Prompt` 这类子节，优先用其内容
    4. 跳过明显是安装命令/介绍文字的伪提示词
    """
    if not markdown:
        return []

    base_tags = base_tags or []
    lines = markdown.split('\n')
    h2_sections = _split_by_heading(lines, 2)

    cards = []
    counter = 0
    repo_anchor_prefix = safe_name(repo.replace('/', '_'), 'repo')

    for h2_title, h2_lines in h2_sections:
        if h2_title is None:
            continue
        if _H2_BLACKLIST_RE.match(h2_title):
            continue

        h2_text = '\n'.join(h2_lines)
        # 整个 H2 区域内既无代码块也无 blockquote 时直接跳过（典型软件 README 不会落进提示词库）
        if not re.search(r'```[a-zA-Z0-9_+-]*\n', h2_text) and not re.search(r'(?:^|\n)>\s+', h2_text):
            continue

        clean_h2_title = _clean_title(h2_title)
        h2_anchor = re.sub(r'[^a-z0-9]+', '-', h2_title.lower()).strip('-')

        h3_sections = _split_by_heading(h2_lines, 3)
        # 有 H3 时按 H3 拆细颗粒度
        real_h3 = [(t, ls) for t, ls in h3_sections if t is not None]

        if real_h3:
            for h3_title, h3_lines in real_h3:
                # 跳过明显的子目录章节
                if _H2_BLACKLIST_RE.match(h3_title):
                    continue
                h3_text = '\n'.join(h3_lines)

                # 优先查找 #### 📝 Prompt / #### Prompt / #### 提示词 子节
                prompt = ""
                h4_match = re.search(
                    r'^####\s+[\W_]*(?:Prompt|提示词|提示语)\b[^\n]*\n([\s\S]*?)(?=\n####\s|\Z)',
                    h3_text, re.IGNORECASE | re.MULTILINE
                )
                if h4_match:
                    prompt = _extract_prompt(h4_match.group(1))

                if not prompt:
                    prompt = _extract_prompt(h3_text)

                if not prompt or _is_non_prompt_content(prompt):
                    continue

                counter += 1
                clean_h3_title = _clean_title(h3_title)
                full_title = clean_h3_title or clean_h2_title

                extra_tags = _extract_extra_tags(h3_text)

                cards.append(PromptCard(
                    id=f"{repo_anchor_prefix}-{counter}",
                    repo=repo,
                    title=full_title,
                    prompt=prompt[:4000],
                    body=h3_text.strip()[:600],
                    tags=list(set(base_tags + list(extra_tags))),
                    url=f"https://github.com/{repo}#{h2_anchor}",
                ))
        else:
            # 无 H3 时整段作为一张卡片
            prompt = _extract_prompt(h2_text)
            if not prompt or _is_non_prompt_content(prompt):
                continue

            counter += 1
            extra_tags = _extract_extra_tags(h2_text)
            cards.append(PromptCard(
                id=f"{repo_anchor_prefix}-{counter}",
                repo=repo,
                title=clean_h2_title,
                prompt=prompt[:4000],
                body=h2_text.strip()[:600],
                tags=list(set(base_tags + list(extra_tags))),
                url=f"https://github.com/{repo}#{h2_anchor}",
            ))

    return cards


def _extract_extra_tags(text: str) -> Set[str]:
    """从文本中提取 Tags/标签/Model 行的额外标签"""
    extra_tags: Set[str] = set()
    tag_match = re.search(r'^\s*(?:Tags?|标签|Model|模型)[:：]\s*(.+)$', text, re.IGNORECASE | re.MULTILINE)
    if tag_match:
        for t in re.split(r'[,，、|/]', tag_match.group(1)):
            cleaned_tag = t.strip().lower()
            if cleaned_tag:
                extra_tags.add(cleaned_tag)
    return extra_tags


TIKPAN_RELAY_HOST = "https://tikpan.com"
DEFAULT_TRANSLATE_MODEL = "deepseek-v4-flash"
TRANSLATE_BATCH_SIZE = 10
TRANSLATE_PREVIEW_CHARS = 80


def _is_mostly_chinese(text: str) -> bool:
    """如果文本里 40% 以上是汉字,认为已经是中文,无需翻译"""
    if not text:
        return False
    han_count = sum(1 for ch in text if '一' <= ch <= '鿿')
    return han_count > 0 and han_count / max(1, len(text)) >= 0.4


def _batch_translate(items: List[str], api_key: str, model: str,
                     api_host: str = TIKPAN_RELAY_HOST, timeout: int = 60) -> List[str]:
    """批量翻译为简体中文,返回与输入等长的列表;失败位置回退为空串"""
    if not items or not api_key:
        return ["" for _ in items]

    numbered = "\n".join(f"{i+1}. {s}" for i, s in enumerate(items))
    system_prompt = (
        "你是专业的图像/视频 AI 提示词翻译助手。"
        "把英文提示词术语翻译成简洁、专业、易懂的简体中文,保留专业摄影/影视术语的常用译法"
        "(如 cinematic→电影感, bokeh→散景, golden hour→黄金时段)。"
        "不要解释,不要加引号,严格保持原编号格式逐行输出译文。"
    )
    user_prompt = (
        f"请把下面 {len(items)} 条文本翻译成简体中文,只输出译文,逐行对应编号:\n\n"
        f"{numbered}"
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        resp = urllib.request.Request(
            f"{api_host.rstrip('/')}/v1/chat/completions",
            data=json.dumps(payload).encode('utf-8'),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(resp, timeout=timeout) as r:
            data = json.loads(r.read().decode('utf-8'))
        content = data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[翻译] 批量请求失败,本批回退原文: {e}")
        return ["" for _ in items]

    result = ["" for _ in items]
    for line in content.splitlines():
        m = re.match(r'^\s*(\d+)[\.\)、]\s*(.+?)\s*$', line)
        if m:
            idx = int(m.group(1)) - 1
            if 0 <= idx < len(items):
                result[idx] = m.group(2).strip(' "\'`')
    return result


def _load_existing_translations(filepath: Path) -> Dict[str, Dict[str, str]]:
    """加载上次同步的翻译缓存,key=原文标题,value={'title_zh','prompt_preview_zh','prompt_head'}"""
    if not filepath.exists():
        return {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        cache = {}
        for c in data.get("cards", []):
            title = c.get("title", "")
            if title and (c.get("title_zh") or c.get("prompt_preview_zh")):
                cache[title] = {
                    "title_zh": c.get("title_zh", ""),
                    "prompt_preview_zh": c.get("prompt_preview_zh", ""),
                    "prompt_head": (c.get("prompt", "") or "")[:TRANSLATE_PREVIEW_CHARS],
                }
        return cache
    except Exception:
        return {}


def translate_cards(cards: List[PromptCard], api_key: str,
                    model: str = DEFAULT_TRANSLATE_MODEL,
                    existing_cache: Dict[str, Dict[str, str]] = None,
                    progress_callback=None,
                    checkpoint_callback=None) -> int:
    """为卡片批量翻译标题和 prompt 预览;返回实际调用 API 翻译的条数

    checkpoint_callback: 每完成一个批次后被调用,用于把当前 cards 状态写入磁盘(断点续传)
    """
    if not api_key or not cards:
        return 0
    existing_cache = existing_cache or {}

    # 收集待翻译条目:标题和 prompt 预览分别送翻译
    pending_titles = []
    pending_title_idx = []
    pending_previews = []
    pending_preview_idx = []

    for i, card in enumerate(cards):
        # 命中缓存且原文未变 → 复用旧翻译
        cached = existing_cache.get(card.title)
        prompt_head = (card.prompt or "")[:TRANSLATE_PREVIEW_CHARS]
        if cached and cached.get("prompt_head") == prompt_head:
            card.title_zh = cached.get("title_zh", "")
            card.prompt_preview_zh = cached.get("prompt_preview_zh", "")
            continue

        # 标题
        if _is_mostly_chinese(card.title):
            card.title_zh = card.title
        elif card.title:
            pending_titles.append(card.title)
            pending_title_idx.append(i)

        # prompt 预览(80 字)
        if _is_mostly_chinese(prompt_head):
            card.prompt_preview_zh = prompt_head
        elif prompt_head:
            pending_previews.append(prompt_head)
            pending_preview_idx.append(i)

    translated_count = len(pending_titles) + len(pending_previews)
    if translated_count == 0:
        # 即使无需翻译也落盘一次,确保命中缓存的卡片把 _zh 字段写入
        if checkpoint_callback:
            try:
                checkpoint_callback()
            except Exception as e:
                print(f"[翻译] 写入磁盘失败: {e}")
        return 0

    # 分批翻译标题
    for batch_start in range(0, len(pending_titles), TRANSLATE_BATCH_SIZE):
        batch = pending_titles[batch_start:batch_start + TRANSLATE_BATCH_SIZE]
        idx_batch = pending_title_idx[batch_start:batch_start + TRANSLATE_BATCH_SIZE]
        translations = _batch_translate(batch, api_key, model)
        for idx, tr in zip(idx_batch, translations):
            if tr:  # 仅写入非空译文,空译文留到下次同步重试
                cards[idx].title_zh = tr
        if progress_callback:
            progress_callback("title", batch_start + len(batch), len(pending_titles))
        # 每批落盘一次,中途断开下次自动跳过已译
        if checkpoint_callback:
            try:
                checkpoint_callback()
            except Exception as e:
                print(f"[翻译] 写入磁盘失败: {e}")

    # 分批翻译预览
    for batch_start in range(0, len(pending_previews), TRANSLATE_BATCH_SIZE):
        batch = pending_previews[batch_start:batch_start + TRANSLATE_BATCH_SIZE]
        idx_batch = pending_preview_idx[batch_start:batch_start + TRANSLATE_BATCH_SIZE]
        translations = _batch_translate(batch, api_key, model)
        for idx, tr in zip(idx_batch, translations):
            if tr:
                cards[idx].prompt_preview_zh = tr
        if progress_callback:
            progress_callback("preview", batch_start + len(batch), len(pending_previews))
        if checkpoint_callback:
            try:
                checkpoint_callback()
            except Exception as e:
                print(f"[翻译] 写入磁盘失败: {e}")

    return translated_count


def sync_prompt_repo(repo_entry: Dict, api_key: str = "",
                     translate_model: str = DEFAULT_TRANSLATE_MODEL,
                     progress_callback=None) -> Dict:
    """同步单个提示词仓库;若提供 api_key 则同步后自动翻译标题与预览"""
    slug = repo_entry["slug"]
    tags = repo_entry.get("tags", [])

    result = {
        "slug": slug,
        "cardCount": 0,
        "translatedCount": 0,
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

        # 保存路径
        PROMPTS_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
        filename = slug_to_filename(slug)
        filepath = PROMPTS_LIBRARY_DIR / filename

        from datetime import datetime

        # ⚠️ 关键顺序:必须先读旧文件的译文缓存,再覆盖写盘
        existing_cache = _load_existing_translations(filepath) if api_key else {}

        def _write_to_disk():
            """原子写入,翻译断点续传依赖它"""
            payload = {
                "slug": slug,
                "sourceUrl": readme_data["url"],
                "updatedAt": datetime.utcnow().isoformat() + "Z",
                "cards": [card.to_dict() for card in cards],
            }
            tmp_path = filepath.with_suffix(filepath.suffix + ".tmp")
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, filepath)

        # 增量翻译:命中旧缓存的卡片直接复用译文;每批翻译完都重新落盘
        if api_key and cards:
            translated = translate_cards(
                cards, api_key, translate_model,
                existing_cache=existing_cache,
                progress_callback=progress_callback,
                checkpoint_callback=_write_to_disk,
            )
            result["translatedCount"] = translated
            _write_to_disk()
        else:
            # 不翻译模式:直接落盘解析结果
            _write_to_disk()

        updated_at = datetime.utcnow().isoformat() + "Z"

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
