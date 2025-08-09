# Cluster Embeddings System - Complete Guide

## Overview

The cluster embedding system creates standardized representations of all clusters across all percentiles and K-values, enabling cross-percentile cluster comparison and future master-cluster assignment. This system generates **1,254 total cluster embeddings** (627 for each population).

## System Architecture

### Feature Spaces
- **Breakdown Population**: 35-dimensional feature space
- **No-Breakdown Population**: 32-dimensional feature space
- Each population maintains its own complete feature space containing ALL features used across ANY percentile

### Embedding Structure

Each cluster embedding contains:
1. **Dictionary Format**: `{feature_name: importance_value}` for human interpretation
2. **Vector Format**: `[importance_values...]` for computational analysis  
3. **Metadata**: Percentile, K-value, cluster ID, population type, and summary statistics

### Data Organization

```
cluster_embeddings/
├── complete_cluster_embeddings.json     # All embeddings (both formats)
├── embedding_summary.json               # High-level statistics
├── breakdown_feature_space.json         # Breakdown population features  
└── no_breakdown_feature_space.json      # No-breakdown population features
```

## Embedding Key Format

**Pattern**: `p{percentile}_k{k_value}_c{cluster_id}`

**Examples**:
- `p25_k3_c0` = Percentile 25, K=3 clusters, Cluster 0
- `p100_k8_c7` = Percentile 100, K=8 clusters, Cluster 7

## Feature Space Details

### Breakdown Population Features (35 total):
```
"10th_percentile_gap", "15th_percentile_gap", "20th_percentile_gap",
"25th_percentile_gap", "30th_percentile_gap", "35th_percentile_gap", 
"40th_percentile_gap", "45th_percentile_gap", "50th_percentile_gap",
"5th_percentile_gap", "abandon_ratio", "avg_group_size",
"biggest_group_metric", "clumpiness_score", "gini_coefficient",
"kurtosis_absolute", "kurtosis_normalized", "largest_group_position",
"largest_group_size", "proportion_in_groups", "riders_in_groups",
"selection_metric", "shannon_entropy_absolute", "shannon_entropy_normalized",
"skewness_absolute", "skewness_normalized", "std_deviation_absolute",
"std_deviation_normalized", "std_group_size", "time_gap_evenness_metric",
"total_finishers", "total_groups", "total_race_duration", 
"variance_absolute", "winning_time"
```

### No-Breakdown Population Features (32 total):
Similar feature set but with some features not present across percentiles.

## Embedding Properties

### Raw Importance Values
- **Preserved from clustering**: Feature importances are kept as raw values from K-means clustering
- **No normalization**: Values reflect actual importance magnitudes for similarity calculations
- **Zero filling**: Features not used in a percentile get importance = 0.0

### Missing Feature Handling
- Features not selected for a percentile = 0.0 importance
- Maintains consistent dimensionality across all embeddings in population
- Enables direct vector operations and similarity calculations

## Usage Examples

### Loading Embeddings
```python
import json
import numpy as np

# Load complete embeddings
with open('cluster_embeddings/complete_cluster_embeddings.json') as f:
    embeddings = json.load(f)

# Access specific cluster embedding (dictionary format)
cluster_dict = embeddings['with_breakdown']['embeddings_dict']['p25_k3_c0']

# Access specific cluster embedding (vector format)  
cluster_vector = np.array(embeddings['with_breakdown']['embeddings_vector']['p25_k3_c0'])

# Get feature space
feature_space = embeddings['with_breakdown']['feature_space']
```

### Similarity Calculations
```python
from cluster_embedding_system import ClusterEmbeddingGenerator

generator = ClusterEmbeddingGenerator()

# Find most similar clusters to a reference
similar_clusters = generator.find_similar_clusters(
    population_type='with_breakdown',
    reference_percentile='25',
    reference_k='3',
    reference_cluster='0',
    top_n=10
)

# Calculate direct similarity between two embeddings
vec1 = generator.create_cluster_embedding_vector('with_breakdown', '25', '3', '0')
vec2 = generator.create_cluster_embedding_vector('with_breakdown', '30', '3', '0')
similarity = generator.calculate_embedding_similarity(vec1, vec2, method='cosine')
```

### Cross-Percentile Analysis
```python
# Analyze how clusters change across percentiles for K=3
patterns = generator.analyze_cross_percentile_patterns('with_breakdown', '3')

# Access cross-percentile similarity matrix
similarities = patterns['cross_percentile_similarities']
```

## Data Statistics

### Coverage:
- **Percentiles**: 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100 (19 total)
- **K Values**: 3, 4, 5, 6, 7, 8 (6 total)
- **Total Combinations**: 19 percentiles × 6 K values = 114 configurations per population

### Embedding Counts:
- **Breakdown Population**: 627 cluster embeddings
- **No-Breakdown Population**: 627 cluster embeddings  
- **Total System**: 1,254 cluster embeddings

### Metadata Available:
Each embedding includes:
- `percentile`: Inclusion percentage (10-100)
- `k_value`: Number of clusters (3-8)
- `cluster_id`: Cluster identifier (0 to k-1)
- `population_type`: "with_breakdown" or "no_breakdown"
- `n_features_used`: Count of non-zero features
- `total_importance`: Sum of all importance values
- `max_importance`: Highest feature importance
- `top_features`: Top 5 features by importance

## Similarity Methods

### Available Methods:
1. **Cosine Similarity** (default): Measures angle between vectors, range [-1, 1]
2. **Euclidean Distance**: Negative L2 norm, lower values = more similar
3. **Correlation**: Pearson correlation coefficient, range [-1, 1]

### Interpretation:
- **Cosine ≥ 0.8**: Very similar cluster types
- **Cosine 0.5-0.8**: Moderately similar clusters
- **Cosine < 0.3**: Different cluster types

## Future Applications

### Master-Cluster Assignment
The embeddings enable:
1. **Cluster correlation**: Find which clusters across percentiles represent the same "race kind"
2. **Consistent labeling**: Assign meaningful names to cluster types
3. **Cross-percentile tracking**: See how race kinds evolve with inclusion percentage

### Similarity Analysis
- Compare cluster stability across percentiles
- Identify dominant race patterns
- Find optimal percentile ranges for classification

### Model Integration  
- Use embeddings as features for race prediction
- Create race type hierarchies
- Enable transfer learning between percentiles

## Technical Notes

### File Sizes
- `complete_cluster_embeddings.json`: ~15MB (contains all data)
- Dense storage format optimized for loading speed
- Consider compression for production deployment

### Performance
- Vector operations optimized with NumPy
- In-memory processing suitable for current dataset size
- Scalable architecture for additional percentiles/populations

### Data Integrity
- All embeddings validated for consistent dimensionality
- Feature spaces verified across all percentiles
- Metadata cross-checked with source clustering results

This embedding system provides the foundation for sophisticated race kind analysis and cross-percentile cluster correlation studies.