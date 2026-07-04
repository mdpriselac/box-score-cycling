"""
Step-0 backtest: does the stack systematically underprice riders who recently
finished a grand tour? (GT-coasting form-dilution hypothesis, 2026-07-03)

Reuses the per-row prediction records from the 2026-06-10 age-bias backtest
(5 folds, 2016 start, production-config heads, test years 2021-2025 pooled)
and slices LambdaRank win calibration by grand-tour recency.

Cal ratio = sum(predicted win p) / sum(actual wins).
  > 1  -> model OVERprices the group
  < 1  -> model UNDERprices the group   (hypothesis: <1 for recent-GT riders)

Refactored 2026-07-03 into importable functions so the GT-aware form-feature
sweep can produce the same calibration tables on each candidate config's
fold records (`attach_gt_recency` + `gt_band_tables`). `main()` preserves the
original step-0 script behavior.
"""

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

PROJ = Path(__file__).resolve().parents[3]
DB = PROJ / "cycling_project/webscrape_tools/database/database/cycling_races.db"
REC = PROJ / "experiments/age_bias_backtest_records_20260610_081757.csv.gz"
OUT = PROJ / "experiments/gt_recency_backtest_20260703.json"

GT_FC_IDS = ("13", "17", "23")  # Giro, TdF, Vuelta
MIN_GT_STAGE_ROWS = 10          # "full GT load" = rode deep into it

BANDS = ["GT ended <=45d ago", "GT 46-90d ago", "GT 91-365d ago", "no GT last 12mo"]


def load_gt_participations(db_path: Path = DB) -> pd.DataFrame:
    """Rider x GT edition participations with >= MIN_GT_STAGE_ROWS stage rows."""
    conn = sqlite3.connect(str(db_path))
    try:
        gt = pd.read_sql_query(
            f"""SELECT rr.rider_id, r.fc_race_id, r.year AS gt_year,
                       MAX(c.date) AS gt_end,
                       SUM(CASE WHEN c.competition_type='stage' THEN 1 ELSE 0 END) AS gt_stage_rows,
                       MAX(CASE WHEN c.competition_type='gc' THEN 1 ELSE 0 END) AS finished_gc
                FROM rider_results rr
                JOIN competitions c ON rr.competition_id = c.id
                JOIN races r ON c.race_id = r.id
                WHERE r.fc_race_id IN {GT_FC_IDS}
                GROUP BY rr.rider_id, r.id""",
            conn,
        )
    finally:
        conn.close()
    gt["gt_end"] = pd.to_datetime(gt["gt_end"])
    return gt[gt["gt_stage_rows"] >= MIN_GT_STAGE_ROWS]


def _band(d) -> str:
    if pd.isna(d):
        return "no GT last 12mo"
    if d <= 45:
        return "GT ended <=45d ago"
    if d <= 90:
        return "GT 46-90d ago"
    if d <= 365:
        return "GT 91-365d ago"
    return "no GT last 12mo"


