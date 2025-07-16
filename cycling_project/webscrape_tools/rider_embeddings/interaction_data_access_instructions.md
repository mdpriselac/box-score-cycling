# Interaction Data Access Instructions

## Overview

This guide provides instructions for accessing and using the interaction-based rider embeddings data for predictive modeling. The interaction embeddings represent how well a rider's historical performance patterns match the characteristics of the current race.

## Data Location

```
webscrape_tools/interaction_embeddings_db_optimized/
├── phase1/                    # Individual percentile interactions
│   ├── gc/
│   │   ├── dot_products.parquet
│   │   ├── hadamard_products.parquet
│   │   └── cosine_products.parquet
│   ├── stage/
│   ├── one_day/
│   ├── stage_one_day/
│   └── all/
├── phase2/                    # Matrix-level interactions (RECOMMENDED FOR ML)
│   ├── gc/
│   │   └── matrix_interactions.parquet
│   ├── stage/
│   ├── one_day/
│   ├── stage_one_day/
│   └── all/
└── extraction_metadata.json
```

## Quick Start for Predictive Modeling

### 1. Load Phase 2 Data (Recommended)

```python
import pandas as pd
import sqlite3

# Load the matrix interactions for a specific race type
race_type = 'stage'  # Options: gc, stage, one_day, stage_one_day, all
df = pd.read_parquet(f'interaction_embeddings_db_optimized/phase2/{race_type}/matrix_interactions.parquet')

print(f"Shape: {df.shape}")
print(f"Columns: {df.columns.tolist()[:10]}...")  # First 10 columns
```

### 2. Link to Database

```python
# Connect to database
conn = sqlite3.connect('database/database/cycling_races.db')

# Get rider_result details
query = """
SELECT 
    rr.id as rider_result_id,
    rr.rider_id,
    rr.competition_id,
    rr.uci_points_proportional,
    rr.final_gc_rank,
    c.name as competition_name,
    c.date as competition_date,
    c.competition_type,
    r.name as rider_name
FROM rider_results rr
JOIN competitions c ON rr.competition_id = c.id
JOIN riders r ON rr.rider_id = r.id
WHERE rr.id IN ({})
""".format(','.join(['?' for _ in df['rider_result_id']]))

metadata = pd.read_sql_query(query, conn, params=df['rider_result_id'].tolist())

# Merge with interaction data
model_data = df.merge(metadata, on='rider_result_id', how='left')
```

### 3. Prepare Features and Target

```python
# Extract feature columns (all except rider_result_id)
feature_columns = [col for col in df.columns if col != 'rider_result_id']
X = model_data[feature_columns]

# Common target variables
y_points = model_data['uci_points_proportional']  # Points earned
y_rank = model_data['final_gc_rank']              # Final rank (lower is better)

# Create binary target (e.g., top 10 finish)
y_top10 = (model_data['final_gc_rank'] <= 10).astype(int)
```

## Data Structure Details

### Phase 1 Data (Individual Percentiles)

#### Dot Products & Cosine Products
- **Columns**: `rider_result_id`, `percentile`, `value`
- **Description**: Single scalar value per rider per percentile
- **Use Case**: Analyzing percentile-specific performance patterns

```python
# Example: Load dot products for stage races
dots = pd.read_parquet('interaction_embeddings_db_optimized/phase1/stage/dot_products.parquet')
print(dots.head())
#    rider_result_id    percentile     value
# 0           123456  race_features_60  1234.5
# 1           123456  race_features_70  1456.7
```

#### Hadamard Products
- **Columns**: `rider_result_id`, `percentile`, `feature`, `value`
- **Description**: Element-wise product for each race feature
- **Use Case**: Understanding which specific features drive interactions

```python
# Example: Load Hadamard products for stage races
hadamard = pd.read_parquet('interaction_embeddings_db_optimized/phase1/stage/hadamard_products.parquet')
print(hadamard.head())
#    rider_result_id    percentile              feature    value
# 0           123456  race_features_60  proportion_in_groups  0.45
# 1           123456  race_features_60      avg_group_size    2.3
```

### Phase 2 Data (Matrix-Level) - RECOMMENDED

#### Matrix Interactions
- **Columns**: `rider_result_id`, `dot_product`, `cosine_similarity`, `hadamard_0` through `hadamard_295`
- **Description**: Consolidated interactions across all percentiles (8 percentiles × 37 features = 296 hadamard values)
- **Use Case**: Direct input for machine learning models
- **Feature count**: 299 total features (1 dot + 1 cosine + 296 hadamard + 1 rider_result_id)

```python
# Phase 2 structure
matrix = pd.read_parquet('interaction_embeddings_db_optimized/phase2/all/matrix_interactions.parquet')
print(f"Shape: {matrix.shape}")  # Example: (446, 299) for 'all' race type
print(matrix.columns[:10])       # First 10 columns
```

## Race Type Selection Guide

| Race Type | Description | When to Use |
|-----------|-------------|-------------|
| `gc` | General Classification races only | Predicting GC performance in stage races |
| `stage` | Stage races only | Predicting stage-specific performance |
| `one_day` | One-day races only | Predicting one-day race performance |
| `stage_one_day` | Stage and one-day races combined | Balanced road racing predictions |
| `all` | All race types | General performance predictions |

