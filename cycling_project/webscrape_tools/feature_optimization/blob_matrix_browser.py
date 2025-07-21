#!/usr/bin/env python3
"""
Interactive browser tool for examining correlation blob matrices.
"""

import sqlite3
import numpy as np
import gzip
import json
from pathlib import Path
from correlation_feature_analysis import config

def format_matrix_table(matrix: np.ndarray, feature_names: list, percentiles: list) -> str:
    """Format the matrix as a readable table with proper alignment"""
    
    # Header row with feature names (truncated for display)
    max_feature_len = 20
    truncated_features = [f[:max_feature_len] for f in feature_names]
    
    lines = []
    
    # Build header
    header = "Percentile".ljust(10)
    for feature in truncated_features:
        header += f"{feature:>8}"
    lines.append(header)
    
    # Add separator line
    separator = "-" * 10
    for _ in truncated_features:
        separator += "-" * 8
    lines.append(separator)
    
    # Add data rows
    for i, percentile in enumerate(percentiles):
        row = f"{percentile}%".ljust(10)
        for j, value in enumerate(matrix[i]):
            if np.isnan(value):
                row += "     NaN"
            else:
                row += f"{value:8.3f}"
        lines.append(row)
    
    return "\n".join(lines)

def get_high_quality_entries(db_path: str, correlation_type: str, min_races: int = 50) -> list:
    """Get entries with high data quality for browsing"""
    
    conn = sqlite3.connect(db_path)
    
    cursor = conn.execute("""
        SELECT 
            dq.rider_result_id,
            dq.data_completeness,
            dq.races_with_features,
            dq.percentile_availability,
            rcb.race_count,
            rr.rider_id,
            rr.competition_id
        FROM correlation_data_quality dq
        JOIN rider_correlations_blob rcb 
            ON dq.rider_result_id = rcb.rider_result_id 
            AND dq.correlation_type = rcb.correlation_type
        JOIN rider_results rr ON dq.rider_result_id = rr.id
        WHERE dq.correlation_type = ?
            AND dq.percentile_availability = '[1, 1, 1, 1, 1, 1, 1, 1]'  -- All percentiles available
            AND dq.races_with_features >= ?
        ORDER BY dq.races_with_features DESC, dq.data_completeness DESC
    """, [correlation_type, min_races])
    
    entries = cursor.fetchall()
    conn.close()
    
    return entries

def load_and_display_matrix(db_path: str, rider_result_id: int, correlation_type: str) -> bool:
    """Load and display a specific correlation matrix"""
    
    conn = sqlite3.connect(db_path)
    
    cursor = conn.execute("""
        SELECT correlation_matrix
        FROM rider_correlations_blob
        WHERE rider_result_id = ? AND correlation_type = ?
    """, [rider_result_id, correlation_type])
    
    result = cursor.fetchone()
    if not result:
        print(f"❌ Matrix not found for rider_result_id {rider_result_id}")
        conn.close()
        return False
    
    blob = result[0]
    conn.close()
    
    try:
        # Decompress and reshape
        decompressed = gzip.decompress(blob)
        matrix = np.frombuffer(decompressed, dtype=np.float64)
        matrix = matrix.reshape(8, 37)  # 8 percentiles x 37 features
        
        percentiles = [30, 40, 50, 60, 70, 80, 90, 100]
        
        print(f"\n{'='*80}")
        print(f"CORRELATION MATRIX: Rider Result ID {rider_result_id}")
        print(f"Correlation Type: {correlation_type}")
        print(f"Matrix Shape: {matrix.shape}")
        print(f"{'='*80}")
        
        # Show data availability summary first
        print(f"\n📊 DATA AVAILABILITY SUMMARY:")
        for i, percentile in enumerate(percentiles):
            row_data = matrix[i, :]
            non_nan_count = np.sum(~np.isnan(row_data))
            nan_count = np.sum(np.isnan(row_data))
            print(f"  {percentile:3d}%: {non_nan_count:2d} valid, {nan_count:2d} NaN out of {len(config.RACE_FEATURES)} features")
        
        # Show the full matrix table
        print(f"\n🔍 FULL CORRELATION MATRIX:")
        table = format_matrix_table(matrix, config.RACE_FEATURES, percentiles)
        print(table)
        
        # Show which features have NaN vs valid data
        print(f"\n🔢 FEATURE STATUS ANALYSIS:")
        
        # Check each feature across all percentiles
        always_nan = []
        sometimes_nan = []
        never_nan = []
        
        for j, feature in enumerate(config.RACE_FEATURES):
            feature_column = matrix[:, j]
            nan_count = np.sum(np.isnan(feature_column))
            
            if nan_count == 8:  # All percentiles are NaN
                always_nan.append(feature)
            elif nan_count > 0:  # Some percentiles are NaN
                sometimes_nan.append(feature)
            else:  # No NaNs
                never_nan.append(feature)
        
        print(f"\n✅ Features with valid data across all percentiles ({len(never_nan)}):")
        for feature in never_nan:
            print(f"   📊 {feature}")
        
        if sometimes_nan:
            print(f"\n⚠️  Features with partial data ({len(sometimes_nan)}):")
            for feature in sometimes_nan:
                feature_column = matrix[:, config.RACE_FEATURES.index(feature)]
                valid_percentiles = [percentiles[i] for i in range(8) if not np.isnan(feature_column[i])]
                print(f"   🔶 {feature}: valid at {valid_percentiles}")
        
        print(f"\n❌ Features that are always NaN ({len(always_nan)}):")
        for feature in always_nan:
            marker = "🔢" if any(char.isdigit() for char in feature.split('_')[0]) else "📊"
            print(f"   {marker} {feature}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error processing matrix: {e}")
        return False

