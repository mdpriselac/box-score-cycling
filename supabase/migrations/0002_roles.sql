-- 0002_roles.sql — Postgres roles, grants and row-level security.
--
-- Key model (checked against supabase.com/docs, 2026-09): API requests carry a
-- publishable/secret key on the `apikey` header for the gateway and a JWT on
-- `Authorization: Bearer`. PostgREST and Storage `SET ROLE` to the JWT's
-- `role` claim, which may be ANY Postgres role that has been GRANTed to
-- `authenticator`. So the agent's key is a JWT minted for `nightly_agent`
-- (supabase/mint_keys.py) — never the secret key, which maps to
-- `service_role` and bypasses RLS.
--
-- Roles
--   nightly_agent   the cloud agent: INSERT on the ledger, SELECT on the registry
--                   and the ledger it writes, no UPDATE/DELETE/TRUNCATE, no DDL.
--   release_reader  read-only consumer of the releases table + bucket.
--   operator        the human privilege set. Humans reach it through Supabase
--                   Auth (role `authenticated`) gated by public.is_operator();
--                   a JWT minted with role = operator gets it directly.
--   service_role    the Mac's secret key: registry writes, release uploads,
--                   promotion. Bypasses RLS; never leaves the Mac.

-- ---------------------------------------------------------------------------
-- roles
-- ---------------------------------------------------------------------------

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'nightly_agent') then
    create role nightly_agent nologin noinherit nocreatedb nocreaterole nosuperuser nobypassrls;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'release_reader') then
    create role release_reader nologin noinherit nocreatedb nocreaterole nosuperuser nobypassrls;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'operator') then
    create role operator nologin noinherit nocreatedb nocreaterole nosuperuser nobypassrls;
  end if;
end $$;

-- PostgREST/Storage can only SET ROLE to roles granted to authenticator.
grant nightly_agent  to authenticator;
grant release_reader to authenticator;
grant operator       to authenticator;

-- ---------------------------------------------------------------------------
-- strip Supabase's permissive defaults on public
-- ---------------------------------------------------------------------------

-- New tables in public are granted to anon/authenticated/service_role by the
-- project's default privileges. The control plane is not a public API.
revoke all on all tables    in schema public from anon, authenticated;
revoke all on all sequences in schema public from anon, authenticated;
revoke all on all functions in schema public from anon, authenticated;
alter default privileges for role postgres in schema public revoke all on tables    from anon, authenticated;
alter default privileges for role postgres in schema public revoke all on sequences from anon, authenticated;
alter default privileges for role postgres in schema public revoke all on functions from anon, authenticated;

grant usage on schema public to nightly_agent, release_reader, operator;

-- ---------------------------------------------------------------------------
-- operator identity
-- ---------------------------------------------------------------------------

-- True for a JWT minted with role = operator, or for a Supabase Auth user whose
-- email / user id is in public.operators. SECURITY DEFINER so callers need no
-- privilege on operators itself (inside a definer function current_user is the
-- owner, so the caller's role is read from the request's JWT claims / the
-- `role` GUC that SET ROLE leaves behind). Never granted to anon.
create or replace function public.is_operator()
returns boolean
language sql stable security definer
set search_path = ''
as $$
  select coalesce(current_setting('request.jwt.claims', true)::jsonb ->> 'role', '') = 'operator'
      or coalesce(current_setting('role', true), '') = 'operator'
      or exists (
           select 1 from public.operators o
           where (o.user_id is not null and o.user_id = auth.uid())
              or lower(o.email) = lower(coalesce(auth.jwt() ->> 'email', ''))
         );
$$;
revoke all on function public.is_operator() from public, anon;
grant execute on function public.is_operator() to operator, authenticated, service_role;

revoke all on function public.whoami() from public, anon;
grant execute on function public.whoami() to nightly_agent, release_reader, operator, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- grants: nightly_agent
-- ---------------------------------------------------------------------------

grant insert on
  public.runs, public.run_steps, public.pcs_raw, public.predictions, public.prediction_log,
  public.day_key_decisions, public.editorial_drafts, public.operator_tasks, public.crosswalk_proposals
to nightly_agent;

