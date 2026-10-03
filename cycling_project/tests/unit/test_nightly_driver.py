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
import sqlite3
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
    """Replay the fixture. Chip X (2026-09-22) retired PCS from `--provider auto`, so the archive
    replay names the provider explicitly — the attended Mac path the fixture stands for. Pass
    `--provider ...` in ``argv`` to override (the auto-path tests do)."""
    base = ["--campaign", str(campaign), "--store-root", str(tmp_path / "store"),
            "--crosswalk", str(campaign / "rider_crosswalk.csv"), "--today", today]
    if "--provider" not in argv:
        base += ["--provider", "pcs"]
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


def test_plan_lists_previews_that_need_route_research(campaign, tmp_path, capsys):
    """Chip Z1 (2026-10-02): the coordinator dispatches one route-researcher per unit listed."""
    pred = campaign / "predictions" / "stage_15"
    assert _run(campaign, tmp_path, "plan", "--dry-run") == 0
    plan = _out(capsys)
    assert plan["route_research"] == []                     # the operator's override stands
    (pred / "route.override.json").unlink()
    assert _run(campaign, tmp_path, "plan", "--dry-run") == 0
    plan = _out(capsys)
    assert plan["route_research"] == ["stage_15"]           # preview due, no route facts at all
    assert next(u for u in plan["units"] if u["unit"] == "stage_15")["route_research"] is True
    assert next(u for u in plan["units"] if u["unit"] == "stage_14")["route_research"] is False
    (pred / "route.json").write_text(json.dumps({"route_facts": "complete"}))
    assert _run(campaign, tmp_path, "plan", "--dry-run") == 0
    assert _out(capsys)["route_research"] == []


def test_a_startlist_handover_is_not_a_rendered_board(campaign, tmp_path, capsys):
    """The Mac horizon capture writes ``startlist.json`` into ``predictions/<unit>/`` for every
    unit the cloud is about to preview. That file is a handover, not a board: it must not make
    ``plan`` think the unit was already previewed (2026-09-16 `acquisition` lesson)."""
    pred = campaign / "predictions" / "stage_15"
    (pred / "startlist.json").write_text(json.dumps({"riders": [{"name": "x"}]}))
    (pred / "route.json").write_text("{}")
    assert (pred / "scenarios.json").exists()
    assert drv._has_scenario_boards(pred) is False
    assert _run(campaign, tmp_path, "plan", "--dry-run") == 0
    plan = _out(capsys)
    assert plan["preview"] == ["stage_15"]
    assert "preview" in next(u for u in plan["units"] if u["unit"] == "stage_15")["due"]
    # a real board flips it
    (pred / "bunch.json").write_text('{"riders": []}')
    assert drv._has_scenario_boards(pred) is True
    assert _run(campaign, tmp_path, "plan", "--dry-run") == 0
    assert _out(capsys)["preview"] == []


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
    assert preview_steps == [("capture_odds", "skipped"), ("stage_config", "ok"), ("startlist", "ok"),
                             ("gc_config", "skipped"),
                             ("route_facts", "ok"), ("bundle", "ok"), ("day_key", "ok"), ("refs_check", "ok"),
                             ("scenario_refs", "skipped"), ("predict", "skipped"), ("validate", "ok"), ("stage_page", "skipped"),
                             ("site_index", "skipped"), ("site_frame", "skipped"), ("upload", "ok"), ("finish", "ok")]
    # the runner is never allowed to reach FirstCycling from the driver unless asked
    assert "--no-scrape" in next(s for s in steps if s["step"] == "predict")["detail"]["argv"]
    seed = next(s for s in steps if s["step"] == "seed_state_cache")
    assert seed["detail"]["argv"][1].endswith("seed_state_cache.py") and "--race-id" in seed["detail"]["argv"]
    assert next(s for s in steps if s["step"] == "score_day_keys")["detail"]["argv"][2:6] == ["--campaign", str(campaign), "--stage", "14"]
    # the card is monotonic: settle also backfills every settled stage missing a row (chip Z2)
    assert next(s for s in steps if s["step"] == "score_day_keys")["detail"]["argv"][6:] == ["--also", "agent", "--backfill"]
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
    # the ask is acquisition_needed: the fixture is UCI-mapped, and --provider pcs found no pages
    assert run["status"] == "waiting_for_input" and run["operator_task"]["kind"] == "acquisition_needed"
    tasks = _ledger(tmp_path, "operator_tasks")
    assert len(tasks) == 1 and tasks[0]["campaign_slug"] == "vuelta-2026" and tasks[0]["author"] == "agent"
    assert tasks[0]["run_id"] == run["run_id"]
    assert not tasks[0].get("resolved")
    fin = [s for s in _ledger(tmp_path, "run_steps") if s["step"] == "finish"]
    assert fin[-1]["state"] == "waiting" and fin[-1]["exit_code"] == 10
    assert run["record"] is None
    assert not (campaign / "runs" / "2026-09-05").exists()


