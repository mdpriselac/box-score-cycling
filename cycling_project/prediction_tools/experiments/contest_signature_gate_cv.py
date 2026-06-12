"""
Contest-signature feature gate — 5-fold CV, baseline vs augmented contender stack.

Adds 11 contest-signature features to the production contender stack and
measures paired per-fold deltas (winner / podium capture, log loss, Brier,
calibration), overall and per competition-type subset.

Feature construction (strictly as-of-then, per the leakage design):
  one_day comps : continuous B4 = clip(field_share + mean prior-edition
                  enrichment, 0, 1); sig_wg_prop = mean prior wg_prop;
                  cold start -> plain field share, wg_prop NaN. Leak-free.
  stage comps   : canonical contest-archetype profile. GMM(k=10) fit per fold
                  on train-years signatures only; HARD own-assignment; values
                  are train-member centroids (bounded race-level leak, same
                  class as existing profile scores).
  gc / uncovered: all sig features NaN (LightGBM native).

Rider interactions: rider_sig_share (predicted share of rider's archetype),
rider_contest_fit (rider profile-ability dot predicted shares),
rider_sig_vs_field (share minus field share for rider's archetype).

Test arms:
  baseline  - production feature set
  sig       - + signature features, stages keyed by OWN assignment (upper bound)
  sig_ref   - same trained models; test-stage features re-keyed from prior-year
              same-race stages (soft mixture) — serving lower bound.

Usage:
    PYTHONUNBUFFERED=1 uv run python -m cycling_project.prediction_tools.experiments.contest_signature_gate_cv
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
from sklearn.mixture import GaussianMixture

from cycling_project.prediction_tools.experiments.stacked_meta_learner_cv_5fold import (
    FOLDS,
    START_DATE,
    _capture_feature_importance,
    _evaluate_on_test,
    _load_full_df,
    _slice_fold,
    _train_bucket_and_contender,
)
from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

OUT_DIR = Path("experiments")
SEED = 42
K_ARCHETYPES = 10
ARCH = ["sprint", "mountain", "hilly", "rolling", "breakaway", "time_trial"]
SIG = [f"sig_{a}" for a in ARCH]
NEW_COLS = SIG + ["sig_wg_prop", "sig_n_refs", "rider_sig_share", "rider_contest_fit", "rider_sig_vs_field"]
ABILITY = {a: f"{a}_avg_bucket" for a in ARCH}
PRIMARY_METRICS = [
    "race_winner_capture_rate", "race_podium_capture_rate",
    "top4_log_loss", "top4_brier", "win_cal_ratio", "podium_cal_ratio",
]


def load_signature_table() -> pd.DataFrame:
    f = sorted(OUT_DIR.glob("selection_signatures_*.csv.gz"))[-1]
    sig = pd.read_csv(f)
    sig["date"] = pd.to_datetime(sig["date"])
    logger.info("Signature table: %s (%d comps)", f.name, len(sig))
    return sig


def oneday_b4(sig: pd.DataFrame) -> pd.DataFrame:
    """Fold-independent as-of-then B4 features for one_day comps."""
    rows = []
    od = sig[sig["competition_type"] == "one_day"]
    for rid, g in od.groupby("fc_race_id"):
        g = g.sort_values("year").reset_index(drop=True)
        for i in range(len(g)):
            r = g.iloc[i]
            prior = g.iloc[:i]
            row = {"comp_id": r["comp_id"], "sig_n_refs": float(i)}
            for a in ARCH:
                fs = float(r[f"field_share_{a}"])
                if i > 0:
                    row[f"sig_{a}"] = float(np.clip(fs + prior[f"enrich_{a}"].mean(), 0, 1))
                else:
                    row[f"sig_{a}"] = fs
            row["sig_wg_prop"] = float(prior["wg_prop"].mean()) if i > 0 else np.nan
            rows.append(row)
    return pd.DataFrame(rows)


def stage_features_for_fold(sig: pd.DataFrame, train_end: str) -> Dict[str, pd.DataFrame]:
    """Own-keyed canonical features for ALL stage comps + ref-keyed variant."""
    shares = [f"top10_{a}" for a in ARCH]
    train_mask = sig["date"] <= pd.to_datetime(train_end)
    gm = GaussianMixture(n_components=K_ARCHETYPES, covariance_type="diag",
                         random_state=SEED, n_init=5)
    gm.fit(sig.loc[train_mask, shares])
    assign = pd.Series(gm.predict(sig[shares]), index=sig.index)

    members = sig[train_mask].copy()
    members["k"] = assign[train_mask]
    centroids = members.groupby("k")[shares].mean()
    cluster_wg = members.groupby("k")["wg_prop"].mean()

    st = sig[sig["competition_type"] == "stage"]
    own = pd.DataFrame({"comp_id": st["comp_id"].to_numpy()})
    ks = assign[st.index].to_numpy()
    for a in ARCH:
        own[f"sig_{a}"] = centroids[f"top10_{a}"].reindex(ks).to_numpy()
    own["sig_wg_prop"] = cluster_wg.reindex(ks).to_numpy()
    own["sig_n_refs"] = np.nan

    # ref-keyed: soft mixture of centroid profiles of same-race prior-year stages
    st_idx = st.reset_index()[["index", "comp_id", "fc_race_id", "year"]]
    ref_rows = []
    by_race: Dict[Any, pd.DataFrame] = {
        rid: g.sort_values("year") for rid, g in st_idx.groupby("fc_race_id")
    }
    for rid, g in by_race.items():
        for _, r in g.iterrows():
            prior = g[g["year"] < r["year"]]
            row = {"comp_id": r["comp_id"]}
            if len(prior):
                pk = assign[prior["index"]].to_numpy()
                prof = centroids.reindex(pk).mean()
                for a in ARCH:
                    row[f"sig_{a}"] = float(prof[f"top10_{a}"])
                row["sig_wg_prop"] = float(cluster_wg.reindex(pk).mean())
                row["sig_n_refs"] = float(len(prior))
            else:
                for a in ARCH:
                    row[f"sig_{a}"] = np.nan
                row["sig_wg_prop"] = np.nan
                row["sig_n_refs"] = 0.0
            ref_rows.append(row)
    return {"own": own, "ref": pd.DataFrame(ref_rows)}


def attach(df: pd.DataFrame, comp_feats: pd.DataFrame, field_shares: pd.DataFrame) -> pd.DataFrame:
    """Join comp-level sig features and compute rider interactions."""
    out = df.merge(comp_feats, left_on="competition_id", right_on="comp_id", how="left")
    out = out.merge(field_shares, left_on="competition_id", right_on="comp_id",
                    how="left", suffixes=("", "_fs"))
    out.drop(columns=[c for c in ("comp_id", "comp_id_fs") if c in out], inplace=True)

    bp = out["best_profile"].map({a: i for i, a in enumerate(ARCH)})
    has_bp = bp.notna().to_numpy()
    bp_idx = bp.fillna(0).astype(int).to_numpy()

    sig_mat = out[SIG].to_numpy()
    fs_mat = out[[f"field_share_{a}" for a in ARCH]].to_numpy()
    rows = np.arange(len(out))
    out["rider_sig_share"] = np.where(has_bp, sig_mat[rows, bp_idx], np.nan)
    out["rider_sig_vs_field"] = np.where(
        has_bp, sig_mat[rows, bp_idx] - fs_mat[rows, bp_idx], np.nan
    )
    ability = np.column_stack([(4.0 - out[ABILITY[a]].to_numpy(dtype=float)) for a in ARCH])
    out["rider_contest_fit"] = np.einsum("ij,ij->i", np.nan_to_num(sig_mat), ability)
    out.loc[np.isnan(sig_mat).all(axis=1), "rider_contest_fit"] = np.nan
    out.drop(columns=[f"field_share_{a}" for a in ARCH], inplace=True)
    return out


def eval_subsets(test_df: pd.DataFrame, bucket, cont) -> Dict[str, Any]:
    out = {}
    subsets = {
        "all": test_df,
        "one_day": test_df[test_df["competition_type"] == "one_day"],
        "stage": test_df[test_df["competition_type"] == "stage"],
    }
    for name, sub in subsets.items():
        if len(sub) == 0:
            continue
        m, n = _evaluate_on_test(sub, bucket, cont, top_n=15)
        out[name] = {"metrics": m, "n_rows": int(len(sub)), "n_contenders": n}
    return out


def main():
    started = datetime.now()
    print("=" * 70, flush=True)
    print("CONTEST-SIGNATURE GATE — 5-fold, baseline vs +11 sig features", flush=True)
    print("=" * 70, flush=True)

    sig = load_signature_table()
    field_shares = sig[["comp_id"] + [f"field_share_{a}" for a in ARCH]].copy()
    od_feats = oneday_b4(sig)
    df = _load_full_df()
    print(f"Loaded {len(df):,} rows, {df['competition_id'].nunique():,} comps", flush=True)
    missing_ability = [c for c in ABILITY.values() if c not in df.columns]
    assert not missing_ability, f"ability cols missing: {missing_ability}"

    fold_results: List[Dict[str, Any]] = []
    for i, fold in enumerate(FOLDS):
        print(f"\n{'─'*60}\nFOLD {i+1}/{len(FOLDS)} (test={fold['label']}+)\n{'─'*60}", flush=True)
        train, val, test = _slice_fold(df, fold)
        if len(test) == 0:
            fold_results.append({"fold_label": fold["label"], "skipped": True})
            continue

        stage_feats = stage_features_for_fold(sig, fold["train_end"])
        comp_own = pd.concat([od_feats, stage_feats["own"]], ignore_index=True)
        comp_ref = pd.concat([od_feats, stage_feats["ref"]], ignore_index=True)

        train_a = attach(train, comp_own, field_shares)
        val_a = attach(val, comp_own, field_shares)
        test_a = attach(test, comp_own, field_shares)
        test_r = attach(test, comp_ref, field_shares)
        cov = 1 - test_a["sig_sprint"].isna().mean()
        print(f"  sig coverage on test rows: {cov:.1%}", flush=True)

        print("  Training BASELINE...", flush=True)
        bucket_b, cont_b, _ = _train_bucket_and_contender(train, val, fold["label"])
        res_b = eval_subsets(test, bucket_b, cont_b)

        print("  Training SIG-AUGMENTED...", flush=True)
        bucket_s, cont_s, _ = _train_bucket_and_contender(train_a, val_a, fold["label"])
        res_s = eval_subsets(test_a, bucket_s, cont_s)
        res_r = eval_subsets(test_r, bucket_s, cont_s)
        fi = _capture_feature_importance(cont_s)

        w_b = res_b["all"]["metrics"].get("race_winner_capture_rate", np.nan)
        w_s = res_s["all"]["metrics"].get("race_winner_capture_rate", np.nan)
        w_r = res_r["all"]["metrics"].get("race_winner_capture_rate", np.nan)
        print(f"  winner: base={w_b:.4f}  sig={w_s:.4f} (Δ{w_s-w_b:+.4f})  "
              f"sig_ref={w_r:.4f} (Δ{w_r-w_b:+.4f})", flush=True)

        fold_results.append({
            "fold_label": fold["label"], "skipped": False,
            "sig_coverage_test": round(float(cov), 4),
            "baseline": res_b, "sig": res_s, "sig_ref": res_r,
            "sig_feature_importance": {
                c: float(fi.get(c, 0.0)) for c in NEW_COLS
            } if fi else {},
            "n_features_total": len(fi) if fi else None,
        })

    # aggregate paired deltas per arm x subset x metric
    usable = [fr for fr in fold_results if not fr.get("skipped")]
    agg: Dict[str, Any] = {}
    for arm in ("sig", "sig_ref"):
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
                        "mean": float(np.mean(deltas)), "std": float(np.std(deltas)),
                        "per_fold": [float(d) for d in deltas],
                    }

    print("\n" + "=" * 88, flush=True)
    print("PAIRED DELTAS vs baseline (mean ± std across folds)", flush=True)
    for arm in ("sig", "sig_ref"):
        for subset in ("all", "one_day", "stage"):
            d = agg[arm][subset]
            if "race_winner_capture_rate" not in d:
                continue
            w, p, ll = (d.get(k, {}) for k in
                        ("race_winner_capture_rate", "race_podium_capture_rate", "top4_log_loss"))
            print(f"  {arm:<8s} {subset:<8s} winner {w.get('mean', np.nan):+.4f}±{w.get('std', np.nan):.4f}  "
                  f"podium {p.get('mean', np.nan):+.4f}±{p.get('std', np.nan):.4f}  "
                  f"logloss {ll.get('mean', np.nan):+.4f}±{ll.get('std', np.nan):.4f}", flush=True)

    ended = datetime.now()
    out = {
        "started_at": started.isoformat(), "ended_at": ended.isoformat(),
        "duration_seconds": (ended - started).total_seconds(),
        "config": {"folds": FOLDS, "start_date": START_DATE, "k_archetypes": K_ARCHETYPES,
                   "new_cols": NEW_COLS},
        "fold_results": fold_results,
        "aggregated_deltas": agg,
    }
    ts = ended.strftime("%Y%m%d_%H%M%S")
    path = OUT_DIR / f"contest_signature_gate_cv_{ts}.json"
    path.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nSaved {path}  ({(ended-started).total_seconds()/60:.1f} min)", flush=True)


if __name__ == "__main__":
    main()