-- Registry reads (+ the approvals projection without approver / private notes),
-- and the ledger the agent itself writes: it needs run_id back from INSERT …
-- RETURNING, the approved day key, open tasks and pending proposals, and
-- Postgres needs SELECT on prediction_log for the idempotent
-- INSERT … ON CONFLICT (run_key, rider_id) DO NOTHING (arbiter index read).
grant select on
  public.calendar, public.campaigns, public.stages, public.releases, public.crosswalk,
  public.approvals_view,
  public.runs, public.run_steps, public.run_status, public.predictions, public.prediction_log,
  public.day_key_decisions, public.editorial_drafts, public.operator_tasks, public.crosswalk_proposals
to nightly_agent;

-- identity columns need the sequence
grant usage, select on all sequences in schema public to nightly_agent;

-- ---------------------------------------------------------------------------
-- grants: release_reader
-- ---------------------------------------------------------------------------

grant select on public.releases to release_reader;

-- ---------------------------------------------------------------------------
-- grants: operator (+ authenticated, gated by RLS through is_operator())
-- ---------------------------------------------------------------------------

grant select on all tables in schema public to operator, authenticated;
revoke select on public.operators from authenticated;          -- allow-list stays service-role only
grant usage, select on all sequences in schema public to operator, authenticated;

grant insert on public.approvals, public.day_key_decisions, public.operator_tasks, public.crosswalk
to operator, authenticated;
grant update (resolved, resolved_by, resolved_at, resolution) on public.operator_tasks to operator, authenticated;
grant update on public.crosswalk to operator, authenticated;
grant update (status, resolved_by, resolved_at) on public.crosswalk_proposals to operator, authenticated;
grant update (approved, approved_by, approved_at) on public.releases to operator, authenticated;
grant update (approved_by, approved_at) on public.day_key_decisions, public.editorial_drafts to operator, authenticated;

-- ---------------------------------------------------------------------------
-- row-level security
-- ---------------------------------------------------------------------------

alter table public.calendar            enable row level security;
alter table public.campaigns           enable row level security;
alter table public.stages              enable row level security;
alter table public.releases            enable row level security;
alter table public.runs                enable row level security;
alter table public.run_steps           enable row level security;
alter table public.pcs_raw             enable row level security;
alter table public.predictions         enable row level security;
alter table public.prediction_log      enable row level security;
alter table public.day_key_decisions   enable row level security;
alter table public.editorial_drafts    enable row level security;
alter table public.operator_tasks      enable row level security;
alter table public.crosswalk           enable row level security;
alter table public.crosswalk_proposals enable row level security;
alter table public.approvals           enable row level security;
alter table public.operators           enable row level security;
alter table public.reconciliation      enable row level security;

-- views run with the privileges of their owner (postgres) — approvals_view
-- therefore projects approvals for the agent without a policy on approvals;
-- run_status is a plain projection of tables the agent may read anyway.

-- -- nightly_agent: reads --------------------------------------------------
create policy agent_read_calendar   on public.calendar            for select to nightly_agent using (true);
create policy agent_read_campaigns  on public.campaigns           for select to nightly_agent using (true);
create policy agent_read_stages     on public.stages              for select to nightly_agent using (true);
create policy agent_read_releases   on public.releases            for select to nightly_agent using (true);
create policy agent_read_crosswalk  on public.crosswalk           for select to nightly_agent using (true);
create policy agent_read_runs       on public.runs                for select to nightly_agent using (true);
create policy agent_read_run_steps  on public.run_steps           for select to nightly_agent using (true);
create policy agent_read_predictions on public.predictions        for select to nightly_agent using (true);
create policy agent_read_prediction_log on public.prediction_log  for select to nightly_agent using (true);
create policy agent_read_day_keys   on public.day_key_decisions   for select to nightly_agent using (true);
create policy agent_read_drafts     on public.editorial_drafts    for select to nightly_agent using (true);
create policy agent_read_tasks      on public.operator_tasks      for select to nightly_agent using (true);
create policy agent_read_proposals  on public.crosswalk_proposals for select to nightly_agent using (true);

-- -- nightly_agent: append-only inserts --------------------------------------
create policy agent_insert_runs on public.runs for insert to nightly_agent
  with check (host = 'cloud' and state = 'started');
create policy agent_insert_run_steps on public.run_steps for insert to nightly_agent
  with check (true);
