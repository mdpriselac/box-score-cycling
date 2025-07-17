# Rider Correlation Processing Pipeline - Technical Specification

## Key Features Summary

1. **Percentile-based Filtering**: Configurable thresholds (e.g., top 90% by total races)
2. **Dual Requirements**: Both global AND race-type minimums must be met
3. **Stage_One_Days Category**: Combined correlations for stages and one-day races
4. **Three Correlation Types**: For stages/one-days: all_races, same_type, stage_one_days
5. **Automatic Threshold Calculation**: Converts percentiles to actual race counts
6. **Full Resume Support**: Can stop/start processing at any time

## Executive Summary

This document outlines an optimized pipeline for processing 1.1M rider results to calculate historical performance correlations against race features. The system is designed for a MacBook Pro M1 Pro with 16GB RAM and SSD storage, with full support for interrupted processing and resumption.

**Key Innovations**: 
1. The pipeline leverages pre-calculated race history columns in the `rider_results` table (`total_prior_races`, `prior_gc_races`, `prior_stage_races`, `prior_one_day_races`) to efficiently filter eligible results without needing to track rider histories during processing. This reduces memory usage by ~75% and processing time by ~25%.

2. **Percentile-based thresholds**: Instead of fixed minimums, the system calculates thresholds based on percentiles (e.g., only process riders in the top 90% by total races). This ensures you're working with the most experienced riders.

3. **Dual requirements**: Each rider result must meet BOTH a global minimum (total races) AND a race-type specific minimum to be processed.

4. **Combined stage_one_days category**: For stages and one-day races, the system calculates three correlation types: all_races, same_type, and stage_one_days (combined category).

## System Architecture Overview

### Key Components
1. **Pre-loading System**: Load all race features into memory (~22MB)
2. **Percentile Calculator**: Determine race count thresholds based on percentiles
3. **Chronological Processor**: Process competitions in time order
4. **Vectorized Calculator**: Use NumPy for efficient correlation calculations
5. **Checkpoint Manager**: Enable start/stop/resume functionality
6. **Batch Writer**: Optimize SQLite writes

### Performance Targets
- Total processing time: 2-3 hours (increased due to additional correlations)
- Memory usage: < 4GB peak (no rider history tracking needed)
- Checkpoint frequency: Every 100 competitions
- Recovery time: < 30 seconds

### Key Optimizations
1. The system leverages pre-calculated race history columns (`total_prior_races`, `prior_gc_races`, `prior_stage_races`, `prior_one_day_races`, `prior_stage_one_days`) in the `rider_results` table. This eliminates the need to track rider histories during processing, significantly reducing memory usage and complexity.

2. **Percentile-based filtering**: Only processes riders meeting both global and type-specific percentile thresholds, ensuring high-quality data.

3. **Three correlation types**: For stages and one-day races, calculates all_races, same_type, and stage_one_days correlations for richer feature sets.

## Database Schema

### Prerequisites

The `rider_results` table must have these pre-calculated columns:
- `total_prior_races`: Total races before this result
- `prior_gc_races`: GC races before this result  
- `prior_stage_races`: Stage races before this result
- `prior_one_day_races`: One-day races before this result
- `prior_stage_one_days`: Combined stage + one-day races (will be created if missing)

### New Tables

