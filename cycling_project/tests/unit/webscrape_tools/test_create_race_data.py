"""
Unit tests for the create_race_data module.
"""
import pytest
from unittest.mock import patch, MagicMock
import re
from bs4 import BeautifulSoup

from cycling_project.webscrape_tools.create_race_data import (
    Race,
    Stage,
    find_stage_selector,
    extract_stages_with_links
)


def test_find_stage_selector_with_id(sample_race_detail_soup):
    """Test finding stage selector with stageSelect ID."""
    selector = find_stage_selector(sample_race_detail_soup)
    
    # Should find the select with id="stageSelect"
    assert selector is not None
    assert selector.get('id') == 'stageSelect'


def test_find_stage_selector_with_option_text():
    """Test finding stage selector by option text content."""
    from bs4 import BeautifulSoup
    
    # Create soup with select that has option containing "Stage:" text
    html = """
    <select>
        <option value="1">Stage: 1</option>
        <option value="2">Stage: 2</option>
    </select>
    """
    soup = BeautifulSoup(html, 'html.parser')
    
    selector = find_stage_selector(soup)
    assert selector is not None
    assert selector.name == 'select'


def test_find_stage_selector_not_found():
    """Test behavior when no stage selector is found."""
    from bs4 import BeautifulSoup
    
    # Create soup with no matching select
    html = "<div>No select here</div>"
    soup = BeautifulSoup(html, 'html.parser')
    
    selector = find_stage_selector(soup)
    assert selector is None


def test_extract_stages_with_links(sample_race_detail_soup):
    """Test extracting stages and their links."""
    stages = extract_stages_with_links(sample_race_detail_soup)
    
    # Should extract 4 stages (3 regular stages + GC)
    assert len(stages) == 4
    
    # Check format of extracted data
    assert "Stage: 1" in stages
    assert stages["Stage: 1"] == "1"
    assert "GC" in stages
    assert stages["GC"] == "0"


def test_extract_stages_with_links_not_found():
    """Test behavior when no stages are found."""
    from bs4 import BeautifulSoup
    
    # Create soup with no stage select
    html = "<div>No stages here</div>"
    soup = BeautifulSoup(html, 'html.parser')
    
    stages = extract_stages_with_links(soup)
    assert stages is None


def test_race_extract_race_identifiers():
    """Test extracting race ID and year from URL."""
    race = Race(
        name="Test Race",
        url="https://firstcycling.com/race.php?r=123&y=2024"
    )
    
    with patch.object(Race, '_fetch_race_page'), \
         patch.object(Race, '_extract_race_data'), \
         patch.object(Race, '_find_stages', return_value=None), \
         patch.object(Race, '_process_one_day_race'):
        
        # Call populate_race to trigger _extract_race_identifiers
        race.populate_race()
    
    # Check that IDs were extracted correctly
    assert race.fc_race_id == "123"
    assert race.year == 2024


def test_race_extract_race_identifiers_invalid():
    """Test behavior with invalid URL."""
    race = Race(
        name="Invalid Race",
        url="https://firstcycling.com/invalid"
    )
    
    with patch('cycling_project.webscrape_tools.create_race_data.WebClient'):
        # Should raise ValueError due to missing race ID and year
        with pytest.raises(ValueError, match="Could not extract race ID or year"):
            race.populate_race()


def test_race_process_one_day_race():
    """Test processing a one-day race."""
    race = Race(
        name="One Day Race",
        url="https://firstcycling.com/race.php?r=123&y=2024"
    )
    
    # Create mock soup
    mock_soup = MagicMock()
    
    with patch('cycling_project.webscrape_tools.get_race_results.extract_race_date', 
               return_value="2024-03-01") as mock_extract_date:
        
        # Process one-day race
        race._process_one_day_race(mock_soup)
        
        # Check date was extracted
        assert race.date == "2024-03-01"
        mock_extract_date.assert_called_once_with(mock_soup)


def test_race_create_stage():
    """Test creating a stage object from parent race."""
    race = Race(
        name="Stage Race",
        url="https://firstcycling.com/race.php?r=123&y=2024",
        fc_race_id="123",
        year=2024,
        category="UWT"
    )
    
    # Create stage
    stage = race._create_stage(
        stage_name="Stage 1",
        stage_url="https://firstcycling.com/race.php?r=123&y=2024&e=1"
    )
    
    # Check stage properties
    assert stage.name == "Stage 1"
    assert stage.url == "https://firstcycling.com/race.php?r=123&y=2024&e=1"
    assert stage.race == "Stage Race"
    assert stage.fc_race_id == "123"
    assert stage.year == 2024
    assert stage.category == "UWT"