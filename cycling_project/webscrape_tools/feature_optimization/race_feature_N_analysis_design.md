# Race Feature Behavior Analysis Across N Spectrum

## Overview
Analyze how each of the 37 race features behaves as we move from N=30 (top 30% of riders) to N=100 (all riders).

## Key Analysis Dimensions

### 1. Statistical Behavior Metrics

#### 1.1 Variability Measures
```python
class FeatureVariabilityAnalyzer:
    def analyze_feature_across_N(self, feature_name: str):
        """Analyze how a feature's statistical properties change across N"""
        
        metrics = {}
        for n in [30, 40, 50, 60, 70, 80, 90, 100]:
            values = self.get_feature_values(feature_name, n)
            
            metrics[n] = {
                'mean': np.mean(values),
                'std': np.std(values),
                'cv': np.std(values) / np.mean(values) if np.mean(values) != 0 else 0,  # Coefficient of variation
                'range': np.max(values) - np.min(values),
                'iqr': np.percentile(values, 75) - np.percentile(values, 25),
                'skewness': stats.skew(values),
                'kurtosis': stats.kurtosis(values),
                'gini': self.calculate_gini(values),  # Inequality measure
                'entropy': stats.entropy(np.histogram(values, bins=20)[0] + 1e-10)
            }
        
        # Calculate trends across N
        trends = {
            'mean_trend': self.calculate_trend([metrics[n]['mean'] for n in sorted(metrics.keys())]),
            'cv_trend': self.calculate_trend([metrics[n]['cv'] for n in sorted(metrics.keys())]),
            'entropy_trend': self.calculate_trend([metrics[n]['entropy'] for n in sorted(metrics.keys())])
        }
        
        return metrics, trends
```

#### 1.2 Monotonicity and Linearity
```python
def analyze_monotonicity(feature_values_by_n):
    """Check if feature changes monotonically with N"""
    n_values = sorted(feature_values_by_n.keys())
    means = [np.mean(feature_values_by_n[n]) for n in n_values]
    
    # Spearman correlation for monotonicity
    spearman_corr, _ = stats.spearmanr(n_values, means)
    
    # Check strict monotonicity
    increasing = all(means[i] <= means[i+1] for i in range(len(means)-1))
    decreasing = all(means[i] >= means[i+1] for i in range(len(means)-1))
    
    # Linearity (R-squared of linear fit)
    slope, intercept, r_value, _, _ = stats.linregress(n_values, means)
    
    return {
        'spearman_correlation': spearman_corr,
        'is_monotonic': increasing or decreasing,
        'is_increasing': increasing,
        'is_decreasing': decreasing,
        'linearity_r2': r_value**2,
        'slope': slope,
        'relative_slope': slope / np.mean(means) if np.mean(means) != 0 else 0
    }
```

### 2. Distinctiveness and Discriminative Power

#### 2.1 Feature Distinctiveness Score
```python
class DistinctivenessAnalyzer:
    def calculate_distinctiveness(self, feature_name: str, n: int):
        """
        How well does this feature distinguish between different races?
        Higher score = more distinctive
        """
        values = self.get_feature_values(feature_name, n)
        
        # Method 1: Normalized entropy (0-1, higher = more distinctive)
        hist, _ = np.histogram(values, bins=50)
        entropy = stats.entropy(hist + 1e-10)
        max_entropy = np.log(50)  # Maximum possible entropy
        normalized_entropy = entropy / max_entropy
        
        # Method 2: Silhouette coefficient if we cluster races
        if len(np.unique(values)) > 1:
            # Cluster races based on this feature
            kmeans = KMeans(n_clusters=min(5, len(np.unique(values))))
            clusters = kmeans.fit_predict(values.reshape(-1, 1))
            silhouette = silhouette_score(values.reshape(-1, 1), clusters)
        else:
            silhouette = 0
        
        # Method 3: Inter-quartile range relative to range
        q1, q3 = np.percentile(values, [25, 75])
        iqr = q3 - q1
        range_val = np.max(values) - np.min(values)
        iqr_ratio = iqr / range_val if range_val > 0 else 0
        
        return {
            'entropy_score': normalized_entropy,
            'clustering_score': silhouette,
            'spread_score': iqr_ratio,
            'overall_distinctiveness': np.mean([normalized_entropy, silhouette, iqr_ratio])
        }
    
    def analyze_distinctiveness_trajectory(self, feature_name: str):
        """How does distinctiveness change across N?"""
        trajectory = {}
        for n in [30, 40, 50, 60, 70, 80, 90, 100]:
            trajectory[n] = self.calculate_distinctiveness(feature_name, n)
        
        # Analyze the trajectory
        scores = [trajectory[n]['overall_distinctiveness'] for n in sorted(trajectory.keys())]
        
        return {
            'trajectory': trajectory,
            'peak_n': max(trajectory.keys(), key=lambda n: trajectory[n]['overall_distinctiveness']),
            'distinctiveness_range': max(scores) - min(scores),
            'distinctiveness_stability': 1 - np.std(scores) / np.mean(scores) if np.mean(scores) > 0 else 0
        }
```

