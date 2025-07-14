import numpy as np
import pandas as pd
import lightgbm as lgb
from typing import Dict, List, Optional, Tuple, Union
import json
from pathlib import Path
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score, roc_auc_score


class EmbeddingPerformanceModel:
    """Two-stage LightGBM model for rider performance prediction using embeddings."""
    
    def __init__(self, race_type: str, random_state: int = 42):
        """
        Initialize the embedding performance model.
        
        Args:
            race_type: One of ['gc', 'stage', 'one_day', 'stage_one_day', 'all']
            random_state: Random seed for reproducibility
        """
        self.race_type = race_type
        self.random_state = random_state
        
        # Model components
        self.classifier = None
        self.regressor = None
        
        # Feature information
        self.feature_columns = None
        self.embedding_features = None
        self.database_features = None
        
        # Training information
        self.training_info = None
        
        # Model parameters (following rider_performance_model.py patterns)
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
        self.classification_threshold = 0.5
    
    def _prepare_features(self, df: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
        """
        Prepare feature matrix from dataframe.
        
        Returns:
            Tuple of (feature_matrix, feature_columns)
        """
        # Exclude non-feature columns
        exclude_cols = {'rider_result_id', 'year', 'competition_race_type', 
                       'uci_points_proportional', 'competition_id', 'rider_id'}
        
        feature_cols = [col for col in df.columns if col not in exclude_cols]
        
        # Separate embedding, database, and race features
        self.embedding_features = [col for col in feature_cols if col.startswith('corr_') or col == 'n_races']
        
        # Race features are from the race_features table (not corr_ or rider-specific)
        race_feature_names = [
            'total_finishers', 'total_race_duration', 'abandon_ratio', 'shannon_entropy_absolute',
            'kurtosis_absolute', 'biggest_group_metric', 'largest_group_position', 'winning_time',
            'time_gap_evenness_metric', 'skewness_absolute', 'shannon_entropy_normalized',
            'riders_in_groups', 'total_groups', 'largest_group_size', 'skewness_normalized',
            'clumpiness_score', '20th_percentile_gap', 'included_finishers'
        ]
        self.race_features = [col for col in feature_cols if col in race_feature_names]
        
        self.database_features = [col for col in feature_cols 
                                 if col not in self.embedding_features and col not in self.race_features]
        
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
        
        # Handle duplicate column names by taking the first occurrence
        if isinstance(train_df[target_col], pd.DataFrame):
            y_train = train_df[target_col].iloc[:, 0].values  # Take first column
        else:
            y_train = train_df[target_col].values
        
        # Create validation split if not provided
        if valid_df is None:
            X_train, X_valid, y_train, y_valid = train_test_split(
                X_train, y_train, test_size=0.2, random_state=self.random_state
            )
        else:
            X_valid, _ = self._prepare_features(valid_df)
            # Handle duplicate column names by taking the first occurrence
            if isinstance(valid_df[target_col], pd.DataFrame):
                y_valid = valid_df[target_col].iloc[:, 0].values  # Take first column
            else:
                y_valid = valid_df[target_col].values
        
        # Create binary target for classification
        y_train_binary = (y_train > 0).astype(int)
        y_valid_binary = (y_valid > 0).astype(int)
        
        if verbose:
            print(f"\nTraining {self.race_type} model...")
            print(f"Training samples: {len(X_train)} (X), {len(y_train)} (y)")
            print(f"Validation samples: {len(X_valid)} (X), {len(y_valid)} (y)")
            print(f"Training zero rate: {(y_train == 0).mean():.2%}")
            print(f"Number of features: {len(self.feature_columns)}")
            print(f"  - Embedding features: {len(self.embedding_features)}")
            print(f"  - Race features: {len(self.race_features)}")
            print(f"  - Database features: {len(self.database_features)}")
            
        # Verify array shapes match
        assert len(X_train) == len(y_train), f"X_train: {X_train.shape}, y_train: {y_train.shape}"
        assert len(X_valid) == len(y_valid), f"X_valid: {X_valid.shape}, y_valid: {y_valid.shape}"
        
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
            'train_samples': len(X_train),
            'valid_samples': len(X_valid),
            'nonzero_train_samples': len(X_train_nonzero),
            'nonzero_valid_samples': len(X_valid_nonzero),
            'n_features': len(self.feature_columns),
            'n_embedding_features': len(self.embedding_features),
            'n_race_features': len(self.race_features),
            'n_database_features': len(self.database_features),
            'performance_metrics': performance_metrics,
            'classifier_iterations': self.classifier.best_iteration,
            'regressor_iterations': self.regressor.best_iteration if self.regressor else 0,
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
                feature_type = 'embedding' if feat in self.embedding_features else (
                    'race' if feat in self.race_features else 'database'
                )
                importance_data.append({
                    'feature': feat,
                    'importance': imp,
                    'stage': 'classifier',
                    'feature_type': feature_type
                })
        
        if stage in ['regressor', 'both'] and self.regressor:
            reg_importance = self.regressor.feature_importance(importance_type='gain')
            for feat, imp in zip(self.feature_columns, reg_importance):
                feature_type = 'embedding' if feat in self.embedding_features else (
                    'race' if feat in self.race_features else 'database'
                )
                importance_data.append({
                    'feature': feat,
                    'importance': imp,
                    'stage': 'regressor',
                    'feature_type': feature_type
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
            'feature_columns': self.feature_columns,
            'embedding_features': self.embedding_features,
            'race_features': self.race_features,
            'database_features': self.database_features,
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
        self.feature_columns = metadata['feature_columns']
        self.embedding_features = metadata['embedding_features']
        self.race_features = metadata.get('race_features', [])  # For backward compatibility
        self.database_features = metadata['database_features']
        self.classification_threshold = metadata['classification_threshold']
        self.training_info = metadata['training_info']
        
        # Load models
        self.classifier = lgb.Booster(model_file=f"{filepath}_classifier.txt")
        self.regressor = lgb.Booster(model_file=f"{filepath}_regressor.txt")