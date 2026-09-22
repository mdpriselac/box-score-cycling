"""
Generate the prediction page for a one-day race.

    python3 netlify_site/build/build_oneday_page.py \
        performance_eval/strade-bianche-2026/predictions/race/scenarios.json

Reads the race's ``target: one_day`` config, the per-scenario prediction JSONs
written by predict_stage_scenarios.py, and — once the race has been settled —
the archived result under ``<campaign>/results/race/``. Writes one page,
``netlify_site/<slug>-<year>.html``, in the same paper/serif language as the
stage pages.

A one-day race has no stage strip, no GC tracker and no day key: the page is
the race. Rerun after settlement to append the "After the race" section; the
page upgrades in place. Refresh the site frame afterwards:

    uv run python netlify_site/build/build_site_index.py
    uv run python netlify_site/build/build_site_frame.py

Results are joined to the boards by rider id — the archive carries
FirstCycling ids and the boards carry internal database ids, so the join goes
through the riders table (names drift on FirstCycling and are never ids); a
normalised-name match is the last resort and is reported on the page.
"""

import html
import json
import os
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).parent
SITE_DIR = HERE.parent
PROJECT_ROOT = SITE_DIR.parent
sys.path.insert(0, str(HERE))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from build_stage_page import provisional_note  # noqa: E402  (sibling script, same directory)
from cycling_project.nightly import site_paths  # noqa: E402  (one rule for page names, chip W)

# CYCLING_DB_PATH redirects serving at a slim slice (see cycling_project/db_path.py);
# resolved inline because this script runs without the package on sys.path.
DB_PATH = Path(os.environ.get("CYCLING_DB_PATH")
               or PROJECT_ROOT / "cycling_project" / "webscrape_tools" / "database"
               / "database" / "cycling_races.db")

# The default scenario a one-day config carries (cycling_project/nightly/oneday.py).
PRIMARY_KEY = "own_history"

SCORE_ORDER = [
    ("sprint", "race_sprint_score"), ("mountain", "race_mountain_score"),
    ("hilly", "race_hilly_score"), ("rolling", "race_rolling_score"),
    ("break", "race_breakaway_score"), ("TT", "race_time_trial_score"),
]

