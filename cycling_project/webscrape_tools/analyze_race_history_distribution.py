#!/usr/bin/env python3
"""
Analyze the distribution of prior race counts for each race type to help optimize
minimum race requirements for better quality data.
"""

import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path

def analyze_race_history_distribution():
    """Analyze prior race count distributions for each race type."""
    
    db_path = "database/database/cycling_races.db"
    
    # Race type configurations to analyze
    race_types = {
        'gc': {
            'competition_types': ['gc'],
            'description': 'GC races only'
        },
        'stage': {
            'competition_types': ['stage'],
            'description': 'Stage races only'
        },
        'one_day': {
            'competition_types': ['one_day'],
            'description': 'One day races only'
        },
        'stage_one_day': {
            'competition_types': ['stage', 'one_day'],
            'description': 'Stage + One day races'
        },
        'all': {
            'competition_types': ['gc', 'stage', 'one_day'],
            'description': 'All race types'
        }
    }
    
    print("Analyzing Prior Race Count Distributions")
    print("=" * 80)
    print("This will help determine optimal minimum race requirements for each type.")
    print("Higher minimums = better data quality but fewer eligible results\n")
    
    with sqlite3.connect(db_path) as conn:
        
        for race_type, config in race_types.items():
            print(f"\n{race_type.upper()} RACE TYPE ({config['description']}):")
            print("-" * 60)
            
            competition_types = config['competition_types']
            
            # Build the competition type filter
            if len(competition_types) == 1:
                type_filter = f"= '{competition_types[0]}'"
            else:
                type_list = "', '".join(competition_types)
                type_filter = f"IN ('{type_list}')"
            
            # Query to get all prior race counts for this race type
            query = f"""
            WITH race_type_results AS (
                SELECT 
                    rr.id as rider_result_id,
                    rr.rider_id,
                    c.date as competition_date,
                    c.competition_type,
                    -- Use window function to count prior races
                    ROW_NUMBER() OVER (
                        PARTITION BY rr.rider_id 
                        ORDER BY c.date
                    ) - 1 as prior_races_of_type
                FROM rider_results rr
                JOIN competitions c ON rr.competition_id = c.id
                WHERE c.date <= '2025-01-01'
                AND c.competition_type {type_filter}
                ORDER BY rr.rider_id, c.date
            )
            SELECT prior_races_of_type
            FROM race_type_results
            WHERE prior_races_of_type > 0  -- Exclude first race (0 prior)
            """
            
            # Execute query and get data
            df = pd.read_sql_query(query, conn)
            
            if df.empty:
                print("  No data found!")
                continue
            
            prior_counts = df['prior_races_of_type'].values
            
            # Calculate statistics
            print(f"Total rider results: {len(prior_counts):,}")
            print(f"Mean prior races: {np.mean(prior_counts):.1f}")
            print(f"Median prior races: {np.median(prior_counts):.1f}")
            print(f"Std deviation: {np.std(prior_counts):.1f}")
            print(f"Min: {np.min(prior_counts)}, Max: {np.max(prior_counts)}")
            
            # Calculate percentiles
            percentiles = [10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 99]
            percentile_values = np.percentile(prior_counts, percentiles)
            
            print(f"\nPercentile Distribution:")
            print(f"{'Percentile':<12} {'Prior Races':<12} {'Eligible Results':<15} {'% of Total':<12}")
            print("-" * 55)
            
            total_results = len(prior_counts)
            
            for pct, val in zip(percentiles, percentile_values):
                eligible_count = np.sum(prior_counts >= val)
                pct_of_total = (eligible_count / total_results) * 100
                print(f"{pct}th{'':<8} {val:<12.0f} {eligible_count:<15,} {pct_of_total:<12.1f}%")
            
            # Show some recommended minimum thresholds
            print(f"\nRecommended Minimum Thresholds:")
            print(f"Conservative (90% coverage): {percentile_values[0]:.0f} prior races")
            print(f"Moderate (70% coverage):     {percentile_values[2]:.0f} prior races") 
            print(f"Aggressive (50% coverage):   {percentile_values[4]:.0f} prior races")
            print(f"Very Aggressive (20% coverage): {percentile_values[7]:.0f} prior races")
            
            # Current pipeline settings for comparison
            current_minimums = {
                'gc': 20,
                'stage': 100, 
                'one_day': 30,
                'stage_one_day': 30,
                'all': 150
            }
            
            if race_type in current_minimums:
                current_min = current_minimums[race_type]
                current_eligible = np.sum(prior_counts >= current_min)
                current_pct = (current_eligible / total_results) * 100
                current_percentile = (np.sum(prior_counts < current_min) / total_results) * 100
                
                print(f"\nCurrent Pipeline Setting: {current_min} prior races")
                print(f"  Eligible results: {current_eligible:,} ({current_pct:.1f}% of total)")
                print(f"  Excludes bottom {current_percentile:.1f}% of results")
    
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print("\nInterpretation Guide:")
    print("• Higher minimums = Better data quality (more historical context)")
    print("• Lower minimums = More training data (larger sample size)")
    print("• Consider the trade-off between quality and quantity")
    print("• Look for 'sweet spots' where you get good coverage without too much noise")
    print("\nRecommendation:")
    print("• Start with moderate settings (70% coverage)")
    print("• Adjust based on model performance and data needs")

if __name__ == "__main__":
    analyze_race_history_distribution()