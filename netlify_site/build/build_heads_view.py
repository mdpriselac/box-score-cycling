"""Build the head-vs-head view from tdf_heads_analysis.json; splice between
<!-- HEADS:BEGIN --> / <!-- HEADS:END --> in predictor-architecture.html."""

import json
import re
from html import escape
from pathlib import Path

HERE = Path(__file__).parent
A = json.loads((HERE / "tdf_heads_analysis.json").read_text())
PRED = json.loads((HERE / "tdf_2026_predictions.json").read_text())
PAGE = HERE / "predictor-architecture.html"

SHORT = {"gc": "GC", "flat_sprint": "Flat sprint", "reduced_sprint": "Reduced sprint",
         "punchy": "Punchy", "mountain": "Mountain", "tt30": "TT ~30 min",
         "queen": "Queen stage"}

def pct(v, dec=1):
    return "–" if v is None else f"{100*float(v):.{dec}f}"

# ---- concentration table ----
book = A["notes"]["book_gc_shape"]
gc_book_sum = PRED["scenarios"]["gc"]["mc_win_book"]
conc_rows = []
for s in A["shape"]:
    conc_rows.append(
        "<tr>"
        f'<td class="nm">{SHORT[s["key"]]}</td>'
        f'<td class="num">{pct(s["cascade"]["top3"], 0)}</td>'
        f'<td class="num">{s["cascade"]["eff_n"]:.1f}</td>'
        f'<td class="num">{pct(s["lr"]["top3"], 0)}</td>'
        f'<td class="num">{s["lr"]["eff_n"]:.1f}</td>'
        + (f'<td class="num hl">{pct(book["top3"], 0)}</td><td class="num hl">{book["eff_n"]:.1f}</td>'
           if s["key"] == "gc" else '<td class="num">–</td><td class="num">–</td>')
        + "</tr>")
CONC = f"""<div class="table-frame tdf-tf"><table class="tdf-table">
<thead><tr><th>Scenario</th>
<th class="num">Cascade top-3&nbsp;%</th><th class="num" title="exp(entropy) of the normalized win book — how many riders effectively share it">Cascade eff.&nbsp;contenders</th>
<th class="num">LR top-3&nbsp;%</th><th class="num">LR eff.&nbsp;contenders</th>
<th class="num">Book top-3&nbsp;%</th><th class="num">Book eff.&nbsp;contenders</th></tr></thead>
<tbody>{''.join(conc_rows)}</tbody></table></div>"""

# ---- bands table ----
band_rows = "".join(
    "<tr>"
    f'<td class="nm">{escape(b["band"])}<span class="tm">{b["n"]} riders</span></td>'
    f'<td class="num hl">{pct(b["book"])}</td>'
    f'<td class="num">{pct(b["cascade"])}</td>'
    f'<td class="num">{pct(b["lr"])}</td>'
    f'<td class="num">{pct(b["blend"])}</td>'
    "</tr>" for b in A["gc_bands"])
BANDS = f"""<div class="table-frame tdf-tf"><table class="tdf-table">
<thead><tr><th>Odds band</th><th class="num">Book&nbsp;%</th>
<th class="num">Cascade&nbsp;%</th><th class="num">LR&nbsp;%</th><th class="num">Blend&nbsp;%</th></tr></thead>
<tbody>{band_rows}</tbody></table></div>"""

# ---- referee table ----
ref = A["referee"]
dis_rows = []
for d in A["disagreements"][:10]:
    side = d["book_sides_with"]
    dis_rows.append(
        "<tr>"
        f'<td class="nm">{escape(d["rider"])}<span class="tm">book odds {d["book_odds"]:g}</span></td>'
        f'<td class="num hl">{pct(d["book"])}</td>'
        f'<td class="num">{pct(d["cascade_n"])}</td>'
        f'<td class="num">{pct(d["lr_n"])}</td>'
        f'<td class="sc"><span class="sidechip side-{side}">{"Cascade" if side == "cascade" else "LambdaRank"}</span></td>'
        "</tr>")
REFEREE = f"""<div class="table-frame tdf-tf"><table class="tdf-table">
<thead><tr><th>Rider</th><th class="num">Book&nbsp;%&nbsp;(devig)</th>
<th class="num" title="Cascade win book normalized to sum to 1 over the 40 priced riders">Cascade&nbsp;%</th>
<th class="num">LR&nbsp;%</th><th>Book sides with</th></tr></thead>
<tbody>{''.join(dis_rows)}</tbody></table></div>"""

