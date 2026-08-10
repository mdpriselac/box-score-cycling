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

And the cancelled-stage churn fixed 2026-08-09:

3. A past-dated result-less stage in a settled race (final GC posted, or —
   when FirstCycling publishes no GC at all, as for Vuelta a Murcia 2026
   after its stage 2 was weather-cancelled — every stage dated and past the
   results-posting grace) marked the pickle stale on every run, and its
   zero-result stage competition marked the race incomplete on every run,
   so the race was deleted + re-migrated forever, churning competition ids.
4. The one-day analogue of 3: a result-less one-day pickle with any past
   date was stale forever (Duo Normand 2012–19 — FirstCycling never posts
   its results), deleted + re-fetched on every run over its folder. Now
   only a date within the posting grace ("results not up yet") is stale.

And the dotted-name stem truncation fixed 2026-08-09:

5. create_to_scrape_list_tour derived pickle stems with split('.'), so a
   race name containing a period ("Kamp. van Vlaanderen", "Pro Ötztaler
   5.500") never matched its races.txt entry — re-scraped on every run
   despite a complete pickle — and the staleness loop opened a nonexistent
   "<stem>.pkl" ("Kamp.pkl"), warning every run and never actually
   checking the real pickle.
"""

import pickle
import sqlite3
from datetime import date, timedelta

import pytest

from cycling_project.update_pipeline import (
    _get_db_result_counts,
    _get_incomplete_race_keys,
    _get_races_needing_refresh,
    _pickle_result_counts,
)
from cycling_project.webscrape_tools.create_race_data import Race, Stage
from cycling_project.webscrape_tools.download_race_data import (
    RESULTS_POSTING_GRACE_DAYS,
    create_to_scrape_list_tour,
)

YESTERDAY = (date.today() - timedelta(days=1)).isoformat()
TOMORROW = (date.today() + timedelta(days=1)).isoformat()
LONG_AGO = (
    date.today() - timedelta(days=RESULTS_POSTING_GRACE_DAYS + 30)
).isoformat()
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


def _one_day_race(name, fc_race_id, race_date, with_results):
    return Race(name=name, url="u", year=2026, stage_race=False,
                fc_race_id=fc_race_id, date=race_date,
                results=list(RESULT_ROW) if with_results else [])


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
# The Vuelta a Murcia 2026 shape: stage 2 weather-cancelled, and FirstCycling
# published no final GC at all — race.results stays empty while every stage
# carries a date months in the past.
GCLESS_SETTLED = [_stage("Stage: 01", LONG_AGO, True),
                  _stage("Stage: 02", LONG_AGO, False)]


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


@pytest.mark.unit
def test_completed_race_with_cancelled_past_dated_stage_is_not_stale(tmp_path):
    # Same, but the cancelled stage carries its (past) scheduled date — the
    # final GC posting settles the race either way.
    stages = COMPLETE + [_stage("Stage: 03", YESTERDAY, False)]
    tour = _tour_dir_with(tmp_path, _stage_race("Storm", 4, stages, gc_results=True))
    assert create_to_scrape_list_tour(str(tour)) == []
    assert (tour / "Storm.pkl").exists()


@pytest.mark.unit
def test_gcless_settled_race_with_cancelled_stage_is_not_stale(tmp_path):
    # Vuelta a Murcia 2026: no final GC exists anywhere, but every stage is
    # dated and the race concluded well past the posting grace.
    tour = _tour_dir_with(tmp_path, _stage_race("Murcia", 74, GCLESS_SETTLED))
    assert create_to_scrape_list_tour(str(tour)) == []
    assert (tour / "Murcia.pkl").exists()


@pytest.mark.unit
def test_gcless_recently_finished_race_is_still_stale(tmp_path):
    # Result-less stage inside the posting grace with no GC: results may
    # simply not be up yet — keep re-scraping.
    stages = [_stage("Stage: 01", YESTERDAY, True),
              _stage("Stage: 02", YESTERDAY, False)]
    tour = _tour_dir_with(tmp_path, _stage_race("Fresh", 5, stages))
    assert create_to_scrape_list_tour(str(tour)) == [("Fresh", "u")]


@pytest.mark.unit
def test_completed_oneday_race_is_not_stale(tmp_path):
    tour = _tour_dir_with(tmp_path, _one_day_race("Classic", 6, YESTERDAY, True))
    assert create_to_scrape_list_tour(str(tour)) == []
    assert (tour / "Classic.pkl").exists()


@pytest.mark.unit
def test_resultless_oneday_race_within_grace_is_still_stale(tmp_path):
    # Raced yesterday, results not up yet — keep re-scraping.
    tour = _tour_dir_with(tmp_path, _one_day_race("Waiting", 7, YESTERDAY, False))
    assert create_to_scrape_list_tour(str(tour)) == [("Waiting", "u")]
    assert not (tour / "Waiting.pkl").exists()


@pytest.mark.unit
def test_resultless_oneday_race_past_grace_is_not_stale(tmp_path):
    # The Duo Normand shape: a one-day race FirstCycling will never post
    # results for (weather-cancelled). Marking its legacy empty pickle stale
    # deleted + re-fetched it on every run over the folder.
    tour = _tour_dir_with(tmp_path, _one_day_race("Cancelled", 8, LONG_AGO, False))
    assert create_to_scrape_list_tour(str(tour)) == []
    assert (tour / "Cancelled.pkl").exists()


@pytest.mark.unit
def test_resultless_undated_oneday_race_is_not_stale(tmp_path):
    # No parseable date: can't tell past from future — leave it alone
    # (pre-fix behavior, preserved).
    tour = _tour_dir_with(tmp_path, _one_day_race("Undated", 9, None, False))
    assert create_to_scrape_list_tour(str(tour)) == []


@pytest.mark.unit
def test_dotted_race_name_with_complete_pickle_is_not_rescraped(tmp_path):
    # Stems came from split('.'), so "Kamp. van Vlaanderen.pkl" registered
    # as "Kamp" — never matching its races.txt entry — and the race was
    # re-scraped on every run over its folder despite the complete pickle.
    tour = _tour_dir_with(
        tmp_path, _one_day_race("Kamp. van Vlaanderen", 10, YESTERDAY, True))
    assert create_to_scrape_list_tour(str(tour)) == []
    assert (tour / "Kamp. van Vlaanderen.pkl").exists()


@pytest.mark.unit
def test_multidot_race_name_with_complete_pickle_is_not_rescraped(tmp_path):
    # Only the final ".pkl" may be stripped: "Pro Ötztaler 5.500" must
    # survive stem derivation whole, dots and all.
    tour = _tour_dir_with(
        tmp_path, _one_day_race("Pro Ötztaler 5.500", 11, YESTERDAY, True))
    assert create_to_scrape_list_tour(str(tour)) == []
    assert (tour / "Pro Ötztaler 5.500.pkl").exists()


@pytest.mark.unit
def test_dotted_race_name_stale_pickle_is_still_detected(tmp_path):
    # The staleness loop opened "<stem>.pkl" ("Mem.pkl"), which doesn't
    # exist, so dotted-name pickles were never staleness-checked ("Error
    # checking pkl" warning every run). The deletion proves the loop now
    # opens the real dotted filename: raced yesterday, no results yet —
    # stale, so re-scrape and drop the pickle.
    tour = _tour_dir_with(
        tmp_path, _one_day_race("Mem. Van Steenbergen", 12, YESTERDAY, False))
    assert create_to_scrape_list_tour(str(tour)) == [("Mem. Van Steenbergen", "u")]
    assert not (tour / "Mem. Van Steenbergen.pkl").exists()


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


_SCHEMA = """
    CREATE TABLE IF NOT EXISTS races (
        id INTEGER PRIMARY KEY, fc_race_id TEXT, year INT, category TEXT);
    CREATE TABLE IF NOT EXISTS competitions (
        id INTEGER PRIMARY KEY, race_id INT, competition_type TEXT, date TEXT);
    CREATE TABLE IF NOT EXISTS rider_results (
        id INTEGER PRIMARY KEY, competition_id INT);
"""


def _seed_db(db_path, fc_race_id, n_result_stages, with_gc, n_empty_stages=0):
    conn = sqlite3.connect(db_path)
    conn.executescript(_SCHEMA)
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


# ---------------------------------------------------------------------------
# Incomplete-race detection (delete + re-migrate trigger)
# ---------------------------------------------------------------------------

def _seed_race_comps(db_path, fc_race_id, comps):
    """Insert one race with explicit competitions: (type, date, n_results)."""
    conn = sqlite3.connect(db_path)
    conn.executescript(_SCHEMA)
    cur = conn.execute(
        "INSERT INTO races (fc_race_id, year, category) VALUES (?, 2026, 'wt')",
        (str(fc_race_id),))
    race_id = cur.lastrowid
    for comp_type, comp_date, n_results in comps:
        c = conn.execute(
            "INSERT INTO competitions (race_id, competition_type, date) "
            "VALUES (?, ?, ?)",
            (race_id, comp_type, comp_date)).lastrowid
        for _ in range(n_results):
            conn.execute(
                "INSERT INTO rider_results (competition_id) VALUES (?)", (c,))
    conn.commit()
    conn.close()


@pytest.mark.unit
def test_cancelled_stage_with_final_gc_is_not_incomplete(tmp_path):
    db = str(tmp_path / "t.db")
    _seed_race_comps(db, 4, [("stage", LONG_AGO, 5), ("stage", LONG_AGO, 0),
                             ("gc", LONG_AGO, 5)])
    assert _get_incomplete_race_keys(db, [2026]) == set()


@pytest.mark.unit
def test_cancelled_stage_in_gcless_settled_race_is_not_incomplete(tmp_path):
    # The DB image of Vuelta a Murcia 2026: no gc competition exists because
    # FirstCycling never published one, and stage 2 is a zero-result comp
    # with a long-past date. Flagging it deleted + re-migrated the race every
    # pipeline run, churning competition ids with no data change.
    db = str(tmp_path / "t.db")
    _seed_race_comps(db, 74, [("stage", LONG_AGO, 5), ("stage", LONG_AGO, 0)])
    assert _get_incomplete_race_keys(db, [2026]) == set()


@pytest.mark.unit
def test_midrace_race_with_unraced_stages_is_still_incomplete(tmp_path):
    # Mid-race: unraced stages migrate as empty comps that are undated or
    # future-dated and no gc comp exists yet — must keep re-migrating.
    db = str(tmp_path / "t.db")
    _seed_race_comps(db, 17, [("stage", YESTERDAY, 5), ("stage", None, 0),
                              ("stage", TOMORROW, 0)])
    assert _get_incomplete_race_keys(db, [2026]) == {("17", 2026, "wt")}


@pytest.mark.unit
def test_gcless_empty_stage_within_grace_is_still_incomplete(tmp_path):
    # Race just ended, no GC yet, one stage result-less: results may merely
    # not be posted — keep flagging until the grace passes.
    db = str(tmp_path / "t.db")
    _seed_race_comps(db, 5, [("stage", YESTERDAY, 5), ("stage", YESTERDAY, 0)])
    assert _get_incomplete_race_keys(db, [2026]) == {("5", 2026, "wt")}


@pytest.mark.unit
def test_race_without_competitions_is_incomplete(tmp_path):
    db = str(tmp_path / "t.db")
    conn = sqlite3.connect(db)
    conn.executescript(_SCHEMA)
    conn.execute(
        "INSERT INTO races (fc_race_id, year, category) VALUES ('9', 2026, 'wt')")
    conn.commit()
    conn.close()
    assert _get_incomplete_race_keys(db, [2026]) == {("9", 2026, "wt")}
