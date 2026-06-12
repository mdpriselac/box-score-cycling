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

ARM-C STACK (default ON since 2026-06-11; disable with --no-stack):
the bucket + contender heads are trained with 17 extra columns on top of
the production frame — the combination that passed the full-stack
integration gate (experiments/full_stack_integration_cv.py, C-A
market_avg_log_loss -0.0040±0.0014 5/5 folds, winner capture +1.2pp):

  meta-OOF (2):     oof_time_gap_pred, oof_lambdarank_win_p — 5-fold
                    temporal OOF predictions on train; the production
                    time-gap model + a production-config LambdaRank head
                    supply the early-stop (and serving) values.
  signatures (11):  one-day contest-signature features (B4 continuous,
                    as-of-then; stage/gc rows NaN) from
                    contest_signature_features.py.
  contested Elo (4): contested_rating, _n, _delta90, _vs_field — as-of-then
                    from the production rating snapshots artifact.

The time-gap / weighted / calibrated heads and the LambdaRank head stay on
the plain frame (they are the stack's base models — exactly the gated arm).

Also fits the win-market calibration corrector (win_calibration.py) on the
early-stop contender pool and persists it next to the models.

Saves to models/production/ via ModelRegistry.

Usage:
    uv run python -m cycling_project.prediction_tools.train_production_model
    uv run python -m cycling_project.prediction_tools.train_production_model --no-stack
"""

import argparse
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
from cycling_project.prediction_tools.contest_signature_features import (
    SIGNATURE_FEATURE_COLS,
    attach_signature_features,
    build_oneday_signature_features,
)
from cycling_project.prediction_tools.contested_rating import (
    PRODUCTION_SNAPSHOT_PATH,
    RATING_FEATURE_COLS,
    attach_rating_features,
    build_or_update_snapshots,
)
from cycling_project.prediction_tools.win_calibration import (
    fit_win_corrector,
    save_corrector,
)

META_FEATURE_COLS = ['oof_time_gap_pred', 'oof_lambdarank_win_p']
STACK_FEATURE_COLS = META_FEATURE_COLS + SIGNATURE_FEATURE_COLS + RATING_FEATURE_COLS

# OOF base-model configs — identical to the gated experiment
# (stacked_meta_learner_cv_5fold / full_stack_integration_cv).
TIME_GAP_OOF_CONFIG = {'n_estimators': 300, 'early_stopping_rounds': 30}
LAMBDARANK_OOF_CONFIG = {
    'n_estimators': 500,
    'early_stopping_rounds': 100,
    'learning_rate': 0.05,
}
N_OOF_FOLDS = 5


def _temporal_fold_mask(dates: pd.Series, fold_idx: int, n_folds: int) -> pd.Series:
    quantiles = [dates.quantile(i / n_folds) for i in range(1, n_folds)]
    if fold_idx == 0:
        return dates <= quantiles[0]
    if fold_idx == n_folds - 1:
        return dates > quantiles[-1]
    return (dates > quantiles[fold_idx - 1]) & (dates <= quantiles[fold_idx])


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

    oof_predictions = np.full(len(train_df), np.nan)

    for fold_idx in range(n_folds):
        fold_mask = _temporal_fold_mask(dates, fold_idx, n_folds)

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


def generate_oof_time_gap(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    n_folds: int = N_OOF_FOLDS,
) -> np.ndarray:
    """5-fold temporal OOF time-gap predictions on train (gated experiment port)."""
    dates = pd.to_datetime(train_df['competition_date'])
    oof = np.full(len(train_df), np.nan)

    for k in range(n_folds):
        mask = _temporal_fold_mask(dates, k, n_folds)
        fold_train = train_df[~mask]
        fold_predict = train_df[mask]
        if len(fold_predict) == 0:
            continue
        cfg = TimeGapPredictorConfig(**TIME_GAP_OOF_CONFIG)
        model = TimeGapPredictor(cfg)
        model.train(fold_train, val_df, verbose=False)
        oof[mask.values] = model.predict(fold_predict)
        print(f"    tg OOF fold {k + 1}/{n_folds}: "
              f"trained on {len(fold_train):,}, predicted {len(fold_predict):,}")

    nan_n = int(np.isnan(oof).sum())
    if nan_n:
        print(f"    Warning: {nan_n} time_gap OOF rows missing; filling with median")
        oof[np.isnan(oof)] = float(np.nanmedian(oof))
    return oof


def generate_oof_lambdarank_winp(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    n_folds: int = N_OOF_FOLDS,
) -> np.ndarray:
    """5-fold temporal OOF calibrated LambdaRank win_p on train (gated port)."""
    dates = pd.to_datetime(train_df['competition_date'])
    oof = np.full(len(train_df), np.nan)

    for k in range(n_folds):
        mask = _temporal_fold_mask(dates, k, n_folds)
        fold_train = train_df[~mask]
        fold_predict = train_df[mask]
        if len(fold_predict) == 0:
            continue
        cfg = LambdaRankPredictorConfig(
            n_estimators=LAMBDARANK_OOF_CONFIG['n_estimators'],
            early_stopping_rounds=LAMBDARANK_OOF_CONFIG['early_stopping_rounds'],
        )
        cfg.lgb_params['learning_rate'] = LAMBDARANK_OOF_CONFIG['learning_rate']
        model = LambdaRankProbabilityPredictor(cfg)
        model.train(fold_train, val_df, verbose=False)
        T = model.calibrate_temperature(val_df)
        oof[mask.values] = model.predict_win_probabilities(fold_predict).values
        print(f"    lr OOF fold {k + 1}/{n_folds}: trained on {len(fold_train):,}, "
              f"predicted {len(fold_predict):,}, T={T:.3f}")

    nan_n = int(np.isnan(oof).sum())
    if nan_n:
        print(f"    Warning: {nan_n} LR OOF rows missing; filling with mean")
        oof[np.isnan(oof)] = float(np.nanmean(oof))
    return oof


def main(enable_stack: bool = True):
    print("=" * 70)
    print("PRODUCTION MODEL TRAINING (ALL DATA)")
    print(f"Arm-C stack: {'ENABLED' if enable_stack else 'DISABLED (--no-stack)'}")
    print("=" * 70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # --- Load Data ---
    db_path = Path(__file__).parent.parent / "webscrape_tools" / "database" / "database" / "cycling_races.db"
    config = DataConfig(
        db_path=str(db_path),
        start_date='2016-01-01',
        min_races_career=10,
        include_gradient_features=True,
        # Stage-race state features: passed Phase-1 CV 2026-06-09 (+0.50pp
        # winner / -0.033 stage log loss). ON since the web app attaches
        # live state to stage-2+ prediction frames (live_race_state.py);
        # all other targets get the same neutral-default imputation used
        # for missing state in training. See stage_race_dynamics_plan.md.
        include_race_state=True,
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

    # --- Train Time Gap Predictor (plain frame — also the stack's main
    # time-gap base model: its predictions feed oof_time_gap_pred on the
    # early-stop frame here and on future-race frames at serving) ---
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

    # --- Stack feature assembly (arm C) ---
    lambdarank_predictor = None
    lambdarank_temp = None
    stack_info = {}
    if enable_stack:
        print("\n" + "=" * 70)
        print("ARM-C STACK — base models + feature assembly")
        print("=" * 70)

        # Main LambdaRank head (plain frame, production config). Trained here
        # so the early-stop meta feature comes from the exact head that ships
        # to the registry / serves oof_lambdarank_win_p at prediction time.
        print("\nTraining main LambdaRank head (production config)...")
        lr_config = LambdaRankPredictorConfig()
        lambdarank_predictor = LambdaRankProbabilityPredictor(lr_config)
        lr_info = lambdarank_predictor.train(train, early_stop, verbose=True)
        lambdarank_temp = lambdarank_predictor.calibrate_temperature(early_stop)
        print(f"Best iteration: {lr_info['best_iteration']}  temperature: {lambdarank_temp:.3f}")

        # OOF meta features on train (5 temporal sub-folds, gated configs)
        print("\nGenerating OOF time-gap predictions on train (5 sub-folds)...")
        oof_tg = generate_oof_time_gap(train, early_stop)
        print("\nGenerating OOF LambdaRank win_p on train (5 sub-folds)...")
        oof_lr = generate_oof_lambdarank_winp(train, early_stop)

        # Contested-Elo snapshots artifact (incremental build/update)
        print("\nBuilding/updating contested-rating snapshots artifact...")
        rating_snaps = build_or_update_snapshots(db_path=db_path)
        print(f"  snapshots: {len(rating_snaps):,} rows -> {PRODUCTION_SNAPSHOT_PATH}")

        # One-day contest-signature features (as-of-then, from the DB)
        print("\nBuilding one-day contest-signature features...")
        od_feats, field_shares = build_oneday_signature_features(db_path)
        print(f"  signature comps: {len(od_feats):,}")

        # Augmented frames for bucket + contender
        print("\nAttaching stack features to train / early-stop frames...")
        train_aug = attach_signature_features(train, od_feats, field_shares)
        early_stop_aug = attach_signature_features(early_stop, od_feats, field_shares)
        train_aug = attach_rating_features(train_aug, rating_snaps, db_path=db_path)
        early_stop_aug = attach_rating_features(early_stop_aug, rating_snaps, db_path=db_path)

        train_aug['oof_time_gap_pred'] = oof_tg
        train_aug['oof_lambdarank_win_p'] = oof_lr
        early_stop_aug['oof_time_gap_pred'] = time_gap_predictor.predict(early_stop_aug)
        early_stop_aug['oof_lambdarank_win_p'] = np.asarray(
            lambdarank_predictor.predict_win_probabilities(early_stop_aug)
        )

        sig_cov = 1 - train_aug['sig_sprint'].isna().mean()
        rating_cov = train_aug['contested_rating'].notna().mean()
        print(f"  sig coverage (train rows): {sig_cov:.1%}  "
              f"rating coverage: {rating_cov:.1%}")
        stack_info = {
            'stack_enabled': True,
            'stack_feature_columns': STACK_FEATURE_COLS,
            'sig_coverage_train': round(float(sig_cov), 4),
            'rating_coverage_train': round(float(rating_cov), 4),
            'rating_snapshot_rows': int(len(rating_snaps)),
            'rating_snapshot_path': str(PRODUCTION_SNAPSHOT_PATH),
            'time_gap_oof_config': TIME_GAP_OOF_CONFIG,
            'lambdarank_oof_config': LAMBDARANK_OOF_CONFIG,
            'n_oof_folds': N_OOF_FOLDS,
            'lambdarank_best_iteration': lr_info['best_iteration'],
            'lambdarank_temperature': lambdarank_temp,
        }
    else:
        train_aug = train
        early_stop_aug = early_stop
        stack_info = {'stack_enabled': False}

    # --- Train Bucket Predictor (augmented frame when stack is on) ---
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
    bucket_info = bucket_predictor.train(train_aug, early_stop_aug, verbose=True)
    print(f"Best iteration: {bucket_info['best_iteration']}")
    print(f"Features: {bucket_info['n_features']}")

    # --- Train Probability Predictor (plain frame) ---
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

    # --- Train Calibrated Probability Predictor (plain frame) ---
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

    # --- Train Contender Probability Predictor (augmented frame) ---
    print("\n" + "=" * 70)
    print("TRAINING CONTENDER PROBABILITY PREDICTOR (filtered + classifier feature)")
    print("=" * 70)

    contender_top_n = 15
    contender_n_classes = 5

    # Generate OOF bucket predictions (leak-free) for training set
    print("\nGenerating out-of-fold bucket predictions...")
    oof_bucket_preds = generate_oof_bucket_predictions(
        train_df=train_aug,
        val_df=early_stop_aug,
        bucket_config=bucket_config,
        n_folds=5,
    )

    # Add OOF predictions and filter to top N per race
    train_contender = train_aug.copy()
    train_contender['classifier_expected_bucket'] = oof_bucket_preds
    train_contender['_rank'] = train_contender.groupby('competition_id')['classifier_expected_bucket'].rank()
    train_contender = train_contender[train_contender['_rank'] <= contender_top_n].drop(columns=['_rank'])

    # Early-stop set uses direct predictions (no leakage — not used to train bucket model)
    early_stop_contender = early_stop_aug.copy()
    early_stop_contender['classifier_expected_bucket'] = bucket_predictor.predict_continuous(early_stop_aug)
    early_stop_contender['_rank'] = early_stop_contender.groupby('competition_id')['classifier_expected_bucket'].rank()
    early_stop_contender = early_stop_contender[early_stop_contender['_rank'] <= contender_top_n].drop(columns=['_rank'])

    # 5-class reduction: merge buckets 4-6 into class 4
    train_contender['place_bucket'] = train_contender['place_bucket'].clip(upper=contender_n_classes - 1)
    early_stop_contender['place_bucket'] = early_stop_contender['place_bucket'].clip(upper=contender_n_classes - 1)

    print(f"Filtered train: {len(train_contender):,} from {len(train_aug):,} ({len(train_contender)/len(train_aug):.1%})")
    print(f"Filtered early-stop: {len(early_stop_contender):,} from {len(early_stop_aug):,}")

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

    # --- Win-market calibration corrector (must-fix: arm-C one-day
    # win_cal_ratio ~0.93). Fit on the early-stop contender pool. ---
    print("\n" + "=" * 70)
    print("FITTING WIN-MARKET CALIBRATION CORRECTOR")
    print("=" * 70)

    es_proba = contender_predictor.predict_proba(early_stop_contender)
    win_corrector = fit_win_corrector(
        win_p=es_proba[:, 0],
        y_win=(early_stop_contender['place_bucket'].values == 0).astype(float),
    )
    print(f"Chosen corrector: {win_corrector['method']} (param={win_corrector['param']})")
    print(f"  val win_cal_ratio: {win_corrector['val_before']['win_cal_ratio']:.3f} "
          f"-> {win_corrector['val_after']['win_cal_ratio']:.3f}")
    print(f"  val win_log_loss:  {win_corrector['val_before']['win_log_loss']:.5f} "
          f"-> {win_corrector['val_after']['win_log_loss']:.5f}")

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
        'win_corrector': {k: win_corrector[k] for k in
                          ('method', 'param', 'val_before', 'val_after')},
        'timestamp': datetime.now().isoformat(),
        **stack_info,
    }
    registry.save(
        bucket_predictor=bucket_predictor,
        time_gap_predictor=time_gap_predictor,
        probability_predictor=probability_predictor,
        calibrated_predictor=calibrated_predictor,
        contender_predictor=contender_predictor,
        lambdarank_predictor=lambdarank_predictor,
        training_info=training_info_dict,
    )
    save_corrector(win_corrector, model_dir)
    print(f"Models saved to {model_dir}")

    # --- Quick early-stop set metrics for reference ---
    print("\n" + "=" * 70)
    print("EARLY-STOP SET METRICS (for reference only)")
    print("=" * 70)

    bucket_preds = bucket_predictor.predict(early_stop_aug)
    y_true = early_stop_aug['place_bucket'].values
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

    if enable_stack:
        # Stack feature ranks in the contender (gate showed meta features at
        # rank #2-3; a collapse here would signal an attachment bug)
        imp_df = contender_predictor.get_feature_importance(importance_type='gain')
        pos = {f: i + 1 for i, f in enumerate(imp_df['feature'])}
        shown = [f"{c}=#{pos[c]}" for c in STACK_FEATURE_COLS if c in pos]
        print(f"\nStack feature gain ranks (of {len(pos)}):")
        print("  " + "  ".join(shown))

    print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Train the production model suite")
    parser.add_argument(
        '--no-stack', action='store_true',
        help="Disable the arm-C stack (meta-OOF + one-day signatures + "
             "contested Elo); reverts to the pre-2026-06-11 feature set.",
    )
    args = parser.parse_args()
    main(enable_stack=not args.no_stack)
