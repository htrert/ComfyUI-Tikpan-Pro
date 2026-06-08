# __init__.py - Tikpan Pro 终极节点管理器

# 1. 导入所有逻辑文件
from .nodes.tikpan_happyhorse_i2v import TikpanHappyHorseI2VNode
from .nodes.tikpan_happyhorse_t2v import TikpanHappyHorseT2VNode
from .nodes.tikpan_happyhorse_r2v import TikpanHappyHorseR2VNode
from .nodes.tikpan_happyhorse_video_edit import TikpanHappyHorseVideoEditNode
from .nodes.tikpan_grok_video import TikpanExclusiveVideoNode
from .nodes.tikpan_grok_imagine_image import (
    TikpanGrokImagineImageNode,
    TikpanGrokImagineImageProNode,
    TikpanGrokImagineImageEditNode,
    TikpanGrokImagineImageProEditNode,
)
from .nodes.tikpan_parallel_image_engine import TikpanParallelImageEngineNode
from .nodes.tikpan_async_nodes import (
    TikpanAsyncImageSubmitNode,
    TikpanAsyncImageResultNode,
    TikpanAsyncImageJoinNode,
    TikpanAsyncTaskListNode,
)
from .nodes.tikpan_gemini_image import TikpanGeminiImageMaxNode
from .nodes.tikpan_gemini_video_analyst import TikpanGeminiVideoAnalystNode
from .nodes.tikpan_gemini_tts import TikpanGemini31FlashTTSNode
from .nodes.tikpan_gemini3_flash_preview_analyst import TikpanGemini3FlashPreviewAnalystNode
from .nodes.tikpan_gemini35_flash import TikpanGemini35FlashNode
from .nodes.tikpan_gpt5_mini_responses import TikpanGPT5MiniResponsesNode
from .nodes.tikpan_grok_optimizer import TikpanGrokPromptOptimizerNode
from .nodes.tikpan_veo_video import TikpanVeoVideoNode
from .nodes.tikpan_gemini_omni_video import TikpanGeminiOmniVideoNode
from .nodes.tikpan_gpt_image_node import TikpanGptImage2Node
from .nodes.tikpan_gpt_image_2_gen import TikpanGptImage2GenNode
from .nodes.tikpan_gpt_image_2_edit import TikpanGptImage2EditNode
from .nodes.tikpan_gpt_image_2_official import TikpanGptImage2OfficialNode
from .nodes.tikpan_gpt_image_2_benefit import TikpanGptImage2BenefitNode
from .nodes.tikpan_gpt_image_2_official_edit_v2 import TikpanGptImage2OfficialEditV2
from .nodes.tikpan_grok_videos import TikpanGrokVideoNode
from .nodes.tikpan_kling_motion_control import TikpanKlingMotionControlNode
from .nodes.tikpan_vidu_video import TikpanVidu3ReferenceVideoNode, TikpanVidu3TurboVideoNode
from .nodes.tikpan_suno_music import TikpanSunoMusicNode
from .nodes.tikpan_minimax_speech import TikpanMiniMaxSpeech28HDNode, TikpanMiniMaxSpeech28TurboNode
from .nodes.tikpan_doubao_image import TikpanDoubaoImageNode
from .nodes.tikpan_doubao_tts import TikpanDoubaoTTS20Node
from .nodes.tikpan_nano_banana_pro import TikpanNanoBananaProNode
from .nodes.tikpan_qwen_wan_image import TikpanQwenImage20Node, TikpanWan27ImageProNode
from .nodes.tikpan_task_fetcher import TikpanTaskFetcherNode

