#!/usr/bin/env python3
"""
Simple comparison of basic vs enhanced experience features for a small sample of rider results.
"""

import sqlite3
import pandas as pd
import json
import numpy as np
from typing import Dict, List
from datetime import datetime
import sys
import os

# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from rider_performance.rider_experience_features import RiderExperienceFeatures
from rider_performance.enhanced_rider_experience import EnhancedRiderExperience
from database.uci_points import get_actual_uci_place_points, get_top_tier_based_points


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
        HAVING COUNT(*) >= 30
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


def get_basic_rider_history(db_path: str, rider_id: int, cutoff_date: str) -> pd.DataFrame:
    """Get basic rider history for experience calculation."""
    conn = sqlite3.connect(db_path)
    
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
    
    history_df = pd.read_sql_query(query, conn, params=[rider_id, cutoff_date])
    conn.close()
    
    if history_df.empty:
        return history_df
    
    # Add UCI points calculation
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
    
    # Add dummy race features for enhanced calculator (all zeros)
    dummy_race_features = [
        'clumpiness_score', 'biggest_group_metric', 'avg_group_size', 'selection_metric',
        'gini_coefficient', 'std_group_size', 'proportion_in_groups', 'time_gap_evenness_metric',
        'total_groups', 'std_deviation_normalized', 'total_race_duration', '50th_percentile_gap',
        'variance_absolute', 'skewness_normalized'
    ]
    
    dummy_race_kind_features = ['cluster_label', 'local_density', 'boundary_distance']
    
    for feature in dummy_race_features:
        history_df[f'rf_{feature}'] = 0
    
    for feature in dummy_race_kind_features:
        history_df[f'rkf_{feature}'] = 0
    
    return history_df


def convert_numpy_to_python(obj):
    """Convert numpy types to Python native types."""
    if isinstance(obj, dict):
        return {k: convert_numpy_to_python(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_to_python(item) for item in obj]
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif pd.isna(obj):
        return None
    else:
        return obj


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
        rider_history = get_basic_rider_history(db_path, rider_id, cutoff_date)
        
        if rider_history.empty:
            print("No history found for this rider")
            continue
        
        print(f"Prior races in history: {len(rider_history)}")
        
        basic_features = {}
        enhanced_features = {}
        
        try:
            # Calculate basic experience features
            basic_features_df = basic_calculator.add_experience_features(rider_history)
            
            # Get the features for the last race (the one we're predicting)
            if len(basic_features_df) > 0:
                last_race_basic = basic_features_df.iloc[-1]
                basic_features = {col: last_race_basic[col] for col in basic_features_df.columns 
                                if col.startswith(('total_prior', 'prior_', 'rider_age_at_race'))}
            
            print(f"\nBASIC EXPERIENCE FEATURES ({len(basic_features)} features):")
            for feature, value in sorted(basic_features.items()):
                if isinstance(value, float):
                    print(f"  {feature}: {value:.4f}")
                else:
                    print(f"  {feature}: {value}")
            
        except Exception as e:
            print(f"Error calculating basic features: {e}")
        
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
                                                        'uci_points', 'rf_', 'rkf_')) or col == 'rider_age_at_race'}
            
            print(f"\nENHANCED EXPERIENCE FEATURES ({len(enhanced_features)} features):")
            
            # Group features by category for better readability
            categories = {
                'Points by Competition Type': [k for k in enhanced_features.keys() if 'prior_gc_' in k or 'prior_stage_' in k or 'prior_one_day_' in k],
                'Points by Race Category': [k for k in enhanced_features.keys() if 'prior_wt_' in k or 'prior_pro_' in k or 'prior_d1_' in k],
                'Overall Performance': [k for k in enhanced_features.keys() if k.startswith(('total_', 'avg_', 'overall_', 'points_', 'performance_'))],
                'Race Interactions': [k for k in enhanced_features.keys() if 'rider_vs_' in k],
                'Recent Form': [k for k in enhanced_features.keys() if 'recent_' in k],
            }
            
            for category, feature_list in categories.items():
                if feature_list:
                    print(f"\n  {category}:")
                    for feature in sorted(feature_list):
                        if feature in enhanced_features:
                            value = enhanced_features[feature]
                            if isinstance(value, float):
                                print(f"    {feature}: {value:.4f}")
                            else:
                                print(f"    {feature}: {value}")
            
        except Exception as e:
            print(f"Error calculating enhanced features: {e}")
        
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
            'basic_features': convert_numpy_to_python(basic_features),
            'enhanced_features': convert_numpy_to_python(enhanced_features),
            'feature_count_comparison': {
                'basic_count': len(basic_features),
                'enhanced_count': len(enhanced_features),
                'enhancement_ratio': len(enhanced_features) / len(basic_features) if basic_features else 0
            }
        }
        
        comparison_results['feature_comparisons'].append(comparison_data)
    
    # Save results to JSON
    output_file = "~/Documents/Cycling Project/cycling_project/webscrape_tools/test_feature_comp.json"
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
    print("- Performance trends and consistency metrics")
    print("- Recent form analysis")
    print("- Rider specialization detection")


if __name__ == "__main__":
    compare_experience_features()