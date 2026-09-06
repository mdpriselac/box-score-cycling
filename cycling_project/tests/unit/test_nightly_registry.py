import json
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from cycling_project.nightly.registry import merge_calendar_sidecars, sync
from cycling_project.nightly.store import FakeStore, StorePermissionError
from cycling_project import update_pipeline

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _calendar_row(**overrides):
    row = {
        "fc_race_id": "99",
        "year": 2026,
        "name": "Test Tour",
        "url": "https://firstcycling.com/race.php?r=99&y=2026",
        "category": "pro",
        "calendar_category": "2.Pro",
        "is_stage_race": True,
        "start_date": "2026-09-10",
        "end_date": "2026-09-12",
        "country": "Spain",
        "week": "2026-W36",
        "source": "performance_eval/calendar/2026.json",
    }
    row.update(overrides)
    return row


def test_merge_sidecars_is_deterministic_and_adds_registry_metadata(tmp_path):
    scraped = tmp_path / "scraped"
    sidecar = scraped / "2026" / "pro" / "pro.calendar.json"
    sidecar.parent.mkdir(parents=True)
    sidecar.write_text(json.dumps([_calendar_row(category=None, week=None, source=None)]))
    perf = tmp_path / "performance_eval"

    merged = merge_calendar_sidecars(
        scraped, perf, [2026], as_of=date(2026, 9, 6)
    )

    assert merged[2026][0]["category"] == "pro"
    assert merged[2026][0]["week"] == "2026-W36"
    saved = json.loads((perf / "calendar" / "2026.json").read_text())
    assert saved["races"] == merged[2026]


def test_pipeline_calendar_horizon_includes_next_month(tmp_path, monkeypatch):
    db = tmp_path / "db.sqlite"
    with sqlite3.connect(db) as connection:
        connection.executescript(
            "CREATE TABLE races (id INTEGER PRIMARY KEY);"
            "CREATE TABLE competitions (race_id INTEGER, date TEXT);"
            "INSERT INTO races VALUES (1);"
            "INSERT INTO competitions VALUES (1, '2026-09-01');"
        )

    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 9, 6)

    monkeypatch.setattr(update_pipeline, "date", FixedDate)
    config = update_pipeline.PipelineConfig(
        project_root=tmp_path, scraped_data_dir=tmp_path / "scraped",
        db_path=db, model_dir=tmp_path / "models",
    )
    assert update_pipeline.determine_scrape_targets(config) == [
        ("2026", [7, 8, 9, 10])
    ]


def test_registry_creates_campaign_and_store_rows_without_network(tmp_path):
    perf = tmp_path / "performance_eval"
    calendar = perf / "calendar" / "2026.json"
    calendar.parent.mkdir(parents=True)
    calendar.write_text(json.dumps({"schema_version": 1, "year": 2026,
                                    "races": [_calendar_row()]}))
    store = FakeStore(tmp_path / "store", role="operator")

    result = sync(perf, horizon=14, now=date(2026, 9, 6), store=store)

    campaign_file = perf / "test-tour-2026" / "campaign.json"
    campaign = json.loads(campaign_file.read_text())
    assert campaign["timezone"] == "Europe/Madrid"
    assert campaign["pcs_slug"] == "test-tour"
    assert campaign["kambi_event_ids"] == {}
    assert campaign["organiser_stage_urls"] == {}
    assert campaign["void_stages"] == []
    assert [stage["date"] for stage in campaign["stages"]] == [
        "2026-09-10", "2026-09-11", "2026-09-12"
    ]
    assert result["store_synced"] is True
    assert len(store.rows["calendar"]) == 1
    assert len(store.rows["campaigns"]) == 1
    assert len(store.rows["stages"]) == 3


def test_registry_fills_unknowns_but_never_overwrites_known_fields(tmp_path):
    perf = tmp_path / "performance_eval"
    calendar = perf / "calendar" / "2026.json"
    calendar.parent.mkdir(parents=True)
    calendar.write_text(json.dumps({"races": [_calendar_row()]}))
    campaign_file = perf / "test-tour-2026" / "campaign.json"
    campaign_file.parent.mkdir(parents=True)
    campaign_file.write_text(json.dumps({
        "slug": "test-tour-2026", "name": "Editor's Name", "fc_race_id": "99",
        "year": 2026, "timezone": "Europe/Custom", "pcs_slug": None,
        "stages": [{"number": 1, "date": "2026-09-10", "towns": "Known finish"}],
    }))

    sync(perf, horizon=14, now=date(2026, 9, 6), store_mode="none")
    campaign = json.loads(campaign_file.read_text())
    assert campaign["name"] == "Editor's Name"
    assert campaign["timezone"] == "Europe/Custom"
    assert campaign["pcs_slug"] == "test-tour"
    assert campaign["stages"][0]["towns"] == "Known finish"
    assert len(campaign["stages"]) == 3


