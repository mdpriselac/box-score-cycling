import numpy as np
from scipy import stats
from cycling_project.webscrape_tools.create_race_data import Race,Stage
from cycling_project.data_loading_tools.load_scraped_data import FCCyclingTour,FCCyclingYear,load_year_path
from cycling_project.webscrape_tools.find_races import DB_PATH
from typing import Union
import pandas as pd
import os

def normalized_variance(times):
    """
    Calculate the normalized variance of race finishing times.
    
    Args:
        times: List of finishing times (in seconds), with the winning time being the first element.
        
    Returns:
        Normalized variance.
    """
    winning_time = times[0]
    normalized_times = [time / winning_time for time in times]
    return np.var(normalized_times)

def normalized_standard_deviation(times):
    """
    Calculate the normalized standard deviation of race finishing times.
    
    Args:
        times: List of finishing times (in seconds), with the winning time being the first element.
        
    Returns:
        Normalized standard deviation.
    """
    return np.sqrt(normalized_variance(times))

def normalized_skewness(times):
    """
    Calculate the normalized skewness of race finishing times.
    
    Args:
        times: List of finishing times (in seconds), with the winning time being the first element.
        
    Returns:
        Normalized skewness.
    """
    winning_time = times[0]
    normalized_times = [time / winning_time for time in times]
    return stats.skew(normalized_times)

def normalized_kurtosis(times):
    """
    Calculate the normalized kurtosis of race finishing times.
    
    Args:
        times: List of finishing times (in seconds), with the winning time being the first element.
        
    Returns:
        Normalized kurtosis.
    """
    #winning_time = times[0]
    #normalized_times = [time / winning_time for time in times]
    return stats.kurtosis(times)

def normalized_gini_coefficient(times):
    """
    Calculate the normalized Gini coefficient of race finishing gaps.
    
    The Gini coefficient measures inequality in a distribution.
    A value of 0 represents perfect equality, while 1 represents perfect inequality.
    
    Args:
        times: List of finishing times (in seconds), with the winning time being the first element.
        
    Returns:
        Normalized Gini coefficient.
    """
    #winning_time = times[0]
    #normalized_times = [time / winning_time for time in times]
    
    # Sort the normalized times
    sorted_times = np.sort(times)
    n = len(sorted_times)
    
    # Calculate cumulative sum
    cumsum = np.cumsum(sorted_times)
    
    # Calculate Lorenz curve points
    lorenz_curve = cumsum / cumsum[-1]
    
    # Calculate area under the Lorenz curve
    area = np.trapz(lorenz_curve, dx=1/n)
    
    # Calculate Gini coefficient: G = 1 - 2 * area
    gini = 1 - 2 * area
    
    return gini

def normalized_shannon_entropy(times):
    """
    Calculate the normalized Shannon entropy of race finishing time gaps.
    
    Shannon entropy measures the uncertainty or randomness in a distribution.
    
    Args:
        times: List of finishing times (in seconds), with the winning time being the first element.
        
    Returns:
        Normalized Shannon entropy.
    """
    #winning_time = times[0]
    #normalized_times = [time / winning_time for time in times]
    
    # Bin the data to calculate probabilities
    hist, bin_edges = np.histogram(times, bins='auto', density=True)
    bin_width = bin_edges[1] - bin_edges[0]
    
    # Calculate probabilities
    probabilities = hist * bin_width
    
    # Filter out zero probabilities
    probabilities = probabilities[probabilities > 0]
    
    # Calculate entropy
    entropy = -np.sum(probabilities * np.log2(probabilities))
    
    # Normalize by maximum entropy (log2(n))
    max_entropy = np.log2(len(times))
    normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0
    
    return normalized_entropy

