# Implementation Plan: Form and Team Strength Features

## Overview

Add two new feature categories to improve prediction on hilly/breakaway races:
1. **Rider Form Features** - Recent performance indicating current fitness/confidence
2. **Team Strength Features** - Quality distribution of teammates in the race

---

## 1. Rider Form Features

### Constraints (Critical for avoiding data leakage)

1. **Same-year only**: Recent races must be in the same calendar year as the target race
2. **Max 3 months**: Recent races can't be older than 90 days before the target race
3. **GC date handling**: For GC competitions, use Stage 1/Prologue date as the "effective date" to avoid including stage results from the same race
4. **Career-to-date**: For form delta calculations, career average must only include races BEFORE the target race

### Features to Implement

| Feature | Description | Calculation |
|---------|-------------|-------------|
| `form_recent_avg_bucket` | Average bucket in last 5 races | Mean of place_bucket for qualifying recent races |
| `form_recent_best_bucket` | Best result in last 5 races | Min of place_bucket for qualifying recent races |
| `form_recent_count` | Number of recent races found | Count (0-5), useful for imputation decisions |
| `form_delta` | Recent form vs career-to-date | `form_recent_avg_bucket - career_avg_bucket_to_date` |
| `form_profile_recent_avg` | Recent form in similar race types | Avg bucket in recent hilly/breakaway/sprint/etc. races |
| `days_since_last_race` | Freshness indicator | Days between target race and most recent race |

### Implementation Logic

```python
def get_recent_races(rider_id, target_date, target_year, competition_type):
    """
    Get qualifying recent races for form calculation.

    Rules:
    - Same year as target race
    - Within 90 days before target date
    - For GC targets: exclude stages from same race
    - Max 5 races
    """

    # Calculate effective date for GC races
    if competition_type == 'gc':
        # Use race start date (Stage 1 / Prologue) instead of GC date
        effective_date = get_race_start_date(race_id)
    else:
        effective_date = target_date

    min_date = max(
        effective_date - timedelta(days=90),
        date(target_year, 1, 1)  # Same year constraint
    )

    # Query recent races
    recent = query("""
        SELECT place_bucket, competition_date, race_dominant_profile
        FROM rider_results rr
        JOIN competition_field_features cff ON rr.competition_id = cff.competition_id
        WHERE rr.rider_id = ?
        AND cff.competition_date >= ?
        AND cff.competition_date < ?
        AND NOT (same_race_exclusion)  -- For GC, exclude stages from this race
        ORDER BY cff.competition_date DESC
        LIMIT 5
    """, [rider_id, min_date, effective_date])

    return recent
```

### GC Date Handling Detail

For GC competitions:
- GC result dates often match the final stage date
- We need to use the **race start date** (Stage 1 or Prologue) as the effective date
- This prevents including any stage results from the current race in form calculations

```sql
-- Get race start date for a GC competition
SELECT MIN(c.date) as race_start_date
FROM competitions c
WHERE c.race_id = (SELECT race_id FROM competitions WHERE id = target_competition_id)
```

---

## 2. Team Strength Features

### Features to Implement

For each rider, calculate the quality distribution of their **teammates** in the current race (excluding the rider themselves).

| Feature | Description |
|---------|-------------|
| `team_quality_mean` | Mean of teammates' career avg bucket |
| `team_quality_median` | Median of teammates' career avg bucket |
| `team_quality_std` | Std dev of teammates' career avg bucket |
| `team_quality_min` | Best teammate (lowest avg bucket) |
| `team_quality_max` | Worst teammate (highest avg bucket) |
| `team_quality_p25` | 25th percentile of teammates |
| `team_quality_p75` | 75th percentile of teammates |
| `team_size` | Number of teammates in race |
| `team_depth` | Count of teammates with avg bucket < 4 |

### Implementation Logic

