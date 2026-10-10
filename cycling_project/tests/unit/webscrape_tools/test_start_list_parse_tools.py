"""
Unit tests for the start_list_parse_tools module.
"""
import pytest
from bs4 import BeautifulSoup

from cycling_project.webscrape_tools.start_list_parse_tools import (
    extract_rider_id,
    extract_team_id,
    parse_start_list,
    Rider,
    Team
)


def test_extract_rider_id():
    """Test extracting rider ID from href."""
    # Test valid href
    assert extract_rider_id("rider.php?r=1234&y=2024") == "1234"
    
    # Test with different format but valid
    assert extract_rider_id("rider.php?y=2024&r=5678") == "5678"
    
    # Test invalid href
    assert extract_rider_id("rider.php?id=1234") is None
    
    # Test None input
    assert extract_rider_id(None) is None


def test_extract_team_id():
    """Test extracting team ID from href."""
    # Test valid href
    assert extract_team_id("team.php?l=42") == "42"
    
    # Test with different format but valid
    assert extract_team_id("team.php?year=2024&l=99") == "99"
    
    # Test invalid href
    assert extract_team_id("team.php?id=42") is None
    
    # Test None input
    assert extract_team_id(None) is None


def test_parse_start_list(sample_start_list_soup):
    """Test parsing a start list from HTML."""
    # Convert BeautifulSoup to HTML string for testing
    html_content = str(sample_start_list_soup)
    
    # Parse the start list
    teams = parse_start_list(html_content)
    
    # Check number of teams
    assert len(teams) == 2
    
    # Check first team
    team1 = teams[0]
    assert team1.name == "Team X"
    assert team1.team_id == "1"
    assert len(team1.riders) == 3
    
    # Check first rider in first team
    rider1 = team1.riders[0]
    assert rider1.name == "Rider A"
    assert rider1.rider_id == "1001"
    assert rider1.number == "1"
    assert rider1.team_name == "Team X"
    assert rider1.team_id == "1"


def test_parse_start_list_empty():
    """Test parsing an empty start list."""
    html = "<html><body><div id='wrapper'></div></body></html>"
    
    teams = parse_start_list(html)
    assert len(teams) == 0


def test_parse_start_list_missing_wrapper():
    """Test handling missing wrapper div."""
    html = "<html><body></body></html>"
    
    with pytest.raises(ValueError, match="Could not find wrapper div"):
        parse_start_list(html)


def test_rider_dataclass():
    """Test Rider dataclass creation and properties."""
    rider = Rider(
        name="Test Rider",
        rider_id="1234",
        number="42",
        team_name="Test Team",
        team_id="99"
    )
    
    assert rider.name == "Test Rider"
    assert rider.rider_id == "1234"
    assert rider.number == "42"
    assert rider.team_name == "Test Team"
    assert rider.team_id == "99"


def test_team_dataclass():
    """Test Team dataclass creation and properties."""
    riders = [
        Rider(name="Rider 1", rider_id="1", number="1", team_name="Test Team", team_id="1"),
        Rider(name="Rider 2", rider_id="2", number="2", team_name="Test Team", team_id="1")
    ]
    
    team = Team(
        name="Test Team",
        team_id="1",
        riders=riders
    )
    
    assert team.name == "Test Team"
    assert team.team_id == "1"
    assert len(team.riders) == 2
    assert team.riders[0].name == "Rider 1"
    assert team.riders[1].name == "Rider 2"

START_GRID_HTML = """
<html><body><div class="start-grid">
<div class="start-team"><div class="start-team-head"><span class="fc-ellipsis">
<a href="team.php?l=25778" title="UAE Team Emirates-XRG">UAE Team Emirates-XRG</a></span></div>
<table class="fc-table rider-table"><tbody>
<tr class="fc-filter-row"><td class="center is-muted">1</td>
<td class="fc-ellipsis"><span class="flag flag-us"></span><a href="rider.php?r=48539&amp;y=2026"><span class="surname">McNulty</span> Brandon</a></td></tr>
<tr class="fc-filter-row"><td class="center is-muted">3</td>
<td class="fc-ellipsis"><a href="rider.php?r=155993&amp;y=2026"><span class="surname">del Toro</span> Isaac</a></td></tr>
</tbody></table></div>
<div class="start-team"><div class="start-team-head"><a href="team.php?l=7">Team Y</a></div>
<table class="rider-table"><tbody>
<tr><td>11</td><td><a href="rider.php?r=42&amp;y=2026"><span class="surname">Rider</span> B</a></td></tr>
</tbody></table></div>
</div></body></html>
"""


def test_parse_start_list_start_grid_layout():
    """FirstCycling's 2026-10 redesign (div.start-grid / div.start-team) parses like the old layout."""
    teams = parse_start_list(START_GRID_HTML)
    assert [t.name for t in teams] == ["UAE Team Emirates-XRG", "Team Y"]
    assert teams[0].team_id == "25778"
    assert [(r.number, r.name, r.rider_id) for r in teams[0].riders] == [
        ("1", "McNulty Brandon", "48539"), ("3", "del Toro Isaac", "155993")]
    assert teams[1].riders[0].team_name == "Team Y"
