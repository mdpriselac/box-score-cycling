# Race Feature N-Analysis: Categories and Quality Metrics Explained

## Overview

The Race Feature N-Analysis examines how cycling race features behave as we expand from analyzing only the top 30% of riders (N=30) to analyzing all riders (N=100). Each feature is classified into behavioral patterns and assigned quality scores to help identify the most useful features for race analysis.

## Feature Behavior Categories

### 1. Stable Features

**Definition**: Features that maintain consistent statistical properties (low variation in coefficient of variation) across all N levels.

**Code Location**: `feature_pattern_classifier.py:162-164`
```python
cv_values = [stats_by_n[n]['cv'] for n in sorted(stats_by_n.keys())]
is_stable = np.std(cv_values) < 0.1
```

**What This Means**: 
- The feature's relative variability doesn't change much whether you're looking at just elite riders or all riders
- These features provide consistent measurement regardless of the rider pool size
- They are reliable for comparisons across different competitive levels

**Example Use Case**: 
If `winning_time` is classified as stable, it means the time advantage of winners is proportionally similar whether you're comparing within the top 30% of riders or across all riders. This makes it a reliable metric for race difficulty assessment regardless of field depth.

---

### 2. Dilution Features

**Definition**: Features where variance increases significantly as N increases (more riders dilute the signal).

**Code Location**: `feature_pattern_classifier.py:166-168`
```python
variance_trend = self.calculate_trend([stats_by_n[n]['variance'] for n in sorted(stats_by_n.keys())])
shows_dilution = variance_trend['slope'] > 0 and variance_trend['r2'] > 0.7
```

**What This Means**:
- Adding more riders (especially lower-performing ones) increases the spread of values
- The feature becomes "noisier" with larger rider pools
- Elite-focused analysis (lower N) provides cleaner signals

**Example Use Case**:
If `abandon_ratio` shows dilution, it means that when you include more riders beyond the elite group, the abandonment patterns become more variable and less predictable. The metric is most informative when focused on top performers.

---

### 3. Concentration Features

**Definition**: Features that become more concentrated (lower entropy) as N increases.

**Code Location**: `feature_pattern_classifier.py:170-172`
```python
entropy_trend = self.calculate_trend([stats_by_n[n]['entropy'] for n in sorted(stats_by_n.keys())])
shows_concentration = entropy_trend['slope'] < 0 and entropy_trend['r2'] > 0.7
```

**What This Means**:
- Including more riders reduces the diversity of feature values
- Lower-performing riders cluster around similar values
- The feature differentiates better among elite riders

**Example Use Case**:
If `selection_metric` shows concentration, it suggests that as you include more riders, most cluster around lower selection values, making the metric primarily useful for distinguishing between highly selective races rather than general race characteristics.

---

### 4. Threshold Features

**Definition**: Features that show sudden, significant changes at specific N levels.

**Code Location**: `feature_pattern_classifier.py:174-175` and `detect_threshold` method at lines 87-119`
```python
threshold_n = self.detect_threshold(stats_by_n)
has_threshold = threshold_n is not None
```

**Detection Logic** (`detect_threshold` method):
- Calculates relative changes between consecutive N levels
- Identifies changes >30% in mean or variance as significant thresholds
- Returns the N level where the largest change occurs

**What This Means**:
- There's a specific competitive level where the feature behavior fundamentally changes
- The threshold often represents the boundary between "competitive" and "recreational" participants
- Analysis strategy should consider this breakpoint

**Example Use Case**:
If `gini_coefficient` has a threshold at N=60, it means the inequality measure behaves differently when analyzing the top 60% vs. including more riders. This could indicate that beyond the 60th percentile, riders cluster more tightly in performance, changing the nature of competitive spread.

---

### 5. Bimodal Features

**Definition**: Features where the distribution shifts from unimodal to bimodal (or vice versa) across N levels.

**Code Location**: `feature_pattern_classifier.py:177` and `test_bimodality` method at lines 124-150`
```python
bimodality_by_n = {n: self.test_bimodality(feature_name, n) for n in [30, 50, 70, 90]}
```

**Detection Logic** (`test_bimodality` method):
- Creates histogram of feature values
- Identifies peaks separated by significant valleys
- A valley <60% of the smaller peak height indicates bimodality

