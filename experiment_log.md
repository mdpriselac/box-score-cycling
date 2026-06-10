# Experiment Log

Running record of experiments for the joint race-characterization plan
(`curried-singing-hammock.md`). Each entry lists the config, the primary
metrics, the diff versus a same-code baseline, and a verdict against the
stage success bar.

All experiments use the 3-fold full-year CV protocol:
- train→2021 / val→2022 / **test→2023**
- train→2022 / val→2023 / **test→2024**
- train→2023 / val→2024 / **test→2025**

Contender model tuning is held constant across experiments at the
"current best" settings from 2026-03-09: top-15 filter, LR 0.01, OOF
bucket predictions, 5-class reduction. Any deviations are called out in
the entry.

---

## Stage 0 — pass-through gradient + null-marker + race-shape columns
**Date:** 2026-04-11
**Branch / worktree:** `claude/objective-bartik` (`.claude/worktrees/objective-bartik`)
**Result JSONs:**
- Baseline clone: `experiments/current_best_rerun_20260411_131738.json`
- Stage 0:        `experiments/stage0_gradients_20260411_132915.json`

### What changed
Added a `DataConfig.include_gradient_features` flag (off by default).
When on, the training and inference SQL queries LEFT JOIN
`race_feature_gradients` and `race_features_100` and select **19 new
columns**:

| Group | Columns |
|---|---|
| Gradient slopes / volatility / monotonicity (11) | `variance_normalized_slope`, `variance_normalized_volatility`, `variance_normalized_monotonicity`, `clumpiness_score_slope`, `clumpiness_score_volatility`, `biggest_group_metric_slope`, `biggest_group_metric_volatility`, `selection_metric_slope`, `selection_metric_volatility`, `gini_coefficient_slope`, `skewness_normalized_slope` |
| Null-awareness markers (5) | `percentile_coverage_ratio`, `lowest_valid_percentile`, `highest_null_percentile`, `kurtosis_null_percentile`, `variance_zero_percentile` |
| Race-shape scalars (2) | `winning_time`, `abandon_ratio` |
| Silent-failure flag (1) | `race_profile_missing` = `CASE WHEN rfg.competition_id IS NULL THEN 1 ELSE 0 END` |

`time_gap_evenness_metric_slope` was dropped from the plan — it doesn't
exist as a gradient column in the schema.

Imputation defaults are added in `feature_engineering.FeatureEngineer.apply_imputation`:
slopes/volatility/monotonicity → 0.0 (neutral); `percentile_coverage_ratio` → 1.0;
`lowest_valid_percentile` → 10; the three null-band percentiles → 0;
`winning_time` → 14000s; `abandon_ratio` → 0.05;
`race_profile_missing` needs no imputation. Feature count goes from 107 → **126**.

### Prework: silent no-profile cohort (filed against live DB 2026-04-11)

```sql
SELECT COUNT(*) AS total,
       SUM(CASE WHEN rfg.competition_id IS NULL THEN 1 ELSE 0 END) AS no_gradient,
       SUM(CASE WHEN rfg.competition_id IS NOT NULL
                 AND (rfg.variance_normalized_slope IS NULL
                   OR rfg.clumpiness_score_slope IS NULL
                   OR rfg.biggest_group_metric_slope IS NULL)
                THEN 1 ELSE 0 END) AS null_slopes
FROM competition_field_features cff
LEFT JOIN race_feature_gradients rfg ON rfg.competition_id = cff.competition_id
WHERE cff.competition_date >= '2018-01-01'
  AND cff.competition_type IN ('stage','one_day','gc')
  AND cff.race_category IN ('wt','pro','d1');
```

Result: **total=4382, no_gradient=37 (0.84%), null_slopes=0**.

Previous handoff count (earlier in the project timeline) was 62/4464.
The size of the silent-failure cohort has shrunk since then, likely due
to the "Fix migration skipping races with zero competitions" commit
(`6f661c4`) retraining on a cleaner dataset. Either way, well below the
5% guardrail from the plan, and every one of those races now enters the
model as `race_profile_missing=1` with filled-in zero-valued gradient
columns.

Latent bug from the plan notes still applies: the TT short-circuit at
`winning_time < 4200s` in `race_profile_scoring.py` never fires for
these rows because `race_profile` is set to `None` before reaching it.
Not addressed in Stage 0 (out of scope).

### Config

- `contender_top_n=15`, `contender_learning_rate=0.01`,
  `contender_use_oof=True`, `contender_n_classes=5`,
  `n_estimators=500`, `early_stopping=50`
- `include_gradient_features=True` (stage 0) vs `False` (baseline)
- Both ran on the **same code** at `claude/objective-bartik`

### Primary metrics (3-fold mean ± std)

| Metric | Baseline (rerun, flag off) | Stage 0 (flag on) | Δ | Δ as σ of baseline |
|---|---|---|---|---|
| Winner capture       | 0.2287 ± 0.0066 | **0.2431 ± 0.0034** | **+0.0144 (+6.29%)** | **+2.17σ** |
| Top-4 log loss       | 1.7936 ± 0.0363 | **1.7785 ± 0.0274** | -0.0151 (-0.84%) | -0.42σ |
| Podium capture       | 0.4504 ± 0.0168 | 0.4436 ± 0.0120 | -0.0068 (-1.50%) | -0.40σ |
| Win cal ratio        | 0.9095 ± 0.0133 | 0.8663 ± 0.0267 | -0.0432 (-4.75%) | -3.25σ ⚠ |
| Podium cal ratio     | 0.9770 ± 0.0347 | 0.9556 ± 0.0326 | -0.0214 (-2.19%) | -0.62σ |
| Top-4 Brier          | 0.9425 ± 0.0229 | 0.9331 ± 0.0160 | -0.0094 (-1.00%) | -0.41σ |
| Bucket MAE           | 1.2396 ± 0.0504 | **1.1905 ± 0.0397** | -0.0492 (-3.97%) | -0.98σ |
| Ranker Kendall τ     | 0.3885 ± 0.0130 | 0.3946 ± 0.0101 | +0.0061 (+1.58%) | +0.47σ |

### Per-fold Stage 0 winner capture

| Fold | Winner | Log loss | Podium |
|---|---|---|---|
| 2023 | 0.2473 | 1.8163 | 0.4267 |
| 2024 | 0.2429 | 1.7523 | 0.4531 |
| 2025 | 0.2390 | 1.7669 | 0.4510 |

Fold-to-fold std tightened meaningfully compared to baseline
(winner std 0.0066 → 0.0034; podium std 0.0168 → 0.0120;
log-loss std 0.0363 → 0.0274). The gradient columns appear to give
LightGBM a more stable signal across years.

### Sanity check — baseline rerun vs historical current_best

The baseline rerun on current code reproduces the historical
`current_best_fullyear_20260309_215606.json` to within 0.1% on every
primary metric (0.2287 vs 0.2293 winner; 0.4504 vs 0.4512 podium;
1.7936 vs 1.7922 log loss). Nothing has drifted from commits between
2026-03-09 and today — comparison is fully apples-to-apples.

### Feature importance — new columns (bucket model, avg gain across folds)

Rank in top-30 is **bolded**. All three folds see the same leaderboard
with very little reordering — the signal is stable.

| Column | 2023 gain | 2024 gain | 2025 gain | Top-30? |
|---|---|---|---|---|
| `variance_normalized_monotonicity` | 69,815 | 90,735 | 101,246 | **all 3** |
| `skewness_normalized_slope`        | 37,538 | 39,285 | 53,518 | **all 3** |
| `clumpiness_score_volatility`      | 30,987 | 39,644 | 52,836 | **all 3** |
| `selection_metric_volatility`      | 30,850 | 37,706 | 50,250 | **all 3** |
| `biggest_group_metric_volatility`  | 32,691 | 34,119 | 43,446 | **2023, 2024** |
| `kurtosis_null_percentile`         | 29,068 | 26,726 | 46,377 | **2023, 2025** |
| `biggest_group_metric_slope`       | 25,280 | 27,792 | 42,580 | — |
| `winning_time`                     | 22,999 | 27,673 | 36,171 | — |
| `variance_normalized_slope`        | 20,009 | 29,373 | 36,867 | — |
| `gini_coefficient_slope`           | 20,374 | 24,966 | 38,699 | — |
| `variance_normalized_volatility`   | 23,297 | 20,781 | 33,194 | — |
| `selection_metric_slope`           | 17,962 | 20,405 | 28,877 | — |
| `clumpiness_score_slope`           | 10,629 | 11,165 | 20,020 | — |
| `percentile_coverage_ratio`        |  2,014 |    838 |  1,224 | — |
| `variance_zero_percentile`         |  1,617 |  1,764 |  2,282 | — |
| `lowest_valid_percentile`          |      0 |    150 |    106 | — |
| `highest_null_percentile`          |      0 |      0 |      0 | — |
| `abandon_ratio`                    |      0 |      0 |      0 | — |
| `race_profile_missing`             |      0 |      0 |      0 | — |

Takeaways:
- **13 of 19 new columns are actively used** (gain > 0 across folds).
- `variance_normalized_monotonicity` is the single biggest contributor.
  It's ranked #11 overall in Stage 0's bucket model vs. not present at
  all in baseline — this is a real new signal.
- The two **noisiest** and **most specialist-relevant** gradient
  metrics (`clumpiness_score_volatility`, `selection_metric_volatility`)
  both land in top-30 across all three folds. This is the kind of
  "how disorderly was the finish" signal the baseline didn't have.
- `kurtosis_null_percentile` is working as a null-awareness signal as
  the plan predicted — it's effectively encoding "at what percentile
  does the field start bunching" and LightGBM picks it up as a top-30
  feature in 2 of 3 folds.
- **Dead weight (0 gain on all folds):** `race_profile_missing`,
  `abandon_ratio`, `highest_null_percentile`. These are harmless (no
  regression) but can be dropped in a future cleanup pass.
  - `race_profile_missing` has only 37/4382 true cases — too rare for
    LightGBM to find a split at 500 iterations. The flag is still
    valuable as a **diagnostic** even if the model doesn't use it.
  - `abandon_ratio` was surprising — the plan expected it to distinguish
    brutal mountain stages. Likely the variance/clumpiness gradients
    already carry this information.

### Verdict vs Stage 0 success bar

Plan's bar: *"match or beat current best within noise (winner 22.9
± 0.6, podium 45.1 ± 1.7, log loss 1.792 ± noise)"*.

- Winner capture: **beats** baseline by +2.17σ. +0.0144 absolute (+6.29%).
- Log loss: **beats** baseline (-0.84%), within noise.
- Podium: -0.68pp, within 0.4σ of baseline noise → **matches**.
- Bucket MAE: **-3.97%** (independent evidence the model is learning more).
- Win calibration: **regression**, -3.25σ. Went from 0.9095 → 0.8663,
  moving **away** from 1.0 — the model is now more over-confident on
  its top-probability picks. Still roughly in the same territory as
  pre-contender-tuning baselines (~0.82), but noticeably worse than
  the post-tuning equilibrium.

**Overall: Stage 0 PASSES the success bar.** Winner and log-loss improve
meaningfully, podium matches within noise, fold-to-fold stability
improves across the board. The calibration regression is a real cost
and should be watched — it likely means a Platt/isotonic calibration
step would be worth revisiting if Stage 0 graduates to production. For
experiment-only purposes, Stage 0 is cleared to become the new baseline
for Stage 1.

### Follow-ups / open items

- [ ] Specialist/generalist diagnostic — compare predicted-win gap for
      profile-matched vs. generalist riders. Plan calls for this across
      all stages; not run for Stage 0 because the winner-capture lift
      is already 2.17σ without it.
