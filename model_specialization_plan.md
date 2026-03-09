# Model Specialization & Experimentation Plan

## Context

The current system trains 5 LightGBM models (bucket, time gap, 3 probability variants) on a unified 103-feature set across all competition types. While `competition_type` and type-specific averages exist as features, the model has no structural specialization for the fundamentally different dynamics of one-day races (open field, individual ambition), stage races (team tactics, domestique roles), and GC (consistency, cumulative performance). The contender model (two-stage: bucket predictor filters to top-25, adds classifier prediction as feature) is the key innovation but stops early at 47 iterations, suggesting room for improvement.

Goal: Design and test multiple approaches to squeeze more predictive accuracy for top-4 buckets (Winner, Podium, Top 5, Top 15), with a systematic experiment framework to measure progress.

---

## Decisions
- **Sequencing**: Build experiment framework first, before any model changes
- **Race type priority**: All three types (stage, one-day, GC) matter equally; handle GC's smaller sample size carefully
- **Rider embedding min samples**: 20 races minimum, with population-average fallback

---

## Phase 1: Experiment Infrastructure (Build First)

### 1.1 ExperimentRunner class
**File**: New `cycling_project/prediction_tools/experiment_runner.py`

Create a standardized experiment harness that:
- Accepts an experiment config (model approach, features, hyperparameters)
- Runs **expanding-window temporal CV** (4 folds):
  - Fold 1: Train 2018-2020, Val 2021H1, Test 2021H2
  - Fold 2: Train 2018-2021, Val 2022H1, Test 2022H2
  - Fold 3: Train 2018-2022, Val 2023H1, Test 2023H2
  - Fold 4: Train 2018-2023, Val 2024H1, Test 2024H2
- Computes all metrics per fold, reports mean +/- std
- Saves results to JSON (one file per experiment, append-friendly)
- Compares against baseline automatically

### 1.2 Metrics Hierarchy