# Shared with build_stage_page.py; kept local so this script needs no imports.
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
  .chip{font-family:var(--sans);font-size:11.5px;font-weight:600;letter-spacing:.05em;
        text-transform:uppercase;padding:2px 9px;border-radius:99px;
        border:1px solid var(--line);color:var(--slate);white-space:nowrap}
  .chip.settled{background:var(--green-soft);color:var(--green);border-color:var(--green-soft)}
  .chip.predicted{background:var(--yellow-soft);border-color:var(--yellow-soft);color:#7a6410}
  .banner{background:#ece9e4;border:1px solid #ddd8d1;border-left:4px solid var(--red);
          border-radius:6px;padding:12px 16px;margin:22px 0 0;font-family:var(--sans);
          font-size:14px;line-height:1.5;color:#4A4038}
  .footer{margin-top:80px;padding-top:16px;border-top:1px solid var(--line);
          font-family:var(--sans);font-size:12.5px;color:var(--slate)}
"""


def esc(s):
    return html.escape(str(s)) if s is not None else ""


def pct(v, digits=1):
    # NaN means "this head didn't price that rider" — a dash, never "nan%".
    if v is None or v != v:
        return "–"
    return f"{100*v:.{digits}f}%"


def norm_name(s):
    return " ".join(sorted((s or "").lower().replace("-", " ").split()))


def fmt_date(iso):
    try:
        return date.fromisoformat(str(iso)).strftime("%-d %B %Y")
    except (TypeError, ValueError):
        return str(iso or "")


# ---------------------------------------------------------------- loading

def campaign_identity(campaign_root, config):
    """Publication identity: race name, page slug, hub URL.

    campaign.json is the registry record; a config-level ``site`` block still
    overrides it, and the campaign directory name is the last resort.
    """
    registry = {}
    try:
        registry = json.loads((campaign_root / "campaign.json").read_text())
    except (OSError, json.JSONDecodeError):
        pass
    site = dict(registry.get("site") or {})
    site.update(config.get("site") or {})
    year = int(config.get("year") or registry.get("year") or 0)
    slug = site_paths.route_slug(campaign_root.name, registry, config)
    race_name = site.get("race_name") or registry.get("name") or config.get("label") or slug
    return {
        "slug": slug,
        "year": year,
        "race_name": race_name,
        "short_name": site.get("short_name") or f"{race_name} {year}".strip(),
        "page": site_paths.oneday_page_name(campaign_root.name, registry, config, year=year),
        "hub_url": f"/race/{slug}/{year}",
        "category": registry.get("category"),
    }


def load_race(config_path):
    """(config, {scenario key: board}, results-or-None) for one race."""
    config = json.loads(config_path.read_text())
    if config.get("target") != "one_day":
        sys.exit(f"{config_path}: not a one-day config "
                 f"(target={config.get('target')!r}) — use build_stage_page.py")
    boards = {}
    for key, spec in (config.get("scenarios") or {}).items():
        if spec.get("hidden"):
            continue
        f = config_path.parent / f"{key}.json"
        if f.exists():
            boards[key] = json.loads(f.read_text())
    campaign_root = config_path.parents[2]
    results_file = campaign_root / "results" / "race" / "results.json"
    results = json.loads(results_file.read_text()) if results_file.exists() else None
    return config, boards, results, campaign_root


def primary_key(boards):
    return PRIMARY_KEY if PRIMARY_KEY in boards else next(iter(boards))


# ------------------------------------------------------------- id joining

def fc_to_internal_ids(fc_ids):
    """{fc_rider_id: internal riders.id} — the archive joins on the stable fc id."""
    fc_ids = [str(f) for f in fc_ids if f and not str(f).startswith("uci:")]
    if not fc_ids or not DB_PATH.exists():
        return {}
    with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as conn:
        rows = conn.execute(
            f"SELECT fc_rider_id, id FROM riders WHERE fc_rider_id IN "
            f"({','.join('?' for _ in fc_ids)})", fc_ids).fetchall()
    return {str(fc): int(i) for fc, i in rows}


def join_results_to_riders(results, boards):
    """Attach each archived result row to its internal rider id.

    Returns ``(rows, n_by_name)`` where each row gains ``internal_id`` (None
    when nothing matched) and ``n_by_name`` counts the rows that needed the
    name fallback — reported on the page rather than hidden.
    """
    rows = [dict(r) for r in (results or {}).get("results", [])]
    by_fc = fc_to_internal_ids(r.get("rider_id") for r in rows)
    by_name = {}
    for board in boards.values():
        for r in board["riders"]:
            by_name.setdefault(norm_name(r["rider_name"]), int(r["rider_id"]))
    n_by_name = 0
    for r in rows:
        rid = by_fc.get(str(r.get("rider_id") or ""))
        if rid is None:
            rid = by_name.get(norm_name(r.get("name")))
            if rid is not None:
                n_by_name += 1
        r["internal_id"] = rid
    return rows, n_by_name


# --------------------------------------------------------------- sections

def profile_bars(profile):
    rows = []
    for lbl, key in SCORE_ORDER:
        v = profile.get(key) or 0
        rows.append(
            f'<div class="bar-row"><span class="lbl">{lbl}</span>'
            f'<span class="track"><span class="fill" style="width:{100*min(v,1):.0f}%"></span></span>'
            f'<span class="val">{v:.2f}</span></div>')
    return f'<div class="bars">{"".join(rows)}</div>'


def ref_name(name):
    """'Strade Bianche - Strade Bianche' -> 'Strade Bianche'.

    The reference profile's display name is 'race - competition'; for a one-day
    race the two halves are the same and the repetition is just noise.
    """
    text = str(name or "")
    left, sep, right = text.partition(" - ")
    return left if sep and left.strip() == right.strip() else text


def reference_list(board):
    refs = board.get("references") or []
    if not refs:
        return ""
    bits = "; ".join(f"{esc(ref_name(r.get('name')))} ({esc(str(r.get('date') or '')[:4])})"
                     for r in refs)
    return f'<div class="note"><b>References:</b> {bits}</div>'


def scenario_cards(config, boards):
    cards = []
    for key, board in boards.items():
        spec = config["scenarios"][key]
        top = sorted(board["riders"], key=lambda r: -(r.get("blend_win_p") or 0))[:5]
        toplist = "; ".join(
            f"{esc(r['rider_name'])} <b>{pct(r.get('blend_win_p'))}</b>" for r in top)
        cards.append(f"""<div class="card">
<h3>{esc(spec.get('short', key))}</h3>
<div class="muted" style="font-family:var(--sans);font-size:12.5px">{esc(board['scenario'])}</div>
{profile_bars(board['avg_profile'])}
{reference_list(board)}
<div class="note">{esc(spec.get('note', ''))}</div>
<div class="note"><b>Top 5 (blend):</b> {toplist}</div>
</div>""")
    return '<div class="cards">' + "".join(cards) + "</div>"


def mass_note(boards):
    """Each reading's real probability mass — the blend is not a distribution."""
    bits = []
    for key, board in boards.items():
        m = sum(r.get("blend_win_p") or 0 for r in board["riders"])
        bits.append(f"{esc(key.replace('_', ' '))} <b>{100*m:.0f}%</b>")
    return ('<p class="note"><b>Read "Max edge" as directional, not as a price.</b> '
            'The blend is a set of per-rider marginals and does not sum to one book — '
            'across this field each reading totals ' + ", ".join(bits) + ' — while the '
            'devigged market column sums to exactly 100%. Putting the two side by side '
            'flatters the model, and Max edge is inflated by about that factor. Of our '
            'heads only the LambdaRank one is natively book-preserving.</p>')


def board_table(config, boards, main):
    """One board: the primary reading's heads, alternates' blends, the market line."""
    specs = config["scenarios"]
    alts = [k for k in boards if k != main]
    by_rider = {}
    for key, board in boards.items():
        for r in board["riders"]:
            rid = int(r["rider_id"])
            e = by_rider.setdefault(rid, {
                "name": r["rider_name"], "team": r.get("team_name"),
                "book_odds": r.get("book_odds"), "book_devig": r.get("book_devig"),
                "blend": {}, "heads": {}})
            e["blend"][key] = r.get("blend_win_p")
            if key == main:
                e["heads"] = {h: r.get(h) for h in
                              ("prob_win", "lambdarank_win_p", "prob_podium", "prob_top15")}
            if r.get("book_odds") and not e["book_odds"]:
                e["book_odds"], e["book_devig"] = r.get("book_odds"), r.get("book_devig")

    def best(e):
        return max([(e["blend"].get(k) or 0) for k in boards], default=0)

    rows = sorted(by_rider.values(), key=lambda e: -best(e))
    shown = [e for e in rows if best(e) >= 0.01 or (e["book_devig"] or 0) >= 0.02][:24]

    head = ("<tr><th>Rider</th><th>Team</th>"
            '<th class="num">Blend</th><th class="num">Cascade</th>'
            '<th class="num">LambdaRank</th>'
            + "".join(f'<th class="num">{esc(specs[k].get("short", k))}</th>' for k in alts)
            + '<th class="num">Market odds</th><th class="num">Market devig</th>'
              '<th class="num">Max edge</th></tr>')
    body = []
    for e in shown:
        bd = e["book_devig"]
        edge = (best(e) - bd) if bd is not None else None
        edge_cell = (f'<td class="num {"pos" if edge > 0 else "neg"}">{100*edge:+.1f}pp</td>'
                     if edge is not None else '<td class="num muted">–</td>')
        body.append(
            "<tr>"
            f"<td>{esc(e['name'])}</td><td class='muted'>{esc(e['team'] or '')}</td>"
            f'<td class="num">{pct(e["blend"].get(main))}</td>'
            f'<td class="num">{pct(e["heads"].get("prob_win"))}</td>'
            f'<td class="num">{pct(e["heads"].get("lambdarank_win_p"))}</td>'
            + "".join(f'<td class="num">{pct(e["blend"].get(k))}</td>' for k in alts)
            + (f'<td class="num">{e["book_odds"]:.2f}</td>' if e["book_odds"]
               else '<td class="num muted">n/a</td>')
            + (f'<td class="num">{pct(bd)}</td>' if bd is not None
               else '<td class="num muted">–</td>')
            + edge_cell + "</tr>")
    return f'<div class="tablewrap"><table>{head}{"".join(body)}</table></div>'


def scenario_details(config, boards):
    blocks = []
    for key, board in boards.items():
        rows = sorted(board["riders"], key=lambda r: -(r.get("blend_win_p") or 0))[:30]
        body = "".join(
            "<tr>"
            f"<td>{i+1}</td><td>{esc(r['rider_name'])}</td>"
            f"<td class='num'>{pct(r.get('blend_win_p'))}</td>"
            f"<td class='num'>{pct(r.get('prob_win'))}</td>"
            f"<td class='num'>{pct(r.get('lambdarank_win_p'))}</td>"
            f"<td class='num'>{pct(r.get('prob_podium'))}</td>"
            f"<td class='num'>{pct(r.get('prob_top15'))}</td>"
            + (f"<td class='num'>{r['book_odds']:.2f}</td>" if r.get("book_odds")
               else "<td class='num muted'>n/a</td>")
            + "</tr>"
            for i, r in enumerate(rows))
        blocks.append(f"""<details><summary>{esc(board['scenario'])} — top 30, all heads</summary>
<div class="tablewrap"><table>
<tr><th>#</th><th>Rider</th><th class="num">Blend</th><th class="num">Cascade</th>
<th class="num">LambdaRank</th><th class="num">Podium</th><th class="num">Top 15</th>
<th class="num">Market odds</th></tr>{body}</table></div></details>""")
    return "".join(blocks)


def results_section(config, boards, results):
    if not results:
        return """<section>
<p class="kicker">After the race</p>
<h2>Result</h2>
<p class="muted">The race hasn't been settled yet — this section fills in once the
results archive lands under results/race/.</p>
</section>"""

    rows, n_by_name = join_results_to_riders(results, boards)
    finishers = [r for r in rows if str(r.get("place", "")).strip().isdigit()]
    finishers.sort(key=lambda r: int(r["place"]))
    top10 = finishers[:10]
    keys = list(boards)
    lookup = {k: {int(r["rider_id"]): r for r in boards[k]["riders"]} for k in keys}

    head = ("<tr><th>Pos</th><th>Rider</th><th>Team</th>"
            + "".join(f'<th class="num">{esc(config["scenarios"][k].get("short", k))} win p</th>'
                      for k in keys) + "</tr>")
    body = []
    for r in top10:
        cells = []
        for k in keys:
            m = lookup[k].get(r["internal_id"]) if r["internal_id"] else None
            cells.append(f'<td class="num">{pct(m.get("blend_win_p")) if m else "–"}</td>')
        cls = ' class="winner"' if int(r["place"]) == 1 else ""
        body.append(f"<tr{cls}><td>{int(r['place'])}</td><td>{esc(r['name'])}</td>"
                    f"<td class='muted'>{esc(r.get('team') or '')}</td>{''.join(cells)}</tr>")

    winner = top10[0] if top10 else None
    score_rows = []
    if winner and winner["internal_id"]:
        for k in keys:
            m = lookup[k].get(winner["internal_id"])
            score_rows.append(
                f"<tr><td>{esc(config['scenarios'][k].get('short', k))}</td>"
                f"<td class='num'>{pct(m.get('blend_win_p'), 2) if m else '–'}</td>"
                f"<td class='num'>{pct(m.get('prob_win'), 2) if m else '–'}</td>"
                f"<td class='num'>{pct(m.get('lambdarank_win_p'), 2) if m else '–'}</td>"
                f"<td class='num'>{pct(m.get('book_devig'), 2) if m and m.get('book_devig') is not None else '–'}</td>"
                "</tr>")
    score = (f"""<h3>Scoring — probability given to the actual winner</h3>
<div class="tablewrap"><table>
<tr><th>Reading</th><th class="num">Blend</th><th class="num">Cascade</th>
<th class="num">LambdaRank</th><th class="num">Market devig</th></tr>
{"".join(score_rows)}</table></div>""" if score_rows else "")

    unmatched = sum(1 for r in finishers if not r["internal_id"])
    join_note = (f'<p class="note muted" style="font-family:var(--sans);font-size:13px">'
                 f'Result rows are joined to the boards by FirstCycling rider id through the '
                 f'riders table. {n_by_name} row(s) needed the normalised-name fallback; '
                 f'{unmatched} finisher(s) could not be matched at all.</p>'
                 if (n_by_name or unmatched) else "")

    return f"""<section>
<p class="kicker">After the race</p>
<h2>Result — won by {esc(winner['name']) if winner else '?'}</h2>
<div class="tablewrap"><table>{head}{"".join(body)}</table></div>
{provisional_note(results, rows=finishers)}
{score}
{join_note}
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


def form_asof(boards):
    """The date the form features were re-aged to, if every board agrees on one."""
    dates = {(b.get("form_status") or {}).get("asof_date") for b in boards.values()}
    dates.discard(None)
    return dates.pop() if len(dates) == 1 else None


def post_hoc_banner(config, boards):
    """A board built after the race is a reconstruction, and must say so.

    It also has to say *why* it cannot be read as a prediction: the serving
    path re-ages a rider's form to the day the board is built, not to the
    config's race date, so a board rebuilt months later has seen the season
    that followed the race.
    """
    scenarios = config.get("scenarios") or {}
    if not (config.get("post_hoc") or (scenarios and all(s.get("post_hoc") for s in scenarios.values()))):
        return ""
    asof, raced = form_asof(boards), str(config.get("date") or "")
    leak = ""
    if asof and raced and asof > raced:
        leak = (f" The form features were re-aged to {esc(fmt_date(asof))}, not to race day: "
                f"these boards have seen every result between {esc(fmt_date(raced))} and then.")
    return ('<div class="banner"><b>Post-hoc reconstruction, not a published '
            'prediction.</b> These boards were built after the race had been run, to '
            'commission the one-day path. Nothing here was frozen before the start, so it '
            'is not evidence about the model and it is not scored on the record.'
            + leak + '</div>')


# ------------------------------------------------------------------ main

def render(config, boards, results, ident):
    main = primary_key(boards)
    main_board = boards[main]
    model_version = (main_board.get("model_version") or "").split("|")[0][:10]
    book_note = main_board.get("book_source") or "no capture"
    settled = bool(results)
    chip = ('<span class="chip settled">settled</span>' if settled
            else '<span class="chip predicted">awaiting the result</span>')
    reading_word = "reading" if len(boards) == 1 else "readings"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(ident['short_name'])} — model predictions</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🚴</text></svg>">
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<header>
  <div class="eyebrow">Cycling race predictor · one-day race</div>
  <h1>{esc(config.get('label') or ident['race_name'])} {chip}</h1>
  <p class="standfirst">One day, one result: the production stack priced the whole
  field under {len(boards)} course {reading_word}, against the market's line where one
  was captured. A one-day race is its own best reference — the main reading is built
  from this race's own recent editions.</p>
  <div class="meta">
    <span>Raced&nbsp;<b>{esc(fmt_date(config.get('date')))}</b></span>
    <span><b>{len(boards)}</b>&nbsp;{reading_word}</span>
    <span><b>{len(main_board['riders'])}</b>&nbsp;riders priced</span>
    <span>models retrained&nbsp;<b>{esc(model_version)}</b></span>
    <span>market snapshot&nbsp;<b>{esc(book_note)}</b></span>
  </div>
  {post_hoc_banner(config, boards)}
  <p class="backlink"><a href="{ident['hub_url']}">← {esc(ident['race_name'])} hub</a>
   &nbsp;·&nbsp; <a href="/races">All races</a>
   &nbsp;·&nbsp; <a href="/model">How the model works</a></p>
</header>

<section>
  <p class="kicker">The fork</p>
  <h2>{len(boards)} {reading_word} of the same road</h2>
  <p>Course profile is an input the model cannot see from a map — it is set from
  reference races. The main reading averages this race's own last editions, so the
  terrain and the kind of rider it selects come from the race's own history; any
  alternate reading swaps in an archetype set to ask what a different day would do to
  the same field.</p>
  {scenario_cards(config, boards)}
</section>

<section>
  <p class="kicker">The board</p>
  <h2>Win probabilities across the heads</h2>
  <p>Blend is the production price (cascade × LambdaRank, DNF-adjusted at the pricing
  layer); Cascade and LambdaRank are the two underlying heads shown for the main
  reading. The market columns are the devigged win line, present as the information
  benchmark the model is scored against.</p>
  {mass_note(boards)}
  {board_table(config, boards, main)}
  {scenario_details(config, boards)}
</section>

{results_section(config, boards, results)}

{reflection_html(config)}

<div class="footer">Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} ·
prediction JSONs in {esc(ident['slug'])}-{ident['year']}/predictions/race/ ·
market archive {esc(book_note)} ·
prospective runs are logged to prediction_log before the start.</div>
</div>
</body>
</html>
"""


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__.strip().splitlines()[0])
    config_path = Path(sys.argv[1]).resolve()
    config, boards, results, campaign_root = load_race(config_path)
    if not boards:
        sys.exit("No scenario prediction JSONs found next to the config — "
                 "run predict_stage_scenarios.py first.")
    ident = campaign_identity(campaign_root, config)
    out = SITE_DIR / ident["page"]
    out.write_text(render(config, boards, results, ident))
    print(f"Wrote {out} ({out.stat().st_size/1024:.0f} KB)"
          f"{' — settled' if results else ''}")
    print("Refresh the frame: build_site_index.py then build_site_frame.py")


if __name__ == "__main__":
    main()
