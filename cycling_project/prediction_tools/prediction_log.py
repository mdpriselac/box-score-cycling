"""
Prediction log: persist each web-app prediction so multiclass and
LambdaRank probabilities can be compared against actual results over time.

A single row captures one (prediction run, rider) pair. A prediction run
is identified by (fc_race_id, year, stage_number, predicted_at). The same
rider in the same race can be logged multiple times across runs — each
run is a separate "opinion" the app produced, e.g. after a start-list
change or after re-running against different reference races.

`competition_id` is filled in at write time when the target race already
exists in `competitions`; otherwise it stays NULL until a later join can
resolve it.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS prediction_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    predicted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fc_race_id TEXT NOT NULL,
    year INTEGER NOT NULL,
    stage_number INTEGER,
    competition_id INTEGER,
    rider_id INTEGER NOT NULL,
    rider_name TEXT,
    reference_comp_ids TEXT,
    model_version TEXT,
    multiclass_win_p REAL,
    multiclass_podium_p REAL,
    multiclass_top5_p REAL,
    multiclass_top15_p REAL,
    lambdarank_win_p REAL,
    lambdarank_podium_p REAL,
    lambdarank_temperature REAL,
    FOREIGN KEY (competition_id) REFERENCES competitions(id),
    FOREIGN KEY (rider_id) REFERENCES riders(id)
);
"""

INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_prediction_log_fc_race ON prediction_log(fc_race_id, year);",
    "CREATE INDEX IF NOT EXISTS idx_prediction_log_competition ON prediction_log(competition_id);",
    "CREATE INDEX IF NOT EXISTS idx_prediction_log_rider ON prediction_log(rider_id);",
    "CREATE INDEX IF NOT EXISTS idx_prediction_log_predicted_at ON prediction_log(predicted_at);",
]


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create prediction_log table + indexes if they don't already exist."""
    conn.execute(SCHEMA_SQL)
    for stmt in INDEX_SQL:
        conn.execute(stmt)
    conn.commit()


@dataclass
class PredictionLogRow:
    fc_race_id: str
    year: int
    rider_id: int
    stage_number: Optional[int] = None
    competition_id: Optional[int] = None
    rider_name: Optional[str] = None
    reference_comp_ids: List[int] = field(default_factory=list)
    model_version: Optional[str] = None
    multiclass_win_p: Optional[float] = None
    multiclass_podium_p: Optional[float] = None
    multiclass_top5_p: Optional[float] = None
    multiclass_top15_p: Optional[float] = None
    lambdarank_win_p: Optional[float] = None
    lambdarank_podium_p: Optional[float] = None
    lambdarank_temperature: Optional[float] = None

    def as_row(self) -> Dict[str, Any]:
        return {
            'fc_race_id': str(self.fc_race_id),
            'year': int(self.year),
            'stage_number': self.stage_number,
            'competition_id': self.competition_id,
            'rider_id': int(self.rider_id),
            'rider_name': self.rider_name,
            'reference_comp_ids': json.dumps(self.reference_comp_ids),
            'model_version': self.model_version,
            'multiclass_win_p': _as_float(self.multiclass_win_p),
            'multiclass_podium_p': _as_float(self.multiclass_podium_p),
            'multiclass_top5_p': _as_float(self.multiclass_top5_p),
            'multiclass_top15_p': _as_float(self.multiclass_top15_p),
            'lambdarank_win_p': _as_float(self.lambdarank_win_p),
            'lambdarank_podium_p': _as_float(self.lambdarank_podium_p),
            'lambdarank_temperature': _as_float(self.lambdarank_temperature),
        }


