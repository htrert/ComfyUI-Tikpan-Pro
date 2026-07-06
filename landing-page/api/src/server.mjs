import { createServer } from "node:http";
import { createHash, createHmac, timingSafeEqual } from "node:crypto";
import {
  advanceTask,
  cancelTask,
  createTask,
  getUsageSummary,
  mapPayload,
  problem,
  publicWallet,
  quoteTask,
  refundTask,
  retryTask,
  selectRoute,
  syncTaskProgress,
  topUpWallet,
} from "./orchestrator.mjs";
import { config } from "./config.mjs";
import { encryptSecret, redactSecret } from "./secrets.mjs";
import { checkDatabaseConnection, closeDb } from "./db/client.mjs";
import {
  assertSupportedRepositoryMode,
  getRepositoryStatus,
  initializeRepositories,
  repositories,
} from "./repositories/index.mjs";
import { createQueueWorker } from "./worker/queueWorker.mjs";

const {
  assetMetadata: assetMetadataRepository,
  apiKeys: apiKeysRepository,
  audit: auditRepository,
  billing: billingRepository,
  catalog: catalogRepository,
  media: mediaRepository,
  paymentProviders: paymentProvidersRepository,
  paymentOrders: paymentOrdersRepository,
  presets: presetsRepository,
  projects: projectsRepository,
  providerKeys: providerKeysRepository,
  tasks: tasksRepository,
  usage: usageRepository,
  users: usersRepository,
  webhooks: webhooksRepository,
} = repositories;

const port = config.port;
const queueWorker = createQueueWorker();
const allowedChannelStatuses = new Set(["active", "degraded", "disabled"]);
const allowedChannelRoles = new Set(["primary", "backup", "cheap", "fast", "quality"]);
const allowedMappingTransforms = new Set(["direct", "map", "default", "omit", "template"]);
const allowedSchemaFieldTypes = new Set(["textarea", "text", "select", "segmented", "slider", "file", "switch"]);
const allowedProviderKinds = new Set(["official", "relay", "private"]);
const allowedProviderStatuses = new Set(["active", "degraded", "testing", "disabled"]);
const allowedProviderAuthTypes = new Set(["bearer", "custom_header", "none"]);
const allowedProviderModelStatuses = new Set(["active", "degraded", "testing", "disabled"]);
const allowedModalities = new Set(["image", "video", "chat", "audio", "workflow"]);
const allowedPlatformTiers = new Set(["lite", "standard", "pro", "ultra", "Lite", "Standard", "Pro", "Ultra"]);
const allowedModelCategoryStatuses = new Set(["draft", "published", "archived"]);
const allowedBillingPlanStatuses = new Set(["active", "archived"]);
const allowedSubscriptionStatuses = new Set(["trialing", "active", "past_due", "cancelled", "expired"]);
const allowedWebhookEvents = new Set(["task.completed", "task.failed", "task.cancelled", "billing.refunded"]);
const allowedWebhookStatuses = new Set(["active", "disabled"]);
const allowedUserStatuses = new Set(["active", "suspended", "deleted"]);
const allowedPaymentProviderKinds = new Set(["mock", "manual", "alipay", "wechat", "stripe", "custom"]);
const allowedPaymentProviderStatuses = new Set(["active", "testing", "disabled"]);
const allowedPaymentCheckoutModes = new Set(["mock", "hosted", "qr_code", "manual", "redirect"]);
const allowedAssetReviewStatuses = new Set(["candidate", "approved", "needs_changes", "archived"]);
const allowedProjectTypes = new Set(["general", "image_campaign", "video_storyboard", "audio_album", "agent_workspace"]);
const allowedProjectStatuses = new Set(["draft", "active", "archived"]);

const server = createServer(async (req, res) => {
  try {
    await route(req, res);
  } catch (error) {
    sendProblem(res, error);
  }
});

initializeRepositories()
  .then(() => {
    server.listen(port, () => {
      if (config.worker.enabled) {
        queueWorker.start();
      }
      console.log(`Tikpan platform API demo listening on http://localhost:${port}`);
    });
  })
  .catch((error) => {
    console.error("Failed to initialize Tikpan API repositories.");
    console.error(error);
    process.exit(1);
  });

process.on("SIGTERM", () => {
  queueWorker.stop();
  server.close(() => {
    void closeDb().finally(() => process.exit(0));
  });
});

process.on("SIGINT", () => {
  queueWorker.stop();
  server.close(() => {
    void closeDb().finally(() => process.exit(0));
  });
});

