"""
Race Profile Scoring Module

Converts race gradient features into interpretable race type scores.
Each race gets a score (0-1) for each category, with scores summing to 1.

Categories:
- SPRINT: Bunch sprint finish, late breakdown, low variance growth
- MOUNTAIN: Selective race, no breakdown, high variance growth
- HILLY: Mid-race selection, increasing clumpiness
- ROLLING: Moderate selection, no breakdown, gradual variance growth
- BREAKAWAY: Early breakdown, negative biggest_group slope

Based on empirical analysis of finishing time distribution gradients.
"""

import math
from typing import Dict, Optional, Tuple, Union
from dataclasses import dataclass
import sqlite3
import os

try:
    from dotenv import load_dotenv
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False


@dataclass
class RaceProfileScores:
    """Container for race profile scores."""
    sprint: float
    mountain: float
    hilly: float
    rolling: float
    breakaway: float
    time_trial: float = 0.0  # Added: TT races identified by winning_time < 90 min

    def dominant_type(self) -> str:
        """Return the category with highest score."""
        scores = {
            'sprint': self.sprint,
            'mountain': self.mountain,
            'hilly': self.hilly,
            'rolling': self.rolling,
            'breakaway': self.breakaway,
            'time_trial': self.time_trial
        }
        return max(scores, key=scores.get)

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            'sprint': self.sprint,
            'mountain': self.mountain,
            'hilly': self.hilly,
            'rolling': self.rolling,
            'breakaway': self.breakaway,
            'time_trial': self.time_trial
        }

    def significant_types(self, threshold: float = 0.2) -> Dict[str, float]:
        """Return types with score above threshold."""
        return {k: v for k, v in self.to_dict().items() if v >= threshold}


def _sigmoid(x: float, center: float = 0, steepness: float = 1) -> float:
    """Sigmoid function centered at `center` with given steepness."""
    try:
        return 1.0 / (1.0 + math.exp(-steepness * (x - center)))
    except OverflowError:
        return 0.0 if x < center else 1.0


def _gaussian(x: float, center: float, width: float) -> float:
    """Gaussian function centered at `center` with given width."""
    return math.exp(-width * (x - center) ** 2)


def _safe_log10(x: float, floor: float = 1e-12) -> float:
    """Safe log10 that handles small/zero values."""
    return math.log10(max(x, floor))


def calculate_race_profile_scores(
    breakdown_percentile: float,
    variance_slope: float,
    clumpiness_slope: float,
    biggest_group_slope: float,
    normalize: bool = True,
    winning_time: float = None
) -> RaceProfileScores:
    """
    Calculate race profile scores from gradient features.

    Args:
        breakdown_percentile: kurtosis_null_percentile (0-100, 0 means no breakdown)
        variance_slope: variance_normalized_slope (typically 1e-8 to 1e-4)
        clumpiness_slope: clumpiness_score_slope (typically -0.008 to 0.011)
        biggest_group_slope: biggest_group_metric_slope (typically -0.015 to 0.008)
        normalize: If True, normalize scores to sum to 1
        winning_time: Race winning time in seconds. If < 4200 (70 min), classified as time trial

    Returns:
        RaceProfileScores with score for each category
    """
    # TIME TRIAL: Identified by short winning time (< 70 minutes)
    if winning_time is not None and winning_time < 4200:
        return RaceProfileScores(
            sprint=0.0,
            mountain=0.0,
            hilly=0.0,
            rolling=0.0,
            breakaway=0.0,
            time_trial=1.0
        )

    # Handle edge cases
    breakdown = breakdown_percentile or 0
    log_var_slope = _safe_log10(variance_slope)

    # SPRINT: High breakdown + low variance slope
    # - Breakdown sigmoid centered at 50% (most of field together)
    # - Variance slope sigmoid (low slope = high score)
    sprint_raw = (
        _sigmoid(breakdown, center=50, steepness=0.1) *
        _sigmoid(-log_var_slope, center=6, steepness=2.0)
    )

    # MOUNTAIN: No breakdown + high variance slope
    # - Penalize any breakdown exponentially
    # - Variance slope sigmoid (high slope = high score)
    breakdown_penalty = 1.0 if breakdown == 0 else math.exp(-0.05 * breakdown)
    mountain_raw = (
        breakdown_penalty *
        _sigmoid(log_var_slope, center=-5, steepness=2.0)
    )

    # HILLY: Mid breakdown + increasing clumpiness
    # - Gaussian centered at 35% breakdown (sweet spot for hilly stages)
    # - Clumpiness slope sigmoid (increasing clumps = high score)
    hilly_raw = (
        _gaussian(breakdown, center=35, width=0.005) *
        _sigmoid(clumpiness_slope, center=0.004, steepness=400)
    )

    # ROLLING: No breakdown + moderate variance slope
    # - Penalize breakdown
    # - Gaussian centered at log(var_slope) = -5.5 (moderate growth)
    breakdown_penalty_rolling = 1.0 if breakdown == 0 else math.exp(-0.1 * breakdown)
    rolling_raw = (
        breakdown_penalty_rolling *
        _gaussian(log_var_slope, center=-5.5, width=0.5)
    )

    # BREAKAWAY: Early breakdown + very negative biggest_group slope
    # - Gaussian centered at 18% breakdown (early selection)
    # - Biggest group slope sigmoid (negative = group fragments = high score)
    breakaway_raw = (
        _gaussian(breakdown, center=18, width=0.01) *
        _sigmoid(-biggest_group_slope, center=0.005, steepness=500)
    )

    # Normalize to sum to 1 (time_trial = 0 for non-TT races)
    if normalize:
        total = sprint_raw + mountain_raw + hilly_raw + rolling_raw + breakaway_raw + 1e-10
        sprint = sprint_raw / total
        mountain = mountain_raw / total
        hilly = hilly_raw / total
        rolling = rolling_raw / total
        breakaway = breakaway_raw / total
    else:
        sprint = sprint_raw
        mountain = mountain_raw
        hilly = hilly_raw
        rolling = rolling_raw
        breakaway = breakaway_raw

    return RaceProfileScores(
        sprint=round(sprint, 4),
        mountain=round(mountain, 4),
        hilly=round(hilly, 4),
        rolling=round(rolling, 4),
        breakaway=round(breakaway, 4),
        time_trial=0.0
    )


