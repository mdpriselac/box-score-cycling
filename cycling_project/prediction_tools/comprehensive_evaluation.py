"""
Comprehensive Model Evaluation

Compares multiple prediction strategies across race types, tour levels, and profiles:
1. Random baseline
2. Bib order (team_bib * 10 + personal_bib)
3. Naive historical average
4. Model-predicted bucket (direct)
5. Ranking-derived bucket

Outputs a detailed markdown report.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from datetime import datetime
from collections import defaultdict
from typing import Dict, List

try:
    from prediction_tools.data_pipeline import CyclingDataPipeline, DataConfig
    from prediction_tools.feature_engineering import FeatureEngineer
    from prediction_tools.bucket_predictor import OrdinalBucketPredictor, BucketPredictorConfig
except ModuleNotFoundError:
    from data_pipeline import CyclingDataPipeline, DataConfig
    from feature_engineering import FeatureEngineer
    from bucket_predictor import OrdinalBucketPredictor, BucketPredictorConfig

import lightgbm as lgb


# Feature categories for importance analysis
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


def place_to_bucket(place):
    """Convert place to bucket."""
    if place == 1: return 0
    elif place <= 3: return 1
    elif place <= 5: return 2
    elif place <= 15: return 3
    elif place <= 30: return 4
    elif place <= 50: return 5
    else: return 6


BUCKET_NAMES = {
    0: "Winner (1st)",
    1: "Podium (2-3)",
    2: "Top 5 (4-5)",
    3: "Top 15 (6-15)",
    4: "Top 30 (16-30)",
    5: "Top 50 (31-50)",
    6: "Finisher (51+)",
}


class AsymmetricPredictor:
    """Predictor with configurable asymmetry ratio (Very Bold 0.3x)."""

    def __init__(self, asymmetry_ratio: float = 0.3, n_estimators: int = 300):
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

    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance from the trained model."""
        if self.model is None:
            return {}
        importance = self.model.feature_importance(importance_type='gain')
        return dict(zip(self.feature_columns, importance))

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


def compute_metrics(y_true, y_pred, prefix=""):
    """Compute standard metrics."""
    metrics = {}
    n = len(y_true)
    if n == 0:
        return {f"{prefix}n": 0}

    metrics[f"{prefix}n"] = n
    metrics[f"{prefix}mae"] = np.mean(np.abs(y_true - y_pred))
    metrics[f"{prefix}exact"] = np.mean(y_true == y_pred)
    metrics[f"{prefix}within1"] = np.mean(np.abs(y_true - y_pred) <= 1)
    metrics[f"{prefix}practical"] = np.mean(y_true <= y_pred)

    return metrics


def compute_threshold_metrics(y_true, y_pred):
    """Compute precision/recall for each threshold."""
    thresholds = {
        "top5": 2,
        "top15": 3,
        "top30": 4,
    }

    metrics = {}
    for name, thresh in thresholds.items():
        actual_in = y_true <= thresh
        pred_in = y_pred <= thresh
        tp = (actual_in & pred_in).sum()
        n_pred = pred_in.sum()
        n_actual = actual_in.sum()

        precision = tp / n_pred if n_pred > 0 else 0
        recall = tp / n_actual if n_actual > 0 else 0

        metrics[f"{name}_precision"] = precision
        metrics[f"{name}_recall"] = recall

    return metrics


