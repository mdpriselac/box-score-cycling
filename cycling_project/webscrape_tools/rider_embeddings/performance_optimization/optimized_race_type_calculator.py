import numpy as np
from scipy import stats
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import warnings
import sys
import sqlite3
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))
from rider_embeddings.performance_feature_link.race_type_correlation_method import RaceTypeCorrelationCalculator
from rider_embeddings.performance_optimization.optimized_base import OptimizedPerformanceFeatureLinkBase


class OptimizedRaceTypeCorrelationCalculator(RaceTypeCorrelationCalculator, OptimizedPerformanceFeatureLinkBase):
    """
    Optimized race type correlation calculator that uses batched database loading
    for significantly improved performance.
    """
    
    def __init__(
        self, 
        db_path: str, 
        min_races_all: int = 35,
        min_races_stage: int = 25,
        min_races_one_day: int = 15,
        min_races_gc: int = 10,
        use_batched_loading: bool = True
    ):
        """
        Initialize the optimized race type correlation calculator.
        
        Args:
            db_path: Path to the cycling races database
            min_races_all: Minimum races required for all-race correlations
            min_races_stage: Minimum races required for stage correlations
            min_races_one_day: Minimum races required for one-day correlations
            min_races_gc: Minimum races required for GC correlations
            use_batched_loading: Whether to use batched database loading
        """
        # Initialize race type calculator
        RaceTypeCorrelationCalculator.__init__(
            self, 
            db_path,
            min_races_all=min_races_all,
            min_races_stage=min_races_stage,
            min_races_one_day=min_races_one_day,
            min_races_gc=min_races_gc
        )
        
        # Initialize optimized base
        OptimizedPerformanceFeatureLinkBase.__init__(self, db_path, use_batched_loading)
    
    def calculate_feature_relationships(
        self, 
        rider_result_id: int,
        lookback_date: str,
        feature_tables: List[str]
    ) -> Dict[str, Any]:
        """
        Calculate correlations using optimized data access when available.
        
        Args:
            rider_result_id: ID from the rider_results table
            lookback_date: Date string (YYYY-MM-DD) to calculate history up to
            feature_tables: List of race_features_N tables to analyze
            
        Returns:
            Dictionary with correlation results for each race type and feature table
        """
        # Validate feature tables
        valid_tables = self.validate_feature_tables(feature_tables)
        
        # Get rider history using optimized method
        if self.use_batched_loading and self._batched_loader:
            # Use cached data
            full_history = self.get_cached_rider_history(rider_result_id)
            if not full_history:
                return self._empty_result(rider_result_id, "No cached history found")
        else:
            # Fallback to original method
            rider_id = self._get_rider_id(rider_result_id)
            if rider_id is None:
                return self._empty_result(rider_result_id, "Rider result not found")
            
            full_history = self.get_rider_history(rider_id, lookback_date)
        
        # Check if any history exists
        if not full_history:
            return self._empty_result(rider_result_id, "No historical data found")
        
        # Segment history by race type
        race_type_histories = self._segment_history_by_race_type(full_history)
        
        # Calculate correlations for each race type and feature table
        feature_correlations = {}
        warnings_list = []
        race_counts = {}
        
        for race_type, history in race_type_histories.items():
            race_counts[race_type] = len(history)
            
            # Check if enough history for this race type
            if len(history) < self.min_races[race_type]:
                warnings_list.append(
                    f"{race_type}: Insufficient history - {len(history)} races "
                    f"(minimum {self.min_races[race_type]} required)"
                )
                continue
            
            # Calculate correlations for each feature table
            race_type_correlations = {}
            for feature_table in valid_tables:
                correlations, table_warnings = self._calculate_table_correlations_optimized(
                    history, feature_table, race_type
                )
                race_type_correlations[feature_table] = correlations
                warnings_list.extend(table_warnings)
            
            feature_correlations[race_type] = race_type_correlations
        
        return {
            'rider_result_id': rider_result_id,
            'feature_correlations': feature_correlations,
            'metadata': {
                'n_races': race_counts,
                'method': 'optimized_race_type_correlation',
                'calculation_date': datetime.now(),
                'warnings': warnings_list
            }
        }
    
    def _calculate_table_correlations_optimized(
        self, 
        history: List[Dict[str, Any]], 
        feature_table: str,
        race_type: str
    ) -> Tuple[Dict[str, float], List[str]]:
        """
        Calculate correlations using optimized feature access.
        
        Returns:
            Tuple of (correlations dict, warnings list)
        """
        # Get competition IDs from history
        competition_ids = [h['competition_id'] for h in history]
        
        # Get race features using optimized method
        if self.use_batched_loading and self._batched_loader:
            features_data = self.get_cached_race_features(competition_ids, feature_table)
        else:
            features_data = self.get_race_features(competition_ids, feature_table)
        
        # Filter history to only include races with feature data
        valid_history = [h for h in history if h['competition_id'] in features_data]
        
        if len(valid_history) < self.min_races[race_type]:
            return {}, [
                f"{feature_table}/{race_type}: Only {len(valid_history)} races with feature data "
                f"(minimum {self.min_races[race_type]} required)"
            ]
        
        # Extract performance data (points)
        points = np.array([h['uci_points_proportional'] for h in valid_history])
        
        # Check for zero variance in points
        if np.std(points) == 0:
            return {}, [f"{feature_table}/{race_type}: No variance in performance data"]
        
        # Calculate correlations for each feature
        correlations = {}
        feature_names = set()
        
        # Get all feature names from the first valid competition
        if valid_history:
            first_comp_id = valid_history[0]['competition_id']
            feature_names = set(features_data[first_comp_id].keys())
        
        for feature_name in feature_names:
            # Extract feature values
            feature_values = []
            for h in valid_history:
                comp_id = h['competition_id']
                value = features_data[comp_id].get(feature_name)
                if value is not None:
                    feature_values.append(value)
                else:
                    feature_values.append(np.nan)
            
            feature_array = np.array(feature_values)
            
            # Calculate correlation if enough non-null values
            min_required = self.min_races[race_type]
            if np.sum(~np.isnan(feature_array)) >= min_required:
                # Remove any rows with NaN values
                valid_mask = ~(np.isnan(feature_array) | np.isnan(points))
                valid_points = points[valid_mask]
                valid_features = feature_array[valid_mask]
                
                # Check for variance in both feature and points
                if (len(valid_features) >= min_required and 
                    np.std(valid_features) > 1e-10 and 
                    np.std(valid_points) > 1e-10):
                    
                    # Suppress the constant input warning
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        corr, p_value = stats.spearmanr(valid_points, valid_features)
                    
                    correlations[feature_name] = float(corr) if not np.isnan(corr) else None
                else:
                    correlations[feature_name] = None
            else:
                correlations[feature_name] = None
        
        return correlations, []
    
    def get_cached_rider_history(self, rider_result_id: int) -> List[Dict[str, Any]]:
        """Get cached rider history with fallback."""
        if self.use_batched_loading and self._batched_loader:
            return self._batched_loader.get_cached_rider_history(rider_result_id)
        return []
    
    def get_cached_race_features(
        self, 
        competition_ids: List[int], 
        feature_table: str
    ) -> Dict[int, Dict[str, float]]:
        """Get cached race features with fallback."""
        if self.use_batched_loading and self._batched_loader:
            return self._batched_loader.get_cached_race_features(competition_ids, feature_table)
        return {}


def create_optimized_calculator_for_worker(worker_data: Dict[str, Any]) -> OptimizedRaceTypeCorrelationCalculator:
    """
    Factory function to create an optimized calculator for worker processes.
    
    This function is used by the parallel processing framework to create
    calculator instances that use cached data.
    """
    config = worker_data['calculator_config']
    
    calculator = OptimizedRaceTypeCorrelationCalculator(
        db_path=worker_data['db_path'],
        min_races_all=config.get('min_races_all', 35),
        min_races_stage=config.get('min_races_stage', 25),
        min_races_one_day=config.get('min_races_one_day', 15),
        min_races_gc=config.get('min_races_gc', 10),
        use_batched_loading=False  # Workers don't use batched loading
    )
    
    return calculator