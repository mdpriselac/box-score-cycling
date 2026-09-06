-- 0001_control_plane.sql — tables of the nightly control plane.
--
-- Spec: NIGHTLY_AGENT_WORKFLOW.md §1a (trust boundary) and §2.12 (table list).
-- Every table carries created_at. Ledger tables (runs, run_steps, pcs_raw,
-- predictions, prediction_log, day_key_decisions, editorial_drafts,
-- operator_tasks, crosswalk_proposals) are append-only for the agent: the
-- grants and row-level security that enforce that live in 0002_roles.sql.
-- Registry tables (calendar, campaigns, stages, releases, crosswalk,
-- reconciliation) are written weekly from the Mac with the secret key.
--
-- Naming: campaign_slug = performance_eval/<slug> (e.g. 'vuelta-2026');
-- unit = 'stage_04' | 'gc' | 'one_day'; phase = 'plan' | 'preview' | 'settle'
-- | 'retro' | 'ops'; run_id = uuid minted by the database.

-- ---------------------------------------------------------------------------
-- helpers
-- ---------------------------------------------------------------------------

create or replace function public.tg_set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at := now();
  return new;
end $$;

-- approved_at follows approved_by (humans edit approved_by in the dashboard;
-- the timestamp is stamped for them). Clearing approved_by clears the stamp.
create or replace function public.tg_stamp_approved_at()
returns trigger language plpgsql as $$
begin
  if new.approved_by is not null and (tg_op = 'INSERT' or old.approved_by is distinct from new.approved_by) then
    new.approved_at := coalesce(new.approved_at, now());
  elsif new.approved_by is null then
    new.approved_at := null;
  end if;
  return new;
end $$;

create or replace function public.tg_stamp_resolved_at()
returns trigger language plpgsql as $$
begin
  if new.resolved and (tg_op = 'INSERT' or not old.resolved) then
    new.resolved_at := coalesce(new.resolved_at, now());
  elsif not new.resolved then
    new.resolved_at := null;
    new.resolved_by := null;
  end if;
  return new;
end $$;

-- releases.approved is a boolean the operator flips; stamp who/when.
create or replace function public.tg_stamp_release_approval()
returns trigger language plpgsql as $$
begin
  if new.approved and (tg_op = 'INSERT' or not old.approved) then
    new.approved_at := coalesce(new.approved_at, now());
    new.approved_by := coalesce(new.approved_by, nullif(current_setting('request.jwt.claims', true)::jsonb ->> 'email', ''), current_user::text);
  elsif not new.approved then
    new.approved_at := null;
    new.approved_by := null;
  end if;
  return new;
end $$;

-- ---------------------------------------------------------------------------
-- registry (Mac, weekly)
-- ---------------------------------------------------------------------------

create table public.calendar (
  id            bigint generated always as identity primary key,
  fc_race_id    text        not null,
  year          integer     not null,
  name          text        not null,
  category      text        not null,           -- 'wt' | 'pro' | '1' (FirstCycling tier)
  is_stage_race boolean     not null default false,
  start_date    date,
  end_date      date,
  country       text,
  pcs_slug      text,
  week          text,                           -- ISO week the race list was cut for, '2026-W36'
  source        text,                           -- repo path of the committed list
  created_at    timestamptz not null default now(),
  unique (fc_race_id, year)
);
comment on table public.calendar is 'Weekly race lists (WT / .Pro / .1) with dates; inserted by nightly registry sync on the Mac.';

create table public.campaigns (
  campaign_slug text primary key,
  fc_race_id    text        not null,
  year          integer     not null,
  name          text        not null,
  category      text,
  is_stage_race boolean     not null default false,
  start_date    date,
  end_date      date,
  timezone      text,
  pcs_slug      text,
  config        jsonb       not null default '{}'::jsonb,   -- the committed campaign.json
  release_tag   text,                                       -- release the campaign dir was cut from
  active        boolean     not null default true,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  unique (fc_race_id, year)
);
comment on table public.campaigns is 'One row per performance_eval/<slug> campaign in the 14-day horizon (campaign.json mirrored in config).';
create trigger campaigns_updated_at before update on public.campaigns
  for each row execute function public.tg_set_updated_at();

create table public.stages (
  id            bigint generated always as identity primary key,
  campaign_slug text        not null references public.campaigns(campaign_slug) on delete cascade,
  unit          text        not null,           -- 'stage_04' | 'gc' | 'one_day'
  kind          text        not null check (kind in ('stage', 'itt', 'ttt', 'gc', 'one_day')),
  stage_number  integer,
  date          date,
  void          boolean     not null default false,   -- cancelled (campaign.json void_stages)
  settle_late   boolean     not null default false,   -- North-American finish: settles a night later
  route         jsonb,                                -- route.json facts at registry time
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  unique (campaign_slug, unit)
);
comment on column public.stages.void is 'Cancelled stage: no preview, no settlement; state_through_stage counts completed stages, not stage numbers.';
create trigger stages_updated_at before update on public.stages
  for each row execute function public.tg_set_updated_at();

