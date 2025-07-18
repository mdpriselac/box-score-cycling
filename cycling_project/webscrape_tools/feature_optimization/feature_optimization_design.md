# Feature Optimization Design for Cycling Performance Prediction

## Overview
This document outlines a systematic approach to feature optimization across race features, correlations, and interactions before model training.

## Current Feature Space
- **Base race features**: 37 features × 8 percentile levels (N=30,40,50,60,70,80,90,100) = 296 features
- **Correlations**: 296 features × 3 correlation types = 888 correlation features per rider
- **Interactions**: 3 interaction types × 888 = 2,664 interaction features per rider
- **Total potential features**: ~3,848 features per prediction

## Key Questions & Approach

### 1. Multi-Stage Feature Optimization Strategy

#### Stage 1: Race Feature Analysis (Foundation Level)
```python
# Analyze raw race features across all N levels
- Correlation matrix between features within each N
- Stability analysis across N levels
- Identify feature clusters/groups
- Detect multicollinearity
```

#### Stage 2: Correlation Strength Analysis
```python
# Analyze rider performance correlations
- Distribution of correlation values
- Identify consistently strong correlators
- Analyze correlation stability across rider populations
- Create correlation quality tiers
```

#### Stage 3: Cross-N Pattern Analysis
```python
# How features behave across different N values
- Feature importance stability across N
- Optimal N combinations (e.g., N=50,70,90 vs all N)
- Information gain from multiple N levels
```

#### Stage 4: Interaction Value Assessment
```python
# Evaluate interaction terms
- Which interactions add predictive value
- Redundancy between interaction types
- Sparse vs dense interaction patterns
```

## Proposed Feature Optimization Pipeline

### Phase 1: Feature Profiling and Quality Assessment

#### 1.1 Race Feature Redundancy Analysis
```python
class RaceFeatureAnalyzer:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.feature_names = RACE_FEATURES
        
    def analyze_within_percentile_redundancy(self, percentile: int):
        """Analyze feature redundancy within a single race_feature_N table"""
        # Load all race features for this percentile
        features_df = self.load_race_features(percentile)
        
        # Correlation matrix
        corr_matrix = features_df[self.feature_names].corr()
        
        # Find highly correlated pairs (>0.95)
        redundant_pairs = []
        for i in range(len(self.feature_names)):
            for j in range(i+1, len(self.feature_names)):
                if abs(corr_matrix.iloc[i, j]) > 0.95:
                    redundant_pairs.append({
                        'feature1': self.feature_names[i],
                        'feature2': self.feature_names[j],
                        'correlation': corr_matrix.iloc[i, j],
                        'percentile': percentile
                    })
        
        # Variance Inflation Factor (VIF) for multicollinearity
        vif_scores = self.calculate_vif(features_df[self.feature_names])
        
        return {
            'correlation_matrix': corr_matrix,
            'redundant_pairs': redundant_pairs,
            'vif_scores': vif_scores,
            'percentile': percentile
        }
    
    def analyze_cross_percentile_stability(self):
        """Analyze how feature relationships change across percentiles"""
        stability_scores = {}
        
        # Get correlation matrices for all percentiles
        corr_matrices = {}
        for n in [30, 40, 50, 60, 70, 80, 90, 100]:
            corr_matrices[n] = self.analyze_within_percentile_redundancy(n)['correlation_matrix']
        
        # Calculate stability scores for each feature pair
        for i, feat1 in enumerate(self.feature_names):
            for j, feat2 in enumerate(self.feature_names):
                if i >= j:
                    continue
                
                correlations = [corr_matrices[n].iloc[i, j] for n in corr_matrices]
                stability_scores[(feat1, feat2)] = {
                    'mean': np.mean(correlations),
                    'std': np.std(correlations),
                    'range': max(correlations) - min(correlations),
                    'stable': np.std(correlations) < 0.1  # Stable if std < 0.1
                }
        
        return stability_scores
```

