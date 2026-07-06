import { getDb } from "../db/client.mjs";

const cache = {
  ready: false,
  loadedAt: null,
  providers: [],
  providerModels: [],
  platformModels: [],
  modelCategories: [],
  categoryAssignments: [],
  modelAliases: [],
  channels: [],
  parameterMappings: [],
};

export const postgresCatalogRepository = {
  async initialize() {
    const db = await getDb();
    const [providers, providerModels, platformModels, modelCategories, categoryAssignments, modelAliases, channels, mappings] = await Promise.all([
      db.query(
        `select id, name, kind, base_url, auth_type, encrypted_api_key, status, rpm, concurrency, latency_ms, success_rate
         from providers
         order by id`
      ),
      db.query(
        `select id, provider_id, upstream_model_name, endpoint_type, modality, status, raw_capabilities, notes
         from provider_models
         order by id`
      ),
      db.query(
        `select id, slug, display_name, name, short_name, modality, tier, description, use_cases, visible, recommended,
                estimated_cost, estimated_time, sort_order, schema
         from platform_models
         order by sort_order, id`
      ),
      db.query(
        `select id, key, name, icon, sort_order, visible, parent_id, status, aliases
         from model_categories
         order by sort_order, key`
      ),
      db.query(
        `select id, platform_model_id, category_id, sort_order, is_primary
         from platform_model_category_assignments
         order by sort_order, id`
      ),
      db.query(
        `select id, platform_model_id, alias, kind
         from platform_model_aliases
         order by platform_model_id, alias`
      ),
      db.query(
        `select id, platform_model_id, provider_id, provider_model_id, role, status, weight, priority,
                cost_price, sale_price, billing_unit, latency, success_rate, max_concurrency, timeout_ms, supports
         from model_channels
         order by platform_model_id, priority, id`
      ),
      db.query(
        `select id, channel_id, platform_param_key, upstream_param_key, transform, value_map, default_value, note
         from channel_parameter_mappings
         order by channel_id, platform_param_key`
      ),
    ]);

    cache.providers = providers.rows.map(mapProvider);
    cache.providerModels = providerModels.rows.map(mapProviderModel);
    cache.platformModels = platformModels.rows.map(mapPlatformModel);
    cache.modelCategories = modelCategories.rows.map(mapModelCategory);
    cache.categoryAssignments = categoryAssignments.rows.map(mapCategoryAssignment);
    cache.modelAliases = modelAliases.rows.map(mapModelAlias);
    cache.channels = channels.rows.map(mapChannel);
    cache.parameterMappings = mappings.rows.map(mapParameterMapping);
    cache.ready = true;
    cache.loadedAt = new Date().toISOString();
  },

  getStatus() {
    return {
      ready: cache.ready,
      loaded_at: cache.loadedAt,
      providers: cache.providers.length,
      platform_models: cache.platformModels.length,
      model_categories: cache.modelCategories.length,
      channels: cache.channels.length,
      parameter_mappings: cache.parameterMappings.length,
    };
  },

  listProviders() {
    return cache.providers;
  },

  listPlatformModels() {
    return cache.platformModels.map(withModelMenuMetadata);
  },

  listModelCategories() {
    return cache.modelCategories;
  },

  listProviderModels() {
    return cache.providerModels;
  },

  listChannels() {
    return cache.channels;
  },

  getProvider(id) {
    return cache.providers.find((provider) => provider.id === id);
  },

  getProviderModel(id) {
    return cache.providerModels.find((model) => model.id === id);
  },

  getPlatformModel(id) {
    const model = cache.platformModels.find((item) => item.id === id);
    return model ? withModelMenuMetadata(model) : undefined;
  },

  getModelCategory(idOrKey) {
    return cache.modelCategories.find((category) => category.id === idOrKey || category.key === idOrKey);
  },

  async upsertModelCategory(category) {
    const db = await getDb();
    const result = await db.query(
      `insert into model_categories (
         id, key, name, icon, sort_order, visible, parent_id, status, aliases, updated_at
       )
       values ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, now())
       on conflict (key)
       do update set
         name = excluded.name,
         icon = excluded.icon,
         sort_order = excluded.sort_order,
         visible = excluded.visible,
         parent_id = excluded.parent_id,
         status = excluded.status,
         aliases = excluded.aliases,
         updated_at = now()
       returning id, key, name, icon, sort_order, visible, parent_id, status, aliases`,
      [
        category.id,
        category.key,
        category.name,
        category.icon ?? null,
        category.sortOrder ?? 0,
        category.visible ?? true,
        category.parentId ?? null,
        category.status ?? "published",
        JSON.stringify(category.aliases ?? []),
      ]
    );

    const saved = mapModelCategory(result.rows[0]);
    await this.initialize();
    return saved;
  },

  listCategoriesForModel(platformModelId) {
    return categoriesForModel(platformModelId);
  },

  listAliasesForModel(platformModelId) {
    return cache.modelAliases.filter((alias) => alias.platformModelId === platformModelId);
  },

  async upsertProvider(provider) {
    const db = await getDb();
    const result = await db.query(
      `insert into providers (
         id, name, kind, base_url, auth_type, encrypted_api_key, status,
         rpm, concurrency, latency_ms, success_rate, updated_at
       )
       values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, now())
       on conflict (id)
       do update set
         name = excluded.name,
         kind = excluded.kind,
         base_url = excluded.base_url,
         auth_type = excluded.auth_type,
         encrypted_api_key = coalesce(excluded.encrypted_api_key, providers.encrypted_api_key),
         status = excluded.status,
         rpm = excluded.rpm,
         concurrency = excluded.concurrency,
         latency_ms = excluded.latency_ms,
         success_rate = excluded.success_rate,
         updated_at = now()
       returning id, name, kind, base_url, auth_type, encrypted_api_key, status, rpm, concurrency, latency_ms, success_rate`,
      [
        provider.id,
        provider.name,
        provider.kind,
        provider.baseUrl,
        provider.authType,
        provider.encryptedApiKey ?? null,
        provider.status,
        provider.rpm,
        provider.concurrency,
        provider.latencyMs,
        provider.successRate,
      ]
    );

    const saved = mapProvider(result.rows[0]);
    await this.initialize();
    return saved;
  },

  async upsertProviderModel(providerModel) {
    const db = await getDb();
    const result = await db.query(
      `insert into provider_models (
         id, provider_id, upstream_model_name, endpoint_type, modality, status,
         raw_capabilities, notes, updated_at
       )
       values ($1, $2, $3, $4, $5, $6, $7::jsonb, $8, now())
       on conflict (id)
       do update set
         provider_id = excluded.provider_id,
         upstream_model_name = excluded.upstream_model_name,
         endpoint_type = excluded.endpoint_type,
         modality = excluded.modality,
         status = excluded.status,
         raw_capabilities = excluded.raw_capabilities,
         notes = excluded.notes,
         updated_at = now()
       returning id, provider_id, upstream_model_name, endpoint_type, modality, status, raw_capabilities, notes`,
      [
        providerModel.id,
        providerModel.providerId,
        providerModel.upstreamModelName,
        providerModel.endpointType,
        providerModel.modality,
        providerModel.status,
        JSON.stringify(providerModel.rawCapabilities ?? {}),
        providerModel.notes ?? null,
      ]
    );

    const saved = mapProviderModel(result.rows[0]);
    await this.initialize();
    return saved;
  },

  async upsertPlatformModel(platformModel) {
    const db = await getDb();
    const result = await db.query(
      `insert into platform_models (
         id, slug, display_name, name, short_name, modality, tier, description, use_cases,
         visible, recommended, estimated_cost, estimated_time, sort_order, schema, updated_at
       )
       values ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10, $11, $12, $13, $14, $15::jsonb, now())
       on conflict (id)
       do update set
         slug = excluded.slug,
         display_name = excluded.display_name,
         name = excluded.name,
         short_name = excluded.short_name,
         modality = excluded.modality,
         tier = excluded.tier,
         description = excluded.description,
         use_cases = excluded.use_cases,
         visible = excluded.visible,
         recommended = excluded.recommended,
         estimated_cost = excluded.estimated_cost,
         estimated_time = excluded.estimated_time,
         sort_order = excluded.sort_order,
         schema = excluded.schema,
         updated_at = now()
       returning id, slug, display_name, name, short_name, modality, tier, description, use_cases, visible, recommended,
                 estimated_cost, estimated_time, sort_order, schema`,
      [
        platformModel.id,
        platformModel.slug ?? slugify(platformModel.id),
        platformModel.displayName ?? platformModel.name,
        platformModel.name,
        platformModel.shortName,
        platformModel.modality,
        platformModel.tier,
        platformModel.description,
        JSON.stringify(platformModel.useCases ?? []),
        platformModel.visible,
        platformModel.recommended,
        platformModel.estimatedCost ?? null,
        platformModel.estimatedTime ?? null,
        platformModel.sortOrder ?? 0,
        JSON.stringify(platformModel.schema ?? []),
      ]
    );

    const saved = mapPlatformModel(result.rows[0]);
    await this.initialize();
    return saved;
  },

  async upsertPlatformModelCategoryAssignment(assignment) {
    const db = await getDb();
    const result = await db.query(
      `insert into platform_model_category_assignments (
         id, platform_model_id, category_id, sort_order, is_primary
       )
       values ($1, $2, $3, $4, $5)
       on conflict (platform_model_id, category_id)
       do update set
         sort_order = excluded.sort_order,
         is_primary = excluded.is_primary
       returning id, platform_model_id, category_id, sort_order, is_primary`,
      [
        assignment.id,
        assignment.platformModelId,
        assignment.categoryId,
        assignment.sortOrder ?? 0,
        Boolean(assignment.isPrimary),
      ]
    );

    const saved = mapCategoryAssignment(result.rows[0]);
    await this.initialize();
    return saved;
  },

  async upsertPlatformModelAlias(alias) {
    const db = await getDb();
    const result = await db.query(
      `insert into platform_model_aliases (id, platform_model_id, alias, kind)
       values ($1, $2, $3, $4)
       on conflict (platform_model_id, alias)
       do update set kind = excluded.kind
       returning id, platform_model_id, alias, kind`,
      [
        alias.id,
        alias.platformModelId,
        alias.alias,
        alias.kind ?? "search",
      ]
    );

    const saved = mapModelAlias(result.rows[0]);
    await this.initialize();
    return saved;
  },

  listChannelsForModel(platformModelId) {
    return cache.channels.filter((channel) => channel.platformModelId === platformModelId);
  },

  getChannelMappings(channelId) {
    return cache.parameterMappings.filter((mapping) => mapping.channelId === channelId);
  },

  getChannel(id) {
    return cache.channels.find((channel) => channel.id === id);
  },

  async createChannel(channel) {
    const db = await getDb();
    const result = await db.query(
      `insert into model_channels (
         id, platform_model_id, provider_id, provider_model_id, role, status, weight, priority,
         cost_price, sale_price, billing_unit, latency, success_rate, max_concurrency, timeout_ms, supports
       )
       values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16::jsonb)
       returning id, platform_model_id, provider_id, provider_model_id, role, status, weight, priority,
                 cost_price, sale_price, billing_unit, latency, success_rate, max_concurrency, timeout_ms, supports`,
      [
        channel.id,
        channel.platformModelId,
        channel.providerId,
        channel.providerModelId,
        channel.role,
        channel.status,
        channel.weight,
        channel.priority,
        channel.costPrice,
        channel.salePrice,
        channel.billingUnit,
        channel.latency,
        channel.successRate,
        channel.maxConcurrency ?? null,
        channel.timeoutMs ?? null,
        JSON.stringify(channel.supports ?? []),
      ]
    );

    const created = mapChannel(result.rows[0]);
    await this.initialize();
    return created;
  },

  async upsertPlatformModelSchemaField(platformModelId, field) {
    const model = this.getPlatformModel(platformModelId);
    if (!model) {
      return null;
    }

    const schema = Array.isArray(model.schema) ? [...model.schema] : [];
    const index = schema.findIndex((item) => item.key === field.key);
    if (index >= 0) {
      schema[index] = { ...schema[index], ...field };
    } else {
      schema.push(field);
    }

    const db = await getDb();
    const result = await db.query(
      `update platform_models
       set schema = $2::jsonb
       where id = $1
       returning id, slug, display_name, name, short_name, modality, tier, description, use_cases, visible, recommended,
                 estimated_cost, estimated_time, sort_order, schema`,
      [platformModelId, JSON.stringify(schema)]
    );

    if (result.rowCount === 0) {
      return null;
    }

    const updated = mapPlatformModel(result.rows[0]);
    await this.initialize();
    return updated;
  },

  async upsertChannelMapping(mapping) {
    const db = await getDb();
    const result = await db.query(
      `insert into channel_parameter_mappings (
         id, channel_id, platform_param_key, upstream_param_key, transform, value_map, default_value, note
       )
       values ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8)
       on conflict (channel_id, platform_param_key)
       do update set
         upstream_param_key = excluded.upstream_param_key,
         transform = excluded.transform,
         value_map = excluded.value_map,
         default_value = excluded.default_value,
         note = excluded.note
       returning id, channel_id, platform_param_key, upstream_param_key, transform, value_map, default_value, note`,
      [
        mapping.id,
        mapping.channelId,
        mapping.platform,
        mapping.upstream ?? null,
        mapping.transform,
        JSON.stringify(mapping.valueMap ?? {}),
        mapping.defaultValue === undefined ? null : JSON.stringify(mapping.defaultValue),
        mapping.note ?? null,
      ]
    );

    const saved = mapParameterMapping(result.rows[0]);
    await this.initialize();
    return saved;
  },

  listParameterMappings() {
    return cache.parameterMappings;
  },
};

