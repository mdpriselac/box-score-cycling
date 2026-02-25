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

from cycling_project.prediction_tools.data_pipeline import CyclingDataPipeline
from cycling_project.prediction_tools.model_registry import ModelRegistry
from cycling_project.webscrape_tools.get_startlist import get_start_list
from cycling_project.webscrape_tools.start_list_parse_tools import Team


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


def parse_firstcycling_url(url: str) -> Tuple[int, int]:
    """
    Extract race_id and year from a FirstCycling URL.

    Handles formats like:
        https://firstcycling.com/race.php?r=9&y=2026
        https://firstcycling.com/race.php?r=9&y=2026&k=8
    """
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    if 'r' not in params:
        raise ValueError(f"No race_id (r=) found in URL: {url}")
    if 'y' not in params:
        raise ValueError(f"No year (y=) found in URL: {url}")

    race_id = int(params['r'][0])
    year = int(params['y'][0])
    return race_id, year


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
