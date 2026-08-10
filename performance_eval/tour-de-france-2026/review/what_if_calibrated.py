"""What would the model look like with its top-end shyness corrected?

    python3 performance_eval/tour-de-france-2026/review/what_if_calibrated.py

The measured defect is a single monotone miscalibration: every head is
under-confident above ~0.30 and slightly over-confident in the long tail. The
standard one-parameter fix is a temperature (power) transform,

    p' = p^T / sum(p^T),      T > 1 sharpens, T = 1 is unchanged,

applied per stage and renormalized to the market's mass. One free parameter, no
new features, no re-training — this is the cheapest possible version of the fix
and therefore a fair floor for what calibration work is worth.

HONESTY: fitting T on a set and then reporting the gain on that same set is
in-sample and always flatters. Every headline number here is
LEAVE-ONE-STAGE-OUT: T is fitted on the other stages and applied to the held-out
one, so no stage contributes to its own correction. The in-sample fit is printed
alongside purely as the upper bound it is.

NOTE: a temperature transform is monotone, so it CANNOT change any ordering.
Top-k overlap and Spearman are identical before and after — those numbers are in
compare_by_class.py and are unaffected by anything in this file.
"""

import csv
import math
import statistics as st
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
f = lambda v: float(v) if v not in ("", None) else None

HARDMAN = {4, 9, 13, 17, 21}  # the class, per compare_by_class.py
GRID = [1 + i * 0.05 for i in range(0, 61)]  # T from 1.00 to 4.00


def load_stages() -> dict[int, dict]:
    """Per stage: the equal-weight model board, the book board, and the labels."""
    rows = [
        r
        for r in csv.DictReader(open(HERE / "stage_riders.csv"))
        if r["is_hidden"] == "0" and r["is_hindsight"] == "0"
    ]
    by_stage: dict[int, dict[str, dict]] = defaultdict(dict)
    for r in rows:
        s = int(r["stage"])
        d = by_stage[s].setdefault(
            r["rider_name"],
            {
                "model": [],
                "podium": [],
                "top5": [],
                "top15": [],
                "book": f(r["book_devig_norm"]),
                "book_pod": f(r.get("book_podium")),
                "win": int(r["is_winner"]),
                "t3": int(r["in_top3"]),
                "t5": int(r["in_top5"]),
                "t15": int(r["in_top15"]),
            },
        )
        for key, col in (
            ("model", "blend_win_norm"),
            ("podium", "podium_norm"),
            ("top5", "top5_norm"),
            ("top15", "top15_norm"),
        ):
            v = f(r[col])
            if v is not None:
                d[key].append(v)

    out = {}
    for s, riders in by_stage.items():
        recs = list(riders.values())
        for key in ("model", "podium", "top5", "top15"):
            for d in recs:
                d[key] = st.mean(d[key]) if d[key] else 0.0
        out[s] = recs
    return out


def temper(ps: list[float], T: float, mass: float = 1.0) -> list[float]:
    powered = [p**T if p > 0 else 0.0 for p in ps]
    tot = sum(powered)
    return [p * mass / tot for p in powered] if tot > 0 else ps


def win_ll(recs: list[dict], T: float) -> float:
    ps = temper([d["model"] for d in recs], T)
    p_win = next(p for p, d in zip(ps, recs) if d["win"])
    return -math.log(max(p_win, 1e-9))


def depth_ll(recs: list[dict], T: float, key: str, label: str, mass: float) -> float:
    ps = temper([d[key] for d in recs], T, mass)
    eps = 1e-9
    return -sum(
        d[label] * math.log(min(max(p, eps), 1 - eps))
        + (1 - d[label]) * math.log(1 - min(max(p, eps), 1 - eps))
        for p, d in zip(ps, recs)
    ) / len(recs)


def fit_T(stages: dict, keys: list[int], scorer) -> float:
    return min(GRID, key=lambda T: sum(scorer(stages[s], T) for s in keys))


def loso(stages: dict, keys: list[int], scorer) -> tuple[float, float, float, list]:
    """Leave-one-stage-out: fit T without stage s, score stage s. Honest."""
    scores, Ts = [], []
    for s in keys:
        others = [k for k in keys if k != s]
        T = fit_T(stages, others, scorer)
        Ts.append(T)
        scores.append(scorer(stages[s], T))
    T_in = fit_T(stages, keys, scorer)
    in_sample = st.mean([scorer(stages[s], T_in) for s in keys])
    return st.mean(scores), in_sample, T_in, Ts


def book_win_ll(recs: list[dict]) -> float:
    p = next(d["book"] for d in recs if d["win"])
    return -math.log(max(p or 1e-9, 1e-9))


def book_depth_ll(recs: list[dict], key: str, label: str) -> float | None:
    if any(d[key] is None for d in recs):
        return None
    eps = 1e-9
    return -sum(
        d[label] * math.log(min(max(d[key], eps), 1 - eps))
        + (1 - d[label]) * math.log(1 - min(max(d[key], eps), 1 - eps))
        for d in recs
    ) / len(recs)