def create_stat_measures_race(race:Union[Race,Stage])->Union[dict,None]:
    """
    Create a dictionary of statistical measures
    for a given bike race:
    - Normalized Variance
    - Normalized Standard Deviation
    - Normalized Skewness
    - Normalized Kurtosis
    - Normalized Gini Coefficient
    - Normalized Shannon Entropy
    Args:
        race: a race or stage object
    Returns:
        A dictionary containing the statistical measures
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
    if race_time is None or race_time=='' or race_time==[] or race_time==0:
        print(f"{race.name} has no times, skipping finishing time distributions")
        return None
    total_time = race_time
    #Check if we pulled GC from a TTT stage for a stage race
    if total_time/30000 >=1.0 and 'stage:' in race.name.lower():
        print(f"{race.name} has too long of a race time (over 8hrs 20min), probably pulling GC times for a TTT stage skipping finishing time distributions")
        return None
    #Check if we have a secret stage race that's not marked properly in the data and shows up as a one day
    if total_time/30000 >=1.0 and isinstance(race,Race) and not race.stage_race:
        print(f"{race.name} has too long of a race time (over 8hrs 20min), probably pulling GC times for a TTT stage skipping finishing time distributions")
        return None
    #create a list of times based on winning time plus gaps
    finishing_gaps = []
    for result in race.results:
        if isinstance(result.get('gap'),(float,int)):
            finishing_gaps.append(result.get('gap'))
        else:
            continue
            #print(f"Non-time gap for {result.get('name')}, skipping")
    finishing_times = [total_time + gap for gap in finishing_gaps]
    abandon_ratio = len(finishing_times)/len(race.results)
    #create the statistical measures dictionary
    stat_measures = {
        'normalized_variance': normalized_variance(finishing_times),
        'normalized_standard_deviation': normalized_standard_deviation(finishing_times),
        'normalized_skewness': normalized_skewness(finishing_times),
        'normalized_kurtosis': normalized_kurtosis(finishing_gaps),
        'normalized_gini_coefficient': normalized_gini_coefficient(finishing_gaps),
        'normalized_shannon_entropy': normalized_shannon_entropy(finishing_gaps),
        'total_time': total_time,
        'abandon_ratio': abandon_ratio,
        'finishing_times': finishing_times
    }
    return stat_measures

def process_top_level_race_stat_measures(race:Race)->list:
    """Take in a top level race object, create the stat measures for each stage,gc, or just one day results.
    Returns a list of of stat measures dictionaries for each stage, gc, or one day results.
    Args:
        race: a race object
    Returns:
        A list of dictionaries containing the statistical measures for each competition event"""
    #if it's not a stage race, process it straight away
    results = []
    if not race.stage_race:
        race_stat_dict = create_stat_measures_race(race=race)
        if race_stat_dict is not None:
            #get the identifying race info
            race_stat_dict['name'] = race.name
            race_stat_dict['parent_race'] = ''
            race_stat_dict['stage_name'] = ''
            race_stat_dict['year'] = race.year
            race_stat_dict['date'] = race.date
            race_stat_dict['fc_race_id'] = race.fc_race_id
            race_stat_dict['tour'] = race.category
            race_stat_dict['race_type'] = 'one_day'
            results.append(race_stat_dict)
        return results
    else:
        for stage in race.stages:
            stage_stat_dict = create_stat_measures_race(race=stage)
            if stage_stat_dict is not None:
                stage_stat_dict['parent_race'] = stage.race
                stage_stat_dict['name'] = stage.race + ': ' + stage.name
                stage_stat_dict['stage_name'] = stage.name
                stage_stat_dict['year'] = stage.year
                stage_stat_dict['date'] = stage.date
                stage_stat_dict['fc_race_id'] = stage.fc_race_id
                stage_stat_dict['tour'] = stage.category
                if stage.name.lower().strip().replace(':','') == 'gc':
                    stage_stat_dict['race_type'] = 'gc'
                else:
                    stage_stat_dict['race_type'] = 'stage'
                results.append(stage_stat_dict)
    
    return results

def process_tour_stat_measures(tour:FCCyclingTour)->pd.DataFrame:
    """Get all results for a tour and return a list of stat measures dictionaries as a dataframe.
    Args:
        tour: a FCCyclingTour object
    Returns:
        a dataframe with the stat measures for each stage, gc, or one day results"""
    tour_stat_measures = []
    for race in tour.races:
        processed_race = process_top_level_race_stat_measures(race=race)
        if len(processed_race) > 0:
            tour_stat_measures.extend(processed_race)
    #create a dataframe from the list of dictionaries
    df = pd.DataFrame(tour_stat_measures)
    #check for empty dataframe
    if df.empty:
        print(f"No stat measures found for {tour.name}")
        return None
    return df

def process_year_stat_measures(year:FCCyclingYear)->pd.DataFrame:
    """Get all results for a year and return a list of stat measures dictionaries as a dataframe.
    Args:
        year: a FCCyclingYear object
    Returns:
        a dataframe with the stat measures for each stage, gc, or one day results"""
    year_dfs = []
    #process wt races
    wt_results = process_tour_stat_measures(tour=year.wt)
    if wt_results is not None:
        year_dfs.append(wt_results)
    #process pro races
    pro_results = process_tour_stat_measures(tour=year.pro)
    if pro_results is not None:
        year_dfs.append(pro_results)
    #process d1 races
    d1_results = process_tour_stat_measures(tour=year.d1)
    if d1_results is not None:
        year_dfs.append(d1_results)
    year_concat_df = pd.concat(year_dfs, ignore_index=True)
    return year_concat_df

def create_stat_measures_db(year_range:tuple[int,int],db_path:str=DB_PATH)->pd.DataFrame:
    """Create a database of stat measures for a given year range.
    Args:
        year_range: a tuple of start and end years
        db_path: the path to the database
    Returns:
        a dataframe with the stat measures for each stage, gc, or one day results"""
    #create a list of years
    years = []
    for year in range(year_range[0],year_range[1]+1):
        years.append(str(year))
    #create a list of dataframes for each year
    year_dfs = []
    for year in years:
        year_path = os.path.join(db_path,year)
        year_db = load_year_path(year_dir_path=year_path)
        year_df = process_year_stat_measures(year=year_db)
        if year_df is not None:
            year_dfs.append(year_df)
    #create a dataframe from the list of dataframes
    stat_measures_df = pd.concat(year_dfs, ignore_index=True)
    return stat_measures_df