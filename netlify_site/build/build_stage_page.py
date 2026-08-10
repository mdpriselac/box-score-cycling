"""
Generate a per-stage prediction page for the netlify site.

    python3 netlify_site/build/build_stage_page.py \
        performance_eval/tour-de-france-2026/predictions/stage_02/scenarios.json

Reads the stage's scenario config + the per-scenario prediction JSONs written
by predict_stage_scenarios.py (+ the archived FirstCycling results, once the
stage has been raced and capture_results.py has run), writes
netlify_site/stageNN.html, refreshes the stage-links strip in
predictor-architecture.html (between STAGES markers), and reruns
make_netlify.py so index.html stays current.

Rerun after the stage to append the results section — the page upgrades in
place.
"""

import csv
import html
import json
import runpy
import sqlite3
import sys
from datetime import datetime
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).parent
SITE_DIR = HERE.parent
PROJECT_ROOT = SITE_DIR.parent
RESULTS_ROOT = PROJECT_ROOT / "performance_eval" / "tour-de-france-2026" / "results"
PREDICTIONS_ROOT = PROJECT_ROOT / "performance_eval" / "tour-de-france-2026" / "predictions"
SOURCE_HTML = HERE / "predictor-architecture.html"

SCORE_ORDER = [
    ("sprint", "race_sprint_score"), ("mountain", "race_mountain_score"),
    ("hilly", "race_hilly_score"), ("rolling", "race_rolling_score"),
    ("break", "race_breakaway_score"), ("TT", "race_time_trial_score"),
]

CSS = """
  *,*::before,*::after{box-sizing:border-box}
  :root{
    --ink:#22272F; --paper:#FBFAF7; --slate:#5C6470; --line:#E5E3DB;
    --yellow:#F5C518; --yellow-soft:#FBF0C4; --blue:#3E6B8F;
    --blue-soft:#E7EEF4; --green:#47705A; --green-soft:#E6EEE9;
    --red:#9A4A3B; --card:#FFFFFF;
    --mono:ui-monospace,"SF Mono",SFMono-Regular,Menlo,Consolas,monospace;
    --sans:"Avenir Next","Avenir","Segoe UI",-apple-system,BlinkMacSystemFont,"Helvetica Neue",sans-serif;
    --serif:"Charter","Iowan Old Style","Palatino Linotype",Georgia,serif;
  }
  body{background:var(--paper);color:var(--ink);font-family:var(--serif);
       font-size:17px;line-height:1.65;margin:0}
  .wrap{max-width:1020px;margin:0 auto;padding:0 24px 96px}
  header{padding:56px 0 8px}
  .eyebrow{font-family:var(--sans);font-size:12px;font-weight:600;
    letter-spacing:.14em;text-transform:uppercase;color:var(--slate);
    display:flex;align-items:center;gap:10px}
  .eyebrow::before{content:"";display:inline-block;width:26px;height:8px;background:var(--yellow)}
  h1{font-family:var(--sans);font-weight:700;font-size:clamp(28px,4.5vw,42px);
     line-height:1.08;letter-spacing:-.015em;margin:.5em 0 .35em;text-wrap:balance}
  .standfirst{font-size:19px;line-height:1.55;color:var(--slate);max-width:680px;margin:0 0 20px}
  .meta{font-family:var(--sans);font-size:13px;color:var(--slate);
    display:flex;flex-wrap:wrap;gap:6px 22px;padding:14px 0;
    border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
  .meta b{color:var(--ink);font-weight:600;font-variant-numeric:tabular-nums}
  .backlink{font-family:var(--sans);font-size:13px;margin:14px 0 0}
  .backlink a{color:var(--blue);text-decoration:none;border-bottom:1px solid var(--blue-soft)}
  section{margin-top:64px}
  .kicker{font-family:var(--sans);font-size:12px;font-weight:600;
    letter-spacing:.14em;text-transform:uppercase;color:var(--blue);margin:0 0 6px}
  h2{font-family:var(--sans);font-weight:700;font-size:26px;letter-spacing:-.01em;
     line-height:1.15;margin:0 0 14px;text-wrap:balance}
  h3{font-family:var(--sans);font-weight:600;font-size:17px;margin:24px 0 8px}
  p{margin:0 0 16px;max-width:680px}
  .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:16px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:16px 18px}
  .card h3{margin:0 0 4px;font-size:16px}
  .card .note{font-size:13.5px;color:var(--slate);line-height:1.5;margin:8px 0 0}
  .bars{margin:10px 0 2px}
  .bar-row{display:flex;align-items:center;gap:8px;font-family:var(--sans);font-size:11.5px;color:var(--slate)}
  .bar-row .lbl{width:56px;text-align:right;flex:none}
  .bar-row .track{flex:1;height:9px;background:var(--paper);border:1px solid var(--line);border-radius:3px;overflow:hidden}
  .bar-row .fill{display:block;height:100%;background:var(--blue)}
  .bar-row .val{width:30px;flex:none;font-variant-numeric:tabular-nums}
  table{border-collapse:collapse;width:100%;font-family:var(--sans);font-size:14px}
  th{font-size:11.5px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;
     color:var(--slate);text-align:left;padding:8px 10px;border-bottom:2px solid var(--ink)}
  td{padding:7px 10px;border-bottom:1px solid var(--line);font-variant-numeric:tabular-nums}
  th.num,td.num{text-align:right}
  tr.winner td{background:var(--yellow-soft)}
  .pos{color:var(--green);font-weight:600}
  .neg{color:var(--red)}
  .muted{color:var(--slate)}
  .tablewrap{overflow-x:auto;background:var(--card);border:1px solid var(--line);
             border-radius:8px;padding:6px 12px 10px;margin:18px 0}
  details{margin:14px 0}
  summary{font-family:var(--sans);font-size:14px;font-weight:600;color:var(--blue);cursor:pointer}
  .footer{margin-top:80px;padding-top:16px;border-top:1px solid var(--line);
          font-family:var(--sans);font-size:12.5px;color:var(--slate)}
"""

