"""Render the Vuelta 2026 post-race review page from review/analysis.json.

    uv run python performance_eval/vuelta-2026/review/analyze_review.py
    uv run python performance_eval/vuelta-2026/review/build_review_page.py

Writes netlify_site/vuelta-review.html. Every number in the prose is pulled
from analysis.json so the page cannot drift from the dataset; the words are
here. Style and structure mirror the Tour's review.html so the two read as a
pair.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "netlify_site" / "vuelta-review.html"
A = json.loads((HERE / "analysis.json").read_text())

STAGE_NAMES = {
    1: "Monaco ITT", 2: "Manosque", 4: "Andorra", 5: "Roquetes", 6: "Castellón",
    7: "Valdelinares", 8: "Xeraco", 9: "Alto de Aitana", 10: "Vinaròs", 11: "Lorca",
    12: "Calar Alto", 14: "La Pandera", 15: "Córdoba", 16: "La Rábida", 17: "Sevilla",
    20: "Collado del Alguacil", 21: "Granada",
}
SHORT_WINNER = {
    "Pogacar Tadej": "Pogačar", "Brennan Matthew": "Brennan", "Leknessund Andreas": "Leknessund",
    "Coquard Bryan": "Coquard", "Mas Enric": "Mas", "Tronchon Bastien": "Tronchon",
    "Omrzel Jakob": "Omrzel", "Brenner Marco": "Brenner", "van Aert Wout": "van Aert",
    "Landa Mikel": "Landa", "Johannessen Tobias Halland": "Johannessen",
}
HARDMAN = {10, 15, 21}
CLIMBER_BREAKS = {7, 12, 14, 20}
ITT = {1}
RESIDUAL_MAJORITY = set(A["exante_key"]["residual_majority"]["stages"])

P = A["panels"]
T = A["tdf_panels"]
G = A["gc"]
TG = A["tdf_gc"]
RC = A["ranking_channel"]
per = {r["stage"]: r for r in A["per_stage"]}
tdf_per = {r["stage"]: r for r in A["tdf_per_stage"]}
sc = A["scorecard"]


def f3(x, d=3):
    return "—" if x is None else f"{x:.{d}f}"


def pct(x, d=0):
    return "—" if x is None else f"{100 * x:.{d}f}%"


def sgn(x, d=3):
    return "—" if x is None else f"{x:+.{d}f}".replace("-", "−")


def cls(x):
    return "pos" if x is not None and x > 0 else ("neg" if x is not None and x < 0 else "")


def pp(x, d=1):
    return f"{x:+.{d}f}pp".replace("-", "−")


def tag(s):
    if s in HARDMAN:
        return '<span class="tagchip t-hm">hard-man</span>'
    if s in CLIMBER_BREAKS:
        return '<span class="tagchip t-cb">climbers\' break</span>'
    if s in ITT:
        return '<span class="tagchip t-itt">ITT</span>'
    return ""


def key_str(k):
    if not k:
        return "—"
    return "<br>".join(f"<span style=\"white-space:nowrap\">{name} {w:.2f}</span>" for name, w in sorted(k.items(), key=lambda kv: -kv[1]))


# ------------------------------------------------------------------ pieces


def diverging_chart(rows, href_prefix, maxabs, names, tags_fn, caption):
    out = ['<div class="dchart">',
           '<div class="dhead"><span class="l">Stage · winner</span><span class="c"><span>← market was closer</span><span>model was closer →</span></span><span class="v">nats</span></div>']
    for r in rows:
        d = r["delta_nats"]
        w = min(abs(d) / maxabs * 50, 50)
        fill = f'<span class="dfill {"pos" if d > 0 else "neg"}" style="width:{w:.1f}%"></span>'
        s = r["stage"]
        out.append(
            f'<div class="dbar"><span class="lab"><a href="{href_prefix}stage{s:02d}.html">St {s}</a> '
            f'<span class="w">· {names.get(r["winner"], r["winner"].split()[0])}</span>{tags_fn(s)}</span>'
            f'<span class="dtrack">{fill}</span><span class="val {cls(d)}">{d:+.2f}</span></div>'
        )
    out.append("</div>")
    out.append(f'<p class="caption">{caption}</p>')
    return "\n".join(out)


def panel_row(label, p, hl=False, note=""):
    o = p["overlap"]
    pod = (f"{f3(p['podium_ll_model'], 4)} / {f3(p['podium_ll_book'], 4)}"
           if p["podium_ll_model"] is not None else "—")
    return (
        f'<tr{" class=\"hl\"" if hl else ""}><td>{"<b>" if hl else ""}{label}{"</b>" if hl else ""}{note}</td>'
        f'<td class="num">{p["n"]}</td>'
        f'<td class="num">{f3(p["win_ll_model_ew"])} / {f3(p["win_ll_book"])} '
        f'<span class="{cls(p["win_ll_delta"])}">({sgn(p["win_ll_delta"])})</span></td>'
        f'<td class="num">{pod}</td>'
        + "".join(f'<td class="num {cls(o[str(k)]["delta_pp"])}">{o[str(k)]["delta_pp"]:+.0f}</td>' for k in (3, 5, 10, 15))
        + "</tr>"
    )


def line_chart(title, sub, series, ymin, ymax, yticks, xlabels, aria, fmt=lambda v: f"{v:.1f}"):
    """series: list of (label, color, dash, [(x_index, y) ...]); x indices 0..n-1."""
    W, H = 460, 250
    x0, x1, y0, y1 = 40, 450, 210, 20
    n = len(xlabels)

    def X(i):
        return x0 + (x1 - x0) * i / max(n - 1, 1)

    def Y(v):
        return y0 - (y0 - y1) * (v - ymin) / (ymax - ymin)

    grid = "".join(f'<line x1="{x0}" y1="{Y(t):.1f}" x2="{x1}" y2="{Y(t):.1f}"/>' for t in yticks)
    ylab = "".join(f'<text x="{x0 - 6}" y="{Y(t) + 4:.1f}" text-anchor="end">{fmt(t)}</text>' for t in yticks)
    step = max(1, (n - 1) // 5)
    xlab = "".join(
        f'<text x="{X(i):.1f}" y="232" text-anchor="middle">{lab}</text>'
        for i, lab in enumerate(xlabels) if i % step == 0 or i == n - 1
    )
    lines = ""
    for label, color, dash, pts in series:
        if not pts:
            continue
        d = f' stroke-dasharray="{dash}"' if dash else ""
        poly = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in pts)
        lines += f'<polyline fill="none" stroke="{color}" stroke-width="{2.5 if not dash else 2}"{d} points="{poly}"/>'
    legend = "".join(
        f'<span><span class="k" style="background:{c}"></span>{l}</span>' for l, c, _, _ in series
    )
    return f"""<div class="chart">
      <h3>{title}</h3>
      <p class="sub">{sub}</p>
      <svg viewBox="0 0 {W} {H}" role="img" aria-label="{aria}">
        <g stroke="#E5E3DB" stroke-width="1">{grid}</g>
        <g font-family="Avenir Next,Segoe UI,sans-serif" font-size="11" fill="#5C6470">{ylab}{xlab}</g>
        {lines}
      </svg>
      <div class="legend">{legend}</div>
    </div>"""


# ------------------------------------------------------------------ numbers

all_ = P["all"]
pel = P["peloton_settled"]
hm = P["hardman_only"]
bw = P["break_won_only"]
mhm = P["minus_hardman"]
mbw = P["minus_break_won"]
tall, tpel, thm, tbw = T["all"], T["peloton_settled"], T["hardman_only"], T["break_won_only"]
resid = A["exante_key"]["residual_majority"]
macro = A["exante_key"]["macro_majority"]
n_stages = all_["n"]
n_reads = all_["reads"]
maxabs = max(abs(r["delta_nats"]) for r in A["per_stage"])
sorted_deltas = sorted(A["per_stage"], key=lambda r: -r["delta_nats"])
best3 = sorted_deltas[:3]
worst3 = sorted_deltas[-3:][::-1]
n_ahead = sum(1 for r in A["per_stage"] if r["delta_nats"] > 0)

rc_tot = RC["totals"]
pub15, prod15, book15 = rc_tot["15"]["published"], rc_tot["15"]["production"], rc_tot["15"]["book"]
pub10, prod10, book10 = rc_tot["10"]["published"], rc_tot["10"]["production"], rc_tot["10"]["book"]
best15 = rc_tot["15"]["best_branch_pub"]
of15 = 15 * n_stages
of10 = 10 * n_stages
rc_rows = {r["stage"]: r for r in RC["per_stage"]}
hind_rows = [r for r in RC["per_stage"] if r["hind15"] is not None]
h15 = sum(r["hind15"] for r in hind_rows)
h15_pub = sum(r["pub15_ew"] for r in hind_rows)
h15_best = sum(r["pub15_best"] for r in hind_rows)
h15_book = sum(r["book15"] for r in hind_rows)

keyed = [s for s in sc if sc[s]["key"]]
n_exact = sum(1 for s in keyed if sc[s]["exact"])
n_cov = sum(1 for s in keyed if sc[s]["covered"])
mean_w = sum(sc[s]["w"] for s in keyed) / len(keyed)
oracle_counts = {}
for s in sc:
    oracle_counts[sc[s]["oracle"]] = oracle_counts.get(sc[s]["oracle"], 0) + 1
agent_rows = [(s, sc[s]["agent"]) for s in sc if sc[s]["agent"].get("agent_key") and not sc[s]["agent"].get("agent_replay")]

cal = A["calibration"]
tmp = A["temperature"]

gpost = G["post_abandon"]
gpre = G["pre_abandon"]
gall = G["all_paired"]
boards = [b for b in G["boards"] if b["through_stage"] is not None]
pog = G["pogacar_pre_abandon"]
last_top = G["last_paired_board_top"]

hits = A["hits"]["podium_model_over_book"]
misses = A["hits"]["podium_book_over_model"]
fav = {r["stage"]: r for r in A["favourites"]}

# ------------------------------------------------------------ chart data
xl = [f"st {b['through_stage']}" for b in boards]
sp_m = [(i, b["spearman_model"]) for i, b in enumerate(boards)]
sp_b = [(i, b["spearman_book"]) for i, b in enumerate(boards) if b["pairing"] not in ("stale", "")]
sp_o = [(i, b["spearman_outlook"]) for i, b in enumerate(boards)]
mas_m = [(i, b["winner_model_p"]) for i, b in enumerate(boards)]
mas_b = [(i, b["winner_book_p"]) for i, b in enumerate(boards) if b["pairing"] not in ("stale", "")]
mas_o = [(i, b["winner_outlook_p"]) for i, b in enumerate(boards)]
abandon_idx = next(i for i, b in enumerate(boards) if b["through_stage"] >= 8)

# ------------------------------------------------------------------- HTML

css = (ROOT / "netlify_site" / "review.html").read_text()
css = css[css.index("<style>") + len("<style>"):css.index("</style>")]
css += """
  .t-key{background:var(--green-soft);color:var(--green)}
  .two{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px;margin:18px 0;max-width:760px}
  .two .card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px 18px 6px}
  .two .card h3{margin:0 0 8px;font-size:15px}
  .two .card p{font-size:14.5px;margin:0 0 10px}
  .cmp td:first-child{white-space:nowrap}
  .dbar .lab,.dhead .l{width:262px}
