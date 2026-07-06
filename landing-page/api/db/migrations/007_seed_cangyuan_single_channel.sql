-- Optional seed: use Cangyuan as the first real upstream channel.
-- This keeps the public product model as "tikpan.chat.assistant" and binds it
-- to one Cangyuan OpenAI-compatible upstream model.
--
-- Runtime secret is NOT stored here. Set:
--   TIKPAN_PROVIDER_SECRETS='{"cangyuan":"sk-your-cangyuan-token"}'

begin;

insert into providers (
  id,
  name,
  kind,
  base_url,
  auth_type,
  encrypted_api_key,
  status,
  rpm,
  concurrency,
  latency_ms,
  success_rate,
  timeout_ms
)
values (
  'cangyuan',
  '沧元算力',
  'relay',
  'https://ai.cangyuansuanli.cn',
  'bearer',
  null,
  'active',
  60,
  2,
  1800,
  98.00,
  60000
)
on conflict (id)
do update set
  name = excluded.name,
  kind = excluded.kind,
  base_url = excluded.base_url,
  auth_type = excluded.auth_type,
  status = excluded.status,
  rpm = excluded.rpm,
  concurrency = excluded.concurrency,
  latency_ms = excluded.latency_ms,
  success_rate = excluded.success_rate,
  timeout_ms = excluded.timeout_ms,
  updated_at = now();

insert into provider_models (
  id,
  provider_id,
  upstream_model_name,
  endpoint_type,
  modality,
  status,
  raw_capabilities,
  notes
)
values (
  'pm-cangyuan-chat',
  'cangyuan',
  'gpt-5.5',
  'chat_completions',
  'chat',
  'active',
  '{"endpoint_path":"/v1/chat/completions","compatible":"openai","setup_note":"Replace upstream_model_name with the exact model id shown in Cangyuan model market."}',
  'First real upstream smoke-test model. Replace model id if Cangyuan model market shows a different exact name.'
)
on conflict (id)
do update set
  provider_id = excluded.provider_id,
  upstream_model_name = excluded.upstream_model_name,
  endpoint_type = excluded.endpoint_type,
  modality = excluded.modality,
  status = excluded.status,
  raw_capabilities = excluded.raw_capabilities,
  notes = excluded.notes,
  updated_at = now();

insert into model_channels (
  id,
  platform_model_id,
  provider_id,
  provider_model_id,
  role,
  status,
  weight,
  priority,
  cost_price,
  sale_price,
  billing_unit,
  latency,
  success_rate,
  supports,
  timeout_ms
)
values (
  'ch-chat-cangyuan',
  'tikpan.chat.assistant',
  'cangyuan',
  'pm-cangyuan-chat',
  'primary',
  'active',
  100,
  1,
  0.01,
  0.08,
  'request',
  1.8,
  98.00,
  '["message","stream"]',
  60000
)
on conflict (id)
do update set
  platform_model_id = excluded.platform_model_id,
  provider_id = excluded.provider_id,
  provider_model_id = excluded.provider_model_id,
  role = excluded.role,
  status = excluded.status,
  weight = excluded.weight,
  priority = excluded.priority,
  cost_price = excluded.cost_price,
  sale_price = excluded.sale_price,
  billing_unit = excluded.billing_unit,
  latency = excluded.latency,
  success_rate = excluded.success_rate,
  supports = excluded.supports,
  timeout_ms = excluded.timeout_ms,
  updated_at = now();

insert into channel_parameter_mappings (
  id,
  channel_id,
  platform_param_key,
  upstream_param_key,
  transform,
  value_map,
  default_value,
  note
)
values
  (
    'map-chat-cangyuan-message',
    'ch-chat-cangyuan',
    'message',
    'messages',
    'template',
    '{}',
    null,
    'Wrap creator text into OpenAI-compatible messages.'
  ),
  (
    'map-chat-cangyuan-stream',
    'ch-chat-cangyuan',
    'stream',
    'stream',
    'direct',
    '{}',
    'false',
    'Forward stream flag. Use false for first smoke test.'
  ),
  (
    'map-chat-cangyuan-tone',
    'ch-chat-cangyuan',
    'tone',
    null,
    'omit',
    '{}',
    null,
    'Keep first integration minimal; prompt style can be folded into message later.'
  )
on conflict (channel_id, platform_param_key)
do update set
  upstream_param_key = excluded.upstream_param_key,
  transform = excluded.transform,
  value_map = excluded.value_map,
  default_value = excluded.default_value,
  note = excluded.note;

commit;
