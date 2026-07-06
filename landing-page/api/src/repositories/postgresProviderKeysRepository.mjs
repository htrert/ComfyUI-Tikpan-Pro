import { getDb } from "../db/client.mjs";
import { decryptSecret, encryptSecret } from "../secrets.mjs";

const defaultLeaseTtlMs = 10 * 60_000;

export const postgresProviderKeysRepository = {
  async list() {
    const db = await getDb();
    const result = await db.query(
      `select id, provider_id, name, encrypted_api_key, status, rpm, tpm, concurrency, priority, weight,
              supported_provider_model_ids, current_concurrency, minute_window_started_at,
              minute_request_count, today_request_count, cooling_until, last_used_at,
              last_error_code, last_error_message, notes, created_at, updated_at
       from provider_keys
       order by provider_id, priority, id`
    );
    return result.rows.map(mapProviderKey);
  },

  async listByProvider(providerId) {
    const db = await getDb();
    const result = await db.query(
      `select id, provider_id, name, encrypted_api_key, status, rpm, tpm, concurrency, priority, weight,
              supported_provider_model_ids, current_concurrency, minute_window_started_at,
              minute_request_count, today_request_count, cooling_until, last_used_at,
              last_error_code, last_error_message, notes, created_at, updated_at
       from provider_keys
       where provider_id = $1
       order by priority, id`,
      [providerId]
    );
    return result.rows.map(mapProviderKey);
  },

  async findById(id) {
    const db = await getDb();
    const result = await db.query(
      `select id, provider_id, name, encrypted_api_key, status, rpm, tpm, concurrency, priority, weight,
              supported_provider_model_ids, current_concurrency, minute_window_started_at,
              minute_request_count, today_request_count, cooling_until, last_used_at,
              last_error_code, last_error_message, notes, created_at, updated_at
       from provider_keys
       where id = $1`,
      [id]
    );
    return result.rows[0] ? mapProviderKey(result.rows[0]) : null;
  },

  async acquire({ providerId, providerModelId, taskId = null, attemptId = null, estimatedTokens = 0, createId, ttlMs = defaultLeaseTtlMs }) {
    const db = await getDb();
    let lease = null;

    await db.transaction(async (client) => {
      await reapExpiredLeases(client);
      const result = await client.query(
        `select id, provider_id, name, encrypted_api_key, status, rpm, tpm, concurrency, priority, weight,
                supported_provider_model_ids, current_concurrency, minute_window_started_at,
                minute_request_count, minute_token_count, today_request_count, today_success_count,
                today_failure_count, total_latency_ms, cooling_until, last_used_at,
                last_error_code, last_error_message, notes, created_at, updated_at
         from provider_keys
         where provider_id = $1
           and status in ('active', 'degraded')
           and (cooling_until is null or cooling_until <= now())
           and current_concurrency < concurrency
           and (
             jsonb_array_length(supported_provider_model_ids) = 0
             or supported_provider_model_ids ? $2
           )
           and (
             rpm is null
             or minute_window_started_at is null
             or minute_window_started_at <= now() - interval '60 seconds'
             or minute_request_count < rpm
           )
           and (
             tpm is null
             or minute_window_started_at is null
             or minute_window_started_at <= now() - interval '60 seconds'
             or minute_token_count + $3 <= tpm
           )
         order by priority asc, current_concurrency asc, weight desc, id asc
         for update skip locked
         limit 1`,
        [providerId, providerModelId, Number(estimatedTokens ?? 0)]
      );

      const row = result.rows[0];
      if (!row) {
        return;
      }

      const updated = await client.query(
        `update provider_keys
         set current_concurrency = current_concurrency + 1,
             minute_window_started_at =
               case
                 when minute_window_started_at is null or minute_window_started_at <= now() - interval '60 seconds'
                 then now()
                 else minute_window_started_at
               end,
             minute_request_count =
               case
                 when minute_window_started_at is null or minute_window_started_at <= now() - interval '60 seconds'
                 then 1
                 else minute_request_count + 1
               end,
             minute_token_count =
               case
                 when minute_window_started_at is null or minute_window_started_at <= now() - interval '60 seconds'
                 then $2
                 else minute_token_count + $2
               end,
             today_request_count = today_request_count + 1,
             last_used_at = now(),
             updated_at = now()
         where id = $1
         returning id, provider_id, name, encrypted_api_key, status, rpm, tpm, concurrency, priority, weight,
                   supported_provider_model_ids, current_concurrency, minute_window_started_at,
                   minute_request_count, minute_token_count, today_request_count, today_success_count,
                   today_failure_count, total_latency_ms, cooling_until, last_used_at,
                   last_error_code, last_error_message, notes, created_at, updated_at`,
        [row.id, Number(estimatedTokens ?? 0)]
      );

      const key = mapProviderKey(updated.rows[0]);
      const leaseId = createId ? createId("pkeylease") : `pkeylease_${Math.random().toString(16).slice(2, 10)}`;
      const expiresAt = new Date(Date.now() + ttlMs).toISOString();
      await client.query(
        `insert into provider_key_leases (
           id, provider_key_id, provider_id, task_id, attempt_id, estimated_tokens, acquired_at, expires_at
         )
         values ($1, $2, $3, $4, $5, $6, now(), $7)`,
        [leaseId, key.id, key.providerId, taskId, attemptId, Number(estimatedTokens ?? 0), expiresAt]
      );
      lease = {
        id: leaseId,
        providerKeyId: key.id,
        providerId: key.providerId,
        acquiredAt: new Date().toISOString(),
        expiresAt,
        releasedAt: null,
        estimatedTokens: Number(estimatedTokens ?? 0),
        key: { ...key, encryptedApiKey: decryptSecret(key.encryptedApiKey) },
      };
    });

    return lease;
  },

  async release(lease, outcome = {}) {
    if (!lease?.providerKeyId) {
      return null;
    }

    const db = await getDb();
    const errorCode = classifyProviderKeyError(outcome.errorCode);
    const errorMessage = errorCode ? outcome.errorMessage ?? null : null;
    const coolingUntil = errorCode && shouldCoolDown(errorCode) ? new Date(Date.now() + coolDownMs(errorCode)).toISOString() : null;
    let releasedKey = null;
    await db.transaction(async (client) => {
      const leaseRow = await client.query(
        `select id, provider_key_id, estimated_tokens, released_at
         from provider_key_leases
         where id = $1
         for update`,
        [lease.id]
      );

      if (!leaseRow.rows[0] || leaseRow.rows[0].released_at) {
        releasedKey = await this.findById(lease.providerKeyId);
        return;
      }

      const estimatedTokens = Number(leaseRow.rows[0].estimated_tokens ?? lease.estimatedTokens ?? 0);
      const actualTokens = outcome.actualTokens === undefined || outcome.actualTokens === null ? estimatedTokens : Number(outcome.actualTokens);
      const latencyMs = outcome.latencyMs === undefined || outcome.latencyMs === null ? null : Number(outcome.latencyMs);
      const result = await client.query(
        `update provider_keys
         set current_concurrency = greatest(0, current_concurrency - 1),
             minute_token_count = greatest(0, minute_token_count - $5 + $6),
             today_success_count = today_success_count + case when $2::text is null then 1 else 0 end,
             today_failure_count = today_failure_count + case when $2::text is null then 0 else 1 end,
             total_latency_ms = total_latency_ms + coalesce($7, 0),
             last_error_code = $2,
             last_error_message = $3,
             cooling_until = coalesce($4, cooling_until),
             updated_at = now()
         where id = $1
         returning id, provider_id, name, encrypted_api_key, status, rpm, tpm, concurrency, priority, weight,
                   supported_provider_model_ids, current_concurrency, minute_window_started_at,
                   minute_request_count, minute_token_count, today_request_count, today_success_count,
                   today_failure_count, total_latency_ms, cooling_until, last_used_at,
                   last_error_code, last_error_message, notes, created_at, updated_at`,
        [lease.providerKeyId, errorCode, errorMessage, coolingUntil, estimatedTokens, actualTokens, latencyMs]
      );

      await client.query(
        `update provider_key_leases
         set released_at = now(),
             actual_tokens = $2,
             error_code = $3,
             error_message = $4,
             latency_ms = $5
         where id = $1`,
        [lease.id, actualTokens, errorCode, errorMessage, latencyMs]
      );
      releasedKey = result.rows[0] ? mapProviderKey(result.rows[0]) : null;
    });

    lease.releasedAt = new Date().toISOString();
    return releasedKey;
  },

  async reapExpiredLeases() {
    const db = await getDb();
    return db.transaction((client) => reapExpiredLeases(client));
  },

  async upsert(providerKey) {
    const db = await getDb();
    const result = await db.query(
      `insert into provider_keys (
         id, provider_id, name, encrypted_api_key, status, rpm, tpm, concurrency, priority, weight,
         supported_provider_model_ids, notes, updated_at
       )
       values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb, $12, now())
       on conflict (id)
       do update set
         provider_id = excluded.provider_id,
         name = excluded.name,
         encrypted_api_key = coalesce(excluded.encrypted_api_key, provider_keys.encrypted_api_key),
         status = excluded.status,
         rpm = excluded.rpm,
         tpm = excluded.tpm,
         concurrency = excluded.concurrency,
         priority = excluded.priority,
         weight = excluded.weight,
         supported_provider_model_ids = excluded.supported_provider_model_ids,
         notes = excluded.notes,
         updated_at = now()
       returning id, provider_id, name, encrypted_api_key, status, rpm, tpm, concurrency, priority, weight,
                 supported_provider_model_ids, current_concurrency, minute_window_started_at,
                 minute_request_count, today_request_count, cooling_until, last_used_at,
                 last_error_code, last_error_message, notes, created_at, updated_at`,
      [
        providerKey.id,
        providerKey.providerId,
        providerKey.name,
        encryptSecret(providerKey.encryptedApiKey) ?? null,
        providerKey.status ?? "active",
        providerKey.rpm ?? null,
        providerKey.tpm ?? null,
        providerKey.concurrency ?? 1,
        providerKey.priority ?? 100,
        providerKey.weight ?? 50,
        JSON.stringify(providerKey.supportedProviderModelIds ?? []),
        providerKey.notes ?? null,
      ]
    );
    return mapProviderKey(result.rows[0]);
  },
};

