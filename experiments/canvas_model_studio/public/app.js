const canvas = document.getElementById("canvas");
const world = document.getElementById("world");
const zoomLabel = document.getElementById("zoomLabel");
const connectionLabel = document.getElementById("connectionLabel");
const statusText = document.getElementById("statusText");
const promptTemplate = document.getElementById("promptTemplate");
const welcomeOverlay = document.getElementById("welcomeOverlay");
const welcomeStartButton = document.getElementById("welcomeStartButton");
const canvasEmptyHint = document.getElementById("canvasEmptyHint");
const launcher = document.getElementById("launcher");
const launcherCloseButton = document.getElementById("launcherCloseButton");
const launcherSearch = document.getElementById("launcherSearch");
const launcherList = document.getElementById("launcherList");
const projectTitleInput = document.getElementById("projectTitleInput");
const themeSelect = document.getElementById("themeSelect");
const assetList = document.getElementById("assetList");
const factoryWorkflowSelect = document.getElementById("factoryWorkflowSelect");
const factoryBriefInput = document.getElementById("factoryBriefInput");
const factorySummary = document.getElementById("factorySummary");
const buildFactoryButton = document.getElementById("buildFactoryButton");
const zoomRange = document.getElementById("zoomRange");
const userSummary = document.getElementById("userSummary");
const loginButton = document.getElementById("loginButton");
const logoutButton = document.getElementById("logoutButton");
const authModal = document.getElementById("authModal");
const authCloseButton = document.getElementById("authCloseButton");
const authLoginTab = document.getElementById("authLoginTab");
const authRegisterTab = document.getElementById("authRegisterTab");
const authEmail = document.getElementById("authEmail");
const authPassword = document.getElementById("authPassword");
const authCode = document.getElementById("authCode");
const authCodeField = document.getElementById("authCodeField");
const sendCodeButton = document.getElementById("sendCodeButton");
const authSubmitButton = document.getElementById("authSubmitButton");
const authMessage = document.getElementById("authMessage");

const providerBadge = document.getElementById("providerBadge");
const providerHint = document.getElementById("providerHint");
const profileSelect = document.getElementById("profileSelect");
const profileNameInput = document.getElementById("profileNameInput");
const profileHint = document.getElementById("profileHint");
const profileSummary = document.getElementById("profileSummary");
const checkpointField = document.getElementById("checkpointField");
const checkpointSelect = document.getElementById("checkpointSelect");
const promptInput = document.getElementById("promptInput");
const negativeInput = document.getElementById("negativeInput");
const sdxlFields = document.getElementById("sdxlFields");
const dynamicFields = document.getElementById("dynamicFields");
const referenceHint = document.getElementById("referenceHint");
const widthInput = document.getElementById("widthInput");
const heightInput = document.getElementById("heightInput");
const stepsInput = document.getElementById("stepsInput");
const cfgInput = document.getElementById("cfgInput");
const samplerInput = document.getElementById("samplerInput");
const schedulerInput = document.getElementById("schedulerInput");
const denoiseInput = document.getElementById("denoiseInput");
const batchSizeInput = document.getElementById("batchSizeInput");
const seedInput = document.getElementById("seedInput");
const projectNameInput = document.getElementById("projectNameInput");
const requestPreview = document.getElementById("requestPreview");

const state = {
  camera: { x: 520, y: 260, scale: 0.78 },
  nodes: [],
  selectedId: null,
  nextId: 1,
  provider: "comfy",
  profiles: [],
  session: null,
  authMode: "login",
  launcherPoint: { x: 0, y: 0 },
  projectName: "Untitled Canvas",
  theme: localStorage.getItem("canvasTheme") || "system",
  assets: [],
  factoryWorkflows: [],
};

let drag = null;

function setStatus(text) {
  statusText.textContent = text;
}

function applyTheme(mode = "system") {
  const nextMode = ["dark", "light", "system"].includes(mode) ? mode : "system";
  state.theme = nextMode;
  document.documentElement.dataset.theme = nextMode;
  if (themeSelect) themeSelect.value = nextMode;
  localStorage.setItem("canvasTheme", nextMode);
}

function setProjectName(value, options = {}) {
  const nextName = String(value || "Untitled Canvas").trim() || "Untitled Canvas";
  state.projectName = nextName;
  if (projectNameInput && projectNameInput.value !== nextName) projectNameInput.value = nextName;
  if (projectTitleInput && projectTitleInput.value !== nextName) projectTitleInput.value = nextName;
  if (options.persist !== false) persistLocal();
}

function authToken() {
  return localStorage.getItem("tikpan_token") || "";
}

function setAuthToken(token) {
  if (token) localStorage.setItem("tikpan_token", token);
  else localStorage.removeItem("tikpan_token");
}

async function authedFetch(url, options = {}) {
  const headers = new Headers(options.headers || {});
  const token = authToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return fetch(url, { ...options, headers });
}

async function refreshSession() {
  try {
    const response = await authedFetch("/api/session");
    const data = await response.json();
    state.session = data;
    const user = data.user || {};
    const name = data.authenticated ? (user.nickname || user.username || "已登录用户") : "访客模式";
    const balance = data.authenticated && user.balance !== null && user.balance !== undefined
      ? `余额 ${user.balance} 额度`
      : (data.auth?.webAppConfigured ? "未登录，生成可能受限" : "本地独立模式");
    userSummary.innerHTML = `
      <strong>${name}</strong>
      <span>${balance}</span>
    `;
    loginButton.hidden = Boolean(data.authenticated);
    logoutButton.hidden = !data.authenticated;
    return data;
  } catch (error) {
    userSummary.innerHTML = `<strong>用户状态异常</strong><span>${error.message}</span>`;
    return null;
  }
}

