"""Chip ED (2026-10-02): every editorial draft lands in ``editorial_drafts`` for the owner's review.

Until this chip the coordinator saved ``editorial_draft.json`` "for upload to insert", no code
inserted it, and every draft died with the container (hosted tasks 104 and 114). The fixture is
the real Tour de Langkawi stage 5 preview draft the cloud wrote on 2026-10-01, with the facts
bundle it was written from.
"""

from __future__ import annotations

import datetime as dt
import json
import shutil
from pathlib import Path

import pytest

from cycling_project.nightly import driver as drv
from cycling_project.nightly import editorial_feedback, run_editorial
from cycling_project.nightly.store import FakeStore, StorePermissionError

pytestmark = pytest.mark.unit

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "editorial" / "langkawi_stage_05"
SLUG = "tour-de-langkawi-2026"


@pytest.fixture
def campaign(tmp_path):
    root = tmp_path / SLUG
    pred = root / "predictions" / "stage_05"
    pred.mkdir(parents=True)
    (root / "campaign.json").write_text(json.dumps({
        "slug": SLUG, "name": "Tour de Langkawi", "year": 2026, "category": "pro", "is_stage_race": True,
        "start_date": "2026-09-27", "end_date": "2026-10-04",
        "stages": [{"number": n, "date": (dt.date(2026, 9, 26) + dt.timedelta(days=n)).isoformat()}
                   for n in range(1, 9)]}))
    shutil.copy(FIXTURE / "scenarios.json", pred / "scenarios.json")
    shutil.copy(FIXTURE / "editorial_facts_stage_preview.json", pred / "editorial_facts_stage_preview.json")
    shutil.copy(FIXTURE / "editorial_draft.json", pred / "editorial_draft_stage_preview.json")
    return root


def _main(campaign, tmp_path, *argv):
    return drv.main([argv[0], "--campaign", str(campaign), "--store", "fake",
                     "--store-root", str(tmp_path / "store"), "--today", "2026-10-02", *argv[1:]])


def _rows(tmp_path, table="editorial_drafts"):
    p = tmp_path / "store" / "ledger" / f"{table}.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []


# ---------------------------------------------------------------------------
# validation, rendering, phase
# ---------------------------------------------------------------------------

def test_the_langkawi_draft_validates_lints_clean_and_renders_for_review():
    d = run_editorial.prepare_draft(FIXTURE / "editorial_draft.json", "stage_05")
    assert d["artifact"] == "stage_preview" and d["phase"] == "preview"
    assert d["lint"]["validation"] == {"ok": True, "errors": []}
    assert d["lint"]["facts_source"] == "editorial_facts_stage_preview.json"
    assert d["lint"]["checks"]["numerals"] is True and d["lint_ok"] is True
    body = d["body_md"]
    assert body.startswith("# Stage 5 runs 125.7 km from Tapah")
    # fixed order: stage read, model and market, the key, scenarios, GC
    heads = [ln for ln in body.splitlines() if ln.startswith("## ")]
    assert heads == ["## Stage read", "## Model and market", "## The key", "## Scenarios", "## General classification"]
    assert "### main_read" in body and "### alt_gc_day" in body
    assert d["record"]["claims"] and d["record_sha256"] == run_editorial.record_sha256(d["record"])
    assert len(d["record_sha256"]) == 64


def test_validation_catches_schema_and_tone_breaks():
    rec = json.loads((FIXTURE / "editorial_draft.json").read_text())
    assert run_editorial.validate_record(rec) == []
    bad = {**rec, "flags": {"tone_check": "punchy", "no_advice_language": False}}
    del bad["claims"]
    errs = run_editorial.validate_record(bad)
    assert "claims: missing" in errs
    assert any(e.startswith("flags.no_advice_language") for e in errs)
    assert any(e.startswith("flags.tone_check") for e in errs)
    assert run_editorial.validate_record({**rec, "artifact": "tweet"})[0].startswith("artifact:")
    assert run_editorial.validate_record([1, 2])[0].startswith("$: expected object")
    # a one-day race has no stage number
    one_day = {**rec, "stage": None}
    assert run_editorial.validate_record(one_day, unit="race") == []
    assert run_editorial.validate_record(one_day, unit="stage_05")


