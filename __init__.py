# __init__.py - Tikpan Pro 终极节点管理器

# 1. 导入所有逻辑文件
from .nodes.tikpan_happyhorse_i2v import TikpanHappyHorseI2VNode
from .nodes.tikpan_happyhorse_t2v import TikpanHappyHorseT2VNode
from .nodes.tikpan_happyhorse_r2v import TikpanHappyHorseR2VNode
from .nodes.tikpan_happyhorse_video_edit import TikpanHappyHorseVideoEditNode
from .nodes.tikpan_grok_video import TikpanExclusiveVideoNode
from .nodes.tikpan_gemini_image import TikpanGeminiImageMaxNode
from .nodes.tikpan_gemini_video_analyst import TikpanGeminiVideoAnalystNode
from .nodes.tikpan_gemini_tts import TikpanGemini31FlashTTSNode
from .nodes.tikpan_grok_optimizer import TikpanGrokPromptOptimizerNode
from .nodes.tikpan_veo_video import TikpanVeoVideoNode
from .nodes.tikpan_vidu_q3_video import TikpanViduQ3Node, TikpanViduQ3MixNode, TikpanViduQ3TurboNode
from .nodes.tikpan_gpt_image_node import TikpanGptImage2Node
from .nodes.tikpan_gpt_image_2_gen import TikpanGptImage2GenNode
from .nodes.tikpan_gpt_image_2_edit import TikpanGptImage2EditNode
from .nodes.tikpan_gpt_image_2_official import TikpanGptImage2OfficialNode
from .nodes.tikpan_gpt_image_2_official_edit_v2 import TikpanGptImage2OfficialEditV2
from .nodes.tikpan_grok_videos import TikpanGrokVideoNode
from .nodes.tikpan_suno_music import TikpanSunoMusicNode
from .nodes.tikpan_minimax_speech import TikpanMiniMaxSpeech28HDNode, TikpanMiniMaxSpeech28TurboNode
from .nodes.tikpan_doubao_image import TikpanDoubaoImageNode
from .nodes.tikpan_nano_banana_pro import TikpanNanoBananaProNode
from .nodes.tikpan_task_fetcher import TikpanTaskFetcherNode

# 2. 建立内部类名映射
NODE_CLASS_MAPPINGS = {
    "TikpanHappyHorseI2VNode": TikpanHappyHorseI2VNode,
    "TikpanHappyHorseT2VNode": TikpanHappyHorseT2VNode,
    "TikpanHappyHorseR2VNode": TikpanHappyHorseR2VNode,
    "TikpanHappyHorseVideoEditNode": TikpanHappyHorseVideoEditNode,
    "TikpanExclusiveVideoNode": TikpanExclusiveVideoNode,
    "TikpanGeminiImageMaxNode": TikpanGeminiImageMaxNode,
    "TikpanGeminiVideoAnalystNode": TikpanGeminiVideoAnalystNode,
    "TikpanGemini31FlashTTSNode": TikpanGemini31FlashTTSNode,
    "TikpanGrokPromptOptimizerNode": TikpanGrokPromptOptimizerNode,
    "TikpanGptImage2Node": TikpanGptImage2Node,
    "TikpanVeoVideoNode": TikpanVeoVideoNode,
    "TikpanViduQ3Node": TikpanViduQ3Node,
    "TikpanViduQ3MixNode": TikpanViduQ3MixNode,
    "TikpanViduQ3TurboNode": TikpanViduQ3TurboNode,
    "TikpanGptImage2GenNode": TikpanGptImage2GenNode,
    "TikpanGptImage2EditNode": TikpanGptImage2EditNode,
    "TikpanGptImage2OfficialNode": TikpanGptImage2OfficialNode,
    "TikpanGptImage2OfficialEditV2": TikpanGptImage2OfficialEditV2,
    "TikpanGrokVideoNode": TikpanGrokVideoNode,
    "TikpanSunoMusicNode": TikpanSunoMusicNode,
    "TikpanMiniMaxSpeech28HDNode": TikpanMiniMaxSpeech28HDNode,
    "TikpanMiniMaxSpeech28TurboNode": TikpanMiniMaxSpeech28TurboNode,
    "TikpanDoubaoImageNode": TikpanDoubaoImageNode,
    "TikpanNanoBananaProNode": TikpanNanoBananaProNode,
    "TikpanTaskFetcherNode": TikpanTaskFetcherNode,
}

# 3. 设置 ComfyUI 界面显示的华丽名称
NODE_DISPLAY_NAME_MAPPINGS = {
    "TikpanHappyHorseI2VNode": "🐴 Tikpan：HappyHorse 1.0 I2V 图生视频",
    "TikpanHappyHorseT2VNode": "🐴 Tikpan：HappyHorse 1.0 T2V 文生视频",
    "TikpanHappyHorseR2VNode": "🐴 Tikpan：HappyHorse 1.0 R2V 参考生视频",
    "TikpanHappyHorseVideoEditNode": "🐴 Tikpan：HappyHorse 1.0 Video-Edit 视频编辑",
    "TikpanExclusiveVideoNode": "🎬 Tikpan：Grok3 直出视频生成",
    "TikpanGeminiImageMaxNode": "👑 Tikpan：Gemini 14图极限生图",
    "TikpanGeminiVideoAnalystNode": "👁️ Tikpan：AI音视频双轨智能解构",
    "TikpanGemini31FlashTTSNode": "🎙️ Tikpan: Gemini 3.1 Flash TTS Preview",
    "TikpanGrokPromptOptimizerNode": "🧠 Tikpan：Grok多图剧本重构专家",
    "TikpanGptImage2Node": "👑 Tikpan：gpt-image-2-all图片生成",
    "TikpanVeoVideoNode": "🚀 Tikpan: Veo 3.1 多模型视频生成",
    "TikpanViduQ3Node": "🎬 Tikpan: viduq3 参考生视频",
    "TikpanViduQ3MixNode": "🎬 Tikpan: viduq3-mix 参考生视频",
    "TikpanViduQ3TurboNode": "🎬 Tikpan: viduq3-turbo 多模式视频",
    "TikpanGptImage2GenNode": "🎨 Tikpan: GPT-Image-2-all 视觉建筑师(生成)",
    "TikpanGptImage2EditNode": "💉 Tikpan: GPT-Image-2-all 视觉整形师(修改)",
    "TikpanGptImage2OfficialNode": "💎 Tikpan: GPT-Image-2 官方正式版(生图)",
    "TikpanGptImage2OfficialEditV2": "💎 Tikpan: GPT-Image-2 官方正式版(修图) V2",
    "TikpanGrokVideoNode": "🎬 Tikpan: Grok-Videos 视频生成",
    "TikpanSunoMusicNode": "🎵 Tikpan: Suno 音乐生成",
    "TikpanMiniMaxSpeech28HDNode": "🎙️ Tikpan: speech-2.8-hd 高清语音合成",
    "TikpanMiniMaxSpeech28TurboNode": "🎙️ Tikpan: speech-2.8-turbo 极速语音合成",
    "TikpanDoubaoImageNode": "🎨 Tikpan: 豆包图像生成",
    "TikpanNanoBananaProNode": "🍌 Tikpan: Nano Banana Pro",
    "TikpanTaskFetcherNode": "🔍 Tikpan：异步任务查询与下载",
}

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']
