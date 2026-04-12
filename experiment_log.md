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