def test_phase_follows_the_artifact_and_the_table_check():
    assert run_editorial.draft_phase("stage_preview", "stage_05") == "preview"
    assert run_editorial.draft_phase("stage_retro", "stage_05") == "retro"
    assert run_editorial.draft_phase("monthly_review", "stage_05") == "retro"
    assert run_editorial.draft_phase("stage_preview", "race") == "one_day"
    assert run_editorial.draft_phase("stage_retro", "race") == "one_day"
    assert run_editorial.draft_phase(None, "stage_02", "settle") == "retro"
    assert run_editorial.draft_phase(None, "stage_02", "preview") == "preview"
    for artifact in (*run_editorial.ARTIFACTS, None):
        for unit in ("stage_01", "race", "gc"):
            assert run_editorial.draft_phase(artifact, unit) in ("preview", "retro", "gc", "one_day")


# ---------------------------------------------------------------------------
# the driver persists drafts
# ---------------------------------------------------------------------------

def test_the_editorial_command_stores_the_draft_once(campaign, tmp_path, capsys):
    assert _main(campaign, tmp_path, "editorial", "--unit", "stage_05") == 0
    out = json.loads(capsys.readouterr().out)
    res = out["editorial"]["editorial_drafts"]
    assert len(res["inserted"]) == 1 and res["duplicates"] == 0 and res["errors"] == []
    assert any(k.endswith("predictions/stage_05/editorial_draft_stage_preview.json") for k in out["editorial"]["artifacts"])
    assert any(k.endswith("editorial_facts_stage_preview.json") for k in out["editorial"]["artifacts"])
    rows = _rows(tmp_path)
    assert len(rows) == 1
    row = rows[0]
    assert row["campaign_slug"] == SLUG and row["unit"] == "stage_05" and row["phase"] == "preview"
    assert row["artifact"] == "stage_preview" and row["kind"] == "prose" and row["author"] == "agent"
    assert row["lint_ok"] is True and row["review_status"] == "pending" and not row.get("approved_by")
    assert row["record"]["sections"]["headline"].startswith("Stage 5 runs")
    assert row["run_id"] == out["run_id"]
    # a clean first draft is stored at once, as attempt 1 (chip EE)
    assert row["lint"]["attempt"] == 1 and row["lint"]["retried"] is False
    assert row["lint"]["first_attempt"]["ok"] is True
    # the coordinator may run it twice; the upload may re-run; nothing is stored twice
    assert _main(campaign, tmp_path, "editorial", "--unit", "stage_05") == 0
    again = json.loads(capsys.readouterr().out)["editorial"]["editorial_drafts"]
    assert again["inserted"] == [] and again["duplicates"] == 1
    assert _main(campaign, tmp_path, "upload", "--unit", "stage_05", "--phase", "preview") == 0
    up = json.loads(capsys.readouterr().out)["upload"]
    assert up["editorial_drafts"]["duplicates"] == 1
    assert len(_rows(tmp_path)) == 1


def test_upload_stores_a_draft_already_on_disk(campaign, tmp_path, capsys):
    """The Mac (or a draft hydrated from an artifact) has the file before upload runs."""
    assert _main(campaign, tmp_path, "upload", "--unit", "stage_05", "--phase", "preview") == 0
    up = json.loads(capsys.readouterr().out)["upload"]
    assert len(up["editorial_drafts"]["inserted"]) == 1
    assert any(k.endswith("editorial_draft_stage_preview.json") for k in up["artifacts"])
    assert len(_rows(tmp_path)) == 1


