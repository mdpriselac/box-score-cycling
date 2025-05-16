from bs4 import BeautifulSoup
import os
import pickle
from typing import Dict, List, Union, Optional
import re
from random import randint
from time import sleep

from cycling_project.webscrape_tools.scrape_client import WebClient
from cycling_project.webscrape_tools.create_race_data import Stage, Race
from cycling_project.data_loading_tools.load_scraped_data import DB_PATH, TOURS
from cycling_project.webscrape_tools.logging_config import get_logger

# Configure logger
logger = get_logger("scrape_startlists")

# Constants
SLEEP_MIN = 1
SLEEP_MAX = 3
BASE_URL = "https://firstcycling.com"

### Tools for extracting startlist
def find_team_tables(soup: BeautifulSoup) -> List[BeautifulSoup]:
    """
    Given a full page soup object, return a list of team startlist tables that have bib numbers as the first column.
    
    Args:
        soup: BeautifulSoup object of the page
        
    Returns:
        list of BeautifulSoup objects of the team startlist tables
    """
    logger.debug("Searching for team tables in page")
    
    # The tables are inside of divs with class='back'
    # Each table has a thead with a tr that has only one th
    # Each table has a tbody that has trs that have two tds. 
    # The first td has text that is 1-3 characters long, all digits
    # The second td has an a tag with an href that has ?rider= in it
    
    # Find all the divs with class='back'
    divs = soup.find_all('div', class_='back')
    logger.debug(f"Found {len(divs)} 'back' divs in page")
    
    # Loop through the divs and find the tables where the conditions are met
    tables = []
    for div_index, div in enumerate(divs):
        # Get the table 
        table = div.find('table')
        if not table:
            continue
            
        one_th_tr_td = False
        two_td_trs = False
        
        # Check the thead structure for match
        # Each table has a thead with a tr that has only one th
        thead = table.find('thead')
        if thead:
            trs = thead.find_all('tr')
            if len(trs) == 1:
                ths = trs[0].find_all('th')
                if len(ths) == 1:
                    one_th_tr_td = True
                    
        # Check the tbody structure for a match
        tbody = table.find('tbody')
        if tbody:
            trs = tbody.find_all('tr')
            # Check to see that all the trs have two tds
            for tr in trs:
                tds = tr.find_all('td')
                if len(tds) < 2:
                    continue
                    
                # Check to see that the first td has text that is 1-3 characters long, all digits
                bib_num_text_found = False
                rider_id_found = False
                
                # Get the first td text
                bib_num_text = tds[0].get_text(strip=True).strip()
                if bib_num_text == '' or bib_num_text is None:
                    continue
                    
                if all(char.isdigit() for char in bib_num_text):
                    bib_num_text_found = True
                    
                # Check to see that the second td has an a tag with an href that has ?rider= in it
                a_tag = tds[1].find('a')
                if a_tag:
                    href = a_tag.get('href')
                    if href and 'rider.php?r=' in href:
                        rider_id_found = True
                        
                if bib_num_text_found and rider_id_found:
                    two_td_trs = True
                    break
                    
        if one_th_tr_td and two_td_trs:
            tables.append(table)
            logger.debug(f"Found valid team table in div {div_index+1}")
    
    logger.info(f"Found {len(tables)} team tables in page")
    return tables


