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


## Credentials (for nightly tooling, chips, and the weekly run)

- **Never in the repo.** `.env` (gitignored, non-secret: DB_PATH, SCRAPER_*) is
  mirrored to `~/.config/cycling-project/env`; secrets live only in
  `~/.config/cycling-project/secrets.env` (chmod 600). Git worktrees have no
  `.env`, so always load via the helper.
- **Load in Python**: `from cycling_project.nightly.secrets import load_local_env;
  load_local_env(require=("SUPABASE_URL",))` — exported env wins, then repo
  `.env`, then the two files. **Load in a shell**:
  `set -a; source ~/.config/cycling-project/secrets.env; set +a`.
  Check what is set (names only): `uv run python -m cycling_project.nightly.secrets`.
- Variable names: `ANTHROPIC_API_KEY` (or `ant auth login` OAuth profile — preferred),
  `SUPABASE_URL/PROJECT_REF/DB_PASSWORD/SECRET_KEY/PUBLISHABLE_KEY/JWT_SECRET/
  NIGHTLY_KEY/RELEASE_READER_KEY`, `CLOUDFLARE_ACCOUNT_ID/API_TOKEN`, `NTFY_TOPIC`
  or `PUSHOVER_*`. `SUPABASE_SECRET_KEY` is operator-only: it must never be
  provisioned into an agent vault, prompt, or log. Use `secrets.redact()` on any
  log line that might echo a value.
- The Managed Agents cloud container gets the SAME variable names as vault
  placeholders (substituted at egress); code must send keys in headers only,
  never in URLs or bodies.

## Gotchas

- **`python -m cycling_project.nightly … --store auto` (the default) talks to the HOSTED Supabase ledger** whenever `SUPABASE_URL` + `SUPABASE_NIGHTLY_KEY` load from `~/.config/cycling-project/secrets.env` — i.e. on this Mac. Tests and experiments must pass `--store fake` (or `--dry-run`); rows in `runs` / `run_steps` are append-only for the agent role and only the service key can remove them. (2026-09-06: seven test `ingest` runs landed in the hosted `runs` table this way.)
- **Results provider is UCI first, PCS fallback** (2026-09-06, `NIGHTLY_AGENT_WORKFLOW.md` §2.8): `uci_acquire.py` (deterministic, ≥ 3 s between requests, verbatim capture, idempotent) → `uci_ingest.py` (validators + FC-shaped archive) → `uci_identity.py` (roster-scoped name bridge, `uci_aliases.csv` for human-confirmed aliases; names are never ids). PCS's Cloudflare wall now also blocks Anthropic's `web_fetch`; `pcs_ingest.py` stays as the fallback path. Do not probe PCS.
- **A campaign's `uci_competition_url` comes from `uci_calendar.py`, never from a guess** (2026-09-07, report `performance_eval/runs/uci_calendar_report_2026-09-07.md`): the whole road season is two requests (`/api/calendar/upcoming` + `/api/calendar/past`, `?discipline=ROA`, no token, no cookies) archived under `cycling_project/tests/fixtures/uci/calendar/`; `uci_calendar resolve` (and `registry sync`, same matcher) writes a URL only on an exact date range with name similarity >= 0.90 and no rival candidate, otherwise it raises a `uci_competition_confirm` operator task and leaves the field null. A URL already set is never overwritten. **One-day races** publish ONE classification titled "General Classification" under an accordion entry labelled "Final Classification" - `uci_acquire` handles that (unit `race` or `one_day`, `required_kinds()`), and since 2026-09-08 so does `uci_ingest`: that one document is the race result, and no `gc.csv` is written.

- **A one-day race is one unit called `race`** (2026-09-08, `NIGHTLY_AGENT_WORKFLOW.md` §2.6, `cycling_project/nightly/oneday.py`): config `predictions/race/scenarios.json` with `target: one_day`, results `results/race/`, page `netlify_site/<slug>-<year>.html` via `build_oneday_page.py`, hub `/race/<slug>/<year>` with the board at `/race/<slug>/<year>/prediction`. It carries **no `day_key`** (the day menu prices stage-day shapes) and no `void_stages`; the default scenario's references are the race's own last five editions. **Form is re-aged to the day the board is built, not to the config's race date** — right for a board cut on race morning, a leak for a reconstruction, so mark a rebuilt config `post_hoc: true` and the page says so.

- **Rate limiting**: `scrape_client.py` enforces 3-second minimum between HTTP requests with random jitter. Do not bypass this.
- **Pickle files**: Legacy intermediate format between scraping and SQLite. The migration step converts these to DB rows.
- **In-progress stage races flow through the weekly pipeline** (2026-07-12): a mid-race pickle re-scrapes every run (its unraced stages are undated — FirstCycling omits the date div on unraced stage pages), and `migrate_new_races` deletes+re-migrates a race whose pickle gained result-bearing stages or the final GC (competition ids change; dependent tables rebuild in later feature steps). Mid-race, the race page serves only the DNF board (place='DNF') as race-level results — a `gc` competition is created from CLASSIFIED rows only. Serving reads race state DB-first (`live_race_state`), and the TdF scenario runner prices the ACTIVE field only (abandons fall out of the reconstructed standings; config `exclude_riders` covers announced withdrawals). **Settled races with a cancelled stage are exempt** (2026-08-09): a result-less past-dated stage in a race that is settled — final GC posted, or every stage dated with the last one past `RESULTS_POSTING_GRACE_DAYS` (FirstCycling publishes NO GC when a short race loses a stage, e.g. Vuelta a Murcia 2026) — is legitimately empty, so the pickle is not stale and the zero-result stage competition does not mark the race incomplete; before this, such races (incl. Vuelta a España 2025) were deleted + re-migrated every run, churning competition ids. Tests: `tests/unit/test_midrace_refresh.py`.
- **Pipeline halts on critical failures**: Steps like migrate, percentiles, gradients, and features will stop the pipeline if they fail. Scraping, training, and LambdaRank-head training failures are non-fatal.
- **Two probability heads**: `prediction_tools/probability_predictor.py` is the multiclass contender cascade (used for ranking). `prediction_tools/lambdarank_probability_predictor.py` is the full-field LambdaRank head (used for calibrated probabilities — book comparison). The web app shows both side-by-side.
- **Production training start_date is `2016-01-01`** in both `train_production_model.py` and `train_lambdarank_production.py` (was 2018; moved on 2026-04-18 after a CV sweep — see experiment_log.md).
- **Trajectory form features are NULL by design**: the `v2_*`/`v3_*` snapshot columns (EMA percentile + multi-season trajectory, added 2026-06-10) are intentionally NULL when a rider lacks qualifying history. Do not add imputation defaults for them — LightGBM consumes NaN natively, and their names deliberately avoid the pattern-based imputation in `feature_engineering.py` (`'avg_bucket'`, `'_count'`). See `form_team_features.get_trajectory_form_features` and experiment_log.md (2026-06-10).
