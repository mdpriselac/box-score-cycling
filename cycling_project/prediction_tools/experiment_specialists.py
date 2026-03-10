"""
Experiment: Compare specialist contender models vs general contender on type-specific races.

For each CV fold, trains:
1. Bucket predictor (all data)
2. General contender (all data, top-15 filter)
3. GC specialist contender (GC-only data, union filter)
4. One-Day specialist contender (one-day-only data, union filter)

Then evaluates each contender on its respective race type in the test set,
comparing specialist vs general performance.
"""

from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd

from cycling_project.prediction_tools.data_pipeline import CyclingDataPipeline, DataConfig
from cycling_project.prediction_tools.bucket_predictor import OrdinalBucketPredictor, BucketPredictorConfig
from cycling_project.prediction_tools.probability_predictor import ProbabilityPredictor, ProbabilityPredictorConfig
from cycling_project.prediction_tools.evaluation import ProbabilityEvaluator


# 5-fold expanding window (same as ExperimentRunner)
FOLDS = [
    {'train_end': '2020-12-31', 'val_end': '2021-06-30', 'label': '2021H2'},
    {'train_end': '2021-12-31', 'val_end': '2022-06-30', 'label': '2022H2'},
    {'train_end': '2022-12-31', 'val_end': '2023-06-30', 'label': '2023H2'},
    {'train_end': '2023-12-31', 'val_end': '2024-06-30', 'label': '2024H2'},
    {'train_end': '2024-12-31', 'val_end': '2025-06-30', 'label': '2025H2'},
]

SPECIALIST_TYPES = ['gc', 'one_day']
CONTENDER_TOP_N = 15
SPECIALIST_MAX_CONTENDERS = 25
N_CLASSES = 5

BUCKET_CONFIG = BucketPredictorConfig(
    n_estimators=500,
    early_stopping_rounds=50,
    use_sample_weights=True,
)
BUCKET_CONFIG.lgb_params.update({
    'num_leaves': 63,
    'learning_rate': 0.05,
    'feature_fraction': 0.8,
    'bagging_fraction': 0.8,
    'bagging_freq': 5,
    'min_child_samples': 50,
})

CONTENDER_LGB_PARAMS = {
    'num_leaves': 63,
    'learning_rate': 0.01,
    'feature_fraction': 0.8,
    'bagging_fraction': 0.8,
    'bagging_freq': 5,
    'min_child_samples': 50,
    'num_class': N_CLASSES,
}


def make_contender_config():
    config = ProbabilityPredictorConfig(
        n_estimators=500,
        early_stopping_rounds=50,
        use_sample_weights=False,
    )
    config.lgb_params.update(CONTENDER_LGB_PARAMS)
    return config


def apply_union_filter(df, bucket_preds, comp_type, top_n=CONTENDER_TOP_N, max_contenders=SPECIALIST_MAX_CONTENDERS):
    """Apply union filter: top-N by bucket OR top-N by type avg, capped."""
    type_avg_col = f'{comp_type}_avg_bucket'

    df = df.copy()
    df['_bucket_pred'] = bucket_preds
    bucket_rank = df.groupby('competition_id')['_bucket_pred'].rank()
    bucket_top = bucket_rank <= top_n

    if type_avg_col in df.columns:
        type_rank = df.groupby('competition_id')[type_avg_col].rank()
        type_top = type_rank <= top_n
        union = (bucket_top | type_top).astype(bool)

        # Cap per race
        per_race = union.groupby(df['competition_id']).sum()
        overcap = per_race[per_race > max_contenders].index
        if len(overcap) > 0:
            drop_idx = []
            for comp_id in overcap:
                rows = union.index[(df['competition_id'] == comp_id) & union]
                ranks = bucket_rank.loc[rows].sort_values()
                drop_idx.extend(ranks.iloc[max_contenders:].index)
            union.loc[drop_idx] = False
    else:
        union = bucket_top.astype(bool)

    df.drop(columns=['_bucket_pred'], inplace=True)
    return union


