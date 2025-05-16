#We can access top level tours by using the t input variable to the url
#y=year
#t=tour
#you can always but in t=1 and get redirected to the top level tour of that year
#t21 is the second level, currently the .Pro level

import os
from bs4 import BeautifulSoup
from time import sleep
from random import randint
from typing import List, Tuple, Optional

from cycling_project.webscrape_tools.scrape_client import WebClient
from cycling_project.webscrape_tools.logging_config import get_logger
from dotenv import load_dotenv

# Configure logger
logger = get_logger("find_races")

# Load environment variables
load_dotenv(dotenv_path='../env')
DB_PATH = os.getenv("DB_PATH")
logger.info(f"Database path: {DB_PATH}")

# Constants
BASE_URL = "https://firstcycling.com"
# Tour level IDs
WORLD_TOUR_ID = 1  # World Tour level, division 1, top level
PRO_TOUR_ID = 21   # .Pro level, division 2, second level
DOT_ONE_TOUR_ID = 22  # .1 level, division 3, third level

def find_race_list_table(soup: BeautifulSoup) -> Optional[BeautifulSoup]:
    """
    Finds the table from a soup object that contains race information for a year and tour level.
    
    Args:
        soup: BeautifulSoup object of a page
        
    Returns:
        BeautifulSoup table tag or None if not found
    """
    #Find the table that has a thead that has a tr that has th tags that have text containing Date, Cat, Race and Winner text
    tables = soup.find_all('table')
    for table in tables:
        thead = table.find('thead')
        if thead:
            ths = thead.find_all('th')
            date_found = False
            cat_found = False
            race_found = False
            #Check through the ths to see if they contain the text we want and mark the tracking bool true
            for th in ths:
                if 'date' in th.text.lower():
                    date_found = True
                if 'cat' in th.text.lower():
                    cat_found = True
                if 'race' in th.text.lower():
                    race_found = True
            #If all are found, return the table
            if date_found and cat_found and race_found:
                return table
            else:
                continue
        else:
            continue
    logger.warning("No Race table found for this page")
    return None

def find_race_data_column(table_tag: BeautifulSoup) -> Optional[int]:
    """
    Finds the index of the race data column in a table that has already been identified as listing races.
    
    Args:
        table_tag: BeautifulSoup table tag
        
    Returns:
        int the index of Race column in the table that has the race name and url, or None if not found
    """
    #In the thead tag, get the tr, and then find the th tag that has 'Race' in it, return its index
    thead = table_tag.find('thead')
    if not thead:
        logger.warning("No thead tag found in this table, can't find winner column")
        return None
        
    tr = thead.find('tr')
    ths = tr.find_all('th')
    for i, th in enumerate(ths):
        if 'race' in th.text.lower():
            return i
            
    logger.warning("No Race Column found in this table")
    return None

def extract_races(soup: BeautifulSoup) -> Optional[List[Tuple[str, str]]]:
    """
    Extracts a list of race names and urls from a soup object that contains a table of race information for a given year and tour level.
    
    Args:
        soup: BeautifulSoup object of a page
        
    Returns:
        List of tuples. The first element is a race name, the second element is the race webpage url.
        Returns None if race table or column not found.
    """
    #Find the key table
    race_table = find_race_list_table(soup)
    if race_table is None:
        logger.warning("No Race table found")
        return None
        
    #Get the race column index
    race_col_index = find_race_data_column(race_table)
    if race_col_index is None:
        logger.warning("No Race column found in the race table")
        return None
        
    #Get the rows of the table
    race_rows = race_table.find('tbody').find_all('tr')
    #Extract the data from the rows. We want race Name and URL. Both are in the a tag inside the td tag. The name is the title attribute, the url is the href
    races = []
    for row in race_rows:
        cols = row.find_all('td')
        race_col = cols[race_col_index]
        try:
            a_tag = race_col.find('a')
            race_name = a_tag.get('title')
            race_url = f"{BASE_URL}/{a_tag.get('href')}"
            races.append((race_name, race_url))
        except Exception as e:
            logger.error(f"Error extracting race name and url: {e}")
            continue
            
    return races

def create_race_year_db(year: str, race_data_dir: str = DB_PATH) -> None:
    """
    Creates a directory structure for a given year and saves a list of races and their webpage urls for all three tour levels in that year. 
    Optionally you can specify the base directory where the directory structure will be created.
    
    Args:
        year: four digit year as a string
        race_data_dir: base directory where the year directory will be created. Default is the current directory.
        
    Returns:
        Nothing. However, it will create a subdirectory for the year. Within the year subdirectory 
        it will create 3 subdirectories, one for each tour level. Within each tour level subdirectory 
        it will create a text file. Each line in the text file will be a name and url for a race in 
        that year and tour level.
    """
    logger.info(f"Creating race database for {year}")
    
    #Check if there's a directory for the year, create it if not
    year_dir = os.path.join(race_data_dir, year)
    logger.debug(f"Year directory: {year_dir}")
    
    if not os.path.exists(year_dir):
        os.makedirs(year_dir)
        logger.info(f"Created directory for year {year}")
        
    #Check if there are directories for wt, pro, and d1 divisions, create them if not
    wt_dir = os.path.join(year_dir, 'wt')
    pro_dir = os.path.join(year_dir, 'pro')
    d1_dir = os.path.join(year_dir, 'd1')
    
    for dir_path, tour_name in [(wt_dir, 'World Tour'), (pro_dir, '.Pro'), (d1_dir, '.1')]:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
            logger.info(f"Created directory for {tour_name} races")
            
    #Get the top level tours for the year
    wt_url = f"{BASE_URL}/race.php?y={year}&t={WORLD_TOUR_ID}"
    pro_url = f"{BASE_URL}/race.php?y={year}&t={PRO_TOUR_ID}"
    d1_url = f"{BASE_URL}/race.php?y={year}&t={DOT_ONE_TOUR_ID}"
    
    client = WebClient(BASE_URL)
    
    try:
        # Process World Tour races
        _process_tour_level(client, year, "World Tour", wt_url, wt_dir, 'wt.txt')
        sleep(randint(1, 3))
        
        # Process .Pro races
        _process_tour_level(client, year, ".Pro", pro_url, pro_dir, 'pro.txt')
        sleep(randint(1, 3))
        
        # Process .1 races
        _process_tour_level(client, year, ".1", d1_url, d1_dir, 'd1.txt')
        
        logger.info(f"Finished getting all race lists for {year}")
    finally:
        client.close()

def _process_tour_level(client: WebClient, year: str, tour_name: str, tour_url: str, 
                        tour_dir: str, filename: str) -> None:
    """
    Process a specific tour level, extract races and save to file.
    
    Args:
        client: WebClient instance
        year: Year to process
        tour_name: Name of the tour level for logging
        tour_url: URL to fetch the tour data
        tour_dir: Directory to save the file
        filename: Name of the file to save the races
    """
    logger.info(f"Getting {tour_name} Race List for {year}")
    
    try:
        response = client.get(tour_url)
        soup = BeautifulSoup(response.text, 'html.parser')
        races = extract_races(soup)
        
        if not races or len(races) == 0:
            logger.warning(f"No {tour_name} Races found for {year}")
            return
            
        with open(os.path.join(tour_dir, filename), 'w') as tour_file:
            for race, url in races:
                tour_file.write(f"{race},{url}\n")
                
        logger.info(f"Saved {len(races)} {tour_name} Race(s) for {year}")
        
    except Exception as e:
        logger.error(f"Error processing {tour_name} races for {year}: {e}")
    
if __name__ == "__main__":
    create_race_year_db(year='2024', race_data_dir=DB_PATH)