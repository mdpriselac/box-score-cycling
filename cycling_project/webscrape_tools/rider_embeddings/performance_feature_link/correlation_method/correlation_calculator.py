import numpy as np
from scipy import stats
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import warnings
import sys
import sqlite3
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent.parent))
from rider_embeddings.performance_feature_link.base import PerformanceFeatureLinkBase


class CorrelationCalculator(PerformanceFeatureLinkBase):
    """
    Calculate correlations between rider performance and race features.
    
    Uses Spearman correlation to measure the relationship between points earned
    and race characteristics across a rider's historical performances.
    """
    
    def __init__(self, db_path: str, min_races: int = 5):
        """
        Initialize the correlation calculator.
        
        Args:
            db_path: Path to the cycling races database
            min_races: Minimum number of races required for correlation calculation
        """
        super().__init__(db_path)
        self.min_races = min_races
        
    def calculate_feature_relationships(
        self, 
        rider_result_id: int,
        lookback_date: str,
        feature_tables: List[str]
    ) -> Dict[str, Any]:
        """
        Calculate correlations between rider performance and race features.
        
        Args:
            rider_result_id: ID from the rider_results table
            lookback_date: Date string (YYYY-MM-DD) to calculate history up to
            feature_tables: List of race_features_N tables to analyze
            
        Returns:
            Dictionary with correlation results for each feature table
        """
        # Validate feature tables
        valid_tables = self.validate_feature_tables(feature_tables)
        
        # Get rider ID from rider_result
        rider_id = self._get_rider_id(rider_result_id)
        if rider_id is None:
            return self._empty_result(rider_result_id, "Rider result not found")
        
        # Get rider's historical data
        history = self.get_rider_history(rider_id, lookback_date)
        
        # Check if enough history
        if len(history) < self.min_races:
            return self._empty_result(
                rider_result_id, 
                f"Insufficient history: {len(history)} races (minimum {self.min_races} required)"
            )
        
        # Calculate correlations for each feature table
        feature_correlations = {}
        warnings_list = []
        
        for feature_table in valid_tables:
            correlations, table_warnings = self._calculate_table_correlations(
                history, feature_table
            )
            feature_correlations[feature_table] = correlations
            warnings_list.extend(table_warnings)
        
        return {
            'rider_result_id': rider_result_id,
            'feature_correlations': feature_correlations,
            'metadata': {
                'n_races': len(history),
                'method': 'correlation',
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
    
    def _calculate_table_correlations(
        self, 
        history: List[Dict[str, Any]], 
        feature_table: str
    ) -> Tuple[Dict[str, float], List[str]]:
        """
        Calculate correlations for a specific feature table.
        
        Returns:
            Tuple of (correlations dict, warnings list)
        """
        # Get competition IDs from history
        competition_ids = [h['competition_id'] for h in history]
        
        # Get race features
        features_data = self.get_race_features(competition_ids, feature_table)
        
        # Filter history to only include races with feature data
        valid_history = [h for h in history if h['competition_id'] in features_data]
        
        if len(valid_history) < self.min_races:
            return {}, [f"{feature_table}: Only {len(valid_history)} races with feature data"]
        
        # Extract performance data (points)
        points = np.array([h['uci_points_proportional'] for h in valid_history])
        
        # Check for zero variance in points
        if np.std(points) == 0:
            return {}, [f"{feature_table}: No variance in performance data"]
        
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
            if np.sum(~np.isnan(feature_array)) >= self.min_races:
                # Remove any rows with NaN values
                valid_mask = ~(np.isnan(feature_array) | np.isnan(points))
                valid_points = points[valid_mask]
                valid_features = feature_array[valid_mask]
                
                # Check for variance in both feature and points
                if (len(valid_features) >= self.min_races and 
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
                'n_races': 0,
                'method': 'correlation',
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