def attach_gt_recency(
    rec: pd.DataFrame,
    db_path: Path = DB,
    gt: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Attach days_since_gt / gt_band / is_win / is_podium to backtest records.

    rec needs: rider_id, competition_id, place_bucket. For each row: days since
    the rider's most recent GT that ENDED strictly before the row's competition
    (same race edition excluded).
    """
    if gt is None:
        gt = load_gt_participations(db_path)

    conn = sqlite3.connect(str(db_path))
    try:
        comp_meta = pd.read_sql_query(
            """SELECT c.id AS competition_id, c.date AS comp_date, r.fc_race_id, r.year
               FROM competitions c JOIN races r ON c.race_id = r.id""",
            conn,
        )
    finally:
        conn.close()

    rec = rec.merge(comp_meta, on="competition_id", how="left")
    rec["comp_date"] = pd.to_datetime(rec["comp_date"])

    gt_sorted = gt.sort_values("gt_end")
    rec = rec.sort_values("comp_date").reset_index(drop=True)
    rec["row_id"] = np.arange(len(rec))
    m = rec[["row_id", "rider_id", "comp_date", "fc_race_id", "year"]].merge(
        gt_sorted[["rider_id", "gt_end", "fc_race_id", "gt_year"]],
        on="rider_id", how="left", suffixes=("", "_gt"))
    m = m[(m["gt_end"] < m["comp_date"])
          & ~((m["fc_race_id_gt"] == m["fc_race_id"]) & (m["gt_year"] == m["year"]))]
    last_gt = m.groupby("row_id")["gt_end"].max()
    rec["last_gt_end"] = rec["row_id"].map(last_gt)
    rec["days_since_gt"] = (rec["comp_date"] - rec["last_gt_end"]).dt.days
    rec["gt_band"] = rec["days_since_gt"].apply(_band)
    rec["is_win"] = (rec["place_bucket"] == 0).astype(int)
    rec["is_podium"] = (rec["place_bucket"] <= 1).astype(int)
    return rec


def table(df: pd.DataFrame, label: str, verbose: bool = True) -> Dict[str, Any]:
    """LambdaRank win-calibration table by GT-recency band (+ fold direction)."""
    if verbose:
        print(f"\n=== {label} ===")
        print(f"{'band':>20} {'n':>8} {'wins':>6} {'sum LR p':>9} {'cal':>6}  fold-consistency")
    out = {}
    for b in BANDS:
        g = df[df["gt_band"] == b]
        wins, psum = g["is_win"].sum(), g["lr_win_p"].sum()
        cal = psum / wins if wins else float("nan")
        # per-fold direction
        dirs = []
        for f, gf in g.groupby("fold_label"):
            w, p = gf["is_win"].sum(), gf["lr_win_p"].sum()
            if w > 0:
                dirs.append(p / w)
        under = sum(1 for c in dirs if c < 1)
        out[b] = {"n": int(len(g)), "wins": int(wins), "cal": round(float(cal), 3),
                  "folds_under": under, "folds": len(dirs),
                  "fold_cals": [round(c, 3) for c in dirs]}
        if verbose:
            print(f"{b:>20} {len(g):>8,} {wins:>6} {psum:>9.1f} {cal:>6.3f}  "
                  f"{under}/{len(dirs)} folds under-priced")
    return out


def ctable(df: pd.DataFrame, label: str, verbose: bool = True) -> Dict[str, Any]:
    """Contender-head win calibration by band (predicted-top-15 rows)."""
    if verbose:
        print(f"\n=== {label} (contender head, top-15 rows) ===")
    out = {}
    for b in BANDS:
        g = df[df["gt_band"] == b]
        wins, psum = g["is_win"].sum(), g["c_win_p"].sum()
        cal = psum / wins if wins else float("nan")
        out[b] = {"n": int(len(g)), "wins": int(wins), "cal": round(float(cal), 3)}
        if verbose:
            print(f"{b:>20} {len(g):>8,} {wins:>6} cal={cal:>6.3f}")
    return out


def gt_band_tables(rec: pd.DataFrame, verbose: bool = True) -> Dict[str, Any]:
    """The full diagnostic block on band-attached records (attach_gt_recency
    output): LR cal on all rows / GC targets / stage targets + contender head.
    """
    results: Dict[str, Any] = {"headline": {}, "subsets": {}}
    results["headline"]["all_rows"] = table(
        rec, "ALL test rows — LambdaRank win calibration", verbose)
    results["subsets"]["gc_targets"] = table(
        rec[rec["competition_type"] == "gc"], "GC targets only", verbose)
    results["subsets"]["stage_targets"] = table(
        rec[rec["competition_type"] == "stage"], "Stage targets only", verbose)
    cont = rec[rec["in_pred_top15"] & rec["c_win_p"].notna()]
    results["subsets"]["contender_head"] = ctable(cont, "ALL", verbose)
    return results


def main():
    rec = pd.read_csv(REC)
    print(f"records: {len(rec):,} rows, folds: {sorted(rec.fold_label.unique())}")

    gt = load_gt_participations()
    print(f"GT participations (>={MIN_GT_STAGE_ROWS} stages): {len(gt):,}")

    rec = attach_gt_recency(rec, gt=gt)
    print(f"date coverage: {rec['comp_date'].notna().mean():.1%}")

    results = gt_band_tables(rec)
    results["notes"] = {
        "records_source": str(REC.name),
        "caveat": "records from 2026-06-10 backtest = pre-trajectory (v2v3) heads; "
                  "mechanism exists in both form generations (live probe confirmed in v2v3)",
        "gt_definition": ">=10 stage rows in Giro/TdF/Vuelta edition; same-edition rows excluded",
    }

    OUT.write_text(json.dumps(results, indent=1))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