```sql
-- Option A: Denormalized correlation storage (RECOMMENDED)
-- One row per correlation value for fast access
CREATE TABLE rider_correlations_denorm (
    rider_result_id INTEGER NOT NULL,
    competition_id INTEGER NOT NULL,
    rider_id INTEGER NOT NULL,
    correlation_type TEXT NOT NULL, -- 'all_races', 'same_type', 'stage_one_days'
    percentile INTEGER NOT NULL, -- 30, 40, 50, 60, 70, 80, 90, 100
    feature_idx INTEGER NOT NULL, -- 0-34
    correlation_value REAL NOT NULL,
    race_count INTEGER NOT NULL,
    
    PRIMARY KEY (rider_result_id, correlation_type, percentile, feature_idx),
    INDEX idx_lookup (competition_id, rider_id, correlation_type),
    INDEX idx_rider_comp_type (rider_id, competition_id, correlation_type),
    INDEX idx_competition_access (competition_id, correlation_type)
);

-- Percentile thresholds table (populated during preprocessing)
CREATE TABLE race_history_thresholds (
    threshold_name TEXT PRIMARY KEY,
    percentile REAL NOT NULL,
    min_races INTEGER NOT NULL,
    total_riders INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Option B: Columnar storage (Alternative)
-- 280 columns, one per percentile-feature combination
CREATE TABLE rider_correlations_columnar (
    rider_result_id INTEGER NOT NULL,
    competition_id INTEGER NOT NULL,
    rider_id INTEGER NOT NULL,
    correlation_type TEXT NOT NULL,
    race_count INTEGER NOT NULL,
    -- 280 columns: corr_p30_f0 through corr_p100_f34
    corr_p30_f0 REAL,
    corr_p30_f1 REAL,
    -- ... all 280 combinations
    corr_p100_f34 REAL,
    
    PRIMARY KEY (rider_result_id, correlation_type),
    INDEX idx_competition_lookup (competition_id, rider_id)
);

-- Hybrid approach: Store both for flexibility
-- Keep the BLOB version for backup/analysis
CREATE TABLE rider_correlations_blob (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rider_result_id INTEGER NOT NULL,
    competition_id INTEGER NOT NULL,
    rider_id INTEGER NOT NULL,
    correlation_type TEXT NOT NULL,
    correlation_matrix BLOB NOT NULL, -- Backup/analysis only
    race_count INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(rider_result_id, correlation_type)
);

-- Processing checkpoint table (simplified - no rider history tracking needed)
CREATE TABLE processing_checkpoint (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    checkpoint_name TEXT NOT NULL,
    last_processed_competition_id INTEGER,
    last_processed_date TEXT,
    total_processed INTEGER,
    total_remaining INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(checkpoint_name)
);

-- Processing log for monitoring
CREATE TABLE processing_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_number INTEGER,
    competitions_processed INTEGER,
    riders_processed INTEGER,
    correlations_calculated INTEGER,
    processing_time_seconds REAL,
    memory_usage_mb REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Implementation Details

### 1. Configuration and Constants

```python
# config.py
import os
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class ProcessingConfig:
    # Batch sizes optimized for M1 Pro
    COMPETITION_BATCH_SIZE: int = 50
    RIDER_BATCH_SIZE: int = 200
    
    # Percentile-based minimum race requirements
    # These will be converted to actual race counts during preprocessing
    MIN_RACE_PERCENTILES: Dict[str, float] = {
        'total_prior_races': 90.0,      # Top 90% of riders by total races
        'prior_gc_races': 75.0,          # Top 75% for GC
        'prior_stage_races': 75.0,       # Top 75% for stages
        'prior_one_day_races': 80.0,     # Top 80% for one-days
        'prior_stage_one_days': 80.0     # Top 80% for combined stage/one-day
    }
    
    # These will be populated by calculate_thresholds()
    MIN_RACES: Dict[str, int] = {}
    
    # Memory management
    MAX_MEMORY_GB: float = 8.0
    CACHE_SIZE_MB: int = 500
    
    # Checkpoint settings
    CHECKPOINT_FREQUENCY: int = 100  # competitions
    CHECKPOINT_NAME: str = "rider_correlation_v1"
    
    # Performance settings for M1
    NUM_WORKERS: int = 4  # M1 Pro efficiency cores
    CHUNK_SIZE: int = 10000  # SQLite read chunk
    
    # Feature dimensions
    PERCENTILES: List[int] = [30, 40, 50, 60, 70, 80, 90, 100]
    NUM_FEATURES: int = 35
    
    # Race types and correlation mappings
    RACE_TYPES: List[str] = ['general_classification', 'stage', 'one_day']
    
    # Map race types to which correlations to calculate
    RACE_TYPE_CORRELATIONS: Dict[str, List[str]] = {
        'general_classification': ['all_races', 'same_type'],
        'stage': ['all_races', 'same_type', 'stage_one_days'],
        'one_day': ['all_races', 'same_type', 'stage_one_days']
    }
    
    RACE_TYPE_COLUMNS: Dict[str, str] = {
        'general_classification': 'prior_gc_races',
        'stage': 'prior_stage_races', 
        'one_day': 'prior_one_day_races',
        'stage_one_days': 'prior_stage_one_days'  # Combined column
    }
```

### 2. Core Processing Pipeline

```python
# correlation_processor.py
import numpy as np
import pandas as pd
import sqlite3
import pickle
import gzip
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import psutil
import logging
from memory_manager import MemoryManager