async function route(req, res) {
  const url = new URL(req.url ?? "/", `http://${req.headers.host ?? "localhost"}`);
  const method = req.method ?? "GET";

  if (method === "OPTIONS") {
    sendJson(res, 204, null);
    return;
  }

  if (method === "GET" && url.pathname === "/health") {
    sendJson(res, 200, {
      data: {
        status: "ok",
        repository: getRepositoryStatus(),
        worker: queueWorker.getStatus(),
        providers: catalogRepository.listProviders().length,
        platform_models: catalogRepository.listPlatformModels().length,
        tasks: (await tasksRepository.list()).length,
      },
    });
    return;
  }

  if (method === "GET" && url.pathname === "/health/readiness") {
    const database = await checkDatabaseConnection();
    sendJson(res, 200, {
      data: {
        status: database.ok ? "ready" : "not_ready",
        repository: getRepositoryStatus(),
        worker: queueWorker.getStatus(),
        database,
      },
    });
    return;
  }

  assertAdminAuthorized(req, url);

  assertSupportedRepositoryMode();

  if (method === "GET" && url.pathname === "/v1/capabilities") {
    sendJson(res, 200, {
      data: {
        categories: catalogRepository
          .listModelCategories()
          .filter((category) => category.visible && category.status !== "archived")
          .map(publicModelCategory),
        models: catalogRepository
        .listPlatformModels()
        .filter((model) => model.visible)
        .map(publicPlatformModel),
      },
    });
    return;
  }

  if (method === "POST" && url.pathname === "/v1/auth/register") {
    const body = await readJson(req);
    const user = await usersRepository.upsert(buildUserUpsert(body));
    await billingRepository.getWallet(user.id);

    const planId = String(body.plan_id ?? body.planId ?? "starter").trim() || "starter";
    if (await usageRepository.getBillingPlan(planId)) {
      await usageRepository.upsertUserSubscription(
        buildUserSubscriptionUpsert({
          user_id: user.id,
          plan_id: planId,
          status: "active",
          renews_at: nextMonthIso(),
        })
      );
    }

    const key = await createApiKey({
      userId: user.id,
      name: body.key_name ?? "User console session",
      scopes: ["tasks:create", "wallet:read"],
    });
    recordAudit({
      actorId: user.id,
      actorType: "user",
      action: "user.registered",
      resourceType: "user",
      resourceId: user.id,
      userId: user.id,
      summary: `User ${user.id} registered from public console.`,
      metadata: { email: user.email, plan_id: planId },
    });
    sendJson(res, 201, { data: await publicUserSession(user, key) });
    return;
  }

  if (method === "POST" && url.pathname === "/v1/auth/login") {
    const body = await readJson(req);
    const userId = String(body.user_id ?? body.userId ?? "").trim();
    if (!userId) {
      throw problem(422, "VALIDATION_ERROR", "User ID is required.");
    }

    const user = await usersRepository.findById(userId);
    if (!user || user.status === "deleted") {
      throw problem(404, "USER_NOT_FOUND", "User does not exist.");
    }
    if (user.status === "suspended") {
      throw problem(403, "USER_SUSPENDED", "This account is suspended.");
    }

    const email = String(body.email ?? "").trim().toLowerCase();
    if (user.email && email && user.email !== email) {
      throw problem(403, "EMAIL_MISMATCH", "Email does not match this account.");
    }

    const key = await createApiKey({
      userId: user.id,
      name: body.key_name ?? "User console session",
      scopes: ["tasks:create", "wallet:read"],
    });

    sendJson(res, 200, { data: await publicUserSession(user, key) });
    return;
  }

  if (method === "GET" && url.pathname === "/v1/me") {
    const userId = await resolveReadUser(req, url.searchParams.get("user_id") ?? "demo_user");
    const user = await usersRepository.findById(userId);
    if (!user || user.status === "deleted") {
      throw problem(404, "USER_NOT_FOUND", "User does not exist.");
    }
    if (user.status === "suspended") {
      throw problem(403, "USER_SUSPENDED", "This account is suspended.");
    }

    sendJson(res, 200, { data: await publicUserProfile(user) });
    return;
  }

  const schemaMatch = url.pathname.match(/^\/v1\/models\/([^/]+)\/schema$/);
  if (method === "GET" && schemaMatch) {
    const model = catalogRepository.getPlatformModel(decodeURIComponent(schemaMatch[1]));
    if (!model) {
      throw problem(404, "MODEL_NOT_FOUND", "Model was not found.");
    }
    sendJson(res, 200, { data: { model: model.id, schema: model.schema } });
    return;
  }

  if (method === "POST" && url.pathname === "/v1/tasks") {
    const body = await readJson(req);
    const authUserId = await resolveTaskUser(req, body);
    const project = await optionalWritableProject(body.project_id ?? body.projectId, authUserId);
    const result = await createTask({
      userId: authUserId,
      model: body.model,
      input: body.input,
      routing: body.routing,
      project: project ? { id: project.id, name: project.name } : null,
    });
    sendJson(res, 201, result);
    return;
  }

  if (method === "POST" && url.pathname === "/v1/tasks/quote") {
    const body = await readJson(req);
    const userId = await resolveReadUser(req, body.user_id ?? "demo_user");
    const result = await quoteTask({
      userId,
      model: body.model,
      input: body.input,
      routing: body.routing,
    });
    sendJson(res, 200, result);
    return;
  }

  if (method === "POST" && url.pathname === "/v1/task-batches") {
    const body = await readJson(req);
    const userId = await resolveTaskUser(req, body);
    const project = await optionalWritableProject(body.project_id ?? body.projectId, userId);
    const items = Array.isArray(body.items) ? body.items.slice(0, 12) : [];

    if (items.length === 0) {
      throw problem(422, "VALIDATION_ERROR", "Task batch requires at least one item.");
    }

    const batchId = normalizeId(body.id, "batch");
    const batchTitle = String(body.title ?? "").trim().slice(0, 120);
    const results = [];
    for (const [index, item] of items.entries()) {
      const itemId = String(item.id ?? `item_${index + 1}`);
      try {
        const created = await createTask({
          userId,
          model: item.model,
          input: item.input,
          routing: item.routing,
          project: project ? { id: project.id, name: project.name } : null,
          batch: {
            id: batchId,
            title: batchTitle,
            itemId,
          },
        });
        results.push({
          id: itemId,
          status: "created",
          task: created.data,
        });
      } catch (error) {
        results.push({
          id: itemId,
          status: "failed",
          error: publicProblem(error),
        });
      }
    }

    const createdCount = results.filter((item) => item.status === "created").length;
    recordAudit({
      actorType: "user",
      actorId: userId,
      action: "task_batch.created",
      resourceType: "task_batch",
      resourceId: batchId,
      userId,
      summary: `Task batch ${batchId} submitted with ${createdCount}/${results.length} created.`,
      metadata: {
        title: body.title ?? null,
        created_count: createdCount,
        failed_count: results.length - createdCount,
      },
    });
    sendJson(res, createdCount > 0 ? 201 : 422, {
      data: {
        batch_id: batchId,
        title: batchTitle,
        status: createdCount === results.length ? "created" : createdCount > 0 ? "partial" : "failed",
        created_count: createdCount,
        failed_count: results.length - createdCount,
        items: results,
      },
    });
    return;
  }

  if (method === "GET" && url.pathname === "/v1/task-batches") {
    const userId = await resolveReadUser(req, url.searchParams.get("user_id") ?? "demo_user");
    const limit = boundedNumber(url.searchParams.get("limit") ?? 20, 1, 100, "Limit must be between 1 and 100.");
    sendJson(res, 200, { data: await publicTaskBatches(userId, limit) });
    return;
  }

  if (method === "GET" && url.pathname === "/v1/tasks") {
    const userId = await resolveReadUser(req, url.searchParams.get("user_id") ?? "demo_user");
    const limit = boundedNumber(url.searchParams.get("limit") ?? 50, 1, 200, "Limit must be between 1 and 200.");
    const projectId = url.searchParams.get("project_id");
    const data = tasksRepository
      .list()
      .filter((task) => task.userId === userId)
      .filter((task) => !projectId || task.projectId === projectId)
      .slice()
      .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
      .slice(0, limit)
      .map(publicTask);
    sendJson(res, 200, { data });
    return;
  }

  if (method === "GET" && url.pathname === "/v1/assets") {
    const userId = await resolveReadUser(req, url.searchParams.get("user_id") ?? "demo_user");
    const limit = boundedNumber(url.searchParams.get("limit") ?? 50, 1, 100, "Limit must be between 1 and 100.");
    sendJson(res, 200, { data: await publicAssetLibrary(userId, limit, { projectId: url.searchParams.get("project_id") }) });
    return;
  }

  const assetMatch = url.pathname.match(/^\/v1\/assets\/([^/]+)$/);
  if (method === "PATCH" && assetMatch) {
    const body = await readJson(req);
    const userId = await resolveReadUser(req, body.user_id ?? "demo_user");
    const task = await tasksRepository.findById(decodeURIComponent(assetMatch[1]));
    if (!task || task.userId !== userId || task.status !== "completed") {
      throw problem(404, "ASSET_NOT_FOUND", "Asset does not exist.");
    }

    const metadata = await assetMetadataRepository.upsert(await buildAssetMetadata(body, task, userId));
    recordAudit({
      actorType: "user",
      actorId: userId,
      action: "asset.updated",
      resourceType: "asset",
      resourceId: task.id,
      userId,
      summary: `Asset ${task.id} updated.`,
      metadata: { favorite: metadata.favorite, title: metadata.title },
    });
    sendJson(res, 200, { data: publicAssetItem(task, await mediaRepository.listByTask(task.id), metadata) });
    return;
  }

  if (method === "GET" && url.pathname === "/v1/projects") {
    const userId = await resolveReadUser(req, url.searchParams.get("user_id") ?? "demo_user");
    const limit = boundedNumber(url.searchParams.get("limit") ?? 50, 1, 100, "Limit must be between 1 and 100.");
    const projects = await projectsRepository.list({ userId, limit });
    sendJson(res, 200, {
      data: await Promise.all(projects.map((project) => publicProjectSummary(project))),
    });
    return;
  }

  if (method === "POST" && url.pathname === "/v1/projects") {
    const body = await readJson(req);
    const userId = await resolveReadUser(req, body.user_id ?? "demo_user");
    const project = await projectsRepository.create(buildProject(body, userId));
    recordAudit({
      actorType: "user",
      actorId: userId,
      action: "project.created",
      resourceType: "project",
      resourceId: project.id,
      userId,
      summary: `Project ${project.name} created.`,
      metadata: { type: project.type, status: project.status },
    });
    sendJson(res, 201, { data: await publicProjectDetail(project) });
    return;
  }

  const projectAssetsMatch = url.pathname.match(/^\/v1\/projects\/([^/]+)\/assets$/);
  if (method === "GET" && projectAssetsMatch) {
    const userId = await resolveReadUser(req, url.searchParams.get("user_id") ?? "demo_user");
    const project = await assertProjectReadable(decodeURIComponent(projectAssetsMatch[1]), userId);
    const limit = boundedNumber(url.searchParams.get("limit") ?? 50, 1, 100, "Limit must be between 1 and 100.");
    sendJson(res, 200, { data: await publicAssetLibrary(userId, limit, { projectId: project.id }) });
    return;
  }

  if (method === "POST" && projectAssetsMatch) {
    const body = await readJson(req);
    const userId = await resolveTaskUser(req, body);
    const project = await assertProjectWritable(decodeURIComponent(projectAssetsMatch[1]), userId);
    const { task, mediaAsset, metadata } = buildManualProjectAsset(body, project, userId);

    await tasksRepository.create(task);
    await mediaRepository.createMany([mediaAsset]);
    const savedMetadata = await assetMetadataRepository.upsert(metadata);
    await touchProject(project);

    recordAudit({
      actorType: "user",
      actorId: userId,
      action: "project_asset.created",
      resourceType: "asset",
      resourceId: task.id,
      userId,
      summary: `Manual asset ${metadata.title || task.id} added to project ${project.name}.`,
      metadata: {
        project_id: project.id,
        source_url: mediaAsset.sourceUrl,
        mime_type: mediaAsset.mimeType,
      },
    });

    sendJson(res, 201, { data: publicAssetItem(task, [mediaAsset], savedMetadata) });
    return;
  }

  const projectTasksMatch = url.pathname.match(/^\/v1\/projects\/([^/]+)\/tasks$/);
  if (method === "GET" && projectTasksMatch) {
    const userId = await resolveReadUser(req, url.searchParams.get("user_id") ?? "demo_user");
    const project = await assertProjectReadable(decodeURIComponent(projectTasksMatch[1]), userId);
    const limit = boundedNumber(url.searchParams.get("limit") ?? 50, 1, 200, "Limit must be between 1 and 200.");
    const tasks = await tasksRepository.listByUser(userId);
    sendJson(res, 200, {
      data: tasks
        .filter((task) => task.projectId === project.id)
        .slice()
        .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
        .slice(0, limit)
        .map(publicTask),
    });
    return;
  }

  if (method === "POST" && projectTasksMatch) {
    const body = await readJson(req);
    const userId = await resolveTaskUser(req, { ...body, user_id: body.user_id ?? "demo_user" });
    const project = await assertProjectWritable(decodeURIComponent(projectTasksMatch[1]), userId);
    const result = await createTask({
      userId,
      model: body.model,
      input: body.input,
      routing: body.routing,
      project: { id: project.id, name: project.name },
    });
    await touchProject(project);
    sendJson(res, 201, result);
    return;
  }

  const projectMatch = url.pathname.match(/^\/v1\/projects\/([^/]+)$/);
  if (method === "GET" && projectMatch) {
    const userId = await resolveReadUser(req, url.searchParams.get("user_id") ?? "demo_user");
    const project = await assertProjectReadable(decodeURIComponent(projectMatch[1]), userId);
    sendJson(res, 200, { data: await publicProjectDetail(project) });
    return;
  }

  if (method === "PATCH" && projectMatch) {
    const body = await readJson(req);
    const userId = await resolveReadUser(req, body.user_id ?? "demo_user");
    const existing = await assertProjectWritable(decodeURIComponent(projectMatch[1]), userId);
    const project = await projectsRepository.save(buildProject(body, userId, existing));
    recordAudit({
      actorType: "user",
      actorId: userId,
      action: "project.updated",
      resourceType: "project",
      resourceId: project.id,
      userId,
      summary: `Project ${project.name} updated.`,
      metadata: { status: project.status },
    });
    sendJson(res, 200, { data: await publicProjectDetail(project) });
    return;
  }

  if (method === "DELETE" && projectMatch) {
    const body = await readJson(req);
    const userId = await resolveReadUser(req, body.user_id ?? "demo_user");
    const existing = await assertProjectWritable(decodeURIComponent(projectMatch[1]), userId);
    const now = new Date().toISOString();
    const project = await projectsRepository.save({
      ...existing,
      status: "archived",
      archivedAt: now,
      updatedAt: now,
    });
    recordAudit({
      actorType: "user",
      actorId: userId,
      action: "project.archived",
      resourceType: "project",
      resourceId: project.id,
      userId,
      summary: `Project ${project.name} archived.`,
    });
    sendJson(res, 200, { data: await publicProjectDetail(project) });
    return;
  }

  const taskMatch = url.pathname.match(/^\/v1\/tasks\/([^/]+)$/);
  if (method === "GET" && taskMatch) {
    const task = await tasksRepository.findById(taskMatch[1]);
    if (!task) {
      throw problem(404, "TASK_NOT_FOUND", "Task does not exist.");
    }
    await assertTaskReadable(req, task);
    sendJson(res, 200, { data: publicTask(await syncTaskProgress(task)) });
    return;
  }

  const taskAdvanceMatch = url.pathname.match(/^\/v1\/tasks\/([^/]+)\/status$/);
  if (method === "POST" && taskAdvanceMatch) {
    const body = await readJson(req);
    const task = await advanceTask(taskAdvanceMatch[1], body.status);
    sendJson(res, 200, { data: publicTask(task) });
    return;
  }

  const taskCancelMatch = url.pathname.match(/^\/v1\/tasks\/([^/]+)\/cancel$/);
  if (method === "POST" && taskCancelMatch) {
    const body = await readJson(req);
    const existingTask = await tasksRepository.findById(taskCancelMatch[1]);
    if (!existingTask) {
      throw problem(404, "TASK_NOT_FOUND", "Task does not exist.");
    }
    await assertTaskReadable(req, existingTask);
    const task = await cancelTask(taskCancelMatch[1], body.reason ?? "Task cancelled by user.");
    sendJson(res, 200, { data: publicTask(task) });
    return;
  }

  const taskRetryMatch = url.pathname.match(/^\/v1\/tasks\/([^/]+)\/retry$/);
  if (method === "POST" && taskRetryMatch) {
    const existingTask = await tasksRepository.findById(taskRetryMatch[1]);
    if (!existingTask) {
      throw problem(404, "TASK_NOT_FOUND", "Task does not exist.");
    }
    await assertTaskReadable(req, existingTask);
    const result = await retryTask(taskRetryMatch[1]);
    sendJson(res, 201, result);
    return;
  }

  if (method === "POST" && url.pathname === "/v1/routes/preview") {
    const body = await readJson(req);
    const model = catalogRepository.getPlatformModel(body.model);
    if (!model) {
      throw problem(404, "MODEL_NOT_FOUND", "Model was not found.");
    }
    const input = body.input ?? {};
    const decision = selectRoute(body.model, input, body.routing?.mode ?? "balanced");
    sendJson(res, 200, { data: routePreview(decision, input) });
    return;
  }

  if (method === "GET" && url.pathname === "/v1/wallet") {
    const userId = await resolveReadUser(req, url.searchParams.get("user_id") ?? "demo_user");
    sendJson(res, 200, {
      data: {
        wallet: publicWallet(await billingRepository.getWallet(userId)),
        ledger: (await publicLedger(userId)).slice(-8).reverse(),
      },
    });
    return;
  }

  if (method === "GET" && url.pathname === "/v1/usage") {
    const authUserId = await resolveReadUser(req, url.searchParams.get("user_id") ?? "demo_user");
    sendJson(res, 200, { data: await getUsageSummary(authUserId) });
    return;
  }

  if (method === "GET" && url.pathname === "/v1/billing-plans") {
    const plans = (await usageRepository.listBillingPlans()).filter((plan) => (plan.status ?? "active") === "active");
    sendJson(res, 200, { data: plans });
    return;
  }

  if (method === "POST" && url.pathname === "/v1/subscription") {
    const body = await readJson(req);
    const userId = await resolveReadUser(req, body.user_id ?? "demo_user");
    const planId = String(body.plan_id ?? body.planId ?? "").trim();
    const plan = await usageRepository.getBillingPlan(planId);
    if (!plan || (plan.status ?? "active") !== "active") {
      throw problem(422, "VALIDATION_ERROR", "Active billing plan does not exist.");
    }

    const existing = await usageRepository.getUserSubscription(userId);
    const subscription = await usageRepository.upsertUserSubscription({
      id: existing?.id ?? normalizeId(body.id, "sub"),
      userId,
      planId,
      status: "active",
      renewsAt: existing?.renewsAt ?? nextMonthIso(),
      cancelledAt: null,
    });
    recordAudit({
      actorType: "user",
      actorId: userId,
      action: "subscription.changed",
      resourceType: "user_subscription",
      resourceId: subscription.id ?? `${userId}:${planId}`,
      userId,
      summary: `Subscription changed to ${plan.name}.`,
      metadata: { plan_id: planId },
    });
    sendJson(res, 200, {
      data: {
        subscription,
        plan,
        usage: await getUsageSummary(userId),
      },
    });
    return;
  }

  if (method === "GET" && url.pathname === "/v1/presets") {
    const userId = await resolveReadUser(req, url.searchParams.get("user_id") ?? "demo_user");
    const limit = boundedNumber(url.searchParams.get("limit") ?? 50, 1, 100, "Limit must be between 1 and 100.");
    sendJson(res, 200, { data: presetsRepository.list({ userId, limit }).map(publicPreset) });
    return;
  }

  if (method === "POST" && url.pathname === "/v1/presets") {
    const body = await readJson(req);
    const userId = await resolveReadUser(req, body.user_id ?? "demo_user");
    const preset = presetsRepository.create(buildPreset(body, userId));
    recordAudit({
      actorType: "user",
      actorId: userId,
      action: "preset.created",
      resourceType: "preset",
      resourceId: preset.id,
      userId,
      summary: `Preset ${preset.name} created.`,
      metadata: { model: preset.platformModelId, route_mode: preset.routeMode },
    });
    sendJson(res, 201, { data: publicPreset(preset) });
    return;
  }

  const presetMatch = url.pathname.match(/^\/v1\/presets\/([^/]+)$/);
  if (method === "PATCH" && presetMatch) {
    const body = await readJson(req);
    const userId = await resolveReadUser(req, body.user_id ?? "demo_user");
    const preset = await assertPresetWritable(presetMatch[1], userId);
    const updated = presetsRepository.save(buildPreset(body, userId, preset));
    recordAudit({
      actorType: "user",
      actorId: userId,
      action: "preset.updated",
      resourceType: "preset",
      resourceId: updated.id,
      userId,
      summary: `Preset ${updated.name} updated.`,
      metadata: { model: updated.platformModelId, route_mode: updated.routeMode },
    });
    sendJson(res, 200, { data: publicPreset(updated) });
    return;
  }

  if (method === "DELETE" && presetMatch) {
    const userId = await resolveReadUser(req, url.searchParams.get("user_id") ?? "demo_user");
    const preset = await assertPresetWritable(presetMatch[1], userId);
    presetsRepository.delete(preset.id);
    recordAudit({
      actorType: "user",
      actorId: userId,
      action: "preset.deleted",
      resourceType: "preset",
      resourceId: preset.id,
      userId,
      summary: `Preset ${preset.name} deleted.`,
      metadata: { model: preset.platformModelId },
    });
    sendJson(res, 204, null);
    return;
  }

  const presetUseMatch = url.pathname.match(/^\/v1\/presets\/([^/]+)\/use$/);
  if (method === "POST" && presetUseMatch) {
    const body = await readJson(req);
    const userId = await resolveReadUser(req, body.user_id ?? "demo_user");
    const preset = await assertPresetWritable(presetUseMatch[1], userId);
    preset.usageCount = Number(preset.usageCount ?? 0) + 1;
    preset.lastUsedAt = new Date().toISOString();
    preset.updatedAt = new Date().toISOString();
    sendJson(res, 200, { data: publicPreset(presetsRepository.save(preset)) });
    return;
  }

  if (method === "GET" && url.pathname === "/v1/payment-providers") {
    sendJson(res, 200, {
      data: (await paymentProvidersRepository.list({ includeDisabled: false })).map(publicPaymentProvider),
    });
    return;
  }

  if (method === "GET" && url.pathname === "/v1/payment-orders") {
    const userId = await resolveReadUser(req, url.searchParams.get("user_id") ?? "demo_user");
    const limit = boundedNumber(url.searchParams.get("limit") ?? 20, 1, 100, "Limit must be between 1 and 100.");
    sendJson(res, 200, { data: (await paymentOrdersRepository.list({ userId, limit })).map(publicPaymentOrder) });
    return;
  }

  if (method === "POST" && url.pathname === "/v1/payment-orders") {
    const body = await readJson(req);
    const userId = await resolveReadUser(req, body.user_id ?? "demo_user");
    const order = await paymentOrdersRepository.create(await buildPaymentOrder(body, userId));
    recordAudit({
      actorType: "user",
      actorId: userId,
      action: "payment_order.created",
      resourceType: "payment_order",
      resourceId: order.id,
      userId,
      summary: `Payment order ${order.id} created.`,
      metadata: { amount: order.amount, provider: order.provider, status: order.status },
    });
    sendJson(res, 201, { data: publicPaymentOrder(order) });
    return;
  }

  const paymentConfirmMatch = url.pathname.match(/^\/v1\/payment-orders\/([^/]+)\/confirm$/);
  if (method === "POST" && paymentConfirmMatch) {
    const body = await readJson(req);
    const order = await paymentOrdersRepository.findById(decodeURIComponent(paymentConfirmMatch[1]));
    if (!order) {
      throw problem(404, "PAYMENT_ORDER_NOT_FOUND", "Payment order does not exist.");
    }
    const userId = await resolveReadUser(req, order.userId);
    if (order.userId !== userId) {
      throw problem(404, "PAYMENT_ORDER_NOT_FOUND", "Payment order does not exist.");
    }

    const result = await confirmPaymentOrder(order, {
      providerTransactionId: body.provider_transaction_id ?? body.providerTransactionId,
      source: "user_console",
    });
    sendJson(res, 200, { data: result });
    return;
  }

  const paymentCancelMatch = url.pathname.match(/^\/v1\/payment-orders\/([^/]+)\/cancel$/);
  if (method === "POST" && paymentCancelMatch) {
    const order = await paymentOrdersRepository.findById(decodeURIComponent(paymentCancelMatch[1]));
    if (!order) {
      throw problem(404, "PAYMENT_ORDER_NOT_FOUND", "Payment order does not exist.");
    }
    const userId = await resolveReadUser(req, order.userId);
    if (order.userId !== userId) {
      throw problem(404, "PAYMENT_ORDER_NOT_FOUND", "Payment order does not exist.");
    }

    sendJson(res, 200, { data: publicPaymentOrder(await closePaymentOrder(order, "cancelled", "user_console")) });
    return;
  }

  const paymentWebhookMatch = url.pathname.match(/^\/v1\/payment-webhooks\/([^/]+)$/);
  if (method === "POST" && paymentWebhookMatch) {
    const webhookProviderId = decodeURIComponent(paymentWebhookMatch[1]);
    const { raw, body } = await readSignedJson(req);
    const orderId = String(body.order_id ?? body.orderId ?? "").trim();
    const order = await paymentOrdersRepository.findById(orderId);
    if (!order) {
      throw problem(404, "PAYMENT_ORDER_NOT_FOUND", "Payment order does not exist.");
    }
    if (webhookProviderId !== order.provider) {
      throw problem(404, "PAYMENT_ORDER_NOT_FOUND", "Payment order does not exist for this payment provider.");
    }

    const paymentProvider = await paymentProvidersRepository.findById(order.provider);
    assertPaymentWebhookSignature(req, raw, paymentProvider);

    if (Number(body.amount ?? order.amount) !== Number(order.amount)) {
      throw problem(422, "PAYMENT_AMOUNT_MISMATCH", "Payment webhook amount does not match the order.");
    }
    if (body.status && String(body.status).trim() !== "paid") {
      sendJson(res, 200, {
        data: {
          order: publicPaymentOrder(await closePaymentOrder(order, "cancelled", "payment_webhook")),
          handled: "closed",
        },
      });
      return;
    }

    const result = await confirmPaymentOrder(order, {
      providerTransactionId: body.provider_transaction_id ?? body.providerTransactionId,
      source: "payment_webhook",
      actorId: paymentProvider?.id ?? order.provider,
      actorType: "system",
    });
    sendJson(res, 200, { data: { ...result, handled: "credited" } });
    return;
  }

  if (method === "POST" && url.pathname === "/v1/wallet/top-ups") {
    const body = await readJson(req);
    const userId = await resolveReadUser(req, body.user_id ?? "demo_user");
    const wallet = await topUpWallet(userId, body.amount, body.note ?? "Balance top-up");
    recordAudit({
      actorType: "user",
      actorId: userId,
      action: "wallet.self_top_up",
      resourceType: "wallet",
      resourceId: userId,
      userId,
      summary: `Self top-up saved for ${userId}.`,
      metadata: { amount: Number(body.amount), note: body.note ?? "Balance top-up" },
    });
    sendJson(res, 201, {
      data: {
        wallet: publicWallet(wallet),
        ledger: (await publicLedger(userId)).slice(-8).reverse(),
      },
    });
    return;
  }

  if (method === "GET" && url.pathname === "/admin/providers") {
    sendJson(res, 200, { data: catalogRepository.listProviders() });
    return;
  }

  if (method === "GET" && url.pathname === "/admin/provider-keys") {
    const providerId = url.searchParams.get("provider_id") ?? url.searchParams.get("providerId");
    const keys = providerId ? await providerKeysRepository.listByProvider(providerId) : await providerKeysRepository.list();
    sendJson(res, 200, { data: keys.map(adminProviderKey) });
    return;
  }

  if (method === "POST" && url.pathname === "/admin/provider-keys") {
    const body = await readJson(req);
    const key = await providerKeysRepository.upsert(buildProviderKeyUpsert(body));
    recordAudit({
      action: "provider_key.upserted",
      resourceType: "provider_key",
      resourceId: key.id,
      summary: `Provider key ${key.name} saved.`,
      metadata: { provider_id: key.providerId, status: key.status, rpm: key.rpm, concurrency: key.concurrency },
    });
    sendJson(res, 201, { data: adminProviderKey(key) });
    return;
  }

  const providerKeyMatch = url.pathname.match(/^\/admin\/provider-keys\/([^/]+)$/);
  if (method === "PATCH" && providerKeyMatch) {
    const existing = await providerKeysRepository.findById(decodeURIComponent(providerKeyMatch[1]));
    if (!existing) {
      throw problem(404, "PROVIDER_KEY_NOT_FOUND", "Provider key does not exist.");
    }

    const body = await readJson(req);
    const key = await providerKeysRepository.upsert(buildProviderKeyUpsert(body, existing));
    recordAudit({
      action: "provider_key.updated",
      resourceType: "provider_key",
      resourceId: key.id,
      summary: `Provider key ${key.name} updated.`,
      metadata: { provider_id: key.providerId, status: key.status, rpm: key.rpm, concurrency: key.concurrency },
    });
    sendJson(res, 200, { data: adminProviderKey(key) });
    return;
  }

  if (method === "GET" && url.pathname === "/admin/model-categories") {
    sendJson(res, 200, { data: catalogRepository.listModelCategories().map(adminModelCategory) });
    return;
  }

  if (method === "POST" && url.pathname === "/admin/model-categories") {
    const body = await readJson(req);
    const category = await catalogRepository.upsertModelCategory(buildModelCategoryUpsert(body));
    recordAudit({
      action: "model_category.upserted",
      resourceType: "model_category",
      resourceId: category.id,
      summary: `Model category ${category.key} saved.`,
      metadata: { key: category.key, name: category.name, visible: category.visible },
    });
    sendJson(res, 201, { data: adminModelCategory(category) });
    return;
  }

  const modelCategoryMatch = url.pathname.match(/^\/admin\/model-categories\/([^/]+)$/);
  if (method === "PATCH" && modelCategoryMatch) {
    const existing = catalogRepository.getModelCategory(decodeURIComponent(modelCategoryMatch[1]));
    if (!existing) {
      throw problem(404, "CATEGORY_NOT_FOUND", "Model category does not exist.");
    }

    const body = await readJson(req);
    const category = await catalogRepository.upsertModelCategory(buildModelCategoryUpsert(body, existing));
    recordAudit({
      action: "model_category.updated",
      resourceType: "model_category",
      resourceId: category.id,
      summary: `Model category ${category.key} updated.`,
      metadata: { key: category.key, name: category.name, visible: category.visible },
    });
    sendJson(res, 200, { data: adminModelCategory(category) });
    return;
  }

  if (method === "POST" && url.pathname === "/admin/providers") {
    const body = await readJson(req);
    const provider = await catalogRepository.upsertProvider(buildProviderUpsert(body));
    recordAudit({
      action: "provider.upserted",
      resourceType: "provider",
      resourceId: provider.id,
      summary: `Provider ${provider.name} saved.`,
      metadata: { status: provider.status, kind: provider.kind },
    });
    sendJson(res, 201, { data: provider });
    return;
  }

  const providerMatch = url.pathname.match(/^\/admin\/providers\/([^/]+)$/);
  if (method === "PATCH" && providerMatch) {
    const existing = catalogRepository.getProvider(decodeURIComponent(providerMatch[1]));
    if (!existing) {
      throw problem(404, "PROVIDER_NOT_FOUND", "Provider does not exist.");
    }

    const body = await readJson(req);
    const provider = await catalogRepository.upsertProvider(buildProviderUpsert(body, existing));
    recordAudit({
      action: "provider.updated",
      resourceType: "provider",
      resourceId: provider.id,
      summary: `Provider ${provider.name} updated.`,
      metadata: { status: provider.status, kind: provider.kind },
    });
    sendJson(res, 200, { data: provider });
    return;
  }

  if (method === "GET" && url.pathname === "/admin/platform-models") {
    sendJson(res, 200, { data: catalogRepository.listPlatformModels().map(adminPlatformModel) });
    return;
  }

  if (method === "POST" && url.pathname === "/admin/platform-models") {
    const body = await readJson(req);
    const model = await catalogRepository.upsertPlatformModel(buildPlatformModelUpsert(body));
    recordAudit({
      action: "platform_model.upserted",
      resourceType: "platform_model",
      resourceId: model.id,
      summary: `Platform model ${model.id} saved.`,
      metadata: { modality: model.modality, tier: model.tier, visible: model.visible },
    });
    sendJson(res, 201, { data: adminPlatformModel(model) });
    return;
  }

  const platformModelMatch = url.pathname.match(/^\/admin\/platform-models\/([^/]+)$/);
  if (method === "PATCH" && platformModelMatch) {
    const existing = catalogRepository.getPlatformModel(decodeURIComponent(platformModelMatch[1]));
    if (!existing) {
      throw problem(404, "MODEL_NOT_FOUND", "Model was not found.");
    }

    const body = await readJson(req);
    const model = await catalogRepository.upsertPlatformModel(buildPlatformModelUpsert(body, existing));
    recordAudit({
      action: "platform_model.updated",
      resourceType: "platform_model",
      resourceId: model.id,
      summary: `Platform model ${model.id} updated.`,
      metadata: { modality: model.modality, tier: model.tier, visible: model.visible },
    });
    sendJson(res, 200, { data: adminPlatformModel(model) });
    return;
  }

  if (method === "GET" && url.pathname === "/admin/provider-models") {
    sendJson(res, 200, { data: catalogRepository.listProviderModels() });
    return;
  }

  if (method === "POST" && url.pathname === "/admin/provider-models") {
    const body = await readJson(req);
    const providerModel = await catalogRepository.upsertProviderModel(buildProviderModelUpsert(body));
    recordAudit({
      action: "provider_model.upserted",
      resourceType: "provider_model",
      resourceId: providerModel.id,
      summary: `Provider model ${providerModel.upstreamModelName} saved.`,
      metadata: {
        provider_id: providerModel.providerId,
        modality: providerModel.modality,
        status: providerModel.status,
      },
    });
    sendJson(res, 201, { data: providerModel });
    return;
  }

  const providerModelMatch = url.pathname.match(/^\/admin\/provider-models\/([^/]+)$/);
  if (method === "PATCH" && providerModelMatch) {
    const existing = catalogRepository.getProviderModel(decodeURIComponent(providerModelMatch[1]));
    if (!existing) {
      throw problem(404, "PROVIDER_MODEL_NOT_FOUND", "Provider model does not exist.");
    }

    const body = await readJson(req);
    const providerModel = await catalogRepository.upsertProviderModel(buildProviderModelUpsert(body, existing));
    recordAudit({
      action: "provider_model.updated",
      resourceType: "provider_model",
      resourceId: providerModel.id,
      summary: `Provider model ${providerModel.upstreamModelName} updated.`,
      metadata: {
        provider_id: providerModel.providerId,
        modality: providerModel.modality,
        status: providerModel.status,
      },
    });
    sendJson(res, 200, { data: providerModel });
    return;
  }

  if (method === "GET" && url.pathname === "/admin/users") {
    const limit = boundedNumber(url.searchParams.get("limit") ?? 100, 1, 500, "Limit must be between 1 and 500.");
    const users = (await usersRepository.list())
      .slice()
      .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
      .slice(0, limit)
      .map(publicUser);
    sendJson(res, 200, { data: users });
    return;
  }

  if (method === "POST" && url.pathname === "/admin/users") {
    const body = await readJson(req);
    const user = await usersRepository.upsert(buildUserUpsert(body));
    await billingRepository.getWallet(user.id);

    let subscription = null;
    const requestedPlanId = String(body.plan_id ?? body.planId ?? "").trim();
    if (requestedPlanId) {
      subscription = await usageRepository.upsertUserSubscription(
        buildUserSubscriptionUpsert({
          user_id: user.id,
          plan_id: requestedPlanId,
          status: body.subscription_status ?? "active",
          renews_at: body.renews_at,
        })
      );
    }

    recordAudit({
      action: "user.created",
      resourceType: "user",
      resourceId: user.id,
      userId: user.id,
      summary: `User ${user.id} created.`,
      metadata: { status: user.status, email: user.email, plan_id: subscription?.planId ?? null },
    });
    sendJson(res, 201, { data: { ...publicUser(user), subscription } });
    return;
  }

  const userMatch = url.pathname.match(/^\/admin\/users\/([^/]+)$/);
  if (method === "PATCH" && userMatch) {
    const existing = await usersRepository.findById(decodeURIComponent(userMatch[1]));
    if (!existing) {
      throw problem(404, "USER_NOT_FOUND", "User does not exist.");
    }

    const body = await readJson(req);
    const user = await usersRepository.upsert(buildUserUpsert(body, existing));
    recordAudit({
      action: user.status === "suspended" ? "user.suspended" : "user.updated",
      resourceType: "user",
      resourceId: user.id,
      userId: user.id,
      summary: `User ${user.id} updated.`,
      metadata: { status: user.status, email: user.email },
    });
    sendJson(res, 200, { data: publicUser(user) });
    return;
  }

  if (method === "GET" && url.pathname === "/admin/api-keys") {
    const userId = url.searchParams.get("user_id") ?? url.searchParams.get("userId") ?? "demo_user";
    sendJson(res, 200, { data: (await apiKeysRepository.listByUser(userId)).map(publicApiKey) });
    return;
  }

  if (method === "POST" && url.pathname === "/admin/api-keys") {
    const body = await readJson(req);
    const userId = String(body.user_id ?? body.userId ?? "demo_user").trim();
    const user = await usersRepository.findById(userId);
    if (!user || user.status === "deleted") {
      throw problem(404, "USER_NOT_FOUND", "User does not exist.");
    }

    const name = String(body.name ?? "User API key").trim().slice(0, 80) || "User API key";
    const scopes = normalizeStringList(body.scopes, ["tasks:create", "wallet:read"]);
    const key = await createApiKey({ userId, name, scopes });
    recordAudit({
      action: "api_key.created",
      resourceType: "api_key",
      resourceId: key.id,
      userId,
      summary: `API key ${key.name} created.`,
      metadata: { prefix: key.prefix, scopes: key.scopes },
    });
    sendJson(res, 201, { data: { ...publicApiKey(key), secret: key.secret } });
    return;
  }

  const apiKeyMatch = url.pathname.match(/^\/admin\/api-keys\/([^/]+)$/);
  if (method === "PATCH" && apiKeyMatch) {
    const key = await apiKeysRepository.findById(decodeURIComponent(apiKeyMatch[1]));
    if (!key) {
      throw problem(404, "API_KEY_NOT_FOUND", "API key does not exist.");
    }

    const body = await readJson(req);
    if (body.status !== undefined) {
      if (!["active", "revoked"].includes(body.status)) {
        throw problem(422, "VALIDATION_ERROR", "Invalid API key status.");
      }
      key.status = body.status;
      key.revokedAt = body.status === "revoked" ? new Date().toISOString() : null;
    }
    const savedKey = await apiKeysRepository.update(key);
    recordAudit({
      action: savedKey.status === "revoked" ? "api_key.revoked" : "api_key.updated",
      resourceType: "api_key",
      resourceId: savedKey.id,
      userId: savedKey.userId,
      summary: `API key ${savedKey.name} set to ${savedKey.status}.`,
      metadata: { status: savedKey.status, prefix: savedKey.prefix },
    });
    sendJson(res, 200, { data: publicApiKey(savedKey) });
    return;
  }

  if (method === "GET" && url.pathname === "/admin/channels") {
    sendJson(res, 200, {
      data: catalogRepository.listChannels().map(adminChannel),
    });
    return;
  }

  const platformSchemaMatch = url.pathname.match(/^\/admin\/platform-models\/([^/]+)\/schema-fields$/);
  if ((method === "POST" || method === "PATCH") && platformSchemaMatch) {
    const model = catalogRepository.getPlatformModel(decodeURIComponent(platformSchemaMatch[1]));
    if (!model) {
      throw problem(404, "MODEL_NOT_FOUND", "Model was not found.");
    }

    const body = await readJson(req);
    const field = buildPlatformSchemaField(body);
    const updatedModel = await catalogRepository.upsertPlatformModelSchemaField(model.id, field);
    if (!updatedModel) {
      throw problem(404, "MODEL_NOT_FOUND", "Model was not found.");
    }
    recordAudit({
      action: "schema_field.upserted",
      resourceType: "platform_model",
      resourceId: updatedModel.id,
      summary: `Schema field ${field.key} saved for ${updatedModel.id}.`,
      metadata: { field_key: field.key, field_type: field.type, required: Boolean(field.required) },
    });
    sendJson(res, 200, { data: adminPlatformModel(updatedModel) });
    return;
  }

  const platformCategoryAssignmentMatch = url.pathname.match(/^\/admin\/platform-models\/([^/]+)\/category-assignments$/);
  if ((method === "POST" || method === "PATCH") && platformCategoryAssignmentMatch) {
    const model = catalogRepository.getPlatformModel(decodeURIComponent(platformCategoryAssignmentMatch[1]));
    if (!model) {
      throw problem(404, "MODEL_NOT_FOUND", "Model was not found.");
    }

    const body = await readJson(req);
    const assignment = buildPlatformModelCategoryAssignment(model, body);
    await catalogRepository.upsertPlatformModelCategoryAssignment(assignment);
    recordAudit({
      action: "platform_model.category_assigned",
      resourceType: "platform_model",
      resourceId: model.id,
      summary: `Category ${assignment.categoryId} assigned to ${model.id}.`,
      metadata: {
        platform_model_id: model.id,
        category_id: assignment.categoryId,
        is_primary: assignment.isPrimary,
      },
    });
    sendJson(res, 200, { data: adminPlatformModel(catalogRepository.getPlatformModel(model.id)) });
    return;
  }

  const platformAliasMatch = url.pathname.match(/^\/admin\/platform-models\/([^/]+)\/aliases$/);
  if ((method === "POST" || method === "PATCH") && platformAliasMatch) {
    const model = catalogRepository.getPlatformModel(decodeURIComponent(platformAliasMatch[1]));
    if (!model) {
      throw problem(404, "MODEL_NOT_FOUND", "Model was not found.");
    }

    const body = await readJson(req);
    const alias = buildPlatformModelAlias(model, body);
    await catalogRepository.upsertPlatformModelAlias(alias);
    recordAudit({
      action: "platform_model.alias_upserted",
      resourceType: "platform_model",
      resourceId: model.id,
      summary: `Alias ${alias.alias} saved for ${model.id}.`,
      metadata: { alias: alias.alias, kind: alias.kind },
    });
    sendJson(res, 200, { data: adminPlatformModel(catalogRepository.getPlatformModel(model.id)) });
    return;
  }

  if (method === "POST" && url.pathname === "/admin/channels") {
    const body = await readJson(req);
    const channel = await catalogRepository.createChannel(buildChannelCreate(body));
    recordAudit({
      action: "channel.created",
      resourceType: "channel",
      resourceId: channel.id,
      summary: `Channel ${channel.id} created for ${channel.platformModelId}.`,
      metadata: {
        platform_model_id: channel.platformModelId,
        provider_id: channel.providerId,
        provider_model_id: channel.providerModelId,
        status: channel.status,
      },
    });
    sendJson(res, 201, { data: adminChannel(channel) });
    return;
  }

  const channelMappingMatch = url.pathname.match(/^\/admin\/channels\/([^/]+)\/parameter-mappings$/);
  if ((method === "POST" || method === "PATCH") && channelMappingMatch) {
    const channel = catalogRepository.getChannel(decodeURIComponent(channelMappingMatch[1]));
    if (!channel) {
      throw problem(404, "CHANNEL_NOT_FOUND", "Channel does not exist.");
    }

    const body = await readJson(req);
    const mapping = buildChannelMappingUpsert(channel, body);
    await catalogRepository.upsertChannelMapping(mapping);
    recordAudit({
      action: "channel_mapping.upserted",
      resourceType: "channel",
      resourceId: channel.id,
      summary: `Mapping ${mapping.platform} saved for ${channel.id}.`,
      metadata: {
        platform_param_key: mapping.platform,
        upstream_param_key: mapping.upstream,
        transform: mapping.transform,
      },
    });
    sendJson(res, 200, { data: adminChannel(channel) });
    return;
  }

  const channelTestMatch = url.pathname.match(/^\/admin\/channels\/([^/]+)\/test$/);
  if (method === "POST" && channelTestMatch) {
    const channel = catalogRepository.getChannel(decodeURIComponent(channelTestMatch[1]));
    if (!channel) {
      throw problem(404, "CHANNEL_NOT_FOUND", "Channel does not exist.");
    }

    const body = await readJson(req);
    sendJson(res, 200, { data: channelTestResult(channel, body.input ?? {}) });
    return;
  }

  const channelMatch = url.pathname.match(/^\/admin\/channels\/([^/]+)$/);
  if (method === "PATCH" && channelMatch) {
    const channel = catalogRepository.getChannel(decodeURIComponent(channelMatch[1]));
    if (!channel) {
      throw problem(404, "CHANNEL_NOT_FOUND", "Channel does not exist.");
    }

    const body = await readJson(req);
    applyChannelPatch(channel, body);
    recordAudit({
      action: "channel.updated",
      resourceType: "channel",
      resourceId: channel.id,
      summary: `Channel ${channel.id} updated.`,
      metadata: {
        status: channel.status,
        role: channel.role,
        weight: channel.weight,
        sale_price: channel.salePrice,
        cost_price: channel.costPrice,
      },
    });
    sendJson(res, 200, { data: adminChannel(channel) });
    return;
  }

  if (method === "GET" && url.pathname === "/admin/tasks") {
    const limit = boundedNumber(url.searchParams.get("limit") ?? 50, 1, 200, "Limit must be between 1 and 200.");
    const data = tasksRepository
      .list()
      .slice()
      .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
      .slice(0, limit)
      .map(adminTask);
    sendJson(res, 200, { data });
    return;
  }

  if (method === "GET" && url.pathname === "/admin/analytics/summary") {
    sendJson(res, 200, { data: await analyticsSummary() });
    return;
  }

  if (method === "GET" && url.pathname === "/admin/commercial-readiness") {
    sendJson(res, 200, { data: commercialReadinessSummary() });
    return;
  }

  if (method === "GET" && url.pathname === "/admin/customers/summary") {
    const limit = boundedNumber(url.searchParams.get("limit") ?? 20, 1, 100, "Limit must be between 1 and 100.");
    sendJson(res, 200, { data: await customersSummary(limit) });
    return;
  }

  if (method === "GET" && url.pathname === "/admin/billing/transactions") {
    const limit = boundedNumber(url.searchParams.get("limit") ?? 20, 1, 100, "Limit must be between 1 and 100.");
    sendJson(res, 200, { data: await billingTransactions(limit) });
    return;
  }

  if (method === "GET" && url.pathname === "/admin/billing/invoices") {
    sendJson(res, 200, { data: await billingInvoices(readBillingPeriod(url)) });
    return;
  }

  if (method === "GET" && url.pathname === "/admin/billing/invoices.csv") {
    const invoices = await billingInvoices(readBillingPeriod(url));
    sendCsv(res, `tikpan-invoices-${invoices.period.start.slice(0, 10)}-${invoices.period.end.slice(0, 10)}.csv`, invoicesToCsv(invoices));
    return;
  }

  if (method === "GET" && url.pathname === "/admin/payment-providers") {
    sendJson(res, 200, {
      data: (await paymentProvidersRepository.list({ includeDisabled: true })).map(adminPaymentProvider),
    });
    return;
  }

  if (method === "POST" && url.pathname === "/admin/payment-providers") {
    const body = await readJson(req);
    const provider = await paymentProvidersRepository.upsert(buildPaymentProviderUpsert(body));
    recordAudit({
      action: "payment_provider.upserted",
      resourceType: "payment_provider",
      resourceId: provider.id,
      summary: `Payment provider ${provider.name} saved.`,
      metadata: { status: provider.status, kind: provider.kind, checkout_mode: provider.checkoutMode },
    });
    sendJson(res, 201, { data: adminPaymentProvider(provider) });
    return;
  }

  const paymentProviderMatch = url.pathname.match(/^\/admin\/payment-providers\/([^/]+)$/);
  if (method === "PATCH" && paymentProviderMatch) {
    const existing = await paymentProvidersRepository.findById(decodeURIComponent(paymentProviderMatch[1]));
    if (!existing) {
      throw problem(404, "PAYMENT_PROVIDER_NOT_FOUND", "Payment provider does not exist.");
    }
    const body = await readJson(req);
    const provider = await paymentProvidersRepository.upsert(buildPaymentProviderUpsert(body, existing));
    recordAudit({
      action: "payment_provider.updated",
      resourceType: "payment_provider",
      resourceId: provider.id,
      summary: `Payment provider ${provider.name} updated.`,
      metadata: { status: provider.status, kind: provider.kind, checkout_mode: provider.checkoutMode },
    });
    sendJson(res, 200, { data: adminPaymentProvider(provider) });
    return;
  }

  if (method === "GET" && url.pathname === "/admin/payment-orders") {
    const limit = boundedNumber(url.searchParams.get("limit") ?? 50, 1, 200, "Limit must be between 1 and 200.");
    sendJson(res, 200, {
      data: (await paymentOrdersRepository.list({
        userId: url.searchParams.get("user_id") ?? undefined,
        limit,
      })).map(publicPaymentOrder),
    });
    return;
  }

  const transactionRefundMatch = url.pathname.match(/^\/admin\/billing\/transactions\/([^/]+)\/refunds$/);
  if (method === "POST" && transactionRefundMatch) {
    const body = await readJson(req);
    const result = await refundTask(
      decodeURIComponent(transactionRefundMatch[1]),
      body.amount,
      body.note ?? "Admin refund",
    );
    recordAudit({
      action: "billing.refunded",
      resourceType: "task",
      resourceId: result.task.id,
      userId: result.task.userId,
      summary: `Refunded ${result.refund_amount} for task ${result.task.id}.`,
      metadata: { refund_amount: result.refund_amount, note: body.note ?? "Admin refund" },
    });
    sendJson(res, 201, {
      data: {
        task: publicTask(result.task),
        wallet: publicWallet(result.wallet),
        refund_amount: result.refund_amount,
        transaction: await billingTransactionForTask(result.task),
      },
    });
    return;
  }

  if (method === "GET" && url.pathname === "/admin/wallet-ledger") {
    sendJson(res, 200, { data: await publicLedger(url.searchParams.get("user_id") ?? undefined) });
    return;
  }

  if (method === "GET" && url.pathname === "/admin/wallet") {
    const userId = url.searchParams.get("user_id") ?? "demo_user";
    sendJson(res, 200, {
      data: {
        wallet: publicWallet(await billingRepository.getWallet(userId)),
        ledger: (await publicLedger(userId)).slice(-8).reverse(),
      },
    });
    return;
  }

  if (method === "POST" && url.pathname === "/admin/wallet/top-ups") {
    const body = await readJson(req);
    const userId = String(body.user_id ?? "demo_user").trim() || "demo_user";
    const wallet = await topUpWallet(userId, body.amount, body.note ?? "Admin balance top-up");
    recordAudit({
      action: "wallet.top_up",
      resourceType: "wallet",
      resourceId: userId,
      userId,
      summary: `Wallet top-up saved for ${userId}.`,
      metadata: { amount: Number(body.amount), note: body.note ?? "Admin balance top-up" },
    });
    sendJson(res, 201, {
      data: {
        wallet: publicWallet(wallet),
        ledger: (await publicLedger(userId)).slice(-8).reverse(),
      },
    });
    return;
  }

  if (method === "GET" && url.pathname === "/admin/billing-plans") {
    sendJson(res, 200, { data: await usageRepository.listBillingPlans() });
    return;
  }

  if (method === "POST" && url.pathname === "/admin/billing-plans") {
    const body = await readJson(req);
    const plan = await usageRepository.upsertBillingPlan(buildBillingPlanUpsert(body));
    recordAudit({
      action: "billing_plan.upserted",
      resourceType: "billing_plan",
      resourceId: plan.id,
      summary: `Billing plan ${plan.name} saved.`,
      metadata: {
        status: plan.status,
        monthly_task_limit: plan.monthlyTaskLimit,
        monthly_spend_limit: plan.monthlySpendLimit,
      },
    });
    sendJson(res, 201, { data: plan });
    return;
  }

  const billingPlanMatch = url.pathname.match(/^\/admin\/billing-plans\/([^/]+)$/);
  if (method === "PATCH" && billingPlanMatch) {
    const existing = await usageRepository.getBillingPlan(decodeURIComponent(billingPlanMatch[1]));
    if (!existing) {
      throw problem(404, "BILLING_PLAN_NOT_FOUND", "Billing plan does not exist.");
    }

    const body = await readJson(req);
    const plan = await usageRepository.upsertBillingPlan(buildBillingPlanUpsert(body, existing));
    recordAudit({
      action: "billing_plan.updated",
      resourceType: "billing_plan",
      resourceId: plan.id,
      summary: `Billing plan ${plan.name} updated.`,
      metadata: {
        status: plan.status,
        monthly_task_limit: plan.monthlyTaskLimit,
        monthly_spend_limit: plan.monthlySpendLimit,
      },
    });
    sendJson(res, 200, { data: plan });
    return;
  }

  if (method === "GET" && url.pathname === "/admin/user-subscriptions") {
    const subscriptions = usageRepository.listUserSubscriptions
      ? await usageRepository.listUserSubscriptions()
      : [await usageRepository.getUserSubscription(url.searchParams.get("user_id") ?? "demo_user")];
    sendJson(res, 200, { data: subscriptions });
    return;
  }

  if (method === "POST" && url.pathname === "/admin/user-subscriptions") {
    const body = await readJson(req);
    const subscription = await usageRepository.upsertUserSubscription(buildUserSubscriptionUpsert(body));
    recordAudit({
      action: "subscription.upserted",
      resourceType: "subscription",
      resourceId: subscription.id ?? subscription.userId,
      userId: subscription.userId,
      summary: `Subscription for ${subscription.userId} saved.`,
      metadata: { plan_id: subscription.planId, status: subscription.status, renews_at: subscription.renewsAt },
    });
    sendJson(res, 201, { data: subscription });
    return;
  }

  const subscriptionMatch = url.pathname.match(/^\/admin\/user-subscriptions\/([^/]+)$/);
  if (method === "PATCH" && subscriptionMatch) {
    const subscriptions = usageRepository.listUserSubscriptions ? await usageRepository.listUserSubscriptions() : [];
    const existing = subscriptions.find((item) => item.id === decodeURIComponent(subscriptionMatch[1]));
    if (!existing) {
      throw problem(404, "SUBSCRIPTION_NOT_FOUND", "User subscription does not exist.");
    }

    const body = await readJson(req);
    const subscription = await usageRepository.upsertUserSubscription(buildUserSubscriptionUpsert(body, existing));
    recordAudit({
      action: "subscription.updated",
      resourceType: "subscription",
      resourceId: subscription.id ?? subscription.userId,
      userId: subscription.userId,
      summary: `Subscription for ${subscription.userId} updated.`,
      metadata: { plan_id: subscription.planId, status: subscription.status, renews_at: subscription.renewsAt },
    });
    sendJson(res, 200, { data: subscription });
    return;
  }

  if (method === "GET" && url.pathname === "/admin/audit-logs") {
    const limit = boundedNumber(url.searchParams.get("limit") ?? 30, 1, 100, "Limit must be between 1 and 100.");
    sendJson(res, 200, {
      data: auditRepository.list({
        userId: url.searchParams.get("user_id") ?? undefined,
        resourceType: url.searchParams.get("resource_type") ?? undefined,
        action: url.searchParams.get("action") ?? undefined,
        limit,
      }).map(publicAuditLog),
    });
    return;
  }

  if (method === "GET" && url.pathname === "/admin/usage") {
    sendJson(res, 200, { data: await getUsageSummary(url.searchParams.get("user_id") ?? "demo_user") });
    return;
  }

  throw problem(404, "NOT_FOUND", "Endpoint does not exist.");
}

