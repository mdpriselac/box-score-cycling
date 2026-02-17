# Feature Pre-computation for Race Predictions

This document describes the pre-computed feature tables used for cycling race prediction algorithms.

## Overview

The feature pre-computation system creates training data for predicting race outcomes by:
1. Processing historical race results chronologically
2. Maintaining running statistics for each rider
3. Creating "snapshots" of rider state at each competition (using only prior races)
4. Aggregating field-level statistics for each competition

**Key principle**: Each snapshot represents a rider's state *going into* a race, not including that race's result. This prevents data leakage in training.

---

## Table Structures

### 1. `rider_competition_snapshots`

Stores the state of each rider at each competition they participated in. This is the primary table for individual rider predictions.

| Column | Type | Description |
|--------|------|-------------|
| `rider_id` | INTEGER | Unique rider identifier |
| `competition_id` | INTEGER | Unique competition identifier |
| `rider_name` | TEXT | Rider's name |
| `age` | INTEGER | Rider's age at this race |
| `team_bib` | INTEGER | Team bib number (1-20+) |
| `personal_bib` | INTEGER | Personal bib within team (1-9) |
| `races_career` | INTEGER | Total races prior to this one |
| `races_this_year` | INTEGER | Races in current calendar year prior to this one |
| `stage_avg_bucket` | REAL | Average bucket in stage races (0-7 scale) |
| `stage_count` | INTEGER | Number of prior stage races |
| `one_day_avg_bucket` | REAL | Average bucket in one-day races |
| `one_day_count` | INTEGER | Number of prior one-day races |
| `gc_avg_bucket` | REAL | Average bucket in GC competitions |
| `gc_count` | INTEGER | Number of prior GC competitions |
| `wt_avg_bucket` | REAL | Average bucket in WorldTour races |
| `wt_count` | INTEGER | Number of prior WorldTour races |
| `pro_avg_bucket` | REAL | Average bucket in Pro Series races |
| `pro_count` | INTEGER | Number of prior Pro Series races |
| `d1_avg_bucket` | REAL | Average bucket in Division 1 races |
| `d1_count` | INTEGER | Number of prior Division 1 races |
| `sprint_avg_bucket` | REAL | Profile-weighted avg bucket for sprint races |
| `mountain_avg_bucket` | REAL | Profile-weighted avg bucket for mountain races |
| `hilly_avg_bucket` | REAL | Profile-weighted avg bucket for hilly races |
| `rolling_avg_bucket` | REAL | Profile-weighted avg bucket for rolling races |
| `breakaway_avg_bucket` | REAL | Profile-weighted avg bucket for breakaway races |
| `time_trial_avg_bucket` | REAL | Profile-weighted avg bucket for time trials |
| `best_profile` | TEXT | Profile type where rider performs best |

**Primary Key**: (`rider_id`, `competition_id`)

### 2. `competition_field_features`

Stores aggregate statistics about the field for each competition. Used for field-level predictions and contextualizing individual predictions.

| Column | Type | Description |
|--------|------|-------------|
| `competition_id` | INTEGER | Unique competition identifier (PK) |
| `competition_name` | TEXT | Competition name (e.g., "Stage: 05") |
| `competition_date` | TEXT | Date in YYYY-MM-DD format |
| `competition_type` | TEXT | Type: 'stage', 'one_day', or 'gc' |
| `race_category` | TEXT | Category: 'wt', 'pro', or 'd1' |
| `field_size` | INTEGER | Number of riders in the field |
| `experience_mean` | REAL | Mean prior races across field |
| `experience_median` | REAL | Median prior races |
| `experience_std` | REAL | Standard deviation of prior races |
| `experience_min` | REAL | Minimum prior races (least experienced) |
| `experience_max` | REAL | Maximum prior races (most experienced) |
| `experience_p25` | REAL | 25th percentile of experience |
| `experience_p75` | REAL | 75th percentile of experience |
| `bucket_mean` | REAL | Mean historical bucket across field (lower = stronger) |
| `bucket_median` | REAL | Median historical bucket |
| `bucket_std` | REAL | Standard deviation of historical bucket |
| `bucket_min` | REAL | Best (lowest) historical bucket in field |
| `bucket_max` | REAL | Worst (highest) historical bucket in field |
| `bucket_p25` | REAL | 25th percentile of historical bucket |
| `bucket_p75` | REAL | 75th percentile of historical bucket |
| `sprinter_count` | INTEGER | Riders whose best profile is 'sprint' |
| `climber_count` | INTEGER | Riders whose best profile is 'mountain' |
| `hilly_specialist_count` | INTEGER | Riders whose best profile is 'hilly' |
| `rolling_specialist_count` | INTEGER | Riders whose best profile is 'rolling' |
| `breakaway_specialist_count` | INTEGER | Riders whose best profile is 'breakaway' |
| `time_trialist_count` | INTEGER | Riders whose best profile is 'time_trial' |
| `unknown_profile_count` | INTEGER | Riders with insufficient data for profile |
| `race_sprint_score` | REAL | Race profile score for sprint (0-1) |
| `race_mountain_score` | REAL | Race profile score for mountain (0-1) |
| `race_hilly_score` | REAL | Race profile score for hilly (0-1) |
| `race_rolling_score` | REAL | Race profile score for rolling (0-1) |
| `race_breakaway_score` | REAL | Race profile score for breakaway (0-1) |
| `race_time_trial_score` | REAL | Race profile score for time trial (0-1) |
| `race_dominant_profile` | TEXT | Dominant profile type for this race |

