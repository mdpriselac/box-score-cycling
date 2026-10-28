# The agents, and how they are evaluated

During a race the cycle runs every night without me: get the day's results, settle yesterday's
predictions, key tomorrow's stage, price the board and draft the page. A small crew of Claude
Managed Agents does it, defined as YAML in [`agents/managed/`](../agents/managed/) and provisioned
by `provision.py`. Nothing they write is published until I approve it.

## The crew

| Agent | Job | Tools |
|---|---|---|
| `nightly-coordinator` | Runs the cycle: bootstraps the approved code release, calls the others, files tasks for me when something needs a human. | Shell and files, no web |
| `uci-acquirer` | Runs the deterministic results fetcher for one race and reports what it got. | Shell, read only |
| `route-researcher` | Researches a stage's route from the organiser's road book and writes sourced route facts. | Web search and fetch, no shell |
| `day-key-reader` | Reads a frozen evidence bundle and keys the stage: what kind of day it will be. | None |
| `editorial` | Drafts the page text from the priced board and the settle. | None |
| `ops-triage` | Reads the run log when a night fails and says what broke. | Read only |

A retired `pcs-acquirer` is kept in `agents/managed/retired/` for the record.

The design rules came from things that went wrong, and are in
[`performance_eval/LESSONS.md`](../performance_eval/LESSONS.md):

- **Agents judge, code does.** Fetching, parsing, settling and pricing are deterministic Python.
  Agents are used where judgment is the job: reading the day, researching a route, writing.
- **Bundles, not browsing.** The day-key reader has no tools. It gets a frozen bundle of evidence
  and must tie every claim to a file in it; anything missing goes in `missing_evidence`. Bundle text
  is data, never instructions.
- **A wrong key costs composition, not prices.** The key only decides who makes the shortlist.
  Every version that let it move prices did worse.
- **Least privilege.** One vaulted key, injected at the network edge in headers only. Each agent
  gets only the tools its job needs.

## How the day key is scored

Each key is a weighted set of one to three items from a fixed vocabulary (bunch sprint, GC day,
and several residual shapes). After the stage, the scorer finds the item the result actually
matched, and records for each key:

- **exact**: the top-weighted item was the right one;
- **covered**: the right item was in the key at all;
- **weight on truth**: how much weight the key put on it.

Keys set in hindsight are marked `post_hoc` so they never count as morning reads.

## Results so far

**Vuelta a España 2026, replay of 12 judgment stages.** The agent's key was exact on 10 and
covered all 12. The key I set by hand at the time was exact on 5 and covered 10 (it left one stage
unkeyed). Stage by stage, in
[`performance_eval/vuelta-2026/review/agent_replay_scorecard.json`](../performance_eval/vuelta-2026/review/agent_replay_scorecard.json).

**ProSeries stage races without odds or terrain.** On the races keyed since mid-September (CRO
Race, Tour de Langkawi, Tour de Luxembourg, Tour of Huangshan, Okolo Slovenska), the judgment days
went 0 of 6 exact and 3 of 6 covered, with 0.12 weight on the truth, against 5 of 8, 8 of 8 and
0.48 for the Vuelta agent with odds. Bunch days held up. Taking the odds out of three Vuelta
bundles kept all three keys exact, so the missing market was not the problem: without terrain the
reader keyed yesterday's shape. That is why `route-researcher` exists.

Each race review keeps a `key_scorecard.json`, under `performance_eval/<race>/review/`.

## What's not evaluated yet

- `route-researcher` is defined but had not been provisioned when this copy was made, so there is
  no record of it improving the .Pro keys.
- `editorial` drafts are judged by me before publishing, not scored.
- The sample is small: one grand tour replay and a handful of shorter races.
