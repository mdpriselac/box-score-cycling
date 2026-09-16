"""Release-bundle side of the Supabase store, with a filesystem fake.

The Supabase client proper (``cycling_project/nightly/store.py``, PostgREST +
Storage, sibling task) owns the network.  This module fixes the *interface*
the release tooling needs from it, so ``weekly_release.py`` and
``bootstrap.py`` work today against a directory (``FakeStore``) and switch to
the real client the moment it exists — :func:`resolve_store` prefers
``store.py`` and falls back with a clear message.

Interface (all paths are bundle-relative, e.g. ``models/production/x.txt``)::

    upload_release(tag, bundle_dir, manifest) -> list[str]      # object keys written
    insert_release(row) -> dict                                  # releases row, approved=False
    newest_approved_release() -> dict | None                     # releases row incl. manifest
    get_release(tag) -> dict | None
    download_release_file(tag, relpath, dest) -> Path
    list_artifacts_since(release_tag) -> list[dict]              # {key, created_at, size, etag}
    list_artifacts() -> list[dict]                               # same shape, every run
    download_artifact(key, dest) -> Path

``etag`` is the object's md5 hex as Storage reports it (quotes stripped), or
``None`` when the store cannot supply one; ``bootstrap.overlay_artifacts``
uses it to skip a download whose bytes are already on disk.

Storage layout mirrored by the fake:  ``releases/<tag>/<relpath>`` and
``nightly-artifacts/<run_id>/<campaign>/<relpath>``.  The fake keeps the
``releases`` rows in ``releases.json`` next to the buckets.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

RELEASES_BUCKET = "releases"
ARTIFACTS_BUCKET = "nightly-artifacts"
MANIFEST_NAME = "manifest.json"


class StoreUnavailable(RuntimeError):
    """The hosted store client is absent or lacks a required call."""


@runtime_checkable
class ReleaseStore(Protocol):
    def upload_release(self, tag: str, bundle_dir: Path, manifest: dict) -> List[str]: ...
    def insert_release(self, row: dict) -> dict: ...
    def newest_approved_release(self) -> Optional[dict]: ...
    def get_release(self, tag: str) -> Optional[dict]: ...
    def download_release_file(self, tag: str, relpath: str, dest: Path) -> Path: ...
    def list_artifacts_since(self, release_tag: str) -> List[dict]: ...
    def list_artifacts(self) -> List[dict]: ...
    def download_artifact(self, key: str, dest: Path) -> Path: ...


def _utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def parse_timestamp(value: Any) -> Optional[dt.datetime]:
    """ISO-8601 -> aware UTC datetime; accepts Storage's ``…Z`` and PostgREST's ``…+00:00``.

    Returns ``None`` for empty/unparseable input so callers fall back to the
    conservative branch instead of comparing timestamp strings, whose
    lexical order breaks across the two suffix styles.
    """
    if not value:
        return None
    text = str(value).strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def md5_hex(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def md5_file(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class FakeStore:
    """Directory-backed store: ``<root>/releases/<tag>/…``, ``<root>/nightly-artifacts/…``.

    Used by tests, ``--dry-run`` and the local ``--out-dir`` flow.  Every
    method has the same signature and return shape as the hosted client.
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self.releases_dir = self.root / RELEASES_BUCKET
        self.artifacts_dir = self.root / ARTIFACTS_BUCKET
        self.rows_path = self.root / "releases.json"
        self.releases_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    # -- releases rows ------------------------------------------------------
    def _rows(self) -> List[dict]:
        if self.rows_path.exists():
            return json.loads(self.rows_path.read_text())
        return []

    def _write_rows(self, rows: List[dict]) -> None:
        self.rows_path.write_text(json.dumps(rows, indent=2, sort_keys=True))

    def insert_release(self, row: dict) -> dict:
        rows = self._rows()
        if any(r["tag"] == row["tag"] for r in rows):
            raise ValueError(f"release {row['tag']} already exists")
        stored = {"approved": False, "created_at": _utcnow(), **row}
        rows.append(stored)
        self._write_rows(rows)
        return stored

    def approve(self, tag: str, by: str = "test") -> None:
        """Human action in production (dashboard); exposed for tests."""
        rows = self._rows()
        for r in rows:
            if r["tag"] == tag:
                r["approved"] = True
                r["approved_by"] = by
                r["approved_at"] = _utcnow()
        self._write_rows(rows)

    def get_release(self, tag: str) -> Optional[dict]:
        return next((r for r in self._rows() if r["tag"] == tag), None)

    def newest_approved_release(self) -> Optional[dict]:
        approved = [r for r in self._rows() if r.get("approved")]
        if not approved:
            return None
        return max(approved, key=lambda r: (r.get("created_at", ""), r["tag"]))

    # -- releases bucket ----------------------------------------------------
    def upload_release(self, tag: str, bundle_dir: Path, manifest: dict) -> List[str]:
        bundle_dir = Path(bundle_dir)
        target = self.releases_dir / tag
        if target.exists():
            raise ValueError(f"release objects already exist under {RELEASES_BUCKET}/{tag}/")
        keys: List[str] = []
        for relpath in sorted(manifest["files"]):
            src = bundle_dir / relpath
            dst = target / relpath
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            keys.append(f"{RELEASES_BUCKET}/{tag}/{relpath}")
        (target / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2, sort_keys=True))
        keys.append(f"{RELEASES_BUCKET}/{tag}/{MANIFEST_NAME}")
        return keys

    def download_release_file(self, tag: str, relpath: str, dest: Path) -> Path:
        src = self.releases_dir / tag / relpath
        if not src.is_file():
            raise FileNotFoundError(f"{RELEASES_BUCKET}/{tag}/{relpath}")
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        return dest

    # -- nightly-artifacts bucket ------------------------------------------
    def put_artifact(self, key: str, data: bytes, created_at: Optional[str] = None) -> str:
        """Insert-only object write (what the agent's ``upload`` does)."""
        path = self.artifacts_dir / key
        if path.exists():
            raise ValueError(f"object exists: {ARTIFACTS_BUCKET}/{key}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        meta = self.artifacts_dir / (key + ".meta.json")
        meta.write_text(json.dumps({"created_at": created_at or _utcnow(), "size": len(data),
                                    "etag": md5_hex(data)}))
        return key

    def list_artifacts_since(self, release_tag: str) -> List[dict]:
        release = self.get_release(release_tag)
        since = parse_timestamp(release.get("created_at")) if release else None
        if since is None:
            return self.list_artifacts()
        return [o for o in self.list_artifacts()
                if (parse_timestamp(o["created_at"]) or since) >= since]

    def list_artifacts(self) -> List[dict]:
        """Every artifact of every run, oldest first: ``{key, created_at, size, etag}``."""
        out = []
        for meta in self.artifacts_dir.rglob("*.meta.json"):
            info = json.loads(meta.read_text())
            key = str(meta.relative_to(self.artifacts_dir))[: -len(".meta.json")]
            out.append({"key": key, "created_at": info["created_at"], "size": info["size"],
                        "etag": info.get("etag")})
        return sorted(out, key=lambda o: (o["created_at"], o["key"]))

    def download_artifact(self, key: str, dest: Path) -> Path:
        src = self.artifacts_dir / key
        if not src.is_file():
            raise FileNotFoundError(f"{ARTIFACTS_BUCKET}/{key}")
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        return dest


LocalDirStore = FakeStore

_REQUIRED = (
    "upload_release", "insert_release", "newest_approved_release", "get_release",
    "download_release_file", "list_artifacts_since", "download_artifact",
)


def hosted_store(role: str = "agent") -> Any:
    """The sibling Supabase client for ``role``, or raise :class:`StoreUnavailable`.

    ``role`` is ``agent`` (nightly container: read releases), ``reader`` or
    ``operator`` (the Mac: upload/approve releases — needs SUPABASE_SECRET_KEY).

    Accepts either a module exposing the functions or a module with a
    ``Store``/``SupabaseStore`` class taking no arguments (credentials from
    the environment via ``secrets.load_local_env``).
    """
    try:
        from cycling_project.nightly import store as store_mod  # type: ignore
    except ImportError as exc:
        raise StoreUnavailable(
            "cycling_project/nightly/store.py is not present (sibling task); "
            "use --dry-run / --out-dir, or --store fake"
        ) from exc
    candidate: Any = store_mod
    for cls_name in ("SupabaseStore", "Store"):
        cls = getattr(store_mod, cls_name, None)
        if cls is not None:
            candidate = cls(role) if cls_name == "SupabaseStore" else cls()
            break
    missing = [name for name in _REQUIRED if not callable(getattr(candidate, name, None))]
    if missing:
        raise StoreUnavailable(
            "store.py lacks release calls: " + ", ".join(missing)
            + " — add them to the sibling client or run with --store fake"
        )
    return candidate


def resolve_store(kind: str = "hosted", root: Optional[Path] = None, role: str = "agent") -> Any:
    """``kind`` is ``hosted`` (Supabase via store.py, opened as ``role``) or ``fake`` (directory ``root``)."""
    if kind == "fake":
        if root is None:
            raise ValueError("--store fake needs --store-root")
        return FakeStore(root, role=role) if "role" in FakeStore.__init__.__code__.co_varnames else FakeStore(root)
    if kind != "hosted":
        raise ValueError(f"unknown store kind {kind!r}")
    return hosted_store(role)
