#The goal here is to take race finish time distribution data and distill a few different dimensions out of the data

## We're going to have a big group finish score: basically all the riders are finishing together in a single group. This dimension will find group sprints
## We're going to have a shattered score, riders are distributed relatively evenly across a wide range of finish times. This dimension will find time trials and mountain top finishes stages
## We're going to have a clumpiness score, riders are distributed in a few clumps. This dimension will find hilly stages
## We're going to have a total finish time score. This dimension will find time trials and long hard stages.
from cycling_project.webscrape_tools.create_race_data import Race,Stage
from cycling_project.engineering_tools.race_characteristics import extract_finishing_time_distributions,generate_finishing_time_data_from_race, generate_finishing_time_data_from_tour, generate_finishing_time_data_from_year
from cycling_project.data_loading_tools.load_scraped_data import load_db, load_year_path,FCCyclingDB,FCCyclingTour,FCCyclingYear,DB_PATH
import os
import pandas as pd
import numpy as np
from typing import Union,List
from datetime import datetime

## Biggest Group Metric:
## This metric goes up the larger the group and the closer to the front this group is.
def biggest_group_metric(finish_time_dist_dict:dict)->float:
    #First, get max group size based component of the score
    #max_group_data = finish_time_dist_dict['max_group_data'] #the max time data will be unpacked already
    #get the raw size of the group    
    max_group_size = finish_time_dist_dict['max_group_size']
    #Get the proportional size of the group
    max_group_proportion = finish_time_dist_dict['max_group_proportion']
    #We want the size score to go up primarily based on the size of the group and then that score can be boosted further by the higher proportion of the race that finished in the group.
    #At most the final size score should go up 50% if the entire race finishes in the group. So, divide the max_group_proportion by 2 and multiply the result + 1 by the max group size.
    size_score = max_group_size * (1 + (max_group_proportion / 2)) 
    #Second, now that we have a size score, let's get an influence score by seeing how close the the front of the race.
    #Let's start with the max_group_position. A winning max group would be 1. Once max group is below 25th percentile it's not really a part of the race. We can have a sliding scale from there that falls off more rapidly the further from the winning position you get
    max_group_percentile = finish_time_dist_dict['max_group_finish_time_percentile']
    # We want the influence score to fall off faster initially and then more gradually as you get closer to the 25th percentile.
    influence_score = max((1 - (max_group_percentile/.20)),0) ** 2.5
    if influence_score < 0:
        influence_score = 0.0
    #Now we can multiply the size score by the influence score to get the final score
    final_group_score = size_score * influence_score
    #Finally, let's make sure we're in a reasonable score range. The max score possible here is something like 270 if you have ~180 riders, all of them finish in the last group and the group wins. Let's divide by 300
    final_group_score = final_group_score / 200
    #We're now scaled approximately between 0 and 1
    return final_group_score


## Evenness Metric:
## This metric goes up the more evenly distributed the riders are across the finish times.
def time_gap_evenness_metric(finish_time_dist_dict:dict)->float:
    """
    Calculate a metric that:
    1. Increases with larger differences between gaps
    2. Heavily penalizes zero differences
    3. Rewards more uniform (but non-zero) differences
    
    Args:
        finish_time_dist_dict: the dict of race finishing characteristics
    """
    #Get the zscore data
    #zscore_data = finish_time_dist_dict['distribution_data'] the zscore data will be unpacked already
    pct_0 = finish_time_dist_dict['winner_zscore']
    pct_5 = finish_time_dist_dict['5th_percentile_zscore']
    pct_10 = finish_time_dist_dict['10th_percentile_zscore']
    pct_15 = finish_time_dist_dict['15th_percentile_zscore']
    pct_20 = finish_time_dist_dict['20th_percentile_zscore']
    pct_25 = finish_time_dist_dict['25th_percentile_zscore']
    pct_30 = finish_time_dist_dict['30th_percentile_zscore']
    pct_35 = finish_time_dist_dict['35th_percentile_zscore']
    pct_40 = finish_time_dist_dict['40th_percentile_zscore']
    pct_45 = finish_time_dist_dict['45th_percentile_zscore']
    pct_50 = finish_time_dist_dict['50th_percentile_zscore']
    # if these are all the same, we want a low shattered score. if these are all different but evenly spaced out we want a high shattered score.
    # We can use the variance of these numbers to get a sense of how evenly spaced they are.
    gaps = [pct_0,pct_5, pct_10, pct_15, pct_20, pct_25, pct_30, pct_35, pct_40, pct_45, pct_50]
    gap_diffs = np.diff(gaps)
    gap_diff_var = np.var(gap_diffs)

    # Penalize zero differences
    zero_penalty = np.sum(gap_diffs == 0) * 0.1
    
    # Get average difference size (excluding zeros)
    non_zero_diffs = gap_diffs[gap_diffs != 0]
    if len(non_zero_diffs) == 0:
        return 0
    
    avg_diff = np.mean(non_zero_diffs)
    
    # Reward larger differences but normalize to prevent extreme values
    size_component = avg_diff
    
    # Reward lower variance (but avoid dividing by zero)
    variance_component = 1 / (1 + gap_diff_var)
    
    # Combine components
    metric = (size_component * variance_component) - zero_penalty
    
    # Ensure non-negative result
    return max(0, metric)
    
