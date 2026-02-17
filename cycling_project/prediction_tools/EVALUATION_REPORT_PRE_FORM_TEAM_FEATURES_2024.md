# Comprehensive Model Evaluation Report

Generated: 2026-01-04 16:11

## Overview

This report compares five prediction strategies for cycling race results:

1. **Random**: Random ranking of riders
2. **Bib Order**: Rank by team_bib * 10 + personal_bib (lower = better)
3. **Naive (Hist Avg)**: Rank by rider's historical average bucket
4. **Model Direct**: Direct bucket prediction from model (rounded)
5. **Model Ranking**: Ranking-derived buckets (force race ranking, then bucket)

## Data Summary

- **Total predictions**: 144,268
- **Top finishers (B0-4)**: 36,364

## Overall Results

### Threshold Identification Precision

*When we predict a rider will finish in the top X, what percentage actually do?*

| Strategy | Top 5 | Top 15 | Top 30 |
|----------|-------|--------|--------|
| Random | 4.8% | 13.8% | 27.6% |
| Bib Order | 10.6% | 20.2% | 33.8% |
| Naive (Hist Avg) | 19.2% | 31.8% | 45.0% |
| Model Direct | 45.4% | 53.2% | 52.3% |
| Model Ranking | 36.5% | 49.3% | 58.1% |

### Standard Metrics (Top Finishers B0-4 Only)

| Strategy | MAE | Exact | Within-1 | Practical Success |
|----------|-----|-------|----------|-------------------|
| Random | 2.114 | 10.6% | 31.0% | 91.2% |
| Bib Order | 1.951 | 12.1% | 35.4% | 89.7% |
| Naive (Hist Avg) | 1.693 | 16.8% | 45.4% | 85.4% |
| Model Direct | 0.955 | 32.7% | 79.5% | 89.3% |
| Model Ranking | 1.294 | 24.4% | 61.2% | 83.2% |

### Model Lift Over Baselines

*Relative improvement in Top 15 precision:*

- vs Random: **3.6x** improvement
- vs Bib Order: **2.4x** improvement
- vs Naive (Hist Avg): **1.6x** improvement (55% relative)

## Year Breakdown

### Threshold Precision by Year

*When we predict top 15, what % actually finish top 15 or better?*

| Year | N | Random | Bib | Naive | Model Direct | Model Ranking |
|-|-|-|-|-|-|-|
| 2023 | 15,753 | 14.8% | 21.5% | 31.9% | 53.2% | 49.1% |
| 2024 | 20,611 | 13.0% | 19.3% | 31.7% | 53.1% | 49.5% |

### Practical Success by Year (Top Finishers)

*When predicting bucket X, what % finish at bucket X or better?*

| Year | Random | Bib | Naive | Model Direct | Model Ranking |
|-|-|-|-|-|-|
| 2023 | 90.4% | 88.9% | 85.1% | 89.1% | 82.6% |
| 2024 | 91.8% | 90.3% | 85.7% | 89.5% | 83.7% |

### MAE by Year (Top Finishers)

| Year | Random | Bib | Naive | Model Direct | Model Ranking |
|-|-|-|-|-|-|
| 2023 | 2.07 | 1.89 | 1.67 | 0.95 | 1.28 |
| 2024 | 2.15 | 2.00 | 1.71 | 0.96 | 1.30 |

## Race Type Breakdown

### Threshold Precision by Race Type

*When we predict top 15, what % actually finish top 15 or better?*

| Type | N | Random | Bib | Naive | Model Direct | Model Ranking |
|-|-|-|-|-|-|-|
| Stage | 25,488 | 12.6% | 18.3% | 27.9% | 53.7% | 48.9% |
| One_Day | 6,737 | 17.9% | 25.4% | 41.0% | 49.3% | 47.0% |
| Gc | 4,139 | 14.3% | 24.1% | 40.9% | 56.9% | 55.8% |

### Practical Success by Race Type (Top Finishers)

*When predicting bucket X, what % finish at bucket X or better?*

| Type | Random | Bib | Naive | Model Direct | Model Ranking |
|-|-|-|-|-|-|
| Stage | 91.9% | 90.2% | 86.0% | 90.0% | 83.2% |
| One_Day | 88.9% | 88.4% | 85.0% | 88.2% | 84.4% |
| Gc | 90.1% | 88.7% | 82.8% | 87.0% | 81.6% |

### MAE by Race Type (Top Finishers)

| Type | Random | Bib | Naive | Model Direct | Model Ranking |
|-|-|-|-|-|-|
| Stage | 2.17 | 2.02 | 1.80 | 0.99 | 1.33 |
| One_Day | 1.93 | 1.77 | 1.41 | 0.88 | 1.29 |
| Gc | 2.06 | 1.81 | 1.47 | 0.83 | 1.11 |