function openAuth(mode = "login") {
  state.authMode = mode;
  authModal.classList.add("open");
  authLoginTab.classList.toggle("active", mode === "login");
  authRegisterTab.classList.toggle("active", mode === "register");
  authCodeField.hidden = mode !== "register";
  authSubmitButton.textContent = mode === "login" ? "登录" : "注册并登录";
  authMessage.textContent = "";
}

function closeAuth() {
  authModal.classList.remove("open");
}

function activeProfile() {
  return state.profiles.find((profile) => profile.id === profileSelect.value);
}

function isSdxlProfile(profile = activeProfile()) {
  return (profile?.engine || "comfy_sdxl") === "comfy_sdxl";
}

function renderCamera() {
  world.style.transform = `translate(${state.camera.x}px, ${state.camera.y}px) scale(${state.camera.scale})`;
  zoomLabel.textContent = `${Math.round(state.camera.scale * 100)}%`;
  if (zoomRange) zoomRange.value = String(Math.round(state.camera.scale * 100));
}

function screenToWorld(clientX, clientY) {
  const rect = canvas.getBoundingClientRect();
  return {
    x: (clientX - rect.left - state.camera.x) / state.camera.scale,
    y: (clientY - rect.top - state.camera.y) / state.camera.scale,
  };
}

function selectNode(id) {
  state.selectedId = id;
  for (const element of world.querySelectorAll(".node")) {
    element.classList.toggle("selected", element.dataset.id === id);
  }
  const node = state.nodes.find((item) => item.id === id);
  if (node?.type === "prompt") {
    promptInput.value = node.text;
    if (node.profileId && profileSelect.value !== node.profileId) {
      profileSelect.value = node.profileId;
      applyProfile(activeProfile());
    }
  }
  updateReferenceHint();
}

function updateEmptyHint() {
  if (canvasEmptyHint) canvasEmptyHint.hidden = state.nodes.length > 0;
}

function createNodeElement(node) {
  let element;
  if (node.type === "note") {
    element = document.createElement("article");
    element.className = "node note-node";
    const header = document.createElement("header");
    const title = document.createElement("strong");
    title.textContent = node.title || "Note";
    const lane = document.createElement("span");
    lane.textContent = node.factory?.lane || "workflow";
    const body = document.createElement("div");
    body.className = "note-body";
    body.textContent = node.body || "";
    if (node.factory?.output) {
      const output = document.createElement("span");
      output.className = "note-output";
      output.textContent = `输出物：${node.factory.output}`;
      body.appendChild(output);
    }
    header.append(title, lane);
    element.append(header, body);
  } else if (node.type === "prompt") {
    element = promptTemplate.content.firstElementChild.cloneNode(true);
    const profile = state.profiles.find((item) => item.id === node.profileId);
    element.querySelector("strong").textContent = profile?.name || "Prompt";
    if (node.title) element.querySelector("span").textContent = node.title;
    element.querySelector("span").textContent = profile?.group || "模型节点";
    const textarea = element.querySelector("textarea");
    if (node.title) element.querySelector("span").textContent = node.title;
    textarea.value = node.text || "";
    textarea.addEventListener("input", () => {
      node.text = textarea.value;
      if (state.selectedId === node.id) promptInput.value = node.text;
      persistLocal();
    });
  } else if (node.type === "video") {
    element = document.createElement("article");
    element.className = "node image-node media-node";
    const video = document.createElement("video");
    video.src = node.src;
    video.controls = true;
    const caption = document.createElement("div");
    caption.className = "node-caption";
    caption.textContent = node.title || "Video";
    element.append(video, caption);
  } else if (node.type === "audio") {
    element = document.createElement("article");
    element.className = "node audio-node";
    const title = document.createElement("strong");
    title.textContent = node.title || "Audio";
    const audio = document.createElement("audio");
    audio.src = node.src;
    audio.controls = true;
    element.append(title, audio);
  } else {
    element = document.createElement("article");
    element.className = "node image-node";
    const image = document.createElement("img");
    image.src = node.src;
    image.alt = node.title || "canvas image";
    const caption = document.createElement("div");
    caption.className = "node-caption";
    caption.textContent = node.title || "Image";
    element.append(image, caption);
  }

  element.dataset.id = node.id;
  element.style.left = `${node.x}px`;
  element.style.top = `${node.y}px`;
  element.style.width = `${node.width}px`;
  element.style.height = `${node.height}px`;
  if (node.id === state.selectedId) element.classList.add("selected");

  element.addEventListener("pointerdown", (event) => {
    if (event.target.tagName === "TEXTAREA" || event.target.tagName === "VIDEO" || event.target.tagName === "AUDIO") return;
    event.stopPropagation();
    selectNode(node.id);
    element.setPointerCapture(event.pointerId);
    const point = screenToWorld(event.clientX, event.clientY);
    drag = {
      type: "node",
      id: node.id,
      startX: point.x,
      startY: point.y,
      nodeX: node.x,
      nodeY: node.y,
    };
  });

  world.appendChild(element);
  return element;
}

function addNode(node) {
  node.id = node.id || `node-${state.nextId++}`;
  state.nodes.push(node);
  createNodeElement(node);
  selectNode(node.id);
  persistLocal();
  updateEmptyHint();
  return node;
}

function addPromptAt(point, text = "a refined product photo of a futuristic desk lamp, warm studio light, realistic materials", profileId = profileSelect.value) {
  if (profileId && profileSelect.value !== profileId) {
    profileSelect.value = profileId;
    applyProfile(activeProfile());
  }
  return addNode({
    type: "prompt",
    x: point.x,
    y: point.y,
    width: 300,
    height: 214,
    text,
    profileId,
  });
}

