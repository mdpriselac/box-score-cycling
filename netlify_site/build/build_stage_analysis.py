"""
Compute extra pre-stage analysis blocks and write them into a stage's
scenarios.json (config["analysis"]), where build_stage_page.py renders them.

    python3 netlify_site/build/build_stage_analysis.py \
        performance_eval/tour-de-france-2026/predictions/stage_03/scenarios.json \
        [--break-scenario healy_carapaz] [--gc-exclude 24] [--book-top 10]

Three blocks (third only when the config carries a "punchy_filter"):

1. "If the break goes" — remove the top N riders by the latest GC-model
   blend (GC captains won't be given freedom / won't be let up the road),
   then renormalize the break-read scenario's win probabilities over the
   remaining pool: P(win | winner is not a GC favourite).
2. "The book's card" — the top book favourites for the stage, with our
   blend and rank under every scenario, flagging which of them are inside
   the GC-favourite pool.
3. "The punchy pool" — the stage-4 lesson as a filter. No terrain reading
   means "selective enough to drop the pure sprinters but won by a fast
   hard-man", so we synthesize it: drop the GC pool AND the pure sprinters,
   then renormalize each visible reading over the survivors. Pure sprinter
   is model-defined via the hidden flat-sprint anchor scenario: a rider with
   anchor probability >= anchor_floor whose selective-read probability
   retains < retention_max of the anchor (punchy fast-men like Pedersen
   retain; pure sprinters like Merlier collapse).

   config["punchy_filter"] = {"sprint_anchor": key, "selective_scenario": key,
                              "anchor_floor": 0.01, "retention_max": 0.12}

Scenarios flagged "hidden": true never appear as table columns; they are
classification inputs only. Rerun any time inputs change (idempotent —
blocks are replaced by title).
"""

import argparse
import csv
import json
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PREDICTIONS_ROOT = (PROJECT_ROOT / "performance_eval" / "tour-de-france-2026"
                    / "predictions")
RESULTS_ROOT = (PROJECT_ROOT / "performance_eval" / "tour-de-france-2026"
                / "results")
DB_PATH = (PROJECT_ROOT / "cycling_project" / "webscrape_tools" / "database"
           / "database" / "cycling_races.db")


def fc_to_internal_ids(fc_ids):
    """{fc_rider_id: internal riders.id} — the stable join between archived
    FirstCycling results (gc.csv) and prediction JSONs; rider NAMES drift on
    FirstCycling mid-career (Gee -> Gee-West, Martin -> Martin-Guyonnet)."""
    fc_ids = [str(f) for f in fc_ids if f]
    if not fc_ids or not DB_PATH.exists():
        return {}
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            f"SELECT fc_rider_id, id FROM riders WHERE fc_rider_id IN "
            f"({','.join('?' for _ in fc_ids)})", fc_ids).fetchall()
    return {str(fc): int(i) for fc, i in rows}


def norm(s):
    return " ".join(sorted(s.lower().replace("-", " ").split()))


def latest_gc_riders():
    gc_dir = PREDICTIONS_ROOT / "gc"
    preds = [p for p in gc_dir.glob("*.json") if p.name != "scenarios.json"]
    if not preds:
        raise SystemExit("No GC prediction JSON found — run the gc config first.")
    f = max(preds, key=lambda p: p.stat().st_mtime)
    return json.loads(f.read_text())["riders"], f.name


def standings_gc_pool(stage, n, field_riders):
    """Actual-standings pool: internal ids + GC ranks of the riders on GC
    before this stage, from the newest archived results/stage_NN/gc.csv
    (NN < stage). The top-n are the riders still close enough that a break
    containing them gets chased. Rows are joined on fc_rider_id (names drift
    on FirstCycling), with normalized-name fallback."""
    by_name = {norm(r["rider_name"]): int(r["rider_id"]) for r in field_riders}
    for nn in range(int(stage) - 1, 0, -1):
        f = RESULTS_ROOT / f"stage_{nn:02d}" / "gc.csv"
        if not f.exists():
            continue
        rows = list(csv.DictReader(f.open()))
        by_fc = fc_to_internal_ids(r.get("rider_id") for r in rows)
        ids, rank, missing = set(), {}, []
        for i, row in enumerate(rows, 1):
            rid = (by_fc.get(str(row.get("rider_id") or ""))
                   or by_name.get(norm(row["name"])))
            if rid is None:
                if i <= n:
                    missing.append(row["name"])
                continue
            rank[rid] = i
            if i <= n:
                ids.add(rid)
        if missing:
            print(f"  WARNING: GC top-{n} riders not matched to the field: "
                  f"{', '.join(missing)}")
        return frozenset(ids), rank, nn
    raise SystemExit(f"exclude_gc_source=standings but no results/stage_NN/"
                     f"gc.csv archived before stage {stage}")


