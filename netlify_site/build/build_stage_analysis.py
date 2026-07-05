"""
Compute extra pre-stage analysis blocks and write them into a stage's
scenarios.json (config["analysis"]), where build_stage_page.py renders them.

    python3 netlify_site/build/build_stage_analysis.py \
        performance_eval/tour-de-france-2026/predictions/stage_03/scenarios.json \
        [--break-scenario healy_carapaz] [--gc-exclude 24] [--book-top 10]

Two blocks:

1. "If the break goes" — remove the top N riders by the latest GC-model
   blend (GC captains won't be given freedom / won't be let up the road),
   then renormalize the break-read scenario's win probabilities over the
   remaining pool: P(win | winner is not a GC favourite).
2. "The book's card" — the top book favourites for the stage, with our
   blend and rank under every scenario, flagging which of them are inside
   the GC-favourite pool.

Rerun any time inputs change (idempotent — blocks are replaced by title).
"""

import argparse
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PREDICTIONS_ROOT = (PROJECT_ROOT / "performance_eval" / "tour-de-france-2026"
                    / "predictions")


def norm(s):
    return " ".join(sorted(s.lower().replace("-", " ").split()))


def latest_gc_riders():
    gc_dir = PREDICTIONS_ROOT / "gc"
    preds = [p for p in gc_dir.glob("*.json") if p.name != "scenarios.json"]
    if not preds:
        raise SystemExit("No GC prediction JSON found — run the gc config first.")
    f = max(preds, key=lambda p: p.stat().st_mtime)
    return json.loads(f.read_text())["riders"], f.name


def fmt_pct(v, d=1):
    return f"{100*v:.{d}f}%" if v is not None else "–"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("--break-scenario", default=None,
                    help="scenario key for the break read (default: first)")
    ap.add_argument("--gc-exclude", type=int, default=24,
                    help="exclude this many top GC-model riders from the pool")
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

    break_key = args.break_scenario or next(iter(scen))
    if break_key not in scen:
        raise SystemExit(f"scenario '{break_key}' not found")

    gc_riders, gc_file = latest_gc_riders()
    gc_sorted = sorted(gc_riders, key=lambda r: -(r.get("blend_win_p") or 0))
    gc_pool_ids = {int(r["rider_id"]) for r in gc_sorted[:args.gc_exclude]}
    gc_rank = {int(r["rider_id"]): i + 1 for i, r in enumerate(gc_sorted)}

    # ── block 1: if the break goes ──
    bs = scen[break_key]["riders"]
    pool = [r for r in bs if int(r["rider_id"]) not in gc_pool_ids]
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
    block1 = {
        "title": "If the break goes — competitive riders outside the GC pool",
        "note": (f"Top {args.gc_exclude} riders by the latest GC-model blend "
                 f"({gc_file}) removed — captains don't get in the break. "
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
    any_riders = next(iter(scen.values()))["riders"]
    priced = [r for r in any_riders if r.get("book_odds")]
    book_sorted = sorted(priced, key=lambda r: r["book_odds"])[:args.book_top]
    by_id = {k: {int(r["rider_id"]): r for r in d["riders"]}
             for k, d in scen.items()}
    keys = list(scen.keys())

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
                 f"our top-{args.gc_exclude} GC pool, i.e. the type the "
                 "peloton might let up the road."),
        "columns": (["Rider", "Book odds", "Devig"]
                    + [config["scenarios"][k].get("short", k) for k in keys]
                    + ["GC status"]),
        "rows": rows2,
    }

    existing = [b for b in config.get("analysis", [])
                if b["title"] not in (block1["title"], block2["title"])]
    config["analysis"] = existing + [block1, block2]
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote 2 analysis blocks into {config_path.name} "
          f"(pool mass {100*pool_mass:.1f}%, excluded {len(gc_pool_ids)} GC riders)")
    for r in rows1[:8]:
        print("  break-pool:", r[0], r[2], "->", r[3], "| book", r[4])


if __name__ == "__main__":
    main()