class RaceProfileScorer:
    """
    Scores races from the database on profile dimensions.

    Usage:
        scorer = RaceProfileScorer()
        scores = scorer.score_race(competition_id=12345)
        print(scores.dominant_type())  # 'mountain'
        print(scores.to_dict())  # {'sprint': 0.02, 'mountain': 0.65, ...}
    """

    def __init__(self, db_path: str = None):
        """Initialize with database connection."""
        if db_path is None:
            db_path = self._find_database()
        self.db_path = db_path

    def _find_database(self) -> str:
        """Find the SQLite database file."""
        override = os.environ.get('CYCLING_DB_PATH')
        if override:
            return override
        if HAS_DOTENV:
            load_dotenv()
            db_path = os.getenv('DB_PATH')
            if db_path and os.path.exists(db_path):
                return db_path

        # Try common locations
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

    def score_race(self, competition_id: int) -> Optional[RaceProfileScores]:
        """
        Score a single race by competition_id.

        Args:
            competition_id: The competition_id from race_feature_gradients

        Returns:
            RaceProfileScores or None if race not found
        """
        query = """
        SELECT
            COALESCE(rfg.kurtosis_null_percentile, 0) as breakdown,
            rfg.variance_normalized_slope,
            rfg.clumpiness_score_slope,
            rfg.biggest_group_metric_slope,
            rf100.winning_time
        FROM race_feature_gradients rfg
        JOIN race_features_100 rf100 ON rfg.competition_id = rf100.competition_id
        WHERE rfg.competition_id = ?
        AND rfg.variance_normalized_values IS NOT NULL
        LIMIT 1
        """

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, (competition_id,))
            row = cursor.fetchone()

        if row is None:
            return None

        breakdown, var_slope, clump_slope, bg_slope, winning_time = row

        if var_slope is None or clump_slope is None or bg_slope is None:
            return None

        return calculate_race_profile_scores(
            breakdown_percentile=breakdown,
            variance_slope=var_slope,
            clumpiness_slope=clump_slope,
            biggest_group_slope=bg_slope,
            winning_time=winning_time
        )

    def score_races_bulk(
        self,
        race_name: str = None,
        race_year: int = None,
        race_category: str = None,
        competition_type: str = 'stage',
        limit: int = None
    ) -> Dict[int, RaceProfileScores]:
        """
        Score multiple races matching criteria.

        Args:
            race_name: Filter by race name (e.g., 'Tour de France')
            race_year: Filter by year
            race_category: Filter by category ('wt', 'pro', 'd1')
            competition_type: Filter by type ('stage', 'one_day', 'gc')
            limit: Maximum number of races to return

        Returns:
            Dict mapping competition_id to RaceProfileScores (includes TTs with time_trial=1.0)
        """
        conditions = ["rfg.variance_normalized_values IS NOT NULL"]
        params = []

        if race_name:
            conditions.append("rfg.race_name = ?")
            params.append(race_name)
        if race_year:
            conditions.append("rfg.race_year = ?")
            params.append(race_year)
        if race_category:
            conditions.append("rfg.race_category = ?")
            params.append(race_category)
        if competition_type:
            conditions.append("rfg.competition_type = ?")
            params.append(competition_type)

        query = f"""
        SELECT
            rfg.competition_id,
            COALESCE(rfg.kurtosis_null_percentile, 0) as breakdown,
            rfg.variance_normalized_slope,
            rfg.clumpiness_score_slope,
            rfg.biggest_group_metric_slope,
            rf100.winning_time
        FROM race_feature_gradients rfg
        JOIN race_features_100 rf100 ON rfg.competition_id = rf100.competition_id
        WHERE {' AND '.join(conditions)}
        """

        if limit:
            query += f" LIMIT {limit}"

        results = {}
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, params)
            for row in cursor:
                comp_id, breakdown, var_slope, clump_slope, bg_slope, winning_time = row
                if var_slope is not None and clump_slope is not None and bg_slope is not None:
                    results[comp_id] = calculate_race_profile_scores(
                        breakdown_percentile=breakdown,
                        variance_slope=var_slope,
                        clumpiness_slope=clump_slope,
                        biggest_group_slope=bg_slope,
                        winning_time=winning_time
                    )

        return results

    def get_race_with_scores(
        self,
        race_name: str,
        race_year: int,
        competition_type: str = 'stage'
    ) -> list:
        """
        Get races with their profile scores for a specific race/year.

        Returns list of dicts with stage info and scores (includes TTs with time_trial=1.0).
        """
        query = """
        SELECT
            rfg.competition_id,
            rfg.competition_name,
            rfg.race_name,
            rfg.race_year,
            COALESCE(rfg.kurtosis_null_percentile, 0) as breakdown,
            rfg.variance_normalized_slope,
            rfg.clumpiness_score_slope,
            rfg.biggest_group_metric_slope,
            rf100.winning_time
        FROM race_feature_gradients rfg
        JOIN race_features_100 rf100 ON rfg.competition_id = rf100.competition_id
        WHERE rfg.race_name = ?
        AND rfg.race_year = ?
        AND rfg.competition_type = ?
        AND rfg.variance_normalized_values IS NOT NULL
        ORDER BY rfg.competition_name
        """

        results = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, (race_name, race_year, competition_type))
            for row in cursor:
                comp_id, comp_name, r_name, r_year, breakdown, var_slope, clump_slope, bg_slope, winning_time = row

                if var_slope is None or clump_slope is None or bg_slope is None:
                    continue

                scores = calculate_race_profile_scores(
                    breakdown_percentile=breakdown,
                    variance_slope=var_slope,
                    clumpiness_slope=clump_slope,
                    biggest_group_slope=bg_slope,
                    winning_time=winning_time
                )

                results.append({
                    'competition_id': comp_id,
                    'stage': comp_name,
                    'race_name': r_name,
                    'year': r_year,
                    'scores': scores,
                    'dominant_type': scores.dominant_type()
                })

        return results


