#!/usr/bin/env python3
"""``uci_acquire`` — deterministic acquisition of a stage's results from the UCI website.

Primary result provider for the nightly (UCI_MANAGED_AGENT_BUILD_BRIEF.md). No
LLM is involved: this module fetches the competition page, decodes the
``CompetitionDetailsModule`` ``data-props`` JSON, selects the requested stage
and its classifications by exact title, builds each results-API URL with a URL
library (never by string concatenation) and saves every response **verbatim**
next to an index (``uci_raw.json``) that records provider, source URL, event
code, race type, race name, fetched time, HTTP status, content type, byte
count, sha256, row count and any error. Parsing/validation is
``uci_ingest.py``'s job.

Verified 2026-09-06 against La Vuelta 2026 (competition 76942): the page and
``GET https://www.uci.org/api/calendar/results/{eventCode}?discipline=ROA&raceType=A&raceName=…``
answer HTTP 200 to plain ``requests`` with no cookies or browser.

Request policy (CLAUDE.md): explicit timeout, bounded retries for transient
failures only, at least three seconds (plus jitter) between requests, shared
logging. Re-running is idempotent: a complete matching capture is reused
without a single request; a differing capture is never silently overwritten
(``--refresh`` refuses unless ``--supersede`` moves the old one aside).

This file is intentionally self-contained (stdlib + ``requests``) so the
Managed Agent can run it before the release bundle exists::

    python -m cycling_project.nightly.uci_acquire \\
        --competition-url https://www.uci.org/competition-details/2026/ROA/76942 \\
        --campaign performance_eval/vuelta-2026 --unit stage_14

    python3 uci_acquire.py --competition-url … --unit stage_14 --out /mnt/session/outputs/uci

Exit codes: 0 complete · 10 incomplete (a required classification is not
published / not reachable — the raw capture and index are kept) · 20 failure
(bad URL, page without the module, stage not in the schedule/results).
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html as html_lib
import json
import logging
import random
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

try:  # the project logger when run inside the repo; plain logging when standalone
    from cycling_project.webscrape_tools.logging_config import get_logger
    logger = get_logger(__name__)
except Exception:  # noqa: BLE001
    logger = logging.getLogger("uci_acquire")
    if not logger.handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

__version__ = "1.0.0"
PROVIDER = "uci"
UCI_HOSTS = ("www.uci.org", "uci.org")
COMPETITION_URL_RE = re.compile(r"^https://(?:www\.)?uci\.org/competition-details/(\d{4})/([A-Z]{3})/(\d+)/?$")
RESULTS_API = "https://www.uci.org/api/calendar/results/{event_code}"
MODULE_NAME = "CompetitionDetailsModule"
MIN_INTERVAL_S = 3.0
JITTER_S = 1.0
TIMEOUT_S = 30.0
RETRIES = 3
INDEX_NAME = "uci_raw.json"
COMPETITION_FILE = "competition.html"
EXIT_OK, EXIT_INCOMPLETE, EXIT_FAILED = 0, 10, 20

# kind -> (exact titles accepted in the results accordion, required for settling a STAGE)
# One-day races publish a single classification; see ONE_DAY_UNITS below.
CLASSIFICATIONS: Dict[str, Tuple[Tuple[str, ...], bool]] = {
    "stage": (("Stage Classification",), True),
    "gc": (("Stage General Classification", "General Classification", "Final Classification"), True),
    "points": (("Overall Points Classification",), False),
    "kom": (("Overall Mountain Classification", "Overall Mountains Classification"), False),
    "youth": (("Overall Youth Classification",), False),
    "teams": (("Overall Team Classification", "Overall Teams Classification", "Team Classification"), False),
}
SUPPORTED_RACE_TYPES = ("A",)          # observed on every road classification; anything else is rejected

# A one-day race has exactly one accordion entry and one classification inside
# it — verified 2026-09-07 on GP Industria & Artigianato (1.Pro, competition
# 78396): accordion label "Final Classification", the single result titled
# "General Classification", raceType "A", 161 rows, winner PIDCOCK Thomas
# 04:33:08.  So a one-day capture is complete with that one document; demanding
# a separate "Stage Classification" (the stage-race rule) would fail every
# one-day race.  ``one_day`` is the unit name the registry gives them and
# ``race`` the name uci_acquire's CLI has always used; both mean the same thing.
ONE_DAY_UNITS = ("race", "one_day")


class AcquireError(RuntimeError):
    """Deterministic failure (exit 20): bad URL, no module, stage not published."""


# ---------------------------------------------------------------------------
# pure helpers (tested offline)
# ---------------------------------------------------------------------------

def parse_competition_url(url: str) -> Dict[str, Any]:
    m = COMPETITION_URL_RE.match((url or "").strip())
    if not m:
        raise AcquireError(f"not a UCI competition-details URL: {url!r} "
                           "(expected https://www.uci.org/competition-details/<year>/<discipline>/<id>)")
    year, discipline, cid = m.groups()
    return {"url": f"https://www.uci.org/competition-details/{year}/{discipline}/{cid}",
            "year": int(year), "discipline": discipline, "id": cid}


def extract_data_props(page_html: str, component: str = MODULE_NAME) -> Dict[str, Any]:
    """``div[data-component=<component>][data-props]`` → decoded JSON (html.unescape → json.loads)."""
    patterns = (
        rf'data-component="{component}"[^>]*?data-props="([^"]*)"',
        rf'data-props="([^"]*)"[^>]*?data-component="{component}"',
    )
    for pat in patterns:
        m = re.search(pat, page_html, flags=re.S)
        if m:
            try:
                props = json.loads(html_lib.unescape(m.group(1)))
            except json.JSONDecodeError as exc:
                raise AcquireError(f"{component} data-props is not valid JSON after html.unescape: {exc}") from exc
            if not isinstance(props, dict):
                raise AcquireError(f"{component} data-props is not a JSON object")
            return props
    raise AcquireError(f"no <div data-component=\"{component}\" data-props=…> in the page "
                       "(a text extraction of the page drops the attribute — fetch the raw HTML)")


def stage_label_for(unit: str) -> str:
    """``stage_14`` → ``Stage 14``; ``race``/``one_day`` → ``race`` (the single accordion entry)."""
    m = re.fullmatch(r"stage_(\d+)", unit or "")
    if m:
        return f"Stage {int(m.group(1))}"
    if unit in ONE_DAY_UNITS:
        return "race"
    raise AcquireError(f"unit must be stage_NN, race or one_day, not {unit!r}")


def is_one_day_unit(unit: Optional[str]) -> bool:
    return (unit or "") in ONE_DAY_UNITS


def required_kinds(unit: Optional[str]) -> Tuple[str, ...]:
    """Which classifications must be present for the capture to count as complete."""
    if is_one_day_unit(unit):
        return ("gc",)
    return tuple(k for k, (_titles, req) in CLASSIFICATIONS.items() if req)


def _norm_label(s: str) -> str:
    return " ".join((s or "").split()).casefold()


def find_stage(props: Dict[str, Any], unit: str) -> Dict[str, Any]:
    """The requested stage's schedule entry and results-accordion entry (both must exist)."""
    label = stage_label_for(unit)
    accordion = ((props.get("results") or {}).get("accordion")) or []
    schedule_items = ((props.get("schedule") or {}).get("items")) or []
    if label == "race":
        if len(accordion) != 1:
            raise AcquireError(f"one-day unit needs exactly one accordion entry, found {len(accordion)}")
        entry = accordion[0]
        sched = schedule_items[0] if schedule_items else {}
        race = (sched.get("races") or [{}])[0]
        return {"label": entry.get("label"), "accordion": entry, "schedule_date": sched.get("date"), "schedule": race}
    entry = next((a for a in accordion if _norm_label(a.get("label")) == _norm_label(label)), None)
    sched, race = None, None
    for item in schedule_items:
        for r in item.get("races") or []:
            if _norm_label(r.get("raceName")) == _norm_label(label):
                sched, race = item, r
    if race is None:
        raise AcquireError(f"{label!r} is not in the competition schedule")
    if entry is None:
        raise AcquireError(f"{label!r} has no results in the accordion yet (schedule date {sched.get('date')!r})")
    return {"label": entry.get("label"), "accordion": entry, "schedule_date": sched.get("date"), "schedule": race}


