---
description: Check database health, data freshness, and common issues
---

# Database Status Check

Query the SQLite database and report on its current state.

The database is located at: `cycling_project/webscrape_tools/database/database/cycling_races.db`

## Steps

1. **Check the database exists** at the expected path. If not found, report the issue.

2. **Run these diagnostic queries** using sqlite3:

   **Table row counts:**
   ```sql
   SELECT 'races' as tbl, COUNT(*) FROM races
   UNION ALL SELECT 'competitions', COUNT(*) FROM competitions
   UNION ALL SELECT 'rider_results', COUNT(*) FROM rider_results
   UNION ALL SELECT 'riders', COUNT(*) FROM riders
   UNION ALL SELECT 'rider_competition_snapshots', COUNT(*) FROM rider_competition_snapshots
   UNION ALL SELECT 'competition_field_features', COUNT(*) FROM competition_field_features;
   ```

   **Data freshness (latest race date):**
   ```sql
   SELECT MAX(c.date) as latest_date FROM competitions c JOIN races r ON c.race_id = r.id;
   ```

   **Races by year:**
   ```sql
   SELECT year, COUNT(*) as race_count FROM races GROUP BY year ORDER BY year DESC LIMIT 5;
   ```

   **Data quality — NULL place_buckets:**
   ```sql
   SELECT COUNT(*) FROM rider_results WHERE place_bucket IS NULL;
   ```

   **Feature computation status:**
   ```sql
   SELECT COUNT(*) as total_comps FROM competitions;
   ```
   ```sql
   SELECT COUNT(*) as with_snapshots FROM (SELECT DISTINCT competition_id FROM rider_competition_snapshots);
   ```
   ```sql
   SELECT COUNT(*) as with_field_features FROM (SELECT DISTINCT competition_id FROM competition_field_features);
   ```

3. **Present results** in a clear summary table. Highlight:
   - How fresh the data is (days since latest race)
   - Any data quality issues (NULL place_buckets, missing features)
   - Feature computation coverage (what percentage of competitions have snapshots and field features)

4. **Recommend actions** if issues are found (e.g., "Run `/update --skip-scrape` to rebuild features" or "Run `/update` to pull in recent race data").
