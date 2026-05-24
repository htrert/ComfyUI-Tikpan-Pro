# toki-plus 工具集 — 完整部署与使用教程

> 更新日期：2026-05-23 | 项目地址：https://github.com/toki-plus

---

## 工具集总览

| 工具 | 功能定位 | 适用人群 |
|---|---|---|
| ai-mixed-cut | 爆款视频解构重构，生成原创混剪 | 内容创作者、MCN |
| ai-highlight-clip | 长视频自动剪辑高光片段 | 直播运营、课程博主 |
| ai-ttv-workflow | 文字/文案自动转短视频 | 新媒体运营、电商 |
| AB-Video-Deduplicator | 视频去重（规避平台查重） | 批量发布运营者 |
| video-mover | 短视频自动搬运（下载/去重/发布） | 矩阵号运营 |
| auto-usps-tracker | USPS 批量物流追踪 | 跨境电商卖家 |

---

## 统一环境准备（所有工具通用）

### 系统要求

- Python 3.9 ~ 3.11（**强烈推荐 3.10**）
- FFmpeg（视频处理工具）
- Git

### 安装 Python

**Windows:**
```
下载 Python 3.10: https://www.python.org/downloads/
安装时勾选 "Add Python to PATH"
```

**Linux/macOS:**
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install python3.10 python3.10-pip python3.10-venv -y

# macOS（Homebrew）
brew install python@3.10
```

### 安装 FFmpeg

**Windows:**
```
1. 下载: https://ffmpeg.org/download.html → Windows builds
2. 解压到 C:\ffmpeg\
3. 将 C:\ffmpeg\bin 添加到系统环境变量 PATH
4. 验证：ffmpeg -version
```

**Linux:**
```bash
sudo apt install ffmpeg -y
ffmpeg -version
```

**macOS:**
```bash
brew install ffmpeg
```

---

## 工具一：ai-highlight-clip — 长视频高光剪辑

### 功能说明

将数小时的直播、课程、访谈视频自动拆解成多个短视频片段，并用 AI 评估哪些片段最有"爆款潜力"，自动生成标题。

### 安装部署

```bash
git clone https://github.com/toki-plus/ai-highlight-clip.git
cd ai-highlight-clip

# 创建虚拟环境
python -m venv venv
# Windows 激活: venv\Scripts\activate
# Linux/Mac 激活: source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 配置 AI 服务

编辑配置文件（或在 GUI 中设置）：

```ini
# 使用攀升AI中转站（国内推荐）
OPENAI_API_BASE = https://tikpan.com/v1
OPENAI_API_KEY = sk-你的攀升AI密钥

# Whisper 语音识别模型
WHISPER_MODEL = base   # tiny/base/small/medium/large
```

### 启动

```bash
python main.py
```

### 使用方法

1. 在 GUI 中选择本地视频文件（支持 mp4/mkv/avi）
2. 选择分析策略（演讲/对话/混合）
3. 设置最小片段时长（建议 30-120 秒）
4. 点击「开始分析」
5. AI 分析完成后，勾选要导出的片段
6. 点击「导出」→ 选择输出目录

---

## 工具二：ai-mixed-cut — AI 混剪工具

### 功能说明

将爆款视频素材「解构」成镜头库，再由 AI「重构」成全新的原创视频，规避版权风险。

### 安装部署

```bash
git clone https://github.com/toki-plus/ai-mixed-cut.git
cd ai-mixed-cut
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 配置

```ini
# LLM 配置（用于生成混剪脚本）
API_BASE = https://tikpan.com/v1
API_KEY = sk-你的攀升AI密钥
MODEL = gpt-4o-mini   # 或其他模型

# FFmpeg 路径（Windows 用户需指定）
FFMPEG_PATH = C:\ffmpeg\bin\ffmpeg.exe
```

### 启动

```bash
python run.py
```

### 使用方法

1. 导入素材视频（支持批量）
2. 选择「解构」→ 设置镜头最短时长（建议 2-5 秒）
3. AI 自动分析每个镜头的特征和情绪
4. 输入「重构主题」（如：积极励志/搞笑日常）
5. AI 生成混剪脚本
6. 预览并导出

---

## 工具三：ai-ttv-workflow — 文字转视频

### 功能说明

输入一段文案（文章/脚本/抖音文案），自动生成带字幕、配音、封面的短视频，支持发布到多平台。

### 安装部署

```bash
git clone https://github.com/toki-plus/ai-ttv-workflow.git
cd ai-ttv-workflow
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 核心配置

