"""
Test fixtures for webscrape_tools tests.
"""
import os
import pytest
from pathlib import Path

from tests.utils.mock_responses import MockWebClient, MockResponse


@pytest.fixture
def html_fixtures_dir(mock_ws_data_dir):
    """Path to the HTML test fixtures."""
    return mock_ws_data_dir / 'test_html'


@pytest.fixture
def mock_client(html_fixtures_dir):
    """
    Create a mock web client with pre-loaded responses.
    """
    client = MockWebClient(base_url="https://firstcycling.com")
    
    # Add race list page
    client.add_html_response(
        url="/race.php?y=2024&t=1",
        filepath=html_fixtures_dir / "race_list.html"
    )
    
    # Add race detail page
    client.add_html_response(
        url="/race.php?r=3001&y=2024",
        filepath=html_fixtures_dir / "race_detail.html"
    )
    
    # Add start list page
    client.add_html_response(
        url="/race.php?r=3001&y=2024&k=8",
        filepath=html_fixtures_dir / "start_list.html"
    )
    
    return client


@pytest.fixture
def sample_race_list_soup(html_fixtures_dir):
    """
    Create a BeautifulSoup object from the race list HTML.
    """
    from bs4 import BeautifulSoup
    
    with open(html_fixtures_dir / "race_list.html", 'r', encoding='utf-8') as f:
        return BeautifulSoup(f.read(), 'html.parser')


@pytest.fixture
def sample_race_detail_soup(html_fixtures_dir):
    """
    Create a BeautifulSoup object from the race detail HTML.
    """
    from bs4 import BeautifulSoup
    
    with open(html_fixtures_dir / "race_detail.html", 'r', encoding='utf-8') as f:
        return BeautifulSoup(f.read(), 'html.parser')


@pytest.fixture
def sample_start_list_soup(html_fixtures_dir):
    """
    Create a BeautifulSoup object from the start list HTML.
    """
    from bs4 import BeautifulSoup
    
    with open(html_fixtures_dir / "start_list.html", 'r', encoding='utf-8') as f:
        return BeautifulSoup(f.read(), 'html.parser')


@pytest.fixture
def temp_db_path(tmp_path):
    """
    Create a temporary directory for database files.
    """
    db_path = tmp_path / "test_db"
    db_path.mkdir()
    return str(db_path)