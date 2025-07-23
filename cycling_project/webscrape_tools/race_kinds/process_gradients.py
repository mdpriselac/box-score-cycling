"""
Process competitions to generate gradient data

This script processes competitions to calculate and store gradient features
"""

import sqlite3
import json
import sys
import os
from pathlib import Path
from gradient_calculator import GradientCalculator
import numpy as np
from typing import List, Dict, Any
try:
    from dotenv import load_dotenv
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False


def find_database():
    """Find the SQLite database file"""
    # Try to load environment variables if dotenv is available
    if HAS_DOTENV:
        load_dotenv()
        db_path = os.getenv('DB_PATH')
        if db_path and os.path.exists(db_path):
            return db_path
    
    # Try hardcoded path
    db_path = "~/Documents/Cycling Project/cycling_project/webscrape_tools/database/database/cycling_races.db"
    if os.path.exists(db_path):
        return db_path
    
    # Fallback to searching for .db files
    db_files = list(Path('.').glob('*.db'))
    if not db_files:
        raise FileNotFoundError("No database file found")
    return str(db_files[0])


def get_sample_competitions(db_path: str, limit: int = 100) -> List[int]:
    """Get sample competitions with good percentile coverage"""
    conn = sqlite3.connect(db_path)
    
    query = """
    WITH percentile_coverage AS (
        SELECT 
            rf100.competition_id,
            rf100.race_category,
            rf100.total_finishers,
            CASE WHEN rf10.id IS NOT NULL THEN 1 ELSE 0 END +
            CASE WHEN rf20.id IS NOT NULL THEN 1 ELSE 0 END +
            CASE WHEN rf30.id IS NOT NULL THEN 1 ELSE 0 END +
            CASE WHEN rf40.id IS NOT NULL THEN 1 ELSE 0 END +
            CASE WHEN rf50.id IS NOT NULL THEN 1 ELSE 0 END +
            CASE WHEN rf60.id IS NOT NULL THEN 1 ELSE 0 END +
            CASE WHEN rf70.id IS NOT NULL THEN 1 ELSE 0 END +
            CASE WHEN rf80.id IS NOT NULL THEN 1 ELSE 0 END +
            CASE WHEN rf90.id IS NOT NULL THEN 1 ELSE 0 END as coverage_count
        FROM race_features_100 rf100
        LEFT JOIN race_features_10 rf10 ON rf100.competition_id = rf10.competition_id
        LEFT JOIN race_features_20 rf20 ON rf100.competition_id = rf20.competition_id
        LEFT JOIN race_features_30 rf30 ON rf100.competition_id = rf30.competition_id
        LEFT JOIN race_features_40 rf40 ON rf100.competition_id = rf40.competition_id
        LEFT JOIN race_features_50 rf50 ON rf100.competition_id = rf50.competition_id
        LEFT JOIN race_features_60 rf60 ON rf100.competition_id = rf60.competition_id
        LEFT JOIN race_features_70 rf70 ON rf100.competition_id = rf70.competition_id
        LEFT JOIN race_features_80 rf80 ON rf100.competition_id = rf80.competition_id
        LEFT JOIN race_features_90 rf90 ON rf100.competition_id = rf90.competition_id
    )
    SELECT 
        competition_id,
        race_category,
        coverage_count
    FROM percentile_coverage
    WHERE race_category IN ('wt', 'pro', 'd1')
    ORDER BY 
        CASE race_category 
            WHEN 'wt' THEN 1 
            WHEN 'pro' THEN 2 
            ELSE 3 
        END,
        coverage_count DESC,
        total_finishers DESC
    LIMIT ?
    """
    
    cursor = conn.execute(query, (limit,))
    competitions = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    return competitions


