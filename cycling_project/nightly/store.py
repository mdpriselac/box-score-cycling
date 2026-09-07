"""Supabase control-plane client: PostgREST + Storage over ``requests``.

Spec: NIGHTLY_AGENT_WORKFLOW.md §1a / §2.12; schema in ``supabase/migrations``.

Roles (``SupabaseStore(role=…)``) pick the key from the environment:

    role        env var                        Postgres role   may
    ----------  ----------------------------   -------------   -------------------------------
    agent       SUPABASE_NIGHTLY_KEY           nightly_agent   insert ledger rows, read registry,
                                                               upload under its own run id
    reader      SUPABASE_RELEASE_READER_KEY    release_reader  read releases (table + bucket)
    operator    SUPABASE_SECRET_KEY            service_role    everything (the Mac only)

``SUPABASE_URL`` and ``SUPABASE_PUBLISHABLE_KEY`` (the gateway's ``apikey``,
not a secret) are read as well. Credentials come from
``cycling_project.nightly.secrets.load_local_env`` on the Mac; in the
Managed Agents container ``SUPABASE_NIGHTLY_KEY`` is a vault placeholder
substituted at egress, so the key travels in headers only — never in a URL,
query string or body (``_headers`` is the single place it is used).

Every write is an INSERT (``POST``); nothing here issues ``PATCH``/``DELETE``
except the operator-only ``upsert_crosswalk`` (human confirmation) — and the
database would refuse the agent key anyway.

Interfaces served (all three call the same thin transport):

* chip A (this module): ``start_run``, ``add_step``, ``insert_pcs_raw``,
  ``insert_prediction``, ``insert_prediction_log_rows``, ``insert_task``,
  ``insert_day_key``, ``insert_editorial_draft``, ``upload_artifact``,
  ``list_artifacts_since``, ``download_release``, ``approved_day_key``,
  ``approved_runs``;
* chip B ``release_store.ReleaseStore``: ``upload_release``, ``insert_release``,
  ``newest_approved_release``, ``get_release``, ``download_release_file``,
  ``list_artifacts_since``, ``download_artifact``;
* chip C ``store_local.JsonlStore``: ``insert``, ``insert_many``,
  ``insert_crosswalk_proposals``, ``insert_reconciliation``, ``upsert_crosswalk``.
* chip D weekly registry (operator only): ``sync_calendar``,
  ``sync_campaign``, ``sync_stages``. These can fill absent fields but never
  replace a known value.

``FakeStore`` implements the same surface in memory (optionally mirrored to
JSONL + a directory) and enforces the same role rules the database does, so
tests and ``--dry-run`` exercise the trust boundary without a network.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import mimetypes
import time
import os
import posixpath
import uuid
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Optional

import requests

from cycling_project.nightly import release_store as _rs
from cycling_project.nightly.secrets import load_local_env, redact
from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

RELEASES_BUCKET = _rs.RELEASES_BUCKET            # 'releases'
ARTIFACTS_BUCKET = _rs.ARTIFACTS_BUCKET          # 'nightly-artifacts'
STAGING_BUCKET = "site-staging"
SITE_BUCKET = "site"
MANIFEST_NAME = _rs.MANIFEST_NAME

ROLE_KEY_ENV = {
    "agent": "SUPABASE_NIGHTLY_KEY",
    "reader": "SUPABASE_RELEASE_READER_KEY",
    "operator": "SUPABASE_SECRET_KEY",
}

# What the agent role may insert, and the per-table conditions RLS enforces
# (0002_roles.sql). FakeStore checks the same so dry runs fail where prod would.
AGENT_INSERT_TABLES = frozenset({
    "runs", "run_steps", "pcs_raw", "predictions", "prediction_log",
    "day_key_decisions", "editorial_drafts", "operator_tasks", "crosswalk_proposals",
})
AGENT_SELECT_TABLES = frozenset({
    "calendar", "campaigns", "stages", "releases", "crosswalk", "approvals_view",
    "runs", "run_steps", "run_status", "predictions", "prediction_log", "day_key_decisions",
    "editorial_drafts", "operator_tasks", "crosswalk_proposals",
})
OPERATOR_ONLY_TABLES = frozenset({"calendar", "campaigns", "stages", "releases", "crosswalk",
                                  "approvals", "reconciliation", "operators"})

_PAGE = 500


class StoreError(RuntimeError):
    def __init__(self, message: str, status: Optional[int] = None, code: Optional[str] = None):
        super().__init__(redact(message))
        self.status = status
        self.code = code


class StorePermissionError(StoreError):
    """401/403: the role may not do this (grant or RLS)."""


class StoreConflictError(StoreError):
    """409: unique violation or an existing object (no overwrite)."""


def _utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _strip_none(row: Dict[str, Any]) -> Dict[str, Any]:
    """Missing keys take the column default; explicit nulls would not."""
    return {k: v for k, v in row.items() if v is not None}


def _normalise(table: str, row: Dict[str, Any]) -> Dict[str, Any]:
    """Map the JSONL-mirror shapes (store_local / crosswalk / reconcile) onto columns."""
    out = dict(row)
    if "campaign" in out and "campaign_slug" not in out:
        out["campaign_slug"] = out.pop("campaign")
    elif "campaign" in out:
        out.pop("campaign")
    out.pop("created_at", None)          # the database stamps it
    if table == "crosswalk_proposals":
        for k in ("confidence",):
            if isinstance(out.get(k), str):
                out[k] = float(out[k])
    if table == "crosswalk":
        for k in ("confidence", "internal_rider_id", "birth_year"):
            if out.get(k) in ("", None):
                out[k] = None
            elif k == "confidence":
                out[k] = float(out[k])
            else:
                out[k] = int(out[k])
        if not out.get("confirmed_by"):
            out["confirmed_by"] = None
    return _strip_none(out)


def _is_absent(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _fill_absent(existing: Dict[str, Any], proposed: Dict[str, Any]) -> Dict[str, Any]:
    """Return only fields that add information without replacing known data."""
    additions: Dict[str, Any] = {}
    for key, value in proposed.items():
        if key in {"id", "created_at", "updated_at"} or _is_absent(value):
            continue
        old = existing.get(key)
        if isinstance(old, dict) and isinstance(value, dict):
            nested = _fill_absent(old, value)
            if nested:
                additions[key] = {**old, **nested}
        elif key not in existing or _is_absent(old):
            additions[key] = value
    return additions


def artifact_key(run_id: str, path: str) -> str:
    """``<run_id>/<path>`` with ``path`` normalised; rejects escapes."""
    run_id = str(run_id)
    try:
        uuid.UUID(run_id)
    except ValueError as exc:
        raise ValueError(f"run_id is not a uuid: {run_id!r}") from exc
    rel = PurePosixPath(str(path).replace("\\", "/"))
    if rel.is_absolute() or not rel.parts or any(p in ("..", "") for p in rel.parts):
        raise ValueError(f"bad artifact path {path!r}")
    return f"{run_id}/{posixpath.normpath(str(rel))}"


def _is_api_key(key: str) -> bool:
    return key.startswith(("sb_secret_", "sb_publishable_"))


# ---------------------------------------------------------------------------
# hosted client
# ---------------------------------------------------------------------------

_UPLOAD_ATTEMPTS = 10  # transport retries per object (TLS resets on large uploads)
PART_SIZE = 8 * 1024 * 1024    # Supabase Storage caps objects at 50 MB on the free plan, and this
                                # Mac's uplink drops TLS on ~40 MB bodies ("bad record mac"); bigger
                                # release files are stored as <relpath>.partNNNN and reassembled.
PART_SUFFIX = ".part"


class SupabaseStore:
    """PostgREST + Storage client for one role. See the module docstring."""

    def __init__(self, role: str = "agent", *, url: Optional[str] = None, key: Optional[str] = None,
                 apikey: Optional[str] = None, timeout: float = 60.0,
                 session: Optional[requests.Session] = None):
        if role not in ROLE_KEY_ENV:
            raise ValueError(f"role must be one of {sorted(ROLE_KEY_ENV)}, not {role!r}")
        self.role = role
        if url is None or key is None:
            load_local_env()
        self.url = (url or os.environ.get("SUPABASE_URL", "")).rstrip("/")
        self._key = key or os.environ.get(ROLE_KEY_ENV[role], "")
        self._apikey = (apikey or os.environ.get("SUPABASE_PUBLISHABLE_KEY")
                        or os.environ.get("SUPABASE_ANON_KEY") or "")
        if not self.url or not self._key:
            raise StoreError(
                f"missing SUPABASE_URL or {ROLE_KEY_ENV[role]} for role {role!r} "
                "(see CLAUDE.md 'Credentials')")
        self.timeout = timeout
        self._s = session or requests.Session()

    # -- transport ------------------------------------------------------------
    def _headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """The only place the key is used. Header-only, per the vault contract."""
        if _is_api_key(self._key):
            # sb_secret_/sb_publishable_ keys go on `apikey`; the gateway maps them to a role.
            h = {"apikey": self._key}
        else:
            # A role JWT: Bearer for PostgREST/Storage, plus a publishable key for the gateway.
            h = {"apikey": self._apikey or self._key, "Authorization": f"Bearer {self._key}"}
        if extra:
            h.update(extra)
        return h

    def _raise(self, r: requests.Response, what: str) -> None:
        try:
            body = r.json()
        except ValueError:
            body = {"message": r.text[:300]}
        status = r.status_code
        if isinstance(body, dict):
            code = body.get("code") or body.get("error")
            msg = body.get("message") or body.get("error") or r.text[:300]
            hint = body.get("hint") or body.get("details")
            # Storage answers HTTP 400 and puts the real status in the body
            # ({"statusCode": "403", "error": "Unauthorized", "code": "AccessDenied"}).
            try:
                status = int(body.get("statusCode") or status)
            except (TypeError, ValueError):
                pass
        else:
            code, msg, hint = None, str(body)[:300], None
        text = f"{what}: HTTP {status} {msg}" + (f" ({hint})" if hint else "")
        code_s = str(code) if code else None
        if status in (401, 403) or code_s in ("42501", "AccessDenied"):
            raise StorePermissionError(text, status, code_s)
        if status == 409 or code_s in ("23505", "Duplicate", "KeyAlreadyExists"):
            raise StoreConflictError(text, status, code_s)
        raise StoreError(text, status, code_s)

    def _rest(self, method: str, table: str, *, params: Optional[Dict[str, str]] = None,
              json_body: Any = None, prefer: Optional[str] = None, what: str = "") -> requests.Response:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if prefer:
            headers["Prefer"] = prefer
        r = self._s.request(method, f"{self.url}/rest/v1/{table}", params=params, json=json_body,
                            headers=self._headers(headers), timeout=self.timeout)
        if r.status_code >= 400:
            self._raise(r, what or f"{method} {table}")
        return r

    def _select(self, table: str, params: Dict[str, str]) -> List[dict]:
        return self._rest("GET", table, params=params, what=f"select {table}").json()

    def _insert(self, table: str, rows: List[Dict[str, Any]], *, returning: bool = True,
                on_conflict: Optional[str] = None, ignore_duplicates: bool = False) -> List[dict]:
        if not rows:
            return []
        prefer = ["return=representation" if returning else "return=minimal"]
        if ignore_duplicates:
            prefer.append("resolution=ignore-duplicates")
        params = {"on_conflict": on_conflict} if on_conflict else None
        r = self._rest("POST", table, params=params, json_body=rows, prefer=",".join(prefer),
                       what=f"insert {table}")
        return r.json() if returning else []

    def _patch(self, table: str, params: Dict[str, str], values: Dict[str, Any]) -> List[dict]:
        if not values:
            return []
        return self._rest(
            "PATCH", table, params=params, json_body=values,
            prefer="return=representation", what=f"fill absent fields in {table}",
        ).json()

    def _rpc(self, name: str, args: Optional[Dict[str, Any]] = None) -> Any:
        return self._rest("POST", f"rpc/{name}", json_body=args or {}, what=f"rpc {name}").json()

    def _require_operator(self, what: str) -> None:
        if self.role != "operator":
            raise StorePermissionError(f"{what} needs the operator role (the Mac's secret key); "
                                       f"this store runs as {self.role!r}", 403)

    # -- storage transport ----------------------------------------------------
    def _upload(self, bucket: str, key: str, data: bytes, content_type: Optional[str] = None) -> str:
        """POST one object, never overwriting. Transport errors (TLS resets,
        connection drops — routine on a 600 MB weekly upload) are retried with
        backoff; HTTP errors are not."""
        headers = {"Content-Type": content_type or mimetypes.guess_type(key)[0] or "application/octet-stream",
                   "x-upsert": "false"}                       # never overwrite
        last: Optional[Exception] = None
        for attempt in range(1, _UPLOAD_ATTEMPTS + 1):
            try:
                r = self._s.post(f"{self.url}/storage/v1/object/{bucket}/{key}", data=data,
                                 headers=self._headers(headers), timeout=max(self.timeout, 600))
            except (requests.exceptions.SSLError, requests.exceptions.ConnectionError,
                    requests.exceptions.ChunkedEncodingError, requests.exceptions.Timeout) as exc:
                last = exc
                if attempt == _UPLOAD_ATTEMPTS:
                    raise
                self._s.close()          # drop the pooled connection that produced the bad record
                wait = min(5 * attempt, 45)
                logger.warning("upload %s/%s attempt %d failed (%s); retrying in %ds",
                               bucket, key, attempt, type(exc).__name__, wait)
                time.sleep(wait)
                continue
            if attempt > 1 and r.status_code == 400 and "already exists" in r.text.lower():
                return key                                    # a retry after a request that had landed
            if r.status_code >= 400:
                self._raise(r, f"upload {bucket}/{key}")
            return key
        raise last  # pragma: no cover

    def _download(self, bucket: str, key: str, dest: Path) -> Path:
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with self._s.get(f"{self.url}/storage/v1/object/authenticated/{bucket}/{key}",
                         headers=self._headers(), stream=True, timeout=max(self.timeout, 600)) as r:
            if r.status_code >= 400:
                self._raise(r, f"download {bucket}/{key}")
            tmp = dest.with_suffix(dest.suffix + ".part")
            with open(tmp, "wb") as fh:
                for chunk in r.iter_content(1 << 20):
                    fh.write(chunk)
            tmp.replace(dest)
        return dest

    def _list(self, bucket: str, prefix: str, recursive: bool = True) -> List[dict]:
        """Objects under ``prefix`` as ``{key, created_at, size}`` (folders expanded)."""
        out: List[dict] = []
        offset = 0
        while True:
            body = {"prefix": prefix, "limit": _PAGE, "offset": offset,
                    "sortBy": {"column": "name", "order": "asc"}}
            r = self._s.post(f"{self.url}/storage/v1/object/list/{bucket}", json=body,
                             headers=self._headers({"Content-Type": "application/json"}), timeout=self.timeout)
            if r.status_code >= 400:
                self._raise(r, f"list {bucket}/{prefix}")
            items = r.json()
            for it in items:
                name = it["name"]
                full = f"{prefix.rstrip('/')}/{name}" if prefix else name
                if it.get("id") is None:                      # a folder
                    if recursive:
                        out.extend(self._list(bucket, full, True))
                    continue
                meta = it.get("metadata") or {}
                out.append({"key": full, "created_at": it.get("created_at") or "",
                            "size": int(meta.get("size") or meta.get("contentLength") or 0)})
            if len(items) < _PAGE:
                break
            offset += _PAGE
        return out

    # -- diagnostics ----------------------------------------------------------
    def whoami(self) -> str:
        """Postgres role the key runs as (public.whoami())."""
        return self._rpc("whoami")

    # -- generic ledger (store_local.JsonlStore surface) ----------------------
    def insert(self, table: str, row: Dict[str, Any]) -> Dict[str, Any]:
        rows = self.insert_many(table, [row])
        return rows[0] if rows else _normalise(table, row)

    def insert_many(self, table: str, rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if self.role == "agent" and table not in AGENT_INSERT_TABLES:
            raise StorePermissionError(f"role 'agent' may not insert into {table!r}", 403)
        payload = [_normalise(table, r) for r in rows]
        returning = table in AGENT_SELECT_TABLES or self.role == "operator"
        out = self._insert(table, payload, returning=returning)
        return out if returning else payload

    def insert_crosswalk_proposals(self, rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return self.insert_many("crosswalk_proposals", rows)

    def insert_reconciliation(self, rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        self._require_operator("reconciliation rows")
        return self.insert_many("reconciliation", rows)

    def upsert_crosswalk(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Operator-only human confirmation: the one write that may replace a row."""
        self._require_operator("crosswalk confirmation")
        payload = _normalise("crosswalk", row)
        out = self._insert("crosswalk", [payload], returning=True, on_conflict="pcs_slug")
        # merge-duplicates is what an upsert needs; ignore-duplicates would keep the old row
        return out[0] if out else payload

    # -- runs -----------------------------------------------------------------
    def start_run(self, campaign_slug: Optional[str], unit: Optional[str], phase: str, *,
                  release_tag: Optional[str] = None, session_id: Optional[str] = None,
                  deployment: Optional[str] = None, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        row = _strip_none({"campaign_slug": campaign_slug, "unit": unit, "phase": phase,
                           "release_tag": release_tag, "session_id": session_id or os.environ.get("ANTHROPIC_SESSION_ID"),
                           "deployment": deployment, "meta": meta or {}})
        if self.role == "operator":
            row["host"] = "mac"
        return self._insert("runs", [row])[0]

    def add_step(self, run_id: str, step: str, state: str = "ok", *, started_at: Optional[str] = None,
                 finished_at: Optional[str] = None, duration_ms: Optional[int] = None,
                 exit_code: Optional[int] = None, detail: Optional[Dict[str, Any]] = None,
                 log_key: Optional[str] = None) -> Dict[str, Any]:
        row = _strip_none({"run_id": str(run_id), "step": step, "state": state, "started_at": started_at,
                           "finished_at": finished_at, "duration_ms": duration_ms, "exit_code": exit_code,
                           "detail": detail or {}, "log_key": log_key})
        return self._insert("run_steps", [row])[0]

    def finish_run(self, run_id: str, state: str = "ok", exit_code: int = 0,
                   detail: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Completion is a ``finish`` step (runs rows are never updated)."""
        return self.add_step(run_id, "finish", state, finished_at=_utcnow(), exit_code=exit_code, detail=detail)

    # -- acquisition / predictions -------------------------------------------
    def insert_pcs_raw(self, run_id: str, campaign_slug: Optional[str], unit: Optional[str], kind: str,
                       source_url: str, content: Optional[str] = None, *, object_key: Optional[str] = None,
                       ingest_verdict: Optional[str] = None, ingest_detail: Optional[Dict[str, Any]] = None,
                       fetched_at: Optional[str] = None) -> Dict[str, Any]:
        sha = hashlib.sha256(content.encode("utf-8")).hexdigest() if content is not None else None
        row = _strip_none({"run_id": str(run_id), "campaign_slug": campaign_slug, "unit": unit, "kind": kind,
                           "source_url": source_url, "content": content, "object_key": object_key,
                           "content_sha256": sha, "ingest_verdict": ingest_verdict,
                           "ingest_detail": ingest_detail or {}, "fetched_at": fetched_at})
        self._insert("pcs_raw", [row], returning=False)
        return row

    def insert_acquisition_raw(self, run_id: str, campaign_slug: Optional[str], unit: Optional[str], provider: str, kind: str,
                               source_url: str, content: Optional[str] = None, *, object_key: Optional[str] = None,
                               ingest_verdict: Optional[str] = None, ingest_detail: Optional[Dict[str, Any]] = None,
                               fetched_at: Optional[str] = None) -> Dict[str, Any]:
        """Provider-neutral raw-capture provenance. Until migration 0004 adds ``provider`` /
        ``acquisition_raw``, rows land in ``pcs_raw`` with ``kind = '<provider>:<kind>'`` for any
        provider other than PCS and ``ingest_detail.provider`` set — UCI data is never labelled PCS."""
        detail = {"provider": provider, **(ingest_detail or {})}
        row_kind = kind if provider == "pcs" else f"{provider}:{kind}"
        return self.insert_pcs_raw(run_id, campaign_slug, unit, row_kind, source_url, content, object_key=object_key,
                                   ingest_verdict=ingest_verdict, ingest_detail=detail, fetched_at=fetched_at)

    def insert_prediction(self, run_id: str, campaign_slug: str, unit: str, phase: str, *,
                          config: Optional[Dict[str, Any]] = None, board_key: Optional[str] = None,
                          target: Optional[str] = None, scenario_key: Optional[str] = None,
                          day_key: Optional[str] = None, model_version: Optional[str] = None,
                          summary: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        row = _strip_none({"run_id": str(run_id), "campaign_slug": campaign_slug, "unit": unit, "phase": phase,
                           "target": target, "scenario_key": scenario_key, "day_key": day_key,
                           "model_version": model_version, "config": config or {}, "board_key": board_key,
                           "summary": summary or {}})
        return self._insert("predictions", [row])[0]

    def insert_prediction_log_rows(self, rows: Iterable[Any], run_id: Optional[str] = None) -> int:
        """Rows are dicts (``PredictionLogRow.as_row()`` shape) or PredictionLogRow objects.

        Idempotent on ``(run_key, rider_id)`` like the SQLite table: duplicates
        are ignored server-side (the agent cannot update). Returns rows sent.
        """
        payload: List[Dict[str, Any]] = []
        for r in rows:
            d = r.as_row() if hasattr(r, "as_row") else dict(r)
            if run_id:
                d["run_id"] = str(run_id)
            payload.append(_strip_none(d))
        for i in range(0, len(payload), _PAGE):
            self._insert("prediction_log", payload[i:i + _PAGE], returning=False,
                         on_conflict="run_key,rider_id", ignore_duplicates=True)
        return len(payload)

    # -- inbox / decisions ----------------------------------------------------
    def insert_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """``build_operator_task`` shape: kind, campaign, summary, detail, urgency, author."""
        return self.insert("operator_tasks", task)

    def insert_day_key(self, campaign_slug: str, unit: str, day_key: str, *, author: str = "agent",
                       run_id: Optional[str] = None, family: Optional[str] = None,
                       confidence: Optional[float] = None, rationale: Optional[str] = None,
                       evidence: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        row = _strip_none({"campaign_slug": campaign_slug, "unit": unit, "day_key": day_key, "author": author,
                           "run_id": str(run_id) if run_id else None, "family": family,
                           "confidence": confidence, "rationale": rationale, "evidence": evidence or {}})
        return self._insert("day_key_decisions", [row])[0]

    def insert_editorial_draft(self, run_id: Optional[str], campaign_slug: str, unit: str, phase: str,
                               body_md: str, *, kind: str = "prose", author: str = "agent",
                               lint: Optional[Dict[str, Any]] = None, lint_ok: Optional[bool] = None) -> Dict[str, Any]:
        row = _strip_none({"run_id": str(run_id) if run_id else None, "campaign_slug": campaign_slug,
                           "unit": unit, "phase": phase, "kind": kind, "author": author, "body_md": body_md,
                           "lint": lint or {}, "lint_ok": lint_ok})
        return self._insert("editorial_drafts", [row])[0]

    def approved_day_key(self, campaign_slug: str, unit: str) -> Optional[Dict[str, Any]]:
        """The newest human-approved key for a unit, or None."""
        rows = self._select("day_key_decisions", {
            "campaign_slug": f"eq.{campaign_slug}", "unit": f"eq.{unit}", "approved_by": "not.is.null",
            "order": "approved_at.desc,id.desc", "limit": "1"})
        return rows[0] if rows else None

    def approved_runs(self, campaign_slug: Optional[str] = None, kind: Optional[str] = None) -> List[Dict[str, Any]]:
        """Approval rows (agent-safe projection), newest first."""
        params = {"decision": "eq.approve", "order": "created_at.desc"}
        if campaign_slug:
            params["campaign_slug"] = f"eq.{campaign_slug}"
        if kind:
            params["kind"] = f"eq.{kind}"
        return self._select("approvals_view", params)

    def open_tasks(self, campaign_slug: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {"resolved": "eq.false", "order": "created_at.desc"}
        if campaign_slug:
            params["campaign_slug"] = f"eq.{campaign_slug}"
        return self._select("operator_tasks", params)

    # -- registry reads -------------------------------------------------------
    def campaigns(self, active_only: bool = True) -> List[Dict[str, Any]]:
        params = {"order": "start_date.asc"}
        if active_only:
            params["active"] = "eq.true"
        return self._select("campaigns", params)

    def stages(self, campaign_slug: str) -> List[Dict[str, Any]]:
        return self._select("stages", {"campaign_slug": f"eq.{campaign_slug}", "order": "stage_number.asc.nullslast"})

    # -- weekly registry writes (operator only) ------------------------------
    def sync_calendar(self, rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Insert calendar rows or fill null/empty fields; never replace facts."""
        self._require_operator("calendar sync")
        out = []
        for raw in rows:
            row = _normalise("calendar", raw)
            found = self._select("calendar", {
                "fc_race_id": f"eq.{row['fc_race_id']}", "year": f"eq.{row['year']}", "limit": "1",
            })
            if not found:
                out.append(self._insert("calendar", [row])[0])
                continue
            additions = _fill_absent(found[0], row)
            changed = self._patch("calendar", {
                "fc_race_id": f"eq.{row['fc_race_id']}", "year": f"eq.{row['year']}",
            }, additions)
            out.append(changed[0] if changed else found[0])
        return out

    def sync_campaign(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Insert one campaign or fill only fields that were previously absent."""
        self._require_operator("campaign sync")
        payload = _normalise("campaigns", row)
        slug = payload["campaign_slug"]
        found = self._select("campaigns", {"campaign_slug": f"eq.{slug}", "limit": "1"})
        if not found:
            return self._insert("campaigns", [payload])[0]
        additions = _fill_absent(found[0], payload)
        changed = self._patch("campaigns", {"campaign_slug": f"eq.{slug}"}, additions)
        return changed[0] if changed else found[0]

    def sync_stages(self, rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Insert stage rows or fill only fields that were previously absent."""
        self._require_operator("stage sync")
        out = []
        for raw in rows:
            row = _normalise("stages", raw)
            found = self._select("stages", {
                "campaign_slug": f"eq.{row['campaign_slug']}", "unit": f"eq.{row['unit']}", "limit": "1",
            })
            if not found:
                out.append(self._insert("stages", [row])[0])
                continue
            additions = _fill_absent(found[0], row)
            changed = self._patch("stages", {
                "campaign_slug": f"eq.{row['campaign_slug']}", "unit": f"eq.{row['unit']}",
            }, additions)
            out.append(changed[0] if changed else found[0])
        return out

    # -- artifacts (nightly-artifacts / site-staging) -------------------------
    def upload_artifact(self, run_id: str, path: str, data: bytes, *, bucket: str = ARTIFACTS_BUCKET,
                        content_type: Optional[str] = None) -> str:
        """Insert-only upload of ``<run_id>/<path>``; returns the object key."""
        if bucket not in (ARTIFACTS_BUCKET, STAGING_BUCKET):
            raise ValueError(f"agent uploads go to {ARTIFACTS_BUCKET} or {STAGING_BUCKET}, not {bucket!r}")
        key = artifact_key(run_id, path)
        return self._upload(bucket, key, data, content_type)

    def list_artifacts_since(self, release_tag: str) -> List[dict]:
        """``{key, created_at, size}`` for every artifact of a run started at/after the release."""
        release = self.get_release(release_tag)
        since = release.get("created_at", "") if release else ""
        params = {"select": "run_id,created_at", "order": "created_at.asc"}
        if since:
            params["created_at"] = f"gte.{since}"
        out: List[dict] = []
        for run in self._select("runs", params):
            out.extend(self._list(ARTIFACTS_BUCKET, str(run["run_id"]), recursive=True))
        return sorted(out, key=lambda o: (o["created_at"], o["key"]))

    def download_artifact(self, key: str, dest: Path) -> Path:
        return self._download(ARTIFACTS_BUCKET, key, Path(dest))

    # -- releases (release_store.ReleaseStore surface) ------------------------
    def get_release(self, tag: str) -> Optional[dict]:
        rows = self._select("releases", {"tag": f"eq.{tag}", "limit": "1"})
        return rows[0] if rows else None

    def newest_approved_release(self) -> Optional[dict]:
        rows = self._select("releases", {"approved": "eq.true", "order": "created_at.desc,tag.desc", "limit": "1"})
        return rows[0] if rows else None

    def insert_release(self, row: dict) -> dict:
        self._require_operator("insert_release")
        payload = _strip_none({**row, "approved": bool(row.get("approved", False))})
        return self._insert("releases", [payload])[0]

    def upload_release(self, tag: str, bundle_dir: Path, manifest: dict) -> List[str]:
        """Mac only. Objects are never overwritten: a tag is immutable once uploaded."""
        self._require_operator("upload_release")
        bundle_dir = Path(bundle_dir)
        present = {o["key"] for o in self._list(RELEASES_BUCKET, tag, recursive=True)}
        if f"{tag}/{MANIFEST_NAME}" in present or MANIFEST_NAME in present:
            raise StoreConflictError(f"release {tag} is complete under {RELEASES_BUCKET}/{tag}/ "
                                     "(manifest present); a tag is immutable once uploaded", 409)
        keys: List[str] = []
        for relpath in sorted(manifest["files"]):
            key = f"{tag}/{relpath}"
            path = bundle_dir / relpath
            if path.stat().st_size > PART_SIZE:
                # chunked: <key>.part0000, .part0001, ... (each under the object cap)
                with open(path, "rb") as fh:
                    n = 0
                    while True:
                        chunk = fh.read(PART_SIZE)
                        if not chunk:
                            break
                        pkey = f"{key}{PART_SUFFIX}{n:04d}"
                        if pkey in present:
                            logger.info("resume: %s already uploaded, skipping", pkey)
                        else:
                            self._upload(RELEASES_BUCKET, pkey, chunk, "application/octet-stream")
                        keys.append(f"{RELEASES_BUCKET}/{pkey}")
                        n += 1
                continue
            if key in present or relpath in present:
                logger.info("resume: %s already uploaded, skipping", key)
            else:
                self._upload(RELEASES_BUCKET, key, path.read_bytes())
            keys.append(f"{RELEASES_BUCKET}/{key}")
        self._upload(RELEASES_BUCKET, f"{tag}/{MANIFEST_NAME}",
                     json.dumps(manifest, indent=2, sort_keys=True).encode(), "application/json")
        keys.append(f"{RELEASES_BUCKET}/{tag}/{MANIFEST_NAME}")
        logger.info("uploaded release %s: %d objects", tag, len(keys))
        return keys

    def download_release_file(self, tag: str, relpath: str, dest: Path) -> Path:
        """One bundle file; transparently reassembles a chunked upload."""
        dest = Path(dest)
        key = f"{tag}/{relpath}"
        # The Storage list API takes a FOLDER prefix, not a filename prefix:
        # list the parent folder and pick the <name>.partNNNN siblings.
        folder = key.rsplit("/", 1)[0] if "/" in key else ""
        parts = sorted(o["key"] for o in self._list(RELEASES_BUCKET, folder, recursive=False)
                       if o["key"].startswith(key + PART_SUFFIX))
        if not parts:
            return self._download(RELEASES_BUCKET, key, dest)
        expected = [f"{key}{PART_SUFFIX}{i:04d}" for i in range(len(parts))]
        if parts != expected:
            raise StoreError(f"chunked object {key} is incomplete or misnumbered: {parts}", 409)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as out:
            for pkey in parts:
                piece = self._download(RELEASES_BUCKET, pkey, tmp.with_suffix(".piece"))
                out.write(piece.read_bytes())
                piece.unlink()
        tmp.replace(dest)
        return dest

    def download_release(self, tag: str, dest: Path) -> Path:
        """The whole bundle (manifest + every listed file) into ``dest``."""
        dest = Path(dest)
        manifest_path = self.download_release_file(tag, MANIFEST_NAME, dest / MANIFEST_NAME)
        manifest = json.loads(manifest_path.read_text())
        for relpath in sorted(manifest["files"]):
            self.download_release_file(tag, relpath, dest / relpath)
        return dest


Store = SupabaseStore          # store_local.open_store(kind='supabase') looks for `Store(role=…)`


# ---------------------------------------------------------------------------
# fake
# ---------------------------------------------------------------------------

class FakeStore(_rs.FakeStore):
    """In-memory/on-disk stand-in with the hosted client's surface AND its rules.

    ``role`` follows the hosted client ('agent' | 'reader' | 'operator'); the
    checks mirror 0002_roles.sql / 0003_storage.sql: agent inserts only into
    the ledger tables and never with approval/resolution fields set; artifact
    keys must start with a run it started; nothing is ever overwritten.
    Ledger rows live in ``rows[table]`` and, when ``root`` is given, are
    appended to ``<root>/ledger/<table>.jsonl``.
    """

    def __init__(self, root: Optional[Path] = None, role: str = "agent"):
        self._tmp = None
        if root is None:
            import tempfile
            self._tmp = tempfile.TemporaryDirectory(prefix="fakestore-")
            root = Path(self._tmp.name)
        super().__init__(Path(root))
        if role not in ROLE_KEY_ENV:
            raise ValueError(f"role must be one of {sorted(ROLE_KEY_ENV)}, not {role!r}")
        self.role = role
        self.rows: Dict[str, List[Dict[str, Any]]] = {}
        self.ledger_dir = self.root / "ledger"
        self.staging_dir = self.root / STAGING_BUCKET
        self._seq: Dict[str, int] = {}
        self._load_ledger()

    def _load_ledger(self) -> None:
        """Rows appended by earlier processes (a human approval, a previous run) stay visible."""
        if not self.ledger_dir.is_dir():
            return
        for path in sorted(self.ledger_dir.glob("*.jsonl")):
            table = path.stem
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                self.rows.setdefault(table, []).append(record)
                try:
                    self._seq[table] = max(self._seq.get(table, 0), int(record.get("id") or 0))
                except (TypeError, ValueError):
                    pass

    # -- helpers --------------------------------------------------------------
    def _deny(self, msg: str) -> None:
        raise StorePermissionError(msg, 403)

    def _append(self, table: str, row: Dict[str, Any]) -> Dict[str, Any]:
        self._seq[table] = self._seq.get(table, 0) + 1
        record = {"id": self._seq[table], "created_at": _utcnow(), **row}
        self.rows.setdefault(table, []).append(record)
        self.ledger_dir.mkdir(parents=True, exist_ok=True)
        with open(self.ledger_dir / f"{table}.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True, default=str) + "\n")
        return record

    def _check_agent_row(self, table: str, row: Dict[str, Any]) -> None:
        if table in ("day_key_decisions", "editorial_drafts"):
            if row.get("approved_by") or row.get("approved_at") or row.get("author") == "human":
                self._deny(f"agent may not insert an approved/human row into {table}")
        if table == "operator_tasks" and (row.get("resolved") or row.get("resolved_by") or row.get("resolution")):
            self._deny("agent may not insert a resolved operator task")
        if table == "crosswalk_proposals" and (row.get("status", "proposed") != "proposed" or row.get("resolved_by")):
            self._deny("agent proposals must be status=proposed")
        if table == "runs" and row.get("host", "cloud") != "cloud":
            self._deny("agent runs are host=cloud")
        if table == "run_steps" and not any(r["run_id"] == row.get("run_id") for r in self.rows.get("runs", [])):
            raise StoreError(f"run_steps.run_id {row.get('run_id')} violates the foreign key", 409, "23503")

    def whoami(self) -> str:
        return {"agent": "nightly_agent", "reader": "release_reader", "operator": "service_role"}[self.role]

    # -- generic ledger ---------------------------------------------------------
    def insert(self, table: str, row: Dict[str, Any]) -> Dict[str, Any]:
        return self.insert_many(table, [row])[0]

    def insert_many(self, table: str, rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if self.role == "reader":
            self._deny("release_reader cannot insert")
        if self.role == "agent" and table not in AGENT_INSERT_TABLES:
            self._deny(f"role 'agent' may not insert into {table!r}")
        out = []
        for r in rows:
            row = _normalise(table, r)
            if self.role == "agent":
                self._check_agent_row(table, row)
            if table == "prediction_log" and row.get("run_key") is not None and any(
                    x.get("run_key") == row["run_key"] and x.get("rider_id") == row.get("rider_id")
                    for x in self.rows.get("prediction_log", [])):
                continue                                             # ignore-duplicates
            out.append(self._append(table, row))
        return out

    def insert_crosswalk_proposals(self, rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return self.insert_many("crosswalk_proposals", rows)

    def insert_reconciliation(self, rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if self.role != "operator":
            self._deny("reconciliation rows need the operator role")
        return self.insert_many("reconciliation", rows)

    def upsert_crosswalk(self, row: Dict[str, Any]) -> Dict[str, Any]:
        if self.role != "operator":
            self._deny("crosswalk confirmation requires the operator role; the nightly agent key can only propose")
        payload = _normalise("crosswalk", row)
        table = self.rows.setdefault("crosswalk", [])
        table[:] = [r for r in table if r.get("pcs_slug") != payload.get("pcs_slug")]
        return self._append("crosswalk", payload)

    # -- runs etc. (same signatures as the hosted client) -----------------------
    def start_run(self, campaign_slug, unit, phase, *, release_tag=None, session_id=None, deployment=None, meta=None):
        row = _strip_none({"run_id": str(uuid.uuid4()), "campaign_slug": campaign_slug, "unit": unit, "phase": phase,
                           "state": "started", "release_tag": release_tag, "session_id": session_id,
                           "deployment": deployment, "host": "mac" if self.role == "operator" else "cloud",
                           "started_at": _utcnow(), "meta": meta or {}})
        return self.insert("runs", row)

    def add_step(self, run_id, step, state="ok", *, started_at=None, finished_at=None, duration_ms=None,
                 exit_code=None, detail=None, log_key=None):
        return self.insert("run_steps", _strip_none({
            "run_id": str(run_id), "step": step, "state": state, "started_at": started_at, "finished_at": finished_at,
            "duration_ms": duration_ms, "exit_code": exit_code, "detail": detail or {}, "log_key": log_key}))

    def finish_run(self, run_id, state="ok", exit_code=0, detail=None):
        return self.add_step(run_id, "finish", state, finished_at=_utcnow(), exit_code=exit_code, detail=detail)

    def insert_pcs_raw(self, run_id, campaign_slug, unit, kind, source_url, content=None, *, object_key=None,
                       ingest_verdict=None, ingest_detail=None, fetched_at=None):
        sha = hashlib.sha256(content.encode("utf-8")).hexdigest() if content is not None else None
        return self.insert("pcs_raw", _strip_none({
            "run_id": str(run_id), "campaign_slug": campaign_slug, "unit": unit, "kind": kind, "source_url": source_url,
            "content": content, "object_key": object_key, "content_sha256": sha, "ingest_verdict": ingest_verdict,
            "ingest_detail": ingest_detail or {}, "fetched_at": fetched_at or _utcnow()}))

    def insert_acquisition_raw(self, run_id, campaign_slug, unit, provider, kind, source_url, content=None, *, object_key=None,
                               ingest_verdict=None, ingest_detail=None, fetched_at=None):
        detail = {"provider": provider, **(ingest_detail or {})}
        row_kind = kind if provider == "pcs" else f"{provider}:{kind}"
        return self.insert_pcs_raw(run_id, campaign_slug, unit, row_kind, source_url, content, object_key=object_key,
                                   ingest_verdict=ingest_verdict, ingest_detail=detail, fetched_at=fetched_at)

    def insert_prediction(self, run_id, campaign_slug, unit, phase, *, config=None, board_key=None, target=None,
                          scenario_key=None, day_key=None, model_version=None, summary=None):
        return self.insert("predictions", _strip_none({
            "run_id": str(run_id), "campaign_slug": campaign_slug, "unit": unit, "phase": phase, "target": target,
            "scenario_key": scenario_key, "day_key": day_key, "model_version": model_version, "config": config or {},
            "board_key": board_key, "summary": summary or {}}))

    def insert_prediction_log_rows(self, rows, run_id=None) -> int:
        payload = []
        for r in rows:
            d = r.as_row() if hasattr(r, "as_row") else dict(r)
            if run_id:
                d["run_id"] = str(run_id)
            payload.append(d)
        self.insert_many("prediction_log", payload)
        return len(payload)

    def insert_task(self, task):
        return self.insert("operator_tasks", task)

    def insert_day_key(self, campaign_slug, unit, day_key, *, author="agent", run_id=None, family=None,
                       confidence=None, rationale=None, evidence=None):
        return self.insert("day_key_decisions", _strip_none({
            "campaign_slug": campaign_slug, "unit": unit, "day_key": day_key, "author": author,
            "run_id": str(run_id) if run_id else None, "family": family, "confidence": confidence,
            "rationale": rationale, "evidence": evidence or {}}))

    def insert_editorial_draft(self, run_id, campaign_slug, unit, phase, body_md, *, kind="prose", author="agent",
                               lint=None, lint_ok=None):
        return self.insert("editorial_drafts", _strip_none({
            "run_id": str(run_id) if run_id else None, "campaign_slug": campaign_slug, "unit": unit, "phase": phase,
            "kind": kind, "author": author, "body_md": body_md, "lint": lint or {}, "lint_ok": lint_ok}))

    # human actions, exposed for tests (the dashboard in production)
    def approve_day_key(self, campaign_slug, unit, day_key, by="test"):
        if self.role != "operator":
            self._deny("approving a day key is a human action")
        return self._append("day_key_decisions", {"campaign_slug": campaign_slug, "unit": unit, "day_key": day_key,
                                                  "author": "human", "approved_by": by, "approved_at": _utcnow()})

    def approve_run(self, run_id, by="test", kind="publish", note=None):
        if self.role != "operator":
            self._deny("approvals are human-only")
        return self._append("approvals", {"run_id": str(run_id), "kind": kind, "decision": "approve",
                                          "approved_by": by, "note": note})

    def approved_day_key(self, campaign_slug, unit):
        rows = [r for r in self.rows.get("day_key_decisions", [])
                if r.get("campaign_slug") == campaign_slug and r.get("unit") == unit and r.get("approved_by")]
        return max(rows, key=lambda r: (r.get("approved_at", ""), r["id"])) if rows else None

    def approved_runs(self, campaign_slug=None, kind=None):
        out = []
        for r in self.rows.get("approvals", []):
            if r.get("decision", "approve") != "approve":
                continue
            if campaign_slug and r.get("campaign_slug") != campaign_slug:
                continue
            if kind and r.get("kind") != kind:
                continue
            out.append({k: v for k, v in r.items() if k not in ("approved_by", "private_note")})
        return sorted(out, key=lambda r: r["created_at"], reverse=True)

    def open_tasks(self, campaign_slug=None):
        return [r for r in self.rows.get("operator_tasks", [])
                if not r.get("resolved") and (campaign_slug is None or r.get("campaign_slug") == campaign_slug)]

    def campaigns(self, active_only=True):
        return [r for r in self.rows.get("campaigns", []) if not active_only or r.get("active", True)]

    def stages(self, campaign_slug):
        return [r for r in self.rows.get("stages", []) if r.get("campaign_slug") == campaign_slug]

    def _sync_registry_row(self, table, row, keys):
        if self.role != "operator":
            self._deny(f"{table} sync needs the operator role")
        payload = _normalise(table, row)
        found = next((r for r in self.rows.get(table, [])
                      if all(r.get(k) == payload.get(k) for k in keys)), None)
        if found is None:
            return self._append(table, payload)
        additions = _fill_absent(found, payload)
        found.update(additions)
        return found

    def sync_calendar(self, rows):
        return [self._sync_registry_row("calendar", row, ("fc_race_id", "year")) for row in rows]

    def sync_campaign(self, row):
        return self._sync_registry_row("campaigns", row, ("campaign_slug",))

    def sync_stages(self, rows):
        return [self._sync_registry_row("stages", row, ("campaign_slug", "unit")) for row in rows]

    # -- storage ----------------------------------------------------------------
    def upload_artifact(self, run_id, path, data: bytes, *, bucket: str = ARTIFACTS_BUCKET, content_type=None) -> str:
        if self.role == "reader":
            self._deny("release_reader cannot upload")
        if bucket not in (ARTIFACTS_BUCKET, STAGING_BUCKET):
            raise ValueError(f"agent uploads go to {ARTIFACTS_BUCKET} or {STAGING_BUCKET}, not {bucket!r}")
        key = artifact_key(run_id, path)
        if self.role == "agent" and not any(r["run_id"] == str(run_id) for r in self.rows.get("runs", [])):
            self._deny(f"object key must start with a run_id in runs: {key}")
        if bucket == STAGING_BUCKET:
            target = self.staging_dir / key
            if target.exists():
                raise StoreConflictError(f"object exists: {STAGING_BUCKET}/{key}", 409)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            return key
        try:
            return self.put_artifact(key, data)
        except ValueError as exc:                                    # release_store's "object exists"
            raise StoreConflictError(str(exc), 409) from exc

    def upload_release(self, tag, bundle_dir, manifest):
        if self.role != "operator":
            self._deny("upload_release is the Mac's job (operator role)")
        try:
            return super().upload_release(tag, bundle_dir, manifest)
        except ValueError as exc:
            raise StoreConflictError(str(exc), 409) from exc

    def insert_release(self, row):
        if self.role != "operator":
            self._deny("insert_release needs the operator role")
        try:
            return super().insert_release(row)
        except ValueError as exc:
            raise StoreConflictError(str(exc), 409) from exc

    def download_release(self, tag, dest):
        dest = Path(dest)
        manifest = json.loads(self.download_release_file(tag, MANIFEST_NAME, dest / MANIFEST_NAME).read_text())
        for relpath in sorted(manifest["files"]):
            self.download_release_file(tag, relpath, dest / relpath)
        return dest

    def list_artifacts_since(self, release_tag):
        if self.role == "reader":
            self._deny("release_reader cannot list artifacts")
        return super().list_artifacts_since(release_tag)

    def download_artifact(self, key, dest):
        if self.role == "reader":
            self._deny("release_reader cannot read artifacts")
        return super().download_artifact(key, dest)
