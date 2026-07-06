begin;

create table asset_metadata (
  task_id text not null references tasks(id) on delete cascade,
  user_id text not null references users(id),
  title text not null default '',
  note text not null default '',
  favorite boolean not null default false,
  review_status text not null default 'candidate',
  tags jsonb not null default '[]',
  collections jsonb not null default '[]',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (task_id, user_id)
);

create index asset_metadata_user_updated_idx on asset_metadata(user_id, updated_at desc);
create index asset_metadata_review_status_idx on asset_metadata(user_id, review_status);

commit;
