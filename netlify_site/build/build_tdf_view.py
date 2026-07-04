"""Build the TdF-2026 view HTML from tdf_2026_predictions.json and splice it
into predictor-architecture.html between <!-- TDF:BEGIN --> / <!-- TDF:END -->."""

import json
import re
from html import escape
from pathlib import Path

HERE = Path(__file__).parent
DATA = json.loads((HERE / "tdf_2026_predictions.json").read_text())
PAGE = HERE / "predictor-architecture.html"

SCORE_KEYS = [
    ("race_sprint_score", "Sprint"),
    ("race_mountain_score", "Mountain"),
    ("race_hilly_score", "Hilly"),
    ("race_rolling_score", "Rolling"),
    ("race_breakaway_score", "Breakaway"),
    ("race_time_trial_score", "Time trial"),
]

ORDER = ["gc", "flat_sprint", "reduced_sprint", "punchy", "mountain", "tt30", "queen"]

BLURBS = {
    "gc": "Final overall standings after three weeks. References: the last five Tour GC outcomes (2021–2025), so the model prices the yellow jersey the way those editions actually resolved.",
    "flat_sprint": "Pan-flat run-in, full bunch gallop. Built from stages the model itself scores as pure sprint (score 1.0): Cavendish, Philipsen and Merlier wins.",
    "reduced_sprint": "Enough lumps to drop half the fast men — a sprint, but from a thinned group of durable sprinters and classics riders.",
    "punchy": "Short steep finish or spiky final hour — Mur-de-Bretagne, Bologna, Rouen. In the model's inputs these read as rolling stages with moderate mountain score; the puncheur signal comes from rider-course fit, not the course score alone.",
    "mountain": "A real summit finish (Luz Ardiden, Cauterets, Pla d'Adet, Hautacam-style) at standard length. GC riders decide it.",
    "tt30": "A ~30-minute individual race against the clock, from the Tour's recent mid-length TTs.",
    "queen": "The hardest day of the race: 4–5 hours, multiple giant passes — double Ventoux, Granon, Col de la Loze, Bonette.",
}

def fmt_pct(v, dec=1):
    if v is None:
        return "–"
    return f"{100*float(v):.{dec}f}"

def fmt_elo(v):
    return "–" if v is None else f"{float(v):,.0f}"

def profile_bars(profile):
    parts = []
    vals = {k: (profile.get(k) or 0.0) for k, _ in SCORE_KEYS}
    dom = max(vals, key=vals.get)
    for k, label in SCORE_KEYS:
        v = vals[k]
        cls = "pbar-fill dom" if k == dom and v > 0 else "pbar-fill"
        parts.append(
            f'<div class="pbar-row"><span class="pbar-label">{label}</span>'
            f'<span class="pbar"><span class="{cls}" style="width:{max(2, round(100*v))}%"></span></span>'
            f'<span class="pbar-val">{v:.2f}</span></div>'
        )
    return '<div class="pbars">' + "".join(parts) + "</div>"

def ref_chips(refs):
    chips = []
    for r in refs:
        name = r["name"].replace("Tour de France - ", "")
        year = (r.get("date") or "")[:4]
        chips.append(f'<span class="refchip">{escape(name)} · {year}</span>')
    return '<div class="refchips">' + "".join(chips) + "</div>"

def rider_table(riders, n, gc=False):
    riders = sorted(riders, key=lambda r: (r.get("blend_win_p") or 0), reverse=True)
    rows = []
    for r in riders[:n]:
        name = escape(str(r.get("rider_name") or ""))
        team = escape(str(r.get("team_name") or ""))
        star = "★ " if r.get("is_contender") else ""
        rows.append(
            "<tr>"
            f'<td class="rk">{int(r["predicted_rank"])}</td>'
            f'<td class="nm">{star}{name}<span class="tm">{team}</span></td>'
            f'<td class="num hl">{fmt_pct(r.get("blend_win_p"))}</td>'
            f'<td class="num">{fmt_pct(r.get("prob_win"))}</td>'
            f'<td class="num">{fmt_pct(r.get("lambdarank_win_p"))}</td>'
            f'<td class="num">{fmt_pct(r.get("prob_podium"))}</td>'
            f'<td class="num">{fmt_pct(r.get("prob_top5"))}</td>'
            f'<td class="num">{fmt_pct(r.get("dnf_p"))}</td>'
            f'<td class="num">{fmt_pct(r.get("dnf_adj_win_p"))}</td>'
            + (f'<td class="num">{fmt_elo(r.get("contested_rating"))}</td>' if gc else "")
            + "</tr>"
        )
    elo_h = '<th class="num" title="Contested-comparison Elo rating">Elo</th>' if gc else ""
    return f"""<div class="table-frame tdf-tf"><table class="tdf-table">
<thead><tr><th></th><th>Rider</th>
<th class="num" title="0.2 x cascade + 0.8 x LambdaRank, book-preserving">Blend&nbsp;Win&nbsp;%</th>
<th class="num" title="Contender cascade, win corrector applied">Win&nbsp;%</th>
<th class="num" title="Full-field LambdaRank book">LR&nbsp;Win&nbsp;%</th>
<th class="num">Podium&nbsp;%</th><th class="num">Top&nbsp;5&nbsp;%</th>
<th class="num" title="P(does not finish | starts)">DNF&nbsp;%</th>
<th class="num" title="Win x P(finish), win book preserved">Honest&nbsp;Win&nbsp;%</th>{elo_h}</tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>"""

