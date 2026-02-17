"""
Race Field History Module

Provides aggregate field metrics for any race, including:
- Field strength: average experience, average historical bucket performance
- Field composition: distribution of rider profile types (sprinters, climbers, etc.)
- Deviation from typical fields to identify specialized start lists

Integrates with rider_history for individual rider snapshots.
"""

import sqlite3
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import os

try:
    from cycling_project.engineering_tools.rider_history import (
        RiderHistoryAnalyzer,
        RiderSnapshot
    )
except ModuleNotFoundError:
    from .rider_history import RiderHistoryAnalyzer, RiderSnapshot

try:
    from dotenv import load_dotenv
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False


@dataclass
class FieldStrengthMetrics:
    """
    Aggregate field strength metrics with numerical distributions.

    Bucket scale (0-7, lower = stronger):
    - 0: Winner level
    - 1: Podium level
    - 2: Top 5 level
    - 3: Top 15 level
    - 4: Top 30 level
    - 5: Top 50 level
    - 6: Finisher level
    """
    competition_id: int
    competition_name: str
    field_size: int

    # Experience Distribution (prior races)
    experience_mean: float
    experience_median: float
    experience_std: float
    experience_min: float
    experience_max: float
    experience_p25: float  # 25th percentile
    experience_p75: float  # 75th percentile

    # Quality Distribution (historical bucket, 0-7 scale)
    bucket_mean: float      # Lower = stronger field
    bucket_median: float
    bucket_std: float
    bucket_min: float
    bucket_max: float
    bucket_p25: float       # 25th percentile
    bucket_p75: float       # 75th percentile

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'competition_id': self.competition_id,
            'competition_name': self.competition_name,
            'field_size': self.field_size,
            'experience_mean': self.experience_mean,
            'experience_median': self.experience_median,
            'experience_std': self.experience_std,
            'experience_min': self.experience_min,
            'experience_max': self.experience_max,
            'experience_p25': self.experience_p25,
            'experience_p75': self.experience_p75,
            'bucket_mean': self.bucket_mean,
            'bucket_median': self.bucket_median,
            'bucket_std': self.bucket_std,
            'bucket_min': self.bucket_min,
            'bucket_max': self.bucket_max,
            'bucket_p25': self.bucket_p25,
            'bucket_p75': self.bucket_p75
        }


