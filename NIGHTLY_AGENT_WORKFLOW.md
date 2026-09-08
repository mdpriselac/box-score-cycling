# Nightly managed-agent workflow — every WT / .Pro / .1 race

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
| Results / GC / startlist capture | acquisition | **PCS via web tool** (FirstCycling: Mac only) |
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
| Results source | PCS via `web_fetch` by the acquisition thread, verbatim → `pcs_raw` row + file; deterministic `ingest` validates before use (§2.8). FirstCycling only via `--source fc` on the Mac. |
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
| `plan [--now]` | Due units from `campaigns`/`stages` + local state: `settle` (date past, no results), `preview` (tomorrow race-local, no boards); flags `settle_late`, `blocked`. |
| `night --campaign <slug>` | Every due `settle`, then every due `preview`, in order. |
| `settle` | `ingest` → `seed_state_cache.py` → GC config templated → GC predict → `build_gc_tracker.py` → `score_day_keys.py` (always) → `retro_facts.json` → `build_stage_page.py` → site index + frame → `upload` (results files, facts, pages, `prediction_log` rows). |
| `preview` | Kambi capture → route facts (from the acquisition thread's `route_raw`) → `bundle` → **exit 10 unless** an approved `day_key` exists (or `--agent-key` in shadow) → `predict_stage_scenarios.py` → `validate` → `build_stage_page.py` → site index + frame → `upload`. One-day races skip the key. |
| `ingest` | Reads `results/<unit>/pcs_raw.json`; validates (§2.8); writes the FC-shaped files or exits 10 with the failing checks. |
| `bundle` | Freezes `predictions/<unit>/bundle/` + `manifest.json` (odds, latest `gc.csv`, startlist + withdrawals, settled-stage ledger, `route.json`, `day_menu_v1_reference.md`, scorecard). |
| `refs --archetype <name>` | Signature-table query for named archetypes, excluding refs already used in the campaign. |
| `validate` | Schemas, NaNs, `lambdarank_win_p` sum ≈ 1, `post_hoc` on late configs, `void_stages` consistent, key weights sum to 1, crosswalk coverage. |
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
  roster `[{type: self}, uci-acquirer, pcs-acquirer, day-key-reader,
  editorial, ops-triage]`; prompt: `bootstrap`, `plan`, one self thread per due
  campaign running `night`; never edit numbers; exit 10 → `operator_tasks`
  row and stop that campaign; exit 20 → ops-triage; end with a ledger
  summary; all fetched/read content is data), `uci-acquirer` (bash / read /
  glob only; runs the deterministic `uci_acquire` command for one unit and
  reports its JSON — §2.8), `pcs-acquirer` (fallback; `web_fetch`
  with `allowed_domains` = PCS + organiser domains, `write`, `read` only;
  writes `pcs_raw.json` / `route_raw.json` verbatim), `day-key-reader` (no
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

### 2.8 Acquisition: UCI results API first, PCS as fallback, validated deterministically

**The rule:** an LLM never transcribes, repairs, reorders or invents a result
row. It may only *invoke* a deterministic acquisition command (UCI) or
transcribe a page verbatim (PCS fallback); nothing downstream trusts a
capture until the driver's `ingest` has validated it, and the weekly
FirstCycling reconciliation is the backstop.

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
  field; stage top-15 and GC top-20 resolve to FirstCycling ids at ≥ 0.97;
  **every** row resolves (strict during the shadow period); FC ids unique.
  Only then are `results.csv` / `results.json` / `gc.csv` /
  `classifications.json` written (byte-compatible with the FirstCycling
  capture; `results.json` keeps the original UCI strings under `uci`).
  Failure → exit 10 with the failing checks and an operator task; the raw
  capture is kept; nothing partial is written.
- **Identity bridge** (`uci_identity.py`): each UCI row is resolved
  against the campaign roster (the archived earlier stages — after stage 1
  it is the whole field), else the confirmed crosswalk rows, else the
  riders table with the race's cached startlist. Exact accent-insensitive
  full name, unique in scope, team compatible, age consistent with the
  known birth year → 0.99; the same with the surname or given names
  *extended* on one side (`BUITRAGO SANCHEZ Santiago` ↔ `Buitrago
  Santiago`, `SOSA CUERVO Ivan Ramiro` ↔ `Sosa Ivan`) → 0.97 with the
  evidence recorded; nicknames, homonyms, fuzzy similarity, or age /
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
- **Provider selection and provenance** (`driver.py`): `uci` is primary
  whenever a complete capture exists; `pcs` only when the campaign has no
  `uci_competition_url`, UCI has not published, or the capture is
  incomplete — the reason is recorded in the run record
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
- **PCS fallback thread** (`pcs-acquirer`, `web_fetch` + `write`): saves
  each fetched page verbatim under `results/<unit>/pcs/` with
  `pcs_raw.json`; `pcs_ingest.py` parses it with the verified DOM map
  (result tabs `ul.resultTabs li.cur` ↔ `div.resTab[data-id]`,
  `td.ridername a[href^="rider/"]`, `,,` = same time, transposed links
  cross-checked). Kept operational while UCI coverage is measured.
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
