"""
Form and Team Strength Feature Computation

This module provides core logic for computing:
1. Form Features - Recent performance indicating current fitness/confidence
2. Team Features - Quality distribution of teammates in a race

Key design decisions:
- Form features use a rolling history buffer per rider (last 50 races)
- GC competitions use race start date to avoid including same-race stages
- Same-race exclusion matches both race_id AND year
- Team features use two-pass algorithm within each competition
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import math


# Race-category quality weights for the quality-weighted EMA. Must match
# prediction_tools/experiments/form_feature_lab.py (CV-validated config).
CATEGORY_WEIGHTS = {'wt': 1.0, 'pro': 0.65, 'd1': 0.4}
_DEFAULT_CAT_WEIGHT = 0.4

_LN2 = math.log(2.0)
_EPOCH = datetime(1970, 1, 1)


def _days_since_epoch(date_str: str) -> int:
    return (datetime.strptime(date_str, '%Y-%m-%d') - _EPOCH).days


@dataclass(slots=True)
class RaceHistoryEntry:
    """Single race entry in rider's history."""
    date: str  # YYYY-MM-DD
    bucket: int
    race_id: int
    race_year: int
    comp_type: str  # stage, one_day, gc
    profile: str  # sprint, mountain, hilly, rolling, breakaway, time_trial
    # Fields for the trajectory/EMA form features (2026-06, form_feature_lab
    # v2v3 config). percentile: within-race finishing percentile, 100 = winner;
    # None on legacy rows without one — such entries are excluded from the
    # new features (matching the lab, which drops NULL-percentile rows).
    percentile: Optional[float] = None
    cat_weight: float = _DEFAULT_CAT_WEIGHT
    season: int = 0  # calendar year of `date`
    days: int = 0    # days since epoch for `date`


