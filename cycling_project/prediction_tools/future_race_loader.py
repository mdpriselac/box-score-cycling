"""
Future Race Loader

Assembles model-ready DataFrames for races not yet in the database.
Bridges scraped start lists + historical reference races → predictions.
"""

import re
import sqlite3
import statistics
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

import numpy as np
import pandas as pd

from bs4 import BeautifulSoup

from cycling_project.prediction_tools.data_pipeline import CyclingDataPipeline
from cycling_project.prediction_tools.model_registry import ModelRegistry
from cycling_project.prediction_tools.evaluation import (
    BucketEvaluator, TimeGapEvaluator, RankingEvaluator,
)
from cycling_project.webscrape_tools.get_startlist import get_start_list
from cycling_project.webscrape_tools.start_list_parse_tools import Team, Rider
from cycling_project.webscrape_tools.scrape_client import WebClient
from cycling_project.webscrape_tools.get_race_results import extract_results, extract_race_time
from cycling_project.webscrape_tools.create_race_data import extract_stages_with_links
from cycling_project.webscrape_tools.database.engineered_metrics import (
    identify_groups,
    calculate_biggest_group_metric,
    calculate_time_gap_evenness,
    calculate_clumpiness_score,
    calculate_selection_metric,
)
from cycling_project.webscrape_tools.database.statistical_measures import (
    calculate_gini_coefficient,
    calculate_variance_and_std,
    calculate_skewness,
    calculate_kurtosis,
)
from cycling_project.engineering_tools.race_profile_scoring import (
    calculate_race_profile_scores,
)
from cycling_project.engineering_tools.place_handling import place_bucketer


# Default database path
_DEFAULT_DB = (
    Path(__file__).parent.parent
    / "webscrape_tools" / "database" / "database" / "cycling_races.db"
)

# Columns expected by the model (mirrors CyclingDataPipeline column lists)
RIDER_FEATURE_COLS = CyclingDataPipeline.RIDER_FEATURE_COLS
FIELD_FEATURE_COLS = CyclingDataPipeline.FIELD_FEATURE_COLS
RACE_PROFILE_COLS = CyclingDataPipeline.RACE_PROFILE_COLS
METADATA_COLS = CyclingDataPipeline.METADATA_COLS


