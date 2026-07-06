import type { OrchestratedTask, StudioInput, TaskAttempt } from "./orchestrator";
import type { Channel, FieldType, PlatformModel, Provider, ProviderModel, RouteMode, SchemaField } from "./productData";

const apiBaseUrl = import.meta.env.VITE_TIKPAN_API_URL ?? "http://localhost:8787";
const configuredAdminToken = import.meta.env.VITE_TIKPAN_ADMIN_TOKEN ?? "";

type ApiAuthOptions = {
  apiKey?: string | null;
};

type BillingPeriodQuery = {
  periodStart?: string | null;
  periodEnd?: string | null;
};

function apiHeaders(apiKey?: string | null, extra?: HeadersInit): HeadersInit {
  const headers: Record<string, string> = {};

  if (extra instanceof Headers) {
    extra.forEach((value, key) => {
      headers[key] = value;
    });
  } else if (Array.isArray(extra)) {
    extra.forEach(([key, value]) => {
      headers[key] = value;
    });
  } else if (extra) {
    Object.assign(headers, extra);
  }

  if (apiKey) {
    headers.Authorization = `Bearer ${apiKey}`;
  }

  return headers;
}

function adminHeaders(extra?: HeadersInit): HeadersInit {
  const token =
    configuredAdminToken ||
    (typeof window !== "undefined" ? window.localStorage.getItem("tikpan_admin_token") ?? "" : "");
  return apiHeaders(token, extra);
}

function billingPeriodQuery(period?: BillingPeriodQuery) {
  const params = new URLSearchParams();
  if (period?.periodStart) {
    params.set("period_start", period.periodStart);
  }
  if (period?.periodEnd) {
    params.set("period_end", period.periodEnd);
  }

  const query = params.toString();
  return query ? `?${query}` : "";
}

type ApiTaskResponse = {
  data: RemoteTaskRecord;
};

type ApiTaskBatchResponse = {
  data: RemoteTaskBatch;
};

type ApiTaskBatchesResponse = {
  data: RemoteTaskBatch[];
};

type TaskQuoteResponse = {
  data: TaskQuote;
};

type RoutePreviewResponse = {
  data: RoutePreviewResult;
};

type ChannelTestResponse = {
  data: ChannelTestResult;
};

export type RemoteTaskRecord = {
  task_id: string;
  model: string;
  status: string;
  batch_id?: string | null;
  batch_title?: string | null;
  batch_item_id?: string | null;
  project_id?: string | null;
  project_name?: string | null;
  input?: StudioInput;
  route_mode?: RouteMode;
  progress?: number;
  current_step?: string | null;
  estimated_cost?: number | string;
  final_cost?: number | string | null;
  estimated_time?: string;
  guarantee?: string;
  message?: string;
  output?: {
    publicUrls?: string[];
    public_urls?: string[];
  } | null;
  error?: {
    code: string;
    message: string;
  } | null;
  attempts?: Array<{
    id: string;
    provider: string;
    provider_model: string;
    channel_id: string;
    status: string;
    error_code?: string | null;
    error_message?: string | null;
    fallback_reason?: string | null;
    created_at?: string;
    finished_at?: string | null;
  }>;
  worker?: {
    worker_id: string | null;
    locked_until: string | null;
    lock_version: number;
  };
  created_at?: string;
  finished_at?: string | null;
  internal?: {
    provider?: string;
    provider_model?: string;
    mapped_payload?: Record<string, unknown>;
    route_score?: Array<{
      reasons?: string[];
    }>;
    rejected?: Array<{
      channelId: string;
      providerName: string;
      reason: string;
      code?: string;
      parameters?: string[];
    }>;
  };
};

export type RemoteTaskBatchItem = {
  id: string;
  status: "created" | "failed";
  task?: RemoteTaskRecord;
  error?: ProblemDetails;
};

export type RemoteTaskBatch = {
  batch_id: string;
  title: string;
  status: "created" | "partial" | "failed" | "running" | "completed";
  task_count?: number;
  created_count: number;
  failed_count: number;
  completed_count?: number;
  active_count?: number;
  estimated_cost?: number;
  final_cost?: number;
  created_at?: string | null;
  updated_at?: string | null;
  items: RemoteTaskBatchItem[];
};

export type RemoteTaskBatchInputItem = {
  id?: string;
  model: PlatformModel;
  input: StudioInput;
  routeMode: RouteMode;
};

export type RemoteTaskBatchResult = {
  batch: RemoteTaskBatch;
  tasks: OrchestratedTask[];
};

type AdminTasksResponse = {
  data: RemoteTaskRecord[];
};

type AnalyticsSummaryResponse = {
  data: AnalyticsSummary;
};

type CommercialReadinessResponse = {
  data: CommercialReadinessSummary;
};

type CustomersSummaryResponse = {
  data: CustomersSummary;
};

type BillingTransactionsResponse = {
  data: BillingTransactionsSummary;
};

type BillingInvoicesResponse = {
  data: BillingInvoicesSummary;
};

type WebhookEndpointsResponse = {
  data: WebhookEndpoint[];
};

type WebhookDeliveriesResponse = {
  data: WebhookDelivery[];
};

type AuditLogsResponse = {
  data: AuditLog[];
};

type PlatformUsersResponse = {
  data: PlatformUser[];
};

type UserConsoleProfileResponse = {
  data: UserConsoleProfile;
};

type PaymentOrdersResponse = {
  data: PaymentOrder[];
};

type PaymentProvidersResponse = {
  data: PaymentProvider[];
};

type PaymentProviderResponse = {
  data: PaymentProvider;
};

type PaymentOrderResponse = {
  data: PaymentOrder;
};

type CreativePresetsResponse = {
  data: CreativePreset[];
};

type CreativePresetResponse = {
  data: CreativePreset;
};

type GenerationAssetsResponse = {
  data: GenerationAsset[];
};

type GenerationAssetResponse = {
  data: GenerationAsset;
};

type CreativeProjectsResponse = {
  data: CreativeProject[];
};

type CreativeProjectResponse = {
  data: CreativeProject;
};

type PaymentOrderConfirmResponse = {
  data: PaymentOrderConfirmResult;
};

type ProblemDetails = {
  title?: string;
  status?: number;
  code?: string;
  detail?: string;
  errors?: Array<{ field?: string; message?: string }>;
  usage?: UsageSummary;
};

export type WalletSnapshot = {
  user_id: string;
  currency: string;
  balance: number;
  frozen: number;
  available: number;
  updated_at: string;
};

export type WalletLedgerItem = {
  id: string;
  user_id: string;
  task_id: string | null;
  type: "top_up" | "gift" | "pre_authorize" | "settle" | "release" | "refund" | "admin_adjust";
  amount: number;
  balance_after: number;
  frozen_after: number;
  note: string;
  created_at: string;
};

export type PlatformApiKey = {
  id: string;
  user_id: string;
  name: string;
  prefix: string;
  masked: string;
  secret?: string;
  status: "active" | "revoked";
  scopes: string[];
  last_used_at: string | null;
  created_at: string;
  revoked_at: string | null;
};

export type UsageSummary = {
  user_id: string;
  period_start: string;
  period_end: string;
  subscription: {
    plan_id: string;
    plan_name: string;
    status: string;
    renews_at: string;
  };
  limits: {
    monthly_tasks: number;
    monthly_spend: number;
    rate_limit_per_minute: number;
    concurrency: number;
  };
  usage: {
    tasks_created: number;
    tasks_completed: number;
    active_tasks: number;
    settled_amount: number;
    frozen_amount: number;
    projected_spend: number;
  };
  remaining: {
    tasks: number;
    spend: number;
    concurrency: number;
  };
};

export type AnalyticsSummary = {
  summary: {
    tasks_total: number;
    tasks_completed: number;
    tasks_failed: number;
    tasks_active: number;
    revenue: number;
    cost: number;
    gross_profit: number;
    gross_margin: number;
  };
  by_model: AnalyticsGroup[];
  by_provider: AnalyticsGroup[];
  reliability: {
    success_rate: number;
    failure_rate: number;
    active_rate: number;
  };
  error_codes: AnalyticsErrorCode[];
  provider_health: AnalyticsProviderHealth[];
};

export type AnalyticsGroup = {
  key: string;
  tasks_total: number;
  tasks_completed: number;
  tasks_failed: number;
  revenue: number;
  cost: number;
  gross_profit: number;
  gross_margin: number;
};

export type AnalyticsErrorCode = {
  code: string;
  count: number;
  task_ids: string[];
  latest_message: string;
};

export type AnalyticsProviderHealth = {
  provider: string;
  attempts_total: number;
  attempts_completed: number;
  attempts_failed: number;
  success_rate: number;
  failure_rate: number;
  cost: number;
};

export type CommercialReadinessSummary = {
  generated_at: string;
  summary: {
    models_total: number;
    sellable_models: number;
    watch_models: number;
    blocked_models: number;
    total_channels: number;
    active_channels: number;
    average_gross_margin: number;
  };
  items: CommercialReadinessItem[];
  priority_actions: Array<{
    model_id: string;
    model_name: string;
    status: CommercialReadinessItem["status"];
    action: string;
  }>;
};