### 3. `rider_features_running`

Internal table storing the running state for each rider. Used for incremental updates and checkpoint recovery. Not typically used directly for ML.

### 4. `feature_computation_checkpoint`

Tracks the last processed competition for resume capability.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Always 1 (single row) |
| `last_processed_date` | TEXT | Date of last processed competition |
| `last_processed_competition_id` | INTEGER | ID of last processed competition |
| `processed_competitions` | INTEGER | Count of processed competitions |
| `updated_at` | TEXT | Timestamp of last update |

---

## Bucket Scale

All bucket values use the same 0-7 scale (lower is better):

| Bucket | Place Range | Description |
|--------|-------------|-------------|
| 0 | 1st | Winner |
| 1 | 2nd-3rd | Podium |
| 2 | 4th-5th | Top 5 |
| 3 | 6th-15th | Top 15 |
| 4 | 16th-30th | Top 30 |
| 5 | 31st-50th | Top 50 |
| 6 | 51st+ | Finisher |
| 7 | DNF/DNS/OTL | Did not finish |

The bucket scale is derived from UCI points distributions, where point gaps decrease exponentially after the winner.

---

## Race Profile Scoring

Each race is classified into profile types based on gradient features of the finishing time distribution:

| Profile | Characteristics |
|---------|-----------------|
| **Sprint** | Late breakdown, bunch finish, low variance growth |
| **Mountain** | No breakdown, high variance growth, selection throughout |
| **Hilly** | Mid-race selection, increasing clumpiness |
| **Rolling** | No breakdown, moderate variance growth |
| **Breakaway** | Early breakdown, fragmented field |
| **Time Trial** | Winning time < 70 minutes |

Profile scores are calculated from:
- `kurtosis_null_percentile`: Point where finishing times become uniformly distributed (breakdown)
- `variance_normalized_slope`: Rate of variance growth in finishing times
- `clumpiness_score_slope`: Rate of change in group formation
- `biggest_group_metric_slope`: Rate of change in largest group size

Each race gets a score (0-1) for each profile type, with scores summing to 1.

---

## Profile-Weighted Bucket Averages

For each rider, profile-specific averages are calculated as weighted means:

```
sprint_avg_bucket = Σ(bucket_i × sprint_score_i) / Σ(sprint_score_i)
```

Where:
- `bucket_i` is the rider's bucket in race i
- `sprint_score_i` is the sprint profile score of race i

This gives more weight to races that strongly match each profile type. A rider's `sprint_avg_bucket` reflects their performance in sprint-like races specifically.

---

## Computation Process

### Chronological Processing

1. **Load all race profiles** - Pre-compute profile scores for every race
2. **Process competitions chronologically** - Maintain temporal ordering
3. **For each competition**:
   - For each rider: capture snapshot (prior state only)
   - For each rider: update running state with this race result
   - Compute field-level aggregates from snapshots
4. **Checkpoint after each batch** - Enable resume on interruption

### Data Integrity

- **No future leakage**: Snapshots contain only data from races prior to the current one
- **Incremental updates**: Running sums/counts enable O(1) updates per race
- **Checkpointing**: Can resume from last completed batch

---

## Usage for ML Training

### Target Variable

We predict **place buckets** (0-7), not raw places. The `rider_results.place_bucket` column is pre-computed:

| Bucket | Place Range |
|--------|-------------|
| 0 | 1st (Winner) |
| 1 | 2nd-3rd (Podium) |
| 2 | 4th-5th (Top 5) |
| 3 | 6th-15th (Top 15) |
| 4 | 16th-30th (Top 30) |
| 5 | 31st-50th (Top 50) |
| 6 | 51st+ (Finisher) |
| 7 | DNF/DNS/OTL |

### Complete Training Data Query