function addImageAt(point, src, width, height, title) {
  const maxSide = 520;
  const ratio = Math.min(maxSide / width, maxSide / height, 1);
  const node = addNode({
    type: "image",
    x: point.x,
    y: point.y,
    width: Math.max(180, Math.round(width * ratio)),
    height: Math.max(140, Math.round(height * ratio)),
    src,
    title,
  });
  saveAssetMetadata({ id: node.id, nodeId: node.id, type: "image", src, width, height, title });
  return node;
}

function addMediaAt(point, src, kind, title) {
  const node = addNode({
    type: kind,
    x: point.x,
    y: point.y,
    width: kind === "audio" ? 360 : 420,
    height: kind === "audio" ? 110 : 240,
    src,
    title,
  });
  saveAssetMetadata({ id: node.id, nodeId: node.id, type: kind, src, title });
  return node;
}

function redraw() {
  world.innerHTML = "";
  for (const node of state.nodes) createNodeElement(node);
  renderCamera();
  updateEmptyHint();
}

function persistLocal() {
  localStorage.setItem("comfyInfiniteCanvas", JSON.stringify({
    projectName: state.projectName,
    theme: state.theme,
    camera: state.camera,
    nodes: state.nodes,
    selectedId: state.selectedId,
    nextId: state.nextId,
  }));
}

function restoreLocal() {
  const saved = localStorage.getItem("comfyInfiniteCanvas");
  if (!saved) {
    updateEmptyHint();
    return;
  }
  try {
    const data = JSON.parse(saved);
    if (data.projectName) setProjectName(data.projectName, { persist: false });
    if (data.theme) applyTheme(data.theme);
    state.camera = data.camera || state.camera;
    state.nodes = data.nodes || [];
    state.selectedId = data.selectedId || null;
    state.nextId = data.nextId || state.nodes.length + 1;
    redraw();
  } catch {
    updateEmptyHint();
  }
}

function fieldValue(profile, key) {
  if (profile?.parameters && profile.parameters[key] !== undefined) return profile.parameters[key];
  const field = (profile?.fields || []).find((item) => item.key === key);
  if (field?.default !== undefined) return field.default;
  if (field?.type === "checkbox") return false;
  return "";
}

function renderDynamicFields(profile) {
  dynamicFields.innerHTML = "";
  const fields = profile?.fields || [];
  if (!fields.length) return;

  for (const field of fields) {
    const label = document.createElement("label");
    label.dataset.fieldKey = field.key;
    label.textContent = field.label || field.key;
    const value = fieldValue(profile, field.key);
    let control;
    if (field.type === "select") {
      control = document.createElement("select");
      for (const optionValue of field.options || []) {
        const option = document.createElement("option");
        option.value = optionValue;
        option.textContent = optionValue;
        option.selected = optionValue === value;
        control.appendChild(option);
      }
    } else if (field.type === "textarea") {
      control = document.createElement("textarea");
      control.rows = field.rows || 3;
      control.value = value || "";
    } else if (field.type === "checkbox") {
      label.classList.add("checkbox-field");
      control = document.createElement("input");
      control.type = "checkbox";
      control.checked = Boolean(value);
    } else {
      control = document.createElement("input");
      control.type = field.type === "number" ? "number" : "text";
      if (field.min !== undefined) control.min = field.min;
      if (field.max !== undefined) control.max = field.max;
      if (field.step !== undefined) control.step = field.step;
      control.value = value ?? "";
    }
    control.dataset.fieldKey = field.key;
    control.addEventListener("change", () => persistLocal());
    control.addEventListener("input", () => persistLocal());
    label.appendChild(control);
    dynamicFields.appendChild(label);
  }
}

function applyProfile(profile) {
  if (!profile) return;
  const p = profile.parameters || {};
  const useSdxl = isSdxlProfile(profile);
  checkpointField.hidden = !useSdxl;
  negativeInput.parentElement.hidden = !useSdxl;
  sdxlFields.hidden = !useSdxl;
  dynamicFields.hidden = useSdxl && !(profile.fields || []).length;

  if (useSdxl) {
    if (p.checkpoint) checkpointSelect.value = p.checkpoint;
    widthInput.value = p.width ?? widthInput.value;
    heightInput.value = p.height ?? heightInput.value;
    stepsInput.value = p.steps ?? stepsInput.value;
    cfgInput.value = p.cfg ?? cfgInput.value;
    samplerInput.value = p.sampler ?? samplerInput.value;
    schedulerInput.value = p.scheduler ?? schedulerInput.value;
    denoiseInput.value = p.denoise ?? denoiseInput.value;
    batchSizeInput.value = p.batchSize ?? batchSizeInput.value;
    negativeInput.value = p.negative ?? negativeInput.value;
  }
  profileNameInput.value = profile.name || profile.id;
  renderDynamicFields(profile);
  profileSummary.innerHTML = `
    <strong>${profile.name}</strong>
    <span>${profile.group || "模型档案"} · ${profile.task || "generation"} · ${profile.engine || "comfy_sdxl"}</span>
    <p>${profile.description || ""}</p>
  `;
  profileHint.textContent = profile.engine === "tikpan_node"
    ? "此档案会在本地 ComfyUI 中调用 Tikpan 自定义节点；生产环境可改为调用 web_app/New API。"
    : "此档案会在本地 ComfyUI 中拼装基础 SDXL workflow。";
  updateReferenceHint();
  setStatus(`已应用参数档案：${profile.name}`);
}

async function loadProvider() {
  try {
    const response = await fetch("/api/provider");
    const data = await response.json();
    state.provider = data.provider || "comfy";
    providerBadge.textContent = state.provider === "upstream" ? "云端上游" : "本地 ComfyUI";
    providerHint.textContent = state.provider === "upstream"
      ? (data.upstreamConfigured ? "请求会发到 UPSTREAM_URL" : "尚未配置 UPSTREAM_URL")
      : `${data.comfyBase}${data.tikpanKeyConfigured ? " · Tikpan Key 已配置" : " · 未配置 TIKPAN_API_KEY"}`;
    connectionLabel.textContent = state.provider === "upstream" ? "云端请求模式" : "本地 ComfyUI 模式";
  } catch (error) {
    providerBadge.textContent = "离线";
    providerHint.textContent = error.message;
    connectionLabel.textContent = "本地服务异常";
  }
}

