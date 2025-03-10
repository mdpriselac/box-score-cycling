from cycling_project.webscrape_tools.create_race_data import Race,Stage
from cycling_project.data_loading_tools.load_scraped_data import load_db, load_year_path,FCCyclingDB,FCCyclingTour,FCCyclingYear,DB_PATH
from typing import Union
from datetime import datetime
import numpy as np
from scipy.stats import zscore
from collections import Counter
from typing import List
import os
import pandas as pd

def extract_finishing_time_distributions(race:Union[Race,Stage])->Union[dict,None]:
    """
    Given a race competition (ie a Race object for a one day or a stage object), check if there are finishing times and extract the finishing time distribution patterns we're interested in.
    Returns a dictionary with four keys, each of which contains a dictionary of the data we're interested in. The keys are max_group_data, group_data, distribution_data, and finish_time_data.
    Args: 
        race: the race to extract finishing time data from (Race object or Stage object)
    Returns:
        a dictionary with four keys, each of which contains a dictionary of the data we're interested in. The keys are max_group_data, group_data, distribution_data, and finish_time_data.
    """
    #check for null results
    if race.results is None:
        print(f"{race.name} has no results, skipping finishing time distributions")
        return None
    #check for empty results
    if len(race.results) < 30:
        print(f"{race.name} has too few results, skipping finishing time distributions")
        return None
    
    if isinstance(race,Race):
        race_time = race.race_time
    elif isinstance(race,Stage):
        try:
            race_time = race.time
            if race_time is None or race_time =='':
                race_time = race.race_time
        except:
            race_time is None
    #check for missing finishing times
    if race_time is None or race_time=='' or race_time==[]:
        print(f"{race.name} has no times, skipping finishing time distributions")
        return None
    total_time = race_time
    #Check if we pulled GC from a TTT stage for a stage race
    if total_time/28800 >=1.0 and 'stage:' in race.name.lower():
        print(f"{race.name} has too long of a race time (over 7hrs 40min), probably pulling GC times for a TTT stage skipping finishing time distributions")
        return None
    finishing_gaps = []
    for result in race.results:
        if isinstance(result.get('gap'),(float,int)):
            finishing_gaps.append(result.get('gap'))
        else:
            continue
            #print(f"Non-time gap for {result.get('name')}, skipping")
    gap_avg = sum(finishing_gaps)/len(finishing_gaps)
    gap_stdev = np.std(finishing_gaps)
    if gap_stdev == 0.0:
        print(f"Standard deviation of gaps is 0, setting to .0001 to avoid divide by zero")
        gap_stdev = .0001
    
    #Get finishing times
    finishing_times = [gap + total_time for gap in finishing_gaps if isinstance(gap,(int,float))]
    #Get attrition/non finish data
    non_finisher_count = len(race.results) - len(finishing_times)
    non_finisher_proportion = non_finisher_count/len(race.results)
    #Get the number of groups (as determined by having the same time)
    unique_finishing_times = len(set(finishing_times))
    #Get the proportion of unique finishing times among all finishing times
    #get the gaps between finishing groups by sorting the unique finishing times and getting the gaps between them
    sorted_times = sorted(list(set(finishing_times)))
    group_gaps = [sorted_times[i+1]-sorted_times[i] for i in range(len(sorted_times)-1)]
    if group_gaps == []:
        print(f"No groups found, setting group_gaps to [0] to avoid divide by zero")
        group_gaps = [0]
    #get the average gap between groups
    avg_group_gap = sum(group_gaps)/len(group_gaps)
    #get the std deviation of the gaps between groups
    stdev_group_gap = np.std(group_gaps)
    #get the possible finishing group counts, which is just the number of seconds between the first and last finishing time
    possible_groups = sorted_times[-1]-sorted_times[0]
    if possible_groups == 0:
        print(f"Possible groups is 0, setting to 1 to avoid divide by zero since there's only one group")
        possible_groups = 1
    #get the proportion of possible groups that are actual groups
    finish_times_filled_proportion = unique_finishing_times/possible_groups
    #Get the sizes of all the groups, ie count how many people have the same finishing time
    group_sizes = Counter(finishing_times)
    #Get just the sizes of actual groups (ie groups larger than 1)
    group_sizes_over_1 = [v for v in group_sizes.values() if v > 1]
    if len(group_sizes_over_1)==0:
        print(f"No groups larger than 1 found, setting group_sizes_over_1 to [0] to avoid divide by zero")
        group_sizes_over_1 = [0]
    #Get the number of groups that are larger than 1
    group_count = len([k for k,v in group_sizes.items() if v > 1])
    #Get the number of riders in groups larger than 1
    grouped_rider_count = sum([v for v in group_sizes.values() if v > 1])
    #proportion of finishing times that are groups (ie have more than one person with the same time)
    proportion_grouped = grouped_rider_count/len(finishing_times)
    #Get the max group size
    max_group_size = max(group_sizes.values())
    #get the average group size
    avg_group_size = sum(group_sizes_over_1)/len(group_sizes_over_1)
    #get the std deviation of the group sizes
    stdev_group_size = np.std(group_sizes_over_1)
    #get the proportion of the total field that is in the largest group
    max_group_proportion = max_group_size/len(race.results)
    #find the group that is the size of the largest group size and has the lowest finishing time
    max_group = [k for k,v in group_sizes.items() if v == max_group_size]
    min_max_group_time = min(max_group)
    #Get the finishing time percentile for the largest group finishing time, keeping in mind that we want the first instance of the lowest time equal to the finishing time of the largest group
    max_group_percentile = finishing_times.index(min_max_group_time)/len(finishing_times)
    #get the max group finishing position
    max_group_position = finishing_times.index(min_max_group_time) + 1
    #get the zscore for the 0th through 50th percentile times, focusing only on the front half as the back half is often compromised in terms of effort.
    front_half_zscores = {}
    if np.std(finishing_times) == 0.0:
        print(f"Standard deviation of finishing times is 0, setting to .001 to avoid divide by zero")
        finish_stdev = .001
    else:
        finish_stdev = np.std(finishing_times)
    
    for percentile in [0,5,10,15,20,25,30,35,40,45,50]:
        front_half_zscores[str(percentile)] = (np.percentile(finishing_times,percentile)-np.mean(finishing_times))/finish_stdev
    #get the finishing time zscore for the winner
    winner_zscore = (min(finishing_times)-np.mean(finishing_times))/finish_stdev
    #get the finishing time zscore for the last finisher
    last_zscore = (max(finishing_times)-np.mean(finishing_times))/finish_stdev
    #get the finishing time zscore for the max group finishing time
    max_group_zscore = (min_max_group_time-np.mean(finishing_times))/finish_stdev
    #get the gap to the winner for the 5th, 10th, 25th, 75th, 90th and 95th percentile finishing times
    gaps_to_winner = {}
    for percentile in [5,10,15,20,25,30,35,40,45,50]:
        gaps_to_winner[str(percentile)] = np.percentile(finishing_times,percentile)-min(finishing_times)
    #get the gap to the winner for the max group finishing time
    max_group_gap_to_winner = min_max_group_time-min(finishing_times)
    
    #max group data
    max_group_data = {}
    max_group_data['max_group_size'] = max_group_size
    max_group_data['max_group_proportion'] = max_group_proportion
    max_group_data['max_group_finish_time_percentile'] = max_group_percentile
    max_group_data['max_group_position'] = max_group_position
    max_group_data['max_group_zscore'] = max_group_zscore
    max_group_data['max_group_gap_to_winner'] = max_group_gap_to_winner
    
    #group data
    group_data = {}
    group_data['group_count'] = group_count
    group_data['avg_group_size'] = avg_group_size
    group_data['stdev_group_size'] = stdev_group_size
    group_data['avg_group_gap'] = avg_group_gap
    group_data['stdev_group_gap'] = stdev_group_gap
    group_data['proportion_grouped'] = proportion_grouped


    #Distribution data (zscores)
    distribution_data = {}
    distribution_data['winner_zscore'] = winner_zscore
    distribution_data['last_zscore'] = last_zscore
    distribution_data['5th_percentile_zscore'] = front_half_zscores['5']
    distribution_data['10th_percentile_zscore'] = front_half_zscores['10']
    distribution_data['15th_percentile_zscore'] = front_half_zscores['15']
    distribution_data['20th_percentile_zscore'] = front_half_zscores['20']
    distribution_data['25th_percentile_zscore'] = front_half_zscores['25']
    distribution_data['30th_percentile_zscore'] = front_half_zscores['30']
    distribution_data['35th_percentile_zscore'] = front_half_zscores['35']
    distribution_data['40th_percentile_zscore'] = front_half_zscores['40']
    distribution_data['45th_percentile_zscore'] = front_half_zscores['45']
    distribution_data['50th_percentile_zscore'] = front_half_zscores['50']
    
    #Finishing time data
    finish_time_data = {}
    finish_time_data['avg_gap'] = gap_avg
    finish_time_data['stdev_gap'] = gap_stdev
    finish_time_data['winning_time'] = min(finishing_times)
    finish_time_data['gap_to_last'] = max(finishing_times)-min(finishing_times)
    finish_time_data['finishing_times_filled_proportion'] = finish_times_filled_proportion
    finish_time_data['non_finisher_proportion'] = non_finisher_proportion
    finish_time_data['5th_percentile_gap'] = gaps_to_winner['5']
    finish_time_data['10th_percentile_gap'] = gaps_to_winner['10']
    finish_time_data['15th_percentile_gap'] = gaps_to_winner['15']
    finish_time_data['20th_percentile_gap'] = gaps_to_winner['20']
    finish_time_data['25th_percentile_gap'] = gaps_to_winner['25']
    finish_time_data['30th_percentile_gap'] = gaps_to_winner['30']
    finish_time_data['35th_percentile_gap'] = gaps_to_winner['35']
    finish_time_data['40th_percentile_gap'] = gaps_to_winner['40']
    finish_time_data['45th_percentile_gap'] = gaps_to_winner['45']
    finish_time_data['50th_percentile_gap'] = gaps_to_winner['50']
        
    #combine all the data into one dictionary
    all_data = {}
    all_data['max_group_data'] = max_group_data
    all_data['group_data'] = group_data
    all_data['distribution_data'] = distribution_data
    all_data['finish_time_data'] = finish_time_data
    
    return all_data

