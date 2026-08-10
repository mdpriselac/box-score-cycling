"""Model vs book across all outcome depths, sliced by stage class.

    python3 performance_eval/tour-de-france-2026/review/compare_by_class.py

The GT hard-day class (shattered non-mountain days won by punchy non-climbers
from breaks / late moves / reduced hard-men sprints) is defined here by DAY
SHAPE and WINNER TYPE, deliberately not by how the model scored — excluding
stages because we did badly on them would be circular. Panels are printed for
several class boundaries so the sensitivity to that judgment is visible.
"""

import csv
import math
import statistics as st
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent

f = lambda v: float(v) if v not in ("", None) else None
i = lambda v: int(v) if v not in ("", None) else None

# Day shapes, read off results/stage_NN gap curves + the stage reflections.
#   4  Pedersen   split to a front 10, sprint out of it, fast-man winner
#   9  van der Poel  late move over the final climbs, punchy non-climbers
#   13 Schmid     break survived a rolling/mountain day, classics-man winner
#   17 Philipsen  26-rider mixed break, sprinter won out of it
# Wider reading adds the one shattered day whose finish was a bunch gallop:
#   21 van der Poel  Montmartre circuit, hard-man win from a reduced gallop
# Stage 2 is deliberately NOT in the class (user, 2026-07-27): it shattered, but
# the thirteen who contested it were GC men — del Toro from Pogacar, Vingegaard
# and Evenepoel. A selective GC day, not a punchy-non-climber day.
CORE = {4, 9, 13, 17}
WIDE = CORE | {21}
# Reference only — these are CLIMBERS' breaks, i.e. NOT the class in question,
# but they are also among our worst days, so the panel shows what excluding
# them would buy (and therefore how much of the gap is class-specific).
# Stage 19 is deliberately NOT here: a climbers' escape took the places but
# Pogacar won the stage out of the GC group.
CLIMBER_BREAKS = {18, 20}
# Every day whose winner came out of the day's escape, regardless of his type.
BREAK_WON = {13, 17, 18, 20}

# ---------------------------------------------------------------------------
# EX-ANTE sets. Everything above is a post-hoc carve: true, but unusable as a
# policy because you only know the membership after the stage. These two sets
# are recoverable from the published config BEFORE the stage was raced, so a
# "sit this one out" rule could actually have been run on them.
#
#   HARDMAN_FLAGGED  — the day's published reads included an explicit hard-man /
#     late-move branch, i.e. we named this class in the preview:
#       4  late_move        9  hard_mens_sprint + late_move
#       17 hard_mens_sprint 21 montmartre_move
#   PUNCHY_MACHINERY — the config carried a `punchy_filter` block, the purely
#     mechanical marker that we ran the punchy/sprinter classification that day.
#     Note this conflates two uses: the hard-day punchy pool (9, 17, 21) and the
#     flat-day mirror-image sprinter filter (11, 12), which is a different day.
HARDMAN_FLAGGED = {4, 9, 17, 21}
PUNCHY_MACHINERY = {9, 11, 12, 17, 21}


def load():
    M = [r for r in csv.DictReader(open(HERE / "stage_metrics.csv"))]
    vis = defaultdict(list)
    for m in M:
        if m["is_hidden"] == "0" and m["is_hindsight"] == "0":
            vis[int(m["stage"])].append(m)
    return vis


def panel(vis, exclude: set[int], label: str) -> dict:
    stages = [s for s in sorted(vis) if s not in exclude]
    n = len(stages)
    out = {"label": label, "n": n}

    # win market: equal weight across the reads we published that day
    mll, bll = [], []
    for s in stages:
        c = [m for m in vis[s] if f(m.get("model_p_winner")) is not None]
        if not c:
            continue
        p = st.mean([f(m["model_p_winner"]) for m in c])
        mll.append(-math.log(max(p, 1e-9)))
        bll.append(-math.log(max(f(c[0]["book_p_winner"]), 1e-9)))
    out["win_model"], out["win_book"] = st.mean(mll), st.mean(bll)

    # podium market (where the book priced one)
    pm, pb = [], []
    for s in stages:
        c = vis[s]
        if c[0]["podium_market"] != "1":
            continue
        pm.append(st.mean([f(x["model_podium_ll"]) for x in c]))
        pb.append(f(c[0]["book_podium_ll"]))
    out["pod_model"], out["pod_book"], out["pod_n"] = st.mean(pm), st.mean(pb), len(pm)

    # ordering depth
    for k in (3, 5, 10, 15):
        mo = st.mean([st.mean([i(m[f"model_overlap{k}"]) for m in vis[s]]) for s in stages])
        bo = st.mean([i(vis[s][0][f"book_overlap{k}"]) for s in stages])
        out[f"ovl{k}_model"], out[f"ovl{k}_book"] = mo / k, bo / k
    out["sp_model"] = st.mean([st.mean([f(m["model_spearman"]) for m in vis[s]]) for s in stages])
    out["sp_book"] = st.mean([f(vis[s][0]["book_spearman"]) for s in stages])
    return out


