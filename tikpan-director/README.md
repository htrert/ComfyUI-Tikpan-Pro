# Tikpan AI Director

> 🎬 AI 一站式漫剧 / 短剧创作平台 — 比 BigBanana 更强，全模型绑定攀升AI中转站

---

## 核心工作流

```
一句话故事创意
    ↓ AI 生成剧本（Gemini 3.5 Flash）
多集剧本 + 分镜脚本
    ↓ AI 生成分镜插图（GPT-Image-2 / Gemini 多参考图）
角色一致性分镜图
    ↓ AI 生成配音（豆包 TTS 2.0）
配音旁白
    ↓ 导出 ZIP
在剪映/PR 中合成成片
```

## 快速开始

### 方法一：Python 直接运行

```bash
cd tikpan-director/backend

# 安装依赖
pip install flask flask-cors requests pillow python-dotenv

# 复制配置文件
cp ../.env.example ../.env
# 编辑 .env，填入你的攀升AI密钥

# 启动
python app.py
```

访问 http://localhost:7788

### 方法二：Docker（推荐）

```bash
cd tikpan-director

# 编辑 .env 文件
cp .env.example .env
# 填入 TIKPAN_API_KEY=sk-你的密钥

docker-compose up -d
```

访问 http://localhost:7788

## 获取攀升AI密钥

1. 访问 https://tikpan.com 注册账号
2. 进入控制台 → 创建 API Key
3. 在网站「设置」里填入密钥（或写入 .env 文件）

## 功能清单

- ✅ 项目管理（创建/编辑/删除漫剧项目）
- ✅ 角色库（上传参考图，保持角色一致性）
- ✅ 场景库（设定场景提示词）
- ✅ AI 剧本生成（一句话 → 完整剧本 + 分镜）
- ✅ AI 分镜图生成（支持多参考图，角色一致性）
- ✅ AI 提示词优化（自动生成正向/负向提示词）
- ✅ 批量渲染（后台并发，实时进度）
- ✅ AI 配音（豆包 TTS，批量生成）
- ✅ 导出 ZIP（图片+音频打包，可导入剪映）
- 🔜 视频生成（HappyHorse/Veo，v0.3 加入）
- 🔜 FFmpeg 自动合成整集视频

## 项目结构

```
tikpan-director/
├── backend/
│   ├── app.py              # Flask 主入口
│   ├── database.py         # SQLite ORM
│   ├── tikpan_client.py    # 攀升AI API 客户端
│   └── api/
│       ├── projects.py     # 项目 CRUD
│       ├── episodes.py     # 集 CRUD + AI生成
│       ├── characters.py   # 角色/场景资源库
│       ├── storyboards.py  # 分镜管理 + 提示词优化
│       ├── render.py       # 图片/音频渲染（支持批量）
│       ├── export.py       # ZIP 导出
│       └── settings.py     # API Key 配置
├── frontend/
│   └── index.html          # 单页应用（无需构建）
├── data/                   # 自动创建（勿提交 git）
│   ├── director.db         # SQLite 数据库
│   ├── uploads/            # 上传的参考图
│   └── outputs/            # 生成的图片/音频
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## 与 BigBanana 对比

| | BigBanana | Tikpan AI Director |
|---|---|---|
| 模型来源 | AntSK 单一平台 | 攀升AI全部模型 |
| 视频支持 | 有限 | HappyHorse/Veo（v0.3） |
| 音频支持 | 无 | 豆包TTS + Suno |
| 源码 | 闭源 | 完全开源 |
| 部署 | Docker only | Python / Docker |
| 商业使用 | 需授权 | MIT 开源 |

## 许可

MIT License — 自由使用，商业部署无限制。
