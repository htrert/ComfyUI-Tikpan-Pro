import { paymentOrders } from "../store.mjs";

export const paymentOrdersRepository = {
  create(order) {
    paymentOrders.push(order);
    return order;
  },

  findById(id) {
    return paymentOrders.find((order) => order.id === id) ?? null;
  },

  list({ userId, limit = 50 } = {}) {
    return paymentOrders
      .filter((order) => !userId || order.userId === userId)
      .slice()
      .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
      .slice(0, limit);
  },

  update(order) {
    const index = paymentOrders.findIndex((item) => item.id === order.id);
    if (index >= 0) {
      paymentOrders[index] = order;
    }
    return order;
  },
};
