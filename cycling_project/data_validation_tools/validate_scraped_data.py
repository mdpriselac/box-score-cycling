import os
import pickle

from typing import Union
import re

from cycling_project.data_loading_tools.load_scraped_data import load_db, load_year_path,DB_PATH, TOURS
from cycling_project.webscrape_tools.create_race_data import Race, Stage

#db = load_db()

#create a dir in the db_path that will hold evaluation

#We're looking for: 
# races that don't have dates,
date_format = re.compile(r"\d{4}-\d{2}-\d{2}")
# races that don't have winning times,
# races that dont' have results

def validate_race(race: Union[Race,Stage])->dict:
    #Set up the valid flags
    valid_date = False
    valid_time = False
    valid_results = False
    #Check if it's a race or a stage
    if isinstance(race,Stage):
        if isinstance(race.time,float):
            if race.time > 0.0:
                valid_time = True
        if isinstance(race.date,str):
            if date_format.match(race.date) is not None:
                valid_date = True
        if isinstance(race.results,list):
            if len(race.results) > 10:
                valid_results = True
    elif isinstance(race,Race):
        if isinstance(race.race_time,float):
            if race.race_time > 0.0:
                valid_time = True
        if isinstance(race.date,str):
            if date_format.match(race.date) is not None:
                valid_date = True
        if isinstance(race.results,list):
            if len(race.results) > 10:
                valid_results = True
    bad_results = []
    if not valid_date:
        bad_results.append("Missing Date")
    if not valid_time:
        bad_results.append("Missing Winning Time")
    if not valid_results:
        bad_results.append("Missing Results")
    
    if len(bad_results) > 0:
        if isinstance(race,Stage):
            outputname = f"{race.race}, {race.name}"
        else:
            outputname = f"{race.name}"
        return {'race':outputname,'errors':bad_results}
    else:
        return None

def validate_year(year:str,db_path:str=DB_PATH):
    year_path = os.path.join(db_path,year)
    problem_races = []
    year_db = load_year_path(year_path)
    total_race_counter = 0
    total_stage_race_counter = 0
    for tour in TOURS:
        tour_db = getattr(year_db,tour)
        print(len(tour_db.races))
        #Extract the races
        tour_db.extract_one_days()
        tour_db.extract_stages()
        tour_db.extract_stage_races()
        #Put together a complete list
        complete_races =  tour_db.stages + tour_db.one_days
        total_race_counter += len(complete_races)
        total_stage_race_counter += len(tour_db.stage_races)
        #Validate each race, saving races with problem cases
        for r in complete_races:
            check = validate_race(r)
            if check is not None:
                problem_races.append(check)
    
    #Save a problem report
    #check for a "problems" dir in the db_path
    problem_dir = os.path.join(db_path,'problems')
    #Create it if it doesn't exist
    if not os.path.exists(problem_dir):
        os.makedirs(problem_dir)
    #Save the problem report to a file called {year}_problems.txt by writing each problem as a row
    with open(os.path.join(problem_dir,f"{year}_problems.txt"),'w') as prob_file:
        for prob in problem_races:
            prob_file.write(f"{prob['race']}: {' -- '.join(prob['errors'])}\n")
    
    #counters
    missing_results = 0
    missing_date = 0
    missing_time = 0
    for pr in problem_races:
        for error in pr['errors']:
            if error == "Missing Results":
                missing_results += 1
            elif error == "Missing Date":
                missing_date += 1
            elif error == "Missing Winning Time":
                missing_time += 1
                    
    print(f"Finished validating {year}.")
    print(f"Evaluated {total_race_counter} races.")
    print(f"Found {missing_results} missing results")
    print(f"Found {missing_date} missing dates, would expect at least {total_stage_race_counter} to have missing dates because their dates are formatted as a range not a date.")
    print(f"Found {missing_time} missing winning times")
    counter_dict = {'missing_results':missing_results,'missing_date':missing_date,'missing_time':missing_time,'total_race_counter':total_race_counter,'total_stage_race_counter':total_stage_race_counter}
    
    return problem_races, counter_dict

def validate_db():
    overall_counter = {'missing_results':0,'missing_date':0,'missing_time':0,'total_race_counter':0,'total_stage_race_counter':0}
    for year in range(2000,2020):
        
        year_probs, year_counter_dict = validate_year(str(year))
        #Add the year's counter to the overall counter
        for key in year_counter_dict.keys():
            overall_counter[key] += year_counter_dict[key]
    print(f"Finished validating the database.")
    for key,val in overall_counter.items():
        print(f"{key}: {val}")

if __name__ == "__main__":
    validate_db()