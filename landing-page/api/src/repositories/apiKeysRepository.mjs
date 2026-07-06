import { apiKeys } from "../store.mjs";

export const apiKeysRepository = {
  listByUser(userId = "demo_user") {
    return apiKeys.filter((key) => key.userId === userId);
  },

  findById(id) {
    return apiKeys.find((key) => key.id === id);
  },

  findBySecret(secret) {
    return apiKeys.find((key) => key.secret === secret);
  },

  create(key) {
    apiKeys.push(key);
    return key;
  },

  update(key) {
    const index = apiKeys.findIndex((item) => item.id === key.id);
    if (index >= 0) {
      apiKeys[index] = key;
    }
    return key;
  },

  touchLastUsed(id, when = new Date().toISOString()) {
    const key = apiKeys.find((item) => item.id === id);
    if (key) {
      key.lastUsedAt = when;
    }
  },
};
