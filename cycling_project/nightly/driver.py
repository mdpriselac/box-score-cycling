"""``python -m cycling_project.nightly <command>`` — the daily runbook as code.

Spec: NIGHTLY_AGENT_WORKFLOW.md §2.2 (commands), §2.8 (ingest) and
``performance_eval/DAILY_RUNBOOK.md`` (the process; its §4 and §5 name each
command beside the manual step it replaces). The driver
is deterministic and idempotent on ``(campaign, unit, phase)``. Prospective
judgment (day keys, scenario references, prose, route overrides) is never
produced here — when it is missing the driver stops with exit 10 and an
operator task. It may, however, *consume* judgment another agent produced: a
day-key record left at ``predictions/<unit>/agent_key.json`` prices the board
when no human key has been approved, stamped ``day_key_author: agent`` so the
page and the scorer both know no person wrote it (2026-09-17). Publication
stays gated on a human approval in ``promote.py``.

Exit codes: ``0`` done · ``10`` waiting for input (``operator_task`` in the
JSON) · ``20`` failed (``error_class``, ``step``, ``log_path``). Every run
and step is recorded through ``store.start_run`` / ``add_step`` /
``finish_run`` and mirrored to ``performance_eval/<campaign>/runs/<date>/``.
Prospective judgment is never invented by the driver; after settlement, a
missed preview may be reconstructed from the result oracle and is permanently
marked post-hoc. Existing scripts are subprocessed unchanged (``PYTHONUNBUFFERED=1``, logs
captured); SQLite-writing steps take a global file lock.

There is no ``publish`` or ``commit`` command and no git operation anywhere
in this module (``assert_no_git`` guards every subprocess).

Commands: ``bootstrap`` · ``plan`` · ``night`` · ``settle`` · ``preview`` · ``acquire`` ·
``ingest`` · ``bundle`` · ``refs`` · ``validate`` · ``upload`` · ``editorial`` · ``status``.
``--dry-run`` everywhere: no fetch, ``--no-log``, a ``FakeStore``, scripts
recorded but not executed.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import datetime as dt
import fcntl
import json
import math
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import traceback
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from cycling_project.db_path import ENV_VAR as DB_ENV_VAR, default_db_path
from cycling_project.nightly import day_key_record as rec
from cycling_project.nightly import autoconfig, hindsight, oneday, pcs_ingest, route_research, site_paths, tiers, uci_acquire, uci_identity, uci_ingest
from cycling_project.nightly.crosswalk import CROSSWALK_CSV, build_operator_task, read_crosswalk_csv
from cycling_project.nightly.secrets import load_local_env, redact
from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PERF_EVAL = PROJECT_ROOT / "performance_eval"
TDF_TOOLS = PERF_EVAL / "tour-de-france-2026"
SITE_BUILD = PROJECT_ROOT / "netlify_site" / "build"
SITE_DIR = PROJECT_ROOT / "netlify_site"
SCRIPTS = {
    "seed_state_cache": TDF_TOOLS / "seed_state_cache.py",
    "capture_odds": TDF_TOOLS / "capture_odds.py",
    "predict": SITE_BUILD / "predict_stage_scenarios.py",
    "gc_tracker": SITE_BUILD / "build_gc_tracker.py",
    "stage_page": SITE_BUILD / "build_stage_page.py",
    "oneday_page": SITE_BUILD / "build_oneday_page.py",
    "site_index": SITE_BUILD / "build_site_index.py",
    "site_frame": SITE_BUILD / "build_site_frame.py",
    "score_day_keys": PERF_EVAL / "vuelta-2026" / "score_day_keys.py",
}

EXIT_DONE, EXIT_WAITING, EXIT_FAILED = 0, 10, 20
# A campaign whose last unit is older than this is finished: nothing is due, ever.  (2026-09-08: the
# Tour's config-only hydration made its 21 July stages "due" every night.)  The window is wider
# than the release bundle's 3-day grace so a race that ended a few days before its first agent
# night (Tour of Britain) still settles late.
FINISHED_AFTER_DAYS = 7
# Kambi does not list most .1 / .Pro races.  Only a WorldTour preview waits on a market match;
# elsewhere a missing book is recorded and the preview goes on without the benchmark columns.
ODDS_REQUIRED_CATEGORIES = ("wt",)


def odds_required(category: Optional[str]) -> bool:
    return str(category or "").lower() in ODDS_REQUIRED_CATEGORIES
PHASES_UNIT = ("settle", "preview", "acquire", "ingest", "bundle", "validate", "upload")
ONE_DAY_UNIT = "race"
TEMPLATE_NAME = "TEMPLATE_scenarios.json"
COMPLETED_INDEX = "completed.json"
FAKESTORE_DIRNAME = "fakestore"
LAMBDARANK_SUM_TOL = 0.02
COVERAGE_WARN, COVERAGE_FAIL = 0.99, 0.90
STATE_SENTENCE_RE = re.compile(r"State through stage \d+", re.I)
# A stage is due to settle only once its own RACE-LOCAL day is over, and it stays previewable
# while that day has not begun.  The tick is a fixed UTC hour, so a race far east of UTC is
# already "tomorrow" when it fires: at 19:45 UTC on 2026-09-17 it was 03:45 on the 18th in
# Shanghai, and Tour of Huangshan stage 1 (dated the 18th) was listed as settle-due — an
# acquisition ask for a stage nobody had ridden (hosted task 88, 2026-09-17).  Between the two
# hours the race is on the road: neither a settle nor an honest preview.
RACE_DAY_OVER_HOUR = 18
RACE_DAY_START_HOUR = 9


def day_is_over(day: dt.date, now: dt.datetime) -> bool:
    """True once ``day`` has finished on the race-local clock ``now``: a past local date, or
    today past the finishing hour.  Module-level so ``nightly.horizon`` shares the rule."""
    if day < now.date():
        return True
    return day == now.date() and now.hour >= RACE_DAY_OVER_HOUR


def day_has_started(day: dt.date, now: dt.datetime) -> bool:
    """True once racing on ``day`` can have begun on the race-local clock ``now`` — a preview
    written after this is not a morning read."""
    if day < now.date():
        return True
    return day == now.date() and now.hour >= RACE_DAY_START_HOUR


# The agent's own decision record, written by the day-key-reader.  ``agent_key.json`` is the
# canonical name (``run_day_key`` writes it, ``score_day_keys --also agent`` reads it, ``upload``
# ships it); ``day_key_agent.json`` is tolerated because the coordinator prompt asked for that
# name until 2026-09-17.  Either one keys a board when no human key has been approved.
AGENT_KEY_FILES = ("agent_key.json", "day_key_agent.json")
NON_BOARD_JSON = {
    "scenarios.json", "route.json", "route_raw.json", "route.override.json",
    "agent_key.json", "agent_key_response.json", "day_key_agent.json", "retro_facts.json",
    "startlist.json", "horizon_raw.json",   # Mac horizon handover files, never a rendered board (2026-09-16)
    "route_research.json",                  # route research log (chip Z1, 2026-10-02)
}


def _has_scenario_boards(pred: Path) -> bool:
    """True when a prediction directory contains at least one rendered board."""
    return pred.is_dir() and any(
        p.suffix == ".json" and p.name not in NON_BOARD_JSON and not p.name.startswith("editorial_")
        for p in pred.iterdir()
    )


# ---------------------------------------------------------------------------
# Errors and records
# ---------------------------------------------------------------------------

# operator_tasks.urgency is a CHECK-constrained vocabulary (crosswalk.URGENCIES); a settle that
# cannot finish blocks settlement, a preview that cannot finish blocks publication.
URGENCY_BY_KIND = {
    "acquisition_needed": "blocks_settlement",
    # No uci_competition_url in campaign.json: nothing deterministic can be acquired, and the
    # operator must pick the competition page from the matcher's candidates (chip X, 2026-09-22).
    # It replaces `pcs_pages_needed`, an ask that told the cloud to go and get ProCyclingStats
    # pages -- a path Cloudflare has blocked to Anthropic's fetcher since 2026-09-06.
    "uci_url_needed": "blocks_settlement",
    "ingest_failed": "blocks_settlement",
    # Not a blocker by design (operator ruling 2026-09-16): the stage settles and publishes with a
    # provisional uci: id and a visible caveat; the weekly Mac reconcile turns it into a real id.
    "identity_provisional": "routine",
    "kambi_match": "blocks_publication", "scenarios_needed": "blocks_publication",
    "day_key_needed": "blocks_publication", "validate_failed": "blocks_publication",
    "startlist_needed": "blocks_publication",
}


class WaitingForInput(Exception):
    """A judgment or a human confirmation is needed: exit 10 with an operator task."""

    def __init__(self, kind: str, summary: str, detail: Optional[Dict[str, Any]] = None,
                 urgency: Optional[str] = None):
        super().__init__(summary)
        self.kind, self.summary, self.detail = kind, summary, detail or {}
        self.urgency = urgency or URGENCY_BY_KIND.get(kind, "blocks_settlement")


class EditorialLintFailed(WaitingForInput):
    """A first-attempt editorial draft failed the lint (chip EE, 2026-10-03): exit 10 with the
    compact report and NOTHING stored.  Not an operator ask — the coordinator sends the report
    back to the same editorial thread once and stores the reply with ``editorial --final``, so
    no ``operator_task`` row is written."""

    def __init__(self, report: Dict[str, Any]):
        super().__init__("editorial_lint_failed",
                         "editorial draft failed the lint on its first attempt; retry once, then store with --final",
                         {"lint_report": report}, urgency="routine")
        self.report = report


class DriverFailure(Exception):
    """A step failed: exit 20 with ``error_class`` / ``step`` / ``log_path``."""

    def __init__(self, error_class: str, message: str, *, log_path: Optional[Path] = None,
                 detail: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.error_class, self.log_path, self.detail = error_class, log_path, detail or {}


def task_fingerprint(task: Dict[str, Any]) -> Tuple[str, str, str, str]:
    """What makes two operator tasks the same ask: kind, campaign, unit and phase.

    The driver files a task from ``WaitingForInput`` (detail carries ``unit`` / ``phase``);
    the coordinator files an ops-triage report through ``nightly task`` (its detail carries
    ``trigger.race`` / ``trigger.stage`` / ``trigger.step``). A tick that meets the same wall
    as last night must not file the same task again — three nights of the missing
    signature table filed six triage rows for one cause (2026-09-14..16).
    """
    detail = task.get("detail") if isinstance(task.get("detail"), dict) else {}
    trigger = detail.get("trigger") if isinstance(detail.get("trigger"), dict) else {}
    unit = detail.get("unit")
    if not unit and trigger.get("stage") not in (None, "", 0):
        try:
            unit = f"stage_{int(trigger['stage']):02d}"
        except (TypeError, ValueError):
            unit = str(trigger["stage"])
    if not unit and trigger.get("stage") in (0, "0") and trigger.get("race"):
        unit = "race"
    phase = detail.get("phase") or trigger.get("step") or ""
    campaign = task.get("campaign_slug") or task.get("campaign") or trigger.get("race") or ""
    return (str(task.get("kind") or ""), str(campaign), str(unit or ""), str(phase))


def find_open_duplicate(store: Any, task: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """An unresolved task with the same fingerprint, else None (a store error counts as none)."""
    campaign = task.get("campaign_slug") or task.get("campaign")
    try:
        candidates = store.open_tasks(campaign) if campaign else store.open_tasks()
    except Exception as exc:  # noqa: BLE001 — dedupe is best-effort; filing still proceeds
        logger.warning("open_tasks failed, filing without dedupe: %s", exc)
        return None
    want = task_fingerprint(task)
    for row in candidates:
        if row.get("resolved"):
            continue
        if task_fingerprint(row) == want:
            return row
    return None


def assert_no_git(argv: Sequence[str]) -> None:
    """The driver never runs git — not as a command, not through a shell."""
    for a in argv:
        base = os.path.basename(str(a))
        if base == "git" or base.startswith("git-"):
            raise DriverFailure("forbidden_command", f"git is not a driver operation: {argv}")


def _utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def _is_placeholder(value: Any, *, numeric: bool = False) -> bool:
    """True when a config field is empty or still carries a ``TEMPLATE_scenarios.json`` sentinel.

    The template ships sentinels rather than empty fields (``FILL_FROM_ODDS_PROVENANCE``,
    ``YYYY-MM-DD/markets_HHMM.json``) and every one of them is truthy, so a plain
    ``not cfg.get(...)`` guard reads a freshly templated config as already filled.
    ``numeric=True`` also rejects anything that is not a bare number: a Kambi event id
    is always digits.
    """
    s = "" if value is None else str(value).strip()
    if not s or s.startswith(("FILL_", "YYYY")):
        return True
    return numeric and not s.isdigit()


def fmt_gap(seconds: Optional[float]) -> str:
    if seconds is None:
        return "?"
    s = int(round(float(seconds)))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


# ---------------------------------------------------------------------------
# Campaign
# ---------------------------------------------------------------------------

@dataclass
class Campaign:
    dir: Path
    cfg: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, spec: str | Path) -> "Campaign":
        p = Path(spec)
        if not p.is_dir():
            cand = PERF_EVAL / str(spec)
            if cand.is_dir():
                p = cand
            else:
                raise DriverFailure("campaign_missing", f"no campaign directory for {spec!r}")
        cfg = _read_json(p / "campaign.json", {}) or {}
        return cls(dir=p.resolve(), cfg=cfg)

    @property
    def slug(self) -> str:
        return str(self.cfg.get("slug") or self.dir.name)

    @property
    def fc_race_id(self) -> Optional[str]:
        v = self.cfg.get("fc_race_id")
        return str(v) if v is not None else None

    @property
    def year(self) -> Optional[int]:
        v = self.cfg.get("year")
        return int(v) if v is not None else None

    @property
    def is_stage_race(self) -> bool:
        return bool(self.cfg.get("is_stage_race", True))

    @property
    def category(self) -> Optional[str]:
        """Race tier as the registry writes it: wt | pro | d1 (None when absent)."""
        return tiers.category_of(self.cfg)

    def is_automated(self, covered: Optional[Sequence[str]] = None) -> bool:
        """Whether the unattended nightly covers this campaign (owner rule, 2026-09-22)."""
        return tiers.is_automated(self.cfg, tiers=covered)

    @property
    def uci_competition_url(self) -> Optional[str]:
        """Operator-confirmed UCI competition page (registry field); None → UCI cannot be used."""
        v = self.cfg.get("uci_competition_url")
        return str(v) if v else None

    @property
    def timezone(self) -> str:
        return str(self.cfg.get("timezone") or "UTC")

    @property
    def void_stages(self) -> List[int]:
        return [int(x) for x in (self.cfg.get("void_stages") or [])]

    @property
    def stages(self) -> List[Dict[str, Any]]:
        return [s for s in (self.cfg.get("stages") or []) if s.get("number") is not None]

    # ---- public page names: one rule, shared with the builders (site_paths, chip W 2026-09-22).
    # Before this the driver fell back to "" — the Tour's prefix — for every campaign
    # without a `site.prefix`, and staged the Tour's stage05.html under Okolo Slovenska's
    # run (hosted task 113).  `site.prefix` in campaign.json still wins when present.
    @property
    def site_prefix(self) -> str:
        return site_paths.site_prefix(self.dir.name, self.cfg, is_stage_race=self.is_stage_race)

    def stage_page_name(self, stage: int) -> str:
        return site_paths.stage_page_name(self.site_prefix, stage)

    def stages_index_name(self) -> str:
        return site_paths.stages_index_name(self.site_prefix)

    def gc_page_name(self) -> str:
        return site_paths.gc_tracker_name(self.site_prefix)

    def oneday_page_name(self) -> str:
        """netlify_site/<route slug>-<year>.html — the same rule build_oneday_page.py applies."""
        return site_paths.oneday_page_name(self.dir.name, self.cfg, year=self.year or 0)

    def own_page_names(self, unit: str) -> List[str]:
        """Every netlify_site/ page this campaign may stage for ``unit`` (frame pages excluded)."""
        stage = self.stage_of(unit)
        if stage is not None:
            return [self.stage_page_name(stage), self.stages_index_name(), self.gc_page_name()]
        return [self.oneday_page_name()]

    def unit_for(self, stage: Optional[int]) -> str:
        return f"stage_{int(stage):02d}" if stage is not None else ONE_DAY_UNIT

    @staticmethod
    def stage_of(unit: str) -> Optional[int]:
        if unit.startswith("stage_"):
            try:
                return int(unit.split("_", 1)[1])
            except ValueError:
                return None
        return None

    def stage_date(self, stage: Optional[int]) -> Optional[str]:
        if stage is None:
            return self.cfg.get("start_date") or self.cfg.get("date")
        for s in self.stages:
            if int(s["number"]) == int(stage):
                return s.get("date")
        return None

    def results_dir(self, unit: str) -> Path:
        return self.dir / "results" / unit

    def pred_dir(self, unit: str) -> Path:
        return self.dir / "predictions" / unit

    def runs_dir(self) -> Path:
        return self.dir / "runs"

    def today(self, override: Optional[dt.date] = None) -> dt.date:
        if override:
            return override
        return self.local_now().date()

    def local_now(self, override: Optional[dt.datetime] = None) -> dt.datetime:
        """The race-local wall clock — what decides whether a race day is over.

        ``timezone`` may be absent (then UTC, the long-standing behaviour) or a name this
        Python does not know; either way the fallback is UTC rather than a raised error, so a
        campaign is never undue merely because its zone string is wrong.
        """
        if override is not None:
            return override
        try:
            from zoneinfo import ZoneInfo
            return dt.datetime.now(ZoneInfo(self.timezone))
        except Exception:  # noqa: BLE001 — unknown zone name
            return dt.datetime.now(dt.timezone.utc)

    def refresh_event_ids(self) -> Dict[str, str]:
        """Re-read the Kambi event ids ``capture_odds`` merged into ``campaign.json``; return the new ones.

        ``cfg`` is read once, when the campaign is loaded.  The odds capture is a subprocess that
        writes newly discovered ids back into the file, so without this the ids it just found are
        invisible to the rest of the run and the fill can only happen on the next invocation.
        """
        disk = (_read_json(self.dir / "campaign.json", {}) or {}).get("kambi_event_ids")
        known = self.cfg.get("kambi_event_ids")
        if not isinstance(known, dict):
            known = self.cfg["kambi_event_ids"] = {}
        if not isinstance(disk, dict):
            return {}
        new = {k: str(v) for k, v in disk.items() if v and str(known.get(k) or "") != str(v)}
        known.update(new)
        return new

    def previous_config(self, stage: int) -> Optional[Dict[str, Any]]:
        for n in range(stage - 1, 0, -1):
            cfg = _read_json(self.pred_dir(self.unit_for(n)) / "scenarios.json")
            if cfg:
                return cfg
        return None

    def latest_results_stage(self, before: Optional[int] = None) -> Optional[int]:
        best = None
        for p in (self.dir / "results").glob("stage_*"):
            n = self.stage_of(p.name)
            if n is None or not (p / "results.csv").exists():
                continue
            if before is not None and n >= before:
                continue
            best = n if best is None else max(best, n)
        return best


# ---------------------------------------------------------------------------
# Store resolution and the SQLite lock
# ---------------------------------------------------------------------------

def resolve_store(kind: str, root: Optional[Path], *, dry_run: bool, campaign: Optional[Campaign]) -> Any:
    from cycling_project.nightly import store as _store
    if dry_run or kind == "fake":
        base = root or (campaign.runs_dir() / FAKESTORE_DIRNAME if campaign else PERF_EVAL / "runs" / FAKESTORE_DIRNAME)
        return _store.FakeStore(Path(base), role="agent")
    load_local_env()
    have = bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_NIGHTLY_KEY"))
    if kind == "supabase" or (kind == "auto" and have):
        if not have:
            raise DriverFailure("credentials", "SUPABASE_URL and SUPABASE_NIGHTLY_KEY are required for --store supabase")
        return _store.SupabaseStore(role="agent")
    if os.environ.get("NIGHTLY_RELEASE_TAG"):
        # A hydrated container (bootstrap sets the tag) must never fall back silently: a FakeStore
        # there means the night's runs, pages and prediction_log rows die with the container
        # (2026-09-17/18, hosted tasks 95 and 103).  Fail loudly; `--store fake` stays available.
        missing = [n for n in ("SUPABASE_URL", "SUPABASE_NIGHTLY_KEY") if not os.environ.get(n)]
        raise DriverFailure("credentials", f"{', '.join(missing)} not set in this shell inside release "
                            f"{os.environ['NIGHTLY_RELEASE_TAG']}: source nightly_env.sh / export the store "
                            "settings, or pass --store fake explicitly")
    base = root or (campaign.runs_dir() / FAKESTORE_DIRNAME if campaign else PERF_EVAL / "runs" / FAKESTORE_DIRNAME)
    logger.info("no Supabase credentials; using FakeStore at %s", base)
    return _store.FakeStore(Path(base), role="agent")


@contextlib.contextmanager
def sqlite_lock(db_path: Path, timeout_s: float = 600.0):
    """Global advisory lock around every SQLite-writing step (threads share the container)."""
    lock_path = Path(str(db_path) + ".nightly.lock")
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(lock_path, "a+")
    except OSError:
        lock_path = PERF_EVAL / "runs" / "sqlite.nightly.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(lock_path, "a+")
    deadline = time.time() + timeout_s
    try:
        while True:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.time() > deadline:
                    raise DriverFailure("lock_timeout", f"could not lock {lock_path} within {timeout_s}s")
                time.sleep(0.5)
        yield
    finally:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        finally:
            fh.close()


# ---------------------------------------------------------------------------
# The driver
# ---------------------------------------------------------------------------

class Driver:
    def __init__(self, campaign: Optional[Campaign], store: Any, *, dry_run: bool = False,
                 today: Optional[dt.date] = None, no_log: bool = False, force: bool = False,
                 python: Optional[str] = None, crosswalk_csv: Optional[Path] = None,
                 db_path: Optional[Path] = None, agent_key: Optional[Path] = None,
                 release_tag: Optional[str] = None, acquire: bool = True, provider: str = "auto",
                 aliases_csv: Optional[Path] = None, signatures: Optional[Path] = None,
                 identity_policy: str = uci_ingest.DEFAULT_IDENTITY_POLICY,
                 local_now: Optional[dt.datetime] = None, allow_scrape: bool = False,
                 automation_tiers: Optional[Sequence[str]] = None):
        self.campaign = campaign
        # Which race tiers this invocation treats as automated (owner rule, 2026-09-22:
        # WorldTour and .Pro).  None = the default set; `--all-tiers` / `--include-tier`
        # widen it for an attended Mac run.  Only `plan`/`night` consult it — an explicit
        # `settle --unit` / `preview --unit` on a `.1` race still runs.
        self.automation_tiers = tuple(automation_tiers) if automation_tiers is not None else None
        self.acquire_enabled = acquire            # settle may run the deterministic UCI acquisition itself
        self.provider_pref = provider              # auto | uci | pcs
        self.aliases_csv = Path(aliases_csv) if aliases_csv else None
        # strict = an unresolved rider inside the top-15/top-20 gate asks a human (attended Mac runs);
        # provisional = archive it under a uci: id, caveat the page, file a routine task (the default,
        # because the unattended cloud tick has nobody to ask).  Operator ruling 2026-09-16.
        self.identity_policy = identity_policy or uci_ingest.DEFAULT_IDENTITY_POLICY
        self.store = store
        self.dry_run = dry_run
        self.today_override = today
        self.now_override = local_now
        # The serving runner reaches FirstCycling for a start list it has neither on disk nor in
        # the cache.  That works on the Mac (visible Chrome, Cloudflare cookie) and never in the
        # cloud container, where it cost a paid triage cycle (task 93, 2026-09-17).  The driver
        # therefore refuses the scrape by default and asks for a handover instead; an attended
        # Mac run passes --allow-scrape.
        self.allow_scrape = allow_scrape
        self.no_log = no_log or dry_run
        self.force = force
        self.python = python or sys.executable
        self.crosswalk_csv = Path(crosswalk_csv) if crosswalk_csv else CROSSWALK_CSV
        self.db_path = Path(db_path) if db_path else default_db_path()
        self.agent_key = Path(agent_key) if agent_key else None
        # experiments/selection_signatures_*.csv.gz — the reference table machine-chosen
        # scenario references are drawn from (None: newest in experiments/).
        self.signatures = Path(signatures) if signatures else None
        self.release_tag = release_tag or os.environ.get("NIGHTLY_RELEASE_TAG")
        # per-run state
        self.run: Optional[Dict[str, Any]] = None
        self.record: Dict[str, Any] = {}
        self.record_path: Optional[Path] = None
        self.built_pages: List[Path] = []
        self.plog_watermark: Optional[int] = None

    # -- helpers ----------------------------------------------------------------
    @property
    def today(self) -> dt.date:
        if self.today_override:
            return self.today_override
        if self.now_override is not None:
            return self.now_override.date()
        return self.campaign.today() if self.campaign else dt.date.today()

    @property
    def local_now(self) -> dt.datetime:
        """Race-local wall clock, honouring the overrides.

        ``--today`` is a date with no hour.  Every existing caller means by it "the nightly
        tick of that date", which fires after European racing, so a bare date override reads as
        that evening; ``--local-now`` is there for the cases where the hour is the point.
        """
        if self.now_override is not None:
            return self.now_override
        if self.today_override is not None:
            return dt.datetime.combine(self.today_override, dt.time(RACE_DAY_OVER_HOUR, 0))
        return self.campaign.local_now() if self.campaign else dt.datetime.now()

    def _day_is_over(self, day: dt.date) -> bool:
        """True once ``day`` has finished where the race is: a past local date, or today past
        the finishing hour."""
        return day_is_over(day, self.local_now)

    def _day_has_started(self, day: dt.date) -> bool:
        """True once racing on ``day`` can have begun — a preview written after this is not a
        morning read."""
        return day_has_started(day, self.local_now)

    def _say(self, msg: str) -> None:
        print(redact(msg), file=sys.stderr, flush=True)

    def _completed_index(self) -> Dict[str, Any]:
        return _read_json(self.campaign.runs_dir() / COMPLETED_INDEX, {}) or {}

    def _mark_completed(self, unit: Optional[str], phase: str) -> None:
        if self.dry_run:
            return
        idx = self._completed_index()
        idx[f"{unit or '-'}:{phase}"] = {"run_id": self.run["run_id"] if self.run else None,
                                          "finished_at": _utcnow(), "date": str(self.today)}
        _write_json(self.campaign.runs_dir() / COMPLETED_INDEX, idx)

    def _already_done(self, unit: Optional[str], phase: str) -> Optional[Dict[str, Any]]:
        if self.force:
            return None
        return self._completed_index().get(f"{unit or '-'}:{phase}")

    # -- run/step recording ----------------------------------------------------
    def begin(self, unit: Optional[str], phase: str, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        slug = self.campaign.slug if self.campaign else None
        self.run = self.store.start_run(slug, unit, phase, release_tag=self.release_tag,
                                        meta={"dry_run": self.dry_run, "today": str(self.today), **(meta or {})})
        self.run.setdefault("run_id", str(uuid.uuid4()))
        self.run_started_ts = time.time()      # ``_odds_files`` ships the snapshots written since
        self.built_pages = []
        self.record = {"run_id": self.run["run_id"], "campaign": slug, "unit": unit, "phase": phase,
                       "started_at": _utcnow(), "dry_run": self.dry_run, "today": str(self.today),
                       "state": "running", "steps": []}
        # Dry runs keep the in-memory record (and FakeStore ledger) for useful
        # JSON/contract validation, but ``--no-log`` means they must not create
        # the campaign's mirrored run record on disk.
        self.record_path = None
        if self.campaign and not self.dry_run:
            day_dir = self.campaign.runs_dir() / str(self.today)
            name = f"{phase}_{unit}.json" if unit else f"{phase}.json"
            self.record_path = day_dir / name
            self._flush()
        self.plog_watermark = self._prediction_log_max_id()
        return self.run

    def _flush(self) -> None:
        if self.record_path:
            _write_json(self.record_path, self.record)

    def _record_step(self, step: str, state: str, *, started: float, exit_code: Optional[int] = None,
                     detail: Optional[Dict[str, Any]] = None, log_path: Optional[Path] = None) -> None:
        finished = _utcnow()
        duration_ms = int((time.time() - started) * 1000)
        entry = {"step": step, "state": state, "finished_at": finished, "duration_ms": duration_ms,
                 "exit_code": exit_code, "detail": detail or {}, "log_path": str(log_path) if log_path else None}
        self.record["steps"].append(entry)
        self._flush()
        try:
            self.store.add_step(self.run["run_id"], step, state, finished_at=finished, duration_ms=duration_ms,
                                exit_code=exit_code, detail=detail or {},
                                log_key=str(log_path.relative_to(PROJECT_ROOT)) if log_path and log_path.is_relative_to(PROJECT_ROOT) else None)
        except Exception as exc:  # noqa: BLE001 — the local record is the fallback ledger
            self._say(f"  [store] add_step failed: {exc}")

    def finish(self, state: str, exit_code: int, detail: Optional[Dict[str, Any]] = None) -> None:
        self.record.update({"state": state, "exit_code": exit_code, "finished_at": _utcnow(), "result": detail or {}})
        self._flush()
        try:
            self.store.finish_run(self.run["run_id"], state, exit_code, detail=detail or {})
        except Exception as exc:  # noqa: BLE001
            self._say(f"  [store] finish_run failed: {exc}")

    def step(self, name: str, fn: Callable[[], Any], *, skip: Optional[str] = None) -> Any:
        """Run one python step; records ok/skipped/waiting/failed and re-raises."""
        started = time.time()
        if skip:
            self._say(f"- {name}: skipped ({skip})")
            self._record_step(name, "skipped", started=started, detail={"reason": skip})
            return None
        self._say(f"- {name}")
        try:
            out = fn()
        except WaitingForInput as w:
            self._record_step(name, "waiting", started=started, exit_code=EXIT_WAITING,
                              detail={"kind": w.kind, "summary": w.summary})
            raise
        except DriverFailure as f:
            self._record_step(name, "failed", started=started, exit_code=EXIT_FAILED,
                              detail={"error_class": f.error_class, "message": str(f), **f.detail}, log_path=f.log_path)
            raise
        except Exception as exc:  # noqa: BLE001
            self._record_step(name, "failed", started=started, exit_code=EXIT_FAILED,
                              detail={"error_class": type(exc).__name__, "message": str(exc),
                                      "trace": traceback.format_exc()[-2000:]})
            raise DriverFailure(type(exc).__name__, str(exc)) from exc
        detail = out if isinstance(out, dict) and out.get("_detail") else {}
        self._record_step(name, "ok", started=started, exit_code=0, detail=detail.get("_detail") if detail else {})
        return out

    def script(self, name: str, argv: Sequence[str], *, lock: bool = False, ok_codes: Iterable[int] = (0,),
               cwd: Optional[Path] = None) -> Dict[str, Any]:
        """Subprocess an existing script unchanged; captured log; dry-run records the argv only."""
        argv = [str(a) for a in argv]
        assert_no_git(argv)
        started = time.time()
        log_path = None
        # Decide the dry-run outcome before creating the log directory.  The
        # argv still lands in the in-memory/Store step detail below.
        if self.dry_run:
            self._say(f"- {name}: skipped (dry-run) :: {' '.join(argv)}")
            self._record_step(name, "skipped", started=started, detail={"reason": "dry-run", "argv": argv})
            return {"skipped": True, "argv": argv, "returncode": None}
        if self.campaign:
            log_dir = self.campaign.runs_dir() / str(self.today) / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            unit = self.record.get("unit") or "-"
            log_path = log_dir / f"{self.record.get('phase', 'run')}_{unit}_{name}.log"
        env = {**os.environ, "PYTHONUNBUFFERED": "1", "SCRAPER_USE_BROWSER": os.environ.get("SCRAPER_USE_BROWSER", "0")}
        env[DB_ENV_VAR] = str(self.db_path)
        self._say(f"- {name}: {' '.join(argv)}")
        lock_cm = sqlite_lock(self.db_path) if lock else contextlib.nullcontext()
        with lock_cm, open(log_path, "w", encoding="utf-8") if log_path else contextlib.nullcontext() as fh:
            proc = subprocess.run(argv, cwd=str(cwd or PROJECT_ROOT), env=env, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, text=True)
            text = redact(proc.stdout or "")
            if fh:
                fh.write(text)
        tail = text[-1500:]
        detail = {"argv": argv, "returncode": proc.returncode, "tail": tail}
        if proc.returncode not in set(ok_codes):
            self._record_step(name, "failed", started=started, exit_code=proc.returncode, detail=detail, log_path=log_path)
            raise DriverFailure("subprocess", f"{name} exited {proc.returncode}", log_path=log_path,
                                detail={"argv": argv, "tail": tail})
        self._record_step(name, "ok", started=started, exit_code=proc.returncode,
                          detail={"argv": argv, "returncode": proc.returncode}, log_path=log_path)
        return {"skipped": False, "argv": argv, "returncode": proc.returncode, "stdout": text}

    # -- top-level wrapper -----------------------------------------------------
    def run_phase(self, unit: Optional[str], phase: str, body: Callable[[], Dict[str, Any]],
                  *, idempotent: bool = True) -> Tuple[int, Dict[str, Any]]:
        done = self._already_done(unit, phase) if (idempotent and self.campaign) else None
        if done:
            out = {"status": "done", "already": True, "campaign": self.campaign.slug, "unit": unit, "phase": phase,
                   "previous_run": done}
            return EXIT_DONE, out
        self.begin(unit, phase)
        base = {"campaign": self.campaign.slug if self.campaign else None, "unit": unit, "phase": phase,
                "run_id": self.run["run_id"], "dry_run": self.dry_run, "record": str(self.record_path) if self.record_path else None}
        try:
            result = body() or {}
        except EditorialLintFailed as e:
            self.finish("waiting", EXIT_WAITING, {"kind": e.kind, "lint_report": e.report})
            return EXIT_WAITING, {**base, "status": "waiting_for_input", "kind": e.kind,
                                  "lint_report": e.report, "operator_task": None,
                                  "next": "send lint_report to the same editorial thread once "
                                          "(\"Fix exactly these and return the whole JSON again\"), save the reply "
                                          "over the draft file, then run `editorial --final`"}
        except WaitingForInput as w:
            task = build_operator_task(w.kind, self.campaign.slug if self.campaign else None, w.summary,
                                       {**w.detail, "unit": unit, "phase": phase, "run_id": self.run["run_id"]}, w.urgency)
            task["run_id"] = self.run["run_id"]
            task_row = None
            duplicate = find_open_duplicate(self.store, task)
            if duplicate:
                task_row = duplicate
                self._say(f"  [store] same ask already open as task {duplicate.get('id')}; not filed again")
            else:
                try:
                    task_row = self.store.insert_task(task)
                except Exception as exc:  # noqa: BLE001
                    self._say(f"  [store] insert_task failed: {exc}")
            self.finish("waiting", EXIT_WAITING, {"operator_task": task,
                                                  "duplicate_of": (duplicate or {}).get("id")})
            return EXIT_WAITING, {**base, "status": "waiting_for_input", "operator_task": task,
                                  "operator_task_id": (task_row or {}).get("id"),
                                  "duplicate_of": (duplicate or {}).get("id")}
        except DriverFailure as f:
            self.finish("failed", EXIT_FAILED, {"error_class": f.error_class, "message": str(f)})
            return EXIT_FAILED, {**base, "status": "failed", "error_class": f.error_class, "message": str(f),
                                 "step": self.record["steps"][-1]["step"] if self.record["steps"] else None,
                                 "log_path": str(f.log_path) if f.log_path else None, "detail": f.detail}
        self.finish("ok", EXIT_DONE, result)
        if idempotent:
            self._mark_completed(unit, phase)
        return EXIT_DONE, {**base, "status": "done", **result}

    # ------------------------------------------------------------------------
    # plan / night
    # ------------------------------------------------------------------------
    def plan(self, horizon_days: int = 1) -> Dict[str, Any]:
        c = self.campaign
        today = self.today
        # Scope gate (owner rule, 2026-09-22): the unattended nightly covers WorldTour and
        # .Pro.  A `.1` race is registered, bundled and runnable by hand, but nothing is due
        # for it unless campaign.json opts it in or the Mac passes --all-tiers/--include-tier.
        # The reason travels in the plan JSON so the coordinator's per-campaign `plan` call
        # shows why the night is empty; no coordinator prompt change is needed.
        # No log line here on purpose: the shared logger writes to stdout, which is the
        # plan's JSON channel — `skipped` in the payload IS the record.
        skipped = tiers.skip_reason(c.cfg, tiers=self.automation_tiers)
        note = tiers.override_note(c.cfg)
        if skipped:
            out = {"campaign": c.slug, "today": str(today), "timezone": c.timezone,
                   "local_now": self.local_now.isoformat(timespec="minutes"),
                   "category": c.category, "automated": False, "skipped": skipped,
                   "void_stages": sorted(set(c.void_stages)), "units": [],
                   "settle": [], "preview": [], "route_research": []}
            if note:
                out["automation_note"] = note
            return out
        store_void: set = set()
        try:
            for s in self.store.stages(c.slug) or []:
                if s.get("void") and s.get("unit"):
                    n = c.stage_of(s["unit"])
                    if n is not None:
                        store_void.add(n)
        except Exception:  # noqa: BLE001
            pass
        void = set(c.void_stages) | store_void
        units: List[Dict[str, Any]] = []
        if c.is_stage_race:
            entries = [(int(s["number"]), s.get("date")) for s in c.stages]
        else:
            entries = [(None, c.stage_date(None))]
        prev_settled = True
        # The preview window reaches ``horizon_days`` beyond the day being raced.  When the local
        # clock is still before racing starts, the current day IS that day, so it ends the window:
        # without this, a tick in the small hours east of UTC previews today's stage AND
        # tomorrow's, and tomorrow's board would be built before today's result exists — no race
        # state, and ``has_boards`` would stop it ever being rebuilt.
        preview_window_end = today + dt.timedelta(days=horizon_days - (0 if self._day_has_started(today) else 1))
        latest_archived = c.latest_results_stage() if c.is_stage_race else None
        # A stage race with a stage on the road right now (race-local day started, not over)
        # previews nothing beyond it: tomorrow's board needs today's result for its race state,
        # and ``has_boards`` would stop it being rebuilt once that result lands.  With one tick
        # this never bit (19:45 UTC is evening in Europe and the small hours in Asia); the second
        # tick at 23:00 Pacific (2026-10-05) is mid-afternoon in Shanghai, so Guangxi's next
        # stage is left to the 12:45 tick, which previews it after today's has settled.
        on_road = c.is_stage_race and self._day_has_started(today) and not self._day_is_over(today) and any(
            d == str(today) and (n is None or n not in void) for n, d in entries)
        dated = [dt.date.fromisoformat(d) for _n, d in entries if d]
        if dated and max(dated) < today - dt.timedelta(days=FINISHED_AFTER_DAYS):
            return {"campaign": c.slug, "today": str(today), "timezone": c.timezone,
                    "local_now": self.local_now.isoformat(timespec="minutes"), "void_stages": sorted(void),
                    "category": c.category, "automated": True,
                    "units": [], "settle": [], "preview": [], "route_research": [], "finished": True,
                    "note": f"last unit {max(dated)} is more than {FINISHED_AFTER_DAYS} days ago: nothing is due"}
        for number, date_s in sorted(entries, key=lambda t: (t[0] is None, t[0] or 0)):
            if not date_s:
                continue
            d = dt.date.fromisoformat(date_s)
            unit = c.unit_for(number)
            if number is not None and number in void:
                units.append({"unit": unit, "date": date_s, "void": True, "due": []})
                continue
            has_results = (c.results_dir(unit) / "results.csv").exists()
            pred = c.pred_dir(unit)
            has_boards = _has_scenario_boards(pred)
            has_pcs = (c.results_dir(unit) / "pcs").is_dir()
            has_uci = uci_acquire.capture_is_complete(uci_acquire.read_index(c.results_dir(unit) / "uci"))
            has_capture = has_pcs or has_uci
            due: List[str] = []
            flags: List[str] = []
            # A stage settles once its own race-local day is over: a past local date, or the
            # local date with the clock past the finishing hour.  The tick is a fixed UTC hour,
            # so east of UTC "race-local today" can already be the morning of a stage nobody has
            # ridden (Huangshan, 2026-09-17) — the date alone is not evidence that a result can
            # exist.  A one-day race may start very late local (Binzhou at 05:49) and the
            # runbook's contract for it is preview the evening before, settle the evening
            # after, so it keeps waiting for the following race-local day.
            settle_due = self._day_is_over(d) if c.is_stage_race else d < today
            if settle_due and not has_results:
                # A stage below the latest archived one is a missed day: the runbook's
                # "a missed day cannot be recovered" — it is a gap, not a due settle,
                # unless the acquisition thread has actually put PCS pages there.
                if number is not None and latest_archived is not None and number < latest_archived and not has_capture:
                    flags.append("gap")
                else:
                    due.append("settle")
                    if d < today:
                        flags.append("settle_late")
                    if not has_capture:
                        flags.append("awaiting_acquisition")
            # Preview a day that is still ahead of the race-local clock and inside the horizon.
            # "Still ahead" is normally tomorrow, but for a race east of UTC the tick can land
            # in the small hours of the race day itself — that is a genuine morning read, and
            # the old ``today < d`` test dropped it.  Once racing can have begun, the window
            # shuts: a board built then would not be a preview.
            research = False
            if d <= preview_window_end and not self._day_has_started(d) and not has_boards and on_road and d > today:
                flags.append("prior_stage_on_road")
            elif d <= preview_window_end and not self._day_has_started(d) and not has_boards:
                due.append("preview")
                if not prev_settled:
                    flags.append("blocked")
                # Route research (chip Z1, 2026-10-02): a preview whose route facts are
                # partial/missing gets one route-researcher task before the campaign
                # thread runs; the preview's route_facts step then ingests route_raw.json.
                research = c.is_stage_race and route_research.needs_research(
                    c.dir, unit, c.cfg, covered=self.automation_tiers)[0]
            units.append({"unit": unit, "date": date_s, "void": False, "due": due, "flags": flags,
                          "has_results": has_results, "has_boards": has_boards, "has_pcs": has_pcs, "has_uci": has_uci,
                          "uci_competition_url": c.uci_competition_url, "route_research": research})
            if settle_due and "gap" not in flags:
                prev_settled = has_results
        return {"campaign": c.slug, "today": str(today), "timezone": c.timezone,
                "local_now": self.local_now.isoformat(timespec="minutes"),
                "category": c.category, "automated": True,
                **({"automation_note": note} if note else {}),
                "void_stages": sorted(void), "units": units,
                "settle": [u["unit"] for u in units if "settle" in u["due"]],
                "preview": [u["unit"] for u in units if "preview" in u["due"]],
                "route_research": [u["unit"] for u in units if u.get("route_research")]}

    def night(self, horizon_days: int = 1) -> Tuple[int, Dict[str, Any]]:
        plan = self.plan(horizon_days)
        if plan.get("skipped"):
            return EXIT_DONE, {"campaign": self.campaign.slug, "status": "skipped",
                               "skipped": plan["skipped"], "plan": plan, "runs": []}
        results: List[Dict[str, Any]] = []
        worst = EXIT_DONE
        for unit in plan["settle"]:
            code, out = self.settle(unit)
            results.append(out)
            worst = max(worst, code)
            if code != EXIT_DONE:
                return worst, {"campaign": self.campaign.slug, "status": "stopped", "plan": plan, "runs": results}
        for unit in plan["preview"]:
            code, out = self.preview(unit)
            results.append(out)
            worst = max(worst, code)
            if code != EXIT_DONE:
                return worst, {"campaign": self.campaign.slug, "status": "stopped", "plan": plan, "runs": results}
        return worst, {"campaign": self.campaign.slug, "status": "done", "plan": plan, "runs": results}

    # ------------------------------------------------------------------------
    # settle
    # ------------------------------------------------------------------------
    def settle(self, unit: str) -> Tuple[int, Dict[str, Any]]:
        return self.run_phase(unit, "settle", lambda: self._settle_body(unit))

    def _settle_body(self, unit: str) -> Dict[str, Any]:
        c = self.campaign
        stage = c.stage_of(unit)
        results_dir = c.results_dir(unit)
        out: Dict[str, Any] = {}

        # 1. acquire (UCI primary, deterministic, in-process) + ingest (→ FC-shaped archive)
        if (results_dir / "results.csv").exists() and not self.force:
            self.step("acquire", lambda: None, skip="results already archived")
            self.step("ingest", lambda: None, skip="results already archived")
        else:
            out["acquire"] = self.step("acquire", lambda: self._acquire(unit))
            out["ingest"] = self.step("ingest", lambda: self._ingest(unit))

        # 2. seed the state cache BEFORE the GC refresh (the outlook head reads it).
        # A one-day race has no within-race state to reconstruct.
        if stage is not None:
            self.script("seed_state_cache", [self.python, SCRIPTS["seed_state_cache"], "--race-id", c.fc_race_id,
                                             "--year", c.year, "--out-root", results_dir.parent], lock=True)
        else:
            self.step("seed_state_cache", lambda: None, skip="one-day race: no within-race state")

        # 3. GC config templated, GC predict, tracker
        gc_cfg_path = c.pred_dir("gc") / "scenarios.json"
        if gc_cfg_path.exists() and stage is not None:
            out["gc_config"] = self.step("gc_config", lambda: self._template_gc_config(gc_cfg_path, stage))
            self.script("gc_predict", self._predict_argv(gc_cfg_path), lock=True)
            self.script("gc_tracker", [self.python, SCRIPTS["gc_tracker"], gc_cfg_path])
        else:
            self.step("gc_config", lambda: None, skip="no predictions/gc/scenarios.json")

        # 4. day-key scoring — always, even for unkeyed stages.  --backfill also scores every
        # settled stage that has no card row (or an unscored prospective agent key): the card is
        # the day-key reader's ledger and must be monotonic.  Before 2026-10-02 (chip Z2) only
        # stage N was scored, so a row lost once — every release rolled the cumulative card back
        # to the Mac's copy (bootstrap.plan_overlay) — never came back.  Deterministic from the
        # archive; existing rows are never re-labelled.
        if stage is not None:
            self.script("score_day_keys", [self.python, SCRIPTS["score_day_keys"], "--campaign", c.dir, "--stage", stage,
                                           "--also", "agent", "--backfill"], lock=True)

        # A missed preview is still publishable as an honestly labelled
        # retrospective.  Build it from the settled oracle, freeze the result
        # field, and force --no-log so it can never enter the prospective log.
        cfg_path = c.pred_dir(unit) / "scenarios.json"
        if not cfg_path.exists():
            out["hindsight"] = self.step("hindsight", lambda: hindsight.build(
                c.dir, unit, fc_race_id=c.fc_race_id, year=c.year,
                date=c.stage_date(stage) or c.cfg.get("start_date"),
                label=(f"Stage {stage}" if stage is not None else c.cfg.get("name") or c.slug),
                db_path=self.db_path, stage=stage, void_stages=c.void_stages))
            self.script("hindsight_predict", self._predict_argv(cfg_path, no_log=True), lock=True)

        # 5. retro facts — a one-day settle writes them too (2026-10-04: without them the
        # editorial bundle for Emilia/Münsterland was rebuilt with no result in it).
        if (stage is not None or oneday.is_one_day_unit(unit)) and (c.pred_dir(unit) / "scenarios.json").exists():
            out["retro_facts"] = self.step("retro_facts", lambda: self._retro_facts(unit))
        else:
            self.step("retro_facts", lambda: None, skip="no scenario config for this unit")

        # 6. pages
        self._build_pages(unit)

        # 7. upload
        out["upload"] = self.step("upload", lambda: self._upload(unit, "settle"))
        return out

    # -- acquisition: provider selection -----------------------------------------
    def _detect_provider(self, unit: str) -> Tuple[Optional[str], Optional[str]]:
        """(provider, fallback_reason) from what is on disk. UCI wins when its capture is complete."""
        c = self.campaign
        res = c.results_dir(unit)
        uci_ok = uci_acquire.capture_is_complete(uci_acquire.read_index(res / "uci"))
        pcs_ok = (res / "pcs").is_dir()
        pref = self.provider_pref
        if pref == "uci":
            return ("uci", None) if uci_ok else (None, "uci capture missing or incomplete")
        if pref == "pcs":
            return ("pcs", "provider forced to pcs") if pcs_ok else (None, "pcs pages missing")
        # `auto` means UCI, full stop (chip X, 2026-09-22).  PCS was the automatic fallback until
        # Cloudflare began 403ing Anthropic's fetcher (LESSONS 2026-09-06), so `auto` could pick a
        # provider the cloud has no way to feed.  `--provider pcs`, given explicitly on the
        # attended Mac, still reaches pcs_ingest; nothing else does, even with pages on disk.
        if uci_ok:
            return "uci", None
        return None, None

    def _acquire(self, unit: str) -> Dict[str, Any]:
        """Run the deterministic UCI acquisition when the campaign is mapped and nothing is captured yet."""
        c = self.campaign
        provider, reason = self._detect_provider(unit)
        info: Dict[str, Any] = {"provider": provider, "fallback_reason": reason, "ran": False}
        if provider is None and c.uci_competition_url and self.provider_pref in ("auto", "uci"):
            if self.dry_run or not self.acquire_enabled:
                info["skipped"] = "dry run" if self.dry_run else "acquisition disabled (--no-acquire)"
            else:
                try:
                    index = uci_acquire.acquire(competition_url=c.uci_competition_url, unit=unit,
                                                out_dir=c.results_dir(unit) / "uci", campaign_slug=c.slug)
                except uci_acquire.AcquireError as exc:
                    info.update({"ran": True, "error": str(exc)})
                else:
                    info.update({"ran": True, "reused": bool(index.get("reused")), "complete": bool(index.get("complete")),
                                 "requests_made": index.get("requests_made"), "summary": uci_acquire.summary(index)})
                provider, reason = self._detect_provider(unit)
                info.update({"provider": provider, "fallback_reason": reason})
        self.record["provider"] = provider
        self.record["fallback_reason"] = reason
        if provider is None:
            if self.provider_pref == "pcs":                      # attended Mac path, asked for by hand
                raise WaitingForInput("acquisition_needed",
                                      f"{c.slug} {unit}: --provider pcs, but no pages under results/{unit}/pcs/",
                                      {"expected": {"pcs": sorted(pcs_ingest.PAGE_FILES.values())}, "acquire": info})
            if not c.uci_competition_url:
                raise self._uci_url_task(unit, info)
            raise WaitingForInput("acquisition_needed",
                                  f"{c.slug} {unit}: no complete UCI capture (results not published, or acquisition failed: "
                                  f"{info.get('error') or info.get('skipped') or 'not run'})",
                                  {"expected": {"uci": f"python -m cycling_project.nightly.uci_acquire "
                                                       f"--competition-url {c.uci_competition_url} "
                                                       f"--campaign {c.dir} --unit {unit}"},
                                   "acquire": info})
        info["_detail"] = {"provider": provider, "fallback_reason": reason, "reused": info.get("reused"), "ran": info["ran"]}
        return info

    def _uci_url_task(self, unit: str, info: Optional[Dict[str, Any]] = None) -> "WaitingForInput":
        """The campaign has no `uci_competition_url`: a HUMAN ask, carrying the matcher's evidence.

        `uci_calendar.py` writes `uci_match_evidence` into campaign.json whenever it declines to
        set a URL (no exact date range, name similarity < 0.90, or a rival candidate) -- its
        candidate and alternates are exactly what the operator needs to pick the right competition
        page in the inbox, so they travel in the task detail.  Before chip X (2026-09-22) this
        raised `pcs_pages_needed`, an ask that told the cloud coordinator to go and obtain
        ProCyclingStats pages; PCS has 403ed Anthropic's fetcher since 2026-09-06, so the ask
        could never be met and the coordinator spent its reasoning hunting for a way (session
        sesn_01EXAMPLE78CD3112BF8B3A4, Giro della Romagna, 2026-09-22).
        """
        c = self.campaign
        evidence = c.cfg.get("uci_match_evidence") or {}
        candidate = evidence.get("candidate")
        alternates = evidence.get("alternates") or []
        detail: Dict[str, Any] = {
            "expected": "an operator-confirmed uci_competition_url in campaign.json",
            "campaign_json": str(c.dir / "campaign.json"),
            "uci_match_evidence": evidence,
            "candidate": candidate,
            "alternates": alternates,
            "matcher_decision": evidence.get("decision"),
            "matcher_reason": evidence.get("reason"),
            "resolve": f"python -m cycling_project.nightly.uci_calendar resolve --campaign {c.dir}",
        }
        if info is not None:
            detail["acquire"] = info
        n = len(alternates) + (1 if candidate else 0)
        return WaitingForInput(
            "uci_url_needed",
            f"{c.slug} {unit}: campaign.json has no uci_competition_url, so there is nothing to "
            f"acquire -- confirm the UCI competition page in the inbox ({n} candidate(s) on file)",
            detail)

    def _crosswalk_store_rows(self) -> List[Dict[str, Any]]:
        try:
            rows = getattr(self.store, "rows", {}).get("crosswalk") if hasattr(self.store, "rows") else None
            if rows is None and hasattr(self.store, "_select"):
                rows = self.store._select("crosswalk", {"select": "*"})
            return list(rows or [])
        except Exception as exc:  # noqa: BLE001 — the CSV is the fallback
            self._say(f"  [store] crosswalk rows unavailable: {exc}")
            return []

    def _ingest(self, unit: str) -> Dict[str, Any]:
        c = self.campaign
        provider = self.record.get("provider")
        if provider is None:
            provider, reason = self._detect_provider(unit)
            self.record["provider"], self.record["fallback_reason"] = provider, reason
        if provider is None:
            if not c.uci_competition_url and self.provider_pref != "pcs":
                raise self._uci_url_task(unit)
            raise WaitingForInput("acquisition_needed",
                                  f"{c.slug} {unit}: nothing to ingest (no captured results for provider "
                                  f"{self.provider_pref})",
                                  {"expected": {"uci": bool(c.uci_competition_url),
                                                "pcs": sorted(pcs_ingest.PAGE_FILES.values())}})
        store_rows = self._crosswalk_store_rows()
        db = self.db_path if self.db_path.exists() else None
        if provider == "uci":
            report = uci_ingest.ingest(c.dir, unit, crosswalk_csv=self.crosswalk_csv, store_rows=store_rows, db_path=db,
                                       aliases_csv=self.aliases_csv, identity_policy=self.identity_policy)
        else:
            report = pcs_ingest.ingest(c.dir, unit, crosswalk_csv=self.crosswalk_csv, store_rows=store_rows, db_path=db)
        for kind, meta in report.pages.items():
            try:
                self.store.insert_acquisition_raw(self.run["run_id"], c.slug, unit, provider, kind, meta.get("source_url") or "",
                                                  object_key=None, ingest_verdict=report.verdict,
                                                  ingest_detail={"sha256": meta["sha256"], "bytes": meta["bytes"], "file": meta["file"],
                                                                 "event_code": meta.get("event_code"), "race_name": meta.get("race_name"),
                                                                 "fallback_reason": self.record.get("fallback_reason"),
                                                                 "failing": report.failing if not report.ok else []},
                                                  fetched_at=meta.get("fetched_at"))
            except Exception as exc:  # noqa: BLE001
                self._say(f"  [store] insert_acquisition_raw failed: {exc}")
        proposals = list(getattr(report, "proposals", []) or [])
        inserted = 0
        for prop in proposals:                       # one row per insert: PostgREST bulk inserts need identical keys
            try:
                self.store.insert_crosswalk_proposals([prop])
                inserted += 1
            except Exception as exc:  # noqa: BLE001
                self._say(f"  [store] insert_crosswalk_proposals failed: {exc}")
        if inserted:
            self._say(f"  {inserted} crosswalk proposal(s) inserted (source=uci)")
        for w in report.warnings:
            self._say(f"  note: {w}")
        if not report.ok:
            raise WaitingForInput("ingest_failed", f"{c.slug} {unit}: {provider} ingest rejected ({len(report.failing)} checks)",
                                  {"provider": provider, "checks": report.failing, "unresolved_riders": report.unresolved,
                                   "proposals": proposals, "warnings": report.warnings})
        self._file_provisional_identity_task(unit, report)
        return {"provider": provider, "verdict": report.verdict, "n_classified": report.n_classified, "n_abandons": report.n_abandons,
                "winner": report.winner, "winning_time": report.winning_time, "written": report.written,
                "identity_policy": report.identity_policy, "provisional_top": report.provisional_top,
                "warnings": report.warnings, "_detail": {"provider": provider, "winner": report.winner, "n_classified": report.n_classified,
                                                          "provisional_top": len(report.provisional_top)}}

    def _file_provisional_identity_task(self, unit: str, report: Any) -> None:
        """One ROUTINE task per unit listing the top-gate rows archived under a provisional id.

        Deliberately not a ``WaitingForInput``: under ``identity_policy=provisional`` the settle
        finishes and publishes with a visible caveat, and this task only asks the operator to confirm
        the mapping at leisure (inbox → ``crosswalk confirm`` → ``crosswalk reconcile-results`` on the
        weekly Mac run).  Operator ruling 2026-09-16.
        """
        rows = list(getattr(report, "provisional_top", None) or [])
        if not rows:
            return
        c = self.campaign
        names = ", ".join(f"{r['uci_name']} (place {r['place']})" for r in rows[:6])
        task = build_operator_task(
            "identity_provisional", c.slug if c else None,
            f"{c.slug if c else '-'} {unit}: {len(rows)} top-gate rider(s) published under a provisional id — {names}",
            {"unit": unit, "phase": self.record.get("phase"), "run_id": (self.run or {}).get("run_id"),
             "identity_policy": getattr(report, "identity_policy", None),
             "provisional": [{"place": r["place"], "uci_name": r["uci_name"], "rider_id": r["rider_id"],
                              "team": r["team"], "age": r["age"],
                              "best_candidate": (r.get("best") or {}).get("fc_name"),
                              "best_fc_rider_id": (r.get("best") or {}).get("fc_rider_id"),
                              "best_confidence": (r.get("best") or {}).get("confidence")} for r in rows],
             "next_step": ("confirm the mapping in the inbox, then run "
                           "`python -m cycling_project.nightly.crosswalk reconcile-results --campaign <dir>` "
                           "on the Mac to rewrite the archived id")},
            urgency="routine")
        task["run_id"] = (self.run or {}).get("run_id")
        try:
            self.store.insert_task(task)
            self._say(f"  routine task filed: {len(rows)} provisional top-gate identity(ies)")
        except Exception as exc:  # noqa: BLE001 — a routine task must never fail a settle
            self._say(f"  [store] insert_task(identity_provisional) failed: {exc}")

    def _template_gc_config(self, gc_cfg_path: Path, stage: int) -> Dict[str, Any]:
        c = self.campaign
        cfg = _read_json(gc_cfg_path, {})
        unit = c.unit_for(stage)
        res_dir = c.results_dir(unit)
        gc_rows = list(csv.DictReader(open(res_dir / "gc.csv", newline="", encoding="utf-8"))) if (res_dir / "gc.csv").exists() else []
        st_rows = list(csv.DictReader(open(res_dir / "results.csv", newline="", encoding="utf-8"))) if (res_dir / "results.csv").exists() else []
        classified = [r for r in st_rows if str(r.get("place", "")).isdigit()]
        winner = classified[0]["name"] if classified else None
        win_time = None
        rj = _read_json(res_dir / "results.json")
        if rj:
            win_time = rj.get("race_time")
        finish = None
        for s in c.stages:
            if int(s["number"]) == stage and s.get("towns"):
                finish = str(s["towns"]).split("→")[-1].split("-")[-1].strip()
        parts = []
        if winner:
            parts.append(f"{winner} won the stage" + (f" in {fmt_gap(win_time)}" if win_time else "") + ".")
        if gc_rows:
            lead = gc_rows[0]
            chasers = ", ".join(f"{r['name']} {fmt_gap(float(r['gap']))}" for r in gc_rows[2:6] if r.get("gap") not in (None, ""))
            second = gc_rows[1] if len(gc_rows) > 1 else None
            gc_txt = f"GC: {lead['name']} leads"
            if second is not None and second.get("gap") not in (None, ""):
                gc_txt += f" {second['name']} by {fmt_gap(float(second['gap']))}"
            if chasers:
                gc_txt += f", {chasers}"
            parts.append(gc_txt + ".")
        voids = sorted(set(c.void_stages) | set(int(v) for v in (cfg.get("void_stages") or [])))
        if voids:
            parts.append(("Stage " if len(voids) == 1 else "Stages ") + ", ".join(str(v) for v in voids)
                         + " cancelled, passed as a void stage.")
        parts.append("Rerun after each evening's seed_state_cache.py.")
        sentence = f"State through stage {stage}" + (f" ({finish})" if finish else "") + ": " + " ".join(parts)

        changed = []
        for key, spec in (cfg.get("scenarios") or {}).items():
            if not isinstance(spec, dict):
                continue
            label = str(spec.get("label") or "")
            new_label, n = re.subn(r"state through stage \d+", f"state through stage {stage}", label, flags=re.I)
            if n == 0:
                new_label = f"{label} — state through stage {stage}" if label else f"GC — state through stage {stage}"
            short = str(spec.get("short") or "")
            new_short, n = re.subn(r"after stage \d+", f"after stage {stage}", short, flags=re.I)
            if n == 0:
                new_short = f"GC after stage {stage}"
            note = str(spec.get("note") or "")
            matches = list(STATE_SENTENCE_RE.finditer(note))
            if matches:
                new_note = note[:matches[-1].start()].rstrip() + (" " if note[:matches[-1].start()].strip() else "") + sentence
            else:
                new_note = (note.rstrip() + " " if note.strip() else "") + sentence
            if (new_label, new_short, new_note) != (label, short, note):
                spec["label"], spec["short"], spec["note"] = new_label, new_short, new_note
                changed.append(key)
        date_s = c.stage_date(stage)
        if date_s:
            cfg["date"] = date_s
        cfg["void_stages"] = voids
        gc_event_id = None if _is_placeholder(cfg.get("event_id"), numeric=True) else str(cfg["event_id"]).strip()
        snap = self._newest_snapshot(date_s, gc_event_id) if date_s else None
        if snap:
            cfg["odds_capture"] = snap
        _write_json(gc_cfg_path, cfg)
        return {"changed": changed, "state_sentence": sentence, "odds_capture": cfg.get("odds_capture"),
                "_detail": {"changed": changed, "through_stage": stage}}

    def _newest_snapshot(self, day: Optional[str], event_id: Optional[str]) -> Optional[str]:
        """``YYYY-MM-DD/markets_HHMM.json`` — newest snapshot on ``day`` (or before) carrying ``event_id``."""
        odds_root = self.campaign.dir / "odds"
        if not odds_root.is_dir():
            return None
        days = sorted((p for p in odds_root.iterdir() if p.is_dir() and (day is None or p.name <= day)), reverse=True)
        for d in days:
            for f in sorted(d.glob("markets_*.json"), reverse=True):
                if event_id:
                    try:
                        if str(event_id) not in json.loads(f.read_text(encoding="utf-8")):
                            continue
                    except (OSError, json.JSONDecodeError):
                        continue
                return f"{d.name}/{f.name}"
            if day is not None and d.name == day:
                break
        return None

    def _rider_id_map(self) -> Dict[str, int]:
        from cycling_project.nightly.run_editorial import rider_id_map
        out: Dict[str, int] = {}
        for r in read_crosswalk_csv(self.crosswalk_csv):
            if r.get("fc_rider_id") and r.get("internal_rider_id"):
                try:
                    out[str(r["fc_rider_id"])] = int(r["internal_rider_id"])
                except ValueError:
                    pass
        if self.db_path.exists():
            out.update(rider_id_map(self.db_path))
        return out

    def _retro_facts(self, unit: str) -> Dict[str, Any]:
        from cycling_project.nightly.run_editorial import ONE_DAY_SCORECARD, build_facts_bundle, key_of_record
        c = self.campaign
        stage = c.stage_of(unit)
        one_day = oneday.is_one_day_unit(unit)
        id_map = self._rider_id_map()
        bundle = build_facts_bundle(c.dir, unit, "stage_retro", db_path=self.db_path if self.db_path.exists() else None,
                                    id_map=id_map, name_fallback=False)
        res_dir = c.results_dir(unit)
        rows = list(csv.DictReader(open(res_dir / "results.csv", newline="", encoding="utf-8"))) if (res_dir / "results.csv").exists() else []
        classified = sorted((r for r in rows if str(r.get("place", "")).isdigit()), key=lambda r: int(r["place"]))
        gaps = []
        for r in classified:
            try:
                gaps.append(float(r["gap"]))
            except (TypeError, ValueError):
                pass
        wg = None
        rule = None
        card_row = None if stage is None else next(
            (r for r in (_read_json(c.dir / "review" / "key_scorecard.json", []) or []) if r.get("stage") == stage), None)
        if card_row:
            wg, rule = card_row.get("wg_size"), card_row.get("rule_type")
        if wg is None and gaps:
            try:
                import numpy as np
                import pandas as pd
                from cycling_project.prediction_tools.experiments.front_local_race_typing import comp_features, rule_label
                feats = comp_features(np.sort(np.array(gaps, dtype=float)) - min(gaps))
                wg, rule = int(feats["wg_size"]), rule_label(pd.Series(feats))
            except Exception as exc:  # noqa: BLE001
                self._say(f"  note: winning group not computed ({exc})")
        results = bundle.setdefault("results", {})
        results["winner"] = classified[0]["name"] if classified else None
        results["winner_fc_rider_id"] = classified[0]["rider_id"] if classified else None
        results["winning_group"] = wg
        results["rule_type"] = rule
        results["abandons"] = [{"status": r["place"], "name": r["name"], "rider_id": r["rider_id"]} for r in rows
                               if not str(r.get("place", "")).isdigit()]
        # Provisional identities (ruling 2026-09-16), threaded straight from what the ingest wrote into
        # results.json so the editorial bundle and the page tell the reader the same thing.  Every such
        # rider is treated as NOT in the model field: no board row joins a uci: key.
        rjson = _read_json(res_dir / "results.json", {}) or {}
        results["provisional_identities"] = list(rjson.get("provisional_identities") or [])
        results["identity_policy"] = rjson.get("identity_policy")
        if card_row:
            bundle["key_vs_oracle"] = {k: card_row.get(k) for k in ("day_key", "key_source", "oracle_item", "day_class", "exact",
                                                                    "covered", "weight_on_true", "agent_key", "agent_exact",
                                                                    "agent_covered", "agent_weight_on_true", "agent_flagged")}
            bundle["key_vs_oracle"]["key_of_record"] = key_of_record(card_row)
        elif one_day:
            bundle["key_vs_oracle"] = {"scored": False, **ONE_DAY_SCORECARD}
        else:
            bundle["key_vs_oracle"] = {"scored": False}
        bundle["retrieval_summary"] = [{
            "scenario_key": b.get("scenario_key"), "post_hoc": b.get("post_hoc"),
            "pool15_with_key": (b.get("retrieval") or {}).get("top15_finishers_in_top15_with_key"),
            "pool15_production": (b.get("retrieval") or {}).get("top15_finishers_in_top15_production"),
        } for b in bundle.get("boards") or []]
        bundle["bundle_kind"] = "driver"
        bundle["join"] = "rider_id (fc → internal via crosswalk + riders); names never used"
        bundle["run_id"] = self.run["run_id"]
        path = c.pred_dir(unit) / "retro_facts.json"
        _write_json(path, bundle)
        return {"path": str(path), "winner": results["winner"], "winning_group": wg,
                "provisional_identities": results["provisional_identities"],
                "retrieval": bundle["retrieval_summary"],
                "_detail": {"winner": results["winner"], "winning_group": wg}}

    def _build_pages(self, unit: str) -> None:
        c = self.campaign
        pred = c.pred_dir(unit)
        cfg = pred / "scenarios.json"
        if cfg.exists() and c.stage_of(unit) is not None:
            if self.record.get("phase") == "settle" and not _has_scenario_boards(pred):
                # A stage that was never previewed can still be settled honestly:
                # results, scoring and retro_facts are useful, but there is no
                # pre-race board from which to construct a stage page.
                self.step("stage_page", lambda: None,
                          skip="retrospective-only settlement: no pre-race boards")
            else:
                r = self.script("stage_page", [self.python, SCRIPTS["stage_page"], cfg])
                if not r.get("skipped"):
                    self._expect_page(SITE_DIR / c.stage_page_name(c.stage_of(unit)), "stage_page")
        elif cfg.exists() and oneday.is_one_day_unit(unit):
            r = self.script("oneday_page", [self.python, SCRIPTS["oneday_page"], cfg])
            if not r.get("skipped"):
                self._expect_page(SITE_DIR / c.oneday_page_name(), "oneday_page")
        else:
            self.step("stage_page", lambda: None, skip="no scenario config for this unit")
        r = self.script("site_index", [self.python, SCRIPTS["site_index"]])
        if not r.get("skipped"):
            self._expect_page(SITE_DIR / site_paths.SITE_INDEX_NAME, "site_index")
        r = self.script("site_frame", [self.python, SCRIPTS["site_frame"]])
        if not r.get("skipped"):
            self._expect_page(SITE_DIR / site_paths.FRAME_DIR, "site_frame")
        # The tracker either writes its page or exits non-zero, so after an ok
        # gc_tracker step the page's absence is a failure, not a quiet omission.
        if self.record.get("phase") == "settle" and any(s["step"] == "gc_tracker" and s["state"] == "ok" for s in self.record["steps"]):
            self._expect_page(SITE_DIR / c.gc_page_name(), "gc_tracker")

    def _expect_page(self, path: Path, built_by: str) -> None:
        """Record a page a builder reported building — or fail the run when it is not there.

        The builder subprocess exited 0, so this is the only place a page it did not
        write can be caught (2026-09-21: CRO Race stage_01 staged nothing and exited 0).
        A directory counts when it holds at least one file.
        """
        present = path.is_file() or (path.is_dir() and any(p.is_file() for p in path.rglob("*")))
        if not present:
            raise DriverFailure("page_missing", f"{built_by} reported ok but {path} was not written",
                                detail={"path": str(path), "built_by": built_by,
                                        "expected_pages": self.campaign.own_page_names(self.record.get("unit") or "")})
        self.built_pages.append(path)

    # ------------------------------------------------------------------------
    # preview
    # ------------------------------------------------------------------------
    def preview(self, unit: str) -> Tuple[int, Dict[str, Any]]:
        return self.run_phase(unit, "preview", lambda: self._preview_body(unit))

    def _preview_body(self, unit: str) -> Dict[str, Any]:
        c = self.campaign
        stage = c.stage_of(unit)
        out: Dict[str, Any] = {}

        # 1. odds
        r = self.script("capture_odds", [self.python, SCRIPTS["capture_odds"], "--campaign", c.dir], ok_codes=(0, 1))
        if not r.get("skipped") and r.get("returncode") == 1 and not odds_required(c.cfg.get("category")):
            self._say(f"  note: Kambi lists no market for {c.slug} ({c.cfg.get('category')}): preview continues without the book benchmark")
            out["odds"] = {"market": None, "reason": "no_kambi_market", "category": c.cfg.get("category")}
        elif not r.get("skipped") and r.get("returncode") == 1:
            raise WaitingForInput("kambi_match", f"{c.slug}: Kambi answered but the race was not matched — confirm kambi_candidates in campaign.json",
                                  {"tail": (r.get("stdout") or "")[-800:]})
        if not r.get("skipped") and "degraded" in (r.get("stdout") or "").lower():
            self._say("  note: odds capture degraded (every brand blocked) — bookless preview")
            out["odds"] = "degraded"
        new_ids = c.refresh_event_ids()          # the capture writes ids into campaign.json; step 2 reads them
        if new_ids:
            self._say(f"  note: campaign.json gained event id(s): {', '.join(sorted(new_ids))}")

        # 2. stage config: create it when absent (template if the campaign ships one, else
        # from campaign.json itself) and fill event id + capture.  References stay empty here:
        # they are judgment tied to the day key, which is only resolved at step 5.
        out["config"] = self.step("stage_config", lambda: self._ensure_config(unit))
        cfg_path = c.pred_dir(unit) / "scenarios.json"

        # 2a. the field.  Every board is built on a start list, and the serving runner will go to
        # FirstCycling for one it cannot find — a scrape the cloud container cannot make.  Ask for
        # the handover here, cheaply, instead of failing inside predict (task 93, 2026-09-17).
        # Every unit is checked, not only the opening one: the serving slice's cache is frozen at
        # release time, so a mid-race stage of a race the release never saw has no field either
        # (Tour of Huangshan stage 2, 2026-09-18 — a failed predict and a paid triage).
        out["startlist"] = self.step("startlist", lambda: self._require_startlist(unit))

        # 2b. the GC board's config, so the settle step has something to re-stamp
        if stage is not None and c.is_stage_race and not (c.pred_dir("gc") / "scenarios.json").exists():
            out["gc_config"] = self.step("gc_config", lambda: self._ensure_gc_config())
        else:
            self.step("gc_config", lambda: None,
                      skip="predictions/gc/scenarios.json exists" if stage is not None else "one-day race: no GC")

        # 3. route facts from the acquisition thread's route_raw (or an operator override)
        pred = c.pred_dir(unit)
        if (pred / "route_raw.json").exists() or (pred / "route.override.json").exists():
            out["route"] = self.step("route_facts", lambda: self._route_facts(unit))
        else:
            self.step("route_facts", lambda: None, skip="no route_raw.json / route.override.json")

        # 4. bundle
        if stage is not None:
            out["bundle"] = self.step("bundle", lambda: self._bundle(unit))
        else:
            self.step("bundle", lambda: None, skip="one-day race: no day key bundle")

        # 5. the key (approved, else agent shadow, else exit 10)
        out["key"] = self.step("day_key", lambda: self._resolve_key(unit))

        # 5b. references, derived from the key that was just resolved.  References a config
        # already carries are checked first: one the serving DB cannot profile would otherwise
        # surface as a traceback tail inside predict (Tour de Luxembourg stage 4, 2026-09-18).
        out["refs_check"] = self.step("refs_check", lambda: self._check_refs(unit))
        missing = autoconfig.scenarios_missing_refs(_read_json(cfg_path, {}) or {})
        if missing:
            out["refs"] = self.step("scenario_refs", lambda: self._scenario_refs(unit, out.get("key") or {}))
        else:
            self.step("scenario_refs", lambda: None, skip="every scenario already carries references")

        # 6. predict
        self.script("predict", self._predict_argv(cfg_path), lock=True)

        # 7. validate
        out["validate"] = self.step("validate", lambda: self._validate(unit, require_boards=not self.dry_run))

        # 8. pages, 9. upload
        self._build_pages(unit)
        out["upload"] = self.step("upload", lambda: self._upload(unit, "preview"))
        return out

    def _ensure_config(self, unit: str) -> Dict[str, Any]:
        c = self.campaign
        stage = c.stage_of(unit)
        pred = c.pred_dir(unit)
        cfg_path = pred / "scenarios.json"
        created = False
        cfg = _read_json(cfg_path)
        if cfg is None and stage is None:
            # A one-day race is its own reference set: the default scenario's refs are
            # this race's own recent editions, looked up from the serving database, so a
            # one-day preview is not blocked on a human writing reference ids.
            refs = oneday.own_edition_refs(c.fc_race_id, c.year,
                                           db_path=self.db_path if self.db_path.exists() else None)
            if not refs:
                raise WaitingForInput("scenarios_needed",
                                      f"{c.slug} {unit}: no earlier edition of race {c.fc_race_id} in the "
                                      "database to build the default reference set from — write "
                                      "predictions/race/scenarios.json by hand",
                                      {"path": str(cfg_path)})
            cfg = oneday.build_config(
                fc_race_id=c.fc_race_id, year=c.year,
                date=c.stage_date(None) or c.cfg.get("start_date"),
                label=c.cfg.get("name") or c.slug,
                refs=refs, tag_prefix=f"{c.slug}_race")
            created = True
        elif cfg is None and _read_json(c.dir / "predictions" / TEMPLATE_NAME) is None:
            # No human ever wrote a template for this race — the common case, and until
            # 2026-09-16 the end of the thread.  The config is built from campaign.json:
            # one scenario, no references (the key at step 5 chooses them), no odds
            # provenance (the odds step fills it when Kambi lists a market).
            entry = next((x for x in c.stages if int(x["number"]) == stage), None)
            cfg = autoconfig.build_stage_skeleton(
                slug=c.slug, stage=stage, fc_race_id=c.fc_race_id, year=c.year,
                date=c.stage_date(stage), label=autoconfig.stage_label(stage, entry),
                void_stages=sorted(set(c.void_stages) | set(int(v) for v in ((c.previous_config(stage) or {}).get("void_stages") or []))))
            created = True
        elif cfg is None:
            template = _read_json(c.dir / "predictions" / TEMPLATE_NAME)
            cfg = json.loads(json.dumps(template))
            cfg.pop("day_key", None)
            cfg.pop("day_key_note", None)
            cfg["stage"] = stage
            cfg["label"] = f"Stage {stage}"
            cfg["fc_race_id"] = c.fc_race_id or cfg.get("fc_race_id")
            cfg["year"] = c.year or cfg.get("year")
            cfg["date"] = c.stage_date(stage) or cfg.get("date")
            prev = c.previous_config(stage)
            cfg["void_stages"] = sorted(set(int(v) for v in ((prev or {}).get("void_stages") or [])) | set(c.void_stages))
            for key, spec in (cfg.get("scenarios") or {}).items():
                if isinstance(spec, dict):
                    spec["tag"] = re.sub(r"_st\d+_", f"_st{stage:02d}_", str(spec.get("tag") or f"{c.slug}_st{stage:02d}_{key}"))
                    spec["refs"] = []                       # placeholders are never carried forward
            created = True
        # Fill event id + odds capture when absent — a config just made from the template
        # carries sentinels, which are truthy but are not values (see _is_placeholder).
        filled = []
        normalized = False
        event_id_placeholder = _is_placeholder(cfg.get("event_id"), numeric=True)
        event_id = None if event_id_placeholder else str(cfg["event_id"]).strip()
        if event_id is None:
            eid = (c.cfg.get("kambi_event_ids") or {}).get(unit)
            if eid:
                cfg["event_id"] = event_id = str(eid)
                filled.append("event_id")
            elif event_id_placeholder and cfg.get("event_id") is not None:
                # A template sentinel is never publishable provenance.  Keep an
                # unresolved market explicitly absent until capture finds its id.
                cfg["event_id"] = None
                normalized = True
        if _is_placeholder(cfg.get("odds_capture")):
            # Without an event id, "newest" may belong to another stage/race.
            # Do not attach unrelated market provenance merely because it shares a date.
            snap = self._newest_snapshot(str(self.today), event_id) if event_id else None
            if snap:
                cfg["odds_capture"] = snap
                filled.append("odds_capture")
            elif cfg.get("odds_capture") is not None:
                cfg["odds_capture"] = None
                normalized = True
        if created or filled or normalized:
            _write_json(cfg_path, cfg)
        return {"path": str(cfg_path), "created": created, "filled": filled, "event_id": cfg.get("event_id"),
                "odds_capture": cfg.get("odds_capture"), "_detail": {"created": created, "filled": filled}}

    def _cached_startlist_size(self, fc_race_id: Optional[str], year: Optional[int]) -> Optional[int]:
        """Rows in ``cached_start_lists`` for this race/year, or None when the table cannot be read.

        Read straight from the serving slice rather than through ``future_race_loader`` so the
        check costs one query and never creates the cache tables as a side effect.
        """
        if not fc_race_id or not year or not self.db_path.exists():
            return None
        try:
            con = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
            try:
                row = con.execute("select count(*) from cached_start_lists where fc_race_id = ? and year = ?",
                                  (str(fc_race_id), int(year))).fetchone()
                return int(row[0]) if row else 0
            finally:
                con.close()
        except sqlite3.Error as exc:
            self._say(f"  note: cached_start_lists unreadable ({exc})")
            return None

    def _require_startlist(self, unit: str) -> Dict[str, Any]:
        """The field must already be here: a handover file or a cache row, never a live scrape.

        ``predict_stage_scenarios.resolve_startlist`` reads ``startlist.json`` beside the config
        first, then ``cached_start_lists``, and only then goes to the network.  In the cloud that
        third path is a Cloudflare 403 inside the runner, which surfaces as a bare exit 20 and buys
        a paid triage cycle instead of a one-line ask.  The Mac's daily ``nightly.horizon`` capture
        is what supplies the missing list, usually the next morning.
        """
        c = self.campaign
        handover = oneday.startlist_path(c.pred_dir(unit))
        found = oneday.find_startlist(c.pred_dir(unit))     # beside the config, else a sibling unit's
        if found is not None:
            path, label = found
            return {"source": label, "path": str(path), "_detail": {"source": label}}
        cached = self._cached_startlist_size(c.fc_race_id, c.year)
        if cached:
            return {"source": "cache", "riders": cached, "_detail": {"source": "cache", "riders": cached}}
        if self.allow_scrape:
            # An attended Mac run may fetch it; say so rather than pretending the list is here.
            self._say("  note: no start list on disk or in the cache — the runner will scrape it (--allow-scrape)")
            return {"source": "scrape_allowed", "_detail": {"source": "scrape_allowed"}}
        raise WaitingForInput(
            "startlist_needed",
            f"{c.slug} {unit}: no start list — nothing at predictions/{unit}/{oneday.STARTLIST_NAME}, none beside "
            f"any other unit of the campaign, and no "
            f"cached_start_lists rows for race {c.fc_race_id} {c.year}. The Mac's daily horizon capture supplies "
            "it once FirstCycling publishes the list; the container never scrapes.",
            {"handover": str(handover), "fc_race_id": c.fc_race_id, "year": c.year,
             "cached_rows": cached,
             "next_step": f"uv run python -m cycling_project.nightly.horizon --campaign {c.slug} --store auto (Mac, visible Chrome)"})

    def _predict_argv(self, cfg_path: Path, *, no_log: Optional[bool] = None) -> List[str]:
        """``predict_stage_scenarios.py`` argv with the scrape policy applied."""
        argv = [self.python, SCRIPTS["predict"], cfg_path]
        if (self.no_log if no_log is None else no_log):
            argv.append("--no-log")
        if not self.allow_scrape:
            argv.append("--no-scrape")
        return [str(a) for a in argv]

    def _route_facts(self, unit: str) -> Dict[str, Any]:
        from cycling_project.nightly.route_facts import RouteFactsError, ingest_route
        try:
            res = ingest_route(self.campaign.dir, unit, write=not self.dry_run)
        except RouteFactsError as exc:
            self._say(f"  note: route facts not ingested ({exc})")
            return {"route_facts": "missing", "error": str(exc)}
        grade = res.get("route_facts") if isinstance(res, dict) else None
        return {"route_facts": grade, "_detail": {"route_facts": grade}}

    def _bundle(self, unit: str) -> Dict[str, Any]:
        from cycling_project.nightly.run_day_key import build_bundle
        stage = self.campaign.stage_of(unit)
        manifest = build_bundle(self.campaign.dir, stage, force=self.force)
        return {"manifest_sha256": manifest.get("manifest_sha256"), "odds": manifest.get("odds"),
                "route_facts": manifest.get("route_facts"), "files": len(manifest.get("entries", [])),
                "notes": manifest.get("notes"), "_detail": {"odds": manifest.get("odds"), "route_facts": manifest.get("route_facts")}}

    def _resolve_key(self, unit: str) -> Dict[str, Any]:
        c = self.campaign
        stage = c.stage_of(unit)
        cfg_path = c.pred_dir(unit) / "scenarios.json"
        cfg = _read_json(cfg_path, {})
        # References used to be gated here; since 2026-09-16 they are derived from the key
        # itself, one step later (``_scenario_refs``).
        if stage is None:
            return {"source": "one_day", "day_key": None}
        if cfg.get("day_key"):
            return {"source": cfg.get("day_key_source") or "config", "day_key": cfg["day_key"]}
        approved = None
        try:
            approved = self.store.approved_day_key(c.slug, unit)
        except Exception as exc:  # noqa: BLE001
            self._say(f"  [store] approved_day_key failed: {exc}")
        if approved:
            key = (approved.get("evidence") or {}).get("key") if isinstance(approved.get("evidence"), dict) else None
            key = rec.normalise_key(key) if key else {str(approved["day_key"]): 1.0}
            cfg["day_key"] = key
            cfg["day_key_source"] = f"store:approved:{approved.get('id')}"
            if approved.get("rationale"):
                cfg["day_key_note"] = approved["rationale"]
            _write_json(cfg_path, cfg)
            return {"source": cfg["day_key_source"], "day_key": key}
        agent_path = self._agent_key_path(unit)
        if agent_path is not None:
            record = _read_json(agent_path, {})
            # The reader answers in the model-facing shape (`key_items`, a list); run_day_key folds it
            # into the §5.1 `key` mapping before writing. When the coordinator saves the raw answer
            # instead, the fold never ran (2026-09-22, CRO Race st2, task 116; the same "carries no
            # key" retry on 09-18/19/21). Accept either shape: normalise_key folds the list itself.
            key = rec.normalise_key(record.get("key") or record.get("key_items") or {})
            if not key:
                raise DriverFailure("agent_key_invalid", f"{agent_path} carries no key (neither `key` nor `key_items`)")
            cfg["day_key"] = key
            # The board is priced from a machine-written key.  ``day_key_author`` is what keeps
            # the two reads apart everywhere downstream: score_day_keys leaves the tier-3 card
            # unkeyed for such a config and scores the record through --also agent, and the
            # stage page says on its face that no person wrote this key.
            cfg["day_key_author"] = "agent"
            cfg["day_key_source"] = f"agent:{agent_path.name}"
            if record.get("rationale") or record.get("reasoning"):
                cfg.setdefault("day_key_note", str(record.get("rationale") or record.get("reasoning")))
            _write_json(cfg_path, cfg)
            return {"source": cfg["day_key_source"], "day_key": key, "author": "agent",
                    "path": str(agent_path), "explicit": bool(self.agent_key)}
        raise WaitingForInput("day_key_needed", f"{c.slug} {unit}: day key needed (no config key, no approved day_key_decisions row, "
                                                f"no agent record at predictions/{unit}/{AGENT_KEY_FILES[0]})",
                              {"path": str(cfg_path), "bundle": str(c.pred_dir(unit) / "bundle"),
                               "agent_key_paths": [str(c.pred_dir(unit) / n) for n in AGENT_KEY_FILES]})

    def _agent_key_path(self, unit: str) -> Optional[Path]:
        """The agent's decision record for this unit: ``--agent-key`` if given, else the one the
        day-key-reader leaves beside the config.

        Looking for it without the flag is what lets a single unattended pass price the board:
        the coordinator writes the record and re-runs ``preview``, and the second pass finds it
        with no extra argument to remember (owner requirement, 2026-09-17).
        """
        if self.agent_key:
            return self.agent_key if self.agent_key.exists() else None
        pred = self.campaign.pred_dir(unit)
        return next((p for p in (pred / n for n in AGENT_KEY_FILES) if p.exists()), None)

    # -- references, derived from the key ---------------------------------------
    def _scenario_refs(self, unit: str, key_result: Dict[str, Any]) -> Dict[str, Any]:
        """Fill every reference-less scenario from the resolved day key (2026-09-16).

        References are judgment, but they are judgment *about the key*: the key names the
        shape of the day, the menu's canonical signature maps that shape to an archetype,
        and the archetype names the days worth averaging into a profile.  A human writing
        them by hand was the last hard gate on a stage race with no template.  An
        auto-written config also gains its alternate branch here — the key's
        second-weighted family — because that too is only knowable once the key exists.
        """
        c = self.campaign
        stage = c.stage_of(unit)
        cfg_path = c.pred_dir(unit) / "scenarios.json"
        cfg = _read_json(cfg_path, {}) or {}
        key = key_result.get("day_key") or cfg.get("day_key")
        if stage is None:
            return {"skipped": "one-day race: references are the race's own editions"}
        if not key:
            raise WaitingForInput("scenarios_needed", f"{c.slug} {unit}: no day key, so no archetype to choose references from",
                                  {"path": str(cfg_path)})
        key = rec.normalise_key(key)
        added = None
        if cfg.get("config_source") == autoconfig.CONFIG_SOURCE:
            alt = autoconfig.alternate_scenario(key, slug=c.slug, stage=stage)
            if alt and alt[0] not in (cfg.get("scenarios") or {}):
                cfg["scenarios"][alt[0]] = alt[1]
                added = alt[0]
        try:
            report = autoconfig.fill_scenario_refs(
                cfg, key=key, slug=c.slug, campaign_dir=c.dir,
                db_path=self.db_path if self.db_path.exists() else None,
                signatures=self.signatures, category=c.cfg.get("category"))
        except autoconfig.AutoConfigError as exc:
            # The genuinely impossible case: no signature table (and, for a one-day, no own
            # editions).  Ask a human rather than guessing a reference set.
            raise WaitingForInput("scenarios_needed", f"{c.slug} {unit}: {exc}",
                                  {"path": str(cfg_path), "scenarios": autoconfig.scenarios_missing_refs(cfg)}) from exc
        _write_json(cfg_path, cfg)
        detail = {"scenarios": report["scenarios"], "alternate": added,
                  "archetypes": {k: v["archetype"] for k, v in report["filled"].items()}}
        return {**detail, "source": autoconfig.REFS_SOURCE, "day_key": key, "_detail": detail}

    def _check_refs(self, unit: str) -> Dict[str, Any]:
        """Every reference must have a ``competition_field_features`` row in the serving DB.

        A machine-written set with a bad id is emptied (``scenario_refs`` rewrites it next); a
        human-written one is never edited, so it waits with the ids named.
        """
        c = self.campaign
        cfg_path = c.pred_dir(unit) / "scenarios.json"
        cfg = _read_json(cfg_path, {}) or {}
        if not self.db_path.exists():
            return {"checked": False, "reason": "no serving DB", "_detail": {"checked": False}}
        healed, blocking = autoconfig.drop_unservable_auto_refs(cfg, self.db_path)
        if blocking:
            named = "; ".join(f"{k}: {', '.join(str(i) for i in v)}" for k, v in sorted(blocking.items()))
            raise WaitingForInput(
                "scenarios_needed",
                f"{c.slug} {unit}: reference competition id(s) with no competition_field_features row in the "
                f"serving DB, so no profile can be built — {named}. Replace them in {cfg_path.name} "
                "(`python -m cycling_project.nightly.refs` lists candidates) or cut a release that carries them.",
                {"path": str(cfg_path), "unservable_refs": blocking})
        if healed and not self.dry_run:
            _write_json(cfg_path, cfg)
        if healed:
            self._say("  note: dropped machine-written reference set(s) holding unservable ids: "
                      + "; ".join(f"{k}: {v}" for k, v in sorted(healed.items())))
        return {"checked": True, "healed": healed, "_detail": {"checked": True, "healed": sorted(healed)}}

    def _ensure_gc_config(self) -> Dict[str, Any]:
        """Create ``predictions/gc/scenarios.json`` for a stage race that has none.

        The settle step only re-stamps a GC config that already exists, so without this a
        machine-run stage race never shows a general-classification board.  References are
        this race's own earlier editions when the database holds at least three, else recent
        GC competitions from the signature table.  A GC board is a bonus, never a blocker:
        when no reference set can be found the step says so and the preview goes on.
        """
        c = self.campaign
        gc_path = c.pred_dir("gc") / "scenarios.json"
        try:
            refs, source = autoconfig.gc_refs(
                fc_race_id=c.fc_race_id, year=c.year, campaign_dir=c.dir,
                db_path=self.db_path if self.db_path.exists() else None,
                signatures=self.signatures, category=c.cfg.get("category"))
        except autoconfig.AutoConfigError as exc:
            self._say(f"  note: no GC config written ({exc})")
            return {"created": False, "reason": str(exc), "_detail": {"created": False}}
        if not refs:
            self._say("  note: no GC config written (no own editions and no GC days in the signature table)")
            return {"created": False, "reason": "no_refs", "_detail": {"created": False}}
        cfg = autoconfig.build_gc_skeleton(
            slug=c.slug, fc_race_id=c.fc_race_id, year=c.year,
            date=c.cfg.get("end_date") or c.stage_date(None), refs=refs, source=source,
            void_stages=c.void_stages, race_name=c.cfg.get("name"))
        problems = autoconfig.validate_gc_config(cfg)
        if problems:
            raise DriverFailure("gc_config_invalid", f"{c.slug}: generated GC config is invalid: {'; '.join(problems)}")
        _write_json(gc_path, cfg)
        return {"created": True, "path": str(gc_path), "refs": refs, "refs_source": source,
                "_detail": {"created": True, "refs_source": source}}

    # ------------------------------------------------------------------------
    # validate
    # ------------------------------------------------------------------------
    def _validate(self, unit: str, *, require_boards: bool = True) -> Dict[str, Any]:
        c = self.campaign
        stage = c.stage_of(unit)
        pred = c.pred_dir(unit)
        cfg_path = pred / "scenarios.json"
        problems: List[str] = []
        warnings: List[str] = []
        cfg = _read_json(cfg_path)
        if not cfg:
            raise WaitingForInput("validate_failed", f"{c.slug} {unit}: no scenarios.json", {"path": str(cfg_path)})
        for k in ("fc_race_id", "year", "date", "scenarios"):
            if k not in cfg:
                problems.append(f"config lacks {k}")
        event_id = cfg.get("event_id")
        if event_id not in (None, "") and _is_placeholder(event_id, numeric=True):
            problems.append("config event_id is an unresolved/invalid placeholder")
        odds_capture = cfg.get("odds_capture")
        if odds_capture not in (None, "") and _is_placeholder(odds_capture):
            problems.append("config odds_capture is an unresolved placeholder")
        if stage is not None and int(cfg.get("stage", -1)) != stage:
            problems.append(f"config stage {cfg.get('stage')} != {stage}")
        if stage is None and oneday.is_one_day_unit(unit):
            # The one-day shape: target, no stage, no void stages, no day key, real refs.
            problems.extend(oneday.validate_config(cfg))

        def _check_key(where: str, key: Any) -> None:
            if key is None:
                return
            try:
                norm = rec.normalise_key(key)
            except Exception as exc:  # noqa: BLE001
                problems.append(f"{where}: unreadable day_key ({exc})")
                return
            bad = [i for i in norm if i not in rec.MENU_ITEMS]
            if bad:
                problems.append(f"{where}: unknown items {bad}")
            if any(i in rec.FORBIDDEN_ITEMS for i in norm):
                problems.append(f"{where}: forbidden item res_5")
            if abs(sum(norm.values()) - 1.0) > rec.WEIGHT_TOLERANCE:
                problems.append(f"{where}: weights sum to {sum(norm.values()):.3f}")

        _check_key("config root", cfg.get("day_key"))
        late = False
        try:
            late = dt.date.fromisoformat(str(cfg.get("date"))) < self.today
        except (TypeError, ValueError):
            pass
        for key, spec in (cfg.get("scenarios") or {}).items():
            if not isinstance(spec, dict):
                problems.append(f"scenario {key}: not an object")
                continue
            if not spec.get("tag"):
                problems.append(f"scenario {key}: no tag")
            refs = [x for x in (spec.get("refs") or spec.get("base_refs") or [])]
            if not refs or any(int(x or 0) <= 0 for x in refs):
                problems.append(f"scenario {key}: placeholder/missing refs")
            _check_key(f"scenario {key}", spec.get("day_key"))
            post_hoc = key == "hindsight" or str(spec.get("label", "")).lower().startswith("hindsight") or bool(spec.get("post_hoc"))
            if late and not cfg.get("day_key") and not post_hoc:
                problems.append(f"scenario {key}: config dated {cfg.get('date')} written after the stage must carry post_hoc: true")
            if spec.get("hidden"):
                continue
            board = pred / f"{key}.json"
            if not board.exists():
                (problems if require_boards else warnings).append(f"scenario {key}: board {board.name} missing")
                continue
            try:
                def _no_nan(x: str) -> Any:
                    raise ValueError(f"non-finite token {x}")
                data = json.loads(board.read_text(encoding="utf-8"), parse_constant=_no_nan)
            except ValueError as exc:
                problems.append(f"scenario {key}: {exc}")
                continue
            riders = data.get("riders") or []
            if not riders:
                problems.append(f"scenario {key}: empty board")
                continue
            lr = [r.get("lambdarank_win_p") for r in riders]
            if any(v is None or (isinstance(v, float) and not math.isfinite(v)) for v in lr):
                problems.append(f"scenario {key}: lambdarank_win_p missing/non-finite")
            else:
                s = sum(float(v) for v in lr)
                if abs(s - 1.0) > LAMBDARANK_SUM_TOL:
                    problems.append(f"scenario {key}: lambdarank_win_p sums to {s:.3f}")
            if any(r.get("predicted_rank") is None for r in riders):
                problems.append(f"scenario {key}: predicted_rank missing")
            if data.get("day_key") and cfg.get("day_key") and not spec.get("day_key") and \
                    rec.normalise_key(data["day_key"]) != rec.normalise_key(cfg["day_key"]):
                problems.append(f"scenario {key}: board keyed {data['day_key']} but config root says {cfg['day_key']} (stale board)")
        # void stages consistent with the campaign
        cfg_void = set(int(v) for v in (cfg.get("void_stages") or []))
        camp_void = set(v for v in c.void_stages if stage is None or v < stage)
        if camp_void - cfg_void:
            problems.append(f"void_stages {sorted(cfg_void)} lacks campaign void stages {sorted(camp_void - cfg_void)}")
        # crosswalk coverage of the current field
        coverage = self._crosswalk_coverage(stage)
        if coverage is not None:
            if coverage < COVERAGE_FAIL and self.identity_policy == "strict":
                problems.append(f"crosswalk coverage {coverage:.3f} < {COVERAGE_FAIL}")
            elif coverage < COVERAGE_FAIL:
                # The bar was set for the Vuelta, whose crosswalk was seeded by hand: it protects the
                # SETTLE, where a result row is tied to a FirstCycling id through the crosswalk.  It
                # says nothing about the board, which is built from FirstCycling ids throughout.
                # Under ``identity_policy=provisional`` (owner's ruling, 2026-09-16) an unresolved
                # rider settles under a provisional ``uci:`` id with a caveat, so a new race's thin
                # crosswalk must not stop its preview (Okolo Slovenska stage 4, 2026-09-18).
                warnings.append(
                    f"crosswalk coverage {coverage:.3f} < {COVERAGE_FAIL} (identity_policy=provisional: not blocking). "
                    "The board is unaffected. At the settle, riders the roster name bridge cannot resolve will be "
                    "archived under provisional uci: ids and will not join to their board rows in scoring until the "
                    "weekly crosswalk reconcile confirms them; --identity-policy strict makes this a blocking problem.")
            elif coverage < COVERAGE_WARN:
                warnings.append(f"crosswalk coverage {coverage:.3f} < {COVERAGE_WARN}")
        result = {"ok": not problems, "problems": problems, "warnings": warnings, "crosswalk_coverage": coverage,
                  "_detail": {"problems": len(problems), "warnings": len(warnings)}}
        if problems:
            raise WaitingForInput("validate_failed", f"{c.slug} {unit}: validation failed ({len(problems)} problems)",
                                  {"problems": problems, "warnings": warnings})
        return result

    def _crosswalk_coverage(self, stage: Optional[int]) -> Optional[float]:
        c = self.campaign
        latest = c.latest_results_stage(before=stage) if stage is not None else c.latest_results_stage()
        field_ids: set = set()
        if latest is not None:
            rows = csv.DictReader(open(c.results_dir(c.unit_for(latest)) / "results.csv", newline="", encoding="utf-8"))
            field_ids = {r["rider_id"] for r in rows if str(r.get("place", "")).isdigit()}
        if not field_ids:
            return None
        known = {r.get("fc_rider_id") for r in read_crosswalk_csv(self.crosswalk_csv)}
        return len(field_ids & known) / len(field_ids)

    # ------------------------------------------------------------------------
    # upload
    # ------------------------------------------------------------------------
    def _prediction_log_max_id(self) -> Optional[int]:
        if self.dry_run or not self.db_path.exists():
            return None
        try:
            con = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
            try:
                row = con.execute("select max(id) from prediction_log").fetchone()
                return int(row[0]) if row and row[0] is not None else 0
            finally:
                con.close()
        except sqlite3.Error:
            return None

    def _prediction_log_rows_since(self, watermark: Optional[int]) -> List[Dict[str, Any]]:
        if watermark is None or not self.db_path.exists():
            return []
        con = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        try:
            rows = [dict(r) for r in con.execute("select * from prediction_log where id > ? and run_key is not null", (watermark,))]
        finally:
            con.close()
        for r in rows:
            r.pop("id", None)
        return rows

    def _upload_file(self, path: Path, key_path: str, *, bucket: Optional[str] = None) -> Optional[str]:
        """Upload one file; ``None`` when it does not exist.

        The None-on-missing is for the OPTIONAL artifacts of a unit — results files a
        one-day race never writes (``gc.csv``, ``classifications.json``), a ``pcs/`` or
        ``uci/`` capture the other provider made, scorecards, the GC boards, a post-hoc
        start list, an agent key record.  Pages are never optional: ``_build_pages`` and
        ``_upload`` raise ``page_missing`` for them before this is reached.
        """
        from cycling_project.nightly.store import ARTIFACTS_BUCKET, StoreConflictError
        if not path.is_file():
            return None
        kwargs = {"bucket": bucket} if bucket else {}
        try:
            return self.store.upload_artifact(self.run["run_id"], key_path, path.read_bytes(), **kwargs)
        except StoreConflictError:
            return f"{key_path} (exists)"

    def _staging_set(self, unit: str) -> List[Tuple[Path, str]]:
        """``(file, netlify_site-relative key)`` for every built page — checked as a set before
        a single object is uploaded, so a bad set stages nothing rather than half of itself.

        * a built page that has gone missing since ``_build_pages`` → ``page_missing``;
        * a page that is neither a frame page nor one of this campaign's own pages for the
          unit → ``page_foreign`` (2026-09-21: Okolo Slovenska stage_05 staged the Tour's
          ``stage05.html`` + ``gc.html`` under its own run — task 113).
        """
        c = self.campaign
        own = set(c.own_page_names(unit))
        out: List[Tuple[Path, str]] = []
        for p in self.built_pages:
            targets = sorted(x for x in p.rglob("*") if x.is_file()) if p.is_dir() else ([p] if p.is_file() else [])
            if not targets:
                raise DriverFailure("page_missing", f"built page {p} is missing at upload time",
                                    detail={"path": str(p), "expected_pages": sorted(own)})
            for t in targets:
                rel = t.relative_to(SITE_DIR).as_posix()
                if not site_paths.is_frame_path(rel) and rel not in own:
                    raise DriverFailure("page_foreign", f"{rel} is not one of {c.slug}'s pages for {unit}",
                                        detail={"path": rel, "expected_pages": sorted(own), "prefix": c.site_prefix})
                out.append((t, rel))
        return out

    def _odds_files(self, unit: str) -> List[Path]:
        """The ``odds/<day>/`` snapshot files a later container needs to read this unit's market.

        2026-10-11: Il Lombardia's preview priced against ``odds/2026-10-10/markets_0403.json``
        but never uploaded it; the next day's settle (a fresh container: release + artifact
        overlay) built retro facts whose market block was ``missing``.  So the upload ships:

        * every snapshot a config references through ``odds_capture`` — the unit's and the GC
          board's (``_refresh_gc_config`` can point at an earlier capture) — as the triple
          ``markets_HHMM.json`` / ``provenance_HHMM.json`` / ``win_odds_HHMM.csv``;
        * the top-level files of any ``odds/<day>/`` written during this run (a capture that no
          config references yet, a ``degraded.json``), never ``raw/`` and never older days.

        The overlay restores them at the same campaign-relative path; promote reads only the
        staging bucket, so these never become site pages.
        """
        c = self.campaign
        odds_root = c.dir / "odds"
        if not odds_root.is_dir():
            return []
        out: List[Path] = []
        for cfg_path in (c.pred_dir(unit) / "scenarios.json", c.pred_dir("gc") / "scenarios.json"):
            ref = (_read_json(cfg_path) or {}).get("odds_capture")
            if not isinstance(ref, str) or _is_placeholder(ref):
                continue
            m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})/markets_(\d{4})\.json", ref.strip())
            if not m:
                continue                      # not a snapshot path this driver writes; never trust it as one
            day, hhmm = m.groups()
            out += [odds_root / day / f"{stem}_{hhmm}.{ext}"
                    for stem, ext in (("markets", "json"), ("provenance", "json"), ("win_odds", "csv"))]
        since = getattr(self, "run_started_ts", None)
        if since is not None:
            for d in sorted(p for p in odds_root.iterdir() if p.is_dir()):
                fresh = [f for f in sorted(d.iterdir()) if f.is_file() and f.stat().st_mtime >= since]
                out += fresh
        return [f for f in dict.fromkeys(out) if f.is_file()]

    def _upload(self, unit: str, phase: str) -> Dict[str, Any]:
        from cycling_project.nightly.store import STAGING_BUCKET
        c = self.campaign
        uploaded: List[str] = []
        staging_set = self._staging_set(unit)      # fails the whole upload before any object lands
        pred, res = c.pred_dir(unit), c.results_dir(unit)
        files: List[Path] = []
        if phase == "settle":
            files += [res / n for n in ("results.csv", "results.json", "gc.csv", "classifications.json")]
            files += sorted((res / "pcs").glob("*")) if (res / "pcs").is_dir() else []
            files += sorted(p for p in (res / "uci").rglob("*") if p.is_file()) if (res / "uci").is_dir() else []
            files += [pred / "retro_facts.json", c.dir / "review" / "key_scorecard.json",
                      c.dir / "review" / "agent_replay_scorecard.json", c.pred_dir("gc") / "scenarios.json"]
            if cfg := _read_json(pred / "scenarios.json"):
                if cfg.get("post_hoc"):
                    files += [pred / "scenarios.json", pred / "startlist.json"]
                    files += sorted(p for p in pred.glob("*.json") if p.name not in NON_BOARD_JSON)
            files += sorted(p for p in c.pred_dir("gc").glob("*.json") if p.name != "scenarios.json") if c.pred_dir("gc").is_dir() else []
            files += self._editorial_files(unit)        # a retro draft written before upload ran
        else:
            files += [pred / "scenarios.json", pred / "route.json", *(pred / n for n in AGENT_KEY_FILES)]
            files += sorted(p for p in pred.glob("*.json") if p.name not in ("scenarios.json", "route.json",
                                                                             *AGENT_KEY_FILES, "agent_key_response.json",
                                                                             "retro_facts.json"))
            files += sorted(p for p in (pred / "bundle").rglob("*") if p.is_file()) if (pred / "bundle").is_dir() else []
        files += self._odds_files(unit)
        for f in dict.fromkeys(files):                # a post-hoc settle globs the drafts twice
            if f.is_file():
                key = f"{c.slug}/{f.relative_to(c.dir).as_posix()}"
                k = self._upload_file(f, key)
                if k:
                    uploaded.append(k)
        pages: List[str] = []
        for t, rel in staging_set:
            k = self._upload_file(t, rel, bucket=STAGING_BUCKET)
            if k:
                pages.append(k)
        # predictions rows: one per board
        boards = 0
        cfg = _read_json(pred / "scenarios.json", {}) or {}
        board_dirs = [(unit, pred, cfg)] if phase == "preview" or (phase == "settle" and cfg.get("post_hoc")) else []
        gc_cfg = _read_json(c.pred_dir("gc") / "scenarios.json")
        if phase == "settle" and gc_cfg:
            board_dirs.append(("gc", c.pred_dir("gc"), gc_cfg))
        for bunit, bdir, bcfg in board_dirs:
            for key, spec in (bcfg.get("scenarios") or {}).items():
                bpath = bdir / f"{key}.json"
                if not isinstance(spec, dict) or not bpath.is_file():
                    continue
                data = _read_json(bpath, {}) or {}
                riders = data.get("riders") or []
                top = sorted(riders, key=lambda r: (r.get("daymenu_rank") if data.get("board") == "daymenu" else r.get("predicted_rank")) or 9999)[:5]
                try:
                    self.store.insert_prediction(
                        self.run["run_id"], c.slug, bunit, phase, target=data.get("target") or bcfg.get("target", "stage"),
                        scenario_key=key, day_key=json.dumps(data.get("day_key"), sort_keys=True) if data.get("day_key") else None,
                        model_version=data.get("model_version"),
                        config={"label": spec.get("label"), "tag": spec.get("tag"), "refs": spec.get("refs") or spec.get("base_refs"),
                                "date": bcfg.get("date"), "event_id": bcfg.get("event_id"), "odds_capture": bcfg.get("odds_capture")},
                        board_key=f"{self.run['run_id']}/{c.slug}/{bpath.relative_to(c.dir).as_posix()}",
                        summary={"board": data.get("board"), "n_riders": len(riders),
                                 "top5": [{"name": r.get("rider_name"), "blend_win_p": r.get("blend_win_p")} for r in top]})
                    boards += 1
                except Exception as exc:  # noqa: BLE001
                    self._say(f"  [store] insert_prediction failed for {key}: {exc}")
        plog_rows = self._prediction_log_rows_since(self.plog_watermark)
        n_log = 0
        if plog_rows:
            try:
                n_log = self.store.insert_prediction_log_rows(plog_rows, self.run["run_id"])
            except Exception as exc:  # noqa: BLE001
                self._say(f"  [store] prediction_log upload failed: {exc}")
        editorial = self._persist_editorial(unit, phase)
        return {"artifacts": uploaded, "pages": pages, "predictions_rows": boards, "prediction_log_rows": n_log,
                "editorial_drafts": editorial,
                "_detail": {"artifacts": len(uploaded), "pages": len(pages), "predictions_rows": boards, "prediction_log_rows": n_log,
                            "editorial_drafts": len(editorial["inserted"]),
                            "editorial_duplicates": editorial["duplicates"]}}

    # -- editorial drafts (chip ED, 2026-10-02) ----------------------------------
    def _editorial_files(self, unit: str) -> List[Path]:
        """The unit's draft files and the facts bundles they were written from (artifacts)."""
        from cycling_project.nightly.run_editorial import DRAFT_GLOB
        pred = self.campaign.pred_dir(unit)
        if not pred.is_dir():
            return []
        return (sorted(pred.glob(DRAFT_GLOB)) + sorted(pred.glob("editorial_lint_attempt1*.json"))
                + sorted(pred.glob("editorial_facts_*.json")))

    @staticmethod
    def _attempt1_path(draft: Path) -> Path:
        """Sidecar the ``editorial`` check writes when a first attempt fails the lint:
        ``editorial_draft_stage_preview.json`` → ``editorial_lint_attempt1_stage_preview.json``
        (outside ``DRAFT_GLOB``, so it is shipped as an artifact but never stored as a draft)."""
        return draft.with_name(draft.name.replace("editorial_draft", "editorial_lint_attempt1", 1))

    def _persist_editorial(self, unit: str, phase: str, *, check: bool = False,
                           final: bool = False) -> Dict[str, Any]:
        """Insert one ``editorial_drafts`` row per draft file the coordinator saved for the unit.

        Until 2026-10-02 nothing did this: the coordinator saved ``editorial_draft.json`` "for
        upload to insert", no code inserted it, and every draft died with the container (hosted
        tasks 104 and 114).  Idempotent: a draft whose record hash (or, before migration 0009,
        whose body) is already stored for the unit is not inserted again.

        ``check`` (the ``editorial`` command, chip EE 2026-10-03): a FIRST attempt that fails
        the lint or the schema is not stored — its report goes to ``lint_failures`` and to an
        ``editorial_lint_attempt1_*`` sidecar, and the coordinator gets the skill's one retry.
        A draft is a second attempt when ``final`` is set or when a sidecar holds a DIFFERENT
        record; a second attempt is always stored, pass or fail, never retried again.  Every
        stored row's ``lint`` carries ``attempt``, ``retried`` and ``first_attempt``.
        ``upload`` runs without ``check``: whatever is on disk is stored, flagged when bad.
        """
        from cycling_project.nightly.lint_prose import retry_report
        from cycling_project.nightly.run_editorial import DRAFT_GLOB, prepare_draft
        out: Dict[str, Any] = {"inserted": [], "duplicates": 0, "errors": [], "files": [], "lint_failures": []}
        pred = self.campaign.pred_dir(unit)
        paths = sorted(pred.glob(DRAFT_GLOB)) if pred.is_dir() else []
        if not paths:
            return out
        try:
            existing = self.store.editorial_drafts(campaign_slug=self.campaign.slug, unit=unit)
        except Exception as exc:  # noqa: BLE001 — store a possible duplicate rather than lose a draft
            self._say(f"  [store] editorial_drafts lookup failed ({exc}); inserting without the duplicate check")
            existing = []
        for path in paths:
            out["files"].append(path.name)
            draft = prepare_draft(path, unit, fallback_phase=phase)
            if any(r.get("record_sha256") == draft["record_sha256"]
                   or (not r.get("record_sha256") and r.get("phase") == draft["phase"]
                       and r.get("body_md") == draft["body_md"]) for r in existing):
                out["duplicates"] += 1
                self._say(f"  editorial: {path.name} already stored for {unit}; not inserted again")
                continue
            side = self._attempt1_path(path)
            prior = _read_json(side) if side.is_file() else None
            second = final or bool(prior and prior.get("record_sha256") != draft["record_sha256"])
            compact = retry_report(draft["lint"], validation_errors=draft["lint"].get("validation", {}).get("errors") or ())
            if check and not draft["lint_ok"] and not second:
                side.write_text(json.dumps({
                    "attempt": 1, "file": path.name, "record_sha256": draft["record_sha256"],
                    "checked_at": _utcnow(), "lint_ok": False, "counts": draft["lint"].get("counts"),
                    "validation": draft["lint"].get("validation"), "retry_report": compact,
                    "record": draft["record"]}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
                out["lint_failures"].append({"file": path.name, "artifact": draft["artifact"], "report": compact})
                self._say(f"  editorial: {path.name} failed the lint on attempt 1; not stored, retry requested")
                continue
            lint = dict(draft["lint"])
            if prior and second:
                lint.update({"attempt": 2, "retried": True,
                             "first_attempt": {"ok": False, "counts": prior.get("counts"),
                                               "validation_ok": (prior.get("validation") or {}).get("ok"),
                                               "record_sha256": prior.get("record_sha256"),
                                               "retry_report": prior.get("retry_report")}})
            elif final:
                lint.update({"attempt": 2, "retried": True, "first_attempt": None})
            else:
                lint.update({"attempt": 1, "retried": False,
                             "first_attempt": {"ok": draft["lint_ok"], "counts": draft["lint"].get("counts"),
                                               "validation_ok": draft["lint"].get("validation", {}).get("ok")}})
            try:
                row = self.store.insert_editorial_draft(
                    self.run["run_id"] if self.run else None, self.campaign.slug, unit, draft["phase"],
                    draft["body_md"], kind="prose", author="agent", lint=lint, lint_ok=draft["lint_ok"],
                    record=draft["record"], record_sha256=draft["record_sha256"], artifact=draft["artifact"])
            except Exception as exc:  # noqa: BLE001
                out["errors"].append(f"{path.name}: {redact(str(exc))}")
                self._say(f"  [store] editorial draft insert failed for {path.name}: {exc}")
                continue
            existing.append({**draft, **(row or {})})
            out["inserted"].append({"id": (row or {}).get("id"), "file": path.name, "artifact": draft["artifact"],
                                    "phase": draft["phase"], "lint_ok": draft["lint_ok"], "attempt": lint["attempt"]})
            self._say(f"  editorial: {path.name} → editorial_drafts #{(row or {}).get('id')} "
                      f"({draft['artifact'] or 'invalid'}, attempt {lint['attempt']}, lint {'ok' if draft['lint_ok'] else 'FAILED'})")
        return out

    def _editorial(self, unit: str, *, final: bool = False) -> Dict[str, Any]:
        """``editorial`` command: ship the drafts the editorial thread returned after ``night``'s
        upload had already run — the artifacts and the rows, nothing else (no pages, no boards,
        no prediction_log rows, so it is safe to run as often as the coordinator likes).

        Lints before it stores (chip EE): a first attempt that fails comes back as
        ``EditorialLintFailed`` (exit 10, ``kind: editorial_lint_failed``, the compact report,
        nothing stored, no operator task); ``final`` stores whatever is there."""
        from cycling_project.nightly.run_editorial import DRAFT_GLOB
        c = self.campaign
        pred = c.pred_dir(unit)
        if not (pred.is_dir() and any(pred.glob(DRAFT_GLOB))):
            raise DriverFailure("editorial_draft_missing",
                                f"no predictions/{unit}/editorial_draft_<artifact>.json to store",
                                detail={"looked_in": str(c.pred_dir(unit).relative_to(c.dir))})
        # the phase only matters for a draft too broken to name its own artifact
        result = self._persist_editorial(unit, "settle" if (c.results_dir(unit) / "results.csv").exists() else "preview",
                                         check=True, final=final)
        uploaded = []
        for f in self._editorial_files(unit):
            k = self._upload_file(f, f"{c.slug}/{f.relative_to(c.dir).as_posix()}")
            if k:
                uploaded.append(k)
        if result["errors"]:
            raise DriverFailure("editorial_insert", "; ".join(result["errors"]), detail=result)
        if result["lint_failures"]:
            raise EditorialLintFailed({f["file"]: f["report"] for f in result["lint_failures"]})
        return {"artifacts": uploaded, "editorial_drafts": result,
                "_detail": {"artifacts": len(uploaded), "editorial_drafts": len(result["inserted"]),
                            "editorial_duplicates": result["duplicates"]}}

    # ------------------------------------------------------------------------
    # status
    # ------------------------------------------------------------------------
    def status(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"campaign": self.campaign.slug if self.campaign else None,
                               "completed": self._completed_index() if self.campaign else {}}
        rows: List[Dict[str, Any]] = []
        try:
            if hasattr(self.store, "rows"):
                runs = list(self.store.rows.get("runs", []))
                steps = self.store.rows.get("run_steps", [])
                for r in runs:
                    fin = [s for s in steps if s.get("run_id") == r.get("run_id") and s.get("step") == "finish"]
                    rows.append({**{k: r.get(k) for k in ("run_id", "campaign_slug", "unit", "phase", "started_at")},
                                 "state": fin[-1]["state"] if fin else "running", "exit_code": fin[-1].get("exit_code") if fin else None,
                                 "steps": len([s for s in steps if s.get("run_id") == r.get("run_id")])})
            elif hasattr(self.store, "_select"):
                params = {"order": "started_at.desc", "limit": "50"}
                if self.campaign:
                    params["campaign_slug"] = f"eq.{self.campaign.slug}"
                rows = self.store._select("run_status", params)
        except Exception as exc:  # noqa: BLE001
            out["store_error"] = redact(str(exc))
        out["runs"] = rows
        if self.campaign:
            out["plan"] = self.plan()
        return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python -m cycling_project.nightly", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser, *, unit: bool = False, campaign_required: bool = True) -> None:
        p.add_argument("--campaign", required=campaign_required, help="campaign dir or slug (performance_eval/<slug>)")
        if unit:
            p.add_argument("--unit", required=True, help="stage_NN (or 'race' for a one-day)")
        p.add_argument("--dry-run", action="store_true", help="no fetch, --no-log, FakeStore, scripts recorded not run")
        p.add_argument("--store", choices=("auto", "supabase", "fake"), default="auto")
        p.add_argument("--store-root", type=Path, default=None)
        p.add_argument("--today", type=dt.date.fromisoformat, default=None, help="race-local date override (tests/replay)")
        p.add_argument("--local-now", type=dt.datetime.fromisoformat, default=None,
                       help="race-local wall-clock override, ISO datetime (tests/replay); --today alone reads as "
                            "that date's evening, after racing")
        p.add_argument("--allow-scrape", action="store_true",
                       help="let the serving runner fetch a missing start list from FirstCycling (attended Mac runs "
                            "only; the cloud container cannot pass Cloudflare)")
        p.add_argument("--no-log", action="store_true", help="pass --no-log to the runner (no prediction_log rows)")
        p.add_argument("--force", action="store_true", help="re-run a phase already completed")
        p.add_argument("--crosswalk", type=Path, default=None, help="crosswalk CSV override (default performance_eval/crosswalk)")
        p.add_argument("--db-path", type=Path, default=None)
        p.add_argument("--signatures", type=Path, default=None,
                       help="selection_signatures_*.csv.gz override (default: newest in experiments/)")
        p.add_argument("--release-tag", default=None)
        p.add_argument("--provider", choices=("auto", "uci", "pcs"), default="auto",
                       help="result provider: auto = UCI only (chip X 2026-09-22); pcs is the "
                            "attended Mac path and must be named explicitly")
        p.add_argument("--no-acquire", action="store_true", help="never run the UCI acquisition in-process (settle)")
        p.add_argument("--aliases", type=Path, default=None, help="UCI alias CSV override (default performance_eval/crosswalk/uci_aliases.csv)")
        p.add_argument("--json", action="store_true", default=True, help=argparse.SUPPRESS)

    def identity_flag(p: argparse.ArgumentParser) -> None:
        """Operator ruling 2026-09-16: unattended runs settle with a provisional id and a caveat."""
        p.add_argument("--identity-policy", choices=uci_ingest.IDENTITY_POLICIES,
                       default=uci_ingest.DEFAULT_IDENTITY_POLICY,
                       help="unresolved rider inside the top-15 stage / top-20 GC gate: 'strict' refuses the "
                            "capture and asks a human (attended Mac runs); 'provisional' (default) archives it "
                            "under a uci: id, caveats the page and files a routine task")

    sub.add_parser("bootstrap", help="hydrate the container from the newest approved release (delegates to nightly.bootstrap)",
                   add_help=False)
    p = sub.add_parser("plan", help="due units for a campaign (settle / preview) as JSON")
    common(p); p.add_argument("--now", action="store_true", help="plan as of now (default)"); p.add_argument("--horizon-days", type=int, default=1)
    tiers.add_tier_flags(p)
    p = sub.add_parser("night", help="every due settle, then every due preview")
    common(p); p.add_argument("--horizon-days", type=int, default=1)
    p.add_argument("--agent-key", type=Path, default=None, help="agent decision record for every due preview")
    identity_flag(p); tiers.add_tier_flags(p)
    p = sub.add_parser("settle", help="ingest → seed → GC → score → retro facts → pages → upload")
    common(p, unit=True); identity_flag(p)
    p = sub.add_parser("preview", help="odds → config → route → bundle → key gate → predict → validate → pages → upload")
    common(p, unit=True); identity_flag(p)      # validate's crosswalk bar follows the policy (2026-09-18)
    p.add_argument("--agent-key", type=Path, default=None,
                   help="key the stage from this agent decision record; without the flag the driver still "
                        "picks up predictions/<unit>/agent_key.json when no human key is approved")
    p = sub.add_parser("acquire", help="run the deterministic UCI acquisition for a unit (idempotent)")
    common(p, unit=True); p.add_argument("--competition-url", default=None, help="override campaign.json uci_competition_url")
    p = sub.add_parser("ingest", help="validate the captured UCI results and write the FC-shaped archive")
    common(p, unit=True); identity_flag(p)
    p = sub.add_parser("bundle", help="freeze predictions/<unit>/bundle/")
    common(p, unit=True)
    p = sub.add_parser("validate", help="schema / NaN / lambdarank sum / post_hoc / void_stages / key weights / crosswalk")
    common(p, unit=True); identity_flag(p)
    p = sub.add_parser("upload", help="insert artifacts, pages and rows for a unit")
    common(p, unit=True); p.add_argument("--phase", choices=("settle", "preview"), required=True)
    p = sub.add_parser("editorial", help="lint, then store the unit's editorial_draft_<artifact>.json as an editorial_drafts "
                                         "row + artifact (idempotent; no pages, boards or prediction_log rows). A first "
                                         "attempt that fails the lint exits 10 (editorial_lint_failed) unstored")
    common(p, unit=True)
    p.add_argument("--final", action="store_true",
                   help="the draft is the one retry: store it with its lint result, pass or fail")
    p = sub.add_parser("status", help="ledger view")
    common(p, campaign_required=False)
    p = sub.add_parser("task", help="file an operator_tasks row (e.g. an ops-triage report) through the store")
    common(p, campaign_required=False)
    p.add_argument("--kind", required=True, help="task kind, e.g. ops_triage")
    p.add_argument("--summary", required=True)
    p.add_argument("--detail-file", type=Path, default=None, help="JSON file inserted verbatim as detail")
    p.add_argument("--urgency", default="routine",
                   help="routine | blocks_publication | blocks_settlement | urgent (anything else is filed as urgent)")
    sub.add_parser("refs", help="reference sets from the signature table (delegates to nightly.refs)", add_help=False)
    return ap


def _emit(code: int, payload: Dict[str, Any]) -> int:
    payload = dict(payload)
    payload.setdefault("exit_code", code)
    print(json.dumps(payload, indent=1, ensure_ascii=False, default=str), flush=True)
    return code


def main(argv: Optional[Sequence[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ("publish", "commit"):
        return _emit(EXIT_FAILED, {"status": "failed", "error_class": "forbidden_command",
                                   "message": f"{argv[0]!r} is not a driver command: publication is a Mac step with its own key (§2.9)"})
    # delegated commands keep their own argparse surface (flags would otherwise be eaten here)
    if argv and argv[0] == "bootstrap":
        from cycling_project.nightly.bootstrap import main as bootstrap_main
        return bootstrap_main(argv[1:])
    if argv and argv[0] == "refs":
        from cycling_project.nightly.refs import main as refs_main
        return refs_main(argv[1:])
    args = build_parser().parse_args(argv)

    campaign = None
    if getattr(args, "campaign", None):
        try:
            campaign = Campaign.load(args.campaign)
        except DriverFailure as exc:
            return _emit(EXIT_FAILED, {"status": "failed", "error_class": exc.error_class, "message": str(exc)})
    try:
        store = resolve_store(args.store, args.store_root, dry_run=args.dry_run, campaign=campaign)
    except DriverFailure as exc:
        return _emit(EXIT_FAILED, {"status": "failed", "error_class": exc.error_class, "message": str(exc)})
    driver = Driver(campaign, store, dry_run=args.dry_run, today=args.today, no_log=args.no_log, force=args.force,
                    crosswalk_csv=args.crosswalk, db_path=args.db_path, agent_key=getattr(args, "agent_key", None),
                    release_tag=args.release_tag, acquire=not getattr(args, "no_acquire", False),
                    provider=getattr(args, "provider", "auto"), aliases_csv=getattr(args, "aliases", None),
                    signatures=getattr(args, "signatures", None),
                    identity_policy=getattr(args, "identity_policy", uci_ingest.DEFAULT_IDENTITY_POLICY),
                    local_now=getattr(args, "local_now", None), allow_scrape=getattr(args, "allow_scrape", False),
                    automation_tiers=(tiers.tiers_from_args(args)
                                      if hasattr(args, "all_tiers") else None))

    if args.command == "status":
        return _emit(EXIT_DONE, {"status": "ok", **driver.status()})
    if args.command == "task":
        from cycling_project.nightly.crosswalk import build_operator_task
        detail = json.loads(args.detail_file.read_text()) if args.detail_file else {}
        if not isinstance(detail, dict):
            return _emit(EXIT_FAILED, {"status": "failed", "error_class": "task_detail", "message": "--detail-file must hold a JSON object"})
        task = build_operator_task(args.kind, campaign.slug if campaign else None, args.summary, detail, urgency=args.urgency)
        if args.dry_run:
            return _emit(EXIT_DONE, {"status": "ok", "dry_run": True, "task": task})
        duplicate = find_open_duplicate(store, task)
        if duplicate:
            return _emit(EXIT_DONE, {"status": "ok", "task": task, "operator_task_id": duplicate.get("id"),
                                     "duplicate_of": duplicate.get("id"),
                                     "note": "an unresolved task with the same kind/campaign/unit/phase is already open; not filed again"})
        try:
            row = store.insert_task(task)
        except Exception as exc:  # noqa: BLE001
            return _emit(EXIT_FAILED, {"status": "failed", "error_class": "task_insert", "message": str(exc), "task": task})
        return _emit(EXIT_DONE, {"status": "ok", "task": task, "operator_task_id": (row or {}).get("id")})
    if campaign is None:
        return _emit(EXIT_FAILED, {"status": "failed", "error_class": "campaign_missing", "message": "--campaign is required"})
    if args.command == "plan":
        return _emit(EXIT_DONE, {"status": "ok", **driver.plan(args.horizon_days)})
    if args.command == "night":
        code, out = driver.night(args.horizon_days)
        return _emit(code, out)
    if args.command == "settle":
        code, out = driver.settle(args.unit)
        return _emit(code, out)
    if args.command == "preview":
        code, out = driver.preview(args.unit)
        return _emit(code, out)
    if args.command == "acquire":
        if args.competition_url:
            campaign.cfg["uci_competition_url"] = args.competition_url
        code, out = driver.run_phase(args.unit, "acquire", lambda: {"acquire": driver.step("acquire", lambda: driver._acquire(args.unit))}, idempotent=False)
        return _emit(code, out)
    if args.command == "ingest":
        code, out = driver.run_phase(args.unit, "ingest", lambda: {"ingest": driver.step("ingest", lambda: driver._ingest(args.unit))}, idempotent=False)
        return _emit(code, out)
    if args.command == "bundle":
        code, out = driver.run_phase(args.unit, "bundle", lambda: {"bundle": driver.step("bundle", lambda: driver._bundle(args.unit))}, idempotent=False)
        return _emit(code, out)
    if args.command == "validate":
        code, out = driver.run_phase(args.unit, "validate", lambda: {"validate": driver.step("validate", lambda: driver._validate(args.unit))}, idempotent=False)
        return _emit(code, out)
    if args.command == "upload":
        code, out = driver.run_phase(args.unit, "upload", lambda: {"upload": driver.step("upload", lambda: driver._upload(args.unit, args.phase))}, idempotent=False)
        return _emit(code, out)
    if args.command == "editorial":
        code, out = driver.run_phase(args.unit, "editorial", lambda: {"editorial": driver.step("editorial", lambda: driver._editorial(args.unit, final=args.final))}, idempotent=False)
        return _emit(code, out)
    return _emit(EXIT_FAILED, {"status": "failed", "error_class": "unknown_command", "message": args.command})


if __name__ == "__main__":
    raise SystemExit(main())
