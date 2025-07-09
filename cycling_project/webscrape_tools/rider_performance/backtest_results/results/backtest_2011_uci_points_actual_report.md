# Temporal Backtest Report - 2011

**Target Variable:** uci_points_actual
**Training Data:** Up to 2010-12-31
**Test Year:** 2011
**Generated:** 2025-07-09 09:25:34

## Data Statistics

| Dataset | Train Samples | Train Riders | Test Samples | Test Riders | Train Zeros | Test Zeros |
|---------|---------------|--------------|--------------|-------------|-------------|------------|
| gc_dataset | 3,004 | 401 | 2,580 | 381 | 2,283 (76.0%) | 2,025 (78.5%) |
| stage_one_day_dataset | 25,911 | 401 | 17,589 | 382 | 24,536 (94.7%) | 16,380 (93.1%) |

## GC Model Performance

### Key Statistics
- **Zero inflation:** 78.5% of test samples have 0 points
- **Non-zero samples:** 555 out of 2,580
- **Races evaluated:** 45

### Ranking Metrics (Most Important)

| Metric | Value |
|--------|-------|
| Spearman Correlation (Overall) | 0.1882 |
| Spearman Correlation (Non-zero) | 0.0615 |
| Within-race Spearman (Mean) | 0.0422 |
| Within-race Spearman (Std) | 0.1783 |
| Top-5 Accuracy | 0.0000 |
| Top-10 Accuracy | 0.0000 |
| Top-20 Accuracy | 0.0000 |
| Within-race Top-3 (Mean) | 0.1778 |
| Within-race Top-5 (Mean) | 0.2356 |
| Within-race Top-10 (Mean) | 0.3571 |

### Classification Metrics (0 vs Non-0)

| Metric | Value |
|--------|-------|
| AUC | 0.6933 |
| Precision | 0.3028 |
| Recall | 0.6378 |
| F1 Score | 0.4107 |
| Zero Prediction Accuracy | 0.5975 |

### Regression Metrics

| Metric | Overall | Non-zero Only |
|--------|---------|---------------|
| RMSE | 29.2015 | 50.7870 |
| MAE | 16.6865 | 32.5221 |
| R² | N/A | -0.1433 |

### Points Distribution

| Metric | Value |
|--------|-------|
| Total True Points | 18,691 |
| Total Predicted Points | 35,884 |
| Points Ratio (Pred/True) | 1.9198 |
| Mean True (Non-zero) | 33.68 |
| Mean Predicted (Non-zero) | 19.61 |

### Top 10 Most Important Features

| Rank | Feature | Importance |
|------|---------|------------|
| 1 | rf_time_gap_evenness_metric_regressor | 72735.19 |
| 2 | prior_one_day_races_regressor | 43494.17 |
| 3 | rf_clumpiness_score_regressor | 35067.38 |
| 4 | prior_stage_races_regressor | 25910.50 |
| 5 | rider_age_at_race_regressor | 24060.05 |
| 6 | total_prior_races_regressor | 19611.48 |
| 7 | rf_skewness_absolute_regressor | 16199.90 |
| 8 | prior_d1_races_regressor | 16124.44 |
| 9 | rkf_boundary_distance_regressor | 14778.70 |
| 10 | rf_riders_in_groups_regressor | 13195.72 |

## STAGE_ONE_DAY Model Performance

### Key Statistics
- **Zero inflation:** 93.1% of test samples have 0 points
- **Non-zero samples:** 1,209 out of 17,589
- **Races evaluated:** 0

### Ranking Metrics (Most Important)

| Metric | Value |
|--------|-------|
| Spearman Correlation (Overall) | 0.0000 |
| Spearman Correlation (Non-zero) | 0.0000 |
| Within-race Spearman (Mean) | 0.0000 |
| Within-race Spearman (Std) | 0.0000 |
| Top-5 Accuracy | 0.0000 |
| Top-10 Accuracy | 0.0000 |
| Top-20 Accuracy | 0.0000 |
| Within-race Top-3 (Mean) | 0.0000 |
| Within-race Top-5 (Mean) | 0.0000 |
| Within-race Top-10 (Mean) | 0.0000 |

### Classification Metrics (0 vs Non-0)

| Metric | Value |
|--------|-------|
| AUC | 0.7940 |
| Precision | 0.0000 |
| Recall | 0.0000 |
| F1 Score | 0.0000 |
| Zero Prediction Accuracy | 1.0000 |

### Regression Metrics

| Metric | Overall | Non-zero Only |
|--------|---------|---------------|
| RMSE | 12.0922 | 46.1226 |
| MAE | 1.8102 | 26.3350 |
| R² | N/A | -0.4837 |

### Points Distribution

| Metric | Value |
|--------|-------|
| Total True Points | 31,839 |
| Total Predicted Points | 0 |
| Points Ratio (Pred/True) | 0.0000 |
| Mean True (Non-zero) | 26.33 |
| Mean Predicted (Non-zero) | 0.00 |

### Top 10 Most Important Features

| Rank | Feature | Importance |
|------|---------|------------|
| 1 | rider_age_at_race_regressor | 693632.60 |
| 2 | prior_wt_proportion_regressor | 632654.90 |
| 3 | prior_d1_races_regressor | 543954.30 |
| 4 | rkf_boundary_distance_regressor | 438150.82 |
| 5 | prior_wt_races_regressor | 436737.86 |
| 6 | total_prior_races_regressor | 417184.01 |
| 7 | prior_stage_races_regressor | 408354.18 |
| 8 | rf_clumpiness_score_regressor | 386278.39 |
| 9 | prior_one_day_races_regressor | 362989.73 |
| 10 | prior_gc_races_regressor | 276546.76 |