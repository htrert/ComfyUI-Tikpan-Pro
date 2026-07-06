-- Internal upstream provider key pool and per-key runtime limits.

begin;

create table provider_keys (
  id text primary key,
  provider_id text not null references providers(id) on delete cascade,
  name text not null,
  encrypted_api_key text,
  status text not null default 'active'
    check (status in ('active', 'degraded', 'disabled')),
  rpm integer check (rpm is null or rpm >= 0),
  tpm integer check (tpm is null or tpm >= 0),
  concurrency integer not null default 1 check (concurrency >= 0),
  priority integer not null default 100 check (priority > 0),
  weight integer not null default 50 check (weight between 0 and 100),
  supported_provider_model_ids jsonb not null default '[]',
  current_concurrency integer not null default 0 check (current_concurrency >= 0),
  minute_window_started_at timestamptz,
  minute_request_count integer not null default 0 check (minute_request_count >= 0),
  today_request_count integer not null default 0 check (today_request_count >= 0),
  cooling_until timestamptz,
  last_used_at timestamptz,
  last_error_code text,
  last_error_message text,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index provider_keys_provider_status_idx
  on provider_keys(provider_id, status, priority);

create index provider_keys_available_idx
  on provider_keys(provider_id, status, cooling_until, current_concurrency, priority);

alter table task_attempts
  add column provider_key_id text references provider_keys(id),
  add column provider_key_lease_id text;

create index task_attempts_provider_key_created_idx
  on task_attempts(provider_key_id, created_at desc)
  where provider_key_id is not null;

insert into provider_keys (
  id,
  provider_id,
  name,
  encrypted_api_key,
  status,
  rpm,
  tpm,
  concurrency,
  priority,
  weight,
  supported_provider_model_ids,
  notes
)
select
  providers.id || '-default-key',
  providers.id,
  providers.name || ' Default Internal Key',
  providers.encrypted_api_key,
  case when providers.status = 'disabled' then 'disabled' else 'active' end,
  providers.rpm,
  null,
  coalesce(nullif(providers.concurrency, 0), 1),
  100,
  50,
  '[]',
  'Migrated from provider-level credential; internal only, never exposed to platform users.'
from providers
where providers.encrypted_api_key is not null
on conflict (id) do nothing;

commit;
