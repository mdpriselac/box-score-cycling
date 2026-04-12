"""
Stage 1 — one-day race clustering via type-profile rider signatures.

This is a refocused rewrite. The earlier gradient-history version died because
every starter's "career gradient signature" was polluted by stage-race mixture
(a single Tour rider pools 21 stages per year across 5+ race shapes), so the
field aggregate collapsed across race types. See `experiment_log.md` for the
diagnostic walkthrough.

The new architecture:

  1. **Scope**: one-day races only. The GMM fits on one-day competitions, the
     clusters are written only for one-day rows. Stage races and GC
     classifications keep their Stage 0 features unchanged.
  2. **Rider signature**: 12 dims, 4 distribution stats per race category:

         [stage_avg, stage_std, stage_best, log1p(stage_count),
          one_day_avg, one_day_std, one_day_best, log1p(one_day_count),
          gc_avg, gc_std, gc_best, log1p(gc_count)]

     Built chronologically from `rider_results` via a single pass that walks
     every competition (stage/one_day/gc) in date order, maintains per-rider
     per-category running state (n, sum, sum_sq, min), and snapshots the
     signature BEFORE each one-day race. Leakage-safe by construction.

     Imputation for riders with zero category experience:
     ``(avg=5.0, std=1.5, best=7.0, log_count=0.0)``. best=7 is a deliberate
     sentinel outside the observed 0..6 range so "never placed in this
     category" is its own mode.

  3. **Field aggregate**: uniform-weighted mean / std / p25 / p75 across the
     starters that have a qualifying signature in at least one category.
     12 sig dims x 4 stats = 48 field dims per one-day race.

     Uniform weighting (no 1/(stage_avg_bucket+1) outer weight) is deliberate:
     the previous quality-weighted version made every elite-heavy field look
     identical regardless of race type. The type-profile signature already
     encodes quality via the bucket stats, so extra quality weighting is
     both redundant and collapse-inducing.

  4. **Joint vector**: 11 race-side gradient columns (Stage 0) + 48 field-side
     type-profile aggregates = 59 dims total.

  5. **PCA-before-GMM**: fit per fold on training-fold one-days, compress to
     10 components. Then fit a diagonal-covariance GMM on the PCA output
     with k in [6, 10], BIC-selected subject to cluster-size constraints
     (each cluster must be between 3% and 20% of the training fold).

Two variants are produced in one pass:

  - ``race_only`` : GMM on just the 11 race-side gradient columns.
  - ``joint``     : GMM on the 59-dim joint vector (race + field type-profile).

Both are written to ``race_cluster_v1_scores`` with a ``variant`` column.

Leakage discipline — three channels blocked:
  1. Intra-race (race T excluded from its own rider signatures).
  2. Chronological rider state (pre-race snapshots, then update).
  3. Cross-fold (scaler, PCA, and GMM all refit per fold on training-fold
     one-days only).

Usage:
    python -m cycling_project.prediction_tools.experiments.stage1_race_clustering \
        --db /path/to/cycling_races.db [--dry-run] [--variants race_only,joint]
"""

from __future__ import annotations

import argparse
import sqlite3
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from sklearn.decomposition import PCA
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GRADIENT_COLS: List[str] = [
    'variance_normalized_slope',
    'variance_normalized_volatility',
    'variance_normalized_monotonicity',
    'clumpiness_score_slope',
    'clumpiness_score_volatility',
    'biggest_group_metric_slope',
    'biggest_group_metric_volatility',
    'selection_metric_slope',
    'selection_metric_volatility',
    'gini_coefficient_slope',
    'skewness_normalized_slope',
]
N_GRAD = len(GRADIENT_COLS)  # 11

# Rider signature layout: 4 stats (avg/std/best/log_count) x 3 categories.
CATEGORIES: List[str] = ['stage', 'one_day', 'gc']
N_CATS = len(CATEGORIES)
N_SIG_PER_CAT = 4  # avg, std, best, log_count
N_SIG = N_CATS * N_SIG_PER_CAT  # 12

# Field aggregate: 4 distribution stats across starters per signature dim.
N_FIELD_STATS = 4  # mean, std, p25, p75
N_FIELD = N_SIG * N_FIELD_STATS  # 48
N_JOINT = N_GRAD + N_FIELD  # 59

DEFAULT_FOLDS: List[Dict[str, str]] = [
    {'train_end': '2021-12-31', 'label': '2023'},
    {'train_end': '2022-12-31', 'label': '2024'},
    {'train_end': '2023-12-31', 'label': '2025'},
]

MAX_CLUSTERS = 12  # table schema upper bound

# Signature imputation for riders with zero category experience.
IMPUTE_AVG = 5.0   # mid-field default
IMPUTE_STD = 1.5   # typical spread
IMPUTE_BEST = 7.0  # sentinel outside 0..6 range, flags "never placed"
IMPUTE_LOG_COUNT = 0.0

# Field aggregation: minimum qualifying starters per one-day race.
# A "qualifying" starter is one with >=1 prior finish in ANY category, so
# their imputed signature isn't the uniform default.
MIN_STARTERS = 20
MIN_PRIOR_ANY = 3  # at least this many prior finishes across all categories

# GMM search.
K_MIN = 6
K_MAX_RACE_ONLY = 10
K_MAX_JOINT = 8  # tighter param budget under split-and-concat (11 race + 5 field_pc = 16 dims)
MIN_CLUSTER_PCT = 0.03
MAX_CLUSTER_PCT = 0.20
GMM_RANDOM_STATE = 42

