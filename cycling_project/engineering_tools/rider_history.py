"""
Rider History Module

Provides complete rider state at any point in time, including:
- Individual data: age, team_bib, personal_bib, races to date
- Race type performance: one_day, stage, gc bucket averages
- Race tour performance: wt, pro, d1 bucket averages
- Profile performance: sprint, mountain, hilly, rolling, breakaway, time_trial bucket averages

Integrates with rider_profile_performance for profile-based metrics.
"""

import sqlite3
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import date
import os

try:
    from cycling_project.engineering_tools.place_handling import place_bucketer
    from cycling_project.engineering_tools.rider_profile_performance import (
        RiderProfileAnalyzer,
        RiderProfilePerformance
    )
except ModuleNotFoundError:
    from .place_handling import place_bucketer
    from .rider_profile_performance import RiderProfileAnalyzer, RiderProfilePerformance

try:
    from dotenv import load_dotenv
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False


@dataclass
class RiderSnapshot:
    """
    Complete rider state at a point in time.

    Bucket scale (0-7, lower is better):
    - 0: Winner (1st place)
    - 1: Podium (2nd-3rd)
    - 2: Top 5 (4th-5th)
    - 3: Top 15 (6th-15th)
    - 4: Top 30 (16th-30th)
    - 5: Top 50 (31st-50th)
    - 6: Finish over 50 (51st+)
    - 7: DNF/OTL/DNS
    """
    rider_id: int
    rider_name: str
    snapshot_date: str  # YYYY-MM-DD format

    # Individual Data
    age: Optional[int] = None
    team_bib: Optional[int] = None
    personal_bib: Optional[int] = None
    races_this_year: int = 0
    races_career: int = 0

    # Race Type Performance (bucket averages, 0-7 scale, lower=better)
    one_day_avg_bucket: float = 4.0
    stage_avg_bucket: float = 4.0
    gc_avg_bucket: float = 4.0
    one_day_count: int = 0
    stage_count: int = 0
    gc_count: int = 0

    # Race Tour Performance (bucket averages)
    wt_avg_bucket: float = 4.0
    pro_avg_bucket: float = 4.0
    d1_avg_bucket: float = 4.0
    wt_count: int = 0
    pro_count: int = 0
    d1_count: int = 0

    # Profile Performance (bucket averages, from rider_profile_performance.py)
    sprint_avg_bucket: float = 4.0
    mountain_avg_bucket: float = 4.0
    hilly_avg_bucket: float = 4.0
    rolling_avg_bucket: float = 4.0
    breakaway_avg_bucket: float = 4.0
    time_trial_avg_bucket: float = 4.0
    best_profile: str = "unknown"

    # UCI Points (stored but not used for field strength)
    total_prior_uci_points: int = 0
    prior_wt_proportion: float = 0.0

    def overall_avg_bucket(self) -> float:
        """Return overall average bucket across all race types."""
        total_count = self.one_day_count + self.stage_count + self.gc_count
        if total_count == 0:
            return 4.0
        weighted_sum = (
            self.one_day_avg_bucket * self.one_day_count +
            self.stage_avg_bucket * self.stage_count +
            self.gc_avg_bucket * self.gc_count
        )
        return round(weighted_sum / total_count, 2)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'rider_id': self.rider_id,
            'rider_name': self.rider_name,
            'snapshot_date': self.snapshot_date,
            'age': self.age,
            'team_bib': self.team_bib,
            'personal_bib': self.personal_bib,
            'races_this_year': self.races_this_year,
            'races_career': self.races_career,
            'one_day_avg_bucket': self.one_day_avg_bucket,
            'stage_avg_bucket': self.stage_avg_bucket,
            'gc_avg_bucket': self.gc_avg_bucket,
            'one_day_count': self.one_day_count,
            'stage_count': self.stage_count,
            'gc_count': self.gc_count,
            'wt_avg_bucket': self.wt_avg_bucket,
            'pro_avg_bucket': self.pro_avg_bucket,
            'd1_avg_bucket': self.d1_avg_bucket,
            'wt_count': self.wt_count,
            'pro_count': self.pro_count,
            'd1_count': self.d1_count,
            'sprint_avg_bucket': self.sprint_avg_bucket,
            'mountain_avg_bucket': self.mountain_avg_bucket,
            'hilly_avg_bucket': self.hilly_avg_bucket,
            'rolling_avg_bucket': self.rolling_avg_bucket,
            'breakaway_avg_bucket': self.breakaway_avg_bucket,
            'time_trial_avg_bucket': self.time_trial_avg_bucket,
            'best_profile': self.best_profile,
            'total_prior_uci_points': self.total_prior_uci_points,
            'prior_wt_proportion': self.prior_wt_proportion,
            'overall_avg_bucket': self.overall_avg_bucket()
        }


