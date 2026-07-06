import { config, getRuntimeSummary } from "../config.mjs";
import { getStorageStatus } from "../storage/storageAdapters.mjs";
import { assetMetadataRepository } from "./assetMetadataRepository.mjs";
import { apiKeysRepository } from "./apiKeysRepository.mjs";
import { auditRepository } from "./auditRepository.mjs";
import { billingRepository } from "./billingRepository.mjs";
import { catalogRepository } from "./catalogRepository.mjs";
import { mediaRepository } from "./mediaRepository.mjs";
import { paymentProvidersRepository } from "./paymentProvidersRepository.mjs";
import { paymentOrdersRepository } from "./paymentOrdersRepository.mjs";
import { presetsRepository } from "./presetsRepository.mjs";
import { postgresApiKeysRepository } from "./postgresApiKeysRepository.mjs";
import { postgresAssetMetadataRepository } from "./postgresAssetMetadataRepository.mjs";
import { postgresAuditRepository } from "./postgresAuditRepository.mjs";
import { postgresBillingRepository } from "./postgresBillingRepository.mjs";
import { postgresCatalogRepository } from "./postgresCatalogRepository.mjs";
import { postgresMediaRepository } from "./postgresMediaRepository.mjs";
import { postgresPaymentProvidersRepository } from "./postgresPaymentProvidersRepository.mjs";
import { postgresPaymentOrdersRepository } from "./postgresPaymentOrdersRepository.mjs";
import { postgresProviderKeysRepository } from "./postgresProviderKeysRepository.mjs";
import { postgresProjectsRepository } from "./postgresProjectsRepository.mjs";
import { postgresTasksRepository } from "./postgresTasksRepository.mjs";
import { postgresUsageRepository } from "./postgresUsageRepository.mjs";
import { postgresUsersRepository } from "./postgresUsersRepository.mjs";
import { postgresWebhooksRepository } from "./postgresWebhooksRepository.mjs";
import { providerKeysRepository } from "./providerKeysRepository.mjs";
import { projectsRepository } from "./projectsRepository.mjs";
import { tasksRepository } from "./tasksRepository.mjs";
import { usageRepository } from "./usageRepository.mjs";
import { usersRepository } from "./usersRepository.mjs";
import { webhooksRepository } from "./webhooksRepository.mjs";

const usingPostgresCatalog = config.storeMode === "postgres";
const usingPostgresAssetMetadata = config.storeMode === "postgres";
const usingPostgresBilling = config.storeMode === "postgres";
const usingPostgresTasks = config.storeMode === "postgres";
const usingPostgresApiKeys = config.storeMode === "postgres";
const usingPostgresUsage = config.storeMode === "postgres";
const usingPostgresMedia = config.storeMode === "postgres";
const usingPostgresPaymentProviders = config.storeMode === "postgres";
const usingPostgresPaymentOrders = config.storeMode === "postgres";
const usingPostgresProviderKeys = config.storeMode === "postgres";
const usingPostgresProjects = config.storeMode === "postgres";
const usingPostgresWebhooks = config.storeMode === "postgres";
const usingPostgresAudit = config.storeMode === "postgres";
const usingPostgresUsers = config.storeMode === "postgres";

export const repositories = {
  assetMetadata: usingPostgresAssetMetadata ? postgresAssetMetadataRepository : assetMetadataRepository,
  apiKeys: usingPostgresApiKeys ? postgresApiKeysRepository : apiKeysRepository,
  audit: usingPostgresAudit ? postgresAuditRepository : auditRepository,
  billing: usingPostgresBilling ? postgresBillingRepository : billingRepository,
  catalog: usingPostgresCatalog ? postgresCatalogRepository : catalogRepository,
  media: usingPostgresMedia ? postgresMediaRepository : mediaRepository,
  paymentProviders: usingPostgresPaymentProviders ? postgresPaymentProvidersRepository : paymentProvidersRepository,
  paymentOrders: usingPostgresPaymentOrders ? postgresPaymentOrdersRepository : paymentOrdersRepository,
  presets: presetsRepository,
  providerKeys: usingPostgresProviderKeys ? postgresProviderKeysRepository : providerKeysRepository,
  projects: usingPostgresProjects ? postgresProjectsRepository : projectsRepository,
  tasks: usingPostgresTasks ? postgresTasksRepository : tasksRepository,
  usage: usingPostgresUsage ? postgresUsageRepository : usageRepository,
  users: usingPostgresUsers ? postgresUsersRepository : usersRepository,
  webhooks: usingPostgresWebhooks ? postgresWebhooksRepository : webhooksRepository,
};

export async function initializeRepositories() {
  if (usingPostgresCatalog) {
    await postgresCatalogRepository.initialize();
  }
  if (usingPostgresTasks) {
    await postgresTasksRepository.initialize();
  }
}

export function getRepositoryStatus() {
  const postgresRequested = config.storeMode === "postgres";
  const postgresCatalogStatus = postgresCatalogRepository.getStatus();
  const postgresTasksStatus = postgresTasksRepository.getStatus();
  const mediaStatus = postgresRequested ? { ready: true, mode: "postgres" } : mediaRepository.getStatus();

  return {
    ...getRuntimeSummary(),
    active_repository: postgresRequested ? "mixed" : "memory",
    postgres_catalog_ready: postgresRequested && postgresCatalogStatus.ready,
    postgres_asset_metadata_ready: postgresRequested,
    postgres_billing_ready: postgresRequested,
    postgres_tasks_ready: postgresRequested && postgresTasksStatus.ready,
    postgres_api_keys_ready: postgresRequested,
    postgres_usage_ready: postgresRequested,
    postgres_media_ready: postgresRequested,
    postgres_payment_providers_ready: postgresRequested,
    postgres_payment_orders_ready: postgresRequested,
    postgres_provider_keys_ready: postgresRequested,
    postgres_projects_ready: postgresRequested,
    postgres_webhooks_ready: postgresRequested,
    postgres_audit_ready: postgresRequested,
    postgres_users_ready: postgresRequested,
    storage: getStorageStatus(),
    postgres_catalog: postgresCatalogStatus,
    media: mediaStatus,
    postgres_tasks: postgresTasksStatus,
    message:
      postgresRequested
        ? "Catalog, wallet ledger, tasks, task attempts, projects, media assets, API keys, usage plans, rate limits, webhooks, and audit logs use PostgreSQL."
        : "Using the in-memory repository set for local product verification.",
  };
}

export function assertSupportedRepositoryMode() {
  if (config.storeMode === "postgres" && !postgresCatalogRepository.getStatus().ready) {
    const error = new Error(
      "PostgreSQL catalog repository is not ready. Check DATABASE_URL, migrations, and seed data."
    );
    error.status = 503;
    error.code = "REPOSITORY_NOT_READY";
    throw error;
  }

  if (config.storeMode === "postgres" && !postgresTasksRepository.getStatus().ready) {
    const error = new Error("PostgreSQL task repository is not ready. Check DATABASE_URL and migrations.");
    error.status = 503;
    error.code = "REPOSITORY_NOT_READY";
    throw error;
  }
}
