-- Configurable creator-facing model menu.
--
-- Product rule:
--   Display names can change freely.
--   Internal ids, category keys, and model slugs should stay stable because
--   tasks, billing, routing, analytics, and historical links depend on them.

begin;

alter table platform_models
  add column if not exists slug text,
  add column if not exists display_name text;

update platform_models
set
  slug = coalesce(slug, regexp_replace(lower(id), '[^a-z0-9]+', '-', 'g')),
  display_name = coalesce(display_name, name);

alter table platform_models
  alter column slug set not null,
  alter column display_name set not null;

create unique index if not exists platform_models_slug_idx on platform_models(slug);

create table if not exists model_categories (
  id text primary key,
  key text not null unique,
  name text not null,
  icon text,
  sort_order integer not null default 0,
  visible boolean not null default true,
  parent_id text references model_categories(id) on delete set null,
  status text not null default 'published'
    check (status in ('draft', 'published', 'archived')),
  aliases jsonb not null default '[]',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists model_categories_visible_sort_idx on model_categories(visible, sort_order, key);
create index if not exists model_categories_parent_idx on model_categories(parent_id);

create table if not exists platform_model_category_assignments (
  id text primary key,
  platform_model_id text not null references platform_models(id) on delete cascade,
  category_id text not null references model_categories(id) on delete cascade,
  sort_order integer not null default 0,
  is_primary boolean not null default false,
  created_at timestamptz not null default now(),
  unique (platform_model_id, category_id)
);

create index if not exists platform_model_category_category_idx
  on platform_model_category_assignments(category_id, sort_order, platform_model_id);

create table if not exists platform_model_aliases (
  id text primary key,
  platform_model_id text not null references platform_models(id) on delete cascade,
  alias text not null,
  kind text not null default 'search'
    check (kind in ('search', 'legacy', 'marketing', 'upstream')),
  created_at timestamptz not null default now(),
  unique (platform_model_id, alias)
);

create index if not exists platform_model_aliases_alias_idx on platform_model_aliases(alias);

insert into model_categories (id, key, name, icon, sort_order, visible, status, aliases)
values
  ('cat-all', 'all', '全部', 'sparkles', 0, true, 'published', '[]'),
  ('cat-image', 'image', '图片', 'image', 10, true, 'published', '["图像","AI 图片","图片创作"]'),
  ('cat-video', 'video', '视频', 'clapperboard', 20, true, 'published', '["AI 视频","短视频"]'),
  ('cat-chat', 'chat', '文案', 'file-text', 30, true, 'published', '["对话","文本","文案创作"]'),
  ('cat-audio', 'audio', '音频', 'audio-lines', 40, true, 'published', '["配音","声音"]'),
  ('cat-workflow', 'workflow', '工作流', 'layers-3', 50, true, 'published', '["自动化","内容套装"]')
on conflict (key)
do update set
  name = excluded.name,
  icon = excluded.icon,
  sort_order = excluded.sort_order,
  visible = excluded.visible,
  status = excluded.status,
  aliases = excluded.aliases,
  updated_at = now();

insert into platform_model_category_assignments (id, platform_model_id, category_id, sort_order, is_primary)
select
  'assign-' || regexp_replace(pm.id, '[^a-zA-Z0-9_-]+', '-', 'g') || '-' || c.key,
  pm.id,
  c.id,
  pm.sort_order,
  true
from platform_models pm
join model_categories c on c.key = pm.modality
on conflict (platform_model_id, category_id)
do update set
  sort_order = excluded.sort_order,
  is_primary = excluded.is_primary;

insert into platform_model_aliases (id, platform_model_id, alias, kind)
select
  'alias-' || regexp_replace(pm.id, '[^a-zA-Z0-9_-]+', '-', 'g') || '-slug',
  pm.id,
  pm.slug,
  'legacy'
from platform_models pm
on conflict (platform_model_id, alias) do nothing;

insert into platform_model_aliases (id, platform_model_id, alias, kind)
select
  'alias-' || regexp_replace(pm.id, '[^a-zA-Z0-9_-]+', '-', 'g') || '-name',
  pm.id,
  pm.name,
  'search'
from platform_models pm
on conflict (platform_model_id, alias) do nothing;

commit;
