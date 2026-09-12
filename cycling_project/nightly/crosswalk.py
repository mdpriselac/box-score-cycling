"""Rider crosswalk: PCS startlist rows ↔ the ``riders`` table.

Spec: NIGHTLY_AGENT_WORKFLOW.md §1a / §2.8 / §2.12 and AGENT_DESIGN.md §3.4.
**Wrong is worse than missing.** The matcher therefore auto-accepts a match
only at confidence ≥ 0.97, which exactly two evidence patterns reach:

1. exact normalised name **and** matching birth year, or
2. exact normalised name that is **unique in the DB**, with no conflicting
   birth year. Team history corroborates a match but does not veto it because
   it can lag transfers.

Everything else becomes a *proposal* (``crosswalk_proposals`` + an operator
task). Confirmation is a human action (``confirm``) that runs with the
operator role — never the agent key. The agent-facing entry points
(``seed``, ``propose``, ``coverage``, ``match_startlist``) never call it;
``tests/unit/test_nightly_crosswalk.py`` asserts that statically.

Name handling
-------------
FirstCycling writes "Surname Firstname" (``Roglic Primoz``); PCS writes
"SURNAME Firstname" (``ROGLIČ Primož``) with the surname in capitals. Both
are reduced to an order-insensitive key: NFD accent strip, casefold,
hyphens/apostrophes/periods → spaces, tokens sorted. Known FirstCycling
drift (Gee → Gee-West, Martin → Martin-Guyonnet, Plapp Lucas/Luke) is an
explicit alias table so those pairs count as *exact*; any other partial
overlap (one token set a subset of the other) is only ever a proposal.

Local mirror: ``performance_eval/crosswalk/rider_crosswalk.csv`` (committed;
the repo copy wins on conflict at ``import``). Proposals and operator tasks
are mirrored to ``performance_eval/runs/*.jsonl``.

Usage::

    uv run python -m cycling_project.nightly.crosswalk seed \
        --startlist performance_eval/vuelta-2026 --race-id 23 --year 2026
    uv run python -m cycling_project.nightly.crosswalk propose --startlist <html|csv|campaign>
    uv run python -m cycling_project.nightly.crosswalk confirm --pcs-slug X --fc-rider-id Y --by matt
    uv run python -m cycling_project.nightly.crosswalk export --to bundle/rider_crosswalk.csv
    uv run python -m cycling_project.nightly.crosswalk import --from pulled.csv
    uv run python -m cycling_project.nightly.crosswalk coverage --campaign performance_eval/vuelta-2026
"""

from __future__ import annotations

import argparse
import csv
import difflib
import json
import os
import re
import sqlite3
import sys
import unicodedata
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

from cycling_project.nightly.store_local import JsonlStore, open_store, utcnow_iso
from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CROSSWALK_DIR = PROJECT_ROOT / "performance_eval" / "crosswalk"
CROSSWALK_CSV = CROSSWALK_DIR / "rider_crosswalk.csv"
PENDING_JSON = CROSSWALK_DIR / "pending_proposals.json"
RUNS_DIR = PROJECT_ROOT / "performance_eval" / "runs"
DEFAULT_DB_PATH = (
    PROJECT_ROOT / "cycling_project" / "webscrape_tools" / "database" / "database" / "cycling_races.db"
)

AUTO_ACCEPT = 0.97
EXIT_OK, EXIT_WAITING, EXIT_FAILED = 0, 10, 20

CSV_FIELDS = [
    "pcs_slug", "fc_rider_id", "internal_rider_id", "pcs_name", "fc_name",
    "birth_year", "confidence", "source", "confirmed_by", "created_at",
]

# Known FirstCycling renames. Keys and values are *name keys* (see name_key);
# the table is symmetric at lookup time.
KNOWN_ALIASES: dict[str, str] = {
    "derek gee": "derek gee west",                    # Gee → Gee-West
    "guillaume martin": "guillaume guyonnet martin",  # Martin → Martin-Guyonnet
    "lucas plapp": "luke plapp",                      # Plapp Lucas / Luke
}

# Given-name nicknames PCS uses where FirstCycling has the formal name. A
# nickname-resolved equality is *not* exact: it caps at 0.95 (proposal).
NICKNAMES: dict[str, str] = {
    "eddie": "edward", "ed": "edward", "larry": "lawrence", "will": "william", "bill": "william",
    "ben": "benjamin", "sam": "samuel", "alex": "alexander", "max": "maximilian", "matt": "matthew",
    "mike": "michael", "nick": "nicholas", "chris": "christopher", "tom": "thomas", "dan": "daniel",
    "joe": "joseph", "jack": "john", "harry": "harold", "fred": "frederick", "kim": "kimberly",
}

TEAM_STOPWORDS = frozenset({"team", "pro", "cycling", "wt", "prt", "ct", "the", "de", "la"})
# Second-to-last FC tokens that mark a two-word given name ("Martin Muñoz
# Jose Maria" → given "Jose Maria"). Used only to *derive* a PCS slug.
GIVEN_NAME_CONNECTORS = frozenset({
    "jose", "juan", "maria", "luis", "carlos", "miguel", "pedro", "angel", "antonio",
    "francisco", "jesus", "manuel", "rafael", "javier", "joao", "jean", "marc",
})


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

def strip_accents(text: str) -> str:
    """NFD-decompose and drop combining marks; also fold a few letters NFD leaves alone."""
    text = text.replace("ø", "o").replace("Ø", "O").replace("æ", "ae").replace("Æ", "AE")
    text = text.replace("ß", "ss").replace("ł", "l").replace("Ł", "L").replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def name_tokens(name: str) -> list[str]:
    """Casefolded, accent-free tokens; hyphens/apostrophes/periods split."""
    cleaned = strip_accents(name or "").casefold()
    cleaned = re.sub(r"[-'’.,/()]", " ", cleaned)
    return [t for t in cleaned.split() if t]


