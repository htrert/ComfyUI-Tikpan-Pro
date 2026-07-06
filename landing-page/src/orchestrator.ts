import {
  channels,
  providers,
  type Channel,
  type PlatformModel,
  type Provider,
  type RouteMode,
  type SchemaField,
} from "./productData";

export type StudioInput = Record<string, string | number | boolean | undefined>;

export type RouteDecision = {
  channel: Channel | null;
  candidates: Channel[];
  rejected: Array<{
    channelId: string;
    providerName: string;
    reason: string;
    code?: string;
    parameters?: string[];
  }>;
  scoreBreakdown: Array<{
    channelId: string;
    providerName: string;
    score: number;
    reasons: string[];
  }>;
};

export type TaskAttempt = {
  id: string;
  provider: string;
  providerModel: string;
  channelId: string;
  status: string;
  errorCode?: string | null;
  errorMessage?: string | null;
  fallbackReason?: string | null;
  createdAt?: string;
  finishedAt?: string | null;
};

export type OrchestratedTask = {
  taskId: string;
  publicModel: string;
  status: "ready" | "blocked";
  routeMode: RouteMode;
  lifecycle?: {
    apiStatus: string;
    progress: number;
    currentStep?: string | null;
    outputUrls?: string[];
    isTerminal: boolean;
  };
  worker?: {
    workerId: string | null;
    lockedUntil: string | null;
    lockVersion: number;
  };
  userVisible: {
    estimatedCost: string;
    estimatedTime: string;
    guarantee: string;
    message: string;
  };
  internal: {
    providerName?: string;
    providerModel?: string;
    billing: {
      preAuthAmount: string;
      settlement: "success_only" | "actual_usage";
      marginHint: string;
    };
    payload?: Record<string, unknown>;
    routeReason: string;
    rejected: RouteDecision["rejected"];
    attempts?: TaskAttempt[];
  };
};

const routeModeWeights: Record<RouteMode, { quality: number; speed: number; cost: number; stable: number }> = {
  balanced: { quality: 0.28, speed: 0.24, cost: 0.2, stable: 0.28 },
  quality: { quality: 0.46, speed: 0.14, cost: 0.1, stable: 0.3 },
  fast: { quality: 0.18, speed: 0.46, cost: 0.12, stable: 0.24 },
  cheap: { quality: 0.16, speed: 0.16, cost: 0.48, stable: 0.2 },
  stable: { quality: 0.18, speed: 0.14, cost: 0.1, stable: 0.58 },
};

const routingControlInputKeys = new Set(["simulate_failover"]);

export function buildDefaultInput(schema: SchemaField[]): StudioInput {
  return schema.reduce<StudioInput>((acc, field) => {
    const configuredDefault = field.value ?? field.defaultValue;

    if (configuredDefault !== undefined) {
      acc[field.key] = configuredDefault;
      return acc;
    }

    if (field.type === "textarea" || field.type === "text") {
      acc[field.key] = "";
      return acc;
    }

    if (field.options?.[0]) {
      acc[field.key] = field.options[0].value;
    }

    return acc;
  }, {});
}

export function selectRoute(model: PlatformModel, input: StudioInput, mode: RouteMode): RouteDecision {
  return selectRouteFromChannels(model, input, mode, channels, providers);
}

