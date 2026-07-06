import type { LucideIcon } from "lucide-react";
import {
  AudioLines,
  Bot,
  Clapperboard,
  FileText,
  Image,
  Layers3,
  MessageSquareText,
  Sparkles,
  WandSparkles,
} from "lucide-react";

export type Modality = "image" | "video" | "chat" | "audio" | "workflow";
export type FieldType = "textarea" | "text" | "select" | "segmented" | "slider" | "file" | "switch";
export type RouteMode = "quality" | "balanced" | "fast" | "cheap" | "stable";

export type SchemaField = {
  key: string;
  label: string;
  type: FieldType;
  required?: boolean;
  advanced?: boolean;
  placeholder?: string;
  value?: string | number | boolean;
  defaultValue?: string | number | boolean;
  min?: number;
  max?: number;
  step?: number;
  options?: Array<{ label: string; value: string }>;
};

export type PlatformModel = {
  id: string;
  slug?: string;
  displayName?: string;
  name: string;
  shortName: string;
  modality: Modality;
  categoryKeys?: string[];
  aliases?: string[];
  icon: LucideIcon;
  tier: "Lite" | "Standard" | "Pro" | "Ultra";
  tagline: string;
  description: string;
  useCases: string[];
  price: string;
  eta: string;
  stability: number;
  recommended?: boolean;
  schema: SchemaField[];
};

export type Provider = {
  id: string;
  name: string;
  kind: "official" | "relay" | "private";
  status: "active" | "degraded" | "testing" | "disabled";
  baseUrl: string;
  latency: number;
  successRate: number;
  rpm: number;
  concurrency: number;
};

export type ProviderModel = {
  id: string;
  providerId: string;
  upstreamModelName: string;
  endpointType?: string;
  modality: Modality;
  status: "active" | "degraded" | "testing" | "disabled";
  rawCapabilities?: Record<string, unknown>;
  notes?: string | null;
};

export type Channel = {
  id: string;
  platformModelId: string;
  providerId: string;
  providerModel: string;
  role: "primary" | "backup" | "cheap" | "fast" | "quality";
  status: "active" | "degraded" | "disabled";
  weight: number;
  cost: string;
  sale: string;
  latency: number;
  successRate: number;
  supports: string[];
  paramMap: Array<{
    platform: string;
    upstream: string;
    transform: "direct" | "map" | "default" | "omit" | "template";
    note: string;
    valueMap?: Record<string, unknown>;
    defaultValue?: unknown;
  }>;
};

export type Task = {
  id: string;
  title: string;
  model: string;
  status: "queued" | "running" | "saving" | "completed" | "failed";
  cost: string;
  time: string;
  progress: number;
};

export const modeLabels: Record<RouteMode, string> = {
  quality: "质量优先",
  balanced: "均衡模式",
  fast: "速度优先",
  cheap: "成本优先",
  stable: "稳定优先",
};

