"""
Parity validation — retrained arm-C production stack vs previous production.

Compares the freshly trained models/production (arm-C: bucket + contender on
meta-OOF + one-day signatures + contested-Elo) against the backed-up
previous production models (plain frame) on a 2025+ holdout slice, under
the probability gate's MarketProbabilityEvaluator (top-15 contender pool).

Expectation from the gate (full_stack_integration_cv 2026-06-11):
C-A market_avg_log_loss ~ -0.004 (all), winner capture ~ +1.2pp.

Caveat encoded in the output: production models train through ~today with
only the last 5% of competitions held out for early stopping, so most 2025
rows are IN-SAMPLE for both models. The paired old-vs-new difference still
isolates the stack (both models saw the same rows), but absolute levels are
optimistic. The post_cutoff subset (rows after BOTH registries' early-stop
cutoffs) is the clean out-of-train comparison.

Usage:
    PYTHONUNBUFFERED=1 uv run python -m cycling_project.prediction_tools.experiments.parity_validation_arm_c \
        [--old-dir models/production_backup_2026-06-11]
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from cycling_project.prediction_tools.contest_signature_features import (
    attach_signature_features,
    build_oneday_signature_features,
)
from cycling_project.prediction_tools.contested_rating import (
    PRODUCTION_SNAPSHOT_PATH,
    attach_rating_features,
    load_snapshots,
)
from cycling_project.prediction_tools.data_pipeline import CyclingDataPipeline, DataConfig
from cycling_project.prediction_tools.evaluation import (
    MarketProbabilityEvaluator,
    Top4ProbabilityEvaluator,
)
from cycling_project.prediction_tools.model_registry import ModelRegistry
from cycling_project.prediction_tools.win_calibration import apply_corrector, load_corrector
from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).parents[3]
DB_PATH = (
    Path(__file__).parents[2]
    / "webscrape_tools" / "database" / "database" / "cycling_races.db"
)
OUT_DIR = PROJECT_ROOT / "experiments"
TOP_N = 15
EVAL_START = "2025-01-01"
SUBSETS = ("all", "one_day", "stage")


def eval_stack(df: pd.DataFrame, bucket, cont, label: str,
               win_corrector: Optional[dict] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for name in SUBSETS:
        sub = df if name == "all" else df[df["competition_type"] == name]
        if len(sub) == 0:
            continue
        d = sub.copy()
        d["classifier_expected_bucket"] = bucket.predict_continuous(d)
        d["_rank"] = d.groupby("competition_id")["classifier_expected_bucket"].rank()
        cd = d[d["_rank"] <= TOP_N].drop(columns=["_rank"])
        proba = cont.predict_proba(cd)
        n_classes = cont.config.lgb_params.get("num_class", 8)
        y = cd["place_bucket"].values
        if n_classes < 8:
            y = np.clip(y, 0, n_classes - 1)
        m = MarketProbabilityEvaluator.evaluate(y, proba)
        t4 = Top4ProbabilityEvaluator.evaluate(
            y, proba, competition_ids=cd["competition_id"].values
        )
        for k in ("race_winner_capture_rate", "race_podium_capture_rate"):
            if k in t4:
                m[k] = t4[k]
        if win_corrector is not None:
            q = apply_corrector(proba[:, 0], win_corrector)
            yw = (y == 0).astype(float)
            qc = np.clip(q, 1e-12, 1 - 1e-12)
            m["corrected_win_log_loss"] = float(
                -np.mean(yw * np.log(qc) + (1 - yw) * np.log(1 - qc))
            )
            m["corrected_win_cal_ratio"] = float(qc.sum() / max(yw.sum(), 1.0))
        m["n_comps"] = int(cd["competition_id"].nunique())
        out[name] = m
        print(
            f"  [{label}] {name:<8s} mkt_avg_ll={m['market_avg_log_loss']:.4f}  "
            f"win_ll={m['win_log_loss']:.4f}  win_cal={m['win_cal_ratio']:.3f}  "
            f"wcap={m.get('race_winner_capture_rate', float('nan')):.4f}  "
            f"({m['n_evaluated']:,} rows / {m['n_comps']:,} comps)",
            flush=True,
        )
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--old-dir", type=Path,
        default=PROJECT_ROOT / "models" / "production_backup_2026-06-11",
    )
    parser.add_argument(
        "--new-dir", type=Path, default=PROJECT_ROOT / "models" / "production",
    )
    args = parser.parse_args()

    started = datetime.now()
    print("=" * 70, flush=True)
    print("PARITY VALIDATION — retrained arm-C stack vs previous production", flush=True)
    print("=" * 70, flush=True)

    old_reg = ModelRegistry(str(args.old_dir))
    new_reg = ModelRegistry(str(args.new_dir))
    old_meta = old_reg.get_metadata().get("training_info", {})
    new_meta = new_reg.get_metadata().get("training_info", {})
    old_cutoff = old_meta.get("early_stop_cutoff")
    new_cutoff = new_meta.get("early_stop_cutoff")
    print(f"old: {args.old_dir.name}  early_stop_cutoff={old_cutoff}", flush=True)
    print(f"new: {args.new_dir.name}  early_stop_cutoff={new_cutoff}  "
          f"stack={new_meta.get('stack_enabled')}", flush=True)

    bucket_old, _, _, _, cont_old, _ = old_reg.load()
    bucket_new, tg_new, _, _, cont_new, lr_new = new_reg.load()
    assert lr_new is not None, "new registry is missing the LambdaRank head"
    win_corrector = load_corrector(args.new_dir)

    # ---- production frame, 2025+ slice ----
    cfg = DataConfig(
        db_path=str(DB_PATH),
        start_date=EVAL_START,
        min_races_career=10,
        include_gradient_features=True,
        include_race_state=True,
    )
    df = CyclingDataPipeline(cfg).load_training_data()
    df["competition_date"] = pd.to_datetime(df["competition_date"])
    print(f"\nEval frame 2025+: {len(df):,} rows, "
          f"{df['competition_id'].nunique():,} comps", flush=True)

    # ---- arm-C features for the new stack (as-of-then everywhere) ----
    print("Attaching arm-C features (signatures + Elo + main-model meta)...", flush=True)
    od_feats, field_shares = build_oneday_signature_features(DB_PATH)
    df_aug = attach_signature_features(df, od_feats, field_shares)
    rating_snaps = load_snapshots(PRODUCTION_SNAPSHOT_PATH)
    df_aug = attach_rating_features(df_aug, rating_snaps, db_path=DB_PATH)
    df_aug["oof_time_gap_pred"] = tg_new.predict(df_aug)
    df_aug["oof_lambdarank_win_p"] = np.asarray(lr_new.predict_win_probabilities(df_aug))
    sig_cov_od = 1 - df_aug.loc[
        df_aug["competition_type"] == "one_day", "sig_sprint"
    ].isna().mean()
    print(f"  sig coverage (one-day rows): {sig_cov_od:.1%}  "
          f"Elo coverage: {df_aug['contested_rating'].notna().mean():.1%}", flush=True)

    results: Dict[str, Any] = {}
    slices = {"full_2025_plus": None}
    if old_cutoff and new_cutoff:
        clean_start = max(pd.to_datetime(old_cutoff), pd.to_datetime(new_cutoff))
        slices["post_cutoff"] = clean_start
    for slice_name, start in slices.items():
        if start is None:
            sl, sl_aug = df, df_aug
        else:
            mask = df["competition_date"] >= start
            sl, sl_aug = df[mask], df_aug[mask.values]
        print(f"\n--- slice {slice_name}: {len(sl):,} rows "
              f"({sl['competition_id'].nunique():,} comps)"
              + (f", from {start.date()}" if start is not None else "")
              + " ---", flush=True)
        if len(sl) == 0:
            continue
        print("OLD production (plain frame):", flush=True)
        res_old = eval_stack(sl, bucket_old, cont_old, "old")
        print("NEW production (arm-C frame):", flush=True)
        res_new = eval_stack(sl_aug, bucket_new, cont_new, "new", win_corrector)

        deltas: Dict[str, Any] = {}
        for subset in SUBSETS:
            if subset not in res_old or subset not in res_new:
                continue
            deltas[subset] = {
                k: res_new[subset][k] - res_old[subset][k]
                for k in ("market_avg_log_loss", "win_log_loss", "podium_log_loss",
                          "top5_log_loss", "top15_log_loss", "market_avg_brier",
                          "win_cal_ratio", "race_winner_capture_rate",
                          "race_podium_capture_rate")
                if k in res_old[subset] and k in res_new[subset]
            }
            d = deltas[subset]
            print(
                f"  Δ new-old {subset:<8s} mkt_avg_ll={d['market_avg_log_loss']:+.4f}  "
                f"win_ll={d['win_log_loss']:+.4f}  "
                f"wcap={d.get('race_winner_capture_rate', float('nan')):+.4f}",
                flush=True,
            )
        results[slice_name] = {"old": res_old, "new": res_new, "delta_new_minus_old": deltas}

    ended = datetime.now()
    out = {
        "started_at": started.isoformat(),
        "ended_at": ended.isoformat(),
        "old_dir": str(args.old_dir),
        "new_dir": str(args.new_dir),
        "old_early_stop_cutoff": old_cutoff,
        "new_early_stop_cutoff": new_cutoff,
        "gate_expectation": {
            "source": "experiments/full_stack_integration_cv_20260611_170401.json",
            "C_minus_A_market_avg_log_loss": -0.0040,
            "C_minus_A_winner_capture_pp": 1.2,
        },
        "win_corrector": win_corrector,
        "caveat": (
            "Production models train through ~today (95/5 early-stop split), so "
            "full_2025_plus is largely in-sample for BOTH models; the paired "
            "delta isolates the stack but absolute levels are optimistic. "
            "post_cutoff is out-of-train for both models."
        ),
        "results": results,
    }
    ts = ended.strftime("%Y%m%d_%H%M%S")
    path = OUT_DIR / f"parity_validation_arm_c_{ts}.json"
    path.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nSaved {path}  ({(ended - started).total_seconds() / 60:.1f} min)", flush=True)


if __name__ == "__main__":
    main()
