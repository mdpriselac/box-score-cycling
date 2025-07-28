# Race Feature Gradient Analysis - Conceptual Overview

This document provides a comprehensive explanation of the gradient statistics used in race kind classification, including what each feature measures and how to interpret the slope, volatility, and monotonicity metrics.

## Overview of Gradient Analysis

**Gradient Direction**: All calculations proceed from **fewer finishers (top 10%) to more finishers (up to 100%)**. This means we start with elite performers and progressively include more of the field.

**Key Metrics**:
- **Slope**: Overall trend as we include more finishers
- **Volatility**: Variability/instability in step-to-step changes
- **Monotonicity**: Consistency of directional change (-1 = always decreasing, +1 = always increasing, 0 = mixed)

---

## Statistical Features

### 1. nth_percentile_gap_5
**What it measures**: Time gap from the race winner to the 5th percentile finisher, measured relative to different proportions of the field.

**Example**: When looking at top 20% of finishers (n=5), the 5th percentile gap tells you the time difference between 1st place and the person who finished at the 5th percentile of that top 20% group.

**Interpretation (10% → 100% direction)**:
- **Positive Slope**: Time gaps increase as we include more finishers → selective race where early gaps are small but grow as field expands
- **Negative Slope**: Time gaps decrease as we include more finishers → early selection with large initial gaps that compress relatively
- **High Volatility**: Erratic gap development, unpredictable selection patterns
- **Low Volatility**: Smooth, consistent gap progression
- **High Monotonicity (+)**: Gaps consistently increase with field size
- **Low Monotonicity (-)**: Gaps consistently decrease with field size
- **Mixed Monotonicity (0)**: Gap development changes direction multiple times

**Reverse Direction (100% → 10%)**:
- **Positive Slope**: Would become negative (gaps shrink as we focus on elites)
- **Negative Slope**: Would become positive (gaps expand as we focus on elites)
- **Volatility**: Same magnitude, represents same pattern instability
- **Monotonicity**: Sign would flip (+ becomes -, - becomes +)

### 2. nth_percentile_gap_25
**What it measures**: Time gap from winner to 25th percentile finisher across different field proportions.

**Example**: In a 100-rider race looking at top 50%, the 25th percentile gap shows time difference between winner and the rider at 25th percentile of those top 50 riders.

**Interpretation (10% → 100% direction)**:
- **Positive Slope**: Indicates progressive selection where 25th percentile gaps grow with field size → races with sustained selection pressure
- **Negative Slope**: Early large gaps that compress relatively → races with early decisive selection
- **High Volatility**: Inconsistent selection patterns affecting mid-strong performers
- **Low Volatility**: Predictable, steady selection affecting 25th percentile riders
- **Positive Monotonicity**: Consistent gap growth → progressive selection race
- **Negative Monotonicity**: Consistent gap compression → early selection race

**Reverse Direction (100% → 10%)**:
- Slopes flip sign, monotonicity flips, volatility unchanged
- Focus shifts from "how gaps develop with more riders" to "how gaps compress to elites"

### 3. nth_percentile_gap_50
**What it measures**: Time gap from winner to median (50th percentile) finisher across field proportions.

**Example**: Shows how the time gap to the "middle performer" in your analysis window changes as you include more of the field.

**Interpretation (10% → 100% direction)**:
- **Large Positive Slope**: Major indicator of mountain/selective stages where median gaps grow dramatically
- **Small/Negative Slope**: Bunch racing where median times stay compressed
- **High Volatility**: Unpredictable mid-field selection (tactical racing)
- **Low Volatility**: Steady, predictable mid-field behavior
- **Strong Positive Monotonicity**: Clear progressive selection affecting half the field
- **Strong Negative Monotonicity**: Early elimination pattern affecting median performers

**Reverse Direction (100% → 10%)**:
- Same flip patterns as above
- Emphasis shifts to "how much faster are elites than median" vs "how much slower is median than elites"

