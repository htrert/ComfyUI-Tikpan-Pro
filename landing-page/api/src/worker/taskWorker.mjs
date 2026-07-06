import { runProviderAttempt } from "../providerAdapters/index.mjs";

export async function executeGenerationTask({
  task,
  catalogRepository,
  providerKeysRepository,
  selectRoute,
  mapPayload,
  createId,
}) {
  const primaryAttempt = task.attempts[task.attempts.length - 1];

  try {
    const result = await runAttempt({
      task,
      attempt: primaryAttempt,
      catalogRepository,
      providerKeysRepository,
      createId,
    });
    primaryAttempt.status = "completed";
    primaryAttempt.finishedAt = new Date().toISOString();
    primaryAttempt.upstreamResponse = result.raw;
    return {
      status: "completed",
      output: result.output,
      currentStep: "Generation completed; result has been saved.",
    };
  } catch (error) {
    primaryAttempt.status = "failed";
    primaryAttempt.errorCode = error.code ?? "PROVIDER_FAILED";
    primaryAttempt.errorMessage = error.message ?? "Upstream provider failed.";
    primaryAttempt.finishedAt = new Date().toISOString();

    const fallbackChannel = findFallbackChannel({ task, selectRoute, failedChannelId: primaryAttempt.channelId });
    if (!fallbackChannel) {
      return {
        status: "failed",
        publicErrorCode: "PROVIDER_FAILED",
        publicErrorMessage: "The service is busy. Frozen funds have been released.",
      };
    }

    const provider = catalogRepository.getProvider(fallbackChannel.providerId);
    const providerModel = catalogRepository.getProviderModel(fallbackChannel.providerModelId);
    const fallbackPayload = mapPayload(fallbackChannel, providerModel, task.input);
    const fallbackAttempt = {
      id: createId("attempt"),
      providerId: provider.id,
      providerModelId: providerModel.id,
      channelId: fallbackChannel.id,
      status: "running",
      mappedPayload: fallbackPayload,
      costPrice: fallbackChannel.costPrice,
      errorCode: null,
      errorMessage: null,
      fallbackReason: `${primaryAttempt.errorCode}; switched to backup channel.`,
      createdAt: new Date().toISOString(),
    };

    task.attempts.push(fallbackAttempt);
    task.selectedChannelId = fallbackChannel.id;
    task.selectedProviderId = provider.id;
    task.selectedProviderModelId = providerModel.id;
    task.mappedPayload = fallbackPayload;

    let fallbackLease = null;
    try {
      fallbackLease = await acquireProviderKey({
        providerKeysRepository,
        provider,
        providerModel,
        task,
        attempt: fallbackAttempt,
        payload: fallbackPayload,
        channel: fallbackChannel,
        createId,
      });
      const fallbackResult = await runProviderAttempt({
        provider,
        providerModel,
        channel: fallbackChannel,
        providerKeyLease: fallbackLease,
        payload: fallbackPayload,
        task,
      });
      await releaseProviderKey(providerKeysRepository, fallbackLease, providerOutcome(fallbackResult));
      fallbackAttempt.status = "completed";
      fallbackAttempt.latencyMs = fallbackResult.latencyMs ?? null;
      fallbackAttempt.finishedAt = new Date().toISOString();
      fallbackAttempt.upstreamResponse = fallbackResult.raw;
      return {
        status: "completed",
        output: fallbackResult.output,
        currentStep: "Primary channel failed; backup channel completed the task.",
      };
    } catch (fallbackError) {
      await releaseProviderKey(providerKeysRepository, fallbackLease, {
        errorCode: fallbackError.code ?? "PROVIDER_FAILED",
        errorMessage: fallbackError.message,
      });
      fallbackAttempt.status = "failed";
      fallbackAttempt.errorCode = fallbackError.code ?? "PROVIDER_FAILED";
      fallbackAttempt.errorMessage = fallbackError.message ?? "Backup provider failed.";
      fallbackAttempt.finishedAt = new Date().toISOString();
      return {
        status: "failed",
        publicErrorCode: "PROVIDER_FAILED",
        publicErrorMessage: "The service is busy. Frozen funds have been released.",
      };
    }
  }
}

