"""
Temporal backtesting system for rider performance models.

This module provides a complete training and evaluation loop:
- Given a test year (e.g., 2022), trains on all prior years
- Tests/predicts on the given year
- Provides comprehensive evaluation metrics
- Supports both UCI point schemes (actual and proportional)
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import json
import os
from datetime import datetime
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score, roc_auc_score
import matplotlib.pyplot as plt
import seaborn as sns

from dataset_generator import DatasetGenerator
from optimized_dataset_generator import OptimizedDatasetGenerator
from optimized_feature_builder import OptimizedFeatureBuilder
from rider_performance_model import RiderPerformanceModel


class TemporalBacktester:
    """Handles temporal backtesting of rider performance models."""
    
    def __init__(self, db_path: str, output_dir: str = "rider_performance/backtest_results"):
        """
        Initialize the temporal backtester.
        
        Args:
            db_path: Path to the SQLite database
            output_dir: Directory to save results and models
        """
        self.db_path = db_path
        self.output_dir = output_dir
        self.generator = DatasetGenerator(db_path)
        self.optimized_generator = OptimizedDatasetGenerator(db_path)
        self.optimized_feature_builder = OptimizedFeatureBuilder(db_path)
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(f"{output_dir}/models", exist_ok=True)
        os.makedirs(f"{output_dir}/results", exist_ok=True)
        os.makedirs(f"{output_dir}/plots", exist_ok=True)
    
    def run_temporal_backtest(self,
                             test_year: int,
                             min_results: int = 10,
                             target_variable: str = 'uci_points_actual',
                             num_boost_round: int = 1000,
                             early_stopping_rounds: int = 50,
                             save_models: bool = True,
                             verbose: bool = True,
                             use_optimized_generator: bool = True,
                             use_enhanced_experience: bool = False) -> Dict:
        """
        Run complete temporal backtest for a given year.
        
        Args:
            test_year: Year to test on (e.g., 2022)
            min_results: Minimum results per rider for inclusion
            target_variable: 'uci_points_actual' or 'uci_points_proportional'
            num_boost_round: Max boosting rounds for training
            early_stopping_rounds: Early stopping patience
            save_models: Whether to save trained models
            verbose: Whether to print progress
            use_optimized_generator: Whether to use optimized generator (default True)
            use_enhanced_experience: Whether to use enhanced experience features (default False)
            
        Returns:
            Dictionary with all results and metrics
        """
        if verbose:
            print(f"{'='*60}")
            print(f"TEMPORAL BACKTEST FOR {test_year}")
            print(f"{'='*60}")
            print(f"Target variable: {target_variable}")
            print(f"Minimum results per rider: {min_results}")
        
        # Define date ranges
        train_cutoff = f"{test_year-1}-12-31"
        test_start = f"{test_year}-01-01"
        test_end = f"{test_year}-12-31"
        
        if verbose:
            print(f"Training data: All data up to {train_cutoff}")
            print(f"Test data: {test_start} to {test_end}")
        
        # Generate training datasets
        if verbose:
            print(f"\nGenerating training datasets...")
        
        if use_optimized_generator:
            # Reinitialize optimized generator with enhanced experience setting
            if use_enhanced_experience:
                optimized_gen = OptimizedDatasetGenerator(self.db_path, use_enhanced_experience=True)
                train_datasets = optimized_gen.generate_datasets_fast(
                    cutoff_date=train_cutoff,
                    min_results=min_results,
                    target_variable=target_variable,
                    use_parallel=True
                )
            else:
                train_datasets = self.optimized_generator.generate_datasets_fast(
                    cutoff_date=train_cutoff,
                    min_results=min_results,
                    target_variable=target_variable,
                    use_parallel=True
                )
        else:
            train_datasets = self.generator.generate_datasets(
                cutoff_date=train_cutoff,
                min_results=min_results,
                target_variable=target_variable
            )
        
        # Generate test datasets
        if verbose:
            print(f"Generating test datasets...")
        
        test_datasets = self._get_test_datasets(
            train_cutoff, test_start, test_end, min_results, target_variable, use_optimized_generator
        )
        
        # Check if we have enough data
        if train_datasets['gc_dataset'].empty and train_datasets['stage_one_day_dataset'].empty:
            raise ValueError("No training data available")
        
        if test_datasets['gc_dataset'].empty and test_datasets['stage_one_day_dataset'].empty:
            raise ValueError(f"No test data available for {test_year}")
        
        # Initialize results
        results = {
            'test_year': test_year,
            'train_cutoff': train_cutoff,
            'target_variable': target_variable,
            'min_results': min_results,
            'data_stats': self._get_data_stats(train_datasets, test_datasets),
            'models': {},
            'predictions': {},
            'metrics': {},
            'feature_importance': {}
        }
        
        # Train and evaluate GC model
        if not train_datasets['gc_dataset'].empty and not test_datasets['gc_dataset'].empty:
            if verbose:
                print(f"\n{'='*40}")
                print("TRAINING GC MODEL")
                print(f"{'='*40}")
            
            gc_results = self._train_and_evaluate_model(
                model_type='gc',
                train_data=train_datasets['gc_dataset'],
                test_data=test_datasets['gc_dataset'],
                target_variable=target_variable,
                num_boost_round=num_boost_round,
                early_stopping_rounds=early_stopping_rounds,
                verbose=verbose
            )
            
            results['models']['gc'] = gc_results['model']
            results['predictions']['gc'] = gc_results['predictions']
            results['metrics']['gc'] = gc_results['metrics']
            results['feature_importance']['gc'] = gc_results['feature_importance']
            
            if save_models:
                model_path = f"{self.output_dir}/models/gc_model_{test_year}_{target_variable}"
                gc_results['model'].save(model_path)
                if verbose:
                    print(f"GC model saved to {model_path}")
        
        # Train and evaluate Stage/One-day model
        if not train_datasets['stage_one_day_dataset'].empty and not test_datasets['stage_one_day_dataset'].empty:
            if verbose:
                print(f"\n{'='*40}")
                print("TRAINING STAGE/ONE-DAY MODEL")
                print(f"{'='*40}")
            
            stage_results = self._train_and_evaluate_model(
                model_type='stage_one_day',
                train_data=train_datasets['stage_one_day_dataset'],
                test_data=test_datasets['stage_one_day_dataset'],
                target_variable=target_variable,
                num_boost_round=num_boost_round,
                early_stopping_rounds=early_stopping_rounds,
                verbose=verbose
            )
            
            results['models']['stage_one_day'] = stage_results['model']
            results['predictions']['stage_one_day'] = stage_results['predictions']
            results['metrics']['stage_one_day'] = stage_results['metrics']
            results['feature_importance']['stage_one_day'] = stage_results['feature_importance']
            
            if save_models:
                model_path = f"{self.output_dir}/models/stage_one_day_model_{test_year}_{target_variable}"
                stage_results['model'].save(model_path)
                if verbose:
                    print(f"Stage/One-day model saved to {model_path}")
        
        # Save results
        results_path = f"{self.output_dir}/results/backtest_{test_year}_{target_variable}.json"
        self._save_results(results, results_path)
        
        # Generate markdown report
        report_path = f"{self.output_dir}/results/backtest_{test_year}_{target_variable}_report.md"
        self._generate_markdown_report(results, report_path)
        
        # Generate plots
        if verbose:
            print(f"\nGenerating evaluation plots...")
        self._generate_plots(results, test_year, target_variable)
        
        # Print summary
        if verbose:
            print(f"\n{'='*60}")
            print("BACKTEST SUMMARY")
            print(f"{'='*60}")
            self._print_summary(results)
        
        return results
    
    def _get_test_datasets(self, train_cutoff: str, test_start: str, test_end: str, 
                          min_results: int, target_variable: str, use_optimized_generator: bool = True) -> Dict[str, pd.DataFrame]:
        """Get test datasets for the specified time period."""
        # Get rider-competition pairs for test period
        # Only include riders who had enough history before train_cutoff
        import sqlite3
        
        conn = sqlite3.connect(self.db_path)
        try:
            # Find riders with sufficient history before train_cutoff
            qualified_riders_query = """
            SELECT rider_id, COUNT(*) as prior_results
            FROM rider_results rr
            JOIN competitions c ON rr.competition_id = c.id
            WHERE c.date <= ?
            GROUP BY rider_id
            HAVING COUNT(*) >= ?
            """
            
            qualified_riders = pd.read_sql_query(
                qualified_riders_query, 
                conn, 
                params=[train_cutoff, min_results]
            )['rider_id'].tolist()
            
            if not qualified_riders:
                return {'gc_dataset': pd.DataFrame(), 'stage_one_day_dataset': pd.DataFrame()}
            
            # Get test pairs for qualified riders
            test_pairs_query = """
            SELECT DISTINCT rr.rider_id, rr.competition_id
            FROM rider_results rr
            JOIN competitions c ON rr.competition_id = c.id
            WHERE c.date BETWEEN ? AND ?
            AND rr.rider_id IN ({})
            ORDER BY c.date
            """.format(','.join('?' * len(qualified_riders)))
            
            cursor = conn.cursor()
            cursor.execute(test_pairs_query, [test_start, test_end] + qualified_riders)
            test_pairs = [(row[0], row[1]) for row in cursor.fetchall()]
            
        finally:
            conn.close()
        
        if not test_pairs:
            return {'gc_dataset': pd.DataFrame(), 'stage_one_day_dataset': pd.DataFrame()}
        
        # Build features for test pairs using train_cutoff for experience calculation
        if use_optimized_generator:
            test_dataset = self.optimized_feature_builder.build_bulk_dataset_fast(
                test_pairs, cutoff_date=train_cutoff, use_parallel=True
            )
        else:
            from feature_builder import FeatureBuilder
            builder = FeatureBuilder(self.db_path)
            test_dataset = builder.build_bulk_dataset(test_pairs, train_cutoff)
        
        if test_dataset.empty:
            return {'gc_dataset': pd.DataFrame(), 'stage_one_day_dataset': pd.DataFrame()}
        
        # Split by competition type
        gc_dataset = test_dataset[test_dataset['competition_type'] == 'gc'].copy()
        stage_one_day_dataset = test_dataset[
            test_dataset['competition_type'].isin(['stage', 'one_day'])
        ].copy()
        
        return {
            'gc_dataset': gc_dataset,
            'stage_one_day_dataset': stage_one_day_dataset
        }
    
    def _train_and_evaluate_model(self, model_type: str, train_data: pd.DataFrame,
                                 test_data: pd.DataFrame, target_variable: str,
                                 num_boost_round: int, early_stopping_rounds: int,
                                 verbose: bool) -> Dict:
        """Train and evaluate a single model."""
        # Initialize model
        model = RiderPerformanceModel(model_type=model_type)
        
        # Train model
        training_info = model.train(
            train_df=train_data,
            target_col=target_variable,
            num_boost_round=num_boost_round,
            early_stopping_rounds=early_stopping_rounds,
            verbose=verbose
        )
        
        # Make predictions on test data
        test_features, _ = model.prepare_features(test_data)
        predictions = model.predict(test_features)
        prob_nonzero = model.predict_proba_nonzero(test_features)
        
        # Calculate metrics
        test_targets = test_data[target_variable].values
        metrics = self._calculate_comprehensive_metrics(
            y_true=test_targets,
            y_pred=predictions,
            y_prob=prob_nonzero
        )
        
        # Calculate within-race ranking metrics
        race_metrics = self._calculate_within_race_metrics(
            test_data, predictions, target_variable
        )
        metrics.update(race_metrics)
        
        # Get feature importance
        feature_importance = model.get_top_features(n=20)
        
        return {
            'model': model,
            'predictions': {
                'y_true': test_targets.tolist(),
                'y_pred': predictions.tolist(),
                'y_prob_nonzero': prob_nonzero.tolist(),
                'rider_ids': test_data['rider_id'].tolist(),
                'competition_ids': test_data['competition_id'].tolist(),
                'competition_names': test_data['competition_name'].tolist(),
                'race_names': test_data['race_name'].tolist()
            },
            'metrics': metrics,
            'feature_importance': feature_importance.to_dict('records'),
            'training_info': training_info
        }
    
    def _calculate_within_race_metrics(self, test_data: pd.DataFrame, 
                                     predictions: np.ndarray, 
                                     target_variable: str) -> Dict:
        """Calculate within-race ranking accuracy metrics."""
        from scipy.stats import spearmanr
        
        race_results = []
        
        # Group by competition
        test_data_with_pred = test_data.copy()
        test_data_with_pred['prediction'] = predictions
        
        for competition_id, race_data in test_data_with_pred.groupby('competition_id'):
            if len(race_data) < 3:  # Skip races with too few riders
                continue
                
            y_true_race = race_data[target_variable].values
            y_pred_race = race_data['prediction'].values
            
            # Skip if no variation in the race
            if np.std(y_true_race) == 0 or np.std(y_pred_race) == 0:
                continue
            
            # Spearman correlation for this race
            race_spearman = spearmanr(y_true_race, y_pred_race).correlation
            
            # Top-K accuracy within race
            race_top_k = {}
            for k in [3, 5, 10]:
                if len(y_true_race) >= k:
                    true_top_k = set(np.argsort(y_true_race)[-k:])
                    pred_top_k = set(np.argsort(y_pred_race)[-k:])
                    race_top_k[f'top_{k}'] = len(true_top_k & pred_top_k) / k
            
            race_results.append({
                'competition_id': competition_id,
                'spearman': race_spearman,
                'n_riders': len(race_data),
                **race_top_k
            })
        
        if not race_results:
            return {
                'within_race_spearman_mean': 0.0,
                'within_race_spearman_std': 0.0,
                'within_race_top_3_mean': 0.0,
                'within_race_top_5_mean': 0.0,
                'within_race_top_10_mean': 0.0,
                'n_races_evaluated': 0
            }
        
        # Aggregate race-level metrics
        race_df = pd.DataFrame(race_results)
        
        return {
            'within_race_spearman_mean': float(race_df['spearman'].mean()),
            'within_race_spearman_std': float(race_df['spearman'].std()),
            'within_race_top_3_mean': float(race_df['top_3'].mean()) if 'top_3' in race_df else 0.0,
            'within_race_top_5_mean': float(race_df['top_5'].mean()) if 'top_5' in race_df else 0.0,
            'within_race_top_10_mean': float(race_df['top_10'].mean()) if 'top_10' in race_df else 0.0,
            'n_races_evaluated': len(race_results)
        }
    
    def _calculate_comprehensive_metrics(self, y_true: np.ndarray, 
                                        y_pred: np.ndarray, 
                                        y_prob: np.ndarray) -> Dict:
        """Calculate comprehensive evaluation metrics."""
        from scipy.stats import spearmanr
        
        # Overall regression metrics
        rmse_overall = np.sqrt(mean_squared_error(y_true, y_pred))
        mae_overall = mean_absolute_error(y_true, y_pred)
        
        # Metrics for non-zero samples only
        non_zero_mask = y_true > 0
        n_nonzero = non_zero_mask.sum()
        
        if n_nonzero > 0:
            rmse_nonzero = np.sqrt(mean_squared_error(y_true[non_zero_mask], y_pred[non_zero_mask]))
            mae_nonzero = mean_absolute_error(y_true[non_zero_mask], y_pred[non_zero_mask])
            r2_nonzero = r2_score(y_true[non_zero_mask], y_pred[non_zero_mask])
            
            # Mean prediction on non-zero samples
            mean_true_nonzero = y_true[non_zero_mask].mean()
            mean_pred_nonzero = y_pred[non_zero_mask].mean()
        else:
            rmse_nonzero = mae_nonzero = r2_nonzero = 0.0
            mean_true_nonzero = mean_pred_nonzero = 0.0
        
        # Ranking metrics
        # Spearman correlation (overall)
        if len(y_true) > 1 and np.std(y_true) > 0 and np.std(y_pred) > 0:
            spearman_overall = spearmanr(y_true, y_pred).correlation
        else:
            spearman_overall = 0.0
            
        # Spearman correlation (non-zero only)
        if n_nonzero > 1 and np.std(y_true[non_zero_mask]) > 0 and np.std(y_pred[non_zero_mask]) > 0:
            spearman_nonzero = spearmanr(y_true[non_zero_mask], y_pred[non_zero_mask]).correlation
        else:
            spearman_nonzero = 0.0
        
        # Top-K accuracy metrics
        top_k_metrics = {}
        for k in [5, 10, 20]:
            if len(y_true) >= k:
                true_top_k = set(np.argsort(y_true)[-k:])
                pred_top_k = set(np.argsort(y_pred)[-k:])
                top_k_accuracy = len(true_top_k & pred_top_k) / k
                top_k_metrics[f'top_{k}_accuracy'] = float(top_k_accuracy)
            else:
                top_k_metrics[f'top_{k}_accuracy'] = 0.0
        
        # Classification metrics (0 vs non-0)
        y_true_binary = (y_true > 0).astype(int)
        auc_score = roc_auc_score(y_true_binary, y_prob)
        
        # Precision, Recall, F1 for non-zero prediction
        from sklearn.metrics import precision_score, recall_score, f1_score
        y_pred_binary = (y_prob > 0.5).astype(int)
        precision = precision_score(y_true_binary, y_pred_binary, zero_division=0)
        recall = recall_score(y_true_binary, y_pred_binary, zero_division=0)
        f1 = f1_score(y_true_binary, y_pred_binary, zero_division=0)
        
        # Zero prediction accuracy
        zero_mask = y_true == 0
        n_zeros = zero_mask.sum()
        zero_accuracy = ((y_pred[zero_mask] == 0).sum() / n_zeros) if n_zeros > 0 else 0.0
        
        # Points distribution metrics
        total_true_points = y_true.sum()
        total_pred_points = y_pred.sum()
        points_ratio = total_pred_points / total_true_points if total_true_points > 0 else 0.0
        
        # Percentile analysis
        percentiles = [50, 75, 90, 95, 99]
        true_percentiles = {f'true_p{p}': np.percentile(y_true[y_true > 0], p) for p in percentiles} if n_nonzero > 0 else {}
        pred_percentiles = {f'pred_p{p}': np.percentile(y_pred[y_pred > 0], p) for p in percentiles} if (y_pred > 0).sum() > 0 else {}
        
        return {
            # Sample counts
            'n_total': len(y_true),
            'n_zeros': int(n_zeros),
            'n_nonzeros': int(n_nonzero),
            'zero_percentage': float(n_zeros / len(y_true) * 100),
            
            # Overall regression metrics
            'rmse_overall': float(rmse_overall),
            'mae_overall': float(mae_overall),
            
            # Non-zero regression metrics
            'rmse_nonzero': float(rmse_nonzero),
            'mae_nonzero': float(mae_nonzero),
            'r2_nonzero': float(r2_nonzero),
            'mean_true_nonzero': float(mean_true_nonzero),
            'mean_pred_nonzero': float(mean_pred_nonzero),
            
            # Ranking metrics
            'spearman_overall': float(spearman_overall),
            'spearman_nonzero': float(spearman_nonzero),
            **top_k_metrics,
            
            # Classification metrics
            'auc_classification': float(auc_score),
            'precision_nonzero': float(precision),
            'recall_nonzero': float(recall),
            'f1_nonzero': float(f1),
            'zero_prediction_accuracy': float(zero_accuracy),
            
            # Points distribution
            'total_true_points': float(total_true_points),
            'total_pred_points': float(total_pred_points),
            'points_ratio': float(points_ratio),
            
            # Percentiles
            **true_percentiles,
            **pred_percentiles
        }
    
    def _get_data_stats(self, train_datasets: Dict, test_datasets: Dict) -> Dict:
        """Get statistics about the training and test datasets."""
        stats = {}
        
        for dataset_name in ['gc_dataset', 'stage_one_day_dataset']:
            train_data = train_datasets[dataset_name]
            test_data = test_datasets[dataset_name]
            
            stats[dataset_name] = {
                'train_samples': len(train_data),
                'test_samples': len(test_data),
                'train_riders': train_data['rider_id'].nunique() if not train_data.empty else 0,
                'test_riders': test_data['rider_id'].nunique() if not test_data.empty else 0,
                'train_zeros': (train_data['uci_points_actual'] == 0).sum() if not train_data.empty else 0,
                'test_zeros': (test_data['uci_points_actual'] == 0).sum() if not test_data.empty else 0
            }
        
        return stats
    
    def _save_results(self, results: Dict, filepath: str):
        """Save results to JSON file."""
        # Create a serializable copy
        serializable_results = results.copy()
        
        # Remove model objects (not JSON serializable)
        if 'models' in serializable_results:
            del serializable_results['models']
        
        # Convert numpy types to native Python types
        serializable_results = self._convert_numpy_types(serializable_results)
        
        with open(filepath, 'w') as f:
            json.dump(serializable_results, f, indent=2)
        
        print(f"Results saved to {filepath}")
    
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
    
    def _generate_plots(self, results: Dict, test_year: int, target_variable: str):
        """Generate evaluation plots."""
        plot_dir = f"{self.output_dir}/plots"
        
        for model_type in ['gc', 'stage_one_day']:
            if model_type not in results['predictions']:
                continue
                
            pred_data = results['predictions'][model_type]
            y_true = np.array(pred_data['y_true'])
            y_pred = np.array(pred_data['y_pred'])
            y_prob = np.array(pred_data['y_prob_nonzero'])
            
            # Create plots
            fig, axes = plt.subplots(2, 2, figsize=(15, 12))
            fig.suptitle(f'{model_type.upper()} Model - {test_year} Backtest ({target_variable})', fontsize=16)
            
            # Plot 1: Predicted vs Actual (non-zero only)
            non_zero_mask = y_true > 0
            if non_zero_mask.sum() > 0:
                axes[0, 0].scatter(y_true[non_zero_mask], y_pred[non_zero_mask], alpha=0.6)
                axes[0, 0].plot([0, y_true.max()], [0, y_true.max()], 'r--', lw=2)
                axes[0, 0].set_xlabel('Actual Points')
                axes[0, 0].set_ylabel('Predicted Points')
                axes[0, 0].set_title('Predicted vs Actual (Non-zero only)')
            
            # Plot 2: Probability distribution
            axes[0, 1].hist(y_prob[y_true == 0], bins=50, alpha=0.7, label='Zero points', density=True)
            axes[0, 1].hist(y_prob[y_true > 0], bins=50, alpha=0.7, label='Non-zero points', density=True)
            axes[0, 1].set_xlabel('Probability of Non-zero Points')
            axes[0, 1].set_ylabel('Density')
            axes[0, 1].set_title('Classification Probability Distribution')
            axes[0, 1].legend()
            
            # Plot 3: Residuals (non-zero only)
            if non_zero_mask.sum() > 0:
                residuals = y_pred[non_zero_mask] - y_true[non_zero_mask]
                axes[1, 0].scatter(y_true[non_zero_mask], residuals, alpha=0.6)
                axes[1, 0].axhline(y=0, color='r', linestyle='--')
                axes[1, 0].set_xlabel('Actual Points')
                axes[1, 0].set_ylabel('Residuals')
                axes[1, 0].set_title('Residuals vs Actual (Non-zero only)')
            
            # Plot 4: Feature importance
            if model_type in results['feature_importance']:
                feat_imp = pd.DataFrame(results['feature_importance'][model_type])
                top_10 = feat_imp.head(10)
                axes[1, 1].barh(range(len(top_10)), top_10['importance'])
                axes[1, 1].set_yticks(range(len(top_10)))
                axes[1, 1].set_yticklabels(top_10['feature'])
                axes[1, 1].set_xlabel('Feature Importance')
                axes[1, 1].set_title('Top 10 Features')
            
            plt.tight_layout()
            plt.savefig(f"{plot_dir}/{model_type}_backtest_{test_year}_{target_variable}.png", 
                       dpi=300, bbox_inches='tight')
            plt.close()
    
    def _print_summary(self, results: Dict):
        """Print a comprehensive summary of the backtest results."""
        print(f"\nTest Year: {results['test_year']}")
        print(f"Target Variable: {results['target_variable']}")
        print(f"Training Cutoff: {results['train_cutoff']}")
        
        print(f"\nData Statistics:")
        for dataset_name, stats in results['data_stats'].items():
            print(f"  {dataset_name}:")
            print(f"    Train: {stats['train_samples']:,} samples, {stats['train_riders']:,} riders")
            print(f"    Test: {stats['test_samples']:,} samples, {stats['test_riders']:,} riders")
            print(f"    Train zeros: {stats['train_zeros']:,} ({stats['train_zeros']/stats['train_samples']*100:.1f}%)")
            print(f"    Test zeros: {stats['test_zeros']:,} ({stats['test_zeros']/stats['test_samples']*100:.1f}%)")
        
        print(f"\nModel Performance Summary:")
        for model_type, metrics in results['metrics'].items():
            print(f"\n  {model_type.upper()} MODEL:")
            
            # Zero inflation stats
            print(f"    Zero inflation: {metrics['zero_percentage']:.1f}% zeros in test set")
            print(f"    Non-zero samples: {metrics['n_nonzeros']:,}")
            
            # Ranking metrics (most important)
            print(f"\n    RANKING METRICS:")
            print(f"      Spearman correlation (overall): {metrics['spearman_overall']:.4f}")
            print(f"      Spearman correlation (non-zero): {metrics['spearman_nonzero']:.4f}")
            print(f"      Within-race Spearman (mean): {metrics['within_race_spearman_mean']:.4f}")
            print(f"      Top-5 accuracy: {metrics['top_5_accuracy']:.4f}")
            print(f"      Top-10 accuracy: {metrics['top_10_accuracy']:.4f}")
            print(f"      Top-20 accuracy: {metrics['top_20_accuracy']:.4f}")
            print(f"      Within-race top-3 (mean): {metrics['within_race_top_3_mean']:.4f}")
            print(f"      Within-race top-5 (mean): {metrics['within_race_top_5_mean']:.4f}")
            
            # Classification metrics
            print(f"\n    CLASSIFICATION METRICS (0 vs non-0):")
            print(f"      AUC: {metrics['auc_classification']:.4f}")
            print(f"      Precision: {metrics['precision_nonzero']:.4f}")
            print(f"      Recall: {metrics['recall_nonzero']:.4f}")
            print(f"      F1 Score: {metrics['f1_nonzero']:.4f}")
            
            # Regression metrics
            print(f"\n    REGRESSION METRICS:")
            print(f"      RMSE (overall): {metrics['rmse_overall']:.4f}")
            print(f"      RMSE (non-zero only): {metrics['rmse_nonzero']:.4f}")
            print(f"      MAE (non-zero only): {metrics['mae_nonzero']:.4f}")
            print(f"      R² (non-zero only): {metrics['r2_nonzero']:.4f}")
            
            # Points distribution
            print(f"\n    POINTS DISTRIBUTION:")
            print(f"      Total true points: {metrics['total_true_points']:,.0f}")
            print(f"      Total predicted points: {metrics['total_pred_points']:,.0f}")
            print(f"      Points ratio (pred/true): {metrics['points_ratio']:.4f}")
            print(f"      Mean non-zero true: {metrics['mean_true_nonzero']:.2f}")
            print(f"      Mean non-zero pred: {metrics['mean_pred_nonzero']:.2f}")
    
    def _generate_markdown_report(self, results: Dict, filepath: str):
        """Generate a comprehensive markdown report of the backtest results."""
        report_lines = []
        
        # Header
        report_lines.append(f"# Temporal Backtest Report - {results['test_year']}")
        report_lines.append(f"\n**Target Variable:** {results['target_variable']}")
        report_lines.append(f"**Training Data:** Up to {results['train_cutoff']}")
        report_lines.append(f"**Test Year:** {results['test_year']}")
        report_lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Data Statistics
        report_lines.append("\n## Data Statistics")
        report_lines.append("\n| Dataset | Train Samples | Train Riders | Test Samples | Test Riders | Train Zeros | Test Zeros |")
        report_lines.append("|---------|---------------|--------------|--------------|-------------|-------------|------------|")
        
        for dataset_name, stats in results['data_stats'].items():
            train_zero_pct = stats['train_zeros']/stats['train_samples']*100 if stats['train_samples'] > 0 else 0
            test_zero_pct = stats['test_zeros']/stats['test_samples']*100 if stats['test_samples'] > 0 else 0
            
            report_lines.append(
                f"| {dataset_name} | {stats['train_samples']:,} | {stats['train_riders']:,} | "
                f"{stats['test_samples']:,} | {stats['test_riders']:,} | "
                f"{stats['train_zeros']:,} ({train_zero_pct:.1f}%) | "
                f"{stats['test_zeros']:,} ({test_zero_pct:.1f}%) |"
            )
        
        # Model Performance
        for model_type, metrics in results['metrics'].items():
            report_lines.append(f"\n## {model_type.upper()} Model Performance")
            
            # Key Statistics
            report_lines.append(f"\n### Key Statistics")
            report_lines.append(f"- **Zero inflation:** {metrics['zero_percentage']:.1f}% of test samples have 0 points")
            report_lines.append(f"- **Non-zero samples:** {metrics['n_nonzeros']:,} out of {metrics['n_total']:,}")
            report_lines.append(f"- **Races evaluated:** {metrics.get('n_races_evaluated', 'N/A')}")
            
            # Ranking Metrics
            report_lines.append(f"\n### Ranking Metrics (Most Important)")
            report_lines.append("\n| Metric | Value |")
            report_lines.append("|--------|-------|")
            report_lines.append(f"| Spearman Correlation (Overall) | {metrics['spearman_overall']:.4f} |")
            report_lines.append(f"| Spearman Correlation (Non-zero) | {metrics['spearman_nonzero']:.4f} |")
            report_lines.append(f"| Within-race Spearman (Mean) | {metrics['within_race_spearman_mean']:.4f} |")
            report_lines.append(f"| Within-race Spearman (Std) | {metrics['within_race_spearman_std']:.4f} |")
            report_lines.append(f"| Top-5 Accuracy | {metrics['top_5_accuracy']:.4f} |")
            report_lines.append(f"| Top-10 Accuracy | {metrics['top_10_accuracy']:.4f} |")
            report_lines.append(f"| Top-20 Accuracy | {metrics['top_20_accuracy']:.4f} |")
            report_lines.append(f"| Within-race Top-3 (Mean) | {metrics['within_race_top_3_mean']:.4f} |")
            report_lines.append(f"| Within-race Top-5 (Mean) | {metrics['within_race_top_5_mean']:.4f} |")
            report_lines.append(f"| Within-race Top-10 (Mean) | {metrics['within_race_top_10_mean']:.4f} |")
            
            # Classification Metrics
            report_lines.append(f"\n### Classification Metrics (0 vs Non-0)")
            report_lines.append("\n| Metric | Value |")
            report_lines.append("|--------|-------|")
            report_lines.append(f"| AUC | {metrics['auc_classification']:.4f} |")
            report_lines.append(f"| Precision | {metrics['precision_nonzero']:.4f} |")
            report_lines.append(f"| Recall | {metrics['recall_nonzero']:.4f} |")
            report_lines.append(f"| F1 Score | {metrics['f1_nonzero']:.4f} |")
            report_lines.append(f"| Zero Prediction Accuracy | {metrics['zero_prediction_accuracy']:.4f} |")
            
            # Regression Metrics
            report_lines.append(f"\n### Regression Metrics")
            report_lines.append("\n| Metric | Overall | Non-zero Only |")
            report_lines.append("|--------|---------|---------------|")
            report_lines.append(f"| RMSE | {metrics['rmse_overall']:.4f} | {metrics['rmse_nonzero']:.4f} |")
            report_lines.append(f"| MAE | {metrics['mae_overall']:.4f} | {metrics['mae_nonzero']:.4f} |")
            report_lines.append(f"| R² | N/A | {metrics['r2_nonzero']:.4f} |")
            
            # Points Distribution
            report_lines.append(f"\n### Points Distribution")
            report_lines.append("\n| Metric | Value |")
            report_lines.append("|--------|-------|")
            report_lines.append(f"| Total True Points | {metrics['total_true_points']:,.0f} |")
            report_lines.append(f"| Total Predicted Points | {metrics['total_pred_points']:,.0f} |")
            report_lines.append(f"| Points Ratio (Pred/True) | {metrics['points_ratio']:.4f} |")
            report_lines.append(f"| Mean True (Non-zero) | {metrics['mean_true_nonzero']:.2f} |")
            report_lines.append(f"| Mean Predicted (Non-zero) | {metrics['mean_pred_nonzero']:.2f} |")
            
            # Feature Importance
            if model_type in results.get('feature_importance', {}):
                report_lines.append(f"\n### Top 10 Most Important Features")
                report_lines.append("\n| Rank | Feature | Importance |")
                report_lines.append("|------|---------|------------|")
                
                features = results['feature_importance'][model_type][:10]
                for i, feat in enumerate(features, 1):
                    report_lines.append(f"| {i} | {feat['feature']} | {feat['importance']:.2f} |")
        
        # Write to file
        with open(filepath, 'w') as f:
            f.write('\n'.join(report_lines))
        
        print(f"Markdown report saved to {filepath}")


def run_multiple_years(db_path: str, 
                      test_years: List[int] = [2022, 2023, 2024],
                      target_variable: str = 'uci_points_actual',
                      min_results: int = 10) -> Dict:
    """
    Run backtests for multiple years.
    
    Args:
        db_path: Path to database
        test_years: List of years to test
        target_variable: Target variable to use
        min_results: Minimum results per rider
        
    Returns:
        Dictionary with results for all years
    """
    backtester = TemporalBacktester(db_path)
    all_results = {}
    
    for year in test_years:
        print(f"\n{'='*80}")
        print(f"RUNNING BACKTEST FOR {year}")
        print(f"{'='*80}")
        
        try:
            results = backtester.run_temporal_backtest(
                test_year=year,
                min_results=min_results,
                target_variable=target_variable,
                save_models=True,
                verbose=True
            )
            all_results[year] = results
            
        except Exception as e:
            print(f"Error running backtest for {year}: {e}")
            all_results[year] = {'error': str(e)}
    
    return all_results


if __name__ == "__main__":
    # Example usage
    db_path = "database/database/cycling_races.db"
    
    # Run single year backtest
    backtester = TemporalBacktester(db_path)
    
    # Test 2023 (trains on all data up to 2022-12-31, tests on 2023)
    results_2023 = backtester.run_temporal_backtest(
        test_year=2023,
        min_results=10,
        target_variable='uci_points_actual',
        save_models=True,
        verbose=True
    )
    
    # Run multiple years
    print("\n" + "="*80)
    print("RUNNING MULTIPLE YEAR BACKTESTS")
    print("="*80)
    
    all_results = run_multiple_years(
        db_path=db_path,
        test_years=[2022, 2023],
        target_variable='uci_points_actual',
        min_results=15
    )