## Tour Level Breakdown

### Threshold Precision by Tour Level

*When we predict top 15, what % actually finish top 15 or better?*

| Level | N | Random | Bib | Naive | Model Direct | Model Ranking |
|-|-|-|-|-|-|-|
| WT | 14,975 | 10.9% | 14.8% | 30.0% | 56.7% | 50.6% |
| PRO | 10,298 | 14.3% | 22.2% | 32.3% | 51.0% | 48.6% |
| D1 | 11,091 | 17.0% | 25.3% | 33.6% | 51.2% | 48.4% |

### Practical Success by Tour Level (Top Finishers)

*When predicting bucket X, what % finish at bucket X or better?*

| Level | Random | Bib | Naive | Model Direct | Model Ranking |
|-|-|-|-|-|-|
| WT | 93.1% | 91.6% | 86.1% | 91.0% | 83.7% |
| PRO | 91.2% | 89.6% | 85.8% | 88.7% | 83.6% |
| D1 | 88.6% | 87.2% | 84.2% | 87.7% | 82.2% |

### MAE by Tour Level (Top Finishers)

| Level | Random | Bib | Naive | Model Direct | Model Ranking |
|-|-|-|-|-|-|
| WT | 2.27 | 2.17 | 1.78 | 1.00 | 1.32 |
| PRO | 2.09 | 1.87 | 1.69 | 0.96 | 1.30 |
| D1 | 1.92 | 1.73 | 1.57 | 0.89 | 1.25 |

## Race Profile Breakdown

### Threshold Precision by Race Profile

*When we predict top 15, what % actually finish top 15 or better?*

| Profile | N | Random | Bib | Naive | Model Direct | Model Ranking |
|-|-|-|-|-|-|-|
| Rolling | 18,490 | 14.4% | 23.3% | 38.2% | 51.0% | 47.5% |
| Sprint | 7,875 | 13.1% | 14.9% | 18.4% | 58.7% | 56.4% |
| Hilly | 4,167 | 14.3% | 17.3% | 26.9% | 49.1% | 45.0% |
| Time_Trial | 2,271 | 12.0% | 21.5% | 27.9% | 57.9% | 51.1% |
| Breakaway | 2,003 | 14.6% | 18.8% | 37.7% | 48.2% | 42.8% |
| Mountain | 1,558 | 10.4% | 20.0% | 35.3% | 56.0% | 51.9% |

### Practical Success by Race Profile (Top Finishers)

*When predicting bucket X, what % finish at bucket X or better?*

| Profile | Random | Bib | Naive | Model Direct | Model Ranking |
|-|-|-|-|-|-|
| Rolling | 90.6% | 89.0% | 83.5% | 88.9% | 81.9% |
| Sprint | 91.9% | 91.4% | 89.9% | 87.9% | 84.6% |
| Hilly | 91.2% | 90.4% | 85.9% | 92.5% | 86.7% |
| Time_Trial | 92.3% | 89.1% | 87.1% | 90.6% | 83.1% |
| Breakaway | 91.5% | 89.2% | 83.6% | 91.6% | 84.2% |
| Mountain | 92.0% | 88.9% | 84.1% | 89.0% | 81.2% |

### MAE by Race Profile (Top Finishers)

| Profile | Random | Bib | Naive | Model Direct | Model Ranking |
|-|-|-|-|-|-|
| Rolling | 2.07 | 1.86 | 1.54 | 0.94 | 1.31 |
| Sprint | 2.17 | 2.11 | 1.98 | 0.95 | 1.20 |
| Hilly | 2.12 | 2.02 | 1.79 | 1.01 | 1.40 |
| Time_Trial | 2.23 | 1.97 | 1.86 | 0.98 | 1.25 |
| Breakaway | 2.06 | 1.97 | 1.60 | 1.00 | 1.39 |
| Mountain | 2.22 | 2.01 | 1.68 | 0.94 | 1.23 |

## Key Insights

### Model Performance by Race Profile

- **Best**: Sprint (56.4% top-15 precision)
- **Worst**: Breakaway (42.8% top-15 precision)

### Model Performance by Race Type

- **Best**: Gc (55.8% top-15 precision)

## Summary

| Comparison | Top 5 Precision | Top 15 Precision | Top 30 Precision |
|------------|-----------------|------------------|------------------|
| Random | 4.8% | 13.8% | 27.6% |
| Bib Order | 10.6% | 20.2% | 33.8% |
| Naive (Hist Avg) | 19.2% | 31.8% | 45.0% |
| Model Direct | 45.4% | 53.2% | 52.3% |
| Model Ranking | 36.5% | 49.3% | 58.1% |

---

*Report generated by comprehensive_evaluation.py*