const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const { URL } = require("node:url");
const crypto = require("node:crypto");

const root = __dirname;
const publicDir = path.join(root, "public");
const dataDir = path.join(root, "data");
const projectsDir = path.join(dataDir, "projects");
const assetsDir = path.join(dataDir, "assets");
const profilesFile = path.join(dataDir, "model-profiles.json");
const platformConfigFile = path.join(dataDir, "platform-config.json");

for (const dir of [dataDir, projectsDir, assetsDir]) {
  fs.mkdirSync(dir, { recursive: true });
}

const port = Number(process.env.PORT || 3456);
const providerMode = (process.env.PROVIDER || "comfy").toLowerCase();
const comfyBase = process.env.COMFY_URL || "http://127.0.0.1:8188";
const upstreamBase = process.env.UPSTREAM_URL || "";
const upstreamToken = process.env.UPSTREAM_TOKEN || "";
const tikpanApiKey = process.env.TIKPAN_API_KEY || "";
const webAppBase = process.env.WEB_APP_URL || "";
const requireLogin = ["1", "true", "yes"].includes(String(process.env.REQUIRE_LOGIN || "").toLowerCase());
const clientId = crypto.randomUUID();

const mimeTypes = new Map([
  [".html", "text/html; charset=utf-8"],
  [".css", "text/css; charset=utf-8"],
  [".js", "text/javascript; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
  [".png", "image/png"],
  [".jpg", "image/jpeg"],
  [".jpeg", "image/jpeg"],
  [".webp", "image/webp"],
  [".svg", "image/svg+xml"],
  [".mp4", "video/mp4"],
  [".mp3", "audio/mpeg"],
  [".wav", "audio/wav"],
]);

function ensureProfilesFile() {
  if (!fs.existsSync(profilesFile)) {
    fs.writeFileSync(profilesFile, "[]", "utf8");
  }
}

const defaultPlatformConfig = {
  channels: [
    {
      key: "tikpan-main",
      name: "Tikpan 主渠道",
      providerType: "new-api",
      baseUrl: "https://tikpan.com",
      apiKeyEnv: "TIKPAN_API_KEY",
      priority: 10,
      enabled: true,
      notes: "本地开发默认渠道，生产建议放到密钥管理中。",
    },
    {
      key: "newapi-backup",
      name: "New API 备用渠道",
      providerType: "openai-compatible",
      baseUrl: "",
      apiKeyEnv: "NEWAPI_BACKUP_KEY",
      priority: 50,
      enabled: false,
      notes: "用于后续接入低价或备用上游。",
    },
  ],
  routes: [
    {
      profileId: "tikpan-gpt-image-2",
      channelKey: "tikpan-main",
      upstreamModel: "gpt-image-2",
      endpoint: "/v1/images/generations",
      enabled: true,
    },
  ],
  pricing: [
    {
      profileId: "tikpan-gpt-image-2",
      billingMode: "resolution",
      credits1k: 6,
      credits2k: 10,
      credits4k: 18,
      costPerUnit: 0,
      enabled: true,
    },
  ],
  settings: {
    siteName: "Canvas Model Studio",
    requireLoginForGenerate: false,
    defaultProfileId: "tikpan-gpt-image-2",
    assetStorage: "local",
    adminNote: "这里是无限画布自己的运营配置；正式商业化时建议迁移到 web_app 后台和数据库。",
  },
};

const contentFactoryWorkflows = [
  {
    id: "ai-drama-manhua",
    name: "AI短剧 / 漫剧工厂",
    tagline: "从小说或剧情梗概生成角色、世界观、九宫格分镜、图像/视频/配音任务。",
    bestFor: ["小说改编", "漫剧连载", "短剧分镜", "角色账号"],
    northStar: "每个项目稳定产出可连载的短视频分镜和资产包。",
    defaultProfileId: "tikpan-gpt-image-2",
    lanes: [
      { key: "source", title: "原文与设定", x: -860 },
      { key: "assets", title: "角色/场景资产", x: -420 },
      { key: "storyboard", title: "九宫格分镜", x: 40 },
      { key: "production", title: "生成与后期", x: 520 },
    ],
    steps: [
      {
        lane: "source",
        type: "note",
        title: "项目Brief",
        output: "题材、受众、平台、时长、更新频率、禁区",
        body: "把原文/梗概贴在这里。先确定题材、人群、单集时长、平台比例、风格边界，再让 Agent 拆分后续任务。",
      },
      {
        lane: "source",
        type: "note",
        title: "世界观 Bible",
        output: "时代、地点、规则、视觉关键词、色调",
        body: "维护世界观数据库：服装、建筑、道具、镜头语言、禁用元素。以后每集都从这里继承。",
      },
      {
        lane: "assets",
        type: "prompt",
        profileId: "tikpan-gpt-image-2",
        title: "主角角色卡",
        output: "主角三视图/表情/服装参考",
        prompt: "为这部 AI 漫剧设计主角角色卡：正面半身、三视图、标志性服装、发型、表情组，统一画风，适合后续多集复用。",
      },
      {
        lane: "assets",
        type: "prompt",
        profileId: "tikpan-gpt-image-2",
        title: "关键场景卡",
        output: "固定场景参考图",
        prompt: "设计本集核心场景资产：固定空间、光线、色调、道具、镜头构图，形成可复用的场景参考图。",
      },
      {
        lane: "storyboard",
        type: "note",
        title: "9宫格分镜结构",
        output: "钩子、冲突、反转、高潮、结尾",
        body: "1 钩子；2 主角状态；3 冲突；4 证据/误会；5 情绪特写；6 对手压迫；7 反转；8 高潮；9 下集钩子。",
      },
      {
        lane: "storyboard",
        type: "prompt",
        profileId: "tikpan-gpt-image-2",
        title: "分镜关键帧",
        output: "9张关键帧图",
        prompt: "根据九宫格分镜生成统一画风的关键帧组：人物一致、场景一致、镜头有连续性，适合转视频。",
      },
      {
        lane: "production",
        type: "prompt",
        profileId: "tikpan-veo-video",
        title: "镜头视频化",
        output: "每格 3-5 秒视频片段",
        prompt: "把选中的关键帧转成短剧镜头：轻微推拉摇移，人物动作自然，情绪明确，适合竖屏短视频。",
      },
      {
        lane: "production",
        type: "prompt",
        profileId: "tikpan-suno-music",
        title: "音乐/氛围",
        output: "BGM 或情绪音效",
        prompt: "为本集生成短剧背景音乐：强钩子、情绪递进、适合 30-60 秒竖屏剧情视频。",
      },
      {
        lane: "production",
        type: "note",
        title: "导出发布清单",
        output: "视频、字幕、标题、封面、多语言版本",
        body: "导出前检查：视频比例 9:16、字幕安全区、前三秒钩子、标题关键词、封面冲突点、平台版本。",
      },
    ],
  },
  {
    id: "novel-recap-tiktok",
    name: "小说推文 / TikTok 切片",
    tagline: "把长小说拆成短视频脚本、钩子、分镜、封面和多语言发布素材。",
    bestFor: ["小说号", "推文号", "英文 TikTok", "批量切片"],
    northStar: "每段原文产出一条可发布的 30-60 秒视频脚本和素材。",
    defaultProfileId: "tikpan-gpt-image-2",
    lanes: [
      { key: "source", title: "文本拆解", x: -860 },
      { key: "script", title: "脚本与钩子", x: -420 },
      { key: "visual", title: "画面资产", x: 40 },
      { key: "publish", title: "发布包装", x: 520 },
    ],
    steps: [
      { lane: "source", type: "note", title: "原文片段", output: "章节/高潮段/人物关系", body: "贴入小说片段，标出高潮、反转、冲突和必须保留的人物关系。" },
      { lane: "script", type: "note", title: "三秒钩子", output: "开头第一句话", body: "把冲突提前：背叛、复仇、打脸、误会、身份反转。不要铺垫太久。" },
      { lane: "script", type: "note", title: "60秒旁白脚本", output: "分段旁白", body: "结构：3秒钩子、15秒背景、25秒冲突升级、10秒反转、7秒下集钩子。" },
      { lane: "visual", type: "prompt", profileId: "tikpan-gpt-image-2", title: "封面冲突图", output: "强点击封面", prompt: "生成小说推文封面：人物关系冲突明显，表情强烈，竖屏构图，标题区域留白，画风统一。" },
      { lane: "visual", type: "prompt", profileId: "tikpan-gpt-image-2", title: "情绪关键帧", output: "6-9张配图", prompt: "根据小说剧情生成情绪关键帧：人物一致、场景递进、镜头清晰，适合旁白型短视频。" },
      { lane: "publish", type: "note", title: "字幕与标题", output: "标题、字幕、标签", body: "字幕句子短，标题直接点冲突；英文版需要本地化而不是直译。" },
    ],
  },
  {
    id: "tiktok-commerce",
    name: "TikTok 电商内容工厂",
    tagline: "从产品图生成卖点脚本、模特图、场景视频、配音字幕和多语言素材。",
    bestFor: ["跨境电商", "带货短视频", "产品广告", "素材矩阵"],
    northStar: "每个 SKU 快速产出多条可测的短视频广告素材。",
    defaultProfileId: "tikpan-gpt-image-2",
    lanes: [
      { key: "product", title: "产品资产", x: -860 },
      { key: "angle", title: "卖点角度", x: -420 },
      { key: "creative", title: "创意生成", x: 40 },
      { key: "test", title: "投放测试", x: 520 },
    ],
    steps: [
      { lane: "product", type: "note", title: "产品输入", output: "产品图、价格、卖点、人群", body: "上传产品图，补充价格、目标人群、使用场景、竞品差异和禁用表达。" },
      { lane: "angle", type: "note", title: "3组卖点脚本", output: "痛点型/对比型/场景型", body: "每个 SKU 至少拆 3 个广告角度：痛点解决、前后对比、生活场景。" },
      { lane: "creative", type: "prompt", profileId: "tikpan-gpt-image-2-edit", title: "产品场景图", output: "产品融入生活场景", prompt: "把选中的产品图融入真实生活使用场景，保持产品外观一致，背景高级干净，适合 TikTok 广告。" },
      { lane: "creative", type: "prompt", profileId: "tikpan-veo-video", title: "产品短视频", output: "3-8秒镜头", prompt: "根据产品场景图生成 TikTok 广告短镜头：开头吸引注意，动作自然，突出产品功能和质感。" },
      { lane: "test", type: "note", title: "A/B 测试矩阵", output: "标题、封面、脚本、受众", body: "每个产品至少测试 3 个标题、2 个封面、3 个脚本角度，记录 CTR、完播、转化。" },
    ],
  },
];

function buildContentFactoryPlan(templateId, brief = "") {
  const template = contentFactoryWorkflows.find((item) => item.id === templateId) || contentFactoryWorkflows[0];
  const laneY = new Map();
  const nodes = template.steps.map((step, index) => {
    const lane = template.lanes.find((item) => item.key === step.lane) || template.lanes[0];
    const y = (laneY.get(lane.key) || -220);
    laneY.set(lane.key, y + (step.type === "prompt" ? 260 : 210));
    const base = {
      id: `factory-${template.id}-${index + 1}`,
      type: step.type,
      x: lane.x,
      y,
      width: step.type === "prompt" ? 330 : 340,
      height: step.type === "prompt" ? 228 : 170,
      title: step.title,
      factory: {
        templateId: template.id,
        lane: step.lane,
        output: step.output,
      },
    };
    if (step.type === "prompt") {
      return {
        ...base,
        profileId: step.profileId || template.defaultProfileId,
        text: `${step.prompt}\n\n项目Brief：${brief || "在这里补充剧情/产品/目标受众。"}`,
      };
    }
    return {
      ...base,
      body: `${step.body}\n\n项目Brief：${brief || "在这里补充剧情/产品/目标受众。"}`,
    };
  });
  return {
    ok: true,
    workflow: template,
    nodes,
    checklist: template.steps.map((step, index) => ({
      id: `${template.id}-${index + 1}`,
      title: step.title,
      output: step.output,
      status: "todo",
    })),
  };
}

function ensurePlatformConfigFile() {
  if (!fs.existsSync(platformConfigFile)) {
    fs.writeFileSync(platformConfigFile, JSON.stringify(defaultPlatformConfig, null, 2), "utf8");
  }
}

function readPlatformConfig() {
  ensurePlatformConfigFile();
  const parsed = JSON.parse(fs.readFileSync(platformConfigFile, "utf8"));
  return {
    ...defaultPlatformConfig,
    ...parsed,
    settings: { ...defaultPlatformConfig.settings, ...(parsed.settings || {}) },
  };
}

function writePlatformConfig(config) {
  const next = {
    channels: Array.isArray(config.channels) ? config.channels : [],
    routes: Array.isArray(config.routes) ? config.routes : [],
    pricing: Array.isArray(config.pricing) ? config.pricing : [],
    settings: { ...defaultPlatformConfig.settings, ...(config.settings || {}) },
  };
  fs.writeFileSync(platformConfigFile, JSON.stringify(next, null, 2), "utf8");
  return next;
}

function readProfiles() {
  ensureProfilesFile();
  const profiles = JSON.parse(fs.readFileSync(profilesFile, "utf8"));
  return Array.isArray(profiles) ? profiles : [];
}

function writeProfiles(profiles) {
  fs.writeFileSync(profilesFile, JSON.stringify(profiles, null, 2), "utf8");
}

function sendJson(res, status, payload) {
  const body = JSON.stringify(payload, null, 2);
  res.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store",
  });
  res.end(body);
}

