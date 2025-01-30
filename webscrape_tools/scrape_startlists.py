from bs4 import BeautifulSoup
import os
import pickle
from typing import Dict,List,Union
import re
from random import randint
from time import sleep

from webscrape_tools.scrape_client import WebClient
from webscrape_tools.create_race_data import Stage, Race
from data_loading_tools.load_scraped_data import DB_PATH, TOURS

### Tools for extracting startlist
def find_team_tables(soup:BeautifulSoup)->BeautifulSoup:
    """Given a full page soup object, return a list of team startlist tables that have bib numbers as the first column
    Args:
        soup: BeautifulSoup object of the page
    Returns:
        list of BeautifulSoup objects of the team startlist tables"""
        
    #The tables are inside of divs with class='back'
    #Each table has a thead with a tr that has only one th
    #Each table has a tbody that has trs that have two tds. 
    # The first td has text that is 1-3 characters long, all digits
    # The scond td has an a tag with an href that has ?rider= in it
    
    #find all the divs with class='back'
    divs = soup.find_all('div',class_='back')
    #loop through the divs and find the tables where the conditions are met
    tables = []
    for div in divs:
        #get the table 
        table = div.find('table')
        if table:
            one_th_tr_td = False
            two_td_trs = False
            #Check the thead structure for match
            #Each table has a thead with a tr that has only one th
            thead = table.find('thead')
            if thead:
                trs = thead.find_all('tr')
                if len(trs) == 1:
                    ths = trs[0].find_all('th')
                    if len(ths) == 1:
                        one_th_tr_td = True
            #Check the tbody structure for a match
            tbody = table.find('tbody')
            if tbody:
                trs = tbody.find_all('tr')
                #check to see that all the trs have two tds
                for tr in trs:
                    tds = tr.find_all('td')
                    #check to see that the first td has text that is 1-3 characters long, all digits
                    bib_num_text_found = False
                    rider_id_found = False
                    #get the first td text
                    bib_num_text = tds[0].get_text(strip=True).strip()
                    if bib_num_text == '' or bib_num_text is None:
                        continue
                    if all(char.isdigit() for char in bib_num_text):
                        bib_num_text_found = True
                    #check to see that the second td has an a tag with an href that has ?rider= in it
                    a_tag = tds[1].find('a')
                    if a_tag:
                        href = a_tag.get('href')
                        if 'rider.php?r=' in href:
                            rider_id_found = True
                    if bib_num_text_found and rider_id_found:
                        two_td_trs = True
                        break
            if one_th_tr_td and two_td_trs:
                tables.append(table)
                

    return tables

def extract_bib_numbers(team_table:BeautifulSoup)->List[Dict[str,Union[str,int]]]:
    """Given a BeautifulSoup object of a team startlist table, return a dict of bib numbers with rider id and rider name
    Args:
        team_table: BeautifulSoup object of a team startlist table
    Returns:
        dict with bib number, rider id, and rider name"""
        
    #The bib numbers are in the first td of each tr
    #The bib numbers are all digits and 1-3 characters long
    
    #find all the trs in the tbody
    trs = team_table.find('tbody').find_all('tr')
    bib_numbers = []
    for tr in trs:
        tds = tr.find_all('td')
        bib_num_text = tds[0].get_text(strip=True).strip()
        if bib_num_text == '':
            print('Empty bib number found, skipping')
            continue
        #Rider name is the title of the second td
        rider_name = tds[1].get('title')
        #rider id is in the href of the a tag in the second td. It is a sequence of digits that follow r=
        a_tag = tds[1].find('a')
        href = a_tag.get('href')
        rider_id_text = re.search(r'r=(\d+)',href).group(1)
        rider_id_int = int(rider_id_text)
        bib_numbers.append({'bib_number':bib_num_text,'rider_id':rider_id_int,'rider_name':rider_name})
    
    return bib_numbers

def extract_bibs_from_startlist_soup(soup:BeautifulSoup)->List[Dict[str,Union[str,int]]]:
    """Given a full page soup object, return a dict of bib numbers with rider id and rider name
    Args:
        soup: BeautifulSoup object of the page
    Returns:
        dict with bib number, rider id, and rider name"""
        
    #find the team tables
    team_tables = find_team_tables(soup)
    if team_tables == []:
        print('No team tables found')
        return []
    bibs = []
    for table in team_tables:
        bibs.extend(extract_bib_numbers(table))
    return bibs