"""

stage_rows_html = ""
for r in A["per_stage"]:
    s = r["stage"]
    k = sc[str(s)]
    verdict = "exact" if k["exact"] else ("covered" if k["covered"] else "missed")
    stage_rows_html += (
        f'<tr><td><a href="vuelta-stage{s:02d}.html">St {s}</a> <span class="muted">{STAGE_NAMES.get(s, "")}</span></td>'
        f'<td>{SHORT_WINNER.get(r["winner"], r["winner"])}</td>'
        f'<td class="num">{pct(r["model_p_ew"], 1)}</td><td class="num">{pct(r["book_p"], 1)}</td>'
        f'<td class="num {cls(r["delta_nats"])}">{r["delta_nats"]:+.2f}</td>'
        f'<td class="num">{r["model_rank_ew"]:.0f} / {r["book_rank"]}</td>'
        f'<td class="num">{r["overlap15_model"]:.1f} / {r["overlap15_book"]}</td>'
        f'<td>{key_str(k["key"])}</td><td>{k["oracle"]}</td><td>{verdict} <span class="muted">{k["w"]:.2f}</span></td></tr>'
    )

rc_rows_html = ""
for r in RC["per_stage"]:
    s = r["stage"]
    d = r["pub15_ew"] - r["prod15_ew"]
    rc_rows_html += (
        f'<tr><td>St {s} <span class="muted">{STAGE_NAMES.get(s, "")}</span></td>'
        f'<td class="num">{r["prod15_ew"]:.1f}</td><td class="num">{r["pub15_ew"]:.1f}</td>'
        f'<td class="num {cls(d)}">{d:+.1f}</td><td class="num">{r["pub15_best"]}</td>'
        f'<td class="num">{r["book15"]}</td><td class="num">{"—" if r["hind15"] is None else r["hind15"]}</td></tr>'
    )

hits_html = "".join(
    f'<tr><td>St {h["stage"]}</td><td>{h["rider"]}</td><td class="num">{h["place"]}</td>'
    f'<td class="num">{pct(h["model_p"], 1)}</td><td class="num">{pct(h["book_p"], 1)}</td><td class="num pos">×{h["ratio"]:.1f}</td></tr>'
    for h in hits[:8]
)
misses_html = "".join(
    f'<tr><td>St {h["stage"]}</td><td>{h["rider"]}</td><td class="num">{h["place"]}</td>'
    f'<td class="num">{pct(h["model_p"], 1)}</td><td class="num">{pct(h["book_p"], 1)}</td><td class="num neg">×{h["ratio"]:.2f}</td></tr>'
    for h in misses[:8]
)


def calrow(head, label):
    rows = {r["band"]: r for r in cal[head]}
    cells = ""
    for band in ("0.10-0.20", "0.20-0.30", "0.30-0.50", "0.50-0.75", "0.75-1.00"):
        r = rows.get(band)
        if not r:
            cells += '<td class="muted">—</td>'
            continue
        gap = r["realised"] - r["stated"]
        mark = "<b>" if abs(gap) > 0.08 else ""
        cells += f'<td>{r["stated"]:.2f} → {mark}{r["realised"]:.2f}{"</b>" if mark else ""} <span class="muted">(n{r["n"]})</span></td>'
    return f"<tr><td>{label}</td>{cells}</tr>"


agent_html = "".join(
    f'<tr><td>St {s}</td><td>{key_str(a["agent_key"])}</td><td>{key_str(sc[s]["key"]) if sc[s]["key"] else "<span class=muted>no human key (missed morning)</span>"}</td>'
    f'<td>{sc[s]["oracle"]}</td><td>{"exact" if a["agent_exact"] else ("covered" if a["agent_covered"] else "missed")} <span class="muted">{a["agent_weight_on_true"]:.2f}</span></td>'
    f'<td>{"exact" if sc[s]["exact"] else ("covered" if sc[s]["covered"] else ("missed" if sc[s]["key"] else "—"))}'
    f'{"" if not sc[s]["key"] else f" <span class=muted>{sc[s]['w']:.2f}</span>"}</td>'
    f'<td class="num">{a["agent_confidence"]:.2f}{" ⚑" if a["agent_self_flag"] else ""}</td></tr>'
    for s, a in agent_rows
)

last_top_html = "".join(
    f'<tr><td class="num">{r["final_place"]}</td><td>{r["rider"]}</td><td class="num">{pct(r["model"], 1)}</td>'
    f'<td class="num">{pct(r["outlook"], 1)}</td><td class="num">{pct(r["book"], 1)}</td></tr>'
    for r in last_top[:6]
)

pog_html = "".join(
    f'<tr><td>after stage {p["through_stage"]}</td><td class="num">{pct(p["model"], 0)}</td><td class="num">{pct(p["outlook"], 0)}</td><td class="num">{pct(p["book"], 0)}</td></tr>'
    for p in pog
)

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vuelta 2026 · How the model's Vuelta actually went</title>
<meta name="description" content="The post-race accounting of the cycling model's Vuelta a España 2026: model against the market and the road on every scored stage, the day-type fix we brought from the Tour, and the GC race after Pogačar left.">
<meta property="og:title" content="Three weeks against the market, second time round: the model's Vuelta">
<meta property="og:description" content="{n_stages} scored stages, {n_reads} published reads, {len(boards)} GC boards. Level with the market on winners this time, behind it at depth, and a Tour lesson that only half survived contact with Spain.">
<meta property="og:type" content="article">
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🚴</text></svg>">
<style>{css}</style>
</head>
<body>
<div class="wrap">

<header>
  <div class="eyebrow">Vuelta a España 2026 · Post-race review</div>
  <h1>Three weeks against the market, second time round: how the model's Vuelta went</h1>
  <p class="standfirst">Every morning of the Vuelta we published the model's prices next to the bookmaker's, chose a "day key" that said what kind of stage we expected, and let the road settle it. This is the full accounting: where the model held its own, where it lost, whether the fix we built after the Tour worked, and how the whole thing compares with July.</p>
  <div class="meta">
    <span><b>{n_stages}</b> stages scored</span>
    <span><b>{n_reads}</b> published reads</span>
    <span><b>{len(boards)}</b> daily GC boards</span>
    <span><b>{len(keyed)}</b> day keys graded</span>
    <span>benchmark: <b>devigged Unibet/Kambi odds</b></span>
    <span>settled <b>2026-09-13</b></span>
  </div>
  <p class="backlink"><a href="index.html">← System overview &amp; season boards</a> &nbsp;·&nbsp; <a href="vuelta-stages.html">Vuelta stage-by-stage diary</a> &nbsp;·&nbsp; <a href="vuelta-gc.html">Vuelta GC tracker</a> &nbsp;·&nbsp; <a href="review.html">The Tour review</a></p>
</header>

<div class="verdict">
  <p><b>The verdict, in six sentences.</b> On picking stage winners the model finished the Vuelta <em>level with the market</em>: {f3(all_["win_ll_model_ew"])} against {f3(all_["win_ll_book"])} in average log loss, where the Tour had ended {sgn(tall["win_ll_delta"], 2)} against us. It was ahead on {n_ahead} of {n_stages} scored days, and on the ten days decided by the peloton or the GC group it was clearly better than the market, not just level. The losses came where they always come, on days a breakaway decided the stage, but this time the market could not see those winners either, so they cost us far less than in July. Deeper down the result the picture reversed: the model was behind the market at five, ten and fifteen riders deep, the one place it had been ahead at the Tour. The day-key channel we built after the Tour named the right kind of day two times in three but kept under-weighting the escape on mountain days, and it changed the published boards very little. And in the GC, once Pogačar abandoned, the main board sat on 8% for the rider wearing the red jersey for two weeks, while the side head we call the "GC outlook" matched the market on the winner and beat it on the podium. That head should be pricing the GC page.</p>
</div>

<!-- ================= glossary ================= -->
<section id="terms">
  <div class="kicker">Before the numbers</div>
  <h2>How to read this page</h2>
  <p>This is written for someone who follows cycling and has no reason to know how a forecasting model or a betting market works. The market's odds are used here as a yardstick for information, not as advice: they are the best public summary of what everyone paying attention thinks will happen, so matching them means the model is capturing about as much as the crowd, and beating them means it knows something the crowd has not priced. Six terms carry the page.</p>
  <div class="gloss">
    <div class="g"><b>The market, or the book</b><p>Unibet's odds via the Kambi feed, captured the evening before each stage. We use it as the benchmark forecast because it aggregates the views of everyone willing to stake money on the outcome.</p></div>
    <div class="g"><b>Devigged</b><p>Bookmaker odds are inflated so the book profits whatever happens; the implied chances add to 140–150%, not 100%. Devigging strips that margin out. Every market number on this page is devigged, and both boards are rescaled over the same riders so they add to exactly one winner.</p></div>
    <div class="g"><b>Log loss and nats</b><p>The standard score for a probability forecast. You are charged for how surprised you were by what happened. Confidently right scores near zero, confidently wrong scores badly. Lower is better. Nats is the unit. A rule of thumb: giving the winner 10% instead of 20% costs 0.69 nats. ±0.1 per stage is small, ±1.0 is a badly missed day.</p></div>
    <div class="g"><b>Equal weight across reads</b><p>Each morning we published two to four "reads": alternative stories about how the day might go, each with its own priced board. The honest way to score us is to average across those reads, because we never said which one to believe. "Best read" numbers are shown as an upper bound only.</p></div>
    <div class="g"><b>Top-k overlap</b><p>A ranking check with no probabilities in it. Of the riders who actually finished in the top ten, how many were in your own top ten? Reported as percentage points of model minus market.</p></div>
    <div class="g"><b>Day key and oracle</b><p>Project terms, new since the Tour. The <em>day key</em> is a morning guess at what kind of stage it will be, as weights over a fixed menu (bunch sprint, GC day, time trial, or several kinds of "residual" day where an escape or a hard selection decides it). The <em>oracle</em> labels the same day afterwards from the actual result. A key is <em>exact</em> when its heaviest item is the oracle's, <em>covered</em> when the oracle's item got any weight at all.</p></div>
  </div>
  <p class="caption">What is and is not in the count. Stage 3 was cancelled in a hailstorm on the Col de Mont-Louis and is not scored. Stages 13, 18 and 19 were missed mornings: no key was chosen and no board was published before the start, so they are excluded rather than reconstructed. That leaves {n_stages} scored stages and {n_reads} published reads. Hidden calibration anchors and after-the-fact "hindsight" runs are never in a settlement number.</p>
</section>

<!-- ================= headline ================= -->
<section id="headline">
  <div class="kicker">The headline</div>
  <h2>Level with the market on the winner, and a very different race from July</h2>
  <p>The fairest single comparison is the winner market: how much probability each board put on the rider who actually won, averaged over the {n_stages} scored stages, with the model scored the way it was published (equal weight across that morning's reads).</p>

  <div class="tablewrap"><table>
    <tr><th>Frame</th><th class="num">Vuelta: model</th><th class="num">Vuelta: market</th><th class="num">Tour: model</th><th class="num">Tour: market</th></tr>
    <tr class="hl"><td><b>Equal weight across published reads</b> <span class="muted">(honest, ex-ante)</span></td><td class="num"><b>{f3(all_["win_ll_model_ew"])}</b></td><td class="num"><b>{f3(all_["win_ll_book"])}</b></td><td class="num">{f3(tall["win_ll_model_ew"])}</td><td class="num">{f3(tall["win_ll_book"])}</td></tr>
    <tr><td>Best read per stage, picked after the fact <span class="muted">(upper bound)</span></td><td class="num">{f3(all_["win_ll_model_best"])}</td><td class="num">{f3(all_["win_ll_book"])}</td><td class="num">{f3(tall["win_ll_model_best"])}</td><td class="num">{f3(tall["win_ll_book"])}</td></tr>
    <tr><td>Favourite won: reads where our top pick won / market's top pick won</td><td class="num">{all_["top_pick_wins_model"]} of {n_reads}</td><td class="num">{all_["top_pick_wins_book"]} of {n_reads}</td><td class="num">{tall["top_pick_wins_model"]} of {tall["reads"]}</td><td class="num">{tall["top_pick_wins_book"]} of {tall["reads"]}</td></tr>
  </table></div>
  <p class="caption">Average winner-market log loss per stage, lower is better. At the Tour the market beat us by {abs(tall["win_ll_delta"]):.2f} nats a stage. At the Vuelta the gap is {sgn(all_["win_ll_delta"], 3)} in the model's favour, which is a tie. Our favourite won on {all_["top_pick_wins_model"]} reads to the market's {all_["top_pick_wins_book"]}.</p>

  <p>Notice the second thing in that table before the first. The market's own score was {f3(all_["win_ll_book"])} at the Vuelta against {f3(tall["win_ll_book"])} at the Tour. This was a much harder race to forecast for everyone: the overwhelming favourite left it on stage 8, five stages went to escapes, and three were won by riders the market had at under 1%. So "level with the market" here is level with a market that was itself struggling. That matters for how much credit to take, and it comes back in the section on hard days.</p>

  <p>Here is the whole race, day by day: how far above or below the market the model priced each actual winner.</p>

{diverging_chart(A["per_stage"], "vuelta-", maxabs, SHORT_WINNER, tag, f"Per-stage winner-market difference in nats: how much more (green) or less (red) probability the model put on the actual winner than the market did, equal weight across that day's published reads. Tags mark the stage classes discussed below. Each stage links to its preview page.")}

  <p>Two things stand out. The good days are big: the model's four best days ({', '.join(f'stage {r["stage"]}' for r in sorted_deltas[:4])}) are each worth more than half a nat, and only one stage all Tour had done that. And the bad days are smaller than the Tour's. The worst day here is {worst3[0]["delta_nats"]:+.2f}; the Tour had four days worse than that.</p>
</section>

<!-- ================= hits ================= -->
<section id="hits">
  <div class="kicker">The best days</div>
  <h2>Where the model saw something the market did not</h2>
  <div class="two">
    <div class="card"><h3>Stage 1, the Monaco time trial ({per[1]["delta_nats"]:+.2f})</h3><p>The market made Joshua Tarling a {pct(fav[1]["book_fav_p"])} favourite for a 9.4 km city prologue and had Pogačar at {pct(per[1]["book_p"], 1)}. The model, which cannot tell a short technical prologue from a long flat time trial and simply prices class, had Pogačar first at {pct(per[1]["model_p_ew"])}. Pogačar won; Tarling was third. This was the first of a pattern: on days the market typecast a rider by discipline, the model's "quality transfers" default won.</p></div>
    <div class="card"><h3>Stage 6, Castellón ({per[6]["delta_nats"]:+.2f})</h3><p>The market priced Pogačar at {pct(per[6]["book_p"])} and spread the rest of its probability across a card of breakaway specialists: Tulett, Johannessen, Fortunato, Vine, Bisiaux, Bilbao. Not one of them finished in the top twenty. The model refused the whole card and had Pogačar at {pct(per[6]["model_p_ew"])}. Stage 4 in Andorra was the same story in miniature: Vine and Fortunato were the market's second and third choices and finished 11th and 40th, and our board had the whole GC group home in nearly the right order.</p></div>
    <div class="card"><h3>Stage 21, Granada ({per[21]["delta_nats"]:+.2f})</h3><p>The market made Wout van Aert a {pct(fav[21]["book_fav_p"])} favourite for the cobbled city circuit. He finished 65th. Our published boards were wrong too: two of the three reads had Brennan first. But the third, the "late move" read, had van Aert, Debruyne and Johannessen as its top three. Johannessen won and Debruyne was third, and that read priced the winner at 4.2% against the market's 0.8%. The scenario fork carried knowledge the model itself does not have.</p></div>
    <div class="card"><h3>Stage 2, Manosque ({per[2]["delta_nats"]:+.2f})</h3><p>Matthew Brennan was the market's third choice at {pct(per[2]["book_p"], 1)} behind Pedersen and van Aert. The model had him first at {pct(per[2]["model_p_ew"], 1)} and Pogačar second; they finished first and third, and the faded van Aert was 22nd. The day key also promoted Pau Miquel from 17th on the production board to 11th on the published one, and he finished second at odds of 101.</p></div>
  </div>

  <p>The same pattern shows up in the small print. Among riders who finished on a stage podium, these are the ones where the model had been furthest above the market:</p>
  <div class="tablewrap"><table>
    <tr><th>Stage</th><th>Rider</th><th class="num">Finished</th><th class="num">Model</th><th class="num">Market</th><th class="num">Ratio</th></tr>
    {hits_html}
  </table></div>
  <p class="caption">Win probability on the rider, model (equal weight across reads) against the devigged market, for podium finishers. Roglič third at Aitana, Johannessen and Debruyne second and third from the escape on stage 20, Gall third in Andorra: the model kept finding the right riders in the places behind the winner, especially on GC days.</p>
</section>

<!-- ================= misses ================= -->
<section id="misses">
  <div class="kicker">The worst days</div>
  <h2>Where the model was wrong, and what kind of wrong it was</h2>
  <div class="two">
    <div class="card"><h3>Stage 10, Vinaròs ({per[10]["delta_nats"]:+.2f})</h3><p>The worst day. The model had Brennan first at {pct(fav[10]["model_fav_p"])}, twice the market's price, with Meeus second and Pedersen fifth. They finished 90th, 111th and 163rd: the hills after the rest day shed every pure sprinter and Bastien Tronchon won from a 68-rider group of everyone else. The day key said "bunch" and was graded exact, because 68 riders is a bunch. The board was still useless, because it was the wrong bunch. This is the cleanest example in the race of the two questions a day key has to answer, how big the front group is and who is in it, coming apart.</p></div>
    <div class="card"><h3>Stage 20, Collado del Alguacil ({per[20]["delta_nats"]:+.2f})</h3><p>Mikel Landa won alone from the escape. Every read, and the hindsight run given the day's real shape, had him around 0.3% and 50th on the board; the market had him at 0.8%. His best result of 2026 before this was 14th, and he had not won a race since 2021. Some winners are not mispriced so much as unpriceable from a results record. The consolation was real: the model had Johannessen and Debruyne, second and third, at three to five times the market's price.</p></div>
    <div class="card"><h3>Stage 7, Valdelinares ({per[7]["delta_nats"]:+.2f})</h3><p>The model's worst day in absolute terms. Pogačar had 3:34 in hand and no reason to race; the bunch conceded the break twenty minutes, and Andreas Leknessund won at odds of 151. Our official read put 60% on a GC day and had Pogačar at {pct(fav[7]["model_fav_p"])}; the production board found one of the actual top fifteen. Nobody priced Leknessund, but the market at least had the day's shape right, with a full card of break riders behind Pogačar.</p></div>
    <div class="card"><h3>Stage 15, Córdoba ({per[15]["delta_nats"]:+.2f}) and stage 9, Aitana ({per[9]["delta_nats"]:+.2f})</h3><p>Two different failures. On the heat-shortened stage 15 the model had Brennan first at {pct(fav[15]["model_fav_p"])} and van Aert third; van Aert's own team rode the last climb to launch him instead of setting up Brennan, and he won from a five-man escape. At Aitana the model got the right four riders in its top four and simply put too little on the one who won: Mas at {pct(per[9]["model_p_ew"], 1)} against the market's {pct(per[9]["book_p"], 1)}, behind Roglič, Gall and Onley.</p></div>
  </div>

  <p>And the mirror image of the table above: podium finishers where the market had been furthest above the model.</p>
  <div class="tablewrap"><table>
    <tr><th>Stage</th><th>Rider</th><th class="num">Finished</th><th class="num">Model</th><th class="num">Market</th><th class="num">Ratio</th></tr>
    {misses_html}
  </table></div>
  <p class="caption">Almost every name here is a rider who finishes at the front of reduced or escape groups: Romele, Nys, Cort, Coquard, Buitrago, Cristian Rodríguez. The market rates them from watching races; the model's features, built on results, kept leaving them outside its top fifteen. This group is the Vuelta's version of the Tour's "hard-man" problem, and it is where the depth deficit below comes from.</p>
</section>

<!-- ================= depth ================= -->
<section id="depth">
  <div class="kicker">The shape of the result</div>
  <h2>Better at the very top, behind the market further down</h2>
  <p>At the Tour the pattern was clear: the model was behind the market on the winner and the podium, level by ten riders deep and slightly ahead by fifteen. The Vuelta flipped it. For each depth, count how many of the actual top-k finishers each board had in its own top k, summed over the scored stages:</p>

  <div class="tablewrap"><table>
    <tr><th>Depth</th><th class="num">Model</th><th class="num">Market</th><th class="num">Vuelta delta</th><th class="num">Tour delta</th></tr>
    {''.join(f'<tr><td>Top {k}</td><td class="num">{all_["overlap"][str(k)]["model"]:.1f} / {all_["overlap"][str(k)]["of"]} <span class="muted">({100*all_["overlap"][str(k)]["model"]/all_["overlap"][str(k)]["of"]:.0f}%)</span></td><td class="num">{all_["overlap"][str(k)]["book"]} / {all_["overlap"][str(k)]["of"]} <span class="muted">({100*all_["overlap"][str(k)]["book"]/all_["overlap"][str(k)]["of"]:.0f}%)</span></td><td class="num {cls(all_["overlap"][str(k)]["delta_pp"])}">{pp(all_["overlap"][str(k)]["delta_pp"])}</td><td class="num {cls(tall["overlap"][str(k)]["delta_pp"])}">{pp(tall["overlap"][str(k)]["delta_pp"])}</td></tr>' for k in (3, 5, 10, 15))}
  </table></div>
  <p class="caption">Actual top-k riders captured inside each board's own top k, summed over {n_stages} stages (Tour: {tall["n"]}). Model = its published reads averaged per stage. Rank correlation over the whole field: model {f3(all_["spearman_model"])}, market {f3(all_["spearman_book"])} (Tour: {f3(tall["spearman_model"])} against {f3(tall["spearman_book"])}). On the podium market, priced on {all_["podium_n"]} stages, the two were level: {f3(all_["podium_ll_model"], 4)} against {f3(all_["podium_ll_book"], 4)} mean per-rider log loss.</p>

  <p>So the Tour's diagnosis, "we read the race as well as the market but will not commit to our favourite", does not describe the Vuelta. Here the model committed, and was often right to. What it lost was the middle of the board: the {all_["overlap"]["15"]["book"] - all_["overlap"]["15"]["model"]:.0f}-rider deficit at fifteen deep is concentrated on the escape days: on stages 7, 14 and 15 the market's card of break specialists found three to six of the top fifteen and our production board found one or two. The next two sections split that out.</p>

  <h3>Did the model's shyness come back?</h3>
  <p>The Tour's most fixable defect was under-confidence: when the model said 38% it happened 40% of the time, when it said 60% on a top-five place it happened 82%. Here is the same table for the Vuelta. Each cell reads <em>probability we stated → rate it actually happened</em>, and bold marks a gap of more than eight points.</p>
  <div class="tablewrap"><table>
    <tr><th>Head</th><th>Stated 0.10–0.20</th><th>0.20–0.30</th><th>0.30–0.50</th><th>0.50–0.75</th><th>0.75+</th></tr>
    {calrow("win", "Winner")}
    {calrow("podium", "Podium")}
    {calrow("top5", "Top 5")}
    {calrow("top15", "Top 15")}
    {calrow("book_win", "Market, winner <span class=muted>(for contrast)</span>")}
  </table></div>
  <p class="caption">Calibration of the published boards over all visible reads. The winner head is still a little shy in the 0.30–0.50 band, on a small sample, and is roughly honest above 0.50. The depth heads have gone the other way: when we said {int(100*[r for r in cal['top5'] if r['band']=='0.75-1.00'][0]['stated'])}% for a top-five place it happened {int(100*[r for r in cal['top5'] if r['band']=='0.75-1.00'][0]['realised'])}% of the time. That is over-confidence, not shyness, and it tracks the thinning field: with Pogačar, Pedersen, Groves and twenty others gone, the riders the model kept rating highly for the places were not all there at the end.</p>
  <p>We also re-ran the Tour's cheapest fix, a one-parameter "sharpening" of the board fitted leave-one-stage-out. At the Tour it was worth about 0.08 nats a stage on ordinary days. At the Vuelta it is worth nothing: the best fitted setting on all {tmp["all"]["n"]} stages is "leave the board alone", and on the ten peloton-settled days sharpening made the held-out score slightly worse ({f3(tmp["peloton_settled"]["raw"])} → {f3(tmp["peloton_settled"]["calibrated"])}). One race said sharpen, the next said do not. The honest reading is that the miscalibration is not a stable constant to correct but depends on the race and the state of the field, which is an argument for a calibration that watches the current race rather than one number fitted in July.</p>
</section>

<!-- ================= hard days ================= -->
<section id="harddays">
  <div class="kicker">The standing problem</div>
  <h2>Escape days still cost us, but far less than in July</h2>
  <p>After the Tour we named one class of day as the model's structural hole: a shattered, non-mountain stage won by a punchy non-climber from a break, a late move, or a reduced hard-men sprint. The broader version was any day a breakaway decided the stage. The same carves, drawn the same way (by day shape and winner type, never by how we scored), applied to the Vuelta:</p>
  <ul>
    <li><b>Hard-man days: stages 10, 15, 21.</b> Tronchon from a 68-rider group with the sprinters gone; van Aert from a five-man escape on a rolling day; Johannessen on the Granada circuit with van Aert 65th. Stage 13, van Aert from a two-up, belongs here too but was a missed morning.</li>
    <li><b>Climbers' breaks: stages 7, 12, 14, 20.</b> Leknessund, Omrzel, Brenner and Landa, all from the escape on mountain days. Stage 19 (Dunbar) belongs here and was also unscored.</li>
    <li><b>Peloton or GC-settled: the other ten</b>, including the Monaco time trial.</li>
  </ul>

  <div class="tablewrap"><table>
    <tr><th>Panel</th><th class="num">n</th><th class="num">Win LL model / market</th><th class="num">Podium LL</th><th class="num">Top 3</th><th class="num">Top 5</th><th class="num">Top 10</th><th class="num">Top 15</th></tr>
    {panel_row("All scored stages", all_)}
    {panel_row("Minus hard-man days {10, 15, 21}", mhm)}
    {panel_row("Minus all break-won days {7, 12, 14, 15, 20}", mbw)}
    {panel_row("Peloton / GC-settled days only", pel, hl=True)}
    {panel_row("Hard-man days alone", hm)}
    {panel_row("Break-won days alone", bw)}
    <tr><td colspan="8" class="muted" style="padding-top:14px">The Tour, same carves</td></tr>
    {panel_row("Tour: all stages", tall)}
    {panel_row("Tour: peloton / GC-settled only", tpel)}
    {panel_row("Tour: hard-man days alone", thm)}
    {panel_row("Tour: break-won and hard-man days", tbw)}
  </table></div>
  <p class="caption">Win LL = average winner log loss, model / market, with the difference in brackets (+ means the model was closer). Podium LL where the market priced a podium. Top-k columns are model-minus-market percentage points of the actual top k captured.</p>

  <p>Three things to take from that.</p>
  <ul>
    <li><b>On the days it is built for, the model beat the market outright.</b> Peloton and GC-settled days: {f3(pel["win_ll_model_ew"])} against {f3(pel["win_ll_book"])}, a {pel["win_ll_delta"]:.2f}-nat lead per stage, on ten stages. At the Tour the same frame was a dead heat ({sgn(tpel["win_ll_delta"], 3)}). This is the strongest result of the campaign.</li>
    <li><b>The escape days hurt about a third as much as they did in July.</b> Break-won days ran {sgn(bw["win_ll_delta"], 2)} against the market here, against {sgn(tbw["win_ll_delta"], 2)} at the Tour; hard-man days {sgn(hm["win_ll_delta"], 2)} against {sgn(thm["win_ll_delta"], 2)}. The reason is not that we got better at them. It is that the market could not see these winners either: Tronchon at 0.7%, Landa 0.8%, Brenner 0.3%, Leknessund 0.4%. At the Tour the break winners were Carapaz twice, Philipsen and Schmid, all riders the market had priced. When the surprise is a genuine surprise, being blind costs little. When the market can see it and we cannot, it costs a lot.</li>
    <li><b>The depth deficit lives on the escape days.</b> Take the break-won days out and the model is ahead at three and ten deep and within four points at fifteen. On the break days themselves it is nine to twelve points behind at every depth: the market's card of stage hunters populates its top fifteen with the people who actually get in the move, and ours does not.</li>
  </ul>
  <p>So the summary sentence from July still stands, with one amendment: <b>we price a bike race at or above market level whenever it is decided by the group we can see, and we lose ground on the days a breakaway decides it, in proportion to how well the market can see the escape.</b></p>
</section>

<!-- ================= the remedy ================= -->
<section id="remedy">
  <div class="kicker">The fix we brought from the Tour</div>
  <h2>The day key: right about the kind of day two times in three, and not yet the fix</h2>
  <p>The Tour review ended with a priority list, and the top item was day-class detection: know what kind of stage it is before it starts, so the model can pull the right kind of rider into its shortlist and so we can say in advance which days to trust. Between the races we built that as a menu of eight day types plus three "macro" types (bunch sprint, GC day, time trial), a labeller that grades each finished stage against the menu, and a serving channel that takes a morning key and uses it to re-rank the shortlist of riders the model considers. Two design decisions matter for reading the results. The key only changes <em>who is in the top fifteen and in what order</em>; the prices still come from the untouched production model, so a wrong key cannot corrupt a probability. And the key is chosen by judgment each morning, from the road book, the news and the market card, then graded that evening. The Vuelta was the first live test.</p>

  <h3>How good were the keys?</h3>
  <p>Of {len(keyed)} keyed stages the key's heaviest item matched the oracle on <b>{n_exact}</b>, the oracle's item had some weight on <b>{n_cov}</b>, and the average weight on the true item was <b>{mean_w:.2f}</b>. The oracle's own labels across the twenty raced stages were: {', '.join(f'{k} {v}' for k, v in sorted(oracle_counts.items(), key=lambda kv: -kv[1]))}.</p>

  <div class="tablewrap"><table>
    <tr><th>Stage</th><th>Winner</th><th class="num">Model</th><th class="num">Market</th><th class="num">Δ nats</th><th class="num">Winner's rank m / b</th><th class="num">Top-15 found m / b</th><th>Day key</th><th>Oracle</th><th>Graded</th></tr>
    {stage_rows_html}
  </table></div>
  <p class="caption">One row per scored stage. Model and market columns are the win probability on the actual winner; Δ is the log-loss difference (+ = model closer). "Winner's rank" is where the winner sat on each board. "Top-15 found" is how many of the actual top fifteen each board had in its own top fifteen. The key is the morning's weights; "graded" is the evening verdict with the weight placed on the true item.</p>

  <p>The misses have a shape, and it was visible by the first week. On stages 2, 5 and 6 the key put the "interesting" residual item ahead of the boring macro one, and the road went the boring way each time. Corrected for that, stage 7 went the interesting way and the key had 60% on a GC day. From there the rule became a question, "who has a reason to chase?", and it worked on the sprint stages: 8, 9, 10, 11, 16 and 17 were all exact. It did not work on the mountain escapes. Stages 7, 12, 14 and 20 all went to the break; on two of them (7 and 14) the key's majority was still the GC day, and on the other two the GC day still carried 40–45%. The written lesson from La Pandera was the sharpest: a breakaway with the leader's own team in it will not be chased, however good the launchpad, and the market had read that by lunchtime. There was also a labelling quirk: three consecutive escape wins (stages 15, 19 and 20) were graded as the "hard puncheur" item rather than the "mountain escape" one, even on stage 20 where the front fifteen were nearly all climbers. That cost stage 20 its grade.</p>

  <h3>Did the key help the boards?</h3>
  <p>This is the question the whole program turns on, and it can be measured cleanly because every prediction file carries both rankings: the production model's order and the key-adjusted order that was actually published. Count the actual top fifteen found by each.</p>
  <div class="tablewrap"><table>
    <tr><th>Stage</th><th class="num">Production board</th><th class="num">Published (keyed) board</th><th class="num">Δ</th><th class="num">Best single read</th><th class="num">Market</th><th class="num">Hindsight run</th></tr>
    {rc_rows_html}
    <tr class="hl"><td><b>Total, {n_stages} stages</b></td><td class="num"><b>{prod15:.0f}</b> / {of15}</td><td class="num"><b>{pub15:.0f}</b> / {of15}</td><td class="num {cls(pub15 - prod15)}"><b>{pub15 - prod15:+.0f}</b></td><td class="num">{best15}</td><td class="num">{book15}</td><td class="num muted">{h15:.0f} on {len(hind_rows)} stages</td></tr>
  </table></div>
  <p class="caption">Actual top-fifteen riders inside each board's top fifteen, averaged across that morning's reads (production and published are the same riders priced the same way; only the order differs). These use the model's published ranking, which is a separate ranking head; the depth table earlier orders riders by their win price, as the Tour review did, and that ordering finds fewer of the top fifteen ({all_["overlap"]["15"]["model"]:.0f}) than the ranking head does. "Best single read" is the highest of the morning's reads. The hindsight run re-ran the day afterwards knowing its real shape; on the {len(hind_rows)} stages that have one it found {h15:.0f} against the published boards' {h15_pub:.0f}, the best single read's {h15_best:.0f} and the market's {h15_book:.0f}.</p>

  <p>Read plainly: <b>the key moved the shortlist by {pub15 - prod15:+.0f} riders in {of15} over the whole race.</b> That is a small positive, and at ten deep it was a small negative ({pub10 - prod10:+.0f}). The gains came exactly where the theory said they would, on the two mountain escapes (stages 7 and 14, {rc_rows[7]["pub15_ew"] - rc_rows[7]["prod15_ew"]:+.1f} and {rc_rows[14]["pub15_ew"] - rc_rows[14]["prod15_ew"]:+.1f}) where the front group looked nothing like the production ranking's default, and the losses came on days where the key was wrong and pushed the right riders out (stage 6, {rc_rows[6]["pub15_ew"] - rc_rows[6]["prod15_ew"]:+.1f}). The market still found more of the top fifteen than either of our boards.</p>
  <p>The more encouraging number is the "best single read" column. Across the race the best of our own morning reads found {best15} of the actual top fifteen, against the market's {book15}. The information is inside our own scenario structure. What we could not do, yet, was say in the morning which read to trust. That is the same finding the Tour produced about scenario weighting, now with a mechanism attached.</p>

  <h3>Did the key tell us which days to trust?</h3>
  <p>At the Tour the days we had flagged in advance as hard-man days were the days we lost most heavily, which suggested a simple rule: publish with less confidence on flagged days. The Vuelta's version of a flag is a key that puts most of its weight on a residual item. Six days were keyed that way (stages {', '.join(str(s) for s in sorted(RESIDUAL_MAJORITY))}); eleven were keyed macro-majority.</p>
  <div class="tablewrap"><table>
    <tr><th>Days where the key said…</th><th class="num">n</th><th class="num">Win LL model / market</th><th class="num">Top 10</th><th class="num">Top 15</th></tr>
    <tr><td>…mostly a residual (unusual) day</td><td class="num">{resid["n"]}</td><td class="num">{f3(resid["win_ll_model_ew"])} / {f3(resid["win_ll_book"])} <span class="{cls(resid["win_ll_delta"])}">({sgn(resid["win_ll_delta"])})</span></td><td class="num {cls(resid["overlap"]["10"]["delta_pp"])}">{resid["overlap"]["10"]["delta_pp"]:+.0f}</td><td class="num {cls(resid["overlap"]["15"]["delta_pp"])}">{resid["overlap"]["15"]["delta_pp"]:+.0f}</td></tr>
    <tr><td>…mostly a bunch sprint, GC day or time trial</td><td class="num">{macro["n"]}</td><td class="num">{f3(macro["win_ll_model_ew"])} / {f3(macro["win_ll_book"])} <span class="{cls(macro["win_ll_delta"])}">({sgn(macro["win_ll_delta"])})</span></td><td class="num {cls(macro["overlap"]["10"]["delta_pp"])}">{macro["overlap"]["10"]["delta_pp"]:+.0f}</td><td class="num {cls(macro["overlap"]["15"]["delta_pp"])}">{macro["overlap"]["15"]["delta_pp"]:+.0f}</td></tr>
  </table></div>
  <p class="caption">The Tour's rule inverted. The days we flagged as unusual were our <em>better</em> days against the market; the days we called ordinary were where we lost. The reason is recall: of the seven escape and hard-man days, the key put its majority on an unusual item on only three (12, 20 and 21). Stages 7, 10, 14 and 15 were all keyed as ordinary days and were not.</p>
  <p>So the honest verdict on the fix: the machinery works as designed (the prices were never touched, the re-ranking helped exactly where the key was right about an unusual front), the keying rules improved measurably through the race, and neither yet catches the days that matter most. The mountain-escape question, "will the bunch let it go?", turned out to be about team incentives rather than terrain, and that is now written down as a rule rather than a feeling.</p>

  <h3>The shadow agent</h3>
  <p>From stage 16 an automated agent chose its own key each morning, blind to the human one, as a rehearsal for running the daily cycle unattended. It produced {len(agent_rows)} live keys. It also replayed the stages before it went live from frozen morning bundles after the fact (a calibration exercise, not a live record), where it was exact on nine of eleven graded stages against the human's five on the same days.</p>
  <div class="tablewrap"><table>
    <tr><th>Stage</th><th>Agent key</th><th>Human key</th><th>Oracle</th><th>Agent graded</th><th>Human graded</th><th class="num">Agent confidence</th></tr>
    {agent_html}
  </table></div>
  <p class="caption">Live, blind keys only. ⚑ marks a key the agent flagged for human review itself. On stage 18 there was no human key at all, because the morning was missed; the agent's key was the only prospective read of the day and it was exact.</p>
</section>

<!-- ================= GC ================= -->
<section id="gc">
  <div class="kicker">The other race</div>
  <h2>GC: the race changed on stage 8, and only one of our heads noticed</h2>
  <p>For seven stages this was a procession. Pogačar won the prologue, Andorra and Castellón and led by 3:34. Then he crashed on the flat run into Xeraco and abandoned, and the Vuelta became a four-man race that Enric Mas won from Roglič and Gall. That makes the GC boards a test of one thing above all: does the board respond to the race? We had two answers running side by side all month. The main blend, which prices riders from their history and form and does not look at the standings, and the state-aware "GC outlook" head, which does.</p>

  <div class="chartgrid">
    {line_chart("How well each board matched the final GC", "Rank correlation with the final classification, board by board", [("model blend", "#3E6B8F", "", sp_m), ("GC outlook head", "#47705A", "", sp_o), ("market", "#22272F", "5 4", sp_b)], 0.4, 1.0, [0.4, 0.6, 0.8, 1.0], xl, "Line chart: model blend flat near 0.7 all race; outlook head and market climb after stage 8, market to 0.94")}
    {line_chart("Win probability on the eventual winner, Enric Mas", "After each stage: model blend, outlook head, devigged market", [("model blend", "#3E6B8F", "", mas_m), ("GC outlook head", "#47705A", "", mas_o), ("market", "#22272F", "5 4", mas_b)], 0.0, 1.0, [0, 0.25, 0.5, 0.75, 1.0], xl, "Line chart: blend stays under 10 percent all race; outlook rises to 58 percent; market rises to 83 percent", fmt=lambda v: f"{int(v*100)}%")}
  </div>
  <p class="caption">Left: the market's board converges on the final order as the race resolves; the blend's stays flat near {f3(gall["spearman_model"], 2)}, exactly the Tour's frozen-board defect again; the outlook head sits between them. Right: the same story in the price on the winner. From the morning after Aitana, when Mas took red, the blend had him at {pct(boards[abandon_idx+1]["winner_model_p"], 0)} and never moved; the outlook head had him at {pct(boards[abandon_idx+1]["winner_outlook_p"], 0)} that day and {pct(boards[-2]["winner_outlook_p"], 0)} going into the last mountain stage; the market went from {pct(boards[abandon_idx+1]["winner_book_p"], 0)} to {pct(boards[-2]["winner_book_p"], 0)}. The market's GC prices closed after stage 19, so its line stops there.</p>

  <div class="tablewrap"><table>
    <tr><th>After Pogačar's abandon ({gpost["n"]} boards, stages 8–19)</th><th class="num">Model blend</th><th class="num">GC outlook head</th><th class="num">Market</th></tr>
    <tr><td>Log loss on the eventual winner <span class="muted">(lower is better)</span></td><td class="num">{f3(gpost["winner_ll_model"])}</td><td class="num"><b>{f3(gpost["winner_ll_outlook"])}</b></td><td class="num"><b>{f3(gpost["winner_ll_book"])}</b></td></tr>
    <tr><td>Podium, mean per-rider log loss</td><td class="num">{f3(gpost["podium_ll_model"], 4)}</td><td class="num"><b>{f3(gpost["podium_ll_outlook"], 4)}</b></td><td class="num">{f3(gpost["podium_ll_book"], 4)}</td></tr>
    <tr><td>Actual top 15 inside the board's top 15 <span class="muted">(of 15)</span></td><td class="num">{gpost["overlap15_model"]:.1f}</td><td class="num"><b>{gpost["overlap15_outlook"]:.1f}</b></td><td class="num">{gpost["overlap15_book"]:.1f}</td></tr>
    <tr><td>Actual top 5 inside the board's top 5 <span class="muted">(of 5)</span></td><td class="num">{gpost["overlap5_model"]:.1f}</td><td class="num"><b>{gpost["overlap5_outlook"]:.1f}</b></td><td class="num"><b>{gpost["overlap5_book"]:.1f}</b></td></tr>
    <tr><td>Rank correlation with the final GC</td><td class="num">{f3(gpost["spearman_model"], 2)}</td><td class="num">{f3(gpost["spearman_outlook"], 2)}</td><td class="num"><b>{f3(gpost["spearman_book"], 2)}</b></td></tr>
  </table></div>
  <p class="caption">Boards paired with the market snapshot that knew the same stages (the market closed its GC prices after stage 19, so the board after stage 20 is not in this table). The outlook head matched the market on the winner, beat it on the podium and at fifteen deep, and trailed it on whole-field ordering because it collapses to near zero on the chasers once it has picked its two leaders.</p>

  <p>The last board with a market price to compare against, going into the final mountain stage:</p>
  <div class="tablewrap"><table>
    <tr><th class="num">Final GC</th><th>Rider</th><th class="num">Model blend</th><th class="num">GC outlook head</th><th class="num">Market</th></tr>
    {last_top_html}
  </table></div>
  <p class="caption">GC win probability after stage 19. The blend had the race leader fourth on its own board, behind Roglič, Gall and Onley, because it never saw the standings and Mas's history is that of a rider who finishes second. The outlook head knew who was winning. Neither head is right alone: the outlook over-concentrates on the leaders and gives third-placed Gall a 1% chance; the blend knows who is good and ignores the race. The Tour review said this needed a corrector over the shared board rather than either head on its own, and the Vuelta says it twice as loudly.</p>

  <div class="note"><b>Before the abandon.</b> All three boards had Pogačar first through stage 7. The blend had him at about {pct(pog[-1]["model"], 0)}, the outlook head at {pct(pog[-1]["outlook"], 0)}, the market at {pct(pog[-1]["book"], 0)}. When he left the race the model's caution looked good in the ledger and the market's confidence looked bad, which is why the whole-race GC numbers are kinder to the blend than the post-abandon table. That is luck, not skill: a board that does not move cannot be credited for not having moved.</div>

  <div class="tablewrap"><table class="cmp">
    <tr><th>GC, whole race</th><th class="num">Vuelta: blend</th><th class="num">Vuelta: market</th><th class="num">Tour: blend</th><th class="num">Tour: market</th></tr>
    <tr><td>Log loss on the eventual winner, mean over boards</td><td class="num">{f3(gall["winner_ll_model"])}</td><td class="num">{f3(gall["winner_ll_book"])}</td><td class="num">{f3(TG["winner_ll_model"])}</td><td class="num">{f3(TG["winner_ll_book"])}</td></tr>
    <tr><td>Rank correlation with the final GC</td><td class="num">{f3(gall["spearman_model"], 2)}</td><td class="num">{f3(gall["spearman_book"], 2)}</td><td class="num">{f3(TG["spearman_model"], 2)}</td><td class="num">{f3(TG["spearman_book"], 2)}</td></tr>
    <tr><td>Actual top 15 inside the board's top 15</td><td class="num">{gall["overlap15_model"]:.1f}</td><td class="num">{gall["overlap15_book"]:.1f}</td><td class="num">{TG["overlap15_model"]:.1f}</td><td class="num">{TG["overlap15_book"]:.1f}</td></tr>
    <tr><td>Podium log loss: blend / outlook head / market</td><td class="num" colspan="2">{f3(gall["podium_ll_model"], 4)} / <b>{f3(gall["podium_ll_outlook"], 4)}</b> / {f3(gall["podium_ll_book"], 4)}</td><td class="num" colspan="2">{f3(TG["podium_ll_model"], 4)} / <b>{f3(TG["podium_ll_outlook"], 4)}</b> / {f3(TG["podium_ll_book"], 4)}</td></tr>
  </table></div>
  <p class="caption">Same defect, two races. The blend's ordering of the GC does not learn from the race in either; the market's does. The outlook head was the best podium estimator on the board at both Grand Tours, market included, and both times it was displayed as a caption rather than used as the price.</p>
</section>

<!-- ================= tour vs vuelta ================= -->
<section id="compare">
  <div class="kicker">July against September</div>
  <h2>What changed between the two Grand Tours, and what did not</h2>
  <div class="tablewrap"><table class="cmp">
    <tr><th></th><th class="num">Tour</th><th class="num">Vuelta</th><th>Reading</th></tr>
    <tr><td>Winner market, model minus market (nats per stage)</td><td class="num neg">{sgn(tall["win_ll_delta"], 3)}</td><td class="num pos">{sgn(all_["win_ll_delta"], 3)}</td><td>From clearly behind to level.</td></tr>
    <tr><td>…on peloton / GC-settled days</td><td class="num">{sgn(tpel["win_ll_delta"], 3)}</td><td class="num pos">{sgn(pel["win_ll_delta"], 3)}</td><td>From level to clearly ahead.</td></tr>
    <tr><td>…on break-won and hard-man days</td><td class="num neg">{sgn(tbw["win_ll_delta"], 2)}</td><td class="num neg">{sgn(P["break_won_only"]["win_ll_delta"], 2)} / {sgn(hm["win_ll_delta"], 2)}</td><td>Still behind; a third of the cost, because the market was blind too.</td></tr>
    <tr><td>Market's own winner log loss</td><td class="num">{f3(tall["win_ll_book"])}</td><td class="num">{f3(all_["win_ll_book"])}</td><td>A far less predictable race for everyone.</td></tr>
    <tr><td>Top-15 overlap, model minus market</td><td class="num pos">{pp(tall["overlap"]["15"]["delta_pp"])}</td><td class="num neg">{pp(all_["overlap"]["15"]["delta_pp"])}</td><td>Depth advantage lost, mostly on escape days.</td></tr>
    <tr><td>Top-end shyness on the winner head</td><td class="num">yes</td><td class="num">mostly gone</td><td>Depth heads now over-confident instead.</td></tr>
    <tr><td>Days the model beat the market</td><td class="num">{sum(1 for r in A["tdf_per_stage"] if r["delta_nats"] > 0)} of {tall["n"]}</td><td class="num">{n_ahead} of {n_stages}</td><td></td></tr>
    <tr><td>Best single day</td><td class="num">{max(r["delta_nats"] for r in A["tdf_per_stage"]):+.2f} <span class="muted">(Evenepoel, st 15)</span></td><td class="num">{best3[0]["delta_nats"]:+.2f} <span class="muted">({SHORT_WINNER.get(best3[0]["winner"])}, st {best3[0]["stage"]})</span></td><td>Both: the market typecast a rider by discipline, and class won.</td></tr>
    <tr><td>Worst single day</td><td class="num">{min(r["delta_nats"] for r in A["tdf_per_stage"]):+.2f} <span class="muted">(Carapaz, st 20)</span></td><td class="num">{worst3[0]["delta_nats"]:+.2f} <span class="muted">({SHORT_WINNER.get(worst3[0]["winner"])}, st {worst3[0]["stage"]})</span></td><td>Both: an escape the model could not see.</td></tr>
    <tr><td>GC blend, rank correlation with the final GC (market)</td><td class="num">{f3(TG["spearman_model"], 2)} <span class="muted">({f3(TG["spearman_book"], 2)})</span></td><td class="num">{f3(gall["spearman_model"], 2)} <span class="muted">({f3(gall["spearman_book"], 2)})</span></td><td>The frozen GC board, twice.</td></tr>
    <tr><td>Mornings missed</td><td class="num">none <span class="muted">(the stage 1 team time trial was not previewed by design)</span></td><td class="num">3 of 20 raced</td><td>The process, not the model, cost three days of evidence.</td></tr>
  </table></div>
</section>

<!-- ================= directions ================= -->
<section id="directions">
  <div class="kicker">What we do about it</div>
  <h2>The programme this Vuelta wrote for us</h2>
  <p>In priority order, with the priority argued by the numbers above.</p>
  <div class="dirs">
    <div class="dir">
      <h3>Put the GC outlook head on the GC page, with a corrector over both heads</h3>
      <p>Two Grand Tours, same result: the blend's GC board does not move with the race, and the state-aware head that does was the best podium forecaster on the board both times, market included. After the abandon it matched the market on the winner ({f3(gpost["winner_ll_outlook"], 2)} against {f3(gpost["winner_ll_book"], 2)}) while the blend sat at {f3(gpost["winner_ll_model"], 2)}. Its weakness is over-concentration on two leaders, which is what the blend is good at. This is the clearest, most repeatable finding we have and the cheapest to act on. The first step was taken with this review: the <a href="vuelta-gc.html">GC tracker</a> now leads with the outlook head and shows the pre-race blend beside it for contrast. The corrector that combines the two is still to build.</p>
    </div>
    <div class="dir">
      <h3>Teach the key when the bunch lets the break go</h3>
      <p>The channel worked where the key was right and did nothing where it was wrong, and it was wrong on three of four mountain escapes. The rules that would have fixed those days are now written: ask who has a reason to chase, weight the composition of the move over the terrain, and treat the leader's own team in the break as the deciding fact. They need to be applied before a stage, not discovered after one.</p>
    </div>
    <div class="dir">
      <h3>Learn to weight our own reads</h3>
      <p>The best of our morning reads found {best15} of the actual top fifteen across the race, more than the market's {book15}; the published average found {pub15:.0f}. The Tour said the same thing in probability terms. The scenario structure holds more information than we publish, and the missing piece is a weighting over reads that can be set in the morning and scored in the evening, which is what the day key was supposed to become.</p>
    </div>
    <div class="dir">
      <h3>Calibrate against the current race, not a July constant</h3>
      <p>The Tour said sharpen; the Vuelta said leave it alone. The depth heads went from shy to over-confident as the field thinned. A fixed temperature fitted on one race is the wrong instrument. What is needed is a calibration that sees the state of the field it is pricing, starting with who has already left the race.</p>
    </div>
    <div class="dir">
      <h3>Escape membership remains the structural hole</h3>
      <p>Every break-won day this race had the same signature: the winner at or near 50th on every board, including the hindsight run given the day's real shape, and the market not much better. Handing the model the day's shape has now failed to find the escape winner on {A["hindsight"]["n"] - A["hindsight"]["beat_best"]} of {A["hindsight"]["n"]} hindsight runs against the best morning read. Course knowledge is not the constraint; a model of who gets in the move is. The Vuelta added five labelled instances with full gap curves and prices to the Tour's four.</p>
    </div>
    <div class="dir">
      <h3>Do not miss mornings</h3>
      <p>Three of twenty raced stages have no scored read because the daily cycle was not run. The shadow agent kept its key on one of them and was exact. The agent's live record is short but clean, and the cost of a missed day is a day of evidence that cannot be recovered. The unattended cycle exists; the next campaign should run on it.</p>
    </div>
  </div>
  <p>A closing note in the same spirit as July's. The story we expected to tell coming into this race was that the day key would show up as a measurable improvement on the hard days. It did not, and the same records that would have shown the improvement show exactly why not. The story we did not expect was that the model would be level with the market on winners and ahead on ordinary days by a clear margin, and that our best single days would come from refusing the market's breakaway cards on stages where the strongest rider simply rode away. We only know either of those things because <a href="vuelta-stages.html">every read</a>, <a href="vuelta-gc.html">every board</a> and every key was written down before the road answered.</p>
</section>

<div class="footer">
  Assembled 2026-09-13 from the archived daily artefacts: pre-stage predictions logged to <code>prediction_log</code>, morning odds captures (devigged Unibet/Kambi), evening results, and the day-key scorecard.
  Model boards renormalized to market mass before every comparison; market boards floor-filled over unlisted starters and devigged; GC boards paired with the market snapshot that knew the same stages.
  Every number on this page is reproducible from <code>build_review_dataset.py --campaign performance_eval/vuelta-2026</code> and the two scripts in <code>performance_eval/vuelta-2026/review/</code>.
  &nbsp;·&nbsp; <a href="index.html">System overview</a> &nbsp;·&nbsp; <a href="vuelta-stages.html">Vuelta stage diary</a> &nbsp;·&nbsp; <a href="vuelta-gc.html">Vuelta GC tracker</a> &nbsp;·&nbsp; <a href="review.html">The Tour review</a>
</div>

</div>
<!-- built by performance_eval/vuelta-2026/review/build_review_page.py from review/analysis.json -->
</body>
</html>
"""

# typographic minus in every rendered number (CSS and SVG are untouched)
import re
head, body = html.split("</style>", 1)
body = re.sub(r"(?<=[>\s(])-(?=\d)", "\u2212", body)
html = head + "</style>" + body
OUT.write_text(html)
print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1024:.0f} KB)")
