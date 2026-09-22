"""
Generate a campaign's stage-by-stage GC tracker page.

    python3 netlify_site/build/build_gc_tracker.py \
        performance_eval/vuelta-2026/predictions/gc/scenarios.json

Writes netlify_site/[prefix]gc.html — the prefix comes from
cycling_project/nightly/site_paths.py (the one rule the builders and the
driver share), so a second race publishes alongside the first instead of
overwriting it. With no argument the TdF GC config is used,
which keeps the Tour's `gc.html` building exactly as before.

Every evening run of the GC config logs one opinion per rider to
prediction_log with `state_through_stage` = however many stages have fed the
state, so the log IS the history: this page reads one checkpoint per completed
stage (the LATEST run when a checkpoint was logged twice — e.g. a re-run after
a withdrawal filtered the field), shows how the road and the model's board
moved together, and details the current board against the freshest odds
capture.

Data sources (all local, all resolved against the config's own campaign
directory): prediction_log (cycling_races.db), the latest
predictions/gc/<scenario>.json (current board incl. book devig), archived
results/stage_NN/gc.csv (the official classification per checkpoint — NOT
results/race_page/standings_*.json, which mid-race is only the DNF board).
Rebuild any time; runs after the evening GC refresh in the daily runbook.
"""

import csv
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from build_stage_page import (
    CSS, DB_PATH, PROJECT_ROOT, SITE_DIR,
    esc, pct, provisional_note, resolve_campaign, _fc_to_internal_ids,
)
from cycling_project.nightly import site_paths  # noqa: E402  (build_stage_page put PROJECT_ROOT on sys.path)

# Campaign archives — rebound in main() from the config's own campaign
# directory (<campaign>/predictions/gc/scenarios.json), mirroring
# build_stage_page.main(). These defaults keep the TdF paths.
DEFAULT_CONFIG = (PROJECT_ROOT / "performance_eval" / "tour-de-france-2026"
                  / "predictions" / "gc" / "scenarios.json")
CAMPAIGN_ROOT = DEFAULT_CONFIG.parents[2]
RESULTS_ROOT = CAMPAIGN_ROOT / "results"
PREDICTIONS_ROOT = CAMPAIGN_ROOT / "predictions"
CAMPAIGN = resolve_campaign(CAMPAIGN_ROOT.name, {})

TOP_N = 10

EXTRA_CSS = """
  .gcnum{font-family:var(--sans);font-variant-numeric:tabular-nums}
  .gap{display:block;font-size:11px;color:var(--slate);font-weight:400;line-height:1.3}
  td.lead{background:var(--yellow-soft)}
  td.void{background:#F1EFEA;color:#8A8378}
  th.void{color:#8A8378;text-decoration:line-through;text-decoration-thickness:1px}
  .chip{font-family:var(--sans);font-size:11.5px;font-weight:600;letter-spacing:.05em;
        text-transform:uppercase;padding:2px 9px;border-radius:99px;
        border:1px solid var(--line);color:var(--slate)}
  .sub{font-weight:400;font-size:11px;color:var(--slate)}
"""


# ────────────────────────────── checkpoints ──────────────────────────────

def raced_stage_numbers(void_stages, n_stages):
    """Calendar stage numbers in racing order, cancelled stages removed."""
    void = {int(v) for v in (void_stages or ())}
    return [n for n in range(1, int(n_stages) + 1) if n not in void]


def stage_for_count(count, raced):
    """Calendar stage number for a `state_through_stage` value.

    prediction_log stores that field as a COUNT of the stages that fed the
    state, not as a stage number. A cancelled stage adds no time to anyone and
    is skipped by live_race_state (`void_stages`), so from the first
    cancellation onwards the two diverge for the rest of the race — at the
    Vuelta 2026, count 5 means "after stage 6". Reading the count as a stage
    number would pull the wrong evening's gc.csv and show the wrong podium.
    """
    i = int(count) - 1
    return raced[i] if 0 <= i < len(raced) else None