## Database Schema Reference

### Key Tables for Model Features

```sql
-- Competition details
SELECT * FROM competitions WHERE id = ?;
-- Columns: id, name, date, competition_type, etc.

-- Rider results (target variables)
SELECT * FROM rider_results WHERE id = ?;
-- Columns: id, rider_id, competition_id, uci_points_proportional, final_gc_rank, etc.

-- Race features (used to create interactions)
SELECT * FROM race_features_60 WHERE competition_id = ?;
-- Columns: competition_id, proportion_in_groups, avg_group_size, etc.
```

## Example: Complete Modeling Pipeline

```python
import pandas as pd
import sqlite3
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score

# 1. Load interaction data
race_type = 'stage'
df = pd.read_parquet(f'interaction_embeddings_db_optimized/phase2/{race_type}/matrix_interactions.parquet')

# 2. Get database connection
conn = sqlite3.connect('database/database/cycling_races.db')

# 3. Load target variables
target_query = """
SELECT 
    rr.id as rider_result_id,
    rr.uci_points_proportional,
    rr.final_gc_rank,
    c.date as competition_date,
    c.competition_type
FROM rider_results rr
JOIN competitions c ON rr.competition_id = c.id
WHERE rr.id IN ({})
""".format(','.join(['?' for _ in df['rider_result_id']]))

targets = pd.read_sql_query(target_query, conn, params=df['rider_result_id'].tolist())

# 4. Merge data
model_data = df.merge(targets, on='rider_result_id', how='inner')

# 5. Prepare features and target
feature_columns = [col for col in df.columns if col != 'rider_result_id']
X = model_data[feature_columns]
y = model_data['uci_points_proportional']

# 6. Split data (time-based)
model_data['competition_date'] = pd.to_datetime(model_data['competition_date'])
split_date = '2023-01-01'
train_mask = model_data['competition_date'] < split_date
test_mask = model_data['competition_date'] >= split_date

X_train, X_test = X[train_mask], X[test_mask]
y_train, y_test = y[train_mask], y[test_mask]

# 7. Train model
model = RandomForestRegressor(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# 8. Evaluate
y_pred = model.predict(X_test)
print(f"R² Score: {r2_score(y_test, y_pred):.4f}")
print(f"RMSE: {mean_squared_error(y_test, y_pred, squared=False):.4f}")

# 9. Feature importance
feature_importance = pd.DataFrame({
    'feature': feature_columns,
    'importance': model.feature_importances_
}).sort_values('importance', ascending=False)

print("\nTop 10 Most Important Features:")
print(feature_importance.head(10))
```

## Data Quality Notes

### Coverage by Race Type (10K Sample Results)
- **stage_one_day**: 9,682 riders (77.8%), comprehensive road racing
- **stage**: 771 riders (6.3%), stage race specialists
- **one_day**: 554 riders (3.4%), classics specialists
- **all**: 446 riders (3.2%), very experienced riders
- **gc**: 34 riders (0.2%), elite GC contenders - very selective!

### Missing Data Patterns
- Some riders lack sufficient historical data for certain race types
- Current minimum race requirements (40th percentile):
  - GC: 11 races (very selective - only 34 qualified)
  - Stage: 69 races  
  - One-day: 18 races
  - Stage_one_day: 82 races
  - All: 91 races
- Check `extraction_metadata.json` for detailed warnings

### Value Ranges
- **Dot products**: Wide range (varies by race type), consider normalization
- **Cosine similarity**: Bounded [-1, 1], interpretable as correlation strength
- **Hadamard products**: Feature-dependent ranges (37 features × 8 percentiles = 296 values), may need scaling

## Performance Tips

1. **Use Phase 2 data** for most modeling tasks (cleaner, more efficient)
2. **Filter by race type** to match your prediction target
3. **Time-based splits** are crucial for realistic evaluation
4. **Feature scaling** may improve model performance
5. **Consider ensemble methods** to handle the high-dimensional feature space
6. **Start with stage_one_day** for most riders (9,682 samples in 10K dataset)
7. **GC predictions** will have limited samples but highly specialized riders

## Troubleshooting

### Common Issues

**Q: Why do some race types have fewer samples?**
A: The system requires minimum historical races per type based on 40th percentile:
   - GC: 11 races (very selective, only elite riders qualify)
   - Stage: 69 races
   - One-day: 18 races  
   - Stage_one_day: 82 races
   - All: 91 races

**Q: What does rider_result_id represent?**
A: It's the unique identifier from the `rider_results` table, linking to a specific rider's performance in a specific competition.

**Q: Can I combine multiple race types?**
A: Yes, but ensure they make sense together. The 'all' race type already combines all types, or you can manually combine DataFrames.

**Q: How do I handle the wide value ranges?**
A: Consider StandardScaler or RobustScaler from scikit-learn, especially for neural networks.

## Contact

For questions about the interaction embeddings system, refer to the implementation in:
- `rider_embeddings/performance_feature_link/interaction_embeddings.py`
- `rider_embeddings/performance_feature_link/interaction_approach.md`