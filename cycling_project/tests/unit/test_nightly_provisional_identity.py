"""``identity_policy`` — an unresolved rider inside the top gate no longer blocks an unattended settle.

Operator ruling 2026-09-16 (supersedes the strict half of the 2026-09-08 ruling for unattended runs):
settle and publish with a provisional ``uci:`` id and a visible caveat; the weekly Mac reconcile
(``crosswalk reconcile-results``) makes the fix durable. This week Trofeo Matteotti (rank 15) and
Okolo Slovenska (ranks 11 and 14) each sat in ``waiting`` for three nights over exactly this.

Fixtures reuse the Vuelta 2026 stage 14 UCI capture (see ``test_nightly_uci.py``); renaming a rider
inside the top 15 is how a stage gets an identity the roster cannot resolve. No test touches the
network or the hosted ledger (every driver run is ``--store fake``).
"""

from __future__ import annotations

import csv
import json
import runpy
import shutil
import sys
from pathlib import Path

import pytest

from cycling_project.nightly import crosswalk as xw
from cycling_project.nightly import driver as drv
from cycling_project.nightly import hindsight
from cycling_project.nightly import uci_ingest as ui

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
UCI = FIXTURES / "uci" / "vuelta-2026-stage14"
ALIASES = FIXTURES / "uci" / "uci_aliases.csv"
CAMPAIGN = FIXTURES / "nightly" / "driver_stage14"
SITE_BUILD = Path(__file__).resolve().parents[3] / "netlify_site" / "build"


@pytest.fixture
def campaign(tmp_path):
    dst = tmp_path / "vuelta-2026"
    shutil.copytree(CAMPAIGN, dst)
    shutil.copytree(UCI, dst / "results" / "stage_14" / "uci")
    shutil.copy(ALIASES, dst / "uci_aliases.csv")
    return dst


def _edit_json(path: Path, fn) -> None:
    doc = json.loads(path.read_text(encoding="utf-8"))
    fn(doc)
    path.write_text(json.dumps(doc), encoding="utf-8")


def _rename_rider(campaign, old_last: str, new_last: str) -> None:
    for f in ("stage.json", "gc.json"):
        def fn(d):
            for r in d["results"]:
                if r["values"].get("lastname") == old_last:
                    r["values"]["lastname"] = new_last
            for p in (d.get("podium") or {}).get("podium") or []:
                if p.get("lastname") == old_last:
                    p["lastname"] = new_last
        _edit_json(campaign / "results/stage_14/uci" / f, fn)


def _ingest(campaign, **kw):
    kw.setdefault("aliases_csv", campaign / "uci_aliases.csv")
    return ui.ingest(campaign, "stage_14", crosswalk_csv=campaign / "rider_crosswalk.csv", **kw)


def _rows(campaign, name="results.csv"):
    with (campaign / "results/stage_14" / name).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# the policy switch
# ---------------------------------------------------------------------------

def test_strict_still_refuses_an_unresolved_rider_inside_the_top_gate(campaign):
    _rename_rider(campaign, "SOSA CUERVO", "SOMEONEELSE")            # stage place 4
    rep = _ingest(campaign, identity_policy="strict")
    assert not rep.ok and "crosswalk_top" in [c["name"] for c in rep.failing]
    assert rep.provisional_top == [] and rep.identity_policy == "strict"
    assert not (campaign / "results/stage_14/results.csv").exists()   # nothing partial written


def test_provisional_is_the_default_and_settles_the_stage(campaign):
    assert ui.DEFAULT_IDENTITY_POLICY == "provisional"
    _rename_rider(campaign, "SOSA CUERVO", "SOMEONEELSE")
    rep = _ingest(campaign)
    assert rep.ok, rep.failing
    assert rep.identity_policy == "provisional"
    top = next(c for c in rep.checks if c.name == "crosswalk_top")
    assert top.ok and top.detail["stage_top15_unresolved"]            # a warning, not a failure
    assert any("INSIDE the top gate carry provisional uci: ids" in w for w in rep.warnings)

    # the report names the rider, its place, its best candidate and the team/age evidence
    prov = rep.provisional_top
    assert len(prov) == 1
    assert prov[0]["uci_name"] == "SOMEONEELSE Ivan Ramiro" and prov[0]["place"] == "4"
    assert prov[0]["rider_id"].startswith("uci:") and prov[0]["team"] and prov[0]["age"]
    assert "best" in prov[0] and "confidence" in prov[0]["best"]

    # the row survives with its place and time intact, under a provisional id
    row = next(r for r in _rows(campaign) if r["place"] == "4")
    assert row["rider_id"].startswith("uci:") and row["name"] == "SOMEONEELSE Ivan Ramiro"
    assert row["gap"] not in (None, "")
    assert len(_rows(campaign)) == 155                                # nothing dropped
    # ... and in the GC archive too
    assert any(r["rider_id"].startswith("uci:") for r in _rows(campaign, "gc.csv"))

    # the archive records what the page has to caveat
    rj = json.loads((campaign / "results/stage_14/results.json").read_text())
    assert rj["identity_policy"] == "provisional"
    assert [p["name"] for p in rj["provisional_identities"]] == ["SOMEONEELSE Ivan Ramiro"]
    assert rj["provisional_identities"][0]["place"] == "4"

    # the proposal is still filed for the inbox
    assert any(p["pcs_name"] == "SOMEONEELSE Ivan Ramiro" and p["status"] == "proposed"
               for p in rep.proposals)


