<p align="center">
  <img src="https://img.shields.io/badge/tikpan--canvas-v1.0.0-2cf0b6?style=for-the-badge" alt="version">
  <img src="https://img.shields.io/badge/Node.js-18+-339933?style=for-the-badge&logo=node.js" alt="nodejs">
  <img src="https://img.shields.io/badge/Local--First-no%20account-orange?style=for-the-badge" alt="local">
  <img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="license">
</p>

<h1 align="center">tikpan-canvas</h1>
<p align="center">面向 AI 创作者的无限画布工具 · 本地运行 · 无需账户 · 双击即用</p>

---

## 这是什么

**tikpan-canvas** 是一个跑在本地的 AI 无限画布工具。你在画布上放 Prompt 卡片，选模型，点生成，结果图片直接贴回画布旁边。支持图片编辑、视频生成、音乐生成，以及内容工厂工作流（短剧/小说推文/电商素材）。

底层通过本地 ComfyUI 调用 [攀升AI (tikpan.com)](https://tikpan.com) 的云端模型 API，不需要自己搭模型环境。

**特点：**
- 无账户体系，无注册，无登录
- 所有数据存在软件文件夹内，复制文件夹即可迁移
- 不写注册表，不改系统文件，删除文件夹无任何残留
- API Key 加密存本地，不上传任何服务器

---

## 快速开始

**前置条件：** [Node.js 18+](https://nodejs.org) · [本地 ComfyUI](https://github.com/comfyanonymous/ComfyUI)（可选）· [tikpan.com](https://tikpan.com) API 密钥

### Windows

```bat
双击 start.bat
```

### Mac / Linux

```bash
chmod +x start.sh && ./start.sh
```

启动后浏览器自动打开 `http://127.0.0.1:3456`，首次使用弹出设置面板，填入 API 密钥即可开始。

---

## 界面预览

```
┌──────────────────────────────────────────────────────────┐
│  侧边栏                   │         无限画布              │
│  ─────────────────────    │                               │
│  本地配置                 │   [Prompt卡片]  [图片节点]    │
│  ● API密钥：已配置        │                               │
│  ● ComfyUI：已连接        │      [生成结果]  [Prompt卡片] │
│                           │                               │
│  参数档案选择             │   双击空白处 → 选择模型       │
│  模型参数                 │   右键节点 → 复制/删除        │
│  生成到画布 [Ctrl+Enter]  │   滚轮缩放 · 拖拽平移         │
└──────────────────────────────────────────────────────────┘
```

---

## 支持的模型

| 类型 | 模型 | 说明 |
|------|------|------|
| 图片生成 | GPT Image 2 | 文字生图，支持 1K/2K/4K |
| 图片编辑 | GPT Image 2 Edit | 选图后编辑，支持遮罩 |
| 图片生成 | Gemini / Nano Banana Pro | 多参考图融合生图 |
| 图片生成 | 豆包 Seedream 5.0 | 商品图、多图参考 |
| 视频生成 | Veo 3.1 | 首尾帧生视频，支持 4K |
| 视频生成 | Grok Video | 多参考图生视频 |
| 音乐生成 | Suno | 自定义风格、歌词、续写 |

---

## 文件结构

```
tikpan-canvas/
├── start.bat / start.sh     一键启动脚本
├── server.js                本地 HTTP 服务
├── public/                  前端页面
│
├── data/                    ★ 所有用户数据
│   ├── local-config.json    API 密钥 + ComfyUI 地址（不上传 git）
│   ├── canvas-autosave.json 画布自动保存（不上传 git）
│   ├── model-profiles.json  模型参数档案（可上传）
│   ├── projects/            手动保存的项目
│   └── assets/              资产元数据
│
└── logs/
    └── canvas-YYYY-MM-DD.log  每日运行日志
```

**备份**：复制 `data/` 文件夹  
**迁移**：复制整个文件夹到新电脑，运行 `start.bat`  
**卸载**：直接删除文件夹

---

## 环境变量（可选覆盖）

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `TIKPAN_API_KEY` | API 密钥（覆盖 local-config.json） | — |
| `COMFY_URL` | ComfyUI 地址 | `http://127.0.0.1:8188` |
| `PORT` | 监听端口 | `3456` |
| `PROVIDER` | `comfy` 或 `upstream` | `comfy` |

---

## API 接口

| 端点 | 说明 |
|------|------|
| `GET /api/config` | 查看当前配置状态 |
| `POST /api/config` | 保存 API Key 和 ComfyUI 地址 |
| `GET /api/autosave` | 读取画布自动保存 |
| `POST /api/autosave` | 写入画布状态 |
| `POST /api/generate` | 提交生成任务 |
| `GET /api/logs?tail=100` | 查看近期运行日志 |
| `GET /api/profiles` | 获取模型档案列表 |
| `GET /api/data-path` | 获取数据目录绝对路径 |

---

## 与 ComfyUI-Tikpan-Pro 的关系

本项目是 [ComfyUI-Tikpan-Pro](https://github.com/htrert/ComfyUI-Tikpan-Pro) 插件的配套本地画布工具。  
ComfyUI-Tikpan-Pro 提供节点能力，tikpan-canvas 提供可视化操作界面。

---

## License

MIT © [htrert](https://github.com/htrert)
