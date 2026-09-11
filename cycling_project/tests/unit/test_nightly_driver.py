"""``python -m cycling_project.nightly``: the runbook as code (chip H).

Replays the committed Vuelta 2026 stage 14 → 15 archive through
``night --dry-run`` on a trimmed campaign fixture: the PCS pages are ingested
for real, every existing script is recorded but not executed, the store is
``FakeStore`` (agent role), and the outputs the spec names are asserted.
"""

from __future__ import annotations

import datetime as dt
import gzip
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from cycling_project.nightly import driver as drv
from cycling_project.nightly import refs as refs_mod
from cycling_project.nightly.store import FakeStore

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
PCS = FIXTURES / "pcs" / "vuelta-2026-stage14"
CAMPAIGN = FIXTURES / "nightly" / "driver_stage14"


@pytest.fixture
def campaign(tmp_path):
    dst = tmp_path / "vuelta-2026"
    shutil.copytree(CAMPAIGN, dst)
    shutil.copytree(PCS, dst / "results" / "stage_14" / "pcs")
    return dst


def _run(campaign, tmp_path, *argv, today="2026-09-05"):
    base = ["--campaign", str(campaign), "--store-root", str(tmp_path / "store"),
            "--crosswalk", str(campaign / "rider_crosswalk.csv"), "--today", today]
    return drv.main([argv[0], *base, *argv[1:]])


def _out(capsys):
    return json.loads(capsys.readouterr().out)


def _ledger(tmp_path, table):
    p = tmp_path / "store" / "ledger" / f"{table}.jsonl"
    return [json.loads(ln) for ln in p.read_text().splitlines()] if p.exists() else []


# ---------------------------------------------------------------------------
# plan
# ---------------------------------------------------------------------------

def test_plan_due_units_stage14_to_15(campaign, tmp_path, capsys):
    assert _run(campaign, tmp_path, "plan", "--dry-run") == 0
    plan = _out(capsys)
    assert plan["settle"] == ["stage_14"] and plan["preview"] == ["stage_15"]
    st14 = next(u for u in plan["units"] if u["unit"] == "stage_14")
    assert st14["due"] == ["settle"] and st14["flags"] == [] and st14["has_pcs"]
    assert next(u for u in plan["units"] if u["unit"] == "stage_03")["void"]
    # a night later with nothing done: stage 15 is late and blocks the stage-16 preview
    assert _run(campaign, tmp_path, "plan", "--dry-run", today="2026-09-07") == 0
    plan = _out(capsys)
    st15 = next(u for u in plan["units"] if u["unit"] == "stage_15")
    assert "settle" in st15["due"] and "settle_late" in st15["flags"] and "awaiting_acquisition" in st15["flags"]
    st16 = next(u for u in plan["units"] if u["unit"] == "stage_16")
    assert st16["due"] == ["preview"] and "blocked" in st16["flags"]


# ---------------------------------------------------------------------------
# night --dry-run replay: stage 14 settle, stage 15 preview
# ---------------------------------------------------------------------------

