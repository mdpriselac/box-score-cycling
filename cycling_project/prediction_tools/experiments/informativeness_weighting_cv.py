"""
Placement-informativeness weighting gate — 5-fold CV.

Hypothesis (user insight): within a same-time finishing group, placements are
arbitrary EXCEPT near the front of the group where riders genuinely contest
(sprint order is real skill). Training currently fits that noise — 58% of
rows are bucket 6, many of them mid-blob placements.

Treatment: per-row sample weight on the BUCKET predictor (the ranking
backbone) based on position within the rider's same-time group (1.0s
consecutive-gap grouping, identical to engineered_metrics.identify_groups):

    w = 1.0                      if pos_in_group <= K
    w = max(floor, K / pos_in_group)   otherwise

Time-separated riders are singleton groups -> always full weight. GC comps
and rows without decomposition -> 1.0. Class-balance weights stay on
(informativeness multiplies them). Val stays unweighted-by-informativeness
so early stopping optimizes the honest objective. Contender stage unchanged.

Arms: baseline / W1 (K=10, floor=0.25) / W2 (K=15, floor=0.5).
No new features anywhere — pure target-side reweighting.

Usage:
    PYTHONUNBUFFERED=1 uv run python -m cycling_project.prediction_tools.experiments.informativeness_weighting_cv
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

from cycling_project.prediction_tools.experiments.contest_signature_gate_cv import (
    PRIMARY_METRICS,
    eval_subsets,
)
from cycling_project.prediction_tools.experiments.stacked_meta_learner_cv_5fold import (
    CONTENDER_CONFIG,
    FOLDS,
    START_DATE,
    _load_full_df,
    _slice_fold,
    _train_bucket_and_contender,
)
from cycling_project.prediction_tools.training import ModelTrainer, TrainingConfig
from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

OUT_DIR = Path("experiments")
DB_PATH = (
    Path(__file__).parents[2] / "webscrape_tools" / "database" / "database" / "cycling_races.db"
)
GROUP_THRESHOLD_S = 1.0
ARMS = [
    {"name": "W1", "k_full": 10, "floor": 0.25},
    {"name": "W2", "k_full": 15, "floor": 0.5},
]


def compute_pos_in_group() -> pd.DataFrame:
    """(competition_id, rider_id) -> position within same-time group, road comps."""
    q = """
        SELECT rr.competition_id, rr.rider_id, rr.place, rr.time_gap
        FROM rider_results rr
        JOIN competitions c ON c.id = rr.competition_id
        WHERE c.competition_type IN ('one_day', 'stage')
    """
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query(q, conn)
    df = df.dropna(subset=["time_gap"]).sort_values(["competition_id", "place"])

    gaps = df["time_gap"].to_numpy()
    comp = df["competition_id"].to_numpy()
    new_comp = np.r_[True, comp[1:] != comp[:-1]]
    new_group = new_comp | (np.r_[0.0, np.diff(gaps)] > GROUP_THRESHOLD_S)
    group_id = np.cumsum(new_group)
    # position within group = running count since last group start
    idx = np.arange(len(df))
    group_start = np.maximum.accumulate(np.where(new_group, idx, 0))
    df["pos_in_group"] = idx - group_start + 1
    logger.info(
        "Group decomposition: %d rows, %d comps, median pos %d",
        len(df), df["competition_id"].nunique(), int(df["pos_in_group"].median()),
    )
    return df[["competition_id", "rider_id", "pos_in_group"]]


def weights_for(df: pd.DataFrame, pos: pd.DataFrame, k_full: int, floor: float) -> np.ndarray:
    m = df[["competition_id", "rider_id"]].merge(pos, on=["competition_id", "rider_id"], how="left")
    p = m["pos_in_group"].to_numpy(dtype=float)
    w = np.where(np.isnan(p), 1.0, np.where(p <= k_full, 1.0, np.maximum(floor, k_full / p)))
    return w


def train_weighted(
    train_df: pd.DataFrame, val_df: pd.DataFrame, fold_label: str, w: np.ndarray
) -> Tuple[Any, Any]:
    cfg = TrainingConfig(
        start_date=START_DATE,
        train_end_date=train_df["competition_date"].max().strftime("%Y-%m-%d"),
        val_end_date=val_df["competition_date"].max().strftime("%Y-%m-%d"),
        bucket_n_estimators=CONTENDER_CONFIG["n_estimators"],
        bucket_early_stopping=CONTENDER_CONFIG["early_stopping"],
        probability_n_estimators=CONTENDER_CONFIG["n_estimators"],
        probability_early_stopping=CONTENDER_CONFIG["early_stopping"],
        time_gap_n_estimators=CONTENDER_CONFIG["n_estimators"],
        time_gap_early_stopping=CONTENDER_CONFIG["early_stopping"],
        contender_top_n=CONTENDER_CONFIG["contender_top_n"],
        contender_learning_rate=CONTENDER_CONFIG["contender_learning_rate"],
        contender_use_oof=CONTENDER_CONFIG["contender_use_oof"],
        contender_n_classes=CONTENDER_CONFIG["contender_n_classes"],
        include_gradient_features=CONTENDER_CONFIG["include_gradient_features"],
        fold_label=fold_label,
        train_time_gap=False,
        train_probability=False,
        train_calibrated_probability=False,
        train_contender_probability=True,
        verbose=False,
    )
    trainer = ModelTrainer(cfg)
    bucket, _ = trainer.train_bucket_predictor(train_df, val_df, external_weights=w)
    cont, _ = trainer.train_contender_predictor(train_df, val_df, bucket)
    return bucket, cont


def main():
    started = datetime.now()
    print("=" * 70, flush=True)
    print("INFORMATIVENESS WEIGHTING GATE — bucket-head sample weights, 5-fold", flush=True)
    print("=" * 70, flush=True)

    pos = compute_pos_in_group()
    df = _load_full_df()
    print(f"Loaded {len(df):,} rows", flush=True)

    fold_results: List[Dict[str, Any]] = []
    for i, fold in enumerate(FOLDS):
        print(f"\n{'─'*60}\nFOLD {i+1}/{len(FOLDS)} (test={fold['label']}+)\n{'─'*60}", flush=True)
        train, val, test = _slice_fold(df, fold)
        if len(test) == 0:
            fold_results.append({"fold_label": fold["label"], "skipped": True})
            continue

        print("  Training BASELINE...", flush=True)
        bucket_b, cont_b, _ = _train_bucket_and_contender(train, val, fold["label"])
        res = {"baseline": eval_subsets(test, bucket_b, cont_b)}

        for arm in ARMS:
            w = weights_for(train, pos, arm["k_full"], arm["floor"])
            print(
                f"  Training {arm['name']} (K={arm['k_full']}, floor={arm['floor']}; "
                f"mean w={w.mean():.3f}, downweighted={np.mean(w < 1.0):.1%})...",
                flush=True,
            )
            bucket_w, cont_w = train_weighted(train, val, fold["label"], w)
            res[arm["name"]] = eval_subsets(test, bucket_w, cont_w)

        wb = res["baseline"]["all"]["metrics"]["race_winner_capture_rate"]
        line = f"  winner: base={wb:.4f}"
        for arm in ARMS:
            wa = res[arm["name"]]["all"]["metrics"]["race_winner_capture_rate"]
            line += f"  {arm['name']}={wa:.4f} (Δ{wa-wb:+.4f})"
        print(line, flush=True)

        fold_results.append({"fold_label": fold["label"], "skipped": False, **res})

    usable = [fr for fr in fold_results if not fr.get("skipped")]
    agg: Dict[str, Any] = {}
    for arm in [a["name"] for a in ARMS]:
        agg[arm] = {}
        for subset in ("all", "one_day", "stage"):
            agg[arm][subset] = {}
            for k in PRIMARY_METRICS:
                deltas = []
                for fr in usable:
                    b = fr["baseline"].get(subset, {}).get("metrics", {}).get(k)
                    s = fr[arm].get(subset, {}).get("metrics", {}).get(k)
                    if b is not None and s is not None and not (np.isnan(b) or np.isnan(s)):
                        deltas.append(s - b)
                if deltas:
                    agg[arm][subset][k] = {
                        "mean": float(np.mean(deltas)),
                        "std": float(np.std(deltas)),
                        "per_fold": [float(d) for d in deltas],
                    }

    print("\nPAIRED DELTAS vs baseline:", flush=True)
    for arm in [a["name"] for a in ARMS]:
        for subset in ("all", "one_day", "stage"):
            d = agg[arm][subset].get("race_winner_capture_rate")
            ll = agg[arm][subset].get("top4_log_loss", {})
            if d:
                print(
                    f"  {arm} {subset:<8s} winner {d['mean']:+.4f}±{d['std']:.4f}  "
                    f"logloss {ll.get('mean', float('nan')):+.4f}",
                    flush=True,
                )

    ended = datetime.now()
    out = {
        "started_at": started.isoformat(),
        "ended_at": ended.isoformat(),
        "duration_seconds": (ended - started).total_seconds(),
        "config": {"folds": FOLDS, "start_date": START_DATE, "arms": ARMS,
                   "group_threshold_s": GROUP_THRESHOLD_S,
                   "scope": "bucket predictor only; class weights retained; val unweighted"},
        "fold_results": fold_results,
        "aggregated_deltas": agg,
    }
    ts = ended.strftime("%Y%m%d_%H%M%S")
    path = OUT_DIR / f"informativeness_weighting_cv_{ts}.json"
    path.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nSaved {path}  ({(ended-started).total_seconds()/60:.1f} min)", flush=True)


if __name__ == "__main__":
    main()
