from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from datetime import datetime
import sqlite3
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))
from rider_embeddings.performance_feature_link.base import PerformanceFeatureLinkBase
from rider_embeddings.performance_optimization.batched_database_loader import BatchedDatabaseLoader


class OptimizedPerformanceFeatureLinkBase(PerformanceFeatureLinkBase):
    """
    Optimized base class that uses batched database loading for improved performance.
    
    This class maintains the same interface as PerformanceFeatureLinkBase but uses
    cached data instead of individual database queries.
    """
    
    def __init__(self, db_path: str, use_batched_loading: bool = True):
        """
        Initialize the optimized performance-feature linker.
        
        Args:
            db_path: Path to the cycling races database
            use_batched_loading: Whether to use batched loading (default: True)
        """
        super().__init__(db_path)
        self.use_batched_loading = use_batched_loading
        self._batched_loader: Optional[BatchedDatabaseLoader] = None
        
        if self.use_batched_loading:
            self._batched_loader = BatchedDatabaseLoader(db_path)
    
    def initialize_batch_cache(
        self, 
        rider_result_ids: List[int], 
        feature_tables: List[str],
        max_lookback_date: str = "2025-01-01"
    ) -> None:
        """
        Initialize the batch cache with data for the specified riders and features.
        
        Args:
            rider_result_ids: List of rider_result IDs to cache data for
            feature_tables: List of feature tables to cache
            max_lookback_date: Maximum lookback date for rider histories
        """
        if not self.use_batched_loading or not self._batched_loader:
            return
        
        self._batched_loader.preload_all_data(
            rider_result_ids, 
            feature_tables, 
            max_lookback_date
        )
    
    def get_rider_history_optimized(
        self, 
        rider_result_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get historical race results using cached data when available.
        
        Args:
            rider_result_id: The rider result ID (not rider_id)
            
        Returns:
            List of dictionaries containing historical race data
        """
        if self.use_batched_loading and self._batched_loader:
            return self._batched_loader.get_cached_rider_history(rider_result_id)
        else:
            # Fallback to original method - need to get rider_id first
            rider_id = self._get_rider_id_from_result(rider_result_id)
            lookback_date = self._get_competition_date(rider_result_id)
            if rider_id and lookback_date:
                return self.get_rider_history(rider_id, lookback_date)
            return []
    
    def get_race_features_optimized(
        self, 
        competition_ids: List[int], 
        feature_table: str
    ) -> Dict[int, Dict[str, float]]:
        """
        Get race features using cached data when available.
        
        Args:
            competition_ids: List of competition IDs
            feature_table: Name of the race_features_N table
            
        Returns:
            Dictionary mapping competition_id to feature values
        """
        if self.use_batched_loading and self._batched_loader:
            return self._batched_loader.get_cached_race_features(competition_ids, feature_table)
        else:
            # Fallback to original method
            return self.get_race_features(competition_ids, feature_table)
    
    def _get_rider_id_from_result(self, rider_result_id: int) -> Optional[int]:
        """Get rider ID from a rider_result ID."""
        query = "SELECT rider_id FROM rider_results WHERE id = ?"
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (rider_result_id,))
            result = cursor.fetchone()
            return result[0] if result else None
    
    def _get_competition_date(self, rider_result_id: int) -> Optional[str]:
        """Get competition date for a rider_result ID."""
        query = """
        SELECT c.date 
        FROM rider_results rr
        JOIN competitions c ON rr.competition_id = c.id
        WHERE rr.id = ?
        """
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (rider_result_id,))
            result = cursor.fetchone()
            return result[0] if result else None
    
    def get_cache_statistics(self) -> Optional[Dict[str, Any]]:
        """
        Get cache statistics if using batched loading.
        
        Returns:
            Cache statistics or None if not using batched loading
        """
        if self.use_batched_loading and self._batched_loader:
            return self._batched_loader.get_cache_stats()
        return None
    
    def clear_cache(self) -> None:
        """Clear the batch cache to free memory."""
        if self.use_batched_loading and self._batched_loader:
            self._batched_loader.clear_cache()
    
    def set_batched_loading(self, enabled: bool) -> None:
        """
        Enable or disable batched loading.
        
        Args:
            enabled: Whether to use batched loading
        """
        self.use_batched_loading = enabled
        
        if enabled and not self._batched_loader:
            self._batched_loader = BatchedDatabaseLoader(self.db_path)
        elif not enabled:
            if self._batched_loader:
                self._batched_loader.clear_cache()
            self._batched_loader = None


class BatchedCorrelationCalculatorMixin:
    """
    Mixin class to add batched loading capabilities to correlation calculators.
    
    This mixin provides methods to integrate batched loading into existing
    correlation calculator classes.
    """
    
    def enable_batch_processing(
        self, 
        rider_result_ids: List[int], 
        feature_tables: List[str],
        max_lookback_date: str = "2025-01-01"
    ) -> None:
        """
        Enable batch processing for the specified data.
        
        Args:
            rider_result_ids: List of rider_result IDs to process
            feature_tables: List of feature tables to use
            max_lookback_date: Maximum lookback date for histories
        """
        if hasattr(self, 'initialize_batch_cache'):
            self.initialize_batch_cache(rider_result_ids, feature_tables, max_lookback_date)
    
    def disable_batch_processing(self) -> None:
        """Disable batch processing and clear cache."""
        if hasattr(self, 'set_batched_loading'):
            self.set_batched_loading(False)
        if hasattr(self, 'clear_cache'):
            self.clear_cache()
    
    def get_processing_stats(self) -> Optional[Dict[str, Any]]:
        """Get batch processing statistics."""
        if hasattr(self, 'get_cache_statistics'):
            return self.get_cache_statistics()
        return None