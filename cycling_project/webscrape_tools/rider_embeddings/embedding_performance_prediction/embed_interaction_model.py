import numpy as np
import pandas as pd
import lightgbm as lgb
from typing import Dict, List, Optional, Tuple, Union, Set
import json
from pathlib import Path
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score, roc_auc_score
import sqlite3


class EmbeddingInteractionPerformanceModel:
    """Two-stage LightGBM model for rider performance prediction using embeddings and interaction features."""
    
    def __init__(
        self, 
        race_type: str,
        db_path: str,
        feature_config: Optional[Dict] = None,
        random_state: int = 42
    ):
        """
        Initialize the embedding interaction performance model.
        
        Args:
            race_type: One of ['gc', 'stage', 'one_day', 'stage_one_day', 'all']
            db_path: Path to the cycling database
            feature_config: Configuration for which features to include. If None, uses defaults.
                Keys:
                    - use_rider_database: bool (default True)
                    - use_race_database: bool (default True)
                    - use_race_features: bool (default False)
                    - use_rider_embeddings: bool (default False)
                    - embedding_type: 'full' or 'optimized' (default 'optimized')
                    - embedding_percentile: str like 'race_features_70' (for full embeddings)
                    - use_interaction_features: bool (default True)
                    - interaction_types: List[str] from ['dot_product', 'cosine_similarity', 'hadamard'] 
                                       (default all three)
                    - interaction_percentile: str like '70' or 'all' (default '70')
            random_state: Random seed for reproducibility
        """
        self.race_type = race_type
        self.db_path = db_path
        self.random_state = random_state
        
        # Default feature configuration
        default_config = {
            'use_rider_database': True,
            'use_race_database': True,
            'use_race_features': False,
            'use_rider_embeddings': False,
            'embedding_type': 'optimized',
            'embedding_percentile': None,
            'use_interaction_features': True,
            'interaction_types': ['dot_product', 'cosine_similarity', 'hadamard'],
            'interaction_percentile': '70'
        }
        
        # Update with user config
        self.feature_config = default_config
        if feature_config:
            self.feature_config.update(feature_config)
        
        # Model components
        self.classifier = None
        self.regressor = None
        
        # Feature information
        self.feature_columns = None
        self.feature_groups = {
            'rider_database': [],
            'race_database': [],
            'race_features': [],
            'rider_embeddings': [],
            'interaction_features': []
        }
        
        # Training information
        self.training_info = None
        
        # Model parameters (following existing patterns)
        self.classifier_params = {
            'objective': 'binary',
            'boosting_type': 'gbdt',
            'num_leaves': 31,
            'learning_rate': 0.05,
            'feature_fraction': 0.9,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'verbose': -1,
            'random_state': random_state,
            'is_unbalance': True,
            'min_child_samples': 20
        }
        
        self.regressor_params = {
            'objective': 'regression',
            'boosting_type': 'gbdt',
            'num_leaves': 63,
            'learning_rate': 0.05,
            'feature_fraction': 0.9,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'verbose': -1,
            'random_state': random_state,
            'reg_alpha': 0.1,
            'reg_lambda': 0.1,
            'min_child_samples': 10
        }
        
        # Classification threshold
        self.classification_threshold = 0.2
        
        # Tour level encoding
        self.tour_level_encoding = {
            'd1': 0,
            'pro': 1,
            'wt': 2
        }
        
        # Rider database features to extract
        self.rider_database_features = [
            'rider_age', 'prior_wt_points_proportional', 'prior_pro_points_proportional',
            'prior_d1_points_proportional', 'prior_gc_points_proportional',
            'prior_stage_points_proportional', 'prior_one_day_points_proportional',
            'prior_wt_races', 'prior_pro_races', 'prior_d1_races',
            'prior_gc_races', 'prior_stage_races', 'prior_one_day_races'
        ]
    
    def _load_rider_results_with_info(self) -> pd.DataFrame:
        """Load rider results with competition and race information."""
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
    
    def _extract_rider_database_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract the 13 rider database features from rider_results."""
        features = []
        
        for col in self.rider_database_features:
            if col in df.columns:
                features.append(col)
                self.feature_groups['rider_database'].append(col)
        
        return df[features] if features else pd.DataFrame(index=df.index)
    
    def _extract_race_database_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract and encode race database features (tour level)."""
        if 'tour_level' not in df.columns:
            return pd.DataFrame(index=df.index)
        
        # Encode tour level
        tour_level_encoded = df['tour_level'].map(self.tour_level_encoding).fillna(0)
        feature_df = pd.DataFrame({'tour_level_encoded': tour_level_encoded}, index=df.index)
        
        self.feature_groups['race_database'].append('tour_level_encoded')
        
        return feature_df
    
    def _load_race_features(self, competition_ids: List[int], percentile: str) -> pd.DataFrame:
        """Load race features for given competitions from specified percentile table."""
        # Handle both formats
        if percentile.startswith('race_features_'):
            table_name = percentile
        else:
            table_name = f"race_features_{percentile}"
        
        # Get all columns from the table except competition_id
        query = f"""
        SELECT *
        FROM {table_name}
        WHERE competition_id IN ({','.join(['?' for _ in competition_ids])})
        """
        
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(query, conn, params=competition_ids)
        
        # Remove competition_id from features
        feature_cols = [col for col in df.columns if col != 'competition_id']
        self.feature_groups['race_features'].extend(feature_cols)
        
        return df
    
    def _load_embeddings(self, rider_result_ids: List[int]) -> pd.DataFrame:
        """Load rider embeddings based on configuration."""
        from data_preparation import EmbeddingDataPreparation
        
        # Initialize data prep with appropriate paths
        if self.feature_config['embedding_type'] == 'full':
            data_prep = EmbeddingDataPreparation(
                self.db_path,
                use_full_embeddings=True,
                full_embeddings_path="race_type_full_embeddings"
            )
            embeddings, config = data_prep.load_embeddings(
                self.race_type, 
                percentile=self.feature_config['embedding_percentile']
            )
        else:
            data_prep = EmbeddingDataPreparation(
                self.db_path,
                embedding_base_path="race_type_optimized_data"
            )
            embeddings, config = data_prep.load_embeddings(self.race_type)
        
        # Filter to our rider_result_ids
        embeddings = embeddings[embeddings['rider_result_id'].isin(rider_result_ids)]
        
        # Get embedding feature columns
        embedding_cols = [col for col in embeddings.columns 
                         if col.startswith('corr_') or col == 'n_races']
        
        self.feature_groups['rider_embeddings'].extend(embedding_cols)
        
        return embeddings
    
    def _load_interaction_features(self, rider_result_ids: List[int]) -> pd.DataFrame:
        """Load interaction features from parquet files."""
        interaction_data = pd.DataFrame({'rider_result_id': rider_result_ids})
        
        # Determine base path based on current working directory
        import os
        if os.path.basename(os.getcwd()) == 'webscrape_tools':
            interaction_base_path = "interaction_embeddings_db_optimized"
        else:
            interaction_base_path = "../../interaction_embeddings_db_optimized"
        
        if self.feature_config['interaction_percentile'] == 'all':
            # Use phase2 matrix interactions
            base_path = Path(interaction_base_path) / "phase2"
            matrix_file = base_path / self.race_type / "matrix_interactions.parquet"
            
            if matrix_file.exists():
                matrix_data = pd.read_parquet(matrix_file)
                # Filter to our rider_result_ids
                matrix_data = matrix_data[matrix_data['rider_result_id'].isin(rider_result_ids)]
                
                # Select requested interaction types
                feature_cols = []
                if 'dot_product' in self.feature_config['interaction_types']:
                    feature_cols.append('dot_product')
                if 'cosine_similarity' in self.feature_config['interaction_types']:
                    feature_cols.append('cosine_similarity')
                if 'hadamard' in self.feature_config['interaction_types']:
                    # All hadamard columns
                    hadamard_cols = [col for col in matrix_data.columns if col.startswith('hadamard_')]
                    feature_cols.extend(hadamard_cols)
                
                if feature_cols:
                    interaction_data = matrix_data[['rider_result_id'] + feature_cols]
                    self.feature_groups['interaction_features'].extend(feature_cols)
        else:
            # Use phase1 individual percentile data
            base_path = Path(interaction_base_path) / "phase1"
            
            for interaction_type in self.feature_config['interaction_types']:
                if interaction_type == 'dot_product':
                    file_path = base_path / self.race_type / "dot_products.parquet"
                    if file_path.exists():
                        dots = pd.read_parquet(file_path)
                        # Filter to specific percentile
                        percentile_name = f"race_features_{self.feature_config['interaction_percentile']}"
                        dots = dots[dots['percentile'] == percentile_name]
                        dots = dots[dots['rider_result_id'].isin(rider_result_ids)]
                        if len(dots) > 0:
                            dots = dots[['rider_result_id', 'value']].rename(columns={'value': 'dot_product'})
                            interaction_data = interaction_data.merge(dots, on='rider_result_id', how='left')
                            self.feature_groups['interaction_features'].append('dot_product')
                
                elif interaction_type == 'cosine_similarity':
                    file_path = base_path / self.race_type / "cosine_products.parquet"
                    if file_path.exists():
                        cosines = pd.read_parquet(file_path)
                        percentile_name = f"race_features_{self.feature_config['interaction_percentile']}"
                        cosines = cosines[cosines['percentile'] == percentile_name]
                        cosines = cosines[cosines['rider_result_id'].isin(rider_result_ids)]
                        if len(cosines) > 0:
                            cosines = cosines[['rider_result_id', 'value']].rename(columns={'value': 'cosine_similarity'})
                            interaction_data = interaction_data.merge(cosines, on='rider_result_id', how='left')
                            self.feature_groups['interaction_features'].append('cosine_similarity')
                
                elif interaction_type == 'hadamard':
                    file_path = base_path / self.race_type / "hadamard_products.parquet"
                    if file_path.exists():
                        hadamard = pd.read_parquet(file_path)
                        percentile_name = f"race_features_{self.feature_config['interaction_percentile']}"
                        hadamard = hadamard[hadamard['percentile'] == percentile_name]
                        hadamard = hadamard[hadamard['rider_result_id'].isin(rider_result_ids)]
                        if len(hadamard) > 0:
                            # Pivot to get features as columns
                            hadamard_pivot = hadamard.pivot(
                                index='rider_result_id',
                                columns='feature',
                                values='value'
                            ).reset_index()
                            # Rename columns to indicate they're hadamard products
                            hadamard_cols = [col for col in hadamard_pivot.columns if col != 'rider_result_id']
                            rename_dict = {col: f'hadamard_{col}' for col in hadamard_cols}
                            hadamard_pivot = hadamard_pivot.rename(columns=rename_dict)
                            
                            interaction_data = interaction_data.merge(hadamard_pivot, on='rider_result_id', how='left')
                            self.feature_groups['interaction_features'].extend(list(rename_dict.values()))
        
        return interaction_data
    
    def prepare_data(
        self,
        min_year: Optional[int] = None,
        max_year: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Prepare complete dataset with all configured features.
        
        Args:
            min_year: Minimum year to include (inclusive)
            max_year: Maximum year to include (inclusive)
            
        Returns:
            DataFrame ready for model training
        """
        # Load base rider results data
        rider_results = self._load_rider_results_with_info()
        
        # Filter by race type
        if self.race_type != 'all':
            if self.race_type == 'stage_one_day':
                rider_results = rider_results[
                    rider_results['competition_race_type'].isin(['stage', 'one_day'])
                ]
            else:
                rider_results = rider_results[
                    rider_results['competition_race_type'] == self.race_type
                ]
        
        # Filter by year
        if min_year is not None:
            rider_results = rider_results[rider_results['year'] >= min_year]
        if max_year is not None:
            rider_results = rider_results[rider_results['year'] <= max_year]
        
        print(f"Starting with {len(rider_results)} rider results for {self.race_type}")
        
        # Initialize with basic columns
        result_df = rider_results[['id', 'competition_id', 'rider_id', 
                                  'year', 'competition_race_type', 'uci_points_proportional']].copy()
        result_df['rider_result_id'] = result_df['id']  # Create rider_result_id from id
        
        # 1. Rider database features
        if self.feature_config['use_rider_database']:
            rider_features = self._extract_rider_database_features(rider_results)
            if len(rider_features.columns) > 0:
                result_df = pd.concat([result_df, rider_features], axis=1)
                print(f"Added {len(rider_features.columns)} rider database features")
        
        # 2. Race database features
        if self.feature_config['use_race_database']:
            race_db_features = self._extract_race_database_features(rider_results)
            if len(race_db_features.columns) > 0:
                result_df = pd.concat([result_df, race_db_features], axis=1)
                print(f"Added {len(race_db_features.columns)} race database features")
        
        # 3. Race features
        if self.feature_config['use_race_features']:
            # Determine which percentile to use
            if self.feature_config['use_rider_embeddings']:
                # Use the same percentile as embeddings
                if self.feature_config['embedding_type'] == 'full':
                    percentile = self.feature_config['embedding_percentile'].replace('race_features_', '')
                else:
                    # Load optimized config to get percentile
                    from data_preparation import EmbeddingDataPreparation
                    data_prep = EmbeddingDataPreparation(self.db_path)
                    _, config = data_prep.load_embeddings(self.race_type)
                    percentile = config.get('percentile', '70')
            else:
                # Use interaction percentile if available
                percentile = self.feature_config.get('interaction_percentile', '70')
            
            competition_ids = result_df['competition_id'].unique().tolist()
            race_features = self._load_race_features(competition_ids, percentile)
            if len(race_features) > 0:
                result_df = result_df.merge(race_features, on='competition_id', how='left')
                print(f"Added {len(race_features.columns) - 1} race features from race_features_{percentile}")
        
        # 4. Rider embeddings
        if self.feature_config['use_rider_embeddings']:
            embeddings = self._load_embeddings(result_df['rider_result_id'].tolist())
            if len(embeddings) > 0:
                # Merge only riders that have embeddings
                result_df = result_df.merge(embeddings, on='rider_result_id', how='inner')
                print(f"Added {len(self.feature_groups['rider_embeddings'])} rider embedding features")
                print(f"Dataset reduced to {len(result_df)} samples with embeddings")
        
        # 5. Interaction features
        if self.feature_config['use_interaction_features']:
            interactions = self._load_interaction_features(result_df['rider_result_id'].tolist())
            if len(interactions.columns) > 1:  # More than just rider_result_id
                # Merge only riders that have interactions
                result_df = result_df.merge(interactions, on='rider_result_id', how='inner')
                print(f"Added {len(self.feature_groups['interaction_features'])} interaction features")
                print(f"Dataset reduced to {len(result_df)} samples with interactions")
        
        print(f"\nFinal dataset: {len(result_df)} samples")
        print(f"Feature groups:")
        for group, features in self.feature_groups.items():
            if features:
                print(f"  {group}: {len(features)} features")
        
        return result_df
    
    def _prepare_features(self, df: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
        """
        Prepare feature matrix from dataframe.
        
        Returns:
            Tuple of (feature_matrix, feature_columns)
        """
        # Exclude non-feature columns
        exclude_cols = {'id', 'rider_result_id', 'year', 'competition_race_type', 
                       'uci_points_proportional', 'competition_id', 'rider_id'}
        
        # Get all feature columns from our groups
        feature_cols = []
        for group_features in self.feature_groups.values():
            feature_cols.extend(group_features)
        
        # Remove duplicates while preserving order
        seen = set()
        feature_cols = [x for x in feature_cols if not (x in seen or seen.add(x))]
        
        # Ensure all columns exist in dataframe
        feature_cols = [col for col in feature_cols if col in df.columns]
        
        # Fill missing values with 0
        X = df[feature_cols].fillna(0).values
        
        return X, feature_cols
    
    def train(
        self,
        train_df: pd.DataFrame,
        valid_df: Optional[pd.DataFrame] = None,
        target_col: str = 'uci_points_proportional',
        num_boost_round: int = 1000,
        early_stopping_rounds: int = 50,
        verbose: bool = True
    ) -> Dict:
        """
        Train the two-stage model.
        
        Args:
            train_df: Training DataFrame from data preparation
            valid_df: Validation DataFrame (if None, uses 20% split)
            target_col: Target column name
            num_boost_round: Maximum number of boosting rounds
            early_stopping_rounds: Early stopping patience
            verbose: Whether to print training progress
            
        Returns:
            Dictionary with training metrics and information
        """
        # Prepare features and target
        X_train, self.feature_columns = self._prepare_features(train_df)
        y_train = train_df[target_col].values
        
        # Create validation split if not provided
        if valid_df is None:
            X_train, X_valid, y_train, y_valid = train_test_split(
                X_train, y_train, test_size=0.2, random_state=self.random_state
            )
        else:
            X_valid, _ = self._prepare_features(valid_df)
            y_valid = valid_df[target_col].values
        
        # Create binary target for classification
        y_train_binary = (y_train > 0).astype(int)
        y_valid_binary = (y_valid > 0).astype(int)
        
        if verbose:
            print(f"\nTraining {self.race_type} interaction model...")
            print(f"Training samples: {len(X_train)}")
            print(f"Validation samples: {len(X_valid)}")
            print(f"Training zero rate: {(y_train == 0).mean():.2%}")
            print(f"Number of features: {len(self.feature_columns)}")
            for group, features in self.feature_groups.items():
                if features:
                    print(f"  - {group}: {len(features)}")
        
        # Stage 1: Train classifier
        if verbose:
            print("\nStage 1: Training classifier...")
        
        train_data_clf = lgb.Dataset(X_train, label=y_train_binary)
        valid_data_clf = lgb.Dataset(X_valid, label=y_valid_binary, reference=train_data_clf)
        
        callbacks = []
        if early_stopping_rounds:
            callbacks.append(lgb.early_stopping(early_stopping_rounds))
        if verbose:
            callbacks.append(lgb.log_evaluation(100))
        
        self.classifier = lgb.train(
            self.classifier_params,
            train_data_clf,
            valid_sets=[valid_data_clf],
            num_boost_round=num_boost_round,
            callbacks=callbacks
        )
        
        # Stage 2: Train regressor on non-zero samples
        if verbose:
            print("\nStage 2: Training regressor on non-zero samples...")
        
        # Filter to non-zero samples
        nonzero_mask_train = y_train > 0
        nonzero_mask_valid = y_valid > 0
        
        X_train_nonzero = X_train[nonzero_mask_train]
        y_train_nonzero = y_train[nonzero_mask_train]
        X_valid_nonzero = X_valid[nonzero_mask_valid]
        y_valid_nonzero = y_valid[nonzero_mask_valid]
        
        if verbose:
            print(f"Non-zero training samples: {len(X_train_nonzero)}")
            print(f"Non-zero validation samples: {len(X_valid_nonzero)}")
        
        if len(X_train_nonzero) > 0 and len(X_valid_nonzero) > 0:
            train_data_reg = lgb.Dataset(X_train_nonzero, label=y_train_nonzero)
            valid_data_reg = lgb.Dataset(X_valid_nonzero, label=y_valid_nonzero, reference=train_data_reg)
            
            callbacks_reg = []
            if early_stopping_rounds:
                callbacks_reg.append(lgb.early_stopping(early_stopping_rounds))
            if verbose:
                callbacks_reg.append(lgb.log_evaluation(100))
                
            self.regressor = lgb.train(
                self.regressor_params,
                train_data_reg,
                valid_sets=[valid_data_reg],
                num_boost_round=num_boost_round,
                callbacks=callbacks_reg
            )
        else:
            raise ValueError("Not enough non-zero samples for regression training")
        
        # Calculate performance metrics
        predictions = self.predict(X_valid)
        
        performance_metrics = {
            'rmse_overall': np.sqrt(mean_squared_error(y_valid, predictions)),
            'mae_overall': mean_absolute_error(y_valid, predictions),
            'rmse_nonzero': np.sqrt(mean_squared_error(y_valid[nonzero_mask_valid], 
                                                      predictions[nonzero_mask_valid])) if nonzero_mask_valid.any() else np.nan,
            'mae_nonzero': mean_absolute_error(y_valid[nonzero_mask_valid], 
                                              predictions[nonzero_mask_valid]) if nonzero_mask_valid.any() else np.nan,
            'r2_nonzero': r2_score(y_valid[nonzero_mask_valid], 
                                  predictions[nonzero_mask_valid]) if nonzero_mask_valid.sum() > 1 else np.nan,
            'auc_classification': roc_auc_score(y_valid_binary, self.predict_proba_nonzero(X_valid)),
            'zero_accuracy': ((predictions == 0) == (y_valid == 0)).mean(),
            'threshold': self.classification_threshold
        }
        
        # Store training information
        self.training_info = {
            'race_type': self.race_type,
            'feature_config': self.feature_config,
            'train_samples': len(X_train),
            'valid_samples': len(X_valid),
            'nonzero_train_samples': len(X_train_nonzero),
            'nonzero_valid_samples': len(X_valid_nonzero),
            'n_features': len(self.feature_columns),
            'feature_groups': {k: len(v) for k, v in self.feature_groups.items() if v},
            'performance_metrics': performance_metrics,
            'classifier_iterations': self.classifier.best_iteration,
            'regressor_iterations': self.regressor.best_iteration,
            'training_date': datetime.now().isoformat()
        }
        
        if verbose:
            print(f"\nTraining complete!")
            print(f"Overall RMSE: {performance_metrics['rmse_overall']:.4f}")
            print(f"Non-zero RMSE: {performance_metrics['rmse_nonzero']:.4f}")
            print(f"Classification AUC: {performance_metrics['auc_classification']:.4f}")
        
        return self.training_info
    
    def predict(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        """Make predictions using the two-stage model."""
        if isinstance(X, pd.DataFrame):
            X = X[self.feature_columns].fillna(0).values
        
        # Stage 1: Predict probability of non-zero
        prob_nonzero = self.classifier.predict(X, num_iteration=self.classifier.best_iteration)
        
        # Stage 2: Predict values for likely non-zero cases
        regression_pred = self.regressor.predict(X, num_iteration=self.regressor.best_iteration)
        
        # Combine predictions
        predictions = np.where(prob_nonzero > self.classification_threshold, regression_pred, 0)
        
        # Ensure non-negative predictions
        predictions = np.maximum(predictions, 0)
        
        return predictions
    
    def predict_proba_nonzero(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        """Predict probability of earning non-zero points."""
        if isinstance(X, pd.DataFrame):
            X = X[self.feature_columns].fillna(0).values
        
        return self.classifier.predict(X, num_iteration=self.classifier.best_iteration)
    
    def get_feature_importance(self, stage: str = 'both', n_features: Optional[int] = None) -> pd.DataFrame:
        """
        Get feature importance.
        
        Args:
            stage: 'classifier', 'regressor', or 'both'
            n_features: Number of top features to return (None for all)
            
        Returns:
            DataFrame with feature names and importance scores
        """
        importance_data = []
        
        if stage in ['classifier', 'both'] and self.classifier:
            clf_importance = self.classifier.feature_importance(importance_type='gain')
            for feat, imp in zip(self.feature_columns, clf_importance):
                # Determine feature group
                feature_group = 'unknown'
                for group, features in self.feature_groups.items():
                    if feat in features:
                        feature_group = group
                        break
                
                importance_data.append({
                    'feature': feat,
                    'importance': imp,
                    'stage': 'classifier',
                    'feature_group': feature_group
                })
        
        if stage in ['regressor', 'both'] and self.regressor:
            reg_importance = self.regressor.feature_importance(importance_type='gain')
            for feat, imp in zip(self.feature_columns, reg_importance):
                # Determine feature group
                feature_group = 'unknown'
                for group, features in self.feature_groups.items():
                    if feat in features:
                        feature_group = group
                        break
                
                importance_data.append({
                    'feature': feat,
                    'importance': imp,
                    'stage': 'regressor',
                    'feature_group': feature_group
                })
        
        importance_df = pd.DataFrame(importance_data)
        
        # Sort by importance
        importance_df = importance_df.sort_values('importance', ascending=False)
        
        if n_features is not None:
            importance_df = importance_df.head(n_features)
        
        return importance_df
    
    def save(self, filepath: str):
        """Save the model to disk."""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # Save models
        self.classifier.save_model(f"{filepath}_classifier.txt")
        self.regressor.save_model(f"{filepath}_regressor.txt")
        
        # Save metadata
        metadata = {
            'race_type': self.race_type,
            'feature_config': self.feature_config,
            'feature_columns': self.feature_columns,
            'feature_groups': self.feature_groups,
            'classification_threshold': self.classification_threshold,
            'training_info': self.training_info,
            'classifier_params': self.classifier_params,
            'regressor_params': self.regressor_params
        }
        
        with open(f"{filepath}_metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def load(self, filepath: str):
        """Load the model from disk."""
        # Load metadata
        with open(f"{filepath}_metadata.json", 'r') as f:
            metadata = json.load(f)
        
        self.race_type = metadata['race_type']
        self.feature_config = metadata['feature_config']
        self.feature_columns = metadata['feature_columns']
        self.feature_groups = metadata['feature_groups']
        self.classification_threshold = metadata['classification_threshold']
        self.training_info = metadata['training_info']
        
        # Load models
        self.classifier = lgb.Booster(model_file=f"{filepath}_classifier.txt")
        self.regressor = lgb.Booster(model_file=f"{filepath}_regressor.txt")