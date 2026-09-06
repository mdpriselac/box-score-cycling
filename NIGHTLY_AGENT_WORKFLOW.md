# Nightly managed-agent workflow — every WT / .Pro / .1 race

**Status:** decision record + build plan, 2026-09-05 (rev 3, evening).
Written after running the Vuelta daily runbook by hand for stage 14 → 15
with the explicit goal of automating it. Supersedes the harness section (§8)
of `AGENT_DESIGN.md`; the three agent contracts, the evidence bundle, gates K
and E and the failure table in that document stand and are referenced, not
repeated. Operational envelope: `CLOUDFLARE_DEPLOYMENT_PLAN.md`. The process
being automated: `performance_eval/vuelta-2026/DAILY_RUNBOOK.md`.

**Operating model (user decisions, 2026-09-05):**

1. **The nightly runs in Anthropic's cloud, not on the Mac.** The Mac cannot
   be relied on daily. Managed Agents *cloud* environment; one deployment
   per night; one session does today's results and tomorrow's previews.
2. **Nightly acquisition is ProCyclingStats through the platform's built-in
   web tool** (user-verified: a managed agent on the cloud platform reaches
   PCS with `web_fetch`; no container-side HTTP needed). FirstCycling is
   unreachable from the platform (Cloudflare JS challenge) and stays the
   **weekly** baseline, scraped by the supervised Mac run. PCS data is
   translated into FirstCycling ids by a crosswalk, never substituted.
3. **The weekly supervised Mac run is the release step**: it scrapes
   FirstCycling, migrates, rebuilds features, retrains, reconciles the
   week's PCS-derived archive against FirstCycling, merges the nightly
   branch, and publishes the data release the cloud session boots from.
4. Keys human until Gate K; publishing human-gated until Gate E; calendar
   from the pipeline's own race lists, refreshed weekly, never nightly.

---

## 0. What the manual run taught

Stage 14 → 15 took ~11 minutes and ~25 commands. Every deterministic step
already exists as a script; the glue is a human reading the runbook, and
every error-in-waiting was glue (edit the GC note *before* the run,
`state_through_stage` is a count, copy the event id, `--all` is mandatory,
`post_hoc: true` on late configs). Judgment sits in exactly four places: the
day key, the scenario reference sets, the prose (previews, reflections, GC
note), and the route facts when an organiser redraws a stage (stage 15 was
cut from 189.7 to 110.2 km mid-afternoon for heat). Everything else is a
driver.

| Step | Kind | Cloud-runnable? |
|---|---|---|
| Results / GC / startlist capture | acquisition | **PCS via web tool** (FirstCycling: Mac only) |
| Odds capture (Kambi JSON) | deterministic | container HTTP; brand fallback for non-NL egress (§2.8) |
| `seed_state_cache`, GC refresh, `score_day_keys`, page builds | deterministic | yes, given the data release |
| `predict_stage_scenarios.py` | deterministic | yes: LightGBM release (in git) + slim inference DB (release asset) |
| Day key, prose, hindsight refs | judgment | agents (§2.4–2.5) + `nightly refs` |
| Publish | deterministic, gated | git push to the site branch (§2.9) |

---

## 1. The shape

```
Anthropic cloud                                                  GitHub                      Mac (weekly, supervised)
───────────────────────────────────────────────────────          ──────────────              ─────────────────────────────
Scheduled deployment "nightly" 19:45 UTC ─► session ─► container  ◄─clone─  repo (code, models,   update_pipeline (FC scrape → migrate
   coordinator (multiagent):                   │ bash/read/write            campaign archives)      → features → retrain)
     ├─ self ×N        one thread per due race │ uv run -m cycling_project.nightly …               + reconcile PCS↔FC
     ├─ pcs-acquirer   web_fetch only          │ downloads data release  ◄─ release  ◄─────────── + export slim inference DB
     ├─ day-key-reader no tools                │ (slim DB + kernels)        assets                + kernels + manifest → release
     ├─ editorial      no tools                │                                                  + merge branch `nightly`
     └─ ops-triage     read-only               ▼                                                  + import prediction_log rows
                                    commits → branch `nightly` ─push─►  repo  ◄─merge──────────── + deploy site
                                                                    site branch → Cloudflare Workers Builds (gated)
```

