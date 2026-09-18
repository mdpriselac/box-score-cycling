"""``nightly bootstrap`` — hydrate a container from the newest approved release.

Steps (fail closed on any hash mismatch):

1. Pick the release: ``--tag`` or the newest ``releases`` row with
   ``approved = true``.
2. Download ``manifest.json`` and then every file it lists into ``--dest``
   by sha256, skipping files already present with the right hash.
3. Unzip ``code-<sha>.zip`` into ``--dest`` (bundle files win over the
   zip's copies).
4. Verify the model contract: every ``models/production`` artifact matches
   the hash recorded from ``production_release_manifest.json``, and the
   manifest validates in place (``validate_release_manifest``).
5. ``uv sync`` in ``--dest`` (skip with ``--skip-uv-sync``).
6. Hydrate campaign dirs: the bundle snapshot is already on disk; list the
   whole ``nightly-artifacts/`` bucket once (``store.list_artifacts``),
   collapse to the newest object per campaign-relative path, and download
   each path that the bundle lacks or that is newer than the release — once,
   skipping any whose bytes are already on disk (Storage md5 etag).
7. Point serving at the slice: export ``CYCLING_DB_PATH`` for this process,
   write it into ``<dest>/.env`` and ``<dest>/nightly_env.sh``.
8. Print the release tag.

Usage::

    uv run python -m cycling_project.nightly.bootstrap --dest /workspace/cycling
    uv run python -m cycling_project.nightly.bootstrap --dest D --store fake --store-root R
    uv run python -m cycling_project.nightly.bootstrap --dest D --manifest-only
"""

from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import datetime as dt
import fcntl
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable, Any, Dict, List, Optional, Sequence

from cycling_project.db_path import ENV_VAR as DB_ENV_VAR
from cycling_project.nightly.release_store import MANIFEST_NAME, md5_file, parse_timestamp, resolve_store
from cycling_project.nightly.weekly_release import sha256_file
from cycling_project.prediction_tools.production_release import validate_release_manifest
from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

RELEASE_DIR = ".release"          # <dest>/.release/{manifest.json, code-*.zip}
SLICE_NAME = "inference_slice.db"
ENV_SCRIPT = "nightly_env.sh"
LOCK_NAME = "bootstrap.lock"
DOWNLOAD_WORKERS = 8              # parallel artifact downloads in overlay_artifacts


class BootstrapError(RuntimeError):
    """Fail-closed condition: wrong hash, missing file, unapproved release."""


def _say(msg: str) -> None:
    print(msg, flush=True)


@contextlib.contextmanager
def bootstrap_lock(dest: Path):
    """Fail fast when another bootstrap owns ``dest``.

    ``flock`` is released by the kernel if the process exits or is killed, so a
    timed-out coordinator cannot leave a stale lock behind.  Failing fast is
    intentional: callers should keep polling the original process, not queue a
    second expensive hydration of the same directory.
    """
    lock_dir = dest / RELEASE_DIR
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / LOCK_NAME
    with open(lock_path, "a+b") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise BootstrapError(
                f"another bootstrap is already running for {dest}; "
                "poll that process instead of relaunching"
            ) from exc
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

def pick_release(store: Any, tag: Optional[str], allow_unapproved: bool = False) -> dict:
    row = store.get_release(tag) if tag else store.newest_approved_release()
    if row is None:
        raise BootstrapError(
            f"no release {tag!r} in the store" if tag else "no approved release in the store")
    if not row.get("approved") and not allow_unapproved:
        raise BootstrapError(f"release {row['tag']} is not approved")
    return row


def fetch_manifest(store: Any, tag: str, dest: Path) -> dict:
    target = dest / RELEASE_DIR / MANIFEST_NAME
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix=f"{MANIFEST_NAME}.part.", dir=target.parent, delete=False
    ) as fh:
        tmp = Path(fh.name)
    try:
        store.download_release_file(tag, MANIFEST_NAME, tmp)
        tmp.replace(target)
    finally:
        tmp.unlink(missing_ok=True)
    manifest = json.loads(target.read_text())
    if manifest.get("tag") != tag:
        raise BootstrapError(f"manifest tag {manifest.get('tag')!r} != {tag!r}")
    if not isinstance(manifest.get("files"), dict) or not manifest["files"]:
        raise BootstrapError("manifest lists no files")
    return manifest