def test_registry_reuses_handwritten_campaign_slug_for_same_fc_race(tmp_path):
    perf = tmp_path / "performance_eval"
    calendar = perf / "calendar" / "2026.json"
    calendar.parent.mkdir(parents=True)
    calendar.write_text(json.dumps({"races": [_calendar_row(name="Vuelta a España")]}))
    handwritten = perf / "vuelta-2026" / "campaign.json"
    handwritten.parent.mkdir(parents=True)
    handwritten.write_text(json.dumps({
        "slug": "vuelta-2026", "name": "Vuelta a España 2026",
        "fc_race_id": "99", "year": 2026,
    }))

    result = sync(perf, horizon=14, now=date(2026, 9, 6), store_mode="none")

    assert result["campaigns"][0]["slug"] == "vuelta-2026"
    assert not (perf / "vuelta-a-espana-2026").exists()
    saved = json.loads(handwritten.read_text())
    assert saved["name"] == "Vuelta a España 2026"
    assert saved["stages"]


def test_registry_dry_run_writes_nothing(tmp_path):
    perf = tmp_path / "performance_eval"
    calendar = perf / "calendar" / "2026.json"
    calendar.parent.mkdir(parents=True)
    calendar.write_text(json.dumps({"races": [_calendar_row()]}))
    store = FakeStore(tmp_path / "store", role="operator")

    result = sync(perf, horizon=14, now=date(2026, 9, 6), dry_run=True, store=store)

    assert result["campaigns"][0]["changed"] is True
    assert not (perf / "test-tour-2026" / "campaign.json").exists()
    assert store.rows == {}


@pytest.mark.parametrize("role", ["agent", "reader"])
def test_registry_store_writes_are_operator_only(tmp_path, role):
    store = FakeStore(tmp_path / role, role=role)
    with pytest.raises(StorePermissionError):
        store.sync_calendar([_calendar_row()])
    with pytest.raises(StorePermissionError):
        store.sync_campaign({"campaign_slug": "test-tour-2026"})
    with pytest.raises(StorePermissionError):
        store.sync_stages([{"campaign_slug": "test-tour-2026", "unit": "stage_01"}])


def test_operator_registry_store_sync_is_idempotent_and_non_overwriting(tmp_path):
    store = FakeStore(tmp_path / "operator", role="operator")
    store.sync_calendar([_calendar_row(country=None)])
    store.sync_calendar([_calendar_row(name="Changed", country="Spain")])
    assert len(store.rows["calendar"]) == 1
    assert store.rows["calendar"][0]["name"] == "Test Tour"
    assert store.rows["calendar"][0]["country"] == "Spain"

    campaign = {
        "campaign_slug": "test-tour-2026", "fc_race_id": "99", "year": 2026,
        "name": "Test Tour", "timezone": None, "config": {"known": "yes", "new": None},
    }
    store.sync_campaign(campaign)
    store.sync_campaign({**campaign, "name": "Changed", "timezone": "Europe/Madrid",
                         "config": {"known": "changed", "new": "filled"}})
    assert len(store.rows["campaigns"]) == 1
    saved = store.rows["campaigns"][0]
    assert saved["name"] == "Test Tour"
    assert saved["timezone"] == "Europe/Madrid"
    assert saved["config"] == {"known": "yes", "new": "filled"}


@pytest.mark.parametrize("campaign", ["tour-de-france-2026", "vuelta-2026"])
def test_handwritten_campaign_stage_dates_match_committed_configs(campaign):
    root = PROJECT_ROOT / "performance_eval" / campaign
    registry = json.loads((root / "campaign.json").read_text())
    by_number = {stage["number"]: stage["date"] for stage in registry["stages"]}
    assert len(by_number) == 21
    for path in (root / "predictions").glob("stage_*/scenarios.json"):
        config = json.loads(path.read_text())
        assert by_number[int(config["stage"])] == config["date"]
    if campaign == "vuelta-2026":
        assert registry["void_stages"] == [3]
