-- Durable webhook and admin audit operations.

begin;

create table webhook_endpoints (
  id text primary key,
  user_id text not null references users(id),
  url text not null,
  events jsonb not null default '[]',
  status text not null default 'active'
    check (status in ('active', 'disabled')),
  secret text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index webhook_endpoints_user_status_idx on webhook_endpoints(user_id, status);

create table webhook_deliveries (
  id text primary key,
  endpoint_id text not null references webhook_endpoints(id) on delete cascade,
  user_id text not null references users(id),
  task_id text,
  event text not null,
  target_url text not null,
  status text not null default 'pending'
    check (status in ('pending', 'delivered', 'failed')),
  response_status integer,
  attempt integer not null default 1 check (attempt > 0),
  payload jsonb not null default '{}',
  error_message text,
  created_at timestamptz not null default now(),
  delivered_at timestamptz
);

create index webhook_deliveries_user_created_idx on webhook_deliveries(user_id, created_at desc);
create index webhook_deliveries_task_idx on webhook_deliveries(task_id) where task_id is not null;
create index webhook_deliveries_endpoint_created_idx on webhook_deliveries(endpoint_id, created_at desc);

create table audit_logs (
  id text primary key,
  actor_id text not null,
  actor_type text not null
    check (actor_type in ('admin', 'user', 'system')),
  action text not null,
  resource_type text not null,
  resource_id text not null,
  user_id text references users(id),
  summary text not null,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create index audit_logs_created_idx on audit_logs(created_at desc);
create index audit_logs_user_created_idx on audit_logs(user_id, created_at desc) where user_id is not null;
create index audit_logs_resource_idx on audit_logs(resource_type, resource_id, created_at desc);
create index audit_logs_action_idx on audit_logs(action, created_at desc);

create table payment_providers (
  id text primary key,
  name text not null,
  kind text not null
    check (kind in ('mock', 'manual', 'alipay', 'wechat', 'stripe', 'custom')),
  status text not null default 'testing'
    check (status in ('active', 'testing', 'disabled')),
  currencies jsonb not null default '[]',
  fee_rate numeric(8,6) not null default 0 check (fee_rate >= 0),
  fixed_fee numeric(12,4) not null default 0 check (fixed_fee >= 0),
  min_amount numeric(12,4) not null default 0.01 check (min_amount > 0),
  max_amount numeric(12,4) not null default 999999 check (max_amount >= min_amount),
  checkout_mode text not null default 'hosted'
    check (checkout_mode in ('mock', 'hosted', 'qr_code', 'manual', 'redirect')),
  webhook_secret text,
  sort_order integer not null default 50,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index payment_providers_status_sort_idx on payment_providers(status, sort_order);
create index payment_providers_kind_idx on payment_providers(kind);

create table payment_orders (
  id text primary key,
  user_id text not null references users(id),
  amount numeric(12,4) not null check (amount > 0),
  currency text not null default 'CNY',
  provider text not null default 'mock' references payment_providers(id),
  status text not null default 'pending'
    check (status in ('pending', 'paid', 'cancelled', 'expired')),
  idempotency_key text,
  provider_transaction_id text,
  paid_at timestamptz,
  credited_ledger_id text references wallet_ledger(id),
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, idempotency_key)
);

create index payment_orders_user_created_idx on payment_orders(user_id, created_at desc);
create index payment_orders_status_created_idx on payment_orders(status, created_at desc);
create index payment_orders_provider_tx_idx on payment_orders(provider, provider_transaction_id)
  where provider_transaction_id is not null;

insert into webhook_endpoints (
  id, user_id, url, events, status, secret, created_at, updated_at
)
values (
  'wh_demo_default',
  'demo_user',
  'https://example.com/webhooks/tikpan',
  '["task.completed", "task.failed", "task.cancelled", "billing.refunded"]',
  'active',
  'whsec_demo',
  now(),
  now()
)
on conflict (id) do nothing;

insert into payment_providers (
  id, name, kind, status, currencies, fee_rate, fixed_fee, min_amount, max_amount,
  checkout_mode, webhook_secret, sort_order, metadata, created_at, updated_at
)
values
  (
    'mock',
    'Mock Pay',
    'mock',
    'active',
    '["CNY", "USD"]',
    0,
    0,
    0.01,
    999999,
    'mock',
    'tikpan_mock_webhook_secret',
    10,
    '{"settlement":"instant","note":"Local signed webhook simulator for development."}',
    now(),
    now()
  ),
  (
    'manual',
    'Manual Transfer',
    'manual',
    'testing',
    '["CNY"]',
    0,
    0,
    10,
    50000,
    'manual',
    null,
    20,
    '{"settlement":"manual_review","note":"Offline transfer placeholder for future reconciliation."}',
    now(),
    now()
  )
on conflict (id) do nothing;

insert into audit_logs (
  id, actor_id, actor_type, action, resource_type, resource_id, user_id, summary, metadata, created_at
)
values (
  'audit_seed_catalog',
  'system',
  'system',
  'catalog.seeded',
  'platform',
  'postgres',
  null,
  'Seeded demo catalog, billing, wallet, webhook, and audit configuration.',
  '{}',
  now()
)
on conflict (id) do nothing;

commit;
