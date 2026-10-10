"""Weekly release bundle from the Mac (§2.10 step 4).

Collects everything the cloud nightly needs into one content-addressed
bundle::

    code-<sha>.zip                      git archive of HEAD (the release commit)
    models/production/*                 29 tracked artifacts + day_menu_kernels.parquet
    inference_slice.db                  export_slice.py output (< 500 MB)
    performance_eval/calendar/**        weekly race lists (when present)
    performance_eval/<campaign>/…       campaign.json + odds/results/predictions/review
                                        for every campaign still in the horizon
    performance_eval/crosswalk/rider_crosswalk.csv   (when present)
    performance_eval/crosswalk/uci_aliases.csv       (when present)
    experiments/selection_signatures_<stamp>.csv.gz  the newest per-competition
                                        signature table (+ its .json sidecar):
                                        hindsight references and the day-menu
                                        retrieval read it, and it is gitignored
    manifest.json                       sha256 + size per file, git sha, model
                                        contract hashes, db snapshot date, horizon

then uploads it to Supabase Storage ``releases/<tag>/`` and inserts a
``releases`` row with ``approved = false`` (a human flips it).  ``bootstrap``
downloads by these shas.

Usage::

    uv run python -m cycling_project.nightly.weekly_release --tag data-2026-09-05 --dry-run
    uv run python -m cycling_project.nightly.weekly_release --tag data-2026-09-05 --out-dir /tmp/rel
    uv run python -m cycling_project.update_pipeline --release        # final, non-fatal step

``--dry-run`` builds the bundle locally and prints the manifest without
touching the store.  With the Supabase client absent, ``--out-dir`` is the
deliverable and the upload is reported as skipped.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from cycling_project.db_path import default_db_path
from cycling_project.nightly.release_store import (
    MANIFEST_NAME,
    StoreUnavailable,
    resolve_store,
)
from cycling_project.prediction_tools.production_release import (
    MANIFEST_FILENAME as MODEL_MANIFEST,
    validate_release_manifest,
)
from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = PROJECT_ROOT / "models" / "production"
PERF_EVAL = PROJECT_ROOT / "performance_eval"
RELEASES_OUT = PERF_EVAL / "runs" / "releases"
MANIFEST_SCHEMA_VERSION = 1
KERNELS_NAME = "day_menu_kernels.parquet"
CAMPAIGN_SUBDIRS = ("odds", "results", "predictions", "review")
CAMPAIGN_TOP_SUFFIXES = (".json", ".md", ".py", ".csv")
# driver.SCRIPTS entries under performance_eval/ (kept in sync by a test)
SHARED_CAMPAIGN_TOOLS = (
    "performance_eval/tour-de-france-2026/seed_state_cache.py",
    "performance_eval/tour-de-france-2026/capture_odds.py",
    "performance_eval/vuelta-2026/score_day_keys.py",
)
SKIP_NAMES = {"__pycache__", ".DS_Store"}
NON_CAMPAIGN_DIRS = {"calendar", "crosswalk", "runs"}
CAMPAIGN_GRACE_DAYS = 3


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def mtime_iso(ts: float) -> str:
    """A file mtime as a UTC ISO timestamp (seconds), the shape ``release_store.parse_timestamp`` reads."""
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat(timespec="seconds")


def _git(*args: str, cwd: Path = PROJECT_ROOT) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def _copy(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def _walk(root: Path) -> Iterable[Path]:
    for p in sorted(root.rglob("*")):
        if p.is_file() and not any(part in SKIP_NAMES or part.startswith(".~lock") for part in p.parts):
            yield p


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------

def tracked_model_files(model_dir: Path = MODEL_DIR, project_root: Path = PROJECT_ROOT) -> List[Path]:
    """Git-tracked artifacts plus the gitignored kernels parquet."""
    rel = model_dir.relative_to(project_root)
    listed = _git("ls-files", "--", str(rel), cwd=project_root).splitlines()
    files = [project_root / line for line in listed if (project_root / line).is_file()]
    kernels = model_dir / KERNELS_NAME
    if kernels.is_file() and kernels not in files:
        files.append(kernels)
    return sorted(files)


def _campaign_dates(campaign_dir: Path) -> List[str]:
    dates: List[str] = []
    cj = campaign_dir / "campaign.json"
    if cj.is_file():
        try:
            data = json.loads(cj.read_text())
        except json.JSONDecodeError:
            data = {}
        for key in ("end_date", "end", "last_date"):
            if isinstance(data.get(key), str):
                dates.append(data[key])
        span = data.get("dates")
        if isinstance(span, dict):
            dates.extend(v for v in (span.get("end"), span.get("start")) if isinstance(v, str))
        elif isinstance(span, list):
            dates.extend(v for v in span if isinstance(v, str))
        for st in data.get("stages") or []:
            if isinstance(st, dict) and isinstance(st.get("date"), str):
                dates.append(st["date"])
    for cfg in campaign_dir.glob("predictions/*/scenarios.json"):
        try:
            d = json.loads(cfg.read_text()).get("date")
        except json.JSONDecodeError:
            continue
        if isinstance(d, str):
            dates.append(d)
    return sorted(dates)


def current_campaigns(
    perf_eval: Path = PERF_EVAL,
    today: Optional[dt.date] = None,
    grace_days: int = CAMPAIGN_GRACE_DAYS,
) -> List[Path]:
    """Campaign dirs whose latest known date is not older than ``grace_days``.

    A campaign is any ``performance_eval/<dir>`` with a ``campaign.json`` or
    ``predictions/*/scenarios.json``.  Finished campaigns (Tour 2026 in
    September) stay in git, not in the bundle.

    Tier is deliberately NOT a filter here (owner rule, 2026-09-22): a `.1`
    campaign is bundled like any other, so the same release can be run by hand
    on the Mac or opted in with ``"automation": "on"``.  What the rule changes
    is what the nightly finds *due* (``tiers.is_automated``), not what ships.
    """
    today = today or dt.date.today()
    cutoff = (today - dt.timedelta(days=grace_days)).isoformat()
    out = []
    for d in sorted(perf_eval.iterdir()) if perf_eval.is_dir() else []:
        if not d.is_dir() or d.name in NON_CAMPAIGN_DIRS or d.name.startswith("."):
            continue
        if not (d / "campaign.json").is_file() and not list(d.glob("predictions/*/scenarios.json")):
            continue
        dates = _campaign_dates(d)
        if dates and dates[-1] >= cutoff:
            out.append(d)
    return out


