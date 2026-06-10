"""
Form feature lab — experiment-side recomputation of candidate form features.

Computes richer rider recent-form features on the fly from `rider_results`
(no snapshot schema change, no precompute rebuild), keyed by
(rider_id, competition_id) for merging onto the training dataframe. The
training FeatureEngineer auto-includes any numeric column, so attaching is
just a merge. Column names deliberately avoid the imputation patterns
('avg_bucket', '_count') so NaN passes through to LightGBM as native
missing values — the "honest defaults" fix.

Leak-freedom replicates production form logic
(engineering_tools/form_team_features.py):
  - only races strictly before the target's effective date count
  - GC targets use the race start date as effective date and additionally
    exclude all same-(race_id, year) competitions
  - stage targets legitimately see earlier stages of the same race
  - history excludes DNFs (rider_results stores finishers only)

History runs from HISTORY_START (2010) so windows and season aggregates
have runway before the 2016 training start. `percentile` is the stored
within-race finishing percentile (100 = winner, higher = better).
Buckets: lower = better (0 = winner .. 6 = 51+).

Feature families (all additive, v-prefixed):

  v1 — fixed-window variants of the existing six form features:
       cross-calendar-year 90-day window, NaN when empty
  v2 — time-decayed EMA form on percentile (and bucket), 365d lookback,
       optional race-category quality weighting
  v3 — multi-season trajectory: season percentile averages and deltas,
       within-365d slope, decline-from-peak
  v4 — volatility: dispersion of recent percentiles

Usage:
    from cycling_project.prediction_tools.experiments.form_feature_lab import (
        FormFeatureLab, V1_COLS, V2_COLS, V3_COLS, V4_COLS
    )
    lab = FormFeatureLab()
    feats = lab.build_or_load()          # cached in experiments/
    df = df.merge(feats, on=['rider_id', 'competition_id'], how='left')

Or build the cache + print sanity diagnostics:
    uv run python -m cycling_project.prediction_tools.experiments.form_feature_lab
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from cycling_project.webscrape_tools.logging_config import get_logger


logger = get_logger(__name__)


HISTORY_START = '2010-01-01'
TARGET_START = '2016-01-01'

# Race-category quality weights for the quality-weighted EMA
CATEGORY_WEIGHTS = {'wt': 1.0, 'pro': 0.65, 'd1': 0.4}

V1_COLS = [
    'v1_form_avg5', 'v1_form_best5', 'v1_form_n5', 'v1_form_delta',
    'v1_form_profile_avg5', 'v1_days_since_race',
]
V2_COLS = [
    'v2_ema_pct_h30', 'v2_ema_pct_h60', 'v2_ema_pct_qw_h60',
    'v2_ema_eff_n_h60', 'v2_ema_bucket_h60',
]
V3_COLS = [
    'v3_season_pct_cur', 'v3_season_pct_prev', 'v3_season_pct_prev2',
    'v3_season_delta', 'v3_season_delta_prev', 'v3_slope365',
    'v3_races365', 'v3_peak_season_pct', 'v3_decline_from_peak',
    'v3_season_races_cur',
]
V4_COLS = [
    'v4_pct_std365', 'v4_pct_spread10',
]
ALL_LAB_COLS = V1_COLS + V2_COLS + V3_COLS + V4_COLS


class FormFeatureLab:
    """Builds the candidate form-feature frame from rider_results."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        cache_dir: str = 'experiments',
        history_start: str = HISTORY_START,
        target_start: str = TARGET_START,
    ):
        if db_path is None:
            db_path = str(
                Path(__file__).parent.parent.parent
                / "webscrape_tools" / "database" / "database" / "cycling_races.db"
            )
        self.db_path = db_path
        self.history_start = history_start
        self.target_start = target_start
        self.cache_path = Path(cache_dir) / 'form_lab_features_v1.csv.gz'

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_results(self) -> pd.DataFrame:
        """All finisher results with dates, percentile, profile, category."""
        conn = sqlite3.connect(self.db_path)
        try:
            df = pd.read_sql_query(
                """
                SELECT
                    rr.rider_id,
                    rr.competition_id,
                    rr.place_bucket,
                    rr.percentile,
                    c.date AS comp_date,
                    c.competition_type,
                    c.race_id,
                    r.year AS race_year,
                    r.category AS race_category,
                    COALESCE(cff.race_dominant_profile, 'unknown') AS profile
                FROM rider_results rr
                JOIN competitions c ON c.id = rr.competition_id
                JOIN races r ON r.id = c.race_id
                LEFT JOIN competition_field_features cff
                    ON cff.competition_id = rr.competition_id
                WHERE c.date IS NOT NULL
                  AND c.date >= ?
                  AND rr.place_bucket IS NOT NULL
                  AND rr.place_bucket != 7
                """,
                conn,
                params=(self.history_start,),
            )
        finally:
            conn.close()

        df['comp_date'] = pd.to_datetime(df['comp_date'])
        df['percentile'] = pd.to_numeric(df['percentile'], errors='coerce')
        # Percentile is occasionally NULL on old rows; reconstruct nothing,
        # just drop those from history (they're rare and pre-date training).
        n_null_pct = int(df['percentile'].isna().sum())
        if n_null_pct:
            logger.info(f"Dropping {n_null_pct} history rows with NULL percentile")
            df = df[df['percentile'].notna()]

        # Race start date per (race_id, race_year) for GC effective dates
        starts = df.groupby(['race_id', 'race_year'])['comp_date'].transform('min')
        df['race_start_date'] = starts

        df['cat_weight'] = df['race_category'].map(CATEGORY_WEIGHTS).fillna(0.4)
        df['season'] = df['comp_date'].dt.year

        df = df.sort_values(['rider_id', 'comp_date', 'competition_id'])
        return df.reset_index(drop=True)

    # ------------------------------------------------------------------
    # Per-rider feature computation
    # ------------------------------------------------------------------

    @staticmethod
    def _rider_features(g: Dict[str, np.ndarray], target_start_day: int) -> List[Dict]:
        """
        Compute all lab features for one rider's chronological results.

        g: dict of aligned numpy arrays for this rider, sorted by date.
        Returns one record per target row (rows on/after target_start_day).
        """
        days = g['days']                  # int days since epoch (comp date)
        eff_days = g['eff_days']          # effective date (race start for GC)
        buckets = g['buckets'].astype(float)
        pct = g['pct']
        catw = g['catw']
        seasons = g['seasons']
        race_keys = g['race_keys']        # (race_id, year) combined int key
        is_gc = g['is_gc']
        profiles = g['profiles']
        comp_ids = g['comp_ids']

        n = len(days)

        # Season aggregates (complete seasons usable for "prev" lookups)
        season_sum: Dict[int, float] = {}
        season_n: Dict[int, int] = {}
        for s in np.unique(seasons):
            mask = seasons == s
            season_sum[int(s)] = float(pct[mask].sum())
            season_n[int(s)] = int(mask.sum())

        records = []
        ln2 = np.log(2.0)

        for i in range(n):
            if days[i] < target_start_day:
                continue

            eff = eff_days[i]
            # History: strictly before effective date
            hi = int(np.searchsorted(days, eff, side='left'))

            rec: Dict = {'competition_id': int(comp_ids[i])}

            if hi == 0:
                # No prior races at all
                rec.update({c: np.nan for c in ALL_LAB_COLS})
                rec['v1_form_n5'] = 0
                rec['v2_ema_eff_n_h60'] = 0.0
                rec['v3_races365'] = 0
                rec['v3_season_races_cur'] = 0
                records.append(rec)
                continue

            # GC same-race exclusion (belt and braces with the date rule)
            if is_gc[i]:
                valid = race_keys[:hi] != race_keys[i]
            else:
                valid = np.ones(hi, dtype=bool)

            h_days = days[:hi][valid]
            h_buckets = buckets[:hi][valid]
            h_pct = pct[:hi][valid]
            h_catw = catw[:hi][valid]
            h_profiles = profiles[:hi][valid]

            # ---------------- v1: fixed-window (90d, cross-year) ----------
            lo90 = np.searchsorted(h_days, eff - 90, side='left')
            w_buckets = h_buckets[lo90:]
            w_profiles = h_profiles[lo90:]
            last5 = w_buckets[-5:]
            if len(last5):
                rec['v1_form_avg5'] = float(last5.mean())
                rec['v1_form_best5'] = float(last5.min())
                rec['v1_form_n5'] = int(len(last5))
                career_avg = float(h_buckets.mean())
                rec['v1_form_delta'] = float(last5.mean() - career_avg)
            else:
                rec['v1_form_avg5'] = np.nan
                rec['v1_form_best5'] = np.nan
                rec['v1_form_n5'] = 0
                rec['v1_form_delta'] = np.nan

            prof_mask = w_profiles == profiles[i]
            # Profile match within the last 5 of the window, as production does
            n_w = len(w_buckets)
            tail_idx = np.arange(max(0, n_w - 5), n_w)
            prof_tail = w_buckets[tail_idx][prof_mask[tail_idx]]
            rec['v1_form_profile_avg5'] = float(prof_tail.mean()) if len(prof_tail) else np.nan

            rec['v1_days_since_race'] = float(min(int(eff - h_days[-1]), 730))

            # ---------------- v2: EMA percentile ---------------------------
            lo365 = np.searchsorted(h_days, eff - 365, side='left')
            e_days = h_days[lo365:]
            e_pct = h_pct[lo365:]
            e_buckets = h_buckets[lo365:]
            e_catw = h_catw[lo365:]
            if len(e_days):
                dt = (eff - e_days).astype(float)
                for hl, col in ((30.0, 'v2_ema_pct_h30'), (60.0, 'v2_ema_pct_h60')):
                    w = np.exp(-ln2 * dt / hl)
                    rec[col] = float((w * e_pct).sum() / w.sum())
                w60 = np.exp(-ln2 * dt / 60.0)
                wq = w60 * e_catw
                rec['v2_ema_pct_qw_h60'] = float((wq * e_pct).sum() / wq.sum())
                rec['v2_ema_eff_n_h60'] = float(w60.sum())
                rec['v2_ema_bucket_h60'] = float((w60 * e_buckets).sum() / w60.sum())
            else:
                rec['v2_ema_pct_h30'] = np.nan
                rec['v2_ema_pct_h60'] = np.nan
                rec['v2_ema_pct_qw_h60'] = np.nan
                rec['v2_ema_eff_n_h60'] = 0.0
                rec['v2_ema_bucket_h60'] = np.nan

            # ---------------- v3: multi-season trajectory ------------------
            season = int(seasons[i])
            # Current season, before effective date (and not same-race for GC)
            season_start_idx = np.searchsorted(h_days, _season_start_day(season), side='left')
            cur_pct = h_pct[season_start_idx:]
            rec['v3_season_races_cur'] = int(len(cur_pct))
            rec['v3_season_pct_cur'] = float(cur_pct.mean()) if len(cur_pct) else np.nan

            prev_n = season_n.get(season - 1, 0)
            prev2_n = season_n.get(season - 2, 0)
            rec['v3_season_pct_prev'] = (
                season_sum[season - 1] / prev_n if prev_n >= 3 else np.nan
            )
            rec['v3_season_pct_prev2'] = (
                season_sum[season - 2] / prev2_n if prev2_n >= 3 else np.nan
            )
            rec['v3_season_delta'] = (
                rec['v3_season_pct_cur'] - rec['v3_season_pct_prev']
                if not np.isnan(rec['v3_season_pct_cur']) and not np.isnan(rec['v3_season_pct_prev'])
                else np.nan
            )
            rec['v3_season_delta_prev'] = (
                rec['v3_season_pct_prev'] - rec['v3_season_pct_prev2']
                if not np.isnan(rec['v3_season_pct_prev']) and not np.isnan(rec['v3_season_pct_prev2'])
                else np.nan
            )

            # Within-365d slope of percentile vs time (pct points per 30 days)
            s_pct = h_pct[lo365:]
            s_days = h_days[lo365:].astype(float)
            rec['v3_races365'] = int(len(s_pct))
            if len(s_pct) >= 5 and s_days.max() > s_days.min():
                xm = s_days - s_days.mean()
                slope = float((xm * (s_pct - s_pct.mean())).sum() / (xm * xm).sum())
                rec['v3_slope365'] = slope * 30.0
            else:
                rec['v3_slope365'] = np.nan

            # Peak completed season (>= 10 races) up to season-1, vs current
            peak = np.nan
            for s, cnt in season_n.items():
                if s < season and cnt >= 10:
                    avg = season_sum[s] / cnt
                    if np.isnan(peak) or avg > peak:
                        peak = avg
            rec['v3_peak_season_pct'] = peak
            rec['v3_decline_from_peak'] = (
                rec['v3_season_pct_cur'] - peak
                if not np.isnan(peak) and not np.isnan(rec['v3_season_pct_cur'])
                else np.nan
            )

            # ---------------- v4: volatility -------------------------------
            if len(s_pct) >= 3:
                rec['v4_pct_std365'] = float(s_pct.std(ddof=1))
            else:
                rec['v4_pct_std365'] = np.nan
            last10 = h_pct[-10:]
            in365 = h_days[-10:] >= eff - 365
            last10 = last10[in365]
            if len(last10) >= 3:
                rec['v4_pct_spread10'] = float(last10.max() - np.median(last10))
            else:
                rec['v4_pct_spread10'] = np.nan

            records.append(rec)

        return records

    # ------------------------------------------------------------------
    # Build / cache
    # ------------------------------------------------------------------

    def build(self) -> pd.DataFrame:
        started = datetime.now()
        print(f"Loading results from {self.history_start}...", flush=True)
        df = self._load_results()
        print(f"  {len(df):,} finisher rows, {df['rider_id'].nunique():,} riders", flush=True)

        epoch = pd.Timestamp('1970-01-01')
        df['days'] = (df['comp_date'] - epoch).dt.days.astype(np.int64)
        df['eff_days'] = np.where(
            df['competition_type'] == 'gc',
            (df['race_start_date'] - epoch).dt.days.astype(np.int64),
            df['days'],
        )
        # Combined (race_id, year) key for same-race exclusion
        df['race_key'] = df['race_id'].astype(np.int64) * 10000 + df['race_year'].astype(np.int64)
        df['is_gc'] = (df['competition_type'] == 'gc').values

        # Profile as small int codes for fast comparison
        prof_codes, _ = pd.factorize(df['profile'])
        df['prof_code'] = prof_codes

        target_start_day = (pd.Timestamp(self.target_start) - epoch).days

        all_records: List[Dict] = []
        rider_ids = df['rider_id'].values
        boundaries = np.flatnonzero(np.diff(rider_ids)) + 1
        starts = np.concatenate([[0], boundaries])
        ends = np.concatenate([boundaries, [len(df)]])

        cols = {
            'days': df['days'].values,
            'eff_days': df['eff_days'].values,
            'buckets': df['place_bucket'].values,
            'pct': df['percentile'].values.astype(float),
            'catw': df['cat_weight'].values.astype(float),
            'seasons': df['season'].values,
            'race_keys': df['race_key'].values,
            'is_gc': df['is_gc'].values,
            'profiles': df['prof_code'].values,
            'comp_ids': df['competition_id'].values,
        }

        n_riders = len(starts)
        for ri, (s, e) in enumerate(zip(starts, ends)):
            g = {k: v[s:e] for k, v in cols.items()}
            recs = self._rider_features(g, target_start_day)
            if recs:
                rid = int(rider_ids[s])
                for r in recs:
                    r['rider_id'] = rid
                all_records.extend(recs)
            if (ri + 1) % 2000 == 0:
                print(f"  riders {ri + 1:,}/{n_riders:,}  ({len(all_records):,} records)", flush=True)

        feats = pd.DataFrame(all_records)
        feats = feats[['rider_id', 'competition_id'] + ALL_LAB_COLS]

        elapsed = (datetime.now() - started).total_seconds()
        print(f"Built {len(feats):,} feature rows in {elapsed:.0f}s", flush=True)

        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        feats.to_csv(self.cache_path, index=False, compression='gzip')
        print(f"Cached to {self.cache_path}", flush=True)
        return feats

    def build_or_load(self) -> pd.DataFrame:
        if self.cache_path.exists():
            print(f"Loading cached lab features from {self.cache_path}", flush=True)
            return pd.read_csv(self.cache_path)
        return self.build()


