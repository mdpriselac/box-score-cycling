"""
Test configuration for pytest.
Includes common fixtures used by multiple tests.
"""
import os
import pytest
import logging
from pathlib import Path

# Tests must never inherit the opt-in browser backend from the project's .env.
# Set this before test modules import; python-dotenv will then preserve it.
os.environ["SCRAPER_USE_BROWSER"] = "0"

# Disable logging during tests by default
logging.basicConfig(level=logging.CRITICAL)

@pytest.fixture
def test_data_dir():
    """
    Returns the path to the test data directory.
    """
    return Path(__file__).parent / "fixtures"

@pytest.fixture
def mock_ws_data_dir(test_data_dir):
    """
    Returns the path to webscrape test data directory.
    """
    return test_data_dir / "webscrape_tools"


@pytest.fixture
def html_fixtures_dir(mock_ws_data_dir):
    """Path to the saved web-scraper HTML fixtures."""
    return mock_ws_data_dir / "test_html"


@pytest.fixture
def mock_client(html_fixtures_dir):
    """Create a mock web client with pre-loaded FirstCycling responses."""
    from cycling_project.tests.utils.mock_responses import MockWebClient

    client = MockWebClient(base_url="https://firstcycling.com")
    client.add_html_response(
        url="/race.php?y=2024&t=1",
        filepath=html_fixtures_dir / "race_list.html",
    )
    client.add_html_response(
        url="/race.php?r=3001&y=2024",
        filepath=html_fixtures_dir / "race_detail.html",
    )
    client.add_html_response(
        url="/race.php?r=3001&y=2024&k=8",
        filepath=html_fixtures_dir / "start_list.html",
    )
    return client


def _fixture_soup(html_fixtures_dir, filename):
    from bs4 import BeautifulSoup

    return BeautifulSoup(
        (html_fixtures_dir / filename).read_text(encoding="utf-8"),
        "html.parser",
    )


@pytest.fixture
def sample_race_list_soup(html_fixtures_dir):
    return _fixture_soup(html_fixtures_dir, "race_list.html")


@pytest.fixture
def sample_race_detail_soup(html_fixtures_dir):
    return _fixture_soup(html_fixtures_dir, "race_detail.html")


@pytest.fixture
def sample_start_list_soup(html_fixtures_dir):
    return _fixture_soup(html_fixtures_dir, "start_list.html")


@pytest.fixture
def temp_db_path(tmp_path):
    """Create a temporary directory for scraper output."""
    db_path = tmp_path / "test_db"
    db_path.mkdir()
    return str(db_path)
