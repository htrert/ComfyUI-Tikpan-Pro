# Tikpan Platform API Deployment Notes

This service is being moved from an in-memory product demo toward a production AI aggregation backend. The public API shape should stay stable while repositories are replaced behind the scenes.

## Runtime Modes

```text
TIKPAN_STORE=memory
```

Default mode. Uses `api/src/store.mjs` arrays through repository wrappers. This is the current runnable mode for local UI and business-flow verification.

```text
TIKPAN_STORE=postgres
DATABASE_URL=postgres://user:password@host:5432/database
```

Mixed migration mode. Catalog data is loaded from PostgreSQL at service startup:

- providers
- provider models
- platform models
- model channels
- channel parameter mappings

Wallet balance and wallet ledger writes also use PostgreSQL transactions in this mode. Task lifecycle data is written through PostgreSQL-backed `tasks` and `task_attempts` repositories. Output media asset records are registered through `media_assets`. Platform API keys, billing plans, user subscriptions, and rate-limit buckets also use PostgreSQL repositories.

## Health Checks

```http
GET /health
```

Returns service status, active repository mode, provider count, model count, and task count.

```http
GET /health/readiness
```

Checks whether the selected runtime dependencies are reachable. In memory mode this does not require a database. In postgres mode this validates `DATABASE_URL`, the optional `pg` package, and reports whether the catalog cache was loaded.

## Required Production Environment

```text
PORT=8787
TIKPAN_STORE=postgres
TIKPAN_PROVIDER_ADAPTER=mock
TIKPAN_STORAGE_ADAPTER=local
TIKPAN_WORKER_ENABLED=true
TIKPAN_WORKER_POLL_INTERVAL_MS=750
TIKPAN_WORKER_LOCK_TTL_MS=120000
TIKPAN_PROVIDER_SECRETS={"relay-a":"sk_live_xxx","relay-b":"sk_live_yyy"}
DATABASE_URL=postgres://...
DB_POOL_MAX=10
DB_IDLE_TIMEOUT_MS=30000
CDN_PUBLIC_BASE_URL=https://cdn.example.com
TIKPAN_REMOTE_ASSET_MAX_BYTES=104857600
```

Future production adapters should also add:

```text
UPSTREAM_SECRET_ENCRYPTION_KEY=...
OBJECT_STORAGE_ENDPOINT=...
OBJECT_STORAGE_ACCESS_KEY_ID=...
OBJECT_STORAGE_SECRET_ACCESS_KEY=...
OBJECT_STORAGE_BUCKET=...
OBJECT_STORAGE_REGION=auto
OBJECT_STORAGE_FORCE_PATH_STYLE=true
PAYMENT_WEBHOOK_SECRET=...
```

## Repository Migration Order

1. Catalog read repositories: providers, provider models, platform models, channels, mappings. Done for startup-loaded PostgreSQL catalog.
2. Billing transaction repository: wallet balance, frozen amount, and ledger writes in one database transaction. Done for top-up, pre-authorize, settle, and release.
3. Task lifecycle repository: tasks, attempts, media assets, idempotent settlement/release guards. Done for tasks, attempts, and media asset records; object storage transfer and stronger idempotency guards are still pending.
4. API key and usage repositories: hashed platform keys, quotas, rate limits. Done for key listing, creation, revocation, hash validation, last-used tracking, plans, subscriptions, and per-key rate-limit buckets.
5. Provider adapters and worker queue: adapter registry, retry wrapper, task worker, and fallback execution are in place. The HTTP adapter supports auth headers, timeout handling, HTTP error mapping, output URL normalization, and media asset registration.
6. Queue execution: task creation writes a queued task, while the background queue worker claims eligible tasks, advances lifecycle state, executes provider fallback, and releases the claim. PostgreSQL mode uses `worker_id`, `locked_until`, `lock_version`, and `for update skip locked` so multiple API instances do not execute the same task concurrently.
7. Object storage: local storage adapter rewrites task outputs to platform object keys and CDN URLs. The S3/R2-compatible adapter downloads provider output assets with timeout and size limits, uploads them to the configured bucket, and records storage provenance in `media_assets`.

