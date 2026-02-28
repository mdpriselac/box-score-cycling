# Cycling Race Predictor

Predicts professional cycling race outcomes using LightGBM models trained on historical FirstCycling data. A Streamlit web app lets you enter a race start list URL, select reference races, and generate finishing predictions.

## Quick Start

```bash
uv sync
uv run streamlit run cycling_project/web/app.py
```

## Project Structure

```
cycling_project/
  update_pipeline.py        Weekly update pipeline (scrape, migrate, build, train)
  web/app.py                Streamlit frontend
  prediction_tools/         ML pipeline (training, inference, evaluation)
  webscrape_tools/          FirstCycling scraping + SQLite database tools
  engineering_tools/        Feature precomputation + race profile scoring
  data_loading_tools/       Pickle-to-memory data loading
  data_cleaning_tools/      Date verification + data standardization
  data_validation_tools/    Data quality checks
  tests/                    Unit + integration tests
models/production/          LightGBM models (bucket + time gap)
```

## Weekly Update Pipeline

The update pipeline (`cycling_project/update_pipeline.py`) is a single script that keeps the entire system current. It automatically determines what data is new based on the latest date in the SQLite database, then runs each step in sequence:

1. **Scrape race lists** — fetches race calendars from FirstCycling for missing months
2. **Scrape race data** — downloads individual race results (incremental, skips existing files)
3. **Migrate to SQLite** — loads new scraped pickle files into the database (skips duplicates)
4. **Backfill place buckets** — ensures all rider results have placement categories
5. **Bib number migration** — populates bib number columns
6. **Experience features** — precomputes rider experience metrics
7. **Percentile tables** — builds statistical percentile tables for target years
8. **Gradient calculation** — computes performance gradients for unprocessed competitions
9. **Feature precomputation** — rebuilds rider snapshots and field-level features
10. **Train production model** — retrains the LightGBM models

### Usage

```bash
# Full pipeline (all 10 steps)
uv run python -m cycling_project.update_pipeline

# Preview what would run without executing
uv run python -m cycling_project.update_pipeline --dry-run

# Skip scraping (useful if data files are already up to date)
uv run python -m cycling_project.update_pipeline --skip-scrape

# Skip migration steps
uv run python -m cycling_project.update_pipeline --skip-migrate

# Skip feature building
uv run python -m cycling_project.update_pipeline --skip-features

# Skip model training
uv run python -m cycling_project.update_pipeline --skip-train

# Run a single step only
uv run python -m cycling_project.update_pipeline --only train

# Verbose logging
uv run python -m cycling_project.update_pipeline -v
```

Valid `--only` step names: `scrape-lists`, `scrape-data`, `migrate`, `place-bucket`, `bib`, `experience`, `percentiles`, `gradients`, `features`, `train`.

### Configuration

The pipeline resolves paths automatically from the project root. Scraped data defaults to `~/cycling_data/scraped_data/`. To override, set `SCRAPED_DATA_DIR` in a `.env` file at the project root.

## Other Workflows

**Predict a race**: Enter a FirstCycling URL in the web app, select reference races, generate predictions.

**Train models manually**: `uv run python -m cycling_project.prediction_tools.train_production_model`

See `DEPLOYMENT_PLAN.md` for Streamlit Cloud deployment instructions.
