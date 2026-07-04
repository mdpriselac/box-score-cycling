"""
Capture Kambi (Unibet NL) TdF 2026 odds, save snapshots to performance_eval/,
and build the model-vs-book comparison JSON for the artifact page.
"""

import csv
import json
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

SCRATCH = Path(__file__).parent
OUT_DIR = Path(__file__).resolve().parents[2] / "performance_eval/tour-de-france-2026"
OUT_DIR.mkdir(parents=True, exist_ok=True)
STAMP = "2026-07-03"

EVENTS = {
    1028200241: "stage1_ttt",
    1024452735: "gc",
    1028202586: "stage_win_specials",
    1028200307: "teams_classification",
    1028200306: "mountains_classification",
    1028200309: "youth_classification",
    1028200308: "points_classification",
}

def norm_name(s):
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("'", "").replace("-", " ").replace(".", " ")
    return " ".join(sorted(s.split()))

def outcomes(bo):
    out = []
    for o in bo.get("outcomes", []):
        odds = o.get("odds")
        if odds is None:
            continue
        out.append({
            "name": o.get("participant") or o.get("label"),
            "label": o.get("label"),
            "odds": odds / 1000.0,
            "implied": 1000.0 / odds,
        })
    return out

def devig(rows, book_sum=1.0):
    s = sum(r["implied"] for r in rows)
    for r in rows:
        r["devig"] = r["implied"] / s * book_sum
    return s

# ---- load raw captures ----
raw = {name: json.loads((SCRATCH / f"kambi_{eid}.json").read_text())
       for eid, name in EVENTS.items()}

markets = {}
prov = {"source": "Kambi CDN (Unibet NL feed), eu-offering-api.kambicdn.com, brand=ubnl",
        "fetched_at": STAMP + " (Europe run, pre-race -1 day)",
        "events": {str(k): v for k, v in EVENTS.items()}, "overrounds": {}}

def grab(event, bo_id, key, book_sum=1.0):
    for bo in raw[event]["betOffers"]:
        if bo["id"] == bo_id:
            rows = outcomes(bo)
            over = devig(rows, book_sum)
            markets[key] = rows
            prov["overrounds"][key] = round(over / book_sum, 4)
            return
    raise SystemExit(f"betoffer {bo_id} not found in {event}")

grab("gc", 2539893847, "gc_win")
grab("gc", 2658783491, "gc_podium", book_sum=3.0)
grab("gc", 2664634959, "gc_top6", book_sum=6.0)
grab("gc", 2663422733, "gc_top10", book_sum=10.0)
grab("gc", 2658789738, "gc_win_wo_pogacar")
grab("stage1_ttt", 2663337357, "stage1_ttt_win")
grab("stage1_ttt", 2664314267, "yellow_after_stage1")

# jerseys: first Winner-type offer in each event
for ev, key in [("points_classification", "points_win"),
                ("mountains_classification", "kom_win"),
                ("youth_classification", "youth_win"),
                ("teams_classification", "teams_win")]:
    bos = [bo for bo in raw[ev]["betOffers"]
           if bo.get("betOfferType", {}).get("name") == "Winnaar"]
    rows = outcomes(bos[0])
    over = devig(rows)
    markets[key] = rows
    prov["overrounds"][key] = round(over, 4)

# rider-wins-a-stage specials ("Ja" outcome per rider)
sw = []
for bo in raw["stage_win_specials"]["betOffers"]:
    if bo["criterion"]["label"] == "Renner wint een etappe":
        ja = [o for o in bo.get("outcomes", []) if o.get("label") == "Ja" and o.get("odds")]
        if ja:
            o = ja[0]
            sw.append({"name": o.get("participant"),
                       "odds": o["odds"] / 1000.0,
                       "implied": 1000.0 / o["odds"]})
sw.sort(key=lambda r: r["odds"])
markets["rider_wins_a_stage"] = sw

# ---- save snapshots ----
for eid, name in EVENTS.items():
    (OUT_DIR / f"kambi_raw_{name}_{STAMP}.json").write_text(
        json.dumps(raw[name]))
(OUT_DIR / f"kambi_markets_parsed_{STAMP}.json").write_text(
    json.dumps(markets, indent=1))
(OUT_DIR / f"kambi_odds_provenance_{STAMP}.json").write_text(
    json.dumps(prov, indent=1))
with open(OUT_DIR / f"unibet_gc_full_field_{STAMP}.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["rider", "win_odds", "win_implied", "win_devig",
                "podium_odds", "podium_devig", "top6_devig", "top10_devig"])
    pod = {norm_name(r["name"]): r for r in markets["gc_podium"]}
    t6 = {norm_name(r["name"]): r for r in markets["gc_top6"]}
    t10 = {norm_name(r["name"]): r for r in markets["gc_top10"]}
    for r in sorted(markets["gc_win"], key=lambda x: x["odds"]):
        k = norm_name(r["name"])
        w.writerow([r["name"], r["odds"], round(r["implied"], 4), round(r["devig"], 4),
                    pod.get(k, {}).get("odds"), round(pod[k]["devig"], 4) if k in pod else None,
                    round(t6[k]["devig"], 4) if k in t6 else None,
                    round(t10[k]["devig"], 4) if k in t10 else None])
