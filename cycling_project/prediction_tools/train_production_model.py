"""
Train Production Model on All Available Data

Uses all data from 2016-01-01 onward for maximum training signal.
A small chronological holdout (last 5%) is used only for LightGBM
early stopping - this is NOT a true validation set.

The 2016-01-01 cutoff was chosen on 2026-04-18 after a start-date CV
sweep (see experiment_log.md "Multiclass stack — start-date sweep"):
moving the window back from 2018 to 2016 delivered +0.7pp winner
capture and ~1% log loss / Brier reduction on the multiclass contender
cascade, with the LambdaRank head unchanged. 2015 was marginally better
on log loss but within fold-std on winner; 2016 is the cautious pick.

Saves to models/production/ via ModelRegistry.
"""

import sys
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd

from cycling_project.prediction_tools.data_pipeline import CyclingDataPipeline, DataConfig
from cycling_project.prediction_tools.bucket_predictor import OrdinalBucketPredictor, BucketPredictorConfig
from cycling_project.prediction_tools.time_gap_predictor import TimeGapPredictor, TimeGapPredictorConfig
from cycling_project.prediction_tools.probability_predictor import ProbabilityPredictor, ProbabilityPredictorConfig
from cycling_project.prediction_tools.lambdarank_probability_predictor import (
    LambdaRankProbabilityPredictor,
    LambdaRankPredictorConfig,
)
from cycling_project.prediction_tools.model_registry import ModelRegistry


def generate_oof_bucket_predictions(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    bucket_config: BucketPredictorConfig,
    n_folds: int = 5,
) -> np.ndarray:
    """Generate out-of-fold bucket predictions to avoid leakage in contender filtering.

    Splits training data into temporal folds, trains a temporary bucket predictor
    on each fold's complement, and predicts on the held-out fold. This produces
    leak-free classifier_expected_bucket values for the full training set.

    Args:
        train_df: Training data (must have competition_date column)
        val_df: Validation/early-stop set (used for early stopping in each fold model)
        bucket_config: Config for the temporary bucket predictors
        n_folds: Number of temporal folds

    Returns:
        Array of OOF continuous bucket predictions, same length as train_df
    """
    dates = pd.to_datetime(train_df['competition_date'])

    # Create temporal fold boundaries using date quantiles
    date_quantiles = [dates.quantile(i / n_folds) for i in range(1, n_folds)]

    oof_predictions = np.full(len(train_df), np.nan)

    for fold_idx in range(n_folds):
        # Define fold boundaries
        if fold_idx == 0:
            fold_mask = dates <= date_quantiles[0]
        elif fold_idx == n_folds - 1:
            fold_mask = dates > date_quantiles[-1]
        else:
            fold_mask = (
                (dates > date_quantiles[fold_idx - 1]) &
                (dates <= date_quantiles[fold_idx])
            )

        fold_train = train_df[~fold_mask]
        fold_predict = train_df[fold_mask]

        if len(fold_predict) == 0:
            continue

        # Train a temporary bucket predictor on the non-fold data
        temp_model = OrdinalBucketPredictor(bucket_config)
        temp_model.train(fold_train, val_df, verbose=False)

        # Predict on the held-out fold
        fold_preds = temp_model.predict_continuous(fold_predict)
        oof_predictions[fold_mask.values] = fold_preds

        print(f"    OOF fold {fold_idx + 1}/{n_folds}: "
              f"trained on {len(fold_train):,}, predicted {len(fold_predict):,}")

    # Fill any remaining NaN with direct predictions (shouldn't happen)
    nan_mask = np.isnan(oof_predictions)
    if nan_mask.any():
        print(f"    Warning: {nan_mask.sum()} NaN OOF predictions filled with direct predictions")
        temp_model = OrdinalBucketPredictor(bucket_config)
        temp_model.train(train_df, val_df, verbose=False)
        oof_predictions[nan_mask] = temp_model.predict_continuous(train_df[nan_mask])

    return oof_predictions