def generate_all_predictions(test_df, model):
    """Generate all prediction strategies for test data."""
    results = []

    # Get average columns for naive baseline
    avg_cols = [c for c in ['stage_avg_bucket', 'one_day_avg_bucket', 'gc_avg_bucket']
                if c in test_df.columns]

    for comp_id, race in test_df.groupby('competition_id'):
        if len(race) < 10:
            continue

        race = race.copy()
        n = len(race)

        # 1. Random baseline - random ranking
        race['random_rank'] = np.random.permutation(n) + 1
        race['random_bucket'] = race['random_rank'].apply(place_to_bucket)

        # 2. Bib order baseline - team_bib * 10 + personal_bib
        team_bib = race['team_bib'].fillna(99)
        personal_bib = race['personal_bib'].fillna(10)
        race['bib_score'] = team_bib * 10 + personal_bib + np.random.random(n) * 0.01
        race['bib_rank'] = race['bib_score'].rank(method='first')
        race['bib_bucket'] = race['bib_rank'].apply(place_to_bucket)

        # 3. Naive historical baseline - average of bucket averages
        if avg_cols:
            race['naive_score'] = race[avg_cols].mean(axis=1)
        else:
            race['naive_score'] = 4.0  # default mid-field
        race['naive_rank'] = race['naive_score'].rank(method='first')
        race['naive_bucket'] = race['naive_rank'].apply(place_to_bucket)

        # 4 & 5. Model predictions
        race['model_bucket'] = model.predict(race)
        continuous = model.predict_continuous(race)
        race['model_rank'] = pd.Series(continuous, index=race.index).rank(method='first')
        race['ranking_bucket'] = race['model_rank'].apply(place_to_bucket)

        # Get race metadata
        race_type = race['competition_type'].iloc[0] if 'competition_type' in race.columns else 'unknown'
        tour_level = race['race_category'].iloc[0] if 'race_category' in race.columns else 'unknown'
        profile = race['race_dominant_profile'].iloc[0] if 'race_dominant_profile' in race.columns else 'unknown'
        year = pd.to_datetime(race['competition_date'].iloc[0]).year

        result_cols = ['rider_id', 'place_bucket', 'random_bucket', 'bib_bucket',
                       'naive_bucket', 'model_bucket', 'ranking_bucket', 'competition_id']
        result = race[result_cols].copy()
        result['race_type'] = race_type
        result['tour_level'] = tour_level
        result['profile'] = profile
        result['year'] = year
        result['field_size'] = n

        results.append(result)

    return pd.concat(results, ignore_index=True)


def evaluate_segment(df, segment_name):
    """Evaluate all strategies on a segment of data."""
    y_true = df['place_bucket'].values

    # Filter to top finishers only (B0-4)
    top_mask = y_true <= 4
    y_true_top = y_true[top_mask]

    strategies = {
        'Random': df['random_bucket'].values,
        'Bib Order': df['bib_bucket'].values,
        'Naive (Hist Avg)': df['naive_bucket'].values,
        'Model Direct': df['model_bucket'].values,
        'Model Ranking': df['ranking_bucket'].values,
    }

    results = {'segment': segment_name, 'n_total': len(df), 'n_top_finishers': top_mask.sum()}

    for strat_name, y_pred in strategies.items():
        y_pred_top = y_pred[top_mask]

        # Standard metrics on top finishers
        metrics = compute_metrics(y_true_top, y_pred_top)
        for k, v in metrics.items():
            results[f"{strat_name}_{k}"] = v

        # Threshold metrics on all data
        thresh_metrics = compute_threshold_metrics(y_true, y_pred)
        for k, v in thresh_metrics.items():
            results[f"{strat_name}_{k}"] = v

    return results


def format_pct(val):
    """Format percentage."""
    return f"{val*100:.1f}%"


