begin;

alter table tasks
  add column batch_id text,
  add column batch_title text,
  add column batch_item_id text;

create index tasks_batch_user_idx
  on tasks(user_id, batch_id, created_at desc)
  where batch_id is not null;

commit;
