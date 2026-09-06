-- 0003_storage.sql — buckets and Storage policies.
--
-- Buckets (all private):
--   releases           weekly bundle releases/<tag>/…  read: release_reader, nightly_agent
--                      write: the Mac's secret key only (service_role bypasses RLS)
--   nightly-artifacts  <run_id>/<campaign>/<relpath>   insert: nightly_agent, key must start
--                      with a run_id that exists in public.runs; read: nightly_agent
--                      (bootstrap overlays artifacts since the release); no update/delete
--   site-staging       <run_id>/…                      insert only: nightly_agent; promotion
--                      reads with the Mac's key
--   site               promoted pages                  Mac / promotion only
--
-- Storage runs its queries as the JWT role, so custom roles need table
-- privileges on storage.objects AND a policy. Overwrite (x-upsert) needs
-- UPDATE — never granted — and there is no DELETE anywhere below.

insert into storage.buckets (id, name, public)
values
  ('releases',          'releases',          false),
  ('nightly-artifacts', 'nightly-artifacts', false),
  ('site-staging',      'site-staging',      false),
  ('site',              'site',              false)
on conflict (id) do nothing;

grant usage on schema storage to nightly_agent, release_reader;
grant select on storage.buckets to nightly_agent, release_reader;
grant select, insert on storage.objects to nightly_agent;
grant select on storage.objects to release_reader;
grant execute on all functions in schema storage to nightly_agent, release_reader;

-- releases: read-only for the reader roles --------------------------------
create policy releases_read on storage.objects for select to release_reader, nightly_agent
  using (bucket_id = 'releases');

-- nightly-artifacts: insert under an existing run id, read back -------------
create policy artifacts_insert_own_run on storage.objects for insert to nightly_agent
  with check (
    bucket_id = 'nightly-artifacts'
    and coalesce(array_length(storage.foldername(name), 1), 0) >= 2          -- <run_id>/<campaign>/<file>
    and exists (select 1 from public.runs r where r.run_id::text = (storage.foldername(name))[1])
  );
create policy artifacts_read on storage.objects for select to nightly_agent
  using (bucket_id = 'nightly-artifacts');

-- site-staging: insert under an existing run id; the agent never reads it back
create policy staging_insert_own_run on storage.objects for insert to nightly_agent
  with check (
    bucket_id = 'site-staging'
    and coalesce(array_length(storage.foldername(name), 1), 0) >= 1          -- <run_id>/<file>
    and exists (select 1 from public.runs r where r.run_id::text = (storage.foldername(name))[1])
  );
-- Storage returns the inserted row, which needs a matching SELECT policy.
create policy staging_read_own_run on storage.objects for select to nightly_agent
  using (bucket_id = 'site-staging');

-- site: no policies → service_role only.
