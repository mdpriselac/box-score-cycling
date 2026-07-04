"""Build the model-vs-books view from tdf_book_comparison.json and splice it
into predictor-architecture.html between <!-- BOOKS:BEGIN --> / <!-- BOOKS:END -->."""

import json
import re
from html import escape
from pathlib import Path

HERE = Path(__file__).parent
C = json.loads((HERE / "tdf_book_comparison.json").read_text())
PAGE = HERE / "predictor-architecture.html"

def pct(v, dec=1):
    return "–" if v is None else f"{100*float(v):.{dec}f}"

def edge_cell(v):
    if v is None:
        return '<td class="num">–</td>'
    cls = "edge-pos" if v >= 0.005 else ("edge-neg" if v <= -0.005 else "")
    return f'<td class="num {cls}">{100*v:+.1f}</td>'

def gc_table(rows, n=16):
    body = []
    for r in rows[:n]:
        body.append(
            "<tr>"
            f'<td class="nm">{escape(r["rider"])}<span class="tm">{escape(r.get("team") or "")}</span></td>'
            f'<td class="num">{r["book_odds"]:g}</td>'
            f'<td class="num hl">{pct(r["book_devig"])}</td>'
            f'<td class="num">{pct(r["blend"])}</td>'
            f'<td class="num">{pct(r["cascade"])}</td>'
            f'<td class="num">{pct(r["lr"])}</td>'
            + edge_cell(r["edge_lr"]) +
            "</tr>"
        )
    return f"""<div class="table-frame tdf-tf"><table class="tdf-table">
<thead><tr><th>Rider</th><th class="num">Book odds</th>
<th class="num" title="Implied probability with the 22% overround removed">Book&nbsp;%&nbsp;(devig)</th>
<th class="num">Blend&nbsp;%</th><th class="num">Cascade&nbsp;%</th><th class="num">LR&nbsp;%</th>
<th class="num" title="LambdaRank minus devigged book — positive means our calibrated head prices the rider above the market">LR&nbsp;−&nbsp;book&nbsp;(pp)</th></tr></thead>
<tbody>{''.join(body)}</tbody></table></div>"""

def wo_pog_table(rows):
    body = []
    for r in rows[:8]:
        d = None
        if r.get("ours_renorm") is not None:
            d = r["ours_renorm"] - r["book_devig"]
        body.append(
            "<tr>"
            f'<td class="nm">{escape(r["rider"])}</td>'
            f'<td class="num">{r["book_odds"]:g}</td>'
            f'<td class="num hl">{pct(r["book_devig"])}</td>'
            f'<td class="num">{pct(r.get("ours_renorm"))}</td>'
            + edge_cell(d) + "</tr>"
        )
    return f"""<div class="table-frame tdf-tf"><table class="tdf-table">
<thead><tr><th>Rider</th><th class="num">Book odds</th><th class="num">Book&nbsp;%&nbsp;(devig)</th>
<th class="num" title="Our blend win probabilities with Pogacar removed and the rest renormalized">Ours,&nbsp;renormed&nbsp;%</th>
<th class="num">Δ&nbsp;(pp)</th></tr></thead><tbody>{''.join(body)}</tbody></table></div>"""

def mini_board(title, rows, n=5, name_key="name"):
    body = "".join(
        f'<tr><td class="nm">{escape(r[name_key])}</td>'
        f'<td class="num">{r["odds"]:g}</td>'
        f'<td class="num">{pct(r.get("devig", r.get("implied")))}</td></tr>'
        for r in rows[:n])
    return f"""<div class="miniboard"><p class="tdf-side-h">{title}</p>
<table class="tdf-table"><thead><tr><th>Outcome</th><th class="num">Odds</th><th class="num">%</th></tr></thead>
<tbody>{body}</tbody></table></div>"""