def main():
    db_path = "../database/database/cycling_races.db"
    
    print("🔍 CORRELATION MATRIX BROWSER")
    print("=" * 60)
    
    # Get available correlation types
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("""
        SELECT DISTINCT correlation_type, COUNT(*) as count 
        FROM rider_correlations_blob 
        GROUP BY correlation_type
    """)
    correlation_types = cursor.fetchall()
    conn.close()
    
    if not correlation_types:
        print("❌ No correlation data found!")
        return
    
    print("Available correlation types:")
    for i, (corr_type, count) in enumerate(correlation_types):
        print(f"  {i+1}. {corr_type}: {count:,} entries")
    
    # Select correlation type
    while True:
        try:
            choice = input(f"\nSelect correlation type (1-{len(correlation_types)}): ").strip()
            if not choice:
                print("Exiting...")
                return
            
            type_idx = int(choice) - 1
            if 0 <= type_idx < len(correlation_types):
                selected_type = correlation_types[type_idx][0]
                break
            else:
                print(f"Please enter a number between 1 and {len(correlation_types)}")
        except ValueError:
            print("Please enter a valid number or press Enter to exit")
    
    print(f"\n📊 Selected correlation type: {selected_type}")
    
    # Get high-quality entries
    min_races = 50
    print(f"\nFinding entries with full percentile coverage and ≥{min_races} races...")
    
    entries = get_high_quality_entries(db_path, selected_type, min_races)
    
    if not entries:
        print(f"❌ No high-quality entries found with ≥{min_races} races!")
        # Try with lower threshold
        min_races = 20
        print(f"Trying with ≥{min_races} races...")
        entries = get_high_quality_entries(db_path, selected_type, min_races)
        
        if not entries:
            print("❌ No suitable entries found!")
            return
    
    print(f"\n✅ Found {len(entries)} high-quality entries:")
    print(f"{'#':<3} {'Rider ID':<8} {'Result ID':<8} {'Races':<6} {'Completeness':<12} {'Competition':<12}")
    print("-" * 60)
    
    # Show first 20 entries
    display_entries = entries[:20]
    for i, (rider_result_id, data_completeness, races_with_features, percentile_availability, race_count, rider_id, competition_id) in enumerate(display_entries):
        print(f"{i+1:<3} {rider_id:<8} {rider_result_id:<8} {races_with_features:<6} {data_completeness:.1%}        {competition_id:<12}")
    
    if len(entries) > 20:
        print(f"... and {len(entries) - 20} more entries")
    
    # Interactive selection
    while True:
        try:
            choice = input(f"\nSelect entry to examine (1-{len(display_entries)}) or 'q' to quit: ").strip().lower()
            
            if choice in ['q', 'quit', '']:
                print("Exiting...")
                break
            
            entry_idx = int(choice) - 1
            if 0 <= entry_idx < len(display_entries):
                selected_entry = display_entries[entry_idx]
                rider_result_id = selected_entry[0]
                
                print(f"\n🔍 Loading matrix for rider_result_id {rider_result_id}...")
                success = load_and_display_matrix(db_path, rider_result_id, selected_type)
                
                if success:
                    input("\nPress Enter to continue browsing...")
                
            else:
                print(f"Please enter a number between 1 and {len(display_entries)}")
                
        except ValueError:
            print("Please enter a valid number or 'q' to quit")
        except KeyboardInterrupt:
            print("\nExiting...")
            break

if __name__ == "__main__":
    main()