"""
Cycling Race Prediction Tools

A modular system for predicting cycling race outcomes using gradient boosting:

1. Bucket Prediction (Ordinal Classification)
   - Predicts finish bucket (0-7) for individual riders
   - Uses ordinal regression to respect bucket ordering

2. Time Gap Prediction (Regression)
   - Predicts time behind winner in seconds
   - Trained only on finishers (excludes DNF)

3. Race Ranking
   - Predicts complete race rankings from start lists
   - Uses individual models to score and rank riders

Quick Start:
    from prediction_tools import train_prediction_system, RacePredictionAPI

    # Train the system
    results = train_prediction_system()

    # Or load pre-trained models
    api = RacePredictionAPI.load('models/prediction_system')
    predictions = api.predict_race(competition_id=12345)
"""

# Data pipeline
from .data_pipeline import (
    CyclingDataPipeline,
    DataConfig,
    load_training_data,
)

# Feature engineering
from .feature_engineering import (
    FeatureEngineer,
    FeatureConfig,
    create_training_features,
)

# Models
from .bucket_predictor import (
    OrdinalBucketPredictor,
    BucketPredictorConfig,
    train_bucket_predictor,
)

from .time_gap_predictor import (
    TimeGapPredictor,
    TimeGapPredictorConfig,
    train_time_gap_predictor,
)

from .probability_predictor import (
    ProbabilityPredictor,
    ProbabilityPredictorConfig,
    train_probability_predictor,
)

from .race_ranking_predictor import (
    RaceRankingPredictor,
    RaceRankingConfig,
    create_race_ranker,
)

# Evaluation
from .evaluation import (
    BucketEvaluator,
    TimeGapEvaluator,
    ProbabilityEvaluator,
    Top4ProbabilityEvaluator,
    RankingEvaluator,
    evaluate_full_system,
    print_evaluation_report,
)

# Training
from .training import (
    ModelTrainer,
    TrainingConfig,
    train_prediction_system,
)

# Model persistence
from .model_registry import (
    ModelRegistry,
    save_models,
    load_models,
)

# Inference API
from .inference import (
    RacePredictionAPI,
    quick_predict_race,
)

__all__ = [
    # Data
    'CyclingDataPipeline',
    'DataConfig',
    'load_training_data',

    # Features
    'FeatureEngineer',
    'FeatureConfig',
    'create_training_features',

    # Models
    'OrdinalBucketPredictor',
    'BucketPredictorConfig',
    'train_bucket_predictor',
    'TimeGapPredictor',
    'TimeGapPredictorConfig',
    'train_time_gap_predictor',
    'ProbabilityPredictor',
    'ProbabilityPredictorConfig',
    'train_probability_predictor',
    'RaceRankingPredictor',
    'RaceRankingConfig',
    'create_race_ranker',

    # Evaluation
    'BucketEvaluator',
    'TimeGapEvaluator',
    'ProbabilityEvaluator',
    'Top4ProbabilityEvaluator',
    'RankingEvaluator',
    'evaluate_full_system',
    'print_evaluation_report',

    # Training
    'ModelTrainer',
    'TrainingConfig',
    'train_prediction_system',

    # Persistence
    'ModelRegistry',
    'save_models',
    'load_models',

    # Inference
    'RacePredictionAPI',
    'quick_predict_race',
]
