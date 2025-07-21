# Correlation Feature Analysis: Patterns and Quality Metrics Explained

## Overview

The Correlation Feature Analysis examines how rider performance correlates with race features across different percentile cutoffs (30% to 100% of the field) and race types. **This system is now fully aligned with the Race Feature N Analysis approach**, using sophisticated pattern detection, 3-component quality scoring, and comprehensive percentile recommendations to identify the most reliable features for rider performance prediction.

## System Alignment

This analysis system now mirrors the Race Feature N Analysis methodology:
- **6 Pattern Types**: Sophisticated pattern detection beyond simple trends
- **3-Component Quality Scoring**: Equal-weighted scoring replacing arbitrary weights
- **Analysis Type Recommendations**: Elite, Balanced, Inclusive, and Comparative analysis guidance
- **Report Structure**: Consistent markdown reports with detailed recommendations

## Understanding Correlation Types

### 1. Same Type Correlations (`same_type`)

**Definition**: Correlations calculated using only races of the same type as the target race.

**What This Means**:
- GC riders: Correlations based only on GC race features
- Stage race riders: Correlations based only on stage race features  
- One-day riders: Correlations based only on one-day race features

**Use Case**: 
Understanding how riders perform relative to race characteristics within their specialized race format. This provides the most targeted insights for race-specific performance prediction.

---

### 2. Stage + One-Day Correlations (`stage_one_days`)

**Definition**: Correlations calculated using combined stage races and one-day races, excluding GC races.

**What This Means**:
- Combines non-GC racing to understand broader performance patterns
- Excludes GC-specific dynamics like overall classification tactics
- Only calculated for stage and one-day race results

**Use Case**:
Identifying performance patterns that transcend the stage/one-day distinction but remain distinct from GC racing dynamics.

---

### 3. All Races Correlations (`all_races`)

**Definition**: Correlations calculated using the rider's entire racing history across all race types.

**What This Means**:
- Maximum data availability for correlation calculation
- Blends different racing contexts and strategies
- May dilute race-type-specific signals

**Use Case**:
Understanding general rider performance characteristics that apply across all competitive contexts.

## Correlation Pattern Classifications

The system now uses 6 sophisticated pattern types aligned with Race Feature N Analysis:

### 1. Stable Patterns

**Definition**: Features with consistent correlation strength across all percentile levels (low coefficient of variation stability).

**Code Location**: `pattern_classifier.py` - `CorrelationPatternClassifier.classify_pattern()`
```python
if cv_values is not None:
    cv_stability = np.std(cv_values)
    is_stable = cv_stability < 0.1
else:
    is_stable = np.std(correlations) < self.stability_threshold
```

**Detection Criteria**:
- CV stability (standard deviation) < 0.1 OR correlation stability < 0.02
- Consistent predictive power across all percentile levels

**What This Means**:
- The feature's predictive relationship with rider performance remains constant
- Reliable for performance prediction regardless of competitive level analyzed
- Represents fundamental performance relationships that scale consistently

**Example Use Case**:
If `winning_time` shows stable correlations, it means a rider's ability to perform well in races with fast winning times is consistent whether you're analyzing elite fields or broader participant pools.

---

### 2. Dilution Patterns

**Definition**: Features where correlation strength decreases as more riders are included (correlation weakens with broader inclusion).

**Code Location**: `pattern_classifier.py`
```python
# Check for Dilution pattern (correlation weakens with more riders)
if slope < -self.trend_slope_threshold and r_value < -self.trend_r_threshold:
    return 'dilution'
```

**Detection Criteria**:
- Negative trend slope < -0.001 
- Strong trend correlation (|r-value|) > 0.7
- Correlation strength decreases with higher percentiles

**What This Means**:
- The feature is most predictive for elite-focused analysis
- Including more riders dilutes the predictive signal
- Represents elite-specific performance relationships

**Example Use Case**:
If `selection_metric` shows a dilution pattern, it means this feature is most valuable for predicting performance when analyzing competitive fields, but loses predictive power when including recreational participants.

---

### 3. Concentration Patterns

**Definition**: Features where correlation strength increases as more riders are included (correlation strengthens with broader inclusion).

