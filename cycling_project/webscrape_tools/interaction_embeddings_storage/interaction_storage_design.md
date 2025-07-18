# Interaction Terms Storage Design

## Overview
This document outlines the storage system for interaction terms between race features and rider performance correlations. The design follows the existing correlation storage pattern for consistency and ease of use.

## Interaction Types
We will calculate three types of interactions:
1. **Dot Product** - Scalar value representing overall alignment
2. **Cosine Similarity** - Normalized dot product (scalar value)
3. **Hadamard Product** - Element-wise multiplication (37-element vector)

## Database Schema

### Primary Storage Tables

#### `rider_interactions_scalar`
Stores dot product and cosine similarity (scalar interactions).

```sql
CREATE TABLE rider_interactions_scalar (
    rider_result_id INTEGER NOT NULL,
    competition_id INTEGER NOT NULL,
    rider_id INTEGER NOT NULL,
    correlation_type TEXT NOT NULL,  -- 'all_races', 'same_type', 'stage_one_days'
    percentile INTEGER NOT NULL,     -- 30, 40, 50, 60, 70, 80, 90, 100
    interaction_type TEXT NOT NULL,  -- 'dot_product', 'cosine_similarity'
    interaction_value REAL,          -- NULL if percentile unavailable
    
    PRIMARY KEY (rider_result_id, correlation_type, percentile, interaction_type),
    FOREIGN KEY (rider_result_id) REFERENCES rider_results(id),
    FOREIGN KEY (competition_id) REFERENCES competitions(id),
    FOREIGN KEY (rider_id) REFERENCES riders(id)
);
```

#### `rider_interactions_hadamard`
Stores Hadamard product (element-wise interactions).

```sql
CREATE TABLE rider_interactions_hadamard (
    rider_result_id INTEGER NOT NULL,
    competition_id INTEGER NOT NULL,
    rider_id INTEGER NOT NULL,
    correlation_type TEXT NOT NULL,
    percentile INTEGER NOT NULL,
    feature_idx INTEGER NOT NULL,     -- 0-36
    feature_name TEXT NOT NULL,
    interaction_value REAL,           -- NULL if percentile unavailable
    
    PRIMARY KEY (rider_result_id, correlation_type, percentile, feature_idx),
    FOREIGN KEY (rider_result_id) REFERENCES rider_results(id),
    FOREIGN KEY (competition_id) REFERENCES competitions(id),
    FOREIGN KEY (rider_id) REFERENCES riders(id)
);
```

#### `interaction_processing_status`
Tracks processing progress and data quality.

```sql
CREATE TABLE interaction_processing_status (
    rider_result_id INTEGER NOT NULL,
    correlation_type TEXT NOT NULL,
    percentiles_processed TEXT NOT NULL,  -- JSON array [1,1,0,0,0,0,0,0]
    scalar_computed BOOLEAN DEFAULT 0,
    hadamard_computed BOOLEAN DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (rider_result_id, correlation_type)
);
```

### Indexes for Performance

```sql
-- Scalar interactions
CREATE INDEX idx_scalar_lookup ON rider_interactions_scalar(competition_id, rider_id, correlation_type);
CREATE INDEX idx_scalar_rider ON rider_interactions_scalar(rider_id, competition_id);

-- Hadamard interactions  
CREATE INDEX idx_hadamard_lookup ON rider_interactions_hadamard(competition_id, rider_id, correlation_type);
CREATE INDEX idx_hadamard_feature ON rider_interactions_hadamard(feature_name, correlation_type);
CREATE INDEX idx_hadamard_rider ON rider_interactions_hadamard(rider_id, competition_id);

-- Processing status
CREATE INDEX idx_proc_status ON interaction_processing_status(scalar_computed, hadamard_computed);
```

## Computation Strategy

### Memory-Efficient Processing
1. **Batch Processing**: Process competitions in batches of 100-200 to manage memory
2. **Streaming Computation**: Load correlation vectors and race features on-demand
3. **Parallel Processing**: Use multiprocessing for independent computations
4. **Checkpointing**: Save progress every 1000 rider results

### Computation Pipeline
```python
# Pseudocode for main processing loop
for competition_batch in get_competition_batches():
    # Load race features for all percentiles
    race_features = load_race_features(competition_batch)
    
    # Process riders in the competition
    for rider_result in get_rider_results(competition_batch):
        # Load correlation vectors
        correlations = load_correlations(rider_result)
        
        # Compute interactions for each available percentile
        for percentile in get_available_percentiles(rider_result):
            if race_features[percentile] exists:
                # Compute scalar interactions
                dot_prod = compute_dot_product(correlations, race_features)
                cosine_sim = compute_cosine_similarity(correlations, race_features)
                
                # Compute hadamard product
                hadamard = compute_hadamard_product(correlations, race_features)
                
                # Store results
                store_interactions(rider_result, percentile, dot_prod, cosine_sim, hadamard)
```

### Handling Missing Data
- If a percentile is missing from either race_features or correlations, store NULL
- Track which percentiles were processed in `interaction_processing_status`
- Maintain consistency with correlation storage patterns

## Subset Infrastructure

### Custom Interaction Calculator
For fine-tuning with specific feature subsets:

```python
class SubsetInteractionCalculator:
    def __init__(self, feature_indices: List[int], correlation_types: List[str]):
        self.feature_indices = feature_indices
        self.correlation_types = correlation_types
    
    def compute_interactions(self, rider_result_ids: List[int], percentiles: List[int]):
        # Load only specified features and correlation types
        # Compute interactions on the subset
        # Return results without storing in main tables
```

### Temporary Storage for Experiments
```sql
CREATE TABLE interaction_experiments (
    experiment_id TEXT NOT NULL,
    rider_result_id INTEGER NOT NULL,
    correlation_type TEXT NOT NULL,
    percentile INTEGER NOT NULL,
    feature_subset TEXT NOT NULL,      -- JSON array of feature indices
    interaction_type TEXT NOT NULL,
    interaction_value REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (experiment_id, rider_result_id, correlation_type, percentile, interaction_type)
);
```

## Storage Estimates
- Scalar interactions: ~100MB (2 values × 3 correlation types × 8 percentiles × ~200k rider results)
- Hadamard interactions: ~2GB (37 features × 3 correlation types × 8 percentiles × ~200k rider results)
- Total estimated storage: ~2.1GB

## Implementation Order
1. Create database schema
2. Implement core computation functions
3. Build batch processing pipeline
4. Add progress tracking and resume capability
5. Create subset calculation infrastructure
6. Add monitoring and validation tools