@dataclass
class FieldProfileComposition:
    """
    Breakdown of rider profile types in a field.

    Profile types are determined by each rider's best_profile from their
    historical race performance across different race profiles.
    """
    competition_id: int
    field_size: int

    # Counts by dominant profile
    sprinter_count: int = 0
    climber_count: int = 0
    hilly_specialist_count: int = 0
    rolling_specialist_count: int = 0
    breakaway_specialist_count: int = 0
    time_trialist_count: int = 0
    unknown_count: int = 0

    # Baseline proportions (typical field composition)
    _baseline: Dict[str, float] = None

    def __post_init__(self):
        if self._baseline is None:
            # Typical field composition (will be calculated from data)
            self._baseline = {
                'sprint': 0.20,
                'mountain': 0.15,
                'hilly': 0.20,
                'rolling': 0.25,
                'breakaway': 0.10,
                'time_trial': 0.05,
                'unknown': 0.05
            }

    @property
    def sprinter_pct(self) -> float:
        return self.sprinter_count / self.field_size if self.field_size > 0 else 0

    @property
    def climber_pct(self) -> float:
        return self.climber_count / self.field_size if self.field_size > 0 else 0

    @property
    def hilly_specialist_pct(self) -> float:
        return self.hilly_specialist_count / self.field_size if self.field_size > 0 else 0

    @property
    def rolling_specialist_pct(self) -> float:
        return self.rolling_specialist_count / self.field_size if self.field_size > 0 else 0

    @property
    def breakaway_specialist_pct(self) -> float:
        return self.breakaway_specialist_count / self.field_size if self.field_size > 0 else 0

    @property
    def time_trialist_pct(self) -> float:
        return self.time_trialist_count / self.field_size if self.field_size > 0 else 0

    @property
    def sprinter_deviation(self) -> float:
        return self.sprinter_pct - self._baseline['sprint']

    @property
    def climber_deviation(self) -> float:
        return self.climber_pct - self._baseline['mountain']

    @property
    def hilly_specialist_deviation(self) -> float:
        return self.hilly_specialist_pct - self._baseline['hilly']

    @property
    def rolling_specialist_deviation(self) -> float:
        return self.rolling_specialist_pct - self._baseline['rolling']

    @property
    def breakaway_specialist_deviation(self) -> float:
        return self.breakaway_specialist_pct - self._baseline['breakaway']

    @property
    def time_trialist_deviation(self) -> float:
        return self.time_trialist_pct - self._baseline['time_trial']

    def is_sprinter_heavy(self, threshold: float = 0.05) -> bool:
        """Check if field has more sprinters than typical."""
        return self.sprinter_deviation > threshold

    def is_climber_heavy(self, threshold: float = 0.05) -> bool:
        """Check if field has more climbers than typical."""
        return self.climber_deviation > threshold

    def is_hilly_specialist_heavy(self, threshold: float = 0.05) -> bool:
        """Check if field has more hilly specialists than typical."""
        return self.hilly_specialist_deviation > threshold

    def is_breakaway_specialist_heavy(self, threshold: float = 0.05) -> bool:
        """Check if field has more breakaway specialists than typical."""
        return self.breakaway_specialist_deviation > threshold

    def is_time_trialist_heavy(self, threshold: float = 0.05) -> bool:
        """Check if field has more time trialists than typical."""
        return self.time_trialist_deviation > threshold

    def dominant_type_skew(self, threshold: float = 0.05) -> Optional[str]:
        """
        Return the profile type that is most over-represented.

        Args:
            threshold: Minimum deviation to be considered "heavy"

        Returns:
            Profile type name or None if field is balanced
        """
        deviations = {
            'sprint': self.sprinter_deviation,
            'mountain': self.climber_deviation,
            'hilly': self.hilly_specialist_deviation,
            'rolling': self.rolling_specialist_deviation,
            'breakaway': self.breakaway_specialist_deviation,
            'time_trial': self.time_trialist_deviation
        }
        max_type = max(deviations, key=deviations.get)
        if deviations[max_type] > threshold:
            return max_type
        return None

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'competition_id': self.competition_id,
            'field_size': self.field_size,
            'sprinter_count': self.sprinter_count,
            'climber_count': self.climber_count,
            'hilly_specialist_count': self.hilly_specialist_count,
            'rolling_specialist_count': self.rolling_specialist_count,
            'breakaway_specialist_count': self.breakaway_specialist_count,
            'time_trialist_count': self.time_trialist_count,
            'unknown_count': self.unknown_count,
            'sprinter_pct': round(self.sprinter_pct, 3),
            'climber_pct': round(self.climber_pct, 3),
            'hilly_specialist_pct': round(self.hilly_specialist_pct, 3),
            'rolling_specialist_pct': round(self.rolling_specialist_pct, 3),
            'breakaway_specialist_pct': round(self.breakaway_specialist_pct, 3),
            'time_trialist_pct': round(self.time_trialist_pct, 3),
            'sprinter_deviation': round(self.sprinter_deviation, 3),
            'climber_deviation': round(self.climber_deviation, 3),
            'hilly_specialist_deviation': round(self.hilly_specialist_deviation, 3),
            'rolling_specialist_deviation': round(self.rolling_specialist_deviation, 3),
            'breakaway_specialist_deviation': round(self.breakaway_specialist_deviation, 3),
            'time_trialist_deviation': round(self.time_trialist_deviation, 3),
            'is_sprinter_heavy': self.is_sprinter_heavy(),
            'is_climber_heavy': self.is_climber_heavy(),
            'dominant_type_skew': self.dominant_type_skew()
        }


@dataclass
class FieldSummary:
    """Combined field strength and composition summary."""
    strength: FieldStrengthMetrics
    composition: FieldProfileComposition

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'strength': self.strength.to_dict(),
            'composition': self.composition.to_dict()
        }


