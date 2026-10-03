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


# --- --backfill: the card is monotonic (chip Z2, 2026-10-02) -----------------------------------
# Every release rolled review/key_scorecard.json back to the Mac's copy and each settle scored only
# --stage N, so a lost row never came back (Langkawi st3, CRO st2-4). --backfill scores every
# settled stage missing a row and attaches unscored prospective agent keys; existing rows are never
# re-labelled. The oracle is stubbed: labelling needs the DB's rider profiles.

def _stub_oracle(mod, label="res_9"):
    calls = []

    def fake(stage, menu):
        calls.append(stage)
        return {"stage": stage, "oracle_item": label, "day_class": "residual", "rule_type": "x", "wg_size": 3,
                "wg_prop": 0.02, "winning_time": 15000, "winner": "W", "winner_gc_morning": None,
                "front5_gc_median": None, "top15_shares": {}, "top15_unknown": 0.0}
    mod.oracle_item = fake
    return calls


def test_backfill_restores_a_lost_row_and_attaches_a_raw_shape_agent_key(sdk):
    mod, camp = sdk
    calls = _stub_oracle(mod)
    card = json.loads(mod.SCORECARD.read_text())
    kept = {r["stage"]: dict(r) for r in card}
    card = [r for r in card if r["stage"] != 13]                    # the release overlay dropped st13
    # st12: a prospective record saved in the reader's raw key_items shape, row unscored
    (camp / "predictions/stage_12/agent_key.json").write_text(json.dumps(
        {"key_items": [{"item": kept[12]["oracle_item"], "weight": 0.7}, {"item": "bunch", "weight": 0.3}],
         "family": "escape", "confidence": 0.6, "human_review_required": True, "replay": False}))
    assert mod.backfill_targets(card, also_agent=True) == {"missing": [13], "agent": [12], "replay": []}

    card, done = mod.backfill(card, menu=None, also_agent=True)
    assert done == {"missing": [13], "agent": [12], "replay": []}
    assert calls == [13]                                            # only the lost stage is labelled
    rows = {r["stage"]: r for r in card}
    assert sorted(rows) == [12, 13, 14]
    assert rows[13]["oracle_item"] == "res_9" and rows[13]["scored_at"]
    assert rows[12]["oracle_item"] == kept[12]["oracle_item"]       # never re-labelled
    assert rows[12]["agent_key"] is not None and rows[12]["agent_exact"] is True
    assert rows[14] == kept[14]                                     # untouched

    # idempotent: nothing left to do, nothing relabelled
    assert mod.backfill_targets(card, also_agent=True) == {"missing": [], "agent": [], "replay": []}
    card2, done2 = mod.backfill(card, menu=None, also_agent=True)
    assert done2 == {"missing": [], "agent": [], "replay": []} and card2 == card and calls == [13]


def test_backfill_keeps_replay_records_off_the_archive(sdk):
    mod, camp = sdk
    _stub_oracle(mod)
    card = json.loads(mod.SCORECARD.read_text())
    (camp / "predictions/stage_13/agent_key.json").write_text(json.dumps(
        _agent_record({"res_2": 0.6, "gc_day": 0.4}, replay=True)))
    card, done = mod.backfill(card, menu=None, also_agent=True)
    assert done == {"missing": [], "agent": [], "replay": [13]}
    assert "agent_key" not in next(r for r in card if r["stage"] == 13)
    assert [r["stage"] for r in json.loads(mod.REPLAY_SCORECARD.read_text())] == [13]
    assert mod.backfill_targets(card, also_agent=True)["replay"] == []


def test_backfill_ignores_unsettled_and_void_stages(sdk):
    mod, camp = sdk
    calls = _stub_oracle(mod)
    (camp / "results/stage_15").mkdir()                             # void / not yet settled: no results.json
    card = json.loads(mod.SCORECARD.read_text())
    card, done = mod.backfill(card, menu=None, also_agent=False)
    assert done["missing"] == [] and calls == []


def test_main_backfill_writes_the_stage_and_every_missing_row(sdk, monkeypatch, capsys):
    mod, camp = sdk
    calls = _stub_oracle(mod)
    monkeypatch.setattr(mod, "load_menu", lambda: None)
    monkeypatch.setattr(mod, "set_campaign", lambda p: None)        # the fixture already points the module
    card = json.loads(mod.SCORECARD.read_text())
    mod.SCORECARD.write_text(json.dumps([r for r in card if r["stage"] == 12]))   # rolled back to st12 only
    monkeypatch.setattr("sys.argv", ["score_day_keys.py", "--campaign", str(camp), "--stage", "14",
                                     "--also", "agent", "--backfill"])
    mod.main()
    rows = json.loads(mod.SCORECARD.read_text())
    assert [r["stage"] for r in rows] == [12, 13, 14] and calls == [14, 13]
    assert '"missing": [13]' in capsys.readouterr().out
