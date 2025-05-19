#The goal here is to take race finish time distribution data and distill a few different dimensions out of the data

## We're going to have a big group finish score: basically all the riders are finishing together in a single group. This dimension will find group sprints
## We're going to have a shattered score, riders are distributed relatively evenly across a wide range of finish times. This dimension will find time trials and mountain top finishes stages
## We're going to have a clumpiness score, riders are distributed in a few clumps. This dimension will find hilly stages
## We're going to have a total finish time score. This dimension will find time trials and long hard stages.
from cycling_project.webscrape_tools.create_race_data import Race
from cycling_project.engineering_tools.race_characteristics import generate_finishing_time_data_from_race, generate_finishing_time_data_from_tour, generate_finishing_time_data_from_year
from cycling_project.data_loading_tools.load_scraped_data import load_year_path,FCCyclingTour,FCCyclingYear
from cycling_project.webscrape_tools.find_races import DB_PATH
import os
import pandas as pd
import numpy as np
from typing import List
from datetime import datetime

## Biggest Group Metric:
## This metric goes up the larger the group and the closer to the front this group is.
def biggest_group_metric(finish_time_dist_dict: dict) -> float:
    """
    Calculate a metric that represents the size and influence of the biggest group in a bike race.
    Returns a normalized score between 0 and 1, where:
    - 1 means the entire race finishes in one group and the winner is in that group
    - 0 means either no significant group or the largest group had no influence on the race outcome
    
    Args:
        finish_time_dist_dict: Dictionary output by the extract_finishing_time_distributions function
                              from the race_characteristics module.
    
    Returns:
        float: A score between 0 and 1 representing the size and influence of the biggest group
    """
    # Extract data about the biggest group
    max_group_proportion = finish_time_dist_dict['max_group_proportion']
    max_group_percentile = finish_time_dist_dict['max_group_finish_time_percentile']
    
    # Size component: normalized directly using proportion rather than raw size
    # This ensures this component is already between 0 and 1
    size_score = max_group_proportion
    
    # Influence component: how close to the front of the race
    # Transformed to be between 0 and 1, with emphasis on being near the front
    # Using a sigmoid-like function to create a smooth falloff
    if max_group_percentile <= 0.01:  # If the group contains the winner
        influence_score = 1.0
    else:
        # Set cutoff at 30% (0.30) - groups beyond this point have minimal influence
        cutoff = 0.3
        if max_group_percentile >= cutoff:
            influence_score = 0.0
        else:
            # Use a power function for smooth falloff between 0 and cutoff
            # Higher powers increase the penalty for being further from the front
            influence_score = ((cutoff - max_group_percentile) / cutoff) ** 2
    
    # Final score combines size and influence
    # Using a weighted geometric mean to ensure result is between 0 and 1
    # Adjusting weights to prioritize influence over size (0.6 vs 0.4)
    final_score = (size_score ** 0.3) * (influence_score ** 0.7)
    
    return final_score


