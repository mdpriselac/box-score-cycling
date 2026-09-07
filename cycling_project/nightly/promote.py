"""
Publish an approved night's pages — the step the cloud agent deliberately
cannot take (NIGHTLY_AGENT_WORKFLOW.md §1a, §2.9).

    uv run python -m cycling_project.nightly.promote --run <run_id>
    uv run python -m cycling_project.nightly.promote --latest-approved --dry-run

The nightly stages its built pages into ``site-staging/<run_id>/`` and stops.
Promotion runs **here, on the Mac**, with the operator's secret key — a key the
deployment never holds — and does what the agent may not: copy the pages into
the repo, commit them, and deploy the public site.

Two gates, neither of them overridable:

* an ``approvals`` row with ``decision = 'approve'`` for that run (a later
  ``reject`` or ``hold`` on the same run wins — the newest decision rules);
* the run's own ledger: its ``finish`` step is ``ok`` and no ``validate`` step
  errored. A unit that failed validation never reaches the site.

This is not part of the driver. ``cycling_project/nightly/driver.py`` runs in
the container and asserts it never invokes git; promotion is git plus a deploy,
so it lives in its own module with its own entry point.

Order of work: download the staged objects → copy into ``netlify_site/`` →
rebuild ``site-index.json`` and ``_frame/`` (the frame renders from the index,
so a new stage page is invisible until both run) → commit → deploy. Every
step is skippable, and ``--dry-run`` does none of them.
"""

from __future__ import annotations

import argparse
import datetime as dt
import filecmp
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from cycling_project.nightly.secrets import load_local_env
from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SITE_DIR = PROJECT_ROOT / "netlify_site"
SITE_BUILD = SITE_DIR / "build"
LAUNCH_JSON = PROJECT_ROOT / ".claude" / "launch.json"
WRANGLER_CONFIG = SITE_DIR / "wrangler.jsonc"
TRUNK = "webscrape-refactor"

EXIT_OK = 0
EXIT_REFUSED = 10          # nothing to promote, or a gate said no
EXIT_FAILED = 20           # a step blew up

# Never copied out of site-staging into the repo, whatever a run staged.
FORBIDDEN_NAMES = {"ops.html"}
FORBIDDEN_PARTS = {"..", ".git", "build", "worker", "node_modules"}


