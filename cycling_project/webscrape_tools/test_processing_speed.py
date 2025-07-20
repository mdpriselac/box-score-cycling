"""
Test the statistical processing speed on loaded data.
"""

import time
import pandas as pd
import numpy as np
from feature_optimization.correlation_feature_analysis.data_loader import CorrelationDataLoader
from feature_optimization.correlation_feature_analysis.statistics_calculator import CorrelationStatisticsCalculator


def test_stats_calculation_speed():
    """Test how fast we can calculate statistics on loaded data"""
    
    print("=== Testing Statistical Calculation Speed ===")
    
    with CorrelationDataLoader("database/database/cycling_races.db") as loader:
        
        # Load data for abandon_ratio from smaller correlation type
        print("Loading abandon_ratio data from 'same_type'...")
        start_time = time.time()
        
        chunks = []
        for chunk in loader.load_correlation_data('same_type', chunk_size=1_000_000):
            feature_chunk = chunk[chunk['feature_name'] == 'abandon_ratio']
            if len(feature_chunk) > 0:
                chunks.append(feature_chunk)
        
        df = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()
        load_time = time.time() - start_time
        
        print(f"✓ Loaded {len(df):,} rows in {load_time:.2f} seconds")
        
        if len(df) == 0:
            print("No data found - trying 'stage_one_days'")
            
            chunks = []
            for chunk in loader.load_correlation_data('stage_one_days', chunk_size=1_000_000):
                feature_chunk = chunk[chunk['feature_name'] == 'abandon_ratio']
                if len(feature_chunk) > 0:
                    chunks.append(feature_chunk)
            
            df = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()
            load_time = time.time() - start_time
            print(f"✓ Loaded {len(df):,} rows in {load_time:.2f} seconds")
        
        if len(df) > 0:
            # Test statistical calculations
            print(f"\nTesting statistics calculation...")
            calc = CorrelationStatisticsCalculator()
            
            start_time = time.time()
            results = []
            
            for percentile in sorted(df['percentile'].unique()):
                p_data = df[df['percentile'] == percentile]
                stats = calc.calculate_feature_stats('abandon_ratio', percentile, 'same_type', p_data)
                if stats:
                    results.append(stats)
            
            calc_time = time.time() - start_time
            
            print(f"✓ Calculated stats for {len(results)} percentiles in {calc_time:.3f} seconds")
            print(f"  Total time (load + calc): {load_time + calc_time:.2f} seconds")
            
            # Extrapolate to full analysis
            features_per_second = 1 / (load_time + calc_time)
            total_time_37_features = 37 / features_per_second
            
            print(f"\nExtrapolation:")
            print(f"  Rate: {features_per_second:.2f} features/second")
            print(f"  Estimated time for 37 features: {total_time_37_features:.1f} seconds ({total_time_37_features/60:.1f} minutes)")


def test_memory_usage():
    """Test memory usage patterns"""
    
    print("\n=== Testing Memory Usage ===")
    
    try:
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        print(f"Initial memory: {initial_memory:.1f} MB")
        
        with CorrelationDataLoader("database/database/cycling_races.db") as loader:
            
            # Load data for multiple features
            print("Loading data for first 5 features...")
            
            chunk_gen = loader.load_correlation_data('same_type', chunk_size=1_000_000)
            first_chunk = next(chunk_gen)
            
            # Get first 5 features
            features = first_chunk['feature_name'].unique()[:5]
            
            all_data = []
            for feature in features:
                feature_data = first_chunk[first_chunk['feature_name'] == feature]
                all_data.append(feature_data)
                
                current_memory = process.memory_info().rss / 1024 / 1024
                print(f"  {feature}: {len(feature_data):,} rows, Memory: {current_memory:.1f} MB (+{current_memory - initial_memory:.1f})")
            
            combined_df = pd.concat(all_data, ignore_index=True)
            final_memory = process.memory_info().rss / 1024 / 1024
            
            print(f"Combined data: {len(combined_df):,} rows")
            print(f"Final memory: {final_memory:.1f} MB (+{final_memory - initial_memory:.1f} MB)")
            print(f"Memory per million rows: ~{(final_memory - initial_memory) / (len(combined_df) / 1000000):.1f} MB")
        
    except ImportError:
        print("psutil not available - skipping memory test")


if __name__ == "__main__":
    test_stats_calculation_speed()
    test_memory_usage()
    
    print("\n=== Processing Speed Test Complete ===")
    print("Please share these results!")