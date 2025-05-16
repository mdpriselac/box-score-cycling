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