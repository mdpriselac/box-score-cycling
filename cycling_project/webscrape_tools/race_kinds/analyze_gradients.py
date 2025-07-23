"""
Analyze gradient patterns to evaluate discriminative power
"""

import sqlite3
import json
import numpy as np
from pathlib import Path
from collections import defaultdict
import os
from dotenv import load_dotenv


def get_db_path():
    """Get database path from environment or hardcoded"""
    load_dotenv()
    db_path = os.getenv('DB_PATH')
    if db_path and os.path.exists(db_path):
        return db_path
    return "~/Documents/Cycling Project/cycling_project/webscrape_tools/database/database/cycling_races.db"


def analyze_variance_patterns():
    """Analyze variance gradient patterns across race types"""
    conn = sqlite3.connect(get_db_path())
    
    # Get variance gradients grouped by race characteristics
    query = """
    SELECT 
        rfg.competition_id,
        rfg.competition_name,
        rfg.race_category,
        rfg.total_finishers,
        rfg.variance_normalized_values,
        rfg.variance_normalized_slope,
        rfg.variance_normalized_volatility,
        rfg.variance_normalized_monotonicity,
        rf100.competition_type
    FROM race_feature_gradients rfg
    JOIN race_features_100 rf100 ON rfg.competition_id = rf100.competition_id
    """
    
    cursor = conn.execute(query)
    data = cursor.fetchall()
    
    # Group by competition type
    by_type = defaultdict(list)
    for row in data:
        comp_type = row[8] if row[8] else 'Unknown'
        by_type[comp_type].append({
            'name': row[1],
            'category': row[2],
            'finishers': row[3],
            'values': json.loads(row[4]),
            'slope': row[5],
            'volatility': row[6],
            'monotonicity': row[7]
        })
    
    # Analyze patterns
    print("=== Variance Gradient Analysis ===\n")
    
    for comp_type, races in by_type.items():
        print(f"\n{comp_type} ({len(races)} races):")
        
        slopes = [r['slope'] for r in races]
        volatilities = [r['volatility'] for r in races]
        monotonicities = [r['monotonicity'] for r in races]
        
        print(f"  Slope: mean={np.mean(slopes):.2e}, std={np.std(slopes):.2e}")
        print(f"  Volatility: mean={np.mean(volatilities):.2e}, std={np.std(volatilities):.2e}")
        print(f"  Monotonicity: mean={np.mean(monotonicities):.3f}, std={np.std(monotonicities):.3f}")
        
        # Look at variance evolution patterns
        if races:
            # Sample variance patterns
            sample_race = races[0]
            values = sample_race['values']
            print(f"  Sample variance evolution ({sample_race['name']}):")
            print(f"    Start (100%): {values[-1]:.2e}")
            print(f"    Mid (50%): {values[len(values)//2]:.2e}")
            print(f"    End (10%): {values[0]:.2e}")
            print(f"    Ratio (end/start): {values[0]/values[-1] if values[-1] > 0 else 'N/A':.3f}")
    
    conn.close()


def find_true_selectivity_points():
    """Find selectivity points using adaptive thresholds"""
    conn = sqlite3.connect(get_db_path())
    
    query = """
    SELECT 
        competition_id,
        competition_name,
        race_category,
        variance_normalized_values,
        valid_percentiles
    FROM race_feature_gradients
    """
    
    cursor = conn.execute(query)
    data = cursor.fetchall()
    
    print("\n=== Adaptive Selectivity Point Analysis ===\n")
    
    selectivity_points = []
    
    for row in data:
        values = json.loads(row[3])
        percentiles = json.loads(row[4])
        
        if len(values) < 3:
            continue
        
        # Find where variance drops significantly (relative to max variance)
        max_var = max(values)
        threshold = max_var * 0.1  # 10% of max variance
        
        selectivity_point = None
        for i, (p, v) in enumerate(zip(percentiles, values)):
            if v < threshold:
                selectivity_point = p
                break
        
        if selectivity_point is None:
            selectivity_point = percentiles[0]  # Lowest percentile
        
        selectivity_points.append({
            'id': row[0],
            'name': row[1],
            'category': row[2],
            'point': selectivity_point
        })
    
    # Analyze distribution
    points = [sp['point'] for sp in selectivity_points]
    
    print(f"Selectivity Point Distribution:")
    print(f"  Mean: {np.mean(points):.1f}")
    print(f"  Std: {np.std(points):.1f}")
    print(f"  Min: {min(points)}")
    print(f"  Max: {max(points)}")
    
    # Count by ranges
    ranges = [(10, 30), (35, 60), (65, 100)]
    for low, high in ranges:
        count = sum(1 for p in points if low <= p <= high)
        print(f"  {low}-{high}%: {count} races ({count/len(points)*100:.1f}%)")
    
    conn.close()
    
    return selectivity_points