#### 1.2 Correlation Quality Tiers
```python
class CorrelationQualityAnalyzer:
    def __init__(self, db_path: str):
        self.db_path = db_path
        
    def create_quality_tiers(self):
        """Create quality tiers based on correlation strength and data completeness"""
        query = """
        SELECT 
            rd.feature_name,
            rd.correlation_type,
            rd.percentile,
            AVG(ABS(rd.correlation_value)) as avg_abs_correlation,
            STDDEV(rd.correlation_value) as correlation_std,
            COUNT(DISTINCT rd.rider_id) as n_riders,
            AVG(dq.data_completeness) as avg_completeness
        FROM rider_correlations_denorm rd
        JOIN correlation_data_quality dq 
            ON rd.rider_result_id = dq.rider_result_id 
            AND rd.correlation_type = dq.correlation_type
        WHERE rd.correlation_value IS NOT NULL
        GROUP BY rd.feature_name, rd.correlation_type, rd.percentile
        """
        
        # Define quality tiers
        tiers = {
            'tier_1': [],  # High correlation, high quality
            'tier_2': [],  # Medium correlation, high quality
            'tier_3': [],  # High correlation, medium quality
            'tier_4': []   # Low correlation or low quality
        }
        
        results = pd.read_sql(query, self.db_conn)
        
        for _, row in results.iterrows():
            feature_combo = {
                'feature': row['feature_name'],
                'correlation_type': row['correlation_type'],
                'percentile': row['percentile'],
                'avg_correlation': row['avg_abs_correlation'],
                'n_riders': row['n_riders']
            }
            
            # Tier assignment logic
            if row['avg_abs_correlation'] > 0.3 and row['avg_completeness'] > 0.8:
                tiers['tier_1'].append(feature_combo)
            elif row['avg_abs_correlation'] > 0.2 and row['avg_completeness'] > 0.8:
                tiers['tier_2'].append(feature_combo)
            elif row['avg_abs_correlation'] > 0.3 and row['avg_completeness'] > 0.6:
                tiers['tier_3'].append(feature_combo)
            else:
                tiers['tier_4'].append(feature_combo)
                
        return tiers
```

### Phase 2: Feature Selection Strategies

#### Strategy A: Hierarchical Feature Selection
```python
class HierarchicalFeatureSelector:
    """
    Select features in order of importance:
    1. Core race features (non-redundant)
    2. High-quality correlations
    3. Valuable interactions
    """
    
    def select_features(self, target_features: int = 500):
        # Step 1: Select core race features
        core_features = self.select_core_race_features(max_features=50)
        
        # Step 2: Add correlation features based on quality tiers
        correlation_features = self.select_correlation_features(
            existing=core_features,
            max_additional=200
        )
        
        # Step 3: Add interaction features for top correlations
        interaction_features = self.select_interaction_features(
            base_features=core_features + correlation_features,
            max_additional=250
        )
        
        return {
            'core': core_features,
            'correlations': correlation_features,
            'interactions': interaction_features
        }
```

#### Strategy B: Information-Theoretic Selection
```python
class InformationTheoreticSelector:
    """
    Use mutual information and redundancy measures
    """
    
    def select_features_mrmr(self, X, y, n_features=500):
        """
        Minimum Redundancy Maximum Relevance (mRMR) algorithm
        """
        selected = []
        remaining = list(range(X.shape[1]))
        
        # Select first feature with highest MI with target
        mi_scores = mutual_info_regression(X, y)
        first_feature = np.argmax(mi_scores)
        selected.append(first_feature)
        remaining.remove(first_feature)
        
        # Iteratively add features
        while len(selected) < n_features and remaining:
            scores = []
            for feature in remaining:
                # Relevance: MI with target
                relevance = mi_scores[feature]
                
                # Redundancy: Average MI with selected features
                redundancy = np.mean([
                    mutual_info_score(X[:, feature], X[:, s])
                    for s in selected
                ])
                
                # mRMR score
                score = relevance - redundancy
                scores.append(score)
            
            # Select feature with highest score
            best_idx = np.argmax(scores)
            best_feature = remaining[best_idx]
            selected.append(best_feature)
            remaining.remove(best_feature)
            
        return selected
```

#### Strategy C: Multi-N Ensemble Selection
```python
class MultiNEnsembleSelector:
    """
    Optimize feature combinations across multiple N values
    """
    
    def find_optimal_n_combination(self):
        """
        Test different N combinations to find optimal set
        """
        n_combinations = [
            [50],                    # Single percentile
            [30, 70],                # Extremes
            [50, 70, 90],           # Common choice
            [30, 50, 70, 90],       # Quarters
            [40, 60, 80, 100],      # Alternative quarters
            [30, 40, 50, 60, 70, 80, 90, 100]  # All
        ]
        
        results = {}
        for combo in n_combinations:
            # Create feature set for this combination
            features = self.create_feature_set(combo)
            
            # Evaluate using cross-validation
            cv_score = self.evaluate_feature_set(features)
            
            results[str(combo)] = {
                'n_features': len(features),
                'cv_score': cv_score,
                'efficiency': cv_score / len(features)  # Score per feature
            }
            
        return results
```

### Phase 3: Feature Redundancy Pruning

