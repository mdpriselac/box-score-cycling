#!/usr/bin/env python3
"""
Example usage of the rider embeddings correlation calculator.
"""
import sys
from pathlib import Path

# Add the project root to Python path  
sys.path.append(str(Path(__file__).parent.parent))

from rider_embeddings.performance_feature_link.correlation_method import CorrelationCalculator


def example_single_calculation():
    """Example of calculating correlations for a single rider result."""
    print("=== Single Rider Result Calculation ===")
    
    # Initialize calculator
    db_path = "database/database/cycling_races.db"
    calc = CorrelationCalculator(db_path, min_races=5)
    
    # Calculate for a specific rider result
    rider_result_id = 1
    lookback_date = "2024-03-10"
    feature_tables = ['race_features_100', 'race_features_80', 'race_features_60']
    
    result = calc.calculate_feature_relationships(
        rider_result_id, 
        lookback_date, 
        feature_tables
    )
    
    print(f"Rider Result ID: {result['rider_result_id']}")
    print(f"Races used: {result['metadata']['n_races']}")
    print(f"Method: {result['metadata']['method']}")
    print(f"Warnings: {result['metadata']['warnings']}")
    print()
    
    # Show correlations for each feature table
    for table_name, correlations in result['feature_correlations'].items():
        print(f"Correlations for {table_name}:")
        
        # Show top positive and negative correlations
        valid_corrs = {k: v for k, v in correlations.items() if v is not None}
        if valid_corrs:
            sorted_corrs = sorted(valid_corrs.items(), key=lambda x: abs(x[1]), reverse=True)
            
            print("  Top 5 strongest correlations:")
            for feature, corr in sorted_corrs[:5]:
                print(f"    {feature}: {corr:.4f}")
            print()
        else:
            print("  No valid correlations found")
            print()


def example_batch_calculation():
    """Example of calculating correlations for multiple rider results."""
    print("=== Batch Calculation ===")
    
    db_path = "database/database/cycling_races.db"
    calc = CorrelationCalculator(db_path, min_races=3)
    
    # Calculate for multiple rider results
    rider_result_ids = [1, 2, 3, 4, 5]
    feature_tables = ['race_features_100', 'race_features_80']
    
    results = calc.batch_calculate(rider_result_ids, feature_tables)
    
    print(f"Processed {len(results)} rider results")
    print()
    
    for result in results:
        print(f"Rider Result {result['rider_result_id']}: "
              f"{result['metadata']['n_races']} races, "
              f"{len(result['feature_correlations'])} feature tables")
        
        if result['metadata']['warnings']:
            print(f"  Warnings: {result['metadata']['warnings']}")
        print()


def analyze_feature_consistency():
    """Analyze how consistent correlations are across different percentile cutoffs."""
    print("=== Feature Consistency Analysis ===")
    
    db_path = "database/database/cycling_races.db"
    calc = CorrelationCalculator(db_path, min_races=10)
    
    # Get correlation for all available feature tables
    all_feature_tables = ['race_features_30', 'race_features_40', 'race_features_50', 
                         'race_features_60', 'race_features_70', 'race_features_80', 
                         'race_features_90', 'race_features_100']
    
    rider_result_id = 1
    lookback_date = "2024-03-10"
    
    result = calc.calculate_feature_relationships(
        rider_result_id, 
        lookback_date, 
        all_feature_tables
    )
    
    if result['feature_correlations']:
        # Pick a feature to analyze across percentiles
        sample_feature = 'gini_coefficient'
        
        print(f"Correlation of '{sample_feature}' across different percentile cutoffs:")
        for table_name in all_feature_tables:
            if table_name in result['feature_correlations']:
                corr = result['feature_correlations'][table_name].get(sample_feature)
                percentile = table_name.split('_')[-1]
                print(f"  {percentile}% cutoff: {corr:.4f if corr is not None else 'N/A'}")
        print()
        
        # Show which features are most consistent across percentiles
        print("Features with most consistent correlations across percentiles:")
        feature_consistency = {}
        
        # Get all feature names
        all_features = set()
        for correlations in result['feature_correlations'].values():
            all_features.update(correlations.keys())
        
        # Calculate consistency for each feature
        for feature in all_features:
            correlations = []
            for table_name in all_feature_tables:
                if table_name in result['feature_correlations']:
                    corr = result['feature_correlations'][table_name].get(feature)
                    if corr is not None:
                        correlations.append(corr)
            
            if len(correlations) >= 3:  # Need at least 3 values to assess consistency
                import numpy as np
                consistency = 1 - np.std(correlations) / (np.mean(np.abs(correlations)) + 1e-6)
                feature_consistency[feature] = consistency
        
        # Show top 10 most consistent features
        if feature_consistency:
            sorted_features = sorted(feature_consistency.items(), key=lambda x: x[1], reverse=True)
            print("  Top 10 most consistent features across percentiles:")
            for feature, consistency in sorted_features[:10]:
                print(f"    {feature}: {consistency:.4f}")


if __name__ == "__main__":
    example_single_calculation()
    example_batch_calculation()
    analyze_feature_consistency()