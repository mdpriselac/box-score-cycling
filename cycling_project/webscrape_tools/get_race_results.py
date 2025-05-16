from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
from typing import Optional, Dict, List, Any, Union

from cycling_project.webscrape_tools.start_list_parse_tools import extract_rider_id, extract_team_id
from cycling_project.webscrape_tools.logging_config import get_logger

# Configure logger
logger = get_logger("get_race_results")


def find_race_result_table(soup: BeautifulSoup) -> Optional[BeautifulSoup]:
    """
    Find the table containing a thead that contains POS, Rider, Team, and Time.
    
    Args:
        soup: BeautifulSoup of the race page
        
    Returns:
        BeautifulSoup table tag or None if not found
    """
    logger.debug("Searching for race result table")
    
    tables_count = len(soup.find_all('table'))
    logger.debug(f"Found {tables_count} tables on page")
    
    for i, table in enumerate(soup.find_all('table')):
        thead = table.find('thead')
        if not thead:
            continue
            
        th_cols = thead.find_all('th')
        pos_found = False
        rider_found = False
        team_found = False
        time_found = False
        
        for th in th_cols:
            th_text = th.text.lower()
            if 'pos' in th_text:
                pos_found = True
            if 'rider' in th_text:
                rider_found = True
            if 'team' in th_text:
                team_found = True
            if 'time' in th_text:
                time_found = True
                
        if pos_found and rider_found and team_found and time_found:
            logger.info(f"Found race result table (table {i+1}/{tables_count})")
            return table
            
    logger.warning("No race result table found on page")
    return None


def find_thead_index(table_col: str, table: BeautifulSoup) -> Optional[int]:
    """
    Find the index of the column in the thead of the table.
    
    Args:
        table_col: The text of the column you want to find (str)
        table: The table you want to search (BeautifulSoup table tag)
        
    Returns:
        The index of the column in the thead or None if not found
    """
    thead = table.find('thead')
    if not thead:
        logger.warning("No thead found in table")
        return None
        
    th_elements = thead.find_all('th')
    logger.debug(f"Searching for column '{table_col}' in {len(th_elements)} thead columns")
    
    for i, th in enumerate(th_elements):
        th_text = th.text.strip().lower()
        if table_col.lower() in th_text:
            logger.debug(f"Found column '{table_col}' at index {i}")
            return i
            
    logger.warning(f"Column '{table_col}' not found in thead")
    return None


def find_table_head_order(race_result_table: BeautifulSoup) -> Dict[str, Optional[int]]:
    """
    Find the order of the columns in the table heads of the race result table.
    
    Args:
        race_result_table: BeautifulSoup table tag
        
    Returns:
        Dict with keys 'pos','rider','team','time','born' and values as the index of the column in the table
    """
    logger.debug("Finding column order in race result table")
    
    key_cols = ['pos', 'rider', 'team', 'time', 'born']
    column_indices = {}
    
    for col_name in key_cols:
        idx = find_thead_index(col_name, race_result_table)
        column_indices[col_name] = idx
        
    found_cols = [col for col, idx in column_indices.items() if idx is not None]
    missing_cols = [col for col, idx in column_indices.items() if idx is None]
    
    logger.info(f"Found columns: {', '.join(found_cols)}")
    if missing_cols:
        logger.warning(f"Missing columns: {', '.join(missing_cols)}")
        
    return column_indices


def extract_rider_birth_year(rider_row: BeautifulSoup, dob_col_index: int) -> Optional[str]:
    """
    Extract the birth year of the rider from the row.
    
    Args:
        rider_row: BeautifulSoup tr tag from the race result table
        dob_col_index: Index of the born column
        
    Returns:
        Rider birth year as string or None if not found
    """
    try:
        dob_text = rider_row.find_all('td')[dob_col_index].get_text(strip=True)
        logger.debug(f"Extracted birth year: {dob_text}")
        return dob_text
    except Exception as e:
        logger.error(f"Error extracting rider birth year: {e}")
        return None


