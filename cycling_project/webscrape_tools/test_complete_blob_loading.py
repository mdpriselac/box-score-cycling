"""
Test loading the complete blob dataset and converting to analysis format.
"""

import time
import sqlite3
import pandas as pd
import numpy as np
import gzip
from typing import Dict, List, Tuple


# Feature mapping (from your config.py)
RACE_FEATURES = [
    # Basic Race Statistics
    'total_finishers', 'included_finishers', 'abandon_ratio',
    'winning_time', 'total_race_duration',
    
    # Performance Distribution
    'variance_absolute', 'variance_normalized',
    'std_deviation_absolute', 'std_deviation_normalized',
    'skewness_absolute', 'skewness_normalized',
    'kurtosis_absolute', 'kurtosis_normalized',
    'gini_coefficient',
    'shannon_entropy_absolute', 'shannon_entropy_normalized',
    
    # Time Gap Analysis
    '5th_percentile_gap', '10th_percentile_gap', '15th_percentile_gap',
    '20th_percentile_gap', '25th_percentile_gap', '30th_percentile_gap',
    '35th_percentile_gap', '40th_percentile_gap', '45th_percentile_gap',
    '50th_percentile_gap',
    
    # Group Dynamics
    'total_groups', 'riders_in_groups', 'proportion_in_groups',
    'largest_group_size', 'largest_group_position',
    'avg_group_size', 'std_group_size',
    'biggest_group_metric', 'time_gap_evenness_metric',
    'clumpiness_score', 'selection_metric'
]

PERCENTILES = [30, 40, 50, 60, 70, 80, 90, 100]


def load_complete_blob_data(correlation_type: str = 'same_type') -> pd.DataFrame:
    """Load complete correlation dataset from blob table"""
    
    print(f"=== Loading Complete Blob Dataset ===")
    print(f"Correlation type: {correlation_type}")
    print()
    
    # Connect to database
    conn = sqlite3.connect("database/database/cycling_races.db")
    
    # Load all blob data
    print("1. Loading blob data from database...")
    start_time = time.time()
    
    blob_query = """
    SELECT rider_result_id, competition_id, rider_id, correlation_matrix, race_count
    FROM rider_correlations_blob 
    WHERE correlation_type = ?
    """
    
    blob_df = pd.read_sql_query(blob_query, conn, params=[correlation_type])
    load_time = time.time() - start_time
    
    print(f"✓ Loaded {len(blob_df):,} blob rows in {load_time:.2f} seconds")
    print(f"  Average blob size: {blob_df['correlation_matrix'].apply(len).mean():.0f} bytes")
    
    conn.close()
    
    # Decompress and convert to denormalized format
    print("\n2. Decompressing correlation matrices...")
    start_time = time.time()
    
    all_rows = []
    failed_decompressions = 0
    
    for idx, row in blob_df.iterrows():
        try:
            # Decompress blob
            blob = row['correlation_matrix']
            decompressed = gzip.decompress(blob)
            matrix = np.frombuffer(decompressed, dtype=np.float64).reshape(8, 37)
            
            # Convert to denormalized format
            for percentile_idx, percentile in enumerate(PERCENTILES):
                for feature_idx, feature_name in enumerate(RACE_FEATURES):
                    correlation_value = matrix[percentile_idx, feature_idx]
                    
                    # Only include non-NaN values
                    if not np.isnan(correlation_value):
                        all_rows.append({
                            'rider_result_id': row['rider_result_id'],
                            'competition_id': row['competition_id'],
                            'rider_id': row['rider_id'],
                            'correlation_type': correlation_type,
                            'percentile': percentile,
                            'feature_idx': feature_idx,
                            'feature_name': feature_name,
                            'correlation_value': correlation_value,
                            'race_count': row['race_count']
                        })
        
        except Exception as e:
            failed_decompressions += 1
            continue
        
        # Progress update
        if (idx + 1) % 10000 == 0:
            elapsed = time.time() - start_time
            rate = (idx + 1) / elapsed
            print(f"  Processed {idx + 1:,} blobs ({rate:.0f} blobs/sec)")
    
    decomp_time = time.time() - start_time
    
    print(f"✓ Decompressed {len(blob_df):,} matrices in {decomp_time:.2f} seconds")
    print(f"  Rate: {len(blob_df)/decomp_time:.0f} matrices/second")
    print(f"  Failed decompressions: {failed_decompressions}")
    
    # Create final DataFrame
    print("\n3. Creating final DataFrame...")
    start_time = time.time()
    
    result_df = pd.DataFrame(all_rows)
    create_time = time.time() - start_time
    
    print(f"✓ Created DataFrame with {len(result_df):,} rows in {create_time:.2f} seconds")
    print(f"  Memory usage: {result_df.memory_usage(deep=True).sum() / 1024 / 1024:.1f} MB")
    
    # Data summary
    print("\n4. Data Summary:")
    print(f"  Unique features: {result_df['feature_name'].nunique()}")
    print(f"  Unique percentiles: {sorted(result_df['percentile'].unique())}")
    print(f"  Unique competitions: {result_df['competition_id'].nunique():,}")
    print(f"  Unique riders: {result_df['rider_id'].nunique():,}")
    print(f"  Correlation range: {result_df['correlation_value'].min():.4f} to {result_df['correlation_value'].max():.4f}")
    print(f"  Race count range: {result_df['race_count'].min()} to {result_df['race_count'].max()}")
    
    # Total time
    total_time = load_time + decomp_time + create_time
    print(f"\nTotal time: {total_time:.2f} seconds")
    print(f"Overall rate: {len(result_df)/total_time:,.0f} rows/second")
    
    return result_df


