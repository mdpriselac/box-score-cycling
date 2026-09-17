"""Every number on the Vuelta 2026 retrospective page, from the review dataset.

    uv run python performance_eval/vuelta-2026/review/analyze_review.py

Reads review/stage_riders.csv, stage_metrics.csv, gc_daily.csv, gc_metrics.csv
(built by ../../tour-de-france-2026/build_review_dataset.py --campaign
performance_eval/vuelta-2026) plus the Tour's own review CSVs for the
like-for-like comparison, and writes review/analysis.json. Prints the panels.

Conventions (identical to the Tour review):
  * the model's ex-ante number on a stage is the EQUAL WEIGHT across that
    morning's published reads (hidden anchors and hindsight runs excluded);
  * blend_win_norm is the renormalized win marginal; book_devig_norm is the
    devigged book renormalized over the same riders;
  * stage classes are defined by day shape and winner type, never by score.
"""

from __future__ import annotations

import csv
import json
import math
import statistics as st
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
TDF = HERE.parents[1] / "tour-de-france-2026" / "review"

f = lambda v: float(v) if v not in ("", None) else None
i = lambda v: int(float(v)) if v not in ("", None) else None

# ----------------------------------------------------------------- classes
# Day shape + winner type, read off results/stage_NN gap curves and the stage
# reflections. Scored stages only (13, 18, 19 were missed mornings; 3 cancelled).
#   hard-man: shattered non-mountain day won by a punchy non-climber from a
#             break / late move / reduced hard-men sprint (the Tour's class)
#     10 Tronchon  68-rider group, the three fastest men 90th/111th/163rd
#     15 van Aert  five-man escape on a hot rolling day, sprinters at 1:47
#     21 Johannessen  cobbled circuit, 40-rider front, van Aert 65th
#   climbers' breaks: escape wins on mountain days (NOT the class above)
#      7 Leknessund (Valdelinares), 12 Omrzel (Calar Alto), 14 Brenner
#     (La Pandera), 20 Landa (Purche)
#   break-won: every day whose winner came out of the escape
#   peloton / GC-settled: the rest, incl. the Monaco ITT (1)
HARDMAN = {10, 15, 21}
CLIMBER_BREAKS = {7, 12, 14, 20}
BREAK_WON = CLIMBER_BREAKS | {15}
ITT = {1}
# Tour classes, from compare_by_class.py
TDF_HARDMAN = {4, 9, 13, 17, 21}
TDF_BREAK_WON = {13, 17, 18, 20}
TDF_HARDMAN_FLAGGED = {4, 9, 17, 21}

MACRO_ITEMS = {"bunch", "gc_day", "itt"}
GRID = [1 + k * 0.05 for k in range(0, 61)]


def load_metrics(path: Path) -> dict[int, list[dict]]:
    vis = defaultdict(list)
    for m in csv.DictReader(open(path)):
        if m["is_hidden"] == "0" and m["is_hindsight"] == "0":
            vis[int(m["stage"])].append(m)
    return vis


def load_all_metrics(path: Path) -> dict[int, list[dict]]:
    out = defaultdict(list)
    for m in csv.DictReader(open(path)):
        out[int(m["stage"])].append(m)
    return out


def stage_ew(reads: list[dict], col: str) -> float | None:
    vals = [f(m[col]) for m in reads if f(m.get(col)) is not None]
    return sum(vals) / len(vals) if vals else None


