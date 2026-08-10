# Tour de France 2026 — comparative review: model vs book vs road

Materials assembled 2026-07-27 from the archived daily artefacts. Written to be
readable without a betting or machine-learning background — the **Terms** section
below defines every technical word used, and the findings are self-contained
after it.

Rebuild with:

```bash
uv run python performance_eval/tour-de-france-2026/build_review_dataset.py
```

## The four tables

| File | Grain | What it holds |
|---|---|---|
| `stage_riders.csv` | stage × scenario × rider (13,909 rows) | every model head (`prob_*`, `lambdarank_win_p`, `blend_win_p`, `dnf_*`), depth heads renormalized to market mass (`podium_norm`, `top5_norm`, `top15_norm`), the devigged book win + podium prices, and the rider's actual finish (`place`, `gap`, `in_top3/5/10/15`) |
| `stage_metrics.csv` | stage × scenario (80 rows) | winner pricing, win- and podium-market log loss + Brier for model / LambdaRank / book, top-k overlap and mean board rank at k = 3/5/10/15, Spearman vs the finish order, top picks |
| `gc_daily.csv` | state-through-stage × rider (3,126 rows) | the logged GC board after each stage, that morning's devigged book GC win/podium/top-10 prices, and the rider's final GC place |
| `gc_metrics.csv` | state-through-stage (18 rows) | the same depth scoring for each daily GC board against the final classification |
| `gc_final.csv` | final GC row (184) | final standings joined to the last model board + book board |

Coverage: stages 2–21 (stage 1 was a TTT and was never previewed), 57 published
reads + 20 hindsight runs + 3 hidden classification anchors. GC: 18 daily boards
(stage 12 has no separate board — the runner reused stage 11 state).

### Reading rules baked into the tables

- **`blend_win_p` is not a distribution.** Every book comparison uses
  `blend_win_norm` = `blend_win_p / Σ blend_win_p`; raw columns are kept only for
  reference. `book_devig_norm` is likewise renormalized over the *predicted*
  field, so the two sum to 1 over the same riders.
- Three riders were renamed by FirstCycling mid-Tour (Gee→Gee-West,
  Martin→Martin-Guyonnet, Plapp Lucas/Luke); `NAME_ALIASES` in the builder
  resolves them. Remaining unmatched predicted riders are genuine same-day
  DNF/DNS and carry `finished=0`.
- The 2026-07-25 odds capture archived only the stage-21 market, so the GC board
  through stage 20 is scored against the 2026-07-24 book (`book_date` column).
- Hindsight rows were never logged and are flagged `is_hindsight=1` — keep them
  out of any settlement number.
- **Depth markets.** The book prices win + podium on 18 of 20 stages (6 and 7
  have no podium market) and win + podium + top-10 on GC. There is no book
  top-5/top-15 market, so those depths are compared by **odds ordering** —
  top-k overlap, mean board rank, Spearman — which works at every depth and is
  the fairest apples-to-apples framing anyway.
- The book lists 92–142 of the ~170 starters. Unlisted riders are floor-filled at
  the longest price on that board (not zero, which would blow up any log loss the
  moment an unlisted rider placed) and flagged `book_*_listed=0`; the whole field
  is then rescaled to the market's mass.

## Terms used below

Plain-English glossary, for reading the findings without a betting or ML
background. Nothing here is project-specific jargon except where noted.

**The book** — the bookmaker's odds (here Unibet/Kambi), used as the benchmark
"expert" forecast. Beating the book is a high bar: it aggregates the opinions of
everyone willing to bet money.

**Devigged / devig** — raw bookmaker odds are deliberately inflated so the book
profits whatever happens; the implied chances add up to ~140–150% rather than
100%. "Devigging" strips that margin out so the prices become honest
probabilities we can compare against. Always use the devigged numbers.

**Log loss** — the standard score for a probability forecast. You are penalised
by how surprised you were by what actually happened: `−log(probability you gave
the thing that occurred)`. Confidently right scores near 0; confidently wrong
scores very badly. **Lower is better.** It punishes overconfidence hard, which is
why it is the honest test of a forecast rather than just counting winners.

