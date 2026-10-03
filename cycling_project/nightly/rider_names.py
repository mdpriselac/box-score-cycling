"""Given-name-first display names for editorial prose (chip EE, 2026-10-03).

FirstCycling stores one ``name`` field, surname first ("Syritsa Gleb", "van der Poel
Mathieu"), and that string is the join key everywhere.  Prose wants "Gleb Syritsa".  The
model cannot reorder it safely — it cannot know where "Lopez Sevilla Diego Pablo" or
"Ibanez Gonzalez Carlos Andres" splits — so the split is decided here, deterministically:

(a) **UCI form** — the UCI writes the surname in capitals ("SMIT Willem Jakobus",
    "LOPEZ SEVILLA Diego Pablo") in the result capture the campaign already archived
    (``results/<unit>/results.json`` → ``uci.raw_results``), in the human-confirmed
    ``uci_aliases.csv`` and in the crosswalk's capitals ``pcs_name``.  When every token of
    the FirstCycling name falls on one side of that split, the display name is the
    FirstCycling tokens reordered given-first, each spelled as the UCI spells it (accents
    as the UCI gives them, letter case from FirstCycling so "McGill" stays "McGill").  The
    token SET stays FirstCycling's: the UCI often carries the full legal name ("GATE Aaron
    Murray", "BALDERSTONE ROUMENS Abel"), and prose names "Aaron Gate", not "Aaron Murray
    Gate".  With no FirstCycling name, the UCI name itself is reordered.
(b) **Heuristic** — no UCI form, or one that does not split the FirstCycling tokens
    cleanly (nicknames: "Pidcock Tom" / "PIDCOCK Thomas").  Leading surname particles
    (van, de, der, den, von, da, di, le, la, dos, du, …) join the surname, the next token
    is the surname, the rest is the given name.  Measured on 1,488 campaign riders with a
    UCI form (2026-10-03): 98.5 % agree with the UCI split; "last token is the given name"
    agreed 96.2 % (it breaks every "Sierra Juan David").  Its misses are compound
    surnames ("Pezzo Rosola Kevin"), which a UCI capture fixes from the first settled
    stage on.  Recorded as ``display_name_source: "heuristic"`` so it can be audited.

``display_name(fc_name, uci_name=None)`` is the single helper; ``NameBook`` gathers every
UCI form a campaign has, and ``annotate_bundle`` adds ``display_name`` beside every rider
``name`` in an editorial facts bundle without touching ``name``.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from cycling_project.nightly.crosswalk import CROSSWALK_DIR, name_tokens

#: Surname particles: a leading run of these always belongs to the surname.
PARTICLES = frozenset({
    "van", "de", "der", "den", "von", "da", "di", "le", "la", "dos", "du",
    "del", "della", "dalla", "dal", "des", "das", "do", "ten", "ter", "vanden", "vander", "zu",
})

#: Where ``uci_aliases.csv`` and ``rider_crosswalk.csv`` live (module-level so tests can point it away).
DEFAULT_CROSSWALK_DIR = CROSSWALK_DIR

SOURCE_UCI = "uci"                  # the campaign's own UCI result capture
SOURCE_ALIAS = "uci_alias"          # performance_eval/crosswalk/uci_aliases.csv (human-confirmed)
SOURCE_CROSSWALK = "crosswalk"      # rider_crosswalk.csv pcs_name (same capitals convention)
SOURCE_HEURISTIC = "heuristic"
SOURCE_MARKET = "market"            # a book name no rider in the bundle matches: kept verbatim

#: Keys that mark a dict in a facts bundle as a rider row (a reference set entry is just
#: ``{"name", "date"}``; the campaign block has ``slug``).
RIDER_ROW_KEYS = frozenset({"fc_rider_id", "rider_id", "place", "rank", "odds", "pct", "team",
                            "gap", "win_pct", "devig_pct", "rank_with_key", "rank_production"})


# ---------------------------------------------------------------------------
# the helper
# ---------------------------------------------------------------------------

def split_uci_name(uci_name: str) -> Optional[Tuple[str, str]]:
    """``"LOPEZ SEVILLA Diego Pablo"`` → ``("LOPEZ SEVILLA", "Diego Pablo")``.

    The surname is the leading run of tokens written entirely in capitals.  ``None`` when
    there is no such run or nothing after it.
    """
    tokens = (uci_name or "").split()
    k = 0
    while k < len(tokens) and _is_caps(tokens[k]):
        k += 1
    if k == 0 or k == len(tokens):
        return None
    return " ".join(tokens[:k]), " ".join(tokens[k:])


def _is_caps(token: str) -> bool:
    letters = [c for c in token if c.isalpha()]
    return bool(letters) and all(not c.islower() for c in letters)


def _uci_case(token: str, *, particle_lower: bool = True) -> str:
    """Capitals surname token → name case ("ARRIOLA-BENGOA" → "Arriola-Bengoa", "VAN" → "van")."""
    if particle_lower and token.casefold() in PARTICLES:
        return token.lower()
    return re.sub(r"[^\W\d_]+", lambda m: m.group(0)[:1].upper() + m.group(0)[1:].lower(), token)


def _spell_like(fc_token: str, uci_token: str) -> str:
    """The UCI spelling of a token (its accents) in FirstCycling's letter case."""
    if len(fc_token) == len(uci_token):
        return "".join(u.upper() if f.isupper() else u.lower() for f, u in zip(fc_token, uci_token))
    return _uci_case(uci_token, particle_lower=False) if fc_token[:1].isupper() else uci_token.lower()


