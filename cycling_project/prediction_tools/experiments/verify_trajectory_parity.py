"""
Parity check: production trajectory-form features vs the CV-validated lab.

Replays sampled riders' real result histories through the production
RiderFormHistory (engineering_tools/form_team_features.py) exactly as the
precompute does — chronological add_race after computing features — and
compares every (rider, competition) value against the cached lab features
that cleared the 5-fold gate. The two implementations are independent
(numpy-vectorized vs pure-Python running state), so agreement here validates
the production port before committing to the full snapshot rebuild.

Usage:
    uv run python -m cycling_project.prediction_tools.experiments.verify_trajectory_parity
"""

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from cycling_project.engineering_tools.form_team_features import (
    RiderFormHistory,
    TRAJECTORY_FORM_COLUMNS,
)

DB_PATH = (
    Path(__file__).parent.parent.parent
    / "webscrape_tools" / "database" / "database" / "cycling_races.db"
)
LAB_CACHE = Path('experiments/form_lab_features_v1.csv.gz')
HISTORY_START = '2010-01-01'
TOL = 1e-6


def _sample_riders(conn) -> list:
    """~40 riders: heavy careers, recent veterans, and random fill."""
    heavy = [r[0] for r in conn.execute("""
        SELECT rider_id FROM rider_results GROUP BY rider_id
        HAVING COUNT(*) >= 100 ORDER BY rider_id LIMIT 20
    """)]
    vets = [r[0] for r in conn.execute("""
        SELECT DISTINCT rr.rider_id FROM rider_results rr
        JOIN competitions c ON c.id = rr.competition_id
        WHERE c.date >= '2024-01-01' AND rr.rider_age >= 34
        ORDER BY rr.rider_id LIMIT 10
    """)]
    rand = [r[0] for r in conn.execute("""
        SELECT DISTINCT rider_id FROM rider_results
        WHERE rider_id % 97 = 3 LIMIT 10
    """)]
    return sorted(set(heavy + vets + rand))


def main():
    conn = sqlite3.connect(DB_PATH)
    riders = _sample_riders(conn)
    print(f"Sampled {len(riders)} riders")

    # Race start dates, exactly as precompute_race_start_dates builds them
    race_starts = {
        (row[0], row[1]): row[2]
        for row in conn.execute("""
            SELECT c.race_id, r.year, MIN(c.date)
            FROM competitions c JOIN races r ON c.race_id = r.id
            WHERE c.competition_type IN ('stage', 'one_day')
            GROUP BY c.race_id, r.year
        """)
    }

    # Known divergence: the lab derived race starts from rows that HAVE
    # results, so races whose stages were never scraped anchor GC windows at
    # the GC's own date there; production (correctly) uses the competitions
    # table. Identify those (race_id, year) pairs and set their GC rows
    # aside rather than fail parity on them.
    lab_starts = {
        (row[0], row[1]): row[2]
        for row in conn.execute("""
            SELECT c.race_id, r.year, MIN(c.date)
            FROM competitions c JOIN races r ON c.race_id = r.id
            WHERE EXISTS (
                SELECT 1 FROM rider_results rr WHERE rr.competition_id = c.id
            )
            GROUP BY c.race_id, r.year
        """)
    }
    divergent_races = {
        key for key, start in race_starts.items()
        if key in lab_starts and lab_starts[key] != start
    }
    print(f"Race-years with start-date divergence (stages without results): "
          f"{len(divergent_races)}")

    placeholders = ','.join('?' * len(riders))
    rows = pd.read_sql_query(f"""
        SELECT rr.rider_id, rr.competition_id, rr.place_bucket, rr.percentile,
               c.date AS comp_date, c.competition_type, c.race_id,
               r.year AS race_year, r.category AS race_category
        FROM rider_results rr
        JOIN competitions c ON c.id = rr.competition_id
        JOIN races r ON r.id = c.race_id
        WHERE rr.rider_id IN ({placeholders})
          AND c.date IS NOT NULL AND c.date >= ?
          AND rr.place_bucket IS NOT NULL AND rr.place_bucket != 7
        ORDER BY rr.rider_id, c.date, c.id
    """, conn, params=[*riders, HISTORY_START])
    conn.close()
    print(f"Loaded {len(rows):,} result rows")

    lab = pd.read_csv(LAB_CACHE)
    lab = lab[lab['rider_id'].isin(riders)].set_index(['rider_id', 'competition_id'])
    print(f"Lab rows for sample: {len(lab):,}")

    produced = []
    n_divergent_skipped = 0
    for rider_id, g in rows.groupby('rider_id', sort=False):
        hist = RiderFormHistory(rider_id=int(rider_id))
        for row in g.itertuples(index=False):
            start = race_starts.get((row.race_id, row.race_year), row.comp_date)
            if (row.competition_type == 'gc'
                    and (row.race_id, row.race_year) in divergent_races):
                # Production anchors the GC window at the true race start;
                # the lab couldn't see it. Skip comparison, still add_race.
                n_divergent_skipped += 1
                hist.add_race(
                    date=row.comp_date,
                    bucket=int(row.place_bucket),
                    race_id=int(row.race_id),
                    race_year=int(row.race_year),
                    comp_type=row.competition_type,
                    profile='unknown',
                    percentile=row.percentile,
                    race_category=row.race_category,
                )
                continue
            if row.comp_date >= '2016-01-01':
                feats = hist.get_trajectory_form_features(
                    target_date=row.comp_date,
                    target_year=int(row.race_year),
                    target_race_id=int(row.race_id),
                    target_comp_type=row.competition_type,
                    race_start_date=start if row.competition_type == 'gc' else None,
                )
                feats['rider_id'] = int(rider_id)
                feats['competition_id'] = int(row.competition_id)
                produced.append(feats)
            hist.add_race(
                date=row.comp_date,
                bucket=int(row.place_bucket),
                race_id=int(row.race_id),
                race_year=int(row.race_year),
                comp_type=row.competition_type,
                profile='unknown',  # not used by trajectory features
                percentile=row.percentile,
                race_category=row.race_category,
            )

    prod = pd.DataFrame(produced).set_index(['rider_id', 'competition_id'])
    common = prod.index.intersection(lab.index)
    print(f"Comparable rows: {len(common):,} "
          f"(prod {len(prod):,}, lab-only {len(lab.index.difference(prod.index)):,}, "
          f"divergent-GC skipped {n_divergent_skipped:,})")

    print(f"\n{'column':<26s} {'n':>7s} {'mismatch':>9s} {'max|diff|':>10s} {'nan_mismatch':>13s}")
    all_ok = True
    for col in TRAJECTORY_FORM_COLUMNS:
        p = prod.loc[common, col].astype(float)
        l = lab.loc[common, col].astype(float)
        both = p.notna() & l.notna()
        nan_mismatch = int((p.isna() != l.isna()).sum())
        diffs = (p[both] - l[both]).abs()
        n_bad = int((diffs > TOL).sum())
        max_diff = float(diffs.max()) if both.any() else 0.0
        flag = "" if (n_bad == 0 and nan_mismatch == 0) else "  <-- MISMATCH"
        if flag:
            all_ok = False
        print(f"{col:<26s} {int(both.sum()):>7,d} {n_bad:>9,d} {max_diff:>10.2e} "
              f"{nan_mismatch:>13,d}{flag}")

    print(f"\n{'PARITY OK' if all_ok else 'PARITY FAILED'}")
    return 0 if all_ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
