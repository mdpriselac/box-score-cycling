"""Assemble a campaign's post-race comparative review dataset: model vs book vs road.

Reads only the archived artefacts in the campaign folder (predictions/, odds/,
results/, campaign.json) plus prediction_log for the daily GC track, and writes
tidy CSVs to <campaign>/review/.

    uv run python performance_eval/tour-de-france-2026/build_review_dataset.py
    uv run python performance_eval/tour-de-france-2026/build_review_dataset.py \
        --campaign performance_eval/vuelta-2026

There is ONE copy of this script (here, beside the other campaign-portable
capture scripts); a campaign is selected by flag. Without the flag it builds the
Tour's own dataset exactly as it did when the Tour was reviewed.

Outputs (<campaign>/review/):
  stage_riders.csv      one row per stage x scenario x rider: every model head,
                        the devigged book price, the rider's actual finish, and
                        (where the day-menu channel ran) the published ranking
                        next to the production ranking.
  stage_metrics.csv     one row per stage x scenario: winner pricing, win-market
                        log loss / Brier for model vs book, depth metrics, and
                        the ranking-channel comparison (published vs production
                        vs book top-k retrieval).
  gc_daily.csv          one row per state-through-stage x rider: the logged GC
                        board, the paired devigged book GC price, final place.
  gc_metrics.csv        one row per state-through-stage board.
  gc_final.csv          final GC standings joined to the last model + book board.

Probability convention (see DAILY_RUNBOOK step 8): blend_win_p is a set of
per-rider marginals and does NOT sum to 1. Every comparison against the book
here uses the renormalized column (*_norm); the raw columns are kept for
reference but must never be compared to book_devig directly.

What is and is not scored:
  * a stage config marked `post_hoc: true` (a missed morning, reconstructed
    afterwards) is NOT a read and is skipped entirely;
  * a stage with no results.csv (cancelled) is skipped;
  * `hindsight` scenarios and `hidden` anchors are kept in stage_riders /
    stage_metrics but flagged, exactly as before — keep them out of any
    settlement number;
  * the GC board logged after the final stage (state count == number of raced
    stages) is kept in gc_daily with is_final=1 and excluded from gc_metrics.

GC book pairing (`--gc-book`): the GC boards are logged in the evening after a
stage (UTC in prediction_log). `next` (default) pairs each board with the
earliest odds capture whose `fetched_at_utc` is at or after the board was
logged — the next morning's book, which knows the same stages the board does.
`same-day` is the original Tour convention (the capture dated the same calendar
day as the board, which is usually the morning BEFORE that stage and so gives
the model a one-stage head start). Both are recorded per board in gc_metrics.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import sqlite3
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DB = ROOT / "cycling_project/webscrape_tools/database/database/cycling_races.db"

# Tour defaults, used when the campaign folder carries no campaign.json /
# gc config to read them from (the Tour campaign predates both).
TDF_GC_EVENT_ID = "1024452735"
TDF_GC_TAG_SUFFIX = "|gc_tdf_editions_state"
TDF_FINAL_STANDINGS = "standings_2026-07-26.csv"

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
    # Vuelta 2026: the results pages carry the short form of these names
    "mathias norsgaard sunekær": "mathias norsgaard",
    "asensio faura jose luis": "faura jose luis",
    "guillermo juan martinez": "juan martinez",
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


def overlap_at_k(rows: list[dict], col: str, k: int, ascending: bool = False) -> int | None:
    """How many of the actual top k the board also had in its top k.

    `col` is a score (higher = better) unless ascending=True, in which case it
    is a rank (1 = best) and missing values sort last.
    """
    scored = [r for r in rows if r.get(col) is not None]
    if not scored:
        return None
    if ascending:
        board = sorted(scored, key=lambda r: r[col])[:k]
    else:
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


# ------------------------------------------------------------------ campaign


class Campaign:
    """Everything the builder needs to know about one campaign folder."""

    def __init__(self, path: Path, gc_book: str):
        self.dir = path.resolve()
        self.out = self.dir / "review"
        self.gc_book = gc_book
        meta_path = self.dir / "campaign.json"
        self.meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        self.void_stages = set(self.meta.get("void_stages") or [])
        self.end_date = self.meta.get("end_date")

        gc_cfg_path = self.dir / "predictions/gc/scenarios.json"
        gc_cfg = json.loads(gc_cfg_path.read_text()) if gc_cfg_path.exists() else {}
        tags = [s.get("tag") for s in gc_cfg.get("scenarios", {}).values() if s.get("tag")]
        self.gc_tag_suffix = f"|{tags[0]}" if tags else TDF_GC_TAG_SUFFIX
        self.gc_event_id = str(
            (self.meta.get("kambi_event_ids") or {}).get("gc")
            or gc_cfg.get("event_id")
            or TDF_GC_EVENT_ID
        )
        if not self.void_stages and gc_cfg.get("void_stages"):
            self.void_stages = set(gc_cfg["void_stages"])

        # stages with a prediction folder, in order
        self.stage_dirs = sorted(
            (Path(p) for p in glob.glob(str(self.dir / "predictions/stage_*"))),
            key=lambda p: int(p.name.split("_")[1]),
        )
        # raced stage numbers (for the count -> stage mapping)
        n_stages = len(self.meta.get("stages") or []) or max(
            (int(p.name.split("_")[1]) for p in self.stage_dirs), default=0
        )
        self.raced_stages = [s for s in range(1, n_stages + 1) if s not in self.void_stages]
        self.stage_dates = {
            int(st["number"]): st["date"] for st in (self.meta.get("stages") or [])
            if st.get("date")
        }
        for sdir in self.stage_dirs:  # configs fill any gap
            try:
                cfg = json.loads((sdir / "scenarios.json").read_text())
            except (OSError, json.JSONDecodeError):
                continue
            self.stage_dates.setdefault(int(sdir.name.split("_")[1]), cfg.get("date"))

    def next_raced_stage(self, stage: int | None) -> int | None:
        later = [s for s in self.raced_stages if stage is not None and s > stage]
        return later[0] if later else None

    # state_through_stage in prediction_log is a COUNT of stages that fed the
    # state, not a stage number — with a cancelled stage the two diverge.
    def count_to_stage(self, count: int | None) -> int | None:
        if count is None or count <= 0:
            return None
        if count > len(self.raced_stages):
            return None
        return self.raced_stages[count - 1]

    def final_standings_path(self) -> Path:
        files = sorted(glob.glob(str(self.dir / "results/race_page/standings_*.csv")))
        if not files:
            raise FileNotFoundError("no results/race_page/standings_*.csv")
        if self.end_date:
            after = [f for f in files if Path(f).stem.split("_")[1] >= self.end_date]
            if after:
                return Path(after[0])
        tdf = self.dir / "results/race_page" / TDF_FINAL_STANDINGS
        if tdf.exists():
            return tdf
        return Path(files[-1])


def book_market(
    camp: Campaign, capture: str, event_id: str, offer_type: str, date_dir: str | None = None
) -> dict[str, float] | None:
    """{normalized rider name: devigged prob} for one betoffer of one event.

    offer_type: 'Winnaar' (win, mass 1), '(1-3)' (podium, mass 3), '(1-10)'.
    Falls back to any other capture on the same date if the named file lacks it.
    """
    if not capture:
        return None
    candidates = [camp.dir / "odds" / capture]
    day = date_dir or capture.split("/")[0]
    candidates += sorted(Path(p) for p in glob.glob(str(camp.dir / "odds" / day / "markets_*.json")))
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


def load_stage_results(camp: Campaign, stage: int) -> tuple[dict, dict]:
    """(by normalized name -> result row, meta)."""
    path = camp.dir / f"results/stage_{stage:02d}/results.csv"
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


def stage_rows(camp: Campaign) -> tuple[list[dict], list[dict], list[str]]:
    riders_out: list[dict] = []
    metrics_out: list[dict] = []
    warnings: list[str] = []

    for sdir in camp.stage_dirs:
        stage = int(sdir.name.split("_")[1])
        cfg_path = sdir / "scenarios.json"
        if not cfg_path.exists():
            warnings.append(f"stage {stage}: no scenarios.json")
            continue
        cfg = json.loads(cfg_path.read_text())
        if cfg.get("post_hoc"):
            warnings.append(f"stage {stage}: post_hoc config (missed morning) — not a read, skipped")
            continue
        results, rmeta = load_stage_results(camp, stage)
        if not results:
            warnings.append(f"stage {stage}: no results.csv (cancelled or unsettled) — skipped")
            continue
        book_podium = book_market(
            camp, cfg.get("odds_capture", ""), cfg.get("event_id", ""), "(1-3)"
        )
        if book_podium is None:
            warnings.append(f"stage {stage}: no book podium market — rank metrics only")
        root_key = cfg.get("day_key")

        for key, scen_cfg in cfg.get("scenarios", {}).items():
            pred_path = sdir / f"{key}.json"
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
            board_kind = pred.get("board") or "production"
            day_key = pred.get("day_key") or scen_cfg.get("day_key") or root_key

            unmatched = 0
            enriched = []
            for i, r in enumerate(rows):
                res = results.get(norm_name(r["rider_name"]))
                if res is None:
                    unmatched += 1
                # published order: the day-menu rank when the channel ranked the
                # board, else the production rank
                pub_rank = (
                    r.get("daymenu_rank")
                    if board_kind == "daymenu" and r.get("daymenu_rank") is not None
                    else r.get("predicted_rank")
                )
                rec = {
                    "stage": stage,
                    "date": cfg.get("date"),
                    "scenario": key,
                    "scenario_label": scen_cfg.get("short") or scen_cfg.get("label"),
                    "is_hindsight": int(is_hindsight),
                    "is_hidden": int(is_hidden),
                    "board": board_kind,
                    "day_key": json.dumps(day_key, sort_keys=True) if day_key else "",
                    "rider_id": r["rider_id"],
                    "rider_name": r["rider_name"],
                    "team": r.get("team_name"),
                    "predicted_rank": r.get("predicted_rank"),
                    "daymenu_rank": r.get("daymenu_rank"),
                    "published_rank": pub_rank,
                    "in_daymenu_pool": (
                        int(bool(r.get("in_daymenu_pool")))
                        if r.get("in_daymenu_pool") is not None else None
                    ),
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
            has_book = any(e.get("book_devig") for e in enriched)
            m = {
                "stage": stage,
                "scenario": key,
                "scenario_label": scen_cfg.get("short") or scen_cfg.get("label"),
                "is_hindsight": int(is_hindsight),
                "is_hidden": int(is_hidden),
                "board": board_kind,
                "day_key": json.dumps(day_key, sort_keys=True) if day_key else "",
                "has_book": int(has_book),
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
                    if out == "book_p_winner" and not has_book:
                        p = None
                    m[out] = p
                    m[out.replace("p_winner", "logloss")] = (
                        -math.log(max(p, 1e-9)) if p is not None else None
                    )
                m["model_rank_of_winner"] = rank_of(winner, "blend_win_norm")
                m["book_rank_of_winner"] = rank_of(winner, "book_devig_norm") if has_book else None
                m["published_rank_of_winner"] = winner.get("published_rank")
                m["production_rank_of_winner"] = winner.get("predicted_rank")
                m["edge_winner"] = (
                    winner["blend_win_norm"] - winner["book_devig_norm"]
                    if winner["blend_win_norm"] is not None
                    and winner["book_devig_norm"] is not None
                    and has_book
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
                    if out == "book_brier" and not has_book:
                        m[out] = None

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
                m[f"book_overlap{k}"] = (
                    overlap_at_k(enriched, "book_devig_norm", k) if has_book else None
                )
                m[f"model_meanrank_top{k}"] = mean_board_rank_of_actual(
                    enriched, "blend_win_norm", k
                )
                m[f"book_meanrank_top{k}"] = (
                    mean_board_rank_of_actual(enriched, "book_devig_norm", k)
                    if has_book else None
                )
                # the ranking channel: published order vs production order
                m[f"published_overlap{k}"] = overlap_at_k(
                    enriched, "published_rank", k, ascending=True
                )
                m[f"production_overlap{k}"] = overlap_at_k(
                    enriched, "predicted_rank", k, ascending=True
                )
            # depth-head orderings can disagree with the win ordering
            m["model_overlap10_top15head"] = overlap_at_k(enriched, "top15_norm", 10)
            m["model_spearman"] = spearman(enriched, "blend_win_norm")
            m["book_spearman"] = spearman(enriched, "book_devig_norm") if has_book else None

            top_model = max(enriched, key=lambda e: e.get("blend_win_norm") or 0.0)
            m["model_top_pick"] = top_model["rider_name"]
            m["model_top_pick_place"] = top_model["place"]
            m["model_top_pick_won"] = int(top_model["is_winner"] == 1)
            if has_book:
                top_book = max(enriched, key=lambda e: e.get("book_devig_norm") or 0.0)
                m["book_top_pick"] = top_book["rider_name"]
                m["book_top_pick_place"] = top_book["place"]
                m["book_top_pick_won"] = int(top_book["is_winner"] == 1)
            else:
                m["book_top_pick"] = m["book_top_pick_place"] = m["book_top_pick_won"] = None
            metrics_out.append(m)

    return riders_out, metrics_out, warnings


# ------------------------------------------------------------------- GC side


def book_gc_captures(camp: Campaign) -> list[dict]:
    """Every odds capture carrying the GC event, with its UTC fetch time.

    Each entry: {date, path, fetched_at (datetime, UTC), markets: {offer_type:
    {normalized rider name: devig}}}. The GC event carries win, podium ('(1-3)')
    and top-10 ('(1-10)') markets; the top-10 one only appears in some captures.
    """
    out: list[dict] = []
    for path in sorted(glob.glob(str(camp.dir / "odds/*/markets_*.json"))):
        p = Path(path)
        ev = json.loads(p.read_text()).get(camp.gc_event_id)
        if not ev:
            continue
        markets: dict[str, dict[str, float]] = {}
        for b in ev["betoffers"]:
            t = b.get("bet_offer_type")
            # the win + podium offers use criterion 'Winnaar'; the top-10 offer
            # is labelled 'Eindigt in de Top 10', so key on the offer type.
            if t == "Winnaar" and b.get("criterion") != "Winnaar":
                continue
            if t in ("Winnaar", "(1-3)", "(1-10)"):
                markets[t] = {norm_name(o["name"]): o["devig"] for o in b["outcomes"]}
        if "Winnaar" not in markets:
            continue
        fetched = None
        prov = p.with_name(p.name.replace("markets_", "provenance_"))
        if prov.exists():
            try:
                iso = json.loads(prov.read_text()).get("fetched_at_utc")
                if iso:
                    fetched = datetime.fromisoformat(iso).astimezone(timezone.utc)
            except (ValueError, json.JSONDecodeError):
                fetched = None
        if fetched is None:
            # no provenance: treat the local filename time as UTC (Tour-era
            # captures) — good enough for same-day pairing
            hhmm = p.stem.split("_")[1]
            fetched = datetime.strptime(
                f"{p.parent.name} {hhmm}", "%Y-%m-%d %H%M"
            ).replace(tzinfo=timezone.utc)
        out.append({"date": p.parent.name, "path": p, "fetched_at": fetched, "markets": markets})
    return out


def pair_book(
    camp: Campaign, captures: list[dict], predicted_at: str, through_stage: int | None
) -> tuple[dict | None, str]:
    """Pick the GC capture to score a board against, per --gc-book.

    `next` looks for the earliest capture fetched after the board was logged
    and before the next raced stage is under way (11:00 UTC on its date); failing
    that, the latest capture taken between the board's own stage finishing
    (15:00 UTC on its date) and the board being logged. Either way the book
    knows exactly the stages the board knows. Anything else is 'stale' (the
    capture predates the board's last stage) and is excluded from paired
    comparisons downstream.
    """
    if not captures:
        return None, ""
    date = predicted_at[:10]
    if camp.gc_book == "same-day":
        same = [c for c in captures if c["date"] == date]
        if same:
            return same[-1], "same-day"
        prior = [c for c in captures if c["date"] < date]
        return (prior[-1], "prior-day") if prior else (None, "")
    board_ts = datetime.strptime(predicted_at[:19], "%Y-%m-%d %H:%M:%S").replace(
        tzinfo=timezone.utc
    )

    def utc(day: str | None, hour: int) -> datetime | None:
        if not day:
            return None
        return datetime.strptime(day, "%Y-%m-%d").replace(hour=hour, tzinfo=timezone.utc)

    nxt = camp.next_raced_stage(through_stage)
    window_end = utc(camp.stage_dates.get(nxt), 11) if nxt else None
    after = [
        c for c in captures
        if c["fetched_at"] >= board_ts and (window_end is None or c["fetched_at"] < window_end)
    ]
    if after:
        return after[0], "next"
    finish = utc(camp.stage_dates.get(through_stage), 15)
    between = [
        c for c in captures
        if c["fetched_at"] < board_ts and (finish is None or c["fetched_at"] >= finish)
    ]
    if between:
        return between[-1], "same-evening"
    before = [c for c in captures if c["fetched_at"] < board_ts]
    return (before[-1], "stale") if before else (None, "")


def gc_board_metrics(
    camp: Campaign, count: int, date: str, book: dict | None, how: str, board: list[dict]
) -> dict:
    """Depth scoring for one daily GC board against the final classification."""
    m = {
        "through_count": count,
        "through_stage": camp.count_to_stage(count),
        "date": date,
        "book_date": book["date"] if book else "",
        "book_capture": str(book["path"].relative_to(camp.dir)) if book else "",
        "book_fetched_at_utc": book["fetched_at"].isoformat() if book else "",
        "book_pairing": how,
        "n_riders": len(board),
        "model_win_ll": bernoulli_ll(
            [(e["blend_win_norm"], int(e["final_place"] == 1)) for e in board]
        ),
        "book_win_ll": bernoulli_ll(
            [(e["book_devig_norm"], int(e["final_place"] == 1)) for e in board]
        ),
        "outlook_win_ll": bernoulli_ll(
            list(zip(renorm(board, "gc_outlook_win_p", 1.0).values(),
                     [int(e["final_place"] == 1) for e in board]))
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
    m["outlook_spearman"] = spearman(board, "gc_outlook_top5_p")
    # the eventual winner's price on each board
    win = next((e for e in board if e["final_place"] == 1), None)
    m["winner_name"] = win["rider_name"] if win else ""
    m["winner_model_p"] = win["blend_win_norm"] if win else None
    m["winner_book_p"] = win["book_devig_norm"] if win else None
    m["winner_outlook_p"] = (
        renorm(board, "gc_outlook_win_p", 1.0)[board.index(win)] if win else None
    )
    m["model_leader"] = max(board, key=lambda e: e["blend_win_norm"] or 0.0)["rider_name"]
    m["book_leader"] = (
        max(board, key=lambda e: e["book_devig_norm"] or 0.0)["rider_name"]
        if any(e["book_devig_norm"] for e in board) else ""
    )
    m["outlook_leader"] = max(board, key=lambda e: e.get("gc_outlook_win_p") or 0.0)["rider_name"]
    return m


def gc_rows(camp: Campaign) -> tuple[list[dict], list[dict], list[dict], list[str]]:
    warnings: list[str] = []
    gc_metrics: list[dict] = []
    final = {}
    fpath = camp.final_standings_path()
    for row in read_csv(fpath):
        final[norm_name(row["name"])] = {
            "final_place": int(row["place"]) if row["place"].isdigit() else None,
            "final_place_raw": row["place"],
            "final_gap": float(row["gap"]) if row["gap"] not in ("", None) else None,
        }

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    # One board = one run. Later rows carry a run_key; older ones (the Tour) do
    # not and were logged within a single second, so fall back to predicted_at.
    # A board's rows can straddle a clock second, which is why the latest run
    # per state is chosen by run identity and not by MAX(predicted_at) alone.
    raw_runs = con.execute(
        """
        SELECT state_through_stage AS count,
               COALESCE(run_key, predicted_at) AS run_id,
               MAX(predicted_at) AS at, COUNT(*) AS n
        FROM prediction_log
        WHERE model_version LIKE ?
        GROUP BY state_through_stage, COALESCE(run_key, predicted_at)
        ORDER BY state_through_stage, MAX(predicted_at)
        """,
        (f"%{camp.gc_tag_suffix}",),
    ).fetchall()
    latest: dict = {}
    for r in raw_runs:
        latest[r["count"]] = r  # ordered by time, so the last one wins
    runs = [latest[k] for k in sorted(latest, key=lambda k: (k is None, k))]
    captures = book_gc_captures(camp)
    n_raced = len(camp.raced_stages)
    daily: list[dict] = []
    for run in runs:
        count = run["count"]
        rows = con.execute(
            """
            SELECT rider_name, rider_id, multiclass_win_p, multiclass_podium_p,
                   multiclass_top5_p, multiclass_top15_p, lambdarank_win_p,
                   blend_win_p, dnf_p, dnf_adj_win_p, dnf_adj_podium_p,
                   dnf_adj_top5_p, dnf_adj_top15_p, gc_outlook_win_p,
                   gc_outlook_podium_p, gc_outlook_top5_p, gc_outlook_top15_p,
                   predicted_at
            FROM prediction_log
            WHERE model_version LIKE ? AND COALESCE(run_key, predicted_at) = ?
            """,
            (f"%{camp.gc_tag_suffix}", run["run_id"]),
        ).fetchall()
        rows = [dict(r) for r in rows]
        date = str(run["at"])[:10]
        book, how = pair_book(camp, captures, str(run["at"]), camp.count_to_stage(count))
        if book is None:
            warnings.append(f"gc through count {count}: no book GC market at all")
        elif how not in ("next", "same-day", "same-evening"):
            warnings.append(
                f"gc through count {count} (stage {camp.count_to_stage(count)}): no GC "
                f"capture after the board was logged — using {book['date']} ({how})"
            )
        win_mkt = book["markets"].get("Winnaar", {}) if book else {}
        book_mass = sum(win_mkt.values()) or None
        is_final = int(count is not None and count >= n_raced)

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
                    "through_count": count,
                    "through_stage": camp.count_to_stage(count),
                    "is_final": is_final,
                    "predicted_at": r["predicted_at"],
                    "date": date,
                    "book_date": book["date"] if book else "",
                    "book_pairing": how,
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
        attach_book(board, book["markets"].get("(1-3)") if book else None, 3.0)
        attach_book(board, book["markets"].get("(1-10)") if book else None, 10.0)
        daily.extend(board)
        if is_final:
            warnings.append(
                f"gc through count {count}: logged after the final stage — kept in "
                "gc_daily (is_final=1), excluded from gc_metrics"
            )
            continue
        gc_metrics.append(gc_board_metrics(camp, count, date, book, how, board))
    con.close()

    # final table: last pre-final board + final standings, one row per finisher
    scored = [d for d in daily if not d["is_final"]] or daily
    last_count = max((d["through_count"] or 0) for d in scored) if scored else None
    last = {norm_name(d["rider_name"]): d for d in scored if d["through_count"] == last_count}
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
                "model_through_count": d.get("through_count"),
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
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument(
        "--campaign", type=Path, default=HERE,
        help="campaign directory (default: this script's own Tour folder)",
    )
    ap.add_argument(
        "--gc-book", choices=("next", "same-day"), default="next",
        help="how to pair each GC board with a book capture (see module doc)",
    )
    args = ap.parse_args()
    camp = Campaign(args.campaign, args.gc_book)
    camp.out.mkdir(exist_ok=True)
    print(
        f"campaign {camp.dir.name}: gc event {camp.gc_event_id}, tag "
        f"{camp.gc_tag_suffix!r}, void stages {sorted(camp.void_stages) or '-'}, "
        f"gc book pairing {camp.gc_book}"
    )
    riders, metrics, warn1 = stage_rows(camp)
    daily, final_rows, gc_metrics, warn2 = gc_rows(camp)
    print("wrote:")
    write_csv(camp.out / "stage_riders.csv", riders)
    write_csv(camp.out / "stage_metrics.csv", metrics)
    write_csv(camp.out / "gc_daily.csv", daily)
    write_csv(camp.out / "gc_metrics.csv", gc_metrics)
    write_csv(camp.out / "gc_final.csv", final_rows)
    warnings = warn1 + warn2
    if warnings:
        print(f"\n{len(warnings)} notes:")
        for w in warnings:
            print(f"  - {w}")


if __name__ == "__main__":
    main()