# Joint variant: how many PCs to keep for the field side. The field block is
# 48 dims but effective rank is ~13; 5 captures most of the type-profile
# structure while giving race-side features (11 dims, untouched) a 2:1
# budget advantage in the GMM's input space.
JOINT_FIELD_PCS = 5

# Canonical races, by sub-type, for the sanity check.
CANONICAL_RACES: List[Tuple[str, List[str]]] = [
    ('Paris-Roubaix (cobbles)',     ['roubaix']),
    ('Tour of Flanders (cobbles)',  ['flanders', 'ronde van']),
    ('Strade Bianche (gravel)',     ['strade']),
    ('Milan-San Remo (sprint-break)', ['milano-sanremo', 'milan-san', 'milan - san']),
    ('Liège-Bastogne-Liège (climber)', ['liege-bastogne', 'liège-bastogne', 'bastogne']),
    ('Il Lombardia (climber)',      ['lombardia', 'lombardy', 'giro di lombardia']),
    ('La Flèche Wallonne (climber)', ['fleche wallonne', 'flèche wallonne', 'waalse']),
    ('Amstel Gold (hilly)',         ['amstel gold']),
    ('Gent-Wevelgem (semi-classic)', ['gent-wevelgem', 'ghent-wevelgem', 'gent - wevelgem']),
    ('Scheldeprijs (bunch sprint)', ['scheldeprijs']),
]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


@dataclass
class LoadedData:
    one_day_df: pd.DataFrame        # one-day comps with gradients (11 cols)
    order_df: pd.DataFrame          # ALL comps for chronological iteration
    one_day_startlists: pd.DataFrame  # startlists for one-day comps only
    results_df: pd.DataFrame        # place_bucket 0..6 across ALL comps


def _chunked_in(
    conn: sqlite3.Connection,
    base_sql: str,
    id_list: Sequence[int],
) -> pd.DataFrame:
    chunks = []
    for i in range(0, len(id_list), 900):
        batch = id_list[i:i + 900]
        placeholders = ','.join('?' * len(batch))
        sql = base_sql.format(placeholders=placeholders)
        chunks.append(pd.read_sql_query(sql, conn, params=list(batch)))
    return pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()


def load_from_db(conn: sqlite3.Connection, start_date: str = '2018-01-01') -> LoadedData:
    """Load one-day competitions with gradients, a chronological index over
    ALL competitions (for updating rider state), one-day startlists, and
    per-rider results across all categories.
    """
    grad_cols_sql = ', '.join(f'rfg.{c}' for c in GRADIENT_COLS)

    # One-day comps with gradients — this is what we cluster.
    one_day_df = pd.read_sql_query(
        f"""
        SELECT
            cff.competition_id, cff.competition_name, cff.competition_date,
            {grad_cols_sql}
        FROM competition_field_features cff
        JOIN race_feature_gradients rfg ON rfg.competition_id = cff.competition_id
        WHERE cff.competition_date >= ?
          AND cff.competition_type = 'one_day'
          AND cff.race_category IN ('wt','pro','d1')
          AND rfg.variance_normalized_slope IS NOT NULL
          AND rfg.clumpiness_score_slope IS NOT NULL
          AND rfg.biggest_group_metric_slope IS NOT NULL
        ORDER BY cff.competition_date, cff.competition_id
        """,
        conn,
        params=[start_date],
    )
    one_day_df['competition_date'] = pd.to_datetime(one_day_df['competition_date'])

    # Chronological index: every competition with a place_bucket result (any
    # type), ordered by date. Used to update rider state.
    order_df = pd.read_sql_query(
        """
        SELECT DISTINCT
            cff.competition_id, cff.competition_type, cff.competition_date
        FROM competition_field_features cff
        WHERE cff.competition_date >= ?
          AND cff.competition_type IN ('stage','one_day','gc')
          AND cff.race_category IN ('wt','pro','d1')
        ORDER BY cff.competition_date, cff.competition_id
        """,
        conn,
        params=[start_date],
    )
    order_df['competition_date'] = pd.to_datetime(order_df['competition_date'])

    all_comp_ids = tuple(int(x) for x in order_df['competition_id'].tolist())
    if not all_comp_ids:
        raise RuntimeError('No competitions loaded — check start_date filter.')

    one_day_ids = tuple(int(x) for x in one_day_df['competition_id'].tolist())

    one_day_startlists = _chunked_in(
        conn,
        """
        SELECT competition_id, rider_id
        FROM rider_competition_snapshots
        WHERE competition_id IN ({placeholders})
        """,
        one_day_ids,
    )

    results_df = _chunked_in(
        conn,
        """
        SELECT competition_id, rider_id, place_bucket
        FROM rider_results
        WHERE competition_id IN ({placeholders})
          AND place_bucket IS NOT NULL
          AND place_bucket < 7
        """,
        all_comp_ids,
    )

    return LoadedData(
        one_day_df=one_day_df,
        order_df=order_df,
        one_day_startlists=one_day_startlists,
        results_df=results_df,
    )


# ---------------------------------------------------------------------------
# Rider type-profile signatures — chronological pass
# ---------------------------------------------------------------------------


