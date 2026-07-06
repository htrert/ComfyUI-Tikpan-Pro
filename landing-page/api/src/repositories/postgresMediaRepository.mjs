import { getDb } from "../db/client.mjs";

export const postgresMediaRepository = {
  async getStatus() {
    const db = await getDb();
    const result = await db.query("select count(*)::int as count from media_assets");
    return {
      ready: true,
      assets: Number(result.rows[0]?.count ?? 0),
    };
  },

  async listByTask(taskId) {
    const db = await getDb();
    const result = await db.query(
      `select id, task_id, user_id, direction, object_key, public_url, mime_type,
              size_bytes, width, height, duration_seconds, hash, source_url,
              storage_mode, created_at
       from media_assets
       where task_id = $1
       order by created_at asc`,
      [taskId]
    );
    return result.rows.map(mapMediaAsset);
  },

  async listByUser(userId, { limit = 50 } = {}) {
    const db = await getDb();
    const result = await db.query(
      `select id, task_id, user_id, direction, object_key, public_url, mime_type,
              size_bytes, width, height, duration_seconds, hash, source_url,
              storage_mode, created_at
       from media_assets
       where user_id = $1
       order by created_at desc
       limit $2`,
      [userId, limit]
    );
    return result.rows.map(mapMediaAsset);
  },

  async createMany(assets) {
    if (assets.length === 0) {
      return [];
    }

    const db = await getDb();
    await db.transaction(async (client) => {
      for (const asset of assets) {
        await client.query(
          `insert into media_assets (
             id, task_id, user_id, direction, object_key, public_url, mime_type,
             size_bytes, width, height, duration_seconds, hash, source_url,
             storage_mode, created_at
           )
           values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
           on conflict (id) do update set
             object_key = excluded.object_key,
             public_url = excluded.public_url,
             mime_type = excluded.mime_type,
             size_bytes = excluded.size_bytes,
             width = excluded.width,
             height = excluded.height,
             duration_seconds = excluded.duration_seconds,
             hash = excluded.hash,
             source_url = excluded.source_url,
             storage_mode = excluded.storage_mode`,
          [
            asset.id,
            asset.taskId,
            asset.userId,
            asset.direction,
            asset.objectKey,
            asset.publicUrl,
            asset.mimeType ?? null,
            asset.sizeBytes ?? null,
            asset.width ?? null,
            asset.height ?? null,
            asset.durationSeconds ?? null,
            asset.hash ?? null,
            asset.sourceUrl ?? null,
            asset.storageMode ?? "local",
            asset.createdAt,
          ]
        );
      }
    });
    return assets;
  },
};

function mapMediaAsset(row) {
  return {
    id: row.id,
    taskId: row.task_id,
    userId: row.user_id,
    direction: row.direction,
    objectKey: row.object_key,
    publicUrl: row.public_url,
    mimeType: row.mime_type,
    sizeBytes: row.size_bytes === null ? null : Number(row.size_bytes),
    width: row.width,
    height: row.height,
    durationSeconds: row.duration_seconds === null ? null : Number(row.duration_seconds),
    hash: row.hash,
    sourceUrl: row.source_url,
    storageMode: row.storage_mode,
    createdAt: row.created_at instanceof Date ? row.created_at.toISOString() : new Date(row.created_at).toISOString(),
  };
}
