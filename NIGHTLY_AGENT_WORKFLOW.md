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
2. **The Mac is not optional.** SQLite DB, the LightGBM release, the Kambi
   and FirstCycling captures (headed Chrome), and the campaign archives all
   live here. Any "managed" agent must execute its tools on this machine.
   Managed Agents supports exactly that: a **self-hosted environment** whose
   worker runs on the Mac, with the agent loop, scheduling, transcripts,
   budgets, and versioned agent configs hosted by Anthropic.

---

## 1. The shape: Managed Agents on top, deterministic driver underneath

```
Anthropic (control plane)                      This Mac (execution)
──────────────────────────                     ────────────────────────────────────
Scheduled deployment "evening"  ──fires──►  session ──tool calls──►  EnvironmentWorker (launchd)
Scheduled deployment "morning"  ──fires──►  session                    │ bash / read / write / edit
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
| Scheduling anchors | Two deployments in UTC: **evening** `30 19 * * *` and **morning** `30 5 * * *`; the driver's `plan` converts race-local deadlines. European evening finishes settle at 19:30 UTC; Americas/Asia races settle on the next morning tick. Jitter is ≤ 9 min, so never schedule against a hard deadline. |
| Race scope | Every `wt`, `pro`, `d1` race in the weekly pipeline's race lists for the horizon (14 days), auto-registered as a campaign once. ~180 races/year, 2–6 active per day. No nightly calendar scrape. |
| Keys | Human keys; agent key recorded beside it and scored (Gate K population). Promotion per `AGENT_DESIGN.md` §6.2. |
| Publishing | **Gated.** The driver stages a validated bundle; `publish` requires an operator approval file until Gate E. No Cloudflare account/domain decision yet — deploy target is `wrangler deploy` of `netlify_site/` when it exists. |
| Prose-less publishing | Allowed for **previews** of races with no human-written scenario notes (numbers-only template); **never** for retros. |
| Roadbook evidence | Deterministic capture from the organiser page or FirstCycling stage page + operator override file `route.json`; when absent, the bundle records `route_facts: missing` and the day-key agent must weight the family conservatively and set `human_review_required`. |
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
| `settle <campaign> <unit>` | `capture_results.py --all` → `seed_state_cache.py` → GC refresh (template label/note from state) → `build_gc_tracker.py` → `score_day_keys.py` → settlement facts JSON (`retro_facts.json`: winner group, front 15 vs each board, pool15 with/without key, oracle vs key, abandons, GC deltas, heads split) → `build_stage_page.py` → site index + frame. |
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

### 2.8 Acquisition hardening

- `capture_odds.py`: discovery by `campaign.json.kambi_match` with fallback
  to fuzzy match on `englishName`; writes the discovered localised name and
  per-stage event ids back into `campaign.json`; retries; degraded mode
  when no market (the bundle says so).
- `capture_results.py`: generic race page → one-day result; stage races
  unchanged; classifies failures (`empty_parse` markup drift, `403`
  challenge, `503` origin) into the ops-triage taxonomy.
- Route facts: `nightly route <campaign> <unit>` fetches the organiser stage
  page listed in `campaign.json` (lavuelta.es-style structured climbs) and
  the FirstCycling stage page; writes `route.json`; an operator can drop a
  hand-written `route.override.json` (tonight's heat-protocol rewrite is the
  canonical case).

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
| **1 — Driver (Sep 14 → Il Lombardia)** | Driver replaces the runbook commands on the autumn calendar (Québec/Montréal, Lombardia, Guangxi, plus .Pro/.1). | Keys stage races, approves every publish. | Several races with no manual commands except keys + approvals; ledger idempotent on rerun. |
| **2 — Managed Agents (October)** | Deployments live; coordinator runs the driver; day-key + editorial recorded, ops-triage on failures. | Approves keys and publishes from the inbox. | ≥ 95 % sessions schema-valid; no session exceeded budget; failure table exercised. |
| **3 — Promotion (2027 season)** | Gate E first (editorial), then Gate K (keys) per `AGENT_DESIGN.md` §6. | Vetoes. | Per gate. |
| **4 — Cloudflare envelope** | Ledger → D1, bundles → R2, atomic publish pointer, Access-protected inbox. | — | `CLOUDFLARE_DEPLOYMENT_PLAN.md` phases 2–3. |

---

## 4. Prerequisites and risks (read before starting any chip)

- **The working tree is 119 files ahead of `webscrape-refactor` HEAD and the
  key inputs to this plan are UNTRACKED**: `CLOUDFLARE_DEPLOYMENT_PLAN.md`,
  `netlify_site/build/build_site_index.py`, `build_site_frame.py`,
  `site-index.json`, `_frame/`, `prediction_service.py`,
  `production_release.py`, the Vuelta pages, and `AGENT_DESIGN.md` (in a
  worktree). Chips run in fresh worktrees from HEAD and will not see any of
  it. **Commit (or at least stage a WIP commit of) the current state before
  starting chips 2.1–2.9.**
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