def panel(vis: dict[int, list[dict]], stages: list[int], label: str) -> dict:
    """Win LL (equal weight + best read), podium LL, depth overlap, spearman."""
    out = {"label": label, "n": len(stages), "stages": stages}
    mll, bll, best, lr_best, pm, pb = [], [], [], [], [], []
    ov = {k: [0.0, 0] for k in (3, 5, 10, 15)}
    sp_m, sp_b = [], []
    mtop, btop, nreads = 0, 0, 0
    for s in stages:
        reads = [m for m in vis[s] if f(m.get("model_p_winner")) is not None]
        if not reads:
            continue
        pw = stage_ew(reads, "model_p_winner")
        mll.append(-math.log(pw))
        bll.append(f(reads[0]["book_logloss"]))
        best.append(min(f(m["model_logloss"]) for m in reads))
        lr_best.append(min(f(m["lambdarank_logloss"]) for m in reads))
        if reads[0]["podium_market"] == "1":
            pm.append(stage_ew(reads, "model_podium_ll"))
            pb.append(f(reads[0]["book_podium_ll"]))
        for k in ov:
            ov[k][0] += stage_ew(reads, f"model_overlap{k}")
            ov[k][1] += i(reads[0][f"book_overlap{k}"])
        sp_m.append(stage_ew(reads, "model_spearman"))
        sp_b.append(f(reads[0]["book_spearman"]))
        mtop += sum(int(m["model_top_pick_won"]) for m in reads)
        btop += sum(int(m["book_top_pick_won"]) for m in reads)
        nreads += len(reads)
    n = len(mll)
    out.update(
        {
            "win_ll_model_ew": st.mean(mll),
            "win_ll_book": st.mean(bll),
            "win_ll_delta": st.mean(bll) - st.mean(mll),
            "win_ll_model_best": st.mean(best),
            "win_ll_lambdarank_best": st.mean(lr_best),
            "total_deficit_nats": sum(m - b for m, b in zip(mll, bll)),
            "podium_n": len(pm),
            "podium_ll_model": st.mean(pm) if pm else None,
            "podium_ll_book": st.mean(pb) if pb else None,
            "overlap": {k: {"model": ov[k][0], "book": ov[k][1], "of": n * k,
                            "delta_pp": 100 * (ov[k][0] - ov[k][1]) / (n * k)} for k in ov},
            "spearman_model": st.mean(sp_m),
            "spearman_book": st.mean(sp_b),
            "reads": nreads,
            "top_pick_wins_model": mtop,
            "top_pick_wins_book": btop,
        }
    )
    return out


def per_stage(vis: dict[int, list[dict]]) -> list[dict]:
    rows = []
    for s in sorted(vis):
        reads = [m for m in vis[s] if f(m.get("model_p_winner")) is not None]
        if not reads:
            continue
        pw = stage_ew(reads, "model_p_winner")
        pb = f(reads[0]["book_p_winner"])
        best = min(reads, key=lambda m: f(m["model_logloss"]))
        rows.append(
            {
                "stage": s,
                "winner": reads[0]["winner"],
                "model_p_ew": pw,
                "book_p": pb,
                "delta_nats": (-math.log(pb)) - (-math.log(pw)),
                "best_read": best["scenario"],
                "best_read_p": f(best["model_p_winner"]),
                "official_read": reads[0]["scenario"],
                "official_p": f(reads[0]["model_p_winner"]),
                "model_rank_ew": stage_ew(reads, "model_rank_of_winner"),
                "book_rank": i(reads[0]["book_rank_of_winner"]),
                "model_top_pick": reads[0]["model_top_pick"],
                "model_top_pick_place": i(reads[0]["model_top_pick_place"]),
                "book_top_pick": reads[0]["book_top_pick"],
                "book_top_pick_place": i(reads[0]["book_top_pick_place"]),
                "n_reads": len(reads),
                "day_key": reads[0].get("day_key", ""),
                "overlap15_model": stage_ew(reads, "model_overlap15"),
                "overlap15_book": i(reads[0]["book_overlap15"]),
                "overlap10_model": stage_ew(reads, "model_overlap10"),
                "overlap10_book": i(reads[0]["book_overlap10"]),
            }
        )
    return rows


# ------------------------------------------------------------ calibration


def load_riders(path: Path) -> list[dict]:
    return [
        r for r in csv.DictReader(open(path))
        if r["is_hidden"] == "0" and r["is_hindsight"] == "0"
    ]