function sendText(res, status, text) {
  res.writeHead(status, { "content-type": "text/plain; charset=utf-8" });
  res.end(text);
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let body = "";
    req.on("data", (chunk) => {
      body += chunk;
      if (body.length > 35 * 1024 * 1024) {
        reject(new Error("Request body is too large."));
        req.destroy();
      }
    });
    req.on("end", () => resolve(body));
    req.on("error", reject);
  });
}

function safeName(name, fallback = "canvas-project") {
  return String(name || fallback)
    .trim()
    .replace(/[^\w.-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80) || fallback;
}

function bearerToken(req) {
  const auth = req.headers.authorization || "";
  return auth.startsWith("Bearer ") ? auth.slice(7).trim() : "";
}

function userProjectDir(user) {
  const key = safeName(user?.id || user?.email || user?.username || "guest", "guest");
  const dir = path.join(projectsDir, key);
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

function userAssetDir(user) {
  const key = safeName(user?.id || user?.email || user?.username || "guest", "guest");
  const dir = path.join(assetsDir, key);
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

function normalizeAsset(asset = {}) {
  const now = new Date().toISOString();
  return {
    id: safeName(asset.id || crypto.randomUUID(), "asset"),
    type: asset.type || "image",
    title: String(asset.title || "Untitled asset").slice(0, 160),
    src: asset.src || "",
    width: Number(asset.width || 0),
    height: Number(asset.height || 0),
    projectName: String(asset.projectName || "").slice(0, 160),
    profileId: String(asset.profileId || "").slice(0, 160),
    nodeId: String(asset.nodeId || "").slice(0, 160),
    createdAt: asset.createdAt || now,
    updatedAt: now,
  };
}

async function fetchWebAppJson(route, options = {}) {
  if (!webAppBase) throw new Error("WEB_APP_URL is not configured.");
  const target = new URL(route, webAppBase);
  const response = await fetch(target, options);
  const bodyText = await response.text();
  let data = {};
  try {
    data = bodyText ? JSON.parse(bodyText) : {};
  } catch {
    data = { error: bodyText || response.statusText };
  }
  if (!response.ok) {
    throw new Error(data.error || data.message || `WEB_APP ${response.status}`);
  }
  return data;
}

async function resolveUser(req) {
  const token = bearerToken(req);
  if (webAppBase && token) {
    const data = await fetchWebAppJson("/api/user/info", {
      headers: { Authorization: `Bearer ${token}` },
    });
    const user = data.user || {};
    return {
      authenticated: true,
      token,
      id: user.id || user.username || "web-user",
      email: user.username || user.email || "",
      username: user.username || user.email || "",
      nickname: user.nickname || user.username || "已登录用户",
      balance: user.balance ?? 0,
      role: user.role || "user",
      source: "web_app",
    };
  }
  return {
    authenticated: false,
    id: "guest",
    nickname: "访客",
    balance: null,
    role: "guest",
    source: webAppBase ? "web_app" : "standalone",
  };
}

async function requireUser(req) {
  const user = await resolveUser(req);
  if (requireLogin && !user.authenticated) {
    const error = new Error("请先登录后再生成或保存项目。");
    error.status = 401;
    throw error;
  }
  return user;
}

function findProfile(profileId) {
  const profiles = readProfiles();
  return profiles.find((profile) => profile.id === profileId) || profiles[0];
}

function profileDefaults(profile) {
  const defaults = { ...(profile?.parameters || {}) };
  for (const field of profile?.fields || []) {
    if (defaults[field.key] === undefined && field.default !== undefined) {
      defaults[field.key] = field.default;
    }
  }
  return defaults;
}

function normalizeBoolean(value) {
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return Boolean(value);
  return ["true", "1", "yes", "on"].includes(String(value).toLowerCase());
}

function buildGenerationRequest(settings) {
  const profile = findProfile(settings.profileId);
  if (!profile) throw new Error("No model profiles are configured.");

  const base = profileDefaults(profile);
  const fieldValues = settings.fields || {};
  const seed = settings.seed === undefined || settings.seed === ""
    ? Math.floor(Math.random() * 2 ** 32)
    : Number(settings.seed);

  const legacySdxl = {
    checkpoint: settings.checkpoint,
    negative: settings.negative,
    width: settings.width,
    height: settings.height,
    steps: settings.steps,
    cfg: settings.cfg,
    sampler: settings.sampler,
    scheduler: settings.scheduler,
    denoise: settings.denoise,
    batchSize: settings.batchSize,
  };

  const parameters = { ...base, ...legacySdxl, ...fieldValues };
  for (const field of profile.fields || []) {
    if (field.type === "number" && parameters[field.key] !== undefined && parameters[field.key] !== "") {
      parameters[field.key] = Number(parameters[field.key]);
    }
    if (field.type === "checkbox") {
      parameters[field.key] = normalizeBoolean(parameters[field.key]);
    }
  }

  return {
    provider: settings.provider || providerMode,
    task: profile.task || "text-to-image",
    profileId: profile.id,
    profileName: profile.name,
    engine: profile.engine || "comfy_sdxl",
    mediaType: profile.mediaType || "image",
    profile,
    parameters: {
      ...parameters,
      prompt: settings.prompt || "",
      seed,
      prefix: settings.prefix || safeName(profile.id || "canvas"),
    },
    canvas: settings.canvas || {},
    canvasImages: Array.isArray(settings.canvasImages) ? settings.canvasImages : [],
    meta: {
      clientId,
      createdAt: new Date().toISOString(),
      note: "Canvas request shaped from a model profile. Tikpan node profiles can run through local ComfyUI or be sent to an upstream website API.",
    },
  };
}

async function comfyFetch(route, options = {}) {
  const target = new URL(route, comfyBase);
  const response = await fetch(target, {
    ...options,
    headers: options.body instanceof FormData
      ? { ...(options.headers || {}) }
      : {
          "content-type": "application/json",
          ...(options.headers || {}),
        },
  });
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(`ComfyUI ${response.status}: ${text || response.statusText}`);
  }
  return response;
}

function buildTextToImageWorkflow(request) {
  const p = request.parameters;
  return {
    "1": {
      class_type: "CheckpointLoaderSimple",
      inputs: { ckpt_name: p.checkpoint },
    },
    "2": {
      class_type: "CLIPTextEncode",
      inputs: { text: p.prompt, clip: ["1", 1] },
    },
    "3": {
      class_type: "CLIPTextEncode",
      inputs: { text: p.negative || "", clip: ["1", 1] },
    },
    "4": {
      class_type: "EmptyLatentImage",
      inputs: {
        width: Number(p.width || 1024),
        height: Number(p.height || 1024),
        batch_size: Number(p.batchSize || 1),
      },
    },
    "5": {
      class_type: "KSampler",
      inputs: {
        seed: Number(p.seed || 0),
        steps: Number(p.steps || 24),
        cfg: Number(p.cfg || 7),
        sampler_name: p.sampler || "euler",
        scheduler: p.scheduler || "normal",
        denoise: Number(p.denoise || 1),
        model: ["1", 0],
        positive: ["2", 0],
        negative: ["3", 0],
        latent_image: ["4", 0],
      },
    },
    "6": {
      class_type: "VAEDecode",
      inputs: { samples: ["5", 0], vae: ["1", 2] },
    },
    "7": {
      class_type: "SaveImage",
      inputs: { filename_prefix: p.prefix || "infinite_canvas", images: ["6", 0] },
    },
  };
}

function imageUrlToBytes(src) {
  if (!src) throw new Error("Missing image src.");
  if (src.startsWith("data:image/")) {
    const match = src.match(/^data:(image\/[a-zA-Z0-9.+-]+);base64,(.*)$/s);
    if (!match) throw new Error("Invalid data URL image.");
    const ext = match[1].split("/")[1].replace("jpeg", "jpg");
    return {
      buffer: Buffer.from(match[2], "base64"),
      mime: match[1],
      ext,
    };
  }
  return null;
}

async function imageSrcToDataUrl(src) {
  const local = imageUrlToBytes(src);
  if (local) {
    return `data:${local.mime};base64,${local.buffer.toString("base64")}`;
  }

  const target = src.startsWith("/")
    ? new URL(src, `http://127.0.0.1:${port}`)
    : new URL(src);
  const response = await fetch(target);
  if (!response.ok) {
    throw new Error(`Failed to read canvas image ${response.status}`);
  }
  const mime = response.headers.get("content-type") || "image/jpeg";
  const buffer = Buffer.from(await response.arrayBuffer());
  return `data:${mime};base64,${buffer.toString("base64")}`;
}

async function uploadImageToComfy(image, index) {
  let source = image?.src || "";
  let parsed = imageUrlToBytes(source);

  if (!parsed) {
    const target = source.startsWith("/")
      ? new URL(source, `http://127.0.0.1:${port}`)
      : new URL(source);
    const response = await fetch(target);
    if (!response.ok) {
      throw new Error(`Failed to fetch canvas image for ComfyUI upload: ${response.status}`);
    }
    const mime = response.headers.get("content-type") || "image/jpeg";
    const ext = mime.split("/")[1]?.replace("jpeg", "jpg") || "jpg";
    parsed = {
      buffer: Buffer.from(await response.arrayBuffer()),
      mime,
      ext,
    };
  }

  const filename = `${safeName(image?.title || image?.id || "canvas-image")}-${index}.${parsed.ext}`;
  const form = new FormData();
  form.append("image", new Blob([parsed.buffer], { type: parsed.mime }), filename);
  form.append("type", "input");
  form.append("overwrite", "true");

  const response = await comfyFetch("/upload/image", { method: "POST", body: form });
  const uploaded = await response.json();
  return uploaded.subfolder ? `${uploaded.subfolder}/${uploaded.name}` : uploaded.name;
}

function orderCanvasImages(request, requiredFirst) {
  const images = request.canvasImages.filter((item) => item?.src);
  const selectedId = request.canvas?.selectedNodeId;
  const selected = images.find((item) => item.id === selectedId);
  const rest = images.filter((item) => item.id !== selectedId);
  if (requiredFirst && selected) return [selected, ...rest];
  return selected ? [selected, ...rest] : images;
}

async function buildTikpanNodeWorkflow(request, { previewOnly = false } = {}) {
  const profile = request.profile;
  const node = profile.node || {};
  if (!node.classType) throw new Error(`Profile ${profile.id} is missing node.classType.`);

  const inputs = {
    ...(node.hiddenInputs || {}),
    ...request.parameters,
  };

  if (node.promptInput) {
    inputs[node.promptInput] = request.parameters.prompt || inputs[node.promptInput] || "";
  }
  if (node.seedInput) {
    inputs[node.seedInput] = Number(request.parameters.seed || 0);
  }
  if (node.apiKeyInput) {
    const key = process.env[profile.credentialEnv || "TIKPAN_API_KEY"] || tikpanApiKey || "";
    inputs[node.apiKeyInput] = key || "sk-";
    if (!key && !previewOnly) {
      throw new Error(`Please set ${profile.credentialEnv || "TIKPAN_API_KEY"} before running ${profile.name}.`);
    }
  }

  delete inputs.fields;
  delete inputs.checkpoint;
  delete inputs.negative;
  delete inputs.width;
  delete inputs.height;
  delete inputs.steps;
  delete inputs.cfg;
  delete inputs.sampler;
  delete inputs.scheduler;
  delete inputs.denoise;
  delete inputs.batchSize;
  delete inputs.prefix;
  delete inputs.prompt;

  const workflow = {
    "1": {
      class_type: node.classType,
      inputs,
    },
  };

  let nextId = 2;
  const orderedImages = orderCanvasImages(request, Boolean(node.requiredImageInput));

  if (node.requiredImageInput) {
    if (!orderedImages[0] && !previewOnly) {
      throw new Error(`${profile.name} needs a selected canvas image as ${node.requiredImageInput}.`);
    }
    if (orderedImages[0]) {
      const imageName = previewOnly ? `<selected image: ${orderedImages[0].title || orderedImages[0].id}>` : await uploadImageToComfy(orderedImages[0], nextId);
      workflow[String(nextId)] = { class_type: "LoadImage", inputs: { image: imageName } };
      workflow["1"].inputs[node.requiredImageInput] = [String(nextId), 0];
      nextId += 1;
    }
  }

  const referenceStart = node.requiredImageInput ? 1 : 0;
  const referenceImages = orderedImages.slice(referenceStart);
  if (Array.isArray(node.referenceImageInputs) && node.referenceImageInputs.length) {
    for (let i = 0; i < Math.min(referenceImages.length, node.referenceImageInputs.length); i += 1) {
      const imageName = previewOnly ? `<canvas image: ${referenceImages[i].title || referenceImages[i].id}>` : await uploadImageToComfy(referenceImages[i], nextId);
      workflow[String(nextId)] = { class_type: "LoadImage", inputs: { image: imageName } };
      workflow["1"].inputs[node.referenceImageInputs[i]] = [String(nextId), 0];
      nextId += 1;
    }
  }

  if (node.dataUrlListInput && referenceImages.length) {
    const limited = referenceImages.slice(0, Number(node.maxCanvasImages || 14));
    workflow["1"].inputs[node.dataUrlListInput] = previewOnly
      ? limited.map((img) => `<canvas image: ${img.title || img.id}>`).join("\n")
      : (await Promise.all(limited.map((img) => imageSrcToDataUrl(img.src)))).join("\n");
  }

  if (node.saveImage) {
    workflow[String(nextId)] = {
      class_type: "SaveImage",
      inputs: {
        filename_prefix: request.parameters.prefix || safeName(profile.id),
        images: ["1", 0],
      },
    };
  }

  return workflow;
}

async function buildWorkflow(request, options = {}) {
  if (request.engine === "tikpan_node") {
    return buildTikpanNodeWorkflow(request, options);
  }
  return buildTextToImageWorkflow(request);
}

function mediaFromComfyItem(item) {
  if (!item || typeof item !== "object" || !item.filename) return null;
  const params = new URLSearchParams({
    filename: item.filename,
    subfolder: item.subfolder || "",
    type: item.type || "output",
  });
  return {
    filename: item.filename,
    subfolder: item.subfolder || "",
    type: item.type || "output",
    url: `/api/comfy/view?${params.toString()}`,
  };
}

async function waitForComfyOutputs(promptId, timeoutMs = 900000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const response = await comfyFetch(`/history/${encodeURIComponent(promptId)}`);
    const history = await response.json();
    const entry = history[promptId];
    if (entry?.outputs) {
      const images = [];
      const media = [];
      for (const output of Object.values(entry.outputs)) {
        for (const image of output.images || []) {
          const item = mediaFromComfyItem(image);
          if (item) images.push(item);
        }
        for (const video of output.videos || output.gifs || []) {
          const item = mediaFromComfyItem(video);
          if (item) media.push({ ...item, kind: "video" });
        }
        for (const audio of output.audio || output.audios || []) {
          const item = mediaFromComfyItem(audio);
          if (item) media.push({ ...item, kind: "audio" });
        }
      }
      if (images.length || media.length) return { images, media, rawOutputs: entry.outputs };
      return { images, media, rawOutputs: entry.outputs };
    }
    await new Promise((resolve) => setTimeout(resolve, 1200));
  }
  throw new Error("Timed out waiting for ComfyUI generation.");
}

async function generateWithComfy(request) {
  if (request.engine === "comfy_sdxl" && !request.parameters.checkpoint) {
    throw new Error("Please select a checkpoint first.");
  }
  const workflow = await buildWorkflow(request);
  const queued = await comfyFetch("/prompt", {
    method: "POST",
    body: JSON.stringify({ prompt: workflow, client_id: clientId }),
  });
  const queuedJson = await queued.json();
  const promptId = queuedJson.prompt_id;
  const outputs = await waitForComfyOutputs(promptId, Number(request.timeoutMs || 900000));
  return {
    ok: true,
    provider: "comfy",
    promptId,
    requestId: promptId,
    images: outputs.images,
    media: outputs.media,
    rawOutputs: outputs.rawOutputs,
    seed: request.parameters.seed,
  };
}

async function generateWithUpstream(request) {
  if (!upstreamBase) {
    throw new Error("UPSTREAM_URL is not configured.");
  }
  const target = new URL("/generate", upstreamBase);
  const headers = { "content-type": "application/json" };
  if (upstreamToken) headers.authorization = `Bearer ${upstreamToken}`;
  const response = await fetch(target, {
    method: "POST",
    headers,
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(`Upstream ${response.status}: ${text || response.statusText}`);
  }
  const result = await response.json();
  return {
    ok: true,
    provider: "upstream",
    requestId: result.requestId || result.id || crypto.randomUUID(),
    images: Array.isArray(result.images) ? result.images : [],
    media: Array.isArray(result.media) ? result.media : [],
    seed: result.seed || request.parameters.seed,
    raw: result,
  };
}

async function handleApi(req, res, url) {
  if (url.pathname === "/api/health") {
    sendJson(res, 200, {
      ok: true,
      provider: providerMode,
      comfyBase,
      upstreamConfigured: Boolean(upstreamBase),
      tikpanKeyConfigured: Boolean(tikpanApiKey),
      webAppConfigured: Boolean(webAppBase),
      requireLogin,
      clientId,
    });
    return;
  }

  if (url.pathname === "/api/provider") {
    sendJson(res, 200, {
      ok: true,
      provider: providerMode,
      options: ["comfy", "upstream"],
      comfyBase,
      upstreamConfigured: Boolean(upstreamBase),
      tikpanKeyConfigured: Boolean(tikpanApiKey),
      webAppConfigured: Boolean(webAppBase),
      requireLogin,
    });
    return;
  }

  if (url.pathname === "/api/session" && req.method === "GET") {
    const user = await resolveUser(req);
    sendJson(res, 200, {
      ok: true,
      authenticated: user.authenticated,
      user: {
        id: user.id,
        email: user.email,
        username: user.username,
        nickname: user.nickname,
        balance: user.balance,
        role: user.role,
        source: user.source,
      },
      auth: {
        webAppConfigured: Boolean(webAppBase),
        requireLogin,
      },
    });
    return;
  }

  if (url.pathname === "/api/auth/login" && req.method === "POST") {
    if (!webAppBase) {
      sendJson(res, 400, { ok: false, error: "WEB_APP_URL 未配置，当前只能以访客模式使用。" });
      return;
    }
    const payload = JSON.parse(await readBody(req) || "{}");
    const data = await fetchWebAppJson("/api/login", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ email: payload.email, password: payload.password }),
    });
    sendJson(res, 200, { ok: true, token: data.token, user: data.user });
    return;
  }

  if (url.pathname === "/api/auth/register" && req.method === "POST") {
    if (!webAppBase) {
      sendJson(res, 400, { ok: false, error: "WEB_APP_URL 未配置，当前只能以访客模式使用。" });
      return;
    }
    const payload = JSON.parse(await readBody(req) || "{}");
    const data = await fetchWebAppJson("/api/register", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
    sendJson(res, 200, { ok: true, token: data.token, user: data.user || { email: payload.email } });
    return;
  }

  if (url.pathname === "/api/auth/send-code" && req.method === "POST") {
    if (!webAppBase) {
      sendJson(res, 400, { ok: false, error: "WEB_APP_URL 未配置，无法发送验证码。" });
      return;
    }
    const payload = JSON.parse(await readBody(req) || "{}");
    const data = await fetchWebAppJson("/api/send-code", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
    sendJson(res, 200, { ok: true, ...data });
    return;
  }

  if (url.pathname === "/api/profiles" && req.method === "GET") {
    sendJson(res, 200, { ok: true, profiles: readProfiles() });
    return;
  }

  if (url.pathname === "/api/admin/config" && req.method === "GET") {
    sendJson(res, 200, {
      ok: true,
      config: readPlatformConfig(),
      profiles: readProfiles().map((profile) => ({
        id: profile.id,
        name: profile.name,
        group: profile.group,
        engine: profile.engine,
        mediaType: profile.mediaType,
      })),
    });
    return;
  }

  if (url.pathname === "/api/admin/config" && req.method === "POST") {
    const payload = JSON.parse(await readBody(req) || "{}");
    const config = writePlatformConfig(payload.config || {});
    sendJson(res, 200, { ok: true, config });
    return;
  }

  if (url.pathname === "/api/content-factory/workflows" && req.method === "GET") {
    sendJson(res, 200, {
      ok: true,
      workflows: contentFactoryWorkflows,
    });
    return;
  }

  if (url.pathname === "/api/content-factory/plan" && req.method === "POST") {
    const payload = JSON.parse(await readBody(req) || "{}");
    sendJson(res, 200, buildContentFactoryPlan(payload.workflowId, payload.brief || ""));
    return;
  }

  if (url.pathname === "/api/profiles" && req.method === "POST") {
    const payload = JSON.parse(await readBody(req) || "{}");
    const profiles = readProfiles();
    const source = findProfile(payload.baseProfileId || payload.id) || {};
    const id = safeName(payload.id || payload.name, "model-profile").toLowerCase();
    const profile = {
      ...source,
      id,
      name: payload.name || id,
      description: payload.description || source.description || "Saved from the canvas parameter panel.",
      parameters: payload.parameters || source.parameters || {},
      fields: source.fields || payload.fields || [],
    };
    const index = profiles.findIndex((item) => item.id === id);
    if (index >= 0) profiles[index] = profile;
    else profiles.push(profile);
    writeProfiles(profiles);
    sendJson(res, 200, { ok: true, profile, profiles });
    return;
  }

  if (url.pathname === "/api/comfy/status") {
    const response = await comfyFetch("/system_stats");
    sendJson(res, 200, { ok: true, comfyBase, stats: await response.json() });
    return;
  }

  if (url.pathname === "/api/comfy/checkpoints") {
    const response = await comfyFetch("/object_info/CheckpointLoaderSimple");
    const info = await response.json();
    const checkpoints = info?.CheckpointLoaderSimple?.input?.required?.ckpt_name?.[0] || [];
    sendJson(res, 200, { ok: true, checkpoints });
    return;
  }

  if (url.pathname === "/api/comfy/view") {
    const params = url.searchParams;
    const response = await comfyFetch(`/view?${params.toString()}`, { headers: {} });
    const contentType = response.headers.get("content-type") || "application/octet-stream";
    res.writeHead(200, {
      "content-type": contentType,
      "cache-control": "no-store",
    });
    res.end(Buffer.from(await response.arrayBuffer()));
    return;
  }

  if (url.pathname === "/api/request/preview" && req.method === "POST") {
    const payload = JSON.parse(await readBody(req) || "{}");
    const request = buildGenerationRequest(payload);
    const workflow = request.provider === "comfy" ? await buildWorkflow(request, { previewOnly: true }) : null;
    sendJson(res, 200, {
      ok: true,
      provider: request.provider,
      request: {
        ...request,
        profile: undefined,
        canvasImages: request.canvasImages.map((img) => ({ id: img.id, title: img.title, type: img.type })),
      },
      comfyWorkflow: workflow,
    });
    return;
  }

  if ((url.pathname === "/api/generate" || url.pathname === "/api/comfy/generate") && req.method === "POST") {
    await requireUser(req);
    const payload = JSON.parse(await readBody(req) || "{}");
    const request = buildGenerationRequest(payload);
    const result = request.provider === "upstream"
      ? await generateWithUpstream(request)
      : await generateWithComfy(request);
    sendJson(res, 200, {
      ...result,
      request: { ...request, profile: undefined },
    });
    return;
  }

  if (url.pathname === "/api/projects" && req.method === "GET") {
    const user = await requireUser(req);
    const dir = userProjectDir(user);
    const projects = fs.readdirSync(dir)
      .filter((file) => file.endsWith(".json"))
      .map((file) => file.replace(/\.json$/, ""));
    sendJson(res, 200, { ok: true, projects });
    return;
  }

  if (url.pathname === "/api/projects" && req.method === "POST") {
    const user = await requireUser(req);
    const payload = JSON.parse(await readBody(req) || "{}");
    const name = safeName(payload.name || payload.project?.name || payload.project?.title);
    const file = path.join(userProjectDir(user), `${name}.json`);
    const project = {
      ...(payload.project || {}),
      name,
      title: payload.project?.title || payload.title || name,
      updatedAt: new Date().toISOString(),
    };
    fs.writeFileSync(file, JSON.stringify(project, null, 2), "utf8");
    sendJson(res, 200, { ok: true, name, project });
    return;
  }

  if (url.pathname.startsWith("/api/projects/") && req.method === "GET") {
    const user = await requireUser(req);
    const name = safeName(decodeURIComponent(url.pathname.slice("/api/projects/".length)));
    const file = path.join(userProjectDir(user), `${name}.json`);
    if (!fs.existsSync(file)) {
      sendJson(res, 404, { ok: false, error: "Project not found." });
      return;
    }
    sendJson(res, 200, { ok: true, name, project: JSON.parse(fs.readFileSync(file, "utf8")) });
    return;
  }

  if (url.pathname === "/api/assets" && req.method === "GET") {
    const user = await requireUser(req);
    const dir = userAssetDir(user);
    const assets = fs.readdirSync(dir)
      .filter((file) => file.endsWith(".json"))
      .map((file) => JSON.parse(fs.readFileSync(path.join(dir, file), "utf8")))
      .sort((a, b) => String(b.updatedAt || b.createdAt || "").localeCompare(String(a.updatedAt || a.createdAt || "")));
    sendJson(res, 200, { ok: true, assets });
    return;
  }

  if (url.pathname === "/api/assets" && req.method === "POST") {
    const user = await requireUser(req);
    const payload = JSON.parse(await readBody(req) || "{}");
    const assets = Array.isArray(payload.assets) ? payload.assets : [payload.asset || payload];
    const saved = assets
      .filter((asset) => asset && asset.src)
      .map((asset) => {
        const normalized = normalizeAsset(asset);
        const file = path.join(userAssetDir(user), `${normalized.id}.json`);
        fs.writeFileSync(file, JSON.stringify(normalized, null, 2), "utf8");
        return normalized;
      });
    sendJson(res, 200, { ok: true, assets: saved });
    return;
  }

  sendJson(res, 404, { ok: false, error: "Unknown API route." });
}

function serveStatic(req, res, url) {
  const requested = url.pathname === "/" ? "/index.html" : decodeURIComponent(url.pathname);
  const normalized = path.normalize(requested).replace(/^(\.\.[/\\])+/, "");
  const file = path.join(publicDir, normalized);
  if (!file.startsWith(publicDir) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
    sendText(res, 404, "Not found");
    return;
  }
  const ext = path.extname(file).toLowerCase();
  res.writeHead(200, {
    "content-type": mimeTypes.get(ext) || "application/octet-stream",
    "cache-control": "no-store",
  });
  fs.createReadStream(file).pipe(res);
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host || "localhost"}`);
  try {
    if (url.pathname.startsWith("/api/")) {
      await handleApi(req, res, url);
      return;
    }
    serveStatic(req, res, url);
  } catch (error) {
    sendJson(res, error.status || 500, { ok: false, error: error.message, stack: String(error.stack || "").split("\n").slice(0, 5) });
  }
});

ensureProfilesFile();
ensurePlatformConfigFile();
server.listen(port, () => {
  console.log(`Infinite Canvas for ComfyUI running at http://127.0.0.1:${port}`);
  console.log(`Provider mode: ${providerMode}`);
  console.log(`ComfyUI target: ${comfyBase}`);
  console.log(`Tikpan key configured: ${Boolean(tikpanApiKey)}`);
  console.log(`Web app auth bridge: ${webAppBase || "disabled"} | require login: ${requireLogin}`);
  if (upstreamBase) console.log(`Upstream target: ${upstreamBase}`);
});
