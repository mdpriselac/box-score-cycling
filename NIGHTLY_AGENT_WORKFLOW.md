# Nightly managed-agent workflow — every WT / .Pro / .1 race

**Status:** decision record + build plan, 2026-09-05. Written after running the
Vuelta daily runbook by hand for stage 14 → 15 (evening + morning cycle) with
the explicit goal of automating it. Supersedes the harness section (§8) of
`AGENT_DESIGN.md` (which lives uncommitted in worktree `busy-darwin-2ac2fa`);
everything else in that document — the three agent contracts, the evidence
bundle, gates K and E, the failure table — stands and is referenced here, not
repeated. Operational envelope: `CLOUDFLARE_DEPLOYMENT_PLAN.md`. The process
being automated: `performance_eval/vuelta-2026/DAILY_RUNBOOK.md`.

---

## 0. What tonight's manual run taught about the automation

Running stage 14 → 15 end to end took ~11 minutes of wall-clock and ~25
commands. Where the minutes actually went, and what that implies:

| Step | Kind | Wall time | Judgment? | Automation note |
|---|---|---|---|---|
| `capture_results.py --all` | deterministic, headed Chrome | ~60 s | no | rate-limited; the only step that needs a GUI session |
| `capture_odds.py` | deterministic, Kambi API | ~10 s | no | event name localised ("Etappe 15"); event id must be copied into the next config |
| `seed_state_cache.py` | deterministic | ~5 s | no | must precede GC run |
| GC scenario label/note edit | **judgment (prose)** | 2 min | yes | today the note is hand-written; template + editorial |
| GC predict + `build_gc_tracker.py` | deterministic | ~30 s | no | logs to `prediction_log` |
| `score_day_keys.py` | deterministic | ~5 s | no | **always run** |
| Hindsight scenario refs | **judgment (retrieval)** | 3 min | yes | needed a signature-table query — no tool exists; becomes a driver command (`nightly refs`) |
| Reflection paragraphs | **judgment (prose)** | 4 min | yes | editorial agent, numbers from the settlement JSON |
| Settle stage page | deterministic | ~5 s | no | `build_stage_page.py` |
| Route facts for next stage | **acquisition** | 3 min | no | web search + fetch; today's route was REDRAWN mid-afternoon (heat protocol) — the bundle must be captured close to the deadline and re-captured if the organiser publishes a modification |
| Day key + scenario configs | **judgment (the core)** | 5 min | yes | day-key agent; scenario `refs` reuse the campaign's archetype sets |
| Predict next stage | deterministic | ~2 min | no | logs the official read |
| Build page, site index, frame | deterministic | ~10 s | no | three scripts; should be one |

Two facts that change the design relative to `AGENT_DESIGN.md`:

1. **Every deterministic step already exists as a script, but the glue is a
   human reading the runbook.** Tonight's errors-in-waiting were all glue:
   the GC note must be edited *before* the run, `state_through_stage` is a
   count not a stage number, the event id must be copied by hand, the
   `--all` flag is mandatory, `post_hoc: true` must be set on any config
   written after the stage. A driver removes that whole class.
2. **The Mac is not optional, and FirstCycling is not reachable from
   anywhere else.** FirstCycling sits behind a Cloudflare JS challenge that
   only a headed real-Chrome profile on this Mac clears; Anthropic's cloud
   containers and `web_fetch` cannot get it, and it 503s under Grand Tour
   load anyway. The SQLite DB (3.3 GB), the LightGBM release and the campaign
   archives also live here. So the nightly agent executes its tools on this
   machine — Managed Agents supports exactly that via a **self-hosted
   environment** — and, to stop the nightly depending on the challenge path,
   **nightly acquisition moves to ProCyclingStats (PCS), translated into the
   FirstCycling-id baseline by a crosswalk** (§2.8). FirstCycling remains the
   system of record, scraped by the weekly supervised run.

---

## 1. The shape: Managed Agents on top, deterministic driver underneath

```
Anthropic (control plane)                      This Mac (execution)
──────────────────────────                     ────────────────────────────────────
Scheduled deployment "nightly"  ──fires──►  session ──tool calls──►  EnvironmentWorker (launchd)
   (one tick: settle today, preview tomorrow)                          │ bash / read / write / edit
                                                                        ▼
Agent: nightly-coordinator  (multiagent roster below)          `uv run python -m cycling_project.nightly …`
  ├─ self            → one thread PER RACE (the "one agent run per race per day")
  ├─ day-key-reader  → no tools; frozen bundle passed inline; returns decision record
  ├─ editorial       → no tools; facts bundle inline; returns prose record
  └─ ops-triage      → read-only tools; diagnoses a failed deterministic step
                                                                        ▼
                                             run ledger, campaign dirs, netlify_site/, publish (gated)
```

