# Temporal Backtest Report - 2022

**Target Variable:** uci_points_actual
**Training Data:** Up to 2021-12-31
**Test Year:** 2022
**Generated:** 2025-07-09 09:52:14

## Data Statistics

| Dataset | Train Samples | Train Riders | Test Samples | Test Riders | Train Zeros | Test Zeros |
|---------|---------------|--------------|--------------|-------------|-------------|------------|
| gc_dataset | 71,154 | 2,107 | 3,287 | 770 | 54,705 (76.9%) | 2,422 (73.7%) |
| stage_one_day_dataset | 588,624 | 2,107 | 30,453 | 794 | 553,234 (94.0%) | 28,212 (92.6%) |

## GC Model Performance

### Key Statistics
- **Zero inflation:** 73.7% of test samples have 0 points
- **Non-zero samples:** 865 out of 3,287
- **Races evaluated:** 0

### Ranking Metrics (Most Important)

| Metric | Value |
|--------|-------|
| Spearman Correlation (Overall) | 0.0000 |
| Spearman Correlation (Non-zero) | 0.0000 |
| Within-race Spearman (Mean) | 0.0000 |
| Within-race Spearman (Std) | 0.0000 |
| Top-5 Accuracy | 0.2000 |
| Top-10 Accuracy | 0.1000 |
| Top-20 Accuracy | 0.0500 |
| Within-race Top-3 (Mean) | 0.0000 |
| Within-race Top-5 (Mean) | 0.0000 |
| Within-race Top-10 (Mean) | 0.0000 |

### Classification Metrics (0 vs Non-0)

| Metric | Value |
|--------|-------|
| AUC | 0.6691 |
| Precision | 0.0000 |
| Recall | 0.0000 |
| F1 Score | 0.0000 |
| Zero Prediction Accuracy | 1.0000 |

### Regression Metrics

| Metric | Overall | Non-zero Only |
|--------|---------|---------------|
| RMSE | 30.6849 | 59.8159 |
| MAE | 8.7289 | 33.1699 |
| R² | N/A | -0.4441 |

### Points Distribution

| Metric | Value |
|--------|-------|
| Total True Points | 28,692 |
| Total Predicted Points | 0 |
| Points Ratio (Pred/True) | 0.0000 |
| Mean True (Non-zero) | 33.17 |
| Mean Predicted (Non-zero) | 0.00 |

### Top 10 Most Important Features

| Rank | Feature | Importance |
|------|---------|------------|
| 1 | prior_wt_proportion_regressor | 8588853.50 |
| 2 | prior_pro_races_regressor | 2697242.80 |
| 3 | prior_one_day_races_regressor | 2110266.41 |
| 4 | rf_winning_time_regressor | 2024102.80 |
| 5 | rider_age_at_race_regressor | 1925620.80 |
| 6 | prior_d1_races_regressor | 1771008.30 |
| 7 | prior_wt_races_regressor | 1554678.21 |
| 8 | prior_gc_races_regressor | 1477715.70 |
| 9 | rf_skewness_absolute_regressor | 1469038.99 |
| 10 | rkf_local_density_regressor | 1309781.20 |

## STAGE_ONE_DAY Model Performance

### Key Statistics
- **Zero inflation:** 92.6% of test samples have 0 points
- **Non-zero samples:** 2,241 out of 30,453
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
| AUC | 0.8187 |
| Precision | 0.0000 |
| Recall | 0.0000 |
| F1 Score | 0.0000 |
| Zero Prediction Accuracy | 1.0000 |

### Regression Metrics

| Metric | Overall | Non-zero Only |
|--------|---------|---------------|
| RMSE | 13.4570 | 49.6070 |
| MAE | 1.9572 | 26.5971 |
| R² | N/A | -0.4034 |

### Points Distribution

| Metric | Value |
|--------|-------|
| Total True Points | 59,604 |
| Total Predicted Points | 0 |
| Points Ratio (Pred/True) | 0.0000 |
| Mean True (Non-zero) | 26.60 |
| Mean Predicted (Non-zero) | 0.00 |

### Top 10 Most Important Features

| Rank | Feature | Importance |
|------|---------|------------|
| 1 | prior_wt_proportion_regressor | 14484250.45 |
| 2 | rkf_boundary_distance_regressor | 8902142.59 |
| 3 | rf_proportion_in_groups_regressor | 7447574.62 |
| 4 | prior_one_day_races_regressor | 5938272.63 |
| 5 | rider_age_at_race_regressor | 4922680.01 |
| 6 | prior_d1_races_regressor | 4833708.23 |
| 7 | rf_clumpiness_score_regressor | 4631855.10 |
| 8 | prior_pro_races_regressor | 4457592.97 |
| 9 | prior_stage_races_regressor | 3829176.91 |
| 10 | prior_wt_races_regressor | 3779032.49 |