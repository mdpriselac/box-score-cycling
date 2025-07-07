"""
Engineered Metrics for Race Analysis

This module provides engineered metrics that capture specific race characteristics
like group finishes, time gap evenness, and clumpiness of results.
"""

import numpy as np
from typing import List, Dict, Tuple
from collections import Counter


def identify_groups(time_gaps: List[float], threshold_seconds: float = 1.0) -> Dict[str, any]:
    """
    Identify groups of riders finishing together.
    
    Riders are considered in the same group if they finish within threshold_seconds
    of each other.
    
    Args:
        time_gaps: List of time gaps from winner (sorted by finishing position)
        threshold_seconds: Maximum gap between riders to be in same group
        
    Returns:
        Dictionary containing group information
    """
    if not time_gaps:
        return {
            'groups': [],
            'group_sizes': [],
            'group_positions': [],
            'total_groups': 0,
            'riders_in_groups': 0,
            'largest_group_size': 0,
            'largest_group_position': 0
        }
    
    groups = []
    current_group = [0]  # Start with winner
    current_group_start_pos = 1
    
    for i in range(1, len(time_gaps)):
        gap_diff = time_gaps[i] - time_gaps[i-1]
        
        if gap_diff <= threshold_seconds:
            current_group.append(i)
        else:
            if len(current_group) > 1:  # Only count as group if 2+ riders
                groups.append({
                    'size': len(current_group),
                    'start_position': current_group_start_pos,
                    'end_position': current_group_start_pos + len(current_group) - 1,
                    'positions': current_group.copy()
                })
            current_group = [i]
            current_group_start_pos = i + 1
    
    # Don't forget the last group
    if len(current_group) > 1:
        groups.append({
            'size': len(current_group),
            'start_position': current_group_start_pos,
            'end_position': current_group_start_pos + len(current_group) - 1,
            'positions': current_group.copy()
        })
    
    # Calculate summary statistics
    group_sizes = [g['size'] for g in groups]
    riders_in_groups = sum(group_sizes)
    
    # Find largest group
    largest_group_size = max(group_sizes) if group_sizes else 0
    largest_group_idx = group_sizes.index(largest_group_size) if group_sizes else -1
    largest_group_position = groups[largest_group_idx]['start_position'] if largest_group_idx >= 0 else 0
    
    return {
        'groups': groups,
        'group_sizes': group_sizes,
        'group_positions': [g['start_position'] for g in groups],
        'total_groups': len(groups),
        'riders_in_groups': riders_in_groups,
        'largest_group_size': largest_group_size,
        'largest_group_position': largest_group_position,
        'proportion_in_groups': riders_in_groups / len(time_gaps) if time_gaps else 0
    }


def calculate_biggest_group_metric(group_info: Dict, total_riders: int) -> float:
    """
    Calculate a metric representing the size and influence of the biggest group.
    
    Returns a score between 0 and 1:
    - 1 means the entire race finishes in one group with the winner
    - 0 means no significant group or the largest group had no race influence
    
    Args:
        group_info: Dictionary from identify_groups()
        total_riders: Total number of riders in the race
        
    Returns:
        Score between 0 and 1
    """
    if group_info['largest_group_size'] == 0:
        return 0.0
    
    # Size component: proportion of field in largest group
    size_score = group_info['largest_group_size'] / total_riders
    
    # Position component: how close to the front
    position = group_info['largest_group_position']
    position_percentile = (position - 1) / total_riders if total_riders > 0 else 0
    
    # Calculate influence score with emphasis on front groups
    if position_percentile <= 0.01:  # Group contains winner
        influence_score = 1.0
    elif position_percentile <= 0.1:  # Top 10%
        influence_score = 1.0 - (position_percentile / 0.1) * 0.3  # 1.0 to 0.7
    elif position_percentile <= 0.3:  # Top 30%
        influence_score = 0.7 - ((position_percentile - 0.1) / 0.2) * 0.5  # 0.7 to 0.2
    else:
        influence_score = 0.2 * (1 - position_percentile)  # Fade to 0
    
    # Combine with geometric mean, weighted toward influence
    final_score = (size_score ** 0.3) * (influence_score ** 0.7)
    
    return float(final_score)


