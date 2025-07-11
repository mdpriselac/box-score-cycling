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
from rider_embeddings.performance_feature_link.base import PerformanceFeatureLinkBase


class RaceTypeCorrelationCalculator(PerformanceFeatureLinkBase):
    """
    Calculate correlations between rider performance and race features, segmented by race type.
    
    This method calculates separate correlations for:
    - GC (General Classification) races
    - Stage races
    - One-day races
    - Stage/One-day combined
    - All races combined
    
    Uses Spearman correlation to measure relationships between points earned
    and race characteristics across different race types.
    """
    
    # Race type definitions
    RACE_TYPES = {
        'gc': ['gc'],
        'stage': ['stage'],
        'one_day': ['one_day'],
        'stage_one_day': ['stage', 'one_day'],
        'all': ['gc', 'stage', 'one_day']
    }
    
    def __init__(
        self, 
        db_path: str, 
        min_races_all: int = 35,
        min_races_stage: int = 25,
        min_races_one_day: int = 15,
        min_races_gc: int = 10
    ):
        """
        Initialize the race type correlation calculator.
        
        Args:
            db_path: Path to the cycling races database
            min_races_all: Minimum races required for all-race correlations
            min_races_stage: Minimum races required for stage correlations
            min_races_one_day: Minimum races required for one-day correlations
            min_races_gc: Minimum races required for GC correlations
        """
        super().__init__(db_path)
        self.min_races = {
            'gc': min_races_gc,
            'stage': min_races_stage,
            'one_day': min_races_one_day,
            'stage_one_day': min_races_one_day,  # Use one_day minimum
            'all': min_races_all
        }
        
    def calculate_feature_relationships(
        self, 
        rider_result_id: int,
        lookback_date: str,
        feature_tables: List[str]
    ) -> Dict[str, Any]:
        """
        Calculate correlations between rider performance and race features by race type.
        
        Args:
            rider_result_id: ID from the rider_results table
            lookback_date: Date string (YYYY-MM-DD) to calculate history up to
            feature_tables: List of race_features_N tables to analyze
            
        Returns:
            Dictionary with correlation results for each race type and feature table
        """
        # Validate feature tables
        valid_tables = self.validate_feature_tables(feature_tables)
        
        # Get rider ID from rider_result
        rider_id = self._get_rider_id(rider_result_id)
        if rider_id is None:
            return self._empty_result(rider_result_id, "Rider result not found")
        
        # Get rider's full historical data
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
                correlations, table_warnings = self._calculate_table_correlations(
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
                'method': 'race_type_correlation',
                'calculation_date': datetime.now(),
                'warnings': warnings_list
            }
        }
    
    def _get_rider_id(self, rider_result_id: int) -> Optional[int]:
        """Get rider ID from a rider_result ID."""
        query = "SELECT rider_id FROM rider_results WHERE id = ?"
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (rider_result_id,))
            result = cursor.fetchone()
            return result[0] if result else None
    
    def _segment_history_by_race_type(
        self, 
        full_history: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Segment rider history by race type.
        
        Args:
            full_history: Complete rider history
            
        Returns:
            Dictionary mapping race type to filtered history
        """
        segmented = {}
        
        for race_type, competition_types in self.RACE_TYPES.items():
            if race_type == 'all':
                segmented[race_type] = full_history
            else:
                segmented[race_type] = [
                    h for h in full_history 
                    if h['competition_type'] in competition_types
                ]
        
        return segmented
    
    def _calculate_table_correlations(
        self, 
        history: List[Dict[str, Any]], 
        feature_table: str,
        race_type: str
    ) -> Tuple[Dict[str, float], List[str]]:
        """
        Calculate correlations for a specific feature table and race type.
        
        Returns:
            Tuple of (correlations dict, warnings list)
        """
        # Get competition IDs from history
        competition_ids = [h['competition_id'] for h in history]
        
        # Get race features
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
    
    def _empty_result(self, rider_result_id: int, warning: str) -> Dict[str, Any]:
        """Create an empty result with a warning."""
        return {
            'rider_result_id': rider_result_id,
            'feature_correlations': {},
            'metadata': {
                'n_races': {race_type: 0 for race_type in self.RACE_TYPES},
                'method': 'race_type_correlation',
                'calculation_date': datetime.now(),
                'warnings': [warning]
            }
        }
    
    def batch_calculate(
        self,
        rider_result_ids: List[int],
        feature_tables: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Calculate correlations for multiple rider results efficiently.
        
        Args:
            rider_result_ids: List of rider_result IDs to process
            feature_tables: List of race_features_N tables to analyze
            
        Returns:
            List of correlation results
        """
        # Get all rider results data
        query = """
        SELECT rr.id, rr.rider_id, c.date as competition_date
        FROM rider_results rr
        JOIN competitions c ON rr.competition_id = c.id
        WHERE rr.id IN ({})
        """.format(','.join(['?' for _ in rider_result_ids]))
        
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, rider_result_ids)
            rider_data = {row['id']: dict(row) for row in cursor.fetchall()}
        
        # Process each rider result
        results = []
        for rr_id in rider_result_ids:
            if rr_id in rider_data:
                lookback_date = rider_data[rr_id]['competition_date']
                result = self.calculate_feature_relationships(
                    rr_id, lookback_date, feature_tables
                )
            else:
                result = self._empty_result(rr_id, "Rider result not found")
            
            results.append(result)
        
        return results
    
    def get_race_type_summary(self, rider_id: int, lookback_date: str) -> Dict[str, int]:
        """
        Get a summary of race counts by type for a rider up to a date.
        
        Args:
            rider_id: The rider's ID
            lookback_date: Date string (YYYY-MM-DD) to look back from
            
        Returns:
            Dictionary mapping race type to count
        """
        history = self.get_rider_history(rider_id, lookback_date)
        segmented = self._segment_history_by_race_type(history)
        
        return {
            race_type: len(races) 
            for race_type, races in segmented.items()
        }