#### 2.2 Information Gain Analysis
```python
def calculate_information_gain_across_n(feature_name: str, target_variable: str):
    """
    How much information does this feature provide about the target at each N?
    """
    ig_scores = {}
    
    for n in [30, 40, 50, 60, 70, 80, 90, 100]:
        X = get_feature_values(feature_name, n)
        y = get_target_values(target_variable, n)
        
        # Discretize continuous feature for MI calculation
        X_discrete = pd.qcut(X, q=10, duplicates='drop', labels=False)
        
        # Calculate mutual information
        mi_score = mutual_info_classif(X_discrete.reshape(-1, 1), y)[0]
        
        ig_scores[n] = mi_score
    
    return ig_scores
```

### 3. Feature Behavior Patterns

#### 3.1 Pattern Classification
```python
class FeaturePatternClassifier:
    def classify_feature_behavior(self, feature_name: str):
        """Classify feature into behavior patterns"""
        
        # Get feature statistics across N
        stats_by_n = self.get_feature_stats_across_n(feature_name)
        
        # Pattern 1: Stable features (low variation across N)
        cv_values = [stats_by_n[n]['cv'] for n in sorted(stats_by_n.keys())]
        is_stable = np.std(cv_values) < 0.1
        
        # Pattern 2: Dilution features (variance increases with N)
        variance_trend = self.calculate_trend([stats_by_n[n]['variance'] for n in sorted(stats_by_n.keys())])
        shows_dilution = variance_trend['slope'] > 0 and variance_trend['r2'] > 0.7
        
        # Pattern 3: Concentration features (become more concentrated as N increases)
        entropy_trend = self.calculate_trend([stats_by_n[n]['entropy'] for n in sorted(stats_by_n.keys())])
        shows_concentration = entropy_trend['slope'] < 0 and entropy_trend['r2'] > 0.7
        
        # Pattern 4: Threshold features (sudden change at specific N)
        threshold_n = self.detect_threshold(stats_by_n)
        
        # Pattern 5: Bimodal features (distribution changes from unimodal to bimodal)
        bimodality_by_n = {n: self.test_bimodality(feature_name, n) for n in [30, 50, 70, 90]}
        
        return {
            'is_stable': is_stable,
            'shows_dilution': shows_dilution,
            'shows_concentration': shows_concentration,
            'has_threshold': threshold_n is not None,
            'threshold_n': threshold_n,
            'bimodality_pattern': bimodality_by_n,
            'primary_pattern': self.determine_primary_pattern(is_stable, shows_dilution, shows_concentration, threshold_n)
        }
```

### 4. Feature Grouping Analysis