# ---- spearman table ----
sp_rows = "".join(
    "<tr>"
    f'<td class="nm">{SHORT[s["key"]]}</td>'
    f'<td class="num">{s["cascade_lr"]:.2f}</td>'
    f'<td class="num{" hl" if s["bucket_timegap"] < 0.5 else ""}">{s["bucket_timegap"]:.2f}</td>'
    f'<td class="num">{s["cascade_elo"]:.2f}</td>'
    "</tr>" for s in A["spearman"])
SPEAR = f"""<div class="table-frame tdf-tf"><table class="tdf-table">
<thead><tr><th>Scenario</th><th class="num" title="Rank correlation between the two probability heads">Cascade&nbsp;~&nbsp;LR</th>
<th class="num" title="Rank correlation between the bucket head and the time-gap head">Bucket&nbsp;~&nbsp;Stopwatch</th>
<th class="num" title="Rank correlation between cascade win prob and contested Elo">Cascade&nbsp;~&nbsp;Elo</th></tr></thead>
<tbody>{sp_rows}</tbody></table></div>"""

# ---- dnf table ----
dnf_rows = "".join(
    "<tr>"
    f'<td class="nm">{SHORT[d["key"]]}</td>'
    f'<td class="num">{pct(d["mean_dnf"])}</td>'
    f'<td class="num">{pct(d["max_dnf"])}</td>'
    f'<td class="num">{d["mountain_score"]:.2f}</td>'
    "</tr>" for d in A["dnf"])
DNF = f"""<div class="table-frame tdf-tf"><table class="tdf-table">
<thead><tr><th>Scenario</th><th class="num">Mean&nbsp;DNF&nbsp;%</th>
<th class="num">Max&nbsp;DNF&nbsp;%</th><th class="num">Mountain score (input)</th></tr></thead>
<tbody>{dnf_rows}</tbody></table></div>"""

