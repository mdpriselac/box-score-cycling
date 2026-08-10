"""Assemble the post-Tour comparative review dataset: model vs book vs road.

Reads only the archived artefacts in this folder (predictions/, odds/, results/)
plus prediction_log for the daily GC track, and writes tidy CSVs to review/.

    uv run python performance_eval/tour-de-france-2026/build_review_dataset.py

Outputs (review/):
  stage_riders.csv      one row per stage x scenario x rider: every model head,
                        the devigged book price, and the rider's actual finish.
  stage_metrics.csv     one row per stage x scenario: winner pricing, win-market
                        log loss / Brier for model vs book, top-pick outcomes.
  gc_daily.csv          one row per state-through-stage x rider: the logged GC
                        board, that morning's devigged book GC price, final place.
  gc_final.csv          final GC standings joined to the last model + book board.

Probability convention (see DAILY_RUNBOOK step 8): blend_win_p is a set of
per-rider marginals and does NOT sum to 1. Every comparison against the book
here uses the renormalized column (*_norm); the raw columns are kept for
reference but must never be compared to book_devig directly.
"""

from __future__ import annotations

import csv
import glob
import json
import math
import sqlite3
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "review"
DB = ROOT / "cycling_project/webscrape_tools/database/database/cycling_races.db"

GC_EVENT_ID = "1024452735"
GC_TAG_SUFFIX = "|gc_tdf_editions_state"
STAGES = range(2, 22)  # stage 1 was not previewed (no scenarios.json)

PROB_COLS = [
    "prob_win",
    "prob_podium",
    "prob_top5",
    "prob_top15",
    "lambdarank_win_p",
    "blend_win_p",
    "dnf_p",
    "dnf_adj_win_p",
    "dnf_adj_podium_p",
    "dnf_adj_top5_p",
    "dnf_adj_top15_p",
]


# FirstCycling renames riders mid-season; our prediction JSONs carry the older
# spelling. Keys and values are both normalized forms (see norm_name).
NAME_ALIASES = {
    "derek gee west": "derek gee",
    "guillaume guyonnet martin": "guillaume martin",
    "luke plapp": "lucas plapp",
}


