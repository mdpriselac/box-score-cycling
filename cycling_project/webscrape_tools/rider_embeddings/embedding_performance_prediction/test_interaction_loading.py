#!/usr/bin/env python3
"""Quick test for interaction loading functionality."""

import pandas as pd
from pathlib import Path

def test_phase2_loading():
    """Test phase2 matrix interactions loading."""
    print("Testing phase2 matrix interactions...")
    
    base_path = Path("../../interaction_embeddings_db_optimized/phase2")
    matrix_file = base_path / "stage" / "matrix_interactions.parquet"
    
    print(f"Looking for file: {matrix_file}")
    print(f"File exists: {matrix_file.exists()}")
    
    if matrix_file.exists():
        df = pd.read_parquet(matrix_file)
        print(f"Shape: {df.shape}")
        print(f"Columns: {df.columns.tolist()[:10]}...")
        
        # Test filtering to specific rider_result_ids
        test_ids = [106249, 10304, 22671]
        filtered = df[df['rider_result_id'].isin(test_ids)]
        print(f"Filtered shape: {filtered.shape}")
        print(f"Test IDs found: {filtered['rider_result_id'].tolist()}")
        
        # Test feature selection
        feature_cols = []
        if 'dot_product' in df.columns:
            feature_cols.append('dot_product')
        if 'cosine_similarity' in df.columns:
            feature_cols.append('cosine_similarity')
        hadamard_cols = [col for col in df.columns if col.startswith('hadamard_')]
        feature_cols.extend(hadamard_cols)
        
        print(f"Available features: {len(feature_cols)}")
        print(f"Feature examples: {feature_cols[:5]}...")
        
        result = filtered[['rider_result_id'] + feature_cols]
        print(f"Result shape: {result.shape}")
        return result
    
    return None

def test_phase1_loading():
    """Test phase1 individual percentile loading."""
    print("\nTesting phase1 individual percentile loading...")
    
    base_path = Path("../../interaction_embeddings_db_optimized/phase1")
    
    # Test dot products
    dot_file = base_path / "stage" / "dot_products.parquet"
    print(f"Dot products file exists: {dot_file.exists()}")
    
    if dot_file.exists():
        df = pd.read_parquet(dot_file)
        print(f"Dot products shape: {df.shape}")
        
        # Filter to specific percentile
        percentile_name = "race_features_70"
        filtered = df[df['percentile'] == percentile_name]
        print(f"Filtered to {percentile_name}: {len(filtered)} rows")
        
        # Test specific rider_result_ids
        test_ids = [106249, 10304, 22671]
        test_data = filtered[filtered['rider_result_id'].isin(test_ids)]
        print(f"Test data shape: {test_data.shape}")
        
        if len(test_data) > 0:
            renamed = test_data[['rider_result_id', 'value']].rename(columns={'value': 'dot_product'})
            print(f"Renamed columns: {renamed.columns.tolist()}")
            print(renamed.head())
            return renamed
    
    return None

def test_full_interaction_loading():
    """Test the full interaction loading process."""
    print("\nTesting full interaction loading process...")
    
    # Simulate the actual loading process
    test_rider_result_ids = [106249, 10304, 22671, 118603, 169313]
    interaction_data = pd.DataFrame({'rider_result_id': test_rider_result_ids})
    
    # Phase 2 loading (like percentile='all')
    base_path = Path("../../interaction_embeddings_db_optimized/phase2")
    matrix_file = base_path / "stage" / "matrix_interactions.parquet"
    
    if matrix_file.exists():
        matrix_data = pd.read_parquet(matrix_file)
        matrix_data = matrix_data[matrix_data['rider_result_id'].isin(test_rider_result_ids)]
        
        interaction_types = ['dot_product', 'cosine_similarity', 'hadamard']
        feature_cols = []
        
        if 'dot_product' in interaction_types:
            feature_cols.append('dot_product')
        if 'cosine_similarity' in interaction_types:
            feature_cols.append('cosine_similarity')
        if 'hadamard' in interaction_types:
            hadamard_cols = [col for col in matrix_data.columns if col.startswith('hadamard_')]
            feature_cols.extend(hadamard_cols)
        
        if feature_cols:
            interaction_data = matrix_data[['rider_result_id'] + feature_cols]
            print(f"Loaded {len(feature_cols)} interaction features")
            print(f"Final shape: {interaction_data.shape}")
            print(f"Sample data:")
            print(interaction_data.head())
            
            # Check for missing values
            print(f"\nMissing values per column:")
            for col in feature_cols:
                missing = interaction_data[col].isna().sum()
                print(f"  {col}: {missing}")
            
            return interaction_data
    
    return None

if __name__ == "__main__":
    test_phase2_loading()
    test_phase1_loading()
    test_full_interaction_loading()