def calibration(riders: list[dict]) -> dict:
    """stated -> realised, by head and band, over all visible reads."""
    bands = [(0.0, 0.05), (0.05, 0.1), (0.1, 0.2), (0.2, 0.3), (0.3, 0.5), (0.5, 0.75), (0.75, 1.01)]
    heads = {
        "win": ("blend_win_norm", "is_winner"),
        "podium": ("podium_norm", "in_top3"),
        "top5": ("top5_norm", "in_top5"),
        "top15": ("top15_norm", "in_top15"),
    }
    out = {}
    for h, (pc, yc) in heads.items():
        out[h] = []
        for lo, hi in bands:
            sel = [(f(r[pc]), int(r[yc])) for r in riders if f(r[pc]) is not None and lo <= f(r[pc]) < hi]
            if len(sel) < 5:
                continue
            out[h].append(
                {"band": f"{lo:.2f}-{min(hi,1):.2f}", "n": len(sel),
                 "stated": st.mean(p for p, _ in sel), "realised": st.mean(y for _, y in sel)}
            )
    # the book's own calibration on the win market for contrast
    out["book_win"] = []
    seen = set()
    for lo, hi in bands:
        sel = []
        for r in riders:
            key = (r["stage"], r["rider_name"])
            p = f(r["book_devig_norm"])
            if p is None or not (lo <= p < hi):
                continue
            if key in seen:
                continue
            sel.append((p, int(r["is_winner"])))
        # book price is identical across a stage's reads: dedupe by stage/rider
        ded = {}
        for r in riders:
            p = f(r["book_devig_norm"])
            if p is not None and lo <= p < hi:
                ded[(r["stage"], r["rider_name"])] = (p, int(r["is_winner"]))
        if len(ded) >= 5:
            out["book_win"].append(
                {"band": f"{lo:.2f}-{min(hi,1):.2f}", "n": len(ded),
                 "stated": st.mean(p for p, _ in ded.values()),
                 "realised": st.mean(y for _, y in ded.values())}
            )
    return out


# -------------------------------------------------------- temperature LOO


def stage_boards(riders: list[dict]) -> dict[int, dict]:
    by = defaultdict(dict)
    for r in riders:
        s = int(r["stage"])
        d = by[s].setdefault(r["rider_name"], {"model": [], "book": f(r["book_devig_norm"]), "win": int(r["is_winner"])})
        d["model"].append(f(r["blend_win_norm"]))
    out = {}
    for s, d in by.items():
        names = list(d)
        p = [st.mean(d[n]["model"]) for n in names]
        tot = sum(p)
        out[s] = {
            "p": [x / tot for x in p],
            "book": [d[n]["book"] for n in names],
            "win": [d[n]["win"] for n in names],
        }
    return out


def sharpen(p: list[float], T: float) -> list[float]:
    q = [max(x, 1e-12) ** T for x in p]
    tot = sum(q)
    return [x / tot for x in q]


def win_ll(board: dict, T: float) -> float:
    q = sharpen(board["p"], T)
    return -math.log(max(q[board["win"].index(1)], 1e-9))


def loo_temperature(boards: dict[int, dict], stages: list[int]) -> dict:
    raw, cal, book = [], [], []
    Ts = []
    for s in stages:
        others = [t for t in stages if t != s]
        T = min(GRID, key=lambda T: sum(win_ll(boards[t], T) for t in others))
        Ts.append(T)
        raw.append(win_ll(boards[s], 1.0))
        cal.append(win_ll(boards[s], T))
        b = boards[s]["book"][boards[s]["win"].index(1)]
        book.append(-math.log(b))
    in_sample_T = min(GRID, key=lambda T: sum(win_ll(boards[t], T) for t in stages))
    return {
        "n": len(stages),
        "raw": st.mean(raw), "calibrated": st.mean(cal), "book": st.mean(book),
        "gap_raw": st.mean(book) - st.mean(raw), "gap_cal": st.mean(book) - st.mean(cal),
        "T_in_sample": in_sample_T, "T_loo_median": st.median(Ts),
        "per_stage": {s: {"raw": r, "cal": c, "book": b, "T": T}
                      for s, r, c, b, T in zip(stages, raw, cal, book, Ts)},
    }


# ------------------------------------------------------------ ranking channel