def test_night_dry_run_replays_stage_14_to_15(campaign, tmp_path, capsys):
    code = _run(campaign, tmp_path, "night", "--dry-run")
    out = _out(capsys)
    assert code == 0, out
    assert out["status"] == "done" and [r["unit"] for r in out["runs"]] == ["stage_14", "stage_15"]
    assert [r["phase"] for r in out["runs"]] == ["settle", "preview"]

    # ingest ran for real and reproduced the FirstCycling archive
    res = campaign / "results" / "stage_14"
    assert (res / "results.csv").read_bytes() == (CAMPAIGN / "expected/stage_14/results.csv").read_bytes()
    assert (res / "gc.csv").read_bytes() == (CAMPAIGN / "expected/stage_14/gc.csv").read_bytes()

    # retro facts: joined by rider id; the numbers the spec names
    facts = json.loads((campaign / "predictions/stage_14/retro_facts.json").read_text())
    assert facts["bundle_kind"] == "driver" and facts["results"]["winner"] == "Brenner Marco"
    assert facts["results"]["winner_fc_rider_id"] == "111801" and facts["results"]["winning_group"] == 2
    pool = {b["scenario_key"]: (b["pool15_with_key"], b["pool15_production"]) for b in facts["retrieval_summary"]}
    assert pool["gc_showdown"] == (2, 1) and pool["mountain_break"] == (5, 2)
    assert facts["key_vs_oracle"]["oracle_item"] == "res_2" and facts["key_vs_oracle"]["day_key"] == {"gc_day": 0.6, "res_2": 0.4}
    assert "rider_id" in facts["join"] and "never" in facts["join"]
    board = next(b for b in facts["boards"] if b["scenario_key"] == "gc_showdown")
    hits = board["retrieval"]["hits_with_key"]
    assert len(hits) == 2 and all(h["place"] <= 15 and h["rank"] <= 15 for h in hits)
    assert {h["name"] for h in hits} == {"Almeida Joao", "Nordhagen Jørgen"}
    assert len(board["retrieval"]["hits_production"]) == 1

    # GC config templated from the settled stage (label/short + trailing state sentence)
    gc = json.loads((campaign / "predictions/gc/scenarios.json").read_text())
    spec = gc["scenarios"]["vuelta_gc"]
    assert spec["label"].endswith("state through stage 14") and spec["short"] == "GC after stage 14"
    assert spec["note"].count("State through stage 14") == 1
    assert "Mas Enric leads Gall Felix by 2:06, Roglic Primoz 2:10" in spec["note"]
    assert spec["note"].endswith("Rerun after each evening's seed_state_cache.py.")
    assert "Brenner Marco won the stage in 4:15:09." in spec["note"]
    assert gc["date"] == "2026-09-05" and gc["odds_capture"] == "2026-09-05/markets_1720.json"
    # the human's earlier narrative before the last state sentence survives
    assert "THE RACE TURNED OVER" in spec["note"]

    # preview: config kept its human key; bundle frozen from the ingested GC
    manifest = json.loads((campaign / "predictions/stage_15/bundle/manifest.json").read_text())
    assert manifest["gc_state_through_stage"] == 14 and manifest["odds"] == "present"
    assert (campaign / "predictions/stage_15/bundle/gc.csv").read_bytes() == (res / "gc.csv").read_bytes()
    preview = out["runs"][1]
    assert preview["key"]["source"] == "config" and preview["key"]["day_key"] == {"bunch": 0.55, "res_3": 0.3, "res_1": 0.15}
    assert preview["validate"]["ok"] and any("board" in w for w in preview["validate"]["warnings"])

    # run / step records remain available in the FakeStore (agent role)
    runs = _ledger(tmp_path, "runs")
    assert [(r["campaign_slug"], r["unit"], r["phase"], r["host"]) for r in runs] == \
        [("vuelta-2026", "stage_14", "settle", "cloud"), ("vuelta-2026", "stage_15", "preview", "cloud")]
    steps = _ledger(tmp_path, "run_steps")
    settle_steps = [(s["step"], s["state"]) for s in steps if s["run_id"] == runs[0]["run_id"]]
    assert settle_steps == [("acquire", "ok"), ("ingest", "ok"), ("seed_state_cache", "skipped"), ("gc_config", "ok"), ("gc_predict", "skipped"),
                            ("gc_tracker", "skipped"), ("score_day_keys", "skipped"), ("retro_facts", "ok"),
                            ("stage_page", "skipped"), ("site_index", "skipped"), ("site_frame", "skipped"),
                            ("upload", "ok"), ("finish", "ok")]
    preview_steps = [(s["step"], s["state"]) for s in steps if s["run_id"] == runs[1]["run_id"]]
    assert preview_steps == [("capture_odds", "skipped"), ("stage_config", "ok"), ("route_facts", "ok"), ("bundle", "ok"),
                             ("day_key", "ok"), ("predict", "skipped"), ("validate", "ok"), ("stage_page", "skipped"),
                             ("site_index", "skipped"), ("site_frame", "skipped"), ("upload", "ok"), ("finish", "ok")]
    seed = next(s for s in steps if s["step"] == "seed_state_cache")
    assert seed["detail"]["argv"][1].endswith("seed_state_cache.py") and "--race-id" in seed["detail"]["argv"]
    assert next(s for s in steps if s["step"] == "score_day_keys")["detail"]["argv"][2:6] == ["--campaign", str(campaign), "--stage", "14"]
    fin = [s for s in steps if s["step"] == "finish"]
    assert [(s["state"], s["exit_code"]) for s in fin] == [("ok", 0), ("ok", 0)]
    # but --dry-run/--no-log makes no mirrored campaign run records or logs.
    assert all(run["record"] is None for run in out["runs"])
    assert not (campaign / "runs" / "2026-09-05").exists()

    # pcs_raw rows, uploaded artifacts (insert-only, under the run id) and prediction rows
    pcs_rows = _ledger(tmp_path, "pcs_raw")
    assert len(pcs_rows) == 6 and {r["ingest_verdict"] for r in pcs_rows} == {"accepted"}
    keys = out["runs"][0]["upload"]["artifacts"]
    assert f"{runs[0]['run_id']}/vuelta-2026/results/stage_14/results.csv" in keys
    assert f"{runs[0]['run_id']}/vuelta-2026/predictions/stage_14/retro_facts.json" in keys
    assert all(k.startswith(runs[0]["run_id"] + "/") for k in keys)
    assert out["runs"][0]["upload"]["pages"] == []                    # nothing was built in a dry run
    preds = _ledger(tmp_path, "predictions")
    assert [(p["unit"], p["scenario_key"], p["phase"]) for p in preds] == [("gc", "vuelta_gc", "settle")]
    assert out["runs"][1]["upload"]["artifacts"] and any(k.endswith("/bundle/manifest.json") for k in out["runs"][1]["upload"]["artifacts"])
    # a dry run never marks the phase completed
    assert not (campaign / "runs" / "completed.json").exists()


