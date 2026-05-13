# Changelog

## [v1.1.10] - 2026-05-13

### Improvements

- 全面复查 ComfyUI 节点输入参数，继续补齐中文参数名，并保留旧工作流英文 key 兼容读取。
- 新增共享参数选项工具，统一下拉项原始值解析、旧参数兼容读取、视频时长解析和随机种子规范化。
- 将旧工作流中的 `seed=-1` 规范化为默认固定种子 `888888`，新节点界面不再展示负数随机种子；同时修复 seed 上限边界取模问题。
- Suno 节点新增模型版本、风格预设、人声性别等下拉项，并通过“发送高级Suno参数”开关控制 `style_weight`、`weirdness_constraint`、`vocal_gender` 等高级字段是否透传。
- Nano Banana Pro / Gemini 图像节点补齐分辨率、画面比例、输出 token 说明，并兼容 Gemini REST `responseFormat.image` 与 SDK/中转层 `imageConfig` 两种图像尺寸配置写法。
- HappyHorse、Veo、Grok、Doubao、GPT Image、任务查询等节点继续统一中文化 `API_密钥`、`生成指令`、`水印`、`视频时长`、`最长等待秒数`、`查询间隔秒数` 等字段。
- 新增豆包 TTS 2.0 节点注册，继续绑定 Tikpan 中转站与对应语音合成端点。

### Validation

- 使用 Aki 自带 Python 通过 `compileall` 编译检查 `nodes` 与 `tests`。
- 新增并通过节点契约离线测试，覆盖 seed 规范化、Suno 下拉/高级参数门控、Nano Banana Pro 图像尺寸 payload、Gemini 图像字段兼容。
- 通过语音节点、Gemini 3 Flash Preview 分析节点、GPT-5.4 Mini Responses 节点离线测试。

## [v1.1.9] - 2026-05-12

### New Features

#### GPT-5 Mini 多模态推理节点 (`TikpanGPT5MiniResponsesNode`)
- 新增 `gpt-5-mini` Responses API 节点，默认调用 `POST /v1/responses`，面向低成本文本推理、图片理解、文件分析、视频抽帧分析、提示词优化和广告/商品分析。
- 支持直接图片 1-4、图片 URL 列表、视频帧 `IMAGE` 抽帧、文件 URL、本地小文件 inline、可选联网搜索工具和高级 JSON 透传。
- 支持 `reasoning_effort`、`verbosity`、`max_output_tokens`、JSON 结构化输出和提示词优化输出，便于后续网站做模型参数表单。
- 优化视频抽帧：新增 `均匀覆盖`、`按秒抽帧`、`首尾加密`、`运动变化优先`、`混合智能` 五种策略，并在输入标注原帧序号和时间点。
- 固定 `API_HOST = "https://tikpan.com"`，节点不再暴露接口地址输入，避免用户误填上游地址；模型、推理强度、输出风格、图片细节、URL 错误处理和 POST 重试策略均改为下拉/开关。
- 强化商业稳定性：优先按 Responses 标准输出路径提取文本，补充状态/截断解释、固定分段输出协议、媒体数量统计、成本风险提示和文件/图片总量限制。
- 增加本地缓存、recovery 记录、幂等 key、提交后断网警告、HTTPS 证书默认校验和大文件请求前拦截，降低重复扣费与不可恢复失败风险。
- 输出回答文本、优化提示词、结构化 JSON、token 用量和状态日志，方便网站侧余额扣费、审计和任务追踪。

#### Gemini 3 Flash Preview 图片/视频分析节点 (`TikpanGemini3FlashPreviewAnalystNode`)
- 新增 `gemini-3-flash-preview` 多模态分析节点，面向图片理解、视频 URL 理解、本地小视频理解和视频抽帧分析，不做图片/视频生成。
- 支持 4 张直接图片、图片 URL 列表、视频帧 `IMAGE`、本地视频路径、公开视频 URL 和高级 JSON 透传。
- 输出分析报告、反推提示词、结构化 JSON、token 用量和状态日志，方便后续网站按量计费、任务记录和结果展示。
- 优化视频抽帧：新增 `均匀覆盖`、`按秒抽帧`、`首尾加密`、`运动变化优先`、`混合智能` 五种策略，并在输入标注原帧序号和时间点。
- 固定 `API_HOST = "https://tikpan.com"`，节点 API 路径绑定 Tikpan 中转站；新增模型下拉、视频输入策略、URL 错误处理和 POST 重试策略，减少用户填写开放参数。
- 强化商业稳定性：优先按 Gemini `candidates.content.parts.text` 标准路径提取结果，补充 `finishReason`、安全阻断摘要、空 candidates 解释、固定分段输出协议、媒体统计和高成本输入警告。
- 增加本地缓存、recovery 记录、幂等 key、网络提交后断开提示，降低重复运行导致多次扣费的风险。
- 对本地大视频做请求前拦截，建议改用视频 URL 或抽帧分析，避免大文件上传不稳定。
- 默认校验 HTTPS 证书，并提供高级开关兼容特殊本地代理或自签名测试环境。