def ranking_channel(all_metrics: dict[int, list[dict]]) -> dict:
    """Published (day-menu) order vs production order vs book, top-k retrieval."""
    per = []
    tot = {k: {"published": 0.0, "production": 0.0, "book": 0, "official_pub": 0, "official_prod": 0,
               "best_branch_pub": 0, "hindsight_pub": 0.0, "n_hind": 0} for k in (10, 15)}
    for s in sorted(all_metrics):
        reads = [m for m in all_metrics[s] if m["is_hidden"] == "0" and m["is_hindsight"] == "0"]
        hind = [m for m in all_metrics[s] if m["is_hindsight"] == "1"]
        if not reads:
            continue
        row = {"stage": s, "board": reads[0]["board"], "n_reads": len(reads)}
        for k in (10, 15):
            pub = [i(m[f"published_overlap{k}"]) for m in reads]
            prod = [i(m[f"production_overlap{k}"]) for m in reads]
            row[f"pub{k}_ew"] = st.mean(pub)
            row[f"prod{k}_ew"] = st.mean(prod)
            row[f"pub{k}_official"] = pub[0]
            row[f"prod{k}_official"] = prod[0]
            row[f"pub{k}_best"] = max(pub)
            row[f"book{k}"] = i(reads[0][f"book_overlap{k}"])
            row[f"hind{k}"] = i(hind[0][f"published_overlap{k}"]) if hind else None
            tot[k]["published"] += st.mean(pub)
            tot[k]["production"] += st.mean(prod)
            tot[k]["book"] += i(reads[0][f"book_overlap{k}"]) or 0
            tot[k]["official_pub"] += pub[0]
            tot[k]["official_prod"] += prod[0]
            tot[k]["best_branch_pub"] += max(pub)
            if hind:
                tot[k]["hindsight_pub"] += i(hind[0][f"published_overlap{k}"]) or 0
                tot[k]["n_hind"] += 1
        per.append(row)
    return {"per_stage": per, "totals": tot}


# ---------------------------------------------------------------- hits/misses


def hits_and_misses(riders: list[dict]) -> dict:
    """Riders on the podium where model and book disagreed most, both ways."""
    ew = defaultdict(lambda: {"m": [], "b": None, "place": None, "n": 0})
    for r in riders:
        key = (int(r["stage"]), r["rider_name"])
        d = ew[key]
        d["m"].append(f(r["blend_win_norm"]) or 0.0)
        d["b"] = f(r["book_devig_norm"])
        d["place"] = i(r["place"])
        d["gap"] = f(r["gap"])
    rows = []
    for (s, name), d in ew.items():
        if d["b"] is None or d["place"] is None or d["place"] > 3:
            continue
        m = st.mean(d["m"])
        rows.append({"stage": s, "rider": name, "place": d["place"], "model_p": m,
                     "book_p": d["b"], "ratio": m / max(d["b"], 1e-6)})
    rows.sort(key=lambda r: -r["ratio"])
    return {"podium_model_over_book": rows[:12], "podium_book_over_model": rows[-12:][::-1]}


def favourites(riders: list[dict]) -> dict:
    """Where the book's and the model's favourite finished, per stage."""
    by = defaultdict(dict)
    for r in riders:
        s = int(r["stage"])
        d = by[s].setdefault(r["rider_name"], {"m": [], "b": f(r["book_devig_norm"]), "place": i(r["place"])})
        d["m"].append(f(r["blend_win_norm"]) or 0.0)
    out = []
    for s in sorted(by):
        d = by[s]
        mfav = max(d, key=lambda n: st.mean(d[n]["m"]))
        bfav = max(d, key=lambda n: d[n]["b"] or 0.0)
        out.append({"stage": s,
                    "model_fav": mfav, "model_fav_p": st.mean(d[mfav]["m"]), "model_fav_book_p": d[mfav]["b"], "model_fav_place": d[mfav]["place"],
                    "book_fav": bfav, "book_fav_p": d[bfav]["b"], "book_fav_model_p": st.mean(d[bfav]["m"]), "book_fav_place": d[bfav]["place"]})
    return out


# ---------------------------------------------------------------------- GC