def name_key(name: str) -> str:
    """Order-insensitive normalised name: sorted tokens joined by a space."""
    return " ".join(sorted(name_tokens(name)))


def alias_keys(key: str) -> set[str]:
    """The key plus every known-drift alias of it (symmetric)."""
    out = {key}
    for a, b in KNOWN_ALIASES.items():
        if key == a:
            out.add(b)
        elif key == b:
            out.add(a)
    return out


def normalize_team(team: Optional[str]) -> frozenset[str]:
    if not team:
        return frozenset()
    cleaned = re.sub(r"\([^)]*\)", " ", strip_accents(team).casefold())
    tokens = re.sub(r"[^a-z0-9]+", " ", cleaned).split()
    return frozenset(t for t in tokens if len(t) > 1 and t not in TEAM_STOPWORDS)


def teams_match(a: Optional[str], b: Optional[str]) -> bool:
    ta, tb = normalize_team(a), normalize_team(b)
    if not ta or not tb:
        return False
    if ta <= tb or tb <= ta:
        return True
    return len(ta & tb) / len(ta | tb) >= 0.5


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", strip_accents(text).casefold()).strip("-")


def split_fc_name(fc_name: str) -> tuple[list[str], list[str]]:
    """FirstCycling "Surname Firstname" → (surname tokens, given tokens).

    Deterministic heuristic: the last token is the given name, unless the
    penultimate token is a known given-name connector (two-word given names).
    Hyphenated parts stay joined here so ``Fisher-Black Finn`` slugs to
    ``finn-fisher-black``.
    """
    raw = [t for t in re.sub(r"\s+", " ", (fc_name or "").strip()).split(" ") if t]
    if len(raw) <= 1:
        return raw, []
    given_n = 1
    if len(raw) >= 3 and strip_accents(raw[-2]).casefold() in GIVEN_NAME_CONNECTORS:
        given_n = 2
    return raw[:-given_n], raw[-given_n:]


def derive_pcs_slug(fc_name: str) -> str:
    """Deterministic PCS-style slug from a FirstCycling name (``firstname-surname``)."""
    surname, given = split_fc_name(fc_name)
    return slugify(" ".join(given + surname))


def split_pcs_name(pcs_name: str) -> tuple[str, str]:
    """PCS "SURNAME Firstname" → (surname, given). Capitalised tokens = surname."""
    tokens = (pcs_name or "").split()
    surname = [t for t in tokens if t.isupper() and len(t) > 1 or t in {"DE", "VAN", "DER", "DEN", "VON", "DA", "DI"}]
    given = [t for t in tokens if t not in surname]
    if not surname:  # fall back to the FC-style guess
        return " ".join(tokens[:-1]), tokens[-1] if tokens else ""
    return " ".join(surname), " ".join(given)


def pcs_name_to_fc_order(pcs_name: str) -> str:
    """"ROGLIČ Primož" → "Roglič Primož" (FirstCycling order, title case surname)."""
    surname, given = split_pcs_name(pcs_name)
    return " ".join(p for p in (surname.title(), given) if p)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RiderRecord:
    internal_id: int
    fc_rider_id: str
    name: str
    birth_year: Optional[int] = None
    teams: frozenset[str] = frozenset()   # raw team names seen for the rider

    @property
    def key(self) -> str:
        return name_key(self.name)


@dataclass
class PcsRow:
    slug: str
    name: str
    team: Optional[str] = None
    bib: Optional[str] = None
    birth_year: Optional[int] = None
    source: str = "pcs_startlist"          # or "derived"
    # FC id of the rider wearing the same bib for the same team on the race's
    # cached FirstCycling startlist. Evidence for a *proposal* only.
    hint_fc_id: Optional[str] = None


@dataclass
class MatchResult:
    pcs: PcsRow
    rider: Optional[RiderRecord]
    confidence: float
    reasons: list[str] = field(default_factory=list)
    alternates: list[RiderRecord] = field(default_factory=list)

    @property
    def auto_accept(self) -> bool:
        return self.rider is not None and self.confidence >= AUTO_ACCEPT

    def to_crosswalk_row(self, source: Optional[str] = None) -> dict[str, Any]:
        assert self.rider is not None
        return {
            "pcs_slug": self.pcs.slug,
            "fc_rider_id": self.rider.fc_rider_id,
            "internal_rider_id": self.rider.internal_id,
            "pcs_name": self.pcs.name,
            "fc_name": self.rider.name,
            "birth_year": self.rider.birth_year or "",
            "confidence": f"{self.confidence:.2f}",
            "source": source or self.pcs.source,
            "confirmed_by": "",
            "created_at": utcnow_iso(),
        }

    def to_proposal(self) -> dict[str, Any]:
        return {
            "pcs_slug": self.pcs.slug,
            "pcs_name": self.pcs.name,
            "pcs_team": self.pcs.team,
            "pcs_bib": self.pcs.bib,
            "fc_rider_id": self.rider.fc_rider_id if self.rider else None,
            "internal_rider_id": self.rider.internal_id if self.rider else None,
            "fc_name": self.rider.name if self.rider else None,
            "confidence": round(self.confidence, 2),
            "evidence": "; ".join(self.reasons),
            "alternates": [
                {"fc_rider_id": r.fc_rider_id, "internal_rider_id": r.internal_id,
                 "fc_name": r.name, "birth_year": r.birth_year}
                for r in self.alternates
            ],
            "author": "agent",
            "status": "proposed",
        }


