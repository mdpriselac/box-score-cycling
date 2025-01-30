from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re

from cycling_project.webscrape_tools.parse_tools import extract_rider_id,extract_team_id
#find a thead that contains, at any level, a th with the text POS or Rider or Team or or Time.
# We want the table that contains the thead that contains all the ths we want.

def find_race_result_table(soup:BeautifulSoup):
    """Find the table containing a thead that contains POS, Rider, Team, and Time.
    Args:
        soup: BeautifulSoup
    Returns:
        BeautifulSoup table tag"""
    for table in soup.find_all('table'):
        thead = table.find('thead')
        if thead:
            th_cols = thead.find_all('th')
            pos_found = False
            rider_found = False
            team_found = False
            time_found = False
            for th in th_cols:
                if 'pos' in th.text.lower():
                    pos_found = True
                if 'rider' in th.text.lower():
                    rider_found = True
                if 'team' in th.text.lower():
                    team_found = True
                if 'time' in th.text.lower():
                    time_found = True
            if pos_found and rider_found and team_found and time_found:
                    return table
    return None

def find_thead_index(table_col:str,table:BeautifulSoup)->int:
    """Find the index of the column in the thead of the table.
    Args:
        table_col: the text of the column you want to find (str)
        table: the table you want to search (BeautifulSoup table tag)
    Returns:
        col_index: the index of the column in the thead"""
    thead = table.find('thead')
    if thead:
        for i,th in enumerate(thead.find_all('th')):
            if table_col.lower() in th.text.strip().lower():
                return i
    return None


def find_table_head_order(race_result_table:BeautifulSoup)->dict:
    """Find the order of the columns in the table heads of the table: POS, Rider, Team, Time in the table heads and return the index for each column.
    Args:
    race_result_table: BeautifulSoup table tag
    Returns:
    dict with keys 'pos','rider','team','time' and values as the index of the column in the table"""
    
    key_cols = ['pos', 'rider','team','time','born']
    return {col_name:find_thead_index(col_name,race_result_table) for col_name in key_cols}


def extract_rider_birth_year(rider_row,dob_col_index:int):
    """Extract the birth year of the rider from the row in"""
    return rider_row.find_all('td')[dob_col_index].get_text(strip=True)

def extract_rider_time_gap(time_str:str)->int:
    """Takes in a time string from a rider race results and returns the time in seconds
    Args:
        time_str: time string extracted from a results row (str)
    Returns:
        time_gap: time gap from winner in seconds"""
    #if the time string does not have '+' in it and there are digits in the string, it is the winner, gap is 0
    if '+' not in time_str and any(char.isdigit() for char in time_str):
        return 0
    #else if no digits are in the string, just return the string itself
    elif not any(char.isdigit() for char in time_str):
        return time_str
    
    #if there's a '+' in the time string, we have a gap. split on '+' and only take what follows, stripping whitespace
    if '+' in time_str:
        time_str = time_str.split('+')[1].strip()
    #if the time string has two colons in it, we have hours, minutes, seconds. Convert to all seconds
    if time_str.count(':') == 2:
        hours = int(time_str.split(':')[0])
        min = int(time_str.split(':')[1])
        sec = float(time_str.split(':')[2])
        time_sec = timedelta(hours=hours,minutes=min,seconds=sec).total_seconds()
        return time_sec
    #if the time string has one colon in it, we have minutes and seconds. Convert to all seconds
    elif time_str.count(':') == 1:
        min = int(time_str.split(':')[0])
        sec = float(time_str.split(':')[1])
        time_sec = timedelta(minutes=min,seconds=sec).total_seconds()
        return time_sec
    #if there are no colons, we have only seconds. Convert to float
    else:
        return float(time_str)

