"""
In-progress stage races through the pipeline: scraper staleness + migration
refresh.

Covers the two defects fixed 2026-07-12:

1. download_race_data.create_to_scrape_list_tour froze mid-race pickles —
   future stages carry no date on FirstCycling, so "past stage without
   results" never matched and the pickle was never re-scraped.
2. update_pipeline.migrate_new_races permanently skipped races already in
   the `races` table, so a race migrated mid-event never received its
   remaining stages or final GC (the CLAUDE.md migration gotcha).
"""

import pickle
import sqlite3
from datetime import date, timedelta

import pytest

from cycling_project.update_pipeline import (
    _get_db_result_counts,
    _get_races_needing_refresh,
    _pickle_result_counts,
)
from cycling_project.webscrape_tools.create_race_data import Race, Stage
from cycling_project.webscrape_tools.download_race_data import (
    create_to_scrape_list_tour,
)

YESTERDAY = (date.today() - timedelta(days=1)).isoformat()
TOMORROW = (date.today() + timedelta(days=1)).isoformat()
RESULT_ROW = [{"rider": "A", "place": 1}]
# Mid-race, FirstCycling's race page serves only the abandons as race-level
# rows — a DNF board, not a final GC.
DNF_BOARD = [{"name": "X", "place": "DNF"}, {"name": "Y", "place": "DNF"}]


def _stage(name, stage_date, with_results):
    return Stage(name=name, url="u", date=stage_date,
                 results=list(RESULT_ROW) if with_results else [])


def _stage_race(name, fc_race_id, stages, gc_results=False):
    return Race(name=name, url="u", year=2026, stage_race=True,
                fc_race_id=fc_race_id, stages=stages,
                results=list(RESULT_ROW) if gc_results else [])


COMPLETE = [_stage("GC", YESTERDAY, True),
            _stage("Stage: 01", YESTERDAY, True),
            _stage("Stage: 02", YESTERDAY, True)]
# Mid-race: stage 1 raced, stage 2 unraced and UNDATED (FirstCycling serves
# no date div on unraced stage pages), GC undated and empty.
MIDRACE = [_stage("GC", None, False),
           _stage("Stage: 01", YESTERDAY, True),
           _stage("Stage: 02", None, False)]
# Pre-race pickle whose stage list is dated (route announced): all future.
FUTURE = [_stage("GC", None, False),
          _stage("Stage: 01", TOMORROW, False),
          _stage("Stage: 02", TOMORROW, False)]


# ---------------------------------------------------------------------------
# Scraper staleness
# ---------------------------------------------------------------------------

def _tour_dir_with(tmp_path, race):
    tour = tmp_path / "wt"
    tour.mkdir()
    (tour / "races.txt").write_text(f"{race.name},u\n")
    with open(tour / f"{race.name}.pkl", "wb") as f:
        pickle.dump(race, f)
    return tour


@pytest.mark.unit
def test_complete_stage_race_pickle_is_not_stale(tmp_path):
    tour = _tour_dir_with(tmp_path, _stage_race("Done", 1, COMPLETE, gc_results=True))
    assert create_to_scrape_list_tour(str(tour)) == []
    assert (tour / "Done.pkl").exists()


@pytest.mark.unit
def test_midrace_pickle_with_undated_future_stages_is_stale(tmp_path):
    tour = _tour_dir_with(tmp_path, _stage_race("Tour", 17, MIDRACE))
    assert create_to_scrape_list_tour(str(tour)) == [("Tour", "u")]
    assert not (tour / "Tour.pkl").exists()  # stale pickle removed


@pytest.mark.unit
def test_future_dated_prerace_pickle_is_stale(tmp_path):
    # Pre-race pickles are phantoms (scrape_tour_data never writes result-less
    # races); a legacy one re-scrapes until the race actually has results —
    # its undated result-less GC entry marks it, since race.results is empty.
    tour = _tour_dir_with(tmp_path, _stage_race("Next", 2, FUTURE))
    assert create_to_scrape_list_tour(str(tour)) == [("Next", "u")]


@pytest.mark.unit
def test_completed_race_with_cancelled_undated_stage_is_not_stale(tmp_path):
    # One result-less undated stage (weather-cancelled) in an otherwise
    # complete race with final GC — must NOT refetch forever.
    stages = COMPLETE + [_stage("Stage: 03", None, False)]
    tour = _tour_dir_with(tmp_path, _stage_race("Cut", 3, stages, gc_results=True))
    assert create_to_scrape_list_tour(str(tour)) == []


