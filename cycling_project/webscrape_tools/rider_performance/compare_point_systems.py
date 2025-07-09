"""
Compare the performance of models trained on actual vs proportional UCI points.

This module runs backtests using both point systems and generates a comprehensive
comparison report highlighting the differences in zero inflation and ranking accuracy.
"""

import pandas as pd
from typing import Dict, List
from temporal_backtest import TemporalBacktester
import os


def compare_point_systems(db_path: str, 
                         test_year: int,
                         min_results: int = 10,
                         output_dir: str = "rider_performance/comparisons",
                         use_optimized_generator: bool = True) -> Dict:
    """
    Run backtest with both point systems and compare results.
    
    Args:
        db_path: Path to database
        test_year: Year to test on
        min_results: Minimum results per rider
        output_dir: Directory for comparison reports
        use_optimized_generator: Whether to use optimized generators
        
    Returns:
        Dictionary with comparison results
    """
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"{'='*80}")
    print(f"COMPARING POINT SYSTEMS FOR {test_year}")
    print(f"{'='*80}")
    
    backtester = TemporalBacktester(db_path)
    
    # Run with actual UCI points
    print("\n1. Running with ACTUAL UCI points...")
    actual_results = backtester.run_temporal_backtest(
        test_year=test_year,
        min_results=min_results,
        target_variable='uci_points_actual',
        save_models=True,
        verbose=True,
        use_optimized_generator=use_optimized_generator
    )
    
    # Run with proportional UCI points
    print("\n2. Running with PROPORTIONAL UCI points...")
    proportional_results = backtester.run_temporal_backtest(
        test_year=test_year,
        min_results=min_results,
        target_variable='uci_points_proportional',
        save_models=True,
        verbose=True,
        use_optimized_generator=use_optimized_generator
    )
    
    # Generate comparison report
    comparison = generate_comparison_report(
        actual_results, 
        proportional_results,
        test_year,
        output_dir
    )
    
    return comparison


