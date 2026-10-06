"""Planner timing under two cloud ticks a day (owner decision 2026-10-05).

The nightly fires at 12:45 Pacific (the original 19:45 UTC deployment) and again at 23:00
Pacific, because FirstCycling posts European start lists overnight European time: the 12:45 tick
is the evening before (no field yet), the 23:00 tick is race morning (field up, racing not begun).
These tests pin, for a European and an Asian race, what each tick plans — and that a unit the
other tick already previewed or settled (its boards / results overlaid back from the artifacts)
is not run twice.
"""
from __future__ import annotations

import datetime as dt
import json
from zoneinfo import ZoneInfo

from cycling_project.nightly import driver as drv

PACIFIC = ZoneInfo("America/Los_Angeles")


def _tick(day: str, hhmm: str, race_tz: str) -> str:
    """The race-local wall clock (naive ISO, what ``--local-now`` takes) at a Pacific tick."""
    h, m = (int(x) for x in hhmm.split(":"))
    pacific = dt.datetime.combine(dt.date.fromisoformat(day), dt.time(h, m), tzinfo=PACIFIC)
    return pacific.astimezone(ZoneInfo(race_tz)).replace(tzinfo=None).isoformat(timespec="minutes")


def early(day, tz):   # the 12:45 PT tick (19:45 UTC in PDT)
    return _tick(day, "12:45", tz)


def late(day, tz):    # the 23:00 PT tick
    return _tick(day, "23:00", tz)


def _campaign(tmp_path, slug, tz, stages=None, date=None):
    d = tmp_path / slug
    d.mkdir()
    cfg = {"slug": slug, "name": slug, "fc_race_id": "900", "year": 2026, "category": "pro",
           "timezone": tz, "is_stage_race": stages is not None}
    if stages is not None:
        cfg["stages"] = [{"number": i + 1, "date": s} for i, s in enumerate(stages)]
    else:
        cfg["date"] = date
    (d / "campaign.json").write_text(json.dumps(cfg))
    return d


def _plan(camp, tmp_path, capsys, local_now):
    assert drv.main(["plan", "--campaign", str(camp), "--dry-run", "--store-root", str(tmp_path / "store"),
                     "--local-now", local_now, "--all-tiers"]) == 0
    return json.loads(capsys.readouterr().out)


def _boards(camp, unit):
    p = camp / "predictions" / unit
    p.mkdir(parents=True, exist_ok=True)
    (p / "bunch.json").write_text("{}")          # what a preview's upload overlays back


def _results(camp, unit):
    p = camp / "results" / unit
    p.mkdir(parents=True, exist_ok=True)
    (p / "results.csv").write_text("rider,place\n")


def test_tick_clock_conversion():
    assert early("2026-10-05", "Europe/Rome") == "2026-10-05T21:45"
    assert late("2026-10-05", "Europe/Rome") == "2026-10-06T08:00"
    assert late("2026-10-12", "Asia/Shanghai") == "2026-10-13T14:00"
    assert early("2026-10-12", "Asia/Shanghai") == "2026-10-13T03:45"
    # Europe leaves summer time on Oct 25, the US on Nov 1: the late tick is still before 09:00
    assert late("2026-10-27", "Europe/Rome") == "2026-10-28T07:00"
    assert late("2026-11-03", "Europe/Rome") == "2026-11-04T08:00"


# ---------------------------------------------------------------------------
# Europe — one-day (Tre Valli Varesine, 2026-10-06)
# ---------------------------------------------------------------------------

def test_europe_one_day_late_tick_previews_race_morning(tmp_path, capsys):
    camp = _campaign(tmp_path, "tre-valli-2026", "Europe/Rome", date="2026-10-06")
    # 12:45 PT the day before = 21:45 CEST: preview due (the field may not be up yet)
    assert _plan(camp, tmp_path, capsys, early("2026-10-05", "Europe/Rome"))["preview"] == ["race"]
    # 23:00 PT = 08:00 CEST race day, racing not begun: still preview-due, not "too late"
    plan = _plan(camp, tmp_path, capsys, late("2026-10-05", "Europe/Rome"))
    assert plan["preview"] == ["race"] and plan["settle"] == [], plan


def test_europe_one_day_previewed_at_1245_is_skipped_at_2300(tmp_path, capsys):
    camp = _campaign(tmp_path, "tre-valli-2026", "Europe/Rome", date="2026-10-06")
    _boards(camp, "race")
    plan = _plan(camp, tmp_path, capsys, late("2026-10-05", "Europe/Rome"))
    assert plan["preview"] == [] and plan["settle"] == [], plan


