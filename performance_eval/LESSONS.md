# Campaign lessons — dated ledger

Everything the Tour de France 2026 and Vuelta a España 2026 campaigns taught,
in one place, newest first. The procedure these lessons produced is in
[`DAILY_RUNBOOK.md`](DAILY_RUNBOOK.md); this file is the evidence behind it.

**Cite an entry by its date and tag**, e.g. "the 2026-09-06 `keying` lesson".
The day-key skill (`agents/skills/day-key-read/`) and the editorial skill
(`agents/skills/editorial/`) both reference entries this way.

Tags:

| Tag | Covers |
|---|---|
| `keying` | how to read a day and pick a day-menu item |
| `tooling` | scripts, flags, configs, the things that bite |
| `acquisition` | getting results, odds and route facts out of a source |
| `scoring` | settlement, the scorecard, probability arithmetic |
| `publishing` | pages, the site, what ships and how |

Dates are the day the lesson was recorded, which for a stage lesson is the
day after the stage. Every entry was verified against the campaign archives
when this ledger was merged (2026-09-08); nothing has been reworded into a
claim the original did not make.

---

## Index

| Date | Tag | Lesson |
|---|---|---|
| 2026-09-17 | `keying` | A key nobody uses is not a key: the agent's read has to price the board |
| 2026-09-17 | `acquisition` | The last resort of a serving path is the first thing to fail in the cloud |
| 2026-09-17 | `tooling` | "Is this stage due?" is a question about a clock, not a date |
| 2026-09-16 | `tooling` | Bootstrap listed the artifact bucket one run at a time and fetched every version of every path |
| 2026-09-16 | `tooling` | A gitignored input is invisible to the release bundle until a settle needs it; one root cause must file one task |
| 2026-09-16 | `keying` | An unresolved rider must not hold a settle hostage when nobody is watching |
| 2026-09-16 | `tooling` | A race no human prepared is a race the driver cannot run — until the config writes itself |
| 2026-09-16 | `keying` | References are judgment about the KEY, so the key has to come first |
| 2026-09-16 | `acquisition` | The cloud cannot learn about a new race by itself; the Mac captures its horizon |
| 2026-09-13 | `acquisition` | A stage race's LAST stage keeps its overall classifications in a different accordion |
| 2026-09-13 | `keying` | The bunch macro grades winner-group SIZE, not winner TYPE |
| 2026-09-13 | `keying` | The closing-circuit time freeze is a Tour practice, not a grand tour one |
| 2026-09-12 | `tooling` | A shared builder hardcoded to one campaign fails silently, not loudly |
| 2026-09-12 | `scoring` | A backfilled config must be marked `post_hoc` when it is written, not when someone notices |
| 2026-09-12 | `tooling` | A post-hoc board's features are clean; the hindsight is in the operator |
| 2026-09-08 | `tooling` | This ledger and the generic runbook do not ship in the release bundle |
| 2026-09-06 | `keying` | One team owning both the sprinter and the puncheur breaks the chase-incentive test |
| 2026-09-06 | `acquisition` | An organiser can redraw a stage after the market and the boards are done |
| 2026-09-06 | `acquisition` | UCI is the primary results source; ProCyclingStats now blocks Anthropic's fetcher |
| 2026-09-05 | `keying` | The launchpad check is subordinate to the composition of the move |
| 2026-09-05 | `keying` | Incentive predicts whether the GC group races, not whether the break is caught |
| 2026-09-05 | `keying` | A road book can overrule the working read |
| 2026-09-05 | `scoring` | `post_hoc: true` or the scorer promotes a hindsight key into the tier-3 archive |
| 2026-09-05 | `scoring` | The winner-inside-GC-top-10 clause mislabels a breakaway rider who banked time |
| 2026-09-05 | `scoring` | The runner's `top-8:` line is the board's top eight, not the top eight prices |
| 2026-09-05 | `scoring` | A missed day cannot be recovered |
| 2026-09-05 | `scoring` | Backfilled GC checkpoints reconstruct the classification, not the read |
| 2026-09-05 | `tooling` | Join on rider ids; FirstCycling names drift |
| 2026-09-05 | `tooling` | `--all` is mandatory on the daily results capture |
| 2026-09-05 | `tooling` | Every config on a race must carry that race's `void_stages` |
| 2026-09-05 | `tooling` | Cancelled-stage protocol |
| 2026-09-05 | `tooling` | Hindsight reference sets come from the signature table |
| 2026-09-05 | `tooling` | `load_book` tolerates a missing market |
| 2026-09-05 | `acquisition` | A mid-race race-page archive is a DNF board, not a standing |
| 2026-09-05 | `acquisition` | The FirstCycling race page 403s during serving runs |
| 2026-09-05 | `acquisition` | Kambi brand fallback and degraded mode |
| 2026-08-21 | `tooling` | The shared capture scripts silently default to the Tour |
| 2026-07-24 | `publishing` | Data snapshots are tracked; the deploy is manual |
| 2026-07-15 | `acquisition` | Kambi's stage-event naming drifts |
| 2026-07-14 | `keying` | A break read on a flat day needs the mirror-image filter |
| 2026-07-14 | `scoring` | `blend_win_p` is not a distribution |
| 2026-07-12 | `keying` | Prefer actual standings to the model blend for the GC pool |
| 2026-07-12 | `tooling` | `state_through_stage` is a count, not a stage number |
| 2026-07-11 | `keying` | The punchy filter, for a selective day won by a fast hard-man |
| 2026-07-11 | `keying` | The grand-tour hard-day hole is the standing design gap |
| 2026-07-06 | `keying` | A break read must carry `exclude_top_gc` |
| 2026-07-05 | `keying` | Model-space semantics are not intuitive |
| 2026-07-05 | `acquisition` | A truncated FirstCycling results page is fixed by rerunning |

---

## 2026-09-17 — A key nobody uses is not a key: the agent's read has to price the board

**Tag:** `keying`

