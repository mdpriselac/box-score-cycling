"""
Feature Pre-computation Module

Efficiently pre-computes rider and field features for ML training.
Uses incremental processing with checkpointing for resume capability.

Key optimizations:
1. Process chronologically - maintain running state, O(1) updates per result
2. Batch SQL queries - load data for multiple competitions at once
3. Pre-compute race profiles once - reuse for all riders
4. Checkpoint after each batch - resume from where we left off

Tables created:
- rider_features_running: Current running state per rider (sums/counts)
- rider_competition_snapshots: Snapshot of rider features at each competition
- competition_field_features: Field-level aggregates per competition
- feature_computation_checkpoint: Resume tracking
"""

import sqlite3
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import os
import json

try:
    from cycling_project.engineering_tools.place_handling import place_bucketer
    from cycling_project.engineering_tools.race_profile_scoring import (
        calculate_race_profile_scores,
        RaceProfileScores
    )
    from cycling_project.engineering_tools.form_team_features import (
        RiderFormHistory, TeamFeatureComputer
    )
except ModuleNotFoundError:
    from .place_handling import place_bucketer
    from .race_profile_scoring import calculate_race_profile_scores, RaceProfileScores
    from .form_team_features import RiderFormHistory, TeamFeatureComputer

try:
    from dotenv import load_dotenv
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False


