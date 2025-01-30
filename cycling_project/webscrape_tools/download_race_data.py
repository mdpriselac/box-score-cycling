import os
from random import randint
from time import sleep
import pickle

from cycling_project.webscrape_tools.create_race_data import Race

TOURS = ['wt','pro','d1']

def read_race_list(tour_folder_path:str)->list:
    """
    Reads the .txt file in a directory and returns a list of name,url tuples for races.
    Args:
        tour_folder_path: the to a tour level folder within a year folder within a base race db folder
    Returns:
        a list of name,url tuples for races at that tour level in that year."""
    #get the list of .txt files in the tour_folder_path
    txt_file = [f for f in os.listdir(tour_folder_path) if f.endswith('.txt')][0]
    race_list = []
    #read the txt_file line by line, splitting by comma. 
    with open(os.path.join(tour_folder_path,txt_file),'r') as file:
        for line in file:
            line = line.strip().split(',')
            #if less than 2 elements, throw an error that reports the problematic line and move to next one
            if len(line) == 2:
                name = line[0]
                url = line[1]
                race_list.append((name,url))
            elif len(line) < 2:
                print(f'Error: {line} is missing either a name or a url')
            elif len(line) > 2:
                print(f'Error: {line} has extra commas')
    return race_list

def create_to_scrape_list_tour(tour_folder_path:str)->list:
    #get all the races in the tour folder
    races_to_scrape = read_race_list(tour_folder_path)
    #Get a list of .pkl files in the tour folder. They'll be saved with the format of race_name.pkl
    scraped_races = [f for f in os.listdir(tour_folder_path) if f.endswith('.pkl')]
    scraped_race_names = [f.split('.')[0] for f in scraped_races]
    #return a list of races to scrape by comparing the scraped_race names with the first obejct in the races_to_scrape list. The races to scrape are in races_to_scrape but not scraped_race_names
    to_scrape = [(race_name,url) for race_name,url in races_to_scrape if race_name not in scraped_race_names]
    return to_scrape
      
def read_year_db(year_folder_path:str)->dict:
    """
    Reads the year folder and returns a dictionary of tour levels with lists of races at that level in the year.
    Args:
        year_folder_path: the path to a year folder within a base race db folder
    Returns:
        a dictionary of tour levels with lists of races at that level in the year."""
    #create the tour paths by joining each tour name as a directory path to the year_folder_path
    tour_paths = [os.path.join(year_folder_path,tour) for tour in TOURS]
    #create a dictionary to hold the tour data
    year_db = {}
    #loop through tours and get a list of races for each tour
    for tour_path in tour_paths:
        tour_name = tour_path.split('/')[-1]
        year_db[tour_name] = read_race_list(tour_path)
    return year_db

def create_to_scrape_list_year(year_folder_path:str)->dict:
    """
    Reads the year folder and returns a dictionary of tour levels with lists of races remaining to scrape in that year for each level.
    Args:
        year_folder_path: the path to a year folder within
    Returns:
        a dictionary of tour levels each of which has a list of races to scrape for that tour level in that year."""
    #create the tour paths by joining each tour name as a directory path to the year_folder_path
    tour_paths = [os.path.join(year_folder_path,tour) for tour in TOURS]
    #create a dictionary to hold the tour data
    year_db = {}
    #loop through tours and get a list of races to scrape for each tour
    for tour_path in tour_paths:
        tour_name = tour_path.split('/')[-1]
        year_db[tour_name] = create_to_scrape_list_tour(tour_path)
    return year_db
    
def read_db(base_db_folder:str)->dict:
    """
    Reads the base db folder and returns a dictionary of years with a dictionary of tour levels with a list of races at that level in that year.
    Args:
        base_db_folder: the path to the base db folder
    Returns:
        a dictionary of years each of which has a dictionary of tour levels each of which has a list of races at that level."""
    #get the list of year folders in the base_db_folder
    year_folders = [f for f in os.listdir(base_db_folder) if os.path.isdir(os.path.join(base_db_folder,f)) and len(f) == 4]
    #create a dictionary to hold the year data
    db = {}
    #loop through years and get a dictionary of tour levels with
    for year_folder in year_folders:
        year_path = os.path.join(base_db_folder,year_folder)
        db[year_folder] = read_year_db(year_path)
    return db

def create_to_scrape_list_db(base_db_folder:str)->dict:
    """
    Reads the base db folder and returns a dictionary of years with a dictionary of tour levels with a list of races to scrape for that tour level in that year.
    Args:
        base_db_folder: the path to the base db folder
    Returns:
        a dictionary of years each of which has a dictionary of tour levels each of which has a list of races to be scraped in that year."""
    #get the list of year folders in the base_db_folder
    year_folders = [f for f in os.listdir(base_db_folder) if os.path.isdir(os.path.join(base_db_folder,f)) and len(f) == 4]
    #create a dictionary to hold the year data
    db = {}
    #loop through years and get a dictionary of tour levels with
    for year_folder in year_folders:
        year_path = os.path.join(base_db_folder,year_folder)
        db[year_folder] = create_to_scrape_list_year(year_path)
    return db


