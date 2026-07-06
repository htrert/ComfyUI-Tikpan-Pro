import { getDb } from "../db/client.mjs";

export const postgresWebhooksRepository = {
  async listEndpoints(userId) {
    const db = await getDb();
    const result = await db.query(
      `select id, user_id, url, events, status, secret, created_at, updated_at
       from webhook_endpoints
       where ($1::text is null or user_id = $1)
       order by updated_at desc`,
      [userId ?? null]
    );
    return result.rows.map(mapEndpoint);
  },

  async findEndpoint(id) {
    const db = await getDb();
    const result = await db.query(
      `select id, user_id, url, events, status, secret, created_at, updated_at
       from webhook_endpoints
       where id = $1`,
      [id]
    );
    return result.rows[0] ? mapEndpoint(result.rows[0]) : null;
  },

  async upsertEndpoint(endpoint) {
    const db = await getDb();
    const result = await db.query(
      `insert into webhook_endpoints (
         id, user_id, url, events, status, secret, created_at, updated_at
       )
       values ($1, $2, $3, $4::jsonb, $5, $6, $7, $8)
       on conflict (id)
       do update set
         user_id = excluded.user_id,
         url = excluded.url,
         events = excluded.events,
         status = excluded.status,
         secret = coalesce(excluded.secret, webhook_endpoints.secret),
         updated_at = excluded.updated_at
       returning id, user_id, url, events, status, secret, created_at, updated_at`,
      [
        endpoint.id,
        endpoint.userId,
        endpoint.url,
        JSON.stringify(endpoint.events ?? []),
        endpoint.status,
        endpoint.secret ?? null,
        endpoint.createdAt,
        endpoint.updatedAt ?? new Date().toISOString(),
      ]
    );
    return mapEndpoint(result.rows[0]);
  },

  async listDeliveries({ userId, taskId, limit = 50 } = {}) {
    const db = await getDb();
    const result = await db.query(
      `select id, endpoint_id, user_id, task_id, event, target_url, status,
              response_status, attempt, payload, error_message, created_at, delivered_at
       from webhook_deliveries
       where ($1::text is null or user_id = $1)
         and ($2::text is null or task_id = $2)
       order by created_at desc
       limit $3`,
      [userId ?? null, taskId ?? null, limit]
    );
    return result.rows.map(mapDelivery);
  },

  async createDelivery(delivery) {
    const db = await getDb();
    const result = await db.query(
      `insert into webhook_deliveries (
         id, endpoint_id, user_id, task_id, event, target_url, status,
         response_status, attempt, payload, error_message, created_at, delivered_at
       )
       values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb, $11, $12, $13)
       returning id, endpoint_id, user_id, task_id, event, target_url, status,
                 response_status, attempt, payload, error_message, created_at, delivered_at`,
      [
        delivery.id,
        delivery.endpointId,
        delivery.userId,
        delivery.taskId,
        delivery.event,
        delivery.targetUrl,
        delivery.status,
        delivery.responseStatus ?? null,
        delivery.attempt ?? 1,
        JSON.stringify(delivery.payload ?? {}),
        delivery.errorMessage ?? null,
        delivery.createdAt,
        delivery.deliveredAt ?? null,
      ]
    );
    return mapDelivery(result.rows[0]);
  },
};

function mapEndpoint(row) {
  return {
    id: row.id,
    userId: row.user_id,
    url: row.url,
    events: parseJsonValue(row.events, []),
    status: row.status,
    secret: row.secret,
    createdAt: toIso(row.created_at),
    updatedAt: toIso(row.updated_at),
  };
}

function mapDelivery(row) {
  return {
    id: row.id,
    endpointId: row.endpoint_id,
    userId: row.user_id,
    taskId: row.task_id,
    event: row.event,
    targetUrl: row.target_url,
    status: row.status,
    responseStatus: row.response_status,
    attempt: Number(row.attempt),
    payload: parseJsonValue(row.payload, {}),
    errorMessage: row.error_message,
    createdAt: toIso(row.created_at),
    deliveredAt: row.delivered_at ? toIso(row.delivered_at) : null,
  };
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

function toIso(value) {
  if (!value) {
    return new Date().toISOString();
  }

  return value instanceof Date ? value.toISOString() : new Date(value).toISOString();
}