def main():
    print("=" * 70)
    print("PRODUCTION MODEL TRAINING (ALL DATA)")
    print("=" * 70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # --- Load Data ---
    db_path = Path(__file__).parent.parent / "webscrape_tools" / "database" / "database" / "cycling_races.db"
    config = DataConfig(
        db_path=str(db_path),
        start_date='2016-01-01',
        min_races_career=10,
        include_gradient_features=True,
    )
    pipeline = CyclingDataPipeline(config)
    df = pipeline.load_training_data()
    df['competition_date'] = pd.to_datetime(df['competition_date'])

    print(f"Total samples: {len(df):,}")
    print(f"Date range: {df['competition_date'].min().date()} to {df['competition_date'].max().date()}")
    print(f"Competitions: {df['competition_id'].nunique():,}")

    # --- Split: use last 5% chronologically for early stopping only ---
    # This is NOT a validation set - it's just to prevent LightGBM from
    # overfitting on boosting rounds. All data trains the model.
    n_comps = df['competition_id'].nunique()
    comp_dates = df.groupby('competition_id')['competition_date'].first().sort_values()
    cutoff_idx = int(len(comp_dates) * 0.95)
    cutoff_comp = comp_dates.iloc[cutoff_idx]
    cutoff_date = cutoff_comp

    train = df[df['competition_date'] < cutoff_date].copy()
    early_stop = df[df['competition_date'] >= cutoff_date].copy()

    print(f"\nTrain:       {len(train):>8,} samples, {train['competition_id'].nunique():,} competitions")
    print(f"             {train['competition_date'].min().date()} to {train['competition_date'].max().date()}")
    print(f"Early-stop:  {len(early_stop):>8,} samples, {early_stop['competition_id'].nunique():,} competitions")
    print(f"             {early_stop['competition_date'].min().date()} to {early_stop['competition_date'].max().date()}")
    print(f"(Early-stop set is used only to determine optimal boosting rounds)")

    # --- Train Bucket Predictor ---
    print("\n" + "=" * 70)
    print("TRAINING BUCKET PREDICTOR")
    print("=" * 70)

    bucket_config = BucketPredictorConfig(
        n_estimators=2000,
        early_stopping_rounds=300,
        use_sample_weights=True,
    )
    bucket_config.lgb_params.update({
        'num_leaves': 63,
        'learning_rate': 0.05,
        'feature_fraction': 0.8,
        'bagging_fraction': 0.8,
        'bagging_freq': 5,
        'min_child_samples': 50,
    })

    bucket_predictor = OrdinalBucketPredictor(bucket_config)
    bucket_info = bucket_predictor.train(train, early_stop, verbose=True)
    print(f"Best iteration: {bucket_info['best_iteration']}")
    print(f"Features: {bucket_info['n_features']}")

    # --- Train Time Gap Predictor ---
    print("\n" + "=" * 70)
    print("TRAINING TIME GAP PREDICTOR")
    print("=" * 70)

    time_gap_config = TimeGapPredictorConfig(
        n_estimators=2000,
        early_stopping_rounds=300,
        log_transform_target=True,
        exclude_winners=True,
        max_time_gap=3600.0,
    )
    time_gap_config.lgb_params.update({
        'num_leaves': 63,
        'learning_rate': 0.05,
        'feature_fraction': 0.8,
        'bagging_fraction': 0.8,
        'bagging_freq': 5,
        'min_child_samples': 50,
    })

    time_gap_predictor = TimeGapPredictor(time_gap_config)
    time_gap_info = time_gap_predictor.train(train, early_stop, verbose=True)
    print(f"Best iteration: {time_gap_info['best_iteration']}")
    print(f"Training samples: {time_gap_info['train_samples']:,}")

    # --- Train Probability Predictor ---
    print("\n" + "=" * 70)
    print("TRAINING PROBABILITY PREDICTOR")
    print("=" * 70)

    probability_config = ProbabilityPredictorConfig(
        n_estimators=2000,
        early_stopping_rounds=300,
        use_sample_weights=True,
    )
    probability_config.lgb_params.update({
        'num_leaves': 63,
        'learning_rate': 0.05,
        'feature_fraction': 0.8,
        'bagging_fraction': 0.8,
        'bagging_freq': 5,
        'min_child_samples': 50,
    })

    probability_predictor = ProbabilityPredictor(probability_config)
    probability_info = probability_predictor.train(train, early_stop, verbose=True)
    print(f"Best iteration: {probability_info['best_iteration']}")

    # Calibrate temperature on early-stop set
    temp = probability_predictor.calibrate_temperature(early_stop)
    print(f"Calibrated temperature: {temp:.3f}")

    # --- Train Calibrated Probability Predictor ---
    print("\n" + "=" * 70)
    print("TRAINING CALIBRATED PROBABILITY PREDICTOR (no sample weights)")
    print("=" * 70)

    calibrated_config = ProbabilityPredictorConfig(
        n_estimators=2000,
        early_stopping_rounds=300,
        use_sample_weights=False,
    )
    calibrated_config.lgb_params.update({
        'num_leaves': 63,
        'learning_rate': 0.05,
        'feature_fraction': 0.8,
        'bagging_fraction': 0.8,
        'bagging_freq': 5,
        'min_child_samples': 50,
    })

    calibrated_predictor = ProbabilityPredictor(calibrated_config)
    calibrated_info = calibrated_predictor.train(train, early_stop, verbose=True)
    print(f"Best iteration: {calibrated_info['best_iteration']}")

    cal_temp = calibrated_predictor.calibrate_temperature(early_stop)
    print(f"Calibrated temperature: {cal_temp:.3f}")

    # --- Train Contender Probability Predictor ---
    print("\n" + "=" * 70)
    print("TRAINING CONTENDER PROBABILITY PREDICTOR (filtered + classifier feature)")
    print("=" * 70)

    contender_top_n = 15
    contender_n_classes = 5

    # Generate OOF bucket predictions (leak-free) for training set
    print("\nGenerating out-of-fold bucket predictions...")
    oof_bucket_preds = generate_oof_bucket_predictions(
        train_df=train,
        val_df=early_stop,
        bucket_config=bucket_config,
        n_folds=5,
    )

    # Add OOF predictions and filter to top N per race
    train_contender = train.copy()
    train_contender['classifier_expected_bucket'] = oof_bucket_preds
    train_contender['_rank'] = train_contender.groupby('competition_id')['classifier_expected_bucket'].rank()
    train_contender = train_contender[train_contender['_rank'] <= contender_top_n].drop(columns=['_rank'])

    # Early-stop set uses direct predictions (no leakage — not used to train bucket model)
    early_stop_contender = early_stop.copy()
    early_stop_contender['classifier_expected_bucket'] = bucket_predictor.predict_continuous(early_stop)
    early_stop_contender['_rank'] = early_stop_contender.groupby('competition_id')['classifier_expected_bucket'].rank()
    early_stop_contender = early_stop_contender[early_stop_contender['_rank'] <= contender_top_n].drop(columns=['_rank'])

    # 5-class reduction: merge buckets 4-6 into class 4
    train_contender['place_bucket'] = train_contender['place_bucket'].clip(upper=contender_n_classes - 1)
    early_stop_contender['place_bucket'] = early_stop_contender['place_bucket'].clip(upper=contender_n_classes - 1)

    print(f"Filtered train: {len(train_contender):,} from {len(train):,} ({len(train_contender)/len(train):.1%})")
    print(f"Filtered early-stop: {len(early_stop_contender):,} from {len(early_stop):,}")

    # Class distribution of filtered set
    dist = train_contender['place_bucket'].value_counts().sort_index()
    print(f"\nFiltered training set class distribution ({contender_n_classes} classes):")
    for bucket, count in dist.items():
        print(f"  Bucket {bucket}: {count:,} ({count/len(train_contender):.1%})")

    contender_config = ProbabilityPredictorConfig(
        n_estimators=2000,
        early_stopping_rounds=300,
        use_sample_weights=False,
    )
    contender_config.lgb_params.update({
        'num_leaves': 63,
        'learning_rate': 0.01,
        'feature_fraction': 0.8,
        'bagging_fraction': 0.8,
        'bagging_freq': 5,
        'min_child_samples': 50,
        'num_class': contender_n_classes,
    })

    contender_predictor = ProbabilityPredictor(contender_config)
    contender_info = contender_predictor.train(train_contender, early_stop_contender, verbose=True)
    print(f"Best iteration: {contender_info['best_iteration']}")

    cont_temp = contender_predictor.calibrate_temperature(early_stop_contender)
    print(f"Calibrated temperature: {cont_temp:.3f}")

    # --- Save via ModelRegistry ---
    print("\n" + "=" * 70)
    print("SAVING PRODUCTION MODEL")
    print("=" * 70)

    model_dir = Path(__file__).parent.parent.parent / "models" / "production"
    registry = ModelRegistry(str(model_dir))
    training_info_dict = {
        'mode': 'production',
        'total_samples': len(df),
        'total_competitions': int(df['competition_id'].nunique()),
        'train_samples': len(train),
        'early_stop_samples': len(early_stop),
        'date_range': f"{df['competition_date'].min().date()} to {df['competition_date'].max().date()}",
        'early_stop_cutoff': str(cutoff_date.date()),
        'bucket_best_iteration': bucket_info['best_iteration'],
        'bucket_n_features': bucket_info['n_features'],
        'time_gap_best_iteration': time_gap_info['best_iteration'],
        'time_gap_train_samples': time_gap_info['train_samples'],
        'probability_best_iteration': probability_info['best_iteration'],
        'probability_temperature': temp,
        'calibrated_best_iteration': calibrated_info['best_iteration'],
        'calibrated_temperature': cal_temp,
        'contender_best_iteration': contender_info['best_iteration'],
        'contender_temperature': cont_temp,
        'contender_top_n': contender_top_n,
        'contender_learning_rate': 0.01,
        'contender_n_classes': contender_n_classes,
        'contender_use_oof': True,
        'contender_train_samples': len(train_contender),
        'min_races_career': 10,
        'start_date': '2016-01-01',
        'timestamp': datetime.now().isoformat(),
    }
    registry.save(
        bucket_predictor=bucket_predictor,
        time_gap_predictor=time_gap_predictor,
        probability_predictor=probability_predictor,
        calibrated_predictor=calibrated_predictor,
        contender_predictor=contender_predictor,
        training_info=training_info_dict,
    )
    print(f"Models saved to {model_dir}")

    # --- Quick early-stop set metrics for reference ---
    print("\n" + "=" * 70)
    print("EARLY-STOP SET METRICS (for reference only)")
    print("=" * 70)

    bucket_preds = bucket_predictor.predict(early_stop)
    y_true = early_stop['place_bucket'].values
    mae = np.mean(np.abs(bucket_preds - y_true))
    accuracy = np.mean(bucket_preds == y_true)
    within_1 = np.mean(np.abs(bucket_preds - y_true) <= 1)
    print(f"Bucket MAE:    {mae:.3f}")
    print(f"Accuracy:      {accuracy:.1%}")
    print(f"Within-1:      {within_1:.1%}")

    # Probability metrics — weighted
    prob_metrics = probability_predictor.evaluate(early_stop)
    print(f"\nWeighted Probability:")
    print(f"  Log Loss:       {prob_metrics['log_loss']:.4f}")
    print(f"  Accuracy:       {prob_metrics['accuracy']:.1%}")
    print(f"  Brier Score:    {prob_metrics['brier_score']:.4f}")
    print(f"  Mean Cal Error: {prob_metrics['mean_calibration_error']:.4f}")
    print(f"  ECE:            {prob_metrics['ece']:.4f}")
    print(f"  Sharpness:      {prob_metrics['sharpness']:.3f}")

    # Probability metrics — calibrated
    cal_metrics = calibrated_predictor.evaluate(early_stop)
    print(f"\nCalibrated Probability:")
    print(f"  Log Loss:       {cal_metrics['log_loss']:.4f}")
    print(f"  Accuracy:       {cal_metrics['accuracy']:.1%}")
    print(f"  Brier Score:    {cal_metrics['brier_score']:.4f}")
    print(f"  Mean Cal Error: {cal_metrics['mean_calibration_error']:.4f}")
    print(f"  ECE:            {cal_metrics['ece']:.4f}")
    print(f"  Sharpness:      {cal_metrics['sharpness']:.3f}")

    # Probability metrics — contender
    cont_metrics = contender_predictor.evaluate(early_stop_contender)
    print(f"\nContender Probability (on filtered set):")
    print(f"  Log Loss:       {cont_metrics['log_loss']:.4f}")
    print(f"  Accuracy:       {cont_metrics['accuracy']:.1%}")
    print(f"  Brier Score:    {cont_metrics['brier_score']:.4f}")
    print(f"  Mean Cal Error: {cont_metrics['mean_calibration_error']:.4f}")
    print(f"  ECE:            {cont_metrics['ece']:.4f}")
    print(f"  Sharpness:      {cont_metrics['sharpness']:.3f}")

    print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == '__main__':
    main()