def hunters_table(rows, n=14):
    body = []
    for r in rows[:n]:
        body.append(
            "<tr>"
            f'<td class="nm">{escape(r["rider"])}</td>'
            f'<td class="num">{r["book_odds"]:g}</td>'
            f'<td class="num hl">{pct(r["book_implied"])}</td>'
            f'<td class="num">{pct(r.get("best_day_blend"))}</td>'
            f'<td class="sc">{escape((r.get("best_day_scenario") or "–").replace(" — ", ", "))}</td>'
            "</tr>"
        )
    return f"""<div class="table-frame tdf-tf"><table class="tdf-table">
<thead><tr><th>Rider</th><th class="num">Book "yes"</th>
<th class="num" title="Raw implied probability — one-sided market, no clean devig">Implied&nbsp;%</th>
<th class="num" title="Our highest single-day blend win probability across the six archetypes">Our&nbsp;best&nbsp;day&nbsp;%</th>
<th>Best archetype</th></tr></thead><tbody>{''.join(body)}</tbody></table></div>"""

ov = C["provenance"]["overrounds"]

html = f"""
<section class="col">
  <p class="kicker">Model vs market</p>
  <h2>Our numbers against the book</h2>
  <p>Odds captured <strong>3 July 2026</strong> (the day before the Grand Départ) from the Kambi feed that powers Unibet — the same numbers shown on the consumer site, taken in one API snapshot and archived. Bookmaker odds carry a margin (this win market sums to {100*(ov['gc_win']-1):.0f}% over a fair book), so every "Book %" below is <em>devigged</em>: rescaled so the market's probabilities sum to what a fair book would.</p>
  <p class="note"><b>Which of our heads to compare:</b> the LambdaRank column is our calibrated book — that's the honest apples-to-apples line. The cascade is our winner-picker, sharp at the top but not book-normalized. One known artifact matters here: LambdaRank's per-race softmax refuses extreme favorites, so its Pogačar number is a floor, not an opinion — at the very top of the market, the cascade is our real quote.</p>
</section>

<section class="col tdf-scenario">
  <h3 class="tdf-h">General classification — the main market</h3>
  <p class="tdf-blurb">40 riders priced by the book, all matched to our board. Sorted by book odds.</p>
  <div class="wide">{gc_table(C["gc"])}</div>
</section>

<section class="col tdf-scenario">
  <h3 class="tdf-h">Three stories in this table</h3>
  <div class="wide cards">
    <div class="card">
      <h4>Where we agree</h4>
      <p class="q">The two systems shake hands at the very top.</p>
      <p>Book devig on Pogačar: <strong>63.0%</strong>. Our cascade: <strong>62.7%</strong>. Two completely different machines — a global betting market and a LightGBM stack trained on result sheets — land within a point of each other on the biggest question. Seixas is the same story in miniature: the book makes the 19-year-old third favorite (5.5%), and our heads have him 6–10%. Del Toro, Ayuso, Johannessen, Carapaz: all within ~1pp of the book. When we agree this closely, both systems are probably right, and there is no bet.</p>
    </div>
    <div class="card">
      <h4>What the books see that we don't</h4>
      <p class="q">The giant gaps are information, not value.</p>
      <p><strong>Evenepoel: book 2.4%, our blend 22.7%.</strong> <strong>Lipowitz: book 2.0%, blend 16.2%.</strong> And in the "winner without Pogačar" market the book gives Vingegaard <strong>47.9%</strong> of the non-Pogačar race where we give him 19%. Read together, the market is telling one coherent story — it believes only one rider genuinely challenges Pogačar, and that Evenepoel and Lipowitz will not contest GC at full strength. One important self-correction on Vingegaard specifically: a backtest run after this snapshot found the model systematically underprices riders who finished a grand tour within ~45 days (they win GC at ~1.6× our quote) — Vingegaard won the Giro 33 days ago, so much of <em>his</em> gap is our measured bias, not the book's private information. Our database runs to 21 June but contains results, not news: no crash reports, no leadership announcements, no route knowledge — and Evenepoel has not raced since 26 April, a fact our model can only see as stale form while the market knows the reason. A 10× gap on a headline rider means the market knows a fact we don't — the move is to find the fact, not to bet against it.</p>
    </div>
    <div class="card">
      <h4>Where we'd explore for edges</h4>
      <p class="q">Small, calibrated disagreements — not the screaming gaps.</p>
      <p>The credible candidates are where our <em>calibrated</em> head sits modestly above the devigged book with no obvious news story: <strong>Ayuso +2.1pp</strong> and <strong>del Toro +2.0pp</strong> — notably the pair who just finished 3rd and 1st at the Dauphiné, a result the model has digested and this odds snapshot predates — plus Seixas (+0.7pp) and Pidcock fractionally. Structurally, the softer targets are the secondary markets — top-6 and top-10 carry ~{100*(ov['gc_top6']-1):.0f}% margins (vs {100*(ov['gc_win']-1):.0f}% on the win market), and place probabilities are exactly what our DNF-adjusted, calibrated stack does best. That's where a retail book is most likely to be lazy, and where our honest prices have teeth.</p>
    </div>
  </div>
</section>

<section class="col tdf-scenario">
  <h3 class="tdf-h">Winner without Pogačar — the market's second opinion</h3>
  <p class="tdf-blurb">The book's conditional race (margin {100*(ov['gc_win_wo_pogacar']-1):.0f}%, devigged) against our blend with Pogačar removed and renormalized. This is the cleanest view of the disagreement about who the real challenger is.</p>
  <div class="wide">{wo_pog_table(C["gc_wo_pog"])}</div>
</section>

<section class="col tdf-scenario">
  <h3 class="tdf-h">What the book prices that we can't</h3>
  <p class="tdf-blurb">Stage 1 is a <strong>team time trial</strong> — a discipline our rider-level models don't price at all. The book also runs three-week jersey markets that need the full route and points structure. These boards are shown as book-implied probabilities (devigged); we have no counter-quote.</p>
  <div class="wide miniboards">
    {mini_board("Stage 1 TTT — winning team (margin " + f"{100*(ov['stage1_ttt_win']-1):.0f}%" + ")", C["stage1_ttt"])}
    {mini_board("Yellow after stage 1", C["yellow_after_stage1"])}
    {mini_board("Points jersey", C["jerseys"]["points_win"])}
    {mini_board("Mountains jersey", C["jerseys"]["kom_win"])}
    {mini_board("Youth jersey", C["jerseys"]["youth_win"])}
    {mini_board("Teams classification", C["jerseys"]["teams_win"])}
  </div>
  <p style="margin-top:14px">Two structural blind spots of ours show up here. The book knows the <em>actual 2026 route</em> — which archetypes occur on which days, and that the race opens with a TTT feeding the yellow-jersey market. And the jersey markets price <em>three-week arcs</em>: the points jersey has Philipsen (2.1) ahead of Merlier (4.5) even though Merlier beats him on our single flat-day board — because the green jersey is won by surviving hills and hoovering intermediate sprints for three weeks, not by being fastest on one day.</p>
</section>

<section class="col tdf-scenario">
  <h3 class="tdf-h">"Wins a stage" — the specials market vs our best-day boards</h3>
  <p class="tdf-blurb">The book prices each rider to win at least one of 21 stages; our number is the single best day we could find for them across the six archetypes. These are different bets — the gap between the columns is mostly the value of having 21 chances, breakaway luck, and route knowledge. Where the book's "yes" is rich <em>and</em> our best day is tiny (van der Poel, Pedersen, Healy, Carapaz), the book is pricing opportunism our stage boards structurally under-count.</p>
  <div class="wide">{hunters_table(C["stage_hunters"])}</div>
</section>

<section class="col tdf-scenario">
  <h3 class="tdf-h">What happens next</h3>
  <p>This snapshot is archived (raw API payloads + parsed markets + margin diagnostics) as the first entry of a going-forward odds archive, alongside our own logged predictions. After Paris, the two get settled against results — per-market log loss for us and for the devigged book, the same yardstick our experiment gate uses. That, repeated over races, is the only honest answer to "can this model beat the books" — one Tour is a single sample. Until then: the model's job this month is to be well-calibrated; the market's job is to know things. The interesting work lives in the gap.</p>
</section>
"""

page = PAGE.read_text()
pattern = re.compile(r"<!-- BOOKS:BEGIN -->.*?<!-- BOOKS:END -->", re.S)
if not pattern.search(page):
    raise SystemExit("BOOKS markers not found")
PAGE.write_text(pattern.sub(lambda m: "<!-- BOOKS:BEGIN -->" + html + "<!-- BOOKS:END -->", page))
print(f"Spliced {len(html)/1024:.0f} KB books view into {PAGE.name}")
