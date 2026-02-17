# Comprehensive Model Evaluation Report

Generated: 2026-01-04 18:51

## Overview

This report compares five prediction strategies for cycling race results:

1. **Random**: Random ranking of riders
2. **Bib Order**: Rank by team_bib * 10 + personal_bib (lower = better)
3. **Naive (Hist Avg)**: Rank by rider's historical average bucket
4. **Model Direct**: Direct bucket prediction from model (rounded)
5. **Model Ranking**: Ranking-derived buckets (force race ranking, then bucket)

## Data Summary

- **Total predictions**: 84,990
- **Top finishers (B0-4)**: 20,611

## Overall Results

### Threshold Identification Precision

*When we predict a rider will finish in the top X, what percentage actually do?*

| Strategy | Top 5 | Top 15 | Top 30 |
|----------|-------|--------|--------|
| Random | 4.3% | 13.2% | 26.2% |
| Bib Order | 9.9% | 19.3% | 32.0% |
| Naive (Hist Avg) | 19.9% | 31.7% | 44.7% |
| Model Direct | 44.9% | 53.0% | 52.7% |
| Model Ranking | 40.1% | 51.4% | 60.1% |

### Standard Metrics (Top Finishers B0-4 Only)

| Strategy | MAE | Exact | Within-1 | Practical Success |
|----------|-----|-------|----------|-------------------|
| Random | 2.157 | 9.8% | 29.1% | 91.4% |
| Bib Order | 1.999 | 11.3% | 33.4% | 90.3% |
| Naive (Hist Avg) | 1.711 | 16.7% | 44.5% | 85.7% |
| Model Direct | 0.916 | 34.2% | 80.9% | 87.2% |
| Model Ranking | 1.247 | 26.1% | 63.4% | 83.3% |

### Model Lift Over Baselines

*Relative improvement in Top 15 precision:*

- vs Random: **3.9x** improvement
- vs Bib Order: **2.7x** improvement
- vs Naive (Hist Avg): **1.6x** improvement (62% relative)

## Race Type Breakdown

### Threshold Precision by Race Type

*When we predict top 15, what % actually finish top 15 or better?*

| Type | N | Random | Bib | Naive | Model Direct | Model Ranking |
|-|-|-|-|-|-|-|
| Stage | 14,651 | 11.9% | 17.2% | 27.6% | 54.0% | 51.0% |
| One_Day | 3,671 | 17.5% | 24.5% | 41.1% | 48.6% | 49.3% |
| Gc | 2,289 | 14.3% | 23.8% | 42.9% | 54.5% | 57.3% |

### Practical Success by Race Type (Top Finishers)

*When predicting bucket X, what % finish at bucket X or better?*

| Type | Random | Bib | Naive | Model Direct | Model Ranking |
|-|-|-|-|-|-|
| Stage | 92.1% | 90.8% | 86.3% | 88.0% | 83.2% |
| One_Day | 89.3% | 89.0% | 84.9% | 86.2% | 84.4% |
| Gc | 90.6% | 88.9% | 82.9% | 83.9% | 81.8% |

### MAE by Race Type (Top Finishers)

| Type | Random | Bib | Naive | Model Direct | Model Ranking |
|-|-|-|-|-|-|
| Stage | 2.21 | 2.07 | 1.83 | 0.95 | 1.27 |
| One_Day | 1.98 | 1.81 | 1.43 | 0.83 | 1.24 |
| Gc | 2.08 | 1.84 | 1.43 | 0.81 | 1.08 |

## Tour Level Breakdown

### Threshold Precision by Tour Level

*When we predict top 15, what % actually finish top 15 or better?*

| Level | N | Random | Bib | Naive | Model Direct | Model Ranking |
|-|-|-|-|-|-|-|
| WT | 10,004 | 10.6% | 14.9% | 30.2% | 54.4% | 51.7% |
| PRO | 5,007 | 14.2% | 20.3% | 32.2% | 51.2% | 50.6% |
| D1 | 5,600 | 16.6% | 25.7% | 33.8% | 52.2% | 51.6% |

### Practical Success by Tour Level (Top Finishers)

