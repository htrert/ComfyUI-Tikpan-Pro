# Changelog

## Documentation Maintenance Index

## [v1.4.4] - 2026-06-30

### Fixed - Grok Video 1.5 福利通道 seconds 字段类型

- 将 `TikpanGrokVideo15BenefitNode` 的 `seconds` 改为字符串提交，修复 relay 返回 `invalid_json` / `cannot unmarshal number into Go struct field .Alias.seconds of type string`。
- 同步更新离线契约测试，确认 `build_payload()` 输出的 `seconds` 为字符串。

### Verification

```bash
python -m py_compile nodes/tikpan_grok_video_15_benefit.py tests/test_node_contracts_offline.py
python tests/test_node_contracts_offline.py
```

## [v1.4.3] - 2026-06-29

### Fixed - Grok Video 1.5 福利通道节点与离线契约

- 新增 `TikpanGrokVideo15BenefitNode`，固定走 `POST /v1/video/generations`，并支持 `seconds` 时长参数。
- 将 Grok Video 1.5 主模型名切换为 `grok-video-1.5`，保留旧别名 `119337-grok-video-1.5` 作为兜底。
- 修复节点 UI 和离线测试中的乱码字符串，恢复 ComfyUI 下拉选项与显示名。
- 离线测试文件重建为可编译版本，补充福利节点契约断言。

### Verification

```bash
python -m py_compile nodes/tikpan_node_options.py nodes/tikpan_grok_video_15_benefit.py tests/test_node_contracts_offline.py __init__.py
python tests/test_node_contracts_offline.py
```

当前文档维护口径：根目录 `__init__.py` 注册 49 个 ComfyUI 节点，用户文档按"教程 + 速查表 + 功能分类 + 更新日志"四件套同步维护。

新增或调整节点时请同步检查：

1. `docs/节点使用教程.md`：补充实际工作流、关键参数、输出连接和常见失败处理。
2. `docs/节点速查表.md`：补充节点类名、用途、关键输入和输出。
3. `docs/Tikpan_ComfyUI_节点功能分类.md`：确认菜单分类和显示名位置正确。
4. `README.md`：只在新增大类能力或主推模型发生变化时更新简介。
5. `CHANGELOG.md`：记录新增功能、修复、文档同步和验证命令。

## [v1.4.1] - 2026-06-09

### Fixed - 视频节点上游 API 参数与模型名对齐

- **MiniMax Hailuo 视频生成**（`nodes/tikpan_minimax_video.py`）：
  - 移除未在上游文档/中转站广场确认的 `MiniMax-Hailuo-2.3-fast`，默认改为 `MiniMax-Hailuo-2.3`。
  - 兼容旧工作流：保存的 `MiniMax-Hailuo-2.3-fast` 会自动归一化为 `MiniMax-Hailuo-2.3`。
  - 首尾帧模式增加本地校验：仅允许 `MiniMax-Hailuo-02`。
  - 增加 `10秒 + 1080P` 本地校验，避免提交上游不支持的组合。
- **通用视频结果提取**（`nodes/tikpan_happyhorse_common.py`）：支持从 `download_url` / `backup_download_url` 提取视频文件，兼容 MiniMax 查询任务返回结构。
- **Kling 文生/图生视频**（`nodes/tikpan_kling_video.py`）：
  - `kling-v2-5-turbo` 开启 `sound=on` 时提前本地报错，提示切换到 `kling-v2-6` 或 `kling-v3`。
  - 图生视频连接 `尾帧图` 时强制 5 秒，避免提交上游不支持的尾帧 10 秒请求。
  - 更新 `生成声音` tooltip，标注仅支持 Kling v2.6 及以上模型。
- **Kling Motion Control**（`nodes/tikpan_kling_motion_control.py`）：
  - 模型选项从 `kling-v3-0` 改为上游文档示例中的 `kling-v3`。
  - 兼容旧工作流：`kling-v3-0` 自动归一化为 `kling-v3`。
  - 请求字段从 `image` / `video` 改为 `image_url` / `video_url`，对齐上游 Motion Control 文档。

### Documentation

- 更新 README、节点使用教程、节点速查表、节点功能分类和飞书合并文档内容。
- 将项目版本提升到 `1.4.1`。
- 标注当前注册节点口径为 52 个节点、7 类菜单。

### Verification

```bash
python -m py_compile "nodes/tikpan_minimax_video.py" "nodes/tikpan_happyhorse_common.py" "nodes/tikpan_kling_video.py" "nodes/tikpan_kling_motion_control.py" "tests/test_node_contracts_offline.py"
```

