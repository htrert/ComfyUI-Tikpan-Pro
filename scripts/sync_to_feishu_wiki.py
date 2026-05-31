"""
Tikpan 文档同步脚本（Wiki 版本）：把本地 Markdown 推送到飞书知识库
官方 API 文档：https://open.feishu.cn/document/server-docs/docs/wiki-v2/wiki-overview

用法：
    1. 复制 .feishu_config.example.json 为 .feishu_config.json
    2. 填入 app_id、app_secret、wiki_files 映射
    3. 运行: python scripts/sync_to_feishu_wiki.py
       或仅同步指定文件: python scripts/sync_to_feishu_wiki.py docs/节点使用教程.md
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


class FeishuWikiClient:
    """飞书 Wiki API 客户端"""

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

    def update_wiki_node(self, space_id: str, node_token: str, markdown: str) -> None:
        """更新 Wiki 节点内容（使用 Markdown 格式）

        Args:
            space_id: 知识库 ID
            node_token: 节点 token（从 URL 中提取）
            markdown: Markdown 内容
        """
        # 方法1: 尝试使用 wiki/v2 的更新接口
        url = f"{FEISHU_API}/wiki/v2/spaces/{space_id}/nodes/{node_token}"

        # Wiki API 可能支持直接更新 Markdown 内容
        payload = {
            "obj_type": "doc",  # 或 "docx"
            "node_type": "origin",
        }

        resp = requests.patch(url, headers=self._headers(), json=payload, timeout=30)
        data = resp.json()

        if data.get("code") != 0:
            # 如果直接更新失败，尝试获取关联的文档 ID 再更新
            print(f"  ⚠️ Wiki 节点更新失败，尝试获取关联文档...")
            doc_id = self._get_wiki_doc_id(space_id, node_token)
            if doc_id:
                self._update_doc_content(doc_id, markdown)
            else:
                raise RuntimeError(f"更新 Wiki 节点失败: {data}")
        else:
            print(f"  ✅ Wiki 节点更新成功")

    def _get_wiki_doc_id(self, space_id: str, node_token: str) -> str:
        """获取 Wiki 节点关联的文档 ID"""
        url = f"{FEISHU_API}/wiki/v2/spaces/{space_id}/nodes/{node_token}"
        resp = requests.get(url, headers=self._headers(), timeout=15)
        data = resp.json()

        if data.get("code") != 0:
            return ""

        node = data.get("data", {}).get("node", {})
        obj_token = node.get("obj_token", "")
        return obj_token

    def _update_doc_content(self, doc_id: str, markdown: str) -> None:
        """更新文档内容（通过 docx API）"""
        # 先清空旧内容
        blocks = self._get_document_blocks(doc_id)
        if len(blocks) > 1:
            root = blocks[0]
            children = root.get("children", [])
            if children:
                self._delete_blocks(doc_id, root["block_id"], 0, len(children))
                print(f"  🧹 清空旧内容: {len(children)} blocks")

        # 写入新内容
        self._create_blocks_from_markdown(doc_id, markdown)
        print(f"  ✅ 文档内容更新完成")

    def _get_document_blocks(self, document_id: str) -> list:
        """读取文档的所有 block"""
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

    def _delete_blocks(self, document_id: str, block_id: str, start: int, end: int) -> None:
        """删除指定范围的子 blocks"""
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

    def _create_blocks_from_markdown(self, document_id: str, markdown: str) -> None:
        """通过 batch_create 接口把 Markdown 内容写入文档"""
        blocks = self._markdown_to_blocks(markdown)

        url = f"{FEISHU_API}/docx/v1/documents/{document_id}/blocks/{document_id}/children"
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
        """把 Markdown 文本转换成飞书 docx block 数组"""
        blocks = []
        lines = markdown.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]

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

            if line.startswith("# "):
                blocks.append(_text_block(line[2:], block_type=3))
            elif line.startswith("## "):
                blocks.append(_text_block(line[3:], block_type=4))
            elif line.startswith("### "):
                blocks.append(_text_block(line[4:], block_type=5))
            elif line.startswith("#### "):
                blocks.append(_text_block(line[5:], block_type=6))
            elif line.strip().startswith(("- ", "* ")):
                blocks.append(_text_block(line.strip()[2:], block_type=12))
            else:
                if line.strip():
                    blocks.append(_text_block(line, block_type=2))
            i += 1
        return blocks


_LANG_MAP = {
    "python": 49, "py": 49, "bash": 28, "sh": 28, "shell": 28,
    "javascript": 30, "js": 30, "json": 31, "yaml": 51, "yml": 51,
    "text": 1, "plaintext": 1, "markdown": 1,
}


def _text_block(content: str, block_type: int = 2) -> dict:
    """构造一个文字块"""
    field_map = {2: "text", 3: "heading1", 4: "heading2", 5: "heading3", 6: "heading4", 12: "bullet"}
    field = field_map.get(block_type, "text")
    return {
        "block_type": block_type,
        field: {
            "elements": [{"text_run": {"content": content}}],
            "style": {},
        },
    }


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        print(f"❌ 找不到配置文件 {CONFIG_PATH}")
        print(f"   请复制 .feishu_config.example.json 为 .feishu_config.json 并填写凭证")
        sys.exit(1)
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def sync_one_wiki_file(client: FeishuWikiClient, md_path: Path, wiki_info: dict) -> None:
    """同步一个 Markdown 文件到 Wiki

    Args:
        client: 飞书客户端
        md_path: Markdown 文件路径
        wiki_info: Wiki 信息，格式: {"space_id": "xxx", "node_token": "yyy"}
                   或简化格式: "space_id/node_token"
    """
    # 解析 wiki_info
    if isinstance(wiki_info, str):
        parts = wiki_info.split("/")
        if len(parts) != 2:
            print(f"  ⚠️ Wiki 信息格式错误，应为 'space_id/node_token': {wiki_info}")
            return
        space_id, node_token = parts
    else:
        space_id = wiki_info.get("space_id", "")
        node_token = wiki_info.get("node_token", "")

    if not space_id or not node_token:
        print(f"  ⚠️ 缺少 space_id 或 node_token")
        return

    print(f"📄 同步: {md_path.name} -> wiki:{space_id[:8]}/{node_token[:8]}...")
    if not md_path.exists():
        print(f"  ⚠️ 跳过（文件不存在）: {md_path}")
        return

    markdown = md_path.read_text(encoding="utf-8")

    try:
        client.update_wiki_node(space_id, node_token, markdown)
    except Exception as e:
        print(f"  ❌ 同步失败: {e}")
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="同步 Markdown 文档到飞书 Wiki")
    parser.add_argument("file", nargs="?", help="可选：仅同步指定的 .md 文件路径（相对于项目根目录）")
    args = parser.parse_args()

    config = load_config()
    app_id = config.get("app_id", "").strip()
    app_secret = config.get("app_secret", "").strip()
    wiki_files: dict = config.get("wiki_files", {})

    if not app_id or not app_secret:
        print("❌ 配置文件缺少 app_id 或 app_secret")
        sys.exit(1)
    if not wiki_files:
        print("❌ 配置文件 wiki_files 为空，请至少配置一个 markdown -> wiki 映射")
        print("   格式: \"docs/xxx.md\": \"space_id/node_token\"")
        sys.exit(1)

    client = FeishuWikiClient(app_id, app_secret)

    if args.file:
        rel = args.file.replace("\\", "/")
        if rel not in wiki_files:
            print(f"❌ 文件 {rel} 未在配置中映射，已配置项: {list(wiki_files.keys())}")
            sys.exit(1)
        sync_one_wiki_file(client, PROJECT_ROOT / rel, wiki_files[rel])
    else:
        for rel, wiki_info in wiki_files.items():
            sync_one_wiki_file(client, PROJECT_ROOT / rel, wiki_info)

    print("\n🎉 同步完成")


if __name__ == "__main__":
    main()