export const platformModels: PlatformModel[] = [
  {
    id: "tikpan.image.pro",
    name: "图像生成 Pro",
    shortName: "图片 Pro",
    modality: "image",
    icon: Image,
    tier: "Pro",
    tagline: "适合商品图、海报、封面和社媒素材",
    description: "输入一句想法，生成可直接用于营销、内容创作和商品展示的图片素材。",
    useCases: ["商品主图", "广告海报", "社媒封面", "人物头像"],
    price: "0.18 Tokens 起 / 次",
    eta: "8-15 秒",
    stability: 98.4,
    recommended: true,
    schema: [
      {
        key: "prompt",
        label: "画面描述",
        type: "textarea",
        required: true,
        placeholder: "例如：一张明亮干净的护肤品商品图，柔和自然光，浅绿色背景",
      },
      {
        key: "aspect_ratio",
        label: "画面比例",
        type: "segmented",
        value: "1:1",
        options: [
          { label: "1:1", value: "1:1" },
          { label: "3:4", value: "3:4" },
          { label: "4:3", value: "4:3" },
          { label: "16:9", value: "16:9" },
        ],
      },
      {
        key: "quality",
        label: "生成质量",
        type: "select",
        value: "balanced",
        options: [
          { label: "快速", value: "fast" },
          { label: "标准", value: "balanced" },
          { label: "高清", value: "high" },
        ],
      },
      {
        key: "reference_image",
        label: "参考图",
        type: "file",
        advanced: true,
        placeholder: "上传商品、人物或风格参考",
      },
      {
        key: "negative_prompt",
        label: "不希望出现",
        type: "text",
        advanced: true,
        placeholder: "例如：模糊、变形、低清晰度",
      },
      {
        key: "simulate_failover",
        label: "模拟主渠道超时",
        type: "switch",
        value: false,
        advanced: true,
      },
    ],
  },
  {
    id: "tikpan.video.story",
    name: "视频生成 Story",
    shortName: "视频 Story",
    modality: "video",
    icon: Clapperboard,
    tier: "Ultra",
    tagline: "适合短视频广告、产品展示和创意分镜",
    description: "把脚本、图片或概念变成短视频素材，支持文生视频和图生视频工作流。",
    useCases: ["图生视频", "产品展示", "广告短片", "动态海报"],
    price: "1.20 Tokens 起 / 5 秒",
    eta: "35-90 秒",
    stability: 96.1,
    schema: [
      {
        key: "prompt",
        label: "视频描述",
        type: "textarea",
        required: true,
        placeholder: "例如：镜头缓慢推进，一瓶香水放在水面上，光线清透，高级广告质感",
      },
      {
        key: "duration",
        label: "视频时长",
        type: "segmented",
        value: "5",
        options: [
          { label: "5 秒", value: "5" },
          { label: "8 秒", value: "8" },
          { label: "10 秒", value: "10" },
        ],
      },
      {
        key: "resolution",
        label: "清晰度",
        type: "select",
        value: "720p",
        options: [
          { label: "720p", value: "720p" },
          { label: "1080p", value: "1080p" },
        ],
      },
      {
        key: "first_frame",
        label: "首帧图片",
        type: "file",
        advanced: true,
        placeholder: "上传一张图片作为视频起始画面",
      },
      {
        key: "motion",
        label: "运动强度",
        type: "slider",
        min: 1,
        max: 10,
        step: 1,
        value: 6,
        advanced: true,
      },
    ],
  },
  {
    id: "tikpan.chat.assistant",
    name: "智能对话 Assistant",
    shortName: "对话助手",
    modality: "chat",
    icon: MessageSquareText,
    tier: "Standard",
    tagline: "适合文案、分析、客服和知识库问答",
    description: "面向日常工作的一站式文本助手，后续可接入文件、联网和团队知识库。",
    useCases: ["文案润色", "脚本扩写", "知识问答", "客服回复"],
    price: "按 Tokens 用量计费",
    eta: "实时响应",
    stability: 99.2,
    schema: [
      {
        key: "message",
        label: "你的问题",
        type: "textarea",
        required: true,
        placeholder: "例如：帮我把这段商品介绍改成更适合小红书的口吻",
      },
      {
        key: "tone",
        label: "回答风格",
        type: "select",
        value: "natural",
        options: [
          { label: "自然", value: "natural" },
          { label: "专业", value: "pro" },
          { label: "营销", value: "marketing" },
        ],
      },
      {
        key: "stream",
        label: "流式输出",
        type: "switch",
        value: true,
        advanced: true,
      },
    ],
  },
  {
    id: "tikpan.audio.voice",
    name: "声音生成 Voice",
    shortName: "声音 Voice",
    modality: "audio",
    icon: AudioLines,
    tier: "Standard",
    tagline: "适合配音、旁白和短视频音频素材",
    description: "为视频、课程、广告和内容创作生成自然旁白，后续可扩展音乐与克隆声音。",
    useCases: ["中文配音", "课程旁白", "广告口播", "角色声音"],
    price: "0.06 Tokens 起 / 百字",
    eta: "3-8 秒",
    stability: 97.7,
    schema: [
      {
        key: "script",
        label: "配音文案",
        type: "textarea",
        required: true,
        placeholder: "输入要生成语音的文案",
      },
      {
        key: "voice",
        label: "声音类型",
        type: "select",
        value: "warm_female",
        options: [
          { label: "温柔女声", value: "warm_female" },
          { label: "稳重男声", value: "calm_male" },
          { label: "活力口播", value: "bright" },
        ],
      },
      {
        key: "speed",
        label: "语速",
        type: "slider",
        min: 0.75,
        max: 1.5,
        step: 0.05,
        value: 1,
      },
    ],
  },
  {
    id: "tikpan.workflow.ecommerce",
    name: "电商素材工作流",
    shortName: "电商工作流",
    modality: "workflow",
    icon: WandSparkles,
    tier: "Pro",
    tagline: "一次生成商品图、卖点文案和短视频脚本",
    description: "把重复的内容生产动作打包成工作流，让运营人员从一个入口完成整套素材准备。",
    useCases: ["商品上新", "详情页素材", "投放素材", "直播预热"],
    price: "2.80 Tokens 起 / 套",
    eta: "1-3 分钟",
    stability: 95.6,
    schema: [
      {
        key: "product",
        label: "商品信息",
        type: "textarea",
        required: true,
        placeholder: "商品名称、卖点、目标人群、价格区间",
      },
      {
        key: "package",
        label: "输出内容",
        type: "select",
        value: "starter",
        options: [
          { label: "基础素材包", value: "starter" },
          { label: "投放素材包", value: "ads" },
          { label: "上新全套包", value: "launch" },
        ],
      },
      {
        key: "brand_tone",
        label: "品牌调性",
        type: "text",
        placeholder: "例如：清爽、专业、高端、年轻化",
      },
    ],
  },
];