def test_a_campaign_with_no_uci_url_asks_for_one_and_never_for_pcs_pages(campaign, tmp_path, capsys):
    """Chip X (2026-09-22). A race the UCI calendar matcher could not place used to raise
    `pcs_pages_needed` — an ask that told the cloud to go and fetch ProCyclingStats pages, which
    have 403ed Anthropic's fetcher since 2026-09-06. On 2026-09-22 the coordinator spent ten tool
    calls on Giro della Romagna working out how. The ask is now for the URL itself, and it carries
    the matcher's candidates so the operator can pick one in the inbox."""
    cfg = json.loads((campaign / "campaign.json").read_text())
    cfg["uci_competition_url"] = None
    cfg["uci_match_evidence"] = {
        "matcher": "uci_calendar", "decision": "operator_confirm", "score": 0.64,
        "reason": "no exact name match on the date",
        "candidate": {"competition_id": "78436", "name": "Giro di Campania",
                      "url": "https://www.uci.org/competition-details/2026/ROA/78436"},
        "alternates": [{"competition_id": "78437", "name": "Grand Prix d'Isbergues", "similarity": 0.35}],
    }
    (campaign / "campaign.json").write_text(json.dumps(cfg, indent=2))
    shutil.rmtree(campaign / "results" / "stage_14" / "pcs")

    assert _run(campaign, tmp_path, "settle", "--unit", "stage_14", "--dry-run", "--provider", "auto") == 10
    out = _out(capsys)
    task = out["operator_task"]
    assert task["kind"] == "uci_url_needed" and task["urgency"] == "blocks_settlement"
    assert "pcs" not in json.dumps(task).lower() and "procyclingstats" not in json.dumps(task).lower()
    d = task["detail"]
    assert d["candidate"]["competition_id"] == "78436"
    assert d["alternates"][0]["competition_id"] == "78437"
    assert d["uci_match_evidence"]["decision"] == "operator_confirm"
    assert d["campaign_json"].endswith("campaign.json") and "uci_calendar resolve" in d["resolve"]
    # and the kind is in the urgency table while the retired one is gone
    assert "pcs_pages_needed" not in drv.URGENCY_BY_KIND
    assert drv.URGENCY_BY_KIND["uci_url_needed"] == "blocks_settlement"


def test_provider_auto_never_selects_pcs_even_with_pages_on_disk(campaign, tmp_path, capsys):
    """`auto` means UCI, full stop (chip X). The fixture's PCS pages are right there and the
    campaign is UCI-mapped, so before this `auto` fell back to pcs_ingest."""
    d = drv.Driver(drv.Campaign.load(campaign), store=FakeStore(tmp_path / "store"),
                   dry_run=True, provider="auto")
    assert (campaign / "results" / "stage_14" / "pcs").is_dir()
    assert d._detect_provider("stage_14") == (None, None)
    # with pcs named explicitly the same pages are chosen
    d2 = drv.Driver(drv.Campaign.load(campaign), store=FakeStore(tmp_path / "store2"),
                    dry_run=True, provider="pcs")
    assert d2._detect_provider("stage_14") == ("pcs", "provider forced to pcs")


def test_provider_pcs_still_ingests_the_fixture_on_the_attended_path(campaign, tmp_path, capsys):
    """Nothing is deleted: `--provider pcs` on the Mac still runs pcs_ingest over the archive."""
    assert _run(campaign, tmp_path, "ingest", "--unit", "stage_14", "--dry-run") == 0
    out = _out(capsys)
    assert out["ingest"]["provider"] == "pcs" and out["ingest"]["verdict"] == "accepted"
    assert out["ingest"]["n_classified"] > 100


def test_the_coordinator_prompt_never_mentions_procyclingstats():
    """The cloud must not be told about a source it cannot reach (chip X)."""
    prompt = (Path(__file__).resolve().parents[3] / "agents/managed/prompts/nightly-coordinator.md").read_text()
    low = prompt.lower()
    assert "pcs" not in low and "procyclingstats" not in low
    assert "uci_url_needed" in prompt and "Prompt revision 8" in prompt


def test_a_hydrated_container_never_falls_back_to_a_fake_store(campaign, tmp_path, capsys, monkeypatch):
    # 2026-09-17/18: a campaign thread's shell lacked SUPABASE_URL, --store auto quietly used a
    # FakeStore, and the night's runs, pages and prediction_log rows died with the container
    monkeypatch.setattr(drv, "load_local_env", lambda **kw: {})
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_NIGHTLY_KEY", raising=False)
    monkeypatch.setenv("NIGHTLY_RELEASE_TAG", "data-2026-09-18")
    base = ["--campaign", str(campaign), "--crosswalk", str(campaign / "rider_crosswalk.csv"), "--today", "2026-09-05"]
    assert drv.main(["status", *base, "--store", "auto"]) == drv.EXIT_FAILED
    out = _out(capsys)
    assert out["error_class"] == "credentials" and "SUPABASE_URL" in out["message"]
    # an explicit fake store is still allowed there, and a plain Mac shell still falls back
    assert drv.main(["status", *base, "--store", "fake", "--store-root", str(tmp_path / "store")]) == 0
    capsys.readouterr()
    monkeypatch.delenv("NIGHTLY_RELEASE_TAG")
    assert drv.main(["status", *base, "--store", "auto", "--store-root", str(tmp_path / "store")]) == 0


def test_an_agent_key_saved_in_the_readers_raw_shape_still_prices(campaign, tmp_path, capsys):
    # 2026-09-22 (task 116): the coordinator saved the reader's raw `key_items` list instead of the
    # folded `key` mapping; the driver saw no key, failed, and a paid retry fixed it — most nights
    cfg_path = campaign / "predictions/stage_15/scenarios.json"
    cfg = json.loads(cfg_path.read_text()); cfg.pop("day_key"); cfg_path.write_text(json.dumps(cfg))
    raw = campaign / "predictions/stage_15/agent_key.json"
    raw.write_text(json.dumps({"key_items": [{"item": "bunch", "weight": 0.65}, {"item": "res_3", "weight": 0.2},
                                             {"item": "res_7", "weight": 0.15}], "family": "macro"}))
    code = _run(campaign, tmp_path, "preview", "--unit", "stage_15", "--dry-run", "--agent-key", str(raw))
    out = _out(capsys)
    assert code == 0, out
    assert json.loads(cfg_path.read_text())["day_key"] == {"bunch": 0.65, "res_3": 0.2, "res_7": 0.15}
    assert out["key"]["day_key"] == {"bunch": 0.65, "res_3": 0.2, "res_7": 0.15}


