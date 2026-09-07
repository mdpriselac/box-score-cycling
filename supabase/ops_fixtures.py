#!/usr/bin/env python3
"""Seed the LOCAL `supabase start` stack with rows that exercise every section
of the operator inbox (`netlify_site/_frame/ops.html`).

    supabase start                                   # in the repo root
    uv run python supabase/ops_fixtures.py           # seed
    uv run python supabase/ops_fixtures.py --clear   # remove what it seeded

This is a preview and test aid, never a production tool: it refuses to run
against anything but a loopback Supabase URL, so it cannot touch the hosted
control plane (whose ledger is append-only and, for the agent role, not
removable at all). Rows are shaped like the real ones — an agent day-key
proposal carries `evidence.record` the way `run_day_key.store_row` writes it,
tasks carry a `crosswalk.build_operator_task` detail dict.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cycling_project.nightly import keys  # noqa: E402

CAMPAIGN = "vuelta-2026"
RELEASE = "data-2026-09-07"
MARK = "ops_fixtures"          # every seeded row is tagged so --clear is exact


def _now(minus_days: float = 0.0) -> str:
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=minus_days)).isoformat(timespec="seconds")


class Local:
    """Tiny PostgREST client for the local stack, service_role."""

    def __init__(self, url: str, key: str):
        if not any(h in url for h in ("127.0.0.1", "localhost", "[::1]")):
            raise SystemExit(f"refusing to seed a non-local Supabase: {url}")
        self.url, self.key = url.rstrip("/"), key

    def _call(self, method: str, path: str, body=None, prefer="return=representation"):
        req = urllib.request.Request(
            f"{self.url}/rest/v1/{path}", method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"apikey": self.key, "Authorization": f"Bearer {self.key}",
                     "Content-Type": "application/json", "Prefer": prefer})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
                return json.loads(raw) if raw else []
        except urllib.error.HTTPError as exc:
            raise SystemExit(f"{method} {path}: HTTP {exc.code} {exc.read().decode()[:400]}") from exc

    def insert(self, table, rows):
        return self._call("POST", table, rows if isinstance(rows, list) else [rows])

    def delete(self, table, query):
        return self._call("DELETE", f"{table}?{query}", prefer="return=minimal")


def seed(db: Local) -> None:
    clear(db)                      # idempotent: reseeding is the normal case
    db.insert("campaigns", {
        "campaign_slug": CAMPAIGN, "fc_race_id": "23", "year": 2026, "name": "Vuelta a España",
        "category": "wt", "is_stage_race": True, "start_date": "2026-08-22",
        "end_date": "2026-09-13", "timezone": "Europe/Madrid",
        "config": {"void_stages": [3], "seeded_by": MARK}})
    db.insert("releases", {
        "tag": RELEASE, "git_sha": "577244a", "db_snapshot_date": "2026-08-16",
        "horizon_end": "2026-09-20", "total_bytes": 566000000,
        "manifest": {"files": {}, "seeded_by": MARK}, "approved": True,
        "approved_by": "matt@example.test"})

    runs, steps = [], []

    def run(days_ago, unit, phase, state, exit_code, session, step_specs):
        rid = str(uuid.uuid4())
        runs.append({"run_id": rid, "campaign_slug": CAMPAIGN, "unit": unit, "phase": phase,
                     "release_tag": RELEASE, "session_id": session, "deployment": "nightly",
                     "host": "cloud", "started_at": _now(days_ago),
                     "meta": {"seeded_by": MARK}})
        # PostgREST bulk inserts need identical key sets on every row.
        def step(name, st, ms=None, log=None, code=None):
            return {"run_id": rid, "step": name, "state": st, "duration_ms": ms,
                    "exit_code": code, "started_at": _now(days_ago),
                    "finished_at": _now(days_ago), "log_key": log,
                    "detail": {"seeded_by": MARK}}

        steps.extend(step(*spec) for spec in step_specs)
        steps.append(step("finish", state, code=exit_code))
        return rid

    ok_steps = [("bootstrap", "ok", 41000, None), ("acquire", "ok", 68000, None),
                ("ingest", "ok", 9000, None), ("predict", "ok", 214000, None),
                ("render", "ok", 6000, None), ("upload", "ok", 12000, None)]
    settled = run(1.2, "stage_15", "settle", "ok", 0, "sesn_01EXAMPLE14E2A253E7954F1", ok_steps)
    run(2.2, "stage_14", "settle", "ok", 0, "sesn_01EXAMPLE0AA1A67C48D02D1", ok_steps)
    waiting = run(0.4, "stage_16", "preview", "waiting", 10, "sesn_01EXAMPLE6D3C96167533FE1",
                  [("bootstrap", "ok", 39000, None), ("odds", "ok", 5000, None),
                   ("bundle", "ok", 22000, None),
                   ("day_key", "error", 1200, f"{MARK}/day_key.log")])
    run(3.2, "stage_13", "settle", "error", 20, "sesn_01EXAMPLE5E2B1D4375C4989",
        [("bootstrap", "ok", 40000, None),
         ("acquire", "timeout", 610000, f"{MARK}/acquire.log")])
    db.insert("runs", runs)
    db.insert("run_steps", steps)

    db.insert("approvals", {
        "run_id": settled, "campaign_slug": CAMPAIGN, "unit": "stage_14", "kind": "publish",
        "decision": "approve", "approved_by": "matt@example.test",
        "note": f"seeded_by {MARK}"})

    db.insert("operator_tasks", [
        {"run_id": waiting, "campaign_slug": CAMPAIGN, "kind": "crosswalk_proposals",
         "summary": "3 riders need a human crosswalk decision",
         "urgency": "blocks_settlement", "author": "agent",
         "detail": {"seeded_by": MARK, "proposals": [
             {"pcs_slug": "ivan-sosa", "pcs_name": "Iván Sosa", "fc_rider_id": "18734",
              "fc_name": "Sosa Iván Ramiro", "confidence": 0.94,
              "evidence": "surname match, team match, dob within a year"}],
             "how_to_confirm": "uv run python -m cycling_project.nightly.crosswalk confirm "
                               "--pcs-slug <slug> --fc-rider-id <id> --by <name>"}},
        {"run_id": waiting, "campaign_slug": CAMPAIGN, "kind": "day_key_needed",
         "summary": "vuelta-2026 stage_16: day key needed (no config key, no approved row)",
         "urgency": "blocks_publication", "author": "agent",
         "detail": {"seeded_by": MARK,
                    "path": "performance_eval/vuelta-2026/predictions/stage_16/scenarios.json",
                    "bundle": "performance_eval/vuelta-2026/predictions/stage_16/bundle"}},
    ])

    db.insert("day_key_decisions", {
        "run_id": waiting, "campaign_slug": CAMPAIGN, "unit": "stage_16", "author": "agent",
        "day_key": "res_2", "family": "escape", "confidence": 0.62,
        "rationale": "Long transitional day after the rest day with no sprinter team "
                     "willing to chase; the break goes clear inside the first hour.",
        "evidence": {"seeded_by": MARK, "record": {
            "race": "Vuelta a España", "stage": 16,
            "key": {"res_2": 0.6, "res_6": 0.4},
            "family": "escape",
            "primary_mechanism": "nobody pays for the chase on a lumpy transitional stage",
            "confidence": 0.62, "human_review_required": True,
            "review_reason": "route facts missing",
            "chase_incentive": {"verdict": "nobody_pays"},
            "evidence": [{"claim": "no pure sprinter inside the top 10 on points",
                          "ref": "bundle/startlist.json"}]}}})

    db.insert("crosswalk_proposals", [
        {"run_id": waiting, "campaign_slug": CAMPAIGN, "pcs_slug": "ivan-sosa",
         "pcs_name": "Iván Sosa", "pcs_team": "Movistar Team", "pcs_bib": "154",
         "fc_rider_id": "18734", "fc_name": "Sosa Iván Ramiro", "internal_rider_id": 4471,
         "confidence": 0.94, "status": "proposed", "author": "agent",
         "evidence": f"surname + team match, dob within a year (seeded_by {MARK})",
         "alternates": [{"fc_rider_id": "23901", "fc_name": "Sosa Juan", "confidence": 0.41}]},
        {"run_id": waiting, "campaign_slug": CAMPAIGN, "pcs_slug": "marc-brustenga",
         "pcs_name": "Marc Brustenga", "pcs_team": "Equipo Kern Pharma", "pcs_bib": "187",
         "fc_rider_id": None, "fc_name": None, "internal_rider_id": None,
         "confidence": 0.38, "status": "proposed", "author": "agent",
         "evidence": f"no candidate above 0.5 in the roster (seeded_by {MARK})",
         "alternates": []},
    ])


def clear(db: Local) -> None:
    """Empty the local ledger. Safe because Local refuses a non-loopback URL."""
    for table in ("run_steps", "approvals", "operator_tasks", "day_key_decisions",
                  "crosswalk_proposals", "predictions", "prediction_log", "pcs_raw"):
        db.delete(table, "id=gt.0")
    db.delete("runs", "host=in.(cloud,mac)")
    db.delete("releases", f"tag=eq.{RELEASE}")
    db.delete("campaigns", f"campaign_slug=eq.{CAMPAIGN}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--clear", action="store_true", help="delete the seeded rows instead")
    args = ap.parse_args(argv)

    env = keys.local_stack_env(ROOT)
    if not env:
        print("no local stack — run `supabase start` in the repo root", file=sys.stderr)
        return 2
    db = Local(env["API_URL"], env.get("SECRET_KEY") or env["SERVICE_ROLE_KEY"])
    if args.clear:
        clear(db)
        print("cleared the local fixture rows")
    else:
        seed(db)
        print(f"seeded {env['API_URL']}: 1 campaign, 1 release, 4 runs, 2 tasks, "
              "1 agent day key, 2 crosswalk proposals, 1 approval")
    return 0


if __name__ == "__main__":
    sys.exit(main())
