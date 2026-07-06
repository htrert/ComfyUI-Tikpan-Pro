const mediaAssets = [];

export const mediaRepository = {
  getStatus() {
    return {
      ready: true,
      assets: mediaAssets.length,
    };
  },

  listByTask(taskId) {
    return mediaAssets.filter((asset) => asset.taskId === taskId);
  },

  listByUser(userId, { limit = 50 } = {}) {
    return mediaAssets
      .filter((asset) => asset.userId === userId)
      .slice()
      .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
      .slice(0, limit);
  },

  createMany(assets) {
    for (const asset of assets) {
      const existingIndex = mediaAssets.findIndex((item) => item.id === asset.id);
      if (existingIndex >= 0) {
        mediaAssets[existingIndex] = asset;
      } else {
        mediaAssets.push(asset);
      }
    }
    return assets;
  },
};
