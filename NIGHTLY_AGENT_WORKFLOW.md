# Nightly managed-agent workflow — every WT / .Pro race (.1 by opt-in)

**Status:** decision record + build plan, 2026-09-05 (rev 4, night).
Written after running the Vuelta daily runbook by hand for stage 14 → 15
with the explicit goal of automating it. Supersedes the harness section (§8)
of `AGENT_DESIGN.md`; the three agent contracts, the evidence bundle, gates K
and E and the failure table in that document stand and are referenced, not
repeated. `CLOUDFLARE_DEPLOYMENT_PLAN.md` remains the envelope for the
*public site*; the control plane it assigned to D1/R2 lives in **Supabase**
from rev 4 (dashboard, REST and row-level security exist today). The process
being automated: `performance_eval/DAILY_RUNBOOK.md` (campaign-agnostic since
2026-09-08; the two campaign runbooks now hold only their own race facts, and
`performance_eval/LESSONS.md` holds their dated lessons).

**Operating model (user decisions, 2026-09-05):**

1. **The nightly runs in Anthropic's cloud, not on the Mac.** Managed Agents
   cloud environment; one deployment per night; one session does today's
   results and tomorrow's previews.
2. **Nightly acquisition is ProCyclingStats through the platform's built-in
   web tool** (user-verified). FirstCycling is unreachable from the platform
   and stays the **weekly** baseline scraped by the supervised Mac run; PCS
   data is translated into FirstCycling ids by a crosswalk, never substituted.
3. **The agent has no credential that can change the codebase.** No GitHub
   resource, no repo token, no push. It runs a *release bundle* (code +
   models + data) that the weekly Mac run built, downloads it read-only,
   and writes only to append-only Supabase tables and insert-only storage
   through a vaulted key it never sees (§1a).
4. **The weekly supervised Mac run is the release step**: FirstCycling
   scrape → migrate → features → retrain; pull the week's rows and
   artifacts from Supabase into the repo (git stays the canonical archive,
   committed by a human-present run); reconcile PCS↔FC; export the slim
   inference DB; upload the next release bundle; promote approved pages.
5. Keys human until Gate K; publishing human until Gate E (and even then
   by a promotion step the agent does not hold a credential for); calendar
   from the pipeline's race lists, refreshed weekly, never nightly.

---

## 0. What the manual run taught

Stage 14 → 15 took ~11 minutes and ~25 commands. Every deterministic step
already exists as a script; the glue is a human reading the runbook, and
every error-in-waiting was glue (edit the GC note *before* the run,
`state_through_stage` is a count, copy the event id, `--all` is mandatory,
`post_hoc: true` on late configs). Judgment sits in exactly four places: the
day key, the scenario reference sets, the prose, and the route facts when an
organiser redraws a stage (stage 15 was cut from 189.7 to 110.2 km
mid-afternoon for heat). Everything else is a driver.

| Step | Kind | Cloud-runnable? |
|---|---|---|
| Results / GC / startlist capture | acquisition | **UCI results API via the deterministic command** (FirstCycling: Mac only; PCS retired 2026-09-22) |
| Odds capture (Kambi JSON) | deterministic | container HTTP; brand fallback for non-NL egress (§2.8) |
| `seed_state_cache`, GC refresh, `score_day_keys`, page builds | deterministic | yes, given the release bundle |
| `predict_stage_scenarios.py` | deterministic | yes: LightGBM release + slim inference DB (both in the bundle) |
| Day key, prose, hindsight refs | judgment | agents (§2.4–2.5) + `nightly refs` |
| Publish | deterministic, gated | promotion step outside the agent (§2.9) |

---

## 1. The shape

```
Anthropic cloud                                          Supabase (control plane + artifacts)        Mac (weekly, supervised)
──────────────────────────────────────────────────       ─────────────────────────────────────       ────────────────────────────────
Scheduled deployment "nightly" 19:45 UTC ─► session      bucket  releases/        (read-only)  ◄──── update_pipeline (FC scrape → migrate
   container: bash/read/write, no git, no repo             ├─ code-<sha>.zip, models/, slice.db,         → features → retrain)
   coordinator (multiagent):                               │  kernels.parquet, calendar, crosswalk       + pull week from Supabase → repo commit
     ├─ self ×N        one thread per due race  ──read──►  │                                             + reconcile PCS↔FC
     ├─ pcs-acquirer   web_fetch + write only              bucket  nightly-artifacts/ (insert-only) ◄─── + export slice, build + upload release
     ├─ day-key-reader no tools                 ──write─►  tables  runs, run_steps, pcs_raw,             + promote approved pages → site
     ├─ editorial      no tools                            │       predictions, prediction_log,
     └─ ops-triage     read-only                           │       operator_tasks, day_key_decisions
                                                           │       (INSERT only for the agent role)
   vault: SUPABASE_NIGHTLY_KEY (placeholder in sandbox;    tables  campaigns, stages, calendar,
          real key substituted at egress, header-only,     │       crosswalk, approvals  (SELECT only)
          host = <project>.supabase.co only)               ▼
                                                    human: dashboard / inbox page — approve keys, publications, crosswalk
                                                                    │
                                                    site-staging/ ──promote (Mac or Edge Function, own key)──► Cloudflare
```

**Why this split.** Judgment lives in agents with sharp contracts
(`AGENT_DESIGN.md` §3). The runbook's control flow lives in a deterministic,
idempotent driver the coordinator *calls*. Managed Agents supplies cron,
container, transcripts, budgets and a multiagent roster; Supabase supplies a
ledger with real access control, a dashboard, storage and a REST API;
the weekly Mac run is the only writer to git and the only builder of what
the nightly runs.

**Why one deployment, not one per race.** Races come and go weekly. One
nightly session runs `nightly plan`, then delegates one thread per due race;
threads share the container; the driver's lock serialises SQLite writes.

### 1b. Scope — WorldTour and .Pro (owner decision, 2026-09-22)