async function readJson(req) {
  const raw = await readRawBody(req);
  if (!raw) {
    return {};
  }

  try {
    return JSON.parse(raw);
  } catch {
    throw problem(400, "INVALID_JSON", "Request body is not valid JSON.");
  }
}

async function readRawBody(req) {
  const chunks = [];

  for await (const chunk of req) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }

  return Buffer.concat(chunks).toString("utf8");
}

async function readSignedJson(req) {
  const raw = await readRawBody(req);
  if (!raw) {
    return { raw, body: {} };
  }

  try {
    return { raw, body: JSON.parse(raw) };
  } catch {
    throw problem(400, "INVALID_JSON", "Request body is not valid JSON.");
  }
}

function assertPaymentWebhookSignature(req, raw, paymentProvider) {
  if (!paymentProvider || paymentProvider.status === "disabled") {
    throw problem(404, "PAYMENT_PROVIDER_NOT_FOUND", "Payment provider does not exist.");
  }

  const secret = paymentProvider.webhookSecret ?? config.paymentWebhookSecret;
  if (!secret) {
    throw problem(422, "PAYMENT_WEBHOOK_SECRET_NOT_CONFIGURED", "Payment provider webhook secret is not configured.");
  }

  const received = String(req.headers["x-tikpan-signature"] ?? "")
    .trim()
    .replace(/^sha256=/i, "");
  if (!received) {
    throw problem(401, "PAYMENT_WEBHOOK_SIGNATURE_REQUIRED", "Payment webhook signature is required.");
  }

  const expected = createHmac("sha256", secret).update(raw).digest("hex");
  if (!secureTokenEquals(received, expected)) {
    throw problem(401, "PAYMENT_WEBHOOK_SIGNATURE_INVALID", "Payment webhook signature is invalid.");
  }
}