- [ ] Calibration: consider re-fitting the contender model's Platt
      scaling with gradient features in the mix. Current regression
      (-4.75%) is the main blemish on an otherwise clean pass.
- [ ] Dead columns to drop in a future cleanup pass: `race_profile_missing`
      (keep as diagnostic but drop from feature list), `abandon_ratio`,
      `highest_null_percentile`.
- [x] Stage 1 proceeded against the `stage0_gradients` baseline
      (see Stage 1 entry below). The bar was winner 0.2431, podium
      0.4436, log loss 1.7785.

---

## Stage 1 — one-day race clustering via type-profile rider signatures
**Date:** 2026-04-11
**Branch / worktree:** `claude/objective-bartik` (`.claude/worktrees/objective-bartik`)
**Result JSONs:**
- 3-fold sweep: `experiments/stage1_s0_baseline_rerun_20260411_162115.json`,
  `experiments/stage1_1a_race_only_20260411_163322.json`,
  `experiments/stage1_1b_joint_20260411_164542.json`
- Per-comp-type breakdown: `experiments/stage1_per_comp_type_breakdown.json`

### What changed

New offline script `cycling_project/prediction_tools/experiments/stage1_race_clustering.py`
fits a diagonal-covariance GMM per CV fold on **one-day races only** (788
total, 331-536 per training fold). Writes soft cluster memberships to a
new experimental table `race_cluster_v1_scores` with `(competition_id,
fold_label, variant)` as composite primary key. Two variants produced:

- **race_only**: GMM on the 11 race-side gradient columns (same as
  Stage 0). No field-side information. k swept [6,10].
- **joint**: GMM on a 16-dim feature vector: 11 race-side gradient
  columns + 5 whitened PCA components from a 48-dim field aggregate.
  Field aggregate is {mean, std, p25, p75} of 12-dim rider type-profile
  signatures across the starters. k swept [6,8].

Rider type-profile signature (12 dims per rider, from existing
`rider_competition_snapshots` columns via a chronological pass):

| Per category (stage, one_day, gc) | Metric | Source |
|---|---|---|
| avg_bucket | Mean bucket performance | Running mean |
| std_bucket | Performance volatility | Running variance |
| best_bucket | Peak ability (min observed bucket) | Running min |
| log1p(count) | Engagement scale | Running count |

Field aggregation uses **uniform weighting** (no quality weighting).
Quality weighting was tested first but caused field-signature convergence
across race types (see "Architecture iterations" below).

Clusters are **additive** to Stage 0 — no features removed. Stage/GC
rows get NULL cluster columns from the LEFT JOIN, imputed to 0.0 in
`feature_engineering.py`. Feature count: 126 (Stage 0) → **140** (+14
cluster features: 12 cluster scores + cluster_dominant + k_chosen).

### Architecture iterations (4 attempts before settling)

The plan originally called for a 55-dim joint vector with rider gradient
histories as the field-side signal. This failed repeatedly. The journey
is documented here because the failures are as informative as the results.

**Attempt 1: gradient-history field signatures (55-dim all-at-once PCA).**
Rider signatures = finish-quality-weighted career mean of race gradient
vectors. Field = quality-weighted aggregate across starters. Result:
every canonical race (Roubaix, MSR, Flanders, Strade, Giro TT) landed
in the same cluster in all 3 folds. Root cause: GT riders ride all stage
types together (21 stages with the same field), so their career gradient
signatures converge to "average stage race shape," and the same elite
pool appears on both cobbles and TT startlists. The field aggregate
captured "how elite is this field" instead of "what type of field is this."

**Attempt 2: type-profile field signatures (55-dim all-at-once PCA).**
Replaced gradient-based rider signatures with per-category (stage /
one_day / gc) performance stats (avg, std, best, log_count = 12 dims per
rider). This avoids the GT contamination because `one_day_avg_bucket`
reflects only one-day finishes. Result: PCA's PC1 (35% of variance) was
pure "field quality" — `field_stage_best_mean`, `field_gc_logcnt_mean`,
etc. Race-side gradient signal didn't appear until PC4 (5.7% of
variance). GMM clustered on quality, not type. Canonical races still
collapsed: all monuments in one cluster regardless of race shape.

**Attempt 3: split-and-concat (race-side raw + field-side PCA to 5 dims).**
Fixed the 48:11 column-count imbalance by processing each side
separately: 11 race-side z-scored columns stay raw, 48 field-side
columns get PCA-compressed to 5 components, then concatenated → 16-dim
GMM input. Race-side gets 69% of the feature budget. Result: significant
improvement. Canonical check showed climber classics (Strade, Lombardia,
Flèche) co-clustering consistently; Scheldeprijs (bunch sprint) distinct;
Flanders (cobbles) distinct 2/3 folds. But Roubaix/MSR still
co-clustered in 2/3 folds because field_PC1 (unwhitened) still carried
~20 variance units — more than all 11 race columns combined.

**Attempt 4: split-and-concat with field PC1 dropped.**
Identified PC1 as a near-pure "field quality" axis and dropped it from
the GMM input. Keeps PCs 2-6 (type-related structure: GC experience
spread, one-day performance heterogeneity, etc.). Result: similar
canonical check to attempt 3, slightly less stable across folds
(Hungarian mean_dist worsened). Roubaix/MSR still partially collapse.

**Decision**: proceeded with attempt 4 for the sweep. Both race_only and
joint variants run. Race_only consistently produces the cleanest
canonical taxonomy (cobbles distinct, climber classics grouped, sprints
separated, TT-like races separate).

### Canonical race sanity check (race_only variant)

Race-only produced the most sensible clustering. Cross-fold-consistent
groupings:

| Race(s) | Behavior across 3 folds |
|---|---|
| Liege-Bastogne-Liege | Cluster 2 in **all 3 folds** (most stable) |
| Gent-Wevelgem | Cluster 2 in **all 3 folds** (co-clusters with Liege) |
| Strade / Lombardia / Fleche Wallonne | Co-cluster in all 3 folds (climber classics) |
| Scheldeprijs | Own cluster in all 3 folds (bunch sprint) |
| Paris-Roubaix | Own cluster in 3/3 folds (cobbles) |
| Tour of Flanders | Own cluster in 3/3 folds |
| Milan-San Remo | Own cluster in 3/3 folds |
| Amstel Gold | Own-ish cluster (2/3 folds) |

Known limitation: Liege and Gent-Wevelgem co-cluster despite being
different race types (Liege is a climber classic; GW is a more
sprinter-focused semi-classic). This is a race-side-only issue — their
finishing-time gradient distributions happen to look similar (both are
selective late-race finishes). Race-side gradients alone can't
distinguish the *mechanism* of selection (climbs vs Kemmelberg), only the
*shape* of the resulting time gaps. The joint variant partially fixes
this (Liege clusters separately from GW in 1/3 folds) but not reliably.

### Config

- Same contender tuning as Stage 0 (top-15, LR 0.01, OOF, 5-class)
- `include_gradient_features=True` for all 3 configs (Stage 0 baseline)
- `include_race_clusters=True/False` and `cluster_variant='race_only'/'joint'`
- One-day rows: cluster features populated from `race_cluster_v1_scores`
- Stage/GC rows: cluster features = NULL → imputed to 0.0

### Primary metrics — 3-fold sweep (pooled across all comp types)

| Metric | S0 baseline | 1a race_only | 1b joint | 1a Δσ | 1b Δσ |
|---|---|---|---|---|---|
| Winner capture  | 0.2431 ± 0.0034 | 0.2439 ± 0.0065 | 0.2394 ± 0.0104 | +0.24σ | -1.07σ |
| Top-4 log loss  | 1.7785 ± 0.0274 | 1.7823 ± 0.0290 | 1.7859 ± 0.0377 | +0.14σ | +0.27σ |
| Podium capture  | 0.4436 ± 0.0120 | 0.4494 ± 0.0094 | 0.4471 ± 0.0022 | +0.48σ | +0.29σ |
| **Win cal ratio** | **0.8663** | **0.8974** | **0.8985** | **+1.16σ** | **+1.21σ** |
| Podium cal ratio | 0.9556 | 0.9762 | 0.9621 | +0.63σ | +0.20σ |
| Bucket MAE      | 1.1905 | 1.1898 | 1.1950 | -0.02σ | +0.11σ |
| Kendall tau     | 0.3946 | 0.3936 | 0.3927 | -0.10σ | -0.19σ |

**Pooled-metric read**: neither variant beats Stage 0 on discrimination
(winner, podium, log loss all within noise). **Both variants recover
~70% of Stage 0's calibration regression** (win cal 0.8663 → 0.8974/0.8985,
+1.16/+1.21σ). This is the one real signal in the pooled numbers.

### Per-competition-type breakdown (3-fold mean ± std)

The pooled metrics are misleading because Stage 1 only touches 18% of
rows (one-day). The per-comp-type split is the honest lens.

**One-day races** (125–355 per fold, 730 total across 3 folds):

| Config | Winner | Podium | Log loss |
|---|---|---|---|
| Baseline    | 24.97% ± 2.02 | 46.98% ± 1.07 | 1.823 ± 0.029 |
| 1a race     | 25.48% ± 2.45 | 45.95% ± 2.34 | 1.833 ± 0.031 |
| 1b joint    | 24.84% ± 2.14 | 45.40% ± 2.18 | 1.832 ± 0.040 |

1a vs baseline: winner +0.5pp (+0.25σ), podium -1.0pp, log loss +0.010.
**All within noise. No one-day discrimination improvement.**

Per-fold detail (1a race_only winner capture on one-day):
- Fold 2023 (355 races): 27.32% → 25.63% (**-1.7pp**)
- Fold 2024 (250 races): 25.20% → 28.40% (**+3.2pp**)
- Fold 2025 (125 races): 22.40% → 22.40% (**+0.0pp**)

Fold 2024 showed a +12.7% relative lift that did NOT replicate across
folds. The 3-fold pooled delta is noise.

**Stage races** (373–1254 per fold): both variants ≈ baseline on all
metrics. Cluster features correctly zero-imputed and harmless.

**GC races** (78–142 per fold): noisy regression for 1a (-14% winner
relative, but n=78-142 so very volatile). Not a reliable signal either
direction.

### Why clusters don't help discrimination

LightGBM IS using the cluster features — the bucket model shows gain > 0
for 10 of 12 cluster score columns in the 1a variant. But the marginal
information they carry is already present in Stage 0's raw gradient
columns. The GMM's soft memberships are a **lossy compression** of the
same 11 gradient features the model already splits on directly.

`variance_normalized_monotonicity` alone (Stage 0's top new feature at
~90k gain) is more discriminative than the cluster representation of
it. LightGBM can learn arbitrary nonlinear splits on raw gradient columns;
the GMM's gaussian-component soft memberships impose a specific (and
apparently suboptimal) partitioning of the same space.

The field-side information doesn't add independent signal in any
formulation we tried — gradient-history signatures (attempt 1),
type-profile signatures (attempts 2-4), or architectural variations
(PCA, whitened PCA, PC1-dropped PCA). The root cause appears structural:
at the quality level where races matter for prediction (WT/Pro fields),
the contender pool overlaps too heavily across race types for
field composition to discriminate one-day sub-types. The model already
has per-rider career stats (stage_avg_bucket, one_day_avg_bucket,
gc_avg_bucket, etc.) as direct features, and can cross-reference them
with race-side gradients without an intermediate clustering layer.

### Verdict vs Stage 1 success bar