**Nats** — the unit log loss comes in (from "natural logarithm"). Only
differences matter, not the absolute number. A gap of 0.1 nats per stage is
small; 0.46 is large. As a feel: giving the winner 10% instead of 20% costs you
0.69 nats on that stage.

**Brier score** — an alternative forecast score: average squared error between
the probability given and what happened (1 or 0). Lower is better. Less harsh on
confident mistakes than log loss.

**Calibration** — whether stated probabilities match reality in the long run. If
you say 30% on a hundred occasions, about 30 should happen. Saying 37% when the
true rate is 55% is *under-confident* — the ordering can still be perfect while
the numbers are wrong, and that turns out to be our main problem.

**Marginals, and why we renormalize** — our model produces each rider's chance
separately, so they don't add to 100% (they summed to 137–180%). A real
distribution must add up: exactly 1 winner, 3 podium places, 15 top-15 places.
So before any comparison we rescale our numbers to that total ("mass"). Skipping
this step flatters us systematically — it is the single easiest way to fool
yourself here.

**Top-k overlap** — a ranking check that needs no probabilities: of the riders
who actually finished in the top 10, how many were in your own top 10? Reported
as percentage points of model minus book.

**Spearman (rank correlation)** — how closely a predicted running order matches
the real finishing order across the whole field. 1.0 is perfect, 0 is random.

**Ex ante / post hoc** — before the event vs after it. A pattern you can only
identify afterwards is interesting; one you flagged beforehand can actually be
acted on. That distinction drives the most important section here.

**Precision and recall** — for a flag that fires on some days: precision is "when
it fired, was it right?", recall is "of the days it should have caught, how many
did it?". A flag can be perfectly precise and still miss most of the class.

**Abstention** — choosing not to bet (or not to publish confidently) on days your
forecast is likely to be weak. Sitting out is a legitimate strategy: avoiding
losses counts as much as making gains.

*Project-specific:* **heads** are the separate model components predicting
different things (winner, podium, top-5, top-15, likelihood of not finishing).
**Reads / scenarios** are the 3–4 alternative stories we published each morning
about how the day might unfold. **Hindsight runs** re-ran the model afterwards
knowing the day's actual shape, as a control for "would course knowledge have
saved us?" — they were never published or bet.

## First-cut findings

### Stages — the book wins overall, and it is not close

Average win-market log loss over the 20 previewed stages (lower is better).
*[Log loss = how surprised the forecast was by the actual winner; see Terms.]*

| Frame | Model | Book |
|---|---|---|
| Equal weight across the published reads (honest ex-ante) | **2.407** | **1.944** |
| Best read per stage, picked post-hoc (upper bound) | 2.129 | 1.944 |
| LambdaRank head, best read | 2.154 | — |

Even the post-hoc-best read loses by 0.19 nats/stage; the number we could
actually have published loses by 0.46. Scenario-level top-pick wins: book 34 of
57 reads, model 22.

### Depth — the deficit is concentrated at the sharp end, and vanishes by top-15

How many of the actual top k each board had in its own top k, summed over the 20
stages (model = its published reads averaged per stage, so this is the ex-ante
number, not a post-hoc pick). *[This is a pure ranking check — no probabilities
involved, so the book's margin and our un-normalized totals can't distort it.]*

| Depth | Model | Book | Delta |
|---|---|---|---|
| top 3 | 25.2 / 60 (42.1%) | 31 / 60 (51.7%) | **−9.6pp** |
| top 5 | 47.1 / 100 (47.1%) | 52 / 100 (52.0%) | −4.9pp |
| top 10 | 102.6 / 200 (51.3%) | 103 / 200 (51.5%) | −0.2pp |
| top 15 | 160.9 / 300 (53.6%) | 160 / 300 (53.3%) | **+0.3pp** |

Spearman against the actual finish order: model 0.507, book 0.532.

This substantially rewrites the headline. **The model's field-wide ordering is
already at book level** — it is level at ten deep and marginally ahead at fifteen.
The entire deficit lives in resolving the podium and the winner. On the podium
market itself (18 stages with a book price) mean per-rider log loss is model
0.0521 vs book 0.0459, the same gap in probability space. *[These podium numbers
are averaged across all ~170 riders rather than scored on one winner, so they sit
on a much smaller scale than the win-market figures above — compare them only
with each other, never against the 2.4 / 1.9 numbers.]*

