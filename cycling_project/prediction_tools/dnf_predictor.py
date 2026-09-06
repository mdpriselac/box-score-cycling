"""
DNF head — binary LightGBM P(DNF | started) per rider per competition.

Labels come from the pickle-derived table built by
``experiments/build_dnf_labels.py`` (rider_results holds only finishers, so
the DB cannot supply non-finisher rows). Training rows are all starters:
finishers label 0, DNF/OOT/DSQ label 1; DNS rows are excluded (never started).

Feature design (deliberately symmetric between classes):

DNF'd riders have NO rider_competition_snapshots row for the competition they
abandoned (snapshots are built from rider_results). To avoid a
missing-data artifact between classes, EVERY row — finisher or DNF — is
featurized from the rider's latest snapshot STRICTLY BEFORE the competition
(merge_asof backward, exact matches excluded). This also matches serving
reality: future-race inference feeds every rider their latest stored
snapshot. Date-sensitive snapshot fields are replaced with values recomputed
from the label table itself (days_since_last_appearance; age from
riders.birth_year), which sees DNF appearances the snapshots never see.

Anchoring (leak control):
  one_day rows  -> features as of that date
  stage rows    -> features as of that stage's date (prior stages of the
                   same race are legitimately known)
  gc rows       -> features as of the RACE START date (the gc sheet's date is
                   the final stage; using it would leak the race's own
                   abandonment events into the gc row)

Rider DNF-history features are computed chronologically from the label table
(event level = one_day + stage rows only; gc rows duplicate the physical
abandonment events) with strictly-before semantics.

5-fold expanding-window CV matching the project's folds. Model artifact is
experiment-grade only (saved under experiments/, not models/production).

Usage:
    PYTHONUNBUFFERED=1 uv run python -m cycling_project.prediction_tools.dnf_predictor
"""

import glob
import gzip
import json
import os
import pickle as _pickle
import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import lightgbm as lgb
import numpy as np
import pandas as pd

from cycling_project.webscrape_tools.logging_config import get_logger
from cycling_project.prediction_tools.production_release import write_release_manifest
from cycling_project.db_path import default_db_path

logger = get_logger(__name__)

_DB_PATH = default_db_path()
OUT_DIR = Path("experiments")
_PRODUCTION_DIR = Path(__file__).parents[2] / "models" / "production"

# Production artifact filenames (self-contained, GCOutlookHead-style — the
# main ModelRegistry is untouched).
PRODUCTION_FILES = {
    "model": "dnf_model.txt",
    "features": "dnf_model_features.json",
    "metadata": "dnf_head_metadata.json",
    "events": "dnf_events.parquet",
}

START_DATE = "2016-01-01"  # head training window (history features use 2010+)

# Same folds as the production experiment harness
# (stacked_meta_learner_cv_5fold.FOLDS; duplicated so core code does not
# import from experiments/).
FOLDS = [
    {"train_end": "2019-12-31", "val_end": "2020-12-31", "label": "2021"},
    {"train_end": "2020-12-31", "val_end": "2021-12-31", "label": "2022"},
    {"train_end": "2021-12-31", "val_end": "2022-12-31", "label": "2023"},
    {"train_end": "2022-12-31", "val_end": "2023-12-31", "label": "2024"},
    {"train_end": "2023-12-31", "val_end": "2024-12-31", "label": "2025"},
]

# Shrinkage prior for career DNF rate: fixed constant (NOT estimated from the
# data) so no global statistic leaks across fold boundaries. 0.10 ~ the
# long-run event-level rate.
DNF_PRIOR_RATE = 0.10
DNF_PRIOR_STRENGTH = 20.0

# --------------------------------------------------------------------------
# Feature column groups
# --------------------------------------------------------------------------

SNAPSHOT_FEATURES = [
    "races_career", "races_this_year",
    "stage_avg_bucket", "stage_count", "one_day_avg_bucket", "one_day_count",
    "gc_avg_bucket", "gc_count", "wt_avg_bucket", "wt_count",
    "pro_avg_bucket", "pro_count", "d1_avg_bucket", "d1_count",
    "sprint_avg_bucket", "mountain_avg_bucket", "hilly_avg_bucket",
    "rolling_avg_bucket", "breakaway_avg_bucket", "time_trial_avg_bucket",
    "form_recent_avg_bucket", "form_recent_best_bucket", "form_recent_count",
    "form_delta", "form_profile_recent_avg",
    "team_quality_mean", "team_quality_median", "team_quality_std",
    "team_quality_min", "team_quality_max", "team_quality_p25",
    "team_quality_p75", "team_size", "team_depth",
    # trajectory/EMA form — NaN means no qualifying history, never imputed
    "v2_ema_pct_h30", "v2_ema_pct_h60", "v2_ema_pct_qw_h60",
    "v2_ema_eff_n_h60", "v2_ema_bucket_h60",
    "v3_season_pct_cur", "v3_season_pct_prev", "v3_season_pct_prev2",
    "v3_season_delta", "v3_season_delta_prev", "v3_slope365", "v3_races365",
    "v3_peak_season_pct", "v3_decline_from_peak", "v3_season_races_cur",
]
# deliberately excluded from the head: days_since_last_race (replaced by the
# recomputed days_since_last_appearance), team_bib/personal_bib (stale bibs
# from a different race), age (recomputed from birth_year), best_profile (text)

