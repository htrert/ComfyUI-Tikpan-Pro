const supportedStoreModes = new Set(["memory", "postgres"]);

export const config = {
  port: Number(process.env.PORT ?? 8787),
  storeMode: normalizeStoreMode(process.env.TIKPAN_STORE ?? "memory"),
  databaseUrl: process.env.DATABASE_URL ?? "",
  adminToken: process.env.TIKPAN_ADMIN_TOKEN ?? "",
  secretsEncryptionKey: process.env.TIKPAN_SECRETS_ENCRYPTION_KEY ?? "",
  paymentWebhookSecret: process.env.TIKPAN_PAYMENT_WEBHOOK_SECRET ?? "tikpan_mock_webhook_secret",
  providerAdapterMode: normalizeProviderAdapterMode(process.env.TIKPAN_PROVIDER_ADAPTER ?? "mock"),
  providerSecrets: readProviderSecrets(process.env.TIKPAN_PROVIDER_SECRETS ?? ""),
  storageAdapterMode: normalizeStorageAdapterMode(process.env.TIKPAN_STORAGE_ADAPTER ?? "local"),
  publicAssetBaseUrl: process.env.CDN_PUBLIC_BASE_URL ?? "https://cdn.example.com",
  remoteAssetMaxBytes: Number(process.env.TIKPAN_REMOTE_ASSET_MAX_BYTES ?? 100 * 1024 * 1024),
  worker: {
    enabled: String(process.env.TIKPAN_WORKER_ENABLED ?? "true").toLowerCase() !== "false",
    id: process.env.TIKPAN_WORKER_ID ?? `worker-${process.pid}`,
    pollIntervalMs: Number(process.env.TIKPAN_WORKER_POLL_INTERVAL_MS ?? 750),
    lockTtlMs: Number(process.env.TIKPAN_WORKER_LOCK_TTL_MS ?? 120000),
  },
  objectStorage: {
    endpoint: process.env.OBJECT_STORAGE_ENDPOINT ?? "",
    bucket: process.env.OBJECT_STORAGE_BUCKET ?? "",
    accessKeyId: process.env.OBJECT_STORAGE_ACCESS_KEY_ID ?? "",
    secretAccessKey: process.env.OBJECT_STORAGE_SECRET_ACCESS_KEY ?? "",
    region: process.env.OBJECT_STORAGE_REGION ?? "auto",
    forcePathStyle: String(process.env.OBJECT_STORAGE_FORCE_PATH_STYLE ?? "true").toLowerCase() !== "false",
  },
};

export function getRuntimeSummary() {
  return {
    store_mode: config.storeMode,
    database_configured: Boolean(config.databaseUrl),
    database_required: config.storeMode === "postgres",
    admin_auth_required: Boolean(config.adminToken),
    secrets_encryption_configured: Boolean(config.secretsEncryptionKey),
    payment_webhook_configured: Boolean(config.paymentWebhookSecret),
    provider_adapter_mode: config.providerAdapterMode,
    storage_adapter_mode: config.storageAdapterMode,
  };
}

function normalizeProviderAdapterMode(value) {
  const mode = String(value).trim().toLowerCase();
  if (!["mock", "http"].includes(mode)) {
    throw new Error(`Unsupported TIKPAN_PROVIDER_ADAPTER "${value}". Use "mock" or "http".`);
  }
  return mode;
}

function normalizeStorageAdapterMode(value) {
  const mode = String(value).trim().toLowerCase();
  if (!["local", "s3"].includes(mode)) {
    throw new Error(`Unsupported TIKPAN_STORAGE_ADAPTER "${value}". Use "local" or "s3".`);
  }
  return mode;
}

function normalizeStoreMode(value) {
  const mode = String(value).trim().toLowerCase();
  if (!supportedStoreModes.has(mode)) {
    throw new Error(`Unsupported TIKPAN_STORE "${value}". Use "memory" or "postgres".`);
  }
  return mode;
}

function readProviderSecrets(raw) {
  if (!raw) {
    return {};
  }

  try {
    return JSON.parse(raw);
  } catch {
    throw new Error("TIKPAN_PROVIDER_SECRETS must be a JSON object keyed by provider id.");
  }
}
