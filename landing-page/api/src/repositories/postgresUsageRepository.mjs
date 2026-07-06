import { getDb } from "../db/client.mjs";

export const postgresUsageRepository = {
  async listBillingPlans() {
    const db = await getDb();
    const result = await db.query(
      `select id, name, monthly_task_limit, monthly_spend_limit,
              rate_limit_per_minute, concurrency_limit, features, status
       from billing_plans
       order by id`
    );
    return result.rows.map(mapBillingPlan);
  },

  async getBillingPlan(id) {
    const db = await getDb();
    const result = await db.query(
      `select id, name, monthly_task_limit, monthly_spend_limit,
              rate_limit_per_minute, concurrency_limit, features, status
       from billing_plans
       where id = $1`,
      [id]
    );
    return result.rows[0] ? mapBillingPlan(result.rows[0]) : null;
  },

  async upsertBillingPlan(plan) {
    const db = await getDb();
    const result = await db.query(
      `insert into billing_plans (
         id, name, monthly_task_limit, monthly_spend_limit, rate_limit_per_minute,
         concurrency_limit, features, status, updated_at
       )
       values ($1, $2, $3, $4, $5, $6, $7::jsonb, $8, now())
       on conflict (id)
       do update set
         name = excluded.name,
         monthly_task_limit = excluded.monthly_task_limit,
         monthly_spend_limit = excluded.monthly_spend_limit,
         rate_limit_per_minute = excluded.rate_limit_per_minute,
         concurrency_limit = excluded.concurrency_limit,
         features = excluded.features,
         status = excluded.status,
         updated_at = now()
       returning id, name, monthly_task_limit, monthly_spend_limit,
                 rate_limit_per_minute, concurrency_limit, features, status`,
      [
        plan.id,
        plan.name,
        plan.monthlyTaskLimit,
        plan.monthlySpendLimit,
        plan.rateLimitPerMinute,
        plan.concurrencyLimit,
        JSON.stringify(plan.features ?? []),
        plan.status,
      ]
    );
    return mapBillingPlan(result.rows[0]);
  },

  async listUserSubscriptions() {
    const db = await getDb();
    const result = await db.query(
      `select id, user_id, plan_id, status, renews_at
       from user_subscriptions
       order by user_id, created_at desc`
    );
    return result.rows.map(mapUserSubscription);
  },

  async getUserSubscription(userId = "demo_user") {
    const db = await getDb();
    const result = await db.query(
      `select id, user_id, plan_id, status, renews_at
       from user_subscriptions
       where user_id = $1
         and status in ('trialing', 'active', 'past_due')
       order by created_at desc
       limit 1`,
      [userId]
    );

    if (result.rows[0]) {
      return mapUserSubscription(result.rows[0]);
    }

    return {
      userId,
      planId: "starter",
      status: "active",
      renewsAt: new Date(new Date().getFullYear(), new Date().getMonth() + 1, 1).toISOString(),
    };
  },

  async upsertUserSubscription(subscription) {
    const db = await getDb();
    const result = await db.query(
      `insert into user_subscriptions (
         id, user_id, plan_id, status, renews_at, cancelled_at, updated_at
       )
       values ($1, $2, $3, $4, $5, $6, now())
       on conflict (id)
       do update set
         user_id = excluded.user_id,
         plan_id = excluded.plan_id,
         status = excluded.status,
         renews_at = excluded.renews_at,
         cancelled_at = excluded.cancelled_at,
         updated_at = now()
       returning id, user_id, plan_id, status, renews_at`,
      [
        subscription.id,
        subscription.userId,
        subscription.planId,
        subscription.status,
        subscription.renewsAt ? new Date(subscription.renewsAt).toISOString() : null,
        subscription.cancelledAt ? new Date(subscription.cancelledAt).toISOString() : null,
      ]
    );
    return mapUserSubscription(result.rows[0]);
  },

  async getRateLimitBucket(apiKeyId) {
    const db = await getDb();
    const result = await db.query(
      `select api_key_id, count, reset_at
       from rate_limit_buckets
       where api_key_id = $1`,
      [apiKeyId]
    );
    return result.rows[0] ? mapRateLimitBucket(result.rows[0]) : null;
  },

  async upsertRateLimitBucket(bucket) {
    const db = await getDb();
    const result = await db.query(
      `insert into rate_limit_buckets (api_key_id, count, reset_at, updated_at)
       values ($1, $2, $3, now())
       on conflict (api_key_id) do update set
         count = excluded.count,
         reset_at = excluded.reset_at,
         updated_at = now()
       returning api_key_id, count, reset_at`,
      [bucket.apiKeyId, bucket.count, new Date(bucket.resetAt).toISOString()]
    );
    return mapRateLimitBucket(result.rows[0]);
  },

  async consumeRateLimit(apiKeyId, limit, nowMs = Date.now()) {
    const db = await getDb();
    const windowMs = 60_000;
    return db.transaction(async (client) => {
      const result = await client.query(
        `select api_key_id, count, reset_at
         from rate_limit_buckets
         where api_key_id = $1
         for update`,
        [apiKeyId]
      );

      const existing = result.rows[0] ? mapRateLimitBucket(result.rows[0]) : null;
      const resetAt = existing && nowMs < existing.resetAt ? existing.resetAt : nowMs + windowMs;
      const count = existing && nowMs < existing.resetAt ? existing.count : 0;

      if (count >= limit) {
        return {
          allowed: false,
          limit,
          remaining: 0,
          resetAt,
          bucket: existing,
        };
      }

      const nextCount = count + 1;
      const updated = await client.query(
        `insert into rate_limit_buckets (api_key_id, count, reset_at, updated_at)
         values ($1, $2, $3, now())
         on conflict (api_key_id) do update set
           count = excluded.count,
           reset_at = excluded.reset_at,
           updated_at = now()
         returning api_key_id, count, reset_at`,
        [apiKeyId, nextCount, new Date(resetAt).toISOString()]
      );

      return {
        allowed: true,
        limit,
        remaining: Math.max(0, limit - nextCount),
        resetAt,
        bucket: mapRateLimitBucket(updated.rows[0]),
      };
    });
  },
};

function mapBillingPlan(row) {
  return {
    id: row.id,
    name: row.name,
    monthlyTaskLimit: Number(row.monthly_task_limit),
    monthlySpendLimit: Number(row.monthly_spend_limit),
    rateLimitPerMinute: Number(row.rate_limit_per_minute),
    concurrencyLimit: Number(row.concurrency_limit),
    features: parseJsonValue(row.features, []),
    status: row.status,
  };
}

function mapUserSubscription(row) {
  return {
    id: row.id,
    userId: row.user_id,
    planId: row.plan_id,
    status: row.status,
    renewsAt: toIsoOrNull(row.renews_at),
  };
}

function mapRateLimitBucket(row) {
  return {
    apiKeyId: row.api_key_id,
    count: Number(row.count),
    resetAt: new Date(row.reset_at).getTime(),
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