**Code Location**: `pattern_classifier.py`
```python
# Check for Concentration pattern (correlation strengthens with more riders)
if slope > self.trend_slope_threshold and r_value > self.trend_r_threshold:
    return 'concentration'
```

**Detection Criteria**:
- Positive trend slope > 0.001
- Strong trend correlation (r-value) > 0.7
- Correlation strength increases with higher percentiles

**What This Means**:
- The feature becomes more predictive when including lower-performing riders
- Elite-only analysis may underestimate the feature's importance
- The relationship strengthens with field depth and mass participation effects

**Example Use Case**:
If `abandon_ratio` shows a concentration pattern, it suggests that the feature becomes more predictive of rider performance when you include riders beyond just the elite level, possibly because abandonment patterns are more varied across skill levels.

---

### 4. Threshold Patterns

**Definition**: Features that show sudden, significant changes in correlation strength at specific percentile levels.

**Code Location**: `pattern_classifier.py` - `detect_threshold` method
```python
def detect_threshold(self, correlations: np.ndarray, percentiles: np.ndarray) -> Tuple[bool, int]:
    # Calculate relative changes between consecutive percentiles
    relative_changes = []
    for i in range(1, len(correlations)):
        if abs(correlations[i-1]) > 0.01:
            rel_change = abs((correlations[i] - correlations[i-1]) / correlations[i-1])
            relative_changes.append((rel_change, percentiles[i]))
```

**Detection Logic**:
- Identifies relative changes >30% in correlation strength between consecutive percentiles
- Returns the percentile where the largest change occurs

**What This Means**:
- There's a specific competitive level where the feature's predictive behavior fundamentally changes
- The threshold often represents the boundary between "competitive" and "recreational" participants
- Analysis strategy should consider this breakpoint

**Example Use Case**:
If `gini_coefficient` has a threshold at 60%, it means the inequality measure's correlation with performance behaves differently when analyzing the top 60% vs. including more riders.

---

### 5. Bimodal Patterns

**Definition**: Features where the correlation distribution shifts or shows two distinct peaks across percentile levels.

**Code Location**: `pattern_classifier.py` - `test_bimodality` method
```python
def test_bimodality(self, correlations: np.ndarray) -> bool:
    # Find peaks (local maxima)
    peaks = []
    for i in range(1, len(abs_corrs) - 1):
        if abs_corrs[i] > abs_corrs[i-1] and abs_corrs[i] > abs_corrs[i+1]:
            peaks.append((i, abs_corrs[i]))
```

**Detection Logic**:
- Identifies peaks separated by significant valleys
- A valley <60% of the smaller peak height indicates bimodality

**What This Means**:
- The competitive field splits into distinct groups at certain percentile levels
- May indicate natural breakpoints in rider categories (e.g., professional vs. amateur)
- Suggests different analytical approaches for different percentile ranges

**Example Use Case**:
If `time_gap_evenness_metric` becomes bimodal at 70%, it suggests that when you include riders beyond the 70th percentile, the correlation field naturally separates into two distinct groups with different predictive relationships.

---

### 6. Complex Patterns

**Definition**: Features that don't fit cleanly into other categories or show multiple behavioral patterns.

**Code Location**: `pattern_classifier.py`
```python
# Default to Complex pattern if no clear pattern emerges
return 'complex'
```

**What This Means**:
- The feature exhibits multiple behaviors simultaneously or changes unpredictably
- May require specialized analysis approaches
- Could indicate interaction effects with other variables or non-linear relationships

**Example Use Case**:
A complex feature might show dilution at lower percentile levels but then stabilize at higher percentile levels, making it useful for specific analytical windows but requiring careful interpretation.

---

## Quality Scoring System

### How Quality Scores Are Calculated

**Code Location**: `quality_scorer.py` - `CorrelationQualityScorer.calculate_quality_score()`

The system now uses a **3-component equal-weight scoring system** aligned with Race Feature N Analysis:

#### 1. Correlation Strength Score
```python
# Maximum predictive power across all percentiles
optimal_strength = abs(feature_pattern.get('optimal_strength', 0))
correlation_strength_score = optimal_strength  # Already normalized to [0,1]
```
- Based on the strongest correlation value across all percentiles
- Measures the maximum predictive power of the feature

