"""
The race-diary links block in predictor-architecture.html (served at /model).

Until 2026-10 every campaign build appended its own "<b>Race diary:</b> …
Stage 1 · Stage 2 …" strip between per-campaign markers, so the explainer grew
one unlabeled row of links per automated race. This module owns the one block
that replaces them: a card per hand-covered Grand Tour (review, GC tracker,
stage overview, a 1–21 stage grid) and a single line pointing everything else
at the race archive (/races).

build_stage_page.py calls inject() after every stage build, whichever campaign
is running, so the block is always re-rendered from the whole site. Run this
file directly to refresh the block (and index.html) without building a stage:

    python3 netlify_site/build/campaign_links.py
"""

import html
import json
import re
import runpy
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITE_DIR = HERE.parent
PROJECT_ROOT = SITE_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from cycling_project.nightly import site_paths  # noqa: E402

SOURCE_HTML = HERE / "predictor-architecture.html"
MARKER = "CAMPAIGN-LINKS"
ANCHOR = "<!-- ================= HEADS VIEW ================= -->"

# The two races covered by hand, in display order. `prefix` is the published
# filename prefix (TdF pages predate prefixes); `slug` keys site-index.json.
GRAND_TOURS = [
    {"slug": "tour-de-france", "year": 2026, "prefix": "", "n_stages": 21,
     "name": "Tour de France 2026",
     "summary": "Every stage predicted the evening before and settled the evening "
                "after: the model's first full Grand Tour in public, measured "
                "against the market throughout."},
    {"slug": "vuelta-a-espana", "year": 2026, "prefix": "vuelta-", "n_stages": 21,
     "name": "Vuelta a España 2026",
     "summary": "Day-type keys chosen each morning, stage predictions published "
                "before the start, and a GC tracker that followed the race as it "
                "reshaped itself."},
]

CSS = """<style>
.gt-diaries{max-width:1020px;margin:28px auto 0;font-family:var(--sans)}
.gt-diaries .gtd-kicker{font-size:12px;font-weight:700;letter-spacing:.08em;
  text-transform:uppercase;color:var(--slate);margin:0 0 12px}
.gt-diaries .gtd-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}
.gt-diaries .gtd-card{background:var(--card);border:1px solid var(--line);border-radius:10px;
  padding:18px 20px 16px}
.gt-diaries h3{font-family:var(--serif);font-size:20px;line-height:1.25;margin:0;color:var(--ink)}
.gt-diaries .gtd-dates{font-size:12.5px;color:var(--slate);margin:2px 0 8px}
.gt-diaries .gtd-summary{font-family:var(--serif);font-size:15px;line-height:1.5;
  color:var(--ink);margin:0 0 12px}
.gt-diaries .gtd-links{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 14px}
.gt-diaries .gtd-links a{font-size:13px;font-weight:600;text-decoration:none;color:var(--blue);
  border:1px solid var(--line);border-radius:999px;padding:5px 12px;background:var(--paper)}
.gt-diaries .gtd-links a.gtd-primary{background:var(--blue-soft);border-color:var(--blue-soft)}
.gt-diaries .gtd-links a:hover,.gt-diaries .gtd-stages a:hover{border-color:var(--blue)}
.gt-diaries .gtd-stages-label{font-size:11.5px;color:var(--slate);margin:0 0 6px}
.gt-diaries .gtd-stages{display:grid;grid-template-columns:repeat(auto-fill,minmax(30px,1fr));gap:5px}
.gt-diaries .gtd-stages a,.gt-diaries .gtd-stages span{display:block;text-align:center;
  font-size:12px;font-weight:600;line-height:28px;border-radius:6px;border:1px solid var(--line);
  text-decoration:none;font-variant-numeric:tabular-nums}
.gt-diaries .gtd-stages a{color:var(--blue);background:var(--paper)}
.gt-diaries .gtd-stages span{color:var(--slate);opacity:.6}
.gt-diaries .gtd-stages span.cancelled{text-decoration:line-through;opacity:.75;background:var(--line)}
.gt-diaries .gtd-more{font-size:13.5px;color:var(--slate);margin:14px 0 0;line-height:1.55}
.gt-diaries .gtd-more a{color:var(--blue);font-weight:600;text-decoration:none;
  border-bottom:1px solid var(--blue-soft)}
@media (max-width:560px){.gt-diaries .gtd-card{padding:16px}}
</style>"""


def esc(s):
    return html.escape(str(s))