The unattended nightly covers **`wt` and `pro`**. A `.1` race (`category:
d1`) is still registered, still bundled into the release and still runnable
by hand on the Mac — it is simply never *due* for the tick.

The evidence is the first week of unattended running: of the eleven races
that caused trouble, eight were `.1`, and every `.1` failure was about the
outside world, not the code — FirstCycling never published a start list (Giro
della Romagna, Kampioenschap van Vlaanderen), no earlier edition existed in
the database (Giro di Campania), no UCI calendar listing (Romagna), riders
nobody could identify (Matteotti, Okolo Slovenska, Huangshan). `.1` races are
18 of the 31 campaigns on disk and 9 of October's 20 calendar rows, so the
rule roughly halves the nightly workload and the cloud spend.

One rule, one place: `cycling_project/nightly/tiers.py`
(`AUTOMATION_TIERS = ("wt", "pro")`, `is_automated(campaign_cfg)`).

| Surface | Behaviour |
|---|---|
| `nightly plan` / `night` | nothing due; the payload carries `"automated": false` and `"skipped": "not_automated: category d1"`, so the coordinator's per-campaign `plan` call says why (**no coordinator prompt change**) |
| `nightly settle --unit` / `preview --unit` | runs as before — attended use is the point |
| `nightly.horizon` | captures only covered campaigns; `--campaign` narrows, it does not widen |
| `registry sync`, `weekly_release` | unchanged: every campaign is registered and bundled |
| `campaigns.automated` (hosted) | mirrored by `registry sync` when migration `0008_campaign_automation.sql` is pushed; the write is dropped and retried without it when it is not |
| operator inbox | open tasks for uncovered campaigns sit under a collapsed "Attended (.1) campaigns" section |
| public hub | an uncovered campaign with no page reads `not_covered`, never "in progress" |

**Opting one race in or out** — in its `campaign.json`:

```json
"automation": "on"     // cover this .1 race
"automation": "off"    // leave this WT/.Pro race to a human
```

An unreadable value is ignored (the category decides) and reported as
`automation_note` in the plan. A campaign with **no** `category` is not
automated: the registry always writes one, so its absence means a human
should look. The Mac can widen a single invocation with `--all-tiers` or
`--include-tier d1` on `plan`, `night` and `horizon`.

### 1a. Trust boundary — what the agent can and cannot do

| Surface | Agent capability | Enforced by |
|---|---|---|
| Codebase | **Read a copy** (the release zip in its container). Cannot push, cannot alter what runs tomorrow. | No git remote, no repo credential in the deployment. Local edits die with the container. |
| Models / data | Read the bundle. | Storage policy: `release_reader` may only `SELECT` objects in `releases/`. |
| Supabase tables | `INSERT` into append-only ledger/artefact tables; `SELECT` on config tables. **No `UPDATE`/`DELETE` anywhere; no DDL.** | Postgres role `nightly_agent` + grants + RLS. The agent's key maps to that role. |
| Storage writes | `INSERT` new objects under `nightly-artifacts/<run_id>/…` and `site-staging/<run_id>/…`. No overwrite, no delete. | Bucket policies keyed on the role; object keys include the run id. |
| Secrets | Sees an opaque placeholder for the one key it uses. | Vault `environment_variable`, `injection_location: {header: true}`, `allowed_hosts: [<project>.supabase.co]`. |
| Network | Supabase host, Kambi hosts, PyPI (package managers). Nothing else from the container. `web_fetch` limited per tool to PCS + organiser domains. | Environment `networking: limited`; tool `allowed_domains`. |
| Publishing | Can stage pages. **Cannot publish.** | Promotion runs on the Mac (or later an Edge Function) with a key the agent never holds. |
| Approvals / keys | Can *propose* (insert). Cannot approve. | `approvals` and `day_key_decisions.approved_by` are written by humans via the dashboard/inbox; RLS denies the agent role. |
| Spend | Bounded. | Deployment budget `$12` copied onto each session. |

Residual risks: garbage rows in append-only tables (caught by `ingest`
validators, the weekly reconciliation and human gates) and wasted budget.
Prompt injection from a PCS page reaches an agent that can only fetch
allowed domains and write a local file, and a coordinator whose only
outbound write path is an append-only role. That is the whole blast radius.

### Decisions

| Question | Decision |
|---|---|
| Executor | Managed Agents **cloud** environment. |
| Schedule | One deployment, `45 19 * * *` UTC, budget $12/session. North American finishes settle a night late (`settle_late`). Jitter ≤ 9 min. |
| Code + models + data into the container | **Release bundle** in Supabase Storage `releases/<tag>/` built weekly by the Mac: `code-<sha>.zip` (`git archive` of the release commit), `models/production/`, `inference_slice.db`, `day_menu_kernels.parquet`, `calendar/<year>.json`, campaign dirs as of release, `rider_crosswalk.csv`, `manifest.json` (shas + model contract hashes). `nightly bootstrap` downloads by sha. No GitHub resource. |
| Working state each night | `bootstrap` hydrates the campaign dirs: bundle snapshot + every artifact inserted since (`nightly-artifacts/`), so prior stages' results, scorecard and configs are present. |
| Results source | The UCI results API via the deterministic acquisition command, verbatim → `pcs_raw` row + file; deterministic `ingest` validates before use (§2.8). No fallback: a race with no `uci_competition_url` waits for the operator (`uci_url_needed`). FirstCycling only via `--source fc` on the Mac; PCS only via `--provider pcs` on the Mac. |
| Odds source | Kambi JSON from the container; brand fallback; degraded mode. |
| State out of the container | Supabase only: rows into append-only tables, files into insert-only buckets (§2.12). Nothing to git. |
| Publishing | Built pages → `site-staging/<run_id>/`. Promotion to the public site is a Mac step (or an Edge Function) reading `approvals`; the agent holds no key for it. Cloudflare stays the public surface. |
| Keys | Human keys until Gate K, entered via the inbox into `day_key_decisions` (`approved_by` set); the nightly reads approved keys; the agent key is inserted beside them and scored. |
| Prose-less publishing | Allowed for previews, never for retros. |
| Route facts | PCS stage page + organiser page via the acquisition thread; `route_overrides` table for operator corrections; missing → recorded, never invented. |
| News | v1 news-less. |
| Calendar + registry | Weekly race lists with a dates sidecar, committed to the repo and inserted into `calendar`; `registry sync` runs **weekly on the Mac** (creates `campaign.json` + `campaigns` rows for the 14-day horizon); the nightly only reads. |
| Git | The Mac run is the only committer: it pulls the week's rows and artifacts from Supabase into `performance_eval/`, commits, and reconciles. |

