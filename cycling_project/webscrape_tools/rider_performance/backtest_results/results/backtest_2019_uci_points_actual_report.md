# Temporal Backtest Report - 2019

**Target Variable:** uci_points_actual
**Training Data:** Up to 2018-12-31
**Test Year:** 2019
**Generated:** 2025-07-09 15:55:27

## Data Statistics

| Dataset | Train Samples | Train Riders | Test Samples | Test Riders | Train Zeros | Test Zeros |
|---------|---------------|--------------|--------------|-------------|-------------|------------|
| gc_dataset | 49,068 | 1,324 | 4,161 | 743 | 37,566 (76.6%) | 3,188 (76.6%) |
| stage_one_day_dataset | 405,793 | 1,324 | 36,161 | 752 | 380,904 (93.9%) | 34,047 (94.2%) |

## GC Model Performance

### Key Statistics
- **Zero inflation:** 76.6% of test samples have 0 points
- **Non-zero samples:** 973 out of 4,161
- **Races evaluated:** 28

### Ranking Metrics (Most Important)

| Metric | Value |
|--------|-------|
| Spearman Correlation (Overall) | 0.1509 |
| Spearman Correlation (Non-zero) | 0.1185 |
| Within-race Spearman (Mean) | 0.2602 |
| Within-race Spearman (Std) | 0.2558 |
| Top-5 Accuracy | 0.0000 |
| Top-10 Accuracy | 0.0000 |
| Top-20 Accuracy | 0.0500 |
| Within-race Top-3 (Mean) | 0.3095 |
| Within-race Top-5 (Mean) | 0.3786 |
| Within-race Top-10 (Mean) | 0.5444 |

### Classification Metrics (0 vs Non-0)

| Metric | Value |
|--------|-------|
| AUC | 0.7334 |
| Precision | 0.4825 |
| Recall | 0.1131 |
| F1 Score | 0.1832 |
| Zero Prediction Accuracy | 0.9630 |

### Regression Metrics

| Metric | Overall | Non-zero Only |
|--------|---------|---------------|
| RMSE | 26.1677 | 51.8119 |
| MAE | 8.3262 | 30.5183 |
| R² | N/A | -0.3756 |

### Points Distribution

| Metric | Value |
|--------|-------|
| Total True Points | 30,639 |
| Total Predicted Points | 9,464 |
| Points Ratio (Pred/True) | 0.3089 |
| Mean True (Non-zero) | 31.49 |
| Mean Predicted (Non-zero) | 4.64 |

### Top 10 Most Important Features

| Rank | Feature | Importance |
|------|---------|------------|
| 1 | prior_stage_points_actual_regressor | 16508674.59 |
| 2 | prior_d1_races_regressor | 5917146.20 |
| 3 | prior_stage_points_proportional_regressor | 4292651.20 |
| 4 | prior_wt_points_proportional_regressor | 4053007.81 |
| 5 | rf_winning_time_regressor | 3133192.79 |
| 6 | prior_pro_races_regressor | 2728622.88 |
| 7 | prior_wt_proportion_regressor | 2712518.59 |
| 8 | prior_gc_points_actual_regressor | 2009564.41 |
| 9 | prior_gc_points_proportional_regressor | 1840850.39 |
| 10 | total_prior_races_regressor | 1782642.29 |

## STAGE_ONE_DAY Model Performance

### Key Statistics
- **Zero inflation:** 94.2% of test samples have 0 points
- **Non-zero samples:** 2,114 out of 36,161
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
| AUC | 0.8555 |
| Precision | 0.0000 |
| Recall | 0.0000 |
| F1 Score | 0.0000 |
| Zero Prediction Accuracy | 1.0000 |

### Regression Metrics

| Metric | Overall | Non-zero Only |
|--------|---------|---------------|
| RMSE | 10.4160 | 43.0793 |
| MAE | 1.3664 | 23.3728 |
| R² | N/A | -0.4172 |

### Points Distribution

| Metric | Value |
|--------|-------|
| Total True Points | 49,410 |
| Total Predicted Points | 0 |
| Points Ratio (Pred/True) | 0.0000 |
| Mean True (Non-zero) | 23.37 |
| Mean Predicted (Non-zero) | 0.00 |

### Top 10 Most Important Features

| Rank | Feature | Importance |
|------|---------|------------|
| 1 | prior_stage_points_actual_regressor | 9898891.54 |
| 2 | rkf_boundary_distance_regressor | 8599535.31 |
| 3 | prior_stage_points_proportional_regressor | 8134853.71 |
| 4 | prior_d1_races_regressor | 4848783.35 |
| 5 | rf_clumpiness_score_regressor | 4704515.60 |
| 6 | prior_wt_points_proportional_regressor | 4313120.19 |
| 7 | prior_one_day_points_actual_regressor | 3844872.09 |
| 8 | prior_one_day_points_proportional_regressor | 3153027.82 |
| 9 | rkf_distance_to_cluster_0_regressor | 3124558.92 |
| 10 | prior_wt_proportion_regressor | 2988325.00 |