"""Tests for stage-race date derivation in migrate_races.

Stage-race pickles never carry a race-level date (the scraper only sets one
for one-day races), so the migrator must derive races.date and the GC
competition date from the stage dates at insert time.
"""

import pickle
import sqlite3

import pytest

from cycling_project.webscrape_tools.create_race_data import Race, Stage
from cycling_project.webscrape_tools.database.migrate_races import RaceMigrator

SCHEMA = """
    CREATE TABLE races (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fc_race_id TEXT, name TEXT, year INTEGER, date DATE,
        category TEXT, is_stage_race BOOLEAN, url TEXT
    );
    CREATE TABLE competitions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        race_id INTEGER, name TEXT, stage_number INTEGER,
        competition_type TEXT, date DATE, winning_time REAL, url TEXT
    );
    CREATE TABLE riders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fc_rider_id TEXT, name TEXT, birth_year INTEGER
    );
    CREATE TABLE teams (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fc_team_id TEXT, name TEXT
    );
    CREATE TABLE rider_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        competition_id INTEGER, rider_id INTEGER, team_id INTEGER,
        place INTEGER, time_gap REAL, bib_number TEXT, rider_age INTEGER,
        percentile REAL, place_bucket INTEGER
    );
"""


def _results():
    return [{
        'place': '1', 'name': 'Test Rider', 'rider_id': 'r1', 'dob': '1995',
        'team': 'Test Team', 'team_id': 't1', 'gap': '0', 'bib_number': '1',
    }]


def _stage_race(stage_dates, race_date=None):
    race = Race(
        name='Test Tour', url='https://firstcycling.com/race.php?r=99&y=2025',
        year=2025, date=race_date, stage_race=True, results=_results(),
        fc_race_id='99',
    )
    race.stages = [
        Stage(name=f'Stage: {i + 1:02d}', url=race.url, fc_race_id='99',
              year=2025, date=d, results=_results())
        for i, d in enumerate(stage_dates)
    ]
    return race


@pytest.fixture
def migrator(tmp_path):
    db_path = tmp_path / 'test.db'
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.close()
    m = RaceMigrator(str(tmp_path), str(db_path))
    m.connect()
    yield m
    m.disconnect()


def _migrate(migrator, race, tmp_path):
    pkl_file = tmp_path / f'{race.name}.pkl'
    with open(pkl_file, 'wb') as f:
        pickle.dump(race, f)
    migrator.migrate_race(pkl_file, 'wt')
    migrator.conn.commit()


@pytest.mark.unit
def test_gc_date_derived_from_final_stage(migrator, tmp_path):
    race = _stage_race(['2025-07-05', '2025-07-06', '2025-07-04'])
    _migrate(migrator, race, tmp_path)

    gc_date, race_date = migrator.cursor.execute("""
        SELECT c.date, r.date FROM competitions c JOIN races r ON r.id = c.race_id
        WHERE c.competition_type = 'gc'
    """).fetchone()
    assert gc_date == '2025-07-06'
    assert race_date == '2025-07-06'


@pytest.mark.unit
def test_gc_rider_age_computed_from_derived_date(migrator, tmp_path):
    race = _stage_race(['2025-07-05', '2025-07-06'])
    _migrate(migrator, race, tmp_path)

    (age,) = migrator.cursor.execute("""
        SELECT rr.rider_age FROM rider_results rr
        JOIN competitions c ON c.id = rr.competition_id
        WHERE c.competition_type = 'gc'
    """).fetchone()
    assert age == 2025 - 1995


@pytest.mark.unit
def test_gc_pseudo_stage_date_participates(migrator, tmp_path):
    # Final road stages can be undated while the 'GC' pseudo-stage carries
    # the final day; the pseudo-stage is skipped as a competition but its
    # date must still drive the GC date.
    race = _stage_race(['2025-07-05', None])
    race.stages.append(Stage(name='GC', url=race.url, fc_race_id='99',
                             year=2025, date='2025-07-06'))
    _migrate(migrator, race, tmp_path)

    (gc_date,) = migrator.cursor.execute(
        "SELECT date FROM competitions WHERE competition_type = 'gc'"
    ).fetchone()
    assert gc_date == '2025-07-06'


@pytest.mark.unit
def test_explicit_race_date_wins(migrator, tmp_path):
    race = _stage_race(['2025-07-05', '2025-07-06'], race_date='2025-07-10')
    _migrate(migrator, race, tmp_path)

    gc_date, race_date = migrator.cursor.execute("""
        SELECT c.date, r.date FROM competitions c JOIN races r ON r.id = c.race_id
        WHERE c.competition_type = 'gc'
    """).fetchone()
    assert gc_date == '2025-07-10'
    assert race_date == '2025-07-10'


@pytest.mark.unit
def test_all_stage_dates_missing_leaves_null(migrator, tmp_path):
    race = _stage_race([None, None])
    _migrate(migrator, race, tmp_path)

    (gc_date,) = migrator.cursor.execute(
        "SELECT date FROM competitions WHERE competition_type = 'gc'"
    ).fetchone()
    assert gc_date is None


@pytest.mark.unit
def test_one_day_race_date_unchanged(migrator, tmp_path):
    race = Race(
        name='Test Classic', url='https://firstcycling.com/race.php?r=98&y=2025',
        year=2025, date='2025-04-13', stage_race=False, results=_results(),
        fc_race_id='98',
    )
    _migrate(migrator, race, tmp_path)

    (date,) = migrator.cursor.execute(
        "SELECT date FROM competitions WHERE competition_type = 'one_day'"
    ).fetchone()
    assert date == '2025-04-13'
