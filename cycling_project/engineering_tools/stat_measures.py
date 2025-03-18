import numpy as np
from scipy import stats
from cycling_project.webscrape_tools.create_race_data import Race,Stage
from typing import Union

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
    winning_time = times[0]
    normalized_times = [time / winning_time for time in times]
    return stats.kurtosis(normalized_times)

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
    if race_time is None or race_time=='' or race_time==[]:
        print(f"{race.name} has no times, skipping finishing time distributions")
        return None
    total_time = race_time
    #Check if we pulled GC from a TTT stage for a stage race
    if total_time/28800 >=1.0 and 'stage:' in race.name.lower():
        print(f"{race.name} has too long of a race time (over 7hrs 40min), probably pulling GC times for a TTT stage skipping finishing time distributions")
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
    #create the statistical measures dictionary
    stat_measures = {
        'normalized_variance': normalized_variance(finishing_times),
        'normalized_standard_deviation': normalized_standard_deviation(finishing_times),
        'normalized_skewness': normalized_skewness(finishing_times),
        'normalized_kurtosis': normalized_kurtosis(finishing_times),
        'normalized_gini_coefficient': normalized_gini_coefficient(finishing_gaps),
        'normalized_shannon_entropy': normalized_shannon_entropy(finishing_gaps),
        'finishing_times': finishing_times
    }
    return stat_measures