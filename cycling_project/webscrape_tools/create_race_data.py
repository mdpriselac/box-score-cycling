from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from dataclasses import dataclass
import re
from random import randint
from time import sleep
from datetime import datetime

from cycling_project.webscrape_tools.scrape_client import WebClient
from cycling_project.webscrape_tools.get_race_results import extract_race_time, extract_results, extract_race_date

def stage_finder(soup):
    #check for a selectbox that has id=stageSelect
    select = soup.find('select',id='stageSelect')
    if select:
        return select
    else:
        #get all the select boxes, see if any of their text has the phrase 'GC' or 'Stage:' in it
        for select in soup.find_all('select'):
            for option in select.find_all('option'):
                if 'Stage:' in option.text:
                    return select
    return None

def extract_stages_w_links(soup):
    #find all the options in the select box
    select = stage_finder(soup)
    if select is None:
        print('No stages found for this race')
        return None
    options = select.find_all('option')
    return {option.text:option.get('value') for option in options}

#create a dataclass for stages. It should have a stage name, stage url, race time, list of rider results
@dataclass
class Stage:
    name: str
    url: str
    fc_race_id: Optional[int] = None
    race: Optional[str] = None
    year: Optional[int] = None
    time: Optional[float] = None #this will be removed over time
    race_time: Optional[float] = None
    date: Optional[str] = None
    results: List[Dict] = None
    category: Optional[str] = None


#create a dataclass for race. It should have a name, url, stage_race indicator, results, optional list of stage objects
@dataclass
class Race:
    name: str
    url: str
    year: Optional[int] = None
    date: Optional[datetime] = None
    category: Optional[str] = None
    stage_race: Optional[bool] = False
    results: Optional[List[Dict]] = None
    race_time: Optional[float] = None
    stages: Optional[List[Stage]] = None
    fc_race_id: Optional[int] = None
    
    def populate_race(self):
        client = WebClient("https://firstcycling.com")
        try:
            print(f'Starting to scrape {self.name} at {self.url}')
            #race id pattern: race_id comes after race.php?r= and before &y=
            race_id = re.search(r'race.php\?r=(\d+)&', self.url).group(1)
            self.fc_race_id = race_id
            race_year = re.search(r'&y=(\d+)', self.url).group(1)
            try:
                self.year = int(race_year.strip())
            except:
                print(f"Error converting year to int for {self.name}")
            clean_url = f"https://firstcycling.com/race.php?r={race_id}&y={race_year}"
            response = client.get(clean_url)
            soup = BeautifulSoup(response.text, 'html.parser')
            #Get the results
            try:
                self.results = extract_results(soup)
            except:
                print(f"Error finding results for {self.name}")
            #Get the race time
            try:
                self.race_time = extract_race_time(soup)
            except:
                print(f"Error finding winning time  for {self.name}")
            #check for stage links
            try:
                stages = extract_stages_w_links(soup)
            except:
                print(f"Error finding stages for {self.name}")
            if stages:
                print(f"Found {len(stages)} stages for {self.name}")
                self.stage_race = True
                self.stages = []
                for stage_name, stage_url in stages.items():
                    stage_url = f"https://firstcycling.com/race.php?r={race_id}&y={race_year}&e={stage_url.strip()}"
                    print(f"Starting to scrape {stage_name} at {stage_url}")
                    #Create the stage object
                    stage = Stage(name=stage_name, url=stage_url,race=self.name)
                    #Populate the fields directly from parent race
                    stage.category = self.category
                    stage.year = self.year
                    stage.fc_race_id = self.fc_race_id
                    #Pull the site
                    stage_resp = client.get(stage_url)
                    #Create the soup
                    stage_soup = BeautifulSoup(stage_resp.text, 'html.parser')
                    #Start parsing the stage
                    try:
                        stage.time = extract_race_time(stage_soup)
                    except:
                        print(f"Error finding winning time for {stage_name}")
                    try:
                        stage.results = extract_results(stage_soup)
                    except:
                        print(f"Error finding results for {stage_name}")
                    try:
                        stage.date = extract_race_date(stage_soup)
                    except:
                        print(f"Error finding date for {stage_name}")
                    
                    self.stages.append(stage)
                    sleep(randint(1,3))
                print(f"Finished scraping all stages for {self.name}")
            else:
                print(f"No stages found for {self.name}, one day race")
                try:
                    self.date = extract_race_date(soup)
                except:
                    print(f"Error finding date for {self.name}")
        except Exception as e:
            print(f"Error processing {self.name}: {e}")
        finally:
            client.close()