import { getDb } from "../db/client.mjs";

export const postgresAuditRepository = {
  async list({ userId, resourceType, action, limit = 50 } = {}) {
    const db = await getDb();
    const result = await db.query(
      `select id, actor_id, actor_type, action, resource_type, resource_id,
              user_id, summary, metadata, created_at
       from audit_logs
       where ($1::text is null or user_id = $1)
         and ($2::text is null or resource_type = $2)
         and ($3::text is null or action = $3)
       order by created_at desc
       limit $4`,
      [userId ?? null, resourceType ?? null, action ?? null, limit]
    );
    return result.rows.map(mapAuditLog);
  },

  async create(entry) {
    const db = await getDb();
    const result = await db.query(
      `insert into audit_logs (
         id, actor_id, actor_type, action, resource_type, resource_id,
         user_id, summary, metadata, created_at
       )
       values ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10)
       returning id, actor_id, actor_type, action, resource_type, resource_id,
                 user_id, summary, metadata, created_at`,
      [
        entry.id,
        entry.actorId,
        entry.actorType,
        entry.action,
        entry.resourceType,
        entry.resourceId,
        entry.userId ?? null,
        entry.summary,
        JSON.stringify(entry.metadata ?? {}),
        entry.createdAt,
      ]
    );
    return mapAuditLog(result.rows[0]);
  },
};

function mapAuditLog(row) {
  return {
    id: row.id,
    actorId: row.actor_id,
    actorType: row.actor_type,
    action: row.action,
    resourceType: row.resource_type,
    resourceId: row.resource_id,
    userId: row.user_id,
    summary: row.summary,
    metadata: parseJsonValue(row.metadata, {}),
    createdAt: toIso(row.created_at),
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