function mapProvider(row) {
  return {
    id: row.id,
    name: row.name,
    kind: row.kind,
    baseUrl: row.base_url,
    authType: row.auth_type,
    encryptedApiKey: row.encrypted_api_key,
    status: row.status,
    rpm: row.rpm,
    concurrency: row.concurrency,
    latencyMs: row.latency_ms,
    successRate: toNumber(row.success_rate),
  };
}

function mapProviderModel(row) {
  return {
    id: row.id,
    providerId: row.provider_id,
    upstreamModelName: row.upstream_model_name,
    endpointType: row.endpoint_type,
    modality: row.modality,
    status: row.status,
    rawCapabilities: parseJsonValue(row.raw_capabilities, {}),
    notes: row.notes,
  };
}

function mapPlatformModel(row) {
  return {
    id: row.id,
    slug: row.slug ?? slugify(row.id),
    displayName: row.display_name ?? row.name,
    name: row.display_name ?? row.name,
    shortName: row.short_name,
    modality: row.modality,
    tier: row.tier,
    description: row.description,
    useCases: parseJsonValue(row.use_cases, []),
    visible: row.visible,
    recommended: row.recommended,
    estimatedCost: row.estimated_cost,
    estimatedTime: row.estimated_time,
    sortOrder: row.sort_order,
    schema: parseJsonValue(row.schema, []),
  };
}