def parse_rider_row(table_race_result_row:BeautifulSoup,table_head_order:dict)->dict:
    """Extract rider position, name, id, team, team id, and raw time from a row in a race results table.
    Args:
        table_race_result_row: BeautifulSoup tr tag taken from the race results table
        table_head_order: dict with keys 'pos','rider','team','time' and values as the index of the column in the table
    Returns:
        dict with keys 'place','name','id','team','team_id','gap'"""
    rider_result_dict = {}
    #Get the columns in the row
    rider_result_cols = table_race_result_row.find_all('td')
    if len(rider_result_cols) < len(table_head_order.keys()):
        print(f'Error: {len(rider_result_cols)} columns found in the row, expected {len(table_head_order)}')
        return None
    #extract the rider name
    rider_name = rider_result_cols[table_head_order['rider']].get_text(strip=True, separator=' ')
    #Get the rider id
    rider_id = extract_rider_id(rider_result_cols[table_head_order['rider']].find('a').get('href'))
    #Get the rider team
    rider_team = rider_result_cols[table_head_order['team']].get_text(strip=True, separator=' ')
    #Get the rider team id, if it exists
    try:
        rider_team_id = extract_team_id(rider_result_cols[table_head_order['team']].find('a').get('href'))
    except:
        print(f'No team id found for {rider_name}, riding for {rider_team}')
        rider_team_id = None
    #Get the rider place
    rider_place = rider_result_cols[table_head_order['pos']].get_text(strip=True)
    #Get the rider time gap
    rider_gap = extract_rider_time_gap(rider_result_cols[table_head_order['time']].get_text(strip=True))
    #Get the DOB year if it exists
    if table_head_order.get('born',None) is not None:
        dob = rider_result_cols[table_head_order['born']].get_text(strip=True)
    else:
        dob = None
    #Assemble the rider results dict
    rider_result_dict = {'place': rider_place, 'name':rider_name, 'gap':rider_gap,'rider_id':rider_id,'team':rider_team,'team_id':rider_team_id,'dob':dob}
    return rider_result_dict

def extract_race_time(race_page_soup:BeautifulSoup)->float:
    """Extract the total race time in seconds from a race results page.
    Args:
        race_page_soup: BeautifulSoup of page containing results
    Returns
        float of race time in seconds"""
    #find the results table
    #find the results table
    result_table = find_race_result_table(race_page_soup)
    if not result_table:
        print("No results table found for this race")
        return []
    #find the order of the columns in the table
    table_head_order = find_table_head_order(result_table)
    #Extract the first row of the table
    first_row = result_table.find('tbody').find('tr')
    #Get the time column index
    time_column = table_head_order['time']
    #If there isn't a valid row, return none
    if len(first_row.find_all('td')) < len(table_head_order):
        print(f'Error: {len(first_row.find_all("td"))} columns found in the row, expected {len(table_head_order)}')
        return None
    #Extract the time string
    time_str = first_row.find_all('td')[time_column].get_text(strip=True)
    #Extract the time in seconds
    time_str = time_str.strip()
    #If there are two colons in the time string, we have hours, minutes, seconds. Convert to all seconds
    if time_str.count(':') == 2:
        hours = int(time_str.split(':')[0])
        min = int(time_str.split(':')[1])
        sec = float(time_str.split(':')[2])
        time_sec = timedelta(hours=hours,minutes=min,seconds=sec).total_seconds()
        return time_sec
    #If there is one colon in the time string, we have minutes and seconds. Convert to all seconds
    elif time_str.count(':') == 1:
        min = int(time_str.split(':')[0])
        sec = float(time_str.split(':')[1])
        time_sec = timedelta(minutes=min,seconds=sec).total_seconds()
        return time_sec
    #If there are no colons, we have only seconds. Convert to float
    else:
        try:
            float(time_str)
        except:
            print(f'Error converting time string to float: {time_str}')
            return None
        return float(time_str)

def extract_race_date(race_page_soup:BeautifulSoup)->str:
    #find the div tag with id='race' within the body tag, and get the first h2 tag within that; get the text in there
    try:
        date_str = race_page_soup.find('body').find('div',id='race').find('h2').get_text(strip=True, separator=' ')
    except:
        print('Error when pulling the H2 tag text for the race date')
        return None
    #extract the date from the string
    try:
        date_str = re.search(r'\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+\d{4}', date_str).group(0)
    except:
        print('Date string not found in h2 tag text')
        return None
    date_str = re.sub(r'(st|nd|rd|th)', '', date_str)
    try:
        date_obj = datetime.strptime(date_str, '%d %B %Y')
    except:
        print('Error converting date string to datetime object')
        return None
    return date_obj.strftime('%Y-%m-%d')

def extract_results(race_page_soup:BeautifulSoup)->list:
    """Extract the race results from the BeautifulSoup of race results webpage
    Args:
        race_page_soup: BeautifulSoup of page containting results
    Returns:
        list of dicts with rider results"""
    
    #find the results table
    result_table = find_race_result_table(race_page_soup)
    if result_table is None:
        print("No results table found for this race")
        return []
    #find the order of the columns in the table
    table_head_order = find_table_head_order(result_table)
    #Extract all the rider results
    rider_results = [parse_rider_row(row,table_head_order) for row in result_table.find('tbody').find_all('tr')]
    
    return rider_results