---

## 2. Components to build

### 2.1 Campaign registry — weekly, from the race lists, committed

`update_pipeline` step 2 already scrapes FirstCycling's per-level calendar
pages into `scraped_data/<year>/{wt,pro,d1}/<level>.txt`. Extend the weekly
step to extract the calendar row dates into a sidecar, cover the current and
next month, write `performance_eval/calendar/<year>.json` into the repo and
upsert `calendar` in Supabase. `nightly registry sync --horizon 14` runs in
the same weekly step: creates `performance_eval/<slug>-<year>/campaign.json`
once per race entering the horizon (fc_race_id, slug, category,
is_stage_race, dates, stages[], timezone, `kambi_match`, `pcs_slug`,
`void_stages: []`, `organiser_stage_urls: {}`) and the matching `campaigns`
/ `stages` rows; never overwrites. A 14-day horizon refreshed weekly keeps
≥ 7 days of cover. `CAMPAIGN_BRANDING` / `CAMPAIGNS` in the builders read
from campaign.json; Tour and Vuelta get hand-written files.

### 2.1a Horizon capture — daily, from the Mac, uploaded as artifacts

Built 2026-09-16 (build-queue chip S): `cycling_project/nightly/horizon.py`,
scheduled by `agents/mac/com.cycling.horizon.plist`.

The registry gives the cloud a *calendar-shaped* campaign — one stage per
calendar day, `stages_provisional: true`, `towns: null` — and nothing else.
The container cannot close that gap itself: FirstCycling and PCS are behind
Cloudflare, the UCI serves a calendar and results but no start list and no
route, and Kambi lists WorldTour only. That is why GP de Wallonie's preview
failed on 2026-09-15 with "no start list from any source" while Abruzzo,
Luxembourg, Slovenska and Huangshan previewed with no route or stage facts.

So the Mac supplies it, daily, before the tick. For every unit whose preview
falls inside the horizon (default 3 days — the same rule the driver's `plan`
uses for `preview`), `horizon` captures through the project's rate-limited
`WebClient`:

- the **start list** → `cached_start_lists` *and*
  `predictions/<unit>/startlist.json`, the handover shape
  `oneday.load_startlist_file` reads and `resolve_startlist` prefers; the
  existing completeness check rejects a preliminary FirstCycling shell. Since
  2026-09-18 the file is written to **every not-yet-settled unit** of the
  campaign (one list, no extra request), and due units are chosen on the
  driver's race-local clock (`driver.day_has_started`, `--local-now`), so a
  race east of UTC gets the unit the cloud tick will actually preview;
- the **FirstCycling stage page**, verbatim, → `results/<unit>/stage_page_<date>.html`
  (plus a `horizon_raw.json` index with url, time and sha256), then
  `route_facts.ingest_route` → `predictions/<unit>/route.json`;
- **stage metadata** (date, towns, distance, `itt`/`ttt` when the page says so
  in words) merged into `campaign.json` under the chip-D provisional gate:
  the stage list may only grow — or lose a calendar-invented rest-day stage —
  while `stages_provisional` is true, and the flag clears only when every
  stage is known.

Everything captured is uploaded with `upload_artifact` under
`<run_id>/<campaign_slug>/<relpath>`, which is exactly what
`bootstrap.overlay_artifacts` lays back over the release bundle on the next
tick; changed stage lists also go to `campaigns` / `stages` through
`sync_campaign` / `sync_stages`. The run is a `runs` row with phase
`horizon`, `host = 'mac'`, one `run_steps` row per step. A campaign that
fails files an `operator_tasks` row of kind `horizon_failed` (urgency
`routine`) and the command still exits 0.

It is idempotent and cheap: anything younger than `--max-age-hours` (20) is
reused, no HTTP client is built when nothing is due, and a normal day costs
one race page plus one stage page per due unit. It runs as **operator**
(host `mac`, and the registry sync is operator-only), unlike the cloud
driver.

### 2.2 The driver — `cycling_project/nightly/driver.py`

`python -m cycling_project.nightly <command>`; JSON out; exit 0 done /
10 waiting_for_input (`operator_task`) / 20 failed (`error_class`, `step`,
`log_path`); idempotent on `(campaign, unit, phase)`; every run and step is a
row in `runs` / `run_steps` (plus a local `runs/<date>/<phase>.json`);
global file lock around SQLite writes. Supabase access through
`cycling_project/nightly/store.py` (PostgREST + Storage; key from the
`SUPABASE_NIGHTLY_KEY` env var, which is the vault placeholder in the cloud
and a real key on the Mac).