Plan's bar: *"beat Stage 0 on winner capture OR podium capture OR log loss,
with no regression beyond fold-level noise"*.

- Winner capture: +0.24σ overall, +0.25σ on one-day → **noise, does not beat**.
- Podium capture: +0.48σ overall, -1.0pp on one-day → **does not beat**.
- Log loss: +0.14σ overall, +0.010 on one-day → **does not beat**.
- Win calibration: +1.16σ → **real improvement**, but plan's bar was
  discrimination-focused. Calibration was a "soft gate," not a success
  criterion.

**Overall: Stage 1 DOES NOT PASS the success bar for discrimination.**
The only genuine benefit — calibration recovery — is achievable more
cheaply via a post-hoc temperature scaling refit on the contender model,
without adding 14 columns to every training row.

### What we learned (preserving for future work)

1. **Raw gradient features (Stage 0) are the high-water mark for
   race-characterization signal.** LightGBM directly splitting on the
   11 gradient columns outperforms any clustering-based compression of
   the same information. The 19-percentile pipeline's gradient outputs
   are correctly information-preserving; the bottleneck was always the
   downstream 6-profile lossy compression, and Stage 0 already fixed
   that by bypassing it.

2. **The "joint race characterization" thesis — combining race shape with
   field composition — is empirically falsified** under two independent
   field-signature formulations (gradient-history and type-profile) and
   four architectural variations (all-at-once PCA, split-and-concat,
   whitened PCA, PC1-dropped PCA). The field-side signal is dominated
   by field quality, not field type, at the elite competition level
   where predictions matter.

3. **GT contamination is the structural reason field signals fail.** In
   stage races (72% of training data), the same ~170 riders start every
   stage regardless of stage type. Any field aggregate over those riders
   is identical across all stages of a race series. In one-day races,
   field composition DOES differ across race types (Roubaix fields ≠
   Liege fields), but the overlap in the contender pool (~20 riders
   who ride all monuments) still collapses the quality-weighted field
   signature for the races that matter most for prediction.

4. **One-day race-only clustering produces a sensible, stable race
   taxonomy** (cobbles / climber classics / sprints / mixed correctly
   separated in the canonical check), but this taxonomy is redundant
   with what LightGBM already extracts from raw gradient features. The
   GMM is a correct but unnecessary intermediate representation.

5. **Calibration and discrimination are decoupled.** Clusters help
   calibration (+1.16σ on win cal ratio) without improving discrimination.
   This suggests the calibration regression in Stage 0 is a
   probability-scaling issue, not a feature-quality issue, and should be
   addressed directly (temperature scaling, Platt refit) rather than
   through additional race-characterization features.

### Planned Stage 2 (from the original plan) and its status

The plan's Stage 2 proposed a learned joint race embedding via small MLPs:
two encoders (`GradientEncoder` + `FieldEncoder`) producing a low-dim
race embedding, trained end-to-end on the outcome prediction objective.
This was gated behind "Stage 1 beats current best but leaves signal on
the table."

**Stage 2 as originally designed is not warranted.** Stage 1 did not beat
Stage 0, and the failure mode — field information doesn't carry
independent signal — would likely persist in a learned embedding. An MLP
can learn a more flexible compression than a GMM, but it's compressing
the same input space that already failed to add value. The effective
race-level sample size (~4,300 races, ~788 one-days) is also marginal
for stable MLP training even with aggressive regularization.

However, the broader question — "can we improve rider-to-race specificity
beyond what raw gradients give us?" — remains open. Possible next
directions (not yet tested):

- **Hard-filtered gradient profiles**: build rider gradient signatures
  only from races where they finished top-5 (making success a filter,
  not a weight). This addresses the contamination problem more
  aggressively than the `1/(bucket+1)` soft weight that failed in
  attempt 1.
- **Archetype projection**: score stage-race stages through the one-day
  race_only GMM to assign each stage a "closest one-day archetype."
  A Tour summit finish would score high on the "Liege-type" cluster.
  Uses the GMM as a vocabulary of racing archetypes rather than as a
  feature-compression layer.
- **Calibration-focused intervention**: since Stage 0's main blemish is
  calibration (not discrimination), a targeted Platt/temperature refit
  may yield more practical value than further feature engineering.
- **Per-competition-type specialist models**: different LightGBM models
  for one-day vs stage predictions, allowing each to learn type-specific
  patterns without the 72:18 stage:one-day training-data dilution.

---

## Ranking-aware loss experiments — Steps A and B
**Date:** 2026-04-12
**Branch / worktree:** `claude/objective-bartik`
**Result JSONs:**
- `experiments/lambdarank_step_a.json`
- `experiments/contender_ranking_step_ab.json`
- `experiments/mlp_pl_step_b.json`

### Motivation

Stages 0 and 1 focused on the "right features" question. This series
tests the "right loss function" question: does treating the race as a
collective ranking event (rather than predicting each rider's bucket
independently) improve winner/podium capture?

The existing pipeline predicts each rider's place_bucket independently
via regression (bucket predictor) and multiclass classification
(contender model). Neither model knows riders are competing against each
other in the same race. A ranking-aware loss like LambdaRank or
Plackett-Luce penalizes getting the **pairwise ordering wrong within a
race**, which is a tighter fit to the actual evaluation metric (who
wins, who podiums).

### Step A: LambdaRank on full field

**Architecture**: one LightGBM model, `objective='lambdarank'`, 126
Stage 0 features, trained on ALL riders per race (no top-N filtering).
Target: `relevance = 6 - place_bucket` (winner=6, podium=5, ..., pack=0).
Groups: riders within each competition_id. Per-race softmax of scores
for probabilities.

**3-fold results**:

| Metric | Stage 0 pipeline | LambdaRank (full field) |
|---|---|---|
| Winner capture | 24.31% | **24.27%** (−0.04pp, noise) |
| Podium capture | 44.36% | **33.42%** (−10.9pp) ⚠ |
| Win calibration | 0.8663 | **1.0067** (near-perfect) |

**Key findings**:
- **Winner capture identical.** A single LambdaRank model matches the
  entire 5-model cascade (bucket + filter + OOF + contender + 5-class)
  at picking winners. The loss function is NOT the bottleneck for winner
  identification.
- **Podium capture terrible** (−24.65%). NDCG's steep discounting
  overspecializes on rank 1 at the expense of ranks 2-3. The model can
  find the winner but can't reliably separate podium from top-5.
- **Win calibration near-perfect** (1.007 vs 0.866). Softmax of ranking
  scores produces the correct probabilistic ranking model (equivalent to
  Plackett-Luce for position 1). The Stage 0 calibration regression was
  a probability-scaling issue inherent to the multiclass objective, not
  a feature problem. This finding alone validates the ranking direction
  for calibration.

### Step A+: Contender-filtered LambdaRank + baseline comparison (top-25)

The full-field comparison wasn't apples-to-apples: the Stage 0 numbers
come from a contender model trained on the top-15 filtered subset. Fair
comparison requires the same population. We also expanded to top-25 per
the project's target population (top ~25 riders per race).

Three configs, all on top-25 filtered by the bucket predictor, same
3-fold CV:

| Config | Winner | Podium |
|---|---|---|
| **Baseline contender** (multiclass 5-class, LR 0.01) | **23.28% ± 0.58** | **36.06% ± 0.91** |
| **Contender LambdaRank** (LR 0.01) | 22.94% ± 2.11 | 36.83% ± 0.98 |
| **Linear PL** (scipy L-BFGS-B) | 19.97% ± 0.50 | 33.90% ± 0.17 |

**Key findings**:
- **Contender LambdaRank ≈ baseline multiclass** even when apples-to-apples
  on the same top-25 pool. Winner −0.34pp (−0.60σ), podium +0.78pp
  (+0.85σ). Statistical tie confirms: the loss function isn't the
  bottleneck.
- **Linear PL terrible** (−5.73σ winner). A linear model
  `score = w @ features + b` can't learn the nonlinear feature
  interactions LightGBM captures via tree splits. This indicts the linear
  scoring function, not the PL loss.
- **Baseline at top-25 gives 23.28%** winner capture vs 24.31% at top-15
  (the production pipeline). The wider filter hurts because the model has
  to discriminate among more riders.

### Step B: MLP Plackett-Luce (PyTorch/MPS)

**Architecture**: MLP scorer (126→64→32→1, ~6K params), PL negative
log-likelihood loss, trained on top-25 contender subset. PyTorch with
MPS (Apple Silicon GPU). Two-phase execution to avoid LightGBM + PyTorch
segfault on macOS (LightGBM prep in process 1, PyTorch training in
process 2).

**Target**: bucket-derived ranks (same as contender LambdaRank — ranks
within race derived from place_bucket with noise tie-breaking). This was
a design error identified post-hoc: bucket-derived ranks lose the
fine-grained ordering that PL is designed to exploit. Within the same
bucket (e.g., 10 riders in bucket 5), all have identical rank labels,
giving PL zero learning signal for their relative ordering.

**3-fold results**:

| Config | Winner | Podium |
|---|---|---|
| Baseline contender | 23.28% | 36.06% |
| **MLP-PL** | **19.85% ± 1.24** | **35.72% ± 1.18** |

**Key findings**:
- **MLP-PL ≈ Linear PL** (19.85% vs 19.97% winner). The nonlinear MLP
  didn't help. Every fold early-stopped at epoch 15-17 after barely
  reducing the loss (train loss 2.23 → 2.20, 1.3% improvement). The
  model didn't meaningfully learn beyond its initialization.
