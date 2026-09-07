-- 0005_run_step_states.sql — let the ledger record the two states the driver
-- actually produces for a run that needs a human.
--
-- NOT YET PUSHED (2026-09-07). Apply with `supabase db push` from the repo root.
--
-- Defect this fixes (found building the operator inbox, chip J): driver.py
-- finishes a run with state 'waiting' (exit 10, an operator_task is waiting on
-- someone) or 'failed' (exit 20), and records the same two states on the step
-- that raised — see Runner.step / Runner.finish. 0001's CHECK on run_steps
-- allowed only ('started','ok','error','skipped','timeout'), so those inserts
-- were rejected with 23514. The driver swallows ledger errors by design (the
-- local run record is the fallback), so the failure was silent and the run
-- simply had no `finish` row: public.run_status then fell back to runs.state
-- and every waiting or failed night showed as 'started' forever — exactly the
-- runs the inbox exists to surface.
--
-- 'error' stays valid: nothing that already writes it changes.

alter table public.run_steps drop constraint if exists run_steps_state_check;
alter table public.run_steps add constraint run_steps_state_check
  check (state in ('started', 'ok', 'error', 'skipped', 'timeout', 'waiting', 'failed'));

comment on column public.run_steps.state is
  'started | ok | error | skipped | timeout | waiting (exit 10, an operator_task is open) | failed (exit 20). The `finish` step carries the run''s final state; run_status projects it.';

notify pgrst, 'reload schema';
