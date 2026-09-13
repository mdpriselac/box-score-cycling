"""The last stage of a stage race takes its overall classifications from the
competition's "Final Classification" accordion entry, not its own.

Vuelta a España 2026, competition 76942, 2026-09-13: the stage-21 accordion held
only Stage / Stage Points / Stage Mountain / Stage Youth Classification, while a
sibling entry labelled "Final Classification" held General Classification
D2EV375983. Stages 1..20 each carried their own "Stage General Classification",
so only the final stage is affected — and it was permanently un-settleable,
because `gc` is required for a stage unit.
"""

import pytest

from cycling_project.nightly import uci_acquire as ua


def _props(last_stage_has_gc: bool = False, with_final: bool = True):
    stage_results = [{"title": "Stage Classification", "eventCode": "D2EV1", "raceType": "A"},
                     {"title": "Stage Points Classification", "eventCode": "D2EV2", "raceType": "A"}]
    if last_stage_has_gc:
        stage_results.append(
            {"title": "Stage General Classification", "eventCode": "D2EVSTAGEGC", "raceType": "A"})
    accordion = [
        {"label": "Stage 20", "results": [
            {"title": "Stage Classification", "eventCode": "D2EV20", "raceType": "A"},
            {"title": "Stage General Classification", "eventCode": "D2EVGC20", "raceType": "A"},
        ]},
        {"label": "Stage 21", "results": stage_results},
    ]
    if with_final:
        accordion.append({"label": "Final Classification", "results": [
            {"title": "General Classification", "eventCode": "D2EVFINALGC", "raceType": "A"},
            {"title": "Points Classification", "eventCode": "D2EVFINALPTS", "raceType": "A"},
            {"title": "Mountain Classification", "eventCode": "D2EVFINALKOM", "raceType": "A"},
            {"title": "Youth Classification", "eventCode": "D2EVFINALYTH", "raceType": "A"},
        ]})
    schedule = {"items": [
        {"date": "12 Sep 2026", "races": [{"raceName": "Stage 20", "raceType": "Individual Road Race"}]},
        {"date": "13 Sep 2026", "races": [{"raceName": "Stage 21", "raceType": "Individual Road Race"}]},
    ]}
    return {"results": {"accordion": accordion}, "schedule": schedule}


@pytest.mark.unit
def test_is_last_stage_reads_the_schedule():
    props = _props()
    assert ua.is_last_stage(props, "stage_21") is True
    assert ua.is_last_stage(props, "stage_20") is False
    assert ua.is_last_stage(props, "race") is False


@pytest.mark.unit
def test_find_stage_exposes_the_final_accordion_on_the_last_stage():
    props = _props()
    got = ua.find_stage(props, "stage_21")
    assert got["is_last_stage"] is True
    assert got["final_accordion"]["label"] == "Final Classification"

    mid = ua.find_stage(props, "stage_20")
    assert mid["is_last_stage"] is False
    # the entry is still reported, but the caller must not pass it for a mid-race stage
    assert mid["final_accordion"]["label"] == "Final Classification"


@pytest.mark.unit
def test_last_stage_takes_gc_from_the_final_accordion():
    props = _props()
    stage = ua.find_stage(props, "stage_21")
    sel = ua.select_classifications(stage["accordion"], None, final_entry=stage["final_accordion"])
    assert sel["stage"]["event_code"] == "D2EV1"
    assert sel["gc"]["event_code"] == "D2EVFINALGC"
    assert sel["gc"]["from_final_accordion"] is True
    # the other jerseys come across under their bare final-accordion titles
    assert sel["points"]["event_code"] == "D2EVFINALPTS"
    assert sel["kom"]["event_code"] == "D2EVFINALKOM"
    assert sel["youth"]["event_code"] == "D2EVFINALYTH"


@pytest.mark.unit
def test_the_stage_result_is_never_taken_from_the_final_accordion():
    """'stage' is excluded from the fallback: a stage result is its own document."""
    assert "stage" not in ua.FINAL_FALLBACK_KINDS
    props = _props()
    stage = ua.find_stage(props, "stage_21")
    entry = {"label": "Stage 21", "results": []}          # nothing in the stage's own entry
    sel = ua.select_classifications(entry, None, final_entry=stage["final_accordion"])
    assert "stage" not in sel
    assert sel["gc"]["event_code"] == "D2EVFINALGC"


@pytest.mark.unit
def test_a_mid_race_stage_never_reads_the_final_accordion():
    """The regression this guards: a stage-14 capture must not attach the race's
    final standings. The caller passes final_entry=None for any non-final stage."""
    props = _props()
    stage = ua.find_stage(props, "stage_20")
    sel = ua.select_classifications(stage["accordion"], None, final_entry=None)
    assert sel["gc"]["event_code"] == "D2EVGC20"
    assert "from_final_accordion" not in sel["gc"]


@pytest.mark.unit
def test_the_stages_own_gc_wins_when_both_exist():
    props = _props(last_stage_has_gc=True)
    stage = ua.find_stage(props, "stage_21")
    sel = ua.select_classifications(stage["accordion"], None, final_entry=stage["final_accordion"])
    assert sel["gc"]["event_code"] == "D2EVSTAGEGC"
    assert "from_final_accordion" not in sel["gc"]


@pytest.mark.unit
def test_no_final_accordion_is_not_an_error():
    props = _props(with_final=False)
    stage = ua.find_stage(props, "stage_21")
    assert stage["final_accordion"] is None
    sel = ua.select_classifications(stage["accordion"], None, final_entry=None)
    assert "gc" not in sel