#### 2. Information Value Score
```python
# Combines discriminative power and monotonicity
correlation_range = feature_pattern.get('correlation_range', 0)
discriminative_power = min(correlation_range * 2, 1.0)
# Monotonicity from trend analysis R² or CV stability
monotonicity = trend_data.get('r_squared', 0) if trend_data else max(0, 1 - cv_stability)
information_value_score = (discriminative_power + monotonicity) / 2
```
- **Discriminative Power**: How much correlation varies across percentiles
- **Monotonicity**: How predictably correlation changes (trend consistency)
- Combined measure of analytical utility

#### 3. Stability Score
```python
# Consistency across percentiles
correlation_stability = feature_pattern.get('correlation_stability', 1.0)
stability_score = max(0, 1 - (correlation_stability * 5))  # Scaled for sensitivity
```
- Lower correlation stability (std dev) means higher stability score
- Rewards features with consistent behavior across percentiles

**Final Quality Score**:
```python
overall_score = np.mean([
    correlation_strength_score,
    information_value_score,
    stability_score
])
```
- **Equal weighting** of all three components (no arbitrary weights)
- Data availability penalty applied if >50% missing data

### Quality Tier Assignments

**Code Location**: `quality_scorer.py` - `assign_quality_tiers()`

Features are automatically assigned to tiers based on their overall quality scores:

#### Tier 1 (High Quality)
- **Characteristics**: High correlation strength, good information value, stable across percentiles
- **Score Range**: Top third of all features
- **Use Case**: Primary features for robust performance prediction and modeling
- **Interpretation**: These features consistently predict rider performance across different competitive contexts

#### Tier 2 (Medium Quality)  
- **Characteristics**: Good in some aspects but may have limitations
- **Score Range**: Middle third of all features
- **Examples**: High strength but lower stability, or stable but moderate correlation strength
- **Use Case**: Secondary features for specialized analysis or validation

#### Tier 3 (Low Quality)
- **Characteristics**: Lower correlation strength, poor information value, or inconsistent patterns
- **Score Range**: Bottom third of all features
- **Issues**: May be noisy, have limited data availability, or show complex/unpredictable behavior
- **Use Case**: Consider for exclusion or use only with careful context and validation

## Percentile Analysis Framework

### Understanding Optimal Percentiles

**Code Location**: `pattern_classifier.py` - `analyze_all_patterns()`

For each feature, the system identifies:

#### Optimal Percentile
- **Definition**: The percentile level (30%, 40%, 50%, etc.) where the feature shows strongest correlation
- **Calculation**: 
```python
optimal_idx = np.argmax(np.abs(mean_corrs))
optimal_percentile = int(percentiles[optimal_idx])
```
- **Use Case**: Indicates the ideal competitive level for analyzing this feature

#### Optimal Strength
- **Definition**: The correlation strength at the optimal percentile
- **Calculation**: `optimal_strength = mean_corrs[optimal_idx]`
- **Use Case**: Quantifies the feature's maximum predictive power

### Percentile Stability Metrics

**Code Location**: `statistics_calculator.py` - `calculate_stability_metrics()`

#### Correlation Stability
```python
correlation_stability = feature_stats['mean_correlation'].std()
```
- **Low values** (< 0.02): Stable pattern classification
- **High values** (> 0.05): Variable performance suggesting dilution, concentration, or complex patterns

#### Coefficient of Variation Stability
```python
cv_stability = feature_stats['cv'].std()
```
- **Low values** (< 0.1): Stable pattern classification (used in pattern detection)
- Measures consistency in relative variability across percentiles

## Percentile Recommendation System

The analysis provides sophisticated recommendations for choosing optimal percentile levels based on your research goals and feature behavior patterns.

### Understanding the Recommendation Categories

#### Analysis Type Recommendations

**Code Location**: `correlation_feature_analyzer.py` - `_recommend_percentiles()`

The system provides percentile-level recommendations tailored to different analytical objectives:

##### Elite Performance Analysis
- **Recommended Percentiles**: [30, 40]
- **Purpose**: Focus on competitive dynamics among top performers
- **When to Use**: Studying elite racing tactics, selection pressure, performance gaps in professional cycling
- **Key Features**: Features that show strong preference for elite focus (dilution patterns, low optimal percentiles)

