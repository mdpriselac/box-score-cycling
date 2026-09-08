-- 0006_acquisition_verdicts.sql — align raw provenance with ingest reports.
--
-- Both PCS and UCI ingest reports use `accepted` / `rejected`. 0001 predated
-- that contract and allowed `ok` as its success value instead. Keep `ok` for
-- rows and older clients already using it, while accepting the canonical
-- report vocabulary so successful captures are not dropped from the ledger.

alter table public.pcs_raw
  drop constraint if exists pcs_raw_ingest_verdict_check;

alter table public.pcs_raw
  add constraint pcs_raw_ingest_verdict_check
  check (ingest_verdict in ('pending', 'ok', 'accepted', 'rejected', 'partial'));

comment on column public.pcs_raw.ingest_verdict is
  'Deterministic ingest outcome: pending | accepted | rejected | partial; ok is retained for backward compatibility.';
