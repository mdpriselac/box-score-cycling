# Supabase control plane (`CyclingNightly`)

The ledger, inbox and artifact store for the nightly Managed-Agents run
(`NIGHTLY_AGENT_WORKFLOW.md` §1a, §2.7, §2.12). Postgres tables behind
PostgREST, four private Storage buckets, and three locked-down roles. The
cloud agent can only **append**; humans approve in the dashboard; the Mac is
the only writer of the registry and of release bundles.

```
supabase/
  config.toml                  local stack (`supabase start`) — Postgres 17 like the hosted project
  migrations/0001_control_plane.sql   tables + views + triggers
  migrations/0002_roles.sql           roles, grants, row-level security
  migrations/0003_storage.sql         buckets + storage policies
  mint_keys.py                 prints a role JWT once (nightly_agent / release_reader / operator)
cycling_project/nightly/store.py     the client (SupabaseStore + FakeStore)
cycling_project/nightly/keys.py      minting primitives used by mint_keys.py and the tests
cycling_project/tests/unit/test_nightly_store.py   trust-boundary tests (live against `supabase start`)
```

## 1. Trust boundary in one table

| Role | Key | Tables | Storage |
|---|---|---|---|
| `nightly_agent` (cloud agent) | JWT minted for the role, vaulted as `SUPABASE_NIGHTLY_KEY` | INSERT `runs, run_steps, pcs_raw, predictions, prediction_log, day_key_decisions, editorial_drafts, operator_tasks, crosswalk_proposals`; SELECT registry (`calendar, campaigns, stages, releases, crosswalk`), `approvals_view` (no approver, no private note) and the ledger it writes (`prediction_log` included: Postgres needs SELECT for the idempotent `ON CONFLICT DO NOTHING`). **No UPDATE / DELETE / TRUNCATE, no DDL.** RLS also refuses inserts with `approved_by`/`approved_at` set, `author = 'human'`, `resolved = true`, or a proposal `status ≠ 'proposed'`. | INSERT into `nightly-artifacts/<run_id>/<campaign>/…` and `site-staging/<run_id>/…` only when `<run_id>` exists in `runs`; SELECT `releases/*` and `nightly-artifacts/*` (bootstrap). Overwrite (`x-upsert`) needs UPDATE → denied. |
| `release_reader` | JWT, `SUPABASE_RELEASE_READER_KEY` | SELECT `releases` | SELECT `releases/*` |
| `operator` (humans) | Supabase Auth login (role `authenticated`) gated by the `operators` allow-list, or a JWT minted with `role = operator` | full read; INSERT `approvals`, `day_key_decisions` (with `approved_by`), `operator_tasks`, `crosswalk`; UPDATE `operator_tasks.resolved*`, `crosswalk`, `crosswalk_proposals.status`, `releases.approved`, `day_key_decisions.approved_by`, `editorial_drafts.approved_by` | none beyond reads |
| `service_role` (the Mac) | `SUPABASE_SECRET_KEY` (`sb_secret_…`), operator-only, never in a vault/prompt/log | everything (bypasses RLS): registry sync, weekly import, reconciliation | `releases/` upload, `site` promotion, cleanup |

`public.whoami()` returns the role a request runs as — the tests and
`mint_keys.py --verify` use it.

## 2. Key model (checked against supabase.com/docs, 2026-09)

* A project has **publishable** (`sb_publishable_…` → `anon`/`authenticated`)
  and **secret** (`sb_secret_…` → `service_role`) API keys. They go on the
  `apikey` header. They cannot be bound to a custom Postgres role.
* PostgREST and Storage `SET ROLE` to the **`role` claim of the JWT on
  `Authorization: Bearer`**, provided that role is `GRANT`ed to
  `authenticator` (0002 does this for the three roles). `role` may be any
  existing Postgres role; `sub` is optional. The gateway still needs a
  publishable key on `apikey` next to the custom JWT.
* Therefore the agent and reader keys are **JWTs minted for their role**, and
  the vault holds `SUPABASE_NIGHTLY_KEY` (the JWT) while
  `SUPABASE_PUBLISHABLE_KEY` (public by design) rides along as `apikey`.
  `store.py` puts both in headers and nowhere else.