def enhanced_gradient_calculation(calculator: GradientCalculator, 
                                competition_id: int) -> Dict[str, Any]:
    """Enhanced gradient calculation with all features"""
    conn = sqlite3.connect(calculator.db_path)
    conn.row_factory = sqlite3.Row
    
    try:
        # Get metadata
        metadata_query = """
        SELECT 
            competition_name,
            competition_type,
            race_id,
            race_name,
            race_category,
            race_year,
            race_date,
            total_finishers
        FROM race_features_100
        WHERE competition_id = ?
        """
        cursor = conn.execute(metadata_query, (competition_id,))
        metadata = dict(cursor.fetchone())
        
        # Collect all feature data
        feature_data = {}
        percentiles = [10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100]
        
        for percentile in percentiles:
            table_name = f'race_features_{percentile}'
            
            query = f"""
            SELECT *
            FROM {table_name}
            WHERE competition_id = ?
            """
            
            try:
                cursor = conn.execute(query, (competition_id,))
                row = cursor.fetchone()
                if row:
                    feature_data[percentile] = dict(row)
            except sqlite3.OperationalError:
                continue
        
        if len(feature_data) < 3:
            return None
        
        valid_percentiles = sorted(feature_data.keys())
        missing_percentiles = [p for p in percentiles if p not in valid_percentiles]
        
        # Initialize result
        result = {
            'competition_id': competition_id,
            'valid_percentiles': json.dumps(valid_percentiles),
            'missing_percentiles': json.dumps(missing_percentiles),
            'percentile_coverage_ratio': len(valid_percentiles) / len(percentiles),
            'lowest_valid_percentile': min(valid_percentiles),
            **metadata
        }
        
        # Process each feature type
        features_to_process = [
            ('variance_normalized', 'variance_normalized'),
            ('variance_absolute', 'variance_absolute'),
            ('skewness_normalized', 'skewness_normalized'),
            ('skewness_absolute', 'skewness_absolute'),
            ('kurtosis_normalized', 'kurtosis_normalized'),
            ('kurtosis_absolute', 'kurtosis_absolute'),
            ('gini_coefficient', 'gini_coefficient'),
            ('clumpiness_score', 'clumpiness_score'),
            ('selection_metric', 'selection_metric'),
            ('biggest_group_metric', 'biggest_group_metric')
        ]
        
        all_gradients = {}
        
        for db_field, gradient_name in features_to_process:
            values = []
            for p in percentiles:
                if p in feature_data:
                    values.append(feature_data[p].get(db_field))
                else:
                    values.append(None)
            
            # Handle kurtosis/skewness with imputation
            if 'kurtosis' in gradient_name or 'skewness' in gradient_name:
                imputed_values, imputed_flags = calculator.impute_missing_values(
                    values, gradient_name, competition_id
                )
                gradient = calculator.calculate_gradient_metrics(
                    imputed_values, valid_percentiles
                )
                if gradient:
                    gradient.imputed_flags = imputed_flags
            else:
                gradient = calculator.calculate_gradient_metrics(
                    values, valid_percentiles
                )
            
            if gradient:
                all_gradients[gradient_name] = gradient
                
                # Store in result
                result[f'{gradient_name}_values'] = json.dumps(gradient.values)
                result[f'{gradient_name}_slope'] = gradient.slope
                result[f'{gradient_name}_volatility'] = gradient.volatility
                result[f'{gradient_name}_monotonicity'] = gradient.monotonicity
                
                # Only add imputed_flags for kurtosis/skewness features
                if hasattr(gradient, 'imputed_flags') and ('kurtosis' in gradient_name or 'skewness' in gradient_name):
                    result[f'{gradient_name}_imputed_flags'] = json.dumps(gradient.imputed_flags)
        
        # Process Nth percentile gaps (only valid above 20th percentile)
        nth_percentile_features = [
            ('5th_percentile_gap', 'nth_percentile_gap_5'),
            ('25th_percentile_gap', 'nth_percentile_gap_25'),
            ('50th_percentile_gap', 'nth_percentile_gap_50')
        ]
        
        for db_field, gradient_name in nth_percentile_features:
            values = []
            valid_percs = []
            
            for p in percentiles:
                if p >= 25 and p in feature_data:  # Only use percentiles >= 25
                    values.append(feature_data[p].get(db_field))
                    valid_percs.append(p)
            
            if len(values) >= 3:
                gradient = calculator.calculate_gradient_metrics(values, valid_percs)
                if gradient:
                    all_gradients[gradient_name] = gradient
                    result[f'{gradient_name}_values'] = json.dumps(gradient.values)
                    result[f'{gradient_name}_slope'] = gradient.slope
                    result[f'{gradient_name}_volatility'] = gradient.volatility
                    result[f'{gradient_name}_monotonicity'] = gradient.monotonicity
        
        # Calculate selectivity point and metrics
        if 'variance_normalized' in all_gradients:
            var_gradient = all_gradients['variance_normalized']
            selectivity_point = calculator.calculate_selectivity_point(
                var_gradient.values, valid_percentiles
            )
            result['selectivity_point'] = selectivity_point
            
            selectivity_metrics = calculator.calculate_selectivity_metrics(
                var_gradient.values, valid_percentiles, selectivity_point
            )
            result.update(selectivity_metrics)
            
            # Classify selectivity type
            if selectivity_point is None:
                result['selectivity_type'] = 'NONE'
            elif selectivity_point <= 30:
                result['selectivity_type'] = 'EARLY'
            elif selectivity_point <= 60:
                result['selectivity_type'] = 'PROGRESSIVE'
            else:
                result['selectivity_type'] = 'LATE'
        
        # Calculate gradient-derived features
        derived = calculator.calculate_gradient_derived_features(
            all_gradients, result.get('selectivity_point')
        )
        result.update(derived)
        
        # Find data quality indicators - counting DOWN from 100
        variance_zero_at = None
        kurtosis_null_at = None
        
        # Check from highest to lowest percentile
        for p in sorted(valid_percentiles, reverse=True):
            if feature_data[p].get('variance_normalized') == 0:
                variance_zero_at = p  # Keep updating to find the highest percentile where this occurs
            if feature_data[p].get('kurtosis_normalized') is None:
                kurtosis_null_at = p  # Keep updating to find the highest percentile where this occurs
        
        result['variance_zero_percentile'] = variance_zero_at
        result['kurtosis_null_percentile'] = kurtosis_null_at
        
        return result
        
    finally:
        conn.close()


