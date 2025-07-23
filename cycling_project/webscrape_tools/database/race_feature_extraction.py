"""
Race Feature Extraction Module

This module provides functionality to extract and calculate race features from competition data.
It includes functions to:
1. Trim race results based on percentile cutoffs
2. Extract statistical measures from finishing time distributions
3. Calculate engineered metrics for race characterization
"""

import numpy as np
import sqlite3
import pandas as pd
from typing import Dict, List, Tuple, Optional, Union
from datetime import datetime

# Import our local modules
from statistical_measures import (
    calculate_gini_coefficient,
    calculate_shannon_entropy,
    calculate_variance_and_std,
    calculate_skewness,
    calculate_kurtosis,
    calculate_percentile_gaps
)

from engineered_metrics import (
    identify_groups,
    calculate_biggest_group_metric,
    calculate_time_gap_evenness,
    calculate_clumpiness_score,
    calculate_selection_metric
)


def trim_race_results_by_percentile(
    competition_id: int,
    percentile: float,
    db_path: str
) -> Tuple[List[float], List[float], int, float]:
    """
    Trim race results to include only the top N percentile of finishers.
    
    Args:
        competition_id: The ID of the competition to analyze
        percentile: The percentile cutoff (e.g., 0.5 for top 50%)
        db_path: Path to the SQLite database
        
    Returns:
        Tuple containing:
        - List of finishing times (in seconds) for included riders
        - List of time gaps (in seconds) from winner for included riders
        - Total number of finishers (before trimming)
        - Winner's time in seconds
    """
    if not 0 < percentile <= 1:
        raise ValueError("Percentile must be between 0 and 1")
    
    conn = sqlite3.connect(db_path)
    
    # Get competition winning time
    winning_time_query = """
    SELECT winning_time
    FROM competitions
    WHERE id = ?
    """
    winning_time_result = pd.read_sql_query(winning_time_query, conn, params=(competition_id,))
    
    if winning_time_result.empty:
        conn.close()
        raise ValueError(f"Competition {competition_id} not found")
    
    winning_time = winning_time_result.iloc[0, 0]
    
    if winning_time is None:
        conn.close()
        raise ValueError(f"No winning time found for competition {competition_id}")
    
    # Get all results for the competition (only non-NULL time_gaps)
    results_query = """
    SELECT place, time_gap
    FROM rider_results
    WHERE competition_id = ? AND time_gap IS NOT NULL
    ORDER BY place
    """
    results_df = pd.read_sql_query(results_query, conn, params=(competition_id,))
    conn.close()
    
    total_finishers = len(results_df)
    cutoff_position = int(total_finishers * percentile)
    
    # Trim to top N percentile
    trimmed_results = results_df.iloc[:cutoff_position]
    
    # Calculate finishing times
    finishing_times = []
    time_gaps = []
    
    for _, row in trimmed_results.iterrows():
        gap = row['time_gap']  # Now guaranteed to be non-NULL
        finishing_time = winning_time + gap
        finishing_times.append(finishing_time)
        time_gaps.append(gap)
    
    return finishing_times, time_gaps, total_finishers, winning_time


def calculate_statistical_features(
    finishing_times: List[float],
    time_gaps: List[float],
    winning_time: float
) -> Dict[str, float]:
    """
    Calculate all statistical features for a race.
    
    Args:
        finishing_times: List of finishing times in seconds
        time_gaps: List of time gaps from winner in seconds
        winning_time: Winner's time in seconds
        
    Returns:
        Dictionary containing all statistical features
    """
    features = {}
    
    # Variance and standard deviation (absolute and normalized)
    var_abs, std_abs = calculate_variance_and_std(time_gaps)
    var_norm, std_norm = calculate_variance_and_std(finishing_times, normalize_by=winning_time)
    
    features['variance_absolute'] = var_abs
    features['variance_normalized'] = var_norm
    features['std_deviation_absolute'] = std_abs
    features['std_deviation_normalized'] = std_norm
    
    # Skewness (absolute and normalized)
    features['skewness_absolute'] = calculate_skewness(time_gaps)
    features['skewness_normalized'] = calculate_skewness(finishing_times, normalize_by=winning_time)
    
    # Kurtosis (absolute and normalized)
    features['kurtosis_absolute'] = calculate_kurtosis(time_gaps)
    features['kurtosis_normalized'] = calculate_kurtosis(finishing_times, normalize_by=winning_time)
    
    # Gini coefficient
    features['gini_coefficient'] = calculate_gini_coefficient(time_gaps)
    
    # Shannon entropy
    entropy_abs, entropy_norm = calculate_shannon_entropy(time_gaps)
    features['shannon_entropy_absolute'] = entropy_abs
    features['shannon_entropy_normalized'] = entropy_norm
    
    # Percentile gaps
    percentile_gaps = calculate_percentile_gaps(time_gaps)
    features.update(percentile_gaps)
    
    return features


