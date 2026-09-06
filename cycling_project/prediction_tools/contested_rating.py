"""
Contested-comparison rider rating — Elo over informative result-sheet comparisons.

Builds a chronological Elo rating per rider from one_day + stage competitions
(gc excluded), using ONLY the comparisons the project's front-local result-sheet
analysis deems informative (2026-06):

  (a) sprint order within the winner's same-time group, restricted to the
      first `winner_group_top_n` (default 10) positions of that group —
      earlier sheet position beats later;
  (b) group-vs-group: every rider in time group g beats every rider in the
      next group g+1 (adjacent groups only), each side capped at its first
      `group_cap` (default 10) positions to bound pair counts.

Deep-blob internal order (positions 11+ inside any same-time group) generates
NO comparisons — per the validated project insight that only the front of a
same-time group is genuinely racing, while time-separated riders and separate
groups ARE real outcomes.

Same-time grouping is the canonical 1.0s consecutive-gap rule
(`group_sizes_from_gaps` reused from front_local_race_typing, identical to
engineered_metrics.identify_groups).

Updates are batched per competition (expected scores computed from
PRE-competition ratings for all pairs, applied at once); competitions are
processed in (date, competition_id) order. After each competition a snapshot
row (rider_id, competition_id, date, rating_after, cumulative comparisons) is
appended for every rider involved in >= 1 comparison, so the rating is
queryable strictly as-of any (date, competition_id) key. The feature for a
competition is the rating BEFORE that competition (merge_asof with
allow_exact_matches=False — zero look-ahead). For gc rows the cutoff is the
race's FIRST stage date (gc competitions are dated on the final stage day).

Snapshots persist to experiments/contested_rating_snapshots.parquet
(read-only DB discipline — nothing is written to the SQLite DB).

Usage:
    uv run python -m cycling_project.prediction_tools.contested_rating              # build + validate + save + sanity
    uv run python -m cycling_project.prediction_tools.contested_rating --k-sweep    # K-factor sensitivity check
    uv run python -m cycling_project.prediction_tools.contested_rating --k 16       # build with explicit K
"""

import argparse
import json
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from cycling_project.prediction_tools.contest_signature_features import (
    GROUP_THRESHOLD_S,
    group_sizes_from_gaps,
)
from cycling_project.webscrape_tools.logging_config import get_logger
from cycling_project.db_path import default_db_path

logger = get_logger(__name__)

DEFAULT_DB_PATH = default_db_path()
OUT_DIR = Path(__file__).parents[2] / "experiments"
DEFAULT_SNAPSHOT_PATH = OUT_DIR / "contested_rating_snapshots.parquet"

# Production artifact (written by build_or_update_snapshots; consumed by
# train_production_model and the web app's serving path).
PRODUCTION_SNAPSHOT_PATH = (
    Path(__file__).parents[2] / "models" / "production" / "contested_rating_snapshots.parquet"
)

# sort_key = days_since_epoch * KEY_MULT + competition_id (comp ids << 1e6),
# a single int64 that totally orders competitions the same way the engine
# processes them: by date, then competition id.
KEY_MULT = 1_000_000

# Chosen via --k-sweep (online rated-pair log loss / accuracy on 2016+ comps,
# K in {1,2,4,6,8,12,16,24,32}): accuracy peaks at K=4 (0.5521), log loss
# bottoms at K=2 (0.6827, K=4 within 0.002). K here is PER PAIR and a capped
# rider takes up to ~20 pair-updates per competition, so per-competition
# movement at K=4 is comparable to a classic single-game Elo K of ~20-80 —
# which is why the classic 16-32 range loses badly online (K=32: 0.7514).
DEFAULT_K = 4.0

# Column names deliberately avoid the 'avg_bucket' / '_count' substrings that
# trigger pattern-based imputation in feature_engineering.py — these features
# must stay NaN where a rider is unrated (LightGBM consumes NaN natively).
RATING_FEATURE_COLS = [
    'contested_rating',
    'contested_rating_n',
    'contested_rating_delta90',
    'contested_rating_vs_field',
]