def extract_bib_numbers(team_table: BeautifulSoup) -> List[Dict[str, Union[str, int]]]:
    """
    Given a BeautifulSoup object of a team startlist table, return a dict of bib numbers with rider id and rider name.
    
    Args:
        team_table: BeautifulSoup object of a team startlist table
        
    Returns:
        List of dicts with bib number, rider id, and rider name
    """
    # Get team name for logging
    team_name = "Unknown Team"
    thead = team_table.find('thead')
    if thead:
        th = thead.find('th')
        if th:
            team_name = th.get_text(strip=True)
    
    logger.debug(f"Extracting bib numbers for team: {team_name}")
    
    # Find all the trs in the tbody
    tbody = team_table.find('tbody')
    if not tbody:
        logger.warning(f"No tbody found in team table for {team_name}")
        return []
        
    trs = tbody.find_all('tr')
    bib_numbers = []
    
    for tr_index, tr in enumerate(trs):
        try:
            tds = tr.find_all('td')
            if len(tds) < 2:
                logger.warning(f"Row {tr_index+1} doesn't have enough columns in team {team_name}")
                continue
                
            bib_num_text = tds[0].get_text(strip=True).strip()
            if bib_num_text == '':
                logger.warning('Empty bib number found, skipping')
                continue
                
            # Rider name is the text of the second td
            a_tag = tds[1].find('a')
            if not a_tag:
                logger.warning(f"No link found for rider with bib number {bib_num_text} in team {team_name}")
                continue
                
            rider_name = a_tag.get_text(strip=True)
            
            # Rider id is in the href of the a tag in the second td. It is a sequence of digits that follow r=
            href = a_tag.get('href')
            if not href or 'rider.php?r=' not in href:
                logger.warning(f"Invalid rider link for bib number {bib_num_text} in team {team_name}")
                continue
                
            match = re.search(r'r=(\d+)', href)
            if not match:
                logger.warning(f"Could not extract rider ID from href: {href}")
                continue
                
            rider_id_text = match.group(1)
            rider_id_int = int(rider_id_text)
            
            bib_numbers.append({
                'bib_number': bib_num_text,
                'rider_id': rider_id_int,
                'rider_name': rider_name
            })
            
            logger.debug(f"Added bib number {bib_num_text} for rider {rider_name} (ID: {rider_id_int})")
            
        except Exception as e:
            logger.error(f"Error processing rider in team {team_name}, row {tr_index+1}: {e}")
    
    logger.info(f"Extracted {len(bib_numbers)} bib numbers from team {team_name}")
    return bib_numbers


def extract_bibs_from_startlist_soup(soup: BeautifulSoup) -> List[Dict[str, Union[str, int]]]:
    """
    Given a full page soup object, return a list of dicts with bib numbers, rider ids, and rider names.
    
    Args:
        soup: BeautifulSoup object of the page
        
    Returns:
        List of dicts with bib number, rider id, and rider name
    """
    logger.info("Extracting all bib numbers from startlist page")
    
    # Find the team tables
    team_tables = find_team_tables(soup)
    if not team_tables:
        logger.warning('No team tables found in startlist page')
        return []
        
    bibs = []
    for i, table in enumerate(team_tables):
        logger.debug(f"Processing team table {i+1}/{len(team_tables)}")
        team_bibs = extract_bib_numbers(table)
        bibs.extend(team_bibs)
        
    logger.info(f"Extracted a total of {len(bibs)} bib numbers from {len(team_tables)} teams")
    return bibs


### Update a race file
def update_race_object(race: Union[Race, Stage], 
                       bib_number_list: List[Dict[str, Union[str, int]]]) -> Union[Race, Stage]:
    """
    Update a given race object's results with the startlist bib numbers.
    
    Args:
        race: a Race or Stage object
        bib_number_list: List of dicts with bib number, rider id, and rider name
        
    Returns:
        An updated race or stage object
    """
    object_type = "Race" if isinstance(race, Race) else "Stage"
    name = race.name if hasattr(race, 'name') else "Unknown"
    logger.info(f"Updating {object_type}: {name} with bib numbers")
    
    results = race.results
    if results is None or len(results) < 5:
        logger.warning(f"No results found for {object_type}: {name}")
        return race
        
    updated_count = 0
    missing_count = 0
    
    for result_index, result in enumerate(results):
        try:
            # Get the rider id
            if not isinstance(result, dict):
                logger.warning(f"Result {result_index+1} is not a dictionary, skipping")
                continue
                
            rider_id_res = result.get('rider_id', None)
            if rider_id_res is None:
                logger.debug(f"No rider ID in result {result_index+1}, cannot match to bib number")
                continue
                
            rider_id_res = int(rider_id_res)
            match = None
            
            for bib_dict in bib_number_list:
                if bib_dict.get('rider_id', None) == rider_id_res:
                    match = bib_dict
                    break
                    
            if match is None:
                logger.debug(f"No match found for rider ID {rider_id_res}")
                missing_count += 1
                continue
                
            result['bib_number'] = match.get('bib_number', None)
            updated_count += 1
            
        except Exception as e:
            logger.error(f"Error updating result {result_index+1}: {e}")
    
    race.results = results
    logger.info(f"Updated {updated_count} results with bib numbers, {missing_count} riders had no matching bib number")
    return race