def test_europe_one_day_settles_once(tmp_path, capsys):
    camp = _campaign(tmp_path, "tre-valli-2026", "Europe/Rome", date="2026-10-06")
    _boards(camp, "race")
    # race evening 21:45 CEST: a one-day race keeps the "settle the evening after" contract
    assert _plan(camp, tmp_path, capsys, early("2026-10-06", "Europe/Rome"))["settle"] == []
    # 23:00 PT = next local morning: settle due
    assert _plan(camp, tmp_path, capsys, late("2026-10-06", "Europe/Rome"))["settle"] == ["race"]
    # settled by that tick → the following 12:45 tick does nothing
    _results(camp, "race")
    plan = _plan(camp, tmp_path, capsys, early("2026-10-07", "Europe/Rome"))
    assert plan["settle"] == [] and plan["preview"] == [], plan


# ---------------------------------------------------------------------------
# Europe — stage race
# ---------------------------------------------------------------------------

STAGES_EU = ["2026-10-06", "2026-10-07", "2026-10-08"]


def test_europe_stage_race_both_ticks(tmp_path, capsys):
    camp = _campaign(tmp_path, "eu-stage-2026", "Europe/Rome", stages=STAGES_EU)
    tz = "Europe/Rome"
    assert _plan(camp, tmp_path, capsys, early("2026-10-05", tz))["preview"] == ["stage_01"]
    plan = _plan(camp, tmp_path, capsys, late("2026-10-05", tz))       # 08:00 stage-1 morning
    assert plan["preview"] == ["stage_01"] and plan["settle"] == [], plan

    # the 12:45 tick of stage-1 day settles it and previews stage 2 …
    _boards(camp, "stage_01")
    plan = _plan(camp, tmp_path, capsys, early("2026-10-06", tz))
    assert plan["settle"] == ["stage_01"] and plan["preview"] == ["stage_02"], plan
    _results(camp, "stage_01")
    _boards(camp, "stage_02")
    # … so the 23:00 tick (08:00 stage-2 morning) has nothing to do
    plan = _plan(camp, tmp_path, capsys, late("2026-10-06", tz))
    assert plan["settle"] == [] and plan["preview"] == [], plan


def test_europe_stage_race_late_tick_catches_what_the_early_one_missed(tmp_path, capsys):
    """Stage 1 results not out at 21:45 and stage 2's field not up: 23:00 does both, in order."""
    camp = _campaign(tmp_path, "eu-stage-2026", "Europe/Rome", stages=STAGES_EU)
    _boards(camp, "stage_01")
    plan = _plan(camp, tmp_path, capsys, late("2026-10-06", "Europe/Rome"))
    assert plan["settle"] == ["stage_01"] and plan["preview"] == ["stage_02"], plan


# ---------------------------------------------------------------------------
# Asia — Tour of Guangxi (from 2026-10-13, UTC+8)
# ---------------------------------------------------------------------------

STAGES_ASIA = ["2026-10-13", "2026-10-14", "2026-10-15"]


def test_asia_late_tick_is_mid_stage_and_plans_nothing(tmp_path, capsys):
    camp = _campaign(tmp_path, "guangxi-2026", "Asia/Shanghai", stages=STAGES_ASIA)
    tz = "Asia/Shanghai"
    # 12:45 PT Oct 12 = 03:45 stage-1 morning in Shanghai: the preview belongs to this tick
    assert _plan(camp, tmp_path, capsys, early("2026-10-12", tz))["preview"] == ["stage_01"]
    # 23:00 PT Oct 12 = 14:00 Oct 13: stage 1 is on the road — no stage-1 preview, no stage-2
    # preview ahead of stage 1's result, nothing to settle
    plan = _plan(camp, tmp_path, capsys, late("2026-10-12", tz))
    assert plan["preview"] == [] and plan["settle"] == [], plan
    s2 = next(u for u in plan["units"] if u["unit"] == "stage_02")
    assert "prior_stage_on_road" in s2["flags"]


def test_asia_settle_and_preview_stay_on_the_early_tick(tmp_path, capsys):
    camp = _campaign(tmp_path, "guangxi-2026", "Asia/Shanghai", stages=STAGES_ASIA)
    tz = "Asia/Shanghai"
    _boards(camp, "stage_01")
    plan = _plan(camp, tmp_path, capsys, early("2026-10-13", tz))      # 03:45 Oct 14
    assert plan["settle"] == ["stage_01"] and plan["preview"] == ["stage_02"], plan
    _results(camp, "stage_01")
    _boards(camp, "stage_02")
    plan = _plan(camp, tmp_path, capsys, late("2026-10-13", tz))       # 14:00 Oct 14, stage 2 racing
    assert plan["settle"] == [] and plan["preview"] == [], plan


def test_asia_unsettled_stage_is_settled_by_the_late_tick_without_previewing_ahead(tmp_path, capsys):
    """The UCI had nothing at the 12:45 tick: at 23:00 the stage settles (late), but the next
    stage — which is racing — and the one after are not previewed."""
    camp = _campaign(tmp_path, "guangxi-2026", "Asia/Shanghai", stages=STAGES_ASIA)
    _boards(camp, "stage_01")
    _boards(camp, "stage_02")
    plan = _plan(camp, tmp_path, capsys, late("2026-10-13", "Asia/Shanghai"))
    assert plan["settle"] == ["stage_01"] and plan["preview"] == [], plan