That reframes the problem: we are not worse at reading a bike race, we are worse
at concentrating mass once the right ~15 riders have been identified.

### Two separable failure modes

**1. Under-confidence at the top of every head.** On days the model reads
correctly it still shades the top price down. Its blend caps out near 0.35–0.40
where the book goes 0.42–0.54 (stages 6, 8, 10, 12, 14, 16, 21). This is not a
win-market quirk — it repeats at every depth. Each cell reads *probability we
stated → rate it actually happened*; if we were calibrated the two would match.

| Head | 0.30–0.50 bucket | 0.50–0.75 bucket | 0.75+ |
|---|---|---|---|
| win (`blend_win_norm`) | 0.285 → 0.391 (0.20–0.35) | 0.381 → 0.400 (0.35+) | — |
| podium (`podium_norm`) | 0.373 → **0.545** | 0.591 → **0.729** | — |
| top-5 (`top5_norm`) | 0.377 → **0.582** | 0.635 → **0.821** | — |
| top-15 (`top15_norm`) | 0.384 → 0.442 | 0.595 → **0.745** | 0.778 → 0.895 |

Every head is under-confident above ~0.30 and slightly over-confident in the
long tail — a single monotone miscalibration, consistent across depths, on a
model whose ordering is fine. This is the cheapest thing on the list to fix and
the measured payoff is the largest.

**2. Days the model cannot reach at all.** Stages 4, 13, 18, 20 (and 9, 21):
the winner is priced 0.004–0.025 and the hindsight run — where the day's shape is
handed to the model for free — is *no better or worse*. Course knowledge is not
the constraint; these are break-formation, late-move and hard-man-sprint days.
This is the standing GT hard-day design hole, and the Tour supplied six labelled
instances of it.

Per-stage delta (nats, + = model beat the book), equal-weight frame.
*[Nats = the unit of log loss; ±0.1 is small, ±1.0 is a badly missed day.]*

```
+2.77  st15  Evenepoel on Solaison — the mountain-axis win
+0.41  st17   +0.37  st05   +0.30  st03   +0.10  st11   +0.09  st07
-0.16  st02   -0.21  st14   -0.35  st06   -0.36  st08   -0.40  st10   -0.45  st12
-0.79  st09   -1.21  st13   -1.26  st16   -1.68  st21   -1.75  st04
-2.05  st18   -2.62  st20
```

Stage 15 is the single biggest edge of the Tour and confirms the note in memory:
the book's "TT-shaped men can't win 9% walls" archetype broke, and the model was
on the right side of it.

### Excluding the GT hard-day class — what's left of the gap

`compare_by_class.py` reruns every panel with stage classes removed. The class is
defined by **day shape and winner type**, never by how we scored — excluding
stages because we did badly on them is circular. A useful check that the core set
is not cherry-picked: stage 17 is in it and was one of our *better* days (+0.41).

The class is five stages: **4, 9, 13, 17, 21**. Stage 2 is deliberately *not* in
it — the day shattered, but the thirteen who contested the finish were GC men
(del Toro from Pogačar, Vingegaard and Evenepoel). Selective GC day, not a
punchy-non-climber day.

| Panel | n | win LL m/b | podium LL m/b | top3 | top5 | top10 | top15 |
|---|---|---|---|---|---|---|---|
| all stages | 20 | 2.407/1.944 (−0.463) | .0521/.0459 (−.0061) | −10 | −5 | −0 | +0 |
| minus hard-day core {4,9,13,17} | 16 | 2.090/1.720 (−0.370) | .0454/.0408 (−.0046) | −6 | −1 | **+3** | **+3** |
| minus hard-day wide {4,9,13,17,21} | 15 | 2.032/1.749 (−0.283) | .0452/.0408 (−.0043) | −5 | −1 | **+3** | **+4** |
| minus all break-won days {13,17,18,20} | 16 | 2.029/1.793 (−0.237) | .0461/.0435 (−.0026) | −6 | +2 | +2 | +2 |
| **peloton/GC-settled days only** | 13 | **1.722/1.754 (+0.033)** | .0405/.0398 (−.0007) | −0 | **+5** | **+3** | **+4** |