@dataclass
class RiderRunningState:
    """Running state for a rider - sums and counts for incremental updates."""
    rider_id: int
    rider_name: str = ""

    # Race type buckets (sum and count for averaging)
    stage_bucket_sum: float = 0.0
    stage_count: int = 0
    one_day_bucket_sum: float = 0.0
    one_day_count: int = 0
    gc_bucket_sum: float = 0.0
    gc_count: int = 0

    # Tour level buckets
    wt_bucket_sum: float = 0.0
    wt_count: int = 0
    pro_bucket_sum: float = 0.0
    pro_count: int = 0
    d1_bucket_sum: float = 0.0
    d1_count: int = 0

    # Profile-weighted buckets (weighted sum and weight sum)
    sprint_weighted_sum: float = 0.0
    sprint_weight_sum: float = 0.0
    mountain_weighted_sum: float = 0.0
    mountain_weight_sum: float = 0.0
    hilly_weighted_sum: float = 0.0
    hilly_weight_sum: float = 0.0
    rolling_weighted_sum: float = 0.0
    rolling_weight_sum: float = 0.0
    breakaway_weighted_sum: float = 0.0
    breakaway_weight_sum: float = 0.0
    time_trial_weighted_sum: float = 0.0
    time_trial_weight_sum: float = 0.0

    # Career tracking
    total_races: int = 0
    races_by_year: Dict[int, int] = field(default_factory=dict)

    def update(
        self,
        bucket: int,
        comp_type: str,
        race_category: str,
        race_year: int,
        race_profile: Optional[RaceProfileScores]
    ):
        """Update running state with a new race result."""
        if bucket is None or bucket == 7:  # Skip DNF/DNS
            return

        self.total_races += 1
        self.races_by_year[race_year] = self.races_by_year.get(race_year, 0) + 1

        # Update by competition type
        if comp_type == 'stage':
            self.stage_bucket_sum += bucket
            self.stage_count += 1
        elif comp_type == 'one_day':
            self.one_day_bucket_sum += bucket
            self.one_day_count += 1
        elif comp_type == 'gc':
            self.gc_bucket_sum += bucket
            self.gc_count += 1

        # Update by race category
        if race_category == 'wt':
            self.wt_bucket_sum += bucket
            self.wt_count += 1
        elif race_category == 'pro':
            self.pro_bucket_sum += bucket
            self.pro_count += 1
        elif race_category == 'd1':
            self.d1_bucket_sum += bucket
            self.d1_count += 1

        # Update profile-weighted (if race profile available)
        if race_profile:
            self.sprint_weighted_sum += bucket * race_profile.sprint
            self.sprint_weight_sum += race_profile.sprint
            self.mountain_weighted_sum += bucket * race_profile.mountain
            self.mountain_weight_sum += race_profile.mountain
            self.hilly_weighted_sum += bucket * race_profile.hilly
            self.hilly_weight_sum += race_profile.hilly
            self.rolling_weighted_sum += bucket * race_profile.rolling
            self.rolling_weight_sum += race_profile.rolling
            self.breakaway_weighted_sum += bucket * race_profile.breakaway
            self.breakaway_weight_sum += race_profile.breakaway
            self.time_trial_weighted_sum += bucket * race_profile.time_trial
            self.time_trial_weight_sum += race_profile.time_trial

    def get_snapshot(self, race_year: int) -> Dict:
        """Get current state as a snapshot dict."""
        def safe_avg(s, c):
            return round(s / c, 2) if c > 0 else 4.0

        def safe_weighted_avg(ws, w):
            return round(ws / w, 2) if w > 0.1 else 4.0

        # Races this year (prior to current race)
        races_this_year = self.races_by_year.get(race_year, 0)

        # Determine best profile
        profile_avgs = {
            'sprint': safe_weighted_avg(self.sprint_weighted_sum, self.sprint_weight_sum),
            'mountain': safe_weighted_avg(self.mountain_weighted_sum, self.mountain_weight_sum),
            'hilly': safe_weighted_avg(self.hilly_weighted_sum, self.hilly_weight_sum),
            'rolling': safe_weighted_avg(self.rolling_weighted_sum, self.rolling_weight_sum),
            'breakaway': safe_weighted_avg(self.breakaway_weighted_sum, self.breakaway_weight_sum),
            'time_trial': safe_weighted_avg(self.time_trial_weighted_sum, self.time_trial_weight_sum),
        }
        # Best profile is lowest bucket average (better performance)
        best_profile = min(profile_avgs, key=profile_avgs.get) if any(
            getattr(self, f'{p}_weight_sum') > 0.1 for p in profile_avgs
        ) else 'unknown'

        return {
            'races_career': self.total_races,
            'races_this_year': races_this_year,
            'stage_avg_bucket': safe_avg(self.stage_bucket_sum, self.stage_count),
            'stage_count': self.stage_count,
            'one_day_avg_bucket': safe_avg(self.one_day_bucket_sum, self.one_day_count),
            'one_day_count': self.one_day_count,
            'gc_avg_bucket': safe_avg(self.gc_bucket_sum, self.gc_count),
            'gc_count': self.gc_count,
            'wt_avg_bucket': safe_avg(self.wt_bucket_sum, self.wt_count),
            'wt_count': self.wt_count,
            'pro_avg_bucket': safe_avg(self.pro_bucket_sum, self.pro_count),
            'pro_count': self.pro_count,
            'd1_avg_bucket': safe_avg(self.d1_bucket_sum, self.d1_count),
            'd1_count': self.d1_count,
            'sprint_avg_bucket': profile_avgs['sprint'],
            'mountain_avg_bucket': profile_avgs['mountain'],
            'hilly_avg_bucket': profile_avgs['hilly'],
            'rolling_avg_bucket': profile_avgs['rolling'],
            'breakaway_avg_bucket': profile_avgs['breakaway'],
            'time_trial_avg_bucket': profile_avgs['time_trial'],
            'best_profile': best_profile,
        }

    def to_db_row(self) -> Tuple:
        """Convert to database row for saving."""
        return (
            self.rider_id,
            self.rider_name,
            self.stage_bucket_sum, self.stage_count,
            self.one_day_bucket_sum, self.one_day_count,
            self.gc_bucket_sum, self.gc_count,
            self.wt_bucket_sum, self.wt_count,
            self.pro_bucket_sum, self.pro_count,
            self.d1_bucket_sum, self.d1_count,
            self.sprint_weighted_sum, self.sprint_weight_sum,
            self.mountain_weighted_sum, self.mountain_weight_sum,
            self.hilly_weighted_sum, self.hilly_weight_sum,
            self.rolling_weighted_sum, self.rolling_weight_sum,
            self.breakaway_weighted_sum, self.breakaway_weight_sum,
            self.time_trial_weighted_sum, self.time_trial_weight_sum,
            self.total_races,
            json.dumps(self.races_by_year)
        )

    @classmethod
    def from_db_row(cls, row) -> 'RiderRunningState':
        """Create from database row."""
        state = cls(rider_id=row[0], rider_name=row[1])
        state.stage_bucket_sum, state.stage_count = row[2], row[3]
        state.one_day_bucket_sum, state.one_day_count = row[4], row[5]
        state.gc_bucket_sum, state.gc_count = row[6], row[7]
        state.wt_bucket_sum, state.wt_count = row[8], row[9]
        state.pro_bucket_sum, state.pro_count = row[10], row[11]
        state.d1_bucket_sum, state.d1_count = row[12], row[13]
        state.sprint_weighted_sum, state.sprint_weight_sum = row[14], row[15]
        state.mountain_weighted_sum, state.mountain_weight_sum = row[16], row[17]
        state.hilly_weighted_sum, state.hilly_weight_sum = row[18], row[19]
        state.rolling_weighted_sum, state.rolling_weight_sum = row[20], row[21]
        state.breakaway_weighted_sum, state.breakaway_weight_sum = row[22], row[23]
        state.time_trial_weighted_sum, state.time_trial_weight_sum = row[24], row[25]
        state.total_races = row[26]
        state.races_by_year = json.loads(row[27]) if row[27] else {}
        return state