**Why this split.** Judgment lives in agents with sharp contracts
(`AGENT_DESIGN.md` §3). The runbook's control flow lives in a deterministic,
idempotent driver the coordinator *calls*. Managed Agents supplies cron,
container, transcripts, budgets, versioned agent configs and a multiagent
roster that gives one isolated thread per race. GitHub is the state channel
in both directions (repo in, `nightly` branch out); a weekly data release is
the only artifact too large for git.

**Why one deployment, not one per race.** Races come and go weekly. One
nightly session runs `nightly plan`, then delegates one thread per due race;
threads share the container, and the driver's lock serialises SQLite writes.

### Decisions

| Question | Decision |
|---|---|
| Executor | Managed Agents **cloud** environment. Self-hosted worker on the Mac is *not* the nightly path (Mac availability); it remains an operator convenience for `--source fc`. |
| Schedule | One deployment, `45 19 * * *` UTC, budget $12/session. European finishes settled, Kambi's next-stage market already posted. North American finishes settle a night late (`settle_late`). Jitter ≤ 9 min. |
| Code + models into the container | `github_repository` resource on the deployment (branch `webscrape-refactor`, fine-grained PAT, contents read/write); every model file is < 100 MB and tracked. |
| Data into the container | **Weekly data release** (GitHub Release `data-YYYY-MM-DD`, assets: `inference_slice.db`, `day_menu_kernels.parquet`, `production_release_manifest.json`); `nightly bootstrap` downloads the newest release by sha at session start. Built by the Mac run (§2.10). |
| Results source | PCS via `web_fetch` by a dedicated acquisition thread that writes tables verbatim; deterministic `ingest` validates before anything downstream sees them (§2.8). FirstCycling only via `--source fc` on the Mac. |
| Odds source | Kambi JSON from the container (`allowed_hosts`), brand fallback for non-NL egress; degraded mode when blocked. |
| State out of the container | Session commits to branch `nightly` (campaign archives, ledger, built pages, exported `prediction_log` rows) and pushes through the git proxy. The Mac run merges weekly. |
| Publishing | The validated site bundle is pushed to branch `site`; Cloudflare Workers Builds deploys that branch. Human-gated: the push to `site` requires an `APPROVED` marker (committed by the operator or set on the run) until Gate E. No Cloudflare token in the agent. |
| Keys | Human keys via the inbox until Gate K; the agent key is recorded and scored beside it. |
| Prose-less publishing | Allowed for previews (numbers-only template), never for retros. |
| Route facts | PCS stage page (distance, vertical metres, profile) + organiser page when `campaign.json` lists one, via the acquisition thread; `route.override.json` on top; missing → recorded, never invented. |
| News | v1 news-less. |
| Calendar | Weekly race lists (`update_pipeline` step 2) with a dates sidecar, **committed to the repo** so the cloud can read them; registry derived once per race. |

---

## 2. Components to build

### 2.1 Campaign registry — from the weekly race lists, committed to the repo

`update_pipeline` step 2 (`find_races.create_race_year_db`) already scrapes
FirstCycling's per-level calendar pages into
`scraped_data/<year>/{wt,pro,d1}/<level>.txt`. Extend the weekly step to (a)
extract the calendar row dates into a sidecar and (b) cover the current and
next month; then **commit the sidecar into the repo** as
`performance_eval/calendar/<year>.json` so the cloud session can plan
without the Mac. `nightly registry sync --horizon 14` (read-only, runs in
the container) creates `performance_eval/<slug>-<year>/campaign.json` once
per race entering the horizon (fc_race_id, slug, category, is_stage_race,
dates, stages[], timezone, `kambi_match`, `pcs_slug`, `void_stages: []`,
`organiser_stage_urls: {}`), never overwriting. Stage rows come from the
PCS race page at registration. `CAMPAIGN_BRANDING` / `CAMPAIGNS` in the
builders read from campaign.json; Tour and Vuelta get hand-written files.