create policy agent_insert_pcs_raw on public.pcs_raw for insert to nightly_agent
  with check (true);
create policy agent_insert_predictions on public.predictions for insert to nightly_agent
  with check (true);
create policy agent_insert_prediction_log on public.prediction_log for insert to nightly_agent
  with check (true);
-- proposals only: a human key carries approved_by, and the agent may never set it
create policy agent_insert_day_keys on public.day_key_decisions for insert to nightly_agent
  with check (approved_by is null and approved_at is null and author <> 'human');
create policy agent_insert_drafts on public.editorial_drafts for insert to nightly_agent
  with check (approved_by is null and approved_at is null and author <> 'human');
create policy agent_insert_tasks on public.operator_tasks for insert to nightly_agent
  with check (resolved = false and resolved_by is null and resolved_at is null and resolution is null);
create policy agent_insert_proposals on public.crosswalk_proposals for insert to nightly_agent
  with check (status = 'proposed' and resolved_by is null and resolved_at is null);

-- -- release_reader ---------------------------------------------------------
create policy reader_read_releases on public.releases for select to release_reader using (true);

-- -- operator / authenticated humans ----------------------------------------
create policy operator_read_calendar      on public.calendar            for select to operator, authenticated using (public.is_operator());
create policy operator_read_campaigns     on public.campaigns           for select to operator, authenticated using (public.is_operator());
create policy operator_read_stages        on public.stages              for select to operator, authenticated using (public.is_operator());
create policy operator_read_releases      on public.releases            for select to operator, authenticated using (public.is_operator());
create policy operator_read_runs          on public.runs                for select to operator, authenticated using (public.is_operator());
create policy operator_read_run_steps     on public.run_steps           for select to operator, authenticated using (public.is_operator());
create policy operator_read_pcs_raw       on public.pcs_raw             for select to operator, authenticated using (public.is_operator());
create policy operator_read_predictions   on public.predictions         for select to operator, authenticated using (public.is_operator());
create policy operator_read_prediction_log on public.prediction_log     for select to operator, authenticated using (public.is_operator());
create policy operator_read_day_keys      on public.day_key_decisions   for select to operator, authenticated using (public.is_operator());
create policy operator_read_drafts        on public.editorial_drafts    for select to operator, authenticated using (public.is_operator());
create policy operator_read_tasks         on public.operator_tasks      for select to operator, authenticated using (public.is_operator());
create policy operator_read_crosswalk     on public.crosswalk           for select to operator, authenticated using (public.is_operator());
create policy operator_read_proposals     on public.crosswalk_proposals for select to operator, authenticated using (public.is_operator());
create policy operator_read_approvals     on public.approvals           for select to operator, authenticated using (public.is_operator());
create policy operator_read_reconciliation on public.reconciliation     for select to operator, authenticated using (public.is_operator());

create policy operator_insert_approvals on public.approvals for insert to operator, authenticated
  with check (public.is_operator());
create policy operator_insert_day_keys on public.day_key_decisions for insert to operator, authenticated
  with check (public.is_operator() and author = 'human' and approved_by is not null);
create policy operator_insert_tasks on public.operator_tasks for insert to operator, authenticated
  with check (public.is_operator());
create policy operator_update_tasks on public.operator_tasks for update to operator, authenticated
  using (public.is_operator()) with check (public.is_operator());
create policy operator_write_crosswalk on public.crosswalk for insert to operator, authenticated
  with check (public.is_operator());
create policy operator_update_crosswalk on public.crosswalk for update to operator, authenticated
  using (public.is_operator()) with check (public.is_operator());
create policy operator_update_proposals on public.crosswalk_proposals for update to operator, authenticated
  using (public.is_operator()) with check (public.is_operator());
create policy operator_update_releases on public.releases for update to operator, authenticated
  using (public.is_operator()) with check (public.is_operator());
create policy operator_approve_day_keys on public.day_key_decisions for update to operator, authenticated
  using (public.is_operator()) with check (public.is_operator());
create policy operator_approve_drafts on public.editorial_drafts for update to operator, authenticated
  using (public.is_operator()) with check (public.is_operator());

-- No policy grants DELETE or TRUNCATE to anyone but service_role (which
-- bypasses RLS). No policy on public.operators: service_role only.

notify pgrst, 'reload schema';
notify pgrst, 'reload config';
