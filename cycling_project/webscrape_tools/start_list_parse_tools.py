from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import re

from cycling_project.webscrape_tools.logging_config import get_logger

# Configure logger
logger = get_logger("start_list_parse_tools")

@dataclass
class Rider:
    """Class representing a rider in a cycling race startlist."""
    name: str
    rider_id: Optional[str]
    number: str
    team_name: str
    team_id: Optional[str]


@dataclass
class Team:
    """Class representing a team in a cycling race startlist."""
    name: str
    team_id: Optional[str]
    riders: List[Rider]


def extract_rider_id(href: Optional[str]) -> Optional[str]:
    """
    Extract rider ID from href like 'rider.php?r=1905&y=2012'.
    
    Args:
        href: URL containing rider ID
        
    Returns:
        Rider ID as a string, or None if not found
    """
    if not href:
        logger.debug("Empty href provided to extract_rider_id")
        return None
        
    match = re.search(r'r=(\d+)', href)
    if match:
        rider_id = match.group(1)
        logger.debug(f"Extracted rider ID: {rider_id}")
        return rider_id
    else:
        logger.debug(f"Could not extract rider ID from href: {href}")
        return None


def extract_team_id(href: Optional[str]) -> Optional[str]:
    """
    Extract team ID from href like 'team.php?l=53'.
    
    Args:
        href: URL containing team ID
        
    Returns:
        Team ID as a string, or None if not found
    """
    if not href:
        logger.debug("Empty href provided to extract_team_id")
        return None
        
    match = re.search(r'l=(\d+)', href)
    if match:
        team_id = match.group(1)
        logger.debug(f"Extracted team ID: {team_id}")
        return team_id
    else:
        logger.debug(f"Could not extract team ID from href: {href}")
        return None


def parse_start_list(html_content: str) -> List[Team]:
    """
    Parse HTML content of a startlist page and extract teams and riders.
    
    Args:
        html_content: HTML content of the startlist page
        
    Returns:
        List of Team objects, each containing riders
        
    Raises:
        ValueError: If the page structure doesn't match expectations
    """
    logger.info("Parsing startlist HTML")
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        # FirstCycling's 2026-10 redesign: <div class="start-grid"> holding one
        # <div class="start-team"> per team (name in .start-team-head, riders in
        # table.rider-table).  The old wrapper/.back layout is kept below.
        grid = soup.find('div', class_='start-grid')
        if grid is not None:
            return _parse_start_grid(grid)

        # Find the wrapper div
        wrapper = soup.find('div', id='wrapper')
        if not wrapper:
            logger.error("Could not find wrapper div in HTML content")
            raise ValueError("Could not find wrapper div")
        
        # Find all 'back' class divs
        back_divs = wrapper.find_all('div', class_='back')
        logger.debug(f"Found {len(back_divs)} team blocks in the startlist")
        
        teams = []
        
        for div_index, back_div in enumerate(back_divs):
            try:
                # Each back div should contain a team table
                table = back_div.find('table')
                if not table:
                    logger.debug(f"No table found in div {div_index+1}, skipping")
                    continue
                
                # Get team information from table head
                thead = table.find('thead')
                if not thead:
                    logger.debug(f"No thead found in table {div_index+1}, skipping")
                    continue
                
                team_row = thead.find('tr')
                if not team_row:
                    logger.debug(f"No team row found in thead {div_index+1}, skipping")
                    continue
                
                # Extract team name and ID
                team_link = team_row.find('a')
                team_name = team_row.get_text(strip=True)
                team_id = extract_team_id(team_link.get('href')) if team_link else None
                
                logger.info(f"Processing team: {team_name} (ID: {team_id})")
                
                # Process riders
                riders = []
                tbody = table.find('tbody')
                if not tbody:
                    logger.warning(f"No tbody found for team {team_name}, skipping riders")
                    continue
                
                rider_rows = tbody.find_all('tr')
                logger.debug(f"Found {len(rider_rows)} rider rows for team {team_name}")
                
                for row_index, rider_row in enumerate(rider_rows):
                    try:
                        rider_info = rider_row.find_all('td')
                        if len(rider_info) < 2:  # Ensure we have number and name
                            logger.warning(f"Insufficient columns in rider row {row_index+1} for team {team_name}")
                            continue
                            
                        rider_number = rider_info[0].get_text(strip=True)
                        rider_name = rider_info[1].get_text(strip=True, separator=' ')
                        
                        # Extract rider ID from link if it exists
                        rider_link = rider_info[1].find('a')
                        rider_id = extract_rider_id(rider_link.get('href')) if rider_link else None
                        
                        if not rider_id:
                            logger.debug(f"No rider ID found for {rider_name} in team {team_name}")
                        
                        rider = Rider(
                            name=rider_name,
                            rider_id=rider_id,
                            number=rider_number,
                            team_name=team_name,
                            team_id=team_id
                        )
                        riders.append(rider)
                        logger.debug(f"Added rider: {rider_name} (ID: {rider_id}, Number: {rider_number})")
                        
                    except Exception as e:
                        logger.error(f"Error processing rider in row {row_index+1} for team {team_name}: {e}")
                
                team = Team(
                    name=team_name,
                    team_id=team_id,
                    riders=riders
                )
                
                teams.append(team)
                logger.info(f"Added team {team_name} with {len(riders)} riders")
                
            except Exception as e:
                logger.error(f"Error processing team div {div_index+1}: {e}")
        
        logger.info(f"Parsing complete. Found {len(teams)} teams with a total of {sum(len(team.riders) for team in teams)} riders")
        return teams
        
    except Exception as e:
        logger.error(f"Error parsing startlist HTML: {e}")
        raise


