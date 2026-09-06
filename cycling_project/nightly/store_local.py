"""Local, file-backed stand-in for the Supabase control-plane client.

The real client (``cycling_project/nightly/store.py``, a sibling task) speaks
PostgREST with a role-scoped key. Until it lands — and always for tests and
``--dry-run`` — the crosswalk and reconciliation tools write the same row
shapes (NIGHTLY_AGENT_WORKFLOW.md §2.12) to append-only JSONL mirrors under
``performance_eval/runs/``.

Two roles are modelled so tests can prove the trust boundary:

* ``agent``    may only *insert* into ``crosswalk_proposals``, ``operator_tasks``
               and ``reconciliation`` (append-only ledger tables).
* ``operator`` may additionally *upsert* ``crosswalk`` rows (the human
               confirmation path). This is the only method that mutates.

``JsonlStore.upsert_crosswalk`` raises ``PermissionError`` for the agent
role — the same outcome Postgres RLS produces for ``nightly_agent``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

AGENT_INSERT_TABLES = frozenset({"crosswalk_proposals", "operator_tasks", "reconciliation"})


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class JsonlStore:
    """Append-only JSONL mirror of the control-plane tables.

    ``runs_dir`` is normally ``performance_eval/runs``. Every insert appends
    one JSON object per line to ``<table>.jsonl`` and to the in-memory
    ``rows`` dict (handy for assertions). ``role`` gates the mutating path.
    """

    runs_dir: Optional[Path] = None
    role: str = "agent"
    rows: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    # -- generic append-only ledger -------------------------------------
    def insert(self, table: str, row: dict[str, Any]) -> dict[str, Any]:
        if self.role == "agent" and table not in AGENT_INSERT_TABLES:
            raise PermissionError(f"role 'agent' may not insert into {table!r}")
        record = {"created_at": utcnow_iso(), **row}
        self.rows.setdefault(table, []).append(record)
        if self.runs_dir is not None:
            self.runs_dir.mkdir(parents=True, exist_ok=True)
            with open(self.runs_dir / f"{table}.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        return record

    def insert_many(self, table: str, rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.insert(table, r) for r in rows]

    # -- named helpers matching the §2.12 tables -------------------------
    def insert_crosswalk_proposals(self, rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        return self.insert_many("crosswalk_proposals", rows)

    def insert_task(self, task: dict[str, Any]) -> dict[str, Any]:
        return self.insert("operator_tasks", task)

    def insert_reconciliation(self, rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        return self.insert_many("reconciliation", rows)

    # -- the ONE mutating path: human confirmation -----------------------
    def upsert_crosswalk(self, row: dict[str, Any]) -> dict[str, Any]:
        """Operator-only. Inserts/replaces the ``crosswalk`` row for a slug."""
        if self.role != "operator":
            raise PermissionError(
                "crosswalk confirmation requires the operator role; "
                "the nightly agent key can only propose"
            )
        record = {"created_at": utcnow_iso(), **row}
        table = self.rows.setdefault("crosswalk", [])
        table[:] = [r for r in table if r.get("pcs_slug") != row.get("pcs_slug")]
        table.append(record)
        if self.runs_dir is not None:
            self.runs_dir.mkdir(parents=True, exist_ok=True)
            with open(self.runs_dir / "crosswalk_confirmations.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        return record


def open_store(kind: str, runs_dir: Optional[Path], role: str = "agent"):
    """Return a store for ``kind`` in {'local', 'none', 'supabase'}.

    ``supabase`` requires the sibling ``store.py``; if it is absent we fall
    back to the local mirror with a warning so the Mac-side commands still
    leave an auditable trail.
    """
    if kind == "none":
        return JsonlStore(runs_dir=None, role=role)
    if kind == "supabase":
        try:
            from cycling_project.nightly import store as _store  # type: ignore
        except ImportError:
            logger.warning("cycling_project.nightly.store not present; using the local JSONL mirror")
            return JsonlStore(runs_dir=runs_dir, role=role)
        factory = getattr(_store, "Store", None)
        if factory is None:
            logger.warning("store.Store missing; using the local JSONL mirror")
            return JsonlStore(runs_dir=runs_dir, role=role)
        return factory(role=role)  # pragma: no cover - needs credentials
    return JsonlStore(runs_dir=runs_dir, role=role)
