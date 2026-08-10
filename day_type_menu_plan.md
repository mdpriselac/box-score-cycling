# Day-type menu & conditional rider representation — work order

**Date:** 2026-08-08 · **Status:** spec agreed, step 1 not yet run
**Predecessors:** front-local race typing / selection signatures (2026-06-11), GT hard-day investigation (post-Paris program, `performance_eval/tour-de-france-2026/review/`), deferred v7 characteristic-weighted form (2026-07-03).

## Objective

Fix contender **retrieval** on hard/selective stage days (TdF 2026 stages 4, 9, 21 class: Pedersen ranked 25, Schmid 37 — outside the model's own top-15) by giving stage rows the day-type vocabulary that one-day rows already have, without leaking outcome values into training. Secondary: upgrade rider-history summaries (form, Elo) from "did he contest" to "how does he fare on days like this one."

**Non-goals here:** break-membership modeling (parallel program — strongest single evidence, stage 20), top-end mass calibration (gated on day-class detection, per review), LLM layer (bracketed 2026-08-08).

## The architecture in one paragraph

Train a **conditional model**: P(outcome | day-type), where day-type is a **menu item** — a canonical pair of (contestant-composition signature, finishing-gap shape). At train time the label is the **hard best-fit assignment from the race's own realized front group** (coarse label; leak bounded), and the feature values filled in are the **menu item's canonical values, never the race's own**. At serve time the menu item is **selected** — by judgment (human/LLM reading parcours, news, weather, book card) or a mechanical prior — and uncertainty is handled by running the board once per plausible item and **mixing the output boards** under the prior. Judgment never trains anything; it only selects from the same menu the model was trained on. This is the TdF multi-read scenario workflow formalized into the training regime.

## Settled design decisions

1. **Hard own-assignment at train; soft forbidden.** Coarse cluster label from realized front group is the only outcome-derived input (June bound: label 49% recoverable from existing features, value-level 0.876 — same leak class as existing own-shape profile scores). Continuous/soft own-derived weights leak more and are banned (settled 2026-06-11).
2. **Borrowed canonical values only.** Feature fills come from the menu library (aggregates of *other* races). Sampling a member race vs. using the canonical aggregate is leak-equivalent for aggregate features; sampling is only required if positional features are ever fed (matrices saved in the June library artifacts).
3. **Sharp conditionals, hedge in the prior, mix boards not features.** For an uncertain day, run the model per menu item and mix outputs by prior weight. Never average signature vectors across items — for a tree model the midpoint of Flanders and bunch-sprint signatures is a third (wrong) conditional. Matches the review's calibration finding: hard days want wide boards because the *script prior* is wide, not because conditionals should be mushy.
4. **Match/cluster in contesting-composition space; shape rides along as canonical values.** WHO contests is ~2× more forward-predictable than front-group size (mean-of-priors r .739 vs .452), and gap-curve matching is what the hindsight runs did without profit.
5. **Gap-bounded contest window** (fixed top-K reaches past a 6-man break into the GC group on shattered days), K=15 fallback for bunch days. June re-gate guidance: K≥15, gap-bounded, per-race paired stats.
6. **Kernel direction: race-to-race only.** History weights compare *historical race signature ↔ target day signature* ("how did he do on days like this"). Never rider-expectation kernels ("how did he do on days like *him*") — those entrench archetype priors and erase exactly the Simmons class whose mechanism is hidden in bucket space. Realized contestation (informative-comparison membership) stays as the row filter — it's realized, not expected, which is why it works.
7. **Kernel target at train = the assigned menu item's canonical signature, never the race's own realized signature** (otherwise soft own-assignment leak returns through the back door).
8. **Three-tier evaluation, always labeled:** (i) *oracle* — true label at test: automatable ceiling; (ii) *mechanical prior* — reference-based today, book-card composition forward, course metadata later; (iii) *judgment prior* — measurable only where judgments were archived (TdF 2026 corpus; = plan item 0 read-selection eval), prospective after. Never headline oracle numbers.
9. **Gates:** hard-slice surfacing suite primary (pool recall@15, composition divergence, front-group membership P/R, per-race winner rank), `market_avg_log_loss` (honest frame, 5-fold) as global no-degradation guardrail. Per the 2026-07-11 program-scoped amendment.
10. **Everything gates ON TOP of the full production stack** (v5 lesson 2026-07-03: standalone sweeps ship redundant features; global contested Elo already carries the plain contesting signal).

## Step 1 — the survey (build the menu, test the premise)

**Question:** do hard/selective stage days actually resemble one-day races in composition space ("a hard-man day looks like a Flanders"), or are they their own animal (break-artist-heavy, stage-native)? Either answer shapes the menu.

**Inputs** (all exist):
- `experiments/selection_signatures_20260611_084046.csv.gz` — per-comp top-5/10/15 contesting archetype shares, winner archetype, field-relative enrichment (5,055 comps, stage+one_day, 2016+, ≥30 finishers).
- `experiments/front_local_comp_features_20260611_081558.csv.gz` — winner-group size/prop, margin, chase gap, top-15 spread/groups, frac_30s.
- `experiments/contest_archetype_{library,assignments}_20260611_093323.*` — GMM k=10 library + per-comp assignments + positional matrices.
- DB for comp metadata (race, year, stage number, category, profile scores).
- `performance_eval/tour-de-france-2026/review/` — validation rows.
- Verify exact column names on load; recompute signatures at K=15/gap-bounded if the artifacts only carry K=10 cleanly (script `selection_signatures.py` is re-runnable).

**Population:** stage comps only, 2016+, ≥30 finishers, exclude ITT/TTT-like (June `itt_like` class).

**Residual-class rule v0** (mechanical; thresholds face-validated against known days before freezing):
- OUT: mass/bunch sprints — winner-group size/prop above threshold (June taxonomy `mass_sprint`, `bunch_sprint`).
- OUT: GC/climber-selective — front mountain+TT archetype share above threshold (note June finding: `time_trial` archetype behaves like GC/power riders in selective contests). Must exclude TdF-2026-stage-2-type days (shattered but GC men contesting).
- REMAINDER = survey object: hard-men selective sprints, break-decided days, echelons, puncheur days.

**Analysis:**
1. Cluster the remainder in composition space (shares + winner archetype + enrichment); pick k by BIC + face validity.
2. Build a **named one-day anchor library**: perennial one-days with ≥4 editions 2016+, multi-edition mean signatures (mean-of-priors beat last-edition everywhere) — Flanders, Roubaix, Gent-Wevelgem, Sanremo, Amstel, Liège, Lombardia, Strade Bianche, semi-classics tier.
3. For every residual stage day: cosine to nearest anchor. Distribution of best-match cosine = **the premise verdict** (fraction ≥ ~0.8 is one-day-expressible; characterize the low-match remainder — expected: breakaway-archetype-heavy stage-native days needing their own menu items).
4. Frequencies: training mass per prospective menu item (decides which conditionals are learnable).
5. Recurrence diagnostics: do slots/regions/weeks produce these days at any predictable rate (informs the mechanical prior, not the training labels).

**Validation rows (TdF 2026, stages 2–21):** report where each lands. Expected if the premise holds: 4/9/21 → classics-family anchors; 18/20 → climber-break (possibly stage-native); 13 → break/rolling; 2 → excluded by the GC-front rule. Compare against archived morning-of judgments (scenario keys in `predictions/stage_NN/scenarios.json`).

**Outputs:** `menu_v0.json` (per item: canonical composition vector, canonical shape values, named anchors, member examples, n_train), `stage_menu_assignments.csv` (every stage comp → item = the future training labels), validation report, premise verdict.

**Cost:** one session, pandas over existing artifacts. No scraping, no training.

## Step 2 — oracle re-gate on the surfacing suite

New script `day_menu_gate_cv.py` (import the 5-fold harness the way `contest_signature_gate_cv.py` does). Arms:
- **A** baseline = production stack (stage rows: 11 signature cols NULL, as shipped).
- **B** oracle menu fill = stage rows get the assigned item's canonical values in the `sig_*` cols; `rider_sig_share` / `rider_contest_fit` / `rider_sig_vs_field` recomputed against the filled signature; one-day rows keep shipped B4. (`sig_n_refs` fill: menu item support count or NaN — decide at implementation.)
- **C** (optional) mechanical-prior fill = reference-keyed, to price the serving bounty (oracle − mechanical = value of a better selector).

**Persist per test race per arm per fold** (the June gate JSON kept only pooled aggregates — the root of the mis-adjudication): winner model-rank, top-15 pool membership flags, board top-15 archetype shares, realized gap-bounded front composition, day-class label (from step 1 assignments).

**Metrics:** hard-slice (residual-class stages) primary — winner-in-top-15 rate, front-group member pool recall@15, composition divergence (board top-15 archetype mix vs realized front mix; cosine + EMD), winner-rank distribution. Global: `market_avg_log_loss`, honest DNF-adjusted frame, 5-fold consistency.

**Pre-registered decision rule (fill in exact thresholds before running):** B−A must improve hard-slice winner-in-top-15 and composition cosine with ≥4/5 fold consistency, at global guardrail no worse than ~−0.001. **If the oracle arm fails, the vocabulary is dead at its ceiling — stop the program before paying for course metadata or serve-side work.**

Cost: ~30 min compute (June harness was 27.6 min).

## Step 3 — rider-side conditional representation

The user's framing (2026-08-08): a rider's history = how he fares given (a) the day's gap shape and (b) who contested it; prediction = riders' conditional records compared within today's field. Generalizes the untested per-rider group ladders (plan item 2) and realizes the deferred **v7 characteristic-weighted EMA** — whose recorded blocker ("GC/GT targets have no single profile to weight toward") the menu dissolves: the menu item supplies the target signature for any stage day.

All features: as-of-then, base rows = contested rows (informative-comparison membership per `contested_rating.py` pair rules — sprint order in first 10 of winner's group + adjacent group-vs-group), kernel = cosine(historical comp's realized composition signature, target menu item's canonical signature). NULL when no qualifying history; **naming must avoid `avg_bucket` / `_count` substrings** (imputation trap) — use a `dtm_` prefix.

- **(a) Kernel attendance** — exposure-normalized contested-row rate on days similar to the target item: the break-artist / hard-day attendance fingerprint (Simmons: scattered top-20s in bucket space, but *keeps making these fronts*).
- **(b) Kernel performance ladder** — EMA of front-group position / finish percentile over contested rows, kernel-weighted: "form on days like this."
- **(c) Type-conditional contested Elo** — rating vector per rider over menu items; each comparison updates items proportionally to the race's soft membership; hierarchical shrinkage toward the global rating (rare items are thin). Serve features mirror the existing four (`rating/n/delta90/vs_field`, per selected item). Supersedes the backlogged terrain-split Elo with a composition-defined split. This is the literal "how do they fare against each other on days like this."

**Gate:** on top of the full stack *including global contested Elo* — the orthogonality claim is that the type axis is what global Elo lacks; if it proves redundant (v5's fate), kill it. Same surfacing-suite-primary + guardrail structure as step 2.

## Step 4 — serve side + full-stack integration gate (REGISTERED 2026-08-09, `day_menu_gate4_cv.py`)

One run answers both pre-ship questions. Arms (K-model trained once per fold, oracle keys at train/val — training always conditions on the realized day; only TEST key sourcing varies):
- **A** shipped arm-C stack (meta-OOF + one-day B4 sigs + contested Elo) — production baseline.
- **korc** A + menu8kernod features, oracle test keys — the ceiling; korc − kmix = the selector bounty.
- **kmech** same model, mechanical selector argmax keys — deployable hard key.
- **kmix** same model, boards run per item and MIXED under the selector's calibrated top-5 prior (renormalized) — the deployable designed serve mode; **the gated arm**.

**Mechanical selector** (tier 2, historically backfillable — supersedes waiting on course-metadata acquisition): LightGBM multiclass over menu items, labeled stage comps, train period only, val for early stopping + scalar temperature (val NLL). Features strictly pre-race: 6 race profile scores, startlist archetype counts + field strength aggregates, per-event historical shape descriptors (`*_slope`/`*_volatility`/percentile stats), `field_share_*`, stage_number / n_stages / stage_frac / month / category / is_stage_race. **Excluded as realized outcomes: `winning_time`, `abandon_ratio`** (the stack's own-shape skew is not imported into the selector). **Registered assumption: ITT format is exogenous-known at serve** (race format is public pre-race; the DB lacks the field) — itt comps get the itt key with prob 1 in all mechanical arms. One-day kernel keys were already mechanical (nearest canonical to own as-of-then B4).

**Pre-registered rule (kmix vs A, paired by fold):**
- G1 probability (primary, per the 2026-08-08 gate-policy addendum): honest_adjusted market_avg_log_loss, all subset, pooled ≤ +0.0010 AND ≥3/5 folds ≤ 0; one_day subset pooled ≤ +0.0015 (od watch-item adjudication).
- G2 surfacing (residual slice): winner_model_rank ≤ −1.00 with ≥4/5 folds < 0 AND board_front_cosine ≥ +0.010 with ≥4/5 folds ≥ 0 (step-3 bars, now on the full stack under mechanical keys).
- Guardrails: all winner capture ≥ −0.005; od winner capture ≥ −0.005 (one-sided). korc/kmech reported, not gated.

Per-race records persisted for every arm (pool ids to rank 25, front ranks, board/realized composition, selector diagnostics) — the pool-selection instrument is the review headline, per the user's 2026-08-09 directive: the production decision is reviewed on pool-selection behavior, not only winner capture or log loss.

Tier-3 (judgment prior) remains: read-selection eval over the TdF 2026 archived-judgment corpus, then prospective; not part of this run.

## Leak / as-of-then audit

| Channel | Status |
|---|---|
| Own-race continuous values as train features | **Forbidden** — borrowed canonical values only |
| Own-race coarse menu label at train | **Accepted, bounded** (49% label / 0.876 value recoverability, June) |
| Soft own-assignment at train | **Forbidden** (settled 2026-06-11) |
| Kernel target at train = own realized signature | **Forbidden** — use assigned item's canonical signature |
| History-row signatures (rider-side kernels) | Clean — realized past races, as-of-then at train and serve |
| Oracle label at CV test time | Oracle tier only; never the headline number |
| Book odds | Serve-time prior input only, forward only; never trains |

## Open questions

- Menu granularity k, and cluster-items vs named-anchor-items (lean: clusters inside the head, nearest named anchor as display metadata).
- Do shape coordinates join the kernel or stay canonical-values-only (lean: values-only, per decision 4).
- Whether step-3 kernels use the menu's discrete items or the continuous signature space directly (lean: continuous kernel, menu only for conditioning labels and serve selection).
- Whether menu-conditioned canonical values should eventually **replace** the own-shape profile scores at train (would fix the existing train/serve skew rather than adding alongside it) — bigger refactor, revisit after step 2.

## References

- Review corpus: `performance_eval/tour-de-france-2026/review/` (README, `compare_by_class.py`, `what_if_calibrated.py`); netlify `review.html`.
- June artifacts: listed under step 1; scripts in `cycling_project/prediction_tools/experiments/` (`front_local_race_typing.py`, `selection_signatures.py`, `contest_archetype_library.py`, `contest_signature_gate_cv.py`).
- Production touch points: `contest_signature_features.py` (the 11 cols, stage rows NULL by design), `contested_rating.py` (pair rules, snapshot attach), `train_production_model.py` (stack assembly), `race_ranking_predictor.py` (top-15 pool from bucket score — the retrieval channel this program feeds).
- Memory: gt-hard-day-design-hole, front-local-race-typing, contested-elo-rating, gt-coasting-form-dilution, gate-policy-probability-quality, day-type-menu-program.