def extract_rider_time_gap(time_str: str) -> Union[float, str]:
    """
    Takes in a time string from rider race results and returns the time in seconds.
    
    Args:
        time_str: Time string extracted from a results row (str)
        
    Returns:
        Time gap from winner in seconds or original string if not convertible
    """
    logger.debug(f"Extracting time gap from: '{time_str}'")
    
    # Clean up the time string
    time_str = time_str.strip()
    
    # If the time string does not have '+' and has digits, it is the winner, gap is 0
    if '+' not in time_str and any(char.isdigit() for char in time_str):
        logger.debug("Detected winner's time (no + sign)")
        return 0
        
    # If no digits are in the string, just return the string itself (e.g., "DNF", "DNS")
    if not any(char.isdigit() for char in time_str):
        logger.debug(f"Returning non-time value: {time_str}")
        return time_str
    
    # If there's a '+' in the time string, we have a gap
    if '+' in time_str:
        logger.debug("Detected time gap (+ sign)")
        time_str = time_str.split('+')[1].strip()
        
    try:
        # If the time string has two colons, we have hours, minutes, seconds
        if time_str.count(':') == 2:
            hours, minutes, seconds = time_str.split(':')
            time_sec = timedelta(
                hours=int(hours),
                minutes=int(minutes),
                seconds=float(seconds)
            ).total_seconds()
            logger.debug(f"Parsed h:m:s format: {time_sec} seconds")
            return time_sec
            
        # If there is one colon, we have minutes and seconds
        elif time_str.count(':') == 1:
            minutes, seconds = time_str.split(':')
            time_sec = timedelta(
                minutes=int(minutes),
                seconds=float(seconds)
            ).total_seconds()
            logger.debug(f"Parsed m:s format: {time_sec} seconds")
            return time_sec
            
        # If there are no colons, we have only seconds
        else:
            time_sec = float(time_str)
            logger.debug(f"Parsed seconds only: {time_sec} seconds")
            return time_sec
            
    except Exception as e:
        logger.error(f"Error parsing time string '{time_str}': {e}")
        return time_str