| Command | Runs |
|---|---|
| `bootstrap` | Download the release named in `releases` (newest `approved`) by sha, verify model contract hashes, `uv sync`, point serving at `inference_slice.db`, **hydrate** campaign dirs from the bundle snapshot + all `nightly-artifacts/` inserted since, load approved `day_key_decisions` into the local configs. Fails closed on any mismatch. |
| `plan [--now]` | Due units from `campaigns`/`stages` + local state, on the **race-local clock**: `settle` once the unit's own local day is over (a past local date, or the local date past 18:00 local), `preview` while that day has not begun (before 09:00 local) and it is inside the horizon; flags `settle_late`, `blocked`. The fixed 19:45 UTC tick is already tomorrow east of UTC, which made Huangshan stage 1 settle-due before it was ridden (2026-09-17). `--local-now <ISO>` overrides the clock; `--today` alone reads as that date's evening. |
| `night --campaign <slug>` | Every due `settle`, then every due `preview`, in order. |
| `settle` | `ingest` → `seed_state_cache.py` → GC config templated → GC predict → `build_gc_tracker.py` → `score_day_keys.py` (always) → `retro_facts.json` → `build_stage_page.py` → site index + frame → `upload` (results files, facts, pages, `prediction_log` rows). |
| `preview` | Kambi capture → stage config (template if the campaign ships one, else written from `campaign.json`) → GC config when absent → route facts (from the acquisition thread's `route_raw`) → **`startlist`** (a handover beside the config or beside any sibling unit, or a cache row, else exit 10 `startlist_needed`; every unit since 2026-09-18) → `bundle` → **exit 10 unless** a key exists: config key, then an approved `day_key_decisions` row, then the agent's own record (`--agent-key <path>`, or `predictions/<unit>/agent_key.json` found without a flag) → `refs_check` (every reference a config carries must have a `competition_field_features` row: a machine-written bad set is emptied and rewritten, a human's waits as `scenarios_needed` naming the id) → `scenario_refs` (references derived from that key, servable ones only) → `predict_stage_scenarios.py` (`--no-scrape` unless `--allow-scrape`) → `validate` → `build_stage_page.py` → site index + frame → `upload`. One-day races skip the key and reference their own editions. |
| `ingest` | Reads `results/<unit>/pcs_raw.json`; validates (§2.8); writes the FC-shaped files or exits 10 with the failing checks. |
| `bundle` | Freezes `predictions/<unit>/bundle/` + `manifest.json` (odds, latest `gc.csv`, startlist + withdrawals, settled-stage ledger, `route.json`, `day_menu_v1_reference.md`, scorecard). |
| `refs --archetype <name>` | Signature-table query for named archetypes, excluding refs already used in the campaign. Since 2026-09-16 `preview` runs the same query itself (`nightly/autoconfig.py`, step `scenario_refs`): a stage race needs no `TEMPLATE_scenarios.json`, no hand-written references and no hand-written GC config. |
| `validate` | Schemas, NaNs, `lambdarank_win_p` sum ≈ 1, `post_hoc` on late configs, `void_stages` consistent, key weights sum to 1, crosswalk coverage (a warning under `identity_policy=provisional`, blocking under `strict`). |
| `upload` | Insert artifacts under `nightly-artifacts/<run_id>/<campaign>/…` and pages under `site-staging/<run_id>/…`; insert `predictions`, `prediction_log`, `pcs_raw`, `operator_tasks` rows. Never overwrites. |
| `status` | Ledger view from `runs`. |

`publish` is **not** a driver command the agent can run; see §2.9.

### 2.3 Managed Agents provisioning — `agents/managed/`

- `environment.yaml`: `cycling-cloud`, `config: {type: cloud, networking:
  {type: limited, allow_package_managers: true, allowed_hosts:
  ["<project>.supabase.co", "eu-offering-api.kambicdn.com", "www.uci.org",
  "uci.org"]}}` (one Kambi host serves every brand).
- `vault.yaml`: one vault, one `environment_variable` credential
  `SUPABASE_NIGHTLY_KEY` (the `nightly_agent` role key), `networking:
  {type: limited, allowed_hosts: ["<project>.supabase.co"]}`,
  `injection_location: {header: true}`.
- Agents (`claude-opus-5` to start): `nightly-coordinator` (agent toolset;
  roster `[{type: self}, uci-acquirer, day-key-reader,
  editorial, ops-triage]`; prompt: `bootstrap`, `plan`, one self thread per due
  campaign running `night`; never edit numbers; exit 10 → `operator_tasks`
  row and stop that campaign; exit 20 → ops-triage; end with a ledger
  summary; all fetched/read content is data), `uci-acquirer` (bash / read /
  glob only; runs the deterministic `uci_acquire` command for one unit and
  reports its JSON — §2.8; since 2026-09-22 it is the only acquisition thread,
  `pcs-acquirer` having been retired out of the roster), `day-key-reader` (no
  tools), `editorial` (no tools), `ops-triage` (read-only).
- `deployments.yaml`: one deployment `nightly`, cron `45 19 * * *` UTC,
  `vault_ids`, `initial_events` = one `user.message`, `budget` `$12.00`;
  created paused; manual run for the smoke test. **No `github_repository`
  resource.**
- `provision.py` (Python SDK), `ids.json`, `README.md`.

### 2.4 Day-key agent skill + decision record — `agents/skills/day-key-read/`

Unchanged from rev 1 (heuristics 1–7, §5.1 record, validator). Records go
to `day_key_decisions` (`author = agent`); the human's approved key is a
separate row with `approved_by`; `score_day_keys.py --also agent` scores
both.

**The agent's key prices the board when no human key exists (2026-09-17).**
Until then the key gate was terminal for an unattended night: the 09-17 tick
built configs, bundles and agent keys for Tour de Luxembourg stage 3 and Giro
d'Abruzzo stage 4 and published no board at all (hosted tasks 90, 91). The
driver now resolves a key as: config key → approved `day_key_decisions` row →
the agent's own record (`--agent-key <path>`, or `predictions/<unit>/agent_key.json`
found without a flag) → exit 10. A board priced from the agent's record carries
`day_key_author: "agent"` and `day_key_source: "agent:<file>"`.

This does **not** move Gate K. Gate K is about whose judgment the *tier-3
archive* records, and the stamp keeps that boundary exactly where it was:
`score_day_keys.py` refuses to read an agent-authored config as a logged human
read (the tier-3 row stays unkeyed) and scores the record through
`--also agent`, so the agent is graded as itself, on its own card, against the
human's when one exists. The public claim is gated twice over: the page says
the key was machine-written, and publication still needs an inbox approval and
`promote.py`. What changed is the *cost of an unattended night* — a board and a
page now exist to approve — not who is trusted with the judgment.

### 2.5 Editorial agent skill + lexicon linter — `agents/skills/editorial/`

Unchanged from rev 1. Drafts go to `editorial_drafts`; the builder uses a
draft only when `approved_by` is set (until Gate E).

### 2.6 One-day race path — built 2026-09-08 (build-queue chip K)

A one-day race is one unit, `race`. `cycling_project/nightly/oneday.py` owns
the shape: `predictions/race/scenarios.json` (`target: one_day`, no `stage`,
no `void_stages`, **no `day_key`** — the menu's items are stage-day shapes),
whose default `own_history` scenario prices the race on its **own last five
editions** (competition ids looked up from the database by `fc_race_id`,
restricted to editions with a `competition_field_features` row) and whose
optional alternates use archetype references (`nightly refs --archetype …`).
`validate_config` is the loader both the runner and the driver's `validate`
call, so a malformed config fails in a second rather than after the model
registry has loaded.

- **Serving**: `predict_stage_scenarios.py` takes `target: one_day` — no race
  state, no day key, and the service builds the one-day contest-signature
  context from the scenario's references. The field comes from a
  `startlist.json` beside the config (what the acquisition thread hands over,
  since the container cannot reach FirstCycling), else `cached_start_lists`,
  else a rate-limited scrape (`--no-scrape` refuses it).
- **The driver proves the field before it runs `predict` (2026-09-17).** The
  scrape is the last resort in `resolve_startlist`, and in the container it is
  a Cloudflare 403 *inside* the runner: Kampioenschap van Vlaanderen 2026 had
  no handover, missed the cache, and turned a missing start list into exit 20
  and a paid ops-triage cycle (hosted task 93). Any preview unit (2026-09-18;
  before that only one-day and stage 1, which let Tour of Huangshan stage 2
  fail inside `predict`) with no handover beside its config or any sibling
  unit's, and no `cached_start_lists` row for
  (`fc_race_id`, `year`) now exits 10 with `startlist_needed`
  (`blocks_publication`), naming the Mac's daily `nightly.horizon` capture as
  the supply. The driver also passes `--no-scrape` to the runner by default, on
  every predict it launches; `--allow-scrape` is the attended-Mac opt-in. The
  inbox retires the ask when a later run's `predict` step succeeds — the step
  that consumes the list is the proof it arrived.
- **Results**: `results/race/results.{csv,json}` + `classifications.json`, the
  same FC-shaped archive a stage settles to. `uci_ingest` reads a one-day
  capture's single "General Classification" as the race result, keeps the
  top-15 identity gate, and writes **no `gc.csv`** — a one-day race has no
  standing to track. `oneday.export_results_from_db` backfills the archive for
  a race the database already holds. The PCS fallback is still stage-shaped: a
  one-day PCS capture is refused at `pages_present` (`missing: ["gc"]`), never
  half-written.
- **Page + frame**: `build_oneday_page.py` writes `netlify_site/<slug>-<year>.html`
  (scenario fork, one board with blend / cascade / LambdaRank / market columns,
  and after settlement the result scored and joined on the FirstCycling rider
  id). The frame gives `type: one_day` a compact hub at `/race/<slug>/<year>`
  with the board at `/race/<slug>/<year>/prediction`, and the calendar and
  races views show the race as a single row.
- **Driver**: `preview` writes the config itself when absent, asks for no day
  key and freezes no bundle; `settle` skips the state seeding, the GC config
  and the key scoring; `_build_pages` runs the one-day builder.
- **Known gap**: the serving path re-ages form to the day the board is built,
  not to the config's race date (`asof_date` reaches the contested-rating
  snapshot but not `assemble_prediction_df`). That is correct for a board cut
  on race morning and wrong for a reconstruction, so a `post_hoc` config makes
  the page print a banner naming the leak.

### 2.7 Operator inbox

Two tiers: (1) the Supabase dashboard is the inbox on day one — `runs`,
`operator_tasks`, `day_key_decisions`, `approvals`, `crosswalk_proposals`
are plain tables a human edits; (2) `_frame/ops.html` renders from those
tables (Supabase JS client, anon read of a view) with approve actions that
write `approvals` rows as the human (Supabase Auth). Notifications: a
Supabase Database Webhook on `operator_tasks` insert → push/email; the
deployment-run webhooks from the Console → the same.

### 2.8 Acquisition: the UCI results API, validated deterministically

> **2026-09-22 (chip X): the PCS fallback is retired from the cloud.** UCI is
> not "primary" any more — it is the only source the nightly has. The
> `pcs-acquirer` agent is out of the coordinator's roster (its yaml lives under
> `agents/managed/retired/`), the coordinator prompt (revision 6) does not
> mention PCS, `--provider auto` resolves to UCI and nothing else, and a
> campaign with no `uci_competition_url` raises `uci_url_needed` — an ask
> addressed to the **operator**, carrying the matcher's candidates — where it
> used to raise `pcs_pages_needed`, an ask that told the cloud to go and get
> ProCyclingStats pages. Everything below about PCS describes the **attended
> Mac path** (`--provider pcs`, `pcs_ingest.py`), which still works by hand.
> Why it matters: PCS has 403ed Anthropic's fetcher since 2026-09-06, so the
> path was dead while still being described as live, and on 2026-09-22 the
> coordinator spent ten tool calls (session `sesn_01EXAMPLE78CD3112BF8B3A4`,
> Giro della Romagna) reading `pcs_ingest.py`, the acquirer prompt and the PCS
> fixtures to work out how to satisfy the ask. See `performance_eval/LESSONS.md`
> 2026-09-22.