### 4. variance_absolute
**What it measures**: Absolute variance of finishing times within different proportions of the field.

**Example**: At top 30%, measures how spread out finishing times are among those top 30% finishers (in actual time units).

**Interpretation (10% → 100% direction)**:
- **Positive Slope**: Variance increases with field size → selective race where time spread grows
- **Negative Slope**: Variance decreases with field size → tight elite group, but rest of field compressed
- **High Volatility**: Inconsistent spread patterns, unpredictable time distributions
- **Low Volatility**: Steady, predictable variance development
- **Positive Monotonicity**: Consistently increasing spread → progressive selection
- **Negative Monotonicity**: Consistently decreasing spread → early separation, then bunching

**Reverse Direction (100% → 10%)**:
- Focus shifts from "how spread increases with more riders" to "how much tighter elite groups are"
- Mountain stages would show large negative slopes (variance decreases dramatically as we focus on elites)

### 5. variance_normalized
**What it measures**: Variance normalized by mean finishing time, showing relative spread independent of race duration.

**Example**: Allows comparison of time spread patterns between 3-hour and 6-hour races on the same scale.

**Interpretation**: Same as variance_absolute, but focuses on relative rather than absolute time spreads.
- **High normalized variance**: Large relative time differences regardless of race length
- **Low normalized variance**: Tight relative groupings regardless of race length

### 6. skewness_absolute
**What it measures**: Asymmetry of finishing time distribution within field proportions.

**Example**: Positive skew = long tail of slower finishers; Negative skew = tight grouping with few very fast outliers.

**Interpretation (10% → 100% direction)**:
- **Positive Slope**: Distribution becomes more right-skewed with more finishers → progressive tail development
- **Negative Slope**: Distribution becomes more left-skewed with more finishers → early outliers, then compression
- **High Volatility**: Erratic distribution shape changes
- **Low Volatility**: Smooth distribution evolution
- **Positive Monotonicity**: Consistently developing positive skew → progressive selection pattern
- **Negative Monotonicity**: Consistently developing negative skew → early breakaway pattern

**Reverse Direction (100% → 10%)**:
- Focus shifts to how distribution shapes change when focusing on elites vs including slower riders

### 7. skewness_normalized
**What it measures**: Same as absolute skew but standardized, allowing cross-race comparisons.

**Interpretation**: Same patterns as skewness_absolute but on standardized scale.

### 8. kurtosis_absolute
**What it measures**: "Peakedness" or concentration of finishing times around the mean within field proportions.

**Example**: High kurtosis = very concentrated times with few outliers; Low kurtosis = more evenly distributed times.

**Interpretation (10% → 100% direction)**:
- **Positive Slope**: Distribution becomes more peaked/concentrated → field bunching as more riders included
- **Negative Slope**: Distribution becomes flatter/more spread → increasing time diversity
- **High Volatility**: Erratic concentration patterns
- **Low Volatility**: Smooth concentration changes
- **Positive Monotonicity**: Consistently increasing concentration → progressive bunching
- **Negative Monotonicity**: Consistently decreasing concentration → progressive spreading

**Reverse Direction (100% → 10%)**:
- Mountain stages would show high positive slopes (distribution becomes very peaked when focusing on elites only)

### 9. kurtosis_normalized
**What it measures**: Standardized kurtosis allowing cross-race comparisons.

**Interpretation**: Same as kurtosis_absolute on standardized scale.

### 10. gini_coefficient
**What it measures**: Inequality measure of time gaps, borrowed from economics (0 = perfect equality, 1 = maximum inequality).

**Example**: Gini near 0 = all riders finish very close together; Gini near 1 = huge time gaps between riders.

**Interpretation (10% → 100% direction)**:
- **Positive Slope**: Inequality increases with field size → selective race creating larger gaps
- **Negative Slope**: Inequality decreases with field size → elite competition with main field compression
- **High Volatility**: Inconsistent inequality patterns
- **Low Volatility**: Predictable inequality development
- **Positive Monotonicity**: Consistently increasing inequality → progressive selection
- **Negative Monotonicity**: Consistently decreasing inequality → early selection then compression

