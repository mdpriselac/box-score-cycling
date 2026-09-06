# Cloudflare deployment and automation plan

## Product vision

Build a public cycling-prediction archive in which:

1. Races are discoverable by recency, date, race, and stage.
2. Before a race, a scheduled agent freezes the available evidence, chooses
   stage-race day keys, runs the prospective models, and publishes pages like
   the current Tour and Vuelta pages.
3. After results arrive, the workflow settles predictions, updates stage-race
   state and GC outlooks, writes a retrospective, and republishes the page.
4. Monthly jobs publish aggregate retrospectives from immutable records.
5. Missing or blocked start lists/results become visible operator tasks rather
   than silent failures.

The existing Python prediction service, scenario runner, page builders, and
campaign archives remain the initial source of truth. Cloudflare is an
operational envelope around them, not an immediate model rewrite.

## Recommended architecture

```text
                         public requests
                                |
                  Cloudflare Worker + Static Assets
                  /races, /calendar, /race/:slug
                       |                 |
                     D1 API          published HTML
                       |
       Cron schedule -> durable Workflow -> run ledger
                              |
                 acquire and freeze evidence
              odds / route / news / start list
                              |
                stage race? -- yes --> key agent
                     |                    |
                     +------ run request-+
                              |
                  Python prediction executor
             external runner first; Container later
                              |
                  validated publication bundle
                     |                    |
                  R2 archive        D1 metadata/index
                     |
                  atomic publish pointer
```

### Cloudflare components

- **Workers Static Assets:** serve the HTML/CSS/JS currently generated into
  `netlify_site/`.
- **Worker API:** calendar, recent races, race metadata, run status, and an
  authenticated operator surface.
- **D1:** small control-plane data: races, stages, deadlines, run state, source
  status, publications, and operator tasks. Do not move the full training
  warehouse into D1 initially.
- **R2:** immutable inputs and outputs: odds, route images/data, permitted news
  snapshots, start-list/result uploads, prediction JSON, model manifests,
  transcripts, and publication bundles.
- **Workflows:** durable multi-step execution, retries, and pauses for missing
  inputs or human approval.
- **Cron Triggers:** discover due work. Cron runs in UTC, so store race-local
  deadlines converted to UTC.
- **Queues:** add for fan-out and external execution. Delivery is at-least-once,
  so every message and write needs a deterministic idempotency key and a
  dead-letter queue.
- **AI Gateway:** route and observe agent calls while recording provider, model,
  prompt version, usage, latency, and result identity in the project ledger.
- **Browser Run:** optional evidence acquisition from sources that permit it;
  not a plan for bypassing another site's anti-bot controls.
- **Containers:** eventual Cloudflare-native home for Python/LightGBM. Ordinary
  Workers do not accept native binaries, while Containers provide a full Linux
  runtime. Keep the executor contract portable so this migration is optional.

## Acquisition boundary

Start-list and result scraping is the largest blocker and must not be coupled
to page serving or model correctness.

Accept source artifacts in this order:

1. Licensed or official structured source.
2. Successful automated capture from a permitted source.
3. Authenticated manual upload or correction.
4. Previously frozen capture, only when explicitly marked stale.

Every artifact receives a timestamp, source/provider, content hash, parser
version, and validation result. The workflow never invents a start list or
result. If one is absent, the run becomes `waiting_for_input`, creates an
operator task, and leaves the last valid public page untouched.

The first operator feature should be a weekly start-list inbox showing races in
the next 14 days, freshness, rider-match failures, and a CSV/JSON paste or
upload action. Results need the same fallback. This makes the system useful
before scraping is permanently solved.

## Public information architecture

- `/` — recent predictions, upcoming races, latest retrospectives.
- `/calendar/2026/08` — month view with upcoming/predicted/settled status.
- `/races` — filter by date, race type, and status.
- `/race/vuelta-a-espana/2026` — stage-race hub and GC tracker.
- `/race/vuelta-a-espana/2026/stage-09` — stage page.
- `/race/milano-sanremo/2027` — one-day page.
- `/retrospectives/2026/08` — monthly review.

Preserve redirects from existing filenames. Initially generate a
machine-readable `site-index.json` beside the pages so recent/calendar views do
not parse HTML. D1 becomes the index after the publication pipeline exists.

## Scheduled workflow

