# Temporal Backtest Report - 2011

**Target Variable:** uci_points_actual
**Training Data:** Up to 2010-12-31
**Test Year:** 2011
**Generated:** 2025-07-09 13:12:47

## Data Statistics

| Dataset | Train Samples | Train Riders | Test Samples | Test Riders | Train Zeros | Test Zeros |
|---------|---------------|--------------|--------------|-------------|-------------|------------|
| gc_dataset | 4,107 | 577 | 3,515 | 537 | 3,153 (76.8%) | 2,758 (78.5%) |
| stage_one_day_dataset | 34,376 | 577 | 23,838 | 541 | 32,434 (94.4%) | 22,205 (93.1%) |

## GC Model Performance

### Key Statistics
- **Zero inflation:** 78.5% of test samples have 0 points
- **Non-zero samples:** 757 out of 3,515
- **Races evaluated:** 38

### Ranking Metrics (Most Important)

| Metric | Value |
|--------|-------|
| Spearman Correlation (Overall) | 0.2480 |
| Spearman Correlation (Non-zero) | 0.1997 |
| Within-race Spearman (Mean) | 0.3447 |
| Within-race Spearman (Std) | 0.2682 |
| Top-5 Accuracy | 0.0000 |
| Top-10 Accuracy | 0.0000 |
| Top-20 Accuracy | 0.0000 |
| Within-race Top-3 (Mean) | 0.3246 |
| Within-race Top-5 (Mean) | 0.3543 |
| Within-race Top-10 (Mean) | 0.4265 |

### Classification Metrics (0 vs Non-0)

| Metric | Value |
|--------|-------|
| AUC | 0.6876 |
| Precision | 0.3429 |
| Recall | 0.5654 |
| F1 Score | 0.4269 |
| Zero Prediction Accuracy | 0.7027 |

### Regression Metrics

| Metric | Overall | Non-zero Only |
|--------|---------|---------------|
| RMSE | 30.1480 | 48.5231 |
| MAE | 15.5517 | 31.6892 |
| R² | N/A | -0.0722 |

### Points Distribution

| Metric | Value |
|--------|-------|
| Total True Points | 24,592 |
| Total Predicted Points | 47,897 |
| Points Ratio (Pred/True) | 1.9477 |
| Mean True (Non-zero) | 32.49 |
| Mean Predicted (Non-zero) | 22.75 |

### Top 10 Most Important Features

| Rank | Feature | Importance |
|------|---------|------------|
| 1 | prior_stage_points_actual_regressor | 2727968.55 |
| 2 | prior_pro_points_proportional_regressor | 627955.12 |
| 3 | prior_stage_points_proportional_regressor | 587439.66 |
| 4 | prior_d1_races_regressor | 542636.08 |
| 5 | total_prior_points_proportional_regressor | 448455.49 |
| 6 | prior_pro_races_regressor | 409671.28 |
| 7 | prior_gc_points_proportional_regressor | 370076.67 |
| 8 | prior_one_day_points_proportional_regressor | 359525.07 |
| 9 | rf_winning_time_regressor | 296427.11 |
| 10 | prior_d1_points_proportional_regressor | 285504.13 |

## STAGE_ONE_DAY Model Performance

### Key Statistics
- **Zero inflation:** 93.1% of test samples have 0 points
- **Non-zero samples:** 1,633 out of 23,838
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
| AUC | 0.7172 |
| Precision | 0.0000 |
| Recall | 0.0000 |
| F1 Score | 0.0000 |
| Zero Prediction Accuracy | 1.0000 |

### Regression Metrics

| Metric | Overall | Non-zero Only |
|--------|---------|---------------|
| RMSE | 11.7622 | 44.9399 |
| MAE | 1.7447 | 25.4685 |
| R² | N/A | -0.4731 |

### Points Distribution

| Metric | Value |
|--------|-------|
| Total True Points | 41,590 |
| Total Predicted Points | 0 |
| Points Ratio (Pred/True) | 0.0000 |
| Mean True (Non-zero) | 25.47 |
| Mean Predicted (Non-zero) | 0.00 |

### Top 10 Most Important Features

| Rank | Feature | Importance |
|------|---------|------------|
| 1 | total_prior_points_proportional_regressor | 1102999.92 |
| 2 | total_prior_races_regressor | 734949.77 |
| 3 | prior_wt_points_proportional_regressor | 729568.89 |
| 4 | prior_stage_points_proportional_regressor | 681893.98 |
| 5 | rkf_boundary_distance_regressor | 660141.86 |
| 6 | prior_wt_proportion_regressor | 611256.41 |
| 7 | prior_stage_points_actual_regressor | 604406.30 |
| 8 | rf_clumpiness_score_regressor | 585963.73 |
| 9 | prior_d1_races_regressor | 466257.23 |
| 10 | prior_one_day_points_actual_regressor | 449377.31 |