def create_expected_race_profile(
    sprint: float = 0,
    mountain: float = 0,
    hilly: float = 0,
    rolling: float = 0,
    breakaway: float = 0,
    time_trial: float = 0
) -> RaceProfileScores:
    """
    Create an expected race profile for prediction.

    Useful when you want to predict results for a race that hasn't happened yet.
    Input scores will be normalized to sum to 1.

    Example:
        # Expecting a hilly stage with sprint potential
        profile = create_expected_race_profile(sprint=0.3, hilly=0.5, rolling=0.2)
        # Expecting a time trial
        profile = create_expected_race_profile(time_trial=1.0)
    """
    total = sprint + mountain + hilly + rolling + breakaway + time_trial
    if total == 0:
        total = 1  # Avoid division by zero

    return RaceProfileScores(
        sprint=round(sprint / total, 4),
        mountain=round(mountain / total, 4),
        hilly=round(hilly / total, 4),
        rolling=round(rolling / total, 4),
        breakaway=round(breakaway / total, 4),
        time_trial=round(time_trial / total, 4)
    )


# Convenience function for quick scoring
def score_race_from_gradients(
    breakdown_percentile: float,
    variance_slope: float,
    clumpiness_slope: float,
    biggest_group_slope: float
) -> Dict[str, float]:
    """
    Quick function to score a race from gradient values.

    Returns dict of scores summing to 1.
    """
    scores = calculate_race_profile_scores(
        breakdown_percentile=breakdown_percentile,
        variance_slope=variance_slope,
        clumpiness_slope=clumpiness_slope,
        biggest_group_slope=biggest_group_slope
    )
    return scores.to_dict()
