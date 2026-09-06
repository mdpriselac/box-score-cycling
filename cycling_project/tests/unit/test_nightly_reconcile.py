"""PCS ↔ FirstCycling reconciliation on a seeded mismatch.

Builds a synthetic FirstCycling ``Race`` pickle under a fake
``SCRAPED_DATA_DIR`` and a campaign dir whose ``results/stage_NN/results.csv``
disagrees with it, then asserts the diff, the jsonl/store records, the
operator task and the exit codes.
"""

import csv
import json
import pickle
from pathlib import Path

import pytest

from cycling_project.nightly import reconcile as rc
from cycling_project.nightly.store_local import JsonlStore
from cycling_project.webscrape_tools.create_race_data import Race, Stage

FIELDS = ["place", "name", "rider_id", "team", "team_id", "gap", "dob"]


def _row(place, name, rid, gap, dob="1995"):
    return {"place": str(place), "name": name, "rider_id": str(rid), "team": "T", "team_id": "9",
            "gap": gap, "dob": dob, "bib_number": str(place)}


def _stage_rows(n=30):
    rows = [_row(i, f"Rider {i}", 1000 + i, 0 if i == 1 else float(i * 3)) for i in range(1, n + 1)]
    rows.append({"place": "DNF", "name": "Quit Q", "rider_id": "2000", "team": "T", "team_id": "9", "gap": "", "dob": "1990"})
    return rows


@pytest.fixture
def scraped(tmp_path):
    """Fake SCRAPED_DATA_DIR with a settled stage race (fc id 23, 2026, wt)."""
    tour = tmp_path / "scraped" / "2026" / "wt"
    tour.mkdir(parents=True)
    (tour / "wt.txt").write_text("Vuelta a España,https://firstcycling.com/race.php?r=23&y=2026\n")
    race = Race(name="Vuelta a España", url="https://firstcycling.com/race.php?r=23&y=2026", year=2026,
                stage_race=True, fc_race_id=23)
    gc = Stage(name="GC", url="https://firstcycling.com/race.php?r=23&y=2026&e=", fc_race_id=23, year=2026,
               date="2026-09-13", results=_stage_rows())
    stages = [gc]
    for n in (1, 2, 4):
        stages.append(Stage(name=f"Stage: {n:02d}", url=f"https://firstcycling.com/race.php?r=23&y=2026&e={n}",
                            fc_race_id=23, year=2026, date=f"2026-08-{21 + n:02d}", results=_stage_rows()))
    race.stages = stages
    race.results = gc.results
    with open(tour / "Vuelta a España.pkl", "wb") as f:
        pickle.dump(race, f)
    return tmp_path / "scraped"