def _uci_split_of(fc_name: str, last: str, first: str) -> Optional[str]:
    """Reorder the FirstCycling tokens by the UCI split, or ``None`` when they do not split cleanly."""
    surname_keys = set(name_tokens(last))
    given_keys = set(name_tokens(first))
    uci_spelling = {}
    for t in (last + " " + first).split():
        keys = name_tokens(t)
        if len(keys) == 1:
            uci_spelling.setdefault(keys[0], t)
    tokens = fc_name.split()
    labels = []
    for t in tokens:
        keys = name_tokens(t)
        if not keys:
            return None
        s, g = all(k in surname_keys for k in keys), all(k in given_keys for k in keys)
        labels.append("B" if s and g else "S" if s else "G" if g else "?")
    for k in range(1, len(tokens)):
        head, tail = labels[:k], labels[k:]
        if "S" in head and "G" in tail and set(head) <= {"S", "B"} and set(tail) <= {"G", "B"}:
            def spelled(t: str) -> str:
                keys = name_tokens(t)
                u = uci_spelling.get(keys[0]) if len(keys) == 1 else None
                return _spell_like(t, u) if u else t
            return " ".join(spelled(t) for t in tokens[k:] + tokens[:k])
    return None


def heuristic_display(fc_name: str) -> str:
    """Leading particles + one token = surname; the rest = given name, moved to the front."""
    tokens = (fc_name or "").split()
    if len(tokens) < 2:
        return " ".join(tokens)
    i = 0
    while i < len(tokens) - 2 and tokens[i].casefold() in PARTICLES:
        i += 1
    surname, given = tokens[:i + 1], tokens[i + 1:]
    return " ".join(given + surname)


def display_name_with_source(fc_name: Optional[str], *, uci_name: Optional[str] = None,
                             uci_source: str = SOURCE_UCI) -> Tuple[str, str]:
    """``(display_name, display_name_source)``; see the module docstring for the rules."""
    fc_name = " ".join((fc_name or "").split())
    split = split_uci_name(uci_name) if uci_name else None
    if split:
        last, first = split
        if not fc_name:
            return " ".join([first] + [_uci_case(t) for t in last.split()]), uci_source
        reordered = _uci_split_of(fc_name, last, first)
        if reordered:
            return reordered, uci_source
    return heuristic_display(fc_name), SOURCE_HEURISTIC


def display_name(fc_name: Optional[str], *, uci_name: Optional[str] = None) -> str:
    """Given-name-first form of a FirstCycling ``name`` (UCI form first, heuristic second)."""
    return display_name_with_source(fc_name, uci_name=uci_name)[0]


# ---------------------------------------------------------------------------
# every UCI form a campaign has
# ---------------------------------------------------------------------------

def _set_key(name: str) -> str:
    return " ".join(sorted(set(name_tokens(name or ""))))