def load_site_index(site_dir=SITE_DIR):
    try:
        return json.loads((site_dir / site_paths.SITE_INDEX_NAME).read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def date_span(start, end):
    """'4–26 July' / '22 August – 13 September'; '' when dates are missing."""
    try:
        a, b = date.fromisoformat(start), date.fromisoformat(end)
    except (TypeError, ValueError):
        return ""
    if a.month == b.month:
        return f"{a.day}–{b.day} {b:%B}"
    return f"{a.day} {a:%B} – {b.day} {b:%B}"


def tour_card(tour, race, site_dir=SITE_DIR):
    """One Grand Tour card. Clean routes come from site-index.json; a missing
    entry falls back to the flat .html names (which the Worker also serves)."""
    pfx = tour["prefix"]
    pages = race.get("pages") or {}
    stages = {s.get("stage"): s for s in race.get("stages") or []}

    def page_url(key, fallback):
        return (pages.get(key) or {}).get("url") or fallback

    links = [
        ("review", f"{pfx}review.html", "Post-race review →", "gtd-primary"),
        ("gc", site_paths.gc_tracker_name(pfx), "GC tracker", ""),
        ("stages", site_paths.stages_index_name(pfx), "All stages", ""),
    ]
    link_html = ""
    for key, fallback, label, cls in links:
        if key in pages or (site_dir / fallback).exists():
            cls_attr = f' class="{cls}"' if cls else ""
            link_html += f'<a href="{esc(page_url(key, fallback))}"{cls_attr}>{esc(label)}</a>'

    chips, cancelled = [], []
    for n in range(1, tour["n_stages"] + 1):
        info = stages.get(n) or {}
        page = site_paths.stage_page_name(pfx, n)
        if info.get("status") == "cancelled":
            cancelled.append(n)
            chips.append(f'<span class="cancelled" title="Stage {n} was cancelled">{n}</span>')
        elif (site_dir / page).exists():
            url = info.get("url") or page
            chips.append(f'<a href="{esc(url)}" title="Stage {n}">{n}</a>')
        else:
            chips.append(f'<span title="No page for stage {n}">{n}</span>')

    span = date_span(race.get("start_date"), race.get("end_date"))
    meta = " · ".join(x for x in (span, f"{tour['n_stages']} stages") if x)
    label = "Stage pages"
    if cancelled:
        nums = ", ".join(str(n) for n in cancelled)
        label += f" · stage{'s' if len(cancelled) > 1 else ''} {nums} cancelled"
    return (
        '<article class="gtd-card">'
        f'<h3>{esc(tour["name"])}</h3>'
        f'<p class="gtd-dates">{esc(meta)}</p>'
        f'<p class="gtd-summary">{esc(tour["summary"])}</p>'
        f'<div class="gtd-links">{link_html}</div>'
        f'<p class="gtd-stages-label">{label}</p>'
        f'<div class="gtd-stages">{"".join(chips)}</div>'
        "</article>")


def render(site_dir=SITE_DIR):
    index = load_site_index(site_dir)
    races = index.get("races") or []
    by_key = {(r.get("slug"), r.get("year")): r for r in races}
    hand = {(t["slug"], t["year"]) for t in GRAND_TOURS}
    cards = "\n".join(tour_card(t, by_key.get((t["slug"], t["year"]), {}), site_dir)
                      for t in GRAND_TOURS)
    n_other = sum(1 for r in races if (r.get("slug"), r.get("year")) not in hand)
    count = f" ({n_other} races so far)" if n_other else ""
    more = ("Since the Vuelta the nightly pipeline runs on its own: one-day races and "
            f"stage races, each with its prediction and result pages{count}. "
            '<a href="/races">Browse them in the race archive →</a>')
    return (f"{CSS}\n"
            '<div class="gt-diaries" aria-labelledby="gtd-title">\n'
            '<p class="gtd-kicker" id="gtd-title">The two Grand Tours we covered by hand</p>\n'
            f'<div class="gtd-grid">\n{cards}\n</div>\n'
            f'<p class="gtd-more">{more}</p>\n'
            "</div>")


_BLOCK = re.compile(r"<!-- ([A-Z0-9-]+):START -->.*?<!-- \1:END -->\n*", re.S)


def replace_block(src, body):
    """Put the CAMPAIGN-LINKS block in `src`, dropping every legacy per-campaign
    stage-strip block. The new block takes the place of the first one removed
    (or of its own previous copy); with neither, it goes before the heads view."""
    block = f"<!-- {MARKER}:START -->\n{body}\n<!-- {MARKER}:END -->\n\n"
    placeholder = "\x00CAMPAIGN-LINKS\x00"
    placed = False

    def swap(m):
        nonlocal placed
        if m.group(1) != MARKER and 'class="stage-strip"' not in m.group(0):
            return m.group(0)
        if placed:
            return ""
        placed = True
        return placeholder

    src = _BLOCK.sub(swap, src)
    if placed:
        return src.replace(placeholder, block)
    return src.replace(ANCHOR, block + ANCHOR)


def inject(source=SOURCE_HTML, site_dir=SITE_DIR):
    source.write_text(replace_block(source.read_text(), render(site_dir)))


if __name__ == "__main__":
    inject()
    print(f"Refreshed race-diary links in {SOURCE_HTML.name}")
    runpy.run_path(str(HERE / "make_netlify.py"))