def _write_csv(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


@pytest.fixture
def campaign(tmp_path):
    c = tmp_path / "vuelta-2026"
    c.mkdir()
    (c / "campaign.json").write_text(json.dumps({"fc_race_id": 23, "year": 2026, "slug": "vuelta-2026"}))
    # stage 1 identical; stage 2 has a swapped podium (id diffs); stage 4 has
    # three top-20 gap diffs (drift by count) but no id diff.
    _write_csv(c / "results/stage_01/results.csv", _stage_rows())
    s2 = _stage_rows()
    s2[0]["rider_id"], s2[1]["rider_id"] = s2[1]["rider_id"], s2[0]["rider_id"]
    _write_csv(c / "results/stage_02/results.csv", s2)
    s4 = _stage_rows()
    for i in (4, 9, 14):
        s4[i]["gap"] = float(s4[i]["gap"]) + 5
    _write_csv(c / "results/stage_04/results.csv", s4)
    _write_csv(c / "results/stage_04/gc.csv", _stage_rows())
    return c


def test_find_race_pickle_via_race_list(scraped):
    p = rc.find_race_pickle(scraped, 2026, "23")
    assert p is not None and p.name == "Vuelta a España.pkl"
    assert rc.find_race_pickle(scraped, 2026, "999") is None


def test_diff_rows_flags_id_and_gap_differences():
    fc = _stage_rows()
    pcs = _stage_rows()
    pcs[2]["rider_id"] = "5555"          # place 3: different rider
    pcs[5]["gap"] = 99.0                 # place 6: gap differs
    pcs[25]["gap"] = 0.2                 # place 26: within tolerance? no — 78 vs 0.2 differs, but outside top 20
    d = rc.diff_rows(pcs, fc, campaign="c", unit="stage_01", kind="stage")
    assert [x["place"] for x in d.id_diffs] == [3]
    assert sorted(x["place"] for x in d.gap_diffs) == [6, 26]
    assert d.top20_diff_places == [3, 6]
    assert d.drift  # any id diff is drift


def test_two_top20_gap_diffs_are_tolerated_three_are_not():
    fc = _stage_rows()
    pcs = _stage_rows()
    for i in (0, 1):
        pcs[i]["gap"] = float(pcs[i]["gap"] or 0) + 10
    assert not rc.diff_rows(pcs, fc, campaign="c", unit="u", kind="stage").drift
    pcs[2]["gap"] = float(pcs[2]["gap"]) + 10
    assert rc.diff_rows(pcs, fc, campaign="c", unit="u", kind="stage").drift


def test_dnf_rows_are_ignored_and_gap_tolerance_applies():
    fc = _stage_rows()
    pcs = _stage_rows()
    pcs[-1]["rider_id"] = "3000"         # DNF row: not classified, never compared
    pcs[3]["gap"] = float(pcs[3]["gap"]) + 0.4
    d = rc.diff_rows(pcs, fc, campaign="c", unit="u", kind="stage")
    assert not d.id_diffs and not d.gap_diffs and not d.drift


def test_run_reconcile_seeded_mismatch_exits_10_with_task(scraped, campaign, tmp_path):
    runs = tmp_path / "runs"
    store = JsonlStore(runs_dir=runs, role="agent")
    code, report = rc.run_reconcile(campaign, scraped_dir=scraped, race_id=None, year=None,
                                    store=store, runs_dir=runs)
    assert code == rc.EXIT_WAITING
    units = {u["unit"]: u for u in report["units"]}
    assert units["stage_01"]["verdict"] == "ok"
    assert units["stage_02"]["verdict"] == "drift" and units["stage_02"]["id_diffs"] == 2
    assert units["stage_04"]["verdict"] == "drift" and units["stage_04"]["top20_diffs"] == 3
    assert units["gc@stage_04"]["verdict"] == "ok"
    assert report["drift_units"] == ["stage_02", "stage_04"]
    # ledger + task
    lines = (runs / "reconciliation.jsonl").read_text().splitlines()
    assert len(lines) == 4 and all(json.loads(l)["fc_race_id"] == "23" for l in lines)
    assert len(store.rows["reconciliation"]) == 4
    task = store.rows["operator_tasks"][0]
    assert task["kind"] == "reconciliation_drift" and task["urgency"] == "blocks_settlement"
    assert {u["unit"] for u in task["detail"]["units"]} == {"stage_02", "stage_04"}
    assert report["operator_task"]["kind"] == "reconciliation_drift"


def test_run_reconcile_clean_campaign_exits_0(scraped, campaign, tmp_path):
    # Overwrite the drifted stages with matching rows.
    _write_csv(campaign / "results/stage_02/results.csv", _stage_rows())
    _write_csv(campaign / "results/stage_04/results.csv", _stage_rows())
    store = JsonlStore(runs_dir=None, role="agent")
    code, report = rc.run_reconcile(campaign, scraped_dir=scraped, race_id="23", year=2026,
                                    store=store, runs_dir=tmp_path / "runs")
    assert code == rc.EXIT_OK and report["drift_units"] == [] and report["operator_task"] is None
    assert "operator_tasks" not in store.rows


def test_stage_missing_from_pickle_is_skipped_not_drift(scraped, campaign, tmp_path):
    _write_csv(campaign / "results/stage_09/results.csv", _stage_rows())
    store = JsonlStore(runs_dir=None, role="agent")
    code, report = rc.run_reconcile(campaign, scraped_dir=scraped, race_id=None, year=None,
                                    store=store, runs_dir=tmp_path / "runs", stages=[9])
    assert code == rc.EXIT_OK
    stage9 = next(u for u in report["units"] if u["unit"] == "stage_09")
    assert stage9["verdict"] == "skipped" and stage9["comparable"] is False


def test_missing_pickle_exits_20(campaign, tmp_path):
    store = JsonlStore(runs_dir=None, role="agent")
    code, report = rc.run_reconcile(campaign, scraped_dir=tmp_path / "nowhere", race_id=None, year=None,
                                    store=store, runs_dir=tmp_path / "runs")
    assert code == rc.EXIT_FAILED and "no FirstCycling pickle" in report["error"]


def test_cli_main_exit_code(scraped, campaign, tmp_path, capsys):
    code = rc.main(["--scraped-dir", str(scraped), "--runs-dir", str(tmp_path / "runs"), "--store", "none",
                    "reconcile", "--campaign", str(campaign), "--stage", "1"])
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert [u["unit"] for u in out["units"]] == ["stage_01", "gc@stage_04"]


def test_reconcile_all_campaigns_is_non_fatal(scraped, campaign, tmp_path):
    perf = campaign.parent
    other = perf / "broken-2026"
    other.mkdir()
    (other / "campaign.json").write_text(json.dumps({"fc_race_id": 777, "year": 2026}))
    _write_csv(other / "results/stage_01/results.csv", _stage_rows())
    store = JsonlStore(runs_dir=None, role="agent")
    reports = rc.reconcile_all_campaigns(perf, scraped_dir=scraped, store=store, runs_dir=tmp_path / "runs")
    by = {r["campaign"]: r for r in reports}
    assert by["vuelta-2026"]["exit"] == rc.EXIT_WAITING
    assert by["broken-2026"]["exit"] == rc.EXIT_FAILED


def test_update_pipeline_reconcile_is_opt_in():
    from cycling_project.update_pipeline import build_parser, should_run
    args = build_parser().parse_args([])
    assert not should_run("reconcile", args)
    assert should_run("reconcile", build_parser().parse_args(["--reconcile"]))
    assert should_run("reconcile", build_parser().parse_args(["--only", "reconcile"]))
    assert not should_run("train", build_parser().parse_args(["--only", "reconcile"]))