def gc_summary(path_metrics: Path, path_daily: Path) -> dict:
    ms = list(csv.DictReader(open(path_metrics)))
    paired = [m for m in ms if m["book_pairing"] not in ("stale", "")]
    def nl(p):
        return -math.log(max(p, 1e-9)) if p is not None else None
    boards = []
    for m in ms:
        boards.append({
            "through_stage": i(m["through_stage"]), "date": m["date"], "book_date": m["book_date"],
            "pairing": m["book_pairing"],
            "winner_model_p": f(m["winner_model_p"]), "winner_book_p": f(m["winner_book_p"]),
            "winner_outlook_p": f(m["winner_outlook_p"]),
            "model_leader": m["model_leader"], "book_leader": m["book_leader"], "outlook_leader": m["outlook_leader"],
            "spearman_model": f(m["model_spearman"]), "spearman_book": f(m["book_spearman"]), "spearman_outlook": f(m["outlook_spearman"]),
            "overlap15_model": i(m["model_overlap15"]), "overlap15_book": i(m["book_overlap15"]), "overlap15_outlook": i(m["outlook_overlap15"]),
            "overlap5_model": i(m["model_overlap5"]), "overlap5_book": i(m["book_overlap5"]), "overlap5_outlook": i(m["outlook_overlap5"]),
            "podium_ll_model": f(m["model_podium_ll"]), "podium_ll_book": f(m["book_podium_ll"]), "podium_ll_outlook": f(m["gc_outlook_podium_ll"]),
            "top10_ll_model": f(m["model_top10_ll"]), "top10_ll_book": f(m["book_top10_ll"]),
        })
    def avg(rows, key, fn=lambda x: x):
        vals = [fn(r[key]) for r in rows if r[key] is not None]
        return st.mean(vals) if vals else None
    pre = [b for b in boards if b["through_stage"] is not None and b["through_stage"] <= 7]
    post = [b for b in boards if b["through_stage"] is not None and b["through_stage"] >= 8 and b["pairing"] not in ("stale", "")]
    post_all = [b for b in boards if b["through_stage"] is not None and b["through_stage"] >= 8]
    pairedb = [b for b in boards if b["pairing"] not in ("stale", "")]
    out = {"boards": boards, "n_boards": len(boards), "n_paired": len(pairedb)}
    for name, rows in (("all_paired", pairedb), ("pre_abandon", pre), ("post_abandon", post), ("post_abandon_all", post_all)):
        out[name] = {
            "n": len(rows),
            "winner_ll_model": avg(rows, "winner_model_p", nl),
            "winner_ll_book": avg(rows, "winner_book_p", nl),
            "winner_ll_outlook": avg(rows, "winner_outlook_p", nl),
            "spearman_model": avg(rows, "spearman_model"), "spearman_book": avg(rows, "spearman_book"), "spearman_outlook": avg(rows, "spearman_outlook"),
            "overlap15_model": avg(rows, "overlap15_model"), "overlap15_book": avg(rows, "overlap15_book"), "overlap15_outlook": avg(rows, "overlap15_outlook"),
            "overlap5_model": avg(rows, "overlap5_model"), "overlap5_book": avg(rows, "overlap5_book"), "overlap5_outlook": avg(rows, "overlap5_outlook"),
            "podium_ll_model": avg(rows, "podium_ll_model"), "podium_ll_book": avg(rows, "podium_ll_book"), "podium_ll_outlook": avg(rows, "podium_ll_outlook"),
        }
    # Pogacar's price on the pre-abandon boards, and the top of the last board
    daily = list(csv.DictReader(open(path_daily)))
    pog = []
    for through in sorted({i(d["through_stage"]) for d in daily if i(d["through_stage"]) is not None and i(d["through_stage"]) <= 7}):
        rows = [d for d in daily if i(d["through_stage"]) == through and d["rider_name"].startswith("Pogacar")]
        if rows:
            r = rows[0]
            pog.append({"through_stage": through, "model": f(r["blend_win_norm"]), "book": f(r["book_devig_norm"]),
                        "outlook": f(r["gc_outlook_win_p"])})
    out["pogacar_pre_abandon"] = pog
    last = [d for d in daily if i(d["through_stage"]) == 19]
    tot_o = sum(f(d["gc_outlook_win_p"]) or 0 for d in last) or 1
    last.sort(key=lambda d: -(f(d["blend_win_norm"]) or 0))
    out["last_paired_board_top"] = [
        {"rider": d["rider_name"], "final_place": i(d["final_place"]), "model": f(d["blend_win_norm"]),
         "book": f(d["book_devig_norm"]), "outlook": (f(d["gc_outlook_win_p"]) or 0) / tot_o}
        for d in sorted(last, key=lambda d: (i(d["final_place"]) or 999))[:8]
    ]
    return out