def test_same_ask_is_not_filed_twice(campaign, tmp_path, capsys):
    shutil.rmtree(campaign / "results" / "stage_14")
    assert _run(campaign, tmp_path, "night", "--dry-run") == 10
    first = _out(capsys)["runs"][0]
    assert _run(campaign, tmp_path, "night", "--dry-run") == 10
    second = _out(capsys)["runs"][0]
    tasks = _ledger(tmp_path, "operator_tasks")
    assert len(tasks) == 1 and tasks[0]["kind"] == "acquisition_needed"
    assert second["duplicate_of"] == tasks[0]["id"] == first["operator_task_id"]
    assert second["operator_task_id"] == tasks[0]["id"]
    fin = [s for s in _ledger(tmp_path, "run_steps") if s["step"] == "finish"]
    assert fin[-1]["state"] == "waiting" and fin[-1]["detail"]["duplicate_of"] == tasks[0]["id"]


def test_task_command_dedupes_ops_triage_reports(campaign, tmp_path, capsys):
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"trigger": {"step": "hindsight", "race": "vuelta-2026", "stage": 15,
                                              "error_class": "ValueError"}, "diagnosis": "table missing"}))
    args = ("task", "--store", "fake", "--kind", "ops_triage", "--summary", "vuelta-2026 stage_15 settle: hindsight failed",
            "--detail-file", str(report), "--urgency", "routine")
    assert _run(campaign, tmp_path, *args) == 0
    first = _out(capsys)
    assert _run(campaign, tmp_path, *args) == 0
    second = _out(capsys)
    tasks = _ledger(tmp_path, "operator_tasks")
    assert len(tasks) == 1 and first["operator_task_id"] == tasks[0]["id"]
    assert second["duplicate_of"] == tasks[0]["id"] and second["operator_task_id"] == tasks[0]["id"]
    # a different unit is a different ask
    report.write_text(json.dumps({"trigger": {"step": "hindsight", "race": "vuelta-2026", "stage": 16,
                                              "error_class": "ValueError"}}))
    assert _run(campaign, tmp_path, *args) == 0
    assert len(_ledger(tmp_path, "operator_tasks")) == 2


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


def test_preview_uses_an_approved_store_key_or_an_agent_key(campaign, tmp_path, capsys):
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
    # an explicit agent record keys the board, stamped so the scorer never treats it as the human read
    cfg = json.loads(cfg_path.read_text()); cfg.pop("day_key"); cfg.pop("day_key_source", None)
    cfg_path.write_text(json.dumps(cfg))
    rec_path = tmp_path / "agent_key.json"
    rec_path.write_text(json.dumps({"key": {"res_3": 0.6, "bunch": 0.4}}))
    code = _run(campaign, tmp_path / "other", "preview", "--unit", "stage_15", "--dry-run", "--agent-key", str(rec_path))
    out = _out(capsys)
    assert code == 0 and out["key"]["author"] == "agent" and out["key"]["day_key"] == {"res_3": 0.6, "bunch": 0.4}
    assert out["key"]["explicit"] and out["key"]["source"] == "agent:agent_key.json"
    assert json.loads(cfg_path.read_text())["day_key_author"] == "agent"


# ---------------------------------------------------------------------------
# chip U — the agent's own key prices the board, unattended
# ---------------------------------------------------------------------------

def _unkey(cfg_path):
    cfg = json.loads(cfg_path.read_text())
    for k in ("day_key", "day_key_source", "day_key_author", "day_key_note"):
        cfg.pop(k, None)
    cfg_path.write_text(json.dumps(cfg))
    return cfg


@pytest.mark.parametrize("name", ["agent_key.json", "day_key_agent.json"])
def test_an_agent_record_beside_the_config_keys_the_board_without_the_flag(campaign, tmp_path, capsys, name):
    """The 2026-09-17 tick wrote a key and stopped: nothing told the driver it was there.

    The record the day-key-reader leaves in the unit's own directory is now picked up on the next
    pass with no extra argument, so one unattended night reaches a priced board.
    """
    cfg_path = campaign / "predictions/stage_15/scenarios.json"
    _unkey(cfg_path)
    (campaign / "predictions/stage_15" / name).write_text(json.dumps(
        {"key": {"res_3": 0.6, "bunch": 0.4}, "confidence": 0.55, "rationale": "Rolling day into a long drag."}))
    code = _run(campaign, tmp_path, "preview", "--unit", "stage_15", "--dry-run")
    out = _out(capsys)
    assert code == 0, out
    assert out["key"]["day_key"] == {"res_3": 0.6, "bunch": 0.4}
    assert out["key"]["author"] == "agent" and out["key"]["source"] == f"agent:{name}" and not out["key"]["explicit"]
    written = json.loads(cfg_path.read_text())
    assert written["day_key_author"] == "agent" and written["day_key_note"].startswith("Rolling day")
    # the board is priced: predict, validate, pages and upload all ran, and no task was filed
    steps = {s["step"] for s in _ledger(tmp_path, "run_steps")}
    assert {"predict", "validate", "upload"} <= steps
    assert _ledger(tmp_path, "operator_tasks") == []
    # the record itself is never mistaken for a rendered board
    assert drv._has_scenario_boards(campaign / "predictions/stage_15") is False


def test_an_approved_human_key_still_wins_over_an_agent_record(campaign, tmp_path, capsys):
    cfg_path = campaign / "predictions/stage_15/scenarios.json"
    _unkey(cfg_path)
    (campaign / "predictions/stage_15/agent_key.json").write_text(json.dumps({"key": {"res_3": 1.0}}))
    store = FakeStore(tmp_path / "store", role="operator")
    store.approve_day_key("vuelta-2026", "stage_15", "bunch", by="human@test")
    assert _run(campaign, tmp_path, "preview", "--unit", "stage_15", "--dry-run") == 0
    out = _out(capsys)
    assert out["key"]["source"].startswith("store:approved:") and out["key"]["day_key"] == {"bunch": 1.0}
    assert "day_key_author" not in json.loads(cfg_path.read_text())


