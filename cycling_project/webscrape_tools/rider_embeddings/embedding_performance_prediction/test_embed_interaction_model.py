#!/usr/bin/env python3
"""Test script for the embed_interaction_model with default settings."""

import sys
sys.path.append('../..')  # Add parent directories to path

from embed_interaction_model import EmbeddingInteractionPerformanceModel
import pandas as pd

def test_default_model():
    """Test the model with default configuration."""
    
    # Default configuration uses:
    # - rider database features
    # - race database features 
    # - all interaction features (dot_product, cosine_similarity, hadamard)
    # - interaction percentile: 70
    
    print("Testing EmbeddingInteractionPerformanceModel with default settings...")
    print("-" * 80)
    
    # Initialize model for stage races as a test
    import os
    db_path = os.path.abspath('../../database/database/cycling_races.db')
    print(f"Database path: {db_path}")
    print(f"Database exists: {os.path.exists(db_path)}")
    
    model = EmbeddingInteractionPerformanceModel(
        race_type='stage',
        db_path=db_path
    )
    
    print("Model initialized with default configuration:")
    print(f"  Race type: {model.race_type}")
    print(f"  Feature configuration:")
    for key, value in model.feature_config.items():
        print(f"    {key}: {value}")
    print()
    
    # Prepare data
    print("Preparing data...")
    try:
        data = model.prepare_data(min_year=2020, max_year=2023)
        print(f"Successfully prepared {len(data)} samples")
        print()
        
        # Show feature groups
        print("Feature groups prepared:")
        for group, features in model.feature_groups.items():
            if features:
                print(f"  {group}: {len(features)} features")
                # Show first 5 features as examples
                examples = features[:5]
                if len(features) > 5:
                    examples_str = ', '.join(examples) + ', ...'
                else:
                    examples_str = ', '.join(examples)
                print(f"    Examples: {examples_str}")
        print()
        
        # Check data statistics
        print("Data statistics:")
        print(f"  Years: {sorted(data['year'].unique())}")
        print(f"  Competitions: {data['competition_id'].nunique()}")
        print(f"  Riders: {data['rider_id'].nunique()}")
        print(f"  Target (uci_points_proportional):")
        print(f"    Mean: {data['uci_points_proportional'].mean():.4f}")
        print(f"    Std: {data['uci_points_proportional'].std():.4f}")
        print(f"    Zero rate: {(data['uci_points_proportional'] == 0).mean():.2%}")
        print()
        
        # Try training a small model
        print("Testing model training on a small subset...")
        # Use 2022 for training, 2023 for validation
        train_data = data[data['year'] < 2023]
        valid_data = data[data['year'] == 2023]
        
        print(f"Training samples: {len(train_data)}")
        print(f"Validation samples: {len(valid_data)}")
        
        if len(train_data) > 100 and len(valid_data) > 50:
            # Train with reduced iterations for quick test
            training_info = model.train(
                train_df=train_data,
                valid_df=valid_data,
                num_boost_round=50,
                early_stopping_rounds=10,
                verbose=True
            )
            
            print("\nTraining completed successfully!")
            print("Performance metrics:")
            for metric, value in training_info['performance_metrics'].items():
                if pd.notna(value):
                    print(f"  {metric}: {value:.4f}")
            
            # Get feature importance
            print("\nTop 10 most important features (regressor):")
            importance_df = model.get_feature_importance(stage='regressor', n_features=10)
            for _, row in importance_df.iterrows():
                print(f"  {row['feature']:40s} ({row['feature_group']:20s}): {row['importance']:.2f}")
        else:
            print("Not enough data for training test")
            
    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\nTest completed successfully!")
    return True


def test_custom_config():
    """Test with a custom configuration."""
    print("\n" + "="*80)
    print("Testing with custom configuration...")
    print("="*80)
    
    # Custom config: all features including interactions
    custom_config = {
        'use_rider_database': True,
        'use_race_database': True,
        'use_race_features': False,
        'use_rider_embeddings': False,
        'use_interaction_features': True,
        'interaction_types': ['dot_product', 'cosine_similarity', 'hadamard'],
        'interaction_percentile': 'all'  # Use phase2 matrix interactions
    }
    
    import os
    db_path = os.path.abspath('../../database/database/cycling_races.db')
    
    model = EmbeddingInteractionPerformanceModel(
        race_type='one_day',
        db_path=db_path,
        feature_config=custom_config
    )
    
    print("Custom configuration:")
    for key, value in custom_config.items():
        print(f"  {key}: {value}")
    print()
    
    try:
        data = model.prepare_data(min_year=2022, max_year=2023)
        print(f"Prepared {len(data)} samples with custom config")
        
        print("\nFeature groups:")
        for group, features in model.feature_groups.items():
            if features:
                print(f"  {group}: {len(features)} features - {features}")
                
    except Exception as e:
        print(f"Error with custom config: {e}")
        return False
    
    return True


if __name__ == "__main__":
    # Run tests
    success = test_default_model()
    
    if success:
        test_custom_config()
    
    print("\nAll tests completed!")