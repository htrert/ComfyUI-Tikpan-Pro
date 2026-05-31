# 飞书 Wiki 同步指南

本指南介绍如何将本地 Markdown 文档同步到飞书知识库（Wiki）。

## Wiki vs Docx 的区别

飞书有两种文档类型：

| 类型 | URL 格式 | 同步脚本 | 适用场景 |
| --- | --- | --- | --- |
| **Wiki（知识库）** | `https://xxx.feishu.cn/wiki/xxxxx` | `sync_to_feishu_wiki.py` | 团队知识库、结构化文档 |
| **Docx（新版文档）** | `https://xxx.feishu.cn/docx/xxxxx` | `sync_to_feishu.py` | 独立文档、临时协作 |

**如何判断**：看你创建的文档 URL，如果是 `/wiki/` 就用 Wiki 脚本，如果是 `/docx/` 就用 Docx 脚本。

## 配置步骤

### 1. 创建飞书应用

1. 访问 [飞书开放平台](https://open.feishu.cn/app)
2. 创建企业自建应用
3. 在"凭证与基础信息"页面获取：
   - `App ID`
   - `App Secret`
4. 在"权限管理"中开通以下权限：
   - `wiki:wiki` - 查看、编辑和管理知识库
   - `wiki:wiki:readonly` - 查看知识库
   - `docx:document` - 查看、评论、编辑和管理云文档（用于更新 Wiki 关联的文档内容）

### 2. 准备 Wiki 文档

#### 方法一：从 Wiki URL 提取信息（推荐）

1. 在飞书中打开你的 Wiki 页面
2. 从 URL 中提取 `space_id` 和 `node_token`：
   ```
   https://example.feishu.cn/wiki/AbCdEfGhIjKl?table=tblXyZaBcDeFgHi&view=vewMnOpQrStUvWx
   ```
   - `space_id`：URL 中 `/wiki/` 后面的第一段：`AbCdEfGhIjKl`
   - `node_token`：通常与 `space_id` 相同，或者是 URL 参数中的特定值

#### 方法二：使用飞书 API 查询

如果不确定 `node_token`，可以通过 API 查询：

```bash
# 获取知识库列表
curl -X GET "https://open.feishu.cn/open-apis/wiki/v2/spaces" \
  -H "Authorization: Bearer YOUR_TOKEN"

# 获取知识库节点列表
curl -X GET "https://open.feishu.cn/open-apis/wiki/v2/spaces/{space_id}/nodes" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### 简化配置格式

在配置文件中，使用 `space_id/node_token` 格式：

```json
{
  "wiki_files": {
    "docs/节点使用教程.md": "AbCdEfGhIjKl/XyZaBcDeFgHi"
  }
}
```

### 3. 配置同步脚本

```bash
# 复制配置模板
cp .feishu_config.example.json .feishu_config.json

# 编辑配置文件
# Windows: notepad .feishu_config.json
# Mac/Linux: nano .feishu_config.json
```

配置文件示例：

```json
{
  "app_id": "cli_a1b2c3d4e5f6g7h8",
  "app_secret": "your_app_secret_here_32_chars",
  "wiki_files": {
    "docs/节点使用教程.md": "AbCdEfGhIjKl/XyZaBcDeFgHi",
    "docs/节点速查表.md": "MnOpQrStUvWx/PqRsTuVwXyZ",
    "CHANGELOG.md": "AaBbCcDdEeFf/GgHhIiJjKkLl"
  }
}
```

**字段说明**：
- `app_id`：飞书应用的 App ID
- `app_secret`：飞书应用的 App Secret（**敏感信息，不要提交到 git**）
- `wiki_files`：本地文件路径 → Wiki 信息的映射表
  - 格式：`"space_id/node_token"` 或 `{"space_id": "xxx", "node_token": "yyy"}`

### 4. 设置 Wiki 权限

1. 打开 Wiki 页面
2. 点击右上角"分享"或"权限设置"
3. 找到你创建的飞书应用
4. 设置为"可编辑"权限

## 使用方法

### 同步所有配置的 Wiki 文档

```bash
python scripts/sync_to_feishu_wiki.py
```

输出示例：

```
📄 同步: 节点使用教程.md -> wiki:AbCdEfGh/XyZaBcDe...
  🧹 清空旧内容: 45 blocks
  ✅ 文档内容更新完成

📄 同步: 节点速查表.md -> wiki:MnOpQrSt/PqRsTuVw...
  🧹 清空旧内容: 23 blocks
  ✅ 文档内容更新完成

🎉 同步完成
```

### 仅同步指定 Wiki 文档

```bash
python scripts/sync_to_feishu_wiki.py docs/节点使用教程.md
```

## 工作原理

Wiki 同步脚本的工作流程：

1. **获取 Wiki 节点信息**：通过 `wiki/v2` API 获取节点关联的文档 ID
2. **清空旧内容**：删除文档中的所有旧 blocks
3. **转换 Markdown**：将本地 Markdown 转换为飞书 block 格式
4. **写入新内容**：批量创建新的 blocks 到文档中

## 支持的 Markdown 语法

与 Docx 版本相同，支持：

- `# / ## / ### / ####` - 标题（1-4 级）
- `` ```代码块``` `` - 代码块（支持语言高亮）
- `- / *` - 无序列表
- 普通文本段落

**暂不支持**：表格、图片、链接、粗体/斜体等行内格式

## 常见问题

### Q1: 如何找到 space_id 和 node_token？

**方法 1**：从 URL 提取
- 打开 Wiki 页面，URL 格式：`https://xxx.feishu.cn/wiki/AbCdEfGhIjKl`
- `space_id` 就是 `/wiki/` 后面的部分：`AbCdEfGhIjKl`
- `node_token` 通常与 `space_id` 相同，或者在 URL 参数中

**方法 2**：使用浏览器开发者工具
- 打开 Wiki 页面
- 按 F12 打开开发者工具
- 在 Network 标签中查看 API 请求
- 找到包含 `wiki/v2` 的请求，查看参数

### Q2: 提示 "更新 Wiki 节点失败"

**原因**：权限不足或 Wiki 信息错误。

**解决**：
1. 检查应用是否有 `wiki:wiki` 权限
2. 确认 `space_id` 和 `node_token` 是否正确
3. 确认 Wiki 页面权限设置为"应用可编辑"
4. 尝试手动在飞书中编辑该 Wiki 页面，确认有编辑权限

### Q3: Wiki 和 Docx 可以同时使用吗？

**可以**。配置文件中可以同时配置 `files`（Docx）和 `wiki_files`（Wiki）：

```json
{
  "app_id": "cli_xxx",
  "app_secret": "xxx",
  "files": {
    "README.md": "docx_document_id"
  },
  "wiki_files": {
    "docs/节点使用教程.md": "space_id/node_token"
  }
}
```

然后分别运行：
- `python scripts/sync_to_feishu.py` - 同步 Docx
- `python scripts/sync_to_feishu_wiki.py` - 同步 Wiki

### Q4: 同步后 Wiki 格式不对

**原因**：Wiki 底层使用的是 Docx 文档格式，支持的 Markdown 语法有限。

**解决**：
1. 简化 Markdown 语法，避免使用表格、图片等复杂格式
2. 使用代码块展示复杂内容
3. 手动在飞书中调整格式

### Q5: 如何批量获取 Wiki 的 space_id 和 node_token？

可以使用飞书 API 批量查询：

```python
import requests

def list_wiki_spaces(token):
    url = "https://open.feishu.cn/open-apis/wiki/v2/spaces"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers)
    return resp.json()

def list_wiki_nodes(token, space_id):
    url = f"https://open.feishu.cn/open-apis/wiki/v2/spaces/{space_id}/nodes"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers)
    return resp.json()
```

## 安全提示

⚠️ **重要**：`.feishu_config.json` 包含敏感凭证，已加入 `.gitignore`。

**请勿**：
- 将 `.feishu_config.json` 提交到 git
- 在公开场合分享 App Secret
- 将配置文件上传到公开服务器

## 技术细节

### API 端点

- 获取 token：`POST /open-apis/auth/v3/tenant_access_token/internal`
- 获取 Wiki 节点：`GET /open-apis/wiki/v2/spaces/{space_id}/nodes/{node_token}`
- 更新 Wiki 节点：`PATCH /open-apis/wiki/v2/spaces/{space_id}/nodes/{node_token}`
- 读取文档：`GET /open-apis/docx/v1/documents/{document_id}/blocks`
- 删除内容：`DELETE /open-apis/docx/v1/documents/{document_id}/blocks/{block_id}/children/batch_delete`
- 写入内容：`POST /open-apis/docx/v1/documents/{document_id}/blocks/{block_id}/children`

### Wiki 与 Docx 的关系

- Wiki 节点本质上是一个容器，关联了一个 Docx 文档
- 更新 Wiki 内容 = 更新其关联的 Docx 文档
- 因此 Wiki 脚本需要同时使用 `wiki/v2` 和 `docx/v1` API

---

**相关文档**：
- [飞书文档同步指南（Docx 版本）](飞书文档同步指南.md)
- [节点使用教程](节点使用教程.md)
- [节点速查表](节点速查表.md)