async function loadProfiles() {
  try {
    const response = await fetch("/api/profiles");
    const data = await response.json();
    if (!data.ok) throw new Error(data.error || "无法读取参数档案");
    state.profiles = data.profiles || [];
    profileSelect.innerHTML = "";
    let currentGroup = "";
    for (const profile of state.profiles) {
      if ((profile.group || "") !== currentGroup) {
        currentGroup = profile.group || "";
        if (currentGroup) {
          const groupOption = document.createElement("option");
          groupOption.disabled = true;
          groupOption.textContent = `-- ${currentGroup} --`;
          profileSelect.appendChild(groupOption);
        }
      }
      const option = document.createElement("option");
      option.value = profile.id;
      option.textContent = profile.name;
      profileSelect.appendChild(option);
    }
    const firstReal = state.profiles[0];
    if (firstReal) {
      profileSelect.value = firstReal.id;
      applyProfile(firstReal);
    }
  } catch (error) {
    profileSelect.innerHTML = "<option value=''>无参数档案</option>";
    setStatus(`参数档案读取失败：${error.message}`);
  }
}

async function loadCheckpoints() {
  try {
    const response = await fetch("/api/comfy/checkpoints");
    const data = await response.json();
    if (!data.ok) throw new Error(data.error || "无法读取 checkpoint");
    checkpointSelect.innerHTML = "";
    for (const checkpoint of data.checkpoints) {
      const option = document.createElement("option");
      option.value = checkpoint;
      option.textContent = checkpoint;
      checkpointSelect.appendChild(option);
    }
    connectionLabel.textContent = `已连接 ComfyUI，${data.checkpoints.length} 个 checkpoint`;
    setStatus("ComfyUI 已连接。Tikpan 节点档案会通过本地 ComfyUI 调用自定义节点。");
  } catch (error) {
    checkpointSelect.innerHTML = "<option value=''>未连接 ComfyUI</option>";
    if (state.provider === "comfy") connectionLabel.textContent = "未连接 ComfyUI";
    setStatus(`ComfyUI 连接失败：${error.message}`);
  }
}

function syncPromptPanelFromSelection() {
  const node = state.nodes.find((item) => item.id === state.selectedId);
  if (node?.type === "prompt") {
    node.text = promptInput.value;
    const element = world.querySelector(`[data-id="${node.id}"] textarea`);
    if (element) element.value = node.text;
    persistLocal();
  }
}

function collectDynamicFields() {
  const values = {};
  for (const control of dynamicFields.querySelectorAll("[data-field-key]")) {
    const key = control.dataset.fieldKey;
    if (!key || control.tagName === "LABEL") continue;
    if (control.type === "checkbox") values[key] = control.checked;
    else if (control.type === "number") values[key] = control.value === "" ? "" : Number(control.value);
    else values[key] = control.value;
  }
  return values;
}

function collectCanvasImages() {
  return state.nodes
    .filter((node) => node.type === "image" && node.src)
    .map((node) => ({
      id: node.id,
      type: node.type,
      title: node.title || "Image",
      src: node.src,
      width: node.width,
      height: node.height,
    }));
}

function renderAssets() {
  if (!assetList) return;
  if (!state.assets.length) {
    assetList.innerHTML = `<p class="status-text">当前还没有资产。导入图片或生成结果后，会自动保存到这里。</p>`;
    return;
  }
  assetList.innerHTML = "";
  for (const asset of state.assets.slice(0, 8)) {
    const item = document.createElement("button");
    item.className = "asset-item";
    item.type = "button";
    const thumb = document.createElement(asset.type === "audio" ? "div" : "img");
    thumb.className = "asset-thumb";
    if (thumb.tagName === "IMG") thumb.src = asset.src;
    else thumb.textContent = "A";
    const body = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = asset.title || "Untitled asset";
    const meta = document.createElement("span");
    meta.textContent = `${asset.type || "image"} · ${asset.projectName || state.projectName}`;
    body.append(title, meta);
    item.append(thumb, body);
    item.addEventListener("click", () => {
      if (asset.type === "audio" || asset.type === "video") {
        addMediaAt(state.launcherPoint, asset.src, asset.type, asset.title);
      } else {
        addImageAt(state.launcherPoint, asset.src, asset.width || 1024, asset.height || 1024, asset.title);
      }
    });
    assetList.appendChild(item);
  }
}

async function loadAssets() {
  try {
    const response = await authedFetch("/api/assets");
    const data = await response.json();
    if (!data.ok) throw new Error(data.error || "Failed to load assets.");
    state.assets = data.assets || [];
    renderAssets();
  } catch {
    renderAssets();
  }
}

async function saveAssetMetadata(asset) {
  if (!asset?.src) return;
  const normalized = {
    ...asset,
    projectName: state.projectName,
    profileId: profileSelect.value,
  };
  state.assets = [normalized, ...state.assets.filter((item) => item.id !== normalized.id)].slice(0, 40);
  renderAssets();
  try {
    const response = await authedFetch("/api/assets", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ asset: normalized }),
    });
    const data = await response.json();
    if (data.ok && data.assets?.[0]) {
      state.assets = [data.assets[0], ...state.assets.filter((item) => item.id !== data.assets[0].id)].slice(0, 40);
      renderAssets();
    }
  } catch {
    // Local canvas state is still saved even when the asset API is not available.
  }
}