#Next we want to develop tools for extracting races and stages from the database
#As we load the races we want to make sure we have the tour and race type.

#A Tour Level Race DB will have a list of races objects. One for each one day and stage race. Stage races need to be unpacked.
#The information we're going to want for these races is going to be something like:
# Race ID, Race Name, Race Year, Race Date, Tour Type, Race Type, and then the finishing time distribution

#So, start with a function to parse a full race (ie netural stage race/one_day race object) object. 

def generate_finishing_time_data_from_race(race:Race)->Union[list,None]:
    """Take in a Race object and get a list of dictionaries with the finishing time data for each stage, as extacted by the extract_finishing_time_distributions function.
    Gives back a list for each stage and GC if it's a stage race, or a list with just one set of data if it's a one day race. If there are no finishing times, return None.
    Args:
        race: Race object that we want to fully process for finishing time data.
    Returns:
        a list of dictionaries with the finishing time data for each stage, as extacted by the extract_finishing_time_distributions function.
    """
    #Check if it's a stage race or a one_day.
    if not race.stage_race:
        #If it'a s one_day, we can just process it as is
        #See if we can get finishing time data. if not, return None
        try:
            finishing_time_data = extract_finishing_time_distributions(race)
            if finishing_time_data is None:
                print(f"{race.name}, {race.year}, has no finishing time data")
                return None
        except:
            print(f"Error processing {race.name}, {race.year} for finishing time data")
            return None
        #now let's get the rest of the data
        tour_type = race.category
        race_type = "one_day"
        race_id = race.fc_race_id
        race_name = race.name
        race_date = race.date
        race_year = race.year
        race_data_dict = {'race_id':race_id,'race_name':race_name,'tour_type':tour_type,'race_type':race_type,'race_date':race_date,'race_year':race_year}
        for sub_d in finishing_time_data.values():
            race_data_dict.update(sub_d)
        return [race_data_dict]
    else:
        tour_type = race.category
        parent_race_name = race.name
        race_year = race.year
        race_id = race.fc_race_id
        stage_data = []
        for stage in race.stages:
            #See if we can get finishing time data. if not, return None
            try:
                finishing_time_data = extract_finishing_time_distributions(stage)
                if finishing_time_data is None:
                    print(f"{parent_race_name}, {stage.name}, {stage.year}, has no finishing time data")
                    continue
            except:
                print(f"Error processing {parent_race_name}, {stage.name}, {stage.year} for finishing time data")
                continue
            #now let's get the rest of the data
            if "GC" in stage.name.strip():
                race_type = "gc"
            else:
                race_type = "stage"
            race_date = stage.date
            race_name = f"{parent_race_name}, {stage.name}"
            race_data_dict = {'race_id':race_id,'race_name':race_name,'tour_type':tour_type,'race_type':race_type,'race_date':race_date,'race_year':race_year}
            for sub_d in finishing_time_data.values():
                race_data_dict.update(sub_d)
            stage_data.append(race_data_dict)
        if len(stage_data)==0:
            print(f"No stages with finishing time data for {race.name}, {race.year}")
            return None
        return stage_data