def campaign_files(campaign_dir: Path) -> List[Path]:
    files: List[Path] = []
    for f in sorted(campaign_dir.iterdir()):
        if f.is_file() and f.suffix in CAMPAIGN_TOP_SUFFIXES and f.name not in SKIP_NAMES:
            files.append(f)
    for sub in CAMPAIGN_SUBDIRS:
        if (campaign_dir / sub).is_dir():
            files.extend(_walk(campaign_dir / sub))
    return files


def signature_table_files(experiments_dir: Path) -> List[Path]:
    """The newest ``selection_signatures_<stamp>.csv.gz`` plus its ``.json`` sidecar (when present)."""
    from cycling_project.nightly.refs import newest_signature_table
    table = newest_signature_table(experiments_dir)
    if table is None:
        logger.warning("no experiments/selection_signatures_*.csv.gz to ship: hindsight will have no references")
        return []
    out = [table]
    sidecar = table.with_name(table.name[: -len(".csv.gz")] + ".json")
    if sidecar.is_file():
        out.append(sidecar)
    return out


def slice_snapshot(slice_path: Path) -> dict:
    """What the slice knows: latest dates and row counts of the key tables."""
    with sqlite3.connect(f"file:{slice_path}?mode=ro", uri=True) as conn:
        def scalar(sql: str):
            try:
                return conn.execute(sql).fetchone()[0]
            except sqlite3.Error:
                return None
        tables = [n for (n,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        counts = {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tables}
        return {
            "path": slice_path.name,
            "size": slice_path.stat().st_size,
            "max_competition_date": scalar("SELECT MAX(date) FROM competitions"),
            "max_result_competition_date": scalar(
                "SELECT MAX(c.date) FROM rider_results rr JOIN competitions c ON c.id = rr.competition_id"),
            "max_cached_result_at": scalar("SELECT MAX(created_at) FROM cached_race_results"),
            "max_cached_startlist_at": scalar("SELECT MAX(created_at) FROM cached_start_lists"),
            "row_counts": counts,
        }


def model_contract(model_dir: Path = MODEL_DIR) -> dict:
    report = validate_release_manifest(model_dir)   # raises on any drift
    manifest = json.loads((model_dir / MODEL_MANIFEST).read_text())
    files: Dict[str, str] = {}
    for comp in manifest["components"].values():
        for entry in comp["files"]:
            if entry.get("sha256"):
                files[entry["path"]] = entry["sha256"]
    return {
        "release_id": report.release_id,
        "artifact_count": report.artifact_count,
        "manifest_file": MODEL_MANIFEST,
        "files": files,
    }


# ---------------------------------------------------------------------------
# Bundle
# ---------------------------------------------------------------------------

def build_bundle(
    tag: str,
    out_dir: Path,
    *,
    slice_path: Optional[Path] = None,
    horizon_days: int = 14,
    today: Optional[dt.date] = None,
    project_root: Path = PROJECT_ROOT,
    model_dir: Path = MODEL_DIR,
    perf_eval: Path = PERF_EVAL,
    db_path: Optional[Path] = None,
    skip_slice: bool = False,
    experiments_dir: Optional[Path] = None,
) -> dict:
    """Assemble the bundle under ``out_dir`` and return its manifest."""
    today = today or dt.date.today()
    out_dir = Path(out_dir)
    if out_dir.exists() and any(out_dir.iterdir()):
        raise FileExistsError(f"bundle dir not empty: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)

    sha = _git("rev-parse", "HEAD", cwd=project_root)
    branch = _git("rev-parse", "--abbrev-ref", "HEAD", cwd=project_root)
    dirty = bool(_git("status", "--porcelain", "--untracked-files=no", cwd=project_root))
    if dirty:
        logger.warning("working tree has uncommitted tracked changes; code zip is HEAD only")

    files: Dict[str, dict] = {}

    def add(relpath: str, path: Path) -> None:
        st = path.stat()
        files[relpath] = {"sha256": sha256_file(path), "size": st.st_size}
        if relpath.startswith("performance_eval/"):
            # The Mac write time of this copy (``_copy`` is copy2, so the bundle file keeps the
            # source's mtime).  bootstrap.plan_overlay dates the bundle's copy by it, so a cloud
            # artifact written after the Mac last touched the file wins even when it predates
            # the release cut (2026-10-02, chip Z2: every release rolled the cumulative
            # key_scorecard.json back to the Mac's copy).
            files[relpath]["mtime"] = mtime_iso(st.st_mtime)

    # 1. code
    code_name = f"code-{sha[:12]}.zip"
    subprocess.check_call(
        # Models and campaign archives ship as separate bundle groups; keeping them
        # out of the zip holds it well under Supabase Storage's per-object cap.
        ["git", "archive", "--format=zip", "-o", str(out_dir / code_name), "HEAD", "--",
         ".", ":(exclude)models", ":(exclude)performance_eval"],
        cwd=project_root,
    )
    add(code_name, out_dir / code_name)

    # 2. models
    contract = model_contract(model_dir)
    for src in tracked_model_files(model_dir, project_root):
        rel = str(Path("models") / "production" / src.name)
        _copy(src, out_dir / rel)
        add(rel, out_dir / rel)
    for path in contract["files"]:
        if f"models/production/{path}" not in files:
            raise FileNotFoundError(f"model contract file missing from bundle: {path}")

    # 3. slice
    slice_info = None
    if not skip_slice:
        dest = out_dir / "inference_slice.db"
        if slice_path is not None:
            _copy(Path(slice_path), dest)
        else:
            from cycling_project.nightly.export_slice import export_slice
            export_slice(
                out=dest,
                horizon_days=horizon_days,
                full_db=Path(db_path or default_db_path()),
                today=today,
                perf_eval=perf_eval,
            )
        add("inference_slice.db", dest)
        slice_info = slice_snapshot(dest)

    # 4. calendar
    if (perf_eval / "calendar").is_dir():
        for f in _walk(perf_eval / "calendar"):
            rel = str(f.relative_to(project_root))
            _copy(f, out_dir / rel)
            add(rel, out_dir / rel)

    # 5. campaigns
    campaigns = []
    for cdir in current_campaigns(perf_eval, today):
        campaigns.append(cdir.name)
        for f in campaign_files(cdir):
            rel = str(f.relative_to(project_root))
            _copy(f, out_dir / rel)
            add(rel, out_dir / rel)
    # every campaign.json, even for campaigns outside the horizon (registry)
    for cj in sorted(perf_eval.glob("*/campaign.json")):
        rel = str(cj.relative_to(project_root))
        if rel not in files:
            _copy(cj, out_dir / rel)
            add(rel, out_dir / rel)
    # shared tooling that happens to live in a campaign dir ships regardless of the horizon
    # (2026-09-08: the Tour dir aged out and took seed_state_cache.py / capture_odds.py with it —
    # every settle failed at exit 20)
    for rel in SHARED_CAMPAIGN_TOOLS:
        src = project_root / rel
        if src.is_file() and rel not in files:
            _copy(src, out_dir / rel)
            add(rel, out_dir / rel)

    # 5b. the campaign-agnostic documents at the top of performance_eval (DAILY_RUNBOOK.md,
    # LESSONS.md, …): the campaign stubs point at them and a hydrated container should be able to
    # read them (chip L finding, 2026-09-08 — they reached neither bundle group)
    for doc in sorted(perf_eval.glob("*.md")):
        rel = str(doc.relative_to(project_root))
        if rel not in files:
            _copy(doc, out_dir / rel)
            add(rel, out_dir / rel)

    # 6. crosswalk + the human-confirmed UCI aliases (uci_identity.ALIASES_CSV). Until
    # 2026-10-09 only the crosswalk shipped, so the cloud never saw a confirmed alias.
    for name in ("rider_crosswalk.csv", "uci_aliases.csv"):
        crosswalk = perf_eval / "crosswalk" / name
        if crosswalk.is_file():
            rel = str(crosswalk.relative_to(project_root))
            _copy(crosswalk, out_dir / rel)
            add(rel, out_dir / rel)

    # 7. the newest per-competition signature table. `experiments/*.csv.gz` is gitignored and
    # belonged to no bundle group, so a hydrated container had none: every stage-race settle
    # that fell through to hindsight failed with "no usable historical references"
    # (Abruzzo / Taihu / Luxembourg, ticks 2026-09-14..16). Only the newest stamp ships.
    for f in signature_table_files(experiments_dir or project_root / "experiments"):
        rel = str(Path("experiments") / f.name)
        _copy(f, out_dir / rel)
        add(rel, out_dir / rel)

    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "tag": tag,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "git": {"sha": sha, "branch": branch, "dirty_tracked": dirty, "code_zip": code_name},
        "horizon": {
            "days": horizon_days,
            "start": today.isoformat(),
            "end": (today + dt.timedelta(days=horizon_days)).isoformat(),
        },
        "db_snapshot_date": (slice_info or {}).get("max_competition_date"),
        "slice": slice_info,
        "model_contract": contract,
        "campaigns": campaigns,
        "files": dict(sorted(files.items())),
        "total_bytes": sum(f["size"] for f in files.values()),
    }
    (out_dir / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return manifest


def verify_bundle(bundle_dir: Path, manifest: Optional[dict] = None) -> List[str]:
    """Return a list of problems (empty = every file matches the manifest)."""
    bundle_dir = Path(bundle_dir)
    manifest = manifest or json.loads((bundle_dir / MANIFEST_NAME).read_text())
    problems = []
    for rel, meta in manifest["files"].items():
        p = bundle_dir / rel
        if not p.is_file():
            problems.append(f"missing {rel}")
        elif p.stat().st_size != meta["size"] or sha256_file(p) != meta["sha256"]:
            problems.append(f"hash mismatch {rel}")
    return problems


def size_table(manifest: dict) -> str:
    groups: Dict[str, List[int]] = {}
    for rel, meta in manifest["files"].items():
        top = rel.split("/")[0] if "/" in rel else rel
        if top == "performance_eval":
            top = "/".join(rel.split("/")[:2])
        groups.setdefault(top, []).append(meta["size"])
    lines = [f"{'group':<48} {'files':>5} {'MB':>9}"]
    for name, sizes in sorted(groups.items(), key=lambda kv: -sum(kv[1])):
        lines.append(f"{name:<48} {len(sizes):>5} {sum(sizes)/1048576:>9.1f}")
    lines.append(f"{'TOTAL':<48} {len(manifest['files']):>5} {manifest['total_bytes']/1048576:>9.1f}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

def upload_bundle(store, bundle_dir: Path, manifest: dict) -> dict:
    keys = store.upload_release(manifest["tag"], bundle_dir, manifest)
    row = store.insert_release({
        "tag": manifest["tag"],
        "git_sha": manifest["git"]["sha"],
        "model_release_id": manifest["model_contract"]["release_id"],
        "db_snapshot_date": manifest["db_snapshot_date"],
        "horizon_end": manifest["horizon"]["end"],
        "total_bytes": manifest["total_bytes"],
        "manifest": manifest,
        "approved": False,
    })
    return {"objects": len(keys), "row": {k: v for k, v in row.items() if k != "manifest"}}


def release(
    tag: str,
    *,
    out_dir: Optional[Path] = None,
    dry_run: bool = False,
    slice_path: Optional[Path] = None,
    horizon_days: int = 14,
    store_kind: str = "hosted",
    store_root: Optional[Path] = None,
    skip_slice: bool = False,
    today: Optional[dt.date] = None,
) -> dict:
    out_dir = Path(out_dir) if out_dir else RELEASES_OUT / tag
    manifest = build_bundle(tag, out_dir, slice_path=slice_path, horizon_days=horizon_days,
                            today=today, skip_slice=skip_slice)
    problems = verify_bundle(out_dir, manifest)
    if problems:
        raise RuntimeError("bundle self-check failed: " + "; ".join(problems))
    print(size_table(manifest))
    print(f"bundle: {out_dir}  git={manifest['git']['sha'][:12]}  "
          f"models={manifest['model_contract']['release_id'][:12]}  "
          f"db_snapshot={manifest['db_snapshot_date']}  campaigns={manifest['campaigns']}")
    result = {"tag": tag, "bundle_dir": str(out_dir), "total_bytes": manifest["total_bytes"],
              "uploaded": False}
    if dry_run:
        print("dry run: not uploading")
        return result
    try:
        store = resolve_store(store_kind, store_root, role="operator")  # upload + releases row: Mac only
    except StoreUnavailable as exc:
        print(f"upload skipped: {exc}")
        result["upload_skipped"] = str(exc)
        return result
    info = upload_bundle(store, out_dir, manifest)
    print(f"uploaded {info['objects']} objects to releases/{tag}/; releases row inserted "
          f"(approved=false — approve it in Supabase to make it live)")
    result.update({"uploaded": True, **info})
    return result


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tag", required=True, help="release tag, e.g. data-2026-09-05")
    ap.add_argument("--dry-run", action="store_true", help="build the bundle, skip the upload")
    ap.add_argument("--upload-only", action="store_true",
                    help="skip the build; upload the bundle already at --out-dir (resumes a partial upload)")
    ap.add_argument("--out-dir", type=Path, default=None,
                    help=f"bundle directory (default {RELEASES_OUT}/<tag>)")
    ap.add_argument("--slice", type=Path, default=None,
                    help="use an existing inference_slice.db instead of exporting one")
    ap.add_argument("--skip-slice", action="store_true", help="bundle without a slice (tests)")
    ap.add_argument("--horizon-days", type=int, default=14)
    ap.add_argument("--store", choices=("hosted", "fake"), default="hosted")
    ap.add_argument("--store-root", type=Path, default=None, help="directory for --store fake")
    args = ap.parse_args(argv)
    if not args.tag.startswith("data-"):
        ap.error("--tag must look like data-YYYY-MM-DD")
    if args.upload_only:
        out_dir = args.out_dir or (RELEASES_OUT / args.tag)
        manifest = json.loads((Path(out_dir) / "manifest.json").read_text())
        store = resolve_store(args.store, args.store_root, role="operator")
        print(json.dumps(upload_bundle(store, Path(out_dir), manifest), indent=1, default=str))
        return

    release(args.tag, out_dir=args.out_dir, dry_run=args.dry_run, slice_path=args.slice,
            horizon_days=args.horizon_days, store_kind=args.store, store_root=args.store_root,
            skip_slice=args.skip_slice)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
