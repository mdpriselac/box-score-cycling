# Box Score Cycling

[![tests](https://github.com/mdpriselac/box-score-cycling/actions/workflows/tests.yml/badge.svg)](https://github.com/mdpriselac/box-score-cycling/actions/workflows/tests.yml)

How much can you learn about a bike race from nothing but its results sheet? This project predicts
men's WorldTour and ProSeries road races before they happen, publishes the predictions, and settles
every one against the result afterwards, misses included. Every feature the models train on comes
from box scores: who started, where each rider finished, and how far behind. Bookmaker odds are
the benchmark for how much signal that carries, not betting guidance.

The project page, with the development diary, is
[outsidethevillage.com/cycling](https://outsidethevillage.com/cycling.html).

## Results

Scored on the 2026 grand tours, against the result and against the bookmaker's devigged prices.
Lower log loss is better.

| | Tour de France 2026 | Vuelta a España 2026 |
|---|---:|---:|
| Stages scored | 20 | 17 |
| Stage-winner log loss, model (published reads, equal weight) | 2.407 | **2.919** |
| Stage-winner log loss, book | **1.944** | 2.942 |
| Gap, model minus book (nats per stage) | +0.46 | **−0.02** |
| Top pick won, model vs book (reads) | 22 vs 34 of 57 | 22 vs 19 of 50 |
| Actual top 15 inside the board's top 15, model vs book | 53.6% vs 53.3% | 40.4% vs 46.7% |

What the numbers say:

- **At the Tour the market won, clearly.** But the model found the right contenders as well as the
  book did (level at ten and fifteen deep). The whole deficit was in concentrating probability on
  the winner and podium: the model was shy at the top.
- **Most of the Tour's gap came from a few hard-man and breakaway days.** That finding became the
  day-type channel: before each stage, a key says what kind of day it will be, and a ranker uses it
  to re-pick the shortlist. Every version that let the key move prices made the predictions worse,
  so it is only allowed to change who makes the shortlist.
- **By the Vuelta the model was level with the market on stage winners**, and ahead on days the
  bunch or the GC group settled (2.62 against 2.73 with the three hard-man days removed). It was
  behind at depth, and breakaways are still the hard problem: in 12 of 13 hindsight runs it couldn't
  find the breakaway winner, and mostly neither could the market.
- **GC is the weak spot.** At the Tour the model had the winner on top of its GC board all 18 days,
  but its win probability barely moved (0.36 to 0.47) while the book's went from 0.65 to 0.93.

The full reviews, with every table and the definitions, are in
[`performance_eval/tour-de-france-2026/review/`](performance_eval/tour-de-france-2026/review/README.md)
and [`performance_eval/vuelta-2026/review/`](performance_eval/vuelta-2026/review/). The models are
described in [`docs/MODEL_CARD.md`](docs/MODEL_CARD.md), and the agents that run the nightly
cycle, and how they are evaluated, in [`docs/EVALUATING_AGENTS.md`](docs/EVALUATING_AGENTS.md).

## What's here

| Path | What it is |
|---|---|
| `cycling_project/prediction_tools/` | The LightGBM heads, training, inference, the pricing layer and the experiment harness. |
| `cycling_project/engineering_tools/` | Point-in-time feature precomputation, race-shape and form features, within-race state. |
| `cycling_project/webscrape_tools/` | Results parsing and the SQLite database tools. |
| `cycling_project/nightly/` | The nightly driver: acquire results, key the day, price the board, settle, publish. |
| `agents/` | The Claude Managed Agents crew: YAML definitions, prompts and skills, and the provisioning script. |
| `netlify_site/build/`, `netlify_site/_frame/` | The static site builders and templates. |
| `performance_eval/` | Campaign configs, the race reviews, and the lessons ledger (`LESSONS.md`). |
| `experiments/`, `experiment_log.md` | Cross-validation results for every model change, and the log of what was tried. |
| `supabase/` | The control-plane schema (runs, steps, keys, the operator inbox). |
| `docs/` | The pipeline guide, model card, agent evaluation, and HTML references. |

## Running it

Bring your own data. This copy has the code, not the data: the scraped results database, the
trained models, raw odds captures and published pages stay private. The parsers expect
FirstCycling-style results pages, and [`docs/PIPELINE.md`](docs/PIPELINE.md) describes the weekly
pipeline that builds the database and trains the heads.

```bash
uv sync --all-groups
cp .env.example .env    # then fill in your own values
uv run pytest           # 969 tests, no network or keys needed
```

A few driver tests replay a real night against uci.org and are skipped unless
`RUN_NETWORK_TESTS=1` is set; one needs the published site pages and is always skipped.
[`cycling_project/tests/conftest.py`](cycling_project/tests/conftest.py) lists them.

## About this copy

This is a filtered copy of my private working repository, with its history kept (345 of 414
commits; commits that only touched removed files dropped out). The filter removed the trained model
files (re-committed many times, about 1.5 GB), committed `node_modules`, scraped result pages and
per-race outputs, raw bookmaker odds captures and PDFs, run transcripts, old analysis plots, and a
betting-report generator. The Supabase project ref and Managed Agents IDs are replaced with
placeholders and read from configuration, absolute paths on my machine are shortened, and my email
is replaced. The browser-based fetcher I use for FirstCycling stays private.

## How this was built

I started this in January 2025 and wrote the first season myself: the scraper, the first
predictors (average finishing place, bib numbers, regressions), and a long attempt to describe what
kind of race a race was from its results alone. None of those 70 commits has a Claude co-author.

From February 2026 most commits were written by Claude agents in Claude Code, from briefs I set and
reviewed; 227 of the 275 commits since then carry a `Co-Authored-By: Claude` trailer. That covers
the LightGBM stack, the experiment harness, the nightly driver and the managed-agent crew. The
questions, the gating rules every model change has to pass, which experiments shipped and which
were shelved, the rider identity calls in the crosswalk, and every published draft were mine:
nothing the agents write goes out until I approve it. [`CLAUDE.md`](CLAUDE.md) is the standing
brief the coding agents worked from, and
[`performance_eval/LESSONS.md`](performance_eval/LESSONS.md) is the dated record of what each
campaign taught.