def generate_finishing_time_data_from_tour(tour:FCCyclingTour)->list:
    """Process a tour level object and return a list of dictionaries with all the races from that tour level object. It will return a flattened list so each stage and gc from a stage race will be an entry in the list along side each one day.
    Args:
        tour: FCCyclingTour object that we want to fully process for finishing time data.
    Returns:
        a list of dictionaries with the finishing time data for each stage, as extacted by the extract_finishing_time_distributions function.
    """
    tour_race_data = []
    for race in tour.races:
        race_data = generate_finishing_time_data_from_race(race)
        if race_data is not None:
            tour_race_data.extend(race_data)
    
    return tour_race_data

def generate_finishing_time_data_from_year(year:FCCyclingYear)->list:
    """Process a full year worth tours, WT, Pro, and .1, and return a list of dictionaries with finishing time data for all races with finishing time objects. Returns a flattend list of finishing time characteristics for each stage or gc or one day of a tour and all tours are in one list as well.
    Args: 
        year: FCCyclingYear object that we want to fully process for finishing time data.
    Returns:
        a list of dictionaries with the finishing time data for each stage, as extacted by the extract_finishing_time_distributions function."""
    year_race_data = []
    #First, try wt
    try:
        wt_data = generate_finishing_time_data_from_tour(year.wt)
        if len(wt_data) == 0:
            print(f"No data for WT races in {year.year}")
        else:
            print(f"Found {len(wt_data)} WT races with time data for {year.year}")
            year_race_data.extend(wt_data)
    except:
        print(f"Error processing WT data for {year.year}")
    #Next, try pro
    try:
        pro_data = generate_finishing_time_data_from_tour(year.pro)
        if len(pro_data) == 0:
            print(f"No data for Pro races in {year.year}")
        else:
            print(f"Found {len(pro_data)} Pro races with time data for {year.year}")
            year_race_data.extend(pro_data)
    except:
        print(f"Error processing Pro data for {year.year}")
    #Next try d1
    try:
        d1_data = generate_finishing_time_data_from_tour(year.d1)
        if len(d1_data) == 0:
            print(f"No data for .1 races for {year.year}")
        else:
            print(f"Found {len(d1_data)} .1 races with time data for {year.year}")
            year_race_data.extend(d1_data)
    except:
        print(f"Error processing .1 data for {year.year}")
    return year_race_data