* Signing: the recommended path is an **ES256 signing key** you generate and
  import (asymmetric, rotatable without downtime; JWKS at
  `/auth/v1/.well-known/jwks.json`). The **legacy HS256 JWT secret** still
  verifies but is "not recommended for production". The local stack uses
  HS256 with the secret `supabase status -o env` prints.

## 3. Project setup

### Local (no questions asked)

```bash
supabase start -x realtime,edge-runtime,logflare,vector,supavisor,imgproxy   # applies migrations/*.sql
supabase status -o env                                                        # API_URL, PUBLISHABLE_KEY, SECRET_KEY, JWT_SECRET …
uv run python supabase/mint_keys.py nightly_agent --local --valid-for 12h --verify
supabase db reset --no-seed        # re-apply every migration from scratch after editing one
supabase stop                      # keeps data; `supabase stop --no-backup` wipes it
```

Studio (the inbox) is at http://127.0.0.1:54323.

### Hosted (`CyclingNightly`, ref in `SUPABASE_PROJECT_REF`)

These steps create objects in the hosted project — run them yourself, in
order, from the repo root:

```bash
set -a; source ~/.config/cycling-project/secrets.env; set +a
supabase link --project-ref "$SUPABASE_PROJECT_REF"      # prompts for SUPABASE_DB_PASSWORD once
supabase db push                                         # applies 0001..0003 (idempotent list in supabase_migrations)
supabase migration list                                  # local == remote
```

`db push` runs as `postgres`, which owns the tables; role creation and
`grant … to authenticator` succeed there. If the project ever reports the
roles missing after a restore, re-run `supabase db push --include-all`.

Then, in the dashboard:

1. **Authentication → Users → Invite** each operator (sign-up is disabled in
   `config.toml`; keep it disabled hosted too: Auth → Providers → Email →
   "Allow new users to sign up" off).
2. Insert their email into `public.operators` (Table editor, or
   `insert into public.operators(email) values ('you@example.com')`). Without
   that row a logged-in user sees nothing and can change nothing.
3. **Project Settings → JWT Signing Keys**: import the ES256 key from step 4
   below as a *standby* key, then **rotate** so it becomes the current key
   (tokens signed by the previous key stay valid while unexpired).

## 4. Minting keys

Generate the signing key once, on the Mac, outside the repo:

```bash
supabase gen signing-key --algorithm ES256 > ~/.config/cycling-project/supabase_signing_key.json
chmod 600 ~/.config/cycling-project/supabase_signing_key.json
```

Import it in the dashboard (step 3 above). Then mint — each command prints
the token **once** on stdout and everything else on stderr:

```bash
uv run python supabase/mint_keys.py nightly_agent  --valid-for 365d --verify | pbcopy
uv run python supabase/mint_keys.py release_reader --valid-for 365d --verify | pbcopy
uv run python supabase/mint_keys.py operator       --valid-for 30d  --verify | pbcopy   # scripts on the Mac that must not hold the secret key
```

`--verify` calls `whoami()` with the fresh token and refuses to print it
unless the API ran it as the requested role (the usual failure is a signing
key not yet imported, or 0002 not pushed). Store the tokens:

* `SUPABASE_NIGHTLY_KEY` → the Anthropic vault for the `nightly` deployment
  (`environment_variable`, header injection only, `allowed_hosts` = the
  project host) **and** `~/.config/cycling-project/secrets.env` for local
  dry-runs;
* `SUPABASE_RELEASE_READER_KEY` → `secrets.env` (and any future reader such
  as an Edge Function);
* the publishable key is already in `secrets.env` as
  `SUPABASE_PUBLISHABLE_KEY`; give the cloud container the same variable
  (plain, not vaulted — it is public by design).

Nothing secret goes in git: `supabase/signing_keys.json` and `.temp/` are
ignored, and `mint_keys.py` never writes to disk. If the hosted project is
still on the legacy JWT secret, `--hs256` signs with `SUPABASE_JWT_SECRET`
(Project Settings → API → JWT Settings → copy into `secrets.env`); switch to
ES256 when convenient — both verify.

