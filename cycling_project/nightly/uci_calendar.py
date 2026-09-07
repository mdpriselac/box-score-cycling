#!/usr/bin/env python3
"""``uci_calendar`` — resolve a campaign's UCI competition-details URL from the UCI road calendar.

Companion of :mod:`cycling_project.nightly.uci_acquire`, which needs
``uci_competition_url`` on every campaign it settles.  ``registry.sync`` emits
that field as ``null`` and the driver never guesses; this module fills it in
**only** where the calendar answers unambiguously, and asks a human otherwise.

How the calendar is exposed (discovered 2026-09-07)
---------------------------------------------------
The road calendar page ``https://www.uci.org/calendar/road/2ruOnavHX0dMGTCRozdYAU``
renders a ``div[data-component="CalendarModule"][data-props]`` (same trick as the
competition page) whose props carry only the filter vocabulary; the listing
itself is fetched client-side from two endpoints that need no token and no
cookies::

    GET https://www.uci.org/api/calendar/upcoming?discipline=ROA
    GET https://www.uci.org/api/calendar/past?discipline=ROA

(The ``bearerToken`` in the page props belongs to a different UCI service and is
not sent to these two.)  Each response is ``items`` = months → days →
competitions, so a stage race appears once per day it spans.  A competition
entry carries ``name``, ``country`` (IOC 3-letter), ``venue``, ``continentCode``,
the human date text ``dates`` (``"22 Aug - 13 Sep 2026"``) and
``detailsLink.url`` = ``/competition-details/<year>/<discipline>/<id>`` — which
is exactly the URL ``uci_acquire`` consumes.

Request policy is ``uci_acquire``'s: honest browser UA, ≥ 3 s between requests,
no cookies, explicit timeout, bounded retries, responses saved verbatim.  A
capture is two requests for the whole calendar — never one per race.

Matching (deterministic, never a guess)
---------------------------------------
Compared fields: **dates** (campaign ``start_date``/``end_date`` vs the parsed
listing span), **name** (normalised, several deterministic variants) and
**country** (recorded from the listing; our FirstCycling calendar carries no
country, so it is evidence only, never a discriminator — see ``COUNTRY_NOTE``).

A candidate is **auto-accepted** only when the date range matches exactly *and*
name similarity ≥ 0.90 *and* no other exact-date candidate also reaches 0.90.
Everything else becomes a ``uci_competition_confirm`` operator task and the URL
stays ``null``.  A non-null ``uci_competition_url`` is never overwritten: the
match is still computed and recorded as evidence (``decision =
preserved_existing``) so a disagreement is visible.

Usage::

    python -m cycling_project.nightly.uci_calendar capture           # 2 requests
    python -m cycling_project.nightly.uci_calendar resolve --dry-run
    python -m cycling_project.nightly.uci_calendar resolve
    python -m cycling_project.nightly.uci_calendar report

Exit codes: 0 done · 10 nothing resolved and at least one campaign still open ·
20 failure (no snapshot, unreadable listing).
"""

from __future__ import annotations

import argparse
import datetime as dt
import difflib
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlencode, urlsplit

from cycling_project.nightly.uci_acquire import AcquireError, Fetcher, sha256_bytes
from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

__version__ = "1.0.0"
PROVIDER = "uci"
LISTING_API = "https://www.uci.org/api/calendar/{kind}"
LISTING_KINDS = ("upcoming", "past")
DISCIPLINE = "ROA"
INDEX_NAME = "calendar_raw.json"
REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_DIR = REPO_ROOT / "cycling_project" / "tests" / "fixtures" / "uci" / "calendar"
LIVE_SNAPSHOT_DIR = REPO_ROOT / "performance_eval" / "calendar" / "uci"
RUNS_DIR = REPO_ROOT / "performance_eval" / "runs"
PERFORMANCE_EVAL = REPO_ROOT / "performance_eval"
TASK_KIND = "uci_competition_confirm"
AUTO_ACCEPT_SIMILARITY = 0.90
COUNTRY_NOTE = ("the FirstCycling calendar rows and campaign files carry no country, "
                "so the listing's country is recorded but not used as a discriminator")
EXIT_OK, EXIT_OPEN, EXIT_FAILED = 0, 10, 20