STRIP_CSS = """<style>
.stage-strip{max-width:1020px;margin:10px auto 0;font-family:var(--sans);
  font-size:13px;color:var(--slate);display:flex;flex-wrap:wrap;gap:6px 14px;
  align-items:center;justify-content:center}
.stage-strip a{color:var(--blue);text-decoration:none;border-bottom:1px solid var(--blue-soft);font-weight:600}
.stage-strip .done{color:var(--green)}
</style>"""


def esc(s):
    return html.escape(str(s)) if s is not None else ""


def pct(v, digits=1):
    # NaN means "this head didn't price that rider" (the GC outlook head only
    # scores real contenders) — it reads as missing, not as a number, so it
    # gets the same dash as None rather than a literal "nan%".
    if v is None or v != v:
        return "–"
    return f"{100*v:.{digits}f}%"


@lru_cache(maxsize=None)
def gc_pool_ids(n):
    """Rider ids of the top-n GC contenders by the latest GC-model blend — the
    captains who won't be given freedom or let up the road in a breakaway."""
    gc_dir = PREDICTIONS_ROOT / "gc"
    preds = [p for p in gc_dir.glob("*.json") if p.name != "scenarios.json"]
    if not preds:
        return frozenset()
    data = json.loads(max(preds, key=lambda p: p.stat().st_mtime).read_text())
    ranked = sorted(data["riders"], key=lambda r: -(r.get("blend_win_p") or 0))
    return frozenset(int(r["rider_id"]) for r in ranked[:n])


def norm_name(s):
    return " ".join(sorted(s.lower().replace("-", " ").split()))


DB_PATH = (PROJECT_ROOT / "cycling_project" / "webscrape_tools" / "database"
           / "database" / "cycling_races.db")


def _fc_to_internal_ids(fc_ids):
    """{fc_rider_id: internal riders.id} — names drift on FirstCycling
    (Gee -> Gee-West), so archived gc.csv rows join on the stable fc id."""
    fc_ids = [str(f) for f in fc_ids if f]
    if not fc_ids or not DB_PATH.exists():
        return {}
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            f"SELECT fc_rider_id, id FROM riders WHERE fc_rider_id IN "
            f"({','.join('?' for _ in fc_ids)})", fc_ids).fetchall()
    return {str(fc): int(i) for fc, i in rows}


def standings_pool_ids(stage, n, riders):
    """Rider ids of the top-n on ACTUAL GC before this stage, from the newest
    archived results/stage_NN/gc.csv — the riders still close enough that a
    break containing them gets chased. Joined on fc_rider_id (names drift on
    FirstCycling) with normalized-name fallback."""
    by_name = {norm_name(r["rider_name"]): int(r["rider_id"]) for r in riders}
    for nn in range(int(stage) - 1, 0, -1):
        f = RESULTS_ROOT / f"stage_{nn:02d}" / "gc.csv"
        if f.exists():
            top = list(csv.DictReader(f.open()))[:n]
            by_fc = _fc_to_internal_ids(r.get("rider_id") for r in top)
            ids = set()
            for r in top:
                rid = (by_fc.get(str(r.get("rider_id") or ""))
                       or by_name.get(norm_name(r["name"])))
                if rid is not None:
                    ids.add(rid)
            return frozenset(ids)
    raise SystemExit(f"exclude_gc_source=standings but no results/stage_NN/"
                     f"gc.csv archived before stage {stage}")


