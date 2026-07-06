import {
  BadgeCheck,
  FileText,
  Image,
  LayoutTemplate,
  Sparkles,
} from "lucide-react";
import type { CapabilityCategory, CreativeModel, LedgerItem, LibraryAsset, ModelCategory, OrderRecord, Template, UserProfile } from "./types";

export const currentUser: UserProfile = {
  initials: "U",
  name: "管理员 U",
  email: "admin@tikpan.ai",
  role: "admin",
  tokens: 8.8,
  frozenTokens: 0,
  plan: "Growth 创作包",
  monthlyAllowance: 30,
};

export const modelCategories: ModelCategory[] = [
  { id: "cat-all", key: "all", name: "全部", icon: "sparkles", sortOrder: 0, visible: true, aliases: [] },
  { id: "cat-image", key: "image", name: "图片", icon: "image", sortOrder: 10, visible: true, aliases: ["图像", "AI 图片"] },
  { id: "cat-video", key: "video", name: "视频", icon: "clapperboard", sortOrder: 20, visible: true, aliases: ["AI 视频"] },
  { id: "cat-chat", key: "chat", name: "文案", icon: "file-text", sortOrder: 30, visible: true, aliases: ["对话", "文本"] },
  { id: "cat-audio", key: "audio", name: "音频", icon: "audio-lines", sortOrder: 40, visible: true, aliases: ["配音"] },
  { id: "cat-workflow", key: "workflow", name: "工作流", icon: "layers-3", sortOrder: 50, visible: true, aliases: ["自动化"] },
];

export const capabilityTabs: Array<{ key: CapabilityCategory; label: string }> = modelCategories
  .filter((category) => category.visible)
  .sort((a, b) => a.sortOrder - b.sortOrder)
  .map((category) => ({ key: category.key, label: category.name }));

const legacyCapabilityTabsUnused: Array<{ key: CapabilityCategory; label: string }> = [
  { key: "all", label: "全部" },
  { key: "image", label: "图片" },
  { key: "video", label: "视频" },
];

export const creativeModels: CreativeModel[] = [
  {
    id: "gpt-image-2-4k",
    slug: "gpt-image-2-4k",
    name: "GPT Image 2 4K",
    category: "image",
    categoryKeys: ["image"],
    aliases: ["图像生成 Pro", "商品主图生成", "广告海报生成", "gptimage2"],
    group: "图片模型",
    description: "适合高分辨率商品图、广告海报和社媒封面，可在后台自定义前台展示名称、简介和参数。",
    bestFor: ["商品主图", "广告海报", "社媒封面"],
    tags: ["4K", "文生图"],
    cost: 0.08,
    health: 100,
    platformModelId: "tikpan.image.gpt-image-2-4k",
    upstreamModelName: "cy-img2-gpt-image-2-4k",
    endpointPath: "/v1/images/generations",
    parameters: [
      {
        key: "prompt",
        label: "画面描述",
        type: "textarea",
        required: true,
        helper: "必填，图像描述提示词。",
      },
      {
        key: "size",
        label: "尺寸",
        type: "select",
        defaultValue: "auto",
        helper: "支持常用图片尺寸；4K 建议按模型能力选择。",
        options: [
          { label: "auto", value: "auto" },
          { label: "1024x1024", value: "1024x1024" },
          { label: "1536x1024", value: "1536x1024" },
          { label: "1024x1536", value: "1024x1536" },
          { label: "2048x2048", value: "2048x2048" },
          { label: "3840x2160", value: "3840x2160" },
        ],
      },
      {
        key: "quality",
        label: "画质",
        type: "segmented",
        defaultValue: "auto",
        options: [
          { label: "auto", value: "auto" },
          { label: "low", value: "low" },
          { label: "medium", value: "medium" },
          { label: "high", value: "high" },
        ],
      },
      {
        key: "n",
        label: "生成张数",
        type: "number",
        defaultValue: 1,
        min: 1,
        max: 10,
        step: 1,
      },
      {
        key: "background",
        label: "背景",
        type: "segmented",
        defaultValue: "opaque",
        helper: "文档提示 gpt-image-2 不支持 transparent。",
        options: [
          { label: "auto", value: "auto" },
          { label: "opaque", value: "opaque" },
        ],
      },
      {
        key: "output_format",
        label: "输出格式",
        type: "segmented",
        defaultValue: "png",
        options: [
          { label: "png", value: "png" },
          { label: "jpeg", value: "jpeg" },
          { label: "webp", value: "webp" },
        ],
      },
      {
        key: "output_compression",
        label: "压缩质量",
        type: "slider",
        defaultValue: 100,
        min: 0,
        max: 100,
        step: 1,
        advanced: true,
        helper: "仅 JPEG/WebP 压缩有效。",
      },
      {
        key: "moderation",
        label: "内容审核",
        type: "segmented",
        defaultValue: "auto",
        advanced: true,
        options: [
          { label: "auto", value: "auto" },
          { label: "low", value: "low" },
        ],
      },
      {
        key: "stream",
        label: "流式返回",
        type: "switch",
        defaultValue: false,
        advanced: true,
        helper: "4K 异步建议关闭。",
      },
      {
        key: "partial_images",
        label: "部分预览图",
        type: "number",
        defaultValue: 0,
        min: 0,
        max: 3,
        step: 1,
        advanced: true,
      },
      {
        key: "async",
        label: "异步模式",
        type: "switch",
        defaultValue: true,
        advanced: true,
        helper: "文生图异步生成建议开启。",
      },
    ],
    icon: Image,
  },
  {
    id: "claude-fable-5",
    slug: "claude-fable-5",
    name: "Claude Fable 5",
    category: "chat",
    categoryKeys: ["chat"],
    aliases: ["fable", "claude", "copywriting", "creative writing"],
    group: "Text Models",
    description: "A chat and copywriting model for long-form drafting, rewrites, ideation, and structured text generation.",
    bestFor: ["copywriting", "story drafting", "knowledge Q&A", "script polishing"],
    tags: ["chat", "writing"],
    cost: 0.03,
    health: 98,
    platformModelId: "tikpan.chat.claude-fable-5",
    upstreamModelName: "claude-fable-5",
    endpointPath: "/v1/chat/completions",
    parameters: [
      {
        key: "prompt",
        label: "Prompt",
        type: "textarea",
        required: true,
        helper: "Describe the writing, analysis, or transformation you need.",
      },
      {
        key: "system_prompt",
        label: "System prompt",
        type: "text",
        defaultValue: "You are a helpful creative writing assistant.",
        advanced: true,
      },
      {
        key: "temperature",
        label: "Temperature",
        type: "slider",
        defaultValue: 0.7,
        min: 0,
        max: 2,
        step: 0.1,
      },
      {
        key: "max_tokens",
        label: "Max tokens",
        type: "slider",
        defaultValue: 1200,
        min: 64,
        max: 8192,
        step: 64,
        advanced: true,
      },
    ],
    icon: FileText,
  },
];

