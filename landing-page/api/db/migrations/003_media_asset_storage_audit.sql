-- Persist media storage provenance for generated output assets.

begin;

alter table media_assets
  add column source_url text,
  add column storage_mode text not null default 'local'
    check (storage_mode in ('local', 's3'));

create index media_assets_storage_mode_idx on media_assets(storage_mode, created_at desc);

commit;