## Evenness Metric:
## This metric goes up the more evenly distributed the riders are across the finish times.
def time_gap_evenness_metric(finish_time_dist_dict: dict) -> float:
    """
    Create a metric that measures how evenly distributed finishing times are across the space of possible finishing times.
    A perfect score of 1.0 indicates perfectly even spacing between each percentile.
    
    Args:
        finish_time_dist_dict: the dict produced by the extract_finishing_time_distributions function.
    
    Returns:
        a float between 0 and 1 representing the evenness of the finish times.
    """
    # Get the gap data
    pct_winner = 0
    pct_5 = finish_time_dist_dict['5th_percentile_gap']
    pct_10 = finish_time_dist_dict['10th_percentile_gap']
    pct_15 = finish_time_dist_dict['15th_percentile_gap']
    pct_20 = finish_time_dist_dict['20th_percentile_gap']
    pct_25 = finish_time_dist_dict['25th_percentile_gap']
    pct_30 = finish_time_dist_dict['30th_percentile_gap']
    pct_35 = finish_time_dist_dict['35th_percentile_gap']
    pct_40 = finish_time_dist_dict['40th_percentile_gap']
    pct_45 = finish_time_dist_dict['45th_percentile_gap']
    pct_50 = finish_time_dist_dict['50th_percentile_gap']
    
    # If there are no time gaps, return 0
    if pct_50 == pct_winner:
        return 0
    
    # Get the raw gaps
    gaps = [pct_winner, pct_5, pct_10, pct_15, pct_20, pct_25, pct_30, pct_35, pct_40, pct_45, pct_50]
    
    # Calculate the differences between consecutive gaps
    gap_diffs = np.diff(gaps)
    
    # If there are any zero differences, apply penalty
    zero_count = np.sum(gap_diffs == 0)
    zero_penalty = zero_count * 0.1
    
    # In a perfectly even distribution, all differences would be equal
    
    # Calculate how much each actual difference deviates from the ideal
    # Use coefficient of variation (normalized measure of dispersion)
    if np.mean(gap_diffs) > 0:
        cv = np.std(gap_diffs) / np.mean(gap_diffs)
        # When CV=0, differences are perfectly even
        evenness_score = 1 / (1 + cv)
    else:
        evenness_score = 0
    
    # Apply zero penalty
    final_score = evenness_score * (1 - zero_penalty)
    
    # Ensure bounds between 0 and 1
    return final_score
    
def calculate_clumpiness_score(finish_time_dist_dict:dict)->float:
    """
    Calculates a clumpiness metric from a finishing time data distribution dictinoary produced by the extract_finishing_time_distributions function in the race_characteristics module.
    The metric works as follows:
    
    1. Increases with more groups (group_count), up to 15 groups
    2. Increases with higher proportion of riders in groups (proportion_grouped)
    3. Increases with groups around the sweetspot of clumpiness of 5-15 average group size, decreases outside of that range, and gets set to 0 when too big.
    
    The goal of the metric is to find races that are clumpy. That is, it is not a shattered race where everyone is on their own. Instead they have been broken into a few groups.
    There is a size penalty functino in here that is designed to penalize the score when the average group size is too small (under 5) or too large (over 15). This is to avoid rewarding shattered races or big group finishes. We want to find the clumpy races here.
    Args:
        finish_time_dist_dict: the dict produced by the extract_finishing_time_distributions function
    """
    #get the group data
    #group_data = finish_time_dist_dict['group_data'] #the group data should be unpacked already
    group_count = finish_time_dist_dict['group_count']
    proportion_grouped = finish_time_dist_dict['proportion_grouped']
    avg_group_size = finish_time_dist_dict['avg_group_size']
    
    
    # Normalize group count by assuming 15. If we have more than 15 total groups in a race we've got something clumpy to shattered. Fewer than 15 we're really looking at a group or reduced group sprint probably. Much more than 15 and we're headed towards shattered.
    # So, we can divide by 15 and then cap at 1. This will give us a score between 0 and 1 for this component
    group_component = min(group_count/15,1)
    
    # Use proportion_grouped directly (already 0-1)
    proportion_component = proportion_grouped
    
    # Penalize or reward group sizes based on a smooth function
    # Create a parabolic size penalty function. Between 5 and 15 the size score will be between 2 and 2.75, increasing from 2 to 2.75 and then decreasing from 2.75 to 2 as you move from 5 to 10 and then 10 to 5. 
    # At 1 is is about a .3 discount, and above 20 it gets negative again meaning we don't have a clumpy race. At 18 it dips below 1 and so starts to be a slight penalty.
    # Need to rework the key stats here to take into account only the top half of the race.
    def size_multiplier(x):
        # 
        return  2.75 - 0.03*(x - 10)**2
    
    #This will naturally set to 0 cases where the average group size is bigger than 15.
    size_score = size_multiplier(avg_group_size)
    
    # Combine components with weights
    #Group component will be bewteen 0 and 1, proportion component will be between 0 and 1, size score will max at 2.75 or be negative. To normalize between 0 and 1, we can divide by 2.75
    metric = group_component * proportion_component * size_score
    # Ensure non-negative result
    metric = max(0, metric)
    #normalize the metric to be between 0 and 1
    normalized_metric = metric / 2.75
    return normalized_metric

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
    normalized_total_time = winning_time / 28800
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
    """Take in a competition object and return the five dimensional rating for each competition (ie a one day, stage, or gc) in the race object. It simply adds the five dimension race data dict to the existing tiem distribution data dict for each dict in the list generated by getting the race time distribution data for each competition in the race object.
    Args:
        race: a race object (ie a one day or stage race)
    Returns:
        a list of dicts with the five dimensional data added to the existing time distribution data
        """
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
    """Take in a tour object and return the five dimensional rating and time distribution data for each competitoin object (gc, stage, one day) in the tour.
    Args:
        tour: a tour object with races
    Returns:
        a list of dicts with the five dimensional data added to the existing time distribution data
    """
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
    """Take in a year object and return the five dimensional rating for each race within each tour level in the year.
    Args:
        year: a year object with tours
    Returns:
        a list of dicts with the five dimensional data added to the existing time distribution data
    """
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