def insert_gradient_data(db_path: str, gradient_data: Dict[str, Any]):
    """Insert gradient data into the database"""
    conn = sqlite3.connect(db_path)
    
    # Build column names and values
    columns = []
    values = []
    
    for key, value in gradient_data.items():
        columns.append(key)
        values.append(value)
    
    # Create insert query
    placeholders = ','.join(['?' for _ in values])
    column_str = ','.join(columns)
    
    query = f"""
    INSERT OR REPLACE INTO race_feature_gradients ({column_str})
    VALUES ({placeholders})
    """
    
    conn.execute(query, values)
    conn.commit()
    conn.close()


def main():
    """Process sample competitions"""
    try:
        db_path = find_database()
        print(f"Using database: {db_path}")
    except Exception as e:
        print(f"Error finding database: {e}")
        return
    
    calculator = GradientCalculator(db_path)
    
    # Get sample competitions
    print("Getting sample competitions...")
    competitions = get_sample_competitions(db_path, limit=50)
    print(f"Found {len(competitions)} competitions to process")
    
    # Process each competition
    success_count = 0
    for i, comp_id in enumerate(competitions):
        try:
            print(f"Processing competition {i+1}/{len(competitions)}: {comp_id}", end='... ')
            
            gradient_data = enhanced_gradient_calculation(calculator, comp_id)
            
            if gradient_data:
                insert_gradient_data(db_path, gradient_data)
                success_count += 1
                print("✓")
            else:
                print("✗ (insufficient data)")
                
        except Exception as e:
            print(f"✗ (error: {str(e)})")
    
    print(f"\nProcessed {success_count}/{len(competitions)} competitions successfully")
    
    # Show summary statistics
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("""
        SELECT 
            COUNT(*) as total,
            AVG(percentile_coverage_ratio) as avg_coverage,
            COUNT(CASE WHEN selectivity_point IS NOT NULL THEN 1 END) as with_selectivity,
            COUNT(DISTINCT race_category) as categories
        FROM race_feature_gradients
    """)
    
    stats = cursor.fetchone()
    print(f"\nGradient Table Summary:")
    print(f"  Total records: {stats[0]}")
    if stats[0] > 0:
        print(f"  Average coverage: {stats[1]:.2%}")
        print(f"  With selectivity point: {stats[2]}")
        print(f"  Categories: {stats[3]}")
    
    conn.close()


if __name__ == "__main__":
    main()