FIELD_FEATURES = [
    "field_size", "experience_mean", "experience_median", "experience_std",
    "bucket_mean", "bucket_median", "bucket_std",
    "sprinter_count", "climber_count", "hilly_specialist_count",
    "rolling_specialist_count", "breakaway_specialist_count",
    "time_trialist_count", "unknown_profile_count",
    "race_sprint_score", "race_mountain_score", "race_hilly_score",
    "race_rolling_score", "race_breakaway_score", "race_time_trial_score",
]

HISTORY_FEATURES = [
    "career_starts", "career_dnf_rate_shrunk", "dnfs_last_365d",
    "days_since_last_dnf", "races_since_last_dnf", "days_since_last_appearance",
]

CONTEXT_FEATURES = [
    "age", "month", "stage_number",
    "type_one_day", "type_stage", "type_gc",
    "cat_wt", "cat_pro", "cat_d1",
]

FEATURE_COLUMNS = SNAPSHOT_FEATURES + FIELD_FEATURES + HISTORY_FEATURES + CONTEXT_FEATURES

META_COLUMNS = [
    "competition_id", "rider_id", "competition_date", "asof_date",
    "competition_type", "race_category", "dnf",
]


# --------------------------------------------------------------------------
# Label loading
# --------------------------------------------------------------------------

def find_latest_labels(out_dir: Path = OUT_DIR) -> Path:
    paths = sorted(glob.glob(str(out_dir / "dnf_labels_*.csv.gz")))
    if not paths:
        raise FileNotFoundError(
            "No experiments/dnf_labels_*.csv.gz found — run "
            "cycling_project.prediction_tools.experiments.build_dnf_labels first"
        )
    return Path(paths[-1])


def load_labels(path: Optional[Path] = None) -> pd.DataFrame:
    path = path or find_latest_labels()
    logger.info(f"Loading DNF labels from {path}")
    with gzip.open(path, "rt") as f:
        df = pd.read_csv(f)
    df["competition_date"] = pd.to_datetime(df["competition_date"])
    return df


# --------------------------------------------------------------------------
# As-of anchoring + rider DNF-history features
# --------------------------------------------------------------------------

def add_asof_dates(labels: pd.DataFrame) -> pd.DataFrame:
    """asof_date: own date for one_day/stage; race start date for gc rows."""
    labels = labels.copy()
    stage_rows = labels[labels["competition_type"] == "stage"]
    race_start = (
        stage_rows.groupby(["fc_race_id", "year", "race_category"])["competition_date"]
        .min().rename("race_start_date").reset_index()
    )
    labels = labels.merge(race_start, on=["fc_race_id", "year", "race_category"], how="left")
    is_gc = labels["competition_type"] == "gc"
    labels["asof_date"] = labels["competition_date"]
    labels.loc[is_gc, "asof_date"] = labels.loc[is_gc, "race_start_date"].fillna(
        labels.loc[is_gc, "competition_date"]
    )
    n_fallback = int((is_gc & labels["race_start_date"].isna()).sum())
    if n_fallback:
        logger.info(f"{n_fallback} gc rows lack stage rows; asof_date fell back to gc date")
    return labels.drop(columns=["race_start_date"])


def extract_history_events(labels: pd.DataFrame, key_col: str = "rider_fc_id") -> pd.DataFrame:
    """Started one_day/stage rows as (key, competition_date, dnf) event stream.

    gc rows excluded: they duplicate the per-stage abandonment events.
    """
    ev = labels[
        (labels["started"] == 1)
        & (labels["competition_type"].isin(["one_day", "stage"]))
        & labels["competition_date"].notna()
        & labels[key_col].notna()
    ][[key_col, "competition_date", "dnf"]].copy()
    return ev.sort_values([key_col, "competition_date"])