export const providers: Provider[] = [
  {
    id: "relay-a",
    name: "Relay A",
    kind: "relay",
    status: "active",
    baseUrl: "https://api.relay-a.example/v1",
    latency: 820,
    successRate: 98.2,
    rpm: 600,
    concurrency: 16,
  },
  {
    id: "relay-b",
    name: "Relay B",
    kind: "relay",
    status: "active",
    baseUrl: "https://gateway.relay-b.example",
    latency: 640,
    successRate: 97.5,
    rpm: 420,
    concurrency: 10,
  },
  {
    id: "official-c",
    name: "Official C",
    kind: "official",
    status: "degraded",
    baseUrl: "https://api.official-c.example",
    latency: 1280,
    successRate: 94.8,
    rpm: 180,
    concurrency: 5,
  },
];

export const providerModels: ProviderModel[] = [
  {
    id: "pm-image-a",
    providerId: "relay-a",
    upstreamModelName: "gpt-image-1",
    modality: "image",
    status: "active",
  },
  {
    id: "pm-image-b",
    providerId: "relay-b",
    upstreamModelName: "openai/gpt-image-1",
    modality: "image",
    status: "active",
  },
  {
    id: "pm-video-a",
    providerId: "relay-a",
    upstreamModelName: "seedance-video-fast",
    modality: "video",
    status: "active",
  },
  {
    id: "pm-chat-c",
    providerId: "official-c",
    upstreamModelName: "gpt-4o-mini",
    modality: "chat",
    status: "degraded",
  },
];

