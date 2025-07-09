#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rider_performance.enhanced_rider_experience import EnhancedRiderExperience

# Test the configuration loading
enhanced_calc = EnhancedRiderExperience()

print("Configuration loaded:")
print(f"Race feature columns: {len(enhanced_calc.race_feature_columns)}")
print(f"Race kind feature columns: {len(enhanced_calc.race_kind_feature_columns)}")
print(f"Key race features: {enhanced_calc.key_race_features}")
print(f"Key race kind features: {enhanced_calc.key_race_kind_features}")

# Get feature names
feature_names = enhanced_calc._get_enhanced_feature_names()
print(f"\nTotal enhanced feature names: {len(feature_names)}")
print("Feature names:", feature_names[:10], "...")

# Test with fake data
import pandas as pd
import numpy as np

# Create minimal test data  
test_data = pd.DataFrame({
    'result_id': [1, 2, 3],
    'rider_id': [100, 100, 100],
    'competition_id': [1, 2, 3],
    'competition_date': ['2020-01-01', '2020-02-01', '2020-03-01'],
    'competition_type': ['stage', 'stage', 'stage'],
    'race_category': ['wt', 'wt', 'wt'],
    'uci_points_actual': [10, 5, 0],
    'uci_points_proportional': [20, 15, 0],
    'place': [10, 20, 50],
    'rider_age': [25, 25, 25],
    'time_gap': [0, 10, 100],
    'percentile': [0.1, 0.2, 0.5],
    'race_name': ['Test Race', 'Test Race', 'Test Race'],
    'race_year': [2020, 2020, 2020],
    'competition_name': ['Stage 1', 'Stage 2', 'Stage 3']
})

# Add dummy race features
for feature in ['clumpiness_score', 'selection_metric', 'gini_coefficient', 'time_gap_evenness_metric', 'std_deviation_normalized']:
    test_data[f'rf_{feature}'] = np.random.random(3)

# Add dummy race kind features
for feature in ['cluster_label', 'local_density', 'boundary_distance']:
    test_data[f'rkf_{feature}'] = np.random.random(3)

print(f"\nTest data shape: {test_data.shape}")
print(f"Test data columns: {list(test_data.columns)}")

try:
    result = enhanced_calc.add_enhanced_experience_features(test_data)
    print(f"\nSuccess! Result shape: {result.shape}")
    print(f"Result columns: {len(result.columns)}")
    
    # Show sample of enhanced features
    enhanced_cols = [col for col in result.columns if not col.startswith(('result_id', 'rider_id', 'competition_id', 'competition_name', 'competition_type', 'race_name', 'race_category', 'race_year', 'competition_date', 'place', 'time_gap', 'percentile', 'rider_age', 'uci_points', 'rf_', 'rkf_'))]
    print(f"Enhanced feature columns: {len(enhanced_cols)}")
    for col in enhanced_cols[:10]:
        print(f"  {col}: {result[col].tolist()}")
        
except Exception as e:
    print(f"\nError: {e}")
    import traceback
    traceback.print_exc()
    
    # Try to debug the issue by accessing the internal method
    print("\nTrying to debug internal calculation...")
    try:
        # Direct access to the internal method
        test_rider_df = test_data.copy()
        enhanced_features = {
            'result_id': test_rider_df['result_id'].values,
        }
        
        # Add all enhanced feature columns
        all_feature_names = enhanced_calc._get_enhanced_feature_names()
        for feature_name in all_feature_names:
            if feature_name != 'result_id':
                enhanced_features[feature_name] = []
        
        print(f"Initialized {len(enhanced_features)} features")
        
        # Try calculating for first race only
        prior_results = test_rider_df.iloc[:0]  # Empty 
        current_race = test_rider_df.iloc[0]
        
        print("Calculating first race features...")
        enhanced_calc._add_zero_experience_features(enhanced_features)
        
        print("Checking feature lengths after first race:")
        for feature_name in list(enhanced_features.keys())[:10]:
            print(f"  {feature_name}: {len(enhanced_features[feature_name])}")
        
    except Exception as e2:
        print(f"Debug error: {e2}")
        import traceback
        traceback.print_exc()