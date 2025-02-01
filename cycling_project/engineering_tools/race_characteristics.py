from cycling_project.webscrape_tools.create_race_data import Race,Stage
from typing import Union
import numpy as np
from collections import Counter

def extract_finishing_time_distributions(race:Union[Race,Stage]):
    #check for null results
    if race.results is None:
        print(f"{race.name} has no results, skipping finishing time distributions")
        return None
    #check for empty results
    if len(race.results) < 3:
        print(f"{race.name} has too few results, skipping finishing time distributions")
        return None
    if isinstance(race,Race):
        race_time = race.race_time
    elif isinstance(race,Stage):
        race_time = race.time
    #check for missing finishing times
    if race_time is None or race_time=='' or race_time==[]:
        print(f"{race.name} has no times, skipping finishing time distributions")
        return None
    total_time = race_time
    finishing_gaps = []
    for result in race.results:
        if isinstance(result.get('gap'),(float,int)):
            finishing_gaps.append(result.get('gap'))
        else:
            print(f"Non-time gap for {result.get('name')}, skipping")
    gap_avg = sum(finishing_gaps)/len(finishing_gaps)
    gap_stdev = np.std(finishing_gaps)
    
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
    #get the average gap between groups
    avg_group_gap = sum(group_gaps)/len(group_gaps)
    #get the std deviation of the gaps between groups
    stdev_group_gap = np.std(group_gaps)
    #get the possible finishing group counts, which is just the number of seconds between the first and last finishing time
    possible_groups = sorted_times[-1]-sorted_times[0]
    #get the proportion of possible groups that are actual groups
    finish_times_filled_proportion = unique_finishing_times/possible_groups
    #Get the sizes of all the groups, ie count how many people have the same finishing time
    group_sizes = Counter(finishing_times)
    #Get the number of groups that are larger than 1
    group_count = len([k for k,v in group_sizes.items() if v > 1])
    #proportion finishers that are grouped
    proportion_grouped = group_count/unique_finishing_times
    #Get the max group size
    max_group_size = max(group_sizes.values())
    #get the average group size
    avg_group_size = sum(group_sizes.values())/len(group_sizes)
    #get the std deviation of the group sizes
    stdev_group_size = np.std(list(group_sizes.values()))
    #get the proportion of the total field that is in the largest group
    max_group_proportion = max_group_size/len(race.results)
    #find the group that is the size of the largest group size and has the lowest finishing time
    max_group = [k for k,v in group_sizes.items() if v == max_group_size]
    min_max_group_time = min(max_group)
    #Get the finishing time percentile for the largest group finishing time, keeping in mind that we want the first instance of the lowest time equal to the finishing time of the largest group
    max_group_percentile = finishing_times.index(min_max_group_time)/len(finishing_times)
    #get the max group finishing position
    max_group_position = finishing_times.index(min_max_group_time) + 1
    #get the zscore for the 10th, 25th, 75th and 90th percetile finishing times
    zscores = {}
    if np.std(finishing_times) == 0.0:
        print(f"Standard deviation of finishing times is 0, setting to .001 to avoid divide by zero")
        finish_stdev = .001
    else:
        finish_stdev = np.std(finishing_times)
    
    for percentile in [5,10,25,50,75,90,95]:
        zscores[str(percentile)] = (np.percentile(finishing_times,percentile)-np.mean(finishing_times))/finish_stdev
    #get the finishing time zscore for the winner
    winner_zscore = (min(finishing_times)-np.mean(finishing_times))/finish_stdev
    #get the finishing time zscore for the last finisher
    last_zscore = (max(finishing_times)-np.mean(finishing_times))/finish_stdev
    #get the finishing time zscore for the max group finishing time
    max_group_zscore = (min_max_group_time-np.mean(finishing_times))/finish_stdev
    #get the gap to the winner for the 10th, 25th, 75th and 90th percentile finishing times
    gaps_to_winner = {}
    for percentile in [10,25,50,75,90]:
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
    group_data['group_count'] = unique_finishing_times
    group_data['avg_group_size'] = avg_group_size
    group_data['stdev_group_size'] = stdev_group_size
    group_data['avg_group_gap'] = avg_group_gap
    group_data['stdev_group_gap'] = stdev_group_gap
    group_data['proportion_grouped'] = proportion_grouped


    #Distribution data (zscores)
    distribution_data = {}
    distribution_data['winner_zscore'] = winner_zscore
    distribution_data['last_zscore'] = last_zscore
    distribution_data['5th_percentile_zscore'] = zscores['5']
    distribution_data['10th_percentile_zscore'] = zscores['10']
    distribution_data['25th_percentile_zscore'] = zscores['25']
    distribution_data['50th_percentile_zscore'] = zscores['50']
    distribution_data['75th_percentile_zscore'] = zscores['75']
    distribution_data['90th_percentile_zscore'] = zscores['90']
    distribution_data['95th_percentile_zscore'] = zscores['95']
    
    #Finishing time data
    finish_time_data = {}
    finish_time_data['avg_gap'] = gap_avg
    finish_time_data['stdev_gap'] = gap_stdev
    finish_time_data['winning_time'] = min(finishing_times)
    finish_time_data['gap_to_last'] = max(finishing_times)-min(finishing_times)
    finish_time_data['finishing_times_filled_proportion'] = finish_times_filled_proportion
    finish_time_data['non_finisher_proportion'] = non_finisher_proportion
        
    #combine all the data into one dictionary
    all_data = {}
    all_data['max_group_data'] = max_group_data
    all_data['group_data'] = group_data
    all_data['distribution_data'] = distribution_data
    all_data['finish_time_data'] = finish_time_data
    
    return all_data