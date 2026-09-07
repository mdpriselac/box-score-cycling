"""Supabase control plane: roles, RLS, Storage policies and the client.

Spec: NIGHTLY_AGENT_WORKFLOW.md §1a (trust boundary) / §2.12; schema in
``supabase/migrations``. The offline tests always run. The live tests need
the local stack (``supabase start`` in the repo root — migrations apply on
start; ``supabase db reset --no-seed`` after editing one) and skip with a
clear message when the CLI, Docker or the stack is unavailable.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest
import requests

from cycling_project.nightly import keys, store_local
from cycling_project.nightly.release_store import FakeStore as ReleaseFakeStore
from cycling_project.nightly.release_store import hosted_store, resolve_store
from cycling_project.nightly.store import (
    AGENT_INSERT_TABLES,
    ARTIFACTS_BUCKET,
    RELEASES_BUCKET,
    STAGING_BUCKET,
    FakeStore,
    StoreConflictError,
    StoreError,
    StorePermissionError,
    SupabaseStore,
    artifact_key,
)
from cycling_project.prediction_tools.prediction_log import (
    MIGRATION_COLUMNS,
    SCHEMA_SQL,
    PredictionLogRow,
)

REPO = Path(__file__).resolve().parents[3]
MIGRATIONS = REPO / "supabase" / "migrations"
ALL_TABLES = (
    "calendar", "campaigns", "stages", "releases", "runs", "run_steps", "pcs_raw", "predictions",
    "prediction_log", "day_key_decisions", "editorial_drafts", "operator_tasks", "crosswalk",
    "crosswalk_proposals", "approvals", "reconciliation", "operators",
)


# ===========================================================================
# offline
# ===========================================================================

def test_artifact_key_rules():
    rid = str(uuid.uuid4())
    assert artifact_key(rid, "vuelta-2026/results/stage_16.json") == f"{rid}/vuelta-2026/results/stage_16.json"
    assert artifact_key(rid, "./a//b.txt") == f"{rid}/a/b.txt"
    for bad in ("../x", "/abs/x", "a/../../x", ""):
        with pytest.raises(ValueError):
            artifact_key(rid, bad)
    with pytest.raises(ValueError):
        artifact_key("not-a-uuid", "x")


def test_hs256_minting_roundtrip():
    secret = "s" * 40
    tok = keys.mint_hs256("nightly_agent", secret, "12h")
    header, payload = keys.decode_unverified(tok)
    assert header == {"alg": "HS256", "typ": "JWT"}
    assert payload["role"] == "nightly_agent" and payload["exp"] - payload["iat"] == 12 * 3600
    assert keys.verify_hs256(tok, secret)["role"] == "nightly_agent"
    with pytest.raises(keys.KeyError_):
        keys.verify_hs256(tok, "t" * 40)
    with pytest.raises(keys.KeyError_):
        keys.mint_hs256("service_role", secret)              # never mint the bypass role
    with pytest.raises(keys.KeyError_):
        keys.mint_hs256("nightly_agent", "short")
    assert keys.parse_duration("365d").days == 365 and keys.parse_duration("90").seconds == 90


def test_key_travels_in_headers_only():
    """The vault substitutes the key at egress in headers: never URL, query or body."""
    captured = {}

    class Sess:
        def request(self, method, url, params=None, json=None, headers=None, timeout=None):
            captured.update(method=method, url=url, params=params, json=json, headers=headers)
            r = requests.Response(); r.status_code = 200; r._content = b"[]"
            return r

    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoibmlnaHRseV9hZ2VudCJ9.sig"
    st = SupabaseStore(role="agent", url="https://ref.supabase.co/", key=jwt, apikey="sb_publishable_x", session=Sess())
    st.approved_runs("vuelta-2026")
    assert captured["headers"]["Authorization"] == f"Bearer {jwt}"
    assert captured["headers"]["apikey"] == "sb_publishable_x"
    blob = captured["url"] + json.dumps(captured["params"]) + json.dumps(captured["json"])
    assert jwt not in blob and "sb_publishable_x" not in blob
    # secret / publishable API keys go on `apikey` alone
    st2 = SupabaseStore(role="operator", url="https://ref.supabase.co", key="sb_secret_abc", apikey="sb_publishable_x")
    assert st2._headers() == {"apikey": "sb_secret_abc"}
    st3 = SupabaseStore(role="agent", url="https://ref.supabase.co", key=jwt)          # no publishable key set
    assert st3._headers()["apikey"] == jwt and st3._headers()["Authorization"] == f"Bearer {jwt}"


def test_hosted_and_fake_surfaces_match():
    hosted = {n for n in dir(SupabaseStore) if not n.startswith("_")}
    fake = {n for n in dir(FakeStore) if not n.startswith("_")}
    assert hosted <= fake, sorted(hosted - fake)
    for name in ("start_run", "add_step", "insert_pcs_raw", "insert_prediction", "insert_prediction_log_rows",
                 "insert_task", "insert_day_key", "insert_editorial_draft", "upload_artifact",
                 "list_artifacts_since", "download_release", "approved_day_key", "approved_runs",
                 "upload_release", "insert_release", "newest_approved_release", "get_release",
                 "download_release_file", "download_artifact",
                 "insert", "insert_many", "insert_crosswalk_proposals", "insert_reconciliation", "upsert_crosswalk",
                 "sync_calendar", "sync_campaign", "sync_stages"):
        assert callable(getattr(SupabaseStore, name)), name


def test_sibling_modules_find_the_client(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://ref.supabase.co")
    monkeypatch.setenv("SUPABASE_NIGHTLY_KEY", "eyJa.b.c")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_x")
    assert isinstance(hosted_store(), SupabaseStore)                       # release_store (chip B)
    assert isinstance(resolve_store("hosted"), SupabaseStore)
    assert isinstance(store_local.open_store("supabase", None, role="agent"), SupabaseStore)   # crosswalk (chip C)
    assert isinstance(resolve_store("fake", Path("/tmp/x")), ReleaseFakeStore)
    monkeypatch.delenv("SUPABASE_NIGHTLY_KEY")
    monkeypatch.setenv("SUPABASE_RELEASE_READER_KEY", "")
    # Keep this missing-key assertion isolated from a developer's configured
    # ~/.config/cycling-project/secrets.env.
    monkeypatch.setattr("cycling_project.nightly.store.load_local_env", lambda *args, **kwargs: None)
    with pytest.raises(StoreError):
        SupabaseStore(role="reader", url="https://ref.supabase.co", key=None)


def test_fake_store_enforces_the_agent_boundary(tmp_path):
    agent = FakeStore(tmp_path, role="agent")
    run = agent.start_run("vuelta-2026", "stage_16", "preview", release_tag=None)
    assert uuid.UUID(run["run_id"]) and run["host"] == "cloud"
    agent.add_step(run["run_id"], "acquire", "ok", duration_ms=5)
    agent.finish_run(run["run_id"], "ok")
    agent.insert_day_key("vuelta-2026", "stage_16", "res_2", author="agent", run_id=run["run_id"])
    agent.insert_task({"kind": "t", "campaign": "vuelta-2026", "summary": "s", "detail": {}, "urgency": "routine",
                       "author": "agent", "resolved": None})
    assert agent.rows["operator_tasks"][0]["campaign_slug"] == "vuelta-2026"
    for table, row in (
        ("approvals", {"run_id": run["run_id"], "approved_by": "x"}),
        ("calendar", {"fc_race_id": "1", "year": 2026, "name": "x", "category": "wt"}),
        ("day_key_decisions", {"campaign_slug": "v", "unit": "u", "author": "agent", "day_key": "k", "approved_by": "me"}),
        ("editorial_drafts", {"campaign_slug": "v", "unit": "u", "phase": "preview", "body_md": "x", "author": "human"}),
        ("operator_tasks", {"kind": "t", "summary": "s", "resolved": True}),
        ("crosswalk_proposals", {"pcs_slug": "a", "status": "confirmed"}),
        ("runs", {"phase": "preview", "host": "mac"}),
    ):
        with pytest.raises(StorePermissionError):
            agent.insert(table, row)
    with pytest.raises(StorePermissionError):
        agent.upload_artifact(str(uuid.uuid4()), "c/x.txt", b"x")          # foreign run id
    key = agent.upload_artifact(run["run_id"], "vuelta-2026/results/x.json", b"{}")
    with pytest.raises(StoreConflictError):
        agent.upload_artifact(run["run_id"], "vuelta-2026/results/x.json", b"{}")   # no overwrite
    with pytest.raises(StorePermissionError):
        agent.upload_release("t", tmp_path, {"files": {}})
    with pytest.raises(StorePermissionError):
        agent.upsert_crosswalk({"pcs_slug": "a", "fc_rider_id": "1"})
    assert agent.approved_day_key("vuelta-2026", "stage_16") is None
    assert agent.insert_prediction_log_rows([PredictionLogRow("23", 2026, 1), PredictionLogRow("23", 2026, 2)],
                                            run_id=run["run_id"]) == 2
    assert len(agent.rows["prediction_log"]) == 2 and agent.rows["prediction_log"][0]["run_id"] == run["run_id"]

    operator = FakeStore(tmp_path, role="operator")
    operator.rows = agent.rows                                              # same database
    operator.approve_day_key("vuelta-2026", "stage_16", "res_7", by="matt")
    assert operator.approved_day_key("vuelta-2026", "stage_16")["day_key"] == "res_7"
    assert agent.approved_day_key("vuelta-2026", "stage_16")["day_key"] == "res_7"
    operator.approve_run(run["run_id"], by="matt", note="ship")
    view = agent.approved_runs()
    assert view and "approved_by" not in view[0] and "private_note" not in view[0]
    operator.upsert_crosswalk({"pcs_slug": "a", "fc_rider_id": "1", "confidence": "1.00", "confirmed_by": "matt"})
    assert operator.rows["crosswalk"][0]["confidence"] == 1.0

    reader = FakeStore(tmp_path, role="reader")
    with pytest.raises(StorePermissionError):
        reader.insert("runs", {"phase": "x"})
    with pytest.raises(StorePermissionError):
        reader.list_artifacts_since("t")
    assert (tmp_path / "ledger" / "runs.jsonl").exists() and key.startswith(run["run_id"])


def test_prediction_log_mirrors_sqlite_columns():
    """§2.12: the Postgres table has exactly the SQLite columns (+ provenance)."""
    sql = (MIGRATIONS / "0001_control_plane.sql").read_text()
    block = re.search(r"create table public\.prediction_log \((.*?)\n\);", sql, re.S).group(1)
    pg_cols = {m.group(1) for m in re.finditer(r"^\s{2}([a-z_0-9]+)\s", block, re.M)}
    sqlite_cols = set(re.findall(r"^\s+([a-z_0-9]+)\s+(?:INTEGER|TEXT|REAL|TIMESTAMP)", SCHEMA_SQL, re.M))
    sqlite_cols |= {c for c, _ in MIGRATION_COLUMNS}
    assert pg_cols - {"run_id", "created_at"} == sqlite_cols
    assert set(PredictionLogRow("1", 2026, 1).as_row()) <= pg_cols


def test_roles_migration_is_append_only_for_the_agent():
    sql = (MIGRATIONS / "0002_roles.sql").read_text().lower()
    assert "grant nightly_agent  to authenticator" in sql
    assert "grant release_reader to authenticator" in sql
    for verb in ("update", "delete", "truncate", "all"):
        assert not re.search(rf"grant\s+{verb}\b[^;]*\bto\s+nightly_agent", sql), verb
        assert not re.search(rf"grant\s+{verb}\b[^;]*\bto\s+release_reader", sql), verb
    for table in ("calendar", "campaigns", "stages", "releases", "runs", "pcs_raw", "prediction_log",
                  "approvals", "operators", "crosswalk", "reconciliation"):
        assert f"alter table public.{table}" in sql and "enable row level security" in sql
    storage = (MIGRATIONS / "0003_storage.sql").read_text().lower()
    assert not re.search(r"for (update|delete) to", storage)
    assert "grant select, insert on storage.objects to nightly_agent" in storage
    tables_in_grant = re.search(r"grant insert on\s*(.*?)\s*to nightly_agent", sql, re.S).group(1)
    assert {t.strip().removeprefix("public.") for t in tables_in_grant.replace("\n", "").split(",")} == set(AGENT_INSERT_TABLES)


# ===========================================================================
# live — local `supabase start`
# ===========================================================================

def _local_stack():
    if not shutil.which("supabase"):
        pytest.skip("supabase CLI not installed (brew install supabase/tap/supabase) — live control-plane tests skipped")
    if not shutil.which("docker") or subprocess.run(["docker", "info"], capture_output=True).returncode != 0:
        pytest.skip("Docker is not running — start Docker Desktop, then `supabase start` in the repo root")
    env = keys.local_stack_env(REPO)
    if not env.get("API_URL") or not env.get("JWT_SECRET"):
        pytest.skip("local Supabase is not running — `supabase start` in the repo root (migrations apply on start)")
    secret = env.get("SECRET_KEY") or env.get("SERVICE_ROLE_KEY")
    try:
        r = requests.post(f"{env['API_URL']}/rest/v1/rpc/whoami", headers={"apikey": secret}, json={}, timeout=10)
    except requests.RequestException as exc:
        pytest.skip(f"local Supabase API not reachable: {exc}")
    if r.status_code != 200 or r.json() != "service_role":
        pytest.skip("local stack lacks the control-plane schema — run `supabase db reset --no-seed`")
    return env


class Live:
    def __init__(self, env):
        self.url = env["API_URL"]
        self.pub = env.get("PUBLISHABLE_KEY") or env["ANON_KEY"]
        self.secret = env.get("SECRET_KEY") or env["SERVICE_ROLE_KEY"]
        self.jwt_secret = env["JWT_SECRET"]
        self.campaign = f"test-{uuid.uuid4().hex[:8]}"
        self.tag = f"test-{uuid.uuid4().hex[:8]}"
        self.agent = self.store("agent", self.token("nightly_agent"))
        self.reader = self.store("reader", self.token("release_reader"))
        self.operator = self.store("operator", self.token("operator"))       # minted human role
        self.admin = SupabaseStore(role="operator", url=self.url, key=self.secret, apikey=self.pub)
        self.user_email = f"{self.campaign}@example.test"
        self.user = self.store("operator", self._user_token())    # role= only steers client-side guards
        self.run_ids: list[str] = []

    def token(self, role):
        return keys.mint_hs256(role, self.jwt_secret, "1h")

    def _user_token(self):
        """A Supabase-Auth-shaped JWT: role authenticated + sub + email."""
        import base64, hashlib, hmac
        header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).rstrip(b"=")
        claims = keys.build_claims("operator", "1h")
        claims.update({"role": "authenticated", "sub": str(uuid.uuid4()), "email": self.user_email, "aud": "authenticated"})
        payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=")
        sig = hmac.new(self.jwt_secret.encode(), header + b"." + payload, hashlib.sha256).digest()
        return (header + b"." + payload + b"." + base64.urlsafe_b64encode(sig).rstrip(b"=")).decode()

    def store(self, role, token):
        return SupabaseStore(role=role, url=self.url, key=token, apikey=self.pub)

    def admin_headers(self, **extra):
        h = {"apikey": self.secret, "Content-Type": "application/json"}
        h.update(extra)
        return h

    def admin_delete_rows(self, table, params):
        requests.delete(f"{self.url}/rest/v1/{table}", params=params, headers=self.admin_headers(), timeout=30)

    def admin_delete_objects(self, bucket, prefix):
        try:
            items = self.admin._list(bucket, prefix, recursive=True)
        except StoreError:
            return
        if items:
            requests.delete(f"{self.url}/storage/v1/object/{bucket}", headers=self.admin_headers(),
                            json={"prefixes": [i["key"] for i in items]}, timeout=60)

    def raw(self, store, method, path, **kw):
        headers = store._headers(kw.pop("headers", {}))
        return requests.request(method, f"{self.url}{path}", headers=headers, timeout=30, **kw)

    def start_run(self, unit="stage_01", phase="preview", **kw):
        run = self.agent.start_run(self.campaign, unit, phase, **kw)
        self.run_ids.append(run["run_id"])
        return run

    def cleanup(self):
        for rid in self.run_ids:
            for bucket in (ARTIFACTS_BUCKET, STAGING_BUCKET):
                self.admin_delete_objects(bucket, rid)
        self.admin_delete_objects(RELEASES_BUCKET, self.tag)
        by_campaign = {"campaign_slug": f"eq.{self.campaign}"}
        for table in ("approvals", "predictions", "pcs_raw", "day_key_decisions", "editorial_drafts",
                      "operator_tasks", "crosswalk_proposals", "reconciliation"):
            self.admin_delete_rows(table, by_campaign)
        self.admin_delete_rows("prediction_log", {"fc_race_id": f"eq.{self.campaign}"})
        self.admin_delete_rows("operators", {"email": f"eq.{self.user_email}"})
        for rid in self.run_ids:
            for table in ("approvals", "run_steps", "prediction_log", "predictions", "pcs_raw", "day_key_decisions",
                          "editorial_drafts", "operator_tasks", "crosswalk_proposals"):
                self.admin_delete_rows(table, {"run_id": f"eq.{rid}"})
            self.admin_delete_rows("runs", {"run_id": f"eq.{rid}"})
        self.admin_delete_rows("releases", {"tag": f"eq.{self.tag}"})


@pytest.fixture(scope="module")
def live():
    env = _local_stack()
    lv = Live(env)
    yield lv
    lv.cleanup()


pytestmark_live = pytest.mark.integration


@pytestmark_live
def test_live_whoami_per_key(live):
    assert live.agent.whoami() == "nightly_agent"
    assert live.reader.whoami() == "release_reader"
    assert live.operator.whoami() == "operator"
    assert live.admin.whoami() == "service_role"
    assert live.user.whoami() == "authenticated"


@pytestmark_live
def test_live_agent_appends_runs_steps_and_ledger(live):
    run = live.start_run(release_tag=None, deployment="nightly", meta={"test": True})
    rid = run["run_id"]
    assert run["state"] == "started" and run["host"] == "cloud"
    live.agent.add_step(rid, "acquire", "ok", duration_ms=12, detail={"rows": 3})
    live.agent.insert_pcs_raw(rid, live.campaign, "stage_01", "results", "https://www.procyclingstats.com/x",
                              "<html>verbatim</html>", ingest_verdict="ok")
    pred = live.agent.insert_prediction(rid, live.campaign, "stage_01", "preview", day_key="res_2",
                                        config={"scenario": "test"}, board_key=None)
    assert pred["day_key"] == "res_2"
    dk = live.agent.insert_day_key(live.campaign, "stage_01", "res_2", author="agent", run_id=rid, confidence=0.71)
    assert dk["approved_by"] is None and dk["approved_at"] is None
    draft = live.agent.insert_editorial_draft(rid, live.campaign, "stage_01", "preview", "Prose.", lint_ok=True)
    assert draft["approved_by"] is None
    task = live.agent.insert_task({"kind": "test-task", "campaign": live.campaign, "summary": "s",
                                   "detail": {"n": 1}, "urgency": "routine", "author": "agent", "resolved": None})
    assert task["resolved"] is False and task["campaign_slug"] == live.campaign
    assert any(t["id"] == task["id"] for t in live.agent.open_tasks(live.campaign))
    fin = live.agent.finish_run(rid, "ok", exit_code=0)
    assert fin["step"] == "finish"
    status = live.agent._select("run_status", {"run_id": f"eq.{rid}"})[0]
    assert status["state"] == "ok" and status["steps"] == 2


@pytestmark_live
def test_live_agent_cannot_update_or_delete_anything(live):
    run = live.start_run()
    for table in ALL_TABLES:
        for method in ("PATCH", "DELETE"):
            with pytest.raises(StorePermissionError):
                live.agent._rest(method, table, params={"created_at": "gt.1970-01-01"},
                                 json_body={"created_at": "1970-01-02"} if method == "PATCH" else None,
                                 prefer="return=minimal")
    with pytest.raises(StorePermissionError):                    # PostgREST upsert = UPDATE
        live.agent._insert("runs", [{"run_id": run["run_id"], "phase": "preview", "state": "hacked"}],
                           returning=False, on_conflict="run_id")
    assert live.agent._select("runs", {"run_id": f"eq.{run['run_id']}"})[0]["state"] == "started"


@pytestmark_live
def test_live_agent_cannot_write_outside_the_ledger(live):
    run = live.start_run()
    denied = {
        "approvals": {"run_id": run["run_id"], "approved_by": "agent"},
        "calendar": {"fc_race_id": "1", "year": 2026, "name": "x", "category": "wt"},
        "campaigns": {"campaign_slug": "x", "fc_race_id": "1", "year": 2026, "name": "x"},
        "stages": {"campaign_slug": "x", "unit": "gc", "kind": "gc"},
        "releases": {"tag": "x", "git_sha": "x", "manifest": {}},
        "crosswalk": {"pcs_slug": "x", "fc_rider_id": "1"},
        "reconciliation": {"campaign_slug": "x", "unit": "gc", "kind": "gc"},
        "operators": {"email": "x@example.test"},
    }
    for table, row in denied.items():
        with pytest.raises(StorePermissionError):
            live.agent._insert(table, [row], returning=False)
        with pytest.raises(StorePermissionError):
            live.agent.insert(table, row)                        # client-side guard, same outcome


@pytestmark_live
def test_live_rls_blocks_approved_or_resolved_rows_from_the_agent(live):
    run = live.start_run()
    rid = run["run_id"]
    with pytest.raises(StorePermissionError):
        live.agent._insert("day_key_decisions", [{"campaign_slug": live.campaign, "unit": "stage_02", "author": "agent",
                                                  "day_key": "res_2", "approved_by": "agent"}])
    with pytest.raises(StorePermissionError):
        live.agent._insert("day_key_decisions", [{"campaign_slug": live.campaign, "unit": "stage_02", "author": "human",
                                                  "day_key": "res_2"}])
    with pytest.raises(StorePermissionError):
        live.agent._insert("editorial_drafts", [{"campaign_slug": live.campaign, "unit": "stage_02", "phase": "preview",
                                                 "body_md": "x", "approved_by": "agent"}])
    with pytest.raises(StorePermissionError):
        live.agent._insert("operator_tasks", [{"kind": "test-task", "summary": "s", "resolved": True}])
    with pytest.raises(StorePermissionError):
        live.agent._insert("crosswalk_proposals", [{"pcs_slug": "x", "status": "confirmed", "run_id": rid}])
    with pytest.raises(StorePermissionError):
        live.agent._insert("runs", [{"phase": "preview", "host": "mac"}])
    assert live.agent.approved_day_key(live.campaign, "stage_02") is None


@pytestmark_live
def test_live_agent_reads_registry_and_approvals_view_only(live):
    run = live.start_run(unit="stage_03")
    assert isinstance(live.agent.campaigns(), list)
    assert isinstance(live.agent._select("calendar", {"limit": "1"}), list)
    for table in ("approvals", "operators"):
        with pytest.raises(StorePermissionError):
            live.agent._select(table, {"limit": "1"})
    row = live.operator._insert("approvals", [{"run_id": run["run_id"], "campaign_slug": live.campaign, "kind": "publish",
                                               "approved_by": "matt", "note": "ship it", "private_note": "hush"}])[0]
    assert row["private_note"] == "hush"
    seen = [a for a in live.agent.approved_runs(live.campaign) if a["run_id"] == run["run_id"]]
    assert seen and seen[0]["note"] == "ship it"
    assert "approved_by" not in seen[0] and "private_note" not in seen[0]


@pytestmark_live
def test_live_operator_role_and_allowlisted_human(live):
    run = live.start_run(unit="stage_04")
    task = live.agent.insert_task({"kind": "test-task", "campaign": live.campaign, "summary": "resolve me"})
    # a minted operator JWT
    done = live.operator._rest("PATCH", "operator_tasks", params={"id": f"eq.{task['id']}"},
                               json_body={"resolved": True, "resolved_by": "matt"}, prefer="return=representation").json()
    assert done[0]["resolved"] is True and done[0]["resolved_at"]
    human_key = live.operator._insert("day_key_decisions", [{"campaign_slug": live.campaign, "unit": "stage_04",
                                                             "author": "human", "day_key": "res_7", "approved_by": "matt"}])[0]
    assert human_key["approved_at"]
    assert live.agent.approved_day_key(live.campaign, "stage_04")["day_key"] == "res_7"
    with pytest.raises(StorePermissionError):
        live.operator._rest("DELETE", "runs", params={"run_id": f"eq.{run['run_id']}"})
    # a Supabase-Auth user who is NOT on the allow-list sees nothing and cannot approve
    assert live.user._select("runs", {"run_id": f"eq.{run['run_id']}"}) == []
    with pytest.raises(StorePermissionError):
        live.user._insert("approvals", [{"run_id": run["run_id"], "approved_by": live.user_email}])
    # … until the admin lists them in public.operators
    live.admin._insert("operators", [{"email": live.user_email}])
    assert live.user._select("runs", {"run_id": f"eq.{run['run_id']}"})[0]["run_id"] == run["run_id"]
    appr = live.user._insert("approvals", [{"run_id": run["run_id"], "campaign_slug": live.campaign,
                                            "approved_by": live.user_email}])[0]
    assert appr["approved_by"] == live.user_email
    with pytest.raises(StorePermissionError):                    # even operators never delete
        live.user._rest("DELETE", "approvals", params={"id": f"eq.{appr['id']}"})


@pytestmark_live
def test_live_reader_scope(live):
    assert isinstance(live.reader._select("releases", {"limit": "1"}), list)
    for table in ("runs", "campaigns", "approvals_view", "operator_tasks"):
        with pytest.raises(StorePermissionError):
            live.reader._select(table, {"limit": "1"})
    with pytest.raises(StorePermissionError):
        live.reader._insert("runs", [{"phase": "preview"}], returning=False)
    with pytest.raises(StorePermissionError):
        live.reader.insert_release({"tag": "x", "git_sha": "x", "manifest": {}})      # client guard


@pytestmark_live
def test_live_storage_artifacts_are_insert_only_under_own_run(live, tmp_path):
    live.admin.insert_release({"tag": live.tag, "git_sha": "deadbeef", "manifest": {"files": {}}, "approved": False})
    run = live.start_run(unit="stage_05")
    rid = run["run_id"]
    key = live.agent.upload_artifact(rid, f"{live.campaign}/results/stage_05.json", b'{"ok": true}')
    assert key == f"{rid}/{live.campaign}/results/stage_05.json"
    with pytest.raises(StoreConflictError):                      # same key again
        live.agent.upload_artifact(rid, f"{live.campaign}/results/stage_05.json", b"{}")
    r = live.raw(live.agent, "POST", f"/storage/v1/object/{ARTIFACTS_BUCKET}/{key}", data=b"overwrite",
                 headers={"x-upsert": "true", "Content-Type": "application/json"})
    assert r.status_code >= 400 and "denied" in r.text.lower()   # upsert needs UPDATE
    with pytest.raises(StorePermissionError):                    # a run id the agent did not start
        live.agent.upload_artifact(str(uuid.uuid4()), f"{live.campaign}/results/x.json", b"{}")
    with pytest.raises(StorePermissionError):                    # too shallow: <run_id>/<file>
        live.agent._upload(ARTIFACTS_BUCKET, f"{rid}/flat.json", b"{}")
    with pytest.raises(StorePermissionError):
        live.agent._upload(ARTIFACTS_BUCKET, f"{live.campaign}/results/no-run.json", b"{}")
    staged = live.agent.upload_artifact(rid, "index.html", b"<html/>", bucket=STAGING_BUCKET)
    assert staged == f"{rid}/index.html"
    for bucket, k in ((RELEASES_BUCKET, f"{live.tag}/x.txt"), ("site", f"{live.campaign}.html")):
        with pytest.raises(StorePermissionError):
            live.agent._upload(bucket, k, b"x")
    r = live.raw(live.agent, "DELETE", f"/storage/v1/object/{ARTIFACTS_BUCKET}/{key}")
    assert r.status_code >= 400
    assert live.agent.download_artifact(key, tmp_path / "back.json").read_bytes() == b'{"ok": true}'
    since = live.agent.list_artifacts_since(live.tag)
    assert any(o["key"] == key and o["size"] == 12 for o in since)


@pytestmark_live
def test_live_release_bundle_round_trip(live, tmp_path):
    tag = live.tag + "-b"
    bundle = tmp_path / "bundle"
    (bundle / "models").mkdir(parents=True)
    (bundle / "models" / "m.txt").write_bytes(b"model")
    (bundle / "slice.db").write_bytes(b"sqlite")
    manifest = {"tag": tag, "files": {"models/m.txt": {"sha256": "x"}, "slice.db": {"sha256": "y"}}}
    try:
        keys_written = live.admin.upload_release(tag, bundle, manifest)
        assert keys_written[-1] == f"{RELEASES_BUCKET}/{tag}/manifest.json" and len(keys_written) == 3
        with pytest.raises(StoreConflictError):                  # a tag is immutable
            live.admin.upload_release(tag, bundle, manifest)
        row = live.admin.insert_release({"tag": tag, "git_sha": "abc", "manifest": manifest, "approved": False})
        assert row["approved"] is False
        assert live.reader.get_release(tag)["tag"] == tag
        newest = live.reader.newest_approved_release()
        assert newest is None or newest["tag"] != tag                # not approved yet
        live.admin._rest("PATCH", "releases", params={"tag": f"eq.{tag}"}, json_body={"approved": True}, prefer="return=minimal")
        approved = live.admin.get_release(tag)
        assert approved["approved"] and approved["approved_at"] and approved["approved_by"]
        out = live.reader.download_release(tag, tmp_path / "out")
        assert (out / "models" / "m.txt").read_bytes() == b"model" and (out / "slice.db").read_bytes() == b"sqlite"
        assert json.loads((out / "manifest.json").read_text())["tag"] == tag
        assert live.agent.download_release_file(tag, "slice.db", tmp_path / "agent.db").read_bytes() == b"sqlite"
        for st in (live.reader, live.agent):
            with pytest.raises(StorePermissionError):
                st._upload(RELEASES_BUCKET, f"{tag}/extra.txt", b"x")
        with pytest.raises(StorePermissionError):
            live.reader.upload_release(tag + "x", bundle, manifest)
    finally:
        live.admin_delete_objects(RELEASES_BUCKET, tag)
        live.admin_delete_rows("releases", {"tag": f"eq.{tag}"})


@pytestmark_live
def test_live_prediction_log_is_idempotent(live):
    run = live.start_run(unit="stage_06")
    rows = [PredictionLogRow(live.campaign, 2026, rider_id=i, stage_number=6, model_version="t",
                             multiclass_win_p=0.1 * i) for i in (1, 2, 3)]
    payload = [{**r.as_row(), "run_key": f"{live.campaign}-k"} for r in rows]
    assert live.agent.insert_prediction_log_rows(payload, run_id=run["run_id"]) == 3
    assert live.agent.insert_prediction_log_rows(payload, run_id=run["run_id"]) == 3     # duplicates ignored
    stored = live.admin._select("prediction_log", {"run_id": f"eq.{run['run_id']}", "select": "rider_id,multiclass_win_p"})
    assert sorted(s["rider_id"] for s in stored) == [1, 2, 3]
    with pytest.raises(StorePermissionError):
        live.agent._rest("DELETE", "prediction_log", params={"run_id": f"eq.{run['run_id']}"})


# ---------------------------------------------------------------------------
# schema vs. the states the driver actually writes
# ---------------------------------------------------------------------------

def _allowed_run_step_states() -> set[str]:
    """The effective CHECK on run_steps.state — the last migration to define it wins."""
    migrations = sorted((Path(__file__).resolve().parents[3] / "supabase" / "migrations").glob("*.sql"))
    allowed: set[str] = set()
    for path in migrations:
        for match in re.finditer(r"state\s+in\s*\(([^)]*)\)", path.read_text(), re.I):
            allowed = set(re.findall(r"'([^']+)'", match.group(1)))
    return allowed


def test_the_schema_accepts_every_state_the_driver_records():
    """Regression for the silent ledger hole found building the inbox (chip J).

    driver.Runner finishes a run 'waiting' (exit 10) or 'failed' (exit 20) and
    records the same on the step that raised. 0001's CHECK allowed neither, and
    the driver swallows ledger errors, so those runs reached the hosted ledger
    with no `finish` row at all: run_status fell back to runs.state and every
    waiting or failed night read as 'started' forever. 0005 widened the CHECK.
    """
    driver_src = (Path(__file__).resolve().parents[2] / "nightly" / "driver.py").read_text()
    written = set(re.findall(r'_record_step\(\s*name,\s*"(\w+)"', driver_src))
    written |= set(re.findall(r'\.finish\(\s*"(\w+)"', driver_src))
    written |= {"ok"}                       # finish_run / add_step defaults

    allowed = _allowed_run_step_states()
    assert allowed, "no CHECK on run_steps.state found in supabase/migrations"
    assert written <= allowed, f"driver writes states the schema rejects: {sorted(written - allowed)}"
