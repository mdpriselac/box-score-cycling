from typing import List, Optional
import sys

from cycling_project.webscrape_tools.scrape_client import WebClient
from cycling_project.webscrape_tools.start_list_parse_tools import parse_start_list, Team, get_startlist_stats
from cycling_project.webscrape_tools.logging_config import get_logger

# Configure logger
logger = get_logger("get_startlist")

# Constants
BASE_URL = "https://firstcycling.com"


def get_start_list(race_id: int, year: int) -> List[Team]:
    """
    Get the start list for a race given a race id and year.
    
    Args:
        race_id: the FirstCycling race id (int)
        year: four digit year of the race (int)
        
    Returns:
        List of Team objects with riders. Team objects have a name, FirstCycling team id, 
        and a list of Rider objects.
    """
    logger.info(f"Getting start list for race ID {race_id}, year {year}")
    
    # Create the URL for the startlist page
    start_list_url = f"{BASE_URL}/race.php?r={race_id}&y={year}&k=8"
    logger.debug(f"Startlist URL: {start_list_url}")
    
    client = WebClient(BASE_URL)
    
    try:
        # Fetch the startlist page
        logger.debug(f"Fetching startlist page for race ID {race_id}")
        response = client.get(start_list_url)
        
        # Parse the startlist
        logger.debug(f"Parsing startlist for race ID {race_id}")
        teams = parse_start_list(response.text)
        
        # Log statistics about the retrieved startlist
        stats = get_startlist_stats(teams)
        logger.info(f"Retrieved startlist for race ID {race_id} with {stats['team_count']} teams and {stats['rider_count']} riders")
        
        return teams
        
    except Exception as e:
        logger.error(f"Error getting start list for race ID {race_id}, year {year}: {e}")
        return []
        
    finally:
        logger.debug("Closing WebClient")
        client.close()


def print_start_list(start_list: List[Team]) -> None:
    """
    Print a formatted view of a start list to the console.
    
    Args:
        start_list: List of Team objects
    """
    logger.debug("Printing startlist to console")
    
    for team in start_list:
        print(team.name, len(team.riders))
        for rider in team.riders:
            print(f"  {rider.number}: {rider.name}")
            print(f"    Rider ID: {rider.rider_id}")
            print(f"    Team ID: {rider.team_id}")


def fetch_start_list_from_cli() -> Optional[List[Team]]:
    """
    Fetch a start list using command line arguments.
    Expects race_id as sys.argv[1] and year as sys.argv[2].
    
    Returns:
        List of Team objects if successful, None if arguments are invalid
    """
    logger.info("Fetching startlist from command line arguments")
    
    if len(sys.argv) < 3:
        logger.error("Insufficient arguments. Usage: python get_startlist.py RACE_ID YEAR")
        print("Usage: python get_startlist.py RACE_ID YEAR")
        return None
        
    try:
        race_id = int(sys.argv[1])
        year = int(sys.argv[2])
        
        logger.info(f"CLI arguments: race_id={race_id}, year={year}")
        return get_start_list(race_id=race_id, year=year)
        
    except ValueError as e:
        logger.error(f"Invalid arguments. Both race_id and year must be integers: {e}")
        print("Error: Both race_id and year must be integers")
        return None


if __name__ == "__main__":
    logger.info("Running get_startlist.py as main script")
    
    start_list = fetch_start_list_from_cli()
    if start_list:
        print_start_list(start_list)
        logger.info("Successfully displayed startlist")
    else:
        logger.warning("No startlist displayed due to errors")