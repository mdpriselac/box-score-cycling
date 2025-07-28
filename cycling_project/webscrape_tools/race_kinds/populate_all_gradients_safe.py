"""
Populate the entire race_feature_gradients table using a SQLite-safe approach
- Single database connection for writes
- Multi-threading for computation only
- Batch inserts to minimize WAL growth
- WAL checkpointing to manage file size
"""

import sqlite3
import json
import sys
import os
from pathlib import Path
from gradient_calculator import GradientCalculator
import numpy as np
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from queue import Queue
import time

try:
    from dotenv import load_dotenv
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False


def find_database():
    """Find the SQLite database file"""
    if HAS_DOTENV:
        load_dotenv()
        db_path = os.getenv('DB_PATH')
        if db_path and os.path.exists(db_path):
            return db_path
    
    db_path = "~/Documents/Cycling Project/cycling_project/webscrape_tools/database/database/cycling_races.db"
    if os.path.exists(db_path):
        return db_path
    
    db_files = list(Path('.').glob('*.db'))
    if not db_files:
        raise FileNotFoundError("No database file found")
    return str(db_files[0])


def get_all_unprocessed_competitions(db_path: str) -> List[int]:
    """Get all unprocessed competitions"""
    conn = sqlite3.connect(db_path)
    
    query = """
    SELECT rf100.competition_id
    FROM race_features_100 rf100
    LEFT JOIN race_feature_gradients rfg ON rf100.competition_id = rfg.competition_id
    WHERE rfg.competition_id IS NULL  -- Not yet processed
    ORDER BY rf100.total_finishers DESC  -- Process larger races first
    """
    
    cursor = conn.execute(query)
    competitions = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    return competitions


def calculate_gradients_for_competition(competition_id: int, db_path: str) -> Dict[str, Any]:
    """Calculate gradients for a single competition - uses separate read-only connection"""
    calculator = GradientCalculator(db_path)
    conn = sqlite3.connect(db_path)
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
        row = cursor.fetchone()
        if not row:
            return None
        metadata = dict(row)
        
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
            'highest_null_percentile': max([p for p in missing_percentiles]) if missing_percentiles else None,
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
        
        for db_field, gradient_name in features_to_process:
            values = []
            for p in percentiles:
                if p in feature_data:
                    values.append(feature_data[p].get(db_field))
                else:
                    values.append(None)
            
            # Handle kurtosis with imputation
            if 'kurtosis' in gradient_name:
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
                # Store in result
                result[f'{gradient_name}_values'] = json.dumps(gradient.values)
                result[f'{gradient_name}_slope'] = gradient.slope
                result[f'{gradient_name}_volatility'] = gradient.volatility
                result[f'{gradient_name}_monotonicity'] = gradient.monotonicity
                result[f'{gradient_name}_directional_changes'] = gradient.directional_changes
                
                # Only add imputed_flags for kurtosis features
                if hasattr(gradient, 'imputed_flags') and 'kurtosis' in gradient_name:
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
                    result[f'{gradient_name}_values'] = json.dumps(gradient.values)
                    result[f'{gradient_name}_slope'] = gradient.slope
                    result[f'{gradient_name}_volatility'] = gradient.volatility
                    result[f'{gradient_name}_monotonicity'] = gradient.monotonicity
                    result[f'{gradient_name}_directional_changes'] = gradient.directional_changes
        
        # Find data quality indicators - counting DOWN from 100
        variance_zero_at = None
        kurtosis_null_at = None
        
        # Check from highest to lowest percentile for variance zero
        for p in sorted(valid_percentiles, reverse=True):
            if feature_data[p].get('variance_normalized') == 0:
                variance_zero_at = p  # Keep updating to find the highest percentile where this occurs
        
        # For kurtosis null, check the imputed flags if they exist
        kurtosis_gradient_name = None
        for name in ['kurtosis_normalized', 'kurtosis_absolute']:
            if f'{name}_imputed_flags' in result:
                kurtosis_gradient_name = name
                break
        
        if kurtosis_gradient_name:
            # Parse the imputed flags to find highest percentile where kurtosis was null
            imputed_flags_json = result[f'{kurtosis_gradient_name}_imputed_flags']
            imputed_flags = json.loads(imputed_flags_json)
            
            # Check percentiles from highest to lowest to find highest percentile where flag is true
            for i, percentile in enumerate(reversed(percentiles)):
                flag_idx = len(percentiles) - 1 - i  # Map back to original index
                if flag_idx < len(imputed_flags) and imputed_flags[flag_idx]:  # If this percentile was imputed (originally null)
                    if percentile in valid_percentiles:
                        kurtosis_null_at = percentile
                        break
        
        result['variance_zero_percentile'] = variance_zero_at
        result['kurtosis_null_percentile'] = kurtosis_null_at
        
        return result
        
    finally:
        conn.close()