function publicTask(task) {
  return {
    task_id: task.id,
    model: task.platformModelId,
    status: publicTaskStatus(task.status),
    batch_id: task.batchId ?? null,
    batch_title: task.batchTitle ?? null,
    batch_item_id: task.batchItemId ?? null,
    project_id: task.projectId ?? null,
    project_name: task.projectName ?? null,
    input: task.input ?? {},
    route_mode: task.routeMode ?? "balanced",
    progress: task.progress ?? (task.status === "completed" ? 100 : 0),
    current_step: task.currentStep ?? null,
    estimated_cost: task.estimatedCost,
    final_cost: task.finalCost,
    output: task.output,
    error: task.publicErrorCode
      ? {
          code: task.publicErrorCode,
          message: task.publicErrorMessage,
        }
      : null,
    created_at: task.createdAt,
    finished_at: task.finishedAt,
  };
}

function publicTaskStatus(status) {
  const map = {
    completed: "succeeded",
    cancelled: "canceled",
    expired: "failed",
    saving_media: "running",
  };
  return map[status] ?? status;
}

function adminTask(task) {
  const selectedProvider = task.selectedProviderId ? catalogRepository.getProvider(task.selectedProviderId) : null;
  const selectedProviderModel = task.selectedProviderModelId
    ? catalogRepository.getProviderModel(task.selectedProviderModelId)
    : null;

  return {
    ...publicTask(task),
    internal_status: task.status,
    attempts: publicAttempts(task),
    worker: {
      worker_id: task.workerId ?? null,
      locked_until: task.lockedUntil ?? null,
      lock_version: task.lockVersion ?? 0,
    },
    internal: {
      provider: selectedProvider?.name ?? null,
      provider_model: selectedProviderModel?.upstreamModelName ?? null,
      selected_channel_id: task.selectedChannelId ?? null,
      mapped_payload: task.mappedPayload ?? null,
    },
  };
}

function adminProviderKey(key) {
  const successCount = Number(key.todaySuccessCount ?? 0);
  const failureCount = Number(key.todayFailureCount ?? 0);
  const completedCount = successCount + failureCount;
  const averageLatencyMs = completedCount > 0 ? Math.round(Number(key.totalLatencyMs ?? 0) / completedCount) : null;
  return {
    id: key.id,
    provider_id: key.providerId,
    name: key.name,
    status: key.status,
    rpm: key.rpm,
    tpm: key.tpm,
    concurrency: key.concurrency,
    priority: key.priority,
    weight: key.weight,
    supported_provider_model_ids: key.supportedProviderModelIds ?? [],
    runtime: {
      current_concurrency: key.currentConcurrency ?? 0,
      minute_window_started_at: key.minuteWindowStartedAt ?? null,
      minute_request_count: key.minuteRequestCount ?? 0,
      minute_token_count: key.minuteTokenCount ?? 0,
      rpm_usage: key.rpm ? Math.min(1, Number(key.minuteRequestCount ?? 0) / Number(key.rpm)) : null,
      tpm_usage: key.tpm ? Math.min(1, Number(key.minuteTokenCount ?? 0) / Number(key.tpm)) : null,
      today_request_count: key.todayRequestCount ?? 0,
      today_success_count: successCount,
      today_failure_count: failureCount,
      success_rate: completedCount > 0 ? Math.round((successCount / completedCount) * 10000) / 100 : null,
      average_latency_ms: averageLatencyMs,
      cooling_until: key.coolingUntil ?? null,
      last_used_at: key.lastUsedAt ?? null,
      last_error_code: key.lastErrorCode ?? null,
      last_error_message: key.lastErrorMessage ?? null,
    },
    secret: {
      configured: Boolean(key.encryptedApiKey),
      masked: redactSecret(key.encryptedApiKey),
      source: "internal_provider_key",
    },
    notes: key.notes ?? null,
    created_at: key.createdAt ?? null,
    updated_at: key.updatedAt ?? null,
  };
}

async function publicTaskBatches(userId, limit = 20) {
  const grouped = new Map();
  for (const task of await tasksRepository.listByUser(userId)) {
    if (!task.batchId) {
      continue;
    }

    const batch =
      grouped.get(task.batchId) ?? {
        batch_id: task.batchId,
        title: task.batchTitle ?? "",
        status: "created",
        task_count: 0,
        created_count: 0,
        failed_count: 0,
        completed_count: 0,
        active_count: 0,
        estimated_cost: 0,
        final_cost: 0,
        created_at: task.createdAt,
        updated_at: task.finishedAt ?? task.updatedAt ?? task.createdAt,
        items: [],
      };

    const publicItem = publicTask(task);
    batch.items.push({
      id: task.batchItemId ?? task.id,
      status: task.publicErrorCode ? "failed" : "created",
      task: publicItem,
    });
    batch.task_count += 1;
    batch.created_count += 1;
    batch.failed_count += task.status === "failed" ? 1 : 0;
    batch.completed_count += task.status === "completed" ? 1 : 0;
    batch.active_count += ["queued", "running", "saving_media"].includes(task.status) ? 1 : 0;
    batch.estimated_cost = roundMoney(Number(batch.estimated_cost ?? 0) + Number(task.estimatedCost ?? 0));
    batch.final_cost = roundMoney(Number(batch.final_cost ?? 0) + Number(task.finalCost ?? 0));
    batch.created_at = earliestIso(batch.created_at, task.createdAt);
    batch.updated_at = latestIso([batch.updated_at, task.finishedAt, task.updatedAt, task.createdAt].filter(Boolean));
    grouped.set(task.batchId, batch);
  }

  return Array.from(grouped.values())
    .map((batch) => ({
      ...batch,
      status: batchStatus(batch),
      items: batch.items.sort((a, b) => new Date(b.task.created_at ?? 0).getTime() - new Date(a.task.created_at ?? 0).getTime()),
    }))
    .sort((a, b) => new Date(b.updated_at ?? b.created_at ?? 0).getTime() - new Date(a.updated_at ?? a.created_at ?? 0).getTime())
    .slice(0, limit);
}

function batchStatus(batch) {
  if (batch.active_count > 0) {
    return "running";
  }
  if (batch.task_count > 0 && batch.completed_count === batch.task_count) {
    return "completed";
  }
  if (batch.failed_count > 0 && batch.completed_count > 0) {
    return "partial";
  }
  if (batch.failed_count > 0 && batch.completed_count === 0) {
    return "failed";
  }
  return "created";
}

function earliestIso(current, candidate) {
  if (!candidate) {
    return current ?? null;
  }
  if (!current) {
    return candidate;
  }
  return new Date(candidate).getTime() < new Date(current).getTime() ? candidate : current;
}

function publicAttempts(task) {
  return (task.attempts ?? []).map((attempt) => {
    const provider = catalogRepository.getProvider(attempt.providerId);
    const providerModel = catalogRepository.getProviderModel(attempt.providerModelId);
    return {
      id: attempt.id,
      provider: provider?.name ?? "Unknown",
      provider_model: providerModel?.upstreamModelName ?? "unknown",
      channel_id: attempt.channelId,
      provider_key_id: attempt.providerKeyId ?? null,
      provider_key_lease_id: attempt.providerKeyLeaseId ?? null,
      provider_key_lease_expires_at: attempt.providerKeyLeaseExpiresAt ?? null,
      latency_ms: attempt.latencyMs ?? null,
      status: attempt.status,
      error_code: attempt.errorCode ?? null,
      error_message: attempt.errorMessage ?? null,
      fallback_reason: attempt.fallbackReason ?? null,
      created_at: attempt.createdAt,
      finished_at: attempt.finishedAt ?? null,
    };
  });
}

async function publicAssetLibrary(userId, limit = 50, { projectId = null } = {}) {
  const mediaByTask = new Map();
  for (const asset of (await mediaRepository.listByUser?.(userId, { limit: 500 })) ?? []) {
    const group = mediaByTask.get(asset.taskId) ?? [];
    group.push(asset);
    mediaByTask.set(asset.taskId, group);
  }
  const metadataByTask = new Map((await assetMetadataRepository.listByUser(userId)).map((item) => [item.taskId, item]));

  const userTasks = await tasksRepository.listByUser(userId);

  return userTasks
    .filter((task) => !projectId || task.projectId === projectId)
    .filter((task) => task.status === "completed")
    .filter((task) => {
      const publicUrls = task.output?.publicUrls ?? task.output?.public_urls ?? [];
      return publicUrls.length > 0 || (mediaByTask.get(task.id)?.length ?? 0) > 0;
    })
    .slice()
    .sort((a, b) => {
      const aFavorite = metadataByTask.get(a.id)?.favorite ? 1 : 0;
      const bFavorite = metadataByTask.get(b.id)?.favorite ? 1 : 0;
      if (aFavorite !== bFavorite) {
        return bFavorite - aFavorite;
      }
      return new Date(b.finishedAt ?? b.createdAt).getTime() - new Date(a.finishedAt ?? a.createdAt).getTime();
    })
    .slice(0, limit)
    .map((task) => publicAssetItem(task, mediaByTask.get(task.id) ?? [], metadataByTask.get(task.id)));
}

async function publicProjectSummary(project) {
  const stats = await projectStats(project);
  return {
    id: project.id,
    user_id: project.userId,
    name: project.name,
    type: project.type,
    status: project.status,
    description: project.description,
    cover_url: project.coverUrl ?? null,
    tags: project.tags ?? [],
    settings: project.settings ?? {},
    stats,
    created_at: project.createdAt,
    updated_at: project.updatedAt,
    archived_at: project.archivedAt ?? null,
  };
}

async function publicProjectDetail(project) {
  const summary = await publicProjectSummary(project);
  const tasks = (await tasksRepository.listByUser(project.userId))
    .filter((task) => task.projectId === project.id)
    .slice()
    .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());

  return {
    ...summary,
    tasks: tasks.slice(0, 20).map(publicTask),
    assets: await publicAssetLibrary(project.userId, 20, { projectId: project.id }),
  };
}

async function projectStats(project) {
  const tasks = (await tasksRepository.listByUser(project.userId)).filter((task) => task.projectId === project.id);
  const assets = await publicAssetLibrary(project.userId, 500, { projectId: project.id });
  const completed = tasks.filter((task) => task.status === "completed").length;
  const failed = tasks.filter((task) => task.status === "failed").length;
  const active = tasks.filter((task) => ["queued", "running", "saving_media"].includes(task.status)).length;
  const spend = tasks.reduce((sum, task) => sum + Number(task.finalCost ?? task.estimatedCost ?? 0), 0);

  return {
    tasks_total: tasks.length,
    tasks_completed: completed,
    tasks_failed: failed,
    tasks_active: active,
    assets_total: assets.length,
    token_spend: roundMoney(spend),
  };
}

function publicAssetItem(task, mediaAssets, metadata = null) {
  const model = catalogRepository.getPlatformModel(task.platformModelId);
  const publicUrls = task.output?.publicUrls ?? task.output?.public_urls ?? mediaAssets.map((asset) => asset.publicUrl).filter(Boolean);
  return {
    id: `asset_${task.id}`,
    task_id: task.id,
    project_id: task.projectId ?? null,
    project_name: task.projectName ?? null,
    model: task.platformModelId,
    model_name: model?.shortName ?? model?.name ?? task.platformModelId,
    modality: model?.modality ?? "image",
    status: task.status,
    route_mode: task.routeMode ?? "balanced",
    title: metadata?.title ?? "",
    note: metadata?.note ?? "",
    favorite: Boolean(metadata?.favorite),
    review_status: metadata?.reviewStatus ?? "candidate",
    tags: Array.isArray(metadata?.tags) ? metadata.tags : [],
    collections: Array.isArray(metadata?.collections) ? metadata.collections : [],
    prompt: summarizePrompt(task.input),
    input: task.input ?? {},
    output_urls: publicUrls,
    media_assets: mediaAssets.map(publicMediaAsset),
    final_cost: task.finalCost ?? task.estimatedCost ?? 0,
    created_at: task.createdAt,
    finished_at: task.finishedAt ?? null,
  };
}

function publicMediaAsset(asset) {
  return {
    id: asset.id,
    object_key: asset.objectKey,
    public_url: asset.publicUrl,
    mime_type: asset.mimeType,
    source_url: asset.sourceUrl,
    storage_mode: asset.storageMode,
    direction: asset.direction,
    created_at: asset.createdAt,
  };
}

async function buildAssetMetadata(body, task, userId) {
  const existing = await assetMetadataRepository.findByTask(task.id, userId);
  const now = new Date().toISOString();
  return {
    taskId: task.id,
    userId,
    title: String(body.title ?? existing?.title ?? "").trim().slice(0, 100),
    note: String(body.note ?? existing?.note ?? "").trim().slice(0, 500),
    favorite: Boolean(body.favorite ?? existing?.favorite ?? false),
    reviewStatus: normalizeAssetReviewStatus(body.review_status ?? body.reviewStatus ?? existing?.reviewStatus ?? "candidate"),
    tags: normalizeAssetTags(body.tags ?? existing?.tags ?? []),
    collections: normalizeAssetTags(body.collections ?? existing?.collections ?? []),
    createdAt: existing?.createdAt ?? now,
    updatedAt: now,
  };
}

function normalizeAssetReviewStatus(value) {
  const status = String(value ?? "candidate").trim();
  if (!allowedAssetReviewStatuses.has(status)) {
    throw problem(422, "VALIDATION_ERROR", "Invalid asset review status.");
  }
  return status;
}

function normalizeAssetTags(value) {
  const rawTags = Array.isArray(value)
    ? value
    : String(value ?? "")
        .split(",")
        .map((item) => item.trim());

  return [...new Set(rawTags.map((item) => String(item).trim().slice(0, 32)).filter(Boolean))].slice(0, 12);
}

function summarizePrompt(input = {}) {
  const candidate = input.prompt ?? input.message ?? input.title ?? "";
  const text = String(candidate).replace(/\s+/g, " ").trim();
  return text.length > 140 ? `${text.slice(0, 137)}...` : text;
}

async function analyticsSummary() {
  const tasks = await tasksRepository.list();
  const completedTasks = tasks.filter((task) => task.status === "completed");
  const failedTasks = tasks.filter((task) => task.status === "failed");
  const activeTasks = tasks.filter((task) => ["queued", "running", "saving_media"].includes(task.status));
  const revenue = completedTasks.reduce((sum, task) => sum + Number(task.finalCost ?? 0), 0);
  const cost = completedTasks.reduce((sum, task) => sum + taskCost(task), 0);
  const grossProfit = revenue - cost;
  const summary = {
    tasks_total: tasks.length,
    tasks_completed: completedTasks.length,
    tasks_failed: failedTasks.length,
    tasks_active: activeTasks.length,
    revenue: roundMoney(revenue),
    cost: roundMoney(cost),
    gross_profit: roundMoney(grossProfit),
    gross_margin: revenue > 0 ? roundMoney(grossProfit / revenue) : 0,
  };

  return {
    summary,
    by_model: groupAnalytics(tasks, (task) => task.platformModelId),
    by_provider: groupAnalytics(tasks, (task) => {
      const attempt = latestBillableAttempt(task);
      return catalogRepository.getProvider(attempt?.providerId)?.name ?? attempt?.providerId ?? "unrouted";
    }),
    reliability: reliabilitySummary(tasks),
    error_codes: errorCodeSummary(tasks),
    provider_health: providerHealthSummary(tasks),
  };
}

async function customersSummary(limit = 20) {
  const tasks = await tasksRepository.list();
  const subscriptions = usageRepository.listUserSubscriptions ? await usageRepository.listUserSubscriptions() : [];
  const userIds = new Set(["demo_user"]);

  for (const user of await usersRepository.list()) {
    userIds.add(user.id);
  }
  for (const subscription of subscriptions) {
    userIds.add(subscription.userId);
  }
  for (const task of tasks) {
    userIds.add(task.userId);
  }
  for (const item of await publicLedger(undefined)) {
    userIds.add(item.user_id);
  }

  const customers = [];
  for (const userId of userIds) {
    const userTasks = tasks.filter((task) => task.userId === userId);
    const completedTasks = userTasks.filter((task) => task.status === "completed");
    const failedTasks = userTasks.filter((task) => task.status === "failed");
    const activeTasks = userTasks.filter((task) => ["queued", "running", "saving_media"].includes(task.status));
    const subscription = subscriptions.find((item) => item.userId === userId) ?? (await usageRepository.getUserSubscription(userId));
    const plan = subscription?.planId ? await usageRepository.getBillingPlan(subscription.planId) : null;
    const wallet = publicWallet(await billingRepository.getWallet(userId));
    const ledger = await publicLedger(userId);
    const apiKeys = await apiKeysRepository.listByUser(userId);
    const activeApiKeys = apiKeys.filter((key) => key.status === "active");
    const lastTaskAt = latestIso(userTasks.flatMap((task) => [task.createdAt, task.finishedAt].filter(Boolean)));
    const lastKeyUsedAt = latestIso(apiKeys.map((key) => key.lastUsedAt).filter(Boolean));
    const lastLedgerAt = latestIso(ledger.map((item) => item.created_at).filter(Boolean));

    customers.push({
      user_id: userId,
      plan_id: subscription?.planId ?? null,
      plan_name: plan?.name ?? subscription?.planId ?? "No plan",
      subscription_status: subscription?.status ?? "none",
      renews_at: subscription?.renewsAt ?? null,
      wallet,
      api_keys_total: apiKeys.length,
      api_keys_active: activeApiKeys.length,
      last_active_at: latestIso([lastTaskAt, lastKeyUsedAt, lastLedgerAt].filter(Boolean)),
      tasks_total: userTasks.length,
      tasks_completed: completedTasks.length,
      tasks_failed: failedTasks.length,
      tasks_active: activeTasks.length,
      revenue: roundMoney(completedTasks.reduce((sum, task) => sum + Number(task.finalCost ?? 0), 0)),
      frozen_amount: wallet.frozen,
      ledger_total: ledger.length,
    });
  }

  const sortedCustomers = customers
    .sort((a, b) => {
      if (b.revenue !== a.revenue) {
        return b.revenue - a.revenue;
      }
      return new Date(b.last_active_at ?? 0).getTime() - new Date(a.last_active_at ?? 0).getTime();
    })
    .slice(0, limit);

  return {
    summary: {
      users_total: customers.length,
      active_subscriptions: customers.filter((customer) => ["trialing", "active"].includes(customer.subscription_status)).length,
      active_api_keys: customers.reduce((sum, customer) => sum + customer.api_keys_active, 0),
      total_balance: roundMoney(customers.reduce((sum, customer) => sum + Number(customer.wallet.available ?? 0), 0)),
      total_revenue: roundMoney(customers.reduce((sum, customer) => sum + customer.revenue, 0)),
    },
    customers: sortedCustomers,
  };
}

async function billingTransactions(limit = 20) {
  const tasks = (await tasksRepository.list())
    .filter((task) => task.status === "completed" || task.status === "failed" || task.finalCost != null)
    .slice()
    .sort((a, b) => new Date(b.finishedAt ?? b.createdAt).getTime() - new Date(a.finishedAt ?? a.createdAt).getTime());
  const ledger = await publicLedger(undefined);
  const transactions = tasks.map((task) => billingTransactionFromTask(task, ledger));

  return {
    summary: {
      transactions_total: tasks.length,
      settled_total: transactions.filter((item) => item.status === "settled").length,
      released_total: transactions.filter((item) => item.status === "released").length,
      refunded_total: transactions.filter((item) => item.status === "refunded").length,
      revenue: roundMoney(transactions.reduce((sum, item) => sum + item.revenue, 0)),
      cost: roundMoney(transactions.reduce((sum, item) => sum + item.cost, 0)),
      gross_profit: roundMoney(transactions.reduce((sum, item) => sum + item.gross_profit, 0)),
    },
    transactions: transactions.slice(0, limit),
  };
}

async function billingTransactionForTask(task) {
  return billingTransactionFromTask(task, await publicLedger(undefined));
}

function billingTransactionFromTask(task, ledger) {
  const taskLedger = ledger
    .filter((item) => item.task_id === task.id)
    .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
  const billableAttempt = latestBillableAttempt(task);
  const provider = catalogRepository.getProvider(billableAttempt?.providerId);
  const refundAmount = taskLedger
    .filter((item) => item.type === "refund")
    .reduce((sum, item) => sum + Number(item.amount ?? 0), 0);
  const revenue = task.status === "completed" ? Math.max(0, Number(task.finalCost ?? 0) - refundAmount) : 0;
  const cost = task.status === "completed" ? taskCost(task) : 0;
  const grossProfit = revenue - cost;
  const status = refundAmount > 0 ? "refunded" : task.status === "completed" ? "settled" : "released";

  return {
    transaction_id: `txn_${task.id}`,
    task_id: task.id,
    user_id: task.userId,
    model: task.platformModelId,
    provider: provider?.name ?? billableAttempt?.providerId ?? null,
    status,
    revenue: roundMoney(revenue),
    cost: roundMoney(cost),
    refund_amount: roundMoney(refundAmount),
    gross_profit: roundMoney(grossProfit),
    gross_margin: revenue > 0 ? roundMoney(grossProfit / revenue) : 0,
    ledger_entries: taskLedger,
    ledger_entry_count: taskLedger.length,
    created_at: task.createdAt,
    settled_at: task.settledAt ?? task.finishedAt ?? null,
  };
}