A single midnight cron is insufficient for a global calendar. Run a lightweight
scheduler every few hours and create one idempotent workflow per due race and
phase. A normal cutoff is the evening before the race in race-local time, with
an optional morning refresh when odds, withdrawals, or news materially change.

### Prospective phase

1. Discover races inside the configured horizon without a completed run for
   the current input fingerprint.
2. Require a validated active start list, approved model release, race/stage
   identity, and route/profile input. Record missing optional evidence.
3. Freeze the exact evidence bundle in R2 and hash its manifest.
4. One-day races use the existing one-day machinery. Stage races invoke the
   day-key agent.
5. Send a signed job containing the model release, input manifest, scenarios,
   day-key record, and output destination to the Python executor.
6. Validate schema compatibility, active-field coverage, published-value NaNs,
   LambdaRank book sum, required scenarios, and page-build success. Preserve
   warnings about unconstrained probability books until that work is complete.
7. Generate page prose from structured evidence and predictions. The editorial
   agent cannot alter numeric predictions or silently change the key.
8. Upload and validate the complete bundle, then atomically change one release
   pointer. Never update a live page piecemeal.

### Retrospective phase

1. Poll for a validated result after the expected finish and back off instead
   of repeatedly hammering a blocked source.
2. Freeze the result and classification artifacts.
3. Settle each prospective scenario deterministically.
4. For stage races, update the state cache, score the prospective key, rerun the
   GC view, and rebuild the hub.
5. Generate a retrospective draft from immutable predictions and results.
6. Validate and atomically republish the complete race/stage bundle.

### Monthly phase

Generate a deterministic metrics artifact covering model/market metrics,
calibration, day-key scoring, retrieval contribution, miss taxonomy, data
freshness, manual interventions, and failed runs. The monthly LLM narrative is
derived from that artifact and links to its underlying races.

## Stage-race day-key agent

Day-key evaluation is prospective only. No historical key is reconstructed
after seeing the result.

### Inputs frozen before cutoff

- Current odds, movement, and market shape.
- Route metadata, elevation profile, terrain map/images, distance, finish
  geometry, and weather where available.
- Active start list, withdrawals, live GC state, team incentives, and remaining
  route context.
- Timestamped news and team/rider statements from permitted sources.
- Later: timestamped podcast excerpts with source attribution.
- Frozen day-menu definitions and examples, without future results.

### Required output

- Weighted key distribution summing to one.
- Primary mechanism and credible alternative.
- Evidence references for material claims.
- Missing-evidence and conflict flags.
- Confidence and `human_review_required` decision.
- Provider/model, prompt version, tool versions, timestamp, and input-manifest
  identity.

Initially the agent recommends a key for human approval. Autopublishing is
earned only after prospective evidence shows acceptable key and retrieval
performance. Human overrides create new signed records; they never erase the
agent's original opinion.

## Podcast and YouTube research track

Podcasts are a later evidence source, not an initial dependency.

1. Discover approved episodes and store metadata through permitted APIs.
2. Prefer creator-provided captions. Process audio only when access and usage
   rights permit it.
3. Store permitted transcripts/excerpts in R2 with timestamps and a source hash.
4. Extract race-, stage-, rider-, and tactic-specific claims with speaker and
   time attribution.
5. Deduplicate claims and distinguish reporting from speculation.
6. Give the key agent compact evidence records, not entire untrusted
   transcripts. Podcast text is evidence, never instructions.

Workers AI offers speech-to-text models, but provider choice follows testing of
quality, language coverage, rights, and cost.

## Prediction executor

### Phase A: external executor (recommended first)

Keep the current Python environment on a controlled machine, small VM, or CI
runner. It pulls signed jobs, downloads immutable inputs/model manifests, runs
`PredictionService` and the page builders, and uploads a result bundle.
Cloudflare Queues supports pull consumers outside Workers; an authenticated
Worker polling endpoint is another option.

This is the shortest path with the least model risk. The tradeoff is one
non-Cloudflare compute dependency.

### Phase B: Cloudflare Container

Package the executor and a slim inference database as a container. R2/D1 remain
the system of record; container disk is working space. Trigger it from a
Workflow and compare output against the external executor before cutover.

Do not port LightGBM to JavaScript/Wasm merely to claim an all-Worker runtime.
That would create a new model-parity program without improving the product.
Weekly model training remains separately approved; nightly jobs consume an
immutable model release and do not retrain.

## Minimal control-plane schema

