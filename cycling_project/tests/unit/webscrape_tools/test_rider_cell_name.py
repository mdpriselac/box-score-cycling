"""Rider names in result rows after FirstCycling's 2026-10 redesign.

The rider cell gained a mobile-only <span class="m-team"> after the link, and the
parser read the whole cell: "Seixas Paul Decathlon CMA CGM".
"""

import pytest
from bs4 import BeautifulSoup

from cycling_project.webscrape_tools.get_race_results import parse_rider_row

pytestmark = pytest.mark.unit

ORDER = {"pos": 0, "rider": 1, "team": 2, "time": 3}


def row(rider_cell: str) -> BeautifulSoup:
    html = (f"<table><tr><td>1</td>{rider_cell}"
            "<td><a href='team.php?l=40474'>Decathlon CMA CGM</a></td><td>5:49:28</td></tr></table>")
    return BeautifulSoup(html, "html.parser").find("tr")


def test_name_excludes_mobile_team_span():
    cell = ("<td class='fc-ellipsis'><span class='flag flag-fr'></span>"
            "<a href='rider.php?r=199233&amp;y=2026' title='Paul Seixas'>"
            "<span class='surname'>Seixas</span> Paul</a>"
            "<span class='m-team'>Decathlon CMA CGM</span></td>")
    out = parse_rider_row(row(cell), ORDER)
    assert out["name"] == "Seixas Paul" and out["rider_id"] == "199233"


def test_old_markup_name_unchanged():
    cell = "<td><span class='flag flag-fr'></span><a href='rider.php?r=199233&amp;y=2026'>Seixas Paul</a></td>"
    assert parse_rider_row(row(cell), ORDER)["name"] == "Seixas Paul"
