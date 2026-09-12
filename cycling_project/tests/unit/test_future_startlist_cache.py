import sqlite3

import pytest

from cycling_project.prediction_tools import future_race_loader as loader
from cycling_project.webscrape_tools.start_list_parse_tools import Rider, Team


def field(ids):
    riders = [
        Rider(name=f"Rider {rider_id}", rider_id=str(rider_id), number=str(i),
              team_name="Test Team", team_id="10")
        for i, rider_id in enumerate(ids, 1)
    ]
    return [Team(name="Test Team", team_id="10", riders=riders)]


def test_incomplete_or_unlinked_startlist_is_not_cached(tmp_path):
    db = tmp_path / "cache.db"
    with pytest.raises(ValueError, match="Incomplete start list"):
        loader.save_start_list_to_cache(242, 2026, field(range(1, 4)), str(db))

    bad = field(range(1, 21))
    bad[0].riders[-1].rider_id = None
    with pytest.raises(ValueError, match="without FirstCycling ids"):
        loader.save_start_list_to_cache(242, 2026, bad, str(db))

    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM cached_start_lists").fetchone()[0] == 0


def test_refresh_replaces_preliminary_field_instead_of_retaining_withdrawals(tmp_path):
    db = tmp_path / "cache.db"
    loader.save_start_list_to_cache(58, 2026, field(range(1, 21)), str(db))
    loader.save_start_list_to_cache(58, 2026, field(range(2, 22)), str(db))

    with sqlite3.connect(db) as conn:
        ids = {row[0] for row in conn.execute(
            "SELECT rider_fc_id FROM cached_start_lists WHERE fc_race_id = '58' AND year = 2026"
        )}
    assert ids == {str(i) for i in range(2, 22)}


def test_scraper_rejects_firstcycling_team_shell(monkeypatch):
    shell = field(range(1, 4))
    monkeypatch.setattr(loader, "get_start_list", lambda race_id, year: shell)
    with pytest.raises(ValueError, match="No complete start list"):
        loader.scrape_startlist(242, 2026)
