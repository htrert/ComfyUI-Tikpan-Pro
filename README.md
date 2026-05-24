
---

# ComfyUI-Tikpan-Pro | 攀升AI官方插件

<p align="center">
  <img src="https://img.shields.io/badge/Official-Tikpan.com-red?style=for-the-badge" alt="Tikpan Official">
  <img src="https://img.shields.io/badge/ComfyUI-Registry-green?style=for-the-badge" alt="Registry">
  <img src="https://img.shields.io/badge/Version-1.3.0-blue?style=for-the-badge" alt="Version">
</p>

**ComfyUI-Tikpan-Pro** 是由 [攀升AI (Tikpan.com)](https://tikpan.com/) 官方发布的深度集成插件。专为 **TikTok 电商矩阵运营**、**高阶内容创作**及 **AI 工作流自动化**设计，通过接入自有的高稳定性 API 渠道，为全球创作者提供顶级的模型生成能力。

---

## 📚 文档入口

* [节点使用教程](docs/节点使用教程.md)：从安装、选节点、连接工作流到常见问题排查，适合实际使用者照着跑通。
* [节点速查表](docs/节点速查表.md)：按图片、视频、音频、分析工具整理关键参数和输出，适合后续做 Web 网站表单、供应商渠道和计费映射。
* [节点功能分类](docs/Tikpan_ComfyUI_节点功能分类.md)：对齐 ComfyUI 菜单分组，适合维护新增节点时检查放置位置。
* [更新日志](CHANGELOG.md)：记录每个版本新增节点、修复项、文档同步和验证结果。

---

## 🌟 核心集成模型

本插件通过云端 API 模式，让您的本地 ComfyUI 具备生产顶级素材的能力：

**图片生成**

* **GPT-Image-2 Official**：官方生图与修图，支持多参考图、遮罩区域重绘、高分辨率。
* **GPT-Image-2-all（生图/修图）**：最多 14 张参考图的多模态图像生成与修图节点。
* **Gemini 14图极限生图**：Gemini 图像模型，最多 14 张参考图融合。
* **Grok Imagine Image / Pro**：Grok 图像生成，支持文生图与最多 3 张参考图修图。
* **Nano Banana Pro**：Gemini 图像链路，支持多参考图、温度和 token 控制。
* **Qwen-Image-2.0**：通义千问图像模型，文生图/图生图/多参考图。
* **Wan 2.7 Image Pro**：支持 4K 分辨率和 thinking 深度推理模式。
* **豆包图像生成 Seedream**：Doubao 5.0 图像，支持联网搜索增强和多图生成。

**视频生成**

* **HappyHorse 1.0 系列**：文生视频、图生视频、多参考图生视频、视频编辑，支持同步/异步模式。
* **Grok-Videos**：Grok 视频生成，支持最多 4 张参考图。
* **Veo 3.1**：Google Veo 3.1 多模型，lite/fast/pro/components，支持首尾帧和 components 垫图。
* **Kling Motion Control**：Kling v2.6/v3.0 动作控制，把角色图像+动作参考视频合成新视频。
* **Vidu3 参考生视频**：最多 7 张参考图，通过 `@1`/`@2` 保持角色一致性生视频。
* **Vidu3 Turbo**：快速文生/图生/首尾帧视频，底层模型 `viduq3-turbo`。
* **Gemini Omni Flash**：多模态视频生成，支持文生/图生/多参考/编辑/音频驱动五种模式。

**音频生成**

* **Suno 音乐生成**：歌曲/纯音乐/续写/歌手风格，支持 V5/Fenix/V4/Auk 等模型。
* **speech-2.8-hd / speech-2.8-turbo**：MiniMax 高清/极速语音合成，支持 100+ 音色。
* **豆包语音合成 2.0**：Doubao TTS，覆盖中文口播、角色音色和多语种。
* **Gemini 3.1 Flash TTS Preview**：Google Gemini TTS，30 个预置音色，低延迟。

**多模态推理与分析**

* **GPT-5.4 Mini 推理**：Responses API，支持图片/视频抽帧/文件分析、联网搜索和 reasoning_effort。
* **Gemini 3 Flash Preview 分析**：图片/视频理解，支持视频 URL 和抽帧分析，输出报告/提示词/JSON。
* **Gemini 3.5 Flash 推理**：长文档/复杂推理，支持 thinking 深度推理（8192 token）和本地文件 inline。
* **Grok 多图剧本重构**：把视频分析报告重构成 Grok 视频专属提示词。
* **AI 音视频双轨解析**：音视频双轨同时分析，输出专业镜头拆解报告。

**工具节点**

* **异步任务查询与下载**：已提交任务按 task_id 继续轮询下载。
* **API 多模型并发生图引擎**：failover 容灾/race 抢速/parallel 全量三种策略。
* **异步图片任务组**（Submit / Result / Join / List）：后台并行提交多个任务，统一收图。

---

## 🛠️ 安装指南

### 方案 A：官方商店安装（推荐）
1. 在 ComfyUI 侧边栏打开 **Manager（自定义节点管理器）**。
2. 搜索关键词 **`Tikpan`**。
3. 点击 **Install**，重启软件即可完成。

### 方案 B：本地解压安装（零网络门槛）
1. [点击此处下载](https://github.com/htrert/ComfyUI-Tikpan-Pro/archive/refs/heads/main.zip) 源码压缩包。
2. 解压后将整个文件夹移动至 `ComfyUI/custom_nodes/` 目录下。
3. 重启 ComfyUI。

---

## 🔑 配置与授权

1.  **访问官网**：前往 [Tikpan.com (攀升AI聚合)](https://tikpan.com/) 注册账号。
2.  **获取密钥**：在个人中心获取您的专属 `API Key`。
3.  **节点填入**：在 ComfyUI 画布中新建 Tikpan 节点，在 `api_key` 字段处填入您的密钥即可。
4.  **计费模式**：平台采用虚拟令牌（Virtual Tokens）结算，支持多种支付方式，告别外币支付烦恼。

---

## 💼 关于 Tikpan (攀升AI)

攀升AI (Tikpan) 是一家专注于跨境电商与 AI 自动化解决方案的专业平台。
* **TikTok 矩阵运营**：提供从获客、内容生产到账号分发的全链路技术支持。
* **1:1 复刻行业专家**：专业提供高品质供应链信息流转服务。
* **API 聚合服务**：致力于将全球最先进的生成式 AI 能力，以最低的门槛交付给每一位实干家。

---

## 📜 许可协议 (License)

本项目采用 [MIT License](https://opensource.org/licenses/MIT)。
*“技术应当服务于效率，攀升 AI 助力每一位中国出海卖家。”*

---
