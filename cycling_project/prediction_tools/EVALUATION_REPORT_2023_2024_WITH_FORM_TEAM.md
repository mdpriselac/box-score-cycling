# Comprehensive Model Evaluation Report

Generated: 2026-01-04 17:29

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
| Random | 4.3% | 13.8% | 27.7% |
| Bib Order | 10.6% | 20.2% | 33.8% |
| Naive (Hist Avg) | 19.2% | 31.8% | 45.0% |
| Model Direct | 45.1% | 53.9% | 53.7% |
| Model Ranking | 37.8% | 51.1% | 60.4% |

### Standard Metrics (Top Finishers B0-4 Only)

| Strategy | MAE | Exact | Within-1 | Practical Success |
|----------|-----|-------|----------|-------------------|
| Random | 2.117 | 10.6% | 30.9% | 91.1% |
| Bib Order | 1.951 | 12.1% | 35.4% | 89.7% |
| Naive (Hist Avg) | 1.693 | 16.8% | 45.4% | 85.4% |
| Model Direct | 0.927 | 34.3% | 80.3% | 88.1% |
| Model Ranking | 1.247 | 26.1% | 63.6% | 82.5% |

### Model Lift Over Baselines

*Relative improvement in Top 15 precision:*

- vs Random: **3.7x** improvement
- vs Bib Order: **2.5x** improvement
- vs Naive (Hist Avg): **1.6x** improvement (61% relative)

## Year Breakdown

### Threshold Precision by Year

*When we predict top 15, what % actually finish top 15 or better?*

| Year | N | Random | Bib | Naive | Model Direct | Model Ranking |
|-|-|-|-|-|-|-|
| 2023 | 15,753 | 14.8% | 21.5% | 31.9% | 54.1% | 51.1% |
| 2024 | 20,611 | 13.0% | 19.3% | 31.7% | 53.8% | 51.1% |

### Practical Success by Year (Top Finishers)

*When predicting bucket X, what % finish at bucket X or better?*

| Year | Random | Bib | Naive | Model Direct | Model Ranking |
|-|-|-|-|-|-|
| 2023 | 90.4% | 88.9% | 85.1% | 87.6% | 81.8% |
| 2024 | 91.6% | 90.3% | 85.7% | 88.4% | 83.1% |

### MAE by Year (Top Finishers)

| Year | Random | Bib | Naive | Model Direct | Model Ranking |
|-|-|-|-|-|-|
| 2023 | 2.07 | 1.89 | 1.67 | 0.92 | 1.24 |
| 2024 | 2.16 | 2.00 | 1.71 | 0.94 | 1.25 |

## Race Type Breakdown

### Threshold Precision by Race Type

*When we predict top 15, what % actually finish top 15 or better?*

| Type | N | Random | Bib | Naive | Model Direct | Model Ranking |
|-|-|-|-|-|-|-|
| Stage | 25,488 | 12.5% | 18.3% | 27.9% | 54.5% | 50.6% |
| One_Day | 6,737 | 17.2% | 25.4% | 41.0% | 50.7% | 49.8% |
| Gc | 4,139 | 15.9% | 24.1% | 40.9% | 56.7% | 56.1% |

### Practical Success by Race Type (Top Finishers)

*When predicting bucket X, what % finish at bucket X or better?*

| Type | Random | Bib | Naive | Model Direct | Model Ranking |
|-|-|-|-|-|-|
| Stage | 91.7% | 90.2% | 86.0% | 88.6% | 82.3% |
| One_Day | 89.0% | 88.4% | 85.0% | 87.5% | 84.0% |
| Gc | 90.6% | 88.7% | 82.8% | 85.6% | 81.4% |

### MAE by Race Type (Top Finishers)

| Type | Random | Bib | Naive | Model Direct | Model Ranking |
|-|-|-|-|-|-|
| Stage | 2.17 | 2.02 | 1.80 | 0.96 | 1.27 |
| One_Day | 1.95 | 1.77 | 1.41 | 0.85 | 1.25 |
| Gc | 2.05 | 1.81 | 1.47 | 0.84 | 1.09 |

## Tour Level Breakdown

### Threshold Precision by Tour Level

*When we predict top 15, what % actually finish top 15 or better?*

