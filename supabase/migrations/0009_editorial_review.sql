-- 0009_editorial_review.sql — the owner's review loop for editorial drafts (chip ED, 2026-10-02).
--
-- NOT YET PUSHED. Apply with `supabase db push` from the repo root. Until it is pushed
-- nothing breaks: the driver inserts drafts without record / record_sha256 / artifact
-- (SupabaseStore drops the optional columns and retries once on PostgREST's
-- "column ... in the schema cache" error) and falls back to comparing body_md for
-- idempotency; the inbox's Editorial section says the migration is missing instead of
-- offering review buttons.
--
-- What it adds to public.editorial_drafts:
--   record         the full draft as the editorial agent returned it (sections, claims,
--                  placeholders_used, flags) — what a later page builder reads, no rework
--   record_sha256  sha256 of the record's canonical JSON; unique per (campaign, unit) so a
--                  re-run upload can never store the same draft twice
--   artifact       stage_preview | stage_retro | monthly_review (phase stays the coarse
--                  preview / retro / gc / one_day the table already had)
--   review_status  pending | approved | rejected | revise   (default pending)
--   review_notes   the owner's written notes — the input to the next SKILL.md revision
--   reviewed_by / reviewed_at
--
-- Trust boundary (matches 0002_roles.sql): the agent still only INSERTs, and only a
-- pending, unreviewed row; the operator may UPDATE the four review columns (plus the
-- approved_by / approved_at pair 0002 already granted). approved_by is kept consistent
-- with review_status by a trigger: approved <=> approved_by set. Gate E is unchanged —
-- nothing here reaches the public site; a later chip adds the page slot that reads
-- approved rows.

alter table public.editorial_drafts
  add column if not exists record        jsonb,
  add column if not exists record_sha256 text,
  add column if not exists artifact      text,
  add column if not exists review_status text not null default 'pending',
  add column if not exists review_notes  text,
  add column if not exists reviewed_by   text,
  add column if not exists reviewed_at   timestamptz;

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'editorial_drafts_review_status_check') then
    alter table public.editorial_drafts
      add constraint editorial_drafts_review_status_check
      check (review_status in ('pending', 'approved', 'rejected', 'revise'));
  end if;
end $$;

-- A draft already approved through the old approved_by column reads as approved.
update public.editorial_drafts set review_status = 'approved', reviewed_by = coalesce(reviewed_by, approved_by),
       reviewed_at = coalesce(reviewed_at, approved_at)
 where approved_by is not null and review_status = 'pending';

-- NULLs are distinct, so rows written before 0009 (no hash) never collide.
create unique index if not exists editorial_drafts_record_uniq
  on public.editorial_drafts (campaign_slug, unit, record_sha256);
create index if not exists editorial_drafts_review_idx
  on public.editorial_drafts (review_status, created_at desc);

comment on column public.editorial_drafts.record is 'The full editorial record (AGENT_DESIGN.md §5.2) as the agent returned it; a page builder reads approved rows from here.';
comment on column public.editorial_drafts.record_sha256 is 'sha256 of the canonical record JSON: the driver''s idempotency key.';
comment on column public.editorial_drafts.review_status is 'pending | approved | rejected | revise. approved <=> approved_by set (trigger editorial_drafts_a_review).';
comment on column public.editorial_drafts.review_notes is 'The owner''s notes; performance_eval/editorial/feedback_<date>.md collects them for the next SKILL.md revision.';

-- ---------------------------------------------------------------------------
-- review_status <-> approved_by, reviewed_at stamping
-- ---------------------------------------------------------------------------
-- Fires before editorial_drafts_approval (triggers run in name order; "a_" < "ap"), so the
-- 0001 stamp trigger then fills approved_at from the approved_by this one sets.
create or replace function public.tg_editorial_review()
returns trigger language plpgsql as $$
begin
  if tg_op = 'UPDATE' and new.review_status is not distinct from old.review_status
     and new.approved_by is distinct from old.approved_by then
    -- the 0002 path: someone set or cleared approved_by directly
    new.review_status := case when new.approved_by is not null then 'approved' else 'pending' end;
    new.reviewed_by := coalesce(new.approved_by, new.reviewed_by);
  end if;

  if new.review_status = 'approved' then
    new.approved_by := coalesce(new.reviewed_by, new.approved_by, 'operator');
  else
    new.approved_by := null;
    new.approved_at := null;
  end if;

  if new.review_status = 'pending' then
    new.reviewed_at := null;
  elsif tg_op = 'INSERT'
        or new.review_status is distinct from old.review_status
        or new.review_notes is distinct from old.review_notes then
    new.reviewed_at := now();
  end if;
  return new;
end $$;

drop trigger if exists editorial_drafts_a_review on public.editorial_drafts;
create trigger editorial_drafts_a_review before insert or update on public.editorial_drafts
  for each row execute function public.tg_editorial_review();

-- ---------------------------------------------------------------------------
-- grants + RLS
-- ---------------------------------------------------------------------------

grant update (review_status, review_notes, reviewed_by, reviewed_at)
  on public.editorial_drafts to operator, authenticated;

-- The agent may insert only a pending, unreviewed, unapproved draft. (BEFORE triggers run
-- first, so an agent row claiming review_status = 'approved' is refused on approved_by.)
drop policy if exists agent_insert_drafts on public.editorial_drafts;
create policy agent_insert_drafts on public.editorial_drafts for insert to nightly_agent
  with check (approved_by is null and approved_at is null and author <> 'human'
              and review_status = 'pending' and review_notes is null
              and reviewed_by is null and reviewed_at is null);

-- operator_approve_drafts (0002) already lets operators UPDATE rows they can read; the
-- column grant above is what widens it to the review columns.

notify pgrst, 'reload schema';