def history_features_from_events(
    events: pd.DataFrame,
    queries: pd.DataFrame,
    key_col: str,
) -> Dict[str, np.ndarray]:
    """HISTORY_FEATURES per query row, strictly before each row's asof_date.

    events: (key_col, competition_date, dnf), date-sorted within key.
    queries: (key_col, asof_date). Returns {feature: array aligned to
    queries' row order}. Riders with no event history get the same
    fixed-prior defaults used at training time.
    """
    out_cols = {c: np.full(len(queries), np.nan) for c in HISTORY_FEATURES}
    ev_groups = {k: g for k, g in events.groupby(key_col, sort=False)}
    day = np.timedelta64(1, "D")

    for rider, q in queries.groupby(key_col, sort=False):
        idx = queries.index.get_indexer_for(q.index)  # positional indices
        qd = q["asof_date"].values.astype("datetime64[ns]")

        g = ev_groups.get(rider)
        if g is None or len(g) == 0:
            out_cols["career_starts"][idx] = 0
            out_cols["career_dnf_rate_shrunk"][idx] = DNF_PRIOR_RATE
            out_cols["dnfs_last_365d"][idx] = 0
            out_cols["races_since_last_dnf"][idx] = 0
            continue

        ed = g["competition_date"].values.astype("datetime64[ns]")
        ednf = g["dnf"].values.astype(float)
        cum_dnf = np.concatenate([[0.0], np.cumsum(ednf)])
        # last DNF position (index into ed) at-or-before each event position
        last_dnf_pos = np.where(ednf > 0, np.arange(len(ed)), -1)
        last_dnf_pos = np.maximum.accumulate(last_dnf_pos)

        pos = np.searchsorted(ed, qd, side="left")        # events strictly before
        pos365 = np.searchsorted(ed, qd - 365 * day, side="left")

        starts = pos.astype(float)
        dnfs = cum_dnf[pos]
        out_cols["career_starts"][idx] = starts
        out_cols["career_dnf_rate_shrunk"][idx] = (
            (dnfs + DNF_PRIOR_STRENGTH * DNF_PRIOR_RATE)
            / (starts + DNF_PRIOR_STRENGTH)
        )
        out_cols["dnfs_last_365d"][idx] = cum_dnf[pos] - cum_dnf[pos365]

        has_prior = pos > 0
        lp = np.where(has_prior, last_dnf_pos[np.maximum(pos - 1, 0)], -1)
        has_dnf = lp >= 0
        dsl = np.where(
            has_dnf, (qd - ed[np.maximum(lp, 0)]) / day, np.nan
        )
        out_cols["days_since_last_dnf"][idx] = dsl
        out_cols["races_since_last_dnf"][idx] = np.where(
            has_dnf, pos - (lp + 1), pos
        )
        out_cols["days_since_last_appearance"][idx] = np.where(
            has_prior, (qd - ed[np.maximum(pos - 1, 0)]) / day, np.nan
        )

    return out_cols


def build_history_features(labels: pd.DataFrame) -> pd.DataFrame:
    """
    Chronological rider DNF-history features, strictly before asof_date.

    Events = started one_day/stage rows (gc rows excluded: they duplicate the
    per-stage abandonment events). Returns one row per label row, aligned by
    (competition_id, rider_id, rider_fc_id).
    """
    ev = extract_history_events(labels, "rider_fc_id")
    queries = labels[["competition_id", "rider_id", "rider_fc_id", "asof_date"]].copy()
    out_cols = history_features_from_events(ev, queries, "rider_fc_id")

    hist = queries[["competition_id", "rider_id", "rider_fc_id"]].copy()
    for c in HISTORY_FEATURES:
        hist[c] = out_cols[c]
    return hist


# --------------------------------------------------------------------------
# Snapshot attach (shared with the market-adjustment experiment)
# --------------------------------------------------------------------------

def load_snapshot_table(db_path: Optional[str] = None) -> pd.DataFrame:
    """All rider snapshots with their competition date (snap_date), date-sorted."""
    db_path = db_path or str(_DB_PATH)
    with sqlite3.connect(db_path) as conn:
        snaps = pd.read_sql_query(
            """SELECT rcs.*, c.date AS snap_date
               FROM rider_competition_snapshots rcs
               JOIN competitions c ON rcs.competition_id = c.id
               WHERE c.date IS NOT NULL""",
            conn,
        )
    snaps["snap_date"] = pd.to_datetime(snaps["snap_date"])
    return snaps.sort_values("snap_date").reset_index(drop=True)


