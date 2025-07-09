#!/usr/bin/env python3
"""
Compare basic vs enhanced experience features for a small sample of rider results.
"""

import sqlite3
import pandas as pd
import json
import numpy as np
from typing import Dict, List
from datetime import datetime

from rider_experience_features import RiderExperienceFeatures
from enhanced_rider_experience import EnhancedRiderExperience


def get_sample_rider_results(db_path: str, n_samples: int = 5) -> List[Dict]:
    """Get a random sample of rider results for testing."""
    conn = sqlite3.connect(db_path)
    
    # Get random rider results with sufficient history
    query = """
    WITH rider_counts AS (
        SELECT rider_id, COUNT(*) as total_results
        FROM rider_results rr
        JOIN competitions c ON rr.competition_id = c.id
        WHERE c.date <= '2020-12-31'
        GROUP BY rider_id
        HAVING COUNT(*) >= 20
    ),
    sample_results AS (
        SELECT 
            rr.rider_id,
            rr.competition_id,
            rr.id as result_id,
            c.date as competition_date,
            c.name as competition_name,
            c.competition_type,
            r.name as race_name,
            r.category as race_category,
            rr.place,
            rr.rider_age,
            rc.total_results
        FROM rider_results rr
        JOIN competitions c ON rr.competition_id = c.id
        JOIN races r ON c.race_id = r.id
        JOIN rider_counts rc ON rr.rider_id = rc.rider_id
        WHERE c.date BETWEEN '2015-01-01' AND '2020-12-31'
        ORDER BY RANDOM()
        LIMIT ?
    )
    SELECT * FROM sample_results
    """
    
    df = pd.read_sql_query(query, conn, params=[n_samples])
    conn.close()
    
    return df.to_dict('records')