# ---------------------------------------------------------------------------
# Migration refresh decision
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_pickle_result_counts_excludes_gc_pseudo_stage():
    race = _stage_race("Tour", 17, COMPLETE, gc_results=True)
    assert _pickle_result_counts(race) == (2, True)
    assert _pickle_result_counts(_stage_race("Tour", 17, MIDRACE)) == (1, False)


@pytest.mark.unit
def test_dnf_board_does_not_count_as_gc():
    race = _stage_race("Tour", 17, MIDRACE)
    race.results = list(DNF_BOARD)
    assert _pickle_result_counts(race) == (1, False)


@pytest.mark.unit
def test_midrace_pickle_with_dnf_board_is_still_stale(tmp_path):
    # The live TdF 2026 shape: raced stages have results, unraced stages are
    # undated, and race.results carries the DNF board — must still re-scrape.
    race = _stage_race("Tour", 17, MIDRACE)
    race.results = list(DNF_BOARD)
    tour = _tour_dir_with(tmp_path, race)
    assert create_to_scrape_list_tour(str(tour)) == [("Tour", "u")]


def _seed_db(db_path, fc_race_id, n_result_stages, with_gc, n_empty_stages=0):
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS races (
            id INTEGER PRIMARY KEY, fc_race_id TEXT, year INT, category TEXT);
        CREATE TABLE IF NOT EXISTS competitions (
            id INTEGER PRIMARY KEY, race_id INT, competition_type TEXT);
        CREATE TABLE IF NOT EXISTS rider_results (
            id INTEGER PRIMARY KEY, competition_id INT);
    """)
    cur = conn.execute(
        "INSERT INTO races (fc_race_id, year, category) VALUES (?, 2026, 'wt')",
        (str(fc_race_id),))
    race_id = cur.lastrowid
    for _ in range(n_result_stages):
        c = conn.execute(
            "INSERT INTO competitions (race_id, competition_type) VALUES (?, 'stage')",
            (race_id,)).lastrowid
        conn.execute("INSERT INTO rider_results (competition_id) VALUES (?)", (c,))
    for _ in range(n_empty_stages):
        conn.execute(
            "INSERT INTO competitions (race_id, competition_type) VALUES (?, 'stage')",
            (race_id,))
    if with_gc:
        c = conn.execute(
            "INSERT INTO competitions (race_id, competition_type) VALUES (?, 'gc')",
            (race_id,)).lastrowid
        conn.execute("INSERT INTO rider_results (competition_id) VALUES (?)", (c,))
    conn.commit()
    conn.close()


@pytest.mark.unit
def test_db_result_counts_ignore_empty_competitions(tmp_path):
    db = str(tmp_path / "t.db")
    _seed_db(db, 17, n_result_stages=2, with_gc=False, n_empty_stages=3)
    assert _get_db_result_counts(db, [2026]) == {("17", 2026, "wt"): (2, False)}


class _Config:
    def __init__(self, scraped_data_dir):
        self.scraped_data_dir = scraped_data_dir
        self.tour_levels = ["wt"]


def _refresh_keys(tmp_path, race, db_stages, db_gc):
    tour = tmp_path / "2026" / "wt"
    tour.mkdir(parents=True)
    with open(tour / f"{race.name}.pkl", "wb") as f:
        pickle.dump(race, f)
    db = str(tmp_path / "t.db")
    _seed_db(db, race.fc_race_id, n_result_stages=db_stages, with_gc=db_gc)
    counts = _get_db_result_counts(db, [2026])
    return _get_races_needing_refresh(
        _Config(tmp_path), [("2026", [])], counts)


@pytest.mark.unit
def test_race_that_gained_stages_is_refreshed(tmp_path):
    race = _stage_race("Tour", 17, COMPLETE, gc_results=True)  # 2 stages + GC
    assert _refresh_keys(tmp_path, race, db_stages=1, db_gc=False) == {("17", 2026, "wt")}


@pytest.mark.unit
def test_race_that_gained_only_gc_is_refreshed(tmp_path):
    race = _stage_race("Tour", 17, COMPLETE, gc_results=True)
    assert _refresh_keys(tmp_path, race, db_stages=2, db_gc=False) == {("17", 2026, "wt")}


@pytest.mark.unit
def test_fully_migrated_race_is_not_refreshed(tmp_path):
    race = _stage_race("Tour", 17, COMPLETE, gc_results=True)
    assert _refresh_keys(tmp_path, race, db_stages=2, db_gc=True) == set()


@pytest.mark.unit
def test_stale_pickle_never_deletes_fuller_db_row(tmp_path):
    race = _stage_race("Tour", 17, MIDRACE)  # 1 result stage, no GC
    assert _refresh_keys(tmp_path, race, db_stages=5, db_gc=True) == set()