def attach_prior_snapshots(
    df: pd.DataFrame,
    snaps: pd.DataFrame,
    asof_col: str = "asof_date",
    columns: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    For each (rider_id, asof_date) row, attach the rider's latest snapshot
    STRICTLY before asof_date. Snapshot competition_id is exposed as
    snap_competition_id to avoid clobbering the target competition_id.
    """
    take = columns or [c for c in snaps.columns if c not in ("snap_date",)]
    right = snaps[["rider_id", "snap_date"] + [c for c in take if c not in ("rider_id",)]].rename(
        columns={"competition_id": "snap_competition_id"}
    )
    left = df.copy()
    left["rider_id"] = left["rider_id"].astype("int64")
    right["rider_id"] = right["rider_id"].astype("int64")
    left["_asof"] = pd.to_datetime(left[asof_col])
    left = left.sort_values("_asof", kind="mergesort")
    merged = pd.merge_asof(
        left,
        right,
        left_on="_asof",
        right_on="snap_date",
        by="rider_id",
        direction="backward",
        allow_exact_matches=False,
    )
    return merged.drop(columns=["_asof"])


# --------------------------------------------------------------------------
# Modeling frame
# --------------------------------------------------------------------------

def build_feature_frame(
    labels: Optional[pd.DataFrame] = None,
    db_path: Optional[str] = None,
    snaps: Optional[pd.DataFrame] = None,
    start_date: str = "2010-01-01",
) -> pd.DataFrame:
    """
    Full modeling frame: one row per started (competition, rider) label row
    with FEATURE_COLUMNS + META_COLUMNS. History features see 2010+ even when
    rows are later filtered to the training window.
    """
    db_path = db_path or str(_DB_PATH)
    if labels is None:
        labels = load_labels()
    labels = labels[labels["competition_date"].notna() & labels["rider_id"].notna()].copy()
    labels["rider_id"] = labels["rider_id"].astype("int64")
    labels = add_asof_dates(labels)

    rows = labels[labels["started"] == 1].copy()
    rows["dnf"] = rows["dnf"].astype(int)

    # ---- history features (chronological, strictly-before) ----
    logger.info("Computing rider DNF-history features...")
    hist = build_history_features(rows)
    rows = rows.reset_index(drop=True)
    hist = hist.reset_index(drop=True)
    for c in HISTORY_FEATURES:
        rows[c] = hist[c].values

    # ---- prior snapshots ----
    logger.info("Attaching prior snapshots (merge_asof, strictly-before)...")
    if snaps is None:
        snaps = load_snapshot_table(db_path)
    snap_cols = ["rider_id", "competition_id", "age"] + SNAPSHOT_FEATURES
    rows = attach_prior_snapshots(rows, snaps, "asof_date", columns=snap_cols)
    rows = rows.rename(columns={"age": "snap_age"})

    # ---- competition-level features ----
    with sqlite3.connect(db_path) as conn:
        cff = pd.read_sql_query(
            f"SELECT competition_id, {', '.join(FIELD_FEATURES)} "
            "FROM competition_field_features",
            conn,
        )
        birth = pd.read_sql_query("SELECT id AS rider_id, birth_year FROM riders", conn)
    rows = rows.merge(cff, on="competition_id", how="left")
    rows = rows.merge(birth, on="rider_id", how="left")

    # ---- context ----
    rows["competition_date"] = pd.to_datetime(rows["competition_date"])
    rows["month"] = rows["competition_date"].dt.month
    comp_year = rows["competition_date"].dt.year
    rows["age"] = np.where(
        rows["birth_year"].notna(), comp_year - rows["birth_year"], rows["snap_age"]
    )
    for t in ("one_day", "stage", "gc"):
        rows[f"type_{t}"] = (rows["competition_type"] == t).astype(int)
    for c in ("wt", "pro", "d1"):
        rows[f"cat_{c}"] = (rows["race_category"] == c).astype(int)
    rows["stage_number"] = pd.to_numeric(rows["stage_number"], errors="coerce")

    rows = rows[rows["competition_date"] >= pd.to_datetime(start_date)].copy()
    return rows[META_COLUMNS + FEATURE_COLUMNS + ["snap_competition_id"]].reset_index(drop=True)


# --------------------------------------------------------------------------
# Predictor
# --------------------------------------------------------------------------

@dataclass
class DNFPredictorConfig:
    n_estimators: int = 2000
    early_stopping_rounds: int = 100
    lgb_params: Dict[str, Any] = field(default_factory=lambda: {
        "objective": "binary",
        "metric": "binary_logloss",
        "learning_rate": 0.05,
        "num_leaves": 63,
        "min_child_samples": 100,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 5,
        "verbosity": -1,
        "seed": 42,
    })


class DNFPredictor:
    """Binary LightGBM head: P(DNF | started) per (rider, competition) row."""

    def __init__(self, config: Optional[DNFPredictorConfig] = None):
        self.config = config or DNFPredictorConfig()
        self.model: Optional[lgb.Booster] = None
        self.feature_columns = list(FEATURE_COLUMNS)

    def _matrix(self, df: pd.DataFrame) -> pd.DataFrame:
        return df[self.feature_columns].astype(float)

    def train(
        self,
        train_df: pd.DataFrame,
        val_df: Optional[pd.DataFrame] = None,
        verbose: bool = False,
    ) -> Dict[str, Any]:
        X = self._matrix(train_df)
        y = train_df["dnf"].values.astype(int)
        train_set = lgb.Dataset(X, y, feature_name=self.feature_columns)
        valid_sets, valid_names = [train_set], ["train"]
        if val_df is not None and len(val_df):
            valid_sets.append(
                lgb.Dataset(self._matrix(val_df), val_df["dnf"].values.astype(int),
                            reference=train_set)
            )
            valid_names.append("val")
        callbacks = []
        if verbose:
            callbacks.append(lgb.log_evaluation(period=100))
        if self.config.early_stopping_rounds and val_df is not None:
            callbacks.append(lgb.early_stopping(self.config.early_stopping_rounds,
                                                verbose=verbose))
        self.model = lgb.train(
            self.config.lgb_params, train_set,
            num_boost_round=self.config.n_estimators,
            valid_sets=valid_sets, valid_names=valid_names, callbacks=callbacks,
        )
        return {"best_iteration": self.model.best_iteration}

    def predict_dnf_proba(self, df: pd.DataFrame) -> np.ndarray:
        if self.model is None:
            raise ValueError("train first")
        return self.model.predict(self._matrix(df))

    def feature_importance(self) -> Dict[str, float]:
        imp = self.model.feature_importance(importance_type="gain")
        return dict(sorted(zip(self.feature_columns, imp.astype(float)),
                           key=lambda kv: kv[1], reverse=True))

    def save(self, model_path: Path, features_path: Path):
        self.model.save_model(str(model_path))
        features_path.write_text(json.dumps(self.feature_columns, indent=2))

    @classmethod
    def load(cls, model_path: Path, features_path: Path) -> "DNFPredictor":
        obj = cls()
        obj.model = lgb.Booster(model_file=str(model_path))
        obj.feature_columns = json.loads(features_path.read_text())
        return obj


# --------------------------------------------------------------------------
# Evaluation
# --------------------------------------------------------------------------

def evaluate_dnf(y: np.ndarray, p: np.ndarray, n_deciles: int = 10) -> Dict[str, Any]:
    from sklearn.metrics import roc_auc_score

    y = np.asarray(y, dtype=float)
    p = np.clip(np.asarray(p, dtype=float), 1e-12, 1 - 1e-12)
    out: Dict[str, Any] = {
        "n": int(len(y)),
        "base_rate": float(y.mean()),
        "mean_pred": float(p.mean()),
        "auc": float(roc_auc_score(y, p)) if 0 < y.mean() < 1 else float("nan"),
        "log_loss": float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))),
        "brier": float(np.mean((p - y) ** 2)),
        "cal_ratio": float(p.sum() / max(y.sum(), 1.0)),
    }
    order = np.argsort(p)
    bins = np.array_split(order, n_deciles)
    out["calibration_deciles"] = [
        {"decile": i + 1, "n": int(len(b)),
         "mean_pred": float(p[b].mean()), "actual_rate": float(y[b].mean())}
        for i, b in enumerate(bins) if len(b)
    ]
    return out


# --------------------------------------------------------------------------
# Label refresh from the scraped pickles (production port of
# experiments/build_dnf_labels.py — rider_results holds only finishers, so
# the pickle corpus remains the only per-rider source of non-finisher rows)
# --------------------------------------------------------------------------

DNS_STATUSES = {"DNS"}


def _scraped_dir() -> Path:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    return Path(os.getenv("SCRAPED_DATA_DIR") or os.getenv("DB_PATH")
                or str(Path.home() / "cycling_data" / "scraped_data"))


def _classify_place(place_raw) -> tuple:
    """-> (status_raw, started, dnf, place); started/dnf None = unknown row."""
    if place_raw is None:
        return ("NONE", None, None, None)
    s = str(place_raw).strip()
    if s == "":
        return ("EMPTY", None, None, None)
    if s.isdigit():
        return ("FIN", 1, 0, int(s))
    su = s.upper()
    if su in DNS_STATUSES:
        return (su, 0, None, None)
    return (su, 1, 1, None)


def _rider_key(row: dict) -> str:
    fc = row.get("rider_id")
    if fc:
        return str(fc)
    name = row.get("name") or ""
    return f"unknown_{name.replace(' ', '_')}"  # migration fallback convention


def _extract_label_rows(results, comp_key, comp_by_url, rider_by_fc, counters,
                        fc_race_id, year, category):
    cid_info = comp_by_url.get(comp_key)
    if cid_info is None:
        counters["unmatched_competitions"] += 1
        return []
    cid, date, stage_no = cid_info
    ctype = comp_key[1]
    rows = []
    for r in results:
        if not isinstance(r, dict):
            counters["non_dict_result_rows"] += 1
            continue
        status, started, dnf, place = _classify_place(r.get("place"))
        counters["status_" + status] += 1
        fc_rid = _rider_key(r)
        rid = rider_by_fc.get(fc_rid)
        if rid is None:
            counters["unmatched_riders"] += 1
        rows.append((cid, rid, fc_rid, status, started, dnf, place,
                     ctype, date, category, str(fc_race_id), year, stage_no))
    return rows


def refresh_labels_from_pickles(
    db_path: Optional[str] = None,
    scraped_dir: Optional[Path] = None,
    out_dir: Path = OUT_DIR,
) -> Path:
    """Walk the pickle corpus read-only and write a fresh dnf_labels file.

    Returns the path of the written experiments/dnf_labels_<ts>.csv.gz.
    Raises FileNotFoundError when the scraped pickle directory is absent
    (callers fall back to the latest existing labels file).
    """
    src = scraped_dir or _scraped_dir()
    if not src.is_dir():
        raise FileNotFoundError(f"Scraped pickle directory not found: {src}")

    db_path = db_path or str(_DB_PATH)
    conn = sqlite3.connect(db_path)
    try:
        comp_by_url = {}
        for cid, url, ctype, date, stage_no in conn.execute(
            "SELECT id, url, competition_type, date, stage_number FROM competitions"
        ):
            comp_by_url[(url, ctype)] = (cid, date, stage_no)
        rider_by_fc = {fc: rid for rid, fc in conn.execute("SELECT id, fc_rider_id FROM riders")}
    finally:
        conn.close()
    logger.info("Label refresh lookups: %d competitions, %d riders",
                len(comp_by_url), len(rider_by_fc))

    counters: Counter = Counter()
    all_rows: List[tuple] = []
    year_dirs = sorted(d for d in src.iterdir() if d.is_dir() and d.name.isdigit())
    for ydir in year_dirs:
        year = int(ydir.name)
        for cat in ("wt", "pro", "d1"):
            cdir = ydir / cat
            if not cdir.exists():
                continue
            for pkl in sorted(cdir.glob("*.pkl")):
                try:
                    with open(pkl, "rb") as f:
                        race = _pickle.load(f)
                except Exception as exc:
                    counters["pickle_errors"] += 1
                    logger.warning(f"Failed to load {pkl}: {exc}")
                    continue
                if race.stage_race:
                    if race.results:
                        all_rows += _extract_label_rows(
                            race.results, (race.url, "gc"), comp_by_url,
                            rider_by_fc, counters, race.fc_race_id, year, cat)
                    for st in race.stages or []:
                        if st.name.strip().upper() == "GC":
                            continue
                        if st.results:
                            all_rows += _extract_label_rows(
                                st.results, (st.url, "stage"), comp_by_url,
                                rider_by_fc, counters, race.fc_race_id, year, cat)
                else:
                    if race.results:
                        all_rows += _extract_label_rows(
                            race.results, (race.url, "one_day"), comp_by_url,
                            rider_by_fc, counters, race.fc_race_id, year, cat)
        logger.info("Label refresh %d: %d rows total", year, len(all_rows))

    df = pd.DataFrame(all_rows, columns=[
        "competition_id", "rider_id", "rider_fc_id", "status_raw", "started",
        "dnf", "place", "competition_type", "competition_date", "race_category",
        "fc_race_id", "year", "stage_number",
    ])
    n_dupes = int(df.duplicated(subset=["competition_id", "rider_id", "rider_fc_id"]).sum())
    df = df.drop_duplicates(subset=["competition_id", "rider_id", "rider_fc_id"], keep="first")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir.mkdir(exist_ok=True)
    out_csv = out_dir / f"dnf_labels_{ts}.csv.gz"
    with gzip.open(out_csv, "wt") as f:
        df.to_csv(f, index=False)
    logger.info("Wrote %d label rows (%d dupes dropped) -> %s  counters: %s",
                len(df), n_dupes, out_csv, dict(counters))
    return out_csv


# --------------------------------------------------------------------------
# Production training + serving
# --------------------------------------------------------------------------

def train_production_dnf_head(
    db_path: Optional[str] = None,
    model_dir: Optional[Path] = None,
    refresh_labels: bool = True,
) -> Dict[str, Any]:
    """Train the DNF head on all labels through today; save to models/production.

    Labels: refreshed from the scraped pickles when available (the only
    source of non-finisher rows); otherwise falls back to the most recent
    experiments/dnf_labels_*.csv.gz with a warning.

    Split: last 5% of competitions chronologically for early stopping only
    (matches train_production_model's convention).

    Also persists dnf_events.parquet — the rider-level (rider_id,
    competition_date, dnf) event stream the serving path needs to recompute
    the as-of-today history features.
    """
    model_dir = Path(model_dir) if model_dir else _PRODUCTION_DIR
    model_dir.mkdir(parents=True, exist_ok=True)

    labels_path: Optional[Path] = None
    if refresh_labels:
        try:
            labels_path = refresh_labels_from_pickles(db_path=db_path)
        except FileNotFoundError as exc:
            logger.warning("Label refresh unavailable (%s); using latest labels file", exc)
    if labels_path is None:
        labels_path = find_latest_labels()

    labels = load_labels(labels_path)
    frame = build_feature_frame(labels=labels, db_path=db_path, start_date=START_DATE)
    frame["competition_date"] = pd.to_datetime(frame["competition_date"])
    logger.info(
        "DNF production frame: %d started rows, %d comps, DNF rate %.4f",
        len(frame), frame["competition_id"].nunique(), frame["dnf"].mean(),
    )

    # Last 5% of competitions (by date) for early stopping only
    comp_dates = (
        frame.groupby("competition_id")["competition_date"].first().sort_values()
    )
    cutoff_date = comp_dates.iloc[int(len(comp_dates) * 0.95)]
    train = frame[frame["competition_date"] < cutoff_date]
    early_stop = frame[frame["competition_date"] >= cutoff_date]
    logger.info(
        "DNF split: train %d rows (< %s), early-stop %d rows",
        len(train), cutoff_date.date(), len(early_stop),
    )

    head = DNFPredictor()
    info = head.train(train, early_stop)
    es_metrics = evaluate_dnf(
        early_stop["dnf"].values, head.predict_dnf_proba(early_stop)
    )
    es_small = {k: es_metrics[k] for k in
                ("n", "base_rate", "mean_pred", "auc", "log_loss", "brier", "cal_ratio")}
    logger.info("DNF head early-stop metrics: %s", es_small)

    head.save(model_dir / PRODUCTION_FILES["model"],
              model_dir / PRODUCTION_FILES["features"])

    # Event stream for serving-time history features (rider_id-keyed; rows
    # with no DB rider match are dropped — they can't be served anyway).
    labels_ev = labels[labels["competition_date"].notna()].copy()
    labels_ev["competition_date"] = pd.to_datetime(labels_ev["competition_date"])
    events = extract_history_events(labels_ev, "rider_id")
    events["rider_id"] = events["rider_id"].astype("int64")
    events["dnf"] = events["dnf"].astype("int8")
    events.to_parquet(model_dir / PRODUCTION_FILES["events"], index=False)

    metadata = {
        "trained_at": datetime.now().isoformat(timespec="seconds"),
        "labels_file": str(labels_path),
        "n_rows": int(len(frame)),
        "n_train_rows": int(len(train)),
        "early_stop_cutoff": str(cutoff_date.date()),
        "best_iteration": info["best_iteration"],
        "n_features": len(FEATURE_COLUMNS),
        "early_stop_metrics": es_small,
        "n_event_rows": int(len(events)),
        "dnf_prior_rate": DNF_PRIOR_RATE,
        "dnf_prior_strength": DNF_PRIOR_STRENGTH,
    }
    (model_dir / PRODUCTION_FILES["metadata"]).write_text(
        json.dumps(metadata, indent=2, default=str)
    )
    write_release_manifest(model_dir)
    logger.info("DNF head saved to %s", model_dir)
    return metadata


def load_production_dnf_head(
    model_dir: Optional[Path] = None,
) -> Optional[Tuple["DNFPredictor", pd.DataFrame, Dict[str, Any]]]:
    """Load the production DNF head + serving event stream, or None if absent."""
    model_dir = Path(model_dir) if model_dir else _PRODUCTION_DIR
    model_path = model_dir / PRODUCTION_FILES["model"]
    feat_path = model_dir / PRODUCTION_FILES["features"]
    events_path = model_dir / PRODUCTION_FILES["events"]
    if not (model_path.exists() and feat_path.exists() and events_path.exists()):
        return None
    head = DNFPredictor.load(model_path, feat_path)
    events = pd.read_parquet(events_path)
    events["competition_date"] = pd.to_datetime(events["competition_date"])
    meta_path = model_dir / PRODUCTION_FILES["metadata"]
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    return head, events, meta


def build_serving_dnf_frame(
    pred_df: pd.DataFrame,
    events: pd.DataFrame,
    asof_date: Optional[str] = None,
    competition_type: str = "one_day",
    race_category: str = "wt",
    stage_number: Optional[int] = None,
    db_path: Optional[str] = None,
) -> pd.DataFrame:
    """DNF-head feature frame for a future-race prediction frame.

    pred_df is the assembled prediction frame (assemble_prediction_df
    output): rider snapshot columns (live-form re-aged), field features and
    race profile scores are read straight off it. History features are
    recomputed from the production event stream strictly before asof_date
    (default today), mirroring training's as-of-then discipline. Age is
    recomputed from riders.birth_year.
    """
    asof = pd.to_datetime(asof_date) if asof_date else pd.Timestamp.today().normalize()
    db_path = db_path or str(_DB_PATH)

    rows = pred_df.copy().reset_index(drop=True)
    rows["rider_id"] = rows["rider_id"].astype("int64")
    rows["asof_date"] = asof

    # ---- history features from the persisted event stream ----
    ev = events[events["rider_id"].isin(set(rows["rider_id"]))].copy()
    ev = ev.sort_values(["rider_id", "competition_date"])
    queries = rows[["rider_id", "asof_date"]].copy()
    hist = history_features_from_events(ev, queries, "rider_id")
    for c in HISTORY_FEATURES:
        rows[c] = hist[c]

    # ---- age from birth_year (snapshot age is as-of the last race) ----
    with sqlite3.connect(db_path) as conn:
        birth = pd.read_sql_query("SELECT id AS rider_id, birth_year FROM riders", conn)
    rows = rows.merge(birth, on="rider_id", how="left")
    snap_age = pd.to_numeric(rows.get("age"), errors="coerce")
    rows["age"] = np.where(
        rows["birth_year"].notna(), asof.year - rows["birth_year"], snap_age
    )

    # ---- context ----
    rows["month"] = asof.month
    rows["stage_number"] = (
        float(stage_number) if stage_number is not None else np.nan
    )
    for t in ("one_day", "stage", "gc"):
        rows[f"type_{t}"] = int(competition_type == t)
    for c in ("wt", "pro", "d1"):
        rows[f"cat_{c}"] = int(race_category == c)

    missing = [c for c in FEATURE_COLUMNS if c not in rows.columns]
    for c in missing:
        rows[c] = np.nan
    if missing:
        logger.warning("DNF serving frame missing columns (filled NaN): %s", missing)
    return rows


# --------------------------------------------------------------------------
# CV main
# --------------------------------------------------------------------------

def main():
    started = datetime.now()
    print("=" * 70, flush=True)
    print("DNF HEAD — binary P(DNF | started), 5-fold expanding-window CV", flush=True)
    print("=" * 70, flush=True)

    frame = build_feature_frame(start_date=START_DATE)
    frame["competition_date"] = pd.to_datetime(frame["competition_date"])
    n_nosnap = int(frame["races_career"].isna().sum())
    print(
        f"Frame: {len(frame):,} started rows, {frame['competition_id'].nunique():,} comps, "
        f"DNF rate {frame['dnf'].mean():.4f}, rows w/o prior snapshot {n_nosnap:,} "
        f"({100 * n_nosnap / len(frame):.1f}%)",
        flush=True,
    )

    fold_results: List[Dict[str, Any]] = []
    for i, fold in enumerate(FOLDS):
        train_end = pd.to_datetime(fold["train_end"])
        val_end = pd.to_datetime(fold["val_end"])
        train = frame[frame["competition_date"] <= train_end]
        val = frame[(frame["competition_date"] > train_end)
                    & (frame["competition_date"] <= val_end)]
        test = frame[frame["competition_date"] > val_end]
        print(
            f"\nFOLD {i + 1}/{len(FOLDS)} (test={fold['label']}+): "
            f"train {len(train):,} (rate {train['dnf'].mean():.4f}) | "
            f"val {len(val):,} | test {len(test):,} (rate {test['dnf'].mean():.4f})",
            flush=True,
        )
        model = DNFPredictor()
        info = model.train(train, val)
        p = model.predict_dnf_proba(test)

        res: Dict[str, Any] = {
            "fold_label": fold["label"],
            "best_iteration": info["best_iteration"],
            "metrics": {"all": evaluate_dnf(test["dnf"].values, p)},
        }
        for t in ("one_day", "stage", "gc"):
            m = (test["competition_type"] == t).values
            if m.sum():
                res["metrics"][t] = evaluate_dnf(test["dnf"].values[m], p[m])
        res["feature_importance_top20"] = dict(
            list(model.feature_importance().items())[:20]
        )
        a = res["metrics"]["all"]
        print(
            f"  all: AUC={a['auc']:.4f}  LL={a['log_loss']:.4f}  Brier={a['brier']:.4f}  "
            f"cal={a['cal_ratio']:.3f}  (best_iter={info['best_iteration']})",
            flush=True,
        )
        for t in ("one_day", "stage", "gc"):
            if t in res["metrics"]:
                m = res["metrics"][t]
                print(
                    f"  {t:<8s} AUC={m['auc']:.4f}  LL={m['log_loss']:.4f}  "
                    f"base={m['base_rate']:.4f}  cal={m['cal_ratio']:.3f}",
                    flush=True,
                )
        fold_results.append(res)

    # Aggregate
    agg = {}
    for subset in ("all", "one_day", "stage", "gc"):
        vals = {k: [fr["metrics"][subset][k] for fr in fold_results if subset in fr["metrics"]]
                for k in ("auc", "log_loss", "brier", "cal_ratio")}
        agg[subset] = {k: {"mean": float(np.mean(v)), "std": float(np.std(v)),
                           "per_fold": [float(x) for x in v]}
                       for k, v in vals.items() if v}
    print("\nAGGREGATE (mean±std over folds):", flush=True)
    for subset in ("all", "one_day", "stage", "gc"):
        s = agg[subset]
        print(
            f"  {subset:<8s} AUC={s['auc']['mean']:.4f}±{s['auc']['std']:.4f}  "
            f"LL={s['log_loss']['mean']:.4f}±{s['log_loss']['std']:.4f}  "
            f"cal={s['cal_ratio']['mean']:.3f}±{s['cal_ratio']['std']:.3f}",
            flush=True,
        )

    # Final artifact: train <= 2024, early-stop on 2025+
    print("\nTraining final artifact (train <= 2024-12-31, val 2025+)...", flush=True)
    cut = pd.to_datetime("2024-12-31")
    final = DNFPredictor()
    final_info = final.train(
        frame[frame["competition_date"] <= cut],
        frame[frame["competition_date"] > cut],
    )
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(exist_ok=True)
    model_path = OUT_DIR / f"dnf_model_{ts}.txt"
    feat_path = OUT_DIR / f"dnf_model_features_{ts}.json"
    final.save(model_path, feat_path)

    out = {
        "started_at": started.isoformat(),
        "ended_at": datetime.now().isoformat(),
        "labels_file": str(find_latest_labels()),
        "config": {
            "start_date": START_DATE, "folds": FOLDS,
            "dnf_prior_rate": DNF_PRIOR_RATE, "dnf_prior_strength": DNF_PRIOR_STRENGTH,
            "n_features": len(FEATURE_COLUMNS),
            "lgb_params": DNFPredictorConfig().lgb_params,
        },
        "frame_stats": {
            "rows": int(len(frame)),
            "dnf_rate": float(frame["dnf"].mean()),
            "rows_without_prior_snapshot": n_nosnap,
        },
        "fold_results": fold_results,
        "aggregated": agg,
        "final_artifact": {
            "model": str(model_path), "features": str(feat_path),
            "best_iteration": final_info["best_iteration"],
        },
    }
    out_path = OUT_DIR / f"dnf_predictor_cv_{ts}.json"
    out_path.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nResults -> {out_path}", flush=True)
    print(f"Artifact -> {model_path}", flush=True)
    print(f"Runtime: {(datetime.now() - started).total_seconds():.0f}s", flush=True)


if __name__ == "__main__":
    main()
