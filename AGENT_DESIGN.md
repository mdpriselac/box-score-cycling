# Agent architecture — autonomous nightly race coverage

**Status:** design proposal, 2026-08-31. Companion to `CLOUDFLARE_DEPLOYMENT_PLAN.md`
(the operational envelope) and `performance_eval/DAILY_RUNBOOK.md`
(the canonical daily process this design automates, merged from the two
campaign runbooks 2026-09-08; its lessons ledger is
`performance_eval/LESSONS.md`). Day-key vocabulary:
`day_menu_v1_reference.md`.

---

## 1. Recommendation at a glance

**Three agents, one deterministic driver, and a hard line between them.**

| Component | Kind | Job | Judgment? |
|---|---|---|---|
| **Nightly driver** | Deterministic Python + launchd (NOT an LLM) | Decide what's due, run every runbook step that is a script today, assemble frozen evidence bundles, invoke agents, write the run ledger, escalate | No |
| **Day-key agent** | Single structured LLM call over a frozen bundle (no tools in v1) | The morning stage read: odds shape + roadbook + GC incentives + settled-stage ledger → weighted key distribution + reasoning record | **Yes — the judgment core** |
| **Editorial agent** | Single structured LLM call per artifact (no tools) | Stage-preview prose, retro prose, monthly narrative — prose only, numbers structurally immutable | Yes (language, not numbers) |
| **Ops-triage agent** | Exception-only Claude Agent SDK session, read-only tools | When a deterministic step fails: diagnose (parser drift, source block, crosswalk ambiguity), draft an operator-inbox item with evidence | Bounded (diagnosis only, never remediation) |

Everything else in the runbook — odds capture, results capture, state-cache
seeding, GC refresh, `score_day_keys.py`, page builds, publication — stays a
deterministic script orchestrated by the driver. **The settlement/scoring
"agent" and the acquisition "agent" from the candidate list do not exist as
agents**: those phases contain no judgment, and wrapping them in an LLM adds
failure modes without adding value. Their exceptions route to ops-triage; their
approvals route to the human.

Where the line was drawn and why: an LLM enters the loop only where the output
is a *defended judgment* (a key, a paragraph) or a *diagnosis of the
unexpected*. Anywhere the correct output is computable from inputs, the LLM is
a reliability tax. Fewer agents with sharp contracts also keeps the provenance
story simple: exactly three kinds of decision record exist, each with one
schema and one prompt lineage.

---

## 2. Design principles (inherited, restated as constraints)

1. **Frozen evidence in, structured record out.** No agent fetches anything at
   decision time. The driver freezes a manifest-hashed bundle first; the agent
   sees only that. This is what makes decisions reproducible, auditable, and
   honest about what was knowable prospectively (no hindsight leakage).
2. **Numbers are never LLM-touched.** Predictions come from the production
   heads via `predict_stage_scenarios.py`; the day key can only re-rank the
   pool (gate 6: wrong key costs pool composition, never prices); editorial
   output is prose slotted into templates around numbers the builder injects.
3. **Human-approval-first, promotion earned per agent on a measured scorecard.**
   Overrides are new signed records; the agent's original opinion is never
   erased.
4. **Never invent evidence; never publish partial pages.** Missing input →
   `waiting_for_input` + operator task + last valid page stays up.
5. **Not a gambling product.** Book odds are the information-capture yardstick.
   No agent-written prose may read as betting advice — enforced by a lexicon
   linter (§6.2), not just by prompt.
6. **The Mac is the executor and agent host.** Cloudflare (later) is control
   plane + publishing surface. Nothing in this design requires Cloudflare to
   exist yet; the driver's run ledger and bundle layout are designed so they
   can later sync to D1/R2 unchanged.

---

## 3. Agent inventory and boundaries

### 3.1 Nightly driver (deterministic — the non-agent that runs the show)

**What it is:** a Python program under launchd on the Mac, run at two anchors
per active race day (race-local morning, race-local evening) plus a
lightweight every-few-hours scheduler tick for the general calendar. It is the
only component with write access to campaign directories, the publication
area, and the run ledger.

**Morning phase (per due stage):** capture odds (`capture_odds.py`) → verify
startlist freshness/withdrawals → assemble + hash the day-key evidence bundle
→ invoke the day-key agent → land the decision record in the operator inbox
(or, post-promotion, into `scenarios.json` directly) → after key approval, run
`predict_stage_scenarios.py` → validate outputs (schema, NaNs, LambdaRank book
sum, required scenarios) → invoke editorial agent for preview prose → validate
prose → build stage page → publish atomically (or queue for approval,
per-phase policy in §7).

