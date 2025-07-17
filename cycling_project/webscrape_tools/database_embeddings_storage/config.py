"""
Configuration for the rider correlation processing pipeline.
Based on the specifications in migrating_embedding_system_to_db.md
"""
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
    MIN_RACE_PERCENTILES: Dict[str, float] = None
    
    def __post_init__(self):
        if self.MIN_RACE_PERCENTILES is None:
            self.MIN_RACE_PERCENTILES = {
                'total_prior_races': 90.0,      # Get 90% of riders
                'prior_gc_races': 75.0,          # Get 75% of riders for GC
                'prior_stage_races': 80.0,       # Get 80% of riders for stages
                'prior_one_day_races': 75.0,     # Get 75% of riders for one-days
                'prior_stage_one_days': 80.0     # Get 80% of riders for combined stage/one-day
            }
    
    # These will be populated by calculate_thresholds()
    MIN_RACES: Dict[str, int] = None
    
    def __post_init_races(self):
        if self.MIN_RACES is None:
            self.MIN_RACES = {}
    
    # Memory management
    MAX_MEMORY_GB: float = 8.0
    CACHE_SIZE_MB: int = 500
    
    # Checkpoint settings
    CHECKPOINT_FREQUENCY: int = 10  # competitions
    CHECKPOINT_NAME: str = "rider_correlation_v1"
    
    # Performance settings for M1
    NUM_WORKERS: int = 4  # M1 Pro efficiency cores
    CHUNK_SIZE: int = 10000  # SQLite read chunk
    
    # Feature dimensions
    PERCENTILES: List[int] = None
    NUM_FEATURES: int = 37
    
    def __post_init_percentiles(self):
        if self.PERCENTILES is None:
            self.PERCENTILES = [30, 40, 50, 60, 70, 80, 90, 100]
    
    # Race types and correlation mappings
    RACE_TYPES: List[str] = None
    
    def __post_init_race_types(self):
        if self.RACE_TYPES is None:
            self.RACE_TYPES = ['gc', 'stage', 'one_day']
    
    # Map race types to which correlations to calculate
    RACE_TYPE_CORRELATIONS: Dict[str, List[str]] = None
    
    def __post_init_correlations(self):
        if self.RACE_TYPE_CORRELATIONS is None:
            self.RACE_TYPE_CORRELATIONS = {
                'gc': ['all_races', 'same_type'],
                'stage': ['all_races', 'same_type', 'stage_one_days'],
                'one_day': ['all_races', 'same_type', 'stage_one_days']
            }
    
    RACE_TYPE_COLUMNS: Dict[str, str] = None
    
    def __post_init_columns(self):
        if self.RACE_TYPE_COLUMNS is None:
            self.RACE_TYPE_COLUMNS = {
                'gc': 'prior_gc_races',
                'stage': 'prior_stage_races', 
                'one_day': 'prior_one_day_races',
                'stage_one_days': 'prior_stage_one_days'  # Combined column
            }
    
    def __post_init__(self):
        """Initialize all None fields with defaults"""
        if self.MIN_RACE_PERCENTILES is None:
            self.MIN_RACE_PERCENTILES = {
                'total_prior_races': 90.0,
                'prior_gc_races': 75.0,
                'prior_stage_races': 75.0,
                'prior_one_day_races': 80.0,
                'prior_stage_one_days': 80.0
            }
        
        if self.MIN_RACES is None:
            self.MIN_RACES = {}
        
        if self.PERCENTILES is None:
            self.PERCENTILES = [30, 40, 50, 60, 70, 80, 90, 100]
        
        if self.RACE_TYPES is None:
            self.RACE_TYPES = ['gc', 'stage', 'one_day']
        
        if self.RACE_TYPE_CORRELATIONS is None:
            self.RACE_TYPE_CORRELATIONS = {
                'gc': ['all_races', 'same_type'],
                'stage': ['all_races', 'same_type', 'stage_one_days'],
                'one_day': ['all_races', 'same_type', 'stage_one_days']
            }
        
        if self.RACE_TYPE_COLUMNS is None:
            self.RACE_TYPE_COLUMNS = {
                'gc': 'prior_gc_races',
                'stage': 'prior_stage_races', 
                'one_day': 'prior_one_day_races',
                'stage_one_days': 'prior_stage_one_days'
            }

    # Database path
    DB_PATH: str = "../database/database/cycling_races.db"
    
    # Feature mapping from the spec
    RACE_FEATURES = [
        'total_finishers', 'included_finishers', 'abandon_ratio', 'winning_time', 
        'total_race_duration', 'variance_absolute', 'variance_normalized', 
        'std_deviation_absolute', 'std_deviation_normalized', 'skewness_absolute', 
        'skewness_normalized', 'kurtosis_absolute', 'kurtosis_normalized', 
        'gini_coefficient', 'shannon_entropy_absolute', 'shannon_entropy_normalized',
        '"5th_percentile_gap"', '"10th_percentile_gap"', '"15th_percentile_gap"', 
        '"20th_percentile_gap"', '"25th_percentile_gap"', '"30th_percentile_gap"', 
        '"35th_percentile_gap"', '"40th_percentile_gap"', '"45th_percentile_gap"', 
        '"50th_percentile_gap"', 'total_groups', 'riders_in_groups', 
        'proportion_in_groups', 'largest_group_size', 'largest_group_position', 
        'avg_group_size', 'std_group_size', 'biggest_group_metric', 
        'time_gap_evenness_metric', 'clumpiness_score', 'selection_metric'
    ]