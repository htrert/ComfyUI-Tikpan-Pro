const canvas = document.getElementById("canvas");
const world = document.getElementById("world");
const stage = document.querySelector(".stage");
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
const miniMapButton = document.getElementById("miniMapButton");
const gridButton = document.getElementById("gridButton");
const miniMap = document.getElementById("miniMap");
const miniMapBody = document.getElementById("miniMapBody");
const miniMapCount = document.getElementById("miniMapCount");
const localStatusEl = document.getElementById("localStatus");
const apiKeyStatusEl = document.getElementById("apiKeyStatus");
const comfyStatusEl = document.getElementById("comfyStatus");
const settingsButton = document.getElementById("settingsButton");
const settingsModal = document.getElementById("settingsModal");
const settingsCloseButton = document.getElementById("settingsCloseButton");
const settingsApiKey = document.getElementById("settingsApiKey");
const settingsKeyToggle = document.getElementById("settingsKeyToggle");
const settingsComfyUrl = document.getElementById("settingsComfyUrl");
const settingsSaveButton = document.getElementById("settingsSaveButton");
const settingsMessage = document.getElementById("settingsMessage");

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
  showGrid: localStorage.getItem("canvasGridHidden") !== "true",
  showMiniMap: localStorage.getItem("canvasMiniMapOpen") === "true",
};

let drag = null;
let clipboardNode = null;

const history = {
  past: [],
  future: [],
  last: "",
  max: 50,
};

const PLACEMENT_GAP = 32;
const PLACEMENT_STEP = 80;
const PLACEMENT_MAX_TRIES = 64;
const NODE_DEFAULT_SIZE = {
  prompt: { width: 300, height: 214 },
  note: { width: 320, height: 180 },
  image: { width: 320, height: 360 },
  video: { width: 420, height: 240 },
  audio: { width: 360, height: 110 },
};

function cloneData(value) {
  if (typeof structuredClone === "function") return structuredClone(value);
  return JSON.parse(JSON.stringify(value));
}

function historySnapshot() {
  return {
    projectName: state.projectName,
    nodes: cloneData(state.nodes),
    selectedId: state.selectedId,
    nextId: state.nextId,
  };
}

function resetHistory() {
  history.past = [];
  history.future = [];
  history.last = JSON.stringify(historySnapshot());
  updateHistoryButtons();
}

function captureHistory() {
  const snapshot = historySnapshot();
  const serialized = JSON.stringify(snapshot);
  if (serialized === history.last) return;
  if (history.last) {
    history.past.push(JSON.parse(history.last));
    if (history.past.length > history.max) history.past.shift();
  }
  history.last = serialized;
  history.future = [];
  updateHistoryButtons();
}

function applyHistorySnapshot(snapshot) {
  state.projectName = snapshot.projectName || "Untitled Canvas";
  state.nodes = cloneData(snapshot.nodes || []);
  state.selectedId = snapshot.selectedId || null;
  state.nextId = snapshot.nextId || state.nodes.length + 1;
  setProjectName(state.projectName, { persist: false });
  redraw();
  persistLocal();
}

function undoCanvas() {
  if (!history.past.length) return;
  const current = historySnapshot();
  const previous = history.past.pop();
  history.future.push(current);
  history.last = JSON.stringify(previous);
  applyHistorySnapshot(previous);
  updateHistoryButtons();
}

function redoCanvas() {
  if (!history.future.length) return;
  const current = historySnapshot();
  const next = history.future.pop();
  history.past.push(current);
  history.last = JSON.stringify(next);
  applyHistorySnapshot(next);
  updateHistoryButtons();
}

function updateHistoryButtons() {
  const undoButton = document.getElementById("undoButton");
  const redoButton = document.getElementById("redoButton");
  if (undoButton) undoButton.disabled = history.past.length === 0;
  if (redoButton) redoButton.disabled = history.future.length === 0;
}

function defaultNodeSize(type) {
  return NODE_DEFAULT_SIZE[type] || NODE_DEFAULT_SIZE.image;
}

function rectOfNode(node) {
  const fallback = defaultNodeSize(node.type);
  return {
    x: Number(node.x) || 0,
    y: Number(node.y) || 0,
    width: Number(node.width) || fallback.width,
    height: Number(node.height) || fallback.height,
  };
}