class FeaturePrecomputer:
    """
    Pre-computes rider and field features incrementally with checkpointing.
    """

    def __init__(self, db_path: str = None, batch_size: int = 50):
        if db_path is None:
            db_path = self._find_database()
        self.db_path = db_path
        self.batch_size = batch_size
        self.rider_states: Dict[int, RiderRunningState] = {}
        self.race_profiles: Dict[int, RaceProfileScores] = {}
        self.rider_histories: Dict[int, RiderFormHistory] = {}
        self.race_start_dates: Dict[Tuple[int, int], str] = {}  # (race_id, year) -> start_date

    def _find_database(self) -> str:
        """Find the SQLite database file."""
        if HAS_DOTENV:
            load_dotenv()
            db_path = os.getenv('DB_PATH')
            if db_path and os.path.isfile(db_path):
                return db_path

        from pathlib import Path
        possible_paths = [
            Path(__file__).parent.parent / "webscrape_tools" / "database" / "database" / "cycling_races.db",
        ]
        for path in possible_paths:
            if path.exists():
                return str(path)
        raise FileNotFoundError("Database not found")

    def create_tables(self, conn: sqlite3.Connection):
        """Create the feature tables if they don't exist."""
        cursor = conn.cursor()

        # Running state table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rider_features_running (
                rider_id INTEGER PRIMARY KEY,
                rider_name TEXT,
                stage_bucket_sum REAL, stage_count INTEGER,
                one_day_bucket_sum REAL, one_day_count INTEGER,
                gc_bucket_sum REAL, gc_count INTEGER,
                wt_bucket_sum REAL, wt_count INTEGER,
                pro_bucket_sum REAL, pro_count INTEGER,
                d1_bucket_sum REAL, d1_count INTEGER,
                sprint_weighted_sum REAL, sprint_weight_sum REAL,
                mountain_weighted_sum REAL, mountain_weight_sum REAL,
                hilly_weighted_sum REAL, hilly_weight_sum REAL,
                rolling_weighted_sum REAL, rolling_weight_sum REAL,
                breakaway_weighted_sum REAL, breakaway_weight_sum REAL,
                time_trial_weighted_sum REAL, time_trial_weight_sum REAL,
                total_races INTEGER,
                races_by_year TEXT
            )
        """)

        # Snapshot table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rider_competition_snapshots (
                rider_id INTEGER,
                competition_id INTEGER,
                rider_name TEXT,
                age INTEGER,
                team_bib INTEGER,
                personal_bib INTEGER,
                races_career INTEGER,
                races_this_year INTEGER,
                stage_avg_bucket REAL, stage_count INTEGER,
                one_day_avg_bucket REAL, one_day_count INTEGER,
                gc_avg_bucket REAL, gc_count INTEGER,
                wt_avg_bucket REAL, wt_count INTEGER,
                pro_avg_bucket REAL, pro_count INTEGER,
                d1_avg_bucket REAL, d1_count INTEGER,
                sprint_avg_bucket REAL,
                mountain_avg_bucket REAL,
                hilly_avg_bucket REAL,
                rolling_avg_bucket REAL,
                breakaway_avg_bucket REAL,
                time_trial_avg_bucket REAL,
                best_profile TEXT,
                -- Form features
                form_recent_avg_bucket REAL,
                form_recent_best_bucket REAL,
                form_recent_count INTEGER,
                form_delta REAL,
                form_profile_recent_avg REAL,
                days_since_last_race INTEGER,
                -- Team features
                team_quality_mean REAL,
                team_quality_median REAL,
                team_quality_std REAL,
                team_quality_min REAL,
                team_quality_max REAL,
                team_quality_p25 REAL,
                team_quality_p75 REAL,
                team_size INTEGER,
                team_depth INTEGER,
                PRIMARY KEY (rider_id, competition_id)
            )
        """)

        # Field features table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS competition_field_features (
                competition_id INTEGER PRIMARY KEY,
                competition_name TEXT,
                competition_date TEXT,
                competition_type TEXT,
                race_category TEXT,
                field_size INTEGER,
                experience_mean REAL, experience_median REAL, experience_std REAL,
                experience_min REAL, experience_max REAL,
                experience_p25 REAL, experience_p75 REAL,
                bucket_mean REAL, bucket_median REAL, bucket_std REAL,
                bucket_min REAL, bucket_max REAL,
                bucket_p25 REAL, bucket_p75 REAL,
                sprinter_count INTEGER, climber_count INTEGER,
                hilly_specialist_count INTEGER, rolling_specialist_count INTEGER,
                breakaway_specialist_count INTEGER, time_trialist_count INTEGER,
                unknown_profile_count INTEGER
            )
        """)

        # Checkpoint table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feature_computation_checkpoint (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                last_processed_date TEXT,
                last_processed_competition_id INTEGER,
                processed_competitions INTEGER,
                updated_at TEXT
            )
        """)

        conn.commit()

    def load_checkpoint(self, conn: sqlite3.Connection) -> Tuple[Optional[str], int]:
        """Load the last checkpoint."""
        cursor = conn.execute(
            "SELECT last_processed_date, processed_competitions FROM feature_computation_checkpoint WHERE id = 1"
        )
        row = cursor.fetchone()
        if row:
            return row[0], row[1]
        return None, 0

    def save_checkpoint(self, conn: sqlite3.Connection, last_date: str, count: int):
        """Save checkpoint."""
        conn.execute("""
            INSERT OR REPLACE INTO feature_computation_checkpoint
            (id, last_processed_date, processed_competitions, updated_at)
            VALUES (1, ?, ?, ?)
        """, (last_date, count, datetime.now().isoformat()))
        conn.commit()

    def load_rider_states(self, conn: sqlite3.Connection):
        """Load existing rider running states from database."""
        cursor = conn.execute("SELECT * FROM rider_features_running")
        for row in cursor:
            state = RiderRunningState.from_db_row(row)
            self.rider_states[state.rider_id] = state
        print(f"Loaded {len(self.rider_states)} existing rider states")

    def save_rider_states(self, conn: sqlite3.Connection):
        """Save all rider running states to database."""
        cursor = conn.cursor()
        for state in self.rider_states.values():
            cursor.execute("""
                INSERT OR REPLACE INTO rider_features_running VALUES
                (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, state.to_db_row())
        conn.commit()

    def precompute_race_start_dates(self, conn: sqlite3.Connection):
        """Pre-compute race start dates for GC date handling."""
        print("Pre-computing race start dates...")
        cursor = conn.execute("""
            SELECT c.race_id, r.year, MIN(c.date) as start_date
            FROM competitions c
            JOIN races r ON c.race_id = r.id
            WHERE c.competition_type IN ('stage', 'one_day')
            GROUP BY c.race_id, r.year
        """)
        count = 0
        for row in cursor:
            self.race_start_dates[(row[0], row[1])] = row[2]
            count += 1
        print(f"Pre-computed {count} race start dates")

    def _rebuild_rider_histories(self, conn: sqlite3.Connection, up_to_date: str):
        """Rebuild rider form histories from historical data when resuming."""
        print("Rebuilding rider histories from prior data...")
        cursor = conn.execute("""
            SELECT
                rr.rider_id,
                cff.competition_date,
                rr.place_bucket,
                c.race_id,
                r.year,
                cff.competition_type,
                cff.race_dominant_profile
            FROM rider_results rr
            JOIN competition_field_features cff ON rr.competition_id = cff.competition_id
            JOIN competitions c ON rr.competition_id = c.id
            JOIN races r ON c.race_id = r.id
            WHERE cff.competition_date < ?
            AND rr.place_bucket IS NOT NULL
            AND rr.place_bucket != 7
            ORDER BY cff.competition_date
        """, (up_to_date,))

        for row in cursor:
            rider_id, comp_date, place_bucket, race_id, race_year, comp_type, profile = row
            if rider_id not in self.rider_histories:
                self.rider_histories[rider_id] = RiderFormHistory(rider_id=rider_id)
            self.rider_histories[rider_id].add_race(
                date=comp_date,
                bucket=place_bucket,
                race_id=race_id,
                race_year=race_year,
                comp_type=comp_type,
                profile=profile or 'unknown'
            )
        print(f"  Rebuilt histories for {len(self.rider_histories)} riders")

    def _get_race_id_for_competition(self, conn: sqlite3.Connection, comp_id: int) -> int:
        """Get the race_id for a competition."""
        cursor = conn.execute(
            "SELECT race_id FROM competitions WHERE id = ?", (comp_id,)
        )
        row = cursor.fetchone()
        return row[0] if row else 0

    @staticmethod
    def _compute_career_avg(snapshot: Dict) -> float:
        """Compute weighted career average bucket from snapshot."""
        stage_sum = (snapshot.get('stage_avg_bucket') or 4.0) * (snapshot.get('stage_count') or 0)
        one_day_sum = (snapshot.get('one_day_avg_bucket') or 4.0) * (snapshot.get('one_day_count') or 0)
        gc_sum = (snapshot.get('gc_avg_bucket') or 4.0) * (snapshot.get('gc_count') or 0)
        total_count = (
            (snapshot.get('stage_count') or 0) +
            (snapshot.get('one_day_count') or 0) +
            (snapshot.get('gc_count') or 0)
        )
        if total_count == 0:
            return 4.0
        return (stage_sum + one_day_sum + gc_sum) / total_count

    def precompute_race_profiles(self, conn: sqlite3.Connection):
        """Pre-compute all race profiles."""
        print("Pre-computing race profiles...")
        cursor = conn.execute("""
            SELECT
                rfg.competition_id,
                COALESCE(rfg.kurtosis_null_percentile, 0) as breakdown,
                rfg.variance_normalized_slope,
                rfg.clumpiness_score_slope,
                rfg.biggest_group_metric_slope,
                rf100.winning_time
            FROM race_feature_gradients rfg
            JOIN race_features_100 rf100 ON rfg.competition_id = rf100.competition_id
            WHERE rfg.variance_normalized_values IS NOT NULL
        """)

        count = 0
        for row in cursor:
            comp_id, breakdown, var_slope, clump_slope, bg_slope, winning_time = row
            if var_slope is None or clump_slope is None or bg_slope is None:
                continue

            profile = calculate_race_profile_scores(
                breakdown_percentile=breakdown,
                variance_slope=var_slope,
                clumpiness_slope=clump_slope,
                biggest_group_slope=bg_slope,
                winning_time=winning_time
            )
            self.race_profiles[comp_id] = profile
            count += 1

        print(f"Pre-computed {count} race profiles")

    def get_competitions_to_process(
        self,
        conn: sqlite3.Connection,
        start_date: str
    ) -> List[Tuple]:
        """Get competitions to process in chronological order."""
        cursor = conn.execute("""
            SELECT
                c.id, c.name, c.date, c.competition_type, r.category, r.year
            FROM competitions c
            JOIN races r ON c.race_id = r.id
            WHERE c.date >= ?
            AND c.competition_type IN ('stage', 'one_day', 'gc')
            ORDER BY c.date, c.id
        """, (start_date,))
        return cursor.fetchall()

    def get_results_for_competitions(
        self,
        conn: sqlite3.Connection,
        comp_ids: List[int]
    ) -> Dict[int, List[Tuple]]:
        """Batch load results for multiple competitions."""
        if not comp_ids:
            return {}

        placeholders = ','.join(['?' for _ in comp_ids])
        cursor = conn.execute(f"""
            SELECT
                rr.competition_id, rr.rider_id, rr.place,
                rr.rider_age, rr.team_bib, rr.personal_bib,
                r.name as rider_name, rr.team_id
            FROM rider_results rr
            LEFT JOIN riders r ON rr.rider_id = r.id
            WHERE rr.competition_id IN ({placeholders})
            ORDER BY rr.competition_id
        """, comp_ids)

        results: Dict[int, List[Tuple]] = {cid: [] for cid in comp_ids}
        for row in cursor:
            results[row[0]].append(row[1:])  # Skip competition_id in tuple

        return results

    def compute_field_features(
        self,
        comp_id: int,
        comp_name: str,
        comp_date: str,
        comp_type: str,
        race_category: str,
        rider_snapshots: List[Dict],
        race_profile: Optional[RaceProfileScores] = None
    ) -> Tuple:
        """Compute field-level features from rider snapshots."""
        if not rider_snapshots:
            return None

        field_size = len(rider_snapshots)

        # Experience distribution
        experiences = [s['races_career'] for s in rider_snapshots]
        experiences_sorted = sorted(experiences)
        exp_mean = sum(experiences) / len(experiences)
        exp_median = self._percentile(experiences_sorted, 50)
        exp_std = self._std(experiences, exp_mean)

        # Bucket distribution (overall average)
        def overall_bucket(s):
            total_count = s['stage_count'] + s['one_day_count'] + s['gc_count']
            if total_count == 0:
                return 4.0
            weighted = (
                s['stage_avg_bucket'] * s['stage_count'] +
                s['one_day_avg_bucket'] * s['one_day_count'] +
                s['gc_avg_bucket'] * s['gc_count']
            )
            return weighted / total_count

        buckets = [overall_bucket(s) for s in rider_snapshots]
        buckets_sorted = sorted(buckets)
        bucket_mean = sum(buckets) / len(buckets)
        bucket_median = self._percentile(buckets_sorted, 50)
        bucket_std = self._std(buckets, bucket_mean)

        # Profile composition
        profile_counts = {
            'sprint': 0, 'mountain': 0, 'hilly': 0,
            'rolling': 0, 'breakaway': 0, 'time_trial': 0, 'unknown': 0
        }
        for s in rider_snapshots:
            profile = s.get('best_profile', 'unknown')
            if profile in profile_counts:
                profile_counts[profile] += 1
            else:
                profile_counts['unknown'] += 1

        # Race profile scores
        if race_profile:
            race_sprint = round(race_profile.sprint, 3)
            race_mountain = round(race_profile.mountain, 3)
            race_hilly = round(race_profile.hilly, 3)
            race_rolling = round(race_profile.rolling, 3)
            race_breakaway = round(race_profile.breakaway, 3)
            race_time_trial = round(race_profile.time_trial, 3)
            race_dominant = race_profile.dominant_type()
        else:
            race_sprint = race_mountain = race_hilly = None
            race_rolling = race_breakaway = race_time_trial = None
            race_dominant = 'unknown'

        return (
            comp_id, comp_name, comp_date, comp_type, race_category,
            field_size,
            round(exp_mean, 1), round(exp_median, 1), round(self._std(experiences, exp_mean), 1),
            min(experiences), max(experiences),
            round(self._percentile(experiences_sorted, 25), 1),
            round(self._percentile(experiences_sorted, 75), 1),
            round(bucket_mean, 2), round(bucket_median, 2), round(bucket_std, 2),
            round(min(buckets), 2), round(max(buckets), 2),
            round(self._percentile(buckets_sorted, 25), 2),
            round(self._percentile(buckets_sorted, 75), 2),
            profile_counts['sprint'], profile_counts['mountain'],
            profile_counts['hilly'], profile_counts['rolling'],
            profile_counts['breakaway'], profile_counts['time_trial'],
            profile_counts['unknown'],
            race_sprint, race_mountain, race_hilly,
            race_rolling, race_breakaway, race_time_trial,
            race_dominant
        )

    @staticmethod
    def _percentile(sorted_values: List[float], p: float) -> float:
        if not sorted_values:
            return 0.0
        k = (len(sorted_values) - 1) * p / 100
        f = int(k)
        c = min(f + 1, len(sorted_values) - 1)
        return sorted_values[f] + (k - f) * (sorted_values[c] - sorted_values[f])

    @staticmethod
    def _std(values: List[float], mean: float) -> float:
        if len(values) < 2:
            return 0.0
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return variance ** 0.5

    def run(self, start_date: str = '2018-01-01', resume: bool = True):
        """
        Run the feature pre-computation.

        Args:
            start_date: Start processing from this date
            resume: If True, resume from last checkpoint
        """
        print("=" * 70)
        print("FEATURE PRE-COMPUTATION")
        print("=" * 70)
        print(f"Database: {self.db_path}")
        print(f"Start date: {start_date}")
        print(f"Batch size: {self.batch_size}")
        print()

        conn = sqlite3.connect(self.db_path)

        try:
            # Create tables
            self.create_tables(conn)

            # Load checkpoint if resuming
            if resume:
                checkpoint_date, processed_count = self.load_checkpoint(conn)
                if checkpoint_date:
                    start_date = checkpoint_date
                    print(f"Resuming from checkpoint: {checkpoint_date} ({processed_count} competitions processed)")
                    self.load_rider_states(conn)
            else:
                processed_count = 0

            # Pre-compute race profiles and start dates
            self.precompute_race_profiles(conn)
            self.precompute_race_start_dates(conn)

            # Load rider histories if resuming
            if resume and processed_count > 0:
                self._rebuild_rider_histories(conn, start_date)

            # Get competitions to process
            competitions = self.get_competitions_to_process(conn, start_date)
            total_comps = len(competitions)
            print(f"Found {total_comps} competitions to process")

            # Process in batches
            for batch_start in range(0, total_comps, self.batch_size):
                batch = competitions[batch_start:batch_start + self.batch_size]
                batch_comp_ids = [c[0] for c in batch]

                # Load results for batch
                results = self.get_results_for_competitions(conn, batch_comp_ids)

                # Process each competition
                snapshot_rows = []
                field_feature_rows = []

                for comp_id, comp_name, comp_date, comp_type, race_cat, race_year in batch:
                    comp_results = results.get(comp_id, [])
                    race_profile = self.race_profiles.get(comp_id)
                    race_profile_name = race_profile.dominant_type() if race_profile else 'unknown'

                    # Get race start date for GC handling
                    race_id = self._get_race_id_for_competition(conn, comp_id)
                    race_start_date = self.race_start_dates.get((race_id, race_year), comp_date)

                    rider_snapshots = []
                    rider_data_list = []  # Store data for form/team computation

                    # PASS 1: Create all rider snapshots
                    for rider_id, place, age, team_bib, personal_bib, rider_name, team_id in comp_results:
                        # Get or create rider state
                        if rider_id not in self.rider_states:
                            self.rider_states[rider_id] = RiderRunningState(
                                rider_id=rider_id,
                                rider_name=rider_name or ""
                            )

                        state = self.rider_states[rider_id]
                        if rider_name:
                            state.rider_name = rider_name

                        # Get snapshot BEFORE updating
                        snapshot = state.get_snapshot(race_year)
                        snapshot['rider_name'] = state.rider_name
                        snapshot['age'] = age
                        snapshot['team_bib'] = team_bib
                        snapshot['personal_bib'] = personal_bib
                        snapshot['rider_id'] = rider_id
                        rider_snapshots.append(snapshot)

                        # Store additional data for later
                        rider_data_list.append({
                            'rider_id': rider_id,
                            'place': place,
                            'team_id': team_id,
                            'snapshot': snapshot,
                            'state': state,
                        })

                    # PASS 2: Compute form and team features
                    # Build team mapping for team features
                    rider_team_ids = {d['rider_id']: d['team_id'] for d in rider_data_list}
                    snapshot_dict = {d['rider_id']: d['snapshot'] for d in rider_data_list}
                    team_features = TeamFeatureComputer.compute_for_competition(
                        snapshot_dict, rider_team_ids
                    )

                    # Compute form features and save rows
                    for data in rider_data_list:
                        rider_id = data['rider_id']
                        snapshot = data['snapshot']
                        place = data['place']

                        # Get or create form history
                        if rider_id not in self.rider_histories:
                            self.rider_histories[rider_id] = RiderFormHistory(rider_id=rider_id)
                        history = self.rider_histories[rider_id]

                        # Compute career average for form delta
                        career_avg = self._compute_career_avg(snapshot)

                        # Compute form features
                        form = history.get_form_features(
                            target_date=comp_date,
                            target_year=race_year,
                            target_race_id=race_id,
                            target_comp_type=comp_type,
                            target_profile=race_profile_name,
                            race_start_date=race_start_date if comp_type == 'gc' else None,
                            career_avg_bucket=career_avg
                        )

                        # Get team features
                        team = team_features.get(rider_id, TeamFeatureComputer._default_team_features())

                        # Save snapshot row with all features (42 columns)
                        snapshot_rows.append((
                            rider_id, comp_id, snapshot['rider_name'],
                            snapshot['age'], snapshot['team_bib'], snapshot['personal_bib'],
                            snapshot['races_career'], snapshot['races_this_year'],
                            snapshot['stage_avg_bucket'], snapshot['stage_count'],
                            snapshot['one_day_avg_bucket'], snapshot['one_day_count'],
                            snapshot['gc_avg_bucket'], snapshot['gc_count'],
                            snapshot['wt_avg_bucket'], snapshot['wt_count'],
                            snapshot['pro_avg_bucket'], snapshot['pro_count'],
                            snapshot['d1_avg_bucket'], snapshot['d1_count'],
                            snapshot['sprint_avg_bucket'], snapshot['mountain_avg_bucket'],
                            snapshot['hilly_avg_bucket'], snapshot['rolling_avg_bucket'],
                            snapshot['breakaway_avg_bucket'], snapshot['time_trial_avg_bucket'],
                            snapshot['best_profile'],
                            # Form features (6)
                            form['form_recent_avg_bucket'], form['form_recent_best_bucket'],
                            form['form_recent_count'], form['form_delta'],
                            form['form_profile_recent_avg'], form['days_since_last_race'],
                            # Team features (9)
                            team['team_quality_mean'], team['team_quality_median'],
                            team['team_quality_std'], team['team_quality_min'],
                            team['team_quality_max'], team['team_quality_p25'],
                            team['team_quality_p75'], team['team_size'], team['team_depth']
                        ))

                        # Update running state with this race result
                        bucket = place_bucketer(place)
                        data['state'].update(bucket, comp_type, race_cat, race_year, race_profile)

                        # Update form history AFTER computing features
                        if bucket is not None and bucket != 7:
                            history.add_race(
                                date=comp_date,
                                bucket=bucket,
                                race_id=race_id,
                                race_year=race_year,
                                comp_type=comp_type,
                                profile=race_profile_name
                            )

                    # Compute field features
                    if rider_snapshots:
                        field_row = self.compute_field_features(
                            comp_id, comp_name, comp_date, comp_type, race_cat,
                            rider_snapshots, race_profile
                        )
                        if field_row:
                            field_feature_rows.append(field_row)

                # Save batch to database
                cursor = conn.cursor()
                cursor.executemany("""
                    INSERT OR REPLACE INTO rider_competition_snapshots VALUES
                    (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, snapshot_rows)

                cursor.executemany("""
                    INSERT OR REPLACE INTO competition_field_features VALUES
                    (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, field_feature_rows)

                # Save rider states and checkpoint
                self.save_rider_states(conn)
                last_date = batch[-1][2]  # comp_date of last in batch
                processed_count += len(batch)
                self.save_checkpoint(conn, last_date, processed_count)

                print(f"Processed {processed_count}/{total_comps} competitions "
                      f"({100*processed_count/total_comps:.1f}%) - last date: {last_date}")

            print()
            print("=" * 70)
            print("PRE-COMPUTATION COMPLETE")
            print("=" * 70)
            print(f"Processed {processed_count} competitions")
            print(f"Tracked {len(self.rider_states)} riders")

        finally:
            conn.close()


def main():
    """Run feature pre-computation."""
    import sys

    start_date = '2018-01-01'
    if len(sys.argv) > 1:
        start_date = sys.argv[1]

    precomputer = FeaturePrecomputer(batch_size=100)
    precomputer.run(start_date=start_date, resume=True)


if __name__ == "__main__":
    main()