def gen_race_char_db(year_range:List[int],db_base_path:str=DB_PATH)->pd.DataFrame:
    """
    Given a range of years (as a a linst of integers that should be within 2010 and 2025), create a dataframe with the finishing time characteristics for each race. Each row of the dataframe is a race (GC, Stage, or one day), the columns are the key data columns. 
    Adjust those columns by updating the finishing-dist_cols variable within this function.
    Args:
        year_range: a list of integers representing the years to include in the database. Should be between 2010 and 2025.
        db_base_path: the base path to the database. Defaults to DB_PATH. The database path should have a folder for each year.
    Returns:
        a dataframe with the finishing time characteristics for each race."""
    db_l = []
    #Need to update this with the key columns that I care about
    finishing_dist_cols = ['max_group_size','max_group_proportion','max_group_finish_time_percentile','max_group_position','max_group_zscore','max_group_gap_to_winner','group_count','avg_group_size','stdev_group_size','avg_group_gap','stdev_group_gap','proportion_grouped','winner_zscore','last_zscore','5th_percentile_zscore','10th_percentile_zscore','25th_percentile_zscore','50th_percentile_zscore','75th_percentile_zscore','90th_percentile_zscore','95th_percentile_zscore','avg_gap','stdev_gap','winning_time','gap_to_last','finishing_times_filled_proportion','non_finisher_proportion']
    for year in year_range:
        year_dir_path = os.path.join(db_base_path,f"{year}")
        try:
            yeardb = load_year_path(year_dir_path)
            race_char_l = generate_finishing_time_data_from_year(yeardb)
            if race_char_l is None or race_char_l == []:
                print(f"No Race Data for {year}")
            db_l.extend(race_char_l)
        except:
            print(f"Error loading {year} database")
    df = pd.concat([pd.DataFrame.from_dict(race_c,orient='index') for race_c in db_l],axis=1).T
    df = df.dropna()
    #convert df to numerical dtypes
    for col in finishing_dist_cols:
        try:
            df[col] = pd.to_numeric(df[col],errors='coerce')
        except:
            continue
    #convert race_date to datetime
    df['race_date'] = pd.to_datetime(df['race_date'],errors='coerce')
    #Sort by race_date, ascending
    df.sort_values(by='race_date',ascending=True,inplace=True)
    #reset the index so it's numbers counting up from zero
    df.index = range(len(df))
    
    return df

    