#### 旧语音节点 Tikpan 中转站绑定与商业化收口
- `TikpanGemini31FlashTTSNode` 固定 `API_HOST = "https://tikpan.com"`，不再暴露接口基础地址；按调用方式自动拼接 Gemini 原生或 OpenAI 兼容路径。
- `TikpanMiniMaxSpeech28HDNode` / `TikpanMiniMaxSpeech28TurboNode` 固定 `https://tikpan.com/minimax/v1`，不再暴露 MiniMax 基础地址输入。
- 语音节点新增 `POST重试策略` 与 `校验HTTPS证书`，默认启用幂等键轻重试和 HTTPS 证书校验，更适合正式商业交付。
- Gemini TTS 的 `语言代码` 改为下拉选择，默认“自动”，降低普通用户填写语言代码的理解成本。

#### 旧视频/提示词节点 HTTPS 策略迁移
- `TikpanGeminiVideoAnalystNode`、`TikpanGrokPromptOptimizerNode`、`TikpanExclusiveVideoNode`、`TikpanVeoVideoNode` 默认启用 HTTPS 证书校验。
- 为上述旧节点补充 `校验HTTPS证书` 开关，兼容少数本地代理/证书异常环境，同时让正式商业使用走更安全的默认值。

### Validation

- 使用 Aki 自带 Python 编译检查 `__init__.py` 和 `nodes/tikpan_gemini3_flash_preview_analyst.py`。
- 完成离线契约测试：payload 构造、图片/视频 URL 打包、幂等哈希稳定性、本地大视频拦截、JSON 输出拆分和非法 URL 校验。
- 补充抽帧策略离线测试：验证抽帧数量边界、首尾覆盖、运动变化策略和抽帧标签。
- 使用 Aki 自带 Python 编译检查 `nodes/tikpan_gpt5_mini_responses.py` 和 `tests/test_gpt5_mini_responses_offline.py`。
- 完成 GPT-5 Mini 离线契约测试：Responses payload、图片/文件 URL、联网搜索工具、JSON 输出格式、幂等哈希、本地文件 inline、大文件拦截、错误输入校验、文本与用量提取。
- 补充 GPT-5 Mini 抽帧策略离线测试：验证抽帧数量边界、首尾覆盖、运动变化策略和抽帧标签。
- 新增语音节点离线契约测试：验证 Gemini TTS 与 MiniMax speech 节点不再暴露接口基础地址、绑定 Tikpan 中转站、POST 重试/HTTPS 参数存在，以及核心 payload 构造稳定。
- 使用 Aki 自带 Python 编译检查旧视频/提示词节点 HTTPS 迁移，确认四个节点语法通过且目标文件不再残留 `verify=False`。

## [v1.1.0] - 2026-05-11

### 🔧 Improvements

#### Gemini 3.1 Flash TTS Preview 节点 (`TikpanGemini31FlashTTSNode`)
- 新增 `gemini-3.1-flash-tts-preview` 文字转语音节点，支持 `geminitts` / `gemini` 原生 `generateContent` 以及 OpenAI 兼容 `/v1/chat/completions`。
- 按官方 Gemini TTS 结构传递 `responseModalities: ["AUDIO"]`、`speechConfig.voiceConfig.prebuiltVoiceConfig.voiceName`。
- 自动提取 `inlineData.data` 音频；对裸 PCM 自动封装成 24kHz/16-bit/mono WAV，便于直接连接 `PreviewAudio` / `SaveAudio`。
- 输出本地音频路径、接口路径、输入/输出 token 用量、状态日志和 `AUDIO` 音频流。
- 增加本地缓存复用、recovery 记录、幂等 key、非 JSON/错误页/空音频检测，降低网络中断和误重复扣费风险。

#### speech-2.8 高清/极速语音合成节点
- 新增 MiniMax `speech-2.8-hd` 语音合成节点，支持同步 `/t2a_v2` 与异步 `/t2a_async_v2` 两种链路。
- 新增 MiniMax `speech-2.8-turbo` 语音合成节点，复用同一套 T2A 接口和稳定性处理，适合更快响应和批量配音预览。
- 支持音色 ID、语言增强、语速、音量、音调、情绪、采样率、比特率、`mp3/wav/flac` 输出、字幕、发音字典、音色混合与高级 JSON 透传。
- 新增 `AUDIO` 音频流输出，可直接连接 `PreviewAudio` / `SaveAudio`；同时输出本地路径、音频链接、任务 ID、文件 ID、计费字符数和状态日志。
- 增加本地缓存复用与 recovery 记录，降低网络中断或重复运行导致的多次扣费风险。
- 增强错误处理：校验上游 `base_resp`、非 JSON 响应、空音频、错误页下载、异步失败/超时等情况。