@dataclass
class ContestedRatingConfig:
    k_factor: float = DEFAULT_K
    init_rating: float = 1500.0
    scale: float = 400.0
    winner_group_top_n: int = 10   # sprint-order pairs within the winner's group
    group_cap: int = 10            # per-side cap for group-vs-group pairs
    start_date: str = '2010-01-01'  # warm-up from 2010; training starts 2016
    db_path: Path = DEFAULT_DB_PATH


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_contested_results(config: ContestedRatingConfig) -> pd.DataFrame:
    """One_day + stage finisher rows in engine processing order.

    NULL time_gap rows (~0.4%) are dropped: they cannot be placed in a
    same-time group. gc competitions are excluded by design.
    """
    query = """
        SELECT rr.competition_id, rr.rider_id, rr.place, rr.time_gap, c.date
        FROM rider_results rr
        JOIN competitions c ON c.id = rr.competition_id
        WHERE c.competition_type IN ('one_day', 'stage')
          AND c.date IS NOT NULL AND c.date >= ?
          AND rr.time_gap IS NOT NULL
        ORDER BY c.date, rr.competition_id, rr.place
    """
    with sqlite3.connect(config.db_path) as conn:
        df = pd.read_sql_query(query, conn, params=(config.start_date,))
    df['date'] = pd.to_datetime(df['date'])
    days = df['date'].values.astype('datetime64[D]').astype(np.int64)
    df['sort_key'] = days * KEY_MULT + df['competition_id'].to_numpy(np.int64)
    logger.info(
        "Loaded %d contested result rows across %d competitions (%s..%s)",
        len(df), df['competition_id'].nunique(),
        df['date'].min().date(), df['date'].max().date(),
    )
    return df


# ---------------------------------------------------------------------------
# Pair generation
# ---------------------------------------------------------------------------