**Reverse Direction (100% → 10%)**:
- Sprint stages would show high negative slopes (inequality drops dramatically when focusing only on elites)

### 11. clumpiness_score
**What it measures**: How clustered or bunched finishing times are within field proportions.

**Example**: High clumpiness = riders finishing in tight groups; Low clumpiness = evenly spread finishing times.

**Interpretation (10% → 100% direction)**:
- **Positive Slope**: More clumping as field size increases → progressive group formation
- **Negative Slope**: Less clumping as field size increases → elite separation from main field
- **High Volatility**: Erratic group formation patterns
- **Low Volatility**: Predictable clumping behavior
- **Positive Monotonicity**: Consistently increasing clumpiness → progressive bunching
- **Negative Monotonicity**: Consistently decreasing clumpiness → progressive spreading

**Reverse Direction (100% → 10%)**:
- Focus shifts from "how groups form with more riders" to "how tight elite groups are"

### 12. selection_metric
**What it measures**: Quantified measure of selection pressure within different field proportions.

**Example**: High selection = large time gaps indicating strong competitive pressure; Low selection = tight times indicating weak selection pressure.

**Interpretation (10% → 100% direction)**:
- **Positive Slope**: Selection pressure increases with field size → progressive race difficulty
- **Negative Slope**: Selection pressure decreases with field size → elite battle with compressed main field
- **High Volatility**: Inconsistent selection patterns
- **Low Volatility**: Steady selection pressure development
- **Positive Monotonicity**: Consistently increasing selection → progressive difficulty
- **Negative Monotonicity**: Consistently decreasing selection → early difficulty then easing

**Reverse Direction (100% → 10%)**:
- Mountain stages would show large negative slopes (selection drops dramatically when focusing only on elites)

### 13. biggest_group_metric
**What it measures**: Size and behavior of the largest group finishing together within field proportions.

**Example**: In sprints, biggest group might be 80% of top finishers; In mountains, might be only 5% of top finishers.

**Interpretation (10% → 100% direction)**:
- **Positive Slope**: Largest group gets relatively bigger → progressive bunching
- **Negative Slope**: Largest group gets relatively smaller → progressive fragmentation
- **High Volatility**: Erratic group size patterns → tactical racing with changing dynamics
- **Low Volatility**: Predictable group size evolution
- **Positive Monotonicity**: Consistently growing groups → bunching race
- **Negative Monotonicity**: Consistently fragmenting groups → selective race

**Reverse Direction (100% → 10%)**:
- Sprint stages would show high negative slopes (biggest group shrinks dramatically when focusing on elites)
- Crosswind stages might show high volatility in either direction (group dynamics change unpredictably)

---

## Practical Interpretation Guide

### Race Type Signatures:

**Sprint Stages**:
- Low percentile gap slopes (minimal gap development)
- Low variance slopes (tight groupings remain tight)
- High biggest group metrics (large groups throughout)
- Low selection metric slopes (minimal selection pressure)

**Mountain Stages**:
- High percentile gap slopes (major gap development)  
- High variance slopes (increasing time spreads)
- Low biggest group metrics (small groups)
- High selection metric slopes (increasing selection pressure)

**Crosswind/Tactical Stages**:
- High volatility across multiple metrics (erratic patterns)
- Mixed monotonicity (changing dynamics)
- Variable biggest group metrics (group fragmentation/reformation)

**Breakaway Stages**:
- Negative slopes initially, then positive (early separation, then compression)
- High early volatility, then stabilization
- Mixed monotonicity patterns

### Key Relationships:
- **Slope magnitude** indicates overall race selectivity
- **Volatility** indicates tactical complexity/unpredictability  
- **Monotonicity** indicates consistency of race dynamics
- **Feature combinations** create unique race signatures

This framework allows systematic classification of race types based on how statistical patterns evolve as we analyze different proportions of the finishing field.