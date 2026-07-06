import { registerTaskOutputAssets } from "./assets/mediaAssets.mjs";
import { repositories } from "./repositories/index.mjs";
import { executeGenerationTask } from "./worker/taskWorker.mjs";

const {
  assetMetadata: assetMetadataRepository,
  billing: billingRepository,
  catalog: catalogRepository,
  media: mediaRepository,
  providerKeys: providerKeysRepository,
  tasks: tasksRepository,
  usage: usageRepository,
} = repositories;

const routeModeWeights = {
  balanced: { quality: 0.28, speed: 0.24, cost: 0.2, stable: 0.28 },
  quality: { quality: 0.46, speed: 0.14, cost: 0.1, stable: 0.3 },
  fast: { quality: 0.18, speed: 0.46, cost: 0.12, stable: 0.24 },
  cheap: { quality: 0.16, speed: 0.16, cost: 0.48, stable: 0.2 },
  stable: { quality: 0.18, speed: 0.14, cost: 0.1, stable: 0.58 },
};

const routingControlInputKeys = new Set(["simulate_failover"]);
const activeTaskStatuses = new Set(["queued", "running", "saving_media"]);
const terminalTaskStatuses = new Set(["completed", "failed", "cancelled", "expired"]);

export async function createTask({ userId = "demo_user", model, input = {}, routing = {}, batch = null, project = null }) {
  const platformModel = catalogRepository.getPlatformModel(model);
  if (!platformModel || !platformModel.visible) {
    throw problem(404, "MODEL_NOT_FOUND", "No visible platform model was found.");
  }

  validateInput(platformModel, input);

  const routeMode = routing.mode ?? "balanced";
  const decision = selectRoute(platformModel.id, input, routeMode);
  const taskId = createId("task");

  if (!decision.channel) {
    const task = {
      id: taskId,
      userId,
      platformModelId: platformModel.id,
      status: "failed",
      input,
      output: null,
      estimatedCost: 0,
      finalCost: 0,
      publicErrorCode: "NO_AVAILABLE_ROUTE",
      publicErrorMessage: noAvailableRouteMessage(decision),
      batchId: batch?.id ?? null,
      batchTitle: batch?.title ?? null,
      batchItemId: batch?.itemId ?? null,
      projectId: project?.id ?? null,
      projectName: project?.name ?? null,
      attempts: [],
      createdAt: new Date().toISOString(),
    };
    await tasksRepository.create(task);
    return formatTaskResponse(task, platformModel, decision);
  }

  const provider = catalogRepository.getProvider(decision.channel.providerId);
  const providerModel = catalogRepository.getProviderModel(decision.channel.providerModelId);
  const payload = mapPayload(decision.channel, providerModel, input);
  const preAuthAmount = estimateTaskCost(decision.channel, input);

  await assertPlanAllowanceAsync(userId, preAuthAmount);
  await preAuthorize(userId, taskId, preAuthAmount, `Pre-authorize ${platformModel.name}`);

  const task = {
    id: taskId,
    userId,
    platformModelId: platformModel.id,
    status: "queued",
    input,
    output: null,
    estimatedCost: preAuthAmount,
    finalCost: null,
    publicErrorCode: null,
    publicErrorMessage: null,
    batchId: batch?.id ?? null,
    batchTitle: batch?.title ?? null,
    batchItemId: batch?.itemId ?? null,
    projectId: project?.id ?? null,
    projectName: project?.name ?? null,
    routeMode,
    selectedChannelId: decision.channel.id,
    selectedProviderId: provider.id,
    selectedProviderModelId: providerModel.id,
    mappedPayload: payload,
    attempts: [
      {
        id: createId("attempt"),
        providerId: provider.id,
        providerModelId: providerModel.id,
        channelId: decision.channel.id,
        status: "queued",
        mappedPayload: payload,
        costPrice: decision.channel.costPrice,
        createdAt: new Date().toISOString(),
      },
    ],
    createdAt: new Date().toISOString(),
    queuedAt: new Date().toISOString(),
  };

  await tasksRepository.create(task);
  return formatTaskResponse(task, platformModel, decision);
}

