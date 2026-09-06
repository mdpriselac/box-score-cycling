# Managed Agents provisioning — the nightly cloud deployment

The control plane for `NIGHTLY_AGENT_WORKFLOW.md` rev 4 (§1, §1a, §2.3): one cloud environment,
one vault with one vaulted key, five agents, one paused scheduled deployment. Everything here is
version-controlled YAML applied by `provision.py`; `ids.json` records what was created.

```
agents/managed/
  environment.yaml            cycling-cloud: limited networking (Supabase host + Kambi host), PyPI allowed
  vault.yaml                  vault cycling-nightly + ONE environment_variable credential SUPABASE_NIGHTLY_KEY
  deployments.yaml            deployment "nightly": 45 19 * * * UTC, $12.00 budget, created PAUSED
  agents/*.agent.yaml         nightly-coordinator, pcs-acquirer, day-key-reader, editorial, ops-triage
  prompts/*.md                system prompts (coordinator, acquirer, ops-triage); the two no-tool agents
                              use agents/skills/*/SKILL.md directly
  stage0.sh                   the pre-code bootstrap the coordinator writes and runs in the container
  provision.py                create-or-update by name; ids.json out
  smoke_test.py               the paid smoke session (README §4)
  ids.json                    ids + versions written by provision.py (no secrets)
```

## 1. What is provisioned (workspace `wrkspc_01EXAMPLEA458FB52026846A`, org "MDP Experiments")

