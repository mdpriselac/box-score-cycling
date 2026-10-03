"""Day-key decision record: validator, driver rules, provenance, scoring."""

import json
from pathlib import Path

import pytest

from cycling_project.nightly import day_key_record as rec

MANIFEST = {"entries": [{"path": "odds/win_odds_1345.csv", "sha256": "a"},
                        {"path": "gc.csv", "sha256": "b"},
                        {"path": "settled_stages.json", "sha256": "c"}]}


def good_record(**over):
    base = {
        "race": "vuelta-2026", "stage": 14, "stage_date": "2026-09-05",
        "key": {"res_2": 0.6, "gc_day": 0.4},
        "family": "escape",
        "macro_routing": {"itt": False, "bunch_considered": False, "gc_day_considered": True,
                          "bunch_rejected_because": "", "gc_day_rejected_because": "leader's team in the move"},
        "primary_mechanism": "A 44-rider escape with Movistar represented is given seven minutes.",
        "credible_alternative": "The Pandera shatters the GC group and Mas wins.",
        "chase_incentive": {"who_has_reason_to_spend": [{"team": "Movistar", "why": "red jersey"}],
                            "verdict": "nobody_pays", "consequence_for_key": "res_2 up"},
        "comparables_used": [{"stage": 12, "argument": "Calar Alto", "measured_outcome": "break won by 2:56"}],
        "evidence": [{"claim": "Mas 3.75, Buitrago 6.50", "ref": "odds/win_odds_1345.csv"}],
        "missing_evidence": ["no route facts"],
        "conflicts": [],
        "confidence": 0.62,
        "human_review_required": False,
        "review_reason": "none",
    }
    base.update(over)
    return base


def test_valid_record_passes():
    assert rec.validate_record(good_record(), MANIFEST) == []


def test_weights_must_sum_to_one():
    errs = rec.validate_record(good_record(key={"res_2": 0.6, "gc_day": 0.5}), MANIFEST)
    assert any("sum to" in e for e in errs)
    assert rec.validate_record(good_record(key={"res_2": 0.6004, "gc_day": 0.4}), MANIFEST) == []


def test_res_5_and_unknown_items_rejected():
    errs = rec.validate_record(good_record(key={"res_5": 1.0}, family="power_sprint"), MANIFEST)
    assert any("res_5" in e for e in errs)
    errs = rec.validate_record(good_record(key={"res_9": 1.0}), MANIFEST)
    assert any("unknown menu item" in e for e in errs)


def test_no_cross_family_hedge_and_family_matches_argmax():
    errs = rec.validate_record(good_record(key={"res_2": 0.5, "res_3": 0.5}), MANIFEST)
    assert any("both residual families" in e for e in errs)
    errs = rec.validate_record(good_record(family="power_sprint"), MANIFEST)
    assert any("does not match argmax" in e for e in errs)
    assert rec.validate_record(good_record(key={"bunch": 0.6, "res_3": 0.4}, family="macro"), MANIFEST) == []


def test_evidence_refs_must_resolve_to_manifest():
    errs = rec.validate_record(good_record(evidence=[{"claim": "x", "ref": "odds/markets_9999.json"}]), MANIFEST)
    assert any("not a bundle file" in e for e in errs)
    errs = rec.validate_record(good_record(evidence=[]), MANIFEST)
    assert any("non-empty" in e for e in errs)
    errs = rec.validate_record(good_record(evidence=[{"claim": "x", "ref": "results/stage_14/results.json"}]),
                               MANIFEST, results_marker="stage_14")
    assert any("results for the stage" in e for e in errs)


def test_confidence_and_flag_types():
    assert any("confidence" in e for e in rec.validate_record(good_record(confidence=1.4), MANIFEST))
    assert any("human_review_required" in e for e in rec.validate_record(good_record(human_review_required="yes"), MANIFEST))


def test_assert_valid_raises_with_all_errors():
    with pytest.raises(rec.RecordValidationError) as ei:
        rec.assert_valid(good_record(key={"res_5": 0.7}, family="macro"), MANIFEST)
    assert len(ei.value.errors) >= 2


def test_driver_forces_review_on_missing_odds_and_low_confidence():
    r = rec.apply_driver_rules(good_record(confidence=0.7), odds_present=True)
    assert r["human_review_required"] is False and r["review_forced_by"] == [] and r["agent_self_flag"] is False

    r = rec.apply_driver_rules(good_record(confidence=0.7), odds_present=False)
    assert r["human_review_required"] is True and r["review_forced_by"] == ["missing odds"]
    assert "driver: missing odds" in r["review_reason"]

    r = rec.apply_driver_rules(good_record(confidence=0.5, review_reason="family torn"), odds_present=True)
    assert r["human_review_required"] is True
    assert r["review_forced_by"][0].startswith("low confidence")
    assert r["review_reason"].startswith("family torn; driver:")

    # the agent's own flag survives even when nothing is forced
    r = rec.apply_driver_rules(good_record(human_review_required=True), odds_present=True)
    assert r["human_review_required"] is True and r["agent_self_flag"] is True and r["review_forced_by"] == []