def parse_rider_row(table_race_result_row: BeautifulSoup, table_head_order: Dict[str, int]) -> Optional[Dict[str, Any]]:
    """
    Extract rider position, name, id, team, team id, and raw time from a row in a race results table.
    
    Args:
        table_race_result_row: BeautifulSoup tr tag taken from the race results table
        table_head_order: Dict with keys 'pos','rider','team','time' and values as the index of the column in the table
        
    Returns:
        Dict with keys 'place','name','id','team','team_id','gap' or None if parsing fails
    """
    # Extract the rider name for logging
    try:
        rider_name = "Unknown rider"
        rider_cols = table_race_result_row.find_all('td')
        rider_col_idx = table_head_order.get('rider')
        
        if rider_col_idx is not None and rider_col_idx < len(rider_cols):
            rider_name = rider_cols[rider_col_idx].get_text(strip=True, separator=' ')
        
        logger.debug(f"Parsing result row for {rider_name}")
        
        # Get all columns in the row
        rider_result_cols = table_race_result_row.find_all('td')
        if len(rider_result_cols) < len([v for v in table_head_order.values() if v is not None]):
            logger.warning(f"Row for {rider_name} has {len(rider_result_cols)} columns, fewer than expected")
            return None
            
        # Extract rider details
        rider_result_dict = {}
        
        # Extract position
        pos_col_idx = table_head_order.get('pos')
        if pos_col_idx is not None:
            rider_place = rider_result_cols[pos_col_idx].get_text(strip=True)
            rider_result_dict['place'] = rider_place
        else:
            logger.warning(f"No position column found for {rider_name}")
            
        # Extract rider name and ID
        rider_col_idx = table_head_order.get('rider')
        if rider_col_idx is not None:
            rider_cell = rider_result_cols[rider_col_idx]
            rider_name = rider_cell.get_text(strip=True, separator=' ')
            rider_result_dict['name'] = rider_name
            
            rider_link = rider_cell.find('a')
            if rider_link and rider_link.get('href'):
                rider_id = extract_rider_id(rider_link.get('href'))
                rider_result_dict['rider_id'] = rider_id
            else:
                logger.warning(f"No rider ID found for {rider_name}")
                rider_result_dict['rider_id'] = None
        else:
            logger.warning("No rider column found")
            
        # Extract team and team ID
        team_col_idx = table_head_order.get('team')
        if team_col_idx is not None:
            team_cell = rider_result_cols[team_col_idx]
            rider_team = team_cell.get_text(strip=True, separator=' ')
            rider_result_dict['team'] = rider_team
            
            try:
                team_link = team_cell.find('a')
                if team_link and team_link.get('href'):
                    rider_team_id = extract_team_id(team_link.get('href'))
                    rider_result_dict['team_id'] = rider_team_id
                else:
                    logger.debug(f"No team link found for {rider_name}")
                    rider_result_dict['team_id'] = None
            except Exception as e:
                logger.warning(f"Error extracting team ID for {rider_name}: {e}")
                rider_result_dict['team_id'] = None
        else:
            logger.warning("No team column found")
            
        # Extract time gap
        time_col_idx = table_head_order.get('time')
        if time_col_idx is not None:
            time_text = rider_result_cols[time_col_idx].get_text(strip=True)
            rider_gap = extract_rider_time_gap(time_text)
            rider_result_dict['gap'] = rider_gap
        else:
            logger.warning("No time column found")
            
        # Extract DOB if available
        born_col_idx = table_head_order.get('born')
        if born_col_idx is not None:
            dob = extract_rider_birth_year(table_race_result_row, born_col_idx)
            rider_result_dict['dob'] = dob
        else:
            rider_result_dict['dob'] = None
            
        logger.debug(f"Successfully parsed result for {rider_name}")
        return rider_result_dict
        
    except Exception as e:
        logger.error(f"Error parsing rider row for {rider_name}: {e}")
        return None


def extract_race_time(race_page_soup: BeautifulSoup) -> Optional[float]:
    """
    Extract the total race time in seconds from a race results page.
    
    Args:
        race_page_soup: BeautifulSoup of page containing results
        
    Returns:
        Float of race time in seconds or None if not found
    """
    logger.info("Extracting race time")
    
    try:
        # Find the results table
        result_table = find_race_result_table(race_page_soup)
        if not result_table:
            logger.warning("No results table found for this race")
            return None
            
        # Find the order of the columns in the table
        table_head_order = find_table_head_order(result_table)
        
        # Get the time column index
        time_column = table_head_order.get('time')
        if time_column is None:
            logger.warning("No time column found in results table")
            return None
            
        # Extract the first row of the table (winner)
        tbody = result_table.find('tbody')
        if not tbody:
            logger.warning("No tbody found in results table")
            return None
            
        first_row = tbody.find('tr')
        if not first_row:
            logger.warning("No rows found in results table")
            return None
            
        # Check if the row has enough columns
        td_elements = first_row.find_all('td')
        if len(td_elements) <= time_column:
            logger.warning(f"First row has {len(td_elements)} columns, time column index is {time_column}")
            return None
            
        # Extract the time string
        time_str = td_elements[time_column].get_text(strip=True)
        logger.debug(f"Winner's time string: '{time_str}'")
        
        # Parse the time string
        if time_str.count(':') == 2:
            # Format: hours:minutes:seconds
            hours, minutes, seconds = time_str.split(':')
            time_sec = timedelta(
                hours=int(hours),
                minutes=int(minutes),
                seconds=float(seconds)
            ).total_seconds()
            logger.info(f"Parsed race time: {time_sec} seconds ({time_str})")
            return time_sec
            
        elif time_str.count(':') == 1:
            # Format: minutes:seconds
            minutes, seconds = time_str.split(':')
            time_sec = timedelta(
                minutes=int(minutes),
                seconds=float(seconds)
            ).total_seconds()
            logger.info(f"Parsed race time: {time_sec} seconds ({time_str})")
            return time_sec
            
        else:
            # Format: seconds only
            try:
                time_sec = float(time_str)
                logger.info(f"Parsed race time: {time_sec} seconds")
                return time_sec
            except ValueError:
                logger.error(f"Error converting time string to float: '{time_str}'")
                return None
                
    except Exception as e:
        logger.error(f"Error extracting race time: {e}")
        return None


