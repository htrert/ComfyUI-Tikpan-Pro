import { auditLogs } from "../store.mjs";

export const auditRepository = {
  list({ userId, resourceType, action, limit = 50 } = {}) {
    return auditLogs
      .filter((item) => !userId || item.userId === userId)
      .filter((item) => !resourceType || item.resourceType === resourceType)
      .filter((item) => !action || item.action === action)
      .slice()
      .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
      .slice(0, limit);
  },

  create(entry) {
    auditLogs.push(entry);
    return entry;
  },
};
