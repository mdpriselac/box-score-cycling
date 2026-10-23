"""
extract_race_date across FirstCycling's markup generations.

Covers the 2026-08 regression: the site replaced <div id='race'><h2>…</h2>
with a <div id='raceSub'> info line, which nulled every scraped stage date
(and, latently, the ordinal-suffix strip corrupted "August" -> "Augu",
nulling August race dates in every era).
"""

import pytest
from bs4 import BeautifulSoup

from cycling_project.webscrape_tools.get_race_results import extract_race_date

pytestmark = pytest.mark.unit


def soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(f"<html><body>{html}</body></html>", "html.parser")


class TestOldMarkup:
    def test_h2_in_race_div(self):
        s = soup("<div id='race'><h2>Stage 9 | 12th July 2026</h2></div>")
        assert extract_race_date(s) == "2026-07-12"

    def test_august_ordinal_bug_fixed(self):
        # 'August' contains 'st' — the old bare substitution made 'Augu'
        s = soup("<div id='race'><h2>23rd August 2025</h2></div>")
        assert extract_race_date(s) == "2025-08-23"

    def test_first_of_august(self):
        s = soup("<div id='race'><h2>1st August 2026</h2></div>")
        assert extract_race_date(s) == "2026-08-01"


class TestNewMarkup:
    def test_race_sub_stage_line(self):
        s = soup("<div id='raceName'>Tour de France</div>"
                 "<div id='raceSub'>Grand Tour, 9th stage, 12th July 2026, "
                 "France</div>")
        assert extract_race_date(s) == "2026-07-12"

    def test_race_sub_august(self):
        s = soup("<div id='raceSub'>Grand Tour, 1st stage, 22nd August 2026, "
                 "Spain</div>")
        assert extract_race_date(s) == "2026-08-22"

    def test_race_sub_one_day(self):
        s = soup("<div id='raceSub'>One-day race, 9th August 2026, Spain</div>")
        assert extract_race_date(s) == "2026-08-09"

    def test_race_page_range_yields_end_date(self):
        s = soup("<div id='raceSub'>Grand Tour, 4th -26th July 2026, "
                 "France</div>")
        assert extract_race_date(s) == "2026-07-26"

    def test_old_anchor_wins_when_both_present(self):
        s = soup("<div id='race'><h2>11th July 2026</h2></div>"
                 "<div id='raceSub'>Grand Tour, 9th stage, 12th July 2026, "
                 "France</div>")
        assert extract_race_date(s) == "2026-07-11"


class TestDegenerate:
    def test_no_container(self):
        assert extract_race_date(soup("<div>12th July 2026</div>")) is None

    def test_no_date_in_container(self):
        s = soup("<div id='raceSub'>Grand Tour, France</div>")
        assert extract_race_date(s) is None


class TestBannerMarkup2026_10:
    """2026-10 redesign: the date moved to <div class='team-banner-info'>."""

    def test_one_day_banner(self):
        s = soup("<div class='team-banner-text'><h1>2026 Il Lombardia</h1>"
                 "<div class='team-banner-info'>WorldTour · Monument · 10th October 2026 · Italy"
                 "<span class='team-banner-social'></span></div></div>")
        assert extract_race_date(s) == "2026-10-10"

    def test_stage_banner(self):
        s = soup("<div class='team-banner-info'>WorldTour · Stage race · 6th stage, 18th October 2026 · China</div>")
        assert extract_race_date(s) == "2026-10-18"
