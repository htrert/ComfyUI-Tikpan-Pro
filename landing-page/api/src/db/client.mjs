import { config } from "../config.mjs";

let pgPool = null;

export async function getDb() {
  if (config.storeMode !== "postgres") {
    return null;
  }

  if (!config.databaseUrl) {
    throw new Error("DATABASE_URL is required when TIKPAN_STORE=postgres.");
  }

  if (!pgPool) {
    const { Pool } = await import("pg").catch((error) => {
      error.message =
        "PostgreSQL mode requires the optional pg package. Run npm install pg in landing-page/api first. " +
        error.message;
      throw error;
    });

    pgPool = new Pool({
      connectionString: config.databaseUrl,
      max: Number(process.env.DB_POOL_MAX ?? 10),
      idleTimeoutMillis: Number(process.env.DB_IDLE_TIMEOUT_MS ?? 30_000),
    });
  }

  return {
    query(text, params) {
      return pgPool.query(text, params);
    },
    async transaction(work) {
      const client = await pgPool.connect();
      try {
        await client.query("begin");
        const result = await work(client);
        await client.query("commit");
        return result;
      } catch (error) {
        await client.query("rollback");
        throw error;
      } finally {
        client.release();
      }
    },
  };
}

export async function checkDatabaseConnection() {
  if (config.storeMode !== "postgres") {
    return {
      ok: true,
      mode: config.storeMode,
      connected: false,
      message: "Memory store mode does not require a database connection.",
    };
  }

  const db = await getDb();
  const result = await db.query("select 1 as ok");
  return {
    ok: result.rows?.[0]?.ok === 1,
    mode: config.storeMode,
    connected: true,
    message: "PostgreSQL connection is available.",
  };
}

export async function closeDb() {
  if (pgPool) {
    await pgPool.end();
    pgPool = null;
  }
}