def generate_markdown_report(all_results, overall_results, output_path):
    """Generate comprehensive markdown report."""

    lines = []
    lines.append("# Comprehensive Model Evaluation Report")
    lines.append("")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    # Overview
    lines.append("## Overview")
    lines.append("")
    lines.append("This report compares five prediction strategies for cycling race results:")
    lines.append("")
    lines.append("1. **Random**: Random ranking of riders")
    lines.append("2. **Bib Order**: Rank by team_bib * 10 + personal_bib (lower = better)")
    lines.append("3. **Naive (Hist Avg)**: Rank by rider's historical average bucket")
    lines.append("4. **Model Direct**: Direct bucket prediction from model (rounded)")
    lines.append("5. **Model Ranking**: Ranking-derived buckets (force race ranking, then bucket)")
    lines.append("")

    # Data summary
    lines.append("## Data Summary")
    lines.append("")
    lines.append(f"- **Total predictions**: {overall_results['n_total']:,}")
    lines.append(f"- **Top finishers (B0-4)**: {overall_results['n_top_finishers']:,}")
    lines.append("")

    # Overall results
    lines.append("## Overall Results")
    lines.append("")

    # Threshold precision table
    lines.append("### Threshold Identification Precision")
    lines.append("")
    lines.append("*When we predict a rider will finish in the top X, what percentage actually do?*")
    lines.append("")
    lines.append("| Strategy | Top 5 | Top 15 | Top 30 |")
    lines.append("|----------|-------|--------|--------|")

    strategies = ['Random', 'Bib Order', 'Naive (Hist Avg)', 'Model Direct', 'Model Ranking']
    for strat in strategies:
        top5 = format_pct(overall_results.get(f"{strat}_top5_precision", 0))
        top15 = format_pct(overall_results.get(f"{strat}_top15_precision", 0))
        top30 = format_pct(overall_results.get(f"{strat}_top30_precision", 0))
        lines.append(f"| {strat} | {top5} | {top15} | {top30} |")

    lines.append("")

    # Standard metrics table
    lines.append("### Standard Metrics (Top Finishers B0-4 Only)")
    lines.append("")
    lines.append("| Strategy | MAE | Exact | Within-1 | Practical Success |")
    lines.append("|----------|-----|-------|----------|-------------------|")

    for strat in strategies:
        mae = overall_results.get(f"{strat}_mae", 0)
        exact = format_pct(overall_results.get(f"{strat}_exact", 0))
        within1 = format_pct(overall_results.get(f"{strat}_within1", 0))
        practical = format_pct(overall_results.get(f"{strat}_practical", 0))
        lines.append(f"| {strat} | {mae:.3f} | {exact} | {within1} | {practical} |")

    lines.append("")

    # Model lift analysis
    lines.append("### Model Lift Over Baselines")
    lines.append("")
    lines.append("*Relative improvement in Top 15 precision:*")
    lines.append("")

    model_top15 = overall_results.get("Model Ranking_top15_precision", 0)
    random_top15 = overall_results.get("Random_top15_precision", 0)
    bib_top15 = overall_results.get("Bib Order_top15_precision", 0)
    naive_top15 = overall_results.get("Naive (Hist Avg)_top15_precision", 0)

    if random_top15 > 0:
        lines.append(f"- vs Random: **{model_top15/random_top15:.1f}x** improvement")
    if bib_top15 > 0:
        lines.append(f"- vs Bib Order: **{model_top15/bib_top15:.1f}x** improvement")
    if naive_top15 > 0:
        lines.append(f"- vs Naive (Hist Avg): **{model_top15/naive_top15:.1f}x** improvement ({(model_top15/naive_top15 - 1)*100:.0f}% relative)")

    lines.append("")

    # Breakdown sections
    def add_breakdown_section(title, key, segments):
        lines.append(f"## {title}")
        lines.append("")

        # Threshold precision
        lines.append("### Threshold Precision by " + title.replace(" Breakdown", ""))
        lines.append("")
        lines.append("*When we predict top 15, what % actually finish top 15 or better?*")
        lines.append("")
        lines.append(f"| {key} | N | Random | Bib | Naive | Model Direct | Model Ranking |")
        lines.append("|" + "-|"*7)

        for seg_results in segments:
            seg_name = seg_results['segment']
            n = seg_results['n_top_finishers']
            random_p = format_pct(seg_results.get("Random_top15_precision", 0))
            bib_p = format_pct(seg_results.get("Bib Order_top15_precision", 0))
            naive_p = format_pct(seg_results.get("Naive (Hist Avg)_top15_precision", 0))
            model_d = format_pct(seg_results.get("Model Direct_top15_precision", 0))
            model_r = format_pct(seg_results.get("Model Ranking_top15_precision", 0))
            lines.append(f"| {seg_name} | {n:,} | {random_p} | {bib_p} | {naive_p} | {model_d} | {model_r} |")

        lines.append("")

        # Practical success by segment
        lines.append("### Practical Success by " + title.replace(" Breakdown", "") + " (Top Finishers)")
        lines.append("")
        lines.append("*When predicting bucket X, what % finish at bucket X or better?*")
        lines.append("")
        lines.append(f"| {key} | Random | Bib | Naive | Model Direct | Model Ranking |")
        lines.append("|" + "-|"*6)

        for seg_results in segments:
            seg_name = seg_results['segment']
            random_p = format_pct(seg_results.get("Random_practical", 0))
            bib_p = format_pct(seg_results.get("Bib Order_practical", 0))
            naive_p = format_pct(seg_results.get("Naive (Hist Avg)_practical", 0))
            model_d = format_pct(seg_results.get("Model Direct_practical", 0))
            model_r = format_pct(seg_results.get("Model Ranking_practical", 0))
            lines.append(f"| {seg_name} | {random_p} | {bib_p} | {naive_p} | {model_d} | {model_r} |")

        lines.append("")

        # MAE comparison
        lines.append("### MAE by " + title.replace(" Breakdown", "") + " (Top Finishers)")
        lines.append("")
        lines.append(f"| {key} | Random | Bib | Naive | Model Direct | Model Ranking |")
        lines.append("|" + "-|"*6)

        for seg_results in segments:
            seg_name = seg_results['segment']
            random_m = seg_results.get("Random_mae", 0)
            bib_m = seg_results.get("Bib Order_mae", 0)
            naive_m = seg_results.get("Naive (Hist Avg)_mae", 0)
            model_d = seg_results.get("Model Direct_mae", 0)
            model_r = seg_results.get("Model Ranking_mae", 0)
            lines.append(f"| {seg_name} | {random_m:.2f} | {bib_m:.2f} | {naive_m:.2f} | {model_d:.2f} | {model_r:.2f} |")

        lines.append("")

    # Add breakdown sections
    if 'by_year' in all_results:
        add_breakdown_section("Year Breakdown", "Year", all_results['by_year'])

    if 'by_race_type' in all_results:
        add_breakdown_section("Race Type Breakdown", "Type", all_results['by_race_type'])

    if 'by_tour_level' in all_results:
        add_breakdown_section("Tour Level Breakdown", "Level", all_results['by_tour_level'])

    if 'by_profile' in all_results:
        add_breakdown_section("Race Profile Breakdown", "Profile", all_results['by_profile'])

    # Key insights
    lines.append("## Key Insights")
    lines.append("")

    # Find best/worst segments for model
    if 'by_profile' in all_results:
        profile_results = all_results['by_profile']
        best_profile = max(profile_results, key=lambda x: x.get("Model Ranking_top15_precision", 0))
        worst_profile = min(profile_results, key=lambda x: x.get("Model Ranking_top15_precision", 0))

        lines.append("### Model Performance by Race Profile")
        lines.append("")
        lines.append(f"- **Best**: {best_profile['segment']} ({format_pct(best_profile.get('Model Ranking_top15_precision', 0))} top-15 precision)")
        lines.append(f"- **Worst**: {worst_profile['segment']} ({format_pct(worst_profile.get('Model Ranking_top15_precision', 0))} top-15 precision)")
        lines.append("")

    if 'by_race_type' in all_results:
        type_results = all_results['by_race_type']
        best_type = max(type_results, key=lambda x: x.get("Model Ranking_top15_precision", 0))

        lines.append("### Model Performance by Race Type")
        lines.append("")
        lines.append(f"- **Best**: {best_type['segment']} ({format_pct(best_type.get('Model Ranking_top15_precision', 0))} top-15 precision)")
        lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append("| Comparison | Top 5 Precision | Top 15 Precision | Top 30 Precision |")
    lines.append("|------------|-----------------|------------------|------------------|")

    for strat in strategies:
        top5 = format_pct(overall_results.get(f"{strat}_top5_precision", 0))
        top15 = format_pct(overall_results.get(f"{strat}_top15_precision", 0))
        top30 = format_pct(overall_results.get(f"{strat}_top30_precision", 0))
        lines.append(f"| {strat} | {top5} | {top15} | {top30} |")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*Report generated by comprehensive_evaluation.py*")

    # Write to file
    with open(output_path, 'w') as f:
        f.write('\n'.join(lines))

    return '\n'.join(lines)