export async function quoteTask({ userId = "demo_user", model, input = {}, routing = {} }) {
  const platformModel = catalogRepository.getPlatformModel(model);
  if (!platformModel || !platformModel.visible) {
    throw problem(404, "MODEL_NOT_FOUND", "No visible platform model was found.");
  }

  validateInput(platformModel, input);

  const routeMode = routing.mode ?? "balanced";
  const decision = selectRoute(platformModel.id, input, routeMode);
  const estimatedCost = decision.channel ? estimateTaskCost(decision.channel, input) : 0;
  const usage = await getUsageSummary(userId);
  const wallet = publicWallet(await billingRepository.getWallet(userId));
  const blockers = [];

  if (!decision.channel) {
    blockers.push({
      code: "NO_AVAILABLE_ROUTE",
      severity: "error",
      message: noAvailableRouteMessage(decision),
    });
  } else {
    blockers.push(...planAllowanceBlockers(usage, estimatedCost));
    if (wallet.available < estimatedCost) {
      blockers.push({
        code: "NO_BALANCE",
        severity: "error",
        message: "余额不足，请先充值后继续生成。",
        required_amount: estimatedCost,
        available_amount: wallet.available,
      });
    }
  }

  return {
    data: {
      model: platformModel.id,
      route_mode: routeMode,
      allowed: blockers.length === 0,
      blockers,
      estimated_cost: estimatedCost,
      estimated_time: platformModel.estimatedTime,
      guarantee: decision.channel ? "失败不扣费，成功后结算。" : "未扣费。",
      message:
        blockers.length === 0
          ? "当前余额和套餐余量可用，可以提交生成。"
          : "请先处理余额、套餐或输入项后再生成。",
      wallet,
      usage,
      route: publicQuoteRoute(decision),
    },
  };
}

export function selectRoute(platformModelId, input, mode = "balanced") {
  const platformModel = catalogRepository.getPlatformModel(platformModelId);
  const modelChannels = catalogRepository.listChannelsForModel(platformModelId);
  const rejected = [];
  const candidates = [];

  for (const channel of modelChannels) {
    const provider = catalogRepository.getProvider(channel.providerId);

    if (!provider || provider.status === "testing" || provider.status === "disabled") {
      rejected.push(reject(channel, provider, "供应商未启用或仍在测试。"));
      continue;
    }

    if (channel.status === "disabled") {
      rejected.push(reject(channel, provider, "渠道已停用。"));
      continue;
    }

    const unsupported = Object.entries(input)
      .filter(([key, value]) => isUserIntentInput(platformModel, key, value))
      .map(([key]) => key)
      .filter((key) => !routingControlInputKeys.has(key))
      .filter((key) => !channel.supports.includes(key))
      .filter((key) => {
        const mapping = catalogRepository.getChannelMappings(channel.id).find((item) => item.platform === key);
        return !mappingCanCarryUserValue(mapping);
      });

    if (unsupported.length > 0) {
      rejected.push(
        reject(channel, provider, `不支持参数：${unsupported.join("、")}`, {
          code: "UNSUPPORTED_PARAMETERS",
          parameters: unsupported,
        }),
      );
      continue;
    }

    candidates.push(channel);
  }

  const scored = candidates
    .map((channel) => scoreChannel(channel, mode))
    .sort((a, b) => b.score - a.score);

  return {
    channel: scored[0]?.channel ?? null,
    rankedChannels: scored.map((item) => item.channel),
    candidates,
    rejected,
    scoreBreakdown: scored.map((item) => ({
      channelId: item.channel.id,
      providerName: catalogRepository.getProvider(item.channel.providerId)?.name ?? "Unknown",
      score: Math.round(item.score * 10) / 10,
      reasons: item.reasons,
    })),
  };
}

export function mapPayload(channel, providerModel, input) {
  const payload = {
    model: providerModel.upstreamModelName,
  };

  for (const mapping of catalogRepository.getChannelMappings(channel.id)) {
    let value = input[mapping.platform];

    if (mapping.transform === "omit") {
      continue;
    }

    if (mapping.transform === "default") {
      if (hasValidUpstreamParam(mapping.upstream)) {
        payload[mapping.upstream] = mapping.defaultValue ?? "default";
      }
      continue;
    }

    if (value === undefined || value === "") {
      if (mapping.defaultValue === undefined) {
        continue;
      }
      value = mapping.defaultValue;
    }

    if (mapping.transform === "map") {
      if (hasValidUpstreamParam(mapping.upstream)) {
        payload[mapping.upstream] = mapping.valueMap?.[String(value)] ?? value;
      }
      continue;
    }

    if (mapping.transform === "template") {
      if (hasValidUpstreamParam(mapping.upstream)) {
        payload[mapping.upstream] = buildTemplate(mapping.platform, value);
      }
      continue;
    }

    if (hasValidUpstreamParam(mapping.upstream)) {
      payload[mapping.upstream] = value;
    }
  }

  return payload;
}

