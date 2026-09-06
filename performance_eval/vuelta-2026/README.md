# Vuelta a España 2026 — daily odds & results archive

Campaign twin of `tour-de-france-2026/`, with the **day-key retrieval channel**
added (Option A, decided 2026-08-09). Race facts: **fc_race_id 23**, year 2026,
stages 1–21, 2026-08-22 (Monaco ITT, 9.4 km) → 2026-09-13.

The capture scripts live in the TdF campaign directory and are pointed here by
flag — there is one copy of each, not two.

```bash
# MORNING (before the stage goes live — stage odds vanish from the feed once live):
uv run python performance_eval/tour-de-france-2026/capture_odds.py \
    --campaign performance_eval/vuelta-2026

# EVENING (after the stage finishes):
uv run python performance_eval/tour-de-france-2026/capture_results.py \
    --race-id 23 --year 2026 --out-root performance_eval/vuelta-2026/results --all
uv run python performance_eval/tour-de-france-2026/seed_state_cache.py \
    --race-id 23 --year 2026 --out-root performance_eval/vuelta-2026/results
uv run python performance_eval/vuelta-2026/score_day_keys.py
```

See `DAILY_RUNBOOK.md` for the full cycle including the day key.

## Layout

```
odds/YYYY-MM-DD/                     Kambi snapshots (raw/, markets_HHMM.json,
                                     provenance_HHMM.json, win_odds_HHMM.csv)
results/stage_NN/ + race_page/       FirstCycling archives (evening)
predictions/stage_NN/scenarios.json  stage config: scenarios + DAY KEY
predictions/gc/scenarios.json        GC config (target: gc)
review/key_scorecard.json            rolling tier-3 key accuracy
score_day_keys.py                    evening oracle labeling + key scoring
```

## campaign.json

`campaign.json` holds the race identity this campaign's tooling reads: the
FirstCycling race id, the dates, `void_stages`, the Kambi match strings and
`kambi_event_ids`. `capture_odds.py --campaign` reads it and writes newly
discovered event ids back into it. The Tour and the Vuelta have hand-written
files; `nightly registry sync` will generate the rest and fill in the fields
left empty here (`stages`, `pcs_slug`, `organiser_stage_urls`).

## Kambi brands

The brand chain is `ubnl,ubuk,ubse,rivers,rsiuspa`, tried in order until one
answers. Checked live on 2026-09-05 from a US residential connection with no
VPN: `ubnl`, `ubuk` and `ubse` all served the full Vuelta feed with identical
prices (only the market labels differ — `Winnaar` / `Winner` / `Etapp`).
`rivers` answered HTTP 429 "No access" for every lang/market tried and no
`na-*` Kambi host resolves, so BetRivers is reachable only through its
per-state codes; `rsiuspa` and `rsiusil` both served the same events from the
same EU host. The serving brand is recorded in every `provenance_*.json` and
in the CSV's `brand` column.

## Kambi event ids (opened 2026-08-21)

The NL brand localises the race name — the feed calls it **"Ronde van Spanje
2026"**, not "Vuelta a España". `capture_odds.py` matches the localised name
*and* `englishName`, so `--match "vuelta a espa"` works; a match on the Dutch
name works too.

| market | event id | outcomes at open |
|---|---|---|
| Stage 1 (Monaco ITT) | `1028797694` | 65 |
| Stage 2 (Monaco → Manosque) | `1028797695` | 103 |
| Stage 3 (Gruissan → Font-Romeu) | `1028797696` | 120 |
| Stage 4 (Andorra la Vella circuit) | `1028797697` | 115 |
| Stage 5 (Falset → Roquetes) | `1028797703` | 91 |
| Stage 6 (Alcossebre → Castellón) | `1028797700` | 114 |
| Stage 7 (Vall d'Alba → Valdelinares) | `1028797705` | 98 |
| Stage 8 (Puçol → Xeraco) | `1028797699` | 137 |
| Stage 11 (Cartagena → Lorca) | `1028797702` | 113 |
| Stage 12 (Vera → Calar Alto) | `1028797706` | 98 |
| Stage 14 (Jaén → Sierra de la Pandera) | `1028797734` | 83 |
| Stage 9 (La Vila Joiosa/Villajoyosa → Alto de Aitana) | `1028797704` | 117 |
| General Classification | `1028635359` | 59 win · 87 top-10 |
| Points | `1028797615` | 61 |
| Mountains | `1028797618` | 91 |
| Youth | `1028797617` | 43 |
| Teams | `1028797616` | 23 |
| Stage-win specials | `1028797625` | 127 betoffers (per-rider/team props) |

Per-stage events appear a day or two ahead and are discovered automatically —
put the new event id and the `odds_capture` filename into that day's
`scenarios.json`.

## Notes carried over from the Tour

- Odds in raw JSONs are decimal × 1000; parsed files already divide.
- Devig columns divide implied probability by the market's implied sum, scaled
  to paid places (win = 1, podium = 3, top-10 = 10). Outright overround runs
  +37–47% here — always compare model probabilities to the **devig** column.
- Head-to-head and yes/no specials are archived but not devigged into the CSV
  (no well-defined book sum), so the stage-win specials event contributes rows
  to `markets_*.json` only.
- `capture_results.py` is archive-only; the weekly `update_pipeline` remains
  the only path into the pickle store and the DB.
- The per-stage `gc.csv` is the official (bonus-inclusive) standing, while
  `stage_race_state.py` training features reconstruct GC as bonus-free
  cumulative stage time — prefer the same reconstruction at inference.
- Scrapes need `SCRAPER_USE_BROWSER=1` and a **visible** Chrome window.
