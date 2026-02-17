# Data Pipeline: Scraped Data to Final Database

This document describes how to integrate newly scraped race data into the production SQLite database.

## Overview

```
Scraped Pickle Files (~/cycling_data/scraped_data/YEAR/TOUR/*.pkl)
    ↓
Step 1: migrate_races.py → Core tables (races, competitions, riders, teams, rider_results)
    ↓
Step 2: migrate_bib_number_columns.py → Parse bib numbers into team_bib/personal_bib
    ↓
Step 3: migrate_precompute_experience_features.py → Add UCI points & race counts
    ↓
Step 4: feature_precomputation.py → Create rider snapshots & field features
    ↓
Final Database Ready for ML
```

---

## File Locations

| Item | Path |
|------|------|
| Scraped pickle files | `~/cycling_data/scraped_data/YEAR/TOUR/*.pkl` |
| Production database | `webscrape_tools/database/database/cycling_races.db` |
| Migration scripts | `webscrape_tools/database/` |
| Feature scripts | `engineering_tools/` |

---

## Step 1: Migrate Pickle Files to SQLite

**Script**: `webscrape_tools/database/migrate_races.py`

**What it does**:
- Reads pickle files from the hierarchical directory structure
- Creates records in: `races`, `competitions`, `riders`, `teams`, `rider_results`
- Handles both one-day races and stage races (with GC + individual stages)
- Calculates rider age and percentile for each result
- Caches rider/team IDs to avoid duplicates

**Usage**:
```bash
cd ~/Documents/Cycling\ Project

# Migrate a specific year
PYTHONPATH=. uv run python webscrape_tools/database/migrate_races.py --year 2025

# Migrate a specific year and category
PYTHONPATH=. uv run python webscrape_tools/database/migrate_races.py --year 2025 --category wt

# Migrate everything (all years)
PYTHONPATH=. uv run python webscrape_tools/database/migrate_races.py
```

**Default paths** (can be overridden with flags):
- `--source-dir`: `~/cycling_data/scraped_data`
- `--db-path`: `database/cycling_races.db`

---

## Step 2: Parse Bib Numbers

**Script**: `webscrape_tools/database/migrate_bib_number_columns.py`

**What it does**:
- Adds `team_bib` and `personal_bib` columns to `rider_results`
- Parses raw `bib_number` string:
  - 1-digit (e.g., "5"): team_bib=0, personal_bib=5
  - 2-digit (e.g., "35"): team_bib=3, personal_bib=5
  - 3-digit (e.g., "125"): team_bib=12, personal_bib=5

**Usage**:
```bash
cd ~/Documents/Cycling\ Project
PYTHONPATH=. uv run python webscrape_tools/database/migrate_bib_number_columns.py
```

---

## Step 3: Add Experience Features

**Script**: `webscrape_tools/database/migrate_precompute_experience_features.py`

**What it does**:
- Adds experience feature columns to `rider_results`
- Processes chronologically to prevent data leakage
- Computes for each result:
  - Prior UCI points by category (wt/pro/d1)
  - Prior UCI points by type (gc/stage/one_day)
  - Prior race counts by category and type
  - Total prior races and points

**Usage**:
```bash
cd ~/Documents/Cycling\ Project
PYTHONPATH=. uv run python webscrape_tools/database/migrate_precompute_experience_features.py
```

---

## Step 4: Feature Precomputation

**Script**: `engineering_tools/feature_precomputation.py`

**What it does**:
- Creates `rider_competition_snapshots` table (rider state at each race)
- Creates `competition_field_features` table (field aggregates + race profiles)
- Processes chronologically with checkpointing
- Can resume from last checkpoint if interrupted

**Usage**:
```bash
cd ~/Documents/Cycling\ Project

# Resume from last checkpoint (processes new data only)
PYTHONPATH=. uv run python -m engineering_tools.feature_precomputation

# Start from a specific date
PYTHONPATH=. uv run python -m engineering_tools.feature_precomputation 2025-01-01
```

