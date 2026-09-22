"""Unit tests for the Mac-side horizon capture (``cycling_project.nightly.horizon``).

Everything here runs against ``MockWebClient`` and the committed HTML
fixtures — a real FirstCycling scrape needs a visible Chrome window on the
owner's Mac and is rate-limited, so no test ever touches the network. The
store is always a ``FakeStore`` (CLAUDE.md: ``--store auto`` writes to the
HOSTED ledger).
"""

import datetime as dt
import json
import os
import time
from pathlib import Path

import pytest

from cycling_project.nightly import horizon, oneday, tiers
from cycling_project.nightly.store import FakeStore
from cycling_project.tests.utils.mock_responses import MockResponse, MockWebClient

pytestmark = pytest.mark.unit

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
STAGE_PAGE = FIXTURES / "nightly" / "firstcycling_stage_page.html"
STARTLIST_PAGE = FIXTURES / "nightly" / "firstcycling_startlist.html"
RACE_PAGE = FIXTURES / "webscrape_tools" / "test_html" / "race_detail.html"

FC_RACE_ID = "900"
YEAR = 2026
TODAY = dt.date(2026, 9, 16)


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

def stage_page_html(stage: int, date_text: str, *, distance: str = "142.4",
                    start: str = "Chieti", finish: str = "Pescara",
                    header_extra: str = "") -> str:
    """The committed stage-page fixture, re-pointed at another stage.

    The Information ``div.sideBox`` markup is the real one (that is the whole
    point of using the fixture); only the numbers and the header line change.
    """
    html = STAGE_PAGE.read_text()
    html = html.replace("15th stage | 110.2 km", f"{stage}th stage | {distance} km")
    html = html.replace("Palma del Rio", start).replace("Cordoba", finish)
    header = (f'<div id="raceSub">1.1, {stage}th stage{header_extra}, {date_text}, Italy</div>')
    return html.replace("<body>", f"<body>{header}")


def write_campaign(root: Path, slug: str, cfg: dict) -> Path:
    d = root / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "campaign.json").write_text(json.dumps(cfg, indent=1))
    return d


def stage_race_config(slug="giro-test-2026", *, start=dt.date(2026, 9, 17), stages=3,
                      provisional=True, fc_race_id=FC_RACE_ID, category="pro") -> dict:
    return {
        # ".Pro" so the campaign is inside the nightly's default coverage (chip Y,
        # 2026-09-22); the tier rule has its own tests further down.
        "slug": slug, "name": "Giro Test", "fc_race_id": fc_race_id, "year": YEAR,
        "category": category, "is_stage_race": True,
        "start_date": str(start), "end_date": str(start + dt.timedelta(days=stages - 1)),
        "stages": [{"number": n, "date": str(start + dt.timedelta(days=n - 1)),
                    "towns": None, "distance_km": None, "kind": None}
                   for n in range(1, stages + 1)],
        "timezone": "Europe/Rome", "kambi_event_ids": {}, "void_stages": [],
        "stages_provisional": provisional,
    }


def one_day_config(slug="gp-test-2026", *, date=dt.date(2026, 9, 17)) -> dict:
    return {
        "slug": slug, "name": "GP Test", "fc_race_id": "901", "year": YEAR,
        "category": "pro", "is_stage_race": False,
        "start_date": str(date), "end_date": str(date),
        "stages": [{"number": None, "date": str(date), "towns": None,
                    "distance_km": None, "kind": "one_day"}],
        "timezone": "Europe/Brussels", "kambi_event_ids": {}, "void_stages": [],
    }


class Client(MockWebClient):
    """MockWebClient that records every URL and serves the FirstCycling shapes."""

    def __init__(self, race_id=FC_RACE_ID, year=YEAR, *, stages=3, one_day=False):
        super().__init__(horizon.BASE_URL)
        base = f"{horizon.BASE_URL}/race.php?r={race_id}&y={year}"
        self.add_response(f"{base}&k=8", MockResponse.from_html_file(STARTLIST_PAGE))
        if one_day:
            self.add_response(base, MockResponse(text=stage_page_html(
                1, "17th September 2026", start="Namur", finish="Namur")))
        else:
            self.add_response(base, MockResponse.from_html_file(RACE_PAGE))
            for n in range(1, stages + 1):
                self.add_response(f"{base}&e={n:02d}", MockResponse(text=stage_page_html(
                    n, f"{16 + n}th September 2026", distance=f"1{40 + n}.4")))


