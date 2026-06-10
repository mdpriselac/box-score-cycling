# Stage-Race Dynamics Plan

*Drafted 2026-06-09. Goal: use information from completed stages of an ongoing stage race to improve predictions for (a) upcoming stages and (b) the final GC.*

> **Status (2026-06-09):** Phases 0–1 built and run. Phase 1 CV **passed the
> ship gate** (+0.50pp winner, 5/5 folds; −0.033 stage-row log loss; clean
> dose-response by stage index). NaN-imputation variant tested and rejected —
> neutral defaults (v1) is the integration config. Plumbing is in
> (TrainingConfig/`train_production_model` flag, weekly `race-state` pipeline
> step) with production training OFF pending Phase 3 inference wiring — see
> §9 integration-order constraint. Full numbers in experiment_log.md
> ("Stage-race state features", 2026-06-09).

## 1. The gap today

The system already treats every stage as its own competition row (`competition_type='stage'`) and the
final GC as another (`'gc'`), so the *targets* are right. What's missing is the *state*:

- **No within-race features exist.** Every row — stage 15 of the Tour included — is predicted from
  history available before that competition, with no current GC rank, no gap to the leader, no
  stage-results-so-far, no fatigue signal. (Snapshots are built chronologically in
  `engineering_tools/feature_precomputation.py`; the only same-race awareness is an *exclusion*:
  GC rows' form windows skip the race's own stages, `form_team_features.py:123-127`.)
- **One nuance:** for stage rows, the generic 90-day form features (`form_recent_avg_bucket` etc.)
  *do* absorb earlier stages of the same race once they're in the DB — but blended indiscriminately
  with pre-race results, and with no GC/time-gap/tactical context.
- **GC rows are predicted completely blind mid-race.** There is no mechanism, in training or
  inference, to condition "final GC outcome" on the standings after stage k. For book comparison
  this is the biggest miss: GC markets reprice every day of a Grand Tour.
- **Operationally**, the pipeline is weekly and the web app's snapshots come from the last migrated
  competition, so mid-race predictions today are effectively pre-race predictions.

## 2. Data foundation (audited 2026-06-09)

Verified directly against `cycling_races.db`:

| Fact | Value |
|---|---|
| Stage races with stage rows, 2016+ | 687 (4,131 stage competitions, ~530K stage results) |
| Stage races with a GC row, 2016+ | 608 |
| Stages missing `winning_time` | 36 / 4,131 (0.9%) |
| Stage results missing `time_gap` | 465 / 529,840 (0.09%) |

**GC state is reconstructable without new scraping.** Cumulative time per rider =
Σ over completed stages of (`competitions.winning_time` + `rider_results.time_gap`). Validated against
stored final GC for 191 races (2023–2025):