_MONTHS = {m: i for i, m in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}

# Deterministic, documented expansions applied to BOTH sides before scoring.
# Only unambiguous cycling shorthand; nothing that could merge two races.
_NAME_EXPANSIONS = (
    (r"\bgp\b", "grand prix"),
    (r"\bg\.?p\.?\b", "grand prix"),
    (r"\bkamp\b", "kampioenschap"),
    (r"\bst\b", "saint"),
)
# Nothing else is stripped: "Men"/"Women"/"Dames" in a UCI name are real
# discriminators (the same race often runs both), so they must lower the score
# rather than disappear.


# ---------------------------------------------------------------------------
# capture
# ---------------------------------------------------------------------------

def listing_url(kind: str, discipline: str = DISCIPLINE) -> str:
    if kind not in LISTING_KINDS:
        raise AcquireError(f"unknown listing kind {kind!r} (expected one of {LISTING_KINDS})")
    if not re.fullmatch(r"[A-Z]{3}", discipline or ""):
        raise AcquireError(f"bad discipline {discipline!r}")
    return f"{LISTING_API.format(kind=kind)}?{urlencode({'discipline': discipline})}"


def assert_well_formed_listing_url(url: str) -> None:
    parts = urlsplit(url)
    if parts.netloc not in ("www.uci.org", "uci.org") or not parts.path.startswith("/api/calendar/"):
        raise AcquireError(f"not a UCI calendar-listing URL: {url}")
    if parts.path.rsplit("/", 1)[-1] not in LISTING_KINDS:
        raise AcquireError(f"not a listing endpoint: {url}")


