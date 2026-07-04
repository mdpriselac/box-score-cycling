# GT-Aware Form Features — Experiment Work Order (2026-07-03)

Self-contained plan for the next experiment: fix the grand-tour coasting
dilution in the form features. Written to be actionable in a fresh session
with no prior context.

## 1. Problem (established, do not re-derive)

The v2/v3 form block (EMA percentile + season trajectory, shipped 2026-06-10)
is computed **per result row**. A grand tour emits ~21 rows; a GC winner
legitimately coasts ~14 of them (gruppetto on sprint days). Those rows score
percentile 30–85 and dilute the EMA. Concrete case that surfaced it:
Vingegaard after **winning** the 2026 Giro (plus Paris-Nice + Catalunya, 3/3
GCs) carried `v2_ema_pct_h60 = 83.4` — lowest of the five TdF favorites
(Pogačar 98.2, Evenepoel 88.4 *while not having raced since Apr 26*). The
model ranked Evenepoel above Vingegaard on the TdF GC board; the book had
Vingegaard 2nd favorite at 5.25 and Evenepoel at 34.0.

Components NOT affected (they got Vingegaard right): `form_profile_recent_avg`
(profile-conditioned), contested Elo (Vin 1751 > Eve 1704), time-gap head.
Only the per-row EMA/trajectory block is blind.

## 2. Step-0 evidence (PASSED 2026-07-03 — the green light)

Sliced the 2026-06-10 age-bias backtest records (280K rows, 5 folds
2021–2025, 2016 start) by days since the rider last finished a GT
(≥10 stage rows in a Giro/TdF/Vuelta edition, same-edition rows excluded).
LambdaRank win cal ratio (Σp/Σwins; <1 = model underprices):

| band | all targets | GC targets |
|---|---|---|
| GT ≤45d ago | **0.762** (5/5 folds under) | **0.510** (5/5) |
| GT 46–90d | 0.846 (5/5) | 0.718 |
| GT 91–365d | 0.966 (4/5) | 0.918 |
| no GT in 12mo | **1.120** (0/5) | **1.274** |

Monotone dose-response; contender head same direction (0.875 → 1.036).
Two-sided: mass moves from recent-GT riders to GT-naive riders. Worst cell
= GC target ≤45d after a GT → riders win at 2× the model's price. Bigger
than the veteran bias (worst 1.327) that justified v2/v3.

- JSON: `experiments/gt_recency_backtest_20260703.json`
- Script: `cycling_project/prediction_tools/experiments/gt_recency_backtest.py`
  (joins GT participation from DB onto backtest records; reusable as the
  bias diagnostic for any new fold records — see §6)
- Narrative: `experiment_log.md` entry 2026-07-03
- Caveat: records are pre-v2v3 heads; mechanism confirmed present in v2v3
  via the live probe. The sweep baseline (§6) re-measures on current stack.

## 3. Candidate designs (user-endorsed, in priority order)

