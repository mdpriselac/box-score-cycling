# Daily prediction runbook — any campaign

The daily cycle for a race's prediction pages, written to be handed to
someone who has never done it. It replaces the per-race runbooks: the Tour
and the Vuelta ran the same process, and their two copies drifted. Every
race-specific fact lives in `<campaign>/campaign.json`; the campaign's own
`DAILY_RUNBOOK.md` now carries only those facts and points here.

The dated evidence behind the rules below — what a stage taught, which
tool bit, which source failed — is in [`LESSONS.md`](LESSONS.md). This file
tells you what to do; that one tells you why, and is the place to cite when
writing a day key or a retrospective.

Everything runs from the project root (`Cycling Project/`). One-time
assumptions: `uv sync` has been run, `.env` has `SCRAPER_USE_BROWSER=1`, and
Google Chrome is installed — FirstCycling scrapes open a **visible** Chrome
window, which you leave alone (it lingers ~15 s after the last fetch).

Market odds appear throughout as an **information-capture yardstick**: the
devigged book is the benchmark a read is scored against. Nothing here is
betting advice.

---

## 1. Parameters

Write `<campaign>` for the campaign directory, `performance_eval/<slug>` —
the slug already carries the year (`vuelta-2026`, `tour-de-france-2026`,
`strade-bianche-2026`). Everything the tooling needs comes from
`<campaign>/campaign.json`:

| Field | Used by | Notes |
|---|---|---|
| `fc_race_id`, `year` | results capture, state seeding, one-day reference lookup | FirstCycling race id as a string. |
| `slug`, `name`, `category` | ledger rows, page titles, whether a missing market blocks a preview, **whether the nightly covers the race at all** | `category: "wt"` is the only one that waits on Kambi; `wt` and `pro` are the tiers the unattended nightly runs (§1a). |
| `automation` (optional) | the nightly's scope gate | `"on"` covers a `.1` race, `"off"` takes a WT/.Pro race out; absent = the category decides. |
| `is_stage_race` | which variant of this runbook applies | `false` → §6, the one-day path. |
| `start_date`, `end_date`, `stages[]` | the driver's due-work planner | one `{number, date}` per stage. |
| `void_stages` | every config, the GC tracker, the key scorer | cancelled stages; `[]` for a clean race. |
| `kambi_match`, `kambi_localised_name`, `kambi_event_ids` | odds capture | the capture writes discovered event ids back into this file. |
| `uci_competition_url` | UCI acquisition | set by `nightly registry sync` / `uci_calendar resolve`, **never** by guessing. |
| `timezone` | "is tomorrow's stage due?" | race-local, not UTC. |
| `site.prefix`, `site.marker`, `site.route_slug` | page and hub names | the Tour's prefix is empty, the Vuelta's is `vuelta-`. |

### 1a. Which races the nightly covers (owner decision, 2026-09-22)

The unattended nightly runs **WorldTour and .Pro** races. A `.1` race
(`category: "d1"`) is registered, bundled and run **by hand on this Mac** —
`nightly plan` and `nightly night` find nothing due for it and say so
(`"skipped": "not_automated: category d1"`). The reason is the first
unattended week: of eleven troublesome races, eight were `.1`, and every one
of those failed on the outside world — no start list published, no earlier
edition in the database, no UCI calendar row, riders nobody can identify.

What this means when you are at the keyboard:

```bash
# a .1 race, run by hand — an explicit unit always runs
uv run python -m cycling_project.nightly settle  --campaign giro-della-toscana-2026 --unit race
uv run python -m cycling_project.nightly preview --campaign giro-della-toscana-2026 --unit race

# plan / night / horizon for one: widen the tiers for this invocation
uv run python -m cycling_project.nightly night --campaign okolo-slovenska-2026 --all-tiers
uv run python -m cycling_project.nightly.horizon --campaign okolo-slovenska-2026 --all-tiers
```

`--campaign` narrows a sweep; it does **not** widen the coverage — one rule
(`cycling_project/nightly/tiers.py`), one place. To cover a `.1` race every
night, add `"automation": "on"` to its `campaign.json` (and `"off"` takes a
WT/.Pro race out); the flag then travels to the hosted `campaigns` row and
the release, and no other file changes.

Directory layout, identical for every campaign:

```
<campaign>/
  campaign.json                       race identity (above)
  odds/YYYY-MM-DD/                    Kambi snapshots: raw/, markets_HHMM.json,
                                      provenance_HHMM.json, win_odds_HHMM.csv
  results/stage_NN/                   settled archive: results.{csv,json}, gc.csv,
                                      classifications.json, uci/ or pcs/ raw capture
  predictions/stage_NN/scenarios.json stage config: scenarios, day key, analysis, reflection
  predictions/stage_NN/<key>.json     one board per scenario (runner output)
  predictions/stage_NN/bundle/        frozen morning bundle for the day-key agent
  predictions/stage_NN/agent_key.json the agent's decision record (shadow)
  predictions/gc/scenarios.json       GC config (`target: "gc"`)
  review/key_scorecard.json           rolling tier-3 key accuracy
  runs/YYYY-MM-DD/<phase>.json        driver run mirror
netlify_site/
  <prefix>stageNN.html, <prefix>gc.html, stages.html, index.html, site-index.json, _frame/
  build/predict_stage_scenarios.py    model runner
  build/build_stage_analysis.py       break-pool / book-card analyses
  build/build_stage_page.py           stage page (also rebuilds hub + index)
  build/build_gc_tracker.py           stage-by-stage GC tracker
  build/build_oneday_page.py          one-day race page
  build/build_site_index.py, build_site_frame.py   calendar / races views + routing
```

Shared tooling lives in two campaign directories and is pointed at any race
by flag — there is one copy of each, not one per race:
`performance_eval/tour-de-france-2026/{capture_odds,capture_results,seed_state_cache}.py`
and `performance_eval/vuelta-2026/score_day_keys.py`.

