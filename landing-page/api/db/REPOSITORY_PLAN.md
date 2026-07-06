# Repository Migration Plan

The API demo currently reads and writes arrays in `api/src/store.mjs`. Move to PostgreSQL in small steps so each business capability remains verifiable.

## Step 1: Read-Only Repositories

Create repositories that read from PostgreSQL and return objects in the current camelCase shape used by `orchestrator.mjs`.

```text
providersRepository.listProviders()
providersRepository.getProvider(id)
modelsRepository.getPlatformModel(id)
modelsRepository.listChannelsForModel(platformModelId)
modelsRepository.getChannelMappings(channelId)
```

Keep writes in memory until the read path is proven with the frontend.

## Step 2: Billing Transaction Repository

Move wallet writes first because money needs database guarantees.

Required operations:

```text
billingRepository.getWalletForUpdate(userId, tx)
billingRepository.preAuthorize(userId, taskId, amount, note, tx)
billingRepository.settleFrozen(userId, taskId, amount, note, tx)
billingRepository.releaseFrozen(userId, taskId, amount, note, tx)
billingRepository.listLedger(userId, limit)
```

Implementation rule: wallet row update and ledger insert must be in the same transaction.

## Step 3: Task Repository

Move task lifecycle persistence.

Required operations:

```text
tasksRepository.createTask(task, attempts, tx)
tasksRepository.getTask(taskId)
tasksRepository.updateProgress(taskId, patch)
tasksRepository.completeTask(taskId, output, settlementPatch, tx)
tasksRepository.failTask(taskId, errorPatch, releasePatch, tx)
tasksRepository.createAttempt(attempt, tx)
tasksRepository.updateAttempt(attemptId, patch, tx)
```

Use `tasks.settled_at` and `tasks.released_at` as idempotency guards inside the transaction.

## Step 4: API Key And Usage Repository

Move platform API key and usage tracking.

Required operations:

```text
apiKeysRepository.findActiveBySecretHash(hash)
apiKeysRepository.createKey(userId, name, scopes)
apiKeysRepository.revokeKey(keyId)
usageRepository.getUsageSummary(userId, period)
usageRepository.consumeRateLimit(apiKeyId, limit)
```

In production, `consumeRateLimit` can use Redis. Keep the SQL table as the single-node fallback and audit shape.

## Step 5: Remove In-Memory Store

After every route uses repositories, keep `store.mjs` only as seed data or replace it with SQL seed files.

Do not change public endpoint responses during this migration. The frontend should not need to know whether data comes from arrays or PostgreSQL.
