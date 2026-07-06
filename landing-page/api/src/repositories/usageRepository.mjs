import { billingPlans, getBillingPlan, getUserSubscription, rateLimitBuckets, userSubscriptions } from "../store.mjs";

export const usageRepository = {
  listBillingPlans() {
    return billingPlans;
  },

  getBillingPlan(id) {
    return getBillingPlan(id);
  },

  upsertBillingPlan(plan) {
    const index = billingPlans.findIndex((item) => item.id === plan.id);
    if (index >= 0) {
      billingPlans[index] = { ...billingPlans[index], ...plan };
      return billingPlans[index];
    }

    billingPlans.push(plan);
    return plan;
  },

  listUserSubscriptions() {
    return userSubscriptions;
  },

  getUserSubscription(userId = "demo_user") {
    return getUserSubscription(userId);
  },

  upsertUserSubscription(subscription) {
    const index = userSubscriptions.findIndex(
      (item) =>
        (subscription.id && item.id === subscription.id) ||
        (item.userId === subscription.userId && ["trialing", "active", "past_due"].includes(item.status)),
    );
    if (index >= 0) {
      userSubscriptions[index] = { ...userSubscriptions[index], ...subscription, id: subscription.id ?? userSubscriptions[index].id };
      return userSubscriptions[index];
    }

    userSubscriptions.push(subscription);
    return subscription;
  },

  getRateLimitBucket(apiKeyId) {
    return rateLimitBuckets.find((bucket) => bucket.apiKeyId === apiKeyId);
  },

  upsertRateLimitBucket(bucket) {
    const existingIndex = rateLimitBuckets.findIndex((item) => item.apiKeyId === bucket.apiKeyId);
    if (existingIndex >= 0) {
      rateLimitBuckets[existingIndex] = bucket;
    } else {
      rateLimitBuckets.push(bucket);
    }
    return bucket;
  },
};
