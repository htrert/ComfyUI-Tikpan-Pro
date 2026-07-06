import { getWallet, walletLedger } from "../store.mjs";

export const billingRepository = {
  getWallet(userId = "demo_user") {
    return getWallet(userId);
  },

  appendLedger(entry) {
    if (entry.taskId && ["pre_authorize", "settle", "release", "refund"].includes(entry.type)) {
      const existing = walletLedger.find((item) => item.taskId === entry.taskId && item.type === entry.type);
      if (existing) {
        return existing;
      }
    }
    walletLedger.push(entry);
    return entry;
  },

  listLedger(userId) {
    return walletLedger.filter((item) => !userId || item.userId === userId);
  },
};
