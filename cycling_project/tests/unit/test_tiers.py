"""The automation scope rule: which campaigns the unattended nightly covers.

Owner decision, 2026-09-22 (chip Y): WorldTour and .Pro.  A `.1` race stays
registered, bundled and runnable by hand; it is due only when its campaign.json
opts in, or when the Mac widens the tier set for one invocation.

One rule, one place: ``cycling_project/nightly/tiers.py``.  These tests pin the
rule itself; ``test_nightly_driver.py`` and ``test_horizon.py`` pin that the
driver and the horizon capture agree with it.
"""

from __future__ import annotations

import datetime
import pathlib

import pytest

from cycling_project.nightly import registry, tiers

pytestmark = pytest.mark.unit


def cfg(**kw):
    base = {"slug": "race-2026", "name": "Race", "category": "wt"}
    base.update(kw)
    return base


# ---------------------------------------------------------------------------
# the tiers themselves
# ---------------------------------------------------------------------------

def test_the_default_coverage_is_worldtour_and_pro():
    assert tiers.AUTOMATION_TIERS == ("wt", "pro")
    assert tiers.ATTENDED_TIERS == ("d1",)


def test_the_spellings_are_the_registrys_own():
    """`wt` / `pro` / `d1` are what registry.CATEGORIES writes into campaign.json."""
    assert set(tiers.KNOWN_TIERS) == set(registry.CATEGORIES)


@pytest.mark.parametrize("category, automated", [("wt", True), ("pro", True), ("d1", False)])
def test_category_decides(category, automated):
    assert tiers.is_automated(cfg(category=category)) is automated


def test_the_spelling_is_forgiving_but_the_rule_is_not():
    assert tiers.is_automated(cfg(category=" WT ")) is True
    assert tiers.is_automated(cfg(category="D1")) is False
    assert tiers.is_automated(cfg(category="cx")) is False


# ---------------------------------------------------------------------------
# the per-campaign escape hatch
# ---------------------------------------------------------------------------

def test_a_d1_race_can_be_opted_in():
    assert tiers.is_automated(cfg(category="d1", automation="on")) is True


def test_a_worldtour_race_can_be_opted_out():
    assert tiers.is_automated(cfg(category="wt", automation="off")) is False
    assert tiers.skip_reason(cfg(category="wt", automation="off")) == (
        "not_automated: automation off in campaign.json")


def test_an_unreadable_override_is_ignored_not_guessed():
    """A typo must not silently switch a race on or off."""
    assert tiers.is_automated(cfg(category="d1", automation="maybe")) is False
    assert tiers.is_automated(cfg(category="wt", automation="maybe")) is True


def test_a_boolean_override_works_too():
    assert tiers.is_automated(cfg(category="d1", automation=True)) is True
    assert tiers.is_automated(cfg(category="wt", automation=False)) is False


# ---------------------------------------------------------------------------
# a missing category
# ---------------------------------------------------------------------------

def test_a_campaign_with_no_category_is_not_automated():
    """The registry always writes one, so its absence means a human should look."""
    for missing in ({}, {"category": None}, {"category": ""}):
        assert tiers.is_automated(missing) is False
        assert tiers.skip_reason(missing) == "not_automated: campaign.json has no category"


def test_the_rule_logs_nothing_on_the_plans_json_channel(capsys):
    """The shared logger writes to stdout, which is `nightly plan`'s JSON channel."""
    tiers.is_automated({})
    tiers.skip_reason({"category": "d1"})
    assert capsys.readouterr().out == ""


# ---------------------------------------------------------------------------
# widening for an attended Mac run
# ---------------------------------------------------------------------------

def test_all_tiers_covers_everything():
    assert tiers.resolve_tiers(all_tiers=True) == tiers.KNOWN_TIERS
    assert tiers.is_automated(cfg(category="d1"), tiers=tiers.KNOWN_TIERS) is True


def test_include_tier_adds_without_dropping_the_default():
    assert tiers.resolve_tiers(include=["d1"]) == ("wt", "pro", "d1")
    assert tiers.resolve_tiers(include=["WT"]) == ("wt", "pro")       # already covered, no duplicate
    assert tiers.resolve_tiers(include=[]) == ("wt", "pro")
    assert tiers.resolve_tiers() == ("wt", "pro")


def test_widening_never_overrides_an_explicit_off():
    """`--all-tiers` widens the tier set; it does not overrule the owner's own flag."""
    assert tiers.is_automated(cfg(category="wt", automation="off"), tiers=tiers.KNOWN_TIERS) is False