@lru_cache(maxsize=None)
def sprinter_pool_ids(config_dir: str):
    """Rider ids the model itself classifies as pure sprinters, via the config's
    punchy_filter: real speed on the flat-sprint anchor, collapsing to a fraction
    of it once the road turns selective. On a FLAT day these — not the GC
    captains — are the men an escape has to beat, so a break reading there sets
    ``exclude_sprinters`` and they leave the pool. Mirrors the classifier in
    build_stage_analysis.py so the board and the analysis table agree."""
    d = Path(config_dir)
    pf = json.loads((d / "scenarios.json").read_text()).get("punchy_filter")
    if not pf:
        return frozenset()
    anchor_f = d / f"{pf['sprint_anchor']}.json"
    sel_f = d / f"{pf['selective_scenario']}.json"
    if not (anchor_f.exists() and sel_f.exists()):
        return frozenset()
    floor = pf.get("anchor_floor", 0.01)
    ret_max = pf.get("retention_max", 0.12)
    sel_p = {int(r["rider_id"]): (r.get("blend_win_p") or 0)
             for r in json.loads(sel_f.read_text())["riders"]}
    ids = set()
    for r in json.loads(anchor_f.read_text())["riders"]:
        rid, a = int(r["rider_id"]), (r.get("blend_win_p") or 0)
        if a >= floor and sel_p.get(rid, 0) / a < ret_max:
            ids.add(rid)
    return frozenset(ids)


def exclusion_pool(spec, data, config):
    """Everyone a break-type reading excludes from its conditional pool: the
    top-N GC contenders (actual standings when exclude_gc_source=standings, else
    the GC-model blend), plus every pure sprinter when the spec sets
    exclude_sprinters (the flat-day case)."""
    pool = set()
    n = spec.get("exclude_top_gc")
    if n:
        if spec.get("exclude_gc_source") == "standings":
            pool |= standings_pool_ids(config["stage"], int(n), data["riders"])
        else:
            pool |= gc_pool_ids(int(n))
    if spec.get("exclude_sprinters") and config.get("_dir"):
        pool |= sprinter_pool_ids(config["_dir"])
    return frozenset(pool)


def pool_label(spec):
    return ("on GC" if spec.get("exclude_gc_source") == "standings"
            else "GC-model")


def pool_removed_text(spec):
    """How the excluded pool reads in prose, for card labels and captions."""
    bits = []
    if spec.get("exclude_top_gc"):
        bits.append(f"top {spec['exclude_top_gc']} {pool_label(spec)}")
    if spec.get("exclude_sprinters"):
        bits.append("the sprinters")
    return " and ".join(bits)


def display_riders(spec, data, config):
    """Riders as *presented* for a scenario (never mutates the logged JSON).

    Break-type readings drop the riders who cannot win from an escape — the GC
    captains (``exclude_top_gc``) and, on a flat day, the pure sprinters
    (``exclude_sprinters``) — then renormalize the rest into a conditional
    'if the break wins' win probability (``display_p``). Ordinary scenarios pass
    through with display_p = blend."""
    riders = data["riders"]
    if not (spec.get("exclude_top_gc") or spec.get("exclude_sprinters")):
        return [dict(r, display_p=r.get("blend_win_p")) for r in riders]
    pool = exclusion_pool(spec, data, config)
    kept = [r for r in riders if int(r["rider_id"]) not in pool]
    mass = sum(r.get("blend_win_p") or 0 for r in kept) or 1.0
    return [dict(r, display_p=(r.get("blend_win_p") or 0) / mass) for r in kept]


def load_stage(config_path: Path):
    config = json.loads(config_path.read_text())
    config["_dir"] = str(config_path.parent)
    scen = {}
    for key, spec in config["scenarios"].items():
        if spec.get("hidden"):
            # classification anchors (e.g. the flat-sprint anchor behind the
            # punchy-pool block) are inputs to analysis, not readings of the day
            continue
        f = config_path.parent / f"{key}.json"
        if f.exists():
            scen[key] = json.loads(f.read_text())
    results_file = RESULTS_ROOT / f"stage_{int(config['stage']):02d}" / "results.json"
    results = json.loads(results_file.read_text()) if results_file.exists() else None
    return config, scen, results


def profile_bars(profile):
    rows = []
    for lbl, key in SCORE_ORDER:
        v = profile.get(key) or 0
        rows.append(
            f'<div class="bar-row"><span class="lbl">{lbl}</span>'
            f'<span class="track"><span class="fill" style="width:{100*min(v,1):.0f}%"></span></span>'
            f'<span class="val">{v:.2f}</span></div>')
    return f'<div class="bars">{"".join(rows)}</div>'


DAY_MENU_NAMES = {
    "res_0": "chaos day", "res_1": "fast-finisher power day",
    "res_2": "mountain escape", "res_3": "survivor gallop",
    "res_4": "hard puncheur day", "res_5": "split sprint (res_5)",
    "res_6": "rouleur power group", "res_7": "split sprint",
    "bunch": "bunch sprint", "gc_day": "GC day", "itt": "time trial",
}