export const channels: Channel[] = [
  {
    id: "ch-image-a",
    platformModelId: "tikpan.image.pro",
    providerId: "relay-a",
    providerModel: "gpt-image-1",
    role: "primary",
    status: "active",
    weight: 60,
    cost: "0.11",
    sale: "0.18",
    latency: 9.2,
    successRate: 98.7,
    supports: ["prompt", "aspect_ratio", "quality", "seed", "reference_image"],
    paramMap: [
      { platform: "prompt", upstream: "prompt", transform: "direct", note: "原样传递" },
      {
        platform: "aspect_ratio",
        upstream: "size",
        transform: "map",
        note: "1:1 -> 1024x1024",
        valueMap: { "1:1": "1024x1024", "3:4": "1024x1365", "4:3": "1365x1024", "16:9": "1536x864" },
      },
      {
        platform: "quality",
        upstream: "quality",
        transform: "map",
        note: "high -> hd",
        valueMap: { fast: "standard", balanced: "hd", high: "ultra" },
      },
      { platform: "negative_prompt", upstream: "-", transform: "omit", note: "该渠道忽略" },
    ],
  },
  {
    id: "ch-image-b",
    platformModelId: "tikpan.image.pro",
    providerId: "relay-b",
    providerModel: "openai/gpt-image-1",
    role: "backup",
    status: "active",
    weight: 30,
    cost: "0.13",
    sale: "0.18",
    latency: 11.8,
    successRate: 97.9,
    supports: ["prompt", "aspect_ratio", "quality", "negative_prompt"],
    paramMap: [
      { platform: "prompt", upstream: "input_prompt", transform: "direct", note: "字段重命名" },
      {
        platform: "aspect_ratio",
        upstream: "image_size",
        transform: "map",
        note: "1:1 -> square_hd",
        valueMap: { "1:1": "square_hd", "3:4": "portrait_4_3", "4:3": "landscape_4_3", "16:9": "landscape_16_9" },
      },
      { platform: "quality", upstream: "steps", transform: "map", note: "high -> 40", valueMap: { fast: 20, balanced: 30, high: 40 } },
      { platform: "seed", upstream: "-", transform: "omit", note: "不支持随机种子" },
    ],
  },
  {
    id: "ch-video-a",
    platformModelId: "tikpan.video.story",
    providerId: "relay-a",
    providerModel: "seedance-video-fast",
    role: "fast",
    status: "active",
    weight: 55,
    cost: "0.82",
    sale: "1.20",
    latency: 42,
    successRate: 96.8,
    supports: ["prompt", "duration", "resolution", "first_frame"],
    paramMap: [
      { platform: "prompt", upstream: "prompt", transform: "direct", note: "原样传递" },
      { platform: "duration", upstream: "seconds", transform: "direct", note: "秒数" },
      { platform: "resolution", upstream: "quality", transform: "map", note: "1080p -> high", valueMap: { "720p": "standard", "1080p": "high" } },
      { platform: "motion", upstream: "-", transform: "default", note: "使用渠道默认运动强度" },
    ],
  },
  {
    id: "ch-chat-a",
    platformModelId: "tikpan.chat.assistant",
    providerId: "official-c",
    providerModel: "gpt-4o-mini",
    role: "cheap",
    status: "degraded",
    weight: 20,
    cost: "0.8 / M tokens",
    sale: "1.6 / M tokens",
    latency: 1.6,
    successRate: 94.8,
    supports: ["message", "tone", "stream"],
    paramMap: [
      { platform: "message", upstream: "messages", transform: "template", note: "包装成 messages 数组" },
      { platform: "tone", upstream: "system", transform: "template", note: "转换成系统提示词" },
      { platform: "stream", upstream: "stream", transform: "direct", note: "布尔值" },
    ],
  },
];

export const tasks: Task[] = [
  {
    id: "task_72ca",
    title: "护肤品商品主图",
    model: "图像生成 Pro",
    status: "completed",
    cost: "0.18",
    time: "12 秒",
    progress: 100,
  },
  {
    id: "task_91fb",
    title: "香水广告短视频",
    model: "视频生成 Story",
    status: "saving",
    cost: "1.20",
    time: "58 秒",
    progress: 86,
  },
  {
    id: "task_a84d",
    title: "小红书文案优化",
    model: "智能对话 Assistant",
    status: "running",
    cost: "0.03",
    time: "实时",
    progress: 64,
  },
];

export const productStats = [
  { label: "今日生成", value: "1,284", detail: "+18.6%" },
  { label: "成功率", value: "97.8%", detail: "近 24 小时" },
  { label: "灵感模板", value: "128", detail: "持续更新" },
  { label: "平均等待", value: "8.7s", detail: "图片与文本" },
];

export const capabilityNav = [
  { key: "image", label: "图片", icon: Image },
  { key: "video", label: "视频", icon: Clapperboard },
  { key: "chat", label: "聊天", icon: MessageSquareText },
  { key: "audio", label: "音频", icon: AudioLines },
  { key: "workflow", label: "工作流", icon: Layers3 },
] as const;

export const userBenefits = [
  {
    icon: Sparkles,
    title: "多能力一处完成",
    copy: "图片、视频、对话、音频和工作流都从同一个工作台开始。",
  },
  {
    icon: Bot,
    title: "生成过程更省心",
    copy: "用户只需要描述目标，系统自动匹配合适能力和参数。",
  },
  {
    icon: FileText,
    title: "费用与记录清晰",
    copy: "生成前显示 Tokens 预估消耗，完成后自动保存作品记录。",
  },
];
