# Deploy Cycling Predictor to Streamlit Cloud

## Context

The web app (`cycling_project/web/app.py`) is a cycling race prediction tool that scrapes start lists from FirstCycling, matches riders against a historical database, and generates predictions using LightGBM models. The main deployment challenge is the **2.9 GB SQLite database** — too large for Git or Streamlit Cloud's 1 GB RAM limit.

## Strategy: Turso (hosted SQLite-compatible database)

Use **Turso** (free tier: 5 GB storage, 500M reads/month) to host a slim export of only the 5 tables the web app actually queries. This avoids downloading a large file on every cold start and keeps memory usage low.

---

## Step 1: Create slim database export script

Write a script that extracts only the 5 tables the app queries into a new SQLite file (~150-250 MB estimated):
- `riders` — rider lookup by `fc_rider_id`
- `rider_competition_snapshots` — latest rider stats
- `competition_field_features` — race profiles
- `competitions` — race metadata
- `races` — parent race info

**File:** `scripts/export_slim_db.py`

## Step 2: Set up Turso and import data

1. Create Turso account + database via CLI
2. Import the slim SQLite export
3. Save the database URL and auth token for secrets

## Step 3: Add database connection abstraction

**File:** `cycling_project/prediction_tools/future_race_loader.py`

Add a `get_connection()` factory function that checks for Turso credentials (via `st.secrets` or env vars). Falls back to local SQLite for development:

```python
def get_connection():
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

Update the 4 DB-querying functions (`match_riders_to_db`, `get_latest_rider_snapshots`, `get_reference_race_profile`, `search_historical_races`) to use `get_connection()` instead of `sqlite3.connect(db_path)`.

**Note:** `pd.read_sql_query()` may not work with `libsql` connections. If not, use `conn.execute()` + manual DataFrame construction.

## Step 4: Fix `.gitignore` for model `.pkl` files

**File:** `.gitignore`

The `*.pkl` rule (line 100) blocks the model feature engineer files. Add an exception:

```
!models/production/*.pkl
```

## Step 5: Guard `logging_config.py` against read-only filesystem

**File:** `cycling_project/webscrape_tools/logging_config.py`

Lines 11-12 create a log directory at import time, and the `FileHandler` will fail on Streamlit Cloud's read-only filesystem. Wrap in try/except:

```python
try:
    if not LOG_DIR.exists():
        LOG_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    LOG_DIR = None  # Signal that file logging is unavailable
```

And in `get_logger()`, skip the file handler if `LOG_DIR is None`.

## Step 6: Create `requirements.txt`

**File:** `requirements.txt` (repo root)

```
streamlit>=1.30.0
pandas>=2.1.0
numpy>=1.26.0
lightgbm>=4.1.0
scikit-learn>=1.3.0
scipy>=1.11.0
beautifulsoup4>=4.14.3
cloudscraper>=1.2.71
httpx>=0.28.1
python-dotenv>=1.2.1
libsql-experimental>=0.0.34
```

## Step 7: Create `packages.txt` for system dependencies

**File:** `packages.txt` (repo root)

```
libgomp1
```

LightGBM needs this on Debian-based systems.

## Step 8: Create `.streamlit/config.toml`

**File:** `.streamlit/config.toml`

Basic theme configuration for the app.

## Step 9: Add `.streamlit/secrets.toml` to `.gitignore`

Ensure Turso credentials are never committed.

## Step 10: Deploy to Streamlit Cloud

1. Commit and push to GitHub
2. Connect repo at share.streamlit.io
3. Set main file path: `cycling_project/web/app.py`
4. Add Turso secrets via the Streamlit Cloud secrets UI
5. Deploy and test the full flow

---

## Key Files to Modify

| File | Change |
|------|--------|
| `cycling_project/prediction_tools/future_race_loader.py` | Add `get_connection()`, update 4 DB functions |
| `cycling_project/webscrape_tools/logging_config.py` | Guard against read-only filesystem |
| `.gitignore` | Allow `models/production/*.pkl` |

## New Files

| File | Purpose |
|------|---------|
| `scripts/export_slim_db.py` | Export 5 tables to slim SQLite file |
| `requirements.txt` | Python dependencies for Streamlit Cloud |
| `packages.txt` | System dependencies (libgomp1) |
| `.streamlit/config.toml` | Streamlit theme config |

## Risks

- **`cloudscraper` on Streamlit Cloud** — may fail if FirstCycling has aggressive Cloudflare. Fallback: use plain `httpx`.
- **`libsql` + pandas compatibility** — `pd.read_sql_query()` may not accept `libsql` connections. Fallback: manual DataFrame construction from cursor results.
- **`prediction_tools/__init__.py` eager imports** — imports many modules not needed by the web app. Should be safe (no module-level DB instantiation found), but if issues arise, switch to lazy imports.

## Verification

1. Run the slim DB export script and verify table counts match the source
2. Test locally with Turso credentials in `.streamlit/secrets.toml`
3. Run `streamlit run cycling_project/web/app.py` locally with Turso connection
4. After deploying: test scraping a FirstCycling URL, searching reference races, and generating predictions