| Level | N | Random | Bib | Naive | Model Direct | Model Ranking |
|-|-|-|-|-|-|-|
| WT | 14,975 | 10.2% | 14.8% | 30.0% | 56.0% | 51.7% |
| PRO | 10,298 | 14.5% | 22.2% | 32.3% | 52.5% | 51.0% |
| D1 | 11,091 | 17.5% | 25.3% | 33.6% | 52.9% | 50.4% |

### Practical Success by Tour Level (Top Finishers)

*When predicting bucket X, what % finish at bucket X or better?*

| Level | Random | Bib | Naive | Model Direct | Model Ranking |
|-|-|-|-|-|-|
| WT | 93.2% | 91.6% | 86.1% | 89.4% | 83.1% |
| PRO | 90.7% | 89.6% | 85.8% | 87.3% | 83.1% |
| D1 | 88.5% | 87.2% | 84.2% | 86.9% | 81.3% |

### MAE by Tour Level (Top Finishers)

| Level | Random | Bib | Naive | Model Direct | Model Ranking |
|-|-|-|-|-|-|
| WT | 2.27 | 2.17 | 1.78 | 0.98 | 1.28 |
| PRO | 2.09 | 1.87 | 1.69 | 0.92 | 1.25 |
| D1 | 1.93 | 1.73 | 1.57 | 0.87 | 1.20 |

## Race Profile Breakdown

### Threshold Precision by Race Profile

*When we predict top 15, what % actually finish top 15 or better?*

| Profile | N | Random | Bib | Naive | Model Direct | Model Ranking |
|-|-|-|-|-|-|-|
| Rolling | 18,490 | 14.9% | 23.3% | 38.2% | 51.7% | 49.5% |
| Sprint | 7,875 | 13.4% | 14.9% | 18.4% | 59.0% | 57.6% |
| Hilly | 4,167 | 13.8% | 17.3% | 26.9% | 49.9% | 45.6% |
| Time_Trial | 2,271 | 10.0% | 21.5% | 27.9% | 58.3% | 52.6% |
| Breakaway | 2,003 | 11.4% | 18.8% | 37.7% | 51.5% | 47.1% |
| Mountain | 1,558 | 11.1% | 20.0% | 35.3% | 59.5% | 54.0% |

### Practical Success by Race Profile (Top Finishers)

*When predicting bucket X, what % finish at bucket X or better?*

| Profile | Random | Bib | Naive | Model Direct | Model Ranking |
|-|-|-|-|-|-|
| Rolling | 90.8% | 89.0% | 83.5% | 87.4% | 81.3% |
| Sprint | 91.7% | 91.4% | 89.9% | 86.6% | 84.0% |
| Hilly | 90.3% | 90.4% | 85.9% | 91.2% | 85.9% |
| Time_Trial | 92.1% | 89.1% | 87.1% | 90.6% | 83.7% |
| Breakaway | 89.7% | 89.2% | 83.6% | 90.3% | 82.5% |
| Mountain | 92.9% | 88.9% | 84.1% | 88.4% | 79.5% |

### MAE by Race Profile (Top Finishers)

| Profile | Random | Bib | Naive | Model Direct | Model Ranking |
|-|-|-|-|-|-|
| Rolling | 2.07 | 1.86 | 1.54 | 0.92 | 1.27 |
| Sprint | 2.16 | 2.11 | 1.98 | 0.92 | 1.16 |
| Hilly | 2.11 | 2.02 | 1.79 | 0.97 | 1.34 |
| Time_Trial | 2.26 | 1.97 | 1.86 | 0.95 | 1.22 |
| Breakaway | 2.14 | 1.97 | 1.60 | 0.94 | 1.32 |
| Mountain | 2.20 | 2.01 | 1.68 | 0.89 | 1.15 |

## Key Insights

### Model Performance by Race Profile

- **Best**: Sprint (57.6% top-15 precision)
- **Worst**: Hilly (45.6% top-15 precision)

### Model Performance by Race Type

- **Best**: Gc (56.1% top-15 precision)

## Summary

| Comparison | Top 5 Precision | Top 15 Precision | Top 30 Precision |
|------------|-----------------|------------------|------------------|
| Random | 4.3% | 13.8% | 27.7% |
| Bib Order | 10.6% | 20.2% | 33.8% |
| Naive (Hist Avg) | 19.2% | 31.8% | 45.0% |
| Model Direct | 45.1% | 53.9% | 53.7% |
| Model Ranking | 37.8% | 51.1% | 60.4% |

---

*Report generated by comprehensive_evaluation.py*