def compute_rider_type_signatures(
    order_df: pd.DataFrame,
    one_day_startlists: pd.DataFrame,
    results_df: pd.DataFrame,
) -> Dict[int, Dict[int, np.ndarray]]:
    """Walk every competition in chronological order, maintaining per-rider
    per-category running state (n, sum, sum_sq, min). Snapshot the 12-dim
    type-profile signature BEFORE processing each one-day race, then update
    the state from the race's results (any category contributes to its own
    per-category bucket).

    Returns ``signatures[one_day_comp_id][rider_id] -> ndarray(12)``.
    Only riders with at least ``MIN_PRIOR_ANY`` prior finishes across all
    categories get a non-default signature — everyone else is absent from
    the snapshot and will be dropped from field aggregation.
    """
    order_sorted = order_df.sort_values(
        ['competition_date', 'competition_id'], kind='stable'
    ).reset_index(drop=True)

    comp_type_by_id: Dict[int, str] = {
        int(cid): str(ctype)
        for cid, ctype in zip(
            order_sorted['competition_id'], order_sorted['competition_type']
        )
    }

    one_day_id_set = {
        int(x) for x in order_sorted.loc[
            order_sorted['competition_type'] == 'one_day', 'competition_id'
        ].tolist()
    }

    starters_by_comp: Dict[int, List[int]] = (
        one_day_startlists.groupby('competition_id', sort=False)['rider_id']
        .apply(lambda s: [int(x) for x in s.tolist()])
        .to_dict()
    )

    # results grouped by (comp_id, rider_id) -> place_bucket
    results_by_comp: Dict[int, List[Tuple[int, int]]] = {}
    for comp_id, rider_id, pb in results_df.itertuples(index=False):
        results_by_comp.setdefault(int(comp_id), []).append(
            (int(rider_id), int(pb))
        )

    # Per-rider running state: 4 stats x 3 categories.
    # n[cat]: int, sum[cat]: float, sum_sq[cat]: float, min[cat]: int (7 means unset)
    n_state: Dict[int, np.ndarray] = {}
    sum_state: Dict[int, np.ndarray] = {}
    sumsq_state: Dict[int, np.ndarray] = {}
    min_state: Dict[int, np.ndarray] = {}

    def _ensure(rider_id: int) -> None:
        if rider_id not in n_state:
            n_state[rider_id] = np.zeros(N_CATS, dtype=np.int64)
            sum_state[rider_id] = np.zeros(N_CATS, dtype=np.float64)
            sumsq_state[rider_id] = np.zeros(N_CATS, dtype=np.float64)
            min_state[rider_id] = np.full(N_CATS, IMPUTE_BEST, dtype=np.float64)

    cat_to_idx = {cat: i for i, cat in enumerate(CATEGORIES)}

    snapshots: Dict[int, Dict[int, np.ndarray]] = {}

    t0 = time.time()
    n_comps_seen = 0
    n_snaps_written = 0

    for row in order_sorted.itertuples(index=False):
        comp_id = int(row.competition_id)
        comp_type = comp_type_by_id.get(comp_id)
        if comp_type is None:
            continue
        n_comps_seen += 1

        # 1. Snapshot if this is a one-day race
        if comp_id in one_day_id_set:
            comp_snap: Dict[int, np.ndarray] = {}
            for rider_id in starters_by_comp.get(comp_id, ()):
                if rider_id not in n_state:
                    continue
                n_vec = n_state[rider_id]
                total_prior = int(n_vec.sum())
                if total_prior < MIN_PRIOR_ANY:
                    continue

                # Build the 12-dim signature. For categories with 0 prior
                # finishes, fall back to imputation defaults.
                sig = np.empty(N_SIG, dtype=np.float64)
                for c_idx in range(N_CATS):
                    base = c_idx * N_SIG_PER_CAT
                    n_c = int(n_vec[c_idx])
                    if n_c == 0:
                        sig[base + 0] = IMPUTE_AVG
                        sig[base + 1] = IMPUTE_STD
                        sig[base + 2] = IMPUTE_BEST
                        sig[base + 3] = IMPUTE_LOG_COUNT
                    else:
                        s = sum_state[rider_id][c_idx]
                        ss = sumsq_state[rider_id][c_idx]
                        avg = s / n_c
                        var = ss / n_c - avg * avg
                        if var < 0.0:
                            var = 0.0
                        std = float(np.sqrt(var)) if n_c >= 2 else IMPUTE_STD
                        best = float(min_state[rider_id][c_idx])
                        sig[base + 0] = avg
                        sig[base + 1] = std
                        sig[base + 2] = best
                        sig[base + 3] = float(np.log1p(n_c))
                comp_snap[rider_id] = sig
            snapshots[comp_id] = comp_snap
            n_snaps_written += len(comp_snap)

        # 2. Update rider state from this competition's results
        cat_idx = cat_to_idx.get(comp_type)
        if cat_idx is None:
            continue
        for rider_id, pb in results_by_comp.get(comp_id, ()):
            _ensure(rider_id)
            n_state[rider_id][cat_idx] += 1
            sum_state[rider_id][cat_idx] += pb
            sumsq_state[rider_id][cat_idx] += pb * pb
            if pb < min_state[rider_id][cat_idx]:
                min_state[rider_id][cat_idx] = float(pb)

    elapsed = time.time() - t0
    print(
        f'  rider signatures: {n_comps_seen} competitions walked, '
        f'{len(n_state)} unique riders, {n_snaps_written:,} qualifying '
        f'snapshots across {len(snapshots)} one-day races in {elapsed:.1f}s'
    )
    return snapshots