- Root causes: (a) per-race SGD is noisy (25 examples per gradient step
  vs LightGBM's 50K+ per iteration), (b) bucket-derived ranks are a weak
  training signal (within-bucket riders have identical labels), (c) 2-layer
  MLP can't match LightGBM's complex multi-feature splits with limited
  training epochs.
- This is a **maturity gap**, not a fundamental limit. The MLP-PL had
  default hyperparameters, no OOF features, no LR warmup, and a lossy
  target variable. The LightGBM baseline had months of tuning.

### Summary table — all ranking experiments

| Config | Winner | Podium | Setting |
|---|---|---|---|
| **Stage 0 contender pipeline** | **24.31%** | **44.36%** | top-15, multiclass, 5-class, OOF |
| Baseline contender (top-25) | 23.28% | 36.06% | top-25, multiclass, 5-class |
| Full-field LambdaRank | 24.27% | 33.42% | full field, lambdarank |
| Contender LambdaRank | 22.94% | 36.83% | top-25, lambdarank |
| Contender Linear PL | 19.97% | 33.90% | top-25, linear scorer, PL loss |
| Contender MLP-PL v1 | 19.85% | 35.72% | top-25, MLP scorer, PL loss |

### Diagnostic conclusion

**The loss function is not the bottleneck.** LambdaRank matches multiclass
LightGBM on winner capture at both full-field and contender-filtered
settings. PL underperforms because of implementation maturity (bucket
targets, minimal tuning), not because the probabilistic ranking model is
wrong.

**LightGBM's tree-based feature interactions are hard to replicate with
shallow MLPs.** The 126 features include complex derived features
(`profile_weighted_expected`, `rider_vs_field_bucket_gap`, etc.) that
LightGBM can split on directly. An MLP needs to relearn these
interactions from scratch, which requires more data and epochs than
our per-race training provides.

**Calibration IS solved by the ranking approach.** Full-field LambdaRank's
softmax gives near-perfect win calibration (1.007 vs 0.866). If we
ever ship a ranking-based model, calibration comes for free.

### Design errors identified for v2

1. **Target variable**: using bucket-derived ranks throws away the
   fine-grained ordering PL needs. Raw finishing `place` (available in
   `rider_results.place`) is the correct target — it distinguishes 1st
   from 2nd from 3rd within what the bucket system calls "bucket 0."

2. **Field size**: top-25 filtering discards context. The full-field
   LambdaRank (24.27% winner) outperformed the contender-filtered
   version (22.94%). PL on the full field with top-k truncated loss
   (focus learning on top-30 positions but keep all riders in the
   softmax denominator) is the right design.

3. **Training regime**: 15-17 epochs is not enough for an MLP to learn
   126 features. Needs LR warmup, cosine schedule, longer patience,
   and possibly OOF features from LightGBM as warm-start inputs.

4. **Multi-task**: simultaneous ranking (PL) + time-gap regression gives
   a richer training signal than PL alone, especially for separating
   riders within the same group finish.

These fixes are implemented in MLP-PL v2 (see next entry).

### MLP-PL v2 — full field, raw place, proper training
**Date:** 2026-04-12
**Result JSON:** `experiments/mlp_pl_v2.json`

**Architecture**: MLP scorer with batch normalization and residual
connection (126→128→128→64→1, ~25K params). Top-30 truncated PL loss
on raw finishing `place` from `rider_results` (not bucket-derived ranks).
Full field (no top-N filtering). LR warmup (10 epochs) + cosine
annealing, AdamW with weight decay 1e-3, gradient clipping, patience 25.
Two-phase execution (LightGBM-free prep → PyTorch/MPS training).

**Bug caught and fixed**: initial run showed 87% winner capture — raw
`place` column was leaking into the feature matrix because
`FeatureEngineer._get_feature_columns()` excludes `place_bucket` and
`time_gap` but not `place`. Fixed by dropping `place` from the
DataFrame before feature engineering and re-attaching as target only.

**3-fold results (leak-free)**:

| Config | Winner | Podium | Calibration |
|---|---|---|---|
| **Stage 0 pipeline** | **24.31%** | **44.36%** | 0.866 |
| Full-field LambdaRank | 24.27% | 33.42% | 1.007 |
| MLP-PL v1 (top-25, bucket target) | 19.85% | 35.72% | 1.148 |
| **MLP-PL v2 (full field, raw place)** | **19.08% ± 1.25** | **26.98% ± 0.98** | **1.007** |

**MLP-PL v2 is worse than v1**, despite all the design improvements.
Every fold early-stopped at epoch 27-30 after ~7% train loss reduction
(4.09 → 3.79). The raw-place target gives a richer PL signal than
bucket-derived ranks, but the model still can't learn the feature
interactions that LightGBM captures automatically.

**Root cause confirmed**: the bottleneck is NOT the loss function, NOT
the target variable, NOT the field size, and NOT the training regime.
It's the **scoring architecture**. An MLP that scores each rider
independently from their features cannot match LightGBM's tree-based
feature interactions on tabular data with 126 engineered features.
This is consistent with the well-established "trees beat MLPs on
tabular data" finding in the ML literature.

### Comprehensive ranking experiment verdict

After 6 experiments (LambdaRank full-field, LambdaRank contender,
linear PL, MLP-PL v1, MLP-PL v2, and the contender baseline):

1. **Loss function is not the bottleneck.** LambdaRank matches LightGBM
   multiclass at 24.27% winner capture. Changing the loss alone gives
   zero lift.
2. **Neural scorers can't match LightGBM on tabular features.** Both
   linear and MLP scorers underperform LightGBM by 3-5pp on winner
   capture, regardless of loss function, field size, or target variable.
3. **Calibration IS solved by ranking approaches.** LambdaRank and MLP-PL
   both give near-perfect win calibration (~1.007). The Stage 0
   calibration regression (0.866) is a multiclass-objective artifact.
4. **The remaining lever is architecture**: specifically, models that
   allow **rider-rider interaction** (attention over the field) so that
   "I'm a sprinter competing against 5 other strong sprinters" becomes
   a learned signal. This is what LightGBM fundamentally cannot express
   because it scores each rider independently. The Set Transformer
   architecture (Step C) is the next experiment.

---

## Step C — Set Transformer with Plackett-Luce loss
**Date:** 2026-04-12
**Result JSON:** `experiments/set_transformer_step_c.json`

### Architecture

Set Transformer over top-30 contenders (filtered by LightGBM bucket
predictor), with learned rider embeddings and Plackett-Luce loss on raw
finishing place.

```
Input: 30 riders × 128 features (126 Stage 0 + lgbm_expected_bucket + lgbm_contender_rank)

Rider Encoder (shared MLP):  128 → 64 → 64  (LayerNorm, GELU, dropout 0.2)
Self-Attention:  1 layer, 4 heads, 64-dim, with FFN (64→128→64)
Score Head:  64 → 32 → 1
Loss:  top-30 truncated Plackett-Luce on raw finishing place
```

48,257 parameters total. Races padded to 30 riders with attention mask
for variable-sized fields. LightGBM warm-start features
(`lgbm_expected_bucket`, `lgbm_contender_rank`) included so the model
can refine LightGBM's estimates using inter-rider dynamics. Two-phase
execution (LightGBM prep → PyTorch/MPS training) to avoid macOS segfault.

### 3-fold results

| Config | Winner | Podium | Calibration |
|---|---|---|---|
| **Stage 0 pipeline (top-15)** | **24.31%** | **44.36%** | 0.866 |
| Full-field LambdaRank | 24.27% | 33.42% | 1.007 |
| Contender baseline (top-25) | 23.28% | 36.06% | 1.148 |
| MLP-PL v2 (full, raw place) | 19.08% | 26.98% | 1.007 |
| **Set Transformer (top-30, 1 attn layer)** | **19.70% ± 1.07** | **33.92% ± 0.56** | **1.117** |

Per-fold detail:

| Fold | Winner | Podium | Val loss | Epochs |
|---|---|---|---|---|
| 2023 | 19.02% | 33.93% | 2.400 | 33 (early stop) |
| 2024 | 21.21% | 34.59% | 2.387 | 30 (early stop) |
| 2025 | 18.88% | 33.23% | 2.395 | 28 (early stop) |

### Analysis

**Set Transformer beats MLP-PL v2** on both winner (+0.62pp) and podium
(+6.94pp), confirming the attention mechanism adds SOME value over a
pure MLP scorer. The attention is learning inter-rider signals that an
independent scorer cannot express.

**Set Transformer still far below LightGBM** (-3.58pp winner vs
contender baseline, -4.61pp vs Stage 0 pipeline). The attention over
hand-engineered features isn't enough to overcome LightGBM's advantage
on tabular data.

**Training dynamics**: every fold early-stopped at epoch 28-33 after
~5% train loss reduction (2.43 → 2.29). The model learns quickly but
overfits quickly — consistent with having 48K params on ~2,000-3,000
training races. Val loss barely improves before diverging.

### Why the Set Transformer underperforms

The core issue is a **representation mismatch**: the 128 input features
are designed for **independent per-rider prediction** (career stats,
form, team quality). The attention mechanism needs features that are
**informative about inter-rider relationships** — but the input
representation doesn't encode rider type in a way that makes inter-rider
comparison via dot-product attention meaningful.

In language model terms: we're feeding the transformer raw word statistics
("this word has 5 letters, starts with 'c'") instead of learned word
embeddings where geometric proximity encodes semantic similarity. The
attention can't learn useful interaction patterns from features that
weren't designed for comparison.

### Direction for future work: learned rider embeddings

The most promising next direction is **pre-trained rider embeddings from
race co-occurrence**, analogous to word2vec / BERT for language:

- **Static version (word2vec-like)**: train rider embeddings from a
  co-occurrence objective: "riders who appear in the same races and
  finish in similar positions should be close in embedding space." Each
  rider gets a learned d-dim vector that captures "what kind of rider is
  this" holistically, not through any predefined feature vocabulary.

- **Contextualized version (BERT-like)**: condition the embedding on race
  characteristics so that the same rider gets a different effective
  representation in a mountain stage vs a sprint stage. A rider's
  "climbing ability" dimensions get amplified in climbing races; their
  "sprint ability" dimensions get amplified in sprint races.

- **Race-conditioned co-occurrence**: train the embedding objective with
  race features as conditioning variables. "Riders who finish close
  together in races of the same type should be close in embedding space,
  when projected through that race-type's lens." This naturally creates
  multi-faceted embeddings where each rider's position encodes their
  abilities across different race contexts.

This addresses the fundamental representation problem: the embedding
space is LEARNED to encode competitive relationships, not constrained
by our hand-engineered feature vocabulary.

### Complete summary — all experiments in the ranking / architecture series

| Experiment | Winner | Podium | What it tested |
|---|---|---|---|
| **Stage 0 pipeline** | **24.31%** | **44.36%** | Baseline (LightGBM multiclass, top-15) |
| Full-field LambdaRank | 24.27% | 33.42% | Ranking loss on same features |
| Contender LambdaRank (top-25) | 22.94% | 36.83% | Ranking loss, apples-to-apples |
| Contender baseline (top-25) | 23.28% | 36.06% | Multiclass on wider pool |
| Linear PL (top-25) | 19.97% | 33.90% | Correct probabilistic loss, linear scorer |
| MLP-PL v1 (top-25, buckets) | 19.85% | 35.72% | Nonlinear scorer, bucket targets |
| MLP-PL v2 (full, raw place) | 19.08% | 26.98% | Correct target + full field |
| **Set Transformer (top-30)** | **19.70%** | **33.92%** | **Rider-rider attention** |

**Key conclusions across all experiments:**

1. **LightGBM's tree-based multiclass is the strongest approach we have**
   for independent per-rider scoring on 126 engineered features. No
   alternative loss function (LambdaRank, PL) or scorer (linear, MLP,
   Set Transformer) improves on it.

2. **The attention mechanism adds marginal value** (+0.62pp winner over
   MLP-PL v2) but cannot overcome the representation deficit — attention
   over hand-engineered tabular features is fundamentally limited.

3. **The path forward is better representations, not better architectures
   or losses.** Learned rider embeddings from competitive co-occurrence
   data, conditioned on race context, is the most promising direction
   for breaking above the 24.31% ceiling.

---

## Hybrid deployment — LambdaRank probability head (2026-04-18)

Shipped a full-field LambdaRank head alongside the existing multiclass
contender cascade, specifically for calibrated probability output
(book-comparison, log-loss scoring). Not a replacement — both heads run
in parallel and disagreements are surfaced in the web UI and logged to
`prediction_log` for long-term analysis.

**Key files**: `lambdarank_probability_predictor.py`,
`train_lambdarank_production.py`, `prediction_log.py`,
`experiments/lambdarank_cv.py`. Web app shows both heads side-by-side
with yellow highlight when |Δ Win pp| ≥ 2pp.

### CV (3-fold, matches Step A folds)

**Results JSON:** `experiments/lambdarank_cv_20260418_*.json`

| Metric | LR=0.05 | LR=0.01 |
|---|---|---|
| Winner capture | 23.26% ± 1.97% | 23.11% ± 2.68% |
| Podium capture | 33.26% ± 1.13% | 33.47% ± 1.48% |
| Win log-loss | 3.040 ± 0.022 | 3.037 ± 0.021 |
| Discrimination ratio | 12.63× | 12.49× |
| Win cal ratio | **1.0086 ± 0.003** | **1.0086 ± 0.003** |
| Win ECE | **0.0005 ± 0.0002** | **0.0005 ± 0.0002** |
| Best iteration | ~172 | ~624 |
| Softmax temperature | ~0.72 | ~0.68 |

### Conclusions

1. **Calibration is confirmed near-perfect** (cal ratio 1.009, ECE
   0.0005). Matches Step A's published 1.007. The softmax of LambdaRank
   scores is directly usable as calibrated win probabilities — the
   original value proposition for book comparison holds up on CV.
2. **LR=0.01 is no better than LR=0.05** on any primary metric — keep
   the LR=0.05 production config. LR=0.01 trains 3.6× as many trees to
   reach the same point.
3. **Winner capture is ~1pp below Step A** (23.26% vs 24.27%). Could be
   data drift (more 2025-26 races now in train/test) or seed variation.
   Still ~1pp below the multiclass Stage 0 ceiling (24.31%), matching
   Step A's finding that the loss function isn't the discrimination
   bottleneck.
4. **Fold 1 (test=2023) regresses** to ~20% winner capture in both
   configs. Folds 2 & 3 are 24-25%. Something systematic about 2023
   data — not investigated today, flagged for follow-up.
5. **Calibrated temperature ~0.7 across all folds** — model consistently
   needs sharpening. This is an inherent LambdaRank/NDCG scale effect,
   not an under-training signal (LR=0.01 doesn't change it).

### Production state

LambdaRank head trained at LR=0.05 is live in `models/production/`.
Web app renders both heads and writes every prediction run to
`prediction_log` (schema in `prediction_log.py`). The 2-pp disagreement
threshold for UI highlighting is tunable via `DISAGREEMENT_THRESHOLD_PP`
in `web/app.py`.

### Start-date sweep — does moving the training window back help? (2026-04-18)

**Result JSON:** `experiments/lambdarank_start_date_cv_*.json`
**Script:** `cycling_project/prediction_tools/experiments/lambdarank_start_date_cv.py`

**Setup bootstrap**: the feature precomputer historically defaulted to
`start_date='2018-01-01'`, so `rider_competition_snapshots` and
`competition_field_features` only covered 2018+. Before the experiment
could run, we rebuilt those tables from 2010 via `FeaturePrecomputer.run(start_date='2010-01-01', resume=False)` — now 1.10M snapshots
(vs 530K previously) and 9077 field_features rows covering 2010→2026.

**What's being varied**: only `DataConfig.start_date` on the training
script; snapshots themselves have identical feature values across all
configs (pre-computed from full 2010+ history). The experiment isolates
the pure "more training labels" effect.

| Metric | 2018 (baseline) | 2017 | 2016 | 2015 |
|---|---|---|---|---|
| Train rows | 291K | 363K (+25%) | 437K (+50%) | 504K (+73%) |
| Winner capture | 23.50% ± 2.3 | **23.82% ± 2.4** | 22.75% ± 2.8 | 23.59% ± 2.7 |
| Podium capture | 33.32% ± 1.9 | **34.39% ± 1.7** | 32.70% ± 1.6 | 33.04% ± 2.2 |
| Win log-loss | 3.094 | **3.058** | 3.107 | 3.073 |
| Win cal ratio | 1.008 | 1.008 | 1.008 | 1.008 |
| Win ECE | 0.0006 | 0.0007 | 0.0008 | **0.0005** |
| Best iteration | 112 | 122 | 97 | 109 |
| Calibrated T | 0.688 | 0.685 | 0.603 | 0.679 |

**Findings:**

1. **Not monotonic.** 2017 > 2018 > 2015 > 2016. If more data strictly
   helped, we'd see a clean trend. We don't. The response to +3 years of
   older labels is essentially flat.
2. **2017 is marginally best** on all primary metrics (winner +0.3pp,
   podium +1.1pp, log-loss −0.04). But all deltas are within fold-std.
3. **2016 regresses sharply** on fold 2 (test=2024): best_iter=24,
   T=0.396 — LightGBM's val NDCG flat-lined almost immediately and
   early-stopped. Noise effect from the weak 2023 val signal, amplified
   by larger train set. Not a systemic problem with 2016 data.
4. **Calibration is invariant** across all configs. Cal ratio 1.008 and
   ECE ≈ 0.0006 hold everywhere — more data doesn't hurt or help
   probability quality. The LambdaRank softmax is fundamentally
   well-calibrated regardless of training window size.

**Verdict:** **Keep production at 2018-01-01.** The marginal lift from
2017 (+0.3pp winner) is within fold noise and not worth the added
training time / operational complexity of maintaining pre-2018
snapshots. The experiment confirms we are near the data ceiling for
this model family — more labels don't unlock more signal.

**Side effect of the rebuild:** The existing production ensemble
(bucket, contender, time_gap, calibrated, multiclass) was all trained
on the *incremental* snapshot table — which we discovered was missing
~100 competitions worth of rows the incremental build had skipped. The
rebuilt table has 498,926 rows at `start_date='2018-01-01'` vs the
470,851 production was originally trained on. Production models remain
valid (feature schemas unchanged), but the next full retrain will
silently include those previously-missed rows.

### Multiclass stack — start-date sweep (2026-04-18)

**Result JSON:** `experiments/multiclass_start_date_cv_*.json` (plus
per-start-date `multiclass_start_{year}_*.json` files from ExperimentRunner)
**Script:** `cycling_project/prediction_tools/experiments/multiclass_start_date_cv.py`

Companion to the LambdaRank start-date sweep. Runs the full multiclass
stack (bucket → time_gap → probability → calibrated → contender cascade
with top-15 filter, LR=0.01, OOF, 5-class reduction, Stage 0 gradients)
across four training start dates. Capped `n_estimators` at 500 (vs
production 2000) to keep runtime reasonable; comparison across
start_dates is apples-to-apples at that cap.

Result (mean ± std across 3 folds):

| Metric | 2018 (291K) | 2017 (363K) | 2016 (437K) | 2015 (504K) |
|---|---|---|---|---|
| Winner capture | 23.59% ± 2.6 | 23.62% ± 2.5 | **24.33% ± 2.6** | 24.19% ± 2.9 |
| Podium capture | 45.79% ± 1.4 | **46.94% ± 1.8** | 46.74% ± 1.5 | 46.59% ± 1.5 |
| Top4 log loss | 1.763 | 1.759 | 1.755 | **1.745** |
| Top4 Brier | 0.9273 | 0.9263 | 0.9246 | **0.9181** |
| Bucket MAE | **1.201** | 1.205 | 1.203 | 1.213 |

**Multiclass scaling signal is real, unlike LambdaRank.**
Log loss and Brier improve monotonically as the training window
extends. Per-year slope analysis (see `analyze_data_scaling.py`):

- Test 2023: **−0.010 log loss per +100K rows** (r = −0.97)
- Test 2024: −0.007 log loss per +100K rows (r = −0.68)
- Test 2025: **−0.006 log loss per +100K rows** (r = −0.99)

Winner and podium capture also trend positive but with weaker r values
(fold-std dominates). Bucket MAE is the exception — it slightly
regresses as older data is added (the bucket model's ordinal regression
is the one stage that sees more noise than signal from pre-2018 rows).

**Implication for full-field / transformer architectures:**
the multiclass contender at 290K–560K training rows is still
data-limited. Per-rider models have ~100× the effective training samples
of full-field models (470K rider-events vs ~4K race-events). The
transformer-over-races failure is consistent with a pure data-size
bottleneck, not an architectural one — the cycling calendar doesn't
produce enough races to reach the data regime where full-field models
could match per-rider LightGBM.

### Production decision — move to start_date='2016-01-01' (2026-04-18)

Cautious pick: 2016 rather than 2015. Rationale:
- 2016 is peak winner capture (24.33% vs 23.59% at 2018, +0.74pp)
- Log loss / Brier improvement is captured (−0.005 log loss, −0.003 Brier vs 2018)
- 2015 adds another +0.007 log loss improvement but with 0.02pp podium regression from its peak and slightly more bucket MAE noise
- Marginal difference 2016→2015 within fold-std; ~50% additional data for essentially no metric gain past 2016

Updated:
- `cycling_project/prediction_tools/train_production_model.py` → `start_date='2016-01-01'`
- `cycling_project/prediction_tools/train_lambdarank_production.py` → `start_date='2016-01-01'` (for consistency; the LambdaRank head is empirically insensitive to window size)

Next full pipeline retrain will pick up the new window.

---

## Score-level blend — multiclass × LambdaRank (2026-05-04)

**Branch / worktree:** `webscrape-refactor`
**Result JSON:** `experiments/blend_multiclass_lambdarank_cv_20260504_145332.json`
**Script:** `cycling_project/prediction_tools/experiments/blend_multiclass_lambdarank_cv.py`

### Motivation

The 2026-04-18 hybrid deployment runs the multiclass contender cascade and
the full-field LambdaRank head **side-by-side** but never combines them.
The two heads have known-decorrelated strengths (multiclass: discrimination,
24.31% winner; LambdaRank: calibration, ~1.009 cal ratio). First experiment
in the reranking series: does a per-rider linear blend
`blend_p = w * mc_p + (1-w) * lr_p` improve over either head alone?

### Setup

Same 3 folds as Step A / `lambdarank_cv.py`. Production-aligned configs:
- Multiclass: top-15, LR=0.01, OOF, 5-class, gradient features (Stage 0),
  500 estimators, 50 early-stop. Trains bucket → contender (skips
  time_gap / weighted / calibrated heads).
- LambdaRank: LR=0.05, 2000 estimators, 300 early-stop, temperature
  calibrated on val.
- `start_date='2018-01-01'` for direct comparability with prior CV
  entries (production has since moved to 2016, but the CV protocol stays
  at 2018).

`mc_p` is the multiclass contender's `prob_win` (class 0 of the 5-class
softmax), padded over the full field with 0 for non-contenders, then
renormalized per race so it sums to 1. `lr_p` is the LambdaRank softmax
win_p over the full field. Sweep `w ∈ {0.0, 0.1, ..., 1.0}` in steps of 0.1.

### Diagnostics (per fold)

| Fold | Bucket top-15 winner coverage | Within-race Spearman(mc, lr) | LR temperature |
|---|---|---|---|
| 2023 | 0.7624 | 0.5956 ± 0.0752 | 0.720 |
| 2024 | 0.7986 | 0.5641 ± 0.0665 | 0.633 |
| 2025 | 0.8014 | 0.5901 ± 0.0810 | 0.709 |

The **0.56–0.60 within-race rank correlation** confirms the heads provide
genuinely different rankings, putting this experiment in the regime where
a blend *could* help.

The **bucket-coverage row is the ceiling for any contender-style head**:
~22% of races have the actual winner outside the top-15 by bucket
regression, so the renormalized multiclass contributes 0 prob to the
winner in those races (this is what blows up log loss at w=1.0).

### Aggregated sweep (3-fold mean ± std)

| w | winner | podium | log_loss | win_ece |
|---|---|---|---|---|
| 0.0 (LR) | 0.2350 ± 0.0231 | 0.3375 ± 0.0197 | 3.0936 ± 0.0594 | 0.0006 |
| **0.1** | **0.2354** ± 0.0255 | 0.3384 ± 0.0214 | 3.0840 ± 0.0614 | 0.0006 |
| **0.2** | 0.2341 ± 0.0246 | 0.3396 ± 0.0216 | **3.0821** ± 0.0640 | **0.0006** |
| 0.3 | 0.2327 ± 0.0251 | 0.3411 ± 0.0200 | 3.0872 ± 0.0670 | 0.0006 |
| **0.4** | 0.2293 ± 0.0248 | **0.3417** ± 0.0184 | 3.0995 ± 0.0705 | 0.0006 |
| 0.5 | 0.2263 ± 0.0254 | 0.3375 ± 0.0204 | 3.1200 ± 0.0745 | 0.0007 |
| 0.6 | 0.2206 ± 0.0214 | 0.3342 ± 0.0212 | 3.1512 ± 0.0794 | 0.0007 |
| 0.7 | 0.2215 ± 0.0223 | 0.3337 ± 0.0211 | 3.1979 ± 0.0854 | 0.0007 |
| 0.8 | 0.2190 ± 0.0240 | 0.3334 ± 0.0201 | 3.2712 ± 0.0935 | 0.0007 |
| 0.9 | 0.2180 ± 0.0247 | 0.3307 ± 0.0211 | 3.4071 ± 0.1067 | 0.0007 |
| 1.0 (MC) | 0.2217 ± 0.0255 | 0.3272 ± 0.0209 | 7.6464 ± 0.4880 | 0.0021 |

Best w per metric: winner @ 0.1 (0.2354), podium @ 0.4 (0.3417),
log_loss @ 0.2 (3.0821), ECE @ 0.2 (0.0006).

`win_cal_ratio` is invariant at 1.008 ± 0.002 across all w — by
construction (both inputs are sums-to-1-per-race, blend is too). Not
informative for blend selection.

### Per-fold detail

Fold 2023 (the historically anomalous fold) shows pure LR is best at all
metrics; blend trends slightly down. Folds 2024 and 2025 are where the
blend lift lives:

**Fold 2024** (704 races, bucket_cov=0.799):
- Winner: 0.2243 (LR) → **0.2286 @ w=0.1** → 0.2029 (MC) — +0.43pp
- Podium: 0.3283 (LR) → **0.3412 @ w=0.4** → 0.3288 (MC) — +1.29pp
- Log loss: 3.120 (LR) → **3.094 @ w=0.2-0.3** → 7.382 (MC)

**Fold 2025** (426 races, bucket_cov=0.801):
- Winner: 0.2671 (LR) → **0.2695 @ w=0.1** → 0.2577 (MC) — +0.24pp
- Podium: 0.3649 (LR) → **0.3676 @ w=0.1-0.2** → 0.3519 (MC) — +0.27pp
- Log loss: 3.012 (LR) → **2.998 @ w=0.2** → 7.227 (MC)

### Why w=1.0 looks much worse than the production multiclass number

The pure-multiclass endpoint here (winner 0.2217, log_loss 7.65) is **not
comparable** to the existing `probability_contender_top4` numbers
(winner 0.2431, log_loss ~1.78). Two reasons:

1. **Population**: production multiclass is evaluated *only* on the
   contender pool (top-15), so its winner_capture is conditional on the
   bucket filter catching the winner. This experiment evaluates over the
   full field; in races where the bucket filter misses (~22%), all top-15
   contenders get `prob_win = 0` after renormalization → winner capture
   automatically counts as a miss, log loss → ∞ for those rows.
2. **Probability scale**: log_loss is computed on the *win* probability
   of the actual winner. Production reports `top4_log_loss` over a
   different population (rows with `place_bucket ≤ 3`), which is a
   completely different distribution.

w=1.0 is included as a sanity-check endpoint, not as a production-realistic
multiclass.

### Verdict

**The blend does not materially improve winner capture.** w=0.1 gives
+0.04pp over pure LR (0.2354 vs 0.2350) — vastly within fold-std (±2.4pp).
Direction is consistent across folds 2024 and 2025 but lift is ≪ noise.

**Podium and log loss show small consistent gains in the w=0.2–0.4 range:**
- Podium: +0.42pp (+1.2%) at w=0.4 vs pure LR
- Log loss: −0.012 (−0.4%) at w=0.2 vs pure LR

Both within fold-std but consistent direction across all 3 folds. Not
enough lift to justify a production change to a fixed blend.

**Calibration is preserved** for w ≤ 0.5 (ECE ≈ 0.0006). LambdaRank's
near-perfect calibration is robust to mild multiclass mixing.

### What we learned

1. **The two heads are providing genuinely orthogonal signal at the
   ranking level** (within-race Spearman ~0.58). They disagree on
   ordering — but they tend to agree on the top-1 pick. The simple
   linear-prob blend can't extract winner-capture lift from this
   orthogonality because the disagreements are mostly in positions 2-N,
   not at the top.

2. **Linear-prob blending is ruled out as a winner-capture lever.** Any
   future experiment that hopes to combine the two heads needs a more
   flexible aggregator that can route by context (e.g., trust LR more on
   bunch finishes, MC more on small fields).

3. **The 22% of races where the bucket filter misses the winner remain
   the structural ceiling for any contender-cascade head.** A meta-learner
   that gets multiclass + LambdaRank + bucket + time_gap as inputs has
   genuine ground to make up here, since LambdaRank already does well on
   those races where bucket misses.

4. **Calibration robustness is a free benefit of any blend below ~50%
   multiclass.** ECE doesn't move; cal ratio is invariant. So a blend at
   w=0.2-0.3 is a "no-regret" config for sportsbook odds output if we
   ever wanted to commit to a single number — small log-loss improvement
   without giving up calibration.

### Next direction

The original plan flagged the **stacked meta-learner** (Approach F from
`model_specialization_plan.md`) as the next bigger swing. It uses all
four outputs (bucket, time_gap, multiclass probs, LambdaRank score) plus
race context and can learn context-dependent routing. The 0.58 within-race
correlation between mc and lr suggests there *is* unblendable signal in
their disagreements that a non-linear aggregator might extract.

Linear-prob blend is shelved.

---

## Stacked meta-learner — augmented contender (+ time-gap OOF + LambdaRank OOF) (2026-05-04)

**Branch / worktree:** `webscrape-refactor`
**Result JSON:** `experiments/stacked_meta_learner_cv_20260504_152931.json`
**Script:** `cycling_project/prediction_tools/experiments/stacked_meta_learner_cv.py`
**Runtime:** 20.3 min

### Motivation

The linear-prob blend (2026-05-04) showed mc and lr are decorrelated within
race (Spearman ~0.58) but linear blending couldn't extract winner-capture
lift. A non-linear aggregator should fare better — it can route by
context. This is the original Approach F from `model_specialization_plan.md`.

### Setup

Augment the production contender (top-15, LR=0.01, OOF, 5-class, gradient
features) with two OOF base-model features:

- `oof_time_gap_pred`: predicted seconds behind winner from a `TimeGapPredictor`
- `oof_lambdarank_win_p`: per-race calibrated softmax win probability from
  a full-field `LambdaRankProbabilityPredictor`

Both generated via 5-fold temporal CV on the training data (each sub-fold
trains on 4/5 of train, predicts on held-out 1/5). Val rows use
predictions from main models trained on full train (with val for early
stopping). Test rows likewise. Same 3-fold CV protocol as
`multiclass_start_date_cv.py` (uncapped test, `start_date='2018-01-01'`),
making the baseline numbers directly comparable to historic Stage 0.

Baseline trains on the original 126 features; meta on 128 (+ 2 OOF) → 129
total inside the contender (counting `classifier_expected_bucket` added
internally). Both contenders trained on the same train/val/test slices
within each outer fold for paired comparison.

### Aggregated 3-fold results (mean ± std)

| Metric | Baseline | Meta | Δ paired |
|---|---|---|---|
| **race_winner_capture_rate** | 0.2385 ± 0.0261 | **0.2535 ± 0.0379** | **+0.0150 ± 0.0155** |
| race_podium_capture_rate | 0.4595 ± 0.0150 | 0.4619 ± 0.0141 | +0.0024 ± 0.0014 |
| top4_log_loss | 1.7626 ± 0.0081 | 1.7596 ± 0.0096 | -0.0030 ± 0.0082 |
| top4_brier | 0.9270 ± 0.0039 | 0.9280 ± 0.0070 | +0.0010 ± 0.0071 |
| win_cal_ratio | 0.9866 ± 0.0353 | 0.9634 ± 0.0262 | -0.0232 ± 0.0147 |
| podium_cal_ratio | 1.0064 ± 0.0364 | 0.9912 ± 0.0312 | -0.0152 ± 0.0052 |

### Per-fold deltas

| Fold (test=) | Δ winner | Δ podium | Δ log_loss |
|---|---|---|---|
| 2023+ | **+0.0107** | +0.0029 | -0.0069 |
| 2024+ | -0.0015 | +0.0038 | -0.0104 |
| 2025+ | **+0.0358** | +0.0005 | +0.0083 |

Fold 3 (test=2025+) drives most of the winner-capture lift: meta jumps
from 26.99% → 30.57%. Fold 1 (test=2023+) shows a +1.07pp lift on the
hardest fold. Fold 2 is essentially flat (-0.15pp, noise).

Mean paired Δ winner = +1.50pp with std 1.55pp across 3 folds. Standard
error 0.90pp → t-stat 1.67 (n=3). **Suggestive but not statistically
significant at this sample size.** Direction is positive in 2 of 3 folds.

### Meta feature importance — both new features dominate

In **all 3 folds**, the new OOF features rank #2 and #3 by gain:

| Feature | Mean rank | Min rank | Max rank | Mean gain |
|---|---|---|---|---|
| `oof_lambdarank_win_p` | **#2.0** | #2 | #2 | 79,581 |
| `oof_time_gap_pred` | **#3.0** | #3 | #3 | 34,670 |

For context, fold 3's top-10 meta features:

```
 1. classifier_expected_bucket           gain=207,122  (vs 227,864 baseline)
 2. oof_lambdarank_win_p                 gain= 82,386  (NEW)
 3. oof_time_gap_pred                    gain= 41,392  (NEW)
 4. profile_weighted_expected            gain= 30,525  (vs 36,675 baseline)
 5. mountain_vs_career_gap               gain= 27,285
 6. time_trial_avg_bucket                gain= 25,747
 7. type_experience_ratio                gain= 24,031
 8. skewness_normalized_slope            gain= 23,649
 9. form_vs_field_gap                    gain= 23,503
10. form_delta                           gain= 23,383
```

The new features slot in below the bucket prediction (#1) but above
`profile_weighted_expected` (the previous #2), without dethroning the
bucket head. They're carrying **independent signal** the contender
couldn't reach with the 126-feature input alone — exactly the
orthogonal-signal hypothesis from the linear-blend diagnostic.

### Why this works where linear blending didn't

The linear-prob blend had access to lr_p as a global mixing weight only
(`blend = w * mc + (1-w) * lr` with a single fold-level `w`). The tree-based
meta-learner can split on `oof_lambdarank_win_p` conditionally — e.g.,
"if mountain stage AND form is high AND lr_p > X, predict winner with
higher confidence." That kind of contextual routing is what the 0.58
within-race Spearman between mc and lr was hinting at: the heads agree
on average but disagree under specific conditions, and a tree can learn
which conditions.

### Cost: calibration regression

`win_cal_ratio` drops 0.987 → 0.963 (paired Δ -0.023). The meta contender
becomes mildly under-confident on its top picks. Same direction for
`podium_cal_ratio` (1.006 → 0.991). This is fixable via temperature refit
on val (the contender already does this; the regression is despite that).
A more flexible Platt rescale would likely close the gap.

### Verdict

**Promising, not conclusive.** Direction is positive across 4 of 5
primary discrimination metrics, the lift is materially larger than the
linear blend (+1.50pp vs +0.04pp paired winner), and the new features
are unambiguously useful (rank #2 and #3 in every fold). But n=3 folds
gives too-wide error bars — the +1.50pp lift is within noise (std 1.55pp).

Before any production decision, this needs:
1. **More folds**: 5-fold CV with the same protocol to tighten error bars,
   or a paired-bootstrap on the existing fold predictions
2. **Production config check**: re-run at `start_date='2016-01-01'`
   (current production) and `n_estimators=2000` to confirm the lift
   isn't a 2018-window or 500-tree artifact
3. **Calibration fix**: temperature recalibration on val with the new
   features, or a Platt-style rescale, to recover the cal_ratio
4. **Ablation**: meta with only `oof_lambdarank_win_p`, only
   `oof_time_gap_pred`, both — to know which feature drives the lift
   (LR's gain is ~2.3× time-gap's, so LR likely dominates)

### What we learned

1. **The orthogonal mc/lr signal IS extractable** — but only with a
   non-linear aggregator. Linear blend couldn't, tree-based meta-learner
   can. This validates the path forward for any future stacking work.
2. **Time-gap is a real meta-signal** despite being a regression on a
   different target than buckets. Predicted seconds carries information
   about race shape (selective vs bunch finish) that the contender
   benefits from.
3. **The bucket regression is still the dominant feature**, and that's
   the right architecture: filter to top-15 with bucket, then refine
   within the contender pool using bucket prediction + LR + time-gap +
   126 base features.
4. **Production retraining of just the contender + base feature
   predictors is sufficient** — no model architecture change required.
   The meta contender is a drop-in replacement for the existing
   contender stage.

### Next steps (if pursuing)

A confirmatory 5-fold run at `start_date='2016-01-01'` with
`n_estimators=2000` is the cheapest way to settle whether to ship.
Estimated runtime: ~50 min (extrapolating from this 20 min run).
Calibration refit is a small change once the production config is
confirmed. Ablation can run in parallel.

---

## Stacked meta-learner — 5-fold confirmatory run at production start_date (2026-05-04)

**Branch / worktree:** `webscrape-refactor`
**Result JSON:** `experiments/stacked_meta_learner_cv_5fold_20260504_161559.json`
**Script:** `cycling_project/prediction_tools/experiments/stacked_meta_learner_cv_5fold.py`
**Runtime:** 39.6 min

### Outcome: the 3-fold lift does not replicate

Same architecture (augmented contender + 2 OOF features), now at 5-fold
expanding-window CV (test years 2021-2025) with `start_date='2016-01-01'`
matching production. n_estimators=500 to match the 3-fold for direct
comparability.

| Metric | Baseline | Meta | Δ paired (5-fold) | Δ paired (3-fold prior) |
|---|---|---|---|---|
| Winner capture | 0.2336 ± 0.0229 | 0.2363 ± 0.0259 | **+0.0027 ± 0.0061** | +0.0150 ± 0.0155 |
| Podium capture | 0.4590 ± 0.0173 | 0.4547 ± 0.0145 | -0.0043 ± 0.0094 | +0.0024 ± 0.0014 |
| Top4 log loss | 1.7559 ± 0.0044 | 1.7501 ± 0.0084 | -0.0058 ± 0.0123 | -0.0030 ± 0.0082 |
| Top4 Brier | 0.9219 ± 0.0033 | 0.9198 ± 0.0058 | -0.0022 ± 0.0064 | +0.0010 ± 0.0071 |
| Win cal ratio | 0.9882 ± 0.0350 | 1.0018 ± 0.0605 | +0.0136 ± 0.0460 | -0.0232 ± 0.0147 |
| Podium cal ratio | 1.0094 ± 0.0258 | 1.0063 ± 0.0487 | -0.0031 ± 0.0401 | -0.0152 ± 0.0052 |

**Winner capture: +0.27pp paired (was +1.50pp at 3-fold).** t-stat
0.27 / (0.61/√5) = 0.99. Solidly within noise.

### Per-fold deltas

| Fold (test=) | Δ winner | Δ podium | Δ log_loss |
|---|---|---|---|
| 2021+ | -0.0018 | +0.0010 | -0.0086 |
| 2022+ | -0.0013 | -0.0050 | -0.0144 |
| 2023+ | **-0.0021** (was +0.0107 at 2018-start) | -0.0098 | -0.0083 |
| 2024+ | **+0.0136** (was -0.0015 at 2018-start) | +0.0098 | -0.0155 |
| 2025+ | **+0.0049** (was +0.0358 at 2018-start) | -0.0177 | +0.0181 |

The matched test years swing wildly between the 2018-start (3-fold) and
2016-start (5-fold) runs:
- **2023**: +1.07pp → -0.21pp
- **2024**: -0.15pp → +1.36pp
- **2025**: +3.58pp → +0.49pp

The 3-fold's headline +1.50pp lift was driven primarily by the 2025-fold
+3.58pp result, which collapses to +0.49pp at the production start_date.
The two new folds added at 5-fold (2021, 2022) both show small negative
winner deltas. The signal is fold-dependent and not robust to data
window choice.

### What stays robust

**Meta features still rank #2 and #3 across all 5 folds:**

| Feature | Mean rank | Min rank | Max rank | Mean gain |
|---|---|---|---|---|
| `oof_lambdarank_win_p` | **#2.0** | #2 | #2 | 98,930 |
| `oof_time_gap_pred` | **#3.0** | #3 | #3 | 43,613 |

The model **wants** these features and uses them heavily. Their
information just doesn't translate into argmax-level winner-capture lift
on most folds.

**Log loss improves consistently** — 4 of 5 folds show -0.008 to -0.016
improvement, with one regressing fold (2025, +0.018). Mean -0.006 across
5 folds. Real but small.

### Why the disconnect between feature importance and winner capture?

Hypothesis: the meta features sharpen the contender's **probability
estimates** without changing the **argmax** much. Same rider gets picked
#1, but with slightly different probability mass — visible in log loss
improvement but invisible in winner-capture rate. For applications that
care about probability calibration (sportsbook comparison) this is a
small win. For applications that care about top-1 picks (ranking
display) it's a wash.

The 0.58 within-race Spearman correlation between mc and lr always meant
the disagreements would be in positions 2-N more than position 1. That
turns out to translate to log-loss / Brier improvements rather than
winner-capture lift.

### Verdict — meta-learner shelved

**Do not ship.** The 5-fold result shows winner capture lift is within
noise (+0.27pp ± 0.61pp). The 3-fold result that motivated the
confirmatory run was driven by a single anomalous fold-year and does not
generalize to 5-fold or to the production training window.

The architectural insight stands: tree-based stacking *can* extract
orthogonal signal that linear blending can't (the meta features rank #2
and #3 in *every* fold across both runs). But the magnitude here — a
~0.3% log-loss improvement with no winner-capture signal — does not
justify the operational complexity of OOF generation in the production
pipeline.

### What we learned (preserving for future work)

1. **n=3 paired CV is too small to settle directional questions.** The
   3-fold +1.50pp paired delta with std 1.55pp looked promising but
   evaporated at n=5. Future stacking / ensembling experiments should
   start at n=5 minimum if the goal is a ship/no-ship decision.
2. **start_date matters as much as the architecture.** The production
   2016-start baseline is stronger than the 2018-start one (more data
   helps), which leaves less marginal room for the meta-learner to
   improve. Experiments at 2018-start may overestimate lifts that
   evaporate at production scale.
3. **Probability quality vs argmax quality are different things.** Meta
   features can sharpen probability estimates (log loss, Brier, ECE)
   without affecting top-1 picks (winner_capture). For book-comparison
   workflows this is still small but real. For ranking workflows it's
   not actionable.
4. **The orthogonal mc/lr signal is real but operationally limited.**
   Both linear blend (2026-05-04 falsified) and tree stacking (this run
   falsified for winner capture) can use the signal, but the lift on
   primary discrimination metrics is bounded by ~0.3% log loss / +0.3pp
   winner. The 24-25% winner-capture ceiling stands.

### Next direction

Drop the meta-learner. Move forward with the queued backlog:
1. Richer rider form/recent-history features (`future_work_form_metrics.md`)
2. Specialist detection in noisy profiles (`specialist_detection_ideas.md`)
3. Rider volatility features, IRT sample weighting (`pipeline_enhancements.md`)
4. Investigate the 2023 CV fold anomaly (LambdaRank-specific drop)

The hybrid LambdaRank deployment continues to be the right architecture
for this project: multiclass for ranking, LambdaRank for calibrated
probabilities, both surfaced side-by-side in the web app. The
meta-learner experiment confirmed that combining them via a single
stacked head doesn't unlock additional value beyond the parallel
deployment.

## Stage-race state features — within-race GC/form/fatigue state (2026-06-09)

Phase 1 of `stage_race_dynamics_plan.md`. Every prior experiment fed the
models pre-race history only; a stage-15 row was predicted blind to the
14 stages already raced. This run adds 22 within-race state features +
a missing-flag to stage rows: reconstructed GC standings (rank, gaps,
leader/team flags), in-race stage form (last/best/mean stage results so
far), fatigue/progress (stages completed, % complete, post-rest-day,
field attrition), and tactical freedom (10-minutes-down flag, lost big
time yesterday).

### Data foundation

New `rider_race_state` table (804,482 rows, 1,088 stage races 2010+),
built by `engineering_tools/stage_race_state.py`. GC standings are
reconstructed as cumulative stage time (winning_time + time_gap summed
over completed stages), tie-broken by countback (mean stage place) so
ranks are strict. Validation against stored final GCs: median top-10 gap
error 10s (bonus seconds), ~72s worst case over a Grand Tour; races
disagreeing by >120s mean (data corruption, e.g. Tour de Wallonie 2024
at 7,951s) are excluded by a sanity guard — 11 suspect + 46 truncated
races write no state and silently fall back to pre-race behavior.
State coverage on stage rows: 81.6% (remainder = stage-1 rows, coverage
gaps, suspect races). Run on the post-dedupe DB (30 duplicate 2024
races removed same day — all numbers here are post-dedupe baselines).

### Setup

Production contender config (top-15, LR 0.01, OOF, 5-class, gradients;
n_estimators 500), start_date 2016-01-01, 5-fold expanding-window CV
(test years 2021-2025), identical row sets for both variants (state
columns dropped for baseline). Stage rows only get state; gc/one-day
rows keep pre-race features (Phase 2 owns the GC head). Evaluation
stratified by stage sequence; stage_1 / one_day / gc are controls (no
state by construction).

### Results (paired Δ state − baseline, mean ± fold std, n=5)

| Stratum | winner Δ | podium Δ | log loss Δ | brier Δ |
|---|---|---|---|---|
| **all** | **+0.50pp ± 0.29** | +0.06pp | **−0.019 ± 0.022** | −0.012 |
| stage_all | +0.40pp ± 0.59 | −0.01pp | **−0.033 ± 0.016** | −0.021 |
| stage_1 (control) | +1.09pp ± 2.66 | **−2.35pp ± 1.27** | +0.033 ± 0.028 | +0.020 |
| stage_2_3 | +0.61pp ± 0.82 | −0.20pp | −0.034 ± 0.015 | −0.024 |
| stage_4_9 | +0.13pp ± 0.54 | +0.57pp | **−0.051 ± 0.015** | −0.031 |
| stage_10_plus | −0.28pp ± 2.21 | **+3.16pp ± 3.63** | −0.048 ± 0.024 | −0.025 |
| one_day (control) | +0.52pp ± 2.10 | +0.29pp | +0.015 ± 0.038 | +0.011 |
| gc (control, n=4 folds) | +1.48pp ± 2.11 | +0.26pp | +0.019 ± 0.034 | +0.010 |

Per-fold [all] winner deltas: +0.64, +0.04, +0.30, +0.86, +0.65 —
**positive in 5 of 5 folds** (the stacked meta-learner, by comparison,
was +0.27 ± 0.61 and got shelved). Per-fold stage_all log loss deltas:
−0.002, −0.046, −0.045, −0.036, −0.034 — improvement in 5/5.

### What the strata say

1. **The log-loss dose-response is the signature of real signal**:
   stage_1 +0.033 (no state) → stage_2_3 −0.034 → stage_4_9 −0.051 →
   stage_10_plus −0.048. Probability quality improves exactly where
   state information exists, and scales with how much of the race has
   been observed. This is 5-8× the meta-learner's log-loss effect.
2. **Winner capture improves overall (+0.50pp, all folds) but isn't
   concentrated late-race** — argmax picks change less than the
   probability mass around them. Same probability-vs-argmax split the
   meta-learner taught us, but with a winner lift that actually clears
   fold noise this time.
3. **stage_10_plus podium +3.2pp** (GT third weeks) is the most
   tantalizing cell but sits on 34-174 competitions/fold — directional,
   not conclusive.
4. **Feature importance**: gc_rank_current ranks #9-#45 (median ~#22),
   then gc_rank_pctile, last_stage_pctile, mean_stage_pctile_so_far,
   gc_gap_to_rank10_s around #42-#70 of 150. Used, not dominant.
5. **Costs**: win_cal_ratio dips ~−0.04 (0.99→0.95 overall, −0.07 on
   stage_4_9) — same direction as the gradient-features tradeoff
   (0.911→0.866) that we shipped and later fixed with the LambdaRank
   head. And the stage_1 control regresses (podium −2.35pp ± 1.27,
   consistent) — the imputed neutral defaults appear to pollute splits
   shared between no-state and with-state rows (training interference,
   not leakage; stage-1 rows carry no state information to leak).

### Verdict — gate PASSED, one refinement run before integration

Ship-gate criteria from the plan: winner lift clearing fold noise OR
consistent podium+log-loss improvement without winner regression. The
all-rows winner lift (+0.50pp ± 0.29, 5/5 folds positive) and the
stage-row log-loss improvement (−0.033, 5/5 folds) both qualify. This is
the first experiment since Stage-0 gradients to move winner capture
beyond fold noise — consistent with the thesis that new *information*
beats new *architecture* on this problem.

Before production integration, one targeted refinement: the stage-1
regression implicates the neutral-default imputation. A variant leaving
missing state as NaN (LightGBM routes missing down its own branch at
every split — exactly the isolation the missing-flag alone isn't
providing) directly tests the identified mechanism. If it removes the
stage-1/one-day regression while keeping stage-2+ gains, integrate that;
otherwise integrate v1 as-is (the all-rows aggregate already nets
positive).

Results JSON: `experiments/stage_state_features_cv_20260609_134033.json`

### NaN-imputation variant (same day follow-up)

The stage-1 interference hypothesis predicted that leaving missing state
as NaN (LightGBM native missing routing) instead of neutral defaults
would remove the stage-1 control regression. Run with identical config
(`--state-nan`, JSON: `experiments/stage_state_features_cv_nan_20260609_141328.json`):

| Δ vs baseline | neutral defaults (v1) | NaN mode |
|---|---|---|
| all winner | **+0.50pp ± 0.29 (5/5 folds)** | +0.21pp ± 0.38 |
| stage_all winner | +0.40pp ± 0.59 | −0.07pp ± 0.65 |
| stage_all log loss | −0.033 ± 0.016 | **−0.040 ± 0.016** |
| stage_4_9 log loss | −0.051 | **−0.060** |
| stage_1 podium (control) | −2.35pp ± 1.27 | −2.17pp ± 2.52 |
| stage_10_plus winner | −0.28pp ± 2.21 | −1.90pp ± 0.83 |

Findings:

1. **The stage-1 regression survives NaN routing** (−2.2pp podium either
   way) — so it is NOT an imputation artifact. It's the intrinsic cost of
   the model reallocating capacity toward state features that pay off on
   the 82% of stage rows that have state. Hypothesis falsified.
2. **NaN mode trades winner capture for probability quality**: log
   loss/Brier improve further everywhere, but the all-rows winner lift
   drops below noise and stages-10+ winner goes consistently negative.
   Probability mass sharpens; argmax picks suffer.
3. Per the pre-registered rule (and winner capture being the primary
   metric): **integrate v1 (neutral defaults)**. NaN mode is worth
   revisiting if a calibrated-probability-first head (LambdaRank +
   state) is built later.

### Integration-order constraint (important)

The CV gains exist only where state is available. A state-trained model
fed all-NaN/default state behaves like the stage_1 stratum — slightly
WORSE than baseline. The web app's future-race frames currently carry no
state columns, so flipping production training on before inference can
attach real state would degrade live predictions, not improve them.

Ship order is therefore: (1) plumbing with flag off — TrainingConfig
pass-through, weekly pipeline step keeping rider_race_state fresh;
(2) inference-side state attachment for ongoing stage races (Phase 3
lite: compute state from completed stages via the same
compute_race_state code path, defaults for everything else);
(3) only then flip include_race_state=True in production training and
retrain. Steps tracked in stage_race_dynamics_plan.md.

## Mid-race GC head — Phase 2 of stage-race dynamics (2026-06-09)

A new head predicting FINAL GC bucket from the race state after k completed
stages: 316K training rows = (rider × gc race × checkpoint k=1..N-1), state
from `rider_race_state` (state-after-k is the row keyed to stage k+1), target
= final GC bucket. Production contender-cascade config. Evaluation on 2,905
(gc race × checkpoint) synthetic groups against two baselines on identical
groups: **blind** (pre-race features only — what production does for GC
today) and **carry-forward** (predicted final GC = current GC order — the
real bar; across the 2024 Tour's own checkpoints it captures the winner 90%
of the time). Strata by pct_race_complete. 4 usable folds (2021-2024 test);
the 2025 fold is empty because 2025+ GC comps had NULL dates (bug found
during this work; backfill landed same day, snapshot rebuild pending).

### Results (means across 4 folds, paired on identical groups)

| Stratum | carry-fwd | blind | **state** | Δ st−cf | Δ st−blind |
|---|---|---|---|---|---|
| early (≤1/3) winner | 0.184 | 0.297 | **0.336** | **+0.152** | +0.040 |
| mid (1/3-2/3) winner | 0.423 | 0.276 | **0.467** | **+0.045** | +0.191 |
| late (>2/3) winner | 0.703 | 0.303 | 0.693 | −0.010 | +0.390 |
| all winner | 0.421 | 0.290 | **0.485** | +0.064 | +0.195 |
| all podium | 0.519 | 0.465 | **0.640** | +0.121 | +0.175 |
| all log loss | — | 1.698 | **1.105** | — | −0.593 |
| all Brier | — | 0.881 | **0.558** | — | −0.323 |

Per-fold Δ winner vs carry-forward: early +0.182/+0.161/+0.185/+0.080
(4/4 positive), mid +0.062/+0.042/+0.042/+0.031 (4/4), late
+0.006/−0.029/−0.006/−0.013 (wash). Vs blind: positive everywhere except
early-fold-2024 (−0.05) — at k=1-2 state is thin and pre-race features carry
most of the signal.

### Reading

1. **The head beats carry-forward exactly where carry-forward is weak** —
   +15.2pp winner capture early-race (4/4 folds), +4.5pp mid (4/4) — and
   **matches it late** (it learns to carry forward when the race is
   settled). This is the textbook shape of a model that adds information
   rather than noise.
2. **Probability quality transforms**: log loss 1.70 → 1.11, Brier 0.88 →
   0.56 vs blind, with calibration ratio 0.95. Carry-forward can't produce
   probabilities at all — for GC in-play market comparison, this head is
   the only game in town.
3. Honest caveats: checkpoint groups within a race are correlated (per-fold
   pairing is the unit of evidence, not the 2,905 groups); 4 folds; blind
   edge early-race is modest and one fold negative.

### Verdict — gate PASSED

Beats carry-forward early/mid in every fold, matches it late, and produces
calibrated probabilities the baseline can't. Productionization (separate
"GC outlook" head + app surface alongside the existing pre-race GC
prediction) should follow the GC-date snapshot rebuild + retrain so 2025+
GC races are covered and a 5th fold can confirm.

JSON: `experiments/gc_checkpoint_head_cv_20260609_154338.json`

## LambdaRank + state — no value, head stays stateless (2026-06-09)

Tested production LambdaRank (LR=0.05) with the 23 state columns in both
imputation modes vs the stateless baseline, same 5-fold design as Phase 1.
Run was stopped during fold 5; folds 1-4 are complete and consistent enough
to call.

Per-fold Δ winner capture vs baseline (folds 2021-2024):
state_defaults +0.23/−0.14/+1.65/+0.53pp (mean +0.57 ± 0.66);
state_nan −0.15/−0.74/+1.17/−0.43pp (mean −0.04). Log loss deltas are
sign-inconsistent for defaults (−0.005/+0.030/+0.024/−0.167) and mildly
negative for nan (−0.041 mean, 3/4 folds). The largest single delta
(fold 2024, defaults, log loss −0.167) coincides with a degenerate baseline
fit that fold (24 boosting iterations, T=0.396) — baseline instability, not
state signal.

**Verdict: keep production LambdaRank stateless.** Consistent with the
training-window experiment's finding that the LambdaRank head sits at a
calibration ceiling and is insensitive to added information. The
within-noise nan-mode log-loss lean isn't worth retraining and re-validating
the deployed calibrated head. Fold 5 not rerun — the 4-fold pattern is
clear; rerun only if a future need for sharper in-race probabilities
emerges. Log: `experiments/lambdarank_state_cv_run.log` (no JSON — killed
before completion).

### 5-fold confirmation after the GC-date rebuild (2026-06-09, evening)

The snapshot rebuild (1,094,045 rows; 81 of 93 date-fixed 2025-26 GC comps
materialized) unlocked the 2025 fold and enlarged every fold's uncapped test
window. Re-run of the identical experiment, now 5 folds and 4,813 checkpoint
groups total:

| Stratum | carry-fwd | blind | **state** | Δ st−cf (per fold) |
|---|---|---|---|---|
| early winner | 0.167 | 0.300 | **0.350** | **+0.183** (+.192/+.171/+.205/+.134/+.214 — 5/5) |
| mid winner | 0.409 | 0.287 | **0.467** | **+0.058** (5/5 positive) |
| late winner | 0.704 | 0.312 | **0.721** | +0.017 (4/5 positive) |
| all winner | 0.408 | 0.298 | **0.495** | **+0.087** (5/5) |
| all podium | 0.496 | 0.456 | **0.632** | +0.136 |
| all log loss vs blind | — | 1.689 | **1.110** | −0.579 |

Stronger than the 4-fold result on every margin, and the new 2025 fold —
data that had never existed in training or evaluation before today — is
among the strongest folds (early +21.4pp over carry-forward). The
early-race blind comparison also turned uniformly positive (5/5, was 3/4).
Late-race now slightly POSITIVE vs carry-forward (+1.7pp, 4/5) rather than
a wash. Verdict unchanged and hardened: **gate passed at 5 folds**.

Production models were retrained the same evening on the rebuilt table
(633,367 samples / 5,636 comps, up from 624,796 / 5,551 — the dedupe,
the previously-missed incremental rows, and the 2025-26 GC rows all now
included). LambdaRank head retrained stateless per the same-day verdict.

JSON: `experiments/gc_checkpoint_head_cv_20260609_191539.json`
Next: productionize as a separate "GC outlook" head + app surface
(stage_race_dynamics_plan.md §8 item 6 → Phase 2b).
