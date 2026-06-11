#!/usr/bin/env python3
"""
本地文章同步可视化工具：拖入/选择 Markdown 或文本文章，保存草稿、导出多平台版本，并同步到飞书文档。

启动：
    python scripts/content_sync_tool.py
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from sync_to_feishu import CONFIG_PATH, FeishuClient, load_config  # noqa: E402

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

APP_DIR = PROJECT_ROOT / ".feishu" / "content_sync_tool"
DRAFTS_DIR = APP_DIR / "drafts"
EXPORTS_DIR = APP_DIR / "exports"
WECHAT_CONFIG_PATH = PROJECT_ROOT / ".wechat_config.json"
SUPPORTED_PLATFORMS = {
    "feishu": "飞书文档",
    "wechat": "微信公众号",
    "zsxq": "知识星球",
    "douyin": "抖音长文章",
    "bilibili": "Bilibili 长文章",
}

PLATFORM_PUBLISH_URLS = {
    "wechat": "https://mp.weixin.qq.com/",
    "zsxq": "https://wx.zsxq.com/",
    "douyin": "https://creator.douyin.com/creator-micro/content/upload",
    "bilibili": "https://member.bilibili.com/platform/upload/text/edit",
    "feishu": "https://www.feishu.cn/",
}

MEDIA_DIR = APP_DIR / "media"
TAGS_DIR = APP_DIR / "tags"
TRENDING_DIR = APP_DIR / "trending"


@dataclass
class Article:
    title: str
    content: str
    source_name: str = ""


def safe_filename(name: str, fallback: str = "article") -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|\r\n\t]+", "-", name).strip(" .-")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:80] or fallback


def extract_local_images(content: str) -> list[str]:
    """提取 Markdown 中引用的本地图片相对路径"""
    image_paths = set()
    def replacer(match):
        src = match.group(2).strip()
        if src and not src.startswith(("http://", "https://", "data:")):
            image_paths.add(src)
        return match.group(0)
    re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", replacer, content)
    return list(image_paths)


def hide_markdown_images(content: str) -> str:
    """Markdown 图片转换为占位文字，用于纯文本导出"""
    def replacer(match):
        alt = match.group(1).strip()
        src = match.group(2).strip()
        label = alt or "图片"
        if src.startswith(("http://", "https://", "data:")):
            return f"[{label}]"
        return f"[{label}]"
    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", replacer, content)


def first_heading(content: str) -> str:
    for line in content.splitlines():
        match = re.match(r"^#\s+(.+?)\s*$", line)
        if match:
            return match.group(1).strip()
    for line in content.splitlines():
        text = line.strip().strip("# ")
        if text:
            return text[:60]
    return "未命名文章"


def normalize_article(payload: dict) -> Article:
    content = str(payload.get("content") or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    source_name = str(payload.get("source_name") or "").strip()
    title = str(payload.get("title") or "").strip() or first_heading(content) or Path(source_name).stem
    return Article(title=title.strip() or "未命名文章", content=content, source_name=source_name)


def normalize_articles(payload: dict) -> list[Article]:
    raw_articles = payload.get("articles")
    if isinstance(raw_articles, list) and raw_articles:
        return [normalize_article(item) for item in raw_articles if isinstance(item, dict)]
    return [normalize_article(payload)]


def load_feishu_mappings() -> list[dict]:
    if not CONFIG_PATH.exists():
        return []
    try:
        config = load_config()
    except SystemExit:
        return []
    files = config.get("files", {})
    if not isinstance(files, dict):
        return []
    mappings = []
    for rel_path, document_id in files.items():
        mappings.append({
            "path": str(rel_path),
            "document_id": str(document_id),
            "title": Path(str(rel_path)).stem,
        })
    return mappings


def export_articles(articles: list[Article], platforms: list[str]) -> list[str]:
    if not articles:
        raise ValueError("没有可导出的文章")
    if not platforms:
        raise ValueError("请至少选择一个目标平台")
    paths = []
    for article in articles:
        if not article.content:
            continue
        for platform in platforms:
            platform = str(platform)
            if platform not in SUPPORTED_PLATFORMS:
                raise ValueError(f"不支持的平台：{platform}")
            content = adapt_for_platform(article, platform)
            paths.append(str(save_text(EXPORTS_DIR / platform, article, platform, content)))
    if not paths:
        raise ValueError("文章正文为空，无法导出")
    return paths


def strip_markdown_images(content: str) -> str:
    return hide_markdown_images(content)


def markdown_inline_to_html(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)
    return text


def markdown_to_wechat_html(markdown: str) -> str:
    lines = markdown.strip().splitlines()
    html_parts = []
    in_code = False
    code_lines = []
    in_ul = False
    in_ol = False

    def close_lists() -> None:
        nonlocal in_ul, in_ol
        if in_ul:
            html_parts.append("</ul>")
            in_ul = False
        if in_ol:
            html_parts.append("</ol>")
            in_ol = False

    for line in lines:
        raw = line.rstrip()
        if raw.startswith("```"):
            if in_code:
                html_parts.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")
                code_lines = []
                in_code = False
            else:
                close_lists()
                in_code = True
            continue
        if in_code:
            code_lines.append(raw)
            continue
        if not raw.strip():
            close_lists()
            continue
        image = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", raw.strip())
        if image:
            close_lists()
            alt, src = image.groups()
            html_parts.append(f'<p class="image-placeholder">图片：{html.escape(alt or src)}</p>')
            continue
        heading = re.match(r"^(#{1,6})\s+(.+)$", raw)
        if heading:
            close_lists()
            level = min(len(heading.group(1)), 3)
            html_parts.append(f"<h{level}>{markdown_inline_to_html(heading.group(2))}</h{level}>")
            continue
        bullet = re.match(r"^[-*]\s+(.+)$", raw.strip())
        if bullet:
            if in_ol:
                html_parts.append("</ol>")
                in_ol = False
            if not in_ul:
                html_parts.append("<ul>")
                in_ul = True
            html_parts.append(f"<li>{markdown_inline_to_html(bullet.group(1))}</li>")
            continue
        ordered = re.match(r"^\d+[.)]\s+(.+)$", raw.strip())
        if ordered:
            if in_ul:
                html_parts.append("</ul>")
                in_ul = False
            if not in_ol:
                html_parts.append("<ol>")
                in_ol = True
            html_parts.append(f"<li>{markdown_inline_to_html(ordered.group(1))}</li>")
            continue
        quote = re.match(r"^>\s*(.+)$", raw)
        if quote:
            close_lists()
            html_parts.append(f"<blockquote>{markdown_inline_to_html(quote.group(1))}</blockquote>")
            continue
        close_lists()
        html_parts.append(f"<p>{markdown_inline_to_html(raw)}</p>")

    close_lists()
    if in_code:
        html_parts.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")
    body = "\n".join(html_parts)
    return f"""<!doctype html>