The 2026-09-17 tick (session `sesn_01EXAMPLE84203F8B85F028F`, release
`data-2026-09-17`) settled 10 of 12 units and produced **no preview board at
all**. It was not a failure: every piece worked. Tour de Luxembourg stage 3 and
Giro d'Abruzzo stage 4 got a machine-written config, a GC config, a frozen
bundle and a day key from the day-key-reader — Abruzzo came back
`bunch 0.60 / res_3 0.28 / res_7 0.12` — and then the thread stopped, because
the coordinator's own instructions told it to save the record and let the
operator task stand (hosted tasks 90, 91). The key was filed where nothing read
it. Every prior chip in the "no human setup" wave removed a *setup* step; this
was the one place where the work was done and simply not used.

The driver had supported `preview --agent-key <file>` since chip E. What was
missing was the instruction to run it, and the willingness to let a machine key
price a board. Both now exist: the coordinator re-runs `preview` with the record
it just received, and the driver picks up `predictions/<unit>/agent_key.json`
even with no flag, so one unattended pass reaches a page.

What keeps the boundary honest is the stamp, not the stop. A board priced this
way carries `day_key_author: "agent"`; `score_day_keys.py` refuses to read such
a config as a logged human read (the tier-3 row stays unkeyed) and scores the
record through `--also agent`; the page says the key was written by the
automated reader; and publication still needs a human approval and `promote.py`.
Gate K did not move — the cost of an unattended night did.

Two traps found in passing. The coordinator prompt named the file
`day_key_agent.json` while every piece of code — `run_day_key`, the uploader,
the scorer, the board-detection set — uses `agent_key.json`, so even a
hand-wired run would have been scored as if the agent had never keyed the day;
worse, the unknown name would have counted as a rendered board and made the
stage look already previewed. The prompt now uses the canonical name and the
driver tolerates both. And the first pass of a stage still files
`day_key_needed`, by design: the inbox retires it automatically once a later
run's `day_key` step succeeds.

## 2026-09-17 — The last resort of a serving path is the first thing to fail in the cloud

**Tag:** `acquisition`

Kampioenschap van Vlaanderen 2026 had no `predictions/race/startlist.json`
handover — FirstCycling had not published the list, and the Mac's daily
`nightly.horizon` capture retries each morning — and no `cached_start_lists`
row. `predict_stage_scenarios.resolve_startlist` therefore fell through to its
third option, a live FirstCycling scrape, *inside the container*: Cloudflare
403, `predict` exit 1, driver exit 20, and a paid ops-triage cycle to establish
that a start list was missing (hosted task 93).

The runner already had `--no-scrape`; nobody was passing it. A fallback that is
correct on the Mac is a guaranteed failure in the cloud, and it fails late, deep
inside a step, where it costs the most to diagnose. The driver now checks for
the field **before** `predict` — a one-day unit, or stage 1 of a stage race,
with neither a handover nor a cache row exits 10 with `startlist_needed`
(`blocks_publication`) naming the horizon capture as the supply — and passes
`--no-scrape` to every predict it launches unless an attended run asks for
`--allow-scrape`. The inbox retires the ask when a later `predict` succeeds: the
step that consumes the list is the proof it arrived.

The general rule: when a serving helper ends in "…else fetch it", the driver
must decide that last branch explicitly, in the open, before the step starts.

## 2026-09-17 — "Is this stage due?" is a question about a clock, not a date

**Tag:** `tooling`

Tour of Huangshan stage 1 is dated 2026-09-18 in Asia/Shanghai. The tick fires
at a fixed 19:45 UTC, which on 2026-09-17 was already 03:45 on the 18th in
Shanghai, so `plan` read "race-local today = the stage's date" as "the stage has
been ridden", listed it as settle-due, and filed an `acquisition_needed` task
(`blocks_settlement`) for a race that started some hours later (hosted task 88).
Campaigns have carried a `timezone` since the beginning and the planner used it
— to get the *date*. A date is not enough: east of UTC the tick lands in the
small hours of the next local day.

Due-ness is now the local wall clock. A stage settles once its own local day is
over — a past local date, or the local date past 18:00 local — and stays
previewable while that day has not begun, before 09:00 local. The same 03:45
tick that was filing an acquisition ask now previews the stage, which is exactly
what it is: a morning read. Between the two hours the race is on the road and
the unit is in neither list. `--today` still means that date's evening (every
existing caller means the nightly tick); `--local-now <ISO>` is there when the
hour is the point.

One consequence worth stating: the preview horizon counts from the day being
raced, not from the calendar date. Without that, the 03:45 tick previews today's
stage *and* tomorrow's, and tomorrow's board would be built before today's
result exists — no race state, and `has_boards` would stop it ever being rebuilt.

## 2026-09-16 — Bootstrap listed the artifact bucket one run at a time and fetched every version of every path

**Tag:** `tooling`

`nightly bootstrap --tag data-2026-09-17` took ~25 minutes on the Mac, and the
cloud tick paid the same every night (sessions 18–27 min active). The bundle
download was a few minutes; the rest was `overlay_artifacts`.
`store.list_artifacts()` issued one Storage list request per folder per run —
Storage's list endpoint is folder-at-a-time and this project's storage-api
(1.77.5) has no recursive form — 471 requests / 63 s for 140 runs, and a bare
call from a script hit the 60 s read timeout. Then every object that was
bundle-lacking or newer than the release was downloaded oldest-first, later
runs overwriting earlier downloads of the same path: 344 downloads for 219
distinct paths.

Fix (branch of 2026-09-16): the listing is one paged PostgREST call to
`public.artifact_index()` — migration 0007, a SELECT over `storage.objects`
that the agent role may already read — falling back to a parallel folder walk
from the bucket root until the migration is pushed; the objects collapse to
the newest per campaign-relative path before anything is fetched; a path whose
local file already carries the object's md5 (Storage's etag) is not fetched
again; and bootstrap prints one line, `artifacts: N objects listed over P
paths; A applied, S skipped (…)`. A path the bundle lacks still always applies
(the 2026-09-09 rule).

## 2026-09-16 — A gitignored input is invisible to the release bundle until a settle needs it; one root cause must file one task

**Tag:** `tooling`

Three ticks in a row (2026-09-14..16) every stage-race settle in the cloud
died at `hindsight` with "no usable historical references match the settled
oracle". The per-competition signature table
`experiments/selection_signatures_<stamp>.csv.gz` is gitignored
(`experiments/*.csv.gz`) and belonged to no bundle group, so the container
never had it; `nearest_refs` returned nothing. One-day races hid the hole
because they fall back to their own past editions. The Vuelta hid it too:
every stage had a morning preview, so no settle ever reached hindsight. The
2026-09-08 lesson above was the same shape (top-level docs), and the fix is
the same: `weekly_release.build_bundle` now ships the newest table and its
sidecar under `experiments/`. When a serving or settle path reads a file, ask
whether the bundle carries it before the first cloud run needs it.