### Update a race file
def update_race_object(race:Union[Race,Stage],bib_number_list:List[Dict[str,Union[str,int]]])->Union[Race|Stage]:
    """Update a given race object's results with the startlist bib numbers
    Args:
        race: a Race or Stage object
    Returns
        an updated race or stage object"""
    
    results = race.results
    if results is None or len(results)<5:
        print('No results found')
        return race
    for result in results:
        #get the rider id
        if not isinstance(result,dict):
            continue
        rider_id_res = result.get('rider_id',None)
        if rider_id_res is None:
            print('No rider id in result dict, cannot match to bib number')
            continue
        rider_id_res = int(rider_id_res)
        match = None
        for bib_dict in bib_number_list:
            if bib_dict.get('rider_id',None) == rider_id_res:
                match = bib_dict
        if match is None:
            print(f'No match found for rider id {rider_id_res}')
            continue
        result['bib_number'] = match.get('bib_number',None)
    race.results = results
    return race

def scrape_and_add_bib_numbers_to_race(race:Race,client:WebClient)->Race:
    """Scrape and add bib numbers to a race object"""
    #get the race url
    start_list_url = race.url + '&k=8'
    #get the startlist page
    response = client.get(start_list_url)
    soup = BeautifulSoup(response.text,'html.parser')
    #check for bib numbers 
    bib_list = extract_bibs_from_startlist_soup(soup)
    if bib_list == []:
        print('No team tables found')
        return race
    #if there are results, update the results
    if race.results is not None and len(race.results) > 5:
        updated_race = update_race_object(race=race,bib_number_list=bib_list)
    else:
        updated_race = race
    if not race.stage_race:
        return updated_race
    #If there are stages, update each stage and then replace the stages list
    updated_stages = []
    for stage in updated_race.stages:
        updated_stage = update_race_object(race=stage,bib_number_list=bib_list)
        updated_stages.append(updated_stage)
    updated_race.stages = updated_stages
    return updated_race

def add_bibs_to_tour(tour_dir_path:str)->None:
    """Given a tour directory, add bib numbers to all races in the tour directory"""
    #find the txt file in the directory, read the race name, url
    #get the files that end in .txt in the tour_dir_path
    txt_files = [f for f in os.listdir(tour_dir_path) if f.endswith('.txt')]
    if len(txt_files) == 0:
        print("No txt files found in the directory to use as a list")
    race_list_file = txt_files[0]
    with open(os.path.join(tour_dir_path,race_list_file),'r') as file:
        lines = file.readlines()
    #Create the scraping client
    client = WebClient("https://firstcycling.com")
    for line in lines:
        #get the race name, which is the first part of the line in front of the comma
        race_name = line.split(',')[0]
        #load the pickle file in the tour_dir_path what starts with that name
        with open(os.path.join(tour_dir_path,f"{race_name}.pkl"),'rb') as f:
            race_obj = pickle.load(f)
        #scrape the bib numbers
        bibs_added_race_obj = scrape_and_add_bib_numbers_to_race(race=race_obj,client=client)
        #save the race_obj to a pickle file in the tour_dir_path
        with open(os.path.join(tour_dir_path,f"{race_name}.pkl"),'wb') as f:
            pickle.dump(bibs_added_race_obj,f)
        sleep(randint(1,4))
    client.close()

def add_bibs_to_year(year_dir_path:str)->None:
    """Given a year directory, add bib numbers to all races in all tours"""
    for tour in TOURS:
        tour_dir_path = os.path.join(year_dir_path,tour)
        add_bibs_to_tour(tour_dir_path)

def add_bibs_to_race_db(db_path:str=DB_PATH)->None:
    """Given a db path, add bib numbers to all races"""
    year_dirs = [f for f in os.listdir(db_path) if os.path.isdir(os.path.join(db_path,f)) and len(f) == 4]
    for year in year_dirs:
        year_dir_path = os.path.join(db_path,year)
        add_bibs_to_year(year_dir_path)