# 2. 建立内部类名映射
NODE_CLASS_MAPPINGS = {
    "TikpanHappyHorseI2VNode": TikpanHappyHorseI2VNode,
    "TikpanHappyHorseT2VNode": TikpanHappyHorseT2VNode,
    "TikpanHappyHorseR2VNode": TikpanHappyHorseR2VNode,
    "TikpanHappyHorseVideoEditNode": TikpanHappyHorseVideoEditNode,
    "TikpanExclusiveVideoNode": TikpanExclusiveVideoNode,
    "TikpanGrokImagineImageNode": TikpanGrokImagineImageNode,
    "TikpanGrokImagineImageProNode": TikpanGrokImagineImageProNode,
    "TikpanGrokImagineImageEditNode": TikpanGrokImagineImageEditNode,
    "TikpanGrokImagineImageProEditNode": TikpanGrokImagineImageProEditNode,
    "TikpanParallelImageEngineNode": TikpanParallelImageEngineNode,
    "TikpanAsyncImageSubmitNode": TikpanAsyncImageSubmitNode,
    "TikpanAsyncImageResultNode": TikpanAsyncImageResultNode,
    "TikpanAsyncImageJoinNode": TikpanAsyncImageJoinNode,
    "TikpanAsyncTaskListNode": TikpanAsyncTaskListNode,
    "TikpanGeminiImageMaxNode": TikpanGeminiImageMaxNode,
    "TikpanGeminiVideoAnalystNode": TikpanGeminiVideoAnalystNode,
    "TikpanGemini31FlashTTSNode": TikpanGemini31FlashTTSNode,
    "TikpanGemini3FlashPreviewAnalystNode": TikpanGemini3FlashPreviewAnalystNode,
    "TikpanGemini35FlashNode": TikpanGemini35FlashNode,
    "TikpanGPT5MiniResponsesNode": TikpanGPT5MiniResponsesNode,
    "TikpanGrokPromptOptimizerNode": TikpanGrokPromptOptimizerNode,
    "TikpanGptImage2Node": TikpanGptImage2Node,
    "TikpanVeoVideoNode": TikpanVeoVideoNode,
    "TikpanGeminiOmniVideoNode": TikpanGeminiOmniVideoNode,
    "TikpanGptImage2GenNode": TikpanGptImage2GenNode,
    "TikpanGptImage2EditNode": TikpanGptImage2EditNode,
    "TikpanGptImage2OfficialNode": TikpanGptImage2OfficialNode,
    "TikpanGptImage2BenefitNode": TikpanGptImage2BenefitNode,
    "TikpanGptImage2OfficialEditV2": TikpanGptImage2OfficialEditV2,
    "TikpanGrokVideoNode": TikpanGrokVideoNode,
    "TikpanKlingMotionControlNode": TikpanKlingMotionControlNode,
    "TikpanVidu3ReferenceVideoNode": TikpanVidu3ReferenceVideoNode,
    "TikpanVidu3TurboVideoNode": TikpanVidu3TurboVideoNode,
    "TikpanSunoMusicNode": TikpanSunoMusicNode,
    "TikpanMiniMaxSpeech28HDNode": TikpanMiniMaxSpeech28HDNode,
    "TikpanMiniMaxSpeech28TurboNode": TikpanMiniMaxSpeech28TurboNode,
    "TikpanDoubaoImageNode": TikpanDoubaoImageNode,
    "TikpanDoubaoTTS20Node": TikpanDoubaoTTS20Node,
    "TikpanNanoBananaProNode": TikpanNanoBananaProNode,
    "TikpanQwenImage20Node": TikpanQwenImage20Node,
    "TikpanWan27ImageProNode": TikpanWan27ImageProNode,
    "TikpanTaskFetcherNode": TikpanTaskFetcherNode,
}

