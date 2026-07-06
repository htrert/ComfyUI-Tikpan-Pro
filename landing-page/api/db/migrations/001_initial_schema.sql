-- Tikpan AI aggregation platform initial PostgreSQL schema.
-- This migration is intentionally explicit so the in-memory demo objects can
-- move to durable storage without changing the public API shape.

begin;

create extension if not exists pgcrypto;

create table users (
  id text primary key,
  display_name text not null,
  email text unique,
  status text not null default 'active'
    check (status in ('active', 'suspended', 'deleted')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table billing_plans (
  id text primary key,
  name text not null,
  monthly_task_limit integer not null check (monthly_task_limit >= 0),
  monthly_spend_limit numeric(12, 4) not null check (monthly_spend_limit >= 0),
  rate_limit_per_minute integer not null check (rate_limit_per_minute > 0),
  concurrency_limit integer not null check (concurrency_limit > 0),
  features jsonb not null default '[]',
  status text not null default 'active'
    check (status in ('active', 'archived')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table user_subscriptions (
  id text primary key,
  user_id text not null references users(id),
  plan_id text not null references billing_plans(id),
  status text not null default 'active'
    check (status in ('trialing', 'active', 'past_due', 'cancelled', 'expired')),
  started_at timestamptz not null default now(),
  renews_at timestamptz,
  cancelled_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index user_subscriptions_one_active_idx
  on user_subscriptions(user_id)
  where status in ('trialing', 'active', 'past_due');

create table wallets (
  user_id text primary key references users(id),
  currency text not null default 'CNY',
  balance numeric(12, 4) not null default 0 check (balance >= 0),
  frozen numeric(12, 4) not null default 0 check (frozen >= 0),
  updated_at timestamptz not null default now()
);

create table wallet_ledger (
  id text primary key,
  user_id text not null references users(id),
  task_id text,
  type text not null
    check (type in ('top_up', 'gift', 'pre_authorize', 'settle', 'release', 'refund', 'admin_adjust')),
  amount numeric(12, 4) not null,
  balance_after numeric(12, 4) not null,
  frozen_after numeric(12, 4) not null default 0,
  note text not null,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create index wallet_ledger_user_created_idx on wallet_ledger(user_id, created_at desc);
create index wallet_ledger_task_idx on wallet_ledger(task_id) where task_id is not null;

create table providers (
  id text primary key,
  name text not null,
  kind text not null check (kind in ('official', 'relay', 'private')),
  base_url text not null,
  auth_type text not null check (auth_type in ('bearer', 'custom_header', 'none')),
  encrypted_api_key text,
  status text not null default 'active'
    check (status in ('active', 'degraded', 'testing', 'disabled')),
  rpm integer check (rpm is null or rpm >= 0),
  concurrency integer check (concurrency is null or concurrency >= 0),
  latency_ms integer,
  success_rate numeric(5, 2),
  timeout_ms integer not null default 60000,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table provider_models (
  id text primary key,
  provider_id text not null references providers(id),
  upstream_model_name text not null,
  endpoint_type text not null,
  modality text not null check (modality in ('image', 'video', 'chat', 'audio', 'workflow')),
  status text not null default 'active'
    check (status in ('active', 'degraded', 'testing', 'disabled')),
  raw_capabilities jsonb not null default '{}',
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (provider_id, upstream_model_name)
);

create index provider_models_provider_idx on provider_models(provider_id);

create table platform_models (
  id text primary key,
  name text not null,
  short_name text not null,
  modality text not null check (modality in ('image', 'video', 'chat', 'audio', 'workflow')),
  tier text not null,
  description text not null,
  use_cases jsonb not null default '[]',
  visible boolean not null default true,
  recommended boolean not null default false,
  estimated_cost text,
  estimated_time text,
  sort_order integer not null default 0,
  schema jsonb not null default '[]',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index platform_models_visible_sort_idx on platform_models(visible, sort_order, id);
create index platform_models_modality_idx on platform_models(modality);

create table model_channels (
  id text primary key,
  platform_model_id text not null references platform_models(id),
  provider_id text not null references providers(id),
  provider_model_id text not null references provider_models(id),
  role text not null check (role in ('primary', 'backup', 'cheap', 'fast', 'quality')),
  status text not null default 'active'
    check (status in ('active', 'degraded', 'disabled')),
  weight integer not null default 50 check (weight between 0 and 100),
  priority integer not null default 100 check (priority > 0),
  cost_price numeric(12, 4) not null default 0 check (cost_price >= 0),
  sale_price numeric(12, 4) not null default 0 check (sale_price >= 0),
  billing_unit text not null,
  latency numeric(8, 2),
  success_rate numeric(5, 2),
  max_concurrency integer,
  timeout_ms integer,
  supports jsonb not null default '[]',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index model_channels_platform_status_idx on model_channels(platform_model_id, status, priority);
create index model_channels_provider_idx on model_channels(provider_id);
create index model_channels_provider_model_idx on model_channels(provider_model_id);

create table channel_parameter_mappings (
  id text primary key,
  channel_id text not null references model_channels(id) on delete cascade,
  platform_param_key text not null,
  upstream_param_key text,
  transform text not null default 'direct'
    check (transform in ('direct', 'map', 'default', 'omit', 'template')),
  value_map jsonb not null default '{}',
  default_value jsonb,
  note text,
  created_at timestamptz not null default now(),
  unique (channel_id, platform_param_key)
);

create index channel_parameter_mappings_channel_idx on channel_parameter_mappings(channel_id);

create table platform_api_keys (
  id text primary key,
  user_id text not null references users(id),
  name text not null,
  prefix text not null,
  secret_hash text not null,
  status text not null default 'active'
    check (status in ('active', 'revoked')),
  scopes jsonb not null default '[]',
  last_used_at timestamptz,
  revoked_at timestamptz,
  created_at timestamptz not null default now(),
  unique (prefix)
);

create index platform_api_keys_user_status_idx on platform_api_keys(user_id, status);

create table rate_limit_buckets (
  api_key_id text primary key references platform_api_keys(id) on delete cascade,
  count integer not null default 0 check (count >= 0),
  reset_at timestamptz not null,
  updated_at timestamptz not null default now()
);

create table tasks (
  id text primary key,
  user_id text not null references users(id),
  platform_model_id text not null references platform_models(id),
  status text not null
    check (status in ('queued', 'running', 'saving_media', 'completed', 'failed', 'cancelled', 'expired')),
  route_mode text not null default 'balanced',
  input jsonb not null,
  output jsonb,
  estimated_cost numeric(12, 4) not null default 0,
  final_cost numeric(12, 4),
  public_error_code text,
  public_error_message text,
  selected_channel_id text references model_channels(id),
  selected_provider_id text references providers(id),
  selected_provider_model_id text references provider_models(id),
  mapped_payload jsonb,
  current_step text,
  progress integer check (progress is null or progress between 0 and 100),
  queued_at timestamptz,
  started_at timestamptz,
  finished_at timestamptz,
  settled_at timestamptz,
  released_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table wallet_ledger
  add constraint wallet_ledger_task_fk foreign key (task_id) references tasks(id);

create index tasks_user_created_idx on tasks(user_id, created_at desc);
create index tasks_status_created_idx on tasks(status, created_at);
create index tasks_platform_model_idx on tasks(platform_model_id);

create table task_attempts (
  id text primary key,
  task_id text not null references tasks(id) on delete cascade,
  provider_id text not null references providers(id),
  provider_model_id text not null references provider_models(id),
  channel_id text not null references model_channels(id),
  status text not null
    check (status in ('queued', 'running', 'saving_media', 'completed', 'failed')),
  mapped_payload jsonb not null,
  upstream_response jsonb,
  upstream_error_code text,
  upstream_error_message text,
  fallback_reason text,
  latency_ms integer,
  cost_price numeric(12, 4),
  created_at timestamptz not null default now(),
  finished_at timestamptz
);

create index task_attempts_task_idx on task_attempts(task_id, created_at);
create index task_attempts_provider_created_idx on task_attempts(provider_id, created_at desc);

create table media_assets (
  id text primary key,
  task_id text not null references tasks(id) on delete cascade,
  user_id text not null references users(id),
  direction text not null check (direction in ('input', 'output')),
  object_key text not null,
  public_url text,
  mime_type text,
  size_bytes bigint,
  width integer,
  height integer,
  duration_seconds numeric(10, 3),
  hash text,
  created_at timestamptz not null default now()
);

create index media_assets_task_idx on media_assets(task_id);
create index media_assets_user_created_idx on media_assets(user_id, created_at desc);

commit;
