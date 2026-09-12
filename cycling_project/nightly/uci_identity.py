"""UCI → FirstCycling rider identity bridge (UCI_MANAGED_AGENT_BUILD_BRIEF.md §3).

The UCI results API carries no stable rider id, team id, bib or full date of
birth — only ``firstname``, ``lastname`` (often with a second surname), the
team name in capitals, ``age`` and ``nationality``. This module resolves each
UCI row to a FirstCycling rider id **deterministically**, against the
campaign's own roster (the archived earlier stages), the confirmed crosswalk
and, for a race's first stage, the serving database. It never lets a name
stand in for an id: every accepted resolution carries the evidence that
justified it, unresolved rows become ``crosswalk_proposals`` (``source=uci``)
plus an operator task, and only a human can add a durable alias.

Acceptance policy (auto-accept threshold ``AUTO_ACCEPT`` = 0.97):

* a human-confirmed row in ``performance_eval/crosswalk/uci_aliases.csv`` —
  keyed by ``uci_key`` (``"<lastname tokens>|<firstname tokens>"``, an ALIAS
  key derived from the name, explicitly not a UCI id) — always wins;
* exact accent-insensitive normalised full name, unique in scope, with no
  age conflict → 0.97 (0.99 when age or team corroborates it). Team history
  is supporting evidence, not a veto: it is frequently stale after transfers
  and development-team moves;
* the same with the name *extended* on one side (UCI adds a second
  surname: ``BUITRAGO SANCHEZ Santiago`` ↔ ``Buitrago Santiago``; or the
  FirstCycling name carries an extra token), given name identical, unique in
  scope, and either team compatible or age consistent → 0.97 (evidence
  recorded);
* nickname-resolved names (``Chris`` ↔ ``Christopher``), homonyms, fuzzy
  similarity, age/nationality-only support, and extended names without age or
  team corroboration → a proposal (< 0.97), never an acceptance.

Scope: the campaign roster (earlier ``results/stage_NN`` files) when it
exists — after stage 1 it is the whole field — else the confirmed crosswalk
rows, else the riders table with the race's cached startlist for team
evidence (``crosswalk.RiderIndex``).
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import difflib
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from cycling_project.nightly.crosswalk import (
    AUTO_ACCEPT,
    CROSSWALK_CSV,
    CROSSWALK_DIR,
    NICKNAMES,
    RiderIndex,
    name_key,
    name_tokens,
    read_crosswalk_csv,
    teams_match,
)
from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

ALIASES_CSV = CROSSWALK_DIR / "uci_aliases.csv"
ALIAS_FIELDS = ["uci_key", "uci_name", "fc_rider_id", "fc_name", "birth_year", "confidence", "source",
                "confirmed_by", "created_at"]
PROVIDER = "uci"
ACCEPT_EXTENDED_SURNAMES = True     # the 0.97 rule above; set False to route every non-exact name to a proposal


# ---------------------------------------------------------------------------
# keys
# ---------------------------------------------------------------------------

def set_key(name: str) -> str:
    """Order-insensitive, duplicate-free normalised name (``SAMITIER SAMITIER Sergio`` == ``Samitier Sergio``)."""
    return " ".join(sorted(set(name_tokens(name))))


def uci_key(lastname: str, firstname: str) -> str:
    """Alias key for a UCI name: sorted surname tokens ``|`` sorted given tokens (accent-free, casefold)."""
    return " ".join(sorted(name_tokens(lastname))) + "|" + " ".join(sorted(name_tokens(firstname)))


def uci_display_name(lastname: str, firstname: str) -> str:
    return " ".join(p for p in ((lastname or "").strip(), (firstname or "").strip()) if p)


def _utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# candidates
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Candidate:
    fc_rider_id: str
    name: str                                   # FirstCycling "Surname Firstname"
    birth_year: Optional[int]
    teams: frozenset                            # raw team strings seen for the rider
    source: str                                 # 'roster' | 'crosswalk' | 'db'
    internal_id: Optional[int] = None

    @property
    def key(self) -> str:
        return set_key(self.name)


class CandidateIndex:
    def __init__(self, candidates: Iterable[Candidate]):
        self.items: List[Candidate] = []
        self.by_key: Dict[str, List[Candidate]] = defaultdict(list)
        self.by_token: Dict[str, Set[int]] = defaultdict(set)
        self.by_fc: Dict[str, Candidate] = {}
        for c in candidates:
            if c.fc_rider_id in self.by_fc:
                continue
            self.by_fc[c.fc_rider_id] = c
            i = len(self.items)
            self.items.append(c)
            self.by_key[c.key].append(c)
            for t in name_tokens(c.name):
                self.by_token[t].add(i)

    def __len__(self) -> int:
        return len(self.items)

    def sharing_tokens(self, tokens: Sequence[str]) -> List[Candidate]:
        idx: Set[int] = set()
        for t in tokens:
            idx |= self.by_token.get(t, set())
        return [self.items[i] for i in sorted(idx)]


def roster_candidates(roster: Dict[str, Dict[str, str]]) -> List[Candidate]:
    out = []
    for fc, pres in roster.items():
        by = pres.get("dob") or ""
        out.append(Candidate(str(fc), pres.get("name", ""), int(by) if str(by).isdigit() else None,
                             frozenset(t for t in (pres.get("team"),) if t), "roster"))
    return out


def crosswalk_candidates(csv_path: Optional[Path]) -> List[Candidate]:
    out = []
    for r in read_crosswalk_csv(Path(csv_path) if csv_path else CROSSWALK_CSV):
        fc = str(r.get("fc_rider_id") or "").strip()
        name = str(r.get("fc_name") or "").strip()
        if not fc or not name:
            continue
        try:
            conf = float(r.get("confidence") or 0)
        except ValueError:
            conf = 0.0
        if not (str(r.get("confirmed_by") or "").strip() or conf >= AUTO_ACCEPT):
            continue
        by = str(r.get("birth_year") or "")
        out.append(Candidate(fc, name, int(by) if by.isdigit() else None, frozenset(), "crosswalk",
                             int(r["internal_rider_id"]) if str(r.get("internal_rider_id") or "").isdigit() else None))
    return out


def db_candidates(db_path: Optional[Path], fc_race_id: Optional[str], year: Optional[int]) -> List[Candidate]:
    if not db_path or not Path(db_path).exists():
        return []
    try:
        index = RiderIndex.from_sqlite(db_path, fc_race_id, year)
    except Exception as exc:  # noqa: BLE001 — the DB is the last-resort scope
        logger.warning("uci identity: riders table unavailable: %s", exc)
        return []
    return [Candidate(r.fc_rider_id, r.name, r.birth_year, r.teams, "db", r.internal_id) for r in index.riders]


# ---------------------------------------------------------------------------
# aliases (human-confirmed durable mappings)
# ---------------------------------------------------------------------------

def read_aliases(path: Optional[Path] = None) -> Dict[str, Dict[str, str]]:
    p = Path(path) if path else ALIASES_CSV
    if not p.exists():
        return {}
    out: Dict[str, Dict[str, str]] = {}
    with open(p, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            k = str(r.get("uci_key") or "").strip()
            if k and str(r.get("fc_rider_id") or "").strip():
                out[k] = r
    return out


def append_alias(row: Dict[str, Any], path: Optional[Path] = None) -> Path:
    p = Path(path) if path else ALIASES_CSV
    p.parent.mkdir(parents=True, exist_ok=True)
    new = not p.exists()
    with open(p, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=ALIAS_FIELDS, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow({k: ("" if row.get(k) is None else row.get(k)) for k in ALIAS_FIELDS})
    return p


# ---------------------------------------------------------------------------
# resolution
# ---------------------------------------------------------------------------

@dataclass
class UciRider:
    """The identity-relevant fields of one UCI result row."""
    firstname: str
    lastname: str
    team: Optional[str] = None
    age: Optional[int] = None
    nationality: Optional[str] = None
    rank_text: str = ""

    @property
    def key(self) -> str:
        return uci_key(self.lastname, self.firstname)

    @property
    def display(self) -> str:
        return uci_display_name(self.lastname, self.firstname)

    @property
    def full_name(self) -> str:
        return f"{self.firstname} {self.lastname}"


@dataclass
class Resolution:
    rider: UciRider
    candidate: Optional[Candidate]
    confidence: float
    reasons: List[str] = field(default_factory=list)
    alternates: List[Candidate] = field(default_factory=list)
    via_alias: bool = False

    @property
    def accepted(self) -> bool:
        return self.candidate is not None and self.confidence >= AUTO_ACCEPT

    @property
    def fc_rider_id(self) -> Optional[str]:
        return self.candidate.fc_rider_id if self.candidate else None

    def as_dict(self) -> Dict[str, Any]:
        return {"uci_name": self.rider.display, "uci_key": self.rider.key, "team": self.rider.team,
                "rank": self.rider.rank_text, "fc_rider_id": self.fc_rider_id,
                "fc_name": self.candidate.name if self.candidate else None,
                "confidence": round(self.confidence, 2), "accepted": self.accepted, "via_alias": self.via_alias,
                "evidence": "; ".join(self.reasons),
                "alternates": [{"fc_rider_id": a.fc_rider_id, "fc_name": a.name, "birth_year": a.birth_year} for a in self.alternates[:5]]}

    def to_proposal(self, campaign_slug: Optional[str] = None) -> Dict[str, Any]:
        """A ``crosswalk_proposals`` row. ``pcs_slug`` is NOT NULL in the schema, so it carries the
        labelled alias key ``uci:<uci_key>`` until migration 0004 adds provider/external_key."""
        return {
            "pcs_slug": f"uci:{self.rider.key}", "pcs_name": self.rider.display, "pcs_team": self.rider.team,
            "pcs_bib": None, "fc_rider_id": self.fc_rider_id, "fc_name": self.candidate.name if self.candidate else None,
            "internal_rider_id": self.candidate.internal_id if self.candidate else None,
            "confidence": round(self.confidence, 2),
            "evidence": "source=uci; " + "; ".join(self.reasons) + (f"; age {self.rider.age}" if self.rider.age else "")
                        + (f"; nat {self.rider.nationality}" if self.rider.nationality else ""),
            "alternates": [{"fc_rider_id": a.fc_rider_id, "internal_rider_id": a.internal_id, "fc_name": a.name,
                            "birth_year": a.birth_year} for a in self.alternates[:5]],
            "author": "agent", "status": "proposed", "campaign_slug": campaign_slug,
        }


def _age_ok(rider: UciRider, cand: Candidate, season_year: Optional[int]) -> Optional[bool]:
    """Age at a dated event implies two birth years; None when either side is unknown."""
    if rider.age is None or cand.birth_year is None or season_year is None:
        return None
    return cand.birth_year in (season_year - rider.age, season_year - rider.age - 1)


def _team_ok(rider: UciRider, cand: Candidate) -> Optional[bool]:
    if not rider.team or not cand.teams:
        return None
    return any(teams_match(rider.team, t) for t in cand.teams)


def _extended_match(rider: UciRider, cand: Candidate) -> bool:
    """One side carries extra name tokens (UCI lists every given name and every surname:
    ``SOSA CUERVO Ivan Ramiro`` ↔ ``Sosa Ivan``; FirstCycling may keep a middle name:
    ``NORSGAARD Mathias`` ↔ ``Norsgaard Mathias Sunekær``). The shorter set must have at
    least two tokens, be contained in the longer, and share BOTH a surname token and a
    given-name token with the UCI name — never a given name alone (``NIELSEN Magnus`` ↔
    ``Cort Magnus`` is not a match)."""
    given = set(name_tokens(rider.firstname))
    surname = set(name_tokens(rider.lastname))
    uci = given | surname
    cand_tokens = set(name_tokens(cand.name))
    if not given or not surname or len(cand_tokens) < 2 or cand_tokens == uci:
        return False
    if cand_tokens < uci:                                    # UCI extends the FC name
        return bool(cand_tokens & surname) and bool(cand_tokens & given)
    if uci < cand_tokens and len(uci) >= 2:                  # FC carries an extra (middle) token
        return True
    return False


def resolve_rider(rider: UciRider, index: CandidateIndex, *, season_year: Optional[int],
                  aliases: Optional[Dict[str, Dict[str, str]]] = None) -> Resolution:
    alias = (aliases or {}).get(rider.key)
    if alias:
        cand = index.by_fc.get(str(alias["fc_rider_id"])) or Candidate(
            str(alias["fc_rider_id"]), alias.get("fc_name", ""),
            int(alias["birth_year"]) if str(alias.get("birth_year") or "").isdigit() else None, frozenset(), "alias")
        try:
            conf = float(alias.get("confidence") or 0.99)
        except ValueError:
            conf = 0.99
        if str(alias.get("confirmed_by") or "").strip():
            conf = max(conf, 0.99)
        return Resolution(rider, cand, conf, [f"uci alias table ({alias.get('source') or 'human'}"
                                            + (f", confirmed by {alias['confirmed_by']}" if alias.get("confirmed_by") else "") + ")"],
                          via_alias=True)

    key = set_key(rider.full_name)
    exact = list(index.by_key.get(key, []))
    if exact:
        if len(exact) == 1:
            c = exact[0]
            age, team = _age_ok(rider, c, season_year), _team_ok(rider, c)
            reasons = ["exact normalised name", "unique in scope"]
            if age is False:
                return Resolution(rider, c, 0.40, reasons + [f"age {rider.age} inconsistent with birth year {c.birth_year}"])
            if age is True:
                reasons.append(f"age {rider.age} consistent with birth year {c.birth_year}")
            if team is True:
                return Resolution(rider, c, 0.99, reasons + ["team matches"])
            if team is False:
                return Resolution(
                    rider, c, 0.99 if age is True else 0.97,
                    reasons + [f"team differs (non-vetoing; uci {rider.team!r} vs {sorted(c.teams)})"],
                )
            return Resolution(rider, c, 0.99 if age is True else 0.97, reasons + ["no team evidence"])
        by_team = [c for c in exact if _team_ok(rider, c) is True]
        return Resolution(rider, by_team[0] if len(by_team) == 1 else None, 0.50,
                          [f"exact name shared by {len(exact)} riders (homonym)", "team discriminates" if len(by_team) == 1 else "no discriminator"],
                          exact)

    if ACCEPT_EXTENDED_SURNAMES:
        ext = [c for c in index.sharing_tokens(name_tokens(rider.full_name)) if _extended_match(rider, c)]
        if len(ext) == 1:
            c = ext[0]
            age, team = _age_ok(rider, c, season_year), _team_ok(rider, c)
            reasons = [f"surname extended on one side (uci {rider.display!r} vs fc {c.name!r})", "given name identical", "unique in scope"]
            if age is False:
                return Resolution(rider, c, 0.40, reasons + [f"age {rider.age} inconsistent with birth year {c.birth_year}"])
            if age is True:
                reasons.append(f"age {rider.age} consistent with birth year {c.birth_year}")
            if team is True:
                return Resolution(rider, c, 0.97, reasons + ["team matches"])
            if age is True:
                suffix = "team differs" if team is False else "no team evidence"
                return Resolution(rider, c, 0.97, reasons + [f"{suffix} (age corroborates unique name)"])
            return Resolution(rider, c, 0.80, reasons + ["team differs or unknown"])
        if len(ext) > 1:
            return Resolution(rider, None, 0.50, ["surname-extended match is ambiguous"], ext)

    tokens = name_tokens(rider.full_name)
    nick_key = " ".join(sorted({NICKNAMES.get(t, t) for t in tokens}))
    if nick_key != key:
        nick = [c for c in index.sharing_tokens(tokens) if " ".join(sorted({NICKNAMES.get(t, t) for t in name_tokens(c.name)})) == nick_key]
        if len(nick) == 1:
            c = nick[0]
            conf, why = 0.85, ["exact name after nickname resolution (proposal only)"]
            if _age_ok(rider, c, season_year) is True:
                conf, why = 0.92, why + [f"age {rider.age} consistent with birth year {c.birth_year}"]
            if _team_ok(rider, c) is True:
                conf, why = min(0.95, conf + 0.03), why + ["team matches"]
            return Resolution(rider, c, conf, why)

    shared = index.sharing_tokens(tokens)
    scored = []
    for c in shared:
        ratio = difflib.SequenceMatcher(None, key, c.key).ratio()
        if ratio >= 0.80:
            conf, why = 0.55 + (ratio - 0.80), [f"fuzzy name similarity {ratio:.2f} (proposal only)"]
            if _age_ok(rider, c, season_year) is True:
                conf, why = conf + 0.10, why + [f"age {rider.age} consistent with birth year {c.birth_year}"]
            if _team_ok(rider, c) is True:
                conf, why = conf + 0.10, why + ["team matches"]
            scored.append((min(0.90, round(conf, 2)), why, c))
    if scored:
        scored.sort(key=lambda x: -x[0])
        conf, why, c = scored[0]
        return Resolution(rider, c, conf, why, [x[2] for x in scored[1:4]])
    same_team = [c for c in index.items if _team_ok(rider, c) is True and set(name_tokens(rider.firstname)) <= set(name_tokens(c.name))]
    return Resolution(rider, None, 0.0, ["no candidate (given name + team only is never enough)"], same_team[:5])


def build_index(*, roster: Dict[str, Dict[str, str]], crosswalk_csv: Optional[Path] = None,
                db_path: Optional[Path] = None, fc_race_id: Optional[str] = None, year: Optional[int] = None) -> CandidateIndex:
    """Scope order: roster; else confirmed crosswalk rows; else the riders table."""
    cands = roster_candidates(roster)
    scope = "roster"
    if not cands:
        cands = crosswalk_candidates(crosswalk_csv)
        scope = "crosswalk"
    if not cands:
        cands = db_candidates(db_path, fc_race_id, year)
        scope = "db"
    index = CandidateIndex(cands)
    index.scope = scope  # type: ignore[attr-defined]
    logger.info("uci identity scope: %s (%d candidates)", scope, len(index))
    return index


def resolve_all(riders: Iterable[UciRider], index: CandidateIndex, *, season_year: Optional[int],
                aliases: Optional[Dict[str, Dict[str, str]]] = None) -> List[Resolution]:
    out = [resolve_rider(r, index, season_year=season_year, aliases=aliases) for r in riders]
    # one FC id may be claimed by at most one accepted UCI row per classification
    claimed: Dict[str, List[int]] = defaultdict(list)
    for i, res in enumerate(out):
        if res.accepted:
            claimed[res.fc_rider_id].append(i)
    for fc, idxs in claimed.items():
        if len(idxs) > 1:
            for i in idxs:
                r = out[i]
                out[i] = Resolution(r.rider, r.candidate, 0.50, r.reasons + [f"FC id {fc} claimed by {len(idxs)} UCI rows"], r.alternates)
    return out


# ---------------------------------------------------------------------------
# CLI: confirm an alias (human), or dry-run the matcher on a capture
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("confirm", help="record a human-confirmed UCI name → FC id alias")
    p.add_argument("--lastname", required=True); p.add_argument("--firstname", required=True)
    p.add_argument("--fc-rider-id", required=True); p.add_argument("--fc-name", default="")
    p.add_argument("--birth-year", default=""); p.add_argument("--by", required=True, help="who confirmed (human)")
    p.add_argument("--aliases", type=Path, default=None)
    p = sub.add_parser("match", help="dry-run the matcher on a saved capture (no writes)")
    p.add_argument("--campaign", type=Path, required=True); p.add_argument("--unit", required=True)
    p.add_argument("--crosswalk", type=Path, default=None); p.add_argument("--db-path", type=Path, default=None)
    p.add_argument("--aliases", type=Path, default=None)
    args = ap.parse_args(argv)

    if args.cmd == "confirm":
        row = {"uci_key": uci_key(args.lastname, args.firstname), "uci_name": uci_display_name(args.lastname, args.firstname),
               "fc_rider_id": args.fc_rider_id, "fc_name": args.fc_name, "birth_year": args.birth_year,
               "confidence": "1.00", "source": "human", "confirmed_by": args.by, "created_at": _utcnow()}
        path = append_alias(row, args.aliases)
        print(json.dumps({"status": "ok", "aliases": str(path), "row": row}, indent=1))
        return 0
    from cycling_project.nightly import uci_ingest
    rep = uci_ingest.ingest(args.campaign, args.unit, crosswalk_csv=args.crosswalk, db_path=args.db_path,
                            aliases_csv=args.aliases, write=False)
    print(json.dumps({"verdict": rep.verdict, "failing": rep.failing, "identities": rep.identities}, indent=1, ensure_ascii=False))
    return 0 if rep.ok else 10


if __name__ == "__main__":
    sys.exit(main())