- Median top-10 gap error **10s**, p90 **27s**, p97 **45s** — the residual is bonus seconds
  (FirstCycling GC includes them; raw stage sums don't). Grand Tour worst case ~72s over 21 stages.
- Reconstructed GC winner matches actual in 172/191 (90%); mean top-10 rank error 0.97 places.
- 2 of 191 races are data-quality outliers (Tour de Wallonie 2024, Tour de Taiwan 2025 — gap errors
  in the hours). A sanity guard must catch these (§7).

That precision is fine for *features* (gaps measured in minutes, ranks within ~1 place). Exact
bonus-second GC would require scraping FirstCycling's per-stage classification tables — a natural
extension to the `webscrape-refactor` branch later, **not** a prerequisite.

Riders absent from a stage's results (DNF/DNS/OOT are never inserted) simply drop out of the
cumulative state from that stage on — which is the correct semantics for abandons.

## 3. Design overview

Three phases, each independently shippable and falsifiable. The core implementation choice: build
race-state as a **separate joined table** (like `race_feature_gradients`), *not* by extending the
`RiderRunningState` snapshot machinery — that avoids a full snapshot rebuild, keeps the state
inspectable, and lets the identical code path serve training (historical) and inference (live).

```
rider_results + competitions
        │
        ▼
engineering_tools/stage_race_state.py        ← new, pure SQL/pandas
        │  builds rider_race_state table: one row per (rider, stage/gc competition)
        │  = standings + in-race form AFTER the previous stage
        ▼
data_pipeline LEFT JOIN (include_race_state flag, mirrors gradients flag)
        │
        ├── Phase 1: stage-day models + state features
        └── Phase 2: mid-race GC head (checkpoint training rows)
```

### `rider_race_state` table

Keyed `(rider_id, competition_id)`. For a stage-k row, every value is computed strictly from stages
1..k-1 of the same race. Stage-1 rows, one-day races: all NULL (LightGBM handles natively, same
pattern as the gradient null-markers). Incremental build by competition date; full build is minutes
(simple aggregations over 530K rows).

## 4. Phase 1 — race-state features for stage-day prediction

Add ~20 features to stage rows; GC rows keep current behavior in this phase (their state-aware
upgrade is Phase 2, as a separate head, so production GC predictions aren't disturbed).

| Family | Features | Notes |
|---|---|---|
| GC standings | `gc_rank_current`, `gc_gap_to_leader_s`, `gc_gap_to_podium_s`, `gc_gap_to_rank10_s`, `gc_rank_pctile`, `is_race_leader` | from reconstructed cumulative time |
| Team GC | `team_best_gc_rank`, `is_team_gc_leader`, `teammates_top10_count`, `team_has_gc_top5` | domestique-duty / protected-rider signal |
| In-race form | `last_stage_bucket`, `last_stage_pctile`, `best_stage_bucket_so_far`, `mean_stage_pctile_so_far`, `stage_top10_count_so_far` | sharper than the blended 90-day form window |
| Fatigue / progress | `stages_completed`, `pct_race_complete`, `cum_time_raced_s`, `is_post_rest_day` (date gap > 1 day), `field_attrition` (finishers remaining / stage-1 starters) | |
| Tactical freedom | `gc_gap_gt_10min`, `lost_big_time_last_stage` (>600s) | the "breakaway license" — far-down riders get freedom, GC teams chase differently |

**Hypothesis:** like the Stage-0 gradient features (the last clear win, +6.3% winner capture), this
is *new orthogonal information*, not a recombination of existing signal — the falsified directions
(blends, meta-learner, embeddings) all recombined what the 126 features already knew. The honest
caveat: part of the recency signal is already absorbed by generic form features on stage rows, so
the marginal value must come from the GC/tactical/fatigue dimensions. That's what the experiment
measures.

**Experiment** (`prediction_tools/experiments/stage_state_features_cv.py`, following the
`stacked_meta_learner_cv_5fold.py` pattern):

- 5-fold full-year CV, start_date 2016, production config + state features vs production config.
- Metrics on **stage rows only**, reported overall and stratified by stage index
  (stage 1 / 2–3 / 4–9 / 10+) — the lift should grow with stage index; stage-1 rows are the control
  (identical features, so any difference there is noise).
- Primary: winner capture, podium capture, top-4 log loss (paired per-fold deltas ± std, as usual).
- Decision rule: ship if paired winner-capture lift on stage-2+ rows clears fold noise, or if podium
  capture + log loss improve consistently without winner regression.

## 5. Phase 2 — mid-race GC head

A new model (alongside the existing heads, not replacing the pre-race GC prediction):
**P(final GC bucket | state after stage k)**, calibrated — the direct analog of in-play GC markets.

- **Training rows:** (rider, gc_competition, checkpoint k) for every k = 1..N−1 with a valid state.
  ~608 races × ~6 checkpoints × ~120 finishers ≈ 400K rows.
- **Features:** the GC row's existing pre-race features + the Phase-1 state block +
  `pct_race_complete`. (Remaining-stage terrain — "how much climbing is left" — is deliberately
  deferred: per-stage profile scores are derived post-hoc from results gradients, so using them for
  *future* stages in training would leak relative to what inference can know. Phase 2B can add
  remaining-terrain from prior-edition reference stages, matching how the web app already sources
  profiles.)
- **Target:** final GC `place_bucket` (already in `rider_results`).
- **Architecture:** reuse the contender-cascade machinery first (known-good); LambdaRank variant as
  a calibration comparison, mirroring the two-head pattern.

**The baseline that matters: carry-forward** — predict final GC = current GC order. Late in a race
this is nearly unbeatable; the model's value window is early/mid race and *probability quality*
(how likely is a 40s lead to hold with two mountain stages left?). Evaluate winner/podium capture,
Spearman vs final GC, and log loss **vs carry-forward**, stratified by checkpoint
(≤33% / 33–66% / >66% of race complete). Ship only where it beats carry-forward and the current
blind pre-race GC prediction.

**CV hygiene:** checkpoint rows from the same race are heavily correlated — fold sampling and
metric aggregation must group by race (extend `experiment_runner`'s race sampling accordingly).

## 6. Phase 3 — live inference & web app

The pieces mostly exist:

- `future_race_loader.py` already scrapes results on demand and caches them
  (`scrape_race_results()` → `save_results_to_cache()` → `cached_race_results` table, with rider-id
  matching). For an ongoing race, fetch completed stages 1..k through this path — no full pipeline
  run needed mid-race.
- Compute the state block in memory from those cached results using the **same function** the table
  builder uses (one implementation, two data sources).
- Web app: it already detects stage races and offers stage/GC selection. When the selected target is
  stage k+1 or GC of a race with completed stages, show a "Refresh completed stages" action, display
  the current reconstructed GC top-10 for sanity, and feed state-aware predictions.
- `prediction_log`: add a nullable `state_through_stage` column so logged predictions record what
  state they conditioned on (needed for clean long-term book comparison).
- Formalize the mid-race rescrape as a CLI: `uv run python -m cycling_project.update_pipeline
  --race <fc_race_id> --year <year>` running scrape→migrate for one race (today this requires
  manually deleting the pickle).

## 7. Risks & guards

- **Leakage:** state for stage k must use only stages with `stage_number < k`. Stage-1/one-day rows
  get NULLs, never zeros (zero is a meaningful gap). The experiment's stage-1 stratum doubles as a
  leakage canary.
- **Bad source data:** per-race sanity check at build time — reconstruct final GC, compare to stored
  GC; if top-10 mean abs error > 120s, mark the race's state rows suspect and exclude from training
  (catches the Wallonie/Taiwan-class outliers).
- **Duplicate 2024 races:** 30 races (incl. both 2024 GTs) exist twice in `races` with identical
  results — double-counted in training and 2024 test folds. Fix before running Phase-1 CV
  (separate task, spawned 2026-06-09).
- **TTT stages:** riders carry team time; cumulative sums remain consistent. No special handling
  needed for state, but `is_post_rest_day` and per-stage form treat them as normal stages.
- **Split stages / same-day stages:** order by `stage_number`, tiebreak by date; both exist in
  older data.
- **2023 fold anomaly** (known ~20% winner-capture dip): report per-fold as always; don't let one
  fold decide.

## 8. Sequencing

1. ~~**Dedupe 2024 races**~~ — DONE 2026-06-09 (separate task).
2. ~~**Phase 0**: `stage_race_state.py` builder + `rider_race_state` table + sanity guard +
   unit tests~~ — DONE 2026-06-09. 804K state rows / 1,088 races; countback tie-breaking added
   after a smoke test found whole bunches tied at rank 1 post sprint stages; validated against
   the 2024 Tour (exact GC order, bonus-second-sized gap errors).
3. ~~**Phase 1 experiment**: data_pipeline join flag + CV script + run~~ — DONE 2026-06-09,
   **gate PASSED** (see status box). NaN-imputation variant tested same day and rejected
   (stage-1 regression is intrinsic capacity reallocation, not an imputation artifact; NaN
   mode trades winner capture for log loss).
4. ~~**Phase 3 lite — inference-side state attachment**~~ — DONE 2026-06-09.
   `prediction_tools/live_race_state.py`: enumerates the live edition's stages, pulls completed
   results through `scrape_or_load_results` (DB → cache → scrape), feeds the SAME
   `compute_race_state` used in training (with `total_stages` denominator override), and
   `attach_race_state` materializes the 23 columns on every prediction frame. Web app attaches
   real state for stage-2+ targets only (matching training); one-day/GC/stage-1 get NaN →
   neutral defaults. `get_feature_matrix` now falls back to state defaults (not zeros) for
   absent state columns. Verified live mid-race on Dauphiné 2026 (3 of 8 stages completed,
   146-rider standings, correct leader). Known v1 gap: `is_post_rest_day` is 0 for live state
   (no stage dates on the live path).
5. ~~**Flip production**~~ — DONE 2026-06-09. Retrained on 624,796 post-dedupe samples
   (13.6 min; calibrated head log loss 1.047 / ECE 0.004 on early-stop set); bucket model now
   carries 149 features including state. End-to-end verified headlessly through the app code
   path on the live Dauphiné: state from 3 completed stages attached, 141/154 predicted ranks
   moved vs the state-blind frame. `prediction_log.state_through_stage` column added (ALTER
   migration), and the logged `stage_number` now records the SELECTED prediction target rather
   than the URL stage hint. LambdaRank head remains stateless by design (untested with state).
6. ~~**Phase 2 experiment**: checkpoint-row construction + GC head CV vs carry-forward~~ —
   DONE 2026-06-09, **gate PASSED and 5-fold confirmed post-rebuild**: vs carry-forward
   +18.3pp winner early-race (5/5 folds, +21.4pp on the new 2025 fold), +5.8pp mid (5/5),
   parity late; vs blind +19.8pp winner, log loss 1.69→1.11. LambdaRank+state tested the same
   day and REJECTED (within noise; head stays stateless). See experiment_log.md.
7. ~~**Phase 2b — productionize the GC outlook head**~~ — DONE 2026-06-09.
   `prediction_tools/gc_outlook.py` (canonical checkpoint assembly + `GCOutlookHead`
   train/save/load/predict; self-contained gc_outlook_* files in models/production, main
   ModelRegistry untouched), `train_gc_outlook_production.py`, pipeline step
   `train-gc-outlook` (13 steps total). Web app: GC targets of in-progress stage races fetch
   live state (all completed stages), the MAIN GC prediction stays pre-race (training
   parity), and a separate "GC Outlook — after stage k" section shows state-aware
   win/podium/top5/top15 with current standings. `prediction_log` gains gc_outlook_* columns;
   outlook probabilities logged per rider per run.
8. **Later / optional:** scrape FirstCycling per-stage classification tables for bonus-second-exact
   GC (webscrape-refactor branch); remaining-terrain features from reference editions; Monte-Carlo
   GC simulation driven by the stage model; points/KOM jersey markets; LambdaRank + state
   revisit only if a calibrated in-race head becomes a priority (2026-06-09 test: within noise).

## 9. Integration-order constraint (learned in Phase 1)

The CV gains exist only where state is available at prediction time. A state-trained model fed
all-default state behaves like the stage_1 control stratum — slightly WORSE than baseline
(podium −2.35pp on those rows). The web app's future-race frames currently carry no state
columns, so the production flag must stay OFF until inference can attach real state:

- **Weekly pipeline** keeps `rider_race_state` fresh (step `race-state`, non-fatal, already in).
- **Phase 3 lite**: when the web app predicts stage k+1 or the GC of a race with completed
  stages, fetch those stages (DB or `cached_race_results`/on-demand scrape via
  `future_race_loader`), run `compute_race_state` in memory, and attach the columns to the
  prediction frame; all other targets get NaN → neutral defaults via `apply_imputation`
  (identical to training-time missing state). Inference frames must INCLUDE the state columns
  as NaN when absent — `get_feature_matrix` zero-fills missing columns, and zeros mean
  "race leader", not "no state".
- Only then flip `include_race_state=True` and retrain production.
