# Vuelta 2026 — Day-Menu Retrieval Channel: Wiring Work Order

**Decided 2026-08-09 (user): Option A** — wire the kernod ranking channel into serving with judgment-priority keys, run the full TdF-style daily process at the Vuelta (start ≈ two weeks out), and treat the Vuelta as the prospective tier-3 evaluation of judgment key quality.

**Architecture (validated by gate 6, `experiments/day_menu_gate6_retrieval_cv_20260809_134250.json`):** the kernod-featured bucket model governs ONLY contender selection (pool membership + board order); the untouched production heads (contender cascade, LambdaRank, corrector, DNF) price the pool. Pricing neutrality +0.0005 honest market LL; judgment-tier retrieval ceiling +2.45pp pool15 / −1.84 winner rank on residual days (5/5 folds). Key priority at serve: **judgment read > one-day self-key (automatic) > selector-mixture fallback**. Vocabulary: `day_menu_v1_reference.md` + `models/production/day_menu_v1.json`.

## Critical path (sequenced)

### 1. Data refresh — DONE 2026-08-09 (with a fight; see [Scrape markup change] memory)
- [x] FirstCycling reachable; markup change (`div#race h2`→`div#raceSub`) broke date parsing mid-refresh + latent August ordinal bug found ("August"→"Augu", had NULL-dated the 2025 August corpus incl. Vuelta 2025 st1–9). Both fixed (`extract_race_date`, 10 regression tests); 35 races healed by delete+re-scrape; 26-race 2025 backfill pass.
- [x] TdF 2026 fully migrated: 22 comps (21 stages + GC), 0 NULL dates, 3,769 snapshot rows. Vuelta 2025: 22 comps, 3,475 snapshots. NOTE: three pipeline steps are year/watermark-scoped (migrate, percentiles, feature checkpoint) — back-dated heals need manual passes (done: 2025 migration, 2025 percentiles, watermark reset to 2025-07-31).
- [x] Kernels rebuilt DB-fresh at train: 642,461 rider-rides through 2026-08-09 (Tour + healed corpus in). Pipeline finished 9/9 steps, `bucket_daymenu` trained (best_iter 371, 195 feats = production 181 + 14 dtm), all four heads retrained. Fresh CSV signature artifact for the experiment record: optional, not load-bearing (DB-fresh build is canonical).

