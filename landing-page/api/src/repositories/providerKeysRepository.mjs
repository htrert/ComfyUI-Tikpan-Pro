import { decryptSecret, encryptSecret } from "../secrets.mjs";
import { providerKeyLeases, providerKeys } from "../store.mjs";

const defaultLeaseTtlMs = 10 * 60_000;

export const providerKeysRepository = {
  list() {
    return providerKeys;
  },

  listByProvider(providerId) {
    return providerKeys.filter((key) => key.providerId === providerId);
  },

  findById(id) {
    return providerKeys.find((key) => key.id === id) ?? null;
  },

  acquire({ providerId, providerModelId, estimatedTokens = 0, createId, ttlMs = defaultLeaseTtlMs }) {
    this.reapExpiredLeases();
    const key = selectAvailableKey(providerKeys, { providerId, providerModelId });
    if (!key) {
      return null;
    }

    const now = new Date();
    const windowStart = normalizeMinuteWindow(key, now);
    key.currentConcurrency = Number(key.currentConcurrency ?? 0) + 1;
    key.minuteWindowStartedAt = windowStart.toISOString();
    key.minuteRequestCount = Number(key.minuteRequestCount ?? 0) + 1;
    key.minuteTokenCount = Number(key.minuteTokenCount ?? 0) + Number(estimatedTokens ?? 0);
    key.todayRequestCount = Number(key.todayRequestCount ?? 0) + 1;
    key.lastUsedAt = now.toISOString();
    key.updatedAt = now.toISOString();

    const lease = {
      id: createId ? createId("pkeylease") : `pkeylease_${Math.random().toString(16).slice(2, 10)}`,
      providerKeyId: key.id,
      providerId: key.providerId,
      acquiredAt: now.toISOString(),
      expiresAt: new Date(now.getTime() + ttlMs).toISOString(),
      releasedAt: null,
      estimatedTokens: Number(estimatedTokens ?? 0),
      actualTokens: null,
      key: { ...key, encryptedApiKey: decryptSecret(key.encryptedApiKey) },
    };
    providerKeyLeases.push(lease);
    return lease;
  },

  release(lease, outcome = {}) {
    if (!lease?.providerKeyId) {
      return null;
    }

    const key = this.findById(lease.providerKeyId);
    if (!key) {
      return null;
    }

    const storedLease = providerKeyLeases.find((item) => item.id === lease.id);
    if (storedLease?.releasedAt) {
      return { ...key };
    }

    key.currentConcurrency = Math.max(0, Number(key.currentConcurrency ?? 0) - 1);
    if (outcome.actualTokens !== undefined && outcome.actualTokens !== null) {
      const estimatedTokens = Number(storedLease?.estimatedTokens ?? lease.estimatedTokens ?? 0);
      const actualTokens = Number(outcome.actualTokens ?? 0);
      key.minuteTokenCount = Math.max(0, Number(key.minuteTokenCount ?? 0) - estimatedTokens + actualTokens);
      if (storedLease) {
        storedLease.actualTokens = actualTokens;
      }
    }
    key.updatedAt = new Date().toISOString();

    const keyErrorCode = classifyProviderKeyError(outcome.errorCode);
    if (keyErrorCode) {
      key.lastErrorCode = keyErrorCode;
      key.lastErrorMessage = outcome.errorMessage ?? null;
      key.todayFailureCount = Number(key.todayFailureCount ?? 0) + 1;
      if (shouldCoolDown(keyErrorCode)) {
        key.coolingUntil = new Date(Date.now() + coolDownMs(keyErrorCode)).toISOString();
      }
    } else {
      key.lastErrorCode = null;
      key.lastErrorMessage = null;
      key.todaySuccessCount = Number(key.todaySuccessCount ?? 0) + 1;
      if (key.coolingUntil && new Date(key.coolingUntil).getTime() <= Date.now()) {
        key.coolingUntil = null;
      }
    }

    lease.releasedAt = key.updatedAt;
    if (storedLease) {
      storedLease.releasedAt = key.updatedAt;
      storedLease.errorCode = keyErrorCode;
      storedLease.errorMessage = outcome.errorMessage ?? null;
    }
    return { ...key };
  },

  reapExpiredLeases(now = new Date()) {
    let released = 0;
    for (const lease of providerKeyLeases) {
      if (lease.releasedAt || !lease.expiresAt || new Date(lease.expiresAt).getTime() > now.getTime()) {
        continue;
      }

      const key = this.findById(lease.providerKeyId);
      if (!key) {
        lease.releasedAt = now.toISOString();
        continue;
      }

      key.currentConcurrency = Math.max(0, Number(key.currentConcurrency ?? 0) - 1);
      key.lastErrorCode = "PROVIDER_KEY_LEASE_EXPIRED";
      key.lastErrorMessage = "Provider key lease expired and was reclaimed.";
      key.updatedAt = now.toISOString();
      lease.releasedAt = now.toISOString();
      lease.errorCode = key.lastErrorCode;
      lease.errorMessage = key.lastErrorMessage;
      released += 1;
    }
    return released;
  },

  upsert(providerKey) {
    const index = providerKeys.findIndex((item) => item.id === providerKey.id);
    const saved = {
      ...providerKey,
      encryptedApiKey: encryptSecret(providerKey.encryptedApiKey),
      updatedAt: new Date().toISOString(),
    };

    if (index >= 0) {
      providerKeys[index] = { ...providerKeys[index], ...saved };
      return providerKeys[index];
    }

    providerKeys.push({
      ...saved,
      currentConcurrency: Number(saved.currentConcurrency ?? 0),
      minuteWindowStartedAt: saved.minuteWindowStartedAt ?? null,
      minuteRequestCount: Number(saved.minuteRequestCount ?? 0),
      minuteTokenCount: Number(saved.minuteTokenCount ?? 0),
      todayRequestCount: Number(saved.todayRequestCount ?? 0),
      coolingUntil: saved.coolingUntil ?? null,
      lastUsedAt: saved.lastUsedAt ?? null,
      lastErrorCode: saved.lastErrorCode ?? null,
      lastErrorMessage: saved.lastErrorMessage ?? null,
      createdAt: saved.createdAt ?? new Date().toISOString(),
    });
    return providerKeys[providerKeys.length - 1];
  },
};

