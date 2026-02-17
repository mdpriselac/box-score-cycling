"""
Rider Performance by Race Profile Module

Analyzes how riders perform in different race types (sprint, mountain, hilly, etc.)
based on historical results weighted by race profile scores.

Integrates with race_profile_scoring to enable predictions based on expected race profiles.
"""

import sqlite3
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import os

try:
    from cycling_project.engineering_tools.race_profile_scoring import (
        calculate_race_profile_scores,
        RaceProfileScores,
        create_expected_race_profile
    )
    from cycling_project.engineering_tools.place_handling import place_bucketer
except ModuleNotFoundError:
    from .race_profile_scoring import (
        calculate_race_profile_scores,
        RaceProfileScores,
        create_expected_race_profile
    )
    from .place_handling import place_bucketer

try:
    from dotenv import load_dotenv
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False


@dataclass
class RiderProfilePerformance:
    """
    Container for a rider's performance across race profiles.

    Each score represents weighted average percentile (0-100, higher is better)
    weighted by how strongly each race matched that profile type.
    """
    rider_id: int
    rider_name: str = ""

    # Weighted average percentile by race type
    sprint_avg: float = 50.0
    mountain_avg: float = 50.0
    hilly_avg: float = 50.0
    rolling_avg: float = 50.0
    breakaway_avg: float = 50.0
    time_trial_avg: float = 50.0

    # Count of races with significant weight for each type
    sprint_races: int = 0
    mountain_races: int = 0
    hilly_races: int = 0
    rolling_races: int = 0
    breakaway_races: int = 0
    time_trial_races: int = 0

    # Total races analyzed
    total_races: int = 0

    def best_profile(self) -> str:
        """Return the profile type where rider performs best."""
        performances = {
            'sprint': self.sprint_avg,
            'mountain': self.mountain_avg,
            'hilly': self.hilly_avg,
            'rolling': self.rolling_avg,
            'breakaway': self.breakaway_avg,
            'time_trial': self.time_trial_avg
        }
        return max(performances, key=performances.get)

    def predict_percentile(self, expected_profile: RaceProfileScores) -> float:
        """
        Predict expected percentile finish given a race profile.

        Args:
            expected_profile: RaceProfileScores for the expected race

        Returns:
            Predicted percentile (0-100, higher is better)
        """
        weighted_sum = (
            expected_profile.sprint * self.sprint_avg +
            expected_profile.mountain * self.mountain_avg +
            expected_profile.hilly * self.hilly_avg +
            expected_profile.rolling * self.rolling_avg +
            expected_profile.breakaway * self.breakaway_avg +
            expected_profile.time_trial * self.time_trial_avg
        )
        return round(weighted_sum, 2)

    def predict_bucket(self, expected_profile: RaceProfileScores) -> int:
        """
        Predict expected place bucket (0-7) given a race profile.

        Converts predicted percentile to place bucket.
        """
        percentile = self.predict_percentile(expected_profile)
        # Convert percentile to approximate place for bucketing
        # Percentile 100 = 1st place, 50 = middle, 0 = last
        approx_place = int((100 - percentile) / 100 * 150) + 1
        return place_bucketer(approx_place)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'rider_id': self.rider_id,
            'rider_name': self.rider_name,
            'sprint_avg': self.sprint_avg,
            'mountain_avg': self.mountain_avg,
            'hilly_avg': self.hilly_avg,
            'rolling_avg': self.rolling_avg,
            'breakaway_avg': self.breakaway_avg,
            'time_trial_avg': self.time_trial_avg,
            'sprint_races': self.sprint_races,
            'mountain_races': self.mountain_races,
            'hilly_races': self.hilly_races,
            'rolling_races': self.rolling_races,
            'breakaway_races': self.breakaway_races,
            'time_trial_races': self.time_trial_races,
            'total_races': self.total_races,
            'best_profile': self.best_profile()
        }