async function billingInvoices(period) {
  const ledger = await publicLedger(undefined);
  const transactions = (await tasksRepository.list())
    .filter((task) => task.status === "completed" || task.status === "failed" || task.finalCost != null)
    .map((task) => billingTransactionFromTask(task, ledger))
    .filter((transaction) => isWithinPeriod(transaction.settled_at ?? transaction.created_at, period));

  const invoicesByUser = new Map();
  for (const transaction of transactions) {
    const invoice =
      invoicesByUser.get(transaction.user_id) ??
      {
        invoice_id: `inv_${period.start.slice(0, 7).replace("-", "")}_${transaction.user_id}`,
        user_id: transaction.user_id,
        period_start: period.start,
        period_end: period.end,
        currency: "CNY",
        status: "open",
        tasks_total: 0,
        settled_total: 0,
        released_total: 0,
        refunded_total: 0,
        revenue: 0,
        refunds: 0,
        cost: 0,
        gross_profit: 0,
        net_amount_due: 0,
        transactions: [],
      };

    invoice.tasks_total += 1;
    if (transaction.status === "settled") {
      invoice.settled_total += 1;
    }
    if (transaction.status === "released") {
      invoice.released_total += 1;
    }
    if (transaction.status === "refunded") {
      invoice.refunded_total += 1;
    }
    invoice.revenue += transaction.revenue;
    invoice.refunds += transaction.refund_amount;
    invoice.cost += transaction.cost;
    invoice.gross_profit += transaction.gross_profit;
    invoice.net_amount_due += transaction.revenue;
    invoice.transactions.push(transaction);
    invoicesByUser.set(transaction.user_id, invoice);
  }

  const invoices = Array.from(invoicesByUser.values())
    .map((invoice) => ({
      ...invoice,
      revenue: roundMoney(invoice.revenue),
      refunds: roundMoney(invoice.refunds),
      cost: roundMoney(invoice.cost),
      gross_profit: roundMoney(invoice.gross_profit),
      net_amount_due: roundMoney(invoice.net_amount_due),
      transaction_count: invoice.transactions.length,
    }))
    .sort((a, b) => b.net_amount_due - a.net_amount_due || a.user_id.localeCompare(b.user_id));

  return {
    period,
    summary: {
      invoices_total: invoices.length,
      tasks_total: invoices.reduce((sum, invoice) => sum + invoice.tasks_total, 0),
      settled_total: invoices.reduce((sum, invoice) => sum + invoice.settled_total, 0),
      released_total: invoices.reduce((sum, invoice) => sum + invoice.released_total, 0),
      refunded_total: invoices.reduce((sum, invoice) => sum + invoice.refunded_total, 0),
      revenue: roundMoney(invoices.reduce((sum, invoice) => sum + invoice.revenue, 0)),
      refunds: roundMoney(invoices.reduce((sum, invoice) => sum + invoice.refunds, 0)),
      cost: roundMoney(invoices.reduce((sum, invoice) => sum + invoice.cost, 0)),
      gross_profit: roundMoney(invoices.reduce((sum, invoice) => sum + invoice.gross_profit, 0)),
      net_amount_due: roundMoney(invoices.reduce((sum, invoice) => sum + invoice.net_amount_due, 0)),
    },
    invoices,
  };
}

function invoicesToCsv(invoices) {
  const rows = [
    [
      "invoice_id",
      "user_id",
      "period_start",
      "period_end",
      "status",
      "currency",
      "tasks_total",
      "settled_total",
      "released_total",
      "refunded_total",
      "revenue",
      "refunds",
      "cost",
      "gross_profit",
      "net_amount_due",
    ],
    ...invoices.invoices.map((invoice) => [
      invoice.invoice_id,
      invoice.user_id,
      invoice.period_start,
      invoice.period_end,
      invoice.status,
      invoice.currency,
      invoice.tasks_total,
      invoice.settled_total,
      invoice.released_total,
      invoice.refunded_total,
      invoice.revenue,
      invoice.refunds,
      invoice.cost,
      invoice.gross_profit,
      invoice.net_amount_due,
    ]),
  ];

  return rows.map((row) => row.map(csvCell).join(",")).join("\n");
}

function groupAnalytics(tasks, keyForTask) {
  const groups = new Map();

  for (const task of tasks) {
    const key = keyForTask(task);
    const current =
      groups.get(key) ?? {
        key,
        tasks_total: 0,
        tasks_completed: 0,
        tasks_failed: 0,
        revenue: 0,
        cost: 0,
      };

    current.tasks_total += 1;
    if (task.status === "completed") {
      current.tasks_completed += 1;
      current.revenue += Number(task.finalCost ?? 0);
      current.cost += taskCost(task);
    }
    if (task.status === "failed") {
      current.tasks_failed += 1;
    }
    groups.set(key, current);
  }

  return Array.from(groups.values())
    .map((group) => {
      const grossProfit = group.revenue - group.cost;
      return {
        ...group,
        revenue: roundMoney(group.revenue),
        cost: roundMoney(group.cost),
        gross_profit: roundMoney(grossProfit),
        gross_margin: group.revenue > 0 ? roundMoney(grossProfit / group.revenue) : 0,
      };
    })
    .sort((a, b) => b.revenue - a.revenue)
    .slice(0, 8);
}

function taskCost(task) {
  return (task.attempts ?? [])
    .filter((attempt) => attempt.status === "completed")
    .reduce((sum, attempt) => sum + Number(attempt.costPrice ?? 0), 0);
}

function reliabilitySummary(tasks) {
  const total = tasks.length;
  const failed = tasks.filter((task) => task.status === "failed").length;
  const completed = tasks.filter((task) => task.status === "completed").length;
  const active = tasks.filter((task) => ["queued", "running", "saving_media"].includes(task.status)).length;

  return {
    success_rate: total > 0 ? roundMoney(completed / total) : 0,
    failure_rate: total > 0 ? roundMoney(failed / total) : 0,
    active_rate: total > 0 ? roundMoney(active / total) : 0,
  };
}

function errorCodeSummary(tasks) {
  const groups = new Map();

  for (const task of tasks) {
    if (task.status !== "failed" && !task.publicErrorCode) {
      continue;
    }
    const attempt = latestErroredAttempt(task);
    const code = task.publicErrorCode ?? attempt?.errorCode ?? "UNKNOWN_ERROR";
    const current =
      groups.get(code) ?? {
        code,
        count: 0,
        task_ids: [],
        latest_message: "",
      };
    current.count += 1;
    current.task_ids.push(task.id);
    current.latest_message = task.publicErrorMessage ?? attempt?.errorMessage ?? current.latest_message;
    groups.set(code, current);
  }

  return Array.from(groups.values())
    .sort((a, b) => b.count - a.count)
    .slice(0, 8);
}

function providerHealthSummary(tasks) {
  const groups = new Map();

  for (const task of tasks) {
    for (const attempt of task.attempts ?? []) {
      const provider = catalogRepository.getProvider(attempt.providerId);
      const key = provider?.name ?? attempt.providerId ?? "unrouted";
      const current =
        groups.get(key) ?? {
          provider: key,
          attempts_total: 0,
          attempts_completed: 0,
          attempts_failed: 0,
          cost: 0,
        };

      current.attempts_total += 1;
      if (attempt.status === "completed") {
        current.attempts_completed += 1;
        current.cost += Number(attempt.costPrice ?? 0);
      }
      if (attempt.status === "failed") {
        current.attempts_failed += 1;
      }
      groups.set(key, current);
    }
  }

  return Array.from(groups.values())
    .map((group) => ({
      ...group,
      success_rate: group.attempts_total > 0 ? roundMoney(group.attempts_completed / group.attempts_total) : 0,
      failure_rate: group.attempts_total > 0 ? roundMoney(group.attempts_failed / group.attempts_total) : 0,
      cost: roundMoney(group.cost),
    }))
    .sort((a, b) => b.attempts_total - a.attempts_total)
    .slice(0, 8);
}

function commercialReadinessSummary() {
  const models = catalogRepository.listPlatformModels().filter((model) => model.visible !== false);
  const items = models.map(commercialReadinessItem);
  const sellableModels = items.filter((item) => item.status === "sellable").length;
  const watchModels = items.filter((item) => item.status === "watch").length;
  const blockedModels = items.filter((item) => item.status === "blocked").length;
  const totalChannels = items.reduce((sum, item) => sum + item.route.total_channels, 0);
  const activeChannels = items.reduce((sum, item) => sum + item.route.active_channels, 0);
  const priorityActions = items
    .flatMap((item) =>
      item.actions.map((action) => ({
        model_id: item.model.id,
        model_name: item.model.name,
        status: item.status,
        action,
      }))
    )
    .slice(0, 10);

  return {
    generated_at: new Date().toISOString(),
    summary: {
      models_total: items.length,
      sellable_models: sellableModels,
      watch_models: watchModels,
      blocked_models: blockedModels,
      total_channels: totalChannels,
      active_channels: activeChannels,
      average_gross_margin:
        items.length > 0
          ? roundRatio(items.reduce((sum, item) => sum + item.pricing.gross_margin, 0) / items.length)
          : 0,
    },
    items,
    priority_actions: priorityActions,
  };
}

function commercialReadinessItem(model) {
  const channels = catalogRepository.listChannelsForModel(model.id);
  const activeChannels = channels.filter((channel) => channel.status === "active");
  const fallbackChannels = channels.filter((channel) => channel.role === "backup" || channel.status === "degraded");
  const pricedChannels = activeChannels.length > 0 ? activeChannels : channels;
  const cost = lowestPositive(pricedChannels.map((channel) => Number(channel.costPrice ?? 0)));
  const sale = highestPositive(pricedChannels.map((channel) => Number(channel.salePrice ?? 0)));
  const grossMargin = sale > 0 ? Math.max(-1, (sale - cost) / sale) : 0;
  const mappedFields = mappedSchemaFieldsForModel(model, channels);
  const totalFields = (model.schema ?? []).length;
  const coverage = totalFields > 0 ? Math.round((mappedFields.length / totalFields) * 100) : 100;
  const providers = uniqueProvidersForChannels(channels);
  const activeProviders = providers.filter((provider) => provider.status === "active");
  const successRate = averageNumber(
    activeChannels.map((channel) => channel.successRate),
    activeProviders.map((provider) => provider.successRate)
  );
  const latency = averageNumber(
    activeChannels.map((channel) => channel.latency),
    activeProviders.map((provider) => provider.latencyMs)
  );
  const missingFields = (model.schema ?? [])
    .filter((field) => !mappedFields.includes(field.key))
    .map((field) => field.key);
  const actions = [];

  if (channels.length === 0) {
    actions.push("Bind at least one upstream channel.");
  }
  if (activeChannels.length === 0) {
    actions.push("Enable one active channel for production routing.");
  }
  if (fallbackChannels.length === 0 && activeChannels.length <= 1) {
    actions.push("Add a backup channel to avoid single-provider failure.");
  }
  if (sale <= 0) {
    actions.push("Set a user-facing sale price.");
  } else if (cost <= 0) {
    actions.push("Set upstream cost price so gross margin is measurable.");
  } else if (grossMargin < 0.25) {
    actions.push("Raise price or route to a cheaper channel; target at least 25% margin.");
  }
  if (coverage < 100) {
    actions.push(`Complete parameter mapping for: ${missingFields.slice(0, 3).join(", ")}.`);
  }
  if (successRate > 0 && successRate < 96) {
    actions.push("Provider success rate is low; lower weight or keep it as backup.");
  }
  if (latency > 1500) {
    actions.push("Latency is high; add a faster route for fast mode.");
  }
  if (actions.length === 0) {
    actions.push("Ready for controlled traffic; keep monitoring price and route health.");
  }

  const blocked = channels.length === 0 || activeChannels.length === 0 || sale <= 0 || coverage < 70;
  const sellable = !blocked && grossMargin >= 0.25 && coverage === 100 && activeProviders.length > 0 && activeChannels.length > 1;
  const status = sellable ? "sellable" : blocked ? "blocked" : "watch";

  return {
    model: {
      id: model.id,
      name: model.name,
      short_name: model.shortName,
      modality: model.modality,
      tier: model.tier,
      recommended: Boolean(model.recommended),
    },
    status,
    summary:
      status === "sellable"
        ? "Pricing, routing, parameter coverage, and provider health meet baseline selling conditions."
        : status === "watch"
          ? "Can be tested with controlled traffic, but margin, backup routes, or health redundancy still need work."
          : "Key launch conditions are missing; keep it hidden from ordinary users.",
    pricing: {
      cost_price: roundMoney(cost),
      sale_price: roundMoney(sale),
      gross_margin: roundRatio(grossMargin),
    },
    route: {
      total_channels: channels.length,
      active_channels: activeChannels.length,
      backup_channels: fallbackChannels.length,
      success_rate: roundRatio(successRate / 100),
      latency_ms: roundMoney(latency),
      providers: providers.map((provider) => ({
        id: provider.id,
        name: provider.name,
        status: provider.status,
        success_rate: provider.successRate,
      })),
    },
    schema: {
      total_fields: totalFields,
      covered_fields: mappedFields.length,
      coverage,
      missing_fields: missingFields,
    },
    actions,
  };
}

function mappedSchemaFieldsForModel(model, channels) {
  const fieldKeys = new Set((model.schema ?? []).map((field) => field.key));
  const mappedFields = new Set();

  for (const channel of channels) {
    for (const fieldKey of channel.supports ?? []) {
      if (fieldKeys.has(fieldKey)) {
        mappedFields.add(fieldKey);
      }
    }

    for (const mapping of catalogRepository.getChannelMappings(channel.id)) {
      if (fieldKeys.has(mapping.platform) && mapping.transform !== "omit") {
        mappedFields.add(mapping.platform);
      }
    }
  }

  return Array.from(mappedFields);
}

function uniqueProvidersForChannels(channels) {
  const providerIds = new Set(channels.map((channel) => channel.providerId));
  return catalogRepository.listProviders().filter((provider) => providerIds.has(provider.id));
}

function lowestPositive(values) {
  const positives = values.filter((value) => Number.isFinite(value) && value > 0);
  return positives.length > 0 ? Math.min(...positives) : 0;
}

function highestPositive(values) {
  const positives = values.filter((value) => Number.isFinite(value) && value > 0);
  return positives.length > 0 ? Math.max(...positives) : 0;
}

function averageNumber(primary, fallback = []) {
  const values = primary.filter((value) => Number.isFinite(Number(value)) && Number(value) > 0).map(Number);
  const fallbackValues = fallback.filter((value) => Number.isFinite(Number(value)) && Number(value) > 0).map(Number);
  const source = values.length > 0 ? values : fallbackValues;
  return source.length > 0 ? source.reduce((sum, value) => sum + value, 0) / source.length : 0;
}

function roundMoney(value) {
  return Math.round((Number(value) + Number.EPSILON) * 100) / 100;
}

function roundRatio(value) {
  return Math.round((Number(value) + Number.EPSILON) * 1000) / 1000;
}

function latestIso(values) {
  let latest = null;
  for (const value of values) {
    if (!value) {
      continue;
    }
    const timestamp = new Date(value).getTime();
    if (!Number.isFinite(timestamp)) {
      continue;
    }
    if (!latest || timestamp > new Date(latest).getTime()) {
      latest = new Date(timestamp).toISOString();
    }
  }
  return latest;
}

function nextMonthIso() {
  const now = new Date();
  return new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + 1, 1)).toISOString();
}

function latestBillableAttempt(task) {
  const attempts = task.attempts ?? [];
  for (let index = attempts.length - 1; index >= 0; index -= 1) {
    if (attempts[index].status === "completed") {
      return attempts[index];
    }
  }
  return attempts.length > 0 ? attempts[attempts.length - 1] : undefined;
}

function latestErroredAttempt(task) {
  const attempts = task.attempts ?? [];
  for (let index = attempts.length - 1; index >= 0; index -= 1) {
    if (attempts[index].status === "failed" || attempts[index].errorCode) {
      return attempts[index];
    }
  }
  return undefined;
}

async function publicLedger(userId) {
  const ledger = await billingRepository.listLedger(userId);
  return ledger.map((item) => ({
    id: item.id,
    user_id: item.userId,
    task_id: item.taskId,
    type: item.type,
    amount: item.amount,
    balance_after: item.balanceAfter,
    frozen_after: item.frozenAfter,
    note: item.note,
    created_at: item.createdAt,
  }));
}

function publicPaymentOrder(order) {
  return {
    id: order.id,
    user_id: order.userId,
    amount: order.amount,
    currency: order.currency,
    provider: order.provider,
    status: order.status,
    idempotency_key: order.idempotencyKey ?? null,
    provider_transaction_id: order.providerTransactionId ?? null,
    paid_at: order.paidAt ?? null,
    credited_ledger_id: order.creditedLedgerId ?? null,
    metadata: order.metadata ?? {},
    created_at: order.createdAt,
    updated_at: order.updatedAt,
  };
}

function publicPaymentProvider(provider) {
  return {
    id: provider.id,
    name: provider.name,
    kind: provider.kind,
    status: provider.status,
    currencies: provider.currencies ?? [],
    fee_rate: provider.feeRate,
    fixed_fee: provider.fixedFee,
    min_amount: provider.minAmount,
    max_amount: provider.maxAmount,
    checkout_mode: provider.checkoutMode,
    metadata: provider.metadata ?? {},
  };
}

function adminPaymentProvider(provider) {
  return {
    ...publicPaymentProvider(provider),
    webhook_secret_set: Boolean(provider.webhookSecret),
    sort_order: provider.sortOrder ?? 50,
    created_at: provider.createdAt,
    updated_at: provider.updatedAt,
  };
}

async function buildPaymentOrder(body, userId) {
  const providerId = String(body.provider ?? "mock").trim() || "mock";
  const provider = await paymentProvidersRepository.findById(providerId);
  if (!provider || provider.status !== "active") {
    throw problem(422, "PAYMENT_PROVIDER_UNAVAILABLE", "Payment provider is not available.");
  }

  const amount = boundedNumber(
    body.amount,
    provider.minAmount,
    provider.maxAmount,
    `Payment amount must be between ${provider.minAmount} and ${provider.maxAmount}.`
  );
  const currency = String(body.currency ?? provider.currencies?.[0] ?? "CNY").trim().toUpperCase() || "CNY";
  if (!provider.currencies?.includes(currency)) {
    throw problem(422, "PAYMENT_CURRENCY_UNSUPPORTED", "Payment currency is not supported by this provider.");
  }

  const idempotencyKey = String(body.idempotency_key ?? body.idempotencyKey ?? "").trim() || null;
  const now = new Date().toISOString();
  const orderId = normalizeId(body.id, "pay");

  return {
    id: orderId,
    userId,
    amount: roundMoney(amount),
    currency,
    provider: provider.id,
    status: "pending",
    idempotencyKey,
    providerTransactionId: null,
    paidAt: null,
    creditedLedgerId: null,
    metadata: {
      source: body.source ?? "user_console",
      provider_name: provider.name,
      checkout_mode: provider.checkoutMode,
      checkout_url: checkoutUrlForProvider(provider, orderId),
      provider_fee_estimate: roundMoney(roundMoney(amount) * Number(provider.feeRate ?? 0) + Number(provider.fixedFee ?? 0)),
    },
    createdAt: now,
    updatedAt: now,
  };
}

function checkoutUrlForProvider(provider, orderId) {
  if (provider.checkoutMode === "mock") {
    return `mockpay://checkout/${orderId}`;
  }
  if (provider.checkoutMode === "manual") {
    return `manual://payment-orders/${orderId}`;
  }
  if (provider.checkoutMode === "qr_code") {
    return `tikpanpay://qr/${provider.id}/${orderId}`;
  }
  if (provider.checkoutMode === "redirect") {
    return `https://pay.tikpan.local/${provider.id}/orders/${orderId}`;
  }
  return `https://checkout.tikpan.local/${provider.id}/orders/${orderId}`;
}

async function closePaymentOrder(order, status, source = "system") {
  if (!["cancelled", "expired"].includes(status)) {
    throw problem(422, "PAYMENT_ORDER_CLOSE_STATUS_INVALID", "Payment order close status is invalid.");
  }

  if (order.status === status) {
    return order;
  }

  if (order.status === "paid") {
    throw problem(409, "PAYMENT_ORDER_ALREADY_PAID", "Paid payment orders cannot be closed.");
  }

  if (order.status !== "pending") {
    throw problem(409, "PAYMENT_ORDER_NOT_CLOSABLE", "Payment order cannot be closed in its current status.", {
      status: order.status,
    });
  }

  const closedAt = new Date().toISOString();
  const updated = await paymentOrdersRepository.update({
    ...order,
    status,
    metadata: {
      ...(order.metadata ?? {}),
      closed_source: source,
      closed_at: closedAt,
    },
    updatedAt: closedAt,
  });

  recordAudit({
    actorType: source === "user_console" ? "user" : "system",
    actorId: source === "user_console" ? order.userId : source,
    action: `payment_order.${status}`,
    resourceType: "payment_order",
    resourceId: order.id,
    userId: order.userId,
    summary: `Payment order ${order.id} ${status}.`,
    metadata: { amount: order.amount, provider: order.provider, source },
  });

  return updated;
}

