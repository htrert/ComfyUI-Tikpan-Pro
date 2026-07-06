export const providers = [
  {
    id: "cangyuan",
    name: "沧元算力",
    kind: "relay",
    baseUrl: "https://ai.cangyuansuanli.cn",
    authType: "bearer",
    status: "active",
    rpm: 60,
    concurrency: 2,
    latencyMs: 1800,
    successRate: 98,
    timeoutMs: 120000,
  },
  {
    id: "tikpan",
    name: "Tikpan",
    kind: "relay",
    baseUrl: "https://tikpan.com",
    authType: "bearer",
    status: "active",
    rpm: 60,
    concurrency: 2,
    latencyMs: 2200,
    successRate: 98,
    timeoutMs: 600000,
  },
];

export const providerKeys = [
  {
    id: "pkey-cangyuan-main",
    providerId: "cangyuan",
    name: "Cangyuan Main Key",
    encryptedApiKey: "demo-encrypted-cangyuan-main",
    status: "active",
    rpm: 60,
    tpm: null,
    concurrency: 2,
    priority: 1,
    weight: 100,
    supportedProviderModelIds: ["pm-cangyuan-gpt-image-2-4k"],
    currentConcurrency: 0,
    minuteWindowStartedAt: null,
    minuteRequestCount: 0,
    todayRequestCount: 0,
    coolingUntil: null,
    lastUsedAt: null,
    lastErrorCode: null,
    lastErrorMessage: null,
    notes: "Internal upstream credential. Never exposed to platform users.",
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  },
  {
    id: "pkey-tikpan-main",
    providerId: "tikpan",
    name: "Tikpan Main Key",
    encryptedApiKey: "demo-encrypted-tikpan-main",
    status: "active",
    rpm: 60,
    tpm: null,
    concurrency: 2,
    priority: 1,
    weight: 100,
    supportedProviderModelIds: ["pm-tikpan-gpt-image-2-edit-v2", "pm-tikpan-claude-fable-5"],
    currentConcurrency: 0,
    minuteWindowStartedAt: null,
    minuteRequestCount: 0,
    todayRequestCount: 0,
    coolingUntil: null,
    lastUsedAt: null,
    lastErrorCode: null,
    lastErrorMessage: null,
    notes: "Internal upstream credential. Never exposed to platform users.",
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  },
];

export const providerKeyLeases = [];

export const providerModels = [
  {
    id: "pm-cangyuan-gpt-image-2-4k",
    providerId: "cangyuan",
    upstreamModelName: "cy-img2-gpt-image-2-4k",
    endpointType: "image_generation",
    modality: "image",
    status: "active",
    rawCapabilities: {
      display_model: "gpt-image-2-4k",
      endpoint_path: "/v1/images/generations",
      async_poll: true,
      poll_status_path: "/v1/images/generations/{task_id}",
      poll_interval_ms: 1500,
      compatible: "openai-gpt-image",
      supports: [
        "prompt",
        "size",
        "n",
        "quality",
        "background",
        "output_format",
        "output_compression",
        "moderation",
        "stream",
        "partial_images",
        "async",
      ],
    },
    notes: "Cangyuan gpt-image-2-4k text-to-image async mode.",
  },
  {
    id: "pm-tikpan-gpt-image-2-edit-v2",
    providerId: "tikpan",
    upstreamModelName: "gpt-image-2",
    endpointType: "image_edit",
    modality: "image",
    status: "active",
    rawCapabilities: {
      display_model: "gpt-image-2",
      endpoint_path: "/v1/images/edits",
      request_format: "multipart",
      compatible: "openai-image-edit",
      supports: [
        "prompt",
        "main_image_url",
        "reference_image_1_url",
        "reference_image_2_url",
        "reference_image_3_url",
        "reference_image_4_url",
        "mask_url",
        "n",
        "size",
        "quality",
        "background",
        "moderation",
      ],
    },
    notes: "Tikpan gpt-image-2 image edit V2 multipart endpoint.",
  },
  {
    id: "pm-tikpan-claude-fable-5",
    providerId: "tikpan",
    upstreamModelName: "claude-fable-5",
    endpointType: "chat_completions",
    modality: "chat",
    status: "active",
    rawCapabilities: {
      display_model: "claude-fable-5",
      endpoint_path: "/v1/chat/completions",
      compatible: "openai-chat",
      supports: ["prompt", "system_prompt", "temperature", "max_tokens"],
    },
    notes: "Tikpan Claude Fable 5 chat/text model.",
  },
];

