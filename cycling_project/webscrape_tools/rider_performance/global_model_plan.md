# Global Model Plan for Rider Performance Prediction

## Overview

This document outlines our approach to building a global rider performance prediction system using a single model that incorporates rider-specific features, rather than training individual models for each rider.

## Core Architecture

### Model Type
- **Primary Algorithm**: Gradient Boosting (XGBoost or LightGBM)
- **Model Scope**: Single global model for all riders
- **Target Variable**: UCI points (both 2026 scheme and proportional discounting)

### Feature Categories

#### 1. Race Features (10-15 features)
- Statistical measures (variance, standard deviation, skewness, kurtosis)
- Distribution metrics (gini coefficient, shannon entropy)
- Engineered metrics (biggest group, time gap evenness, clumpiness, selection metric)
- Percentile gaps (10th, 25th, 50th percentile gaps)

#### 2. Race Kind Features (~8 features)
- Cluster label (0, 1, 2)
- Local density and boundary distance
- One-hot encoded cluster membership
- Distances to each cluster center

#### 3. Competition Metadata
- Competition type (gc, stage, one_day)
- Tour level (wt, pro, d1)
- Race year and date (for temporal features)

#### 4. Rider-Specific Features
- **Basic attributes**: Age at race date
- **Experience metrics**:
  - Total competitions completed
  - Competitions by type (gc, stage, one_day)
  - Proportion of WT competitions
- **Historical performance**:
  - Average points in this race kind
  - Recent form (last 3, 6, 12 months)
  - Career statistics by race type/level
  - Performance trajectory/improvement rate

## Implementation Phases

### Phase 1: Data Pipeline
1. Build feature extraction pipeline for historical data
2. Create point calculation system (both UCI schemes)
3. Implement rider history aggregation up to any given date
4. Handle minimum history requirements (fallback to percentile predictions)

### Phase 2: Model Development
1. Feature engineering and selection
2. Train global XGBoost/LightGBM model
3. Hyperparameter optimization
4. Cross-validation strategy (time-based splits)

### Phase 3: Rider Characterization System
1. **Performance Fingerprinting**
   - Generate predictions across all race kinds for each rider
   - Create rider specialty profiles based on relative performance
   
2. **SHAP Analysis Pipeline**
   - Calculate feature importance for each prediction
   - Identify which race characteristics drive each rider's success
   
3. **Rider Embedding System** (lightweight parallel model)
   - Map riders to low-dimensional specialty space
   - Use embeddings as additional features in main model

### Phase 4: Field Strength & Analytics
1. **Field Strength Calculator**
   - Sum/average predicted points for all riders in a race
   - Compare to historical averages by race kind
   
2. **Rider Clustering**
   - Group riders by their performance fingerprints
   - Identify rider archetypes (sprinter, climber, all-rounder, etc.)

### Phase 5: Evaluation Framework
1. Backtest on 2022, 2023, 2024 seasons
2. Compare UCI 2026 vs proportional point schemes
3. Analyze prediction accuracy by:
   - Race type and level
   - Rider experience levels
   - Field strength variations

## Technical Considerations

### Temporal Handling
- Initial: Static snapshots (all data up to prediction date)
- Enhancement: Implement time decay for older results
- Future: Rolling window approaches with recency weighting

### Missing Data Strategy
- Riders with insufficient history: Use race-kind-specific percentile predictions
- Minimum races threshold: Start with 10 races, tune based on performance
- Gradual transition from generic to personalized predictions

### Feature Store Design
- Pre-compute rider features for efficiency
- Update incrementally as new results arrive
- Cache race features and race kind features

## Advantages of Global Model Approach

1. **Data Efficiency**: Leverages all rider data for better generalization
2. **Computational Efficiency**: Single model to train and maintain
3. **Consistency**: Uniform predictions across all riders
4. **Interpretability**: Clear feature importance across the system
5. **Flexibility**: Easy to add new features or adjust for new riders

## Success Metrics

1. **Prediction Accuracy**: MAE/RMSE on held-out test sets
2. **Ranking Quality**: Spearman correlation of predicted vs actual rankings
3. **Characterization Quality**: Coherence of identified rider clusters
4. **Field Strength Accuracy**: Correlation with actual race difficulty

## Next Steps

1. Set up data pipeline infrastructure
2. Create feature engineering modules
3. Implement baseline model
4. Build rider characterization tools
5. Develop evaluation framework