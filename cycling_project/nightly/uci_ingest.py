"""``nightly ingest --provider uci`` — deterministic UCI JSON → FirstCycling-shaped results.

Provider adapter for the capture written by ``uci_acquire.py`` under
``results/<unit>/uci/`` (``competition.html``, ``stage.json``, ``gc.json``,
optional ``points.json`` / ``kom.json`` / ``youth.json`` / ``teams.json``,
index ``uci_raw.json``). Nothing downstream trusts the capture until every
check below has passed; then the same FC-shaped archive files
``pcs_ingest.py`` writes are produced (``results.csv`` / ``results.json`` /
``gc.csv`` / ``classifications.json``), byte-compatible with
``capture_results.py``. On failure nothing is written and the failing checks
(and the unresolved identities as ``crosswalk_proposals`` rows) are reported.

UCI JSON shape (verified 2026-09-06, Vuelta 2026 stage 14): ``{results: [{headerType:
"rider", values: {rank, firstname, lastname, team, result, points, age, nationality}}],
podium: {podium: [{firstname, lastname, team, time}], discipline}, headers: [...]}``.
``rank`` is a numeric string for classified riders and ``null`` for DNS/DNF/…
whose status is in ``result``; ``result`` is the winner's absolute time, then
``+s`` / ``+m:ss`` / ``+h:mm:ss`` gaps (an empty value = same time as the
previous rider). Original strings are preserved in ``results.json`` under
``uci``; only the canonical files carry converted seconds.

Identity: ``uci_identity.py`` (roster / crosswalk / DB scope, aliases,
proposals). Names are never used as ids.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from cycling_project.nightly import uci_identity as ident
from cycling_project.nightly.crosswalk import name_tokens, teams_match
from cycling_project.nightly.pcs_ingest import (
    FC_TABLE_KEYS,
    GAP_TOLERANCE_S,
    NON_CLASSIFIED,
    TOP_GC,
    TOP_STAGE,
    Check,
    IngestReport,
    _abandon_sort_key,
    _write_csv,
    campaign_roster,
    db_roster,
    fc_gap_value,
    load_crosswalk,
    parse_time_to_seconds,
    sha256_bytes,
)
from cycling_project.nightly.uci_acquire import CLASSIFICATIONS, INDEX_NAME, PROVIDER, capture_is_complete
from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

REQUIRED_KINDS = tuple(k for k, (_t, req) in CLASSIFICATIONS.items() if req)
ABSOLUTE_TIME_RE = re.compile(r"^\d{1,2}:\d{2}:\d{2}$|^\d{1,3}:\d{2}$")
GAP_RE = re.compile(r"^\+\s*(\d+(?::\d{2}){0,2})$")
DISCIPLINE_FOR_ROAD = "ROA"


class UciIngestError(RuntimeError):
    pass


@dataclass
class UciRow:
    index: int
    kind: str
    rank_text: str
    status: str                     # 'classified' | DNS | DNF | OTL | DSQ | DQ | NR | DF | '?'
    place: Optional[int]
    firstname: str
    lastname: str
    team: Optional[str]
    result_raw: str
    points: Optional[str]
    age: Optional[int]
    nationality: Optional[str]
    gap_seconds: Optional[float] = None
    absolute_seconds: Optional[float] = None
    same_time: bool = False

    @property
    def rider(self) -> ident.UciRider:
        return ident.UciRider(self.firstname, self.lastname, self.team, self.age, self.nationality, self.rank_text)

    @property
    def display(self) -> str:
        return ident.uci_display_name(self.lastname, self.firstname)


@dataclass
class TeamRow:
    index: int
    rank_text: str
    place: Optional[int]
    team: str
    result_raw: str
    gap_seconds: Optional[float]


# ---------------------------------------------------------------------------
# parsing (pure)
# ---------------------------------------------------------------------------

def _status_of(rank: Any, result: str) -> Tuple[str, Optional[int]]:
    r = str(rank).strip() if rank is not None else ""
    if r.isdigit():
        return "classified", int(r)
    tag = (result or "").strip().upper()
    for t in NON_CLASSIFIED:
        if tag == t or tag.startswith(t + " "):
            return t, None
    if r:
        for t in NON_CLASSIFIED:
            if r.upper().startswith(t):
                return t, None
    return "?", None


def parse_result_value(value: str) -> Tuple[Optional[float], Optional[float], bool]:
    """``(gap_seconds, absolute_seconds, same_time)`` for one ``result`` string.

    ``+1`` / ``+2:06`` / ``+1:02:03`` → gap; ``4:15:09`` / ``49:28:12`` → absolute; ``""`` → same time.
    """
    v = (value or "").strip()
    if not v:
        return None, None, True
    m = GAP_RE.match(v)
    if m:
        return parse_time_to_seconds(m.group(1)), None, False
    if ABSOLUTE_TIME_RE.match(v):
        return None, parse_time_to_seconds(v), False
    return None, None, False


def parse_rider_results(doc: Dict[str, Any], kind: str) -> List[UciRow]:
    rows: List[UciRow] = []
    if not isinstance(doc, dict) or not isinstance(doc.get("results"), list):
        raise UciIngestError(f"{kind}: response is not a {{results: [...]}} document")
    winner_abs: Optional[float] = None
    prev_gap: Optional[float] = None
    for i, entry in enumerate(doc["results"]):
        if not isinstance(entry, dict):
            raise UciIngestError(f"{kind}: results[{i}] is not an object")
        if entry.get("headerType") not in (None, "rider"):
            continue
        v = entry.get("values") or {}
        result = str(v.get("result") or "")
        status, place = _status_of(v.get("rank"), result)
        age = v.get("age")
        row = UciRow(index=i, kind=kind, rank_text=str(v.get("rank") if v.get("rank") is not None else (result or "")).strip(),
                     status=status, place=place, firstname=str(v.get("firstname") or "").strip(),
                     lastname=str(v.get("lastname") or "").strip(), team=(str(v.get("team")).strip() or None) if v.get("team") else None,
                     result_raw=result, points=str(v.get("points")) if v.get("points") is not None else None,
                     age=int(age) if isinstance(age, int) or (isinstance(age, str) and age.isdigit()) else None,
                     nationality=str(v.get("nationality") or "").strip() or None)
        if status == "classified":
            gap, absolute, same = parse_result_value(result)
            row.same_time = same
            if winner_abs is None and place == 1:
                row.absolute_seconds = absolute
                row.gap_seconds = 0.0 if absolute is not None else None
                winner_abs = absolute
            elif same:
                row.gap_seconds = prev_gap
            elif gap is not None:
                row.gap_seconds = gap
            elif absolute is not None and winner_abs is not None:
                row.absolute_seconds = absolute
                row.gap_seconds = absolute - winner_abs
            if row.gap_seconds is not None:
                prev_gap = row.gap_seconds
        rows.append(row)
    return rows


def parse_team_results(doc: Dict[str, Any]) -> List[TeamRow]:
    rows: List[TeamRow] = []
    prev: Optional[float] = None
    for i, entry in enumerate((doc or {}).get("results") or []):
        v = (entry or {}).get("values") or {}
        team = str(v.get("team") or v.get("name") or "").strip()
        if not team:
            continue
        rank = v.get("rank")
        place = int(rank) if rank is not None and str(rank).isdigit() else None
        gap, absolute, same = parse_result_value(str(v.get("result") or ""))
        g = prev if same else (0.0 if i == 0 and absolute is not None else gap)
        prev = g if g is not None else prev
        rows.append(TeamRow(i, str(rank or ""), place, team, str(v.get("result") or ""), g))
    return rows


def podium_of(doc: Dict[str, Any]) -> List[Dict[str, str]]:
    pod = (doc or {}).get("podium") or {}
    items = pod.get("podium") if isinstance(pod, dict) else pod
    return [dict(x) for x in (items or []) if isinstance(x, dict)]


# ---------------------------------------------------------------------------
# capture loading
# ---------------------------------------------------------------------------

def load_capture(uci_dir: Path) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]], Dict[str, bytes]]:
    """(index, kind → parsed JSON doc, kind → raw bytes) for every page the index lists with a file."""
    uci_dir = Path(uci_dir)
    p = uci_dir / INDEX_NAME
    if not p.exists():
        raise UciIngestError(f"no {INDEX_NAME} under {uci_dir}")
    try:
        index = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise UciIngestError(f"{INDEX_NAME} is not valid JSON: {exc}") from exc
    docs: Dict[str, Dict[str, Any]] = {}
    raw: Dict[str, bytes] = {}
    for kind, entry in (index.get("pages") or {}).items():
        if kind == "competition" or not entry.get("file"):
            continue
        f = uci_dir / entry["file"]
        if not f.exists():
            continue
        data = f.read_bytes()
        raw[kind] = data
        try:
            docs[kind] = json.loads(data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            docs[kind] = {"__malformed__": True}
    return index, docs, raw


# ---------------------------------------------------------------------------
# the ingest
# ---------------------------------------------------------------------------

def _campaign_name_ok(campaign: Dict[str, Any], comp_name: Optional[str]) -> bool:
    a = {t for t in name_tokens(campaign.get("name") or campaign.get("slug") or "") if len(t) > 2 and not t.isdigit()}
    b = {t for t in name_tokens(comp_name or "") if len(t) > 2}
    stop = {"the", "des", "del", "della", "ciclista", "cycling", "tour", "race", "grand", "prix", "vuelta", "giro", "ronde"}
    sig_a = a - stop
    return bool(sig_a & b) or (bool(a & b) and len(a & b) >= 2)


def ingest(campaign_dir: Path, unit: str, *, crosswalk_csv: Optional[Path] = None, store_rows: Iterable[Dict[str, Any]] = (),
           db_path: Optional[Path] = None, aliases_csv: Optional[Path] = None, write: bool = True,
           now: Optional[datetime] = None) -> IngestReport:
    campaign_dir = Path(campaign_dir)
    unit_dir = campaign_dir / "results" / unit
    uci_dir = unit_dir / "uci"
    report = IngestReport(unit=unit, verdict="rejected")
    report.identities = []          # type: ignore[attr-defined]  (extra: resolution table + proposals)
    report.proposals = []           # type: ignore[attr-defined]
    report.provider = PROVIDER      # type: ignore[attr-defined]
    checks = report.checks
    stage: Optional[int] = None
    m = re.fullmatch(r"stage_(\d+)", unit)
    if m:
        stage = int(m.group(1))
    campaign: Dict[str, Any] = {}
    cpath = campaign_dir / "campaign.json"
    if cpath.exists():
        campaign = json.loads(cpath.read_text(encoding="utf-8"))

    # ---- capture present + complete ---------------------------------------------------------
    try:
        index, docs, raw = load_capture(uci_dir)
    except UciIngestError as exc:
        checks.append(Check("capture_present", False, str(exc)))
        return report
    pages = index.get("pages") or {}
    missing = [k for k in REQUIRED_KINDS if k not in docs]
    checks.append(Check("capture_present", not missing and capture_is_complete(index),
                        {"missing_required": missing, "present": sorted(docs), "complete": bool(index.get("complete"))}))
    for kind, entry in pages.items():
        if entry.get("file"):
            data = raw.get(kind) if kind != "competition" else None
            if kind == "competition":
                f = uci_dir / entry["file"]
                data = f.read_bytes() if f.exists() else b""
            report.pages[kind] = {"file": entry["file"], "bytes": len(data or b""), "sha256": sha256_bytes(data or b""),
                                  "source_url": entry.get("source_url"), "fetched_at": entry.get("fetched_at"),
                                  "event_code": entry.get("event_code"), "race_type": entry.get("race_type"),
                                  "race_name": entry.get("race_name"), "http_status": entry.get("http_status"),
                                  "provider": PROVIDER}
    if missing:
        return report

    # ---- competition / stage / event codes -----------------------------------------------------
    comp = index.get("competition") or {}
    comp_ok = (campaign.get("year") is None or int(campaign["year"]) == int(comp.get("year") or -1)) \
        and (comp.get("discipline") in (None, DISCIPLINE_FOR_ROAD)) and _campaign_name_ok(campaign, comp.get("name"))
    checks.append(Check("competition_matches_campaign", comp_ok,
                        {"campaign": {"name": campaign.get("name"), "year": campaign.get("year")},
                         "uci": {"name": comp.get("name"), "year": comp.get("year"), "discipline": comp.get("discipline"), "id": comp.get("id")}}))
    st = index.get("stage") or {}
    label_ok = stage is None or ident.name_key(str(st.get("label") or "")) == ident.name_key(f"Stage {stage}")
    checks.append(Check("stage_in_schedule_and_results", bool(st.get("label")) and bool(st.get("schedule_date")) and label_ok
                        and bool(st.get("accordion_titles")), {"stage": st}))
    # A bad OPTIONAL classification page (points / kom / youth / teams) is a warning and the page is
    # dropped; only the required pages can reject the capture.  (2026-09-08: ZLM Tour stage 1 was
    # refused over a non-200 KOM page while stage and GC were perfect.)
    def _bad_code(k: str) -> bool:
        return not (pages.get(k) or {}).get("event_code") or (pages.get(k) or {}).get("race_type") not in ("A",)

    def _bad_resp(k: str, d: dict) -> bool:
        return ((pages.get(k) or {}).get("http_status") != 200 or "__malformed__" in d
                or not isinstance(d.get("results"), list) or "headers" not in d or "podium" not in d)

    optional_bad = sorted(k for k, d in docs.items() if k not in REQUIRED_KINDS and (_bad_code(k) or _bad_resp(k, d)))
    for k in optional_bad:
        report.warnings.append(f"{k}: optional classification page unusable "
                               f"(http {(pages.get(k) or {}).get('http_status')}, event_code {(pages.get(k) or {}).get('event_code')}) — dropped")
        docs.pop(k, None)
    bad_codes = [k for k in docs if _bad_code(k)]
    checks.append(Check("event_codes", not bad_codes, {"bad": bad_codes, "dropped_optional": optional_bad,
                                                       "codes": {k: (pages.get(k) or {}).get("event_code") for k in docs}}))
    bad_resp = [k for k, d in docs.items() if _bad_resp(k, d)]
    checks.append(Check("responses_ok", not bad_resp, {"bad": bad_resp, "dropped_optional": optional_bad}))
    if bad_codes or bad_resp or not label_ok:
        return report

    # ---- parse ---------------------------------------------------------------------------------
    try:
        stage_rows = parse_rider_results(docs["stage"], "stage")
        gc_rows_all = parse_rider_results(docs["gc"], "gc")
    except UciIngestError as exc:
        checks.append(Check("parse", False, str(exc)))
        return report
    classified = [r for r in stage_rows if r.status == "classified"]
    abandons = [r for r in stage_rows if r.status != "classified"]
    unknown = [r for r in stage_rows if r.status == "?"]
    gc_rows = [r for r in gc_rows_all if r.status == "classified"]
    secondary: Dict[str, List[UciRow]] = {}
    for kind in ("points", "kom", "youth"):
        if kind in docs:
            try:
                secondary[kind] = [r for r in parse_rider_results(docs[kind], kind) if r.status == "classified"]
            except UciIngestError as exc:
                report.warnings.append(f"{kind}: {exc}")
    team_rows = parse_team_results(docs["teams"]) if "teams" in docs else []
    report.n_classified, report.n_abandons = len(classified), len(abandons)
    winner = classified[0] if classified else None
    report.winner = winner.display if winner else None
    report.winning_time = winner.absolute_seconds if winner else None

    # ---- checks: winner / ranks / uniqueness / gaps / statuses ----------------------------------
    checks.append(Check("winner_time", winner is not None and winner.place == 1 and winner.absolute_seconds is not None,
                        {"winner": report.winner, "result": winner.result_raw if winner else None}))
    places = [r.place for r in classified]
    contiguous = places == list(range(1, len(places) + 1))
    checks.append(Check("ranks_contiguous_unique", contiguous and len(set(places)) == len(places),
                        {"n": len(places), "first_break": next((i + 1 for i, p in enumerate(places) if p != i + 1), None)}))
    dup = [k for k, n in _counts(r.rider.key for r in stage_rows).items() if n > 1]
    dup_gc = [k for k, n in _counts(r.rider.key for r in gc_rows).items() if n > 1]
    checks.append(Check("riders_unique", not dup and not dup_gc, {"stage_duplicates": dup[:10], "gc_duplicates": dup_gc[:10]}))
    problems: List[str] = []
    prev = -1.0
    for r in classified:
        if r.gap_seconds is None:
            problems.append(f"place {r.place}: gap unparsed ({r.result_raw!r})")
            continue
        if r.gap_seconds < 0:
            problems.append(f"place {r.place}: negative gap {r.gap_seconds}")
        if r.gap_seconds + GAP_TOLERANCE_S < prev:
            problems.append(f"place {r.place}: gap {r.gap_seconds} < previous {prev}")
        prev = max(prev, r.gap_seconds)
    checks.append(Check("gaps", not problems and winner is not None and winner.absolute_seconds is not None,
                        {"winning_time": report.winning_time, "problems": problems[:20]}))
    checks.append(Check("statuses", not unknown, {"unrecognised": [(r.rank_text, r.result_raw, r.display) for r in unknown][:10],
                                                   "abandons": sorted({r.status for r in abandons})}))

    # ---- podium block vs first three ----------------------------------------------------------
    pod = podium_of(docs["stage"])
    top3 = classified[:3]
    pod_ok = len(pod) == 3 and len(top3) == 3 and all(
        ident.name_key(f"{p.get('firstname', '')} {p.get('lastname', '')}") == ident.name_key(r.rider.full_name)
        and (str(p.get("time") or "").strip() == r.result_raw.strip()) for p, r in zip(pod, top3))
    checks.append(Check("podium", pod_ok, {"podium_block": [f"{p.get('lastname')} {p.get('firstname')} {p.get('time')}" for p in pod],
                                          "first_three": [f"{r.display} {r.result_raw}" for r in top3]}))

    # ---- GC winner / gaps / field consistency ------------------------------------------------------
    gc_winner = gc_rows[0] if gc_rows else None
    gc_problems: List[str] = []
    prev = -1.0
    for r in gc_rows:
        if r.gap_seconds is None:
            gc_problems.append(f"gc {r.place}: gap unparsed ({r.result_raw!r})")
            continue
        if r.gap_seconds + GAP_TOLERANCE_S < prev:
            gc_problems.append(f"gc {r.place}: gap {r.gap_seconds} < previous {prev}")
        prev = max(prev, r.gap_seconds)
    checks.append(Check("gc_winner_and_gaps", gc_winner is not None and gc_winner.place == 1 and gc_winner.absolute_seconds is not None
                        and not gc_problems, {"gc_winner": gc_winner.display if gc_winner else None,
                                              "gc_time": gc_winner.absolute_seconds if gc_winner else None, "problems": gc_problems[:20]}))
    gc_keys = {r.rider.key for r in gc_rows}
    st_keys = {r.rider.key for r in classified}
    checks.append(Check("row_counts_plausible", len(classified) > 0 and len(gc_rows) == len(classified) and gc_keys == st_keys,
                        {"classified": len(classified), "abandons": len(abandons), "gc_rows": len(gc_rows),
                         "only_in_gc": sorted(gc_keys - st_keys)[:10], "only_in_stage": sorted(st_keys - gc_keys)[:10],
                         "index_row_counts": {k: (pages.get(k) or {}).get("row_count") for k in docs}}))

    # ---- identity -------------------------------------------------------------------------------------
    roster = campaign_roster(campaign_dir, stage)
    fallback = db_roster(db_path, campaign.get("fc_race_id"), campaign.get("year")) if db_path else {}
    xw_rows = load_crosswalk(crosswalk_csv, store_rows)      # confirmed/accepted PCS crosswalk: fc_name + birth_year candidates
    if not roster:
        for slug, row in xw_rows.items():
            fc = str(row.get("fc_rider_id"))
            if fc and fc not in fallback and row.get("fc_name"):
                fallback[fc] = {"name": row["fc_name"], "team": "", "team_id": "", "dob": str(row.get("birth_year") or "")}
    index_ = ident.build_index(roster=roster or fallback, crosswalk_csv=crosswalk_csv, db_path=db_path,
                               fc_race_id=campaign.get("fc_race_id"), year=campaign.get("year"))
    aliases = ident.read_aliases(aliases_csv)
    season_year = int(campaign.get("year") or comp.get("year") or 0) or None
    by_key: Dict[str, ident.Resolution] = {}
    resolutions = ident.resolve_all([r.rider for r in stage_rows], index_, season_year=season_year, aliases=aliases)
    for row, res in zip(stage_rows, resolutions):
        by_key[row.rider.key] = res
    # riders appearing only in a secondary classification (should not happen) resolve the same way
    extra_riders = [r.rider for rows in list(secondary.values()) + [gc_rows] for r in rows if r.rider.key not in by_key]
    for r, res in zip(extra_riders, ident.resolve_all(extra_riders, index_, season_year=season_year, aliases=aliases)):
        by_key.setdefault(r.key, res)
    report.identities = [res.as_dict() for res in by_key.values()]  # type: ignore[attr-defined]

    def resolved(row: UciRow) -> Optional[ident.Resolution]:
        res = by_key.get(row.rider.key)
        return res if res and res.accepted else None

    def unresolved_of(rows: List[UciRow]) -> List[Dict[str, Any]]:
        out = []
        for r in rows:
            if resolved(r) is None:
                res = by_key.get(r.rider.key)
                out.append({"place": r.rank_text, "uci_name": r.display, "team": r.team, "age": r.age, "nationality": r.nationality,
                            "best": res.as_dict() if res else None})
        return out

    top_stage_unres = unresolved_of(classified[:TOP_STAGE])
    top_gc_unres = unresolved_of(gc_rows[:TOP_GC])
    checks.append(Check("crosswalk_top", not top_stage_unres and not top_gc_unres,
                        {"threshold": ident.AUTO_ACCEPT, "stage_top15_unresolved": top_stage_unres, "gc_top20_unresolved": top_gc_unres,
                         "scope": getattr(index_, "scope", None)}))
    all_unres = unresolved_of(stage_rows)
    report.unresolved = all_unres
    report.proposals = [res.to_proposal(campaign.get("slug")) for res in by_key.values() if not res.accepted]  # type: ignore[attr-defined]
    checks.append(Check("crosswalk_all_rows", not all_unres,
                        {"unresolved": all_unres, "note": "every row needs a FirstCycling id before the archive can be written (shadow period: strict)"}))
    fc_ids = [resolved(r).fc_rider_id for r in stage_rows if resolved(r)]
    checks.append(Check("fc_ids_unique", len(fc_ids) == len(set(fc_ids)), {"n": len(fc_ids), "duplicates": [x for x in set(fc_ids) if fc_ids.count(x) > 1][:10]}))

    # ---- verdict ----------------------------------------------------------------------------------------
    if any(not c.ok for c in checks):
        return report
    report.verdict = "accepted"
    if not write:
        return report

    # ---- write (only after every check passed) ----------------------------------------------------------
    fetched_at = (now or datetime.now()).isoformat(timespec="seconds")

    def fc_row(r: UciRow, winner_flag: bool) -> Optional[Dict[str, Any]]:
        res = resolved(r)
        if res is None:
            return None
        fc_id = res.fc_rider_id
        pres = roster.get(fc_id) or fallback.get(fc_id) or {}
        name = pres.get("name") or (res.candidate.name if res.candidate else "") or r.display
        team = pres.get("team") or (r.team or "")
        team_id = pres.get("team_id") or ""
        dob = pres.get("dob") or (str(res.candidate.birth_year) if res.candidate and res.candidate.birth_year else "")
        gap = fc_gap_value(r.gap_seconds, winner_flag) if r.status == "classified" else ""
        return {"place": str(r.place) if r.status == "classified" else r.status, "name": name, "rider_id": fc_id,
                "team": team, "team_id": team_id, "gap": gap, "dob": dob}

    if not roster:
        report.warnings.append("no earlier archived stage: rider presentation from the DB / crosswalk")
    fc_classified = [fc_row(r, i == 0) for i, r in enumerate(sorted(classified, key=lambda r: r.place or 0))]
    fc_abandons = sorted((fc_row(r, False) for r in abandons), key=_abandon_sort_key)
    results = [r for r in fc_classified + fc_abandons if r is not None]
    fc_gc = [r for r in (fc_row(x, i == 0) for i, x in enumerate(gc_rows)) if r is not None]
    stage_date = None
    for s in campaign.get("stages") or []:
        if stage is not None and int(s.get("number", -1)) == stage:
            stage_date = s.get("date")
    payload = {
        "stage": str(stage) if stage is not None else unit,
        "stage_name": f"Stage: {stage}" if stage is not None else unit,
        "url": (pages.get("stage") or {}).get("source_url") or "",
        "date": stage_date,
        "race_time": report.winning_time,
        "fetched_at": fetched_at,
        "n_results": len(results),
        "results": results,
        "source": PROVIDER,
        "uci": {"competition": comp, "stage": st,
                "pages": {k: {"file": v["file"], "sha256": v["sha256"], "source_url": v.get("source_url"), "fetched_at": v.get("fetched_at"),
                              "event_code": v.get("event_code"), "race_name": v.get("race_name")} for k, v in report.pages.items()},
                "raw_results": [{"rank": r.rank_text, "lastname": r.lastname, "firstname": r.firstname, "team": r.team,
                                 "result": r.result_raw, "points": r.points, "age": r.age, "nationality": r.nationality} for r in stage_rows],
                "identity_scope": getattr(index_, "scope", None)},
    }
    unit_dir.mkdir(parents=True, exist_ok=True)
    (unit_dir / "results.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")
    _write_csv(unit_dir / "results.csv", results)
    _write_csv(unit_dir / "gc.csv", fc_gc)
    tables: Dict[str, Any] = {FC_TABLE_KEYS["stage"]: results, FC_TABLE_KEYS["gc"]: fc_gc}
    for kind, rows in secondary.items():
        tables[FC_TABLE_KEYS[kind]] = [r for r in (fc_row(x, False) for x in rows) if r is not None]
    if team_rows:
        tables[FC_TABLE_KEYS["teams"]] = [[t.rank_text, "", "", t.team, t.result_raw] for t in team_rows]
    (unit_dir / "classifications.json").write_text(json.dumps(
        {"stage": payload["stage"], "fetched_at": fetched_at, "source": PROVIDER, "tables": tables}, indent=1), encoding="utf-8")
    report.written = ["results.json", "results.csv", "gc.csv", "classifications.json"]
    return report


def _counts(items: Iterable[str]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for x in items:
        out[x] = out.get(x, 0) + 1
    return out
