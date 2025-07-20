"""
Optimized data loader using blob storage for correlation analysis.
"""

import sqlite3
import pandas as pd
import numpy as np
import gzip
from typing import Dict, List, Optional
from . import config


class BlobCorrelationDataLoader:
    """Optimized data loader using blob storage"""
    
    def __init__(self, db_path: str):
        """
        Initialize the blob data loader.
        
        Args:
            db_path: Path to the SQLite database
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
    
    def load_complete_correlation_data(self, correlation_type: str) -> pd.DataFrame:
        """
        Load complete correlation dataset from blob table.
        
        This replaces the need for multiple feature-specific queries.
        
        Args:
            correlation_type: Type of correlation ('all_races', 'same_type', 'stage_one_days')
            
        Returns:
            DataFrame with all correlation data in denormalized format
        """
        print(f"Loading complete correlation dataset: {correlation_type}")
        
        # Load blob data from database
        blob_query = """
        SELECT rider_result_id, competition_id, rider_id, correlation_matrix, race_count
        FROM rider_correlations_blob 
        WHERE correlation_type = ?
        """
        
        print("Loading blob data from database...")
        blob_df = pd.read_sql_query(blob_query, self.conn, params=[correlation_type])
        print(f"✓ Loaded {len(blob_df):,} blob rows")
        
        # Decompress and convert to analysis format
        print("Decompressing correlation matrices...")
        all_rows = []
        failed_count = 0
        
        for idx, row in blob_df.iterrows():
            try:
                # Decompress blob
                blob = row['correlation_matrix']
                decompressed = gzip.decompress(blob)
                matrix = np.frombuffer(decompressed, dtype=np.float64).reshape(8, 37)
                
                # Convert to denormalized format
                for percentile_idx, percentile in enumerate(config.PERCENTILES):
                    for feature_idx, feature_name in enumerate(config.RACE_FEATURES):
                        correlation_value = matrix[percentile_idx, feature_idx]
                        
                        # Only include non-NaN values
                        if not np.isnan(correlation_value):
                            all_rows.append({
                                'rider_result_id': row['rider_result_id'],
                                'competition_id': row['competition_id'],
                                'rider_id': row['rider_id'],
                                'correlation_type': correlation_type,
                                'percentile': percentile,
                                'feature_idx': feature_idx,
                                'feature_name': feature_name,
                                'correlation_value': correlation_value,
                                'race_count': row['race_count']
                            })
            
            except Exception as e:
                failed_count += 1
                continue
            
            # Progress update
            if (idx + 1) % 50000 == 0:
                print(f"  Processed {idx + 1:,} / {len(blob_df):,} blobs")
        
        if failed_count > 0:
            print(f"⚠ Failed to decompress {failed_count} blobs")
        
        # Create final DataFrame
        print("Creating final DataFrame...")
        result_df = pd.DataFrame(all_rows)
        
        print(f"✓ Complete dataset: {len(result_df):,} correlation values")
        print(f"  Memory usage: {result_df.memory_usage(deep=True).sum() / 1024 / 1024:.1f} MB")
        print(f"  Features: {result_df['feature_name'].nunique()}")
        print(f"  Competitions: {result_df['competition_id'].nunique():,}")
        
        return result_df
    
    def get_feature_data(self, complete_data: pd.DataFrame, feature_name: str) -> pd.DataFrame:
        """
        Extract data for a specific feature from complete dataset.
        
        Args:
            complete_data: Complete correlation dataset
            feature_name: Name of the feature to extract
            
        Returns:
            DataFrame with data for the specified feature
        """
        return complete_data[complete_data['feature_name'] == feature_name].copy()
    
    def get_percentile_data(self, complete_data: pd.DataFrame, percentile: int) -> pd.DataFrame:
        """
        Extract data for a specific percentile from complete dataset.
        
        Args:
            complete_data: Complete correlation dataset
            percentile: Percentile to extract (30, 40, ..., 100)
            
        Returns:
            DataFrame with data for the specified percentile
        """
        return complete_data[complete_data['percentile'] == percentile].copy()
    
    def filter_by_competition_type(self, complete_data: pd.DataFrame, 
                                 competition_type: str) -> pd.DataFrame:
        """
        Filter correlation data by competition type (GC, stage, one-day).
        
        Note: This requires a JOIN with competitions table and may be slower.
        For better performance, consider pre-filtering during blob loading.
        
        Args:
            complete_data: Complete correlation dataset
            competition_type: Type of competition ('gc', 'stage', 'one_day')
            
        Returns:
            Filtered DataFrame
        """
        # Get competition IDs for the specified type
        comp_query = """
        SELECT id FROM competitions WHERE competition_type = ?
        """
        comp_ids = pd.read_sql_query(comp_query, self.conn, params=[competition_type])['id'].tolist()
        
        # Filter correlation data
        return complete_data[complete_data['competition_id'].isin(comp_ids)].copy()
    
    def get_data_summary(self, complete_data: pd.DataFrame) -> Dict:
        """
        Get summary statistics for the complete dataset.
        
        Args:
            complete_data: Complete correlation dataset
            
        Returns:
            Dictionary with summary statistics
        """
        return {
            'total_rows': len(complete_data),
            'unique_features': complete_data['feature_name'].nunique(),
            'unique_percentiles': sorted(complete_data['percentile'].unique()),
            'unique_competitions': complete_data['competition_id'].nunique(),
            'unique_riders': complete_data['rider_id'].nunique(),
            'correlation_range': (
                complete_data['correlation_value'].min(),
                complete_data['correlation_value'].max()
            ),
            'race_count_range': (
                complete_data['race_count'].min(),
                complete_data['race_count'].max()
            ),
            'memory_usage_mb': complete_data.memory_usage(deep=True).sum() / 1024 / 1024
        }
    
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