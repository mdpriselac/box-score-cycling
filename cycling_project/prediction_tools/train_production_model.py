"""
Train Production Model on All Available Data

Uses all data from 2018-01-01 onward for maximum training signal.
A small chronological holdout (last 5%) is used only for LightGBM
early stopping - this is NOT a true validation set.

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
from cycling_project.prediction_tools.model_registry import ModelRegistry


def main():
    print("=" * 70)
    print("PRODUCTION MODEL TRAINING (ALL DATA)")
    print("=" * 70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # --- Load Data ---
    db_path = Path(__file__).parent.parent / "webscrape_tools" / "database" / "database" / "cycling_races.db"
    config = DataConfig(
        db_path=str(db_path),
        start_date='2018-01-01',
        min_races_career=10,
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
        n_estimators=1000,
        early_stopping_rounds=100,
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
        n_estimators=1000,
        early_stopping_rounds=100,
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
        n_estimators=1000,
        early_stopping_rounds=100,
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
        n_estimators=1000,
        early_stopping_rounds=100,
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

    contender_top_n = 25

    # Add classifier predictions and filter to top N per race
    train_contender = train.copy()
    train_contender['classifier_expected_bucket'] = bucket_predictor.predict_continuous(train)
    train_contender['_rank'] = train_contender.groupby('competition_id')['classifier_expected_bucket'].rank()
    train_contender = train_contender[train_contender['_rank'] <= contender_top_n].drop(columns=['_rank'])

    early_stop_contender = early_stop.copy()
    early_stop_contender['classifier_expected_bucket'] = bucket_predictor.predict_continuous(early_stop)
    early_stop_contender['_rank'] = early_stop_contender.groupby('competition_id')['classifier_expected_bucket'].rank()
    early_stop_contender = early_stop_contender[early_stop_contender['_rank'] <= contender_top_n].drop(columns=['_rank'])

    print(f"Filtered train: {len(train_contender):,} from {len(train):,} ({len(train_contender)/len(train):.1%})")
    print(f"Filtered early-stop: {len(early_stop_contender):,} from {len(early_stop):,}")

    # Class distribution of filtered set
    dist = train_contender['place_bucket'].value_counts().sort_index()
    print("\nFiltered training set class distribution:")
    for bucket, count in dist.items():
        print(f"  Bucket {bucket}: {count:,} ({count/len(train_contender):.1%})")

    contender_config = ProbabilityPredictorConfig(
        n_estimators=1000,
        early_stopping_rounds=100,
        use_sample_weights=False,
    )
    contender_config.lgb_params.update({
        'num_leaves': 63,
        'learning_rate': 0.05,
        'feature_fraction': 0.8,
        'bagging_fraction': 0.8,
        'bagging_freq': 5,
        'min_child_samples': 50,
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
    registry.save(
        bucket_predictor=bucket_predictor,
        time_gap_predictor=time_gap_predictor,
        probability_predictor=probability_predictor,
        calibrated_predictor=calibrated_predictor,
        contender_predictor=contender_predictor,
        training_info={
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
            'contender_train_samples': len(train_contender),
            'min_races_career': 10,
            'start_date': '2018-01-01',
            'timestamp': datetime.now().isoformat(),
        },
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