# ---------------------------------------------------------------------------
# Field aggregates — uniform weighting
# ---------------------------------------------------------------------------


def _weighted_quantile(
    values: np.ndarray, weights: np.ndarray, q: float
) -> float:
    """Cumulative-weight weighted quantile (interpolated, type-7-ish)."""
    if len(values) == 0:
        return float('nan')
    order = np.argsort(values)
    v = values[order]
    w = weights[order]
    total = w.sum()
    if total <= 0:
        return float('nan')
    cum = np.cumsum(w)
    mids = (cum - 0.5 * w) / total
    return float(np.interp(q, mids, v))


def compute_field_aggregates(
    one_day_df: pd.DataFrame,
    signatures: Dict[int, Dict[int, np.ndarray]],
) -> Tuple[np.ndarray, np.ndarray]:
    """For each one-day race, compute a 48-dim field aggregate: for each of
    the 12 signature dims, a uniformly-weighted {mean, std, p25, p75}
    across the race's qualifying starters.

    Returns ``(field_matrix, valid_mask)``. ``field_matrix`` has shape
    ``(n_one_day, 48)``; races with fewer than ``MIN_STARTERS`` qualifying
    starters have NaN rows and ``valid_mask[i]=False``.

    NOTE: uniform weighting here is deliberate. The type-profile signature
    already encodes rider quality via the per-category bucket stats; adding
    a ``1/(stage_avg_bucket+1)`` outer weight was what caused the earlier
    gradient-history version to collapse Roubaix and Giro-TT into the same
    cluster (both fields dominated by the same elite pool signature).
    """
    n_comps = len(one_day_df)
    field_matrix = np.full((n_comps, N_FIELD), np.nan, dtype=np.float64)
    valid_mask = np.zeros(n_comps, dtype=bool)

    comp_ids = one_day_df['competition_id'].to_numpy(dtype=np.int64)

    n_valid = 0
    n_dropped = 0
    for i in range(n_comps):
        comp_id = int(comp_ids[i])
        sigs = signatures.get(comp_id, {})
        if len(sigs) < MIN_STARTERS:
            n_dropped += 1
            continue

        sig_matrix = np.stack(list(sigs.values()))  # (m, 12)
        m = sig_matrix.shape[0]
        weights = np.ones(m, dtype=np.float64)
        w_norm = weights / weights.sum()

        means = (sig_matrix * w_norm[:, None]).sum(axis=0)      # (12,)
        diffs = sig_matrix - means[None, :]
        stds = np.sqrt((w_norm[:, None] * diffs * diffs).sum(axis=0))  # (12,)

        p25 = np.empty(N_SIG, dtype=np.float64)
        p75 = np.empty(N_SIG, dtype=np.float64)
        for j in range(N_SIG):
            p25[j] = _weighted_quantile(sig_matrix[:, j], weights, 0.25)
            p75[j] = _weighted_quantile(sig_matrix[:, j], weights, 0.75)

        out = np.empty(N_FIELD, dtype=np.float64)
        for j in range(N_SIG):
            base = j * N_FIELD_STATS
            out[base + 0] = means[j]
            out[base + 1] = stds[j]
            out[base + 2] = p25[j]
            out[base + 3] = p75[j]
        field_matrix[i] = out
        valid_mask[i] = True
        n_valid += 1

    print(
        f'  field aggregates: {n_valid}/{n_comps} one-day races qualify '
        f'(>= {MIN_STARTERS} starters with >= {MIN_PRIOR_ANY} prior finishes); '
        f'{n_dropped} dropped'
    )
    return field_matrix, valid_mask