*When predicting bucket X, what % finish at bucket X or better?*

| Level | Random | Bib | Naive | Model Direct | Model Ranking |
|-|-|-|-|-|-|
| WT | 92.9% | 91.8% | 86.0% | 87.9% | 83.4% |
| PRO | 91.3% | 91.0% | 86.6% | 87.4% | 84.4% |
| D1 | 89.1% | 86.9% | 84.3% | 85.9% | 82.0% |

### MAE by Tour Level (Top Finishers)

| Level | Random | Bib | Naive | Model Direct | Model Ranking |
|-|-|-|-|-|-|
| WT | 2.27 | 2.18 | 1.79 | 0.94 | 1.26 |
| PRO | 2.12 | 1.90 | 1.70 | 0.91 | 1.26 |
| D1 | 1.99 | 1.77 | 1.58 | 0.88 | 1.22 |

## Race Profile Breakdown

### Threshold Precision by Race Profile

*When we predict top 15, what % actually finish top 15 or better?*

| Profile | N | Random | Bib | Naive | Model Direct | Model Ranking |
|-|-|-|-|-|-|-|
| Rolling | 10,164 | 14.5% | 22.3% | 38.8% | 50.7% | 50.3% |
| Sprint | 4,605 | 11.7% | 13.6% | 16.7% | 58.4% | 57.1% |
| Hilly | 2,175 | 12.7% | 15.9% | 24.7% | 49.8% | 45.7% |
| Time_Trial | 1,378 | 10.8% | 21.8% | 29.5% | 57.8% | 52.8% |
| Mountain | 1,040 | 10.7% | 20.8% | 39.2% | 54.5% | 54.3% |
| Breakaway | 1,249 | 13.5% | 17.2% | 37.8% | 49.0% | 44.7% |

### Practical Success by Race Profile (Top Finishers)

*When predicting bucket X, what % finish at bucket X or better?*

| Profile | Random | Bib | Naive | Model Direct | Model Ranking |
|-|-|-|-|-|-|
| Rolling | 90.7% | 89.5% | 83.5% | 86.1% | 82.0% |
| Sprint | 92.2% | 92.3% | 90.8% | 87.1% | 85.3% |
| Hilly | 92.2% | 91.6% | 86.5% | 92.1% | 86.6% |
| Time_Trial | 92.5% | 88.8% | 86.6% | 89.0% | 83.3% |
| Mountain | 93.5% | 89.5% | 84.6% | 84.0% | 80.1% |
| Breakaway | 90.6% | 89.0% | 82.8% | 89.3% | 82.8% |

### MAE by Race Profile (Top Finishers)

| Profile | Random | Bib | Naive | Model Direct | Model Ranking |
|-|-|-|-|-|-|
| Rolling | 2.10 | 1.90 | 1.53 | 0.90 | 1.26 |
| Sprint | 2.23 | 2.17 | 2.03 | 0.93 | 1.17 |
| Hilly | 2.16 | 2.08 | 1.85 | 0.95 | 1.37 |
| Time_Trial | 2.26 | 2.00 | 1.85 | 0.90 | 1.20 |
| Mountain | 2.28 | 2.04 | 1.66 | 0.90 | 1.13 |
| Breakaway | 2.14 | 2.00 | 1.62 | 0.95 | 1.34 |

## Key Insights

### Model Performance by Race Profile

- **Best**: Sprint (57.1% top-15 precision)
- **Worst**: Breakaway (44.7% top-15 precision)

### Model Performance by Race Type

- **Best**: Gc (57.3% top-15 precision)

## Summary

| Comparison | Top 5 Precision | Top 15 Precision | Top 30 Precision |
|------------|-----------------|------------------|------------------|
| Random | 4.3% | 13.2% | 26.2% |
| Bib Order | 9.9% | 19.3% | 32.0% |
| Naive (Hist Avg) | 19.9% | 31.7% | 44.7% |
| Model Direct | 44.9% | 53.0% | 52.7% |
| Model Ranking | 40.1% | 51.4% | 60.1% |

---

*Report generated by comprehensive_evaluation.py*