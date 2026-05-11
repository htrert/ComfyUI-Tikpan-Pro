let adminState = {
  config: null,
  profiles: [],
};

const notice = document.getElementById("adminNotice");
const rawConfig = document.getElementById("rawConfig");

function setNotice(text) {
  notice.textContent = text;
}

async function apiJson(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok || data.ok === false) throw new Error(data.error || "请求失败");
  return data;
}

function profileOptions(selected = "") {
  return adminState.profiles.map((profile) => (
    `<option value="${profile.id}" ${profile.id === selected ? "selected" : ""}>${profile.name} (${profile.id})</option>`
  )).join("");
}

function input(name, value = "", placeholder = "") {
  return `<label>${name}<input data-key="${name}" value="${String(value ?? "").replace(/"/g, "&quot;")}" placeholder="${placeholder}"></label>`;
}

function checkbox(name, value = false) {
  return `<label class="checkbox-field">${name}<input data-key="${name}" type="checkbox" ${value ? "checked" : ""}></label>`;
}

function readCard(card) {
  const obj = {};
  card.querySelectorAll("[data-key]").forEach((control) => {
    const key = control.dataset.key;
    if (control.type === "checkbox") obj[key] = control.checked;
    else if (control.type === "number") obj[key] = Number(control.value || 0);
    else obj[key] = control.value;
  });
  return obj;
}

function renderOverview() {
  const cfg = adminState.config;
  document.getElementById("profileCount").textContent = adminState.profiles.length;
  document.getElementById("channelCount").textContent = cfg.channels.length;
  document.getElementById("routeCount").textContent = cfg.routes.length;
  document.getElementById("pricingCount").textContent = cfg.pricing.length;
  document.getElementById("profileTable").innerHTML = `
    <table>
      <thead><tr><th>ID</th><th>名称</th><th>分组</th><th>引擎</th><th>媒体</th></tr></thead>
      <tbody>
        ${adminState.profiles.map((p) => `<tr><td><code>${p.id}</code></td><td>${p.name}</td><td>${p.group || ""}</td><td>${p.engine || ""}</td><td>${p.mediaType || ""}</td></tr>`).join("")}
      </tbody>
    </table>
  `;
}

function renderChannels() {
  document.getElementById("channelsEditor").innerHTML = adminState.config.channels.map((channel, index) => `
    <article class="config-card" data-index="${index}" data-kind="channels">
      <div class="config-card-head"><strong>${channel.name || channel.key || "渠道"}</strong><button data-remove>删除</button></div>
      <div class="config-form">
        ${input("key", channel.key, "newapi-main")}
        ${input("name", channel.name, "New API 主渠道")}
        ${input("providerType", channel.providerType, "openai-compatible / new-api / sub2api")}
        ${input("baseUrl", channel.baseUrl, "https://api.example.com")}
        ${input("apiKeyEnv", channel.apiKeyEnv, "环境变量名，不直接存 key")}
        <label>priority<input data-key="priority" type="number" value="${channel.priority ?? 100}"></label>
        ${checkbox("enabled", channel.enabled !== false)}
        <label class="wide">notes<textarea data-key="notes" rows="3">${channel.notes || ""}</textarea></label>
      </div>
    </article>
  `).join("");
}

function renderRoutes() {
  document.getElementById("routesEditor").innerHTML = adminState.config.routes.map((route, index) => `
    <article class="config-card" data-index="${index}" data-kind="routes">
      <div class="config-card-head"><strong>${route.profileId || "模型路由"}</strong><button data-remove>删除</button></div>
      <div class="config-form">
        <label>profileId<select data-key="profileId">${profileOptions(route.profileId)}</select></label>
        ${input("channelKey", route.channelKey, "tikpan-main")}
        ${input("upstreamModel", route.upstreamModel, "gpt-image-2")}
        ${input("endpoint", route.endpoint, "/v1/images/generations")}
        ${checkbox("enabled", route.enabled !== false)}
      </div>
    </article>
  `).join("");
}

