"""
Evening day-key scoring for the Vuelta 2026 — the tier-3 judgment evaluation.

For a settled stage, reconstructs the ORACLE menu item from the archived
results (the same labeler + frozen GMM the training keys use) and scores the
morning's logged day_key against it:

    exact           argmax-weight item == oracle item
    covered         oracle item in the keyed set (weight > 0)
    weight_on_true  weight the read put on the oracle item

Run each evening AFTER capture_results.py (which archives the stage) —
requires only the archive + the DB's pre-race rider profiles; the weekly
pipeline is NOT needed mid-race.

    uv run python performance_eval/vuelta-2026/score_day_keys.py            # latest archived stage
    uv run python performance_eval/vuelta-2026/score_day_keys.py --stage 4
    uv run python performance_eval/vuelta-2026/score_day_keys.py --also agent          # + the agent's key
    uv run python performance_eval/vuelta-2026/score_day_keys.py --agent-refresh       # re-attach every agent key, no DB

Appends to review/key_scorecard.json and prints the running table.

``--also agent`` (chip E, 2026-09-06): when ``predictions/stage_NN/agent_key.json``
exists (written by ``cycling_project.nightly.run_day_key``), the row gains
``agent_key``, ``agent_exact``, ``agent_covered``, ``agent_weight_on_true``,
``agent_flagged`` (+ ``agent_self_flag``, ``agent_family_covered``,
``agent_confidence``); the human fields are never touched. Records marked
``replay: true`` (settled stages re-keyed from frozen morning inputs) are
NOT prospective: they are scored into ``review/agent_replay_scorecard.json``
instead of the tier-3 card, and the paired table shows them flagged.
The paired table applies the Gate K criteria (AGENT_DESIGN §6.2) over
judgment stages (``itt`` excluded).

Evening labels are PROVISIONAL: rider archetypes come from the latest DB
snapshots (pre-race mid-campaign), so items can flip between within-family
twins (res_3/res_7 seen on TdF st17 in validation; macro routes and family
identity are stable). The canonical tier-3 numbers are re-scored after the
race from the rebuilt signature table (label_days) — the stored
top15_shares make that a pure re-read.
Oracle construction (mirrors prediction_tools/day_menu.label_days):
  itt      winning time < labeler.itt_seconds
  bunch    rule_label mass_sprint, or bunch_sprint with wg_prop >= wide_bs_prop
  gc_day   stage winner (or front-5 median) inside morning-GC top gc_top —
           morning GC = the newest standings_*.json archived BEFORE the stage,
           falling back to the newest results/stage_NN/gc.csv (mid-race the
           race page serves only the DNF board, which would otherwise disable
           the gc_day branch outright)
  residual stored-parameter GMM assignment on the realized top-15 archetype
           shares (as-of rider best_profile snapshots from the DB)
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

CAMPAIGN = Path(__file__).resolve().parent
PROJECT_ROOT = CAMPAIGN.parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from cycling_project.prediction_tools.day_menu import (   # noqa: E402
    ARCH,
    assign_residual_items,
    load_menu,
)
from cycling_project.prediction_tools.experiments.front_local_race_typing import (  # noqa: E402
    comp_features,
    rule_label,
)
from cycling_project.db_path import default_db_path
from cycling_project.nightly.day_key_record import (   # noqa: E402
    family_covered,
    score_agent_key,
)

DB_PATH = str(default_db_path())
RESULTS_ROOT = CAMPAIGN / "results"
PREDICTIONS_ROOT = CAMPAIGN / "predictions"
SCORECARD = CAMPAIGN / "review" / "key_scorecard.json"
REPLAY_SCORECARD = CAMPAIGN / "review" / "agent_replay_scorecard.json"
AGENT_FIELDS = ("agent_key", "agent_exact", "agent_covered", "agent_weight_on_true", "agent_flagged",
                "agent_self_flag", "agent_family_covered", "agent_confidence", "agent_replay")


def set_campaign(path) -> Path:
    """Point the module at another campaign directory (``--campaign``; the nightly driver, chip H).

    Every path below is derived from ``CAMPAIGN`` at import time, so re-point
    them together. The DB path is untouched.
    """
    global CAMPAIGN, RESULTS_ROOT, PREDICTIONS_ROOT, SCORECARD, REPLAY_SCORECARD
    CAMPAIGN = Path(path).resolve()
    RESULTS_ROOT = CAMPAIGN / "results"
    PREDICTIONS_ROOT = CAMPAIGN / "predictions"
    SCORECARD = CAMPAIGN / "review" / "key_scorecard.json"
    REPLAY_SCORECARD = CAMPAIGN / "review" / "agent_replay_scorecard.json"
    return CAMPAIGN


def latest_archived_stage() -> int:
    stages = sorted(int(p.name.split("_")[1]) for p in RESULTS_ROOT.glob("stage_*")
                    if (p / "results.json").exists())
    if not stages:
        sys.exit("no archived stages under results/ — run capture_results.py first")
    return stages[-1]


def morning_gc_ranks(stage_results_fetched_at: str, stage: int = None) -> dict:
    """fc_rider_id -> GC place as it stood the morning of this stage.

    Primary source is the newest race-page standings snapshot archived BEFORE
    the stage's results capture. MID-RACE THAT SOURCE IS USUALLY EMPTY: while a
    stage race is running, FirstCycling's race page serves only the DNF board
    (every row place='DNF'), so the digit filter below drops everything and the
    map comes back {}. An empty map silently disables the gc_day branch of the
    oracle entirely — every GC day then falls through to a residual item — so
    when the race page yields nothing we fall back to the per-stage
    ``results/stage_NN/gc.csv``, which is parsed off the STAGE page and is the
    real classification. Walks back from stage-1 to the newest archived one,
    the same way build_stage_page.standings_pool_ids does.
    """
    def _from_race_page():
        race_page = RESULTS_ROOT / "race_page"
        cutoff = stage_results_fetched_at[:10]
        cands = sorted(race_page.glob("standings_*.json"))
        prior = [p for p in cands if p.stem.split("_")[1] < cutoff]
        if not prior:
            return {}
        snap = json.loads(prior[-1].read_text())
        out = {}
        for r in snap.get("results", []):
            place = str(r.get("place", "")).strip()
            if place.isdigit():
                out[str(r.get("rider_id"))] = int(place)
        return out

    def _from_stage_gc():
        if stage is None:
            return {}
        import csv as _csv
        for nn in range(int(stage) - 1, 0, -1):
            f = RESULTS_ROOT / f"stage_{nn:02d}" / "gc.csv"
            if not f.exists():
                continue
            out = {}
            with f.open() as fh:
                for r in _csv.DictReader(fh):
                    place = str(r.get("place", "")).strip()
                    if place.isdigit():
                        out[str(r.get("rider_id"))] = int(place)
            if out:
                return out
        return {}

    return _from_race_page() or _from_stage_gc()


def rider_profiles(fc_ids: list) -> dict:
    """fc_rider_id -> as-of best_profile (latest snapshot per rider; mid-race
    these are the pre-race snapshots, matching the labeler's as-of-then
    discipline)."""
    con = sqlite3.connect(DB_PATH)
    con.execute("CREATE TEMP TABLE want(fc_id TEXT PRIMARY KEY)")
    con.executemany("INSERT OR IGNORE INTO want VALUES (?)",
                    [(str(i),) for i in fc_ids])
    rows = con.execute("""
        SELECT r.fc_rider_id, s.best_profile
        FROM riders r
        JOIN want w ON w.fc_id = CAST(r.fc_rider_id AS TEXT)
        JOIN rider_competition_snapshots s ON s.rider_id = r.id
        JOIN (SELECT rider_id, MAX(competition_id) AS mc
              FROM rider_competition_snapshots GROUP BY rider_id) latest
          ON latest.rider_id = s.rider_id AND latest.mc = s.competition_id
    """).fetchall()
    con.close()
    return {str(fc): (bp or "unknown") for fc, bp in rows}


def oracle_item(stage: int, menu) -> dict:
    d = json.loads((RESULTS_ROOT / f"stage_{stage:02d}" / "results.json").read_text())
    rows = [r for r in d["results"]
            if str(r.get("place", "")).strip().isdigit()]
    rows.sort(key=lambda r: int(r["place"]))
    gaps = np.array([r["gap"] for r in rows
                     if isinstance(r.get("gap"), (int, float))], dtype=float)
    gaps = np.sort(gaps) - gaps.min()
    feats = comp_features(gaps)
    rule = rule_label(feats)
    winning_time = d.get("race_time")

    profiles = rider_profiles([r["rider_id"] for r in rows[:15]])
    top15 = [profiles.get(str(r["rider_id"]), "unknown") for r in rows[:15]]
    shares_all = {a: top15.count(a) / len(top15) for a in set(top15)}
    shares6 = np.array([[shares_all.get(a, 0.0) for a in ARCH]])

    cfg = menu.labeler
    gc = morning_gc_ranks(d.get("fetched_at", ""), stage)
    winner_gc = gc.get(str(rows[0]["rider_id"])) if rows else None
    front5 = [gc.get(str(r["rider_id"])) for r in rows[:5]]
    front5 = [g for g in front5 if g is not None]
    front5_med = float(np.median(front5)) if front5 else None

    if winning_time is not None and winning_time < cfg["itt_seconds"]:
        item, day_class = "itt", "itt"
    elif rule == "mass_sprint" or (rule == "bunch_sprint"
                                   and feats["wg_prop"] >= cfg["wide_bs_prop"]):
        item, day_class = "bunch", "bunch"
    elif ((winner_gc is not None and winner_gc <= cfg["gc_top"])
          or (front5_med is not None and front5_med <= cfg["gc_top"])):
        item, day_class = "gc_day", "gc_day"
    else:
        item = assign_residual_items(shares6, menu)[0]
        day_class = "residual"

    return {
        "stage": stage,
        "oracle_item": item,
        "day_class": day_class,
        "rule_type": rule,
        "wg_size": int(feats["wg_size"]),
        "wg_prop": round(float(feats["wg_prop"]), 4),
        "winning_time": winning_time,
        "winner": rows[0]["name"] if rows else None,
        "winner_gc_morning": winner_gc,
        "front5_gc_median": front5_med,
        "top15_shares": {a: round(shares_all.get(a, 0.0), 3) for a in ARCH},
        "top15_unknown": round(shares_all.get("unknown", 0.0), 3),
    }


def logged_key(stage: int) -> dict | None:
    cfg_path = PREDICTIONS_ROOT / f"stage_{stage:02d}" / "scenarios.json"
    if not cfg_path.exists():
        return None
    cfg = json.loads(cfg_path.read_text())
    if cfg.get("post_hoc"):
        # Config written AFTER the stage (a missed-day backfill). It contains
        # no morning read, and the scenario-level fallback below would happily
        # promote a hindsight scenario's day_key into the tier-3 archive as if
        # it had been logged in advance — scoring a fabricated exact. A
        # post_hoc config is never a logged key.
        return None
    if cfg.get("day_key_author") == "agent":
        # Shadow mode (nightly driver --agent-key): the board was priced under
        # the agent's key so the preview could run, but no human read was
        # logged. The tier-3 card stays unkeyed; the agent record is scored
        # through --also agent from agent_key.json, never from here.
        return None
    key = cfg.get("day_key")
    if key is None:
        for spec in cfg.get("scenarios", {}).values():
            if spec.get("day_key"):
                return {"day_key": spec["day_key"],
                        "source": f"scenario:{spec.get('tag')}"}
        return None
    return {"day_key": key, "source": "config-root"}


def score(oracle: dict, logged: dict | None) -> dict:
    row = dict(oracle)
    if logged is None:
        row.update({"day_key": None, "exact": None, "covered": None,
                    "weight_on_true": None, "key_source": None})
        return row
    key = {k: float(v) for k, v in logged["day_key"].items()}
    tot = sum(key.values()) or 1.0
    key = {k: v / tot for k, v in key.items()}
    top_item = max(key, key=key.get)
    row.update({
        "day_key": key,
        "key_source": logged["source"],
        "exact": top_item == oracle["oracle_item"],
        "covered": oracle["oracle_item"] in key,
        "weight_on_true": round(key.get(oracle["oracle_item"], 0.0), 3),
    })
    return row


def agent_record(stage: int) -> dict | None:
    p = PREDICTIONS_ROOT / f"stage_{stage:02d}" / "agent_key.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return None


def attach_agent(row: dict, record: dict | None) -> dict:
    """Return a copy of ``row`` with the agent_* fields (human fields untouched)."""
    out = dict(row)
    out.update(score_agent_key(record, row["oracle_item"]))
    out["agent_scored_at"] = datetime.now().isoformat()
    return out


def write_agent_score(row: dict, record: dict | None, card: list) -> list:
    """Prospective records land on the tier-3 row; replay records go to the
    separate replay card so the archive stays prospective-only."""
    if record is None:
        return card
    scored = attach_agent(row, record)
    if scored["agent_replay"]:
        rep = json.loads(REPLAY_SCORECARD.read_text()) if REPLAY_SCORECARD.exists() else []
        rep = [r for r in rep if r["stage"] != row["stage"]] + [
            {k: scored.get(k) for k in ("stage", "oracle_item", "day_class", "day_key", "exact", "covered",
                                        "weight_on_true", *AGENT_FIELDS, "agent_scored_at")}]
        rep.sort(key=lambda r: r["stage"])
        REPLAY_SCORECARD.write_text(json.dumps(rep, indent=1))
        return card
    return [r for r in card if r["stage"] != row["stage"]] + [scored]


def paired_rows(card: list) -> list:
    """Every stage with both a human key and an agent key, prospective rows
    from the tier-3 card and replay rows from the replay card."""
    rows = {r["stage"]: r for r in card if r.get("agent_key")}
    if REPLAY_SCORECARD.exists():
        for r in json.loads(REPLAY_SCORECARD.read_text()):
            rows.setdefault(r["stage"], r)
    return [rows[s] for s in sorted(rows)]


def _fmt_key(key: dict | None) -> str:
    if not key:
        return "-"
    return " ".join(f"{k}:{v:.2f}" for k, v in sorted(key.items(), key=lambda kv: -kv[1]))


def _fmt_bool(v) -> str:
    return "-" if v is None else ("Y" if v else "n")


def print_paired_table(card: list) -> None:
    rows = paired_rows(card)
    if not rows:
        print("\nno stage carries both a human key and an agent key yet")
        return
    print("\npaired human vs agent keys (Gate K population = judgment stages, itt excluded; R = replay, not prospective)")
    hdr = f"{'st':>3} {'oracle':<7} {'human key':<28} {'ex':>2} {'cov':>3} {'wt':>4} | {'agent key':<28} {'ex':>2} {'cov':>3} {'wt':>4} {'flag':>4} {'conf':>4} R"
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        print(f"{r['stage']:>3} {str(r.get('oracle_item')):<7} {_fmt_key(r.get('day_key')):<28} "
              f"{_fmt_bool(r.get('exact')):>2} {_fmt_bool(r.get('covered')):>3} "
              f"{(r.get('weight_on_true') if r.get('weight_on_true') is not None else 0):>4.2f} | "
              f"{_fmt_key(r.get('agent_key')):<28} {_fmt_bool(r.get('agent_exact')):>2} "
              f"{_fmt_bool(r.get('agent_covered')):>3} {(r.get('agent_weight_on_true') or 0):>4.2f} "
              f"{_fmt_bool(r.get('agent_flagged')):>4} {(r.get('agent_confidence') or 0):>4.2f} "
              f"{'R' if r.get('agent_replay') else ' '}")

    for label, subset in (("prospective", [r for r in rows if not r.get("agent_replay")]),
                          ("replay", [r for r in rows if r.get("agent_replay")])):
        judged = [r for r in subset if r.get("oracle_item") != "itt" and r.get("exact") is not None
                  and r.get("agent_exact") is not None]
        if not judged:
            continue
        n = len(judged)
        h_cov = sum(bool(r["covered"]) for r in judged) / n
        a_cov = sum(bool(r["agent_covered"]) for r in judged) / n
        h_wt = float(np.mean([r["weight_on_true"] for r in judged]))
        a_wt = float(np.mean([r["agent_weight_on_true"] for r in judged]))
        h_ex = sum(bool(r["exact"]) for r in judged)
        a_ex = sum(bool(r["agent_exact"]) for r in judged)
        regressions = [r["stage"] for r in judged
                       if family_covered(r.get("day_key"), r["oracle_item"])
                       and not r.get("agent_family_covered")]
        unflagged_wrong = [r["stage"] for r in judged if not r["agent_exact"] and not r.get("agent_flagged")]
        flagged_wrong = [r["stage"] for r in judged if not r["agent_exact"] and r.get("agent_flagged")]
        print(f"\nGate K ({label}, {n} judgment stages):")
        print(f"  1 covered      human {h_cov:.2f}  agent {a_cov:.2f}  -> {'PASS' if a_cov >= h_cov else 'FAIL'}")
        print(f"  2 weight_true  human {h_wt:.2f}  agent {a_wt:.2f}  -> {'PASS' if a_wt >= h_wt - 0.03 else 'FAIL'}")
        print(f"  3 family regressions (human covered family, agent missed it): {regressions or 'none'} "
              f"-> {'PASS' if not regressions else 'FAIL'}")
        print(f"  5 self-flagging: agent wrong+unflagged {unflagged_wrong or 'none'}; wrong+flagged {flagged_wrong or 'none'}")
        print(f"  exact          human {h_ex}/{n}  agent {a_ex}/{n}   (diagnostic)")
        print("  4 retrieval neutrality: not measured here (needs the retrieval ledger under agent keys)")
        print(f"  sample size: {n} of >= 30 stages across >= 3 races required before promotion")


def agent_refresh() -> list:
    """Re-attach agent fields to every stage with an agent_key.json using the
    stored oracle rows (no DB, no re-labelling)."""
    card = json.loads(SCORECARD.read_text()) if SCORECARD.exists() else []
    for row in list(card):
        record = agent_record(row["stage"])
        if record is None:
            continue
        card = write_agent_score(row, record, card)
    card.sort(key=lambda r: r["stage"])
    SCORECARD.write_text(json.dumps(card, indent=1))
    return card


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--campaign", default=None,
                    help="campaign directory (default: this script's own, performance_eval/vuelta-2026)")
    ap.add_argument("--stage", type=int, default=None)
    ap.add_argument("--also", choices=["agent"], default=None,
                    help="also score predictions/stage_NN/agent_key.json into the row (paired table)")
    ap.add_argument("--agent-refresh", action="store_true",
                    help="re-attach every agent key from stored oracle rows and print the paired table (no DB)")
    args = ap.parse_args()
    if args.campaign:
        set_campaign(args.campaign)
    if args.agent_refresh:
        print_paired_table(agent_refresh())
        return
    stage = args.stage or latest_archived_stage()

    menu = load_menu()
    row = score(oracle_item(stage, menu), logged_key(stage))
    row["scored_at"] = datetime.now().isoformat()

    SCORECARD.parent.mkdir(parents=True, exist_ok=True)
    card = json.loads(SCORECARD.read_text()) if SCORECARD.exists() else []
    prior = next((r for r in card if r["stage"] == stage), {})
    # never drop agent fields already on the row when re-scoring the human key
    row = {**{k: prior[k] for k in (*AGENT_FIELDS, "agent_scored_at") if k in prior}, **row}
    card = [r for r in card if r["stage"] != stage] + [row]
    if args.also == "agent":
        record = agent_record(stage)
        if record is None:
            print(f"  --also agent: no predictions/stage_{stage:02d}/agent_key.json")
        else:
            card = write_agent_score(row, record, card)
            row = next(r for r in card if r["stage"] == stage) if not record.get("replay") else attach_agent(row, record)
    card.sort(key=lambda r: r["stage"])
    SCORECARD.write_text(json.dumps(card, indent=1))

    print(f"stage {stage}: oracle={row['oracle_item']} ({row['day_class']}, "
          f"rule={row['rule_type']}, wg={row['wg_size']}, "
          f"wt={row['winning_time']})")
    if row["day_key"] is None:
        print("  no day_key logged for this stage")
    else:
        print(f"  read: {row['day_key']} ({row['key_source']})")
        print(f"  exact={row['exact']} covered={row['covered']} "
              f"weight_on_true={row['weight_on_true']}")

    scored = [r for r in card if r.get("exact") is not None]
    if scored:
        print(f"\nrunning tier-3 accuracy over {len(scored)} keyed stages: "
              f"exact {sum(r['exact'] for r in scored)}/{len(scored)}, "
              f"covered {sum(r['covered'] for r in scored)}/{len(scored)}, "
              f"mean weight_on_true "
              f"{np.mean([r['weight_on_true'] for r in scored]):.2f}")
    if args.also == "agent":
        if row.get("agent_key") is not None:
            print(f"  agent: {row['agent_key']} exact={row['agent_exact']} covered={row['agent_covered']} "
                  f"weight_on_true={row['agent_weight_on_true']} flagged={row['agent_flagged']}"
                  + (" [REPLAY — not in the tier-3 card]" if row.get("agent_replay") else ""))
        print_paired_table(card)


if __name__ == "__main__":
    main()
