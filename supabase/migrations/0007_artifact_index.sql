-- 0007_artifact_index.sql — one-request index of the nightly-artifacts bucket.
--
-- NOT YET PUSHED (2026-09-16). Apply with `supabase db push` from the repo root.
--
-- Why: `bootstrap.overlay_artifacts` needs every object under
-- nightly-artifacts/<run_id>/<campaign>/<relpath>. The Storage list endpoint on
-- this project (storage-api 1.77.5) is folder-at-a-time — no recursive or
-- list-v2 form — so store.list_artifacts() walked one request per folder per
-- run (471 requests / 63 s for 140 runs on 2026-09-16, and a bare call from a
-- script hit the 60 s read timeout). The bucket's rows already sit in
-- storage.objects, which nightly_agent may SELECT under the artifacts_read
-- policy (0003); this function is that SELECT, reachable through PostgREST
-- because it lives in `public`. SECURITY INVOKER: each role sees exactly the
-- rows its storage policies allow (release_reader has no artifacts policy and
-- is not granted execute).
--
-- store.SupabaseStore.list_artifacts() calls this first and falls back to the
-- per-folder walk when PostgREST reports the function missing (PGRST202), so
-- a bootstrap running against a project without this migration is slower,
-- not wrong.

create or replace function public.artifact_index()
returns table (
  key        text,
  created_at timestamptz,
  size       bigint,
  etag       text
)
language sql
stable
security invoker
set search_path = ''
as $$
  select
    o.name                                             as key,
    o.created_at                                       as created_at,
    coalesce(nullif(o.metadata->>'size', '')::bigint,
             nullif(o.metadata->>'contentLength', '')::bigint,
             0)                                        as size,
    nullif(trim(both '"' from (o.metadata->>'eTag')), '') as etag
  from storage.objects o
  where o.bucket_id = 'nightly-artifacts'
  order by o.created_at, o.name
$$;

comment on function public.artifact_index() is
  'Every nightly-artifacts object as {key, created_at, size, etag} — key is <run_id>/<campaign>/<relpath>, etag the Storage md5 (quotes stripped). Read by bootstrap.overlay_artifacts; SECURITY INVOKER so storage policies decide visibility.';

revoke all on function public.artifact_index() from public;
grant execute on function public.artifact_index() to nightly_agent, service_role;
-- (the `operator` role has no usage on schema storage — 0003 — so it is not granted; the Mac's
--  secret key runs as service_role, which bypasses RLS and sees every row.)

notify pgrst, 'reload schema';