def checkpoints(fc_race_id, year, tag, raced):
    """[{count, stage, day, riders: {rider_id: {name, blend, outlook}}}] from
    the prediction log, one per state_through_stage (latest run wins)."""
    like = f"%|{tag}"
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    thru_rows = conn.execute(
        "SELECT DISTINCT state_through_stage AS thru FROM prediction_log "
        "WHERE fc_race_id=? AND year=? AND model_version LIKE ? "
        "AND state_through_stage IS NOT NULL ORDER BY thru",
        (fc_race_id, year, like)).fetchall()
    out = []
    for tr in thru_rows:
        thru = int(tr["thru"])
        # latest logging batch for this checkpoint (a batch spans seconds;
        # 5 minutes cleanly separates distinct runs)
        rows = conn.execute(
            "SELECT rider_id, rider_name, blend_win_p, gc_outlook_win_p, "
            "       predicted_at "
            "FROM prediction_log "
            "WHERE fc_race_id=? AND year=? AND model_version LIKE ? "
            "  AND state_through_stage=? AND predicted_at >= ("
            "    SELECT datetime(MAX(predicted_at), '-300 seconds') "
            "    FROM prediction_log WHERE fc_race_id=? AND year=? "
            "      AND model_version LIKE ? AND state_through_stage=?)",
            (fc_race_id, year, like, thru,
             fc_race_id, year, like, thru)).fetchall()
        riders = {int(r["rider_id"]): {
            "name": r["rider_name"],
            "blend": r["blend_win_p"],
            "outlook": r["gc_outlook_win_p"],
        } for r in rows}
        day = max(r["predicted_at"] for r in rows)[:10]
        out.append({"count": thru, "stage": stage_for_count(thru, raced),
                    "day": day, "riders": riders})
    conn.close()
    return out


# ───────────────────────────── the actual race ────────────────────────────

def actual_gc(stage):
    """[{fc, rider_id, name, place, gap}] — the official classification after
    the given stage, from the archived per-stage gc.csv."""
    if stage is None:
        return []
    f = RESULTS_ROOT / f"stage_{int(stage):02d}" / "gc.csv"
    if not f.exists():
        return []
    rows = list(csv.DictReader(f.open()))
    by_fc = _fc_to_internal_ids(r.get("rider_id") for r in rows)
    out = []
    for r in rows:
        if not str(r.get("place", "")).strip().isdigit():
            continue
        try:
            gap = float(r.get("gap"))
        except (TypeError, ValueError):
            gap = None
        fc = str(r.get("rider_id") or "")
        out.append({"fc": fc, "rider_id": by_fc.get(fc), "name": r["name"],
                    "place": int(r["place"]), "gap": gap})
    return out


def archived_standings(raced):
    """{stage: [rows]} for every raced stage with a gc.csv archived."""
    return {n: rows for n in raced for rows in [actual_gc(n)] if rows}


def fmt_gap(seconds):
    if seconds is None or seconds != seconds:  # NaN: int() would raise
        return "–"
    s = int(seconds)
    return "0:00" if s == 0 else f"+{s//60}:{s%60:02d}"


def race_table(standings, void_stages):
    """The road's own story: top-10 placings and gaps, stage by stage."""
    if not standings:
        return ""
    stages = sorted(standings)
    void = sorted(v for v in {int(x) for x in (void_stages or ())}
                  if v < max(stages))
    columns = sorted(stages + void)

    universe, names, latest = [], {}, standings[stages[-1]]
    for n in stages:
        for r in standings[n][:TOP_N]:
            if r["fc"] not in universe:
                universe.append(r["fc"])
        for r in standings[n]:
            names.setdefault(r["fc"], r["name"])
    place_now = {r["fc"]: r["place"] for r in latest}
    universe.sort(key=lambda fc: place_now.get(fc, 999))

    head = "<tr><th>Rider</th>" + "".join(
        f'<th class="num void">s{n}<div class="sub">cancelled</div></th>'
        if n in void else f'<th class="num">after s{n}</th>'
        for n in columns) + "</tr>"

    body = []
    for fc in universe:
        cells = []
        for n in columns:
            if n in void:
                cells.append('<td class="num void">—</td>')
                continue
            row = next((r for r in standings[n] if r["fc"] == fc), None)
            if row is None:
                cells.append('<td class="num muted">out</td>')
            else:
                cls = "num lead" if row["place"] == 1 else "num"
                cells.append(
                    f'<td class="{cls}"><b>{row["place"]}</b>'
                    f'<span class="gap">{fmt_gap(row["gap"])}</span></td>')
        body.append(f'<tr><td>{esc(names.get(fc, fc))}</td>'
                    + "".join(cells) + "</tr>")
    return f'<div class="tablewrap"><table>{head}{"".join(body)}</table></div>'