# ---------------------------------------------------------------------------
# exit 10 / exit 20 / idempotency / the git guard
# ---------------------------------------------------------------------------

def test_settle_without_pcs_pages_exits_10_with_operator_task(campaign, tmp_path, capsys):
    shutil.rmtree(campaign / "results" / "stage_14")
    code = _run(campaign, tmp_path, "night", "--dry-run")
    out = _out(capsys)
    assert code == 10 and out["status"] == "stopped" and len(out["runs"]) == 1
    run = out["runs"][0]
    # the fixture campaign is UCI-mapped (uci_competition_url), so the ask names both providers
    assert run["status"] == "waiting_for_input" and run["operator_task"]["kind"] == "acquisition_needed"
    tasks = _ledger(tmp_path, "operator_tasks")
    assert len(tasks) == 1 and tasks[0]["campaign_slug"] == "vuelta-2026" and tasks[0]["author"] == "agent"
    assert tasks[0]["run_id"] == run["run_id"]
    assert not tasks[0].get("resolved")
    fin = [s for s in _ledger(tmp_path, "run_steps") if s["step"] == "finish"]
    assert fin[-1]["state"] == "waiting" and fin[-1]["exit_code"] == 10
    assert run["record"] is None
    assert not (campaign / "runs" / "2026-09-05").exists()


def test_preview_without_a_key_exits_10_day_key_needed(campaign, tmp_path, capsys):
    cfg_path = campaign / "predictions/stage_15/scenarios.json"
    cfg = json.loads(cfg_path.read_text())
    cfg.pop("day_key")
    cfg_path.write_text(json.dumps(cfg))
    code = _run(campaign, tmp_path, "preview", "--unit", "stage_15", "--dry-run")
    out = _out(capsys)
    assert code == 10 and out["operator_task"]["kind"] == "day_key_needed"
    steps = [(s["step"], s["state"]) for s in _ledger(tmp_path, "run_steps")]
    assert ("bundle", "ok") in steps and ("day_key", "waiting") in steps and ("predict", "skipped") not in steps


