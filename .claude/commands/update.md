---
description: Run the weekly update pipeline (scrape, migrate, features, train)
argument-hint: [--dry-run | --skip-scrape | --skip-train | --only <step>]
---

# Weekly Update Pipeline

Run the cycling data update pipeline and report results.

## Steps

1. **Determine arguments**: If the user provided arguments via `$ARGUMENTS`, pass them through. If no arguments were given, run the full pipeline. Common options:
   - `--dry-run` — preview what would run without executing
   - `--skip-scrape` — skip scraping (data already up to date)
   - `--skip-migrate` — skip SQLite migration steps
   - `--skip-features` — skip feature building
   - `--skip-train` — skip model training
   - `--only <step>` — run a single step (scrape-lists, scrape-data, migrate, place-bucket, bib, experience, percentiles, gradients, features, train)
   - `-v` — verbose/debug logging

2. **Run the pipeline**:
   ```bash
   uv run python -m cycling_project.update_pipeline $ARGUMENTS
   ```

3. **Monitor and report**: The pipeline prints a summary table at the end. After it completes:
   - Report which steps ran and their status (OK / FAILED)
   - Report total elapsed time
   - If any step failed, read the error output and analyze the root cause
   - Suggest specific fixes for any failures (e.g., network issues for scraping, schema issues for migration)

4. **If the pipeline succeeds fully**, confirm that models were updated by checking the modification time of files in `models/production/`.
