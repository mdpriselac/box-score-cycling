"""
Validation: live_form recompute vs stored snapshot form features.

For sampled past competitions, compute_form_features_asof(comp date) must
reproduce the form columns the precompute wrote into
rider_competition_snapshots — same classes, same data, so agreement here
validates the live path end to end (history loading, career averages,
GC start dates, profile plumbing).

Known tolerable deviations (reported, not fatal if rare):
  - riders with another competition on the SAME day: the precompute's
    career average updates between same-day comps in (date, id) order,
    while the live path cuts strictly before the day → tiny form_delta
    diffs on those rows only.

Usage:
    uv run python -m cycling_project.prediction_tools.experiments.verify_live_form
"""

import logging
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from cycling_project.prediction_tools.live_form import (
    LIVE_FORM_COLUMNS,
    compute_form_features_asof,
)

logging.disable(logging.INFO)  # one INFO line per comp otherwise

DB_PATH = (
    Path(__file__).parent.parent.parent
    / "webscrape_tools" / "database" / "database" / "cycling_races.db"
)
N_COMPS = 60
TOL = 1e-6


def main():
    conn = sqlite3.connect(DB_PATH)

    comps = pd.read_sql_query(f"""
        SELECT c.id, c.date, c.competition_type, c.race_id, r.year,
               COALESCE(cff.race_dominant_profile, 'unknown') AS dominant
        FROM competitions c
        JOIN races r ON r.id = c.race_id
        JOIN competition_field_features cff ON cff.competition_id = c.id
        WHERE c.date >= '2024-01-01'
        ORDER BY (c.id * 2654435761) % 100000
        LIMIT {N_COMPS}
    """, conn)
    print(f"Sampled {len(comps)} competitions "
          f"({comps['competition_type'].value_counts().to_dict()})")

    race_starts = {
        (row[0], row[1]): row[2]
        for row in conn.execute("""
            SELECT c.race_id, r.year, MIN(c.date)
            FROM competitions c JOIN races r ON c.race_id = r.id
            WHERE c.competition_type IN ('stage', 'one_day')
            GROUP BY c.race_id, r.year
        """)
    }

    total = {c: [0, 0, 0.0] for c in LIVE_FORM_COLUMNS}  # n, mismatch, maxdiff
    n_rows = 0

    for comp in comps.itertuples(index=False):
        stored = pd.read_sql_query(f"""
            SELECT rider_id, {', '.join(LIVE_FORM_COLUMNS)}
            FROM rider_competition_snapshots WHERE competition_id = {comp.id}
        """, conn)
        if stored.empty:
            continue

        live = compute_form_features_asof(
            rider_ids=stored['rider_id'].tolist(),
            asof_date=comp.date,
            comp_type=comp.competition_type,
            race_dominant_profile=comp.dominant,
            exclude_race=(comp.race_id, comp.year),
            race_start_date=race_starts.get((comp.race_id, comp.year), comp.date),
            db_path=str(DB_PATH),
            asof_comp_id=comp.id,
        )
        m = stored.merge(live, on='rider_id', suffixes=('_snap', '_live'))
        n_rows += len(m)

        for c in LIVE_FORM_COLUMNS:
            s = pd.to_numeric(m[f'{c}_snap'], errors='coerce')
            l = pd.to_numeric(m[f'{c}_live'], errors='coerce')
            both = s.notna() & l.notna()
            nan_mm = int((s.isna() != l.isna()).sum())
            diffs = (s[both] - l[both]).abs()
            bad = int((diffs > TOL).sum()) + nan_mm
            total[c][0] += int(both.sum()) + nan_mm
            total[c][1] += bad
            if both.any():
                total[c][2] = max(total[c][2], float(diffs.max()))

    conn.close()

    print(f"\nCompared {n_rows:,} snapshot rows across {len(comps)} comps")
    print(f"{'column':<26s} {'n':>8s} {'mismatch':>9s} {'rate':>8s} {'max|diff|':>10s}")
    worst_rate = 0.0
    for c, (n, bad, mx) in total.items():
        rate = bad / max(n, 1)
        worst_rate = max(worst_rate, rate)
        flag = "" if rate < 0.005 else "  <-- CHECK"
        print(f"{c:<26s} {n:>8,d} {bad:>9,d} {rate:>7.2%} {mx:>10.2e}{flag}")

    verdict = "LIVE FORM PARITY OK" if worst_rate < 0.005 else "LIVE FORM PARITY FAILED"
    print(f"\n{verdict} (worst column mismatch rate {worst_rate:.3%})")
    return 0 if worst_rate < 0.005 else 1


if __name__ == '__main__':
    raise SystemExit(main())