class RiderIndex:
    """In-memory index over ``riders`` with team evidence from
    ``cached_start_lists`` and ``rider_team_history``."""

    def __init__(self, riders: Iterable[RiderRecord]):
        self.riders: list[RiderRecord] = list(riders)
        self.by_key: dict[str, list[RiderRecord]] = defaultdict(list)
        self.by_token: dict[str, set[int]] = defaultdict(set)
        self.by_fc_id: dict[str, RiderRecord] = {}
        for i, r in enumerate(self.riders):
            self.by_key[r.key].append(r)
            self.by_fc_id[str(r.fc_rider_id)] = r
            for t in name_tokens(r.name):
                self.by_token[t].add(i)

    def __len__(self) -> int:
        return len(self.riders)

    def exact(self, key: str) -> list[RiderRecord]:
        out: list[RiderRecord] = []
        for k in alias_keys(key):
            out.extend(self.by_key.get(k, []))
        return out

    def sharing_tokens(self, tokens: Sequence[str]) -> list[RiderRecord]:
        idx: set[int] = set()
        for t in tokens:
            idx |= self.by_token.get(t, set())
        return [self.riders[i] for i in sorted(idx)]

    @classmethod
    def from_sqlite(cls, db_path: Path | str, fc_race_id: Optional[str] = None,
                    year: Optional[int] = None) -> "RiderIndex":
        conn = sqlite3.connect(str(db_path))
        try:
            rows = conn.execute("SELECT id, fc_rider_id, name, birth_year FROM riders").fetchall()
            teams: dict[str, set[str]] = defaultdict(set)
            # Team evidence 1: the race's own cached startlist (strongest) —
            # or every cached startlist when no race is given.
            if fc_race_id is not None and year is not None:
                q = ("SELECT rider_fc_id, team_name FROM cached_start_lists "
                     "WHERE fc_race_id = ? AND year = ?")
                params: tuple = (str(fc_race_id), int(year))
            else:
                q = "SELECT rider_fc_id, team_name FROM cached_start_lists"
                params = ()
            for fc_id, team in conn.execute(q, params):
                if team:
                    teams[str(fc_id)].add(team)
            # Team evidence 2: rider_team_history (latest year per rider).
            for fc_id, team in conn.execute(
                "SELECT r.fc_rider_id, t.name FROM rider_team_history h "
                "JOIN riders r ON r.id = h.rider_id JOIN teams t ON t.id = h.team_id "
                "WHERE h.year = (SELECT MAX(year) FROM rider_team_history h2 WHERE h2.rider_id = h.rider_id)"
            ):
                if team:
                    teams[str(fc_id)].add(team)
        finally:
            conn.close()
        return cls(
            RiderRecord(int(i), str(fc), n, int(by) if by is not None else None,
                        frozenset(teams.get(str(fc), ())))
            for i, fc, n, by in rows
        )


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def _subset_match(a: Sequence[str], b: Sequence[str]) -> bool:
    sa, sb = set(a), set(b)
    if sa == sb:
        return False
    return (sa < sb or sb < sa) and len(sa & sb) >= 2


