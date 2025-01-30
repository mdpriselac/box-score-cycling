from typing import List
import sys

from webscrape_tools.scrape_client import WebClient
from webscrape_tools.parse_tools import parse_start_list,Team


def get_start_list(race_id:int, year:int) -> List[Team]:
    """Get the start list for a race given a race id and year.
    Args:
        race_id: the FirstCycling race id (int)
        year: four digit year of the race (int)
    Returns:
        List of Team objects with riders. Team objects have a name, FirstCycling team id, and a list of Rider objects."""
    start_list = f"https://firstcycling.com/race.php?r={race_id}&y={year}&k=8"
    client = WebClient("https://firstcycling.com")
    try:
        response = client.get(start_list)
        return parse_start_list(response.text)
    except Exception as e:
        print(f"Error getting start list: {e}")
        return []
    finally:
        client.close()

if __name__ == "__main__":
    race_id = sys.argv[1]
    year = sys.argv[2]
    start_list = get_start_list(race_id=race_id, year=year)
    for team in start_list:
        print(team.name, len(team.riders))
        for rider in team.riders:
            print(f"  {rider.number}: {rider.name}")
            print(f"    Rider ID: {rider.rider_id}")
            print(f"    Team ID: {rider.team_id}")
    