class RiderHistoryAnalyzer:
    """
    Analyzes rider history at any point in time.

    Usage:
        analyzer = RiderHistoryAnalyzer()

        # Get rider's state before a specific date
        snapshot = analyzer.get_rider_snapshot(rider_id=123, prior_to_date='2024-07-01')
        print(f"Career races: {snapshot.races_career}")
        print(f"Stage avg bucket: {snapshot.stage_avg_bucket}")

        # Get all riders for a competition
        snapshots = analyzer.get_riders_for_competition(competition_id=12345)
    """

    def __init__(self, db_path: str = None):
        """Initialize with database connection."""
        if db_path is None:
            db_path = self._find_database()
        self.db_path = db_path
        self._profile_analyzer = None

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
    def profile_analyzer(self) -> RiderProfileAnalyzer:
        """Lazy load profile analyzer."""
        if self._profile_analyzer is None:
            self._profile_analyzer = RiderProfileAnalyzer(self.db_path)
        return self._profile_analyzer

    def get_rider_snapshot(
        self,
        rider_id: int,
        prior_to_date: str,
        competition_id: Optional[int] = None
    ) -> Optional[RiderSnapshot]:
        """
        Get complete rider state prior to a specific date.

        Args:
            rider_id: The rider's ID
            prior_to_date: Only include races before this date (YYYY-MM-DD)
            competition_id: If provided, also get bib info from this competition

        Returns:
            RiderSnapshot or None if rider not found
        """
        with sqlite3.connect(self.db_path) as conn:
            # Get rider name
            cursor = conn.execute(
                "SELECT name FROM riders WHERE fc_rider_id = ?",
                (rider_id,)
            )
            row = cursor.fetchone()
            rider_name = row[0] if row else "Unknown"

            # Get race type performance (one_day, stage, gc)
            type_performance = self._calculate_type_performance(conn, rider_id, prior_to_date)

            # Get race tour performance (wt, pro, d1)
            tour_performance = self._calculate_tour_performance(conn, rider_id, prior_to_date)

            # Get year-to-date race count
            year = prior_to_date[:4]
            cursor = conn.execute("""
                SELECT COUNT(*)
                FROM rider_results rr
                JOIN competitions c ON rr.competition_id = c.id
                WHERE rr.rider_id = ?
                AND strftime('%Y', c.date) = ?
                AND c.date < ?
            """, (rider_id, year, prior_to_date))
            races_this_year = cursor.fetchone()[0]

            # Get total career races
            cursor = conn.execute("""
                SELECT COUNT(*)
                FROM rider_results rr
                JOIN competitions c ON rr.competition_id = c.id
                WHERE rr.rider_id = ?
                AND c.date < ?
            """, (rider_id, prior_to_date))
            races_career = cursor.fetchone()[0]

            # Get age and bib info from the most recent result before date
            age = None
            team_bib = None
            personal_bib = None

            if competition_id:
                # Get bib from specific competition
                cursor = conn.execute("""
                    SELECT rider_age, team_bib, personal_bib
                    FROM rider_results
                    WHERE rider_id = ? AND competition_id = ?
                """, (rider_id, competition_id))
                row = cursor.fetchone()
                if row:
                    age, team_bib, personal_bib = row
            else:
                # Get from most recent result
                cursor = conn.execute("""
                    SELECT rr.rider_age, rr.team_bib, rr.personal_bib
                    FROM rider_results rr
                    JOIN competitions c ON rr.competition_id = c.id
                    WHERE rr.rider_id = ?
                    AND c.date < ?
                    ORDER BY c.date DESC
                    LIMIT 1
                """, (rider_id, prior_to_date))
                row = cursor.fetchone()
                if row:
                    age, team_bib, personal_bib = row

            # Get UCI points info
            cursor = conn.execute("""
                SELECT
                    COALESCE(SUM(total_prior_points_actual), 0),
                    COALESCE(AVG(prior_wt_proportion), 0)
                FROM rider_results rr
                JOIN competitions c ON rr.competition_id = c.id
                WHERE rr.rider_id = ?
                AND c.date < ?
                ORDER BY c.date DESC
                LIMIT 1
            """, (rider_id, prior_to_date))
            row = cursor.fetchone()
            total_prior_uci_points = row[0] if row else 0
            prior_wt_proportion = row[1] if row else 0.0

        # Get profile performance (uses RiderProfileAnalyzer)
        profile_perf = self._get_profile_performance(rider_id, prior_to_date)

        return RiderSnapshot(
            rider_id=rider_id,
            rider_name=rider_name,
            snapshot_date=prior_to_date,
            age=age,
            team_bib=team_bib,
            personal_bib=personal_bib,
            races_this_year=races_this_year,
            races_career=races_career,
            one_day_avg_bucket=type_performance['one_day_avg'],
            stage_avg_bucket=type_performance['stage_avg'],
            gc_avg_bucket=type_performance['gc_avg'],
            one_day_count=type_performance['one_day_count'],
            stage_count=type_performance['stage_count'],
            gc_count=type_performance['gc_count'],
            wt_avg_bucket=tour_performance['wt_avg'],
            pro_avg_bucket=tour_performance['pro_avg'],
            d1_avg_bucket=tour_performance['d1_avg'],
            wt_count=tour_performance['wt_count'],
            pro_count=tour_performance['pro_count'],
            d1_count=tour_performance['d1_count'],
            sprint_avg_bucket=profile_perf['sprint_avg'],
            mountain_avg_bucket=profile_perf['mountain_avg'],
            hilly_avg_bucket=profile_perf['hilly_avg'],
            rolling_avg_bucket=profile_perf['rolling_avg'],
            breakaway_avg_bucket=profile_perf['breakaway_avg'],
            time_trial_avg_bucket=profile_perf['time_trial_avg'],
            best_profile=profile_perf['best_profile'],
            total_prior_uci_points=total_prior_uci_points,
            prior_wt_proportion=prior_wt_proportion
        )

    def _calculate_type_performance(
        self,
        conn: sqlite3.Connection,
        rider_id: int,
        prior_to_date: str
    ) -> Dict:
        """Calculate average bucket by competition type (one_day, stage, gc)."""
        cursor = conn.execute("""
            SELECT c.competition_type, rr.place
            FROM rider_results rr
            JOIN competitions c ON rr.competition_id = c.id
            WHERE rr.rider_id = ?
            AND c.date < ?
            AND rr.place IS NOT NULL
        """, (rider_id, prior_to_date))

        type_buckets = {'one_day': [], 'stage': [], 'gc': []}

        for row in cursor:
            comp_type, place = row
            bucket = place_bucketer(place)
            if bucket is not None and comp_type in type_buckets:
                type_buckets[comp_type].append(bucket)

        def safe_avg(lst):
            return round(sum(lst) / len(lst), 2) if lst else 4.0

        return {
            'one_day_avg': safe_avg(type_buckets['one_day']),
            'stage_avg': safe_avg(type_buckets['stage']),
            'gc_avg': safe_avg(type_buckets['gc']),
            'one_day_count': len(type_buckets['one_day']),
            'stage_count': len(type_buckets['stage']),
            'gc_count': len(type_buckets['gc'])
        }

    def _calculate_tour_performance(
        self,
        conn: sqlite3.Connection,
        rider_id: int,
        prior_to_date: str
    ) -> Dict:
        """Calculate average bucket by race category (wt, pro, d1)."""
        cursor = conn.execute("""
            SELECT r.category, rr.place
            FROM rider_results rr
            JOIN competitions c ON rr.competition_id = c.id
            JOIN races r ON c.race_id = r.id
            WHERE rr.rider_id = ?
            AND c.date < ?
            AND rr.place IS NOT NULL
        """, (rider_id, prior_to_date))

        tour_buckets = {'wt': [], 'pro': [], 'd1': []}

        for row in cursor:
            category, place = row
            bucket = place_bucketer(place)
            if bucket is not None and category in tour_buckets:
                tour_buckets[category].append(bucket)

        def safe_avg(lst):
            return round(sum(lst) / len(lst), 2) if lst else 4.0

        return {
            'wt_avg': safe_avg(tour_buckets['wt']),
            'pro_avg': safe_avg(tour_buckets['pro']),
            'd1_avg': safe_avg(tour_buckets['d1']),
            'wt_count': len(tour_buckets['wt']),
            'pro_count': len(tour_buckets['pro']),
            'd1_count': len(tour_buckets['d1'])
        }

    def _get_profile_performance(
        self,
        rider_id: int,
        prior_to_date: str
    ) -> Dict:
        """Get profile performance from RiderProfileAnalyzer."""
        perf = self.profile_analyzer.get_rider_performance(
            rider_id=rider_id,
            prior_to_date=prior_to_date,
            min_races=1
        )

        if perf is None:
            return {
                'sprint_avg': 4.0,
                'mountain_avg': 4.0,
                'hilly_avg': 4.0,
                'rolling_avg': 4.0,
                'breakaway_avg': 4.0,
                'time_trial_avg': 4.0,
                'best_profile': 'unknown'
            }

        # Convert percentile to bucket (approximation)
        # Percentile 100 = best = bucket 0, percentile 0 = worst = bucket 6
        def percentile_to_bucket(pct: float) -> float:
            # Linear mapping: 100->0, 0->6
            bucket = (100 - pct) / 100 * 6
            return round(min(max(bucket, 0), 6), 2)

        return {
            'sprint_avg': percentile_to_bucket(perf.sprint_avg),
            'mountain_avg': percentile_to_bucket(perf.mountain_avg),
            'hilly_avg': percentile_to_bucket(perf.hilly_avg),
            'rolling_avg': percentile_to_bucket(perf.rolling_avg),
            'breakaway_avg': percentile_to_bucket(perf.breakaway_avg),
            'time_trial_avg': percentile_to_bucket(perf.time_trial_avg),
            'best_profile': perf.best_profile()
        }

    def get_riders_for_competition(
        self,
        competition_id: int
    ) -> Dict[int, RiderSnapshot]:
        """
        Get rider snapshots for all riders in a competition.

        Args:
            competition_id: The competition ID

        Returns:
            Dict mapping rider_id to RiderSnapshot
        """
        with sqlite3.connect(self.db_path) as conn:
            # Get competition date
            cursor = conn.execute(
                "SELECT date FROM competitions WHERE id = ?",
                (competition_id,)
            )
            row = cursor.fetchone()
            if not row:
                return {}
            comp_date = row[0]

            # Get all rider IDs for this competition
            cursor = conn.execute(
                "SELECT DISTINCT rider_id FROM rider_results WHERE competition_id = ?",
                (competition_id,)
            )
            rider_ids = [row[0] for row in cursor.fetchall()]

        # Get snapshots for each rider
        snapshots = {}
        for rider_id in rider_ids:
            snapshot = self.get_rider_snapshot(
                rider_id=rider_id,
                prior_to_date=comp_date,
                competition_id=competition_id
            )
            if snapshot:
                snapshots[rider_id] = snapshot

        return snapshots

    def get_riders_bulk(
        self,
        rider_ids: List[int],
        prior_to_date: str
    ) -> Dict[int, RiderSnapshot]:
        """
        Get rider snapshots for multiple riders.

        Args:
            rider_ids: List of rider IDs
            prior_to_date: Only include races before this date (YYYY-MM-DD)

        Returns:
            Dict mapping rider_id to RiderSnapshot
        """
        snapshots = {}
        for rider_id in rider_ids:
            snapshot = self.get_rider_snapshot(
                rider_id=rider_id,
                prior_to_date=prior_to_date
            )
            if snapshot:
                snapshots[rider_id] = snapshot
        return snapshots