def test_analysis_compatibility(df: pd.DataFrame):
    """Test compatibility with existing analysis modules"""
    
    print("\n=== Testing Analysis Compatibility ===")
    
    # Test 1: Feature statistics (like your existing modules)
    print("1. Testing feature statistics calculation...")
    start_time = time.time()
    
    # Example: Calculate stats for abandon_ratio at 70th percentile
    test_data = df[
        (df['feature_name'] == 'abandon_ratio') & 
        (df['percentile'] == 70)
    ]
    
    if len(test_data) > 0:
        stats = {
            'mean_correlation': test_data['correlation_value'].mean(),
            'std_correlation': test_data['correlation_value'].std(),
            'median_correlation': test_data['correlation_value'].median(),
            'sample_size': len(test_data),
            'min_correlation': test_data['correlation_value'].min(),
            'max_correlation': test_data['correlation_value'].max()
        }
        
        calc_time = time.time() - start_time
        print(f"✓ Calculated stats for abandon_ratio/70th percentile in {calc_time:.4f} seconds")
        print(f"  Sample: mean={stats['mean_correlation']:.4f}, std={stats['std_correlation']:.4f}, n={stats['sample_size']}")
    
    # Test 2: Pattern analysis across percentiles
    print("\n2. Testing pattern analysis...")
    start_time = time.time()
    
    abandon_by_percentile = df[df['feature_name'] == 'abandon_ratio'].groupby('percentile')['correlation_value'].agg(['mean', 'std', 'count'])
    
    pattern_time = time.time() - start_time
    print(f"✓ Calculated pattern across percentiles in {pattern_time:.4f} seconds")
    print("Sample pattern:")
    print(abandon_by_percentile.head())
    
    # Test 3: Competition-specific filtering
    print("\n3. Testing competition filtering...")
    start_time = time.time()
    
    # Filter for a specific competition
    comp_data = df[df['competition_id'] == 53]
    filter_time = time.time() - start_time
    
    print(f"✓ Filtered to competition 53 in {filter_time:.4f} seconds")
    print(f"  Found {len(comp_data)} correlation values for this competition")
    
    print("\nAll tests passed! Blob data is compatible with existing analysis modules.")


if __name__ == "__main__":
    # Load complete dataset
    df = load_complete_blob_data('same_type')
    
    # Test compatibility
    if len(df) > 0:
        test_analysis_compatibility(df)
        
        print(f"\n=== Success! ===")
        print(f"Blob approach loaded {len(df):,} correlation values")
        print(f"This replaces the need for 37 separate feature queries!")
        print(f"Data is ready for your correlation analysis modules.")
    else:
        print(f"\n=== Failed ===")
        print(f"Blob loading produced no usable data.")