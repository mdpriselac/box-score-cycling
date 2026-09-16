"""Automatic, explicitly post-hoc boards for units that missed preview.

The settled result is the oracle.  Its winning-group shape and top-15 rider
composition select the nearest historical reference races; stage races also
use the already-recorded day-menu oracle as their key.  These artifacts are
never prospective and must always be run with ``--no-log``.
"""

from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import numpy as np

from cycling_project.nightly import oneday
from cycling_project.nightly.refs import load_signatures, newest_signature_table

ARCH = ["sprint", "mountain", "hilly", "rolling", "breakaway", "time_trial"]


REF_COUNT = 5


def _classified(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = [r for r in result.get("results", []) if str(r.get("place", "")).strip().isdigit()]
    return sorted(rows, key=lambda r: int(r["place"]))


def _profiles(fc_ids: Iterable[Any], db_path: Path) -> Dict[str, str]:
    # A provisional ``uci:<key>`` id (identity_policy=provisional, ruling 2026-09-16) is not a
    # FirstCycling id: it can never join the riders table, so it is dropped here and the caller
    # sees the rider as "unknown" — the same reading as a rider who is not in the model field.
    ids = [str(x) for x in fc_ids if x not in (None, "") and not str(x).startswith("uci:")]
    if not ids or not db_path.exists():
        return {}
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        con.execute("CREATE TEMP TABLE want(fc_id TEXT PRIMARY KEY)")
        con.executemany("INSERT OR IGNORE INTO want VALUES (?)", [(x,) for x in ids])
        rows = con.execute(
            """
            SELECT r.fc_rider_id, s.best_profile
            FROM riders r JOIN want w ON w.fc_id = CAST(r.fc_rider_id AS TEXT)
            JOIN rider_competition_snapshots s ON s.rider_id = r.id
            JOIN (SELECT rider_id, MAX(competition_id) mc
                  FROM rider_competition_snapshots GROUP BY rider_id) z
              ON z.rider_id=s.rider_id AND z.mc=s.competition_id
            """
        ).fetchall()
    finally:
        con.close()
    return {str(fc): (profile or "unknown") for fc, profile in rows}


def result_signature(result: Dict[str, Any], db_path: Path) -> Dict[str, Any]:
    rows = _classified(result)
    gaps = np.asarray([r["gap"] for r in rows if isinstance(r.get("gap"), (int, float))], dtype=float)
    if not len(gaps):
        raise ValueError("settled result has no numeric time gaps")
    gaps = np.sort(gaps) - gaps.min()
    # Keep the production front-local taxonomy without importing the experiment
    # module (which pulls training-only sklearn into the nightly container).
    sizes, current = [], 1
    for idx in range(1, len(gaps)):
        if gaps[idx] - gaps[idx - 1] <= 1.0:
            current += 1
        else:
            sizes.append(current)
            current = 1
    sizes.append(current)
    wg = sizes[0]
    top15 = gaps[:min(15, len(gaps))]
    top_groups = 1 + sum(top15[idx] - top15[idx - 1] > 1.0 for idx in range(1, len(top15)))
    if top_groups >= 13:
        rule = "itt_like"
    elif wg >= 40:
        rule = "mass_sprint"
    elif wg >= 20:
        rule = "bunch_sprint"
    elif wg >= 8:
        rule = "reduced_sprint"
    elif wg >= 4:
        rule = "small_group"
    elif wg >= 2:
        rule = "tiny_group"
    else:
        rule = "solo"
    profiles = _profiles((r.get("rider_id") for r in rows[:15]), db_path)
    top = [profiles.get(str(r.get("rider_id")), "unknown") for r in rows[:15]]
    denom = len(top) or 1
    shares = {a: top.count(a) / denom for a in ARCH}
    return {
        "rule_type": rule,
        "wg_size": int(wg),
        "wg_prop": float(wg / len(gaps)),
        "top15_shares": shares,
    }


def _usable_reference_ids(db_path: Path) -> Optional[set[int]]:
    if not db_path.exists():
        return None
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        return {int(r[0]) for r in con.execute("SELECT competition_id FROM competition_field_features")}
    except sqlite3.Error:
        return None
    finally:
        con.close()


def nearest_refs(signature: Dict[str, Any], *, competition_type: str, before: str,
                 db_path: Path, exclude: Iterable[int] = (), count: int = REF_COUNT) -> List[int]:
    """Nearest prior realized signatures, deterministically newest on ties."""
    table = newest_signature_table()
    if table is None:
        return []
    usable = _usable_reference_ids(db_path)
    excluded = {int(x) for x in exclude}
    target = [float(signature.get("wg_prop") or 0.0)] + [
        float((signature.get("top15_shares") or {}).get(a) or 0.0) for a in ARCH
    ]
    ranked = []
    for row in load_signatures(table):
        cid = int(row["comp_id"])
        if cid in excluded or row.get("competition_type") != competition_type:
            continue
        if str(row.get("date") or "") >= str(before):
            continue
        if usable is not None and cid not in usable:
            continue
        vec = [float(row.get("wg_prop") or 0.0)] + [float(row.get(f"top15_{a}") or 0.0) for a in ARCH]
        distance = math.sqrt(sum((a - b) ** 2 for a, b in zip(target, vec)))
        ranked.append((distance, -int(str(row.get("date") or "0").replace("-", "") or 0), cid))
    ranked.sort()
    return [cid for _, _, cid in ranked[:count]]


def _oracle_for_stage(campaign_dir: Path, stage: int) -> Dict[str, Any]:
    path = campaign_dir / "review" / "key_scorecard.json"
    rows = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    found = next((r for r in reversed(rows) if int(r.get("stage", -1)) == int(stage)), None)
    if not found or not found.get("oracle_item"):
        raise ValueError(f"no settled oracle row for stage {stage}")
    return found


def _write_result_field(result: Dict[str, Any], path: Path, *, fc_race_id: str, year: int) -> None:
    """Freeze the settled field for a post-hoc run when no morning field exists."""
    if path.exists():
        return
    teams: Dict[tuple[str, str], List[Dict[str, Any]]] = {}
    skipped: List[str] = []
    for row in result.get("results", []):
        if not row.get("rider_id"):
            continue
        if str(row["rider_id"]).startswith("uci:"):
            # A provisional identity is not a rider the model can price: it never enters the frozen
            # field (a uci: key would resolve to nothing downstream).  Recorded, not silently dropped.
            skipped.append(str(row.get("name") or row["rider_id"]))
            continue
        key = (str(row.get("team") or "Unknown team"), str(row.get("team_id") or ""))
        teams.setdefault(key, []).append({"name": row.get("name"), "rider_id": str(row["rider_id"]), "number": ""})
    doc = {
        "fc_race_id": str(fc_race_id), "year": int(year),
        "source": "settled results (post-hoc field; not a morning start list)",
        "excluded_provisional_identities": skipped,
        "teams": [{"name": name, "team_id": team_id or None, "riders": riders}
                  for (name, team_id), riders in teams.items()],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def build(campaign_dir: Path, unit: str, *, fc_race_id: str, year: int, date: str,
          label: str, db_path: Path, stage: Optional[int], void_stages: Iterable[int] = ()) -> Dict[str, Any]:
    """Create a post-hoc config and result-derived field; return provenance."""
    campaign_dir = Path(campaign_dir)
    pred = campaign_dir / "predictions" / unit
    result_path = campaign_dir / "results" / unit / "results.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    sig = result_signature(result, db_path)
    oracle = _oracle_for_stage(campaign_dir, stage) if stage is not None else sig
    refs = nearest_refs(sig, competition_type="stage" if stage is not None else "one_day",
                        before=date, db_path=db_path)
    if not refs and stage is None:
        refs = oneday.own_edition_refs(fc_race_id, year, db_path=db_path)
    if not refs:
        raise ValueError("no usable historical references match the settled oracle")

    note = ("RETROSPECTIVE ONLY — no pre-race prediction was made. This board uses the settled "
            "result as the oracle and the nearest historical realized race shapes. It is corpus "
            "completion, not evidence of forecasting skill.")
    scenario = {
        "label": "Hindsight (post-hoc) — oracle-matched references",
        "short": "Hindsight (post-hoc)", "refs": refs,
        "tag": f"{campaign_dir.name}_{'race' if stage is None else f'st{stage:02d}'}_hindsight",
        "note": note, "post_hoc": True,
    }
    config: Dict[str, Any] = {
        "fc_race_id": str(fc_race_id), "year": int(year), "date": date,
        "label": f"{label} (no prediction made)", "post_hoc": True,
        "post_hoc_note": note, "event_id": None, "odds_capture": None,
        "scenarios": {"hindsight": scenario},
    }
    if stage is None:
        config["target"] = "one_day"
    else:
        config["stage"] = int(stage)
        config["void_stages"] = sorted({int(x) for x in void_stages})
        scenario["day_key"] = {str(oracle["oracle_item"]): 1.0}

    pred.mkdir(parents=True, exist_ok=True)
    cfg_path = pred / "scenarios.json"
    cfg_path.write_text(json.dumps(config, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_result_field(result, pred / oneday.STARTLIST_NAME, fc_race_id=fc_race_id, year=year)
    return {"path": str(cfg_path), "refs": refs, "oracle": oracle,
            "signature": sig, "post_hoc": True}