export const platformModels = [
  {
    id: "tikpan.image.gpt-image-2-4k",
    name: "GPT Image 2 4K",
    shortName: "Image 2 4K",
    modality: "image",
    tier: "pro",
    description: "适合高分辨率商品图、广告海报和社媒封面，可在后台自定义前台展示名称、简介和参数。",
    useCases: ["商品主图", "广告海报", "社媒封面"],
    visible: true,
    recommended: true,
    estimatedCost: "0.08 Tokens / 张",
    estimatedTime: "异步生成",
    sortOrder: 10,
    schema: [
      { key: "prompt", label: "画面描述", type: "textarea", required: true },
      {
        key: "size",
        label: "尺寸",
        type: "select",
        defaultValue: "auto",
        options: ["auto", "1024x1024", "1536x1024", "1024x1536", "2048x2048", "3840x2160"],
      },
      {
        key: "quality",
        label: "画质",
        type: "segmented",
        defaultValue: "auto",
        options: ["auto", "low", "medium", "high"],
      },
      { key: "n", label: "生成张数", type: "slider", defaultValue: 1, min: 1, max: 10, step: 1 },
      {
        key: "background",
        label: "背景",
        type: "segmented",
        defaultValue: "opaque",
        options: ["auto", "opaque"],
      },
      {
        key: "output_format",
        label: "输出格式",
        type: "segmented",
        defaultValue: "png",
        options: ["png", "jpeg", "webp"],
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
      },
      {
        key: "moderation",
        label: "内容审核",
        type: "segmented",
        defaultValue: "auto",
        options: ["auto", "low"],
        advanced: true,
      },
      { key: "stream", label: "流式返回", type: "switch", defaultValue: false, advanced: true },
      { key: "partial_images", label: "部分预览图", type: "slider", defaultValue: 0, min: 0, max: 3, step: 1, advanced: true },
      { key: "async", label: "异步模式", type: "switch", defaultValue: true, advanced: true },
    ],
  },
  {
    id: "tikpan.image.gpt-image-2-edit-v2",
    name: "GPT Image 2 Edit V2",
    shortName: "Image 2 Edit",
    modality: "image",
    tier: "pro",
    description: "Instruction-based image editing with masks and reference images through Tikpan gpt-image-2.",
    useCases: ["image editing", "product retouching", "background replacement", "local inpainting"],
    visible: true,
    recommended: true,
    estimatedCost: "0.60 Tokens / image",
    estimatedTime: "Long-running edit task",
    sortOrder: 11,
    schema: [
      { key: "prompt", label: "Edit instruction", type: "textarea", required: true },
      {
        key: "main_image_url",
        label: "Main image URL",
        type: "text",
        required: true,
        helper: "HTTP(S) image URL or data URL.",
      },
      { key: "reference_image_1_url", label: "Reference image 1", type: "text", advanced: true },
      { key: "reference_image_2_url", label: "Reference image 2", type: "text", advanced: true },
      { key: "reference_image_3_url", label: "Reference image 3", type: "text", advanced: true },
      { key: "reference_image_4_url", label: "Reference image 4", type: "text", advanced: true },
      {
        key: "mask_url",
        label: "Mask image URL",
        type: "text",
        advanced: true,
        helper: "White area is edited; black area is preserved.",
      },
      { key: "n", label: "Output count", type: "slider", defaultValue: 1, min: 1, max: 10, step: 1 },
      {
        key: "size",
        label: "Size",
        type: "select",
        defaultValue: "auto",
        options: ["auto", "1024x1024", "1536x1024", "1024x1536", "2048x2048", "2048x1152", "1152x2048", "3840x2160", "2160x3840"],
      },
      {
        key: "quality",
        label: "Quality",
        type: "segmented",
        defaultValue: "medium",
        options: ["low", "medium", "high"],
      },
      {
        key: "background",
        label: "Background",
        type: "segmented",
        defaultValue: "auto",
        options: ["auto", "opaque"],
      },
      {
        key: "moderation",
        label: "Moderation",
        type: "segmented",
        defaultValue: "auto",
        options: ["auto", "low"],
        advanced: true,
      },
    ],
  },
  {
    id: "tikpan.chat.claude-fable-5",
    name: "Claude Fable 5",
    shortName: "Fable 5",
    modality: "chat",
    tier: "pro",
    description: "A chat and copywriting model for long-form drafting, rewrites, ideation, and structured text generation.",
    useCases: ["copywriting", "story drafting", "knowledge Q&A", "script polishing"],
    visible: true,
    recommended: true,
    estimatedCost: "0.03 Tokens / request",
    estimatedTime: "Streaming-ready text",
    sortOrder: 30,
    schema: [
      { key: "prompt", label: "Prompt", type: "textarea", required: true },
      {
        key: "system_prompt",
        label: "System prompt",
        type: "text",
        defaultValue: "You are a helpful creative writing assistant.",
        advanced: true,
      },
      { key: "temperature", label: "Temperature", type: "slider", defaultValue: 0.7, min: 0, max: 2, step: 0.1 },
      { key: "max_tokens", label: "Max tokens", type: "slider", defaultValue: 1200, min: 64, max: 8192, step: 64, advanced: true },
    ],
  },
];