def test_skip_reason_is_none_when_the_campaign_is_covered():
    assert tiers.skip_reason(cfg(category="pro")) is None
    assert tiers.skip_reason(cfg(category="d1"), tiers=tiers.KNOWN_TIERS) is None
    assert tiers.skip_reason(cfg(category="d1")) == "not_automated: category d1"


# ---------------------------------------------------------------------------
# shapes
# ---------------------------------------------------------------------------

def test_it_reads_a_campaign_object_as_happily_as_a_dict():
    class Camp:
        cfg = {"category": "d1"}

    assert tiers.is_automated(Camp()) is False
    assert tiers.category_of(Camp()) == "d1"
    assert tiers.is_automated(None) is False


# ---------------------------------------------------------------------------
# the registry row
# ---------------------------------------------------------------------------

def test_the_registry_row_mirrors_the_effective_flag():
    row = registry._campaign_row({
        "slug": "x-2026", "fc_race_id": "1", "year": 2026, "name": "X", "category": "d1",
    })
    assert row["automated"] is False
    on = registry._campaign_row({
        "slug": "x-2026", "fc_race_id": "1", "year": 2026, "name": "X",
        "category": "d1", "automation": "on",
    })
    assert on["automated"] is True


# ---------------------------------------------------------------------------
# the public hub: a race nobody covers must not read as "in progress"
# ---------------------------------------------------------------------------

def _index_globals():
    import runpy
    import sys

    build = pathlib.Path(__file__).resolve().parents[3] / "netlify_site" / "build"
    sys.path.insert(0, str(build))
    try:
        return runpy.run_path(str(build / "build_site_index.py"), run_name="_for_tests")
    finally:
        sys.path.remove(str(build))


def _camp(**kw):
    base = {"dir": "nowhere-2026", "slug": "nowhere", "year": 2026, "name": "Nowhere 2026",
            "short_name": "Nowhere 2026", "type": "stage_race", "prefix": "nowhere-2026-",
            "n_stages": 2, "start_date": "2026-09-20", "end_date": "2026-09-22",
            "blurb": "", "extra_pages": {}}
    base.update(kw)
    return base


def test_an_uncovered_race_with_no_pages_is_not_in_progress():
    index = _index_globals()
    today = datetime.date(2026, 9, 21)
    entry = index["build_campaign"](_camp(automated=False), today)
    assert entry["status"] == "not_covered" and entry["automated"] is False
    # the same race, covered by the nightly: the old status stands, silence is a real gap
    assert index["build_campaign"](_camp(automated=True), today)["status"] == "in_progress"


def test_the_frame_knows_the_new_status():
    """A KeyError in the frame would take down every race hub."""
    build = pathlib.Path(__file__).resolve().parents[3] / "netlify_site" / "build"
    src = (build / "build_site_frame.py").read_text()
    assert '"not_covered": "not covered"' in src
    assert '}.get(race["status"], "Not covered")' in src


# ---------------------------------------------------------------------------
# the hosted row tolerates its migration not being pushed
# ---------------------------------------------------------------------------

def test_sync_campaign_drops_the_automated_column_when_the_schema_lacks_it():
    """Migration 0008 is not pushed yet; a registry sync must still work (CLAUDE.md)."""
    from cycling_project.nightly import store as store_mod

    sent = []

    class FakeSupabase(store_mod.SupabaseStore):
        def __init__(self):
            self.role = "operator"

        def _require_operator(self, what):
            return None

        def _select(self, table, params):
            return []

        def _insert(self, table, rows, **kw):
            sent.append(dict(rows[0]))
            if "automated" in rows[0]:
                raise store_mod.StoreError(
                    "insert campaigns: HTTP 400 Could not find the 'automated' column of "
                    "'campaigns' in the schema cache", 400, "PGRST204")
            return [dict(rows[0])]

    row = FakeSupabase().sync_campaign({"campaign_slug": "x-2026", "fc_race_id": "1",
                                        "year": 2026, "name": "X", "automated": False})
    assert len(sent) == 2 and "automated" in sent[0] and "automated" not in sent[1]
    assert "automated" not in row


def test_sync_campaign_never_swallows_an_unrelated_failure():
    from cycling_project.nightly import store as store_mod

    class FakeSupabase(store_mod.SupabaseStore):
        def __init__(self):
            self.role = "operator"

        def _require_operator(self, what):
            return None

        def _select(self, table, params):
            return []

        def _insert(self, table, rows, **kw):
            raise store_mod.StoreError("insert campaigns: HTTP 500 boom", 500, None)

    with pytest.raises(store_mod.StoreError):
        FakeSupabase().sync_campaign({"campaign_slug": "x-2026", "automated": True})
