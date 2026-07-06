import { getDb } from "../db/client.mjs";

export const postgresApiKeysRepository = {
  async listByUser(userId = "demo_user") {
    const db = await getDb();
    const result = await db.query(
      `select id, user_id, name, prefix, status, scopes, last_used_at, revoked_at, created_at
       from platform_api_keys
       where user_id = $1
       order by created_at desc`,
      [userId]
    );
    return result.rows.map(mapApiKey);
  },

  async findById(id) {
    const db = await getDb();
    const result = await db.query(
      `select id, user_id, name, prefix, status, scopes, last_used_at, revoked_at, created_at
       from platform_api_keys
       where id = $1`,
      [id]
    );
    return result.rows[0] ? mapApiKey(result.rows[0]) : null;
  },

  async findBySecret(secret) {
    const db = await getDb();
    const result = await db.query(
      `select id, user_id, name, prefix, status, scopes, last_used_at, revoked_at, created_at
       from platform_api_keys
       where secret_hash = crypt($1, secret_hash)
       limit 1`,
      [secret]
    );
    return result.rows[0] ? mapApiKey(result.rows[0]) : null;
  },

  async create(key) {
    const db = await getDb();
    const result = await db.query(
      `insert into platform_api_keys (
         id, user_id, name, prefix, secret_hash, status, scopes, last_used_at, revoked_at, created_at
       )
       values ($1, $2, $3, $4, crypt($5, gen_salt('bf')), $6, $7::jsonb, $8, $9, $10)
       returning id, user_id, name, prefix, status, scopes, last_used_at, revoked_at, created_at`,
      [
        key.id,
        key.userId,
        key.name,
        key.prefix,
        key.secret,
        key.status,
        JSON.stringify(key.scopes ?? []),
        key.lastUsedAt,
        key.revokedAt ?? null,
        key.createdAt,
      ]
    );

    return { ...mapApiKey(result.rows[0]), secret: key.secret };
  },

  async update(key) {
    const db = await getDb();
    const result = await db.query(
      `update platform_api_keys
       set name = $2,
           status = $3,
           scopes = $4::jsonb,
           last_used_at = $5,
           revoked_at = $6
       where id = $1
       returning id, user_id, name, prefix, status, scopes, last_used_at, revoked_at, created_at`,
      [
        key.id,
        key.name,
        key.status,
        JSON.stringify(key.scopes ?? []),
        key.lastUsedAt ?? null,
        key.revokedAt ?? null,
      ]
    );
    return result.rows[0] ? mapApiKey(result.rows[0]) : null;
  },

  async touchLastUsed(id, when = new Date().toISOString()) {
    const db = await getDb();
    await db.query("update platform_api_keys set last_used_at = $2 where id = $1", [id, when]);
  },
};

function mapApiKey(row) {
  return {
    id: row.id,
    userId: row.user_id,
    name: row.name,
    prefix: row.prefix,
    status: row.status,
    scopes: parseJsonValue(row.scopes, []),
    lastUsedAt: toIsoOrNull(row.last_used_at),
    createdAt: toIsoOrNull(row.created_at),
    revokedAt: toIsoOrNull(row.revoked_at),
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

function toIsoOrNull(value) {
  if (!value) {
    return null;
  }

  return value instanceof Date ? value.toISOString() : new Date(value).toISOString();
}