export function selectRouteFromChannels(
  model: PlatformModel,
  input: StudioInput,
  mode: RouteMode,
  availableChannels: Channel[],
  availableProviders: Provider[] = providers,
): RouteDecision {
  const modelChannels = availableChannels.filter((channel) => channel.platformModelId === model.id);
  const rejected: RouteDecision["rejected"] = [];

  const candidates = modelChannels.filter((channel) => {
    const provider = availableProviders.find((item) => item.id === channel.providerId);

    if (!provider || provider.status === "testing" || provider.status === "disabled") {
      rejected.push({
        channelId: channel.id,
        providerName: provider?.name ?? "Unknown",
        reason: "供应商未启用或仍在测试",
      });
      return false;
    }

    if (channel.status === "disabled") {
      rejected.push({
        channelId: channel.id,
        providerName: provider.name,
        reason: "渠道已停用",
      });
      return false;
    }

    const unsupportedKeys = Object.entries(input)
      .filter(([key, value]) => isUserIntentInput(model, key, value))
      .map(([key]) => key)
      .filter((key) => !routingControlInputKeys.has(key))
      .filter((key) => !channel.supports.includes(key))
      .filter((key) => {
        const mapping = channel.paramMap.find((item) => item.platform === key);
        return !mappingCanCarryUserValue(mapping);
      });

    if (unsupportedKeys.length > 0) {
      rejected.push({
        channelId: channel.id,
        providerName: provider.name,
        reason: `不支持参数：${unsupportedKeys.join("、")}`,
        code: "UNSUPPORTED_PARAMETERS",
        parameters: unsupportedKeys,
      });
      return false;
    }

    return true;
  });

  const scored = candidates
    .map((channel) => {
      const provider = availableProviders.find((item) => item.id === channel.providerId);
      const weights = routeModeWeights[mode];
      const costNumber = extractNumber(channel.cost);
      const qualityScore = channel.role === "quality" || channel.role === "primary" ? 95 : 84;
      const speedScore = normalizeLowerIsBetter(channel.latency);
      const costScore = costNumber > 0 ? Math.max(30, 100 - costNumber * 80) : 70;
      const stableScore = channel.successRate;
      const degradedPenalty = channel.status === "degraded" || provider?.status === "degraded" ? 8 : 0;
      const score =
        qualityScore * weights.quality +
        speedScore * weights.speed +
        costScore * weights.cost +
        stableScore * weights.stable -
        degradedPenalty +
        channel.weight * 0.05;

      return {
        channel,
        score,
        reasons: [
          `成功率 ${channel.successRate}%`,
          `延迟 ${channel.latency}s`,
          `权重 ${channel.weight}`,
          `${provider?.status === "degraded" ? "供应商降级，已扣分" : "供应商可用"}`,
        ],
      };
    })
    .sort((a, b) => b.score - a.score);

  return {
    channel: scored[0]?.channel ?? null,
    candidates,
    rejected,
    scoreBreakdown: scored.map((item) => ({
      channelId: item.channel.id,
      providerName: availableProviders.find((provider) => provider.id === item.channel.providerId)?.name ?? "Unknown",
      score: Math.round(item.score * 10) / 10,
      reasons: item.reasons,
    })),
  };
}

export function mapInputForChannel(channel: Channel, input: StudioInput): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    model: channel.providerModel,
  };

  for (const mapping of channel.paramMap) {
    const value = input[mapping.platform];

    if (mapping.transform === "omit") {
      continue;
    }

    if (mapping.transform === "default") {
      if (hasValidUpstreamParam(mapping.upstream)) {
        payload[mapping.upstream] = mapping.defaultValue ?? "default";
      }
      continue;
    }

    if (value === undefined || value === "") {
      continue;
    }

    if (mapping.transform === "map") {
      if (hasValidUpstreamParam(mapping.upstream)) {
        payload[mapping.upstream] = mapping.valueMap?.[String(value)] ?? mapCommonValue(mapping.platform, value);
      }
      continue;
    }

    if (mapping.transform === "template") {
      if (hasValidUpstreamParam(mapping.upstream)) {
        payload[mapping.upstream] = buildTemplateValue(mapping.platform, value);
      }
      continue;
    }

    if (hasValidUpstreamParam(mapping.upstream)) {
      payload[mapping.upstream] = value;
    }
  }

  return payload;
}

export function orchestrateTask(model: PlatformModel, input: StudioInput, mode: RouteMode): OrchestratedTask {
  return orchestrateTaskWithChannels(model, input, mode, channels);
}

