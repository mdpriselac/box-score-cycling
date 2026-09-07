"""Promotion: the step the cloud agent cannot take.

Spec: NIGHTLY_AGENT_WORKFLOW.md §1a (trust boundary) and §2.9 (publishing).
Everything here runs against ``store.FakeStore``, which mirrors the hosted
client's surface and its RLS rules, so the two gates — an ``approvals`` row and
a clean ``validate`` — are tested exactly as production evaluates them. No test
touches the real ``netlify_site/``, runs git, or deploys: the site directory is
redirected to a tmp path and the rebuild is stubbed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cycling_project.nightly import promote as P
from cycling_project.nightly.store import FakeStore

pytestmark = pytest.mark.unit

CAMPAIGN = "vuelta-2026"


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def site(tmp_path, monkeypatch):
    """Redirect the repo's netlify_site/ and neuter the rebuild + record write."""
    site_dir = tmp_path / "netlify_site"
    site_dir.mkdir()
    monkeypatch.setattr(P, "SITE_DIR", site_dir)
    monkeypatch.setattr(P, "rebuild_frame", lambda: [{"script": "stub", "returncode": 0}])
    monkeypatch.setattr(P, "record_path", lambda run: None)
    return site_dir


@pytest.fixture
def store(tmp_path):
    return FakeStore(tmp_path / "store", role="operator")


def stage_run(store, *, unit="stage_15", phase="settle", finish="ok", exit_code=0,
              validate="ok", pages=("vuelta-stage15.html", "_frame/home.html"),
              approve="approve", note=None):
    """A finished run with staged pages, and optionally a decision on it."""
    run = store.start_run(CAMPAIGN, unit, phase, release_tag="data-2026-09-07",
                          session_id="sesn_test", deployment="nightly")
    rid = run["run_id"]
    store.add_step(rid, "predict", "ok", duration_ms=1000)
    if validate is not None:
        store.add_step(rid, "validate", validate, duration_ms=50)
    if finish is not None:
        store.finish_run(rid, finish, exit_code)
    for i, rel in enumerate(pages):
        target = store.staging_dir / rid / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"<html>{rel} v{i}</html>")
    if approve:
        store.approve_run(rid, by="matt@example.test", note=note)
        if approve != "approve":
            store.insert("approvals", {"run_id": rid, "campaign_slug": CAMPAIGN, "unit": unit,
                                       "kind": "publish", "decision": approve,
                                       "approved_by": "matt@example.test"})
    return rid


def run_promote(store, rid=None, **kw):
    kw.setdefault("do_commit", False)
    kw.setdefault("do_deploy", False)
    return P.promote(store, run_id=rid, **kw)


# ---------------------------------------------------------------------------
# the happy path
# ---------------------------------------------------------------------------

def test_approved_run_publishes_its_pages(store, site):
    rid = stage_run(store)
    out = run_promote(store, rid)

    assert out["pages"]["added"] == ["_frame/home.html", "vuelta-stage15.html"]
    assert (site / "vuelta-stage15.html").read_text().startswith("<html>vuelta-stage15.html")
    assert (site / "_frame" / "home.html").exists()
    assert out["approved_by"] == "matt@example.test"
    assert out["campaign"] == CAMPAIGN and out["unit"] == "stage_15"


def test_unchanged_pages_are_not_recopied(store, site):
    rid = stage_run(store)
    run_promote(store, rid)
    again = run_promote(store, rid)
    assert again["pages"]["added"] == [] and again["pages"]["changed"] == []
    assert len(again["pages"]["unchanged"]) == 2


def test_changed_page_is_reported_as_changed(store, site):
    rid = stage_run(store)
    run_promote(store, rid)
    (store.staging_dir / rid / "vuelta-stage15.html").write_text("<html>revised</html>")
    out = run_promote(store, rid)
    assert out["pages"]["changed"] == ["vuelta-stage15.html"]
    assert (site / "vuelta-stage15.html").read_text() == "<html>revised</html>"


def test_latest_approved_picks_the_newest_standing_approval(store, site):
    stage_run(store, unit="stage_14")
    newest = stage_run(store, unit="stage_15")
    out = run_promote(store, None, campaign=CAMPAIGN)
    assert out["run_id"] == newest and out["unit"] == "stage_15"


# ---------------------------------------------------------------------------
# gate 1: the approval
# ---------------------------------------------------------------------------

def test_unapproved_run_is_refused(store, site):
    rid = stage_run(store, approve=None)
    with pytest.raises(P.PromoteRefused) as exc:
        run_promote(store, rid)
    assert exc.value.reason == "not_approved"
    assert not list(site.rglob("*.html"))


def test_a_hold_after_an_approve_wins(store, site):
    rid = stage_run(store, approve="hold")
    with pytest.raises(P.PromoteRefused) as exc:
        run_promote(store, rid)
    assert exc.value.reason == "not_approved"
    assert exc.value.detail["decision"] == "hold"


def test_latest_approved_skips_a_held_run(store, site):
    ok = stage_run(store, unit="stage_14")
    stage_run(store, unit="stage_15", approve="hold")
    assert run_promote(store, None, campaign=CAMPAIGN)["run_id"] == ok


def test_nothing_approved_is_refused(store, site):
    stage_run(store, approve=None)
    with pytest.raises(P.PromoteRefused) as exc:
        run_promote(store, None, campaign=CAMPAIGN)
    assert exc.value.reason == "nothing_approved"


def test_unknown_run_is_refused(store, site):
    with pytest.raises(P.PromoteRefused) as exc:
        run_promote(store, "11111111-2222-3333-4444-555555555555")
    assert exc.value.reason == "unknown_run"