def select_classifications(entry: Dict[str, Any], kinds: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
    """kind → ``{title, event_code, race_type}`` for every supported classification present, by exact title."""
    wanted = kinds or list(CLASSIFICATIONS)
    by_title = {}
    for r in entry.get("results") or []:
        by_title[_norm_label(r.get("title"))] = r
    out: Dict[str, Dict[str, Any]] = {}
    for kind in wanted:
        titles, _required = CLASSIFICATIONS[kind]
        for t in titles:
            r = by_title.get(_norm_label(t))
            if r is not None:
                out[kind] = {"title": r.get("title"), "event_code": r.get("eventCode"), "race_type": r.get("raceType")}
                break
    return out


def results_url(event_code: str, discipline: str, race_type: str, race_name: str) -> str:
    """Three independent query parameters, encoded by ``urllib`` (spaces → %20, never a literal ``%26``)."""
    if not event_code or not re.fullmatch(r"[A-Z0-9]+", event_code):
        raise AcquireError(f"bad event code {event_code!r}")
    if race_type not in SUPPORTED_RACE_TYPES:
        raise AcquireError(f"unsupported raceType {race_type!r} for {event_code}")
    base = RESULTS_API.format(event_code=event_code)
    query = urlencode([("discipline", discipline), ("raceType", race_type), ("raceName", race_name)], quote_via=_quote_no_plus)
    return f"{base}?{query}"


def _quote_no_plus(s: str, safe: str = "", encoding=None, errors=None) -> str:
    from urllib.parse import quote
    return quote(s, safe=safe, encoding=encoding, errors=errors)


def assert_well_formed_results_url(url: str) -> Dict[str, str]:
    """Regression guard: a literal ``%26`` between parameters yields ONE malformed parameter."""
    parts = urlsplit(url)
    if parts.netloc not in UCI_HOSTS or not parts.path.startswith("/api/calendar/results/"):
        raise AcquireError(f"not a UCI results-API URL: {url}")
    params = dict(parse_qsl(parts.query, keep_blank_values=True))
    if set(params) != {"discipline", "raceType", "raceName"}:
        raise AcquireError(f"results URL must carry exactly discipline, raceType and raceName (got {sorted(params)}): {url}")
    if "%26" in parts.query.upper() or "&" in params["raceName"]:
        raise AcquireError(f"encoded '&' inside a parameter — the query was concatenated, not encoded: {url}")
    return params


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def row_count_of(doc: Any) -> Optional[int]:
    if isinstance(doc, dict) and isinstance(doc.get("results"), list):
        return len(doc["results"])
    return None


# ---------------------------------------------------------------------------
# HTTP with the conservative policy
# ---------------------------------------------------------------------------

class Fetcher:
    """One session; ≥ 3 s + jitter between requests; bounded retries on 429/5xx/connection errors."""

    def __init__(self, session: Optional[requests.Session] = None, *, min_interval: float = MIN_INTERVAL_S,
                 timeout: float = TIMEOUT_S, retries: int = RETRIES, sleep=time.sleep, jitter: float = JITTER_S):
        self.session = session or requests.Session()
        self.min_interval = min_interval
        self.timeout = timeout
        self.retries = max(1, retries)
        self._sleep = sleep
        self._jitter = jitter
        self._last: Optional[float] = None
        self.requests_made = 0

    def _throttle(self) -> None:
        if self._last is not None:
            wait = self.min_interval - (time.monotonic() - self._last) + random.uniform(0, self._jitter)
            if wait > 0:
                self._sleep(wait)
        self._last = time.monotonic()

    def get(self, url: str, *, accept: str) -> Tuple[Optional[requests.Response], Optional[str]]:
        """(response, error). Retries only what is transient, never more than ``retries`` attempts;
        the last response is returned even on failure so its body can be kept verbatim."""
        last_err: Optional[str] = None
        last_resp: Optional[requests.Response] = None
        for attempt in range(1, self.retries + 1):
            self._throttle()
            self.requests_made += 1
            try:
                r = self.session.get(url, timeout=self.timeout, headers={"Accept": accept})
            except requests.RequestException as exc:
                last_err = f"{type(exc).__name__}: {exc}"
                logger.warning("uci fetch attempt %d/%d failed for %s: %s", attempt, self.retries, url, last_err)
                continue
            last_resp = r
            if r.status_code == 429 or 500 <= r.status_code < 600:
                last_err = f"HTTP {r.status_code}"
                retry_after = r.headers.get("Retry-After")
                try:
                    extra = float(retry_after) if retry_after else 0.0
                except ValueError:
                    extra = 0.0
                logger.warning("uci %s for %s (attempt %d/%d)", last_err, url, attempt, self.retries)
                if attempt < self.retries:
                    self._sleep(max(self.min_interval, extra) + attempt * self.min_interval)
                continue
            return r, None
        return last_resp, last_err


# ---------------------------------------------------------------------------
# the capture
# ---------------------------------------------------------------------------

def read_index(uci_dir: Path) -> Optional[Dict[str, Any]]:
    p = Path(uci_dir) / INDEX_NAME
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def capture_is_complete(index: Optional[Dict[str, Any]], required: Optional[Tuple[str, ...]] = None) -> bool:
    if not index or index.get("provider") != PROVIDER:
        return False
    required = required if required is not None else required_kinds(index.get("unit"))
    pages = index.get("pages") or {}
    if "competition" not in pages:
        return False
    for kind in required:
        e = pages.get(kind) or {}
        if e.get("http_status") != 200 or not e.get("file") or e.get("error"):
            return False
    return bool(index.get("complete"))


def _page_entry(kind: str, url: str, fetched_at: str, r: Optional[requests.Response], err: Optional[str],
                data: Optional[bytes], file: Optional[str], **extra: Any) -> Dict[str, Any]:
    entry: Dict[str, Any] = {"file": file, "source_url": url, "fetched_at": fetched_at,
                             "http_status": r.status_code if r is not None else None,
                             "content_type": r.headers.get("Content-Type") if r is not None else None,
                             "bytes": len(data) if data is not None else 0,
                             "sha256": sha256_bytes(data) if data is not None else None,
                             "error": err}
    entry.update(extra)
    return entry


def acquire(*, competition_url: str, unit: str, out_dir: Path, campaign_slug: Optional[str] = None,
            kinds: Optional[List[str]] = None, fetcher: Optional[Fetcher] = None, refresh: bool = False,
            supersede: bool = False) -> Dict[str, Any]:
    """Fetch + save; returns the index (also written to ``<out_dir>/uci_raw.json``)."""
    out_dir = Path(out_dir)
    comp = parse_competition_url(competition_url)
    existing = read_index(out_dir)
    if existing and not refresh:
        same = (existing.get("competition") or {}).get("id") == comp["id"] and existing.get("unit") == unit
        if same and capture_is_complete(existing):
            logger.info("uci capture for %s already complete under %s — reused, no request made", unit, out_dir)
            existing["reused"] = True
            return existing
    if existing and refresh and not supersede:
        raise AcquireError(f"a capture already exists under {out_dir}; --refresh needs --supersede to move it aside "
                           "(captures are never overwritten in place)")
    if existing and refresh and supersede:
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        keep = out_dir / f"previous_{stamp}"
        keep.mkdir(parents=True, exist_ok=True)
        for p in list(out_dir.iterdir()):
            if p.is_file():
                shutil.move(str(p), str(keep / p.name))
        logger.info("previous capture moved to %s", keep)

    out_dir.mkdir(parents=True, exist_ok=True)
    f = fetcher or Fetcher()
    index: Dict[str, Any] = {
        "provider": PROVIDER, "acquirer": f"uci_acquire {__version__}", "campaign": campaign_slug, "unit": unit,
        "competition": comp, "acquired_at": _utcnow(), "pages": {}, "complete": False,
        "superseded": [p.name for p in out_dir.iterdir() if p.is_dir() and p.name.startswith("previous_")],
    }
    pages = index["pages"]

    # 1. competition page (raw HTML — the data-props attribute lives only in the source)
    fetched_at = _utcnow()
    r, err = f.get(comp["url"], accept="text/html")
    data = r.content if r is not None else None
    if r is not None and r.status_code != 200:
        err = f"HTTP {r.status_code}"
    if data is not None:
        (out_dir / COMPETITION_FILE).write_bytes(data)
    pages["competition"] = _page_entry("competition", comp["url"], fetched_at, r, err, data,
                                       COMPETITION_FILE if data is not None else None)
    _write_index(out_dir, index)
    if err:
        raise AcquireError(f"competition page not acquired: {err}")

    props = extract_data_props(data.decode("utf-8", errors="replace"))
    details = props.get("competitionDetails") or {}
    index["competition"].update({"name": details.get("name"), "dates": details.get("dates"),
                                 "country": details.get("country"), "class": details.get("competitionClass"),
                                 "discipline_code": (props.get("results") or {}).get("disciplineCode")})
    stage = find_stage(props, unit)
    index["stage"] = {"label": stage["label"], "schedule_date": stage["schedule_date"],
                      "race_type": (stage["schedule"] or {}).get("raceType"),
                      "race_class": (stage["schedule"] or {}).get("raceClass"),
                      "category": (stage["schedule"] or {}).get("category"),
                      "accordion_titles": [x.get("title") for x in stage["accordion"].get("results") or []]}
    selected = select_classifications(stage["accordion"], kinds)
    for kind in (kinds or list(CLASSIFICATIONS)):
        if kind not in selected:
            pages[kind] = {"available": False, "reason": "not in the results accordion for this stage",
                           "required": CLASSIFICATIONS[kind][1]}
    _write_index(out_dir, index)

    # 2. every selected classification, verbatim
    for kind, sel in selected.items():
        if not sel.get("event_code"):
            pages[kind] = {"available": False, "reason": "empty event code", "required": CLASSIFICATIONS[kind][1]}
            continue
        try:
            url = results_url(sel["event_code"], comp["discipline"], sel["race_type"], sel["title"])
            assert_well_formed_results_url(url)
        except AcquireError as exc:
            pages[kind] = {"available": False, "reason": str(exc), "required": CLASSIFICATIONS[kind][1], **sel}
            continue
        fetched_at = _utcnow()
        r, err = f.get(url, accept="application/json")
        data = r.content if r is not None else None
        row_count = None
        if r is not None and r.status_code != 200:
            err = f"HTTP {r.status_code}"
        elif data is not None:
            try:
                row_count = row_count_of(json.loads(data.decode("utf-8")))
                if row_count is None:
                    err = "response is not a {results: [...]} document"
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                err = f"response is not JSON: {exc}"
        file = f"{kind}.json"
        if data is not None:
            (out_dir / file).write_bytes(data)          # verbatim, even when it is an error body
        pages[kind] = _page_entry(kind, url, fetched_at, r, err, data, file if data is not None else None,
                                  event_code=sel["event_code"], race_type=sel["race_type"], race_name=sel["title"],
                                  row_count=row_count, required=CLASSIFICATIONS[kind][1])
        _write_index(out_dir, index)

    required_ok = all((pages.get(k) or {}).get("http_status") == 200 and not (pages.get(k) or {}).get("error")
                      for k in required_kinds(unit) if kinds is None or k in kinds)
    index["complete"] = required_ok
    index["requests_made"] = f.requests_made
    _write_index(out_dir, index)
    return index


def _write_index(out_dir: Path, index: Dict[str, Any]) -> None:
    (Path(out_dir) / INDEX_NAME).write_text(json.dumps(index, indent=1, ensure_ascii=False), encoding="utf-8")


def summary(index: Dict[str, Any]) -> Dict[str, Any]:
    pages = index.get("pages") or {}
    return {
        "provider": PROVIDER, "unit": index.get("unit"), "competition": (index.get("competition") or {}).get("id"),
        "stage": (index.get("stage") or {}).get("label"), "complete": bool(index.get("complete")),
        "reused": bool(index.get("reused")), "requests_made": index.get("requests_made"),
        "pages": {k: ({"status": v.get("http_status"), "rows": v.get("row_count"), "sha256": (v.get("sha256") or "")[:12],
                       "error": v.get("error")} if v.get("file") or v.get("http_status")
                      else {"available": False, "reason": v.get("reason")})
                  for k, v in pages.items()},
    }


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--competition-url", required=True)
    ap.add_argument("--unit", required=True, help="stage_NN, race or one_day")
    ap.add_argument("--campaign", type=Path, default=None, help="campaign dir; capture goes to results/<unit>/uci/")
    ap.add_argument("--campaign-slug", default=None)
    ap.add_argument("--out", type=Path, default=None, help="explicit capture directory (overrides --campaign)")
    ap.add_argument("--kinds", default=None, help="comma list of classifications (default: all supported)")
    ap.add_argument("--refresh", action="store_true", help="re-fetch even if a complete capture exists")
    ap.add_argument("--supersede", action="store_true", help="with --refresh: move the old capture to previous_<ts>/")
    ap.add_argument("--min-interval", type=float, default=MIN_INTERVAL_S)
    ap.add_argument("--timeout", type=float, default=TIMEOUT_S)
    ap.add_argument("--retries", type=int, default=RETRIES)
    args = ap.parse_args(argv)
    if args.out is None and args.campaign is None:
        ap.error("--campaign or --out is required")
    out_dir = args.out or (args.campaign / "results" / args.unit / "uci")
    slug = args.campaign_slug or (args.campaign.name if args.campaign else None)
    kinds = [k.strip() for k in args.kinds.split(",")] if args.kinds else None
    if kinds and any(k not in CLASSIFICATIONS for k in kinds):
        ap.error(f"unknown kind in --kinds (supported: {', '.join(CLASSIFICATIONS)})")
    try:
        index = acquire(competition_url=args.competition_url, unit=args.unit, out_dir=out_dir, campaign_slug=slug,
                        kinds=kinds, refresh=args.refresh, supersede=args.supersede,
                        fetcher=Fetcher(min_interval=max(MIN_INTERVAL_S, args.min_interval), timeout=args.timeout,
                                        retries=args.retries))
    except AcquireError as exc:
        print(json.dumps({"status": "failed", "error_class": "uci_acquire", "message": str(exc), "out_dir": str(out_dir)}, indent=1))
        return EXIT_FAILED
    out = {"status": "ok" if index.get("complete") else "incomplete", "out_dir": str(out_dir), **summary(index)}
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return EXIT_OK if index.get("complete") else EXIT_INCOMPLETE


if __name__ == "__main__":
    sys.exit(main())