html = f"""
<section class="col">
  <p class="kicker">Same field, seven opinions</p>
  <h2>How the heads disagree with each other</h2>
  <p>Every head saw identical inputs on 3 July — the same 184 riders, the same form, the same course profiles. Whatever differs between their outputs is pure architecture: what each head was trained to predict, over which population, with which loss. The Tour runs give us seven parallel experiments, and for GC the devigged book acts as an outside referee.</p>
</section>

<section class="col tdf-scenario">
  <h3 class="tdf-h">Finding 1 — nobody here is as sure as the market</h3>
  <p class="tdf-blurb">"Effective contenders" = exp(entropy) of a win book: how many riders meaningfully share it. Top-3 % = probability mass on the three favorites.</p>
  <div class="wide">{CONC}</div>
  <p style="margin-top:14px">The headline surprise: the two heads' famous disagreement mostly <em>isn't about shape</em>. Force the cascade's quotes into a coherent book (they sum to {gc_book_sum:.2f} on GC — it's a per-rider conditional head, not a book) and it spreads the race across ~11 effective contenders, almost exactly like LambdaRank. The bookmaker spreads it across <strong>4.4</strong>. The cascade's per-rider quote on Pogačar (62.7%) matches the book's 63.0% — but it achieves that while also quoting everyone else generously, which a coherent book can't do. So the deep systematic pattern is not "cascade sharp, LR flat"; it's <strong>both heads hedge harder than the market</strong>, and the cascade hides it in an inflated book.</p>
</section>

<section class="col tdf-scenario">
  <h3 class="tdf-h">Finding 2 — where our probability mass goes instead</h3>
  <p class="tdf-blurb">GC win probability, grouped by the book's own odds bands (all books normalized over the same 40 priced riders).</p>
  <div class="wide">{BANDS}</div>
  <p style="margin-top:14px">Every head makes the same two transfers, in the same direction: out of the top two favorites (book 78.6%, ours ~47–54%) and into the 10–50 band and the extreme tail. The middle-band excess is mostly the <em>information gap</em> — Evenepoel and Lipowitz live there, and our heads don't know what the market knows. The tail excess (11% vs 4.7% on 200/1+ shots) is the models' trained caution: three-week races have delivered enough chaos in the training data that no head will zero out 30 riders the way a bookmaker will. Note how uniform the three columns are — this is a property of the <em>stack</em>, not of any one head.</p>
</section>

<section class="col tdf-scenario">
  <h3 class="tdf-h">Finding 3 — when the heads argue, the market referees</h3>
  <p class="tdf-blurb">The ten biggest cascade-vs-LambdaRank gaps on GC, with the book's verdict on each.</p>
  <div class="wide">{REFEREE}</div>
  <p style="margin-top:14px">Score it across the whole market and the split is clean: among favorites and contenders (odds ≤ 50) the book sides with the <strong>cascade {ref["favorites_cascade"]} times out of {ref["favorites_total"]}</strong>; among longshots it sides with <strong>LambdaRank {ref["tail_total"] - ref["tail_cascade"]} times out of {ref["tail_total"]}</strong>. That is the two-head design thesis — sharp head for the top, calibrated head for the field — endorsed by an independent market. It's also exactly the split the pricing layer already encodes: the corrector fixes the cascade at the top, while the blend leans 80% on LambdaRank everywhere else.</p>
</section>

<section class="col tdf-scenario">
  <h3 class="tdf-h">Finding 4 — the heads agree on <em>who</em>, argue about <em>how much</em></h3>
  <p class="tdf-blurb">Rank correlation (Spearman) between heads, per scenario. 1.00 = identical ordering.</p>
  <div class="wide">{SPEAR}</div>
  <p style="margin-top:14px">Cascade and LambdaRank order the field near-identically everywhere (0.91–0.96) — their disagreement is magnitude, never ranking. The interesting column is the middle one: the bucket head and the time-gap head agree almost perfectly on mountain days and time trials (0.87–0.96) and <strong>decouple completely on sprint days (0.23–0.30)</strong>. That's physics, not a bug: in a bunch sprint the entire peloton records the same finishing time, so "seconds behind the winner" stops encoding finishing order — the stopwatch goes blind exactly when the sorter still sees fine. It's the clearest demonstration in the data that the heads measure different physical quantities, which is why stacking them as features works. Elo, meanwhile, is the <em>least</em> redundant signal in the stack: rank agreement with the cascade of only 0.37–0.56, highest on the sprint-and-punchy profiles where finishes are literally contested duels (which is what Elo counts) and lowest on time trials, where nothing is. Low redundancy is exactly why it earned its place as a feature.</p>
</section>

<section class="col tdf-scenario">
  <h3 class="tdf-h">Finding 5 — the DNF head is the only one that changes level, not allocation</h3>
  <p class="tdf-blurb">Every other head redistributes ~1.0 of win probability between riders. The DNF head's output moves with the scenario itself.</p>
  <div class="wide">{DNF}</div>
  <p style="margin-top:14px">Single stages barely register (0.2–0.6% mean — you rarely abandon on the day itself), the time trial is the safest of all, and the GC scenario jumps to <strong>7.3% mean</strong> with individual riders above 20% — because finishing a three-week race is a genuinely different proposition than finishing a Tuesday. This is why DNF multiplication lives at the pricing layer: it's a per-scenario survival discount, orthogonal to the who-beats-whom question every other head answers.</p>
</section>

<section class="col tdf-scenario">
  <h3 class="tdf-h">The systematic patterns, in one list</h3>
  <div class="example">
    <ol>
      <li><strong>Both probability heads hedge harder than the market.</strong> ~11 effective GC contenders for us, 4.4 for the book. The cascade's sharp top quote coexists with an inflated book (sum {gc_book_sum:.2f}); as a coherent book it's as flat as LambdaRank.</li>
      <li><strong>The mass we shave off favorites goes two places</strong>: the 10–50 odds band (mostly the Evenepoel/Lipowitz information gap) and the extreme tail (trained three-week-chaos caution the book doesn't share).</li>
      <li><strong>The market endorses the two-head split</strong>: cascade closer to the book at the top ({ref["favorites_cascade"]}/{ref["favorites_total"]}), LambdaRank closer in the tail ({ref["tail_total"] - ref["tail_cascade"]}/{ref["tail_total"]}) — the corrector-plus-blend pricing layer already implements exactly this.</li>
      <li><strong>Ordering is consensus, magnitude is contested.</strong> Cascade~LR rank agreement is 0.92+ in every scenario; every visible disagreement is about confidence, not ranking.</li>
      <li><strong>The time-gap head goes blind on sprint days</strong> (rank agreement with the bucket head: ~0.95 in the mountains, ~0.25 in sprints) — same-time bunch finishes carry no gap signal. Its stack-feature value is concentrated on selective terrain.</li>
      <li><strong>DNF is a level, not an allocation</strong>: ~0.4% on a stage, 7.3% over three weeks — the only head whose scenario response is about survival rather than hierarchy.</li>
    </ol>
  </div>
</section>
"""

page = PAGE.read_text()
pattern = re.compile(r"<!-- HEADS:BEGIN -->.*?<!-- HEADS:END -->", re.S)
if not pattern.search(page):
    raise SystemExit("HEADS markers not found")
PAGE.write_text(pattern.sub(lambda m: "<!-- HEADS:BEGIN -->" + html + "<!-- HEADS:END -->", page))
print(f"Spliced {len(html)/1024:.0f} KB heads view")
