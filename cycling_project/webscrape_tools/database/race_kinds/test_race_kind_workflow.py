"""
Test script for the complete race kind workflow:
1. Find race kinds and save the best model
2. Calculate and save race kind features
3. Apply saved model to new races
"""

import os
import sys
from race_kind_models import RaceKindModelManager

# Database path
DB_PATH = "~/Documents/Cycling Project/cycling_project/webscrape_tools/database/database/cycling_races.db"


def test_workflow():
    """Test the complete race kind workflow."""
    
    print("="*60)
    print("RACE KIND WORKFLOW TEST")
    print("="*60)
    
    # Step 1: Run race kind analysis with model saving
    print("\n1. Running race kind analysis with model saving...")
    print("-" * 50)
    
    cmd = [
        "uv", "run", "python", "database/race_kinds/find_race_kinds.py",
        "--mode", "single",
        "--percentile", "70",
        "--method", "kmeans",
        "--competition-type", "stage",
        "--save-model",
        "--save-features",
        "--use-feature-selection",
        "--max-features", "15"
    ]
    
    print(f"Running command: {' '.join(cmd)}")
    os.system(' '.join(cmd))
    
    # Step 2: List saved models
    print("\n\n2. Listing saved models...")
    print("-" * 50)
    
    model_manager = RaceKindModelManager(DB_PATH)
    saved_models = model_manager.list_saved_models()
    
    if not saved_models:
        print("No saved models found!")
        return
    
    print(f"Found {len(saved_models)} saved models:")
    for i, model_info in enumerate(saved_models[:3]):  # Show latest 3
        print(f"\n  Model {i+1}:")
        print(f"    Algorithm: {model_info['algorithm']}")
        print(f"    Percentile: {model_info['percentile']}")
        print(f"    Timestamp: {model_info['timestamp']}")
        print(f"    Features: {len(model_info['feature_columns'])}")
    
    # Step 3: Apply the latest model to new races
    print("\n\n3. Applying model to new races...")
    print("-" * 50)
    
    latest_model = saved_models[0]
    model_path = latest_model['model_path']
    
    print(f"Using model: {os.path.basename(model_path)}")
    
    # Apply to all one-day races in the same percentile table
    try:
        n_processed = model_manager.predict_and_store_new_races(
            model_path=model_path,
            source_table=f"race_features_{latest_model['percentile']}",
            target_table=f"race_kind_features_test_{latest_model['algorithm']}_{latest_model['percentile']}",
            competition_type='one_day'
        )
        
        print(f"Successfully processed {n_processed} one-day races")
        
    except Exception as e:
        print(f"Error applying model: {e}")
    
    # Step 4: Query the results
    print("\n\n4. Sample race kind features...")
    print("-" * 50)
    
    import sqlite3
    import pandas as pd
    
    conn = sqlite3.connect(DB_PATH)
    
    # Get sample of race kind features
    query = f"""
    SELECT 
        rkf.competition_id,
        rkf.cluster_label,
        rkf.local_density,
        rkf.boundary_distance,
        rf.race_name,
        rf.competition_name
    FROM race_kind_features_test_{latest_model['algorithm']}_{latest_model['percentile']} rkf
    JOIN race_features_{latest_model['percentile']} rf 
        ON rkf.competition_id = rf.competition_id
    LIMIT 10
    """
    
    try:
        sample_df = pd.read_sql_query(query, conn)
        print("\nSample race kind features:")
        print(sample_df.to_string(index=False))
    except Exception as e:
        print(f"Error querying results: {e}")
    
    conn.close()
    
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)


if __name__ == "__main__":
    test_workflow()