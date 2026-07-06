-- Add task claim fields for queue workers and multi-instance safety.

begin;

alter table tasks
  add column worker_id text,
  add column locked_until timestamptz,
  add column lock_version integer not null default 0 check (lock_version >= 0);

create index tasks_worker_claim_idx
  on tasks(status, locked_until, created_at)
  where status in ('queued', 'running', 'saving_media') and finished_at is null;

commit;