async function confirmPaymentOrder(
  order,
  { providerTransactionId, source = "mock", actorId = order.userId, actorType = "user" } = {}
) {
  if (order.status === "paid") {
    return {
      order: publicPaymentOrder(order),
      wallet: publicWallet(await billingRepository.getWallet(order.userId)),
      ledger: (await publicLedger(order.userId)).slice(-8).reverse(),
      idempotent: true,
    };
  }

  if (order.status !== "pending") {
    throw problem(409, "PAYMENT_ORDER_NOT_PAYABLE", "Payment order cannot be confirmed in its current status.", {
      status: order.status,
    });
  }

  const wallet = await topUpWallet(order.userId, order.amount, `Payment order ${order.id}`);
  const ledger = await publicLedger(order.userId);
  const creditedLedger = ledger
    .slice()
    .reverse()
    .find((item) => item.type === "top_up" && item.note === `Payment order ${order.id}`);

  const paidAt = new Date().toISOString();
  const updated = await paymentOrdersRepository.update({
    ...order,
    status: "paid",
    providerTransactionId: String(providerTransactionId ?? `${order.provider}_${order.id}`).trim(),
    paidAt,
    creditedLedgerId: creditedLedger?.id ?? null,
    metadata: {
      ...(order.metadata ?? {}),
      confirmed_source: source,
    },
    updatedAt: paidAt,
  });

  recordAudit({
    actorType,
    actorId,
    action: "payment_order.paid",
    resourceType: "payment_order",
    resourceId: order.id,
    userId: order.userId,
    summary: `Payment order ${order.id} paid and credited.`,
    metadata: { amount: order.amount, provider: order.provider, ledger_id: creditedLedger?.id ?? null },
  });

  return {
    order: publicPaymentOrder(updated),
    wallet: publicWallet(wallet),
    ledger: ledger.slice(-8).reverse(),
    idempotent: false,
  };
}

async function resolveTaskUser(req, body) {
  const apiKey = getBearerToken(req);
  if (!apiKey) {
    return body.user_id ?? "demo_user";
  }

  const key = await apiKeysRepository.findBySecret(apiKey);
  if (!key || key.status !== "active") {
    throw problem(401, "INVALID_API_KEY", "Platform API key is invalid or revoked.");
  }

  if (!key.scopes.includes("tasks:create")) {
    throw problem(403, "FORBIDDEN", "This API key cannot create tasks.");
  }

  await enforceRateLimit(key);
  key.lastUsedAt = new Date().toISOString();
  await apiKeysRepository.touchLastUsed(key.id, key.lastUsedAt);
  return key.userId;
}

async function resolveReadUser(req, fallbackUserId) {
  const apiKey = getBearerToken(req);
  if (!apiKey) {
    return fallbackUserId;
  }

  const key = await apiKeysRepository.findBySecret(apiKey);
  if (!key || key.status !== "active") {
    throw problem(401, "INVALID_API_KEY", "Platform API key is invalid or revoked.");
  }

  if (!key.scopes.includes("wallet:read")) {
    throw problem(403, "FORBIDDEN", "This API key cannot read usage.");
  }

  key.lastUsedAt = new Date().toISOString();
  await apiKeysRepository.touchLastUsed(key.id, key.lastUsedAt);
  return key.userId;
}

async function assertTaskReadable(req, task) {
  const apiKey = getBearerToken(req);
  if (!apiKey) {
    return;
  }

  const key = await apiKeysRepository.findBySecret(apiKey);
  if (!key || key.status !== "active") {
    throw problem(401, "INVALID_API_KEY", "Platform API key is invalid or revoked.");
  }

  if (!key.scopes.includes("wallet:read")) {
    throw problem(403, "FORBIDDEN", "This API key cannot read tasks.");
  }

  if (task.userId !== key.userId) {
    throw problem(404, "TASK_NOT_FOUND", "Task does not exist.");
  }

  key.lastUsedAt = new Date().toISOString();
  await apiKeysRepository.touchLastUsed(key.id, key.lastUsedAt);
}

async function enforceRateLimit(key) {
  const subscription = await usageRepository.getUserSubscription(key.userId);
  const plan = await usageRepository.getBillingPlan(subscription.planId);
  const limit = Number(plan?.rateLimitPerMinute ?? 60);

  if (usageRepository.consumeRateLimit) {
    const result = await usageRepository.consumeRateLimit(key.id, limit);
    if (!result.allowed) {
      throw problem(429, "RATE_LIMIT_EXCEEDED", "Too many requests. Please retry later.", {
        rate_limit: {
          limit,
          remaining: 0,
          reset_at: new Date(result.resetAt).toISOString(),
        },
      });
    }
    return;
  }

  const now = Date.now();
  const windowMs = 60_000;
  let bucket = await usageRepository.getRateLimitBucket(key.id);

  if (!bucket || now >= bucket.resetAt) {
    bucket = await usageRepository.upsertRateLimitBucket({
      apiKeyId: key.id,
      count: 0,
      resetAt: now + windowMs,
    });
  }

  if (bucket.count >= limit) {
    throw problem(429, "RATE_LIMIT_EXCEEDED", "Too many requests. Please retry later.", {
      rate_limit: {
        limit,
        remaining: 0,
        reset_at: new Date(bucket.resetAt).toISOString(),
      },
    });
  }

  bucket.count += 1;
}

function getBearerToken(req) {
  const auth = req.headers.authorization;
  if (!auth || !auth.toLowerCase().startsWith("bearer ")) {
    return null;
  }
  return auth.slice(7).trim();
}

function assertAdminAuthorized(req, url) {
  if (!url.pathname.startsWith("/admin/") || !config.adminToken) {
    return;
  }

  const token = getBearerToken(req);
  if (!token || !secureTokenEquals(token, config.adminToken)) {
    throw problem(401, "ADMIN_AUTH_REQUIRED", "Admin authorization is required.");
  }
}

function secureTokenEquals(received, expected) {
  const receivedHash = createHash("sha256").update(String(received)).digest();
  const expectedHash = createHash("sha256").update(String(expected)).digest();
  return timingSafeEqual(receivedHash, expectedHash);
}

async function createApiKey({ userId, name, scopes }) {
  const suffix = Math.random().toString(36).slice(2, 10);
  const key = {
    id: createId("key"),
    userId,
    name,
    prefix: `tk_${suffix.slice(0, 6)}`,
    secret: `tk_${suffix}_${Math.random().toString(36).slice(2, 18)}`,
    status: "active",
    scopes,
    lastUsedAt: null,
    createdAt: new Date().toISOString(),
  };
  return apiKeysRepository.create(key);
}

function publicApiKey(key) {
  return {
    id: key.id,
    user_id: key.userId,
    name: key.name,
    prefix: key.prefix,
    masked: `${key.prefix}_****************`,
    status: key.status,
    scopes: key.scopes,
    last_used_at: key.lastUsedAt,
    created_at: key.createdAt,
    revoked_at: key.revokedAt ?? null,
  };
}

function publicUser(user) {
  return {
    id: user.id,
    display_name: user.displayName,
    email: user.email ?? null,
    status: user.status,
    created_at: user.createdAt,
    updated_at: user.updatedAt,
  };
}

async function publicUserProfile(user) {
  const subscription = await usageRepository.getUserSubscription(user.id);
  const plan = subscription?.planId ? await usageRepository.getBillingPlan(subscription.planId) : null;
  const tasks = tasksRepository
    .list()
    .filter((task) => task.userId === user.id)
    .slice()
    .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
    .slice(0, 8)
    .map(publicTask);

  return {
    user: publicUser(user),
    subscription,
    plan,
    wallet: publicWallet(await billingRepository.getWallet(user.id)),
    ledger: (await publicLedger(user.id)).slice(-8).reverse(),
    payment_orders: (await paymentOrdersRepository.list({ userId: user.id, limit: 8 })).map(publicPaymentOrder),
    presets: presetsRepository.list({ userId: user.id, limit: 20 }).map(publicPreset),
    tasks,
  };
}

async function publicUserSession(user, key) {
  return {
    ...(await publicUserProfile(user)),
    api_key: {
      ...publicApiKey(key),
      secret: key.secret,
    },
  };
}

function publicPreset(preset) {
  return {
    id: preset.id,
    user_id: preset.userId,
    name: preset.name,
    description: preset.description ?? "",
    model: preset.platformModelId,
    route_mode: preset.routeMode ?? "balanced",
    input: preset.input ?? {},
    usage_count: Number(preset.usageCount ?? 0),
    last_used_at: preset.lastUsedAt ?? null,
    created_at: preset.createdAt,
    updated_at: preset.updatedAt,
  };
}

async function assertPresetWritable(id, userId) {
  const preset = presetsRepository.findById(decodeURIComponent(id));
  if (!preset || preset.userId !== userId) {
    throw problem(404, "PRESET_NOT_FOUND", "Preset does not exist.");
  }

  return preset;
}

function buildPreset(body, userId, existing = null) {
  const modelId = String(body.model ?? body.platform_model_id ?? body.platformModelId ?? existing?.platformModelId ?? "").trim();
  const model = catalogRepository.getPlatformModel(modelId);
  if (!model || !model.visible) {
    throw problem(422, "VALIDATION_ERROR", "Preset must use a visible platform model.");
  }

  const name = String(body.name ?? existing?.name ?? "").trim();
  if (!name) {
    throw problem(422, "VALIDATION_ERROR", "Preset name is required.");
  }

  const routeMode = String(body.route_mode ?? body.routeMode ?? existing?.routeMode ?? "balanced").trim();
  if (!["balanced", "quality", "fast", "cheap", "stable"].includes(routeMode)) {
    throw problem(422, "VALIDATION_ERROR", "Invalid route mode.");
  }

  const input = sanitizePresetInput(model, body.input ?? existing?.input ?? {});
  const now = new Date().toISOString();

  return {
    id: existing?.id ?? normalizeId(body.id, "preset"),
    userId,
    name: name.slice(0, 80),
    description: String(body.description ?? existing?.description ?? "").trim().slice(0, 240),
    platformModelId: model.id,
    routeMode,
    input,
    usageCount: Number(existing?.usageCount ?? 0),
    lastUsedAt: existing?.lastUsedAt ?? null,
    createdAt: existing?.createdAt ?? now,
    updatedAt: now,
  };
}

function buildProject(body, userId, existing = null) {
  const name = String(body.name ?? existing?.name ?? "").trim();
  if (!name) {
    throw problem(422, "VALIDATION_ERROR", "Project name is required.");
  }

  const type = String(body.type ?? existing?.type ?? "general").trim();
  if (!allowedProjectTypes.has(type)) {
    throw problem(422, "VALIDATION_ERROR", "Project type is not supported.");
  }

  const status = String(body.status ?? existing?.status ?? "active").trim();
  if (!allowedProjectStatuses.has(status)) {
    throw problem(422, "VALIDATION_ERROR", "Project status is not supported.");
  }

  const now = new Date().toISOString();
  return {
    id: existing?.id ?? normalizeId(body.id, "proj"),
    userId,
    name: name.slice(0, 100),
    type,
    status,
    description: String(body.description ?? existing?.description ?? "").trim().slice(0, 500),
    coverUrl: normalizeOptionalUrl(body.cover_url ?? body.coverUrl ?? existing?.coverUrl),
    settings: normalizeObject(body.settings ?? existing?.settings, {}),
    tags: normalizeAssetTags(body.tags ?? existing?.tags ?? []),
    createdAt: existing?.createdAt ?? now,
    updatedAt: now,
    archivedAt: status === "archived" ? existing?.archivedAt ?? now : null,
  };
}

function buildManualProjectAsset(body, project, userId) {
  const title = String(body.title ?? "").trim().slice(0, 100);
  const sourceUrl = normalizeOptionalUrl(body.source_url ?? body.sourceUrl);
  const mimeType = normalizeMimeType(body.mime_type ?? body.mimeType);
  const tags = normalizeAssetTags(body.tags ?? []);
  const note = String(body.note ?? "").trim().slice(0, 500);

  if (!title) {
    throw problem(422, "VALIDATION_ERROR", "Asset title is required.");
  }
  if (!sourceUrl) {
    throw problem(422, "VALIDATION_ERROR", "Asset source_url is required.");
  }

  const now = new Date().toISOString();
  const taskId = createId("task");
  const mediaId = createId("media");
  const modality = modalityFromMimeType(mimeType);
  const modelId = defaultManualAssetModel(modality);

  const task = {
    id: taskId,
    userId,
    platformModelId: modelId,
    status: "completed",
    routeMode: "manual",
    input: {
      prompt: title,
      source_url: sourceUrl,
      note,
      tags,
      import_type: "manual_project_asset",
    },
    output: {
      publicUrls: [sourceUrl],
      public_urls: [sourceUrl],
      assets: [`manual/${project.id}/${mediaId}`],
      source: "manual_import",
      mime_type: mimeType,
    },
    estimatedCost: 0,
    finalCost: 0,
    publicErrorCode: null,
    publicErrorMessage: null,
    batchId: null,
    batchTitle: null,
    batchItemId: null,
    projectId: project.id,
    projectName: project.name,
    selectedChannelId: null,
    selectedProviderId: null,
    selectedProviderModelId: null,
    mappedPayload: null,
    currentStep: "Manual asset added to project.",
    progress: 100,
    attempts: [],
    queuedAt: now,
    startedAt: now,
    finishedAt: now,
    settledAt: now,
    releasedAt: null,
    createdAt: now,
    updatedAt: now,
  };

  const mediaAsset = {
    id: mediaId,
    taskId,
    userId,
    direction: "output",
    objectKey: `manual/${project.id}/${mediaId}`,
    publicUrl: sourceUrl,
    mimeType,
    sizeBytes: null,
    width: null,
    height: null,
    durationSeconds: null,
    hash: null,
    sourceUrl,
    storageMode: "local",
    createdAt: now,
  };

  const metadata = {
    taskId,
    userId,
    title,
    note,
    favorite: false,
    reviewStatus: "approved",
    tags,
    collections: [],
    createdAt: now,
    updatedAt: now,
  };

  return { task, mediaAsset, metadata };
}

function normalizeMimeType(value) {
  const mimeType = String(value ?? "").trim().toLowerCase();
  if (!mimeType) {
    throw problem(422, "VALIDATION_ERROR", "Asset mime_type is required.");
  }
  if (!/^[a-z0-9.+-]+\/[a-z0-9.+-]+$/.test(mimeType)) {
    throw problem(422, "VALIDATION_ERROR", "Asset mime_type is invalid.");
  }
  if (!["image/", "video/", "audio/", "text/", "application/pdf"].some((prefix) => mimeType.startsWith(prefix))) {
    throw problem(422, "VALIDATION_ERROR", "Asset mime_type is not supported.");
  }
  return mimeType;
}

function modalityFromMimeType(mimeType) {
  if (mimeType.startsWith("video/")) {
    return "video";
  }
  if (mimeType.startsWith("audio/")) {
    return "audio";
  }
  if (mimeType.startsWith("text/") || mimeType === "application/pdf") {
    return "chat";
  }
  return "image";
}

function defaultManualAssetModel(modality) {
  const preferredByModality = {
    image: "tikpan.image.gpt-image-2-4k",
    video: "tikpan.image.gpt-image-2-4k",
    audio: "tikpan.chat.claude-fable-5",
    chat: "tikpan.chat.claude-fable-5",
  };
  const preferred = catalogRepository.getPlatformModel(preferredByModality[modality]);
  if (preferred) {
    return preferred.id;
  }

  const fallback = catalogRepository.listPlatformModels().find((model) => model.visible) ?? catalogRepository.listPlatformModels()[0];
  if (!fallback) {
    throw problem(500, "CATALOG_EMPTY", "No platform model is available for asset attribution.");
  }
  return fallback.id;
}

async function optionalWritableProject(projectId, userId) {
  const id = String(projectId ?? "").trim();
  if (!id) {
    return null;
  }
  return assertProjectWritable(id, userId);
}

async function assertProjectReadable(projectId, userId) {
  const project = await projectsRepository.findById(projectId);
  if (!project || project.userId !== userId || project.status === "archived") {
    throw problem(404, "PROJECT_NOT_FOUND", "Project does not exist.");
  }
  return project;
}

async function assertProjectWritable(projectId, userId) {
  const project = await assertProjectReadable(projectId, userId);
  if (project.status === "archived") {
    throw problem(409, "PROJECT_ARCHIVED", "Archived projects cannot be changed.");
  }
  return project;
}

async function touchProject(project) {
  await projectsRepository.save({
    ...project,
    updatedAt: new Date().toISOString(),
  });
}

function sanitizePresetInput(model, input) {
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    throw problem(422, "VALIDATION_ERROR", "Preset input must be an object.");
  }

  const allowedFields = new Set((model.schema ?? []).map((field) => field.key));
  return Object.fromEntries(
    Object.entries(input)
      .filter(([key]) => allowedFields.has(key))
      .filter(([, value]) => value !== undefined && value !== null && value !== "")
  );
}

function buildUserUpsert(body, existing = null) {
  const id = existing?.id ?? normalizeId(body.id ?? body.user_id ?? body.userId, "user");
  const displayName = String(body.display_name ?? body.displayName ?? existing?.displayName ?? "").trim();
  if (!displayName) {
    throw problem(422, "VALIDATION_ERROR", "User display name is required.");
  }

  const status = String(body.status ?? existing?.status ?? "active").trim();
  if (!allowedUserStatuses.has(status)) {
    throw problem(422, "VALIDATION_ERROR", "Invalid user status.");
  }

  const email = normalizeOptionalEmail(body.email ?? existing?.email);
  const now = new Date().toISOString();
  return {
    id,
    displayName,
    email,
    status,
    createdAt: existing?.createdAt ?? now,
    updatedAt: now,
  };
}

function buildWebhookEndpoint(body) {
  const id = String(body.id ?? createId("wh")).trim();
  const userId = String(body.user_id ?? "demo_user").trim() || "demo_user";
  const url = String(body.url ?? "").trim();
  const status = String(body.status ?? "active").trim();
  const events = Array.isArray(body.events) ? body.events.map((event) => String(event).trim()).filter(Boolean) : [];

  if (!id) {
    throw problem(422, "VALIDATION_ERROR", "Webhook endpoint id is required.");
  }
  try {
    const parsed = new URL(url);
    if (!["http:", "https:"].includes(parsed.protocol)) {
      throw new Error("Unsupported protocol.");
    }
  } catch {
    throw problem(422, "VALIDATION_ERROR", "Webhook URL must be a valid HTTP or HTTPS URL.");
  }
  if (!allowedWebhookStatuses.has(status)) {
    throw problem(422, "VALIDATION_ERROR", "Webhook status is not supported.");
  }
  if (events.length === 0 || events.some((event) => !allowedWebhookEvents.has(event))) {
    throw problem(422, "VALIDATION_ERROR", "Webhook events must be supported platform events.");
  }

  return {
    id,
    userId,
    url,
    events,
    status,
    secret: String(body.secret ?? "").trim() || undefined,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };
}

function publicWebhookEndpoint(endpoint) {
  return {
    id: endpoint.id,
    user_id: endpoint.userId,
    url: endpoint.url,
    events: endpoint.events,
    status: endpoint.status,
    secret_set: Boolean(endpoint.secret),
    created_at: endpoint.createdAt,
    updated_at: endpoint.updatedAt,
  };
}

function publicWebhookDelivery(delivery) {
  return {
    id: delivery.id,
    endpoint_id: delivery.endpointId,
    user_id: delivery.userId,
    task_id: delivery.taskId,
    event: delivery.event,
    target_url: delivery.targetUrl,
    status: delivery.status,
    response_status: delivery.responseStatus,
    attempt: delivery.attempt,
    payload: delivery.payload,
    error_message: delivery.errorMessage,
    created_at: delivery.createdAt,
    delivered_at: delivery.deliveredAt,
  };
}

function publicAuditLog(entry) {
  return {
    id: entry.id,
    actor_id: entry.actorId,
    actor_type: entry.actorType,
    action: entry.action,
    resource_type: entry.resourceType,
    resource_id: entry.resourceId,
    user_id: entry.userId,
    summary: entry.summary,
    metadata: entry.metadata ?? {},
    created_at: entry.createdAt,
  };
}

function recordAudit({
  actorId = "admin",
  actorType = "admin",
  action,
  resourceType,
  resourceId,
  userId = null,
  summary,
  metadata = {},
}) {
  auditRepository.create({
    id: createId("audit"),
    actorId,
    actorType,
    action,
    resourceType,
    resourceId: String(resourceId ?? ""),
    userId,
    summary,
    metadata,
    createdAt: new Date().toISOString(),
  });
}