def test_a_bad_draft_is_stored_flagged_never_dropped(campaign, tmp_path, capsys):
    pred = campaign / "predictions" / "stage_05"
    rec = json.loads((FIXTURE / "editorial_draft.json").read_text())
    retro = {**rec, "artifact": "stage_retro", "flags": {"tone_check": "x", "no_advice_language": False}}
    retro["sections"] = {**rec["sections"], "stage_read": "A value bet on Jasch at 9.99."}
    (pred / "editorial_draft_stage_retro.json").write_text(json.dumps(retro))
    (pred / "editorial_draft.json").write_text("{not json")             # the pre-rev-7 name, broken
    # chip EE: the check stores the clean draft and asks for the one retry on the two bad ones
    assert _main(campaign, tmp_path, "editorial", "--unit", "stage_05") == drv.EXIT_WAITING
    first = json.loads(capsys.readouterr().out)
    assert first["kind"] == "editorial_lint_failed" and first["operator_task"] is None
    assert set(first["lint_report"]) == {"editorial_draft.json", "editorial_draft_stage_retro.json"}
    assert len(_rows(tmp_path)) == 1 and not _rows(tmp_path, "operator_tasks")
    # the retry came back unchanged: --final stores them anyway, flagged, never dropped
    assert _main(campaign, tmp_path, "editorial", "--unit", "stage_05", "--final") == 0
    res = json.loads(capsys.readouterr().out)["editorial"]["editorial_drafts"]
    assert len(res["inserted"]) == 2 and res["duplicates"] == 1
    rows = {r["lint"]["source_file"]: r for r in _rows(tmp_path)}
    good = rows["editorial_draft_stage_preview.json"]
    assert good["lint_ok"] is True
    bad = rows["editorial_draft_stage_retro.json"]
    assert bad["lint_ok"] is False and bad["phase"] == "retro" and bad["artifact"] == "stage_retro"
    assert any("no_advice_language" in e for e in bad["lint"]["validation"]["errors"])
    assert bad["lint"]["counts"]["lexicon"] >= 1               # "value bet"
    assert bad["lint"]["attempt"] == 2 and bad["lint"]["first_attempt"]["counts"]["lexicon"] >= 1
    assert good["lint"]["attempt"] == 1 and good["lint"]["retried"] is False
    broken = rows["editorial_draft.json"]
    assert broken["lint_ok"] is False and not broken.get("artifact")
    assert broken["record"]["unparseable"] is True and broken["phase"] == "preview"
    assert broken["lint"]["validation"]["errors"][0].startswith("invalid JSON")
    assert broken["body_md"].startswith("# Unparseable editorial draft")


def _placeholder_draft(pred):
    """The cloud's 2026-10-03 failure: a bundle path in double braces where a number belongs."""
    rec = json.loads((FIXTURE / "editorial_draft.json").read_text())
    rec["sections"]["stage_read"] = rec["sections"]["stage_read"] + " The stage is {{route.distance_km}} km."
    (pred / "editorial_draft_stage_preview.json").write_text(json.dumps(rec))
    return rec


def test_a_failing_first_draft_waits_for_its_one_retry(campaign, tmp_path, capsys):
    """Chip EE: the skill promised one retry; the cloud stored the first reply whatever it said."""
    pred = campaign / "predictions" / "stage_05"
    _placeholder_draft(pred)
    for _ in range(2):                                   # re-running the check on the same draft changes nothing
        assert _main(campaign, tmp_path, "editorial", "--unit", "stage_05") == drv.EXIT_WAITING
        out = json.loads(capsys.readouterr().out)
        assert out["status"] == "waiting_for_input" and out["kind"] == "editorial_lint_failed"
        assert out["operator_task"] is None and "--final" in out["next"]
        (report,) = out["lint_report"].values()
        assert set(out["lint_report"]) == {"editorial_draft_stage_preview.json"}
        assert report["placeholders"] == [{"section": "stage_read", "token": "{{route.distance_km}}"}]
        # the real 10-01 draft named riders surname first: advisory, but it rides along with the retry
        assert {"section": "stage_read", "token": "Malucelli Matteo", "use": "Matteo Malucelli"} in report["name_order"]
        assert set(report) == {"placeholders", "name_order"}
        assert _rows(tmp_path) == [] and _rows(tmp_path, "operator_tasks") == []
    side = json.loads((pred / "editorial_lint_attempt1_stage_preview.json").read_text())
    assert side["attempt"] == 1 and side["counts"]["placeholders"] == 1
    assert "{{route.distance_km}}" in side["record"]["sections"]["stage_read"]   # the first draft survives the overwrite
    # the retry comes back clean and is saved over the same file: stored as attempt 2, both results kept
    shutil.copy(FIXTURE / "editorial_draft.json", pred / "editorial_draft_stage_preview.json")
    assert _main(campaign, tmp_path, "editorial", "--unit", "stage_05", "--final") == 0
    out = json.loads(capsys.readouterr().out)
    assert any(k.endswith("editorial_lint_attempt1_stage_preview.json") for k in out["editorial"]["artifacts"])
    (row,) = _rows(tmp_path)
    assert row["lint_ok"] is True and row["lint"]["attempt"] == 2 and row["lint"]["retried"] is True
    first = row["lint"]["first_attempt"]
    assert first["ok"] is False and first["counts"]["placeholders"] == 1
    assert first["retry_report"]["placeholders"][0]["token"] == "{{route.distance_km}}"


