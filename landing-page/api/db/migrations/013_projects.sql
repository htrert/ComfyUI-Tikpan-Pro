begin;

create table projects (
  id text primary key,
  user_id text not null references users(id),
  name text not null,
  type text not null default 'general',
  status text not null default 'active',
  description text not null default '',
  cover_url text,
  settings jsonb not null default '{}',
  tags jsonb not null default '[]',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  archived_at timestamptz
);

alter table tasks add column project_id text references projects(id);
alter table tasks add column project_name text;

create index projects_user_updated_idx on projects(user_id, updated_at desc);
create index projects_user_status_idx on projects(user_id, status);
create index tasks_project_created_idx on tasks(project_id, created_at desc);

insert into projects (
  id, user_id, name, type, status, description, settings, tags, created_at, updated_at
)
values
  (
    'proj_campaign_skin_2026',
    'demo_user',
    'Summer skincare campaign',
    'image_campaign',
    'active',
    'Product hero images, social covers, and short video prompts for a seasonal launch.',
    '{"defaultModel":"tikpan.image.gpt-image-2-4k","routeMode":"quality","brandTone":"clean, bright, premium"}',
    '["commerce","campaign","social"]',
    '2026-07-04T09:30:00Z',
    '2026-07-05T16:20:00Z'
  ),
  (
    'proj_storyboard_demo',
    'demo_user',
    'Product video storyboard',
    'video_storyboard',
    'draft',
    'Shot list, image references, and generation tasks for a 10 second product reel.',
    '{"defaultModel":"tikpan.chat.claude-fable-5","routeMode":"balanced","duration":"10s"}',
    '["video","storyboard"]',
    '2026-07-03T13:10:00Z',
    '2026-07-04T10:45:00Z'
  )
on conflict (id) do nothing;

commit;