@pytest.fixture
def perf(tmp_path):
    (tmp_path / "performance_eval").mkdir()
    return tmp_path / "performance_eval"


@pytest.fixture
def store(tmp_path):
    return FakeStore(tmp_path / "fakestore", role="operator")


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "cache.db"


def run(perf, store, client, db_path, **kw):
    """``run_horizon`` with the mock client wired into both fetch paths."""
    import cycling_project.webscrape_tools.get_startlist as gs

    original = gs.WebClient
    gs.WebClient = lambda base_url: client
    try:
        return horizon.run_horizon(
            perf_eval=perf, store=store, db_path=db_path, today=kw.pop("today", TODAY),
            client_factory=lambda: client, quiet=True, **kw)
    finally:
        gs.WebClient = original


# ---------------------------------------------------------------------------
# selection
# ---------------------------------------------------------------------------

def test_select_units_only_inside_the_horizon(perf, store):
    write_campaign(perf, "soon-2026", stage_race_config("soon-2026", start=dt.date(2026, 9, 17)))
    write_campaign(perf, "later-2026", stage_race_config("later-2026", start=dt.date(2026, 9, 30)))
    due = horizon.select_units(perf, store, days=3, today=TODAY)
    assert [d.slug for d in due] == ["soon-2026"]
    assert due[0].units == ["stage_01", "stage_02", "stage_03"]


def test_select_units_takes_the_next_stages_of_a_race_in_progress(perf, store):
    cfg = stage_race_config("running-2026", start=dt.date(2026, 9, 15), stages=5)
    d = write_campaign(perf, "running-2026", cfg)
    (d / "results" / "stage_01").mkdir(parents=True)
    (d / "results" / "stage_01" / "results.csv").write_text("place,name\n1,x\n")
    due = horizon.select_units(perf, store, days=2, today=TODAY)
    assert due[0].units == ["stage_03", "stage_04"]


def test_select_units_skips_a_unit_that_already_has_boards(perf, store):
    d = write_campaign(perf, "soon-2026", stage_race_config("soon-2026", stages=1))
    pred = d / "predictions" / "stage_01"
    pred.mkdir(parents=True)
    (pred / "bunch.json").write_text('{"riders": []}')
    assert horizon.select_units(perf, store, days=3, today=TODAY) == []


def test_select_units_honours_the_campaign_filter(perf, store):
    write_campaign(perf, "soon-2026", stage_race_config("soon-2026"))
    write_campaign(perf, "other-2026", stage_race_config("other-2026", fc_race_id="902"))
    due = horizon.select_units(perf, store, days=3, today=TODAY, only=["other-2026"])
    assert [d.slug for d in due] == ["other-2026"]


# ---------------------------------------------------------------------------
# capture
# ---------------------------------------------------------------------------

def test_capture_writes_startlist_stage_page_and_route(perf, store, db_path):
    d = write_campaign(perf, "giro-test-2026", stage_race_config())
    summary = run(perf, store, Client(), db_path, days=3)

    assert summary["campaigns"][0]["status"] == "ok"
    handover = d / "predictions" / "stage_01" / "startlist.json"
    assert handover.exists()
    teams = oneday.load_startlist_file(handover)
    assert sum(len(t.riders) for t in teams) == 24
    assert all(r.rider_id for t in teams for r in t.riders)

    pages = list((d / "results" / "stage_01").glob("stage_page_*.html"))
    assert len(pages) == 1
    assert "sideBox" in pages[0].read_text()
    index = json.loads((d / "results" / "stage_01" / "horizon_raw.json").read_text())
    assert list(index["pages"])[0].startswith("stage_page_")
    assert index["pages"][pages[0].name]["source_url"].endswith("&e=01")

    route = json.loads((d / "predictions" / "stage_01" / "route.json").read_text())
    assert route["distance_km"] == 141.4
    assert route["start"] == "Chieti"
    assert route["finish"] == "Pescara"