def test_the_retry_is_stored_even_when_it_still_fails(campaign, tmp_path, capsys):
    pred = campaign / "predictions" / "stage_05"
    _placeholder_draft(pred)
    assert _main(campaign, tmp_path, "editorial", "--unit", "stage_05") == drv.EXIT_WAITING
    capsys.readouterr()
    rec = _placeholder_draft(pred)
    rec["sections"]["headline"] += " Again."                 # a different record, still failing
    (pred / "editorial_draft_stage_preview.json").write_text(json.dumps(rec))
    # without --final too: a sidecar holding a DIFFERENT record marks this as the retry
    assert _main(campaign, tmp_path, "editorial", "--unit", "stage_05") == 0
    capsys.readouterr()
    (row,) = _rows(tmp_path)
    assert row["lint_ok"] is False and row["lint"]["attempt"] == 2
    assert row["lint"]["counts"]["placeholders"] == 1 and row["lint"]["first_attempt"]["counts"]["placeholders"] == 1


def test_final_without_a_check_stores_a_failing_draft_as_the_retry(campaign, tmp_path, capsys):
    _placeholder_draft(campaign / "predictions" / "stage_05")
    assert _main(campaign, tmp_path, "editorial", "--unit", "stage_05", "--final") == 0
    capsys.readouterr()
    (row,) = _rows(tmp_path)
    assert row["lint_ok"] is False and row["lint"]["attempt"] == 2 and row["lint"]["first_attempt"] is None


def test_upload_still_stores_whatever_is_on_disk(campaign, tmp_path, capsys):
    """Upload never gates: a failing draft hydrated before upload runs is stored, flagged."""
    _placeholder_draft(campaign / "predictions" / "stage_05")
    assert _main(campaign, tmp_path, "upload", "--unit", "stage_05", "--phase", "preview") == 0
    capsys.readouterr()
    (row,) = _rows(tmp_path)
    assert row["lint_ok"] is False and row["lint"]["attempt"] == 1


def test_no_draft_is_an_honest_failure(campaign, tmp_path, capsys):
    (campaign / "predictions" / "stage_05" / "editorial_draft_stage_preview.json").unlink()
    assert _main(campaign, tmp_path, "editorial", "--unit", "stage_05") == drv.EXIT_FAILED
    assert json.loads(capsys.readouterr().out)["error_class"] == "editorial_draft_missing"


def test_drafts_land_before_migration_0009_is_pushed(campaign, tmp_path):
    """The hosted schema may not have record / record_sha256 / artifact yet: the row still lands
    (the client drops the columns and retries once) and a re-run does not duplicate it."""
    store = FakeStore(tmp_path / "store", role="agent")
    store.editorial_review_columns = False
    d = drv.Driver(drv.Campaign.load(campaign), store, today=dt.date(2026, 10, 2))
    for _ in range(2):
        code, out = d.run_phase("stage_05", "editorial", lambda: {"editorial": d.step("editorial", lambda: d._editorial("stage_05"))},
                                idempotent=False)
        assert code == 0, out
    rows = store.rows["editorial_drafts"]
    assert len(rows) == 1
    assert "record" not in rows[0] and "record_sha256" not in rows[0] and "artifact" not in rows[0]
    assert rows[0]["lint_ok"] is True and rows[0]["body_md"].startswith("# Stage 5")