def match_row(pcs: PcsRow, index: RiderIndex,
              race_fc_ids: Optional[set[str]] = None) -> MatchResult:
    """Score a single PCS startlist row against the rider index.

    ``race_fc_ids`` (the FC ids on the same race's cached startlist) is a
    tie-breaker for homonyms only; uniqueness is always judged DB-wide.
    """
    key = name_key(pcs.name)
    tokens = name_tokens(pcs.name)
    exact = index.exact(key)

    def team_ok(r: RiderRecord) -> bool:
        return any(teams_match(pcs.team, t) for t in r.teams)

    def year_ok(r: RiderRecord) -> Optional[bool]:
        if pcs.birth_year is None or r.birth_year is None:
            return None
        return int(pcs.birth_year) == int(r.birth_year)

    if exact:
        unique = len(exact) == 1
        # Rule 1: exact name + birth year.
        by_year = [r for r in exact if year_ok(r) is True]
        if len(by_year) == 1:
            r = by_year[0]
            reasons = ["exact normalised name", f"birth year {r.birth_year} matches"]
            if team_ok(r):
                reasons.append("team matches")
            return MatchResult(pcs, r, 0.99, reasons, [x for x in exact if x is not r])
        if len(by_year) > 1:
            return MatchResult(pcs, None, 0.50,
                               ["exact name + birth year shared by several riders"], by_year)
        # Rule 2: an exact normalised name that is unique DB-wide is an
        # identity, not an operator decision. Current provider team names can
        # legitimately disagree with our latest stored team after a transfer.
        # A known birth-year conflict remains a hard stop above.
        if unique:
            r = exact[0]
            yr = year_ok(r)
            if yr is False:
                return MatchResult(pcs, r, 0.40,
                                   ["exact normalised name", f"birth year MISMATCH pcs={pcs.birth_year} db={r.birth_year}"])
            if team_ok(r):
                return MatchResult(pcs, r, 0.97, ["exact normalised name", "unique in DB", "team matches"])
            if pcs.team and r.teams:
                return MatchResult(pcs, r, 0.97,
                                   ["exact normalised name", "unique in DB", "team differs (non-vetoing)"])
            return MatchResult(pcs, r, 0.97,
                               ["exact normalised name", "unique in DB", "no conflicting identity evidence"])
        # Homonyms without a birth-year discriminator: proposal only.
        by_team = [r for r in exact if team_ok(r)]
        in_race = [r for r in exact if race_fc_ids and r.fc_rider_id in race_fc_ids]
        pick = by_team if len(by_team) == 1 else in_race if len(in_race) == 1 else []
        if pick:
            r = pick[0]
            why = "team matches" if pick is by_team else "on the race's cached startlist"
            return MatchResult(pcs, r, 0.85, ["exact name shared by several riders (homonym)", why],
                               [x for x in exact if x is not r])
        return MatchResult(pcs, None, 0.50,
                           [f"exact name shared by {len(exact)} riders (homonym); no discriminator"], exact)

    # Nickname-resolved exact ("BARTA Will" ↔ "Barta William"): strong but
    # never auto-accepted — capped at 0.95.
    nick_key = " ".join(sorted(NICKNAMES.get(t, t) for t in tokens))
    if nick_key != key:
        nick_exact = [r for r in index.riders if " ".join(sorted(NICKNAMES.get(t, t) for t in name_tokens(r.name))) == nick_key]
        if len(nick_exact) == 1:
            r = nick_exact[0]
            conf, why = 0.85, ["exact name after nickname resolution"]
            if year_ok(r) is True:
                conf, why = 0.92, why + [f"birth year {r.birth_year} matches"]
            if team_ok(r):
                conf, why = min(0.95, conf + 0.03), why + ["team matches"]
            return MatchResult(pcs, r, conf, why)

    # Partial: one token set is a subset of the other (unknown hyphen drift,
    # dropped middle names). Never auto-accepted.
    candidates = index.sharing_tokens(tokens)
    subset = [r for r in candidates if _subset_match(tokens, name_tokens(r.name))]
    if subset:
        scored: list[tuple[float, list[str], RiderRecord]] = []
        for r in subset:
            conf, why = 0.80, ["partial name (token subset)"]
            if year_ok(r) is True:
                conf, why = 0.93, why + [f"birth year {r.birth_year} matches"]
            elif year_ok(r) is False:
                conf, why = 0.30, why + ["birth year mismatch"]
            if team_ok(r):
                conf, why = min(0.94, conf + 0.05), why + ["team matches"]
            scored.append((conf, why, r))
        scored.sort(key=lambda x: -x[0])
        conf, why, r = scored[0]
        return MatchResult(pcs, r, conf, why, [x[2] for x in scored[1:]])

    # Fuzzy: sequence ratio on sorted-token strings, among riders sharing a token.
    best: list[tuple[float, RiderRecord]] = []
    for r in candidates:
        ratio = difflib.SequenceMatcher(None, key, r.key).ratio()
        if ratio >= 0.85:
            best.append((ratio, r))
    if best:
        best.sort(key=lambda x: -x[0])
        ratio, r = best[0]
        conf = 0.60 + (ratio - 0.85)
        why = [f"fuzzy name similarity {ratio:.2f}"]
        if year_ok(r) is True:
            conf, why = conf + 0.10, why + [f"birth year {r.birth_year} matches"]
        if team_ok(r):
            conf, why = conf + 0.10, why + ["team matches"]
        return MatchResult(pcs, r, min(0.94, round(conf, 2)), why, [x[1] for x in best[1:4]])

    # Last resort: the rider wearing the same bib for the same team on the
    # race's FirstCycling startlist. Names differ, so this is a proposal
    # with a named candidate — never an acceptance.
    if pcs.hint_fc_id and pcs.hint_fc_id in index.by_fc_id:
        r = index.by_fc_id[pcs.hint_fc_id]
        why = ["same bib and team on the race's cached FC startlist", "names differ"]
        conf = 0.75
        if year_ok(r) is True:
            conf, why = 0.80, why + [f"birth year {r.birth_year} matches"]
        return MatchResult(pcs, r, conf, why)

    return MatchResult(pcs, None, 0.0, ["no candidate"])


def match_startlist(rows: Iterable[PcsRow], index: RiderIndex,
                    race_fc_ids: Optional[set[str]] = None) -> list[MatchResult]:
    return [match_row(r, index, race_fc_ids) for r in rows]


# ---------------------------------------------------------------------------
# Startlist loaders
# ---------------------------------------------------------------------------