export type CommercialReadinessItem = {
  model: {
    id: string;
    name: string;
    short_name?: string;
    modality: PlatformModel["modality"];
    tier: PlatformModel["tier"];
    recommended: boolean;
  };
  status: "sellable" | "watch" | "blocked";
  summary: string;
  pricing: {
    cost_price: number;
    sale_price: number;
    gross_margin: number;
  };
  route: {
    total_channels: number;
    active_channels: number;
    backup_channels: number;
    success_rate: number;
    latency_ms: number;
    providers: Array<{
      id: string;
      name: string;
      status: Provider["status"];
      success_rate: number;
    }>;
  };
  schema: {
    total_fields: number;
    covered_fields: number;
    coverage: number;
    missing_fields: string[];
  };
  actions: string[];
};

export type CustomersSummary = {
  summary: {
    users_total: number;
    active_subscriptions: number;
    active_api_keys: number;
    total_balance: number;
    total_revenue: number;
  };
  customers: CustomerSummary[];
};

export type CustomerSummary = {
  user_id: string;
  plan_id: string | null;
  plan_name: string;
  subscription_status: string;
  renews_at: string | null;
  wallet: WalletSnapshot;
  api_keys_total: number;
  api_keys_active: number;
  last_active_at: string | null;
  tasks_total: number;
  tasks_completed: number;
  tasks_failed: number;
  tasks_active: number;
  revenue: number;
  frozen_amount: number;
  ledger_total: number;
};

export type BillingTransactionsSummary = {
  summary: {
    transactions_total: number;
    settled_total: number;
    released_total: number;
    refunded_total: number;
    revenue: number;
    cost: number;
    gross_profit: number;
  };
  transactions: BillingTransaction[];
};

export type BillingTransaction = {
  transaction_id: string;
  task_id: string;
  user_id: string;
  model: string;
  provider: string | null;
  status: "settled" | "released" | "refunded";
  revenue: number;
  cost: number;
  refund_amount: number;
  gross_profit: number;
  gross_margin: number;
  ledger_entries: WalletLedgerItem[];
  ledger_entry_count: number;
  created_at: string;
  settled_at: string | null;
};

export type BillingInvoicesSummary = {
  period: {
    start: string;
    end: string;
  };
  summary: {
    invoices_total: number;
    tasks_total: number;
    settled_total: number;
    released_total: number;
    refunded_total: number;
    revenue: number;
    refunds: number;
    cost: number;
    gross_profit: number;
    net_amount_due: number;
  };
  invoices: BillingInvoice[];
};

export type BillingInvoice = {
  invoice_id: string;
  user_id: string;
  period_start: string;
  period_end: string;
  currency: string;
  status: "open" | "paid" | "void" | string;
  tasks_total: number;
  settled_total: number;
  released_total: number;
  refunded_total: number;
  revenue: number;
  refunds: number;
  cost: number;
  gross_profit: number;
  net_amount_due: number;
  transaction_count: number;
  transactions: BillingTransaction[];
};