#### 4.1 Correlation Stability Groups
```python
class FeatureGroupingAnalyzer:
    def find_stable_feature_groups(self):
        """Find groups of features that maintain similar relationships across N"""
        
        # Calculate correlation matrices for each N
        corr_matrices = {}
        for n in [30, 40, 50, 60, 70, 80, 90, 100]:
            features_df = self.get_all_features(n)
            corr_matrices[n] = features_df.corr()
        
        # Find stable correlation pairs
        stable_pairs = []
        for i, feat1 in enumerate(RACE_FEATURES):
            for j, feat2 in enumerate(RACE_FEATURES):
                if i >= j:
                    continue
                
                correlations = [corr_matrices[n].loc[feat1, feat2] for n in corr_matrices.keys()]
                
                # Check stability
                if np.std(correlations) < 0.1 and abs(np.mean(correlations)) > 0.5:
                    stable_pairs.append({
                        'feature1': feat1,
                        'feature2': feat2,
                        'mean_correlation': np.mean(correlations),
                        'correlation_std': np.std(correlations)
                    })
        
        # Cluster features based on stable relationships
        return self.cluster_by_stable_relationships(stable_pairs)
```

#### 4.2 Behavioral Similarity Groups
```python
def group_features_by_behavior(self):
    """Group features by similar behavior patterns across N"""
    
    behavior_vectors = {}
    
    for feature in RACE_FEATURES:
        # Create behavior vector for each feature
        vector = []
        
        # Add monotonicity metrics
        mono = analyze_monotonicity(feature)
        vector.extend([mono['spearman_correlation'], mono['linearity_r2']])
        
        # Add variability trajectory
        var_trajectory = [get_cv(feature, n) for n in [30, 50, 70, 90]]
        vector.extend(var_trajectory)
        
        # Add distinctiveness trajectory
        dist_trajectory = [get_distinctiveness(feature, n) for n in [30, 50, 70, 90]]
        vector.extend(dist_trajectory)
        
        behavior_vectors[feature] = np.array(vector)
    
    # Cluster features by behavior
    X = np.array(list(behavior_vectors.values()))
    
    # Determine optimal number of clusters
    silhouette_scores = []
    for k in range(2, 10):
        kmeans = KMeans(n_clusters=k, random_state=42)
        clusters = kmeans.fit_predict(X)
        score = silhouette_score(X, clusters)
        silhouette_scores.append(score)
    
    optimal_k = np.argmax(silhouette_scores) + 2
    
    # Final clustering
    kmeans = KMeans(n_clusters=optimal_k, random_state=42)
    clusters = kmeans.fit_predict(X)
    
    # Create groups
    groups = {}
    for i, feature in enumerate(behavior_vectors.keys()):
        cluster = clusters[i]
        if cluster not in groups:
            groups[cluster] = []
        groups[cluster].append(feature)
    
    return groups, kmeans.cluster_centers_
```

### 5. Quality Metrics Across N

#### 5.1 Signal-to-Noise Ratio
```python
def calculate_snr_across_n(feature_name: str):
    """Calculate signal-to-noise ratio at each N level"""
    snr_by_n = {}
    
    for n in [30, 40, 50, 60, 70, 80, 90, 100]:
        values = get_feature_values(feature_name, n)
        
        # Method 1: Between-race variance vs within-race variance
        # (assuming we can group by race type or similar)
        between_var = calculate_between_group_variance(values)
        within_var = calculate_within_group_variance(values)
        
        snr1 = between_var / within_var if within_var > 0 else 0
        
        # Method 2: Peak-to-peak range vs standard deviation
        snr2 = (np.max(values) - np.min(values)) / (2 * np.std(values)) if np.std(values) > 0 else 0
        
        snr_by_n[n] = {
            'variance_based_snr': snr1,
            'range_based_snr': snr2,
            'combined_snr': np.mean([snr1, snr2])
        }
    
    return snr_by_n
```