(top-k columns are model-minus-book percentage points of the actual top k
captured in each board's own top k.)

Three things fall out.

**Removing the class narrows the gap but does not close it.** Win-market log
loss goes −0.463 → −0.370 → −0.283. Roughly 35–40% of our total deficit to the
book is those four or five days. The rest is spread across ordinary stages.

**Ordering flips decisively positive once the class is out.** At top-10 and
top-15 we go from level to +3 and +4 points ahead of the book. On the days
the model is designed for, its read of the front of the race is *better* than the
market's — that was invisible in the all-stages number because the hard days
dragged it to parity.

**The class the user named is a subtype of a bigger one: break-won days.** Pull
out every stage whose winner came from the escape — including the two *climbers'*
breaks (18, 20) that are explicitly not the hard-man class — and the gap narrows
similarly. Restrict to the 13 days settled by the peloton or the GC group and the
model **beats the book on the win market** (1.722 vs 1.754), matches it on podium,
and leads it by 3–5 points at every ordering depth.

So the honest summary is: *we price a bike race at or above market level whenever
the race is decided by the group we can see. We lose the Tour on the days a
breakaway decides it* — and the hard-man variant is the worst-priced part of that,
not the whole of it.

One caveat on the wide set: it adds stage 21 (−1.68), our fourth-worst day, whose
membership is arguable on shape (Montmartre finished in a reduced gallop, not a
break) and which carries its own asterisk (see below). The core-set row is the
more conservative read and is the one to quote.

### The carve that matters: ex ante, not post hoc

Every slice above shares a defect — membership is only known *after* the stage.
The hard-man GT class is different, and that is the point of naming it: **we
flagged those days in the previews, before they were raced.** Escape days in
general were not knowable that way (nothing in the stage-18 or stage-20 configs
says "a break will win this"), but the hard-man days were, and the flag is sitting
in the published config in machine-readable form.

Two ex-ante markers exist:

- **`HARDMAN_FLAGGED` = {4, 9, 17, 21}** — the day's published reads carried an
  explicit hard-man / late-move branch (`late_move`, `hard_mens_sprint`,
  `montmartre_move`). This is the class as we named it at the time.
- **`PUNCHY_MACHINERY` = {9, 11, 12, 17, 21}** — the config carried a
  `punchy_filter` block. Purely mechanical, but it conflates two different days:
  the hard-day punchy pool (9, 17, 21) and the flat-day mirror-image sprinter
  filter (11, 12).

| Ex-ante panel | n | win LL m/b | top3 | top5 | top10 | top15 |
|---|---|---|---|---|---|---|
| bet everything | 20 | 2.407/1.944 (−0.463) | −10 | −5 | −0 | +0 |
| **skip hard-man flagged {4,9,17,21}** | 16 | **2.256/1.915 (−0.341)** | −6 | −4 | +1 | +2 |
| skip punchy-filter days | 15 | 2.294/1.837 (−0.456) | −11 | −3 | −2 | +1 |
| skip either flag | 14 | 2.195/1.830 (−0.364) | −9 | −3 | −0 | +2 |
| *[post-hoc core, for contrast]* | 16 | *2.090/1.720 (−0.370)* | *−6* | *−1* | *+3* | *+3* |

As an abstention rule:

*[Read this as: how far below the book we ran on the days the flag fired, versus
the days it didn't. "Nats avoided" = total loss we would not have taken by
sitting those days out.]*

| Rule | n | mean delta on flagged days | on unflagged days | nats avoided |
|---|---|---|---|---|
| **hard-man flagged (ex ante)** | 4 | **−0.951** (3 of 4 below book) | −0.341 | **3.80** |
| punchy-filter (ex ante) | 5 | −0.482 (3 of 5) | −0.456 | 2.41 |
| post-hoc core | 4 | −0.834 (3 of 4) | −0.370 | 3.33 |

**The ex-ante flag is a better filter than the post-hoc carve.** Sitting out the
four days we had already named would have avoided 3.80 nats of the ~9.3 total
deficit — more than the post-hoc "core" set recovers (3.33) — while touching only
20% of the stages. Days we flagged ran −0.951 against the book; days we didn't ran
−0.341. That is a real, tradeable separation, and it was available at preview time.

The honest limits of it:

- **n = 4.** Three of the four went against us; one (stage 17, +0.41) is a day we
  would have skipped while actually beating the market. That is the cost of the
  policy, and at this sample it cannot be distinguished from noise with any
  confidence. Treat it as a hypothesis with a strong prior, not a proven edge.
- **The flag is high-precision, decent-recall.** All 4 flagged days were
  genuinely in the class — no false alarms — and of the five-stage class it
  missed only stage 13, whose reads were a mountain-break shape even though a
  hard man (Schmid) won it. It does not catch escape days in general (18, 20),
  but those were never claimed to be knowable in advance. Good abstention
  trigger; not a coverage measure for break-won days.
- **The `punchy_filter` marker is the worse of the two** — skipping those days
  barely helps (−0.456), because 11 and 12 were flat sprint days where we were
  fine. If this gets automated, key it on the hard-man/late-move read, not on the
  presence of the filter block.

### A note on stage 21

Stage 21 is structurally odd and should carry an asterisk in any aggregate: GC
times were taken at 47 km to go, so the closing circuits were contested by only
two or three teams and a handful of individuals with anything at stake. The field
that raced the finish is not the field we priced. It belongs in the hard-man class
by shape, but its −1.68 is partly a startlist artefact rather than a pure model
miss.

### Both corrections at once: hard days out, shyness fixed

`what_if_calibrated.py` applies the cheapest possible version of the calibration
fix — a one-parameter temperature transform `p' ∝ p^T`, which sharpens the top of
the board and thins the tail — and rescores. Every headline number is
**leave-one-stage-out**: `T` is fitted on the other stages and applied to the
held-out one, so no stage helps correct itself. *[A monotone transform cannot
reorder anything, so all the top-k overlap and Spearman numbers above are
unchanged by this — only the probabilities move.]*

| Panel | win LL: raw → calibrated | vs book | podium vs book | fitted T |
|---|---|---|---|---|
| all 20 stages | 2.407 → 2.394 | −0.463 → **−0.450** | −.0037 → −.0022 | 1.25 |
| **hard-man class out** | 2.032 → **1.954** | −0.283 → **−0.205** | −.0033 → **−.0005** | **1.40** |
| hard-man stages alone | 3.532 → 3.643 | −1.002 → **−1.113** | −.0047 → −.0068 | **1.00** |

**So: on ordinary racing days, with the shyness corrected, the model is a
genuinely competitive forecaster.** Within 0.2 nats of the book on the winner,
statistically level with it on the podium (−.0005), and *ahead* of it by 3–4
points at top-10 and top-15. That is the honest picture of what we built: on the
days it is designed for, it is at or above market standard at every depth except
the very sharp end, and even there the residual gap is small.

**The two fixes are not independent — the second is gated on the first.** Look at
the fitted temperatures. Ordinary days want T = 1.40 (sharpen hard). Hard days
want T = 1.00 (don't sharpen at all) and calibration makes them *worse*
out-of-sample. The model's shyness is not a bug uniformly — it is correct
behaviour on the days it cannot read, and a costly hedge everywhere else. A
single global temperature is a compromise between two regimes and is worth almost
nothing: −0.463 → −0.450 across all stages, which rounds to noise.

**And today's flag is not yet good enough to run the switch.** Using the ex-ante
`HARDMAN_FLAGGED` set to choose between the two temperatures gets the days-we'd-bet
number to −0.346, barely better than the −0.341 we already had. The per-stage
breakdown says exactly why: sharpening pays about +0.5 nats each on the ordinary
days (st 3, 6, 10, 14, 19), and gives it all back on the surprise-winner days the
flag does not catch — **st 13 alone costs −1.20** (in the class, missed by the
flag), st 20 −0.69, st 18 −0.60, st 11 −0.49.

**This reorders the priorities.** I initially called calibration the cheapest win
with the largest payoff; the honest cross-validated numbers say that is only true
*conditional on knowing what kind of day it is*. Calibration is worth ~0.08
nats/stage, but only on correctly-identified ordinary days. Day-class detection is
therefore not a separate project from calibration — it is the thing that unlocks
it. Improving the flag's recall (st 13, and the escape days generally) is now the
highest-leverage work on the list, because it pays twice: once by abstaining, once
by licensing confidence everywhere else.

### GC — right man, too little mass, and a board that never learns



The model had Pogačar top of the GC board on all 18 days and the final top 3 in
its top 4. But its win probability moved 0.360 → 0.468 across the whole race
while the book went 0.651 → 0.933. Average GC win log loss over the 18 boards:
model **0.969**, book **0.205**.

Depth tells the sharper story. Scored against the final classification, board by
board:

| | early (thru 2–9) | late (thru 14–20) |
|---|---|---|
| model, actual top-15 inside its top-15 | 9.2 | 10.9 |
| book, same | 10.5 | 12.9 |
| model Spearman vs final GC | 0.772 | 0.770 |
| book Spearman vs final GC | 0.822 | **0.933** |

**The model's GC ordering is frozen.** Its Spearman against the final
classification is 0.767–0.773 on every single one of the 18 boards — it ends the
Tour knowing no more about the finishing order than it did after stage 2, while
the book climbs from 0.81 to 0.98 as the race resolves. The win probability moves
just as little (0.360 → 0.468). Whatever within-race state reaches the GC blend,
it is not moving the board.

And the fix may already be in the building: the **GC outlook head is the best
podium estimator we have**, better than both the blend and the market.

| GC podium (mean per-rider log loss, 18 boards) | |
|---|---|
| `gc_outlook_*` renormalized | **0.0202** |
| book | 0.0299 |
| model blend | 0.0343 |

The outlook head is what the page currently relegates to a "position safety"
caption; on this evidence it is the sharper GC instrument at depth.

## Candidate directions (to be prioritised)

1. **Day-class detection, because it unlocks the calibration.** Formerly listed
   as two items; the cross-validated counterfactual shows they are one. Sharpening
   is worth ~0.08 nats/stage on correctly-identified ordinary days and is actively
   harmful on hard days (which want T = 1.00), so a global correction buys
   ~nothing (−0.463 → −0.450). The binding constraint is recall on the hard/
   surprise class: st 13 alone costs −1.20 when wrongly sharpened, and the escape
   days (18, 20) are not flagged at all. Improving detection pays twice — abstain
   where we're weak, and license confidence everywhere else.
2. **Top-end calibration, applied to every head, conditional on (1).** The
   miscalibration is one monotone curve and shows up identically on podium, top-5
   and top-15; ordinary days want T ≈ 1.40. The corrector already exists
   (`win_calibration.json`) but is win-only and was fit on the general corpus, not
   on GT boards. Ranking work is *not* indicated: at top-10 and top-15 we are
   already at or above book level.
3. **GC board responsiveness — the clearest standalone defect.** Model Spearman against
   the final GC is flat at 0.77 across all 18 boards while the book climbs to
   0.93. Find out what within-race state actually reaches the GC blend. Related:
   promote or blend in `gc_outlook_*`, which beats both the blend and the book on
   podium (0.0202 vs 0.0343 / 0.0299).
4. **An abstention / confidence flag, keyed on the hard-man read.** The one carve
   that is available *before* the stage separates −0.951 from −0.341 nats and
   would have avoided 3.80 of ~9.3 total deficit nats at 20% of the stages. It is
   n = 4 and needs more editions before it is an edge rather than a hypothesis,
   but it costs nothing to emit: the trigger already exists in the configs. The
   cheap first version is a published confidence tier on the day, not a model
   change.
5. **Break-won days, of which the GT hard-day class is the worst part.** The
   class slice says this is ~35–40% of the total deficit and that the boundary
   should be drawn at *"did an escape decide it"* rather than at the winner's
   rider type — the two climbers' breaks (18, 20) cost us just as much as the
   hard-man days. Labelled instances now exist with full gap curves, book prices
   and hindsight controls, and hindsight-is-no-better remains the strongest
   evidence that this needs a structural component (break membership / per-rider
   group ladders), not better day-typing.
6. **Scenario aggregation.** We publish 3–4 reads and never commit to a mixture.
   The gap between equal-weight (2.407) and post-hoc-best (2.129) is the value
   a learned or judgment-weighted prior over reads could recover — the day-shape
   labels for fitting it are in `results/stage_NN/`.
