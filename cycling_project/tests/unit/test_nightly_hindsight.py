from __future__ import annotations

import json
from pathlib import Path

from cycling_project.nightly import hindsight, oneday


def _result():
    return {
        "results": [
            {"place": "1", "name": "Winner", "rider_id": "11", "team": "A", "gap": 0},
            {"place": "2", "name": "Second", "rider_id": "12", "team": "A", "gap": 0},
            {"place": "3", "name": "Third", "rider_id": "13", "team": "B", "gap": 8},
        ]
    }


def test_stage_hindsight_uses_oracle_and_freezes_result_field(tmp_path, monkeypatch):
    campaign = tmp_path / "race-2026"
    result_dir = campaign / "results" / "stage_02"
    result_dir.mkdir(parents=True)
    (result_dir / "results.json").write_text(json.dumps(_result()))
    review = campaign / "review"
    review.mkdir()
    (review / "key_scorecard.json").write_text(json.dumps([
        {"stage": 2, "oracle_item": "res_4", "day_class": "residual"}
    ]))
    monkeypatch.setattr(hindsight, "result_signature", lambda *a, **k: {
        "rule_type": "tiny_group", "wg_size": 2, "wg_prop": .02,
        "top15_shares": {a: 0 for a in hindsight.ARCH},
    })
    monkeypatch.setattr(hindsight, "nearest_refs", lambda *a, **k: [101, 102, 103])

    out = hindsight.build(campaign, "stage_02", fc_race_id="9", year=2026,
                          date="2026-09-02", label="Stage 2", db_path=tmp_path / "none.db",
                          stage=2, void_stages=[1])

    cfg = json.loads(Path(out["path"]).read_text())
    assert cfg["post_hoc"] is True and cfg["void_stages"] == [1]
    assert cfg["scenarios"]["hindsight"]["day_key"] == {"res_4": 1.0}
    assert cfg["scenarios"]["hindsight"]["refs"] == [101, 102, 103]
    field = json.loads((campaign / "predictions/stage_02/startlist.json").read_text())
    assert field["source"].startswith("settled results")
    assert sum(len(t["riders"]) for t in field["teams"]) == 3


def test_one_day_hindsight_is_valid_and_has_no_day_key(tmp_path, monkeypatch):
    campaign = tmp_path / "classic-2026"
    result_dir = campaign / "results" / "race"
    result_dir.mkdir(parents=True)
    (result_dir / "results.json").write_text(json.dumps(_result()))
    monkeypatch.setattr(hindsight, "result_signature", lambda *a, **k: {
        "rule_type": "tiny_group", "wg_size": 2, "wg_prop": .02,
        "top15_shares": {a: 0 for a in hindsight.ARCH},
    })
    monkeypatch.setattr(hindsight, "nearest_refs", lambda *a, **k: [201, 202])

    out = hindsight.build(campaign, "race", fc_race_id="10", year=2026,
                          date="2026-09-03", label="A Classic", db_path=tmp_path / "none.db",
                          stage=None)

    cfg = json.loads(Path(out["path"]).read_text())
    assert cfg["target"] == "one_day" and cfg["post_hoc"] is True
    assert "day_key" not in cfg and "day_key" not in cfg["scenarios"]["hindsight"]
    assert oneday.validate_config(cfg) == []
