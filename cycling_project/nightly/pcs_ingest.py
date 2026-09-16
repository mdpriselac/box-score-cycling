"""``nightly ingest`` — deterministic ProCyclingStats → FirstCycling-shaped results.

Spec: NIGHTLY_AGENT_WORKFLOW.md §2.8. The acquisition thread saves the PCS
pages it fetched *verbatim* under ``results/<unit>/pcs/`` plus a small
``pcs_raw.json`` index; nothing downstream trusts them until this module
has parsed and validated them. On success the FirstCycling-shaped archive
files are written (``results.csv`` / ``results.json`` / ``gc.csv`` /
``classifications.json``, byte-compatible with ``capture_results.py``);
on failure nothing is written and the failing checks are reported.

Verified PCS DOM map (the user's August test agent, reproduced on the
Vuelta 2026 stage-14 fixtures):

* result tabs ``ul.resultTabs li`` (``li.cur`` = active, ``data-id``) ↔
  ``div.resTab[data-id]`` → ``table.results``; every page carries every tab;
* rider name from ``td.ridername a[href^="rider/"]`` only (slug = href);
* team from ``a[href^="team/"]`` in the team column (PCS occasionally
  transposes rider/team links — cross-checked, flagged, corrected);
* time cell ``td.time``: ``<font>visible</font><span class="hide">resolved</span>``;
  ``,,`` visible = same time as the previous rider (the gap is carried);
* startlist ``div.ridersCont ul li`` with ``span.bib`` and a trailing
  ``(DNF #n)`` / ``(DNS #n)`` annotation once a rider has left the race;
* ``embed_top10.html`` (``…/more/embed-results``) lists the stage top 10
  first — the podium cross-check.

Identity: PCS rider slugs are translated to FirstCycling ids through the
crosswalk (``store`` table rows and/or ``performance_eval/crosswalk/
rider_crosswalk.csv``, auto-accept ≥ 0.97 or human-confirmed). The
FirstCycling *presentation* of a rider (name order, team, team id, birth
year) comes from the campaign's own archive (earlier ``results/stage_NN``
files — the roster) and, for a first stage, the cached startlist / riders
table in the serving database. Names are never used to identify a rider.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sqlite3
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from bs4 import BeautifulSoup

from cycling_project.nightly.crosswalk import AUTO_ACCEPT, CROSSWALK_CSV, read_crosswalk_csv
from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

PAGE_FILES = {
    "stage": "stage.html",
    "gc": "gc.html",
    "points": "points.html",
    "kom": "kom.html",
    "youth": "youth.html",
    "startlist": "startlist.html",
    "embed_top10": "embed_top10.html",
}
REQUIRED_PAGES = ("stage", "gc", "startlist", "embed_top10")
TAB_LABELS = {"stage": "STAGE", "gc": "GC", "points": "POINTS", "kom": "KOM", "youth": "YOUTH", "teams": "TEAMS"}
# FirstCycling classification-table keys (capture_results.parse_classification_tables)
FC_TABLE_KEYS = {"stage": "sta", "gc": "gc", "points": "point", "kom": "mountain", "youth": "youth", "teams": "team"}
RESULT_FIELDS = ["place", "name", "rider_id", "team", "team_id", "gap", "dob"]
NON_CLASSIFIED = ("DNS", "DNF", "OTL", "DSQ", "DQ", "NR", "DF")
STATUS_ORDER = {"DNS": 0, "DNF": 1, "OTL": 2, "DSQ": 3, "DQ": 3, "NR": 4, "DF": 5}
TOP_STAGE = 15
TOP_GC = 20
GAP_TOLERANCE_S = 0.5


class IngestError(RuntimeError):
    """Structural problem that prevents parsing at all (missing page, no table)."""


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.lower().replace("-", " ").split())


def _name_tokens(s: str) -> frozenset:
    return frozenset(_norm(s).split())


def parse_time_to_seconds(text: str) -> Optional[float]:
    """``h:mm:ss`` / ``m:ss`` / ``ss`` (optional leading ``+``) → seconds; None if not a time."""
    t = (text or "").strip().lstrip("+").strip()
    if not t or not any(ch.isdigit() for ch in t):
        return None
    t = t.replace("″", "").replace('"', "")
    parts = t.split(":")
    try:
        nums = [float(p) for p in parts]
    except ValueError:
        return None
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    if len(nums) == 1:
        return nums[0]
    return None


def fc_gap_value(seconds: Optional[float], winner: bool) -> Any:
    """FirstCycling encoding: winner ``0`` (int), others float seconds, abandons ``''``."""
    if winner:
        return 0
    if seconds is None:
        return ""
    return float(seconds)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Parsed rows
# ---------------------------------------------------------------------------

@dataclass
class PcsRow:
    index: int                      # 0-based row order on the page
    place_text: str
    status: str                     # 'classified' | 'DNF' | 'DNS' | 'OTL' | 'DSQ' ...
    place: Optional[int]
    rider_slug: Optional[str]
    pcs_name: Optional[str]
    team_slug: Optional[str]
    team_name: Optional[str]
    bib: Optional[str]
    time_visible: str
    time_resolved: str
    gap_seconds: Optional[float] = None
    same_time: bool = False
    transposed: bool = False


@dataclass
class StartRow:
    bib: Optional[str]
    rider_slug: Optional[str]
    pcs_name: str
    team_slug: Optional[str]
    team_name: Optional[str]
    status: Optional[str] = None        # 'DNF' | 'DNS' | None
    status_stage: Optional[int] = None


@dataclass
class TeamRow:
    place_text: str
    team_slug: Optional[str]
    team_name: str
    time_visible: str
    time_resolved: str
    gap_seconds: Optional[float] = None


@dataclass
class Check:
    name: str
    ok: bool
    detail: Any = None

    def as_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "ok": self.ok, "detail": self.detail}


@dataclass
class IngestReport:
    unit: str
    verdict: str                                  # 'accepted' | 'rejected'
    checks: List[Check] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    written: List[str] = field(default_factory=list)
    n_classified: int = 0
    n_abandons: int = 0
    winner: Optional[str] = None
    winning_time: Optional[float] = None
    unresolved: List[Dict[str, Any]] = field(default_factory=list)
    pages: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # Identity policy inside the top gate and, under ``provisional``, the top-gate rows archived
    # under a ``uci:`` id (operator ruling 2026-09-16; see uci_ingest.py).  The PCS path leaves
    # both at their defaults: it has always been strict.
    identity_policy: str = "strict"
    provisional_top: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.verdict == "accepted"

    @property
    def failing(self) -> List[Dict[str, Any]]:
        return [c.as_dict() for c in self.checks if not c.ok]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "unit": self.unit, "verdict": self.verdict, "ok": self.ok,
            "checks": [c.as_dict() for c in self.checks], "failing": self.failing,
            "warnings": self.warnings, "written": self.written,
            "n_classified": self.n_classified, "n_abandons": self.n_abandons,
            "winner": self.winner, "winning_time": self.winning_time,
            "unresolved": self.unresolved, "pages": self.pages,
            "identity_policy": self.identity_policy, "provisional_top": self.provisional_top,
        }


# ---------------------------------------------------------------------------
# DOM parsing
# ---------------------------------------------------------------------------

def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def result_tabs(soup: BeautifulSoup) -> Dict[str, Dict[str, Any]]:
    """``{LABEL: {'data_id': …, 'active': bool, 'table': <table> or None}}``."""
    out: Dict[str, Dict[str, Any]] = {}
    for li in soup.select("ul.resultTabs li"):
        label = li.get_text(" ", strip=True).upper()
        data_id = li.get("data-id")
        div = soup.select_one(f'div.resTab[data-id="{data_id}"]') if data_id else None
        table = div.select_one("table.results") if div is not None else None
        out[label] = {"data_id": data_id, "active": "cur" in (li.get("class") or []), "table": table}
    return out


def active_tab_label(soup: BeautifulSoup) -> Optional[str]:
    for label, meta in result_tabs(soup).items():
        if meta["active"]:
            return label
    return None


def _header_index(table) -> Dict[str, int]:
    heads = [th.get_text(" ", strip=True).lower() for th in table.select("thead th")]
    if not heads:                                   # some tables carry the header in the first tr
        first = table.find("tr")
        heads = [c.get_text(" ", strip=True).lower() for c in first.find_all(["th", "td"])] if first else []
    idx: Dict[str, int] = {}
    for i, h in enumerate(heads):
        if h in ("rnk", "pos", "#") and "rank" not in idx:
            idx["rank"] = i
        elif h == "rider":
            idx["rider"] = i
        elif h == "team":
            idx["team"] = i
        elif h == "bib":
            idx["bib"] = i
        elif h == "time" and "time" not in idx:
            idx["time"] = i
        elif h in ("pnt", "points") and "points" not in idx:
            idx["points"] = i
    return idx


def _rider_link(cell) -> Optional[Any]:
    return cell.select_one('a[href^="rider/"]') if cell is not None else None


def _team_link(cell) -> Optional[Any]:
    return cell.select_one('a[href^="team/"]') if cell is not None else None


def _time_cell(cell) -> Tuple[str, str]:
    if cell is None:
        return "", ""
    font = cell.find("font")
    hidden = cell.select_one("span.hide")
    visible = font.get_text(" ", strip=True) if font is not None else cell.get_text(" ", strip=True)
    resolved = hidden.get_text(" ", strip=True) if hidden is not None else ""
    return visible, resolved


def _status_of(place_text: str) -> Tuple[str, Optional[int]]:
    t = (place_text or "").strip().upper()
    if t.isdigit():
        return "classified", int(t)
    for tag in NON_CLASSIFIED:
        if t.startswith(tag):
            return tag, None
    return t or "?", None


def parse_rider_table(table, bib_index: Optional[Dict[str, "StartRow"]] = None) -> List[PcsRow]:
    """Rows of a rider-classification table (stage / gc / points / kom / youth).

    Transposition cross-check: PCS occasionally renders a row with the wrong
    rider link (the bib, age and team column belong to one rider, the
    ``a[href^="rider/"]`` to a neighbour). The tell is the rider cell's own
    team caption (``div.showIfMobile``) disagreeing with the team column; the
    fix is the startlist's bib → rider map (``bib_index``). Unresolvable rows
    are flagged ``transposed`` with ``rider_slug`` cleared so ``ingest`` fails
    closed rather than crediting the wrong rider.
    """
    idx = _header_index(table)
    if "rider" not in idx or "rank" not in idx:
        raise IngestError(f"rider table lacks Rnk/Rider columns: {sorted(idx)}")
    rows: List[PcsRow] = []
    prev_gap: Optional[float] = None
    winner_seen = False
    for i, tr in enumerate(table.select("tbody tr") or table.find_all("tr")[1:]):
        tds = tr.find_all("td")
        if len(tds) <= max(idx.values()):
            continue
        place_text = tds[idx["rank"]].get_text(" ", strip=True)
        status, place = _status_of(place_text)
        rider_cell = tds[idx["rider"]]
        team_cell = tds[idx["team"]] if "team" in idx else None
        rlink = _rider_link(rider_cell)
        tlink = _team_link(team_cell)
        transposed = False
        if rlink is None and _rider_link(team_cell) is not None:      # PCS transposition
            rlink, tlink = _rider_link(team_cell), _team_link(rider_cell)
            transposed = True
        elif rlink is not None and tlink is None and _team_link(rider_cell) is not None:
            tlink = _team_link(rider_cell)
            transposed = True
        slug = rlink["href"].split("/", 1)[1].strip("/") if rlink is not None and rlink.get("href") else None
        pcs_name = " ".join(rlink.get_text(" ", strip=True).split()) if rlink is not None else None
        team_slug = tlink["href"].split("/", 1)[1].strip("/") if tlink is not None and tlink.get("href") else None
        team_name = " ".join(tlink.get_text(" ", strip=True).split()) if tlink is not None else None
        if team_name is None and team_cell is not None:
            team_name = " ".join(team_cell.get_text(" ", strip=True).split()) or None
        bib = tds[idx["bib"]].get_text(" ", strip=True) if "bib" in idx else None
        # rider link vs team column: the rider cell captions its own team for mobile
        caption_el = rider_cell.select_one("div.showIfMobile") if rider_cell is not None else None
        caption = " ".join(caption_el.get_text(" ", strip=True).split()) if caption_el is not None else ""
        if slug and caption and team_name and _norm(caption) != _norm(team_name):
            start = (bib_index or {}).get(bib or "")
            if start is not None and start.rider_slug and start.rider_slug != slug and \
                    (not start.team_name or _norm(start.team_name).startswith(_norm(team_name))
                     or _norm(team_name).startswith(_norm(start.team_name))):
                slug, pcs_name, transposed = start.rider_slug, start.pcs_name, True
            elif start is not None and start.rider_slug == slug:
                pass                                   # caption drift only; the link agrees with the bib
            else:
                slug, transposed = None, True          # cannot resolve: fail closed downstream
        visible, resolved = _time_cell(tds[idx["time"]] if "time" in idx else None)
        row = PcsRow(index=i, place_text=place_text, status=status, place=place, rider_slug=slug,
                     pcs_name=pcs_name, team_slug=team_slug, team_name=team_name, bib=bib,
                     time_visible=visible, time_resolved=resolved, transposed=transposed)
        if status == "classified":
            if visible.startswith(",,"):
                row.same_time = True
                row.gap_seconds = prev_gap
            elif not winner_seen:
                row.gap_seconds = 0.0 if parse_time_to_seconds(resolved or visible) is not None else None
                winner_seen = True
            else:
                row.gap_seconds = parse_time_to_seconds(resolved or visible)
            if row.gap_seconds is not None:
                prev_gap = row.gap_seconds
        rows.append(row)
    return rows


def winning_time_of(table) -> Optional[float]:
    idx = _header_index(table)
    if "time" not in idx:
        return None
    first = table.select_one("tbody tr")
    if first is None:
        return None
    tds = first.find_all("td")
    if len(tds) <= idx["time"]:
        return None
    visible, resolved = _time_cell(tds[idx["time"]])
    return parse_time_to_seconds(resolved or visible)


def parse_team_table(table) -> List[TeamRow]:
    idx = _header_index(table)
    rows: List[TeamRow] = []
    prev: Optional[float] = None
    for i, tr in enumerate(table.select("tbody tr")):
        tds = tr.find_all("td")
        if "team" not in idx or len(tds) <= idx["team"]:
            continue
        place_text = tds[idx["rank"]].get_text(" ", strip=True) if "rank" in idx else str(i + 1)
        tlink = _team_link(tds[idx["team"]])
        team_name = " ".join((tlink or tds[idx["team"]]).get_text(" ", strip=True).split())
        visible, resolved = _time_cell(tds[idx["time"]] if "time" in idx else None)
        gap = prev if visible.startswith(",,") else (0.0 if i == 0 else parse_time_to_seconds(resolved or visible))
        prev = gap if gap is not None else prev
        rows.append(TeamRow(place_text, tlink["href"].split("/", 1)[1] if tlink else None, team_name, visible, resolved, gap))
    return rows


_ANNOT_RE = re.compile(r"\((DNF|DNS|OTL|DSQ)\s*#?\s*(\d+)?\)", re.I)


def parse_startlist(html: str) -> List[StartRow]:
    soup = _soup(html)
    out: List[StartRow] = []
    for cont in soup.select("div.ridersCont"):
        tlink = cont.select_one('a.team[href^="team/"]') or cont.select_one('a[href^="team/"]')
        team_slug = tlink["href"].split("/", 1)[1] if tlink is not None else None
        team_name = " ".join(tlink.get_text(" ", strip=True).split()) if tlink is not None else None
        for li in cont.select("ul li"):
            bib_el = li.select_one("span.bib")
            a = li.select_one('a[href^="rider/"]')
            if a is None:
                continue
            text = li.get_text(" ", strip=True)
            m = _ANNOT_RE.search(text)
            out.append(StartRow(
                bib=bib_el.get_text(strip=True) if bib_el is not None else None,
                rider_slug=a["href"].split("/", 1)[1].strip("/"),
                pcs_name=" ".join(a.get_text(" ", strip=True).split()),
                team_slug=team_slug, team_name=team_name,
                status=m.group(1).upper() if m else None,
                status_stage=int(m.group(2)) if m and m.group(2) else None,
            ))
    return out


def parse_embed_tables(html: str) -> List[List[Dict[str, str]]]:
    """Every ``Rnk | Rider | Team | Time`` table on the embed page, in page order."""
    soup = _soup(html)
    tables: List[List[Dict[str, str]]] = []
    for table in soup.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) < 3 or not cells[0].strip().isdigit():
                continue
            rows.append({"rank": cells[0].strip(), "name": cells[1].strip(), "team": cells[2].strip(),
                         "time": cells[3].strip() if len(cells) > 3 else ""})
        if rows:
            tables.append(rows)
    return tables


# ---------------------------------------------------------------------------
# Identity: crosswalk + roster
# ---------------------------------------------------------------------------

def load_crosswalk(csv_path: Optional[Path] = None, extra_rows: Iterable[Dict[str, Any]] = ()) -> Dict[str, Dict[str, Any]]:
    """``pcs_slug → row`` for rows that are auto-accepted (≥ 0.97) or human-confirmed.

    ``extra_rows`` are store-table rows (same columns); a store row replaces
    the CSV row for the same slug when it is confirmed or at least as confident.
    """
    accepted: Dict[str, Dict[str, Any]] = {}

    def _take(row: Dict[str, Any]) -> None:
        slug = str(row.get("pcs_slug") or "").strip()
        fc = str(row.get("fc_rider_id") or "").strip()
        if not slug or not fc:
            return
        try:
            conf = float(row.get("confidence") or 0.0)
        except (TypeError, ValueError):
            conf = 0.0
        confirmed = bool(str(row.get("confirmed_by") or "").strip())
        if not (confirmed or conf >= AUTO_ACCEPT):
            return
        prev = accepted.get(slug)
        if prev is None or confirmed or conf >= float(prev.get("confidence") or 0.0):
            accepted[slug] = {**row, "confidence": conf, "confirmed": confirmed}

    for row in read_crosswalk_csv(Path(csv_path) if csv_path else CROSSWALK_CSV):
        _take(row)
    for row in extra_rows:
        _take(dict(row))
    return accepted


def campaign_roster(campaign_dir: Path, stage: Optional[int]) -> Dict[str, Dict[str, str]]:
    """``fc_rider_id → {name, team, team_id, dob}`` from earlier archived stages (latest wins)."""
    roster: Dict[str, Dict[str, str]] = {}
    results_root = Path(campaign_dir) / "results"
    if not results_root.is_dir():
        return roster
    dirs = []
    for p in results_root.glob("stage_*"):
        try:
            n = int(p.name.split("_", 1)[1])
        except ValueError:
            continue
        if stage is None or n < stage:
            dirs.append((n, p))
    for _, p in sorted(dirs):
        for fname in ("results.csv", "gc.csv"):
            f = p / fname
            if not f.exists():
                continue
            with open(f, newline="", encoding="utf-8") as fh:
                for r in csv.DictReader(fh):
                    rid = str(r.get("rider_id") or "").strip()
                    if rid:
                        roster[rid] = {"name": r.get("name", ""), "team": r.get("team", ""),
                                       "team_id": r.get("team_id", ""), "dob": r.get("dob", "")}
    return roster


def db_roster(db_path: Optional[Path], fc_race_id: Optional[str], year: Optional[int]) -> Dict[str, Dict[str, str]]:
    """Fallback presentation from the serving DB (cached startlist + riders.birth_year)."""
    if not db_path or not Path(db_path).exists():
        return {}
    out: Dict[str, Dict[str, str]] = {}
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            for fc, name, by in con.execute("select fc_rider_id, name, birth_year from riders"):
                out[str(fc)] = {"name": name or "", "team": "", "team_id": "", "dob": str(by) if by else ""}
            if fc_race_id is not None and year is not None:
                for fc, name, team, team_fc in con.execute(
                        "select rider_fc_id, rider_name, team_name, team_fc_id from cached_start_lists "
                        "where fc_race_id = ? and year = ?", (str(fc_race_id), int(year))):
                    row = out.setdefault(str(fc), {"name": name or "", "team": "", "team_id": "", "dob": ""})
                    row["team"] = team or row["team"]
                    row["team_id"] = str(team_fc) if team_fc else row["team_id"]
                    row["name"] = row["name"] or (name or "")
        finally:
            con.close()
    except sqlite3.Error as exc:  # noqa: BLE001 — the roster is a fallback layer
        logger.warning("db roster unavailable: %s", exc)
    return out


# ---------------------------------------------------------------------------
# The ingest
# ---------------------------------------------------------------------------

def read_index(pcs_dir: Path) -> Dict[str, Any]:
    p = pcs_dir / "pcs_raw.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise IngestError(f"pcs_raw.json is not valid JSON: {exc}") from exc


def page_path(pcs_dir: Path, index: Dict[str, Any], kind: str) -> Optional[Path]:
    entry = (index.get("pages") or {}).get(kind) or {}
    name = entry.get("file") or PAGE_FILES[kind]
    p = pcs_dir / name
    return p if p.exists() else None


def _fc_order(rows: List[PcsRow]) -> List[PcsRow]:
    """FirstCycling row order: classified by place, then DNS block, then DNF/OTL/DSQ, each by (team, name)."""
    classified = sorted((r for r in rows if r.status == "classified"), key=lambda r: r.place or 0)
    others = [r for r in rows if r.status != "classified"]
    return classified + others


def _abandon_sort_key(fc_row: Dict[str, Any]) -> Tuple[int, str, str]:
    return (STATUS_ORDER.get(str(fc_row["place"]), 9), str(fc_row["team"]), str(fc_row["name"]))


def ingest(campaign_dir: Path, unit: str, *, crosswalk: Optional[Dict[str, Dict[str, Any]]] = None,
           crosswalk_csv: Optional[Path] = None, store_rows: Iterable[Dict[str, Any]] = (),
           db_path: Optional[Path] = None, write: bool = True, now: Optional[datetime] = None) -> IngestReport:
    campaign_dir = Path(campaign_dir)
    unit_dir = campaign_dir / "results" / unit
    pcs_dir = unit_dir / "pcs"
    report = IngestReport(unit=unit, verdict="rejected")
    checks = report.checks
    try:
        stage = int(unit.split("_", 1)[1])
    except (IndexError, ValueError):
        stage = None

    campaign = {}
    cpath = campaign_dir / "campaign.json"
    if cpath.exists():
        campaign = json.loads(cpath.read_text(encoding="utf-8"))

    # ---- pages ------------------------------------------------------------
    if not pcs_dir.is_dir():
        checks.append(Check("pages_present", False, f"no {pcs_dir.relative_to(campaign_dir)} directory"))
        return report
    index = read_index(pcs_dir)
    pages: Dict[str, Path] = {}
    missing = []
    for kind in PAGE_FILES:
        p = page_path(pcs_dir, index, kind)
        if p is not None:
            pages[kind] = p
            data = p.read_bytes()
            entry = dict((index.get("pages") or {}).get(kind) or {})
            report.pages[kind] = {"file": p.name, "bytes": len(data), "sha256": sha256_bytes(data),
                                  "source_url": entry.get("source_url"), "fetched_at": entry.get("fetched_at")}
        elif kind in REQUIRED_PAGES:
            missing.append(kind)
    checks.append(Check("pages_present", not missing, {"missing": missing, "present": sorted(pages)}))
    if missing:
        return report

    # ---- startlist first: its bib → rider map resolves PCS transpositions ------
    startlist = parse_startlist(pages["startlist"].read_text(encoding="utf-8", errors="replace"))
    bib_index = {s.bib: s for s in startlist if s.bib}

    # ---- stage table ----------------------------------------------------------
    stage_soup = _soup(pages["stage"].read_text(encoding="utf-8", errors="replace"))
    tabs = result_tabs(stage_soup)
    active = active_tab_label(stage_soup)
    checks.append(Check("active_tab_stage", active == TAB_LABELS["stage"], {"active": active}))
    stage_table = (tabs.get(TAB_LABELS["stage"]) or {}).get("table")
    if stage_table is None:
        checks.append(Check("stage_table", False, "no table.results in the STAGE tab"))
        return report
    try:
        stage_rows = parse_rider_table(stage_table, bib_index)
    except IngestError as exc:
        checks.append(Check("stage_table", False, str(exc)))
        return report
    winning_time = winning_time_of(stage_table)
    classified = [r for r in stage_rows if r.status == "classified"]
    abandons = [r for r in stage_rows if r.status != "classified"]
    report.n_classified, report.n_abandons = len(classified), len(abandons)
    report.winning_time = winning_time
    report.winner = classified[0].pcs_name if classified else None
    totals = (index.get("pages") or {}).get("stage", {}).get("totals") or {}

    # ---- gc table ---------------------------------------------------------------
    gc_soup = _soup(pages["gc"].read_text(encoding="utf-8", errors="replace"))
    gc_active = active_tab_label(gc_soup)
    checks.append(Check("active_tab_gc", gc_active == TAB_LABELS["gc"], {"active": gc_active}))
    gc_table = (result_tabs(gc_soup).get(TAB_LABELS["gc"]) or {}).get("table")
    if gc_table is None:
        checks.append(Check("gc_table", False, "no table.results in the GC tab"))
        return report
    try:
        gc_rows_all = parse_rider_table(gc_table, bib_index)
        gc_rows = [r for r in gc_rows_all if r.status == "classified"]
    except IngestError as exc:
        checks.append(Check("gc_table", False, str(exc)))
        return report

    # ---- secondary classifications (optional pages; fall back to the stage page's tabs) ----
    secondary: Dict[str, List[PcsRow]] = {}
    for kind in ("points", "kom", "youth"):
        src_soup = _soup(pages[kind].read_text(encoding="utf-8", errors="replace")) if kind in pages else stage_soup
        table = (result_tabs(src_soup).get(TAB_LABELS[kind]) or {}).get("table")
        if table is None:
            continue
        try:
            secondary[kind] = [r for r in parse_rider_table(table, bib_index) if r.status == "classified"]
        except IngestError as exc:
            report.warnings.append(f"{kind} table unparsed: {exc}")
    teams_table = (tabs.get(TAB_LABELS["teams"]) or {}).get("table")
    team_rows = parse_team_table(teams_table) if teams_table is not None else []

    # ---- prior abandons from the startlist annotations --------------------------------
    prior_out = [s for s in startlist if s.status and s.status_stage is not None and stage is not None and s.status_stage < stage]
    unknown_stage_out = [s for s in startlist if s.status and s.status_stage is None]
    expected_rows = len(startlist) - len(prior_out) - len(unknown_stage_out)

    # ---- check: row count ----------------------------------------------------------------------
    total = len(classified) + len(abandons)
    detail = {"classified": len(classified), "abandons": len(abandons), "rows": total,
              "startlist": len(startlist), "prior_abandons": len(prior_out),
              "unattributed_abandons": len(unknown_stage_out), "expected": expected_rows}
    if totals.get("rows") is not None:
        detail["thread_reported_rows"] = totals["rows"]
    ok_rows = (total == expected_rows and total > 0
               and (totals.get("rows") is None or int(totals["rows"]) == total))
    checks.append(Check("row_count", ok_rows, detail))

    # ---- check: transposition + rider links -----------------------------------------------------
    nolink = [f"stage {r.place_text}" for r in stage_rows if not r.rider_slug] + \
             [f"gc {r.place_text}" for r in gc_rows_all if not r.rider_slug]
    corrected = [f"stage {r.place_text}" for r in stage_rows if r.transposed and r.rider_slug] + \
                [f"gc {r.place_text}" for r in gc_rows_all if r.transposed and r.rider_slug]
    if corrected:
        report.warnings.append(f"rider links transposed on {corrected}; resolved from bib + team column via the startlist")
    checks.append(Check("rider_links", not nolink, {"rows_without_resolvable_rider": nolink, "transposed_corrected": corrected}))

    # ---- check: gaps ------------------------------------------------------------------------------
    gap_problems: List[str] = []
    if winning_time is None:
        gap_problems.append("winner time missing")
    prev = -1.0
    for r in classified:
        if r.gap_seconds is None:
            gap_problems.append(f"place {r.place}: gap unparsed ({r.time_visible!r}|{r.time_resolved!r})")
            continue
        if r.gap_seconds < 0:
            gap_problems.append(f"place {r.place}: negative gap {r.gap_seconds}")
        if r.gap_seconds + GAP_TOLERANCE_S < prev:
            gap_problems.append(f"place {r.place}: gap {r.gap_seconds} < previous {prev}")
        prev = max(prev, r.gap_seconds)
    prev = -1.0
    for r in gc_rows:
        if r.gap_seconds is None:
            gap_problems.append(f"gc {r.place}: gap unparsed ({r.time_visible!r}|{r.time_resolved!r})")
            continue
        if r.gap_seconds + GAP_TOLERANCE_S < prev:
            gap_problems.append(f"gc {r.place}: gap {r.gap_seconds} < previous {prev}")
        prev = max(prev, r.gap_seconds)
    checks.append(Check("gaps", not gap_problems, {"winning_time": winning_time, "problems": gap_problems[:20]}))

    # ---- check: podium vs embed ----------------------------------------------------------------------------
    embed = parse_embed_tables(pages["embed_top10"].read_text(encoding="utf-8", errors="replace"))
    podium_check = [r["name"] for r in embed[0][:3]] if embed else []
    podium = [r.pcs_name or "" for r in classified[:3]]
    pod_ok = bool(podium_check) and len(podium) == 3 and all(
        _name_tokens(a) == _name_tokens(b) for a, b in zip(podium, podium_check))
    checks.append(Check("podium", pod_ok, {"stage_table": podium, "podium_check": podium_check}))

    # ---- check: gc rows == classified riders -------------------------------------------------------------
    gc_slugs = {r.rider_slug for r in gc_rows}
    st_slugs = {r.rider_slug for r in classified}
    checks.append(Check("gc_matches_field", gc_slugs == st_slugs and len(gc_rows) == len(classified),
                        {"gc_rows": len(gc_rows), "classified": len(classified),
                         "only_in_gc": sorted(gc_slugs - st_slugs)[:10], "only_in_stage": sorted(st_slugs - gc_slugs)[:10]}))

    # ---- crosswalk ------------------------------------------------------------------------------------------------
    xw = crosswalk if crosswalk is not None else load_crosswalk(crosswalk_csv, store_rows)

    def resolve(slug: Optional[str]) -> Optional[Dict[str, Any]]:
        return xw.get(slug) if slug else None

    def unresolved_of(rows: List[PcsRow]) -> List[Dict[str, Any]]:
        out = []
        for r in rows:
            if resolve(r.rider_slug) is None:
                out.append({"place": r.place_text, "pcs_slug": r.rider_slug, "pcs_name": r.pcs_name,
                            "team": r.team_name, "bib": r.bib})
        return out

    top_stage_unres = unresolved_of(classified[:TOP_STAGE])
    top_gc_unres = unresolved_of(gc_rows[:TOP_GC])
    checks.append(Check("crosswalk_top", not top_stage_unres and not top_gc_unres,
                        {"threshold": AUTO_ACCEPT, "stage_top15_unresolved": top_stage_unres,
                         "gc_top20_unresolved": top_gc_unres}))
    all_unres = unresolved_of(stage_rows)
    report.unresolved = all_unres
    checks.append(Check("crosswalk_all_rows", not all_unres,
                        {"unresolved": all_unres, "note": "every row needs a FirstCycling id before the archive can be written"}))

    # ---- presentation: roster --------------------------------------------------------------------------------------
    roster = campaign_roster(campaign_dir, stage)
    fallback = db_roster(db_path, campaign.get("fc_race_id"), campaign.get("year")) if db_path else {}
    fetched_at = (now or datetime.now()).isoformat(timespec="seconds")

    def fc_row(r: PcsRow, winner: bool) -> Optional[Dict[str, Any]]:
        x = resolve(r.rider_slug)
        if x is None:
            return None
        fc_id = str(x["fc_rider_id"])
        pres = roster.get(fc_id) or fallback.get(fc_id) or {}
        name = pres.get("name") or x.get("fc_name") or (r.pcs_name or "")
        team = pres.get("team") or (r.team_name or "")
        team_id = pres.get("team_id") or ""
        dob = pres.get("dob") or str(x.get("birth_year") or "")
        gap = fc_gap_value(r.gap_seconds, winner) if r.status == "classified" else ""
        return {"place": str(r.place) if r.status == "classified" else r.status,
                "name": name, "rider_id": fc_id, "team": team, "team_id": team_id, "gap": gap, "dob": dob}

    if not roster:
        report.warnings.append("no earlier archived stage: rider presentation from the DB / crosswalk")
    missing_pres = [str(resolve(r.rider_slug)["fc_rider_id"]) for r in stage_rows
                    if resolve(r.rider_slug) is not None and str(resolve(r.rider_slug)["fc_rider_id"]) not in roster
                    and str(resolve(r.rider_slug)["fc_rider_id"]) not in fallback]
    if missing_pres:
        report.warnings.append(f"{len(missing_pres)} riders have no archived presentation (team/dob from PCS/crosswalk)")

    # ---- verdict -------------------------------------------------------------------------------------------------------
    if any(not c.ok for c in checks):
        return report
    report.verdict = "accepted"
    if not write:
        return report

    # ---- write (only after every check passed) -----------------------------------------------------------------------
    fc_classified = [fc_row(r, winner=(i == 0)) for i, r in enumerate(sorted(classified, key=lambda r: r.place or 0))]
    fc_abandons = sorted((fc_row(r, False) for r in abandons), key=_abandon_sort_key)
    results = [r for r in fc_classified + fc_abandons if r is not None]
    fc_gc = [r for r in (fc_row(x, winner=(i == 0)) for i, x in enumerate(gc_rows)) if r is not None]

    source_url = report.pages["stage"].get("source_url") or ""
    stage_date = None
    for key in ("stages",):
        for s in campaign.get(key) or []:
            if stage is not None and int(s.get("number", -1)) == stage:
                stage_date = s.get("date")
    payload = {
        "stage": str(stage) if stage is not None else unit,
        "stage_name": f"Stage: {stage}" if stage is not None else unit,
        "url": source_url,
        "date": stage_date,
        "race_time": winning_time,
        "fetched_at": fetched_at,
        "n_results": len(results),
        "results": results,
        "source": "pcs",
        "pcs": {k: {"file": v["file"], "sha256": v["sha256"], "source_url": v.get("source_url"),
                    "fetched_at": v.get("fetched_at")} for k, v in report.pages.items()},
    }
    unit_dir.mkdir(parents=True, exist_ok=True)
    (unit_dir / "results.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")
    _write_csv(unit_dir / "results.csv", results)
    _write_csv(unit_dir / "gc.csv", fc_gc)
    tables: Dict[str, Any] = {FC_TABLE_KEYS["stage"]: results, FC_TABLE_KEYS["gc"]: fc_gc}
    for kind, rows in secondary.items():
        tables[FC_TABLE_KEYS[kind]] = [r for r in (fc_row(x, winner=False) for x in rows) if r is not None]
    if team_rows:
        tables[FC_TABLE_KEYS["teams"]] = [[t.place_text, "", "", t.team_name, t.time_resolved or t.time_visible] for t in team_rows]
    (unit_dir / "classifications.json").write_text(json.dumps(
        {"stage": payload["stage"], "fetched_at": fetched_at, "source": "pcs", "tables": tables}, indent=1), encoding="utf-8")
    report.written = ["results.json", "results.csv", "gc.csv", "classifications.json"]
    return report


def _write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=RESULT_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