def load_pcs_startlist_html(path: Path, source: str = "pcs_startlist") -> list[PcsRow]:
    """Parse a saved PCS startlist page (``div.ridersCont`` blocks)."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(Path(path).read_text(encoding="utf-8", errors="replace"), "html.parser")
    rows: list[PcsRow] = []
    for cont in soup.select("div.ridersCont"):
        team_a = cont.select_one("a[href^='team/']")
        team = team_a.get_text(" ", strip=True) if team_a else None
        for li in cont.select("ul li"):
            a = li.select_one("a[href^='rider/']")
            if a is None:
                continue
            slug = a["href"].split("rider/", 1)[1].strip("/")
            bib_el = li.select_one("span.bib")
            rows.append(PcsRow(slug=slug, name=a.get_text(" ", strip=True), team=team,
                               bib=bib_el.get_text(strip=True) if bib_el else None, source=source))
    return rows


def load_startlist_csv(path: Path) -> list[PcsRow]:
    """CSV with columns ``pcs_slug|slug, name, team, bib, birth_year`` (extras ignored)."""
    rows: list[PcsRow] = []
    with open(path, newline="", encoding="utf-8") as f:
        for rec in csv.DictReader(f):
            slug = rec.get("pcs_slug") or rec.get("slug") or derive_pcs_slug(rec.get("name", ""))
            by = rec.get("birth_year") or rec.get("dob") or ""
            rows.append(PcsRow(slug=slug, name=rec.get("name", ""), team=rec.get("team") or None,
                               bib=rec.get("bib") or rec.get("bib_number") or None,
                               birth_year=int(by[:4]) if by[:4].isdigit() else None,
                               source=rec.get("source") or "pcs_startlist"))
    return rows


def read_campaign_json(campaign_dir: Path) -> dict[str, Any]:
    p = Path(campaign_dir) / "campaign.json"
    return json.loads(p.read_text()) if p.exists() else {}


def campaign_identity(campaign_dir: Path, race_id: Optional[str], year: Optional[int]) -> tuple[str, int]:
    meta = read_campaign_json(campaign_dir)
    rid = race_id or meta.get("fc_race_id")
    yr = year or meta.get("year") or (meta.get("start_date") or "")[:4]
    if rid is None or not str(yr).isdigit():
        raise SystemExit(f"cannot determine race id/year for {campaign_dir}: pass --race-id and --year")
    return str(rid), int(yr)


def campaign_dobs(campaign_dir: Path) -> dict[str, int]:
    """fc_rider_id → birth year from every ``results/stage_NN/results.csv`` + ``gc.csv``."""
    out: dict[str, int] = {}
    for p in sorted(Path(campaign_dir).glob("results/stage_*/*.csv")):
        with open(p, newline="", encoding="utf-8") as f:
            for rec in csv.DictReader(f):
                dob = (rec.get("dob") or "")[:4]
                if dob.isdigit() and rec.get("rider_id"):
                    out[str(rec["rider_id"])] = int(dob)
    return out


def load_campaign_field(campaign_dir: Path, db_path: Path, race_id: Optional[str] = None,
                        year: Optional[int] = None) -> tuple[list[dict[str, Any]], str, int]:
    """The FC-side field: cached startlist rows for the campaign's race, with
    birth years from the archived results. Returns (rows, fc_race_id, year)."""
    rid, yr = campaign_identity(campaign_dir, race_id, year)
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            "SELECT c.rider_fc_id, c.rider_name, c.team_name, c.team_fc_id, c.bib_number, r.id, r.birth_year "
            "FROM cached_start_lists c LEFT JOIN riders r ON r.fc_rider_id = c.rider_fc_id "
            "WHERE c.fc_race_id = ? AND c.year = ? ORDER BY CAST(c.bib_number AS INTEGER), c.rider_fc_id",
            (rid, yr),
        ).fetchall()
    finally:
        conn.close()
    dobs = campaign_dobs(campaign_dir)
    field_rows = []
    for fc_id, name, team, team_fc, bib, internal_id, by in rows:
        field_rows.append({
            "fc_rider_id": str(fc_id), "fc_name": name, "team": team, "team_fc_id": team_fc,
            "bib": bib, "internal_rider_id": internal_id,
            "birth_year": by if by is not None else dobs.get(str(fc_id)),
        })
    return field_rows, rid, yr


def campaign_pcs_startlist(campaign_dir: Path) -> Optional[Path]:
    for rel in ("results/pcs/startlist.html", "results/startlist/pcs/startlist.html", "pcs_startlist.html"):
        p = Path(campaign_dir) / rel
        if p.exists():
            return p
    return None


def derived_rows_from_field(field_rows: Iterable[dict[str, Any]]) -> list[PcsRow]:
    """PCS rows *derived* from the FC field when no PCS page is available.
    Slugs are deterministic guesses; ``source='derived'`` marks them."""
    return [
        PcsRow(slug=derive_pcs_slug(r["fc_name"]), name=r["fc_name"], team=r.get("team"),
               bib=r.get("bib"), birth_year=r.get("birth_year"), source="derived")
        for r in field_rows
    ]


def load_startlist(spec: str, db_path: Path, race_id: Optional[str] = None,
                   year: Optional[int] = None) -> tuple[list[PcsRow], Optional[set[str]], Optional[tuple[str, int]]]:
    """``--startlist`` accepts a PCS HTML page, a CSV, or a campaign directory.

    Returns (pcs rows, FC ids of the race field or None, (race id, year) or None).
    For a campaign the PCS page saved under ``results/pcs/startlist.html`` is
    used when present; otherwise rows are derived from the cached FC field
    and their birth years come from the archived results.
    """
    p = Path(spec)
    if p.is_dir():
        field_rows, rid, yr = load_campaign_field(p, db_path, race_id, year)
        race_ids = {r["fc_rider_id"] for r in field_rows}
        html = campaign_pcs_startlist(p)
        if html is not None:
            rows = load_pcs_startlist_html(html)
            # Fold in birth years from the FC field by (bib, team) so rule 1
            # can fire: PCS startlists do not show birth years.
            by_bib = {(str(r["bib"]), normalize_team(r["team"])): r for r in field_rows if r.get("bib")}
            for row in rows:
                fr = by_bib.get((str(row.bib), normalize_team(row.team)))
                if fr is None:
                    fr = next((r for r in field_rows if str(r.get("bib")) == str(row.bib)
                               and teams_match(r.get("team"), row.team)), None)
                if fr is None:
                    continue
                row.hint_fc_id = str(fr["fc_rider_id"])
                if fr.get("birth_year") and _names_compatible(row.name, fr["fc_name"]):
                    row.birth_year = int(fr["birth_year"])
            return rows, race_ids, (rid, yr)
        logger.warning("no PCS startlist under %s; deriving slugs from the FC field (source=derived)", p)
        return derived_rows_from_field(field_rows), race_ids, (rid, yr)
    if p.suffix.lower() in {".html", ".htm"}:
        return load_pcs_startlist_html(p), None, None
    return load_startlist_csv(p), None, None


def _names_compatible(pcs_name: str, fc_name: str) -> bool:
    """Same bib+team is strong, but only carry the birth year across when
    the names at least share a token — a transposed PCS row must not inherit
    another rider's year and then auto-accept."""
    return bool(set(name_tokens(pcs_name)) & set(name_tokens(fc_name)))


