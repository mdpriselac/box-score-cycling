"""
Test configuration for pytest.
Includes common fixtures used by multiple tests.
"""
import os
import pytest
import logging
from pathlib import Path

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