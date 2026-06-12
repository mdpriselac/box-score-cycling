"""
Forward race-character model (step 3 of the race-character program).

Predicts, for a one-day competition, using ONLY pre-race information:
  - the contesting-archetype profile (top-10 best_profile shares, 6 known dims)
  - the finish shape (winner-group proportion, wg_prop)

Inputs per target edition (strictly as-of-then):
  - history: per-dim mean of prior editions, last edition, prior count
  - startlist: field archetype shares (computed from as-of-then snapshots of
    the actual field), field size
  - metadata: category, month

Predictors compared (shares):
  B0 global train mean          (no info)
  B1 last edition               (single reference)
  B2 mean of prior editions     (multi-reference, the r=0.739 benchmark)
  B3 field share                (startlist only — "race selects randomly")
  B4 field share + mean prior enrichment  (course's selective pressure
                                 transferred onto this year's startlist)
  M1 LightGBM per dim           (all features)

For wg_prop: B0/B1/B2 + LightGBM. Cold-start rows (no prior editions) are
evaluated separately on the no-history predictors.

Evaluation: rolling-origin by year — for each test year Y >= 2019, train on
rows with year < Y, predict rows in year Y. Pooled metrics across test years.

Reads the latest selection_signatures CSV; no DB writes.

Usage:
    uv run python -m cycling_project.prediction_tools.experiments.forward_race_character
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import lightgbm as lgb
import numpy as np
import pandas as pd

from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

OUT_DIR = Path(__file__).parents[3] / "experiments"
SEED = 42
ARCH = ["sprint", "mountain", "hilly", "rolling", "breakaway", "time_trial"]
SHARE = [f"top10_{a}" for a in ARCH]
FIELD = [f"field_share_{a}" for a in ARCH]
ENRICH = [f"enrich_{a}" for a in ARCH]
TEST_YEARS = list(range(2019, 2027))

LGB_PARAMS = dict(
    objective="regression", n_estimators=250, learning_rate=0.05,
    num_leaves=15, min_child_samples=20, subsample=0.9, subsample_freq=1,
    colsample_bytree=0.8, random_state=SEED, verbose=-1,
)


def load_signatures() -> pd.DataFrame:
    f = sorted(OUT_DIR.glob("selection_signatures_*.csv.gz"))[-1]
    comp = pd.read_csv(f)
    logger.info("Loaded %s (%d comps)", f.name, len(comp))
    oneday = comp[comp["competition_type"] == "one_day"].copy()
    oneday["date"] = pd.to_datetime(oneday["date"])
    oneday["month"] = oneday["date"].dt.month
    # one edition per (race, year)
    oneday = oneday.sort_values("date").drop_duplicates(["fc_race_id", "year"], keep="first")
    return oneday


def build_dataset(oneday: pd.DataFrame) -> pd.DataFrame:
    """One row per edition with as-of-then prior aggregates."""
    rows = []
    hist_dims = SHARE + ENRICH + ["wg_prop"]
    for rid, g in oneday.groupby("fc_race_id"):
        g = g.sort_values("year").reset_index(drop=True)
        for i in range(len(g)):
            r = g.iloc[i]
            row = {
                "fc_race_id": rid, "race_name": r["race_name"], "year": int(r["year"]),
                "category": r["category"], "month": int(r["month"]),
                "field_size": float(r.get("field_size", np.nan)) if "field_size" in g.columns else np.nan,
                "n_priors": i,
            }
            for d in SHARE + ["wg_prop"]:
                row[f"y_{d}"] = float(r[d])
            for d in FIELD:
                row[d] = float(r[d])
            if i > 0:
                prior = g.iloc[:i]
                for d in hist_dims:
                    row[f"prior_mean_{d}"] = float(prior[d].mean())
                    row[f"last_{d}"] = float(prior[d].iloc[-1])
            else:
                for d in hist_dims:
                    row[f"prior_mean_{d}"] = np.nan
                    row[f"last_{d}"] = np.nan
            rows.append(row)
    ds = pd.DataFrame(rows)
    ds["cat_enc"] = ds["category"].map({"wt": 0, "pro": 1, "d1": 2}).fillna(2)
    logger.info("Dataset: %d edition rows (%d cold-start)", len(ds), (ds["n_priors"] == 0).sum())
    return ds


def metrics(y: np.ndarray, p: np.ndarray) -> Dict:
    ok = ~(np.isnan(y) | np.isnan(p))
    y, p = y[ok], p[ok]
    if len(y) < 10 or np.std(p) < 1e-12:
        return {"n": int(len(y)), "r": None, "mae": round(float(np.mean(np.abs(y - p))), 4) if len(y) else None}
    return {
        "n": int(len(y)),
        "r": round(float(np.corrcoef(y, p)[0, 1]), 3),
        "mae": round(float(np.mean(np.abs(y - p))), 4),
    }


def cosine_rows(Y: np.ndarray, P: np.ndarray) -> float:
    ok = ~(np.isnan(Y).any(axis=1) | np.isnan(P).any(axis=1))
    Y, P = Y[ok], P[ok]
    yn = Y / np.clip(np.linalg.norm(Y, axis=1, keepdims=True), 1e-9, None)
    pn = P / np.clip(np.linalg.norm(P, axis=1, keepdims=True), 1e-9, None)
    return round(float(np.mean(np.sum(yn * pn, axis=1))), 4)


def feature_cols() -> List[str]:
    cols = ["month", "cat_enc", "field_size", "n_priors"] + FIELD
    for d in SHARE + ENRICH + ["wg_prop"]:
        cols += [f"prior_mean_{d}", f"last_{d}"]
    return cols


def evaluate(ds: pd.DataFrame) -> Dict:
    fc = feature_cols()
    preds = {name: {d: np.full(len(ds), np.nan) for d in SHARE + ["wg_prop"]}
             for name in ["B0", "B1", "B2", "B3", "B4", "M1"]}
    is_test = np.zeros(len(ds), dtype=bool)

    for ty in TEST_YEARS:
        tr = ds["year"] < ty
        te = ds["year"] == ty
        if te.sum() == 0 or tr.sum() < 50:
            continue
        is_test |= te.to_numpy()
        tr_idx, te_idx = np.where(tr)[0], np.where(te)[0]

        for d in SHARE:
            a = d.replace("top10_", "")
            preds["B0"][d][te_idx] = ds[f"y_{d}"].iloc[tr_idx].mean()
            preds["B1"][d][te_idx] = ds[f"last_{d}"].iloc[te_idx]
            preds["B2"][d][te_idx] = ds[f"prior_mean_{d}"].iloc[te_idx]
            preds["B3"][d][te_idx] = ds[f"field_share_{a}"].iloc[te_idx]
            preds["B4"][d][te_idx] = np.clip(
                ds[f"field_share_{a}"].iloc[te_idx].to_numpy()
                + ds[f"prior_mean_enrich_{a}"].iloc[te_idx].to_numpy(),
                0, 1,
            )
            m = lgb.LGBMRegressor(**LGB_PARAMS)
            m.fit(ds.iloc[tr_idx][fc], ds[f"y_{d}"].iloc[tr_idx])
            preds["M1"][d][te_idx] = m.predict(ds.iloc[te_idx][fc])

        d = "wg_prop"
        preds["B0"][d][te_idx] = ds[f"y_{d}"].iloc[tr_idx].mean()
        preds["B1"][d][te_idx] = ds[f"last_{d}"].iloc[te_idx]
        preds["B2"][d][te_idx] = ds[f"prior_mean_{d}"].iloc[te_idx]
        m = lgb.LGBMRegressor(**LGB_PARAMS)
        m.fit(ds.iloc[tr_idx][fc], ds[f"y_{d}"].iloc[tr_idx])
        preds["M1"][d][te_idx] = m.predict(ds.iloc[te_idx][fc])

    out = {"n_test_rows": int(is_test.sum())}
    has_hist = (ds["n_priors"] >= 1).to_numpy() & is_test
    cold = (ds["n_priors"] == 0).to_numpy() & is_test

    for scope, mask in [("with_history", has_hist), ("cold_start", cold)]:
        scope_out = {}
        for name in ["B0", "B1", "B2", "B3", "B4", "M1"]:
            if scope == "cold_start" and name in ("B1", "B2", "B4"):
                continue
            per_dim = {}
            for d in SHARE + ["wg_prop"]:
                if name in ("B3", "B4") and d == "wg_prop":
                    continue
                per_dim[d] = metrics(ds[f"y_{d}"].to_numpy()[mask], preds[name][d][mask])
            Y = np.column_stack([ds[f"y_{d}"].to_numpy()[mask] for d in SHARE])
            P = np.column_stack([preds[name][d][mask] for d in SHARE])
            scope_out[name] = {
                "per_dim": per_dim,
                "signature_cosine": cosine_rows(Y, P),
                "mean_share_r": round(
                    float(np.nanmean([per_dim[d]["r"] for d in SHARE if per_dim[d]["r"] is not None])), 3
                ),
            }
        out[scope] = {"n_rows": int(mask.sum()), "predictors": scope_out}
    return out


def main():
    ds = build_dataset(load_signatures())
    results = evaluate(ds)
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "n_edition_rows": len(ds),
        "test_years": TEST_YEARS,
        "results": results,
    }
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    (OUT_DIR / f"forward_race_character_{ts}.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps(summary, indent=2, default=str))
    logger.info("Wrote forward_race_character_%s.json", ts)


if __name__ == "__main__":
    main()
