"""
Tikpan 文档同步脚本：把本地 Markdown 推送到飞书云文档
官方 API 文档：https://open.feishu.cn/document/server-docs/docs/docs/docx-v1/document/overview

用法：
    1. 复制 .feishu_config.example.json 为 .feishu_config.json
    2. 填入 app_id、app_secret、文件映射
    3. 运行: python scripts/sync_to_feishu.py
       或仅同步指定文件: python scripts/sync_to_feishu.py docs/节点使用教程.md
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / ".feishu_config.json"
FEISHU_API = "https://open.feishu.cn/open-apis"


class FeishuClient:
    """飞书 API 极简客户端，仅覆盖 Docs 同步所需的端点"""

    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self._token = None
        self._token_expire_at = 0

    def _ensure_token(self) -> str:
        """获取或刷新 tenant_access_token，缓存 2 小时"""
        if self._token and time.time() < self._token_expire_at - 300:
            return self._token

        url = f"{FEISHU_API}/auth/v3/tenant_access_token/internal"
        resp = requests.post(url, json={"app_id": self.app_id, "app_secret": self.app_secret}, timeout=15)
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"获取 tenant_access_token 失败: {data}")
        self._token = data["tenant_access_token"]
        self._token_expire_at = time.time() + int(data.get("expire", 7200))
        return self._token

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._ensure_token()}",
            "Content-Type": "application/json; charset=utf-8",
        }

    def get_document_blocks(self, document_id: str) -> list:
        """读取文档的所有 block，用于后续清空"""
        all_blocks = []
        page_token = ""
        while True:
            url = f"{FEISHU_API}/docx/v1/documents/{document_id}/blocks"
            params = {"page_size": 500}
            if page_token:
                params["page_token"] = page_token
            resp = requests.get(url, headers=self._headers(), params=params, timeout=15)
            data = resp.json()
            if data.get("code") != 0:
                raise RuntimeError(f"读取文档 blocks 失败: {data}")
            items = data.get("data", {}).get("items", [])
            all_blocks.extend(items)
            page_token = data.get("data", {}).get("page_token", "")
            if not page_token:
                break
        return all_blocks

    def delete_blocks(self, document_id: str, block_id: str, start: int, end: int) -> None:
        """删除指定范围的子 blocks（用于清空文档）"""
        url = f"{FEISHU_API}/docx/v1/documents/{document_id}/blocks/{block_id}/children/batch_delete"
        resp = requests.delete(
            url,
            headers=self._headers(),
            json={"start_index": start, "end_index": end},
            timeout=15,
        )
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"删除 blocks 失败: {data}")

    def create_blocks_from_markdown(self, document_id: str, markdown: str) -> None:
        """通过 import 接口把 Markdown 内容写入文档"""
        # 飞书文档 import API 是把 markdown 转成新文档；
        # 要追加到已有文档，使用 batch_create 端点逐块创建
        # 简化方案：每段 Markdown 转成 block，按顺序追加
        blocks = self._markdown_to_blocks(markdown)

        # 批量创建到文档根节点
        url = f"{FEISHU_API}/docx/v1/documents/{document_id}/blocks/{document_id}/children"
        # 飞书限制单次最多 50 个 block，分批写入
        batch_size = 40
        for i in range(0, len(blocks), batch_size):
            batch = blocks[i:i + batch_size]
            payload = {"children": batch, "index": -1}
            resp = requests.post(url, headers=self._headers(), json=payload, timeout=30)
            data = resp.json()
            if data.get("code") != 0:
                raise RuntimeError(f"写入 blocks 失败 (batch {i//batch_size+1}): {data}")
            time.sleep(0.3)

    @staticmethod
    def _markdown_to_blocks(markdown: str) -> list:
        """把 Markdown 文本转换成飞书 docx block 数组（增强版）

        - # / ## / ### → 对应 heading1/2/3
        - 反引号围成的代码块 → code block
        - Markdown 表格 → 飞书表格 block
        - 普通行 → text block
        """
        blocks = []
        lines = markdown.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]

            # 代码块
            if line.startswith("```"):
                lang = line[3:].strip() or "plaintext"
                code_lines = []
                i += 1
                while i < len(lines) and not lines[i].startswith("```"):
                    code_lines.append(lines[i])
                    i += 1
                blocks.append({
                    "block_type": 14,
                    "code": {
                        "elements": [{"text_run": {"content": "\n".join(code_lines)}}],
                        "style": {"language": _LANG_MAP.get(lang, 1), "wrap": True},
                    },
                })
                i += 1
                continue

            # Markdown 表格检测
            if "|" in line and i + 1 < len(lines) and "|" in lines[i + 1]:
                table_block = FeishuClient._parse_markdown_table(lines, i)
                if table_block:
                    blocks.append(table_block)
                    # 跳过表格行
                    i += table_block.get("_row_count", 1)
                    continue

            # 标题
            if line.startswith("# "):
                blocks.append(_text_block(line[2:], block_type=3))
            elif line.startswith("## "):
                blocks.append(_text_block(line[3:], block_type=4))
            elif line.startswith("### "):
                blocks.append(_text_block(line[4:], block_type=5))
            elif line.startswith("#### "):
                blocks.append(_text_block(line[5:], block_type=6))
            # 列表
            elif line.strip().startswith(("- ", "* ")):
                blocks.append(_text_block(line.strip()[2:], block_type=12))
            # 普通文本
            else:
                if line.strip():
                    blocks.append(_text_block(line, block_type=2))
            i += 1
        return blocks

    @staticmethod
    def _parse_markdown_table(lines: list, start_idx: int) -> dict:
        """解析 Markdown 表格并转换为飞书表格 block"""
        table_lines = []
        i = start_idx

        # 收集表格行
        while i < len(lines) and "|" in lines[i]:
            table_lines.append(lines[i])
            i += 1

        if len(table_lines) < 2:
            return None

        # 解析表头
        header_line = table_lines[0]
        headers = [cell.strip() for cell in header_line.split("|") if cell.strip()]

        # 跳过分隔线（第二行）
        if len(table_lines) < 3:
            # 只有表头没有数据，转换为文本
            return None

        # 解析数据行
        rows = []
        for line in table_lines[2:]:
            cells = [cell.strip() for cell in line.split("|") if cell.strip()]
            if cells:
                rows.append(cells)

        if not rows:
            return None

        # 构建飞书表格 block（使用代码块模拟，因为飞书 API 表格支持复杂）
        # 转换为美化的文本表格
        table_text = _format_table_as_text(headers, rows)

        return {
            "block_type": 14,  # 使用代码块展示表格
            "code": {
                "elements": [{"text_run": {"content": table_text}}],
                "style": {"language": 1, "wrap": False},  # plaintext
            },
            "_row_count": len(table_lines),
        }


_LANG_MAP = {
    "python": 49, "py": 49, "bash": 28, "sh": 28, "shell": 28,
    "javascript": 30, "js": 30, "json": 31, "yaml": 51, "yml": 51,
    "text": 1, "plaintext": 1, "markdown": 1,
}


def _text_block(content: str, block_type: int = 2) -> dict:
    """构造一个文字块（block_type 2=text, 3=h1, 4=h2, 5=h3, 12=bullet）"""
    field_map = {2: "text", 3: "heading1", 4: "heading2", 5: "heading3", 6: "heading4", 12: "bullet"}
    field = field_map.get(block_type, "text")
    return {
        "block_type": block_type,
        field: {
            "elements": [{"text_run": {"content": content}}],
            "style": {},
        },
    }


def _format_table_as_text(headers: list, rows: list) -> str:
    """将表格格式化为美化的文本表格"""
    # 计算每列的最大宽度
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(cell))

    # 构建表格
    lines = []

    # 表头
    header_line = " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    lines.append(header_line)

    # 分隔线
    separator = "-+-".join("-" * w for w in col_widths)
    lines.append(separator)

    # 数据行
    for row in rows:
        # 补齐列数
        while len(row) < len(headers):
            row.append("")
        row_line = " | ".join(row[i].ljust(col_widths[i]) if i < len(row) else "".ljust(col_widths[i])
                              for i in range(len(headers)))
        lines.append(row_line)

    return "\n".join(lines)


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        print(f"❌ 找不到配置文件 {CONFIG_PATH}")
        print(f"   请复制 .feishu_config.example.json 为 .feishu_config.json 并填写凭证")
        sys.exit(1)
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def sync_one_file(client: FeishuClient, md_path: Path, document_id: str) -> None:
    print(f"📄 同步: {md_path.name} -> docx:{document_id[:8]}...")
    if not md_path.exists():
        print(f"  ⚠️ 跳过（文件不存在）: {md_path}")
        return

    markdown = md_path.read_text(encoding="utf-8")

    # 清空旧内容
    blocks = client.get_document_blocks(document_id)
    if len(blocks) > 1:
        root = blocks[0]
        children = root.get("children", [])
        if children:
            client.delete_blocks(document_id, root["block_id"], 0, len(children))
            print(f"  🧹 清空旧内容: {len(children)} blocks")

    # 写入新内容
    client.create_blocks_from_markdown(document_id, markdown)
    print(f"  ✅ 完成")


def main() -> None:
    parser = argparse.ArgumentParser(description="同步 Markdown 文档到飞书云文档")
    parser.add_argument("file", nargs="?", help="可选：仅同步指定的 .md 文件路径（相对于项目根目录）")
    args = parser.parse_args()

    config = load_config()
    app_id = config.get("app_id", "").strip()
    app_secret = config.get("app_secret", "").strip()
    file_map: dict = config.get("files", {})

    if not app_id or not app_secret:
        print("❌ 配置文件缺少 app_id 或 app_secret")
        sys.exit(1)
    if not file_map:
        print("❌ 配置文件 files 为空，请至少配置一个 markdown -> document_id 映射")
        sys.exit(1)

    client = FeishuClient(app_id, app_secret)

    if args.file:
        rel = args.file.replace("\\", "/")
        if rel not in file_map:
            print(f"❌ 文件 {rel} 未在配置中映射，已配置项: {list(file_map.keys())}")
            sys.exit(1)
        sync_one_file(client, PROJECT_ROOT / rel, file_map[rel])
    else:
        for rel, doc_id in file_map.items():
            sync_one_file(client, PROJECT_ROOT / rel, doc_id)

    print("\n🎉 同步完成")


if __name__ == "__main__":
    main()