```sql
-- Full training dataset: rider features + field features + race profile + target
SELECT
    -- Rider historical features
    rcs.rider_id,
    rcs.rider_name,
    rcs.age,
    rcs.team_bib,
    rcs.personal_bib,
    rcs.races_career,
    rcs.races_this_year,
    rcs.stage_avg_bucket,
    rcs.stage_count,
    rcs.one_day_avg_bucket,
    rcs.one_day_count,
    rcs.gc_avg_bucket,
    rcs.gc_count,
    rcs.wt_avg_bucket,
    rcs.pro_avg_bucket,
    rcs.d1_avg_bucket,
    rcs.sprint_avg_bucket,
    rcs.mountain_avg_bucket,
    rcs.hilly_avg_bucket,
    rcs.rolling_avg_bucket,
    rcs.breakaway_avg_bucket,
    rcs.time_trial_avg_bucket,
    rcs.best_profile,

    -- Field strength features
    cff.field_size,
    cff.experience_mean,
    cff.experience_std,
    cff.bucket_mean,
    cff.bucket_std,
    cff.bucket_p25,
    cff.bucket_p75,

    -- Field composition
    cff.sprinter_count,
    cff.climber_count,
    cff.hilly_specialist_count,
    cff.time_trialist_count,

    -- Race profile (what kind of race is this?)
    cff.race_sprint_score,
    cff.race_mountain_score,
    cff.race_hilly_score,
    cff.race_rolling_score,
    cff.race_breakaway_score,
    cff.race_time_trial_score,
    cff.race_dominant_profile,

    -- Competition metadata
    cff.competition_id,
    cff.competition_name,
    cff.competition_date,
    cff.competition_type,
    cff.race_category,

    -- TARGET VARIABLE
    rr.place_bucket

FROM rider_competition_snapshots rcs
JOIN competition_field_features cff ON rcs.competition_id = cff.competition_id
JOIN rider_results rr ON rcs.rider_id = rr.rider_id
    AND rcs.competition_id = rr.competition_id
WHERE rcs.races_career >= 10           -- Experienced riders only
AND rr.place_bucket IS NOT NULL        -- Has valid result
AND cff.race_sprint_score IS NOT NULL  -- Has race profile
```

### Filtering Options

```sql
-- By competition type
WHERE cff.competition_type = 'stage'           -- Stage races only
WHERE cff.competition_type = 'one_day'         -- One-day races only
WHERE cff.competition_type = 'gc'              -- GC results only

-- By race category
WHERE cff.race_category = 'wt'                 -- WorldTour only
WHERE cff.race_category IN ('wt', 'pro')       -- Top-tier races

-- By race profile
WHERE cff.race_dominant_profile = 'sprint'     -- Sprint stages
WHERE cff.race_mountain_score > 0.5            -- Mountain-heavy races

-- By date range
WHERE cff.competition_date >= '2022-01-01'     -- Recent data only

-- By field quality
WHERE cff.bucket_mean < 4.0                    -- Strong fields only

-- By rider experience
WHERE rcs.races_career >= 50                   -- Well-established riders
WHERE rcs.races_career BETWEEN 10 AND 100      -- Mid-career riders
```

### Feature Engineering Ideas

```sql
-- Rider-vs-field comparisons
SELECT
    rcs.*,
    rcs.stage_avg_bucket - cff.bucket_mean as rider_vs_field_gap,
    CASE WHEN rcs.best_profile = cff.race_dominant_profile
         THEN 1 ELSE 0 END as profile_match,
    rcs.races_career / cff.experience_mean as relative_experience
FROM rider_competition_snapshots rcs
JOIN competition_field_features cff ON rcs.competition_id = cff.competition_id

-- Profile-race alignment score
SELECT
    rcs.*,
    (rcs.sprint_avg_bucket * cff.race_sprint_score +
     rcs.mountain_avg_bucket * cff.race_mountain_score +
     rcs.hilly_avg_bucket * cff.race_hilly_score +
     rcs.rolling_avg_bucket * cff.race_rolling_score +
     rcs.breakaway_avg_bucket * cff.race_breakaway_score +
     rcs.time_trial_avg_bucket * cff.race_time_trial_score) as predicted_bucket
FROM rider_competition_snapshots rcs
JOIN competition_field_features cff ON rcs.competition_id = cff.competition_id
```

---

## Additional Data Sources

For more advanced features, join with these tables:

### Race Feature Gradients (raw gradient data)
```sql
SELECT rfg.*
FROM race_feature_gradients rfg
WHERE rfg.competition_id = ?
```

### Race Features 100 (per-percentile features)
```sql
SELECT rf100.*
FROM race_features_100 rf100
WHERE rf100.competition_id = ?
```

---

## Data Summary

| Table | Rows | Purpose |
|-------|------|---------|
| `rider_competition_snapshots` | ~466K | Rider state at each race |
| `competition_field_features` | ~3.9K | Field aggregates + race profile |
| `rider_features_running` | ~6.4K | Current rider state (for updates) |
| `rider_results` | ~1M | Raw results with `place_bucket` |

---

## Files

| File | Purpose |
|------|---------|
| `feature_precomputation.py` | Main pre-computation script |
| `rider_history.py` | RiderSnapshot class (for real-time queries) |
| `race_field_history.py` | Field analysis (for real-time queries) |
| `race_profile_scoring.py` | Race profile calculation |
| `place_handling.py` | Bucket conversion |

---

## Updating Features

To process new competitions after the initial run:

```bash
# Resume from last checkpoint (processes new data only)
uv run python -m engineering_tools.feature_precomputation

# Or specify a start date
uv run python -m engineering_tools.feature_precomputation 2024-01-01
```

The checkpoint system ensures you can resume if interrupted.
