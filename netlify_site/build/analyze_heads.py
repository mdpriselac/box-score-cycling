"""Head-vs-head analysis over the TdF 2026 runs + GC book as referee.
Writes tdf_heads_analysis.json for the page builder."""

import json
import math
import unicodedata
from pathlib import Path

HERE = Path(__file__).parent
PRED = json.loads((HERE / "tdf_2026_predictions.json").read_text())
BOOK = json.loads((HERE / "tdf_book_comparison.json").read_text())

ORDER = ["gc", "flat_sprint", "reduced_sprint", "punchy", "mountain", "tt30", "queen"]


def norm(vals):
    s = sum(v or 0 for v in vals)
    return [(v or 0) / s if s else 0 for v in vals]


def eff_n(probs):
    """exp(entropy) — effective number of contenders in a win book."""
    h = -sum(p * math.log(p) for p in probs if p > 1e-12)
    return math.exp(h)


def top_share(probs, k):
    return sum(sorted(probs, reverse=True)[:k])


def spearman(a, b):
    n = len(a)
    ra = {v: i for i, v in enumerate(sorted(range(n), key=lambda i: -a[i]))}
    rb = {v: i for i, v in enumerate(sorted(range(n), key=lambda i: -b[i]))}
    d2 = sum((ra[i] - rb[i]) ** 2 for i in range(n))
    return 1 - 6 * d2 / (n * (n * n - 1))


out = {"shape": [], "gc_bands": [], "referee": {}, "disagreements": [],
       "spearman": [], "dnf": [], "notes": {}}

# ---------- 1. book shape per scenario ----------
for key in ORDER:
    s = PRED["scenarios"][key]
    riders = s["riders"]
    casc = norm([r.get("prob_win") for r in riders])
    lr = [r.get("lambdarank_win_p") or 0 for r in riders]
    blend = norm([r.get("blend_win_p") for r in riders])
    out["shape"].append({
        "key": key, "label": s["label"],
        "cascade": {"top1": top_share(casc, 1), "top3": top_share(casc, 3),
                    "eff_n": eff_n(casc)},
        "lr": {"top1": top_share(lr, 1), "top3": top_share(lr, 3),
               "eff_n": eff_n(lr)},
        "blend": {"top1": top_share(blend, 1), "top3": top_share(blend, 3),
                  "eff_n": eff_n(blend)},
    })

# book shape for GC (devig sums to 1 over priced riders)
gc_book = [r["book_devig"] for r in BOOK["gc"]]
out["notes"]["book_gc_shape"] = {
    "top1": top_share(gc_book, 1), "top3": top_share(gc_book, 3),
    "eff_n": eff_n(gc_book), "n_priced": len(gc_book),
}

# ---------- 2. GC odds-band mass allocation ----------
BANDS = [("Favorites (odds < 10)", 0, 10), ("Contenders (10–50)", 10, 50),
         ("Longshots (51–200)", 50, 200), ("Extreme (> 200)", 200, 1e9)]
rows = BOOK["gc"]
casc_n = norm([r["cascade"] for r in rows])
blend_n = norm([r["blend"] for r in rows])
lr_raw = [r["lr"] or 0 for r in rows]
lr_n = norm(lr_raw)  # LR book over the 40 priced riders (rest of field tiny)
for label, lo, hi in BANDS:
    idx = [i for i, r in enumerate(rows) if lo < r["book_odds"] <= hi]
    out["gc_bands"].append({
        "band": label, "n": len(idx),
        "book": sum(rows[i]["book_devig"] for i in idx),
        "cascade": sum(casc_n[i] for i in idx),
        "blend": sum(blend_n[i] for i in idx),
        "lr": sum(lr_n[i] for i in idx),
    })

