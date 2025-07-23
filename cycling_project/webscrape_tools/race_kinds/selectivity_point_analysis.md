# Selectivity Point Analysis: Finding Where Racing Becomes Riding

## Core Concept

Every race has a **selectivity point** - the percentile threshold where competitive racing transitions to simply finishing. This point reveals fundamental race characteristics and helps classify race types.

## Key Metrics

### 1. Selectivity Point (SP)
The percentile where variance drops below a threshold, indicating the end of competitive racing.

```python
def find_selectivity_point(variance_gradient, threshold=0.05):
    """
    Find the percentile where normalized variance drops below threshold.
    Returns None if variance never drops (fully competitive race).
    """
    for percentile, variance in variance_gradient:
        if variance < threshold:
            return percentile
    return None  # No clear selectivity point
```

### 2. Selectivity Profile
How variance changes approaching the selectivity point:

```python
selectivity_profile = {
    'point': 45,  # Selectivity at 45th percentile
    'sharpness': 0.8,  # How suddenly it drops (0=gradual, 1=sudden)
    'pre_slope': -0.02,  # Variance slope before SP
    'post_slope': -0.001,  # Variance slope after SP
}
```

### 3. Post-Selectivity Distribution
Analyzing the "non-racing" portion reveals race dynamics:

```python
def analyze_post_selectivity(time_gaps, selectivity_point):
    """Analyze rider distribution after selectivity point."""
    post_sp_gaps = time_gaps[selectivity_point:]
    
    return {
        'spread': np.std(post_sp_gaps),
        'groups': count_groups(post_sp_gaps),
        'isolation_ratio': count_isolated_riders(post_sp_gaps) / len(post_sp_gaps),
        'largest_group_size': max_group_size(post_sp_gaps)
    }
```

## Race Type Signatures

### 1. Mass Sprint Finish
- **Selectivity Point**: Very low (10-20%) or none
- **Profile**: Sudden drop after breakaway
- **Post-SP**: Large group with few stragglers
```
Variance: [0.9, 0.85, 0.8, 0.1, 0.05, 0.02, 0.01, ...]
           ↑ high variance  ↑ sharp drop  ↑ minimal variance
SP: 25%
Post-SP: 90% of field in main group
```

### 2. Mountain Stage
- **Selectivity Point**: Progressive, often 60-70%
- **Profile**: Gradual decline
- **Post-SP**: Scattered individuals/small groups
```
Variance: [0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.4, 0.2, 0.05, ...]
           ↑ increasing selection  ↑ SP ~70%  ↑ stragglers
SP: 70%
Post-SP: Highly scattered, many individuals
```

### 3. Echelon/Crosswind Stage  
- **Selectivity Point**: Multiple or mid-race (40-60%)
- **Profile**: Step-wise drops
- **Post-SP**: Distinct groups
```
Variance: [0.4, 0.35, 0.3, 0.15, 0.1, 0.12, 0.08, 0.02, ...]
           ↑ first split  ↑ second split  ↑ groups form
SP: 50% (primary)
Post-SP: 3-4 distinct groups
```

### 4. Time Trial
- **Selectivity Point**: None or very high (90%+)
- **Profile**: Constant low variance
- **Post-SP**: Even distribution
```
Variance: [0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.08, 0.05, ...]
           ↑ constant low variance throughout
SP: None (always competitive)
Post-SP: N/A
```

## Advanced Metrics

### 1. Racing Intensity Score
How much of the field is actually racing vs riding:
```python
racing_intensity = selectivity_point / 100 if selectivity_point else 1.0
```

### 2. Attrition Pattern
The distribution pattern beyond the selectivity point:
```python
def classify_attrition_pattern(post_sp_distribution):
    if post_sp_distribution['largest_group_size'] > 0.7:
        return "GROUPED"  # Most in one group (sprint)
    elif post_sp_distribution['isolation_ratio'] > 0.5:
        return "SCATTERED"  # Individual time gaps (mountain)
    elif post_sp_distribution['groups'] > 3:
        return "MULTI_GROUP"  # Echelons/splits
    else:
        return "GRADUAL"  # Even distribution
```

### 3. Selectivity Gradient
Rate of change approaching the selectivity point:
```python
def calculate_selectivity_gradient(variance_values, sp_index):
    if sp_index < 3:
        return None
    
    # Look at 3 points before SP
    pre_sp_values = variance_values[sp_index-3:sp_index]
    gradient = np.gradient(pre_sp_values).mean()
    
    return {
        'gradient': gradient,
        'acceleration': np.gradient(np.gradient(pre_sp_values)).mean(),
        'pattern': 'sudden' if abs(gradient) > 0.1 else 'gradual'
    }
```