export const modelCategories = [
  { id: "cat-all", key: "all", name: "全部", icon: "sparkles", sortOrder: 0, visible: true, parentId: null, status: "published", aliases: [] },
  { id: "cat-image", key: "image", name: "图片", icon: "image", sortOrder: 10, visible: true, parentId: null, status: "published", aliases: ["图像", "AI 图片", "图片创作"] },
  { id: "cat-video", key: "video", name: "视频", icon: "clapperboard", sortOrder: 20, visible: true, parentId: null, status: "published", aliases: ["AI 视频", "短视频"] },
  { id: "cat-chat", key: "chat", name: "文案", icon: "file-text", sortOrder: 30, visible: true, parentId: null, status: "published", aliases: ["对话", "文本", "文案创作"] },
  { id: "cat-audio", key: "audio", name: "音频", icon: "audio-lines", sortOrder: 40, visible: true, parentId: null, status: "published", aliases: ["配音", "声音"] },
  { id: "cat-workflow", key: "workflow", name: "工作流", icon: "layers-3", sortOrder: 50, visible: true, parentId: null, status: "published", aliases: ["自动化", "内容套装"] },
];

export const platformModelCategoryAssignments = [
  { id: "assign-gpt-image-2-4k-image", platformModelId: "tikpan.image.gpt-image-2-4k", categoryId: "cat-image", sortOrder: 10, isPrimary: true },
  { id: "assign-gpt-image-2-edit-v2-image", platformModelId: "tikpan.image.gpt-image-2-edit-v2", categoryId: "cat-image", sortOrder: 11, isPrimary: true },
  { id: "assign-claude-fable-5-chat", platformModelId: "tikpan.chat.claude-fable-5", categoryId: "cat-chat", sortOrder: 30, isPrimary: true },
];

export const platformModelAliases = [
  { id: "alias-claude-fable-5-slug", platformModelId: "tikpan.chat.claude-fable-5", alias: "claude-fable-5", kind: "legacy" },
  { id: "alias-claude-fable-5-search-1", platformModelId: "tikpan.chat.claude-fable-5", alias: "fable", kind: "search" },
  { id: "alias-claude-fable-5-search-2", platformModelId: "tikpan.chat.claude-fable-5", alias: "creative writing", kind: "marketing" },
  { id: "alias-gpt-image-2-4k-slug", platformModelId: "tikpan.image.gpt-image-2-4k", alias: "gpt-image-2-4k", kind: "legacy" },
  { id: "alias-gpt-image-2-4k-search-1", platformModelId: "tikpan.image.gpt-image-2-4k", alias: "图像生成 Pro", kind: "marketing" },
  { id: "alias-gpt-image-2-4k-search-2", platformModelId: "tikpan.image.gpt-image-2-4k", alias: "商品主图生成", kind: "search" },
  { id: "alias-gpt-image-2-edit-v2-slug", platformModelId: "tikpan.image.gpt-image-2-edit-v2", alias: "gpt-image-2-edit-v2", kind: "legacy" },
  { id: "alias-gpt-image-2-edit-v2-search-1", platformModelId: "tikpan.image.gpt-image-2-edit-v2", alias: "图片修图", kind: "search" },
  { id: "alias-gpt-image-2-edit-v2-search-2", platformModelId: "tikpan.image.gpt-image-2-edit-v2", alias: "局部重绘", kind: "search" },
];