##### Balanced Performance Analysis  
- **Recommended Percentiles**: [50, 60, 70]
- **Purpose**: Compromise between competitive signal and field representation
- **When to Use**: General rider characterization, comparing events with different competitive depths
- **Key Features**: Features that are stable across percentile levels

##### Inclusive Performance Analysis
- **Recommended Percentiles**: [80, 90, 100] 
- **Purpose**: Understanding full field dynamics including recreational participants
- **When to Use**: Mass participation events, understanding dropout patterns, field effects
- **Key Features**: Features that perform optimally with broader inclusion (concentration patterns)

##### Comparative Analysis
- **Recommended Percentiles**: [30, 60, 90]
- **Purpose**: Strategic sampling across competitive levels
- **When to Use**: Multi-level studies, understanding how competitive depth affects rider performance patterns

#### Statistical Performance Rankings

**Code Location**: `correlation_feature_analyzer.py` - percentile_analysis

##### Best Peak Performance
- **Definition**: Percentile levels where the most features achieve their highest correlations
- **Interpretation**: These percentile levels maximize feature predictive power
- **Use Case**: When you need maximum discriminative power for rider performance prediction

##### Most Consistent Performance  
- **Definition**: Percentile levels with lowest coefficient of variation across features
- **Calculation**: `1 - (std_scores / mean_scores)` for each percentile level
- **Use Case**: When you need reliable, stable measurements across different competitive contexts

##### Highest Average Correlations
- **Definition**: Percentile levels with highest mean correlation strength across all features
- **Use Case**: General-purpose analysis when you want overall strong predictive performance

### Feature Behavior Classification

**Code Location**: `correlation_feature_analyzer.py` - feature categorization

#### Elite-Preferring Features
- **Criteria**: Dilution pattern OR optimal percentile ≤ 40
- **Meaning**: These features lose predictive power when including lower-tier riders
- **Examples**: Selection-based features, competitive intensity measures
- **Interpretation**: Elite competitive dynamics are fundamentally different for these features

#### Inclusive-Preferring Features  
- **Criteria**: Concentration pattern OR optimal percentile ≥ 80
- **Meaning**: These features gain predictive power from broader field inclusion
- **Examples**: Participation-based features, field depth measures
- **Interpretation**: Full field effects matter for these characteristics

#### Stable Across Percentiles Features
- **Criteria**: Stable pattern classification
- **Meaning**: Robust measurements regardless of competitive level analyzed
- **Interpretation**: Fundamental performance relationships that scale consistently

### Traditional Sets (Backward Compatibility)

For users familiar with the original approach:

- **Minimal Set**: [30, 50, 80] - Strategic sampling across competitive levels
- **Balanced Set**: [30, 40, 60, 80, 90] - Comprehensive coverage with key transition points
- **Comprehensive Set**: All percentile levels [30, 40, 50, 60, 70, 80, 90, 100]

## Practical Usage Guidelines

### For Performance Prediction Models

#### Feature Selection Strategy
1. **Start with Tier 1 features** for core model components
2. **Consider pattern types**:
   - Use **Stable** features for robust baseline models
   - Add **Dilution** features for elite-focused analysis
   - Add **Concentration** features for mass-participation analysis
   - Use **Threshold** and **Bimodal** features with care for their specific percentile ranges
   - Avoid **Complex** features unless you understand their specific behaviors

#### Percentile Selection Strategy
1. **Match analysis depth to use case**:
   - **Elite analysis** (30-40%): Focus on dilution pattern features
   - **General analysis** (50-70%): Use stable pattern features  
   - **Inclusive analysis** (80-100%): Include concentration pattern features

### For Rider Performance Characterization

#### Understanding Correlation Contexts
- **Same Type correlations**: Use for format-specific insights (GC with GC, stage with stage, etc.)
- **Stage + One-Day correlations**: Compare to understand broader non-GC performance patterns
- **All Races correlations**: Use for general performance characteristics across all contexts

#### Comparative Analysis
1. **Across correlation types**: Compare how features behave differently in same-type vs. mixed-type contexts
2. **Across percentiles**: Identify which competitive levels provide the strongest predictive signals
3. **Across competition types**: Understand format-specific vs. general performance patterns

### For Research Design