def local_path(dest: Path, relpath: str, manifest: dict) -> Path:
    """Where a bundle file lives under ``dest`` (code zip goes to .release/)."""
    if relpath == manifest["git"]["code_zip"]:
        return dest / RELEASE_DIR / relpath
    return dest / relpath


def download_files(store: Any, tag: str, manifest: dict, dest: Path) -> Dict[str, str]:
    """Download every manifest file by sha; returns relpath -> 'present'|'downloaded'."""
    status: Dict[str, str] = {}
    for relpath, meta in sorted(manifest["files"].items()):
        target = local_path(dest, relpath, manifest)
        if target.is_file() and target.stat().st_size == meta["size"] and sha256_file(target) == meta["sha256"]:
            status[relpath] = "present"
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            prefix=f"{target.name}.part.", dir=target.parent, delete=False
        ) as fh:
            tmp = Path(fh.name)
        try:
            store.download_release_file(tag, relpath, tmp)
            if sha256_file(tmp) != meta["sha256"]:
                raise BootstrapError(f"sha256 mismatch after download: {relpath}")
            tmp.replace(target)
        finally:
            tmp.unlink(missing_ok=True)
        status[relpath] = "downloaded"
    return status


def unzip_code(manifest: dict, dest: Path) -> int:
    """Extract the release commit; bundle-supplied paths are not overwritten."""
    zip_path = dest / RELEASE_DIR / manifest["git"]["code_zip"]
    bundle_paths = set(manifest["files"])
    n = 0
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            name = info.filename
            if name.endswith("/") or name in bundle_paths:
                continue
            target = (dest / name).resolve()
            if not str(target).startswith(str(dest.resolve()) + os.sep):
                raise BootstrapError(f"zip entry escapes dest: {name}")
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as dst:
                dst.write(src.read())
            n += 1
    return n


def verify_models(manifest: dict, dest: Path) -> dict:
    contract = manifest["model_contract"]
    model_dir = dest / "models" / "production"
    for path, sha in sorted(contract["files"].items()):
        f = model_dir / path
        if not f.is_file():
            raise BootstrapError(f"model artifact missing: {path}")
        if sha256_file(f) != sha:
            raise BootstrapError(f"model contract hash mismatch: {path}")
    report = validate_release_manifest(model_dir)
    if report.release_id != contract["release_id"]:
        raise BootstrapError(
            f"model release id {report.release_id[:12]} != contract {contract['release_id'][:12]}")
    return {"release_id": report.release_id, "artifacts": report.artifact_count}


def uv_sync(dest: Path) -> None:
    subprocess.run(["uv", "sync"], cwd=dest, check=True)


_EPOCH = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)


def _recency(obj: dict) -> tuple:
    """Sort key: parsed ``created_at`` (unparseable -> epoch), then object key."""
    return (parse_timestamp(obj.get("created_at")) or _EPOCH, obj["key"])


def plan_overlay(objs: Iterable[dict], bundled: Iterable[str], since: Any) -> Dict[str, dict]:
    """Newest object per campaign-relative path that the overlay must consider.

    ``objs`` are ``{key, created_at, size, etag}`` rows with keys
    ``<run_id>/<campaign>/<rel>``; the run id is dropped and, per path, only
    the newest object (``created_at``, then key) survives — a path uploaded by
    twelve runs is fetched at most once and the latest run wins.

    A path is then dropped when the bundle carries a file there AND the object
    is not newer than the release: the bundle's copy is at least as new.
    (2026-09-09: the release was cut between a cloud settle and its results
    being committed, so the results existed only as artifacts older than the
    release — the previous "newer than the release" rule skipped them and the
    tick settled Tour of Britain 1–4 a second time. A path the bundle lacks
    therefore always applies.)
    """
    bundled_set = set(bundled)
    release_ts = parse_timestamp(since)
    newest: Dict[str, dict] = {}
    for obj in objs:
        parts = obj["key"].split("/")
        if len(parts) < 3:
            continue                       # not a campaign file
        rel = "/".join(parts[1:])          # drop the run id
        cur = newest.get(rel)
        if cur is None or _recency(obj) > _recency(cur):
            newest[rel] = obj
    plan: Dict[str, dict] = {}
    for rel, obj in newest.items():
        if f"performance_eval/{rel}" in bundled_set and release_ts is not None:
            obj_ts = parse_timestamp(obj.get("created_at"))
            if obj_ts is not None and obj_ts <= release_ts:
                continue                   # the bundle already carries a copy at least this new
        plan[rel] = obj
    return plan


