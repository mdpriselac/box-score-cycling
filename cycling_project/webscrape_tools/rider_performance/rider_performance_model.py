"""
LightGBM-based global models for rider performance prediction.

This module implements two global models:
1. GC Model: For General Classification races
2. Stage/One-day Model: For Stage and One-day races

The models handle the zero-inflated nature of UCI points through a two-stage approach:
- Stage 1: Classification (0 vs non-0 points)
- Stage 2: Regression (predict actual points for non-0 cases)
"""

import lightgbm as lgb
import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional, List, Union
import joblib
import json
from datetime import datetime
import os
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score, roc_auc_score, accuracy_score
import warnings
warnings.filterwarnings('ignore', category=UserWarning)

from cycling_project.engineering_tools.imputation import smart_fillna


class RiderPerformanceModel:
    """
    Two-stage LightGBM model for rider performance prediction.
    Handles zero-inflated UCI points through classification + regression.
    """
    
    def __init__(self, model_type: str = 'gc', random_state: int = 42):
        """
        Initialize the rider performance model.
        
        Args:
            model_type: Either 'gc' or 'stage_one_day'
            random_state: Random seed for reproducibility
        """
        if model_type not in ['gc', 'stage_one_day']:
            raise ValueError("model_type must be 'gc' or 'stage_one_day'")
        
        self.model_type = model_type
        self.random_state = random_state
        
        # Two-stage models
        self.classifier = None  # Predicts 0 vs non-0 points
        self.regressor = None   # Predicts actual points for non-0 cases
        
        # Feature information
        self.feature_columns = None
        self.categorical_features = None
        
        # Training information
        self.training_info = {
            'model_type': model_type,
            'trained': False,
            'training_date': None,
            'n_samples': None,
            'feature_importance': None,
            'performance_metrics': None
        }
        
        # Default parameters for zero-inflated data
        self.classifier_params = {
            'objective': 'binary',
            'metric': 'binary_logloss',
            'boosting_type': 'gbdt',
            'num_leaves': 31,
            'learning_rate': 0.05,
            'feature_fraction': 0.9,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'verbose': -1,
            'random_state': random_state,
            'is_unbalance': True,  # Important for imbalanced classification
            'min_data_in_leaf': 20,
            'max_depth': -1,
            'num_threads': -1,  # Use all available cores
            'force_row_wise': True  # Faster for large datasets
        }
        
        self.regressor_params = {
            'objective': 'regression',
            'metric': 'rmse',
            'boosting_type': 'gbdt',
            'num_leaves': 63,
            'learning_rate': 0.05,
            'feature_fraction': 0.9,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'verbose': -1,
            'random_state': random_state,
            'min_data_in_leaf': 10,
            'max_depth': -1,
            'reg_alpha': 0.1,
            'reg_lambda': 0.1,
            'num_threads': -1,  # Use all available cores
            'force_row_wise': True  # Faster for large datasets
        }
    
    def prepare_features(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """
        Prepare features from the dataset.
        
        Args:
            df: DataFrame from DatasetGenerator
            
        Returns:
            Feature matrix and list of categorical feature names
        """
        # Identify feature columns
        race_features = [col for col in df.columns if col.startswith('rf_')]
        race_kind_features = [col for col in df.columns if col.startswith('rkf_')]
        experience_features = [col for col in df.columns 
                             if col.startswith(('prior_', 'total_prior', 'rider_age_at_race'))]
        
        # Combine all features
        feature_cols = race_features + race_kind_features + experience_features
        
        # Store feature columns
        self.feature_columns = feature_cols
        
        # Identify categorical features (none in current design, but structure for future)
        self.categorical_features = []
        
        # Extract features
        X = df[feature_cols].copy()

        # Handle missing values with type-aware imputation
        X = smart_fillna(X, feature_columns=feature_cols)

        return X, self.categorical_features
    
    def train(self, 
              train_df: pd.DataFrame,
              valid_df: Optional[pd.DataFrame] = None,
              target_col: str = 'uci_points_actual',
              num_boost_round: int = 1000,
              early_stopping_rounds: int = 50,
              verbose: bool = True) -> Dict:
        """
        Train the two-stage model.
        
        Args:
            train_df: Training DataFrame from DatasetGenerator
            valid_df: Optional validation DataFrame
            target_col: Target column name
            num_boost_round: Maximum number of boosting rounds
            early_stopping_rounds: Early stopping patience
            verbose: Whether to print training progress
            
        Returns:
            Dictionary with training metrics and information
        """
        # Prepare features
        X_train, cat_features = self.prepare_features(train_df)
        y_train = train_df[target_col].values
        
        # Create binary target for classification
        y_train_binary = (y_train > 0).astype(int)
        
        # Split for validation if not provided
        if valid_df is None:
            X_train_full, X_valid, y_train_full, y_valid = train_test_split(
                X_train, y_train, test_size=0.2, random_state=self.random_state
            )
            y_train_binary_full, y_valid_binary = train_test_split(
                y_train_binary, test_size=0.2, random_state=self.random_state
            )
        else:
            X_train_full = X_train
            y_train_full = y_train
            y_train_binary_full = y_train_binary
            X_valid, _ = self.prepare_features(valid_df)
            y_valid = valid_df[target_col].values
            y_valid_binary = (y_valid > 0).astype(int)
        
        if verbose:
            print(f"Training {self.model_type} model on {len(X_train_full)} samples")
            print(f"Features: {len(self.feature_columns)}")
            print(f"Target distribution - Zeros: {(y_train_full == 0).sum()}, Non-zeros: {(y_train_full > 0).sum()}")
        
        # Stage 1: Train classifier
        if verbose:
            print("\nStage 1: Training classifier (0 vs non-0 points)...")
        
        train_data_clf = lgb.Dataset(
            X_train_full, 
            label=y_train_binary_full,
            categorical_feature=cat_features
        )
        valid_data_clf = lgb.Dataset(
            X_valid,
            label=y_valid_binary,
            categorical_feature=cat_features,
            reference=train_data_clf
        )
        
        self.classifier = lgb.train(
            self.classifier_params,
            train_data_clf,
            valid_sets=[valid_data_clf],
            num_boost_round=num_boost_round,
            callbacks=[
                lgb.early_stopping(early_stopping_rounds),
                lgb.log_evaluation(50 if verbose else 0)
            ]
        )
        
        # Stage 2: Train regressor on non-zero samples only
        if verbose:
            print("\nStage 2: Training regressor (for non-zero points)...")
        
        # Filter to non-zero samples
        non_zero_mask_train = y_train_full > 0
        X_train_nonzero = X_train_full[non_zero_mask_train]
        y_train_nonzero = y_train_full[non_zero_mask_train]
        
        non_zero_mask_valid = y_valid > 0
        X_valid_nonzero = X_valid[non_zero_mask_valid]
        y_valid_nonzero = y_valid[non_zero_mask_valid]
        
        if verbose:
            print(f"Non-zero training samples: {len(X_train_nonzero)}")
            print(f"Non-zero validation samples: {len(X_valid_nonzero)}")
        
        if len(X_train_nonzero) > 0 and len(X_valid_nonzero) > 0:
            train_data_reg = lgb.Dataset(
                X_train_nonzero,
                label=y_train_nonzero,
                categorical_feature=cat_features
            )
            valid_data_reg = lgb.Dataset(
                X_valid_nonzero,
                label=y_valid_nonzero,
                categorical_feature=cat_features,
                reference=train_data_reg
            )
            
            self.regressor = lgb.train(
                self.regressor_params,
                train_data_reg,
                valid_sets=[valid_data_reg],
                num_boost_round=num_boost_round,
                callbacks=[
                    lgb.early_stopping(early_stopping_rounds),
                    lgb.log_evaluation(50 if verbose else 0)
                ]
            )
        else:
            warnings.warn("Not enough non-zero samples to train regressor")
        
        # Calculate performance metrics
        metrics = self._evaluate(X_valid, y_valid)
        
        # Get feature importance
        feature_importance = self._get_feature_importance()
        
        # Update training info
        self.training_info.update({
            'trained': True,
            'training_date': datetime.now().isoformat(),
            'n_samples': len(X_train_full),
            'n_features': len(self.feature_columns),
            'feature_importance': feature_importance,
            'performance_metrics': metrics,
            'target_column': target_col
        })
        
        if verbose:
            print("\nTraining complete!")
            print(f"Validation metrics:")
            for metric, value in metrics.items():
                print(f"  {metric}: {value:.4f}")
        
        return self.training_info
    
    def predict(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        """
        Make predictions using the two-stage model.
        
        Args:
            X: Feature matrix (must have same columns as training)
            
        Returns:
            Predicted UCI points
        """
        if not self.training_info['trained']:
            raise ValueError("Model must be trained before making predictions")
        
        # Ensure we have the right features
        if isinstance(X, pd.DataFrame):
            X = smart_fillna(X[self.feature_columns], feature_columns=self.feature_columns)
        
        # Stage 1: Predict probability of non-zero points
        prob_nonzero = self.classifier.predict(X, num_iteration=self.classifier.best_iteration)
        
        # Stage 2: Predict actual points for all samples
        if self.regressor is not None:
            point_predictions = self.regressor.predict(X, num_iteration=self.regressor.best_iteration)
        else:
            # Fallback if regressor wasn't trained
            point_predictions = np.zeros(len(X))
        
        # Combine predictions: use threshold to determine final predictions
        # You might want to tune this threshold
        threshold = 0.5
        final_predictions = np.where(prob_nonzero > threshold, point_predictions, 0)
        
        # Ensure non-negative predictions
        final_predictions = np.maximum(final_predictions, 0)
        
        return final_predictions
    
    def predict_proba_nonzero(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        """
        Predict probability of earning non-zero points.
        
        Args:
            X: Feature matrix
            
        Returns:
            Probability of non-zero points
        """
        if not self.training_info['trained']:
            raise ValueError("Model must be trained before making predictions")

        if isinstance(X, pd.DataFrame):
            X = smart_fillna(X[self.feature_columns], feature_columns=self.feature_columns)

        return self.classifier.predict(X, num_iteration=self.classifier.best_iteration)
    
    def _evaluate(self, X: pd.DataFrame, y_true: np.ndarray) -> Dict:
        """Evaluate model performance."""
        # Get predictions directly from models (bypass the trained check)
        if isinstance(X, pd.DataFrame):
            X_features = smart_fillna(X[self.feature_columns], feature_columns=self.feature_columns)
        else:
            X_features = X
        
        # Stage 1: Predict probability of non-zero points
        if self.classifier is not None:
            y_prob_nonzero = self.classifier.predict(X_features, num_iteration=self.classifier.best_iteration)
        else:
            y_prob_nonzero = np.zeros(len(X_features))
        
        # Stage 2: Predict actual points
        if self.regressor is not None:
            point_predictions = self.regressor.predict(X_features, num_iteration=self.regressor.best_iteration)
        else:
            point_predictions = np.zeros(len(X_features))
        
        # Combine predictions
        threshold = 0.5
        y_pred = np.where(y_prob_nonzero > threshold, point_predictions, 0)
        y_pred = np.maximum(y_pred, 0)  # Ensure non-negative
        
        y_true_binary = (y_true > 0).astype(int)
        
        # Overall regression metrics
        rmse = np.sqrt(mean_squared_error(y_true, y_pred))
        mae = mean_absolute_error(y_true, y_pred)
        
        # Metrics for non-zero samples only
        non_zero_mask = y_true > 0
        if non_zero_mask.sum() > 0:
            rmse_nonzero = np.sqrt(mean_squared_error(y_true[non_zero_mask], y_pred[non_zero_mask]))
            mae_nonzero = mean_absolute_error(y_true[non_zero_mask], y_pred[non_zero_mask])
            r2_nonzero = r2_score(y_true[non_zero_mask], y_pred[non_zero_mask])
        else:
            rmse_nonzero = mae_nonzero = r2_nonzero = 0.0
        
        # Classification metrics
        auc_score = roc_auc_score(y_true_binary, y_prob_nonzero)
        acc_score = accuracy_score(y_true_binary, y_prob_nonzero > 0.5)
        
        # Custom metric: percentage of correct zero predictions
        zero_mask = y_true == 0
        if zero_mask.sum() > 0:
            zero_accuracy = ((y_pred[zero_mask] == 0).sum() / zero_mask.sum())
        else:
            zero_accuracy = 0.0
        
        return {
            'rmse_overall': rmse,
            'mae_overall': mae,
            'rmse_nonzero': rmse_nonzero,
            'mae_nonzero': mae_nonzero,
            'r2_nonzero': r2_nonzero,
            'auc_classification': auc_score,
            'accuracy_classification': acc_score,
            'zero_prediction_accuracy': zero_accuracy,
            'n_samples': len(y_true),
            'n_nonzero': non_zero_mask.sum()
        }
    
    def _get_feature_importance(self) -> Dict:
        """Get feature importance from both models."""
        importance_dict = {}
        
        # Classifier importance
        if self.classifier is not None:
            clf_importance = self.classifier.feature_importance(importance_type='gain')
            for i, feature in enumerate(self.feature_columns):
                importance_dict[f"{feature}_classifier"] = float(clf_importance[i])
        
        # Regressor importance
        if self.regressor is not None:
            reg_importance = self.regressor.feature_importance(importance_type='gain')
            for i, feature in enumerate(self.feature_columns):
                importance_dict[f"{feature}_regressor"] = float(reg_importance[i])
        
        return importance_dict
    
    def _convert_numpy_types(self, obj):
        """Convert numpy types to native Python types for JSON serialization."""
        if isinstance(obj, dict):
            return {k: self._convert_numpy_types(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._convert_numpy_types(item) for item in obj]
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return obj
    
    def save(self, filepath: str):
        """
        Save the model to disk.
        
        Args:
            filepath: Path to save the model (without extension)
        """
        # Save models
        if self.classifier is not None:
            self.classifier.save_model(f"{filepath}_classifier.txt")
        if self.regressor is not None:
            self.regressor.save_model(f"{filepath}_regressor.txt")
        
        # Save metadata
        metadata = {
            'model_type': self.model_type,
            'feature_columns': self.feature_columns,
            'categorical_features': self.categorical_features,
            'training_info': self._convert_numpy_types(self.training_info),
            'classifier_params': self.classifier_params,
            'regressor_params': self.regressor_params
        }
        
        with open(f"{filepath}_metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"Model saved to {filepath}")
    
    def load(self, filepath: str):
        """
        Load the model from disk.
        
        Args:
            filepath: Path to load the model from (without extension)
        """
        # Load metadata
        with open(f"{filepath}_metadata.json", 'r') as f:
            metadata = json.load(f)
        
        self.model_type = metadata['model_type']
        self.feature_columns = metadata['feature_columns']
        self.categorical_features = metadata['categorical_features']
        self.training_info = metadata['training_info']
        self.classifier_params = metadata['classifier_params']
        self.regressor_params = metadata['regressor_params']
        
        # Load models
        if os.path.exists(f"{filepath}_classifier.txt"):
            self.classifier = lgb.Booster(model_file=f"{filepath}_classifier.txt")
        if os.path.exists(f"{filepath}_regressor.txt"):
            self.regressor = lgb.Booster(model_file=f"{filepath}_regressor.txt")
        
        print(f"Model loaded from {filepath}")
    
    def get_top_features(self, n: int = 20, stage: str = 'both') -> pd.DataFrame:
        """
        Get top n most important features.
        
        Args:
            n: Number of top features to return
            stage: 'classifier', 'regressor', or 'both'
            
        Returns:
            DataFrame with feature names and importance scores
        """
        importance = self.training_info.get('feature_importance', {})
        
        if stage == 'classifier':
            importance = {k: v for k, v in importance.items() if '_classifier' in k}
        elif stage == 'regressor':
            importance = {k: v for k, v in importance.items() if '_regressor' in k}
        
        # Sort by importance
        sorted_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)[:n]
        
        return pd.DataFrame(sorted_features, columns=['feature', 'importance'])


if __name__ == "__main__":
    # Example usage
    from dataset_generator import DatasetGenerator
    
    print("Loading data...")
    db_path = "database/database/cycling_races.db"
    generator = DatasetGenerator(db_path)
    
    # Generate small sample datasets for testing
    datasets = generator.generate_datasets(
        cutoff_date="2023-12-31",
        min_results=20,  # Higher threshold for faster testing
        target_variable='uci_points_actual'
    )
    
    # Test GC model
    print("\n" + "="*50)
    print("Testing GC Model")
    print("="*50)
    
    gc_data = datasets['gc_dataset']
    if len(gc_data) > 100:
        gc_model = RiderPerformanceModel(model_type='gc')
        
        # Split data
        train_df = gc_data.sample(frac=0.8, random_state=42)
        valid_df = gc_data.drop(train_df.index)
        
        # Train model
        training_info = gc_model.train(
            train_df=train_df,
            valid_df=valid_df,
            target_col='uci_points_actual',
            num_boost_round=100,  # Fewer rounds for testing
            early_stopping_rounds=20
        )
        
        # Show top features
        print("\nTop 10 important features:")
        print(gc_model.get_top_features(n=10))
        
        # Save model
        gc_model.save("rider_performance/models/gc_model_test")
    else:
        print(f"Not enough GC data for testing: {len(gc_data)} samples")
    
    # Test Stage/One-day model
    print("\n" + "="*50)
    print("Testing Stage/One-day Model")
    print("="*50)
    
    stage_data = datasets['stage_one_day_dataset']
    if len(stage_data) > 100:
        stage_model = RiderPerformanceModel(model_type='stage_one_day')
        
        # Split data
        train_df = stage_data.sample(frac=0.8, random_state=42)
        valid_df = stage_data.drop(train_df.index)
        
        # Train model
        training_info = stage_model.train(
            train_df=train_df,
            valid_df=valid_df,
            target_col='uci_points_actual',
            num_boost_round=100,
            early_stopping_rounds=20
        )
        
        # Show top features
        print("\nTop 10 important features:")
        print(stage_model.get_top_features(n=10))
        
        # Save model
        stage_model.save("rider_performance/models/stage_one_day_model_test")
    else:
        print(f"Not enough Stage/One-day data for testing: {len(stage_data)} samples")