def get_rider_history_with_features(db_path: str, rider_id: int, cutoff_date: str) -> pd.DataFrame:
    """Get complete rider history with race features up to cutoff date."""
    conn = sqlite3.connect(db_path)
    
    # Get rider history with race features and race kind features
    query = """
    SELECT 
        rr.id as result_id,
        rr.rider_id,
        rr.competition_id,
        c.date as competition_date,
        c.name as competition_name,
        c.competition_type,
        r.name as race_name,
        r.category as race_category,
        r.year as race_year,
        rr.place,
        rr.time_gap,
        rr.percentile,
        rr.rider_age
    FROM rider_results rr
    JOIN competitions c ON rr.competition_id = c.id
    JOIN races r ON c.race_id = r.id
    WHERE rr.rider_id = ?
    AND c.date <= ?
    ORDER BY c.date
    """
    
    # Get basic history
    history_df = pd.read_sql_query(query, conn, params=[rider_id, cutoff_date])
    
    if history_df.empty:
        conn.close()
        return history_df
    
    # Add UCI points calculation
    import sys
    import os
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, parent_dir)
    from database.uci_points import get_actual_uci_place_points, get_top_tier_based_points
    
    uci_actual = []
    uci_proportional = []
    
    for _, row in history_df.iterrows():
        try:
            actual = get_actual_uci_place_points(
                row['place'], row['competition_type'], 
                row['race_category'], 0  # Using 0 for fc_race_id as fallback
            )
            proportional = get_top_tier_based_points(
                row['place'], row['competition_type'], 
                row['race_category'], 0
            )
        except:
            actual = proportional = 0
        
        uci_actual.append(actual)
        uci_proportional.append(proportional)
    
    history_df['uci_points_actual'] = uci_actual
    history_df['uci_points_proportional'] = uci_proportional
    
    # Get race features for GC competitions
    gc_competitions = history_df[history_df['competition_type'] == 'gc']['competition_id'].tolist()
    
    race_features_70 = {}
    if gc_competitions:
        placeholders = ','.join('?' * len(gc_competitions))
        rf70_query = f"""
        SELECT competition_id, "clumpiness_score", "biggest_group_metric", "avg_group_size",
               "selection_metric", "gini_coefficient", "std_group_size", "proportion_in_groups",
               "time_gap_evenness_metric", "total_groups", "std_deviation_normalized",
               "total_race_duration", "50th_percentile_gap", "variance_absolute", "skewness_normalized"
        FROM race_features_70
        WHERE competition_id IN ({placeholders})
        """
        
        rf70_df = pd.read_sql_query(rf70_query, conn, params=gc_competitions)
        for _, row in rf70_df.iterrows():
            race_features_70[row['competition_id']] = row.to_dict()
    
    # Get race features for stage/one-day competitions
    stage_one_day_competitions = history_df[
        history_df['competition_type'].isin(['stage', 'one_day'])
    ]['competition_id'].tolist()
    
    race_features_40 = {}
    if stage_one_day_competitions:
        placeholders = ','.join('?' * len(stage_one_day_competitions))
        rf40_query = f"""
        SELECT competition_id, "clumpiness_score", "biggest_group_metric", "avg_group_size",
               "selection_metric", "gini_coefficient", "std_group_size", "proportion_in_groups",
               "time_gap_evenness_metric", "total_groups", "std_deviation_normalized",
               "total_race_duration", "50th_percentile_gap", "variance_absolute", "skewness_normalized"
        FROM race_features_40
        WHERE competition_id IN ({placeholders})
        """
        
        rf40_df = pd.read_sql_query(rf40_query, conn, params=stage_one_day_competitions)
        for _, row in rf40_df.iterrows():
            race_features_40[row['competition_id']] = row.to_dict()
    
    # Get race kind features
    all_competitions = history_df['competition_id'].tolist()
    race_kind_features = {}
    
    if all_competitions:
        placeholders = ','.join('?' * len(all_competitions))
        rkf_query = f"""
        SELECT competition_id, "cluster_label", "local_density", "boundary_distance"
        FROM race_kind_features
        WHERE competition_id IN ({placeholders})
        """
        
        rkf_df = pd.read_sql_query(rkf_query, conn, params=all_competitions)
        for _, row in rkf_df.iterrows():
            race_kind_features[row['competition_id']] = row.to_dict()
    
    conn.close()
    
    # Add race features to history
    for col in ['clumpiness_score', 'biggest_group_metric', 'avg_group_size', 'selection_metric', 
                'gini_coefficient', 'std_group_size', 'proportion_in_groups', 'time_gap_evenness_metric',
                'total_groups', 'std_deviation_normalized', 'total_race_duration', '50th_percentile_gap',
                'variance_absolute', 'skewness_normalized']:
        history_df[f'rf_{col}'] = history_df.apply(
            lambda row: race_features_70.get(row['competition_id'], race_features_40.get(row['competition_id'], {})).get(col, 0),
            axis=1
        )
    
    # Add race kind features
    for col in ['cluster_label', 'local_density', 'boundary_distance']:
        history_df[f'rkf_{col}'] = history_df.apply(
            lambda row: race_kind_features.get(row['competition_id'], {}).get(col, 0),
            axis=1
        )
    
    return history_df