---

## 2. Two ways to run the same steps

Every step below is shown twice.

- **Manual** — what a human runs on the Mac. This is the supervised path,
  the one that can reach FirstCycling, and the one to use when anything is
  unusual.
- **Driver** — `uv run python -m cycling_project.nightly <command>`, the
  same steps as code (`cycling_project/nightly/driver.py`). JSON on stdout,
  logs on stderr; idempotent on `(campaign, unit, phase)`; every run and
  step becomes a row in `runs` / `run_steps` and a file under
  `<campaign>/runs/<date>/`. Exit **0** done · **10** waiting for input (a
  judgment call is missing; the payload carries an `operator_task`) · **20**
  failed (`error_class`, `step`, `log_path`).

A "unit" is `stage_NN` for a stage race and `race` for a one-day. A "phase"
is `settle` or `preview`.

Flags worth knowing on every driver command: `--dry-run` (no fetch, no
logging, a fake store, scripts recorded not run), `--store fake` (keep the
hosted ledger clean — **mandatory for tests and experiments**, see the
gotcha in CLAUDE.md), `--today YYYY-MM-DD` (race-local date override for
replay), `--local-now <ISO datetime>` (race-local wall clock; `--today` alone
reads as that date's evening, after racing), `--allow-scrape` (let the runner
fetch a missing start list — attended Mac runs only), `--force` (re-run a phase
already marked complete), `--no-log`.

`nightly plan --campaign <campaign>` lists what is due; `nightly night
--campaign <campaign>` runs every due settle, then every due preview.
There is no `publish` command and no git operation anywhere in the driver.

**Due-ness is a race-local clock, not a date** (2026-09-17). A stage settles
only once its own race-local day is over — a past local date, or the local date
past 18:00 local — and stays previewable while that day has not begun (before
09:00 local). The tick is a fixed 19:45 UTC, so for a race far east of UTC it
lands in the small hours of the *next* local day: Tour of Huangshan stage 1,
dated 2026-09-18 in Asia/Shanghai, was listed as settle-due at 03:45 local and
an acquisition task was filed for a stage nobody had ridden. Under the clock
rule that same tick previews it instead, which is what it is: a morning read.

---

## 3. Before you start

### 3.1 Invariants

These are the errors-in-waiting. Each one has cost a day at least once;
`LESSONS.md` has the dated case.

1. **`--all` is mandatory on the daily results capture.** Without it the
   capture stops at the first stage with no results and silently skips the
   rest.
2. **Seed the state cache BEFORE the GC run.** The GC outlook head reads the
   state the seeding just wrote. Edit the GC scenario's `label`/`short`/`note`
   to the new stage first, too — it is a one-line edit that cannot be made
   after the run.
3. **`state_through_stage` in `prediction_log` is a COUNT of the stages that
   fed the state, not a stage number.** With any entry in `void_stages` the
   two diverge for the rest of the race. Reading it as a stage number shows
   the wrong podium.
4. **Any config written after its stage started MUST carry `post_hoc: true`.**
   Otherwise the key scorer promotes a hindsight key into the tier-3 archive
   and scores it as a genuine exact.
5. **Every config on the campaign must carry the campaign's `void_stages`.**
6. **Cancelled stage protocol:** mark the stage config `"cancelled": true`
   with a reflection, add the number to `void_stages` in `campaign.json` and
   in every later config, capture with `--all`, rebuild the pages.
7. **`blend_win_p` is not a distribution.** It is a set of per-rider
   marginals summing to 136–180 %, while the devigged book sums to 100 %.
   Putting the raw blend beside the book systematically flatters the model,
   and the page's "Max edge" is inflated the same way. Renormalise
   (`p / sum(p)`) before claiming any edge in prose. Only
   `lambdarank_win_p` is book-preserving (sums to 1.000). The GC outlook
   head is per-rider too — read it as position-safety, not odds.
8. **The runner's `top-8:` console line is the BOARD's top eight, not the
   eight highest-priced riders.** Quote it as "the board's top eight, with
   prices"; take probability rankings from the JSON.
9. **Hindsight is never logged.** Run post-hoc scenarios with `--no-log`.
10. **Join on rider ids, never on names.** FirstCycling drifts
    (`Gee` → `Gee-West`, `Martin` → `Martin-Guyonnet`), and settlement by
    normalised name reports a rider who started as NOT ON BOARD.
11. **Rerunning a scenario logs a fresh opinion.** Logging is idempotent for
    an unchanged rerun; a changed release, scenario, field, profile, day key
    or race state creates a distinct one. Use `--only <key>` while iterating
    and `--no-log` for experiments.

### 3.2 Race-week checklist

Work through this in the week before stage 1. It is cheap now and expensive
on the first morning.

- [ ] Full `update_pipeline` run no more than two days before stage 1, for a
      fresh startlist, forms and kernels. `bucket_daymenu` retrains
      automatically.
- [ ] Day-menu channel loads — a dry run prints
      "day-menu channel ready: menu v1, kernels N rows".
- [ ] Kambi market open: run the odds capture once, confirm the race matches,
      and check that the discovered event ids landed in `campaign.json`.
- [ ] `campaign.json` complete: `fc_race_id`, `year`, `category`,
      `is_stage_race`, dates, every stage with its date, `timezone`,
      `void_stages`, `kambi_match`, and `uci_competition_url` from
      `uci_calendar resolve` (never a guess).
- [ ] Startlist cached and matched to internal database rider ids — record how
      many of the field matched, and resolve the rest through the crosswalk
      before stage 1.
- [ ] Dry-run the whole morning flow on stage 1 with `--no-log`, both
      scenarios, and confirm the key routes to a board with a sensible pool
      size. The scenario JSONs that dry run leaves behind get overwritten by
      the real morning run.
