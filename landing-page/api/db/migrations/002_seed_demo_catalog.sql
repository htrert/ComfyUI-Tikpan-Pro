-- Seed data matching the current in-memory API demo catalog.

begin;

insert into users (
  id,
  display_name,
  email,
  status
)
values (
  'demo_user',
  'Demo User',
  'demo@tikpan.local',
  'active'
);

insert into billing_plans (
  id,
  name,
  monthly_task_limit,
  monthly_spend_limit,
  rate_limit_per_minute,
  concurrency_limit,
  features,
  status
)
values (
  'starter',
  'Starter',
  120,
  30,
  20,
  2,
  '["image","video","chat"]',
  'active'
);

insert into user_subscriptions (
  id,
  user_id,
  plan_id,
  status,
  renews_at
)
values (
  'sub_demo_starter',
  'demo_user',
  'starter',
  'active',
  now() + interval '30 days'
);

insert into wallets (
  user_id,
  currency,
  balance,
  frozen
)
values (
  'demo_user',
  'CNY',
  8.8,
  0
);

insert into wallet_ledger (
  id,
  user_id,
  task_id,
  type,
  amount,
  balance_after,
  frozen_after,
  note
)
values (
  'ledger_seed_balance',
  'demo_user',
  null,
  'top_up',
  8.8,
  8.8,
  0,
  'Demo initial balance'
);

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
  success_rate
)
values
  ('relay-a', 'Relay A', 'relay', 'https://api.relay-a.example/v1', 'bearer', 'demo-encrypted-relay-a', 'active', 600, 16, 820, 98.2),
  ('relay-b', 'Relay B', 'relay', 'https://gateway.relay-b.example', 'custom_header', 'demo-encrypted-relay-b', 'active', 420, 10, 640, 97.5),
  ('official-c', 'Official C', 'official', 'https://api.official-c.example', 'bearer', 'demo-encrypted-official-c', 'degraded', 180, 5, 1280, 94.8);