def extract_race_date(race_page_soup: BeautifulSoup) -> Optional[str]:
    """
    Extract the race date from the race page.
    
    Args:
        race_page_soup: BeautifulSoup of race page
        
    Returns:
        Race date string in YYYY-MM-DD format or None if extraction fails
    """
    logger.info("Extracting race date")
    
    try:
        # Find the div tag with id='race' within the body tag, and get the first h2 tag
        body = race_page_soup.find('body')
        if not body:
            logger.warning("No body tag found in page")
            return None
            
        race_div = body.find('div', id='race')
        if not race_div:
            logger.warning("No div with id='race' found")
            return None
            
        h2_tag = race_div.find('h2')
        if not h2_tag:
            logger.warning("No h2 tag found in race div")
            return None
            
        date_str = h2_tag.get_text(strip=True, separator=' ')
        logger.debug(f"Found date string in h2: '{date_str}'")
        
        # Extract the date using regex
        date_match = re.search(r'\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+\d{4}', date_str)
        if not date_match:
            logger.warning(f"Date pattern not found in: '{date_str}'")
            return None
            
        date_str = date_match.group(0)
        logger.debug(f"Extracted date string: '{date_str}'")
        
        # Remove ordinal suffixes
        date_str = re.sub(r'(st|nd|rd|th)', '', date_str)
        
        # Parse the date string
        try:
            date_obj = datetime.strptime(date_str, '%d %B %Y')
            formatted_date = date_obj.strftime('%Y-%m-%d')
            logger.info(f"Parsed race date: {formatted_date}")
            return formatted_date
        except Exception as e:
            logger.error(f"Error parsing date string '{date_str}': {e}")
            return None
            
    except Exception as e:
        logger.error(f"Error extracting race date: {e}")
        return None


def extract_results(race_page_soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """
    Extract the race results from the BeautifulSoup of race results webpage.
    
    Args:
        race_page_soup: BeautifulSoup of page containing results
        
    Returns:
        List of dicts with rider results, or empty list if no results found
    """
    logger.info("Extracting race results")
    
    try:
        # Find the results table
        result_table = find_race_result_table(race_page_soup)
        if result_table is None:
            logger.warning("No results table found for this race")
            return []
            
        # Find the order of columns in the table
        table_head_order = find_table_head_order(result_table)
        
        # Get the tbody and rows
        tbody = result_table.find('tbody')
        if not tbody:
            logger.warning("No tbody found in results table")
            return []
            
        rows = tbody.find_all('tr')
        logger.debug(f"Found {len(rows)} result rows")
        
        # Extract results from each row
        rider_results = []
        for i, row in enumerate(rows):
            try:
                result = parse_rider_row(row, table_head_order)
                if result:
                    rider_results.append(result)
                    if i == 0:
                        logger.debug(f"Winner: {result.get('name', 'Unknown')}")
            except Exception as e:
                logger.error(f"Error parsing result row {i+1}: {e}")
                
        logger.info(f"Extracted {len(rider_results)} rider results")
        return rider_results
        
    except Exception as e:
        logger.error(f"Error extracting race results: {e}")
        return []