def day_key_chip(data):
    """'keyed: mountain escape 0.6 / hard puncheur 0.4' badge for boards
    ranked by the day-menu retrieval channel (prices stay production)."""
    key = data.get("day_key")
    if not key or data.get("board") != "daymenu":
        return ""
    parts = sorted(key.items(), key=lambda kv: -float(kv[1]))
    tot = sum(float(w) for _, w in parts) or 1.0
    txt = " / ".join(
        f"{DAY_MENU_NAMES.get(i, i)}" + (f" {float(w)/tot:.1f}" if len(parts) > 1 else "")
        for i, w in parts)
    return ('<div class="note" style="border-left:3px solid #7a5df0;'
            'padding-left:7px"><b>keyed:</b> ' + esc(txt) +
            ' <span class="muted">(board order by rider-type retrieval; '
            'prices unchanged)</span></div>')


def scenario_cards(config, scen):
    cards = []
    for key, data in scen.items():
        spec = config["scenarios"][key]
        top = sorted(display_riders(spec, data, config),
                     key=lambda r: -(r["display_p"] or 0))[:5]
        toplist = "; ".join(
            f"{esc(r['rider_name'])} <b>{pct(r['display_p'])}</b>" for r in top)
        removed = pool_removed_text(spec)
        label = (f"Top 5 if the break wins ({removed} removed)"
                 if removed else "Top 5 (blend)")
        cards.append(f"""<div class="card">
<h3>{esc(spec.get('short', key))}</h3>
<div class="muted" style="font-family:var(--sans);font-size:12.5px">{esc(data['scenario'])}</div>
{profile_bars(data['avg_profile'])}
{day_key_chip(data)}
<div class="note">{esc(spec.get('note', ''))}</div>
<div class="note"><b>{label}:</b> {toplist}</div>
</div>""")
    return '<div class="cards">' + "".join(cards) + "</div>"


def mass_note(config, scen):
    """Print each unconditional reading's real probability mass.

    The blend is a set of per-rider marginals, NOT a distribution: it sums to
    well over one book (136-156% on a typical stage) while the devigged book
    column sums to exactly 100%. Setting them side by side therefore flatters
    the model, and "Max edge" is inflated by roughly that factor. Say so on the
    page rather than quietly bank the difference. (Conditional break columns are
    excluded — they already renormalize within their own pool.)"""
    bits = []
    for key, data in scen.items():
        spec = config["scenarios"][key]
        if spec.get("exclude_top_gc") or spec.get("exclude_sprinters"):
            continue
        m = sum(r.get("blend_win_p") or 0 for r in data["riders"])
        bits.append(f"{esc(spec.get('short', key))} <b>{100*m:.0f}%</b>")
    if not bits:
        return ""
    return ('<p class="note"><b>Read "Max edge" as directional, not as a '
            'price.</b> The blend is a set of per-rider marginals and does not '
            'sum to one book — across this field each reading totals '
            + ", ".join(bits) + ' — while the devigged book column sums to '
            'exactly 100%. Putting the two side by side flatters the model, and '
            'Max edge is inflated by about that factor: divide a rider\'s '
            'probability by his reading\'s total before calling anything an '
            'edge. Of our heads only the LambdaRank one is natively '
            'book-preserving.</p>')


