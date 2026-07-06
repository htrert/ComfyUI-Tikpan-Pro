import { getDb } from "../db/client.mjs";

const cache = {
  ready: false,
  loadedAt: null,
  tasks: [],
};

export const postgresTasksRepository = {
  async initialize() {
    const db = await getDb();
    const [taskRows, attemptRows] = await Promise.all([
      db.query(
        `select id, user_id, platform_model_id, status, route_mode, batch_id, batch_title, batch_item_id,
                project_id, project_name, input, output,
                estimated_cost, final_cost, public_error_code, public_error_message,
                selected_channel_id, selected_provider_id, selected_provider_model_id,
                mapped_payload, current_step, progress, queued_at, started_at, finished_at,
                settled_at, released_at, worker_id, locked_until, lock_version, created_at, updated_at
         from tasks
         order by created_at asc`
      ),
      db.query(
        `select id, task_id, provider_id, provider_model_id, channel_id, status, mapped_payload,
                upstream_response, upstream_error_code, upstream_error_message, fallback_reason, cost_price,
                provider_key_id, provider_key_lease_id, provider_key_lease_expires_at, latency_ms, created_at, finished_at
         from task_attempts
         order by task_id, created_at asc`
      ),
    ]);

    const attemptsByTask = groupBy(attemptRows.rows.map(mapAttempt), "taskId");
    cache.tasks = taskRows.rows.map((row) => mapTask(row, attemptsByTask.get(row.id) ?? []));
    cache.ready = true;
    cache.loadedAt = new Date().toISOString();
  },

  getStatus() {
    return {
      ready: cache.ready,
      loaded_at: cache.loadedAt,
      tasks: cache.tasks.length,
    };
  },

  async list() {
    await this.initialize();
    return cache.tasks;
  },

  async listByUser(userId) {
    await this.initialize();
    return cache.tasks.filter((task) => task.userId === userId);
  },

  async findById(id) {
    const db = await getDb();
    const task = await loadTaskById(db, id);
    if (task) {
      upsertCachedTask(task);
    }
    return task;
  },

  async create(task) {
    const db = await getDb();
    await db.transaction(async (client) => {
      await upsertTask(client, task);
      for (const attempt of task.attempts ?? []) {
        await upsertAttempt(client, task.id, attempt);
      }
    });

    cache.tasks.push(task);
    return task;
  },

  async save(task) {
    const db = await getDb();
    await db.transaction(async (client) => {
      await upsertTask(client, task);
      for (const attempt of task.attempts ?? []) {
        await upsertAttempt(client, task.id, attempt);
      }
    });
    return task;
  },

  async claimNextQueued({ workerId, lockTtlMs }) {
    const db = await getDb();
    let claimedTask = null;
    const lockedUntil = new Date(Date.now() + lockTtlMs).toISOString();

    await db.transaction(async (client) => {
      const result = await client.query(
        `select id
         from tasks
         where status in ('queued', 'running', 'saving_media')
           and finished_at is null
           and (locked_until is null or locked_until <= now() or worker_id = $1)
         order by created_at asc
         for update skip locked
         limit 1`,
        [workerId]
      );

      const taskId = result.rows[0]?.id;
      if (!taskId) {
        return;
      }

      await client.query(
        `update tasks
         set worker_id = $1,
             locked_until = $2,
             lock_version = lock_version + 1,
             updated_at = now()
         where id = $3`,
        [workerId, lockedUntil, taskId]
      );

      claimedTask = await loadTaskById(client, taskId);
      upsertCachedTask(claimedTask);
    });

    return claimedTask;
  },

  async releaseClaim(taskId, workerId) {
    const task = cache.tasks.find((item) => item.id === taskId);
    if (!task || task.workerId !== workerId) {
      return null;
    }

    const db = await getDb();
    await db.query(
      `update tasks
       set worker_id = null,
           locked_until = null,
           updated_at = now()
       where id = $1 and worker_id = $2`,
      [taskId, workerId]
    );
    task.workerId = null;
    task.lockedUntil = null;
    return task;
  },
};

