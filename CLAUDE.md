# Cycling Race Predictor

LightGBM-based prediction of professional cycling race outcomes, trained on historical FirstCycling data. Streamlit web app for inference.

## Common Commands

```bash
uv sync                                                  # install dependencies
uv run streamlit run cycling_project/web/app.py          # launch web app
uv run python -m cycling_project.update_pipeline         # full weekly update
uv run python -m cycling_project.update_pipeline --dry-run  # preview pipeline
uv run pytest                                            # run all tests
uv run pytest -m unit                                    # unit tests only
```

## Architecture

Data flows through a linear pipeline:

```
FirstCycling HTML → scrape → pickle files → migrate → SQLite DB
→ feature engineering → rider/field snapshots → train → LightGBM models
→ web app inference
```

**Module responsibilities:**

| Module | Role |
|--------|------|
| `webscrape_tools/` | Scraping (scrape_client, find_races, download_race_data) + SQLite migrations (`database/`) |
| `engineering_tools/` | Feature precomputation, race profile scoring, form/team features |
| `prediction_tools/` | Training pipeline, feature engineering, bucket + time gap + multiclass cascade + LambdaRank predictors, inference, prediction_log persistence |
| `data_loading_tools/` | Pickle-to-memory data loading |
| `data_cleaning_tools/` | Date verification, data standardization |
| `data_validation_tools/` | Data quality checks |
| `web/` | Streamlit frontend (`app.py`) |
| `update_pipeline.py` | Orchestrates all 15 steps: scrape → migrate → features → elo-snapshots → train → train-lambdarank → train-gc-outlook → train-dnf |

## Key Paths

| Path | Contents |
|------|----------|
| `cycling_project/webscrape_tools/database/database/cycling_races.db` | SQLite database (also hosts the `prediction_log` table written by the web app) |
| `models/production/` | Trained LightGBM models: bucket, time gap, multiclass cascade (weighted/calibrated/contender), LambdaRank probability head, GC outlook head, DNF head (`dnf_*` + `dnf_events.parquet`), contested-Elo snapshots (`contested_rating_snapshots.parquet`), win corrector (`win_calibration.json`) |
| `~/cycling_data/scraped_data/` | Scraped pickle files (default; override with `SCRAPED_DATA_DIR` in `.env`) |
| `cycling_project/tests/fixtures/` | Test fixtures (HTML pages, mock data) |
| `experiments/` | JSON results from CV / experiment runs (see `experiment_log.md` for the narrative) |

## Conventions

- **Imports**: Always absolute — `from cycling_project.webscrape_tools.X import Y`
- **Module invocation**: Run as modules — `uv run python -m cycling_project.update_pipeline`, not as scripts
- **Logging**: Use the shared logger — `from cycling_project.webscrape_tools.logging_config import get_logger; logger = get_logger(__name__)`
- **Paths**: Use `pathlib.Path`; resolve relative to `__file__`, never hardcode absolute paths
- **Data structures**: `@dataclass` for domain objects (Race, Stage, RiderRunningState, etc.)
- **Database**: SQLite with `PRAGMA foreign_keys = ON`; always use parameterized queries
- **Package manager**: `uv` (not pip)

## Testing

- Framework: **pytest** with `pytest.ini` in `cycling_project/`
- Markers: `unit`, `integration`, `slow`
- Structure: `tests/unit/`, `tests/integration/`, `tests/fixtures/`, `tests/utils/`
- Mock pattern: `tests/utils/` provides `MockWebClient` and `MockResponse` for scraper tests
- Run from project root: `uv run pytest`

## Gotchas

- **Rate limiting**: `scrape_client.py` enforces 3-second minimum between HTTP requests with random jitter. Do not bypass this.
- **Pickle files**: Legacy intermediate format between scraping and SQLite. The migration step converts these to DB rows.
- **Pipeline halts on critical failures**: Steps like migrate, percentiles, gradients, and features will stop the pipeline if they fail. Scraping, training, and LambdaRank-head training failures are non-fatal.
- **Two probability heads**: `prediction_tools/probability_predictor.py` is the multiclass contender cascade (used for ranking). `prediction_tools/lambdarank_probability_predictor.py` is the full-field LambdaRank head (used for calibrated probabilities — book comparison). The web app shows both side-by-side.
- **Production training start_date is `2016-01-01`** in both `train_production_model.py` and `train_lambdarank_production.py` (was 2018; moved on 2026-04-18 after a CV sweep — see experiment_log.md).
- **Trajectory form features are NULL by design**: the `v2_*`/`v3_*` snapshot columns (EMA percentile + multi-season trajectory, added 2026-06-10) are intentionally NULL when a rider lacks qualifying history. Do not add imputation defaults for them — LightGBM consumes NaN natively, and their names deliberately avoid the pattern-based imputation in `feature_engineering.py` (`'avg_bucket'`, `'_count'`). See `form_team_features.get_trajectory_form_features` and experiment_log.md (2026-06-10).