export type PaymentOrder = {
  id: string;
  user_id: string;
  amount: number;
  currency: string;
  provider: string;
  status: "pending" | "paid" | "cancelled" | "expired";
  idempotency_key: string | null;
  provider_transaction_id: string | null;
  paid_at: string | null;
  credited_ledger_id: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type PaymentProvider = {
  id: string;
  name: string;
  kind: "mock" | "manual" | "alipay" | "wechat" | "stripe" | "custom";
  status: "active" | "testing" | "disabled";
  currencies: string[];
  fee_rate: number;
  fixed_fee: number;
  min_amount: number;
  max_amount: number;
  checkout_mode: "mock" | "hosted" | "qr_code" | "manual" | "redirect";
  webhook_secret_set?: boolean;
  sort_order?: number;
  metadata: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
};

export type PaymentProviderUpsert = {
  id?: string;
  name: string;
  kind: PaymentProvider["kind"];
  status: PaymentProvider["status"];
  currencies: string[];
  fee_rate: number;
  fixed_fee: number;
  min_amount: number;
  max_amount: number;
  checkout_mode: PaymentProvider["checkout_mode"];
  webhook_secret?: string | null;
  sort_order: number;
  metadata?: Record<string, unknown>;
};

export type PaymentOrderConfirmResult = {
  order: PaymentOrder;
  wallet: WalletSnapshot;
  ledger: WalletLedgerItem[];
  idempotent: boolean;
};

export type BillingRefundResult = {
  task: RemoteTaskRecord;
  wallet: WalletSnapshot;
  refund_amount: number;
  transaction: BillingTransaction;
};

export type WebhookEndpoint = {
  id: string;
  user_id: string;
  url: string;
  events: string[];
  status: "active" | "disabled";
  secret_set: boolean;
  created_at: string;
  updated_at: string;
};

export type WebhookDelivery = {
  id: string;
  endpoint_id: string;
  user_id: string;
  task_id: string;
  event: string;
  target_url: string;
  status: "delivered" | "failed" | "pending";
  response_status: number | null;
  attempt: number;
  payload: Record<string, unknown>;
  error_message: string | null;
  created_at: string;
  delivered_at: string | null;
};

export type WebhookEndpointUpsert = {
  id?: string;
  user_id: string;
  url: string;
  events: string[];
  status: WebhookEndpoint["status"];
  secret?: string;
};

export type AuditLog = {
  id: string;
  actor_id: string;
  actor_type: "admin" | "user" | "system" | string;
  action: string;
  resource_type: string;
  resource_id: string;
  user_id: string | null;
  summary: string;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type PlatformUser = {
  id: string;
  display_name: string;
  email: string | null;
  status: "active" | "suspended" | "deleted";
  created_at: string;
  updated_at: string;
  subscription?: UserSubscription | null;
};

export type BillingPlan = {
  id: string;
  name: string;
  monthlyTaskLimit: number;
  monthlySpendLimit: number;
  rateLimitPerMinute: number;
  concurrencyLimit: number;
  features: string[];
  status: "active" | "archived";
};

export type UserSubscription = {
  id?: string;
  userId: string;
  planId: string;
  status: "trialing" | "active" | "past_due" | "cancelled" | "expired";
  renewsAt: string | null;
  cancelledAt?: string | null;
};

export type ChannelTestResult = {
  channel: {
    id: string;
    status: Channel["status"];
    role: Channel["role"];
    billing_unit?: string;
  };
  provider: {
    id: string;
    name: string;
    status: string;
  } | null;
  provider_model: {
    id: string;
    upstream_model_name: string;
    endpoint_type?: string;
    modality?: string;
  } | null;
  platform_input: Record<string, unknown>;
  mapped_payload: Record<string, unknown>;
  checks: Array<{
    level: "ok" | "warning" | "error";
    code: string;
    message: string;
  }>;
};

export type BillingPlanUpsert = {
  id?: string;
  name: string;
  monthly_task_limit: number;
  monthly_spend_limit: number;
  rate_limit_per_minute: number;
  concurrency_limit: number;
  features: string[];
  status: BillingPlan["status"];
};

export type UserSubscriptionUpsert = {
  id?: string;
  user_id: string;
  plan_id: string;
  status: UserSubscription["status"];
  renews_at?: string | null;
  cancelled_at?: string | null;
};

export type PlatformUserUpsert = {
  id?: string;
  display_name: string;
  email?: string | null;
  status: PlatformUser["status"];
  plan_id?: string;
  subscription_status?: UserSubscription["status"];
  renews_at?: string | null;
};

export type UserConsoleProfile = {
  user: PlatformUser;
  subscription: RemoteUserSubscriptionRecord | UserSubscription | null;
  plan: RemoteBillingPlanRecord | BillingPlan | null;
  wallet: WalletSnapshot;
  ledger: WalletLedgerItem[];
  payment_orders?: PaymentOrder[];
  presets?: CreativePreset[];
  tasks: RemoteTaskRecord[];
  api_key?: PlatformApiKey;
};

export type CreativePreset = {
  id: string;
  user_id: string;
  name: string;
  description: string;
  model: string;
  route_mode: RouteMode;
  input: StudioInput;
  usage_count: number;
  last_used_at: string | null;
  created_at: string;
  updated_at: string;
};

export type CreativePresetInput = {
  id?: string;
  name: string;
  description?: string;
  model: string;
  route_mode: RouteMode;
  input: StudioInput;
};

export type GenerationAsset = {
  id: string;
  task_id: string;
  project_id?: string | null;
  project_name?: string | null;
  model: string;
  model_name: string;
  modality: PlatformModel["modality"];
  status: string;
  route_mode: RouteMode;
  title: string;
  note: string;
  favorite: boolean;
  review_status: "candidate" | "approved" | "needs_changes" | "archived";
  tags: string[];
  collections: string[];
  prompt: string;
  input: StudioInput;
  output_urls: string[];
  media_assets: Array<{
    id: string;
    object_key: string;
    public_url: string | null;
    mime_type: string;
    source_url: string | null;
    storage_mode: string;
    direction: string;
    created_at: string;
  }>;
  final_cost: number | string;
  created_at: string;
  finished_at: string | null;
};

export type GenerationAssetPatch = {
  title?: string;
  note?: string;
  favorite?: boolean;
  review_status?: GenerationAsset["review_status"];
  tags?: string[];
  collections?: string[];
};

export type ManualProjectAssetInput = {
  title: string;
  source_url: string;
  mime_type: string;
  tags?: string[];
  note?: string;
};

export type CreativeProjectStats = {
  tasks_total: number;
  tasks_completed: number;
  tasks_failed: number;
  tasks_active: number;
  assets_total: number;
  token_spend: number;
};

export type CreativeProject = {
  id: string;
  user_id: string;
  name: string;
  type: "general" | "image_campaign" | "video_storyboard" | "audio_album" | "agent_workspace";
  status: "draft" | "active" | "archived";
  description: string;
  cover_url: string | null;
  tags: string[];
  settings: Record<string, unknown>;
  stats: CreativeProjectStats;
  tasks?: RemoteTaskRecord[];
  assets?: GenerationAsset[];
  created_at: string;
  updated_at: string;
  archived_at: string | null;
};

export type CreativeProjectInput = {
  id?: string;
  name: string;
  type?: CreativeProject["type"];
  status?: CreativeProject["status"];
  description?: string;
  cover_url?: string | null;
  tags?: string[];
  settings?: Record<string, unknown>;
};

export type UserSessionInput = {
  user_id: string;
  display_name?: string;
  email?: string;
  plan_id?: string;
};

export type RoutePreviewResult = {
  channel: {
    id: string;
    role: Channel["role"];
    status: Channel["status"];
    weight: number;
    cost_price: number;
    sale_price: number;
    latency: number;
    success_rate: number;
  } | null;
  provider: {
    id: string;
    name: string;
    status: string;
  } | null;
  provider_model: {
    id: string;
    upstream_model_name: string;
  } | null;
  mapped_payload: Record<string, unknown> | null;
  score_breakdown: Array<{
    channelId: string;
    providerName: string;
    score: number;
    reasons: string[];
  }>;
  rejected: Array<{
    channelId: string;
    providerName: string;
    reason: string;
    code?: string;
    parameters?: string[];
  }>;
};

export type TaskQuoteBlocker = {
  code: string;
  severity: "error" | "warning" | string;
  message: string;
  required_amount?: number;
  available_amount?: number;
  remaining_amount?: number;
};

export type TaskQuote = {
  model: string;
  route_mode: RouteMode;
  allowed: boolean;
  blockers: TaskQuoteBlocker[];
  estimated_cost: number;
  estimated_time: string;
  guarantee: string;
  message: string;
  wallet: WalletSnapshot;
  usage: UsageSummary;
  route: RoutePreviewResult;
};

type WalletResponse = {
  data: {
    wallet: WalletSnapshot;
    ledger: WalletLedgerItem[];
  };
};

type AdminChannelResponse = {
  data: {
    id: string;
    platformModelId: string;
    providerId: string;
    providerModelId?: string;
    status: Channel["status"];
    role: Channel["role"];
    weight: number;
    costPrice: number;
    salePrice: number;
    latency: number;
    successRate: number;
    supports?: string[];
    parameter_mappings?: Array<{
      platform: string;
      upstream: string | null;
      transform: "direct" | "map" | "default" | "omit" | "template";
      valueMap?: Record<string, unknown>;
      defaultValue?: unknown;
      value_map?: Record<string, unknown>;
      default_value?: unknown;
      note?: string | null;
    }>;
    provider?: {
      id: string;
      name: string;
    };
    provider_model?: {
      upstreamModelName: string;
    };
  };
};

type AdminChannelsResponse = {
  data: AdminChannelResponse["data"][];
};

type AdminPlatformModelResponse = {
  data: RemotePlatformModelRecord;
};

type RemotePlatformModelRecord = {
  id: string;
  slug?: string;
  display_name?: string;
  displayName?: string;
  name: string;
  short_name?: string;
  shortName?: string;
  modality: PlatformModel["modality"];
  tier: PlatformModel["tier"];
  description?: string;
  use_cases?: string[];
  useCases?: string[];
  recommended?: boolean;
  estimated_cost?: string;
  estimatedCost?: string;
  estimated_time?: string;
  estimatedTime?: string;
  schema?: SchemaField[];
  category_ids?: string[];
  categoryIds?: string[];
  category_keys?: string[];
  categoryKeys?: string[];
  aliases?: string[];
};

type PlatformModelsResponse = {
  data: RemotePlatformModelRecord[];
};

type RemoteModelCategoryRecord = {
  id: string;
  key: string;
  name: string;
  icon?: string | null;
  sort_order?: number;
  visible?: boolean;
  parent_id?: string | null;
  aliases?: string[];
};

type PublicCapabilitiesResponse = {
  data:
    | RemotePlatformModelRecord[]
    | {
        categories?: RemoteModelCategoryRecord[];
        models?: RemotePlatformModelRecord[];
      };
};

type PublicModelSchemaResponse = {
  data: {
    model: string;
    schema: SchemaField[];
  };
};

export type PlatformModelUpsert = {
  id?: string;
  slug?: string;
  display_name?: string;
  name: string;
  short_name: string;
  modality: PlatformModel["modality"];
  tier: PlatformModel["tier"];
  description: string;
  use_cases: string[];
  visible: boolean;
  recommended: boolean;
  estimated_cost: string;
  estimated_time: string;
  sort_order: number;
  schema?: SchemaField[];
};

type RemoteProviderRecord = {
  id: string;
  name: string;
  kind: Provider["kind"];
  status: Provider["status"];
  baseUrl?: string;
  base_url?: string;
  latency?: number;
  latency_ms?: number;
  successRate?: number;
  success_rate?: number;
  rpm?: number;
  concurrency?: number;
};

type ProvidersResponse = {
  data: RemoteProviderRecord[];
};

type ProviderResponse = {
  data: RemoteProviderRecord;
};

type RemoteProviderModelRecord = {
  id: string;
  providerId?: string;
  provider_id?: string;
  upstreamModelName?: string;
  upstream_model_name?: string;
  endpointType?: string;
  endpoint_type?: string;
  modality: ProviderModel["modality"];
  status: ProviderModel["status"];
  rawCapabilities?: Record<string, unknown>;
  raw_capabilities?: Record<string, unknown>;
  notes?: string | null;
};

type ProviderModelsResponse = {
  data: RemoteProviderModelRecord[];
};

type ProviderModelResponse = {
  data: RemoteProviderModelRecord;
};

export type ProviderUpsert = {
  id?: string;
  name: string;
  kind: Provider["kind"];
  status: Provider["status"];
  base_url: string;
  auth_type: "bearer" | "custom_header" | "none";
  encrypted_api_key?: string | null;
  rpm: number;
  concurrency: number;
  latency_ms: number;
  success_rate: number;
};

export type ProviderModelUpsert = {
  id?: string;
  provider_id: string;
  upstream_model_name: string;
  endpoint_type: string;
  modality: ProviderModel["modality"];
  status: ProviderModel["status"];
  raw_capabilities?: Record<string, unknown>;
  notes?: string | null;
};

export type ChannelCreate = {
  platform_model_id: string;
  provider_id: string;
  provider_model_id: string;
  role?: Channel["role"];
  status?: Channel["status"];
  weight?: number;
  priority?: number;
  cost_price?: number;
  sale_price?: number;
  billing_unit?: string;
  latency?: number;
  success_rate?: number;
  supports?: string[];
};

export type ChannelMappingUpsert = {
  platform_param_key: string;
  upstream_param_key?: string | null;
  transform: "direct" | "map" | "default" | "omit" | "template";
  note?: string | null;
  value_map?: Record<string, unknown>;
  default_value?: unknown;
};

export type SchemaFieldUpsert = {
  key: string;
  label: string;
  type: FieldType;
  required?: boolean;
  advanced?: boolean;
  placeholder?: string;
  options?: Array<{ label: string; value: string }> | string[];
  min?: number;
  max?: number;
  step?: number;
  default_value?: string | number | boolean;
};

type ApiKeysResponse = {
  data: PlatformApiKey[];
};

type ApiKeyResponse = {
  data: PlatformApiKey;
};

type UsageResponse = {
  data: UsageSummary;
};

type BillingPlansResponse = {
  data: RemoteBillingPlanRecord[];
};

type BillingPlanResponse = {
  data: RemoteBillingPlanRecord;
};

type UserSubscriptionsResponse = {
  data: RemoteUserSubscriptionRecord[];
};

type UserSubscriptionChangeResponse = {
  data: {
    subscription: RemoteUserSubscriptionRecord;
    plan: RemoteBillingPlanRecord;
    usage: UsageSummary;
  };
};

type UserSubscriptionResponse = {
  data: RemoteUserSubscriptionRecord;
};

type RemoteBillingPlanRecord = {
  id: string;
  name: string;
  monthlyTaskLimit?: number;
  monthly_task_limit?: number;
  monthlySpendLimit?: number;
  monthly_spend_limit?: number;
  rateLimitPerMinute?: number;
  rate_limit_per_minute?: number;
  concurrencyLimit?: number;
  concurrency_limit?: number;
  features?: string[];
  status: BillingPlan["status"];
};

type RemoteUserSubscriptionRecord = {
  id?: string;
  userId?: string;
  user_id?: string;
  planId?: string;
  plan_id?: string;
  status: UserSubscription["status"];
  renewsAt?: string | null;
  renews_at?: string | null;
  cancelledAt?: string | null;
  cancelled_at?: string | null;
};

export type PlatformRuntimeHealth = {
  status: string;
  repository: {
    store_mode: "memory" | "postgres";
    admin_auth_required: boolean;
    database_configured: boolean;
    database_required: boolean;
    provider_adapter_mode: "mock" | "http";
    storage_adapter_mode: "local" | "s3";
    active_repository: string;
    postgres_catalog_ready: boolean;
    postgres_billing_ready: boolean;
    postgres_tasks_ready: boolean;
    postgres_api_keys_ready: boolean;
    postgres_usage_ready: boolean;
    postgres_media_ready: boolean;
    storage?: {
      mode: "local" | "s3";
      ready: boolean;
      public_base_url: string;
      object_storage_configured: boolean;
      max_remote_asset_bytes: number;
    };
    message: string;
  };
  database?: {
    ok: boolean;
    mode: string;
    connected: boolean;
    message: string;
  };
  worker?: {
    enabled: boolean;
    running: boolean;
    worker_id: string;
    poll_interval_ms: number;
    lock_ttl_ms: number;
    tick_count: number;
    completed_count: number;
    last_error: {
      message: string;
      code: string;
      at: string;
    } | null;
  };
  providers?: number;
  platform_models?: number;
  tasks?: number;
};

type HealthResponse = {
  data: PlatformRuntimeHealth;
};

export type ChannelPatch = {
  status?: Channel["status"];
  role?: Channel["role"];
  weight?: number;
  priority?: number;
  cost_price?: number;
  sale_price?: number;
};

export async function quoteRemoteTask({
  model,
  input,
  routeMode,
  apiKey,
}: {
  model: PlatformModel;
  input: StudioInput;
  routeMode: RouteMode;
  apiKey?: string | null;
}): Promise<TaskQuote> {
  const response = await fetch(`${apiBaseUrl}/v1/tasks/quote`, {
    method: "POST",
    headers: apiHeaders(apiKey, {
      "Content-Type": "application/json",
    }),
    body: JSON.stringify({
      model: model.id,
      input,
      routing: {
        mode: routeMode,
      },
    }),
  });

  const payload = (await response.json()) as TaskQuoteResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as TaskQuoteResponse).data;
}

export async function createRemoteTask({
  model,
  input,
  projectId,
  routeMode,
  apiKey,
}: {
  model: PlatformModel;
  input: StudioInput;
  projectId?: string | null;
  routeMode: RouteMode;
  apiKey?: string | null;
}): Promise<OrchestratedTask> {
  const response = await fetch(`${apiBaseUrl}/v1/tasks`, {
    method: "POST",
    headers: apiHeaders(apiKey, {
      "Content-Type": "application/json",
    }),
    body: JSON.stringify({
      model: model.id,
      input,
      project_id: projectId || undefined,
      routing: {
        mode: routeMode,
      },
    }),
  });

  const payload = (await response.json()) as ApiTaskResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return mapApiTaskToPreview(payload as ApiTaskResponse, model, routeMode);
}

export async function createRemoteTaskBatch({
  apiKey,
  items,
  projectId,
  title,
}: {
  apiKey?: string | null;
  items: RemoteTaskBatchInputItem[];
  projectId?: string | null;
  title?: string;
}): Promise<RemoteTaskBatchResult> {
  const response = await fetch(`${apiBaseUrl}/v1/task-batches`, {
    method: "POST",
    headers: apiHeaders(apiKey, {
      "Content-Type": "application/json",
    }),
    body: JSON.stringify({
      title,
      project_id: projectId || undefined,
      items: items.map((item) => ({
        id: item.id,
        model: item.model.id,
        input: item.input,
        routing: {
          mode: item.routeMode,
        },
      })),
    }),
  });

  const payload = (await response.json()) as ApiTaskBatchResponse | ProblemDetails;

  if (!response.ok && !("data" in payload)) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  const batch = (payload as ApiTaskBatchResponse).data;
  return {
    batch,
    tasks: batch.items
      .map((item) => {
        if (!item.task) {
          return null;
        }
        const source = items.find((inputItem) => (inputItem.id ?? "") === item.id);
        const model = source?.model ?? items.find((inputItem) => inputItem.model.id === item.task?.model)?.model;
        if (!model) {
          return null;
        }
        return mapApiTaskToPreview({ data: item.task }, model, item.task.route_mode ?? source?.routeMode ?? "balanced");
      })
      .filter((task): task is OrchestratedTask => Boolean(task)),
  };
}

export async function getRemoteTask({
  taskId,
  model,
  routeMode,
  previousTask,
  apiKey,
}: {
  taskId: string;
  model: PlatformModel;
  routeMode: RouteMode;
  previousTask: OrchestratedTask;
  apiKey?: string | null;
}): Promise<OrchestratedTask> {
  const response = await fetch(`${apiBaseUrl}/v1/tasks/${taskId}`, {
    headers: apiHeaders(apiKey),
  });
  const payload = (await response.json()) as ApiTaskResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return mapApiTaskToPreview(payload as ApiTaskResponse, model, routeMode, previousTask);
}

export async function cancelRemoteTask({
  taskId,
  model,
  routeMode,
  previousTask,
  reason = "Task cancelled by user.",
  apiKey,
}: {
  taskId: string;
  model: PlatformModel;
  routeMode: RouteMode;
  previousTask: OrchestratedTask;
  reason?: string;
  apiKey?: string | null;
}): Promise<OrchestratedTask> {
  const response = await fetch(`${apiBaseUrl}/v1/tasks/${taskId}/cancel`, {
    method: "POST",
    headers: apiHeaders(apiKey, {
      "Content-Type": "application/json",
    }),
    body: JSON.stringify({ reason }),
  });
  const payload = (await response.json()) as ApiTaskResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return mapApiTaskToPreview(payload as ApiTaskResponse, model, routeMode, previousTask);
}

export async function retryRemoteTask({
  taskId,
  model,
  routeMode,
  apiKey,
}: {
  taskId: string;
  model: PlatformModel;
  routeMode: RouteMode;
  apiKey?: string | null;
}): Promise<OrchestratedTask> {
  const response = await fetch(`${apiBaseUrl}/v1/tasks/${taskId}/retry`, {
    method: "POST",
    headers: apiHeaders(apiKey),
  });
  const payload = (await response.json()) as ApiTaskResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return mapApiTaskToPreview(payload as ApiTaskResponse, model, routeMode);
}

export function getApiBaseUrl() {
  return apiBaseUrl;
}

export async function registerRemoteUserSession(input: UserSessionInput): Promise<UserConsoleProfile> {
  const response = await fetch(`${apiBaseUrl}/v1/auth/register`, {
    method: "POST",
    headers: apiHeaders(null, {
      "Content-Type": "application/json",
    }),
    body: JSON.stringify({
      user_id: input.user_id,
      id: input.user_id,
      display_name: input.display_name,
      email: input.email,
      plan_id: input.plan_id,
    }),
  });
  const payload = (await response.json()) as UserConsoleProfileResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as UserConsoleProfileResponse).data;
}

