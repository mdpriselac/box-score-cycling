import pandas as pd
import numpy as np
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json
from datetime import datetime


class EmbeddingDataPreparation:
    """Prepares data for training embedding-based prediction models."""
    
    def __init__(self, db_path: str, embedding_base_path: str = "race_type_optimized_data", 
                 use_full_embeddings: bool = False, full_embeddings_path: str = "race_type_full_embeddings"):
        """
        Initialize the data preparation class.
        
        Args:
            db_path: Path to the cycling database
            embedding_base_path: Path to the folder containing optimized embedding parquet files
            use_full_embeddings: Whether to use full embeddings instead of optimized
            full_embeddings_path: Path to the folder containing full embedding parquet files
        """
        self.db_path = db_path
        self.embedding_base_path = Path(embedding_base_path)
        self.full_embeddings_path = Path(full_embeddings_path)
        self.use_full_embeddings = use_full_embeddings
        self.race_types = ['gc', 'stage', 'one_day', 'stage_one_day', 'all']
        
        # Columns to exclude from rider_results
        self.exclude_columns = {
            'place', 'time_gap', 'bib_number', 'created_at', 'updated_at',
            'id', 'competition_id', 'rider_id', 'team_id', 'percentile'
        }
        
        # Tour level encoding
        self.tour_level_encoding = {
            'd1': 0,
            'pro': 1, 
            'wt': 2
        }
    
    def load_embeddings(self, race_type: str, percentile: Optional[str] = None) -> Tuple[pd.DataFrame, Dict]:
        """
        Load embeddings for a specific race type and return embeddings with config.
        
        Args:
            race_type: Race type to load
            percentile: For full embeddings, which percentile to use (e.g., 'race_features_90')
                       For optimized embeddings, this is ignored (uses config file)
        
        Returns:
            Tuple of (embeddings DataFrame, config dict)
        """
        if self.use_full_embeddings:
            # Load full embeddings
            if percentile is None:
                raise ValueError("percentile must be specified when using full embeddings")
            
            file_path = self.full_embeddings_path / race_type / f"{percentile}_full.parquet"
            config_path = self.full_embeddings_path / race_type / f"{race_type}_config.json"
            
            if not file_path.exists():
                raise FileNotFoundError(f"Full embedding file not found: {file_path}")
            
            embeddings = pd.read_parquet(file_path)
            
            # For full embeddings, we need to get all feature columns (not metadata)
            feature_cols = [col for col in embeddings.columns 
                          if col not in ['rider_result_id', 'n_races', 'calculation_date']]
            
            # Rename correlation columns to avoid conflict with race feature columns
            # Add 'corr_' prefix to distinguish embedding correlations from race features
            rename_mapping = {col: f'corr_{col}' for col in feature_cols}
            embeddings = embeddings.rename(columns=rename_mapping)
            
            # Update feature list with new names
            feature_cols = [f'corr_{col}' for col in feature_cols]
            
            # Create config matching optimized format
            config = {
                'percentile': percentile.replace('race_features_', ''),
                'features': feature_cols,
                'data_type': 'full_embeddings'
            }
            
            # Load additional config if exists
            if config_path.exists():
                with open(config_path, 'r') as f:
                    full_config = json.load(f)
                    config.update(full_config)
            
            print(f"Loaded {len(embeddings)} FULL embeddings for {race_type} - {percentile}")
            print(f"Using ALL {len(feature_cols)} features")
            
        else:
            # Load optimized embeddings (original behavior)
            file_path = self.embedding_base_path / f"{race_type}_optimized.parquet"
            config_path = self.embedding_base_path / f"{race_type}_config.json"
            
            if not file_path.exists():
                raise FileNotFoundError(f"Optimized embedding file not found: {file_path}")
            
            embeddings = pd.read_parquet(file_path)
            
            # Load configuration to get percentile info
            config = {}
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
            
            print(f"Loaded {len(embeddings)} OPTIMIZED embeddings for {race_type}")
            if 'percentile' in config:
                print(f"Using {config['percentile']} with {len(config.get('features', []))} selected features")
        
        return embeddings, config
    
    def load_race_features(self, percentile_table: str, feature_list: List[str]) -> pd.DataFrame:
        """Load race features from the appropriate percentile table, only including specified features."""
        import re
        
        # Always include competition_id for joining
        columns_to_select = ['competition_id']
        
        # Handle column names that start with numbers (invalid SQL identifiers)
        for feature in feature_list:
            if re.match(r'^\d', feature):  # Starts with a digit
                # Database already has columns like "20th_percentile_gap"
                # Just quote them to make them valid SQL identifiers
                columns_to_select.append(f'"{feature}"')
            else:
                columns_to_select.append(feature)
        
        # Create column selection string
        columns_str = ', '.join(columns_to_select)
        
        # Handle both formats: just number (e.g. "90") or full table name (e.g. "race_features_90")
        if percentile_table.startswith('race_features_'):
            table_name = percentile_table
        else:
            table_name = f"race_features_{percentile_table}"
        
        query = f"""
        SELECT {columns_str}
        FROM {table_name}
        """
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                df = pd.read_sql_query(query, conn)
            print(f"Loaded {len(df)} race features from {table_name} with {len(feature_list)} features: {feature_list}")
            return df
        except Exception as e:
            print(f"Warning: Could not load {table_name}: {e}")
            return pd.DataFrame()
    
    def load_rider_results_with_competition_info(self) -> pd.DataFrame:
        """Load rider results with competition information including year and tour level."""
        query = """
        SELECT 
            rr.*,
            r.category as tour_level,
            c.competition_type as competition_race_type,
            r.year
        FROM rider_results rr
        JOIN competitions c ON rr.competition_id = c.id
        JOIN races r ON c.race_id = r.id
        WHERE r.year IS NOT NULL
        """
        
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(query, conn)
        
        return df
    
    def prepare_features(self, rider_results: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare features from rider_results data.
        
        Args:
            rider_results: DataFrame with rider results
            
        Returns:
            DataFrame with prepared features
        """
        # Create a copy to avoid modifying original
        features_df = rider_results.copy()
        
        # Identify columns to keep
        # Exclude specific columns and columns ending with '_actual'
        columns_to_exclude = self.exclude_columns | {'tour_level', 'competition_race_type', 'year'}
        actual_columns = [col for col in features_df.columns if col.endswith('_actual')]
        columns_to_exclude.update(actual_columns)
        
        # Exclude timestamp/datetime columns
        timestamp_columns = [col for col in features_df.columns if 
                           'created_at' in col or 'updated_at' in col or 
                           col.endswith('_at') or features_df[col].dtype == 'object']
        columns_to_exclude.update(timestamp_columns)
        
        # Keep only numeric/boolean columns
        feature_columns = []
        for col in features_df.columns:
            if col not in columns_to_exclude:
                if features_df[col].dtype in ['int64', 'float64', 'bool', 'int32', 'float32']:
                    feature_columns.append(col)
        
        return features_df[feature_columns]
    
    def combine_embeddings_with_features(
        self, 
        embeddings: pd.DataFrame, 
        rider_results: pd.DataFrame,
        race_features: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Combine embedding data with rider result features and race features.
        
        Args:
            embeddings: DataFrame with embedding correlations
            rider_results: DataFrame with rider results and competition info
            race_features: Optional DataFrame with race features for competitions
            
        Returns:
            Combined DataFrame ready for model training
        """
        # Merge on rider_result_id
        combined = embeddings.merge(
            rider_results,
            left_on='rider_result_id',
            right_on='id',
            how='inner'
        )
        
        print(f"Combined {len(combined)} records after merging embeddings with rider results")
        
        # Add race features if provided
        if race_features is not None and len(race_features) > 0:
            # Merge with race features on competition_id
            combined = combined.merge(
                race_features,
                on='competition_id',
                how='left'
            )
            print(f"Added race features: {list(race_features.columns[1:])}")  # Skip competition_id
        
        # Encode tour level first
        combined['tour_level_encoded'] = combined['tour_level'].map(
            self.tour_level_encoding
        ).fillna(0)  # Default to d1 if missing
        
        # Prepare features from rider_results
        feature_cols_df = self.prepare_features(combined)
        
        # Combine embedding columns with prepared features
        if self.use_full_embeddings:
            # For full embeddings, all non-metadata columns are embedding features
            embedding_cols = [col for col in embeddings.columns 
                            if col not in ['rider_result_id', 'n_races', 'calculation_date']]
            # Also include n_races as it's an important feature
            embedding_cols.append('n_races')
        else:
            # For optimized embeddings, use corr_ prefix
            embedding_cols = [col for col in embeddings.columns if col.startswith('corr_') or col == 'n_races']
        
        # Add race feature columns if they exist
        race_feature_cols = []
        if race_features is not None and len(race_features) > 0:
            race_feature_cols = [col for col in race_features.columns if col != 'competition_id']
        
        # Get all feature columns
        all_feature_cols = list(set(embedding_cols + list(feature_cols_df.columns) + race_feature_cols))
        
        # Create final dataframe with features and target, preserving ID columns for stats
        final_df = combined[['rider_result_id', 'year', 'competition_race_type', 
                           'uci_points_proportional', 'competition_id', 'rider_id'] + all_feature_cols].copy()
        
        return final_df
    
    def prepare_race_type_data(
        self, 
        race_type: str,
        min_year: Optional[int] = None,
        max_year: Optional[int] = None,
        percentile: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Prepare complete dataset for a specific race type.
        
        Args:
            race_type: One of ['gc', 'stage', 'one_day', 'stage_one_day', 'all']
            min_year: Minimum year to include (inclusive)
            max_year: Maximum year to include (inclusive)
            percentile: For full embeddings, which percentile to use (e.g., 'race_features_90')
            
        Returns:
            DataFrame ready for model training
        """
        # Load embeddings and config
        embeddings, config = self.load_embeddings(race_type, percentile=percentile)
        
        # Load race features if config contains percentile and feature information
        race_features = None
        if 'percentile' in config and 'features' in config:
            percentile_table = config['percentile']
            if self.use_full_embeddings:
                # For full embeddings, remove 'corr_' prefix to get original feature names
                feature_list = [fname.replace('corr_', '') for fname in config['features']]
            else:
                # For optimized embeddings, use features as-is
                feature_list = config['features']
            race_features = self.load_race_features(percentile_table, feature_list)
        
        # Load rider results with competition info
        rider_results = self.load_rider_results_with_competition_info()
        
        # Filter by race type if not 'all'
        if race_type != 'all':
            if race_type == 'stage_one_day':
                rider_results = rider_results[
                    rider_results['competition_race_type'].isin(['stage', 'one_day'])
                ]
            else:
                # Map race_type to competition_type
                race_type_mapping = {
                    'gc': 'gc',
                    'stage': 'stage', 
                    'one_day': 'one_day'
                }
                comp_type = race_type_mapping.get(race_type, race_type)
                rider_results = rider_results[
                    rider_results['competition_race_type'] == comp_type
                ]
        
        # Filter by year if specified
        if min_year is not None:
            rider_results = rider_results[rider_results['year'] >= min_year]
        if max_year is not None:
            rider_results = rider_results[rider_results['year'] <= max_year]
        
        # Combine embeddings with features and race features
        combined_data = self.combine_embeddings_with_features(embeddings, rider_results, race_features)
        
        print(f"Prepared {len(combined_data)} samples for {race_type} model")
        if min_year or max_year:
            year_range = f"{min_year or 'start'} to {max_year or 'end'}"
            print(f"Year range: {year_range}")
        
        return combined_data
    
    def split_by_year(
        self, 
        data: pd.DataFrame, 
        test_year: int
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Split data into train and test sets based on year.
        
        Args:
            data: Combined data with 'year' column
            test_year: Year to use for testing
            
        Returns:
            Tuple of (train_df, test_df)
        """
        train_df = data[data['year'] < test_year].copy()
        test_df = data[data['year'] == test_year].copy()
        
        print(f"Train set: {len(train_df)} samples (years < {test_year})")
        print(f"Test set: {len(test_df)} samples (year = {test_year})")
        
        return train_df, test_df
    
    def get_dataset_stats(self, df: pd.DataFrame) -> Dict:
        """Get statistics about a dataset."""
        stats = {
            'n_samples': len(df),
            'n_competitions': int(df['competition_id'].nunique()) if 'competition_id' in df.columns else 0,
            'n_riders': int(df['rider_id'].nunique()) if 'rider_id' in df.columns else 0,
            'years': sorted([int(x) for x in df['year'].unique()]) if 'year' in df else [],
            'target_stats': {
                'mean': float(df['uci_points_proportional'].iloc[:, 0].mean() if isinstance(df['uci_points_proportional'], pd.DataFrame) else df['uci_points_proportional'].mean()),
                'std': float(df['uci_points_proportional'].iloc[:, 0].std() if isinstance(df['uci_points_proportional'], pd.DataFrame) else df['uci_points_proportional'].std()),
                'min': float(df['uci_points_proportional'].iloc[:, 0].min() if isinstance(df['uci_points_proportional'], pd.DataFrame) else df['uci_points_proportional'].min()),
                'max': float(df['uci_points_proportional'].iloc[:, 0].max() if isinstance(df['uci_points_proportional'], pd.DataFrame) else df['uci_points_proportional'].max()),
                'zero_rate': float((df['uci_points_proportional'].iloc[:, 0] == 0).mean() if isinstance(df['uci_points_proportional'], pd.DataFrame) else (df['uci_points_proportional'] == 0).mean())
            }
        }
        
        return stats