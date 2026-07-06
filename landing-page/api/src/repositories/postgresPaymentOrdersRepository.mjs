import { getDb } from "../db/client.mjs";

export const postgresPaymentOrdersRepository = {
  async create(order) {
    const db = await getDb();
    const result = await db.query(
      `insert into payment_orders (
         id, user_id, amount, currency, provider, status, idempotency_key,
         provider_transaction_id, paid_at, credited_ledger_id, metadata, created_at, updated_at
       )
       values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb, $12, $13)
       on conflict (id)
       do update set updated_at = payment_orders.updated_at
       returning id, user_id, amount, currency, provider, status, idempotency_key,
                 provider_transaction_id, paid_at, credited_ledger_id, metadata, created_at, updated_at`,
      [
        order.id,
        order.userId,
        order.amount,
        order.currency,
        order.provider,
        order.status,
        order.idempotencyKey ?? null,
        order.providerTransactionId ?? null,
        order.paidAt ?? null,
        order.creditedLedgerId ?? null,
        JSON.stringify(order.metadata ?? {}),
        order.createdAt,
        order.updatedAt,
      ]
    );
    return mapOrder(result.rows[0]);
  },

  async findById(id) {
    const db = await getDb();
    const result = await db.query(
      `select id, user_id, amount, currency, provider, status, idempotency_key,
              provider_transaction_id, paid_at, credited_ledger_id, metadata, created_at, updated_at
       from payment_orders
       where id = $1`,
      [id]
    );
    return result.rows[0] ? mapOrder(result.rows[0]) : null;
  },

  async list({ userId, limit = 50 } = {}) {
    const db = await getDb();
    const result = await db.query(
      `select id, user_id, amount, currency, provider, status, idempotency_key,
              provider_transaction_id, paid_at, credited_ledger_id, metadata, created_at, updated_at
       from payment_orders
       where ($1::text is null or user_id = $1)
       order by created_at desc
       limit $2`,
      [userId ?? null, limit]
    );
    return result.rows.map(mapOrder);
  },

  async update(order) {
    const db = await getDb();
    const result = await db.query(
      `update payment_orders
       set status = $2,
           provider_transaction_id = $3,
           paid_at = $4,
           credited_ledger_id = $5,
           metadata = $6::jsonb,
           updated_at = $7
       where id = $1
       returning id, user_id, amount, currency, provider, status, idempotency_key,
                 provider_transaction_id, paid_at, credited_ledger_id, metadata, created_at, updated_at`,
      [
        order.id,
        order.status,
        order.providerTransactionId ?? null,
        order.paidAt ?? null,
        order.creditedLedgerId ?? null,
        JSON.stringify(order.metadata ?? {}),
        order.updatedAt ?? new Date().toISOString(),
      ]
    );
    return result.rows[0] ? mapOrder(result.rows[0]) : null;
  },
};

function mapOrder(row) {
  return {
    id: row.id,
    userId: row.user_id,
    amount: Number(row.amount),
    currency: row.currency,
    provider: row.provider,
    status: row.status,
    idempotencyKey: row.idempotency_key,
    providerTransactionId: row.provider_transaction_id,
    paidAt: toIsoOrNull(row.paid_at),
    creditedLedgerId: row.credited_ledger_id,
    metadata: parseJsonValue(row.metadata, {}),
    createdAt: toIso(row.created_at),
    updatedAt: toIso(row.updated_at),
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

function toIsoOrNull(value) {
  return value ? toIso(value) : null;
}
