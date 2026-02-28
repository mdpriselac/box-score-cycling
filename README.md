# Cycling Race Predictor

Predicts professional cycling race outcomes using LightGBM models trained on historical FirstCycling data. A Streamlit web app lets you enter a race start list URL, select reference races, and generate finishing predictions.

## Quick Start

```bash
uv sync
uv run streamlit run cycling_project/web/app.py
```

## Project Structure

```
models/production/          LightGBM models (bucket + time gap)
cycling_project/
  web/app.py                Streamlit frontend
  prediction_tools/         ML pipeline (training, inference, evaluation)
  webscrape_tools/          FirstCycling scraping + SQLite database tools
  engineering_tools/        Feature precomputation + race profile scoring
  data_loading_tools/       Pickle-to-memory data loading
  data_cleaning_tools/      Date verification + data standardization
  data_validation_tools/    Data quality checks
  tests/                    Unit + integration tests
```

## Key Workflows

**Predict a race**: Enter a FirstCycling URL in the web app, select reference races, generate predictions.

**Train models**: `uv run python cycling_project/prediction_tools/train_production_model.py`

**Scrape new data**: Use `webscrape_tools/download_race_data.py` to batch-scrape race results, then run the migration scripts in `webscrape_tools/database/` to populate the SQLite database.

**Rebuild features**: Run `engineering_tools/feature_precomputation.py` to recompute rider snapshots and field features.

See `DEPLOYMENT_PLAN.md` for Streamlit Cloud deployment instructions.