**The rule:** an LLM never transcribes, repairs, reorders or invents a result
row. It may only *invoke* a deterministic acquisition command (UCI); nothing
downstream trusts a capture until the driver's `ingest` has validated it, and
the weekly FirstCycling reconciliation is the backstop.

**Why UCI (2026-09-06).** PCS moved behind a Cloudflare wall that also
refuses Anthropic's `web_fetch` (the August verification no longer holds:
every fresh PCS URL answers `url_not_accessible`; see
`agents/managed/README.md`). The UCI website is open: the competition page
`https://www.uci.org/competition-details/<year>/<discipline>/<id>` answers
plain `requests` with no cookies or browser, and its
`CompetitionDetailsModule` `data-props` JSON lists every stage's
classifications with an `eventCode`, which
`GET https://www.uci.org/api/calendar/results/<eventCode>?discipline=…&raceType=…&raceName=…`
turns into a complete JSON result table (Stage 14 of the Vuelta 2026: 155
entries = 150 ranked + 4 DNF + 1 DNS, gaps identical to the FirstCycling
archive). UCI carries no rider id, team id, bib or full birth date, so the
identity layer does the bridging (below).

- **uci-acquirer thread** (per due settle unit): runs
  `python -m cycling_project.nightly.uci_acquire --competition-url <url>
  --campaign <dir> --unit <unit>` once and reports the printed JSON. The
  command (`cycling_project/nightly/uci_acquire.py`, stdlib + `requests`,
  ≥ 3 s + jitter between requests, explicit timeout, bounded retries for
  transient failures only) fetches the raw competition page, decodes
  `data-props` (`html.unescape` → `json.loads`), selects the stage by exact
  label and its classifications by exact title (Stage / Stage General
  required; Overall Points / Mountain / Youth / Team optional), builds each
  results URL with `urllib` (a literal `%26` is a regression-tested
  failure), saves every response **verbatim** under `results/<unit>/uci/`
  (`competition.html`, `stage.json`, `gc.json`, …) and writes `uci_raw.json`
  (provider, source URL, event code, race type, race name, fetched time,
  HTTP status, content type, bytes, sha256, row count, error). Re-runs
  reuse a complete capture without a request and never overwrite a
  differing one (`--refresh` needs `--supersede`, which moves the old
  capture to `previous_<ts>/`). Exit 0 complete · 10 not published yet ·
  20 bad URL / no module / stage absent. The `settle` phase also runs the
  same acquisition in-process when the campaign is mapped and nothing is
  captured (`--no-acquire` disables it); the agent path and the driver path
  are the same idempotent function.
