import pickle
import os
from datetime import datetime,timedelta
from bs4 import BeautifulSoup
from time import sleep
from random import randint

from dotenv import load_dotenv

from cycling_project.webscrape_tools.scrape_client import WebClient
from cycling_project.data_loading_tools.load_scraped_data import load_tour_path
from cycling_project.webscrape_tools.find_races import find_race_list_table,find_race_data_column
from cycling_project.webscrape_tools.find_races import DB_PATH

#Set the tour ids
#World Tour level, division 1, top level
world_tour_id = 1
#.Pro level, division 2, second level
pro_tour_id = 21
#.1 level, division 3, third level
dot_one_tour_id = 22

tour_name_id_map = {'wt':1,'pro':21,'d1':22}


def find_date_column(table_tag:BeautifulSoup)->int:
    """
    Find the index of the column in the table that has the date or date range of a race.
    Args:
        table_tag: BeautifulSoup table tag for the race data
    Returns:
        int the index of the date column in the table that has the date or date range for a race."""
    #In the thead tag, get the tr, and then find the th tag that has 'Date' in it, return its index
    thead = table_tag.find('thead')
    if not thead:
        print("No thead tag found in this table, can't find date column")
        return None
    tr = thead.find('tr')
    ths = tr.find_all('th')
    for i,th in enumerate(ths):
        if 'date' in th.text.lower():
            return i
    print("No Date Column found in this table")
    return None


def extract_race_date_race_name(race_row:BeautifulSoup,date_col_ind:int,name_col_ind:int,year:int)->tuple:
    """Extract a race date (or date range) from a soup object that contains a table of race information for a given year and tour level.
    Args:
        race_row: BeautifulSoup object of a row in a table with race date information.
        year: the year of the tour
        date_col_ind: the index of the column in the table that has the date
        name_col_ind: the index of the column in the table that has the race name
    Returns:
        tuple containing the race date and race name. The date is a datetime object or range of datetime objects, the name is a string. The date will be returned as a list of datetime objects. If there's one, it's a one day race. Else it's a range of dates."""
    
    date_column = race_row.find_all('td')[date_col_ind]
    #get the text in the date_column
    date_text = date_column.get_text(strip=True)
    #if the date has a '-' in it, it is a date range, split on that
    if '-' in date_text:
        date_range = date_text.split('-')
        #strip the whitespace
        date_range = [date.strip() for date in date_range]
        #each date is a string MM.dd. Add YEAR to the start of it and convert to date time object
        date_range = [datetime.strptime(f"{year}.{date}",'%Y.%d.%m') for date in date_range]
    else:
        #Add YEAR to the start of it and convert to date time object
        date_range = [datetime.strptime(f"{year}.{date_text.strip()}",'%Y.%d.%m')]
    #Get the race name
    name_column = race_row.find_all('td')[name_col_ind]
    name_text = name_column.get_text(strip=True)
    #return the date range and the name
    return date_range,name_text
    

def extract_race_dates(table_tag:BeautifulSoup,year:int,date_col_ind:int,name_col_ind:int)->list:
    """Extract all races and dates into a list of tuples from a soup object that is a table tag"""
    
    rows = table_tag.find('tbody').find_all('tr')
    races_w_dates = []
    for race_row in rows:
        dates,name = extract_race_date_race_name(race_row=race_row, date_col_ind=date_col_ind, name_col_ind=name_col_ind, year=year)
        races_w_dates.append((dates,name))
    return races_w_dates 
    
def scrape_races_w_dates(tour_path:str)->list:
    tour = tour_path.split('/')[-1]
    tour_id = tour_name_id_map[tour]
    year = tour_path.split('/')[-2]
    #print(f"Scraping {tour}, {year}, id: {tour_id}")
    race_list_url = f"https://firstcycling.com/race.php?y={year}&t={tour_id}"
    #print(race_list_url)
    client = WebClient("https://firstcycling.com/")
    resp = client.get(race_list_url)
    soup = BeautifulSoup(resp.content,'html.parser')
    client.close()
    race_info_table = find_race_list_table(soup)
    if race_info_table is None:
        print(f"No race table found for {tour}, {year}")
        return None
    date_col_ind = find_date_column(race_info_table)
    name_col_ind = find_race_data_column(race_info_table)
    if date_col_ind is None or name_col_ind is None:
        print(f"Could not find date or name column for {tour}, {year}")
        return None
    races_w_dates = extract_race_dates(table_tag=race_info_table,year=int(year),date_col_ind=date_col_ind,name_col_ind=name_col_ind)
    
    return races_w_dates

