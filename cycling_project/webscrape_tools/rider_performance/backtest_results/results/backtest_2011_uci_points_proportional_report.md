# Temporal Backtest Report - 2011

**Target Variable:** uci_points_proportional
**Training Data:** Up to 2010-12-31
**Test Year:** 2011
**Generated:** 2025-07-09 09:26:38

## Data Statistics

| Dataset | Train Samples | Train Riders | Test Samples | Test Riders | Train Zeros | Test Zeros |
|---------|---------------|--------------|--------------|-------------|-------------|------------|
| gc_dataset | 3,004 | 401 | 2,580 | 381 | 2,283 (76.0%) | 2,025 (78.5%) |
| stage_one_day_dataset | 25,911 | 401 | 17,589 | 382 | 24,536 (94.7%) | 16,380 (93.1%) |

## GC Model Performance

### Key Statistics
- **Zero inflation:** 41.3% of test samples have 0 points
- **Non-zero samples:** 1,515 out of 2,580
- **Races evaluated:** 58

### Ranking Metrics (Most Important)

| Metric | Value |
|--------|-------|
| Spearman Correlation (Overall) | 0.0937 |
| Spearman Correlation (Non-zero) | -0.0152 |
| Within-race Spearman (Mean) | 0.0584 |
| Within-race Spearman (Std) | 0.2432 |
| Top-5 Accuracy | 0.0000 |
| Top-10 Accuracy | 0.1000 |
| Top-20 Accuracy | 0.1000 |
| Within-race Top-3 (Mean) | 0.1724 |
| Within-race Top-5 (Mean) | 0.2276 |
| Within-race Top-10 (Mean) | 0.3556 |

### Classification Metrics (0 vs Non-0)

| Metric | Value |
|--------|-------|
| AUC | 0.5831 |
| Precision | 0.6286 |
| Recall | 0.7809 |
| F1 Score | 0.6965 |
| Zero Prediction Accuracy | 0.3437 |

### Regression Metrics

| Metric | Overall | Non-zero Only |
|--------|---------|---------------|
| RMSE | 119.9011 | 150.1313 |
| MAE | 61.1058 | 77.5220 |
| R² | N/A | -0.0567 |

### Points Distribution

| Metric | Value |
|--------|-------|
| Total True Points | 110,742 |
| Total Predicted Points | 110,794 |
| Points Ratio (Pred/True) | 1.0005 |
| Mean True (Non-zero) | 73.10 |
| Mean Predicted (Non-zero) | 46.59 |

### Top 10 Most Important Features

| Rank | Feature | Importance |
|------|---------|------------|
| 1 | prior_wt_proportion_regressor | 23692850.10 |
| 2 | rider_age_at_race_regressor | 14651229.70 |
| 3 | prior_wt_races_regressor | 10391283.54 |
| 4 | prior_one_day_races_regressor | 8806437.59 |
| 5 | prior_d1_races_regressor | 8190505.56 |
| 6 | prior_pro_races_regressor | 7710053.89 |
| 7 | total_prior_races_regressor | 7041842.41 |
| 8 | prior_stage_races_regressor | 6945890.86 |
| 9 | rf_winning_time_regressor | 5592421.33 |
| 10 | rf_clumpiness_score_regressor | 4437171.89 |

## STAGE_ONE_DAY Model Performance

### Key Statistics
- **Zero inflation:** 77.3% of test samples have 0 points
- **Non-zero samples:** 3,991 out of 17,589
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
| AUC | 0.7526 |
| Precision | 0.0000 |
| Recall | 0.0000 |
| F1 Score | 0.0000 |
| Zero Prediction Accuracy | 1.0000 |

### Regression Metrics

| Metric | Overall | Non-zero Only |
|--------|---------|---------------|
| RMSE | 50.9880 | 107.0405 |
| MAE | 10.5761 | 46.6107 |
| R² | N/A | -0.2340 |

### Points Distribution

| Metric | Value |
|--------|-------|
| Total True Points | 186,023 |
| Total Predicted Points | 0 |
| Points Ratio (Pred/True) | 0.0000 |
| Mean True (Non-zero) | 46.61 |
| Mean Predicted (Non-zero) | 0.00 |

### Top 10 Most Important Features

| Rank | Feature | Importance |
|------|---------|------------|
| 1 | prior_wt_proportion_regressor | 19939617.39 |
| 2 | prior_d1_races_regressor | 18748855.35 |
| 3 | rider_age_at_race_regressor | 11486907.68 |
| 4 | prior_stage_races_regressor | 11297989.31 |
| 5 | prior_wt_races_regressor | 8390522.20 |
| 6 | prior_pro_races_regressor | 7296079.03 |
| 7 | total_prior_races_regressor | 7281073.21 |
| 8 | prior_one_day_races_regressor | 6423618.34 |
| 9 | prior_gc_races_regressor | 5042680.09 |
| 10 | rkf_distance_to_cluster_0_regressor | 4734891.81 |