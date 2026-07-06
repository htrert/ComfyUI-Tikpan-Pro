import { getDb } from "../db/client.mjs";

export const postgresUsersRepository = {
  async list() {
    const db = await getDb();
    const result = await db.query(
      `select id, display_name, email, status, created_at, updated_at
       from users
       order by created_at desc`
    );
    return result.rows.map(mapUser);
  },

  async findById(id) {
    const db = await getDb();
    const result = await db.query(
      `select id, display_name, email, status, created_at, updated_at
       from users
       where id = $1`,
      [id]
    );
    return result.rows[0] ? mapUser(result.rows[0]) : null;
  },

  async upsert(user) {
    const db = await getDb();
    const result = await db.query(
      `insert into users (id, display_name, email, status, created_at, updated_at)
       values ($1, $2, $3, $4, $5, $6)
       on conflict (id)
       do update set
         display_name = excluded.display_name,
         email = excluded.email,
         status = excluded.status,
         updated_at = excluded.updated_at
       returning id, display_name, email, status, created_at, updated_at`,
      [
        user.id,
        user.displayName,
        user.email ?? null,
        user.status,
        user.createdAt ?? new Date().toISOString(),
        user.updatedAt ?? new Date().toISOString(),
      ]
    );
    return mapUser(result.rows[0]);
  },
};

function mapUser(row) {
  return {
    id: row.id,
    displayName: row.display_name,
    email: row.email,
    status: row.status,
    createdAt: toIso(row.created_at),
    updatedAt: toIso(row.updated_at),
  };
}

function toIso(value) {
  if (!value) {
    return new Date().toISOString();
  }

  return value instanceof Date ? value.toISOString() : new Date(value).toISOString();
}