class RaceFieldAnalyzer:
    """
    Analyzes race field strength and composition.

    Usage:
        analyzer = RaceFieldAnalyzer()

        # Get field strength for a competition
        strength = analyzer.get_field_strength(competition_id=12345)
        print(f"Field size: {strength.field_size}")
        print(f"Experience: mean={strength.experience_mean}, std={strength.experience_std}")
        print(f"Bucket: mean={strength.bucket_mean}, p25={strength.bucket_p25}")

        # Get field profile composition
        composition = analyzer.get_field_profile_composition(competition_id=12345)
        print(f"Sprinter heavy: {composition.is_sprinter_heavy()}")

        # Get combined summary
        summary = analyzer.get_field_summary(competition_id=12345)
    """

    def __init__(self, db_path: str = None):
        """Initialize with database connection."""
        if db_path is None:
            db_path = self._find_database()
        self.db_path = db_path
        self._rider_analyzer = None
        self._baseline_composition = None

    def _find_database(self) -> str:
        """Find the SQLite database file."""
        if HAS_DOTENV:
            load_dotenv()
            db_path = os.getenv('DB_PATH')
            if db_path and os.path.exists(db_path):
                return db_path

        from pathlib import Path
        possible_paths = [
            Path(__file__).parent.parent / "webscrape_tools" / "database" / "database" / "cycling_races.db",
            Path(__file__).parent.parent / "database" / "database" / "cycling_races.db",
            Path(__file__).parent.parent / "cycling_races.db",
        ]
        for path in possible_paths:
            if path.exists():
                return str(path)

        raise FileNotFoundError("Database not found")

    @property
    def rider_analyzer(self) -> RiderHistoryAnalyzer:
        """Lazy load rider analyzer."""
        if self._rider_analyzer is None:
            self._rider_analyzer = RiderHistoryAnalyzer(self.db_path)
        return self._rider_analyzer

    def get_field_strength(self, competition_id: int) -> Optional[FieldStrengthMetrics]:
        """
        Get field strength metrics for a competition.

        Args:
            competition_id: The competition ID

        Returns:
            FieldStrengthMetrics or None if competition not found
        """
        with sqlite3.connect(self.db_path) as conn:
            # Get competition info
            cursor = conn.execute("""
                SELECT c.name, c.date
                FROM competitions c
                WHERE c.id = ?
            """, (competition_id,))
            row = cursor.fetchone()
            if not row:
                return None
            competition_name, comp_date = row

            # Get all experience values for distribution calculation
            cursor = conn.execute("""
                SELECT total_prior_races
                FROM rider_results
                WHERE competition_id = ?
                AND total_prior_races IS NOT NULL
            """, (competition_id,))
            experience_values = [row[0] for row in cursor.fetchall()]

        if not experience_values:
            return None

        field_size = len(experience_values)

        # Get rider snapshots to calculate bucket distribution
        snapshots = self.rider_analyzer.get_riders_for_competition(competition_id)

        if not snapshots:
            return None

        # Collect bucket values
        bucket_values = [s.overall_avg_bucket() for s in snapshots.values()]

        # Calculate experience distribution stats
        experience_values_sorted = sorted(experience_values)
        exp_mean = sum(experience_values) / len(experience_values)
        exp_median = self._percentile(experience_values_sorted, 50)
        exp_std = self._std(experience_values, exp_mean)
        exp_min = min(experience_values)
        exp_max = max(experience_values)
        exp_p25 = self._percentile(experience_values_sorted, 25)
        exp_p75 = self._percentile(experience_values_sorted, 75)

        # Calculate bucket distribution stats
        bucket_values_sorted = sorted(bucket_values)
        bucket_mean = sum(bucket_values) / len(bucket_values)
        bucket_median = self._percentile(bucket_values_sorted, 50)
        bucket_std = self._std(bucket_values, bucket_mean)
        bucket_min = min(bucket_values)
        bucket_max = max(bucket_values)
        bucket_p25 = self._percentile(bucket_values_sorted, 25)
        bucket_p75 = self._percentile(bucket_values_sorted, 75)

        return FieldStrengthMetrics(
            competition_id=competition_id,
            competition_name=competition_name,
            field_size=field_size,
            experience_mean=round(exp_mean, 1),
            experience_median=round(exp_median, 1),
            experience_std=round(exp_std, 1),
            experience_min=round(exp_min, 1),
            experience_max=round(exp_max, 1),
            experience_p25=round(exp_p25, 1),
            experience_p75=round(exp_p75, 1),
            bucket_mean=round(bucket_mean, 2),
            bucket_median=round(bucket_median, 2),
            bucket_std=round(bucket_std, 2),
            bucket_min=round(bucket_min, 2),
            bucket_max=round(bucket_max, 2),
            bucket_p25=round(bucket_p25, 2),
            bucket_p75=round(bucket_p75, 2)
        )

    @staticmethod
    def _percentile(sorted_values: List[float], p: float) -> float:
        """Calculate percentile from sorted values."""
        if not sorted_values:
            return 0.0
        k = (len(sorted_values) - 1) * p / 100
        f = int(k)
        c = f + 1 if f + 1 < len(sorted_values) else f
        return sorted_values[f] + (k - f) * (sorted_values[c] - sorted_values[f])

    @staticmethod
    def _std(values: List[float], mean: float) -> float:
        """Calculate standard deviation."""
        if len(values) < 2:
            return 0.0
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return variance ** 0.5

    def get_field_profile_composition(
        self,
        competition_id: int
    ) -> Optional[FieldProfileComposition]:
        """
        Get profile type breakdown for a competition field.

        Args:
            competition_id: The competition ID

        Returns:
            FieldProfileComposition or None if competition not found
        """
        # Get rider snapshots
        snapshots = self.rider_analyzer.get_riders_for_competition(competition_id)

        if not snapshots:
            return None

        # Count by profile type
        counts = {
            'sprint': 0,
            'mountain': 0,
            'hilly': 0,
            'rolling': 0,
            'breakaway': 0,
            'time_trial': 0,
            'unknown': 0
        }

        for snapshot in snapshots.values():
            profile = snapshot.best_profile
            if profile in counts:
                counts[profile] += 1
            else:
                counts['unknown'] += 1

        # Get baseline (or calculate it)
        baseline = self._get_typical_field_composition()

        return FieldProfileComposition(
            competition_id=competition_id,
            field_size=len(snapshots),
            sprinter_count=counts['sprint'],
            climber_count=counts['mountain'],
            hilly_specialist_count=counts['hilly'],
            rolling_specialist_count=counts['rolling'],
            breakaway_specialist_count=counts['breakaway'],
            time_trialist_count=counts['time_trial'],
            unknown_count=counts['unknown'],
            _baseline=baseline
        )

    def get_field_summary(self, competition_id: int) -> Optional[FieldSummary]:
        """
        Get combined field strength and composition summary.

        Args:
            competition_id: The competition ID

        Returns:
            FieldSummary or None if competition not found
        """
        strength = self.get_field_strength(competition_id)
        composition = self.get_field_profile_composition(competition_id)

        if strength is None or composition is None:
            return None

        return FieldSummary(strength=strength, composition=composition)

    def _get_typical_field_composition(self) -> Dict[str, float]:
        """
        Get baseline field composition for comparison.

        Returns typical proportions of each profile type in race fields.
        """
        if self._baseline_composition is not None:
            return self._baseline_composition

        # Default baseline (can be calculated from data later)
        self._baseline_composition = {
            'sprint': 0.20,
            'mountain': 0.15,
            'hilly': 0.20,
            'rolling': 0.25,
            'breakaway': 0.10,
            'time_trial': 0.05,
            'unknown': 0.05
        }
        return self._baseline_composition

    def calculate_baseline_composition(
        self,
        sample_competitions: int = 100
    ) -> Dict[str, float]:
        """
        Calculate baseline field composition from sample of competitions.

        Args:
            sample_competitions: Number of competitions to sample

        Returns:
            Dict of profile type to proportion
        """
        with sqlite3.connect(self.db_path) as conn:
            # Get random sample of competitions
            cursor = conn.execute("""
                SELECT id FROM competitions
                WHERE competition_type IN ('stage', 'one_day')
                ORDER BY RANDOM()
                LIMIT ?
            """, (sample_competitions,))
            comp_ids = [row[0] for row in cursor.fetchall()]

        # Aggregate profile counts
        total_counts = {
            'sprint': 0,
            'mountain': 0,
            'hilly': 0,
            'rolling': 0,
            'breakaway': 0,
            'time_trial': 0,
            'unknown': 0
        }
        total_riders = 0

        for comp_id in comp_ids:
            composition = self.get_field_profile_composition(comp_id)
            if composition:
                total_counts['sprint'] += composition.sprinter_count
                total_counts['mountain'] += composition.climber_count
                total_counts['hilly'] += composition.hilly_specialist_count
                total_counts['rolling'] += composition.rolling_specialist_count
                total_counts['breakaway'] += composition.breakaway_specialist_count
                total_counts['time_trial'] += composition.time_trialist_count
                total_counts['unknown'] += composition.unknown_count
                total_riders += composition.field_size

        if total_riders > 0:
            self._baseline_composition = {
                k: round(v / total_riders, 3)
                for k, v in total_counts.items()
            }
        else:
            self._baseline_composition = self._get_typical_field_composition()

        return self._baseline_composition

    def compare_fields(
        self,
        competition_ids: List[int]
    ) -> List[Dict]:
        """
        Compare field strength and composition across multiple competitions.

        Args:
            competition_ids: List of competition IDs to compare

        Returns:
            List of field summary dicts
        """
        results = []
        for comp_id in competition_ids:
            summary = self.get_field_summary(comp_id)
            if summary:
                result = summary.to_dict()
                result['competition_id'] = comp_id
                results.append(result)
        return results