#### 5.2 Feature Reliability Score
```python
def calculate_reliability_score(feature_name: str):
    """
    How reliable/consistent is this feature across different N values?
    """
    # Get feature values at each N
    values_by_n = {n: get_feature_values(feature_name, n) for n in [30, 40, 50, 60, 70, 80, 90, 100]}
    
    # Calculate various reliability metrics
    
    # 1. Rank correlation between consecutive N levels
    rank_correlations = []
    n_values = sorted(values_by_n.keys())
    for i in range(len(n_values) - 1):
        n1, n2 = n_values[i], n_values[i+1]
        # Match competitions between N levels
        matched_values = match_competitions(values_by_n[n1], values_by_n[n2])
        if len(matched_values) > 10:
            corr, _ = stats.spearmanr(matched_values[n1], matched_values[n2])
            rank_correlations.append(corr)
    
    # 2. Coefficient of variation stability
    cv_values = [calculate_cv(values_by_n[n]) for n in n_values]
    cv_stability = 1 - (np.std(cv_values) / np.mean(cv_values)) if np.mean(cv_values) > 0 else 0
    
    # 3. Distribution shape stability (KS test between distributions)
    ks_statistics = []
    for i in range(len(n_values) - 1):
        n1, n2 = n_values[i], n_values[i+1]
        ks_stat, _ = stats.ks_2samp(values_by_n[n1], values_by_n[n2])
        ks_statistics.append(ks_stat)
    
    distribution_stability = 1 - np.mean(ks_statistics)
    
    return {
        'rank_preservation': np.mean(rank_correlations) if rank_correlations else 0,
        'cv_stability': cv_stability,
        'distribution_stability': distribution_stability,
        'overall_reliability': np.mean([
            np.mean(rank_correlations) if rank_correlations else 0,
            cv_stability,
            distribution_stability
        ])
    }
```

## Comprehensive Analysis Pipeline

```python
class RaceFeatureNAnalyzer:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.n_levels = [30, 40, 50, 60, 70, 80, 90, 100]
        
    def run_comprehensive_analysis(self):
        """Run all analyses for all features"""
        
        results = {}
        
        for feature in RACE_FEATURES:
            print(f"Analyzing {feature}...")
            
            results[feature] = {
                # Statistical behavior
                'variability_analysis': self.analyze_feature_variability(feature),
                'monotonicity': self.analyze_monotonicity(feature),
                
                # Distinctiveness
                'distinctiveness': self.analyze_distinctiveness_trajectory(feature),
                
                # Patterns
                'behavior_pattern': self.classify_feature_behavior(feature),
                
                # Quality metrics
                'snr_analysis': self.calculate_snr_across_n(feature),
                'reliability': self.calculate_reliability_score(feature),
                
                # Summary scores
                'stability_score': self.calculate_overall_stability(feature),
                'information_score': self.calculate_overall_information_value(feature),
                'quality_score': self.calculate_overall_quality(feature)
            }
        
        # Group-level analyses
        results['feature_groups'] = {
            'correlation_groups': self.find_stable_feature_groups(),
            'behavior_groups': self.group_features_by_behavior(),
            'quality_tiers': self.create_quality_based_tiers(results)
        }
        
        # N-level recommendations
        results['n_recommendations'] = self.recommend_n_levels(results)
        
        return results
    
    def visualize_results(self, results):
        """Create visualizations of the analysis"""
        # 1. Heatmap of feature behavior across N
        # 2. Clustering dendogram of feature groups
        # 3. Feature quality scatter plot
        # 4. Trajectory plots for each behavior pattern
        pass
```

## Key Insights to Extract

1. **Stable Core Features**: Features that maintain consistent relationships and information content across N
2. **N-Sensitive Features**: Features that are only informative at specific N levels
3. **Redundancy Patterns**: Which features become redundant at different N levels
4. **Optimal N Combinations**: Based on information gain and redundancy minimization
5. **Feature Quality Tiers**: Ranking features by reliability, distinctiveness, and information content

## Output Format

```python
{
    'feature_analysis': {
        'abandon_ratio': {
            'behavior_type': 'dilution',
            'optimal_n_range': [30, 50],
            'reliability_score': 0.87,
            'distinctiveness_peak': 40,
            'quality_tier': 1
        },
        # ... for all 37 features
    },
    'feature_groups': {
        'stable_core': ['total_finishers', 'winning_time', ...],
        'early_discriminators': ['abandon_ratio', 'variance_normalized', ...],
        'late_stage_features': ['clumpiness_score', 'selection_metric', ...]
    },
    'n_recommendations': {
        'minimal_set': [50, 90],  # Captures 85% of information
        'balanced_set': [30, 50, 70, 90],  # 95% of information
        'comprehensive_set': [30, 40, 50, 60, 70, 80, 90, 100]  # Full information
    }
}