## Implementation in Gradient System

### Additional Table Columns
```sql
-- Add to race_feature_gradients table
selectivity_point INTEGER,  -- Percentile where variance < threshold
selectivity_sharpness REAL,  -- How suddenly variance drops
pre_selectivity_slope REAL,  -- Variance trend before SP
post_selectivity_slope REAL,  -- Variance trend after SP

-- Post-selectivity metrics
post_sp_spread REAL,  -- Std dev of gaps after SP
post_sp_group_count INTEGER,  -- Number of groups after SP
post_sp_isolation_ratio REAL,  -- Proportion riding alone
post_sp_largest_group REAL,  -- Size of biggest group

-- Derived classifications
racing_intensity_score REAL,  -- How much of field is racing
attrition_pattern TEXT,  -- GROUPED/SCATTERED/MULTI_GROUP
selectivity_type TEXT  -- NONE/EARLY/PROGRESSIVE/LATE
```

### Analysis Function
```python
def analyze_selectivity_point(competition_id, variance_gradient):
    """Complete selectivity point analysis."""
    
    # Find selectivity point
    sp = find_selectivity_point(variance_gradient)
    
    if sp is None:
        return {
            'selectivity_point': None,
            'selectivity_type': 'NONE',
            'racing_intensity_score': 1.0
        }
    
    # Analyze approach to SP
    sp_profile = analyze_selectivity_profile(variance_gradient, sp)
    
    # Analyze post-SP distribution
    post_sp_data = analyze_post_selectivity_distribution(competition_id, sp)
    
    # Classify patterns
    selectivity_type = classify_selectivity_type(sp, sp_profile)
    attrition_pattern = classify_attrition_pattern(post_sp_data)
    
    return {
        'selectivity_point': sp,
        'selectivity_sharpness': sp_profile['sharpness'],
        'pre_selectivity_slope': sp_profile['pre_slope'],
        'post_selectivity_slope': sp_profile['post_slope'],
        'post_sp_spread': post_sp_data['spread'],
        'post_sp_group_count': post_sp_data['groups'],
        'post_sp_isolation_ratio': post_sp_data['isolation_ratio'],
        'post_sp_largest_group': post_sp_data['largest_group_size'],
        'racing_intensity_score': sp / 100,
        'attrition_pattern': attrition_pattern,
        'selectivity_type': selectivity_type
    }
```

## Race Classification Rules

### Sprint Stage Indicators
- Selectivity point < 30% OR none
- Post-SP largest group > 70%
- Low post-SP spread
- Sudden selectivity drop

### Mountain Stage Indicators  
- Selectivity point > 60%
- High post-SP isolation ratio
- Progressive selectivity gradient
- High post-SP spread

### Breakaway Stage Indicators
- Early selectivity point (20-40%)
- Sharp selectivity drop
- Stable low variance after SP
- Small post-SP groups

### Classic/Monument Indicators
- Multiple variance peaks
- Mid-race selectivity (40-60%)
- Multiple distinct post-SP groups
- Variable selectivity gradient

## Visualization Ideas

### Selectivity Point Chart
```
100% |●····························
 90% |·●···························
 80% |··●··························
 70% |···●·························
 60% |····●························ 
 50% |·····●······················· ← Selectivity Point
 40% |······○○○○○○○················ (variance drops)
 30% |·············○○○○○○○○········
 20% |····················○○○○○○○○·
 10% |····························○
     +-----------------------------
      0.0   0.2   0.4   0.6   0.8
           Normalized Variance
```

### Post-Selectivity Distribution
```
Sprint Finish:          Mountain Stage:
|████████████···|       |·█·█··█·█··█·█|
 ↑ main group           ↑ scattered individuals

Echelon Stage:          Time Trial:
|███··███··██··|       |█·█·█·█·█·█·█·|
 ↑ multiple groups      ↑ even distribution
```

## Strategic Insights

1. **Team Tactics**: Races with early selectivity points favor aggressive early moves
2. **Energy Management**: High selectivity point = save energy early
3. **Positioning Importance**: Sharp selectivity drops = critical positioning
4. **Recovery Opportunities**: Post-SP group size indicates drafting potential

This analysis provides deep insights into race dynamics that simple statistical measures miss, enabling much more nuanced race classification and strategic understanding.