# ---------------------------------------------------------------------------
# CSV mirror
# ---------------------------------------------------------------------------

def read_crosswalk_csv(path: Path = CROSSWALK_CSV) -> list[dict[str, str]]:
    if not Path(path).exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def write_crosswalk_csv(rows: Iterable[dict[str, Any]], path: Path = CROSSWALK_CSV) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(rows, key=lambda r: (str(r.get("pcs_slug", "")), str(r.get("fc_rider_id", ""))))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for r in ordered:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in CSV_FIELDS})
    return path


def merge_crosswalk(repo_rows: Iterable[dict[str, Any]], incoming: Iterable[dict[str, Any]],
                    *, repo_wins: bool = True) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Merge by ``pcs_slug``. Returns (merged, conflicts).

    A conflict is the same slug mapped to a different ``fc_rider_id``. With
    ``repo_wins`` (the committed copy is authoritative) the repo row is kept
    and the conflict reported; otherwise the incoming row replaces it. Rows
    for a slug already present with the same rider are refreshed only when
    the incoming confidence is higher or it carries a confirmation.
    """
    merged: dict[str, dict[str, Any]] = {str(r["pcs_slug"]): dict(r) for r in repo_rows}
    conflicts: list[dict[str, Any]] = []
    for row in incoming:
        slug = str(row["pcs_slug"])
        cur = merged.get(slug)
        if cur is None:
            merged[slug] = dict(row)
            continue
        if str(cur.get("fc_rider_id")) != str(row.get("fc_rider_id")):
            conflicts.append({"pcs_slug": slug, "repo": cur, "incoming": dict(row)})
            if not repo_wins:
                merged[slug] = dict(row)
            continue
        if row.get("confirmed_by") or float(row.get("confidence") or 0) > float(cur.get("confidence") or 0):
            merged[slug] = dict(row)
    return list(merged.values()), conflicts


# ---------------------------------------------------------------------------
# Operator task + proposal plumbing (agent-facing)
# ---------------------------------------------------------------------------

# The ledger's vocabulary (supabase/migrations/0001_control_plane.sql, operator_tasks.urgency CHECK).
# 2026-09-08: the first cloud run lost every operator task to HTTP 400 because the driver said
# "tonight" — a word the schema does not know.  Anything outside this set is filed as 'urgent'
# with the requested word kept in detail.urgency_requested, so the task still reaches the inbox.
URGENCIES = ("routine", "blocks_publication", "blocks_settlement", "urgent")


def normalise_urgency(urgency: Optional[str], detail: dict[str, Any]) -> str:
    if urgency in URGENCIES:
        return urgency
    detail.setdefault("urgency_requested", urgency)
    return "urgent"


def build_operator_task(kind: str, campaign: Optional[str], summary: str,
                        detail: dict[str, Any], urgency: str = "routine") -> dict[str, Any]:
    detail = dict(detail or {})
    return {
        "kind": kind, "campaign": campaign, "summary": summary, "detail": detail,
        "urgency": normalise_urgency(urgency, detail), "author": "agent", "resolved": None,
    }


def propose_matches(results: Iterable[MatchResult], store: JsonlStore,
                    campaign: Optional[str] = None) -> tuple[list[dict[str, Any]], Optional[dict[str, Any]]]:
    """Insert one ``crosswalk_proposals`` row per non-accepted match and one
    operator task summarising them. Agent-facing: proposal only."""
    pending = [m.to_proposal() for m in results if not m.auto_accept]
    if not pending:
        return [], None
    inserted = store.insert_crosswalk_proposals(pending)
    task = store.insert_task(build_operator_task(
        "crosswalk_proposals", campaign,
        f"{len(pending)} PCS riders need a human crosswalk decision",
        {"proposals": [{"pcs_slug": p["pcs_slug"], "pcs_name": p["pcs_name"],
                        "fc_rider_id": p["fc_rider_id"], "fc_name": p["fc_name"],
                        "confidence": p["confidence"], "evidence": p["evidence"]} for p in pending],
         "how_to_confirm": "uv run python -m cycling_project.nightly.crosswalk confirm "
                           "--pcs-slug <slug> --fc-rider-id <id> --by <name>"},
        urgency="blocks_settlement" if len(pending) > 5 else "routine",
    ))
    return inserted, task


def coverage_report(field_rows: Iterable[dict[str, Any]], crosswalk_rows: Iterable[dict[str, Any]],
                    pcs_rows: Optional[Iterable[PcsRow]] = None) -> dict[str, Any]:
    field_rows = list(field_rows)
    by_fc: dict[str, dict[str, Any]] = {}
    for r in crosswalk_rows:
        if float(r.get("confidence") or 0) >= AUTO_ACCEPT or r.get("confirmed_by"):
            by_fc[str(r["fc_rider_id"])] = r
    matched = [r for r in field_rows if r["fc_rider_id"] in by_fc]
    unmatched = [r for r in field_rows if r["fc_rider_id"] not in by_fc]
    report: dict[str, Any] = {
        "field": len(field_rows), "matched": len(matched), "unmatched": len(unmatched),
        "coverage": round(len(matched) / len(field_rows), 4) if field_rows else None,
        "unmatched_riders": [{"fc_rider_id": r["fc_rider_id"], "fc_name": r["fc_name"], "team": r["team"],
                              "bib": r["bib"]} for r in unmatched],
    }
    if pcs_rows is not None:
        pcs_list = list(pcs_rows)
        slugs = {str(r["pcs_slug"]) for r in by_fc.values()}
        missing = [p for p in pcs_list if p.slug not in slugs]
        report["pcs_rows"] = len(pcs_list)
        report["pcs_unmatched"] = [{"pcs_slug": p.slug, "pcs_name": p.name, "team": p.team, "bib": p.bib}
                                   for p in missing]
    return report


# ---------------------------------------------------------------------------
# Human confirmation (operator role only)
# ---------------------------------------------------------------------------

def _require_operator_context() -> None:
    """Refuse to run the confirmation path from an agent context.

    The cloud container carries ``SUPABASE_NIGHTLY_KEY`` and never the
    operator secret; ``NIGHTLY_ROLE=agent`` is the explicit marker.
    """
    if os.environ.get("NIGHTLY_ROLE", "").lower() == "agent":
        raise PermissionError("confirm is a human action; refusing under NIGHTLY_ROLE=agent")
    if os.environ.get("SUPABASE_NIGHTLY_KEY") and not os.environ.get("SUPABASE_SECRET_KEY") \
            and os.environ.get("CROSSWALK_STORE", "local") == "supabase":
        raise PermissionError("confirm needs the operator key (SUPABASE_SECRET_KEY), not the agent key")


def confirm(pcs_slug: str, fc_rider_id: str, by: str, *, index: RiderIndex, store: JsonlStore,
            csv_path: Path = CROSSWALK_CSV, pcs_name: Optional[str] = None) -> dict[str, Any]:
    """Record a human-confirmed mapping in the CSV and (as operator) in ``crosswalk``."""
    _require_operator_context()
    if not by or not by.strip():
        raise ValueError("--by <name> is required for a confirmation")
    rider = index.by_fc_id.get(str(fc_rider_id))
    if rider is None:
        raise ValueError(f"fc_rider_id {fc_rider_id} is not in the riders table")
    row = {
        "pcs_slug": pcs_slug, "fc_rider_id": rider.fc_rider_id, "internal_rider_id": rider.internal_id,
        "pcs_name": pcs_name or "", "fc_name": rider.name, "birth_year": rider.birth_year or "",
        "confidence": "1.00", "source": "human", "confirmed_by": by.strip(), "created_at": utcnow_iso(),
    }
    existing = read_crosswalk_csv(csv_path)
    merged, _ = merge_crosswalk(existing, [row], repo_wins=False)
    write_crosswalk_csv(merged, csv_path)
    store.upsert_crosswalk(row)
    return row


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=1, ensure_ascii=False, default=str))


def _campaign_slug(spec: Optional[str]) -> Optional[str]:
    if spec and Path(spec).is_dir():
        return Path(spec).name
    return None


def cmd_seed(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    rows, race_ids, ident = load_startlist(args.startlist, db_path, args.race_id, args.year)
    index = RiderIndex.from_sqlite(db_path, *(ident or (None, None)))
    results = match_startlist(rows, index, race_ids)
    accepted = [m.to_crosswalk_row() for m in results if m.auto_accept]
    pending = [m.to_proposal() for m in results if not m.auto_accept]
    csv_path = Path(args.csv)
    merged, conflicts = merge_crosswalk(read_crosswalk_csv(csv_path), accepted, repo_wins=True)
    if not args.dry_run:
        write_crosswalk_csv(merged, csv_path)
        PENDING_JSON.parent.mkdir(parents=True, exist_ok=True)
        Path(args.pending).write_text(json.dumps(
            {"startlist": args.startlist, "campaign": _campaign_slug(args.startlist),
             "generated_at": utcnow_iso(), "proposals": pending}, indent=1, ensure_ascii=False))
    report = {
        "startlist": args.startlist, "rows": len(results), "accepted": len(accepted),
        "pending": len(pending), "conflicts": conflicts,
        "coverage": round(len(accepted) / len(results), 4) if results else None,
        "sources": sorted({m.pcs.source for m in results}),
        "unmatched": [{"pcs_slug": p["pcs_slug"], "pcs_name": p["pcs_name"], "team": p["pcs_team"],
                       "best": p["fc_name"], "confidence": p["confidence"], "evidence": p["evidence"]}
                      for p in pending],
        "csv": str(csv_path), "dry_run": args.dry_run,
    }
    _print(report)
    if args.propose and pending and not args.dry_run:
        store = open_store(args.store, Path(args.runs_dir), role="agent")
        propose_matches(results, store, _campaign_slug(args.startlist))
    return EXIT_WAITING if pending else EXIT_OK


def cmd_propose(args: argparse.Namespace) -> int:
    store = open_store(args.store, Path(args.runs_dir), role="agent")
    campaign = None
    if args.startlist:
        db_path = Path(args.db)
        rows, race_ids, ident = load_startlist(args.startlist, db_path, args.race_id, args.year)
        index = RiderIndex.from_sqlite(db_path, *(ident or (None, None)))
        results = match_startlist(rows, index, race_ids)
        campaign = _campaign_slug(args.startlist)
        inserted, task = propose_matches(results, store, campaign)
    else:
        pending_file = Path(args.pending)
        if not pending_file.exists():
            _print({"error": f"{pending_file} missing; run seed first or pass --startlist"})
            return EXIT_FAILED
        pend = json.loads(pending_file.read_text())
        campaign = pend.get("campaign")
        proposals = pend.get("proposals", [])
        if not proposals:
            _print({"proposals": 0, "task": None})
            return EXIT_OK
        inserted = store.insert_crosswalk_proposals(proposals)
        task = store.insert_task(build_operator_task(
            "crosswalk_proposals", campaign, f"{len(proposals)} PCS riders need a human crosswalk decision",
            {"proposals": proposals}, urgency="blocks_settlement" if len(proposals) > 5 else "routine"))
    _print({"proposals": len(inserted), "task": task, "campaign": campaign, "store": args.store})
    return EXIT_WAITING if inserted else EXIT_OK


def cmd_confirm(args: argparse.Namespace) -> int:
    os.environ.setdefault("CROSSWALK_STORE", args.store)
    index = RiderIndex.from_sqlite(Path(args.db))
    store = open_store(args.store, Path(args.runs_dir), role="operator")
    if args.from_pending:
        pending_file = Path(args.pending)
        if not pending_file.exists():
            _print({"error": f"{pending_file} missing; run seed first"})
            return EXIT_FAILED
        pend = json.loads(pending_file.read_text())
        chosen = [p for p in pend.get("proposals", [])
                  if p.get("fc_rider_id") and float(p.get("confidence") or 0) >= args.min_confidence]
        confirmed = [confirm(p["pcs_slug"], str(p["fc_rider_id"]), args.by, index=index, store=store,
                             csv_path=Path(args.csv), pcs_name=p.get("pcs_name")) for p in chosen]
        remaining = [p for p in pend.get("proposals", []) if p not in chosen]
        pend["proposals"] = remaining
        pending_file.write_text(json.dumps(pend, indent=1, ensure_ascii=False))
        _print({"confirmed": confirmed, "remaining": len(remaining), "by": args.by})
        return EXIT_OK
    if not (args.pcs_slug and args.fc_rider_id):
        _print({"error": "confirm needs --pcs-slug and --fc-rider-id (or --from-pending)"})
        return EXIT_FAILED
    row = confirm(args.pcs_slug, args.fc_rider_id, args.by, index=index, store=store,
                  csv_path=Path(args.csv), pcs_name=args.pcs_name)
    # Drop the slug from the pending file if it was there.
    pending_file = Path(args.pending)
    if pending_file.exists():
        pend = json.loads(pending_file.read_text())
        pend["proposals"] = [p for p in pend.get("proposals", []) if p.get("pcs_slug") != args.pcs_slug]
        pending_file.write_text(json.dumps(pend, indent=1, ensure_ascii=False))
    _print(row)
    return EXIT_OK


def cmd_export(args: argparse.Namespace) -> int:
    rows = read_crosswalk_csv(Path(args.csv))
    out = write_crosswalk_csv(rows, Path(args.to))
    _print({"rows": len(rows), "to": str(out)})
    return EXIT_OK


def cmd_import(args: argparse.Namespace) -> int:
    incoming = read_crosswalk_csv(Path(getattr(args, "from")))
    repo = read_crosswalk_csv(Path(args.csv))
    merged, conflicts = merge_crosswalk(repo, incoming, repo_wins=True)
    if not args.dry_run:
        write_crosswalk_csv(merged, Path(args.csv))
    _print({"incoming": len(incoming), "repo_before": len(repo), "repo_after": len(merged),
            "conflicts_repo_kept": conflicts, "dry_run": args.dry_run})
    return EXIT_OK


def cmd_coverage(args: argparse.Namespace) -> int:
    campaign = Path(args.campaign)
    field_rows, rid, yr = load_campaign_field(campaign, Path(args.db), args.race_id, args.year)
    html = campaign_pcs_startlist(campaign)
    pcs_rows = load_pcs_startlist_html(html) if html else None
    report = coverage_report(field_rows, read_crosswalk_csv(Path(args.csv)), pcs_rows)
    report.update({"campaign": campaign.name, "fc_race_id": rid, "year": yr,
                   "pcs_startlist": str(html) if html else None})
    _print(report)
    return EXIT_OK if report["unmatched"] == 0 else EXIT_WAITING


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="crosswalk", description=__doc__.split("\n\n")[0])
    p.add_argument("--db", default=str(DEFAULT_DB_PATH))
    p.add_argument("--csv", default=str(CROSSWALK_CSV), help="repo CSV mirror")
    p.add_argument("--pending", default=str(PENDING_JSON))
    p.add_argument("--runs-dir", default=str(RUNS_DIR))
    p.add_argument("--store", choices=["local", "none", "supabase"], default="local")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("seed", help="match a startlist; write auto-accepted rows to the CSV")
    s.add_argument("--startlist", required=True, help="PCS HTML page, CSV, or campaign dir")
    s.add_argument("--race-id"); s.add_argument("--year", type=int)
    s.add_argument("--propose", action="store_true", help="also insert proposals for the rest")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(func=cmd_seed)

    s = sub.add_parser("propose", help="insert crosswalk_proposals + an operator task")
    s.add_argument("--startlist"); s.add_argument("--race-id"); s.add_argument("--year", type=int)
    s.set_defaults(func=cmd_propose)

    s = sub.add_parser("confirm", help="HUMAN: confirm a mapping (operator role)")
    s.add_argument("--pcs-slug"); s.add_argument("--fc-rider-id")
    s.add_argument("--by", required=True); s.add_argument("--pcs-name")
    s.add_argument("--from-pending", action="store_true",
                   help="batch: confirm every pending proposal at/above --min-confidence "
                        "(review the printed list first — this is the human decision)")
    s.add_argument("--min-confidence", type=float, default=0.93)
    s.set_defaults(func=cmd_confirm)

    s = sub.add_parser("export", help="write the repo CSV to another path (bundle)")
    s.add_argument("--to", required=True)
    s.set_defaults(func=cmd_export)

    s = sub.add_parser("import", help="merge a pulled CSV into the repo CSV (repo wins)")
    s.add_argument("--from", required=True, dest="from")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(func=cmd_import)

    s = sub.add_parser("coverage", help="crosswalk coverage of a campaign's field")
    s.add_argument("--campaign", required=True); s.add_argument("--race-id"); s.add_argument("--year", type=int)
    s.set_defaults(func=cmd_coverage)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
