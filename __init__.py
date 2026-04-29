# __init__.py - Tikpan Pro 终极节点管理器

# 1. 导入所有逻辑文件
from .nodes.tikpan_grok_video import TikpanExclusiveVideoNode
from .nodes.tikpan_gemini_image import TikpanGeminiImageMaxNode
from .nodes.tikpan_gemini_video_analyst import TikpanGeminiVideoAnalystNode
from .nodes.tikpan_grok_optimizer import TikpanGrokPromptOptimizerNode
from .nodes.tikpan_veo_video import TikpanVeoVideoNode
from .nodes.tikpan_gpt_image_node import TikpanGptImage2Node
from .nodes.tikpan_gpt_image_2_gen import TikpanGptImage2GenNode
from .nodes.tikpan_gpt_image_2_edit import TikpanGptImage2EditNode
from .nodes.tikpan_gpt_image_2_official import TikpanGptImage2OfficialNode
from .nodes.tikpan_gpt_image_2_official_edit_v2 import TikpanGptImage2OfficialEditV2

# 2. 建立内部类名映射
NODE_CLASS_MAPPINGS = {
    "TikpanExclusiveVideoNode": TikpanExclusiveVideoNode,
    "TikpanGeminiImageMaxNode": TikpanGeminiImageMaxNode,
    "TikpanGeminiVideoAnalystNode": TikpanGeminiVideoAnalystNode,
    "TikpanGrokPromptOptimizerNode": TikpanGrokPromptOptimizerNode,
    "TikpanGptImage2Node": TikpanGptImage2Node,
    "TikpanVeoVideoNode": TikpanVeoVideoNode,
    "TikpanGptImage2GenNode": TikpanGptImage2GenNode,
    "TikpanGptImage2EditNode": TikpanGptImage2EditNode,
    "TikpanGptImage2OfficialNode": TikpanGptImage2OfficialNode,
    "TikpanGptImage2OfficialEditV2": TikpanGptImage2OfficialEditV2,
}

# 3. 设置 ComfyUI 界面显示的华丽名称
NODE_DISPLAY_NAME_MAPPINGS = {
    "TikpanExclusiveVideoNode": "🎬 Tikpan：Grok3 直出视频生成",
    "TikpanGeminiImageMaxNode": "👑 Tikpan：Gemini 14图极限生图",
    "TikpanGeminiVideoAnalystNode": "👁️ Tikpan：AI音视频双轨智能解构",
    "TikpanGrokPromptOptimizerNode": "🧠 Tikpan：Grok多图剧本重构专家",
    "TikpanGptImage2Node": "👑 Tikpan：gpt-image-2-all图片生成",
    "TikpanVeoVideoNode": "🚀 Tikpan: Veo 3.1 备用视频生成",
    "TikpanGptImage2GenNode": "🎨 Tikpan: GPT-Image-2-all 视觉建筑师(生成)",
    "TikpanGptImage2EditNode": "💉 Tikpan: GPT-Image-2-all 视觉整形师(修改)",
    "TikpanGptImage2OfficialNode": "💎 Tikpan: GPT-Image-2 官方正式版(生图)",
    "TikpanGptImage2OfficialEditV2": "💎 Tikpan: GPT-Image-2 官方正式版(修图) V2"
}

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']