"""
Unit tests for the local-first Step-4 stage selector and results loading.

``enumerate_edition_stages`` must build the stage dropdown from the main DB
and ``cached_race_results`` without any network fetch, falling back to the
live race page only when the edition has no local stage data; and
``scrape_or_load_results`` must serve stage / GC competitions straight from
``rider_results`` when the caller keys them (stage_number / competition_type),
while keeping the legacy cache-first behaviour for unkeyed stage targets
(``fetch_live_race_state`` relies on that).

Everything runs against a throwaway SQLite file; the WebClient class and
``detect_race_stages`` / ``scrape_race_results`` are stubbed so any attempted
fetch fails the test loudly.
"""

import sqlite3

import pytest

from cycling_project.prediction_tools import future_race_loader
from cycling_project.prediction_tools.future_race_loader import (
    _ensure_cache_tables,
    scrape_or_load_results,
)
from cycling_project.prediction_tools.live_race_state import (
    enumerate_edition_stages,
)

pytestmark = pytest.mark.unit


class _NoNetworkClient:
    def __init__(self, *args, **kwargs):
        pass

    def get(self, *args, **kwargs):
        raise AssertionError("network fetch attempted in unit test")

    def close(self):
        pass


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setattr(future_race_loader, 'WebClient', _NoNetworkClient)


def _forbid_live_detection(monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("detect_race_stages called — live page fetched")
    monkeypatch.setattr(future_race_loader, 'detect_race_stages', _boom)


def _forbid_results_scrape(monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("scrape_race_results called — live page fetched")
    monkeypatch.setattr(future_race_loader, 'scrape_race_results', _boom)


@pytest.fixture
def db_path(tmp_path):
    """Temp DB: a stage race (500/2026), a one-day (600/2026), and a
    finished stage race with migrated GC (700/2025)."""
    path = str(tmp_path / "test.db")
    with sqlite3.connect(path) as conn:
        conn.executescript("""
        CREATE TABLE races (
            id INTEGER PRIMARY KEY, fc_race_id TEXT, name TEXT,
            year INTEGER, is_stage_race BOOLEAN
        );
        CREATE TABLE competitions (
            id INTEGER PRIMARY KEY, race_id INTEGER, name TEXT,
            stage_number INTEGER, competition_type TEXT, date DATE,
            winning_time REAL, url TEXT
        );
        CREATE TABLE riders (
            id INTEGER PRIMARY KEY, fc_rider_id TEXT, name TEXT
        );
        CREATE TABLE teams (
            id INTEGER PRIMARY KEY, fc_team_id TEXT, name TEXT
        );
        CREATE TABLE rider_results (
            id INTEGER PRIMARY KEY, competition_id INTEGER,
            rider_id INTEGER, team_id INTEGER, place INTEGER,
            time_gap REAL, place_bucket INTEGER, percentile REAL
        );

        INSERT INTO riders VALUES (1, 'r1', 'Rider One'), (2, 'r2', 'Rider Two');
        INSERT INTO teams VALUES (1, 't1', 'Team Alpha');

        -- 500/2026: in-progress stage race. Stages 1-3 migrated with
        -- results (stage 3 row has no stored url); stage 4 migrated but
        -- empty (results not in yet).
        INSERT INTO races VALUES (1, '500', 'Test Tour', 2026, 1);
        INSERT INTO competitions VALUES
            (11, 1, 'Stage 1', 1, 'stage', '2026-06-01', 13438.0,
             'https://firstcycling.com/race.php?r=500&y=2026&e=1'),
            (12, 1, 'Stage 2', 2, 'stage', '2026-06-02', 20429.0,
             'https://firstcycling.com/race.php?r=500&y=2026&e=2'),
            (13, 1, 'Stage 3', 3, 'stage', '2026-06-03', 36061.0, NULL),
            (14, 1, 'Stage 4', 4, 'stage', '2026-06-04', 12848.0,
             'https://firstcycling.com/race.php?r=500&y=2026&e=4');
        INSERT INTO rider_results (competition_id, rider_id, team_id, place,
                                   time_gap, place_bucket) VALUES
            (11, 1, 1, 1, 0.0, 0), (11, 2, NULL, 2, 5.0, 1),
            (12, 1, 1, 1, 0.0, 0), (12, 2, NULL, 2, 8.0, 1),
            (13, 1, 1, 1, 0.0, 0), (13, 2, NULL, 2, 3.0, 1);

        -- 600/2026: one-day race with migrated results.
        INSERT INTO races VALUES (2, '600', 'Test Classic', 2026, 0);
        INSERT INTO competitions VALUES
            (21, 2, 'Test Classic', NULL, 'one_day', '2026-04-05',
             17000.0, 'https://firstcycling.com/race.php?r=600&y=2026');
        INSERT INTO rider_results (competition_id, rider_id, team_id, place,
                                   time_gap, place_bucket) VALUES
            (21, 1, 1, 1, 0.0, 0), (21, 2, NULL, 2, 12.0, 1);

        -- 700/2025: finished stage race with migrated GC, plus an empty
        -- duplicate stage-1 competition left by migrations.
        INSERT INTO races VALUES (3, '700', 'Test Tour Two', 2025, 1);
        INSERT INTO competitions VALUES
            (31, 3, 'Stage 1', 1, 'stage', '2025-06-01', 14000.0,
             'https://firstcycling.com/race.php?r=700&y=2025&e=1'),
            (32, 3, 'GC', NULL, 'gc', '2025-06-02', 50000.0,
             'https://firstcycling.com/race.php?r=700&y=2025'),
            (33, 3, 'Stage 1 dup', 1, 'stage', '2025-06-01', NULL, NULL);
        INSERT INTO rider_results (competition_id, rider_id, team_id, place,
                                   time_gap, place_bucket) VALUES
            (31, 1, 1, 1, 0.0, 0), (31, 2, NULL, 2, 6.0, 1),
            (32, 1, 1, 1, 0.0, 0), (32, 2, NULL, 2, 30.0, 1);
        """)

    _ensure_cache_tables(path)
    with sqlite3.connect(path) as conn:
        # 500/2026 cache: stage 1 (also in DB, different place so the
        # legacy cache-first path is distinguishable), stages 3-5, and a
        # GC tab cached under the live selector's '0' value.
        conn.executemany(
            "INSERT INTO cached_race_results "
            "(fc_race_id, year, stage_id, stage_name, rider_fc_id, "
            " rider_name, team_name, place, time_gap, place_bucket, "
            " winning_time) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ('500', 2026, '1', '1', 'r1', 'Rider One', 'Team Alpha',
                 99, 0.0, 6, 100.0),
                ('500', 2026, '3', '3', 'r1', 'Rider One', 'Team Alpha',
                 1, 0.0, 0, 36061.0),
                ('500', 2026, '4', '4', 'r1', 'Rider One', 'Team Alpha',
                 1, 0.0, 0, 12848.0),
                ('500', 2026, '5', '5', 'r1', 'Rider One', 'Team Alpha',
                 99, 0.0, 6, 100.0),
                ('500', 2026, '0', 'GC', 'r1', 'Rider One', 'Team Alpha',
                 1, 0.0, 0, 90000.0),
            ],
        )
        conn.commit()
    return path