- [ ] `predictions/TEMPLATE_scenarios.json` — **optional since 2026-09-16**.
      Write one only when the campaign wants a house shape for every stage;
      without it the driver writes each stage's config from `campaign.json`
      (`nightly/autoconfig.py`) and derives the references from the day key.
- [ ] A GC config at `predictions/gc/scenarios.json` with `"target": "gc"`
      (stage races only) — also **optional since 2026-09-16**: the first
      driver preview creates one from this race's own earlier editions, or
      from recent GC competitions when the database has fewer than three.

---

## 4. SETTLE — after unit N has finished

### 4.1 Pull the results and standings

**Manual (FirstCycling, the supervised path):**

```bash
uv run python performance_eval/tour-de-france-2026/capture_results.py \
    --race-id <fc_race_id> --year <year> --out-root <campaign>/results --all
```

Expect "archived 18x results (winner: …)" and "classifications archived: gc, …".
"No stage selector found" or 0 results means FirstCycling served a truncated
page — **just rerun it**.

**Manual (UCI, the deterministic path the nightly uses):**

```bash
uv run python -m cycling_project.nightly.uci_acquire \
    --competition-url <uci_competition_url> --campaign <campaign> --unit stage_NN
uv run python -m cycling_project.nightly ingest \
    --campaign <campaign> --unit stage_NN --store fake
```

`uci_acquire` saves every response verbatim under `results/stage_NN/uci/`
and is idempotent; `ingest` runs every validator and only then writes the
FirstCycling-shaped `results.csv` / `results.json` / `gc.csv` /
`classifications.json`. A failed check exits 10 and writes nothing partial.
Unresolved identities become crosswalk proposals, never acceptances; a human
confirms an alias with:

```bash
uv run python -m cycling_project.nightly.uci_identity confirm \
    --lastname "NIELSEN" --firstname "Magnus" --fc-rider-id 7695 \
    --fc-name "Cort Magnus" --birth-year 1993 --by <you>
```

**Driver:** `settle` runs the acquisition in-process when the campaign has a
`uci_competition_url` and nothing is captured, then ingests.

```bash
uv run python -m cycling_project.nightly acquire --campaign <campaign> --unit stage_NN
uv run python -m cycling_project.nightly ingest  --campaign <campaign> --unit stage_NN
```

Provider selection is automatic and it means **UCI only** (chip X, 2026-09-22):
`--provider auto` picks `uci` when the capture is complete and picks nothing
otherwise — there is no fallback, and a campaign whose `campaign.json` has no
`uci_competition_url` exits 10 with `uci_url_needed`, carrying the
`uci_match_evidence` candidates so the operator can confirm the competition page
in the inbox. `--provider pcs`, named explicitly, is the attended-Mac path over
pages a human has already saved under `results/<unit>/pcs/`; the cloud never
reaches it. `--no-acquire` disables the in-process fetch.

**Identity policy (operator ruling 2026-09-16).** `--identity-policy
{strict,provisional}` on `ingest`, `settle` and `night` decides what an
unresolved rider **inside** the top-15 stage / top-20 GC gate does. The
default is `provisional`, for the unattended cloud tick: the rider is
archived under a provisional `uci:<key>` id with his place and time intact,
the page carries a plain caveat naming him, and a **routine**
`identity_provisional` task goes to the inbox instead of a waiting state.
**You are attended, so pass `strict`** — it refuses the capture and asks you,
which is still the better read when someone is watching:

```bash
uv run python -m cycling_project.nightly ingest \
    --campaign <campaign> --unit stage_NN --identity-policy strict
uv run python -m cycling_project.nightly settle \
    --campaign <campaign> --unit stage_NN --identity-policy strict
```

After confirming an alias (or a pending proposal) on the Mac, make the fix
durable in the archive — this is what replaces a provisional id the cloud
already published, and it is idempotent:

```bash
uv run python -m cycling_project.nightly.crosswalk reconcile-results \
    --campaign <campaign>            # add --dry-run to see the rewrites first
```

Only a human-confirmed mapping rewrites an archived result. Rebuild the
stage / one-day / GC pages afterwards so the caveat disappears with it.

### 4.2 Seed the model's state cache

**Manual:**

```bash
uv run python performance_eval/tour-de-france-2026/seed_state_cache.py \
    --race-id <fc_race_id> --year <year> --out-root <campaign>/results
```

Copies the archived results into `cached_race_results` so model runs attach
within-race GC state without re-scraping. Idempotent; run it every evening
after the capture. Without the flags it silently seeds the Tour.

**Driver:** step 2 of `settle`. Skipped for a one-day race.

### 4.3 Refresh the GC board and the tracker

**Manual** (update the GC scenario's `label` / `short` / `note` to the new
stage first):

```bash
uv run python netlify_site/build/predict_stage_scenarios.py <campaign>/predictions/gc/scenarios.json
python3 netlify_site/build/build_gc_tracker.py <campaign>/predictions/gc/scenarios.json
```

The run writes the campaign's GC JSON beside its config
(`predictions/gc/vuelta_gc.json`, `tdf_gc.json`) and logs one checkpoint per
rider; the builder writes `netlify_site/<prefix>gc.html` from the log, that
JSON and the archived `results/stage_NN/gc.csv`, mapping
`state_through_stage` back through `void_stages` (invariant 3). The builder
takes the GC config path and resolves everything against that config's own
campaign directory, so a second race publishes alongside the first.

**Driver:** `settle` templates the GC config to the new stage itself, runs
the prediction and the tracker.

### 4.4 Settle the stage page

**Manual:**

```bash
python3 netlify_site/build/build_stage_page.py <campaign>/predictions/stage_NN/scenarios.json
```

The page gains "After the stage" (actual top 10, and how much win
probability each scenario gave the winner against the devigged book) and the
hub card flips to "Won by …".

**Driver:** step 6 of `settle`, followed by `build_site_index.py` and
`build_site_frame.py` so the calendar and races views pick the race up.

