"""Defects surfaced by the first cloud run (2026-09-08, sesn_01EXAMPLE8DBE29AF1DE0A86).

Every operator task was rejected (urgency outside the CHECK), two shared scripts were missing from
the bundle, the driver's JSON stdout carried log lines, and there was no command to file a triage
report.  These tests pin the fixes.
"""
import json
import logging
import re
from pathlib import Path

import pytest

from cycling_project.nightly import crosswalk, driver, weekly_release

ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "supabase" / "migrations" / "0001_control_plane.sql"


def _schema_urgencies() -> set:
    sql = MIGRATION.read_text()
    m = re.search(r"urgency\s+text.*?check \(urgency in \(([^)]*)\)\)", sql, re.S)
    assert m, "operator_tasks.urgency CHECK not found in 0001"
    return set(re.findall(r"'([a-z_]+)'", m.group(1)))


def test_urgency_vocabulary_matches_the_schema():
    assert set(crosswalk.URGENCIES) == _schema_urgencies()


def test_every_waiting_kind_maps_to_a_schema_urgency():
    src = (ROOT / "cycling_project" / "nightly" / "driver.py").read_text()
    kinds = set(re.findall(r"WaitingForInput\(\s*\"([a-z_]+)\"", src))
    kinds |= set(re.findall(r"WaitingForInput\(\"([a-z_]+)\" if", src))
    assert kinds, "no WaitingForInput raises found"
    for kind in kinds:
        assert driver.WaitingForInput(kind, "x").urgency in crosswalk.URGENCIES, kind
    assert driver.WaitingForInput("something_new", "x").urgency == "blocks_settlement"
    assert driver.WaitingForInput("kambi_match", "x").urgency == "blocks_publication"


def test_an_unknown_urgency_is_filed_as_urgent_and_remembered():
    task = crosswalk.build_operator_task("ops_triage", "zlm-tour-2026", "s", {"a": 1}, urgency="blocks_tonight")
    assert task["urgency"] == "urgent"
    assert task["detail"]["urgency_requested"] == "blocks_tonight"
    assert task["detail"]["a"] == 1
    ok = crosswalk.build_operator_task("x", None, "s", {}, urgency="routine")
    assert ok["urgency"] == "routine" and "urgency_requested" not in ok["detail"]


def test_shared_campaign_tools_are_the_drivers_scripts_and_exist():
    scripts = {str(p.relative_to(driver.PROJECT_ROOT)) for p in driver.SCRIPTS.values()
               if str(p).startswith(str(driver.PERF_EVAL))}
    assert set(weekly_release.SHARED_CAMPAIGN_TOOLS) == scripts
    for rel in weekly_release.SHARED_CAMPAIGN_TOOLS:
        assert (ROOT / rel).is_file(), rel


def test_log_stream_env_routes_console_logging_to_stderr(monkeypatch):
    import sys
    from cycling_project.webscrape_tools import logging_config
    monkeypatch.setenv("CYCLING_LOG_STREAM", "stderr")
    lg = logging_config.get_logger("test_nightly_manual_run_fixes.stderr")
    streams = [h.stream for h in lg.handlers if type(h) is logging.StreamHandler]
    assert streams == [sys.stderr]
    monkeypatch.delenv("CYCLING_LOG_STREAM")
    lg = logging_config.get_logger("test_nightly_manual_run_fixes.stdout")
    assert [h.stream for h in lg.handlers if type(h) is logging.StreamHandler] == [sys.stdout]


def test_task_command_files_a_report_through_the_store(tmp_path, capsys):
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"diagnosis": "bundle lacks seed_state_cache.py", "confidence": 0.9}))
    code = driver.main(["task", "--store", "fake", "--store-root", str(tmp_path / "store"), "--kind", "ops_triage",
                        "--summary", "release data-2026-09-07b is missing shared tooling",
                        "--detail-file", str(report), "--urgency", "blocks_tonight"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and out["status"] == "ok"
    assert out["task"]["urgency"] == "urgent" and out["task"]["detail"]["urgency_requested"] == "blocks_tonight"
    assert out["task"]["detail"]["diagnosis"].startswith("bundle lacks")
    assert out["task"]["campaign"] is None


def test_task_command_rejects_a_non_object_detail(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("[1, 2]")
    code = driver.main(["task", "--store", "fake", "--store-root", str(tmp_path / "s"), "--kind", "k", "--summary", "s",
                        "--detail-file", str(bad)])
    assert code == driver.EXIT_FAILED
    assert json.loads(capsys.readouterr().out)["error_class"] == "task_detail"
