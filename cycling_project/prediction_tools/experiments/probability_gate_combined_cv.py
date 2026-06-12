"""
Combined probability-gate run — baseline vs (meta-OOF + one-day signatures),
evaluated under MarketProbabilityEvaluator (gate policy 2026-06-11).

Collects the shelved probability-quality candidates into one stack:
  - meta-OOF features: oof_time_gap_pred, oof_lambdarank_win_p (stacked
    meta-learner harness; base models trained on plain frames)
  - signature features: 11 contest-signature cols, ONE-DAY rows only
    (B4 continuous, as-of-then; stage rows NaN — ref-keyed stage serving
    was shown to cost +0.078 log loss, so stages stay out)
  - blend overlay: win-market blend p = w*mc + (1-w)*lr_win_p (w=0.2),
    renormalized per race, reported as win_log_loss overlay on both arms.

Gate metrics: per-market binary log loss / Brier / cal ratio over ALL priced
riders (win/podium/top5/top15) + market_avg_log_loss headline. Winner/podium
capture retained as diagnostics.

Usage:
    PYTHONUNBUFFERED=1 uv run python -m cycling_project.prediction_tools.experiments.probability_gate_combined_cv
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from cycling_project.prediction_tools.evaluation import (
    MarketProbabilityEvaluator,
    Top4ProbabilityEvaluator,
)
from cycling_project.prediction_tools.experiments.contest_signature_gate_cv import (
    ARCH,
    attach,
    load_signature_table,
    oneday_b4,
)
from cycling_project.prediction_tools.experiments.stacked_meta_learner_cv_5fold import (
    FOLDS,
    START_DATE,
    _generate_oof_lambdarank_winp,
    _generate_oof_time_gap,
    _load_full_df,
    _slice_fold,
    _train_bucket_and_contender,
    _train_main_lambdarank,
    _train_main_time_gap,
)
from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

OUT_DIR = Path("experiments")
BLEND_W = 0.2
GATE_METRICS = [
    "market_avg_log_loss", "win_log_loss", "podium_log_loss",
    "top5_log_loss", "top15_log_loss", "market_avg_brier",
    "win_cal_ratio", "top15_cal_ratio",
    "race_winner_capture_rate", "race_podium_capture_rate",
]


def eval_arm(test_df: pd.DataFrame, bucket, cont, lr_model=None) -> Dict[str, Any]:
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
        t4 = Top4ProbabilityEvaluator.evaluate(y, proba, competition_ids=cd["competition_id"].values)
        for k in ("race_winner_capture_rate", "race_podium_capture_rate"):
            if k in t4:
                m[k] = t4[k]

        if lr_model is not None and name == "all":
            lr_p = np.asarray(lr_model.predict_win_probabilities(cd))
            mc_p = proba[:, 0]
            bl = BLEND_W * mc_p + (1 - BLEND_W) * lr_p
            bl = pd.Series(bl, index=cd.index)
            bl = bl / bl.groupby(cd["competition_id"]).transform("sum") * \
                pd.Series(mc_p, index=cd.index).groupby(cd["competition_id"]).transform("sum")
            p = np.clip(bl.to_numpy(), 1e-12, 1 - 1e-12)
            yw = (y == 0).astype(float)
            m["blend_win_log_loss"] = float(-np.mean(yw * np.log(p) + (1 - yw) * np.log(1 - p)))
        out[name] = m
    return out


def main():
    started = datetime.now()
    print("=" * 70, flush=True)
    print("COMBINED PROBABILITY GATE — baseline vs meta-OOF + one-day signatures", flush=True)
    print("=" * 70, flush=True)

    sig = load_signature_table()
    od_feats = oneday_b4(sig)
    field_shares = sig[["comp_id"] + [f"field_share_{a}" for a in ARCH]].copy()
    df = _load_full_df()
    print(f"Loaded {len(df):,} rows", flush=True)

    fold_results: List[Dict[str, Any]] = []
    for i, fold in enumerate(FOLDS):
        print(f"\n{'─'*60}\nFOLD {i+1}/{len(FOLDS)} (test={fold['label']}+)\n{'─'*60}", flush=True)
        train, val, test = _slice_fold(df, fold)
        if len(test) == 0:
            fold_results.append({"fold_label": fold["label"], "skipped": True})
            continue

        print("  OOF time_gap...", flush=True)
        oof_tg = _generate_oof_time_gap(train, val)
        print("  OOF LambdaRank...", flush=True)
        oof_lr = _generate_oof_lambdarank_winp(train, val)
        print("  Main base models...", flush=True)
        main_tg = _train_main_time_gap(train, val)
        main_lr = _train_main_lambdarank(train, val)

        train_c = attach(train, od_feats, field_shares)
        val_c = attach(val, od_feats, field_shares)
        test_c = attach(test, od_feats, field_shares)
        train_c["oof_time_gap_pred"] = oof_tg
        train_c["oof_lambdarank_win_p"] = oof_lr
        val_c["oof_time_gap_pred"] = main_tg.predict(val_c)
        val_c["oof_lambdarank_win_p"] = np.asarray(main_lr.predict_win_probabilities(val_c))
        test_c["oof_time_gap_pred"] = main_tg.predict(test_c)
        test_c["oof_lambdarank_win_p"] = np.asarray(main_lr.predict_win_probabilities(test_c))

        print("  Training BASELINE...", flush=True)
        bucket_b, cont_b, _ = _train_bucket_and_contender(train, val, fold["label"])
        res_b = eval_arm(test, bucket_b, cont_b, lr_model=main_lr)

        print("  Training COMBINED...", flush=True)
        bucket_c, cont_c, _ = _train_bucket_and_contender(train_c, val_c, fold["label"])
        res_c = eval_arm(test_c, bucket_c, cont_c, lr_model=main_lr)

        b, c = res_b["all"], res_c["all"]
        print(
            f"  mkt_avg_ll: base={b['market_avg_log_loss']:.4f} comb={c['market_avg_log_loss']:.4f} "
            f"(Δ{c['market_avg_log_loss']-b['market_avg_log_loss']:+.4f})  "
            f"win_ll Δ{c['win_log_loss']-b['win_log_loss']:+.4f}  "
            f"blend_win_ll: base={b.get('blend_win_log_loss', float('nan')):.4f} "
            f"comb={c.get('blend_win_log_loss', float('nan')):.4f}  "
            f"winner_cap Δ{c['race_winner_capture_rate']-b['race_winner_capture_rate']:+.4f}",
            flush=True,
        )
        fold_results.append(
            {"fold_label": fold["label"], "skipped": False, "baseline": res_b, "combined": res_c}
        )

    usable = [fr for fr in fold_results if not fr.get("skipped")]
    agg: Dict[str, Any] = {}
    for subset in ("all", "one_day", "stage"):
        agg[subset] = {}
        for k in GATE_METRICS + ["blend_win_log_loss"]:
            deltas = [
                fr["combined"][subset][k] - fr["baseline"][subset][k]
                for fr in usable
                if k in fr["combined"].get(subset, {}) and k in fr["baseline"].get(subset, {})
            ]
            if deltas:
                agg[subset][k] = {
                    "mean": float(np.mean(deltas)), "std": float(np.std(deltas)),
                    "per_fold": [float(x) for x in deltas],
                }

    print("\nPAIRED DELTAS combined - baseline:", flush=True)
    for subset in ("all", "one_day", "stage"):
        for k in ("market_avg_log_loss", "win_log_loss", "top15_log_loss", "race_winner_capture_rate"):
            d = agg[subset].get(k)
            if d:
                print(f"  {subset:<8s} {k:<26s} {d['mean']:+.4f}±{d['std']:.4f}", flush=True)

    ended = datetime.now()
    out = {
        "started_at": started.isoformat(), "ended_at": ended.isoformat(),
        "duration_seconds": (ended - started).total_seconds(),
        "config": {"folds": FOLDS, "start_date": START_DATE, "blend_w": BLEND_W,
                   "stack": "meta_oof + oneday_signatures; stage sig NaN"},
        "fold_results": fold_results,
        "aggregated_deltas": agg,
    }
    ts = ended.strftime("%Y%m%d_%H%M%S")
    path = OUT_DIR / f"probability_gate_combined_cv_{ts}.json"
    path.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nSaved {path}  ({(ended-started).total_seconds()/60:.1f} min)", flush=True)


if __name__ == "__main__":
    main()