export const modelChannels = [
  {
    id: "ch-cangyuan-gpt-image-2-4k",
    platformModelId: "tikpan.image.gpt-image-2-4k",
    providerId: "cangyuan",
    providerModelId: "pm-cangyuan-gpt-image-2-4k",
    role: "primary",
    status: "active",
    weight: 100,
    priority: 1,
    costPrice: 0.08,
    salePrice: 0.08,
    billingUnit: "image",
    latency: 18,
    successRate: 98,
    supports: [
      "prompt",
      "size",
      "n",
      "quality",
      "background",
      "output_format",
      "output_compression",
      "moderation",
      "stream",
      "partial_images",
      "async",
    ],
    timeoutMs: 120000,
  },
  {
    id: "ch-tikpan-gpt-image-2-edit-v2",
    platformModelId: "tikpan.image.gpt-image-2-edit-v2",
    providerId: "tikpan",
    providerModelId: "pm-tikpan-gpt-image-2-edit-v2",
    role: "primary",
    status: "active",
    weight: 100,
    priority: 1,
    costPrice: 0.45,
    salePrice: 0.6,
    billingUnit: "image",
    latency: 45,
    successRate: 98,
    supports: [
      "prompt",
      "main_image_url",
      "reference_image_1_url",
      "reference_image_2_url",
      "reference_image_3_url",
      "reference_image_4_url",
      "mask_url",
      "n",
      "size",
      "quality",
      "background",
      "moderation",
    ],
    timeoutMs: 600000,
  },
  {
    id: "ch-tikpan-claude-fable-5",
    platformModelId: "tikpan.chat.claude-fable-5",
    providerId: "tikpan",
    providerModelId: "pm-tikpan-claude-fable-5",
    role: "primary",
    status: "active",
    weight: 100,
    priority: 1,
    costPrice: 0.02,
    salePrice: 0.03,
    billingUnit: "request",
    latency: 6,
    successRate: 98,
    supports: ["prompt", "system_prompt", "temperature", "max_tokens"],
    timeoutMs: 120000,
  },
];