**Key principle**: Snapshots contain only data from races PRIOR to the current one (no future leakage).

---

## Database Schema Summary

### Core Tables (from Step 1)

| Table | Key Columns |
|-------|-------------|
| `races` | id, fc_race_id, name, year, date, category, is_stage_race |
| `competitions` | id, race_id, name, stage_number, competition_type, date, winning_time |
| `riders` | id, fc_rider_id, name, birth_year |
| `teams` | id, fc_team_id, name |
| `rider_results` | id, competition_id, rider_id, team_id, place, time_gap, bib_number, rider_age, percentile |

### Enhanced Columns (from Steps 2-3)

Added to `rider_results`:
- `team_bib`, `personal_bib` (parsed bib numbers)
- `prior_wt_points`, `prior_pro_points`, `prior_d1_points`
- `prior_gc_points`, `prior_stage_points`, `prior_one_day_points`
- `prior_race_count`, `prior_total_points`

### Feature Tables (from Step 4)

| Table | Purpose |
|-------|---------|
| `rider_competition_snapshots` | Rider historical features at each race (~20 columns) |
| `competition_field_features` | Field strength + race profile (~40 columns) |
| `rider_features_running` | Current state for incremental updates |
| `feature_computation_checkpoint` | Resume point for feature computation |

---

## Complete Integration Example (2025 Data)

```bash
cd ~/Documents/Cycling\ Project

# Step 1: Migrate pickle files to database
PYTHONPATH=. uv run python webscrape_tools/database/migrate_races.py --year 2025

# Step 2: Parse bib numbers (runs on all data, handles new rows)
PYTHONPATH=. uv run python webscrape_tools/database/migrate_bib_number_columns.py

# Step 3: Add experience features (runs on all data, handles new rows)
PYTHONPATH=. uv run python webscrape_tools/database/migrate_precompute_experience_features.py

# Step 4: Compute rider/field features (resumes from checkpoint)
PYTHONPATH=. uv run python -m engineering_tools.feature_precomputation
```

---

## Verification Queries

After integration, verify with these SQL queries:

```sql
-- Check 2025 races were added
SELECT category, COUNT(*) as race_count
FROM races
WHERE year = 2025
GROUP BY category;

-- Check competitions created
SELECT r.category, c.competition_type, COUNT(*) as comp_count
FROM competitions c
JOIN races r ON c.race_id = r.id
WHERE r.year = 2025
GROUP BY r.category, c.competition_type;

-- Check results have bib numbers
SELECT COUNT(*) as total,
       SUM(CASE WHEN team_bib IS NOT NULL THEN 1 ELSE 0 END) as with_bibs
FROM rider_results rr
JOIN competitions c ON rr.competition_id = c.id
JOIN races r ON c.race_id = r.id
WHERE r.year = 2025;

-- Check feature computation coverage
SELECT COUNT(DISTINCT competition_id) as competitions_with_features
FROM rider_competition_snapshots rcs
JOIN competitions c ON rcs.competition_id = c.id
JOIN races r ON c.race_id = r.id
WHERE r.year = 2025;
```

---

## Troubleshooting

### Duplicate race errors
The migration script checks for existing `fc_race_id` before inserting. If you get duplicate errors, the race may already exist. Check:
```sql
SELECT * FROM races WHERE year = 2025 AND name LIKE '%Race Name%';
```

### Missing bib numbers
Some older races may not have startlist data. The bib parsing step will skip NULL values.

### Feature computation not picking up new data
Check the checkpoint table:
```sql
SELECT * FROM feature_computation_checkpoint;
```
If `last_processed_date` is after your new data, you may need to reset or specify a start date.

---

## Notes

- The database uses SQLite with foreign keys enabled
- All migrations are idempotent where possible (can re-run safely)
- Feature computation has built-in checkpointing for long runs
- Batch commits happen every 10-50 records to balance safety and performance
