# Git Hooks 自动化文档同步

本目录包含 Git hooks 脚本，用于自动化文档管理和同步。

## 功能说明

### 1. pre-commit（提交前检查）

**作用**：在 `git commit` 之前检查，如果修改了 Python 代码但没有更新文档，会阻止提交。

**检查规则**：
- 如果有 `.py` 文件变更
- 但没有更新任何文档文件（`docs/*.md`、`CHANGELOG.md`、`README.md`）
- 则提交失败，提示需要更新文档

**跳过检查**：
```bash
git commit --no-verify -m "commit message"
```

### 2. post-commit（提交后同步）

**作用**：在 `git commit` 成功后，如果检测到文档变更，自动同步到飞书。

**同步规则**：
- 如果本次提交包含文档文件变更
- 自动执行 `sync_to_feishu_merged.py` 同步到飞书
- 同步成功后显示飞书文档链接

## 安装方法

### Windows（Git Bash）

```bash
# 进入项目目录
cd C:\ComfyUI-aki-v2\ComfyUI\custom_nodes\ComfyUI-Tikpan-Pro

# 复制 hooks 到 .git/hooks 目录
cp scripts/git-hooks/pre-commit .git/hooks/pre-commit
cp scripts/git-hooks/post-commit .git/hooks/post-commit

# 添加执行权限
chmod +x .git/hooks/pre-commit
chmod +x .git/hooks/post-commit
```

### 验证安装

```bash
# 查看 hooks 是否存在
ls -la .git/hooks/

# 应该看到：
# -rwxr-xr-x  pre-commit
# -rwxr-xr-x  post-commit
```

## 使用示例

### 场景1：修改代码但忘记更新文档

```bash
# 修改了 nodes/tikpan_image.py
git add nodes/tikpan_image.py
git commit -m "优化图像生成逻辑"

# 输出：
# ❌ 错误：检测到代码变更但文档未更新！
# 请更新以下文档之一：
#   - docs/节点使用教程.md
#   - docs/节点速查表.md
#   - CHANGELOG.md
```

### 场景2：修改代码并更新文档

```bash
# 修改了代码和文档
git add nodes/tikpan_image.py docs/节点使用教程.md CHANGELOG.md
git commit -m "优化图像生成逻辑并更新文档"

# 输出：
# ✅ Pre-commit 检查通过
# [main abc1234] 优化图像生成逻辑并更新文档
# 📤 检查是否需要同步文档到飞书...
# 📄 检测到文档变更，开始同步到飞书...
# ✅ 文档已自动同步到飞书
# 🔗 查看：https://aw5zg7a9e9u.feishu.cn/docx/Dkncdyrl8oo6OvxDP9KcRHnOnLg
```

### 场景3：仅修改文档

```bash
# 只修改了文档
git add docs/节点使用教程.md
git commit -m "更新文档"

# 输出：
# ✅ Pre-commit 检查通过（没有代码变更）
# [main def5678] 更新文档
# 📤 检查是否需要同步文档到飞书...
# 📄 检测到文档变更，开始同步到飞书...
# ✅ 文档已自动同步到飞书
```

## 工作流程图

```
代码变更 → git add → git commit
                         ↓
                   pre-commit hook
                         ↓
              检查是否更新了文档？
                    ↙        ↘
                  是          否
                  ↓           ↓
              允许提交    阻止提交并提示
                  ↓
            post-commit hook
                  ↓
          检测到文档变更？
                ↙        ↘
              是          否
              ↓           ↓
        自动同步到飞书   跳过同步
```

## 配置说明

### 修改飞书文档 ID

如果需要同步到不同的飞书文档，修改 `post-commit` 文件中的文档 ID：

```bash
# 找到这一行
python scripts/sync_to_feishu_merged.py Dkncdyrl8oo6OvxDP9KcRHnOnLg

# 替换为你的文档 ID
python scripts/sync_to_feishu_merged.py YOUR_DOCUMENT_ID
```

### 自定义检查规则

修改 `pre-commit` 文件中的检查逻辑：

```bash
# 当前检查：Python 文件变更时必须更新文档
python_changed=$(git diff --cached --name-only | grep -E '\.py$' | wc -l)

# 可以改为：任何代码文件变更时都检查
code_changed=$(git diff --cached --name-only | grep -E '\.(py|js|ts)$' | wc -l)
```

## 卸载方法

```bash
# 删除 hooks
rm .git/hooks/pre-commit
rm .git/hooks/post-commit
```

## 注意事项

1. **首次安装**：需要手动复制并添加执行权限
2. **团队协作**：每个开发者需要在自己的本地仓库安装 hooks
3. **跳过检查**：紧急情况下可以使用 `--no-verify` 跳过 pre-commit 检查
4. **同步失败**：如果自动同步失败，会提示手动执行同步命令
5. **网络要求**：post-commit 同步需要网络连接到飞书 API

## 故障排查

### Hook 没有执行

```bash
# 检查文件是否有执行权限
ls -la .git/hooks/pre-commit

# 如果没有 x 权限，添加：
chmod +x .git/hooks/pre-commit
chmod +x .git/hooks/post-commit
```

### 同步失败

```bash
# 手动执行同步脚本查看详细错误
python scripts/sync_to_feishu_merged.py Dkncdyrl8oo6OvxDP9KcRHnOnLg

# 检查配置文件
cat .feishu_config.json
```

### Windows 环境问题

如果在 Windows 上使用 Git Bash 遇到问题：

```bash
# 确保使用 Unix 风格的换行符
dos2unix .git/hooks/pre-commit
dos2unix .git/hooks/post-commit
```

## 相关文档

- [飞书文档同步指南](../飞书文档同步指南.md)
- [飞书Wiki同步指南](../飞书Wiki同步指南.md)
- [节点使用教程](../节点使用教程.md)