def evaluate_contender_on_type(contender_model, bucket_predictor, test_df, comp_type, use_union=False):
    """Evaluate a contender model on type-filtered test data.

    Returns dict with winner_capture, podium_capture, top4_log_loss.
    """
    type_test = test_df[test_df['competition_type'] == comp_type].copy()
    if len(type_test) == 0:
        return None

    # Get bucket predictions for classifier feature
    bucket_preds = bucket_predictor.predict_continuous(type_test)
    type_test['classifier_expected_bucket'] = bucket_preds

    # Determine contender mask
    if use_union:
        contender_mask = apply_union_filter(type_test, bucket_preds, comp_type)
    else:
        rank = type_test.groupby('competition_id')['classifier_expected_bucket'].rank()
        contender_mask = (rank <= CONTENDER_TOP_N).astype(bool)

    contender_test = type_test[contender_mask].copy()
    contender_test['place_bucket'] = contender_test['place_bucket'].clip(upper=N_CLASSES - 1)

    if len(contender_test) == 0:
        return None

    # Get predictions (predict_proba pads to 8 cols; slice to N_CLASSES)
    proba = contender_model.predict_proba(contender_test)[:, :N_CLASSES]

    # Metrics
    y_true = contender_test['place_bucket'].values
    comp_ids = contender_test['competition_id'].values

    # Log loss on top-4 (buckets 0-3)
    top4_mask = y_true <= 3
    if top4_mask.sum() > 0:
        from sklearn.metrics import log_loss
        top4_true = y_true[top4_mask]
        top4_proba = proba[top4_mask]
        top4_log = log_loss(top4_true, top4_proba, labels=list(range(N_CLASSES)))
    else:
        top4_log = float('nan')

    # Winner capture: for each race, did the model's #1 (highest prob_bucket_0) actually win?
    winner_captures = []
    podium_captures = []
    unique_comps = np.unique(comp_ids)
    for cid in unique_comps:
        race_mask = comp_ids == cid
        race_proba = proba[race_mask]
        race_true = y_true[race_mask]

        if len(race_proba) == 0:
            continue

        # Winner capture: model's predicted winner (highest P(bucket=0))
        pred_winner_idx = np.argmax(race_proba[:, 0])
        actual_winner = (race_true == 0)
        if actual_winner.any():
            winner_captures.append(1.0 if race_true[pred_winner_idx] == 0 else 0.0)

        # Podium capture: top 3 by P(bucket<=1), how many actual podium?
        podium_score = race_proba[:, 0] + race_proba[:, 1]
        pred_top3_idx = np.argsort(-podium_score)[:3]
        actual_podium = set(np.where(race_true <= 1)[0])
        if len(actual_podium) > 0:
            overlap = len(set(pred_top3_idx) & actual_podium)
            podium_captures.append(overlap / min(3, len(actual_podium)))

    return {
        'winner_capture': np.mean(winner_captures) if winner_captures else float('nan'),
        'podium_capture': np.mean(podium_captures) if podium_captures else float('nan'),
        'top4_log_loss': top4_log,
        'n_races': len(unique_comps),
        'n_samples': len(contender_test),
    }


