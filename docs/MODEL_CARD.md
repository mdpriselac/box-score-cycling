# Model card

## What the models predict

For each rider on a start list, the finishing outcome of a men's WorldTour or ProSeries road race
or stage: the chance of winning, of a podium, a top 5, 10 or 15, and the expected time gap. Stage
races also get a GC outlook (the chance of winning or making the GC top 10 from the current
standings) and a did-not-finish head.

## Inputs

Only results data, as of the morning of the race. For each rider: age, bib numbers, career and
season race counts, average finishing bucket by race type (sprint, mountain, hilly, rolling,
breakaway, time trial) and by race class, recent form and its trajectory over several seasons,
days since the last race, and team quality. For the race: the composition of the field (how many
sprinters, climbers and so on, and how strong), a profile of the race built from the shape of its
past finishing times (how clumped, how selective), and within a stage race, the current GC
standings. A contested rating (an Elo over head-to-head finishes against riders who were actually
in contention) is added on top.

All features are computed point in time: a rider's form for a race uses only results dated before
it. Features that need history the rider doesn't have are left missing on purpose, and LightGBM
handles missing values natively.

Bookmaker odds are **not** a model input. They are captured only to score against.

## The heads

| Head | What it does |
|---|---|
| Bucket model | LightGBM over finishing buckets; the base ranker. |
| Time gap model | Expected gap to the winner. |
| Contender cascade | Multiclass win / podium / top-10 cascade, weighted and calibrated; used for ranking. |
| LambdaRank head | Full-field ranker turned into probabilities; used for the published prices and the book comparison. |
| Win calibration | A single logit shift fitted on held-out races (252 winners in 4,590 rows) so stated win probabilities sum to the realized rate. |
| GC outlook | Win and top-10 probabilities for the overall classification. |
| DNF head | Chance of abandoning. |
| Day-menu ranker | Re-picks the stage shortlist given the day key (see [EVALUATING_AGENTS.md](EVALUATING_AGENTS.md)). |

Production models train on races from 2016 onward. The trained files are not in this repository;
[`models/production/`](../models/production/) keeps only their metadata and feature lists.

## How a change ships

Every model change runs through rolling-season cross-validation (train on earlier seasons, test on
the next, three to five folds) in the experiment harness. It ships only if the winner lift clears
fold-to-fold noise, or if podium and log loss improve consistently without the winner getting
worse. [`experiment_log.md`](../experiment_log.md) records every experiment, including the ones that
failed the gate, and [`experiments/`](../experiments/) has the result files.

## How it did

Scored live on the 2026 Tour de France and Vuelta a España: see the results table in the
[README](../README.md#results) and the full reviews under
[`performance_eval/`](../performance_eval/). In short, the model trailed the market at the Tour and
was level with it on stage winners at the Vuelta.

## Known limits

- **Shy at the top.** The model finds the contenders about as well as the market, but puts too
  little probability on the eventual winner. At the Tour its top-5 bands stated 63.5% and realized
  82.1%.
- **GC moves too slowly.** It had the Tour winner on top of its GC board all 18 days, but its win
  probability only went from 0.36 to 0.47.
- **Breakaways.** Results alone say little about who will be in the move or whether it will stay
  away. In 12 of 13 hindsight runs the model could not find the breakaway winner.
- **Men's road racing only**, at WorldTour and ProSeries level, where the results history is deep.
  New riders with little history get wide, uncertain predictions.
- **Not betting advice.** The odds are the benchmark for how much signal results carry.