- `races`: identity, slug, type, dates, timezone, source identifiers.
- `stages`: stage number/status, start time, prediction/result deadlines.
- `source_artifacts`: type, URI, capture time, hash, parser, validation state.
- `model_releases`: release ID, contract hashes, approval/publication time.
- `workflow_runs`: phase, state, attempt, idempotency key, timestamps, error.
- `day_key_decisions`: distribution, evidence manifest, agent/human identity.
- `prediction_runs`: model/input/key identities and output bundle URI.
- `publications`: public route, bundle hash, current/previous release.
- `operator_tasks`: missing data, unmatched riders, approvals.

Large payloads belong in R2; D1 contains identities, state, and pointers.

## Failure and publication policy

- No start list: block prospective run and request intervention.
- Too many unmatched riders: block; permit an audited operator mapping.
- No odds: mark degraded and normally require human review for stage races.
- Missing news/terrain: record absence; never fabricate.
- Agent failure: retry, then request a human key.
- Model failure: retain the previous public page and expose delayed status.
- No result: defer settlement and create a task after a deadline.
- Partial build failure: publish nothing.
- Duplicate delivery: return the completed result for the idempotency key.

## Security and observability

- Protect operator routes with Cloudflare Access or equivalent authentication.
- Use narrowly scoped service tokens and signed executor callbacks.
- Never put scraper, odds, or model-provider credentials in public bundles.
- Record every workflow transition and immutable input/output manifest.
- Alert on missed deadlines, `waiting_for_input`, dead letters, validation
  failures, and stale calendars.
- Set AI Gateway retention deliberately for news or paid-source content.
- Export D1 control-plane snapshots to R2 for retention beyond Time Travel.

## Delivery phases

### 1. Public static Worker

Deploy the existing site with Workers Static Assets. Add stable routes,
redirects, recent-race index, and calendar. Gate: Tour/Vuelta pages render
identically and preview, custom-domain, cache, and rollback behavior work.

### 2. Control plane and manual publishing

Add D1, R2 layout, run ledger, operator inbox, and atomic bundles. Exercise one
one-day race and one stage with manually supplied inputs. Gate: reruns are
idempotent and partial releases cannot become public.

### 3. Scheduled workflows

Add scheduler, Workflows, retries, external executor, settlement, GC refresh,
and notifications. Keep keys human-supplied. Gate: several shadow races run
without manual commands while retaining manual data uploads.

### 4. Day-key recommendation agent

Add frozen odds/terrain/news bundles and structured agent output. Run agent and
human decisions side by side prospectively. Gate: sufficient sample, acceptable
evidence failures, working overrides, and measured retrieval value.

### 5. Native executor and richer evidence

Evaluate Containers and add permitted podcast ingestion plus monthly reviews.
Gate: executor parity, bounded cost, reliable cold starts, audit, and rollback.

## First implementation slice

1. Generate `site-index.json` from the Tour/Vuelta campaign directories.
2. Add a minimal Worker using `netlify_site/` as static assets.
3. Build recent-race and calendar views from the index.
4. Add preview/production deployment and rollback documentation.
5. Define R2 bundle layout and executor request/result contracts.
6. Prototype authenticated manual start-list/result upload.

This produces a navigable public site without waiting for perfect scraping or
agent design.

## Decisions needed

- Cloudflare account/project and custom domain.
- First executor: local machine, VM, or CI runner.
- Workers Paid plan timing, especially for Containers.
- Initial calendar and start-list/result source policy.
- Key publication policy: recommendation-only or human approval required.
- LLM provider and AI Gateway retention policy.
- Retention policy for raw news, odds, and later transcripts.

## Cloudflare references

- https://developers.cloudflare.com/workers/static-assets/
- https://developers.cloudflare.com/workers/configuration/cron-triggers/
- https://developers.cloudflare.com/workflows/
- https://developers.cloudflare.com/workflows/reference/limits/
- https://developers.cloudflare.com/d1/platform/limits/
- https://developers.cloudflare.com/r2/pricing/
- https://developers.cloudflare.com/queues/reference/delivery-guarantees/
- https://developers.cloudflare.com/browser-run/limits/
- https://developers.cloudflare.com/containers/
- https://developers.cloudflare.com/containers/platform/limits/
- https://developers.cloudflare.com/ai-gateway/usage/rest-api/
- https://developers.cloudflare.com/workers-ai/