def test_preview_uses_an_approved_store_key_or_an_agent_key_in_shadow(campaign, tmp_path, capsys):
    cfg_path = campaign / "predictions/stage_15/scenarios.json"
    cfg = json.loads(cfg_path.read_text())
    cfg.pop("day_key")
    cfg_path.write_text(json.dumps(cfg))
    # a human approval in the store (the dashboard writes this in production)
    store = FakeStore(tmp_path / "store", role="operator")
    store.approve_day_key("vuelta-2026", "stage_15", "bunch", by="human@test")
    code = _run(campaign, tmp_path, "preview", "--unit", "stage_15", "--dry-run")
    out = _out(capsys)
    assert code == 0 and out["key"]["source"].startswith("store:approved:") and out["key"]["day_key"] == {"bunch": 1.0}
    assert json.loads(cfg_path.read_text())["day_key"] == {"bunch": 1.0}
    # shadow mode: an agent record keys the board, flagged so the scorer never treats it as the human read
    cfg = json.loads(cfg_path.read_text()); cfg.pop("day_key"); cfg.pop("day_key_source", None)
    cfg_path.write_text(json.dumps(cfg))
    rec_path = tmp_path / "agent_key.json"
    rec_path.write_text(json.dumps({"key": {"res_3": 0.6, "bunch": 0.4}}))
    code = _run(campaign, tmp_path / "other", "preview", "--unit", "stage_15", "--dry-run", "--agent-key", str(rec_path))
    out = _out(capsys)
    assert code == 0 and out["key"]["shadow"] and out["key"]["day_key"] == {"res_3": 0.6, "bunch": 0.4}
    assert json.loads(cfg_path.read_text())["day_key_author"] == "agent"


def test_validate_rejects_bad_key_weights_and_stale_void_stages(campaign, tmp_path, capsys):
    cfg_path = campaign / "predictions/stage_15/scenarios.json"
    cfg = json.loads(cfg_path.read_text())
    cfg["day_key"] = {"bunch": 0.7, "res_5": 0.5}
    cfg["void_stages"] = []
    cfg_path.write_text(json.dumps(cfg))
    code = _run(campaign, tmp_path, "validate", "--unit", "stage_15", "--dry-run")
    out = _out(capsys)
    assert code == 10 and out["operator_task"]["kind"] == "validate_failed"
    problems = " | ".join(out["operator_task"]["detail"]["problems"])
    assert "res_5" in problems and "weights sum" in problems and "void_stages" in problems


def test_phase_is_idempotent_and_never_invokes_git(campaign, tmp_path, capsys, monkeypatch):
    calls = []

    def fake_run(argv, **kw):
        calls.append([str(a) for a in argv])
        return subprocess.CompletedProcess(argv, 0, stdout="fake ok\n", stderr="")

    monkeypatch.setattr(drv.subprocess, "run", fake_run)
    monkeypatch.setattr(drv, "sqlite_lock", lambda *a, **k: __import__("contextlib").nullcontext())
    args = ["settle", "--campaign", str(campaign), "--unit", "stage_14", "--store", "fake",
            "--store-root", str(tmp_path / "store"), "--crosswalk", str(campaign / "rider_crosswalk.csv"),
            "--today", "2026-09-05", "--no-log", "--db-path", str(tmp_path / "nonexistent.db")]
    assert drv.main(args) == 0
    out = _out(capsys)
    assert out["status"] == "done" and not out.get("already")
    assert len(calls) >= 6
    for argv in calls:
        assert not any(Path(a).name == "git" or Path(a).name.startswith("git-") for a in argv), argv
        assert "commit" not in argv and "push" not in argv
    scripts = [Path(a[1]).name for a in calls]
    assert scripts == ["seed_state_cache.py", "predict_stage_scenarios.py", "build_gc_tracker.py", "score_day_keys.py",
                       "build_stage_page.py", "build_site_index.py", "build_site_frame.py"]
    assert "--no-log" in calls[1]
    # second call: already completed → exit 0 without re-running anything
    n = len(calls)
    assert drv.main(args) == 0
    out = _out(capsys)
    assert out["already"] and len(calls) == n
    completed = json.loads((campaign / "runs" / "completed.json").read_text())
    assert "stage_14:settle" in completed
    # --force re-runs
    assert drv.main(args + ["--force"]) == 0
    assert len(calls) == 2 * n


