"""
Integration tests for the webscrape_tools package.
"""
import pytest
import os
import tempfile
from pathlib import Path

from cycling_project.webscrape_tools.find_races import create_race_year_db
from cycling_project.webscrape_tools.create_race_data import Race
from cycling_project.webscrape_tools.get_startlist import get_start_list


@pytest.mark.integration
def test_race_scraping_flow(mock_client, temp_db_path):
    """
    Test the entire race scraping flow from finding races to populating race data.
    
    This test uses mock HTTP responses instead of making real network requests.
    """
    # Patch the WebClient to use our mock client
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr('cycling_project.webscrape_tools.find_races.WebClient', 
                  lambda base_url: mock_client)
        mp.setattr('cycling_project.webscrape_tools.create_race_data.WebClient', 
                  lambda base_url: mock_client)
        
        # Step 1: Create race database
        create_race_year_db(year="2024", race_data_dir=temp_db_path)
        
        # Verify directories and files were created
        year_dir = os.path.join(temp_db_path, "2024")
        wt_file = os.path.join(year_dir, "wt", "wt.txt")
        
        assert os.path.exists(wt_file)
        
        # Step 2: Read race list and create Race object
        with open(wt_file, 'r') as f:
            first_line = f.readline().strip()
            race_name, race_url = first_line.split(',')
        
        # Create and populate race
        race = Race(name=race_name, url=race_url)
        race.populate_race()
        
        # Verify race data
        assert race.name == "Test Race 1"
        assert race.fc_race_id == "3001"
        assert race.year == 2024
        assert race.stage_race is True
        assert len(race.stages) == 4  # 3 stages + GC


@pytest.mark.integration
def test_startlist_scraping(mock_client):
    """
    Test the start list scraping functionality.
    
    This test uses mock HTTP responses instead of making real network requests.
    """
    # Patch the WebClient to use our mock client
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr('cycling_project.webscrape_tools.get_startlist.WebClient', 
                  lambda base_url: mock_client)
        
        # Get start list
        teams = get_start_list(race_id=3001, year=2024)
        
        # Verify teams were extracted
        assert len(teams) == 2
        
        # Check first team
        assert teams[0].name == "Team X"
        assert teams[0].team_id == "1"
        assert len(teams[0].riders) == 3
        
        # Check first rider in first team
        rider = teams[0].riders[0]
        assert rider.name == "Rider A"
        assert rider.rider_id == "1001"
        assert rider.number == "1"
        assert rider.team_name == "Team X"