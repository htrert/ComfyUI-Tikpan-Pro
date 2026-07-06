-- Optional seed: Tikpan gpt-image-2 image edit V2.
--
-- Runtime secret is NOT stored here. Set:
--   TIKPAN_PROVIDER_SECRETS='{"tikpan":"sk-your-tikpan-token"}'
--
-- Billing model:
--   model_channels.sale_price is the unit price per output image.
--   The API estimates and freezes sale_price * input.n, then settles on success
--   or releases the frozen amount on failure/cancel.

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
  'tikpan',
  'Tikpan',
  'relay',
  'https://tikpan.com',
  'bearer',
  null,
  'active',
  60,
  2,
  2200,
  98.00,
  600000
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
  'tikpan.image.gpt-image-2-edit-v2',
  'GPT Image 2 Edit V2',
  'Image 2 Edit',
  'image',
  'pro',
  'Tikpan gpt-image-2 image editing endpoint for instruction-based edits, masks, and reference images.',
  '["image editing","product retouching","background replacement","local inpainting"]',
  true,
  true,
  '0.60 Tokens / image',
  'Long-running edit task',
  11,
  '[
    {"key":"prompt","label":"Edit instruction","type":"textarea","required":true},
    {"key":"main_image_url","label":"Main image URL","type":"text","required":true,"helper":"HTTP(S) image URL or data URL."},
    {"key":"reference_image_1_url","label":"Reference image 1","type":"text","advanced":true},
    {"key":"reference_image_2_url","label":"Reference image 2","type":"text","advanced":true},
    {"key":"reference_image_3_url","label":"Reference image 3","type":"text","advanced":true},
    {"key":"reference_image_4_url","label":"Reference image 4","type":"text","advanced":true},
    {"key":"mask_url","label":"Mask image URL","type":"text","advanced":true,"helper":"White area is edited; black area is preserved."},
    {"key":"n","label":"Output count","type":"slider","defaultValue":1,"min":1,"max":10,"step":1},
    {"key":"size","label":"Size","type":"select","defaultValue":"auto","options":["auto","1024x1024","1536x1024","1024x1536","2048x2048","2048x1152","1152x2048","3840x2160","2160x3840"]},
    {"key":"quality","label":"Quality","type":"segmented","defaultValue":"medium","options":["low","medium","high"]},
    {"key":"background","label":"Background","type":"segmented","defaultValue":"auto","options":["auto","opaque"]},
    {"key":"moderation","label":"Moderation","type":"segmented","defaultValue":"auto","options":["auto","low"],"advanced":true}
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
  'pm-tikpan-gpt-image-2-edit-v2',
  'tikpan',
  'gpt-image-2',
  'image_edit',
  'image',
  'active',
  '{
    "display_model":"gpt-image-2",
    "endpoint_path":"/v1/images/edits",
    "request_format":"multipart",
    "compatible":"openai-image-edit",
    "supports":["prompt","main_image_url","reference_image_1_url","reference_image_2_url","reference_image_3_url","reference_image_4_url","mask_url","n","size","quality","background","moderation"]
  }',
  'Tikpan gpt-image-2 image edit V2 multipart endpoint.'
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
  'ch-tikpan-gpt-image-2-edit-v2',
  'tikpan.image.gpt-image-2-edit-v2',
  'tikpan',
  'pm-tikpan-gpt-image-2-edit-v2',
  'primary',
  'active',
  100,
  1,
  0.45,
  0.60,
  'image',
  45.0,
  98.00,
  '["prompt","main_image_url","reference_image_1_url","reference_image_2_url","reference_image_3_url","reference_image_4_url","mask_url","n","size","quality","background","moderation"]',
  600000
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
  ('map-tp-edit-v2-model', 'ch-tikpan-gpt-image-2-edit-v2', 'model', 'model', 'default', '{}', '"gpt-image-2"', 'Model is fixed for this channel.'),
  ('map-tp-edit-v2-prompt', 'ch-tikpan-gpt-image-2-edit-v2', 'prompt', 'prompt', 'direct', '{}', null, 'Edit instruction.'),
  ('map-tp-edit-v2-main-image', 'ch-tikpan-gpt-image-2-edit-v2', 'main_image_url', 'main_image_url', 'direct', '{}', null, 'Downloaded and sent as multipart image.'),
  ('map-tp-edit-v2-ref-1', 'ch-tikpan-gpt-image-2-edit-v2', 'reference_image_1_url', 'reference_image_1_url', 'direct', '{}', null, 'Downloaded and sent as additional multipart image.'),
  ('map-tp-edit-v2-ref-2', 'ch-tikpan-gpt-image-2-edit-v2', 'reference_image_2_url', 'reference_image_2_url', 'direct', '{}', null, 'Downloaded and sent as additional multipart image.'),
  ('map-tp-edit-v2-ref-3', 'ch-tikpan-gpt-image-2-edit-v2', 'reference_image_3_url', 'reference_image_3_url', 'direct', '{}', null, 'Downloaded and sent as additional multipart image.'),
  ('map-tp-edit-v2-ref-4', 'ch-tikpan-gpt-image-2-edit-v2', 'reference_image_4_url', 'reference_image_4_url', 'direct', '{}', null, 'Downloaded and sent as additional multipart image.'),
  ('map-tp-edit-v2-mask', 'ch-tikpan-gpt-image-2-edit-v2', 'mask_url', 'mask_url', 'direct', '{}', null, 'Downloaded and sent as multipart mask.'),
  ('map-tp-edit-v2-n', 'ch-tikpan-gpt-image-2-edit-v2', 'n', 'n', 'direct', '{}', '1', 'Output count, 1-10.'),
  ('map-tp-edit-v2-size', 'ch-tikpan-gpt-image-2-edit-v2', 'size', 'size', 'direct', '{}', '"auto"', 'Output size.'),
  ('map-tp-edit-v2-quality', 'ch-tikpan-gpt-image-2-edit-v2', 'quality', 'quality', 'direct', '{}', '"medium"', 'low / medium / high.'),
  ('map-tp-edit-v2-background', 'ch-tikpan-gpt-image-2-edit-v2', 'background', 'background', 'direct', '{}', '"auto"', 'auto / opaque.'),
  ('map-tp-edit-v2-moderation', 'ch-tikpan-gpt-image-2-edit-v2', 'moderation', 'moderation', 'direct', '{}', '"auto"', 'auto / low.')
on conflict (channel_id, platform_param_key)
do update set
  upstream_param_key = excluded.upstream_param_key,
  transform = excluded.transform,
  value_map = excluded.value_map,
  default_value = excluded.default_value,
  note = excluded.note;

commit;