create table public.releases (
  tag              text primary key,
  git_sha          text        not null,
  model_release_id text,
  db_snapshot_date date,
  horizon_end      date,
  total_bytes      bigint,
  manifest         jsonb       not null,
  approved         boolean     not null default false,
  approved_by      text,
  approved_at      timestamptz,
  created_at       timestamptz not null default now()
);
comment on table public.releases is 'Weekly release bundles in Storage releases/<tag>/ (weekly_release.py). bootstrap uses the newest approved row.';
create trigger releases_approval before insert or update on public.releases
  for each row execute function public.tg_stamp_release_approval();

-- ---------------------------------------------------------------------------
-- ledger (agent inserts)
-- ---------------------------------------------------------------------------

create table public.runs (
  run_id        uuid primary key default gen_random_uuid(),
  campaign_slug text,                           -- null for the plan / ops tick itself
  unit          text,
  phase         text        not null,           -- 'plan' | 'preview' | 'settle' | 'retro' | 'ops'
  state         text        not null default 'started',  -- initial state; transitions are run_steps rows
  release_tag   text        references public.releases(tag),
  session_id    text,                           -- Managed Agents session id
  deployment    text,                           -- e.g. 'nightly'
  host          text        not null default 'cloud' check (host in ('cloud', 'mac')),
  started_at    timestamptz not null default now(),
  meta          jsonb       not null default '{}'::jsonb,
  created_at    timestamptz not null default now()
);
comment on table public.runs is 'One row per (nightly tick, campaign, unit, phase). Append-only: completion is a run_steps row with step = finish.';
create index runs_campaign_unit_idx on public.runs (campaign_slug, unit, created_at desc);
create index runs_created_idx on public.runs (created_at);

create table public.run_steps (
  id          bigint generated always as identity primary key,
  run_id      uuid        not null references public.runs(run_id),
  step        text        not null,             -- 'bootstrap' | 'acquire' | 'ingest' | 'predict' | 'render' | 'finish' …
  state       text        not null check (state in ('started', 'ok', 'error', 'skipped', 'timeout')),
  started_at  timestamptz,
  finished_at timestamptz,
  duration_ms integer,
  exit_code   integer,
  log_key     text,                             -- nightly-artifacts object key with the step log
  detail      jsonb       not null default '{}'::jsonb,
  created_at  timestamptz not null default now()
);
create index run_steps_run_idx on public.run_steps (run_id, id);

-- Latest state per run, derived from the ledger (no UPDATE anywhere).
create view public.run_status as
  select r.run_id, r.campaign_slug, r.unit, r.phase, r.release_tag, r.session_id, r.host, r.started_at,
         coalesce(f.state, r.state) as state,
         f.exit_code,
         f.finished_at,
         (select count(*) from public.run_steps s where s.run_id = r.run_id) as steps
  from public.runs r
  left join lateral (
    select s.state, s.exit_code, s.finished_at
    from public.run_steps s
    where s.run_id = r.run_id and s.step = 'finish'
    order by s.id desc limit 1
  ) f on true;

create table public.pcs_raw (
  id             bigint generated always as identity primary key,
  run_id         uuid        not null references public.runs(run_id),
  campaign_slug  text,
  unit           text,
  kind           text        not null,          -- 'results' | 'startlist' | 'stage' | 'gc' | 'route'
  source_url     text        not null,
  fetched_at     timestamptz not null default now(),
  content        text,                          -- verbatim transcription (small pages) …
  object_key     text,                          -- … or the nightly-artifacts key holding it
  content_sha256 text,
  ingest_verdict text        check (ingest_verdict in ('pending', 'ok', 'rejected', 'partial')),
  ingest_detail  jsonb       not null default '{}'::jsonb,
  created_at     timestamptz not null default now()
);
comment on table public.pcs_raw is 'Verbatim PCS transcriptions by the web_fetch-only acquirer plus the deterministic ingest verdict (§2.8).';
create index pcs_raw_campaign_unit_idx on public.pcs_raw (campaign_slug, unit, created_at desc);

create table public.predictions (
  id            bigint generated always as identity primary key,
  run_id        uuid        not null references public.runs(run_id),
  campaign_slug text        not null,
  unit          text        not null,
  phase         text        not null,           -- 'preview' | 'retro' | 'scenario'
  target        text,                           -- 'stage' | 'gc' | 'one_day'
  scenario_key  text,
  day_key       text,
  model_version text,
  config        jsonb       not null default '{}'::jsonb,   -- scenario config as run
  board_key     text,                                       -- nightly-artifacts key of the board JSON
  summary       jsonb       not null default '{}'::jsonb,
  created_at    timestamptz not null default now()
);
create index predictions_campaign_unit_idx on public.predictions (campaign_slug, unit, created_at desc);