#### Study Population Considerations
- **Elite-focused studies**: Prioritize features with **Dilution** patterns
- **Mass participation studies**: Include features with **Concentration** patterns  
- **Cross-population studies**: Focus on **Stable** features for comparison validity
- **Transition studies**: Use **Threshold** and **Bimodal** features to understand competitive breakpoints

#### Validation Strategies
1. **Check pattern classifications** align with research hypotheses
2. **Use recommended percentile sets** based on your analysis type
3. **Cross-validate** across different correlation types when applicable
4. **Consider feature behavior summaries** when interpreting results

## Data Availability Analysis

### Understanding Data Completeness

**Code Location**: `correlation_feature_analyzer.py` - analysis pipeline

#### By Percentile Analysis
For each percentile level, the system tracks:
- **Average sample size**: Number of correlation values available
- **Features with data**: Count of features with non-null correlations
- **Data completeness**: Percentage of expected correlations that are available

#### Data Availability Integration
Data availability is now integrated into the quality scoring system:
- **Quality penalty**: Applied when >50% of data is missing
- **Pattern reliability**: Low data availability may indicate insufficient data patterns
- **Tier assignment**: Features with poor data availability are penalized in tier assignments

#### Interpretation Guidelines

##### High Data Availability (> 90%)
- **Meaning**: Robust correlation calculations with large sample sizes
- **Reliability**: High confidence in correlation estimates and pattern detection
- **Use Case**: Preferred for primary analysis and model building

##### Moderate Data Availability (70-90%)
- **Meaning**: Good sample sizes but some data limitations
- **Reliability**: Generally reliable with appropriate caution in pattern interpretation
- **Use Case**: Suitable for secondary analysis with acknowledgment of limitations

##### Low Data Availability (< 70%)
- **Meaning**: Limited sample sizes or significant missing data
- **Reliability**: Correlations and patterns may be unstable or biased
- **Pattern Impact**: May result in "Complex" or unreliable pattern classifications
- **Use Case**: Use with extreme caution or consider exclusion from primary analysis

## Interpreting Report Outputs

### Quality Tier Distributions
- **High Tier 1 count**: Your feature set contains many reliable predictors with strong, stable correlations
- **Balanced distribution**: Good mix of primary and supporting features across all quality levels
- **Many Tier 3 features**: Consider feature set refinement or understand their specific use cases

### Pattern Classification Results
- **Many Stable features**: Robust feature set suitable for diverse analyses across competitive levels
- **Many Dilution features**: Feature set optimized for elite performance analysis
- **Many Concentration features**: Feature set benefits from inclusive field analysis
- **Threshold/Bimodal features**: Specialized features with specific optimal percentile ranges
- **Many Complex features**: May need specialized analytical approaches or indicate interaction effects

### Percentile Recommendation Usage
- **Elite Performance Analysis recommended**: Your feature set works best for competitive analysis
- **Inclusive Performance Analysis recommended**: Your features benefit from broader field inclusion
- **Balanced Performance Analysis recommended**: Your features work well across competitive levels
- **High statistical consistency**: Features provide reliable measurements across percentiles

### Feature Behavior Summary Interpretation
- **High elite-preferring count**: Competitive dynamics dominate your correlation patterns
- **High inclusive-preferring count**: Field effects and mass participation patterns are important  
- **High stable count**: Your features are robust measurement tools across competitive contexts
- **Balanced distribution**: Your feature set captures multiple aspects of rider performance dynamics

## Advanced Interpretation Guidelines

### When you see:
- **High correlation strength but low stability**: Feature provides strong signals but only in specific competitive contexts
- **High stability but moderate strength**: Feature provides consistent but limited predictive power
- **High information value**: Feature shows good discriminative ability and predictable trends
- **Threshold patterns**: Consider separate analysis for different competitive levels
- **Bimodal patterns**: Your data may contain distinct competitive populations

### For Longitudinal Studies
1. **Prioritize Stable features** for consistent cross-study comparisons
2. **Document percentile recommendations** for reproducible analysis approaches
3. **Consider feature behavior changes** over time or across different datasets
4. **Use Analysis Type Recommendations** as starting points for comparative studies

This comprehensive framework enables data-driven decisions about feature selection, analysis scope, and model building strategy based on sophisticated empirical correlation pattern analysis rather than assumptions about feature utility.