| Resource | Name | Notes |
|---|---|---|
| Environment | `cycling-cloud` | `type: cloud`; `networking.limited` with `allowed_hosts` = `your-project-ref.supabase.co`, `eu-offering-api.kambicdn.com` (chip F: one Kambi host covers ubnl/ubuk/ubse/rsiuspa/rsiusil; `rivers` is dead); `allow_package_managers: true`; pip packages `uv`, `beautifulsoup4`, `requests` preinstalled. `networking` does **not** govern `web_fetch`. |
| Vault | `cycling-nightly` | one credential: `environment_variable` `SUPABASE_NIGHTLY_KEY`, `networking.limited` to the Supabase host, `injection_location: {header: true}`. The sandbox sees an opaque placeholder; the real key is substituted at egress, in headers only. |
| Agent | `nightly-coordinator` | `claude-opus-5` effort high; agent toolset minus `web_fetch`/`web_search`; `multiagent` roster `[self, pcs-acquirer, day-key-reader, editorial, ops-triage]`; prompt = `prompts/nightly-coordinator.md` with `stage0.sh` inlined. |
| Agent | `pcs-acquirer` | effort low; `web_fetch` (`allowed_domains`: procyclingstats.com, www.procyclingstats.com, lavuelta.es, giroditalia.it — `letour.fr` is rejected by the API because the site blocks Anthropic's crawler, so Tour organiser pages need operator upload) + `write` + `read` only. Derived from the user's `agent_01EXAMPLE466A1EFA1DEDA25` "Procycling Stats Extractor" — fetching rules and DOM notes kept, parsing/JSON duties removed. The original agent is untouched (`PROTECTED_AGENT_IDS`). |
| Agent | `day-key-reader` | no tools; system = `agents/skills/day-key-read/SKILL.md`. |
| Agent | `editorial` | no tools; system = `agents/skills/editorial/SKILL.md`. |
| Agent | `ops-triage` | `read`/`glob`/`grep` only; prompt = `prompts/ops-triage.md`. |
| Deployment | `nightly` | agent pinned to the coordinator version, `environment_id`, `vault_ids`, cron `45 19 * * *` UTC, `budget` `$12.00` (`"1200"` cents), `initial_events` = one `user.message` "Run the nightly cycle.", **paused**. No `github_repository`, no `file` resources. |

Every resource carries `metadata.spec_sha256`; provision.py skips a resource whose stored hash matches
the rendered spec, so re-running it is a no-op. Agents are updated by version (`--version` optimistic
lock); nothing is ever archived by this tooling.

### How the container gets code (no repo resource)

The container starts empty and holds no git credential. The coordinator writes `stage0.sh` from its
system prompt and runs it: it `curl`s the newest **approved** row of `releases` (PostgREST, header
auth with the vault placeholder), downloads `releases/<tag>/code-<sha>.zip` from Storage, unzips it
into `/workspace/cycling`, `uv sync`s, and `exec`s `cycling_project.nightly.bootstrap --dest
/workspace/cycling`, which verifies every bundle file by sha256, checks the model contract, hydrates
the campaign dirs and writes `nightly_env.sh` (exports `CYCLING_DB_PATH` → the inference slice).
Until a release is uploaded and approved (chip B's `weekly_release.py`, then `releases.approved`
flipped by a human), stage 0 exits 3 and the coordinator stops with a summary.

## 2. Credentials on the Mac

* **Anthropic:** `ant auth login` profile (default). `provision.py` and `smoke_test.py` deliberately
  drop `ANTHROPIC_API_KEY` from the process environment unless `--api-key` is passed: the key in
  `secrets.env` is scoped to a *different* workspace (`wrkspc_01NsRD…`) and cannot see the existing
  agent. The profile token refreshes itself; if `ant` starts failing auth, `ant auth login` again.
* **Supabase:** `SUPABASE_NIGHTLY_KEY` (the `nightly_agent` role JWT, `supabase/README.md` §4) is
  read from `~/.config/cycling-project/secrets.env` via `cycling_project.nightly.secrets.load_local_env`
  at provision time and sent write-only to the Vaults API. It is the only Supabase key that may be
  vaulted; `provision.py` refuses if its value equals `SUPABASE_SECRET_KEY` or any other
  operator-only secret, and a leak check refuses to send any rendered document containing a secret
  value. `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` (public by design) are rendered into the
  coordinator's system prompt; they are never in git.

## 3. Provisioning

```bash
uv sync --group agents
uv run --group agents python agents/managed/provision.py --dry-run   # render + plan, no API calls
uv run --group agents python agents/managed/provision.py             # apply; writes ids.json
```

Order: environment → vault + credential → leaf agents → coordinator (roster pinned to the leaf
versions just applied) → deployment (pinned to the coordinator version; `create` is followed by
`pause`; an `update` never changes the pause state). Flags: `--force` re-applies matching hashes,
`--only {environment,vault,agents,deployment}`, `--rotate-key` (below), `--workspace-id`.

The same YAML can be applied with the CLI (`ant beta:agents create < …`, `ant beta:environments
create < environment.yaml`) after stripping the provision-only keys (`system_file`,
`strip_frontmatter`, roster names, `secret_value_from_env`, `budget_usd`); provision.py exists so
those resolutions happen in one place.

**Console.** Everything is visible at https://platform.claude.com → workspace *MDP Experiments /
wrkspc_01EXAMPLEA458FB52026846A*: Agents (five + the untouched extractor), Environments
(`cycling-cloud`), Vaults (`cycling-nightly`, credential metadata only — the value is write-only),
Deployments (`nightly`, paused, next fire times listed), Sessions (one per fired or manual run, with
the full transcript, per-thread view and list cost). Deep-link a session:
`https://platform.claude.com/workspaces/wrkspc_01EXAMPLEA458FB52026846A/sessions/<session_id>`.

## 4. Smoke test (costs money — user approval first)

```bash
uv run --group agents python agents/managed/smoke_test.py --budget-usd 5     # asks y/N, then streams
```

Starts one coordinator session (agent version from `ids.json`, the environment, `vault_ids`, a $5
cap) whose message asks for: (a) a `curl` of `releases` through PostgREST with the placeholder in
`apikey`/`Authorization` (egress substitution) and a `PATCH` that must be rejected (role), plus
`rpc/whoami`; (b) stage 0 with `--manifest-only`, or a listing of the `releases` bucket when no
approved release exists; (c) a delegated pcs-acquirer fetch of the Vuelta 2026 stage 14 result page
saved to `/mnt/session/outputs/stage14.html` + `pcs_raw.json`; (d) `git` absent / no remote. The
script streams events, prints the Console URL, saves `transcript.json`, `session.json`,
`threads.json` and every output file under `performance_eval/runs/smoke_<stamp>/`, parses the saved
HTML with BeautifulSoup per the DOM map (`ul.resultTabs li.cur` ↔ `div.resTab[data-id]` →
`table.results`, `td.ridername a[href^="rider/"]`, `,,` = same time, `|` split time) and diffs
place / name / gap against `performance_eval/vuelta-2026/results/stage_14/results.csv`, reporting the
match rate and any HTML-fidelity loss (`looks_like_html`, `has_results_table`, `content_kind`).
`--session-id sesn_…` re-collects an existing session; `--parse-only file.html` runs the parse + diff
offline; `--via-deployment` uses `deployments.run` instead (that fires "Run the nightly cycle."
first, then the smoke message — more expensive, exercises the deployment object itself).

### Result of the first run (2026-09-06, `sesn_01EXAMPLE14E2A253E7954F1`, $0.58 list)

| Check | Result |
|---|---|
| (a) egress substitution + role | **PASS** — `GET /rest/v1/releases` 200 (`content-range: */0`), `PATCH` 403 `42501 permission denied for table releases`, `rpc/whoami` → `nightly_agent` |
| (b) release bundle | stage 0 exit 3 (no approved release: table and bucket both empty, both readable) — expected until chip B uploads and a human approves a release |
| (c) PCS acquisition | **FAIL** — `web_fetch` → `url_not_accessible` (two attempts). A Messages-API `web_fetch` against a 2025 PCS stage page fails identically, so PCS (Cloudflare) now blocks Anthropic's fetcher as it blocks plain clients. Cross-check against the archived 2026-08-30 sessions of the extractor agent: the same `agent_toolset_20260401` `web_fetch` made 18 successful PCS fetches then (results, GC, KOM, points, embed widgets, startlist); on 2026-09-06 every fresh PCS URL fails (result pages, GC, startlist, race overview, embed widgets, bare and `www.` hosts), and the one URL that still returned content was one fetched in August, i.e. served from the fetcher's cache. **Do not probe PCS further** — rate limits and the block itself are the user's concern. The August verification no longer holds; §2.8 needs a new acquisition path (e.g. Mac-side headed-Chrome capture uploaded to `nightly-artifacts/`). The acquirer behaved correctly: no HTML, no counts, no timestamp fabricated; `pcs_raw.json` records the error. |
| (d) git | **PASS** — binary present, no repository under `/workspace`, no remote |

Container facts: `uv` and `python3` 3.11 preinstalled (the pip fallback in stage 0 was not exercised); the sandbox user writing `/mnt/session/outputs` is `claude`. Artifacts: `performance_eval/runs/smoke_20260906T212323Z/` (transcript, session, threads, outputs).

## 5. Operations

* **Pause / unpause / manual run** (the deployment is created paused; unpausing is a human decision):
  ```bash
  ant beta:deployments retrieve --deployment-id "$(jq -r .deployments.nightly.id agents/managed/ids.json)"
  ant beta:deployments run      --deployment-id <depl_id>    # manual run, allowed while paused
  ant beta:deployments unpause  --deployment-id <depl_id>    # resumes from the next 19:45 UTC; missed ticks are not backfilled
  ant beta:deployments pause    --deployment-id <depl_id>
  ```
  Execution is jittered up to 9 minutes after the cron time. Failed triggers are recorded as
  deployment runs (`ant beta:deployment-runs list --deployment-id <id> --has-error true`).
* **Budgets.** `budget_usd` in `deployments.yaml` (copied onto each fired session; change applies
  from the next session). A session at its cap goes idle with `stop_reason: budget_reached`; change
  or remove its budget (`ant beta:sessions update --session-id … --budget …`) to resume. List cost
  counts model tokens at list rates, web fetches, and $0.08/h of running time.
* **Key rotation.** Mint a new `nightly_agent` JWT (`supabase/README.md` §4), put it in
  `secrets.env`, then `provision.py --rotate-key` (or just `provision.py`: a changed fingerprint is
  detected and the credential's `secret_value` is updated in place — same credential id, running
  sessions pick it up on their next operation). Then revoke the old token by rotating the Supabase
  signing key. Never create a second credential with the same `secret_name` (409).
* **Reading a session.** Console link above, or:
  ```bash
  ant beta:sessions list --transform '{id,title,status,created_at}' --format jsonl
  ant beta:sessions:events list --session-id <sesn_id> --transform '{type,text:content.#(type=="text").text}' --format jsonl
  ant beta:sessions:events stream --session-id <sesn_id>          # live
  uv run --group agents python agents/managed/smoke_test.py --session-id <sesn_id>   # transcript + outputs to disk
  ```
  Session outputs (`/mnt/session/outputs/`) come back through `client.beta.files.list(scope_id=…)`;
  the `ant` CLI does not expose `scope_id` yet.
* **Changing a prompt or tool.** Edit the YAML/markdown, re-run `provision.py`: the agent gets a new
  version, the coordinator's roster pin and the deployment's agent pin follow automatically; sessions
  already running keep their pinned versions.
* **Never** archive an agent, environment, vault or deployment from tooling (archive is permanent and
  archiving the coordinator archives the deployment). Never vault `SUPABASE_SECRET_KEY`. Never put a
  secret in a prompt, a `user.message`, a log line or `ids.json`.