def test_the_agent_may_not_insert_a_reviewed_draft(tmp_path):
    agent = FakeStore(tmp_path, role="agent")
    for extra in ({"review_status": "approved"}, {"reviewed_by": "agent"}, {"review_notes": "fine"}):
        with pytest.raises(StorePermissionError):
            agent.insert("editorial_drafts", {"campaign_slug": SLUG, "unit": "stage_05", "phase": "preview",
                                              "body_md": "x", **extra})
    row = agent.insert_editorial_draft(None, SLUG, "stage_05", "preview", "x")
    with pytest.raises(StorePermissionError):
        agent.review_editorial_draft(row["id"], "approved", by="agent")


# ---------------------------------------------------------------------------
# the feedback digest
# ---------------------------------------------------------------------------

def test_feedback_digest_groups_verdicts_with_notes_lint_and_prose(campaign, tmp_path, capsys):
    pred = campaign / "predictions" / "stage_05"
    rec = json.loads((FIXTURE / "editorial_draft.json").read_text())
    for i, unit_head in enumerate(("Second", "Third")):
        alt = json.loads(json.dumps(rec))
        alt["sections"]["headline"] = f"{unit_head} headline for review."
        (pred / f"editorial_draft_{i}.json").write_text(json.dumps(alt))
    assert _main(campaign, tmp_path, "editorial", "--unit", "stage_05") == 0
    capsys.readouterr()
    op = FakeStore(tmp_path / "store", role="operator")
    ids = sorted(r["id"] for r in op.rows["editorial_drafts"])
    assert len(ids) == 3
    op.review_editorial_draft(ids[0], "approved", by="matt", notes="Good read; the chase-incentive paragraph lands.")
    op.review_editorial_draft(ids[1], "revise", by="matt", notes="Too long. Paragraphs too long; cut the placeholder talk.")
    op.review_editorial_draft(ids[2], "rejected", by="matt", notes="Too long and repeats the board.")
    approved = next(r for r in op.rows["editorial_drafts"] if r["id"] == ids[0])
    assert approved["approved_by"] == "matt" and approved["approved_at"]
    revised = next(r for r in op.rows["editorial_drafts"] if r["id"] == ids[1])
    assert revised["approved_by"] is None and revised["reviewed_at"]

    out_dir = tmp_path / "digest"
    assert editorial_feedback.main(["--store", "fake", "--store-root", str(tmp_path / "store"),
                                    "--out-dir", str(out_dir)]) == 0
    files = list(out_dir.glob("feedback_*.md"))
    assert len(files) == 1
    text = files[0].read_text()
    assert "**3**" in text and "approved 1" in text and "rejected 1" in text and "changes requested 1" in text
    assert text.index("## Changes requested (1)") < text.index("## Rejected (1)") < text.index("## Approved (1)")
    assert "Too long. Paragraphs too long" in text and "the chase-incentive paragraph lands" in text
    assert "| long | 2 |" in text                      # the recurring note theme
    assert "> # " in text and "> ## Stage read" in text   # the prose itself, quoted
    assert "**Lint:** name order (advisory) " in text   # the 10-01 draft named riders surname first (chip EE)
    # --since after every review: nothing reviewed, the pending count still honest
    assert editorial_feedback.main(["--store", "fake", "--store-root", str(tmp_path / "store"),
                                    "--out-dir", str(out_dir), "--since", "2999-01-01"]) == 0
    assert "Nothing has been reviewed yet." in files[0].read_text()


def test_the_digest_counts_how_often_the_retry_was_needed():
    rows = [{"lint": {"attempt": 2, "retried": True, "counts": {"placeholders": 0},
                      "first_attempt": {"ok": False, "counts": {"placeholders": 129, "lexicon": 0}}}, "lint_ok": True},
            {"lint": {"attempt": 1, "retried": False, "advisory_counts": {"name_order": 4}}, "lint_ok": True},
            {"lint": {"ok": True}, "lint_ok": True}]                  # stored before chip EE: not counted
    assert editorial_feedback.retry_tally(rows) == "Needed the lint retry: 1 of 2; still failing after it: 0."
    assert editorial_feedback.lint_summary(rows[0]["lint"]) == "second attempt; the first failed on placeholders 129"
    assert editorial_feedback.lint_summary(rows[1]["lint"]) == "name order (advisory) 4"
    assert editorial_feedback.retry_tally(rows[2:]) is None
