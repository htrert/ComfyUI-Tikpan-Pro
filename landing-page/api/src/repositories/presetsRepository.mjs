import { presets } from "../store.mjs";

export const presetsRepository = {
  list({ userId, limit = 50 } = {}) {
    return presets
      .filter((preset) => !userId || preset.userId === userId)
      .slice()
      .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
      .slice(0, limit);
  },

  findById(id) {
    return presets.find((preset) => preset.id === id) ?? null;
  },

  create(preset) {
    presets.push(preset);
    return preset;
  },

  save(preset) {
    const index = presets.findIndex((item) => item.id === preset.id);
    if (index >= 0) {
      presets[index] = preset;
    }
    return preset;
  },

  delete(id) {
    const index = presets.findIndex((preset) => preset.id === id);
    if (index < 0) {
      return false;
    }

    presets.splice(index, 1);
    return true;
  },
};
