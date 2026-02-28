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
| `prediction_tools/` | Training pipeline, feature engineering, bucket + time gap predictors, inference |
| `data_loading_tools/` | Pickle-to-memory data loading |
| `data_cleaning_tools/` | Date verification, data standardization |
| `data_validation_tools/` | Data quality checks |
| `web/` | Streamlit frontend (`app.py`) |
| `update_pipeline.py` | Orchestrates all 10 steps: scrape → migrate → features → train |

## Key Paths

| Path | Contents |
|------|----------|
| `cycling_project/webscrape_tools/database/database/cycling_races.db` | SQLite database |
| `models/production/` | Trained LightGBM models (bucket + time gap) |
| `~/cycling_data/scraped_data/` | Scraped pickle files (default; override with `SCRAPED_DATA_DIR` in `.env`) |
| `cycling_project/tests/fixtures/` | Test fixtures (HTML pages, mock data) |

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
- **Cloudflare**: Uses `cloudscraper` library (not plain requests/httpx) for FirstCycling pages.
- **Pickle files**: Legacy intermediate format between scraping and SQLite. The migration step converts these to DB rows.
- **Pipeline halts on critical failures**: Steps like migrate, percentiles, gradients, and features will stop the pipeline if they fail. Scraping and training failures are non-fatal.
