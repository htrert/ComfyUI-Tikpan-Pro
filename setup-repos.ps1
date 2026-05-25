# ============================================================
#  Tikpan 三仓库拆分 & 推送脚本 v2
#
#  运行前确认：
#  1. GitHub 已建好两个空仓库（不勾选任何初始化选项）：
#     - https://github.com/htrert/tikpan-canvas
#     - https://github.com/htrert/tikpan-web
#  2. 关闭 VS Code / GitHub Desktop（避免 git index.lock 冲突）
#  3. 确认 git 已登录 GitHub（凭据管理器或 gh auth login）
#
#  运行方式（在项目根目录打开 PowerShell）：
#    .\setup-repos.ps1
# ============================================================

$ErrorActionPreference = "Stop"
$ROOT      = Split-Path -Parent $MyInvocation.MyCommand.Path
$CANVAS    = Join-Path $ROOT "experiments\canvas_model_studio"
$WEBAPP    = Join-Path $ROOT "web_app"
$GIT_NAME  = "htrert"
$GIT_EMAIL = "htrert@users.noreply.github.com"

function Banner($msg) {
    Write-Host ""
    Write-Host ("=" * 50) -ForegroundColor Cyan
    Write-Host "  $msg" -ForegroundColor Cyan
    Write-Host ("=" * 50) -ForegroundColor Cyan
}
function Step($msg)  { Write-Host "[+] $msg" -ForegroundColor Yellow }
function OK($msg)    { Write-Host "  OK $msg" -ForegroundColor Green }
function Info($msg)  { Write-Host "  .. $msg" -ForegroundColor Gray }

# ── 清理可能残留的 index.lock ──────────────────────────────
$lock = Join-Path $ROOT ".git\index.lock"
if (Test-Path $lock) {
    Remove-Item $lock -Force
    Info "已清除 .git/index.lock"
}

# ─────────────────────────────────────────────────────────────
# 1.  主仓库 ComfyUI-Tikpan-Pro
# ─────────────────────────────────────────────────────────────
Banner "1/3  ComfyUI-Tikpan-Pro（更新已有仓库）"
Set-Location $ROOT
git config user.name  $GIT_NAME
git config user.email $GIT_EMAIL

Step "取消追踪 web_app/ 和 experiments/"
git rm -r --cached web_app/    2>$null; $true
git rm -r --cached experiments/ 2>$null; $true

Step "暂存核心改动"
git add .gitignore
git add CHANGELOG.md
git add pyproject.toml
git add README.md
git add setup-repos.ps1
git add nodes/tikpan_gpt_image_2_official_edit_v2.py

Step "提交"
$msg = "chore: v1.3.1 — split web_app/canvas to separate repos, fix 4K 1:1 size"
git diff --cached --quiet 2>$null
if ($LASTEXITCODE -ne 0) {
    git commit -m $msg
    OK "commit done"
} else {
    Info "nothing new to commit"
}

Step "推送 main"
git push origin main
OK "ComfyUI-Tikpan-Pro 推送完成"

# ─────────────────────────────────────────────────────────────
# 2.  tikpan-canvas
# ─────────────────────────────────────────────────────────────
Banner "2/3  tikpan-canvas（新仓库）"
Set-Location $CANVAS

if (-not (Test-Path ".git")) {
    Step "git init"
    git init
    git branch -M main
}
git config user.name  $GIT_NAME
git config user.email $GIT_EMAIL

Step "暂存所有文件"
git add .

Step "提交"
$hasStaged = (git diff --cached --name-only 2>$null).Count -gt 0
if ($hasStaged) {
    git commit -m "init: tikpan-canvas v1.0.0 — local-first infinite canvas"
    OK "commit done"
} else {
    Info "already committed"
}

Step "设置远端并推送"
$remotes = git remote 2>$null
if ($remotes -notcontains "origin") {
    git remote add origin "https://github.com/htrert/tikpan-canvas.git"
}
git push -u origin main
OK "tikpan-canvas 推送完成"

# ─────────────────────────────────────────────────────────────
# 3.  tikpan-web
# ─────────────────────────────────────────────────────────────
Banner "3/3  tikpan-web（新仓库）"
Set-Location $WEBAPP

if (-not (Test-Path ".git")) {
    Step "git init"
    git init
    git branch -M main
}
git config user.name  $GIT_NAME
git config user.email $GIT_EMAIL

Step "暂存所有文件"
git add .

Step "提交"
$hasStaged = (git diff --cached --name-only 2>$null).Count -gt 0
if ($hasStaged) {
    git commit -m "init: tikpan-web v1.0.0 — AI model aggregation backend"
    OK "commit done"
} else {
    Info "already committed"
}

Step "设置远端并推送"
$remotes = git remote 2>$null
if ($remotes -notcontains "origin") {
    git remote add origin "https://github.com/htrert/tikpan-web.git"
}
git push -u origin main
OK "tikpan-web 推送完成"

# ─────────────────────────────────────────────────────────────
Banner "全部完成"
Write-Host ""
Write-Host "  ComfyUI-Tikpan-Pro  https://github.com/htrert/ComfyUI-Tikpan-Pro" -ForegroundColor White
Write-Host "  tikpan-canvas       https://github.com/htrert/tikpan-canvas"       -ForegroundColor White
Write-Host "  tikpan-web          https://github.com/htrert/tikpan-web"          -ForegroundColor White
Write-Host ""

Set-Location $ROOT