def capture(*, out_dir: Path = SNAPSHOT_DIR, kinds: Sequence[str] = LISTING_KINDS,
            discipline: str = DISCIPLINE, fetcher: Optional[Fetcher] = None) -> Dict[str, Any]:
    """Fetch each listing once, save it verbatim, write ``calendar_raw.json``."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    f = fetcher or Fetcher()
    index: Dict[str, Any] = {"provider": PROVIDER, "capturer": f"uci_calendar {__version__}",
                             "discipline": discipline,
                             "captured_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                             "listings": {}, "complete": False}
    for kind in kinds:
        url = listing_url(kind, discipline)
        assert_well_formed_listing_url(url)
        r, err = f.get(url, accept="application/json")
        data = r.content if r is not None else None
        rows = None
        if r is not None and r.status_code != 200:
            err = f"HTTP {r.status_code}"
        elif data is not None:
            try:
                rows = len(parse_listing(json.loads(data.decode("utf-8"))))
            except (json.JSONDecodeError, UnicodeDecodeError, AcquireError) as exc:
                err = f"response is not a calendar listing: {exc}"
        name = f"{kind}_{discipline}.json"
        if data is not None:
            (out_dir / name).write_bytes(data)
        index["listings"][kind] = {
            "file": name if data is not None else None, "source_url": url,
            "http_status": r.status_code if r is not None else None,
            "content_type": r.headers.get("Content-Type") if r is not None else None,
            "bytes": len(data) if data is not None else 0,
            "sha256": sha256_bytes(data) if data is not None else None,
            "competitions": rows, "error": err,
        }
    index["complete"] = all(not v.get("error") for v in index["listings"].values())
    index["requests_made"] = f.requests_made
    (out_dir / INDEX_NAME).write_text(json.dumps(index, indent=1, ensure_ascii=False), encoding="utf-8")
    return index


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CalendarEntry:
    competition_id: str
    discipline: str
    year: int
    url: str
    name: str
    country: Optional[str] = None
    continent: Optional[str] = None
    venue: Optional[str] = None
    dates_text: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    observed_days: Tuple[str, ...] = ()
    listing: Optional[str] = None

    @property
    def full_url(self) -> str:
        return f"https://www.uci.org{self.url}" if self.url.startswith("/") else self.url

    def as_evidence(self) -> Dict[str, Any]:
        return {"competition_id": self.competition_id, "discipline": self.discipline,
                "url": self.full_url, "name": self.name, "country": self.country,
                "dates_text": self.dates_text, "start_date": self.start_date, "end_date": self.end_date,
                "listing": self.listing}


_DETAILS_RE = re.compile(r"^/competition-details/(\d{4})/([A-Z]{3})/(\d+)/?$")


def parse_dates_text(text: str) -> Tuple[Optional[str], Optional[str]]:
    """``"22 Aug - 13 Sep 2026"`` → ``("2026-08-22", "2026-09-13")``.

    Accepts ``"09 Sep 2026"`` (single day) and a year on either side of the
    dash.  A range that would end before it starts rolls the start back a year
    (December → January).  Anything else returns ``(None, None)`` — the caller
    then falls back to the days the entry was observed on.
    """
    if not text:
        return None, None
    parts = [p.strip() for p in re.split(r"\s*[-–]\s*", text.strip()) if p.strip()]
    if not 1 <= len(parts) <= 2:
        return None, None
    parsed: List[Tuple[int, int, Optional[int]]] = []
    for part in parts:
        m = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]{3,})\.?\s*(\d{4})?", part)
        if not m:
            return None, None
        month = _MONTHS.get(m.group(2)[:3].lower())
        if month is None:
            return None, None
        parsed.append((int(m.group(1)), month, int(m.group(3)) if m.group(3) else None))
    default_year = next((y for _d, _m, y in reversed(parsed) if y is not None), None)
    if default_year is None:
        return None, None
    try:
        dates = [dt.date(y or default_year, mo, d) for d, mo, y in parsed]
    except ValueError:
        return None, None
    start, end = dates[0], dates[-1]
    if end < start:                      # "28 Dec - 03 Jan 2027"
        try:
            start = start.replace(year=start.year - 1)
        except ValueError:
            return None, None
    return start.isoformat(), end.isoformat()


def parse_listing(doc: Any, *, listing: Optional[str] = None) -> List[CalendarEntry]:
    """One :class:`CalendarEntry` per competition in a listing response."""
    if not isinstance(doc, dict) or not isinstance(doc.get("items"), list):
        raise AcquireError("listing document has no top-level items[] (months)")
    seen: Dict[str, Dict[str, Any]] = {}
    for month in doc["items"]:
        for day in (month or {}).get("items") or []:
            day_iso = (day or {}).get("competitionDate")
            day_iso = day_iso[:10] if isinstance(day_iso, str) else None
            for comp in (day or {}).get("items") or []:
                url = ((comp or {}).get("detailsLink") or {}).get("url") or ""
                m = _DETAILS_RE.match(url)
                if not m:
                    continue
                year, discipline, cid = m.groups()
                bucket = seen.setdefault(cid, {"comp": comp, "year": int(year),
                                               "discipline": discipline, "url": url, "days": set()})
                if day_iso:
                    bucket["days"].add(day_iso)
    out: List[CalendarEntry] = []
    for cid, bucket in seen.items():
        comp = bucket["comp"]
        start, end = parse_dates_text(comp.get("dates") or "")
        days = tuple(sorted(bucket["days"]))
        out.append(CalendarEntry(
            competition_id=cid, discipline=bucket["discipline"], year=bucket["year"], url=bucket["url"],
            name=(comp.get("name") or "").strip(), country=comp.get("country") or None,
            continent=comp.get("continentCode") or None, venue=(comp.get("venue") or "").strip() or None,
            dates_text=comp.get("dates") or None, start_date=start, end_date=end,
            observed_days=days, listing=listing))
    return sorted(out, key=lambda e: (e.start_date or "9999", e.name, e.competition_id))


def load_snapshot(snapshot_dir: Path = SNAPSHOT_DIR) -> Tuple[List[CalendarEntry], Dict[str, Any]]:
    """Entries from every listing file in a capture directory, plus its index."""
    snapshot_dir = Path(snapshot_dir)
    index_path = snapshot_dir / INDEX_NAME
    if not index_path.exists():
        raise AcquireError(f"no calendar capture under {snapshot_dir} — run "
                           "`python -m cycling_project.nightly.uci_calendar capture` first")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    merged: Dict[str, CalendarEntry] = {}
    for kind, meta in (index.get("listings") or {}).items():
        name = meta.get("file")
        if not name or not (snapshot_dir / name).exists():
            continue
        doc = json.loads((snapshot_dir / name).read_text(encoding="utf-8"))
        for entry in parse_listing(doc, listing=kind):
            merged.setdefault(entry.competition_id, entry)
    return sorted(merged.values(), key=lambda e: (e.start_date or "9999", e.name)), index


def snapshot_provenance(index: Dict[str, Any]) -> Dict[str, Any]:
    return {"captured_at": index.get("captured_at"), "capturer": index.get("capturer"),
            "listings": {k: {"source_url": v.get("source_url"), "sha256": v.get("sha256"),
                             "competitions": v.get("competitions")}
                         for k, v in (index.get("listings") or {}).items()}}


# ---------------------------------------------------------------------------
# name normalisation and scoring
# ---------------------------------------------------------------------------

def normalise_name(name: str) -> str:
    plain = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    plain = re.sub(r"\b(?:19|20)\d{2}\b", " ", plain)
    plain = re.sub(r"[^a-z0-9]+", " ", plain)
    for pattern, replacement in _NAME_EXPANSIONS:
        plain = re.sub(pattern, replacement, plain)
    return " ".join(plain.split())


def name_variants(name: str) -> Dict[str, str]:
    """``full`` plus the head/tail around a ``" - "`` sponsor or memorial separator.

    ``"Gran Premio città di Peccioli - Coppa Sabatini"`` → head ``gran premio
    citta di peccioli``, tail ``coppa sabatini``; our calendar knows the race as
    the tail.  Variants are only ever compared against a *dated* candidate.
    """
    variants = {"full": normalise_name(name)}
    parts = [p for p in re.split(r"\s+[-–]\s+", name or "") if p.strip()]
    if len(parts) > 1:
        head, tail = normalise_name(parts[0]), normalise_name(parts[-1])
        if head:
            variants["head"] = head
        if tail:
            variants["tail"] = tail
    return {k: v for k, v in variants.items() if v}


def name_similarity(left: str, right: str) -> Tuple[float, str]:
    """Best ``difflib`` ratio over the variant pairs, with the pair that won."""
    best, which = 0.0, "full~full"
    for lk, lv in name_variants(left).items():
        for rk, rv in name_variants(right).items():
            ratio = difflib.SequenceMatcher(None, lv, rv).ratio()
            if ratio > best:
                best, which = ratio, f"{lk}~{rk}"
    return round(best, 4), which


def token_containment(left: str, right: str) -> float:
    """|shared tokens| / |smaller token set| — evidence only, never a decision."""
    a, b = set(normalise_name(left).split()), set(normalise_name(right).split())
    if not a or not b:
        return 0.0
    return round(len(a & b) / min(len(a), len(b)), 4)


# ---------------------------------------------------------------------------
# matching
# ---------------------------------------------------------------------------

@dataclass
class Candidate:
    entry: CalendarEntry
    dates_verdict: str          # exact | overlap | disjoint
    similarity: float
    variant: str
    containment: float

    def sort_key(self) -> Tuple[int, float, float]:
        rank = {"exact": 2, "overlap": 1, "disjoint": 0}[self.dates_verdict]
        return (rank, self.similarity, self.containment)


@dataclass
class CampaignMatch:
    slug: str
    campaign_name: str
    start_date: Optional[str]
    end_date: Optional[str]
    existing_url: Optional[str]
    best: Optional[Candidate] = None
    alternates: List[Candidate] = field(default_factory=list)
    decision: str = "no_candidate"          # auto_accepted | operator_confirm | no_candidate
    existing_agrees: Optional[bool] = None
    reasons: List[str] = field(default_factory=list)

    @property
    def auto_accept(self) -> bool:
        """What the CALENDAR says, independent of what the file already holds.

        Keeping the verdict free of prior writes is what makes the evidence
        block stable: re-running the matcher after it filled a URL must not
        flip the recorded decision (and rewrite every campaign file).
        """
        return self.decision == "auto_accepted"

    @property
    def needs_operator(self) -> bool:
        return self.decision != "auto_accepted" and not self.existing_url

    def evidence(self, provenance: Dict[str, Any]) -> Dict[str, Any]:
        best = self.best
        return {
            "matcher": f"uci_calendar {__version__}",
            "matched_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "decision": self.decision,
            # Only the CONFLICT is recorded, never "a URL is present": the field is
            # filled by this matcher on the run that accepts a candidate, and an
            # evidence block that flipped afterwards would rewrite every campaign
            # file on the next sync.
            "existing_url_conflict": self.existing_agrees is False,
            "auto_accept_rule": (f"exact date range AND name similarity >= {AUTO_ACCEPT_SIMILARITY:.2f} "
                                 "AND no other exact-date candidate at that bar"),
            "score": best.similarity if best else None,
            "fields_compared": {
                "dates": {"campaign": f"{self.start_date}..{self.end_date}",
                          "uci": f"{best.entry.start_date}..{best.entry.end_date}" if best else None,
                          "uci_text": best.entry.dates_text if best else None,
                          "verdict": best.dates_verdict if best else "no candidate"},
                "name": {"campaign": self.campaign_name,
                         "uci": best.entry.name if best else None,
                         "campaign_normalised": normalise_name(self.campaign_name),
                         "uci_normalised": normalise_name(best.entry.name) if best else None,
                         "variant": best.variant if best else None,
                         "similarity": best.similarity if best else None,
                         "token_containment": best.containment if best else None},
                "country": {"campaign": None, "uci": best.entry.country if best else None,
                            "verdict": "not_compared", "note": COUNTRY_NOTE},
            },
            "candidate": best.entry.as_evidence() if best else None,
            "alternates": [dict(c.entry.as_evidence(), similarity=c.similarity,
                                dates_verdict=c.dates_verdict) for c in self.alternates[:3]],
            "reasons": list(self.reasons),
            "snapshot": provenance,
        }

    def task_detail(self, provenance: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "campaign": self.slug, "campaign_name": self.campaign_name,
            "campaign_dates": f"{self.start_date}..{self.end_date}",
            "field": "uci_competition_url",
            "candidate": self.best.entry.as_evidence() if self.best else None,
            "similarity": self.best.similarity if self.best else None,
            "dates_verdict": self.best.dates_verdict if self.best else "no candidate",
            "alternates": [dict(c.entry.as_evidence(), similarity=c.similarity) for c in self.alternates[:3]],
            "reasons": list(self.reasons),
            "how_to_confirm": ("open the candidate URL, check the race, then set uci_competition_url / "
                               "uci_competition_id / uci_discipline in the campaign.json"),
            "snapshot": provenance,
        }


def _dates_verdict(campaign_start: Optional[str], campaign_end: Optional[str], entry: CalendarEntry) -> str:
    e_start = entry.start_date or (entry.observed_days[0] if entry.observed_days else None)
    e_end = entry.end_date or (entry.observed_days[-1] if entry.observed_days else None)
    if not (campaign_start and campaign_end and e_start and e_end):
        return "disjoint"
    if campaign_start == e_start and campaign_end == e_end:
        return "exact"
    return "overlap" if campaign_start <= e_end and e_start <= campaign_end else "disjoint"


def match_campaign(campaign: Dict[str, Any], entries: Iterable[CalendarEntry]) -> CampaignMatch:
    """Rank the calendar against one campaign; decide auto-accept vs operator task."""
    slug = campaign.get("slug") or ""
    name = campaign.get("name") or ""
    start, end = campaign.get("start_date"), campaign.get("end_date")
    year = campaign.get("year")
    match = CampaignMatch(slug=slug, campaign_name=name, start_date=start, end_date=end,
                          existing_url=campaign.get("uci_competition_url") or None)

    candidates: List[Candidate] = []
    for entry in entries:
        if year is not None and entry.year != int(year):
            continue
        verdict = _dates_verdict(start, end, entry)
        if verdict == "disjoint":
            continue
        similarity, variant = name_similarity(name, entry.name)
        candidates.append(Candidate(entry=entry, dates_verdict=verdict, similarity=similarity,
                                    variant=variant, containment=token_containment(name, entry.name)))
    candidates.sort(key=lambda c: c.sort_key(), reverse=True)
    if not candidates:
        match.reasons.append("no calendar entry overlaps the campaign dates")
        match.decision = "no_candidate"
        if match.existing_url:
            match.reasons.append("uci_competition_url is already set and is never overwritten")
        return match

    match.best = candidates[0]
    match.alternates = candidates[1:]
    best = match.best
    exact_at_bar = [c for c in candidates
                    if c.dates_verdict == "exact" and c.similarity >= AUTO_ACCEPT_SIMILARITY]
    if best.dates_verdict != "exact":
        match.reasons.append(f"date range {best.dates_verdict}, not exact "
                             f"({best.entry.start_date}..{best.entry.end_date})")
    if best.similarity < AUTO_ACCEPT_SIMILARITY:
        match.reasons.append(f"name similarity {best.similarity:.3f} below {AUTO_ACCEPT_SIMILARITY:.2f} "
                             f"({name!r} vs {best.entry.name!r})")
    if len(exact_at_bar) > 1:
        match.reasons.append("more than one exact-date candidate reaches the name bar: "
                             + ", ".join(f"{c.entry.competition_id} {c.entry.name!r}" for c in exact_at_bar))

    if match.existing_url:
        match.existing_agrees = match.existing_url.rstrip("/").endswith(f"/{best.entry.competition_id}")
        if not match.existing_agrees:
            match.reasons.append(f"uci_competition_url is already set to {match.existing_url} and is never "
                                 f"overwritten, but the calendar DISAGREES (it says {best.entry.competition_id} "
                                 f"{best.entry.name!r}) — a human should look")

    if not [r for r in match.reasons if "never\noverwritten" not in r and "is never " not in r]:
        match.decision = "auto_accepted"
        match.reasons.append(f"exact date range and name similarity {best.similarity:.3f} "
                             f"(variant {best.variant}) — unique at the bar")
    else:
        match.decision = "operator_confirm"
    return match


# ---------------------------------------------------------------------------
# campaigns
# ---------------------------------------------------------------------------

def horizon_campaigns(performance_eval: Path = PERFORMANCE_EVAL, *, horizon: int = 14,
                      now: Optional[dt.date] = None, back: int = 0) -> List[Tuple[Path, Dict[str, Any]]]:
    """Campaign files whose span intersects ``[now - back, now + horizon]``."""
    now = now or dt.date.today()
    lo, hi = now - dt.timedelta(days=back), now + dt.timedelta(days=horizon)
    out = []
    for path in sorted(Path(performance_eval).glob("*/campaign.json")):
        try:
            campaign = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        start, end = campaign.get("start_date"), campaign.get("end_date")
        if not (start and end):
            continue
        if dt.date.fromisoformat(end) >= lo and dt.date.fromisoformat(start) <= hi:
            out.append((path, campaign))
    return sorted(out, key=lambda pair: (pair[1].get("start_date") or "", pair[1].get("slug") or ""))


def _same_verdict(old: Any, new: Dict[str, Any]) -> bool:
    """Two evidence blocks that differ only in when they were written."""
    if not isinstance(old, dict):
        return False
    volatile = ("matched_at",)
    return ({k: v for k, v in old.items() if k not in volatile}
            == {k: v for k, v in new.items() if k not in volatile})


def apply_match(campaign: Dict[str, Any], match: CampaignMatch, provenance: Dict[str, Any]) -> Dict[str, Any]:
    """Return the campaign with the UCI fields and evidence applied.

    ``uci_competition_url`` is written **only** on ``auto_accepted`` and only
    when it is currently empty.  Evidence that says the same thing as the
    recorded block keeps its original ``matched_at``, so re-running the matcher
    (or a weekly ``registry sync``) does not churn every campaign file.
    """
    updated = dict(campaign)
    if match.auto_accept and not (campaign.get("uci_competition_url") or "").strip():
        entry = match.best.entry
        updated["uci_competition_url"] = entry.full_url
        updated["uci_competition_id"] = entry.competition_id
        updated["uci_discipline"] = entry.discipline
    evidence = match.evidence(provenance)
    if _same_verdict(campaign.get("uci_match_evidence"), evidence):
        evidence = campaign["uci_match_evidence"]
    updated["uci_match_evidence"] = evidence
    return updated


def _dump(campaign: Dict[str, Any]) -> str:
    return json.dumps(campaign, indent=2, ensure_ascii=False) + "\n"


def render_campaign(original_text: Optional[str], original: Dict[str, Any],
                    updated: Dict[str, Any]) -> str:
    """New file text that keeps a hand-formatted file byte-for-byte.

    ``registry.sync`` writes campaign files with ``json.dumps(indent=2)``, so
    re-dumping one of those changes only the keys we touched.  The Tour and
    Vuelta files are hand-written (compact stage rows); re-dumping them would
    reformat 200 lines the matcher never looked at.  When the file does not
    round-trip, the new keys are appended before the closing brace instead and
    every existing byte survives.
    """
    dumped = _dump(updated)
    if original_text is None or _dump(original) == original_text:
        return dumped
    added = {k: v for k, v in updated.items() if k not in original or original[k] != v}
    if any(k in original for k in added):          # an existing key changed — cannot append
        return dumped
    body = original_text.rstrip()
    if not body.endswith("}") or not added:
        return dumped
    tail = ",\n" + ",\n".join(
        f"  {json.dumps(k, ensure_ascii=False)}: " + json.dumps(v, indent=2, ensure_ascii=False).replace("\n", "\n  ")
        for k, v in added.items())
    return body[:-1].rstrip() + tail + "\n}\n"


def _write_campaign(path: Path, campaign: Dict[str, Any], *, original_text: Optional[str] = None,
                    original: Optional[Dict[str, Any]] = None) -> None:
    text = render_campaign(original_text, original if original is not None else {}, campaign)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def resolve(performance_eval: Path = PERFORMANCE_EVAL, *, snapshot_dir: Path = SNAPSHOT_DIR,
            horizon: int = 14, back: int = 0, now: Optional[dt.date] = None, dry_run: bool = False,
            store: Any = None, runs_dir: Optional[Path] = RUNS_DIR) -> Dict[str, Any]:
    """Match every horizon campaign against the snapshot; write files and tasks."""
    entries, index = load_snapshot(snapshot_dir)
    provenance = snapshot_provenance(index)
    results: List[Dict[str, Any]] = []
    matches: List[CampaignMatch] = []
    for path, campaign in horizon_campaigns(performance_eval, horizon=horizon, now=now, back=back):
        match = match_campaign(campaign, entries)
        matches.append(match)
        updated = apply_match(campaign, match, provenance)
        changed = updated != campaign
        if changed and not dry_run:
            _write_campaign(path, updated, original_text=path.read_text(encoding="utf-8"),
                            original=campaign)
        results.append({"slug": match.slug or path.parent.name, "path": str(path),
                        "decision": match.decision,
                        "url_already_set": bool(match.existing_url),
                        "existing_agrees": match.existing_agrees,
                        "uci_competition_url": updated.get("uci_competition_url"),
                        "score": match.best.similarity if match.best else None,
                        "dates_verdict": match.best.dates_verdict if match.best else None,
                        "candidate_name": match.best.entry.name if match.best else None,
                        "candidate_id": match.best.entry.competition_id if match.best else None,
                        "reasons": match.reasons, "changed": changed})

    pending = [m for m in matches if m.needs_operator]
    tasks: List[Dict[str, Any]] = []
    if pending and not dry_run:
        tasks = emit_tasks(pending, provenance, store=store, runs_dir=runs_dir)
    return {"snapshot": provenance, "calendar_entries": len(entries),
            "campaigns": results,
            "auto_accepted": sum(1 for m in matches if m.decision == "auto_accepted"),
            "operator_confirm": len(pending),
            "already_set": sum(1 for m in matches if m.existing_url),
            "tasks_written": len(tasks), "dry_run": dry_run}


def open_task_candidates(runs_dir: Optional[Path]) -> Dict[str, Optional[str]]:
    """``slug -> candidate competition id`` for unresolved confirm tasks already on file.

    The ledger is append-only, so re-running ``resolve`` must not stack a
    second identical task on the operator's inbox; a task is repeated only if
    the calendar now proposes a different competition.
    """
    out: Dict[str, Optional[str]] = {}
    path = Path(runs_dir) / "operator_tasks.jsonl" if runs_dir else None
    if not path or not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("kind") != TASK_KIND or row.get("resolved"):
            continue
        detail = row.get("detail") or {}
        slug = row.get("campaign") or detail.get("campaign")
        if slug:
            out[slug] = ((detail.get("candidate") or {}) or {}).get("competition_id")
    return out


def emit_tasks(pending: Sequence[CampaignMatch], provenance: Dict[str, Any], *,
               store: Any = None, runs_dir: Optional[Path] = RUNS_DIR) -> List[Dict[str, Any]]:
    """One ``uci_competition_confirm`` task per unresolved campaign.

    Per campaign rather than one grouped row: each is confirmed (or dismissed)
    on its own, and a race that is settled tonight should not wait behind ten
    others.
    """
    from cycling_project.nightly.crosswalk import build_operator_task
    from cycling_project.nightly.store_local import JsonlStore

    sink = store if store is not None else JsonlStore(runs_dir=Path(runs_dir) if runs_dir else None)
    already = open_task_candidates(Path(runs_dir) if runs_dir else None)
    written = []
    for match in pending:
        best = match.best
        candidate_id = best.entry.competition_id if best else None
        if already.get(match.slug) == candidate_id:
            logger.info("uci_competition_confirm task for %s already open on candidate %s — not repeated",
                        match.slug, candidate_id)
            continue
        summary = (f"{match.slug}: confirm the UCI competition URL "
                   + (f"(best candidate {best.entry.competition_id} {best.entry.name!r}, "
                      f"name similarity {best.similarity:.3f})" if best else "(no calendar candidate)"))
        written.append(sink.insert_task(build_operator_task(
            TASK_KIND, match.slug, summary, match.task_detail(provenance), urgency="blocks_settlement")))
    return written


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _table(result: Dict[str, Any]) -> str:
    rows = [("campaign", "decision", "score", "dates", "uci id", "url")]
    for row in result["campaigns"]:
        decision = row["decision"] + (" (url already set)" if row.get("url_already_set") else "")
        rows.append((row["slug"], decision,
                     f"{row['score']:.3f}" if row["score"] is not None else "-",
                     row["dates_verdict"] or "-", row["candidate_id"] or "-",
                     row["uci_competition_url"] or "-"))
    widths = [max(len(str(r[i])) for r in rows) for i in range(len(rows[0]))]
    return "\n".join("  ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row)) for row in rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    cap = sub.add_parser("capture", help="fetch the road calendar listings (2 requests) and archive them")
    cap.add_argument("--out", type=Path, default=SNAPSHOT_DIR)
    cap.add_argument("--discipline", default=DISCIPLINE)
    cap.add_argument("--kinds", default=",".join(LISTING_KINDS))
    cap.add_argument("--min-interval", type=float, default=3.0)

    for name, help_text in (("resolve", "match campaigns and write the URLs"),
                            ("report", "print the match table without writing anything")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--performance-eval", type=Path, default=PERFORMANCE_EVAL)
        p.add_argument("--snapshot", type=Path, default=SNAPSHOT_DIR)
        p.add_argument("--horizon", type=int, default=14)
        p.add_argument("--back", type=int, default=0,
                       help="also include campaigns that ended within this many days")
        p.add_argument("--now", type=dt.date.fromisoformat, default=None)
        p.add_argument("--runs-dir", type=Path, default=RUNS_DIR)
        if name == "resolve":
            p.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "capture":
            index = capture(out_dir=args.out, discipline=args.discipline,
                            kinds=tuple(k.strip() for k in args.kinds.split(",") if k.strip()),
                            fetcher=Fetcher(min_interval=max(3.0, args.min_interval)))
            print(json.dumps(index, indent=1, ensure_ascii=False))
            return EXIT_OK if index.get("complete") else EXIT_FAILED
        result = resolve(args.performance_eval, snapshot_dir=args.snapshot, horizon=args.horizon,
                         back=args.back, now=args.now, runs_dir=args.runs_dir,
                         dry_run=args.command == "report" or getattr(args, "dry_run", False))
    except AcquireError as exc:
        print(json.dumps({"status": "failed", "error_class": "uci_calendar", "message": str(exc)}, indent=1))
        return EXIT_FAILED
    print(_table(result))
    print(json.dumps({k: v for k, v in result.items() if k != "campaigns"}, indent=1, ensure_ascii=False))
    return EXIT_OPEN if result["operator_confirm"] else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
