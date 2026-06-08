# Tikpan ComfyUI 节点功能分类

> 更新日期：2026-06-08  
> 当前口径：根目录 `__init__.py` 已注册 47 个节点，菜单分为 6 类。

本插件的 ComfyUI 菜单按功能整理在 `👑 Tikpan 官方独家节点` 下，方便用户按任务选择节点，而不是记模型名。

## 01 图片 Image

用于生图、修图、多参考图生成、商品图、角色图、海报图等。

- `图片｜GPT-Image-2 官方生图`
- `图片｜GPT-Image-2 福利生图`
- `图片｜GPT-Image-2 官方修图 V2`
- `图片｜GPT-Image-2-all 生图`
- `图片｜GPT-Image-2-all 修图`
- `图片｜GPT-Image-2-all 简易生图`
- `图片｜Gemini 14图极限生图`
- `图片｜Nano Banana Pro`
- `图片｜Wan 2.7 Image Pro 生图/编辑`
- `图片｜Qwen-Image-2.0 生图/编辑`
- `图片｜豆包图像生成 Seedream`
- `图片｜Grok Imagine Image 生图`
- `图片｜Grok Imagine Image Pro 生图`
- `图片｜Grok Imagine Image 参考图/修图`
- `图片｜Grok Imagine Image Pro 参考图/修图`

## 02 视频 Video

用于文生视频、图生视频、参考图生视频、视频编辑、视频延长和多模型视频生成。

- `视频｜HappyHorse 1.0 文生视频 T2V`
- `视频｜HappyHorse 1.0 图生视频 I2V`
- `视频｜HappyHorse 1.0 参考生视频 R2V`
- `视频｜HappyHorse 1.0 视频编辑`
- `视频｜Grok3 直出视频生成`
- `视频｜Grok-Videos 视频生成`
- `视频｜Kling Motion Control 动作控制`
- `视频｜Vidu3 参考生视频`
- `视频｜Vidu3 Turbo 文生/图生/首尾帧`
- `视频｜Veo 3.1 多模型视频生成`
- `视频｜Gemini Omni 视频生成`

## 03 音频 Audio

用于音乐生成、语音合成、旁白、配音和口播音频。

- `音频｜Suno 音乐生成`
- `音频｜Gemini 3.1 Flash TTS`
- `音频｜豆包语音合成 2.0`
- `音频｜speech-2.8-hd 高清语音合成`
- `音频｜speech-2.8-turbo 极速语音合成`

## 04 文字与多模态 Text & Multimodal

用于文本推理、图片理解、视频理解、文件分析和结构化输出。

- `多模态｜GPT-5.4 Mini 推理`
- `多模态｜Gemini 3 Flash 图片/视频分析`
- `多模态｜Gemini 3.5 Flash 推理`

## 05 提示词与分析 Prompt & Analysis

用于从素材中反推提示词、分析视频结构、重构脚本和优化生成描述。

- `分析｜AI 音视频双轨解析`
- `提示词｜Grok 多图剧本重构`

## 06 任务与并发 Tools

用于异步任务提交、查询、合并、最近任务查看，以及多模型并发/容灾，以及 PSD 分层导出。

- `工具｜异步任务查询与下载`
- `工具｜API 多模型并发生图引擎`
- `工具｜异步提交图片任务`
- `工具｜异步查询图片结果`
- `工具｜合并异步图片任务`
- `工具｜最近异步任务列表`
- `工具｜PSD 文件保存器`
- `工具｜智能分层 PSD 生成器`
- `工具｜PSD 模型预下载器`

## 后续新增模型放置规则

- 生图、修图、图像识别、图片参考生成：放入 `01 图片 Image`。
- 文生视频、图生视频、视频编辑、视频延长、数字人视频：放入 `02 视频 Video`。
- 音乐、TTS、音效、声音克隆：放入 `03 音频 Audio`。
- LLM、图片/视频/文件理解、结构化分析：放入 `04 文字与多模态 Text & Multimodal`。
- 提示词优化、脚本重构、素材拆解：放入 `05 提示词与分析 Prompt & Analysis`。
- 查询任务、下载结果、批量提交、并发引擎：放入 `06 任务与并发 Tools`。