# 3. 设置 ComfyUI 界面显示的华丽名称
NODE_DISPLAY_NAME_MAPPINGS = {
    "TikpanHappyHorseI2VNode": "视频｜HappyHorse 1.0 图生视频 I2V",
    "TikpanHappyHorseT2VNode": "视频｜HappyHorse 1.0 文生视频 T2V",
    "TikpanHappyHorseR2VNode": "视频｜HappyHorse 1.0 参考生视频 R2V",
    "TikpanHappyHorseVideoEditNode": "视频｜HappyHorse 1.0 视频编辑",
    "TikpanExclusiveVideoNode": "视频｜Grok3 直出视频生成",
    "TikpanGrokImagineImageNode": "图片｜Grok Imagine Image 生图",
    "TikpanGrokImagineImageProNode": "图片｜Grok Imagine Image Pro 生图",
    "TikpanGrokImagineImageEditNode": "图片｜Grok Imagine Image 参考图/修图",
    "TikpanGrokImagineImageProEditNode": "图片｜Grok Imagine Image Pro 参考图/修图",
    "TikpanParallelImageEngineNode": "工具｜API 多模型并发生图引擎",
    "TikpanAsyncImageSubmitNode": "工具｜异步提交图片任务",
    "TikpanAsyncImageResultNode": "工具｜异步查询图片结果",
    "TikpanAsyncImageJoinNode": "工具｜合并异步图片任务",
    "TikpanAsyncTaskListNode": "工具｜最近异步任务列表",
    "TikpanGeminiImageMaxNode": "图片｜Gemini 14图极限生图",
    "TikpanGeminiVideoAnalystNode": "分析｜AI 音视频双轨解析",
    "TikpanGemini31FlashTTSNode": "音频｜Gemini 3.1 Flash TTS",
    "TikpanGemini3FlashPreviewAnalystNode": "多模态｜Gemini 3 Flash 图片/视频分析",
    "TikpanGemini35FlashNode": "多模态｜Gemini 3.5 Flash 推理",
    "TikpanGPT5MiniResponsesNode": "多模态｜GPT-5.4 Mini 推理",
    "TikpanGeminiOmniVideoNode": "视频｜Gemini Omni Flash 视频生成",
    "TikpanGrokPromptOptimizerNode": "提示词｜Grok 多图剧本重构",
    "TikpanGptImage2Node": "图片｜GPT-Image-2-all 简易生图",
    "TikpanVeoVideoNode": "视频｜Veo 3.1 多模型视频生成",
    "TikpanGptImage2GenNode": "图片｜GPT-Image-2-all 生图",
    "TikpanGptImage2EditNode": "图片｜GPT-Image-2-all 修图",
    "TikpanGptImage2OfficialNode": "图片｜GPT-Image-2 官方生图",
    "TikpanGptImage2BenefitNode": "图片｜GPT-Image-2 福利生图",
    "TikpanGptImage2OfficialEditV2": "图片｜GPT-Image-2 官方修图 V2",
    "TikpanGrokVideoNode": "视频｜Grok-Videos 视频生成",
    "TikpanKlingMotionControlNode": "视频｜Kling Motion Control 动作控制",
    "TikpanVidu3ReferenceVideoNode": "视频｜Vidu3 参考生视频",
    "TikpanVidu3TurboVideoNode": "视频｜Vidu3 Turbo 文生/图生/首尾帧",
    "TikpanSunoMusicNode": "音频｜Suno 音乐生成",
    "TikpanMiniMaxSpeech28HDNode": "音频｜speech-2.8-hd 高清语音合成",
    "TikpanMiniMaxSpeech28TurboNode": "音频｜speech-2.8-turbo 极速语音合成",
    "TikpanDoubaoImageNode": "图片｜豆包图像生成 Seedream",
    "TikpanDoubaoTTS20Node": "音频｜豆包语音合成 2.0",
    "TikpanNanoBananaProNode": "图片｜Nano Banana Pro",
    "TikpanWan27ImageProNode": "图片｜Wan 2.7 Image Pro 生图/编辑",
    "TikpanQwenImage20Node": "图片｜Qwen-Image-2.0 生图/编辑",
    "TikpanTaskFetcherNode": "工具｜异步任务查询与下载",
}

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']
