# Data Loading Tools

There are two main tools here: tools for loading scraped data from the saved scraped pkl files and tools for loading rider information from the loaded race files.

## Loading Scraped Files

Scraped files can be loaded in three ways:

1. By passing the path for a tour directory
2. By passing the path for a year directory
3. By passing the root path for the database

Functions for loading these are in the load_scraped_data module

### Loading Tours

Created by passing a path to a tour directory (ie a directory path that ends with wt, pro, or d1) to the load_tour_path function 

Passing a tour directory creates an FCCyclingTour object. These objects have a .races attribute that is a list of Race objects (from the webscrape_tool.create_race_data module). Stage race Race objects will have a list of Stage objects

FCCyclingTour objects also have .stage_races, .one_days, and .stages attributes. Each is a list of Race objects. These attributes can be populated with the extract_stage_races(), extract_one_days() and extract_stages() class methods.

The add_race_attrs() class method will create attributes for the object for each race of the form r{race_id}

### Loading Years

Created by passing a year directory (ie a directory path that ends with a four digit year) to the load_tour_year function

Passing a year directory will return an FCCylingYear object. This object will have year attribute that tells you the year and a .wt, .pro, and .d1 attribute that are FCCyclingYear objects.

I also added an export_jsons class method at the year level. You pass the parent directory you would like to save the jsons to and the export_jsons method will create a year subdirectory, a tour sub directory for each tour within the year directory and then populate each tour with JSON files for each object.


### Loading a full race database

Created by passing a base scraped data directory (ie a directory that contains year subdirectories) to the load_db function. Returns an FCCyclingDB object.

The object has a years attribute which is a list of FCCyclingYear objects.

FCCycingDB objects have an add_year class method. The year argument for that method takes a FCCyclingYear object, adds it to the FCCyclingDB.year list, and adds an attribute of the form y{year} to the db object.

Calling the load_year_path function creates a FCCyclingDB object, adds years for each year directory in the DB directory.

There is an environmental variable, DB_PATH that is currently used as the default across all functions that use a base database path.


## Rider Information Tools

Rider data is initially created through the create_rider_data module here.

There are three main classes employed to create rider data

First, there is the RiderResult class. RiderResult objects are created from the dictionaries that are in the Race.results list. Some additional information is calculated at the creation of these objects, like rider age, and bib number information if it's available (both the team number and the rider's individual number are extracted).

Second, there is the RiderCareer class. RiderCareer objects represent all of the information we have about a rider. RiderCareer objects have a date of bither, race_history, team_history, career_start and career_end information. 

RiderCareer objects have an add_race_result that is used to add RiderResult objects to their rider_history list. 

RaderCareer objects have a generate_race_history class method that will return a list of RiderResult objects based on the filtering conditions provided. Filters can be placed by placing a prior_to_year condition, a race_type condigion (gc, stage, one_day), a tour_type condition (wt, pro, d1), and a prior_to_date condition (will get all RiderResult objects from the rider_history that happened prior to the date specified.) 

Third, and finally, there is the RiderDB class. This is a class to hold a set of riders. the RiderDB class has a .riders attribute which is a dictionary that links rider ids (from FirstCycling, as int) to RiderCareer objects.

RiderDB objects are populated by passing scraped race data in the form of either an FCCycling Tour object to the add_tour class method or an FCCyclingYear object to teh add_year class method.

Each of these methods goes through the results list of each Race object (or the results list of each Stage object in the Race.stages list) to create a RiderCareer object for that rider (if it doesn't exist) and add the result to the RiderCareer object.

Individual result dictionaries can also be used to update a RiderDB object through the add_rider_result object.