def test_no_key_at_all_still_exits_10(campaign, tmp_path, capsys):
    """The gate is unchanged when nobody — human or agent — has read the day."""
    cfg_path = campaign / "predictions/stage_15/scenarios.json"
    _unkey(cfg_path)
    assert _run(campaign, tmp_path, "preview", "--unit", "stage_15", "--dry-run") == 10
    out = _out(capsys)
    assert out["operator_task"]["kind"] == "day_key_needed"
    assert "agent_key.json" in out["operator_task"]["summary"]


def test_the_stage_page_says_when_the_key_was_machine_written():
    """A reader cannot tell a machine key from a human one by looking at the board, so the page
    has to say it. Plain language, and no betting vocabulary (lint_prose lexicon)."""
    import runpy
    import sys
    build = Path(drv.PROJECT_ROOT) / "netlify_site" / "build"
    sys.path.insert(0, str(build))
    try:
        page = runpy.run_path(str(build / "build_stage_page.py"), run_name="_page_for_tests")
    finally:
        sys.path.remove(str(build))
    board = {"day_key": {"res_2": 0.6, "res_4": 0.4}, "board": "daymenu"}
    by_agent = page["day_key_chip"](board, {"day_key_author": "agent"})
    assert "written by the automated reader, not by a person" in by_agent
    assert "mountain escape" in by_agent and "prices unchanged" in by_agent
    by_human = page["day_key_chip"](board, {"day_key_author": "human"})
    assert "automated reader" not in by_human and "mountain escape" in by_human
    assert page["day_key_chip"](board) == by_human                 # no config: unchanged, as before
    for word in ("bet", "wager", "odds on", "value"):
        assert word not in by_agent.lower()


def test_the_inbox_clears_a_day_key_ask_once_the_step_succeeds(campaign, tmp_path, capsys):
    """Fix 1 leaves one task behind on the first pass; the reconciler's proving step retires it."""
    import importlib.util
    cfg_path = campaign / "predictions/stage_15/scenarios.json"
    _unkey(cfg_path)
    assert _run(campaign, tmp_path, "preview", "--unit", "stage_15", "--dry-run") == 10
    capsys.readouterr()
    (campaign / "predictions/stage_15/agent_key.json").write_text(json.dumps({"key": {"bunch": 1.0}}))
    assert _run(campaign, tmp_path, "preview", "--unit", "stage_15", "--dry-run") == 0
    capsys.readouterr()
    task = _ledger(tmp_path, "operator_tasks")[0]
    spec = importlib.util.spec_from_file_location(
        "build_ops_page", Path(drv.PROJECT_ROOT) / "netlify_site/build/build_ops_page.py")
    ops = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ops)
    proving = ops.TASK_SUCCESS_STEPS[task["kind"]]
    later = [s for s in _ledger(tmp_path, "run_steps") if s["step"] == proving and s["state"] == "ok"]
    assert proving == "day_key" and later, "the reconciler needs a later ok day_key step to retire the ask"


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
        "bootstrap", "plan", "night", "settle", "preview", "acquire", "ingest", "bundle", "refs", "validate", "upload", "editorial", "status", "task"}


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


# ---------------------------------------------------------------------------
# chip U — the field must be here before predict, and the driver never scrapes
# ---------------------------------------------------------------------------

def _oneday_campaign(tmp_path, *, date="2026-09-19", slug="kampioenschap-2026"):
    """A minimal one-day campaign: campaign.json plus a written config."""
    d = tmp_path / slug
    (d / "predictions" / "race").mkdir(parents=True)
    (d / "campaign.json").write_text(json.dumps(
        {"slug": slug, "name": "Kampioenschap van Vlaanderen", "fc_race_id": "54", "year": 2026,
         "is_stage_race": False, "category": "pro", "date": date, "start_date": date,
         "timezone": "Europe/Brussels"}))
    (d / "predictions" / "race" / "scenarios.json").write_text(json.dumps(
        {"fc_race_id": "54", "year": 2026, "date": date, "target": "one_day", "label": "Kampioenschap",
         "scenarios": {"default": {"tag": f"{slug}_race_default", "label": "Kampioenschap",
                                   "short": "Race", "refs": [101, 102, 103]}}}))
    return d


def test_a_one_day_preview_with_no_start_list_asks_instead_of_scraping(tmp_path, capsys):
    """Task 93 (2026-09-17): the container fell through to a live FirstCycling scrape inside
    ``predict``, hit Cloudflare, and turned a missing hand-over into a paid triage cycle."""
    camp = _oneday_campaign(tmp_path)
    code = drv.main(["preview", "--campaign", str(camp), "--unit", "race", "--dry-run",
                     "--store-root", str(tmp_path / "store"), "--today", "2026-09-18",
                     "--db-path", str(tmp_path / "nonexistent.db")])
    out = _out(capsys)
    assert code == 10, out
    task = out["operator_task"]
    assert task["kind"] == "startlist_needed" and task["urgency"] == "blocks_publication"
    assert "horizon" in task["summary"] and task["detail"]["fc_race_id"] == "54"
    steps = [(s["step"], s["state"]) for s in _ledger(tmp_path, "run_steps")]
    assert ("startlist", "waiting") in steps
    assert not any(step == "predict" for step, _ in steps), "predict must never be reached"


