"""
Unit tests for the find_races module.
"""
import pytest
import os
from unittest.mock import patch, MagicMock

from cycling_project.webscrape_tools.find_races import (
    find_race_list_table,
    find_race_data_column,
    extract_races,
    create_race_year_db,
    _process_tour_level
)


def test_find_race_list_table(sample_race_list_soup):
    """Test finding the race list table in the page."""
    table = find_race_list_table(sample_race_list_soup)
    
    # Should find the table with Date, Cat, Race headers
    assert table is not None
    
    # Verify the table has the correct headers
    thead = table.find('thead')
    headers = [th.text.lower() for th in thead.find_all('th')]
    assert 'date' in headers
    assert 'cat' in headers
    assert 'race' in headers


def test_find_race_list_table_no_match():
    """Test handling of missing race list table."""
    from bs4 import BeautifulSoup
    
    # Create soup with no matching table
    html = "<html><body><table><tr><th>No Match</th></tr></table></body></html>"
    soup = BeautifulSoup(html, 'html.parser')
    
    table = find_race_list_table(soup)
    assert table is None


def test_find_race_data_column(sample_race_list_soup):
    """Test finding the race data column in the table."""
    table = find_race_list_table(sample_race_list_soup)
    col_index = find_race_data_column(table)
    
    # The race column should be found (column index 2 in our test HTML)
    assert col_index == 2


def test_find_race_data_column_no_thead():
    """Test handling missing thead in table."""
    from bs4 import BeautifulSoup
    
    # Create table with no thead
    html = "<table><tbody><tr><td>No thead</td></tr></tbody></table>"
    soup = BeautifulSoup(html, 'html.parser')
    
    col_index = find_race_data_column(soup)
    assert col_index is None


def test_extract_races(sample_race_list_soup):
    """Test extracting races from the page."""
    races = extract_races(sample_race_list_soup)
    
    # Should extract 3 races from our test HTML
    assert len(races) == 3
    
    # Check format of extracted data
    race_name, race_url = races[0]
    assert race_name == "Test Race 1"
    assert "race.php?r=3001&y=2024" in race_url


def test_extract_races_no_table():
    """Test extracting races with no table found."""
    from bs4 import BeautifulSoup
    
    # Create soup with no matching table
    html = "<html><body><div>No table here</div></body></html>"
    soup = BeautifulSoup(html, 'html.parser')
    
    races = extract_races(soup)
    assert races is None


@pytest.mark.parametrize("tour_name, filename", [
    ("World Tour", "wt.txt"),
    (".Pro", "pro.txt"),
    (".1", "d1.txt")
])
def test_process_tour_level(tour_name, filename, mock_client, temp_db_path):
    """Test processing of an individual tour level."""
    # Create a year directory in the temp path
    year_dir = os.path.join(temp_db_path, "2024")
    tour_dir = os.path.join(year_dir, filename.split('.')[0])
    os.makedirs(tour_dir, exist_ok=True)
    
    # Process a tour level
    _process_tour_level(
        client=mock_client,
        year="2024",
        tour_name=tour_name,
        tour_url="/race.php?y=2024&t=1",  # All use same mock response
        tour_dir=tour_dir,
        filename=filename
    )
    
    # Check that output file was created
    output_file = os.path.join(tour_dir, filename)
    assert os.path.exists(output_file)
    
    # Check file contents
    with open(output_file, 'r') as f:
        lines = f.readlines()
        assert len(lines) == 3  # 3 races in our test data
        
        # Check format of first line
        assert "Test Race 1,https://firstcycling.com/race.php?r=3001&y=2024" in lines[0]


@patch('cycling_project.webscrape_tools.find_races._process_tour_level')
def test_create_race_year_db(mock_process, temp_db_path):
    """Test creating the race year database."""
    with patch('cycling_project.webscrape_tools.find_races.WebClient') as MockClient:
        # Set up mock client
        mock_client_instance = MagicMock()
        MockClient.return_value = mock_client_instance
        
        # Call function
        create_race_year_db(year="2024", race_data_dir=temp_db_path)
        
        # Check directories were created
        year_dir = os.path.join(temp_db_path, "2024")
        assert os.path.exists(year_dir)
        assert os.path.exists(os.path.join(year_dir, "wt"))
        assert os.path.exists(os.path.join(year_dir, "pro"))
        assert os.path.exists(os.path.join(year_dir, "d1"))
        
        # Check _process_tour_level was called 3 times (once per tour level)
        assert mock_process.call_count == 3
        
        # Check client was closed
        mock_client_instance.close.assert_called_once()