function renderFactorySummary() {
  if (!factoryWorkflowSelect || !factorySummary) return;
  const workflow = state.factoryWorkflows.find((item) => item.id === factoryWorkflowSelect.value);
  if (!workflow) {
    factorySummary.textContent = "选择一个工作流后，会自动生成角色、分镜、生成、后期和发布节点。";
    return;
  }
  factorySummary.innerHTML = `
    <strong>${workflow.name}</strong>
    <span>${workflow.tagline}</span>
    <span>核心指标：${workflow.northStar}</span>
  `;
}

async function loadFactoryWorkflows() {
  if (!factoryWorkflowSelect) return;
  try {
    const response = await fetch("/api/content-factory/workflows");
    const data = await response.json();
    if (!data.ok) throw new Error(data.error || "Failed to load workflows.");
    state.factoryWorkflows = data.workflows || [];
    factoryWorkflowSelect.innerHTML = "";
    for (const workflow of state.factoryWorkflows) {
      const option = document.createElement("option");
      option.value = workflow.id;
      option.textContent = workflow.name;
      factoryWorkflowSelect.appendChild(option);
    }
    renderFactorySummary();
  } catch (error) {
    factoryWorkflowSelect.innerHTML = "<option value=''>工作流读取失败</option>";
    if (factorySummary) factorySummary.textContent = error.message;
  }
}

async function buildFactoryCanvas() {
  const workflowId = factoryWorkflowSelect?.value;
  if (!workflowId) {
    setStatus("先选择一个内容工厂工作流。");
    return;
  }
  const brief = factoryBriefInput?.value.trim() || "";
  buildFactoryButton.disabled = true;
  setStatus("正在生成内容工厂画布...");
  try {
    const response = await authedFetch("/api/content-factory/plan", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ workflowId, brief }),
    });
    const data = await response.json();
    if (!data.ok) throw new Error(data.error || "工作流生成失败");
    const stamp = Date.now();
    state.nodes = state.nodes.filter((node) => node.factory?.templateId !== data.workflow.id);
    for (const [index, node] of data.nodes.entries()) {
      addNode({
        ...node,
        id: `${node.id}-${stamp}-${index}`,
      });
    }
    if (data.workflow?.name) setProjectName(`${data.workflow.name} - ${new Date().toLocaleDateString()}`);
    state.camera = { x: 920, y: 330, scale: 0.72 };
    renderCamera();
    requestPreview.value = JSON.stringify({
      workflow: data.workflow,
      checklist: data.checklist,
      nextBackendTables: ["projects", "assets", "workflow_runs", "workflow_tasks", "model_routes", "usage_records"],
    }, null, 2);
    persistLocal();
    setStatus(`已铺开「${data.workflow.name}」：先补 Brief，再逐个生成角色、分镜、视频和发布素材。`);
  } catch (error) {
    setStatus(`内容工厂生成失败：${error.message}`);
  } finally {
    buildFactoryButton.disabled = false;
  }
}

function collectPayload() {
  syncPromptPanelFromSelection();
  const selected = state.nodes.find((item) => item.id === state.selectedId);
  const selectedProfileId = selected?.type === "prompt" && selected.profileId ? selected.profileId : profileSelect.value;
  if (selectedProfileId && profileSelect.value !== selectedProfileId) {
    profileSelect.value = selectedProfileId;
    applyProfile(activeProfile());
  }
  const prompt = promptInput.value.trim() || (selected?.type === "prompt" ? selected.text : "");
  return {
    provider: state.provider,
    profileId: selectedProfileId,
    checkpoint: checkpointSelect.value,
    prompt,
    negative: negativeInput.value,
    width: Number(widthInput.value),
    height: Number(heightInput.value),
    steps: Number(stepsInput.value),
    cfg: Number(cfgInput.value),
    sampler: samplerInput.value,
    scheduler: schedulerInput.value,
    denoise: Number(denoiseInput.value),
    batchSize: Number(batchSizeInput.value),
    seed: seedInput.value,
    fields: collectDynamicFields(),
    canvasImages: collectCanvasImages(),
    canvas: selected ? {
      selectedNodeId: selected.id,
      selectedNodeType: selected.type,
      x: selected.x,
      y: selected.y,
      width: selected.width,
      height: selected.height,
    } : {},
  };
}

function updateReferenceHint() {
  const profile = activeProfile();
  if (!profile) return;
  const imageCount = collectCanvasImages().length;
  const selected = state.nodes.find((node) => node.id === state.selectedId);
  if (profile.requiresSelectedImage) {
    referenceHint.textContent = selected?.type === "image"
      ? "已选中图片节点，会作为主图像传入编辑节点。其他图片会按顺序作为参考图。"
      : "这个档案需要先选中一张图片作为主图像。";
    return;
  }
  const refInputs = profile.node?.referenceImageInputs?.length || profile.node?.maxCanvasImages || 0;
  referenceHint.textContent = refInputs
    ? `画布中 ${imageCount} 张图片可作为参考图，最多会传入 ${refInputs} 张。`
    : "当前档案不需要参考图；选中 Prompt 卡片即可生成。";
}

function profileIcon(profile) {
  if (profile?.mediaType === "video") return "▣";
  if (profile?.mediaType === "audio") return "♪";
  if (profile?.task === "image-edit") return "✎";
  return "✦";
}

function renderLauncherList(filter = "") {
  const query = filter.trim().toLowerCase();
  launcherList.innerHTML = "";
  const profiles = state.profiles.filter((profile) => {
    const haystack = `${profile.name || ""} ${profile.group || ""} ${profile.description || ""} ${profile.task || ""}`.toLowerCase();
    return !query || haystack.includes(query);
  });
  let currentGroup = "";
  for (const profile of profiles) {
    if ((profile.group || "模型") !== currentGroup) {
      currentGroup = profile.group || "模型";
      const group = document.createElement("div");
      group.className = "launcher-group";
      group.textContent = currentGroup;
      launcherList.appendChild(group);
    }
    const button = document.createElement("button");
    button.className = "launcher-item";
    button.innerHTML = `
      <span>${profileIcon(profile)}</span>
      <strong>${profile.name}</strong>
      <small>${profile.description || profile.task || ""}</small>
    `;
    button.addEventListener("click", () => {
      createProfileNode(profile.id, state.launcherPoint);
      hideLauncher();
    });
    launcherList.appendChild(button);
  }
}

