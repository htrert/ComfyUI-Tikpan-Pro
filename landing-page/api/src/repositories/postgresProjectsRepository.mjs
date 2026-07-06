import { getDb } from "../db/client.mjs";

export const postgresProjectsRepository = {
  async list({ userId, includeArchived = false, limit = 50 } = {}) {
    const db = await getDb();
    const clauses = [];
    const values = [];

    if (userId) {
      values.push(userId);
      clauses.push(`user_id = $${values.length}`);
    }
    if (!includeArchived) {
      clauses.push("status <> 'archived'");
    }

    values.push(limit);
    const where = clauses.length > 0 ? `where ${clauses.join(" and ")}` : "";
    const result = await db.query(
      `select id, user_id, name, type, status, description, cover_url, settings, tags,
              created_at, updated_at, archived_at
       from projects
       ${where}
       order by updated_at desc
       limit $${values.length}`,
      values
    );
    return result.rows.map(mapProject);
  },

  async findById(id) {
    const db = await getDb();
    const result = await db.query(
      `select id, user_id, name, type, status, description, cover_url, settings, tags,
              created_at, updated_at, archived_at
       from projects
       where id = $1`,
      [id]
    );
    return result.rows[0] ? mapProject(result.rows[0]) : null;
  },

  async create(project) {
    return this.save(project);
  },

  async save(project) {
    const db = await getDb();
    const result = await db.query(
      `insert into projects (
         id, user_id, name, type, status, description, cover_url, settings, tags,
         created_at, updated_at, archived_at
       )
       values ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9::jsonb, $10, $11, $12)
       on conflict (id) do update set
         name = excluded.name,
         type = excluded.type,
         status = excluded.status,
         description = excluded.description,
         cover_url = excluded.cover_url,
         settings = excluded.settings,
         tags = excluded.tags,
         updated_at = excluded.updated_at,
         archived_at = excluded.archived_at
       returning id, user_id, name, type, status, description, cover_url, settings, tags,
                 created_at, updated_at, archived_at`,
      [
        project.id,
        project.userId,
        project.name,
        project.type,
        project.status,
        project.description ?? "",
        project.coverUrl ?? null,
        JSON.stringify(project.settings ?? {}),
        JSON.stringify(project.tags ?? []),
        project.createdAt ?? new Date().toISOString(),
        project.updatedAt ?? new Date().toISOString(),
        project.archivedAt ?? null,
      ]
    );
    return mapProject(result.rows[0]);
  },

  async delete(id) {
    const db = await getDb();
    const result = await db.query("delete from projects where id = $1", [id]);
    return result.rowCount > 0;
  },
};

function mapProject(row) {
  return {
    id: row.id,
    userId: row.user_id,
    name: row.name,
    type: row.type,
    status: row.status,
    description: row.description ?? "",
    coverUrl: row.cover_url,
    settings: parseJsonValue(row.settings, {}),
    tags: parseJsonValue(row.tags, []),
    createdAt: toIsoOrNull(row.created_at),
    updatedAt: toIsoOrNull(row.updated_at),
    archivedAt: toIsoOrNull(row.archived_at),
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