- 通过针对本次修改点的离线 stub 检查：`download_url` 提取、Hailuo 模型列表、Kling 声音 tooltip、Kling Motion `kling-v3-0` 归一化。
- 完整离线契约脚本在当前轻量环境缺少 `torch` 时无法直接运行，非本次变更导致。

## [v1.3.8] - 2026-06-08

### Added - GPT-Image-2 福利生图节点 & 独立「福利」菜单目录

- 新增 `TikpanGptImage2BenefitNode`（显示名：`图片｜GPT-Image-2 福利生图`），继承官方 GPT-Image-2 节点，面向福利渠道生图活动。
- 节点 UI 仅暴露 `福利渠道` 下拉（内置 `福利渠道一`），真实中转站地址固定在代码内、不向参数面板暴露。
- 福利节点走 `/v1/chat/completions`，兼容返回 `choices.message.content` 中的 Markdown 图片链接与 `data:image/...;base64` 图片数据，并对上游尺寸降级做居中裁切兜底。
- 新增独立二级目录 `07 福利 Benefit`（`CATEGORY_BENEFIT`，`nodes/tikpan_categories.py`），与 `01 图片`/`02 视频`/`03 音频` 等并列；福利节点归入该目录。
- 离线契约测试 `tests/test_node_contracts_offline.py` 补充福利节点用例，并放宽分类白名单接纳 `07 福利 Benefit`。

### 验证

- `python tests/test_node_contracts_offline.py`：福利节点契约、分类菜单树、注册完整性用例均通过。



### Enhanced - 提示词库解析与中文化

本次重写提示词库解析器并新增中文翻译能力，让英文 prompt 库对中文用户低门槛可用。

- **解析器重构**（`utils/prompts_library.py`）：
  - 章节黑名单大幅扩展（中英双语）：自动跳过 Introduction / News / Quick Start / 我的其他开源项目 / Acknowledge / License 等 50+ 类非提示词章节
  - 内容启发式过滤：丢弃以 `npx`、`pip install`、`git clone`、`Welcome to` 开头的安装指引/介绍文字
  - H2 必须包含代码块或 blockquote 才入库：纯软件 README（如 toki-plus 系列）自动 0 卡片
  - 按 H3 拆细颗粒度：GPT-Image-2、Seedance 等仓库的 100+ 用例每个独立成卡
  - 优先识别 `#### 📝 Prompt` 子节：精准提取 Nano Banana 仓库的真实提示词
  - **效果**：80 张混合卡片 → 503 张真实可用卡片

- **中文翻译缓存**（可选启用）：
  - 「提示词库管理器」新增 `Tikpan_API密钥` 和 `翻译模型` 字段
  - 默认模型 `deepseek-v4-flash`，500 张全译成本 ≈ ¥0.05
  - 翻译标题 + 80 字 prompt 预览，**原文 prompt 永不翻译**（保证生图质量）
  - 自动检测已是中文的内容并跳过翻译，省 token
  - 批量翻译（每批 10 条），约 1-2 分钟翻完 500 张

- **断点续传**：
  - 每批翻译完成立即原子写盘（`.tmp` + `os.replace`），中途崩溃不丢译文
  - 下次同步通过 `prompt_head` 比对自动跳过已译卡片
  - 最坏情况浪费 1 个批次（< 1 分钱）

- **选择器节点优化**（`nodes/tikpan_prompts_selector.py`）：
  - 下拉框上限 200 → 800
  - 下拉标签格式：`{编号}. {中文标题或英文} — {中文预览或英文预览}`
  - 索引精确匹配完整卡片列表，过滤条件改为下拉占位时的回退（修复原索引/过滤错配 bug）
  - 控制台详情同时显示中英对照

- **新增 2 个专用选择器**（按内容类型预过滤，避免下拉框混杂）：
  - `TikpanPromptsImageSelectorNode` 「工具｜提示词选择器·图片」：只显示 336 张图片类卡片（gpt-image-2 + nano-banana）
  - `TikpanPromptsVideoSelectorNode` 「工具｜提示词选择器·视频」：只显示 163 张视频类卡片（seedance）
  - 通过基类 `CARD_TYPE_FILTER` 类属性实现，子类零代码改动
  - 仓库/标签下拉框自动剔除冗余（视频选择器里不再出现 gpt-image-2 仓库；图片选择器里不再列 `image` 标签）
  - 原 `TikpanPromptsSelectorNode` 显示名改为「工具｜提示词选择器·全部」

### Technical Details