- **`nightly ingest`** (`uci_ingest.py`) validates: competition name /
  year / discipline match the campaign; the stage exists in both schedule
  and results accordion; every event code is non-empty with a supported
  race type; each response is HTTP 200 JSON with `results` / `headers` /
  `podium`; the winner is rank 1 with an absolute time; ranks numeric,
  unique, contiguous; riders unique; gaps parse (`+s`, `+m:ss`,
  `+h:mm:ss`, equal-time) non-negative and monotone; statuses recognised
  (DNS DNF OTL DSQ DQ NR DF); `podium` equals the first three rows; the GC
  winner has an absolute total and GC gaps parse; GC rows = the classified
  field; stage top-15 and GC top-20 resolve to FirstCycling ids at ≥ 0.97
  (see the identity-policy ruling below); FC ids unique.
  Only then are `results.csv` / `results.json` / `gc.csv` /
  `classifications.json` written (byte-compatible with the FirstCycling
  capture; `results.json` keeps the original UCI strings under `uci`).
  Failure → exit 10 with the failing checks and an operator task; the raw
  capture is kept; nothing partial is written.
- **Identity bridge** (`uci_identity.py`): each UCI row is resolved
  against the campaign roster (the archived earlier stages — after stage 1
  it is the whole field), else the confirmed crosswalk rows, else the
  riders table with the race's cached startlist. Exact accent-insensitive
  full name, unique in scope, with no birth-year conflict → 0.97 (0.99
  when age or team corroborates it); stored team history is evidence, not a
  veto, because it can lag transfers. The same with surname or given names
  *extended* on one side (`BUITRAGO SANCHEZ Santiago` ↔ `Buitrago
  Santiago`, `SOSA CUERVO Ivan Ramiro` ↔ `Sosa Ivan`) → 0.97 when age
  or team corroborates the unique match, with the evidence recorded;
  nicknames, homonyms, fuzzy similarity, or age /
  nationality alone → a `crosswalk_proposals` row (`pcs_slug =
  uci:<alias key>`, `source=uci` in the evidence) and an operator task,
  never an acceptance. Human-confirmed aliases live in
  `performance_eval/crosswalk/uci_aliases.csv` (`python -m
  cycling_project.nightly.uci_identity confirm …`); `uci_key` is an alias
  key derived from the name, never presented as a UCI id. Names are never
  ids. Vuelta 2026 stage 14: 150 of 155 rows resolve deterministically with
  zero errors against the archive; the five leftovers (Chris/Christopher,
  Nick/Nicholas, Mulubrhan/Mulueberhan, Skjelmose's Danish name order,
  Cort/Nielsen) are confirmed aliases.
- **Identity policy inside the top gate — operator ruling 2026-09-16**
  (supersedes the strict half of the 2026-09-08 ruling for **unattended**
  runs). `--identity-policy {strict,provisional}` on `nightly ingest`,
  `settle` and `night`, **default `provisional`** because the cloud tick has
  no operator:
  - `strict` — an unresolved rider inside the top-15 stage / top-20 GC gate
    refuses the capture (exit 10, `ingest_failed`, `blocks_settlement`) and
    asks a human. The Mac runbook passes this for attended runs.
  - `provisional` — that rider is archived exactly like an
    outside-the-gate row: provisional `uci:<alias key>` id, the row kept,
    place and time intact. `crosswalk_top` becomes a **warning**, the report
    gains `provisional_top` (name, place, best candidate + score, team, age),
    `results.json` records `provisional_identities` / `identity_policy`, the
    published page carries a plain caveat naming the riders, and the driver
    files a **routine** `identity_provisional` task (never a waiting state).
    The `crosswalk_proposals` rows are filed either way.
  The fix is made durable on the Mac: confirm the mapping in the inbox
  (`crosswalk confirm` / `confirm --from-pending`), then run `python -m
  cycling_project.nightly.crosswalk reconcile-results --campaign <dir>`,
  which rewrites the confirmed `uci:` ids in every archived `results.csv` /
  `gc.csv` / `results.json` / `classifications.json` (idempotent; only a
  human confirmation rewrites an archived result). Downstream, a provisional
  id is read as a rider who is **not in the model field**: `hindsight` and
  `score_day_keys` drop it before the riders-table join (archetype
  "unknown"), and the frozen post-hoc field excludes it and records that it
  did. What this ends: Trofeo Matteotti (rank 15) and Okolo Slovenska (ranks
  11, 14) each sat in `waiting` for three nights over one unmappable rider.
