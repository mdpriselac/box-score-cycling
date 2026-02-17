# Cycling Race Prediction System - User Guide

A modular system for predicting cycling race outcomes using gradient boosting models.

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Data Pipeline](#data-pipeline)
4. [Training Models](#training-models)
5. [Making Predictions](#making-predictions)
6. [Evaluation](#evaluation)
7. [Saving and Loading Models](#saving-and-loading-models)
8. [API Reference](#api-reference)
9. [Performance Benchmarks](#performance-benchmarks)

---

## Overview

The prediction system consists of three main models:

| Model | Purpose | Output |
|-------|---------|--------|
| **Bucket Predictor** | Predict finish position category | Bucket 0-7 (ordinal) |
| **Time Gap Predictor** | Predict time behind winner | Seconds (continuous) |
| **Race Ranking Predictor** | Predict complete race order | Ranked list of riders |

### Bucket Scale

| Bucket | Place Range | Description |
|--------|-------------|-------------|
| 0 | 1st | Winner |
| 1 | 2nd-3rd | Podium |
| 2 | 4th-5th | Top 5 |
| 3 | 6th-15th | Top 15 |
| 4 | 16th-30th | Top 30 |
| 5 | 31st-50th | Top 50 |
| 6 | 51st+ | Finisher |
| 7 | DNF/DNS/OTL | Did not finish |

### Dependencies

```python
lightgbm
pandas
numpy
scipy
scikit-learn
optuna  # optional, for hyperparameter tuning
```

---

## Quick Start

### Train and Evaluate in One Step

```python
from prediction_tools import train_prediction_system, print_evaluation_report

# Train with default settings (2018+ data, temporal split)
results = train_prediction_system()

# View evaluation results
print_evaluation_report(results['evaluation'])

# Access trained models
bucket_predictor = results['bucket_predictor']
time_gap_predictor = results['time_gap_predictor']
race_ranker = results['race_ranker']
```

### Make Predictions

```python
from prediction_tools import RacePredictionAPI

# Load pre-trained models
api = RacePredictionAPI.load('models/prediction_system')

# Predict a race
predictions = api.predict_race(competition_id=12345)
print(predictions.head(10))

# Predict individual rider
result = api.predict_rider(rider_id=177, competition_id=12345)
print(f"Predicted bucket: {result['predicted_bucket']}")
print(f"Confidence: {result['confidence']:.1%}")
```

---

## Data Pipeline

### Loading Training Data

```python
from prediction_tools import CyclingDataPipeline, DataConfig

# Default configuration
pipeline = CyclingDataPipeline()

# Or customize
config = DataConfig(
    start_date='2018-01-01',      # Training data start
    min_races_career=10,           # Minimum career races for riders
    competition_types=['stage', 'one_day', 'gc'],
    race_categories=['wt', 'pro', 'd1'],
)
pipeline = CyclingDataPipeline(config)

# Load all training data
df = pipeline.load_training_data()
print(f"Loaded {len(df):,} samples")
```

### Temporal Train/Val/Test Split

```python
# Split by date (prevents data leakage)
train, val, test = pipeline.get_temporal_split(
    df,
    train_end='2022-12-31',    # Train: 2018-01-01 to 2022-12-31
    val_end='2023-06-30'       # Val: 2023-01-01 to 2023-06-30
                                # Test: 2023-07-01 onwards
)

print(f"Train: {len(train):,}")
print(f"Val:   {len(val):,}")
print(f"Test:  {len(test):,}")
```

### Loading Race Data for Prediction

```python
# Load a specific race's start list
race_df = pipeline.load_race_startlist(competition_id=12345)

# Include actual results (for evaluation)
race_df = pipeline.load_race_startlist(
    competition_id=12345,
    include_targets=True
)

# List available races in a date range
races = pipeline.load_races_in_range('2024-01-01', '2024-06-30')
print(races[['competition_id', 'competition_name', 'field_size']])
```

### Data Summary

```python
summary = pipeline.get_data_summary()
print(f"Total snapshots: {summary['total_rider_snapshots']:,}")
print(f"Total competitions: {summary['total_competitions']:,}")
print(f"Date range: {summary['date_range']}")
print(f"By type: {summary['by_competition_type']}")
```

---

## Training Models

### Training the Bucket Predictor

```python
from prediction_tools import OrdinalBucketPredictor, BucketPredictorConfig

# Configure model
config = BucketPredictorConfig(
    n_estimators=500,
    early_stopping_rounds=50,
    use_sample_weights=True,  # Handle class imbalance
)

# LightGBM parameters can be customized
config.lgb_params.update({
    'num_leaves': 63,
    'learning_rate': 0.05,
})

# Train
predictor = OrdinalBucketPredictor(config)
info = predictor.train(train, val, verbose=True)

print(f"Best iteration: {info['best_iteration']}")
print(f"Features: {info['n_features']}")
```

### Training the Time Gap Predictor

```python
from prediction_tools import TimeGapPredictor, TimeGapPredictorConfig

config = TimeGapPredictorConfig(
    n_estimators=500,
    early_stopping_rounds=50,
    log_transform_target=True,  # Better distribution
    exclude_winners=True,       # Winners have 0 gap
    max_time_gap=3600.0,        # Cap outliers at 1 hour
)

predictor = TimeGapPredictor(config)
info = predictor.train(train, val, verbose=True)

print(f"Training samples: {info['train_samples']:,}")
```

### Creating the Race Ranker

```python
from prediction_tools import RaceRankingPredictor, RaceRankingConfig

# Combine models into a race ranker
config = RaceRankingConfig(
    ranking_method='expected_bucket',  # or 'time_gap', 'ensemble'
    ensemble_weights=(0.7, 0.3),       # For ensemble method
)

ranker = RaceRankingPredictor(
    bucket_predictor=bucket_pred,
    time_gap_predictor=time_gap_pred,  # Optional
    config=config
)
```

### Full Training Pipeline

```python
from prediction_tools import ModelTrainer, TrainingConfig

config = TrainingConfig(
    # Data
    start_date='2018-01-01',
    train_end_date='2022-12-31',
    val_end_date='2023-06-30',
    min_races_career=10,

    # Model
    bucket_n_estimators=500,
    bucket_early_stopping=50,
    time_gap_n_estimators=500,
    time_gap_early_stopping=50,

    # Options
    train_time_gap=True,
    ranking_method='expected_bucket',
    tune_hyperparameters=False,  # Set True for Optuna tuning

    # Output
    model_save_dir='models/prediction_system',
    verbose=True,
)

trainer = ModelTrainer(config)
results = trainer.train_full_system()
```

### Hyperparameter Tuning (Optional)

```python
config = TrainingConfig(
    tune_hyperparameters=True,
    n_tuning_trials=50,  # Optuna trials
)

trainer = ModelTrainer(config)
results = trainer.train_full_system()

# Best parameters are stored
print(results['training_info']['tuned_params'])
```

---

## Making Predictions

### Individual Bucket Prediction

```python
# Predict bucket class (0-7)
buckets = bucket_predictor.predict(test_df)

# Predict continuous value (for ranking)
continuous = bucket_predictor.predict_continuous(test_df)

# Predict probability distribution
proba = bucket_predictor.predict_proba(test_df)
print(f"Bucket 0 probability: {proba[0, 0]:.1%}")
```

### Individual Time Gap Prediction

```python
# Predict time gap in seconds
gaps = time_gap_predictor.predict(test_df)
print(f"Predicted gap: {gaps[0]:.0f} seconds")
```

### Complete Race Ranking

```python
# Predict race ranking
race_df = pipeline.load_race_startlist(competition_id)
predictions = ranker.predict_race(race_df, return_details=True)

# Results include:
# - rider_id, rider_name
# - predicted_rank (1 = winner)
# - predicted_bucket (from rank position)
# - expected_bucket (from individual model)
# - predicted_time_gap (if time gap model used)
# - prob_bucket_0 through prob_bucket_7 (if return_details=True)

print(predictions[['rider_name', 'predicted_rank', 'expected_bucket']].head(10))
```

### Using the Inference API

```python
from prediction_tools import RacePredictionAPI

# Load models
api = RacePredictionAPI.load('models/prediction_system')

# Predict a race
predictions = api.predict_race(competition_id=12345)

# Predict individual rider
result = api.predict_rider(rider_id=177, competition_id=12345)
# Returns: {
#   'predicted_bucket': 3,
#   'expected_bucket': 2.85,
#   'bucket_probabilities': [0.02, 0.15, 0.25, ...],
#   'predicted_time_gap': 245.0,
#   'confidence': 0.25
# }

# Custom start list
predictions = api.predict_startlist(
    rider_ids=[177, 234, 456],
    competition_id=12345
)

# Get race info
info = api.get_race_info(competition_id=12345)
print(f"Race: {info['competition_name']}")
print(f"Field size: {info['field_size']}")
```

---

## Evaluation

### Bucket Evaluation

```python
from prediction_tools import BucketEvaluator

y_true = test['place_bucket'].values
y_pred = bucket_predictor.predict(test)

metrics = BucketEvaluator.evaluate(y_true, y_pred)

print(f"MAE: {metrics['mae']:.3f}")
print(f"Accuracy: {metrics['accuracy']:.1%}")
print(f"Within-1: {metrics['within_1']:.1%}")
print(f"Within-2: {metrics['within_2']:.1%}")
print(f"Quadratic Kappa: {metrics['quadratic_kappa']:.3f}")

# Per-bucket metrics
for bucket in range(8):
    if f'bucket_{bucket}_count' in metrics:
        print(f"Bucket {bucket}: {metrics[f'bucket_{bucket}_accuracy']:.1%}")

# Confusion matrix
cm = BucketEvaluator.confusion_matrix(y_true, y_pred)
print(cm)
```

### Time Gap Evaluation

```python
from prediction_tools import TimeGapEvaluator

# Filter to valid samples
test_filtered = time_gap_predictor.filter_for_training(test)
y_true = test_filtered['time_gap'].values
y_pred = time_gap_predictor.predict(test_filtered)

metrics = TimeGapEvaluator.evaluate(y_true, y_pred)

print(f"MAE: {metrics['mae']:.1f} seconds")
print(f"RMSE: {metrics['rmse']:.1f} seconds")
print(f"Median AE: {metrics['median_ae']:.1f} seconds")
print(f"R²: {metrics['r2']:.3f}")

# By bucket
by_bucket = TimeGapEvaluator.evaluate_by_bucket(
    y_true, y_pred, test_filtered['place_bucket'].values
)
print(by_bucket)
```

### Race Ranking Evaluation

```python
# Single race
metrics = ranker.evaluate_race(race_df)

print(f"Kendall's Tau: {metrics['kendall_tau']:.3f}")
print(f"Winner correct: {metrics['winner_correct']}")
print(f"Podium accuracy: {metrics['podium_accuracy']:.1%}")
print(f"Top-5 accuracy: {metrics['top5_accuracy']:.1%}")
print(f"Top-10 accuracy: {metrics['top10_accuracy']:.1%}")

# Multiple races
eval_results = ranker.evaluate_races(
    test,
    competition_ids=test['competition_id'].unique(),
    min_field_size=20
)

print(f"Mean Kendall's Tau: {eval_results['kendall_tau'].mean():.3f}")
print(f"Mean winner correct: {eval_results['winner_correct'].mean():.1%}")
```

### Full System Evaluation

```python
from prediction_tools import evaluate_full_system, print_evaluation_report

results = evaluate_full_system(
    bucket_predictor,
    time_gap_predictor,
    ranker,
    test,
    n_sample_races=100
)

print_evaluation_report(results)
```

---

## Saving and Loading Models

### Saving Models

```python
from prediction_tools import ModelRegistry

registry = ModelRegistry('models/my_model_v1')
registry.save(
    bucket_predictor,
    time_gap_predictor,
    evaluation=results['evaluation'],
    training_info=results['training_info']
)
```

### Loading Models

```python
# Load models only
bucket_pred, time_gap_pred = registry.load()

# Load with race ranker
bucket_pred, time_gap_pred, ranker = registry.load_with_ranker(
    ranking_method='expected_bucket'
)

# Check saved metadata
metadata = registry.get_metadata()
print(f"Saved at: {metadata['saved_at']}")
print(f"Evaluation: {metadata['evaluation']}")
```

### Convenience Functions

```python
from prediction_tools import save_models, load_models

# Save
save_models(bucket_pred, time_gap_pred, path='models/v1')

# Load
bucket_pred, time_gap_pred = load_models(path='models/v1')
```

---

## API Reference

### Core Classes

| Class | Purpose |
|-------|---------|
| `CyclingDataPipeline` | Load data from database |
| `FeatureEngineer` | Create derived features |
| `OrdinalBucketPredictor` | Predict finish bucket |
| `TimeGapPredictor` | Predict time gap |
| `RaceRankingPredictor` | Predict race rankings |
| `ModelTrainer` | Orchestrate training |
| `ModelRegistry` | Save/load models |
| `RacePredictionAPI` | Production inference |

### Evaluators

| Class | Purpose |
|-------|---------|
| `BucketEvaluator` | Bucket prediction metrics |
| `TimeGapEvaluator` | Time gap metrics |
| `RankingEvaluator` | Ranking metrics |

### Configuration Classes

| Class | Purpose |
|-------|---------|
| `DataConfig` | Data loading options |
| `FeatureConfig` | Feature engineering options |
| `BucketPredictorConfig` | Bucket model settings |
| `TimeGapPredictorConfig` | Time gap model settings |
| `RaceRankingConfig` | Ranking method options |
| `TrainingConfig` | Full training pipeline |

---

## Performance Benchmarks

Results from deep test (500 iterations, temporal split 2018-2022/2023H1/2023H2+):

### Bucket Prediction

| Metric | Value |
|--------|-------|
| MAE | 1.197 |
| Accuracy | 22.4% |
| Within-1 | 68.8% |
| Within-2 | 91.2% |
| Quadratic Kappa | 0.401 |

### Time Gap Prediction

| Competition Type | MAE | R² |
|------------------|-----|-----|
| Stage | 4.9 min | 0.471 |
| One-day | 3.0 min | 0.226 |
| GC | 9.9 min | 0.595 |

### Race Ranking

| Metric | Value |
|--------|-------|
| Kendall's Tau | 0.384 |
| Winner correct | 21.5% |
| Podium accuracy | 31.0% |
| Top-5 accuracy | 36.3% |
| Top-10 accuracy | 33.4% |

### Top Predictive Features

1. `profile_weighted_expected` - Expected bucket based on race profile match
2. `relevant_category_avg_bucket` - Performance at race's tour level
3. `best_profile_bucket` - Rider's best profile performance
4. `sprint_avg_bucket` - Sprint race performance
5. `team_bib` - Team role indicator

---

## Tips and Best Practices

1. **Use temporal splits**: Always split by date to prevent data leakage.

2. **Filter by career races**: Riders with <10 races have unreliable features.

3. **Interpret predictions carefully**:
   - Use `predict_continuous()` for ranking (finer granularity)
   - Use `predict()` for bucket classification
   - Use `predict_proba()` for uncertainty estimation

4. **GC time gaps are different**: Consider training separate models or normalizing.

5. **Feature importance**: Check feature importance to understand what drives predictions.

6. **Per-bucket analysis**: Winners (bucket 0) are hardest to predict - don't expect high accuracy.

7. **Race type matters**: GC rankings are more predictable than one-day races.
