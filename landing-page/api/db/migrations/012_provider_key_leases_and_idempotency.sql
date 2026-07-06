-- Provider key leases, token-window accounting, and wallet settlement idempotency.

begin;

alter table provider_keys
  add column if not exists minute_token_count integer not null default 0 check (minute_token_count >= 0),
  add column if not exists today_success_count integer not null default 0 check (today_success_count >= 0),
  add column if not exists today_failure_count integer not null default 0 check (today_failure_count >= 0),
  add column if not exists total_latency_ms bigint not null default 0 check (total_latency_ms >= 0);

create table provider_key_leases (
  id text primary key,
  provider_key_id text not null references provider_keys(id) on delete cascade,
  provider_id text not null references providers(id) on delete cascade,
  task_id text references tasks(id) on delete set null,
  attempt_id text,
  estimated_tokens integer not null default 0 check (estimated_tokens >= 0),
  actual_tokens integer,
  acquired_at timestamptz not null default now(),
  expires_at timestamptz not null,
  released_at timestamptz,
  error_code text,
  error_message text,
  latency_ms integer
);

create index provider_key_leases_active_idx
  on provider_key_leases(provider_key_id, expires_at)
  where released_at is null;

create index provider_key_leases_task_idx
  on provider_key_leases(task_id, acquired_at desc)
  where task_id is not null;

create unique index wallet_ledger_task_type_once_idx
  on wallet_ledger(task_id, type)
  where task_id is not null and type in ('pre_authorize', 'settle', 'release', 'refund');

alter table task_attempts
  add column if not exists provider_key_lease_expires_at timestamptz,
  add column if not exists latency_ms integer;

commit;