# ──────────────────────────── the model's board ───────────────────────────

def evolution_table(checks, field, standings):
    """One head's opinion across every checkpoint: rows are every rider who
    has made a top-10, columns are the checkpoints in racing order."""
    def top_ids(ck):
        vals = [(rid, v[field]) for rid, v in ck["riders"].items()
                if v[field] is not None and v[field] == v[field]]
        return [rid for rid, _ in sorted(vals, key=lambda kv: -kv[1])[:TOP_N]]

    # Once per checkpoint, not once per cell. The ordered list seeds the row
    # order; the set is only membership for the bolding.
    ranked = [top_ids(ck) for ck in checks]
    tops = [set(r) for r in ranked]
    latest = checks[-1]
    universe, names = [], {}
    for ck, top in zip(checks, ranked):
        for rid in top:
            if rid not in universe:
                universe.append(rid)
        for rid, v in ck["riders"].items():
            names.setdefault(rid, v["name"])
    if not universe:
        return ""
    universe.sort(key=lambda rid: -(latest["riders"].get(rid, {}).get(field)
                                    or 0))

    leaders = {}
    for ck in checks:
        rows = standings.get(ck["stage"]) or []
        if rows:
            leaders[ck["count"]] = rows[0]["name"]

    head = "<tr><th>Rider</th>" + "".join(
        f'<th class="num">after s{ck["stage"] if ck["stage"] else ck["count"]}'
        + (f'<div class="sub">🟡 {esc(leaders[ck["count"]].split()[0])}</div>'
           if leaders.get(ck["count"]) else "")
        + "</th>" for ck in checks) + "</tr>"

    body = []
    for rid in universe:
        cells = []
        for ck, top in zip(checks, tops):
            v = ck["riders"].get(rid)
            if v is None:
                cells.append('<td class="num muted">out</td>')
                continue
            val = pct(v[field])
            cells.append(f'<td class="num">'
                         f'{f"<b>{val}</b>" if rid in top else val}'
                         "</td>")
        body.append(f'<tr><td>{esc(names.get(rid, rid))}</td>'
                    + "".join(cells) + "</tr>")
    return f'<div class="tablewrap"><table>{head}{"".join(body)}</table></div>'


# ───────────────────────────────── page ───────────────────────────────────