function rectsIntersect(a, b, gap = PLACEMENT_GAP) {
  return !(
    a.x + a.width + gap <= b.x ||
    b.x + b.width + gap <= a.x ||
    a.y + a.height + gap <= b.y ||
    b.y + b.height + gap <= a.y
  );
}

function anyRectIntersects(rect, others, gap = PLACEMENT_GAP) {
  return others.some((other) => rectsIntersect(rect, other, gap));
}

function* spiralOffsets(step, maxTries) {
  yield { dx: 0, dy: 0 };
  let x = 0;
  let y = 0;
  let tries = 1;
  let leg = 1;
  while (tries < maxTries) {
    for (let i = 0; i < leg && tries < maxTries; i += 1) {
      x += step;
      tries += 1;
      yield { dx: x, dy: y };
    }
    for (let i = 0; i < leg && tries < maxTries; i += 1) {
      y += step;
      tries += 1;
      yield { dx: x, dy: y };
    }
    leg += 1;
    for (let i = 0; i < leg && tries < maxTries; i += 1) {
      x -= step;
      tries += 1;
      yield { dx: x, dy: y };
    }
    for (let i = 0; i < leg && tries < maxTries; i += 1) {
      y -= step;
      tries += 1;
      yield { dx: x, dy: y };
    }
    leg += 1;
  }
}

function adaptivePlacementStep(rects, fallback = PLACEMENT_STEP) {
  return rects.reduce((max, rect) => Math.max(max, rect.width + PLACEMENT_GAP, rect.height + PLACEMENT_GAP), fallback);
}

function fallbackRightmost(rect, existing) {
  if (!existing.length) return { x: rect.x, y: rect.y };
  const maxRight = existing.reduce((max, item) => Math.max(max, item.x + item.width), -Infinity);
  return { x: maxRight + PLACEMENT_GAP, y: rect.y };
}

function findClearRect(rect, existing) {
  const passes = [
    { step: PLACEMENT_STEP, tries: Math.min(24, PLACEMENT_MAX_TRIES) },
    { step: adaptivePlacementStep([rect, ...existing]), tries: PLACEMENT_MAX_TRIES },
  ];
  for (const pass of passes) {
    for (const offset of spiralOffsets(pass.step, pass.tries)) {
      const candidate = { ...rect, x: rect.x + offset.dx, y: rect.y + offset.dy };
      if (!anyRectIntersects(candidate, existing)) return candidate;
    }
  }
  return { ...rect, ...fallbackRightmost(rect, existing) };
}

function placeNodeRect(node, existingNodes = state.nodes) {
  const desired = rectOfNode(node);
  const existing = existingNodes.filter((item) => item.id !== node.id).map(rectOfNode);
  return findClearRect(desired, existing);
}

function boundingRect(rects) {
  return rects.reduce((box, rect) => ({
    x: Math.min(box.x, rect.x),
    y: Math.min(box.y, rect.y),
    right: Math.max(box.right, rect.x + rect.width),
    bottom: Math.max(box.bottom, rect.y + rect.height),
  }), { x: Infinity, y: Infinity, right: -Infinity, bottom: -Infinity });
}

function placeNodeBatch(nodes, existingNodes = state.nodes) {
  if (!nodes.length) return { dx: 0, dy: 0 };
  const rects = nodes.map(rectOfNode);
  const box = boundingRect(rects);
  const groupRect = { x: box.x, y: box.y, width: box.right - box.x, height: box.bottom - box.y };
  const existing = existingNodes.map(rectOfNode);
  const placed = findClearRect(groupRect, existing);
  return { dx: placed.x - groupRect.x, dy: placed.y - groupRect.y };
}

function setStatus(text) {
  statusText.textContent = text;
}

