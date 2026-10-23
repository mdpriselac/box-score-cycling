# TdF 2026 site toolchain

Source + build scripts for `netlify_site/index.html` (the five-view page:
tech architecture / plain-English / TdF 2026 boards / vs-the-books /
head-vs-head). Regeneration chain, from the repo root:

1. `PYTHONPATH=. SCRAPER_USE_BROWSER=1 uv run python netlify_site/build/run_tdf_predictions.py`
   — headless arm-C serving run over the cached startlist -> `tdf_2026_predictions.json`
2. `python3 netlify_site/build/capture_kambi_tdf.py`
   — Kambi (Unibet NL) odds snapshot (needs VPN) -> `tdf_book_comparison.json`
   + archive in `performance_eval/tour-de-france-2026/`
3. `python3 netlify_site/build/analyze_heads.py` -> `tdf_heads_analysis.json`
4. `python3 netlify_site/build/build_tdf_view.py && python3 netlify_site/build/build_books_view.py && python3 netlify_site/build/build_heads_view.py`
   — splice views into `predictor-architecture.html` between HTML markers
5. `python3 netlify_site/build/make_netlify.py` -> `../index.html`

Deploy: drag the `netlify_site/` folder onto app.netlify.com (or
`npx netlify-cli deploy --prod --dir netlify_site`). Prose in the builder
scripts contains hand-written numbers — re-check them after data changes.

## Daily stage pages (added 2026-07-04)

One page per Tour stage (`netlify_site/stageNN.html`), linked from the
race-diary block under the view toggle on index.html (`campaign_links.py`:
one card per hand-covered Grand Tour with review / GC / stage-grid links, and
one line sending every automated campaign to `/races`; it replaced the
per-campaign strips in 2026-10). Per stage:

1. Write `performance_eval/tour-de-france-2026/predictions/stage_NN/scenarios.json`
   — scenario definitions (real reference comps and/or synthetic terrain-score
   overrides), plus the odds capture to compare against (see stage_02 for the
   format).
2. `uv run python netlify_site/build/predict_stage_scenarios.py <scenarios.json> [--only k1,k2]`
   — runs each scenario through the arm-C serving path, writes `<key>.json`
   next to the config and logs the run to prediction_log. Logging is
   idempotent: an unchanged rerun updates the same opinion, while a changed
   release, scenario, active field, profile, day key, or race state creates a
   distinct opinion. Use `--no-log` for artifact-only dry reruns.
3. `python3 netlify_site/build/build_stage_page.py <scenarios.json>`
   — writes stageNN.html, re-renders the race-diary block (CAMPAIGN-LINKS
   markers in predictor-architecture.html), reruns make_netlify.py.
   `python3 netlify_site/build/campaign_links.py` refreshes just that block.
4. After the stage: run the results capture
   (`performance_eval/tour-de-france-2026/capture_results.py`), then rerun
   step 3 — the page picks up the archived results and appends the
   "After the stage" section with per-scenario scoring.

Within-race state: stage targets >= 2 automatically attach live race state
(completed stages, local-first). Seed the state cache from the daily archive
with `uv run python performance_eval/tour-de-france-2026/seed_state_cache.py`
after each results capture — no re-scrape, immune to flaky page loads. A
config with `"target": "gc"` (see `predictions/gc/scenarios.json`) keeps the
main heads pre-race and adds the state-aware GC outlook head
(gc_outlook_* in JSON + prediction_log); the hub then shows a "GC picture"
card from the latest GC run.

`build_gc_tracker.py <gc scenarios.json>` writes the full tracker page —
`netlify_site/[prefix]gc.html`, already linked from the race-diary card and the
hub's GC card. It takes the GC config path (no argument = the TdF config, so
the Tour's `gc.html` still builds from a bare call), resolves the results and
prediction archives against that config's own campaign directory, and reads
the scenario key + `tag` from it, so a second race publishes alongside the
first. Note that `state_through_stage` in prediction_log is a COUNT of the
stages that fed the state, not a stage number: with a cancelled stage in
`void_stages` the two diverge for the rest of the race, and the builder maps
the count back to the calendar stage before pulling that evening's `gc.csv`.

`build_stage_page.py` also regenerates `stages.html` — the Tour-diary hub
(one card per stage: scenario picks, book favourite, status chip, winner +
reflection once settled), linked from the race-diary card on index.html. To add a
post-stage reflection, put a `"reflection"` field (string or list of
paragraphs) in the stage's scenarios.json and rerun step 3 — it renders on
both the stage page and its hub card.

## One-day races (added 2026-09-08)

A one-day race is a single unit called `race`, so everything the stage path
spreads across `stage_NN` it keeps in one place:

```
performance_eval/<campaign>/predictions/race/scenarios.json    "target": "one_day"
performance_eval/<campaign>/predictions/race/<key>.json        one board per scenario
performance_eval/<campaign>/results/race/results.{csv,json}    the settled result
netlify_site/<slug>-<year>.html                                the page
```

1. Write the config, or let the driver write it. `cycling_project/nightly/oneday.py`
   builds it: the default `own_history` scenario's references are the race's own
   last five editions, looked up from the database by `fc_race_id`, and any
   alternate uses archetype references (`nightly refs --archetype …`). A one-day
   config carries no `stage`, no `void_stages` and no `day_key` — the day-menu
   channel prices stage-day shapes — and the loader refuses one that does.
2. `uv run python netlify_site/build/predict_stage_scenarios.py <scenarios.json> [--no-log]`
   — the same runner. It takes the field from a `startlist.json` beside the config
   (what the cloud acquisition thread hands over), else the `cached_start_lists`
   cache, else a rate-limited FirstCycling scrape; `--no-scrape` refuses the last.
3. `python3 netlify_site/build/build_oneday_page.py <scenarios.json>`
   — writes `netlify_site/<slug>-<year>.html`: the scenario fork, one board with
   blend / cascade / LambdaRank / market columns, and after settlement the
   "After the race" section scored against `results/race/results.csv`, joined on
   the FirstCycling rider id through the riders table.
4. `build_site_index.py` then `build_site_frame.py` — the race appears as a
   single row in the calendar and races views, and `/race/<slug>/<year>` gets a
   one-day hub whose board lives at `/race/<slug>/<year>/prediction`.

Settling a race the database already holds (an old campaign, or one migrated
before this path existed) needs no scrape:

```python
from cycling_project.nightly import oneday
oneday.export_results_from_db("performance_eval/strade-bianche-2026", "54", 2026)
```

A board built after the race is a reconstruction: mark the config `post_hoc`
and the page prints a banner saying so, naming the form leak (the serving path
re-ages form to the day the board is built, not to the config's race date).