```ini
[AI]
API_BASE = https://tikpan.com/v1
API_KEY = sk-你的攀升AI密钥
TTS_MODEL = tts-1          # TTS 语音合成
IMAGE_MODEL = dall-e-3     # 图片生成

[OUTPUT]
VIDEO_DIR = ./output/videos
COVER_DIR = ./output/covers
FORMAT = mp4
RESOLUTION = 1080x1920     # 竖版短视频
```

### 启动

```bash
python app.py
```

### 使用方法

**方式 A：粘贴文案**
1. 在文本框粘贴你的文案（500-2000字最佳）
2. 选择目标平台（抖音/小红书/B站）
3. 选择配音风格（青年女声/成熟男声/专业播音）
4. 点击「一键生成」

**方式 B：抖音文案提取**
1. 粘贴抖音分享链接
2. 点击「提取文案」
3. 选择「AI二创」（去重改写）
4. 点击「生成视频」

---

## 工具四：AB-Video-Deduplicator — 视频去重

### 功能说明

使用高帧率抽帧混合算法对视频进行去重处理，生成平台无法识别为重复内容的新版本，同时保持视频质量。支持 GPU 加速。

### 安装部署

```bash
git clone https://github.com/toki-plus/AB-Video-Deduplicator.git
cd AB-Video-Deduplicator
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# GPU 加速（可选，需要 NVIDIA 显卡）
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

### 启动

```bash
python main.py
```

### 使用方法

1. 点击「添加视频」→ 选择要去重的视频文件（支持批量）
2. 选择去重强度：
   - 轻度（画质损失最小，过检率适中）
   - 中度（推荐）
   - 重度（过检率最高，画质有轻微损失）
3. 开启/关闭 GPU 加速
4. 选择输出目录
5. 点击「开始处理」

---

## 工具五：video-mover — 视频搬运平台

### 功能说明

全自动短视频搬运工具：监控源账号 → 自动下载新视频 → 去重处理 → 定时发布到你的账号。

### 安装部署

```bash
git clone https://github.com/toki-plus/video-mover.git
cd video-mover
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 安装 Selenium 浏览器驱动（用于自动化登录/发布）
# Chrome 驱动下载：https://chromedriver.chromium.org/
```

### 配置

```ini
[SOURCE]
PLATFORM = douyin      # 数据来源平台
ACCOUNTS = @account1,@account2   # 要监控的账号

[TARGET]
PLATFORM = douyin      # 目标发布平台
COOKIE_FILE = ./cookies/target.json

[SCHEDULE]
CHECK_INTERVAL = 3600  # 每隔多久检查新视频（秒）
PUBLISH_TIME = 09:00,12:00,18:00   # 发布时间点

[DEDUP]
ENABLE = true
STRENGTH = medium
```

### 启动

```bash
python run.py
```

### 首次配置流程

1. 运行后会弹出浏览器窗口
2. 手动登录目标平台账号（程序会保存 Cookie）
3. 设置监控的源账号列表
4. 确认发布计划
5. 最小化运行，等待自动搬运

---

## 工具六：auto-usps-tracker — USPS 物流追踪

### 功能说明

批量追踪 USPS 快递单号，生成 Excel 报告，支持防屏蔽爬取（代理池）。

### 安装部署

```bash
git clone https://github.com/toki-plus/auto-usps-tracker.git
cd auto-usps-tracker
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 配置

```ini
[TRACKING]
# 每次查询间隔（毫秒，避免被限流）
REQUEST_INTERVAL = 1500

# 可选：代理配置
USE_PROXY = false
PROXY_LIST = ./proxies.txt

[OUTPUT]
EXCEL_FILE = ./tracking_report.xlsx
DATE_FORMAT = %Y-%m-%d %H:%M
```

### 启动

```bash
python main.py
```

### 使用方法

**方式 A：文件导入**
1. 准备包含快递单号的 TXT 或 Excel 文件（每行一个单号）
2. 在 GUI 中导入文件
3. 点击「开始追踪」
4. 完成后导出 Excel 报告

**方式 B：手动输入**
1. 在文本框逐行输入单号
2. 点击「批量查询」

---

## 常见问题

**Q：安装依赖失败（超时/报错）**

```bash
# 使用国内 PyPI 镜像
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

**Q：GUI 界面打不开（PyQt5 报错）**

```bash
# Windows
pip install PyQt5 --force-reinstall
# Linux
sudo apt install python3-pyqt5 -y
```

**Q：FFmpeg 命令找不到**

确保 FFmpeg 已加入系统 PATH，或在配置文件中指定完整路径。

**Q：video-mover 登录 Cookie 失效**

删除 cookies 目录下的 JSON 文件，重新启动程序完成登录。