export async function loginRemoteUserSession(input: UserSessionInput): Promise<UserConsoleProfile> {
  const response = await fetch(`${apiBaseUrl}/v1/auth/login`, {
    method: "POST",
    headers: apiHeaders(null, {
      "Content-Type": "application/json",
    }),
    body: JSON.stringify({
      user_id: input.user_id,
      email: input.email,
    }),
  });
  const payload = (await response.json()) as UserConsoleProfileResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as UserConsoleProfileResponse).data;
}

export async function getRemoteMe(options: ApiAuthOptions = {}): Promise<UserConsoleProfile> {
  const response = await fetch(`${apiBaseUrl}/v1/me`, {
    headers: apiHeaders(options.apiKey),
  });
  const payload = (await response.json()) as UserConsoleProfileResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as UserConsoleProfileResponse).data;
}

export async function listRemotePresets(limit = 50, options: ApiAuthOptions = {}): Promise<CreativePreset[]> {
  const response = await fetch(`${apiBaseUrl}/v1/presets?limit=${encodeURIComponent(String(limit))}`, {
    headers: apiHeaders(options.apiKey),
  });
  const payload = (await response.json()) as CreativePresetsResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as CreativePresetsResponse).data;
}

export async function saveRemotePreset(
  input: CreativePresetInput,
  options: ApiAuthOptions = {},
): Promise<CreativePreset> {
  const response = await fetch(
    input.id ? `${apiBaseUrl}/v1/presets/${encodeURIComponent(input.id)}` : `${apiBaseUrl}/v1/presets`,
    {
      method: input.id ? "PATCH" : "POST",
      headers: apiHeaders(options.apiKey, {
        "Content-Type": "application/json",
      }),
      body: JSON.stringify(input),
    },
  );
  const payload = (await response.json()) as CreativePresetResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as CreativePresetResponse).data;
}