-- Mirrors cycling_project/prediction_tools/prediction_log.py column-for-column
-- (SCHEMA_SQL + MIGRATION_COLUMNS, SQLite types mapped) so the weekly import is
-- a straight copy. run_id + created_at are provenance columns that do not exist
-- in SQLite; the importer drops them.
create table public.prediction_log (
  id                     bigint generated always as identity primary key,
  predicted_at           timestamptz      not null default now(),
  fc_race_id             text             not null,
  year                   integer          not null,
  stage_number           integer,
  competition_id         integer,
  rider_id               integer          not null,
  rider_name             text,
  reference_comp_ids     text,                       -- JSON list, as in SQLite
  model_version          text,
  multiclass_win_p       double precision,
  multiclass_podium_p    double precision,
  multiclass_top5_p      double precision,
  multiclass_top15_p     double precision,
  lambdarank_win_p       double precision,
  lambdarank_podium_p    double precision,
  lambdarank_temperature double precision,
  state_through_stage    integer,
  gc_outlook_win_p       double precision,
  gc_outlook_podium_p    double precision,
  gc_outlook_top5_p      double precision,
  gc_outlook_top15_p     double precision,
  dnf_p                  double precision,
  dnf_adj_win_p          double precision,
  dnf_adj_podium_p       double precision,
  dnf_adj_top5_p         double precision,
  dnf_adj_top15_p        double precision,
  blend_win_p            double precision,
  run_key                text,
  run_id                 uuid             references public.runs(run_id),
  created_at             timestamptz      not null default now()
);
comment on table public.prediction_log is 'Same columns as the SQLite prediction_log (prediction_log.py); imported weekly into cycling_races.db. (run_key, rider_id) is unique like the SQLite index.';
create index prediction_log_fc_race_idx      on public.prediction_log (fc_race_id, year);
create index prediction_log_competition_idx  on public.prediction_log (competition_id);
create index prediction_log_rider_idx        on public.prediction_log (rider_id);
create index prediction_log_predicted_at_idx on public.prediction_log (predicted_at);
create unique index prediction_log_run_rider_uidx on public.prediction_log (run_key, rider_id);

create table public.day_key_decisions (
  id            bigint generated always as identity primary key,
  run_id        uuid        references public.runs(run_id),
  campaign_slug text        not null,
  unit          text        not null,
  author        text        not null check (author in ('agent', 'model', 'human', 'oracle')),
  day_key       text        not null,           -- day_menu.py menu item; 'none' when no read
  family        text,
  confidence    numeric(4, 3),
  rationale     text,
  evidence      jsonb       not null default '{}'::jsonb,
  approved_by   text,                           -- set only by humans (RLS); the serving key
  approved_at   timestamptz,
  created_at    timestamptz not null default now()
);
comment on table public.day_key_decisions is 'Both day keys per stage: agent/model proposals (approved_by null) and the human key (approved_by set). score_day_keys.py scores them.';
create index day_key_decisions_lookup_idx on public.day_key_decisions (campaign_slug, unit, approved_at desc nulls last);
create trigger day_key_decisions_approval before insert or update on public.day_key_decisions
  for each row execute function public.tg_stamp_approved_at();

create table public.editorial_drafts (
  id            bigint generated always as identity primary key,
  run_id        uuid        references public.runs(run_id),
  campaign_slug text        not null,
  unit          text        not null,
  phase         text        not null check (phase in ('preview', 'retro', 'gc', 'one_day')),
  kind          text        not null default 'prose',   -- 'prose' | 'headline' | 'caption'
  author        text        not null default 'agent',
  body_md       text        not null,
  lint          jsonb       not null default '{}'::jsonb,   -- lexicon linter report
  lint_ok       boolean,
  approved_by   text,
  approved_at   timestamptz,
  created_at    timestamptz not null default now()
);
create index editorial_drafts_lookup_idx on public.editorial_drafts (campaign_slug, unit, created_at desc);
create trigger editorial_drafts_approval before insert or update on public.editorial_drafts
  for each row execute function public.tg_stamp_approved_at();