**v5 — contested-rows-only form** ("form when it mattered"):
EMA percentile computed only over rows where the rider appeared in ≥1
informative comparison in that competition. Reuse the contested-Elo
extraction: `prediction_tools/contested_rating.py::load_contested_results`
+ `_competition_pairs` already identify informative comparisons (sprint
order within first 10 of winner's group; adjacent group-vs-group). A row is
"contested" for rider R in comp C iff R appears in ≥1 pair for C. Fixes
within-race dilution for every rider type at once (coasting days drop out
because the rider wasn't contesting anything).

**v6 — comp-type-scoped form**:
Parallel EMA over `competition_type in ('gc','one_day')` rows only (stage
rows excluded). Fixes across-race credit (a GC row counts as one clean
observation of GC output). Simple, directly targets the GC board.

They are complementary (within-race vs across-race), so the grid must
include the combination.

**Suggested columns** (mirror v2 naming; MUST avoid the substrings
`avg_bucket` and `_count` — those trigger pattern-based imputation in
`feature_engineering.py`; use `eff_n` like v2 does):
- v5: `v5_cont_ema_pct_h60`, `v5_cont_ema_pct_h30`, `v5_cont_ema_eff_n_h60`,
  optionally `v5_cont_season_pct_cur`
- v6: `v6_scoped_ema_pct_h60`, `v6_scoped_ema_pct_h30`,
  `v6_scoped_ema_eff_n_h60`, optionally `v6_scoped_season_delta`

NULL when no qualifying history (LightGBM native NaN) — never impute.

## 4. Where to build

1. **Lab**: extend `prediction_tools/experiments/form_feature_lab.py`
   (`FormFeatureLab`, existing V1–V4_COLS pattern; cache
   `experiments/form_lab_features_v1.csv.gz`, 685K rows, ~55s build —
   add V5/V6 blocks, bump cache filename to v2). Contested flags: build a
   (rider_id, competition_id) → contested boolean from
   `load_contested_results` once, join into the lab's row stream.
   Chronological / as-of-then discipline identical to v2 (only rows strictly
   before the target comp).
2. **Sweep**: add configs to
   `prediction_tools/experiments/form_feature_sweep.py::CONFIG_REGISTRY`
   (name → lab column list; CLI-selectable; 5-fold, 2016 start).
   Grid: `baseline` (production = with v2v3), `v5`, `v6`, `v5v6` — each
   ADDED to the production feature set (v2v3 stays in; the question is
   incremental value, mirroring how v2v3 itself was gated).

## 5. Gate (per standing policy)

- **Primary**: `market_avg_log_loss` (MarketProbabilityEvaluator,
  prediction_tools/evaluation.py), 5-fold, honest frame (startlist pool,
  DNF-adjusted), fold consistency reported. Winner capture = diagnostic.
- **Bias diagnostic** (the point of the exercise): re-run the GT-recency
  cal table (adapt `gt_recency_backtest.py::table` onto each config's fold
  records). Success shape: GT ≤45d band moves toward 1.0 (esp. GC targets)
  WITHOUT pushing the no-GT band further above 1.12. Watch the v4 lesson:
  a config can win standard metrics while diluting the bias fix — v4
  volatility was shelved for exactly that.
- If v5/v6 pass, next stop is the full-stack integration CV
  (`full_stack_integration_cv.py` pattern) before any production wiring.

## 6. Baseline requirement

The step-0 numbers came from pre-v2v3 records. First sweep action: run the
`baseline` config's folds, collect records (the sweep already collects
per-row records in the age-bias backtest format), and produce the GT-recency
table for the CURRENT stack. That number is what v5/v6 must beat.

## 7. Gotchas

- **Worktree sessions**: the SQLite DB and large caches are NOT in git. If
  running from a fresh worktree, first symlink them from the main checkout:
  `ln -sf "~/Documents/Cycling Project/cycling_project/webscrape_tools/database/database/cycling_races.db" cycling_project/webscrape_tools/database/database/cycling_races.db`
  and reuse `~/Documents/Cycling Project/experiments/` outputs
  (lab cache csv.gz, backtest records) by absolute path where needed.
  Same for `models/production/` artifacts if the sweep loads them.
- `rider_results.rider_id` and all internal joins use **internal DB ids**
  (`riders.id`), not FirstCycling ids (Vingegaard=1, Pogačar=177,
  Evenepoel=649). `live_form.compute_form_features_asof` silently returns
  degenerate defaults if given FC ids.
- GT definition for diagnostics: fc_race_id ∈ {13 Giro, 17 TdF, 23 Vuelta},
  ≥10 stage rows in the edition; exclude same-edition rows when computing
  "days since GT".
- DB is current through 2026-06-21 + full Dauphiné 2026 (backfilled
  2026-07-03; the rebranded "Tour Auvergne - Rhône-Alpes", fc 15).
- Migration gotcha (unrelated but nearby): `migrate_races.py` permanently
  skips races already in `races` — a race migrated mid-event never gets its
  remaining stages. Don't scrape-migrate mid-GT and expect a later top-up.
- Rate limits / Cloudflare: no scraping needed for this experiment.
- Snapshots table: `rider_competition_snapshots`, 1.1M rows from 2010;
  training frames via the sweep's existing `_load_full_df`.

## 8. Definition of done

Sweep JSON in `experiments/` + experiment_log.md entry with: per-config
market_avg_log_loss deltas (fold-by-fold), GT-recency cal tables
(baseline vs candidates), feature-importance ranks of the new columns, and
a ship/shelve verdict per the gate. If shipped later: production twin in
`form_team_features.py`, snapshot schema migration, 2010 rebuild, retrain —
same checklist as the v2v3 productionization (see memory
`future_work_form_metrics`).