function showLauncherAt(point, clientX, clientY) {
  state.launcherPoint = point;
  renderLauncherList(launcherSearch.value || "");
  launcher.hidden = false;
  const rect = canvas.getBoundingClientRect();
  launcher.style.left = `${Math.min(rect.width - 420, Math.max(88, clientX - rect.left + 14))}px`;
  launcher.style.top = `${Math.min(rect.height - 460, Math.max(74, clientY - rect.top + 14))}px`;
  launcherSearch.focus();
}

function hideLauncher() {
  launcher.hidden = true;
}

function createProfileNode(profileId, point = { x: 0, y: 0 }) {
  const profile = state.profiles.find((item) => item.id === profileId);
  const prompts = {
    "image-edit": "把选中的商品图换成高级电商广告背景，保持主体轮廓和细节，画面干净、有销售感。",
    "text-to-video": "一个高质量产品广告短片，镜头缓慢推进，真实光影，适合 TikTok 投放。",
    "text-to-audio": "创作一段适合短视频广告的流行音乐，节奏清晰，情绪积极。",
  };
  const text = prompts[profile?.task] || "一张高质量商品广告图，真实摄影质感，主体清晰，干净背景，适合跨境电商投放。";
  addPromptAt(point, text, profileId);
  setStatus(`已添加 ${profile?.name || "模型"} 节点。写好提示词后点击“生成到画布”。`);
}

async function previewRequest() {
  const payload = collectPayload();
    const response = await authedFetch("/api/request/preview", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  requestPreview.value = JSON.stringify(data, null, 2);
  setStatus(data.ok ? "已生成请求预览。这里能看到 Tikpan 节点 workflow 或云端请求结构。" : `预览失败：${data.error}`);
}

async function saveCurrentProfile() {
  const profile = activeProfile();
  const payload = collectPayload();
  const parameters = isSdxlProfile(profile)
    ? {
        checkpoint: payload.checkpoint,
        width: payload.width,
        height: payload.height,
        steps: payload.steps,
        cfg: payload.cfg,
        sampler: payload.sampler,
        scheduler: payload.scheduler,
        denoise: payload.denoise,
        batchSize: payload.batchSize,
        negative: payload.negative,
      }
    : payload.fields;

    const response = await authedFetch("/api/profiles", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      baseProfileId: profile?.id,
      id: profileNameInput.value,
      name: profileNameInput.value,
      description: profile?.description || "Saved from the canvas parameter panel.",
      parameters,
    }),
  });
  const data = await response.json();
  if (!data.ok) {
    setStatus(`保存参数档案失败：${data.error}`);
    return;
  }
  state.profiles = data.profiles;
  await loadProfiles();
  profileSelect.value = data.profile.id;
  applyProfile(data.profile);
  setStatus(`已保存参数档案：${data.profile.name}`);
}

async function generateImage() {
  const profile = activeProfile();
  const payload = collectPayload();
  if (!payload.prompt) {
    setStatus("先写一个 prompt，或者选中一个 prompt 卡片。");
    return;
  }
  if (isSdxlProfile(profile) && state.provider === "comfy" && !payload.checkpoint) {
    setStatus("本地 SDXL 模式需要先选择 checkpoint。");
    return;
  }
  if (profile?.requiresSelectedImage && payload.canvas.selectedNodeType !== "image") {
    setStatus("这个编辑档案需要先选中一张图片节点。");
    return;
  }

  setStatus("已提交请求，正在等待生成结果...");
  document.getElementById("generateButton").disabled = true;
  try {
    const response = await authedFetch("/api/generate", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    requestPreview.value = JSON.stringify(data.request || data, null, 2);
    if (!data.ok) throw new Error(data.error || "生成失败");

    const selected = state.nodes.find((item) => item.id === state.selectedId);
    const anchor = selected || { x: -120, y: -120, width: 300, height: 180 };
    const images = data.images || [];
    const media = data.media || [];
    images.forEach((image, index) => {
      addImageAt({
        x: anchor.x + anchor.width + 42 + index * 34,
        y: anchor.y + index * 34,
      }, image.url, payload.width || 1024, payload.height || 1024, `${profile?.name || data.provider} seed ${data.seed}`);
    });
    media.forEach((item, index) => {
      addMediaAt({
        x: anchor.x + anchor.width + 42 + (images.length + index) * 34,
        y: anchor.y + (images.length + index) * 34,
      }, item.url, item.kind || "video", `${profile?.name || "Media"} ${data.requestId || ""}`);
    });
    if (!images.length && !media.length) {
      setStatus(`任务完成但没有找到可贴回的图片/媒体。请求 ID: ${data.requestId || data.promptId}`);
      return;
    }
    setStatus(`生成完成，已贴回画布。请求 ID: ${data.requestId || data.promptId}`);
  } catch (error) {
      if (error.message.includes("请先登录")) openAuth("login");
      setStatus(`生成失败：${error.message}`);
  } finally {
    document.getElementById("generateButton").disabled = false;
  }
}

function fitView() {
  if (!state.nodes.length) return;
  const bounds = state.nodes.reduce((box, node) => ({
    minX: Math.min(box.minX, node.x),
    minY: Math.min(box.minY, node.y),
    maxX: Math.max(box.maxX, node.x + node.width),
    maxY: Math.max(box.maxY, node.y + node.height),
  }), { minX: Infinity, minY: Infinity, maxX: -Infinity, maxY: -Infinity });
  const rect = canvas.getBoundingClientRect();
  const width = bounds.maxX - bounds.minX;
  const height = bounds.maxY - bounds.minY;
  state.camera.scale = Math.min(rect.width / (width + 180), rect.height / (height + 180), 1.2);
  state.camera.x = rect.width / 2 - (bounds.minX + width / 2) * state.camera.scale;
  state.camera.y = rect.height / 2 - (bounds.minY + height / 2) * state.camera.scale;
  renderCamera();
  persistLocal();
}

async function saveProject() {
  syncPromptPanelFromSelection();
  setProjectName(projectTitleInput.value || projectNameInput.value);
  const name = state.projectName || "my-canvas";
  const project = {
    name,
    title: state.projectName,
    camera: state.camera,
    nodes: state.nodes,
    selectedId: state.selectedId,
    nextId: state.nextId,
    profileId: profileSelect.value,
  };
  const response = await authedFetch("/api/projects", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ name, project }),
  });
  const data = await response.json();
  setStatus(data.ok ? `已保存项目：${data.name}` : `保存失败：${data.error}`);
}