create table public.operator_tasks (
  id            bigint generated always as identity primary key,
  run_id        uuid        references public.runs(run_id),
  campaign_slug text,
  kind          text        not null,           -- 'crosswalk_proposals' | 'reconciliation_drift' | 'ingest_rejected' …
  summary       text        not null,
  detail        jsonb       not null default '{}'::jsonb,
  urgency       text        not null default 'routine'
                            check (urgency in ('routine', 'blocks_publication', 'blocks_settlement', 'urgent')),
  author        text        not null default 'agent',
  resolved      boolean     not null default false,
  resolved_by   text,
  resolved_at   timestamptz,
  resolution    text,
  created_at    timestamptz not null default now()
);
comment on table public.operator_tasks is 'The inbox. Agents insert (resolved = false); humans flip resolved in the dashboard.';
create index operator_tasks_open_idx on public.operator_tasks (resolved, urgency, created_at desc);
create trigger operator_tasks_resolution before insert or update on public.operator_tasks
  for each row execute function public.tg_stamp_resolved_at();

-- ---------------------------------------------------------------------------
-- rider identity
-- ---------------------------------------------------------------------------

-- Same columns as performance_eval/crosswalk/rider_crosswalk.csv (crosswalk.py).
create table public.crosswalk (
  pcs_slug          text primary key,
  fc_rider_id       text        not null,
  internal_rider_id integer,
  pcs_name          text,
  fc_name           text,
  birth_year        integer,
  confidence        numeric(4, 2),
  source            text,                       -- 'pcs_startlist' | 'derived' | 'human'
  confirmed_by      text,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);
create index crosswalk_fc_idx on public.crosswalk (fc_rider_id);
create trigger crosswalk_updated_at before update on public.crosswalk
  for each row execute function public.tg_set_updated_at();

create table public.crosswalk_proposals (
  id                bigint generated always as identity primary key,
  run_id            uuid        references public.runs(run_id),
  campaign_slug     text,
  pcs_slug          text        not null,
  pcs_name          text,
  pcs_team          text,
  pcs_bib           text,
  fc_rider_id       text,
  fc_name           text,
  internal_rider_id integer,
  confidence        numeric(4, 2),
  evidence          text,
  alternates        jsonb       not null default '[]'::jsonb,
  author            text        not null default 'agent',
  status            text        not null default 'proposed'
                                check (status in ('proposed', 'confirmed', 'rejected', 'superseded')),
  resolved_by       text,
  resolved_at       timestamptz,
  created_at        timestamptz not null default now()
);
create index crosswalk_proposals_open_idx on public.crosswalk_proposals (status, created_at desc);

-- ---------------------------------------------------------------------------
-- human decisions
-- ---------------------------------------------------------------------------

create table public.approvals (
  id            bigint generated always as identity primary key,
  run_id        uuid        not null references public.runs(run_id),
  campaign_slug text,
  unit          text,
  kind          text        not null default 'publish'
                            check (kind in ('publish', 'retro', 'preview', 'release', 'other')),
  decision      text        not null default 'approve' check (decision in ('approve', 'reject', 'hold')),
  approved_by   text        not null,
  note          text,                           -- visible to the agent via approvals_view
  private_note  text,                           -- operator-only, never exposed to agents
  created_at    timestamptz not null default now()
);
comment on table public.approvals is 'Publication approvals per run. Human-only writes; the agent reads approvals_view (no approver identity, no private notes).';
create index approvals_run_idx on public.approvals (run_id, created_at desc);

-- The agent-facing projection: what was approved, never by whom or the private note.
create view public.approvals_view as
  select id, run_id, campaign_slug, unit, kind, decision, note, created_at
  from public.approvals;

-- Allow-list of humans who act as operators through Supabase Auth
-- (see public.is_operator() in 0002_roles.sql). Service role only.
create table public.operators (
  email      text primary key,
  user_id    uuid,                              -- auth.users.id once known
  name       text,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- weekly reconciliation (Mac)
-- ---------------------------------------------------------------------------

-- Same fields as reconcile.UnitDiff.as_row().
create table public.reconciliation (
  id             bigint generated always as identity primary key,
  campaign_slug  text        not null,
  unit           text        not null,
  kind           text        not null,          -- 'stage' | 'gc'
  pcs_rows       integer,
  fc_rows        integer,
  comparable     boolean,
  id_diffs       integer,
  gap_diffs      integer,
  missing_places integer,
  top20_diffs    integer,
  verdict        text        check (verdict in ('ok', 'drift', 'skipped')),
  sample         jsonb       not null default '[]'::jsonb,
  note           text,
  checked_at     timestamptz,
  created_at     timestamptz not null default now()
);
create index reconciliation_lookup_idx on public.reconciliation (campaign_slug, unit, created_at desc);

-- ---------------------------------------------------------------------------
-- diagnostics
-- ---------------------------------------------------------------------------

-- Which Postgres role a request runs as (key verification: mint_keys.py --verify).
create or replace function public.whoami()
returns text language sql stable as $$ select current_user::text $$;