def build(config):
    void_stages = config.get("void_stages") or []
    raced = raced_stage_numbers(void_stages, CAMPAIGN["n_stages"])
    fc_race_id, year = str(config["fc_race_id"]), int(config["year"])

    scen_key, spec = next(iter(config["scenarios"].items()))
    tag = spec["tag"]

    checks = checkpoints(fc_race_id, year, tag, raced)
    if not checks:
        raise SystemExit(f"No GC runs found in prediction_log for "
                         f"race {fc_race_id}/{year} (tag {tag}).")
    latest = checks[-1]
    standings = archived_standings(raced)

    gc_json_path = PREDICTIONS_ROOT / "gc" / f"{scen_key}.json"
    current = json.loads(gc_json_path.read_text()) if gc_json_path.exists() else None

    # The board's gaps must come from the standing the board itself saw, not
    # from the newest archive — the road can be one evening ahead of the log.
    board_count = ((current.get("state") or {}).get("through_stage")
                   if current else None) or latest["count"]
    # A count past the end of the calendar cannot name a stage; fall back to
    # the count so the page still renders rather than printing "stage None".
    board_stage = stage_for_count(board_count, raced) or board_count
    gaps = {r["rider_id"]: r["gap"] for r in actual_gc(board_stage)
            if r["rider_id"]}
    newest_stage = max(standings) if standings else None

    # ── current top-10 detail ──
    detail_rows = []
    # The blend is a set of per-rider marginals, not a distribution: it sums to
    # well over one book. Surface the actual total so the book column next to it
    # is read as directional, not as a like-for-like price.
    # `x or 0` does not screen NaN (NaN is truthy), and one NaN would carry
    # through the sum into the note's total.
    blend_mass = sum(p for p in (r.get("blend_win_p") for r in current["riders"])
                     if p is not None and p == p) if current else 0
    if current:
        # The outlook head is the only head that has seen the race, so it
        # leads the board: order by it, with the pre-race blend as the
        # tie-break for riders it never priced (NaN = not a contender).
        def _p(v):
            return v if v is not None and v == v else -1.0
        top = sorted(current["riders"],
                     key=lambda r: (-_p(r.get("gc_outlook_win_p")),
                                    -(r.get("blend_win_p") or 0)))[:TOP_N]
        for i, r in enumerate(top, 1):
            detail_rows.append(
                "<tr>"
                f"<td class='num'>{i}</td><td>{esc(r['rider_name'])}</td>"
                f"<td class='muted'>{esc(r.get('team_name') or '')}</td>"
                f"<td class='num'>{fmt_gap(gaps.get(int(r['rider_id'])))}</td>"
                f"<td class='num'><b>{pct(r.get('gc_outlook_win_p'))}</b></td>"
                f"<td class='num'>{pct(r.get('blend_win_p'))}</td>"
                + (f"<td class='num'>{pct(r.get('book_devig'))}</td>"
                   if r.get("book_devig") is not None
                   else "<td class='num muted'>–</td>")
                + "</tr>")

    void_note = ""
    if void_stages:
        vs = ", ".join(f"stage {v}" for v in sorted(void_stages))
        void_note = (f" {vs.capitalize()} was cancelled and never raced: it "
                     "adds no time to anyone, so it is skipped rather than "
                     "treated as a missing result, and every later "
                     "classification still lines up.")

    lag_note = ""
    if newest_stage and board_stage and newest_stage > board_stage:
        lag_note = (f" The road is a stage ahead of the board here — stage "
                    f"{newest_stage} is in the results archive, while the "
                    f"newest logged opinion still sees state through stage "
                    f"{board_stage}; tonight's refresh closes the gap.")

    # Riders the nightly ingest archived under a provisional identity (ruling 2026-09-16) are named
    # on the classification table rather than passed off as matched riders.
    gc_provisional = provisional_note(
        None,
        rows=[{"rider_id": r["fc"], "place": r["place"], "name": r["name"]}
              for r in standings.get(newest_stage, [])],
        top_n=20, scope="the top 20 on general classification")

    n_field = len(latest["riders"])
    pfx = CAMPAIGN["prefix"]
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{CAMPAIGN['short_name']} · GC tracker — the favourites, stage by stage</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🚴</text></svg>">
<style>{CSS}{EXTRA_CSS}</style>
</head>
<body>
<div class="wrap">
<header>
  <div class="eyebrow">Cycling race predictor · {CAMPAIGN['race_name']}</div>
  <h1>GC tracker — the favourites, stage by stage</h1>
  <p class="standfirst">After every stage the race-aware GC outlook head
  re-prices the final general classification from the standings, the gaps and
  the stages left. It is the one part of the model that watches the race, so
  it leads this page; the pre-race blend, which only knows what happened
  before the start, is shown beside it for contrast. Each column is one
  evening's logged opinion; the current board sits on top.</p>
  <div class="meta">
    <span>state through&nbsp;<b>stage {board_stage}</b></span>
    <span>classification through&nbsp;<b>stage {newest_stage or '–'}</b></span>
    <span><b>{n_field}</b>&nbsp;riders still in the race</span>
    <span><b>{len(checks)}</b>&nbsp;checkpoints logged</span>
    <span>updated&nbsp;<b>{datetime.now().strftime('%Y-%m-%d')}</b></span>
  </div>
  <p class="backlink"><a href="{site_paths.stages_index_name(pfx)}">← {esc(CAMPAIGN['hub_title'])}</a> ·
  <a href="index.html">system overview</a></p>