def overlay_artifacts(store: Any, tag: str, dest: Path, manifest_files: Optional[Iterable[str]] = None) -> List[str]:
    """Copy the newest ``nightly-artifacts/<run_id>/<campaign>/<rel>`` per path onto the bundle.

    One bucket listing, one download per path at most: :func:`plan_overlay`
    collapses runs and applies the bundle rule; a planned path whose local
    file already has the object's md5 (Storage's etag) is not fetched again.
    Returns the applied object keys, oldest first.
    """
    perf = (dest / "performance_eval").resolve()
    release = store.get_release(tag) or {}
    since = release.get("created_at", "") or ""
    objs = list(store.list_artifacts()) if hasattr(store, "list_artifacts") else list(store.list_artifacts_since(tag))
    plan = plan_overlay(objs, manifest_files or (), since)
    n_paths = len({"/".join(o["key"].split("/")[1:]) for o in objs if len(o["key"].split("/")) >= 3})

    fetch: List[tuple] = []
    identical = 0
    for rel in sorted(plan):
        obj = plan[rel]
        target = (perf / Path(*rel.split("/"))).resolve()
        if not str(target).startswith(str(perf) + os.sep):
            raise BootstrapError(f"artifact key escapes performance_eval: {obj['key']}")
        etag = obj.get("etag")
        if etag and target.is_file() and md5_file(target) == etag:
            identical += 1
            continue                       # the bytes are already on disk
        fetch.append((obj, target))
    # distinct targets, so the downloads are independent; a pool hides per-request latency
    with concurrent.futures.ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as pool:
        list(pool.map(lambda item: store.download_artifact(item[0]["key"], item[1]), fetch))
    applied = sorted((obj for obj, _ in fetch), key=_recency)
    _say(f"artifacts: {len(objs)} objects listed over {n_paths} paths; {len(applied)} applied, "
         f"{n_paths - len(applied)} skipped ({n_paths - len(plan)} bundle at least as new, {identical} identical on disk)")
    return [o["key"] for o in applied]


# Plain, non-secret connection settings a fresh shell needs to reach the hosted store.  Never a
# key that grants a role: SUPABASE_NIGHTLY_KEY stays a vault placeholder in the process env only.
PLAIN_STORE_ENV = ("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_PROJECT_REF")


def write_env(dest: Path, slice_path: Path, release_tag: str) -> None:
    """Persist what every later shell in the container needs.

    2026-09-17/18: campaign threads start a fresh shell and source ``nightly_env.sh`` alone;
    it carried only the DB path and the release tag, so ``--store auto`` found no
    ``SUPABASE_URL`` there and silently fell back to a local FakeStore — runs, staged pages
    and prediction_log rows were lost with the container (hosted tasks 95, 103).  The plain
    connection settings now ride along in both files (``load_local_env`` reads ``.env``).
    """
    os.environ[DB_ENV_VAR] = str(slice_path)
    os.environ["NIGHTLY_RELEASE_TAG"] = release_tag
    values = {DB_ENV_VAR: str(slice_path), "NIGHTLY_RELEASE_TAG": release_tag}
    values.update({n: os.environ[n] for n in PLAIN_STORE_ENV if os.environ.get(n)})
    env_file = dest / ".env"
    lines = []
    if env_file.exists():
        lines = [ln for ln in env_file.read_text().splitlines()
                 if not ln.startswith(tuple(f"{n}=" for n in values))]
    lines.extend(f"{n}={v}" for n, v in values.items())
    env_file.write_text("\n".join(lines) + "\n")
    (dest / ENV_SCRIPT).write_text("".join(f"export {n}={v}\n" for n, v in values.items()))


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def bootstrap(
    dest: Path,
    store: Any,
    *,
    tag: Optional[str] = None,
    skip_uv_sync: bool = False,
    skip_artifacts: bool = False,
    allow_unapproved: bool = False,
) -> dict:
    dest = Path(dest).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    with bootstrap_lock(dest):
        return _bootstrap_locked(
            dest, store, tag=tag, skip_uv_sync=skip_uv_sync,
            skip_artifacts=skip_artifacts, allow_unapproved=allow_unapproved,
        )