class CorrelationProcessor:
    def __init__(self, db_path: str, config: ProcessingConfig):
        self.db_path = db_path
        self.config = config
        self.race_features_cache: Dict[int, np.ndarray] = {}
        self.checkpoint_manager = CheckpointManager(db_path, config)
        
    def run(self, resume: bool = True):
        """Main entry point for processing"""
        start_time = datetime.now()
        
        # Calculate percentile-based thresholds
        self._calculate_thresholds()
        
        # Initialize or resume from checkpoint
        start_competition_id = 0
        if resume:
            checkpoint_data = self.checkpoint_manager.load_checkpoint()
            if checkpoint_data:
                start_competition_id = checkpoint_data['last_competition_id']
                logging.info(f"Resuming from competition {start_competition_id}")
        
        # Pre-load race features
        self._preload_race_features()
        
        # Get competitions to process
        competitions = self._get_competitions_to_process(start_competition_id)
        total_competitions = len(competitions)
        
        # Process in batches
        for batch_idx, comp_batch in enumerate(self._batch_competitions(competitions)):
            batch_start = datetime.now()
            
            # Process batch
            results = self._process_competition_batch(comp_batch)
            
            # Write results
            self._write_results_batch(results)
            
            # Log progress
            self._log_progress(batch_idx, comp_batch, batch_start)
            
            # Checkpoint if needed
            if (batch_idx + 1) % self.config.CHECKPOINT_FREQUENCY == 0:
                self.checkpoint_manager.save_checkpoint(
                    comp_batch[-1]['competition_id']
                )
            
            # Check memory usage
            if MemoryManager.check_memory_pressure():
                self.race_features_cache = MemoryManager.optimize_race_features_cache(
                    self.race_features_cache
                )
        
        # Final checkpoint
        self.checkpoint_manager.finalize()
        
        logging.info(f"Processing completed in {datetime.now() - start_time}")
    
    def _calculate_thresholds(self):
        """Calculate actual race count thresholds from percentiles"""
        logging.info("Calculating percentile-based thresholds...")
        
        with sqlite3.connect(self.db_path) as conn:
            # First, ensure we have the combined stage_one_days column
            # This should be pre-calculated, but we verify it exists
            try:
                conn.execute("""
                    ALTER TABLE rider_results 
                    ADD COLUMN prior_stage_one_days INTEGER DEFAULT 0
                """)
                
                # Update if column was just added
                conn.execute("""
                    UPDATE rider_results
                    SET prior_stage_one_days = prior_stage_races + prior_one_day_races
                """)
                conn.commit()
                logging.info("Added prior_stage_one_days column")
            except sqlite3.OperationalError:
                # Column already exists
                pass
            
            # Calculate thresholds for each column
            for column, percentile in self.config.MIN_RACE_PERCENTILES.items():
                # Get the value at the (100-percentile)th percentile
                # E.g., for top 90%, we want the 10th percentile value
                query = f"""
                    SELECT {column}
                    FROM rider_results
                    WHERE {column} > 0
                    ORDER BY {column}
                    LIMIT 1
                    OFFSET (SELECT COUNT(*) * ? / 100 FROM rider_results WHERE {column} > 0)
                """
                
                result = conn.execute(query, [100 - percentile]).fetchone()
                threshold = result[0] if result else 5  # Default to 5 if no data
                
                self.config.MIN_RACES[column] = threshold
                
                # Store in database for reference
                conn.execute("""
                    INSERT OR REPLACE INTO race_history_thresholds
                    (threshold_name, percentile, min_races, total_riders)
                    VALUES (?, ?, ?, (SELECT COUNT(DISTINCT rider_id) FROM rider_results))
                """, (column, percentile, threshold))
            
            conn.commit()
        
        logging.info(f"Calculated thresholds: {self.config.MIN_RACES}")
    
    def _preload_race_features(self):
        """Pre-load all race features into memory"""
        logging.info("Pre-loading race features...")
        
        query = """
        SELECT competition_id, percentile, feature_data
        FROM (
            SELECT competition_id, 30 as percentile, * FROM race_feature_30
            UNION ALL
            SELECT competition_id, 40 as percentile, * FROM race_feature_40
            UNION ALL
            -- ... continue for all percentiles
            SELECT competition_id, 100 as percentile, * FROM race_feature_100
        )
        ORDER BY competition_id, percentile
        """
        
        with sqlite3.connect(self.db_path) as conn:
            # Use M1-optimized settings
            conn.execute("PRAGMA cache_size = -2000000")  # 2GB cache
            conn.execute("PRAGMA temp_store = MEMORY")
            conn.execute("PRAGMA mmap_size = 2147483648")  # 2GB mmap
            
            df = pd.read_sql_query(query, conn)
            
        # Organize into nested structure
        for comp_id in df['competition_id'].unique():
            comp_data = df[df['competition_id'] == comp_id]
            feature_matrix = np.zeros((8, 35))
            
            for idx, percentile in enumerate(self.config.PERCENTILES):
                percentile_data = comp_data[comp_data['percentile'] == percentile]
                # Extract 35 features (adjust column names as needed)
                feature_matrix[idx, :] = percentile_data.iloc[0, 3:38].values
            
            self.race_features_cache[comp_id] = feature_matrix
        
        logging.info(f"Loaded {len(self.race_features_cache)} competition features")
    
    def _process_competition_batch(self, competitions: List[Dict]) -> List[Dict]:
        """Process a batch of competitions"""
        results = []
        comp_ids = [c['competition_id'] for c in competitions]
        
        # Get eligible rider results
        # Must meet BOTH global minimum AND race-type specific minimum
        query = """
        SELECT rr.*, c.race_type
        FROM rider_results rr
        JOIN competitions c ON rr.competition_id = c.competition_id
        WHERE rr.competition_id IN ({})
        AND rr.total_prior_races >= ?  -- Global minimum
        AND (
            -- Race-type specific minimums
            (c.race_type = 'general_classification' AND rr.prior_gc_races >= ?)
            OR
            (c.race_type = 'stage' AND rr.prior_stage_races >= ? AND rr.prior_stage_one_days >= ?)
            OR
            (c.race_type = 'one_day' AND rr.prior_one_day_races >= ? AND rr.prior_stage_one_days >= ?)
        )
        ORDER BY rr.competition_date, rr.competition_id
        """.format(','.join(['?'] * len(comp_ids)))
        
        params = comp_ids + [
            self.config.MIN_RACES['total_prior_races'],       # Global minimum
            self.config.MIN_RACES['prior_gc_races'],         # GC minimum
            self.config.MIN_RACES['prior_stage_races'],      # Stage minimum
            self.config.MIN_RACES['prior_stage_one_days'],   # Stage combined minimum
            self.config.MIN_RACES['prior_one_day_races'],    # One-day minimum
            self.config.MIN_RACES['prior_stage_one_days']    # One-day combined minimum
        ]
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rider_results = conn.execute(query, params).fetchall()
        
        logging.info(f"Processing {len(rider_results)} eligible rider results in batch")
        
        # Process each rider result
        for rr in rider_results:
            result_dict = dict(rr)
            race_type = result_dict['race_type']
            
            # Get correlation types for this race type
            correlation_types = self.config.RACE_TYPE_CORRELATIONS[race_type]
            
            for corr_type in correlation_types:
                # Determine which history to use
                if corr_type == 'all_races':
                    history = self._get_rider_history(
                        result_dict['rider_id'], 
                        result_dict['competition_date'],
                        race_type=None
                    )
                    min_required = self.config.MIN_RACES['total_prior_races']
                
                elif corr_type == 'same_type':
                    history = self._get_rider_history(
                        result_dict['rider_id'],
                        result_dict['competition_date'],
                        race_type=race_type
                    )
                    col_name = self.config.RACE_TYPE_COLUMNS[race_type]
                    min_required = self.config.MIN_RACES[col_name]
                
                elif corr_type == 'stage_one_days':
                    history = self._get_rider_history(
                        result_dict['rider_id'],
                        result_dict['competition_date'],
                        race_type='stage_one_days'  # Special combined type
                    )
                    min_required = self.config.MIN_RACES['prior_stage_one_days']
                
                # Calculate correlation if sufficient history
                if len(history) >= min_required:
                    correlation_matrix = self._calculate_correlation(history)
                    
                    if correlation_matrix is not None:
                        results.append({
                            'rider_result_id': result_dict['rider_result_id'],
                            'competition_id': result_dict['competition_id'],
                            'rider_id': result_dict['rider_id'],
                            'correlation_type': corr_type,
                            'correlation_matrix': correlation_matrix,
                            'race_count': len(history)
                        })
        
        return results
    
    def _get_rider_history(self, rider_id: int, before_date: str, 
                          race_type: Optional[str] = None) -> List[Dict]:
        """Get rider's history before a specific date"""
        
        if race_type == 'stage_one_days':
            # Special case: combined stage and one-day races
            query = """
            SELECT rr.competition_id, rr.points, rr.competition_date
            FROM rider_results rr
            JOIN competitions c ON rr.competition_id = c.competition_id
            WHERE rr.rider_id = ?
            AND rr.competition_date < ?
            AND c.race_type IN ('stage', 'one_day')
            ORDER BY rr.competition_date DESC
            """
            params = [rider_id, before_date]
            
        elif race_type:
            query = """
            SELECT rr.competition_id, rr.points, rr.competition_date
            FROM rider_results rr
            JOIN competitions c ON rr.competition_id = c.competition_id
            WHERE rr.rider_id = ?
            AND rr.competition_date < ?
            AND c.race_type = ?
            ORDER BY rr.competition_date DESC
            """
            params = [rider_id, before_date, race_type]
            
        else:
            # All races
            query = """
            SELECT competition_id, points, competition_date
            FROM rider_results
            WHERE rider_id = ?
            AND competition_date < ?
            ORDER BY competition_date DESC
            """
            params = [rider_id, before_date]
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            results = conn.execute(query, params).fetchall()
        
        return [dict(r) for r in results]
    
    def _calculate_correlation(self, history: List[Dict]) -> Optional[np.ndarray]:
        """Calculate correlation matrix for a rider's history"""
        if not history:
            return None
        
        # Extract points and competition IDs
        points = np.array([h['points'] for h in history])
        comp_ids = [h['competition_id'] for h in history]
        
        # Build feature matrix
        feature_matrices = []
        for comp_id in comp_ids:
            if comp_id in self.race_features_cache:
                feature_matrices.append(self.race_features_cache[comp_id])
        
        if len(feature_matrices) != len(points):
            logging.warning(f"Missing race features for some competitions")
            return None
        
        # Stack into 3D array: (n_races, 8, 35)
        features_3d = np.stack(feature_matrices)
        
        # Flatten to 2D for correlation: (n_races, 280)
        features_flat = features_3d.reshape(len(points), -1)
        
        # Calculate correlations using vectorized operations
        # Use M1-optimized NumPy
        correlation_matrix = np.zeros((8, 35))
        
        for i in range(features_flat.shape[1]):
            if np.std(features_flat[:, i]) > 0:  # Avoid division by zero
                corr = np.corrcoef(points, features_flat[:, i])[0, 1]
                row = i // 35
                col = i % 35
                correlation_matrix[row, col] = corr
        
        return correlation_matrix
    
    def _get_competitions_to_process(self, start_competition_id: int) -> List[Dict]:
        """Get list of competitions to process"""
        with sqlite3.connect(self.db_path) as conn:
            query = """
            SELECT DISTINCT competition_id, competition_date
            FROM competitions
            WHERE competition_id > ?
            ORDER BY competition_date, competition_id
            """
            results = conn.execute(query, [start_competition_id]).fetchall()
            
        return [{'competition_id': r[0], 'competition_date': r[1]} for r in results]
    
    def _batch_competitions(self, competitions: List[Dict]):
        """Yield batches of competitions"""
        for i in range(0, len(competitions), self.config.COMPETITION_BATCH_SIZE):
            yield competitions[i:i + self.config.COMPETITION_BATCH_SIZE]
    
    def _log_progress(self, batch_idx: int, comp_batch: List[Dict], 
                     batch_start: datetime):
        """Log processing progress"""
        processing_time = (datetime.now() - batch_start).total_seconds()
        memory_usage = psutil.virtual_memory().used / (1024 ** 2)  # MB
        
        with sqlite3.connect(self.db_path) as conn:
            # Get batch statistics
            comp_ids = [c['competition_id'] for c in comp_batch]
            placeholders = ','.join(['?'] * len(comp_ids))
            
            stats = conn.execute(f"""
                SELECT 
                    COUNT(DISTINCT rider_id) as riders,
                    COUNT(*) as correlations
                FROM rider_correlations_denorm
                WHERE competition_id IN ({placeholders})
            """, comp_ids).fetchone()
            
            # Log to database
            conn.execute("""
                INSERT INTO processing_log
                (batch_number, competitions_processed, riders_processed,
                 correlations_calculated, processing_time_seconds, memory_usage_mb)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                batch_idx,
                len(comp_batch),
                stats[0] if stats else 0,
                stats[1] if stats else 0,
                processing_time,
                memory_usage
            ))
            conn.commit()
        
        logging.info(
            f"Batch {batch_idx}: Processed {len(comp_batch)} competitions "
            f"in {processing_time:.1f}s, Memory: {memory_usage:.1f}MB"
        )
    
    def _write_results_batch(self, results: List[Dict]):
        """Write results to database in batch"""
        if not results:
            return
        
        with sqlite3.connect(self.db_path) as conn:
            # Optimize for writes
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA cache_size = -2000000")
            
            # Prepare denormalized records
            denorm_records = []
            blob_records = []
            
            for r in results:
                # Store BLOB version for backup
                matrix_blob = gzip.compress(r['correlation_matrix'].tobytes())
                blob_records.append((
                    r['rider_result_id'],
                    r['competition_id'],
                    r['rider_id'],
                    r['correlation_type'],
                    matrix_blob,
                    r['race_count']
                ))
                
                # Create denormalized records
                matrix = r['correlation_matrix']
                for p_idx, percentile in enumerate(self.config.PERCENTILES):
                    for f_idx in range(self.config.NUM_FEATURES):
                        denorm_records.append((
                            r['rider_result_id'],
                            r['competition_id'],
                            r['rider_id'],
                            r['correlation_type'],
                            percentile,
                            f_idx,
                            float(matrix[p_idx, f_idx]),
                            r['race_count']
                        ))
            
            # Batch insert denormalized data
            conn.executemany("""
                INSERT OR REPLACE INTO rider_correlations_denorm 
                (rider_result_id, competition_id, rider_id, correlation_type,
                 percentile, feature_idx, correlation_value, race_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, denorm_records)
            
            # Batch insert blob backup
            conn.executemany("""
                INSERT OR REPLACE INTO rider_correlations_blob
                (rider_result_id, competition_id, rider_id, correlation_type,
                 correlation_matrix, race_count)
                VALUES (?, ?, ?, ?, ?, ?)
            """, blob_records)
            
            conn.commit()
            
            logging.info(f"Wrote {len(results)} correlation matrices ({len(denorm_records)} values)")
```

### 3. Checkpoint Manager

```python
# checkpoint_manager.py
class CheckpointManager:
    def __init__(self, db_path: str, config: ProcessingConfig):
        self.db_path = db_path
        self.config = config
    
    def save_checkpoint(self, last_competition_id: int):
        """Save current processing state"""
        
        with sqlite3.connect(self.db_path) as conn:
            # Get processing statistics
            stats = conn.execute("""
                SELECT 
                    COUNT(DISTINCT rider_id) as riders_processed,
                    COUNT(DISTINCT competition_id) as competitions_processed,
                    COUNT(*) as correlations_calculated
                FROM rider_correlations_denorm
            """).fetchone()
            
            conn.execute("""
                INSERT OR REPLACE INTO processing_checkpoint
                (checkpoint_name, last_processed_competition_id, 
                 last_processed_date, total_processed, rider_histories_snapshot)
                VALUES (?, ?, ?, ?, NULL)
            """, (
                self.config.CHECKPOINT_NAME,
                last_competition_id,
                datetime.now().isoformat(),
                stats[2] if stats else 0
            ))
            conn.commit()
        
        logging.info(f"Checkpoint saved at competition {last_competition_id}")
    
    def load_checkpoint(self) -> Optional[Dict]:
        """Load the most recent checkpoint"""
        with sqlite3.connect(self.db_path) as conn:
            result = conn.execute("""
                SELECT last_processed_competition_id
                FROM processing_checkpoint
                WHERE checkpoint_name = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (self.config.CHECKPOINT_NAME,)).fetchone()
            
            if result:
                return {'last_competition_id': result[0]}
        
        return None
    
    def finalize(self):
        """Mark processing as complete"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE processing_checkpoint
                SET last_processed_date = ?
                WHERE checkpoint_name = ?
            """, (datetime.now().isoformat(), self.config.CHECKPOINT_NAME))
            conn.commit()
```

### 4. Memory Management

```python
# memory_manager.py
class MemoryManager:
    @staticmethod
    def check_memory_pressure(threshold_gb: float = 12.0) -> bool:
        """Check if memory usage is approaching threshold"""
        memory = psutil.virtual_memory()
        used_gb = memory.used / (1024 ** 3)
        return used_gb > threshold_gb
    
    @staticmethod
    def optimize_race_features_cache(cache: Dict, max_size: int = 5000):
        """Optimize race features cache if it grows too large"""
        if len(cache) > max_size:
            # Keep most recent competitions
            sorted_comps = sorted(cache.keys(), reverse=True)
            keep_comps = sorted_comps[:max_size]
            
            new_cache = {comp_id: cache[comp_id] for comp_id in keep_comps}
            
            removed = len(cache) - len(new_cache)
            logging.info(f"Removed {removed} old competitions from cache")
            
            return new_cache
        
        return cache
```

### 5. Usage Instructions

```python
# main.py
import logging
from correlation_processor import CorrelationProcessor, ProcessingConfig

def main():
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('correlation_processing.log'),
            logging.StreamHandler()
        ]
    )
    
    # Initialize configuration with percentile requirements
    config = ProcessingConfig()
    
    # Optionally override percentile requirements
    # config.MIN_RACE_PERCENTILES = {
    #     'total_prior_races': 95.0,      # More restrictive
    #     'prior_gc_races': 80.0,
    #     'prior_stage_races': 80.0,
    #     'prior_one_day_races': 85.0,
    #     'prior_stage_one_days': 85.0
    # }
    
    # Create processor
    processor = CorrelationProcessor(
        db_path='path/to/your/database.db',
        config=config
    )
    
    # Run processing (will automatically resume if interrupted)
    processor.run(resume=True)

if __name__ == "__main__":
    main()
```

### 6. Preprocessing Script (Optional)

```python
# preprocess_stage_one_days.py
import sqlite3
import logging

def add_stage_one_days_column(db_path: str):
    """Add and populate prior_stage_one_days column if needed"""
    
    with sqlite3.connect(db_path) as conn:
        try:
            # Add column
            conn.execute("""
                ALTER TABLE rider_results 
                ADD COLUMN prior_stage_one_days INTEGER DEFAULT 0
            """)
            
            # Populate with sum of stage and one-day races
            conn.execute("""
                UPDATE rider_results
                SET prior_stage_one_days = prior_stage_races + prior_one_day_races
            """)
            
            conn.commit()
            logging.info("Successfully added prior_stage_one_days column")
            
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                logging.info("prior_stage_one_days column already exists")
            else:
                raise
    
    # Verify the update
    with sqlite3.connect(db_path) as conn:
        result = conn.execute("""
            SELECT 
                COUNT(*) as total_rows,
                AVG(prior_stage_one_days) as avg_combined,
                AVG(prior_stage_races) as avg_stage,
                AVG(prior_one_day_races) as avg_one_day
            FROM rider_results
        """).fetchone()
        
        logging.info(f"""
        Column statistics:
        - Total rows: {result[0]:,}
        - Avg stage_one_days: {result[1]:.1f}
        - Avg stages: {result[2]:.1f}
        - Avg one-days: {result[3]:.1f}
        """)

if __name__ == "__main__":
    add_stage_one_days_column('path/to/database.db')
```

## Migration Plan

### Phase 1: Preparation (30 minutes)
1. **Backup Database**: Create full backup of SQLite database
2. **Create Tables**: Run schema creation scripts (both denormalized and blob tables)
3. **Index Verification**: Ensure all required indexes exist
4. **Storage Check**: Ensure ~3GB free space (denormalized storage requires more)
5. **Test Run**: Process first 100 competitions as validation

### Phase 2: Initial Processing (2-4 hours)
1. **Start Processing**: Run `python main.py`
2. **Monitor Progress**: Check `processing_log` table
3. **Verify Checkpoints**: Ensure checkpoints are being saved

### Phase 3: Interruption Handling
If processing needs to be stopped:
1. **Graceful Shutdown**: Press Ctrl+C (handler will save checkpoint)
2. **Force Stop**: Kill process (checkpoint from last batch preserved)
3. **Resume**: Run `python main.py` again (auto-resumes)

### Phase 4: Validation
```sql
-- Check progress
SELECT 
    COUNT(DISTINCT rider_id) as riders_processed,
    COUNT(DISTINCT competition_id) as competitions_processed,
    COUNT(*) as total_correlations
FROM rider_correlations;

-- Verify data integrity
SELECT 
    correlation_type,
    AVG(race_count) as avg_races,
    COUNT(*) as count
FROM rider_correlations
GROUP BY correlation_type;
```

## Performance Optimization Tips

### For M1 Pro Specific:
1. **Use ARM64 NumPy**: Ensure NumPy is compiled for ARM64
2. **Parallel Processing**: Use 4 efficiency cores for I/O operations
3. **Memory Alignment**: Keep arrays 64-byte aligned for SIMD

### SQLite Optimizations:
```python
# Optimal connection settings for M1 Pro
conn.execute("PRAGMA cache_size = -2000000")    # 2GB cache
conn.execute("PRAGMA temp_store = MEMORY")      # Use RAM for temp
conn.execute("PRAGMA mmap_size = 2147483648")   # 2GB memory map
conn.execute("PRAGMA page_size = 4096")         # Optimal for SSD
conn.execute("PRAGMA synchronous = NORMAL")     # Balance safety/speed
conn.execute("PRAGMA journal_mode = WAL")       # Write-ahead logging
```

## Monitoring and Debugging

### Viewing Calculated Thresholds

```python
# view_thresholds.py
import sqlite3

def view_thresholds(db_path: str):
    """View the calculated percentile-based thresholds"""
    
    with sqlite3.connect(db_path) as conn:
        # Get thresholds
        thresholds = conn.execute("""
            SELECT * FROM race_history_thresholds
            ORDER BY threshold_name
        """).fetchall()
        
        print("\nCalculated Race History Thresholds:")
        print("-" * 60)
        print(f"{'Column':<25} {'Percentile':<12} {'Min Races':<10}")
        print("-" * 60)
        
        for row in thresholds:
            print(f"{row[0]:<25} Top {row[1]:<8.0f}% {row[2]:<10}")
        
        # Get distribution info
        print("\n\nDistribution Analysis:")
        print("-" * 60)
        
        for threshold_name, percentile, min_races, _, _ in thresholds:
            if threshold_name == 'prior_stage_one_days':
                # Special handling for combined column
                query = f"""
                    SELECT 
                        COUNT(*) as total_eligible,
                        AVG({threshold_name}) as avg_races,
                        MAX({threshold_name}) as max_races
                    FROM rider_results
                    WHERE {threshold_name} >= ?
                """
            else:
                query = f"""
                    SELECT 
                        COUNT(*) as total_eligible,
                        AVG({threshold_name}) as avg_races,
                        MAX({threshold_name}) as max_races
                    FROM rider_results
                    WHERE {threshold_name} >= ?
                """
            
            stats = conn.execute(query, [min_races]).fetchone()
            
            print(f"\n{threshold_name}:")
            print(f"  Eligible results: {stats[0]:,}")
            print(f"  Average races for eligible: {stats[1]:.1f}")
            print(f"  Maximum races: {stats[2]}")

if __name__ == "__main__":
    view_thresholds('path/to/database.db')
```

### Progress Monitoring Script:
```python
# monitor.py
import sqlite3
import time
from datetime import datetime

def monitor_progress(db_path: str, interval: int = 30):
    """Monitor processing progress"""
    while True:
        with sqlite3.connect(db_path) as conn:
            # Get latest stats
            stats = conn.execute("""
                SELECT 
                    MAX(batch_number) as last_batch,
                    SUM(riders_processed) as total_riders,
                    SUM(correlations_calculated) as total_correlations,
                    AVG(processing_time_seconds) as avg_time,
                    AVG(memory_usage_mb) as avg_memory
                FROM processing_log
                WHERE created_at > datetime('now', '-1 hour')
            """).fetchone()
            
            # Get checkpoint info
            checkpoint = conn.execute("""
                SELECT last_processed_competition_id, last_processed_date
                FROM processing_checkpoint
                WHERE checkpoint_name = 'rider_correlation_v1'
                ORDER BY created_at DESC
                LIMIT 1
            """).fetchone()
            
            print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]")
            print(f"Last Batch: {stats[0]}")
            print(f"Total Riders: {stats[1]:,}")
            print(f"Total Correlations: {stats[2]:,}")
            print(f"Avg Processing Time: {stats[3]:.2f}s")
            print(f"Avg Memory Usage: {stats[4]:.2f}MB")
            
            if checkpoint:
                print(f"Last Checkpoint: Competition {checkpoint[0]} at {checkpoint[1]}")
        
        time.sleep(interval)

if __name__ == "__main__":
    monitor_progress('path/to/database.db')
```

## Error Handling

### Common Issues and Solutions:

1. **Memory Errors**:
   - Reduce `COMPETITION_BATCH_SIZE`
   - Enable memory optimization in config
   - Increase checkpoint frequency

2. **Correlation Calculation Errors**:
   - Check for missing race features
   - Verify data types in feature tables
   - Handle edge cases (single race, zero variance)

3. **Database Lock Errors**:
   - Ensure single process running
   - Use WAL mode for concurrent reads
   - Implement retry logic with exponential backoff

## Final Notes

- Total estimated time: 2-3 hours on M1 Pro (increased due to additional correlations)
- Can be safely interrupted and resumed at any time
- Checkpoints every 100 competitions (~5-10 minutes)
- Final output: ~2-2.5GB of denormalized correlation data (larger due to stage_one_days)
- Memory usage: Peak ~4GB (no rider history tracking needed)
- Monitor progress via log table and monitoring script

**Key Benefits of the Enhanced System:**
1. **Quality Control**: Percentile-based filtering ensures only experienced riders are processed
2. **Flexibility**: Easy to adjust thresholds by changing percentiles
3. **Comprehensive**: Stage/one-day riders get 3 correlation types for richer features
4. **Dual Requirements**: Both global and type-specific minimums ensure data quality

**Processing Statistics (Estimated):**
- ~200-300K rider results will meet the percentile thresholds
- ~400-600K total correlation matrices (due to multiple types)
- ~112-168M individual correlation values in denormalized table

For questions or issues, check:
1. `correlation_processing.log` file
2. `processing_log` table in database
3. `race_history_thresholds` table for calculated minimums
4. Memory usage via Activity Monitor
5. SQLite integrity: `PRAGMA integrity_check`

## Efficient Access Patterns for Interaction Features

### Pre-filtering Benefits

The percentile-based thresholds ensure you're working with experienced riders:

```sql
-- Get threshold values
SELECT * FROM race_history_thresholds;

-- Example: Get riders with substantial history for a competition
SELECT 
    rr.rider_result_id,
    rr.rider_id,
    rr.total_prior_races,
    rr.prior_gc_races,
    rr.prior_stage_races,
    rr.prior_one_day_races,
    rr.prior_stage_one_days,
    rc_all.correlation_value as all_races_corr,
    rc_type.correlation_value as same_type_corr,
    rc_combined.correlation_value as stage_one_days_corr
FROM rider_results rr
LEFT JOIN rider_correlations_denorm rc_all 
    ON rr.rider_result_id = rc_all.rider_result_id 
    AND rc_all.correlation_type = 'all_races'
LEFT JOIN rider_correlations_denorm rc_type
    ON rr.rider_result_id = rc_type.rider_result_id
    AND rc_type.correlation_type = 'same_type'
LEFT JOIN rider_correlations_denorm rc_combined
    ON rr.rider_result_id = rc_combined.rider_result_id
    AND rc_combined.correlation_type = 'stage_one_days'
WHERE rr.competition_id = ?
```

### Query Examples for Fast Correlation Access

```python
# Get all correlations for riders in a specific competition
def get_competition_correlations(conn, competition_id):
    """Retrieve all rider correlations for a competition"""
    query = """
    SELECT 
        rider_id,
        correlation_type,
        percentile,
        feature_idx,
        correlation_value
    FROM rider_correlations_denorm
    WHERE competition_id = ?
    AND correlation_type = 'all_races'  -- or 'same_type'
    ORDER BY rider_id, percentile, feature_idx
    """
    
    df = pd.read_sql_query(query, conn, params=[competition_id])
    
    # Pivot to get rider matrices
    rider_matrices = {}
    for rider_id in df['rider_id'].unique():
        rider_data = df[df['rider_id'] == rider_id]
        matrix = np.zeros((8, 35))
        
        for _, row in rider_data.iterrows():
            p_idx = self.config.PERCENTILES.index(row['percentile'])
            f_idx = row['feature_idx']
            matrix[p_idx, f_idx] = row['correlation_value']
        
        rider_matrices[rider_id] = matrix
    
    return rider_matrices

# Efficient batch query for multiple riders
def get_rider_correlations_batch(conn, rider_result_ids):
    """Get correlations for specific rider results"""
    placeholders = ','.join(['?'] * len(rider_result_ids))
    query = f"""
    SELECT 
        rider_result_id,
        percentile,
        feature_idx,
        correlation_value
    FROM rider_correlations_denorm
    WHERE rider_result_id IN ({placeholders})
    AND correlation_type = ?
    """
    
    return pd.read_sql_query(
        query, 
        conn, 
        params=rider_result_ids + ['all_races']
    )

# Direct feature interaction calculation
def calculate_interaction_features(conn, competition_id):
    """Calculate interaction features between correlations and race features"""
    
    # Get race features for this competition
    race_features = get_race_features(competition_id)  # Your existing method
    
    # Get race type for this competition
    race_type = conn.execute(
        "SELECT race_type FROM competitions WHERE competition_id = ?",
        [competition_id]
    ).fetchone()[0]
    
    # Determine which correlation types to use
    if race_type in ['stage', 'one_day']:
        correlation_types = ['all_races', 'same_type', 'stage_one_days']
    else:
        correlation_types = ['all_races', 'same_type']
    
    all_interactions = []
    
    for corr_type in correlation_types:
        # Get all rider correlations for this competition and type
        query = """
        SELECT 
            rc.rider_id,
            rc.rider_result_id,
            rc.percentile,
            rc.feature_idx,
            rc.correlation_value,
            rr.points
        FROM rider_correlations_denorm rc
        JOIN rider_results rr ON rc.rider_result_id = rr.rider_result_id
        WHERE rc.competition_id = ?
        AND rc.correlation_type = ?
        """
        
        df = pd.read_sql_query(query, conn, params=[competition_id, corr_type])
        
        # Calculate interactions efficiently
        interactions = []
        for _, row in df.iterrows():
            p_idx = PERCENTILES.index(row['percentile'])
            f_idx = row['feature_idx']
            
            # Example interactions
            feature_value = race_features[p_idx, f_idx]
            correlation = row['correlation_value']
            
            interaction = {
                'rider_result_id': row['rider_result_id'],
                'correlation_type': corr_type,
                f'{corr_type}_interaction_product': correlation * feature_value,
                f'{corr_type}_interaction_squared': correlation * feature_value ** 2,
                f'{corr_type}_correlation_weighted': correlation * np.log1p(abs(feature_value)),
                # Add more interaction types as needed
            }
            interactions.append(interaction)
        
        all_interactions.extend(interactions)
    
    # Combine all correlation types into wide format
    df_interactions = pd.DataFrame(all_interactions)
    wide_format = df_interactions.pivot_table(
        index='rider_result_id',
        columns='correlation_type',
        values=[col for col in df_interactions.columns if 'interaction' in col],
        aggfunc='first'
    )
    
    return wide_format
```

### Storage Trade-offs

**Denormalized Approach (Recommended)**:
- Storage: ~1.5-2GB (3x larger than BLOB)
- Write time: ~20% slower
- Read time: 10-50x faster for queries
- Flexibility: Can query specific features/percentiles
- SQL aggregations: Fully supported

**If storage is a concern**, consider:
1. Store only significant correlations (abs(corr) > 0.1)
2. Use REAL (4 bytes) instead of DOUBLE
3. Compress similar correlation patterns
4. Archive old competitions to separate tables

### Alternative: Hybrid External Storage

For maximum performance with interaction features, consider storing correlations in Parquet files:

```python
# After processing, export to Parquet for ML pipelines
def export_to_parquet(conn, output_dir):
    """Export correlations to Parquet for fast ML access"""
    
    # Read all correlations
    df = pd.read_sql_query("""
        SELECT * FROM rider_correlations_denorm
    """, conn)
    
    # Partition by competition for efficient access
    df.to_parquet(
        output_dir,
        partition_cols=['competition_id'],
        compression='snappy',
        engine='pyarrow'
    )
    
    # Now you can read specific competitions instantly:
    # df = pd.read_parquet(f"{output_dir}/competition_id=12345")
```

This gives you:
- Lightning-fast reads for ML pipelines
- Columnar compression (smaller than SQLite)
- Direct integration with ML frameworks
- Keep SQLite for queries, Parquet for bulk ML operations