def _as_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
        if pd.isna(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def resolve_competition_id(
    conn: sqlite3.Connection,
    fc_race_id: str,
    year: int,
    stage_number: Optional[int],
) -> Optional[int]:
    """Look up the DB competition_id for a given FirstCycling race identifier.

    Returns None if the race (or specific stage) isn't in the DB yet, which
    is expected for future races scheduled but not yet raced.
    """
    if stage_number is None:
        # One-day or overall — fetch the sole competition for the race.
        cur = conn.execute(
            """
            SELECT c.id FROM competitions c
            JOIN races r ON c.race_id = r.id
            WHERE r.fc_race_id = ? AND r.year = ?
              AND c.stage_number IS NULL
            ORDER BY c.id LIMIT 1
            """,
            (str(fc_race_id), int(year)),
        )
    else:
        cur = conn.execute(
            """
            SELECT c.id FROM competitions c
            JOIN races r ON c.race_id = r.id
            WHERE r.fc_race_id = ? AND r.year = ?
              AND c.stage_number = ?
            ORDER BY c.id LIMIT 1
            """,
            (str(fc_race_id), int(year), int(stage_number)),
        )
    row = cur.fetchone()
    return int(row[0]) if row else None


def log_predictions(
    conn: sqlite3.Connection,
    rows: Iterable[PredictionLogRow],
) -> int:
    """Insert a batch of prediction rows. Returns number of rows inserted."""
    ensure_schema(conn)
    payload = [r.as_row() for r in rows]
    if not payload:
        return 0

    cols = list(payload[0].keys())
    placeholders = ", ".join([f":{c}" for c in cols])
    sql = f"INSERT INTO prediction_log ({', '.join(cols)}) VALUES ({placeholders})"
    conn.executemany(sql, payload)
    conn.commit()
    return len(payload)


def fetch_with_actuals(
    conn: sqlite3.Connection,
    since: Optional[datetime] = None,
    limit: Optional[int] = None,
) -> pd.DataFrame:
    """Return logged predictions joined with actual finishing places (where available).

    Unresolved logs (competition_id NULL) are included with NULL `place`
    so the caller can filter or re-run `backfill_competition_ids` first.
    """
    where = ["1=1"]
    params: List[Any] = []
    if since is not None:
        where.append("p.predicted_at >= ?")
        params.append(since.isoformat())
    where_sql = " AND ".join(where)

    limit_sql = f"LIMIT {int(limit)}" if limit else ""

    sql = f"""
        SELECT
            p.*,
            rr.place AS actual_place,
            rr.place_bucket AS actual_bucket
        FROM prediction_log p
        LEFT JOIN rider_results rr
          ON rr.competition_id = p.competition_id
         AND rr.rider_id = p.rider_id
        WHERE {where_sql}
        ORDER BY p.predicted_at DESC
        {limit_sql}
    """
    return pd.read_sql_query(sql, conn, params=params)


def backfill_competition_ids(conn: sqlite3.Connection) -> int:
    """Resolve any NULL competition_id rows against the current races/competitions.

    Returns the number of rows updated. Safe to run repeatedly.
    """
    ensure_schema(conn)

    # Pull distinct unresolved (fc_race_id, year, stage_number) tuples.
    cur = conn.execute(
        """
        SELECT DISTINCT fc_race_id, year, stage_number
        FROM prediction_log
        WHERE competition_id IS NULL
        """
    )
    unresolved = cur.fetchall()

    updated = 0
    for fc_race_id, year, stage_number in unresolved:
        comp_id = resolve_competition_id(conn, fc_race_id, year, stage_number)
        if comp_id is None:
            continue
        if stage_number is None:
            cur = conn.execute(
                """
                UPDATE prediction_log
                SET competition_id = ?
                WHERE competition_id IS NULL
                  AND fc_race_id = ? AND year = ?
                  AND stage_number IS NULL
                """,
                (comp_id, fc_race_id, year),
            )
        else:
            cur = conn.execute(
                """
                UPDATE prediction_log
                SET competition_id = ?
                WHERE competition_id IS NULL
                  AND fc_race_id = ? AND year = ?
                  AND stage_number = ?
                """,
                (comp_id, fc_race_id, year, stage_number),
            )
        updated += cur.rowcount

    conn.commit()
    return updated