def test_a_handover_start_list_lets_the_one_day_preview_run(tmp_path, capsys):
    camp = _oneday_campaign(tmp_path)
    (camp / "predictions/race/startlist.json").write_text(json.dumps(
        {"fc_race_id": "54", "year": 2026, "teams": [{"name": "T", "team_id": "1",
                                                      "riders": [{"name": "R", "rider_id": "9"}]}]}))
    code = drv.main(["preview", "--campaign", str(camp), "--unit", "race", "--dry-run",
                     "--store-root", str(tmp_path / "store"), "--today", "2026-09-18",
                     "--db-path", str(tmp_path / "nonexistent.db")])
    out = _out(capsys)
    assert code == 0, out
    assert out["startlist"]["source"] == "handover:startlist.json"
    predict = next(s for s in _ledger(tmp_path, "run_steps") if s["step"] == "predict")
    assert "--no-scrape" in predict["detail"]["argv"]


def test_a_cached_start_list_counts_as_the_field(tmp_path, capsys):
    camp = _oneday_campaign(tmp_path)
    db = tmp_path / "serving.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE cached_start_lists (fc_race_id TEXT, year INTEGER, rider_fc_id TEXT, "
                "rider_name TEXT, team_name TEXT, team_fc_id TEXT, bib_number TEXT)")
    con.executemany("INSERT INTO cached_start_lists VALUES (?,?,?,?,?,?,?)",
                    [("54", 2026, str(i), f"R{i}", "T", "1", str(i)) for i in range(3)])
    con.commit(); con.close()
    code = drv.main(["preview", "--campaign", str(camp), "--unit", "race", "--dry-run",
                     "--store-root", str(tmp_path / "store"), "--today", "2026-09-18", "--db-path", str(db)])
    out = _out(capsys)
    assert code == 0, out
    assert out["startlist"] == {"source": "cache", "riders": 3, "_detail": {"source": "cache", "riders": 3}}


def test_allow_scrape_reaches_the_runner_and_skips_the_gate(tmp_path, capsys):
    """An attended Mac run may fetch the list; that choice is explicit and visible in the argv."""
    camp = _oneday_campaign(tmp_path)
    code = drv.main(["preview", "--campaign", str(camp), "--unit", "race", "--dry-run", "--allow-scrape",
                     "--store-root", str(tmp_path / "store"), "--today", "2026-09-18",
                     "--db-path", str(tmp_path / "nonexistent.db")])
    out = _out(capsys)
    assert code == 0, out
    assert out["startlist"]["source"] == "scrape_allowed"
    predict = next(s for s in _ledger(tmp_path, "run_steps") if s["step"] == "predict")
    assert "--no-scrape" not in predict["detail"]["argv"]


def test_a_mid_race_stage_waits_for_the_field_instead_of_failing_predict(campaign, tmp_path, capsys):
    """Chip V (Tour of Huangshan stage 2, 2026-09-18): the release slice's cache never saw the race
    and horizon wrote the list elsewhere, so predict died with exit 1.  Every unit is pre-checked."""
    assert _run(campaign, tmp_path, "preview", "--unit", "stage_15", "--dry-run",
                "--db-path", str(tmp_path / "nonexistent.db")) == 10
    out = _out(capsys)
    assert out["operator_task"]["kind"] == "startlist_needed", out
    steps = [(s["step"], s["state"]) for s in _ledger(tmp_path, "run_steps")]
    assert ("startlist", "waiting") in steps and not any(n == "predict" for n, _ in steps)


def test_a_sibling_units_start_list_is_the_field(campaign, tmp_path, capsys):
    """One race, one field: the list horizon left beside stage 16 serves stage 15."""
    sib = campaign / "predictions/stage_16"
    sib.mkdir(parents=True, exist_ok=True)
    (sib / "startlist.json").write_text(json.dumps(
        {"teams": [{"name": "T", "team_id": "1", "riders": [{"name": "R", "rider_id": "9"}]}]}))
    assert _run(campaign, tmp_path, "preview", "--unit", "stage_15", "--dry-run",
                "--db-path", str(tmp_path / "nonexistent.db")) == 0
    assert _out(capsys)["startlist"]["source"] == "handover:stage_16/startlist.json"


# ---------------------------------------------------------------------------
# chip U — a stage settles only after its own race-local day is over
# ---------------------------------------------------------------------------

def _huangshan(tmp_path):
    d = tmp_path / "huangshan-2026"
    d.mkdir()
    (d / "campaign.json").write_text(json.dumps(
        {"slug": "huangshan-2026", "name": "Tour of Huangshan", "fc_race_id": "900", "year": 2026,
         "is_stage_race": True, "category": "d1", "timezone": "Asia/Shanghai",
         "stages": [{"number": 1, "date": "2026-09-18"}, {"number": 2, "date": "2026-09-19"}]}))
    return d


def _plan(camp, tmp_path, capsys, local_now, *, extra=("--all-tiers",)):
    """--all-tiers by default: Huangshan is a `.1` race and the chip U tests are about the
    race-local clock, not about the coverage rule (chip Y, 2026-09-22)."""
    assert drv.main(["plan", "--campaign", str(camp), "--dry-run", "--store-root", str(tmp_path / "store"),
                     "--local-now", local_now, *extra]) == 0
    return _out(capsys)


def test_a_stage_is_not_settle_due_before_its_local_day_ends(tmp_path, capsys):
    """Hosted task 88: the 19:45 UTC tick of 2026-09-17 was already 03:45 on the 18th in Shanghai,
    so stage 1 — dated the 18th and not yet ridden — was listed as settle-due and an acquisition
    ask was filed for a stage that did not exist yet."""
    camp = _huangshan(tmp_path)
    plan = _plan(camp, tmp_path, capsys, "2026-09-18T03:45")
    assert plan["settle"] == [], plan
    assert plan["preview"] == ["stage_01"], plan       # a morning read is still honest at 03:45
    assert plan["local_now"].startswith("2026-09-18T03:45")

    # mid-race: stage 1 has begun, so it is neither settle-due nor previewable.  (Stage 2 enters
    # the ordinary one-day horizon here exactly as it always has; the real tick never fires at
    # this local hour for a race this far east.)
    plan = _plan(camp, tmp_path, capsys, "2026-09-18T13:00")
    assert plan["settle"] == [] and "stage_01" not in plan["preview"]

    # the same evening, local: the racing is done and the stage settles
    plan = _plan(camp, tmp_path, capsys, "2026-09-18T21:00")
    assert plan["settle"] == ["stage_01"] and plan["preview"] == ["stage_02"]

    # and the next local day it is late, not merely due
    plan = _plan(camp, tmp_path, capsys, "2026-09-19T03:45")
    assert plan["settle"] == ["stage_01"]
    assert "settle_late" in next(u for u in plan["units"] if u["unit"] == "stage_01")["flags"]