### 4.5 Score the day key (tier-3)

**Manual:**

```bash
uv run python performance_eval/vuelta-2026/score_day_keys.py --campaign <campaign> --stage NN --also agent
```

Reconstructs the oracle item from the archived results with the same labeler
and frozen GMM that made the training keys, scores the morning read
(exact / covered / weight-on-true), appends to `review/key_scorecard.json`
and prints the running table. **Run it even for unkeyed stages** — the
oracle labels build the settled-stage corpus regardless. `--also agent` adds
the shadow agent's fields when `predictions/stage_NN/agent_key.json` exists;
replay records (`replay: true`) are scored into
`review/agent_replay_scorecard.json` and never into the tier-3 card.
`--agent-refresh` re-attaches agent keys from stored oracle rows without
touching the database.

**Driver:** step 4 of `settle`, always run, always with `--also agent`.

### 4.6 The retrospective

Two judgment products, in this order.

**a. The hindsight run** — *if we had known exactly what kind of day it would
be, what would the model have said?* Get the finish structure:

```bash
python3 - <<'EOF'
import json
d = json.load(open('<campaign>/results/stage_NN/results.json'))
gaps = [r['gap'] for r in d['results'] if isinstance(r['gap'], (int, float))]
for t in (0, 5, 30, 60, 120, 600):
    print(f'within {t:>3}s: {sum(1 for g in gaps if g <= t)}')
EOF
```

Then find the reference set. The modern way is the signature table:

```bash
uv run python -m cycling_project.nightly refs --archetype <name> --campaign <campaign>
uv run python -m cycling_project.nightly refs --list
```

It queries `experiments/selection_signatures_*.csv.gz` (working-group size,
winner margin, `frac_120s`, top-15 archetype shares) joined to
`competitions`, and excludes every reference already used in this campaign.
The older hand-rolled query against the gap curves is in the 2026-09-05
`tooling` lesson and still works when no archetype fits.

Add a `hindsight` scenario **last** in the scenarios map with `"refs"`, a
`"short"` of `"Hindsight (post-hoc)"` and a note saying it is a post-race
reconstruction, then run it without logging (invariant 9):

```bash
uv run python netlify_site/build/predict_stage_scenarios.py \
    <campaign>/predictions/stage_NN/scenarios.json --only hindsight --no-log
```

