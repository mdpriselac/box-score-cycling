"""
Contested-rating gate — baseline vs +contested-Elo features under the
probability gate (MarketProbabilityEvaluator, gate policy 2026-06-11).

Adds four as-of-then features from the contested-comparison Elo
(contested_rating.py: winner-group sprint order + adjacent group-vs-group
comparisons only, K=4, warm-up from 2010):

  contested_rating           rating strictly before the row's competition
  contested_rating_n         cumulative contested comparisons (confidence)
  contested_rating_delta90   rating change over the trailing 90 days
  contested_rating_vs_field  rating minus the competition's mean rating

NaN where unrated (no imputation — LightGBM consumes NaN natively).

Arms: baseline (plain frames) vs +rating (same frames + 4 columns), trained
with the production-aligned bucket+contender stack from the 5-fold harness.
PRIMARY gate metric: market_avg_log_loss over the top-15 contender pool
(per-market binary log loss/Brier/cal for win/podium/top5/top15);
winner/podium capture reported as diagnostics only. Subsets: all / one_day /
stage. 5 folds, paired per-fold deltas.

Usage:
    PYTHONUNBUFFERED=1 uv run python -m cycling_project.prediction_tools.experiments.contested_rating_gate_cv
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from cycling_project.prediction_tools.contested_rating import (
    ContestedRatingConfig,
    DEFAULT_DB_PATH,
    DEFAULT_SNAPSHOT_PATH,
    RATING_FEATURE_COLS,
    attach_rating_features,
    build_and_save,
    load_snapshots,
)
from cycling_project.prediction_tools.evaluation import (
    MarketProbabilityEvaluator,
    Top4ProbabilityEvaluator,
)
from cycling_project.prediction_tools.experiments.stacked_meta_learner_cv_5fold import (
    FOLDS,
    START_DATE,
    _load_full_df,
    _slice_fold,
    _train_bucket_and_contender,
)
from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

OUT_DIR = Path("experiments")

GATE_METRICS = [
    "market_avg_log_loss", "win_log_loss", "podium_log_loss",
    "top5_log_loss", "top15_log_loss", "market_avg_brier",
    "win_cal_ratio", "top15_cal_ratio",
    "race_winner_capture_rate", "race_podium_capture_rate",
]


def eval_arm(test_df: pd.DataFrame, bucket, cont) -> Dict[str, Any]:
    """Top-15 contender-pool market evaluation, per subset (probability gate)."""
    out = {}
    for name, sub in {
        "all": test_df,
        "one_day": test_df[test_df["competition_type"] == "one_day"],
        "stage": test_df[test_df["competition_type"] == "stage"],
    }.items():
        if len(sub) == 0:
            continue
        expected = bucket.predict_continuous(sub)
        d = sub.copy()
        d["classifier_expected_bucket"] = expected
        d["_rank"] = d.groupby("competition_id")["classifier_expected_bucket"].rank()
        cd = d[d["_rank"] <= 15].drop(columns=["_rank"])
        proba = cont.predict_proba(cd)
        y = cd["place_bucket"].values
        n_classes = cont.config.lgb_params.get("num_class", 8)
        if n_classes < 8:
            y = np.clip(y, 0, n_classes - 1)
        m = MarketProbabilityEvaluator.evaluate(y, proba)
        t4 = Top4ProbabilityEvaluator.evaluate(
            y, proba, competition_ids=cd["competition_id"].values
        )
        for k in ("race_winner_capture_rate", "race_podium_capture_rate"):
            if k in t4:
                m[k] = t4[k]
        out[name] = m
    return out


def rating_feature_ranks(cont) -> Optional[Dict[str, Any]]:
    """Gain-importance ranks of the rating features in the contender."""
    try:
        imp_df = cont.get_feature_importance(importance_type="gain")
    except Exception as exc:  # pragma: no cover
        print(f"    [warn] feature importance unavailable: {exc}", flush=True)
        return None
    imp = dict(zip(imp_df["feature"], imp_df["importance"].astype(float)))
    sorted_fi = sorted(imp.items(), key=lambda x: x[1], reverse=True)
    ranks = {}
    for feat in RATING_FEATURE_COLS:
        rank = next((i + 1 for i, (k, _) in enumerate(sorted_fi) if k == feat), None)
        ranks[feat] = {"rank": rank, "gain": imp.get(feat)}
    ranks["n_features"] = len(sorted_fi)
    return ranks


def coverage_stats(df_rated: pd.DataFrame) -> Dict[str, Any]:
    rated = df_rated["contested_rating"].notna()
    stats: Dict[str, Any] = {"all": float(rated.mean()), "n_rows": int(len(df_rated))}
    for t, sub in df_rated.groupby("competition_type"):
        stats[f"type_{t}"] = float(sub["contested_rating"].notna().mean())
    by_year = (
        rated.groupby(df_rated["competition_date"].dt.year).mean().round(4)
    )
    stats["by_year"] = {int(k): float(v) for k, v in by_year.items()}
    return stats


def main():
    started = datetime.now()
    print("=" * 70, flush=True)
    print("CONTESTED-RATING GATE — baseline vs +contested-Elo features", flush=True)
    print("=" * 70, flush=True)
    print(f"Started: {started.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)

    rating_cfg = ContestedRatingConfig()
    if DEFAULT_SNAPSHOT_PATH.exists():
        snapshots = load_snapshots(DEFAULT_SNAPSHOT_PATH)
        print(f"Loaded {len(snapshots):,} rating snapshots from {DEFAULT_SNAPSHOT_PATH}", flush=True)
    else:
        print("Snapshot parquet missing — building from DB...", flush=True)
        snapshots = build_and_save(rating_cfg, DEFAULT_SNAPSHOT_PATH)

    df = _load_full_df()
    print(f"Loaded {len(df):,} training rows, {df['competition_id'].nunique():,} comps", flush=True)

    df_rated = attach_rating_features(df, snapshots, db_path=DEFAULT_DB_PATH)
    assert len(df_rated) == len(df)
    assert (df_rated["competition_id"].to_numpy() == df["competition_id"].to_numpy()).all()
    assert (df_rated["rider_id"].to_numpy() == df["rider_id"].to_numpy()).all()

    cov = coverage_stats(df_rated)
    print(
        f"Rating coverage: all={cov['all']:.1%}  "
        + "  ".join(f"{k[5:]}={v:.1%}" for k, v in cov.items() if k.startswith("type_")),
        flush=True,
    )
    print(f"  by year: {cov['by_year']}", flush=True)

    fold_results: List[Dict[str, Any]] = []
    for i, fold in enumerate(FOLDS):
        print(f"\n{'─' * 60}", flush=True)
        print(f"FOLD {i + 1}/{len(FOLDS)} (test={fold['label']}+)", flush=True)
        print(f"{'─' * 60}", flush=True)

        train_b, val_b, test_b = _slice_fold(df, fold)
        train_r, val_r, test_r = _slice_fold(df_rated, fold)
        if len(test_b) == 0:
            fold_results.append({"fold_label": fold["label"], "skipped": True})
            continue
        print(
            f"  Train {len(train_b):,} / val {len(val_b):,} / test {len(test_b):,} rows  "
            f"(test rating coverage {test_r['contested_rating'].notna().mean():.1%})",
            flush=True,
        )

        print("  Training BASELINE...", flush=True)
        bucket_b, cont_b, _ = _train_bucket_and_contender(train_b, val_b, fold["label"])
        res_b = eval_arm(test_b, bucket_b, cont_b)

        print("  Training +RATING...", flush=True)
        bucket_r, cont_r, _ = _train_bucket_and_contender(train_r, val_r, fold["label"])
        res_r = eval_arm(test_r, bucket_r, cont_r)
        ranks = rating_feature_ranks(cont_r)

        b, r = res_b["all"], res_r["all"]
        print(
            f"  mkt_avg_ll: base={b['market_avg_log_loss']:.4f} rated={r['market_avg_log_loss']:.4f} "
            f"(Δ{r['market_avg_log_loss'] - b['market_avg_log_loss']:+.4f})  "
            f"win_ll Δ{r['win_log_loss'] - b['win_log_loss']:+.4f}  "
            f"top15_ll Δ{r['top15_log_loss'] - b['top15_log_loss']:+.4f}  "
            f"winner_cap Δ{r['race_winner_capture_rate'] - b['race_winner_capture_rate']:+.4f}",
            flush=True,
        )
        if ranks:
            print(
                "  feature ranks: "
                + "  ".join(
                    f"{f.replace('contested_rating', 'cr')}=#{ranks[f]['rank']}"
                    for f in RATING_FEATURE_COLS
                )
                + f" (of {ranks['n_features']})",
                flush=True,
            )

        fold_results.append({
            "fold_label": fold["label"],
            "skipped": False,
            "baseline": res_b,
            "rated": res_r,
            "rating_feature_ranks": ranks,
        })

    # ----------------------------------------------------------------
    # Aggregate paired deltas
    # ----------------------------------------------------------------
    usable = [fr for fr in fold_results if not fr.get("skipped")]
    agg: Dict[str, Any] = {}
    for subset in ("all", "one_day", "stage"):
        agg[subset] = {}
        for k in GATE_METRICS:
            deltas = [
                fr["rated"][subset][k] - fr["baseline"][subset][k]
                for fr in usable
                if k in fr["rated"].get(subset, {}) and k in fr["baseline"].get(subset, {})
            ]
            if deltas:
                agg[subset][k] = {
                    "mean": float(np.mean(deltas)),
                    "std": float(np.std(deltas)),
                    "per_fold": [float(x) for x in deltas],
                }

    print("\n" + "=" * 70, flush=True)
    print("PAIRED DELTAS (rated - baseline), mean±std across folds:", flush=True)
    print("=" * 70, flush=True)
    for subset in ("all", "one_day", "stage"):
        for k in GATE_METRICS:
            d = agg[subset].get(k)
            if d:
                per = "  ".join(f"{v:+.4f}" for v in d["per_fold"])
                print(
                    f"  {subset:<8s} {k:<28s} {d['mean']:+.4f}±{d['std']:.4f}   [{per}]",
                    flush=True,
                )

    ended = datetime.now()
    out = {
        "started_at": started.isoformat(),
        "ended_at": ended.isoformat(),
        "duration_seconds": (ended - started).total_seconds(),
        "config": {
            "folds": FOLDS,
            "start_date": START_DATE,
            "rating_engine": {
                "k_factor": rating_cfg.k_factor,
                "init_rating": rating_cfg.init_rating,
                "scale": rating_cfg.scale,
                "winner_group_top_n": rating_cfg.winner_group_top_n,
                "group_cap": rating_cfg.group_cap,
                "start_date": rating_cfg.start_date,
            },
            "rating_feature_cols": RATING_FEATURE_COLS,
            "snapshot_path": str(DEFAULT_SNAPSHOT_PATH),
            "n_snapshot_rows": int(len(snapshots)),
        },
        "coverage": cov,
        "fold_results": fold_results,
        "aggregated_deltas": agg,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = ended.strftime("%Y%m%d_%H%M%S")
    path = OUT_DIR / f"contested_rating_gate_cv_{ts}.json"
    path.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nSaved {path}  ({(ended - started).total_seconds() / 60:.1f} min)", flush=True)


if __name__ == "__main__":
    main()