**What This Means**:
- The competitive field splits into distinct groups at certain N levels
- May indicate natural breakpoints in rider categories (e.g., professional vs. amateur)
- Suggests different analytical approaches for different N ranges

**Example Use Case**:
If `time_gap_evenness_metric` becomes bimodal at N=70, it suggests that when you include riders beyond the 70th percentile, the race field naturally separates into two distinct groups: one with tight time gaps (competitive riders) and another with loose gaps (recreational riders).

---

### 6. Complex Features

**Definition**: Features that don't fit cleanly into other categories or show multiple behavioral patterns.

**Code Location**: `feature_pattern_classifier.py:186-187`
```python
primary_pattern = self.determine_primary_pattern(is_stable, shows_dilution, shows_concentration, threshold_n)
# Returns "complex" if no clear pattern emerges
```

**What This Means**:
- The feature exhibits multiple behaviors simultaneously or changes unpredictably
- May require specialized analysis approaches
- Could indicate interaction effects with other variables

**Example Use Case**:
A complex feature might show dilution at lower N levels but then stabilize at higher N levels, making it useful for specific analytical windows but requiring careful interpretation.

---

## Feature Quality Tiers

### How Quality Scores Are Calculated

**Code Location**: `race_feature_n_analyzer.py:115-140`

The overall quality score combines three components:

1. **Stability Score** (`calculate_overall_stability` method):
   ```python
   cv_stability = 1 - (np.std(cv_values) / (np.mean(cv_values) + 1e-10))
   mean_stability = 1 - (np.std(mean_values) / (np.mean(mean_values) + 1e-10))
   trend_stability = 1 - trends.get('cv_r2', 0)
   return np.mean([cv_stability, mean_stability, trend_stability])
   ```

2. **Information Value Score** (`calculate_overall_information_value` method):
   ```python
   mean_ig = np.mean(ig_scores)  # Information gain across targets
   mean_distinctiveness = distinctiveness_results['distinctiveness'].get('mean_distinctiveness', 0)
   return (mean_distinctiveness + mean_ig) / 2
   ```

3. **Monotonicity Score**:
   ```python
   monotonicity_score = abs(mono.spearman_correlation) * mono.linearity_r2
   ```

**Final Quality Score**:
```python
quality_score = np.mean([stability_score, information_score, monotonicity_score])
```

### Tier Definitions

**Code Location**: `race_feature_n_analyzer.py:142-156`

```python
n_features = len(quality_scores)
tier_size = n_features // 3

tiers = {
    'tier_1_high_quality': top_third_features,      # Highest quality scores
    'tier_2_medium_quality': middle_third_features,  # Middle quality scores  
    'tier_3_low_quality': bottom_third_features     # Lowest quality scores
}
```

### What Each Tier Means

#### Tier 1 (High Quality)
- **Stability**: Consistent behavior across N levels
- **Information Value**: High discriminative power and information gain
- **Monotonicity**: Clear, predictable trends with N changes
- **Use Case**: Primary features for robust race analysis and modeling

#### Tier 2 (Medium Quality)
- **Characteristics**: Good in some aspects but may have limitations
- **Examples**: Stable but low information content, or high information but unstable
- **Use Case**: Secondary features for specialized analysis or validation

#### Tier 3 (Low Quality)
- **Characteristics**: Inconsistent, low information content, or unpredictable behavior
- **Issues**: May be noisy, redundant, or only useful in specific contexts
- **Use Case**: Consider for exclusion or use only with careful context

## N-Level Recommendation System

The analysis provides sophisticated recommendations for choosing optimal N levels based on your research goals and feature behavior patterns.

### Understanding the Recommendation Categories

#### Analysis Type Recommendations

**Code Location**: `race_type_analyzer.py:309-330`

The system provides N-level recommendations tailored to different analytical objectives:

##### Elite Competition Analysis
- **Recommended N**: [30, 40]
- **Purpose**: Focus on competitive dynamics among top performers
- **When to Use**: Studying tactics, selection pressure, performance gaps in professional racing
- **Key Features**: Features that show strong preference for elite focus (peak at low N with >5% score range)

##### Balanced Field Analysis  
- **Recommended N**: [50, 60, 70]
- **Purpose**: Compromise between competitive signal and field representation
- **When to Use**: General race characterization, comparing events with different competitive depths
- **Key Features**: Features that are stable across N levels (score range ≤5%)