export async function useRemotePreset(presetId: string, options: ApiAuthOptions = {}): Promise<CreativePreset> {
  const response = await fetch(`${apiBaseUrl}/v1/presets/${encodeURIComponent(presetId)}/use`, {
    method: "POST",
    headers: apiHeaders(options.apiKey),
  });
  const payload = (await response.json()) as CreativePresetResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as CreativePresetResponse).data;
}

export async function deleteRemotePreset(presetId: string, options: ApiAuthOptions = {}): Promise<void> {
  const response = await fetch(`${apiBaseUrl}/v1/presets/${encodeURIComponent(presetId)}`, {
    method: "DELETE",
    headers: apiHeaders(options.apiKey),
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as ProblemDetails;
    throw new Error(formatProblem(payload));
  }
}

export async function previewRemoteRoute({
  model,
  input,
  routeMode,
}: {
  model: PlatformModel;
  input: StudioInput;
  routeMode: RouteMode;
}): Promise<RoutePreviewResult> {
  const response = await fetch(`${apiBaseUrl}/v1/routes/preview`, {
    method: "POST",
    headers: apiHeaders(null, {
      "Content-Type": "application/json",
    }),
    body: JSON.stringify({
      model: model.id,
      input,
      routing: {
        mode: routeMode,
      },
    }),
  });
  const payload = (await response.json()) as RoutePreviewResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as RoutePreviewResponse).data;
}

export async function testRemoteChannel(channelId: string, input: StudioInput): Promise<ChannelTestResult> {
  const response = await fetch(`${apiBaseUrl}/admin/channels/${encodeURIComponent(channelId)}/test`, {
    method: "POST",
    headers: adminHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify({ input }),
  });
  const payload = (await response.json()) as ChannelTestResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as ChannelTestResponse).data;
}

export async function getRemoteHealth(): Promise<PlatformRuntimeHealth> {
  const response = await fetch(`${apiBaseUrl}/health/readiness`);
  const payload = (await response.json()) as HealthResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as HealthResponse).data;
}

export async function getRemoteWallet(options: ApiAuthOptions = {}): Promise<WalletResponse["data"]> {
  const response = await fetch(`${apiBaseUrl}/v1/wallet`, {
    headers: apiHeaders(options.apiKey),
  });
  const payload = (await response.json()) as WalletResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as WalletResponse).data;
}

export async function getAdminWallet(userId = "demo_user"): Promise<WalletResponse["data"]> {
  const response = await fetch(`${apiBaseUrl}/admin/wallet?user_id=${encodeURIComponent(userId)}`, {
    headers: adminHeaders(),
  });
  const payload = (await response.json()) as WalletResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as WalletResponse).data;
}

export async function getRemoteUsage(options: ApiAuthOptions = {}): Promise<UsageSummary> {
  const response = await fetch(`${apiBaseUrl}/v1/usage`, {
    headers: apiHeaders(options.apiKey),
  });
  const payload = (await response.json()) as UsageResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as UsageResponse).data;
}

export async function listRemoteBillingPlans(): Promise<BillingPlan[]> {
  const response = await fetch(`${apiBaseUrl}/admin/billing-plans`, {
    headers: adminHeaders(),
  });
  const payload = (await response.json()) as BillingPlansResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as BillingPlansResponse).data.map(mapRemoteBillingPlan);
}

export async function listPublicBillingPlans(): Promise<BillingPlan[]> {
  const response = await fetch(`${apiBaseUrl}/v1/billing-plans`);
  const payload = (await response.json()) as BillingPlansResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as BillingPlansResponse).data.map(mapRemoteBillingPlan);
}

export async function upsertRemoteBillingPlan(input: BillingPlanUpsert, planId?: string): Promise<BillingPlan> {
  const response = await fetch(
    planId ? `${apiBaseUrl}/admin/billing-plans/${encodeURIComponent(planId)}` : `${apiBaseUrl}/admin/billing-plans`,
    {
      method: planId ? "PATCH" : "POST",
      headers: adminHeaders({
        "Content-Type": "application/json",
      }),
      body: JSON.stringify(input),
    },
  );
  const payload = (await response.json()) as BillingPlanResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return mapRemoteBillingPlan((payload as BillingPlanResponse).data);
}

export async function listRemoteUserSubscriptions(): Promise<UserSubscription[]> {
  const response = await fetch(`${apiBaseUrl}/admin/user-subscriptions`, {
    headers: adminHeaders(),
  });
  const payload = (await response.json()) as UserSubscriptionsResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as UserSubscriptionsResponse).data.map(mapRemoteUserSubscription);
}

export async function upsertRemoteUserSubscription(
  input: UserSubscriptionUpsert,
  subscriptionId?: string,
): Promise<UserSubscription> {
  const response = await fetch(
    subscriptionId
      ? `${apiBaseUrl}/admin/user-subscriptions/${encodeURIComponent(subscriptionId)}`
      : `${apiBaseUrl}/admin/user-subscriptions`,
    {
      method: subscriptionId ? "PATCH" : "POST",
      headers: adminHeaders({
        "Content-Type": "application/json",
      }),
      body: JSON.stringify(input),
    },
  );
  const payload = (await response.json()) as UserSubscriptionResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return mapRemoteUserSubscription((payload as UserSubscriptionResponse).data);
}

export async function changeRemoteSubscription(
  planId: string,
  options: ApiAuthOptions & { userId?: string } = {},
): Promise<{ subscription: UserSubscription; plan: BillingPlan; usage: UsageSummary }> {
  const response = await fetch(`${apiBaseUrl}/v1/subscription`, {
    method: "POST",
    headers: apiHeaders(options.apiKey, {
      "Content-Type": "application/json",
    }),
    body: JSON.stringify({
      plan_id: planId,
      user_id: options.userId,
    }),
  });
  const payload = (await response.json()) as UserSubscriptionChangeResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  const data = (payload as UserSubscriptionChangeResponse).data;
  return {
    subscription: mapRemoteUserSubscription(data.subscription),
    plan: mapRemoteBillingPlan(data.plan),
    usage: data.usage,
  };
}

export async function topUpRemoteWallet(amount: number, options: ApiAuthOptions = {}): Promise<WalletResponse["data"]> {
  const response = await fetch(`${apiBaseUrl}/v1/wallet/top-ups`, {
    method: "POST",
    headers: apiHeaders(options.apiKey, {
      "Content-Type": "application/json",
    }),
    body: JSON.stringify({
      amount,
      note: "演示充值",
    }),
  });
  const payload = (await response.json()) as WalletResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as WalletResponse).data;
}

export async function listRemotePaymentOrders(limit = 20, options: ApiAuthOptions = {}): Promise<PaymentOrder[]> {
  const response = await fetch(`${apiBaseUrl}/v1/payment-orders?limit=${encodeURIComponent(String(limit))}`, {
    headers: apiHeaders(options.apiKey),
  });
  const payload = (await response.json()) as PaymentOrdersResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as PaymentOrdersResponse).data;
}

export async function listPublicPaymentProviders(): Promise<PaymentProvider[]> {
  const response = await fetch(`${apiBaseUrl}/v1/payment-providers`);
  const payload = (await response.json()) as PaymentProvidersResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as PaymentProvidersResponse).data;
}

export async function listAdminPaymentProviders(): Promise<PaymentProvider[]> {
  const response = await fetch(`${apiBaseUrl}/admin/payment-providers`, {
    headers: adminHeaders(),
  });
  const payload = (await response.json()) as PaymentProvidersResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as PaymentProvidersResponse).data;
}

export async function upsertRemotePaymentProvider(
  input: PaymentProviderUpsert,
  providerId?: string,
): Promise<PaymentProvider> {
  const response = await fetch(
    providerId
      ? `${apiBaseUrl}/admin/payment-providers/${encodeURIComponent(providerId)}`
      : `${apiBaseUrl}/admin/payment-providers`,
    {
      method: providerId ? "PATCH" : "POST",
      headers: adminHeaders({
        "Content-Type": "application/json",
      }),
      body: JSON.stringify(input),
    },
  );
  const payload = (await response.json()) as PaymentProviderResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as PaymentProviderResponse).data;
}

export async function listAdminPaymentOrders(limit = 50, userId?: string): Promise<PaymentOrder[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (userId) {
    params.set("user_id", userId);
  }

  const response = await fetch(`${apiBaseUrl}/admin/payment-orders?${params.toString()}`, {
    headers: adminHeaders(),
  });
  const payload = (await response.json()) as PaymentOrdersResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as PaymentOrdersResponse).data;
}

export async function createRemotePaymentOrder(
  amount: number,
  options: ApiAuthOptions & { provider?: string; currency?: string } = {},
): Promise<PaymentOrder> {
  const response = await fetch(`${apiBaseUrl}/v1/payment-orders`, {
    method: "POST",
    headers: apiHeaders(options.apiKey, {
      "Content-Type": "application/json",
    }),
    body: JSON.stringify({
      amount,
      provider: options.provider ?? "mock",
      currency: options.currency,
      idempotency_key: `topup-${Date.now().toString(16)}-${Math.random().toString(16).slice(2, 8)}`,
    }),
  });
  const payload = (await response.json()) as PaymentOrderResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as PaymentOrderResponse).data;
}