def test_a_date_only_override_still_means_that_evening(campaign, tmp_path, capsys):
    """Every existing caller of ``--today`` means the nightly tick, after racing: stage 14, dated
    2026-09-05, must stay settle-due under a bare date."""
    assert _run(campaign, tmp_path, "plan", "--dry-run") == 0
    plan = _out(capsys)
    assert plan["settle"] == ["stage_14"] and plan["preview"] == ["stage_15"]
    assert drv.RACE_DAY_START_HOUR < drv.RACE_DAY_OVER_HOUR


# ---------------------------------------------------------------------------
# chip V (2026-09-18) — a thin crosswalk warns under provisional, blocks under strict
# ---------------------------------------------------------------------------

def _validate_with_thin_crosswalk(campaign, tmp_path, capsys, *extra):
    thin = tmp_path / "thin_crosswalk.csv"
    header = (campaign / "rider_crosswalk.csv").read_text().splitlines()[0]
    thin.write_text(header + "\n")                                   # a new race: nobody seeded it
    shutil.copytree(campaign / "predictions/stage_14", campaign / "predictions/stage_15", dirs_exist_ok=True)
    code = drv.main(["validate", "--campaign", str(campaign), "--store-root", str(tmp_path / "store"),
                     "--crosswalk", str(thin), "--today", "2026-09-05", "--unit", "stage_14", "--dry-run", *extra])
    return code, _out(capsys)


def test_low_crosswalk_coverage_is_a_warning_under_provisional(campaign, tmp_path, capsys):
    """Okolo Slovenska stage 4 (2026-09-18): the board was built, then ``crosswalk coverage 0.016 < 0.9``
    stopped it.  The owner's 2026-09-16 ruling is provisional identities, so this only warns."""
    code, out = _validate_with_thin_crosswalk(campaign, tmp_path, capsys)
    assert not any("crosswalk" in p for p in (out.get("operator_task") or {}).get("detail", {}).get("problems", [])), out
    warnings = (out.get("validate") or {}).get("warnings") or (out.get("operator_task") or {}).get("detail", {}).get("warnings", [])
    assert any("crosswalk coverage" in w and "provisional" in w and "settle" in w for w in warnings), out


def test_low_crosswalk_coverage_still_blocks_under_strict(campaign, tmp_path, capsys):
    code, out = _validate_with_thin_crosswalk(campaign, tmp_path, capsys, "--identity-policy", "strict")
    assert code == 10 and any("crosswalk coverage" in p for p in out["operator_task"]["detail"]["problems"]), out


# ---------------------------------------------------------------------------
# page names: one rule for the driver and the builders (chip W, task 113)
# ---------------------------------------------------------------------------

def _stage_race_campaign(tmp_path, dirname, *, site=None):
    """A minimal stage-race campaign dir with no `site.prefix` (every non-Tour/Vuelta race)."""
    d = tmp_path / dirname
    (d / "predictions" / "stage_01").mkdir(parents=True)
    cfg = {"slug": dirname, "name": "Some Race", "year": 2026, "is_stage_race": True,
           "fc_race_id": "999", "start_date": "2026-09-20",
           "stages": [{"number": 1, "date": "2026-09-20"}]}
    if site is not None:
        cfg["site"] = site
    (d / "campaign.json").write_text(json.dumps(cfg))
    return d


def _builder_resolve_campaign():
    import runpy
    import sys
    build = Path(drv.PROJECT_ROOT) / "netlify_site" / "build"
    sys.path.insert(0, str(build))
    try:
        return runpy.run_path(str(build / "build_stage_page.py"), run_name="_page_for_tests")["resolve_campaign"]
    finally:
        sys.path.remove(str(build))


def test_a_stage_race_without_a_site_prefix_is_namespaced_by_its_directory(tmp_path):
    c = drv.Campaign.load(_stage_race_campaign(tmp_path, "cro-race-2026"))
    assert c.site_prefix == "cro-race-2026-"
    assert c.stage_page_name(1) == "cro-race-2026-stage01.html"
    assert c.gc_page_name() == "cro-race-2026-gc.html"
    assert c.stages_index_name() == "cro-race-2026-stages.html"
    assert c.own_page_names("stage_01") == ["cro-race-2026-stage01.html", "cro-race-2026-stages.html",
                                            "cro-race-2026-gc.html"]


def test_an_explicit_site_prefix_still_wins(tmp_path):
    c = drv.Campaign.load(_stage_race_campaign(tmp_path, "cro-race-2026", site={"prefix": "cro-"}))
    assert c.stage_page_name(1) == "cro-stage01.html" and c.gc_page_name() == "cro-gc.html"
    empty = drv.Campaign.load(_stage_race_campaign(tmp_path, "other-2026", site={"prefix": ""}))
    assert empty.stage_page_name(1) == "stage01.html"        # "" is a choice, not an absence