@dataclass
class RiderFormHistory:
    """
    Maintains rolling history of recent races for form calculation.

    Keeps last MAX_HISTORY_SIZE races per rider for efficient lookback,
    plus never-pruned per-season percentile aggregates for the multi-season
    trajectory features (prev/prev2/peak season lookups).
    """
    rider_id: int
    history: List[RaceHistoryEntry] = field(default_factory=list)
    # Per-season [pct_sum, n] over percentile-bearing races. Tiny (one entry
    # per season raced), so never pruned — needed for peak-season lookback.
    season_pct: Dict[int, List[float]] = field(default_factory=dict)
    # Must exceed any rider's competition count in a 365-day window PLUS the
    # GC offset (window anchored at race start while the buffer extends to
    # race end). Observed max is 115 comps/calendar year (rider 8925, 2010);
    # 250 leaves >2x headroom so the windows never truncate.
    MAX_HISTORY_SIZE: int = 250

    def add_race(
        self,
        date: str,
        bucket: int,
        race_id: int,
        race_year: int,
        comp_type: str,
        profile: str,
        percentile: Optional[float] = None,
        race_category: Optional[str] = None,
    ):
        """Add a race to history, maintaining size limit."""
        if bucket == 7:  # Skip DNF/DNS
            return

        season = int(date[:4])
        entry = RaceHistoryEntry(
            date=date,
            bucket=bucket,
            race_id=race_id,
            race_year=race_year,
            comp_type=comp_type,
            profile=profile,
            percentile=percentile,
            cat_weight=CATEGORY_WEIGHTS.get(race_category, _DEFAULT_CAT_WEIGHT),
            season=season,
            days=_days_since_epoch(date),
        )
        self.history.append(entry)

        if percentile is not None:
            agg = self.season_pct.setdefault(season, [0.0, 0])
            agg[0] += float(percentile)
            agg[1] += 1

        # Maintain size limit
        if len(self.history) > self.MAX_HISTORY_SIZE:
            self.history.pop(0)

    def get_form_features(
        self,
        target_date: str,
        target_year: int,
        target_race_id: int,
        target_comp_type: str,
        target_profile: str,
        race_start_date: Optional[str] = None,
        career_avg_bucket: float = 4.0
    ) -> Dict:
        """
        Calculate form features for this rider at a given competition.

        Args:
            target_date: Date of the target competition (YYYY-MM-DD)
            target_year: Year of the target competition
            target_race_id: Race ID of the target competition
            target_comp_type: Competition type (stage, one_day, gc)
            target_profile: Dominant profile of the target race
            race_start_date: For GC, the race start date (Stage 1/Prologue)
            career_avg_bucket: Rider's career average bucket to date

        Returns:
            Dict with form feature values
        """
        # Determine effective date (for GC, use race start date)
        if target_comp_type == 'gc' and race_start_date:
            effective_date = race_start_date
        else:
            effective_date = target_date

        eff_dt = datetime.strptime(effective_date, '%Y-%m-%d')

        # Window: same year, within 90 days
        min_dt = max(
            eff_dt - timedelta(days=90),
            datetime(target_year, 1, 1)
        )

        # Filter qualifying recent races
        qualifying = []
        for entry in self.history:
            race_dt = datetime.strptime(entry.date, '%Y-%m-%d')

            # Must be before effective date
            if race_dt >= eff_dt:
                continue

            # Must be within window
            if race_dt < min_dt:
                continue

            # For GC targets, exclude stages from same race AND year
            if (target_comp_type == 'gc' and
                entry.race_id == target_race_id and
                entry.race_year == target_year):
                continue

            qualifying.append(entry)

        # Take last 5
        recent_5 = qualifying[-5:] if len(qualifying) >= 5 else qualifying

        # Calculate form features
        if not recent_5:
            return self._default_form_features()

        buckets = [e.bucket for e in recent_5]

        # Days since last race
        last_race_date = datetime.strptime(recent_5[-1].date, '%Y-%m-%d')
        days_since = (eff_dt - last_race_date).days

        # Profile-specific form (matching races only)
        profile_buckets = [e.bucket for e in recent_5 if e.profile == target_profile]

        recent_avg = sum(buckets) / len(buckets)

        return {
            'form_recent_avg_bucket': round(recent_avg, 2),
            'form_recent_best_bucket': min(buckets),
            'form_recent_count': len(recent_5),
            'form_delta': round(recent_avg - career_avg_bucket, 2),
            'form_profile_recent_avg': (
                round(sum(profile_buckets) / len(profile_buckets), 2)
                if profile_buckets else 4.0
            ),
            'days_since_last_race': min(days_since, 365)  # Cap at 365
        }

    @staticmethod
    def _default_form_features() -> Dict:
        """Default form features when no recent races available."""
        return {
            'form_recent_avg_bucket': 4.0,
            'form_recent_best_bucket': 4.0,
            'form_recent_count': 0,
            'form_delta': 0.0,
            'form_profile_recent_avg': 4.0,
            'days_since_last_race': 90  # Cap value
        }

    def get_trajectory_form_features(
        self,
        target_date: str,
        target_year: int,
        target_race_id: int,
        target_comp_type: str,
        race_start_date: Optional[str] = None,
    ) -> Dict:
        """
        EMA-percentile + multi-season trajectory form features (v2v3 config).

        Production twin of prediction_tools/experiments/form_feature_lab.py,
        which cleared the 5-fold CV gate on 2026-06-10 (veteran-bias fix +
        winner capture; see experiment_log.md). Column names are kept
        byte-identical to the validated experiment config. Missing values are
        returned as None (→ NULL in SQLite → NaN in training, where LightGBM
        handles them natively — no imputation by design).

        Semantics replicated from the lab:
        - only races strictly before the effective date count; for GC the
          effective date is the race start date and same-(race_id, year)
          entries are additionally excluded
        - only percentile-bearing entries feed these features
        - prev/prev2/peak seasons come from the never-pruned season
          aggregates; the current-season slice comes from the buffer with
          the exclusion rules applied
        """
        if target_comp_type == 'gc' and race_start_date:
            effective_date = race_start_date
        else:
            effective_date = target_date
        eff_days = _days_since_epoch(effective_date)

        is_gc = target_comp_type == 'gc'
        candidates = [
            e for e in self.history
            if e.percentile is not None
            and e.days < eff_days
            and not (
                is_gc
                and e.race_id == target_race_id
                and e.race_year == target_year
            )
        ]

        out: Dict[str, Optional[float]] = {}

        # ---------------- v2: EMA percentile (365d lookback) ----------------
        win365 = [e for e in candidates if e.days >= eff_days - 365]
        if win365:
            dts = [float(eff_days - e.days) for e in win365]
            pcts = [float(e.percentile) for e in win365]
            buckets = [float(e.bucket) for e in win365]
            catws = [e.cat_weight for e in win365]

            for half_life, col in ((30.0, 'v2_ema_pct_h30'), (60.0, 'v2_ema_pct_h60')):
                ws = [math.exp(-_LN2 * dt / half_life) for dt in dts]
                out[col] = sum(w * p for w, p in zip(ws, pcts)) / sum(ws)

            w60 = [math.exp(-_LN2 * dt / 60.0) for dt in dts]
            sum_w60 = sum(w60)
            wq = [w * c for w, c in zip(w60, catws)]
            out['v2_ema_pct_qw_h60'] = sum(w * p for w, p in zip(wq, pcts)) / sum(wq)
            out['v2_ema_eff_n_h60'] = sum_w60
            out['v2_ema_bucket_h60'] = sum(w * b for w, b in zip(w60, buckets)) / sum_w60
        else:
            out['v2_ema_pct_h30'] = None
            out['v2_ema_pct_h60'] = None
            out['v2_ema_pct_qw_h60'] = None
            out['v2_ema_eff_n_h60'] = 0.0
            out['v2_ema_bucket_h60'] = None

        # ---------------- v3: multi-season trajectory -----------------------
        cur = [float(e.percentile) for e in candidates if e.season == target_year]
        out['v3_season_races_cur'] = len(cur)
        out['v3_season_pct_cur'] = (sum(cur) / len(cur)) if cur else None

        def _season_avg(season: int, min_n: int) -> Optional[float]:
            agg = self.season_pct.get(season)
            if agg and agg[1] >= min_n:
                return agg[0] / agg[1]
            return None

        out['v3_season_pct_prev'] = _season_avg(target_year - 1, min_n=3)
        out['v3_season_pct_prev2'] = _season_avg(target_year - 2, min_n=3)

        out['v3_season_delta'] = (
            out['v3_season_pct_cur'] - out['v3_season_pct_prev']
            if out['v3_season_pct_cur'] is not None and out['v3_season_pct_prev'] is not None
            else None
        )
        out['v3_season_delta_prev'] = (
            out['v3_season_pct_prev'] - out['v3_season_pct_prev2']
            if out['v3_season_pct_prev'] is not None and out['v3_season_pct_prev2'] is not None
            else None
        )

        # Within-365d slope of percentile vs time (pct points per 30 days)
        out['v3_races365'] = len(win365)
        if len(win365) >= 5:
            xs = [float(e.days) for e in win365]
            ys = [float(e.percentile) for e in win365]
            x_mean = sum(xs) / len(xs)
            y_mean = sum(ys) / len(ys)
            sxx = sum((x - x_mean) ** 2 for x in xs)
            if sxx > 0:
                sxy = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
                out['v3_slope365'] = (sxy / sxx) * 30.0
            else:
                out['v3_slope365'] = None
        else:
            out['v3_slope365'] = None

        # Peak completed season (>= 10 races) strictly before the target year
        peak = None
        for season, (pct_sum, n) in self.season_pct.items():
            if season < target_year and n >= 10:
                avg = pct_sum / n
                if peak is None or avg > peak:
                    peak = avg
        out['v3_peak_season_pct'] = peak
        out['v3_decline_from_peak'] = (
            out['v3_season_pct_cur'] - peak
            if peak is not None and out['v3_season_pct_cur'] is not None
            else None
        )

        return out