# ---------- 3. book as referee on cascade-vs-LR disagreements ----------
dis = []
for i, r in enumerate(rows):
    gap = casc_n[i] - lr_n[i]
    closer = "cascade" if abs(casc_n[i] - r["book_devig"]) < abs(lr_n[i] - r["book_devig"]) else "lr"
    dis.append({"rider": r["rider"], "book_odds": r["book_odds"],
                "book": r["book_devig"], "cascade_n": casc_n[i],
                "lr_n": lr_n[i], "gap": gap, "book_sides_with": closer})
dis.sort(key=lambda d: -abs(d["gap"]))
out["disagreements"] = dis[:12]
top10 = [d for d in dis if d["book_odds"] <= 50]
tail = [d for d in dis if d["book_odds"] > 50]
out["referee"] = {
    "favorites_cascade": sum(1 for d in top10 if d["book_sides_with"] == "cascade"),
    "favorites_total": len(top10),
    "tail_cascade": sum(1 for d in tail if d["book_sides_with"] == "cascade"),
    "tail_total": len(tail),
}

# ---------- 4. rank agreement between heads per scenario ----------
for key in ORDER:
    s = PRED["scenarios"][key]
    riders = [r for r in s["riders"]
              if r.get("prob_win") is not None and r.get("lambdarank_win_p") is not None]
    casc = [r["prob_win"] for r in riders]
    lr = [r["lambdarank_win_p"] for r in riders]
    tg = [-(r.get("predicted_time_gap") or 0) for r in riders]  # smaller gap = better
    eb = [-(r.get("expected_bucket") or 9) for r in riders]
    elo = [r.get("contested_rating") or 0 for r in riders]
    out["spearman"].append({
        "key": key, "label": s["label"],
        "cascade_lr": spearman(casc, lr),
        "bucket_timegap": spearman(eb, tg),
        "cascade_elo": spearman(casc, elo),
    })

# ---------- 5. DNF head by archetype ----------
for key in ORDER:
    s = PRED["scenarios"][key]
    dnfs = [r.get("dnf_p") for r in s["riders"] if r.get("dnf_p") is not None]
    prof = s["avg_profile"]
    out["dnf"].append({
        "key": key, "label": s["label"],
        "mean_dnf": sum(dnfs) / len(dnfs), "max_dnf": max(dnfs),
        "ref_abandon": prof.get("abandon_ratio"),
        "mountain_score": prof.get("race_mountain_score"),
    })

(HERE / "tdf_heads_analysis.json").write_text(json.dumps(out, indent=1))

print("SHAPE (top1 / top3 / effective contenders):")
for s in out["shape"]:
    print(f"  {s['key']:>14} casc {100*s['cascade']['top1']:4.1f}/{100*s['cascade']['top3']:4.1f}/{s['cascade']['eff_n']:5.1f}"
          f" | LR {100*s['lr']['top1']:4.1f}/{100*s['lr']['top3']:4.1f}/{s['lr']['eff_n']:5.1f}")
b = out["notes"]["book_gc_shape"]
print(f"  BOOK gc        {100*b['top1']:4.1f}/{100*b['top3']:4.1f}/{b['eff_n']:5.1f} over {b['n_priced']} priced")
print("\nGC BANDS (probability mass):")
for r in out["gc_bands"]:
    print(f"  {r['band']:>24} n={r['n']:2d} book {100*r['book']:5.1f}% | casc {100*r['cascade']:5.1f}% | LR {100*r['lr']:5.1f}% | blend {100*r['blend']:5.1f}%")
print("\nREFEREE:", out["referee"])
print("\nSPEARMAN (cascade~LR | bucket~timegap | cascade~Elo):")
for s in out["spearman"]:
    print(f"  {s['key']:>14} {s['cascade_lr']:.3f} | {s['bucket_timegap']:.3f} | {s['cascade_elo']:.3f}")
print("\nDNF by archetype:")
for d in out["dnf"]:
    print(f"  {d['key']:>14} mean {100*d['mean_dnf']:4.1f}% max {100*d['max_dnf']:4.1f}% (ref abandon {100*(d['ref_abandon'] or 0):4.1f}%, mtn {d['mountain_score']:.2f})")