// ─── Toast 通知系统 ────────────────────────────────────────────────────────
// type: "info" | "success" | "error" | "warn"
function toast(message, type = "info", duration = 5000) {
  const container = document.getElementById("toastContainer");
  if (!container) return;
  const el = document.createElement("div");
  el.className = `toast toast-${type}`;
  const icons = { success: "✓", error: "✕", warn: "⚠", info: "ℹ" };
  el.innerHTML = `<span class="toast-icon">${icons[type] || icons.info}</span><span class="toast-msg">${message}</span><button class="toast-close" aria-label="关闭">×</button>`;
  el.querySelector(".toast-close").addEventListener("click", () => dismissToast(el));
  container.appendChild(el);
  requestAnimationFrame(() => el.classList.add("toast-in"));
  const timer = setTimeout(() => dismissToast(el), duration);
  el._toastTimer = timer;
}

function dismissToast(el) {
  clearTimeout(el._toastTimer);
  el.classList.remove("toast-in");
  el.classList.add("toast-out");
  el.addEventListener("transitionend", () => el.remove(), { once: true });
}

// ─── 节点生成中状态 ────────────────────────────────────────────────────────
function setNodeGenerating(nodeId, isGenerating) {
  const el = nodeId ? world.querySelector(`[data-id="${nodeId}"]`) : null;
  if (el) el.classList.toggle("generating", isGenerating);
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

// 简单 fetch 包装（本地模式无需 token）
async function authedFetch(url, options = {}) {
  return fetch(url, options);
}

// ─── 本地配置 / 设置弹窗 ─────────────────────────────────────────────────
async function loadLocalConfig() {
  try {
    const response = await fetch("/api/config");
    const data = await response.json();
    if (!data.ok) return;
    
    // 更新状态栏
    if (apiKeyStatusEl) {
      apiKeyStatusEl.textContent = data.apiKeyConfigured
        ? ("API 密钥：" + (data.apiKeyMasked || "已配置"))
        : "API 密钥：未配置";
      apiKeyStatusEl.dataset.ok = data.apiKeyConfigured ? "1" : "0";
    }
    if (settingsComfyUrl) settingsComfyUrl.value = data.comfyUrl || "http://127.0.0.1:8188";

    // 没有 Key 时自动打开设置
    if (!data.apiKeyConfigured) {
      setTimeout(() => openSettings(), 800);
    }
    return data;
  } catch (e) {
    if (apiKeyStatusEl) apiKeyStatusEl.textContent = "配置读取失败";
  }
}

function openSettings() {
  if (settingsModal) settingsModal.classList.add("open");
  if (settingsApiKey) { settingsApiKey.value = ""; settingsApiKey.focus(); }
  if (settingsMessage) settingsMessage.textContent = "";
  // 加载数据目录路径
  fetch("/api/data-path").then(r => r.json()).then(data => {
    const info = document.getElementById("dataPathInfo");
    const text = document.getElementById("dataPathText");
    if (info && text && data.ok) {
      text.textContent = data.dataDir;
      info.style.display = "block";
    }
  }).catch(() => {});
}

function closeSettings() {
  if (settingsModal) settingsModal.classList.remove("open");
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
  renderMiniMap();
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

function applyCanvasChrome() {
  if (stage) stage.classList.toggle("grid-hidden", !state.showGrid);
  if (gridButton) gridButton.classList.toggle("active", state.showGrid);
  if (miniMap) miniMap.classList.toggle("open", state.showMiniMap);
  if (miniMapButton) miniMapButton.classList.toggle("active", state.showMiniMap);
  renderMiniMap();
}

function nodeBounds(nodes = state.nodes) {
  if (!nodes.length) return null;
  return nodes.reduce((box, node) => ({
    minX: Math.min(box.minX, node.x),
    minY: Math.min(box.minY, node.y),
    maxX: Math.max(box.maxX, node.x + node.width),
    maxY: Math.max(box.maxY, node.y + node.height),
  }), { minX: Infinity, minY: Infinity, maxX: -Infinity, maxY: -Infinity });
}

function renderMiniMap() {
  if (!miniMapBody || !state.showMiniMap) return;
  miniMapBody.innerHTML = "";
  if (miniMapCount) miniMapCount.textContent = `${state.nodes.length} 节点`;
  const bounds = nodeBounds();
  if (!bounds) return;

  const pad = 90;
  const mapRect = miniMapBody.getBoundingClientRect();
  const worldWidth = Math.max(bounds.maxX - bounds.minX + pad * 2, 1);
  const worldHeight = Math.max(bounds.maxY - bounds.minY + pad * 2, 1);
  const scale = Math.min(mapRect.width / worldWidth, mapRect.height / worldHeight);
  const originX = bounds.minX - pad;
  const originY = bounds.minY - pad;
  const offsetX = (mapRect.width - worldWidth * scale) / 2;
  const offsetY = (mapRect.height - worldHeight * scale) / 2;

  for (const node of state.nodes) {
    const item = document.createElement("div");
    item.className = `mini-node ${node.type || "prompt"}`;
    item.style.left = `${offsetX + (node.x - originX) * scale}px`;
    item.style.top = `${offsetY + (node.y - originY) * scale}px`;
    item.style.width = `${Math.max(4, node.width * scale)}px`;
    item.style.height = `${Math.max(4, node.height * scale)}px`;
    miniMapBody.appendChild(item);
  }

  const canvasRect = canvas.getBoundingClientRect();
  const view = document.createElement("div");
  view.className = "mini-viewport";
  view.style.left = `${offsetX + ((-state.camera.x / state.camera.scale) - originX) * scale}px`;
  view.style.top = `${offsetY + ((-state.camera.y / state.camera.scale) - originY) * scale}px`;
  view.style.width = `${Math.max(8, (canvasRect.width / state.camera.scale) * scale)}px`;
  view.style.height = `${Math.max(8, (canvasRect.height / state.camera.scale) * scale)}px`;
  miniMapBody.appendChild(view);
}

function clearCanvasLinks() {
  world.querySelectorAll(".canvas-link").forEach((link) => link.remove());
}

function drawLinkBetween(fromNode, toNode) {
  if (!fromNode || !toNode) return;
  const startX = fromNode.x + fromNode.width;
  const startY = fromNode.y + fromNode.height / 2;
  const endX = toNode.x;
  const endY = toNode.y + toNode.height / 2;
  const dx = endX - startX;
  const dy = endY - startY;
  const length = Math.hypot(dx, dy);
  if (length < 12) return;
  const link = document.createElement("div");
  link.className = "canvas-link";
  link.style.left = `${startX}px`;
  link.style.top = `${startY}px`;
  link.style.width = `${length}px`;
  link.style.transform = `rotate(${Math.atan2(dy, dx)}rad)`;
  world.insertBefore(link, world.firstChild);
}

function renderCanvasLinks() {
  clearCanvasLinks();
  const factoryNodes = state.nodes.filter((node) => node.factory?.templateId);
  if (!factoryNodes.length) return;
  const byLane = new Map();
  for (const node of factoryNodes) {
    const lane = node.factory?.lane || "workflow";
    if (!byLane.has(lane)) byLane.set(lane, []);
    byLane.get(lane).push(node);
  }
  for (const nodes of byLane.values()) {
    nodes.sort((a, b) => a.y - b.y).forEach((node, index, arr) => {
      if (arr[index + 1]) drawLinkBetween(node, arr[index + 1]);
    });
  }
  const ordered = [...factoryNodes].sort((a, b) => (a.x - b.x) || (a.y - b.y));
  ordered.forEach((node, index) => {
    if (ordered[index + 1] && ordered[index + 1].factory?.lane !== node.factory?.lane) {
      drawLinkBetween(node, ordered[index + 1]);
    }
  });
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

function addNode(node, options = {}) {
  node.id = node.id || `node-${state.nextId++}`;
  if (options.place !== false) {
    const placed = placeNodeRect(node);
    node.x = placed.x;
    node.y = placed.y;
  }
  if (options.capture !== false) captureHistory();
  state.nodes.push(node);
  createNodeElement(node);
  selectNode(node.id);
  persistLocal();
  updateEmptyHint();
  renderCanvasLinks();
  renderMiniMap();
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

function duplicateSelectedNode(offset = { x: 42, y: 42 }) {
  const source = state.nodes.find((item) => item.id === state.selectedId);
  if (!source) return null;
  const copy = cloneData(source);
  delete copy.id;
  copy.x = source.x + offset.x;
  copy.y = source.y + offset.y;
  copy.title = copy.title ? `${copy.title} copy` : copy.title;
  return addNode(copy);
}

function addImageAt(point, src, width, height, title, options = {}) {
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
  }, options);
  saveAssetMetadata({ id: node.id, nodeId: node.id, type: "image", src, width, height, title });
  return node;
}

function addMediaAt(point, src, kind, title, options = {}) {
  const node = addNode({
    type: kind,
    x: point.x,
    y: point.y,
    width: kind === "audio" ? 360 : 420,
    height: kind === "audio" ? 110 : 240,
    src,
    title,
  }, options);
  saveAssetMetadata({ id: node.id, nodeId: node.id, type: kind, src, title });
  return node;
}

function redraw() {
  world.innerHTML = "";
  for (const node of state.nodes) createNodeElement(node);
  renderCanvasLinks();
  renderCamera();
  updateEmptyHint();
}

// ─── 画布状态持久化（服务器文件 + localStorage 双备份）─────────────────────
// 所有画布数据写入 data/canvas-autosave.json，复制该文件夹即可完整迁移。
// localStorage 仅作快速缓存/离线备份，不是主存储。
let _saveTimer = null;

function _buildSaveSnapshot() {
  return {
    projectName: state.projectName,
    theme: state.theme,
    camera: state.camera,
    nodes: state.nodes,
    selectedId: state.selectedId,
    nextId: state.nextId,
    savedAt: new Date().toISOString(),
  };
}

function persistLocal() {
  const snapshot = _buildSaveSnapshot();
  // 快速写 localStorage（同步，供刷新/重开浏览器用）
  try { localStorage.setItem("comfyInfiniteCanvas", JSON.stringify(snapshot)); } catch { /* quota 满时忽略 */ }
  // 防抖 500ms 写服务器文件
  clearTimeout(_saveTimer);
  _saveTimer = setTimeout(() => _saveToServer(snapshot), 500);
}

async function _saveToServer(snapshot) {
  try {
    await fetch("/api/autosave", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(snapshot),
    });
  } catch { /* 服务不可用时静默失败，localStorage 仍有备份 */ }
}

function _applySnapshot(data) {
  if (!data) { updateEmptyHint(); return; }
  if (data.projectName) setProjectName(data.projectName, { persist: false });
  if (data.theme) applyTheme(data.theme);
  state.camera = data.camera || state.camera;
  state.nodes = data.nodes || [];
  state.selectedId = data.selectedId || null;
  state.nextId = data.nextId || state.nodes.length + 1;
  redraw();
  resetHistory();
}

async function restoreLocal() {
  // 优先从服务器文件读取（可迁移、可备份）
  try {
    const res = await fetch("/api/autosave");
    const result = await res.json();
    if (result.ok && result.data && Array.isArray(result.data.nodes)) {
      _applySnapshot(result.data);
      return;
    }
  } catch { /* 服务不可用，回退 localStorage */ }

  // 回退：浏览器 localStorage
  try {
    const saved = localStorage.getItem("comfyInfiniteCanvas");
    if (saved) { _applySnapshot(JSON.parse(saved)); return; }
  } catch { /* ignore */ }

  updateEmptyHint();
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
      : `${data.comfyBase}${data.apiKeyConfigured ? " · API 密钥已配置" : " · 未配置 API 密钥"}`;
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
  const dot = document.getElementById("comfyDot");
  const label = document.getElementById("comfyStatus");
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
    setStatus("ComfyUI 已连接，Tikpan 节点档案通过本地 ComfyUI 执行。");
    if (dot) dot.dataset.ok = "1";
    if (label) label.textContent = `ComfyUI：已连接（${data.checkpoints.length} 个模型）`;
  } catch (error) {
    checkpointSelect.innerHTML = "<option value=''>未连接 ComfyUI</option>";
    if (state.provider === "comfy") connectionLabel.textContent = "未连接 ComfyUI";
    setStatus(`ComfyUI 连接失败：${error.message}`);
    if (dot) dot.dataset.ok = "0";
    if (label) label.textContent = "ComfyUI：未连接";
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
    captureHistory();
    state.nodes = state.nodes.filter((node) => node.factory?.templateId !== data.workflow.id);
    const incomingNodes = data.nodes.map((node, index) => ({
        ...node,
        id: `${node.id}-${stamp}-${index}`,
    }));
    const offset = placeNodeBatch(incomingNodes, state.nodes);
    for (const node of incomingNodes) {
      addNode({
        ...node,
        x: node.x + offset.dx,
        y: node.y + offset.dy,
      }, { place: false, capture: false });
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
  try {
    const response = await authedFetch("/api/request/preview", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    requestPreview.value = JSON.stringify(data, null, 2);
    if (data.ok) {
      setStatus("已生成请求预览。这里能看到 Tikpan 节点 workflow 或云端请求结构。");
    } else {
      toast(`预览失败：${data.error}`, "error");
      setStatus(`预览失败：${data.error}`);
    }
  } catch (error) {
    toast(`预览请求异常：${error.message}`, "error");
    setStatus(`预览请求异常：${error.message}`);
  }
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
    toast("先写一个 prompt，或者选中一个 prompt 卡片。", "warn");
    setStatus("先写一个 prompt，或者选中一个 prompt 卡片。");
    return;
  }
  if (isSdxlProfile(profile) && state.provider === "comfy" && !payload.checkpoint) {
    toast("本地 SDXL 模式需要先选择 checkpoint。", "warn");
    setStatus("本地 SDXL 模式需要先选择 checkpoint。");
    return;
  }
  if (profile?.requiresSelectedImage && payload.canvas.selectedNodeType !== "image") {
    toast("这个编辑档案需要先选中一张图片节点。", "warn");
    setStatus("这个编辑档案需要先选中一张图片节点。");
    return;
  }

  const genBtn = document.getElementById("generateButton");
  const selectedNode = state.nodes.find((item) => item.id === state.selectedId);

  genBtn.disabled = true;
  genBtn.textContent = "生成中…";
  setNodeGenerating(state.selectedId, true);
  setStatus("已提交请求，正在等待生成结果…");

  try {
    const response = await authedFetch("/api/generate", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });

    // 先检查 HTTP 状态，再解析 JSON
    const data = await response.json().catch(() => ({ ok: false, error: `HTTP ${response.status}` }));
    if (!response.ok || !data.ok) {
      const msg = data.error || `服务器返回 ${response.status}`;
      if (msg.includes("密钥")) openSettings();
      throw new Error(msg);
    }

    requestPreview.value = JSON.stringify(data.request || data, null, 2);

    const anchor = selectedNode || { x: -120, y: -120, width: 300, height: 180 };
    const images = data.images || [];
    const media = data.media || [];

    if (images.length || media.length) captureHistory();

    // 使用 findClearRect 算法摆放结果，避免重叠
    const existingRects = state.nodes.map(rectOfNode);
    const startX = anchor.x + anchor.width + 42;
    const startY = anchor.y;

    images.forEach((image, index) => {
      const w = 320, h = 360;
      const candidate = { x: startX + index * 16, y: startY + index * 16, width: w, height: h };
      const placed = findClearRect(candidate, existingRects);
      existingRects.push(placed);
      addImageAt(placed, image.url, payload.width || 1024, payload.height || 1024,
        `${profile?.name || data.provider} · seed ${data.seed}`, { capture: false });
    });

    media.forEach((item, index) => {
      const w = item.kind === "audio" ? 360 : 420;
      const h = item.kind === "audio" ? 110 : 240;
      const candidate = { x: startX + (images.length + index) * 16, y: startY + (images.length + index) * 16, width: w, height: h };
      const placed = findClearRect(candidate, existingRects);
      existingRects.push(placed);
      addMediaAt(placed, item.url, item.kind || "video",
        `${profile?.name || "Media"} ${data.requestId || ""}`, { capture: false });
    });

    const total = images.length + media.length;
    if (!total) {
      toast(`任务完成，但未返回可贴回的图片/媒体。请求 ID: ${data.requestId || data.promptId || "—"}`, "warn", 8000);
      setStatus(`任务完成但无结果。请求 ID: ${data.requestId || data.promptId}`);
      return;
    }

    toast(`生成完成，已贴回 ${total} 张${images.length ? "图片" : ""}${media.length ? "·媒体" : ""}`, "success");
    setStatus(`生成完成 | ${total} 张结果 | 请求 ID: ${data.requestId || data.promptId || "—"}`);

  } catch (error) {
    toast(`生成失败：${error.message}`, "error", 10000);
    setStatus(`生成失败：${error.message}`);
  } finally {
    genBtn.disabled = false;
    genBtn.textContent = "生成到画布";
    setNodeGenerating(state.selectedId, false);
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
  resetHistory();
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
    renderCanvasLinks();
    renderMiniMap();
  }
});