def norm_name(name: str) -> str:
    """Order- and accent-insensitive key: 'Merlier Tim' == 'Tim Merlier'."""
    s = unicodedata.normalize("NFKD", name or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = "".join(c if c.isalnum() or c.isspace() else " " for c in s)
    key = " ".join(sorted(s.split()))
    return NAME_ALIASES.get(key, key)


def renorm(rows: list[dict], col: str, mass: float = 1.0) -> dict[int, float]:
    """Scale a column of per-rider marginals to a known total mass.

    Win markets carry mass 1, podium 3, top-5 5, top-15 15 — the model heads are
    independent marginals and do not obey that, so every depth comparison against
    the book renormalizes first.
    """
    total = sum(r.get(col) or 0.0 for r in rows)
    if total <= 0:
        return {i: None for i in range(len(rows))}
    return {i: (r.get(col) or 0.0) * mass / total for i, r in enumerate(rows)}


def bernoulli_ll(pairs: list[tuple[float, int]]) -> float | None:
    """Mean per-rider Bernoulli log loss for a set of (prob, label) marginals."""
    pairs = [(p, y) for p, y in pairs if p is not None]
    if not pairs:
        return None
    eps = 1e-9
    return -sum(
        y * math.log(min(max(p, eps), 1 - eps))
        + (1 - y) * math.log(1 - min(max(p, eps), 1 - eps))
        for p, y in pairs
    ) / len(pairs)


def overlap_at_k(rows: list[dict], col: str, k: int) -> int | None:
    """How many of the actual top k the board also had in its top k."""
    scored = [r for r in rows if r.get(col) is not None]
    if not scored:
        return None
    board = sorted(scored, key=lambda r: -(r[col] or 0.0))[:k]
    return sum(1 for r in board if r["place"] and r["place"] <= k)


def mean_board_rank_of_actual(rows: list[dict], col: str, k: int) -> float | None:
    """Mean position on the board of the riders who actually finished top k."""
    scored = [r for r in rows if r.get(col) is not None]
    if not scored:
        return None
    order = sorted(scored, key=lambda r: -(r[col] or 0.0))
    rank = {id(r): i + 1 for i, r in enumerate(order)}
    hits = [rank[id(r)] for r in order if r["place"] and r["place"] <= k]
    return sum(hits) / len(hits) if hits else None


def spearman(rows: list[dict], col: str) -> float | None:
    """Rank correlation between a board and the actual finishing order."""
    scored = [r for r in rows if r.get(col) is not None and r["place"]]
    n = len(scored)
    if n < 3:
        return None
    board = {id(r): i for i, r in enumerate(sorted(scored, key=lambda r: -(r[col] or 0.0)))}
    actual = {id(r): i for i, r in enumerate(sorted(scored, key=lambda r: r["place"]))}
    d2 = sum((board[id(r)] - actual[id(r)]) ** 2 for r in scored)
    return 1 - 6 * d2 / (n * (n * n - 1))


def read_csv(path: Path) -> list[dict]:
    with path.open() as fh:
        return list(csv.DictReader(fh))


def book_market(
    capture: str, event_id: str, offer_type: str, date_dir: str | None = None
) -> dict[str, float] | None:
    """{normalized rider name: devigged prob} for one betoffer of one event.

    offer_type: 'Winnaar' (win, mass 1), '(1-3)' (podium, mass 3), '(1-10)'.
    Falls back to any other capture on the same date if the named file lacks it.
    """
    candidates = [HERE / "odds" / capture]
    day = date_dir or capture.split("/")[0]
    candidates += sorted(Path(p) for p in glob.glob(str(HERE / "odds" / day / "markets_*.json")))
    for path in candidates:
        if not path.exists():
            continue
        ev = json.loads(path.read_text()).get(str(event_id))
        if not ev:
            continue
        for b in ev["betoffers"]:
            if b.get("bet_offer_type") != offer_type:
                continue
            if offer_type == "Winnaar" and b.get("criterion") != "Winnaar":
                continue  # team/country novelty markets reuse the 'Winnaar' type
            return {norm_name(o["name"]): o["devig"] for o in b["outcomes"]}
    return None


def attach_book(rows: list[dict], market: dict[str, float] | None, mass: float) -> None:
    """Floor-fill riders the book did not list, then rescale to the market mass.

    The book prices 92-142 of the ~170 starters; the rest are simply absent. We
    give them the longest price actually on that board rather than zero (which
    would make any log loss infinite the moment an unlisted rider placed), flag
    them with book_listed=0, and rescale the whole field back to `mass`.
    """
    key = "book_podium" if mass == 3 else ("book_top10" if mass == 10 else "book_win")
    if not market:
        for r in rows:
            r[key] = None
            r[key + "_listed"] = None
        return
    floor = min(market.values())
    raw = []
    for r in rows:
        p = market.get(norm_name(r["rider_name"]))
        r[key + "_listed"] = int(p is not None)
        raw.append(p if p is not None else floor)
    total = sum(raw)
    for r, p in zip(rows, raw):
        r[key] = p * mass / total


# ---------------------------------------------------------------- stage side


def load_stage_results(stage: int) -> tuple[dict, dict]:
    """(by normalized name -> result row, meta)."""
    path = HERE / f"results/stage_{stage:02d}/results.csv"
    if not path.exists():
        return {}, {}
    by_name, meta = {}, {}
    for row in read_csv(path):
        place = row["place"]
        rec = {
            "place": int(place) if place.isdigit() else None,
            "place_raw": place,
            "gap": float(row["gap"]) if row["gap"] not in ("", None) else None,
            "fc_rider_id": row["rider_id"],
        }
        by_name[norm_name(row["name"])] = rec
        if rec["place"] == 1:
            meta["winner"] = row["name"]
    return by_name, meta


def stage_rows() -> tuple[list[dict], list[dict], list[str]]:
    riders_out: list[dict] = []
    metrics_out: list[dict] = []
    warnings: list[str] = []

    for stage in STAGES:
        cfg_path = HERE / f"predictions/stage_{stage:02d}/scenarios.json"
        if not cfg_path.exists():
            warnings.append(f"stage {stage}: no scenarios.json")
            continue
        cfg = json.loads(cfg_path.read_text())
        results, rmeta = load_stage_results(stage)
        book_podium = book_market(
            cfg.get("odds_capture", ""), cfg.get("event_id", ""), "(1-3)"
        )
        if book_podium is None:
            warnings.append(f"stage {stage}: no book podium market — rank metrics only")
        if not results:
            warnings.append(f"stage {stage}: no results.csv")

        for key, scen_cfg in cfg.get("scenarios", {}).items():
            pred_path = cfg_path.parent / f"{key}.json"
            if not pred_path.exists():
                warnings.append(f"stage {stage}/{key}: no prediction json")
                continue
            pred = json.loads(pred_path.read_text())
            rows = pred["riders"]

            blend_n = renorm(rows, "blend_win_p")
            dnfadj_n = renorm(rows, "dnf_adj_win_p")
            book_n = renorm(rows, "book_devig")
            # depth heads renormalized to their market mass (3 podium, 5, 15)
            podium_n = renorm(rows, "dnf_adj_podium_p", 3.0)
            top5_n = renorm(rows, "dnf_adj_top5_p", 5.0)
            top15_n = renorm(rows, "dnf_adj_top15_p", 15.0)
            lr_mass = sum(r.get("lambdarank_win_p") or 0.0 for r in rows)
            blend_mass = sum(r.get("blend_win_p") or 0.0 for r in rows)
            book_mass = sum(r.get("book_devig") or 0.0 for r in rows)

            is_hindsight = key == "hindsight"
            is_hidden = bool(scen_cfg.get("hidden"))

            unmatched = 0
            enriched = []
            for i, r in enumerate(rows):
                res = results.get(norm_name(r["rider_name"]))
                if res is None:
                    unmatched += 1
                rec = {
                    "stage": stage,
                    "date": cfg.get("date"),
                    "scenario": key,
                    "scenario_label": scen_cfg.get("short") or scen_cfg.get("label"),
                    "is_hindsight": int(is_hindsight),
                    "is_hidden": int(is_hidden),
                    "rider_id": r["rider_id"],
                    "rider_name": r["rider_name"],
                    "team": r.get("team_name"),
                    "predicted_rank": r.get("predicted_rank"),
                    "is_contender": int(bool(r.get("is_contender"))),
                    **{c: r.get(c) for c in PROB_COLS},
                    "blend_win_norm": blend_n[i],
                    "dnf_adj_win_norm": dnfadj_n[i],
                    "podium_norm": podium_n[i],
                    "top5_norm": top5_n[i],
                    "top15_norm": top15_n[i],
                    "book_odds": r.get("book_odds"),
                    "book_devig": r.get("book_devig"),
                    "book_devig_norm": book_n[i],
                    "place": res["place"] if res else None,
                    "place_raw": res["place_raw"] if res else "",
                    "gap": res["gap"] if res else None,
                    "finished": int(bool(res and res["place"])),
                    "is_winner": int(bool(res and res["place"] == 1)),
                    "in_top3": int(bool(res and res["place"] and res["place"] <= 3)),
                    "in_top5": int(bool(res and res["place"] and res["place"] <= 5)),
                    "in_top10": int(bool(res and res["place"] and res["place"] <= 10)),
                    "in_top15": int(bool(res and res["place"] and res["place"] <= 15)),
                }
                enriched.append(rec)

            attach_book(enriched, book_podium, 3.0)
            riders_out.extend(enriched)

            if unmatched:
                warnings.append(
                    f"stage {stage}/{key}: {unmatched}/{len(rows)} predicted riders "
                    "absent from results (DNF/DNS or name drift)"
                )

            # ---- per-scenario metrics
            winner = next((e for e in enriched if e["is_winner"]), None)
            m = {
                "stage": stage,
                "scenario": key,
                "scenario_label": scen_cfg.get("short") or scen_cfg.get("label"),
                "is_hindsight": int(is_hindsight),
                "is_hidden": int(is_hidden),
                "n_riders": len(rows),
                "winner": rmeta.get("winner", ""),
                "blend_mass": round(blend_mass, 4),
                "lambdarank_mass": round(lr_mass, 4),
                "book_mass": round(book_mass, 4),
            }

            def rank_of(rec, col, desc=True):
                vals = sorted(
                    (e.get(col) or 0.0 for e in enriched), reverse=desc
                )
                return vals.index(rec.get(col) or 0.0) + 1

            if winner:
                for col, out in (
                    ("blend_win_norm", "model_p_winner"),
                    ("dnf_adj_win_norm", "dnfadj_p_winner"),
                    ("lambdarank_win_p", "lambdarank_p_winner"),
                    ("book_devig_norm", "book_p_winner"),
                ):
                    p = winner.get(col)
                    m[out] = p
                    m[out.replace("p_winner", "logloss")] = (
                        -math.log(max(p, 1e-9)) if p is not None else None
                    )
                m["model_rank_of_winner"] = rank_of(winner, "blend_win_norm")
                m["book_rank_of_winner"] = rank_of(winner, "book_devig_norm")
                m["edge_winner"] = (
                    winner["blend_win_norm"] - winner["book_devig_norm"]
                    if winner["blend_win_norm"] is not None
                    and winner["book_devig_norm"] is not None
                    else None
                )
                # Brier over the field on the win market
                for col, out in (
                    ("blend_win_norm", "model_brier"),
                    ("lambdarank_win_p", "lambdarank_brier"),
                    ("book_devig_norm", "book_brier"),
                ):
                    m[out] = sum(
                        ((e.get(col) or 0.0) - e["is_winner"]) ** 2 for e in enriched
                    )

            # ---- depth: how did the two boards do across the top 3/5/10/15?
            # Probability comparison where a book market exists (podium only),
            # rank comparison at every depth using the win-odds ordering.
            m["podium_market"] = int(book_podium is not None)
            m["model_podium_ll"] = bernoulli_ll(
                [(e["podium_norm"], e["in_top3"]) for e in enriched]
            )
            m["book_podium_ll"] = bernoulli_ll(
                [(e.get("book_podium"), e["in_top3"]) for e in enriched]
            )
            m["model_top5_ll"] = bernoulli_ll(
                [(e["top5_norm"], e["in_top5"]) for e in enriched]
            )
            m["model_top15_ll"] = bernoulli_ll(
                [(e["top15_norm"], e["in_top15"]) for e in enriched]
            )
            for k in (3, 5, 10, 15):
                m[f"model_overlap{k}"] = overlap_at_k(enriched, "blend_win_norm", k)
                m[f"book_overlap{k}"] = overlap_at_k(enriched, "book_devig_norm", k)
                m[f"model_meanrank_top{k}"] = mean_board_rank_of_actual(
                    enriched, "blend_win_norm", k
                )
                m[f"book_meanrank_top{k}"] = mean_board_rank_of_actual(
                    enriched, "book_devig_norm", k
                )
            # depth-head orderings can disagree with the win ordering
            m["model_overlap10_top15head"] = overlap_at_k(enriched, "top15_norm", 10)
            m["model_spearman"] = spearman(enriched, "blend_win_norm")
            m["book_spearman"] = spearman(enriched, "book_devig_norm")

            top_model = max(enriched, key=lambda e: e.get("blend_win_norm") or 0.0)
            top_book = max(enriched, key=lambda e: e.get("book_devig_norm") or 0.0)
            m["model_top_pick"] = top_model["rider_name"]
            m["model_top_pick_place"] = top_model["place"]
            m["book_top_pick"] = top_book["rider_name"]
            m["book_top_pick_place"] = top_book["place"]
            m["model_top_pick_won"] = int(top_model["is_winner"] == 1)
            m["book_top_pick_won"] = int(top_book["is_winner"] == 1)
            metrics_out.append(m)

    return riders_out, metrics_out, warnings


# ------------------------------------------------------------------- GC side


def book_gc_by_date() -> dict[str, dict[str, dict[str, float]]]:
    """date -> offer_type -> {normalized rider name: devig} (latest capture wins).

    The GC event carries win, podium ('(1-3)') and top-10 ('(1-10)') markets;
    the top-10 one only appears in some captures.
    """
    out: dict[str, dict[str, dict[str, float]]] = {}
    for path in sorted(glob.glob(str(HERE / "odds/*/markets_*.json"))):
        date = Path(path).parent.name
        ev = json.loads(Path(path).read_text()).get(GC_EVENT_ID)
        if not ev:
            continue
        for b in ev["betoffers"]:
            t = b.get("bet_offer_type")
            # the win + podium offers use criterion 'Winnaar'; the top-10 offer
            # is labelled 'Eindigt in de Top 10', so key on the offer type.
            if t == "Winnaar" and b.get("criterion") != "Winnaar":
                continue
            if t in ("Winnaar", "(1-3)", "(1-10)"):
                out.setdefault(date, {})[t] = {
                    norm_name(o["name"]): o["devig"] for o in b["outcomes"]
                }
    return out


def gc_board_metrics(through: int, date: str, book_date: str, board: list[dict]) -> dict:
    """Depth scoring for one daily GC board against the final classification."""
    m = {
        "through_stage": through,
        "date": date,
        "book_date": book_date,
        "n_riders": len(board),
        "model_win_ll": bernoulli_ll(
            [(e["blend_win_norm"], int(e["final_place"] == 1)) for e in board]
        ),
        "book_win_ll": bernoulli_ll(
            [(e["book_devig_norm"], int(e["final_place"] == 1)) for e in board]
        ),
        "model_podium_ll": bernoulli_ll([(e["podium_norm"], e["in_top3"]) for e in board]),
        "book_podium_ll": bernoulli_ll([(e.get("book_podium"), e["in_top3"]) for e in board]),
        "model_top10_ll": bernoulli_ll(
            [(e["top15_norm"] * 10 / 15, e["in_top10"]) for e in board]
        ),
        "book_top10_ll": bernoulli_ll([(e.get("book_top10"), e["in_top10"]) for e in board]),
        # the outlook head is per-rider position safety, not a distribution:
        # renormalize to the market mass before scoring it like one
        "gc_outlook_podium_ll": bernoulli_ll(
            list(zip(renorm(board, "gc_outlook_podium_p", 3.0).values(),
                     [e["in_top3"] for e in board]))
        ),
        "gc_outlook_top5_ll": bernoulli_ll(
            list(zip(renorm(board, "gc_outlook_top5_p", 5.0).values(),
                     [e["in_top5"] for e in board]))
        ),
        "podium_market": int(any(e.get("book_podium") is not None for e in board)),
        "top10_market": int(any(e.get("book_top10") is not None for e in board)),
    }
    for k in (3, 5, 10, 15):
        m[f"model_overlap{k}"] = overlap_at_k(board, "blend_win_norm", k)
        m[f"book_overlap{k}"] = overlap_at_k(board, "book_devig_norm", k)
        m[f"outlook_overlap{k}"] = overlap_at_k(board, "gc_outlook_top5_p", k)
    m["model_spearman"] = spearman(board, "blend_win_norm")
    m["book_spearman"] = spearman(board, "book_devig_norm")
    return m


def gc_rows() -> tuple[list[dict], list[dict], list[dict], list[str]]:
    warnings: list[str] = []
    gc_metrics: list[dict] = []
    final = {}
    fpath = HERE / "results/race_page/standings_2026-07-26.csv"
    for row in read_csv(fpath):
        final[norm_name(row["name"])] = {
            "final_place": int(row["place"]) if row["place"].isdigit() else None,
            "final_place_raw": row["place"],
            "final_gap": float(row["gap"]) if row["gap"] not in ("", None) else None,
        }

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    runs = con.execute(
        """
        SELECT state_through_stage, MAX(predicted_at) AS at
        FROM prediction_log
        WHERE model_version LIKE ?
        GROUP BY state_through_stage
        ORDER BY state_through_stage
        """,
        (f"%{GC_TAG_SUFFIX}",),
    ).fetchall()

    book = book_gc_by_date()
    daily: list[dict] = []
    for run in runs:
        rows = con.execute(
            """
            SELECT rider_name, rider_id, multiclass_win_p, multiclass_podium_p,
                   multiclass_top5_p, multiclass_top15_p, lambdarank_win_p,
                   blend_win_p, dnf_p, dnf_adj_win_p, dnf_adj_podium_p,
                   dnf_adj_top5_p, dnf_adj_top15_p, gc_outlook_win_p,
                   gc_outlook_podium_p, gc_outlook_top5_p, gc_outlook_top15_p,
                   predicted_at
            FROM prediction_log
            WHERE model_version LIKE ? AND predicted_at = ?
            """,
            (f"%{GC_TAG_SUFFIX}", run["at"]),
        ).fetchall()
        rows = [dict(r) for r in rows]
        date = str(run["at"])[:10]
        bookday = book.get(date, {})
        book_date = date
        if not bookday:
            # Some captures missed the GC event entirely (e.g. 2026-07-25 archived
            # only the stage 21 market): fall back to the most recent prior board.
            prior = [d for d in sorted(book) if d < date]
            if prior:
                book_date = prior[-1]
                bookday = book[book_date]
            warnings.append(
                f"gc through stage {run['state_through_stage']}: no book GC market for "
                f"{date}" + (f" — using {book_date}" if bookday else "")
            )
        win_mkt = bookday.get("Winnaar", {})
        book_mass = sum(win_mkt.values()) or None

        blend_n = renorm(rows, "blend_win_p")
        podium_n = renorm(rows, "dnf_adj_podium_p", 3.0)
        top5_n = renorm(rows, "dnf_adj_top5_p", 5.0)
        top15_n = renorm(rows, "dnf_adj_top15_p", 15.0)
        board = []
        for i, r in enumerate(rows):
            key = norm_name(r["rider_name"])
            bp = win_mkt.get(key)
            fin = final.get(
                key, {"final_place": None, "final_place_raw": "", "final_gap": None}
            )
            fp = fin["final_place"]
            board.append(
                {
                    "through_stage": run["state_through_stage"],
                    "predicted_at": r["predicted_at"],
                    "date": date,
                    "book_date": book_date,
                    "rider_id": r["rider_id"],
                    "rider_name": r["rider_name"],
                    **{
                        k: r[k]
                        for k in r
                        if k not in ("rider_id", "rider_name", "predicted_at")
                    },
                    "blend_win_norm": blend_n[i],
                    "podium_norm": podium_n[i],
                    "top5_norm": top5_n[i],
                    "top15_norm": top15_n[i],
                    "book_devig": bp,
                    "book_devig_norm": (bp / book_mass) if bp and book_mass else None,
                    **fin,
                    "place": fp,  # alias so the shared rank helpers work
                    "in_top3": int(bool(fp and fp <= 3)),
                    "in_top5": int(bool(fp and fp <= 5)),
                    "in_top10": int(bool(fp and fp <= 10)),
                    "in_top15": int(bool(fp and fp <= 15)),
                }
            )
        attach_book(board, bookday.get("(1-3)"), 3.0)
        attach_book(board, bookday.get("(1-10)"), 10.0)
        daily.extend(board)
        gc_metrics.append(gc_board_metrics(run["state_through_stage"], date, book_date, board))
    con.close()

    # final table: last board + final standings, one row per finisher
    last_stage = max((d["through_stage"] or 0) for d in daily) if daily else None
    last = {norm_name(d["rider_name"]): d for d in daily if d["through_stage"] == last_stage}
    final_rows = []
    for row in read_csv(fpath):
        key = norm_name(row["name"])
        d = last.get(key, {})
        final_rows.append(
            {
                "final_place": row["place"],
                "rider_name": row["name"],
                "team": row["team"],
                "final_gap": row["gap"],
                "model_through_stage": d.get("through_stage"),
                "model_blend_win_norm": d.get("blend_win_norm"),
                "model_blend_win_p": d.get("blend_win_p"),
                "model_lambdarank_win_p": d.get("lambdarank_win_p"),
                "model_dnf_adj_win_p": d.get("dnf_adj_win_p"),
                "gc_outlook_win_p": d.get("gc_outlook_win_p"),
                "gc_outlook_podium_p": d.get("gc_outlook_podium_p"),
                "gc_outlook_top5_p": d.get("gc_outlook_top5_p"),
                "gc_outlook_top15_p": d.get("gc_outlook_top15_p"),
                "book_devig_norm": d.get("book_devig_norm"),
            }
        )
    return daily, final_rows, gc_metrics, warnings


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        print(f"  (skipped {path.name}: no rows)")
        return
    cols: list[str] = []
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"  {path.relative_to(ROOT)}  ({len(rows)} rows, {len(cols)} cols)")


def main() -> None:
    OUT.mkdir(exist_ok=True)
    riders, metrics, warn1 = stage_rows()
    daily, final_rows, gc_metrics, warn2 = gc_rows()
    print("wrote:")
    write_csv(OUT / "stage_riders.csv", riders)
    write_csv(OUT / "stage_metrics.csv", metrics)
    write_csv(OUT / "gc_daily.csv", daily)
    write_csv(OUT / "gc_metrics.csv", gc_metrics)
    write_csv(OUT / "gc_final.csv", final_rows)
    warnings = warn1 + warn2
    if warnings:
        print(f"\n{len(warnings)} notes:")
        for w in warnings:
            print(f"  - {w}")


if __name__ == "__main__":
    main()