def test_startlist_lands_in_the_cache_for_the_serving_path(perf, store, db_path):
    import sqlite3

    write_campaign(perf, "giro-test-2026", stage_race_config())
    run(perf, store, Client(), db_path, days=3)
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "select count(*) from cached_start_lists where fc_race_id = ?", (FC_RACE_ID,)
        ).fetchone()
    assert rows[0] == 24


def test_one_day_race_uses_the_race_page_as_its_stage_page(perf, store, db_path):
    d = write_campaign(perf, "gp-test-2026", one_day_config())
    summary = run(perf, store, Client("901", one_day=True), db_path, days=3)
    assert summary["campaigns"][0]["units"] == ["race"]
    assert (d / "predictions" / "race" / "startlist.json").exists()
    assert list((d / "results" / "race").glob("stage_page_*.html"))
    route = json.loads((d / "predictions" / "race" / "route.json").read_text())
    assert route["start"] == "Namur"


# ---------------------------------------------------------------------------
# campaign.json stages
# ---------------------------------------------------------------------------

def test_stage_metadata_is_filled_from_the_captured_pages(perf, store, db_path):
    d = write_campaign(perf, "giro-test-2026", stage_race_config())
    run(perf, store, Client(), db_path, days=3)
    cfg = json.loads((d / "campaign.json").read_text())
    first = cfg["stages"][0]
    assert first["towns"] == "Chieti → Pescara"
    assert first["distance_km"] == 141.4
    assert first["date"] == "2026-09-17"


def test_provisional_stays_until_every_stage_is_known(perf, store, db_path):
    d = write_campaign(perf, "giro-test-2026", stage_race_config())
    run(perf, store, Client(), db_path, days=1, backfill=False)
    cfg = json.loads((d / "campaign.json").read_text())
    assert cfg["stages_provisional"] is True
    assert cfg["stages"][1]["towns"] is None


def test_provisional_clears_once_the_whole_schedule_is_parsed(perf, store, db_path):
    d = write_campaign(perf, "giro-test-2026", stage_race_config())
    run(perf, store, Client(), db_path, days=3, max_backfill=5)
    cfg = json.loads((d / "campaign.json").read_text())
    assert cfg["stages_provisional"] is False
    assert all(s["towns"] and s["distance_km"] for s in cfg["stages"])


def test_a_provisional_calendar_stage_the_race_does_not_have_is_dropped(perf, store, db_path):
    # The calendar invents one stage per day; the race page lists three.
    d = write_campaign(perf, "giro-test-2026",
                       stage_race_config(stages=4, start=dt.date(2026, 9, 17)))
    run(perf, store, Client(stages=3), db_path, days=3, max_backfill=5)
    cfg = json.loads((d / "campaign.json").read_text())
    assert [s["number"] for s in cfg["stages"]] == [1, 2, 3]


def test_a_declared_stage_list_is_never_grown_or_trimmed(perf, store, db_path):
    cfg = stage_race_config(stages=2, provisional=False)
    d = write_campaign(perf, "giro-test-2026", cfg)
    run(perf, store, Client(stages=3), db_path, days=3, max_backfill=5)
    after = json.loads((d / "campaign.json").read_text())
    assert [s["number"] for s in after["stages"]] == [1, 2]
    assert "stages_provisional" not in after or after["stages_provisional"] is False


