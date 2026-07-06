export const adminProvider = {
  id: "cangyuan",
  name: "沧元算力",
  baseUrl: "https://ai.cangyuansuanli.cn",
  authType: "Bearer Token",
  status: "active",
  concurrency: 2,
  timeoutMs: 120000,
};

export const adminPlatformModel = {
  id: "tikpan.image.gpt-image-2-4k",
  name: "GPT Image 2 4K",
  displayName: "GPT Image 2 4K",
  category: "图片模型",
  description: "适合高分辨率商品图、广告海报和社媒封面，可在后台按业务包装展示文案。",
  useCaseText: "商品主图，广告海报，社媒封面",
  visible: true,
  estimatedCost: "0.08 Tokens / 张",
  upstreamModelId: "cy-img2-gpt-image-2-4k",
  endpointPath: "/v1/images/generations",
  pollPath: "/v1/images/generations/{task_id}",
};

export const adminParameters = [
  { key: "prompt", label: "画面描述", type: "textarea", required: true, defaultValue: "", upstream: "prompt", transform: "direct" },
  { key: "size", label: "尺寸", type: "select", required: false, defaultValue: "auto", upstream: "size", transform: "direct" },
  { key: "quality", label: "画质", type: "segmented", required: false, defaultValue: "auto", upstream: "quality", transform: "direct" },
  { key: "n", label: "生成张数", type: "number", required: false, defaultValue: "1", upstream: "n", transform: "direct" },
  { key: "background", label: "背景", type: "segmented", required: false, defaultValue: "opaque", upstream: "background", transform: "direct" },
  { key: "output_format", label: "输出格式", type: "segmented", required: false, defaultValue: "png", upstream: "output_format", transform: "direct" },
  { key: "output_compression", label: "压缩质量", type: "slider", required: false, defaultValue: "100", upstream: "output_compression", transform: "direct" },
  { key: "moderation", label: "内容审核", type: "segmented", required: false, defaultValue: "auto", upstream: "moderation", transform: "direct" },
  { key: "stream", label: "流式返回", type: "switch", required: false, defaultValue: "false", upstream: "stream", transform: "direct" },
  { key: "partial_images", label: "部分预览图", type: "number", required: false, defaultValue: "0", upstream: "partial_images", transform: "direct" },
  { key: "async", label: "异步模式", type: "switch", required: false, defaultValue: "true", upstream: "async", transform: "direct" },
];