# ── enumerate_edition_stages ─────────────────────────────────────────────

class TestEnumerateEditionStages:
    def test_merges_db_and_cache_without_fetch(self, db_path, monkeypatch):
        _forbid_live_detection(monkeypatch)
        is_stage_race, entries = enumerate_edition_stages(500, 2026, db_path)

        assert is_stage_race is True
        assert [e['name'] for e in entries] == [
            'Stage 1', 'Stage 2', 'Stage 3', 'Stage 4', 'Stage 5', 'GC',
        ]
        by_name = {e['name']: e for e in entries}
        # DB-backed stages carry the url param mined from competitions.url;
        # stage 3 has none stored and falls back to its cached stage_id.
        assert by_name['Stage 1'] == {
            'stage_number': 1, 'name': 'Stage 1', 'url_param': '1',
            'competition_type': 'stage', 'source': 'db',
        }
        assert by_name['Stage 3']['source'] == 'db'
        assert by_name['Stage 3']['url_param'] == '3'
        # Stage 4 is migrated but has no results yet -> cache-backed entry.
        assert by_name['Stage 4']['source'] == 'cache'
        assert by_name['Stage 5'] == {
            'stage_number': 5, 'name': 'Stage 5', 'url_param': '5',
            'competition_type': 'stage', 'source': 'cache',
        }
        # The cached '0' row is the live selector's GC tab, not a prologue.
        assert by_name['GC'] == {
            'stage_number': None, 'name': 'GC', 'url_param': '0',
            'competition_type': 'gc', 'source': 'cache',
        }

    def test_known_one_day_skips_fetch(self, db_path, monkeypatch):
        _forbid_live_detection(monkeypatch)
        assert enumerate_edition_stages(600, 2026, db_path) == (False, [])

    def test_migrated_gc_gets_db_entry(self, db_path, monkeypatch):
        _forbid_live_detection(monkeypatch)
        is_stage_race, entries = enumerate_edition_stages(700, 2025, db_path)
        assert is_stage_race is True
        assert [e['name'] for e in entries] == ['Stage 1', 'GC']
        assert entries[1] == {
            'stage_number': None, 'name': 'GC', 'url_param': '0',
            'competition_type': 'gc', 'source': 'db',
        }

    def test_unknown_race_uses_live_fallback(self, db_path, monkeypatch):
        raw = [
            {'name': 'Stage: 1', 'url_param': '1'},
            {'name': 'Stage: 2', 'url_param': '2'},
            {'name': 'Stage 7a', 'url_param': '7a'},
            {'name': 'Points', 'url_param': '11'},
            {'name': 'GC', 'url_param': '0'},
        ]
        monkeypatch.setattr(
            future_race_loader, 'detect_race_stages',
            lambda *a, **k: (True, raw),
        )
        is_stage_race, entries = enumerate_edition_stages(999, 2026, db_path)
        assert is_stage_race is True
        assert all(e['source'] == 'live' for e in entries)
        by_name = {e['name']: e for e in entries}
        assert by_name['Stage: 1']['competition_type'] == 'stage'
        assert by_name['Stage: 1']['stage_number'] == 1
        assert by_name['GC']['competition_type'] == 'gc'
        assert by_name['GC']['stage_number'] is None
        # Ambiguous entries get no DB key: cache/scrape handles them.
        assert by_name['Stage 7a']['competition_type'] is None
        assert by_name['Stage 7a']['stage_number'] is None
        assert by_name['Points']['competition_type'] is None

    def test_live_failure_with_no_local_data(self, db_path, monkeypatch):
        monkeypatch.setattr(
            future_race_loader, 'detect_race_stages',
            lambda *a, **k: (False, []),
        )
        assert enumerate_edition_stages(999, 2026, db_path) == (False, [])

    def test_prefer_live_keeps_local_list_on_failure(self, db_path, monkeypatch):
        monkeypatch.setattr(
            future_race_loader, 'detect_race_stages',
            lambda *a, **k: (False, []),
        )
        is_stage_race, entries = enumerate_edition_stages(
            500, 2026, db_path, prefer_live=True
        )
        assert is_stage_race is True
        assert len(entries) == 6
        assert all(e['source'] in ('db', 'cache') for e in entries)


