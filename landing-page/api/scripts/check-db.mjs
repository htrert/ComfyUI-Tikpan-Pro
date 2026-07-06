import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const migrationsDir = join(root, "db", "migrations");
const migrationFiles = readdirSync(migrationsDir)
  .filter((file) => file.endsWith(".sql"))
  .sort();

const requiredTables = [
  "users",
  "billing_plans",
  "user_subscriptions",
  "wallets",
  "wallet_ledger",
  "providers",
  "provider_models",
  "provider_keys",
  "provider_key_leases",
  "platform_models",
  "model_channels",
  "channel_parameter_mappings",
  "platform_api_keys",
  "rate_limit_buckets",
  "tasks",
  "task_attempts",
  "media_assets",
  "asset_metadata",
  "webhook_endpoints",
  "webhook_deliveries",
  "audit_logs",
  "payment_providers",
  "payment_orders",
  "projects",
];

if (migrationFiles.length === 0) {
  throw new Error("No SQL migrations found.");
}

for (const file of migrationFiles) {
  const sql = readFileSync(join(migrationsDir, file), "utf8");

  assertContains(sql, "begin;", `${file} must start a transaction`);
  assertContains(sql, "commit;", `${file} must commit its transaction`);

  if (file.startsWith("001_") && sql.toLowerCase().includes("insert into")) {
    throw new Error(`${file} must contain schema only; move seed data to a later migration.`);
  }

  const singleQuotes = [...sql].filter((char) => char === "'").length;
  if (singleQuotes % 2 !== 0) {
    throw new Error(`${file} has an odd number of single quotes.`);
  }
}

const fullSchema = migrationFiles.map((file) => readFileSync(join(migrationsDir, file), "utf8")).join("\n");

for (const table of requiredTables) {
  assertContains(fullSchema, `create table ${table}`, `Missing table: ${table}`);
}

for (const indexName of [
  "tasks_user_created_idx",
  "wallet_ledger_user_created_idx",
  "model_channels_platform_status_idx",
  "provider_keys_provider_status_idx",
  "provider_keys_available_idx",
  "provider_key_leases_active_idx",
  "provider_key_leases_task_idx",
  "platform_api_keys_user_status_idx",
  "task_attempts_task_idx",
  "task_attempts_provider_key_created_idx",
  "media_assets_storage_mode_idx",
  "tasks_worker_claim_idx",
  "webhook_endpoints_user_status_idx",
  "webhook_deliveries_user_created_idx",
  "audit_logs_created_idx",
  "audit_logs_resource_idx",
  "payment_providers_status_sort_idx",
  "payment_orders_user_created_idx",
  "payment_orders_status_created_idx",
  "tasks_batch_user_idx",
  "projects_user_updated_idx",
  "projects_user_status_idx",
  "tasks_project_created_idx",
  "asset_metadata_user_updated_idx",
  "asset_metadata_review_status_idx",
]) {
  assertContains(fullSchema, indexName, `Missing index: ${indexName}`);
}

for (const mediaNeedle of ["source_url text", "storage_mode text"]) {
  assertContains(fullSchema, mediaNeedle, `Missing media asset audit column: ${mediaNeedle}`);
}

for (const workerNeedle of ["worker_id text", "locked_until timestamptz", "lock_version integer"]) {
  assertContains(fullSchema, workerNeedle, `Missing task worker column: ${workerNeedle}`);
}

for (const providerKeyNeedle of [
  "supported_provider_model_ids jsonb",
  "current_concurrency integer",
  "minute_request_count integer",
  "cooling_until timestamptz",
  "provider_key_id text references provider_keys",
  "provider_key_lease_expires_at timestamptz",
  "wallet_ledger_task_type_once_idx",
]) {
  assertContains(fullSchema, providerKeyNeedle, `Missing provider key field: ${providerKeyNeedle}`);
}

for (const batchNeedle of ["batch_id text", "batch_title text", "batch_item_id text"]) {
  assertContains(fullSchema, batchNeedle, `Missing task batch column: ${batchNeedle}`);
}

for (const projectNeedle of [
  "project_id text references projects",
  "project_name text",
  "settings jsonb",
  "tags jsonb",
]) {
  assertContains(fullSchema, projectNeedle, `Missing project field: ${projectNeedle}`);
}

for (const assetMetadataNeedle of [
  "create table asset_metadata",
  "review_status text",
  "collections jsonb",
  "primary key (task_id, user_id)",
]) {
  assertContains(fullSchema, assetMetadataNeedle, `Missing asset metadata field: ${assetMetadataNeedle}`);
}

for (const seedNeedle of [
  "insert into users",
  "insert into billing_plans",
  "insert into user_subscriptions",
  "insert into wallets",
  "insert into wallet_ledger",
  "'demo_user'",
  "'ledger_seed_balance'",
  "insert into projects",
  "'proj_campaign_skin_2026'",
]) {
  assertContains(fullSchema, seedNeedle, `Missing seed data: ${seedNeedle}`);
}

console.log(`Checked ${migrationFiles.length} SQL migration(s).`);

function assertContains(haystack, needle, message) {
  if (!haystack.toLowerCase().includes(needle.toLowerCase())) {
    throw new Error(message);
  }
}