def test_kind_is_only_set_from_words_on_the_page(perf, store, db_path):
    d = write_campaign(perf, "giro-test-2026", stage_race_config(stages=1))
    client = Client(stages=1)
    client.add_response(f"{horizon.BASE_URL}/race.php?r={FC_RACE_ID}&y={YEAR}&e=01",
                        MockResponse(text=stage_page_html(1, "17th September 2026",
                                                          header_extra=" (ITT)")))
    run(perf, store, client, db_path, days=3, backfill=False)
    cfg = json.loads((d / "campaign.json").read_text())
    assert cfg["stages"][0]["kind"] == "itt"
    assert cfg["stages"][0]["fc_profile_code"] == "GT2"


# ---------------------------------------------------------------------------
# the ledger and the artifacts
# ---------------------------------------------------------------------------

def test_artifacts_use_the_drivers_key_convention(perf, store, db_path):
    write_campaign(perf, "giro-test-2026", stage_race_config())
    summary = run(perf, store, Client(), db_path, days=3)
    keys = summary["campaigns"][0]["uploaded"]
    run_id = summary["campaigns"][0]["run_id"]
    assert f"{run_id}/giro-test-2026/predictions/stage_01/startlist.json" in keys
    assert f"{run_id}/giro-test-2026/predictions/stage_01/route.json" in keys
    assert f"{run_id}/giro-test-2026/campaign.json" in keys
    assert any(k.endswith(".html") for k in keys)
    # every key drops to performance_eval/<campaign>/<rel> under overlay_artifacts
    for key in keys:
        assert key.split("/")[1] == "giro-test-2026"


def test_the_run_and_its_steps_reach_the_ledger(perf, store, db_path):
    write_campaign(perf, "giro-test-2026", stage_race_config())
    summary = run(perf, store, Client(), db_path, days=3)
    run_id = summary["campaigns"][0]["run_id"]
    row = store.get_run(run_id)
    assert row["phase"] == "horizon"
    assert row["host"] == "mac"
    steps = {s["step"]: s["state"] for s in store.run_steps(run_id)}
    assert steps["startlist"] == "ok"
    assert steps["unit:stage_01"] == "ok"
    assert steps["stages"] == "ok"
    assert steps["upload"] == "ok"
    assert steps["finish"] == "ok"


def test_registry_rows_are_synced_when_the_stage_list_changes(perf, store, db_path):
    write_campaign(perf, "giro-test-2026", stage_race_config())
    run(perf, store, Client(), db_path, days=3)
    assert [c["campaign_slug"] for c in store.campaigns()] == ["giro-test-2026"]
    units = {s["unit"] for s in store.stages("giro-test-2026")}
    assert "stage_01" in units


# ---------------------------------------------------------------------------
# idempotence, dry run, failure
# ---------------------------------------------------------------------------

def test_a_second_pass_makes_no_requests(perf, store, db_path):
    write_campaign(perf, "giro-test-2026", stage_race_config())
    first = Client()
    run(perf, store, first, db_path, days=3)
    assert first.requests

    second = Client()
    summary = run(perf, store, second, db_path, days=3)
    assert second.requests == []
    assert summary["requests_made"] == 0
    assert summary["campaigns"][0]["status"] == "ok"


def test_a_stale_capture_is_refreshed(perf, store, db_path):
    d = write_campaign(perf, "giro-test-2026", stage_race_config())
    run(perf, store, Client(), db_path, days=3)
    old = time.time() - 40 * 3600
    for p in list(d.rglob("startlist.json")) + list(d.rglob("stage_page_*.html")) \
            + list(d.rglob("race_page_*.html")):
        os.utime(p, (old, old))
    for p in d.rglob("startlist.json"):
        doc = json.loads(p.read_text())
        doc["captured_at"] = "2026-09-10T06:00:00+00:00"
        p.write_text(json.dumps(doc))
        os.utime(p, (old, old))
    again = Client()
    run(perf, store, again, db_path, days=3)
    assert any("&e=01" in r["url"] for r in again.requests)


def test_dry_run_fetches_nothing_and_writes_nothing(perf, store, db_path):
    d = write_campaign(perf, "giro-test-2026", stage_race_config())
    client = Client()
    summary = run(perf, store, client, db_path, days=3, dry_run=True)
    assert client.requests == []
    assert not (d / "predictions").exists()
    assert not (d / "results").exists()
    assert summary["campaigns"][0]["status"] == "ok"


