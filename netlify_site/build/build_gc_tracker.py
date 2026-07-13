"""
Generate the stage-by-stage GC tracker page (netlify_site/gc.html).

    python3 netlify_site/build/build_gc_tracker.py

Every morning run of the GC config logs one opinion per rider to
prediction_log with `state_through_stage` = the latest completed stage, so
the log IS the history: this page reads one checkpoint per completed stage
(the LATEST run when a checkpoint was logged twice — e.g. a re-run after a
withdrawal filtered the field), shows how the model's top-10 GC favourites
evolved, and details the current board against the freshest odds capture.

Data sources (all local): prediction_log (cycling_races.db), the latest
predictions/gc/tdf_gc.json (current board incl. book devig), archived
results/stage_NN/gc.csv (actual yellow jersey + gaps per checkpoint).
Rebuild any time; runs after the morning GC refresh in the daily runbook.
"""

import csv
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from build_stage_page import (
    CSS, DB_PATH, PREDICTIONS_ROOT, RESULTS_ROOT, SITE_DIR,
    esc, pct, _fc_to_internal_ids,
)

GC_TAG = "|gc_tdf_editions_state"
FC_RACE_ID, YEAR = "17", 2026
TOP_N = 10


def checkpoints():
    """[{through, day, riders: {rider_id: {name, blend, outlook}}}] from the
    prediction log, one per state_through_stage (latest run wins)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    thru_rows = conn.execute(
        "SELECT DISTINCT state_through_stage AS thru FROM prediction_log "
        "WHERE fc_race_id=? AND year=? AND model_version LIKE ? "
        "AND state_through_stage IS NOT NULL ORDER BY thru",
        (FC_RACE_ID, YEAR, f"%{GC_TAG}")).fetchall()
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
            (FC_RACE_ID, YEAR, f"%{GC_TAG}", thru,
             FC_RACE_ID, YEAR, f"%{GC_TAG}", thru)).fetchall()
        riders = {int(r["rider_id"]): {
            "name": r["rider_name"],
            "blend": r["blend_win_p"],
            "outlook": r["gc_outlook_win_p"],
        } for r in rows}
        day = max(r["predicted_at"] for r in rows)[:10]
        out.append({"through": thru, "day": day, "riders": riders})
    conn.close()
    return out


def actual_gc(through):
    """[(internal_id or None, name, gap_seconds)] after the given stage."""
    f = RESULTS_ROOT / f"stage_{through:02d}" / "gc.csv"
    if not f.exists():
        return []
    rows = list(csv.DictReader(f.open()))
    by_fc = _fc_to_internal_ids(r.get("rider_id") for r in rows)
    out = []
    for r in rows:
        gap = r.get("gap")
        try:
            gap = float(gap)
        except (TypeError, ValueError):
            gap = None
        out.append((by_fc.get(str(r.get("rider_id") or "")), r["name"], gap))
    return out


def fmt_gap(seconds):
    if seconds is None:
        return "–"
    s = int(seconds)
    return "0:00" if s == 0 else f"+{s//60}:{s%60:02d}"


def build():
    checks = checkpoints()
    if not checks:
        raise SystemExit("No GC runs found in prediction_log.")
    latest = checks[-1]

    gc_json_path = PREDICTIONS_ROOT / "gc" / "tdf_gc.json"
    current = json.loads(gc_json_path.read_text()) if gc_json_path.exists() else None

    # ── current top-10 detail ──
    gaps = {rid: g for rid, _, g in actual_gc(latest["through"]) if rid}
    detail_rows = []
    if current:
        top = sorted(current["riders"],
                     key=lambda r: -(r.get("blend_win_p") or 0))[:TOP_N]
        for i, r in enumerate(top, 1):
            detail_rows.append(
                "<tr>"
                f"<td class='num'>{i}</td><td>{esc(r['rider_name'])}</td>"
                f"<td class='muted'>{esc(r.get('team_name') or '')}</td>"
                f"<td class='num'>{fmt_gap(gaps.get(int(r['rider_id'])))}</td>"
                f"<td class='num'><b>{pct(r.get('blend_win_p'))}</b></td>"
                f"<td class='num'>{pct(r.get('gc_outlook_win_p'))}</td>"
                + (f"<td class='num'>{pct(r.get('book_devig'))}</td>"
                   if r.get("book_devig") is not None
                   else "<td class='num muted'>–</td>")
                + "</tr>")

    # ── evolution table: union of every checkpoint's top-10 ──
    def top_ids(ck):
        ranked = sorted(ck["riders"].items(),
                        key=lambda kv: -(kv[1]["blend"] or 0))
        return [rid for rid, _ in ranked[:TOP_N]]

    universe, names = [], {}
    for ck in checks:
        for rid in top_ids(ck):
            if rid not in universe:
                universe.append(rid)
        for rid, v in ck["riders"].items():
            names.setdefault(rid, v["name"])
    universe.sort(key=lambda rid: -(latest["riders"].get(rid, {}).get("blend") or 0))

    leaders = {ck["through"]: next(iter(actual_gc(ck["through"])), None)
               for ck in checks}
    head = ("<tr><th>Rider</th>"
            + "".join(
                f'<th class="num">after s{ck["through"]}'
                + (f'<div class="muted" style="font-weight:400;font-size:11px">'
                   f'🟡 {esc(leaders[ck["through"]][1].split()[0])}</div>'
                   if leaders.get(ck["through"]) else "")
                + "</th>"
                for ck in checks)
            + "</tr>")
    body = []
    for rid in universe:
        cells = []
        for ck in checks:
            v = ck["riders"].get(rid)
            in_top = rid in top_ids(ck)
            if v is None:
                cells.append('<td class="num muted">out</td>')
            else:
                val = pct(v["blend"])
                cells.append(f'<td class="num">{f"<b>{val}</b>" if in_top else val}</td>')
        body.append(f"<tr><td>{esc(names.get(rid, rid))}</td>" + "".join(cells) + "</tr>")

    n_field = len(latest["riders"])
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TdF 2026 · GC tracker — the favourites, stage by stage</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🚴</text></svg>">
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<header>
  <div class="eyebrow">Cycling race predictor · Tour de France 2026</div>
  <h1>GC tracker — the favourites, stage by stage</h1>
  <p class="standfirst">After every stage the production stack re-prices the
  final general classification with the race state it has seen so far. Each
  column is one morning's logged opinion; the current board sits on top.</p>
  <div class="meta">
    <span>state through&nbsp;<b>stage {latest['through']}</b></span>
    <span><b>{n_field}</b>&nbsp;riders still in the race</span>
    <span>updated&nbsp;<b>{datetime.now().strftime('%Y-%m-%d')}</b></span>
  </div>
  <p class="backlink"><a href="stages.html">← The Tour, stage by stage</a> ·
  <a href="index.html">system overview</a></p>
</header>

<section>
<h2>The current top 10</h2>
<div class="tablewrap"><table>
<tr><th class="num">#</th><th>Rider</th><th>Team</th><th class="num">GC gap</th>
<th class="num">Model win</th><th class="num">Outlook head</th>
<th class="num">Book devig</th></tr>
{''.join(detail_rows)}
</table></div>
<div class="note">Model win = the pre-race heads with live form and the
DNF-adjusted active field — book-preserving, comparable with the devigged
book column. The outlook head is state-aware but per-rider: its numbers
don't sum to one book; read them as "how safe is this position", not as
odds.</div>
</section>

<section>
<h2>How the board moved</h2>
<div class="tablewrap"><table>
{head}
{''.join(body)}
</table></div>
<div class="note">Model GC win probability (blend) after each completed
stage — every rider who has appeared in a morning top-10, ordered by the
current board. <b>Bold</b> = inside that morning's top-10; "out" = no longer
in the race when that opinion was logged. 🟡 names the actual race leader at
each checkpoint. Checkpoints start after stage 2, the first morning the
state-aware refresh ran.</div>
</section>

<div class="footer">Opinions logged pre-stage to prediction_log
(model_version …{GC_TAG}); standings from the FirstCycling results archive;
odds from the Kambi (Unibet) capture. Full methodology on the
<a href="index.html">main page</a>.</div>
</div>
</body>
</html>
"""
    out = SITE_DIR / "gc.html"
    out.write_text(page)
    print(f"Wrote {out} ({out.stat().st_size/1024:.0f} KB) — "
          f"{len(checks)} checkpoints, {len(universe)} riders tracked")


if __name__ == "__main__":
    build()