#### Veo 3.1 视频节点 (`TikpanVeoVideoNode`)
- 将 Veo 节点收窄为 Tikpan 价格页中确认的 7 个模型：`veo_3_1-lite`、`veo_3_1-lite-4K`、`veo_3_1-fast-4K`、`veo3.1-fast-components`、`veo3.1-pro`、`veo_3_1-components-4K`、`veo_3_1-fast-components-4K`。
- 按模型分端点提交：lite/fast/components-4K 走 OpenAI 视频格式 `POST /v1/videos`；`veo3.1-fast-components` 与 `veo3.1-pro` 走视频统一格式 `POST /v1/video/create`。
- 对齐官方 Veo 3.1 比例能力，将节点比例选项收窄为 `16:9` 与 `9:16`。
- 新增 `垫图_1~3` 输入，components 模型可传最多 3 张参考垫图；非 components 模型接入垫图时会返回明确错误。
- 增强任务 ID、视频 URL 和状态解析，兼容更多 Tikpan/上游返回结构。
- 增强视频下载校验：检查 HTTP 状态、内容类型和文件大小，避免把错误页保存成 `.mp4`。
- 增强 `VIDEO` 输出包装：读取本地视频为 `BytesIO` 并预先校验尺寸，提高连接 ComfyUI 原生 `Save Video` 节点时的兼容性。
- 下载文件名中加入模型名，方便区分 lite、fast、pro 和 components 输出。

## [v1.0.1] - 2026-05-10

### 🚀 New Features

#### Suno 音乐生成节点 (`TikpanSunoMusicNode`)
- 新增两个 `AUDIO` 音频流输出，可直接连接 ComfyUI 的 `PreviewAudio` / `SaveAudio` 等音频节点。
- 保留原有音频路径、音频链接、任务 ID、片段 ID 等字符串输出，方便继续排查上游返回内容。
- 新增 `负面风格标签` 输入，对应 Suno API 的 `negative_tags` 参数。
- 补充模型选项 `chirp-auk`，并保留 `chirp-v3-0`、`chirp-v3-5`、`chirp-v4`、`chirp-v5`、`chirp-fenix`。

#### HappyHorse 视频节点
- 新增通用辅助模块 `tikpan_happyhorse_common.py`，统一处理任务状态、视频链接提取、视频下载与 ComfyUI `VIDEO` 输出。
- `HappyHorse T2V`、`I2V`、`R2V`、`Video-Edit` 四个节点均新增 `VIDEO` 输出，方便后续接入完整视频工作流。

#### GPT-Image-2 恢复能力
- 新增 `tikpan_gpt_image_recovery.py` 恢复辅助节点，用于读取本地 recovery 记录，帮助找回上游已返回但本地下载/回传失败的图片信息。

### 🐛 Bug Fixes

#### Suno 音乐生成节点 (`TikpanSunoMusicNode`)
- 修复提交参数字段错误：将原来的 `model` 改为文档要求的 `mv`，避免中转站/上游因参数不兼容导致任务失败。
- 修复任务查询路径：优先使用 `/suno/fetch/{task_id}`，并保留 `?id=` 与批量 `/suno/fetch` 作为兼容 fallback。
- 修复云雾/Tikpan 返回结构解析：兼容 `data.data` 音乐数组、`data` 直接数组、`clips`、`items` 等多种任务结果格式。
- 修复歌手风格模式参数：按文档使用 `artist_consistency`，并自动将普通模型映射到 `chirp-v*-tau` 形式。
- 将 `generation_type` 调整为文档示例中的 `TEXT`，减少上游参数不兼容概率。

#### Doubao 图像生成节点 (`TikpanDoubaoImageNode`)
- 对齐 Tikpan 中转站的 Doubao 5.0 图像接口参数，默认使用 `doubao-seedream-5-0-260128`。
- 保留文档要求的 `2K` / `3K` 分辨率写法与 `output_format` 参数。
- 移除容易造成兼容问题的默认负面提示词与不必要的 `sequential_image_generation: disabled`。

### 🔧 Improvements

#### 视频节点链路
- `Grok Video`、`Grok Videos`、`Veo Video` 节点新增 `VIDEO` 输出，保留原有字符串路径/链接输出。
- 异步任务查询节点 `TikpanTaskFetcherNode` 新增 `VIDEO` 输出，可用于提交任务后单独轮询并继续传递视频流。
- HappyHorse 系列节点增强状态识别与视频 URL 提取，兼容更多上游返回字段。

#### GPT-Image-2 节点
- 增强上游返回数据保存与恢复提示，降低“上游已扣费但本地下载失败”时完全找不到结果的风险。
- 在部分失败场景中保留更完整的错误信息、任务信息或可恢复记录，方便后续人工排查。

#### 项目元数据
- `pyproject.toml` 版本更新至 `1.0.1`。
- 更新项目描述，覆盖 GPT-Image-2、Doubao、Suno、HappyHorse、Grok、Veo 等图像、音频与视频节点。
- 新增 `keywords` 标签：`tikpan`、`gpt-image-2`、`doubao`、`suno`、`happyhorse`、`grok`、`veo`、`image-generation`、`video-generation`、`audio-generation` 等。

### ✅ Validation

- 已使用 Aki 自带 Python 执行节点编译检查：
  - `C:\ComfyUI-aki-v2\python\python.exe -m compileall -q .\nodes`
- Suno 节点已做本地 payload 构造、返回数量、任务状态解析的基础自检。

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