async function loadProject() {
  const name = state.projectName || projectNameInput.value || "my-canvas";
  const response = await authedFetch(`/api/projects/${encodeURIComponent(name)}`);
  const data = await response.json();
  if (!data.ok) {
    setStatus(`加载失败：${data.error}`);
    return;
  }
  state.camera = data.project.camera || state.camera;
  state.nodes = data.project.nodes || [];
  state.selectedId = data.project.selectedId || null;
  state.nextId = data.project.nextId || state.nodes.length + 1;
  setProjectName(data.project.title || data.project.name || data.name, { persist: false });
  if (data.project.profileId) profileSelect.value = data.project.profileId;
  redraw();
  applyProfile(activeProfile());
  persistLocal();
  setStatus(`已加载项目：${data.name}`);
}

canvas.addEventListener("pointerdown", (event) => {
  if (event.button !== 0) return;
  const isBlankCanvas = event.target === canvas || event.target === world;
  if (!isBlankCanvas) return;
  selectNode(null);
  hideLauncher();
  canvas.setPointerCapture(event.pointerId);
  drag = {
    type: "pan",
    blankCanvas: isBlankCanvas,
    startClientX: event.clientX,
    startClientY: event.clientY,
    cameraX: state.camera.x,
    cameraY: state.camera.y,
    moved: false,
  };
  canvas.classList.add("panning");
});

canvas.addEventListener("pointermove", (event) => {
  if (!drag) return;
  if (drag.type === "pan" && (Math.abs(event.clientX - drag.startClientX) > 4 || Math.abs(event.clientY - drag.startClientY) > 4)) {
    drag.moved = true;
  }
  if (drag.type === "pan") {
    state.camera.x = drag.cameraX + event.clientX - drag.startClientX;
    state.camera.y = drag.cameraY + event.clientY - drag.startClientY;
    renderCamera();
  }
  if (drag.type === "node") {
    const point = screenToWorld(event.clientX, event.clientY);
    const node = state.nodes.find((item) => item.id === drag.id);
    node.x = drag.nodeX + point.x - drag.startX;
    node.y = drag.nodeY + point.y - drag.startY;
    const element = world.querySelector(`[data-id="${node.id}"]`);
    element.style.left = `${node.x}px`;
    element.style.top = `${node.y}px`;
  }
});

canvas.addEventListener("pointerup", (event) => {
  const shouldOpenLauncher = drag?.type === "pan" && drag.blankCanvas && !drag.moved;
  const point = shouldOpenLauncher ? screenToWorld(event.clientX, event.clientY) : null;
  drag = null;
  canvas.classList.remove("panning");
  persistLocal();
  if (shouldOpenLauncher) showLauncherAt(point, event.clientX, event.clientY);
});

canvas.addEventListener("wheel", (event) => {
  event.preventDefault();
  const before = screenToWorld(event.clientX, event.clientY);
  const delta = Math.exp(-event.deltaY * 0.001);
  state.camera.scale = Math.min(3, Math.max(0.16, state.camera.scale * delta));
  const rect = canvas.getBoundingClientRect();
  state.camera.x = event.clientX - rect.left - before.x * state.camera.scale;
  state.camera.y = event.clientY - rect.top - before.y * state.camera.scale;
  renderCamera();
  persistLocal();
}, { passive: false });

canvas.addEventListener("dblclick", (event) => {
  if (event.target !== canvas && event.target !== world) return;
  showLauncherAt(screenToWorld(event.clientX, event.clientY), event.clientX, event.clientY);
});

window.addEventListener("keydown", (event) => {
  if ((event.key === "Delete" || event.key === "Backspace") && state.selectedId && document.activeElement.tagName !== "TEXTAREA" && document.activeElement.tagName !== "INPUT") {
    state.nodes = state.nodes.filter((item) => item.id !== state.selectedId);
    state.selectedId = null;
    redraw();
    persistLocal();
  }
});

promptInput.addEventListener("input", syncPromptPanelFromSelection);
profileSelect.addEventListener("change", () => applyProfile(activeProfile()));
projectNameInput.addEventListener("input", () => setProjectName(projectNameInput.value));
projectTitleInput.addEventListener("input", () => setProjectName(projectTitleInput.value));
if (themeSelect) themeSelect.addEventListener("change", () => applyTheme(themeSelect.value));
if (factoryWorkflowSelect) factoryWorkflowSelect.addEventListener("change", renderFactorySummary);
if (buildFactoryButton) buildFactoryButton.addEventListener("click", buildFactoryCanvas);

document.getElementById("addPromptButton").addEventListener("click", () => {
  const rect = canvas.getBoundingClientRect();
  showLauncherAt(
    screenToWorld(rect.left + rect.width / 2, rect.top + rect.height / 2),
    rect.left + rect.width / 2,
    rect.top + rect.height / 2
  );
});