def test_driver_rules_by_odds_status():
    """Policy 2026-10-02 (chip Z3): `missing` (a configured market absent or degraded) still forces
    review; `not_offered` (the race never had a market) does not on its own — low confidence and
    the agent's own flag still do."""
    r = rec.apply_driver_rules(good_record(confidence=0.7), odds_status="missing")
    assert r["human_review_required"] is True and r["review_forced_by"] == ["missing odds"]

    r = rec.apply_driver_rules(good_record(confidence=0.7), odds_status="not_offered")
    assert r["human_review_required"] is False and r["review_forced_by"] == []
    assert "missing odds" not in r["review_reason"]

    r = rec.apply_driver_rules(good_record(confidence=0.4), odds_status="not_offered")
    assert r["human_review_required"] is True and r["review_forced_by"][0].startswith("low confidence")

    r = rec.apply_driver_rules(good_record(confidence=0.7, human_review_required=True,
                                           review_reason="terrain unknown on a possible non-bunch day"),
                               odds_status="not_offered")
    assert r["human_review_required"] is True and r["agent_self_flag"] is True
    assert r["review_reason"] == "terrain unknown on a possible non-bunch day"

    # an unknown status is read as missing; no status at all keeps the legacy default
    assert rec.apply_driver_rules(good_record(confidence=0.7), odds_status="weird")["review_forced_by"] == ["missing odds"]
    assert rec.apply_driver_rules(good_record(confidence=0.7))["review_forced_by"] == ["missing odds"]
    assert rec.ODDS_STATUSES == ("present", "missing", "not_offered")


def test_normalise_record_folds_key_items():
    out = {"key_items": [{"item": "res_2", "weight": 0.6}, {"item": "gc_day", "weight": 0.4}], "family": "escape"}
    r = rec.normalise_record(out, race="vuelta-2026", stage=14, stage_date="2026-09-05")
    assert list(r)[:4] == ["race", "stage", "stage_date", "key"]
    assert r["key"] == {"res_2": 0.6, "gc_day": 0.4} and "key_items" not in r
    # a duplicated item is visible as a bad total, not silently deduplicated
    dup = rec.normalise_key([{"item": "res_2", "weight": 0.6}, {"item": "res_2", "weight": 0.6}])
    assert dup == {"res_2": 1.2}


def test_schema_excludes_res_5_and_is_closed():
    items = rec.RECORD_SCHEMA["properties"]["key_items"]["items"]["properties"]["item"]["enum"]
    assert "res_5" not in items and set(items) == set(rec.MENU_ITEMS)
    assert rec.RECORD_SCHEMA["additionalProperties"] is False
    assert set(rec.RECORD_SCHEMA["required"]) == set(rec.RECORD_SCHEMA["properties"])


def test_provenance_stamp(tmp_path):
    skill = tmp_path / "SKILL.md"
    skill.write_text("---\nname: x\nversion: 2.3.4\n---\n# body\n")
    r = rec.stamp_provenance(good_record(), model_id="claude-opus-5", manifest_sha256="abc",
                             skill_path=skill, generated_at="2026-09-06T08:00:00+00:00", replay=True,
                             extra={"request_id": "req_1"})
    p = r["provenance"]
    assert p["skill_version"] == "2.3.4" and p["model_id"] == "claude-opus-5"
    assert p["bundle_manifest_sha256"] == "abc" and p["generated_at"] == "2026-09-06T08:00:00+00:00"
    assert p["skill_sha256"] and p["request_id"] == "req_1" and r["replay"] is True
    assert "skill_git_sha" in p and "skill_blob_sha" in p
    assert rec.skill_body(skill) == "# body\n"


def test_real_skill_has_semver_header():
    assert rec.skill_version(rec.SKILL_PATH).count(".") == 2
    assert tuple(int(x) for x in rec.skill_version(rec.SKILL_PATH).split(".")) >= (1, 1, 0)  # no-market rules (chip Z3)
    body = rec.skill_body(rec.SKILL_PATH)
    assert body.startswith("# Day-key read") and "version:" not in body[:40]


def test_score_agent_key():
    s = rec.score_agent_key(good_record(), "res_2")
    assert s["agent_exact"] and s["agent_covered"] and s["agent_weight_on_true"] == 0.6
    assert s["agent_flagged"] is False and s["agent_family_covered"] is True and s["agent_replay"] is False
    s = rec.score_agent_key(good_record(key={"gc_day": 0.6, "res_2": 0.4}, replay=True), "res_2")
    assert not s["agent_exact"] and s["agent_covered"] and s["agent_weight_on_true"] == 0.4 and s["agent_replay"]
    s = rec.score_agent_key(good_record(key={"bunch": 1.0}), "res_2")
    assert s["agent_covered"] is False and s["agent_family_covered"] is False
    assert rec.score_agent_key(None, "res_2")["agent_key"] is None
    # the reader's raw answer, saved by the coordinator without the fold (CRO Race st4, 2026-09-25)
    raw = good_record()
    raw.pop("key")
    raw["key_items"] = [{"item": "bunch", "weight": 0.5}, {"item": "res_3", "weight": 0.28},
                        {"item": "gc_day", "weight": 0.22}]
    s = rec.score_agent_key(raw, "bunch")
    assert s["agent_key"] == {"bunch": 0.5, "res_3": 0.28, "gc_day": 0.22}
    assert s["agent_exact"] and s["agent_weight_on_true"] == 0.5 and s["agent_confidence"] == 0.62
    assert rec.score_agent_key({"key_items": []}, "bunch")["agent_key"] is None
    assert rec.family_covered({"res_4": 1.0}, "res_2") is True
    assert rec.family_covered({"res_7": 1.0}, "res_2") is False
