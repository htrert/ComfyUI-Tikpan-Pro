# Database Layer

This folder contains the production-oriented PostgreSQL schema for the Tikpan AI aggregation platform. The running demo still uses `api/src/store.mjs`, but the table names and columns here intentionally mirror the in-memory objects so the API can be migrated without changing the frontend contract.

## Migration Order

Run migrations in lexical order:

```bash
psql "$DATABASE_URL" -f api/db/migrations/001_initial_schema.sql
```

The first migration creates the durable model for:

- users, subscriptions, billing plans, API keys, and rate-limit buckets
- wallet balances and immutable wallet ledger rows
- providers, provider models, platform models, channels, and parameter mappings
- tasks, task attempts, media assets, fallback attempts, and settlement markers

## In-Memory To Database Mapping

| Current demo object | PostgreSQL table |
| --- | --- |
| `providers` | `providers` |
| `providerModels` | `provider_models` |
| `platformModels` | `platform_models` |
| `modelChannels` | `model_channels` |
| `parameterMappings` | `channel_parameter_mappings` |
| `apiKeys` | `platform_api_keys` |
| `billingPlans` | `billing_plans` |
| `userSubscriptions` | `user_subscriptions` |
| `rateLimitBuckets` | `rate_limit_buckets` |
| `wallets` | `wallets` |
| `walletLedger` | `wallet_ledger` |
| `tasks` | `tasks` |
| `task.attempts` | `task_attempts` |

## Consistency Rules

- Wallet balance changes should happen inside one database transaction with the related `wallet_ledger` insert.
- `tasks.settled_at` and `tasks.released_at` are idempotency guards. A task should not settle or release frozen funds twice.
- `task_attempts` records every provider call, including fallback retries. User-facing status comes from `tasks`; provider debugging comes from `task_attempts`.
- `platform_api_keys.secret_hash` should store a one-way hash, never the raw secret.
- `providers.encrypted_api_key` should store encrypted upstream credentials, never plaintext.
- `rate_limit_buckets` can remain in Redis in production if horizontal scaling requires it; the SQL table documents the shape and works for a single-node deployment.

## Indexing Notes

The migration indexes the hottest reads first:

- task history by user and creation time
- active routing channels by platform model and status
- wallet ledger by user and creation time
- task attempts by task and provider
- API keys by user and status

For high-volume production traffic, add partitioning to `wallet_ledger`, `tasks`, and `task_attempts` by month after the first real usage profile is known.

## Next Implementation Step

Introduce a repository layer next to `store.mjs`:

```text
api/src/repositories/
  providers.mjs
  models.mjs
  routing.mjs
  tasks.mjs
  billing.mjs
  apiKeys.mjs
  usage.mjs
```

Each repository should expose the same operations currently performed against arrays. That keeps `server.mjs` and `orchestrator.mjs` mostly stable while the storage backend changes from memory to PostgreSQL.