def calculate_engineered_features(
    finishing_times: List[float],
    time_gaps: List[float],
    winning_time: float,
    total_finishers: int,
    abandon_ratio: float
) -> Dict[str, float]:
    """
    Calculate all engineered features for a race.
    
    Args:
        finishing_times: List of finishing times in seconds
        time_gaps: List of time gaps from winner in seconds
        winning_time: Winner's time in seconds
        total_finishers: Total number of finishers before trimming
        abandon_ratio: Ratio of non-finishers to starters
        
    Returns:
        Dictionary containing all engineered features
    """
    features = {}
    
    # Identify groups
    group_info = identify_groups(time_gaps)
    
    # Group-based features
    features['total_groups'] = group_info['total_groups']
    features['riders_in_groups'] = group_info['riders_in_groups']
    features['proportion_in_groups'] = group_info['proportion_in_groups']
    features['largest_group_size'] = group_info['largest_group_size']
    features['largest_group_position'] = group_info['largest_group_position']
    
    if group_info['group_sizes']:
        features['avg_group_size'] = float(np.mean(group_info['group_sizes']))
        features['std_group_size'] = float(np.std(group_info['group_sizes']))
    else:
        features['avg_group_size'] = 0.0
        features['std_group_size'] = 0.0
    
    # Calculate metrics
    features['biggest_group_metric'] = calculate_biggest_group_metric(
        group_info, len(time_gaps)
    )
    features['time_gap_evenness_metric'] = calculate_time_gap_evenness(time_gaps)
    features['clumpiness_score'] = calculate_clumpiness_score(
        group_info, len(time_gaps), time_gaps
    )
    features['selection_metric'] = calculate_selection_metric(time_gaps, winning_time)
    
    return features


def extract_race_features(
    competition_id: int,
    percentile: float,
    db_path: str
) -> Dict[str, Union[float, int, str]]:
    """
    Extract all race features for a given competition and percentile.
    
    Args:
        competition_id: The ID of the competition
        percentile: The percentile cutoff for analysis
        db_path: Path to the SQLite database
        
    Returns:
        Dictionary containing all extracted features
    """
    # Get trimmed race data
    finishing_times, time_gaps, total_finishers, winning_time = trim_race_results_by_percentile(
        competition_id, percentile, db_path
    )
    
    if len(finishing_times) < 10:
        raise ValueError(f"Too few finishers ({len(finishing_times)}) after trimming to {percentile:.0%}")
    
    # Get competition metadata
    conn = sqlite3.connect(db_path)
    metadata_query = """
    SELECT c.id, c.name, c.competition_type, c.date, c.winning_time,
           r.id as race_id, r.name as race_name, r.category, r.year
    FROM competitions c
    JOIN races r ON c.race_id = r.id
    WHERE c.id = ?
    """
    metadata = pd.read_sql_query(metadata_query, conn, params=(competition_id,)).iloc[0]
    conn.close()
    
    # Calculate basic race statistics
    included_finishers = len(finishing_times)
    abandon_ratio = 1 - (included_finishers / total_finishers)
    
    # Base features
    features = {
        'competition_id': competition_id,
        'competition_name': metadata['name'],
        'competition_type': metadata['competition_type'],
        'race_id': metadata['race_id'],
        'race_name': metadata['race_name'],
        'race_category': metadata['category'],
        'race_year': metadata['year'],
        'race_date': metadata['date'],
        'percentile_analyzed': percentile,
        'total_finishers': total_finishers,
        'included_finishers': included_finishers,
        'abandon_ratio': abandon_ratio,
        'winning_time': winning_time,
        'total_race_duration': finishing_times[-1] - finishing_times[0] if len(finishing_times) > 1 else 0
    }
    
    # Calculate statistical features
    stat_features = calculate_statistical_features(finishing_times, time_gaps, winning_time)
    features.update(stat_features)
    
    # Calculate engineered features
    eng_features = calculate_engineered_features(
        finishing_times, time_gaps, winning_time, total_finishers, abandon_ratio
    )
    features.update(eng_features)
    
    return features


def extract_features_for_percentile_range(
    competition_id: int,
    db_path: str,
    start_percentile: float = 0.1,
    end_percentile: float = 1.0,
    step: float = 0.05
) -> pd.DataFrame:
    """
    Extract race features across a range of percentiles.
    
    Args:
        competition_id: The ID of the competition
        db_path: Path to the SQLite database
        start_percentile: Starting percentile (default 0.1 for top 10%)
        end_percentile: Ending percentile (default 1.0 for full field)
        step: Step size between percentiles (default 0.05)
        
    Returns:
        DataFrame with features for each percentile
    """
    results = []
    
    percentiles = np.arange(start_percentile, end_percentile + step, step)
    percentiles = np.clip(percentiles, 0, 1)  # Ensure we don't exceed 1.0
    
    for pct in percentiles:
        try:
            features = extract_race_features(competition_id, pct, db_path)
            results.append(features)
        except ValueError as e:
            print(f"Skipping percentile {pct:.0%} for competition {competition_id}: {e}")
            continue
    
    if not results:
        return pd.DataFrame()
    
    return pd.DataFrame(results)


def batch_extract_features(
    competition_ids: List[int],
    percentile: float,
    db_path: str
) -> pd.DataFrame:
    """
    Extract features for multiple competitions at a specific percentile.
    
    Args:
        competition_ids: List of competition IDs
        percentile: The percentile cutoff for analysis
        db_path: Path to the SQLite database
        
    Returns:
        DataFrame with features for all competitions
    """
    results = []
    
    for comp_id in competition_ids:
        try:
            features = extract_race_features(comp_id, percentile, db_path)
            results.append(features)
        except Exception as e:
            print(f"Error processing competition {comp_id}: {e}")
            continue
    
    if not results:
        return pd.DataFrame()
    
    return pd.DataFrame(results)