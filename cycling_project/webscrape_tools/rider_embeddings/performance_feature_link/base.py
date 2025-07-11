from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from datetime import datetime
import sqlite3
from pathlib import Path


class PerformanceFeatureLinkBase(ABC):
    """
    Abstract base class for linking rider performance to race features.
    
    All performance-feature linking methods must inherit from this class
    and implement the calculate_feature_relationships method.
    """
    
    def __init__(self, db_path: str):
        """
        Initialize the performance-feature linker.
        
        Args:
            db_path: Path to the cycling races database
        """
        self.db_path = db_path
        self._validate_db_path()
        
    def _validate_db_path(self):
        """Validate that the database exists and is accessible."""
        if not Path(self.db_path).exists():
            raise ValueError(f"Database not found at {self.db_path}")
            
    def get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        return sqlite3.connect(self.db_path)
    
    @abstractmethod
    def calculate_feature_relationships(
        self, 
        rider_result_id: int,
        lookback_date: str,
        feature_tables: List[str]
    ) -> Dict[str, Any]:
        """
        Calculate the relationship between rider performance and race features.
        
        This method must be implemented by all subclasses.
        
        Args:
            rider_result_id: ID from the rider_results table
            lookback_date: Date string (YYYY-MM-DD) to calculate history up to
            feature_tables: List of race_features_N tables to analyze
                           e.g., ['race_features_100', 'race_features_80']
        
        Returns:
            Dictionary with structure:
            {
                'rider_result_id': int,
                'feature_correlations': {
                    'race_features_100': {
                        'variance_normalized': float,
                        'gini_coefficient': float,
                        # ... all other features
                    },
                    'race_features_80': {...}
                },
                'metadata': {
                    'n_races': int,  # number of historical races used
                    'method': str,   # name of the method used
                    'calculation_date': datetime,
                    'warnings': List[str]  # any warnings or issues
                }
            }
        """
        pass
    
    def get_rider_history(
        self, 
        rider_id: int, 
        lookback_date: str
    ) -> List[Dict[str, Any]]:
        """
        Get historical race results for a rider up to a specific date.
        
        Args:
            rider_id: The rider's ID
            lookback_date: Date string (YYYY-MM-DD) to look back from
            
        Returns:
            List of dictionaries containing historical race data
        """
        query = """
        SELECT 
            rr.competition_id,
            rr.place,
            rr.uci_points_proportional,
            c.date as competition_date,
            c.competition_type,
            c.race_id,
            r.category as race_level
        FROM rider_results rr
        JOIN competitions c ON rr.competition_id = c.id
        JOIN races r ON c.race_id = r.id
        WHERE rr.rider_id = ?
        AND c.date < ?
        ORDER BY c.date DESC
        """
        
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, (rider_id, lookback_date))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_race_features(
        self, 
        competition_ids: List[int], 
        feature_table: str
    ) -> Dict[int, Dict[str, float]]:
        """
        Get race features for a list of competitions from a specific feature table.
        
        Args:
            competition_ids: List of competition IDs
            feature_table: Name of the race_features_N table
            
        Returns:
            Dictionary mapping competition_id to feature values
        """
        if not competition_ids:
            return {}
            
        placeholders = ','.join(['?' for _ in competition_ids])
        
        # Get all numeric columns except IDs and metadata
        exclude_cols = {
            'id', 'competition_id', 'extraction_date', 'competition_name',
            'competition_type', 'race_id', 'race_name', 'race_category',
            'race_year', 'race_date', 'percentile_analyzed'
        }
        
        with self.get_connection() as conn:
            # Get column names
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({feature_table})")
            all_cols = [row[1] for row in cursor.fetchall()]
            feature_cols = [col for col in all_cols if col not in exclude_cols]
            
            # Get feature data - quote column names to handle those starting with numbers
            quoted_cols = [f'`{col}`' for col in feature_cols]
            query = f"""
            SELECT competition_id, {', '.join(quoted_cols)}
            FROM {feature_table}
            WHERE competition_id IN ({placeholders})
            """
            
            # Set row factory for dictionary access
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()  # Get new cursor with row factory
            cursor.execute(query, competition_ids)
            
            result = {}
            for row in cursor.fetchall():
                comp_id = row['competition_id']
                result[comp_id] = {col: row[col] for col in feature_cols}
                
            return result
    
    def validate_feature_tables(self, feature_tables: List[str]) -> List[str]:
        """
        Validate that the requested feature tables exist in the database.
        
        Args:
            feature_tables: List of table names to validate
            
        Returns:
            List of valid table names
            
        Raises:
            ValueError if no valid tables found
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'race_features_%'"
            )
            existing_tables = {row[0] for row in cursor.fetchall()}
            
        valid_tables = [t for t in feature_tables if t in existing_tables]
        
        if not valid_tables:
            raise ValueError(
                f"No valid feature tables found. Requested: {feature_tables}, "
                f"Available: {sorted(existing_tables)}"
            )
            
        return valid_tables