function renderPricing() {
  document.getElementById("pricingEditor").innerHTML = adminState.config.pricing.map((price, index) => `
    <article class="config-card" data-index="${index}" data-kind="pricing">
      <div class="config-card-head"><strong>${price.profileId || "计价规则"}</strong><button data-remove>删除</button></div>
      <div class="config-form">
        <label>profileId<select data-key="profileId">${profileOptions(price.profileId)}</select></label>
        ${input("billingMode", price.billingMode, "resolution / flat / per_unit")}
        <label>credits1k<input data-key="credits1k" type="number" value="${price.credits1k ?? 5}"></label>
        <label>credits2k<input data-key="credits2k" type="number" value="${price.credits2k ?? 8}"></label>
        <label>credits4k<input data-key="credits4k" type="number" value="${price.credits4k ?? 15}"></label>
        <label>costPerUnit<input data-key="costPerUnit" type="number" step="0.0001" value="${price.costPerUnit ?? 0}"></label>
        ${checkbox("enabled", price.enabled !== false)}
      </div>
    </article>
  `).join("");
}

function renderSettings() {
  const s = adminState.config.settings || {};
  document.getElementById("settingsEditor").innerHTML = `
    ${input("siteName", s.siteName, "Canvas Model Studio")}
    ${input("defaultProfileId", s.defaultProfileId, "tikpan-gpt-image-2")}
    ${input("assetStorage", s.assetStorage, "local / s3 / r2 / oss")}
    ${checkbox("requireLoginForGenerate", Boolean(s.requireLoginForGenerate))}
    <label class="wide">adminNote<textarea data-key="adminNote" rows="4">${s.adminNote || ""}</textarea></label>
  `;
}

function syncFromEditors() {
  document.querySelectorAll(".config-card").forEach((card) => {
    const kind = card.dataset.kind;
    const index = Number(card.dataset.index);
    adminState.config[kind][index] = readCard(card);
  });
  const settingsEditor = document.getElementById("settingsEditor");
  if (settingsEditor.children.length) {
    adminState.config.settings = readCard(settingsEditor);
  }
  try {
    const raw = JSON.parse(rawConfig.value || "{}");
    if (raw.channels || raw.routes || raw.pricing || raw.settings) adminState.config = raw;
  } catch {
    // Ignore while the user is editing non-JSON tabs.
  }
}

function renderAll() {
  renderOverview();
  renderChannels();
  renderRoutes();
  renderPricing();
  renderSettings();
  rawConfig.value = JSON.stringify(adminState.config, null, 2);
}

async function loadConfig() {
  setNotice("正在读取配置...");
  const data = await apiJson("/api/admin/config");
  adminState.config = data.config;
  adminState.profiles = data.profiles || [];
  renderAll();
  setNotice("配置已加载。修改后点击右上角保存。");
}

async function saveConfig() {
  syncFromEditors();
  rawConfig.value = JSON.stringify(adminState.config, null, 2);
  const data = await apiJson("/api/admin/config", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ config: adminState.config }),
  });
  adminState.config = data.config;
  renderAll();
  setNotice("配置已保存。");
}

document.querySelectorAll("[data-admin-tab]").forEach((button) => {
  button.addEventListener("click", () => {
    const tab = button.dataset.adminTab;
    document.querySelectorAll("[data-admin-tab]").forEach((item) => item.classList.toggle("active", item.dataset.adminTab === tab));
    document.querySelectorAll(".admin-tab").forEach((panel) => panel.classList.toggle("active", panel.id === `tab-${tab}`));
  });
});

document.addEventListener("click", (event) => {
  const removeButton = event.target.closest("[data-remove]");
  if (!removeButton) return;
  const card = removeButton.closest(".config-card");
  adminState.config[card.dataset.kind].splice(Number(card.dataset.index), 1);
  renderAll();
});

document.getElementById("addChannelButton").addEventListener("click", () => {
  adminState.config.channels.push({ key: "new-channel", name: "新渠道", providerType: "openai-compatible", baseUrl: "", apiKeyEnv: "", priority: 100, enabled: true, notes: "" });
  renderAll();
});

document.getElementById("addRouteButton").addEventListener("click", () => {
  adminState.config.routes.push({ profileId: adminState.profiles[0]?.id || "", channelKey: "tikpan-main", upstreamModel: "", endpoint: "", enabled: true });
  renderAll();
});

document.getElementById("addPricingButton").addEventListener("click", () => {
  adminState.config.pricing.push({ profileId: adminState.profiles[0]?.id || "", billingMode: "resolution", credits1k: 5, credits2k: 8, credits4k: 15, costPerUnit: 0, enabled: true });
  renderAll();
});

document.getElementById("reloadConfigButton").addEventListener("click", loadConfig);
document.getElementById("saveConfigButton").addEventListener("click", saveConfig);

loadConfig().catch((error) => setNotice(`读取失败：${error.message}`));
