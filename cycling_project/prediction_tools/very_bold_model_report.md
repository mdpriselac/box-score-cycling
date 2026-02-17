# Very Bold 0.3x Model Performance Report

Generated: 2026-01-04

## Model Configuration

- **Model**: Very Bold 0.3x (Asymmetric Loss)
- **Asymmetry Ratio**: 0.3 (penalizes under-prediction 3.3x more than over-prediction)
- **Training Data**: 2018-2022 (267,445 samples)
- **Test Data**: 2023 (59,279 samples), 2024 (84,989 samples)
- **Base Model**: LightGBM with custom asymmetric objective

## Bucket Definitions

| Bucket | Name | Places |
|--------|------|--------|
| 0 | Winner | 1st |
| 1 | Podium | 2nd-3rd |
| 2 | Top 5 | 4th-5th |
| 3 | Top 15 | 6th-15th |
| 4 | Top 30 | 16th-30th |
| 5 | Top 50 | 31st-50th |
| 6 | Finisher | 51st+ |

## Key Metrics Explained

- **MAE**: Mean Absolute Error in bucket prediction
- **Exact**: Percentage of predictions in exactly the right bucket
- **Within-1**: Percentage of predictions within 1 bucket of actual
- **Practical Success**: Rider finished at least as good as predicted (actual ≤ predicted)

---

## Overall Performance

### 2023 Test Set

| Scope | N | MAE | Exact | Within-1 | Practical |
|-------|---|-----|-------|----------|-----------|
| All Buckets | 59,279 | 0.737 | 52.8% | 81.5% | 75.6% |
| Top Finishers (B0-4) | 15,753 | 1.282 | 24.9% | 62.2% | 82.6% |

### 2024 Test Set

| Scope | N | MAE | Exact | Within-1 | Practical |
|-------|---|-----|-------|----------|-----------|
| All Buckets | 84,989 | 0.689 | 55.9% | 82.4% | 78.1% |
| Top Finishers (B0-4) | 20,611 | 1.303 | 24.1% | 60.5% | 83.7% |

---

## Performance by Race Type

### 2023

| Type | N | N (B0-4) | MAE (B0-4) | Exact (B0-4) | Within-1 (B0-4) | Practical (B0-4) |
|------|---|----------|------------|--------------|-----------------|------------------|
| Stage | 43,700 | 10,837 | 1.313 | 24.3% | 60.8% | 82.5% |
| One Day | 9,253 | 3,066 | 1.273 | 24.3% | 62.1% | 83.9% |
| Gc | 6,326 | 1,850 | 1.111 | 29.2% | 70.6% | 81.3% |

### 2024

| Type | N | N (B0-4) | MAE (B0-4) | Exact (B0-4) | Within-1 (B0-4) | Practical (B0-4) |
|------|---|----------|------------|--------------|-----------------|------------------|
| Stage | 64,692 | 14,651 | 1.334 | 23.7% | 59.0% | 83.7% |
| One Day | 12,081 | 3,671 | 1.307 | 22.6% | 60.4% | 84.8% |
| Gc | 8,216 | 2,289 | 1.100 | 29.3% | 69.8% | 81.9% |

---

## Performance by Tour Level

### 2023

| Level | N | N (B0-4) | MAE (B0-4) | Exact (B0-4) | Within-1 (B0-4) | Practical (B0-4) |
|-------|---|----------|------------|--------------|-----------------|------------------|
| WT | 23,684 | 4,971 | 1.345 | 24.0% | 59.2% | 83.4% |
| PRO | 18,732 | 5,291 | 1.283 | 24.4% | 62.3% | 82.7% |
| D1 | 16,863 | 5,491 | 1.223 | 26.2% | 64.9% | 81.8% |

### 2024

| Level | N | N (B0-4) | MAE (B0-4) | Exact (B0-4) | Within-1 (B0-4) | Practical (B0-4) |
|-------|---|----------|------------|--------------|-----------------|------------------|
| WT | 47,884 | 10,004 | 1.311 | 24.5% | 59.7% | 83.8% |
| PRO | 18,819 | 5,007 | 1.322 | 22.9% | 59.8% | 84.5% |
| D1 | 18,286 | 5,600 | 1.271 | 24.5% | 62.4% | 82.6% |

---

## Performance by Race Profile

### 2023

| Profile | N | N (B0-4) | MAE (B0-4) | Exact (B0-4) | Within-1 (B0-4) | Practical (B0-4) |
|---------|---|----------|------------|--------------|-----------------|------------------|
| Sprint | 12,958 | 3,270 | 1.161 | 27.1% | 66.3% | 83.5% |
| Mountain | 2,196 | 518 | 1.280 | 27.2% | 63.1% | 79.0% |
| Hilly | 7,420 | 1,992 | 1.382 | 21.7% | 56.0% | 85.4% |
| Rolling | 29,913 | 8,326 | 1.300 | 24.8% | 62.6% | 81.6% |
| Breakaway | 2,902 | 754 | 1.350 | 23.7% | 56.1% | 84.9% |
| Time Trial | 3,890 | 893 | 1.272 | 24.6% | 62.0% | 83.5% |

### 2024

| Profile | N | N (B0-4) | MAE (B0-4) | Exact (B0-4) | Within-1 (B0-4) | Practical (B0-4) |
|---------|---|----------|------------|--------------|-----------------|------------------|
| Sprint | 20,453 | 4,605 | 1.221 | 26.2% | 61.7% | 85.3% |
| Mountain | 4,801 | 1,040 | 1.209 | 26.9% | 66.1% | 82.3% |
| Hilly | 9,334 | 2,175 | 1.418 | 20.5% | 53.2% | 87.9% |
| Rolling | 39,083 | 10,164 | 1.319 | 24.0% | 61.1% | 82.3% |
| Breakaway | 4,767 | 1,249 | 1.417 | 19.7% | 56.4% | 83.7% |
| Time Trial | 6,551 | 1,378 | 1.244 | 25.1% | 62.6% | 82.8% |

---

## Notes

- **Ranking-Derived Buckets**: Predictions are continuous values converted to race rankings, then bucketed based on predicted rank within each race
- **Bold Loss Function**: The asymmetric loss encourages the model to make more optimistic predictions, improving identification of top finishers at the cost of slightly higher over-prediction rate
- **Practical Success**: High practical success (~83%) means the model rarely over-promises; when wrong, it tends to under-predict rather than over-predict