class RiderProfileAnalyzer:
    """
    Analyzes rider performance across different race profiles.

    Usage:
        analyzer = RiderProfileAnalyzer()

        # Get rider's performance profile
        perf = analyzer.get_rider_performance(rider_id=123, prior_to_date='2024-07-01')
        print(f"Best in: {perf.best_profile()}")
        print(f"Mountain avg: {perf.mountain_avg}th percentile")

        # Predict for upcoming race
        expected = create_expected_race_profile(mountain=0.6, rolling=0.4)
        predicted = perf.predict_percentile(expected)
        print(f"Predicted finish: {predicted}th percentile")
    """

    def __init__(self, db_path: str = None):
        """Initialize with database connection."""
        if db_path is None:
            db_path = self._find_database()
        self.db_path = db_path

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

    def get_rider_performance(
        self,
        rider_id: int,
        prior_to_date: str = None,
        prior_to_year: int = None,
        min_races: int = 5,
        competition_types: List[str] = None
    ) -> Optional[RiderProfilePerformance]:
        """
        Calculate rider's weighted performance across race profiles.

        Args:
            rider_id: The rider's ID
            prior_to_date: Only include races before this date (YYYY-MM-DD)
            prior_to_year: Only include races before this year
            min_races: Minimum races required to return results
            competition_types: Filter by competition types (default: ['stage', 'one_day'])

        Returns:
            RiderProfilePerformance or None if insufficient data
        """
        if competition_types is None:
            competition_types = ['stage', 'one_day']

        # Build date filter
        date_filter = ""
        params = [rider_id]

        if prior_to_date:
            date_filter = "AND rfg.race_date < ?"
            params.append(prior_to_date)
        elif prior_to_year:
            date_filter = "AND rfg.race_year < ?"
            params.append(prior_to_year)

        # Competition type filter
        type_placeholders = ','.join(['?' for _ in competition_types])
        params.extend(competition_types)

        query = f"""
        SELECT
            rr.rider_id,
            r.name as rider_name,
            rr.percentile,
            rr.place,
            COALESCE(rfg.kurtosis_null_percentile, 0) as breakdown,
            rfg.variance_normalized_slope,
            rfg.clumpiness_score_slope,
            rfg.biggest_group_metric_slope,
            rfg.race_name,
            rfg.competition_name,
            rfg.race_year,
            rf100.winning_time
        FROM rider_results rr
        JOIN race_feature_gradients rfg ON rr.competition_id = rfg.competition_id
        JOIN race_features_100 rf100 ON rfg.competition_id = rf100.competition_id
        LEFT JOIN riders r ON rr.rider_id = r.fc_rider_id
        WHERE rr.rider_id = ?
        {date_filter}
        AND rfg.variance_normalized_values IS NOT NULL
        AND rfg.competition_type IN ({type_placeholders})
        AND rr.percentile IS NOT NULL
        ORDER BY rfg.race_date DESC
        """

        results = []
        rider_name = ""

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, params)
            for row in cursor:
                (rid, rname, percentile, place, breakdown,
                 var_slope, clump_slope, bg_slope,
                 race_name, comp_name, race_year, winning_time) = row

                if rname:
                    rider_name = rname

                if var_slope is None or clump_slope is None or bg_slope is None:
                    continue

                # Calculate race profile scores (includes TT detection via winning_time)
                profile = calculate_race_profile_scores(
                    breakdown_percentile=breakdown,
                    variance_slope=var_slope,
                    clumpiness_slope=clump_slope,
                    biggest_group_slope=bg_slope,
                    winning_time=winning_time
                )

                results.append({
                    'percentile': percentile,
                    'place': place,
                    'profile': profile
                })

        if len(results) < min_races:
            return None

        # Calculate weighted averages
        sprint_sum, sprint_weight = 0.0, 0.0
        mountain_sum, mountain_weight = 0.0, 0.0
        hilly_sum, hilly_weight = 0.0, 0.0
        rolling_sum, rolling_weight = 0.0, 0.0
        breakaway_sum, breakaway_weight = 0.0, 0.0
        time_trial_sum, time_trial_weight = 0.0, 0.0

        sprint_races = 0
        mountain_races = 0
        hilly_races = 0
        rolling_races = 0
        breakaway_races = 0
        time_trial_races = 0

        for r in results:
            pct = r['percentile']
            p = r['profile']

            sprint_sum += pct * p.sprint
            sprint_weight += p.sprint
            if p.sprint >= 0.2:
                sprint_races += 1

            mountain_sum += pct * p.mountain
            mountain_weight += p.mountain
            if p.mountain >= 0.2:
                mountain_races += 1

            hilly_sum += pct * p.hilly
            hilly_weight += p.hilly
            if p.hilly >= 0.2:
                hilly_races += 1

            rolling_sum += pct * p.rolling
            rolling_weight += p.rolling
            if p.rolling >= 0.2:
                rolling_races += 1

            breakaway_sum += pct * p.breakaway
            breakaway_weight += p.breakaway
            if p.breakaway >= 0.2:
                breakaway_races += 1

            time_trial_sum += pct * p.time_trial
            time_trial_weight += p.time_trial
            if p.time_trial >= 0.2:
                time_trial_races += 1

        # Calculate weighted averages (default to 50 if no weight)
        def safe_avg(s, w):
            return round(s / w, 2) if w > 0.1 else 50.0

        return RiderProfilePerformance(
            rider_id=rider_id,
            rider_name=rider_name,
            sprint_avg=safe_avg(sprint_sum, sprint_weight),
            mountain_avg=safe_avg(mountain_sum, mountain_weight),
            hilly_avg=safe_avg(hilly_sum, hilly_weight),
            rolling_avg=safe_avg(rolling_sum, rolling_weight),
            breakaway_avg=safe_avg(breakaway_sum, breakaway_weight),
            time_trial_avg=safe_avg(time_trial_sum, time_trial_weight),
            sprint_races=sprint_races,
            mountain_races=mountain_races,
            hilly_races=hilly_races,
            rolling_races=rolling_races,
            breakaway_races=breakaway_races,
            time_trial_races=time_trial_races,
            total_races=len(results)
        )

    def get_riders_performance_bulk(
        self,
        rider_ids: List[int],
        prior_to_date: str = None,
        prior_to_year: int = None,
        min_races: int = 5
    ) -> Dict[int, RiderProfilePerformance]:
        """
        Get performance profiles for multiple riders.

        Returns dict mapping rider_id to RiderProfilePerformance (includes TT performance).
        """
        results = {}
        for rider_id in rider_ids:
            perf = self.get_rider_performance(
                rider_id=rider_id,
                prior_to_date=prior_to_date,
                prior_to_year=prior_to_year,
                min_races=min_races
            )
            if perf is not None:
                results[rider_id] = perf
        return results

    def predict_race_results(
        self,
        rider_ids: List[int],
        expected_profile: RaceProfileScores,
        prior_to_date: str = None,
        prior_to_year: int = None
    ) -> List[Dict]:
        """
        Predict race results for a start list given an expected race profile.

        Args:
            rider_ids: List of rider IDs on the start list
            expected_profile: Expected race profile scores
            prior_to_date: Only use historical data before this date
            prior_to_year: Only use historical data before this year

        Returns:
            List of dicts with rider predictions, sorted by predicted percentile (best first)
        """
        predictions = []

        for rider_id in rider_ids:
            perf = self.get_rider_performance(
                rider_id=rider_id,
                prior_to_date=prior_to_date,
                prior_to_year=prior_to_year,
                min_races=3  # Lower threshold for prediction
            )

            if perf is None:
                # No historical data - use default
                predictions.append({
                    'rider_id': rider_id,
                    'rider_name': 'Unknown',
                    'predicted_percentile': 50.0,
                    'predicted_bucket': 4,
                    'confidence': 'low',
                    'total_races': 0
                })
            else:
                pred_pct = perf.predict_percentile(expected_profile)
                pred_bucket = perf.predict_bucket(expected_profile)

                confidence = 'high' if perf.total_races >= 20 else 'medium' if perf.total_races >= 10 else 'low'

                predictions.append({
                    'rider_id': rider_id,
                    'rider_name': perf.rider_name,
                    'predicted_percentile': pred_pct,
                    'predicted_bucket': pred_bucket,
                    'confidence': confidence,
                    'total_races': perf.total_races,
                    'best_profile': perf.best_profile(),
                    'sprint_avg': perf.sprint_avg,
                    'mountain_avg': perf.mountain_avg,
                    'hilly_avg': perf.hilly_avg,
                    'rolling_avg': perf.rolling_avg,
                    'breakaway_avg': perf.breakaway_avg,
                    'time_trial_avg': perf.time_trial_avg
                })

        # Sort by predicted percentile (best first)
        predictions.sort(key=lambda x: x['predicted_percentile'], reverse=True)

        # Add predicted place
        for i, pred in enumerate(predictions):
            pred['predicted_place'] = i + 1

        return predictions

    def compare_riders(
        self,
        rider_ids: List[int],
        prior_to_date: str = None
    ) -> Dict:
        """
        Compare multiple riders across all race profiles.

        Returns comparison summary with rankings per profile type.
        """
        performances = self.get_riders_performance_bulk(
            rider_ids=rider_ids,
            prior_to_date=prior_to_date
        )

        if not performances:
            return {'error': 'No rider data found'}

        # Rank riders by each profile type
        rankings = {
            'sprint': [],
            'mountain': [],
            'hilly': [],
            'rolling': [],
            'breakaway': [],
            'time_trial': []
        }

        for profile_type in rankings:
            sorted_riders = sorted(
                performances.items(),
                key=lambda x: getattr(x[1], f'{profile_type}_avg'),
                reverse=True
            )
            rankings[profile_type] = [
                {
                    'rider_id': rid,
                    'rider_name': perf.rider_name,
                    'avg_percentile': getattr(perf, f'{profile_type}_avg'),
                    'race_count': getattr(perf, f'{profile_type}_races')
                }
                for rid, perf in sorted_riders
            ]

        return {
            'rankings': rankings,
            'rider_count': len(performances)
        }


# Convenience function for quick predictions
def predict_race(
    rider_ids: List[int],
    sprint: float = 0,
    mountain: float = 0,
    hilly: float = 0,
    rolling: float = 0,
    breakaway: float = 0,
    time_trial: float = 0,
    prior_to_date: str = None
) -> List[Dict]:
    """
    Quick function to predict race results.

    Args:
        rider_ids: List of rider IDs
        sprint/mountain/hilly/rolling/breakaway/time_trial: Expected race profile weights
        prior_to_date: Only use historical data before this date

    Returns:
        Sorted list of predictions (best first)
    """
    profile = create_expected_race_profile(
        sprint=sprint,
        mountain=mountain,
        hilly=hilly,
        rolling=rolling,
        breakaway=breakaway,
        time_trial=time_trial
    )

    analyzer = RiderProfileAnalyzer()
    return analyzer.predict_race_results(
        rider_ids=rider_ids,
        expected_profile=profile,
        prior_to_date=prior_to_date
    )