def test_a_failure_files_an_operator_task_and_the_command_still_exits_zero(perf, store, db_path,
                                                                          monkeypatch):
    d_broken = write_campaign(perf, "broken-2026",
                              stage_race_config("broken-2026", fc_race_id="999"))
    d_ok = write_campaign(perf, "giro-test-2026", stage_race_config())

    client = Client()          # serves race 900; race 999 404s
    import cycling_project.webscrape_tools.get_startlist as gs
    monkeypatch.setattr(gs, "WebClient", lambda base_url: client)
    monkeypatch.setattr(horizon, "WebClient", lambda base_url: client)
    monkeypatch.setattr(horizon, "resolve_store", lambda *a, **k: store)

    code = horizon.main(["--store", "fake", "--today", str(TODAY), "--days", "3",
                         "--performance-eval", str(perf), "--db-path", str(db_path), "--quiet"])
    assert code == 0
    tasks = [t for t in store.open_tasks() if t["kind"] == horizon.TASK_KIND]
    assert [t["campaign_slug"] for t in tasks] == ["broken-2026"]
    assert tasks[0]["urgency"] == "routine"
    assert "999" in json.dumps(tasks[0]["detail"])
    # the failure is recorded as a step and the run finishes failed
    failed_run = [r for r in store.rows["runs"] if r["campaign_slug"] == "broken-2026"][0]
    states = {s["step"]: s["state"] for s in store.run_steps(failed_run["run_id"])}
    assert states["race_page"] == "failed"
    assert states["finish"] == "failed"
    # the healthy campaign was still captured
    assert (d_ok / "predictions" / "stage_01" / "startlist.json").exists()
    assert not (d_broken / "predictions").exists()


def test_an_incomplete_start_list_is_rejected(perf, store, db_path):
    write_campaign(perf, "giro-test-2026", stage_race_config())
    client = Client()
    client.add_response(f"{horizon.BASE_URL}/race.php?r={FC_RACE_ID}&y={YEAR}&k=8",
                        MockResponse.from_html_file(
                            FIXTURES / "webscrape_tools" / "test_html" / "start_list.html"))
    summary = run(perf, store, client, db_path, days=3)
    assert summary["campaigns"][0]["status"] == "failed"
    assert "start list" in summary["campaigns"][0]["error"].lower()
    assert [t["kind"] for t in store.open_tasks()] == ["horizon_failed"]


# ---------------------------------------------------------------------------
# chip V (2026-09-18) — the race-local clock, and one list for the whole race
# ---------------------------------------------------------------------------

def _huangshan(perf):
    cfg = stage_race_config("huangshan-2026", start=dt.date(2026, 9, 17), stages=4)
    cfg["timezone"] = "Asia/Shanghai"
    return write_campaign(perf, "huangshan-2026", cfg)