async function loadTaskById(client, taskId) {
  const [taskRows, attemptRows] = await Promise.all([
    client.query(
      `select id, user_id, platform_model_id, status, route_mode, batch_id, batch_title, batch_item_id,
              project_id, project_name, input, output,
              estimated_cost, final_cost, public_error_code, public_error_message,
              selected_channel_id, selected_provider_id, selected_provider_model_id,
              mapped_payload, current_step, progress, queued_at, started_at, finished_at,
              settled_at, released_at, worker_id, locked_until, lock_version, created_at, updated_at
       from tasks
       where id = $1`,
      [taskId]
    ),
    client.query(
      `select id, task_id, provider_id, provider_model_id, channel_id, status, mapped_payload,
              upstream_response, upstream_error_code, upstream_error_message, fallback_reason, cost_price,
              provider_key_id, provider_key_lease_id, provider_key_lease_expires_at, latency_ms, created_at, finished_at
       from task_attempts
       where task_id = $1
       order by created_at asc`,
      [taskId]
    ),
  ]);

  const row = taskRows.rows[0];
  return row ? mapTask(row, attemptRows.rows.map(mapAttempt)) : null;
}

function upsertCachedTask(task) {
  if (!task) {
    return;
  }

  const index = cache.tasks.findIndex((item) => item.id === task.id);
  if (index >= 0) {
    cache.tasks[index] = task;
  } else {
    cache.tasks.push(task);
  }
}

async function upsertTask(client, task) {
  await client.query(
    `insert into tasks (
       id, user_id, platform_model_id, status, route_mode, batch_id, batch_title, batch_item_id,
       project_id, project_name, input, output,
       estimated_cost, final_cost, public_error_code, public_error_message,
       selected_channel_id, selected_provider_id, selected_provider_model_id,
       mapped_payload, current_step, progress, queued_at, started_at, finished_at,
       settled_at, released_at, worker_id, locked_until, lock_version, created_at, updated_at
     )
     values (
       $1, $2, $3, $4, $5, $6, $7, $8,
       $9, $10, $11::jsonb, $12::jsonb,
       $13, $14, $15, $16,
       $17, $18, $19,
       $20::jsonb, $21, $22, $23, $24, $25,
       $26, $27, $28, $29, $30, $31, $32
     )
     on conflict (id) do update set
       status = excluded.status,
       route_mode = excluded.route_mode,
       batch_id = excluded.batch_id,
       batch_title = excluded.batch_title,
       batch_item_id = excluded.batch_item_id,
       project_id = excluded.project_id,
       project_name = excluded.project_name,
       input = excluded.input,
       output = excluded.output,
       estimated_cost = excluded.estimated_cost,
       final_cost = excluded.final_cost,
       public_error_code = excluded.public_error_code,
       public_error_message = excluded.public_error_message,
       selected_channel_id = excluded.selected_channel_id,
       selected_provider_id = excluded.selected_provider_id,
       selected_provider_model_id = excluded.selected_provider_model_id,
       mapped_payload = excluded.mapped_payload,
       current_step = excluded.current_step,
       progress = excluded.progress,
       queued_at = excluded.queued_at,
       started_at = excluded.started_at,
       finished_at = excluded.finished_at,
       settled_at = excluded.settled_at,
       released_at = excluded.released_at,
       worker_id = excluded.worker_id,
       locked_until = excluded.locked_until,
       lock_version = excluded.lock_version,
       updated_at = excluded.updated_at`,
    [
      task.id,
      task.userId,
      task.platformModelId,
      task.status,
      task.routeMode ?? "balanced",
      task.batchId ?? null,
      task.batchTitle ?? null,
      task.batchItemId ?? null,
      task.projectId ?? null,
      task.projectName ?? null,
      toJson(task.input ?? {}),
      toJson(task.output ?? null),
      task.estimatedCost ?? 0,
      task.finalCost ?? null,
      task.publicErrorCode ?? null,
      task.publicErrorMessage ?? null,
      task.selectedChannelId ?? null,
      task.selectedProviderId ?? null,
      task.selectedProviderModelId ?? null,
      toJson(task.mappedPayload ?? null),
      task.currentStep ?? null,
      task.progress ?? null,
      task.queuedAt ?? null,
      task.startedAt ?? null,
      task.finishedAt ?? null,
      task.settledAt ?? null,
      task.releasedAt ?? null,
      task.workerId ?? null,
      task.lockedUntil ?? null,
      task.lockVersion ?? 0,
      task.createdAt ?? new Date().toISOString(),
      new Date().toISOString(),
    ]
  );
}