- `PromptCard` 新增 `title_zh` 和 `prompt_preview_zh` 字段，向后兼容旧 JSON
- 翻译走 `https://tikpan.com/v1/chat/completions` OpenAI 兼容协议
- `_load_existing_translations()` 在写盘前读取旧译文缓存，防止覆盖丢失
- `translate_cards()` 支持 `checkpoint_callback`，每批落盘
- 401 连通性测试已验证端点和模型名路由正常

### Verification

```
# 本地校验解析器（无需 API key）
python -c "from utils.prompts_library import sync_prompt_repo, PROMPT_REPOS;
[print(sync_prompt_repo(r)) for r in PROMPT_REPOS]"

# 翻译连通性测试（用假 key 期望 401）
python -c "from utils.prompts_library import _batch_translate;
print(_batch_translate(['test'], 'sk-fake', 'deepseek-v4-flash'))"
```

## [v1.3.6] - 2026-05-31

### Enhanced - PSD 智能分层优化

优化智能分层 PSD 生成器的用户体验：

- **图层分组功能**：自动将图层按类型分组（背景层/产品元素/文字层），在 Photoshop 中打开时图层自动组织在文件夹中
- **智能命名功能**：根据元素位置（九宫格：中心/左上/右上等）、大小（主产品/大元素/元素/小装饰）自动生成有意义的图层名称
  - 示例：`主产品_中心`、`大元素_左上`、`元素_右下_1`、`小装饰_顶部_2`
- **增强缩略图预览**：预览图显示每个图层的 60x60 像素缩略图，包含图层名称、类型、分组、可见性等详细信息

### Technical Details

- 在 `tikpan_psd_processor.py` 中新增 `_generate_smart_name()` 方法，实现九宫格位置判断和大小分级
- 在 `_build_layer_list()` 中为每个图层添加 `group` 字段
- 在 `save_as_psd()` 中新增 `_organize_layers_by_group()` 方法，使用 PSD 兼容图层分组流程创建图层组
- 在 `create_preview()` 中实现缩略图渲染，使用深色主题界面

## [v1.3.5] - 2026-05-30

### New Features - PSD 分层导出能力

本次新增 PSD 智能分层工作流：智能 AI 分层 → 模型预下载。

- **`TikpanSmartPSDLayeringNode` 工具｜智能分层 PSD 生成器**：纯本地 AI 自动识别图片元素并保存为分层 PSD，**三档可选**:
  - **经济档（5-15秒）**：BiRefNet + OpenCV 连通域 + PaddleOCR。适合简单商品图、追求速度。
  - **标准档（20-60秒）⭐推荐**：BiRefNet + SAM2 自动多尺度 + PaddleOCR。适合大多数日常场景、复杂商品图和海报。
  - **极致档（60-180秒）**：BiRefNet + GroundingDINO + SAM2 + LaMa。商业级分层（**被遮挡区域智能补全**），让每一层都是完整的。
  - 标准档可勾选"补全被遮挡区域"升级到极致档效果。
  - 输出：原图参考层（默认隐藏）+ 背景层 + N 个独立元素层 + N 个文字层。
  - 处理流程异常时自动降级（SAM2 不可用降级到 rembg，inpainting 失败跳过补全）。

- **`TikpanPSDDependencyDownloaderNode` 工具｜PSD 模型预下载器**：让用户提前一次性下载分层节点的全部依赖和模型。
  - 可选档位：经济档 / 标准档 / 极致档 / 全部档位。
  - 自动安装 pip 包并预拉取对应 AI 模型权重。
  - 提供可视化下载状态预览图。
  - 解决"首次使用智能分层节点时需要等待几分钟下载"的体验问题。

### Architecture

- 智能分层节点的处理逻辑拆分到独立模块 `tikpan_psd_processor.py`，三档共享同一套图层组装与 PSD 写入流程。
- 依赖按需加载策略：重启 ComfyUI 不会下载任何模型；用户只在选择对应档位、实际运行节点时才会触发下载和安装。
- 用户也可主动使用预下载器节点提前下载，避免首次卡顿。

### Documentation

- 节点速查表 (`docs/节点速查表.md`) 新增 PSD 智能分层表与三档精度对比表。
- 节点功能分类 (`docs/Tikpan_ComfyUI_节点功能分类.md`) 在"06 任务与并发 Tools"分类下新增 PSD 智能分层和模型预下载条目。
- 节点使用教程 (`docs/节点使用教程.md`) 新增第 10 章 "PSD 分层导出"，覆盖三档选择决策、首次使用流程、工作流示例与常见失败处理。
- 新增飞书文档同步指南 (`docs/飞书文档同步指南.md`)：完整的飞书 API 配置教程、使用方法、常见问题排查和安全提示。
- README 新增"快速开始：PSD 分层导出"章节，补充 PSD 智能分层功能简介和三档对比说明。