def board_table(config, scen):
    keys = list(scen.keys())
    specs = config["scenarios"]
    cond = {k: bool(specs[k].get("exclude_top_gc")
                    or specs[k].get("exclude_sprinters")) for k in keys}
    # break readings are conditional; sort + edge use the unconditional readings
    # so their renormalized numbers don't hijack the board or fake an edge
    eff_keys = [k for k in keys if not cond[k]] or keys
    # per-scenario display prob keyed by rider id (the excluded pool is already
    # dropped for break scenarios, so those ids simply won't appear in that column)
    disp = {k: {int(r["rider_id"]): r["display_p"]
                for r in display_riders(specs[k], scen[k], config)}
            for k in keys}

    riders = {}
    for key, data in scen.items():
        for r in data["riders"]:
            rid = int(r["rider_id"])
            e = riders.setdefault(rid, {
                "name": r["rider_name"], "team": r.get("team_name"),
                "book_odds": r.get("book_odds"), "book_devig": r.get("book_devig"),
                "blend": {}})
            e["blend"][key] = disp[key].get(rid)

    def scen_max(e):
        return max([(e["blend"].get(k) or 0) for k in eff_keys], default=0)
    rows = sorted(riders.values(), key=lambda e: -scen_max(e))
    shown = [e for e in rows
             if scen_max(e) >= 0.01 or (e["book_devig"] or 0) >= 0.02][:24]

    head = ("<tr><th>Rider</th><th>Team</th>"
            + "".join(f'<th class="num">{esc(specs[k].get("short", k))}</th>'
                      for k in keys)
            + '<th class="num">Book odds</th><th class="num">Book devig</th>'
              '<th class="num">Max edge</th></tr>')
    body = []
    for e in shown:
        best = scen_max(e)
        bd = e["book_devig"]
        edge = (best - bd) if bd is not None else None
        edge_cell = (f'<td class="num {"pos" if edge > 0 else "neg"}">{100*edge:+.1f}pp</td>'
                     if edge is not None else '<td class="num muted">–</td>')
        body.append(
            "<tr>"
            f"<td>{esc(e['name'])}</td><td class='muted'>{esc(e['team'] or '')}</td>"
            + "".join(f'<td class="num">{pct(e["blend"].get(k))}</td>' for k in keys)
            + (f'<td class="num">{e["book_odds"]:.2f}</td>' if e["book_odds"]
               else '<td class="num muted">n/a</td>')
            + (f'<td class="num">{pct(bd)}</td>' if bd is not None
               else '<td class="num muted">–</td>')
            + edge_cell + "</tr>")
    caveat = ""
    if any(cond.values()):
        names = ", ".join(specs[k].get("short", k) for k in keys if cond[k])
        ck = [k for k in keys if cond[k]]
        gcs = [specs[k]["exclude_top_gc"] for k in ck
               if specs[k].get("exclude_top_gc")]
        by_standings = any(specs[k].get("exclude_gc_source") == "standings"
                           for k in ck)
        drops_sprinters = any(specs[k].get("exclude_sprinters") for k in ck)
        bits = []
        if gcs:
            pool_txt = ("riders on actual GC" if by_standings else "GC contenders")
            bits.append(f"the top {max(gcs)} {pool_txt}")
        if drops_sprinters:
            bits.append("every pure sprinter")
        dashed = ("a GC captain or a pure sprinter" if drops_sprinters
                  else "a GC captain")
        caveat = (f'<div class="note"><b>{esc(names)}</b> is shown conditional on the '
                  f'break winning — {" and ".join(bits)} are removed and the '
                  f'remaining probabilities renormalize within the break pool. That '
                  f'column isn\'t comparable with the book line or the other readings, '
                  f'so it\'s left out of Max&nbsp;edge; a "–" means {dashed} we '
                  f'assume won\'t be up the road.</div>')
    return f'<div class="tablewrap"><table>{head}{"".join(body)}</table></div>' + caveat


def scenario_details(config, scen):
    blocks = []
    for key, data in scen.items():
        spec = config["scenarios"][key]
        pool = exclusion_pool(spec, data, config)
        riders = [r for r in data["riders"] if int(r["rider_id"]) not in pool]
        extra = f" · {pool_removed_text(spec)} removed" if pool else ""
        rows = sorted(riders, key=lambda r: -(r["blend_win_p"] or 0))[:30]
        body = "".join(
            "<tr>"
            f"<td>{i+1}</td><td>{esc(r['rider_name'])}</td>"
            f"<td class='num'>{pct(r['blend_win_p'])}</td>"
            f"<td class='num'>{pct(r['prob_win'])}</td>"
            f"<td class='num'>{pct(r['lambdarank_win_p'])}</td>"
            f"<td class='num'>{pct(r['prob_podium'])}</td>"
            f"<td class='num'>{pct(r['prob_top15'])}</td>"
            + (f"<td class='num'>{r['book_odds']:.2f}</td>" if r.get("book_odds")
               else "<td class='num muted'>n/a</td>")
            + "</tr>"
            for i, r in enumerate(rows))
        blocks.append(f"""<details><summary>{esc(data['scenario'])} — top 30, all heads{extra}</summary>
<div class="tablewrap"><table>
<tr><th>#</th><th>Rider</th><th class="num">Blend</th><th class="num">Cascade</th>
<th class="num">LambdaRank</th><th class="num">Podium</th><th class="num">Top 15</th>
<th class="num">Book odds</th></tr>{body}</table></div></details>""")
    return "".join(blocks)


def analysis_sections(config):
    """Render config['analysis'] blocks (written by build_stage_analysis.py)."""
    blocks = config.get("analysis") or []
    out = []
    for b in blocks:
        head = "".join(f'<th class="num">{esc(c)}</th>' if i else f"<th>{esc(c)}</th>"
                       for i, c in enumerate(b["columns"]))
        body = "".join(
            "<tr>" + "".join(
                f'<td class="num">{esc(c)}</td>' if i else f"<td>{esc(c)}</td>"
                for i, c in enumerate(row)) + "</tr>"
            for row in b["rows"])
        out.append(f"""<section>
<p class="kicker">Angle</p>
<h2>{esc(b['title'])}</h2>
<p>{esc(b['note'])}</p>
<div class="tablewrap"><table><tr>{head}</tr>{body}</table></div>
</section>""")
    return "".join(out)