**Why this split.** The judgment lives in agents with sharp contracts (as in
`AGENT_DESIGN.md` §3). The runbook's control flow lives in a deterministic,
idempotent driver the coordinator *calls* — it never re-derives the checklist
from prose. Managed Agents supplies what the launchd-only design lacked: cron
without a scheduler process, per-run session transcripts in the Console,
hard dollar budgets per session, versioned agent configs, webhooks, and a
multiagent roster that gives us one isolated thread per race with no
orchestration code.

**Why not one deployment per race.** Deployments are per agent + cron; races
come and go weekly. A single nightly deployment whose first action is
`nightly plan` (what is due tonight, race-local) and which then delegates one
thread per due race is the same "one run per race per day" with a stable
control plane. Threads run in parallel in the same workspace; the driver's
lock serialises the two things that must not overlap (SQLite writes, the
single Chrome profile).

### Decisions taken here

| Question (from `AGENT_DESIGN.md` §10 / plan) | Decision |
|---|---|
| Harness | Managed Agents (self-hosted environment on the Mac). `claude -p` / Agent SDK only as a manual fallback. |
| Model | `claude-opus-5` for coordinator, day-key, editorial; `claude-sonnet-5` for ops-triage and the per-race `self` threads is acceptable once the driver is stable — start everything on Opus. |
| Scheduling anchors | **One deployment**, `45 19 * * *` UTC (user decision 2026-09-05: a single night run does both the results and the next-day work). European finishes (~15:30 UTC) are settled and Kambi's next-stage market (posted late morning the day before) is already up; North American finishes (Québec/Montréal ~22:00 UTC) settle on the following night and `plan` marks them `settle_late`. Jitter ≤ 9 min; never schedule against a hard deadline. |
| Race scope | Every `wt`, `pro`, `d1` race in the weekly pipeline's race lists for the horizon (14 days), auto-registered as a campaign once. ~180 races/year, 2–6 active per day. No nightly calendar scrape. |
| Keys | Human keys; agent key recorded beside it and scored (Gate K population). Promotion per `AGENT_DESIGN.md` §6.2. |
| Publishing | **Gated.** The driver stages a validated bundle; `publish` requires an operator approval file until Gate E. No Cloudflare account/domain decision yet — deploy target is `wrangler deploy` of `netlify_site/` when it exists. |
| Prose-less publishing | Allowed for **previews** of races with no human-written scenario notes (numbers-only template); **never** for retros. |
| Nightly source | **PCS first** (results, GC, startlists, withdrawals, stage facts) through the crosswalk; FirstCycling only as an operator-present fallback (`--source fc`) and as the weekly baseline. |
| Roadbook evidence | Deterministic capture from the organiser page or the PCS stage page + operator override file `route.json`; when absent, the bundle records `route_facts: missing` and the day-key agent must weight the family conservatively and set `human_review_required`. |
| News | v1 news-less. |
| Veto window | Key locks at the morning tick; unvetoed agent keys stay *recorded*, human key stays *served*, until Gate K. |

---

## 2. Components to build

Each row is a chip (separate session). Order matters only where noted.

### 2.1 Campaign registry — derived from the weekly race lists, never rebuilt nightly

The pipeline already builds the calendar: `update_pipeline` step 2
(`find_races.create_race_year_db`) scrapes FirstCycling's per-level calendar
pages into `scraped_data/<year>/{wt,pro,d1}/<level>.txt`. That is the source
of truth and it is refreshed by the **weekly supervised run**, not by the
nightly agent. (The DB `races` table is not a forward calendar — it only
holds races already migrated from result pickles; as of 2026-09-05 nothing
after 2026-08-16.) Two gaps to close, both in the weekly step:

- the lists carry `name,url` only — add the calendar row's dates as a sidecar
  `<level>.calendar.json`;
- the weekly targets only cover months already scraped — include the current
  and next month so the horizon is always populated.

`nightly registry sync --horizon 14` is then read-only: for every wt/pro/d1
entry intersecting the horizon it creates
`performance_eval/<slug>-<year>/campaign.json` once (one race-page fetch at
registration for the stage list: number, date, towns, distance, kind;
timezone by finish country; `kambi_match`; `void_stages: []`) and never
overwrites it. `CAMPAIGN_BRANDING` (build_stage_page.py) and `CAMPAIGNS`
(build_site_index.py) read from campaign.json; the Tour and Vuelta dirs get
hand-written files so nothing regenerates. Stage dates on unraced FirstCycling
stage pages are missing by design — the calendar range is the fallback.