### Testing

- 新增智能分层节点离线测试 (`tests/test_smart_layering_offline.py`)：覆盖节点初始化、输入类型、依赖检查、处理器导入、文件名清理、错误处理、图层结构构建等 8 个测试用例。
- 已有 PSD 保存节点离线测试 (`tests/test_psd_saver_offline.py`)：覆盖标准模式、高级模式、多图层、文件名清理等 6 个测试用例。

## [v1.3.1] - 2026-05-25

### Bug Fixes

- **GPT Image 2 编辑节点 v2（`tikpan_gpt_image_2_official_edit_v2.py`）**：修复 `("4K", "1:1")` 分辨率映射错误——原值为 `2048x2048`（与 2K 1:1 完全一样），导致选择"4K + 1:1"实际只生成 2K 图像。已修正为 `2880x2880`（4K 总像素 ≈ 829 万，1:1 比例下最大可用正方形尺寸，符合 API 像素上限）。4K 16:9 / 9:16 不受影响。

### Canvas Model Studio 工具重构（`experiments/canvas_model_studio/`）

本次对配套的本地无限画布工具进行了较大重构，方向是**纯本地软件模式**：不需要账户，不写注册表，所有文件在软件文件夹内，复制文件夹即可迁移。

**架构改进**

- 去掉全部账户体系（登录/注册/验证码/Token/余额显示），以访客/本地用户替代
- API Key 和 ComfyUI 地址存入 `data/local-config.json`，运行时热更新无需重启
- 画布状态（节点、相机位置）从浏览器 `localStorage` 迁移到 `data/canvas-autosave.json`，换电脑不丢数据
- 项目和资产目录去掉用户分层，直接使用 `data/projects/` 和 `data/assets/`
- 新增 `.gitignore`，保护 `local-config.json`（含 API Key）不被提交到 git

**新增功能**

- 设置弹窗：侧边栏显示 API Key 状态（绿点/红点），首次启动无 Key 时自动弹出
- 数据目录路径展示：设置弹窗内显示 `data/` 绝对路径，方便备份和定位
- Toast 弹窗通知系统：成功/失败/警告分色，右下角滑入，代替纯状态栏小字
- 节点"生成中"状态：生成期间节点显示斜纹 shimmer 动画，直观知道等哪张
- 右键上下文菜单：右键节点弹出复制/删除菜单，Esc 关闭
- Ctrl+Enter 快捷键：全局触发生成
- 图片摆放算法修复：生成结果使用 `findClearRect` 螺旋算法而非简单偏移，多张结果不再重叠

**可靠性改进**

- 结构化请求日志：每条请求打 `requestId`、耗时、状态码，写入 `logs/canvas-YYYY-MM-DD.log`
- 新增 `GET /api/logs?tail=N` 端点，可在浏览器查看近期日志
- `POST /api/generate` 单独打 GEN 日志，记录模型档案、耗时、返回图片数量
- `profile.json` 10 秒内存缓存，减少重复读盘
- `previewRequest` 补充 try/catch，修复无错误处理的 bug
- 一键启动脚本：`start.bat`（Windows）和 `start.sh`（Mac/Linux），自动检测 Node.js、延迟打开浏览器

## [v1.3.0] - 2026-05-23

### New Features