def results_section(config, scen, results):
    if not results:
        return """<section>
<p class="kicker">After the stage</p>
<h2>Results</h2>
<p class="muted">The stage hasn't been settled yet — this section fills in once the
results capture runs after the finish.</p>
</section>"""

    finishers = [r for r in results["results"] if str(r.get("place", "")).isdigit()]
    finishers.sort(key=lambda r: int(r["place"]))
    top10 = finishers[:10]

    # per-scenario lookups by rider name (results carry FC ids, predictions DB ids)
    def norm(s):
        return " ".join(sorted(s.lower().replace("-", " ").split()))
    lookups = {k: {norm(r["rider_name"]): r for r in d["riders"]}
               for k, d in scen.items()}
    keys = list(scen.keys())

    head = ("<tr><th>Pos</th><th>Rider</th><th>Team</th>"
            + "".join(f'<th class="num">{esc(config["scenarios"][k].get("short", k))} win p</th>'
                      for k in keys) + "</tr>")
    body = []
    for r in top10:
        cells = []
        for k in keys:
            m = lookups[k].get(norm(r["name"]))
            cells.append(f'<td class="num">{pct(m["blend_win_p"]) if m else "–"}</td>')
        cls = ' class="winner"' if int(r["place"]) == 1 else ""
        body.append(f"<tr{cls}><td>{int(r['place'])}</td><td>{esc(r['name'])}</td>"
                    f"<td class='muted'>{esc(r.get('team') or '')}</td>{''.join(cells)}</tr>")

    winner = top10[0] if top10 else None
    score_rows = []
    if winner:
        wn = norm(winner["name"])
        for k in keys:
            m = lookups[k].get(wn)
            p = m["blend_win_p"] if m else None
            bd = m.get("book_devig") if m else None
            score_rows.append(
                f"<tr><td>{esc(config['scenarios'][k].get('short', k))}</td>"
                f"<td class='num'>{pct(p, 2)}</td>"
                f"<td class='num'>{pct(bd, 2) if bd is not None else '–'}</td></tr>")
    score = (f"""<h3>Scenario scoring — probability given to the actual winner</h3>
<div class="tablewrap"><table>
<tr><th>Scenario</th><th class="num">Blend win p</th><th class="num">Book devig</th></tr>
{"".join(score_rows)}</table></div>""" if score_rows else "")

    return f"""<section>
<p class="kicker">After the stage</p>
<h2>Results — won by {esc(winner['name']) if winner else '?'}</h2>
<div class="tablewrap"><table>{head}{"".join(body)}</table></div>
{score}
</section>"""


def reflection_html(config):
    refl = config.get("reflection")
    if not refl:
        return ""
    paras = [refl] if isinstance(refl, str) else list(refl)
    body = "".join(f"<p>{esc(p)}</p>" for p in paras)
    return f"""<section>
<p class="kicker">Reflection</p>
<h2>What we make of it</h2>
{body}
</section>"""


def all_stage_entries():
    """(config, scenario JSONs, results-or-None) for every configured stage."""
    entries = []
    for cfg in sorted(PREDICTIONS_ROOT.glob("stage_*/scenarios.json")):
        entries.append(load_stage(cfg))
    return entries


def stage_strip():
    """Rebuild the stage-links strip from every generated stage page."""
    items = []
    for cfg in sorted(PREDICTIONS_ROOT.glob("stage_*/scenarios.json")):
        c = json.loads(cfg.read_text())
        n = int(c["stage"])
        page = SITE_DIR / f"stage{n:02d}.html"
        if page.exists():
            results = RESULTS_ROOT / f"stage_{n:02d}" / "results.json"
            mark = ' <span class="done">✓</span>' if results.exists() else ""
            items.append(f'<a href="stage{n:02d}.html">Stage {n}</a>{mark}')
    if not items:
        return ""
    lead = ('<a href="stages.html"><b>Stage-by-stage predictions '
            '&amp; reflections →</b></a> · '
            '<a href="gc.html"><b>GC tracker</b></a>')
    return (STRIP_CSS + '\n<div class="stage-strip"><b style="color:var(--ink)">'
            'Tour diary:</b> ' + lead + " · " + " · ".join(items) + "</div>")


def hub_card(config, scen, results):
    n = int(config["stage"])
    picks = []
    for key, data in scen.items():
        spec = config["scenarios"][key]
        disp = display_riders(spec, data, config)
        if not disp:
            continue
        top = max(disp, key=lambda r: r["display_p"] or 0)
        scen_name = spec.get("short", key) + (
            " · if break wins" if pool_removed_text(spec) else "")
        picks.append(
            f'<div class="pickline"><span class="scen">{esc(scen_name)}</span>'
            f'{esc(top["rider_name"])} <b>{pct(top["display_p"])}</b></div>')

    any_scen = next(iter(scen.values()))
    priced = [r for r in any_scen["riders"] if r.get("book_odds")]
    fav = min(priced, key=lambda r: r["book_odds"]) if priced else None
    fav_html = (f'<div class="pickline"><span class="scen">Book favourite</span>'
                f'{esc(fav["rider_name"])} <b>{fav["book_odds"]:.2f}</b> '
                f'({pct(fav["book_devig"])} devig)</div>' if fav else "")

    if results:
        finishers = [r for r in results["results"]
                     if str(r.get("place", "")).isdigit()]
        winner = min(finishers, key=lambda r: int(r["place"])) if finishers else None
        status = (f'<span class="chip done-chip">Won by {esc(winner["name"])}</span>'
                  if winner else '<span class="chip">results in</span>')
    else:
        status = '<span class="chip wait-chip">awaiting results</span>'

    refl = config.get("reflection")
    refl_html = ""
    if refl and results:
        paras = [refl] if isinstance(refl, str) else list(refl)
        refl_html = ('<div class="refl">' +
                     "".join(f"<p>{esc(p)}</p>" for p in paras) + "</div>")

    return f"""<div class="card stage-card">
<div class="stage-head"><h3><a href="stage{n:02d}.html">Stage {n} — {esc(config.get('date', ''))}</a></h3>{status}</div>
{"".join(picks)}
{fav_html}
{refl_html}
<div class="note"><a href="stage{n:02d}.html">Full board, all scenarios →</a></div>
</div>"""