class PromoteRefused(RuntimeError):
    """A gate said no. Not an error — the answer is 'not this run'."""

    def __init__(self, reason: str, message: str, detail: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.reason, self.detail = reason, detail or {}


def _utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# gates
# ---------------------------------------------------------------------------

def latest_decision(rows: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Newest approvals row wins — a hold after an approve holds."""
    if not rows:
        return None
    return sorted(rows, key=lambda r: (str(r.get("created_at") or ""), r.get("id") or 0))[-1]


def check_approved(store: Any, run_id: str) -> Dict[str, Any]:
    rows = store.approvals(run_id=run_id)
    decision = latest_decision(rows)
    if decision is None:
        if store.get_run(run_id) is None:
            raise PromoteRefused("unknown_run", f"no run {run_id} in the ledger", {"run_id": run_id})
        raise PromoteRefused("not_approved",
                             f"run {run_id} has no approvals row — approve it in the inbox first",
                             {"run_id": run_id})
    if decision.get("decision") != "approve":
        raise PromoteRefused("not_approved",
                             f"run {run_id} was last marked {decision.get('decision')!r} "
                             f"by {decision.get('approved_by')}",
                             {"run_id": run_id, "decision": decision.get("decision")})
    return decision


def check_ledger(store: Any, run_id: str) -> Dict[str, Any]:
    """Refuse a run that failed, is unfinished, or whose validate step errored."""
    run = store.get_run(run_id)
    if run is None:
        raise PromoteRefused("unknown_run", f"no run {run_id} in the ledger", {"run_id": run_id})
    steps = store.run_steps(run_id)
    bad = {"error", "failed", "timeout"}
    failed_validate = [s for s in steps if s.get("step") == "validate" and s.get("state") in bad]
    if failed_validate:
        raise PromoteRefused("validate_failed",
                             f"run {run_id} failed validate — its pages are not publishable",
                             {"run_id": run_id, "steps": [s.get("detail") for s in failed_validate]})
    finish = [s for s in steps if s.get("step") == "finish"]
    state = (finish[-1] if finish else {}).get("state") or run.get("state")
    if state != "ok":
        raise PromoteRefused("run_not_ok",
                             f"run {run_id} finished as {state!r}, not 'ok'",
                             {"run_id": run_id, "state": state})
    return run


def pick_run(store: Any, *, run_id: Optional[str], campaign: Optional[str]) -> str:
    if run_id:
        return run_id
    rows = store.approvals(decision="approve")
    seen = set()
    for row in sorted(rows, key=lambda r: (str(r.get("created_at") or ""), r.get("id") or 0), reverse=True):
        rid = str(row["run_id"])
        if rid in seen:
            continue
        seen.add(rid)
        if latest_decision(store.approvals(run_id=rid)).get("decision") != "approve":
            continue                      # a later hold or reject on the same run
        if campaign:
            run = store.get_run(rid)
            slug = (run or {}).get("campaign_slug") or row.get("campaign_slug")
            if slug != campaign:
                continue
        return rid
    raise PromoteRefused("nothing_approved",
                         "no approved run" + (f" for {campaign}" if campaign else ""),
                         {"campaign": campaign})


# ---------------------------------------------------------------------------
# staged pages
# ---------------------------------------------------------------------------

def safe_relpath(key: str, run_id: str) -> str:
    """``<run_id>/<netlify_site-relative path>`` → the relative path, checked.

    Object keys come from a machine the operator does not control, so a key
    that climbs out of ``netlify_site/`` or lands on the ops page is dropped
    rather than trusted.
    """
    rel = key[len(run_id) + 1:] if key.startswith(f"{run_id}/") else key
    parts = [p for p in Path(rel).parts]
    if not parts or Path(rel).is_absolute():
        raise ValueError(f"unusable object key {key!r}")
    if any(p in FORBIDDEN_PARTS for p in parts) or parts[-1] in FORBIDDEN_NAMES:
        raise ValueError(f"refusing staged object {key!r}")
    return Path(*parts).as_posix()


def fetch_pages(store: Any, run_id: str, dest: Path) -> List[Dict[str, Any]]:
    objects = store.list_staged(run_id)
    if not objects:
        raise PromoteRefused("nothing_staged",
                             f"run {run_id} staged no pages under site-staging/",
                             {"run_id": run_id})
    out = []
    for obj in objects:
        try:
            rel = safe_relpath(obj["key"], run_id)
        except ValueError as exc:
            logger.warning("%s", exc)
            out.append({"key": obj["key"], "skipped": str(exc)})
            continue
        store.download_staged(obj["key"], dest / rel)
        out.append({"key": obj["key"], "path": rel, "size": obj.get("size")})
    if not any("path" in o for o in out):
        raise PromoteRefused("nothing_staged", f"run {run_id} staged nothing promotable",
                             {"run_id": run_id, "objects": out})
    return out


def copy_into_site(staged: Path, pages: List[Dict[str, Any]], *, apply: bool) -> Dict[str, List[str]]:
    added, changed, same = [], [], []
    for page in pages:
        rel = page.get("path")
        if not rel:
            continue
        src, dst = staged / rel, SITE_DIR / rel
        if not dst.exists():
            added.append(rel)
        elif filecmp.cmp(src, dst, shallow=False):
            same.append(rel)
            continue
        else:
            changed.append(rel)
        if apply:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    return {"added": sorted(added), "changed": sorted(changed), "unchanged": sorted(same)}


# ---------------------------------------------------------------------------
# rebuild / commit / deploy
# ---------------------------------------------------------------------------

def run_cmd(argv: Sequence[str], *, cwd: Path = PROJECT_ROOT, env: Optional[dict] = None,
            timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run([str(a) for a in argv], cwd=str(cwd), capture_output=True, text=True,
                          timeout=timeout, env=env)


def rebuild_frame() -> List[Dict[str, Any]]:
    """site-index.json then _frame/ — the frame renders only what the index lists."""
    out = []
    for script in ("build_site_index.py", "build_site_frame.py"):
        proc = run_cmd([sys.executable, SITE_BUILD / script])
        out.append({"script": script, "returncode": proc.returncode,
                    "stdout": proc.stdout.strip()[-400:], "stderr": proc.stderr.strip()[-400:]})
        if proc.returncode != 0:
            raise RuntimeError(f"{script} failed: {proc.stderr.strip()[-400:]}")
    return out


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    proc = run_cmd(["git", *args], timeout=180)
    if check and proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {proc.stderr.strip()[-400:]}")
    return proc


def current_branch() -> str:
    return git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()


def commit_message(run: Dict[str, Any], decision: Dict[str, Any], counts: Dict[str, List[str]]) -> str:
    unit = run.get("unit") or "site"
    campaign = run.get("campaign_slug") or "site"
    n = len(counts["added"]) + len(counts["changed"])
    lines = [
        f"Publish {campaign} {unit} ({run.get('phase')}) — {n} page{'' if n == 1 else 's'}",
        "",
        f"Promoted from site-staging/{run.get('run_id')} after an approvals row from "
        f"{decision.get('approved_by')} ({decision.get('created_at')}).",
    ]
    if run.get("release_tag"):
        lines.append(f"Release {run['release_tag']}.")
    if decision.get("note"):
        lines.append(f"Note: {decision['note']}")
    if counts["added"]:
        lines += ["", "New:"] + [f"  {p}" for p in counts["added"][:20]]
    if counts["changed"]:
        lines += ["", "Updated:"] + [f"  {p}" for p in counts["changed"][:20]]
    return "\n".join(lines) + "\n"


def commit(message: str, paths: Sequence[str] = ()) -> Dict[str, Any]:
    """Stage only what this promotion wrote — the pages it copied plus the two
    rebuild outputs — so an operator's unrelated edits under ``netlify_site/``
    are never swept into a publish commit."""
    try:
        site = SITE_DIR.relative_to(PROJECT_ROOT)
    except ValueError:                       # a redirected SITE_DIR (tests)
        site = SITE_DIR
    targets = [str(site / "site-index.json"), str(site / "_frame")]
    targets += [str(site / rel) for rel in paths]
    git("add", "--", *targets)
    staged = git("diff", "--cached", "--name-only").stdout.split()
    if not staged:
        return {"committed": False, "reason": "nothing changed after the rebuild"}
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
        fh.write(message)
        path = fh.name
    try:
        git("commit", "-F", path)
    finally:
        os.unlink(path)
    return {"committed": True, "sha": git("rev-parse", "HEAD").stdout.strip(), "files": staged}


def npx_path() -> Optional[str]:
    """The absolute npx the site-frame launch config uses, else whatever is on PATH."""
    try:
        cfgs = json.loads(LAUNCH_JSON.read_text()).get("configurations", [])
        for cfg in cfgs:
            exe = cfg.get("runtimeExecutable", "")
            if cfg.get("name") == "site-frame" and Path(exe).is_absolute():
                return exe
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    return shutil.which("npx")


def deploy() -> Dict[str, Any]:
    npx = npx_path()
    if not npx:
        return {"deployed": False, "reason": "no npx on PATH — install Node or run wrangler by hand"}
    env = {**os.environ}
    who = run_cmd([npx, "wrangler", "whoami"], timeout=300, env=env)
    if who.returncode != 0:
        return {"deployed": False,
                "reason": "wrangler is not authenticated — run `npx wrangler login`, or put "
                          "CLOUDFLARE_ACCOUNT_ID + CLOUDFLARE_API_TOKEN in "
                          "~/.config/cycling-project/secrets.env",
                "stderr": who.stderr.strip()[-400:]}
    proc = run_cmd([npx, "wrangler", "deploy", "--config", WRANGLER_CONFIG], timeout=900, env=env)
    if proc.returncode != 0:
        raise RuntimeError(f"wrangler deploy failed: {proc.stderr.strip()[-600:]}")
    return {"deployed": True, "stdout": proc.stdout.strip()[-600:]}


# ---------------------------------------------------------------------------
# orchestration
# ---------------------------------------------------------------------------

def open_store(kind: str, root: Optional[Path]) -> Any:
    from cycling_project.nightly import store as _store
    if kind == "fake":
        return _store.FakeStore(root, role="operator")
    load_local_env()
    return _store.SupabaseStore(role="operator")


def record_path(run: Dict[str, Any]) -> Optional[Path]:
    campaign = run.get("campaign_slug")
    if not campaign:
        return None
    day = (run.get("started_at") or _utcnow())[:10]
    return (PROJECT_ROOT / "performance_eval" / campaign / "runs" / day /
            f"promote_{run.get('unit') or 'site'}.json")


def promote(store: Any, *, run_id: Optional[str] = None, campaign: Optional[str] = None,
            dry_run: bool = False, do_commit: bool = True, do_deploy: bool = True,
            branch: Optional[str] = TRUNK, any_branch: bool = False) -> Dict[str, Any]:
    rid = pick_run(store, run_id=run_id, campaign=campaign)
    decision = check_approved(store, rid)
    run = check_ledger(store, rid)
    run.setdefault("run_id", rid)

    result: Dict[str, Any] = {
        "run_id": rid, "campaign": run.get("campaign_slug"), "unit": run.get("unit"),
        "phase": run.get("phase"), "release_tag": run.get("release_tag"),
        "approved_by": decision.get("approved_by"), "approved_at": decision.get("created_at"),
        "dry_run": dry_run, "promoted_at": _utcnow(),
    }

    if do_commit and not dry_run and not any_branch:
        here = current_branch()
        if branch and here != branch:
            raise PromoteRefused("wrong_branch",
                                 f"on {here!r}, not {branch!r} — the site is published from the trunk "
                                 f"(pass --any-branch to override)", {"branch": here})

    with tempfile.TemporaryDirectory(prefix="promote-") as tmp:
        staged = Path(tmp)
        pages = fetch_pages(store, rid, staged)
        result["objects"] = pages
        counts = copy_into_site(staged, pages, apply=not dry_run)
        result["pages"] = counts

        if dry_run:
            result["rebuilt"] = "skipped (dry run)"
            result["commit"] = {"committed": False, "reason": "dry run"}
            result["deploy"] = {"deployed": False, "reason": "dry run"}
            return result

        result["rebuilt"] = rebuild_frame()
        published = counts["added"] + counts["changed"]
        result["commit"] = (commit(commit_message(run, decision, counts), published) if do_commit
                            else {"committed": False, "reason": "--no-commit"})
        result["deploy"] = (deploy() if do_deploy
                            else {"deployed": False, "reason": "--no-deploy"})

    path = record_path(run)
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2, sort_keys=True, default=str))
        result["record"] = str(path.relative_to(PROJECT_ROOT))
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m cycling_project.nightly.promote",
        description="Publish an approved night's staged pages (operator key; never the agent's).")
    what = ap.add_mutually_exclusive_group(required=True)
    what.add_argument("--run", help="run_id to promote")
    what.add_argument("--latest-approved", action="store_true",
                      help="the newest run with a standing approval")
    ap.add_argument("--campaign", help="restrict --latest-approved to one campaign slug")
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would be published; copy nothing, commit nothing, deploy nothing")
    ap.add_argument("--no-commit", action="store_true", help="copy and rebuild, leave the tree dirty")
    ap.add_argument("--no-deploy", action="store_true", help="commit but do not deploy")
    ap.add_argument("--any-branch", action="store_true",
                    help=f"allow a commit off {TRUNK}")
    ap.add_argument("--store", choices=("auto", "supabase", "fake"), default="auto")
    ap.add_argument("--store-root", type=Path, help="FakeStore directory (--store fake)")
    args = ap.parse_args(argv)

    try:
        store = open_store("fake" if args.store == "fake" else "supabase", args.store_root)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error_class": type(exc).__name__, "message": str(exc)}, indent=2))
        return EXIT_FAILED

    try:
        result = promote(store, run_id=args.run, campaign=args.campaign, dry_run=args.dry_run,
                         do_commit=not args.no_commit, do_deploy=not args.no_deploy,
                         any_branch=args.any_branch)
    except PromoteRefused as refused:
        print(json.dumps({"refused": refused.reason, "message": str(refused),
                          "detail": refused.detail}, indent=2))
        return EXIT_REFUSED
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error_class": type(exc).__name__, "message": str(exc)}, indent=2))
        return EXIT_FAILED

    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
