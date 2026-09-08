"""Release bundle, inference slice and bootstrap (NIGHTLY_AGENT_WORKFLOW §2.10)."""

import datetime as dt
import json
import os
import sqlite3
import subprocess
import zipfile
from pathlib import Path

import pytest

from cycling_project import db_path as db_path_mod
from cycling_project.nightly import bootstrap as bootstrap_mod
from cycling_project.nightly.bootstrap import BootstrapError, bootstrap
from cycling_project.nightly.export_slice import export_slice
from cycling_project.nightly.release_store import FakeStore
from cycling_project.nightly.weekly_release import (
    build_bundle,
    current_campaigns,
    sha256_file,
    upload_bundle,
    verify_bundle,
)
from cycling_project.prediction_tools.production_release import (
    COMPONENT_SPECS,
    tracked_artifact_paths,
    write_release_manifest,
)

TODAY = dt.date(2026, 9, 5)


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

def _make_full_db(path: Path) -> None:
    """A miniature cycling_races.db with the tables/indexes/views the slice copies."""
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE riders (id INTEGER PRIMARY KEY AUTOINCREMENT, fc_rider_id TEXT UNIQUE NOT NULL,
                             name TEXT NOT NULL, birth_year INTEGER);
        CREATE TABLE teams (id INTEGER PRIMARY KEY AUTOINCREMENT, fc_team_id TEXT UNIQUE NOT NULL, name TEXT);
        CREATE TABLE races (id INTEGER PRIMARY KEY AUTOINCREMENT, fc_race_id TEXT NOT NULL, name TEXT NOT NULL,
                            year INTEGER NOT NULL, date DATE, category TEXT NOT NULL,
                            is_stage_race BOOLEAN NOT NULL);
        CREATE TABLE competitions (id INTEGER PRIMARY KEY AUTOINCREMENT, race_id INTEGER NOT NULL,
                                   name TEXT NOT NULL, stage_number INTEGER, competition_type TEXT NOT NULL,
                                   date DATE, FOREIGN KEY (race_id) REFERENCES races(id));
        CREATE TABLE rider_results (id INTEGER PRIMARY KEY AUTOINCREMENT, competition_id INTEGER NOT NULL,
                                    rider_id INTEGER NOT NULL, place INTEGER, place_bucket INTEGER,
                                    percentile REAL, time_gap REAL, team_id INTEGER, rider_age INTEGER,
                                    bib_number TEXT, UNIQUE(competition_id, rider_id));
        CREATE INDEX idx_results_rider_competition ON rider_results(rider_id, competition_id);
        CREATE TABLE rider_competition_snapshots (rider_id INTEGER NOT NULL, competition_id INTEGER NOT NULL,
                                                  best_profile TEXT, PRIMARY KEY (rider_id, competition_id));
        CREATE TABLE rider_race_state (rider_id INTEGER NOT NULL, competition_id INTEGER NOT NULL,
                                       gc_rank_current REAL, PRIMARY KEY (rider_id, competition_id));
        CREATE TABLE competition_field_features (competition_id INTEGER PRIMARY KEY, field_size INTEGER);
        CREATE TABLE race_feature_gradients (competition_id INTEGER PRIMARY KEY, slope REAL);
        CREATE TABLE race_features_100 (competition_id INTEGER PRIMARY KEY, x REAL);
        CREATE TABLE race_cluster_v1_scores (competition_id INTEGER, fold_label TEXT, variant TEXT,
                                             PRIMARY KEY (competition_id, fold_label, variant));
        CREATE TABLE race_history_thresholds (threshold_name TEXT PRIMARY KEY, percentile REAL);
        CREATE TABLE rider_team_history (id INTEGER PRIMARY KEY AUTOINCREMENT, rider_id INTEGER, team_id INTEGER,
                                         year INTEGER);
        CREATE TABLE cached_start_lists (id INTEGER PRIMARY KEY AUTOINCREMENT, fc_race_id TEXT NOT NULL,
                                         year INTEGER NOT NULL, rider_fc_id TEXT NOT NULL, rider_name TEXT,
                                         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                         UNIQUE(fc_race_id, year, rider_fc_id));
        CREATE TABLE cached_race_results (id INTEGER PRIMARY KEY AUTOINCREMENT, fc_race_id TEXT NOT NULL,
                                          year INTEGER NOT NULL, stage_id TEXT, rider_fc_id TEXT, place INTEGER,
                                          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE prediction_log (id INTEGER PRIMARY KEY AUTOINCREMENT, predicted_at TIMESTAMP,
                                     fc_race_id TEXT NOT NULL, rider_id INTEGER NOT NULL, prob_win REAL);
        CREATE INDEX idx_prediction_log_rider ON prediction_log(rider_id);
        CREATE TABLE rider_correlations_blob (rider_id INTEGER PRIMARY KEY, blob BLOB);
        CREATE VIEW v_race_results AS SELECT r.name AS race_name, rr.place FROM rider_results rr
            JOIN competitions c ON rr.competition_id = c.id JOIN races r ON c.race_id = r.id;
        CREATE VIEW v_rider_stats AS SELECT rid.id AS rider_id, COUNT(*) AS n FROM riders rid
            JOIN rider_results rr ON rid.id = rr.rider_id GROUP BY rid.id;
        """
    )
    # riders 1..4; rider 1 + 2 on the horizon startlist, rider 3 active last year, rider 4 stale
    conn.executemany("INSERT INTO riders(id, fc_rider_id, name, birth_year) VALUES (?,?,?,?)", [
        (1, "f1", "Startlist One", 1995), (2, "f2", "Startlist Two", 1996),
        (3, "f3", "Active Three", 1990), (4, "f4", "Stale Four", 1985),
    ])
    conn.execute("INSERT INTO teams(id, fc_team_id, name) VALUES (1, 't1', 'Team')")
    # races: horizon race 23/2026 (stage race in progress), its 2025 edition, a reference one-day 2024,
    # an old 2019 race
    conn.executemany("INSERT INTO races(id, fc_race_id, name, year, date, category, is_stage_race) VALUES (?,?,?,?,?,?,?)", [
        (10, "23", "Vuelta", 2026, "2026-08-22", "wt", 1),
        (11, "23", "Vuelta", 2025, "2025-08-23", "wt", 1),
        (12, "11", "Liege", 2024, "2024-04-21", "wt", 0),
        (13, "99", "Old", 2019, "2019-05-01", "d1", 0),
    ])
    conn.executemany("INSERT INTO competitions(id, race_id, name, stage_number, competition_type, date) VALUES (?,?,?,?,?,?)", [
        (100, 10, "Stage 1", 1, "stage", "2026-08-22"),
        (101, 11, "Stage 1", 1, "stage", "2025-08-23"),
        (102, 12, "Liege", None, "one_day", "2024-04-21"),
        (103, 13, "Old", None, "one_day", "2019-05-01"),
        (104, 13, "Old GC", None, "gc", "2019-05-01"),
    ])
    conn.executemany("INSERT INTO rider_results(competition_id, rider_id, place, place_bucket) VALUES (?,?,?,?)", [
        (100, 1, 1, 0), (100, 2, 2, 1),      # horizon race, startlist riders
        (103, 1, 5, 3),                      # old race, startlist rider (kept via rider)
        (103, 3, 6, 3), (101, 3, 1, 0),      # rider 3 active in 2025
        (103, 4, 9, 4),                      # stale rider, old race only -> dropped
        (102, 4, 2, 1),                      # stale rider at a REFERENCE comp -> kept via comp
    ])
    conn.executemany("INSERT INTO rider_competition_snapshots VALUES (?,?,?)", [
        (1, 100, "sprint"), (1, 103, "climber"), (3, 101, "hilly"), (4, 102, "hilly"), (4, 103, "hilly"),
    ])
    conn.executemany("INSERT INTO rider_race_state VALUES (?,?,?)", [(1, 100, 1.0), (3, 101, 2.0)])
    conn.executemany("INSERT INTO competition_field_features VALUES (?,?)", [(100, 150), (102, 170)])
    conn.executemany("INSERT INTO race_feature_gradients VALUES (?,?)", [(100, 0.1), (103, 0.2)])
    conn.executemany("INSERT INTO race_features_100 VALUES (?,?)", [(100, 1.0)])
    conn.execute("INSERT INTO race_history_thresholds VALUES ('p90', 0.9)")
    conn.executemany("INSERT INTO cached_start_lists(fc_race_id, year, rider_fc_id, rider_name, created_at) VALUES (?,?,?,?,?)", [
        ("23", 2026, "f1", "Startlist One", "2026-08-22 02:30:00"),
        ("23", 2026, "f2", "Startlist Two", "2026-08-22 02:30:00"),
        ("8", 2026, "f4", "Stale Four", "2026-04-10 02:30:00"),   # old cache, outside horizon
    ])
    conn.executemany("INSERT INTO cached_race_results(fc_race_id, year, stage_id, rider_fc_id, place) VALUES (?,?,?,?,?)", [
        ("23", 2026, "1", "f1", 1), ("8", 2026, "1", "f4", 1),
    ])
    conn.execute("INSERT INTO prediction_log(predicted_at, fc_race_id, rider_id, prob_win) VALUES ('2026-09-01', '23', 1, 0.3)")
    conn.execute("INSERT INTO rider_correlations_blob VALUES (1, x'00')")
    conn.commit()
    conn.close()


def _make_perf_eval(root: Path) -> Path:
    perf = root / "performance_eval"
    unit = perf / "vuelta-2026" / "predictions" / "stage_15"
    unit.mkdir(parents=True)
    unit.joinpath("scenarios.json").write_text(json.dumps({
        "fc_race_id": 23, "year": 2026, "date": "2026-09-06", "stage": 15,
        "scenarios": {"a": {"label": "A", "tag": "a", "refs": [102]}},
    }))
    (perf / "vuelta-2026" / "odds").mkdir()
    (perf / "vuelta-2026" / "odds" / "markets.json").write_text("{}")
    (perf / "vuelta-2026" / "DAILY_RUNBOOK.md").write_text("# runbook\n")
    old = perf / "tour-de-france-2026" / "predictions" / "gc"
    old.mkdir(parents=True)
    old.joinpath("scenarios.json").write_text(json.dumps({
        "fc_race_id": 17, "year": 2026, "date": "2026-07-26", "target": "gc",
        "scenarios": {"g": {"label": "G", "tag": "g", "refs": [104]}},
    }))
    (perf / "tour-de-france-2026" / "campaign.json").write_text(json.dumps({"slug": "tour-de-france-2026"}))
    # shared tooling that lives in the (finished) Tour dir — the driver runs these every settle
    (perf / "tour-de-france-2026" / "seed_state_cache.py").write_text("# seed\n")
    (perf / "tour-de-france-2026" / "capture_odds.py").write_text("# odds\n")
    (perf / "tour-de-france-2026" / "build_review_dataset.py").write_text("# not shared\n")
    (perf / "DAILY_RUNBOOK.md").write_text("# generic runbook\n")         # top-level documents ship too
    (perf / "LESSONS.md").write_text("# lessons\n")
    return perf


def _schema(db: Path) -> set:
    with sqlite3.connect(db) as conn:
        return set(conn.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY name").fetchall())


# ---------------------------------------------------------------------------
# CYCLING_DB_PATH
# ---------------------------------------------------------------------------

def test_cycling_db_path_env_overrides_repo_default(monkeypatch, tmp_path):
    monkeypatch.delenv(db_path_mod.ENV_VAR, raising=False)
    assert db_path_mod.default_db_path() == db_path_mod.repo_default_db_path()
    monkeypatch.setenv(db_path_mod.ENV_VAR, str(tmp_path / "slice.db"))
    assert db_path_mod.default_db_path() == tmp_path / "slice.db"
    assert db_path_mod.resolve_db_path("/explicit.db") == "/explicit.db"
    monkeypatch.setenv(db_path_mod.ENV_VAR, "")
    assert db_path_mod.default_db_path() == db_path_mod.repo_default_db_path()


# ---------------------------------------------------------------------------
# export_slice
# ---------------------------------------------------------------------------

def test_slice_schema_equals_full_db_and_filters_rows(tmp_path):
    full = tmp_path / "full.db"
    _make_full_db(full)
    perf = _make_perf_eval(tmp_path)
    out = tmp_path / "inference_slice.db"

    stats = export_slice(out, horizon_days=14, full_db=full, today=TODAY, perf_eval=perf,
                         active_days=400, quiet=True)

    assert _schema(out) == _schema(full)                 # tables, indexes, views, sqlite_sequence
    assert stats["integrity"] == "ok"
    assert ("23", 2026) in {tuple(k) for k in stats["race_keys"]}
    with sqlite3.connect(out) as conn:
        q = lambda sql: conn.execute(sql).fetchall()
        assert q("SELECT COUNT(*) FROM prediction_log") == [(0,)]           # empty, schema kept
        assert q("SELECT COUNT(*) FROM rider_correlations_blob") == [(0,)]
        assert q("SELECT COUNT(*) FROM riders") == [(4,)]                   # full
        assert q("SELECT COUNT(*) FROM competitions") == [(5,)]
        kept = {tuple(r) for r in q("SELECT competition_id, rider_id FROM rider_results")}
        assert (100, 1) in kept and (103, 1) in kept        # startlist rider: whole history
        assert (101, 3) in kept and (103, 3) in kept        # active rider: whole history
        assert (102, 4) in kept                             # reference comp: every rider
        assert (103, 4) not in kept                         # stale rider elsewhere: dropped
        snaps = {tuple(r) for r in q("SELECT rider_id, competition_id FROM rider_competition_snapshots")}
        assert (1, 103) in snaps                            # latest = MAX(competition_id)
        assert (3, 101) in snaps
        assert (4, 102) in snaps and (4, 103) not in snaps  # reference-comp row kept, others not
        assert q("SELECT DISTINCT fc_race_id FROM cached_start_lists") == [("23",)]
        assert q("SELECT DISTINCT fc_race_id FROM cached_race_results") == [("23",)]
        assert q("SELECT competition_id FROM rider_race_state") == [(100,)]   # in-progress edition only
        assert q("SELECT seq FROM sqlite_sequence WHERE name='prediction_log'") == [(1,)]
        assert q("SELECT COUNT(*) FROM v_rider_stats")[0][0] >= 1           # views work
        # the serving lookup gives the same "latest snapshot" on both databases
        latest = "SELECT rider_id, MAX(competition_id) FROM rider_competition_snapshots WHERE rider_id IN (1,3) GROUP BY rider_id"
        assert q(latest) == sqlite3.connect(full).execute(latest).fetchall()


def test_slice_startlist_only_scope_drops_active_riders(tmp_path):
    full = tmp_path / "full.db"
    _make_full_db(full)
    perf = _make_perf_eval(tmp_path)
    out = tmp_path / "slice0.db"
    export_slice(out, horizon_days=14, full_db=full, today=TODAY, perf_eval=perf, active_days=0, quiet=True)
    with sqlite3.connect(out) as conn:
        kept = {tuple(r) for r in conn.execute("SELECT competition_id, rider_id FROM rider_results")}
    assert (101, 3) in kept          # prior edition of a horizon race: every rider
    assert (103, 3) not in kept      # rider 3 is not on a startlist -> no personal history
    assert (102, 4) in kept and (103, 4) not in kept


@pytest.mark.slow
@pytest.mark.skipif(not os.environ.get("NIGHTLY_SLOW_TESTS"), reason="set NIGHTLY_SLOW_TESTS=1")
def test_slice_schema_equals_real_database(tmp_path):
    full = db_path_mod.repo_default_db_path()
    if not full.is_file():
        pytest.skip("repo database not present")
    out = tmp_path / "inference_slice.db"
    export_slice(out, horizon_days=14, full_db=full, active_days=0, quiet=True)
    assert _schema(out) == _schema(full)
    assert out.stat().st_size < 500 * 1024 * 1024


# ---------------------------------------------------------------------------
# weekly_release + bootstrap
# ---------------------------------------------------------------------------

def _seed_models(model_dir: Path) -> None:
    model_dir.mkdir(parents=True)
    flags = {spec.metadata_flag: True for spec in COMPONENT_SPECS if spec.metadata_flag is not None}
    (model_dir / "metadata.json").write_text(json.dumps({"saved_at": "2026-09-05", **flags}))
    for filename in tracked_artifact_paths():
        artifact = model_dir / filename
        if artifact.exists():
            continue
        if filename.endswith(".json"):
            artifact.write_text(json.dumps({"payload": filename}))
        else:
            artifact.write_bytes(f"payload:{filename}".encode())
    write_release_manifest(model_dir)


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args], cwd=root, text=True).strip()


@pytest.fixture
def fake_project(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "cycling_project").mkdir()
    (root / "cycling_project" / "__init__.py").write_text("")
    (root / "pyproject.toml").write_text('[project]\nname = "fake"\nversion = "0"\n')
    _seed_models(root / "models" / "production")
    _make_perf_eval(root)
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "release commit")
    slice_db = tmp_path / "slice_src.db"
    _make_full_db(slice_db)
    return root, slice_db


def _bundle(fake_project, tmp_path, tag="data-2026-09-05"):
    root, slice_db = fake_project
    out = tmp_path / "bundle" / tag
    manifest = build_bundle(
        tag, out, slice_path=slice_db, today=TODAY, project_root=root,
        model_dir=root / "models" / "production", perf_eval=root / "performance_eval",
    )
    return root, out, manifest


def test_manifest_round_trip_and_bundle_contents(fake_project, tmp_path):
    root, out, manifest = _bundle(fake_project, tmp_path)

    reloaded = json.loads((out / "manifest.json").read_text())
    assert reloaded == json.loads(json.dumps(manifest))
    assert verify_bundle(out) == []
    files = manifest["files"]
    assert manifest["git"]["sha"] == _git(root, "rev-parse", "HEAD")
    assert manifest["git"]["code_zip"] in files
    assert "inference_slice.db" in files and files["inference_slice.db"]["sha256"] == sha256_file(out / "inference_slice.db")
    assert all(f"models/production/{p}" in files for p in manifest["model_contract"]["files"])
    assert "performance_eval/vuelta-2026/predictions/stage_15/scenarios.json" in files
    assert "performance_eval/vuelta-2026/odds/markets.json" in files
    assert "performance_eval/vuelta-2026/DAILY_RUNBOOK.md" in files
    assert "performance_eval/tour-de-france-2026/campaign.json" in files      # registry entries always
    assert "performance_eval/tour-de-france-2026/predictions/gc/scenarios.json" not in files  # finished
    assert "performance_eval/tour-de-france-2026/seed_state_cache.py" in files   # shared tooling ships regardless
    assert "performance_eval/tour-de-france-2026/capture_odds.py" in files
    assert "performance_eval/tour-de-france-2026/build_review_dataset.py" not in files
    assert "performance_eval/DAILY_RUNBOOK.md" in files and "performance_eval/LESSONS.md" in files
    assert manifest["campaigns"] == ["vuelta-2026"]
    assert manifest["db_snapshot_date"] == "2026-08-22"
    assert manifest["total_bytes"] == sum(m["size"] for m in files.values())
    with zipfile.ZipFile(out / manifest["git"]["code_zip"]) as zf:
        assert "pyproject.toml" in zf.namelist()


def test_current_campaigns_uses_latest_known_date(tmp_path):
    perf = _make_perf_eval(tmp_path)
    assert [c.name for c in current_campaigns(perf, today=TODAY)] == ["vuelta-2026"]
    assert [c.name for c in current_campaigns(perf, today=dt.date(2026, 7, 27))] == ["tour-de-france-2026", "vuelta-2026"]
    assert current_campaigns(perf, today=dt.date(2026, 12, 1)) == []


def test_bootstrap_hydrates_from_fake_store_and_fails_closed(fake_project, tmp_path, monkeypatch):
    root, out, manifest = _bundle(fake_project, tmp_path)
    store = FakeStore(tmp_path / "store")
    upload_bundle(store, out, manifest)
    monkeypatch.delenv(db_path_mod.ENV_VAR, raising=False)

    # not approved yet -> refused
    with pytest.raises(BootstrapError, match="approved"):
        bootstrap(tmp_path / "dest0", store, skip_uv_sync=True)

    store.approve("data-2026-09-05", by="human")
    store.put_artifact("run-1/vuelta-2026/results/stage_15/results.csv", b"place,name\n1,X\n",
                       created_at="2099-01-01T00:00:00+00:00")
    dest = tmp_path / "dest"
    summary = bootstrap(dest, store, skip_uv_sync=True)

    assert summary["release_tag"] == "data-2026-09-05"
    assert (dest / "pyproject.toml").is_file()                              # unzipped code
    assert (dest / "cycling_project" / "__init__.py").is_file()
    assert (dest / "models" / "production" / "production_release_manifest.json").is_file()
    assert (dest / "inference_slice.db").is_file()
    assert (dest / "performance_eval" / "vuelta-2026" / "predictions" / "stage_15" / "scenarios.json").is_file()
    assert (dest / "performance_eval" / "vuelta-2026" / "results" / "stage_15" / "results.csv").read_text().startswith("place")
    assert summary["artifacts_overlaid"] == ["run-1/vuelta-2026/results/stage_15/results.csv"]
    assert os.environ[db_path_mod.ENV_VAR] == str(dest / "inference_slice.db")
    assert f"{db_path_mod.ENV_VAR}={dest / 'inference_slice.db'}" in (dest / ".env").read_text()
    assert (dest / bootstrap_mod.ENV_SCRIPT).read_text().startswith("export CYCLING_DB_PATH=")

    # second run: everything already present, nothing downloaded
    again = bootstrap(dest, store, skip_uv_sync=True)
    assert again["files_downloaded"] == 0 and again["files_present"] == len(manifest["files"])

    # tamper with a model artifact in the store -> fail closed on a fresh dest
    victim = store.releases_dir / "data-2026-09-05" / "models" / "production" / "dnf_model.txt"
    victim.write_bytes(b"tampered")
    with pytest.raises(BootstrapError, match="sha256 mismatch"):
        bootstrap(tmp_path / "dest2", store, skip_uv_sync=True)

    # a locally edited model file is healed by re-download (the store copy is genuine again)
    victim.write_bytes((root / "models" / "production" / "dnf_model.txt").read_bytes())
    (dest / "models" / "production" / "bucket_model.txt").write_bytes(b"edited")
    healed = bootstrap(dest, store, skip_uv_sync=True)
    assert healed["files_downloaded"] == 1
    assert (dest / "models" / "production" / "bucket_model.txt").read_bytes() == b"payload:bucket_model.txt"

    # a manifest whose contract disagrees with the artifacts it ships -> fail closed
    manifest_path = store.releases_dir / "data-2026-09-05" / "manifest.json"
    forged = json.loads(manifest_path.read_text())
    forged["model_contract"]["files"]["bucket_model.txt"] = "0" * 64
    manifest_path.write_text(json.dumps(forged))
    with pytest.raises(BootstrapError, match="model contract hash mismatch"):
        bootstrap(tmp_path / "dest3", store, skip_uv_sync=True)


def test_fake_store_release_rows_and_artifact_listing(tmp_path):
    store = FakeStore(tmp_path / "store")
    store.insert_release({"tag": "data-2026-08-29", "manifest": {}})
    store.insert_release({"tag": "data-2026-09-05", "manifest": {}})
    assert store.newest_approved_release() is None
    store.approve("data-2026-08-29")
    assert store.newest_approved_release()["tag"] == "data-2026-08-29"
    with pytest.raises(ValueError):
        store.insert_release({"tag": "data-2026-09-05"})
    store.put_artifact("run-9/vuelta-2026/x.json", b"{}")
    assert [o["key"] for o in store.list_artifacts_since("data-2026-08-29")] == ["run-9/vuelta-2026/x.json"]
    with pytest.raises(ValueError):
        store.put_artifact("run-9/vuelta-2026/x.json", b"{}")      # insert-only