def build_feature_matrices(
    one_day_df: pd.DataFrame, field_matrix: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    """Return (X_race[n, 11], X_joint[n, 59])."""
    race_side = one_day_df[GRADIENT_COLS].to_numpy(dtype=np.float64)
    joint = np.concatenate([race_side, field_matrix], axis=1)
    return race_side, joint


# ---------------------------------------------------------------------------
# Preprocessors — one per variant. Responsible for scaling, optional PCA,
# and providing transform / inverse_transform for Hungarian matching.
# ---------------------------------------------------------------------------


class RaceOnlyPreprocessor:
    """z-score the 11-dim race-side feature vector. No PCA (already small)."""

    def __init__(self) -> None:
        self.scaler: StandardScaler = StandardScaler()

    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        return self.scaler.fit_transform(X)

    def transform(self, X: np.ndarray) -> np.ndarray:
        return self.scaler.transform(X)

    def inverse_transform(self, feat: np.ndarray) -> np.ndarray:
        return self.scaler.inverse_transform(feat)

    def field_pca_explained(self) -> Optional[np.ndarray]:
        return None


class JointPreprocessor:
    """Split the joint vector into race (first 11 cols) and field (rest),
    z-score each block independently, PCA-compress the field block to
    ``JOINT_FIELD_PCS`` components, and concatenate. The feature space the
    GMM sees is ``(11 race-z) || (JOINT_FIELD_PCS field-pcs)``.

    The whole point of this split is to prevent the 48-dim field block from
    dominating a naive all-at-once PCA. Under split-and-concat, the race
    side keeps its full 11-dim budget in the GMM input and the field side
    contributes JOINT_FIELD_PCS compressed dims as secondary information.
    """

    def __init__(self, n_field_pcs: int = JOINT_FIELD_PCS) -> None:
        self.n_field_pcs = n_field_pcs
        self.scaler_race: StandardScaler = StandardScaler()
        self.scaler_field: StandardScaler = StandardScaler()
        # Fit one extra component and drop PC1 in transform. The inspection
        # from the unwhitened run showed PC1 is a near-pure "field quality"
        # axis (field_stage_best_mean, field_gc_logcnt_mean, etc. — all
        # elite-vs-non-elite signals), while PC2..PC5 carry the type
        # structure we actually want (GC experience spread, one-day
        # performance heterogeneity, etc.). Dropping PC1 strips the
        # quality-dominance failure mode without amplifying noise in the
        # long tail the way whitening did. Without whitening, PCs 2..5
        # retain their natural variance ordering so the more structural
        # components weigh more than the tail.
        self.pca_field: PCA = PCA(
            n_components=n_field_pcs + 1,
            random_state=GMM_RANDOM_STATE,
        )

    def _split(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        return X[:, :N_GRAD], X[:, N_GRAD:]

    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        race, field = self._split(X)
        race_z = self.scaler_race.fit_transform(race)
        field_z = self.scaler_field.fit_transform(field)
        # Fit one extra PC so we can drop PC1. Guard against over-requesting
        # components on small training folds.
        requested = self.n_field_pcs + 1
        max_pcs = min(requested, field_z.shape[0] - 1, field_z.shape[1])
        if max_pcs != requested:
            self.pca_field = PCA(
                n_components=max_pcs,
                random_state=GMM_RANDOM_STATE,
            )
            self.n_field_pcs = max_pcs - 1  # one is dropped
        field_pca_full = self.pca_field.fit_transform(field_z)
        # Drop PC1 (the quality-dominance axis) and keep PC2..PCk.
        field_pca = field_pca_full[:, 1:]
        return np.concatenate([race_z, field_pca], axis=1)

    def transform(self, X: np.ndarray) -> np.ndarray:
        race, field = self._split(X)
        race_z = self.scaler_race.transform(race)
        field_z = self.scaler_field.transform(field)
        field_pca_full = self.pca_field.transform(field_z)
        field_pca = field_pca_full[:, 1:]
        return np.concatenate([race_z, field_pca], axis=1)

    def inverse_transform(self, feat: np.ndarray) -> np.ndarray:
        """Map a ``(11 race-z, field-PC2..PCk)`` feature vector back to the
        original joint-space (unstandardized race + unstandardized field).
        Used only by Hungarian cross-fold matching. Since PC1 was dropped,
        we re-insert a zero for it before inverse-PCA — the reconstruction
        is lossy along the quality axis but good for centroid matching.
        """
        race_z = feat[:, :N_GRAD]
        field_pca_kept = feat[:, N_GRAD:]
        # Re-insert a zero column for the dropped PC1.
        n_rows = field_pca_kept.shape[0]
        field_pca_full = np.concatenate(
            [np.zeros((n_rows, 1)), field_pca_kept], axis=1
        )
        race = self.scaler_race.inverse_transform(race_z)
        field_z = self.pca_field.inverse_transform(field_pca_full)
        field = self.scaler_field.inverse_transform(field_z)
        return np.concatenate([race, field], axis=1)

    def field_pca_explained(self) -> Optional[np.ndarray]:
        return self.pca_field.explained_variance_ratio_


# ---------------------------------------------------------------------------
# GMM per fold
# ---------------------------------------------------------------------------


@dataclass
class FoldFit:
    label: str
    variant: str
    k: int
    bic: float
    preprocessor: object  # RaceOnlyPreprocessor | JointPreprocessor
    gmm: GaussianMixture
    scores: np.ndarray       # (n_comps, k) soft memberships (NaN for invalid)
    dominant: np.ndarray     # (n_comps,) int argmax (-1 for invalid)
    n_train: int
    k_reports: List[Dict]


def _cluster_sizes_ok(labels: np.ndarray, k: int, n: int) -> Tuple[bool, float, float]:
    counts = np.bincount(labels, minlength=k)
    max_pct = counts.max() / n
    min_pct = counts.min() / n
    ok = (min_pct >= MIN_CLUSTER_PCT) and (max_pct <= MAX_CLUSTER_PCT)
    return bool(ok), float(min_pct), float(max_pct)


def _make_preprocessor(variant: str):
    if variant == 'race_only':
        return RaceOnlyPreprocessor()
    if variant == 'joint':
        return JointPreprocessor()
    raise ValueError(f'unknown variant {variant!r}')


def _fit_gmm(k: int, X_train_feat: np.ndarray) -> GaussianMixture:
    gmm = GaussianMixture(
        n_components=k,
        covariance_type='diag',
        random_state=GMM_RANDOM_STATE,
        max_iter=300,
        n_init=5,
        reg_covar=1e-3,
    )
    gmm.fit(X_train_feat)
    return gmm


def fit_and_score_per_fold(
    X: np.ndarray,
    dates: np.ndarray,
    folds: List[Dict[str, str]],
    variant: str,
    k_min: int,
    k_max: int,
) -> Dict[str, FoldFit]:
    """For each fold: fit a variant-specific preprocessor on the training
    fold, then sweep GMM k in ``[k_min, k_max]`` picking the smallest-BIC
    fit subject to the 3-20% cluster size constraints. Score all one-days.
    """
    dates_dt = pd.to_datetime(dates)
    n_comps = X.shape[0]
    valid_rows = ~np.isnan(X).any(axis=1)

    results: Dict[str, FoldFit] = {}

    for fold in folds:
        label = fold['label']
        train_end = pd.to_datetime(fold['train_end'])
        train_mask = (dates_dt <= train_end) & valid_rows
        n_train = int(train_mask.sum())
        if n_train < 60:
            raise RuntimeError(
                f'Fold {label}/{variant}: only {n_train} training one-days '
                f'(need >= 60). Something is wrong with the fold construction.'
            )

        preprocessor = _make_preprocessor(variant)
        X_train_feat = preprocessor.fit_transform(X[train_mask])
        X_valid_feat = preprocessor.transform(X[valid_rows])

        best: Optional[Dict] = None
        k_reports: List[Dict] = []
        for k in range(k_min, k_max + 1):
            gmm = _fit_gmm(k, X_train_feat)
            train_labels = gmm.predict(X_train_feat)
            bic = float(gmm.bic(X_train_feat))
            ok, min_pct, max_pct = _cluster_sizes_ok(train_labels, k, n_train)
            k_reports.append({
                'k': k, 'bic': bic, 'ok': ok,
                'min_pct': min_pct, 'max_pct': max_pct,
                'cluster_sizes': np.bincount(train_labels, minlength=k).tolist(),
            })
            if ok and (best is None or bic < best['bic']):
                best = {'k': k, 'gmm': gmm, 'bic': bic}

        if best is None:
            fallback = min(k_reports, key=lambda r: r['max_pct'])
            k = fallback['k']
            gmm = _fit_gmm(k, X_train_feat)
            best = {'k': k, 'gmm': gmm, 'bic': fallback['bic']}
            print(
                f'  [{variant}/{label}] WARN: no k in [{k_min},{k_max}] '
                f'passed cluster constraints; falling back to k={k} '
                f'(min={fallback["min_pct"]:.3f}, max={fallback["max_pct"]:.3f})'
            )

        k = best['k']
        gmm = best['gmm']

        scores = np.full((n_comps, k), np.nan, dtype=np.float64)
        dominant = np.full(n_comps, -1, dtype=np.int64)
        scores[valid_rows] = gmm.predict_proba(X_valid_feat)
        dominant[valid_rows] = gmm.predict(X_valid_feat)

        field_exp = preprocessor.field_pca_explained()
        field_note = (
            f' field_pca={len(field_exp)}d '
            f'(explained={float(field_exp.sum()):.3f})'
            if field_exp is not None else ''
        )
        print(
            f'  [{variant}/{label}] k={k} BIC={best["bic"]:.1f} '
            f'n_train={n_train} valid_scored={int(valid_rows.sum())}{field_note}'
        )

        results[label] = FoldFit(
            label=label, variant=variant,
            k=k, bic=best['bic'],
            preprocessor=preprocessor, gmm=gmm,
            scores=scores, dominant=dominant,
            n_train=n_train, k_reports=k_reports,
        )

    return results


# ---------------------------------------------------------------------------
# Hungarian cross-fold cluster matching (diagnostic only)
# ---------------------------------------------------------------------------


def hungarian_match(
    fits: Dict[str, FoldFit], reference_label: str = '2023'
) -> Dict:
    """Map each fold's cluster centroids into the reference fold's feature
    space via the preprocessor's inverse_transform + the reference
    preprocessor's transform, then Hungarian-match centroids to produce
    canonical cluster IDs.
    """
    ref = fits[reference_label]

    def _centroid_in_ref_space(fit: FoldFit) -> np.ndarray:
        # fit.gmm.means_ lives in fit's (possibly split+compressed) feature
        # space. Undo fit's preprocessor to get original joint/race space,
        # then apply ref's preprocessor to land in ref's feature space.
        original = fit.preprocessor.inverse_transform(fit.gmm.means_)
        return ref.preprocessor.transform(original)

    ref_centroids = ref.gmm.means_
    ref_k = ref.k

    matching: Dict[str, Dict[int, int]] = {
        reference_label: {i: i for i in range(ref_k)}
    }
    diagnostics: Dict[str, Dict] = {
        reference_label: {
            'k': ref_k, 'mean_distance': 0.0, 'max_distance': 0.0,
            'per_raw_cluster': {i: 0.0 for i in range(ref_k)},
            'unmatched_raw': [], 'unmatched_canonical': [],
        }
    }

    for label, fit in fits.items():
        if label == reference_label:
            continue
        raw_in_ref = _centroid_in_ref_space(fit)
        k = fit.k

        max_k = max(k, ref_k)
        D = np.full((max_k, max_k), 1e9)
        for i in range(k):
            for j in range(ref_k):
                D[i, j] = float(np.linalg.norm(raw_in_ref[i] - ref_centroids[j]))

        row_ind, col_ind = linear_sum_assignment(D)
        cluster_map: Dict[int, int] = {}
        per_cluster: Dict[int, float] = {}
        for raw_i, canon_j in zip(row_ind, col_ind):
            if raw_i < k and canon_j < ref_k:
                cluster_map[int(raw_i)] = int(canon_j)
                per_cluster[int(raw_i)] = float(D[raw_i, canon_j])

        matching[label] = cluster_map
        dists = list(per_cluster.values())
        diagnostics[label] = {
            'k': k,
            'mean_distance': float(np.mean(dists)) if dists else 0.0,
            'max_distance': float(np.max(dists)) if dists else 0.0,
            'per_raw_cluster': per_cluster,
            'unmatched_raw': sorted(i for i in range(k) if i not in cluster_map),
            'unmatched_canonical': sorted(
                j for j in range(ref_k) if j not in set(cluster_map.values())
            ),
        }

    return {'matching': matching, 'diagnostics': diagnostics}


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def ensure_table(conn: sqlite3.Connection) -> None:
    cluster_cols_sql = ',\n'.join(
        f'    cluster_{i}_score REAL' for i in range(MAX_CLUSTERS)
    )
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS race_cluster_v1_scores (
            competition_id INTEGER NOT NULL,
            fold_label TEXT NOT NULL,
            variant TEXT NOT NULL,
            k_chosen INTEGER NOT NULL,
            cluster_dominant INTEGER NOT NULL,
        {cluster_cols_sql},
            PRIMARY KEY (competition_id, fold_label, variant)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_rcv1_comp_fold_variant
        ON race_cluster_v1_scores (competition_id, fold_label, variant)
        """
    )
    conn.commit()


def write_cluster_scores(
    conn: sqlite3.Connection,
    comp_ids: np.ndarray,
    fits: Dict[str, FoldFit],
    variant: str,
) -> int:
    cluster_col_names = [f'cluster_{i}_score' for i in range(MAX_CLUSTERS)]
    cols_sql = ', '.join(cluster_col_names)
    placeholders = ', '.join('?' * (5 + MAX_CLUSTERS))
    sql = f"""
        INSERT OR REPLACE INTO race_cluster_v1_scores
            (competition_id, fold_label, variant, k_chosen, cluster_dominant, {cols_sql})
        VALUES ({placeholders})
    """

    total = 0
    for label, fit in fits.items():
        rows = []
        for i in range(len(comp_ids)):
            comp_id = int(comp_ids[i])
            dominant = int(fit.dominant[i])
            row_scores = fit.scores[i]
            if np.isnan(row_scores).any():
                cluster_values = [None] * MAX_CLUSTERS
                dominant = -1
            else:
                cluster_values = list(row_scores.tolist()) + [None] * (MAX_CLUSTERS - fit.k)
            rows.append((comp_id, label, variant, fit.k, dominant, *cluster_values))
        conn.executemany(sql, rows)
        total += len(rows)
    conn.commit()
    return total


# ---------------------------------------------------------------------------
# Canonical races sanity
# ---------------------------------------------------------------------------


def canonical_race_report(
    one_day_df: pd.DataFrame,
    fits: Dict[str, FoldFit],
    variant: str,
) -> List[Dict]:
    """For each canonical sub-type, find the most recent example in the
    loaded data and print its dominant cluster per fold. We want races of
    the same sub-type (e.g., all cobbles classics) to share a cluster and
    races of different sub-types (climber classic vs bunch sprint) to
    split.
    """
    names_lower = one_day_df['competition_name'].astype(str).str.lower()
    comp_ids = one_day_df['competition_id'].to_numpy()
    dates = one_day_df['competition_date'].to_numpy()
    reports: List[Dict] = []

    for display_name, substrings in CANONICAL_RACES:
        mask = np.zeros(len(one_day_df), dtype=bool)
        for sub in substrings:
            mask |= names_lower.str.contains(sub, na=False).to_numpy()
        if not mask.any():
            reports.append({'name': display_name, 'match': 'NONE'})
            continue
        idxs = np.where(mask)[0]
        idx = int(idxs[np.argmax(dates[idxs])])
        entry = {
            'name': display_name,
            'match_comp_id': int(comp_ids[idx]),
            'match_comp_name': one_day_df.iloc[idx]['competition_name'],
            'match_comp_date': str(one_day_df.iloc[idx]['competition_date'].date()),
            'per_fold': {},
        }
        for label, fit in fits.items():
            dom = int(fit.dominant[idx])
            entry['per_fold'][label] = {
                'k': fit.k,
                'dominant': dom,
            }
        reports.append(entry)

    print(f'\n  CANONICAL RACE SANITY CHECK — variant={variant}')
    for r in reports:
        if r.get('match') == 'NONE':
            print(f'    {r["name"]}: no match found in one-day data')
            continue
        per_fold_str = '  '.join(
            f'[{lab}]={pf["dominant"]}(k={pf["k"]})'
            for lab, pf in r['per_fold'].items()
        )
        print(
            f'    {r["name"]:<36} comp {r["match_comp_id"]} '
            f'({r["match_comp_date"]})  {per_fold_str}'
        )
    return reports


def _field_feature_names() -> List[str]:
    stat_labels = ['mean', 'std', 'p25', 'p75']
    sig_labels: List[str] = []
    for cat in CATEGORIES:
        for s in ['avg', 'std', 'best', 'logcnt']:
            sig_labels.append(f'{cat}_{s}')
    names: List[str] = []
    for sig_label in sig_labels:
        for stat in stat_labels:
            names.append(f'field_{sig_label}_{stat}')
    return names


def pca_interpretability_report(
    fits: Dict[str, FoldFit], variant: str, label: str = '2023'
) -> None:
    """For the joint variant, print loadings of the field-side PCs so we
    can see what field-level structure the GMM is getting as its secondary
    signal. Race-side features are raw and not PCA-compressed under the
    split-and-concat design, so there's nothing to report for them.
    """
    fit = fits.get(label)
    if fit is None or variant != 'joint':
        return
    pre = fit.preprocessor
    if not isinstance(pre, JointPreprocessor):
        return

    field_names = _field_feature_names()
    explained = pre.pca_field.explained_variance_ratio_

    print(f'\n  FIELD-PCA INTERPRETABILITY — variant={variant}, fold={label}')
    print(f'    field PC explained variance: {np.round(explained, 3).tolist()}')
    print(f'    cumulative:                  {np.round(np.cumsum(explained), 3).tolist()}')
    print('    (PC1 is dropped in transform — shown here for reference only)')
    n_pcs = min(6, pre.pca_field.components_.shape[0])
    for i in range(n_pcs):
        loadings = pre.pca_field.components_[i]
        top_idx = np.argsort(np.abs(loadings))[::-1][:6]
        top_str = '  '.join(
            f'{field_names[j]}({loadings[j]:+.2f})' for j in top_idx
        )
        dropped_note = ' [DROPPED]' if i == 0 else ''
        print(f'    field_PC{i+1}{dropped_note}: {top_str}')


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def run(
    db_path: str,
    variants: List[str],
    dry_run: bool = False,
    start_date: str = '2018-01-01',
) -> Dict:
    print(f'>>> Stage 1 one-day clustering on {db_path}')
    print(f'    variants={variants}  dry_run={dry_run}  start_date={start_date}')

    conn = sqlite3.connect(db_path)
    try:
        t0 = time.time()
        print('\n[1/5] Loading data from DB...')
        data = load_from_db(conn, start_date=start_date)
        print(
            f'  loaded {len(data.one_day_df)} one-day competitions '
            f'({len(data.order_df)} total comps walked for rider state), '
            f'{len(data.one_day_startlists)} startlist rows, '
            f'{len(data.results_df)} results rows in {time.time()-t0:.1f}s'
        )

        print('\n[2/5] Building rider type-profile signatures (chronological pass)...')
        signatures = compute_rider_type_signatures(
            data.order_df, data.one_day_startlists, data.results_df
        )

        print('\n[3/5] Building field aggregates (uniform weighting)...')
        field_matrix, valid_mask = compute_field_aggregates(
            data.one_day_df, signatures
        )

        print('\n[4/5] Assembling feature matrices...')
        X_race, X_joint = build_feature_matrices(data.one_day_df, field_matrix)
        print(f'  X_race_only shape={X_race.shape}')
        print(f'  X_joint     shape={X_joint.shape}')
        print(f'  valid rows for joint: {int(valid_mask.sum())}/{len(valid_mask)}')

        if not dry_run:
            ensure_table(conn)

        all_fits: Dict[str, Dict[str, FoldFit]] = {}
        all_diagnostics: Dict = {}

        dates = data.one_day_df['competition_date'].to_numpy()
        comp_ids = data.one_day_df['competition_id'].to_numpy()

        print('\n[5/5] Fitting GMMs')
        for variant in variants:
            print(f'\n  === variant={variant} ===')
            if variant == 'race_only':
                X = X_race
                k_max = K_MAX_RACE_ONLY
            elif variant == 'joint':
                X = X_joint
                k_max = K_MAX_JOINT
            else:
                raise ValueError(f'unknown variant {variant!r}')

            fits = fit_and_score_per_fold(
                X, dates, DEFAULT_FOLDS, variant,
                k_min=K_MIN, k_max=k_max,
            )
            all_fits[variant] = fits

            diag = hungarian_match(fits, reference_label='2023')
            all_diagnostics[variant] = diag

            canonical_race_report(data.one_day_df, fits, variant)

            if variant == 'joint':
                pca_interpretability_report(fits, variant, label='2023')

            if not dry_run:
                n_rows = write_cluster_scores(conn, comp_ids, fits, variant)
                print(
                    f'\n  wrote {n_rows} rows to race_cluster_v1_scores '
                    f'(variant={variant})'
                )
            else:
                print('\n  dry-run: skipping DB write')

        print('\n=== CROSS-FOLD CLUSTER STABILITY (Hungarian, ref=2023) ===')
        for variant in variants:
            diag = all_diagnostics[variant]['diagnostics']
            print(f'\n  variant={variant}')
            for label, d in diag.items():
                if label == '2023':
                    continue
                print(
                    f'    [{label} -> 2023] mean_dist={d["mean_distance"]:.3f} '
                    f'max_dist={d["max_distance"]:.3f} k={d["k"]} '
                    f'unmatched_raw={d["unmatched_raw"]} '
                    f'unmatched_canonical={d["unmatched_canonical"]}'
                )

        print(f'\n>>> Done in {time.time()-t0:.1f}s')
        return {
            'fits': all_fits,
            'diagnostics': all_diagnostics,
            'n_one_day': len(data.one_day_df),
        }
    finally:
        conn.close()


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    p.add_argument('--db', type=str, required=True)
    p.add_argument('--variants', type=str, default='race_only,joint')
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--start-date', type=str, default='2018-01-01')
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    variants = [v.strip() for v in args.variants.split(',') if v.strip()]
    run(
        db_path=args.db,
        variants=variants,
        dry_run=args.dry_run,
        start_date=args.start_date,
    )


if __name__ == '__main__':
    main()