export async function advanceTask(taskId, status = "completed") {
  const task = await tasksRepository.findById(taskId);
  if (!task) {
    throw problem(404, "TASK_NOT_FOUND", "Task does not exist.");
  }

  if (status === "completed") {
    return completeTask(task);
  }

  if (status === "failed") {
    if (terminalTaskStatuses.has(task.status) && task.status !== "failed") {
      return task;
    }

    if (task.status === "failed") {
      return task;
    }

    task.status = "failed";
    task.progress = 100;
    task.currentStep = "Generation failed; frozen funds have been released.";
    task.finalCost = 0;
    task.publicErrorCode = "PROVIDER_FAILED";
    task.publicErrorMessage = "The service is busy. Frozen funds have been released.";
    task.finishedAt = new Date().toISOString();

    const activeAttempt = task.attempts[task.attempts.length - 1];
    if (activeAttempt && activeAttempt.status !== "failed") {
      activeAttempt.status = "failed";
      activeAttempt.finishedAt = task.finishedAt;
    }

    if (!task.releasedAt) {
      await releaseFrozen(task.userId, task.id, task.estimatedCost, "Task failed release");
      task.releasedAt = new Date().toISOString();
    }
    await tasksRepository.save(task);
    return task;
  }

  task.status = status;
  await tasksRepository.save(task);
  return task;
}

export async function cancelTask(taskId, reason = "Task cancelled by user.") {
  const task = await tasksRepository.findById(taskId);
  if (!task) {
    throw problem(404, "TASK_NOT_FOUND", "Task does not exist.");
  }

  if (terminalTaskStatuses.has(task.status)) {
    throw problem(409, "TASK_ALREADY_TERMINAL", "Only queued or running tasks can be cancelled.", {
      task_status: task.status,
    });
  }

  task.status = "cancelled";
  task.progress = 100;
  task.currentStep = "Task was cancelled; frozen funds have been released.";
  task.finalCost = 0;
  task.publicErrorCode = "TASK_CANCELLED";
  task.publicErrorMessage = reason;
  task.finishedAt = new Date().toISOString();
  task.workerId = null;
  task.lockedUntil = null;

  for (const attempt of task.attempts ?? []) {
    if (!["completed", "failed"].includes(attempt.status)) {
      attempt.status = "failed";
      attempt.errorCode = "TASK_CANCELLED";
      attempt.errorMessage = reason;
      attempt.finishedAt = task.finishedAt;
    }
  }

  if (!task.releasedAt) {
    await releaseFrozen(task.userId, task.id, task.estimatedCost, "Task cancelled release");
    task.releasedAt = new Date().toISOString();
  }

  await tasksRepository.save(task);
  return task;
}

export async function retryTask(taskId) {
  const task = await tasksRepository.findById(taskId);
  if (!task) {
    throw problem(404, "TASK_NOT_FOUND", "Task does not exist.");
  }

  if (!["failed", "cancelled", "expired"].includes(task.status)) {
    throw problem(409, "TASK_NOT_RETRYABLE", "Only failed, cancelled, or expired tasks can be retried.", {
      task_status: task.status,
    });
  }

  return createTask({
    userId: task.userId,
    model: task.platformModelId,
    input: { ...task.input },
    routing: { mode: task.routeMode ?? "balanced" },
    project: task.projectId ? { id: task.projectId, name: task.projectName ?? null } : null,
  });
}

export async function syncTaskProgress(task) {
  if (!task || terminalTaskStatuses.has(task.status)) {
    return task;
  }

  return task;
}

