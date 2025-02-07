from cycling_project.prediction_tools.bib_avg_place_predictions import validate_bib_race_result_dict,validate_race_for_bib_prediction,get_bib_nums
from cycling_project.webscrape_tools.create_race_data import Race, Stage
from cycling_project.data_loading_tools.create_rider_data import RiderDB,RiderCareer
from cycling_project.data_loading_tools.load_scraped_data import FCCyclingYear,FCCyclingTour,FCCyclingDB
from cycling_project.engineering_tools.place_handling import place_bucketer
from random import shuffle
from typing import Union,List,Dict,Tuple
import os
import pickle
import numpy as np

from sklearn.linear_model import LinearRegression


#Working on the extraction for races. Just need to add the histories the training data phase

def get_rider_hist_w_unknown_date_min_req(rider_career:RiderCareer,prior_to_time:str|int=None,min_req_history:int=3,avg_default:float=6.0,race_type=['gc','stage','one_day'],tour_type=['wt','pro','d1']):
    if isinstance(prior_to_time,int):
        rider_history = rider_career.generate_race_history(prior_to_year=prior_to_time,race_type=race_type,tour_type=tour_type)
    elif isinstance(prior_to_time,str):
        rider_history = rider_career.generate_race_history(prior_to_date=prior_to_time,race_type=race_type,tour_type=tour_type)
    else:
        rider_history = []
    if len(rider_history) < min_req_history:
        avg_place = avg_default
    else:
        avg_place = sum([place_bucketer(rider_history.place) for rider_history in rider_history])/len(rider_history)
    return avg_place

#Let's establish a standard order: gc,stage,one_day,wt,pro,d1. Those will be the average results we'll use
def extract_specific_career_averages(rider_career:RiderCareer,prior_to_time:str|int=None,min_req_history:int=3):
    #Get the average gc place
    gc_avg = get_rider_hist_w_unknown_date_min_req(rider_career,prior_to_time=prior_to_time,min_req_history=min_req_history,race_type=['gc'])
    #Get the average stage place
    stage_avg = get_rider_hist_w_unknown_date_min_req(rider_career,prior_to_time=prior_to_time,min_req_history=min_req_history,race_type=['stage'])
    #Get the average one day place
    one_day_avg = get_rider_hist_w_unknown_date_min_req(rider_career,prior_to_time=prior_to_time,min_req_history=min_req_history,race_type=['one_day'])
    #Get the average wt place
    wt_avg = get_rider_hist_w_unknown_date_min_req(rider_career,prior_to_time=prior_to_time,min_req_history=min_req_history,tour_type=['wt'])
    #Get the average pro place
    pro_avg = get_rider_hist_w_unknown_date_min_req(rider_career,prior_to_time=prior_to_time,min_req_history=min_req_history,tour_type=['pro'])
    #Get the average d1 place
    d1_avg = get_rider_hist_w_unknown_date_min_req(rider_career,prior_to_time=prior_to_time,min_req_history=min_req_history,tour_type=['d1'])
    return gc_avg,stage_avg,one_day_avg,wt_avg,pro_avg,d1_avg

# Extract training data from a race
def extract_bib_place_training_data_from_race(race:Union[Race,Stage],rider_db:RiderDB,race_type=['gc','stage','one_day'],tour_type=['wt','pro','d1'])->Tuple[List[Tuple[int,str,int,int,float,int]],Dict]:
    """Extracts training data for a race that has bib number data,  prior average bucketed finishing place data, and actual bucketed finishing place data for each rider in the race if the race has bib data in its results.
    Args:
        race: the race or stage object to extract the training data from.
        rider_db: the RiderDB object to use for generating rider histories.
        race_type: select which kind of races you want to use in generating the rider history.
        tour_type: select which kind of tours you want to use in generating the rider history.
    Returns:
        A list of tuples. The first tuple is the training data. The training data is a list of tuples with a rider ide, rider name, team bib number, personal bib number, prior average finishing place, and actual finishing place. Places are bucketed. The second tuple is a dictionary with the meta data about the training data: how many total prior races were use to generate the average finishing place and how many riders from the race had the results."""
    #validate the race
    validated_race = validate_race_for_bib_prediction(race=race)
    if validated_race is None:
        print(f"{race.name} has no valid training data with bib numbers, skipping")
        return None
    #Get prior_to_date for generating average place bucket fo the rider
    prior_to_date = validated_race.date
    if prior_to_date is None:
        prior_to_date = int(validated_race.year)
    if prior_to_date is None:
        print(f"No date or year found, can't generate a rider prediction or history for {validated_race.name}")
        return None
    #Initialize the training data list
    training_data = []
    meta_data_tracking = {'num_histories':0,'num_riders':0,}
    for rider_result_dict in validated_race.results:
        #Validate the rider result dictionary
        validated_rider_result_dict = validate_bib_race_result_dict(rider_result_dict)
        if validated_rider_result_dict is None:
            continue
        #Get the rider id
        rider_id = validated_rider_result_dict['rider_id']
        #Get the bib numbers
        team_num,personal_num = get_bib_nums(validated_rider_result_dict['bib_number'])
        if team_num is None or personal_num is None:
            print(f"Team or personal bib number is None for rider id {rider_id}, skipping")
            continue
        #Get the actual bucketed place
        actual_bucketed_place = place_bucketer(validated_rider_result_dict['place'])
        #Get the average finishing place up to the date
        #To get the average finishing place, we need the RiderCareer from the RiderDB
        rider_career = rider_db.riders.get(rider_id)
        if rider_career is None:
            print(f"Rider id {rider_id} not found in the rider_db, skipping")
            continue
        if isinstance(prior_to_date,int):
            rider_history = rider_career.generate_race_history(prior_to_year=prior_to_date,race_type=race_type,tour_type=tour_type)
        else:
            rider_history = rider_career.generate_race_history(prior_to_date=prior_to_date,race_type=race_type,tour_type=tour_type)
        #Now that we have our rider history we can make our predicted finishing place by calculating the average finishing place up to this point in the rider's career.
        #If the rider history is empty, set the average finish to 6 for above top 30
        if rider_history is None or rider_history==[]:
            avg_place = 6
        else:
            #Calculate the average place
            avg_place = sum([place_bucketer(race_res.place) for race_res in rider_history])/len(rider_history)
        #return a tuple of id, name, team number, personal number, average place, and actual place
        training_data.append((rider_id,validated_rider_result_dict['name'],team_num,personal_num,avg_place,actual_bucketed_place))
        #increment the number of histories by the len of rider_history, increment the riders processed by 1
        meta_data_tracking['num_histories'] += len(rider_history)
        meta_data_tracking['num_riders'] += 1
        
    if training_data is None or training_data == []:
        print(f"{race.name} has no valid training data, skipping")
        return None
    return training_data,meta_data_tracking