def calculate_clumpiness_score(finish_time_dist_dict:dict)->float:
    """
    Calculate a clumpiness metric that:
    1. Increases with more groups (group_count)
    2. Increases with higher proportion of riders in groups (proportion_grouped)
    3. Decreases with larger average group size (avg_group_size)
    
    Args:
        group_count: Number of groups
        proportion_grouped: Proportion of riders in groups (0-1)
        avg_group_size: Average size of groups
    """
    #get the group data
    #group_data = finish_time_dist_dict['group_data'] #the group data should be unpacked already
    group_count = finish_time_dist_dict['group_count']
    proportion_grouped = finish_time_dist_dict['proportion_grouped']
    avg_group_size = finish_time_dist_dict['avg_group_size']
    
    
    
    # Normalize group count (assuming max ~90 groups as might happen in time trials )
    group_component = group_count/90
    
    # Use proportion_grouped directly (already 0-1)
    proportion_component = proportion_grouped
    
    # Penalize or reward group sizes based on a smooth function
    # Create a parabolic size penalty that's minimal around 10, increases sharply below 5 and above 15
    def size_penalty_function(x):
        # Shift the parabola to have minimum at x=10
        shifted_x = (x - 10)
        # Scale the parabola to be gentle in the middle and steep at edges
        if x <= 4:
            # Sharp penalty for very small groups
            return max(0, 1 - (x/4)**2)
        elif x >= 25:
            # Sharp penalty for large groups
            return max(0, 1 - ((50-x)/25)**2)
        else:
            # Gentle curve in the sweet spot
            return 1 - (shifted_x/10)**2

    size_penalty = size_penalty_function(avg_group_size)
    
    # Combine components with weights
    metric = (group_component * .5 + proportion_component * .5) * size_penalty
    
    return max(0, min(1, metric))

#Now we have three metrics. let's create our final five dimensional race rating score: total time, abandon proportion, biggest group, shattered, clumpiness
def calculate_five_race_dimensions(finish_time_dist_dict:dict)->dict:
    """
    Calculate a five-dimensional rating of a race based on its finishing time distributions.
    Args:
        finish_time_dist_dict: the dict with finishing time characteristics
    Returns a dict with the five dimensions:
        total_time: float, normalized total time relative to 4 hours
        abandon_proportion: float, proportion of riders who abandoned
        biggest_group: float, metric of largest group finish
        shattered: float, metric of evenness of finish times
        clumpiness: float, metric of clumpiness of finish times
    """
    #get the total time data, it will be in seconds. Normalize it to 4 hours
    winning_time = finish_time_dist_dict['winning_time']
    normalized_total_time = winning_time / 14400
    #get the abandon data
    abaondon_proportion = finish_time_dist_dict['non_finisher_proportion']
    #Get the biggest group metric
    biggest_group = biggest_group_metric(finish_time_dist_dict)
    #get the shattered metric
    shattered = time_gap_evenness_metric(finish_time_dist_dict)
    #get the clumpiness metric
    clumpiness = calculate_clumpiness_score(finish_time_dist_dict)
    #return the dict
    return {'total_time':normalized_total_time, 'abandon_proportion':abaondon_proportion, 'biggest_group':biggest_group, 'shattered':shattered, 'clumpiness':clumpiness}

def process_race_for_five_dimensions(race:Race)->dict:
    """Take in a competition object and return the five dimensional rating"""
    #First, check if we can get finishing time data from it
    race_data = generate_finishing_time_data_from_race(race)
    if len(race_data) == 0:
        print(f'Could not extract any finishing time data from {race.name}')
    #Second, go through each race in the list and try to process it for five dimensions
    five_dim_race_data = []
    for race_dict in race_data:
        #get the five dim data
        five_dim_dict = calculate_five_race_dimensions(race_dict)
        if five_dim_dict is not None:
            race_dict.update(five_dim_dict)
            five_dim_race_data.append(race_dict)
        else:
            print(f'Could not extract five dimensional data for {race.name}')
            continue
    return five_dim_race_data

def process_tour_for_five_dimensinos(tour:FCCyclingTour)->list:
    """Take in a tour object and return the five dimensional rating"""
    #First, check if we can get finishing time data from it
    tour_data = generate_finishing_time_data_from_tour(tour)
    if len(tour_data) == 0:
        print(f'Could not extract any finishing time data from {tour.name}')
    five_dim_tour_data = []
    for race_dict in tour_data:
        #get the five dim data
        five_dim_dict = calculate_five_race_dimensions(race_dict)
        if five_dim_dict is not None:
            race_dict.update(five_dim_dict)
            five_dim_tour_data.append(race_dict)
        else:
            print(f'Could not extract five dimensional data for {tour.name}')
            continue
    return five_dim_tour_data

