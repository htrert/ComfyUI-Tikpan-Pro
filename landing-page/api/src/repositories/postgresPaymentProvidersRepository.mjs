import { getDb } from "../db/client.mjs";

export const postgresPaymentProvidersRepository = {
  async list({ includeDisabled = true } = {}) {
    const db = await getDb();
    const result = await db.query(
      `select id, name, kind, status, currencies, fee_rate, fixed_fee, min_amount, max_amount,
              checkout_mode, webhook_secret, sort_order, metadata, created_at, updated_at
       from payment_providers
       where ($1::boolean = true or status = 'active')
       order by sort_order asc, created_at asc`,
      [includeDisabled]
    );
    return result.rows.map(mapPaymentProvider);
  },

  async findById(id) {
    const db = await getDb();
    const result = await db.query(
      `select id, name, kind, status, currencies, fee_rate, fixed_fee, min_amount, max_amount,
              checkout_mode, webhook_secret, sort_order, metadata, created_at, updated_at
       from payment_providers
       where id = $1`,
      [id]
    );
    return result.rows[0] ? mapPaymentProvider(result.rows[0]) : null;
  },

  async upsert(provider) {
    const db = await getDb();
    const result = await db.query(
      `insert into payment_providers (
         id, name, kind, status, currencies, fee_rate, fixed_fee, min_amount, max_amount,
         checkout_mode, webhook_secret, sort_order, metadata, created_at, updated_at
       )
       values ($1, $2, $3, $4, $5::jsonb, $6, $7, $8, $9, $10, $11, $12, $13::jsonb, $14, $15)
       on conflict (id)
       do update set
         name = excluded.name,
         kind = excluded.kind,
         status = excluded.status,
         currencies = excluded.currencies,
         fee_rate = excluded.fee_rate,
         fixed_fee = excluded.fixed_fee,
         min_amount = excluded.min_amount,
         max_amount = excluded.max_amount,
         checkout_mode = excluded.checkout_mode,
         webhook_secret = coalesce(excluded.webhook_secret, payment_providers.webhook_secret),
         sort_order = excluded.sort_order,
         metadata = excluded.metadata,
         updated_at = excluded.updated_at
       returning id, name, kind, status, currencies, fee_rate, fixed_fee, min_amount, max_amount,
                 checkout_mode, webhook_secret, sort_order, metadata, created_at, updated_at`,
      [
        provider.id,
        provider.name,
        provider.kind,
        provider.status,
        JSON.stringify(provider.currencies ?? []),
        provider.feeRate,
        provider.fixedFee,
        provider.minAmount,
        provider.maxAmount,
        provider.checkoutMode,
        provider.webhookSecret ?? null,
        provider.sortOrder ?? 50,
        JSON.stringify(provider.metadata ?? {}),
        provider.createdAt,
        provider.updatedAt ?? new Date().toISOString(),
      ]
    );
    return mapPaymentProvider(result.rows[0]);
  },
};

function mapPaymentProvider(row) {
  return {
    id: row.id,
    name: row.name,
    kind: row.kind,
    status: row.status,
    currencies: parseJsonValue(row.currencies, []),
    feeRate: Number(row.fee_rate),
    fixedFee: Number(row.fixed_fee),
    minAmount: Number(row.min_amount),
    maxAmount: Number(row.max_amount),
    checkoutMode: row.checkout_mode,
    webhookSecret: row.webhook_secret,
    sortOrder: Number(row.sort_order ?? 50),
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
