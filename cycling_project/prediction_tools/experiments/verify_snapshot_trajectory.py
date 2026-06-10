"""
Post-rebuild validation: rebuilt snapshot trajectory columns vs the lab cache.

The logic-level parity (verify_trajectory_parity) validated the production
math on replayed histories. This checks the *wiring* end-to-end after the
snapshot rebuild: column order in the INSERT, percentile plumbing through
get_results_for_competitions, GC start dates from the precompute path, and
coverage. Samples snapshot rows 2016+ and compares each trajectory column
against the CV-validated lab cache.

Tolerances: values equal within 1e-6. GC rows of race-years whose stages
have no results are excluded (documented divergence — production anchors at
the true race start; the lab could not see it). A small residual NaN/value
mismatch rate (<0.1%) is reported but not fatal IF confined to that class.

Usage:
    uv run python -m cycling_project.prediction_tools.experiments.verify_snapshot_trajectory
"""

import sqlite3
from pathlib import Path

import pandas as pd

from cycling_project.engineering_tools.form_team_features import TRAJECTORY_FORM_COLUMNS

DB_PATH = (
    Path(__file__).parent.parent.parent
    / "webscrape_tools" / "database" / "database" / "cycling_races.db"
)
LAB_CACHE = Path('experiments/form_lab_features_v1.csv.gz')
SAMPLE = 60_000
TOL = 1e-6


def main():
    conn = sqlite3.connect(DB_PATH)
    cols = ', '.join(f's.{c}' for c in TRAJECTORY_FORM_COLUMNS)
    snap = pd.read_sql_query(f"""
        SELECT s.rider_id, s.competition_id, c.competition_type,
               c.race_id, r.year AS race_year, {cols}
        FROM rider_competition_snapshots s
        JOIN competitions c ON c.id = s.competition_id
        JOIN races r ON r.id = c.race_id
        WHERE c.date >= '2016-01-01'
        ORDER BY (s.rider_id * 2654435761) % 100000, s.competition_id
        LIMIT {SAMPLE}
    """, conn)

    divergent = {
        (row[0], row[1])
        for row in conn.execute("""
            SELECT g.race_id, g.year FROM (
                SELECT c.race_id, r.year,
                       MIN(c.date) AS table_start,
                       MIN(CASE WHEN EXISTS (
                           SELECT 1 FROM rider_results rr
                           WHERE rr.competition_id = c.id
                       ) THEN c.date END) AS results_start
                FROM competitions c JOIN races r ON r.id = c.race_id
                WHERE c.competition_type IN ('stage', 'one_day')
                GROUP BY c.race_id, r.year
            ) g
            WHERE g.results_start IS NULL OR g.results_start != g.table_start
        """)
    }
    conn.close()
    print(f"Sampled {len(snap):,} snapshot rows; "
          f"{len(divergent):,} divergent race-years to exclude (GC rows only)")

    gc_divergent = snap['competition_type'].eq('gc') & snap.apply(
        lambda r: (r['race_id'], r['race_year']) in divergent, axis=1
    )
    snap = snap[~gc_divergent]
    print(f"After exclusion: {len(snap):,} rows")

    lab = pd.read_csv(LAB_CACHE)
    merged = snap.merge(
        lab, on=['rider_id', 'competition_id'], how='inner',
        suffixes=('_snap', '_lab'),
    )
    print(f"Matched to lab: {len(merged):,} rows")

    print(f"\n{'column':<26s} {'n_both':>8s} {'mismatch':>9s} {'nan_mismatch':>13s} {'snap_cov':>9s}")
    worst = 0
    for c in TRAJECTORY_FORM_COLUMNS:
        s = merged[f'{c}_snap'].astype(float)
        l = merged[f'{c}_lab'].astype(float)
        both = s.notna() & l.notna()
        nan_mm = int((s.isna() != l.isna()).sum())
        bad = int(((s[both] - l[both]).abs() > TOL).sum())
        cov = s.notna().mean()
        worst = max(worst, bad + nan_mm)
        flag = "" if (bad == 0 and nan_mm == 0) else "  <-- CHECK"
        print(f"{c:<26s} {int(both.sum()):>8,d} {bad:>9,d} {nan_mm:>13,d} {cov:>8.1%}{flag}")

    rate = worst / max(len(merged), 1)
    verdict = "SNAPSHOT PARITY OK" if rate < 0.001 else "SNAPSHOT PARITY FAILED"
    print(f"\n{verdict} (worst column mismatch rate {rate:.4%})")
    return 0 if rate < 0.001 else 1


if __name__ == '__main__':
    raise SystemExit(main())
