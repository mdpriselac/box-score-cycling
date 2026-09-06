# Historical Streamlit deployment plan

> Superseded by [`CLOUDFLARE_DEPLOYMENT_PLAN.md`](CLOUDFLARE_DEPLOYMENT_PLAN.md).
> This file is retained as historical context for the earlier Streamlit/Turso
> proposal; it is not the current deployment direction.

## Deploy Cycling Predictor to Streamlit Cloud

## Context

The web app (`cycling_project/web/app.py`) is a cycling race prediction tool that scrapes start lists from FirstCycling, matches riders against a historical database, and generates predictions using LightGBM models. The main deployment challenge is the **3.1 GB SQLite database** — too large for Git or Streamlit Cloud's 1 GB RAM limit.

## Strategy: Turso (hosted SQLite-compatible database)

Use **Turso** (free tier: 5 GB storage, 500M reads+writes/month) to host a slim export of only the tables the web app queries. This avoids downloading a large file on every cold start and keeps memory usage low.

---

## Step 1: Create slim database export script

Write a script that extracts the 7 tables the app queries into a new SQLite file:

| Table | Used by |
|-------|---------|
| `riders` | `match_riders_to_db`, `get_cached_results`, result scraping |
| `rider_competition_snapshots` | `get_latest_rider_snapshots` |
| `competition_field_features` | `get_reference_race_profile`, `search_historical_races`, `get_selected_race_details` |
| `competitions` | Joins throughout |
| `races` | `get_race_name`, joins throughout |
| `race_features_50` | `get_race_finishing_characteristics`, `get_selected_race_details` |
| `rider_results` | `_get_results_from_rider_results` (checked before scraping) |

The app also creates 2 cache tables (`cached_start_lists`, `cached_race_results`) via `_ensure_cache_tables` at runtime — these don't need exporting.

**File:** `scripts/export_slim_db.py`

## Step 2: Set up Turso and import data

1. Create Turso account + database via CLI
2. Import the slim SQLite export
3. Save the database URL and auth token for secrets

## Step 3: Add database connection abstraction

**File:** `cycling_project/prediction_tools/future_race_loader.py`

Add a `get_connection()` factory function that checks for Turso credentials (via `st.secrets` or env vars). Falls back to local SQLite for development. Preserves the `db_path` parameter for non-web callers (e.g. `update_pipeline.py`):

```python
def get_connection(db_path: str = None):
    if db_path:  # Explicit path = local SQLite (for update_pipeline, etc.)
        return sqlite3.connect(db_path)
    try:
        import streamlit as st
        url = st.secrets["turso"]["database_url"]
        token = st.secrets["turso"]["auth_token"]
    except (ImportError, KeyError):
        url = os.environ.get("TURSO_DATABASE_URL")
        token = os.environ.get("TURSO_AUTH_TOKEN")

    if url and token:
        import libsql_experimental as libsql
        return libsql.connect(url, auth_token=token)
    return sqlite3.connect(str(_DEFAULT_DB))
```

Replace all **16 `sqlite3.connect()` call sites** across these functions:

| Function | Access | Uses `pd.read_sql_query`? |
|----------|--------|---------------------------|
| `_ensure_cache_tables` | WRITE (CREATE TABLE) | No |
| `get_cached_start_list` | READ | No |
| `save_start_list_to_cache` | WRITE (INSERT OR REPLACE) | No |
| `get_race_name` | READ | No |
| `match_riders_to_db` | READ | No |
| `get_latest_rider_snapshots` | READ | Yes |
| `get_reference_race_profile` | READ | No |
| `search_historical_races` | READ | Yes |
| `get_race_finishing_characteristics` | READ | No |
| `get_selected_race_details` | READ | Yes |
| `get_cached_results` | READ | Yes |
| `save_results_to_cache` | WRITE (INSERT OR REPLACE) | No |
| `_get_results_from_rider_results` | READ | Yes |

**Note:** `pd.read_sql_query()` may not work with `libsql` connections (5 call sites). If not, use `conn.execute()` + manual DataFrame construction:

```python
cursor = conn.execute(query, params)
columns = [desc[0] for desc in cursor.description]
df = pd.DataFrame(cursor.fetchall(), columns=columns)
```