def test_horizon_and_driver_pick_the_same_unit_east_of_utc(perf, store, tmp_path, capsys):
    """17:30 UTC on the 17th is 01:30 on the 18th in Shanghai: the tick that night previews the
    stage dated the 18th.  The old ``today < d`` rule skipped it and captured the 19th's."""
    from cycling_project.nightly import driver as drv

    d = _huangshan(perf)
    (d / "results" / "stage_01").mkdir(parents=True)
    (d / "results" / "stage_01" / "results.csv").write_text("place,name\n1,x\n")
    local = dt.datetime(2026, 9, 18, 1, 30)
    due = horizon.select_units(perf, store, days=1, local_now=local)
    assert due[0].units[0] == "stage_02"

    assert drv.main(["plan", "--campaign", str(d), "--dry-run", "--store-root", str(tmp_path / "s"),
                     "--local-now", "2026-09-18T03:45"]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["preview"] == ["stage_02"]
    assert plan["preview"][0] in due[0].units


def test_a_bare_today_still_means_that_evening(perf, store):
    _huangshan(perf)
    due = horizon.select_units(perf, store, days=1, today=dt.date(2026, 9, 18))
    assert due[0].units == ["stage_03"]


def test_the_start_list_goes_to_every_unsettled_unit(perf, store, db_path):
    cfg = stage_race_config(stages=3)
    cfg["void_stages"] = []
    d = write_campaign(perf, "giro-test-2026", cfg)
    (d / "results" / "stage_01").mkdir(parents=True)
    (d / "results" / "stage_01" / "results.csv").write_text("place,name\n1,x\n")
    summary = run(perf, store, Client(), db_path, days=1, today=dt.date(2026, 9, 17))
    assert summary["campaigns"][0]["units"] == ["stage_02"]
    assert not (d / "predictions" / "stage_01" / "startlist.json").exists()     # settled
    for unit in ("stage_02", "stage_03"):
        assert (d / "predictions" / unit / "startlist.json").exists(), unit


# ---------------------------------------------------------------------------
# chip Y — the capture covers what the tick will actually ask for (2026-09-22)
# ---------------------------------------------------------------------------

def test_a_d1_campaign_is_not_captured_by_default(perf, store):
    """No point handing a start list to a tick that will never ask for it."""
    write_campaign(perf, "d1-2026", stage_race_config("d1-2026", category="d1"))
    assert horizon.select_units(perf, store, today=TODAY) == []


def test_all_tiers_restores_the_d1_capture(perf, store):
    write_campaign(perf, "d1-2026", stage_race_config("d1-2026", category="d1"))
    due = horizon.select_units(perf, store, today=TODAY,
                               automation_tiers=tiers.KNOWN_TIERS)
    assert [d.slug for d in due] == ["d1-2026"]
    due = horizon.select_units(perf, store, today=TODAY,
                               automation_tiers=tiers.resolve_tiers(include=["d1"]))
    assert [d.slug for d in due] == ["d1-2026"]


def test_an_explicit_campaign_does_not_bypass_the_tier(perf, store):
    """One rule: --campaign narrows the sweep, it does not widen the coverage."""
    write_campaign(perf, "d1-2026", stage_race_config("d1-2026", category="d1"))
    assert horizon.select_units(perf, store, today=TODAY, only=["d1-2026"]) == []


def test_campaign_json_can_opt_a_d1_race_in(perf, store):
    cfg = stage_race_config("d1-2026", category="d1")
    cfg["automation"] = "on"
    write_campaign(perf, "d1-2026", cfg)
    assert [d.slug for d in horizon.select_units(perf, store, today=TODAY)] == ["d1-2026"]


def test_a_campaign_with_no_category_is_not_captured(perf, store):
    cfg = stage_race_config("mystery-2026")
    cfg.pop("category")
    write_campaign(perf, "mystery-2026", cfg)
    assert horizon.select_units(perf, store, today=TODAY) == []


def test_the_capture_and_the_driver_agree_on_the_tier(perf, store, tmp_path, capsys):
    """The horizon must not capture what the driver will not plan, and vice versa."""
    from cycling_project.nightly import driver as drv

    for category, automated in (("wt", True), ("pro", True), ("d1", False)):
        slug = f"{category}-2026"
        write_campaign(perf, slug, stage_race_config(slug, category=category))
        captured = [d.slug for d in horizon.select_units(perf, store, today=TODAY)]
        assert drv.main(["plan", "--campaign", str(perf / slug), "--dry-run",
                         "--store-root", str(tmp_path / f"store-{category}"),
                         "--today", str(TODAY)]) == 0
        plan = json.loads(capsys.readouterr().out)
        assert plan["automated"] is automated
        assert (slug in captured) is automated
        assert bool(plan["preview"]) is automated
        (perf / slug / "campaign.json").unlink()


def test_the_summary_records_the_covered_tiers(perf, store, db_path):
    write_campaign(perf, "pro-2026", stage_race_config("pro-2026"))
    summary = run(perf, store, Client(), db_path, dry_run=True)
    assert summary["automation_tiers"] == ["wt", "pro"]
