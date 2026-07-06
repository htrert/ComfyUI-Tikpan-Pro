import { assetMetadata } from "../store.mjs";

export const assetMetadataRepository = {
  listByUser(userId) {
    return assetMetadata.filter((item) => item.userId === userId);
  },

  findByTask(taskId, userId) {
    return assetMetadata.find((item) => item.taskId === taskId && item.userId === userId) ?? null;
  },

  upsert(metadata) {
    const index = assetMetadata.findIndex((item) => item.taskId === metadata.taskId && item.userId === metadata.userId);
    if (index >= 0) {
      assetMetadata[index] = { ...assetMetadata[index], ...metadata, updatedAt: new Date().toISOString() };
      return assetMetadata[index];
    }

    assetMetadata.push(metadata);
    return metadata;
  },
};