```python
def get_team_features(rider_id, competition_id, team_id):
    """
    Calculate team strength features for a rider.
    Uses career-to-date avg bucket for each teammate.
    """

    # Get all teammates in this race (excluding the rider)
    teammates = query("""
        SELECT rcs.stage_avg_bucket as career_avg
        FROM rider_results rr
        JOIN rider_competition_snapshots rcs
            ON rr.rider_id = rcs.rider_id
            AND rr.competition_id = rcs.competition_id
        WHERE rr.competition_id = ?
        AND rr.team_id = ?
        AND rr.rider_id != ?  -- Exclude self
    """, [competition_id, team_id, rider_id])

    if len(teammates) == 0:
        return default_team_features()

    values = teammates['career_avg'].values

    return {
        'team_quality_mean': np.mean(values),
        'team_quality_median': np.median(values),
        'team_quality_std': np.std(values),
        'team_quality_min': np.min(values),
        'team_quality_max': np.max(values),
        'team_quality_p25': np.percentile(values, 25),
        'team_quality_p75': np.percentile(values, 75),
        'team_size': len(values),
        'team_depth': np.sum(values < 4)
    }
```

---

## 3. Data Pipeline Integration

### Option A: Precompute and Store

Add new tables to store precomputed features:

```sql
CREATE TABLE rider_form_features (
    rider_id INTEGER,
    competition_id INTEGER,
    form_recent_avg_bucket REAL,
    form_recent_best_bucket REAL,
    form_recent_count INTEGER,
    form_delta REAL,
    form_profile_recent_avg REAL,
    days_since_last_race INTEGER,
    PRIMARY KEY (rider_id, competition_id)
);

CREATE TABLE rider_team_features (
    rider_id INTEGER,
    competition_id INTEGER,
    team_quality_mean REAL,
    team_quality_median REAL,
    team_quality_std REAL,
    team_quality_min REAL,
    team_quality_max REAL,
    team_quality_p25 REAL,
    team_quality_p75 REAL,
    team_size INTEGER,
    team_depth INTEGER,
    PRIMARY KEY (rider_id, competition_id)
);
```

### Option B: Compute on the fly in feature engineering

Add to `feature_engineering.py`:
- New methods in `FeatureEngineer` class
- Compute during `fit_transform()` / `transform()`

**Recommendation**: Option A (precompute) for form features due to the complex date queries. Option B could work for team features since they're simpler.

---

## 4. Imputation Strategy

### Form Features

| Condition | Imputation |
|-----------|------------|
| No recent races (form_recent_count = 0) | Use career-to-date avg, set form_delta = 0 |
| 1-2 recent races | Use available data, flag as low confidence |
| days_since_last_race > 90 | Set to 90 (cap), indicates rider is rusty |

### Team Features

| Condition | Imputation |
|-----------|------------|
| No teammates found | Use field averages as proxy |
| Small team (1-2 teammates) | Use available data, set std = 0 |

---

## 5. File Changes

| File | Changes |
|------|---------|
| `engineering_tools/rider_form_features.py` | NEW: Form feature computation |
| `engineering_tools/rider_team_features.py` | NEW: Team feature computation |
| `prediction_tools/feature_engineering.py` | Add new features to pipeline |
| `prediction_tools/data_pipeline.py` | Load new feature tables |

---

## 6. Validation Plan

### A. Feature Correlation Check

Run correlation analysis on hilly/breakaway races to verify:
- `form_recent_avg_bucket` correlates better than career avg
- `form_delta` adds incremental signal
- Team features add any signal

### B. Model Performance Comparison

Train two models:
1. **Baseline**: Current features
2. **With form/team**: Current + new features

Compare on hilly/breakaway races specifically:
- Top-15 precision
- MAE for top finishers
- Practical success rate

### C. Feature Importance

Check LightGBM feature importance to see if new features are being used.

---

## 7. Implementation Order

1. **Phase 1**: Implement form features with all constraints
   - Create `rider_form_features.py`
   - Handle GC date logic
   - Test on sample races

2. **Phase 2**: Implement team features
   - Create `rider_team_features.py`
   - Compute distribution stats

3. **Phase 3**: Integration
   - Add to feature engineering pipeline
   - Update data pipeline to load new features

4. **Phase 4**: Validation
   - Run correlation analysis
   - Train comparison models
   - Evaluate on hilly/breakaway races

---

## 8. Expected Impact

Based on preliminary analysis:

| Metric | Current | Expected with Form |
|--------|---------|-------------------|
| Hilly/Breakaway Top-15 Precision | ~44% | ~48-50% |
| Form correlation vs career | 0.373 | 0.412 (+10%) |

The form delta feature specifically targets the "surprise winner" problem - riders who are currently outperforming their historical average are more likely to be in the winning break.
