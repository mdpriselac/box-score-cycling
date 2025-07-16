#!/usr/bin/env python3
"""Test that checks rider_result_ids overlap between database and interaction files."""

import pandas as pd
import sqlite3
import os

def test_interaction_overlap():
    """Test the overlap between database rider_result_ids and interaction data."""
    
    # Determine paths based on current working directory
    if os.path.basename(os.getcwd()) == 'webscrape_tools':
        # Running from webscrape_tools folder
        db_path = os.path.abspath('database/database/cycling_races.db')
        interaction_base_path = 'interaction_embeddings_db_optimized/phase2'
    else:
        # Running from embedding_performance_prediction folder
        db_path = os.path.abspath('../../database/database/cycling_races.db')
        interaction_base_path = '../../interaction_embeddings_db_optimized/phase2'
    
    print(f"Database path: {db_path}")
    print(f"Database exists: {os.path.exists(db_path)}")
    print(f"Interaction base path: {interaction_base_path}")
    
    race_types = ['stage', 'one_day', 'gc', 'stage_one_day', 'all']
    
    for race_type in race_types:
        print(f"\n{'='*60}")
        print(f"Testing {race_type.upper()} race type")
        print(f"{'='*60}")
        
        # Load interaction data
        interaction_file = f"{interaction_base_path}/{race_type}/matrix_interactions.parquet"
        
        if not os.path.exists(interaction_file):
            print(f"❌ Interaction file not found: {interaction_file}")
            continue
            
        interaction_df = pd.read_parquet(interaction_file)
        interaction_ids = set(interaction_df['rider_result_id'].unique())
        
        print(f"📊 Interaction data: {len(interaction_ids)} rider_result_ids")
        
        # Query database for these specific rider_result_ids
        conn = sqlite3.connect(db_path)
        
        # Get sample of interaction IDs for query (SQLite has limits)
        sample_ids = list(interaction_ids)[:100]  # First 100 for testing
        ids_str = ','.join([str(id) for id in sample_ids])
        
        query = f"""
        SELECT 
            rr.id as rider_result_id,
            c.competition_type,
            r.year,
            rr.uci_points_proportional
        FROM rider_results rr
        JOIN competitions c ON rr.competition_id = c.id
        JOIN races r ON c.race_id = r.id
        WHERE rr.id IN ({ids_str})
        ORDER BY r.year, rr.id
        """
        
        db_results = pd.read_sql_query(query, conn)
        conn.close()
        
        if len(db_results) == 0:
            print("❌ No matching rider_result_ids found in database")
            continue
            
        print(f"✅ Found {len(db_results)} matching records in database")
        
        # Show year distribution
        year_counts = db_results['year'].value_counts().sort_index()
        print(f"📅 Year distribution:")
        for year, count in year_counts.items():
            print(f"   {year}: {count} records")
        
        # Show competition type distribution
        comp_type_counts = db_results['competition_type'].value_counts()
        print(f"🏁 Competition type distribution:")
        for comp_type, count in comp_type_counts.items():
            print(f"   {comp_type}: {count} records")
        
        # Target variable stats
        target_stats = db_results['uci_points_proportional'].describe()
        print(f"🎯 Target variable (uci_points_proportional):")
        print(f"   Mean: {target_stats['mean']:.4f}")
        print(f"   Std: {target_stats['std']:.4f}")
        print(f"   Zero rate: {(db_results['uci_points_proportional'] == 0).mean():.2%}")
        
        # Show sample IDs for testing
        sample_valid_ids = db_results['rider_result_id'].head(10).tolist()
        print(f"📋 Sample valid rider_result_ids for testing:")
        print(f"   {sample_valid_ids}")
        
        # Check if we can create a model with this data
        print(f"🔬 Model feasibility:")
        print(f"   Interaction features: {len(interaction_df.columns) - 1}")  # -1 for rider_result_id
        print(f"   Available samples: {len(db_results)}")
        
        if len(db_results) > 50:
            print("   ✅ Sufficient data for model training")
        else:
            print("   ⚠️  Limited data - may need more samples")

def test_with_actual_interaction_data():
    """Test the model with actual interaction data that exists."""
    print(f"\n{'='*80}")
    print("TESTING MODEL WITH ACTUAL INTERACTION DATA")
    print(f"{'='*80}")
    
    # Import our model
    if os.path.basename(os.getcwd()) == 'webscrape_tools':
        # Running from webscrape_tools folder - add the path
        import sys
        sys.path.append('rider_embeddings/embedding_performance_prediction')
        from embed_interaction_model import EmbeddingInteractionPerformanceModel
        db_path = os.path.abspath('database/database/cycling_races.db')
    else:
        # Running from embedding_performance_prediction folder
        from embed_interaction_model import EmbeddingInteractionPerformanceModel
        db_path = os.path.abspath('../../database/database/cycling_races.db')
    
    # Test with stage_one_day as it has the most data (9682 samples)
    print("Testing with stage_one_day race type (most data available)...")
    
    config = {
        'use_rider_database': True,
        'use_race_database': True,
        'use_race_features': False,
        'use_rider_embeddings': False,
        'use_interaction_features': True,
        'interaction_types': ['dot_product', 'cosine_similarity', 'hadamard'],
        'interaction_percentile': 'all'
    }
    
    model = EmbeddingInteractionPerformanceModel(
        race_type='stage_one_day',
        db_path=db_path,
        feature_config=config
    )
    
    # Use 2024 data since that's when interaction data is available
    try:
        data = model.prepare_data(min_year=2024, max_year=2024)
        print(f"✅ Successfully prepared {len(data)} samples")
        
        if len(data) > 100:
            print("🎯 Sufficient data for model training test")
            
            # Quick training test with small subset
            train_data = data.sample(n=min(500, len(data)), random_state=42)
            
            print(f"Testing model training with {len(train_data)} samples...")
            
            # Split into train/test
            split_idx = int(len(train_data) * 0.8)
            train_subset = train_data.iloc[:split_idx]
            test_subset = train_data.iloc[split_idx:]
            
            # Train model
            training_info = model.train(
                train_df=train_subset,
                valid_df=test_subset,
                num_boost_round=20,  # Quick test
                early_stopping_rounds=5,
                verbose=True
            )
            
            print("✅ Model training successful!")
            print(f"   Features used: {training_info['n_features']}")
            print(f"   Feature groups: {training_info['feature_groups']}")
            print(f"   RMSE: {training_info['performance_metrics']['rmse_overall']:.4f}")
            
        else:
            print("⚠️  Not enough data for training test")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_interaction_overlap()
    test_with_actual_interaction_data()