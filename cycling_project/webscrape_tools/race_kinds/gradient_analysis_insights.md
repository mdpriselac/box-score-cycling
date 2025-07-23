# Race Feature Gradient Analysis: Key Insights

## Why Gradients Matter for Race Classification

Traditional race analysis looks at features at a single percentile (e.g., full field). However, **how** features change as we zoom in from the full field to just the top performers reveals the fundamental nature of the race.

## Expected Gradient Patterns by Race Type

### 1. Time Trials / Prologues
**Expected Pattern**: Minimal gradient change across percentiles
- **Variance**: Stays relatively constant (everyone races alone)
- **Skewness**: Near zero at all percentiles
- **Clumpiness**: Very low throughout
- **Selection Metric**: Gradual, linear increase

**Gradient Signature**:
```
- Low volatility across all features
- High monotonicity (consistent direction)
- Minimal early selection indicator
```

### 2. Sprint Finishes
**Expected Pattern**: Dramatic changes only at top percentiles
- **Variance**: Huge drop from 100% to 90% (peloton vs breakaway)
- **Skewness**: Shifts dramatically at top percentiles
- **Clumpiness**: High at 100%, drops sharply
- **Selection Metric**: Step function around 20-30%

**Gradient Signature**:
```
- High volatility in upper percentiles (10-30%)
- Low progressive selection score (sudden changes)
- High early selection indicator
```

### 3. Mountain Stages
**Expected Pattern**: Progressive, gradual changes
- **Variance**: Steady increase as percentile decreases
- **Skewness**: Gradually becomes more negative
- **Clumpiness**: Decreases progressively
- **Selection Metric**: Smooth, progressive increase

**Gradient Signature**:
```
- High monotonicity (consistent trends)
- High progressive selection score
- Medium feature stability
```

### 4. Classics/Monuments
**Expected Pattern**: Multiple inflection points
- **Variance**: Non-monotonic changes (multiple selection points)
- **Skewness**: Oscillates based on race dynamics
- **Clumpiness**: Multiple peaks at different percentiles
- **Selection Metric**: Step-wise increases at key points

**Gradient Signature**:
```
- Medium-high volatility
- Low monotonicity (direction changes)
- Multiple local maxima in gradient curves
```

## Key Gradient-Based Discriminators

### 1. **Volatility Patterns**
- **Low volatility** → Predictable races (TT, controlled stages)
- **High volatility** → Dynamic races (classics, mountain stages)
- **Volatility concentrated at top** → Sprint stages

### 2. **Monotonicity Scores**
- **High positive** → Progressive selection (climbing)
- **High negative** → Bunch finishes
- **Near zero** → Complex dynamics (classics)

### 3. **Early vs Late Selection**
```python
early_selection_ratio = changes_10_30pct / total_changes
```
- **High ratio** → Decisive early moves (breakaway stages)
- **Low ratio** → Late race decisions (sprints)

### 4. **Feature Coupling**
How features change together reveals race dynamics:
- **Variance ↑ + Clumpiness ↓** → Individual time gaps (climbing)
- **Variance ↓ + Clumpiness ↑** → Group formations (echelons)
- **All stable** → Processional stage

## Practical Applications

### 1. Automatic Race Classification
```python
def classify_race_type(gradients):
    if gradients.avg_volatility < 0.1:
        return "TIME_TRIAL"
    elif gradients.early_selection > 0.7:
        return "BREAKAWAY_STAGE"  
    elif gradients.variance_slope > 0.5:
        return "MOUNTAIN_STAGE"
    elif gradients.monotonicity['clumpiness'] < -0.8:
        return "SPRINT_STAGE"
    else:
        return "MIXED_TERRAIN"
```

### 2. Race Difficulty Assessment
- **Total gradient magnitude**: Σ|slope| across features
- **Percentile coverage**: How many riders "survive" to each percentile
- **Feature instability**: High volatility = unpredictable/hard race

### 3. Strategic Insights
- **Where selection happens**: Identify critical percentile ranges
- **Type of selection**: Gradual (endurance) vs sudden (tactical)
- **Recovery opportunities**: Stable gradient zones = regrouping points

## Implementation Priority

1. **Phase 1**: Calculate gradients for core features
   - Variance (absolute & normalized)
   - Skewness & Kurtosis
   - Selection metric

2. **Phase 2**: Develop race type classifier
   - Train on known race types
   - Validate gradient patterns
   - Refine discriminator thresholds

3. **Phase 3**: Advanced applications
   - Similarity matching via gradient signatures
   - Anomaly detection (unusual race dynamics)
   - Performance prediction based on gradient fit

## Example Gradient Signatures

### Classic Sprint Stage
```
variance_normalized: [0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.15, 0.1, ...]
                     ↓ steady decrease then sharp drop at top percentiles

clumpiness_score:    [0.9, 0.85, 0.8, 0.75, 0.7, 0.6, 0.3, 0.1, ...]
                     ↓ high values (bunch) dropping sharply for breakaway

early_selection:     0.75 (most change happens in top 30%)
```

### Mountain Stage
```
variance_normalized: [0.2, 0.25, 0.3, 0.35, 0.45, 0.55, 0.7, 0.85, ...]
                     ↓ steady increase as selection increases

selection_metric:    [0.1, 0.15, 0.2, 0.3, 0.4, 0.55, 0.7, 0.85, ...]
                     ↓ progressive increase, high monotonicity

progressive_score:   0.85 (gradual selection throughout)
```

## Next Steps

1. Implement gradient calculation pipeline
2. Process historical races to build gradient database
3. Develop classification algorithms based on gradient patterns
4. Create visualization tools for gradient analysis
5. Validate patterns against known race outcomes