def test_an_unknown_policy_is_refused(campaign):
    with pytest.raises(ui.UciIngestError):
        _ingest(campaign, identity_policy="lenient")


# ---------------------------------------------------------------------------
# the driver: routine task, not a waiting state
# ---------------------------------------------------------------------------

def _run(campaign, tmp_path, *argv, today="2026-09-05"):
    base = ["--campaign", str(campaign), "--store", "fake", "--store-root", str(tmp_path / "store"),
            "--crosswalk", str(campaign / "rider_crosswalk.csv"),
            "--aliases", str(campaign / "uci_aliases.csv"), "--today", today]
    return drv.main([argv[0], *base, *argv[1:]])


def _ledger(tmp_path, table):
    p = tmp_path / "store" / "ledger" / f"{table}.jsonl"
    return [json.loads(ln) for ln in p.read_text().splitlines()] if p.exists() else []


def test_driver_settles_and_files_a_routine_task_not_a_waiting_state(campaign, tmp_path, capsys):
    _rename_rider(campaign, "SOSA CUERVO", "SOMEONEELSE")
    assert _run(campaign, tmp_path, "ingest", "--unit", "stage_14") == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "done" and out["ingest"]["identity_policy"] == "provisional"
    assert len(out["ingest"]["provisional_top"]) == 1

    tasks = _ledger(tmp_path, "operator_tasks")
    task = next(t for t in tasks if t["kind"] == "identity_provisional")
    assert task["urgency"] == "routine" and task["author"] == "agent"
    assert task["detail"]["unit"] == "stage_14"
    assert [p["uci_name"] for p in task["detail"]["provisional"]] == ["SOMEONEELSE Ivan Ramiro"]
    assert "reconcile-results" in task["detail"]["next_step"]
    assert not any(t["kind"] == "ingest_failed" for t in tasks)

    props = _ledger(tmp_path, "crosswalk_proposals")
    assert any(p["pcs_name"] == "SOMEONEELSE Ivan Ramiro" for p in props)


def test_strict_from_the_cli_still_waits_for_the_operator(campaign, tmp_path, capsys):
    _rename_rider(campaign, "SOSA CUERVO", "SOMEONEELSE")
    assert _run(campaign, tmp_path, "ingest", "--unit", "stage_14", "--identity-policy", "strict") == 10
    out = json.loads(capsys.readouterr().out)
    assert out["operator_task"]["kind"] == "ingest_failed"
    assert out["operator_task"]["urgency"] == "blocks_settlement"


# ---------------------------------------------------------------------------
# the page caveat
# ---------------------------------------------------------------------------

def _page_module():
    sys.path.insert(0, str(SITE_BUILD))
    try:
        return runpy.run_path(str(SITE_BUILD / "build_stage_page.py"), run_name="_page_for_tests")
    finally:
        sys.path.remove(str(SITE_BUILD))


def test_page_caveat_names_the_provisional_riders():
    note = _page_module()["provisional_note"]
    results = {"provisional_identities": [{"place": "4", "name": "SOMEONEELSE Ivan Ramiro"},
                                          {"place": "11", "name": "PAKOT Andras Gusztav"}],
               "results": []}
    html = note(results)
    assert "2 riders in the top 15 are shown under a provisional identity pending reconciliation" in html
    assert "SOMEONEELSE Ivan Ramiro, PAKOT Andras Gusztav" in html
    # singular reads plainly too
    one = note({"provisional_identities": [{"place": "15", "name": "LOPEZ SEVILLA Diego Pablo"}]})
    assert "1 rider in the top 15 is shown under a provisional identity" in one
    # an older archive with no recorded list still gets the note from the rows themselves
    from_rows = note({}, rows=[{"place": "3", "name": "KADLEC Milan", "rider_id": "uci:kadlec|milan"},
                               {"place": "40", "name": "Someone Else", "rider_id": "uci:x|y"},
                               {"place": "1", "name": "Real Rider", "rider_id": "12345"}])
    assert "KADLEC Milan" in from_rows and "Someone Else" not in from_rows   # outside the top 15
    assert note({"provisional_identities": [], "results": []}) == ""         # silent when clean