async function upsertAttempt(client, taskId, attempt) {
  await client.query(
    `insert into task_attempts (
       id, task_id, provider_id, provider_model_id, channel_id, status, mapped_payload,
       upstream_response, upstream_error_code, upstream_error_message, fallback_reason, cost_price,
       provider_key_id, provider_key_lease_id, provider_key_lease_expires_at, latency_ms, created_at, finished_at
     )
     values ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
     on conflict (id) do update set
       status = excluded.status,
       mapped_payload = excluded.mapped_payload,
       upstream_response = excluded.upstream_response,
       upstream_error_code = excluded.upstream_error_code,
       upstream_error_message = excluded.upstream_error_message,
       fallback_reason = excluded.fallback_reason,
       cost_price = excluded.cost_price,
       provider_key_id = excluded.provider_key_id,
       provider_key_lease_id = excluded.provider_key_lease_id,
       provider_key_lease_expires_at = excluded.provider_key_lease_expires_at,
       latency_ms = excluded.latency_ms,
       finished_at = excluded.finished_at`,
    [
      attempt.id,
      taskId,
      attempt.providerId,
      attempt.providerModelId,
      attempt.channelId,
      attempt.status,
      toJson(attempt.mappedPayload ?? {}),
      toJson(attempt.upstreamResponse ?? null),
      attempt.errorCode ?? null,
      attempt.errorMessage ?? null,
      attempt.fallbackReason ?? null,
      attempt.costPrice ?? null,
      attempt.providerKeyId ?? null,
      attempt.providerKeyLeaseId ?? null,
      attempt.providerKeyLeaseExpiresAt ?? null,
      attempt.latencyMs ?? null,
      attempt.createdAt ?? new Date().toISOString(),
      attempt.finishedAt ?? null,
    ]
  );
}

function mapTask(row, attempts) {
  return {
    id: row.id,
    userId: row.user_id,
    platformModelId: row.platform_model_id,
    status: row.status,
    routeMode: row.route_mode,
    batchId: row.batch_id,
    batchTitle: row.batch_title,
    batchItemId: row.batch_item_id,
    projectId: row.project_id,
    projectName: row.project_name,
    input: parseJsonValue(row.input, {}),
    output: parseJsonValue(row.output, null),
    estimatedCost: toNumber(row.estimated_cost),
    finalCost: row.final_cost === null ? null : toNumber(row.final_cost),
    publicErrorCode: row.public_error_code,
    publicErrorMessage: row.public_error_message,
    selectedChannelId: row.selected_channel_id,
    selectedProviderId: row.selected_provider_id,
    selectedProviderModelId: row.selected_provider_model_id,
    mappedPayload: parseJsonValue(row.mapped_payload, null),
    currentStep: row.current_step,
    progress: row.progress,
    attempts,
    queuedAt: toIsoOrNull(row.queued_at),
    startedAt: toIsoOrNull(row.started_at),
    finishedAt: toIsoOrNull(row.finished_at),
    settledAt: toIsoOrNull(row.settled_at),
    releasedAt: toIsoOrNull(row.released_at),
    workerId: row.worker_id,
    lockedUntil: toIsoOrNull(row.locked_until),
    lockVersion: Number(row.lock_version ?? 0),
    createdAt: toIsoOrNull(row.created_at),
    updatedAt: toIsoOrNull(row.updated_at),
  };
}

function mapAttempt(row) {
  return {
    id: row.id,
    taskId: row.task_id,
    providerId: row.provider_id,
    providerModelId: row.provider_model_id,
    channelId: row.channel_id,
    status: row.status,
    mappedPayload: parseJsonValue(row.mapped_payload, {}),
    upstreamResponse: parseJsonValue(row.upstream_response, null),
    errorCode: row.upstream_error_code,
    errorMessage: row.upstream_error_message,
    fallbackReason: row.fallback_reason,
    costPrice: row.cost_price === null ? null : toNumber(row.cost_price),
    providerKeyId: row.provider_key_id,
    providerKeyLeaseId: row.provider_key_lease_id,
    providerKeyLeaseExpiresAt: toIsoOrNull(row.provider_key_lease_expires_at),
    latencyMs: row.latency_ms,
    createdAt: toIsoOrNull(row.created_at),
    finishedAt: toIsoOrNull(row.finished_at),
  };
}

function groupBy(items, key) {
  const grouped = new Map();
  for (const item of items) {
    const value = item[key];
    const list = grouped.get(value) ?? [];
    list.push(item);
    grouped.set(value, list);
  }
  return grouped;
}

function parseJsonValue(value, fallback) {
  if (value === null || value === undefined) {
    return fallback;
  }

  if (typeof value === "string") {
    try {
      return JSON.parse(value);
    } catch {
      return fallback;
    }
  }

  return value;
}

function toJson(value) {
  return JSON.stringify(value);
}

function toNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
}

function toIsoOrNull(value) {
  if (!value) {
    return null;
  }

  return value instanceof Date ? value.toISOString() : new Date(value).toISOString();
}