function publicPlatformModel(model) {
  return {
    id: model.id,
    slug: model.slug ?? slugify(model.id),
    display_name: model.displayName ?? model.name,
    name: model.name,
    short_name: model.shortName,
    modality: model.modality,
    tier: model.tier,
    description: model.description,
    use_cases: model.useCases,
    recommended: model.recommended,
    estimated_cost: model.estimatedCost,
    estimated_time: model.estimatedTime,
    schema: model.schema ?? [],
    category_ids: model.categoryIds ?? catalogRepository.listCategoriesForModel(model.id).map((category) => category.id),
    category_keys: model.categoryKeys ?? catalogRepository.listCategoriesForModel(model.id).map((category) => category.key),
    categories: (model.categories ?? catalogRepository.listCategoriesForModel(model.id)).map(publicModelCategory),
    aliases: model.aliases ?? catalogRepository.listAliasesForModel(model.id).map((alias) => alias.alias),
  };
}

function adminPlatformModel(model) {
  return {
    id: model.id,
    slug: model.slug ?? slugify(model.id),
    display_name: model.displayName ?? model.name,
    name: model.name,
    short_name: model.shortName,
    modality: model.modality,
    tier: model.tier,
    description: model.description,
    use_cases: model.useCases,
    visible: model.visible,
    recommended: model.recommended,
    estimated_cost: model.estimatedCost,
    estimated_time: model.estimatedTime,
    schema: model.schema ?? [],
    category_ids: model.categoryIds ?? catalogRepository.listCategoriesForModel(model.id).map((category) => category.id),
    category_keys: model.categoryKeys ?? catalogRepository.listCategoriesForModel(model.id).map((category) => category.key),
    categories: (model.categories ?? catalogRepository.listCategoriesForModel(model.id)).map(adminModelCategory),
    aliases: model.aliases ?? catalogRepository.listAliasesForModel(model.id).map((alias) => alias.alias),
  };
}

function publicModelCategory(category) {
  return {
    id: category.id,
    key: category.key,
    name: category.name,
    icon: category.icon ?? null,
    sort_order: category.sortOrder ?? 0,
    visible: category.visible,
    parent_id: category.parentId ?? null,
    aliases: category.aliases ?? [],
  };
}

function adminModelCategory(category) {
  return {
    ...publicModelCategory(category),
    status: category.status ?? "published",
  };
}

function adminChannel(channel) {
  return {
    ...channel,
    provider: catalogRepository.getProvider(channel.providerId),
    provider_model: catalogRepository.getProviderModel(channel.providerModelId),
    parameter_mappings: catalogRepository.getChannelMappings(channel.id).map(adminParameterMapping),
  };
}

function adminParameterMapping(mapping) {
  return {
    ...mapping,
    platform_param_key: mapping.platform,
    upstream_param_key: mapping.upstream,
    value_map: mapping.valueMap ?? {},
    default_value: mapping.defaultValue,
  };
}

function routePreview(decision, input) {
  const channel = decision.channel;
  const provider = channel ? catalogRepository.getProvider(channel.providerId) : null;
  const providerModel = channel ? catalogRepository.getProviderModel(channel.providerModelId) : null;
  const mappedPayload = channel && providerModel ? mapPayload(channel, providerModel, input) : null;

  return {
    channel: channel
      ? {
          id: channel.id,
          role: channel.role,
          status: channel.status,
          weight: channel.weight,
          cost_price: channel.costPrice,
          sale_price: channel.salePrice,
          latency: channel.latency,
          success_rate: channel.successRate,
        }
      : null,
    provider: provider
      ? {
          id: provider.id,
          name: provider.name,
          status: provider.status,
        }
      : null,
    provider_model: providerModel
      ? {
          id: providerModel.id,
          upstream_model_name: providerModel.upstreamModelName,
        }
      : null,
    mapped_payload: mappedPayload,
    score_breakdown: decision.scoreBreakdown,
    rejected: decision.rejected,
  };
}

function channelTestResult(channel, input) {
  const provider = catalogRepository.getProvider(channel.providerId);
  const providerModel = catalogRepository.getProviderModel(channel.providerModelId);
  const mappedPayload = providerModel ? mapPayload(channel, providerModel, input) : {};
  const checks = [];

  if (!provider) {
    checks.push({ level: "error", code: "PROVIDER_MISSING", message: "Provider is not configured." });
  } else if (provider.status === "active") {
    checks.push({ level: "ok", code: "PROVIDER_ACTIVE", message: "Provider is active." });
  } else {
    checks.push({ level: "warning", code: "PROVIDER_NOT_ACTIVE", message: `Provider status is ${provider.status}.` });
  }

  if (!providerModel) {
    checks.push({ level: "error", code: "PROVIDER_MODEL_MISSING", message: "Provider model is not configured." });
  } else {
    checks.push({ level: "ok", code: "PROVIDER_MODEL_READY", message: `Mapped to ${providerModel.upstreamModelName}.` });
  }

  if (channel.status === "active") {
    checks.push({ level: "ok", code: "CHANNEL_ACTIVE", message: "Channel can receive production traffic." });
  } else {
    checks.push({ level: "warning", code: "CHANNEL_NOT_ACTIVE", message: `Channel status is ${channel.status}.` });
  }

  if (Object.keys(mappedPayload).length <= 1) {
    checks.push({ level: "warning", code: "PAYLOAD_SPARSE", message: "Mapped payload only contains the model field." });
  } else {
    checks.push({ level: "ok", code: "PAYLOAD_MAPPED", message: "Input was mapped into upstream payload fields." });
  }

  return {
    channel: {
      id: channel.id,
      status: channel.status,
      role: channel.role,
      billing_unit: channel.billingUnit,
    },
    provider: provider
      ? {
          id: provider.id,
          name: provider.name,
          status: provider.status,
        }
      : null,
    provider_model: providerModel
      ? {
          id: providerModel.id,
          upstream_model_name: providerModel.upstreamModelName,
          endpoint_type: providerModel.endpointType,
          modality: providerModel.modality,
        }
      : null,
    platform_input: input,
    mapped_payload: mappedPayload,
    checks,
  };
}

function applyChannelPatch(channel, body) {
  if (body.status !== undefined) {
    if (!allowedChannelStatuses.has(body.status)) {
      throw problem(422, "VALIDATION_ERROR", "Invalid channel status.");
    }
    channel.status = body.status;
  }

  if (body.role !== undefined) {
    if (!allowedChannelRoles.has(body.role)) {
      throw problem(422, "VALIDATION_ERROR", "Invalid channel role.");
    }
    channel.role = body.role;
  }

  if (body.weight !== undefined) {
    channel.weight = boundedNumber(body.weight, 0, 100, "Weight must be between 0 and 100.");
  }

  if (body.priority !== undefined) {
    channel.priority = boundedNumber(body.priority, 1, 99, "Priority must be between 1 and 99.");
  }

  if (body.cost_price !== undefined) {
    channel.costPrice = boundedNumber(body.cost_price, 0, 999999, "Cost price cannot be negative.");
  }

  if (body.sale_price !== undefined) {
    channel.salePrice = boundedNumber(body.sale_price, 0, 999999, "Sale price cannot be negative.");
  }

  channel.updatedAt = new Date().toISOString();
}

function buildModelCategoryUpsert(body, existing = null) {
  const id = existing?.id ?? normalizeId(body.id, "cat");
  const key = String(body.key ?? existing?.key ?? "").trim();
  if (!/^[a-z][a-z0-9_-]{1,63}$/.test(key)) {
    throw problem(422, "VALIDATION_ERROR", "Category key must be stable lowercase letters, numbers, underscores, or hyphens.");
  }

  const name = String(body.name ?? existing?.name ?? "").trim();
  if (!name) {
    throw problem(422, "VALIDATION_ERROR", "Category display name is required.");
  }

  const status = String(body.status ?? existing?.status ?? "published").trim();
  if (!allowedModelCategoryStatuses.has(status)) {
    throw problem(422, "VALIDATION_ERROR", "Invalid category status.");
  }

  const parentId = body.parent_id ?? body.parentId ?? existing?.parentId ?? null;
  if (parentId && !catalogRepository.getModelCategory(parentId)) {
    throw problem(422, "VALIDATION_ERROR", "Parent category does not exist.");
  }

  return {
    id,
    key,
    name,
    icon: body.icon === undefined ? existing?.icon ?? null : String(body.icon ?? "").trim() || null,
    sortOrder: boundedNumber(body.sort_order ?? body.sortOrder ?? existing?.sortOrder ?? 0, 0, 999999, "Sort order cannot be negative."),
    visible: body.visible === undefined ? existing?.visible ?? true : Boolean(body.visible),
    parentId,
    status,
    aliases: normalizeStringList(body.aliases, existing?.aliases ?? []),
  };
}

function buildProviderUpsert(body, existing = null) {
  const id = existing?.id ?? normalizeId(body.id, "prv");
  const name = String(body.name ?? existing?.name ?? "").trim();
  if (!name) {
    throw problem(422, "VALIDATION_ERROR", "Provider name is required.");
  }

  const kind = String(body.kind ?? existing?.kind ?? "relay").trim();
  if (!allowedProviderKinds.has(kind)) {
    throw problem(422, "VALIDATION_ERROR", "Invalid provider kind.");
  }

  const baseUrl = String(body.base_url ?? body.baseUrl ?? existing?.baseUrl ?? "").trim();
  if (!baseUrl) {
    throw problem(422, "VALIDATION_ERROR", "Provider base URL is required.");
  }

  const authType = String(body.auth_type ?? body.authType ?? existing?.authType ?? "bearer").trim();
  if (!allowedProviderAuthTypes.has(authType)) {
    throw problem(422, "VALIDATION_ERROR", "Invalid provider auth type.");
  }

  const status = String(body.status ?? existing?.status ?? "testing").trim();
  if (!allowedProviderStatuses.has(status)) {
    throw problem(422, "VALIDATION_ERROR", "Invalid provider status.");
  }

  const encryptedApiKey =
    body.encrypted_api_key !== undefined || body.encryptedApiKey !== undefined
      ? encryptSecret(String(body.encrypted_api_key ?? body.encryptedApiKey ?? "").trim() || null)
      : existing?.encryptedApiKey;

  return {
    id,
    name,
    kind,
    baseUrl,
    authType,
    encryptedApiKey,
    status,
    rpm: boundedNumber(body.rpm ?? existing?.rpm ?? 0, 0, 999999, "RPM cannot be negative."),
    concurrency: boundedNumber(body.concurrency ?? existing?.concurrency ?? 0, 0, 999999, "Concurrency cannot be negative."),
    latencyMs: boundedNumber(
      body.latency_ms ?? body.latencyMs ?? existing?.latencyMs ?? 0,
      0,
      999999,
      "Latency cannot be negative."
    ),
    successRate: boundedNumber(
      body.success_rate ?? body.successRate ?? existing?.successRate ?? 95,
      0,
      100,
      "Success rate must be between 0 and 100."
    ),
  };
}

function buildProviderKeyUpsert(body, existing = null) {
  const id = existing?.id ?? normalizeId(body.id, "pkey");
  const providerId = String(body.provider_id ?? body.providerId ?? existing?.providerId ?? "").trim();
  const provider = catalogRepository.getProvider(providerId);
  if (!provider) {
    throw problem(422, "VALIDATION_ERROR", "Provider does not exist.");
  }

  const name = String(body.name ?? existing?.name ?? "").trim();
  if (!name) {
    throw problem(422, "VALIDATION_ERROR", "Provider key name is required.");
  }

  const status = String(body.status ?? existing?.status ?? "active").trim();
  if (!["active", "degraded", "disabled"].includes(status)) {
    throw problem(422, "VALIDATION_ERROR", "Invalid provider key status.");
  }

  const encryptedApiKey =
    body.encrypted_api_key !== undefined || body.encryptedApiKey !== undefined
      ? String(body.encrypted_api_key ?? body.encryptedApiKey ?? "").trim() || null
      : existing?.encryptedApiKey;

  return {
    id,
    providerId,
    name,
    encryptedApiKey,
    status,
    rpm: optionalBoundedNumber(body.rpm ?? existing?.rpm, 0, 999999, "RPM cannot be negative."),
    tpm: optionalBoundedNumber(body.tpm ?? existing?.tpm, 0, 999999999, "TPM cannot be negative."),
    concurrency: boundedNumber(
      body.concurrency ?? existing?.concurrency ?? provider.concurrency ?? 1,
      0,
      999999,
      "Concurrency cannot be negative."
    ),
    priority: boundedNumber(body.priority ?? existing?.priority ?? 100, 1, 999999, "Priority must be greater than 0."),
    weight: boundedNumber(body.weight ?? existing?.weight ?? 50, 0, 100, "Weight must be between 0 and 100."),
    supportedProviderModelIds: normalizeStringList(
      body.supported_provider_model_ids ?? body.supportedProviderModelIds,
      existing?.supportedProviderModelIds ?? []
    ),
    notes: body.notes !== undefined ? String(body.notes ?? "").trim() || null : existing?.notes ?? null,
  };
}

function buildPaymentProviderUpsert(body, existing = null) {
  const id = existing?.id ?? normalizeId(body.id, "payprov");
  const name = String(body.name ?? existing?.name ?? "").trim();
  if (!name) {
    throw problem(422, "VALIDATION_ERROR", "Payment provider name is required.");
  }

  const kind = String(body.kind ?? existing?.kind ?? "custom").trim();
  if (!allowedPaymentProviderKinds.has(kind)) {
    throw problem(422, "VALIDATION_ERROR", "Invalid payment provider kind.");
  }

  const status = String(body.status ?? existing?.status ?? "testing").trim();
  if (!allowedPaymentProviderStatuses.has(status)) {
    throw problem(422, "VALIDATION_ERROR", "Invalid payment provider status.");
  }

  const checkoutMode = String(
    body.checkout_mode ?? body.checkoutMode ?? existing?.checkoutMode ?? defaultCheckoutMode(kind)
  ).trim();
  if (!allowedPaymentCheckoutModes.has(checkoutMode)) {
    throw problem(422, "VALIDATION_ERROR", "Invalid payment checkout mode.");
  }

  const currencies = normalizeStringList(body.currencies, existing?.currencies ?? ["CNY"]).map((currency) =>
    currency.toUpperCase()
  );
  if (currencies.length === 0) {
    throw problem(422, "VALIDATION_ERROR", "Payment provider must support at least one currency.");
  }

  const minAmount = boundedNumber(
    body.min_amount ?? body.minAmount ?? existing?.minAmount ?? 0.01,
    0.01,
    999999,
    "Payment provider minimum amount must be greater than 0."
  );
  const maxAmount = boundedNumber(
    body.max_amount ?? body.maxAmount ?? existing?.maxAmount ?? 999999,
    minAmount,
    999999,
    "Payment provider maximum amount must be greater than or equal to minimum amount."
  );

  const webhookSecret =
    body.webhook_secret !== undefined || body.webhookSecret !== undefined
      ? String(body.webhook_secret ?? body.webhookSecret ?? "").trim() || null
      : existing?.webhookSecret;
  const now = new Date().toISOString();

  return {
    id,
    name,
    kind,
    status,
    currencies,
    feeRate: boundedNumber(
      body.fee_rate ?? body.feeRate ?? existing?.feeRate ?? 0,
      0,
      1,
      "Payment provider fee rate must be between 0 and 1."
    ),
    fixedFee: boundedNumber(
      body.fixed_fee ?? body.fixedFee ?? existing?.fixedFee ?? 0,
      0,
      999999,
      "Payment provider fixed fee cannot be negative."
    ),
    minAmount,
    maxAmount,
    checkoutMode,
    webhookSecret,
    sortOrder: boundedNumber(
      body.sort_order ?? body.sortOrder ?? existing?.sortOrder ?? 50,
      0,
      999999,
      "Payment provider sort order cannot be negative."
    ),
    metadata: normalizeObject(body.metadata ?? existing?.metadata, {}),
    createdAt: existing?.createdAt ?? now,
    updatedAt: now,
  };
}

function defaultCheckoutMode(kind) {
  if (kind === "mock") {
    return "mock";
  }
  if (kind === "manual") {
    return "manual";
  }
  if (kind === "alipay" || kind === "wechat") {
    return "qr_code";
  }
  if (kind === "stripe") {
    return "hosted";
  }
  return "redirect";
}

function buildProviderModelUpsert(body, existing = null) {
  const id = existing?.id ?? normalizeId(body.id, "pm");
  const providerId = String(body.provider_id ?? body.providerId ?? existing?.providerId ?? "").trim();
  const provider = catalogRepository.getProvider(providerId);
  if (!provider) {
    throw problem(422, "VALIDATION_ERROR", "Provider does not exist.");
  }

  const upstreamModelName = String(body.upstream_model_name ?? body.upstreamModelName ?? existing?.upstreamModelName ?? "").trim();
  if (!upstreamModelName) {
    throw problem(422, "VALIDATION_ERROR", "Upstream model name is required.");
  }

  const modality = String(body.modality ?? existing?.modality ?? "").trim();
  if (!allowedModalities.has(modality)) {
    throw problem(422, "VALIDATION_ERROR", "Invalid provider model modality.");
  }

  const status = String(body.status ?? existing?.status ?? "testing").trim();
  if (!allowedProviderModelStatuses.has(status)) {
    throw problem(422, "VALIDATION_ERROR", "Invalid provider model status.");
  }

  return {
    id,
    providerId,
    upstreamModelName,
    endpointType: String(body.endpoint_type ?? body.endpointType ?? existing?.endpointType ?? defaultEndpointType(modality)).trim(),
    modality,
    status,
    rawCapabilities: normalizeObject(body.raw_capabilities ?? body.rawCapabilities ?? existing?.rawCapabilities, {}),
    notes: body.notes === undefined ? existing?.notes ?? null : String(body.notes ?? "").trim() || null,
  };
}

function buildPlatformModelUpsert(body, existing = null) {
  const id = existing?.id ?? normalizeModelId(body.id, "model");
  const name = String(body.name ?? existing?.name ?? "").trim();
  if (!name) {
    throw problem(422, "VALIDATION_ERROR", "Platform model name is required.");
  }

  const shortName = String(body.short_name ?? body.shortName ?? existing?.shortName ?? name).trim();
  if (!shortName) {
    throw problem(422, "VALIDATION_ERROR", "Platform model short name is required.");
  }

  const modality = String(body.modality ?? existing?.modality ?? "").trim();
  if (!allowedModalities.has(modality)) {
    throw problem(422, "VALIDATION_ERROR", "Invalid platform model modality.");
  }

  const tier = String(body.tier ?? existing?.tier ?? "standard").trim();
  if (!allowedPlatformTiers.has(tier)) {
    throw problem(422, "VALIDATION_ERROR", "Invalid platform model tier.");
  }

  const description = String(body.description ?? existing?.description ?? "").trim();
  if (!description) {
    throw problem(422, "VALIDATION_ERROR", "Platform model description is required.");
  }

  const rawSchema = body.schema ?? existing?.schema ?? defaultSchemaForModality(modality);
  const schema = normalizeSchemaFields(rawSchema);
  if (schema.length === 0) {
    throw problem(422, "VALIDATION_ERROR", "Platform model needs at least one schema field.");
  }

  return {
    id,
    slug: normalizeSlug(body.slug ?? existing?.slug ?? id),
    displayName: String(body.display_name ?? body.displayName ?? body.name ?? existing?.displayName ?? existing?.name ?? name).trim(),
    name,
    shortName,
    modality,
    tier,
    description,
    useCases: normalizeStringList(body.use_cases ?? body.useCases, existing?.useCases ?? []),
    visible: body.visible === undefined ? existing?.visible ?? true : Boolean(body.visible),
    recommended: body.recommended === undefined ? existing?.recommended ?? false : Boolean(body.recommended),
    estimatedCost: body.estimated_cost ?? body.estimatedCost ?? existing?.estimatedCost ?? "",
    estimatedTime: body.estimated_time ?? body.estimatedTime ?? existing?.estimatedTime ?? "",
    sortOrder: boundedNumber(body.sort_order ?? body.sortOrder ?? existing?.sortOrder ?? 0, 0, 999999, "Sort order cannot be negative."),
    schema,
  };
}

function buildBillingPlanUpsert(body, existing = null) {
  const id = existing?.id ?? normalizeId(body.id, "plan");
  const name = String(body.name ?? existing?.name ?? "").trim();
  if (!name) {
    throw problem(422, "VALIDATION_ERROR", "Billing plan name is required.");
  }

  const status = String(body.status ?? existing?.status ?? "active").trim();
  if (!allowedBillingPlanStatuses.has(status)) {
    throw problem(422, "VALIDATION_ERROR", "Invalid billing plan status.");
  }

  return {
    id,
    name,
    monthlyTaskLimit: boundedNumber(
      body.monthly_task_limit ?? body.monthlyTaskLimit ?? existing?.monthlyTaskLimit ?? 0,
      0,
      999999999,
      "Monthly task limit cannot be negative."
    ),
    monthlySpendLimit: boundedNumber(
      body.monthly_spend_limit ?? body.monthlySpendLimit ?? existing?.monthlySpendLimit ?? 0,
      0,
      999999999,
      "Monthly spend limit cannot be negative."
    ),
    rateLimitPerMinute: boundedNumber(
      body.rate_limit_per_minute ?? body.rateLimitPerMinute ?? existing?.rateLimitPerMinute ?? 60,
      1,
      999999,
      "Rate limit per minute must be greater than 0."
    ),
    concurrencyLimit: boundedNumber(
      body.concurrency_limit ?? body.concurrencyLimit ?? existing?.concurrencyLimit ?? 1,
      1,
      999999,
      "Concurrency limit must be greater than 0."
    ),
    features: normalizeStringList(body.features, existing?.features ?? []),
    status,
  };
}

