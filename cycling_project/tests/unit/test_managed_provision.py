"""agents/managed/provision.py — rendering, ordering and the no-secret-leaves-the-Mac rules.

Pure tests: no API calls. The real provisioning is exercised by hand (README §3).
"""

import importlib.util
import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MANAGED = PROJECT_ROOT / "agents" / "managed"


@pytest.fixture(scope="module")
def pv():
    spec = importlib.util.spec_from_file_location("provision", MANAGED / "provision.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def env():
    return {
        "SUPABASE_URL": "https://your-project-ref.supabase.co",
        "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_test_0123456789",
        "SUPABASE_NIGHTLY_KEY": "eyJ.nightly.jwt.value.0123456789abcdef",
        "SUPABASE_SECRET_KEY": "sb_secret_MUST_NEVER_LEAVE_THE_MAC_0123",
        "SUPABASE_DB_PASSWORD": "dbpassword-0123456789",
        "SUPABASE_JWT_SECRET": "jwtsecret-0123456789",
        "ANTHROPIC_API_KEY": "sk-ant-api03-fake-0123456789",
    }


def test_plan_renders_every_document_without_secrets(pv, env):
    p = pv.plan(env)
    blob = json.dumps({k: v for k, v in p.items()}, default=str)
    for name in ("SUPABASE_NIGHTLY_KEY", "SUPABASE_SECRET_KEY", "SUPABASE_DB_PASSWORD", "SUPABASE_JWT_SECRET", "ANTHROPIC_API_KEY"):
        assert env[name] not in blob, f"{name} leaked into the rendered plan"
    assert "{{" not in blob, "unresolved template placeholder"
    # the two non-secret values do reach the coordinator prompt
    coord = p["agents"]["nightly-coordinator"]["system"]
    assert env["SUPABASE_URL"] in coord and env["SUPABASE_PUBLISHABLE_KEY"] in coord
    assert "your-project-ref.supabase.co" in coord


def test_stage0_is_inlined_and_hands_over_to_bootstrap(pv, env):
    coord = pv.plan(env)["agents"]["nightly-coordinator"]["system"]
    assert "exec uv run python -m cycling_project.nightly.bootstrap --dest" in coord
    assert "storage/v1/object/authenticated/releases/" in coord
    assert "Authorization: Bearer ${SUPABASE_NIGHTLY_KEY}" in coord      # header-only use
    assert "git" in coord and "never run `git`" in coord


def test_agent_order_leaves_first_and_roster_resolves(pv, env):
    p = pv.plan(env)
    order = p["agent_order"]
    assert order[-1] == "nightly-coordinator"
    assert set(order[:-1]) == {"uci-acquirer", "pcs-acquirer", "day-key-reader", "editorial", "ops-triage"}
    ids = {n: {"id": f"agent_{i}", "version": i + 1} for i, n in enumerate(order[:-1])}
    roster = pv.resolve_roster(p["agents"]["nightly-coordinator"], ids)
    assert roster["type"] == "coordinator"
    assert {"type": "self"} in roster["agents"]
    pinned = [e for e in roster["agents"] if e.get("type") == "agent"]
    assert {e["id"] for e in pinned} == {v["id"] for v in ids.values()}
    assert all("version" in e for e in pinned)
    for leaf in order[:-1]:
        assert pv.resolve_roster(p["agents"][leaf], ids) is None       # depth limit 1


def test_tool_surfaces_match_the_trust_boundary(pv, env):
    a = pv.plan(env)["agents"]
    def enabled(spec):
        tools = spec.get("tools") or []
        if not tools:
            return set()
        ts = tools[0]
        default = (ts.get("default_config") or {}).get("enabled", True)
        names = {"bash", "read", "write", "edit", "glob", "grep", "web_fetch", "web_search"}
        cfg = {c["name"]: c.get("enabled", default) for c in ts.get("configs", [])}
        return {n for n in names if cfg.get(n, default)}
    assert enabled(a["day-key-reader"]) == set() and enabled(a["editorial"]) == set()
    assert enabled(a["ops-triage"]) == {"read", "glob", "grep"}
    assert enabled(a["pcs-acquirer"]) == {"web_fetch", "write", "read"}
    assert enabled(a["uci-acquirer"]) == {"bash", "read", "glob"}              # deterministic CLI runner: no write, no web
    fetch_cfg = next(c for c in a["pcs-acquirer"]["tools"][0]["configs"] if c["name"] == "web_fetch")
    assert "procyclingstats.com" in fetch_cfg["allowed_domains"] and "blocked_domains" not in fetch_cfg
    coord = enabled(a["nightly-coordinator"])
    assert "bash" in coord and "web_fetch" not in coord and "web_search" not in coord
    for name, spec in a.items():
        assert spec["model"]["id"] == "claude-opus-5", name


def test_skill_files_are_the_system_prompts(pv, env):
    a = pv.plan(env)["agents"]
    skill = (PROJECT_ROOT / "agents/skills/day-key-read/SKILL.md").read_text()
    assert a["day-key-reader"]["system"].strip() == pv.strip_frontmatter(skill).strip()
    assert not a["day-key-reader"]["system"].lstrip().startswith("---")
    assert "Editorial agent" in a["editorial"]["system"]


def test_vault_and_deployment_specs(pv, env):
    p = pv.plan(env)
    v = p["vault"]
    assert [c["auth"]["secret_name"] for c in v["credentials"]] == ["SUPABASE_NIGHTLY_KEY"]
    cred = v["credentials"][0]["auth"]
    assert cred["injection_location"] == {"header": True}
    assert cred["networking"] == {"type": "limited", "allowed_hosts": ["your-project-ref.supabase.co"]}
    assert "secret_value" not in cred
    d = p["deployments"]["deployments"][0]
    assert d["name"] == "nightly" and d["create_paused"] is True
    assert d["schedule"] == {"type": "cron", "expression": "45 19 * * *", "timezone": "UTC"}
    assert d["budget"] == {"type": "limit", "max_list_cost": {"amount": "1200", "currency": "USD"}}
    assert d["initial_events"] == [{"type": "user.message", "content": [{"type": "text", "text": "Run the nightly cycle."}]}]
    e = p["environment"]
    net = e["config"]["networking"]
    assert net["type"] == "limited" and net["allow_package_managers"] is True
    assert set(net["allowed_hosts"]) == {"your-project-ref.supabase.co", "eu-offering-api.kambicdn.com", "www.uci.org", "uci.org"}
    assert "resources" not in d


def test_cents_and_leak_check(pv, env):
    assert pv.cents("12.00") == "1200" and pv.cents("5") == "500" and pv.cents("0.50") == "50"
    with pytest.raises(pv.ProvisionError):
        pv.cents("0")
    with pytest.raises(pv.ProvisionError):
        pv.leak_check({"system": "x " + env["SUPABASE_SECRET_KEY"]}, env, label="t")
    pv.leak_check({"system": "clean"}, env, label="t")
    with pytest.raises(pv.ProvisionError):
        pv.render_text("{{SUPABASE_SECRET_KEY}}", pv.template_context(env))


def test_protected_agent_is_never_a_target(pv):
    assert "agent_01EXAMPLE466A1EFA1DEDA25" in pv.PROTECTED_AGENT_IDS
    names = {y.stem.replace(".agent", "") for y in (MANAGED / "agents").glob("*.agent.yaml")}
    assert "Procycling Stats Extractor" not in names