def _bootstrap_locked(
    dest: Path,
    store: Any,
    *,
    tag: Optional[str] = None,
    skip_uv_sync: bool = False,
    skip_artifacts: bool = False,
    allow_unapproved: bool = False,
) -> dict:
    row = pick_release(store, tag, allow_unapproved)
    tag = row["tag"]
    _say(f"release {tag} (approved={bool(row.get('approved'))})")
    manifest = fetch_manifest(store, tag, dest)

    status = download_files(store, tag, manifest, dest)
    n_dl = sum(1 for s in status.values() if s == "downloaded")
    _say(f"files: {len(status)} in manifest, {n_dl} downloaded, {len(status) - n_dl} already present")

    n_code = unzip_code(manifest, dest)
    _say(f"code: {manifest['git']['code_zip']} -> {n_code} files (git {manifest['git']['sha'][:12]})")

    models = verify_models(manifest, dest)
    _say(f"models: contract {models['release_id'][:12]} verified ({models['artifacts']} artifacts)")

    if not skip_uv_sync:
        uv_sync(dest)
        _say("uv sync: done")

    applied: List[str] = []
    if not skip_artifacts:
        applied = overlay_artifacts(store, tag, dest, manifest_files=manifest["files"].keys())
        _say(f"campaigns: {manifest.get('campaigns')} hydrated")

    slice_path = dest / SLICE_NAME
    if SLICE_NAME in manifest["files"]:
        write_env(dest, slice_path, tag)
        _say(f"{DB_ENV_VAR}={slice_path}")
    else:
        _say("bundle has no inference slice; serving database not redirected")

    summary = {
        "release_tag": tag,
        "dest": str(dest),
        "git_sha": manifest["git"]["sha"],
        "model_release_id": models["release_id"],
        "db_snapshot_date": manifest.get("db_snapshot_date"),
        "files_downloaded": n_dl,
        "files_present": len(status) - n_dl,
        "artifacts_overlaid": applied,
        DB_ENV_VAR: str(slice_path) if SLICE_NAME in manifest["files"] else None,
    }
    print(json.dumps(summary, indent=2))
    print(f"release tag: {tag}")
    return summary


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dest", type=Path, required=True)
    ap.add_argument("--tag", default=None, help="release tag (default: newest approved)")
    ap.add_argument("--store", choices=("hosted", "fake"), default="hosted")
    ap.add_argument("--store-root", type=Path, default=None)
    ap.add_argument("--skip-uv-sync", action="store_true")
    ap.add_argument("--skip-artifacts", action="store_true")
    ap.add_argument("--allow-unapproved", action="store_true",
                    help="local testing only: accept a release the human has not approved")
    ap.add_argument("--manifest-only", action="store_true",
                    help="download and print the manifest, nothing else")
    args = ap.parse_args(argv)
    if args.store == "hosted":
        from cycling_project.nightly.secrets import load_local_env
        load_local_env()
    store = resolve_store(args.store, args.store_root)
    try:
        if args.manifest_only:
            dest = Path(args.dest).resolve()
            with bootstrap_lock(dest):
                row = pick_release(store, args.tag, args.allow_unapproved)
                manifest = fetch_manifest(store, row["tag"], dest)
                print(json.dumps({k: v for k, v in manifest.items() if k != "files"}, indent=2))
                print(f"files: {len(manifest['files'])}  total_bytes: {manifest['total_bytes']}")
                print(f"release tag: {row['tag']}")
                return 0
        bootstrap(args.dest, store, tag=args.tag, skip_uv_sync=args.skip_uv_sync,
                  skip_artifacts=args.skip_artifacts, allow_unapproved=args.allow_unapproved)
    except BootstrapError as exc:
        print(f"bootstrap FAILED (closed): {exc}", file=sys.stderr)
        return 20
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