**Note:** 3 functions write to the DB (cache operations). Turso supports writes, but `commit()` and `INSERT OR REPLACE` need testing with libsql. Fallback: use a separate local SQLite for cache tables.

## Step 4: Guard `logging_config.py` against read-only filesystem

**File:** `cycling_project/webscrape_tools/logging_config.py`

Two fixes needed — both the module-level `mkdir` (lines 11-12) and the `FileHandler` in `get_logger()` (line 51) will fail on Streamlit Cloud's read-only filesystem:

```python
# Module level
try:
    if not LOG_DIR.exists():
        LOG_DIR.mkdir(parents=True, exist_ok=True)
    _FILE_LOGGING_AVAILABLE = True
except OSError:
    _FILE_LOGGING_AVAILABLE = False

# In get_logger(), conditionally add file handler:
if _FILE_LOGGING_AVAILABLE:
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(DEFAULT_LEVEL)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    logger.addHandler(file_handler)
```

This matters because 5 webscrape modules imported transitively by `future_race_loader.py` all use `get_logger` from this file: `scrape_client`, `get_startlist`, `get_race_results`, `create_race_data`, `start_list_parse_tools`.

## Step 5: Add `libsql-experimental` to dependencies

**File:** `pyproject.toml`

Add `libsql-experimental>=0.0.34` to the dependencies list. The project already uses `pyproject.toml` with `uv` — no need to create a separate `requirements.txt` (Streamlit Cloud supports `pyproject.toml`).

**Python version note:** `pyproject.toml` currently requires `>=3.13`. Verify Streamlit Cloud supports this. If not, relax to `>=3.11` (codebase is compatible).

## Step 6: Create `packages.txt` for system dependencies

**File:** `packages.txt` (repo root)

```
libgomp1
```

LightGBM needs this on Debian-based systems.

## Step 7: Create `.streamlit/config.toml`

**File:** `.streamlit/config.toml`

Basic theme configuration for the app.

## Step 8: Deploy to Streamlit Cloud

1. Commit and push to GitHub
2. Connect repo at share.streamlit.io
3. Set main file path: `cycling_project/web/app.py`
4. Verify Python version compatibility (3.13)
5. Add Turso secrets via the Streamlit Cloud secrets UI
6. Deploy and test the full flow

---

## Key Files to Modify

| File | Change |
|------|--------|
| `cycling_project/prediction_tools/future_race_loader.py` | Add `get_connection()`, replace 16 `sqlite3.connect()` calls |
| `cycling_project/webscrape_tools/logging_config.py` | Guard `mkdir` and `FileHandler` against read-only filesystem |
| `pyproject.toml` | Add `libsql-experimental` dependency |

## New Files

| File | Purpose |
|------|---------|
| `scripts/export_slim_db.py` | Export 7 tables to slim SQLite file |
| `packages.txt` | System dependencies (libgomp1) |
| `.streamlit/config.toml` | Streamlit theme config |

## Already Complete

- `.gitignore` lines 100-101: `*.pkl` with `!models/production/*.pkl` exception
- `.gitignore` line 112: `.streamlit/secrets.toml` excluded

## Risks

| Risk | Mitigation |
|------|------------|
| `pd.read_sql_query()` incompatible with libsql | Test early; 5 call sites need fallback to manual DataFrame construction |
| Cache write operations fail on Turso | Test `CREATE TABLE IF NOT EXISTS`, `INSERT OR REPLACE`, `commit()` with libsql; fallback: separate local SQLite for caches |
| `cloudscraper` on Streamlit Cloud | May fail with aggressive Cloudflare; fallback: plain `httpx` |
| Python 3.13 unsupported on Streamlit Cloud | Relax to `>=3.11` in `pyproject.toml` |
| Cold start latency from eager `__init__.py` imports | Optional: convert to lazy imports if measured as a problem |

## Verification

1. Run the slim DB export script and verify all 7 table row counts match the source
2. Import to Turso and verify with `turso db shell`
3. Test `libsql-experimental` locally: `get_connection()`, `pd.read_sql_query()` compatibility, write operations
4. Run locally with Turso credentials in `.streamlit/secrets.toml`: `uv run streamlit run cycling_project/web/app.py`
5. After deploying: test the full flow — scrape start list, search reference races, run predictions, compare with actuals
