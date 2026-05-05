潘总，一份优秀的 README 不仅是给分销商看的“说明书”，更是你 Tikpan 平台的“脸面”。

结合咱们之前的调试经历和你平台的业务重心（TikTok 电商、高阶 AI 模型），我为你准备了一份**既专业又通俗**的完整版 `README.md`。你可以直接全选复制，替换掉仓库里原有的内容。

---

# ComfyUI-Tikpan-Pro | 攀升AI官方插件

<p align="center">
  <img src="[https://img.shields.io/badge/ComfyUI-Registry-green](https://img.shields.io/badge/ComfyUI-Registry-green)" alt="Registry">
  <img src="[https://img.shields.io/badge/Version-0.0.9-blue](https://img.shields.io/badge/Version-0.0.9-blue)" alt="Version">
  <img src="[https://img.shields.io/badge/License-MIT-orange](https://img.shields.io/badge/License-MIT-orange)" alt="License">
</p>

**ComfyUI-Tikpan-Pro** 是由 [攀升AI聚合平台](https://github.com/htrert) 官方开发的深度集成插件。专为 TikTok 电商运营、高阶内容创作及 AI 自动化工作流设计，提供极其稳定的云端模型调用能力。

---

## 🚀 核心能力

本插件集成了多款业界顶尖的 AI 大模型，无需本地高配显卡，一键接入：

* **GPT-Image-2 (Official)**：支持超强的高级多图编辑、风格迁移与精准图像生成，是目前 1:1 复刻级内容生成的首选。
* **Google Veo / Sora**：接入最前沿的视频生成模型，提供原生高保真视频素材生产能力。
* **Grok-3 / GPT-4o**：集成深度搜索与逻辑分析模型，助力 TikTok 选品建议与营销文案生成。
* **TikTok UGC 优化**：针对短版视频平台算法，输出更具“原生感”和“生活化”的视频内容，提升账号权重。

---

## 🛠️ 安装教程

### 方式一：官方管理器安装（推荐）
1. 在 ComfyUI 界面打开 **Manager（自定义节点管理器）**。
2. 点击 **Install Custom Nodes**，搜索关键词 **`Tikpan`**。
3. 点击 **Install**，重启后即可使用。

### 方式二：命令行安装 (CLI)
在 ComfyUI 根目录下执行：
```bash
comfy node install comfyui-tikpan-pro
```

### 方式三：手动安装（免翻墙，零成本）
1. [点击此处下载](https://github.com/htrert/ComfyUI-Tikpan-Pro/archive/refs/heads/main.zip) 源码压缩包。
2. 解压后将 `ComfyUI-Tikpan-Pro` 文件夹放入你的 `ComfyUI/custom_nodes/` 目录中。
3. 重启 ComfyUI 即可。

---

## ⚙️ 配置说明

1.  **获取 API Key**：请前往 [攀升AI聚合平台]([https://github.com/htrert](https://tikpan.com/)) 获取您的专属访问密钥。
2.  **填入节点**：在 Tikpan 系列节点中的 `api_key` 字段处填入您的密钥。
3.  **计费说明**：平台采用虚拟令牌（Internal Tokens）计费模式，确保高阶模型的使用成本更具竞争力。

---

## 🤝 商务合作与反馈

* **开发者**：htrert
* **官方平台**：攀升AI (Tikpan)
* **核心业务**：高阶 1:1 复刻信息分销、TikTok 矩阵运营自动化、AI 工作流定制。
* **反馈通道**：如有 Bug 或功能建议，请提交 [GitHub Issue](https://github.com/htrert/ComfyUI-Tikpan-Pro/issues)。

---

## 📜 开源协议 (License)

本项目遵循 [MIT License](https://opensource.org/licenses/MIT)。
*“随便使用，标注来源，玩的开心。”*