def report(stages: dict, keys: list[int], title: str) -> None:
    print(f"\n{title}  (n = {len(keys)} stages)")
    print("-" * 78)

    # --- win market
    base = st.mean([win_ll(stages[s], 1.0) for s in keys])
    book = st.mean([book_win_ll(stages[s]) for s in keys])
    cv, ins, T_in, Ts = loso(stages, keys, win_ll)
    print(f"  WIN market      raw model {base:.3f}   book {book:.3f}   "
          f"(model is {book-base:+.3f})")
    print(f"                  calibrated, honest LOSO {cv:.3f}   -> vs book {book-cv:+.3f}"
          f"   [in-sample {ins:.3f}, T={T_in:.2f}, LOSO T range {min(Ts):.2f}-{max(Ts):.2f}]")

    # --- podium market (book price exists on most stages)
    pk = [s for s in keys if book_depth_ll(stages[s], "book_pod", "t3") is not None]
    if pk:
        scorer = lambda recs, T: depth_ll(recs, T, "podium", "t3", 3.0)
        base_p = st.mean([scorer(stages[s], 1.0) for s in pk])
        book_p = st.mean([book_depth_ll(stages[s], "book_pod", "t3") for s in pk])
        cv_p, ins_p, Tp, _ = loso(stages, pk, scorer)
        print(f"  PODIUM market   raw model {base_p:.4f}  book {book_p:.4f}  "
              f"(model is {book_p-base_p:+.4f})")
        print(f"                  calibrated, honest LOSO {cv_p:.4f}  -> vs book "
              f"{book_p-cv_p:+.4f}   [T={Tp:.2f}]")

    # --- our own depth heads (no book market to compare against)
    for key, label, mass, name in (
        ("top5", "t5", 5.0, "TOP-5 "),
        ("top15", "t15", 15.0, "TOP-15"),
    ):
        scorer = lambda recs, T, k=key, l=label, m=mass: depth_ll(recs, T, k, l, m)
        base_d = st.mean([scorer(stages[s], 1.0) for s in keys])
        cv_d, _, Td, _ = loso(stages, keys, scorer)
        print(f"  {name} (model only)  raw {base_d:.4f} -> calibrated {cv_d:.4f}  "
              f"({(base_d-cv_d)/base_d:+.1%}, T={Td:.2f})")


HARDMAN_FLAGGED = {4, 9, 17, 21}  # ex-ante marker, per compare_by_class.py


def regime_switched(stages: dict) -> None:
    """The implementable version: let the EX-ANTE flag choose the temperature.

    The two panels above show the model wants T ~ 1.4 on ordinary days and
    T = 1.0 on hard days. That is a switch, and the only switch available before
    the stage is the hard-man flag from the previews. Note this uses the flag
    ({4,9,17,21}), not the true class ({4,9,13,17,21}) — stage 13 gets sharpened
    wrongly, which is the honest cost of the flag's imperfect recall.
    """
    allk = sorted(stages)
    print("\n\nREGIME-SWITCHED — ex-ante flag picks the temperature (implementable)")
    print("-" * 78)
    scores = []
    for s in allk:
        others = [k for k in allk if k != s]
        pool = [k for k in others if (k in HARDMAN_FLAGGED) == (s in HARDMAN_FLAGGED)]
        T = fit_T(stages, pool, win_ll)
        scores.append(win_ll(stages[s], T))
    book = st.mean([book_win_ll(stages[s]) for s in allk])
    flat_cv, _, _, _ = loso(stages, allk, win_ll)
    raw = st.mean([win_ll(stages[s], 1.0) for s in allk])
    print(f"  all 20 stages   raw {raw:.3f}   one global T {flat_cv:.3f}   "
          f"regime-switched {st.mean(scores):.3f}   book {book:.3f}")

    # and the combination the review actually argues for: switch AND sit out
    bet = [s for s in allk if s not in HARDMAN_FLAGGED]
    sub = [sc for s, sc in zip(allk, scores) if s in bet]
    book_bet = st.mean([book_win_ll(stages[s]) for s in bet])
    print(f"  days we'd bet   calibrated {st.mean(sub):.3f}   book {book_bet:.3f}   "
          f"-> vs book {book_bet-st.mean(sub):+.3f}   (n={len(bet)})")


def main() -> None:
    stages = load_stages()
    allk = sorted(stages)
    clean = [s for s in allk if s not in HARDMAN]

    print("What the model looks like with its top-end shyness corrected.")
    print("Temperature transform p^T, one parameter, fitted leave-one-stage-out.")
    print("Ordering is unchanged by construction — only the probabilities move.")

    report(stages, allk, "ALL 20 STAGES")
    report(stages, clean, f"HARD-MAN CLASS REMOVED {sorted(HARDMAN)}")
    report(stages, sorted(HARDMAN), "THE HARD-MAN STAGES ALONE")
    regime_switched(stages)


if __name__ == "__main__":
    main()
