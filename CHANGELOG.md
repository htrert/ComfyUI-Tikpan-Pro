# Changelog

## [v0.1.0] - 2026-05-07

### 🐛 Bug Fixes

#### 实质是香蕉2 / Gemini 14图极限生图节点 (`TikpanGeminiImageMaxNode`)
- **修复：选择2K/4K分辨率但实际未生成对应尺寸图片的问题**
  - 核心原因：API 的 `imageSize` 参数必须传递像素值（如 `'1152x2048'`），之前传递 `'2K'` 等字符串导致 API 端不识别，退回默认低分辨率。
  - 新增 `calc_pixel_size()` 方法，将 `'1K'`/`'2K'`/`'4K'` 字符串结合画面比例，精确换算为像素值（如 `1152x2048`、`2048x1152`），并对齐至 8 的倍数。
  - 新增 `ensure_target_resolution()` 方法，当 API 返回的实际图片分辨率低于请求目标时，自动采用 Lanczos 高质量上采样至目标分辨率，作为保底方案。
  - Gemini 原生调用中，`generationConfig.imageConfig` 正确传递解析后的像素级 `imageSize`。
  - `images_generations` 调用中，正确传递 `size`（比例）+ `resolution`（像素级）。
  - `chat_completions` 调用中，正确传递 `image_config.image_size` 及 `generationConfig.imageConfig.imageSize`。

### 🚀 New Features

#### 新增：Nano Banana Pro 节点 (`TikpanNanoBananaProNode`)
- **全新独立的 Banana Pro 图像生成节点**，命名：`🍌 Tikpan: Nano Banana Pro`
- 支持的模型：`gemini-3-pro-image-preview`、`gemini-3.1-flash-image-preview`
- 两种调用方式：
  - **Gemini 原生**（`/v1beta/models/{model}:generateContent`）：完整支持 `generationConfig.responseModalities` 和 `imageConfig`，可获取图片+文本双模态输出。
  - **OpenAI 兼容**（`/v1/chat/completions`）：通过 `image_config` 传递比例和分辨率参数。
- 分辨率支持：`2K` / `4K` / `1K` / `none`，同样内置像素值换算及保底 Lanczos 上采样逻辑。
- 画面比例：支持 9 种带中文描述的选项（如 `9:16 | 9:16竖屏`），更直观易用。
- 新增参数：`温度`（FLOAT, 0.0~2.0）、`max_tokens`（INT, 1~32768），精细化控制生成效果。
- 最多支持 14 张参考图输入，支持文生图与图生图。
- 完善的图片提取逻辑：兼容 Gemini 原生 `inlineData` 和 OpenAI 兼容格式的 `b64_json`、`url` 等多种响应结构。

### 🔧 Improvements

- 两节点均增强响应提取能力：支持从 Markdown 图片语法、data URL、裸 base64、http/https URL 等多种嵌套结构中精准提取图片数据。
- 完善的日志输出：每个节点运行过程输出详细的 URL、payload、分辨率换算、提取来源和实际输出尺寸，便于排查问题。