</header>

<section>
<h2>The current top 10</h2>
<div class="tablewrap"><table>
<tr><th class="num">#</th><th>Rider</th><th>Team</th>
<th class="num">GC gap<div class="sub">after s{board_stage}</div></th>
<th class="num">Outlook<div class="sub">sees the race</div></th>
<th class="num">Pre-race blend<div class="sub">form + references only</div></th>
<th class="num">Book devig</th></tr>
{''.join(detail_rows)}
</table></div>
<div class="note">Ordered by the <b>outlook head</b>, the one head that sees
the race state: standings, gaps and stages remaining. It scores contenders
only (a rider it never priced shows a dash) and its per-rider numbers do not
sum to exactly one book, so read a row as "how safe is this position" rather
than as a like-for-like price. The <b>pre-race blend</b> is the main heads
with live form and the DNF-adjusted active field: it prices the final GC from
what happened before the race and never sees the standings, which is why it
barely moves from one evening to the next and why a rider who has already
lost an hour can still carry his pre-race price there. It sums to
{100*blend_mass:.0f}% over the field, so compare it with the book column
directionally only.</div>
</section>

<section>
<h2>How the race has actually gone</h2>
{race_table(standings, void_stages)}
{gc_provisional}
<div class="note">The official classification after each stage, from the
FirstCycling results archive — place, with the gap to the leader beneath it.
Every rider who has held a top-10 place, ordered by the current standing;
"out" = no longer classified.{void_note}</div>
</section>

<section>
<h2>How the race-aware board moved</h2>
{evolution_table(checks, "outlook", standings)}
<div class="note">The GC outlook head at each checkpoint — every rider who
has appeared in its top-10, ordered by the current board. <b>Bold</b> =
inside that evening's top-10; "out" = no longer in the race when that opinion
was logged. 🟡 names the actual race leader at each checkpoint. Columns are
labelled by the stage the road had reached, which is what the state was built
from. This head sees the standings, the gaps and the stages remaining, so it
is the row that should move when the race does; it scores contenders only,
so a rider it never priced shows a dash.{lag_note}</div>
</section>

<section>
<h2>The pre-race view, for contrast</h2>
{evolution_table(checks, "blend", standings)}
<div class="note">Model GC win probability (blend) at each checkpoint — every
rider who has appeared in a top-10, ordered by the current board.
<b>Bold</b> = inside that evening's top-10; "out" = no longer in the race when
that opinion was logged. 🟡 names the actual race leader at each checkpoint.
The row is close to flat by construction — these heads price the final GC
from form and the reference editions, and never see the standings — so treat
this table as the baseline the race-aware head above is moving against, not
as a forecast of the race as it stands.</div>
</section>

<div class="footer">Opinions logged pre-stage to prediction_log
(model_version …|{esc(tag)}); standings from the per-stage
{esc(str(RESULTS_ROOT.relative_to(PROJECT_ROOT)))}/stage_NN/gc.csv archive;
odds from the Kambi (Unibet) capture. Full methodology on the
<a href="index.html">main page</a>.</div>
</div>
</body>
</html>
"""
    out = SITE_DIR / site_paths.gc_tracker_name(pfx)
    out.write_text(page)
    print(f"Wrote {out} ({out.stat().st_size/1024:.0f} KB) — "
          f"{len(checks)} checkpoints through stage {board_stage}, "
          f"{len(standings)} archived standings")


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CONFIG
    config_path = Path(arg).resolve()

    global CAMPAIGN_ROOT, RESULTS_ROOT, PREDICTIONS_ROOT, CAMPAIGN
    CAMPAIGN_ROOT = config_path.parents[2]
    RESULTS_ROOT = CAMPAIGN_ROOT / "results"
    PREDICTIONS_ROOT = CAMPAIGN_ROOT / "predictions"

    config = json.loads(config_path.read_text())
    CAMPAIGN = resolve_campaign(CAMPAIGN_ROOT.name, config)
    build(config)


if __name__ == "__main__":
    main()