def tdf_gc_summary() -> dict:
    """Tour GC on the same footing (its builder paired same-day; numbers as in the review)."""
    ms = list(csv.DictReader(open(TDF / "gc_metrics.csv")))
    daily = list(csv.DictReader(open(TDF / "gc_daily.csv")))
    by = defaultdict(list)
    for d in daily:
        by[i(d["through_stage"])].append(d)
    wl_m, wl_b, sp_m, sp_b, o15m, o15b, pm, pb, po = [], [], [], [], [], [], [], [], []
    for m in ms:
        t = i(m["through_stage"])
        rows = by[t]
        win = next((d for d in rows if i(d["final_place"]) == 1), None)
        if win:
            wl_m.append(-math.log(f(win["blend_win_norm"])))
            wl_b.append(-math.log(f(win["book_devig_norm"])))
        sp_m.append(f(m["model_spearman"])); sp_b.append(f(m["book_spearman"]))
        o15m.append(i(m["model_overlap15"])); o15b.append(i(m["book_overlap15"]))
        pm.append(f(m["model_podium_ll"])); pb.append(f(m["book_podium_ll"])); po.append(f(m["gc_outlook_podium_ll"]))
    pm, pb, po = ([x for x in v if x is not None] for v in (pm, pb, po))
    return {"n": len(ms), "winner_ll_model": st.mean(wl_m), "winner_ll_book": st.mean(wl_b),
            "spearman_model": st.mean(sp_m), "spearman_book": st.mean(sp_b),
            "overlap15_model": st.mean(o15m), "overlap15_book": st.mean(o15b),
            "podium_ll_model": st.mean(pm), "podium_ll_book": st.mean(pb), "podium_ll_outlook": st.mean(po)}


# ---------------------------------------------------------------- day keys


def key_weights(day_key: str) -> tuple[float, float]:
    if not day_key:
        return None, None
    d = json.loads(day_key)
    macro = sum(v for k, v in d.items() if k in MACRO_ITEMS)
    return macro, 1 - macro


