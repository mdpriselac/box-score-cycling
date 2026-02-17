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


@dataclass
class RaceHistoryEntry:
    """Single race entry in rider's history."""
    date: str  # YYYY-MM-DD
    bucket: int
    race_id: int
    race_year: int
    comp_type: str  # stage, one_day, gc
    profile: str  # sprint, mountain, hilly, rolling, breakaway, time_trial


@dataclass
class RiderFormHistory:
    """
    Maintains rolling history of recent races for form calculation.

    Keeps last MAX_HISTORY_SIZE races per rider for efficient lookback.
    """
    rider_id: int
    history: List[RaceHistoryEntry] = field(default_factory=list)
    MAX_HISTORY_SIZE: int = 50

    def add_race(
        self,
        date: str,
        bucket: int,
        race_id: int,
        race_year: int,
        comp_type: str,
        profile: str
    ):
        """Add a race to history, maintaining size limit."""
        if bucket == 7:  # Skip DNF/DNS
            return

        entry = RaceHistoryEntry(
            date=date,
            bucket=bucket,
            race_id=race_id,
            race_year=race_year,
            comp_type=comp_type,
            profile=profile
        )
        self.history.append(entry)

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