HUB_EXTRA_CSS = """
  .stage-card{margin:0 0 16px}
  .stage-head{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:6px}
  .stage-head h3{margin:0;font-size:18px}
  .stage-head a{color:var(--ink);text-decoration:none;border-bottom:1px solid var(--line)}
  .chip{font-family:var(--sans);font-size:11.5px;font-weight:600;letter-spacing:.05em;
        text-transform:uppercase;padding:2px 9px;border-radius:99px;border:1px solid var(--line);color:var(--slate)}
  .done-chip{background:var(--green-soft);color:var(--green);border-color:var(--green-soft)}
  .wait-chip{background:var(--yellow-soft);border-color:var(--yellow-soft);color:#7a6410}
  .pickline{font-family:var(--sans);font-size:14px;padding:3px 0;font-variant-numeric:tabular-nums}
  .pickline .scen{display:inline-block;min-width:170px;padding-right:12px;
                  color:var(--slate);font-size:12.5px;
                  font-weight:600;letter-spacing:.04em;text-transform:uppercase}
  .refl{border-left:3px solid var(--yellow);padding:2px 0 2px 14px;margin:12px 0 4px}
  .refl p{font-size:15.5px;margin:0 0 8px}
  .note a{color:var(--blue);text-decoration:none;font-family:var(--sans);font-size:13px}
"""


def gc_card():
    """Compact GC-picture card for the hub, from the latest GC run."""
    gc_dir = PREDICTIONS_ROOT / "gc"
    preds = [p for p in gc_dir.glob("*.json") if p.name != "scenarios.json"]
    if not preds:
        return ""
    data = json.loads(max(preds, key=lambda p: p.stat().st_mtime).read_text())
    state = data.get("state") or {}
    through = state.get("through_stage")

    gaps = {}
    if through:
        gc_file = RESULTS_ROOT / f"stage_{int(through):02d}" / "gc.csv"
        if gc_file.exists():
            import csv as _csv
            with open(gc_file) as f:
                for row in _csv.DictReader(f):
                    gaps[" ".join(sorted(row["name"].lower().split()))] = row["gap"]

    def gap_for(name):
        g = gaps.get(" ".join(sorted(name.lower().split())))
        if g in (None, ""):
            return "–"
        s = float(g)
        return "0:00" if s == 0 else f"+{int(s//60)}:{int(s%60):02d}"

    top = sorted(data["riders"], key=lambda r: -(r.get("blend_win_p") or 0))[:6]
    rows = "".join(
        "<tr>"
        f"<td>{esc(r['rider_name'])}</td>"
        f"<td class='num'>{gap_for(r['rider_name'])}</td>"
        f"<td class='num'>{pct(r.get('blend_win_p'))}</td>"
        f"<td class='num'>{pct(r.get('gc_outlook_win_p'))}</td>"
        f"<td class='num'>{pct(r.get('book_devig'))}</td>"
        "</tr>" for r in top)
    return f"""<div class="card stage-card">
<div class="stage-head"><h3>The GC picture</h3>
<span class="chip">through stage {through if through else '?'}</span></div>
<div class="tablewrap" style="margin:10px 0"><table>
<tr><th>Rider</th><th class="num">GC gap</th><th class="num">Model win</th>
<th class="num">Outlook head</th><th class="num">Book devig</th></tr>
{rows}</table></div>
<div class="note">Model win = pre-race heads with live form (book-preserving).
The outlook head is state-aware but per-rider — its probabilities don't sum
to one book, and {through if through else 'few'}/21 stages is the thinnest
state it sees; read it as "how safe is the current position", not as odds.
<b><a href="gc.html">Full stage-by-stage GC tracker →</a></b></div>
</div>"""