def analyze_feature_correlations():
    """Analyze how different gradient features correlate"""
    conn = sqlite3.connect(get_db_path())
    
    query = """
    SELECT 
        variance_normalized_slope,
        variance_normalized_volatility,
        variance_normalized_monotonicity,
        gini_coefficient_slope,
        gini_coefficient_volatility,
        gini_coefficient_monotonicity,
        clumpiness_score_slope,
        clumpiness_score_volatility,
        clumpiness_score_monotonicity,
        selection_metric_slope,
        selection_metric_volatility,
        selection_metric_monotonicity
    FROM race_feature_gradients
    WHERE variance_normalized_slope IS NOT NULL
    """
    
    cursor = conn.execute(query)
    data = np.array(cursor.fetchall())
    
    if len(data) == 0:
        print("No data available for correlation analysis")
        return
    
    # Calculate correlation matrix
    corr = np.corrcoef(data.T)
    
    feature_names = [
        'var_slope', 'var_volatility', 'var_monotonicity',
        'gini_slope', 'gini_volatility', 'gini_monotonicity',
        'clump_slope', 'clump_volatility', 'clump_monotonicity',
        'select_slope', 'select_volatility', 'select_monotonicity'
    ]
    
    print("\n=== Feature Correlation Analysis ===\n")
    print("High correlations (|r| > 0.7):")
    
    for i in range(len(feature_names)):
        for j in range(i+1, len(feature_names)):
            if abs(corr[i, j]) > 0.7:
                print(f"  {feature_names[i]} vs {feature_names[j]}: {corr[i, j]:.3f}")
    
    conn.close()


def analyze_gradient_stability():
    """Analyze where gradients become unstable"""
    conn = sqlite3.connect(get_db_path())
    
    query = """
    SELECT 
        competition_name,
        variance_zero_percentile,
        kurtosis_null_percentile,
        lowest_valid_percentile,
        percentile_coverage_ratio
    FROM race_feature_gradients
    ORDER BY total_finishers DESC
    """
    
    cursor = conn.execute(query)
    data = cursor.fetchall()
    
    print("\n=== Gradient Stability Analysis ===\n")
    
    var_zero_points = [row[1] for row in data if row[1] is not None]
    kurt_null_points = [row[2] for row in data if row[2] is not None]
    
    if var_zero_points:
        print(f"Variance goes to zero:")
        print(f"  Occurrences: {len(var_zero_points)}/{len(data)} races")
        print(f"  Average percentile: {np.mean(var_zero_points):.1f}")
        print(f"  Most common: {max(set(var_zero_points), key=var_zero_points.count)}")
    
    if kurt_null_points:
        print(f"\nKurtosis becomes null:")
        print(f"  Occurrences: {len(kurt_null_points)}/{len(data)} races")
        print(f"  Average percentile: {np.mean(kurt_null_points):.1f}")
        print(f"  Most common: {max(set(kurt_null_points), key=kurt_null_points.count)}")
    
    # Coverage analysis
    coverages = [row[4] for row in data]
    print(f"\nPercentile coverage:")
    print(f"  Mean: {np.mean(coverages):.1%}")
    print(f"  All have 100% coverage: {all(c == 1.0 for c in coverages)}")
    
    conn.close()


def generate_summary_report():
    """Generate a summary report of gradient effectiveness"""
    conn = sqlite3.connect(get_db_path())
    
    # Get overall statistics
    query = """
    SELECT 
        COUNT(*) as total,
        COUNT(DISTINCT rfg.race_category) as categories,
        COUNT(DISTINCT rf100.competition_type) as types,
        AVG(rfg.feature_stability_score) as avg_stability,
        AVG(rfg.racing_intensity_score) as avg_intensity
    FROM race_feature_gradients rfg
    JOIN race_features_100 rf100 ON rfg.competition_id = rf100.competition_id
    """
    
    cursor = conn.execute(query)
    stats = cursor.fetchone()
    
    print("\n" + "="*60)
    print("GRADIENT FEATURE EFFECTIVENESS REPORT")
    print("="*60)
    
    print(f"\nDataset Overview:")
    print(f"  Total competitions analyzed: {stats[0]}")
    print(f"  Race categories: {stats[1]}")
    print(f"  Competition types: {stats[2]}")
    print(f"  Average feature stability: {stats[3]:.3f}")
    print(f"  Average racing intensity: {stats[4]:.3f}")
    
    # Key findings
    print("\nKey Findings:")
    print("1. Variance values are extremely small (1e-05 to 1e-06 range)")
    print("2. Current selectivity threshold (0.05) is too high for normalized data")
    print("3. All races show 'early' selectivity due to threshold issue")
    print("4. Gradient patterns show promise for race discrimination")
    print("5. Need adaptive thresholding based on race-specific variance ranges")
    
    print("\nRecommendations:")
    print("1. Implement adaptive selectivity thresholds (e.g., 10% of max variance)")
    print("2. Focus on relative variance changes rather than absolute thresholds")
    print("3. Use gradient monotonicity as key discriminator")
    print("4. Combine multiple gradient features for classification")
    print("5. Process more competitions to validate patterns")
    
    conn.close()


def main():
    """Run all analyses"""
    print("Running gradient analysis...\n")
    
    analyze_variance_patterns()
    find_true_selectivity_points()
    analyze_feature_correlations()
    analyze_gradient_stability()
    generate_summary_report()


if __name__ == "__main__":
    main()