- **Provider selection and provenance** (`driver.py`): `--provider auto` (the
  default) means **UCI, full stop** since 2026-09-22 — it resolves to `uci`
  when a complete capture exists and to nothing otherwise, even with PCS pages
  sitting in `results/<unit>/pcs/`. `pcs` is reachable only by naming it
  (`--provider pcs`), on the attended Mac. A campaign with no
  `uci_competition_url` cannot be settled: exit 10 `uci_url_needed`
  (`blocks_settlement`), whose detail carries `uci_match_evidence` — the
  candidate and alternates `uci_calendar.py` recorded — so the operator picks
  the competition page in the inbox. The provider is recorded in the run record
  (`provider`, `fallback_reason`), the `acquire` / `ingest` step details
  and every raw-provenance row (`store.insert_acquisition_raw`: until
  migration `0004_acquisition_provider.sql` is pushed, rows land in
  `pcs_raw` with `kind = 'uci:<kind>'` and `ingest_detail.provider = 'uci'`;
  the migration adds a `provider` column and the `acquisition_raw` view).
  Two providers are never blended into one classification; a UCI
  rejection stops the unit (exit 10), it does not fall through to PCS.
- **Registry**: `campaign.json` carries `uci_competition_url`,
  `uci_competition_id`, `uci_discipline`. `uci_calendar.py` (2026-09-07)
  resolves them from the UCI road calendar — two requests
  (`/api/calendar/upcoming` and `/api/calendar/past`, `?discipline=ROA`, no
  token, no cookies) archive the whole season under
  `cycling_project/tests/fixtures/uci/calendar/`, and the matcher compares
  dates and normalised names (country is recorded but not compared: our
  calendar rows carry none). A URL is written only on an **exact** date range
  with name similarity ≥ 0.90 and no rival exact-date candidate at that bar;
  anything else stays `null` and becomes a `uci_competition_confirm` operator
  task with the candidate, the score and the reason. A set URL is never
  overwritten. `registry sync` applies the same matcher at creation
  (`--no-uci-match` opts out); `uci_calendar resolve` fills existing
  campaigns; every campaign keeps a `uci_match_evidence` block. Start lists
  and route facts keep their current paths — UCI is a results source only
  until tested for more.
- **One-day races** (verified 2026-09-07 on GP Industria & Artigianato,
  competition 78396): the accordion holds one entry labelled `Final
  Classification` whose single classification is titled `General
  Classification` — no `Stage Classification` exists, so `required_kinds()`
  asks only for `gc` on a one-day unit, and `one_day` (the registry's unit
  name) is a synonym for `race`. `uci_ingest` reads that one document as the
  race result (2026-09-08, chip K): the same winner / rank / gap / status /
  podium / identity checks run on it, `gc_winner_and_gaps` and
  `row_counts_plausible` are replaced by `one_day_single_classification`, the
  top-20 GC identity gate collapses into the top-15 result gate, and no
  `gc.csv` is written.
- **PCS, attended Mac only** (retired from the cloud 2026-09-22): the
  `pcs-acquirer` yaml sits under `agents/managed/retired/` and is no longer
  provisioned or delegated to. `pcs_ingest.py` still parses a saved page with
  the verified DOM map (result tabs `ul.resultTabs li.cur` ↔
  `div.resTab[data-id]`, `td.ridername a[href^="rider/"]`, `,,` = same time,
  transposed links cross-checked) when a human puts pages under
  `results/<unit>/pcs/` and runs `--provider pcs`. Nothing automatic reaches
  it, and the coordinator is never told it exists.
- **Kambi**: container HTTP; brand fallback `ubnl → ubuk → ubse` (one host,
  `eu-offering-api.kambicdn.com`); brand recorded; `degraded` when every
  brand blocks; `--wait-for-stage`.
- **Weekly reconciliation** on the Mac: diff each night's `results.csv` /
  `gc.csv` (pulled from Supabase) against the FirstCycling pickle for the
  same stage; log to `reconciliation` table + jsonl; drift above threshold →
  operator task. The rollout gates for making UCI primary in fact (identity
  coverage ≥ 99 %, all top-15 / top-20 resolve, no unexplained differences
  over a race week) are in `UCI_MANAGED_AGENT_BUILD_BRIEF.md`.

### 2.9 Publishing — outside the agent

The nightly stages pages under `site-staging/<run_id>/`. `promote`
(`cycling_project/nightly/promote.py`, run by the weekly Mac step or on
demand, with a key the deployment does not hold) reads `approvals`, copies
the approved run's pages into the repo's `netlify_site/`, commits, and
deploys through Cloudflare (Workers Builds on the `site` branch, or
`wrangler deploy`). Post-Gate-E the same promotion can move to a Supabase
Edge Function triggered by an `approvals` insert — still not the agent.

### 2.10 Weekly release from the Mac — the critical path

The cloud session cannot open the 3.3 GB `cycling_races.db`; it needs a
slim inference slice, and it needs *code and models it cannot alter*.

1. **Instrument**: run `predict_stage_scenarios.py --no-log` for a stage
   config, the GC config and a one-day config with a `sqlite3` trace
   callback; record every statement and table.
2. **Export** `inference_slice.db` (target **< 500 MB**, VACUUM): `riders`,
   `races`, `competitions`, `teams`, `rider_team_history` in full;
   `rider_results` for every rider on a startlist in the horizon plus every
   reference competition in any scenario config; latest
   `rider_competition_snapshots` per such rider; `rider_race_state` for
   in-progress races; `race_features_*`, gradients, thresholds (full if
   under budget, else for reference comps); `cached_start_lists`; empty
   `prediction_log`; `rider_crosswalk`.