canvas.addEventListener("pointerup", (event) => {
  const shouldOpenLauncher = drag?.type === "pan" && drag.blankCanvas && !drag.moved;
  const point = shouldOpenLauncher ? screenToWorld(event.clientX, event.clientY) : null;
  const changedNode = drag?.type === "node";
  drag = null;
  canvas.classList.remove("panning");
  if (changedNode) captureHistory();
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

// ─── 右键上下文菜单 ────────────────────────────────────────────────────────
let _ctxMenu = null;

function hideContextMenu() {
  if (_ctxMenu) { _ctxMenu.remove(); _ctxMenu = null; }
}

function showContextMenu(nodeId, clientX, clientY) {
  hideContextMenu();
  const node = state.nodes.find((n) => n.id === nodeId);
  if (!node) return;

  const menu = document.createElement("div");
  menu.className = "ctx-menu";
  menu.style.left = `${clientX}px`;
  menu.style.top  = `${clientY}px`;

  const items = [
    { label: "复制节点  Ctrl+D", action: () => { duplicateSelectedNode(); toast("已复制节点", "info", 2500); } },
    { label: "复制到剪贴板  Ctrl+C", action: () => { clipboardNode = cloneData(node); toast("已复制到剪贴板", "info", 2500); } },
    { type: "sep" },
    { label: "删除节点  Del", danger: true, action: () => {
        captureHistory();
        state.nodes = state.nodes.filter((n) => n.id !== nodeId);
        state.selectedId = null;
        redraw(); persistLocal();
        toast("已删除节点", "info", 2500);
      },
    },
  ];

  for (const item of items) {
    if (item.type === "sep") {
      const sep = document.createElement("hr");
      sep.className = "ctx-sep";
      menu.appendChild(sep);
      continue;
    }
    const btn = document.createElement("button");
    btn.className = `ctx-item${item.danger ? " ctx-danger" : ""}`;
    btn.textContent = item.label;
    btn.addEventListener("click", () => { hideContextMenu(); item.action(); });
    menu.appendChild(btn);
  }

  document.body.appendChild(menu);
  _ctxMenu = menu;

  // 防止菜单超出视窗
  requestAnimationFrame(() => {
    const r = menu.getBoundingClientRect();
    if (r.right  > window.innerWidth)  menu.style.left = `${clientX - r.width  - 4}px`;
    if (r.bottom > window.innerHeight) menu.style.top  = `${clientY - r.height - 4}px`;
  });
}

document.addEventListener("click", () => hideContextMenu());
document.addEventListener("keydown", (e) => { if (e.key === "Escape") hideContextMenu(); });

canvas.addEventListener("contextmenu", (event) => {
  const nodeEl = event.target.closest(".node");
  if (!nodeEl) return;
  event.preventDefault();
  selectNode(nodeEl.dataset.id);
  showContextMenu(nodeEl.dataset.id, event.clientX, event.clientY);
});

window.addEventListener("keydown", (event) => {
  const activeTag = document.activeElement?.tagName || "";
  const isEditingText = activeTag === "TEXTAREA" || activeTag === "INPUT";
  // Ctrl+Enter / Cmd+Enter → 生成
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    const genBtn = document.getElementById("generateButton");
    if (genBtn && !genBtn.disabled) generateImage();
    return;
  }
  const key = event.key.toLowerCase();
  if ((event.ctrlKey || event.metaKey) && !isEditingText) {
    if (key === "z" && !event.shiftKey) {
      event.preventDefault();
      undoCanvas();
      return;
    }
    if (key === "y" || (key === "z" && event.shiftKey)) {
      event.preventDefault();
      redoCanvas();
      return;
    }
    if (key === "c" && state.selectedId) {
      event.preventDefault();
      const selected = state.nodes.find((item) => item.id === state.selectedId);
      clipboardNode = selected ? cloneData(selected) : null;
      setStatus(clipboardNode ? "已复制当前节点。" : "没有可复制的节点。");
      return;
    }
    if (key === "v" && clipboardNode) {
      event.preventDefault();
      const copy = cloneData(clipboardNode);
      delete copy.id;
      copy.x = (copy.x || 0) + 48;
      copy.y = (copy.y || 0) + 48;
      addNode(copy);
      return;
    }
    if (key === "d" && state.selectedId) {
      event.preventDefault();
      duplicateSelectedNode();
      return;
    }
  }
  if ((event.key === "Delete" || event.key === "Backspace") && state.selectedId && !isEditingText) {
    captureHistory();
    state.nodes = state.nodes.filter((item) => item.id !== state.selectedId);
    state.selectedId = null;
    redraw();
    persistLocal();
  }
});

window.addEventListener("resize", () => {
  renderMiniMap();
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
document.getElementById("undoButton")?.addEventListener("click", undoCanvas);
document.getElementById("redoButton")?.addEventListener("click", redoCanvas);
document.getElementById("duplicateButton")?.addEventListener("click", () => duplicateSelectedNode());
document.getElementById("saveButton").addEventListener("click", saveProject);
document.getElementById("loadButton").addEventListener("click", loadProject);
document.getElementById("clearButton").addEventListener("click", () => {
  if (!confirm("清空当前画布？")) return;
  captureHistory();
  state.nodes = [];
  state.selectedId = null;
  state.nextId = 1;
  redraw();
  persistLocal();
  updateReferenceHint();
});
if (gridButton) {
  gridButton.addEventListener("click", () => {
    state.showGrid = !state.showGrid;
    localStorage.setItem("canvasGridHidden", String(!state.showGrid));
    applyCanvasChrome();
    setStatus(state.showGrid ? "已显示画布网格。" : "已隐藏画布网格。");
  });
}
if (miniMapButton) {
  miniMapButton.addEventListener("click", () => {
    state.showMiniMap = !state.showMiniMap;
    localStorage.setItem("canvasMiniMapOpen", String(state.showMiniMap));
    applyCanvasChrome();
    setStatus(state.showMiniMap ? "已打开小地图。" : "已关闭小地图。");
  });
}

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
// shareButton / rechargeButton 已在本地软件模式移除

// ─── 设置弹窗事件 ────────────────────────────────────────────────────────
if (settingsButton) settingsButton.addEventListener("click", openSettings);
if (settingsCloseButton) settingsCloseButton.addEventListener("click", closeSettings);
if (settingsModal) settingsModal.addEventListener("click", (e) => {
  if (e.target === settingsModal) closeSettings();
});
if (settingsKeyToggle) settingsKeyToggle.addEventListener("click", () => {
  const isPassword = settingsApiKey.type === "password";
  settingsApiKey.type = isPassword ? "text" : "password";
  settingsKeyToggle.textContent = isPassword ? "隐藏" : "显示";
});
if (settingsSaveButton) settingsSaveButton.addEventListener("click", async () => {
  const key = settingsApiKey.value.trim();
  const url = settingsComfyUrl ? settingsComfyUrl.value.trim() : "";
  if (!key && !url) {
    settingsMessage.textContent = "请填写 API 密钥。";
    return;
  }
  settingsSaveButton.disabled = true;
  settingsMessage.textContent = "保存中…";
  try {
    const payload = {};
    if (key) payload.tikpanApiKey = key;
    if (url) payload.comfyUrl = url;
    const response = await fetch("/api/config", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!data.ok) throw new Error(data.error || "保存失败");
    settingsMessage.textContent = "";
    settingsApiKey.value = "";
    closeSettings();
    await loadLocalConfig();
    toast("API 密钥已保存，立即生效", "success");
    setStatus("API 密钥已保存。");
  } catch (error) {
    settingsMessage.textContent = error.message;
  } finally {
    settingsSaveButton.disabled = false;
  }
});

applyTheme(state.theme);
applyCanvasChrome();
setProjectName(projectTitleInput.value || projectNameInput.value, { persist: false });
renderCamera();
restoreLocal();
loadProvider();
loadProfiles();
loadCheckpoints();
loadFactoryWorkflows();
loadLocalConfig().then(loadAssets);
