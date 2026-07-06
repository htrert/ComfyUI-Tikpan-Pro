-- Optional seed: first image model integration with Cangyuan gpt-image-2-4k.
--
-- Cangyuan docs observed in browser:
--   Display model: gpt-image-2-4k
--   Upstream model id: cy-img2-gpt-image-2-4k
--   Submit: POST /v1/images/generations
--   Poll:   GET  /v1/images/generations/{task_id}
--   Auth:   Authorization: Bearer sk-your-token
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
  120000
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

insert into platform_models (
  id,
  name,
  short_name,
  modality,
  tier,
  description,
  use_cases,
  visible,
  recommended,
  estimated_cost,
  estimated_time,
  sort_order,
  schema
)
values (
  'tikpan.image.gpt-image-2-4k',
  'GPT Image 2 4K',
  'Image 2 4K',
  'image',
  'pro',
  '沧元算力 gpt-image-2-4k，适合高分辨率商品图、广告海报和社媒封面。',
  '["商品主图","广告海报","社媒封面"]',
  true,
  true,
  '0.08 Tokens / 张',
  '异步生成',
  10,
  '[
    {"key":"prompt","label":"画面描述","type":"textarea","required":true},
    {"key":"size","label":"尺寸","type":"select","defaultValue":"auto","options":["auto","1024x1024","1536x1024","1024x1536","2048x2048","3840x2160"]},
    {"key":"quality","label":"画质","type":"segmented","defaultValue":"auto","options":["auto","low","medium","high"]},
    {"key":"n","label":"生成张数","type":"slider","defaultValue":1,"min":1,"max":10,"step":1},
    {"key":"background","label":"背景","type":"segmented","defaultValue":"opaque","options":["auto","opaque"]},
    {"key":"output_format","label":"输出格式","type":"segmented","defaultValue":"png","options":["png","jpeg","webp"]},
    {"key":"output_compression","label":"压缩质量","type":"slider","defaultValue":100,"min":0,"max":100,"step":1,"advanced":true},
    {"key":"moderation","label":"内容审核","type":"segmented","defaultValue":"auto","options":["auto","low"],"advanced":true},
    {"key":"stream","label":"流式返回","type":"switch","defaultValue":false,"advanced":true},
    {"key":"partial_images","label":"部分预览图","type":"slider","defaultValue":0,"min":0,"max":3,"step":1,"advanced":true},
    {"key":"async","label":"异步模式","type":"switch","defaultValue":true,"advanced":true}
  ]'
)
on conflict (id)
do update set
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
  'pm-cangyuan-gpt-image-2-4k',
  'cangyuan',
  'cy-img2-gpt-image-2-4k',
  'image_generation',
  'image',
  'active',
  '{
    "display_model":"gpt-image-2-4k",
    "endpoint_path":"/v1/images/generations",
    "async_poll":true,
    "poll_status_path":"/v1/images/generations/{task_id}",
    "poll_interval_ms":1500,
    "compatible":"openai-gpt-image",
    "supports":["prompt","size","n","quality","background","output_format","output_compression","moderation","stream","partial_images","async"]
  }',
  'Cangyuan gpt-image-2-4k text-to-image async mode.'
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
  'ch-cangyuan-gpt-image-2-4k',
  'tikpan.image.gpt-image-2-4k',
  'cangyuan',
  'pm-cangyuan-gpt-image-2-4k',
  'primary',
  'active',
  100,
  1,
  0.08,
  0.08,
  'image',
  18.0,
  98.00,
  '["prompt","size","n","quality","background","output_format","output_compression","moderation","stream","partial_images","async"]',
  120000
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
  ('map-cy-img2-model', 'ch-cangyuan-gpt-image-2-4k', 'model', 'model', 'default', '{}', '"cy-img2-gpt-image-2-4k"', 'Model is set by provider_model automatically; kept for audit clarity.'),
  ('map-cy-img2-prompt', 'ch-cangyuan-gpt-image-2-4k', 'prompt', 'prompt', 'direct', '{}', null, 'Prompt text.'),
  ('map-cy-img2-size', 'ch-cangyuan-gpt-image-2-4k', 'size', 'size', 'direct', '{}', '"auto"', 'OpenAI official size values.'),
  ('map-cy-img2-n', 'ch-cangyuan-gpt-image-2-4k', 'n', 'n', 'direct', '{}', '1', 'Image count, 1-10.'),
  ('map-cy-img2-quality', 'ch-cangyuan-gpt-image-2-4k', 'quality', 'quality', 'direct', '{}', '"auto"', 'auto / low / medium / high.'),
  ('map-cy-img2-background', 'ch-cangyuan-gpt-image-2-4k', 'background', 'background', 'direct', '{}', '"opaque"', 'gpt-image-2 does not support transparent.'),
  ('map-cy-img2-output-format', 'ch-cangyuan-gpt-image-2-4k', 'output_format', 'output_format', 'direct', '{}', '"png"', 'png / jpeg / webp.'),
  ('map-cy-img2-output-compression', 'ch-cangyuan-gpt-image-2-4k', 'output_compression', 'output_compression', 'direct', '{}', '100', 'JPEG/WebP compression, 0-100.'),
  ('map-cy-img2-moderation', 'ch-cangyuan-gpt-image-2-4k', 'moderation', 'moderation', 'direct', '{}', '"auto"', 'auto / low.'),
  ('map-cy-img2-stream', 'ch-cangyuan-gpt-image-2-4k', 'stream', 'stream', 'direct', '{}', 'false', '4K async recommendation: false.'),
  ('map-cy-img2-partial', 'ch-cangyuan-gpt-image-2-4k', 'partial_images', 'partial_images', 'direct', '{}', '0', '0-3 partial previews when stream is enabled.'),
  ('map-cy-img2-async', 'ch-cangyuan-gpt-image-2-4k', 'async', 'async', 'direct', '{}', 'true', 'Cangyuan image generation requires async true.')
on conflict (channel_id, platform_param_key)
do update set
  upstream_param_key = excluded.upstream_param_key,
  transform = excluded.transform,
  value_map = excluded.value_map,
  default_value = excluded.default_value,
  note = excluded.note;

commit;
