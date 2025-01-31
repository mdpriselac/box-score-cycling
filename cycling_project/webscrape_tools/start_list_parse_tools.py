from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import List, Optional
import re

@dataclass
class Rider:
    name: str
    rider_id: Optional[str]
    number: str
    team_name: str
    team_id: Optional[str]

@dataclass
class Team:
    name: str
    team_id: Optional[str]
    riders: List[Rider]

def extract_rider_id(href: Optional[str]) -> Optional[str]:
    """Extract rider ID from href like 'rider.php?r=1905&y=2012'"""
    if not href:
        return None
    match = re.search(r'r=(\d+)', href)
    return match.group(1) if match else None

def extract_team_id(href: Optional[str]) -> Optional[str]:
    """Extract team ID from href like 'team.php?l=53'"""
    if not href:
        return None
    match = re.search(r'l=(\d+)', href)
    return match.group(1) if match else None

def parse_start_list(html_content: str) -> List[Team]:
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find the wrapper div
    wrapper = soup.find('div', id='wrapper')
    if not wrapper:
        raise ValueError("Could not find wrapper div")
    
    teams = []
    
    # Find all 'back' class divs
    back_divs = wrapper.find_all('div', class_='back')
    
    for back_div in back_divs:
        table = back_div.find('table')
        if not table:
            continue
            
        # Get team information from table head
        thead = table.find('thead')
        if not thead:
            continue
            
        team_row = thead.find('tr')
        if not team_row:
            continue
            
        # Extract team name and ID
        team_link = team_row.find('a')
        team_name = team_row.get_text(strip=True)
        team_id = extract_team_id(team_link.get('href')) if team_link else None
        
        # Process riders
        riders = []
        tbody = table.find('tbody')
        if tbody:
            for rider_row in tbody.find_all('tr'):
                rider_info = rider_row.find_all('td')
                if len(rider_info) >= 2:  # Ensure we have number and name
                    rider_number = rider_info[0].get_text(strip=True)
                    rider_name = rider_info[1].get_text(strip=True, separator=' ')
                    
                    # Extract rider ID from link if it exists
                    rider_link = rider_info[1].find('a')
                    rider_id = extract_rider_id(rider_link.get('href')) if rider_link else None
                    
                    rider = Rider(
                        name=rider_name,
                        rider_id=rider_id,
                        number=rider_number,
                        team_name=team_name,
                        team_id=team_id
                    )
                    riders.append(rider)
        
        team = Team(
            name=team_name,
            team_id=team_id,
            riders=riders
        )
        teams.append(team)
    
    return teams