##### Inclusive Field Analysis
- **Recommended N**: [80, 90, 100] 
- **Purpose**: Understanding full field dynamics including recreational participants
- **When to Use**: Mass participation events, understanding dropout patterns, field effects
- **Key Features**: Features that perform optimally with broader inclusion (peak at high N)

##### Comparative Analysis
- **Recommended N**: [30, 60, 90]
- **Purpose**: Strategic sampling across competitive levels
- **When to Use**: Multi-level studies, understanding how competitive depth affects race characteristics

#### Statistical Performance Rankings

**Code Location**: `race_type_analyzer.py:332-336`

##### Best Peak Performance
- **Definition**: N levels where the most features achieve their highest scores
- **Interpretation**: These N levels maximize feature information content
- **Use Case**: When you need maximum discriminative power

##### Most Consistent Performance  
- **Definition**: N levels with lowest coefficient of variation across features
- **Calculation**: `1 - (std_scores / mean_scores)` for each N level
- **Use Case**: When you need reliable, stable measurements

##### Highest Average Scores
- **Definition**: N levels with highest mean feature scores across all features
- **Use Case**: General-purpose analysis when you want overall strong performance

### Feature Behavior Classification

**Code Location**: `race_type_analyzer.py:269-275`

#### Elite-Preferring Features
- **Criteria**: Optimal N ≤ 40 AND score range > 5%
- **Meaning**: These features lose information when including lower-tier riders
- **Examples**: `abandon_ratio`, `selection_metric`, `clumpiness_score`
- **Interpretation**: Elite competitive dynamics are fundamentally different

#### Inclusive-Preferring Features  
- **Criteria**: Optimal N ≥ 80 AND score range > 5%
- **Meaning**: These features gain information from broader field inclusion
- **Examples**: Percentile gap features, time distribution metrics
- **Interpretation**: Full field effects matter for these characteristics

#### Stable Across N Features
- **Criteria**: Score range ≤ 5% across all N levels
- **Meaning**: Robust measurements regardless of competitive level analyzed
- **Interpretation**: Fundamental race characteristics that scale consistently

### Traditional Sets (Backward Compatibility)

For users familiar with the original simple recommendations:

- **Minimal Set**: [30, 50, 80] - Strategic sampling across competitive levels
- **Balanced Set**: [30, 40, 60, 80, 90] - Comprehensive coverage with key transition points
- **Comprehensive Set**: All N levels [30, 40, 50, 60, 70, 80, 90, 100]

## Practical Usage Guidelines

### For Research Design

#### If you're studying...
- **Professional racing tactics** → Use Elite Competition Analysis ([30, 40])
- **General race characteristics** → Use Balanced Field Analysis ([50, 60, 70])  
- **Mass participation events** → Use Inclusive Field Analysis ([80, 90, 100])
- **Multi-level comparisons** → Use Comparative Analysis ([30, 60, 90])

#### If your features are...
- **Elite-preferring** → Focus on N ≤ 40 for maximum signal
- **Inclusive-preferring** → Include N ≥ 80 for complete picture
- **Stable across N** → Any N level works, choose based on sample size needs

### For Feature Selection
1. **Check the Feature Behavior Summary** to understand your feature portfolio
2. **Prioritize Stable features** for consistent cross-study comparisons
3. **Use Elite-preferring features** for competitive analysis
4. **Include Inclusive-preferring features** for field effect studies

### For N-Level Selection
1. **Start with Analysis Type Recommendations** based on your research question
2. **Check Statistical Performance Rankings** for data quality considerations
3. **Consider feature behavior** - don't use Elite-preferring features at high N levels
4. **For longitudinal studies**, use N levels where your key features are Stable

### Interpreting Your Results

#### When you see:
- **High elite-preferring count**: Competitive dynamics dominate your race characteristics
- **High inclusive-preferring count**: Field effects and mass participation patterns are important  
- **High stable count**: Your features are robust measurement tools
- **Balanced distribution**: Your feature set captures multiple aspects of race dynamics

This sophisticated framework ensures that N-level selection is guided by both statistical rigor and practical analytical needs, moving beyond simple "one-size-fits-all" recommendations to research-question-specific guidance.