**Primary** (optimize for these):
1. Race winner capture rate (% of races where actual winner is model's #1)
2. Top-4 log loss (log loss on samples with actual bucket 0-3 only)
3. Podium capture rate (% of actual podium finishers in model's top 3)

**Secondary** (diagnostic):
4. Win/Podium cumulative calibration ratio (predicted vs actual frequency)
5. Top-5 precision@10
6. Brier score on top-4 samples

**Stopping rule**: If 3 consecutive experiments fail to improve best validation metrics, stop exploring and productionize best approach.

### 1.3 Baseline Run
Run the current production model through the 4-fold CV to establish baseline numbers. All subsequent experiments compare against this.

**Key files**:
- New: `cycling_project/prediction_tools/experiment_runner.py`
- Modify: `cycling_project/prediction_tools/evaluation.py` (add fold-level aggregation utilities)
- Reuse: `CyclingDataPipeline`, `ModelTrainer`, existing evaluators

---

## Phase 2: Quick-Win Approaches (1-2 days each)

### Approach A: Competition-Type Interaction Features
**Complexity**: Low | **Files**: `prediction_tools/feature_engineering.py` only

Add ~10 derived features to `create_derived_features()` capturing *relative* specialization:

| Feature | Formula | Rationale |
|---------|---------|-----------|
| `type_specialization_gap` | best type avg - worst type avg | How specialized is this rider? |
| `is_type_specialist` | relevant_type_avg < overall avg - 0.5 | Boolean: strong in this race type |
| `type_experience_ratio` | relevant_type_count / races_career | What fraction of career is this type? |
| `stage_vs_oneday_gap` | stage_avg - one_day_avg | Domestique signal (positive = better at one-days) |
| `gc_specialist_score` | gc_avg weighted by gc_count | GC ability with confidence |
| `form_x_type_match` | form_recent_avg * is_type_specialist | Recent form amplified by type fit |
| `profile_x_type_interaction` | profile_weighted_expected * relevant_type_avg | Combined terrain + type signal |
| `category_x_type_interaction` | relevant_category_avg * relevant_type_avg | Level + type combined |

**Data leakage**: None. All features derive from pre-computed snapshots (historical data only).

**Expected benefit**: Modest but risk-free. Captures the domestique-in-stages / contender-in-onedays dynamic the user identified.

### Approach B: Contender Model Tuning
**Complexity**: Low-Medium | **Files**: `prediction_tools/training.py`, `prediction_tools/train_production_model.py`

The contender model's 47-iteration early stop is a red flag. Test these variants:

1. **Top-N sweep**: Test top-15, top-20, top-25, top-30, top-35
2. **Adaptive top-N**: Use top 20% of field (varies by race size)
3. **Reduced learning rate**: 0.01 instead of 0.05 for the contender model specifically (more iterations, smoother convergence)
4. **Soft contender weighting**: Instead of hard filtering, weight all training samples by `1 / (1 + expected_bucket)` — riders predicted better get higher weight, no data discarded
5. **Out-of-fold filtering**: Use 5-fold CV bucket predictions to filter training data, eliminating the leakage from the bucket predictor predicting on its own training data

**Data leakage risk**: Current approach uses bucket predictor's predictions on its own training data for filtering (mild leakage). Out-of-fold variant (option 5) eliminates this.

**Expected benefit**: High ROI — the contender model is already the key differentiator, and it appears undertrained.

---

## Phase 3: Medium Investments (3-5 days each)

### Approach C: Race-Type Specialized Probability Models
**Complexity**: Medium | **Files**: `prediction_tools/training.py`, `prediction_tools/race_ranking_predictor.py`, `prediction_tools/model_registry.py`

Train 2-3 separate contender probability models, one per competition type:
- **One-day model**: Trained only on one-day race data
- **Stage model**: Trained only on stage race data
- **GC model**: Trained only on GC data (if sufficient samples; else fall back to general model)

All share the same bucket predictor backbone (trained on all data). Each specialized model gets `classifier_expected_bucket` as usual.

**Routing at inference**: Based on `competition_type` of the target race.

**Data leakage risks**:
- Cross-type features (e.g., `stage_avg_bucket` visible in one-day model): This is intentional, not leakage. A rider's stage history *should* inform one-day predictions.
- GC vs stages of same race: A rider's GC result is influenced by their stage results. But since features are pre-computed snapshots from *prior* races, this is already handled by temporal ordering.
- GC sample size: May be too small for a standalone model. Strategy: train GC model on all data but with heavy upweighting of GC samples, rather than filtering to GC-only. This preserves cross-type transfer learning while emphasizing GC patterns. If GC has < 5K samples, use the shared model + GC-specific temperature calibration (Approach D) instead.

**Expected benefit**: Strong for all three types. The unified model currently treats all types equally in its learned patterns despite one-hot encoding. All three types matter equally per user preference.

### Approach D: Context-Specific Temperature Calibration
**Complexity**: Medium | **Files**: `prediction_tools/probability_predictor.py`

Replace single global temperature with context-specific temperatures:
- Group by `(competition_type, race_dominant_profile, race_category)`
- Fit per-group temperature on validation data
- Hierarchical pooling: blend per-group temperature with global temperature, weighted by group sample size (avoid overfitting small groups)

**Data leakage**: None (calibration is always done on held-out data).

**Expected benefit**: Directly improves cumulative probability calibration for the sportsbook odds display. Different race contexts likely need different confidence adjustments.

---

## Phase 4: Ambitious Approaches (1-2 weeks each)

### Approach E: Per-Rider Regression Embeddings
**Complexity**: High | **Files**: `engineering_tools/feature_precomputation.py`, `prediction_tools/feature_engineering.py`

For riders with >= 20 career races, fit an incremental linear regression:
- **Target**: `place_bucket`
- **Features**: 6 race profile scores + field_quality_score + race_category_encoded (~8 features)
- **Output**: 8 coefficients become rider embedding features (intercept + 7 slopes)

**Implementation via incremental OLS**:
- Maintain `X^T X` (8x8 matrix) and `X^T y` (8-vector) per rider in `RiderRunningState`
- Update after each race with Sherman-Morrison formula
- Compute coefficients at snapshot time: `beta = (X^T X)^-1 @ X^T y`
- For riders with < 20 races: use population-average coefficients (confirmed threshold)

The slopes capture how each rider *responds* to race difficulty — e.g., a `lr_slope_mountain` of -0.5 means this rider performs 0.5 buckets worse per unit increase in mountain score. Two riders with identical `mountain_avg_bucket` but different slopes have very different profiles.

**Data leakage risk**: HIGH if not incremental. Must use only races *before* the target race. The incremental OLS approach handles this correctly by computing coefficients from the running statistics at snapshot time.

**Requires**: Full re-run of `feature_precomputation.py` to populate new columns. Add columns to `rider_competition_snapshots` table.

### Approach F: Stacked Ensemble with Meta-Learner
**Complexity**: High | **Files**: New `prediction_tools/meta_learner.py`, modifications to `training.py`

Train a lightweight meta-learner on out-of-fold predictions from all base models:
- **Inputs**: bucket_pred_continuous, time_gap_pred, prob_weighted[8], prob_calibrated[8], prob_contender[8], plus context features (comp_type, field_size, profile scores)
- **Output**: 8-class probabilities
- **Model**: Small LightGBM (num_leaves=15, few estimators) or logistic regression

**Critical requirement**: Base model predictions must be out-of-fold to avoid leakage. Use 5-fold temporal-aware CV on training data.

**Expected benefit**: Can learn context-dependent model weighting (e.g., trust time gap model more for mountain stages, contender model more for small fields).

### Approach G: Rider Clustering / Latent Archetypes
**Complexity**: High | **Files**: New `prediction_tools/rider_clustering.py`, `prediction_tools/feature_engineering.py`

Cluster riders into 8-15 archetypes using GMM on their feature vectors:
- Input: 6 profile avg_buckets + 3 type avg_buckets + form features + regression embeddings (from Approach E)
- Output: cluster_id + soft membership probabilities as features
- Fit on training-period data only; assign new riders at inference

Main value: lets us "borrow strength" from similar riders, especially for riders with limited history.

**Depends on**: Approach E (regression embeddings) for richest clustering features.

---

## Implementation Order

```
Phase 1: Experiment Infrastructure     [~2 days]
    └─> Baseline CV run

Phase 2: Quick Wins (parallel)         [~2 days each]
    ├─> Approach A: Type interaction features
    └─> Approach B: Contender model tuning

Phase 3: Medium Investments             [~3-5 days each]
    ├─> Approach C: Type-specialized models
    └─> Approach D: Context temperature calibration

Phase 4: Ambitious (sequential)         [~1-2 weeks each]
    ├─> Approach E: Per-rider regression embeddings
    ├─> Approach F: Stacked ensemble
    └─> Approach G: Rider clustering (if E shows promise)
```

Each approach is evaluated via the experiment framework before moving to the next. Stop if 3 consecutive approaches fail to beat the best result.

---

## Data Leakage Summary

| Approach | Risk | Severity | Mitigation |
|----------|------|----------|------------|
| A. Type interactions | None | - | Snapshot-based features |
| B. Contender tuning | Bucket predictor predicts on own training data | Low | Out-of-fold filtering variant |
| C. Type-specialized | Cross-type features visible | Negligible | Intentional (not leakage) |
| D. Context temperature | Overfitting small groups | Low | Hierarchical pooling |
| E. Rider embeddings | Regression on future data | **HIGH** | Incremental OLS mandatory |
| F. Meta-learner | Base models predict on own data | **HIGH** | Out-of-fold base predictions mandatory |
| G. Clustering | Clustering on future riders | Medium | Fit on training period only |

---

## Verification Plan

For each approach:
1. Run through 4-fold expanding-window CV via `ExperimentRunner`
2. Compare primary metrics (winner capture, top-4 log loss, podium capture) vs baseline
3. Check for overfitting: val metrics should correlate with test metrics across folds
4. Inspect feature importances for sanity (new features should rank meaningfully)
5. Spot-check predictions on known races (e.g., recent Tour de France stages)

Final validation before production:
- Run best approach on full train/val/test split
- Compare race-level predictions against actual results for recent season
- Verify calibration curves for cumulative probabilities
- Ensure inference time remains acceptable for web app