class NameBook:
    """FirstCycling name → (UCI name, source), keyed order-insensitively.

    A key that two sources disagree on keeps the higher-priority source (campaign capture,
    then confirmed aliases, then the crosswalk); a key two DIFFERENT riders share inside one
    source is dropped, so a homonym falls back to the heuristic instead of borrowing the
    other rider's split.
    """

    def __init__(self) -> None:
        self.forms: Dict[str, Tuple[str, str, str]] = {}      # key -> (fc_name, uci_name, source)
        self._ambiguous: set = set()

    def add(self, fc_name: str, uci_name: str, source: str) -> None:
        key = _set_key(fc_name)
        if not key or not uci_name or key in self._ambiguous:
            return
        have = self.forms.get(key)
        if have is None:
            self.forms[key] = (fc_name, uci_name, source)
        elif have[2] == source and _set_key(have[1]) != _set_key(uci_name):
            del self.forms[key]
            self._ambiguous.add(key)

    def __len__(self) -> int:
        return len(self.forms)

    def lookup(self, name: str) -> Optional[Tuple[str, str, str]]:
        return self.forms.get(_set_key(name))

    def display(self, fc_name: str) -> Tuple[str, str]:
        hit = self.lookup(fc_name)
        if hit:   # the book's own FirstCycling form: a book name ("Gleb Syritsa") is not surname first
            return display_name_with_source(hit[0], uci_name=hit[1], uci_source=hit[2])
        return display_name_with_source(fc_name)

    # -- sources ------------------------------------------------------------------------------------
    def add_campaign_captures(self, campaign_dir: Path, *, exclude_units: Iterable[str] = ()) -> "NameBook":
        """Join each archived UCI capture to its FirstCycling rows: classified rows on place,
        accepted only when a surname token agrees (so a mis-joined row never lends its split)."""
        skip = set(exclude_units)
        for path in sorted(Path(campaign_dir).glob("results/*/results.json")):
            if path.parent.name in skip:
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            raw = ((data.get("uci") or {}).get("raw_results")) or []
            by_rank: Dict[str, List[Dict[str, Any]]] = {}
            for r in raw:
                by_rank.setdefault(str(r.get("rank")), []).append(r)
            for row in data.get("results") or []:
                rid, name = str(row.get("rider_id") or ""), row.get("name") or ""
                if not name or rid.startswith("uci:"):
                    continue
                candidates = by_rank.get(str(row.get("place")), [])
                fc_keys = set(name_tokens(name))
                hits = [r for r in candidates if fc_keys & set(name_tokens(r.get("lastname") or ""))]
                if len(hits) == 1:
                    h = hits[0]
                    self.add(name, f"{(h.get('lastname') or '').strip()} {(h.get('firstname') or '').strip()}", SOURCE_UCI)
        return self

    def add_alias_csv(self, path: Path, *, uci_col: str, source: str) -> "NameBook":
        if not Path(path).is_file():
            return self
        with Path(path).open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                if row.get("fc_name") and row.get(uci_col):
                    self.add(row["fc_name"], row[uci_col], source)
        return self


def campaign_name_book(campaign_dir: Path, *, exclude_units: Iterable[str] = (),
                       crosswalk_dir: Optional[Path] = None) -> NameBook:
    """The campaign's captures, then the confirmed UCI aliases, then the crosswalk."""
    xw = Path(crosswalk_dir) if crosswalk_dir else DEFAULT_CROSSWALK_DIR
    book = NameBook().add_campaign_captures(campaign_dir, exclude_units=exclude_units)
    book.add_alias_csv(xw / "uci_aliases.csv", uci_col="uci_name", source=SOURCE_ALIAS)
    book.add_alias_csv(xw / "rider_crosswalk.csv", uci_col="pcs_name", source=SOURCE_CROSSWALK)
    return book


# ---------------------------------------------------------------------------
# facts bundle annotation
# ---------------------------------------------------------------------------

def annotate_bundle(bundle: Dict[str, Any], book: Optional[NameBook] = None) -> Dict[str, Any]:
    """Add ``display_name`` + ``display_name_source`` beside every rider ``name`` (in place).

    ``name`` is never changed — it is the join key.  Book names (``market``) are already
    given-name first: they take the matching rider's display name when the book knows the
    rider, else they are kept verbatim (source ``market``).  ``abandons.names`` gains a
    parallel ``display_names`` list; scorecard ledger rows gain ``winner_display_name``.
    """
    book = book or NameBook()

    def show(name: str, *, market: bool) -> Tuple[str, str]:
        if market and not book.lookup(name):
            return name, SOURCE_MARKET
        return book.display(name)

    def walk(node: Any, market: bool) -> None:
        if isinstance(node, dict):
            name = node.get("name")
            if isinstance(name, str) and name.strip() and RIDER_ROW_KEYS & set(node):
                node["display_name"], node["display_name_source"] = show(name, market=market)
            for k, v in node.items():
                if k in ("manifest", "display_name", "display_name_source"):
                    continue
                walk(v, market or k == "market")
        elif isinstance(node, list):
            for v in node:
                walk(v, market)

    walk(bundle, False)
    ab = bundle.get("abandons")
    if isinstance(ab, dict) and isinstance(ab.get("names"), list):
        ab["display_names"] = [show(n, market=False)[0] for n in ab["names"] if isinstance(n, str)]
    for row in ((bundle.get("scorecard") or {}).get("ledger") or []) + [(bundle.get("scorecard") or {}).get("stage") or {}]:
        if isinstance(row, dict) and isinstance(row.get("winner"), str) and row["winner"].strip():
            row["winner_display_name"] = show(row["winner"], market=False)[0]
    return bundle


def name_pairs(facts: Any) -> Dict[str, str]:
    """``{surname-first name: display_name}`` for every rider row whose two forms differ
    (book rows excluded: their ``name`` is already given-name first)."""
    out: Dict[str, str] = {}

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            n, d = node.get("name"), node.get("display_name")
            if (isinstance(n, str) and isinstance(d, str) and n.strip() and n != d
                    and node.get("display_name_source") != SOURCE_MARKET):
                out.setdefault(" ".join(n.split()), d)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(facts)
    return out