def _competition_pairs(
    group_sizes: List[int], winner_group_top_n: int, group_cap: int
) -> Tuple[np.ndarray, np.ndarray]:
    """(winner_idx, loser_idx) local-index pairs for one competition.

    Indices are sheet positions 0..n-1 (rows sorted by place). Comparisons:
      (a) ordered pairs among the first `winner_group_top_n` positions of the
          winner's same-time group (sprint order);
      (b) each of the first `group_cap` riders of group g beats each of the
          first `group_cap` riders of group g+1 (adjacent groups only).
    Deep-blob internal order beyond those rules produces no pairs.
    """
    w_parts: List[np.ndarray] = []
    l_parts: List[np.ndarray] = []

    # (a) winner-group sprint order
    k = min(group_sizes[0], winner_group_top_n)
    if k >= 2:
        iw, il = np.triu_indices(k, k=1)
        w_parts.append(iw.astype(np.int64))
        l_parts.append(il.astype(np.int64))

    # (b) adjacent group-vs-group
    start = 0
    for g in range(len(group_sizes) - 1):
        a_start, a_n = start, min(group_sizes[g], group_cap)
        start += group_sizes[g]
        b_n = min(group_sizes[g + 1], group_cap)
        a = np.arange(a_start, a_start + a_n, dtype=np.int64)
        b = np.arange(start, start + b_n, dtype=np.int64)
        w_parts.append(np.repeat(a, b_n))
        l_parts.append(np.tile(b, a_n))

    if not w_parts:
        empty = np.empty(0, dtype=np.int64)
        return empty, empty
    return np.concatenate(w_parts), np.concatenate(l_parts)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class ContestedRatingEngine:
    """Chronological batch-Elo over contested comparisons.

    Per competition all expected scores use pre-competition ratings; the
    summed deltas are applied at once (order-independence within a
    competition). Online predictive quality (accuracy / log loss of the
    pre-competition ratings on that competition's pairs, restricted to pairs
    where both riders were previously rated) is accumulated for the K-factor
    sensitivity check.
    """

    def __init__(self, config: Optional[ContestedRatingConfig] = None):
        self.config = config or ContestedRatingConfig()
        self.snapshots: Optional[pd.DataFrame] = None
        # per-competition online metrics: (date_days, n_rated_pairs, sum_nll, sum_correct)
        self._comp_metrics: List[Tuple[int, int, float, float]] = []

    def run(
        self,
        results: pd.DataFrame,
        initial_ratings: Optional[Dict[int, float]] = None,
        initial_ncomp: Optional[Dict[int, int]] = None,
    ) -> pd.DataFrame:
        """Process results chronologically; returns the new snapshot rows.

        initial_ratings / initial_ncomp seed the engine state for
        incremental updates (state as of strictly before the first row of
        `results`). With no seed this is the full historical build.
        """
        cfg = self.config
        ratings: Dict[int, float] = dict(initial_ratings) if initial_ratings else {}
        ncomp: Dict[int, int] = dict(initial_ncomp) if initial_ncomp else {}

        snap_rider: List[np.ndarray] = []
        snap_comp: List[np.ndarray] = []
        snap_key: List[np.ndarray] = []
        snap_rating: List[np.ndarray] = []
        snap_n: List[np.ndarray] = []
        self._comp_metrics = []
        total_pairs = 0

        # results are sorted by (date, competition_id, place); groupby with
        # sort=False preserves that chronological order.
        for comp_id, sub in results.groupby('competition_id', sort=False):
            gaps = sub['time_gap'].to_numpy(dtype=float)
            rid = sub['rider_id'].to_numpy(dtype=np.int64)
            sizes = group_sizes_from_gaps(gaps)
            w, l = _competition_pairs(sizes, cfg.winner_group_top_n, cfg.group_cap)
            if len(w) == 0:
                continue
            total_pairs += len(w)
            key = int(sub['sort_key'].iat[0])

            r = np.fromiter(
                (ratings.get(x, cfg.init_rating) for x in rid),
                dtype=np.float64, count=len(rid),
            )
            n_prev = np.fromiter(
                (ncomp.get(x, 0) for x in rid), dtype=np.int64, count=len(rid)
            )

            expected_w = 1.0 / (1.0 + 10.0 ** ((r[l] - r[w]) / cfg.scale))

            # online metrics on pairs where both riders were already rated
            rated = (n_prev[w] > 0) & (n_prev[l] > 0)
            if rated.any():
                e = expected_w[rated]
                self._comp_metrics.append((
                    key // KEY_MULT,
                    int(rated.sum()),
                    float(-np.log(np.clip(e, 1e-12, None)).sum()),
                    float((e > 0.5).sum() + 0.5 * (e == 0.5).sum()),
                ))

            gain = cfg.k_factor * (1.0 - expected_w)
            delta = np.zeros(len(rid))
            np.add.at(delta, w, gain)
            np.add.at(delta, l, -gain)
            cnt = np.zeros(len(rid), dtype=np.int64)
            np.add.at(cnt, w, 1)
            np.add.at(cnt, l, 1)

            inv = cnt > 0
            new_r = r[inv] + delta[inv]
            new_n = n_prev[inv] + cnt[inv]
            for x, nr, nn in zip(rid[inv].tolist(), new_r.tolist(), new_n.tolist()):
                ratings[x] = nr
                ncomp[x] = nn

            n_inv = int(inv.sum())
            snap_rider.append(rid[inv])
            snap_comp.append(np.full(n_inv, comp_id, dtype=np.int64))
            snap_key.append(np.full(n_inv, key, dtype=np.int64))
            snap_rating.append(new_r)
            snap_n.append(new_n)

        if not snap_rider:
            snapshots = pd.DataFrame({
                'rider_id': pd.Series(dtype=np.int64),
                'competition_id': pd.Series(dtype=np.int64),
                'sort_key': pd.Series(dtype=np.int64),
                'rating_after': pd.Series(dtype=float),
                'n_after': pd.Series(dtype=np.int64),
            })
            snapshots['date'] = pd.to_datetime(snapshots['sort_key'])
            self.snapshots = snapshots
            logger.info("Engine done: no new comparisons")
            return snapshots
        snapshots = pd.DataFrame({
            'rider_id': np.concatenate(snap_rider),
            'competition_id': np.concatenate(snap_comp),
            'sort_key': np.concatenate(snap_key),
            'rating_after': np.concatenate(snap_rating),
            'n_after': np.concatenate(snap_n),
        })
        snapshots['date'] = pd.to_datetime(
            snapshots['sort_key'] // KEY_MULT, unit='D'
        )
        self.snapshots = snapshots
        logger.info(
            "Engine done: %d comparisons, %d snapshot rows, %d rated riders (K=%.0f)",
            total_pairs, len(snapshots), snapshots['rider_id'].nunique(), cfg.k_factor,
        )
        return snapshots

    def online_metrics(self, since: str = '2016-01-01') -> Dict[str, float]:
        since_days = int(np.datetime64(since, 'D').astype(np.int64))
        rows = [m for m in self._comp_metrics if m[0] >= since_days]
        n = sum(m[1] for m in rows)
        if n == 0:
            return {'n_rated_pairs': 0}
        return {
            'n_rated_pairs': int(n),
            'pair_accuracy': float(sum(m[3] for m in rows) / n),
            'pair_log_loss': float(sum(m[2] for m in rows) / n),
        }


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_snapshots(snapshots: pd.DataFrame, path: Path = DEFAULT_SNAPSHOT_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    snapshots.to_parquet(path, index=False)
    logger.info("Saved %d snapshot rows to %s", len(snapshots), path)
    return path


def load_snapshots(path: Path = DEFAULT_SNAPSHOT_PATH) -> pd.DataFrame:
    return pd.read_parquet(path)


def build_and_save(
    config: Optional[ContestedRatingConfig] = None,
    path: Path = DEFAULT_SNAPSHOT_PATH,
) -> pd.DataFrame:
    """Convenience: load results, run engine, persist snapshots."""
    config = config or ContestedRatingConfig()
    results = load_contested_results(config)
    engine = ContestedRatingEngine(config)
    snapshots = engine.run(results)
    save_snapshots(snapshots, path)
    _write_artifact_meta(path, snapshots, config)
    if path.resolve() == PRODUCTION_SNAPSHOT_PATH.resolve():
        from cycling_project.prediction_tools.production_release import write_release_manifest
        write_release_manifest(path.parent)
    return snapshots


def _meta_path(artifact_path: Path) -> Path:
    return artifact_path.with_suffix(".meta.json")


def _count_eligible_comps_lte(db_path: Path, start_date: str, last_key: int) -> int:
    """Eligible competitions (engine input universe) at or before last_key."""
    last_days = last_key // KEY_MULT
    last_comp = last_key % KEY_MULT
    last_date = str(np.datetime64(int(last_days), 'D'))
    query = """
        SELECT COUNT(DISTINCT c.id)
        FROM competitions c
        WHERE c.competition_type IN ('one_day', 'stage')
          AND c.date IS NOT NULL AND c.date >= ?
          AND (c.date < ? OR (c.date = ? AND c.id <= ?))
          AND EXISTS (
            SELECT 1 FROM rider_results rr
            WHERE rr.competition_id = c.id AND rr.time_gap IS NOT NULL
          )
    """
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(query, (start_date, last_date, last_date, last_comp)).fetchone()
    return int(row[0])


def _write_artifact_meta(
    artifact_path: Path,
    snapshots: pd.DataFrame,
    config: ContestedRatingConfig,
) -> None:
    """Sidecar metadata that makes the artifact safely resumable."""
    last_key = int(snapshots['sort_key'].max()) if len(snapshots) else 0
    meta = {
        'last_sort_key': last_key,
        'n_snapshot_rows': int(len(snapshots)),
        'n_eligible_comps_lte_key': (
            _count_eligible_comps_lte(config.db_path, config.start_date, last_key)
            if last_key else 0
        ),
        'k_factor': config.k_factor,
        'start_date': config.start_date,
        'updated_at': datetime.now().isoformat(timespec='seconds'),
    }
    _meta_path(artifact_path).write_text(json.dumps(meta, indent=2))


def build_or_update_snapshots(
    db_path: Optional[Path] = None,
    artifact_path: Path = PRODUCTION_SNAPSHOT_PATH,
    config: Optional[ContestedRatingConfig] = None,
) -> pd.DataFrame:
    """Production entry: build or incrementally extend the snapshot artifact.

    Chronological and resumable: state is reconstructed from each rider's
    latest stored snapshot, then only competitions strictly AFTER the
    artifact's last (date, competition_id) key are processed and appended.

    Safety: a sidecar .meta.json records how many eligible competitions the
    artifact had seen at-or-before its last key. If the DB now contains a
    different count at-or-before that key (late-arriving migration of an
    older race), the incremental path would process out of order — we fall
    back to a full rebuild instead.
    """
    config = config or ContestedRatingConfig()
    if db_path is not None:
        config.db_path = Path(db_path)

    if not artifact_path.exists():
        logger.info("No rating artifact at %s — full build", artifact_path)
        return build_and_save(config, artifact_path)

    existing = load_snapshots(artifact_path)
    if existing.empty:
        return build_and_save(config, artifact_path)
    last_key = int(existing['sort_key'].max())

    # Late-arrival guard
    meta_path = _meta_path(artifact_path)
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        recorded = meta.get('n_eligible_comps_lte_key')
        if meta.get('k_factor') != config.k_factor or meta.get('start_date') != config.start_date:
            logger.warning("Rating artifact config drift — full rebuild")
            return build_and_save(config, artifact_path)
        current = _count_eligible_comps_lte(config.db_path, config.start_date, last_key)
        if recorded is not None and current != recorded:
            logger.warning(
                "Eligible comps at-or-before artifact key changed (%s -> %s) — "
                "late-arriving results detected, full rebuild", recorded, current,
            )
            return build_and_save(config, artifact_path)
    else:
        logger.warning("Rating artifact has no sidecar metadata — full rebuild")
        return build_and_save(config, artifact_path)

    results = load_contested_results(config)
    new_results = results[results['sort_key'] > last_key]
    if new_results.empty:
        logger.info("Rating artifact already current (last key %d)", last_key)
        return existing

    # Reconstruct state strictly as of the artifact
    final = (
        existing.sort_values('sort_key', kind='mergesort')
        .groupby('rider_id').tail(1)
    )
    initial_ratings = dict(zip(final['rider_id'].astype(int), final['rating_after'].astype(float)))
    initial_ncomp = dict(zip(final['rider_id'].astype(int), final['n_after'].astype(int)))

    engine = ContestedRatingEngine(config)
    new_snaps = engine.run(new_results, initial_ratings, initial_ncomp)
    combined = pd.concat([existing, new_snaps], ignore_index=True)
    save_snapshots(combined, artifact_path)
    _write_artifact_meta(artifact_path, combined, config)
    if artifact_path.resolve() == PRODUCTION_SNAPSHOT_PATH.resolve():
        from cycling_project.prediction_tools.production_release import write_release_manifest
        write_release_manifest(artifact_path.parent)
    logger.info(
        "Rating artifact updated: +%d snapshot rows over %d new comps (total %d rows)",
        len(new_snaps), new_results['competition_id'].nunique(), len(combined),
    )
    return combined


# ---------------------------------------------------------------------------
# Feature attachment (strictly as-of-then)
# ---------------------------------------------------------------------------

def _gc_first_stage_days(db_path: Path) -> Dict[int, int]:
    """gc competition id -> days-since-epoch of the race's first stage."""
    query = """
        SELECT g.id AS comp_id, MIN(s.date) AS first_stage_date
        FROM competitions g
        JOIN competitions s
          ON s.race_id = g.race_id
         AND s.competition_type = 'stage'
         AND s.date IS NOT NULL
        WHERE g.competition_type = 'gc'
        GROUP BY g.id
    """
    with sqlite3.connect(db_path) as conn:
        fs = pd.read_sql_query(query, conn)
    days = pd.to_datetime(fs['first_stage_date']).values.astype('datetime64[D]').astype(np.int64)
    return dict(zip(fs['comp_id'].astype(int), days.tolist()))


def attach_rating_features(
    df: pd.DataFrame,
    snapshots: pd.DataFrame,
    db_path: Optional[Path] = DEFAULT_DB_PATH,
    init_rating: float = 1500.0,
    delta_window_days: int = 90,
) -> pd.DataFrame:
    """Attach as-of-then contested-rating features to a training/serving frame.

    Requires columns: rider_id, competition_id, competition_date (and
    optionally competition_type for the gc race-start cutoff). Adds:

      contested_rating          rating strictly BEFORE the row's competition
      contested_rating_n        cumulative contested comparisons before it
      contested_rating_delta90  rating change over the trailing 90 days
                                (vs init_rating when first rated < 90d ago)
      contested_rating_vs_field rating minus the competition's mean rating

    All NaN where the rider has never been in a contested comparison.
    Cutoff for one_day/stage rows is (date, competition_id) with exact
    matches excluded — the row's own competition never contributes. For gc
    rows the cutoff is the race's first stage date (gc comps are dated on the
    final stage day; the pre-race rating is the leak-safe choice).
    """
    out = df.copy()
    dates = pd.to_datetime(out['competition_date'])
    days = dates.values.astype('datetime64[D]').astype(np.int64)
    comp_ids = out['competition_id'].to_numpy(np.int64)
    cutoff_key = days * KEY_MULT + comp_ids

    if 'competition_type' in out.columns and db_path is not None:
        gc_mask = (out['competition_type'] == 'gc').to_numpy()
        if gc_mask.any():
            first_stage = _gc_first_stage_days(db_path)
            gc_days = np.array([
                first_stage.get(int(c), int(d))
                for c, d in zip(comp_ids[gc_mask], days[gc_mask])
            ], dtype=np.int64)
            # id component 0 => strictly before anything on that day
            cutoff_key[gc_mask] = gc_days * KEY_MULT

    snaps = snapshots[['rider_id', 'sort_key', 'rating_after', 'n_after']].copy()
    snaps['rider_id'] = snaps['rider_id'].astype(np.int64)
    snaps = snaps.sort_values('sort_key', kind='mergesort')

    def _asof(keys: np.ndarray) -> pd.DataFrame:
        left = pd.DataFrame({
            'rider_id': out['rider_id'].to_numpy(np.int64),
            'cutoff_key': keys,
            '_orig_pos': np.arange(len(out)),
        }).sort_values('cutoff_key', kind='mergesort')
        merged = pd.merge_asof(
            left, snaps,
            left_on='cutoff_key', right_on='sort_key',
            by='rider_id', direction='backward', allow_exact_matches=False,
        )
        return merged.sort_values('_orig_pos')

    now = _asof(cutoff_key)
    rating = now['rating_after'].to_numpy()
    n_before = now['n_after'].to_numpy(dtype=float)

    window_key = (cutoff_key // KEY_MULT - delta_window_days) * KEY_MULT
    past = _asof(window_key)
    r_past = past['rating_after'].to_numpy()
    base = np.where(np.isnan(r_past), init_rating, r_past)
    delta90 = np.where(np.isnan(rating), np.nan, rating - base)

    out['contested_rating'] = rating
    out['contested_rating_n'] = n_before
    out['contested_rating_delta90'] = delta90
    field_mean = out.groupby('competition_id')['contested_rating'].transform('mean')
    out['contested_rating_vs_field'] = out['contested_rating'] - field_mean
    return out


# ---------------------------------------------------------------------------
# Sanity / validation helpers
# ---------------------------------------------------------------------------

def top_rated(
    snapshots: pd.DataFrame,
    db_path: Path = DEFAULT_DB_PATH,
    as_of: str = '2026-01-01',
    active_since: str = '2024-01-01',
    min_n: int = 200,
    top_n: int = 20,
) -> pd.DataFrame:
    """Top rated riders as of a date, restricted to recently active riders."""
    key = int(np.datetime64(as_of, 'D').astype(np.int64)) * KEY_MULT
    active_key = int(np.datetime64(active_since, 'D').astype(np.int64)) * KEY_MULT
    s = snapshots[snapshots['sort_key'] < key].sort_values('sort_key', kind='mergesort')
    last = s.groupby('rider_id').tail(1)
    last = last[(last['sort_key'] >= active_key) & (last['n_after'] >= min_n)]
    top = last.nlargest(top_n, 'rating_after').copy()
    with sqlite3.connect(db_path) as conn:
        names = pd.read_sql_query("SELECT id AS rider_id, name FROM riders", conn)
    top = top.merge(names, on='rider_id', how='left')
    return top[['rider_id', 'name', 'rating_after', 'n_after', 'date']].reset_index(drop=True)


def k_sweep(
    results: pd.DataFrame,
    ks: Tuple[float, ...] = (8.0, 16.0, 24.0, 32.0),
    since: str = '2016-01-01',
) -> List[Dict[str, float]]:
    """Online holdout quality of pre-competition ratings, per K."""
    rows = []
    for k in ks:
        engine = ContestedRatingEngine(ContestedRatingConfig(k_factor=k))
        engine.run(results)
        m = engine.online_metrics(since)
        rows.append({'k': k, **m})
        print(
            f"  K={k:>5.1f}  rated_pairs={m['n_rated_pairs']:,}  "
            f"accuracy={m['pair_accuracy']:.4f}  log_loss={m['pair_log_loss']:.4f}",
            flush=True,
        )
    return rows


def validate_no_lookahead(
    results: pd.DataFrame,
    snapshots: pd.DataFrame,
    config: ContestedRatingConfig,
    cutoff_date: str = '2023-06-01',
) -> Tuple[bool, Dict[str, float]]:
    """Confirm attached features at competition C exclude C's own comparisons.

    Re-runs a fresh engine on results strictly before the first competition at
    or after `cutoff_date` (the probe), then checks that
    attach_rating_features (driven by the FULL snapshot table) reproduces the
    truncated engine's final state exactly for every rider on the probe's
    sheet.
    """
    cutoff_days = int(np.datetime64(cutoff_date, 'D').astype(np.int64))
    after = results[results['sort_key'] >= cutoff_days * KEY_MULT]
    probe_key = int(after['sort_key'].iloc[0])
    probe_comp = int(after['competition_id'].iloc[0])
    probe_date = after['date'].iloc[0]

    truncated = results[results['sort_key'] < probe_key]
    engine = ContestedRatingEngine(config)
    snap_trunc = engine.run(truncated)
    final = (
        snap_trunc.sort_values('sort_key', kind='mergesort')
        .groupby('rider_id').tail(1).set_index('rider_id')
    )

    probe_rows = results[results['competition_id'] == probe_comp][['rider_id']].copy()
    probe_rows['competition_id'] = probe_comp
    probe_rows['competition_date'] = probe_date
    attached = attach_rating_features(probe_rows, snapshots, db_path=None)

    exp_r = probe_rows['rider_id'].map(final['rating_after'])
    exp_n = probe_rows['rider_id'].map(final['n_after'])
    got_r = attached['contested_rating']
    got_n = attached['contested_rating_n']

    both = exp_r.notna() & got_r.notna()
    max_diff = float((exp_r[both] - got_r[both]).abs().max()) if both.any() else 0.0
    nan_mismatch = int((exp_r.isna() != got_r.isna()).sum())
    n_mismatch = int((exp_n[both].to_numpy() != got_n[both].to_numpy()).sum()) if both.any() else 0
    ok = (max_diff < 1e-9) and (nan_mismatch == 0) and (n_mismatch == 0)

    info = {
        'probe_competition_id': probe_comp,
        'probe_date': str(pd.Timestamp(probe_date).date()),
        'n_riders_checked': int(len(probe_rows)),
        'n_rated': int(both.sum()),
        'max_rating_diff': max_diff,
        'nan_set_mismatches': nan_mismatch,
        'n_comparisons_mismatches': n_mismatch,
    }
    return ok, info


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--k', type=float, default=DEFAULT_K, help='Elo K-factor')
    parser.add_argument('--k-sweep', action='store_true', help='run K sensitivity check only')
    parser.add_argument('--out', type=Path, default=DEFAULT_SNAPSHOT_PATH)
    parser.add_argument('--skip-validate', action='store_true')
    args = parser.parse_args()

    config = ContestedRatingConfig(k_factor=args.k)
    print(f"Config: {asdict(config)}  group_threshold={GROUP_THRESHOLD_S}s", flush=True)

    results = load_contested_results(config)
    print(
        f"Results: {len(results):,} rows, {results['competition_id'].nunique():,} comps, "
        f"{results['date'].min().date()}..{results['date'].max().date()}",
        flush=True,
    )

    if args.k_sweep:
        print("\nK-factor sensitivity (online rated-pair quality, 2016+):", flush=True)
        k_sweep(results)
        return

    engine = ContestedRatingEngine(config)
    snapshots = engine.run(results)
    m = engine.online_metrics('2016-01-01')
    print(
        f"\nOnline rated-pair quality 2016+ (K={config.k_factor:.0f}): "
        f"pairs={m['n_rated_pairs']:,} accuracy={m['pair_accuracy']:.4f} "
        f"log_loss={m['pair_log_loss']:.4f}",
        flush=True,
    )
    save_snapshots(snapshots, args.out)
    print(f"Snapshots: {len(snapshots):,} rows -> {args.out}", flush=True)

    # Sanity 1: top-20 circa 2024-2025
    print("\nTop 20 rated riders as of 2026-01-01 (active 2024+, n>=200):", flush=True)
    top = top_rated(snapshots)
    for i, row in top.iterrows():
        print(
            f"  {i + 1:>2d}. {row['name']:<28s} {row['rating_after']:>7.1f}  "
            f"(n={int(row['n_after']):>5d}, last={pd.Timestamp(row['date']).date()})",
            flush=True,
        )

    # Sanity 2: coverage of as-of-then ratings on 2016+ result rows
    sample = results[results['date'] >= '2016-01-01'][
        ['rider_id', 'competition_id', 'date']
    ].rename(columns={'date': 'competition_date'})
    attached = attach_rating_features(sample, snapshots, db_path=None)
    cov = float(attached['contested_rating'].notna().mean())
    print(f"\nCoverage on 2016+ one_day/stage result rows: {cov:.1%} rated", flush=True)

    # Sanity 3: zero look-ahead
    if not args.skip_validate:
        print("\nNo-look-ahead validation (truncated re-run at 2023-06-01)...", flush=True)
        ok, info = validate_no_lookahead(results, snapshots, config)
        print(f"  {'PASS' if ok else 'FAIL'}: {info}", flush=True)
        if not ok:
            raise SystemExit(1)


if __name__ == '__main__':
    main()
