import {
  getChannelMappings,
  getModelCategory,
  getPlatformModel,
  getProvider,
  getProviderModel,
  listAliasesForModel,
  listCategoriesForModel,
  listChannelsForModel,
  modelCategories,
  modelChannels,
  parameterMappings,
  platformModelAliases,
  platformModelCategoryAssignments,
  platformModels,
  providerModels,
  providers,
} from "../store.mjs";

export const catalogRepository = {
  listProviders() {
    return providers;
  },

  listPlatformModels() {
    return platformModels;
  },

  listModelCategories() {
    return modelCategories.slice().sort((a, b) => (a.sortOrder ?? 0) - (b.sortOrder ?? 0));
  },

  getModelCategory(idOrKey) {
    return getModelCategory(idOrKey);
  },

  upsertModelCategory(category) {
    const index = modelCategories.findIndex((item) => item.id === category.id || item.key === category.key);
    if (index >= 0) {
      modelCategories[index] = { ...modelCategories[index], ...category, updatedAt: new Date().toISOString() };
      return modelCategories[index];
    }

    modelCategories.push({ ...category, createdAt: new Date().toISOString(), updatedAt: new Date().toISOString() });
    modelCategories.sort((a, b) => (a.sortOrder ?? 0) - (b.sortOrder ?? 0));
    return category;
  },

  listProviderModels() {
    return providerModels;
  },

  listChannels() {
    return modelChannels;
  },

  getProvider(id) {
    return getProvider(id);
  },

  getProviderModel(id) {
    return getProviderModel(id);
  },

  getPlatformModel(id) {
    return getPlatformModel(id);
  },

  listCategoriesForModel(platformModelId) {
    return listCategoriesForModel(platformModelId);
  },

  listAliasesForModel(platformModelId) {
    return listAliasesForModel(platformModelId);
  },

  upsertProvider(provider) {
    const index = providers.findIndex((item) => item.id === provider.id);
    if (index >= 0) {
      providers[index] = { ...providers[index], ...provider };
      return providers[index];
    }

    providers.push(provider);
    return provider;
  },

  upsertProviderModel(providerModel) {
    const index = providerModels.findIndex((item) => item.id === providerModel.id);
    if (index >= 0) {
      providerModels[index] = { ...providerModels[index], ...providerModel };
      return providerModels[index];
    }

    providerModels.push(providerModel);
    return providerModel;
  },

  upsertPlatformModel(platformModel) {
    const index = platformModels.findIndex((item) => item.id === platformModel.id);
    if (index >= 0) {
      platformModels[index] = { ...platformModels[index], ...platformModel };
      return platformModels[index];
    }

    platformModels.push(platformModel);
    platformModels.sort((a, b) => (a.sortOrder ?? 0) - (b.sortOrder ?? 0));
    return platformModel;
  },

  upsertPlatformModelCategoryAssignment(assignment) {
    const index = platformModelCategoryAssignments.findIndex(
      (item) => item.platformModelId === assignment.platformModelId && item.categoryId === assignment.categoryId
    );
    if (index >= 0) {
      platformModelCategoryAssignments[index] = { ...platformModelCategoryAssignments[index], ...assignment };
      return platformModelCategoryAssignments[index];
    }

    platformModelCategoryAssignments.push(assignment);
    return assignment;
  },

  upsertPlatformModelAlias(alias) {
    const index = platformModelAliases.findIndex(
      (item) => item.platformModelId === alias.platformModelId && item.alias === alias.alias
    );
    if (index >= 0) {
      platformModelAliases[index] = { ...platformModelAliases[index], ...alias };
      return platformModelAliases[index];
    }

    platformModelAliases.push(alias);
    return alias;
  },

  listChannelsForModel(platformModelId) {
    return listChannelsForModel(platformModelId);
  },

  getChannelMappings(channelId) {
    return getChannelMappings(channelId);
  },

  getChannel(id) {
    return modelChannels.find((channel) => channel.id === id);
  },

  createChannel(channel) {
    modelChannels.push(channel);
    return channel;
  },

  upsertPlatformModelSchemaField(platformModelId, field) {
    const model = getPlatformModel(platformModelId);
    if (!model) {
      return null;
    }

    const schema = Array.isArray(model.schema) ? model.schema : [];
    const index = schema.findIndex((item) => item.key === field.key);
    if (index >= 0) {
      schema[index] = { ...schema[index], ...field };
    } else {
      schema.push(field);
    }
    model.schema = schema;
    return model;
  },

  upsertChannelMapping(mapping) {
    const index = parameterMappings.findIndex(
      (item) => item.channelId === mapping.channelId && item.platform === mapping.platform
    );

    if (index >= 0) {
      parameterMappings[index] = { ...parameterMappings[index], ...mapping };
      return parameterMappings[index];
    }

    parameterMappings.push(mapping);
    return mapping;
  },

  listParameterMappings() {
    return parameterMappings;
  },
};