def build_stages_hub():
    entries = [e for e in all_stage_entries() if e[1]]
    if not entries:
        return
    settled = sum(1 for _, _, res in entries if res)
    cards = gc_card() + "".join(hub_card(c, s, r) for c, s, r in entries)
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TdF 2026 · Stage-by-stage predictions &amp; reflections</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🚴</text></svg>">
<style>{CSS}{HUB_EXTRA_CSS}</style>
</head>
<body>
<div class="wrap">
<header>
  <div class="eyebrow">Cycling race predictor · Tour de France 2026</div>
  <h1>The Tour, stage by stage</h1>
  <p class="standfirst">Every stage gets priced the morning before under several
  course readings, compared with the bookmaker's line, and settled against the
  result — with a reflection on what the model got right and why.</p>
  <div class="meta">
    <span><b>{len(entries)}</b>&nbsp;stages predicted</span>
    <span><b>{settled}</b>&nbsp;settled</span>
    <span>updated&nbsp;<b>{datetime.now().strftime('%Y-%m-%d')}</b></span>
  </div>
  <p class="backlink"><a href="index.html">← System overview, season boards &amp; the full Tour views</a></p>
</header>
<section>
{cards}
</section>
<div class="footer">Predictions logged pre-stage to prediction_log; odds from the
Kambi (Unibet) archive; results from FirstCycling. Full methodology on the
<a href="index.html">main page</a>.</div>
</div>
</body>
</html>
"""
    out = SITE_DIR / "stages.html"
    out.write_text(page)
    print(f"Wrote {out} ({out.stat().st_size/1024:.0f} KB)")


def inject_strip():
    src = SOURCE_HTML.read_text()
    block = f"<!-- STAGES:START -->\n{stage_strip()}\n<!-- STAGES:END -->"
    if "<!-- STAGES:START -->" in src:
        pre = src.split("<!-- STAGES:START -->")[0]
        post = src.split("<!-- STAGES:END -->")[1]
        src = pre + block + post
    else:
        anchor = "<!-- ================= HEADS VIEW ================= -->"
        src = src.replace(anchor, block + "\n\n" + anchor)
    SOURCE_HTML.write_text(src)


def main():
    config_path = Path(sys.argv[1]).resolve()
    config, scen, results = load_stage(config_path)
    if not scen:
        sys.exit("No scenario prediction JSONs found next to the config.")
    n = int(config["stage"])
    any_scen = next(iter(scen.values()))
    model_version = any_scen.get("model_version", "").split("|")[0][:10]
    book_note = any_scen.get("book_source") or "no capture"

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TdF 2026 · Stage {n} — model predictions</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🚴</text></svg>">
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<header>
  <div class="eyebrow">Cycling race predictor · Tour de France 2026</div>
  <h1>Stage {n} — {esc(config.get('date', ''))}</h1>
  <p class="standfirst">The same production stack priced under {len(scen)} course
  readings, against the bookmaker's pre-stage line. Each scenario is one opinion
  about what kind of day this is; the results section settles the argument.</p>
  <div class="meta">
    <span><b>{len(scen)}</b>&nbsp;scenarios</span>
    <span><b>{len(any_scen['riders'])}</b>&nbsp;riders priced</span>
    <span>models retrained&nbsp;<b>{esc(model_version)}</b></span>
    <span>book snapshot&nbsp;<b>{esc(book_note)}</b></span>
  </div>
  <p class="backlink"><a href="index.html">← System overview, season boards &amp; the full Tour views</a></p>
</header>

<section>
  <p class="kicker">The fork</p>
  <h2>{len(scen)} readings of the same road</h2>
  <p>Course profile is an input the model can't see from a map — it's set from
  reference races (or overridden by hand). Different readings redistribute the
  same probability mass across rider types.</p>
  {scenario_cards(config, scen)}
</section>

<section>
  <p class="kicker">The board</p>
  <h2>Win probabilities, scenario by scenario</h2>
  <p>Blend win probability per scenario (cascade × LambdaRank, DNF-adjusted at
  the pricing layer), next to the devigged Kambi (Unibet) win line captured the
  morning before the stage. "Max edge" compares the most favourable scenario
  against the book — treat it as scenario-conditional, not a free bet.</p>
  {mass_note(config, scen)}
  {board_table(config, scen)}
  {scenario_details(config, scen)}
</section>

{analysis_sections(config)}

{results_section(config, scen, results)}

{reflection_html(config)}

<div class="footer">Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} ·
prediction JSONs in performance_eval/tour-de-france-2026/predictions/stage_{n:02d}/ ·
odds archive {esc(book_note)} · all runs logged to prediction_log for settlement.</div>
</div>
</body>
</html>
"""
    out = SITE_DIR / f"stage{n:02d}.html"
    out.write_text(page)
    print(f"Wrote {out} ({out.stat().st_size/1024:.0f} KB)")

    build_stages_hub()
    inject_strip()
    print("Refreshed stage strip in predictor-architecture.html")
    runpy.run_path(str(HERE / "make_netlify.py"))


if __name__ == "__main__":
    main()
