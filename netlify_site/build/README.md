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

One page per Tour stage (`netlify_site/stageNN.html`), linked from a strip
under the view toggle on index.html. Per stage:

1. Write `performance_eval/tour-de-france-2026/predictions/stage_NN/scenarios.json`
   — scenario definitions (real reference comps and/or synthetic terrain-score
   overrides), plus the odds capture to compare against (see stage_02 for the
   format).
2. `uv run python netlify_site/build/predict_stage_scenarios.py <scenarios.json> [--only k1,k2]`
   — runs each scenario through the arm-C serving path, writes `<key>.json`
   next to the config, logs every run to prediction_log (tagged
   model_version). Use `--only` / `--no-log` to avoid duplicate log opinions
   when re-running unchanged scenarios.
3. `python3 netlify_site/build/build_stage_page.py <scenarios.json>`
   — writes stageNN.html, refreshes the stage strip (STAGES markers in
   predictor-architecture.html), reruns make_netlify.py.
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

`build_stage_page.py` also regenerates `stages.html` — the Tour-diary hub
(one card per stage: scenario picks, book favourite, status chip, winner +
reflection once settled), linked from the strip on index.html. To add a
post-stage reflection, put a `"reflection"` field (string or list of
paragraphs) in the stage's scenarios.json and rerun step 3 — it renders on
both the stage page and its hub card.
