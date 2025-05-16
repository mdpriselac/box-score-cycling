from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Tuple, Dict
from dataclasses import dataclass, field
import re
from random import randint
from time import sleep
from datetime import datetime

from cycling_project.webscrape_tools.scrape_client import WebClient
from cycling_project.webscrape_tools.get_race_results import extract_race_time, extract_results, extract_race_date
from cycling_project.webscrape_tools.logging_config import get_logger

# Configure logger
logger = get_logger("create_race_data")

# Constants
BASE_URL = "https://firstcycling.com"
DEFAULT_SLEEP_MIN = 1
DEFAULT_SLEEP_MAX = 3

@dataclass
class Stage:
    """Represents a stage of a cycling race with all relevant data."""
    name: str
    url: str
    fc_race_id: Optional[int] = None
    race: Optional[str] = None
    year: Optional[int] = None
    time: Optional[float] = None  # Legacy field, will be removed
    race_time: Optional[float] = None
    date: Optional[str] = None
    results: List[Dict] = field(default_factory=list)
    category: Optional[str] = None


@dataclass
class Race:
    """Represents a cycling race with all relevant data, including multiple stages if applicable."""
    name: str
    url: str
    year: Optional[int] = None
    date: Optional[datetime] = None
    category: Optional[str] = None
    stage_race: bool = False
    results: List[Dict] = field(default_factory=list)
    race_time: Optional[float] = None
    stages: List[Stage] = field(default_factory=list)
    fc_race_id: Optional[int] = None
    
    def populate_race(self) -> None:
        """
        Scrapes all data for this race from FirstCycling website.
        This includes race results and all stages if it's a stage race.
        """
        client = WebClient(BASE_URL)
        
        try:
            logger.info(f'Starting to scrape {self.name} at {self.url}')
            
            # Extract race ID and year from URL
            race_id, race_year = self._extract_race_identifiers()
            
            # Fetch and parse race page
            soup = self._fetch_race_page(client, race_id, race_year)
            
            # Extract basic race data
            self._extract_race_data(soup)
            
            # Process stages if this is a stage race
            stages = self._find_stages(soup)
            if stages:
                self._process_stage_race(client, stages, race_id, race_year)
            else:
                self._process_one_day_race(soup)
                
        except Exception as e:
            logger.error(f"Error processing {self.name}: {e}")
        finally:
            client.close()
    
    def _extract_race_identifiers(self) -> Tuple[str, str]:
        """Extract race ID and year from the race URL."""
        race_id_match = re.search(r'race.php\?r=(\d+)&', self.url)
        race_year_match = re.search(r'&y=(\d+)', self.url)
        
        if not race_id_match or not race_year_match:
            raise ValueError(f"Could not extract race ID or year from URL: {self.url}")
            
        race_id = race_id_match.group(1)
        race_year = race_year_match.group(1)
        
        self.fc_race_id = race_id
        try:
            self.year = int(race_year.strip())
        except ValueError:
            logger.warning(f"Error converting year to int for {self.name}")
            
        return race_id, race_year
    
    def _fetch_race_page(self, client: WebClient, race_id: str, race_year: str) -> BeautifulSoup:
        """Fetch and parse the race page."""
        clean_url = f"{BASE_URL}/race.php?r={race_id}&y={race_year}"
        response = client.get(clean_url)
        return BeautifulSoup(response.text, 'html.parser')
    
    def _extract_race_data(self, soup: BeautifulSoup) -> None:
        """Extract basic race data from the race page."""
        try:
            self.results = extract_results(soup)
        except Exception as e:
            logger.warning(f"Error finding results for {self.name}: {e}")
            
        try:
            self.race_time = extract_race_time(soup)
        except Exception as e:
            logger.warning(f"Error finding winning time for {self.name}: {e}")
    
    def _find_stages(self, soup: BeautifulSoup) -> Optional[Dict[str, str]]:
        """Find stages and their links if this is a stage race."""
        try:
            return extract_stages_with_links(soup)
        except Exception as e:
            logger.warning(f"Error finding stages for {self.name}: {e}")
            return None
    
    def _process_stage_race(self, client: WebClient, stages: Dict[str, str], 
                           race_id: str, race_year: str) -> None:
        """Process all stages for a stage race."""
        logger.info(f"Found {len(stages)} stages for {self.name}")
        self.stage_race = True
        self.stages = []
        
        for stage_name, stage_path in stages.items():
            stage_url = f"{BASE_URL}/race.php?r={race_id}&y={race_year}&e={stage_path.strip()}"
            logger.info(f"Starting to scrape {stage_name} at {stage_url}")
            
            # Create the stage object
            stage = self._create_stage(stage_name, stage_url)
            
            # Scrape stage data
            self._scrape_stage_data(client, stage)
            
            self.stages.append(stage)
            sleep(randint(DEFAULT_SLEEP_MIN, DEFAULT_SLEEP_MAX))
            
        logger.info(f"Finished scraping all stages for {self.name}")
    
    def _create_stage(self, stage_name: str, stage_url: str) -> Stage:
        """Create a new Stage object with basic info from parent race."""
        stage = Stage(name=stage_name, url=stage_url, race=self.name)
        # Inherit properties from parent race
        stage.category = self.category
        stage.year = self.year
        stage.fc_race_id = self.fc_race_id
        return stage
    
    def _scrape_stage_data(self, client: WebClient, stage: Stage) -> None:
        """Scrape data for a specific stage."""
        try:
            stage_resp = client.get(stage.url)
            stage_soup = BeautifulSoup(stage_resp.text, 'html.parser')
            
            try:
                stage.time = extract_race_time(stage_soup)
                stage.race_time = stage.time  # Set both for compatibility
            except Exception as e:
                logger.warning(f"Error finding winning time for {stage.name}: {e}")
                
            try:
                stage.results = extract_results(stage_soup)
            except Exception as e:
                logger.warning(f"Error finding results for {stage.name}: {e}")
                
            try:
                stage.date = extract_race_date(stage_soup)
            except Exception as e:
                logger.warning(f"Error finding date for {stage.name}: {e}")
                
        except Exception as e:
            logger.error(f"Error scraping stage {stage.name}: {e}")
    
    def _process_one_day_race(self, soup: BeautifulSoup) -> None:
        """Process a one-day race (no stages)."""
        logger.info(f"No stages found for {self.name}, one day race")
        try:
            self.date = extract_race_date(soup)
        except Exception as e:
            logger.warning(f"Error finding date for {self.name}: {e}")


def find_stage_selector(soup: BeautifulSoup) -> Optional[BeautifulSoup]:
    """
    Find the select element containing stage options.
    
    Args:
        soup: BeautifulSoup object of the race page
        
    Returns:
        BeautifulSoup select element or None if not found
    """
    # First look for the specific ID
    select = soup.find('select', id='stageSelect')
    if select:
        return select
    
    # Fall back to looking for Stage text in options
    for select in soup.find_all('select'):
        for option in select.find_all('option'):
            if 'Stage:' in option.text:
                return select
                
    return None


def extract_stages_with_links(soup: BeautifulSoup) -> Optional[Dict[str, str]]:
    """
    Extract all stages and their URLs from the race page.
    
    Args:
        soup: BeautifulSoup object of the race page
        
    Returns:
        Dictionary mapping stage names to their URL values, or None if no stages found
    """
    select = find_stage_selector(soup)
    if select is None:
        logger.info('No stages found for this race')
        return None
        
    options = select.find_all('option')
    return {option.text: option.get('value') for option in options}