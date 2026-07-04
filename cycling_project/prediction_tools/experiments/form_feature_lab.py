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
  v5 — contested-rows-only EMA ("form when it mattered"): percentile EMA
       over rows where the rider appeared in >=1 informative comparison
       (contested_rating pair rules: sprint order in the first 10 of the
       winner's group + adjacent group-vs-group). GT coasting days drop out.
  v6 — comp-type-scoped EMA: percentile EMA over gc + one_day rows only
       (stage rows excluded) — a GC row counts as one clean observation.

NOTE (2026-07): the v2/v3 blocks were productionized on 2026-06-10 under the
SAME column names — the production training frame now carries them natively.
Merging lab V2/V3 onto that frame would collide, so sweeps must merge only
MERGEABLE_LAB_COLS (v1/v4/v5/v6).

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
# v5/v6 names deliberately avoid the 'avg_bucket' / '_count' imputation
# patterns; NaN = no qualifying history, never imputed.
V5_COLS = [
    'v5_cont_ema_pct_h30', 'v5_cont_ema_pct_h60', 'v5_cont_ema_eff_n_h60',
    'v5_cont_season_pct_cur',
]
V6_COLS = [
    'v6_scoped_ema_pct_h30', 'v6_scoped_ema_pct_h60', 'v6_scoped_ema_eff_n_h60',
    'v6_scoped_season_delta',
]
ALL_LAB_COLS = V1_COLS + V2_COLS + V3_COLS + V4_COLS + V5_COLS + V6_COLS
# Safe to merge onto the current production frame (V2/V3 shipped to
# production 2026-06-10 under identical names — they'd collide).
MERGEABLE_LAB_COLS = V1_COLS + V4_COLS + V5_COLS + V6_COLS

# Combined (rider_id, competition_id) int64 key for the contested-flag join.
RIDER_COMP_KEY_MULT = 10_000_000


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
        self.cache_path = Path(cache_dir) / 'form_lab_features_v2.csv.gz'
        # In-memory history state for features_for_targets (built lazily)
        self._hist_df: Optional[pd.DataFrame] = None
        self._hist_cols: Optional[Dict[str, np.ndarray]] = None
        self._hist_spans: Optional[Dict[int, tuple]] = None
        self._prof_map: Optional[Dict[str, int]] = None

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

        # v5/v6 history masks
        contested_keys = self._contested_keys()
        row_keys = (
            df['rider_id'].to_numpy(np.int64) * RIDER_COMP_KEY_MULT
            + df['competition_id'].to_numpy(np.int64)
        )
        df['contested'] = np.isin(row_keys, contested_keys)
        df['scoped'] = df['competition_type'].isin(('gc', 'one_day')).values
        logger.info(
            "History masks: contested %.1f%%, scoped %.1f%% of rows",
            100 * df['contested'].mean(), 100 * df['scoped'].mean(),
        )

        df = df.sort_values(['rider_id', 'comp_date', 'competition_id'])
        return df.reset_index(drop=True)

    def _contested_keys(self) -> np.ndarray:
        """Sorted combined keys of (rider, comp) with >=1 informative comparison.

        Derived directly from the DB with the contested-Elo pair rules
        (contested_rating._competition_pairs) — no dependency on the rating
        snapshot artifact's freshness. one_day + stage comps only (gc rows
        are never contested by construction).
        """
        from cycling_project.prediction_tools.contested_rating import (
            ContestedRatingConfig,
            _competition_pairs,
            load_contested_results,
        )
        from cycling_project.prediction_tools.contest_signature_features import (
            group_sizes_from_gaps,
        )

        cfg = ContestedRatingConfig(
            start_date=self.history_start, db_path=Path(self.db_path)
        )
        results = load_contested_results(cfg)
        parts: List[np.ndarray] = []
        for comp_id, sub in results.groupby('competition_id', sort=False):
            gaps = sub['time_gap'].to_numpy(dtype=float)
            sizes = group_sizes_from_gaps(gaps)
            w, l = _competition_pairs(sizes, cfg.winner_group_top_n, cfg.group_cap)
            if len(w) == 0:
                continue
            rid = sub['rider_id'].to_numpy(np.int64)
            idx = np.unique(np.concatenate([w, l]))
            parts.append(rid[idx] * RIDER_COMP_KEY_MULT + int(comp_id))
        keys = np.sort(np.concatenate(parts)) if parts else np.empty(0, dtype=np.int64)
        logger.info("Contested keys: %d (rider, comp) pairs", len(keys))
        return keys

    # ------------------------------------------------------------------
    # Per-rider feature computation
    # ------------------------------------------------------------------

    @staticmethod
    def _rider_features(
        hist: Dict[str, np.ndarray], targets: Dict[str, np.ndarray]
    ) -> List[Dict]:
        """
        Compute all lab features for one rider.

        hist: dict of aligned numpy arrays of the rider's finisher results,
              sorted by date (days, buckets, pct, catw, seasons, race_keys,
              profiles, contested, scoped).
        targets: dict of aligned arrays of the rows to compute features FOR
              (eff_days, seasons, race_keys, is_gc, profiles, comp_ids).
              Targets need not be rows of hist (e.g. DNF'd starters).
        Returns one record per target row.
        """
        days = hist['days']               # int days since epoch (comp date)
        buckets = hist['buckets'].astype(float)
        pct = hist['pct']
        catw = hist['catw']
        seasons = hist['seasons']
        race_keys = hist['race_keys']     # (race_id, year) combined int key
        profiles = hist['profiles']
        contested = hist['contested']
        scoped = hist['scoped']

        t_eff_days = targets['eff_days']  # effective date (race start for GC)
        t_seasons = targets['seasons']
        t_race_keys = targets['race_keys']
        t_is_gc = targets['is_gc']
        t_profiles = targets['profiles']
        t_comp_ids = targets['comp_ids']

        # Season aggregates (complete seasons usable for "prev" lookups)
        season_sum: Dict[int, float] = {}
        season_n: Dict[int, int] = {}
        scoped_season_sum: Dict[int, float] = {}
        scoped_season_n: Dict[int, int] = {}
        for s in np.unique(seasons):
            mask = seasons == s
            season_sum[int(s)] = float(pct[mask].sum())
            season_n[int(s)] = int(mask.sum())
            smask = mask & scoped
            scoped_season_sum[int(s)] = float(pct[smask].sum())
            scoped_season_n[int(s)] = int(smask.sum())

        records = []
        ln2 = np.log(2.0)

        for i in range(len(t_comp_ids)):
            eff = t_eff_days[i]
            # History: strictly before effective date
            hi = int(np.searchsorted(days, eff, side='left'))

            rec: Dict = {'competition_id': int(t_comp_ids[i])}

            # GC same-race exclusion (belt and braces with the date rule)
            if hi > 0 and t_is_gc[i]:
                valid = race_keys[:hi] != t_race_keys[i]
            else:
                valid = np.ones(hi, dtype=bool)

            h_days = days[:hi][valid]

            if len(h_days) == 0:
                # No prior races at all
                rec.update({c: np.nan for c in ALL_LAB_COLS})
                rec['v1_form_n5'] = 0
                rec['v2_ema_eff_n_h60'] = 0.0
                rec['v3_races365'] = 0
                rec['v3_season_races_cur'] = 0
                rec['v5_cont_ema_eff_n_h60'] = 0.0
                rec['v6_scoped_ema_eff_n_h60'] = 0.0
                records.append(rec)
                continue

            h_buckets = buckets[:hi][valid]
            h_pct = pct[:hi][valid]
            h_catw = catw[:hi][valid]
            h_profiles = profiles[:hi][valid]
            h_contested = contested[:hi][valid]
            h_scoped = scoped[:hi][valid]

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

            prof_mask = w_profiles == t_profiles[i]
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
            season = int(t_seasons[i])
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

            # ---------------- v5: contested-rows-only EMA ------------------
            c_days = h_days[h_contested]
            c_pct = h_pct[h_contested]
            lo_c = np.searchsorted(c_days, eff - 365, side='left')
            cd = c_days[lo_c:]
            cp = c_pct[lo_c:]
            if len(cd):
                dt = (eff - cd).astype(float)
                w30 = np.exp(-ln2 * dt / 30.0)
                w60 = np.exp(-ln2 * dt / 60.0)
                rec['v5_cont_ema_pct_h30'] = float((w30 * cp).sum() / w30.sum())
                rec['v5_cont_ema_pct_h60'] = float((w60 * cp).sum() / w60.sum())
                rec['v5_cont_ema_eff_n_h60'] = float(w60.sum())
            else:
                rec['v5_cont_ema_pct_h30'] = np.nan
                rec['v5_cont_ema_pct_h60'] = np.nan
                rec['v5_cont_ema_eff_n_h60'] = 0.0
            cs_c = np.searchsorted(c_days, _season_start_day(season), side='left')
            cur_c = c_pct[cs_c:]
            rec['v5_cont_season_pct_cur'] = (
                float(cur_c.mean()) if len(cur_c) else np.nan
            )

            # ---------------- v6: comp-type-scoped EMA (gc + one_day) ------
            sc_days = h_days[h_scoped]
            sc_pct = h_pct[h_scoped]
            lo_s = np.searchsorted(sc_days, eff - 365, side='left')
            sd = sc_days[lo_s:]
            sp = sc_pct[lo_s:]
            if len(sd):
                dt = (eff - sd).astype(float)
                w30 = np.exp(-ln2 * dt / 30.0)
                w60 = np.exp(-ln2 * dt / 60.0)
                rec['v6_scoped_ema_pct_h30'] = float((w30 * sp).sum() / w30.sum())
                rec['v6_scoped_ema_pct_h60'] = float((w60 * sp).sum() / w60.sum())
                rec['v6_scoped_ema_eff_n_h60'] = float(w60.sum())
            else:
                rec['v6_scoped_ema_pct_h30'] = np.nan
                rec['v6_scoped_ema_pct_h60'] = np.nan
                rec['v6_scoped_ema_eff_n_h60'] = 0.0
            cs_s = np.searchsorted(sc_days, _season_start_day(season), side='left')
            cur_s = sc_pct[cs_s:]
            cur_s_mean = float(cur_s.mean()) if len(cur_s) else np.nan
            prev_s_n = scoped_season_n.get(season - 1, 0)
            prev_s_mean = (
                scoped_season_sum[season - 1] / prev_s_n if prev_s_n >= 3 else np.nan
            )
            rec['v6_scoped_season_delta'] = (
                cur_s_mean - prev_s_mean
                if not np.isnan(cur_s_mean) and not np.isnan(prev_s_mean)
                else np.nan
            )

            records.append(rec)

        return records

    # ------------------------------------------------------------------
    # Build / cache
    # ------------------------------------------------------------------

    HIST_KEYS = ('days', 'buckets', 'pct', 'catw', 'seasons', 'race_keys',
                 'profiles', 'contested', 'scoped')
    TARGET_KEYS = ('eff_days', 'seasons', 'race_keys', 'is_gc', 'profiles',
                   'comp_ids')

    def _prepare_hist(self) -> None:
        """Load results once and precompute per-rider array spans."""
        if self._hist_cols is not None:
            return
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
        prof_codes, prof_uniques = pd.factorize(df['profile'])
        df['prof_code'] = prof_codes
        self._prof_map = {p: i for i, p in enumerate(prof_uniques)}

        rider_ids = df['rider_id'].values
        boundaries = np.flatnonzero(np.diff(rider_ids)) + 1
        starts = np.concatenate([[0], boundaries])
        ends = np.concatenate([boundaries, [len(df)]])
        self._hist_spans = {
            int(rider_ids[s]): (int(s), int(e)) for s, e in zip(starts, ends)
        }
        self._hist_cols = {
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
            'contested': df['contested'].values,
            'scoped': df['scoped'].values,
        }
        self._hist_df = df

    def build(self) -> pd.DataFrame:
        started = datetime.now()
        self._prepare_hist()
        cols = self._hist_cols
        epoch = pd.Timestamp('1970-01-01')
        target_start_day = (pd.Timestamp(self.target_start) - epoch).days

        all_records: List[Dict] = []
        n_riders = len(self._hist_spans)
        for ri, (rid, (s, e)) in enumerate(self._hist_spans.items()):
            hist = {k: cols[k][s:e] for k in self.HIST_KEYS}
            tmask = cols['days'][s:e] >= target_start_day
            if not tmask.any():
                continue
            targets = {k: cols[k][s:e][tmask] for k in self.TARGET_KEYS}
            recs = self._rider_features(hist, targets)
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

    # ------------------------------------------------------------------
    # Features for arbitrary targets (e.g. DNF'd starters in honest pools)
    # ------------------------------------------------------------------

    def features_for_targets(self, targets_df: pd.DataFrame) -> pd.DataFrame:
        """Lab features for arbitrary (rider_id, competition_id) target keys.

        For rows that are NOT in rider_results (e.g. DNF'd starters scored in
        the honest DNF-inclusive pool). History = the rider's finisher rows
        strictly before the target's effective date — identical discipline to
        build() (GC targets keyed to race start date, same-edition excluded).
        Riders with no finisher history get all-NaN features (eff_n = 0).
        """
        self._prepare_hist()
        epoch = pd.Timestamp('1970-01-01')

        keys = targets_df[['rider_id', 'competition_id']].drop_duplicates().copy()
        comp_ids = keys['competition_id'].unique().tolist()

        conn = sqlite3.connect(self.db_path)
        try:
            placeholders = ','.join('?' * len(comp_ids))
            meta = pd.read_sql_query(
                f"""
                SELECT
                    c.id AS competition_id,
                    c.date AS comp_date,
                    c.competition_type,
                    c.race_id,
                    r.year AS race_year,
                    COALESCE(cff.race_dominant_profile, 'unknown') AS profile,
                    (SELECT MIN(c2.date) FROM competitions c2
                     WHERE c2.race_id = c.race_id AND c2.date IS NOT NULL
                    ) AS race_start_date
                FROM competitions c
                JOIN races r ON r.id = c.race_id
                LEFT JOIN competition_field_features cff
                    ON cff.competition_id = c.id
                WHERE c.id IN ({placeholders})
                """,
                conn,
                params=comp_ids,
            )
        finally:
            conn.close()

        meta['comp_date'] = pd.to_datetime(meta['comp_date'])
        meta['race_start_date'] = pd.to_datetime(meta['race_start_date'])
        t = keys.merge(meta, on='competition_id', how='left')
        missing_meta = t['comp_date'].isna()
        if missing_meta.any():
            logger.warning(
                "features_for_targets: dropping %d keys with no competition date",
                int(missing_meta.sum()),
            )
            t = t[~missing_meta]

        days = (t['comp_date'] - epoch).dt.days.astype(np.int64)
        start_days = (t['race_start_date'] - epoch).dt.days
        t['eff_days'] = np.where(
            (t['competition_type'] == 'gc') & start_days.notna(),
            start_days.fillna(0).astype(np.int64),
            days,
        )
        t['seasons'] = t['comp_date'].dt.year.astype(np.int64)
        t['race_keys'] = (
            t['race_id'].astype(np.int64) * 10000 + t['race_year'].astype(np.int64)
        )
        t['is_gc'] = (t['competition_type'] == 'gc').values
        t['profiles'] = t['profile'].map(self._prof_map).fillna(-1).astype(np.int64)
        t['comp_ids'] = t['competition_id'].astype(np.int64)

        cols = self._hist_cols
        empty_hist = {
            k: cols[k][:0] for k in self.HIST_KEYS
        }
        all_records: List[Dict] = []
        for rid, g in t.groupby('rider_id'):
            span = self._hist_spans.get(int(rid))
            hist = (
                {k: cols[k][span[0]:span[1]] for k in self.HIST_KEYS}
                if span is not None else empty_hist
            )
            targets = {k: g[k].to_numpy() for k in self.TARGET_KEYS}
            recs = self._rider_features(hist, targets)
            for r in recs:
                r['rider_id'] = int(rid)
            all_records.extend(recs)

        if not all_records:
            return pd.DataFrame(columns=['rider_id', 'competition_id'] + ALL_LAB_COLS)
        feats = pd.DataFrame(all_records)
        return feats[['rider_id', 'competition_id'] + ALL_LAB_COLS]


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
              'v3_decline_from_peak', 'v1_form_avg5',
              'v5_cont_ema_pct_h60', 'v5_cont_ema_pct_h30',
              'v5_cont_season_pct_cur',
              'v6_scoped_ema_pct_h60', 'v6_scoped_ema_pct_h30',
              'v6_scoped_season_delta']:
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