export function orchestrateTaskWithChannels(
  model: PlatformModel,
  input: StudioInput,
  mode: RouteMode,
  availableChannels: Channel[],
  availableProviders: Provider[] = providers,
): OrchestratedTask {
  const decision = selectRouteFromChannels(model, input, mode, availableChannels, availableProviders);
  const taskId = `task_${Math.random().toString(16).slice(2, 8)}`;

  if (!decision.channel) {
    return {
      taskId,
      publicModel: model.id,
      status: "blocked",
      routeMode: mode,
      userVisible: {
        estimatedCost: model.price,
        estimatedTime: model.eta,
        guarantee: "未扣费",
        message: "当前参数暂时没有可用生成能力，请减少高级选项或稍后再试。",
      },
      internal: {
        billing: {
          preAuthAmount: "0",
          settlement: "success_only",
          marginHint: "没有可用渠道，未进入预冻结",
        },
        routeReason: "没有渠道同时满足能力、参数和健康状态要求",
        rejected: decision.rejected,
      },
    };
  }

  const provider = availableProviders.find((item) => item.id === decision.channel?.providerId);
  const payload = mapInputForChannel(decision.channel, input);
  const sale = extractNumber(decision.channel.sale);
  const cost = extractNumber(decision.channel.cost);
  const margin = sale > 0 && cost > 0 ? `${Math.round(((sale - cost) / sale) * 100)}%` : "按实际用量结算";

  return {
    taskId,
    publicModel: model.id,
    status: "ready",
    routeMode: mode,
    userVisible: {
      estimatedCost: model.price,
      estimatedTime: model.eta,
      guarantee: "失败不扣费，成功后结算",
      message: "系统已完成智能调度，生成失败时会自动尝试可用备用能力。",
    },
    internal: {
      providerName: provider?.name,
      providerModel: decision.channel.providerModel,
      billing: {
        preAuthAmount: sale > 0 ? sale.toFixed(2) : "usage_based",
        settlement: model.modality === "chat" ? "actual_usage" : "success_only",
        marginHint: margin,
      },
      payload,
      routeReason:
        decision.scoreBreakdown[0]?.reasons.join("；") ?? "按当前路由偏好选择得分最高渠道",
      rejected: decision.rejected,
      attempts: [
        {
          id: `attempt_${taskId.slice(-6)}`,
          provider: provider?.name ?? "Unknown",
          providerModel: decision.channel.providerModel,
          channelId: decision.channel.id,
          status: "completed",
        },
      ],
    },
  };
}

function extractNumber(value: string): number {
  const match = value.match(/\d+(?:\.\d+)?/);
  return match ? Number(match[0]) : 0;
}

function isUserIntentInput(model: PlatformModel, key: string, value: string | number | boolean | undefined) {
  if (value === undefined || value === null || value === "" || value === false) {
    return false;
  }

  const field = model.schema.find((item) => item.key === key);
  const defaultValue = field?.value ?? field?.defaultValue;
  if (defaultValue !== undefined && String(defaultValue) === String(value)) {
    return false;
  }

  return true;
}

function mappingCanCarryUserValue(mapping: Channel["paramMap"][number] | undefined) {
  if (!mapping || mapping.transform === "omit" || mapping.transform === "default") {
    return false;
  }

  return hasValidUpstreamParam(mapping.upstream);
}

function hasValidUpstreamParam(value: string | null | undefined) {
  return Boolean(value && value !== "-");
}

function normalizeLowerIsBetter(value: number) {
  return Math.max(20, Math.min(100, 110 - value));
}

function mapCommonValue(key: string, value: string | number | boolean) {
  if (key === "aspect_ratio") {
    return {
      "1:1": "1024x1024",
      "3:4": "1024x1365",
      "4:3": "1365x1024",
      "16:9": "1536x864",
    }[String(value)] ?? value;
  }

  if (key === "quality") {
    return {
      fast: "standard",
      balanced: "hd",
      high: "ultra",
    }[String(value)] ?? value;
  }

  if (key === "resolution") {
    return {
      "720p": "standard",
      "1080p": "high",
    }[String(value)] ?? value;
  }

  return value;
}

function buildTemplateValue(key: string, value: string | number | boolean) {
  if (key === "message") {
    return [{ role: "user", content: value }];
  }

  if (key === "tone") {
    return `请用${value}风格回答用户。`;
  }

  return value;
}
