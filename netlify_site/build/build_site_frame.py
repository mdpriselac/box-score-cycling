"""
Render the site frame (home, /races, calendar months, race hubs) from
netlify_site/site-index.json.

    uv run python netlify_site/build/build_site_index.py   # refresh the index
    uv run python netlify_site/build/build_site_frame.py   # then the frame

Writes netlify_site/_frame/…; the Worker (netlify_site/worker/index.js) maps
clean URLs onto these files. Every view renders from the index — this script
never parses campaign HTML. The existing generated pages (stage pages, GC
trackers, stage diaries, index.html) are wrapped by the frame, never touched.

Design follows the campaign pages' editorial language: paper background,
Charter serif body, Avenir sans headings, yellow eyebrow bar, status chips
(green settled / yellow predicted / plain upcoming / struck-through
cancelled). Market probabilities are referenced only as an information
benchmark, never as betting guidance.
"""

import calendar
import html
import json
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITE_DIR = HERE.parent
INDEX_PATH = SITE_DIR / "site-index.json"
FRAME_DIR = SITE_DIR / "_frame"

FAVICON = ('<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://'
           'www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em'
           '%22 font-size=%2290%22>🚴</text></svg>">')

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
  .topnav{font-family:var(--sans);font-size:13px;display:flex;flex-wrap:wrap;
    align-items:baseline;gap:8px 20px;padding:16px 0 14px;border-bottom:1px solid var(--line)}
  .topnav .brand{font-weight:700;font-size:14px;letter-spacing:-.01em;color:var(--ink);
    text-decoration:none;margin-right:auto}
  .topnav .brand::before{content:"";display:inline-block;width:18px;height:7px;
    background:var(--yellow);margin-right:9px;vertical-align:baseline}
  .topnav a{color:var(--blue);text-decoration:none;border-bottom:1px solid transparent}
  .topnav a:hover{border-bottom-color:var(--blue-soft)}
  .topnav a.here{color:var(--ink);font-weight:600;border-bottom:2px solid var(--yellow)}
  header{padding:44px 0 8px}
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
  section{margin-top:56px}
  .kicker{font-family:var(--sans);font-size:12px;font-weight:600;
    letter-spacing:.14em;text-transform:uppercase;color:var(--blue);margin:0 0 6px}
  h2{font-family:var(--sans);font-weight:700;font-size:26px;letter-spacing:-.01em;
     line-height:1.15;margin:0 0 14px;text-wrap:balance}
  h3{font-family:var(--sans);font-weight:600;font-size:17px;margin:24px 0 8px}
  p{margin:0 0 16px;max-width:680px}
  a{color:var(--blue)}
  .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:16px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:16px 18px}
  .card h3{margin:0 0 4px;font-size:16px}
  .card h3 a{color:var(--ink);text-decoration:none}
  .card h3 a:hover{color:var(--blue)}
  .card .note{font-size:13.5px;color:var(--slate);line-height:1.5;margin:8px 0 0;font-family:var(--sans)}
  .card .go{font-family:var(--sans);font-size:13px;margin-top:10px}
  .card .go a{text-decoration:none;border-bottom:1px solid var(--blue-soft);font-weight:600}
  table{border-collapse:collapse;width:100%;font-family:var(--sans);font-size:14px}
  th{font-size:11.5px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;
     color:var(--slate);text-align:left;padding:8px 10px;border-bottom:2px solid var(--ink)}
  td{padding:7px 10px;border-bottom:1px solid var(--line);font-variant-numeric:tabular-nums}
  td a{text-decoration:none;border-bottom:1px solid var(--blue-soft)}
  .muted{color:var(--slate)}
  .tablewrap{overflow-x:auto;background:var(--card);border:1px solid var(--line);
             border-radius:8px;padding:6px 12px 10px;margin:18px 0}
  .chip{font-family:var(--sans);font-size:11.5px;font-weight:600;letter-spacing:.05em;
        text-transform:uppercase;padding:2px 9px;border-radius:99px;
        border:1px solid var(--line);color:var(--slate);white-space:nowrap}
  .chip.settled{background:var(--green-soft);color:var(--green);border-color:var(--green-soft)}
  .chip.predicted{background:var(--yellow-soft);border-color:var(--yellow-soft);color:#7a6410}
  .chip.cancelled{background:#ece9e4;border-color:#ddd8d1;color:#6b6259;
    text-decoration:line-through;text-decoration-thickness:1px}
  .chip.live{background:var(--blue-soft);color:var(--blue);border-color:var(--blue-soft)}
  .chip.archive{background:transparent}
  .mono{font-family:var(--mono);font-size:12.5px}
  .entry{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;padding:9px 0;
         border-bottom:1px solid var(--line);font-family:var(--sans);font-size:14.5px}
  .entry:last-child{border-bottom:none}
  .entry .d{color:var(--slate);font-variant-numeric:tabular-nums;width:88px;flex:none;font-size:13px}
  .entry .race{color:var(--slate);font-size:12.5px;font-weight:600;
    letter-spacing:.04em;text-transform:uppercase;width:110px;flex:none}
  .entry a{text-decoration:none;border-bottom:1px solid var(--blue-soft);font-weight:600;color:var(--ink)}
  .entry a:hover{color:var(--blue)}
  .listbox{background:var(--card);border:1px solid var(--line);border-radius:8px;
           padding:6px 18px;margin:18px 0}
  .stage-strip{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0 6px}
  .stage-strip a,.stage-strip span{font-family:var(--sans);font-size:13px;font-weight:600;
    padding:5px 0;width:40px;text-align:center;border-radius:6px;border:1px solid var(--line);
    color:var(--slate);text-decoration:none;background:var(--card);font-variant-numeric:tabular-nums}
  .stage-strip a.settled{background:var(--green-soft);color:var(--green);border-color:#cfe0d6}
  .stage-strip a.predicted{background:var(--yellow-soft);color:#7a6410;border-color:#eedf9e}
  .stage-strip a.cancelled,.stage-strip span.cancelled{text-decoration:line-through;background:#ece9e4;color:#6b6259}
  .stage-strip span.settled{background:var(--green-soft);color:var(--green);border-color:#cfe0d6;opacity:.55}
  .stage-strip span.predicted{background:var(--yellow-soft);color:#7a6410;border-color:#eedf9e;opacity:.55}
  .stage-strip a:hover{border-color:var(--blue)}
  .progress{height:9px;background:var(--card);border:1px solid var(--line);
            border-radius:5px;overflow:hidden;margin:10px 0 4px}
  .progress i{display:block;height:100%;background:var(--green)}
  .filters{font-family:var(--sans);font-size:13px;display:flex;flex-wrap:wrap;gap:8px;
           align-items:center;margin:6px 0 18px}
  .filters .lbl{color:var(--slate);font-size:11.5px;font-weight:600;
    letter-spacing:.08em;text-transform:uppercase;margin-right:2px}
  .filters button{font-family:var(--sans);font-size:12.5px;font-weight:600;cursor:pointer;
    padding:4px 12px;border-radius:99px;border:1px solid var(--line);
    background:var(--card);color:var(--slate)}
  .filters button.on{background:var(--ink);color:var(--paper);border-color:var(--ink)}
  .cal{display:grid;grid-template-columns:repeat(7,1fr);gap:6px;font-family:var(--sans)}
  .cal .dow{font-size:11px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;
            color:var(--slate);text-align:center;padding:4px 0}
  .cal .day{background:var(--card);border:1px solid var(--line);border-radius:6px;
            min-height:74px;padding:6px 7px;font-size:12px}
  .cal .day.blank{background:transparent;border-color:transparent}
  .cal .day.today{border-color:var(--yellow);box-shadow:0 0 0 1px var(--yellow)}
  .cal .num{color:var(--slate);font-variant-numeric:tabular-nums;font-weight:600;font-size:11.5px}
  .cal .ev{display:block;margin-top:5px;padding:2px 6px;border-radius:4px;font-weight:600;
           font-size:11.5px;line-height:1.35;text-decoration:none;color:var(--slate);
           border:1px solid var(--line);background:var(--paper)}
  .cal .ev.settled{background:var(--green-soft);color:var(--green);border-color:#cfe0d6}
  .cal .ev.predicted{background:var(--yellow-soft);color:#7a6410;border-color:#eedf9e}
  .cal .ev.cancelled{background:#ece9e4;color:#6b6259;text-decoration:line-through}
  .cal .ev[href]:hover{border-color:var(--blue)}
  .cal-nav{font-family:var(--sans);font-size:13.5px;display:flex;gap:18px;margin:0 0 16px}
  .cal-nav a{text-decoration:none;border-bottom:1px solid var(--blue-soft);font-weight:600}
  .cal-nav .now{color:var(--slate)}
  @media (max-width:640px){
    .cal{gap:3px}.cal .day{min-height:52px;padding:4px 5px}
    .entry .race{width:auto}
  }
  .footer{margin-top:80px;padding-top:16px;border-top:1px solid var(--line);
          font-family:var(--sans);font-size:12.5px;color:var(--slate)}
"""

CHIP_TEXT = {"settled": "settled", "predicted": "predicted",
             "upcoming": "upcoming", "cancelled": "cancelled",
             "in_progress": "in progress", "archive": "archive"}

STATUS_BLURB = {"settled": "Predictions published, results in, scored.",
                "predicted": "Prediction published; awaiting the result.",
                "upcoming": "On the calendar; nothing published yet."}


def esc(s):
    return html.escape(str(s)) if s is not None else ""


def chip(status, extra=""):
    return (f'<span class="chip {esc(status)}">'
            f'{esc(CHIP_TEXT.get(status, status))}{extra}</span>')


def fmt_date(iso, with_year=False):
    if not iso:
        return "—"
    d = date.fromisoformat(iso)
    return d.strftime("%-d %b %Y" if with_year else "%a %-d %b")


def fmt_month(ym):
    return date(int(ym[:4]), int(ym[5:7]), 1).strftime("%B %Y")


def day_key_text(dk):
    if not dk:
        return ""
    parts = sorted(dk.items(), key=lambda kv: -kv[1])
    return " · ".join(f"{k} {v:.2f}".rstrip("0").rstrip(".") for k, v in parts)


def short_label(stage):
    """'Stage 7 — Vall d'Alba → …' -> the part after the em-dash."""
    label = stage["label"]
    for sep in (" — ", " – ", " - "):
        if sep in label:
            return label.split(sep, 1)[1]
    return "" if label == f"Stage {stage['stage']}" else label


def page(title, body, active, description=""):
    nav_links = [("/", "Home"), ("/races", "Races"),
                 ("/calendar", "Calendar"), ("/model", "How the model works")]
    nav = "".join(
        f'<a href="{href}"{" class=\"here\"" if href == active else ""}>'
        f'{esc(text)}</a>'
        for href, text in nav_links if href != "/")
    desc = (f'<meta name="description" content="{esc(description)}">\n'
            if description else "")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
{desc}{FAVICON}
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<nav class="topnav"><a class="brand" href="/">Cycling Race Predictor</a>{nav}</nav>
{body}
<div class="footer">Frame generated from <span class="mono">site-index.json</span>
 by <span class="mono">build_site_frame.py</span>.
 Market probabilities appear on these pages as a benchmark — a measure of how
 much real information the model captures — not as betting guidance.</div>
</div>
</body>
</html>
"""


# ---------------------------------------------------------------- entries

def dated_stage_rows(races):
    rows = []
    for race in races:
        for s in race.get("stages", []):
            if s.get("date"):
                rows.append((s["date"], race, s))
    rows.sort(key=lambda r: (r[0], r[1]["slug"], r[2]["stage"]))
    return rows


def entry_line(race, s, show_year=False):
    text = f"Stage {s['stage']}"
    sub = short_label(s)
    if sub:
        text += f" · {sub}"
    body = (f'<a href="{s["url"]}">{esc(text)}</a>' if s["url"]
            else f'<span>{esc(text)}</span>')
    return (f'<div class="entry"><span class="d">{fmt_date(s["date"], show_year)}</span>'
            f'<span class="race">{esc(race["short_name"])}</span>'
            f'{body}{chip(s["status"])}</div>')


# ------------------------------------------------------------------ home

def render_home(idx, today):
    races = [r for r in idx["races"] if r["status"] != "archive"]
    live = [r for r in races if r["status"] == "in_progress"]
    rows = dated_stage_rows(races)

    recent = [(d, r, s) for d, r, s in rows if s["url"] and d <= today.isoformat()][-6:]
    upcoming = [(d, r, s) for d, r, s in rows if d > today.isoformat()][:6]

    live_html = ""
    for race in live:
        pcs = []
        for key in ("gc", "stages"):
            if key in race["pages"]:
                p = race["pages"][key]
                pcs.append(f'<a href="{p["url"]}">{esc(p["title"])} →</a>')
        nxt = next((s for s in race["stages"]
                    if s["status"] in ("predicted", "upcoming")
                    and (s["date"] or "9999") >= today.isoformat()), None)
        nxt_html = ""
        if nxt:
            what = f"Stage {nxt['stage']}"
            if short_label(nxt):
                what += f" — {esc(short_label(nxt))}"
            when = fmt_date(nxt["date"]) if nxt["date"] else "date TBC"
            link = (f' · <a href="{nxt["url"]}">prediction →</a>'
                    if nxt["url"] else "")
            nxt_html = (f'<p class="note" style="margin-top:10px">Next up: '
                        f'<b>{what}</b> ({when}){link}</p>')
        done = race["n_settled"]
        pct_done = round(100 * done / race["n_stages"])
        live_html += f"""
<section>
<p class="kicker">Live now</p>
<h2><a href="{race['url']}" style="color:inherit;text-decoration:none">{esc(race['name'])}</a> {chip('in_progress')}</h2>
<p>{esc(race['blurb'])}</p>
<div class="progress" title="{done} of {race['n_stages']} stages settled"><i style="width:{pct_done}%"></i></div>
<p class="note muted" style="font-family:var(--sans);font-size:13px">{done} of {race['n_stages']} stages settled ·
 {fmt_date(race['start_date'], True)} – {fmt_date(race['end_date'], True)}</p>
{nxt_html}
<p class="go" style="font-family:var(--sans);font-size:13.5px;margin-top:14px">
<a href="{race['url']}"><b>Race hub →</b></a>&nbsp;&nbsp; {'&nbsp;&nbsp; '.join(pcs)}</p>
</section>"""

    recent_html = "".join(entry_line(r, s) for _, r, s in reversed(recent))
    upcoming_html = ("".join(entry_line(r, s) for _, r, s in upcoming)
                     or '<div class="entry"><span class="muted">Nothing scheduled yet — '
                        'stage configs are cut the evening before each stage.</span></div>')

    retro_cards = ""
    for race in races:
        if "review" in race["pages"]:
            p = race["pages"]["review"]
            retro_cards += f"""
<div class="card"><h3><a href="{p['url']}">{esc(race['name'])}: {esc(p['title'].lower())}</a></h3>
<p class="note">How the three-week campaign scored — stage by stage, against results and against
the market benchmark.</p>
<p class="go"><a href="{p['url']}">Read the review →</a></p></div>"""
    for race in races:
        if race["status"] == "settled":
            retro_cards += f"""
<div class="card"><h3><a href="{race['url']}">{esc(race['name'])} archive</a></h3>
<p class="note">{race['n_settled']} settled stages with predictions frozen before each start,
plus the GC tracker as it evolved.</p>
<p class="go"><a href="{race['url']}">Open the race hub →</a></p></div>"""
    retro_cards += """
<div class="card"><h3><a href="/model">How the model works</a></h3>
<p class="note">The full write-up: seven pricing heads, one pricing layer, the day-type retrieval
channel, and how the outputs are compared with the market.</p>
<p class="go"><a href="/model">Read the article →</a></p></div>"""

    n_pages = sum(1 for r in races for s in r["stages"] if s["url"])
    n_settled = sum(r["n_settled"] for r in races)
    body = f"""
<header>
<div class="eyebrow">Prospective predictions · scored in the open</div>
<h1>Machine predictions for professional road cycling</h1>
<p class="standfirst">Every prediction here was published before the race and settled against the
result afterwards. Where market probabilities appear, they are the benchmark we score ourselves
against — a measure of how much real information the model captures.</p>
<div class="meta">
<span>Races covered <b>{len(races)}</b></span>
<span>Stage predictions <b>{n_pages}</b></span>
<span>Stages settled <b>{n_settled}</b></span>
<span>Updated <b>{esc(idx['generated_at'][:10])}</b></span>
</div>
</header>
{live_html}
<section>
<p class="kicker">Recent predictions</p>
<h2>The latest pages</h2>
<div class="listbox">{recent_html}</div>
<p class="note" style="font-family:var(--sans);font-size:13px">
<a href="/races">All races →</a> &nbsp;·&nbsp; <a href="/calendar">Calendar view →</a></p>
</section>
<section>
<p class="kicker">Coming up</p>
<h2>Next on the calendar</h2>
<div class="listbox">{upcoming_html}</div>
</section>
<section>
<p class="kicker">Retrospectives</p>
<h2>Looking back</h2>
<div class="cards">{retro_cards}</div>
</section>"""
    return page("Cycling Race Predictor", body, "/",
                "Prospective machine predictions for professional road cycling, "
                "settled against results and benchmarked against the market.")


# ----------------------------------------------------------------- races

def render_races(idx):
    races = [r for r in idx["races"] if r["status"] != "archive"]
    archives = [r for r in idx["races"] if r["status"] == "archive"]

    cards = ""
    for race in races:
        links = [f'<a href="{race["url"]}"><b>Race hub →</b></a>']
        for p in race["pages"].values():
            links.append(f'<a href="{p["url"]}">{esc(p["title"])} →</a>')
        when = (f"{fmt_date(race['start_date'], True)} – "
                f"{fmt_date(race['end_date'], True)}")
        cards += f"""
<div class="card race-card" data-status="{race['status']}" data-type="{race['type']}">
<h3><a href="{race['url']}">{esc(race['name'])}</a> {chip(race['status'])}</h3>
<p class="note muted">{'Stage race' if race['type'] == 'stage_race' else 'One-day race'} ·
 {when} · {race['n_settled']}/{race['n_stages']} stages settled</p>
<p class="note">{esc(race['blurb'])}</p>
<p class="go">{'&nbsp;&nbsp; '.join(links)}</p>
</div>"""

    arch_rows = ""
    for a in archives:
        circa = fmt_month(a["circa"]) if a.get("circa") else "2026"
        arch_rows += (
            f'<tr data-status="archive" data-type="{a["type"]}">'
            f'<td>{esc(a["name"])}</td>'
            f'<td class="muted">{"Stage race" if a["type"] == "stage_race" else "One-day race"}</td>'
            f'<td class="muted">{esc(circa)}</td>'
            f'<td class="muted mono" style="font-size:11.5px">{esc(a["campaign_dir"])}</td></tr>')

    body = f"""
<header>
<div class="eyebrow">The archive</div>
<h1>Races</h1>
<p class="standfirst">Every campaign the model has run — published prediction pages first,
earlier evaluation-only campaigns below.</p>
</header>
<section>
<div class="filters">
<span class="lbl">Status</span>
<button class="on" data-filter="status" data-value="all">All</button>
<button data-filter="status" data-value="in_progress">In progress</button>
<button data-filter="status" data-value="settled">Settled</button>
<button data-filter="status" data-value="upcoming">Upcoming</button>
<span class="lbl" style="margin-left:14px">Type</span>
<button class="on" data-filter="type" data-value="all">All</button>
<button data-filter="type" data-value="stage_race">Stage races</button>
<button data-filter="type" data-value="one_day">One-day</button>
</div>
<div class="cards" id="race-cards">{cards}</div>
<p class="note muted" id="no-match" style="display:none;font-family:var(--sans)">
No published race matches those filters — the earlier campaigns below may.</p>
</section>
<section>
<p class="kicker">Earlier campaigns</p>
<h2>Evaluation archive, spring 2026</h2>
<p>Before the site existed, the model ran these races as pure evaluation campaigns:
predictions were frozen and compared with the market benchmark, but no pages were published.
The raw comparisons live in the repository.</p>
<div class="tablewrap"><table id="arch-table">
<thead><tr><th>Race</th><th>Type</th><th>Circa</th><th>Data</th></tr></thead>
<tbody>{arch_rows}</tbody>
</table></div>
</section>
<script>
(function () {{
  var active = {{ status: "all", type: "all" }};
  document.querySelectorAll(".filters button").forEach(function (btn) {{
    btn.addEventListener("click", function () {{
      var f = btn.dataset.filter;
      active[f] = btn.dataset.value;
      document.querySelectorAll('.filters button[data-filter="' + f + '"]')
        .forEach(function (b) {{ b.classList.toggle("on", b === btn); }});
      var shown = 0;
      document.querySelectorAll("#race-cards .race-card, #arch-table tbody tr")
        .forEach(function (el) {{
          var ok = (active.status === "all" || el.dataset.status === active.status) &&
                   (active.type === "all" || el.dataset.type === active.type);
          el.style.display = ok ? "" : "none";
          if (ok && el.classList.contains("race-card")) shown++;
        }});
      document.getElementById("no-match").style.display = shown ? "none" : "";
    }});
  }});
}})();
</script>"""
    return page("Races · Cycling Race Predictor", body, "/races",
                "All campaigns: published prediction pages and earlier "
                "evaluation-only archives.")


# -------------------------------------------------------------- calendar

def render_calendar_month(idx, ym, today):
    year, month = int(ym[:4]), int(ym[5:7])
    races = [r for r in idx["races"] if r["status"] != "archive"]
    by_day = {}
    for d, race, s in dated_stage_rows(races):
        if d[:7] == ym:
            by_day.setdefault(int(d[8:10]), []).append((race, s))

    months = idx["months"]
    i = months.index(ym)
    nav = []
    if i > 0:
        prev = months[i - 1]
        nav.append(f'<a href="/calendar/{prev.replace("-", "/")}">'
                   f'← {esc(fmt_month(prev))}</a>')
    nav.append(f'<span class="now">{esc(fmt_month(ym))}</span>')
    if i < len(months) - 1:
        nxt = months[i + 1]
        nav.append(f'<a href="/calendar/{nxt.replace("-", "/")}">'
                   f'{esc(fmt_month(nxt))} →</a>')

    dows = "".join(f'<div class="dow">{d}</div>'
                   for d in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"))
    cells = ""
    for week in calendar.Calendar().monthdayscalendar(year, month):
        for day in week:
            if day == 0:
                cells += '<div class="day blank"></div>'
                continue
            iso = f"{ym}-{day:02d}"
            today_cls = " today" if iso == today.isoformat() else ""
            evs = ""
            for race, s in by_day.get(day, []):
                text = f"{esc(race['short_name'])} · st {s['stage']}"
                cls = f"ev {s['status']}"
                if s["url"]:
                    evs += (f'<a class="{cls}" href="{s["url"]}" '
                            f'title="{esc(s["label"])}">{text}</a>')
                else:
                    evs += (f'<span class="{cls}" '
                            f'title="{esc(s["label"])}">{text}</span>')
            cells += (f'<div class="day{today_cls}">'
                      f'<span class="num">{day}</span>{evs}</div>')

    notes = ""
    for race in races:
        undated = [s for s in race["stages"] if not s.get("date")]
        if undated and race["end_date"][:7] >= ym >= race["start_date"][:7]:
            lo, hi = undated[0]["stage"], undated[-1]["stage"]
            notes += (f'<p class="note muted" style="font-family:var(--sans);font-size:13px">'
                      f'{esc(race["short_name"])} stages {lo}–{hi} run through '
                      f'{fmt_date(race["end_date"], True)}; they appear here as each '
                      f'stage config is cut the evening before.</p>')

    body = f"""
<header>
<div class="eyebrow">Calendar</div>
<h1>{esc(fmt_month(ym))}</h1>
<p class="standfirst">Stage-by-stage coverage this month. Green stages are settled,
yellow are predicted and awaiting a result, struck-through were cancelled.</p>
</header>
<section>
<div class="cal-nav">{' '.join(nav)}</div>
<div class="cal">{dows}{cells}</div>
{notes}
</section>"""
    return page(f"{fmt_month(ym)} · Cycling Race Predictor", body, "/calendar",
                f"Race calendar for {fmt_month(ym)}: prediction and results "
                "status for every covered stage.")


# -------------------------------------------------------------- race hub

def render_race_hub(idx, race):
    links = []
    for p in race["pages"].values():
        links.append((p["url"], p["title"]))

    strip = ""
    for s in race["stages"]:
        cls = s["status"] if s["status"] != "upcoming" else ""
        title = esc(s["label"]) + (f' · {fmt_date(s["date"])}' if s["date"] else "")
        if s["url"]:
            strip += f'<a class="{cls}" href="{s["url"]}" title="{title}">{s["stage"]}</a>'
        else:
            strip += f'<span class="{cls}" title="{title}">{s["stage"]}</span>'
    if "gc" in race["pages"]:
        strip += (f'<a class="settled" href="{race["pages"]["gc"]["url"]}" '
                  f'title="General classification tracker" '
                  f'style="width:auto;padding:5px 12px">GC</a>')

    cards = ""
    card_copy = {
        "gc": "Where the general classification stands, how the model's GC heads "
              "read it, and how that compares with the market's view.",
        "stages": "The full diary: every stage card with its scenarios, prediction "
                  "boards, and morning-after reflections in one place.",
        "review": "The post-race accounting: what the model got right, what it "
                  "missed, and what the campaign taught us.",
    }
    for key, p in race["pages"].items():
        cards += f"""
<div class="card"><h3><a href="{p['url']}">{esc(p['title'])}</a></h3>
<p class="note">{esc(card_copy.get(key, ''))}</p>
<p class="go"><a href="{p['url']}">Open →</a></p></div>"""
    cards += """
<div class="card"><h3><a href="/model">How the model works</a></h3>
<p class="note">The architecture behind these pages: pricing heads, the pricing layer,
and the day-type retrieval channel.</p>
<p class="go"><a href="/model">Read the article →</a></p></div>"""

    rows = ""
    for s in race["stages"]:
        what = esc(short_label(s)) or '<span class="muted">—</span>'
        link = (f'<a href="{s["url"]}">prediction</a>' if s["url"]
                else ('<span class="muted">settled, not predicted</span>'
                      if s["status"] == "settled" and not s["predicted"]
                      else '<span class="muted">—</span>'))
        dk = day_key_text(s.get("day_key"))
        rows += (f'<tr><td>{s["stage"]}</td>'
                 f'<td>{fmt_date(s["date"]) if s["date"] else "<span class=muted>TBC</span>"}</td>'
                 f'<td>{what}</td>'
                 f'<td class="mono" style="font-size:11.5px">{esc(dk) or "—"}</td>'
                 f'<td>{chip(s["status"])}</td>'
                 f'<td>{link}</td></tr>')

    status_line = {"in_progress": "In progress", "settled": "Complete",
                   "upcoming": "Upcoming"}[race["status"]]
    body = f"""
<header>
<div class="eyebrow">{'Stage race' if race['type'] == 'stage_race' else 'One-day race'} · {race['year']}</div>
<h1>{esc(race['name'])} {chip(race['status'])}</h1>
<p class="standfirst">{esc(race['blurb'])}</p>
<div class="meta">
<span>Dates <b>{fmt_date(race['start_date'], True)} – {fmt_date(race['end_date'], True)}</b></span>
<span>Status <b>{status_line}</b></span>
<span>Settled <b>{race['n_settled']}/{race['n_stages']}</b></span>
<span>Predicted <b>{race['n_predicted']}</b></span>
</div>
</header>
<section>
<p class="kicker">Stages</p>
<h2>Jump to a stage</h2>
<div class="stage-strip">{strip}</div>
<p class="note muted" style="font-family:var(--sans);font-size:12.5px">
Green settled · yellow predicted · struck-through cancelled · plain upcoming.</p>
</section>
<section>
<p class="kicker">Race views</p>
<h2>The full picture</h2>
<div class="cards">{cards}</div>
</section>
<section>
<p class="kicker">Stage log</p>
<h2>Every stage, in order</h2>
<div class="tablewrap"><table>
<thead><tr><th>St</th><th>Date</th><th>Route</th><th>Day key</th><th>Status</th><th>Page</th></tr></thead>
<tbody>{rows}</tbody>
</table></div>
<p class="note muted" style="font-family:var(--sans);font-size:13px">
The day key is the morning read of how the stage would unfold — the retrieval channel's
menu item and weight, frozen before the start.</p>
</section>"""
    return page(f"{race['name']} · Cycling Race Predictor", body, "/races",
                f"{race['name']}: stage predictions, GC tracker, and "
                "retrospectives.")


# ------------------------------------------------------------------ main

def main():
    idx = json.loads(INDEX_PATH.read_text())
    today = date.today()

    (FRAME_DIR / "race").mkdir(parents=True, exist_ok=True)
    (FRAME_DIR / "calendar").mkdir(parents=True, exist_ok=True)

    written = []

    def write(rel, content):
        (FRAME_DIR / rel).write_text(content)
        written.append(rel)

    write("home.html", render_home(idx, today))
    write("races.html", render_races(idx))
    for ym in idx["months"]:
        write(f"calendar/{ym}.html", render_calendar_month(idx, ym, today))
    for race in idx["races"]:
        if race["status"] != "archive":
            write(f"race/{race['slug']}-{race['year']}.html",
                  render_race_hub(idx, race))

    print(f"wrote {len(written)} frame pages under "
          f"{FRAME_DIR.relative_to(SITE_DIR.parent)}: {', '.join(written)}")


if __name__ == "__main__":
    main()
