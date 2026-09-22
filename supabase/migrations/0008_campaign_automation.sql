-- 0008_campaign_automation.sql — which campaigns the unattended nightly covers.
--
-- NOT YET PUSHED (2026-09-22, chip Y). Apply with `supabase db push` from the repo root.
-- Until it is pushed nothing breaks: `registry sync` writes the flag, and
-- store.sync_campaign drops the column and retries once when PostgREST says it does not
-- exist (SupabaseStore.OPTIONAL_COLUMNS). The rule itself lives in
-- cycling_project/nightly/tiers.py and is enforced from campaign.json, not from this row;
-- the column exists so the hosted views and the operator inbox can say, without reading
-- a config file, why a `.1` race files tasks nobody needs to treat as an automation failure.
--
-- Owner decision, 2026-09-22: the automation covers WorldTour and .Pro. `.1` races stay
-- registerable and runnable by hand on the Mac; they are due only when campaign.json
-- carries "automation": "on".

alter table public.campaigns
  add column if not exists automated boolean not null default true;

comment on column public.campaigns.automated is
  'Effective automation flag from campaign.json (category in (wt, pro), or an explicit "automation": "on"|"off"). False = registered and runnable by hand, never due for the unattended tick.';

-- Backfill from the mirrored config: category is already a column, and the per-campaign
-- override lives in config->>'automation'.
update public.campaigns
   set automated = case
         when lower(coalesce(config->>'automation', '')) in ('on', 'yes', 'true', '1', 'always') then true
         when lower(coalesce(config->>'automation', '')) in ('off', 'no', 'false', '0', 'never') then false
         else coalesce(category, '') in ('wt', 'pro')
       end;

create index if not exists campaigns_automated_idx on public.campaigns (automated)
  where automated;