function selectAvailableKey(keys, { providerId, providerModelId }) {
  const now = new Date();
  return keys
    .filter((key) => key.providerId === providerId)
    .filter((key) => key.status === "active" || key.status === "degraded")
    .filter((key) => supportsProviderModel(key, providerModelId))
    .filter((key) => !key.coolingUntil || new Date(key.coolingUntil).getTime() <= now.getTime())
    .filter((key) => Number(key.currentConcurrency ?? 0) < Number(key.concurrency ?? Number.POSITIVE_INFINITY))
    .filter((key) => availableRpm(key, now) > 0)
    .sort(compareProviderKeys)[0] ?? null;
}

function supportsProviderModel(key, providerModelId) {
  const supported = key.supportedProviderModelIds ?? [];
  return supported.length === 0 || supported.includes(providerModelId);
}

function availableRpm(key, now) {
  const rpm = Number(key.rpm ?? 0);
  if (!rpm) {
    return Number.POSITIVE_INFINITY;
  }

  const windowStart = normalizeMinuteWindow(key, now);
  const sameWindow = key.minuteWindowStartedAt && new Date(key.minuteWindowStartedAt).getTime() === windowStart.getTime();
  const used = sameWindow ? Number(key.minuteRequestCount ?? 0) : 0;
  return rpm - used;
}

function normalizeMinuteWindow(key, now) {
  const currentWindow = key.minuteWindowStartedAt ? new Date(key.minuteWindowStartedAt) : null;
  if (currentWindow && now.getTime() - currentWindow.getTime() < 60_000) {
    return currentWindow;
  }

  key.minuteRequestCount = 0;
  return now;
}

function compareProviderKeys(a, b) {
  const priorityDiff = Number(a.priority ?? 100) - Number(b.priority ?? 100);
  if (priorityDiff !== 0) {
    return priorityDiff;
  }

  const concurrencyDiff = Number(a.currentConcurrency ?? 0) - Number(b.currentConcurrency ?? 0);
  if (concurrencyDiff !== 0) {
    return concurrencyDiff;
  }

  return Number(b.weight ?? 0) - Number(a.weight ?? 0);
}

function shouldCoolDown(errorCode) {
  return ["PROVIDER_RATE_LIMITED", "PROVIDER_AUTH_FAILED", "PROVIDER_5XX", "PROVIDER_TIMEOUT"].includes(errorCode);
}

function classifyProviderKeyError(errorCode) {
  if (!errorCode || ["VALIDATION_ERROR", "INVALID_IMAGE_INPUT", "CONTENT_REJECTED", "PROVIDER_REQUEST_FAILED"].includes(errorCode)) {
    return null;
  }
  return errorCode;
}

function coolDownMs(errorCode) {
  if (errorCode === "PROVIDER_AUTH_FAILED") {
    return 10 * 60_000;
  }
  if (errorCode === "PROVIDER_RATE_LIMITED") {
    return 60_000;
  }
  return 15_000;
}
