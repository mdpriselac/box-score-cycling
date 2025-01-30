#We can access top level tours by using the t input variable to the url
#y=year
#t=tour
#you can always but in t=1 and get redirected to the top level tour of that year
#t21 is the second level, currently the .Pro level

#We get Date, Cat, Race (name) columns.

#Let's create a database
#Riders database
    #Each has a name, an id, and a list of years.
    #Each racer year has a set of properties:
        # team
        # race days
        # list of race results
            # Each race result has a race name, race id, stage number (if necessary), position, time gap, race date 
                #Race date can be parsed from an h2 tag. Formatted ,/d{1,2}[[th][rd][st]] Full month name 4 digit year,
            #
#Race database


### Ok the basic way this works is it creates a directory for the year, then a directory for each tour level.
### From there we have a text file. Each line in the text file is a race name and url.
### We can create a Race object from the create_race_data.py file for each line and then use the populate_race() method. It will pull all the data, including stages for stage races.
### That gives us a model. We can then save that model to a file to be loaded in the future. Or we could just add it to a database.
### However, what we can now do is progressively save a race at a time and compare the saved models in a directory with the names and urls in the txt file at the top of the directory to see our progress.


import os
from bs4 import BeautifulSoup
from time import sleep
from random import randint

from cycling_project.webscrape_tools.scrape_client import WebClient


### Defining the functions to extract race names and urls
def find_race_list_table(soup:BeautifulSoup)->None:
    """
    Finds the table from a soup object that contains race information for a year and tour level.
    Args:
        soup: BeautifulSoup object of a page
    Returns:
        BeautifulSoup table tag
    """
    #Find the table that has a thead that has a tr that has th tags that have text containing Date, Cat, Race and Winner text
    tables = soup.find_all('table')
    for table in tables:
        thead = table.find('thead')
        if thead:
            ths = thead.find_all('th')
            date_found = False
            cat_found = False
            race_found = False
            #Check through the ths to see if they contain the text we want and mark the tracking bool true
            for th in ths:
                if 'date' in th.text.lower():
                    date_found = True
                if 'cat' in th.text.lower():
                    cat_found = True
                if 'race' in th.text.lower():
                    race_found = True
            #If all are found, return the table
            if date_found and cat_found and race_found:
                return table
            else:
                continue
        else:
            continue
    print("No Race table found for this page")
    return None

def find_race_data_column(table_tag:BeautifulSoup)->int:
    """
    Finds the index of the race data column in a table that has already been identified as listing races.
    Args:
        table_tag: BeautifulSoup table tag
    Returns:
        int the index of Race column in the table that has the race name and url
    """
    #In the thead tag, get the tr, and then find the th tag that has 'Race' in it, return its index
    thead = table_tag.find('thead')
    if not thead:
        print("No thead tag found in this table, can't find winner column")
        return None
    tr = thead.find('tr')
    ths = tr.find_all('th')
    for i,th in enumerate(ths):
        if 'race' in th.text.lower():
            return i
    print("No Race Column found in this table")
    return None

def extract_races(soup:BeautifulSoup)->list:
    """
    Extracts a list of race names and urls from a soup object that contains a table of race information for a given year and tour level.
    Args:
        soup: BeautifulSoup object of a page
    Returns:
        List a list of tuples. The first element is a race name, the second element is the race webpage url.
    """
    #Find the key table
    race_table = find_race_list_table(soup)
    if race_table is None:
        print("No Race table found")
        return None
    #Get the race column index
    race_col_index = find_race_data_column(race_table)
    if race_col_index is None:
        print("No Race column found in the race table")
        return None
    #Get the rows of the table
    race_rows = race_table.find('tbody').find_all('tr')
    #Extract the data from the rows. We want race Name and URL. Both are in the a tag inside the td tag. The name is the title attribute, the url is the href
    races = []
    for row in race_rows:
        cols = row.find_all('td')
        race_col = cols[race_col_index]
        try:
            a_tag = race_col.find('a')
            race_name = a_tag.get('title')
            race_url = f"https://firstcycling.com/{a_tag.get('href')}"
            races.append((race_name,race_url))
        except Exception as e:
            print(f"Error extracting race name and url: {e}")
            continue
    return races