def analyze_feature_importance(model: AsymmetricPredictor) -> Dict[str, any]:
    """Analyze feature importance by category."""
    importance = model.get_feature_importance()
    if not importance:
        return {}

    total_importance = sum(importance.values())

    # Calculate category totals
    form_total = sum(importance.get(f, 0) for f in FORM_FEATURES)
    team_total = sum(importance.get(f, 0) for f in TEAM_FEATURES)
    other_total = total_importance - form_total - team_total

    # Get top features by category
    form_importance = [(f, importance.get(f, 0)) for f in FORM_FEATURES if importance.get(f, 0) > 0]
    team_importance = [(f, importance.get(f, 0)) for f in TEAM_FEATURES if importance.get(f, 0) > 0]

    form_importance.sort(key=lambda x: x[1], reverse=True)
    team_importance.sort(key=lambda x: x[1], reverse=True)

    # Get top 20 overall
    all_sorted = sorted(importance.items(), key=lambda x: x[1], reverse=True)[:20]

    return {
        'total': total_importance,
        'form_pct': form_total / total_importance * 100 if total_importance > 0 else 0,
        'team_pct': team_total / total_importance * 100 if total_importance > 0 else 0,
        'other_pct': other_total / total_importance * 100 if total_importance > 0 else 0,
        'top_form': form_importance[:5],
        'top_team': team_importance[:5],
        'top_overall': all_sorted
    }


