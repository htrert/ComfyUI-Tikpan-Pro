import { getDb } from "../db/client.mjs";

export const postgresAssetMetadataRepository = {
  async listByUser(userId) {
    const db = await getDb();
    const result = await db.query(
      `select task_id, user_id, title, note, favorite, review_status, tags, collections, created_at, updated_at
       from asset_metadata
       where user_id = $1
       order by updated_at desc`,
      [userId]
    );
    return result.rows.map(mapMetadata);
  },

  async findByTask(taskId, userId) {
    const db = await getDb();
    const result = await db.query(
      `select task_id, user_id, title, note, favorite, review_status, tags, collections, created_at, updated_at
       from asset_metadata
       where task_id = $1 and user_id = $2`,
      [taskId, userId]
    );
    return result.rows[0] ? mapMetadata(result.rows[0]) : null;
  },

  async upsert(metadata) {
    const db = await getDb();
    const now = new Date().toISOString();
    const result = await db.query(
      `insert into asset_metadata (
         task_id, user_id, title, note, favorite, review_status, tags, collections, created_at, updated_at
       )
       values ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb, $9, $10)
       on conflict (task_id, user_id) do update set
         title = excluded.title,
         note = excluded.note,
         favorite = excluded.favorite,
         review_status = excluded.review_status,
         tags = excluded.tags,
         collections = excluded.collections,
         updated_at = excluded.updated_at
       returning task_id, user_id, title, note, favorite, review_status, tags, collections, created_at, updated_at`,
      [
        metadata.taskId,
        metadata.userId,
        metadata.title ?? "",
        metadata.note ?? "",
        Boolean(metadata.favorite),
        metadata.reviewStatus ?? "candidate",
        JSON.stringify(metadata.tags ?? []),
        JSON.stringify(metadata.collections ?? []),
        metadata.createdAt ?? now,
        now,
      ]
    );
    return mapMetadata(result.rows[0]);
  },
};

function mapMetadata(row) {
  return {
    taskId: row.task_id,
    userId: row.user_id,
    title: row.title ?? "",
    note: row.note ?? "",
    favorite: Boolean(row.favorite),
    reviewStatus: row.review_status ?? "candidate",
    tags: parseJsonValue(row.tags, []),
    collections: parseJsonValue(row.collections, []),
    createdAt: toIsoOrNull(row.created_at),
    updatedAt: toIsoOrNull(row.updated_at),
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
