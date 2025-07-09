# Temporal Backtest Report - 2011

**Target Variable:** uci_points_proportional
**Training Data:** Up to 2010-12-31
**Test Year:** 2011
**Generated:** 2025-07-09 13:15:24

## Data Statistics

| Dataset | Train Samples | Train Riders | Test Samples | Test Riders | Train Zeros | Test Zeros |
|---------|---------------|--------------|--------------|-------------|-------------|------------|
| gc_dataset | 4,107 | 577 | 3,515 | 537 | 3,153 (76.8%) | 2,758 (78.5%) |
| stage_one_day_dataset | 34,376 | 577 | 23,838 | 541 | 32,434 (94.4%) | 22,205 (93.1%) |

## GC Model Performance

### Key Statistics
- **Zero inflation:** 42.6% of test samples have 0 points
- **Non-zero samples:** 2,018 out of 3,515
- **Races evaluated:** 64

### Ranking Metrics (Most Important)

| Metric | Value |
|--------|-------|
| Spearman Correlation (Overall) | 0.3162 |
| Spearman Correlation (Non-zero) | 0.2691 |
| Within-race Spearman (Mean) | 0.2917 |
| Within-race Spearman (Std) | 0.2078 |
| Top-5 Accuracy | 0.0000 |
| Top-10 Accuracy | 0.3000 |
| Top-20 Accuracy | 0.1500 |
| Within-race Top-3 (Mean) | 0.2552 |
| Within-race Top-5 (Mean) | 0.3213 |
| Within-race Top-10 (Mean) | 0.3983 |

### Classification Metrics (0 vs Non-0)

| Metric | Value |
|--------|-------|
| AUC | 0.6799 |
| Precision | 0.6407 |
| Recall | 0.8791 |
| F1 Score | 0.7412 |
| Zero Prediction Accuracy | 0.3360 |

### Regression Metrics

| Metric | Overall | Non-zero Only |
|--------|---------|---------------|
| RMSE | 111.4545 | 131.8575 |
| MAE | 63.4185 | 76.9358 |
| R² | N/A | 0.0586 |

### Points Distribution

| Metric | Value |
|--------|-------|
| Total True Points | 134,872 |
| Total Predicted Points | 223,445 |
| Points Ratio (Pred/True) | 1.6567 |
| Mean True (Non-zero) | 66.83 |
| Mean Predicted (Non-zero) | 77.20 |

### Top 10 Most Important Features

| Rank | Feature | Importance |
|------|---------|------------|
| 1 | prior_stage_points_proportional_regressor | 53427691.69 |
| 2 | prior_wt_points_proportional_regressor | 21833691.35 |
| 3 | prior_d1_races_regressor | 17894804.59 |
| 4 | prior_stage_points_actual_regressor | 9526657.98 |
| 5 | prior_stage_races_regressor | 9199168.11 |
| 6 | prior_gc_points_actual_regressor | 8199000.69 |
| 7 | rf_time_gap_evenness_metric_regressor | 8068714.58 |
| 8 | prior_one_day_points_proportional_regressor | 7792969.61 |
| 9 | rkf_distance_to_cluster_2_regressor | 6716940.60 |
| 10 | total_prior_races_regressor | 6676821.08 |

## STAGE_ONE_DAY Model Performance

### Key Statistics
- **Zero inflation:** 77.5% of test samples have 0 points
- **Non-zero samples:** 5,354 out of 23,838
- **Races evaluated:** 114

### Ranking Metrics (Most Important)

| Metric | Value |
|--------|-------|
| Spearman Correlation (Overall) | 0.4690 |
| Spearman Correlation (Non-zero) | 0.2037 |
| Within-race Spearman (Mean) | 0.2552 |
| Within-race Spearman (Std) | 0.2441 |
| Top-5 Accuracy | 0.0000 |
| Top-10 Accuracy | 0.0000 |
| Top-20 Accuracy | 0.0500 |
| Within-race Top-3 (Mean) | 0.2778 |
| Within-race Top-5 (Mean) | 0.3248 |
| Within-race Top-10 (Mean) | 0.4262 |

### Classification Metrics (0 vs Non-0)

| Metric | Value |
|--------|-------|
| AUC | 0.8271 |
| Precision | 0.6923 |
| Recall | 0.4350 |
| F1 Score | 0.5343 |
| Zero Prediction Accuracy | 0.9440 |

### Regression Metrics

| Metric | Overall | Non-zero Only |
|--------|---------|---------------|
| RMSE | 47.2244 | 93.7225 |
| MAE | 13.9536 | 50.1027 |
| R² | N/A | -0.0263 |

### Points Distribution

| Metric | Value |
|--------|-------|
| Total True Points | 238,076 |
| Total Predicted Points | 258,416 |
| Points Ratio (Pred/True) | 1.0854 |
| Mean True (Non-zero) | 44.47 |
| Mean Predicted (Non-zero) | 36.24 |

### Top 10 Most Important Features

| Rank | Feature | Importance |
|------|---------|------------|
| 1 | prior_wt_points_proportional_regressor | 24661795.98 |
| 2 | rkf_distance_to_cluster_0_regressor | 17191904.89 |
| 3 | total_prior_races_regressor | 10982980.61 |
| 4 | total_prior_points_proportional_regressor | 10341743.91 |
| 5 | prior_stage_races_regressor | 9247651.60 |
| 6 | prior_one_day_points_proportional_regressor | 8151157.20 |
| 7 | rkf_boundary_distance_regressor | 7691790.50 |
| 8 | prior_stage_points_proportional_regressor | 7246512.90 |
| 9 | prior_gc_points_proportional_regressor | 7135916.19 |
| 10 | prior_wt_proportion_regressor | 7007968.88 |