3. **Parity**: re-run the three configs against the slice; byte-identical
   probabilities.
4. **Bundle + upload** (`weekly_release.py`, an `update_pipeline` step after
   training): `git archive` the release commit → `code-<sha>.zip`; collect
   `models/production/` (+ kernels parquet), the slice, calendar, campaign
   dirs, crosswalk CSV; write `manifest.json` (shas, model contract hashes,
   db snapshot date); upload to `releases/<tag>/`; insert a `releases` row
   (`approved` set by the human running the step).
5. **Pull + merge back** (`weekly_pull.py`, before step 1 next week):
   download the week's `nightly-artifacts/` into `performance_eval/`,
   import `prediction_log` rows into the real DB (idempotent), import
   `day_key_decisions`/`editorial_drafts` into the configs, run
   reconciliation, commit on `webscrape-refactor`.

### 2.11 Tests + replay

`tests/unit/test_nightly_driver.py` replays the committed Vuelta stage
14 → 15 archive through `night --dry-run` (no fetches, `--no-log`, a local
fake store) and asserts `retro_facts.json`, the run rows and the built
pages. `test_nightly_ingest.py` covers every validator with fixtures.
`test_store.py` runs against a local Supabase (`supabase start`) and asserts
the agent role **cannot** update, delete or read `approvals` secrets.

### 2.12 Supabase control plane — schema and roles (`supabase/`)

Migrations in `supabase/migrations/`, a `supabase/README.md`, and a Python
client `cycling_project/nightly/store.py`.

Tables (all with `created_at`, most append-only):

| Table | Written by | Purpose |
|---|---|---|
| `calendar`, `campaigns`, `stages` | Mac (weekly) | Registry; `stages.void` for cancelled stages. |
| `releases` | Mac | Release tags, manifest, `approved`. |
| `runs`, `run_steps` | agent (insert) | Ledger: campaign, unit, phase, state, exit codes, session id, step timings, log object key. |
| `pcs_raw` | agent (insert) | Verbatim transcriptions + `ingest` verdict. |
| `predictions` | agent (insert) | Scenario configs + board JSON object keys per unit and run. |
| `prediction_log` | agent (insert) | Same schema as the SQLite table; imported weekly. |
| `day_key_decisions` | agent (insert, `author=agent`), human (insert with `approved_by`) | Both keys per stage; scored by `score_day_keys.py`. |
| `editorial_drafts` | agent (insert), human (`approved_by`) | Prose records. |
| `operator_tasks` | agent (insert), human (update `resolved`) | Inbox. |
| `crosswalk`, `crosswalk_proposals` | Mac / human; agent proposes | Rider identity. |
| `approvals` | human only | Publication approvals per run. |
| `reconciliation` | Mac | PCS↔FC diffs. |

Roles: `nightly_agent` (INSERT on the agent tables, SELECT on registry and
its own rows, **no UPDATE/DELETE/DDL**, RLS on), `release_reader` (SELECT on
`releases` bucket objects), `operator` (human, dashboard/Auth). Buckets:
`releases` (private; read for `release_reader`, write for Mac),
`nightly-artifacts` and `site-staging` (insert-only for `nightly_agent`,
object keys must start with the run id), `site` (Mac/promotion only). The
agent's key is minted for the `nightly_agent` role (Supabase's key mechanics
are checked against current docs in the chip — do not hand the agent a
service-role key).

---

## 3. Rollout

| Phase | What runs | Human does | Exit gate |
|---|---|---|---|
| **0 — Vuelta shadow (now → Sep 13)** | Human runs the runbook on the Mac. Day-key agent shadow each morning; `pcs-acquirer` + `ingest` dry-run each evening against the FirstCycling archive to measure transcription accuracy. Supabase project + schema stood up; the Mac run starts inserting `runs`. | Everything, as today. | Validators catch every seeded fault; crosswalk coverage ≥ 99 %. |
| **1 — Slice + driver on the Mac (Sep 14 →)** | Weekly release built and uploaded; driver runs `night` on the Mac *against the bundle* with the `nightly_agent` key, exactly as the cloud will. | Keys, approvals, crosswalk confirmations in the dashboard. | Parity on the slice; a race week with no manual commands except keys + approvals; the agent role provably cannot update/delete. |
| **2 — Cloud nightly (October)** | Deployment live; coordinator + acquisition + ops-triage; day-key + editorial recorded. | Keys/approvals from the inbox; weekly Mac release + promote. | ≥ 95 % sessions schema-valid, none over budget, failure table exercised, reconciliation clean. |
| **3 — Promotion (2027)** | Gate E, then Gate K, per `AGENT_DESIGN.md` §6; promotion moves to an Edge Function. | Vetoes. | Per gate. |
| **4 — Cloudflare envelope for the public site** | Access-protected inbox, atomic publish pointer. | — | Plan phases 2–3 (public surface only). |

---

## 4. Prerequisites and risks

- **Supabase project** (free tier is enough to start; Storage egress for
  a ~700 MB bundle per night is the cost to watch — cache by sha, and
  consider a 7-day-stable bundle). Two keys: `nightly_agent` (vault) and
  the Mac's operator key (Keychain).
- **Bundle size** decides feasibility: code ≈ small, models ≈ 200 MB,
  kernels 103 MB, slice < 500 MB target. If the slice cannot get under
  budget, slim the serving path (precomputed reference profiles), not the
  download.
- **PCS transcription risk** bounded by `ingest` + reconciliation; the
  PCS↔FC gap convention (bonus-inclusive GC) must be handled explicitly.
- **Kambi geo**: brand fallback untested from the container's egress;
  previews run degraded if every brand blocks.
- **Cost**: 2–8 Opus threads per night; budget cap $12; Storage egress.
- **What the agent can still do wrong**: insert bad rows (validated,
  gated, reconciled), waste budget (capped), read the code (a copy, same
  exposure as any CI container). It cannot change the code, the models,
  the data, the site, an approval, or a key.