def compare_experience_features():
    """Compare basic vs enhanced experience features."""
    db_path = "~/Documents/Cycling Project/cycling_project/webscrape_tools/database/database/cycling_races.db"
    
    print("=" * 80)
    print("RIDER EXPERIENCE FEATURES COMPARISON")
    print("=" * 80)
    
    # Get sample rider results
    print("Getting sample rider results...")
    sample_results = get_sample_rider_results(db_path, n_samples=5)
    
    print(f"Selected {len(sample_results)} rider results for comparison:")
    for i, result in enumerate(sample_results, 1):
        print(f"  {i}. Rider {result['rider_id']} in {result['competition_name']} "
              f"({result['competition_date']}) - Place {result['place']}")
    
    # Initialize feature calculators
    basic_calculator = RiderExperienceFeatures()
    enhanced_calculator = EnhancedRiderExperience()
    
    comparison_results = {
        'metadata': {
            'generated_at': datetime.now().isoformat(),
            'n_samples': len(sample_results),
            'description': 'Comparison of basic vs enhanced rider experience features'
        },
        'sample_results': sample_results,
        'feature_comparisons': []
    }
    
    print("\n" + "=" * 80)
    print("FEATURE COMPARISON RESULTS")
    print("=" * 80)
    
    for i, result in enumerate(sample_results, 1):
        rider_id = result['rider_id']
        cutoff_date = result['competition_date']
        
        print(f"\n{'-' * 60}")
        print(f"SAMPLE {i}: Rider {rider_id} - {result['competition_name']}")
        print(f"Date: {cutoff_date}, Place: {result['place']}")
        print(f"Total career results: {result['total_results']}")
        print(f"{'-' * 60}")
        
        # Get rider history up to this race
        rider_history = get_rider_history_with_features(db_path, rider_id, cutoff_date)
        
        if rider_history.empty:
            print("No history found for this rider")
            continue
        
        print(f"Prior races in history: {len(rider_history)}")
        
        try:
            # Calculate basic experience features
            basic_features_df = basic_calculator.add_experience_features(rider_history)
            
            # Get the features for the last race (the one we're predicting)
            if len(basic_features_df) > 0:
                last_race_basic = basic_features_df.iloc[-1]
                basic_features = {col: last_race_basic[col] for col in basic_features_df.columns 
                                if col.startswith(('total_prior', 'prior_', 'rider_age_at_race'))}
            else:
                basic_features = {}
            
            print("\nBASIC EXPERIENCE FEATURES:")
            for feature, value in basic_features.items():
                print(f"  {feature}: {value}")
            
        except Exception as e:
            print(f"Error calculating basic features: {e}")
            basic_features = {}
        
        try:
            # Calculate enhanced experience features
            enhanced_features_df = enhanced_calculator.add_enhanced_experience_features(rider_history)
            
            # Get the features for the last race
            if len(enhanced_features_df) > 0:
                last_race_enhanced = enhanced_features_df.iloc[-1]
                enhanced_features = {col: last_race_enhanced[col] for col in enhanced_features_df.columns 
                                   if not col.startswith(('result_id', 'rider_id', 'competition_id', 'competition_name', 
                                                        'competition_type', 'race_name', 'race_category', 'race_year',
                                                        'competition_date', 'place', 'time_gap', 'percentile', 'rider_age',
                                                        'uci_points', 'rf_', 'rkf_'))}
            else:
                enhanced_features = {}
            
            print(f"\nENHANCED EXPERIENCE FEATURES ({len(enhanced_features)} features):")
            for feature, value in enhanced_features.items():
                if isinstance(value, float):
                    print(f"  {feature}: {value:.4f}")
                else:
                    print(f"  {feature}: {value}")
            
        except Exception as e:
            print(f"Error calculating enhanced features: {e}")
            enhanced_features = {}
        
        # Store comparison
        comparison_data = {
            'sample_index': i,
            'rider_id': rider_id,
            'competition_info': {
                'competition_id': result['competition_id'],
                'competition_name': result['competition_name'],
                'competition_date': result['competition_date'],
                'competition_type': result['competition_type'],
                'place': result['place']
            },
            'history_size': len(rider_history),
            'basic_features': {k: float(v) if isinstance(v, (int, float, np.number)) else v 
                             for k, v in basic_features.items()},
            'enhanced_features': {k: float(v) if isinstance(v, (int, float, np.number)) else v 
                                for k, v in enhanced_features.items()},
            'feature_count_comparison': {
                'basic_count': len(basic_features),
                'enhanced_count': len(enhanced_features),
                'enhancement_ratio': len(enhanced_features) / len(basic_features) if basic_features else 0
            }
        }
        
        comparison_results['feature_comparisons'].append(comparison_data)
    
    # Save results to JSON
    output_file = "test_feature_comp.json"
    with open(output_file, 'w') as f:
        json.dump(comparison_results, f, indent=2, default=str)
    
    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print(f"{'=' * 80}")
    print(f"Comparison results saved to: {output_file}")
    print(f"Samples processed: {len(comparison_results['feature_comparisons'])}")
    
    if comparison_results['feature_comparisons']:
        basic_count = comparison_results['feature_comparisons'][0]['feature_count_comparison']['basic_count']
        enhanced_count = comparison_results['feature_comparisons'][0]['feature_count_comparison']['enhanced_count']
        
        print(f"Basic feature count: {basic_count}")
        print(f"Enhanced feature count: {enhanced_count}")
        print(f"Enhancement ratio: {enhanced_count / basic_count:.1f}x more features")
    
    print("\nKey improvements in enhanced features:")
    print("- Points-based performance metrics instead of just race counts")
    print("- Success rates and performance quality measures") 
    print("- Rider-race interaction profiles")
    print("- Performance trends and consistency metrics")
    print("- Recent form analysis")


if __name__ == "__main__":
    compare_experience_features()