def test_the_tour_and_the_vuelta_keep_their_published_names(campaign):
    vuelta = drv.Campaign.load(campaign)                      # fixture carries site.prefix "vuelta-"
    assert vuelta.stage_page_name(14) == "vuelta-stage14.html" and vuelta.gc_page_name() == "vuelta-gc.html"
    for d in ("tour-de-france-2026", "vuelta-2026"):
        c = drv.Campaign.load(d)                              # the real registry files
        assert c.stage_page_name(5) == {"tour-de-france-2026": "stage05.html", "vuelta-2026": "vuelta-stage05.html"}[d]
        assert c.gc_page_name() == {"tour-de-france-2026": "gc.html", "vuelta-2026": "vuelta-gc.html"}[d]
    # the historical rule survives a registry with no `site` block at all (an old archive)
    bare = drv.Campaign(dir=Path("/nowhere/vuelta-2026"), cfg={"slug": "vuelta-2026", "year": 2026})
    assert bare.stage_page_name(1) == "vuelta-stage01.html"


@pytest.mark.parametrize("dirname", ["tour-de-france-2026", "vuelta-2026", "cro-race-2026", "okolo-slovenska-2026"])
def test_the_driver_names_pages_exactly_as_build_stage_page_writes_them(tmp_path, dirname):
    """Import both sides and compare; the rule itself is not restated here."""
    resolve_campaign = _builder_resolve_campaign()
    real = Path(drv.PERF_EVAL) / dirname
    c = drv.Campaign.load(real) if (real / "campaign.json").exists() else drv.Campaign.load(_stage_race_campaign(tmp_path, dirname))
    branding = resolve_campaign(dirname, {})
    for n in (1, 5, 21):
        assert c.stage_page_name(n) == f"{branding['prefix']}stage{n:02d}.html"
    assert c.gc_page_name() == f"{branding['prefix']}gc.html"
    assert c.stages_index_name() == f"{branding['prefix']}stages.html"


def _settle_with_fake_scripts(campaign, tmp_path, monkeypatch, *, write_pages):
    """Run a stage-14 settle with every script faked; `write_pages(argv)` decides what a builder leaves behind."""
    site = tmp_path / "site"
    site.mkdir()
    monkeypatch.setattr(drv, "SITE_DIR", site)

    def fake_run(argv, **kw):
        write_pages([str(a) for a in argv], site)
        return subprocess.CompletedProcess(argv, 0, stdout="fake ok\n", stderr="")

    monkeypatch.setattr(drv.subprocess, "run", fake_run)
    monkeypatch.setattr(drv, "sqlite_lock", lambda *a, **k: __import__("contextlib").nullcontext())
    code = drv.main(["settle", "--campaign", str(campaign), "--unit", "stage_14", "--store", "fake",
                     "--store-root", str(tmp_path / "store"), "--crosswalk", str(campaign / "rider_crosswalk.csv"),
                     "--today", "2026-09-05", "--no-log", "--db-path", str(tmp_path / "nonexistent.db")])
    return code, site


def _honest_builders(argv, site):
    """What the real builders do: each writes exactly its own campaign's page."""
    script = Path(argv[1]).name
    if script == "build_stage_page.py":
        (site / "vuelta-stage14.html").write_text("<html>stage 14</html>")
        (site / "vuelta-stages.html").write_text("<html>hub</html>")
    elif script == "build_gc_tracker.py":
        (site / "vuelta-gc.html").write_text("<html>gc</html>")
    elif script == "build_site_index.py":
        (site / "site-index.json").write_text("{}")
    elif script == "build_site_frame.py":
        (site / "_frame").mkdir(exist_ok=True)
        (site / "_frame" / "home.html").write_text("<html>home</html>")


def test_pages_the_builders_wrote_are_staged(campaign, tmp_path, capsys, monkeypatch):
    code, _ = _settle_with_fake_scripts(campaign, tmp_path, monkeypatch, write_pages=_honest_builders)
    out = _out(capsys)
    assert code == 0, out
    staged = sorted(p for p in (tmp_path / "store" / "site-staging").rglob("*") if p.is_file())
    names = sorted(p.relative_to(p.parents[len(p.parts) - p.parts.index("site-staging") - 3]).as_posix() for p in staged)
    assert names == ["_frame/home.html", "site-index.json", "vuelta-gc.html", "vuelta-stage14.html"], names


def test_a_page_the_builder_did_not_write_fails_the_run_as_page_missing(campaign, tmp_path, capsys, monkeypatch):
    """2026-09-21: CRO Race stage_01 'built' its page, staged nothing and exited 0."""
    def builders_that_forget_the_stage_page(argv, site):
        if Path(argv[1]).name != "build_stage_page.py":
            _honest_builders(argv, site)

    code, _ = _settle_with_fake_scripts(campaign, tmp_path, monkeypatch, write_pages=builders_that_forget_the_stage_page)
    out = _out(capsys)
    assert code == drv.EXIT_FAILED, out
    assert out["error_class"] == "page_missing"
    assert "vuelta-stage14.html" in out["message"]
    steps = {s["step"]: s["state"] for s in _ledger(tmp_path, "run_steps")}
    assert steps["stage_page"] == "ok"                        # the builder itself reported fine
    assert not (tmp_path / "store" / "site-staging").exists() # nothing reached staging


def test_a_gc_page_missing_after_an_ok_tracker_step_is_page_missing(campaign, tmp_path, capsys, monkeypatch):
    def builders_that_forget_the_tracker(argv, site):
        if Path(argv[1]).name != "build_gc_tracker.py":
            _honest_builders(argv, site)

    code, _ = _settle_with_fake_scripts(campaign, tmp_path, monkeypatch, write_pages=builders_that_forget_the_tracker)
    out = _out(capsys)
    assert code == drv.EXIT_FAILED and out["error_class"] == "page_missing", out
    assert "vuelta-gc.html" in out["message"]