# ---------------------------------------------------------------------------
# gate 2: the ledger
# ---------------------------------------------------------------------------

def test_a_failed_validate_is_never_published(store, site):
    rid = stage_run(store, validate="failed")
    with pytest.raises(P.PromoteRefused) as exc:
        run_promote(store, rid)
    assert exc.value.reason == "validate_failed"
    assert not list(site.rglob("*.html"))


def test_a_waiting_run_is_not_published(store, site):
    rid = stage_run(store, finish="waiting", exit_code=10)
    with pytest.raises(P.PromoteRefused) as exc:
        run_promote(store, rid)
    assert exc.value.reason == "run_not_ok"


def test_an_unfinished_run_is_not_published(store, site):
    rid = stage_run(store, finish=None)
    with pytest.raises(P.PromoteRefused) as exc:
        run_promote(store, rid)
    assert exc.value.reason == "run_not_ok"


def test_a_run_that_staged_nothing_is_refused(store, site):
    rid = stage_run(store, pages=())
    with pytest.raises(P.PromoteRefused) as exc:
        run_promote(store, rid)
    assert exc.value.reason == "nothing_staged"


# ---------------------------------------------------------------------------
# object keys are untrusted input
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rel", ["../secrets.env", "a/../../x.html", "_frame/ops.html",
                                 "build/build_stage_page.py", "worker/index.js"])
def test_dangerous_staged_keys_are_rejected(rel):
    with pytest.raises(ValueError):
        P.safe_relpath(f"run-1/{rel}", "run-1")


def test_safe_keys_survive():
    assert P.safe_relpath("run-1/vuelta-stage16.html", "run-1") == "vuelta-stage16.html"
    assert P.safe_relpath("run-1/_frame/race/x-2026.html", "run-1") == "_frame/race/x-2026.html"


def test_a_dangerous_key_is_skipped_not_fatal(store, site):
    rid = stage_run(store, pages=("vuelta-stage15.html",))
    bad = store.staging_dir / rid / "_frame" / "ops.html"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("operator page")
    out = run_promote(store, rid)
    assert out["pages"]["added"] == ["vuelta-stage15.html"]
    assert not (site / "_frame" / "ops.html").exists()
    assert any("skipped" in o for o in out["objects"])


# ---------------------------------------------------------------------------
# dry run
# ---------------------------------------------------------------------------

def test_dry_run_writes_nothing(store, site):
    rid = stage_run(store)
    out = P.promote(store, run_id=rid, dry_run=True)
    assert out["pages"]["added"] == ["_frame/home.html", "vuelta-stage15.html"]
    assert not list(site.rglob("*"))
    assert out["commit"] == {"committed": False, "reason": "dry run"}
    assert out["deploy"] == {"deployed": False, "reason": "dry run"}


def test_dry_run_still_applies_both_gates(store, site):
    rid = stage_run(store, validate="error")
    with pytest.raises(P.PromoteRefused):
        P.promote(store, run_id=rid, dry_run=True)


# ---------------------------------------------------------------------------
# the commit message and the CLI
# ---------------------------------------------------------------------------

def test_commit_message_names_the_run_the_approver_and_the_pages(store, site):
    rid = stage_run(store, note="looks right")
    run, decision = store.get_run(rid), store.approvals(run_id=rid)[0]
    msg = P.commit_message(run, decision, {"added": ["vuelta-stage15.html"], "changed": [], "unchanged": []})
    assert msg.startswith("Publish vuelta-2026 stage_15 (settle) — 1 page\n")
    assert rid in msg and "matt@example.test" in msg
    assert "data-2026-09-07" in msg and "looks right" in msg
    assert "vuelta-stage15.html" in msg


def test_cli_refuses_an_unapproved_run_with_exit_10(store, site, tmp_path, capsys):
    rid = stage_run(store, approve=None)
    code = P.main(["--run", rid, "--store", "fake", "--store-root", str(tmp_path / "store"),
                   "--dry-run"])
    assert code == P.EXIT_REFUSED
    assert json.loads(capsys.readouterr().out)["refused"] == "not_approved"


def test_cli_dry_run_reports_the_pages(store, site, tmp_path, capsys):
    rid = stage_run(store)
    code = P.main(["--run", rid, "--store", "fake", "--store-root", str(tmp_path / "store"),
                   "--dry-run"])
    assert code == P.EXIT_OK
    out = json.loads(capsys.readouterr().out)
    assert out["run_id"] == rid and out["dry_run"] is True
    assert out["pages"]["added"] == ["_frame/home.html", "vuelta-stage15.html"]


def test_the_agent_role_cannot_read_approvals(tmp_path):
    """The gate is only readable with the operator key — the deployment has neither."""
    agent = FakeStore(tmp_path / "store", role="agent")
    with pytest.raises(Exception) as exc:
        agent.approvals()
    assert "operator" in str(exc.value)


def test_promote_module_never_calls_the_driver():
    """Promotion is git + deploy; the driver guarantees it does neither."""
    source = Path(P.__file__).read_text()
    assert "from cycling_project.nightly.driver" not in source
    assert "import driver" not in source


def test_commit_stages_only_what_it_published(store, site, monkeypatch):
    """An operator editing another page must not have it swept into the publish."""
    calls = []
    monkeypatch.setattr(P, "git", lambda *a, **kw: calls.append(a) or type(
        "R", (), {"stdout": "", "returncode": 0})())
    P.commit("msg", ["vuelta-stage15.html"])
    added = next(a for a in calls if a[0] == "add")
    assert [Path(x).name for x in added[2:]] == ["site-index.json", "_frame", "vuelta-stage15.html"]
