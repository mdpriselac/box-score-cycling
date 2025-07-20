"""
Data loader module for correlation feature analysis.

Handles all database interactions and data loading operations.
"""

import sqlite3
import pandas as pd
from typing import Iterator, List, Optional, Dict
from pathlib import Path


class CorrelationDataLoader:
    """Handles all database interactions and data loading"""
    
    def __init__(self, db_path: str):
        """
        Initialize the data loader with database connection.
        
        Args:
            db_path: Path to the SQLite database
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        
    def load_correlation_data(self, correlation_type: str, 
                            chunk_size: int = 100000) -> Iterator[pd.DataFrame]:
        """
        Load correlation data in chunks to manage memory efficiently.
        
        Args:
            correlation_type: Type of correlation ('all_races', 'same_type', 'stage_one_days')
            chunk_size: Number of rows to load per chunk
            
        Yields:
            DataFrame chunks of correlation data
        """
        query = """
        WITH feature_data AS (
            SELECT 
                feature_name,
                percentile,
                correlation_value,
                race_count,
                COUNT(*) OVER (PARTITION BY feature_name, percentile) as total_count,
                SUM(CASE WHEN correlation_value IS NULL THEN 1 ELSE 0 END) 
                    OVER (PARTITION BY feature_name, percentile) as null_count
            FROM rider_correlations_denorm
            WHERE correlation_type = ?
        )
        SELECT * FROM feature_data
        WHERE correlation_value IS NOT NULL
        ORDER BY feature_name, percentile
        """
        
        for chunk in pd.read_sql_query(query, self.conn, 
                                      params=[correlation_type], 
                                      chunksize=chunk_size):
            yield chunk
    
    def get_feature_list(self) -> List[str]:
        """
        Get list of all features in database.
        
        Returns:
            List of feature names
        """
        query = """
        SELECT DISTINCT feature_name 
        FROM rider_correlations_denorm 
        ORDER BY feature_idx
        """
        
        result = pd.read_sql_query(query, self.conn)
        return result['feature_name'].tolist()
    
    def get_available_percentiles(self) -> List[int]:
        """
        Get list of available percentiles.
        
        Returns:
            List of percentile values
        """
        query = """
        SELECT DISTINCT percentile 
        FROM rider_correlations_denorm 
        ORDER BY percentile
        """
        
        result = pd.read_sql_query(query, self.conn)
        return result['percentile'].tolist()
    
    def get_correlation_types(self) -> List[str]:
        """
        Get list of available correlation types.
        
        Returns:
            List of correlation type names
        """
        query = """
        SELECT DISTINCT correlation_type 
        FROM rider_correlations_denorm 
        ORDER BY correlation_type
        """
        
        result = pd.read_sql_query(query, self.conn)
        return result['correlation_type'].tolist()
    
    def get_data_quality_summary(self, correlation_type: Optional[str] = None) -> pd.DataFrame:
        """
        Get quick summary of data availability and quality.
        
        Args:
            correlation_type: Optional filter by correlation type
            
        Returns:
            DataFrame with data quality metrics
        """
        where_clause = ""
        params = []
        
        if correlation_type:
            where_clause = "WHERE correlation_type = ?"
            params = [correlation_type]
        
        query = f"""
        SELECT 
            correlation_type,
            AVG(data_completeness) as avg_completeness,
            AVG(races_with_features) as avg_races_with_features,
            COUNT(*) as total_correlations,
            MIN(races_with_features) as min_races,
            MAX(races_with_features) as max_races
        FROM correlation_data_quality
        {where_clause}
        GROUP BY correlation_type
        """
        
        return pd.read_sql_query(query, self.conn, params=params)
    
    def get_feature_sample_sizes(self, correlation_type: str) -> pd.DataFrame:
        """
        Get sample sizes for each feature-percentile combination.
        
        Args:
            correlation_type: Type of correlation to analyze
            
        Returns:
            DataFrame with sample size information
        """
        query = """
        SELECT 
            feature_name,
            percentile,
            COUNT(*) as sample_size,
            SUM(CASE WHEN correlation_value IS NOT NULL THEN 1 ELSE 0 END) as non_null_count,
            AVG(race_count) as avg_race_count
        FROM rider_correlations_denorm
        WHERE correlation_type = ?
        GROUP BY feature_name, percentile
        ORDER BY feature_name, percentile
        """
        
        return pd.read_sql_query(query, self.conn, params=[correlation_type])
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()