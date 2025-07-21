#!/usr/bin/env python3
"""
Investigate the actual structure of correlation blobs to diagnose missing features.
"""

import sqlite3
import numpy as np
import gzip
from correlation_feature_analysis import config

def investigate_blob_structure(db_path: str):
    """Investigate the actual structure of correlation blobs"""
    
    print("🔍 INVESTIGATING CORRELATION BLOB STRUCTURE")
    print("=" * 60)
    
    conn = sqlite3.connect(db_path)
    
    # First, let's see what correlation types we have
    print("Available correlation types:")
    cursor = conn.execute("""
        SELECT DISTINCT correlation_type, COUNT(*) as count 
        FROM rider_correlations_blob 
        GROUP BY correlation_type
    """)
    correlation_types = cursor.fetchall()
    for corr_type, count in correlation_types:
        print(f"  - {corr_type}: {count:,} entries")
    
    # Pick the first correlation type for investigation
    if not correlation_types:
        print("❌ No correlation data found!")
        return
    
    test_correlation_type = correlation_types[0][0]
    print(f"\n📊 Testing with correlation type: {test_correlation_type}")
    
    # Find a high-quality blob with full data
    print("\nSearching for high-quality blob with complete data...")
    cursor = conn.execute("""
        SELECT rcb.correlation_matrix, rcb.rider_result_id, rcb.race_count,
               dq.data_completeness, dq.races_with_features, dq.percentile_availability
        FROM rider_correlations_blob rcb
        JOIN correlation_data_quality dq 
            ON rcb.rider_result_id = dq.rider_result_id 
            AND rcb.correlation_type = dq.correlation_type
        WHERE rcb.correlation_type = ?
            AND dq.percentile_availability = '[1, 1, 1, 1, 1, 1, 1, 1]'  -- All percentiles available (note: spaces matter!)
            AND dq.races_with_features >= 50
        ORDER BY dq.races_with_features DESC, dq.data_completeness DESC
        LIMIT 1
    """, [test_correlation_type])
    
    result = cursor.fetchone()
    if not result:
        print("❌ No high-quality blob found! Trying with relaxed criteria...")
        # Try with relaxed criteria
        cursor = conn.execute("""
            SELECT rcb.correlation_matrix, rcb.rider_result_id, rcb.race_count,
                   dq.data_completeness, dq.races_with_features, dq.percentile_availability
            FROM rider_correlations_blob rcb
            JOIN correlation_data_quality dq 
                ON rcb.rider_result_id = dq.rider_result_id 
                AND rcb.correlation_type = dq.correlation_type
            WHERE rcb.correlation_type = ?
                AND dq.data_completeness >= 0.7
                AND dq.races_with_features >= 10
            ORDER BY dq.races_with_features DESC, dq.data_completeness DESC
            LIMIT 1
        """, [test_correlation_type])
        result = cursor.fetchone()
        
        if not result:
            print("❌ No blob data found even with relaxed criteria!")
            return
    
    blob, rider_result_id, race_count, data_completeness, races_with_features, percentile_availability = result
    print(f"✓ Found high-quality blob:")
    print(f"  - Rider result ID: {rider_result_id}")
    print(f"  - Race count: {race_count}")
    print(f"  - Data completeness: {data_completeness:.1%}")
    print(f"  - Races with features: {races_with_features}")
    print(f"  - Percentile availability: {percentile_availability}")
    print(f"  - Blob size: {len(blob):,} bytes")
    
    # Decompress and analyze
    try:
        decompressed = gzip.decompress(blob)
        print(f"✓ Decompressed to: {len(decompressed):,} bytes")
        
        # Try to determine the actual matrix shape
        matrix = np.frombuffer(decompressed, dtype=np.float64)
        total_elements = len(matrix)
        print(f"✓ Matrix contains: {total_elements:,} elements")
        
        # We know there are 8 percentiles, so features = total_elements / 8
        actual_features = total_elements // 8
        print(f"✓ Calculated features: {actual_features} (total_elements / 8 percentiles)")
        
        # Try reshaping to see if it works
        try:
            actual_matrix = matrix.reshape(8, actual_features)
            print(f"✓ Successfully reshaped to: {actual_matrix.shape}")
            
            print(f"\n📋 COMPARISON:")
            print(f"Expected features (from config): {len(config.RACE_FEATURES)}")
            print(f"Actual features (from blob):     {actual_features}")
            print(f"Missing features:                {len(config.RACE_FEATURES) - actual_features}")
            
        except Exception as e:
            print(f"❌ Could not reshape matrix: {e}")
            
            # Try different potential shapes
            print("\nTrying to determine actual shape...")
            for n_features in range(20, 50):
                if total_elements % n_features == 0:
                    n_percentiles = total_elements // n_features
                    print(f"  Possible shape: ({n_percentiles}, {n_features})")
    
    except Exception as e:
        print(f"❌ Could not decompress blob: {e}")
        return
    
    print(f"\n🔍 FEATURE ANALYSIS:")
    print(f"Expected features from config.RACE_FEATURES:")
    
    # Show all expected features with their indices
    for i, feature in enumerate(config.RACE_FEATURES):
        marker = "🔢" if any(char.isdigit() for char in feature.split('_')[0]) else "📊"
        print(f"  {i:2d}. {marker} {feature}")
    
    # Identify the percentile gap features specifically
    percentile_gap_features = [f for f in config.RACE_FEATURES if 'percentile_gap' in f]
    print(f"\nPercentile gap features ({len(percentile_gap_features)}):")
    for feature in percentile_gap_features:
        print(f"  🔢 {feature}")
    
    # Show what we expect vs what we might actually have
    non_percentile_features = [f for f in config.RACE_FEATURES if 'percentile_gap' not in f]
    print(f"\nNon-percentile features ({len(non_percentile_features)}):")
    for i, feature in enumerate(non_percentile_features):
        print(f"  {i:2d}. 📊 {feature}")
    
    print(f"\n💡 HYPOTHESIS:")
    if actual_features == len(non_percentile_features):
        print("✅ The actual blob contains exactly the non-percentile features!")
        print("✅ This confirms that percentile gap features were filtered out during matrix creation")
        print("✅ Likely because column names starting with numbers need quotes in SQL")
    else:
        print(f"❓ Actual features ({actual_features}) ≠ non-percentile features ({len(non_percentile_features)})")
        print("❓ There might be a different filtering pattern")
    
    # Let's check actual values from different percentiles
    if 'actual_matrix' in locals():
        print(f"\n📊 SAMPLE DATA FROM BLOB:")
        print(f"Matrix shape: {actual_matrix.shape}")
        
        # Show data from multiple percentiles to see if we get non-NaN values
        percentile_names = ['30%', '40%', '50%', '60%', '70%', '80%', '90%', '100%']
        
        for p_idx, p_name in enumerate(percentile_names):
            print(f"\nSample values from {p_name} percentile:")
            sample_values = actual_matrix[p_idx, :min(10, actual_features)]
            non_nan_count = 0
            
            for i, val in enumerate(sample_values):
                if not np.isnan(val):
                    feature_name = config.RACE_FEATURES[i] if i < len(config.RACE_FEATURES) else f"feature_{i}"
                    print(f"  {i:2d}. {feature_name}: {val:.6f}")
                    non_nan_count += 1
            
            if non_nan_count == 0:
                print(f"  All values are NaN for {p_name} percentile")
            else:
                print(f"  ({non_nan_count} non-NaN values found)")
            
            # Stop after finding percentiles with data
            if non_nan_count > 5:
                break
        
        # Summary of data availability by percentile
        print(f"\n📈 DATA AVAILABILITY SUMMARY:")
        for p_idx, p_name in enumerate(percentile_names):
            row_data = actual_matrix[p_idx, :]
            non_nan_count = np.sum(~np.isnan(row_data))
            nan_count = np.sum(np.isnan(row_data))
            print(f"  {p_name}: {non_nan_count:2d} valid, {nan_count:2d} NaN out of {actual_features} features")
    
    conn.close()
    
    print(f"\n🎯 RECOMMENDATIONS:")
    print("1. Update config.RACE_FEATURES to match the actual 27 stored features")
    print("2. Remove the 10 percentile gap features from the expected feature list")
    print("3. Update documentation to reflect the actual feature set")
    print("4. Consider whether percentile gap features should be added back to the correlation matrix creation process")

def main():
    db_path = "../database/database/cycling_races.db"
    
    try:
        investigate_blob_structure(db_path)
    except Exception as e:
        print(f"❌ Error during investigation: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()