def verify_race_date(race,race_date_list):
    #check if we have a race in the race_date list
    race_dates = None
    for dates,rname in race_date_list:
        if race.name.strip() == rname.strip():
            race_dates = dates
            race_name_l = rname
    if race_dates is None:
        print(f"Could not find {race.name} in the race date list")
    #Check if the race is a stage race or not
    if not race.stage_race:
        #If it isn't a stage race, it should have a date. See if the date is None or a string. If it's a string, try converting to YYYY-MM-DD datetime object. If that fails or the object is none, update the object with a string of the date from the date time object list
        if race.date is None:
            race.date = race_dates[0].strftime('%Y-%m-%d')
        elif isinstance(race.date,str):
            try:
                datetime.strptime(race.date,'%Y-%m-%d')
            except:
                race.date = race_dates[0].strftime('%Y-%m-%d')
    
    else:
        #set the overall race object stage equal to the last date in the date range
        if race.date is None:
            race.date = race_dates[-1].strftime('%Y-%m-%d')
        elif isinstance(race.date,str):
            try:
                datetime.strptime(race.date,'%Y-%m-%d')
            except:
                race.date = race_dates[-1].strftime('%Y-%m-%d')
        #Next work through each stage. For each stage, verify the date, then increment the date counter by one day
        latest_date = race_dates[0]
        for stage in race.stages:
            #If the stage is a GC, ie it has gc in the stage.name, then set the date to the last date in the date range.
            if 'gc' in stage.name.lower():
                if stage.date is None:
                    stage.date = race_dates[-1].strftime('%Y-%m-%d')
                elif isinstance(stage.date,str):
                    try:
                        datetime.strptime(stage.date,'%Y-%m-%d')
                    except:
                        stage.date = race_dates[-1].strftime('%Y-%m-%d')
                continue
            if stage.date is None:
                #If the stage date is None, set it to the latest date
                stage.date = latest_date.strftime('%Y-%m-%d')
            elif isinstance(stage.date,str):
                try:
                    #If the stage has a date string, try converting it to a date object. If that works, set the latest date equal to the stages date. If it doesn't work, set the stage date to the latest date
                    stage_date_obj = datetime.strptime(stage.date,'%Y-%m-%d')
                    latest_date = stage_date_obj
                except:
                    stage.date = latest_date.strftime('%Y-%m-%d')
            #Increment the stage by a day. This won't exactly work for grand tours that have rest days but it's close enough for our purposes.
            latest_date += timedelta(days=1)
    #Now that we've updated the stages, we can return the race object
    return race
             

def verify_dates_for_tour(tour_path:str):
    #Get all of the race dates
    try:
        races_w_dates = scrape_races_w_dates(tour_path)
    except Exception as e:
        return None
        print(f"Error scraping tour races page for {tour_path}: {e}")
    if races_w_dates is None:
        print(f"No information could be scraped for {tour_path}")
        return None
    
    #Load the race data
    tour_db = load_tour_path(tour_path)
    if tour_db is None:
        print(f"Could not load tour data for {tour_path}")
    
    for race in tour_db.races:
        try:
            verify_race_date(race=race,race_date_list=races_w_dates)
        except:
            print(f"Error verifying dates for {tour_path}")
    return tour_db

def save_date_verified_tour(tour_path:str):
    tour_db = verify_dates_for_tour(tour_path)
    if tour_db is None:
        print(f"Could not verify dates for {tour_path}")
        return None
    if len(tour_db.races) == 0:
        print(f"No races found in the tour at {tour_path}")
        return None
    #get a list of all race pkl files in the tour path directory
    race_files = [f for f in os.listdir(tour_path) if f.endswith('.pkl')]
    for race in tour_db.races:
        #check that there's a pkl file of the form race.name.pkl in the tour directory. if there is overwrite it.
        race_file = f"{race.name}.pkl"
        if race_file in race_files:
            with open(os.path.join(tour_path,race_file),'wb') as f:
                pickle.dump(race,f)
        else:
            print(f"Could not find {race.name} in {tour_path}")

def save_year_verified_tour(year_path:str):
    wt_path = os.path.join(year_path,'wt')
    pro_path = os.path.join(year_path,'pro')
    d1_path = os.path.join(year_path,'d1')
    save_date_verified_tour(wt_path)
    sleep(randint(1,3))
    save_date_verified_tour(pro_path)
    sleep(randint(1,3))
    save_date_verified_tour(d1_path)
    sleep(randint(1,3))

def clean_db_dates(db_path=DB_PATH):
    #Get all of the year directories
    year_dirs = [f for f in os.listdir(db_path) if os.path.isdir(os.path.join(db_path,f)) and len(f) == 4]
    for year in year_dirs:
        year_path = os.path.join(db_path,year)
        save_year_verified_tour(year_path)
        sleep(randint(1,3))