export async function processClaimedTask(task) {
  if (!task || terminalTaskStatuses.has(task.status)) {
    return task;
  }

  const elapsedMs = Date.now() - new Date(task.createdAt).getTime();

  if (task.status === "saving_media" || elapsedMs >= 4200) {
    task.status = "saving_media";
    task.progress = 86;
    task.currentStep = "Saving generated media to object storage.";
    task.attempts[0].status = "saving_media";
    await tasksRepository.save(task);
    return executeTaskWithFallback(task);
  }

  if (elapsedMs >= 1800) {
    task.status = "running";
    task.progress = 52;
    task.currentStep = "The upstream model is generating.";
    task.startedAt ??= new Date().toISOString();
    task.attempts[0].status = "running";
    await tasksRepository.save(task);
    return task;
  }

  task.status = "queued";
  task.progress = 18;
  task.currentStep = "Task has entered the queue.";
  await tasksRepository.save(task);
  return task;
}

export async function topUpWallet(userId = "demo_user", amount, note = "Balance top-up") {
  const value = normalizeAmount(amount);
  if (value <= 0) {
    throw problem(422, "VALIDATION_ERROR", "Top-up amount must be greater than 0.");
  }

  if (billingRepository.supportsAtomicOperations) {
    return billingRepository.topUp(userId, value, note, createId);
  }

  const wallet = billingRepository.getWallet(userId);
  wallet.balance = roundMoney(wallet.balance + value);
  wallet.updatedAt = new Date().toISOString();
  appendWalletLedger(wallet, {
    taskId: null,
    type: "top_up",
    amount: value,
    note,
  });
  return wallet;
}

export async function refundTask(taskId, amount, note = "Admin refund") {
  const task = await tasksRepository.findById(taskId);
  if (!task) {
    throw problem(404, "TASK_NOT_FOUND", "Task does not exist.");
  }

  if (task.status !== "completed" || !task.settledAt) {
    throw problem(409, "TASK_NOT_SETTLED", "Only settled completed tasks can be refunded.");
  }

  const existingRefund = (await billingRepository.listLedger(task.userId)).find(
    (item) => item.taskId === task.id && item.type === "refund",
  );
  if (existingRefund) {
    throw problem(409, "TASK_ALREADY_REFUNDED", "This task has already been refunded.", { ledger_id: existingRefund.id });
  }

  const value = normalizeAmount(amount ?? task.finalCost ?? task.estimatedCost ?? 0);
  if (value <= 0) {
    throw problem(422, "VALIDATION_ERROR", "Refund amount must be greater than zero.");
  }
  if (value > Number(task.finalCost ?? 0)) {
    throw problem(422, "VALIDATION_ERROR", "Refund amount cannot exceed the settled task amount.");
  }

  if (billingRepository.supportsAtomicOperations) {
    const wallet = await billingRepository.refundSettled(task.userId, task.id, value, note, createId);
    return { task, wallet, refund_amount: value };
  }

  const wallet = billingRepository.getWallet(task.userId);
  wallet.balance = roundMoney(wallet.balance + value);
  wallet.updatedAt = new Date().toISOString();
  appendWalletLedger(wallet, {
    taskId: task.id,
    type: "refund",
    amount: value,
    note,
  });
  return { task, wallet, refund_amount: value };
}

export function publicWallet(wallet) {
  return {
    user_id: wallet.userId,
    currency: wallet.currency,
    balance: wallet.balance,
    frozen: wallet.frozen,
    available: Math.max(0, roundMoney(Number(wallet.balance ?? 0) - Number(wallet.frozen ?? 0))),
    updated_at: wallet.updatedAt,
  };
}

export async function getUsageSummary(userId = "demo_user") {
  const subscription = await usageRepository.getUserSubscription(userId);
  const plan = await usageRepository.getBillingPlan(subscription.planId);
  const period = currentMonthRange();
  const userTasks = (await tasksRepository.listByUser(userId)).filter((task) => isInRange(task.createdAt, period));
  const completedTasks = userTasks.filter((task) => task.status === "completed");
  const activeTasks = userTasks.filter((task) => activeTaskStatuses.has(task.status));
  const settledAmount = userTasks.reduce((sum, task) => sum + Number(task.finalCost ?? 0), 0);
  const frozenAmount = activeTasks.reduce((sum, task) => sum + Number(task.estimatedCost ?? 0), 0);
  const projectedSpend = roundMoney(settledAmount + frozenAmount);

  return {
    user_id: userId,
    period_start: period.start.toISOString(),
    period_end: period.end.toISOString(),
    subscription: {
      plan_id: subscription.planId,
      plan_name: plan?.name ?? subscription.planId,
      status: subscription.status,
      renews_at: subscription.renewsAt,
    },
    limits: {
      monthly_tasks: plan?.monthlyTaskLimit ?? 0,
      monthly_spend: plan?.monthlySpendLimit ?? 0,
      rate_limit_per_minute: plan?.rateLimitPerMinute ?? 0,
      concurrency: plan?.concurrencyLimit ?? 0,
    },
    usage: {
      tasks_created: userTasks.length,
      tasks_completed: completedTasks.length,
      active_tasks: activeTasks.length,
      settled_amount: roundMoney(settledAmount),
      frozen_amount: roundMoney(frozenAmount),
      projected_spend: projectedSpend,
    },
    remaining: {
      tasks: Math.max(0, Number(plan?.monthlyTaskLimit ?? 0) - userTasks.length),
      spend: Math.max(0, roundMoney(Number(plan?.monthlySpendLimit ?? 0) - projectedSpend)),
      concurrency: Math.max(0, Number(plan?.concurrencyLimit ?? 0) - activeTasks.length),
    },
  };
}