### 2.2 The driver — `cycling_project/nightly/driver.py`

`python -m cycling_project.nightly <command>`; JSON out; exit 0 done /
10 waiting_for_input (`operator_task`) / 20 failed (`error_class`, `step`,
`log_path`); idempotent on `(campaign, unit, phase)`; writes
`performance_eval/<campaign>/runs/<date>/<phase>.json` and appends to
`performance_eval/runs/ledger.jsonl`; global file lock around SQLite writes.

| Command | Runs |
|---|---|
| `bootstrap` | Verify the repo checkout, download the newest data release assets by sha (skip if present), `uv sync`, point `DB_PATH`/serving at `inference_slice.db`, print the release id. Fails closed (exit 20) if the release manifest's model contract hashes do not match `models/production/`. |
| `plan [--now]` | Due units from every `campaign.json` + the calendar: `settle` (date past, no `results/<unit>/results.csv`), `preview` (tomorrow race-local, no boards), flags `settle_late`, `blocked`. |
| `night --campaign <dir>` | Every due `settle`, then every due `preview`, in order. |
| `settle <campaign> <unit>` | `ingest` (validated PCS tables → FC-shaped `results/stage_NN/results.csv|json`, `gc.csv`, classifications) → `seed_state_cache.py` → GC config templated ("state through stage N") → GC predict → `build_gc_tracker.py` → `score_day_keys.py` (always) → `retro_facts.json` (winner group, top 15 vs each board by rider id, pool15 with/without key, oracle vs key, abandons, GC deltas, heads split) → `build_stage_page.py` → site index + frame → `export-log` (new `prediction_log` rows → `runs/<date>/prediction_log.jsonl`) → `commit`. |
| `preview <campaign> <unit>` | Kambi capture (event id written into the config) → route facts (from the acquisition thread's `route_raw.json`) → `bundle` → **exit 10 unless** the config has `day_key` or `--agent-key` → `predict_stage_scenarios.py` → `validate` → `build_stage_page.py` → site index + frame → `export-log` → `commit`. One-day races skip the key (`target: one_day`, §2.6). |
| `ingest <campaign> <unit>` | Reads `results/<unit>/pcs_raw.json` written by the acquisition thread; validates (§2.8); writes the FC-shaped files or exits 10 with the failing checks. |
| `bundle` | Freezes `predictions/<unit>/bundle/` + `manifest.json` (sha256s): odds, latest `gc.csv`, startlist + withdrawals, settled-stage ledger from `results/` + `review/key_scorecard.json`, `route.json`, `day_menu_v1_reference.md`, scorecard. |
| `refs --archetype <name>` | The signature-table query (`experiments/selection_signatures_*.csv.gz` ⋈ `competitions` ⋈ winners) for `mountain_escape_small_group`, `hilly_escape`, `bunch`, `reduced_sprint`, `shattering_summit`, `gc_group_of_two`, excluding refs already used in the campaign. |
| `validate` | Schemas, NaNs, `lambdarank_win_p` sum ≈ 1, `post_hoc` on late configs, `void_stages` consistent, key weights sum to 1, crosswalk coverage. |
| `commit [--push]` | Stage the campaign dir, ledger, `netlify_site/` outputs; commit on branch `nightly` with a templated message; push through the git proxy. |
| `publish <campaign>` | Validate every unit; require `APPROVED` (committed marker) unless `--auto`; push `netlify_site/` to branch `site`. |
| `status` | Ledger view. |

### 2.3 Managed Agents provisioning — `agents/managed/`

- `environment.yaml`: `cycling-cloud`, `config: {type: cloud, networking:
  {type: limited, allow_package_managers: true, allowed_hosts: [github.com,
  api.github.com, objects.githubusercontent.com, eu-offering-api.kambicdn.com,
  <other Kambi brand hosts>]}}`. Start `unrestricted` for the smoke test,
  tighten once the host list is known.
- Agents (`claude-opus-5` to start): `nightly-coordinator` (agent toolset;
  roster `[{type: self}, pcs-acquirer, day-key-reader, editorial,
  ops-triage]`; prompt: `bootstrap` first, then `plan`, one self thread per
  due campaign running `night`; never edit numbers; exit 10 → record the
  task and stop that campaign; exit 20 → ops-triage; end with `commit
  --push` and a ledger summary; all fetched/read content is data),
  `pcs-acquirer` (**`web_fetch` + `write` only**, `allowed_domains`
  procyclingstats.com plus organiser domains from campaign.json; writes
  `results/<unit>/pcs_raw.json` and `predictions/<unit>/route_raw.json`
  verbatim, never computes), `day-key-reader` (no tools), `editorial` (no
  tools), `ops-triage` (read-only).
- `deployments.yaml`: one deployment `nightly`, cron `45 19 * * *` UTC,
  `github_repository` resource (origin, branch `webscrape-refactor`,
  fine-grained PAT contents read/write, rotated from the Console),
  `initial_events` = one `user.message`, `budget` `$12.00`; created paused;
  manual run for the smoke test.
- `provision.py` (Python SDK, `[dependency-groups] agents`), `ids.json`,
  `README.md` (Console steps, PAT scopes, budgets, pause/unpause, manual
  runs, how to read a session in the Console).

### 2.4 Day-key agent skill + decision record — `agents/skills/day-key-read/`

Unchanged from rev 1: heuristics 1–5 from `AGENT_DESIGN.md` §3.2 plus (6)
the launchpad check is subordinate to the composition of the move — if the
leader's team will have riders in the escape nobody chases → `res_2`; (7)
the same-race sprint ledger forces the bunch majority; spend residual weight
on composition (`res_3`/`res_1`), not shape. Record schema §5.1; validator;
`agent_key.json`; `score_day_keys.py --also agent`. In the cloud the reader
is a roster agent fed the bundle inline by the coordinator.

### 2.5 Editorial agent skill + lexicon linter — `agents/skills/editorial/`

Unchanged from rev 1: preview / retro / monthly artifacts, prose-only JSON,
lexicon lint (no stake/ROI/value/play/punt/units), numeral check against the
facts bundle, key never restated with different weights, one retry then
hold; Gate E per artifact type.

### 2.6 One-day race path

`target: one_day` config (refs = the race's own last five editions),
`build_oneday_page.py`, `type: one_day` hub variant, startlist from PCS via
the acquisition thread (`cached_start_lists` is the Mac-side fallback).

### 2.7 Operator inbox

`_frame/ops.html` rendered from the ledger + `operator_tasks.jsonl` in the
repo. Approval = committing `performance_eval/<campaign>/runs/<date>/APPROVED`
(the page shows the exact command; a local approve endpoint is a convenience
when the Mac is open). Notifications: the deployment-run and session
webhooks are Console-registered; a tiny Cloudflare Worker (or the Mac when
awake) turns `session.status_idled` with `requires_action` into a push.
Private until Cloudflare Access exists (`.assetsignore` + Worker guard).

### 2.8 Acquisition: PCS through the web tool, validated deterministically

**The rule:** an LLM may *transcribe* a table it fetched, but nothing
downstream trusts the transcription until the driver has validated it, and
the weekly FirstCycling reconciliation is the backstop.

- **pcs-acquirer thread** (per due unit): `web_fetch` the PCS stage result,
  GC, secondary classifications and startlist pages (and the organiser stage
  page when listed) and write them *verbatim* to
  `results/<unit>/pcs_raw.json` — every row `{place|status, rider, team,
  time_or_gap, bib?, age?}` exactly as displayed, plus `source_url`,
  `fetched_at`, and the page's own totals — and `predictions/<unit>/route_raw.json`
  (distance, vertical metres, profile class, climbs if listed). It never
  computes gaps, never fills gaps in, never guesses a missing rider.
- **`nightly ingest`** validates before writing the FC-shaped archive: row
  count = classified finishers + DNF/DNS/OTL rows and matches the startlist
  minus prior abandons (tolerance 0); gaps parse and are monotone
  non-negative; winner time present; every top-15 and GC-top-20 rider
  crosswalks at ≥ 0.97; podium agrees with a second fetch (the GC page, or
  the race's result page on the organiser site) recorded in `pcs_raw.json`.
  Any failure → exit 10 with the failing checks; the acquisition thread may
  be asked once to re-fetch, then it is an operator task.
- **Crosswalk** (`rider_crosswalk` table, shipped inside the slim DB and
  mirrored to `performance_eval/crosswalk/rider_crosswalk.csv` in the repo
  so confirmations survive a release): `pcs_slug ↔ fc_rider_id ↔
  internal_rider_id`, seeded from `riders` by normalised name + team +
  birth year; auto-accept ≥ 0.97; proposals to the inbox; confirmations are
  human and committed. Wrong is worse than missing: an unmatched rider is
  written with an empty id, and the unit blocks if he is in the top 15 / GC
  top 20.
- **Kambi**: container HTTP against `eu-offering-api.kambicdn.com`;
  discovery by `campaign.json.kambi_match` (fuzzy proposals ≥ 0.95 auto);
  event ids written back; **brand fallback** `ubnl → ubuk → ubse → rivers`
  because the container's egress is not Dutch — record the brand used, keep
  devig per brand; `degraded.json` + exit 0 (degraded) when every brand
  blocks. `--wait-for-stage` polling for late markets.
- **Weekly reconciliation** on the Mac (`update_pipeline --reconcile`):
  diff each night's PCS-derived `results.csv`/`gc.csv` against the
  FirstCycling pickle for the same stage (place, gap, rider id); log to
  `performance_eval/runs/reconciliation.jsonl`; drift above threshold →
  operator task. This is what keeps PCS a sub and FirstCycling the baseline.

### 2.9 Publishing

`netlify_site/` is the build output. The nightly commits it to branch
`nightly`; `publish` fast-forwards branch `site` to the approved commit.
Cloudflare Workers Builds is connected to `site` (the `wrangler.jsonc` +
`.assetsignore` already exist), so a push is the deploy and a revert is a
rollback. Until Gate E the operator approves by committing the marker (or
merging a PR the coordinator opens through the GitHub MCP if we add the
vault credential later). Nothing partial is ever pushed to `site`.

### 2.10 Weekly release from the Mac — the critical path

The cloud session cannot open the 3.3 GB `cycling_races.db`. The serving
path reads only `rider_results`, `races`, `competitions`, `riders`,
`rider_race_state`, `cached_race_results` directly, plus whatever the
feature/live-form path reads (`rider_competition_snapshots` for the active
field, `race_features_*` and gradients for reference competitions,
`cached_start_lists`) — the exact set is measured, not assumed:

1. **Instrument**: run `predict_stage_scenarios.py` in `--no-log` for a
   stage config, the GC config and a one-day config with a
   `sqlite3` trace callback; record every statement and table.
2. **Export** `inference_slice.db`: `riders`, `races`, `competitions`,
   `teams`, `rider_team_history` in full (small); `rider_results` for every
   rider on a startlist in the next 14 days plus every reference competition
   in any scenario config; the latest `rider_competition_snapshots` rows per
   such rider; `rider_race_state` for in-progress races; `race_features_*`,
   `race_feature_gradients`, `race_history_thresholds` in full if under the
   budget, else for reference comps; `cached_start_lists`; empty
   `prediction_log` with the same schema; `rider_crosswalk`. Target
   **< 500 MB**; VACUUM.
3. **Parity**: re-run the three configs against the slice; outputs must be
   byte-identical (probabilities) to the full-DB run.
4. **Release**: `weekly_release.py` (new `update_pipeline` step after
   training) tags `data-YYYY-MM-DD`, uploads the slice, the kernels parquet
   and the release manifest as assets (`gh release create`), pushes
   `models/production/`, and writes `performance_eval/data_release.json`
   (id, shas) into the repo so `bootstrap` knows what to fetch.
5. **Merge back**: `git merge nightly`, import `runs/*/prediction_log.jsonl`
   into the real `prediction_log` (idempotent), run reconciliation, then
   the normal FirstCycling scrape → migrate → features → retrain.

### 2.11 Tests + replay

`tests/unit/test_nightly_driver.py` replays the committed Vuelta stage
14 → 15 archive through `night --dry-run` (no fetches, `--no-log`, archived
PCS raw fixtures) and asserts `retro_facts.json`, the ledger, and the built
pages. `test_nightly_ingest.py` covers every validator with fixtures
(missing rider, non-monotone gap, podium mismatch, sub-threshold crosswalk).

---

## 3. Rollout

| Phase | What runs | Human does | Exit gate |
|---|---|---|---|
| **0 — Vuelta shadow (now → Sep 13)** | Human runs the runbook on the Mac as tonight. Day-key agent shadow via `run_day_key.py` each morning; `pcs-acquirer` + `ingest` dry-run each evening against the FirstCycling archive to measure PCS transcription accuracy. | Everything, as today. | Ingest validators catch every seeded fault; crosswalk coverage on the Vuelta field ≥ 99 %. |
| **1 — Slice + driver on the Mac (Sep 14 →)** | Data release built weekly; driver runs `night` on the Mac against the slice (not the full DB) so the cloud path is exercised before the cloud exists. | Keys, approvals, crosswalk confirmations. | Parity on the slice; a race week with no manual commands except keys + approvals. |
| **2 — Cloud nightly (October: Québec/Montréal, Lombardia, Guangxi, .Pro/.1)** | Deployment live; coordinator + acquisition + ops-triage; day-key + editorial recorded. | Keys and approvals from the inbox; weekly Mac release. | ≥ 95 % sessions schema-valid, none over budget, failure table exercised, weekly reconciliation clean. |
| **3 — Promotion (2027)** | Gate E, then Gate K, per `AGENT_DESIGN.md` §6. | Vetoes. | Per gate. |
| **4 — Cloudflare envelope** | Ledger → D1, bundles → R2, Access-protected inbox, atomic publish pointer. | — | Plan phases 2–3. |

---

## 4. Prerequisites and risks

- **Repo**: origin is `github.com/mdpriselac/Cycling_Project`, branch
  `webscrape-refactor` (local is ahead of origin — push before provisioning).
  Fine-grained PAT (contents read/write) for the deployment resource; the
  token never enters the container (git proxy).
- **Data release size** is the unknown that decides feasibility; measure it
  first (chip 2.10). If the slice cannot get under ~500 MB, the fallback is
  a slimmer serving path (drop `race_features_*` in favour of precomputed
  reference profiles per config), not a bigger download.
- **PCS transcription risk** is bounded by `ingest` + weekly reconciliation,
  but a systematic PCS↔FC gap convention difference (bonus-inclusive GC vs
  cumulative stage time) must be handled explicitly: the archive's `gc.csv`
  is bonus-inclusive today (memory), so PCS's GC page is the right source.
- **Kambi geo**: the NL brand may 403/451 from the container's egress; the
  brand fallback is untested. If every brand blocks, previews run degraded
  (no book columns) — acceptable, but the day-key agent must be told.
- **Cost**: repo clone is cached; the release download is per session
  (~slice size); 2–8 Opus threads per night. Budget cap $12 is the guard.
- **Concurrency**: threads share one container; the driver lock serialises
  SQLite; no Chrome anywhere in the nightly.
- **Sensitive**: nothing secret in the repo, prompts, bundles or logs; the
  GitHub PAT is a deployment resource; Kambi needs no credential; Cloudflare
  deploys from the `site` branch without a token in the agent.