def create_five_dim_db(year_range:List[int],db_path:str=DB_PATH)->pd.DataFrame:
    """
    Given a list of years as integers from 2010 to 2025, and a db_path for a db with years as folders, return a pandas DataFrame with race id, name, tour type, race type, date, year, and the five dimensions as columns in the dataframe. Each row is a race.
    Args:
        year_range: a list of years as integers from 2010 to 2025
        db_path: the path to the db with years as folders, optional
    Returns:
        dataframe with all races, key identifying race info and five dimensions
    """
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
    """
    A class for creating and managing a race database where races have the five key dimensions and identifying race data.
    The class object is initialized with a year range (list of ints) and an optional db_path (path to the db with years as folders). The class has methods for looking up specific races and finding all races prior to a give date."""
    def __init__(self,year_range:List[int],db_path:str=DB_PATH):
        self.db = create_five_dim_db(year_range=year_range,db_path=db_path)
        self._non_data_cols = ['race_id','race_name','tour_type','race_type','race_date','race_year']
        self._five_dim_cols = ['total_time', 'abandon_proportion','biggest_group', 'shattered', 'clumpiness']
        self.gc = self.db[self.db['race_type'].str.lower().str.strip() == 'gc'].copy()
        self.one_day = self.db[self.db['race_type'].str.lower().str.strip() == 'one_day'].copy()
        self.stage = self.db[self.db['race_type'].str.lower().str.strip() == 'stage'].copy()
    
    def race_lookup(self,fc_race_id:int,race_type:str,year:int,stage_name:str|None=None)->pd.DataFrame:
        """
        Given a race_id, race_type (gc, one_day, stage), year, and optional stage_name (if selecting a stage), return a
        dataframe where the row is the specified race data.
        Args:
            fc_race_id: an int that is the fc_race_id of the race
            race_type: a string (gc, one_day, stage) that is the type of race
            year: an int that is the year you're interested in
            stage_name: an optional string that is the name of the stage you're interested in. mandatory if selecting stage race_type.
        Returns:
            a one row dataframe with the race data in question."""
        
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
        """
        Given a race_type, a prior_to_date (YYYY-MM-DD), and an optional fc_race_id as int, return a dataframe with all races of the specified race_type that happened prior to teh given date.
        Args:
            race_type: a string (gc, one_day, stage) that is the race type you're interested in
            prior_to_date: a string that is the date you're interested in (YYYY-MM-DD)
            fc_race_id: an optional int that represents the race id of a specific race
        Returns:
            a dataframe with all the prior races in the db to the specified date of the specified race type"""
        
        
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