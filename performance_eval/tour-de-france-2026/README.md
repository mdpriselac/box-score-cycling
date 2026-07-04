# Tour de France 2026 — daily odds & results archive

Two scripts, run from the project root each day of the Tour:

```bash
# MORNING (before the stage starts — stage odds vanish from the feed once live):
uv run python performance_eval/tour-de-france-2026/capture_odds.py

# EVENING (after the stage finishes):
uv run python performance_eval/tour-de-france-2026/capture_results.py
```

## capture_odds.py — Kambi (Unibet NL) odds snapshots

Discovers every live TdF 2026 event (next stage, GC, jerseys, stage-win
specials) from the Kambi cycling listView and archives all betoffers.
No hard-coded event IDs — stage events appear in the feed a day or two ahead
and are picked up automatically.

- Output: `odds/YYYY-MM-DD/` — raw event JSONs under `raw/`, plus
  `markets_HHMM.json` (parsed), `provenance_HHMM.json` (URLs, timestamps,
  overrounds), `win_odds_HHMM.csv` (flat devigged full-field markets).
- Files are timestamped `HHMM`, so running twice a day (e.g. early morning +
  just before the start) gives you line movement for free.
- Stdlib-only; no VPN was needed on the home network as of 2026-07-04, but the
  feed can be geo-fenced — a 403 or an empty event list means switch on the
  NL VPN and rerun.
- Odds in raw JSONs are decimal × 1000; the parsed files already divide.
- Devig columns divide implied probability by the market's implied sum,
  scaled to the number of paid places (win = 1, podium = 3, top-10 = 10).
- `--match 'tour de france'` widens the filter to include TdF Femmes.

## capture_results.py — FirstCycling results snapshots

Archive-only (does NOT touch the pickle store or the SQLite DB — the weekly
`update_pipeline` remains the path into the training data). Each run:

1. Snapshots the race page (`results/race_page/race_page_DATE.html` +
   `standings_DATE.json/csv` once FirstCycling populates it — mid-race the
   main page shows "No data"; final GC appears after Paris).
2. Fetches any stage not yet archived with results and writes
   `results/stage_NN/`: raw HTML per fetch date, `results.json` /
   `results.csv` (stage result), `classifications.json` (every standings
   table on the page, keyed by FirstCycling's div ids: `sta` stage result,
   `gc` GC after the stage, `youth`, `teamcomp`, points/KOM when present)
   and `gc.csv` — **full-field individual GC gaps after each stage**,
   official times incl. bonus seconds. Stops at the first stage with no
   results, so a normal daily run is ~3 rate-limited requests.

The per-stage `gc.csv` is the running-GC record (individual, not team
gaps) — enough to run the in-race GC/stage-race-state features mid-Tour.
Note `stage_race_state.py` training features reconstruct GC as bonus-free
cumulative stage time; the archived `gc.csv` is the official (bonus-inclusive)
standing, so prefer the same reconstruction at inference for consistency.

Flags: `--force` (re-fetch archived stages), `--all` (scan every stage),
`--stage 05` (just one stage), `--race-id/--year` (reuse for another race).

Needs the usual scraper setup: `SCRAPER_USE_BROWSER=1` in `.env` means a
visible Chrome window opens for the Cloudflare challenge — don't close it.

## Pre-existing files (2026-07-03)

The `kambi_*_2026-07-03.json` / `unibet_gc_full_field_2026-07-03.csv` files in
this folder root are the pre-race capture made with the one-off
`netlify_site/build/capture_kambi_tdf.py` (hard-coded event IDs); everything
from 2026-07-04 onward lives in `odds/` via `capture_odds.py`.

## After Paris

Settle the archived odds against `prediction_log` in the market_avg_log_loss
frame (honest DNF-adjusted startlist). Overround on outright win markets runs
+40-50% — always use the devig columns when comparing to model probabilities.