function buildUserSubscriptionUpsert(body, existing = null) {
  const id = existing?.id ?? normalizeId(body.id, "sub");
  const userId = String(body.user_id ?? body.userId ?? existing?.userId ?? "").trim();
  if (!userId) {
    throw problem(422, "VALIDATION_ERROR", "User ID is required.");
  }

  const planId = String(body.plan_id ?? body.planId ?? existing?.planId ?? "").trim();
  const plan = usageRepository.getBillingPlan(planId);
  if (!plan) {
    throw problem(422, "VALIDATION_ERROR", "Billing plan does not exist.");
  }

  const status = String(body.status ?? existing?.status ?? "active").trim();
  if (!allowedSubscriptionStatuses.has(status)) {
    throw problem(422, "VALIDATION_ERROR", "Invalid subscription status.");
  }

  return {
    id,
    userId,
    planId,
    status,
    renewsAt: normalizeOptionalDate(body.renews_at ?? body.renewsAt ?? existing?.renewsAt),
    cancelledAt: normalizeOptionalDate(body.cancelled_at ?? body.cancelledAt ?? existing?.cancelledAt),
  };
}

const capabilityFieldAliases = {
  prompt: ["input", "input_prompt", "text", "description"],
  aspect_ratio: ["aspectRatio", "ratio", "size", "image_size"],
  quality: ["quality", "steps", "mode"],
  reference_image: ["referenceImage", "image", "input_image", "init_image"],
  negative_prompt: ["negativePrompt", "negative", "negative_prompt"],
  duration: ["seconds", "duration_seconds", "length"],
  resolution: ["quality", "resolution", "size"],
  first_frame: ["firstFrame", "image", "start_image"],
  motion: ["motion_strength", "motionStrength", "motion"],
  message: ["messages", "message", "input"],
  tone: ["system", "tone", "style"],
  stream: ["stream", "streaming"],
};

function supportedFieldKeysForProviderModel(schema, providerModel) {
  return (schema ?? [])
    .map((field) => field.key)
    .filter((fieldKey) => suggestedUpstreamParamForField(fieldKey, providerModel));
}

function suggestedUpstreamParamForField(fieldKey, providerModel) {
  const capabilities = providerModel?.rawCapabilities ?? {};
  const explicitMap = capabilityParamMap(capabilities);
  const mapped = explicitMap[fieldKey];
  if (mapped) {
    return mapped;
  }

  const paramKeys = capabilityParamKeys(capabilities);
  if (paramKeys.length === 0) {
    return fieldKey;
  }

  return matchCapabilityKey(paramKeys, [fieldKey, ...(capabilityFieldAliases[fieldKey] ?? [])]);
}

function capabilityParamKeys(capabilities) {
  const keys = new Set();
  const topLevelCandidates = [
    capabilities.supports,
    capabilities.supported_params,
    capabilities.supportedParameters,
    capabilities.parameters,
    capabilities.input_parameters,
    capabilities.inputParameters,
  ];

  for (const candidate of topLevelCandidates) {
    collectCapabilityKeys(candidate, keys);
  }

  collectCapabilityKeys(readNestedCapability(capabilities, ["input_schema", "properties"]), keys);
  collectCapabilityKeys(readNestedCapability(capabilities, ["inputSchema", "properties"]), keys);
  collectCapabilityKeys(readNestedCapability(capabilities, ["schema", "properties"]), keys);

  return Array.from(keys);
}

function collectCapabilityKeys(value, keys) {
  if (Array.isArray(value)) {
    for (const item of value) {
      if (typeof item === "string") {
        keys.add(item);
        continue;
      }

      if (item && typeof item === "object") {
        const key = item.key ?? item.name ?? item.id ?? item.param ?? item.field;
        if (typeof key === "string") {
          keys.add(key);
        }
      }
    }
    return;
  }

  if (value && typeof value === "object") {
    Object.keys(value).forEach((key) => keys.add(key));
  }
}

function capabilityParamMap(capabilities) {
  const rawMap =
    capabilities.parameter_mappings ??
    capabilities.parameterMappings ??
    capabilities.mappings ??
    capabilities.platform_to_upstream ??
    capabilities.platformToUpstream;

  if (!rawMap || typeof rawMap !== "object" || Array.isArray(rawMap)) {
    return {};
  }

  return Object.fromEntries(
    Object.entries(rawMap)
      .map(([key, value]) => [key, typeof value === "string" ? value : readCapabilityMappingTarget(value)])
      .filter((entry) => Boolean(entry[1])),
  );
}

function readCapabilityMappingTarget(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }

  const target = value.upstream ?? value.upstream_param_key ?? value.upstreamParamKey ?? value.name ?? value.key;
  return typeof target === "string" ? target : null;
}

function readNestedCapability(source, path) {
  let current = source;
  for (const key of path) {
    if (!current || typeof current !== "object" || Array.isArray(current)) {
      return undefined;
    }
    current = current[key];
  }
  return current;
}

function matchCapabilityKey(keys, candidates) {
  const keyByLowercase = new Map(keys.map((key) => [key.toLowerCase(), key]));
  for (const candidate of candidates) {
    const match = keyByLowercase.get(candidate.toLowerCase());
    if (match) {
      return match;
    }
  }
  return null;
}

function buildChannelCreate(body) {
  const platformModel = catalogRepository.getPlatformModel(body.platform_model_id);
  if (!platformModel) {
    throw problem(422, "VALIDATION_ERROR", "Platform model does not exist.");
  }

  const provider = catalogRepository.getProvider(body.provider_id);
  if (!provider) {
    throw problem(422, "VALIDATION_ERROR", "Provider does not exist.");
  }

  const providerModel = catalogRepository.getProviderModel(body.provider_model_id);
  if (!providerModel || providerModel.providerId !== provider.id) {
    throw problem(422, "VALIDATION_ERROR", "Provider model does not belong to the selected provider.");
  }

  if (providerModel.modality !== platformModel.modality) {
    throw problem(422, "VALIDATION_ERROR", "Provider model modality does not match platform model.");
  }

  const role = body.role ?? "backup";
  const status = body.status ?? "disabled";
  if (!allowedChannelRoles.has(role)) {
    throw problem(422, "VALIDATION_ERROR", "Invalid channel role.");
  }
  if (!allowedChannelStatuses.has(status)) {
    throw problem(422, "VALIDATION_ERROR", "Invalid channel status.");
  }

  const inferredSupports = supportedFieldKeysForProviderModel(platformModel.schema ?? [], providerModel);
  const supports = body.supports === undefined ? normalizeStringList(inferredSupports, []) : normalizeStringList(body.supports, []);

  return {
    id: body.id ?? createId("ch"),
    platformModelId: platformModel.id,
    providerId: provider.id,
    providerModelId: providerModel.id,
    role,
    status,
    weight: boundedNumber(body.weight ?? 30, 0, 100, "Weight must be between 0 and 100."),
    priority: boundedNumber(body.priority ?? 10, 1, 99, "Priority must be between 1 and 99."),
    costPrice: boundedNumber(body.cost_price ?? 0, 0, 999999, "Cost price cannot be negative."),
    salePrice: boundedNumber(body.sale_price ?? 0, 0, 999999, "Sale price cannot be negative."),
    billingUnit: String(body.billing_unit ?? "request").trim() || "request",
    latency: boundedNumber(body.latency ?? 10, 0, 999999, "Latency cannot be negative."),
    successRate: boundedNumber(body.success_rate ?? 95, 0, 100, "Success rate must be between 0 and 100."),
    maxConcurrency: optionalBoundedNumber(body.max_concurrency, 0, 999999, "Max concurrency cannot be negative."),
    timeoutMs: optionalBoundedNumber(body.timeout_ms, 1, 3600000, "Timeout must be between 1 and 3600000ms."),
    supports,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };
}

function buildPlatformModelCategoryAssignment(model, body) {
  const rawCategory = String(body.category_id ?? body.categoryId ?? body.category_key ?? body.categoryKey ?? "").trim();
  const category = catalogRepository.getModelCategory(rawCategory);
  if (!category) {
    throw problem(422, "VALIDATION_ERROR", "Category does not exist.");
  }

  return {
    id: String(body.id ?? `assign_${stableIdPart(model.id)}_${stableIdPart(category.key)}`).slice(0, 96),
    platformModelId: model.id,
    categoryId: category.id,
    sortOrder: boundedNumber(body.sort_order ?? body.sortOrder ?? model.sortOrder ?? 0, 0, 999999, "Sort order cannot be negative."),
    isPrimary: body.is_primary === undefined && body.isPrimary === undefined ? true : Boolean(body.is_primary ?? body.isPrimary),
  };
}

function buildPlatformModelAlias(model, body) {
  const alias = String(body.alias ?? body.name ?? "").trim();
  if (!alias) {
    throw problem(422, "VALIDATION_ERROR", "Alias is required.");
  }

  const kind = String(body.kind ?? "search").trim();
  if (!["search", "legacy", "marketing", "upstream"].includes(kind)) {
    throw problem(422, "VALIDATION_ERROR", "Invalid alias kind.");
  }

  return {
    id: String(body.id ?? `alias_${stableIdPart(model.id)}_${stableIdPart(alias)}`).slice(0, 96),
    platformModelId: model.id,
    alias,
    kind,
  };
}

function defaultEndpointType(modality) {
  const endpointTypes = {
    image: "image_generation",
    video: "video_generation",
    chat: "chat_completions",
    audio: "audio_generation",
    workflow: "workflow_run",
  };
  return endpointTypes[modality] ?? "generate";
}

function normalizeId(value, prefix) {
  const raw = String(value ?? "").trim() || createId(prefix);
  if (!/^[a-zA-Z][a-zA-Z0-9_-]{1,63}$/.test(raw)) {
    throw problem(422, "VALIDATION_ERROR", "ID must start with a letter and use letters, numbers, underscores, or hyphens.");
  }
  return raw;
}

function normalizeModelId(value, prefix) {
  const raw = String(value ?? "").trim() || createId(prefix);
  if (!/^[a-zA-Z][a-zA-Z0-9_.-]{1,127}$/.test(raw)) {
    throw problem(422, "VALIDATION_ERROR", "Model ID must start with a letter and use letters, numbers, dots, underscores, or hyphens.");
  }
  return raw;
}

function normalizeSlug(value) {
  const raw = String(value ?? "").trim().toLowerCase();
  if (!/^[a-z][a-z0-9_.-]{1,127}$/.test(raw)) {
    throw problem(422, "VALIDATION_ERROR", "Slug must start with a lowercase letter and use lowercase letters, numbers, dots, underscores, or hyphens.");
  }
  return raw;
}

function slugify(value) {
  return String(value ?? "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || "model";
}

function stableIdPart(value) {
  return String(value ?? "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "") || Math.random().toString(16).slice(2, 8);
}

function buildPlatformSchemaField(body) {
  const key = String(body.key ?? body.field_key ?? "").trim();
  if (!/^[a-zA-Z][a-zA-Z0-9_]{0,63}$/.test(key)) {
    throw problem(422, "VALIDATION_ERROR", "Schema field key must start with a letter and use letters, numbers, or underscores.");
  }

  const label = String(body.label ?? key).trim();
  if (!label) {
    throw problem(422, "VALIDATION_ERROR", "Schema field label is required.");
  }

  const type = String(body.type ?? "text").trim();
  if (!allowedSchemaFieldTypes.has(type)) {
    throw problem(422, "VALIDATION_ERROR", "Invalid schema field type.");
  }

  const defaultValue = body.default_value ?? body.defaultValue ?? body.value;
  const field = {
    key,
    label,
    type,
    required: Boolean(body.required),
    advanced: Boolean(body.advanced),
  };

  if (body.placeholder !== undefined && body.placeholder !== null) {
    field.placeholder = String(body.placeholder);
  }

  if (type === "select" || type === "segmented") {
    const options = normalizeSchemaOptions(body.options);
    if (options.length === 0) {
      throw problem(422, "VALIDATION_ERROR", "Select and segmented fields require at least one option.");
    }
    field.options = options;
    field.defaultValue = defaultValue ?? options[0].value;
    field.value = field.defaultValue;
    return field;
  }

  if (type === "slider") {
    field.min = boundedNumber(body.min ?? 1, -999999, 999999, "Slider min must be a valid number.");
    field.max = boundedNumber(body.max ?? 10, -999999, 999999, "Slider max must be a valid number.");
    if (field.max < field.min) {
      throw problem(422, "VALIDATION_ERROR", "Slider max must be greater than or equal to min.");
    }
    field.step = boundedNumber(body.step ?? 1, 0.000001, 999999, "Slider step must be greater than 0.");
    field.defaultValue =
      defaultValue === undefined || defaultValue === null || defaultValue === ""
        ? field.min
        : boundedNumber(defaultValue, field.min, field.max, "Slider default value must be within range.");
    field.value = field.defaultValue;
    return field;
  }

  if (type === "switch") {
    field.defaultValue = Boolean(defaultValue ?? false);
    field.value = field.defaultValue;
    return field;
  }

  if ((type === "text" || type === "textarea") && defaultValue !== undefined && defaultValue !== null) {
    field.defaultValue = String(defaultValue);
    field.value = field.defaultValue;
  }

  return field;
}

function normalizeSchemaFields(value) {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.map((field) => buildPlatformSchemaField(field));
}

function defaultSchemaForModality(modality) {
  const promptField = {
    key: modality === "chat" ? "message" : modality === "audio" ? "script" : "prompt",
    label: modality === "chat" ? "Message" : modality === "audio" ? "Script" : "Prompt",
    type: "textarea",
    required: true,
  };

  if (modality === "image") {
    return [
      promptField,
      {
        key: "aspect_ratio",
        label: "Aspect ratio",
        type: "segmented",
        default_value: "1:1",
        options: ["1:1", "3:4", "4:3", "16:9"],
      },
    ];
  }

  if (modality === "video") {
    return [
      promptField,
      {
        key: "duration",
        label: "Duration",
        type: "segmented",
        default_value: "5",
        options: ["5", "8", "10"],
      },
    ];
  }

  return [promptField];
}

function buildChannelMappingUpsert(channel, body) {
  const platformKey = String(body.platform_param_key ?? body.platform ?? "").trim();
  if (!platformKey) {
    throw problem(422, "VALIDATION_ERROR", "Platform parameter key is required.");
  }

  const platformModel = catalogRepository.getPlatformModel(channel.platformModelId);
  const schemaKeys = new Set((platformModel?.schema ?? []).map((field) => field.key));
  if (schemaKeys.size > 0 && !schemaKeys.has(platformKey)) {
    throw problem(422, "VALIDATION_ERROR", "Platform parameter does not belong to this model schema.");
  }

  const transform = body.transform ?? "direct";
  if (!allowedMappingTransforms.has(transform)) {
    throw problem(422, "VALIDATION_ERROR", "Invalid parameter mapping transform.");
  }

  const upstreamRaw = body.upstream_param_key ?? body.upstream ?? platformKey;
  const upstream = transform === "omit" ? null : String(upstreamRaw ?? "").trim();
  if (transform !== "omit" && !upstream) {
    throw problem(422, "VALIDATION_ERROR", "Upstream parameter key is required unless transform is omit.");
  }

  return {
    id: body.id ?? createId("map"),
    channelId: channel.id,
    platform: platformKey,
    upstream,
    transform,
    valueMap: normalizeObject(body.value_map ?? body.valueMap, {}),
    defaultValue: body.default_value ?? body.defaultValue,
    note: body.note ? String(body.note) : null,
  };
}

function normalizeObject(value, fallback) {
  if (value === undefined || value === null || value === "") {
    return fallback;
  }

  if (typeof value === "string") {
    try {
      const parsed = JSON.parse(value);
      return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : fallback;
    } catch {
      throw problem(422, "VALIDATION_ERROR", "JSON object is invalid.");
    }
  }

  return typeof value === "object" && !Array.isArray(value) ? value : fallback;
}

function normalizeSchemaOptions(value) {
  const rawItems = Array.isArray(value)
    ? value
    : typeof value === "string"
      ? value.split(",").map((item) => item.trim())
      : [];

  const options = rawItems
    .map((item) => {
      if (typeof item === "string") {
        return { label: item, value: item };
      }

      if (item && typeof item === "object") {
        const optionValue = String(item.value ?? item.id ?? item.label ?? "").trim();
        const optionLabel = String(item.label ?? optionValue).trim();
        return optionValue ? { label: optionLabel || optionValue, value: optionValue } : null;
      }

      return null;
    })
    .filter(Boolean);

  const seen = new Set();
  return options.filter((option) => {
    if (seen.has(option.value)) {
      return false;
    }
    seen.add(option.value);
    return true;
  });
}

function normalizeStringList(value, fallback) {
  if (Array.isArray(value)) {
    return [...new Set(value.map((item) => String(item).trim()).filter(Boolean))];
  }

  if (typeof value === "string") {
    return [...new Set(value.split(",").map((item) => item.trim()).filter(Boolean))];
  }

  return [...new Set(fallback)];
}

function optionalBoundedNumber(value, min, max, message) {
  if (value === undefined || value === null || value === "") {
    return null;
  }

  return boundedNumber(value, min, max, message);
}

function normalizeOptionalDate(value) {
  if (value === undefined || value === null || value === "") {
    return null;
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    throw problem(422, "VALIDATION_ERROR", "Date value is invalid.");
  }
  return date.toISOString();
}

function normalizeOptionalEmail(value) {
  if (value === undefined || value === null || String(value).trim() === "") {
    return null;
  }

  const email = String(value).trim().toLowerCase();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    throw problem(422, "VALIDATION_ERROR", "Email address is invalid.");
  }
  return email;
}

function normalizeOptionalUrl(value) {
  if (value === undefined || value === null || String(value).trim() === "") {
    return null;
  }

  const url = String(value).trim();
  try {
    const parsed = new URL(url);
    if (!["http:", "https:"].includes(parsed.protocol)) {
      throw new Error("Unsupported protocol.");
    }
  } catch {
    throw problem(422, "VALIDATION_ERROR", "URL must be a valid HTTP or HTTPS URL.");
  }
  return url;
}

function readBillingPeriod(url) {
  const now = new Date();
  const defaultStart = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1));
  const defaultEnd = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + 1, 1));
  const start = normalizeOptionalDate(url.searchParams.get("period_start")) ?? defaultStart.toISOString();
  const end = normalizeOptionalDate(url.searchParams.get("period_end")) ?? defaultEnd.toISOString();

  if (new Date(start).getTime() >= new Date(end).getTime()) {
    throw problem(422, "VALIDATION_ERROR", "Billing period start must be before period end.");
  }

  return { start, end };
}

function isWithinPeriod(value, period) {
  if (!value) {
    return false;
  }
  const timestamp = new Date(value).getTime();
  return timestamp >= new Date(period.start).getTime() && timestamp < new Date(period.end).getTime();
}

function csvCell(value) {
  const text = value === null || value === undefined ? "" : String(value);
  if (/[",\n\r]/.test(text)) {
    return `"${text.replaceAll('"', '""')}"`;
  }
  return text;
}

function boundedNumber(value, min, max, message) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric < min || numeric > max) {
    throw problem(422, "VALIDATION_ERROR", message);
  }

  return numeric;
}

function createId(prefix) {
  return `${prefix}_${Math.random().toString(16).slice(2, 10)}`;
}

function sendJson(res, status, payload) {
  res.writeHead(status, {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Tikpan-Signature",
    "Access-Control-Allow-Methods": "GET, POST, PATCH, DELETE, OPTIONS",
    "Content-Type": "application/json; charset=utf-8",
  });

  if (status === 204) {
    res.end();
    return;
  }

  res.end(JSON.stringify(payload, null, 2));
}

function sendCsv(res, filename, csv) {
  res.writeHead(200, {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Tikpan-Signature",
    "Access-Control-Allow-Methods": "GET, POST, PATCH, DELETE, OPTIONS",
    "Content-Disposition": `attachment; filename="${filename}"`,
    "Content-Type": "text/csv; charset=utf-8",
  });
  res.end(csv);
}

function sendProblem(res, error) {
  const status = error.status ?? 500;
  const code = error.code ?? "INTERNAL_ERROR";
  sendJson(res, status, {
    type: `https://api.tikpan.local/errors/${code.toLowerCase()}`,
    title: code,
    status,
    detail: error.message ?? "Internal server error.",
    ...error.extra,
  });
}

function publicProblem(error) {
  const status = error.status ?? 500;
  const code = error.code ?? "INTERNAL_ERROR";
  return {
    type: `https://api.tikpan.local/errors/${code.toLowerCase()}`,
    title: code,
    status,
    detail: error.message ?? "Internal server error.",
    ...error.extra,
  };
}