### 2. Menu v1.1 refit → drift check — RESOLVED 2026-08-09: **v1 STANDS**
- [x] Kernels + oracle keys rebuild DB-fresh at every train (`build_signature_table_from_db`) — Tour rides delivered by the train step itself (kernel history 642,461 rows through 2026-08-09).
- [x] Drift check run (fresh GMM k=8/seed 42 on 1,066 junk-filtered residual days vs v1's 951): family cores EXACT (res_4 0.9999/177-en-bloc, res_5 1.0000, res_6 0.9999), res_2 intact (0.993). Crosstab shows ZERO cross-family flow — the re-fit only re-partitions WITHIN families: it would split res_2's mass into two grades (199+188) and merge res_3 into res_7's cluster (coarsening the survivor-gallop distinction the TdF used for st5/st17). Verdict: partition non-uniqueness at +12% data, NOT item-meaning drift → **v1 remains the serving menu** (doc, ranker, kernels, serving all consistent). Post-Vuelta candidate v2: split res_2 into high-mountain vs punchy escape grades.
- [ ] Regenerate the reference doc's TdF table from actual migrated data (validates the labeler end-to-end on the freshest GT).

### 3. Production menu/kernel module (promote from experiments) — DONE 2026-08-09
- [x] `prediction_tools/day_menu.py` shipped: artifact load (stored-param GMM assign — never refits), labeler, kernel cumulants + parquet save/load, `attach_day_menu_features` (gate4 key_attach semantics), serve attach + weighted board scores, DB-fresh signature build. Port fidelity: 4033/4033 comps identical to the freeze run.
- [x] One-day self-key map builder (`self_key_oneday`, validated on production od-B4 output).
- [x] Unit tests `tests/unit/test_day_menu.py` (14): determinism, as-of-then leak, half-life decay, NaN on unkeyed, fills-vs-kernels split, train/serve skew guard, board-mix algebra.

### 4. Ranking-model training (pipeline step) — CODE DONE; model lands with the next train run
- [x] `train_production_model.main()` trains `bucket_daymenu` AFTER `registry.save()` (non-fatal; oracle keys; kernels rebuilt DB-fresh each train). Registry `add_bucket_variant`/`load_bucket_variant` (metadata flag + file both required — stale-file guard).
- [x] The pricing heads are NOT retrained with dtm features under any circumstances (gate 4/5 verdicts) — structurally enforced: only the variant sees the dtm frame.

### 5. Serving integration — DONE 2026-08-09 (Streamlit app deferred)
- [x] `predict_stage_scenarios.py`: `day_key` per scenario or config root; weighted sets mix at the RANKING-SCORE stage only; output JSON logs `day_key`/`board`/`daymenu_rank`.
- [x] Kernod board when keyed; production board when not (selector fallback not wired — default OFF stands). Promoted riders priced by the contender model via `predict_race(extra_contender_ids=...)` — pool membership routes pricing exactly as production top-N does.
- [x] Stage-page chip (`build_stage_page.py day_key_chip`): "keyed: mountain escape 0.6 / hard puncheur 0.4 (board order by rider-type retrieval; prices unchanged)". Streamlit-app key input DEFERRED post-Vuelta — the campaign serves through the runner + pages.
- [x] Prices remain the production heads' output in all cases.

### 6. Vuelta daily workflow (the TdF runbook + keys) — SCAFFOLDED 2026-08-09
- [x] Campaign dir `performance_eval/vuelta-2026/`: DAILY_RUNBOOK.md (morning key procedure + evening scoring), predictions/TEMPLATE_scenarios.json. TdF capture scripts gained `--out-root` (both) — one tool, per-campaign archives; Kambi match "vuelta a espa".
- [x] Evening scorer `score_day_keys.py`: oracle item from archives (labeler + frozen GMM; results.json + standings + as-of DB profiles, fc-id joins), scores exact/covered/weight-on-true, rolling table in review/key_scorecard.json. Validated on the TdF archive: 4/5 exact (st17 flips to the res_7 twin from snapshot recency — labels provisional until the post-race signature rebuild re-scores them).
- [ ] Retro page panels: "key vs oracle" and "pool with/without key" (build at race time on the settled-stage pages).

### 7. Pre-race verification
- [x] Smoke #1 (2026-08-09, TdF st4, key {res_2:0.6, res_4:0.4}): channel loads (menu v1 + 642K kernels + bucket_daymenu), kernod board promotes the break class (Schmid 19→6, Paret-Peintre 63→8, Storer 88→12) and demotes GC/sprint men (Pogačar 2→16 — keeps his 8.2% blend price and contender pricing); Pedersen #1 on the keyed board (won the stage). Promoted riders contender-priced via extra_contender_ids. Retrieval-only mechanics verified live.
- [ ] 2 more settled-race smokes at race week (a gc_day false-positive check + a bunch day).
- [ ] Dry-run stage-1 morning flow end to end two days before the Vuelta.
- [ ] KNOWN: archived TdF configs' `refs` point at pre-re-migration comp ids (ids changed 2026-08-09) — TdF reruns need ref re-resolution; Vuelta configs unaffected (fresh ids).

## Explicitly out of scope (decided)
- dtm/kernel features in any pricing head (dead — gates 4/5).
- Conditional boards as prices at any tier (dead — gate 5 HOME_TURF_HARM).
- Selector v2 strategic features (null probe); kernel hyperparameter sweep (deprioritized).
- Break-membership program, dedicated GC model — separate programs, untouched by this wiring.

## Open items to watch
- The weekly pipeline SKIPS the Vuelta until it has results ("no results found", 2026-08-09 scrape) — pre-race startlist/field features flow through the app's upcoming-race path instead; phase 7's dry run must confirm that path serves stage 1 with the current startlist.
- rorc is an oracle bound; the Vuelta IS the measurement of where judgment actually sits (tier-3). If Vuelta reads score near-oracle on residual days, the channel is validated at its ceiling; if near-mixture, revisit whether it stays default-on.
- res_5 never selectable (degenerate → res_7); res_0 discouraged (weight family candidates instead).
- gc_day boards: per the 2026-08-09 user directive, GC-slice performance is a soft consideration; the dedicated GC model is the eventual fix.
