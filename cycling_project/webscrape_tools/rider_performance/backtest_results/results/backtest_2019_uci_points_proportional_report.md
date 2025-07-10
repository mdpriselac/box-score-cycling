# Temporal Backtest Report - 2019

**Target Variable:** uci_points_proportional
**Training Data:** Up to 2018-12-31
**Test Year:** 2019
**Generated:** 2025-07-09 16:24:17

## Data Statistics

| Dataset | Train Samples | Train Riders | Test Samples | Test Riders | Train Zeros | Test Zeros |
|---------|---------------|--------------|--------------|-------------|-------------|------------|
| gc_dataset | 49,068 | 1,324 | 4,161 | 743 | 37,566 (76.6%) | 3,188 (76.6%) |
| stage_one_day_dataset | 405,793 | 1,324 | 36,161 | 752 | 380,904 (93.9%) | 34,047 (94.2%) |

## GC Model Performance

### Key Statistics
- **Zero inflation:** 38.7% of test samples have 0 points
- **Non-zero samples:** 2,550 out of 4,161
- **Races evaluated:** 85

### Ranking Metrics (Most Important)

| Metric | Value |
|--------|-------|
| Spearman Correlation (Overall) | 0.5202 |
| Spearman Correlation (Non-zero) | 0.4211 |
| Within-race Spearman (Mean) | 0.4751 |
| Within-race Spearman (Std) | 0.1744 |
| Top-5 Accuracy | 0.2000 |
| Top-10 Accuracy | 0.2000 |
| Top-20 Accuracy | 0.2500 |
| Within-race Top-3 (Mean) | 0.3451 |
| Within-race Top-5 (Mean) | 0.4235 |
| Within-race Top-10 (Mean) | 0.5476 |

### Classification Metrics (0 vs Non-0)

| Metric | Value |
|--------|-------|
| AUC | 0.8007 |
| Precision | 0.7959 |
| Recall | 0.7541 |
| F1 Score | 0.7745 |
| Zero Prediction Accuracy | 0.6940 |

### Regression Metrics

| Metric | Overall | Non-zero Only |
|--------|---------|---------------|
| RMSE | 95.2090 | 117.4272 |
| MAE | 46.6815 | 64.7181 |
| R² | N/A | 0.2548 |

### Points Distribution

| Metric | Value |
|--------|-------|
| Total True Points | 172,792 |
| Total Predicted Points | 183,566 |
| Points Ratio (Pred/True) | 1.0623 |
| Mean True (Non-zero) | 67.76 |
| Mean Predicted (Non-zero) | 60.53 |

### Top 10 Most Important Features

| Rank | Feature | Importance |
|------|---------|------------|
| 1 | prior_gc_points_proportional_regressor | 369171329.00 |
| 2 | prior_stage_points_proportional_regressor | 127536597.00 |
| 3 | prior_d1_races_regressor | 108673583.00 |
| 4 | prior_wt_points_proportional_regressor | 92436247.00 |
| 5 | rf_winning_time_regressor | 64145815.00 |
| 6 | prior_one_day_races_regressor | 61405605.00 |
| 7 | prior_pro_races_regressor | 61229477.00 |
| 8 | prior_stage_points_actual_regressor | 55372105.00 |
| 9 | total_prior_races_regressor | 53553584.00 |
| 10 | prior_gc_points_actual_regressor | 49272281.00 |

## STAGE_ONE_DAY Model Performance

### Key Statistics
- **Zero inflation:** 78.5% of test samples have 0 points
- **Non-zero samples:** 7,780 out of 36,161
- **Races evaluated:** 129

### Ranking Metrics (Most Important)

| Metric | Value |
|--------|-------|
| Spearman Correlation (Overall) | 0.4364 |
| Spearman Correlation (Non-zero) | 0.1714 |
| Within-race Spearman (Mean) | 0.3138 |
| Within-race Spearman (Std) | 0.2070 |
| Top-5 Accuracy | 0.0000 |
| Top-10 Accuracy | 0.0000 |
| Top-20 Accuracy | 0.1000 |
| Within-race Top-3 (Mean) | 0.2842 |
| Within-race Top-5 (Mean) | 0.3581 |
| Within-race Top-10 (Mean) | 0.4715 |

### Classification Metrics (0 vs Non-0)

| Metric | Value |
|--------|-------|
| AUC | 0.8310 |
| Precision | 0.6624 |
| Recall | 0.4048 |
| F1 Score | 0.5025 |
| Zero Prediction Accuracy | 0.9434 |

### Regression Metrics

| Metric | Overall | Non-zero Only |
|--------|---------|---------------|
| RMSE | 43.0318 | 87.3231 |
| MAE | 12.2226 | 46.0816 |
| R² | N/A | 0.1239 |

### Points Distribution

| Metric | Value |
|--------|-------|
| Total True Points | 356,441 |
| Total Predicted Points | 311,803 |
| Points Ratio (Pred/True) | 0.8748 |
| Mean True (Non-zero) | 45.82 |
| Mean Predicted (Non-zero) | 29.35 |

### Top 10 Most Important Features

| Rank | Feature | Importance |
|------|---------|------------|
| 1 | prior_wt_points_proportional_regressor | 266348273.11 |
| 2 | rkf_boundary_distance_regressor | 230662317.11 |
| 3 | prior_one_day_points_proportional_regressor | 189151627.68 |
| 4 | prior_stage_points_actual_regressor | 90444450.89 |
| 5 | prior_d1_races_regressor | 89341406.77 |
| 6 | prior_one_day_points_actual_regressor | 86794485.30 |
| 7 | prior_stage_points_proportional_regressor | 84870384.71 |
| 8 | prior_wt_races_regressor | 77664739.29 |
| 9 | prior_stage_races_regressor | 73276671.10 |
| 10 | prior_one_day_races_regressor | 72704024.98 |