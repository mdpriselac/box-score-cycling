#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rider_performance.enhanced_rider_experience import EnhancedRiderExperience
import pandas as pd
import numpy as np

# Create minimal test data with just 1 rider, 1 race
test_data = pd.DataFrame({
    'result_id': [1],
    'rider_id': [100],
    'competition_id': [1],
    'competition_date': ['2020-01-01'],
    'competition_type': ['stage'],
    'race_category': ['wt'],
    'uci_points_actual': [10],
    'uci_points_proportional': [20],
    'place': [10],
    'rider_age': [25],
    'time_gap': [0],
    'percentile': [0.1],
    'race_name': ['Test Race'],
    'race_year': [2020],
    'competition_name': ['Stage 1']
})

# Add dummy race features
for feature in ['clumpiness_score', 'selection_metric', 'gini_coefficient', 'time_gap_evenness_metric', 'std_deviation_normalized']:
    test_data[f'rf_{feature}'] = [0.5]

# Add dummy race kind features
for feature in ['cluster_label', 'local_density', 'boundary_distance']:
    test_data[f'rkf_{feature}'] = [0.5]

print("Single race test:")
print(f"Test data shape: {test_data.shape}")

enhanced_calc = EnhancedRiderExperience()

try:
    result = enhanced_calc.add_enhanced_experience_features(test_data)
    print(f"Success! Result shape: {result.shape}")
    print(f"Result columns: {len(result.columns)}")
    
    enhanced_cols = [col for col in result.columns if col.startswith(('prior_', 'total_', 'avg_', 'overall_', 'points_', 'performance_', 'rider_vs_', 'recent_'))]
    print(f"Enhanced feature columns: {len(enhanced_cols)}")
    for col in enhanced_cols[:10]:
        print(f"  {col}: {result[col].tolist()}")
    
    # Now try with 2 races
    print("\n" + "="*50)
    print("Two race test:")
    
    test_data_2 = pd.DataFrame({
        'result_id': [1, 2],
        'rider_id': [100, 100],
        'competition_id': [1, 2],
        'competition_date': ['2020-01-01', '2020-02-01'],
        'competition_type': ['stage', 'stage'],
        'race_category': ['wt', 'wt'],
        'uci_points_actual': [10, 5],
        'uci_points_proportional': [20, 15],
        'place': [10, 20],
        'rider_age': [25, 25],
        'time_gap': [0, 10],
        'percentile': [0.1, 0.2],
        'race_name': ['Test Race', 'Test Race'],
        'race_year': [2020, 2020],
        'competition_name': ['Stage 1', 'Stage 2']
    })
    
    # Add dummy race features
    for feature in ['clumpiness_score', 'selection_metric', 'gini_coefficient', 'time_gap_evenness_metric', 'std_deviation_normalized']:
        test_data_2[f'rf_{feature}'] = [0.5, 0.6]
    
    # Add dummy race kind features
    for feature in ['cluster_label', 'local_density', 'boundary_distance']:
        test_data_2[f'rkf_{feature}'] = [0.5, 0.6]
    
    result_2 = enhanced_calc.add_enhanced_experience_features(test_data_2)
    print(f"Success! Result shape: {result_2.shape}")
    print(f"Result columns: {len(result_2.columns)}")
    
    # Show first few enhanced features for both races
    for col in enhanced_cols[:5]:
        print(f"  {col}: {result_2[col].tolist()}")
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()