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


# --- Public copy -----------------------------------------------------------------------------
# Some driver tests replay a real night: they fetch the Vuelta 2026 results from uci.org and
# check the pages the site builders wrote. They need the network, and one needs the published
# site pages, which stay out of the public repository. They are skipped with the reason
# stated; set RUN_NETWORK_TESTS=1 to run the network ones.
_DRIVER = "cycling_project/tests/unit/test_nightly_driver.py::"
NEEDS_NETWORK = tuple(_DRIVER + name for name in (
    "test_night_dry_run_replays_stage_14_to_15",
    "test_an_agent_key_saved_in_the_readers_raw_shape_still_prices",
    "test_preview_without_a_key_exits_10_day_key_needed",
    "test_preview_uses_an_approved_store_key_or_an_agent_key",
    "test_an_agent_record_beside_the_config_keys_the_board_without_the_flag",
    "test_an_approved_human_key_still_wins_over_an_agent_record",
    "test_no_key_at_all_still_exits_10",
    "test_the_inbox_clears_a_day_key_ask_once_the_step_succeeds",
    "test_phase_is_idempotent_and_never_invokes_git",
    "test_pages_the_builders_wrote_are_staged",
    "test_a_page_the_builder_did_not_write_fails_the_run_as_page_missing",
    "test_a_gc_page_missing_after_an_ok_tracker_step_is_page_missing",
    "test_another_campaigns_page_in_the_staging_set_is_page_foreign",
))
NEEDS_PUBLISHED_PAGES = (_DRIVER + "test_settle_without_pre_race_boards_is_retrospective_only",)


def pytest_collection_modifyitems(config, items):
    network = pytest.mark.skip(reason="fetches results from uci.org; set RUN_NETWORK_TESTS=1 to run")
    pages = pytest.mark.skip(reason="needs the published site pages, which are not in the public repository")
    for item in items:
        if not os.environ.get("RUN_NETWORK_TESTS") and item.nodeid.startswith(NEEDS_NETWORK):
            item.add_marker(network)
        if item.nodeid.startswith(NEEDS_PUBLISHED_PAGES):
            item.add_marker(pages)