def show(rows: list[dict]) -> None:
    print(f"{'panel':<34} {'n':>3} | {'win LL m/b':>17} | {'podium LL m/b':>19} |"
          f" {'top3':>13} {'top5':>13} {'top10':>13} {'top15':>13} | {'spearman':>13}")
    for r in rows:
        print(
            f"{r['label']:<34} {r['n']:>3} | "
            f"{r['win_model']:.3f}/{r['win_book']:.3f} ({r['win_book']-r['win_model']:+.3f}) | "
            f"{r['pod_model']:.4f}/{r['pod_book']:.4f} ({r['pod_book']-r['pod_model']:+.4f}) | "
            + " ".join(
                f"{r[f'ovl{k}_model']:.0%}/{r[f'ovl{k}_book']:.0%}"
                f"({(r[f'ovl{k}_model']-r[f'ovl{k}_book'])*100:+.0f})".rjust(13)
                for k in (3, 5, 10, 15)
            )
            + f" | {r['sp_model']:.3f}/{r['sp_book']:.3f}"
        )


def main() -> None:
    vis = load()
    rows = [
        panel(vis, set(), "all 20 stages"),
        panel(vis, CORE, f"minus GT hard-day core {sorted(CORE)}"),
        panel(vis, WIDE, f"minus GT hard-day wide {sorted(WIDE)}"),
        panel(vis, CLIMBER_BREAKS, "minus climbers' breaks (ref only)"),
        panel(vis, BREAK_WON, "minus ALL break-won days"),
        # WIDE | CLIMBER_BREAKS is the same 7 stages as BREAK_WON | {4,9,21}
        panel(vis, BREAK_WON | {4, 9, 21}, "peloton/GC-settled days only"),
    ]
    print("POST-HOC carves (true, but membership is only known after the stage)")
    print("model / book  (delta in parens; + = model better; LL lower is better)\n")
    show(rows)

    print("\n" + "=" * 120)
    print("EX-ANTE carves — membership recoverable from the published config BEFORE the stage")
    print("i.e. these are the only slices a 'sit this one out' policy could actually have run\n")
    ex = [
        panel(vis, set(), "all 20 stages (bet everything)"),
        panel(vis, HARDMAN_FLAGGED, f"skip hard-man flagged {sorted(HARDMAN_FLAGGED)}"),
        panel(vis, PUNCHY_MACHINERY, f"skip punchy-filter days {sorted(PUNCHY_MACHINERY)}"),
        panel(vis, HARDMAN_FLAGGED | PUNCHY_MACHINERY, "skip either flag"),
        panel(vis, CORE, "[post-hoc core, for contrast]"),
    ]
    show(ex)

    # --- policy view: is the flag a usable abstention rule?
    print("\nabstention-policy view (win-market nats vs the book):")
    deltas = {}
    for s in sorted(vis):
        c = [m for m in vis[s] if f(m.get("model_p_winner")) is not None]
        p = st.mean([f(m["model_p_winner"]) for m in c])
        deltas[s] = -math.log(max(f(c[0]["book_p_winner"]), 1e-9)) + math.log(max(p, 1e-9))
    for name, sel in (
        ("hard-man flagged", HARDMAN_FLAGGED),
        ("punchy-filter", PUNCHY_MACHINERY),
        ("[post-hoc core]", CORE),
    ):
        on = [deltas[s] for s in sel]
        off = [deltas[s] for s in deltas if s not in sel]
        bad = sum(1 for d in on if d < 0)
        print(
            f"  {name:<18} n={len(on)}  mean delta on flagged {st.mean(on):+.3f} "
            f"({bad}/{len(on)} below the book)   on unflagged {st.mean(off):+.3f}   "
            f"total nats avoided {-sum(on):+.2f}"
        )
    print(f"  cost of a false abstention: st17 was flagged and we BEAT the book there "
          f"({deltas[17]:+.2f} nats forgone)")

    print("\nwhat the ex-ante flag actually caught, day by day:")
    for s in sorted(vis):
        c = [m for m in vis[s] if f(m.get("model_p_winner")) is not None]
        p = st.mean([f(m["model_p_winner"]) for m in c])
        d = -math.log(max(f(c[0]["book_p_winner"]), 1e-9)) + math.log(max(p, 1e-9))
        flag = "HARDMAN" if s in HARDMAN_FLAGGED else ("punchy" if s in PUNCHY_MACHINERY else "")
        truth = "hard-day" if s in WIDE else ("break-won" if s in BREAK_WON else "")
        hit = ""
        if flag and truth:
            hit = "caught"
        elif flag and not truth:
            hit = "false alarm"
        elif not flag and truth:
            hit = "MISSED"
        print(f"  st{s:>2} {d:>+6.2f}  {c[0]['winner']:<22} flag={flag:<8} actual={truth:<10} {hit}")
    print("\nper-stage win-market delta (nats, + = model beat the book):")
    for s in sorted(vis):
        c = [m for m in vis[s] if f(m.get("model_p_winner")) is not None]
        p = st.mean([f(m["model_p_winner"]) for m in c])
        d = -math.log(max(f(c[0]["book_p_winner"]), 1e-9)) + math.log(max(p, 1e-9))
        tag = "CORE" if s in CORE else ("wide" if s in WIDE else ("clmb" if s in CLIMBER_BREAKS else ""))
        print(f"  st{s:>2} {d:>+6.2f}  {c[0]['winner']:<22} {tag}")


if __name__ == "__main__":
    main()