# ── scrape_or_load_results keyed DB serving ──────────────────────────────

class TestScrapeOrLoadResults:
    def test_stage_served_from_db(self, db_path, monkeypatch):
        _forbid_results_scrape(monkeypatch)
        df, wt = scrape_or_load_results(
            500, 2026, stage_id='2', stage_url_param='2',
            stage_number=2, competition_type='stage', db_path=db_path,
        )
        assert wt == 20429.0
        assert df['place'].tolist() == [1, 2]
        assert df['rider_name'].tolist() == ['Rider One', 'Rider Two']
        assert df['team_name'].tolist()[0] == 'Team Alpha'
        assert df['rider_id'].tolist() == [1, 2]

    def test_stage_missing_from_db_falls_to_cache(self, db_path, monkeypatch):
        _forbid_results_scrape(monkeypatch)
        df, wt = scrape_or_load_results(
            500, 2026, stage_id='5', stage_url_param='5',
            stage_number=5, competition_type='stage', db_path=db_path,
        )
        assert wt == 100.0
        assert df['place'].tolist() == [99]

    def test_gc_served_from_db(self, db_path, monkeypatch):
        _forbid_results_scrape(monkeypatch)
        df, wt = scrape_or_load_results(
            700, 2025, stage_id='0', stage_url_param='0',
            competition_type='gc', db_path=db_path,
        )
        assert wt == 50000.0
        assert df['place'].tolist() == [1, 2]

    def test_duplicate_stage_competitions_pick_populated(
        self, db_path, monkeypatch
    ):
        _forbid_results_scrape(monkeypatch)
        df, wt = scrape_or_load_results(
            700, 2025, stage_id='1', stage_url_param='1',
            stage_number=1, competition_type='stage', db_path=db_path,
        )
        assert wt == 14000.0  # comp 31, not the empty duplicate 33
        assert len(df) == 2

    def test_unkeyed_stage_target_stays_cache_first(self, db_path, monkeypatch):
        # Legacy semantics for fetch_live_race_state: stage_id without
        # stage_number must NOT consult rider_results.
        _forbid_results_scrape(monkeypatch)
        df, wt = scrape_or_load_results(
            500, 2026, stage_id='1', stage_url_param='1', db_path=db_path,
        )
        assert df['place'].tolist() == [99]  # the cache row, not DB place 1
        assert wt == 100.0

    def test_one_day_db_first_unchanged(self, db_path, monkeypatch):
        _forbid_results_scrape(monkeypatch)
        df, wt = scrape_or_load_results(600, 2026, db_path=db_path)
        assert wt == 17000.0
        assert df['place'].tolist() == [1, 2]
        assert 'team_name' in df.columns