## Provider Adapter Modes

```text
TIKPAN_PROVIDER_ADAPTER=mock
```

Default mode. No external provider request is sent. This is safe for local UI, routing, billing, and fallback verification.

```text
TIKPAN_PROVIDER_ADAPTER=http
```

Sends real HTTP requests to each provider `base_url`. Runtime secrets must be supplied through `TIKPAN_PROVIDER_SECRETS`. Demo seed values such as `demo-encrypted-relay-a` are treated as placeholders and will return `PROVIDER_NOT_CONFIGURED`.

## Storage Adapter Modes

```text
TIKPAN_STORAGE_ADAPTER=local
```

Default mode. The service registers output media assets, creates stable platform object keys, and returns URLs under `CDN_PUBLIC_BASE_URL`. No external object storage request is sent.

```text
TIKPAN_STORAGE_ADAPTER=s3
```

S3/R2-compatible storage mode. The service validates `OBJECT_STORAGE_ENDPOINT`, `OBJECT_STORAGE_BUCKET`, `OBJECT_STORAGE_ACCESS_KEY_ID`, and `OBJECT_STORAGE_SECRET_ACCESS_KEY`, downloads remote provider assets, uploads them with the generated object key, and returns URLs under `CDN_PUBLIC_BASE_URL`.

Security defaults for media transfer:

- only `http` and `https` source URLs are accepted
- localhost and private IPv4 hosts are rejected
- downloads time out after 30 seconds
- asset downloads are capped by `TIKPAN_REMOTE_ASSET_MAX_BYTES`
- every uploaded asset stores `source_url`, `storage_mode`, `size_bytes`, and `sha256` hash metadata where available

The frontend must not depend on whether the backend is using memory or PostgreSQL.

## Queue Worker

For local verification, run the API with its built-in worker:

```bash
npm run dev
```

```text
TIKPAN_WORKER_ENABLED=true
```

Starts the in-process queue worker with the API service. This is useful for simple deployments and local verification.

For production-style process separation, run API instances without an embedded worker:

```text
TIKPAN_WORKER_ENABLED=false
```

Then start one or more worker processes:

```bash
npm run worker
```

API-only and worker-only process separation requires shared durable storage. Use `TIKPAN_STORE=postgres` so the API process can create tasks and the worker process can claim them from the same `tasks` table. Memory mode is only suitable for a single local API process because each process has its own in-memory task list.

Queue tuning:

- `TIKPAN_WORKER_ID`: stable worker id for logs and task claims; defaults to the process id
- `TIKPAN_WORKER_POLL_INTERVAL_MS`: how often the worker looks for eligible tasks
- `TIKPAN_WORKER_LOCK_TTL_MS`: how long a task claim remains valid if a worker crashes

Task reads are intentionally side-effect-light: `GET /v1/tasks/{task_id}` returns the current persisted state instead of executing the task inline. Execution is handled by the worker claim loop.

Task operation endpoints:

- `POST /v1/tasks/{task_id}/cancel`: cancels a non-terminal task, marks active attempts failed, releases frozen funds, and returns the task resource.
- `POST /v1/tasks/{task_id}/retry`: creates a new queued task from a failed, cancelled, or expired task using the original model, input, and route mode.
- `POST /v1/tasks/{task_id}/status`: local/admin helper for manual lifecycle testing.

Task responses include `worker.worker_id`, `worker.locked_until`, and `worker.lock_version` so operations teams can see whether a task is currently claimed by a worker.

Recommended production topology:

- API service: `TIKPAN_WORKER_ENABLED=false npm run dev`
- Worker service: `npm run worker`
- Shared store: PostgreSQL with all migrations applied
- Media storage: `TIKPAN_STORAGE_ADAPTER=s3` with S3/R2 credentials and a CDN public base URL
