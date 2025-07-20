"""
Test different chunk sizes and correlation types for performance comparison.
"""

import time
import pandas as pd
from feature_optimization.correlation_feature_analysis.data_loader import CorrelationDataLoader


def test_chunk_size_performance():
    """Test different chunk sizes on abandon_ratio feature"""
    
    print("=== Testing Chunk Size Performance ===")
    print("Feature: abandon_ratio, Correlation: all_races")
    
    chunk_sizes = [100_000, 500_000, 1_000_000, 2_000_000]
    
    with CorrelationDataLoader("database/database/cycling_races.db") as loader:
        
        for chunk_size in chunk_sizes:
            print(f"\nTesting chunk size: {chunk_size:,}")
            
            start_time = time.time()
            total_rows = 0
            chunk_count = 0
            
            try:
                for chunk in loader.load_correlation_data('all_races', chunk_size=chunk_size):
                    # Filter to abandon_ratio
                    feature_chunk = chunk[chunk['feature_name'] == 'abandon_ratio']
                    total_rows += len(feature_chunk)
                    chunk_count += 1
                    
                    # Show progress for large chunks
                    if chunk_count % 5 == 0:
                        elapsed = time.time() - start_time
                        print(f"  Processed {chunk_count} chunks, {total_rows:,} rows in {elapsed:.1f}s")
                
                elapsed = time.time() - start_time
                print(f"✓ Total: {total_rows:,} rows in {chunk_count} chunks, {elapsed:.2f} seconds")
                print(f"  Rate: {total_rows/elapsed:,.0f} rows/second")
                
            except Exception as e:
                print(f"✗ Error with chunk size {chunk_size}: {e}")


def test_correlation_type_sizes():
    """Test data sizes for different correlation types"""
    
    print("\n=== Testing Correlation Type Sizes ===")
    
    correlation_types = ['same_type', 'stage_one_days', 'all_races']
    
    with CorrelationDataLoader("database/database/cycling_races.db") as loader:
        
        for corr_type in correlation_types:
            print(f"\nTesting correlation type: {corr_type}")
            
            start_time = time.time()
            total_rows = 0
            feature_count = 0
            
            try:
                # Load first chunk only to estimate size
                chunk_gen = loader.load_correlation_data(corr_type, chunk_size=100_000)
                first_chunk = next(chunk_gen)
                
                features_in_chunk = first_chunk['feature_name'].nunique()
                rows_in_chunk = len(first_chunk)
                
                elapsed = time.time() - start_time
                
                print(f"✓ First chunk: {rows_in_chunk:,} rows, {features_in_chunk} unique features in {elapsed:.2f}s")
                print(f"  Estimated total if 37 features: {rows_in_chunk * 37 / features_in_chunk:,.0f} rows")
                
            except Exception as e:
                print(f"✗ Error with {corr_type}: {e}")


def test_single_feature_load():
    """Test loading complete data for one feature with large chunks"""
    
    print("\n=== Testing Single Feature Complete Load ===")
    print("Feature: abandon_ratio, Large chunks")
    
    correlation_types = ['same_type', 'stage_one_days']  # Skip all_races for now
    
    with CorrelationDataLoader("database/database/cycling_races.db") as loader:
        
        for corr_type in correlation_types:
            print(f"\nTesting {corr_type} with abandon_ratio:")
            
            start_time = time.time()
            chunks = []
            
            try:
                for chunk in loader.load_correlation_data(corr_type, chunk_size=1_000_000):
                    feature_chunk = chunk[chunk['feature_name'] == 'abandon_ratio']
                    if len(feature_chunk) > 0:
                        chunks.append(feature_chunk)
                
                df = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()
                elapsed = time.time() - start_time
                
                print(f"✓ Loaded {len(df):,} rows in {elapsed:.2f} seconds")
                if len(df) > 0:
                    print(f"  Percentiles: {sorted(df['percentile'].unique())}")
                    print(f"  Non-null: {df['correlation_value'].notna().sum():,}")
                
            except Exception as e:
                print(f"✗ Error: {e}")


if __name__ == "__main__":
    test_correlation_type_sizes()
    test_chunk_size_performance() 
    test_single_feature_load()
    
    print("\n=== Test Complete ===")
    print("Please share these timing results!")