function mapProviderKey(row) {
  return {
    id: row.id,
    providerId: row.provider_id,
    name: row.name,
    encryptedApiKey: row.encrypted_api_key,
    status: row.status,
    rpm: toNullableNumber(row.rpm),
    tpm: toNullableNumber(row.tpm),
    concurrency: Number(row.concurrency ?? 1),
    priority: Number(row.priority ?? 100),
    weight: Number(row.weight ?? 50),
    supportedProviderModelIds: parseJsonValue(row.supported_provider_model_ids, []),
    currentConcurrency: Number(row.current_concurrency ?? 0),
    minuteWindowStartedAt: toIsoOrNull(row.minute_window_started_at),
    minuteRequestCount: Number(row.minute_request_count ?? 0),
    minuteTokenCount: Number(row.minute_token_count ?? 0),
    todayRequestCount: Number(row.today_request_count ?? 0),
    todaySuccessCount: Number(row.today_success_count ?? 0),
    todayFailureCount: Number(row.today_failure_count ?? 0),
    totalLatencyMs: Number(row.total_latency_ms ?? 0),
    coolingUntil: toIsoOrNull(row.cooling_until),
    lastUsedAt: toIsoOrNull(row.last_used_at),
    lastErrorCode: row.last_error_code,
    lastErrorMessage: row.last_error_message,
    notes: row.notes,
    createdAt: toIsoOrNull(row.created_at),
    updatedAt: toIsoOrNull(row.updated_at),
  };
}

