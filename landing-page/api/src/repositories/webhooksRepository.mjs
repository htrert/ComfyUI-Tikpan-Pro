import { webhookDeliveries, webhookEndpoints } from "../store.mjs";

export const webhooksRepository = {
  listEndpoints(userId) {
    return webhookEndpoints.filter((endpoint) => !userId || endpoint.userId === userId);
  },

  findEndpoint(id) {
    return webhookEndpoints.find((endpoint) => endpoint.id === id) ?? null;
  },

  upsertEndpoint(endpoint) {
    const index = webhookEndpoints.findIndex((item) => item.id === endpoint.id);
    if (index >= 0) {
      webhookEndpoints[index] = { ...webhookEndpoints[index], ...endpoint, updatedAt: new Date().toISOString() };
      return webhookEndpoints[index];
    }

    webhookEndpoints.push(endpoint);
    return endpoint;
  },

  listDeliveries({ userId, taskId, limit = 50 } = {}) {
    return webhookDeliveries
      .filter((delivery) => !userId || delivery.userId === userId)
      .filter((delivery) => !taskId || delivery.taskId === taskId)
      .slice()
      .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
      .slice(0, limit);
  },

  createDelivery(delivery) {
    webhookDeliveries.push(delivery);
    return delivery;
  },
};
