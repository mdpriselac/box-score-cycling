# Temporal Backtest Report - 2022

**Target Variable:** uci_points_proportional
**Training Data:** Up to 2021-12-31
**Test Year:** 2022
**Generated:** 2025-07-09 10:48:06

## Data Statistics

| Dataset | Train Samples | Train Riders | Test Samples | Test Riders | Train Zeros | Test Zeros |
|---------|---------------|--------------|--------------|-------------|-------------|------------|
| gc_dataset | 71,154 | 2,107 | 3,287 | 770 | 54,705 (76.9%) | 2,422 (73.7%) |
| stage_one_day_dataset | 588,624 | 2,107 | 30,453 | 794 | 553,234 (94.0%) | 28,212 (92.6%) |

## GC Model Performance

### Key Statistics
- **Zero inflation:** 37.1% of test samples have 0 points
- **Non-zero samples:** 2,069 out of 3,287
- **Races evaluated:** 58

### Ranking Metrics (Most Important)

| Metric | Value |
|--------|-------|
| Spearman Correlation (Overall) | 0.3518 |
| Spearman Correlation (Non-zero) | 0.3084 |
| Within-race Spearman (Mean) | 0.2814 |
| Within-race Spearman (Std) | 0.1730 |
| Top-5 Accuracy | 0.2000 |
| Top-10 Accuracy | 0.3000 |
| Top-20 Accuracy | 0.3500 |
| Within-race Top-3 (Mean) | 0.2011 |
| Within-race Top-5 (Mean) | 0.2897 |
| Within-race Top-10 (Mean) | 0.4017 |

### Classification Metrics (0 vs Non-0)

| Metric | Value |
|--------|-------|
| AUC | 0.7003 |
| Precision | 0.7373 |
| Recall | 0.7134 |
| F1 Score | 0.7251 |
| Zero Prediction Accuracy | 0.5681 |

### Regression Metrics

| Metric | Overall | Non-zero Only |
|--------|---------|---------------|
| RMSE | 112.7988 | 135.3051 |
| MAE | 58.7042 | 74.6727 |
| R² | N/A | 0.0957 |

### Points Distribution

| Metric | Value |
|--------|-------|
| Total True Points | 148,754 |
| Total Predicted Points | 162,193 |
| Points Ratio (Pred/True) | 1.0903 |
| Mean True (Non-zero) | 71.90 |
| Mean Predicted (Non-zero) | 59.80 |

### Top 10 Most Important Features

| Rank | Feature | Importance |
|------|---------|------------|
| 1 | prior_wt_proportion_regressor | 352870196.09 |
| 2 | prior_pro_races_regressor | 156571611.70 |
| 3 | prior_d1_races_regressor | 149342340.67 |
| 4 | prior_one_day_races_regressor | 139827269.31 |
| 5 | rider_age_at_race_regressor | 117878035.80 |
| 6 | rf_winning_time_regressor | 99500911.30 |
| 7 | prior_wt_races_regressor | 88586400.30 |
| 8 | prior_gc_races_regressor | 66883926.60 |
| 9 | total_prior_races_regressor | 61269764.80 |
| 10 | rf_skewness_absolute_regressor | 53923604.00 |

## STAGE_ONE_DAY Model Performance

### Key Statistics
- **Zero inflation:** 76.5% of test samples have 0 points
- **Non-zero samples:** 7,144 out of 30,453
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
| AUC | 0.7820 |
| Precision | 0.0000 |
| Recall | 0.0000 |
| F1 Score | 0.0000 |
| Zero Prediction Accuracy | 1.0000 |

### Regression Metrics

| Metric | Overall | Non-zero Only |
|--------|---------|---------------|
| RMSE | 55.3776 | 114.3349 |
| MAE | 11.8238 | 50.4017 |
| R² | N/A | -0.2412 |

### Points Distribution

| Metric | Value |
|--------|-------|
| Total True Points | 360,070 |
| Total Predicted Points | 0 |
| Points Ratio (Pred/True) | 0.0000 |
| Mean True (Non-zero) | 50.40 |
| Mean Predicted (Non-zero) | 0.00 |

### Top 10 Most Important Features

| Rank | Feature | Importance |
|------|---------|------------|
| 1 | prior_wt_proportion_regressor | 352420161.19 |
| 2 | rkf_boundary_distance_regressor | 184703108.71 |
| 3 | prior_one_day_races_regressor | 182100443.00 |
| 4 | prior_d1_races_regressor | 179207994.43 |
| 5 | prior_pro_races_regressor | 148871676.70 |
| 6 | rider_age_at_race_regressor | 133023273.51 |
| 7 | prior_wt_races_regressor | 101568919.20 |
| 8 | prior_stage_races_regressor | 92877772.70 |
| 9 | total_prior_races_regressor | 82284573.39 |
| 10 | rf_clumpiness_score_regressor | 74785381.10 |