export async function confirmRemotePaymentOrder(orderId: string, options: ApiAuthOptions = {}): Promise<PaymentOrderConfirmResult> {
  const response = await fetch(`${apiBaseUrl}/v1/payment-orders/${encodeURIComponent(orderId)}/confirm`, {
    method: "POST",
    headers: apiHeaders(options.apiKey, {
      "Content-Type": "application/json",
    }),
    body: JSON.stringify({
      provider_transaction_id: `mock_tx_${Date.now().toString(16)}`,
    }),
  });
  const payload = (await response.json()) as PaymentOrderConfirmResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as PaymentOrderConfirmResponse).data;
}

export async function cancelRemotePaymentOrder(orderId: string, options: ApiAuthOptions = {}): Promise<PaymentOrder> {
  const response = await fetch(`${apiBaseUrl}/v1/payment-orders/${encodeURIComponent(orderId)}/cancel`, {
    method: "POST",
    headers: apiHeaders(options.apiKey, {
      "Content-Type": "application/json",
    }),
    body: JSON.stringify({}),
  });
  const payload = (await response.json()) as PaymentOrderResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as PaymentOrderResponse).data;
}

export async function topUpAdminWallet(userId: string, amount: number): Promise<WalletResponse["data"]> {
  const response = await fetch(`${apiBaseUrl}/admin/wallet/top-ups`, {
    method: "POST",
    headers: adminHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify({
      user_id: userId,
      amount,
      note: "Admin top-up",
    }),
  });
  const payload = (await response.json()) as WalletResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as WalletResponse).data;
}

export async function updateRemoteChannel(channelId: string, patch: ChannelPatch): Promise<Channel> {
  const response = await fetch(`${apiBaseUrl}/admin/channels/${channelId}`, {
    method: "PATCH",
    headers: adminHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify(patch),
  });
  const payload = (await response.json()) as AdminChannelResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return mapAdminChannelToChannel((payload as AdminChannelResponse).data);
}

export async function createRemoteChannel(input: ChannelCreate): Promise<Channel> {
  const response = await fetch(`${apiBaseUrl}/admin/channels`, {
    method: "POST",
    headers: adminHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify(input),
  });
  const payload = (await response.json()) as AdminChannelResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return mapAdminChannelToChannel((payload as AdminChannelResponse).data);
}

export async function upsertRemoteChannelMapping(channelId: string, input: ChannelMappingUpsert): Promise<Channel> {
  const response = await fetch(`${apiBaseUrl}/admin/channels/${encodeURIComponent(channelId)}/parameter-mappings`, {
    method: "POST",
    headers: adminHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify(input),
  });
  const payload = (await response.json()) as AdminChannelResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return mapAdminChannelToChannel((payload as AdminChannelResponse).data);
}

export async function listRemoteChannels(): Promise<Channel[]> {
  const response = await fetch(`${apiBaseUrl}/admin/channels`, {
    headers: adminHeaders(),
  });
  const payload = (await response.json()) as AdminChannelsResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as AdminChannelsResponse).data.map(mapAdminChannelToChannel);
}

export async function upsertRemotePlatformModelSchemaField(
  modelId: string,
  input: SchemaFieldUpsert,
): Promise<SchemaField[]> {
  const response = await fetch(`${apiBaseUrl}/admin/platform-models/${encodeURIComponent(modelId)}/schema-fields`, {
    method: "POST",
    headers: adminHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify(input),
  });
  const payload = (await response.json()) as AdminPlatformModelResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as AdminPlatformModelResponse).data.schema ?? [];
}

export async function upsertRemotePlatformModel(input: PlatformModelUpsert, modelId?: string): Promise<RemotePlatformModelRecord> {
  const response = await fetch(
    modelId ? `${apiBaseUrl}/admin/platform-models/${encodeURIComponent(modelId)}` : `${apiBaseUrl}/admin/platform-models`,
    {
      method: modelId ? "PATCH" : "POST",
      headers: adminHeaders({
        "Content-Type": "application/json",
      }),
      body: JSON.stringify(input),
    },
  );
  const payload = (await response.json()) as AdminPlatformModelResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as AdminPlatformModelResponse).data;
}

export async function listRemotePlatformModels(localModels: PlatformModel[]): Promise<PlatformModel[]> {
  const response = await fetch(`${apiBaseUrl}/admin/platform-models`, {
    headers: adminHeaders(),
  });
  const payload = (await response.json()) as PlatformModelsResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return mergeRemotePlatformModels(localModels, (payload as PlatformModelsResponse).data);
}

export async function listPublicCapabilities(localModels: PlatformModel[]): Promise<PlatformModel[]> {
  const response = await fetch(`${apiBaseUrl}/v1/capabilities`);
  const payload = (await response.json()) as PublicCapabilitiesResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  const data = (payload as PublicCapabilitiesResponse).data;
  const models = Array.isArray(data) ? data : data.models ?? [];
  return mergeRemotePlatformModels(localModels, models);
}

export async function getPublicModelSchema(modelId: string): Promise<SchemaField[]> {
  const response = await fetch(`${apiBaseUrl}/v1/models/${encodeURIComponent(modelId)}/schema`);
  const payload = (await response.json()) as PublicModelSchemaResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return normalizeRemoteSchema((payload as PublicModelSchemaResponse).data.schema ?? []);
}

export async function listRemoteProviders(): Promise<Provider[]> {
  const response = await fetch(`${apiBaseUrl}/admin/providers`, {
    headers: adminHeaders(),
  });
  const payload = (await response.json()) as ProvidersResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as ProvidersResponse).data.map(mapRemoteProvider);
}

export async function listRemoteProviderModels(): Promise<ProviderModel[]> {
  const response = await fetch(`${apiBaseUrl}/admin/provider-models`, {
    headers: adminHeaders(),
  });
  const payload = (await response.json()) as ProviderModelsResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as ProviderModelsResponse).data.map(mapRemoteProviderModel);
}

export async function upsertRemoteProvider(input: ProviderUpsert, providerId?: string): Promise<Provider> {
  const response = await fetch(
    providerId ? `${apiBaseUrl}/admin/providers/${encodeURIComponent(providerId)}` : `${apiBaseUrl}/admin/providers`,
    {
      method: providerId ? "PATCH" : "POST",
      headers: adminHeaders({
        "Content-Type": "application/json",
      }),
      body: JSON.stringify(input),
    },
  );
  const payload = (await response.json()) as ProviderResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return mapRemoteProvider((payload as ProviderResponse).data);
}

export async function upsertRemoteProviderModel(input: ProviderModelUpsert, providerModelId?: string): Promise<ProviderModel> {
  const response = await fetch(
    providerModelId
      ? `${apiBaseUrl}/admin/provider-models/${encodeURIComponent(providerModelId)}`
      : `${apiBaseUrl}/admin/provider-models`,
    {
      method: providerModelId ? "PATCH" : "POST",
      headers: adminHeaders({
        "Content-Type": "application/json",
      }),
      body: JSON.stringify(input),
    },
  );
  const payload = (await response.json()) as ProviderModelResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return mapRemoteProviderModel((payload as ProviderModelResponse).data);
}

export function mapAdminChannelToChannel(channel: AdminChannelResponse["data"]): Channel {
  return {
    id: channel.id,
    platformModelId: channel.platformModelId,
    providerId: channel.providerId,
    providerModel: channel.provider_model?.upstreamModelName ?? channel.providerModelId ?? "unknown",
    role: channel.role,
    status: channel.status,
    weight: channel.weight,
    cost: String(channel.costPrice),
    sale: String(channel.salePrice),
    latency: channel.latency,
    successRate: channel.successRate,
    supports: channel.supports ?? [],
    paramMap:
      channel.parameter_mappings?.map((item) => ({
        platform: item.platform,
        upstream: item.upstream ?? "",
        transform: item.transform,
        valueMap: item.valueMap ?? item.value_map,
        defaultValue: item.defaultValue ?? item.default_value,
        note: item.note ?? "",
      })) ?? [],
  };
}

function mapRemoteProvider(provider: RemoteProviderRecord): Provider {
  return {
    id: provider.id,
    name: provider.name,
    kind: provider.kind,
    status: provider.status,
    baseUrl: provider.baseUrl ?? provider.base_url ?? "",
    latency: provider.latency ?? provider.latency_ms ?? 0,
    successRate: provider.successRate ?? provider.success_rate ?? 0,
    rpm: provider.rpm ?? 0,
    concurrency: provider.concurrency ?? 0,
  };
}

function mapRemoteProviderModel(model: RemoteProviderModelRecord): ProviderModel {
  return {
    id: model.id,
    providerId: model.providerId ?? model.provider_id ?? "",
    upstreamModelName: model.upstreamModelName ?? model.upstream_model_name ?? model.id,
    endpointType: model.endpointType ?? model.endpoint_type,
    modality: model.modality,
    status: model.status,
    rawCapabilities: model.rawCapabilities ?? model.raw_capabilities ?? {},
    notes: model.notes ?? null,
  };
}

