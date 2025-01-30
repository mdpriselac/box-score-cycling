# File Overview

## Scraping Tools
- scrape_client.py
    - Basic role: Houses the webcliet used to scrape pages.
    - Key Import from this file: 
        - WebClient class
            - Brief Description: httpx based web client. Webclient.get() is the key method. Has built in minimum request interval tha tcan be set with the .min_request_interval attribute. Set headers with .default_headers attribute

## Creating a File Structure and List of Races to Be Scraped

- find_races.py
    - Basic role: Houses the functions for identifying lists of races and their urls by year and tour level (world tour, .Pro and .1 (and their equivalents back in time))
    - Key import from this file: 
        - create_race_year_db function.
            - Brief Description: Function takes a year and base directory as inputs and creates a file structure for housing race data by year and tour level. Also creates a list within each sub directory of all races in that tour/year and their urls. These are stored in text files as name,url tuples on each line. Create Race objects (from create_race_data.py) from each line and then call their populate_race method to scrape a race.

## Scraping Race Results

- get_race_results.py
    - Basic role: a set of functions for extracting all relevant data about a race from its page. 
    - Key import: extract_results function
        - Brief overview: Given the Beautiful Soup of a race page, creates a list of dictionaries that contain rider info for that race.
    - Key import: extract_race_date, extract_race_time functions. 
        - Brief overview: Gets the total time of the race (in seconds) and a string representation of the race date.

- create_race_data.py
    - NOTE: CONSIDER CHANGING NAME TO FOCUS ON 'RESULT' INSTEAD OF GENERAL RACE
    - Basic role: Create an object to represent a race by passing in a race name and url for the race. These objects then scrape their webpages to populate their date.
    - Key Import: Race class. 
        - Brief overview: This class is created with a race name and url. Calling the populate_race method will then scrape the race (and all stages) to create an object with a date, tour category level, stage_race indicator, race_time, list of stages, the first_cycling id, and results. The results is a list of dictionaries that contain rider information.

## Scraping Startlist Data
This is useful for generating predictions. Get a race, get rider startlist information.

Remember to include Race bib numbers in prediction data. They contain information relevant to outcomes.

- get_startlist.py
    - Basic role: take a race id (firstcycling based race id) and year (four digit) and generate a list of teams and riders.
    - Key import: get_start_list function. Give it the first_cycling race_id and year you want and it will scrape the page to generate a list of Team objects that have a rider list of Rider objects, each of which are defined in the parse_tools.py file.
    - Can run the function by calling the file from the command line and passing the id and year variables in that order as arguments.

- parse_tools.py
    - NOTE: RENAME THIS MODULE TO REFLECT STARTLIST FOCUS (startlist_parse_tools?)
    - NOTE 2: CONSIDER A MORE UNIVERSAL RIDER OBJECT THAT CAN BE IMPORTED AND USED HERE AS WELL AS RESULTS SCRAPING
    - Basic role: a set of classes and functions for parsing a start list of a race before the race has happened.
    - Key import: parse_start_list function
        - Given the HTML response of for a race page, creates a list of Team objects (name, rider list and team_id (if it exists)) The rider list is populated with Rider objects that have a name, rider_id (for firstcycling), team name, team_id, and race number.


# How to use this 

*Starting by setting up the database and file structure*

Use the create_race_year_db function from find_races.py to create a file structure to store race data and list of races to scrape. You can customize which tours are scraped by looking in find_races.py file and changing the tour ids for the appropriate tours.

*Systematically scraping websites*

When you set up the database and file structure you will create text files in the folder for every tour folder within each year folder. Each line in that text file is a race name followed by a comma, followed by a race url. 

You can pass in a base directory to the function and it will use that as the base within which it creates the year folder.

You can use the Race class from the create_race_data.py file to create Race objects for each race in the list. Call the object's populate_race() method and the scrape will begin (including all stages if it's a stage race). Dump the models in the folder housing the ext file to save them. This will allow you to scrape overtime to see which races have been scraped and which need to be scraped.

*Getting Pre-Race Information for Predictions*
Use the get_start_list function from the get_startlist.py file. To use the function you need a first cyclign race id and the year. It returns a list of Team objects which contain a list of Rider objects.

Use the information from here to feed into a predictive model

Might need to update this with the date scraping function to pull the dates automatically for the race.

# To do

- write a script to check the progress and continue and scraping that needs to be done within a tour folder, within a year folder, and overall within a base directory folder. 
- consider some renaming as described above
- consider placing all scrape functions in one file and all classes in another file. Can the Race object perhaps be used to represent start list only?
- consider adding a cloud storage saving option
- consider adding proper DB storage for races and riders (though maybe only once the scraped data has already been saved.) Maybe something to go through the file structure and create a DB to store in the cloud. Then from there read what needs to be scraped and save it to the db. I think a cloud db is the best way to go here.
- Next we'll need to create tools for accessing the scraped data. That will be module part two.


# Let's save the data here
~/cycling_scraped_data