def fmt_pct(v, d=1):
    return f"{100*v:.{d}f}%" if v is not None else "–"


def classify_sprinters(config, scen):
    """Model-defined pure sprinters, via the config's punchy_filter.

    A rider is a pure sprinter if he has real speed on a flat-sprint anchor
    (blend >= anchor_floor) but keeps under retention_max of it once the road
    turns selective — the collapse that separates a Merlier from a Pedersen.
    Returns (sprinter_ids, names). Empty when no punchy_filter is configured.
    """
    pf = config.get("punchy_filter")
    if not pf:
        return set(), {}
    anchor_key = pf["sprint_anchor"]
    sel_key = pf["selective_scenario"]
    for k in (anchor_key, sel_key):
        if k not in scen:
            raise SystemExit(f"punchy_filter scenario '{k}' has no prediction "
                             f"JSON — run it with --only {k} --no-log")
    floor = pf.get("anchor_floor", 0.01)
    ret_max = pf.get("retention_max", 0.12)
    anchor_p = {int(r["rider_id"]): (r.get("blend_win_p") or 0)
                for r in scen[anchor_key]["riders"]}
    sel_p = {int(r["rider_id"]): (r.get("blend_win_p") or 0)
             for r in scen[sel_key]["riders"]}
    names = {int(r["rider_id"]): r["rider_name"]
             for r in scen[anchor_key]["riders"]}

    print(f"\npunchy-filter diagnostics (anchor={anchor_key}, "
          f"selective={sel_key}, floor={floor}, retention_max={ret_max}):")
    sprinter_ids = set()
    for rid, a in sorted(anchor_p.items(), key=lambda kv: -kv[1]):
        if a < floor:
            continue
        ret = sel_p.get(rid, 0) / a
        if ret < ret_max:
            sprinter_ids.add(rid)
        print(f"  {names[rid]:<24} anchor {100*a:5.1f}%  retention {ret:5.2f}  "
              f"{'PURE SPRINTER' if ret < ret_max else 'punchy fast-man'}")
    return sprinter_ids, names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("--break-scenario", default=None,
                    help="scenario key for the break read (default: first)")
    ap.add_argument("--gc-exclude", type=int, default=None,
                    help="exclude this many top GC-model riders from the pool "
                         "(default: the break scenario's exclude_top_gc, else 24)")
    ap.add_argument("--book-top", type=int, default=10)
    args = ap.parse_args()

    config_path = Path(args.config).resolve()
    config = json.loads(config_path.read_text())
    scen = {}
    for key in config["scenarios"]:
        f = config_path.parent / f"{key}.json"
        if f.exists():
            scen[key] = json.loads(f.read_text())
    if not scen:
        raise SystemExit("No scenario JSONs found — run predictions first.")
    # hidden scenarios (classification anchors) never appear as table columns
    vis = {k: v for k, v in scen.items()
           if not config["scenarios"][k].get("hidden")}

    break_key = args.break_scenario or next(iter(vis))
    if break_key not in scen:
        raise SystemExit(f"scenario '{break_key}' not found")

    gc_exclude = (args.gc_exclude if args.gc_exclude is not None
                  else config["scenarios"][break_key].get("exclude_top_gc") or 24)

    if config["scenarios"][break_key].get("exclude_gc_source") == "standings":
        gc_pool_ids, gc_rank, gc_stage = standings_gc_pool(
            config["stage"], gc_exclude, scen[break_key]["riders"])
        pool_desc = f"top {gc_exclude} on GC after stage {gc_stage}"
        pool_reason = ("everyone below that is far enough back to be "
                       "given freedom")
    else:
        gc_riders, gc_file = latest_gc_riders()
        gc_sorted = sorted(gc_riders, key=lambda r: -(r.get("blend_win_p") or 0))
        gc_pool_ids = {int(r["rider_id"]) for r in gc_sorted[:gc_exclude]}
        gc_rank = {int(r["rider_id"]): i + 1 for i, r in enumerate(gc_sorted)}
        pool_desc = f"top {gc_exclude} by the latest GC-model blend ({gc_file})"
        pool_reason = "captains don't get in the break"

    # pure-sprinter classification — shared by block 1 (flat days, where the
    # men who beat a break are the sprinters, not the GC pool) and block 3.
    sprinter_ids, sprinter_names = classify_sprinters(config, scen)

    # ── block 1: if the break goes ──
    # On a hard day the pool that gets freedom = field minus the GC captains.
    # On a FLAT day the GC pool is a near-no-op (sprinters sit ~130th on GC and
    # the captains aren't winning a gallop anyway) — there the break has to beat
    # the sprinters, so the break scenario can set "exclude_sprinters": true and
    # the pool drops them too.
    drop_sprinters = bool(config["scenarios"][break_key].get("exclude_sprinters"))
    if drop_sprinters and not sprinter_ids:
        raise SystemExit(f"'{break_key}' sets exclude_sprinters but the "
                         f"punchy_filter classified nobody — check the config")
    excluded1 = gc_pool_ids | (sprinter_ids if drop_sprinters else set())
    bs = scen[break_key]["riders"]
    pool = [r for r in bs if int(r["rider_id"]) not in excluded1]
    pool_mass = sum(r.get("blend_win_p") or 0 for r in pool)
    pool_sorted = sorted(pool, key=lambda r: -(r.get("blend_win_p") or 0))
    rows1 = []
    for r in pool_sorted[:14]:
        p = r.get("blend_win_p") or 0
        rows1.append([
            r["rider_name"], r.get("team_name") or "",
            fmt_pct(p), fmt_pct(p / pool_mass if pool_mass else None),
            f"{r['book_odds']:.0f}" if r.get("book_odds") else "n/a",
            fmt_pct(r.get("book_devig")),
        ])
    short = config["scenarios"][break_key].get("short", break_key)
    if drop_sprinters:
        gone = ", ".join(sorted(sprinter_names[i] for i in sprinter_ids))
        block1 = {
            "title": "If the break goes — the field with the sprinters and the GC pool removed",
            "note": (f"On a flat day the escape has to beat the fast men home, "
                     f"so the pool that can win from it is the field minus every "
                     f"pure sprinter and minus the {pool_desc}. Pure sprinter is "
                     f"the model's own verdict, not a hand list: real speed on a "
                     f"flat-sprint anchor of this exact field, but collapsing to "
                     f"a fraction of it once the road turns selective — that "
                     f"collapse is what separates a Merlier from a Pedersen. "
                     f"Classified out: {gone}. The conditional column "
                     f"renormalizes the survivors' win probability under the "
                     f"'{short}' read over this pool (P(win | the break wins); "
                     f"the pool holds {100*pool_mass:.0f}% of the unconditional "
                     f"book). The model cannot see who actually gets up the road "
                     f"— read this as a fitness-for-the-day ranking, not "
                     f"break-formation odds."),
            "columns": ["Rider", "Team", f"{short} win p", "P(win | break wins)",
                        "Book odds", "Book devig"],
            "rows": rows1,
        }
    else:
        block1 = {
            "title": "If the break goes — competitive riders outside the GC pool",
            "note": (f"The {pool_desc} removed — {pool_reason}. "
                     f"Remaining riders under the '{short}' read; the conditional "
                     f"column renormalizes their win probability over this pool "
                     f"(P(win | a non-GC rider wins), pool holds "
                     f"{100*pool_mass:.0f}% of the unconditional book). The model "
                     f"can't see who actually makes the break — read this as a "
                     f"fitness-for-the-day ranking, not break-formation odds."),
            "columns": ["Rider", "Team", f"{short} win p", "P(win | break wins)",
                        "Book odds", "Book devig"],
            "rows": rows1,
        }

    # ── block 2: the book's card ──
    any_riders = next(iter(vis.values()))["riders"]
    priced = [r for r in any_riders if r.get("book_odds")]
    book_sorted = sorted(priced, key=lambda r: r["book_odds"])[:args.book_top]
    by_id = {k: {int(r["rider_id"]): r for r in d["riders"]}
             for k, d in vis.items()}
    keys = list(vis.keys())

    def scen_rank(key, rid):
        rs = sorted(scen[key]["riders"], key=lambda r: -(r.get("blend_win_p") or 0))
        for i, r in enumerate(rs):
            if int(r["rider_id"]) == rid:
                return i + 1
        return None

    rows2 = []
    for r in book_sorted:
        rid = int(r["rider_id"])
        cells = [r["rider_name"],
                 f"{r['book_odds']:.2f}", fmt_pct(r.get("book_devig"))]
        for k in keys:
            m = by_id[k].get(rid)
            rk = scen_rank(k, rid)
            cells.append(f"{fmt_pct(m.get('blend_win_p')) if m else '–'}"
                         f" (#{rk})" if rk else "–")
        cells.append(f"GC #{gc_rank[rid]}" if rid in gc_pool_ids else "free")
        rows2.append(cells)
    block2 = {
        "title": "The book's card — its favourites under our readings",
        "note": ("Shortest book prices for the stage, with our blend win "
                 "probability (and rank) under each scenario. 'free' = outside "
                 f"the excluded GC pool ({pool_desc}), i.e. the type the "
                 "peloton might let up the road."),
        "columns": (["Rider", "Book odds", "Devig"]
                    + [config["scenarios"][k].get("short", k) for k in keys]
                    + ["GC status"]),
        "rows": rows2,
    }

    # ── block 3: the punchy pool (GC captains AND pure sprinters removed) ──
    # Skipped when the config sets punchy_filter.emit_pool = false — on a flat
    # day block 1 already IS the sprinters-removed pool, and a second copy of it
    # under the "punchy non-climber" framing would just be wrong prose.
    blocks = [block1, block2]
    pf = config.get("punchy_filter")
    if pf and pf.get("emit_pool", True):
        floor = pf.get("anchor_floor", 0.01)
        ret_max = pf.get("retention_max", 0.12)
        sel_key = pf["selective_scenario"]
        names = sprinter_names
        excluded = gc_pool_ids | sprinter_ids
        vk = list(vis.keys())
        pools = {}
        for k in vk:
            kept = [r for r in vis[k]["riders"]
                    if int(r["rider_id"]) not in excluded]
            mass = sum(r.get("blend_win_p") or 0 for r in kept) or 1.0
            pools[k] = ({int(r["rider_id"]): (r.get("blend_win_p") or 0) / mass
                         for r in kept}, mass)
        pool_riders = {int(r["rider_id"]): r for k in vk for r in vis[k]["riders"]
                       if int(r["rider_id"]) not in excluded}

        def pool_max(rid):
            return max(pools[k][0].get(rid, 0) for k in vk)
        ranked = sorted(pool_riders, key=pool_max, reverse=True)
        rows3 = []
        for rid in ranked[:16]:
            r = pool_riders[rid]
            rows3.append(
                [r["rider_name"], r.get("team_name") or ""]
                + [fmt_pct(pools[k][0].get(rid)) for k in vk]
                + [f"{r['book_odds']:.0f}" if r.get("book_odds") else "n/a",
                   fmt_pct(r.get("book_devig"))])
        classified_out = ", ".join(sorted(names[i] for i in sprinter_ids))
        masses = " / ".join(
            f"{config['scenarios'][k].get('short', k)} {100*pools[k][1]:.0f}%"
            for k in vk)
        block3 = {
            "title": "The punchy pool — the field with GC captains and pure sprinters removed",
            "note": (f"The stage-4 lesson as a filter: no terrain reading means "
                     f"'selective enough to shed the fast finishers but won by a "
                     f"punchy non-climber', so this table synthesizes it. We drop "
                     f"the GC pool ({pool_desc}) and every pure "
                     f"sprinter, then renormalize each reading over the survivors "
                     f"— P(win | the winner is a punchy non-climber). Pure "
                     f"sprinter is the model's own verdict, not a hand list: "
                     f"probability under a flat-sprint anchor of this exact field "
                     f">= {100*floor:.0f}% while retaining under {100*ret_max:.0f}% "
                     f"of it when the day turns selective ('{sel_key}' read) — "
                     f"that collapse is what separates a Merlier from a Pedersen. "
                     f"Classified out: {classified_out}. Pool holds {masses} of "
                     f"each reading's unconditional book."),
            "columns": (["Rider", "Team"]
                        + [f"P(win | pool) {config['scenarios'][k].get('short', k)}"
                           for k in vk]
                        + ["Book odds", "Book devig"]),
            "rows": rows3,
        }
        blocks.append(block3)

    titles = {b["title"] for b in blocks}
    existing = [b for b in config.get("analysis", []) if b["title"] not in titles]
    config["analysis"] = existing + blocks
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n")
    print(f"\nWrote {len(blocks)} analysis blocks into {config_path.name} "
          f"(pool mass {100*pool_mass:.1f}%, excluded {len(gc_pool_ids)} GC riders)")
    for r in rows1[:8]:
        print("  break-pool:", r[0], r[2], "->", r[3], "| book", r[4])


if __name__ == "__main__":
    main()