**Evening phase:** `capture_results.py --all` → `seed_state_cache.py` → GC
board refresh + `build_gc_tracker.py` → `score_day_keys.py` (always, even
unkeyed stages — the oracle labels build the settled corpus) → assemble retro
facts → invoke editorial agent for retro prose → settle + republish the stage
bundle atomically.

**Why deterministic and not an "orchestrator agent":** the runbook's control
flow is a checklist with a known order and known failure modes. A determinist
driver is restartable (idempotency keys per race/stage/phase, exactly as the
Cloudflare plan's workflow-run schema anticipates), auditable, and free. The
places where the runbook currently requires judgment mid-flow (update the GC
scenario label, cancelled-stage protocol, "is this source blocked or just
slow") are handled by: config (labels templated from stage metadata), operator
task (void-stage protocol is a human decision — it changes every later
config), and ops-triage (diagnosis).

**Tool access:** full local access — it's trusted code, not a model.

### 3.2 Day-key agent — the judgment core

**Job:** the MORNING step-2 stage read, exactly as the runbook defines it:
route the macros mechanically, then family first, then grade within family,
weighting 2–3 items when torn. Output is a decision record (§5.1), not prose.

**Form: a single structured LLM call, extended thinking on, NO tools in v1.**
This is the strongest version of the frozen-bundle discipline: if the agent
can't fetch, it can't leak hindsight, can't act on injected instructions in
scraped content, and every input it saw is in one hashed manifest. The cost is
that the bundle builder (driver code) must anticipate what the read needs —
acceptable, because the runbook already tells us what a good read consumes,
and the campaign archive is small and local. In v2, if bundle-anticipation
proves limiting, add exactly one tool: a read-only `comparable_stages` query
(same-race settled stages + historical menu exemplars from the DB), still no
web access.

**Bundle contents (frozen, manifest-hashed — §5.1 for schema):**

- Kambi odds snapshot(s) for the stage + movement vs prior snapshot; devigged
  implied probabilities; the market's "break cards" (long-odds riders drawing
  money).
- Route/roadbook evidence: stage profile data as structured facts (climb
  lengths/gradients/positions, total elevation, finish geometry, distance) —
  operator-supplied or extracted upstream, never fetched by the agent.
- Race state: current GC with gaps, active startlist + withdrawals, points/KOM
  context where captured, `void_stages`.
- **Settled-stage ledger for the same race**: for every prior stage — the key
  as logged, the oracle item, winner-group size and % of field, winner +
  front group, and the measured outcome facts the runbook's stage-8 argument
  used (e.g. "Roquetes produced an 89-rider bunch, 48.9%"). This is what makes
  the gold-standard argument possible.
- Frozen day-menu reference (`day_menu_v1_reference.md`) + serve guidance.
- Timestamped news/team-statement snippets from permitted sources, when the
  acquisition layer captures them (later phase; absence recorded, never
  fabricated).
- The running key scorecard (its own track record — for calibration of
  `confidence`, not for streak-based priors; see below).

**The distilled judgment heuristics belong in the agent's skill file**, not
rediscovered per call. From the runbook's Open items, the skill must encode at
minimum:

1. **The chase-incentive test replaces macro-frequency priors.** Before
   keying, name who specifically has a reason to spend to control the stage.
   If the answer is nobody — leader comfortable, podium men marking each
   other — price `res_2` up. A streak of macro results is not a prior (the
   stage-7 failure: gc_day .6 keyed off a four-macro streak; the break won by
   nineteen minutes). A summit finish is a reason a chase would *work*, not a
   reason anyone *wants* one.
2. **The gold-standard argument is a same-race parcours comparison against a
   measured outcome.** "Barx is 4.7 km at 5.6% vs Pauls at 3.9 km at 6.6% —
   longer but shallower, half the elevation of the Roquetes day, flat run-in;
   Roquetes produced an 89-rider bunch, so bunch-majority is forced." Prefer
   this over any frequency or vibes argument. The ledger in the bundle exists
   to make it.
3. **Family with confidence, grade with humility.** Neighbors flip
   (res_2/res_4 at cos 0.97, res_3/res_7 borders); families never have. When
   torn on grade, weight two neighbors — a one-grade miss is cheap
   (kernel overlap ≈ 0.8). Never `res_5`; avoid `res_0` — weight the two
   family candidates instead.
4. **Course-knowledge humility.** Six consecutive post-hoc reconstruction
   attempts failed to beat the morning read; "better course knowledge would
   have found it" is falsified. Don't overweight terrain micro-detail against
   incentive structure.
5. **Where the channel earns its keep** (context for confidence and
   `human_review_required`): worth ~nothing when the front is the obvious
   strong group; worth a lot when it is not (stage 7: +3 retrieval on the
   model's worst absolute day, from `mountain_break` keyed res_2 .85).

**What it never does:** touch prices or scenarios beyond the `day_key` field;
see results for the stage being keyed (structurally impossible — they don't
exist); fetch anything; emit a key without an evidence-referenced mechanism.

### 3.3 Editorial agent

**Job:** three artifact types — stage-preview prose, retro prose, monthly
review narrative. Input: a frozen facts bundle (predictions as structured
data, the approved day-key decision record, settled results + scorecard for
retros, the deterministic monthly metrics artifact for reviews). Output:
prose-only structured record (§5.2).

**Form: single structured LLM call, no tools.** Same reasoning as the day-key
agent, stronger even: editorial has zero legitimate need to look anything up.
Everything it may say must be derivable from the facts bundle.

**Numbers-immutable, enforced structurally, not by prompt:**

- The agent's output schema has no free-form page; it emits named prose
  sections that the page builder slots into templates. Numbers on the page are
  injected by the builder from prediction/result JSONs.
- Prose that must cite a number uses a placeholder token
  (`{{p:rider_id:win}}`, `{{gc_gap:rider_id}}`, `{{key_weight:res_2}}`)
  resolved by the builder. A post-render validator rejects any bare numeral in
  prose that doesn't match a whitelisted fact (dates, stage numbers, climb
  stats from the bundle are whitelisted).
- The key is quoted, never restated: the builder prints the key from the
  signed decision record. The editorial agent cannot "silently change the
  key" because it never writes it.

**Framing guardrails (user directive 2026-08-31):** the skill instructs and a
deterministic lexicon linter enforces — no stake/ROI/value-pick/"play"/"punt"/
"smart money"/units language; model-vs-market is presented as *where the model
captured information the market missed, and vice versa*; devigged implied
probabilities may be discussed as probabilities. Linter failure = draft
rejected back to the agent once, then to the operator. The linter list lives
in the repo beside the skill and is versioned like a prompt.

### 3.4 Ops-triage agent

**Job:** exception handler of last resort before the human. Invoked by the
driver only when a deterministic step fails in a non-obvious way: parser
returns empty/malformed (markup drift — the 2026-08 `div#raceSub` class of
failure), capture blocked (Cloudflare/403/503 taxonomies), crosswalk
low-confidence matches, odds event-id discovery for a new race, validation
failures with unclear cause.

**Form: Claude Agent SDK session with read-only tools** (Read, Grep, Glob,
read-only Bash allowlist, read-only DB access). This one genuinely benefits
from the harness: diagnosis means exploring captured HTML, logs, and the DB.

**Output:** an operator-inbox item (§5.3): diagnosis, evidence excerpts,
proposed remediation, urgency. **It never remediates**: no file writes outside
its report, no code patches, no retries with modified parameters, no
"helpful" manual data entry. Wrong matches are worse than missing ones — this
is the component where that rule bites, so it proposes crosswalk matches with
evidence but confirmation is permanently human.

**On acquisition generally:** nightly PCS capture (startlists, withdrawals,
results, GC) and Kambi odds capture are deterministic scripts using the
existing Playwright headed-Chrome client — rate-limited honest-browser
posture, same as FirstCycling. The one agent-shaped task in acquisition is
matching (riders, odds event ids), and that is proposal-only via ops-triage.

---

## 4. The nightly timeline (who does what)

```
MORNING (race-local, before stage N)
  driver: capture odds ──────────────── deterministic, retries + backoff
  driver: freshness checks ──────────── startlist age, withdrawals delta,
                                        state-cache seeded through N-1
  driver: assemble + hash bundle ────── §5.1 inputs
  AGENT:  day-key read ──────────────── decision record, signed
  human:  approve / edit key ────────── (until promotion; edit = override record)
  driver: predict_stage_scenarios.py ── production prices, kernod pool
  driver: validate outputs
  AGENT:  editorial preview prose
  driver: lint + render + validate
  human:  approve publish ───────────── (until editorial promotion)
  driver: atomic publish

EVENING (after stage N)
  driver: capture_results.py --all ──── mandatory --all
  driver: seed_state_cache.py
  driver: GC refresh + build_gc_tracker.py
  driver: score_day_keys.py ─────────── always, even unkeyed stages
  driver: assemble retro facts ──────── key vs oracle, pool with/without key,
                                        break-card ledger entry, abandons
  AGENT:  editorial retro prose
  driver: lint + render + validate
  human:  approve settle ────────────── (until editorial promotion)
  driver: atomic republish of stage bundle + hub

ANY FAILURE at any step
  driver: classify → known-transient? retry with backoff
          else → AGENT: ops-triage → operator inbox + notification
          public pages untouched throughout
```

One-day races skip the day-key agent entirely (existing one-day machinery
keys off history); their morning phase is capture → predict → validate →
editorial → publish.

---

## 5. Evidence contracts

All records share a provenance block — this satisfies the plan's requirement
that prompt-version provenance ride in every decision record:

```json
"provenance": {
  "agent": "day_key",
  "model": "claude-<pinned-id>",
  "skill": {"name": "day-key-read", "version": "1.3.0", "git_sha": "<sha of skill file>"},
  "bundle_manifest_sha256": "…",
  "generated_at": "2026-09-01T06:40:00+02:00",
  "harness": "agent-sdk@<version>",
  "transcript_uri": "runs/vuelta-2026/stage_10/day_key/transcript.json"
}
```

### 5.1 Day-key decision record (extends the plan's spec)

Input bundle manifest (each entry: path/URI, sha256, captured_at, source):
odds snapshots, route facts, startlist+withdrawals, GC state, settled-stage
ledger, menu reference, scorecard, news snippets (optional).

Output:

```json
{
  "race": "vuelta-a-espana-2026", "stage": 10, "stage_date": "2026-09-01",
  "key": {"res_2": 0.6, "res_4": 0.4},
  "family": "escape",
  "macro_routing": {"itt": false, "bunch_considered": false, "gc_day_considered": true,
                    "gc_day_rejected_because": "…"},
  "primary_mechanism": "one paragraph: how the stage is won under the argmax item",
  "credible_alternative": "one paragraph: the next-most-likely mechanism and what would make it true",
  "chase_incentive": {
    "who_has_reason_to_spend": [{"team": "…", "why": "…"}],
    "verdict": "nobody_pays | contested | controlled",
    "consequence_for_key": "…"
  },
  "comparables_used": [
    {"stage": 8, "argument": "same-race parcours comparison text", "measured_outcome": "…"}
  ],
  "evidence": [
    {"claim": "…", "ref": "odds/2026-09-01/markets_0830.json", "sha256": "…"}
  ],
  "missing_evidence": ["no weather capture", "no news snippets"],
  "conflicts": ["odds imply bunch; roadbook implies selection — resolved toward … because …"],
  "confidence": 0.62,
  "human_review_required": true,
  "review_reason": "missing odds | low confidence | family torn | novel situation"
}
```

Rules: weights sum to 1 (validator-enforced, ±0.001); every material claim in
`primary_mechanism` must be traceable to an `evidence` ref or flagged as
inference; `human_review_required` is forced true by the driver (regardless of
the agent's own setting) when odds are missing, when confidence < threshold,
or during the shadow/approval phases. Human approval or edit produces a
separate signed override record pointing at the agent record; the agent record
is immutable.

### 5.2 Editorial output record

```json
{
  "artifact": "stage_preview | stage_retro | monthly_review",
  "race": "…", "stage": 10,
  "sections": {
    "headline": "…",
    "stage_read": "prose with {{placeholders}} for numeric citations",
    "model_vs_market": "…",
    "key_rationale_summary": "restates the decision record's mechanism, cites it",
    "retro_key_vs_oracle": "(retro only)",
    "retro_pool_panel": "(retro only)"
  },
  "claims": [
    {"text": "…", "basis": "prediction_json#rider_123.win_p | decision_record#chase_incentive | results/stage_10/gc.csv"}
  ],
  "placeholders_used": ["p:123:win", "key_weight:res_2"],
  "flags": {"tone_check": "information-capture framing", "no_advice_language": true}
}
```

Validators (deterministic, driver-side): every placeholder resolves; no bare
numerals outside the whitelist; lexicon lint passes; every claim has a basis
that exists in the bundle; section set matches the template for the artifact
type. The monthly review's input is the plan's deterministic metrics artifact
— the narrative may only reference races/metrics present in it.

### 5.3 Ops-triage report

```json
{
  "trigger": {"step": "capture_results", "race": "…", "stage": 12, "error_class": "empty_parse"},
  "diagnosis": "…",
  "evidence": [{"excerpt": "…", "source": "results/raw/page.html", "lines": "…"}],
  "proposed_action": {"kind": "operator_fix | rerun_after | code_change_needed | data_upload",
                       "detail": "…"},
  "crosswalk_proposals": [
    {"pcs_rider": "…", "internal_id": 4512, "confidence": 0.71, "evidence": "name+team+birthyear partial"}
  ],
  "urgency": "blocks_tonight | blocks_settlement | routine",
  "confidence": 0.8
}
```

### 5.4 Settlement record (deterministic — for completeness)

`score_day_keys.py` already defines it: per-stage oracle item, exact /
covered / weight_on_true, appended to `review/key_scorecard.json`. Extended
with: which record was scored (agent's, human's, or the approved override —
in shadow, **both** the agent's and the human's key are scored per stage),
plus the retrieval ledger entry (pool15 with/without key vs production
board). Evening labels remain provisional as documented; canonical re-scoring
after the race from the rebuilt signature table is a driver task.

---

## 6. Human-in-the-loop map and promotion gates

### 6.1 The map

| Decision | Initially | Promotion gate | End state |
|---|---|---|---|
| Day key | Human keys; agent recommendation logged + scored in shadow | Gate K (below) | Agent keys by default, human veto window; full no-veto autopublish is a second, later gate |
| Stage preview publish | Human approves each | Gate E | Auto-publish on green validators |
| Retro settle/publish | Human approves each | Gate E | Auto-publish on green validators |
| Monthly review | Human approves | — | **Permanently human-approved** (public synthesis, low frequency, high blast radius) |
| Weekly pipeline + model retrain/release | Human runs/approves | — | **Permanently human** (plan: nightly consumes an immutable model release, never retrains) |
| Crosswalk confirmations below auto-threshold | Human confirms from inbox | — | **Permanently human** (wrong > missing) |
| Void/cancelled-stage protocol | Human invokes | — | **Permanently human** (changes every later config) |
| Menu version changes (v1→v1.1…) | Human | — | **Permanently human** |
| Ops-triage proposed remediations | Human executes | — | **Permanently human** (agent diagnoses only) |

### 6.2 Gate K — day-key promotion (shadow → default-with-veto)

Measured on `review/key_scorecard.json` with both keys scored per stage.
Population: **judgment stages only** — residual-family and contested-macro
days; pure-mechanical `itt` stages are excluded from the comparison (both
always score exact).

Promote when, over **≥ 30 scored judgment stages spanning ≥ 3 races** (at
least one GT):

1. **Covered:** agent covered-rate ≥ human covered-rate on the same stages
   (paired comparison, not separate samples).
2. **Weight on true:** agent mean weight_on_true ≥ human mean − 0.03.
3. **No family regressions:** zero stages where the human's key covered the
   oracle's family and the agent's missed the family entirely.
4. **Retrieval neutrality:** the retrieval ledger under agent keys is
   net ≥ 0 vs the production board over the sample (the channel must not
   destroy pool value under agent stewardship; human's current ledger is
   roughly break-even with one big up day).
5. **Process health:** ≥ 95% of runs produced schema-valid records without
   retry; `human_review_required` self-flagging caught every stage the human
   materially disagreed with (no confident-and-wrong-and-unflagged cases —
   this is the calibration criterion that matters most for removing the
   human).

Reference point: the human's current scorecard is ~2/6 exact, 5/6 covered,
mean weight 0.45. The bar is "at least as good as the human, with calibrated
self-doubt," not an absolute number — the gate is paired by design.

The second gate (default-with-veto → no-veto autopublish) reuses the same
criteria over a further ≥ 30 stages *in the default-with-veto regime*, adding:
veto rate < 10% and no vetoed key that scored worse than the veto.

### 6.3 Gate E — editorial promotion

Per artifact type (preview and retro gate separately): **20 consecutive
drafts** where validators passed first-try and human edits were nil or
typo-level (no substantive rewrite, no factual correction, no tone
correction). One tone/factual correction resets the counter. The lexicon
linter runs forever regardless of promotion.

---

## 7. Failure policy per component

Mapping the plan's failure table onto this architecture — in every row, the
public site keeps the last valid page; nothing partial is ever published.

| Condition | Driver | Day-key agent | Editorial | Ops-triage |
|---|---|---|---|---|
| No startlist / stale startlist | Block morning phase, `waiting_for_input`, operator task | Not invoked | Not invoked | Invoked if capture failed non-obviously |
| No odds | Proceed **degraded**: bundle marks odds missing | May run; driver forces `human_review_required=true`; must list in `missing_evidence`, never estimate odds | Preview omits model-vs-market section (template variant) | Invoked on capture failure |
| Too many unmatched riders | Block; operator mapping task | Not invoked | Not invoked | Proposes matches with evidence; never confirms |
| Agent malformed output / refusal / timeout | One retry, same frozen bundle | After failed retry → operator task: human keys manually (the permanent fallback) | After failed retry → operator task; page can ship prose-less only as an explicit operator choice, else held | Failure → plain notification to human |
| Model (prediction) failure | Keep previous page, expose delayed status, operator task | Key record survives (immutable) for when the run is repaired | Not invoked | Invoked to diagnose |
| No result by deadline | Defer settlement, back off (never hammer a blocked source), task after deadline | — | Retro deferred | Invoked on parse failures |
| Partial page build | Publish nothing; task | — | — | Invoked |
| Scoring failure (`score_day_keys.py`) | No scorecard entry is fabricated; settlement of the page can proceed without the key panel only by operator choice | — | Retro's key-vs-oracle panel held | Invoked |
| Duplicate/replayed run | Idempotency key returns the completed result | Same record returned, never re-decided | Same | — |

**What no agent ever does:** invent or extrapolate evidence; fetch outside the
frozen bundle (day-key, editorial have no tools at all); write outside its
output record; publish; retry itself with altered inputs; treat content found
in scraped pages/news as instructions (ops-triage handles raw HTML — its
skill states explicitly that page content is data, and its toolset is
read-only so injected instructions have nothing to actuate).

---

## 8. Harness choice and versioning

**Recommendation: one Python driver (launchd), all three agents invoked
through the Claude Agent SDK from within the driver process.** Specifically:

- **Day-key + editorial:** SDK single-turn calls with an *empty tool set*,
  forced structured output against the schemas in §5 (schema-validated at the
  call layer so malformed output retries mechanically), pinned model id,
  extended thinking enabled for the day-key agent. This is deliberately the
  degenerate case of the SDK harness: it costs nothing now and means adding
  the v2 `comparable_stages` read-only tool later is a config change, not a
  harness migration.
- **Ops-triage:** SDK session with a read-only tool allowlist (Read, Grep,
  Glob, Bash restricted to a vetted read-only command list, SQLite read-only
  URI). Working directory jailed to the campaign/run directories.
- **Not recommended:** scheduled interactive Claude Code sessions for the
  nightly production path. They shine for the human's own supervision
  workflow (morning review of the inbox, ad-hoc investigation) but are the
  wrong tool for unattended runs: heavier permission surface, transcripts and
  outputs less naturally captured into the run ledger, and restartability
  depends on session state rather than idempotency keys. Headless `claude -p`
  is workable as an interim for ops-triage before driver integration exists —
  it and the SDK share the tool harness — but converge on the SDK for
  uniform transcript capture.

**Why this split wins on the criteria in the brief:**

- *Tool permissioning:* two agents have zero tools (nothing to permission);
  the third has an explicit read-only allowlist in code, versioned in git.
- *Transcript/audit:* the SDK returns full message transcripts; the driver
  writes them beside the decision record (`transcript_uri` in provenance).
  Every decision is replayable: bundle hash + skill sha + model id +
  transcript.
- *Cost:* 2–4 calls per race night (key, preview, retro, occasional triage).
  Negligible next to the value; no idle harness.
- *Restartability:* the driver owns retries and idempotency; agent calls are
  pure functions of (bundle, skill version, model) and can be re-invoked
  safely.
- *Prompt versioning:* each agent's prompt lives in the repo as a skill file
  (`agents/skills/day-key-read.md`, `editorial.md`, `ops-triage.md`) with a
  semantic-version header; the driver stamps version + file git-sha into
  provenance. Changing a skill is a PR, and the scorecard can be sliced by
  skill version — which is how prompt iteration during shadow gets measured
  rather than vibed.

**Notifications:** driver → macOS notification + (optionally) the operator
inbox page. Escalations carry the run-ledger entry id, never a bare "it
broke."

---

## 9. Rollout phases

### Phase 0 — Vuelta shadow pilot (now → ~Sep 13, stages 10–21)

No driver yet; the human runs the runbook exactly as today. Add only:

1. A small script that assembles the frozen bundle for the morning's stage
   from the campaign archive (odds snapshot, GC csv, startlist, settled-stage
   ledger built from `results/` + `review/key_scorecard.json`, menu
   reference) and invokes the day-key agent, writing the decision record to
   `predictions/stage_NN/agent_key.json` — **before** the human writes their
   own key, so the human read isn't anchored (or the human keys first and
   doesn't look; either way, log which ordering happened).
2. Extend the evening flow to score both keys (a sidecar to
   `score_day_keys.py` or a `--also` flag; design-only note, not prescribing
   implementation here).

Yield: ~10–12 paired judgment samples plus prompt iteration under real
conditions — not enough for Gate K alone, but enough to debug the bundle
contents, the schema, and the self-flagging behavior before the driver
exists. Editorial can shadow the same way on 2–3 retros, zero risk.

### Phase 1 — the driver (post-Vuelta, off-season races)

Build the nightly driver to run the deterministic runbook end-to-end
(morning capture→predict→build, evening capture→seed→GC→score→settle) with
the human still keying and approving every publish. Gate: several races run
with no manual commands except key entry and approvals; idempotent reruns;
failure table exercised (at least synthetically).

### Phase 2 — agents wired in

Day-key recommendations land in the operator inbox pre-filled into
`scenarios.json` (approve = run; edit = override record). Editorial drafts
attached to every publish approval. Ops-triage handles driver exceptions.
Crosswalk inbox live for PCS. This is the plan's Phase-4 shape, running on
the Mac before any Cloudflare control plane exists.

### Phase 3 — per-agent promotion

Gates K and E as specified in §6, evaluated per agent independently — the
editorial agent will likely promote first (its gate is cheaper and its
failure mode smaller). Day key moves to default-with-veto, then (second
gate) no-veto.

### Phase 4 — general calendar + Cloudflare envelope

Multi-race scheduling from a calendar table, one-day races fully automatic
(no key agent), monthly metrics artifact + review, and — when the Cloudflare
control plane lands — the driver becomes the plan's "external executor":
run ledger syncs to D1, bundles to R2, publication via the atomic pointer.
Nothing in the agent contracts changes; that was the point of writing them
against manifests and immutable records from day one.

---

## 10. Open questions for the user

1. **Roadbook evidence for the general calendar.** For the Vuelta, the human
   reads the roadbook and the stage facts arrive via judgment. For arbitrary
   races, who produces the structured route facts in the bundle — an operator
   task per race week, a PCS-profile capture (permitted?), or accept
   "route facts missing" as a standing degraded mode for minor races?
2. **Gate thresholds.** §6.2's numbers (30 paired stages, −0.03 weight
   tolerance, <10% veto, 20 consecutive editorial drafts) are proposals.
   Comfortable, or do you want the key gate harder (e.g. require the agent to
   *beat* covered-rate, not match it)?
3. **Shadow ordering.** Agent-first-then-human risks anchoring your read;
   human-first-then-agent delays your morning. Which default for the Vuelta
   pilot? (Recommend: agent runs but you key blind, then compare — costs one
   glance of discipline.)
4. **Prose-less publishing.** When editorial fails and a human isn't
   available, may the driver ship a numbers-only stage page (template without
   prose sections), or hold the page entirely? §7 currently makes it an
   explicit operator choice, never automatic.
5. **News capture scope.** The day-key bundle improves with timestamped news
   (withdrawal rumors, team statements), but that adds a permitted-source
   policy question the plan defers. Start entirely news-less (odds + roadbook
   + ledger only) and measure, or prioritize a minimal permitted-source news
   capture early?
6. **Where the veto window sits.** Default-with-veto needs a race-local
   morning deadline ("key locks at 10:00 unless vetoed"). Is a hard
   time-lock acceptable, or should unvetoed keys wait for explicit ack
   indefinitely (which is just approval mode with extra steps)?