function mapRemoteBillingPlan(plan: RemoteBillingPlanRecord): BillingPlan {
  return {
    id: plan.id,
    name: plan.name,
    monthlyTaskLimit: plan.monthlyTaskLimit ?? plan.monthly_task_limit ?? 0,
    monthlySpendLimit: plan.monthlySpendLimit ?? plan.monthly_spend_limit ?? 0,
    rateLimitPerMinute: plan.rateLimitPerMinute ?? plan.rate_limit_per_minute ?? 0,
    concurrencyLimit: plan.concurrencyLimit ?? plan.concurrency_limit ?? 0,
    features: plan.features ?? [],
    status: plan.status ?? "active",
  };
}

function mapRemoteUserSubscription(subscription: RemoteUserSubscriptionRecord): UserSubscription {
  return {
    id: subscription.id,
    userId: subscription.userId ?? subscription.user_id ?? "",
    planId: subscription.planId ?? subscription.plan_id ?? "",
    status: subscription.status,
    renewsAt: subscription.renewsAt ?? subscription.renews_at ?? null,
    cancelledAt: subscription.cancelledAt ?? subscription.cancelled_at ?? null,
  };
}

function mergeRemotePlatformModels(localModels: PlatformModel[], remoteModels: RemotePlatformModelRecord[]): PlatformModel[] {
  const localById = new Map(localModels.map((model) => [model.id, model]));
  const merged: PlatformModel[] = [];

  remoteModels.forEach((remote) => {
    const local = localById.get(remote.id);
    const template = local ?? localModels.find((model) => model.modality === remote.modality) ?? localModels[0];

    merged.push({
      ...template,
      id: remote.id,
      slug: remote.slug ?? template.slug,
      displayName: remote.displayName ?? remote.display_name ?? remote.name ?? template.displayName,
      name: remote.displayName ?? remote.display_name ?? remote.name ?? template.name,
      shortName: remote.shortName ?? remote.short_name ?? template.shortName,
      modality: remote.modality ?? template.modality,
      categoryKeys: remote.categoryKeys ?? remote.category_keys ?? template.categoryKeys ?? [remote.modality ?? template.modality],
      aliases: remote.aliases ?? template.aliases ?? [],
      tier: remote.tier ?? template.tier,
      description: remote.description ?? template.description,
      useCases: remote.useCases ?? remote.use_cases ?? template.useCases,
      recommended: remote.recommended ?? template.recommended,
      price: remote.estimatedCost ?? remote.estimated_cost ?? template.price,
      eta: remote.estimatedTime ?? remote.estimated_time ?? template.eta,
      schema: normalizeRemoteSchema(remote.schema ?? template.schema),
    });
  });

  const remoteIds = new Set(merged.map((model) => model.id));
  const localOnly = localModels.filter((model) => !remoteIds.has(model.id));
  return [...merged, ...localOnly];
}

function normalizeRemoteSchema(schema: SchemaField[]): SchemaField[] {
  return schema.map((field) => ({
    ...field,
    value: field.value ?? field.defaultValue,
    defaultValue: field.defaultValue ?? field.value,
  }));
}

export async function listRemoteApiKeys(userId = "demo_user"): Promise<PlatformApiKey[]> {
  const response = await fetch(`${apiBaseUrl}/admin/api-keys?user_id=${encodeURIComponent(userId)}`, {
    headers: adminHeaders(),
  });
  const payload = (await response.json()) as ApiKeysResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as ApiKeysResponse).data;
}

export async function listRemoteUsers(limit = 100): Promise<PlatformUser[]> {
  const response = await fetch(`${apiBaseUrl}/admin/users?limit=${encodeURIComponent(String(limit))}`, {
    headers: adminHeaders(),
  });
  const payload = (await response.json()) as PlatformUsersResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as PlatformUsersResponse).data;
}

export async function upsertRemoteUser(input: PlatformUserUpsert, userId?: string): Promise<PlatformUser> {
  const response = await fetch(
    userId ? `${apiBaseUrl}/admin/users/${encodeURIComponent(userId)}` : `${apiBaseUrl}/admin/users`,
    {
      method: userId ? "PATCH" : "POST",
      headers: adminHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(input),
    },
  );
  const payload = (await response.json()) as { data: PlatformUser } | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as { data: PlatformUser }).data;
}

export async function listRemoteTasks(limit = 50): Promise<RemoteTaskRecord[]> {
  const response = await fetch(`${apiBaseUrl}/admin/tasks?limit=${encodeURIComponent(String(limit))}`, {
    headers: adminHeaders(),
  });
  const payload = (await response.json()) as AdminTasksResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as AdminTasksResponse).data;
}

export async function getRemoteAnalyticsSummary(): Promise<AnalyticsSummary> {
  const response = await fetch(`${apiBaseUrl}/admin/analytics/summary`, {
    headers: adminHeaders(),
  });
  const payload = (await response.json()) as AnalyticsSummaryResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as AnalyticsSummaryResponse).data;
}

export async function getRemoteCommercialReadiness(): Promise<CommercialReadinessSummary> {
  const response = await fetch(`${apiBaseUrl}/admin/commercial-readiness`, {
    headers: adminHeaders(),
  });
  const payload = (await response.json()) as CommercialReadinessResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as CommercialReadinessResponse).data;
}

export async function getRemoteCustomersSummary(limit = 20): Promise<CustomersSummary> {
  const response = await fetch(`${apiBaseUrl}/admin/customers/summary?limit=${encodeURIComponent(String(limit))}`, {
    headers: adminHeaders(),
  });
  const payload = (await response.json()) as CustomersSummaryResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as CustomersSummaryResponse).data;
}

export async function getRemoteBillingTransactions(limit = 20): Promise<BillingTransactionsSummary> {
  const response = await fetch(`${apiBaseUrl}/admin/billing/transactions?limit=${encodeURIComponent(String(limit))}`, {
    headers: adminHeaders(),
  });
  const payload = (await response.json()) as BillingTransactionsResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as BillingTransactionsResponse).data;
}

export async function getRemoteBillingInvoices(period?: BillingPeriodQuery): Promise<BillingInvoicesSummary> {
  const response = await fetch(`${apiBaseUrl}/admin/billing/invoices${billingPeriodQuery(period)}`, {
    headers: adminHeaders(),
  });
  const payload = (await response.json()) as BillingInvoicesResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as BillingInvoicesResponse).data;
}

export async function downloadRemoteBillingInvoicesCsv(period?: BillingPeriodQuery): Promise<string> {
  const response = await fetch(`${apiBaseUrl}/admin/billing/invoices.csv${billingPeriodQuery(period)}`, {
    headers: adminHeaders(),
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as ProblemDetails;
    throw new Error(formatProblem(payload));
  }

  const disposition = response.headers.get("Content-Disposition") ?? "";
  const filename = disposition.match(/filename="([^"]+)"/)?.[1] ?? "tikpan-invoices.csv";
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
  return filename;
}

export async function refundRemoteBillingTransaction(taskId: string, amount?: number, note = "Admin refund"): Promise<BillingRefundResult> {
  const response = await fetch(`${apiBaseUrl}/admin/billing/transactions/${encodeURIComponent(taskId)}/refunds`, {
    method: "POST",
    headers: adminHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ amount, note }),
  });
  const payload = (await response.json()) as { data: BillingRefundResult } | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as { data: BillingRefundResult }).data;
}

export async function listRemoteWebhookEndpoints(userId = "demo_user"): Promise<WebhookEndpoint[]> {
  const response = await fetch(`${apiBaseUrl}/admin/webhook-endpoints?user_id=${encodeURIComponent(userId)}`, {
    headers: adminHeaders(),
  });
  const payload = (await response.json()) as WebhookEndpointsResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as WebhookEndpointsResponse).data;
}

export async function upsertRemoteWebhookEndpoint(endpoint: WebhookEndpointUpsert): Promise<WebhookEndpoint> {
  const response = await fetch(`${apiBaseUrl}/admin/webhook-endpoints`, {
    method: "POST",
    headers: adminHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(endpoint),
  });
  const payload = (await response.json()) as { data: WebhookEndpoint } | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as { data: WebhookEndpoint }).data;
}

export async function listRemoteWebhookDeliveries(limit = 20, userId = "demo_user"): Promise<WebhookDelivery[]> {
  const response = await fetch(`${apiBaseUrl}/admin/webhook-deliveries?limit=${encodeURIComponent(String(limit))}&user_id=${encodeURIComponent(userId)}`, {
    headers: adminHeaders(),
  });
  const payload = (await response.json()) as WebhookDeliveriesResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as WebhookDeliveriesResponse).data;
}

export async function listRemoteAuditLogs(limit = 30, userId?: string): Promise<AuditLog[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (userId) {
    params.set("user_id", userId);
  }

  const response = await fetch(`${apiBaseUrl}/admin/audit-logs?${params.toString()}`, {
    headers: adminHeaders(),
  });
  const payload = (await response.json()) as AuditLogsResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as AuditLogsResponse).data;
}

