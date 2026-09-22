"""One rule for a campaign's page filenames: the builders and the driver must agree.

Chip W (2026-09-22, hosted task 113): before ``cycling_project/nightly/site_paths.py``
the builders derived a prefix from the campaign directory while the driver read
``campaign.json`` ``site.prefix`` and fell back to the Tour's ``""``.
"""

from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path

import pytest

from cycling_project.nightly import site_paths

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BUILD = PROJECT_ROOT / "netlify_site" / "build"


def _script_globals(name):
    sys.path.insert(0, str(BUILD))
    try:
        return runpy.run_path(str(BUILD / name), run_name="_for_tests")
    finally:
        sys.path.remove(str(BUILD))


def test_the_rule():
    assert site_paths.site_prefix("tour-de-france-2026") == ""
    assert site_paths.site_prefix("vuelta-2026") == "vuelta-"
    assert site_paths.site_prefix("cro-race-2026") == "cro-race-2026-"
    assert site_paths.site_prefix("cro-race-2026", {"is_stage_race": True}) == "cro-race-2026-"
    assert site_paths.site_prefix("trofeo-matteotti-2026", {"is_stage_race": False}) == ""
    assert site_paths.site_prefix("cro-race-2026", {"site": {"prefix": "cro-"}}) == "cro-"
    assert site_paths.site_prefix("cro-race-2026", {"site": {"prefix": ""}}) == ""
    assert site_paths.site_prefix("cro-race-2026", {"site": {"prefix": "a-"}}, {"site": {"prefix": "b-"}}) == "b-"
    assert site_paths.stage_page_name("cro-race-2026-", 1) == "cro-race-2026-stage01.html"
    assert site_paths.stages_index_name("") == "stages.html"
    assert site_paths.gc_tracker_name("vuelta-") == "vuelta-gc.html"
    assert site_paths.oneday_page_name("trofeo-matteotti-2026", {"slug": "trofeo-matteotti-2026", "year": 2026}) == "trofeo-matteotti-2026.html"
    assert site_paths.oneday_page_name("vuelta-2026", {"site": {"route_slug": "vuelta-a-espana"}}, year=2026) == "vuelta-a-espana-2026.html"
    assert site_paths.is_frame_path("_frame/home.html") and site_paths.is_frame_path("site-index.json")
    assert not site_paths.is_frame_path("stage05.html")


@pytest.mark.parametrize("dirname", sorted(p.name for p in (PROJECT_ROOT / "performance_eval").iterdir()
                                           if (p / "campaign.json").exists()))
def test_build_stage_page_and_build_site_index_agree_with_site_paths(dirname):
    """Every real campaign: the stage-page builder's prefix, the site index's prefix and the
    driver's are the same string, and the Tour/Vuelta keep their published names."""
    from cycling_project.nightly.driver import Campaign
    registry = json.loads((PROJECT_ROOT / "performance_eval" / dirname / "campaign.json").read_text())
    branding = _script_globals("build_stage_page.py")["resolve_campaign"](dirname, {})
    index = _script_globals("build_site_index.py")
    legacy = {c["dir"]: c for c in index["CAMPAIGNS"]}
    camp = index["load_campaign"](legacy[dirname]) if dirname in legacy else index["registry_campaign"](dirname)
    driver = Campaign.load(PROJECT_ROOT / "performance_eval" / dirname)
    assert branding["prefix"] == camp["prefix"] == driver.site_prefix
    if registry.get("is_stage_race", True):
        assert index["stage_asset"].__globals__  # imported fine
        assert driver.stage_page_name(3) == f"{camp['prefix']}stage03.html"
    if dirname == "tour-de-france-2026":
        assert camp["prefix"] == "" and driver.gc_page_name() == "gc.html"
    if dirname == "vuelta-2026":
        assert camp["prefix"] == "vuelta-" and driver.gc_page_name() == "vuelta-gc.html"
    if not registry.get("is_stage_race", True):
        assert camp["prefix"] == "" and driver.oneday_page_name() == f"{camp['slug']}-{camp['year']}.html"


def test_build_oneday_page_names_the_page_like_the_driver(tmp_path):
    from cycling_project.nightly.driver import Campaign
    d = tmp_path / "some-classic-2026"
    d.mkdir()
    (d / "campaign.json").write_text(json.dumps({"slug": "some-classic-2026", "year": 2026, "is_stage_race": False,
                                                 "name": "Some Classic"}))
    identity = _script_globals("build_oneday_page.py")["campaign_identity"](d, {"target": "one_day"})
    assert identity["page"] == Campaign.load(d).oneday_page_name() == "some-classic-2026.html"