### 2.2 The driver — `cycling_project/nightly/driver.py`

Commands (all JSON-out, all idempotent on a `(campaign, unit, phase)` key,
all writing `performance_eval/<campaign>/runs/<date>/<phase>.json` + a line in
`performance_eval/runs/ledger.jsonl`):

| Command | What it runs (today's scripts, unchanged) |
|---|---|
| `plan --now <iso>` | Reads every `campaign.json`; emits due units: `{campaign, unit: stage_NN | race, phase: settle | preview | gc}` with race-local deadlines, plus stale/blocked flags (results missing past grace, startlist missing). |
| `night [--now <iso>]` | The one command the coordinator runs per due race: `settle` for every unit raced today, then `preview` for every unit due tomorrow, in that order (preview needs the seeded state). |
| `settle <campaign> <unit>` | `capture --source pcs` (PCS → FC-shaped `results/stage_NN/results.csv|json`, `gc.csv`, classifications, via the crosswalk; §2.8) → `seed_state_cache.py` → GC refresh (template label/note from state) → `build_gc_tracker.py` → `score_day_keys.py` → settlement facts JSON (`retro_facts.json`: winner group, front 15 vs each board, pool15 with/without key, oracle vs key, abandons, GC deltas, heads split) → `build_stage_page.py` → site index + frame. |
| `preview <campaign> <unit>` | `capture_odds.py` (+ localised-name discovery, event id written into the config) → route facts capture → `bundle` → **stops** unless a `day_key` is present in `scenarios.json` (human) or `--agent-key` is passed → `predict_stage_scenarios.py` → validators → `build_stage_page.py` → site index + frame. One-day races skip the key and use `target: one_day` scenarios generated from the campaign's archetype (**needs 2.6**). |
| `bundle <campaign> <unit>` | Freezes `predictions/<unit>/bundle/` (odds snapshot, route facts, GC csv, startlist + withdrawals, settled-stage ledger from `results/` + `review/key_scorecard.json`, `day_menu_v1_reference.md`, scorecard) and `manifest.json` with sha256s. |
| `refs --archetype <name> [--exclude-used]` | The signature-table query I did by hand tonight: returns candidate reference competitions for a scenario (mountain escape small-group, hilly escape, bunch, reduced sprint, shattering summit…), disjoint from every ref already used in the campaign. |
| `validate <campaign> <unit>` | Schema, NaNs, LambdaRank book sum ≈ 1, required scenarios present, `post_hoc` set on any config dated after its stage, `void_stages` consistent across configs, `state_through_stage` count↔stage mapping sane. |
| `publish <campaign>` | Assembles the bundle, runs `validate`, requires `runs/<date>/APPROVED` (human) unless `--auto` (post-Gate-E), then `wrangler deploy`. Never partial. |
| `status` | Ledger view for the operator inbox page. |

Rules baked in: a global file lock around any step that writes SQLite or
opens Chrome; `SCRAPER_USE_BROWSER` honoured; every step's stdout/stderr
captured to the run dir; exit code 0 = done, 10 = waiting_for_input (with
`operator_task` in the JSON), 20 = failed (with `error_class`).

### 2.3 Managed Agents provisioning — `agents/managed/`

- `environment.yaml` (`config: {type: self_hosted}`), five `*.agent.yaml`
  files, `deployments.yaml`, and `provision.py` (Python SDK; creates or
  updates by name, stores ids in `agents/managed/ids.json`, prints
  `upcoming_runs_at` for each deployment). Budgets: `$8` per evening
  session, `$6` per morning session to start; raise after a week of ledger
  data.
- `worker.py`: `EnvironmentWorker` with `workdir` = project root,
  `allowed_roots` = `[performance_eval, netlify_site, agents/skills]`,
  `read_only_roots` = `[models, cycling_project]`. Reads
  `ANTHROPIC_ENVIRONMENT_KEY` from the macOS Keychain at startup (never a
  global env var — the doc is explicit that an org API key must not be on
  the worker host). launchd plist `com.cyclingproject.managed-worker.plist`
  with `KeepAlive`, `RunAtLoad`, logs under `~/Library/Logs/cycling-worker/`.
- Coordinator system prompt: "you operate a deterministic CLI; never edit
  numbers; never run steps outside `python -m cycling_project.nightly`;
  delegate one thread per due unit; on exit 20 delegate to ops-triage; on
  exit 10 write the operator task and stop". Roster:
  `[{type: self}, {agent: day-key-reader}, {agent: editorial}, {agent: ops-triage}]`.
- Day-key and editorial agents: `tools: []`. The coordinator reads the
  frozen bundle and passes it inline in the delegation message; the record
  comes back as JSON in the thread's final message and the driver validates
  it (weights sum to 1, evidence refs resolve to manifest entries).

### 2.4 Day-key agent skill + decision record — `agents/skills/day-key-read/`

Skill file encodes the five heuristics in `AGENT_DESIGN.md` §3.2 plus two
from tonight:

6. **The launchpad check measures where a break can extend a lead; the
   composition of the move decides whether it gets one.** Stage 14: 44
   riders, every team represented, the *leader's own team* with two men in
   it → nobody chases, `res_2` by lunchtime. Before keying `gc_day` on a
   mountain day, ask: will the red jersey's team have riders in the move?
7. **Same-race sprint ledger forces the bunch majority** (five of five this
   Vuelta); spend the residual weight on *composition* (`res_3`/`res_1`),
   not on shape.

Record schema = `AGENT_DESIGN.md` §5.1. Written to
`predictions/<unit>/agent_key.json`; `score_day_keys.py --also agent` scores
both keys per stage and the scorecard row gains `agent_*` fields.

### 2.5 Editorial skill + lexicon linter — `agents/skills/editorial/`, `nightly/lint_prose.py`

Three artifacts: preview (`day_key_note`, per-scenario `note`, GC scenario
`note`), retro (`reflection[]`), monthly (later). Input = the facts JSON the
driver produces (`retro_facts.json` / `preview_facts.json`); output =
prose-only JSON. Validators: lexicon lint (no stake/ROI/value/play/punt/
units/"smart money"), every numeral in the prose must appear in the facts
bundle (allowlist: dates, stage numbers, climb stats), no key restated in a
different weight. On failure: one retry with the validator message, then hold
for the operator. Gate E per artifact type.

### 2.6 One-day race path

Missing today: a one-day scenario config shape (`target: one_day`, refs =
the race's own last five editions by default), a one-day page template
(`build_oneday_page.py`) and the `type: one_day` hub variant in
`build_site_frame.py` (deferred in `SITE_FRAME_NOTES.md`). Startlist comes
from `cached_start_lists`; withdrawals from the FirstCycling startlist page
the evening before.

### 2.7 Operator inbox — `netlify_site/_frame/ops.html` + macOS notifications

Rendered from `performance_eval/runs/ledger.jsonl` + `operator_tasks.jsonl`
by `build_site_frame.py` (private; served only locally until Cloudflare
Access exists). Each row: campaign, unit, phase, state, session id (Console
deep link), operator task, approve button that writes `APPROVED`. The driver
posts a macOS notification for `waiting_for_input` and `failed`.

### 2.8 Acquisition: PCS nightly, FirstCycling weekly, one crosswalk between them

**Why.** The nightly must not depend on the FirstCycling challenge path: it
needs a logged-in Mac with a visible Chrome window, it 503s under load, and it
is the only step that cannot run anywhere but here. ProCyclingStats publishes
the same facts (stage results with gaps, GC, startlists with withdrawals,
stage distance/profile) and is reachable with an ordinary polite HTTP client
(it 403s Anthropic's `web_fetch`, not a normal client with a UA — verify in
the chip). FirstCycling ids are the baseline of everything downstream, so PCS
data is **translated, never substituted**: the archive the nightly writes is
FC-shaped and carries FC rider ids.

- `cycling_project/nightly/pcs.py`: `capture --source pcs <campaign> <unit>`
  fetches the PCS stage/race result page (+ GC and secondary classifications)
  and startlist, rate-limited (≥ 3 s, jitter) through the project's client
  posture (no stealth libs), and writes the same files `capture_results.py`
  writes today so `seed_state_cache.py`, `score_day_keys.py`,
  `build_stage_page.py` and the state cache consume them unchanged. The PCS
  raw HTML is archived beside the FC archive (`results/stage_NN/pcs_*.html`).
- `cycling_project/nightly/crosswalk.py`: table `rider_crosswalk`
  (`pcs_slug, fc_rider_id, internal_rider_id, confidence, source, confirmed_by`)
  in the DB, seeded from the `riders` table (FC id, name, team history,
  birth year) by normalised-name + team + birth-year matching. Auto-accept
  only at confidence ≥ 0.97 (exact normalised name + birth year); everything
  else becomes an operator task with the candidates listed — **wrong is worse
  than missing**, so the driver never guesses. A PCS rider with no crosswalk
  row is written with `rider_id = null` and the unit is flagged
  `waiting_for_input` if any of the top 15 or any GC top 20 is unmatched.
- **Weekly reconciliation** (in the supervised Mac run, after the FC scrape
  + migrate): diff each night's PCS-derived `results.csv`/`gc.csv` against
  the FC pickle for the same stage (place, gap, rider id); log drift to
  `performance_eval/runs/reconciliation.jsonl`; a mismatch above a threshold
  opens an operator task. This is what keeps PCS a *sub* and FC the
  *baseline*.
- Kambi odds: as before — discovery by `campaign.json.kambi_match` with a
  fuzzy fallback that proposes (≥ 0.95 auto), localised name + event ids
  written back, retries, `degraded.json` on geo-block; `--wait-for-stage`
  polling for a late market.
- Route facts: `nightly route <campaign> <unit>` from the organiser stage
  page when `campaign.json.organiser_stage_urls` has one, else the PCS stage
  page (distance, vertical metres, profile class, finish altitude); FC stage
  page only in `--source fc` mode. `route.override.json` on top (the stage-15
  heat rewrite is the canonical case). Missing → `route_facts: missing`,
  never invented.
- FirstCycling in the nightly: `--source fc` exists and is what an operator
  runs when present (today's path); the coordinator never selects it.

### 2.8b Cloud-execution spike (later, low priority)

With PCS-first acquisition the only things pinning the nightly to the Mac
are the 3.3 GB SQLite DB and the model release. A bounded spike: instrument
the serving path to inventory every table/row it reads for one stage
(`rider_competition_snapshots` for the active field, `rider_race_state`,
`competitions`, kernels parquet), export that slice to a slim DB, and time a
`predict_stage_scenarios.py` run against it. If the slice is < 500 MB and
parity holds, Phase B (Anthropic cloud environment or a Cloudflare Container
per the plan) becomes a packaging job rather than a research one. Not before
Phase 2.

### 2.9 Tests + replay

`tests/unit/test_nightly_driver.py` replays the Vuelta 2026 stage 14 → 15
archive through `settle` and `preview` in `--dry-run` (no scrape, no log)
and asserts the ledger, the facts JSONs, and the built pages match the
committed ones.

---

## 3. Rollout

| Phase | What runs | Human does | Exit gate |
|---|---|---|---|
| **0 — Vuelta shadow (now → Sep 13)** | Nothing new in production. `nightly bundle` + day-key agent produce `agent_key.json` each morning from the same bundle the human reads. | Runs the runbook as tonight. | Bundle contents, schema, self-flagging debugged on ~7 stages. |
| **1 — Driver (Sep 14 → Il Lombardia)** | Driver replaces the runbook commands on the autumn calendar (Québec/Montréal, Lombardia, Guangxi, plus .Pro/.1), PCS-sourced with weekly FC reconciliation. | Keys stage races, approves every publish, confirms crosswalk proposals. | Several races with no manual commands except keys + approvals; ledger idempotent on rerun. |
| **2 — Managed Agents (October)** | Deployments live; coordinator runs the driver; day-key + editorial recorded, ops-triage on failures. | Approves keys and publishes from the inbox. | ≥ 95 % sessions schema-valid; no session exceeded budget; failure table exercised. |
| **3 — Promotion (2027 season)** | Gate E first (editorial), then Gate K (keys) per `AGENT_DESIGN.md` §6. | Vetoes. | Per gate. |
| **4 — Cloudflare envelope** | Ledger → D1, bundles → R2, atomic publish pointer, Access-protected inbox. | — | `CLOUDFLARE_DEPLOYMENT_PLAN.md` phases 2–3. |

---

## 4. Prerequisites and risks (read before starting any chip)

- The working tree was committed on `webscrape-refactor` on 2026-09-05
  (three commits: release/service/retrain, Vuelta campaign + site frame,
  design docs), so chip worktrees see everything referenced here.
- Worktrees need the DB symlink (memory: `reference_database_location`).
- `ant` CLI is not installed and `anthropic` is not a project dependency;
  chip 2.3 adds `anthropic>=1.0` under a `[dependency-groups] agents` group
  and installs `ant`.
- Self-hosted sandboxes do not support vault `environment_variable`
  credentials; all secrets (Kambi needs none; FirstCycling uses the Chrome
  profile) stay on the Mac. Nothing secret enters the agent context.
- Bash inside the worker is *not* confined by `allowed_roots`. Mitigations:
  the coordinator prompt forbids anything but the driver CLI, the driver
  validates every write, publish is human-gated, session budgets are hard
  caps, and every transcript is in the Console. Revisit (separate macOS
  user for the worker) before Gate E.
- Headed Chrome requires the Mac to be logged in with the display awake at
  the evening tick; `caffeinate` in the launchd plist, and the ops-triage
  taxonomy treats "no window" as a distinct class.