async function executeTaskWithFallback(task) {
  if (task.executedAt) {
    return task;
  }

  task.executedAt = new Date().toISOString();
  const result = await executeGenerationTask({
    task,
    catalogRepository,
    providerKeysRepository,
    selectRoute,
    mapPayload,
    createId,
  });

  if (result.status === "failed") {
    task.publicErrorCode = "PROVIDER_FAILED";
    task.publicErrorMessage = result.publicErrorMessage;
    return advanceTask(task.id, "failed");
  }

  task.output = result.output;
  task.currentStep = result.currentStep;
  return completeTask(task);
}

async function completeTask(task) {
  if (terminalTaskStatuses.has(task.status) && task.status !== "completed") {
    return task;
  }

  if (task.status === "completed") {
    return task;
  }

  task.status = "completed";
  task.progress = 100;
  task.currentStep = task.currentStep ?? "Generation completed; result has been saved.";
  task.finalCost = task.estimatedCost;
  const activeAttempt = task.attempts?.[task.attempts.length - 1];
  if (activeAttempt && !terminalTaskStatuses.has(activeAttempt.status)) {
    activeAttempt.status = "completed";
    activeAttempt.finishedAt = new Date().toISOString();
  }
  task.output ??= {
    assets: [`r2://outputs/${task.id}.json`],
    publicUrls: [`https://cdn.example.com/outputs/${task.id}.json`],
  };
  task.output = await registerTaskOutputAssets({
    task,
    output: task.output,
    mediaRepository,
    createId,
  });
  await ensureDefaultAssetMetadata(task);
  task.finishedAt = new Date().toISOString();

  if (!task.settledAt) {
    await settleFrozen(task.userId, task.id, task.finalCost, "Task success settlement");
    task.settledAt = new Date().toISOString();
  }
  await tasksRepository.save(task);
  return task;
}

async function ensureDefaultAssetMetadata(task) {
  if (!assetMetadataRepository?.findByTask || !assetMetadataRepository?.upsert) {
    return null;
  }

  const existing = await assetMetadataRepository.findByTask(task.id, task.userId);
  if (existing) {
    return existing;
  }

  const prompt = summarizePrompt(task.input);
  const model = catalogRepository.getPlatformModel(task.platformModelId);
  const title = prompt || `${model?.shortName ?? model?.name ?? task.platformModelId} result`;
  const tags = [
    model?.modality,
    task.projectId ? "project" : null,
    task.routeMode ?? "balanced",
  ].filter(Boolean);
  const collections = [task.projectName, task.projectId].filter(Boolean).slice(0, 2);
  const now = new Date().toISOString();

  return assetMetadataRepository.upsert({
    taskId: task.id,
    userId: task.userId,
    title: String(title).slice(0, 100),
    note: task.projectName ? `Generated in project: ${task.projectName}` : "Generated from workspace.",
    favorite: false,
    reviewStatus: "candidate",
    tags,
    collections,
    createdAt: now,
    updatedAt: now,
  });
}

function summarizePrompt(input = {}) {
  const candidate = input.prompt ?? input.message ?? input.title ?? "";
  const text = String(candidate).replace(/\s+/g, " ").trim();
  return text.length > 96 ? `${text.slice(0, 93)}...` : text;
}