document.getElementById("imageInput").addEventListener("change", (event) => {
  const files = Array.from(event.target.files || []);
  const rect = canvas.getBoundingClientRect();
  files.forEach((file, index) => {
    const reader = new FileReader();
    reader.onload = () => {
      const image = new Image();
      image.onload = () => {
        const point = screenToWorld(rect.left + rect.width / 2 + index * 36, rect.top + rect.height / 2 + index * 36);
        addImageAt(point, reader.result, image.naturalWidth, image.naturalHeight, file.name);
        updateReferenceHint();
      };
      image.src = reader.result;
    };
    reader.readAsDataURL(file);
  });
  event.target.value = "";
});

document.getElementById("generateButton").addEventListener("click", generateImage);
document.getElementById("previewButton").addEventListener("click", previewRequest);
document.getElementById("saveProfileButton").addEventListener("click", saveCurrentProfile);
document.getElementById("fitButton").addEventListener("click", fitView);
document.getElementById("saveButton").addEventListener("click", saveProject);
document.getElementById("loadButton").addEventListener("click", loadProject);
document.getElementById("clearButton").addEventListener("click", () => {
  if (!confirm("清空当前画布？")) return;
  state.nodes = [];
  state.selectedId = null;
  state.nextId = 1;
  redraw();
  persistLocal();
  updateReferenceHint();
});

launcherCloseButton.addEventListener("click", hideLauncher);
launcherSearch.addEventListener("input", () => renderLauncherList(launcherSearch.value));
welcomeStartButton.addEventListener("click", () => {
  welcomeOverlay.hidden = true;
  localStorage.setItem("canvasWelcomeSeen", "true");
});
document.querySelectorAll("[data-welcome-profile], [data-quick-profile]").forEach((button) => {
  button.addEventListener("click", () => {
    welcomeOverlay.hidden = true;
    localStorage.setItem("canvasWelcomeSeen", "true");
    const rect = canvas.getBoundingClientRect();
    createProfileNode(
      button.dataset.welcomeProfile || button.dataset.quickProfile,
      screenToWorld(rect.left + rect.width / 2, rect.top + rect.height / 2)
    );
  });
});
if (localStorage.getItem("canvasWelcomeSeen") === "true") {
  welcomeOverlay.hidden = true;
}

document.querySelectorAll("[data-menu]").forEach((button) => {
  button.addEventListener("click", () => {
    const menu = button.dataset.menu;
    document.querySelectorAll("[data-menu]").forEach((item) => item.classList.toggle("active", item.dataset.menu === menu));
    const labels = {
      create: "创作模式：点击画布添加模型节点。",
      assets: "资产面板稍后会接入我的素材库；现在可先导入本地图片。",
      workflows: "工作流面板稍后会接入后台配置的工作流模板。",
      history: "历史记录稍后会接入用户生成任务和扣费记录。",
      director: "导演台适合后续管理视频分镜、首尾帧和批量生成。",
      cut: "剪辑区适合后续接入视频裁剪、拼接和字幕。",
    };
    setStatus(labels[menu] || "已切换菜单。");
  });
});

zoomRange.addEventListener("input", () => {
  state.camera.scale = Math.min(3, Math.max(0.16, Number(zoomRange.value) / 100));
  renderCamera();
  persistLocal();
});
document.getElementById("centerButton").addEventListener("click", fitView);
document.getElementById("shareButton").addEventListener("click", () => setStatus("分享功能后续可生成只读项目链接。"));
document.getElementById("rechargeButton").addEventListener("click", () => setStatus("充值入口后续接入 web_app 的充值方案。"));

loginButton.addEventListener("click", () => openAuth("login"));
logoutButton.addEventListener("click", async () => {
  setAuthToken("");
  await refreshSession();
  await loadAssets();
  setStatus("已退出登录，画布仍保留在本地。");
});
authCloseButton.addEventListener("click", closeAuth);
authLoginTab.addEventListener("click", () => openAuth("login"));
authRegisterTab.addEventListener("click", () => openAuth("register"));
sendCodeButton.addEventListener("click", async () => {
  const email = authEmail.value.trim();
  if (!email) {
    authMessage.textContent = "请先填写邮箱。";
    return;
  }
  sendCodeButton.disabled = true;
  authMessage.textContent = "正在发送验证码...";
  try {
    const response = await fetch("/api/auth/send-code", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ email }),
    });
    const data = await response.json();
    if (!data.ok && !data.success) throw new Error(data.error || "发送失败");
    authMessage.textContent = data.code_preview ? `开发模式验证码：${data.code_preview}` : "验证码已发送。";
  } catch (error) {
    authMessage.textContent = error.message;
  } finally {
    sendCodeButton.disabled = false;
  }
});
authSubmitButton.addEventListener("click", async () => {
  const endpoint = state.authMode === "register" ? "/api/auth/register" : "/api/auth/login";
  const payload = {
    email: authEmail.value.trim(),
    password: authPassword.value.trim(),
  };
  if (state.authMode === "register") payload.code = authCode.value.trim();
  authSubmitButton.disabled = true;
  authMessage.textContent = state.authMode === "register" ? "正在注册..." : "正在登录...";
  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!data.ok) throw new Error(data.error || "登录失败");
    setAuthToken(data.token);
    closeAuth();
    await refreshSession();
    await loadAssets();
    setStatus("已登录，后续生成和项目保存会绑定到当前账号。");
  } catch (error) {
    authMessage.textContent = error.message;
  } finally {
    authSubmitButton.disabled = false;
  }
});

applyTheme(state.theme);
setProjectName(projectTitleInput.value || projectNameInput.value, { persist: false });
renderCamera();
restoreLocal();
loadProvider();
loadProfiles();
loadCheckpoints();
loadFactoryWorkflows();
refreshSession().then(loadAssets);
