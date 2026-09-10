"""Two defects seen previewing Vuelta stage 18 on 2026-09-09 (``filled: []`` on two runs in a row).

``predictions/TEMPLATE_scenarios.json`` ships sentinels rather than empty fields — ``event_id:
FILL_FROM_ODDS_PROVENANCE`` and ``odds_capture: YYYY-MM-DD/markets_HHMM.json`` — and both are
truthy, so the driver's fill guards read a freshly templated config as already filled; the sentinel
was then handed to ``_newest_snapshot`` as an event id, where it matched nothing.  The second defect
is one step upstream: ``capture_odds`` merges newly discovered Kambi event ids into
``campaign.json``, but ``Campaign`` caches that file at load, so an id found by step 1 was invisible
to step 2 of the same run.  The operator filled both fields by hand.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from cycling_project.nightly import driver as drv

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
CAMPAIGN = FIXTURES / "nightly" / "driver_stage14"

UNIT = "stage_16"                       # the first unit of the fixture with no committed scenarios.json
EVENT_ID = "1028797740"
TODAY = "2026-09-07"
SNAPSHOT = f"{TODAY}/markets_1558.json"


@pytest.fixture
def campaign(tmp_path):
    """The stage-14 campaign, plus two same-day snapshots: only the earlier one lists stage 16."""
    dst = tmp_path / "vuelta-2026"
    shutil.copytree(CAMPAIGN, dst)
    src = json.loads((dst / "odds/2026-09-05/markets_1720.json").read_text())
    day = dst / "odds" / TODAY
    day.mkdir(parents=True)
    (day / "markets_1558.json").write_text(json.dumps({EVENT_ID: src["1028797735"], "1028635359": src["1028635359"]}))
    (day / "markets_1900.json").write_text(json.dumps({"1028635359": src["1028635359"]}))
    return dst


def _preview(campaign, tmp_path, *extra):
    """``nightly preview`` against a FakeStore — never the hosted ledger (CLAUDE.md)."""
    return drv.main(["preview", "--unit", UNIT, "--campaign", str(campaign),
                     "--store", "fake", "--store-root", str(tmp_path / "store"),
                     "--crosswalk", str(campaign / "rider_crosswalk.csv"), "--today", TODAY,
                     "--db-path", str(tmp_path / "nonexistent.db"), *extra])


def _ledger(tmp_path, table):
    p = tmp_path / "store" / "ledger" / f"{table}.jsonl"
    return [json.loads(ln) for ln in p.read_text().splitlines()] if p.exists() else []


def _config(campaign):
    return json.loads((campaign / "predictions" / UNIT / "scenarios.json").read_text())


def _set_event_id(campaign, unit, event_id):
    path = campaign / "campaign.json"
    cfg = json.loads(path.read_text())
    cfg["kambi_event_ids"][unit] = event_id
    path.write_text(json.dumps(cfg, indent=1))


# ---------------------------------------------------------------------------
# the sentinels
# ---------------------------------------------------------------------------

def test_a_template_sentinel_is_not_a_value():
    assert drv._is_placeholder("FILL_FROM_ODDS_PROVENANCE") and drv._is_placeholder("FILL_FROM_ODDS_PROVENANCE", numeric=True)
    assert drv._is_placeholder("YYYY-MM-DD/markets_HHMM.json")
    assert drv._is_placeholder(None) and drv._is_placeholder("") and drv._is_placeholder("  ")
    # real values are not placeholders
    assert not drv._is_placeholder("2026-09-07/markets_1558.json")
    assert not drv._is_placeholder("1028797740") and not drv._is_placeholder("1028797740", numeric=True)
    # numeric=True is the event-id branch: a Kambi id is always digits
    assert drv._is_placeholder("tbc", numeric=True) and not drv._is_placeholder("tbc")


def test_a_templated_config_fills_its_sentinel_event_id_and_odds_capture(campaign, tmp_path, capsys):
    template = json.loads((campaign / "predictions" / drv.TEMPLATE_NAME).read_text())
    assert template["event_id"] == "FILL_FROM_ODDS_PROVENANCE" and template["odds_capture"].startswith("YYYY")
    _set_event_id(campaign, UNIT, EVENT_ID)

    # the run stops later, at day_key: stage 16 has no scenario references yet.  The config
    # was written — with both fields filled — several steps before that.
    assert _preview(campaign, tmp_path, "--dry-run") == drv.EXIT_WAITING
    assert json.loads(capsys.readouterr().out)["operator_task"]["kind"] == "scenarios_needed"

    cfg = _config(campaign)
    assert cfg["event_id"] == EVENT_ID
    # markets_1900.json is newer but lists no stage-16 market: the real id, not the sentinel, chose this file
    assert cfg["odds_capture"] == SNAPSHOT
    step = next(s for s in _ledger(tmp_path, "run_steps") if s["step"] == "stage_config")
    assert step["detail"] == {"created": True, "filled": ["event_id", "odds_capture"]}


def test_an_unresolved_event_id_does_not_select_an_unrelated_snapshot(campaign, tmp_path, capsys):
    assert UNIT not in json.loads((campaign / "campaign.json").read_text())["kambi_event_ids"]

    assert _preview(campaign, tmp_path, "--dry-run") == drv.EXIT_WAITING
    assert json.loads(capsys.readouterr().out)["operator_task"]["kind"] == "scenarios_needed"

    cfg = _config(campaign)
    assert cfg["event_id"] is None
    assert cfg["odds_capture"] is None
    assert cfg["odds_capture"] != f"{TODAY}/markets_1900.json"


def test_a_config_that_already_carries_real_values_is_left_alone(campaign, tmp_path):
    _set_event_id(campaign, UNIT, EVENT_ID)
    pred = campaign / "predictions" / UNIT
    pred.mkdir(parents=True, exist_ok=True)
    (pred / "scenarios.json").write_text(json.dumps(
        {"stage": 16, "fc_race_id": "23", "year": 2026, "date": "2026-09-08", "label": "Stage 16",
         "event_id": "1028797999", "odds_capture": "2026-09-04/markets_1345.json",
         "day_key": {"bunch": 1.0}, "void_stages": [3], "scenarios": {}}))

    assert _preview(campaign, tmp_path, "--dry-run") == drv.EXIT_DONE
    cfg = _config(campaign)
    assert cfg["event_id"] == "1028797999" and cfg["odds_capture"] == "2026-09-04/markets_1345.json"
    step = next(s for s in _ledger(tmp_path, "run_steps") if s["step"] == "stage_config")
    assert step["detail"] == {"created": False, "filled": []}


@pytest.mark.parametrize("field,value", [
    ("event_id", "FILL_FROM_ODDS_PROVENANCE"),
    ("odds_capture", "YYYY-MM-DD/markets_HHMM.json"),
])
def test_validate_hard_fails_a_remaining_template_sentinel(campaign, tmp_path, capsys, field, value):
    pred = campaign / "predictions" / UNIT
    pred.mkdir(parents=True, exist_ok=True)
    cfg = {"stage": 16, "fc_race_id": "23", "year": 2026, "date": TODAY,
           "event_id": None, "odds_capture": None, "void_stages": [], "scenarios": {}}
    cfg[field] = value
    (pred / "scenarios.json").write_text(json.dumps(cfg))

    code = drv.main(["validate", "--unit", UNIT, "--campaign", str(campaign),
                     "--store", "fake", "--store-root", str(tmp_path / "store"),
                     "--crosswalk", str(campaign / "rider_crosswalk.csv"), "--today", TODAY,
                     "--db-path", str(tmp_path / "nonexistent.db"), "--dry-run"])
    out = json.loads(capsys.readouterr().out)
    assert code == drv.EXIT_WAITING and out["operator_task"]["kind"] == "validate_failed"
    assert any(field in problem and "placeholder" in problem
               for problem in out["operator_task"]["detail"]["problems"])


# ---------------------------------------------------------------------------
# the cached campaign.json
# ---------------------------------------------------------------------------

def test_an_event_id_the_odds_capture_discovers_is_usable_in_the_same_run(campaign, tmp_path, monkeypatch):
    assert UNIT not in json.loads((campaign / "campaign.json").read_text())["kambi_event_ids"]

    def fake_run(argv, **kw):
        argv = [str(a) for a in argv]
        if any(Path(a).name == "capture_odds.py" for a in argv):   # what the real script does with a new market
            _set_event_id(campaign, UNIT, EVENT_ID)
        return subprocess.CompletedProcess(argv, 0, stdout="fake ok\n", stderr="")

    monkeypatch.setattr(drv.subprocess, "run", fake_run)
    assert _preview(campaign, tmp_path, "--no-log") == drv.EXIT_WAITING      # day_key again
    cfg = _config(campaign)
    assert cfg["event_id"] == EVENT_ID and cfg["odds_capture"] == SNAPSHOT


def test_refresh_event_ids_reports_only_what_is_new_and_never_drops_what_is_known(campaign):
    c = drv.Campaign.load(campaign)
    known = dict(c.cfg["kambi_event_ids"])
    assert c.refresh_event_ids() == {}                                        # nothing changed on disk
    _set_event_id(campaign, UNIT, EVENT_ID)
    assert c.refresh_event_ids() == {UNIT: EVENT_ID}
    assert c.cfg["kambi_event_ids"] == {**known, UNIT: EVENT_ID}
    assert c.refresh_event_ids() == {}                                        # idempotent
