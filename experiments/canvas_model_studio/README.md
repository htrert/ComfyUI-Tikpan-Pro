# Canvas Model Studio · 本地版

无限画布 AI 创作工具，连接本地 ComfyUI 和云端模型 API（Tikpan / New API 兼容）。
不需要账户，不需要安装，不写注册表，所有数据都在软件文件夹内。

---

## 快速启动

**Windows**：双击 `start.bat`

**Mac / Linux**：
```bash
chmod +x start.sh && ./start.sh
```

启动后浏览器会自动打开 `http://127.0.0.1:3456`，
首次使用会弹出设置面板，填入 API 密钥即可开始。

---

## 文件布局

```
canvas_model_studio/
├── start.bat            ← Windows 一键启动
├── start.sh             ← Mac/Linux 一键启动
├── server.js            ← 本地服务主程序
├── public/              ← 前端页面（不需要修改）
│
├── data/                ← ★ 所有用户数据都在这里 ★
│   ├── local-config.json      API 密钥 + ComfyUI 地址
│   ├── canvas-autosave.json   画布自动保存（实时写入）
│   ├── model-profiles.json    模型参数档案
│   ├── platform-config.json   平台路由配置
│   ├── projects/              手动保存的项目文件
│   └── assets/                生成/导入的资产元数据
│
└── logs/                ← 运行日志（按日期分文件）
    └── canvas-YYYY-MM-DD.log
```

**备份**：复制 `data/` 文件夹即可保存全部数据。
**迁移**：复制整个 `canvas_model_studio/` 文件夹到新电脑，再运行 `start.bat`。
**卸载**：删除 `canvas_model_studio/` 文件夹，无任何残留（不写注册表，不改系统文件）。

---

## 手动启动（高级）

```powershell
cd canvas_model_studio
node server.js
```

可选环境变量（优先级高于 data/local-config.json 里的设置）：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `PORT` | 监听端口 | `3456` |
| `TIKPAN_API_KEY` | API 密钥（覆盖 local-config.json）| — |
| `COMFY_URL` | ComfyUI 地址 | `http://127.0.0.1:8188` |
| `PROVIDER` | 生成模式：`comfy` 或 `upstream` | `comfy` |

---

## 已内置的模型档案

| 档案 | 节点 | 说明 |
|------|------|------|
| GPT Image 2 官方生图 | `TikpanGptImage2OfficialNode` | 文字生图 |
| GPT Image 2 图片编辑 | `TikpanGptImage2OfficialEditV2` | 选图编辑 |
| Nano Banana Pro / Gemini | `TikpanNanoBananaProNode` | 多参考图生图 |
| 豆包 Seedream 5.0 | `TikpanDoubaoImageNode` | 商品图 |
| Veo 3.1 视频 | `TikpanVeoVideoNode` | 首尾帧生视频 |
| Grok 视频 | `TikpanExclusiveVideoNode` | 参考图生视频 |
| Suno 音乐 | `TikpanSunoMusicNode` | AI 作曲 |

---

## 依赖

- **Node.js** 18 LTS 以上（https://nodejs.org）
- **本地 ComfyUI**（可选，Tikpan 节点需要）
- **Tikpan API 密钥**（https://tikpan.com 获取）