export const parameterMappings = [
  { channelId: "ch-cangyuan-gpt-image-2-4k", platform: "model", upstream: "model", transform: "default", defaultValue: "cy-img2-gpt-image-2-4k" },
  { channelId: "ch-cangyuan-gpt-image-2-4k", platform: "prompt", upstream: "prompt", transform: "direct" },
  { channelId: "ch-cangyuan-gpt-image-2-4k", platform: "size", upstream: "size", transform: "direct", defaultValue: "auto" },
  { channelId: "ch-cangyuan-gpt-image-2-4k", platform: "n", upstream: "n", transform: "direct", defaultValue: 1 },
  { channelId: "ch-cangyuan-gpt-image-2-4k", platform: "quality", upstream: "quality", transform: "direct", defaultValue: "auto" },
  { channelId: "ch-cangyuan-gpt-image-2-4k", platform: "background", upstream: "background", transform: "direct", defaultValue: "opaque" },
  { channelId: "ch-cangyuan-gpt-image-2-4k", platform: "output_format", upstream: "output_format", transform: "direct", defaultValue: "png" },
  { channelId: "ch-cangyuan-gpt-image-2-4k", platform: "output_compression", upstream: "output_compression", transform: "direct", defaultValue: 100 },
  { channelId: "ch-cangyuan-gpt-image-2-4k", platform: "moderation", upstream: "moderation", transform: "direct", defaultValue: "auto" },
  { channelId: "ch-cangyuan-gpt-image-2-4k", platform: "stream", upstream: "stream", transform: "direct", defaultValue: false },
  { channelId: "ch-cangyuan-gpt-image-2-4k", platform: "partial_images", upstream: "partial_images", transform: "direct", defaultValue: 0 },
  { channelId: "ch-cangyuan-gpt-image-2-4k", platform: "async", upstream: "async", transform: "direct", defaultValue: true },
  { channelId: "ch-tikpan-gpt-image-2-edit-v2", platform: "model", upstream: "model", transform: "default", defaultValue: "gpt-image-2" },
  { channelId: "ch-tikpan-gpt-image-2-edit-v2", platform: "prompt", upstream: "prompt", transform: "direct" },
  { channelId: "ch-tikpan-gpt-image-2-edit-v2", platform: "main_image_url", upstream: "main_image_url", transform: "direct" },
  { channelId: "ch-tikpan-gpt-image-2-edit-v2", platform: "reference_image_1_url", upstream: "reference_image_1_url", transform: "direct" },
  { channelId: "ch-tikpan-gpt-image-2-edit-v2", platform: "reference_image_2_url", upstream: "reference_image_2_url", transform: "direct" },
  { channelId: "ch-tikpan-gpt-image-2-edit-v2", platform: "reference_image_3_url", upstream: "reference_image_3_url", transform: "direct" },
  { channelId: "ch-tikpan-gpt-image-2-edit-v2", platform: "reference_image_4_url", upstream: "reference_image_4_url", transform: "direct" },
  { channelId: "ch-tikpan-gpt-image-2-edit-v2", platform: "mask_url", upstream: "mask_url", transform: "direct" },
  { channelId: "ch-tikpan-gpt-image-2-edit-v2", platform: "n", upstream: "n", transform: "direct", defaultValue: 1 },
  { channelId: "ch-tikpan-gpt-image-2-edit-v2", platform: "size", upstream: "size", transform: "direct", defaultValue: "auto" },
  { channelId: "ch-tikpan-gpt-image-2-edit-v2", platform: "quality", upstream: "quality", transform: "direct", defaultValue: "medium" },
  { channelId: "ch-tikpan-gpt-image-2-edit-v2", platform: "background", upstream: "background", transform: "direct", defaultValue: "auto" },
  { channelId: "ch-tikpan-gpt-image-2-edit-v2", platform: "moderation", upstream: "moderation", transform: "direct", defaultValue: "auto" },
  { channelId: "ch-tikpan-claude-fable-5", platform: "model", upstream: "model", transform: "default", defaultValue: "claude-fable-5" },
  { channelId: "ch-tikpan-claude-fable-5", platform: "prompt", upstream: "prompt", transform: "direct" },
  { channelId: "ch-tikpan-claude-fable-5", platform: "system_prompt", upstream: "system", transform: "direct" },
  { channelId: "ch-tikpan-claude-fable-5", platform: "temperature", upstream: "temperature", transform: "direct", defaultValue: 0.7 },
  { channelId: "ch-tikpan-claude-fable-5", platform: "max_tokens", upstream: "max_tokens", transform: "direct", defaultValue: 1200 },
];

export const tasks = [];
export const projects = [
  {
    id: "proj_campaign_skin_2026",
    userId: "demo_user",
    name: "Summer skincare campaign",
    type: "image_campaign",
    status: "active",
    description: "Product hero images, social covers, and short video prompts for a seasonal launch.",
    coverUrl: null,
    settings: {
      defaultModel: "tikpan.image.gpt-image-2-4k",
      routeMode: "quality",
      brandTone: "clean, bright, premium",
    },
    tags: ["commerce", "campaign", "social"],
    createdAt: "2026-07-04T09:30:00.000Z",
    updatedAt: "2026-07-05T16:20:00.000Z",
    archivedAt: null,
  },
  {
    id: "proj_storyboard_demo",
    userId: "demo_user",
    name: "Product video storyboard",
    type: "video_storyboard",
    status: "draft",
    description: "Shot list, image references, and generation tasks for a 10 second product reel.",
    coverUrl: null,
    settings: {
      defaultModel: "tikpan.chat.claude-fable-5",
      routeMode: "balanced",
      duration: "10s",
    },
    tags: ["video", "storyboard"],
    createdAt: "2026-07-03T13:10:00.000Z",
    updatedAt: "2026-07-04T10:45:00.000Z",
    archivedAt: null,
  },
];
export const presets = [];
export const assetMetadata = [];

export const users = [
  {
    id: "demo_user",
    displayName: "Demo User",
    email: "demo@tikpan.local",
    status: "active",
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  },
];

export const billingPlans = [
  {
    id: "starter",
    name: "Starter",
    monthlyTaskLimit: 120,
    monthlySpendLimit: 30,
    rateLimitPerMinute: 20,
    concurrencyLimit: 2,
    features: ["image", "video", "chat"],
    status: "active",
  },
];

export const userSubscriptions = [
  {
    id: "sub_demo_starter",
    userId: "demo_user",
    planId: "starter",
    status: "active",
    renewsAt: new Date(new Date().getFullYear(), new Date().getMonth() + 1, 1).toISOString(),
  },
];

