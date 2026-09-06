import json
from types import SimpleNamespace

from bs4 import BeautifulSoup

from cycling_project.webscrape_tools.find_races import (
    _process_tour_level_by_months,
    extract_calendar_rows,
    parse_calendar_dates,
)


def test_parse_calendar_single_and_range_dates():
    assert parse_calendar_dates("06.09", 2026) == ("2026-09-06", "2026-09-06")
    assert parse_calendar_dates("22.08 – 13.09", 2026) == ("2026-08-22", "2026-09-13")
    assert parse_calendar_dates("29.12-03.01", 2026) == ("2026-12-29", "2027-01-03")
    assert parse_calendar_dates("02 Mar", 2026) == ("2026-03-02", "2026-03-02")


def test_extract_calendar_rows_uses_existing_race_list_fixture(sample_race_list_soup):
    rows = extract_calendar_rows(sample_race_list_soup, 2024)
    assert rows[0] == {
        "fc_race_id": "3001",
        "name": "Test Race 1",
        "url": "https://firstcycling.com/race.php?r=3001&y=2024",
        "start_date": "2024-03-02",
        "end_date": "2024-03-02",
        "calendar_category": "1.UWT",
        "is_stage_race": False,
        "country": None,
    }


def test_month_scrape_keeps_txt_shape_and_writes_dated_sidecar(tmp_path, monkeypatch):
    html = """
      <table><thead><tr><th>Date</th><th>Cat</th><th>Race</th></tr></thead>
      <tbody><tr><td>10.09-12.09</td><td>2.Pro</td><td>
      <span class='flag' title='Spain'></span>
      <a href='race.php?r=99&y=2026' title='Test Tour'>Test Tour</a>
      </td></tr></tbody></table>
    """

    class Client:
        def get(self, _url):
            return SimpleNamespace(text=html)

    monkeypatch.setattr("cycling_project.webscrape_tools.find_races.sleep", lambda _n: None)
    tour_dir = tmp_path / "pro"
    tour_dir.mkdir()
    _process_tour_level_by_months(
        Client(), "2026", ".Pro", 21, str(tour_dir), "pro.txt", [9]
    )

    assert (tour_dir / "pro.txt").read_text() == (
        "Test Tour,https://firstcycling.com/race.php?r=99&y=2026\n"
    )
    rows = json.loads((tour_dir / "pro.calendar.json").read_text())
    assert rows[0]["start_date"] == "2026-09-10"
    assert rows[0]["end_date"] == "2026-09-12"
    assert rows[0]["country"] == "Spain"
    assert rows[0]["is_stage_race"] is True


def test_row_country_falls_back_to_flag_class():
    from bs4 import BeautifulSoup
    from cycling_project.webscrape_tools.find_races import _row_country
    live = BeautifulSoup('<tr><td><span class="flag flag-es"></span> Vuelta</td></tr>', "html.parser").tr
    old = BeautifulSoup('<tr><td><span class="flag be"></span> Omloop</td></tr>', "html.parser").tr
    titled = BeautifulSoup('<tr><td><img class="flag" title="Italy"></td></tr>', "html.parser").tr
    assert _row_country(live) == "es" and _row_country(old) == "be" and _row_country(titled) == "Italy"