async function runAttempt({ task, attempt, catalogRepository, providerKeysRepository, createId }) {
  const provider = catalogRepository.getProvider(attempt.providerId);
  const providerModel = catalogRepository.getProviderModel(attempt.providerModelId);
  const channel = catalogRepository.getChannel(attempt.channelId);
  attempt.status = "running";
  const providerKeyLease = await acquireProviderKey({
    providerKeysRepository,
    provider,
    providerModel,
    task,
    attempt,
    payload: attempt.mappedPayload,
    channel,
    createId,
  });

  try {
    const result = await runProviderAttempt({
      provider,
      providerModel,
      channel,
      providerKeyLease,
      payload: attempt.mappedPayload,
      task,
    });
    await releaseProviderKey(providerKeysRepository, providerKeyLease, providerOutcome(result));
    attempt.latencyMs = result.latencyMs ?? null;
    return result;
  } catch (error) {
    await releaseProviderKey(providerKeysRepository, providerKeyLease, {
      errorCode: error.code ?? "PROVIDER_FAILED",
      errorMessage: error.message,
    });
    throw error;
  }
}

async function acquireProviderKey({ providerKeysRepository, provider, providerModel, task, attempt, payload, channel, createId }) {
  if (!providerKeysRepository?.acquire) {
    return null;
  }

  const lease = await providerKeysRepository.acquire({
    providerId: provider.id,
    providerModelId: providerModel.id,
    taskId: task?.id ?? null,
    attemptId: attempt.id,
    estimatedTokens: estimateProviderTokens({
      providerModel,
      channel,
      payload,
    }),
    createId,
  });

  if (!lease) {
    const error = new Error(`No available internal key for provider ${provider.name}.`);
    error.code = "PROVIDER_KEY_EXHAUSTED";
    throw error;
  }

  attempt.providerKeyId = lease.providerKeyId;
  attempt.providerKeyLeaseId = lease.id;
  attempt.providerKeyLeaseExpiresAt = lease.expiresAt ?? null;
  return lease;
}

async function releaseProviderKey(providerKeysRepository, lease, outcome = {}) {
  if (!providerKeysRepository?.release || !lease) {
    return null;
  }
  return providerKeysRepository.release(lease, outcome);
}

function providerOutcome(result) {
  return {
    actualTokens: extractUsageTokens(result?.raw),
    latencyMs: result?.latencyMs ?? null,
  };
}

function extractUsageTokens(raw) {
  const usage = raw?.usage ?? raw?.data?.usage ?? {};
  const candidates = [
    usage.total_tokens,
    usage.totalTokens,
    usage.input_tokens !== undefined || usage.output_tokens !== undefined
      ? Number(usage.input_tokens ?? 0) + Number(usage.output_tokens ?? 0)
      : null,
    usage.prompt_tokens !== undefined || usage.completion_tokens !== undefined
      ? Number(usage.prompt_tokens ?? 0) + Number(usage.completion_tokens ?? 0)
      : null,
  ];
  const value = candidates.find((item) => Number.isFinite(Number(item)));
  return value === undefined || value === null ? null : Math.max(0, Math.ceil(Number(value)));
}

function estimateProviderTokens({ providerModel, channel, payload }) {
  if (providerModel?.modality !== "chat") {
    return 0;
  }

  const serialized = JSON.stringify(payload ?? {});
  const roughInputTokens = Math.ceil(serialized.length / 4);
  const maxTokens = Number(payload?.max_tokens ?? payload?.maxTokens ?? 1024);
  return Math.max(1, roughInputTokens + (Number.isFinite(maxTokens) ? maxTokens : 1024));
}

function findFallbackChannel({ task, selectRoute, failedChannelId }) {
  const decision = selectRoute(task.platformModelId, task.input, task.routeMode);
  return decision.rankedChannels?.find((channel) => channel.id !== failedChannelId) ?? null;
}