def print_feature_importance_summary(analysis: Dict):
    """Print feature importance summary to console."""
    print("\n" + "=" * 70)
    print("FEATURE IMPORTANCE ANALYSIS - FORM AND TEAM FEATURES")
    print("=" * 70)

    print(f"\n--- Importance by Category (% of total gain) ---")
    print(f"  Form features:  {analysis['form_pct']:5.1f}%")
    print(f"  Team features:  {analysis['team_pct']:5.1f}%")
    print(f"  Other features: {analysis['other_pct']:5.1f}%")

    print(f"\n--- Top Form Features ---")
    for feat, imp in analysis['top_form']:
        marker = " [FORM]"
        print(f"  {feat:<35} {imp:>12.1f}")

    print(f"\n--- Top Team Features ---")
    for feat, imp in analysis['top_team']:
        print(f"  {feat:<35} {imp:>12.1f}")

    print(f"\n--- Top 20 Overall Features ---")
    for i, (feat, imp) in enumerate(analysis['top_overall'], 1):
        marker = ""
        if feat in FORM_FEATURES:
            marker = " [FORM]"
        elif feat in TEAM_FEATURES:
            marker = " [TEAM]"
        print(f"  {i:2}. {feat:<40} {imp:>12.1f}{marker}")


def main():
    print("=" * 70)
    print("COMPREHENSIVE MODEL EVALUATION")
    print("=" * 70)

    # Load data
    print("\nLoading data...")
    db_path = Path(__file__).parent.parent / "webscrape_tools" / "database" / "database" / "cycling_races.db"
    config = DataConfig(db_path=str(db_path), start_date='2018-01-01', min_races_career=10)
    pipeline = CyclingDataPipeline(config)

    df = pipeline.load_training_data()
    df['competition_date'] = pd.to_datetime(df['competition_date'])

    # Split data: Train through 2023, Val 2023-H2, Test 2024, Holdout 2025
    train = df[df['competition_date'] < '2023-07-01'].copy()
    val = df[(df['competition_date'] >= '2023-07-01') & (df['competition_date'] < '2024-01-01')].copy()
    test = df[(df['competition_date'] >= '2024-01-01') & (df['competition_date'] < '2025-01-01')].copy()
    holdout = df[df['competition_date'] >= '2025-01-01'].copy()

    print(f"Train (2018-2023H1): {len(train):,}")
    print(f"Val (2023-H2):       {len(val):,}")
    print(f"Test (2024):         {len(test):,}")
    print(f"Holdout (2025):      {len(holdout):,}")

    # Train model
    print("\nTraining Very Bold 0.3x model...")
    model = AsymmetricPredictor(asymmetry_ratio=0.3, n_estimators=300)
    model.train(train, val)
    print("Done.")

    # Generate predictions for test (2024)
    print("\nGenerating predictions for TEST (2024)...")
    test_predictions = generate_all_predictions(test, model)
    print(f"Test predictions: {len(test_predictions):,} | Races: {test_predictions['competition_id'].nunique():,}")

    # Generate predictions for holdout (2025)
    print("Generating predictions for HOLDOUT (2025)...")
    holdout_predictions = generate_all_predictions(holdout, model)
    print(f"Holdout predictions: {len(holdout_predictions):,} | Races: {holdout_predictions['competition_id'].nunique():,}")

    # Evaluate test set (2024)
    print("\n" + "=" * 70)
    print("TEST SET: 2024")
    print("=" * 70)
    test_overall = evaluate_segment(test_predictions, "2024 Test")

    # Evaluate holdout set (2025)
    print("\n" + "=" * 70)
    print("HOLDOUT SET: 2025")
    print("=" * 70)
    holdout_overall = evaluate_segment(holdout_predictions, "2025 Holdout")

    # Build all_results for test set (2024) - used for markdown report
    all_results = {'overall': test_overall}

    # By race type (test)
    print("\nEvaluating test set by race type...")
    by_race_type = []
    for race_type in test_predictions['race_type'].unique():
        seg_df = test_predictions[test_predictions['race_type'] == race_type]
        if len(seg_df) > 500:
            by_race_type.append(evaluate_segment(seg_df, race_type.title()))
    all_results['by_race_type'] = sorted(by_race_type, key=lambda x: x['n_total'], reverse=True)

    # By tour level (test)
    by_tour_level = []
    for level in test_predictions['tour_level'].unique():
        seg_df = test_predictions[test_predictions['tour_level'] == level]
        if len(seg_df) > 500:
            by_tour_level.append(evaluate_segment(seg_df, level.upper() if level else 'Unknown'))
    all_results['by_tour_level'] = sorted(by_tour_level, key=lambda x: x['n_total'], reverse=True)

    # By profile (test)
    print("Evaluating test set by race profile...")
    by_profile_test = []
    for profile in test_predictions['profile'].unique():
        seg_df = test_predictions[test_predictions['profile'] == profile]
        if len(seg_df) > 200:
            by_profile_test.append(evaluate_segment(seg_df, profile.title() if profile else 'Unknown'))
    all_results['by_profile'] = sorted(by_profile_test, key=lambda x: x['n_total'], reverse=True)

    # By profile (holdout)
    print("Evaluating holdout set by race profile...")
    by_profile_holdout = []
    for profile in holdout_predictions['profile'].unique():
        seg_df = holdout_predictions[holdout_predictions['profile'] == profile]
        if len(seg_df) > 200:
            by_profile_holdout.append(evaluate_segment(seg_df, profile.title() if profile else 'Unknown'))
    by_profile_holdout = sorted(by_profile_holdout, key=lambda x: x['n_total'], reverse=True)

    # Generate report for test set
    print("\nGenerating markdown report...")
    output_path = Path(__file__).parent / "EVALUATION_REPORT.md"
    report = generate_markdown_report(all_results, test_overall, output_path)
    print(f"Report saved to: {output_path}")

    # Print comparison summary
    print("\n" + "=" * 70)
    print("COMPARISON: TEST (2024) vs HOLDOUT (2025)")
    print("=" * 70)
    print(f"{'Metric':<25} {'2024 Test':>12} {'2025 Holdout':>14} {'Delta':>10}")
    print("-" * 65)

    metrics_to_compare = [
        ('Model Ranking_top15_precision', 'Top 15 Precision'),
        ('Model Ranking_top30_precision', 'Top 30 Precision'),
        ('Model Ranking_mae', 'MAE'),
        ('Model Ranking_exact', 'Exact Match'),
        ('Model Ranking_within1', 'Within-1'),
    ]

    for key, label in metrics_to_compare:
        test_val = test_overall.get(key, 0)
        holdout_val = holdout_overall.get(key, 0)
        delta = holdout_val - test_val
        if 'mae' in key.lower():
            print(f"{label:<25} {test_val:>12.3f} {holdout_val:>14.3f} {delta:>+10.3f}")
        else:
            print(f"{label:<25} {test_val:>11.1%} {holdout_val:>13.1%} {delta:>+9.1%}")

    # Overfitting assessment
    test_t15 = test_overall.get('Model Ranking_top15_precision', 0)
    holdout_t15 = holdout_overall.get('Model Ranking_top15_precision', 0)
    delta_t15 = holdout_t15 - test_t15

    print("\n" + "-" * 65)
    if abs(delta_t15) < 0.02:
        print("✓ OVERFITTING CHECK: PASSED - Holdout performance similar to test")
    elif delta_t15 < -0.02:
        print("⚠ OVERFITTING CHECK: WARNING - Performance degraded on holdout")
    else:
        print("✓ OVERFITTING CHECK: PASSED - Holdout performance actually better!")

    # Quick summary tables
    print("\n" + "=" * 70)
    print("QUICK SUMMARY - Top 15 Precision by Strategy")
    print("=" * 70)
    print(f"{'Strategy':<20} {'2024 Test':>12} {'2025 Holdout':>14}")
    print("-" * 50)
    for strat in ['Random', 'Bib Order', 'Naive (Hist Avg)', 'Model Direct', 'Model Ranking']:
        test_p = test_overall.get(f"{strat}_top15_precision", 0)
        holdout_p = holdout_overall.get(f"{strat}_top15_precision", 0)
        print(f"{strat:<20} {test_p:>11.1%} {holdout_p:>13.1%}")

    # Feature importance analysis
    print("\nAnalyzing feature importance...")
    importance_analysis = analyze_feature_importance(model)
    if importance_analysis:
        print_feature_importance_summary(importance_analysis)

    # Profile comparison: Test vs Holdout
    print("\n" + "=" * 70)
    print("PERFORMANCE BY RACE PROFILE: TEST (2024) vs HOLDOUT (2025)")
    print("=" * 70)
    print(f"{'Profile':<12} {'Test N':>8} {'Test T15':>10} {'Hold N':>8} {'Hold T15':>10} {'Delta':>8}")
    print("-" * 60)

    # Create lookup for holdout by profile
    holdout_by_profile = {seg['segment']: seg for seg in by_profile_holdout}

    for seg in by_profile_test:
        profile = seg['segment']
        test_n = seg['n_top_finishers']
        test_p = seg.get('Model Ranking_top15_precision', 0)

        holdout_seg = holdout_by_profile.get(profile, {})
        holdout_n = holdout_seg.get('n_top_finishers', 0)
        holdout_p = holdout_seg.get('Model Ranking_top15_precision', 0)

        delta = holdout_p - test_p if holdout_n > 0 else 0
        print(f"{profile:<12} {test_n:>8,} {test_p:>9.1%} {holdout_n:>8,} {holdout_p:>9.1%} {delta:>+7.1%}")

    print("\n" + "=" * 70)
    print("EVALUATION COMPLETE")
    print("=" * 70)


if __name__ == '__main__':
    main()
