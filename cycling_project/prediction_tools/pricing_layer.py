"""
Pricing layer — arm-C post-processing applied to every displayed prediction.

Shared by the web app and headless callers (smoke tests) so serving has one
code path. Three steps, each degrading gracefully when its artifact is
absent:

1. Win-market calibration corrector (win_calibration.json): applied to
   CONTENDER rows' prob_win (the corrector was fit on the contender pool);
   odds_win recomputed from corrected values.
2. Blend win market: w x multiclass + (1-w) x LambdaRank win probability,
   renormalized over the field to preserve the multiclass book (the gated
   w=0.2 overlay).
3. DNF-adjusted (honest) prices: P(market | finish) x P(finish) from the
   production DNF head. Podium / top5 / top15 multiply directly (adjusted
   <= unadjusted); the win market is renormalized within the race to
   preserve the total win book — the gated adjust_markets semantics.
"""

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from cycling_project.prediction_tools.dnf_predictor import build_serving_dnf_frame
from cycling_project.prediction_tools.win_calibration import apply_corrector
from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

BLEND_W = 0.2
MAX_ODDS = 999.0

ADJ_MARKETS = ("win", "podium", "top5", "top15")


def apply_pricing_layer(
    result_df: pd.DataFrame,
    pred_df: pd.DataFrame,
    profile: Dict[str, Any],
    win_corrector: Optional[Dict[str, Any]] = None,
    dnf_bundle: Optional[Tuple] = None,
    stage_number: Optional[int] = None,
    db_path: Optional[str] = None,
    asof_date: Optional[str] = None,
    blend_w: float = BLEND_W,
) -> Tuple[pd.DataFrame, List[str]]:
    """Apply corrector + blend + DNF adjustment to a predict_race result.

    Args:
        result_df: RaceRankingPredictor.predict_race(return_details=True)
            output (mutated copy returned).
        pred_df: the assembled prediction frame the result came from (the
            DNF head featurizes from it).
        profile: the race profile used for pred_df (competition_type /
            race_category drive the DNF context flags).
        win_corrector: persisted corrector dict (win_calibration.load_corrector).
        dnf_bundle: (DNFPredictor, events_df, metadata) from
            dnf_predictor.load_production_dnf_head, or None.
        stage_number: target stage number when predicting a stage, else None.
        asof_date: cutoff for DNF history features; defaults to today.

    Returns:
        (result_df, warnings) — warnings are user-facing degradation notes.
    """
    out = result_df.copy()
    warnings: List[str] = []

    # ---- 1. win-market calibration corrector (contender rows only) ----
    if (win_corrector and win_corrector.get("method") != "identity"
            and "prob_win" in out.columns):
        if "is_contender" in out.columns:
            mask = out["is_contender"].fillna(False).astype(bool)
        else:
            mask = pd.Series(True, index=out.index)
        corrected = apply_corrector(
            out.loc[mask, "prob_win"].to_numpy(dtype=float), win_corrector
        )
        out.loc[mask, "prob_win"] = corrected
        if "odds_win" in out.columns:
            p = out["prob_win"].to_numpy(dtype=float)
            with np.errstate(divide="ignore", invalid="ignore"):
                odds = np.where(p > 0, 1.0 / p, MAX_ODDS)
            out["odds_win"] = np.minimum(np.round(odds, 2), MAX_ODDS)

    # ---- 2. blend win market (book-preserving) ----
    # LambdaRank win probabilities: prefer the column the app merges onto the
    # result; fall back to the stack feature already attached to pred_df
    # (attach_stack_features) — identical values by construction.
    if ("lambdarank_win_p" not in out.columns
            or not out["lambdarank_win_p"].notna().any()):
        if (pred_df is not None and "oof_lambdarank_win_p" in pred_df.columns
                and pred_df["oof_lambdarank_win_p"].notna().any()):
            lr_map = dict(zip(pred_df["rider_id"].astype(int),
                              pred_df["oof_lambdarank_win_p"].astype(float)))
            out["lambdarank_win_p"] = out["rider_id"].astype(int).map(lr_map)
    if ("prob_win" in out.columns and "lambdarank_win_p" in out.columns
            and out["lambdarank_win_p"].notna().any()):
        mc = out["prob_win"].astype(float)
        lr = out["lambdarank_win_p"].astype(float)
        bl = blend_w * mc + (1 - blend_w) * lr
        s = bl.sum()
        if s > 0:
            bl = bl / s * mc.sum()
        out["blend_win_p"] = bl
    else:
        out["blend_win_p"] = np.nan
        if "prob_win" in out.columns:
            warnings.append("LambdaRank head absent — blend win market unavailable")

    # ---- 3. DNF-adjusted (honest) prices ----
    out["dnf_p"] = np.nan
    for m in ADJ_MARKETS:
        out[f"dnf_adj_{m}_p"] = np.nan
    if dnf_bundle is None:
        warnings.append("DNF head absent — honest (DNF-adjusted) prices unavailable")
        return out, warnings

    try:
        head, dnf_events, _meta = dnf_bundle
        dnf_frame = build_serving_dnf_frame(
            pred_df, dnf_events,
            competition_type=profile.get("competition_type", "one_day"),
            race_category=profile.get("race_category", "wt"),
            stage_number=stage_number,
            db_path=db_path,
            asof_date=asof_date,
        )
        p_dnf = head.predict_dnf_proba(dnf_frame)
        dnf_map = dict(zip(dnf_frame["rider_id"].astype(int), p_dnf))
        out["dnf_p"] = out["rider_id"].map(dnf_map)
        p_finish = 1.0 - out["dnf_p"].astype(float)
        for m in ADJ_MARKETS:
            col = f"prob_{m}"
            if col in out.columns:
                out[f"dnf_adj_{m}_p"] = out[col].astype(float) * p_finish
        # Win book preserved within the race (gated adjust_markets semantics)
        adj = out["dnf_adj_win_p"].astype(float)
        if adj.sum() > 0 and "prob_win" in out.columns:
            out["dnf_adj_win_p"] = (
                adj * out["prob_win"].astype(float).sum() / adj.sum()
            )
    except Exception as exc:  # pragma: no cover — defensive serving path
        logger.warning("DNF pricing failed: %s", exc)
        warnings.append(f"DNF pricing unavailable: {exc}")

    return out, warnings