function validateInput(platformModel, input) {
  const schema = platformModel.schema ?? [];
  const schemaByKey = new Map(schema.map((field) => [field.key, field]));
  const errors = [];

  for (const key of Object.keys(input ?? {})) {
    if (!schemaByKey.has(key) && !routingControlInputKeys.has(key)) {
      errors.push({ field: key, message: "This parameter is not supported by the selected model.", code: "UNSUPPORTED_FIELD" });
    }
  }

  for (const field of schema) {
    const value = input?.[field.key];
    const isEmpty = value === undefined || value === null || value === "";

    if (field.required && isEmpty) {
      errors.push({ field: field.key, message: "This field is required.", code: "REQUIRED" });
      continue;
    }

    if (isEmpty) {
      continue;
    }

    if ((field.type === "textarea" || field.type === "text" || field.type === "file") && typeof value !== "string") {
      errors.push({ field: field.key, message: "Value must be a string.", code: "INVALID_TYPE" });
      continue;
    }

    if ((field.type === "select" || field.type === "segmented") && Array.isArray(field.options)) {
      const allowedValues = new Set(field.options.map((option) => String(optionValue(option))));
      if (!allowedValues.has(String(value))) {
        errors.push({ field: field.key, message: "Value must be one of the configured options.", code: "INVALID_OPTION" });
      }
      continue;
    }

    if (field.type === "slider") {
      const numeric = Number(value);
      const min = Number(field.min ?? Number.NEGATIVE_INFINITY);
      const max = Number(field.max ?? Number.POSITIVE_INFINITY);
      if (!Number.isFinite(numeric)) {
        errors.push({ field: field.key, message: "Value must be a number.", code: "INVALID_TYPE" });
      } else if (numeric < min || numeric > max) {
        errors.push({ field: field.key, message: `Value must be between ${min} and ${max}.`, code: "OUT_OF_RANGE" });
      }
      continue;
    }

    if (field.type === "switch" && typeof value !== "boolean") {
      errors.push({ field: field.key, message: "Value must be true or false.", code: "INVALID_TYPE" });
    }
  }

  if (errors.length > 0) {
    throw problem(422, "VALIDATION_ERROR", "The request input does not match the model schema.", { errors });
  }
}

function optionValue(option) {
  if (option && typeof option === "object" && "value" in option) {
    return option.value;
  }
  return option;
}

function scoreChannel(channel, mode) {
  const provider = catalogRepository.getProvider(channel.providerId);
  const weights = routeModeWeights[mode] ?? routeModeWeights.balanced;
  const qualityScore = channel.role === "quality" || channel.role === "primary" ? 95 : 84;
  const speedScore = Math.max(20, Math.min(100, 110 - channel.latency));
  const costScore = channel.salePrice > 0 ? Math.max(30, 100 - channel.costPrice * 80) : 70;
  const stableScore = channel.successRate;
  const degradedPenalty = channel.status === "degraded" || provider?.status === "degraded" ? 8 : 0;
  const score =
    qualityScore * weights.quality +
    speedScore * weights.speed +
    costScore * weights.cost +
    stableScore * weights.stable -
    degradedPenalty +
    channel.weight * 0.05;

  return {
    channel,
    score,
    reasons: [
      `成功率 ${channel.successRate}%`,
      `延迟 ${channel.latency}s`,
      `权重 ${channel.weight}`,
      provider?.status === "degraded" ? "供应商降级，已扣分" : "供应商可用",
    ],
  };
}

function formatTaskResponse(task, platformModel, decision) {
  return {
    data: {
      task_id: task.id,
      model: platformModel.id,
      status: task.status,
      batch_id: task.batchId ?? null,
      batch_title: task.batchTitle ?? null,
      batch_item_id: task.batchItemId ?? null,
      project_id: task.projectId ?? null,
      project_name: task.projectName ?? null,
      input: task.input ?? {},
      route_mode: task.routeMode ?? "balanced",
      estimated_cost: task.estimatedCost,
      estimated_time: platformModel.estimatedTime,
      guarantee: task.status === "failed" ? "未扣费。" : "失败不扣费，成功后结算。",
      message:
        task.status === "failed"
          ? task.publicErrorMessage
          : "系统已完成智能调度，生成失败时会自动尝试可用备用能力。",
      progress: task.progress ?? (task.status === "completed" ? 100 : 0),
      current_step: task.currentStep ?? null,
      output: task.output ?? null,
      error: task.publicErrorCode
        ? {
            code: task.publicErrorCode,
            message: task.publicErrorMessage,
          }
        : null,
    },
  };
}