export const featuredTemplates: Template[] = [
  {
    id: "new-product-set",
    title: "新品主图四件套",
    category: "今日精选",
    description: "主图、场景图、卖点图和封面一次带入工作台。",
    prompt: "为一款轻盈保湿精华生成新品主图四件套：白底主图、自然光场景图、核心卖点图、小红书封面。整体干净明亮，突出质地和高级感。",
    tokens: 0.72,
    accent: "teal",
  },
  {
    id: "product-poster",
    title: "新品广告海报",
    category: "热门模板",
    description: "适合活动预热、投放素材和品牌视觉方向。",
    prompt: "为一款轻盈保湿精华生成新品广告海报，画面干净明亮，产品居中，突出水润质感和高级品牌氛围。",
    tokens: 0.18,
    accent: "violet",
  },
  {
    id: "five-second-hook",
    title: "短视频开场 5 秒",
    category: "热门能力",
    description: "为产品短视频生成前三秒钩子和镜头节奏。",
    prompt: "为一款电商新品设计短视频开场 5 秒：包含镜头、画面、字幕、口播和节奏说明，目标是在前 3 秒抓住注意力。",
    tokens: 0.24,
    accent: "amber",
  },
  {
    id: "video-product-shot",
    title: "产品短视频画面",
    category: "视频模型预留",
    description: "后续接入视频模型后，可直接带入生成。",
    prompt: "为一款电商新品设计产品短视频画面：自然光、缓慢推进、突出瓶身质感和使用场景。",
    tokens: 1.5,
    accent: "sky",
  },
];

export const libraryAssets: LibraryAsset[] = [
  { id: "asset-1", title: "保湿精华主图方向 A", type: "图片", createdAt: "今天 14:20", model: "图像生成 Pro", favorite: true },
  { id: "asset-2", title: "夏季上新短视频画面", type: "视频", createdAt: "昨天 19:08", model: "视频模型预留" },
  { id: "asset-3", title: "广告海报视觉方向", type: "图片", createdAt: "周三 10:35", model: "GPT Image 2 4K" },
  { id: "asset-4", title: "社媒封面视觉方向", type: "图片", createdAt: "周一 16:12", model: "GPT Image 2 4K" },
];

export const ledgerItems: LedgerItem[] = [
  { id: "ledger-1", title: "商品图生成", time: "今天 14:20", tokens: -0.22, status: "已完成" },
  { id: "ledger-2", title: "短视频分镜", time: "昨天 19:08", tokens: -0.12, status: "已完成" },
  { id: "ledger-3", title: "取消的海报任务", time: "昨天 18:44", tokens: 0.2, status: "已退回" },
  { id: "ledger-4", title: "月度额度发放", time: "本月 1 日", tokens: 30, status: "已完成" },
];

export const orders: OrderRecord[] = [
  { id: "TP20260704001", tokens: 30, status: "已完成", time: "2026-07-04 10:18" },
  { id: "TP20260628009", tokens: 10, status: "已完成", time: "2026-06-28 21:06" },
  { id: "TP20260621011", tokens: 30, status: "已取消", time: "2026-06-21 09:32" },
];

export const workflowHighlights = [
  { icon: Sparkles, title: "今日精选", copy: "新品主图、广告海报、社媒封面、产品短视频画面。" },
  { icon: LayoutTemplate, title: "热门模板", copy: "电商主图、社媒封面、广告海报、产品短视频。" },
  { icon: BadgeCheck, title: "模型扩展", copy: "先接图片模型，后续在后台继续新增视频模型。" },
];
