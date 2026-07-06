import { getDb } from "../db/client.mjs";

export const postgresBillingRepository = {
  supportsAtomicOperations: true,

  async getWallet(userId = "demo_user") {
    const db = await getDb();
    const result = await db.query(
      `select user_id, currency, balance, frozen, updated_at
       from wallets
       where user_id = $1`,
      [userId]
    );

    if (result.rows.length === 0) {
      return createWallet(userId);
    }

    return mapWallet(result.rows[0]);
  },

  async listLedger(userId) {
    const db = await getDb();
    const result = await db.query(
      `select id, user_id, task_id, type, amount, balance_after, frozen_after, note, metadata, created_at
       from wallet_ledger
       where ($1::text is null or user_id = $1)
       order by created_at asc`,
      [userId ?? null]
    );
    return result.rows.map(mapLedgerEntry);
  },

  async topUp(userId, amount, note, idFactory) {
    return mutateWallet(userId, { taskId: null, type: "top_up", amount, note, idFactory }, (wallet, value) => ({
      balance: roundMoney(wallet.balance + value),
      frozen: wallet.frozen,
    }));
  },

  async preAuthorize(userId, taskId, amount, note, idFactory) {
    return mutateWallet(userId, { taskId, type: "pre_authorize", amount, note, idFactory }, (wallet, value) => {
      if (wallet.balance < value) {
        const error = new Error("Insufficient balance. Please top up first.");
        error.status = 402;
        error.code = "NO_BALANCE";
        error.wallet = wallet;
        error.requiredAmount = value;
        throw error;
      }

      return {
        balance: roundMoney(wallet.balance - value),
        frozen: roundMoney(wallet.frozen + value),
      };
    });
  },

  async settleFrozen(userId, taskId, amount, note, idFactory) {
    return mutateWallet(userId, { taskId, type: "settle", amount, note, idFactory }, (wallet, value) => ({
      balance: wallet.balance,
      frozen: roundMoney(Math.max(0, wallet.frozen - value)),
    }));
  },

  async releaseFrozen(userId, taskId, amount, note, idFactory) {
    return mutateWallet(userId, { taskId, type: "release", amount, note, idFactory }, (wallet, value) => ({
      balance: roundMoney(wallet.balance + value),
      frozen: roundMoney(Math.max(0, wallet.frozen - value)),
    }));
  },

  async refundSettled(userId, taskId, amount, note, idFactory) {
    return mutateWallet(userId, { taskId, type: "refund", amount, note, idFactory }, (wallet, value) => ({
      balance: roundMoney(wallet.balance + value),
      frozen: wallet.frozen,
    }));
  },
};

async function mutateWallet(userId, { taskId, type, amount, note, idFactory }, calculateNext) {
  const value = roundMoney(amount);
  const db = await getDb();

  return db.transaction(async (client) => {
    const walletResult = await client.query(
      `select user_id, currency, balance, frozen, updated_at
       from wallets
       where user_id = $1
       for update`,
      [userId]
    );

    const wallet = walletResult.rows.length > 0 ? mapWallet(walletResult.rows[0]) : await createWallet(userId, client);
    if (taskId && ["pre_authorize", "settle", "release", "refund"].includes(type)) {
      const existingLedger = await client.query(
        `select id
         from wallet_ledger
         where task_id = $1 and type = $2
         limit 1`,
        [taskId, type]
      );
      if (existingLedger.rows.length > 0) {
        return wallet;
      }
    }

    const next = calculateNext(wallet, value);
    const updatedAt = new Date().toISOString();

    const updated = await client.query(
      `update wallets
       set balance = $2,
           frozen = $3,
           updated_at = $4
       where user_id = $1
       returning user_id, currency, balance, frozen, updated_at`,
      [userId, next.balance, next.frozen, updatedAt]
    );

    const nextWallet = mapWallet(updated.rows[0]);
    const ledgerTaskId = await getLedgerTaskId(client, taskId);
    const metadata = taskId && !ledgerTaskId ? { task_id: taskId, source: "memory_task_repository" } : {};

    await client.query(
      `insert into wallet_ledger (
         id, user_id, task_id, type, amount, balance_after, frozen_after, note, metadata, created_at
       )
       values ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10)`,
      [
        idFactory("ledger"),
        userId,
        ledgerTaskId,
        type,
        value,
        nextWallet.balance,
        nextWallet.frozen,
        note,
        JSON.stringify(metadata),
        new Date().toISOString(),
      ]
    ).catch((error) => {
      if (error?.code === "23505") {
        return null;
      }
      throw error;
    });

    return nextWallet;
  });
}

async function getLedgerTaskId(client, taskId) {
  if (!taskId) {
    return null;
  }

  const result = await client.query("select id from tasks where id = $1", [taskId]);
  return result.rows.length > 0 ? taskId : null;
}

async function createWallet(userId, client) {
  const db = client ?? (await getDb());
  await db.query(
    `insert into users (id, display_name, email, status, created_at, updated_at)
     values ($1, $2, null, 'active', now(), now())
     on conflict (id) do nothing`,
    [userId, userId]
  );
  const result = await db.query(
    `insert into wallets (user_id, currency, balance, frozen, updated_at)
     values ($1, 'CNY', 0, 0, $2)
     on conflict (user_id) do nothing`,
    [userId, new Date().toISOString()]
  );

  if (result.rowCount === 0) {
    const existing = await db.query(
      `select user_id, currency, balance, frozen, updated_at
       from wallets
       where user_id = $1`,
      [userId]
    );
    return mapWallet(existing.rows[0]);
  }

  return {
    userId,
    currency: "CNY",
    balance: 0,
    frozen: 0,
    updatedAt: new Date().toISOString(),
  };
}

function mapWallet(row) {
  return {
    userId: row.user_id,
    currency: row.currency,
    balance: toNumber(row.balance),
    frozen: toNumber(row.frozen),
    updatedAt: toIso(row.updated_at),
  };
}

function mapLedgerEntry(row) {
  return {
    id: row.id,
    userId: row.user_id,
    taskId: row.task_id ?? parseJsonValue(row.metadata, {}).task_id ?? null,
    type: row.type,
    amount: toNumber(row.amount),
    balanceAfter: toNumber(row.balance_after),
    frozenAfter: toNumber(row.frozen_after),
    note: row.note,
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

function toNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
}

function roundMoney(value) {
  return Math.round(Number(value) * 10000) / 10000;
}

function toIso(value) {
  if (!value) {
    return new Date().toISOString();
  }

  return value instanceof Date ? value.toISOString() : new Date(value).toISOString();
}