function mapModelCategory(row) {
  return {
    id: row.id,
    key: row.key,
    name: row.name,
    icon: row.icon,
    sortOrder: row.sort_order,
    visible: row.visible,
    parentId: row.parent_id,
    status: row.status,
    aliases: parseJsonValue(row.aliases, []),
  };
}

function mapCategoryAssignment(row) {
  return {
    id: row.id,
    platformModelId: row.platform_model_id,
    categoryId: row.category_id,
    sortOrder: row.sort_order,
    isPrimary: row.is_primary,
  };
}

function mapModelAlias(row) {
  return {
    id: row.id,
    platformModelId: row.platform_model_id,
    alias: row.alias,
    kind: row.kind,
  };
}

function withModelMenuMetadata(model) {
  return {
    ...model,
    categoryIds: categoriesForModel(model.id).map((category) => category.id),
    categoryKeys: categoriesForModel(model.id).map((category) => category.key),
    categories: categoriesForModel(model.id),
    aliases: cache.modelAliases.filter((alias) => alias.platformModelId === model.id).map((item) => item.alias),
  };
}

function categoriesForModel(platformModelId) {
  return cache.categoryAssignments
    .filter((assignment) => assignment.platformModelId === platformModelId)
    .map((assignment) => {
      const category = cache.modelCategories.find((item) => item.id === assignment.categoryId);
      return category
        ? {
            ...category,
            assignmentId: assignment.id,
            assignmentSortOrder: assignment.sortOrder,
            isPrimary: assignment.isPrimary,
          }
        : null;
    })
    .filter(Boolean);
}