print(f"Saved snapshots to {OUT_DIR}")
print("Overrounds:", json.dumps(prov["overrounds"], indent=1))

# ---- comparison vs our predictions ----
PRED = json.loads((SCRATCH / "tdf_2026_predictions.json").read_text())
gc_riders = PRED["scenarios"]["gc"]["riders"]
ours = {norm_name(r["rider_name"]): r for r in gc_riders}

def find_ours(book_name):
    """Exact normalized match, else token-subset fallback (book names may
    carry extra middle names, ours may hyphenate differently)."""
    k = norm_name(book_name)
    if k in ours:
        return ours[k]
    bt = set(k.split())
    cands = [(ok, o) for ok, o in ours.items()
             if set(ok.split()) <= bt or bt <= set(ok.split())]
    return cands[0][1] if len(cands) == 1 else None

# best-day stage win chance per rider across the 6 archetypes (blend)
best_day = {}
for key, s in PRED["scenarios"].items():
    if key == "gc":
        continue
    for r in s["riders"]:
        k = norm_name(r["rider_name"])
        b = r.get("blend_win_p") or 0
        if k not in best_day or b > best_day[k]["blend"]:
            best_day[k] = {"blend": b, "scenario": s["label"]}

comp = {"provenance": prov, "gc": [], "gc_wo_pog": [],
        "stage1_ttt": sorted(markets["stage1_ttt_win"], key=lambda r: r["odds"])[:8],
        "yellow_after_stage1": sorted(markets["yellow_after_stage1"], key=lambda r: r["odds"])[:8],
        "jerseys": {k: sorted(markets[k], key=lambda r: r["odds"])[:6]
                    for k in ("points_win", "kom_win", "youth_win", "teams_win")},
        "stage_hunters": [], "unmatched_book_riders": []}

pod = {norm_name(r["name"]): r for r in markets["gc_podium"]}
for r in sorted(markets["gc_win"], key=lambda x: x["odds"]):
    k = norm_name(r["name"])
    m = find_ours(r["name"])
    if m is None:
        comp["unmatched_book_riders"].append(r["name"])
        continue
    comp["gc"].append({
        "rider": m["rider_name"], "team": m.get("team_name"),
        "book_odds": r["odds"], "book_devig": r["devig"],
        "book_podium_devig": pod.get(k, {}).get("devig"),
        "blend": m.get("blend_win_p"), "cascade": m.get("prob_win"),
        "lr": m.get("lambdarank_win_p"), "honest": m.get("dnf_adj_win_p"),
        "podium": m.get("prob_podium"), "dnf": m.get("dnf_p"),
        "edge_lr": (m.get("lambdarank_win_p") or 0) - r["devig"],
        "edge_blend": (m.get("blend_win_p") or 0) - r["devig"],
    })

# winner-without-Pogacar: renormalize our blend excluding him
non_pog = [r for r in gc_riders if "pogacar" not in norm_name(r["rider_name"])]
s_blend = sum(r.get("blend_win_p") or 0 for r in non_pog)
ours_wo = {norm_name(r["rider_name"]): (r.get("blend_win_p") or 0) / s_blend
           for r in non_pog}
for r in sorted(markets["gc_win_wo_pogacar"], key=lambda x: x["odds"])[:12]:
    m = find_ours(r["name"])
    k = norm_name(m["rider_name"]) if m else norm_name(r["name"])
    comp["gc_wo_pog"].append({
        "rider": r["name"], "book_odds": r["odds"], "book_devig": r["devig"],
        "ours_renorm": ours_wo.get(k),
    })

for r in sw:
    m = find_ours(r["name"])
    k = norm_name(m["rider_name"]) if m else norm_name(r["name"])
    bd = best_day.get(k)
    comp["stage_hunters"].append({
        "rider": r["name"], "book_odds": r["odds"], "book_implied": r["implied"],
        "best_day_blend": bd["blend"] if bd else None,
        "best_day_scenario": bd["scenario"] if bd else None,
    })

(SCRATCH / "tdf_book_comparison.json").write_text(json.dumps(comp, indent=1))
print(f"\nComparison written. GC matched {len(comp['gc'])}/{len(markets['gc_win'])} "
      f"book riders; unmatched: {comp['unmatched_book_riders']}")
print("\nTop GC comparison (book devig vs blend vs LR):")
for r in comp["gc"][:12]:
    print(f"  {r['rider']:>28} book {100*r['book_devig']:5.1f}% "
          f"(odds {r['book_odds']:>6}) | blend {100*(r['blend'] or 0):5.1f}% "
          f"| LR {100*(r['lr'] or 0):5.1f}% | edgeLR {100*r['edge_lr']:+5.1f}pp")