function formatAttempts(task) {
  return (task.attempts ?? []).map((attempt) => {
    const provider = catalogRepository.getProvider(attempt.providerId);
    const providerModel = catalogRepository.getProviderModel(attempt.providerModelId);
    return {
      id: attempt.id,
      provider: provider?.name ?? "Unknown",
      provider_model: providerModel?.upstreamModelName ?? "unknown",
      channel_id: attempt.channelId,
      status: attempt.status,
      error_code: attempt.errorCode ?? null,
      error_message: attempt.errorMessage ?? null,
      fallback_reason: attempt.fallbackReason ?? null,
      created_at: attempt.createdAt,
      finished_at: attempt.finishedAt ?? null,
    };
  });
}

function quoteRoute(decision, input) {
  const channel = decision.channel;
  const provider = channel ? catalogRepository.getProvider(channel.providerId) : null;
  const providerModel = channel ? catalogRepository.getProviderModel(channel.providerModelId) : null;

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
    mapped_payload: channel && providerModel ? mapPayload(channel, providerModel, input) : null,
    score_breakdown: decision.scoreBreakdown,
    rejected: decision.rejected,
  };
}

function publicQuoteRoute(decision) {
  return {
    channel: null,
    provider: null,
    provider_model: null,
    mapped_payload: null,
    score_breakdown: [],
    rejected: decision.rejected.map((item) => ({
      channelId: "",
      providerName: "",
      reason: item.reason,
      code: item.code,
      parameters: item.parameters,
    })),
  };
}

function buildTemplate(key, value) {
  if (key === "message") {
    return [{ role: "user", content: value }];
  }

  if (key === "tone") {
    return `Please answer in a ${value} style.`;
  }

  return value;
}

async function preAuthorize(userId, taskId, amount, note) {
  const value = normalizeAmount(amount);

  if (billingRepository.supportsAtomicOperations) {
    try {
      await billingRepository.preAuthorize(userId, taskId, value, note, createId);
      return;
    } catch (error) {
      if (error.code === "NO_BALANCE") {
        throw problem(402, "NO_BALANCE", error.message, {
          wallet: publicWallet(error.wallet),
          required_amount: error.requiredAmount,
        });
      }
      throw error;
    }
  }

  const wallet = billingRepository.getWallet(userId);

  if (wallet.balance < value) {
    throw problem(402, "NO_BALANCE", "Insufficient balance. Please top up first.", {
      wallet: publicWallet(wallet),
      required_amount: value,
    });
  }

  wallet.balance = roundMoney(wallet.balance - value);
  wallet.frozen = roundMoney(wallet.frozen + value);
  wallet.updatedAt = new Date().toISOString();
  appendWalletLedger(wallet, {
    taskId,
    type: "pre_authorize",
    amount: value,
    note,
  });
}

async function settleFrozen(userId, taskId, amount, note) {
  const value = normalizeAmount(amount);

  if (billingRepository.supportsAtomicOperations) {
    await billingRepository.settleFrozen(userId, taskId, value, note, createId);
    return;
  }

  const wallet = billingRepository.getWallet(userId);
  wallet.frozen = roundMoney(Math.max(0, wallet.frozen - value));
  wallet.updatedAt = new Date().toISOString();
  appendWalletLedger(wallet, {
    taskId,
    type: "settle",
    amount: value,
    note,
  });
}

async function releaseFrozen(userId, taskId, amount, note) {
  const value = normalizeAmount(amount);

  if (billingRepository.supportsAtomicOperations) {
    await billingRepository.releaseFrozen(userId, taskId, value, note, createId);
    return;
  }

  const wallet = billingRepository.getWallet(userId);
  wallet.frozen = roundMoney(Math.max(0, wallet.frozen - value));
  wallet.balance = roundMoney(wallet.balance + value);
  wallet.updatedAt = new Date().toISOString();
  appendWalletLedger(wallet, {
    taskId,
    type: "release",
    amount: value,
    note,
  });
}

function appendWalletLedger(wallet, { taskId, type, amount, note }) {
  billingRepository.appendLedger({
    id: createId("ledger"),
    userId: wallet.userId,
    taskId,
    type,
    amount: roundMoney(amount),
    balanceAfter: wallet.balance,
    frozenAfter: wallet.frozen,
    note,
    createdAt: new Date().toISOString(),
  });
}