def main() -> None:
    vis = load_metrics(HERE / "stage_metrics.csv")
    allm = load_all_metrics(HERE / "stage_metrics.csv")
    riders = load_riders(HERE / "stage_riders.csv")
    scored = sorted(vis)
    tdf_vis = load_metrics(TDF / "stage_metrics.csv")
    tdf_stages = sorted(tdf_vis)

    A = {}
    A["stages_scored"] = scored
    A["per_stage"] = per_stage(vis)
    A["panels"] = {
        "all": panel(vis, scored, "all scored stages"),
        "minus_hardman": panel(vis, [s for s in scored if s not in HARDMAN], "minus hard-man {10,15,21}"),
        "minus_climber_breaks": panel(vis, [s for s in scored if s not in CLIMBER_BREAKS], "minus climbers' breaks {7,12,14,20}"),
        "minus_break_won": panel(vis, [s for s in scored if s not in BREAK_WON], "minus all break-won {7,12,14,15,20}"),
        "peloton_settled": panel(vis, [s for s in scored if s not in BREAK_WON | HARDMAN], "peloton / GC-settled only"),
        "hardman_only": panel(vis, sorted(HARDMAN), "hard-man only"),
        "break_won_only": panel(vis, sorted(BREAK_WON), "break-won only"),
        "climber_breaks_only": panel(vis, sorted(CLIMBER_BREAKS), "climbers' breaks only"),
    }
    A["tdf_panels"] = {
        "all": panel(tdf_vis, tdf_stages, "Tour: all"),
        "minus_hardman": panel(tdf_vis, [s for s in tdf_stages if s not in TDF_HARDMAN], "Tour: minus hard-man"),
        "peloton_settled": panel(tdf_vis, [s for s in tdf_stages if s not in TDF_BREAK_WON | TDF_HARDMAN], "Tour: peloton settled"),
        "hardman_only": panel(tdf_vis, sorted(TDF_HARDMAN), "Tour: hard-man only"),
        "break_won_only": panel(tdf_vis, sorted(TDF_BREAK_WON | {4, 9, 21}), "Tour: break-won + hard-man"),
    }
    A["tdf_per_stage"] = per_stage(tdf_vis)

    # ex-ante split by the day key: macro-majority vs residual-majority
    ps = {r["stage"]: r for r in A["per_stage"]}
    macro_maj, resid_maj = [], []
    for s in scored:
        macro, resid = key_weights(ps[s]["day_key"])
        (macro_maj if macro >= 0.5 else resid_maj).append(s)
    A["exante_key"] = {
        "macro_majority": panel(vis, macro_maj, "key put >=0.5 on a macro item"),
        "residual_majority": panel(vis, resid_maj, "key put >0.5 on residual items"),
    }
    # scorecard split
    sc = {r["stage"]: r for r in json.load(open(HERE / "key_scorecard.json"))}
    exact = [s for s in scored if sc.get(s, {}).get("exact")]
    covered_only = [s for s in scored if sc.get(s, {}).get("covered") and not sc[s]["exact"]]
    missed = [s for s in scored if s in sc and not sc[s]["covered"]]
    A["by_key_score"] = {
        "exact": panel(vis, exact, "key exact"),
        "covered_only": panel(vis, covered_only, "key covered, not exact"),
        "missed": panel(vis, missed, "key not covered"),
    }
    A["scorecard"] = {s: {"oracle": sc[s]["oracle_item"], "key": sc[s]["day_key"], "exact": sc[s]["exact"],
                          "covered": sc[s]["covered"], "w": sc[s]["weight_on_true"], "wg_size": sc[s]["wg_size"],
                          "wg_prop": sc[s]["wg_prop"], "winner": sc[s]["winner"],
                          "agent": {k: v for k, v in sc[s].items() if k.startswith("agent_")}}
                      for s in sorted(sc)}

    A["calibration"] = calibration(riders)
    boards = stage_boards(riders)
    A["temperature"] = {
        "all": loo_temperature(boards, scored),
        "minus_hardman": loo_temperature(boards, [s for s in scored if s not in HARDMAN]),
        "minus_break_won": loo_temperature(boards, [s for s in scored if s not in BREAK_WON]),
        "peloton_settled": loo_temperature(boards, [s for s in scored if s not in BREAK_WON | HARDMAN]),
        "hardman_only": loo_temperature(boards, sorted(HARDMAN)),
        "break_won_only": loo_temperature(boards, sorted(BREAK_WON)),
    }
    A["ranking_channel"] = ranking_channel(allm)
    A["hits"] = hits_and_misses(riders)
    A["favourites"] = favourites(riders)

    # hindsight vs morning reads on the winner
    hs = []
    for s in scored:
        h = [m for m in allm[s] if m["is_hindsight"] == "1"]
        if not h:
            continue
        ph = f(h[0]["model_p_winner"])
        hs.append({"stage": s, "hindsight_p": ph, "ew_p": ps[s]["model_p_ew"], "best_p": ps[s]["best_read_p"],
                   "beat_ew": ph > ps[s]["model_p_ew"], "beat_best": ph > ps[s]["best_read_p"]})
    A["hindsight"] = {"rows": hs, "n": len(hs), "beat_ew": sum(r["beat_ew"] for r in hs), "beat_best": sum(r["beat_best"] for r in hs)}

    A["gc"] = gc_summary(HERE / "gc_metrics.csv", HERE / "gc_daily.csv")
    A["tdf_gc"] = tdf_gc_summary()

    (HERE / "analysis.json").write_text(json.dumps(A, indent=1, default=str))

    # ---------------------------------------------------------------- print
    def P(x, d=3):
        return "—" if x is None else f"{x:.{d}f}"
    print("== per stage (equal-weight model vs book on the winner) ==")
    for r in A["per_stage"]:
        print(f"st{r['stage']:>2} {r['winner']:<28} model {P(r['model_p_ew'])} book {P(r['book_p'])} "
              f"delta {r['delta_nats']:+.2f}  best={r['best_read']}({P(r['best_read_p'])}) official={r['official_read']}({P(r['official_p'])}) "
              f"rank m/b {P(r['model_rank_ew'],1)}/{r['book_rank']}  ov15 {P(r['overlap15_model'],1)}/{r['overlap15_book']}  key={r['day_key']}")
    print("\n== panels ==")
    for grp in ("panels", "tdf_panels", "exante_key", "by_key_score"):
        for k, p in A[grp].items():
            o = p["overlap"]
            print(f"{grp}/{k:<22} n={p['n']:>2} winLL m/b {P(p['win_ll_model_ew'])}/{P(p['win_ll_book'])} ({p['win_ll_delta']:+.3f}) "
                  f"best {P(p['win_ll_model_best'])} lr {P(p['win_ll_lambdarank_best'])} pod {P(p['podium_ll_model'],4)}/{P(p['podium_ll_book'],4)} (n{p['podium_n']}) "
                  f"ov3 {o[3]['delta_pp']:+.1f} ov5 {o[5]['delta_pp']:+.1f} ov10 {o[10]['delta_pp']:+.1f} ov15 {o[15]['delta_pp']:+.1f} "
                  f"sp {P(p['spearman_model'])}/{P(p['spearman_book'])} toppick {p['top_pick_wins_model']}/{p['top_pick_wins_book']} of {p['reads']} deficit {p['total_deficit_nats']:+.2f}")
    print("\n== calibration ==")
    for h, rows in A["calibration"].items():
        print(h, " | ".join(f"{r['band']}: {r['stated']:.3f}->{r['realised']:.3f} (n{r['n']})" for r in rows))
    print("\n== temperature LOO ==")
    for k, t in A["temperature"].items():
        print(f"{k:<18} n={t['n']} raw {t['raw']:.3f} -> cal {t['calibrated']:.3f} | book {t['book']:.3f} | gap {t['gap_raw']:+.3f} -> {t['gap_cal']:+.3f} | T {t['T_in_sample']:.2f} (loo med {t['T_loo_median']:.2f})")
    print("\n== ranking channel ==")
    for r in A["ranking_channel"]["per_stage"]:
        print(f"st{r['stage']:>2} {r['board']:<10} pub15 ew {r['pub15_ew']:.1f} prod15 ew {r['prod15_ew']:.1f} | official pub/prod {r['pub15_official']}/{r['prod15_official']} best-branch {r['pub15_best']} | book15 {r['book15']} | hind {r['hind15']} || 10: pub {r['pub10_ew']:.1f} prod {r['prod10_ew']:.1f} book {r['book10']}")
    print("totals", json.dumps(A["ranking_channel"]["totals"]))
    print("\n== hindsight ==", A["hindsight"]["n"], "beat_ew", A["hindsight"]["beat_ew"], "beat_best", A["hindsight"]["beat_best"])
    print("\n== podium finishers: model over book ==")
    for r in A["hits"]["podium_model_over_book"]:
        print(f"st{r['stage']:>2} {r['rider']:<28} P{r['place']} model {r['model_p']:.3f} book {r['book_p']:.3f} x{r['ratio']:.1f}")
    print("== podium finishers: book over model ==")
    for r in A["hits"]["podium_book_over_model"]:
        print(f"st{r['stage']:>2} {r['rider']:<28} P{r['place']} model {r['model_p']:.3f} book {r['book_p']:.3f} x{r['ratio']:.2f}")
    print("\n== favourites ==")
    for r in A["favourites"]:
        print(f"st{r['stage']:>2} model fav {r['model_fav']:<24} {r['model_fav_p']:.3f} (book {P(r['model_fav_book_p'])}) -> P{r['model_fav_place']} | book fav {r['book_fav']:<24} {P(r['book_fav_p'])} (model {r['book_fav_model_p']:.3f}) -> P{r['book_fav_place']}")
    print("\n== GC ==")
    for b in A["gc"]["boards"]:
        print(f"thru {b['through_stage']:>2} {b['pairing']:<12} Mas m/b/o {P(b['winner_model_p'])}/{P(b['winner_book_p'])}/{P(b['winner_outlook_p'])} "
              f"sp {P(b['spearman_model'])}/{P(b['spearman_book'])}/{P(b['spearman_outlook'])} ov15 {b['overlap15_model']}/{b['overlap15_book']}/{b['overlap15_outlook']} "
              f"ov5 {b['overlap5_model']}/{b['overlap5_book']}/{b['overlap5_outlook']} pod {P(b['podium_ll_model'],4)}/{P(b['podium_ll_book'],4)}/{P(b['podium_ll_outlook'],4)} leaders {b['model_leader']}/{b['book_leader']}/{b['outlook_leader']}")
    for k in ("all_paired", "pre_abandon", "post_abandon", "post_abandon_all"):
        print(k, json.dumps({kk: (round(v, 4) if isinstance(v, float) else v) for kk, v in A["gc"][k].items()}))
    print("pogacar", A["gc"]["pogacar_pre_abandon"])
    print("last board top", A["gc"]["last_paired_board_top"])
    print("tdf gc", json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in A["tdf_gc"].items()}))


if __name__ == "__main__":
    main()