**b. The reflection** — add `"reflection": ["para 1", "para 2", …]` to the
stage config and rebuild the page (§4.4). Cover: which branch the road
picked; what each read gave the actual winner against the book (the settled
page's scoring table has the numbers, renormalised per invariant 7); what
the hindsight run says — was course knowledge the constraint, or something
structural the model cannot see (team tactics, break formation); and
anything to carry forward as a watch item. A retrospective on a keyed race
adds two panels: **key vs oracle** (what we keyed, what the road said) and
**pool with/without key** (which riders the day-menu board surfaced that the
production board missed, and the reverse).

**Driver:** `settle` writes `retro_facts.json` — the numbers a retrospective
is allowed to cite — and builds the page. The prose stays human until Gate E;
the editorial agent drafts it in shadow:

```bash
uv run python -m cycling_project.nightly.run_editorial --artifact stage_retro \
    --campaign <campaign> --unit stage_NN            # add --apply to merge the prose
```

---

## 5. PREVIEW — before unit M starts

### 5.1 Capture the odds (before the stage goes live)

Stage markets vanish from the feed once the stage is live, so this is the one
step with a deadline.

**Manual:**

```bash
uv run python performance_eval/tour-de-france-2026/capture_odds.py --campaign <campaign>
```

`campaign.json` supplies the match strings and archive root and receives the
event ids the run discovers, so nothing has to be copied out of the console.
Read one back with `--stage NN --print-event-id`. If the stage market has
not posted yet (Kambi puts up `Stage N` around 11:00–12:40 local the day
before), wait for it rather than re-running by hand:

```bash
uv run python performance_eval/tour-de-france-2026/capture_odds.py \
    --campaign <campaign> --wait-for-stage NN --until 13:00
```

It polls every 15 minutes and exits 2 if the deadline passes with no market.
Brands in `--brands` are tried in order (`ubnl,ubuk,ubse,rivers,rsiuspa`) and
the serving brand is recorded in `provenance_*.json` and in the CSV's `brand`
column. When every brand blocks, the run writes `odds/<day>/degraded.json`
and exits 0 — a bookless day is recorded, not a crash, and the model board is
unaffected. If a brand answers but the race is not in it, the run exits 1 and
writes fuzzy `kambi_candidates` into `campaign.json` for a human to confirm;
nothing below the 0.95 threshold is ever accepted automatically. `--match`
**overrides** the campaign's own names rather than adding to them.

Running it twice a day (early, then near the start) archives line movement
for free.

**Driver:** step 1 of `preview`. Only a WorldTour campaign waits on a market
match; elsewhere a missing book is recorded (`no_kambi_market`) and the
preview continues without the benchmark columns.

### 5.2 Route facts (only when the organisers redraw the stage)

Write `predictions/stage_NN/route.override.json` with the corrected numbers
and a `reason`, then:

```bash
uv run python -m cycling_project.nightly.route_facts ingest-route <campaign> stage_NN
```

It merges the override over the acquisition thread's `route_raw.json` and the
archived FirstCycling stage page, validates the numbers, and writes
`route.json` graded `complete` / `partial` / `missing`. Missing facts are
recorded, never invented.

**Driver:** step 3 of `preview`, run when `route_raw.json` or
`route.override.json` is present.

### 5.3 Freeze the bundle and take the agent's key (shadow)

Before writing your own key, so the agent's read is independent:

```bash
uv run python -m cycling_project.nightly.run_day_key --campaign <campaign> --stage NN
```

It freezes `predictions/stage_NN/bundle/` (the newest odds snapshot captured
before the stage's start, `gc.csv` after N−1, the settled-stage ledger, the
scorecard restricted to earlier stages, `route.json`, the menu reference, and
`manifest.json` with sha256s), makes one `claude-opus-5` call with
`agents/skills/day-key-read/SKILL.md` as the system prompt, and writes
`predictions/stage_NN/agent_key.json`. The record is shadow only. `--dry-run`
builds the bundle without the API call; `--rebuild-bundle` discards a frozen
bundle (only before the stage). **A bundle built after the stage has started
is a replay input, not a prospective one** — key such a stage with
`--replay --stages NN`, and it is scored into the replay card, never tier-3.

**Driver:** step 4 of `preview` freezes the bundle. Skipped for a one-day race.

### 5.4 Write the day key (judgment)

The **`day_key` at the config root is the official morning read** — logged
before the stage, it *is* the tier-3 archive entry. Vocabulary and serve
guidance: `day_menu_v1_reference.md` (repo root).

1. Route macros mechanically: individual time trial from the road book → the
   runner needs no key (`itt` routing is automatic at oracle time; key it
   `{"itt": 1}` for the record); full bunch sprint expected → `{"bunch": 1}`;
   GC group contests the win → `{"gc_day": 1}`.
2. Otherwise family first: escape / select group (`res_2` / `res_4` /
   `res_6`) or fractured fast finish (`res_3` / `res_7`, with `res_1`
   between)?
3. Grade within the family; when torn, weight two or three items:
   `"day_key": {"res_2": 0.6, "res_4": 0.4}`.
4. Never key `res_5`; avoid `res_0` — weight the family candidates instead.

Neighbours flip and families do not: the key names the family and the weights
grade it. The three tests that decide a family — chase incentive, launchpad,
and who owns both the sprinter and the puncheur — are in `LESSONS.md` under
`keying`, each with the stage that produced it.

**Driver:** step 5 of `preview` resolves the key in this order: a key already
in the config, then an approved `day_key_decisions` row, then the agent's own
decision record — `--agent-key <path>`, or, since 2026-09-17, whatever sits at
`predictions/<unit>/agent_key.json` with no flag at all. With none of those it
exits 10 with a `day_key_needed` operator task. The key comes **before** the
references: step 5b (`scenario_refs`) derives every missing reference set from
the key it just resolved, so a placeholder reference is no longer a human gate.

A board priced from the agent's record is stamped `day_key_author: "agent"` and
`day_key_source: "agent:<file>"`. That stamp is what keeps the two reads apart
everywhere downstream:

- `score_day_keys.py` leaves the tier-3 card **unkeyed** for such a config (it
  is not a human morning read) and scores the record itself through
  `--also agent`, so the agent is still graded on the day;
- the stage page says on its face that the key was written by the automated
  reader, not by a person;
- publication is unaffected and still human: pages go to `site-staging/` and
  reach the public site only through an inbox approval and `promote.py`.

An approved human key always wins; the agent record is only read when no human
key exists. The `day_key_needed` task the first pass files is left alone — the
inbox reconciles it once a later run's `day_key` step succeeds.

### 5.5 Choose the scenario paradigms (judgment)

The key and the scenarios are one edit to one file — `scenarios.json` carries
both — so in practice §5.4 and §5.5 happen together. They are split here
because they are graded separately: the key is scored against the oracle, the
scenarios against the book.

Aim for about three scenarios: distinct, plausible readings of the day. Two
ways to build one, mixable per scenario.

- **Real references** (preferred): 4–6 database competition ids whose stages
  embody the reading. `nightly refs --archetype <name>` is the fast path.
  By winner type:

  ```sql
  SELECT c.id, r.name, r.year, c.name, ri.name FROM rider_results rr
  JOIN riders ri ON ri.id=rr.rider_id
  JOIN competitions c ON c.id=rr.competition_id
  JOIN races r ON r.id=c.race_id
  WHERE rr.place=1 AND ri.name LIKE '%<rider>%' AND r.year>=2021;
  ```

  Check their profile scores in `competition_field_features` for coherence
  before using them.
- **Synthetic overrides**: `"base_refs"` (for gradients and metadata) plus
  `"scores": {"sprint": 0, "mountain": 0.4, …}` summing to about 1.

**Model-space semantics — memorise these, they are not intuitive:**

- High `race_hilly_score` = a classics day ending in a **reduced bunch
  sprint** (sprinters up, GC men down). It is not a puncheur read.
- Puncheur / selective days = rolling 0.4–0.6 with mountain 0.2–0.4.
- Breakaway-won mountain days = rolling ~0.55 with mountain ~0.45.
  `race_breakaway_score` does **not** mean "the break wins" (Montjuïc
  circuits score 0.33 on it; actual break-won stages score ~0).
- The model prices rider-course fit, not break formation or team tactics. On
  a true break day its raw board is the "break gets caught" branch, with GC
  stars on top because they fit the terrain.

Three presentation-only devices follow from that last point. None of them
touches a logged prediction or the settlement.

| Device | When | How |
|---|---|---|
| `"exclude_top_gc": N` on the break-read scenario | any break read | The page drops the top-N GC contenders and renormalises the rest into "if the break wins" odds. From about stage 10, prefer `"exclude_top_gc": 10, "exclude_gc_source": "standings"` — the pool becomes the top-N of the **actual** GC from the newest `results/stage_NN/gc.csv`. Pick N at the standings cliff. |
| **Punchy filter** | a selective day won by a fast hard-man, where high hilly would keep the pure sprinters on top and rolling+mountain would bury every fast man equally | Add a `"hidden": true` scenario `anchor_sprint` with flat archetype refs, run it `--only anchor_sprint --no-log`, and add a top-level `"punchy_filter": {"sprint_anchor": "anchor_sprint", "selective_scenario": "<break-read key>", "anchor_floor": 0.01, "retention_max": 0.08}`. Riders above the floor are classified by **retention** = selective-read p / anchor p: pure sprinters collapse, punchy fast men retain. |
| **Mirror-image filter on a flat day** | a break read on flat roads | `exclude_top_gc` is nearly a no-op there (the sprinters sit ~130th on GC) and the men an escape must beat are the sprinters. Add `"exclude_sprinters": true` to the break scenario and give the `punchy_filter` a **hidden rolling anchor** as its `selective_scenario` — a hilly read cannot classify sprinters. Set `"emit_pool": false`: block 1 already is the sprinters-removed pool. |

Write `predictions/stage_NN/scenarios.json` from
`predictions/TEMPLATE_scenarios.json` (fields: stage, date, `odds_capture` =
today's `YYYY-MM-DD/markets_HHMM.json`, `event_id`, and the scenarios with
label / short / refs-or-scores / tag / note). Tag convention:
`stageN_<slug>`.

**Driver:** `preview` writes the config when it is absent — from the template
if the campaign ships one, otherwise from `campaign.json` itself (stage,
date, `label` from the stage's towns and distance, `void_stages`, one
reference-less `main_read` scenario) — and fills in the event id and the odds
capture. **Since 2026-09-16 no human writes the references either**: the
`scenario_refs` step runs after the key is resolved and fills every
reference-less scenario from it (menu item → the item's canonical
archetype-share signature in `models/production/day_menu_v1.json` →
`refs.ARCHETYPES` → five unspent days, this race's own editions and the
campaign's category tier first), and an auto-written config also gains one
alternate branch for the key's second-weighted *family*. Every generated
scenario carries `refs_source` / `refs_archetype` / `refs_note`, so the page
and the retro can say the references were machine-chosen. `preview` still
exits 10 with `day_key_needed` when there is no key, and with
`scenarios_needed` only in the one genuinely impossible case: no
`experiments/selection_signatures_*.csv.gz` to query.

### 5.6 Run the models

**Manual:**

```bash
uv run python netlify_site/build/predict_stage_scenarios.py <campaign>/predictions/stage_NN/scenarios.json
```

Check the log line `race state: available=True through stage N` — `False`
means §4.2 was skipped (state also loads from the main database once the
weekly pipeline has migrated the in-progress race). The runner drops riders
who are out of the race (the `out of race:` line names them) and logs one row
per active rider to `prediction_log`. For an announced withdrawal the road
has not recorded yet, add a top-level `"exclude_riders": ["Name"]` and rerun.
With the day-menu channel active the run prints
`day key: {…} -> kernod board (pool of K)`, and each output JSON records
`day_key`, `board: daymenu` and a per-rider `daymenu_rank` — the published
board order. **Prices are the production heads' output in every case**; the
key only ranks.

**Driver:** step 6 of `preview`.

### 5.7 Run the analysis blocks

**Manual only — there is no driver equivalent.**

```bash
python3 netlify_site/build/build_stage_analysis.py \
    <campaign>/predictions/stage_NN/scenarios.json --break-scenario <break-read key>
```

Writes "If the break goes" (GC captains removed, remaining pool
renormalised) and "The book's card" (the top 10 book favourites under every
scenario, with GC-pool status) into the config. The exclude count comes from
the break scenario's `exclude_top_gc` (falls back to 24; override with
`--gc-exclude N`) — keep the flag and this block in agreement so the table
and the scenario board tell the same story. With a `punchy_filter` in the
config a third block, "The punchy pool", is written and per-rider
anchor/retention diagnostics are printed: check the pure-sprinter /
punchy-fast-man split before building the page, and adjust `retention_max`
if a name lands on the wrong side (rerunning this step is cheap — no model
rerun needed). Scenarios flagged `"hidden": true` never render and never
become table columns.

### 5.8 Build the preview page

**Manual:**

```bash
python3 netlify_site/build/build_stage_page.py <campaign>/predictions/stage_NN/scenarios.json
python3 netlify_site/build/build_site_index.py
python3 netlify_site/build/build_site_frame.py
```

The first writes `netlify_site/<prefix>stageNN.html` and refreshes the hub
(`stages.html`), the stage strip and `index.html`; the other two refresh the
calendar and races views and the routing frame. Preview locally with
`python3 -m http.server 8411 --directory netlify_site`.

**Driver:** step 8 of `preview` — the same three builders, run after
`validate` (§5.9) and before `upload`.

### 5.9 Validate

**Manual / driver:**

```bash
uv run python -m cycling_project.nightly validate --campaign <campaign> --unit stage_NN
```

Checks schemas and NaNs, that `lambdarank_win_p` sums to about 1,
`post_hoc` on late configs, `void_stages` consistency, day-key weights
summing to 1, and crosswalk coverage of the field. Coverage below 0.90 is a
**warning** under the default `--identity-policy provisional` (2026-09-18: a new
race's crosswalk is nearly empty, and unresolved riders settle under provisional
`uci:` ids anyway) and a blocking problem only under `--identity-policy strict`.
The driver runs it as step
7 of `preview`, between the model run and the page build; by hand it is worth
running whenever a config has been edited late.

### 5.10 Ship

```bash
git add netlify_site <campaign>/{predictions,odds,results,review}
git commit -m "Stage M preview / stage N retrospective"
git push origin webscrape-refactor
```

Data snapshots are tracked: odds, results and the prediction JSONs go in
alongside the configs, scripts and pages. Only raw scraped HTML is ignored
(`stage_page_*.html`, `race_page_*.html`, `odds/**/raw/`), so a plain
`git add netlify_site` also picks up strays — check `git status` first.

**Deployment is a separate, manual step**: the push publishes nothing.
Cloudflare is the public surface (Workers Builds on the `site` branch, or
`wrangler deploy`); the older Netlify path was dragging `netlify_site/` onto
app.netlify.com. Pages produced by the cloud nightly are staged, never
published — see §7.

---

## 6. One-day race variant

A one-day race is **one unit called `race`**. Everything the stage path
spreads across `stage_NN` it keeps in one place: config at
`predictions/race/scenarios.json` with `"target": "one_day"`, results at
`results/race/`, page at `netlify_site/<race>-<year>.html`, hub at
`/race/<race>/<year>` with the board at `/race/<race>/<year>/prediction`.
`<race>` there is `site.route_slug`, or the campaign slug with its trailing
year stripped — so `strade-bianche-2026/` publishes
`netlify_site/strade-bianche-2026.html` at `/race/strade-bianche/2026`.

What changes:

- **No day key** — the day menu prices stage-day shapes — and **no
  `void_stages`** and no `stage`. The loader refuses a config carrying them.
- **No state seeding, no GC config, no GC tracker, no key scoring.**
- **The default scenario prices the race on its own last five editions**,
  looked up from the database by `fc_race_id`
  (`cycling_project/nightly/oneday.py`). Alternates use archetype references
  from `nightly refs --archetype …`.
- **The field** comes from a `startlist.json` beside the config (what the
  cloud acquisition thread hands over), else the newest `startlist.json` beside
  any sibling unit of the campaign (2026-09-18: one race, one field — source
  `handover:<unit>/startlist.json`), else the `cached_start_lists` cache,
  else a rate-limited FirstCycling scrape; `--no-scrape` refuses the last.
  **The driver checks for the field before `predict` and refuses the scrape by
  default** (2026-09-17; every preview unit since 2026-09-18, not only one-day
  and stage 1): a preview with no handover anywhere in the campaign and no
  cache row exits 10 with `startlist_needed`
  (`blocks_publication`) and names the Mac's `nightly.horizon` capture as the
  supply. Nothing is fetched, no triage is spent, and the unit comes back
  tomorrow. An attended Mac run that *wants* the scrape passes `--allow-scrape`,
  which also drops `--no-scrape` from the runner's argv.
- **UCI ingest reads the single "General Classification" document as the race
  result** and writes **no `gc.csv`** — a one-day race has no standing. The
  attended-Mac `--provider pcs` path is still stage-shaped and refuses a one-day
  capture at `pages_present` rather than half-writing it.

The cycle is preview the evening before, settle the evening after:

```bash
# preview
uv run python -m cycling_project.nightly preview --campaign <campaign> --unit race
# or by hand:
uv run python netlify_site/build/predict_stage_scenarios.py <campaign>/predictions/race/scenarios.json
python3 netlify_site/build/build_oneday_page.py <campaign>/predictions/race/scenarios.json
python3 netlify_site/build/build_site_index.py && python3 netlify_site/build/build_site_frame.py

# settle
uv run python -m cycling_project.nightly settle --campaign <campaign> --unit race
```

Settling a race the database already holds needs no scrape:

```python
from cycling_project.nightly import oneday
oneday.export_results_from_db("<campaign>", "<fc_race_id>", <year>)
```

**A board built after the race is a reconstruction.** The serving path
re-ages form to the day the board is built, not to the config's race date,
so mark the config `post_hoc` and the page prints a banner naming the leak.

---

## 6a. Horizon capture (Mac, daily)

The cloud cannot fetch a start list, a stage page or a route: FirstCycling and
PCS are behind Cloudflare, the UCI serves results only, Kambi lists WorldTour
only. The Mac captures them the same day and hands them over as artifacts.

```bash
# scheduled: agents/mac/com.cycling.horizon.plist, 10:30 local (17:30 UTC),
# about two hours before the 19:45 UTC tick
uv run python -m cycling_project.nightly.horizon --store auto

# what it would do — no fetch, no writes, fake store
uv run python -m cycling_project.nightly.horizon --dry-run --days 4

# one campaign, or a wider horizon
uv run python -m cycling_project.nightly.horizon --campaign giro-d-abruzzo-2026
uv run python -m cycling_project.nightly.horizon --days 5 --max-age-hours 12

# a .1 race: outside the nightly's coverage, so capture it explicitly (§1a)
uv run python -m cycling_project.nightly.horizon --campaign giro-d-abruzzo-2026 --all-tiers
```

The capture covers exactly what the tick will ask for — WorldTour and .Pro
(§1a) — because a start list handed to a race nobody plans is a wasted
FirstCycling fetch. `--all-tiers` / `--include-tier d1` restores a `.1` race
for this run.

For every unit due to be previewed inside `--days` (default 3) it writes:

| What | Where | Read by |
|---|---|---|
| start list | `cached_start_lists` + `predictions/<unit>/startlist.json` | `resolve_startlist` (handover first), `oneday.load_startlist_file` |
| stage page (verbatim) | `results/<unit>/stage_page_<date>.html` + `horizon_raw.json` | `route_facts.ingest_route` |
| route facts | `predictions/<unit>/route.json` | the preview, the day key, the page |
| stage metadata | `campaign.json` `stages[]` (date, towns, distance, `itt`/`ttt`) | the hub, the registry rows |

All of it uploads as `<run_id>/<campaign>/<relpath>` artifacts, which
`bootstrap` overlays into the container on the next tick, and the run appears
in the ledger with phase `horizon`, host `mac`.

Notes that bite:

- **A visible Chrome window is required** (`SCRAPER_USE_BROWSER=1`); run it
  while logged in, and do not close the window mid-run.
- It is idempotent: anything younger than `--max-age-hours` (20) is reused, so
  a second run the same day makes no requests at all.
- A campaign that fails files a `horizon_failed` operator task (urgency
  `routine`) and the command still exits **0** — one bad race never costs the
  others their handover. Check the inbox, then re-run just that campaign.
- `stages_provisional` only clears when every stage has a date, towns and a
  distance; until then the stage list stays honest about what is not yet known.
- Logs: `performance_eval/runs/horizon_<date>.log`. Setup and `launchctl`
  commands: `agents/mac/README.md`.

---

## 7. Cloud variant — the nightly

One scheduled Managed Agents deployment, 19:45 UTC, one session, one thread
per due race. The full design is `NIGHTLY_AGENT_WORKFLOW.md`; what matters
for this runbook:

1. **`bootstrap`** downloads the newest **approved** release bundle from
   Supabase Storage by sha (code zip, models, `inference_slice.db`, kernels,
   calendar, campaign dirs, crosswalk), verifies the model contract hashes,
   points serving at the slice, and hydrates the campaign directories from
   the bundle plus every artifact inserted since. It fails closed on any
   mismatch.
2. **`plan`** lists the due units; **`night`** runs every due settle, then
   every due preview, for one campaign. A campaign outside the nightly's
   coverage (§1a) returns no due units and `"skipped": "not_automated: …"` —
   that is the answer, not a failure, and nothing is filed for it.
3. **Acquisition is the UCI, and only the UCI** (§4.1): the `uci-acquirer`
   thread runs the deterministic command, and the deterministic `ingest`
   validates the capture before anything downstream reads a row. **An agent
   never transcribes, repairs, reorders or invents a result.** There is no
   second source: a unit the UCI has not published waits for tomorrow, and a
   race with no `uci_competition_url` waits for the operator
   (`uci_url_needed`). The ProCyclingStats fallback was retired from the cloud
   on 2026-09-22 (chip X) — PCS has 403ed Anthropic's `web_fetch` since
   2026-09-06, and describing a dead path as live cost the coordinator ten tool
   calls hunting for a way to use it. Do not probe PCS.
4. **The judgment gates hold.** No approved day key → exit 10 and an
   operator task, and the campaign stops there for the night. Prose-less
   previews are allowed; prose-less retrospectives are not.
5. **Nothing reaches git or the public site from the cloud.** Rows go into
   append-only Supabase tables, files into insert-only buckets, pages into
   `site-staging/<run_id>/`. Promotion runs on the Mac with a key the
   deployment does not hold:

   ```bash
   uv run python -m cycling_project.nightly.promote --latest-approved --dry-run
   ```

6. **The weekly Mac run is the release step**: FirstCycling scrape →
   migrate → features → retrain → pull the week's rows and artifacts back
   into the repo → reconcile → export the slice → build and upload the next
   release bundle → promote approved pages.

**`--store auto` (the default) writes to the hosted ledger** whenever
`SUPABASE_URL` and `SUPABASE_NIGHTLY_KEY` load from
`~/.config/cycling-project/secrets.env`, which is the case on this Mac. Any
run that is not the real nightly must pass `--store fake` or `--dry-run`;
the agent role's rows are append-only and only the service key can remove
them.

---

## 8. Known failure modes

| Symptom | Fix |
|---|---|
| Results capture: "no stage selector" / 0 results | FirstCycling truncated the page — rerun; a retry has always worked. |
| FirstCycling race page 403s during a serving run | Expected under load; state resolves from the seeded cache. Keep seeding each evening. |
| Mid-race race-page archive looks like a DNF list | It is one — mid-race FirstCycling serves only the DNF board at race level. The real standing is the per-stage `results/stage_NN/gc.csv`. |
| Odds capture: HTTP 403/451, or no events matched | Geo-fence — try another brand or an NL VPN; or the markets are already live and you are too late. |
| Odds capture: only the classification markets, no stage event | Kambi's naming drifts — the stage event is sometimes English ("Stage N (…") not localised, and has shipped with the closing paren dropped. Rerun with a looser `--match` (no parens) and grep the raw `listview_*.json` for the event id. |
| Odds capture exits 1 with `kambi_candidates` in campaign.json | A brand answered but the race did not match above 0.95 — a human confirms the candidate; nothing is auto-accepted. |
| Every brand blocks | `odds/<day>/degraded.json` is written, exit 0. A bookless day is recorded; the model board is unaffected. |
| Runner: `race state: available=False` | Seed the state cache (§4.2). |
| Runner: startlist assert fails | The cached startlist is missing. Mid-race this should not happen — investigate before scraping. |
| Chrome window does not appear | `SCRAPER_USE_BROWSER=1` missing from `.env`. |
| A scenario logged twice | Harmless — opinions are timestamped. Settle on the latest pre-race run per tag. |
| Driver exits 10 | A judgment call is missing (day key, scenario references, a Kambi match, an identity). The JSON names it; the campaign stops there for the night. |
| Driver exits 20 | A real failure: `error_class`, `step` and `log_path` are in the JSON. |
| A rider shows as NOT ON BOARD in settlement | Name drift — join on rider ids (invariant 10). |

---

## 9. End of campaign

Settle everything against `prediction_log`. Rows are tagged by
`model_version = <retrain date>|<scenario tag>`; `competition_id` backfills
once the race migrates into the database via the weekly pipeline. The frame
is `market_avg_log_loss` on the honest DNF-adjusted startlist, with the
devigged book as the benchmark. Hindsight scenarios were never logged and
stay out of settlement by construction.

Two standing retrospectives run alongside it:

- **The day-key record**: `review/key_scorecard.json` is the tier-3 archive
  (exact / covered / weight-on-true per stage). The agent's shadow keys sit
  beside it and are scored, never substituted.
- **The grand-tour hard-day retrospective** — the standing design hole:
  shattered non-mountain days won by punchy non-climbers from breaks, late
  moves, or reduced hard-men sprints. Mountains and sprints are solved; this
  class is not. The settled stages are the labelled corpus: label each day's
  finish shape from the gap curves, score every read's winner pricing from
  the reflections, and check the punchy-pool hit rate on the hard days.
  Prior art, structural constraints and candidate directions are in the
  memory note `gt_hard_day_design_hole.md`.

`performance_eval/tour-de-france-2026/build_review_dataset.py` builds the
review dataset; it has not been generalised to other campaigns yet.