<html lang=\"zh-CN\">
<head>
<meta charset=\"utf-8\" />
<title>微信公众号预览</title>
<style>
body{{margin:0;background:#f5f5f5;color:#222;font:16px/1.8 -apple-system,BlinkMacSystemFont,\"Segoe UI\",\"Microsoft YaHei\",sans-serif;}}
.article{{max-width:676px;margin:0 auto;background:#fff;padding:28px 24px;}}
h1{{font-size:24px;line-height:1.35;margin:0 0 22px;font-weight:700;}}
h2{{font-size:20px;margin:28px 0 12px;border-left:4px solid #2563eb;padding-left:10px;}}
h3{{font-size:18px;margin:24px 0 10px;}}
p{{margin:14px 0;}}
blockquote{{margin:18px 0;padding:12px 14px;background:#f7f7f7;border-left:4px solid #d0d7de;color:#555;}}
pre{{white-space:pre-wrap;background:#f6f8fa;border-radius:8px;padding:12px;overflow:auto;}}
code{{font-family:Consolas,Menlo,monospace;background:#f6f8fa;border-radius:4px;padding:2px 4px;}}
ul,ol{{padding-left:1.3em;}}
.image-placeholder{{padding:12px;border:1px dashed #cbd5e1;border-radius:8px;color:#64748b;background:#f8fafc;}}
</style>
</head>
<body><article class=\"article\">
{body}
</article></body>
</html>"""


def remove_top_h1(content: str, title: str) -> str:
    lines = content.splitlines()
    if lines and re.match(r"^#\s+", lines[0].strip()):
        return "\n".join(lines[1:]).lstrip()
    return content.strip()


def adapt_for_platform(article: Article, platform: str) -> str:
    body = article.content.strip()
    title = article.title.strip() or first_heading(body)

    if platform == "feishu":
        if body.startswith("# "):
            return body
        return f"# {title}\n\n{body}".strip() + "\n"

    if platform == "wechat":
        body = remove_top_h1(body, title)
        return (
            f"# {title}\n\n"
            f"{body}\n\n"
            "---\n"
            "排版提示：发布前建议检查封面、摘要、图片授权与文末引导。\n"
        )

    if platform == "zsxq":
        body = hide_markdown_images(remove_top_h1(body, title))
        return (
            f"【{title}】\n\n"
            f"{body}\n\n"
            "#知识星球 #长文\n"
        )

    if platform == "douyin":
        body = hide_markdown_images(remove_top_h1(body, title))
        body = re.sub(r"^#{1,6}\s*", "", body, flags=re.MULTILINE)
        return (
            f"{title}\n\n"
            f"{body}\n\n"
            "发布提示：抖音长文章建议补充吸引点击的封面标题和 3-5 个话题标签。\n"
        )

    if platform == "bilibili":
        body = remove_top_h1(body, title)
        return (
            f"# {title}\n\n"
            f"{body}\n\n"
            "---\n"
            "发布提示：Bilibili 专栏建议补充分区、封面图和相关视频/合集链接。\n"
        )

    return body + "\n"


def save_text(directory: Path, article: Article, platform: str, content: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    platform_name = SUPPORTED_PLATFORMS.get(platform, platform)
    suffix = "md" if platform in {"feishu", "wechat", "bilibili"} else "txt"
    if platform == "wechat-html":
        suffix = "html"
    filename = f"{stamp}-{safe_filename(article.title)}-{safe_filename(platform_name)}.{suffix}"
    path = directory / filename
    path.write_text(content, encoding="utf-8")
    return path


def generate_tags(article: Article) -> tuple[list[str], str]:
    """自动识别关键词并生成平台标签，基于标题/正文词频"""
    from collections import Counter
    stopwords = {'的','了','在','是','我','有','和','就','不','人','都','一','一个','上','也','很','到','说','要','去','你','会','着','没有','看','好','自己','这','他','她','它','我们','你们','他们','那个','这个','那么','什么','怎么','哪','还','可以','比如','因为','所以','但是','虽然','如果','或者','才','又','再','下','天','里','把','得','像','从','对','向','与','为','以','等','做','办','用','加','比','吗','吧','啊','嗯','哦','呢'}
    words = re.findall(r'[a-zA-Z一-鿿]{2,10}', article.title + '\n' + article.content[:2000])
    filtered = [w for w in words if w not in stopwords]
    freq = Counter(filtered)
    tags = [word for word, _ in freq.most_common(8)]
    tag_str = ', '.join(tags[:5])
    return tags, f"# {' #'.join(tags[:5])}"


def fetch_trending_topics() -> dict:
    """获取当前公开热门话题（知乎 + 微博）"""
    topics = {}
    if requests is None:
        return {"error": "缺少 requests 依赖"}
    try:
        resp = requests.get("https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("data", [])[:10]
            topics["zhihu"] = [item.get("target", {}).get("title", "") for item in items if item.get("target", {}).get("title")]
    except Exception:
        topics["zhihu"] = []
    try:
        resp = requests.get("https://tophub.today/n/KqndgxeLl9",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
        text = resp.text
        wb = re.findall(r'<td[^>]*><a[^>]*>(\d+)[.]?\s*(.+?)</a>', text)[:10]
        topics["weibo"] = [t[1].strip() for t in wb]
    except Exception:
        topics["weibo"] = []
    if not any(topics.values()):
        topics["note"] = "请自行补充当前热门话题"
    return topics


def save_wechat_html(article: Article) -> Path:
    content = adapt_for_platform(article, "wechat")
    html_content = markdown_to_wechat_html(content)
    return save_text(EXPORTS_DIR / "wechat_html", article, "wechat-html", html_content)


def load_wechat_config() -> dict:
    if not WECHAT_CONFIG_PATH.exists():
        return {}
    with open(WECHAT_CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def get_wechat_access_token(app_id: str, app_secret: str) -> str:
    if requests is None:
        raise RuntimeError("缺少 requests 依赖，无法调用微信公众号 API")
    resp = requests.get(
        "https://api.weixin.qq.com/cgi-bin/token",
        params={"grant_type": "client_credential", "appid": app_id, "secret": app_secret},
        timeout=15,
    )
    data = resp.json()
    token = data.get("access_token")
    if not token:
        raise RuntimeError(f"获取微信公众号 access_token 失败：{data}")
    return token


def create_wechat_draft(article: Article, thumb_media_id: str, author: str = "") -> dict:
    config = load_wechat_config()
    app_id = str(config.get("app_id", "")).strip()
    app_secret = str(config.get("app_secret", "")).strip()
    if not app_id or not app_secret:
        raise ValueError(f"请先创建 {WECHAT_CONFIG_PATH.name} 并填写 app_id、app_secret")
    if not thumb_media_id.strip():
        raise ValueError("微信公众号草稿 API 需要封面素材 thumb_media_id")
    token = get_wechat_access_token(app_id, app_secret)
    content = markdown_to_wechat_html(adapt_for_platform(article, "wechat"))
    digest = re.sub(r"\s+", " ", re.sub(r"[#>*`\[\]()]", "", article.content)).strip()[:120]
    payload = {
        "articles": [{
            "title": article.title[:64],
            "author": author or str(config.get("author", "")),
            "digest": digest,
            "content": content,
            "content_source_url": str(config.get("content_source_url", "")),
            "thumb_media_id": thumb_media_id.strip(),
            "need_open_comment": 0,
            "only_fans_can_comment": 0,
        }]
    }
    resp = requests.post(
        "https://api.weixin.qq.com/cgi-bin/draft/add",
        params={"access_token": token},
        json=payload,
        timeout=30,
    )
    data = resp.json()
    if data.get("errcode"):
        raise RuntimeError(f"创建微信公众号草稿失败：{data}")
    return data


def sync_article_to_feishu(article: Article, document_id: str) -> dict:
    if not document_id.strip():
        raise ValueError("请填写飞书文档 Token/ID")

    config = load_config()
    app_id = str(config.get("app_id", "")).strip()
    app_secret = str(config.get("app_secret", "")).strip()
    if not app_id or not app_secret:
        raise ValueError(f"配置文件缺少 app_id 或 app_secret：{CONFIG_PATH}")

    markdown = adapt_for_platform(article, "feishu")
    client = FeishuClient(app_id, app_secret)
    blocks = client.get_document_blocks(document_id)
    cleared = 0
    if len(blocks) > 1:
        root = blocks[0]
        children = root.get("children", [])
        if children:
            client.delete_blocks(document_id, root["block_id"], 0, len(children))
            cleared = len(children)
    client.create_blocks_from_markdown(document_id, markdown)
    return {"document_id": document_id, "cleared_blocks": cleared}


HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Tikpan 内容同步工具</title>
  <style>
    :root { color-scheme: light; --bg:#f6f7fb; --card:#fff; --text:#1f2937; --muted:#6b7280; --brand:#2563eb; --line:#e5e7eb; --ok:#16a34a; --warn:#d97706; --bad:#dc2626; }
    * { box-sizing: border-box; }
    body { margin:0; background:var(--bg); color:var(--text); font:14px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif; }
    header { padding:22px 28px; background:linear-gradient(135deg,#111827,#1d4ed8); color:white; }
    header h1 { margin:0 0 6px; font-size:24px; }
    header p { margin:0; opacity:.86; }
    main { max-width:1280px; margin:0 auto; padding:22px; display:grid; grid-template-columns: 1.05fr .95fr; gap:18px; }
    .card { background:var(--card); border:1px solid var(--line); border-radius:16px; box-shadow:0 8px 24px rgba(15,23,42,.06); overflow:hidden; }
    .card h2 { margin:0; padding:16px 18px; font-size:16px; border-bottom:1px solid var(--line); }
    .section { padding:16px 18px; }
    .drop { border:2px dashed #93c5fd; background:#eff6ff; border-radius:14px; padding:24px; text-align:center; cursor:pointer; transition:.15s; }
    .drop.drag { background:#dbeafe; border-color:var(--brand); transform:scale(1.01); }
    .drop strong { display:block; font-size:17px; margin-bottom:4px; }
    .file-list { margin-top:12px; display:grid; gap:8px; }
    .file-item { display:flex; justify-content:space-between; gap:10px; padding:8px 10px; border:1px solid var(--line); border-radius:10px; background:#f9fafb; }
    .file-item button { padding:4px 8px; border-radius:8px; background:#e5e7eb; color:#374151; }
    label { display:block; font-weight:600; margin:12px 0 6px; }
    input[type=text], select, textarea { width:100%; border:1px solid var(--line); border-radius:10px; padding:10px 12px; font:inherit; background:white; }
    textarea { min-height:430px; resize:vertical; font-family: ui-monospace,SFMono-Regular,Consolas,"Liberation Mono",monospace; line-height:1.55; }
    .row { display:flex; gap:10px; align-items:center; flex-wrap:wrap; }
    .platforms { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px; }
    .platforms label { margin:0; padding:10px; border:1px solid var(--line); border-radius:10px; font-weight:500; cursor:pointer; }
    button { border:0; border-radius:10px; background:var(--brand); color:white; padding:10px 14px; cursor:pointer; font-weight:700; }
    button.secondary { background:#374151; }
    button.ghost { color:var(--text); background:#eef2ff; }
    button:disabled { opacity:.5; cursor:not-allowed; }
    .preview { min-height:560px; white-space:pre-wrap; padding:16px 18px; font-family: ui-monospace,SFMono-Regular,Consolas,"Liberation Mono",monospace; border-top:1px solid var(--line); overflow:auto; }
    .status { margin-top:12px; padding:10px 12px; border-radius:10px; background:#f3f4f6; color:var(--muted); white-space:pre-wrap; }
    .status.ok { background:#dcfce7; color:#166534; }
    .status.bad { background:#fee2e2; color:#991b1b; }
    .muted { color:var(--muted); font-size:13px; }
    .pill { display:inline-flex; align-items:center; gap:6px; border:1px solid var(--line); border-radius:999px; padding:4px 9px; background:#fff; color:var(--muted); font-size:12px; }
    @media (max-width: 980px) { main { grid-template-columns:1fr; } textarea { min-height:300px; } }
  </style>
</head>
<body>
  <header>
    <h1>Tikpan 内容同步工具</h1>
    <p>拖入 Markdown / TXT / HTML 文章，保存草稿，导出公众号、知识星球、抖音、Bilibili 版本，或同步到飞书文档。</p>
  </header>
  <main>
    <section class="card">
      <h2>文章输入</h2>
      <div class="section">
        <div id="drop" class="drop">
          <strong>拖入文章文件到这里</strong>
          <span class="muted">也可以点击选择 .md / .txt / .html 文件；支持一次选择多个文件。</span>
          <input id="file" type="file" accept=".md,.markdown,.txt,.html,.htm,text/*" multiple hidden />
        </div>
        <div id="fileList" class="file-list"></div>
        <label for="title">标题</label>
        <input id="title" type="text" placeholder="未填写时自动取第一个 Markdown 一级标题" />
        <label for="content">正文</label>
        <textarea id="content" placeholder="把文章粘贴到这里，或拖入文件自动填充"></textarea>
        <div class="row" style="margin-top:12px">
          <span class="pill" id="source">未选择文件</span>
          <span class="pill" id="count">0 字</span>
        </div>
      </div>
    </section>

    <section class="card">
      <h2>保存 / 同步</h2>
      <div class="section">
        <label>目标平台</label>
        <div class="platforms" id="platforms">
          <label><input type="checkbox" value="feishu" checked /> 飞书文档</label>
          <label><input type="checkbox" value="wechat" checked /> 微信公众号</label>
          <label><input type="checkbox" value="zsxq" checked /> 知识星球</label>
          <label><input type="checkbox" value="douyin" /> 抖音长文章</label>
          <label><input type="checkbox" value="bilibili" /> Bilibili 长文章</label>
        </div>

        <label for="wechatThumb">微信公众号封面 thumb_media_id</label>
        <input id="wechatThumb" type="text" placeholder="使用开放平台草稿 API 时必填；半自动发布不需要" />
        <label for="wechatAuthor">微信公众号作者</label>
        <input id="wechatAuthor" type="text" placeholder="可选；不填则读取 .wechat_config.json 的 author" />
        <div class="row" style="margin-top:10px">
          <button id="wechatHtml" class="ghost">生成公众号 HTML</button>
          <button id="wechatDraft" class="ghost">创建公众号草稿</button>
          <button id="wechatOpen" class="ghost">打开公众号后台</button>
        </div>

        <label for="documentSelect">飞书配置映射</label>
        <select id="documentSelect">
          <option value="">手动填写文档 Token/ID</option>
        </select>
        <label for="documentId">飞书文档 Token/ID</label>
        <input id="documentId" type="text" placeholder="飞书 URL 中 /docx/ 后面的那段；只在点“同步到飞书”时使用" />
        <p class="muted">飞书凭证继续读取项目根目录 .feishu_config.json；其他平台当前先导出适配文稿，避免不稳定自动发布。</p>

        <div class="row" style="margin-top:14px">
          <button id="saveDraft">保存当前草稿</button>
          <button id="export" class="secondary">导出当前文稿</button>
          <button id="exportAll" class="secondary">批量导出全部</button>
          <button id="sync" class="ghost">同步当前到飞书</button>
        </div>
        <div id="status" class="status">准备就绪。</div>
      </div>
      <h2>当前平台预览</h2>
      <div class="section row">
        <select id="previewPlatform">
          <option value="feishu">飞书文档</option>
          <option value="wechat">微信公众号</option>
          <option value="zsxq">知识星球</option>
          <option value="douyin">抖音长文章</option>
          <option value="bilibili">Bilibili 长文章</option>
        </select>
        <button id="refresh" class="ghost">刷新预览</button>
      </div>
      <div id="preview" class="preview muted">暂无内容。</div>
    </section>
  </main>
<script>
const $ = (id) => document.getElementById(id);
const drop = $('drop');
const fileInput = $('file');
const titleInput = $('title');
const contentInput = $('content');
const statusBox = $('status');
const preview = $('preview');
const source = $('source');
const count = $('count');
const fileList = $('fileList');
const documentSelect = $('documentSelect');
let sourceName = '';
let articles = [];
let currentIndex = -1;

function setStatus(message, kind='') {
  statusBox.textContent = message;
  statusBox.className = 'status' + (kind ? ' ' + kind : '');
}
function updateCount() { count.textContent = `${contentInput.value.length} 字`; }
function selectedPlatforms() {
  return [...document.querySelectorAll('#platforms input:checked')].map(i => i.value);
}
function payload(extra={}) {
  return { title: titleInput.value, content: contentInput.value, source_name: sourceName, ...extra };
}
function syncCurrentArticle() {
  if (currentIndex >= 0 && articles[currentIndex]) {
    articles[currentIndex].title = titleInput.value;
    articles[currentIndex].content = contentInput.value;
    articles[currentIndex].source_name = sourceName;
  }
}
function renderFileList() {
  fileList.innerHTML = '';
  articles.forEach((article, index) => {
    const item = document.createElement('div');
    item.className = 'file-item';
    const name = document.createElement('span');
    name.textContent = `${index + 1}. ${article.title || article.source_name || '未命名文章'}`;
    const actions = document.createElement('div');
    const open = document.createElement('button');
    open.textContent = index === currentIndex ? '当前' : '编辑';
    open.disabled = index === currentIndex;
    open.addEventListener('click', () => selectArticle(index));
    const remove = document.createElement('button');
    remove.textContent = '移除';
    remove.addEventListener('click', () => removeArticle(index));
    actions.append(open, remove);
    item.append(name, actions);
    fileList.appendChild(item);
  });
}
function selectArticle(index) {
  syncCurrentArticle();
  const article = articles[index];
  if (!article) return;
  currentIndex = index;
  sourceName = article.source_name || '';
  titleInput.value = article.title || '';
  contentInput.value = article.content || '';
  source.textContent = sourceName || '手动输入';
  updateCount();
  renderFileList();
  refreshPreview();
}
function removeArticle(index) {
  articles.splice(index, 1);
  if (!articles.length) {
    currentIndex = -1;
    sourceName = '';
    titleInput.value = '';
    contentInput.value = '';
    source.textContent = '未选择文件';
    updateCount();
    renderFileList();
    refreshPreview();
    return;
  }
  currentIndex = Math.min(index, articles.length - 1);
  selectArticle(currentIndex);
}
function currentArticles() {
  syncCurrentArticle();
  if (articles.length) return articles;
  return [payload()];
}
async function postJSON(path, data) {
  const resp = await fetch(path, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data) });
  const json = await resp.json().catch(() => ({}));
  if (!resp.ok || json.ok === false) throw new Error(json.error || `请求失败：${resp.status}`);
  return json;
}
function guessTitle(text, name) {
  const h1 = text.split(/\r?\n/).map(l => l.match(/^#\s+(.+)$/)).find(Boolean);
  if (h1) return h1[1].trim();
  return (name || '未命名文章').replace(/\.[^.]+$/, '');
}
async function readFile(file) {
  const text = await file.text();
  const article = {
    title: guessTitle(text, file.name),
    content: text.replace(/\r\n/g, '\n'),
    source_name: file.name
  };
  articles.push(article);
  selectArticle(articles.length - 1);
  setStatus(`已载入：${file.name}`, 'ok');
}
async function readFiles(files) {
  const list = [...files];
  for (const file of list) {
    const text = await file.text();
    articles.push({
      title: guessTitle(text, file.name),
      content: text.replace(/\r\n/g, '\n'),
      source_name: file.name
    });
  }
  if (list.length) selectArticle(articles.length - list.length);
  setStatus(`已载入 ${list.length} 个文件。`, 'ok');
}
async function loadConfig() {
  try {
    const data = await fetch('/api/config').then(r => r.json());
    if (data.mappings && data.mappings.length) {
      documentSelect.innerHTML = '<option value="">手动填写文档 Token/ID</option>';
      for (const mapping of data.mappings) {
        const option = document.createElement('option');
        option.value = mapping.document_id;
        option.textContent = `${mapping.path} → ${mapping.document_id.slice(0, 8)}...`;
        documentSelect.appendChild(option);
      }
    }
  } catch (err) {
    console.warn(err);
  }
}
async function refreshPreview() {
  if (!contentInput.value.trim()) {
    preview.textContent = '暂无内容。';
    preview.className = 'preview muted';
    return;
  }
  const platform = $('previewPlatform').value;
  try {
    const data = await postJSON('/api/preview', payload({ platform }));
    preview.textContent = data.content;
    preview.className = 'preview';
  } catch (err) {
    setStatus(err.message, 'bad');
  }
}

drop.addEventListener('click', () => fileInput.click());
drop.addEventListener('dragover', (event) => { event.preventDefault(); drop.classList.add('drag'); });
drop.addEventListener('dragleave', () => drop.classList.remove('drag'));
drop.addEventListener('drop', async (event) => {
  event.preventDefault(); drop.classList.remove('drag');
  const files = event.dataTransfer.files;
  if (files.length) await readFiles(files);
});
fileInput.addEventListener('change', async () => { if (fileInput.files.length) await readFiles(fileInput.files); });
contentInput.addEventListener('input', () => { updateCount(); syncCurrentArticle(); });
titleInput.addEventListener('input', () => { syncCurrentArticle(); renderFileList(); });
documentSelect.addEventListener('change', () => { $('documentId').value = documentSelect.value; });
$('refresh').addEventListener('click', refreshPreview);
$('previewPlatform').addEventListener('change', refreshPreview);

$('saveDraft').addEventListener('click', async () => {
  try {
    const data = await postJSON('/api/save-draft', payload());
    setStatus(`草稿已保存：\n${data.path}`, 'ok');
  } catch (err) { setStatus(err.message, 'bad'); }
});
$('export').addEventListener('click', async () => {
  try {
    const data = await postJSON('/api/export', payload({ platforms:selectedPlatforms() }));
    setStatus('当前文稿已导出：\n' + data.paths.join('\n'), 'ok');
  } catch (err) { setStatus(err.message, 'bad'); }
});
$('exportAll').addEventListener('click', async () => {
  try {
    const data = await postJSON('/api/export', { articles:currentArticles(), platforms:selectedPlatforms() });
    setStatus(`已批量导出 ${data.paths.length} 个文件：\n` + data.paths.join('\n'), 'ok');
  } catch (err) { setStatus(err.message, 'bad'); }
});
$('wechatHtml').addEventListener('click', async () => {
  try {
    const data = await postJSON('/api/export/wechat-html', payload());
    setStatus(`公众号 HTML 已生成：\n${data.path}\n可以打开该文件复制排版内容到公众号后台。`, 'ok');
  } catch (err) { setStatus(err.message, 'bad'); }
});
$('wechatDraft').addEventListener('click', async () => {
  if (!confirm('将通过微信公众号开放平台 API 创建草稿，请确认 .wechat_config.json 和 thumb_media_id 已配置。继续吗？')) return;
  try {
    setStatus('正在创建微信公众号草稿，请稍等...');
    const data = await postJSON('/api/sync/wechat-draft', payload({ thumb_media_id:$('wechatThumb').value, author:$('wechatAuthor').value }));
    setStatus(`微信公众号草稿创建完成：\nmedia_id: ${data.media_id || '(无返回 media_id)'}`, 'ok');
  } catch (err) { setStatus(err.message, 'bad'); }
});
$('wechatOpen').addEventListener('click', () => {
  window.open('https://mp.weixin.qq.com/', '_blank');
});
$('sync').addEventListener('click', async () => {
  if (!confirm('同步到飞书会清空目标文档旧内容并写入当前文章，确定继续吗？')) return;
  try {
    setStatus('正在同步到飞书，请稍等...');
    const data = await postJSON('/api/sync/feishu', payload({ document_id:$('documentId').value }));
    setStatus(`飞书同步完成：docx/${data.document_id}\n清空旧 blocks：${data.cleared_blocks}`, 'ok');
  } catch (err) { setStatus(err.message, 'bad'); }
});
loadConfig();
updateCount();
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "TikpanContentSync/0.1"

    def log_message(self, fmt: str, *args) -> None:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {self.address_string()} {fmt % args}")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/" or parsed.path == "/index.html":
            self.send_text(HTML, "text/html; charset=utf-8")
            return
        if parsed.path == "/api/config":
            exists = CONFIG_PATH.exists()
            self.send_json({
                "ok": True,
                "feishu_config_exists": exists,
                "config_path": str(CONFIG_PATH),
                "mappings": load_feishu_mappings(),
            })
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:
        try:
            parsed = urlparse(self.path)
            payload = self.read_json()
            if parsed.path == "/api/preview":
                article = normalize_article(payload)
                platform = str(payload.get("platform") or "feishu")
                self.ensure_platform(platform)
                self.send_json({"ok": True, "content": adapt_for_platform(article, platform)})
                return

            if parsed.path == "/api/save-draft":
                article = normalize_article(payload)
                if not article.content:
                    raise ValueError("正文为空，无法保存")
                content = adapt_for_platform(article, "feishu")
                path = save_text(DRAFTS_DIR, article, "draft", content)
                self.send_json({"ok": True, "path": str(path)})
                return

            if parsed.path == "/api/export":
                articles = normalize_articles(payload)
                platforms = payload.get("platforms") or []
                if not isinstance(platforms, list):
                    raise ValueError("平台参数格式错误")
                paths = export_articles(articles, [str(platform) for platform in platforms])
                self.send_json({"ok": True, "paths": paths})
                return

            if parsed.path == "/api/export/wechat-html":
                article = normalize_article(payload)
                if not article.content:
                    raise ValueError("正文为空，无法生成公众号 HTML")
                path = save_wechat_html(article)
                self.send_json({"ok": True, "path": str(path)})
                return

            if parsed.path == "/api/sync/feishu":
                article = normalize_article(payload)
                if not article.content:
                    raise ValueError("正文为空，无法同步")
                document_id = str(payload.get("document_id") or "").strip()
                result = sync_article_to_feishu(article, document_id)
                self.send_json({"ok": True, **result})
                return

            if parsed.path == "/api/sync/wechat-draft":
                article = normalize_article(payload)
                if not article.content:
                    raise ValueError("正文为空，无法创建公众号草稿")
                thumb_media_id = str(payload.get("thumb_media_id") or "").strip()
                author = str(payload.get("author") or "").strip()
                result = create_wechat_draft(article, thumb_media_id, author)
                self.send_json({"ok": True, **result})
                return

            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def ensure_platform(self, platform: str) -> None:
        if platform not in SUPPORTED_PLATFORMS:
            raise ValueError(f"不支持的平台：{platform}")

    def send_json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_text(self, text: str, content_type: str) -> None:
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser(description="启动 Tikpan 内容同步可视化工具")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址，默认 127.0.0.1")
    parser.add_argument("--port", default=8765, type=int, help="监听端口，默认 8765")
    parser.add_argument("--no-open", action="store_true", help="不自动打开浏览器")
    args = parser.parse_args()

    APP_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}/"
    print(f"Tikpan 内容同步工具已启动：{url}")
    print(f"草稿目录：{DRAFTS_DIR}")
    print(f"导出目录：{EXPORTS_DIR}")
    print("按 Ctrl+C 停止。")
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