#Set the tour ids
#World Tour level, division 1, top level
world_tour_id = 1
#.Pro level, division 2, second level
pro_tour_id = 21
#.1 level, division 3, third level
dot_one_tour_id = 22

def create_race_year_db(year:str,race_data_dir:str='./')->None:
    """
    Creates a directory structure for a given year and saves a list of races and their webpage urls for all three tour levels in that year. Optionally you can specify the base directory where the directory structure will be created.
    Args:
        year: four digit year as a string
        race_data_dir: base directory where the year directory will be created. Default is the current directory.
    Returns:
        Nothing. However, it will create a subdirectory for the year. Within th year subdirectory it will create 3 subdirectories, one for each tour level. Within each tour level subdirectory it will create a text file. Each line in the text file will be a name and url for a race in that year and tour level."""
    #Check if there's a directory for the year, create it if not
    year_dir = os.path.join(race_data_dir,year)
    if not os.path.exists(year_dir):
        os.makedirs(year_dir)
    #Check if there are directories for wt, pro, and d1 divisions, create them if not
    wt_dir = os.path.join(year_dir,'wt')
    pro_dir = os.path.join(year_dir,'pro')
    d1_dir = os.path.join(year_dir,'d1')
    if not os.path.exists(wt_dir):
        os.makedirs(wt_dir)
    if not os.path.exists(pro_dir):
        os.makedirs(pro_dir)
    if not os.path.exists(d1_dir):
        os.makedirs(d1_dir)
    #Get the top level tours for the year
    wt_url = f"https://firstcycling.com/race.php?y={year}&t={world_tour_id}"
    pro_url = f"https://firstcycling.com/race.php?y={year}&t={pro_tour_id}"
    d1_url = f"https://firstcycling.com/race.php?y={year}&t={dot_one_tour_id}"
    client = WebClient("https://firstcycling.com")
    #Get the wt races and save the races to a csv with no headers, race_name, race_url. the file should be called wt.txt
    print(f"Getting World Tour Race List for {year}")
    wt_response = client.get(wt_url)
    wt_soup = BeautifulSoup(wt_response.text, 'html.parser')
    wt_races = extract_races(wt_soup)
    if len(wt_races) == 0:
        print(f"No World Tour Races found for {year}")
    else:
        with open(os.path.join(wt_dir,'wt.txt'),'w') as wt_file:
            for race, url in wt_races:
                wt_file.write(f"{race},{url}\n")
        print(f"Saved World Tour Race List for {year}")
    sleep(randint(1,3))
    #Get the .Pro races and save the races to a csv with no headers, race_name, race_url. the file should be called pro.txt
    print(f"Getting .Pro Races for {year}")
    pro_response = client.get(pro_url)
    pro_soup = BeautifulSoup(pro_response.text, 'html.parser')
    pro_races = extract_races(pro_soup)
    if len(pro_races) == 0:
        print(f"No .Pro races found for {year}")
    else:
        with open(os.path.join(pro_dir,'pro.txt'),'w') as pro_file:
            for race, url in pro_races:
                pro_file.write(f"{race},{url}\n")
        print(f"Saved .Pro races for {year}")
    sleep(randint(1,3))
    #Get the .1 Races
    print(f"Getting .1 races for {year}")
    d1_response = client.get(d1_url)
    d1_soup = BeautifulSoup(d1_response.text, 'html.parser')
    d1_races = extract_races(d1_soup)
    if len(d1_races) == 0:
        print(f"No .1 races found for {year}")
    else:
        with open(os.path.join(d1_dir,'d1.txt'),'w') as d1_file:
            for race,url in d1_races:
                d1_file.write(f"{race},{url}\n")
        print(f"Saved .1 races for {year}")
    print(f"Finished getting all race lists for {year}")
    
if __name__ == "__main__":
    create_race_year_db(year='2024',race_data_dir='~/cycling_scraped_data')