export const rateLimitBuckets = [];

export const wallets = [
  {
    userId: "demo_user",
    currency: "TOKENS",
    balance: 8.8,
    frozen: 0,
    updatedAt: new Date().toISOString(),
  },
];

export const walletLedger = [
  {
    id: "ledger_seed_balance",
    userId: "demo_user",
    taskId: null,
    type: "top_up",
    amount: 8.8,
    balanceAfter: 8.8,
    frozenAfter: 0,
    note: "Demo initial balance",
    createdAt: new Date().toISOString(),
  },
];

export const paymentOrders = [];

export const paymentProviders = [
  {
    id: "mock",
    name: "Mock Pay",
    kind: "mock",
    status: "active",
    currencies: ["TOKENS"],
    feeRate: 0,
    fixedFee: 0,
    minAmount: 0.01,
    maxAmount: 999999,
    checkoutMode: "mock",
    webhookSecret: "tikpan_mock_webhook_secret",
    sortOrder: 10,
    metadata: { settlement: "instant" },
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  },
];

export const apiKeys = [
  {
    id: "key_demo_default",
    userId: "demo_user",
    name: "Default Demo Key",
    prefix: "tk_demo",
    secret: "tk_demo_sk_live_demo123456",
    status: "active",
    scopes: ["tasks:create", "wallet:read"],
    lastUsedAt: null,
    createdAt: new Date().toISOString(),
  },
];

export const webhookEndpoints = [];
export const webhookDeliveries = [];

export const auditLogs = [
  {
    id: "audit_seed_catalog",
    actorId: "system",
    actorType: "system",
    action: "catalog.seeded",
    resourceType: "platform",
    resourceId: "memory",
    userId: null,
    summary: "Seeded Cangyuan gpt-image-2-4k single-channel catalog.",
    metadata: {
      providers: providers.length,
      platformModels: platformModels.length,
      channels: modelChannels.length,
    },
    createdAt: new Date().toISOString(),
  },
];

export function getProvider(id) {
  return providers.find((provider) => provider.id === id);
}

export function getProviderModel(id) {
  return providerModels.find((model) => model.id === id);
}

export function getPlatformModel(id) {
  return platformModels.find((model) => model.id === id);
}

export function getModelCategory(id) {
  return modelCategories.find((category) => category.id === id || category.key === id);
}

export function listCategoriesForModel(platformModelId) {
  return platformModelCategoryAssignments
    .filter((assignment) => assignment.platformModelId === platformModelId)
    .map((assignment) => {
      const category = getModelCategory(assignment.categoryId);
      return category
        ? {
            ...category,
            assignmentId: assignment.id,
            assignmentSortOrder: assignment.sortOrder,
            isPrimary: assignment.isPrimary,
          }
        : null;
    })
    .filter(Boolean);
}

export function listAliasesForModel(platformModelId) {
  return platformModelAliases.filter((alias) => alias.platformModelId === platformModelId);
}

export function getChannelMappings(channelId) {
  return parameterMappings.filter((mapping) => mapping.channelId === channelId);
}

export function listChannelsForModel(platformModelId) {
  return modelChannels.filter((channel) => channel.platformModelId === platformModelId);
}

export function getWallet(userId = "demo_user") {
  let wallet = wallets.find((item) => item.userId === userId);
  if (!wallet) {
    wallet = {
      userId,
      currency: "TOKENS",
      balance: 0,
      frozen: 0,
      updatedAt: new Date().toISOString(),
    };
    wallets.push(wallet);
  }

  return wallet;
}

export function listApiKeys(userId = "demo_user") {
  return apiKeys.filter((key) => key.userId === userId);
}

export function findApiKey(secret) {
  return apiKeys.find((key) => key.secret === secret);
}

export function getBillingPlan(id) {
  return billingPlans.find((plan) => plan.id === id);
}

export function getUserSubscription(userId = "demo_user") {
  let subscription = userSubscriptions.find((item) => item.userId === userId);
  if (!subscription) {
    subscription = {
      id: `sub_${userId}`,
      userId,
      planId: "starter",
      status: "active",
      renewsAt: new Date(new Date().getFullYear(), new Date().getMonth() + 1, 1).toISOString(),
    };
    userSubscriptions.push(subscription);
  }

  return subscription;
}