class TeamFeatureComputer:
    """
    Computes team strength features for riders in a competition.

    Uses two-pass algorithm:
    1. First pass: Collect all rider snapshots
    2. Second pass: Compute team features using collected data
    """

    @staticmethod
    def compute_for_competition(
        rider_snapshots: Dict[int, Dict],
        rider_team_ids: Dict[int, Optional[int]]
    ) -> Dict[int, Dict]:
        """
        Compute team features for all riders in a competition.

        Args:
            rider_snapshots: Dict of rider_id -> snapshot dict with avg buckets
            rider_team_ids: Dict of rider_id -> team_id (may be None)

        Returns:
            Dict of rider_id -> team feature dict
        """
        # Group riders by team
        teams: Dict[int, List[Tuple[int, Dict]]] = defaultdict(list)
        for rider_id, snapshot in rider_snapshots.items():
            team_id = rider_team_ids.get(rider_id)
            if team_id is not None:
                teams[team_id].append((rider_id, snapshot))

        # Compute team features for each rider
        results = {}
        for rider_id, snapshot in rider_snapshots.items():
            team_id = rider_team_ids.get(rider_id)

            if team_id is None or team_id not in teams:
                results[rider_id] = TeamFeatureComputer._default_team_features()
                continue

            # Get teammates (exclude self)
            teammates = [
                (rid, snap) for (rid, snap) in teams[team_id]
                if rid != rider_id
            ]

            if not teammates:
                results[rider_id] = TeamFeatureComputer._default_team_features()
                continue

            # Calculate teammate career averages
            teammate_avgs = []
            for _, snap in teammates:
                avg = TeamFeatureComputer._compute_career_avg(snap)
                teammate_avgs.append(avg)

            results[rider_id] = TeamFeatureComputer._compute_team_stats(teammate_avgs)

        return results

    @staticmethod
    def _compute_career_avg(snapshot: Dict) -> float:
        """Compute weighted career average bucket from snapshot."""
        stage_sum = snapshot.get('stage_avg_bucket', 4.0) * snapshot.get('stage_count', 0)
        one_day_sum = snapshot.get('one_day_avg_bucket', 4.0) * snapshot.get('one_day_count', 0)
        gc_sum = snapshot.get('gc_avg_bucket', 4.0) * snapshot.get('gc_count', 0)

        total_count = (
            snapshot.get('stage_count', 0) +
            snapshot.get('one_day_count', 0) +
            snapshot.get('gc_count', 0)
        )

        if total_count == 0:
            return 4.0  # New rider default

        return (stage_sum + one_day_sum + gc_sum) / total_count

    @staticmethod
    def _compute_team_stats(values: List[float]) -> Dict:
        """Compute distribution stats for teammate quality."""
        if not values:
            return TeamFeatureComputer._default_team_features()

        sorted_vals = sorted(values)
        n = len(sorted_vals)
        mean = sum(values) / n

        return {
            'team_quality_mean': round(mean, 2),
            'team_quality_median': round(TeamFeatureComputer._percentile(sorted_vals, 50), 2),
            'team_quality_std': round(TeamFeatureComputer._std(values, mean), 2),
            'team_quality_min': round(min(values), 2),
            'team_quality_max': round(max(values), 2),
            'team_quality_p25': round(TeamFeatureComputer._percentile(sorted_vals, 25), 2),
            'team_quality_p75': round(TeamFeatureComputer._percentile(sorted_vals, 75), 2),
            'team_size': n,
            'team_depth': sum(1 for v in values if v < 4.0)
        }

    @staticmethod
    def _default_team_features() -> Dict:
        """Default team features when no teammates available."""
        return {
            'team_quality_mean': 4.0,
            'team_quality_median': 4.0,
            'team_quality_std': 0.0,
            'team_quality_min': 4.0,
            'team_quality_max': 4.0,
            'team_quality_p25': 4.0,
            'team_quality_p75': 4.0,
            'team_size': 0,
            'team_depth': 0
        }

    @staticmethod
    def _percentile(sorted_values: List[float], p: float) -> float:
        """Calculate percentile of sorted values."""
        if not sorted_values:
            return 0.0
        n = len(sorted_values)
        k = (n - 1) * p / 100
        f = int(k)
        c = min(f + 1, n - 1)
        return sorted_values[f] + (k - f) * (sorted_values[c] - sorted_values[f])

    @staticmethod
    def _std(values: List[float], mean: float) -> float:
        """Calculate standard deviation."""
        if len(values) < 2:
            return 0.0
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return math.sqrt(variance)