def _ensure_cache_tables(db_path: str = None) -> None:
    """Create cache tables if they don't exist."""
    db_path = db_path or str(_DEFAULT_DB)
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cached_start_lists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fc_race_id TEXT NOT NULL,
                year INTEGER NOT NULL,
                rider_fc_id TEXT NOT NULL,
                rider_name TEXT,
                team_name TEXT,
                team_fc_id TEXT,
                bib_number TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(fc_race_id, year, rider_fc_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cached_race_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fc_race_id TEXT NOT NULL,
                year INTEGER NOT NULL,
                stage_id TEXT,
                stage_name TEXT,
                rider_fc_id TEXT,
                rider_name TEXT,
                team_name TEXT,
                place INTEGER,
                time_gap REAL,
                place_bucket INTEGER,
                winning_time REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(fc_race_id, year, stage_id, rider_fc_id)
            )
        """)
        conn.commit()


def get_cached_start_list(
    fc_race_id: int,
    year: int,
    db_path: str = None,
) -> Optional[List[Team]]:
    """
    Load a start list from the cache.

    Returns List[Team] if cached, None if not found.
    """
    db_path = db_path or str(_DEFAULT_DB)
    _ensure_cache_tables(db_path)

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT rider_fc_id, rider_name, team_name, team_fc_id, bib_number "
            "FROM cached_start_lists WHERE fc_race_id = ? AND year = ?",
            (str(fc_race_id), int(year)),
        ).fetchall()

    if not rows:
        return None

    # Group by (team_name, team_fc_id) to reconstruct Team objects
    teams_dict: Dict[Tuple[str, str], List[Rider]] = {}
    for rider_fc_id, rider_name, team_name, team_fc_id, bib_number in rows:
        key = (team_name or '', team_fc_id or '')
        if key not in teams_dict:
            teams_dict[key] = []
        teams_dict[key].append(Rider(
            name=rider_name or '',
            rider_id=rider_fc_id,
            number=bib_number or '',
            team_name=team_name or '',
            team_id=team_fc_id,
        ))

    return [
        Team(name=team_name, team_id=team_fc_id, riders=riders)
        for (team_name, team_fc_id), riders in teams_dict.items()
    ]


def save_start_list_to_cache(
    fc_race_id: int,
    year: int,
    teams: List[Team],
    db_path: str = None,
) -> None:
    """Save a scraped start list to the cache."""
    db_path = db_path or str(_DEFAULT_DB)
    _ensure_cache_tables(db_path)

    rows = []
    for team in teams:
        for rider in team.riders:
            rows.append((
                str(fc_race_id), int(year),
                rider.rider_id, rider.name,
                team.name, team.team_id, rider.number,
            ))

    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO cached_start_lists "
            "(fc_race_id, year, rider_fc_id, rider_name, team_name, team_fc_id, bib_number) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()


def scrape_or_load_startlist(
    race_id: int,
    year: int,
    force_refresh: bool = False,
    db_path: str = None,
) -> Tuple[List[Team], bool]:
    """
    Load start list from cache, or scrape and cache it.

    Returns:
        (teams, from_cache) — the list of Team objects and whether it came from cache.
    """
    if not force_refresh:
        cached = get_cached_start_list(race_id, year, db_path)
        if cached:
            return cached, True

    teams = scrape_startlist(race_id, year)
    save_start_list_to_cache(race_id, year, teams, db_path)
    return teams, False


def parse_firstcycling_url(url: str) -> Tuple[int, int, Optional[int]]:
    """
    Extract race_id, year, and optional stage number from a FirstCycling URL.

    Handles formats like:
        https://firstcycling.com/race.php?r=9&y=2026
        https://firstcycling.com/race.php?r=9&y=2026&k=8
        https://firstcycling.com/race.php?r=17&y=2026&e=01

    Returns:
        (race_id, year, stage_number) where stage_number is None when not
        specified in the URL.
    """
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    if 'r' not in params:
        raise ValueError(f"No race_id (r=) found in URL: {url}")
    if 'y' not in params:
        raise ValueError(f"No year (y=) found in URL: {url}")

    race_id = int(params['r'][0])
    year = int(params['y'][0])
    stage_number = int(params['e'][0]) if 'e' in params else None
    return race_id, year, stage_number


def get_race_name(fc_race_id: int, db_path: str = None) -> str:
    """Look up a race name from the database by FirstCycling race ID."""
    db_path = db_path or str(_DEFAULT_DB)
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT name FROM races WHERE fc_race_id = ? ORDER BY year DESC LIMIT 1",
        (str(fc_race_id),),
    ).fetchone()
    conn.close()
    return row[0] if row else f"Race {fc_race_id}"


def detect_stage_race_from_db(fc_race_id: int, db_path: str = None) -> bool:
    """Check if a race is a stage race based on the most recent DB entry."""
    db_path = db_path or str(_DEFAULT_DB)
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT is_stage_race FROM races "
            "WHERE fc_race_id = ? ORDER BY year DESC LIMIT 1",
            (str(fc_race_id),),
        ).fetchone()
    return bool(row[0]) if row else False


def get_available_stages(fc_race_id: int, db_path: str = None) -> List[dict]:
    """
    Get distinct stages available for a race from DB data.

    Only includes stages that have competition_field_features data in at
    least one year. Returns list of dicts with label/competition_type/
    stage_number, ordered GC first then stages by number.
    """
    db_path = db_path or str(_DEFAULT_DB)
    query = """
    SELECT DISTINCT c.competition_type, c.stage_number
    FROM races r
    JOIN competitions c ON c.race_id = r.id
    JOIN competition_field_features cff ON cff.competition_id = c.id
    WHERE r.fc_race_id = ?
      AND cff.race_sprint_score IS NOT NULL
    ORDER BY
        CASE c.competition_type WHEN 'gc' THEN 0 WHEN 'one_day' THEN 0 ELSE 1 END,
        c.stage_number
    """
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(query, (str(fc_race_id),)).fetchall()

    stages = []
    for comp_type, stage_num in rows:
        if comp_type == 'gc':
            stages.append({
                'label': 'GC',
                'competition_type': 'gc',
                'stage_number': None,
            })
        elif comp_type == 'one_day':
            stages.append({
                'label': 'Race',
                'competition_type': 'one_day',
                'stage_number': None,
            })
        elif comp_type == 'stage' and stage_num is not None:
            stages.append({
                'label': f'Stage {stage_num}',
                'competition_type': 'stage',
                'stage_number': int(stage_num),
            })
    return stages


def get_default_references(
    fc_race_id: int,
    competition_type: str = 'one_day',
    stage_number: Optional[int] = None,
    exclude_year: Optional[int] = None,
    max_results: int = 5,
    db_path: str = None,
) -> pd.DataFrame:
    """
    Find the most recent historical competitions for a given race.

    Handles duplicate entries per year by picking MIN(c.id). Only returns
    competitions with competition_field_features data (race profile scores).

    Returns DataFrame with the same columns as search_historical_races().
    """
    db_path = db_path or str(_DEFAULT_DB)

    conditions = [
        "r.fc_race_id = ?",
        "c.competition_type = ?",
        "cff.race_sprint_score IS NOT NULL",
    ]
    params: list = [str(fc_race_id), competition_type]

    if competition_type == 'stage' and stage_number is not None:
        conditions.append("c.stage_number = ?")
        params.append(stage_number)

    if exclude_year is not None:
        conditions.append("r.year != ?")
        params.append(exclude_year)

    where = " AND ".join(conditions)

    query = f"""
    SELECT
        sub.competition_id,
        r.name || ' - ' || cff.competition_name as display_name,
        r.name as race_name,
        cff.competition_name,
        cff.competition_date,
        cff.competition_type,
        cff.race_category,
        cff.field_size,
        cff.race_sprint_score,
        cff.race_mountain_score,
        cff.race_hilly_score,
        cff.race_rolling_score,
        cff.race_breakaway_score,
        cff.race_time_trial_score,
        cff.race_dominant_profile
    FROM (
        SELECT MIN(c.id) as competition_id
        FROM races r
        JOIN competitions c ON c.race_id = r.id
        JOIN competition_field_features cff ON cff.competition_id = c.id
        WHERE {where}
        GROUP BY r.year
        ORDER BY r.year DESC
        LIMIT ?
    ) sub
    JOIN competition_field_features cff ON cff.competition_id = sub.competition_id
    JOIN competitions c ON c.id = sub.competition_id
    JOIN races r ON c.race_id = r.id
    ORDER BY cff.competition_date DESC
    """
    params.append(max_results)

    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(query, conn, params=params)


def scrape_startlist(race_id: int, year: int) -> List[Team]:
    """Scrape a start list from FirstCycling."""
    teams = get_start_list(race_id, year)
    if not teams:
        raise ValueError(f"No start list found for race {race_id}, year {year}")
    return teams


def match_riders_to_db(
    teams: List[Team],
    db_path: str = None,
) -> Tuple[pd.DataFrame, List[dict]]:
    """
    Match scraped riders to the database by fc_rider_id.

    Returns:
        matched_df: DataFrame with columns [rider_id, fc_rider_id, rider_name, team_name, bib_number]
        unmatched: List of dicts with rider info for riders not found in DB
    """
    db_path = db_path or str(_DEFAULT_DB)

    # Collect all riders from start list
    all_riders = []
    for team in teams:
        for rider in team.riders:
            all_riders.append({
                'fc_rider_id': rider.rider_id,
                'rider_name': rider.name,
                'team_name': team.name,
                'bib_number': rider.number,
            })

    # Look up fc_rider_ids in the database
    fc_ids = [r['fc_rider_id'] for r in all_riders if r['fc_rider_id']]
    if not fc_ids:
        return pd.DataFrame(), all_riders

    placeholders = ','.join(['?'] * len(fc_ids))
    query = f"SELECT id, fc_rider_id FROM riders WHERE fc_rider_id IN ({placeholders})"

    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(query, fc_ids)
        db_map = {str(row[1]): row[0] for row in cursor.fetchall()}

    matched = []
    unmatched = []
    for rider in all_riders:
        fc_id = rider['fc_rider_id']
        if fc_id and str(fc_id) in db_map:
            rider['rider_id'] = db_map[str(fc_id)]
            matched.append(rider)
        else:
            unmatched.append(rider)

    matched_df = pd.DataFrame(matched) if matched else pd.DataFrame()
    return matched_df, unmatched


def get_latest_rider_snapshots(
    rider_ids: List[int],
    db_path: str = None,
) -> pd.DataFrame:
    """
    Get the most recent rider_competition_snapshot for each rider.

    Returns a DataFrame with one row per rider, containing all snapshot columns.
    """
    db_path = db_path or str(_DEFAULT_DB)
    if not rider_ids:
        return pd.DataFrame()

    placeholders = ','.join(['?'] * len(rider_ids))

    # Get the latest snapshot per rider (highest competition_id = most recent)
    query = f"""
    SELECT rcs.*
    FROM rider_competition_snapshots rcs
    INNER JOIN (
        SELECT rider_id, MAX(competition_id) as max_comp_id
        FROM rider_competition_snapshots
        WHERE rider_id IN ({placeholders})
        GROUP BY rider_id
    ) latest ON rcs.rider_id = latest.rider_id
              AND rcs.competition_id = latest.max_comp_id
    """

    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(query, conn, params=rider_ids)

    return df


def compute_field_features(rider_snapshots: pd.DataFrame) -> dict:
    """
    Compute field-level features from rider snapshots.

    Mirrors the computation in feature_precomputation.py for competition_field_features.
    """
    n = len(rider_snapshots)
    if n == 0:
        return {}

    def _stats(values):
        """Compute distribution stats."""
        clean = [v for v in values if v is not None and not np.isnan(v)]
        if not clean:
            return {'mean': 0, 'median': 0, 'std': 0, 'min': 0, 'max': 0, 'p25': 0, 'p75': 0}
        arr = np.array(clean)
        return {
            'mean': float(np.mean(arr)),
            'median': float(np.median(arr)),
            'std': float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0,
            'min': float(np.min(arr)),
            'max': float(np.max(arr)),
            'p25': float(np.percentile(arr, 25)),
            'p75': float(np.percentile(arr, 75)),
        }

    # Experience distribution (races_career)
    exp = _stats(rider_snapshots['races_career'].values)

    # Bucket distribution (use stage_avg_bucket as overall indicator)
    bucket = _stats(rider_snapshots['stage_avg_bucket'].values)

    # Specialist counts based on best_profile
    profile_counts = Counter(rider_snapshots['best_profile'].fillna('unknown').values)

    return {
        'field_size': n,
        'experience_mean': exp['mean'],
        'experience_median': exp['median'],
        'experience_std': exp['std'],
        'experience_min': exp['min'],
        'experience_max': exp['max'],
        'experience_p25': exp['p25'],
        'experience_p75': exp['p75'],
        'bucket_mean': bucket['mean'],
        'bucket_median': bucket['median'],
        'bucket_std': bucket['std'],
        'bucket_min': bucket['min'],
        'bucket_max': bucket['max'],
        'bucket_p25': bucket['p25'],
        'bucket_p75': bucket['p75'],
        'sprinter_count': profile_counts.get('sprint', 0),
        'climber_count': profile_counts.get('mountain', 0),
        'hilly_specialist_count': profile_counts.get('hilly', 0),
        'rolling_specialist_count': profile_counts.get('rolling', 0),
        'breakaway_specialist_count': profile_counts.get('breakaway', 0),
        'time_trialist_count': profile_counts.get('time_trial', 0),
        'unknown_profile_count': profile_counts.get('unknown', 0),
    }


def get_reference_race_profile(
    competition_id: int,
    db_path: str = None,
) -> dict:
    """
    Get race profile and metadata from a historical race.

    Returns dict with race profile scores, competition_type, race_category,
    competition_name (includes parent race name), and competition_date.
    """
    db_path = db_path or str(_DEFAULT_DB)

    query = """
    SELECT
        r.name || ' - ' || cff.competition_name as display_name,
        cff.competition_date, cff.competition_type, cff.race_category,
        cff.race_sprint_score, cff.race_mountain_score, cff.race_hilly_score,
        cff.race_rolling_score, cff.race_breakaway_score, cff.race_time_trial_score,
        cff.race_dominant_profile
    FROM competition_field_features cff
    JOIN competitions c ON cff.competition_id = c.id
    JOIN races r ON c.race_id = r.id
    WHERE cff.competition_id = ?
    """

    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(query, (int(competition_id),))
        row = cursor.fetchone()

    if row is None:
        raise ValueError(f"No competition_field_features found for competition_id={competition_id}")

    return {
        'competition_name': row[0],
        'competition_date': row[1],
        'competition_type': row[2],
        'race_category': row[3],
        'race_sprint_score': row[4],
        'race_mountain_score': row[5],
        'race_hilly_score': row[6],
        'race_rolling_score': row[7],
        'race_breakaway_score': row[8],
        'race_time_trial_score': row[9],
        'race_dominant_profile': row[10],
    }


def average_race_profiles(profiles: List[dict]) -> dict:
    """
    Average race profile scores across multiple reference races.

    Uses mean of profile scores, mode of competition_type and race_category.
    """
    score_keys = [
        'race_sprint_score', 'race_mountain_score', 'race_hilly_score',
        'race_rolling_score', 'race_breakaway_score', 'race_time_trial_score',
    ]

    avg = {}
    for key in score_keys:
        values = [p[key] for p in profiles if p[key] is not None]
        avg[key] = statistics.mean(values) if values else 0.0

    # Dominant profile = highest averaged score
    best_key = max(score_keys, key=lambda k: avg[k])
    profile_name = best_key.replace('race_', '').replace('_score', '')
    avg['race_dominant_profile'] = profile_name

    # Mode of competition_type and race_category
    comp_types = [p['competition_type'] for p in profiles if p['competition_type']]
    avg['competition_type'] = Counter(comp_types).most_common(1)[0][0] if comp_types else 'stage'

    categories = [p['race_category'] for p in profiles if p['race_category']]
    avg['race_category'] = Counter(categories).most_common(1)[0][0] if categories else 'wt'

    avg['competition_name'] = 'Averaged Reference Races'
    avg['competition_date'] = None

    return avg


def assemble_prediction_df(
    rider_snapshots: pd.DataFrame,
    matched_riders: pd.DataFrame,
    field_features: dict,
    race_profile: dict,
) -> pd.DataFrame:
    """
    Combine rider snapshots + field features + race profile into a model-ready DataFrame.

    Args:
        rider_snapshots: Latest snapshots from rider_competition_snapshots
        matched_riders: Rider mapping with bib_number, team_name
        field_features: Computed from the actual start list
        race_profile: From a historical reference race
    """
    # Start with rider snapshot data
    df = rider_snapshots.copy()

    # Merge in bib numbers and team names from the scraped start list
    if not matched_riders.empty and 'bib_number' in matched_riders.columns:
        bib_map = matched_riders.set_index('rider_id')['bib_number'].to_dict()
        team_map = matched_riders.set_index('rider_id')['team_name'].to_dict()

        # Parse bib numbers into team_bib and personal_bib
        for rider_id in df['rider_id']:
            bib = bib_map.get(rider_id)
            if bib is not None:
                try:
                    bib_int = int(bib)
                    df.loc[df['rider_id'] == rider_id, 'team_bib'] = bib_int // 10
                    df.loc[df['rider_id'] == rider_id, 'personal_bib'] = bib_int % 10
                except (ValueError, TypeError):
                    pass

    # Add field features (same for all riders)
    for col in FIELD_FEATURE_COLS:
        df[col] = field_features.get(col)

    # Add race profile (same for all riders)
    for col in RACE_PROFILE_COLS:
        df[col] = race_profile.get(col)

    # Add metadata
    df['competition_id'] = 0  # Placeholder for future race
    df['competition_name'] = race_profile.get('competition_name', 'Future Race')
    df['competition_date'] = race_profile.get('competition_date', '')
    df['competition_type'] = race_profile.get('competition_type', 'stage')
    df['race_category'] = race_profile.get('race_category', 'wt')

    # Drop the snapshot's competition_id (it was from the rider's last race)
    # We've already set competition_id = 0 above

    return df


def search_historical_races(
    name_filter: str = None,
    year_filter: int = None,
    category_filter: str = None,
    type_filter: str = None,
    db_path: str = None,
    limit: int = 100,
) -> pd.DataFrame:
    """
    Search historical races by joining competition_field_features with races table.

    The name_filter searches on the parent race name (e.g. 'Tour de France'),
    not the competition_name which is just 'Stage: 01', 'GC', etc.

    Returns DataFrame with competition metadata and profile scores.
    """
    db_path = db_path or str(_DEFAULT_DB)

    conditions = ["cff.race_sprint_score IS NOT NULL"]
    params = []

    if name_filter:
        conditions.append("r.name LIKE ?")
        params.append(f"%{name_filter}%")
    if year_filter:
        conditions.append("r.year = ?")
        params.append(year_filter)
    if category_filter:
        conditions.append("cff.race_category = ?")
        params.append(category_filter)
    if type_filter:
        conditions.append("cff.competition_type = ?")
        params.append(type_filter)

    where = f"WHERE {' AND '.join(conditions)}"

    query = f"""
    SELECT
        cff.competition_id,
        r.name || ' - ' || cff.competition_name as display_name,
        r.name as race_name,
        cff.competition_name,
        cff.competition_date,
        cff.competition_type,
        cff.race_category,
        cff.field_size,
        cff.race_sprint_score,
        cff.race_mountain_score,
        cff.race_hilly_score,
        cff.race_rolling_score,
        cff.race_breakaway_score,
        cff.race_time_trial_score,
        cff.race_dominant_profile
    FROM competition_field_features cff
    JOIN competitions c ON cff.competition_id = c.id
    JOIN races r ON c.race_id = r.id
    {where}
    ORDER BY cff.competition_date DESC
    LIMIT ?
    """
    params.append(limit)

    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(query, conn, params=params)


def predict_future_race(
    url: str,
    reference_competition_ids: List[int],
    model_dir: str = None,
    db_path: str = None,
) -> dict:
    """
    Full pipeline: scrape start list → assemble features → predict for each reference race.

    Args:
        url: FirstCycling URL for the upcoming race
        reference_competition_ids: Up to 5 historical competition IDs
        model_dir: Path to saved production model
        db_path: Path to SQLite database

    Returns:
        dict with keys:
            'matched_riders': DataFrame of riders found in DB
            'unmatched_riders': list of riders not found
            'predictions': dict mapping reference label → ranked predictions DataFrame
    """
    db_path = db_path or str(_DEFAULT_DB)
    model_dir = model_dir or str(Path(__file__).parent.parent.parent / "models" / "production")

    # 1. Parse URL and scrape start list
    race_id, year = parse_firstcycling_url(url)
    teams = scrape_startlist(race_id, year)

    # 2. Match riders to database
    matched_riders, unmatched_riders = match_riders_to_db(teams, db_path)
    if matched_riders.empty:
        raise ValueError("No riders from the start list were found in the database")

    rider_ids = matched_riders['rider_id'].tolist()

    # 3. Get latest rider snapshots
    snapshots = get_latest_rider_snapshots(rider_ids, db_path)
    if snapshots.empty:
        raise ValueError("No rider snapshots found in the database")

    # 4. Compute field features from actual start list
    field_features = compute_field_features(snapshots)

    # 5. Load production model
    registry = ModelRegistry(model_dir)
    bucket_pred, time_gap_pred, race_ranker = registry.load_with_ranker(
        ranking_method='expected_bucket'
    )

    # 6. Get reference race profiles and generate predictions
    reference_profiles = []
    predictions = {}

    for comp_id in reference_competition_ids:
        profile = get_reference_race_profile(comp_id, db_path)
        reference_profiles.append(profile)

        pred_df = assemble_prediction_df(snapshots, matched_riders, field_features, profile)
        result = race_ranker.predict_race(pred_df, return_details=False)

        # Add rider names from matched_riders
        name_map = matched_riders.set_index('rider_id')[['rider_name', 'team_name']].to_dict('index')
        result['team'] = result['rider_id'].map(lambda rid: name_map.get(rid, {}).get('team_name', ''))

        label = f"{profile['competition_name']} ({profile['competition_date']})"
        predictions[label] = result

    # 7. Average prediction
    if len(reference_profiles) > 1:
        avg_profile = average_race_profiles(reference_profiles)
        pred_df = assemble_prediction_df(snapshots, matched_riders, field_features, avg_profile)
        result = race_ranker.predict_race(pred_df, return_details=False)

        name_map = matched_riders.set_index('rider_id')[['rider_name', 'team_name']].to_dict('index')
        result['team'] = result['rider_id'].map(lambda rid: name_map.get(rid, {}).get('team_name', ''))

        predictions['Averaged Reference Races'] = result

    return {
        'matched_riders': matched_riders,
        'unmatched_riders': unmatched_riders,
        'predictions': predictions,
        'field_features': field_features,
        'reference_profiles': reference_profiles,
    }


# ── Group B: Enhanced Historical Race Details ────────────────────────────

_FINISHING_CHAR_COLS = [
    'biggest_group_metric', 'time_gap_evenness_metric', 'clumpiness_score',
    'selection_metric', 'total_race_duration', 'variance_normalized',
    'skewness_normalized', 'gini_coefficient', 'total_finishers',
    'abandon_ratio', 'largest_group_size', 'proportion_in_groups',
]


def get_race_finishing_characteristics(
    competition_id: int,
    db_path: str = None,
) -> Optional[dict]:
    """
    Get finishing time distribution characteristics from race_features_50.

    Returns dict with 12 key metrics, or None if no data exists.
    """
    db_path = db_path or str(_DEFAULT_DB)
    cols = ', '.join(_FINISHING_CHAR_COLS)
    query = f"SELECT {cols} FROM race_features_50 WHERE competition_id = ?"

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(query, (int(competition_id),)).fetchone()

    if row is None:
        return None

    return dict(zip(_FINISHING_CHAR_COLS, row))


def get_selected_race_details(
    competition_ids: List[int],
    db_path: str = None,
) -> pd.DataFrame:
    """
    Get enriched data for selected reference races.

    Joins competition_field_features with race_features_50 to provide
    profile scores, field composition, and finishing characteristics.
    """
    db_path = db_path or str(_DEFAULT_DB)
    if not competition_ids:
        return pd.DataFrame()

    placeholders = ','.join(['?'] * len(competition_ids))
    rf_cols = ', '.join([f'rf.{c}' for c in _FINISHING_CHAR_COLS])

    query = f"""
    SELECT
        cff.competition_id,
        r.name || ' - ' || cff.competition_name as display_name,
        cff.competition_date,
        cff.competition_type,
        cff.race_dominant_profile,
        cff.race_sprint_score, cff.race_mountain_score, cff.race_hilly_score,
        cff.race_rolling_score, cff.race_breakaway_score, cff.race_time_trial_score,
        cff.field_size, cff.experience_mean, cff.bucket_mean,
        cff.sprinter_count, cff.climber_count, cff.hilly_specialist_count,
        cff.rolling_specialist_count, cff.breakaway_specialist_count,
        cff.time_trialist_count,
        {rf_cols}
    FROM competition_field_features cff
    JOIN competitions c ON cff.competition_id = c.id
    JOIN races r ON c.race_id = r.id
    LEFT JOIN race_features_50 rf ON rf.competition_id = cff.competition_id
    WHERE cff.competition_id IN ({placeholders})
    """

    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(query, conn, params=[int(c) for c in competition_ids])


# ── Group C: Stage Detection & Results Loading ───────────────────────────

_BASE_URL = "https://firstcycling.com"


def detect_race_stages(
    fc_race_id: int,
    year: int,
) -> Tuple[bool, List[dict]]:
    """
    Detect whether a race is a stage race and extract stage list.

    Returns:
        (is_stage_race, stages) where stages is a list of
        {'name': str, 'url_param': str} dicts.
    """
    client = WebClient(_BASE_URL)
    try:
        url = f"{_BASE_URL}/race.php?r={fc_race_id}&y={year}"
        response = client.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        stages_dict = extract_stages_with_links(soup)
    except Exception:
        return False, []
    finally:
        client.close()

    if not stages_dict:
        return False, []

    stages = [
        {'name': name, 'url_param': value}
        for name, value in stages_dict.items()
    ]
    return True, stages


def get_cached_results(
    fc_race_id: int,
    year: int,
    stage_id: str = None,
    db_path: str = None,
) -> Optional[pd.DataFrame]:
    """Load results from the cache table."""
    db_path = db_path or str(_DEFAULT_DB)
    _ensure_cache_tables(db_path)

    if stage_id is not None:
        query = (
            "SELECT rider_fc_id, rider_name, team_name, place, time_gap, "
            "place_bucket, winning_time "
            "FROM cached_race_results "
            "WHERE fc_race_id = ? AND year = ? AND stage_id = ?"
        )
        params = (str(fc_race_id), int(year), str(stage_id))
    else:
        query = (
            "SELECT rider_fc_id, rider_name, team_name, place, time_gap, "
            "place_bucket, winning_time "
            "FROM cached_race_results "
            "WHERE fc_race_id = ? AND year = ? AND stage_id IS NULL"
        )
        params = (str(fc_race_id), int(year))

    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(query, conn, params=params)

    if df.empty:
        return None

    # Match riders to DB to get internal rider_id
    fc_ids = df['rider_fc_id'].dropna().tolist()
    if fc_ids:
        placeholders = ','.join(['?'] * len(fc_ids))
        with sqlite3.connect(db_path) as conn:
            id_rows = conn.execute(
                f"SELECT id, fc_rider_id FROM riders WHERE fc_rider_id IN ({placeholders})",
                fc_ids,
            ).fetchall()
        id_map = {str(row[1]): row[0] for row in id_rows}
        df['rider_id'] = df['rider_fc_id'].map(lambda x: id_map.get(str(x)))

    winning_time = df['winning_time'].iloc[0] if 'winning_time' in df.columns else None
    return df


def save_results_to_cache(
    fc_race_id: int,
    year: int,
    results_df: pd.DataFrame,
    winning_time: Optional[float],
    stage_id: str = None,
    stage_name: str = None,
    db_path: str = None,
) -> None:
    """Save scraped results to the cache table."""
    db_path = db_path or str(_DEFAULT_DB)
    _ensure_cache_tables(db_path)

    rows = []
    for _, row in results_df.iterrows():
        rows.append((
            str(fc_race_id), int(year),
            str(stage_id) if stage_id is not None else None,
            stage_name,
            str(row.get('rider_fc_id', row.get('fc_rider_id', ''))),
            row.get('rider_name', row.get('name', '')),
            row.get('team_name', row.get('team', '')),
            int(row['place']) if pd.notna(row.get('place')) else None,
            float(row['time_gap']) if pd.notna(row.get('time_gap')) and isinstance(row.get('time_gap'), (int, float)) else None,
            int(row['place_bucket']) if pd.notna(row.get('place_bucket')) else None,
            float(winning_time) if winning_time is not None else None,
        ))

    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO cached_race_results "
            "(fc_race_id, year, stage_id, stage_name, rider_fc_id, rider_name, "
            "team_name, place, time_gap, place_bucket, winning_time) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()


def scrape_race_results(
    fc_race_id: int,
    year: int,
    stage_url_param: str = None,
    db_path: str = None,
) -> Tuple[Optional[pd.DataFrame], Optional[float]]:
    """
    Scrape race results from FirstCycling.

    Returns:
        (results_df, winning_time) or (None, None) if no results found.
        results_df has columns: rider_fc_id, rider_name, team_name, place,
        time_gap, place_bucket, rider_id (internal DB id if matched).
    """
    db_path = db_path or str(_DEFAULT_DB)
    url = f"{_BASE_URL}/race.php?r={fc_race_id}&y={year}"
    if stage_url_param:
        url += f"&e={stage_url_param}"

    client = WebClient(_BASE_URL)
    try:
        response = client.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        raw_results = extract_results(soup)
        winning_time = extract_race_time(soup)
    except Exception:
        return None, None
    finally:
        client.close()

    if not raw_results:
        return None, None

    # Build DataFrame from raw results
    rows = []
    for r in raw_results:
        place_val = r.get('place')
        gap_val = r.get('gap')
        try:
            place_int = int(str(place_val).strip())
        except (ValueError, TypeError):
            place_int = None
        bucket = place_bucketer(place_val) if place_val is not None else None

        rows.append({
            'rider_fc_id': r.get('rider_id'),
            'rider_name': r.get('name', ''),
            'team_name': r.get('team', ''),
            'place': place_int,
            'time_gap': gap_val if isinstance(gap_val, (int, float)) else None,
            'place_bucket': bucket,
        })

    df = pd.DataFrame(rows)

    # Match riders to DB
    fc_ids = df['rider_fc_id'].dropna().tolist()
    if fc_ids:
        placeholders = ','.join(['?'] * len(fc_ids))
        with sqlite3.connect(db_path) as conn:
            id_rows = conn.execute(
                f"SELECT id, fc_rider_id FROM riders WHERE fc_rider_id IN ({placeholders})",
                [str(x) for x in fc_ids],
            ).fetchall()
        id_map = {str(row[1]): row[0] for row in id_rows}
        df['rider_id'] = df['rider_fc_id'].map(lambda x: id_map.get(str(x)))
    else:
        df['rider_id'] = None

    return df, winning_time


def _get_results_from_rider_results(
    fc_race_id: int,
    year: int,
    db_path: str = None,
) -> Tuple[Optional[pd.DataFrame], Optional[float]]:
    """Check the main rider_results table for existing results."""
    db_path = db_path or str(_DEFAULT_DB)

    query = """
    SELECT
        c.id as competition_id,
        c.winning_time
    FROM competitions c
    JOIN races r ON c.race_id = r.id
    WHERE r.fc_race_id = ? AND r.year = ?
    LIMIT 1
    """
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(query, (str(fc_race_id), int(year))).fetchone()

    if row is None:
        return None, None

    comp_id, winning_time = row

    results_query = """
    SELECT
        rr.rider_id,
        rd.fc_rider_id as rider_fc_id,
        rd.name as rider_name,
        rr.place,
        rr.time_gap,
        rr.place_bucket
    FROM rider_results rr
    JOIN riders rd ON rr.rider_id = rd.id
    WHERE rr.competition_id = ?
    ORDER BY rr.place
    """
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(results_query, conn, params=[comp_id])

    if df.empty:
        return None, None

    return df, winning_time


def scrape_or_load_results(
    fc_race_id: int,
    year: int,
    stage_id: str = None,
    stage_url_param: str = None,
    force_refresh: bool = False,
    db_path: str = None,
) -> Tuple[Optional[pd.DataFrame], Optional[float]]:
    """
    Load results from DB/cache, or scrape and cache them.

    Checks in order: rider_results table, cached_race_results, then scrapes.
    """
    db_path = db_path or str(_DEFAULT_DB)

    if not force_refresh:
        # Check main DB first (only for non-stage or when we can map stages)
        if stage_id is None:
            df, wt = _get_results_from_rider_results(fc_race_id, year, db_path)
            if df is not None:
                return df, wt

        # Check cache
        cached = get_cached_results(fc_race_id, year, stage_id, db_path)
        if cached is not None:
            wt = cached['winning_time'].iloc[0] if 'winning_time' in cached.columns else None
            return cached, wt

    # Scrape
    df, wt = scrape_race_results(fc_race_id, year, stage_url_param, db_path)
    if df is not None:
        save_results_to_cache(
            fc_race_id, year, df, wt,
            stage_id=stage_id,
            stage_name=stage_id,
            db_path=db_path,
        )
    return df, wt


# ── Group D: Race Characteristics from Results ───────────────────────────

def compute_characteristics_from_results(
    results_df: pd.DataFrame,
    winning_time: Optional[float],
) -> Optional[dict]:
    """
    Compute finishing time distribution characteristics from a results DataFrame.

    Returns dict with same keys as get_race_finishing_characteristics().
    """
    if winning_time is None or winning_time <= 0:
        return None

    # Extract valid numeric time gaps
    valid = results_df[results_df['time_gap'].notna()].copy()
    time_gaps = valid['time_gap'].astype(float).tolist()

    total_starters = len(results_df)
    total_finishers = len(valid)

    if total_finishers < 10:
        return None

    # Sort time gaps
    time_gaps_sorted = sorted(time_gaps)

    # Finishing times for statistical measures
    finishing_times = [winning_time + g for g in time_gaps_sorted]

    # Group analysis
    group_info = identify_groups(time_gaps_sorted)
    biggest_group = calculate_biggest_group_metric(group_info, total_finishers)
    evenness = calculate_time_gap_evenness(time_gaps_sorted)
    clumpiness = calculate_clumpiness_score(group_info, total_finishers, time_gaps_sorted)
    selection = calculate_selection_metric(time_gaps_sorted, winning_time)

    # Statistical measures
    variance_norm, _ = calculate_variance_and_std(finishing_times, normalize_by=winning_time)
    skewness_norm = calculate_skewness(finishing_times, normalize_by=winning_time)
    gini = calculate_gini_coefficient(time_gaps_sorted)

    # Duration
    total_duration = time_gaps_sorted[-1] if time_gaps_sorted else 0

    return {
        'biggest_group_metric': biggest_group,
        'time_gap_evenness_metric': evenness,
        'clumpiness_score': clumpiness,
        'selection_metric': selection,
        'total_race_duration': total_duration,
        'variance_normalized': variance_norm,
        'skewness_normalized': skewness_norm,
        'gini_coefficient': gini,
        'total_finishers': total_finishers,
        'abandon_ratio': 1 - (total_finishers / total_starters) if total_starters > 0 else 0,
        'largest_group_size': group_info['largest_group_size'],
        'proportion_in_groups': group_info['proportion_in_groups'],
    }


def compute_profile_scores_from_results(
    results_df: pd.DataFrame,
    winning_time: Optional[float],
) -> Optional[dict]:
    """
    Compute race profile scores from a results DataFrame.

    Calculates statistics at multiple percentile levels, fits gradient slopes,
    and feeds them into the profile scoring model.

    Returns dict with keys: sprint, mountain, hilly, rolling, breakaway,
    time_trial, dominant_profile — or None if insufficient data.
    """
    if winning_time is None or winning_time <= 0:
        return None

    valid = results_df[results_df['time_gap'].notna()].copy()
    time_gaps = sorted(valid['time_gap'].astype(float).tolist())
    total_finishers = len(time_gaps)

    if total_finishers < 10:
        return None

    # Compute metrics at each percentile level
    percentiles = [10, 15, 20, 25, 30, 35, 40, 45, 50,
                   55, 60, 65, 70, 75, 80, 85, 90, 95, 100]
    variance_values = []
    clumpiness_values = []
    biggest_group_values = []
    kurtosis_null_percentile = None
    valid_percentiles = []

    for pct in percentiles:
        n = max(1, int(total_finishers * pct / 100))
        subset_gaps = time_gaps[:n]
        if len(subset_gaps) < 3:
            continue

        finishing_times = [winning_time + g for g in subset_gaps]

        # Variance
        var_norm, _ = calculate_variance_and_std(finishing_times, normalize_by=winning_time)

        # Kurtosis — check for breakdown
        try:
            kurt = calculate_kurtosis(finishing_times, normalize_by=winning_time)
        except Exception:
            kurt = None

        # Track breakdown point (highest percentile where kurtosis is null/incalculable)
        if kurt is None or (var_norm is not None and var_norm == 0):
            if kurtosis_null_percentile is None or pct > kurtosis_null_percentile:
                kurtosis_null_percentile = pct

        # Group metrics
        group_info = identify_groups(subset_gaps)
        bg = calculate_biggest_group_metric(group_info, n)
        clump = calculate_clumpiness_score(group_info, n, subset_gaps)

        valid_percentiles.append(pct)
        variance_values.append(var_norm if var_norm is not None else 0.0)
        clumpiness_values.append(clump)
        biggest_group_values.append(bg)

    if len(valid_percentiles) < 3:
        return None

    # Fit linear regression slopes
    pcts = np.array(valid_percentiles, dtype=float)
    var_slope = float(np.polyfit(pcts, variance_values, 1)[0])
    clump_slope = float(np.polyfit(pcts, clumpiness_values, 1)[0])
    bg_slope = float(np.polyfit(pcts, biggest_group_values, 1)[0])

    breakdown = kurtosis_null_percentile or 0

    scores = calculate_race_profile_scores(
        breakdown_percentile=breakdown,
        variance_slope=var_slope,
        clumpiness_slope=clump_slope,
        biggest_group_slope=bg_slope,
        winning_time=winning_time,
    )

    result = scores.to_dict()
    result['dominant_profile'] = scores.dominant_type()
    return result


# ── Group E: Comparison & Evaluation ─────────────────────────────────────

_COMPARABLE_METRICS = [
    'biggest_group_metric', 'time_gap_evenness_metric', 'clumpiness_score',
    'selection_metric', 'variance_normalized', 'skewness_normalized',
    'gini_coefficient', 'total_race_duration',
]


def compare_race_characteristics(
    actual_chars: dict,
    reference_chars_list: List[dict],
) -> pd.DataFrame:
    """
    Compare actual race characteristics against reference races.

    Returns DataFrame with one row per reference, including similarity scores.
    The most similar reference is flagged with most_similar=True.
    """
    if not actual_chars or not reference_chars_list:
        return pd.DataFrame()

    # Collect all values for normalization
    all_values = {m: [actual_chars.get(m, 0)] for m in _COMPARABLE_METRICS}
    for ref in reference_chars_list:
        for m in _COMPARABLE_METRICS:
            all_values[m].append(ref.get(m, 0))

    # Compute ranges for normalization
    ranges = {}
    for m in _COMPARABLE_METRICS:
        vals = [v for v in all_values[m] if v is not None]
        r = max(vals) - min(vals) if vals else 0
        ranges[m] = r if r > 0 else 1.0

    rows = []
    for ref in reference_chars_list:
        diffs = {}
        sum_sq = 0.0
        for m in _COMPARABLE_METRICS:
            actual_val = actual_chars.get(m, 0) or 0
            ref_val = ref.get(m, 0) or 0
            norm_diff = abs(actual_val - ref_val) / ranges[m]
            diffs[f'{m}_diff'] = norm_diff
            sum_sq += norm_diff ** 2

        distance = sum_sq ** 0.5
        similarity = 1.0 / (1.0 + distance)

        row = {'label': ref.get('label', ''), 'similarity': similarity, 'distance': distance}
        # Add actual and reference values for display
        for m in _COMPARABLE_METRICS:
            row[f'ref_{m}'] = ref.get(m)
            row[f'actual_{m}'] = actual_chars.get(m)
        rows.append(row)

    df = pd.DataFrame(rows)
    if not df.empty:
        df['most_similar'] = df['similarity'] == df['similarity'].max()

    return df


def evaluate_predictions_against_actual(
    predictions_dict: dict,
    actual_results_df: pd.DataFrame,
) -> dict:
    """
    Evaluate each prediction against actual race results.

    Args:
        predictions_dict: {label: prediction_df} from session state
        actual_results_df: DataFrame with rider_id, place, time_gap, place_bucket

    Returns:
        dict with per-prediction metrics and best-prediction flags.
    """
    results = {}

    for label, pred_df in predictions_dict.items():
        if 'rider_id' not in pred_df.columns or 'rider_id' not in actual_results_df.columns:
            continue

        # Join on rider_id
        merged = pred_df.merge(
            actual_results_df[['rider_id', 'place', 'time_gap', 'place_bucket']].rename(
                columns={'place': 'actual_place', 'time_gap': 'actual_time_gap',
                         'place_bucket': 'actual_bucket'}
            ),
            on='rider_id',
            how='inner',
        )

        if merged.empty:
            continue

        metrics = {}

        # Bucket evaluation
        valid_buckets = merged.dropna(subset=['actual_bucket', 'ranking_derived_bucket'])
        if not valid_buckets.empty:
            bucket_metrics = BucketEvaluator.evaluate(
                valid_buckets['actual_bucket'].values.astype(int),
                valid_buckets['ranking_derived_bucket'].values.astype(int),
            )
            metrics['bucket'] = bucket_metrics

        # Time gap evaluation
        if 'predicted_time_gap' in merged.columns:
            valid_tg = merged.dropna(subset=['actual_time_gap', 'predicted_time_gap'])
            valid_tg = valid_tg[valid_tg['actual_time_gap'].apply(lambda x: isinstance(x, (int, float)))]
            if len(valid_tg) >= 5:
                tg_metrics = TimeGapEvaluator.evaluate(
                    valid_tg['actual_time_gap'].values.astype(float),
                    valid_tg['predicted_time_gap'].values.astype(float),
                )
                metrics['time_gap'] = tg_metrics

        # Ranking evaluation
        valid_ranks = merged.dropna(subset=['actual_place', 'predicted_rank'])
        if len(valid_ranks) >= 10:
            ranking_metrics = RankingEvaluator.evaluate(
                valid_ranks['predicted_rank'].values.astype(int),
                valid_ranks['actual_place'].values.astype(int),
            )
            metrics['ranking'] = ranking_metrics

        metrics['n_matched'] = len(merged)
        results[label] = metrics

    # Identify best predictions
    if results:
        # Best ranking (highest kendall_tau)
        taus = {l: m['ranking']['kendall_tau'] for l, m in results.items() if 'ranking' in m}
        if taus:
            best_ranking = max(taus, key=taus.get)
            results[best_ranking].setdefault('best_for', []).append('ranking')

        # Best bucket (lowest MAE)
        maes = {l: m['bucket']['mae'] for l, m in results.items() if 'bucket' in m}
        if maes:
            best_bucket = min(maes, key=maes.get)
            results[best_bucket].setdefault('best_for', []).append('bucket')

        # Best time gap (lowest MAE)
        tg_maes = {l: m['time_gap']['mae'] for l, m in results.items() if 'time_gap' in m}
        if tg_maes:
            best_tg = min(tg_maes, key=tg_maes.get)
            results[best_tg].setdefault('best_for', []).append('time_gap')

    return results
