"""score_day_keys.py --also agent: paired fields, replay routing, Gate K table.

Imports the campaign script with its archive paths pointed at a temp copy of
the stage-14 fixture; the oracle rows come from the fixture scorecard, so no
DB is needed.
"""

import importlib.util
import json
import shutil
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = PROJECT_ROOT / "performance_eval" / "vuelta-2026" / "score_day_keys.py"
FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "nightly" / "day_key_stage14"


@pytest.fixture
def sdk(tmp_path):
    if not SCRIPT.exists():
        pytest.skip("campaign script not present")
    camp = tmp_path / "vuelta-2026"
    shutil.copytree(FIXTURE, camp)
    spec = importlib.util.spec_from_file_location("score_day_keys_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.PREDICTIONS_ROOT = camp / "predictions"
    mod.RESULTS_ROOT = camp / "results"
    mod.SCORECARD = camp / "review" / "key_scorecard.json"
    mod.REPLAY_SCORECARD = camp / "review" / "agent_replay_scorecard.json"
    return mod, camp


def _agent_record(key, *, replay, flagged=False, confidence=0.6):
    return {"key": key, "family": "escape", "confidence": confidence, "human_review_required": flagged,
            "agent_self_flag": flagged, "replay": replay}


def test_prospective_record_lands_on_the_row_and_human_fields_are_untouched(sdk):
    mod, camp = sdk
    card = json.loads(mod.SCORECARD.read_text())
    row = next(r for r in card if r["stage"] == 14)
    before = dict(row)
    card2 = mod.write_agent_score(row, _agent_record({"res_2": 0.65, "gc_day": 0.35}, replay=False), card)
    new = next(r for r in card2 if r["stage"] == 14)
    assert new["agent_key"] == {"res_2": 0.65, "gc_day": 0.35} and new["agent_exact"] is True
    assert new["agent_covered"] is True and new["agent_weight_on_true"] == 0.65 and new["agent_flagged"] is False
    for k in ("day_key", "exact", "covered", "weight_on_true", "oracle_item"):
        assert new[k] == before[k]
    assert not mod.REPLAY_SCORECARD.exists()


def test_replay_record_goes_to_the_replay_card_not_the_archive(sdk):
    mod, camp = sdk
    card = json.loads(mod.SCORECARD.read_text())
    row = next(r for r in card if r["stage"] == 14)
    card2 = mod.write_agent_score(row, _agent_record({"gc_day": 0.6, "res_2": 0.4}, replay=True, flagged=True), card)
    assert "agent_key" not in next(r for r in card2 if r["stage"] == 14)
    rep = json.loads(mod.REPLAY_SCORECARD.read_text())
    assert [r["stage"] for r in rep] == [14] and rep[0]["agent_replay"] is True
    assert rep[0]["agent_exact"] is False and rep[0]["agent_weight_on_true"] == 0.4 and rep[0]["agent_flagged"] is True
    # paired rows merge both sources; the human fields ride along for pairing
    rows = mod.paired_rows(card2)
    assert rows[0]["stage"] == 14 and rows[0]["day_key"] == row["day_key"]


def test_agent_refresh_and_paired_table(sdk, capsys):
    mod, camp = sdk
    (camp / "predictions/stage_12/agent_key.json").write_text(json.dumps(
        _agent_record({"res_2": 0.7, "gc_day": 0.3}, replay=True)))
    (camp / "predictions/stage_14/agent_key.json").write_text(json.dumps(
        _agent_record({"res_2": 0.55, "gc_day": 0.45}, replay=True)))
    card = mod.agent_refresh()
    assert all("agent_key" not in r for r in card)           # replay never touches the archive
    rep = json.loads(mod.REPLAY_SCORECARD.read_text())
    assert [r["stage"] for r in rep] == [12, 14]
    mod.print_paired_table(card)
    out = capsys.readouterr().out
    assert "Gate K (replay, 2 judgment stages)" in out
    assert "1 covered      human 1.00  agent 1.00  -> PASS" in out
    assert "family regressions" in out and "Gate K (prospective" not in out
