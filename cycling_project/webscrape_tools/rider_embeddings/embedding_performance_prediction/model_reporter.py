import pandas as pd
import numpy as np
from typing import Dict, List, Optional
import json
from pathlib import Path
from datetime import datetime
from tabulate import tabulate


class ModelReporter:
    """Generate comprehensive reports for embedding-based prediction models."""
    
    def __init__(self, output_dir: str = "embedding_model_performance_reports"):
        """
        Initialize the model reporter.
        
        Args:
            output_dir: Directory to save reports
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_training_report(
        self,
        model,
        train_stats: Dict,
        test_stats: Dict,
        test_year: int,
        save_file: bool = True
    ) -> Dict:
        """
        Generate comprehensive training report for a model.
        
        Args:
            model: Trained EmbeddingPerformanceModel
            train_stats: Statistics from training data
            test_stats: Statistics from test data
            test_year: Year used for testing
            save_file: Whether to save report to file
            
        Returns:
            Dictionary containing the full report
        """
        report = {
            'metadata': {
                'race_type': model.race_type,
                'test_year': test_year,
                'report_date': datetime.now().isoformat(),
                'model_type': 'embedding_performance_model'
            },
            'dataset_info': {
                'training': {
                    'n_rider_results': train_stats['n_samples'],
                    'n_competitions': train_stats['n_competitions'],
                    'n_riders': train_stats['n_riders'],
                    'years': train_stats['years'],
                    'target_stats': train_stats['target_stats']
                },
                'test': {
                    'n_rider_results': test_stats['n_samples'],
                    'n_competitions': test_stats['n_competitions'],
                    'n_riders': test_stats['n_riders'],
                    'years': test_stats['years'],
                    'target_stats': test_stats['target_stats']
                }
            },
            'model_performance': model.training_info['performance_metrics'],
            'model_details': {
                'n_features': model.training_info['n_features'],
                'n_embedding_features': model.training_info['n_embedding_features'],
                'n_database_features': model.training_info['n_database_features'],
                'classifier_iterations': model.training_info['classifier_iterations'],
                'regressor_iterations': model.training_info['regressor_iterations']
            },
            'feature_importance': self._get_feature_importance_report(model)
        }
        
        if save_file:
            filename = f"{model.race_type}_model_report_{test_year}.json"
            filepath = self.output_dir / filename
            with open(filepath, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"Report saved to: {filepath}")
            
            # Generate text summary
            self._generate_text_summary(report, filepath.with_suffix('.txt'))
        
        return report
    
    def _get_feature_importance_report(self, model) -> Dict:
        """Get detailed feature importance for both stages."""
        # Get all features importance
        importance_df = model.get_feature_importance(stage='both')
        
        # Separate by stage and type
        report = {}
        
        for stage in ['classifier', 'regressor']:
            stage_df = importance_df[importance_df['stage'] == stage].copy()
            
            # Get top features by type
            embedding_features = stage_df[stage_df['feature_type'] == 'embedding'].head(20)
            race_features = stage_df[stage_df['feature_type'] == 'race'].head(20)
            database_features = stage_df[stage_df['feature_type'] == 'database'].head(20)
            
            report[stage] = {
                'top_embedding_features': embedding_features[['feature', 'importance']].to_dict('records'),
                'top_race_features': race_features[['feature', 'importance']].to_dict('records'),
                'top_database_features': database_features[['feature', 'importance']].to_dict('records'),
                'all_features': stage_df[['feature', 'importance', 'feature_type']].to_dict('records')
            }
        
        return report
    
    def generate_multi_race_type_report(
        self,
        results: Dict[str, Dict],
        test_year: int,
        save_file: bool = True
    ) -> Dict:
        """
        Generate report comparing multiple race type models.
        
        Args:
            results: Dictionary mapping race_type to training results
            test_year: Year used for testing
            save_file: Whether to save report to file
            
        Returns:
            Consolidated report dictionary
        """
        consolidated_report = {
            'metadata': {
                'test_year': test_year,
                'report_date': datetime.now().isoformat(),
                'race_types': list(results.keys())
            },
            'race_type_results': results,
            'summary': self._generate_summary_table(results)
        }
        
        if save_file:
            filename = f"all_models_report_{test_year}.json"
            filepath = self.output_dir / filename
            with open(filepath, 'w') as f:
                json.dump(consolidated_report, f, indent=2)
            print(f"Consolidated report saved to: {filepath}")
        
        return consolidated_report
    
    def _generate_summary_table(self, results: Dict[str, Dict]) -> Dict:
        """Generate summary comparison table."""
        summary_data = []
        
        for race_type, result in results.items():
            if 'model_performance' in result:
                perf = result['model_performance']
                data_info = result['dataset_info']
                
                summary_data.append({
                    'race_type': race_type,
                    'train_samples': data_info['training']['n_rider_results'],
                    'test_samples': data_info['test']['n_rider_results'],
                    'rmse_overall': perf['rmse_overall'],
                    'rmse_nonzero': perf['rmse_nonzero'],
                    'auc_classification': perf['auc_classification'],
                    'zero_accuracy': perf['zero_accuracy']
                })
        
        return pd.DataFrame(summary_data).to_dict('records')
    
    def print_training_summary(self, model, train_stats: Dict, test_stats: Dict):
        """Print a formatted training summary to console."""
        print(f"\n{'='*60}")
        print(f"Training Summary - {model.race_type.upper()} Model")
        print(f"{'='*60}")
        
        # Dataset information
        print("\nDataset Information:")
        print(f"  Training set:")
        print(f"    - Rider results: {train_stats['n_samples']:,}")
        print(f"    - Competitions: {train_stats['n_competitions']:,}")
        print(f"    - Years: {min(train_stats['years'])} - {max(train_stats['years'])}")
        print(f"    - Zero rate: {train_stats['target_stats']['zero_rate']:.2%}")
        
        print(f"\n  Test set:")
        print(f"    - Rider results: {test_stats['n_samples']:,}")
        print(f"    - Competitions: {test_stats['n_competitions']:,}")
        print(f"    - Year: {test_stats['years'][0]}")
        print(f"    - Zero rate: {test_stats['target_stats']['zero_rate']:.2%}")
        
        # Model performance
        perf = model.training_info['performance_metrics']
        print("\nModel Performance:")
        print(f"  Overall RMSE: {perf['rmse_overall']:.4f}")
        print(f"  Overall MAE: {perf['mae_overall']:.4f}")
        print(f"  Non-zero RMSE: {perf['rmse_nonzero']:.4f}")
        print(f"  Non-zero MAE: {perf['mae_nonzero']:.4f}")
        print(f"  Non-zero R²: {perf['r2_nonzero']:.4f}")
        print(f"  Classification AUC: {perf['auc_classification']:.4f}")
        print(f"  Zero prediction accuracy: {perf['zero_accuracy']:.2%}")
        
        # Feature information
        print("\nFeature Information:")
        print(f"  Total features: {model.training_info['n_features']}")
        print(f"  Embedding features: {model.training_info['n_embedding_features']}")
        print(f"  Race features: {model.training_info.get('n_race_features', 0)}")
        print(f"  Database features: {model.training_info['n_database_features']}")
        
        # Top features
        print("\nTop 10 Features (Classifier):")
        clf_importance = model.get_feature_importance(stage='classifier', n_features=10)
        for idx, row in clf_importance.iterrows():
            emoji_map = {'embedding': '📊', 'race': '🏁', 'database': '📋'}
            feature_type = emoji_map.get(row['feature_type'], '📋')
            print(f"  {feature_type} {row['feature']}: {row['importance']:.2f}")
        
        print("\nTop 10 Features (Regressor):")
        reg_importance = model.get_feature_importance(stage='regressor', n_features=10)
        for idx, row in reg_importance.iterrows():
            emoji_map = {'embedding': '📊', 'race': '🏁', 'database': '📋'}
            feature_type = emoji_map.get(row['feature_type'], '📋')
            print(f"  {feature_type} {row['feature']}: {row['importance']:.2f}")
        
        print(f"\n{'='*60}\n")
    
    def _generate_text_summary(self, report: Dict, filepath: Path):
        """Generate a text summary of the model report."""
        race_type = report['metadata']['race_type']
        test_year = report['metadata']['test_year']
        
        # Determine if this is using full embeddings
        n_embedding_features = report['model_details']['n_embedding_features']
        is_full_embeddings = n_embedding_features > 15  # Heuristic: full embeddings have ~37 features
        
        with open(filepath, 'w') as f:
            f.write('='*80 + '\n')
            if is_full_embeddings:
                f.write(f'🎯 {race_type.upper()} MODEL WITH FULL EMBEDDINGS\n')
            else:
                f.write(f'🎯 {race_type.upper()} MODEL WITH OPTIMIZED EMBEDDINGS\n')
            f.write('='*80 + '\n\n')
            
            # Model performance
            f.write('📊 MODEL PERFORMANCE:\n')
            perf = report['model_performance']
            f.write(f'  Classification AUC:    {perf["auc_classification"]:.4f}\n')
            f.write(f'  Overall RMSE:          {perf["rmse_overall"]:.2f} UCI points\n')
            f.write(f'  Non-zero RMSE:         {perf["rmse_nonzero"]:.2f} UCI points\n')
            f.write(f'  Non-zero R²:           {perf["r2_nonzero"]:.4f}\n')
            f.write(f'  Zero prediction acc:   {perf["zero_accuracy"]:.1%}\n\n')
            
            # Feature breakdown
            f.write('🔧 FEATURE BREAKDOWN:\n')
            details = report['model_details']
            n_race_features = len([f for f in report["feature_importance"]["classifier"]["top_race_features"] 
                                 if f["importance"] > 0])
            f.write(f'  Total features:        {details["n_features"]}\n')
            f.write(f'  📊 Embedding features:  {details["n_embedding_features"]} (rider correlations)\n')
            f.write(f'  🏁 Race features:        {n_race_features} (actual race characteristics)\n')
            f.write(f'  📋 Database features:    {details["n_database_features"]} (rider history)\n\n')
            
            # Top 15 features
            f.write('🏆 TOP 15 FEATURES (Classifier):\n')
            for i, feature in enumerate(report['feature_importance']['classifier']['all_features'][:15], 1):
                name = feature['feature']
                importance = feature['importance']
                ftype = feature['feature_type']
                icon = {'database': '📋', 'race': '🏁', 'embedding': '📊'}[ftype]
                f.write(f'  {i:2d}. {icon} {name:35s} {importance:8.1f}\n')
            f.write('\n')
            
            # Embedding features analysis
            embedding_in_top15 = [f for f in report['feature_importance']['classifier']['all_features'][:15]
                                 if f['feature_type'] == 'embedding']
            f.write('🔍 EMBEDDING FEATURES IN TOP 15:\n')
            f.write(f'  Count: {len(embedding_in_top15)}/15 ({len(embedding_in_top15)/15:.1%})\n')
            for i, feature in enumerate(embedding_in_top15, 1):
                corr_name = feature['feature'].replace('corr_', '')
                f.write(f'    {i}. {feature["feature"]:35s} → Rider correlation with {corr_name}\n')
            f.write('\n')
            
            # Files generated
            f.write('💾 FILES GENERATED:\n')
            f.write(f'  📄 JSON Report:     reports/{race_type}_model_report_{test_year}.json\n')
            f.write(f'  📄 Text Summary:    reports/{race_type}_model_report_{test_year}.txt\n')
            
            # Model filename depends on embedding type
            if is_full_embeddings:
                f.write(f'  🤖 Trained Model:   models/{race_type}_model_{test_year}_full_*\n')
            else:
                f.write(f'  🤖 Trained Model:   models/{race_type}_model_{test_year}\n')
            
            f.write(f'  📈 Feature CSVs:    reports/{race_type}_feature_importance_*.csv\n\n')
            
            # Dataset stats
            f.write('📈 DATASET STATISTICS:\n')
            train_info = report['dataset_info']['training']
            test_info = report['dataset_info']['test']
            f.write(f'  Training: {train_info["n_rider_results"]} samples, {train_info["n_competitions"]} competitions\n')
            f.write(f'  Testing:  {test_info["n_rider_results"]} samples, {test_info["n_competitions"]} competitions\n')
            f.write(f'  Years:    {min(train_info["years"])}-{max(train_info["years"])} → {test_info["years"][0]}\n')
        
        print(f"Text summary saved to: {filepath}")
    
    def export_feature_importance_csv(self, model, filename: Optional[str] = None):
        """Export feature importance to CSV files."""
        if filename is None:
            filename = f"{model.race_type}_feature_importance"
        
        # Get importance for both stages
        importance_df = model.get_feature_importance(stage='both')
        
        # Save full importance
        full_path = self.output_dir / f"{filename}_full.csv"
        importance_df.to_csv(full_path, index=False)
        
        # Save by stage
        for stage in ['classifier', 'regressor']:
            stage_df = importance_df[importance_df['stage'] == stage]
            stage_path = self.output_dir / f"{filename}_{stage}.csv"
            stage_df.to_csv(stage_path, index=False)
        
        print(f"Feature importance exported to {self.output_dir}/")
    
    def compare_models_table(self, models: Dict[str, any], test_data: Dict[str, pd.DataFrame]):
        """
        Generate comparison table for multiple models.
        
        Args:
            models: Dictionary mapping race_type to trained models
            test_data: Dictionary mapping race_type to test dataframes
        """
        comparison_data = []
        
        for race_type, model in models.items():
            if race_type in test_data:
                test_df = test_data[race_type]
                
                # Get predictions
                X_test, _ = model._prepare_features(test_df)
                y_test = test_df['uci_points_proportional'].values
                predictions = model.predict(X_test)
                
                # Calculate metrics
                rmse = np.sqrt(mean_squared_error(y_test, predictions))
                mae = mean_absolute_error(y_test, predictions)
                
                nonzero_mask = y_test > 0
                rmse_nonzero = np.sqrt(mean_squared_error(
                    y_test[nonzero_mask], 
                    predictions[nonzero_mask]
                )) if nonzero_mask.any() else np.nan
                
                comparison_data.append({
                    'Race Type': race_type.upper(),
                    'Test Samples': len(test_df),
                    'RMSE': f"{rmse:.4f}",
                    'MAE': f"{mae:.4f}",
                    'Non-zero RMSE': f"{rmse_nonzero:.4f}",
                    'Features': model.training_info['n_features']
                })
        
        # Print table
        print("\nModel Comparison:")
        print(tabulate(comparison_data, headers='keys', tablefmt='grid'))