- 新增 Kling Motion Control 动作控制节点 (`TikpanKlingMotionControlNode`)：支持 Kling v2.6 / v3.0 的 std（720P）和 pro（1080P）模式，传入角色图像和动作参考视频（URL 或本地路径），将参考视频的动作精准迁移到角色图像上生成视频。
- 新增 Vidu3 参考生视频节点 (`TikpanVidu3ReferenceVideoNode`)：最多传 7 张参考图，通过 `@1`、`@2` 等占位符在提示词里引用对应主体，保持人物/产品一致性生成视频；支持音画同步、音频类型、错峰生成。
- 新增 Vidu3 Turbo 文生/图生/首尾帧节点 (`TikpanVidu3TurboVideoNode`)：底层模型固定 `viduq3-turbo`，支持纯文字生视频、图生视频（首帧控制）、首尾帧同时控制三种模式；支持运动幅度、音画同步和错峰生成。
- 新增 Gemini Omni Flash 视频生成节点 (`TikpanGeminiOmniVideoNode`)：多模态视频生成，支持文生/图生/多参考/视频编辑/音频驱动五种模式；模型包含 `omni-flash`、`omni-flash-components`、`gemini-omni-flash` 等；端点支持 Tikpan 中转站（`/v1/video/create`、`/v1/videos`）和 Gemini 原生预览。
- 新增 Gemini 3.5 Flash 推理节点 (`TikpanGemini35FlashNode`)：长文档/复杂推理场景，支持 thinking 深度推理（auto/关闭/轻量/中等/深度）、最多 6 张图片 inline、本地文件 inline（PDF/TXT/代码等，建议 < 18MB）、Gemini 原生和 OpenAI 兼容两种调用方式；recovery 目录 `recovery/gemini_3_5_flash`。
- 新增 Qwen-Image-2.0 生图/编辑节点 (`TikpanQwenImage20Node`)：支持文生图、图生图/编辑、多参考图三种模式，最多 4 张参考图；清晰度 `auto/1k/2k`；画质策略 `auto/speed/balanced/quality`。
- 新增 Wan 2.7 Image Pro 生图/编辑节点 (`TikpanWan27ImageProNode`)：支持 4K 清晰度（清晰度选项 `auto/1k/2k/4k`）；支持 thinking 模式（`auto/false/true`）；最多 4 张参考图。

### Bug Fixes

- 修复 `tikpan_gemini_omni_video.py` 中 `ENDPOINT_OPTIONS` 列表存在重复项的问题：原第 0 项和第 2 项均为 `"Tikpan 视频创建｜/v1/video/create"`，导致下拉菜单出现两个完全相同的选项，且 Gemini 原生预览选项的实际下拉索引错位。已删除重复项，从 5 项精简为 4 项。

### Documentation

- 节点速查表 (`docs/节点速查表.md`) 补充上述所有新节点的关键输入/输出行，并新增"工具节点"表，覆盖并发引擎和异步任务组共 5 个工具节点。
- 节点使用教程 (`docs/节点使用教程.md`) 补充第 5.8–5.11 节（Grok Imagine Image 生图/修图、Qwen/Wan 图像）、第 6.9–6.12 节（Kling Motion Control、Vidu3 参考、Vidu3 Turbo、Gemini Omni Flash）、第 8.3 节（Gemini 3.5 Flash 推理），以及新增第 9 章（工具节点：并发引擎 + 异步任务组）；章节编号随之顺延。
- 修正使用教程中 `GPT-5 Mini` → `GPT-5.4 Mini` 名称不一致问题，并在"应该用哪个节点"决策表中补充新节点入口。

### Validation

- 检查所有 40 个注册节点在根 `__init__.py` 的 `NODE_CLASS_MAPPINGS` 和 `NODE_DISPLAY_NAME_MAPPINGS` 中均有正确条目。
- 确认 `ENDPOINT_OPTIONS` 修复后无重复项，下拉索引逻辑正常。

## [v1.2.0] - 2026-05-19

### New Features

- 新增 Grok Imagine Image / Grok Imagine Image Pro 生图节点，并补齐 Tikpan 福利入口、中文字段、生成张数、画面比例、清晰度与返回格式参数。
- 新增 Grok Imagine Image / Pro 参考图修图节点，单独走 `/v1/images/edits`，支持最多 3 张参考图，避免把参考图误塞进纯文生图接口。
- 新增 Tikpan Async Engine 与 Parallel Image Engine 节点，支持提交任务、查询结果、合并任务、最近任务和 API 多模型并发/容灾场景。

### Improvements

- GPT Image 2 相关节点与网站 catalog 对齐最多 16 张参考图，不再用”参考流”隐藏真实能力。
- Grok Imagine 节点增强返回解析、去重、RGB 标准化、payload 预览、失败上下文日志和 `Skip_Error` 黑图兜底说明。
- ComfyUI 节点统一收口到 Tikpan 官方中转站 `https://tikpan.com`；旧工作流里残留的其他中转站地址会自动回退到 Tikpan。
- 更新并发引擎说明文档，删除旧供应商示例，明确当前版本只使用 Tikpan 官方接口。

### Validation

- 使用 Aki 自带 Python 编译检查 Grok Imagine、异步/并发引擎、GPT Image 2、Doubao、Suno、Gemini 等主要节点文件。
- 验证 `API_HOST_OPTIONS` 只包含 `https://tikpan.com`，并确认旧上游地址会被 `normalize_api_host()` 回退到 Tikpan。

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