function mapChannel(row) {
  return {
    id: row.id,
    platformModelId: row.platform_model_id,
    providerId: row.provider_id,
    providerModelId: row.provider_model_id,
    role: row.role,
    status: row.status,
    weight: row.weight,
    priority: row.priority,
    costPrice: toNumber(row.cost_price),
    salePrice: toNumber(row.sale_price),
    billingUnit: row.billing_unit,
    latency: toNumber(row.latency),
    successRate: toNumber(row.success_rate),
    maxConcurrency: row.max_concurrency,
    timeoutMs: row.timeout_ms,
    supports: parseJsonValue(row.supports, []),
  };
}

function mapParameterMapping(row) {
  return {
    id: row.id,
    channelId: row.channel_id,
    platform: row.platform_param_key,
    upstream: row.upstream_param_key,
    transform: row.transform,
    valueMap: parseJsonValue(row.value_map, {}),
    defaultValue: parseJsonValue(row.default_value, undefined),
    note: row.note,
  };
}

function parseJsonValue(value, fallback) {
  if (value === null || value === undefined) {
    return fallback;
  }

  if (typeof value === "string") {
    try {
      return JSON.parse(value);
    } catch {
      return fallback;
    }
  }

  return value;
}

function toNumber(value) {
  if (value === null || value === undefined) {
    return value;
  }
  const number = Number(value);
  return Number.isFinite(number) ? number : value;
}

function slugify(value) {
  return String(value ?? "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || "model";
}