def process_year_for_five_dimensions(year:FCCyclingYear)->list:
    """Take in a year object and return the five dimensional rating"""
    #First, check if we can get finishing time data from it
    year_data = generate_finishing_time_data_from_year(year)
    if len(year_data) == 0:
        print(f'Could not extract any finishing time data from {year.year}')
    five_dim_year_data = []
    #process wt
    five_dim_year_data.extend(process_tour_for_five_dimensinos(year.wt))
    #process pro
    five_dim_year_data.extend(process_tour_for_five_dimensinos(year.pro))
    #process d1
    five_dim_year_data.extend(process_tour_for_five_dimensinos(year.d1))
    return five_dim_year_data

def create_five_dim_db(year_range:List[int],db_path:str=DB_PATH)->list:
    """"""
    #First, load the race db
    db_data = []
    for year in year_range:
        year_path = os.path.join(db_path,str(year))
        year_db = load_year_path(year_path)
        year_five_dim_l = process_year_for_five_dimensions(year_db)
        db_data.extend(year_five_dim_l)
        
    db_data_dict = {}
    i = 0
    for race_dict in db_data:
        db_data_dict[i] = race_dict
        i += 1
    db_data_df_full = pd.DataFrame.from_dict(db_data_dict,orient='index')
    key_cols_f_d = ['race_id','race_name','tour_type','race_type','race_date','race_year','total_time', 'abandon_proportion','biggest_group', 'shattered', 'clumpiness']
    return db_data_df_full[key_cols_f_d].copy()

class FiveDimDB:
    def __init__(self,year_range:List[int],db_path:str=DB_PATH):
        self.db = create_five_dim_db(year_range=year_range,db_path=db_path)
        self._non_data_cols = ['race_id','race_name','tour_type','race_type','race_date','race_year']
        self._five_dim_cols = ['total_time', 'abandon_proportion','biggest_group', 'shattered', 'clumpiness']
        self.gc = self.db[self.db['race_type'].str.lower().str.strip() == 'gc'].copy()
        self.one_day = self.db[self.db['race_type'].str.lower().str.strip() == 'one_day'].copy()
        self.stage = self.db[self.db['race_type'].str.lower().str.strip() == 'stage'].copy()
    
    def race_lookup(self,fc_race_id:int,race_type:str,year:int,stage_name:str|None=None)->pd.DataFrame:
        #get the right db
        if race_type.lower().strip()=='gc':
            db = self.gc
        elif race_type.lower().strip()=='one_day':
            db = self.one_day
        elif race_type.lower().strip()=='stage':
            db = self.stage
            #if stage_name is None, return an error and message
            if stage_name is None:
                #print("You must provide a stage_name for stage lookup")
                return None
        else:
            #print("You must select a race_type from 'gc', 'one_day', or 'stage'")
            return None
        if stage_name:
            race_data = db.loc[(db['race_id'].astype(int)==fc_race_id) & (db['race_year'].astype(int)==year)].copy()
            #get the row that contains the stage name in the race_name column
            stage_data = race_data.loc[race_data['race_name'].str.contains(stage_name,case=False)].copy()
            if stage_data.shape[0] == 0:
                pass
                #print(f"No data found for {fc_race_id} in {year} with stage name {stage_name}")
            return stage_data
        else:
            race_data = db.loc[(db['race_id'].astype(int)==fc_race_id) & (db['race_year'].astype(int)==year)].copy()
            if race_data.shape[0] == 0:
                pass
                #print(f"No data found for {fc_race_id} in {year}")
            return race_data
    
    def find_prior_races(self,race_type:str,prior_to_date:str,fc_race_id:int|None=None)->pd.DataFrame:
        #convert prior to date to datetime
        try:
            prior_to_date_dto = datetime.strptime(prior_to_date,'%Y-%m-%d')
        except:
            print(f"Error converting {prior_to_date} to datetime. Make sure it is YYYY-MM-DD")
            return None
        #get the right db
        if race_type.lower().strip()=='gc':
            db = self.gc
        elif race_type.lower().strip()=='one_day':
            db = self.one_day
        elif race_type.lower().strip()=='stage':
            db = self.stage
        else:
            print("You must select a race_type from 'gc', 'one_day', or 'stage'")
            return None
        #Filter db for rows only with dates prior to prior_to_date
        prior_race_db = db.loc[db['race_date'] < prior_to_date_dto].copy()
        if prior_race_db.shape[0] == 0:
            print(f"{race_type} has no races prior to {prior_to_date}")
            return prior_race_db 
        #If fc_race_id is provided, only get those races as well
        if fc_race_id is not None:
            #get the races where the fc_race_id is in the race_id column
            prior_race_history_db = prior_race_db.loc[prior_race_db['race_id'].astype(int)==fc_race_id].copy()
            if prior_race_history_db.shape[0] == 0:
                pass
                #print(f"{fc_race_id} not found in the races prior to {prior_to_date}")
            return prior_race_history_db
        else:
            return prior_race_db