async function reapExpiredLeases(client) {
  const expired = await client.query(
    `select id, provider_key_id, estimated_tokens
     from provider_key_leases
     where released_at is null and expires_at <= now()
     for update skip locked`
  );

  for (const lease of expired.rows) {
    await client.query(
      `update provider_keys
       set current_concurrency = greatest(0, current_concurrency - 1),
           minute_token_count = greatest(0, minute_token_count - $2),
           today_failure_count = today_failure_count + 1,
           last_error_code = 'PROVIDER_KEY_LEASE_EXPIRED',
           last_error_message = 'Provider key lease expired and was reclaimed.',
           updated_at = now()
       where id = $1`,
      [lease.provider_key_id, Number(lease.estimated_tokens ?? 0)]
    );
    await client.query(
      `update provider_key_leases
       set released_at = now(),
           error_code = 'PROVIDER_KEY_LEASE_EXPIRED',
           error_message = 'Provider key lease expired and was reclaimed.'
       where id = $1`,
      [lease.id]
    );
  }

  return expired.rowCount;
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

function toNullableNumber(value) {
  if (value === null || value === undefined) {
    return null;
  }
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function toIsoOrNull(value) {
  if (!value) {
    return null;
  }
  return value instanceof Date ? value.toISOString() : new Date(value).toISOString();
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