def run_experiment():
    print("=" * 70)
    print("SPECIALIST vs GENERAL CONTENDER COMPARISON")
    print("=" * 70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    db_path = Path(__file__).parent.parent / "webscrape_tools" / "database" / "database" / "cycling_races.db"
    config = DataConfig(db_path=str(db_path), start_date='2018-01-01', min_races_career=10)
    pipeline = CyclingDataPipeline(config)
    df = pipeline.load_training_data()
    df['competition_date'] = pd.to_datetime(df['competition_date'])

    print(f"Total samples: {len(df):,}")

    # Collect results per fold
    all_results = {spec_type: {'general': [], 'specialist': []} for spec_type in SPECIALIST_TYPES}

    for fold_i, fold in enumerate(FOLDS):
        label = fold['label']
        print(f"\n{'─' * 60}")
        print(f"FOLD {fold_i + 1}/{len(FOLDS)}: test={label}")
        print(f"{'─' * 60}")

        train_end = pd.Timestamp(fold['train_end'])
        val_end = pd.Timestamp(fold['val_end'])

        train = df[df['competition_date'] <= train_end].copy()
        val = df[(df['competition_date'] > train_end) & (df['competition_date'] <= val_end)].copy()
        test = df[df['competition_date'] > val_end].copy()

        print(f"  Train: {len(train):,} | Val: {len(val):,} | Test: {len(test):,}")

        # Train bucket predictor
        print("  Training bucket predictor...")
        bucket_pred = OrdinalBucketPredictor(BUCKET_CONFIG)
        bucket_pred.train(train, val, verbose=False)

        # Get bucket predictions for contender filtering
        bucket_preds_train = bucket_pred.predict_continuous(train)
        bucket_preds_val = bucket_pred.predict_continuous(val)

        # Prepare general contender training data (top-15 filter, all types)
        train_gen = train.copy()
        train_gen['classifier_expected_bucket'] = bucket_preds_train
        gen_rank = train_gen.groupby('competition_id')['classifier_expected_bucket'].rank()
        gen_mask = gen_rank <= CONTENDER_TOP_N
        train_gen = train_gen[gen_mask].copy()
        train_gen['place_bucket'] = train_gen['place_bucket'].clip(upper=N_CLASSES - 1)

        val_gen = val.copy()
        val_gen['classifier_expected_bucket'] = bucket_preds_val
        vg_rank = val_gen.groupby('competition_id')['classifier_expected_bucket'].rank()
        val_gen = val_gen[vg_rank <= CONTENDER_TOP_N].copy()
        val_gen['place_bucket'] = val_gen['place_bucket'].clip(upper=N_CLASSES - 1)

        # Train general contender
        print(f"  Training general contender ({len(train_gen):,} samples)...")
        gen_contender = ProbabilityPredictor(make_contender_config())
        gen_info = gen_contender.train(train_gen, val_gen, verbose=False)
        print(f"    Best iteration: {gen_info['best_iteration']}")

        # Train and evaluate specialists
        for spec_type in SPECIALIST_TYPES:
            type_avg_col = f'{spec_type}_avg_bucket'

            # Evaluate general contender on this type's test races
            print(f"\n  Evaluating on {spec_type} test races...")
            gen_result = evaluate_contender_on_type(gen_contender, bucket_pred, test, spec_type, use_union=False)
            if gen_result is None:
                print(f"    No {spec_type} races in test set, skipping")
                continue

            print(f"    General contender: winner={gen_result['winner_capture']:.3f}, "
                  f"podium={gen_result['podium_capture']:.3f}, "
                  f"log_loss={gen_result['top4_log_loss']:.4f} ({gen_result['n_races']} races)")

            # Train specialist contender
            type_train = train[train['competition_type'] == spec_type].copy()
            type_val = val[val['competition_type'] == spec_type].copy()

            if len(type_train) < 500:
                print(f"    Skipping {spec_type} specialist: only {len(type_train)} samples")
                continue

            # Union filter on type-specific training data
            type_bucket_preds = bucket_pred.predict_continuous(type_train)
            union_mask = apply_union_filter(type_train, type_bucket_preds, spec_type)

            spec_train = type_train[union_mask].copy()
            spec_train['classifier_expected_bucket'] = type_bucket_preds[union_mask.values]
            spec_train['place_bucket'] = spec_train['place_bucket'].clip(upper=N_CLASSES - 1)

            # Val set for specialist
            if len(type_val) > 0:
                type_val_preds = bucket_pred.predict_continuous(type_val)
                val_union = apply_union_filter(type_val, type_val_preds, spec_type)
                spec_val = type_val[val_union].copy()
                spec_val['classifier_expected_bucket'] = type_val_preds[val_union.values]
                spec_val['place_bucket'] = spec_val['place_bucket'].clip(upper=N_CLASSES - 1)
            else:
                # Fall back to general val
                spec_val = val_gen.copy()

            print(f"  Training {spec_type} specialist ({len(spec_train):,} samples)...")
            spec_contender = ProbabilityPredictor(make_contender_config())
            spec_info = spec_contender.train(spec_train, spec_val, verbose=False)
            print(f"    Best iteration: {spec_info['best_iteration']}")

            # Evaluate specialist on same test races
            spec_result = evaluate_contender_on_type(spec_contender, bucket_pred, test, spec_type, use_union=True)
            if spec_result:
                print(f"    Specialist:       winner={spec_result['winner_capture']:.3f}, "
                      f"podium={spec_result['podium_capture']:.3f}, "
                      f"log_loss={spec_result['top4_log_loss']:.4f}")

                all_results[spec_type]['general'].append(gen_result)
                all_results[spec_type]['specialist'].append(spec_result)

    # Print summary
    print(f"\n{'=' * 70}")
    print("SUMMARY: SPECIALIST vs GENERAL CONTENDER")
    print(f"{'=' * 70}")

    for spec_type in SPECIALIST_TYPES:
        gen_list = all_results[spec_type]['general']
        spec_list = all_results[spec_type]['specialist']

        if not gen_list:
            print(f"\n  {spec_type.upper()}: No results (insufficient data)")
            continue

        print(f"\n  {spec_type.upper()} ({len(gen_list)} folds):")
        print(f"  {'Metric':<20s} {'General':>10s} {'Specialist':>10s} {'Delta':>10s}")
        print(f"  {'─' * 52}")

        for metric in ['winner_capture', 'podium_capture', 'top4_log_loss']:
            gen_vals = [r[metric] for r in gen_list if not np.isnan(r[metric])]
            spec_vals = [r[metric] for r in spec_list if not np.isnan(r[metric])]

            if gen_vals and spec_vals:
                gen_mean = np.mean(gen_vals)
                spec_mean = np.mean(spec_vals)
                delta = spec_mean - gen_mean
                pct = (delta / abs(gen_mean) * 100) if gen_mean != 0 else 0

                better = (delta > 0) if metric != 'top4_log_loss' else (delta < 0)
                marker = "+" if better else ""

                print(f"  {metric:<20s} {gen_mean:>10.4f} {spec_mean:>10.4f} {delta:>+10.4f} ({pct:>+.1f}%)")

        # Per-fold detail
        print(f"\n  Per-fold winner capture:")
        for i, (gen_r, spec_r) in enumerate(zip(gen_list, spec_list)):
            label = FOLDS[i]['label'] if i < len(FOLDS) else f"fold_{i}"
            print(f"    {label}: general={gen_r['winner_capture']:.3f}, "
                  f"specialist={spec_r['winner_capture']:.3f}, "
                  f"races={gen_r['n_races']}")

    print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == '__main__':
    run_experiment()