#### 3.1 Correlation-Based Pruning
```python
def prune_correlated_features(feature_matrix, threshold=0.95):
    """Remove features that are highly correlated with others"""
    corr_matrix = np.corrcoef(feature_matrix.T)
    
    # Find features to remove
    to_remove = set()
    for i in range(len(corr_matrix)):
        for j in range(i+1, len(corr_matrix)):
            if abs(corr_matrix[i, j]) > threshold:
                # Remove the feature with lower variance
                if np.var(feature_matrix[:, i]) < np.var(feature_matrix[:, j]):
                    to_remove.add(i)
                else:
                    to_remove.add(j)
    
    return [i for i in range(feature_matrix.shape[1]) if i not in to_remove]
```

#### 3.2 Quality-Aware Pruning
```python
def prune_by_quality_tiers(features, quality_scores, redundancy_groups):
    """
    When features are redundant, keep the one from higher quality tier
    """
    selected = []
    processed = set()
    
    # Sort features by quality tier
    sorted_features = sorted(features, key=lambda x: quality_scores[x], reverse=True)
    
    for feature in sorted_features:
        if feature in processed:
            continue
            
        # Add feature
        selected.append(feature)
        processed.add(feature)
        
        # Mark redundant features as processed
        for redundant in redundancy_groups.get(feature, []):
            processed.add(redundant)
            
    return selected
```

## Recommended Approach: Hybrid Progressive Selection

### Step 1: Foundation Analysis
```python
# 1. Analyze race feature redundancy at each N
redundancy_analysis = analyze_all_percentile_redundancy()

# 2. Identify stable vs unstable feature relationships
stability_scores = analyze_cross_percentile_stability()

# 3. Create correlation quality tiers
quality_tiers = create_correlation_quality_tiers()
```

### Step 2: Core Feature Selection
```python
# Select 100-150 core features using:
# - Remove redundant race features (keep most informative)
# - Include features from multiple N levels based on stability
# - Prioritize Tier 1 correlation features
core_features = select_core_features(
    max_race_features_per_n=10,  # 80 total
    max_correlation_features=70,   # From Tier 1
    n_levels=[50, 70, 90]         # Most informative N levels
)
```

### Step 3: Progressive Expansion
```python
# Start with core features and progressively add:
feature_sets = {
    'minimal': core_features,  # 150 features
    'standard': core_features + tier2_correlations + key_interactions,  # 500 features
    'extended': all_tier1_2_features + selected_interactions,  # 1000 features
    'full': all_features  # 3848 features
}

# Test each set with cross-validation
for name, features in feature_sets.items():
    score = cross_validate_lgbm(features)
    print(f"{name}: {len(features)} features, CV score: {score}")
```

### Step 4: Feature Importance Feedback
```python
# After initial model training, use feature importance for refinement
lgbm_model = train_initial_model(feature_sets['standard'])
importances = lgbm_model.feature_importances_

# Refine selection based on actual usage
refined_features = select_by_importance(
    features=feature_sets['standard'],
    importances=importances,
    min_importance=0.001
)
```

## Storage Schema for Feature Selection

```sql
-- Feature selection metadata
CREATE TABLE feature_selection_runs (
    run_id TEXT PRIMARY KEY,
    run_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    strategy TEXT NOT NULL,  -- 'hierarchical', 'information_theoretic', 'multi_n'
    parameters TEXT,         -- JSON parameters
    n_features_selected INTEGER,
    cv_score REAL,
    notes TEXT
);

-- Selected features per run
CREATE TABLE selected_features (
    run_id TEXT,
    feature_type TEXT,      -- 'race_feature', 'correlation', 'interaction'
    feature_name TEXT,
    percentile INTEGER,
    correlation_type TEXT,
    importance_score REAL,
    quality_tier INTEGER,
    
    FOREIGN KEY (run_id) REFERENCES feature_selection_runs(run_id)
);

-- Feature redundancy groups
CREATE TABLE feature_redundancy_groups (
    group_id INTEGER,
    feature_name TEXT,
    percentile INTEGER,
    correlation_value REAL,
    is_representative BOOLEAN,  -- The feature kept from this group
    
    PRIMARY KEY (group_id, feature_name, percentile)
);
```

## Implementation Priority

1. **Start with Multi-N Analysis**: Understand which percentile combinations are most informative
2. **Implement Quality Tiers**: Create robust correlation quality metrics
3. **Build Progressive Selection**: Start small and expand based on performance
4. **Use Model Feedback**: Let initial training guide final selection

## Recommendation: Progressive Hybrid Approach

Rather than choosing between pre-optimization or letting the model figure it out, use a progressive approach:

1. **Phase 1**: Remove obvious redundancies (correlation > 0.95)
2. **Phase 2**: Create quality-tiered feature sets (minimal, standard, extended)
3. **Phase 3**: Train models on each set to understand diminishing returns
4. **Phase 4**: Use model feature importances to create final optimized set

This balances computational efficiency with information preservation and provides interpretable results.