def scrape_and_add_bib_numbers_to_race(race: Race, client: Optional[WebClient] = None) -> Race:
    """
    Scrape and add bib numbers to a race object.
    
    Args:
        race: Race object to update
        client: Optional WebClient. If not provided, a new one will be created
        
    Returns:
        Updated Race object with bib numbers
    """
    logger.info(f"Scraping and adding bib numbers to race: {race.name}")
    
    # Create URL for startlist page
    start_list_url = race.url + '&k=8'
    logger.debug(f"Startlist URL: {start_list_url}")
    
    # Get the startlist page
    close_client = False
    if client is None:
        logger.debug("Creating new WebClient")
        client = WebClient(BASE_URL)
        close_client = True
        
    try:
        # Fetch startlist page
        logger.debug(f"Fetching startlist page for {race.name}")
        response = client.get(start_list_url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Check for bib numbers
        logger.debug(f"Extracting bib numbers for {race.name}")
        bib_list = extract_bibs_from_startlist_soup(soup)
        if not bib_list:
            logger.warning(f"No bib numbers found for {race.name}")
            return race
            
        logger.info(f"Found {len(bib_list)} bib numbers for {race.name}")
        
        # If there are results, update the results
        if race.results is not None and len(race.results) > 5:
            logger.debug(f"Updating main race results for {race.name}")
            updated_race = update_race_object(race=race, bib_number_list=bib_list)
        else:
            logger.debug(f"No main race results to update for {race.name}")
            updated_race = race
            
        # If this is not a stage race, we're done
        if not race.stage_race:
            logger.info(f"Completed bib number update for one-day race: {race.name}")
            return updated_race
            
        # If there are stages, update each stage and then replace the stages list
        logger.info(f"Updating {len(race.stages)} stages for {race.name}")
        updated_stages = []
        
        for i, stage in enumerate(updated_race.stages):
            stage_name = stage.name if hasattr(stage, 'name') else f"Stage {i+1}"
            logger.debug(f"Updating stage {i+1}/{len(updated_race.stages)}: {stage_name}")
            
            updated_stage = update_race_object(race=stage, bib_number_list=bib_list)
            updated_stages.append(updated_stage)
            
        updated_race.stages = updated_stages
        logger.info(f"Completed bib number update for stage race: {race.name}")
        
        # Sleep to avoid overwhelming the server
        sleep_time = randint(SLEEP_MIN, SLEEP_MAX)
        logger.debug(f"Sleeping for {sleep_time} seconds")
        sleep(sleep_time)
        
        return updated_race
        
    except Exception as e:
        logger.error(f"Error scraping bib numbers for {race.name}: {e}")
        return race
        
    finally:
        if close_client:
            logger.debug("Closing WebClient")
            client.close()


def add_bibs_to_tour(tour_dir_path: str) -> None:
    """
    Given a tour directory, add bib numbers to all races in the tour directory.
    
    Args:
        tour_dir_path: Path to a tour directory
    """
    tour_name = os.path.basename(tour_dir_path)
    logger.info(f"Adding bib numbers to all races in tour: {tour_name}")
    
    try:
        # Find the txt file in the directory, read the race name, url
        txt_files = [f for f in os.listdir(tour_dir_path) if f.endswith('.txt')]
        if not txt_files:
            logger.error(f"No txt files found in {tour_dir_path} to use as a race list")
            return
            
        race_list_file = txt_files[0]
        file_path = os.path.join(tour_dir_path, race_list_file)
        
        try:
            with open(file_path, 'r') as file:
                lines = file.readlines()
                
            logger.info(f"Found {len(lines)} races in {file_path}")
        except Exception as e:
            logger.error(f"Error reading race list file {file_path}: {e}")
            return
            
        # Create the scraping client
        client = WebClient(BASE_URL)
        logger.debug("Created WebClient for batch processing")
        
        # Process each race
        for i, line in enumerate(lines):
            try:
                # Get the race name, which is the first part of the line in front of the comma
                parts = line.strip().split(',')
                if len(parts) < 1:
                    logger.warning(f"Invalid line format in {file_path}, line {i+1}")
                    continue
                    
                race_name = parts[0]
                logger.info(f"Processing race {i+1}/{len(lines)}: {race_name}")
                
                # Load the pickle file in the tour_dir_path that starts with that name
                pkl_path = os.path.join(tour_dir_path, f"{race_name}.pkl")
                if not os.path.exists(pkl_path):
                    logger.warning(f"Pickle file not found for race: {race_name}")
                    continue
                    
                try:
                    with open(pkl_path, 'rb') as f:
                        race_obj = pickle.load(f)
                except Exception as e:
                    logger.error(f"Error loading race pickle file {pkl_path}: {e}")
                    continue
                    
                # Scrape the bib numbers
                logger.debug(f"Scraping bib numbers for {race_name}")
                bibs_added_race_obj = scrape_and_add_bib_numbers_to_race(race=race_obj, client=client)
                
                # Save the race_obj to a pickle file in the tour_dir_path
                try:
                    with open(pkl_path, 'wb') as f:
                        pickle.dump(bibs_added_race_obj, f)
                    logger.info(f"Successfully saved updated race data for {race_name}")
                except Exception as e:
                    logger.error(f"Error saving updated race pickle file {pkl_path}: {e}")
                    
                # Sleep between races
                sleep_time = randint(SLEEP_MIN, SLEEP_MAX + 1)
                logger.debug(f"Sleeping for {sleep_time} seconds before next race")
                sleep(sleep_time)
                
            except Exception as e:
                logger.error(f"Error processing race in line {i+1}: {e}")
                
        logger.info(f"Completed adding bib numbers to all races in tour: {tour_name}")
        
    except Exception as e:
        logger.error(f"Error processing tour directory {tour_dir_path}: {e}")
        
    finally:
        # Make sure the client is closed
        try:
            client.close()
            logger.debug("WebClient closed")
        except:
            pass


def add_bibs_to_year(year_dir_path: str) -> None:
    """
    Given a year directory, add bib numbers to all races in all tours.
    
    Args:
        year_dir_path: Path to a year directory
    """
    year = os.path.basename(year_dir_path)
    logger.info(f"Adding bib numbers to all races in year: {year}")
    
    for tour in TOURS:
        tour_dir_path = os.path.join(year_dir_path, tour)
        if not os.path.exists(tour_dir_path):
            logger.warning(f"Tour directory not found: {tour_dir_path}")
            continue
            
        logger.info(f"Processing tour: {tour}")
        try:
            add_bibs_to_tour(tour_dir_path)
            logger.info(f"Completed processing tour: {tour}")
        except Exception as e:
            logger.error(f"Error processing tour {tour}: {e}")
            
    logger.info(f"Completed adding bib numbers to all races in year: {year}")


def add_bibs_to_race_db(db_path: str = DB_PATH) -> None:
    """
    Given a db path, add bib numbers to all races.
    
    Args:
        db_path: Path to the database directory
    """
    logger.info(f"Adding bib numbers to all races in database: {db_path}")
    
    try:
        # Get all year directories (4-digit folders)
        year_dirs = [f for f in os.listdir(db_path) 
                    if os.path.isdir(os.path.join(db_path, f)) and len(f) == 4]
        
        if not year_dirs:
            logger.warning(f"No year directories found in {db_path}")
            return
            
        logger.info(f"Found {len(year_dirs)} years to process")
        
        # Process each year
        for year in sorted(year_dirs):
            year_dir_path = os.path.join(db_path, year)
            logger.info(f"Processing year: {year}")
            
            try:
                add_bibs_to_year(year_dir_path)
                logger.info(f"Completed processing year: {year}")
            except Exception as e:
                logger.error(f"Error processing year {year}: {e}")
                
        logger.info(f"Completed adding bib numbers to all races in database")
        
    except Exception as e:
        logger.error(f"Error processing database directory {db_path}: {e}")


if __name__ == '__main__':
    logger.info("Starting bib number addition to race database")
    add_bibs_to_race_db(db_path=DB_PATH)
    logger.info("Completed bib number addition to race database")