async function assertPlanAllowanceAsync(userId, nextAmount) {
  const summary = await getUsageSummary(userId);

  for (const blocker of planAllowanceBlockers(summary, nextAmount)) {
    const status = blocker.code === "SUBSCRIPTION_INACTIVE" ? 403 : blocker.code === "MONTHLY_SPEND_LIMIT_EXCEEDED" ? 402 : 429;
    throw problem(status, blocker.code, blocker.message, { usage: summary });
  }
}

function planAllowanceBlockers(summary, nextAmount) {
  const blockers = [];

  if (summary.subscription.status !== "active") {
    blockers.push({
      code: "SUBSCRIPTION_INACTIVE",
      severity: "error",
      message: "当前套餐未生效，请先到账户中心处理。",
    });
  }

  if (summary.remaining.tasks <= 0) {
    blockers.push({
      code: "MONTHLY_TASK_LIMIT_EXCEEDED",
      severity: "error",
      message: "本月生成次数已用完，请升级套餐或下个周期再试。",
    });
  }

  if (summary.remaining.concurrency <= 0) {
    blockers.push({
      code: "CONCURRENCY_LIMIT_EXCEEDED",
      severity: "error",
      message: "当前同时生成任务已达上限，请等待已有任务完成。",
    });
  }

  if (summary.usage.projected_spend + Number(nextAmount) > summary.limits.monthly_spend) {
    blockers.push({
      code: "MONTHLY_SPEND_LIMIT_EXCEEDED",
      severity: "error",
      message: "本月 Tokens 额度不足，请升级套餐或稍后再试。",
      required_amount: roundMoney(Number(nextAmount)),
      remaining_amount: summary.remaining.spend,
    });
  }

  return blockers;
}

function noAvailableRouteMessage(decision) {
  const unsupportedParams = [
    ...new Set(
      decision.rejected
        .flatMap((item) => item.parameters ?? [])
        .filter(Boolean),
    ),
  ];

  if (unsupportedParams.length > 0) {
    return `当前能力暂不支持这些高级选项：${unsupportedParams.join("、")}。请关闭相关选项后再试。`;
  }

  return "当前能力暂时不可用，请稍后再试或切换其他能力。";
}

function isUserIntentInput(platformModel, key, value) {
  if (value === undefined || value === null || value === "" || value === false) {
    return false;
  }

  const field = platformModel?.schema?.find((item) => item.key === key);
  const defaultValue = field?.value ?? field?.defaultValue;
  if (defaultValue !== undefined && String(defaultValue) === String(value)) {
    return false;
  }

  return true;
}

function mappingCanCarryUserValue(mapping) {
  if (!mapping || mapping.transform === "omit" || mapping.transform === "default") {
    return false;
  }

  return hasValidUpstreamParam(mapping.upstream);
}

function hasValidUpstreamParam(value) {
  return Boolean(value && value !== "-");
}

function reject(channel, provider, reason, extra = {}) {
  return {
    channelId: channel.id,
    providerName: provider?.name ?? "Unknown",
    reason,
    ...extra,
  };
}

function createId(prefix) {
  return `${prefix}_${Math.random().toString(16).slice(2, 10)}`;
}

function currentMonthRange(now = new Date()) {
  return {
    start: new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1)),
    end: new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + 1, 1)),
  };
}

function isInRange(value, range) {
  const time = new Date(value).getTime();
  return time >= range.start.getTime() && time < range.end.getTime();
}

function normalizeAmount(amount) {
  const value = Number(amount);
  if (!Number.isFinite(value)) {
    throw problem(422, "VALIDATION_ERROR", "Invalid amount.");
  }
  return roundMoney(value);
}

function estimateTaskCost(channel, input = {}) {
  const unitPrice = Number(channel?.salePrice ?? 0);
  const rawCount = Number(input?.n ?? input?.count ?? 1);
  const count = channel?.billingUnit === "image" ? Math.max(1, Math.min(100, Number.isFinite(rawCount) ? rawCount : 1)) : 1;
  return roundMoney(unitPrice * count);
}

function roundMoney(value) {
  return Math.round(Number(value) * 10000) / 10000;
}

export function problem(status, code, detail, extra = {}) {
  const error = new Error(detail);
  error.status = status;
  error.code = code;
  error.extra = extra;
  return error;
}