def calculate_time_gap_evenness(time_gaps: List[float]) -> float:
    """
    Calculate how evenly distributed the time gaps are.
    
    Perfect evenness (1.0) means equal spacing between each rider.
    Low evenness means bunching and large gaps.
    
    Args:
        time_gaps: List of time gaps from winner
        
    Returns:
        Evenness score between 0 and 1
    """
    if len(time_gaps) < 2:
        return 0.0
    
    # Calculate gaps between consecutive riders
    consecutive_gaps = []
    for i in range(1, len(time_gaps)):
        gap_diff = time_gaps[i] - time_gaps[i-1]
        consecutive_gaps.append(gap_diff)
    
    if not consecutive_gaps or np.mean(consecutive_gaps) == 0:
        return 0.0
    
    # Calculate coefficient of variation
    cv = np.std(consecutive_gaps) / np.mean(consecutive_gaps)
    
    # Convert to evenness score (high CV = low evenness)
    evenness = 1 / (1 + cv)
    
    # Apply penalty for zero gaps (indicates groups)
    zero_count = sum(1 for gap in consecutive_gaps if gap < 0.1)
    zero_penalty = zero_count / len(consecutive_gaps) * 0.5
    
    final_score = evenness * (1 - zero_penalty)
    
    return float(final_score)


def calculate_clumpiness_score(
    group_info: Dict,
    total_riders: int,
    time_gaps: List[float]
) -> float:
    """
    Calculate a clumpiness score for the race.
    
    High clumpiness means riders finish in distinct groups (not solo, not one big group).
    Ideal clumpy race has 5-15 riders per group and multiple groups.
    
    Args:
        group_info: Dictionary from identify_groups()
        total_riders: Total number of riders
        time_gaps: List of time gaps
        
    Returns:
        Clumpiness score between 0 and 1
    """
    if group_info['total_groups'] == 0:
        return 0.0
    
    # Component 1: Number of groups (ideal 5-15 groups)
    group_count = group_info['total_groups']
    if group_count <= 5:
        group_score = group_count / 5
    elif group_count <= 15:
        group_score = 1.0
    else:
        group_score = max(0, 1 - (group_count - 15) / 15)
    
    # Component 2: Proportion of riders in groups
    proportion_score = group_info['proportion_in_groups']
    
    # Component 3: Average group size (ideal 5-15 riders)
    avg_group_size = np.mean(group_info['group_sizes']) if group_info['group_sizes'] else 0
    
    if avg_group_size < 2:
        size_score = 0.0
    elif avg_group_size < 5:
        size_score = (avg_group_size - 2) / 3
    elif avg_group_size <= 15:
        size_score = 1.0
    elif avg_group_size <= 20:
        size_score = 1 - (avg_group_size - 15) / 5
    else:
        size_score = 0.0
    
    # Component 4: Distribution of groups across the race
    if len(time_gaps) > 0 and group_info['group_positions']:
        # Check how spread out the groups are
        group_positions_normalized = [p / len(time_gaps) for p in group_info['group_positions']]
        position_variance = np.var(group_positions_normalized)
        # Higher variance = better spread
        spread_score = min(1.0, position_variance * 10)
    else:
        spread_score = 0.0
    
    # Combine components
    clumpiness = (group_score * 0.25 + 
                  proportion_score * 0.25 + 
                  size_score * 0.35 + 
                  spread_score * 0.15)
    
    return float(clumpiness)


def calculate_selection_metric(time_gaps: List[float], winning_time: float) -> float:
    """
    Calculate how selective/difficult the race was.
    
    High selection means large time gaps and high abandon rate.
    
    Args:
        time_gaps: List of time gaps from winner
        winning_time: Winner's time in seconds
        
    Returns:
        Selection metric between 0 and 1
    """
    if not time_gaps or winning_time == 0:
        return 0.0
    
    # Component 1: Relative spread of finish times
    last_gap = time_gaps[-1] if time_gaps else 0
    relative_spread = last_gap / winning_time
    spread_score = min(1.0, relative_spread / 0.1)  # 10% spread = max score
    
    # Component 2: Gap progression (how quickly gaps grow)
    if len(time_gaps) >= 10:
        # Compare gaps at different percentiles
        p10_gap = time_gaps[int(len(time_gaps) * 0.1)]
        p50_gap = time_gaps[int(len(time_gaps) * 0.5)]
        p90_gap = time_gaps[int(len(time_gaps) * 0.9)]
        
        if p90_gap > 0:
            early_progression = p10_gap / p90_gap if p90_gap > 0 else 0
            mid_progression = p50_gap / p90_gap if p90_gap > 0 else 0
            
            # Steeper progression = higher selection
            progression_score = 1 - (early_progression * 0.5 + mid_progression * 0.5)
        else:
            progression_score = 0.0
    else:
        progression_score = 0.0
    
    # Combine components
    selection = spread_score * 0.6 + progression_score * 0.4
    
    return float(selection)