#let's write three functions, one for gc, one for one_day, and one for stages. Each function will produce a dataframe with the key finishing time data that has been processed and cleaned to remove duplicate features as well as extreme outlier races (we'll be trimming the data by about 10% total for each race)
#We'll use only races in each of these data frames for predicting rider performance in that type of race.
#The first way that I want to use this is to see if we can use it to bucket riders into categories. What I want to try to extract is the values/weights/coefficients that are most useful for segmenting riders into categories when it comes to predicitng finishign places. 
#In the first pass we used LinearRegression coefficients for different categories. But I would like to see if we can get some thing usable and interpretable from an ordinal regression model.
#I have filtering conditions special for GC, one_day, and stages. Let's set that up and see what we can get about riders.

class RaceCharDB:
    """A class to represent a race characteristic database. Created by passiing a list of years as integers to the constructor (should be between 2010 and 2025) and a path to a databse file structure that has the stored race data with a foldder for each year.
    The class object then creates a dataframe with the finishing time characteristics for each type of race: GC, Stage, One Day.
    The key utility with this class object is to filter out different characteristics for different types of races. Each class method, gen_gc_db, gen_one_day_db, and gen_stag_db has a differet list for columns to ignore and drop based on the race.
    We can also filter out outlier races based on z-score for each column. The default is 3.5, but this can be changed by passing a different value to the outlier_limit parameter.
    The class also has a method to return all races and their characteristics prior to a given date or year, of a given race type, or by a given fc_race_id.
    Finally, the class has a method to look up a race directly and return the characteristics for that race."""
    def __init__(self,year_range:List[int],db_base_path:str=DB_PATH):
        self.year_range = year_range
        self.db_base_path = db_base_path
        self.db = gen_race_char_db(year_range,db_base_path)
        self._non_data_cols = ['race_id','race_name','tour_type','race_type','race_date','race_year']
        self.gen_gc_db()
        self.gen_one_day_db()
        self.gen_stage_db()
        
    
    def _filter_outliers(self,df:pd.DataFrame, z_score_limit:float=3.5):
        """Filter outlier races based on a z-score for each race characteristic column. The default is 3.5, but this can be changed by passing a different value to the z_score_limit parameter.
        Args:
            df: the dataframe to filter
            z_score_limit: the z-score limit to use for filtering. Default is 3.5.
        Returns:
            a filtered dataframe with outliers dropped."""
        filtered_df = df.copy()
        for col in [col for col in filtered_df.columns if col != 'winning_time']:
            #Calculate the zscore for each row in the column
            col_mean = filtered_df[col].mean()
            col_std = filtered_df[col].std()
            if col_std == 0.0:
                print(f"Standard deviation of {col} is 0, setting to .001 to avoid divide by zero")
                col_std = .001
            zscores = (filtered_df[col] - col_mean) / col_std
            #Filter out the rows where the zscore is greater than 3.5
            filtered_df = filtered_df.loc[np.abs(zscores) <= z_score_limit]
        print(f"Outlier Races removed: {df.shape[0]-filtered_df.shape[0]}, {1-filtered_df.shape[0]/df.shape[0]:.2%}")
        return filtered_df
    
    
  
    def gen_gc_db(self,outlier_limit:float=5.0) -> pd.DataFrame:
        """Creates a dataframe with the finishing time characteristics for all GC races in the database. The dataframe is filtered for outliers and the self.gc attribute is set to the resulting dataframe.
        Args:
            outlier_limit: the z-score limit to use for filtering. Default is 5.0.
        Returns:
            a dataframe with the finishing time characteristics of GC. It also sets the self.gc attribute to the dataframe."""
        gc_db = self.db[self.db['race_type'] == 'gc'].copy()
        if gc_db.shape[0] == 0:
            print("No GC results in the database for this year range")
            self.gc = gc_db
            return gc_db
        #drop the group and max group columns
        gc_db.drop(columns=['max_group_size','max_group_proportion','max_group_finish_time_percentile','max_group_position','max_group_zscore','max_group_gap_to_winner','group_count','avg_group_size','stdev_group_size','avg_group_gap','stdev_group_gap','proportion_grouped'],inplace=True) 
        #drop redundant columns
        gc_db.drop(columns=['winner_zscore','10th_percentile_zscore','avg_gap','stdev_gap'],inplace=True)
        #drop last place influence cols
        gc_db.drop(columns=['gap_to_last','75th_percentile_zscore','90th_percentile_zscore','95th_percentile_zscore','last_zscore','finishing_times_filled_proportion','75th_percentile_gap','90th_percentile_gap','95th_percentile_gap'],inplace=True)
        #get the data only colums to filter outliers
        gc_data_only = gc_db.drop(columns=self._non_data_cols)
        #filter outliers
        gc_filtered = self._filter_outliers(gc_data_only,outlier_limit)
        #print the 
        #merge the filtered data back into the original dataframe
        final_gc_df = gc_db.loc[gc_filtered.index].copy()
        self.gc = final_gc_df
        return final_gc_df

    def gen_one_day_db(self,outlier_limit:float=5.0) -> pd.DataFrame:
        """Creates a dataframe with the finishing time characteristics for all one day races in the database. The dataframe is filtered for outliers and the self.one_day attribute is set to the resulting dataframe.
        Args:
            outlier_limit: the z-score limit to use for filtering. Default is 5.0.
        Returns:
            a dataframe with the finishing time characteristics
        """
        one_day_db = self.db[self.db['race_type']=='one_day'].copy()
        if one_day_db.shape[0] == 0:
            print(f"No one day races in the database for this year range")
            self.one_day = one_day_db
            return one_day_db
        #drop redundant columns
        redundant_one_day_cols = ['winner_zscore','max_group_proportion', 'stdev_group_size', 'avg_group_size','max_group_position','max_group_zscore',	'max_group_gap_to_winner','stdev_group_gap','avg_gap', 'gap_to_last']
        one_day_db.drop(columns=redundant_one_day_cols,inplace=True)
        #Drop the back half of distribution columns
        back_half_cols = ['75th_percentile_zscore','90th_percentile_zscore','95th_percentile_zscore','last_zscore','75th_percentile_gap','90th_percentile_gap','95th_percentile_gap']
        one_day_db.drop(columns=back_half_cols,inplace=True)
        #filter outliers for one_day
        one_day_data_only = one_day_db.drop(columns=self._non_data_cols)
        one_day_filtered = self._filter_outliers(one_day_data_only,outlier_limit)
        #merge the filtered data back into the original dataframe
        one_day_final_df = one_day_db.loc[one_day_filtered.index].copy()
        self.one_day = one_day_final_df
        return one_day_final_df
    
    def gen_stage_db(self,outlier_limit:float=5.0) -> pd.DataFrame:
        """Creates a dataframe with the finishing time characteristics for all stages in the database. Also filters out outliers and sets the self.stage attribute to the resulting dataframe.
        Args:
            outlier_limit: the z-score limit to use for filtering. Default is 5.0.
        Returns:
            a dataframe with the finishing time characteristics of stages. It also sets the self.stage attribute to the dataframe.
        """
        stage_db = self.db[self.db['race_type']=='stage'].copy()
        if stage_db.shape[0] == 0:
            print(f"No stages in the database for this year range")
            self.stage = stage_db
            return stage_db
        #drop redundant columns
        redundant_stage_cols = ['max_group_proportion', 'stdev_group_size','max_group_position','max_group_gap_to_winner','stdev_gap','winner_zscore','10th_percentile_zscore']
        stage_db.drop(columns=redundant_stage_cols,inplace=True)
        back_half_cols = ['75th_percentile_zscore','90th_percentile_zscore','95th_percentile_zscore','last_zscore','gap_to_last','75th_percentile_gap','90th_percentile_gap','95th_percentile_gap']
        stage_db.drop(columns=back_half_cols,inplace=True)
        #filter outliers for stages
        stage_data_only = stage_db.drop(columns=self._non_data_cols)
        stage_filtered = self._filter_outliers(stage_data_only,outlier_limit)
        #merge the filtered data back into the original dataframe
        stage_final_df = stage_db.loc[stage_filtered.index].copy()
        self.stage = stage_final_df
        return stage_final_df
    
    def __post_init__(self):
        self.gen_gc_db()
        self.gen_one_day_db()
        self.gen_stage_db()

    def find_prior_races(self,race_type:str,prior_to_date:str,fc_race_id:int|None=None)->pd.DataFrame:
        """Returns a dataframe with all races that are prior to given date, passed as YYYY-MM-DD str and race type (gc, stage, one_day). Can also filter by fc_race_id to pickout specific races.
        Args:
            race_type: the type of race to filter by. Should be one of 'gc', 'stage', or 'one_day'.
            prior_to_date: the date to filter by. Should be in YYYY-MM-DD format.
            fc_race_id: the fc_race_id for the race to filter by, passed as an int. If None, will return all races.
        Returns:
            a dataframe with all the races prior to the given date of the given race type.
        """
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
    
    def race_lookup(self,fc_race_id:int,race_type:str,year:int,stage_name:str|None=None)->pd.DataFrame:
        """Look up a specific race in the database by passing an fc_race_id as an int, the race_type as a str (gc, stage, or one_day), the year as an int, and an optional stage_name as a str if looking up a stage. Will throw an error if set race_type to stage but don't pass a stage name
        Args:
            fc_race_id: the fc_race_id as an int for the race. This will be the same for all stages and the gc of a stage race.
            race_type: the race_type as a str. Should be one of 'gc', 'stage', or 'one_day'.
            year: the year as an int
            stage_name: the stage name as a str. Only needed if race_type is set to 'stage'.
        Returns:
            a one row dataframe with with the race characteristics
        """
        
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