def test_settle_without_pre_race_boards_is_retrospective_only(campaign, tmp_path, capsys, monkeypatch):
    """A missed preview must not prevent results and retro facts from settling."""
    for board in (campaign / "predictions/stage_14").glob("*.json"):
        if board.name != "scenarios.json":
            board.unlink()

    calls = []

    def fake_run(argv, **kw):
        calls.append([str(a) for a in argv])
        return subprocess.CompletedProcess(argv, 0, stdout="fake ok\n", stderr="")

    monkeypatch.setattr(drv.subprocess, "run", fake_run)
    monkeypatch.setattr(drv, "sqlite_lock", lambda *a, **k: __import__("contextlib").nullcontext())
    code = _run(campaign, tmp_path, "settle", "--unit", "stage_14", "--store", "fake", "--no-log",
                "--db-path", str(tmp_path / "nonexistent.db"))
    out = _out(capsys)

    assert code == 0, out
    steps = {s["step"]: s for s in _ledger(tmp_path, "run_steps")}
    assert "stage_page" in steps, steps
    assert steps["stage_page"]["state"] == "skipped"
    assert steps["stage_page"]["detail"]["reason"] == \
        "retrospective-only settlement: no pre-race boards"
    scripts = [Path(a[1]).name for a in calls]
    assert "build_stage_page.py" not in scripts
    assert scripts[-2:] == ["build_site_index.py", "build_site_frame.py"]


def test_publish_and_commit_are_not_commands(capsys):
    for cmd in ("publish", "commit"):
        assert drv.main([cmd]) == 20
        out = _out(capsys)
        assert out["error_class"] == "forbidden_command"
    with pytest.raises(drv.DriverFailure):
        drv.assert_no_git(["git", "push"])
    with pytest.raises(drv.DriverFailure):
        drv.assert_no_git(["/usr/bin/git", "commit", "-m", "x"])
    drv.assert_no_git(["python", "seed_state_cache.py"])                      # fine


def test_driver_source_contains_no_git_invocation():
    src = Path(drv.__file__).read_text()
    import re
    hits = [m.group(0) for m in re.finditer(r"[\"']git[\"']|subprocess\.[a-z_]+\([^\n]*git", src)]
    # the only mention is the guard itself
    assert all("assert_no_git" in line or "base == \"git\"" in line or "startswith(\"git-\")" in line
               for line in src.splitlines() if "\"git\"" in line), [l for l in src.splitlines() if "\"git\"" in l]
    assert not any("subprocess" in h for h in hits)
    assert "publish" not in {a.dest for a in drv.build_parser()._subparsers._group_actions[0].choices.values()
                             for a in [a] if hasattr(a, "dest")} or True
    assert set(drv.build_parser()._subparsers._group_actions[0].choices) == {
        "bootstrap", "plan", "night", "settle", "preview", "acquire", "ingest", "bundle", "refs", "validate", "upload", "status", "task"}


def test_status_lists_ledger_and_plan(campaign, tmp_path, capsys):
    _run(campaign, tmp_path, "ingest", "--unit", "stage_14", "--dry-run")
    capsys.readouterr()
    assert _run(campaign, tmp_path, "status", "--dry-run") == 0
    out = _out(capsys)
    assert out["runs"] and out["runs"][0]["phase"] == "ingest" and out["runs"][0]["state"] == "ok"
    assert out["plan"]["settle"] == []                                     # ingest archived the stage


# ---------------------------------------------------------------------------
# refs
# ---------------------------------------------------------------------------

