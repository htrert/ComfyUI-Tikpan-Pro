import { paymentProviders } from "../store.mjs";

export const paymentProvidersRepository = {
  list({ includeDisabled = true } = {}) {
    return paymentProviders
      .filter((provider) => includeDisabled || provider.status === "active")
      .slice()
      .sort((a, b) => Number(a.sortOrder ?? 0) - Number(b.sortOrder ?? 0));
  },

  findById(id) {
    return paymentProviders.find((provider) => provider.id === id) ?? null;
  },

  upsert(provider) {
    const index = paymentProviders.findIndex((item) => item.id === provider.id);
    if (index >= 0) {
      paymentProviders[index] = {
        ...paymentProviders[index],
        ...provider,
        webhookSecret: provider.webhookSecret ?? paymentProviders[index].webhookSecret,
      };
      return paymentProviders[index];
    }

    paymentProviders.push(provider);
    return provider;
  },
};