_SEASON_START_CACHE: Dict[int, int] = {}


def _season_start_day(season: int) -> int:
    if season not in _SEASON_START_CACHE:
        _SEASON_START_CACHE[season] = (
            pd.Timestamp(f'{season}-01-01') - pd.Timestamp('1970-01-01')
        ).days
    return _SEASON_START_CACHE[season]


# ---------------------------------------------------------------------------
# Sanity diagnostics
# ---------------------------------------------------------------------------

def _sanity(feats: pd.DataFrame, db_path: str):
    """Coverage + signal sanity checks against subsequent performance."""
    conn = sqlite3.connect(db_path)
    try:
        meta = pd.read_sql_query(
            """
            SELECT rr.competition_id, rr.rider_id, rr.place_bucket, rr.percentile,
                   rr.rider_age AS age, c.date AS comp_date
            FROM rider_results rr JOIN competitions c ON c.id = rr.competition_id
            WHERE c.date >= '2016-01-01'
            """,
            conn,
        )
    finally:
        conn.close()
    meta['comp_date'] = pd.to_datetime(meta['comp_date'])

    m = feats.merge(meta, on=['rider_id', 'competition_id'], how='inner')
    m['month'] = m['comp_date'].dt.month

    print("\n" + "=" * 78)
    print("SANITY — coverage and signal")
    print("=" * 78)

    jan = m[m['month'] == 1]
    print(f"\nJanuary rows: {len(jan):,}")
    print(f"  v1 window non-empty:        {(jan['v1_form_n5'] > 0).mean():.1%}  "
          f"(old same-year window was ~66%)")
    print(f"  v2 EMA available (365d):    {jan['v2_ema_pct_h60'].notna().mean():.1%}")
    print(f"  v3 prev-season available:   {jan['v3_season_pct_prev'].notna().mean():.1%}")

    print("\nOverall coverage (non-NaN):")
    for c in ALL_LAB_COLS:
        print(f"  {c:<28s} {m[c].notna().mean():>6.1%}")

    print("\nSpearman corr with same-race percentile (higher pct = better):")
    for c in ['v2_ema_pct_h30', 'v2_ema_pct_h60', 'v2_ema_pct_qw_h60',
              'v3_season_pct_cur', 'v3_season_delta', 'v3_slope365',
              'v3_decline_from_peak', 'v1_form_avg5']:
        sub = m[[c, 'percentile']].dropna()
        if len(sub) > 1000:
            rho = sub[c].corr(sub['percentile'], method='spearman')
            print(f"  {c:<28s} {rho:>+7.3f}  (n={len(sub):,})")

    print("\nAge-band means (34+ decline visibility), 2021+ rows:")
    recent = m[m['comp_date'] >= '2021-01-01'].copy()
    age = pd.to_numeric(recent['age'], errors='coerce')
    recent['band'] = pd.cut(age.where(age > 0), bins=[0, 30, 34, 200],
                            labels=['<30', '30-33', '34+'], right=False)
    tbl = recent.groupby('band', observed=True)[
        ['v3_season_delta', 'v3_decline_from_peak', 'v3_slope365', 'v2_ema_pct_h60']
    ].mean()
    print(tbl.round(2).to_string())


def main():
    lab = FormFeatureLab()
    feats = lab.build_or_load()
    _sanity(feats, lab.db_path)


if __name__ == '__main__':
    main()