def scenario_block(key, s):
    gc = key == "gc"
    n = 15 if gc else 10
    riders = s["riders"]
    label = escape(s["label"])
    blurb = BLURBS.get(key, "")
    book = s.get("mc_win_book")
    p = s["avg_profile"]
    wt = p.get("winning_time")
    wt_txt = f"{wt/60:.0f} min" if wt else "–"
    ab = p.get("abandon_ratio")
    ab_txt = f"{100*ab:.1f}%" if ab is not None else "–"
    meta_bits = (
        f'<span>dominant: <b>{escape(str(p.get("race_dominant_profile")))}</b></span>'
        f'<span>ref winning time: <b>{wt_txt}</b></span>'
        f'<span>ref abandon rate: <b>{ab_txt}</b></span>'
        f'<span>cascade win book: <b>{book:.2f}</b></span>'
    )
    return f"""
<section class="col tdf-scenario" id="tdf-{key}">
  <h3 class="tdf-h">{label}</h3>
  <p class="tdf-blurb">{blurb}</p>
  <div class="wide tdf-grid">
    <div class="tdf-side">
      <p class="tdf-side-h">The archetype, as the model sees it</p>
      {profile_bars(p)}
      <div class="tdf-meta">{meta_bits}</div>
      <p class="tdf-side-h" style="margin-top:14px">Built from</p>
      {ref_chips(s["references"])}
    </div>
    <div class="tdf-main">{rider_table(riders, n, gc=gc)}</div>
  </div>
</section>"""

def build():
    sl = DATA["startlist"]
    blocks = "".join(scenario_block(k, DATA["scenarios"][k]) for k in ORDER
                     if k in DATA["scenarios"])
    html = f"""
<section class="col">
  <p class="kicker">Tour de France 2026</p>
  <h2>The startlist, priced seven ways</h2>
  <p>These are live predictions from the production stack, generated on <strong>3 July 2026</strong> from the official startlist ({sl['riders']} riders, {sl['teams']} teams; {sl['matched']} matched to the database). One general-classification forecast, plus the same field run through six <em>stage archetypes</em> — hypothetical stage profiles built by averaging real Tour stages from 2021–2025 that the model itself scores as that type of day.</p>
  <p class="note"><b>Read it honestly:</b> archetypes are course profiles, not the actual 2026 route — think "if Wednesday is a pure bunch-sprint day, here's the board." The database is current through 21 June 2026 — Giro, Tour de Suisse, and (after a same-day backfill) the full rebranded Dauphiné are all in; these boards were regenerated on 3 July with that complete picture. ★ marks the model's top-15 contender gate. Model estimates, not betting advice.</p>
</section>
{blocks}
<section class="col">
  <p class="kicker">Reading notes</p>
  <h3 class="tdf-h" style="margin-top:0">Why the boards look different per archetype</h3>
  <p>Only two things change between scenarios: the course profile fed to the models (the bars on each card) and the stage-context the DNF head sees. The startlist, every rider's form, Elo, and team context stay identical — so the differences between boards are purely the model's view of <em>rider-course fit</em>. The win books also behave differently by design: the cascade's book is unconstrained (it's a per-rider conditional head), widest on open sprint days and most concentrated when one rider dominates a profile.</p>
</section>
"""
    page = PAGE.read_text()
    pattern = re.compile(r"<!-- TDF:BEGIN -->.*?<!-- TDF:END -->", re.S)
    replacement = "<!-- TDF:BEGIN -->" + html + "<!-- TDF:END -->"
    if not pattern.search(page):
        raise SystemExit("TDF markers not found in page")
    PAGE.write_text(pattern.sub(lambda m: replacement, page))
    print(f"Spliced {len(html)/1024:.0f} KB of TdF view into {PAGE.name}")

if __name__ == "__main__":
    build()
