import numpy as np
import pandas as pd
from typing import Dict, List, Any, Tuple, Set
from scipy.stats import pearsonr, spearmanr
from sklearn.feature_selection import mutual_info_regression
from sklearn.preprocessing import StandardScaler
from collections import defaultdict
import warnings


class FeatureRedundancyAnalyzer:
    """
    Analyze feature redundancy in rider correlation data.
    
    Identifies highly correlated features and provides recommendations
    for feature selection to minimize redundancy while maximizing
    information content.
    """
    
    def __init__(self, correlation_threshold: float = 0.8):
        """
        Initialize the feature redundancy analyzer.
        
        Args:
            correlation_threshold: Threshold above which features are considered redundant
        """
        self.correlation_threshold = correlation_threshold
        
    def calculate_feature_correlations(
        self, 
        correlation_results: List[Dict[str, Any]], 
        percentile: str,
        method: str = 'spearman'
    ) -> Dict[str, Any]:
        """
        Calculate correlations between features based on rider correlation patterns.
        
        Args:
            correlation_results: List of correlation results
            percentile: Percentile to analyze
            method: Correlation method ('pearson', 'spearman')
            
        Returns:
            Dictionary with feature correlation analysis
        """
        # Prepare correlation matrix
        correlation_matrix, rider_ids, feature_names = self._prepare_feature_matrix(
            correlation_results, percentile
        )
        
        if correlation_matrix.shape[1] < 2:
            raise ValueError("Need at least 2 features for redundancy analysis")
        
        # Calculate feature-to-feature correlations
        n_features = correlation_matrix.shape[1]
        feature_corr_matrix = np.zeros((n_features, n_features))
        p_value_matrix = np.zeros((n_features, n_features))
        
        for i in range(n_features):
            for j in range(n_features):
                if i == j:
                    feature_corr_matrix[i, j] = 1.0
                    p_value_matrix[i, j] = 0.0
                elif i < j:  # Calculate only upper triangle
                    if method == 'pearson':
                        corr, p_val = pearsonr(correlation_matrix[:, i], correlation_matrix[:, j])
                    else:  # spearman
                        corr, p_val = spearmanr(correlation_matrix[:, i], correlation_matrix[:, j])
                    
                    feature_corr_matrix[i, j] = corr
                    feature_corr_matrix[j, i] = corr
                    p_value_matrix[i, j] = p_val
                    p_value_matrix[j, i] = p_val
        
        return {
            'feature_names': feature_names,
            'correlation_matrix': feature_corr_matrix,
            'p_value_matrix': p_value_matrix,
            'method': method,
            'data_shape': correlation_matrix.shape
        }
    
    def identify_redundant_features(
        self, 
        feature_correlation_data: Dict[str, Any],
        significance_level: float = 0.05
    ) -> Dict[str, Any]:
        """
        Identify redundant feature pairs and groups.
        
        Args:
            feature_correlation_data: Output from calculate_feature_correlations
            significance_level: P-value threshold for significance
            
        Returns:
            Dictionary with redundancy analysis
        """
        feature_names = feature_correlation_data['feature_names']
        corr_matrix = feature_correlation_data['correlation_matrix']
        p_matrix = feature_correlation_data['p_value_matrix']
        
        n_features = len(feature_names)
        
        # Find redundant pairs
        redundant_pairs = []
        redundant_groups = []
        
        for i in range(n_features):
            for j in range(i + 1, n_features):
                corr = abs(corr_matrix[i, j])
                p_val = p_matrix[i, j]
                
                if corr >= self.correlation_threshold and p_val <= significance_level:
                    redundant_pairs.append({
                        'feature1': feature_names[i],
                        'feature2': feature_names[j],
                        'correlation': corr_matrix[i, j],
                        'abs_correlation': corr,
                        'p_value': p_val
                    })
        
        # Group redundant features using connected components
        redundant_groups = self._find_redundant_groups(redundant_pairs, feature_names)
        
        # Calculate redundancy statistics
        redundancy_stats = self._calculate_redundancy_stats(
            corr_matrix, feature_names, self.correlation_threshold
        )
        
        return {
            'redundant_pairs': redundant_pairs,
            'redundant_groups': redundant_groups,
            'redundancy_stats': redundancy_stats,
            'threshold_used': self.correlation_threshold,
            'significance_level': significance_level
        }
    
    def _find_redundant_groups(
        self, 
        redundant_pairs: List[Dict[str, Any]], 
        feature_names: List[str]
    ) -> List[Dict[str, Any]]:
        """Find connected components of redundant features."""
        # Build adjacency list
        adjacency = defaultdict(set)
        
        for pair in redundant_pairs:
            f1, f2 = pair['feature1'], pair['feature2']
            adjacency[f1].add(f2)
            adjacency[f2].add(f1)
        
        # Find connected components using DFS
        visited = set()
        groups = []
        
        def dfs(feature, current_group):
            visited.add(feature)
            current_group.append(feature)
            for neighbor in adjacency[feature]:
                if neighbor not in visited:
                    dfs(neighbor, current_group)
        
        for feature in feature_names:
            if feature in adjacency and feature not in visited:
                group = []
                dfs(feature, group)
                if len(group) > 1:  # Only groups with multiple features
                    # Calculate group statistics
                    avg_correlation = np.mean([
                        pair['abs_correlation'] 
                        for pair in redundant_pairs
                        if pair['feature1'] in group and pair['feature2'] in group
                    ])
                    
                    groups.append({
                        'features': group,
                        'size': len(group),
                        'avg_correlation': avg_correlation
                    })
        
        return sorted(groups, key=lambda x: x['size'], reverse=True)
    
    def _calculate_redundancy_stats(
        self, 
        corr_matrix: np.ndarray, 
        feature_names: List[str], 
        threshold: float
    ) -> Dict[str, Any]:
        """Calculate overall redundancy statistics."""
        n_features = len(feature_names)
        
        # Count redundant pairs
        redundant_count = 0
        total_pairs = 0
        high_corr_values = []
        
        for i in range(n_features):
            for j in range(i + 1, n_features):
                total_pairs += 1
                abs_corr = abs(corr_matrix[i, j])
                if abs_corr >= threshold:
                    redundant_count += 1
                if abs_corr >= 0.5:  # Moderate correlation threshold
                    high_corr_values.append(abs_corr)
        
        redundancy_rate = redundant_count / total_pairs if total_pairs > 0 else 0
        
        # Calculate distribution statistics
        upper_triangle = []
        for i in range(n_features):
            for j in range(i + 1, n_features):
                upper_triangle.append(abs(corr_matrix[i, j]))
        
        return {
            'total_features': n_features,
            'total_pairs': total_pairs,
            'redundant_pairs': redundant_count,
            'redundancy_rate': redundancy_rate,
            'mean_correlation': np.mean(upper_triangle),
            'max_correlation': np.max(upper_triangle),
            'correlation_std': np.std(upper_triangle),
            'high_correlation_count': len(high_corr_values)
        }
    
    def recommend_feature_selection(
        self, 
        redundancy_data: Dict[str, Any],
        feature_quality_scores: Dict[str, float] = None,
        max_features: int = None
    ) -> Dict[str, Any]:
        """
        Recommend which features to keep based on redundancy and quality.
        
        Args:
            redundancy_data: Output from identify_redundant_features
            feature_quality_scores: Dictionary mapping feature names to quality scores
            max_features: Maximum number of features to recommend
            
        Returns:
            Dictionary with feature selection recommendations
        """
        redundant_groups = redundancy_data['redundant_groups']
        all_features = set()
        
        # Collect all features mentioned in redundancy analysis
        for group in redundant_groups:
            all_features.update(group['features'])
        
        # Features to keep and remove
        features_to_remove = set()
        features_to_keep = set()
        group_selections = []
        
        # For each redundant group, select the best feature(s)
        for group in redundant_groups:
            group_features = group['features']
            
            if feature_quality_scores:
                # Select feature with highest quality score
                feature_scores = {
                    f: feature_quality_scores.get(f, 0) 
                    for f in group_features
                }
                best_feature = max(feature_scores.keys(), key=lambda f: feature_scores[f])
                
                group_selections.append({
                    'group': group_features,
                    'selected': best_feature,
                    'removed': [f for f in group_features if f != best_feature],
                    'selection_reason': f'Highest quality score: {feature_scores[best_feature]:.4f}'
                })
                
                features_to_keep.add(best_feature)
                features_to_remove.update(f for f in group_features if f != best_feature)
            else:
                # If no quality scores, keep first feature alphabetically
                sorted_features = sorted(group_features)
                best_feature = sorted_features[0]
                
                group_selections.append({
                    'group': group_features,
                    'selected': best_feature,
                    'removed': sorted_features[1:],
                    'selection_reason': 'Alphabetically first (no quality scores provided)'
                })
                
                features_to_keep.add(best_feature)
                features_to_remove.update(sorted_features[1:])
        
        # Calculate reduction statistics
        total_redundant_features = len(all_features)
        features_removed = len(features_to_remove)
        reduction_rate = features_removed / total_redundant_features if total_redundant_features > 0 else 0
        
        # If max_features is specified, further reduce features
        final_selection = None
        if max_features and feature_quality_scores:
            # Get all features not in redundant groups plus selected features
            all_available = set(feature_quality_scores.keys())
            non_redundant = all_available - all_features
            candidate_features = non_redundant.union(features_to_keep)
            
            # Sort by quality score and take top features
            if len(candidate_features) > max_features:
                sorted_features = sorted(
                    candidate_features, 
                    key=lambda f: feature_quality_scores.get(f, 0), 
                    reverse=True
                )
                final_selection = sorted_features[:max_features]
            else:
                final_selection = list(candidate_features)
        
        return {
            'group_selections': group_selections,
            'features_to_keep': list(features_to_keep),
            'features_to_remove': list(features_to_remove),
            'reduction_stats': {
                'total_redundant_features': total_redundant_features,
                'features_removed': features_removed,
                'reduction_rate': reduction_rate
            },
            'final_selection': final_selection,
            'max_features_applied': max_features is not None
        }
    
    def _prepare_feature_matrix(
        self, 
        correlation_results: List[Dict[str, Any]], 
        percentile: str,
        min_features: int = 5
    ) -> Tuple[np.ndarray, List[int], List[str]]:
        """Prepare correlation matrix for feature analysis."""
        # Filter valid results
        valid_results = [
            r for r in correlation_results 
            if (r['metadata']['n_races'] >= 5 and 
                not r['metadata']['warnings'] and
                percentile in r['feature_correlations'])
        ]
        
        if not valid_results:
            raise ValueError(f"No valid results found for percentile {percentile}")
        
        # Get all possible features
        all_features = set()
        for result in valid_results:
            all_features.update(result['feature_correlations'][percentile].keys())
        
        feature_names = sorted(list(all_features))
        
        # Build correlation matrix
        correlation_matrix = []
        rider_ids = []
        
        for result in valid_results:
            correlations = result['feature_correlations'][percentile]
            
            # Create correlation vector
            corr_vector = []
            valid_count = 0
            
            for feature in feature_names:
                corr = correlations.get(feature)
                if corr is not None and not np.isnan(corr):
                    corr_vector.append(corr)
                    valid_count += 1
                else:
                    corr_vector.append(0.0)  # Impute missing as 0
            
            # Only include riders with sufficient valid features
            if valid_count >= min_features:
                correlation_matrix.append(corr_vector)
                rider_ids.append(result['rider_result_id'])
        
        return np.array(correlation_matrix), rider_ids, feature_names
    
    def analyze_mutual_information(
        self, 
        correlation_results: List[Dict[str, Any]], 
        percentile: str,
        target_feature: str = None
    ) -> Dict[str, Any]:
        """
        Calculate mutual information between features.
        
        Args:
            correlation_results: List of correlation results
            percentile: Percentile to analyze
            target_feature: Feature to use as target (if None, use first feature)
            
        Returns:
            Dictionary with mutual information analysis
        """
        correlation_matrix, rider_ids, feature_names = self._prepare_feature_matrix(
            correlation_results, percentile
        )
        
        if target_feature is None:
            target_feature = feature_names[0]
        
        if target_feature not in feature_names:
            raise ValueError(f"Target feature {target_feature} not found")
        
        target_idx = feature_names.index(target_feature)
        target_values = correlation_matrix[:, target_idx]
        
        # Calculate mutual information with other features
        mi_scores = {}
        
        for i, feature in enumerate(feature_names):
            if feature != target_feature:
                feature_values = correlation_matrix[:, i].reshape(-1, 1)
                mi_score = mutual_info_regression(feature_values, target_values)[0]
                mi_scores[feature] = mi_score
        
        # Sort by mutual information score
        sorted_mi = sorted(mi_scores.items(), key=lambda x: x[1], reverse=True)
        
        return {
            'target_feature': target_feature,
            'mutual_information_scores': mi_scores,
            'sorted_scores': sorted_mi,
            'top_10_features': sorted_mi[:10]
        }