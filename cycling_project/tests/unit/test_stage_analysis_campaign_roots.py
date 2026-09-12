"""build_stage_analysis roots must follow the config's own campaign.

Before 2026-09-12 PREDICTIONS_ROOT and RESULTS_ROOT were hardcoded to
`performance_eval/tour-de-france-2026`, so building the "If the break goes"
block for any other campaign silently excluded the TOUR's GC top-N and
labelled riders with their Tour positions. It was caught on Vuelta 2026
stage 20, the first Vuelta stage to use the analysis builder: the break pool
came back holding the race leader, and Carapaz was tagged "GC #8" (his Tour
placing) while sitting 4th on the Vuelta.
"""

import importlib.util
import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = PROJECT_ROOT / "netlify_site" / "build" / "build_stage_analysis.py"


def load_module():
    spec = importlib.util.spec_from_file_location("build_stage_analysis", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.unit
def test_roots_default_to_the_tour_campaign():
    """A bare invocation keeps working for the Tour, which has no explicit root."""
    mod = load_module()
    assert mod.PREDICTIONS_ROOT.parent.name == "tour-de-france-2026"
    assert mod.RESULTS_ROOT.parent.name == "tour-de-france-2026"


@pytest.mark.unit
def test_roots_follow_the_config_campaign(tmp_path):
    """A config under <campaign>/predictions/<unit>/ repoints both roots."""
    mod = load_module()
    campaign = tmp_path / "performance_eval" / "vuelta-2026"
    cfg = campaign / "predictions" / "stage_20" / "scenarios.json"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(json.dumps({"stage": 20, "scenarios": {}}))

    returned = mod.set_campaign_roots(cfg)

    assert returned == campaign
    assert mod.PREDICTIONS_ROOT == campaign / "predictions"
    assert mod.RESULTS_ROOT == campaign / "results"
    assert "tour-de-france-2026" not in str(mod.RESULTS_ROOT)


@pytest.mark.unit
def test_standings_pool_reads_the_configured_campaign(tmp_path, monkeypatch):
    """standings_gc_pool must find gc.csv under the campaign it was pointed at.

    The regression: with the roots stuck on the Tour it happily returned the
    Tour's pool instead of raising, so the caller never learned it had the
    wrong race.
    """
    mod = load_module()
    campaign = tmp_path / "performance_eval" / "vuelta-2026"
    cfg = campaign / "predictions" / "stage_20" / "scenarios.json"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(json.dumps({"stage": 20, "scenarios": {}}))
    gc = campaign / "results" / "stage_19" / "gc.csv"
    gc.parent.mkdir(parents=True)
    gc.write_text(
        "place,name,rider_id,team,team_id,gap,dob\n"
        "1,Leader One,1527,Team A,1,0,1995\n"
        "2,Chaser Two,18655,Team B,2,97.0,1989\n"
        "3,Third Man,23097,Team C,3,181.0,1993\n"
    )
    mod.set_campaign_roots(cfg)
    # names are never the join key in production; here the fc->internal lookup
    # has no database, so the normalised-name fallback is what resolves rows.
    monkeypatch.setattr(mod, "fc_to_internal_ids", lambda ids: {})

    field = [
        {"rider_name": "Leader One", "rider_id": 11},
        {"rider_name": "Chaser Two", "rider_id": 22},
        {"rider_name": "Third Man", "rider_id": 33},
    ]
    ids, rank, stage = mod.standings_gc_pool(20, 2, field)

    assert stage == 19
    assert ids == frozenset({11, 22})       # top 2 excluded
    assert 33 not in ids                    # third man stays in the pool
    assert rank == {11: 1, 22: 2, 33: 3}


@pytest.mark.unit
def test_standings_pool_raises_when_the_campaign_has_no_archive(tmp_path):
    """No gc.csv under this campaign is an error, never a fallback to another."""
    mod = load_module()
    campaign = tmp_path / "performance_eval" / "empty-2026"
    cfg = campaign / "predictions" / "stage_20" / "scenarios.json"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(json.dumps({"stage": 20, "scenarios": {}}))
    mod.set_campaign_roots(cfg)

    with pytest.raises(SystemExit):
        mod.standings_gc_pool(20, 10, [])