The second half: the ops-triage agent diagnosed the cause correctly on the
first night and then filed the same diagnosis five more times, one per unit
per tick, so an inbox with one defect read as sixteen. The driver now
fingerprints an operator task on kind + campaign + unit + phase (a triage
report's `trigger.race/stage/step` counts) and reuses an unresolved twin
instead of inserting; the run's `finish` step records `duplicate_of`.
## 2026-09-16 — An unresolved rider must not hold a settle hostage when nobody is watching

**Tag:** `keying` · Trofeo Matteotti, Okolo Slovenska

The 2026-09-08 ruling made the identity gate strict inside the top-15 stage /
top-20 GC places: a rider the roster could not match to a FirstCycling id
refused the whole capture and asked a human. That is the right call when a
human is there. In the unattended cloud tick there is nobody to ask, so the
race simply stopped. Trofeo Matteotti waited three nights over **one** rider
at rank 15 ("LOPEZ SEVILLA Diego Pablo", Team Polti); Okolo Slovenska waited
three nights over ranks 11 and 14 ("PAKOT Andras Gusztav", "KADLEC Milan").
Hosted tasks 70, 76 and 77. **Three settled races went unpublished to protect
one name in a result table nobody could read.**

The owner's ruling: settle and publish with a provisional `uci:` id and a
visible caveat; the weekly Mac reconcile fixes it durably. The general shape —
an unattended run should degrade to something honest and labelled, not to
silence — is the lesson; the switch is `--identity-policy
{strict,provisional}`, defaulting to `provisional` in the cloud and passed as
`strict` in the attended runbook.

What "honest and labelled" costs: the row keeps its place and time under a
provisional id, `crosswalk_top` becomes a warning, the page says "N riders in
the top 15 are shown under a provisional identity pending reconciliation" and
names them, the crosswalk proposal still reaches the inbox, and the task is
filed as `routine` rather than `blocks_settlement`. Downstream the provisional
rider is read as a rider who is **not in the model field** — `hindsight` and
`score_day_keys` drop the key before the riders-table join and score him
"unknown", and the frozen post-hoc field excludes him and records that it did.
Nothing pretends the identity is known.

The durable half had to be built: the weekly reconcile compared the archive
with FirstCycling but never rewrote it, so a confirmed alias left the
published id stale forever. `crosswalk reconcile-results --campaign <dir>`
now replaces confirmed `uci:` ids across `results.csv`, `gc.csv`,
`results.json` and `classifications.json`, idempotently, and only on a human
confirmation — a high-confidence proposal is exactly what the ingest already
declined to accept, so it must not rewrite a published result on its own.
## 2026-09-16 — A race no human prepared is a race the driver cannot run

**Tag:** `tooling` · Giro d'Abruzzo, Tour de Luxembourg, Okolo Slovenska, Tour of Huangshan

Four stage races died in one week at the same line, with hosted ledger tasks
66, 71, 72 and 78 to show for it: `preview` refused every stage race that had
no `predictions/TEMPLATE_scenarios.json`, and only the Vuelta ever had one.
The template was never judgment — it is stage number, date, label, void
stages and a tag convention, every field of which is already in
`campaign.json`. The same was true of `predictions/gc/scenarios.json`: the
settle step re-stamps a GC config it finds, so a race without one simply never
showed a general-classification board.

The driver now writes both (`cycling_project/nightly/autoconfig.py`). A stage
config comes from the campaign — `label` from the stage's towns and distance
when they are known, `"Stage N"` when they are not — with `odds_capture` and
`event_id` left absent, because most `.1` and `.Pro` races have no Kambi
market and an absent market is not an error. The GC config prefers this race's
own earlier editions and falls back to recent GC competitions when the
database holds fewer than three. Everything generated says so in the file
(`config_source`, `refs_source`, `refs_note`), so a page or a retrospective
can never present a machine-written config as a human read.

`scenarios_needed` survives for exactly one case: no
`experiments/selection_signatures_*.csv.gz` to query. That is not a judgment
gap, it is a missing artifact.

---

## 2026-09-16 — References are judgment about the KEY, so the key has to come first

**Tag:** `keying` · the same four races

The second half of the same gate was the reference sets. They *are* judgment,
which is why they were a human step — but they are judgment **about the day
key**, not independent of it: the key names the shape of the day, and the
references are the days worth averaging into a profile for that shape. The
driver had the order backwards, writing the config at step 2 and resolving the
key at step 5, so it had to ask a human for references before it knew what it
was asking about.

Preview now runs `day_key` and then `scenario_refs`. The chain is
deterministic: menu item → that item's canonical archetype-share signature in
`models/production/day_menu_v1.json` → a `refs.ARCHETYPES` filter → the five
most recent unspent matching days, this race's own earlier editions first,
then the campaign's own category tier. Frozen menu v1 gives
`bunch → bunch_sprint`, `res_3 → reduced_sprint`, `res_7 → punchy_select`,
`res_1 → small_group`, `res_2` and `gc_day → gc_from_two`,
`res_4 → mountain_break`, `res_6` and `res_0 → solo`, `itt → itt_like`.

One alternate board comes with it, and it is the key's second-weighted
**family**, not its second-weighted item — neighbours flip and families do
not (2026-08-09), so an alternate inside the leading family would bracket
nothing. A key of `bunch 0.6 / res_2 0.4` gets a mass-sprint main read and a
climbers-alone alternate; a key of `bunch 0.6 / itt 0.4`, both macro, gets no
alternate at all.

---
## 2026-09-16 — The cloud cannot learn about a new race by itself

**Tag:** `acquisition` · GP de Wallonie, Abruzzo, Luxembourg, Slovenska, Huangshan

`registry sync` creates a campaign from the calendar and nothing more: one
stage per calendar day, `stages_provisional: true`, `towns: null`,
`distance_km: null`, no start list, no route. The container cannot close that
gap — FirstCycling and PCS are behind Cloudflare, the UCI serves a calendar and
results but no field and no course, and Kambi lists WorldTour only. On
2026-09-15 GP de Wallonie's preview failed with "no start list from any
source", and Abruzzo, Luxembourg, Slovenska and Huangshan previewed with no
route or stage facts at all.

**A preview needs three things the cloud cannot fetch: the field, the stage
page, and the schedule.** They are all one rate-limited FirstCycling visit
away *on the Mac*, so the Mac takes it, daily, before the tick:

```bash
uv run python -m cycling_project.nightly.horizon --store auto
```

`cycling_project/nightly/horizon.py` (chip S) captures the start list into
`cached_start_lists` and `predictions/<unit>/startlist.json`, archives the
stage page verbatim for `route_facts`, fills `campaign.json`'s stage rows
under the chip-D provisional gate, and uploads everything as
`<run_id>/<campaign>/<relpath>` artifacts, which `bootstrap` overlays on the
next tick. Runbook §6a; scheduling in `agents/mac/README.md`.

Two things this cost, worth keeping:

- **`startlist.json` read as a rendered board.** `driver._has_scenario_boards`
  counts any `predictions/<unit>/*.json` outside `NON_BOARD_JSON` as a board,
  and the handover file was not in that set — so a unit that had only a start
  list looked already previewed and `plan` never listed it: the exact failure
  the capture exists to prevent. **Fixed 2026-09-16**: `startlist.json` and
  `horizon_raw.json` are in `NON_BOARD_JSON`, `horizon.has_boards` now just
  calls the driver's test, and `test_nightly_driver.py` pins a start-list-only
  unit as still preview-due. The preview upload still ships the file (its
  exclusion list is separate), so the cloud gets the field.
- **A capture scheduled after the tick is a capture the cloud sees tomorrow.**
  The tick is 19:45 UTC and this Mac runs on US Pacific, so the job is at
  10:30 local, not the late-afternoon slot a European clock would suggest.

## 2026-09-13 — A stage race's LAST stage keeps its overall classifications in a different accordion

**Tag:** `acquisition` · Vuelta stage 21

Stages 1 to N-1 each carry a "Stage General Classification" inside their own
results accordion entry. Stage N does not. On Vuelta 2026 the stage-21 entry
held only Stage, Stage Points, Stage Mountain and Stage Youth Classification,
while the race's final standings sat in a sibling entry labelled **"Final
Classification"** holding General Classification D2EV375983 plus the three
jerseys under their bare titles. `uci_acquire` only ever looked inside the
requested stage's entry, so `gc` came back "not in the results accordion for
this stage", the capture never reached complete, and `settle` exited 10.

**The final stage of every stage race was un-settleable from the UCI, for a
document the page was serving one entry away.** The same shape as the one-day
rule already in the code, which also reads its single result out of a "Final
Classification" entry.

Fixed by a fallback gated on `is_last_stage`, read off the competition
schedule rather than a campaign's stage count so a cancelled stage cannot
fool it. A mid-race stage must never read that entry or a stage-14 capture
would attach the race's final standings, and the stage result itself is never
taken from it. `cycling_project/tests/unit/test_uci_final_accordion.py` covers
both directions.

Second lesson from the same evening: the UCI was still serving that document
**empty** three hours after the finish. The fix resolves the entry; it cannot
conjure rows. The final classifications came from FirstCycling by the
supervised path, scoped with `--stage 21` so twenty settled archives were left
alone, with the UCI capture kept beside them.

## 2026-09-13 — The bunch macro grades winner-group SIZE, not winner TYPE

**Tag:** `keying` · Vuelta stage 21

Granada's closing circuit took a partly cobbled 2.1 km at 6.6% four times with
the last crest 7.8 km out. The read was that puncheurs, not pure sprinters,
would win — and it was right. The realised top fifteen came back sprint .20,
rolling .267, mountain .267, with a front-five classification median of 77th.
Matthew Brennan, who won four stages at this race, was fourth. Wout van Aert,
the book's favourite at 1.75, was sixty-fifth. The winner, Tobias Halland
Johannessen, was a climber lying 26th.

And the oracle said `bunch`, because forty riders finished on his time.

**Being right about who wins tells you nothing about the item. The macro is a
group-size question; composition is a different question with a different
answer, and a key that spends its weight on the composition read will be
covered rather than exact.** The punchy filter answered the composition
question well (van Aert retained 0.61 of his sprint-anchor probability,
Brennan 0.00) and that is still not what the key grades.

## 2026-09-13 — The closing-circuit time freeze is a Tour practice, not a grand tour one

**Tag:** `keying` · Vuelta stage 21

The stage-21 key put 0.35 on `bunch` rather than a minority weight, largely
because the last two Tour de France circuit finales — Montmartre 2025 and 2026
— both recorded **every** finisher on the winner's time, wg_prop 1.000. Under
a neutralised clock `bunch` is true by construction whoever wins, and van Aert
taking the 2025 edition still labelled mass_sprint.

Granada did not neutralise. Winner-group proportion was 0.282: forty riders
together, seventy-eight at 1:49, fourteen at 3:59. The road produced the split
honestly.

**The hedge was right and the argument behind it was wrong, which is worth
recording as plainly as a miss.** The Vuelta's own closing stages never froze
either (2019 wg_prop .634, 2022 .216, 2023 .324). Do not carry the Montmartre
precedent to another organiser's circuit; check wg_prop == 1.000 when settling
and let that, not the design of the day, decide whether a freeze happened.

## 2026-09-12 — A shared builder hardcoded to one campaign fails silently, not loudly

**Tag:** `tooling` · Vuelta stage 20

`build_stage_analysis.py` still had `PREDICTIONS_ROOT` and `RESULTS_ROOT`
pinned to `performance_eval/tour-de-france-2026`, months after
`predict_stage_scenarios.py`, `build_stage_page.py` and `build_gc_tracker.py`
were each made campaign-portable. Stage 20 was the first Vuelta stage to use
the analysis step, so the bug had never fired here before. It did not raise:
`standings_gc_pool` found a perfectly good `gc.csv` — the Tour's — matched ten
riders in it, printed "excluded 10 GC riders", and returned. The "If the break
goes" pool then held Mas, Gall, Roglic and Onley, and the book's card tagged
Carapaz "GC #8", his Tour placing, while the race leader read "free".

**A path constant that resolves to a real file on the wrong race produces a
plausible table, not an error. The tell is semantic: check that the excluded
riders are the ones you meant to exclude before you trust the pool.**

Fixed by `set_campaign_roots(config_path)`, resolving the campaign two levels
above the config's directory, with `cycling_project/tests/unit/
test_stage_analysis_campaign_roots.py` covering both the default and the
repoint. Nothing published was affected — no other Vuelta config carries an
analysis block — but the same class of bug is worth re-checking in
`build_review_dataset.py`, which is still TdF-only by construction.

## 2026-09-12 — A backfilled config must be marked `post_hoc` when it is written, not when someone notices

**Tag:** `scoring` · Vuelta stage 19

The 2026-09-05 lesson established that `post_hoc: true` stops the scorer
promoting a hindsight key into the tier-3 archive. Stage 19 showed the same
hole from the other side. Its config was drafted around the stage rather than
before it, carried no root `day_key` and no `post_hoc` flag, and two of its
scenarios carried their own `day_key`. `logged_key` fell through to the first
of them and scored `{res_2 .85, gc_day .15}` against an `res_4` oracle as a
genuine morning read — a fabricated MISS, on a day nobody keyed. The card read
16 keyed stages when the campaign had keyed 15.

**A scenario-level `day_key` is not a read. Any config written after its stage
started needs `post_hoc: true` in the same edit that creates it, because the
flag is the only thing standing between a draft scenario and the tier-3
archive — and the error is silent in both directions.**

Marking it post_hoc and rescoring restored the card to 15 keyed, 8 exact, 13
covered, mean weight 0.52, with stage 19 correctly unkeyed.

## 2026-09-12 — A post-hoc board's features are clean; the hindsight is in the operator

**Tag:** `tooling` · Vuelta stages 18 and 19

Worth recording because the natural assumption is the pessimistic one. When
the boards for two missed stages were rebuilt two days late, the runner
reported `Recomputed live form for 148 riders as of 2026-09-10` for the stage
18 config and `as of 2026-09-11` for stage 19, and attached race state through
stage 17 and stage 18 respectively. Form is re-aged to the config's own date,
not the run date, and state comes from the seeded cache through N-1, so the
model saw nothing from the stage it was pricing or from any stage after it.

**A late board is not feature-leaked. What it cannot have is an operator who
does not know the result — the hindsight lives in the choice of scenarios and
in the prose, so that is what the `post_hoc` note should say.** Claiming a
form leak that the logs disprove is its own kind of inaccuracy.

## 2026-09-08 — This ledger and the generic runbook do not ship in the release bundle

**Tag:** `tooling`

The release bundle's code zip is `git archive HEAD -- . :(exclude)models
:(exclude)performance_eval`, and its campaign group walks
`performance_eval/<campaign>/` directories only. Files sitting directly in
`performance_eval/` — this ledger and `DAILY_RUNBOOK.md` — are in neither
group, so a hydrated cloud container has the campaign runbook stubs but not
what they point at. That is harmless today (both are human documents and the
cloud path is the driver, not the prose), but a stub in the container is a
dead link. If an agent ever needs to read the runbook, add the two files to
`weekly_release.build_bundle` rather than copying them back into the campaign
directories.

## 2026-09-06 — One team owning both the sprinter and the puncheur breaks the chase-incentive test

**Tag:** `keying` · Vuelta stage 15

The same-race sprint ledger was falsified on the sixth sprint-flavoured day.
Visma held both the sprint favourite (Brennan) and the strongest escape
candidate (van Aert), so "who has a reason to chase?" returned Visma twice
over. A team that can win either shape chooses the one its preferred rider
wins: on a 40 °C day fifteen stages in they rode Artafi to launch van Aert,
not to thin the field for Brennan.

**When one team owns both the fastest man and the best puncheur, the
incentive test does not decide the family — the team's preference does, and a
team riding the last climb hard is telling you.**

Keyed bunch .55 / res_3 .30 / res_1 .15 against oracle res_4: not covered.
Scorecard after the stage: 6/13 exact, 11/13 covered, mean 0.48. The branch
board (`break_survives`, res_4 .45) had van Aert first and retrieved 3 of 15.

## 2026-09-06 — An organiser can redraw a stage after the market and the boards are done

**Tag:** `acquisition` · Vuelta stage 15

The stage was cut from 189.7 km to 110.2 km mid-afternoon under the
extreme-heat protocol, after the odds, config and boards had been built the
evening before on the 2026-09-05 17:20 snapshot. Route facts came from
lavuelta.es (the climbs) plus the organiser statement; FirstCycling had only
the distance.

If an organiser modifies a stage again: write
`predictions/stage_NN/route.override.json` with the corrected numbers and a
`reason`, run `nightly route_facts ingest-route`, re-capture the market once
it re-prices, and re-run the boards with `--no-log`.

## 2026-09-06 — UCI is the primary results source; ProCyclingStats now blocks Anthropic's fetcher

**Tag:** `acquisition`

PCS moved behind a Cloudflare wall that also refuses Anthropic's `web_fetch`:
every fresh PCS URL answers `url_not_accessible`, where the same tool made 18
successful fetches in August. The §2.8 PCS-via-`web_fetch` acquisition path is
dead until re-verified. **Do not probe PCS further** — rate limits.

The UCI website is open: the competition page answers plain `requests` with no
cookies or browser, and its `CompetitionDetailsModule` `data-props` JSON lists
every classification with an `eventCode` that the results API turns into a
complete table. Vuelta stage 14 came back with 155 entries and gaps identical
to the FirstCycling archive. UCI carries no rider id, team id, bib or full
birth date, so `uci_identity.py` bridges names to FirstCycling ids inside the
campaign roster and refuses to guess: nicknames, homonyms, fuzzy similarity or
age alone become a crosswalk proposal and an operator task, never an
acceptance.

A campaign's `uci_competition_url` comes from `uci_calendar resolve`, never
from a guess: an exact date range with name similarity ≥ 0.90 and no rival
candidate, or the field stays null and a human confirms. A one-day race
publishes one classification titled "General Classification" under an
accordion entry labelled "Final Classification" — that single document is the
race result and no `gc.csv` is written.

## 2026-09-05 — The launchpad check is subordinate to the composition of the move

**Tag:** `keying` · Vuelta stage 14

The key went `gc_day` 0.6 on the argument that the first categorised climb at
km 80 gave a break too little road. The break went on flat roads in the first
hour: 44 riders, every team represented, and Movistar — the leader's team —
with two men in it. It was given seven minutes.

**Before keying `gc_day` on a mountain day, ask whether the red jersey's team
will have riders up the road. If yes, nobody chases and it is `res_2`.**

Scored covered at 0.40; scorecard 6/12 exact, 11/12 covered, mean 0.53.

## 2026-09-05 — Incentive predicts whether the GC group races, not whether the break is caught

**Tag:** `keying` · Vuelta stage 12

The GC group did race — Mas took 27 s on Roglič, Gall and Carapaz — and the
escape was never threatened, because it had gone on the early slopes of a
4,568 m day whose climbing started at km 7.7.

**Add a launchpad check to the key: how early does the categorised climbing
start?** Stage 14's first categorised climb at km 80 is why `gc_day` took the
majority there despite the market leaning break. Read this entry together with
the 2026-09-05 lesson above, which bounds it: the launchpad check loses to the
composition of the move.

## 2026-09-05 — A road book can overrule the working read

**Tag:** `keying` · Vuelta stage 14

The working read was "not a super hard day, probably not a shattered GC
finish". The road book said 154.5 km and **4,338 m**, virtually no flat — the
same order as Calar Alto's 4,568 m — finishing on the Sierra de la Pandera:
11.4 km at 7.2 %, two kilometres of double-digit gradient from 4.5 km to go, a
15 % ramp at the flamme rouge, pitches to 21 %, in 40 °C. It is the steepest
finish of the race and has moved the GC every time it has been used since
2002. The key departed from the working read on those numbers.

## 2026-09-05 — `post_hoc: true` or the scorer promotes a hindsight key into the tier-3 archive

**Tag:** `scoring`

`logged_key` falls back to the first scenario carrying a `day_key` when the
config root has none. A backfill file containing only a hindsight scenario
would therefore have had that key promoted into the tier-3 archive and scored
as a fabricated exact. `score_day_keys` now honours `post_hoc: true`, and
**any config written after its stage started must set it**. Verified on stage
13: it stays unkeyed and the record stays at 11 keyed stages.

## 2026-09-05 — The winner-inside-GC-top-10 clause mislabels a breakaway rider who banked time

**Tag:** `scoring` · Vuelta stage 12

Omrzel won from the escape with the GC group three minutes back — a mountain
escape by any human reading, realised composition mountain .47 / rolling .40 —
but he sat tenth on GC overnight, so the oracle's "winner inside morning GC
top-10" clause stamped it `gc_day`. The key scored covered at 0.45 on a
labelling artifact. It is the inverse of the stage 2–4 problem: then the
top-10 was contaminated by sprinters, here by a breakaway rider who had banked
time. Scorecard at that point: 6/11 exact, 10/11 covered, mean weight 0.54.

## 2026-09-05 — The runner's `top-8:` line is the board's top eight, not the top eight prices

**Tag:** `scoring`

`records` is sorted by `daymenu_rank` when the day-menu channel is active
(`predicted_rank` otherwise), the line takes `records[:8]`, and only then
sorts that slice by blend for display. On most stages the board and the prices
agree, so the two readings coincide; on a `res_2`-keyed board they diverge
sharply — the stage-13 post-hoc printed Johannessen at 2.4 % at the head while
the highest-priced rider on that board was Roglič at 13.5 %.

**Quote it as "the board's top eight, with prices", and take probability
rankings from the JSON.**

## 2026-09-05 — A missed day cannot be recovered

**Tag:** `scoring` · Vuelta stages 12 and 13

Stage 12 had boards and can be judged. Stage 13 has none — no odds, no key, no
boards — so its retrospective is a report plus a post-hoc board with empty
book columns, and it is worth very little.

## 2026-09-05 — Backfilled GC checkpoints reconstruct the classification, not the read

**Tag:** `scoring`

GC checkpoints for stages 12 and 13 were backfilled on 2026-09-04 by seeding
the state cache through stage 12, running GC, then seeding 13 and running
again — the tracker keys one checkpoint per `state_through_stage` count. The
standings are exact, but the live-form features are as-of the run date. These
are reconstructions of the classification, not of the reads we would have had
on the night. Label them as such.

## 2026-09-05 — Join on rider ids; FirstCycling names drift

**Tag:** `tooling`

`Martin-Guyonnet Guillaume` on FirstCycling is `Martin Guillaume` on the
boards, and settlement by normalised name reports him as NOT ON BOARD. Other
known drift: `Gee` → `Gee-West`, `Plapp Lucas` / `Plapp Luke`. Join on rider
id everywhere — in the driver, in settlement, in archived CSVs.

## 2026-09-05 — `--all` is mandatory on the daily results capture

**Tag:** `tooling`

Without it, `capture_results.py` stops at the first stage with no results and
silently skips everything after it.

## 2026-09-05 — Every config on a race must carry that race's `void_stages`

**Tag:** `tooling`

The Vuelta's stage 3 was cancelled, so every config on that campaign carries
`"void_stages": [3]`. A config that omits it desynchronises the GC tracker and
the key scorer from the calendar.

## 2026-09-05 — Cancelled-stage protocol

**Tag:** `tooling`

Mark the stage config `"cancelled": true` with a reflection, add the number to
`void_stages` in `campaign.json` and in every later config, capture with
`--all`, rebuild the pages.

Related database behaviour (2026-08-09): a settled race with a cancelled stage
is exempt from the staleness and incompleteness rules. FirstCycling publishes
no GC when a short race loses a stage, so a result-less past-dated stage in a
settled race is legitimately empty; before the exemption, eight races —
including Vuelta a España 2025 — were deleted and re-migrated every pipeline
run, churning competition ids.

## 2026-09-05 — Hindsight reference sets come from the signature table

**Tag:** `tooling`

Query `experiments/selection_signatures_*.csv.gz` (working-group size, winner
margin, `frac_120s`, top-15 archetype shares) joined to `competitions`, and
exclude every reference already used in the campaign. This is now the driver
command `nightly refs --archetype <name> --campaign <dir>`; `--list` shows the
archetypes.

The older hand-rolled path is still the fallback when no archetype fits: count
the finishers within 0/5/30/60/120/600 s of the winner in `results.json`, then
find the database stages with the closest weighted gap curve. Substitute those
six counts for the target numbers in the query:

```sql
WITH curves AS (
  SELECT c.id, r.name || ' ' || r.year || ' ' || c.name AS comp,
    SUM(rr.time_gap<=0) w0, SUM(rr.time_gap<=5) w5, SUM(rr.time_gap<=30) w30,
    SUM(rr.time_gap<=60) w60, SUM(rr.time_gap<=120) w120, SUM(rr.time_gap<=600) w600,
    COUNT(*) n
  FROM competitions c JOIN races r ON r.id=c.race_id
  JOIN rider_results rr ON rr.competition_id=c.id
  WHERE c.competition_type='stage' AND r.year>=2021 AND r.category='wt'
    AND rr.time_gap IS NOT NULL GROUP BY c.id HAVING n>=120)
SELECT id, comp, w0,w5,w30,w60,w120,w600,
  ((w0-4)*(w0-4)*4.0 + (w5-13)*(w5-13)*2.0 + (w30-17)*(w30-17)*2.0
   + (w60-26)*(w60-26) + (w120-37)*(w120-37)*0.5 + (w600-68)*(w600-68)*0.1) dist
FROM curves ORDER BY dist LIMIT 10;
```

The weights emphasise the front of the race; do not overthink them. Sanity-check
the matches by pulling their winners and profile scores — they should look like
the kind of rider who won today.

## 2026-09-05 — `load_book` tolerates a missing market

**Tag:** `tooling`

It returns an empty book instead of raising when `odds_capture` or `event_id`
is absent, which is what a backfill board on a day whose market was never
captured needs. Stage 13 has no market at all.

## 2026-09-05 — A mid-race race-page archive is a DNF board, not a standing

**Tag:** `acquisition`

Mid-race, FirstCycling's race page serves only the DNF board at race level
(rows with `place='DNF'` and FirstCycling rider ids). The real standing is the
per-stage `results/stage_NN/gc.csv`. In the database, a `gc` competition is
created from classified rows only.

## 2026-09-05 — The FirstCycling race page 403s during serving runs

**Tag:** `acquisition`

Expected under load. State resolves from the seeded cache instead, so keep
seeding each evening (`seed_state_cache.py` after every results capture). The
origin also returned 503s under Tour load in July with the Cloudflare
challenge clearing and no page behind it; the daily cycle still ran, off state
through stage N−1 with `SCRAPER_USE_BROWSER=0`.

## 2026-09-05 — Kambi brand fallback and degraded mode

**Tag:** `acquisition`

Brands are tried in order (`ubnl,ubuk,ubse,rivers,rsiuspa`) and the serving
brand is recorded in `provenance_*.json` and in the CSV's `brand` column.
Checked live on 2026-09-05 from a US residential connection with no VPN:
`ubnl`, `ubuk` and `ubse` all served the full Vuelta feed with identical
prices, differing only in market labels. `rivers` answered HTTP 429 for every
lang/market tried and no `na-*` Kambi host resolves, so BetRivers is reachable
only through its per-state codes; `rsiuspa` and `rsiusil` served the same
events from the same EU host.

When every brand blocks, the run writes `odds/<day>/degraded.json` and exits 0
— a bookless day is recorded, not a crash, and the model board is unaffected.
When a brand answers but the race is not in it, the run exits 1 and writes
fuzzy `kambi_candidates` into `campaign.json` for a human to confirm; nothing
below the 0.95 threshold is ever accepted automatically. The NL feed localises
names — the Vuelta is "Ronde van Spanje 2026" — and the capture matches both
the localised name and `englishName`. `--match` **overrides** the campaign's
own names rather than adding to them.

## 2026-08-21 — The shared capture scripts silently default to the Tour

**Tag:** `tooling`

`seed_state_cache.py` was hardcoded to FirstCycling race id 17 and the Tour
archive; without `--race-id / --year / --out-root` it would seed Tour state
into a Vuelta run and say nothing. It is parameterised now, but the defaults
are still the Tour's. The same applies to `capture_results.py` (`--race-id`
defaults to 17). `predict_stage_scenarios.py` and `build_stage_page.py` now
resolve `odds_capture`, results and predictions against the config's own
campaign directory, and `build_gc_tracker.py` takes the GC config path, so a
second race publishes alongside the first.

## 2026-07-24 — Data snapshots are tracked; the deploy is manual

**Tag:** `publishing`

Odds, results and the prediction JSONs are committed alongside the configs,
scripts and pages as of commit `09ff18a`. Only raw scraped HTML is ignored
(`stage_page_*.html`, `race_page_*.html`, `odds/**/raw/`), so a plain
`git add netlify_site` also picks up any stray file in that folder — check
`git status` before committing.

**The push publishes nothing.** Deployment is a separate manual step.
Cloudflare is the public surface today (Workers Builds on the `site` branch,
or `wrangler deploy`); the Tour-era instruction was to drag `netlify_site/`
onto app.netlify.com. Pages built by the cloud nightly are staged under
`site-staging/<run_id>/` and promoted by a Mac step holding a key the
deployment does not have.

## 2026-07-15 — Kambi's stage-event naming drifts

**Tag:** `acquisition`

The stage event is sometimes English ("Stage N (…") rather than localised, and
has shipped with the closing paren dropped ("Stage 12 (Tour de France 2026"),
so a `--match "(tour de france 2026)"` skips it. Rerun with a looser match (no
parens — that still excludes the Femmes race, whose "Femmes" breaks the
substring), and grep the raw `listview_*.json` for the stage event id if
unsure.

## 2026-07-14 — A break read on a flat day needs the mirror-image filter

**Tag:** `keying` · Tour stage 11

`exclude_top_gc` is close to a no-op on a flat day: the sprinters sit around
130th on GC, so no GC cut touches them, and the men an escape has to beat home
are precisely the sprinters. So the break scenario adds
`"exclude_sprinters": true`, and the `punchy_filter`'s `selective_scenario`
must be a **hidden rolling anchor** — reuse stage 9's break-day references
`[2098, 321, 158, 9749, 9744]` — rather than one of the day's own readings:
a hilly or reduced-sprint read will not collapse the sprinters (high hilly
keeps them on top) and therefore cannot classify. Set `"emit_pool": false`:
block 1 already is the sprinters-removed pool on such a day, and the "punchy
non-climber" prose of block 3 would simply be wrong. Run the hidden anchor
separately with `--only anchor_selective --no-log`.

## 2026-07-14 — `blend_win_p` is not a distribution

**Tag:** `scoring`

It is a set of per-rider marginals and sums to well over one book: 136 % on the
stage-11 flat read, 156 % on the reduced-sprint read, 180 % on the GC board.
The devigged book sums to exactly 100 %. Putting the raw blend next to the book
column **systematically flatters the model**, and the page's "Max edge" is
inflated for the same reason. Renormalise over the field (`p / sum(p)`) before
claiming any edge in prose. The only natively book-preserving head is
`lambdarank_win_p` (sums to 1.000 by construction). The GC outlook head is
per-rider too — read it as position-safety, not odds. `gc.html` prints its own
blend mass in the caption so the comparison is labelled honestly; the stage
boards do not.

## 2026-07-12 — Prefer actual standings to the model blend for the GC pool

**Tag:** `keying` · Tour stage 10

Once the race has real structure, use `"exclude_top_gc": 10,
"exclude_gc_source": "standings"`: the pool becomes the top-N of the actual GC
from the newest `results/stage_NN/gc.csv` instead of the GC-model blend. Model
ranks in the 8–20 zone are noise-ordered (about 0.2–1 % blend each) and
imprison the wrong riders — on stage 10 the model pool held Pidcock, 9:40 down
on the road, while freeing Lenny Martinez at 4:21. Pick N at the standings
cliff (after stage 9 it was four minutes between GC ninth and tenth); riders
below it are far enough back to be given freedom. The default stays the model
blend, so pre-standings stages and old pages rebuild unchanged.

## 2026-07-12 — `state_through_stage` is a count, not a stage number

**Tag:** `tooling`

It counts the stages that fed the state. With any entry in `void_stages` the
count and the calendar stage diverge for the rest of the race — the Vuelta's
void stage 3 makes count 6 mean "after stage 7". The GC tracker maps the count
back through `void_stages` before pulling that evening's `gc.csv`. Reading it
as a stage number shows the wrong podium.

## 2026-07-11 — The punchy filter, for a selective day won by a fast hard-man

**Tag:** `keying` · Tour stages 4 and 9

There is a day shape with no scenario read: "selective enough to shed the pure
sprinters but won by a fast hard-man" — the stage-4 day, where Pedersen wins
and Philipsen is dropped. High hilly keeps pure sprinters on top; rolling plus
mountain buries all fast men equally.

Stage 9 is the template for handling it. Add a `"hidden": true` scenario
`anchor_sprint` with the flat archetype references `[2095, 2097, 145, 150,
9741]`, run it separately with
`--only anchor_sprint --no-log` (it is a classification input, not an opinion —
never logged, never rendered), and add a top-level
`"punchy_filter": {"sprint_anchor": "anchor_sprint", "selective_scenario":
"<break-read key>", "anchor_floor": 0.01, "retention_max": 0.08}`. Each rider
with anchor probability at or above the floor is classified by **retention** =
selective-read p / anchor p. Pure sprinters collapse (Merlier, Kooij,
Philipsen, Girmay all at or below 0.06 on stage 9); punchy fast men retain
(Pedersen 0.22, Matthews 0.10, Van der Poel 0.45). The 0.08 threshold sits in
the empirical gap. The punchy-pool block renormalises every visible read over
the field minus the GC pool minus the pure sprinters, giving
P(win | winner is a punchy non-climber). It is presentation-only, like
`exclude_top_gc`: eyeball the printed diagnostics and adjust `retention_max` if
a name lands on the wrong side — rerunning the analysis step is cheap and
needs no model rerun.

## 2026-07-11 — The grand-tour hard-day hole is the standing design gap

**Tag:** `keying`

Shattered non-mountain days won by punchy non-climbers, from breaks, late
moves or reduced hard-men sprints. Mountains and sprints are solved; this class
is not. Tour stages 4 and 9 are the canonical cases. The settled stages are the
labelled corpus: label each day's finish shape from the gap curves, score every
read's winner pricing from the reflections, and check the punchy-pool hit rate
on the hard days. Structural constraints (grand-tour startlists carry no
per-stage signal; per-slot edition history is dead) and candidate directions
(break-membership model, per-rider group ladders, within-grand-tour
day-character priors) are in the memory note `gt_hard_day_design_hole.md`.

## 2026-07-06 — A break read must carry `exclude_top_gc`

**Tag:** `keying`

The model prices rider-course fit, not break formation or team tactics. On a
true break day its raw board is the "break gets caught" branch, so GC stars sit
on top because they fit the terrain. A break-read scenario therefore carries
`"exclude_top_gc": N`: the page drops the top-N GC contenders and renormalises
the rest into "if the break wins" odds across the cards, the board column and
the hub pick. It is presentation-only and never touches the logged prediction
or the settlement. `build_stage_analysis.py` reads the same value (falling back
to 24, overridable with `--gc-exclude N`) — keep the flag and the analysis
block in agreement so the table and the scenario board tell the same story.

## 2026-07-05 — Model-space semantics are not intuitive

**Tag:** `keying`

- High `race_hilly_score` = a classics day ending in a **reduced bunch
  sprint** (sprinters up, GC men down). It is not a puncheur read.
- Puncheur and selective days = rolling 0.4–0.6 with mountain 0.2–0.4.
- Breakaway-won mountain days = rolling about 0.55 with mountain about 0.45.
- `race_breakaway_score` does **not** mean "the break wins". Montjuïc circuits
  score 0.33 on it; actual break-won stages score about 0.

Build a scenario from 4–6 real database competition ids whose stages embody
the reading (checking their profile scores in `competition_field_features` for
coherence first), or from synthetic `"scores"` over `"base_refs"` summing to
about 1.

## 2026-07-05 — A truncated FirstCycling results page is fixed by rerunning

**Tag:** `acquisition`

"No stage selector found", or 0 results archived, means FirstCycling served a
truncated page. Rerun; a retry has always worked. The browser client's
`<body>` check makes a stuck run rare.