def generate_comparison_report(actual_results: Dict, 
                              proportional_results: Dict,
                              test_year: int,
                              output_dir: str) -> Dict:
    """Generate detailed comparison report between the two point systems."""
    
    report_lines = []
    
    # Header
    report_lines.append(f"# Point System Comparison Report - {test_year}")
    report_lines.append(f"\nComparing **Actual UCI Points** vs **Proportional UCI Points**")
    report_lines.append(f"\n## Executive Summary")
    
    # Calculate improvement metrics
    comparison_data = {}
    
    for model_type in ['gc', 'stage_one_day']:
        if model_type in actual_results['metrics'] and model_type in proportional_results['metrics']:
            actual_metrics = actual_results['metrics'][model_type]
            prop_metrics = proportional_results['metrics'][model_type]
            
            # Calculate improvements
            zero_reduction = actual_metrics['zero_percentage'] - prop_metrics['zero_percentage']
            spearman_improvement = prop_metrics['spearman_overall'] - actual_metrics['spearman_overall']
            top10_improvement = prop_metrics['top_10_accuracy'] - actual_metrics['top_10_accuracy']
            
            comparison_data[model_type] = {
                'zero_reduction': zero_reduction,
                'spearman_improvement': spearman_improvement,
                'top10_improvement': top10_improvement,
                'actual_metrics': actual_metrics,
                'prop_metrics': prop_metrics
            }
            
            report_lines.append(f"\n### {model_type.upper()} Model")
            report_lines.append(f"- **Zero inflation reduced by:** {zero_reduction:.1f} percentage points")
            report_lines.append(f"- **Spearman correlation improved by:** {spearman_improvement:.4f}")
            report_lines.append(f"- **Top-10 accuracy improved by:** {top10_improvement:.4f}")
    
    # Detailed comparison tables
    report_lines.append("\n## Detailed Metrics Comparison")
    
    for model_type, data in comparison_data.items():
        report_lines.append(f"\n### {model_type.upper()} Model")
        
        # Zero inflation comparison
        report_lines.append("\n#### Zero Inflation")
        report_lines.append("\n| Point System | Zero % | Non-zero Samples |")
        report_lines.append("|--------------|--------|------------------|")
        report_lines.append(f"| Actual UCI | {data['actual_metrics']['zero_percentage']:.1f}% | {data['actual_metrics']['n_nonzeros']:,} |")
        report_lines.append(f"| Proportional | {data['prop_metrics']['zero_percentage']:.1f}% | {data['prop_metrics']['n_nonzeros']:,} |")
        report_lines.append(f"| **Improvement** | **{data['zero_reduction']:.1f}pp** | **+{data['prop_metrics']['n_nonzeros'] - data['actual_metrics']['n_nonzeros']:,}** |")
        
        # Ranking metrics comparison
        report_lines.append("\n#### Ranking Metrics")
        report_lines.append("\n| Metric | Actual UCI | Proportional | Improvement |")
        report_lines.append("|--------|------------|--------------|-------------|")
        
        ranking_metrics = [
            ('Spearman (Overall)', 'spearman_overall'),
            ('Spearman (Non-zero)', 'spearman_nonzero'),
            ('Within-race Spearman', 'within_race_spearman_mean'),
            ('Top-5 Accuracy', 'top_5_accuracy'),
            ('Top-10 Accuracy', 'top_10_accuracy'),
            ('Top-20 Accuracy', 'top_20_accuracy'),
            ('Within-race Top-3', 'within_race_top_3_mean'),
            ('Within-race Top-5', 'within_race_top_5_mean')
        ]
        
        for metric_name, metric_key in ranking_metrics:
            actual_val = data['actual_metrics'][metric_key]
            prop_val = data['prop_metrics'][metric_key]
            improvement = prop_val - actual_val
            
            report_lines.append(
                f"| {metric_name} | {actual_val:.4f} | {prop_val:.4f} | "
                f"{'✅' if improvement > 0 else '❌'} {improvement:+.4f} |"
            )
        
        # Classification metrics comparison
        report_lines.append("\n#### Classification Metrics (0 vs Non-0)")
        report_lines.append("\n| Metric | Actual UCI | Proportional | Change |")
        report_lines.append("|--------|------------|--------------|--------|")
        
        class_metrics = [
            ('AUC', 'auc_classification'),
            ('Precision', 'precision_nonzero'),
            ('Recall', 'recall_nonzero'),
            ('F1 Score', 'f1_nonzero')
        ]
        
        for metric_name, metric_key in class_metrics:
            actual_val = data['actual_metrics'][metric_key]
            prop_val = data['prop_metrics'][metric_key]
            change = prop_val - actual_val
            
            report_lines.append(
                f"| {metric_name} | {actual_val:.4f} | {prop_val:.4f} | {change:+.4f} |"
            )
        
        # Regression metrics comparison
        report_lines.append("\n#### Regression Metrics")
        report_lines.append("\n| Metric | Actual UCI | Proportional | Note |")
        report_lines.append("|--------|------------|--------------|------|")
        
        report_lines.append(
            f"| RMSE (Overall) | {data['actual_metrics']['rmse_overall']:.2f} | "
            f"{data['prop_metrics']['rmse_overall']:.2f} | Not comparable* |"
        )
        report_lines.append(
            f"| RMSE (Non-zero) | {data['actual_metrics']['rmse_nonzero']:.2f} | "
            f"{data['prop_metrics']['rmse_nonzero']:.2f} | Not comparable* |"
        )
        report_lines.append(
            f"| R² (Non-zero) | {data['actual_metrics']['r2_nonzero']:.4f} | "
            f"{data['prop_metrics']['r2_nonzero']:.4f} | Within-system only |"
        )
    
    # Conclusions
    report_lines.append("\n## Key Findings")
    report_lines.append("\n1. **Zero Inflation**: The proportional point system significantly reduces zero inflation:")
    
    for model_type, data in comparison_data.items():
        report_lines.append(f"   - {model_type}: {data['actual_metrics']['zero_percentage']:.1f}% → {data['prop_metrics']['zero_percentage']:.1f}% zeros")
    
    report_lines.append("\n2. **Ranking Accuracy**: The proportional system generally improves ranking metrics")
    report_lines.append("\n3. **Classification**: Both systems can identify point-scorers reasonably well")
    report_lines.append("\n4. **Important Note**: RMSE values are not directly comparable between systems due to different point scales")
    
    # Recommendations
    report_lines.append("\n## Recommendations")
    
    # Check if proportional is better
    gc_better = comparison_data.get('gc', {}).get('spearman_improvement', 0) > 0
    stage_better = comparison_data.get('stage_one_day', {}).get('spearman_improvement', 0) > 0
    
    if gc_better and stage_better:
        report_lines.append("\n✅ **Proportional points show superior performance** for both GC and Stage/One-day races")
        report_lines.append("- Better ranking accuracy (Spearman correlation)")
        report_lines.append("- Reduced zero inflation makes models more stable")
        report_lines.append("- More training signal from mid-pack finishers")
    else:
        report_lines.append("\n⚠️ **Mixed results** - consider model-specific choices")
    
    report_lines.append("\n### Next Steps")
    report_lines.append("1. Consider extending proportional points to top 60 for stages (currently top 20)")
    report_lines.append("2. Test on multiple years to confirm consistency")
    report_lines.append("3. Analyze specific race types where improvements are largest")
    
    # Write report
    report_path = os.path.join(output_dir, f"point_system_comparison_{test_year}.md")
    with open(report_path, 'w') as f:
        f.write('\n'.join(report_lines))
    
    print(f"\nComparison report saved to {report_path}")
    
    return comparison_data


if __name__ == "__main__":
    # Example usage
    db_path = "database/database/cycling_races.db"
    
    # Compare for 2023
    comparison = compare_point_systems(
        db_path=db_path,
        test_year=2023,
        min_results=15,
        use_optimized_generator=True
    )
    
    # Print quick summary
    print("\n" + "="*80)
    print("COMPARISON SUMMARY")
    print("="*80)
    
    for model_type, data in comparison.items():
        print(f"\n{model_type.upper()}:")
        print(f"  Zero reduction: {data['zero_reduction']:.1f} percentage points")
        print(f"  Spearman improvement: {data['spearman_improvement']:+.4f}")
        print(f"  Top-10 improvement: {data['top10_improvement']:+.4f}")