insert into provider_models (
  id,
  provider_id,
  upstream_model_name,
  endpoint_type,
  modality,
  status,
  raw_capabilities
)
values
  ('pm-image-a', 'relay-a', 'gpt-image-1', 'image_generation', 'image', 'active', '{"supports":["prompt","aspect_ratio","quality","seed","reference_image"]}'),
  ('pm-image-b', 'relay-b', 'openai/gpt-image-1', 'image_generation', 'image', 'active', '{"supports":["prompt","aspect_ratio","quality","negative_prompt"]}'),
  ('pm-video-a', 'relay-a', 'seedance-video-fast', 'video_generation', 'video', 'active', '{"supports":["prompt","duration","resolution","first_frame"]}'),
  ('pm-chat-c', 'official-c', 'gpt-4o-mini', 'chat_completions', 'chat', 'degraded', '{"supports":["message","tone","stream"]}');

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
values
  (
    'tikpan.image.pro',
    'Image Generation Pro',
    'Image Pro',
    'image',
    'pro',
    'Generate marketing-ready product images, posters, covers, and social assets from a prompt.',
    '["product hero image","ad poster","social cover","portrait"]',
    true,
    true,
    '0.18 CNY / request',
    '8-15 seconds',
    10,
    '[
      {"key":"prompt","label":"Image description","type":"textarea","required":true},
      {"key":"aspect_ratio","label":"Aspect ratio","type":"segmented","defaultValue":"1:1","options":["1:1","3:4","4:3","16:9"]},
      {"key":"quality","label":"Quality","type":"select","defaultValue":"balanced","options":["fast","balanced","high"]},
      {"key":"reference_image","label":"Reference image","type":"file","advanced":true},
      {"key":"negative_prompt","label":"Negative prompt","type":"text","advanced":true},
      {"key":"simulate_failover","label":"Simulate primary timeout","type":"switch","defaultValue":false,"advanced":true}
    ]'
  ),
  (
    'tikpan.video.story',
    'Video Generation Story',
    'Video Story',
    'video',
    'ultra',
    'Turn scripts, images, or concepts into short video assets.',
    '["image to video","product showcase","ad short","motion poster"]',
    true,
    false,
    '1.20 CNY / 5 seconds',
    '35-90 seconds',
    20,
    '[
      {"key":"prompt","label":"Video description","type":"textarea","required":true},
      {"key":"duration","label":"Duration","type":"segmented","defaultValue":"5","options":["5","8","10"]},
      {"key":"resolution","label":"Resolution","type":"select","defaultValue":"720p","options":["720p","1080p"]},
      {"key":"first_frame","label":"First frame","type":"file","advanced":true},
      {"key":"motion","label":"Motion strength","type":"slider","defaultValue":6,"advanced":true}
    ]'
  ),
  (
    'tikpan.chat.assistant',
    'Chat Assistant',
    'Assistant',
    'chat',
    'standard',
    'A practical text assistant for copywriting, analysis, customer support, and knowledge workflows.',
    '["copy polishing","script expansion","knowledge Q&A","support reply"]',
    true,
    false,
    'usage based',
    'real time',
    30,
    '[
      {"key":"message","label":"Message","type":"textarea","required":true},
      {"key":"tone","label":"Tone","type":"select","defaultValue":"natural","options":["natural","pro","marketing"]},
      {"key":"stream","label":"Stream","type":"switch","defaultValue":true,"advanced":true}
    ]'
  );

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
  supports
)
values
  ('ch-image-a', 'tikpan.image.pro', 'relay-a', 'pm-image-a', 'primary', 'active', 60, 1, 0.11, 0.18, 'request', 9.2, 98.7, '["prompt","aspect_ratio","quality","seed","reference_image"]'),
  ('ch-image-b', 'tikpan.image.pro', 'relay-b', 'pm-image-b', 'backup', 'active', 30, 2, 0.13, 0.18, 'request', 11.8, 97.9, '["prompt","aspect_ratio","quality","negative_prompt"]'),
  ('ch-video-a', 'tikpan.video.story', 'relay-a', 'pm-video-a', 'fast', 'active', 55, 1, 0.82, 1.2, 'second', 42, 96.8, '["prompt","duration","resolution","first_frame"]'),
  ('ch-chat-c', 'tikpan.chat.assistant', 'official-c', 'pm-chat-c', 'cheap', 'degraded', 20, 3, 0.8, 1.6, 'million_tokens', 1.6, 94.8, '["message","tone","stream"]');

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
  ('map-image-a-prompt', 'ch-image-a', 'prompt', 'prompt', 'direct', '{}', null, 'forward prompt'),
  ('map-image-a-ratio', 'ch-image-a', 'aspect_ratio', 'size', 'map', '{"1:1":"1024x1024","3:4":"1024x1365","4:3":"1365x1024","16:9":"1536x864"}', null, 'map common ratio to size'),
  ('map-image-a-quality', 'ch-image-a', 'quality', 'quality', 'map', '{"fast":"standard","balanced":"hd","high":"ultra"}', null, 'map quality'),
  ('map-image-a-negative', 'ch-image-a', 'negative_prompt', null, 'omit', '{}', null, 'unsupported by channel'),
  ('map-image-b-prompt', 'ch-image-b', 'prompt', 'input_prompt', 'direct', '{}', null, 'rename prompt field'),
  ('map-image-b-ratio', 'ch-image-b', 'aspect_ratio', 'image_size', 'map', '{"1:1":"square_hd","3:4":"portrait_4_3","4:3":"landscape_4_3","16:9":"landscape_16_9"}', null, 'map ratio'),
  ('map-image-b-quality', 'ch-image-b', 'quality', 'steps', 'map', '{"fast":20,"balanced":30,"high":40}', null, 'map quality to steps'),
  ('map-image-b-seed', 'ch-image-b', 'seed', null, 'omit', '{}', null, 'unsupported by channel'),
  ('map-video-a-prompt', 'ch-video-a', 'prompt', 'prompt', 'direct', '{}', null, 'forward prompt'),
  ('map-video-a-duration', 'ch-video-a', 'duration', 'seconds', 'direct', '{}', null, 'duration seconds'),
  ('map-video-a-resolution', 'ch-video-a', 'resolution', 'quality', 'map', '{"720p":"standard","1080p":"high"}', null, 'map resolution'),
  ('map-video-a-motion', 'ch-video-a', 'motion', 'motion_strength', 'default', '{}', '6', 'default motion strength'),
  ('map-chat-c-message', 'ch-chat-c', 'message', 'messages', 'template', '{}', null, 'wrap message array'),
  ('map-chat-c-tone', 'ch-chat-c', 'tone', 'system', 'template', '{}', null, 'build system tone'),
  ('map-chat-c-stream', 'ch-chat-c', 'stream', 'stream', 'direct', '{}', null, 'stream flag');

insert into platform_api_keys (
  id,
  user_id,
  name,
  prefix,
  secret_hash,
  status,
  scopes
)
values (
  'key_demo_default',
  'demo_user',
  'Default Demo Key',
  'tk_demo',
  crypt('tk_demo_sk_live_demo123456', gen_salt('bf')),
  'active',
  '["tasks:create","wallet:read"]'
);

commit;