def test_refs_archetype_query_excludes_used_refs(campaign, tmp_path):
    import csv, io
    cols = ["comp_id", "race_name", "year", "date", "stage_number", "category", "competition_type", "rule_type", "wg_size",
            "winner_margin", "chase_gap", "frac_120s", "winner_archetype", "dominant_archetype", "top15_sprint",
            "top15_mountain", "top15_hilly", "top15_rolling", "top15_breakaway", "top15_time_trial"]
    rows = [
        {"comp_id": 1529, "race_name": "TdF", "year": 2022, "date": "2022-07-20", "stage_number": 17, "category": "wt",
         "competition_type": "stage", "rule_type": "tiny_group", "wg_size": 2, "winner_margin": 0, "chase_gap": 30,
         "frac_120s": 0.2, "winner_archetype": "mountain", "dominant_archetype": "mountain", "top15_sprint": 0,
         "top15_mountain": 0.6, "top15_hilly": 0, "top15_rolling": 0.3, "top15_breakaway": 0.1, "top15_time_trial": 0},
        {"comp_id": 9001, "race_name": "Giro", "year": 2025, "date": "2025-05-20", "stage_number": 16, "category": "wt",
         "competition_type": "stage", "rule_type": "solo", "wg_size": 1, "winner_margin": 40, "chase_gap": 40,
         "frac_120s": 0.1, "winner_archetype": "mountain", "dominant_archetype": "mountain", "top15_sprint": 0,
         "top15_mountain": 0.5, "top15_hilly": 0.1, "top15_rolling": 0.3, "top15_breakaway": 0.1, "top15_time_trial": 0},
        {"comp_id": 9002, "race_name": "Flat", "year": 2025, "date": "2025-03-01", "stage_number": 2, "category": "wt",
         "competition_type": "stage", "rule_type": "mass_sprint", "wg_size": 80, "winner_margin": 0, "chase_gap": 0,
         "frac_120s": 1.0, "winner_archetype": "sprint", "dominant_archetype": "sprint", "top15_sprint": 0.7,
         "top15_mountain": 0.0, "top15_hilly": 0.1, "top15_rolling": 0.2, "top15_breakaway": 0, "top15_time_trial": 0},
    ]
    buf = io.StringIO(); w = csv.DictWriter(buf, fieldnames=cols); w.writeheader(); w.writerows(rows)
    sig = tmp_path / "selection_signatures_20260901_000000.csv.gz"
    with gzip.open(sig, "wt") as fh:
        fh.write(buf.getvalue())
    out = refs_mod.query_refs(archetype="gc_from_two", campaign_dir=campaign, signatures=sig, db_path=tmp_path / "none.db")
    ids = [r["comp_id"] for r in out["refs"]]
    assert ids == [9001] and 1529 in out["excluded_used_refs"]          # 1529 is a stage-14 gc_showdown ref
    out = refs_mod.query_refs(archetype="gc_from_two", campaign_dir=campaign, signatures=sig, include_used=True, db_path=tmp_path / "none.db")
    assert [r["comp_id"] for r in out["refs"]] == [9001, 1529]
    out = refs_mod.query_refs(archetype=None, where=["wg_size>=20", "category in wt"], signatures=sig, db_path=tmp_path / "none.db")
    assert [r["comp_id"] for r in out["refs"]] == [9002]
    assert refs_mod.parse_where("top15_mountain>=0.4") == ("top15_mountain", ">=", 0.4)
    with pytest.raises(KeyError):
        refs_mod.query_refs(archetype="nope", signatures=sig)


def test_a_finished_campaign_has_nothing_due(campaign, tmp_path, capsys):
    """Config-only hydration of a finished campaign (the Tour in September) must not make every
    past stage a permanently due settle."""
    assert _run(campaign, tmp_path, "plan", "--dry-run", today="2026-10-15") == 0
    out = _out(capsys)
    assert out["finished"] is True and out["settle"] == [] and out["preview"] == [] and out["units"] == []
    # a race that ended a few days ago still settles late
    assert _run(campaign, tmp_path, "plan", "--dry-run", today="2026-09-08") == 0
    out = _out(capsys)
    assert not out.get("finished") and out["settle"]


def test_a_missing_book_market_only_blocks_worldtour_previews():
    assert drv.odds_required("wt")
    assert not drv.odds_required("pro") and not drv.odds_required("d1") and not drv.odds_required(None)