def update_tour_folder(tour_folder_dir:str)->None:
    """Given a tour folder directory, scrapes and saves any races that have not yet been scraped.
    Args:
        tour_folder_dir: the path to a tour folder within a year folder within a year folder within a base race directory.
    Returns:
        None, but will create and save race objects to a pkl file in the tour folder."""
    #Get a list of races to scrape in this tour folder
    to_scrape = create_to_scrape_list_tour(tour_folder_dir)
    #loop through the lists to scrape, create a race object, call populate_race on it, and save it as a pkl
    for race_name,url in to_scrape:
        race_obj = Race(name=race_name,url=url)
        race_obj.populate_race()
        race_obj.category = tour_folder_dir.split('/')[-1]
        #save the race_obj as a pick in this tour folder with the format race_name.pkl
        with open(os.path.join(tour_folder_dir, f"{race_name}.pkl"), 'wb') as f:
            pickle.dump(race_obj, f)
        print(f"Saved {race_name} to {tour_folder_dir}")
        sleep(randint(2,4))
    return None

def remove_duplicates_across_tours(year_folder_dir:str)->None:
    """Given a year folder directory, removes any duplicate races that are in multiple tours. Defaults to keeping the race in a higher tour.
    Args:
        year_folder_dir: the path to a year folder within
    Returns:
        None, but will remove duplicates from pro and d1 if they appear in a higher list"""
    #get the wt race names from the txt file in the wt folder
    wt_dir = os.path.join(year_folder_dir,'wt')
    wt_race_file = [f for f in os.listdir(wt_dir) if f.endswith('.txt')][0]
    wt_race_names = []
    with open(os.path.join(wt_dir,wt_race_file),'r') as f:
        for line in f:
            line = line.strip().split(',')
            race_name = line[0]
            wt_race_names.append(race_name)
    #rewrite pro text file to remove duplicates that are in the wt list
    pro_dir = os.path.join(year_folder_dir,'pro')
    pro_text_file = [f for f in os.listdir(pro_dir) if f.endswith('.txt')][0]
    #read in the pro text file
    pro_races = []
    with open(os.path.join(pro_dir,pro_text_file),'r') as f:
        for line in f:
            line = line.strip().split(',')
            pro_races.append(line)
    pro_race_names = [race_name for race_name,url in pro_races]
    clean_pro_races = [(race_name,url) for race_name,url in pro_races if race_name not in wt_race_names]
    #rewrite the pro text file
    with open(os.path.join(pro_dir,pro_text_file),'w') as f:
        for race_name,url in clean_pro_races:
            f.write(f"{race_name},{url}\n")
    #rewrite d1 text file to remove duplicates that are in the wt or pro list
    d1_dir = os.path.join(year_folder_dir,'d1')
    d1_text_file = [f for f in os.listdir(d1_dir) if f.endswith('.txt')][0]
    d1_races = []
    with open(os.path.join(d1_dir,d1_text_file),'r') as f:
        for line in f:
            line = line.strip().split(',')
            d1_races.append(line)
    clean_d1_races = [(race_name,url) for race_name,url in d1_races if race_name not in wt_race_names and race_name not in pro_race_names]
    #rewrite the d1 text file
    with open(os.path.join(d1_dir,d1_text_file),'w') as f:
        for race_name,url in clean_d1_races:
            f.write(f"{race_name},{url}\n")
    print(f"Removed duplicates from {year_folder_dir}")
    return None
    


def update_year_folder(year_folder_dir:str)->None:
    """Given a year folder directory, scrapes and saves any races in each tour folder that have yet to be scraped
    Args: 
        year_folder_dir: the path to a year folder within a base race db directory
    Returns:
        None but will systematically scrape all remaining races within each tour folder of the year folder."""
    #remove duplicates from pro and d1
    remove_duplicates_across_tours(year_folder_dir)
    #get the tour directories in the year folder
    tour_directories = [os.path.join(year_folder_dir,tour) for tour in TOURS]
    for tour_dir in tour_directories:
        print(f"Updating {tour_dir}")
        update_tour_folder(tour_dir)
        print(f"Finished updating {tour_dir}")
    return None

def update_db(base_db_folder:str)->None:
    """Given a base db folder, scrapes and saves any races in each tour folder of each year folder that have yet to be scraped.
    Args:
        base_db_folder: the path to a base db folder
    Returns:
        None but will systematically scrape all remaining races within each tour folder of each year folder of the base db folder."""
    year_directories = [os.path.join(base_db_folder,year) for year in os.listdir(base_db_folder) if os.path.isdir(os.path.join(base_db_folder,year)) and len(year) == 4]
    for year_dir in year_directories:
        print(f"Updating {year_dir}")
        update_year_folder(year_dir)
        print(f"Finished updating {year_dir}")
    return None
default_race_db_path = '~/cycling_scraped_data'
if __name__ == '__main__':
    #update the full db
    update_db(base_db_folder=default_race_db_path)
    