export async function listUserRemoteTasks(limit = 50, options: ApiAuthOptions = {}): Promise<RemoteTaskRecord[]> {
  const response = await fetch(`${apiBaseUrl}/v1/tasks?limit=${encodeURIComponent(String(limit))}`, {
    headers: apiHeaders(options.apiKey),
  });
  const payload = (await response.json()) as AdminTasksResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as AdminTasksResponse).data;
}

export async function listRemoteTaskBatches(limit = 20, options: ApiAuthOptions = {}): Promise<RemoteTaskBatch[]> {
  const response = await fetch(`${apiBaseUrl}/v1/task-batches?limit=${encodeURIComponent(String(limit))}`, {
    headers: apiHeaders(options.apiKey),
  });
  const payload = (await response.json()) as ApiTaskBatchesResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as ApiTaskBatchesResponse).data;
}

export async function listRemoteAssets(limit = 50, options: ApiAuthOptions = {}): Promise<GenerationAsset[]> {
  const response = await fetch(`${apiBaseUrl}/v1/assets?limit=${encodeURIComponent(String(limit))}`, {
    headers: apiHeaders(options.apiKey),
  });
  const payload = (await response.json()) as GenerationAssetsResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as GenerationAssetsResponse).data;
}

export async function listRemoteProjects(limit = 50, options: ApiAuthOptions = {}): Promise<CreativeProject[]> {
  const response = await fetch(`${apiBaseUrl}/v1/projects?limit=${encodeURIComponent(String(limit))}`, {
    headers: apiHeaders(options.apiKey),
  });
  const payload = (await response.json()) as CreativeProjectsResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as CreativeProjectsResponse).data;
}

export async function getRemoteProject(projectId: string, options: ApiAuthOptions = {}): Promise<CreativeProject> {
  const response = await fetch(`${apiBaseUrl}/v1/projects/${encodeURIComponent(projectId)}`, {
    headers: apiHeaders(options.apiKey),
  });
  const payload = (await response.json()) as CreativeProjectResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as CreativeProjectResponse).data;
}

export async function saveRemoteProject(
  input: CreativeProjectInput,
  options: ApiAuthOptions = {},
): Promise<CreativeProject> {
  const response = await fetch(
    input.id ? `${apiBaseUrl}/v1/projects/${encodeURIComponent(input.id)}` : `${apiBaseUrl}/v1/projects`,
    {
      method: input.id ? "PATCH" : "POST",
      headers: apiHeaders(options.apiKey, {
        "Content-Type": "application/json",
      }),
      body: JSON.stringify(input),
    },
  );
  const payload = (await response.json()) as CreativeProjectResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as CreativeProjectResponse).data;
}

export async function createRemoteProjectAsset(
  projectId: string,
  input: ManualProjectAssetInput,
  options: ApiAuthOptions = {},
): Promise<GenerationAsset> {
  const response = await fetch(`${apiBaseUrl}/v1/projects/${encodeURIComponent(projectId)}/assets`, {
    method: "POST",
    headers: apiHeaders(options.apiKey, {
      "Content-Type": "application/json",
    }),
    body: JSON.stringify(input),
  });
  const payload = (await response.json()) as GenerationAssetResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as GenerationAssetResponse).data;
}

export async function updateRemoteAsset(
  taskId: string,
  patch: GenerationAssetPatch,
  options: ApiAuthOptions = {},
): Promise<GenerationAsset> {
  const response = await fetch(`${apiBaseUrl}/v1/assets/${encodeURIComponent(taskId)}`, {
    method: "PATCH",
    headers: apiHeaders(options.apiKey, {
      "Content-Type": "application/json",
    }),
    body: JSON.stringify(patch),
  });
  const payload = (await response.json()) as GenerationAssetResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as GenerationAssetResponse).data;
}

export async function createRemoteApiKey(name: string, userId = "demo_user"): Promise<PlatformApiKey> {
  const response = await fetch(`${apiBaseUrl}/admin/api-keys`, {
    method: "POST",
    headers: adminHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify({ name, user_id: userId }),
  });
  const payload = (await response.json()) as ApiKeyResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as ApiKeyResponse).data;
}

export async function revokeRemoteApiKey(keyId: string): Promise<PlatformApiKey> {
  const response = await fetch(`${apiBaseUrl}/admin/api-keys/${keyId}`, {
    method: "PATCH",
    headers: adminHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify({ status: "revoked" }),
  });
  const payload = (await response.json()) as ApiKeyResponse | ProblemDetails;

  if (!response.ok) {
    throw new Error(formatProblem(payload as ProblemDetails));
  }

  return (payload as ApiKeyResponse).data;
}

function mapApiTaskToPreview(
  response: ApiTaskResponse,
  model: PlatformModel,
  routeMode: RouteMode,
  previousTask?: OrchestratedTask,
): OrchestratedTask {
  const task = response.data;
  const terminal = isTerminalTaskStatus(task.status);
  const failed = isFailedTaskStatus(task.status);
  const outputUrls = task.output?.publicUrls ?? task.output?.public_urls ?? previousTask?.lifecycle?.outputUrls;
  const routeReason =
    task.internal?.route_score?.[0]?.reasons?.join("；") ??
    previousTask?.internal.routeReason ??
    "由后端 API 根据当前路由偏好选择渠道";

  return {
    taskId: task.task_id,
    publicModel: task.model,
    status: failed ? "blocked" : "ready",
    routeMode,
    lifecycle: {
      apiStatus: task.status,
      progress: task.progress ?? previousTask?.lifecycle?.progress ?? (isSucceededTaskStatus(task.status) ? 100 : 0),
      currentStep: task.current_step ?? previousTask?.lifecycle?.currentStep ?? null,
      outputUrls,
      isTerminal: terminal,
    },
    worker: task.worker
      ? {
          workerId: task.worker.worker_id,
          lockedUntil: task.worker.locked_until,
          lockVersion: task.worker.lock_version,
        }
      : previousTask?.worker,
    userVisible: {
      estimatedCost: String(task.estimated_cost ?? previousTask?.userVisible.estimatedCost ?? model.price),
      estimatedTime: task.estimated_time ?? previousTask?.userVisible.estimatedTime ?? model.eta,
      guarantee: task.guarantee ?? previousTask?.userVisible.guarantee ?? "失败不扣费，成功后结算",
      message: task.error?.message ?? task.message ?? previousTask?.userVisible.message ?? "任务状态已更新",
    },
    internal: {
      providerName: task.internal?.provider ?? previousTask?.internal.providerName,
      providerModel: task.internal?.provider_model ?? previousTask?.internal.providerModel,
      billing: {
        preAuthAmount: String(task.estimated_cost ?? previousTask?.internal.billing.preAuthAmount ?? 0),
        settlement: model.modality === "chat" ? "actual_usage" : "success_only",
        marginHint: previousTask?.internal.billing.marginHint ?? "由后端账务模块计算",
      },
      payload: task.internal?.mapped_payload ?? previousTask?.internal.payload,
      routeReason,
      rejected: task.internal?.rejected ?? previousTask?.internal.rejected ?? [],
      attempts: mapApiAttempts(task.attempts) ?? previousTask?.internal.attempts,
    },
  };
}

function isSucceededTaskStatus(status: string) {
  return status === "completed" || status === "succeeded";
}

function isFailedTaskStatus(status: string) {
  return ["failed", "cancelled", "canceled", "expired", "refunded"].includes(status);
}

function isTerminalTaskStatus(status: string) {
  return isSucceededTaskStatus(status) || isFailedTaskStatus(status);
}

function mapApiAttempts(attempts: ApiTaskResponse["data"]["attempts"]): TaskAttempt[] | undefined {
  if (!attempts) {
    return undefined;
  }

  return attempts.map((attempt) => ({
    id: attempt.id,
    provider: attempt.provider,
    providerModel: attempt.provider_model,
    channelId: attempt.channel_id,
    status: attempt.status,
    errorCode: attempt.error_code ?? null,
    errorMessage: attempt.error_message ?? null,
    fallbackReason: attempt.fallback_reason ?? null,
    createdAt: attempt.created_at,
    finishedAt: attempt.finished_at ?? null,
  }));
}

function formatProblem(problem: ProblemDetails) {
  const code = problem.code ?? problem.title;
  const friendlyMessages: Record<string, string> = {
    NO_AVAILABLE_ROUTE: "当前参数暂时没有可用生成能力，请减少高级选项或稍后再试。",
    NO_BALANCE: "余额不足，请先充值后继续生成。",
    MONTHLY_TASK_LIMIT_EXCEEDED: "本月生成次数已用完，请升级套餐或下个周期再试。",
    MONTHLY_SPEND_LIMIT_EXCEEDED: "本月 Tokens 额度不足，请升级套餐或稍后再试。",
    CONCURRENCY_LIMIT_EXCEEDED: "当前同时生成任务已达上限，请等待已有任务完成。",
    SUBSCRIPTION_INACTIVE: "当前套餐未生效，请先到账户中心处理。",
  };
  if (code && friendlyMessages[code]) {
    return friendlyMessages[code];
  }

  const fieldErrors = problem.errors
    ?.map((item) => `${item.field ?? "field"}: ${item.message ?? "invalid"}`)
    .join("；");

  return fieldErrors || problem.detail || problem.title || "API 请求失败";
}
