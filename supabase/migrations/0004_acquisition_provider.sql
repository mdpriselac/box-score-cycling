-- 0004_acquisition_provider.sql — provider-neutral raw-acquisition provenance (UCI results bridge).
--
-- NOT YET PUSHED (2026-09-06). Until it is, the store writes UCI captures into public.pcs_raw with
-- kind = 'uci:<kind>' and ingest_detail.provider = 'uci' (store.insert_acquisition_raw), and UCI
-- identity proposals into public.crosswalk_proposals with pcs_slug = 'uci:<uci_key>' (an alias
-- key derived from the name — explicitly not a UCI id). This migration makes the provider a
-- first-class column and exposes the same rows as public.acquisition_raw; nothing is renamed, so
-- code that still says pcs_raw keeps working. Apply with `supabase db push` from the repo root.

alter table public.pcs_raw
  add column if not exists provider text not null default 'pcs'
    check (provider in ('pcs', 'uci', 'fc'));
comment on column public.pcs_raw.provider is 'Result provider that produced the capture: pcs | uci | fc (weekly reconciliation).';

-- Backfill the kind-prefixed rows written before this migration.
update public.pcs_raw
   set provider = split_part(kind, ':', 1), kind = split_part(kind, ':', 2)
 where kind like 'uci:%' or kind like 'fc:%';

create or replace view public.acquisition_raw as
  select id, run_id, campaign_slug, unit, provider, kind, source_url, fetched_at, content, object_key,
         content_sha256, ingest_verdict, ingest_detail, created_at
    from public.pcs_raw;
comment on view public.acquisition_raw is 'Provider-neutral view over pcs_raw (UCI_MANAGED_AGENT_BUILD_BRIEF.md §5).';
grant select on public.acquisition_raw to nightly_agent, operator, authenticated, service_role;

alter table public.crosswalk_proposals
  add column if not exists provider text not null default 'pcs' check (provider in ('pcs', 'uci')),
  add column if not exists external_key text;
comment on column public.crosswalk_proposals.external_key is
  'Provider-side identity: the PCS slug, or for UCI the alias key "<surname tokens>|<given tokens>" (not a UCI id).';
update public.crosswalk_proposals
   set provider = 'uci', external_key = substr(pcs_slug, 5)
 where pcs_slug like 'uci:%' and external_key is null;
