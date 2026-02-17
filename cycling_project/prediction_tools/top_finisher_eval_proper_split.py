"""
Top Finisher Evaluation with Proper Temporal Split

Train: 2018-2022
Val: 2023-H1 (early stopping)
Test: 2023-H2
Holdout: 2024 (overfitting check)

Evaluate buckets 0-4 only, compare 2023 vs 2024 performance.

Updated to analyze form and team feature importance.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
import lightgbm as lgb
from typing import Tuple, Dict, List

try:
    from prediction_tools.data_pipeline import CyclingDataPipeline, DataConfig
    from prediction_tools.feature_engineering import FeatureEngineer
    from prediction_tools.bucket_predictor import OrdinalBucketPredictor, BucketPredictorConfig
except ModuleNotFoundError:
    from data_pipeline import CyclingDataPipeline, DataConfig
    from feature_engineering import FeatureEngineer
    from bucket_predictor import OrdinalBucketPredictor, BucketPredictorConfig


BUCKET_VALUES = {0: 10.0, 1: 7.0, 2: 5.0, 3: 3.0, 4: 1.5, 5: 1.0, 6: 0.5}


class AsymmetricPredictor:
    def __init__(self, asymmetry_ratio: float, n_estimators: int = 300):
        self.asymmetry_ratio = asymmetry_ratio
        self.n_estimators = n_estimators
        self.model = None
        self.feature_engineer = FeatureEngineer()
        self.feature_columns = None

    def _objective(self, y_pred, train_data):
        y_true = train_data.get_label()
        residual = y_pred - y_true
        grad = np.where(residual < 0, self.asymmetry_ratio * residual, residual)
        hess = np.where(residual < 0, self.asymmetry_ratio, 1.0) * np.ones_like(residual)
        return grad, hess

    def prepare_features(self, df, fit=False):
        if fit:
            df = self.feature_engineer.fit_transform(df)
            self.feature_columns = self.feature_engineer.feature_columns
        else:
            df = self.feature_engineer.transform(df)
        return df

    def get_feature_matrix(self, df):
        # Build dict first to avoid DataFrame fragmentation
        feature_data = {
            col: df[col].values if col in df.columns else np.zeros(len(df))
            for col in self.feature_columns
        }
        return pd.DataFrame(feature_data, index=df.index)

    def train(self, train_df, val_df):
        train_df = self.prepare_features(train_df, fit=True)
        val_df = self.prepare_features(val_df, fit=False)
        X_train, y_train = self.get_feature_matrix(train_df), train_df['place_bucket'].values
        X_val, y_val = self.get_feature_matrix(val_df), val_df['place_bucket'].values
        train_data = lgb.Dataset(X_train, label=y_train)
        val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

        params = {
            'objective': self._objective, 'metric': 'None', 'num_leaves': 63,
            'learning_rate': 0.05, 'feature_fraction': 0.8, 'bagging_fraction': 0.8,
            'bagging_freq': 5, 'min_child_samples': 50, 'verbose': -1,
        }

        def mae_eval(y_pred, data):
            return 'mae', float(np.mean(np.abs(data.get_label() - y_pred))), False

        self.model = lgb.train(
            params, train_data, num_boost_round=self.n_estimators,
            valid_sets=[val_data], feval=mae_eval,
            callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)],
        )

    def predict(self, df):
        return np.clip(np.round(self.predict_continuous(df)), 0, 7).astype(int)

    def predict_continuous(self, df):
        df = self.prepare_features(df, fit=False)
        return self.model.predict(self.get_feature_matrix(df))


def place_bucketer(place):
    if place == 1: return 0
    elif place <= 3: return 1
    elif place <= 5: return 2
    elif place <= 15: return 3
    elif place <= 30: return 4
    elif place <= 50: return 5
    else: return 6


def get_ranking_derived_buckets(continuous_preds, competition_ids):
    df = pd.DataFrame({'continuous': continuous_preds, 'competition_id': competition_ids})
    df['rank'] = df.groupby('competition_id')['continuous'].rank(method='first')
    df['ranking_bucket'] = df['rank'].apply(place_bucketer)
    return df['ranking_bucket'].values


def evaluate_set(y_true, y_model, y_ranking, mask=None):
    """Evaluate on a subset (filtered to buckets 0-4)."""
    if mask is not None:
        y_true, y_model, y_ranking = y_true[mask], y_model[mask], y_ranking[mask]

    top_mask = y_true <= 4
    y_true, y_model, y_ranking = y_true[top_mask], y_model[top_mask], y_ranking[top_mask]

    n = len(y_true)
    if n == 0:
        return None

    results = {'n': n}

    # Model metrics
    results['m_mae'] = np.mean(np.abs(y_true - y_model))
    results['m_exact'] = np.mean(y_true == y_model)
    results['m_within1'] = np.mean(np.abs(y_true - y_model) <= 1)
    results['m_practical'] = np.mean(y_true <= y_model)

    # Ranking metrics
    results['r_mae'] = np.mean(np.abs(y_true - y_ranking))
    results['r_exact'] = np.mean(y_true == y_ranking)
    results['r_within1'] = np.mean(np.abs(y_true - y_ranking) <= 1)
    results['r_practical'] = np.mean(y_true <= y_ranking)

    # Per-bucket exact accuracy (ranking)
    for b in range(5):
        b_mask = y_true == b
        if b_mask.sum() > 0:
            results[f'r_b{b}_exact'] = (y_ranking[b_mask] == b).mean()
        else:
            results[f'r_b{b}_exact'] = 0

    return results


def evaluate_thresholds(y_true_all, y_ranking_all, mask=None):
    """Threshold identification metrics."""
    if mask is not None:
        y_true_all, y_ranking_all = y_true_all[mask], y_ranking_all[mask]

    results = {}
    for name, thresh in [('winner', 0), ('podium', 1), ('top5', 2), ('top15', 3)]:
        actual = y_true_all <= thresh
        pred = y_ranking_all <= thresh
        tp = (actual & pred).sum()
        n_pred = pred.sum()
        n_actual = actual.sum()

        precision = tp / n_pred if n_pred > 0 else 0
        recall = tp / n_actual if n_actual > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        results[f'{name}_prec'] = precision
        results[f'{name}_rec'] = recall
        results[f'{name}_f1'] = f1

    return results


# Form and team feature names for analysis
FORM_FEATURES = [
    'form_recent_avg_bucket', 'form_recent_best_bucket', 'form_recent_count',
    'form_delta', 'form_profile_recent_avg', 'days_since_last_race',
    'form_vs_field_gap', 'is_improving_form', 'is_fresh', 'is_rusty', 'form_confidence'
]

TEAM_FEATURES = [
    'team_quality_mean', 'team_quality_median', 'team_quality_std',
    'team_quality_min', 'team_quality_max', 'team_quality_p25', 'team_quality_p75',
    'team_size', 'team_depth', 'is_team_best', 'team_support_ratio', 'rider_vs_team_gap'
]


def analyze_feature_importance(model, model_name: str):
    """Analyze feature importance, highlighting form and team features."""
    if hasattr(model, 'model') and hasattr(model.model, 'feature_importance'):
        # LightGBM model
        importance = model.model.feature_importance(importance_type='gain')
        features = model.feature_columns
    elif hasattr(model, 'models') and len(model.models) > 0:
        # OrdinalBucketPredictor with multiple models
        importance = model.models[0].feature_importance(importance_type='gain')
        features = model.feature_columns
    else:
        return None, None, None

    # Create importance DataFrame
    imp_df = pd.DataFrame({'feature': features, 'importance': importance})
    imp_df = imp_df.sort_values('importance', ascending=False)

    # Calculate totals by category
    total_importance = imp_df['importance'].sum()

    form_imp = imp_df[imp_df['feature'].isin(FORM_FEATURES)]['importance'].sum()
    team_imp = imp_df[imp_df['feature'].isin(TEAM_FEATURES)]['importance'].sum()
    other_imp = total_importance - form_imp - team_imp

    form_pct = form_imp / total_importance * 100 if total_importance > 0 else 0
    team_pct = team_imp / total_importance * 100 if total_importance > 0 else 0
    other_pct = other_imp / total_importance * 100 if total_importance > 0 else 0

    return imp_df, (form_pct, team_pct, other_pct), (form_imp, team_imp, other_imp)


def print_feature_importance_summary(models: dict):
    """Print feature importance summary for all models."""
    print("\n" + "=" * 95)
    print("FEATURE IMPORTANCE ANALYSIS - FORM AND TEAM FEATURES")
    print("=" * 95)

    print("\n--- Importance by Feature Category (% of total gain) ---")
    print(f"{'Model':<20} {'Form %':>10} {'Team %':>10} {'Other %':>10}")
    print("-" * 55)

    for name, model in models.items():
        imp_df, pcts, _ = analyze_feature_importance(model, name)
        if pcts:
            form_pct, team_pct, other_pct = pcts
            print(f"{name:<20} {form_pct:>9.1f}% {team_pct:>9.1f}% {other_pct:>9.1f}%")
        else:
            print(f"{name:<20} {'N/A':>10} {'N/A':>10} {'N/A':>10}")

    # Show top form/team features for first model
    first_model = list(models.values())[0]
    imp_df, _, _ = analyze_feature_importance(first_model, "first")

    if imp_df is not None:
        print("\n--- Top Form Features (by importance) ---")
        form_df = imp_df[imp_df['feature'].isin(FORM_FEATURES)].head(10)
        for _, row in form_df.iterrows():
            print(f"  {row['feature']:<35} {row['importance']:>12.1f}")

        print("\n--- Top Team Features (by importance) ---")
        team_df = imp_df[imp_df['feature'].isin(TEAM_FEATURES)].head(10)
        for _, row in team_df.iterrows():
            print(f"  {row['feature']:<35} {row['importance']:>12.1f}")

        print("\n--- Top 20 Overall Features ---")
        for i, (_, row) in enumerate(imp_df.head(20).iterrows()):
            marker = ""
            if row['feature'] in FORM_FEATURES:
                marker = " [FORM]"
            elif row['feature'] in TEAM_FEATURES:
                marker = " [TEAM]"
            print(f"  {i+1:>2}. {row['feature']:<40} {row['importance']:>10.1f}{marker}")


def evaluate_by_profile(test_df, model, profile_col='race_dominant_profile'):
    """Evaluate model performance by race profile."""
    results = {}

    y_true = test_df['place_bucket'].values
    y_continuous = model.predict_continuous(test_df)
    comp_ids = test_df['competition_id'].values
    y_ranking = get_ranking_derived_buckets(y_continuous, comp_ids)

    # Overall
    top_mask = y_true <= 4
    results['Overall'] = {
        'n': top_mask.sum(),
        'mae': np.mean(np.abs(y_true[top_mask] - y_ranking[top_mask])),
        'exact': np.mean(y_true[top_mask] == y_ranking[top_mask]),
    }

    # By profile
    for profile in test_df[profile_col].unique():
        if pd.isna(profile):
            continue
        profile_mask = test_df[profile_col].values == profile
        combined_mask = top_mask & profile_mask

        if combined_mask.sum() < 50:
            continue

        results[profile] = {
            'n': combined_mask.sum(),
            'mae': np.mean(np.abs(y_true[combined_mask] - y_ranking[combined_mask])),
            'exact': np.mean(y_true[combined_mask] == y_ranking[combined_mask]),
        }

    return results


def main():
    print("=" * 95)
    print("TOP FINISHER EVALUATION - PROPER TEMPORAL SPLIT")
    print("Train: 2018-2022 | Val: 2023-H1 | Test: 2023-H2 | Holdout: 2024")
    print("=" * 95)

    # Load data
    db_path = Path(__file__).parent.parent / "webscrape_tools" / "database" / "database" / "cycling_races.db"
    config = DataConfig(db_path=str(db_path), start_date='2018-01-01', min_races_career=10)
    pipeline = CyclingDataPipeline(config)

    df = pipeline.load_training_data()
    df['competition_date'] = pd.to_datetime(df['competition_date'])

    # Proper splits
    train = df[df['competition_date'] < '2023-01-01'].copy()
    val = df[(df['competition_date'] >= '2023-01-01') & (df['competition_date'] < '2023-07-01')].copy()
    test_2023 = df[(df['competition_date'] >= '2023-07-01') & (df['competition_date'] < '2024-01-01')].copy()
    holdout_2024 = df[df['competition_date'] >= '2024-01-01'].copy()

    print(f"\nData splits:")
    print(f"  Train (2018-2022):  {len(train):>8,}")
    print(f"  Val (2023-H1):      {len(val):>8,}")
    print(f"  Test (2023-H2):     {len(test_2023):>8,}")
    print(f"  Holdout (2024):     {len(holdout_2024):>8,}")

    # Top finisher counts
    for name, data in [("Test 2023-H2", test_2023), ("Holdout 2024", holdout_2024)]:
        top = (data['place_bucket'] <= 4).sum()
        print(f"\n{name} top finishers (B0-4): {top:,} ({top/len(data):.1%})")

    # Train models
    models = {}
    configs = [
        ("Standard MAE", None),
        ("Conservative 3x", 3.0),
        ("Bold 0.5x", 0.5),
        ("Very Bold 0.3x", 0.3),
        ("Super Bold 0.1x", 0.1),
    ]

    print("\nTraining models...")
    for name, ratio in configs:
        print(f"  {name}...", end=" ", flush=True)
        if ratio is None:
            model = OrdinalBucketPredictor(BucketPredictorConfig(n_estimators=300, early_stopping_rounds=50))
            model.train(train, val, verbose=False)
        else:
            model = AsymmetricPredictor(asymmetry_ratio=ratio, n_estimators=300)
            model.train(train, val)
        models[name] = model
        print("done")

    # =========================================================================
    # EVALUATE ON 2023-H2 (TEST)
    # =========================================================================
    print("\n" + "=" * 95)
    print("TEST SET: 2023-H2 (Buckets 0-4 only)")
    print("=" * 95)

    y_true_2023 = test_2023['place_bucket'].values
    comp_ids_2023 = test_2023['competition_id'].values

    results_2023 = {}
    thresh_2023 = {}

    for name, model in models.items():
        y_model = model.predict(test_2023)
        y_continuous = model.predict_continuous(test_2023)
        y_ranking = get_ranking_derived_buckets(y_continuous, comp_ids_2023)
        results_2023[name] = evaluate_set(y_true_2023, y_model, y_ranking)
        thresh_2023[name] = evaluate_thresholds(y_true_2023, y_ranking)

    print("\n--- Model Bucket Performance (2023-H2, B0-4) ---")
    print(f"{'Model':<20} {'N':>7} {'MAE':>7} {'Exact':>7} {'W/in1':>7} {'Prac%':>7}")
    print("-" * 60)
    for name in models:
        r = results_2023[name]
        print(f"{name:<20} {r['n']:>7,} {r['m_mae']:>7.3f} {r['m_exact']:>6.1%} {r['m_within1']:>6.1%} {r['m_practical']:>6.1%}")

    print("\n--- Ranking-Derived Bucket Performance (2023-H2, B0-4) ---")
    print(f"{'Model':<20} {'MAE':>7} {'Exact':>7} {'W/in1':>7} {'Prac%':>7}   {'B0':>6} {'B1':>6} {'B2':>6} {'B3':>6} {'B4':>6}")
    print("-" * 95)
    for name in models:
        r = results_2023[name]
        print(f"{name:<20} {r['r_mae']:>7.3f} {r['r_exact']:>6.1%} {r['r_within1']:>6.1%} {r['r_practical']:>6.1%}  "
              f"{r['r_b0_exact']:>6.1%} {r['r_b1_exact']:>6.1%} {r['r_b2_exact']:>6.1%} {r['r_b3_exact']:>6.1%} {r['r_b4_exact']:>6.1%}")

    print("\n--- Threshold Identification (2023-H2) ---")
    print(f"{'Model':<20} {'Win P':>7} {'Win R':>7} {'Pod P':>7} {'Pod R':>7} {'T5 P':>7} {'T5 R':>7} {'T15 P':>7} {'T15 R':>7}")
    print("-" * 95)
    for name in models:
        t = thresh_2023[name]
        print(f"{name:<20} {t['winner_prec']:>6.1%} {t['winner_rec']:>6.1%} "
              f"{t['podium_prec']:>6.1%} {t['podium_rec']:>6.1%} "
              f"{t['top5_prec']:>6.1%} {t['top5_rec']:>6.1%} "
              f"{t['top15_prec']:>6.1%} {t['top15_rec']:>6.1%}")

    # =========================================================================
    # EVALUATE ON 2024 (HOLDOUT)
    # =========================================================================
    print("\n" + "=" * 95)
    print("HOLDOUT SET: 2024 (Buckets 0-4 only)")
    print("=" * 95)

    y_true_2024 = holdout_2024['place_bucket'].values
    comp_ids_2024 = holdout_2024['competition_id'].values

    results_2024 = {}
    thresh_2024 = {}

    for name, model in models.items():
        y_model = model.predict(holdout_2024)
        y_continuous = model.predict_continuous(holdout_2024)
        y_ranking = get_ranking_derived_buckets(y_continuous, comp_ids_2024)
        results_2024[name] = evaluate_set(y_true_2024, y_model, y_ranking)
        thresh_2024[name] = evaluate_thresholds(y_true_2024, y_ranking)

    print("\n--- Model Bucket Performance (2024, B0-4) ---")
    print(f"{'Model':<20} {'N':>7} {'MAE':>7} {'Exact':>7} {'W/in1':>7} {'Prac%':>7}")
    print("-" * 60)
    for name in models:
        r = results_2024[name]
        print(f"{name:<20} {r['n']:>7,} {r['m_mae']:>7.3f} {r['m_exact']:>6.1%} {r['m_within1']:>6.1%} {r['m_practical']:>6.1%}")

    print("\n--- Ranking-Derived Bucket Performance (2024, B0-4) ---")
    print(f"{'Model':<20} {'MAE':>7} {'Exact':>7} {'W/in1':>7} {'Prac%':>7}   {'B0':>6} {'B1':>6} {'B2':>6} {'B3':>6} {'B4':>6}")
    print("-" * 95)
    for name in models:
        r = results_2024[name]
        print(f"{name:<20} {r['r_mae']:>7.3f} {r['r_exact']:>6.1%} {r['r_within1']:>6.1%} {r['r_practical']:>6.1%}  "
              f"{r['r_b0_exact']:>6.1%} {r['r_b1_exact']:>6.1%} {r['r_b2_exact']:>6.1%} {r['r_b3_exact']:>6.1%} {r['r_b4_exact']:>6.1%}")

    print("\n--- Threshold Identification (2024) ---")
    print(f"{'Model':<20} {'Win P':>7} {'Win R':>7} {'Pod P':>7} {'Pod R':>7} {'T5 P':>7} {'T5 R':>7} {'T15 P':>7} {'T15 R':>7}")
    print("-" * 95)
    for name in models:
        t = thresh_2024[name]
        print(f"{name:<20} {t['winner_prec']:>6.1%} {t['winner_rec']:>6.1%} "
              f"{t['podium_prec']:>6.1%} {t['podium_rec']:>6.1%} "
              f"{t['top5_prec']:>6.1%} {t['top5_rec']:>6.1%} "
              f"{t['top15_prec']:>6.1%} {t['top15_rec']:>6.1%}")

    # =========================================================================
    # 2023 vs 2024 COMPARISON (OVERFITTING CHECK)
    # =========================================================================
    print("\n" + "=" * 95)
    print("OVERFITTING CHECK: 2023-H2 vs 2024 DELTA")
    print("(Positive = better on 2024, Negative = worse on 2024)")
    print("=" * 95)

    print("\n--- Ranking-Derived Bucket Deltas ---")
    print(f"{'Model':<20} {'ΔMAE':>8} {'ΔExact':>8} {'ΔW/in1':>8} {'ΔPrac':>8}   {'ΔB0':>7} {'ΔB1':>7} {'ΔB2':>7} {'ΔB3':>7} {'ΔB4':>7}")
    print("-" * 100)
    for name in models:
        r23, r24 = results_2023[name], results_2024[name]
        d_mae = r24['r_mae'] - r23['r_mae']
        d_exact = r24['r_exact'] - r23['r_exact']
        d_w1 = r24['r_within1'] - r23['r_within1']
        d_prac = r24['r_practical'] - r23['r_practical']

        print(f"{name:<20} {d_mae:>+7.3f} {d_exact:>+7.1%} {d_w1:>+7.1%} {d_prac:>+7.1%}  ", end="")
        for b in range(5):
            delta = r24[f'r_b{b}_exact'] - r23[f'r_b{b}_exact']
            print(f" {delta:>+6.1%}", end="")
        print()

    print("\n--- Threshold Identification Deltas ---")
    print(f"{'Model':<20} {'ΔWin P':>8} {'ΔWin R':>8} {'ΔPod P':>8} {'ΔPod R':>8} {'ΔT5 P':>8} {'ΔT5 R':>8} {'ΔT15 P':>8} {'ΔT15 R':>8}")
    print("-" * 100)
    for name in models:
        t23, t24 = thresh_2023[name], thresh_2024[name]
        print(f"{name:<20} "
              f"{t24['winner_prec']-t23['winner_prec']:>+7.1%} {t24['winner_rec']-t23['winner_rec']:>+7.1%} "
              f"{t24['podium_prec']-t23['podium_prec']:>+7.1%} {t24['podium_rec']-t23['podium_rec']:>+7.1%} "
              f"{t24['top5_prec']-t23['top5_prec']:>+7.1%} {t24['top5_rec']-t23['top5_rec']:>+7.1%} "
              f"{t24['top15_prec']-t23['top15_prec']:>+7.1%} {t24['top15_rec']-t23['top15_rec']:>+7.1%}")

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "=" * 95)
    print("SUMMARY: BEST MODEL FOR EACH METRIC")
    print("=" * 95)

    metrics = [
        ('Winner Recall 2023', [(name, thresh_2023[name]['winner_rec']) for name in models]),
        ('Winner Recall 2024', [(name, thresh_2024[name]['winner_rec']) for name in models]),
        ('Podium Recall 2023', [(name, thresh_2023[name]['podium_rec']) for name in models]),
        ('Podium Recall 2024', [(name, thresh_2024[name]['podium_rec']) for name in models]),
        ('Top15 Recall 2023', [(name, thresh_2023[name]['top15_rec']) for name in models]),
        ('Top15 Recall 2024', [(name, thresh_2024[name]['top15_rec']) for name in models]),
        ('B0 Exact 2023', [(name, results_2023[name]['r_b0_exact']) for name in models]),
        ('B0 Exact 2024', [(name, results_2024[name]['r_b0_exact']) for name in models]),
    ]

    print(f"\n{'Metric':<25} {'Best Model':<20} {'Value':>10} {'2nd Best':<20} {'Value':>10}")
    print("-" * 90)
    for metric_name, values in metrics:
        sorted_vals = sorted(values, key=lambda x: x[1], reverse=True)
        best = sorted_vals[0]
        second = sorted_vals[1]
        print(f"{metric_name:<25} {best[0]:<20} {best[1]:>9.1%} {second[0]:<20} {second[1]:>9.1%}")

    # =========================================================================
    # FEATURE IMPORTANCE ANALYSIS
    # =========================================================================
    print_feature_importance_summary(models)

    # =========================================================================
    # PERFORMANCE BY RACE PROFILE
    # =========================================================================
    print("\n" + "=" * 95)
    print("PERFORMANCE BY RACE PROFILE (2024 Holdout, B0-4)")
    print("=" * 95)

    # Use the Standard MAE model for profile analysis
    std_model = models["Standard MAE"]
    profile_results = evaluate_by_profile(holdout_2024, std_model)

    print(f"\n{'Profile':<15} {'N':>8} {'MAE':>8} {'Exact':>8}")
    print("-" * 45)
    for profile in ['Overall', 'sprint', 'hilly', 'mountain', 'breakaway', 'rolling', 'time_trial']:
        if profile in profile_results:
            r = profile_results[profile]
            print(f"{profile:<15} {r['n']:>8,} {r['mae']:>8.3f} {r['exact']:>7.1%}")

    # Compare bold model on hilly/breakaway (where form should help most)
    print("\n--- Bold Model on Hilly/Breakaway Races ---")
    bold_model = models["Very Bold 0.3x"]
    bold_profile = evaluate_by_profile(holdout_2024, bold_model)

    for profile in ['hilly', 'breakaway', 'mountain']:
        if profile in profile_results and profile in bold_profile:
            std_r = profile_results[profile]
            bold_r = bold_profile[profile]
            delta_mae = bold_r['mae'] - std_r['mae']
            delta_exact = bold_r['exact'] - std_r['exact']
            print(f"  {profile:<12} Standard: MAE={std_r['mae']:.3f}, Exact={std_r['exact']:.1%} | "
                  f"Bold: MAE={bold_r['mae']:.3f}, Exact={bold_r['exact']:.1%} | "
                  f"Δ MAE={delta_mae:+.3f}, Δ Exact={delta_exact:+.1%}")

    print("\n" + "=" * 95)
    print("EVALUATION COMPLETE")
    print("=" * 95)


if __name__ == '__main__':
    main()