**Rotation.** Mint a new token (new expiry), swap it in the vault/secrets,
then revoke the old one by rotating the signing key in the dashboard (the
revoked key's tokens stop verifying at once). Roles themselves need no
change.

## 5. The client

```python
from cycling_project.nightly.store import SupabaseStore, FakeStore

store = SupabaseStore(role="agent")                  # SUPABASE_URL + SUPABASE_NIGHTLY_KEY (+ PUBLISHABLE) from env
run = store.start_run("vuelta-2026", "stage_16", "preview", release_tag="2026-09-05")
store.add_step(run["run_id"], "acquire", "ok", duration_ms=1234)
store.insert_pcs_raw(run["run_id"], "vuelta-2026", "stage_16", "results", url, html, ingest_verdict="ok")
key = store.upload_artifact(run["run_id"], "vuelta-2026/results/stage_16.json", data)   # nightly-artifacts/<run_id>/…
store.insert_prediction(run["run_id"], "vuelta-2026", "stage_16", "preview", board_key=key, day_key="res_2")
store.insert_prediction_log_rows(rows, run_id=run["run_id"])      # idempotent on (run_key, rider_id)
store.insert_day_key("vuelta-2026", "stage_16", "res_2", author="agent", confidence=0.7)
store.insert_task({"kind": "ingest_rejected", "campaign": "vuelta-2026", "summary": "…", "detail": {...}})
store.approved_day_key("vuelta-2026", "stage_16")                 # the human key, or None
store.approved_runs()                                             # approvals_view rows
store.finish_run(run["run_id"], "ok")                             # a run_steps row; runs are never updated

SupabaseStore(role="reader").download_release("2026-09-05", dest)  # whole bundle by manifest
SupabaseStore(role="operator").upload_release(tag, bundle_dir, manifest)   # the Mac (secret key)
```

`FakeStore(root, role=…)` has the same methods and enforces the same rules
in memory, so `--dry-run`, `--store fake` and the unit tests exercise the
trust boundary without a network. `release_store.resolve_store("hosted")`
and `store_local.open_store("supabase")` both find this module.

Errors: `StorePermissionError` (401/403 — grant or RLS), `StoreConflictError`
(409 — duplicate key or existing object), `StoreError` otherwise; messages
are passed through `secrets.redact()`.

## 6. Dashboard as inbox (day one)

Table editor → these tables are the queue; filters are saved per browser:

| Table | Human action | Effect |
|---|---|---|
| `operator_tasks` (`resolved = false`, sort by `urgency`) | tick `resolved`, optionally `resolution` | `resolved_by/at` are stamped by trigger; the agent lists `open_tasks()` to avoid duplicates |
| `day_key_decisions` | **insert** a row `author = 'human'`, `day_key`, `approved_by = <you>` for the unit | `approved_at` stamped; `approved_day_key()` returns the newest approved row and the nightly run prices with it |
| `approvals` | **insert** `run_id`, `kind = 'publish'`, `decision = 'approve'`, `approved_by` | promotion (`nightly promote` on the Mac) publishes only approved runs; the agent sees the decision through `approvals_view` |
| `crosswalk_proposals` | set `status` to `confirmed`/`rejected` and add the `crosswalk` row (or `nightly crosswalk confirm --by <you>` which runs as operator) | identity fixes reach the next release |
| `releases` | tick `approved` on the tag you verified | `bootstrap` takes the newest approved release |
| `editorial_drafts` | set `approved_by` on prose you accept | retros need an approved draft; previews may ship prose-less |

Views: `run_status` (latest `finish` step per run) and `approvals_view`.
Notifications: Database → Webhooks on `operator_tasks` INSERT → ntfy /
Pushover (chip J). Later the `_frame/ops.html` page renders the same tables
through the Supabase JS client with the publishable key and an operator
login.

## 7. Backups

* Hosted: daily automatic backups on the Pro plan (Database → Backups); for
  the ledger a weekly logical dump is enough and the Mac already pulls the
  week's rows into `performance_eval/` (git is the second copy):
  `supabase db dump --linked --data-only -f backups/control-plane-$(date +%F).sql`.
* Storage: `releases/` is rebuilt from the repo + models on demand;
  `nightly-artifacts/` is overlaid into `performance_eval/` weekly and
  committed. Nothing in Supabase is the only copy of anything after the
  weekly reconcile.
* Schema is code: `supabase/migrations/`. Never edit tables in the dashboard;
  add `0004_….sql` and `supabase db push`.