# Feature column definitions for use in other modules
FORM_FEATURE_COLUMNS = [
    'form_recent_avg_bucket',
    'form_recent_best_bucket',
    'form_recent_count',
    'form_delta',
    'form_profile_recent_avg',
    'days_since_last_race',
]

# Trajectory/EMA form features (v2v3 config, CV-validated 2026-06-10).
# Order matters: matches the snapshot table column order and the INSERT in
# feature_precomputation.py. Names deliberately avoid the training-time
# imputation patterns ('avg_bucket', '_count') so NULLs reach LightGBM as
# native missing values.
TRAJECTORY_FORM_COLUMNS = [
    'v2_ema_pct_h30',
    'v2_ema_pct_h60',
    'v2_ema_pct_qw_h60',
    'v2_ema_eff_n_h60',
    'v2_ema_bucket_h60',
    'v3_season_pct_cur',
    'v3_season_pct_prev',
    'v3_season_pct_prev2',
    'v3_season_delta',
    'v3_season_delta_prev',
    'v3_slope365',
    'v3_races365',
    'v3_peak_season_pct',
    'v3_decline_from_peak',
    'v3_season_races_cur',
]

TEAM_FEATURE_COLUMNS = [
    'team_quality_mean',
    'team_quality_median',
    'team_quality_std',
    'team_quality_min',
    'team_quality_max',
    'team_quality_p25',
    'team_quality_p75',
    'team_size',
    'team_depth',
]

ALL_NEW_COLUMNS = FORM_FEATURE_COLUMNS + TEAM_FEATURE_COLUMNS
