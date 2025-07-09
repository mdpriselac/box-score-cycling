#!/usr/bin/env python3
"""Test the feature builder with enhanced features."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rider_performance'))

from feature_builder import FeatureBuilder
import sqlite3
import pandas as pd

def test_feature_builder():
    """Test the feature builder with enhanced features."""
    db_path = "database/database/cycling_races.db"
    
    print("Testing feature builder with enhanced features...")
    print("=" * 80)
    
    # Initialize builder (will use enhanced features by default)
    builder = FeatureBuilder(db_path, use_enhanced_experience=True)
    
    print(f"Enhanced feature count: {len(builder.experience_feature_names)}")
    print(f"First 10 features: {builder.experience_feature_names[:10]}")
    print()
    
    # Get a sample rider-competition pair
    conn = sqlite3.connect(db_path)
    query = """
    SELECT rr.rider_id, rr.competition_id, r.name as rider_name, c.name as competition_name
    FROM rider_results rr
    JOIN riders r ON rr.rider_id = r.id
    JOIN competitions c ON rr.competition_id = c.id
    WHERE c.date BETWEEN '2010-01-01' AND '2010-12-31' 
    AND c.competition_type = 'stage'
    LIMIT 1
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty:
        print("No sample data found in the specified date range")
        return
    
    sample = df.iloc[0]
    
    rider_id = int(sample['rider_id'])
    competition_id = int(sample['competition_id'])
    
    print(f"Testing with rider {sample['rider_name']} (ID: {rider_id})")
    print(f"Competition: {sample['competition_name']} (ID: {competition_id})")
    print()
    
    # Get features for this rider-competition pair
    features = builder.get_prediction_features(rider_id, competition_id)
    
    if features:
        print(f"Successfully retrieved features!")
        print(f"Total features: {len(features)}")
        
        # Count different types of features
        experience_features = {k: v for k, v in features.items() 
                             if k in builder.experience_feature_names}
        race_features = {k: v for k, v in features.items() 
                        if k.startswith('rf_')}
        race_kind_features = {k: v for k, v in features.items() 
                            if k.startswith('rkf_')}
        
        print(f"\nFeature breakdown:")
        print(f"  Experience features: {len(experience_features)}")
        print(f"  Race features: {len(race_features)}")
        print(f"  Race kind features: {len(race_kind_features)}")
        
        # Show some experience feature values
        print(f"\nSample experience features:")
        sample_features = ['total_prior_races', 'prior_wt_proportion', 
                          'overall_success_rate', 'rider_age_at_race']
        
        for feat in sample_features:
            if feat in features:
                value = features[feat]
                if isinstance(value, float):
                    print(f"  {feat}: {value:.4f}")
                else:
                    print(f"  {feat}: {value}")
            else:
                print(f"  {feat}: NOT FOUND")
        
        # Check for some enhanced features
        print(f"\nSample enhanced features:")
        enhanced_samples = ['prior_stage_success_rate', 'points_variance',
                           'rider_vs_clumpiness_score_performance']
        
        for feat in enhanced_samples:
            if feat in features:
                value = features[feat]
                if isinstance(value, float):
                    print(f"  {feat}: {value:.4f}")
                else:
                    print(f"  {feat}: {value}")
            else:
                print(f"  {feat}: NOT FOUND (may depend on available data)")
        
        print(f"\nTarget values:")
        print(f"  UCI points actual: {features.get('uci_points_actual', 'N/A')}")
        print(f"  UCI points proportional: {features.get('uci_points_proportional', 'N/A')}")
        
    else:
        print("No features found - check rider/competition IDs")
    
    # Test feature names method
    print("\n" + "=" * 80)
    print("Testing get_feature_names method...")
    
    for comp_type in ['gc', 'stage', 'one_day']:
        feature_names = builder.get_feature_names(comp_type)
        print(f"\n{comp_type.upper()} competition features:")
        print(f"  Race features: {len(feature_names['race_features'])}")
        print(f"  Race kind features: {len(feature_names['race_kind_features'])}")
        print(f"  Experience features: {len(feature_names['experience_features'])}")


if __name__ == "__main__":
    test_feature_builder()