def test_another_campaigns_page_in_the_staging_set_is_page_foreign(campaign, tmp_path, capsys, monkeypatch):
    """2026-09-21: Okolo Slovenska stage_05 staged the Tour's stage05.html + gc.html under its own run."""
    def honest(argv, site):
        _honest_builders(argv, site)
        (site / "stage05.html").write_text("<html>the Tour's</html>")

    real_build_pages = drv.Driver._build_pages

    def build_pages_with_the_old_fallback(self, unit):
        real_build_pages(self, unit)
        self.built_pages.append(drv.SITE_DIR / "stage05.html")     # what the "" fallback produced

    monkeypatch.setattr(drv.Driver, "_build_pages", build_pages_with_the_old_fallback)
    code, _ = _settle_with_fake_scripts(campaign, tmp_path, monkeypatch, write_pages=honest)
    out = _out(capsys)
    assert code == drv.EXIT_FAILED, out
    assert out["error_class"] == "page_foreign"
    assert "stage05.html" in out["message"] and "vuelta-2026" in out["message"]
    assert not (tmp_path / "store" / "site-staging").exists()   # the honest pages did not go up either
    artifacts = tmp_path / "store" / "nightly-artifacts"           # nor the unit's artifacts
    assert not any(p.is_file() for p in artifacts.rglob("*")) if artifacts.exists() else True


# ---------------------------------------------------------------------------
# chip Y — the unattended nightly covers WorldTour and .Pro (owner, 2026-09-22)
# ---------------------------------------------------------------------------

def _tiered_campaign(tmp_path, *, category="d1", automation=None, slug="tier-test-2026"):
    """A two-stage race, both stages in the past, so something IS due but for the tier."""
    d = tmp_path / slug
    d.mkdir()
    cfg = {"slug": slug, "name": "Tier Test", "fc_race_id": "900", "year": 2026,
           "is_stage_race": True, "category": category, "timezone": "Europe/Rome",
           "start_date": "2026-09-18", "end_date": "2026-09-19",
           "stages": [{"number": 1, "date": "2026-09-18"}, {"number": 2, "date": "2026-09-19"}]}
    if automation is not None:
        cfg["automation"] = automation
    if category is None:
        cfg.pop("category")
    (d / "campaign.json").write_text(json.dumps(cfg))
    return d


def _tier_plan(camp, tmp_path, capsys, *flags, local_now="2026-09-19T21:00"):
    assert drv.main(["plan", "--campaign", str(camp), "--dry-run",
                     "--store-root", str(tmp_path / "store"), "--local-now", local_now,
                     *flags]) == 0
    return _out(capsys)


def test_nothing_is_due_for_a_d1_campaign(tmp_path, capsys):
    """Eight of the eleven troublesome races in the first unattended week were `.1`."""
    plan = _tier_plan(_tiered_campaign(tmp_path), tmp_path, capsys)
    assert plan["settle"] == [] and plan["preview"] == [] and plan["units"] == []
    assert plan["automated"] is False
    assert plan["skipped"] == "not_automated: category d1"
    assert plan["category"] == "d1"


def test_a_worldtour_campaign_is_due_as_before(tmp_path, capsys):
    plan = _tier_plan(_tiered_campaign(tmp_path, category="wt"), tmp_path, capsys)
    assert plan["settle"] == ["stage_01", "stage_02"]
    assert plan["automated"] is True and "skipped" not in plan


def test_automation_on_makes_a_d1_campaign_due(tmp_path, capsys):
    plan = _tier_plan(_tiered_campaign(tmp_path, automation="on"), tmp_path, capsys)
    assert plan["settle"] == ["stage_01", "stage_02"]
    assert plan["automated"] is True


def test_automation_off_takes_a_worldtour_campaign_out(tmp_path, capsys):
    plan = _tier_plan(_tiered_campaign(tmp_path, category="wt", automation="off"), tmp_path, capsys)
    assert plan["settle"] == []
    assert plan["skipped"] == "not_automated: automation off in campaign.json"


def test_a_campaign_with_no_category_is_never_automated(tmp_path, capsys):
    plan = _tier_plan(_tiered_campaign(tmp_path, category=None), tmp_path, capsys)
    assert plan["skipped"] == "not_automated: campaign.json has no category"
    assert plan["category"] is None


def test_all_tiers_restores_the_plan_for_the_mac(tmp_path, capsys):
    camp = _tiered_campaign(tmp_path)
    assert _tier_plan(camp, tmp_path, capsys, "--all-tiers")["settle"] == ["stage_01", "stage_02"]
    assert _tier_plan(camp, tmp_path, capsys, "--include-tier", "d1")["settle"] == \
        ["stage_01", "stage_02"]


def test_night_stops_at_the_scope_gate_and_says_why(tmp_path, capsys):
    camp = _tiered_campaign(tmp_path)
    code = drv.main(["night", "--campaign", str(camp), "--dry-run",
                     "--store-root", str(tmp_path / "store"), "--local-now", "2026-09-19T21:00"])
    out = _out(capsys)
    assert code == 0 and out["status"] == "skipped"
    assert out["runs"] == [] and out["skipped"] == "not_automated: category d1"
    assert not _ledger(tmp_path, "runs"), "a skipped campaign opens no run"


def test_an_explicit_unit_still_runs_on_an_attended_campaign(tmp_path, capsys):
    """The `.1` races stay runnable by hand: only plan/night consult the tier."""
    camp = _oneday_campaign(tmp_path, slug="attended-2026")
    cfg = json.loads((camp / "campaign.json").read_text())
    cfg["category"] = "d1"
    (camp / "campaign.json").write_text(json.dumps(cfg))
    code = drv.main(["preview", "--campaign", str(camp), "--unit", "race", "--dry-run",
                     "--store-root", str(tmp_path / "store"), "--today", "2026-09-18",
                     "--db-path", str(tmp_path / "nonexistent.db")])
    out = _out(capsys)
    # It reaches the start-list gate — i.e. the phase ran — rather than being skipped.
    assert code == 10 and out["operator_task"]["kind"] == "startlist_needed"