class SafeDatabaseWriter:
    """Thread-safe database writer with WAL management"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.lock = threading.Lock()
        self.batch_count = 0
        
        # Configure for better performance
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA cache_size=10000")
        self.conn.execute("PRAGMA temp_store=memory")
        
    def insert_batch(self, gradient_data_list: List[Dict[str, Any]]):
        """Insert batch with thread safety and WAL management"""
        if not gradient_data_list:
            return
        
        with self.lock:
            try:
                # Get column names from first record
                first_record = gradient_data_list[0]
                columns = list(first_record.keys())
                placeholders = ','.join(['?' for _ in columns])
                column_str = ','.join(columns)
                
                query = f"""
                INSERT OR REPLACE INTO race_feature_gradients ({column_str})
                VALUES ({placeholders})
                """
                
                # Prepare all data
                data_rows = []
                for gradient_data in gradient_data_list:
                    row = [gradient_data.get(col) for col in columns]
                    data_rows.append(row)
                
                self.conn.executemany(query, data_rows)
                self.conn.commit()
                
                self.batch_count += 1
                
                # Checkpoint WAL every 20 batches to prevent it from growing too large
                if self.batch_count % 20 == 0:
                    self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                    
            except Exception as e:
                self.conn.rollback()
                raise e
    
    def close(self):
        """Close connection with final checkpoint"""
        with self.lock:
            self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            self.conn.close()


def main():
    """Process all competitions using ThreadPoolExecutor with single DB writer"""
    try:
        db_path = find_database()
        print(f"Using database: {db_path}")
    except Exception as e:
        print(f"Error finding database: {e}")
        return
    
    # Get all unprocessed competitions
    print("Getting unprocessed competitions...")
    competitions = get_all_unprocessed_competitions(db_path)
    print(f"Found {len(competitions)} competitions to process")
    
    if not competitions:
        print("No competitions to process!")
        return
    
    # Initialize database writer
    db_writer = SafeDatabaseWriter(db_path)
    
    # Use ThreadPoolExecutor for computation
    max_workers = min(8, len(competitions))  # More conservative thread count
    batch_size = 25  # Smaller batches for more frequent checkpointing
    
    print(f"Starting processing with {max_workers} workers, batch size {batch_size}...")
    
    start_time = time.time()
    success_count = 0
    error_count = 0
    batch_data = []
    
    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all jobs
            future_to_comp = {
                executor.submit(calculate_gradients_for_competition, comp_id, db_path): comp_id 
                for comp_id in competitions
            }
            
            # Process completed jobs
            for i, future in enumerate(as_completed(future_to_comp)):
                comp_id = future_to_comp[future]
                
                try:
                    gradient_data = future.result()
                    
                    if gradient_data:
                        batch_data.append(gradient_data)
                        success_count += 1
                        
                        # Insert in batches
                        if len(batch_data) >= batch_size:
                            db_writer.insert_batch(batch_data)
                            batch_data = []
                            
                    else:
                        error_count += 1
                        if error_count <= 10:
                            print(f"Insufficient data for competition {comp_id}")
                            
                except Exception as e:
                    error_count += 1
                    if error_count <= 10:
                        print(f"Error processing {comp_id}: {str(e)}")
                
                # Progress update
                if (i + 1) % 100 == 0 or i == len(competitions) - 1:
                    elapsed = time.time() - start_time
                    rate = (i + 1) / elapsed
                    remaining = (len(competitions) - i - 1) / rate if rate > 0 else 0
                    print(f"Progress: {i+1}/{len(competitions)} ({(i+1)/len(competitions)*100:.1f}%) - "
                          f"Success: {success_count}, Errors: {error_count}, "
                          f"Rate: {rate:.1f}/sec, ETA: {remaining/60:.1f}min")
        
        # Insert remaining batch
        if batch_data:
            db_writer.insert_batch(batch_data)
        
    finally:
        # Clean shutdown
        db_writer.close()
    
    total_time = time.time() - start_time
    print(f"\nCompleted in {total_time/60:.1f} minutes")
    print(f"Successfully processed: {success_count}/{len(competitions)} competitions")
    print(f"Errors: {error_count}")
    
    # Show final statistics
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(DISTINCT race_category) as categories,
            AVG(percentile_coverage_ratio) as avg_coverage,
            COUNT(CASE WHEN variance_zero_percentile IS NOT NULL THEN 1 END) as with_variance_zero,
            COUNT(CASE WHEN kurtosis_null_percentile IS NOT NULL THEN 1 END) as with_kurtosis_null
        FROM race_feature_gradients
    """)
    
    stats = cursor.fetchone()
    print(f"\nFinal Gradient Table Summary:")
    print(f"  Total records: {stats[0]}")
    print(f"  Categories: {stats[1]}")
    print(f"  Average coverage: {stats[2]:.2%}")
    print(f"  With variance zero: {stats[3]}")
    print(f"  With kurtosis null: {stats[4]}")
    
    # Show breakdown by category
    cursor = conn.execute("""
        SELECT 
            race_category,
            COUNT(*) as count,
            AVG(percentile_coverage_ratio) as avg_coverage
        FROM race_feature_gradients
        GROUP BY race_category
        ORDER BY count DESC
    """)
    
    print(f"\nBy category:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} competitions (avg coverage: {row[2]:.1%})")
    
    conn.close()


if __name__ == "__main__":
    main()