def test_gc_tracker_and_oneday_page_share_the_helper():
    for name in ("build_gc_tracker.py", "build_oneday_page.py"):
        src = (SITE_BUILD / name).read_text()
        assert "provisional_note" in src, name


# ---------------------------------------------------------------------------
# scoring: a provisional id is a rider who is not in the model field
# ---------------------------------------------------------------------------

def test_hindsight_profiles_drop_a_provisional_id_rather_than_querying_it(tmp_path):
    # no DB: the point is that the uci: key never reaches SQL and the caller reads "unknown"
    assert hindsight._profiles(["uci:kadlec|milan", "12345"], tmp_path / "nope.db") == {}


def test_hindsight_field_excludes_provisional_rows(tmp_path):
    out = tmp_path / "field.json"
    hindsight._write_result_field(
        {"results": [{"place": "1", "name": "Real Rider", "rider_id": "12345", "team": "T"},
                     {"place": "2", "name": "KADLEC Milan", "rider_id": "uci:kadlec|milan", "team": "T"}]},
        out, fc_race_id="23", year=2026)
    doc = json.loads(out.read_text())
    ids = [r["rider_id"] for t in doc["teams"] for r in t["riders"]]
    assert ids == ["12345"]
    assert doc["excluded_provisional_identities"] == ["KADLEC Milan"]       # recorded, not silent


def test_day_key_scorer_skips_provisional_ids():
    src = (Path(__file__).resolve().parents[3] / "performance_eval" / "vuelta-2026"
           / "score_day_keys.py").read_text()
    assert 'fc_ids = [i for i in fc_ids if not str(i).startswith("uci:")]' in src


# ---------------------------------------------------------------------------
# the durable half: the weekly reconcile rewrites the archived id
# ---------------------------------------------------------------------------

def test_reconcile_results_rewrites_a_confirmed_provisional_id(campaign):
    _rename_rider(campaign, "SOSA CUERVO", "SOMEONEELSE")
    rep = _ingest(campaign)
    assert rep.ok
    slug = rep.provisional_top[0]["rider_id"]

    # only a HUMAN confirmation rewrites an archived result
    proposed = [{"pcs_slug": slug, "fc_rider_id": "61639", "fc_name": "Sosa Ivan",
                 "birth_year": "1997", "confidence": "0.95", "confirmed_by": ""}]
    assert xw.confirmed_uci_mappings(proposed) == {}

    confirmed = [{**proposed[0], "confirmed_by": "mdp@example.org", "confidence": "1.00"}]
    mapping = xw.confirmed_uci_mappings(confirmed)
    assert set(mapping) == {slug}

    dry = xw.reconcile_results(campaign, mapping, dry_run=True)
    assert dry["changes"] and dry["dry_run"]
    assert any(r["rider_id"] == slug for r in _rows(campaign))               # untouched on a dry run

    out = xw.reconcile_results(campaign, mapping)
    assert {"results/stage_14/results.csv", "results/stage_14/gc.csv",
            "results/stage_14/results.json", "results/stage_14/classifications.json"} <= set(out["files_rewritten"])
    row = next(r for r in _rows(campaign) if r["place"] == "4")
    assert row["rider_id"] == "61639" and row["name"] == "Sosa Ivan"
    assert not any(r["rider_id"].startswith("uci:") for r in _rows(campaign, "gc.csv"))
    rj = json.loads((campaign / "results/stage_14/results.json").read_text())
    assert rj["provisional_identities"] == []
    assert next(r for r in rj["results"] if r["place"] == "4")["rider_id"] == "61639"
    cl = json.loads((campaign / "results/stage_14/classifications.json").read_text())
    assert not any(str(r.get("rider_id", "")).startswith("uci:")
                   for tbl in cl["tables"].values() for r in tbl if isinstance(r, dict))

    # idempotent: a second pass has nothing left to do
    assert xw.reconcile_results(campaign, mapping)["changes"] == []


def test_reconcile_results_cli_is_registered():
    args = xw.build_parser().parse_args(["reconcile-results", "--campaign", "x", "--dry-run"])
    assert args.func is xw.cmd_reconcile_results and args.dry_run