def _parse_start_grid(grid) -> List[Team]:
    """Teams and riders from the 2026-10 ``start-grid`` layout."""
    teams = []
    for block in grid.find_all('div', class_='start-team'):
        head = block.find(class_='start-team-head')
        team_link = head.find('a') if head else None
        team_name = (team_link.get_text(strip=True) if team_link
                     else head.get_text(strip=True) if head else "")
        team_id = extract_team_id(team_link.get('href')) if team_link else None
        riders = []
        table = block.find('table')
        for row in (table.find_all('tr') if table else []):
            cells = row.find_all('td')
            if len(cells) < 2:
                continue
            rider_link = cells[1].find('a')
            riders.append(Rider(
                name=cells[1].get_text(strip=True, separator=' '),
                rider_id=extract_rider_id(rider_link.get('href')) if rider_link else None,
                number=cells[0].get_text(strip=True),
                team_name=team_name,
                team_id=team_id,
            ))
        teams.append(Team(name=team_name, team_id=team_id, riders=riders))
        logger.info(f"Added team {team_name} with {len(riders)} riders")
    logger.info(f"Parsing complete. Found {len(teams)} teams with a total of {sum(len(t.riders) for t in teams)} riders")
    return teams


def get_startlist_stats(teams: List[Team]) -> Dict[str, Any]:
    """
    Generate statistics about a parsed startlist.
    
    Args:
        teams: List of Team objects from parse_start_list
        
    Returns:
        Dictionary containing statistics about the startlist
    """
    logger.debug("Generating startlist statistics")
    
    total_riders = sum(len(team.riders) for team in teams)
    riders_with_ids = sum(1 for team in teams for rider in team.riders if rider.rider_id)
    teams_with_ids = sum(1 for team in teams if team.team_id)
    
    stats = {
        "team_count": len(teams),
        "rider_count": total_riders,
        "riders_with_ids": riders_with_ids,
        "riders_without_ids": total_riders - riders_with_ids,
        "teams_with_ids": teams_with_ids,
        "teams_without_ids": len(teams) - teams_with_ids,
        "average_riders_per_team": total_riders / len(teams) if teams else 0
    }
    
    logger.info(f"Startlist stats: {len(teams)} teams, {total_riders} riders")
    return stats