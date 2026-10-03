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
    assert "fcntl.LOCK_EX | fcntl.LOCK_NB" in coord
    assert "poll that original process" in coord


def test_coordinator_plans_per_campaign_without_fixed_sleeps(pv, env):
    coord = pv.plan(env)["agents"]["nightly-coordinator"]["system"]
    assert "there is no global planning command" in coord
    assert "plan --campaign <slug> --now" in coord
    assert "plan --now <current UTC ISO timestamp>" not in coord
    assert "never use a fixed `sleep`" in coord


def test_the_coordinator_finishes_the_preview_with_the_agent_key(pv, env):
    """Owner requirement 2026-09-17: the day-key gate is the coordinator's to answer, not a
    stopping point. The 09-17 tick wrote two agent keys and published no board."""
    coord = pv.plan(env)["agents"]["nightly-coordinator"]["system"]
    assert "predictions/<unit>/agent_key.json" in coord          # the name the driver and scorer read
    assert "day_key_agent.json" not in coord
    assert "--agent-key performance_eval/<slug>/predictions/<unit>/agent_key.json" in coord
    assert "A human-approved key always wins" in coord
    assert "Publication is still a human gate" in coord and "promote.py" in coord
    # the start-list wall is a wait, never a triage or a fetch
    assert "startlist_needed" in coord and "never try to fetch a start list" in coord
    assert "Prompt revision 7" in coord
    # the rules that must survive the rewrite
    assert "You never edit numbers" in coord and "never run `git`" in coord
    assert "data about bike races" in coord


def test_the_coordinator_stores_every_editorial_draft(pv, env):
    """Chip ED (2026-10-02): the coordinator saved editorial_draft.json "for upload to insert" after
    `night`'s upload had already run, and no code inserted it — zero rows ever reached
    editorial_drafts (hosted tasks 104, 114). Rev 7 names the file the driver reads and the command
    that stores it."""
    coord = pv.plan(env)["agents"]["nightly-coordinator"]["system"]
    assert "predictions/<unit>/editorial_draft_<artifact>.json" in coord
    assert "uv run python -m cycling_project.nightly editorial --campaign <slug> --unit <unit>" in coord
    assert "for `upload` to insert as a draft" not in coord
    assert coord.index("editorial_draft_<artifact>.json") < coord.index("nightly editorial --campaign")
    assert "Never merge prose into a page yourself" in coord
    from cycling_project.nightly import driver as drv
    from cycling_project.nightly.run_editorial import DRAFT_GLOB
    import fnmatch
    assert fnmatch.fnmatch("editorial_draft_stage_preview.json", DRAFT_GLOB)
    assert "editorial" in drv.build_parser()._subparsers._group_actions[0].choices


def test_the_coordinator_dispatches_route_research_from_the_plan(pv, env):
    """Chip Z1 (2026-10-02): the plan's `route_research` units get one researcher task each,
    before the campaign thread runs; the reader itself never gets web tools."""
    p = pv.plan(env)
    coord = p["agents"]["nightly-coordinator"]["system"]
    assert "`route_research`" in coord and "route-researcher" in coord
    assert "predictions/<unit>/route_raw.json" in coord
    assert "ingest-route performance_eval/<slug> <unit> --dry-run" in coord
    assert "route-researcher" in p["agents"]["nightly-coordinator"]["multiagent"]["agents"]
    researcher = p["agents"]["route-researcher"]["system"]
    assert "researched_by" in researcher and "never the race" in researcher
    assert "data about a bike race" in researcher


def test_agent_order_leaves_first_and_roster_resolves(pv, env):
    p = pv.plan(env)
    order = p["agent_order"]
    assert order[-1] == "nightly-coordinator"
    assert set(order[:-1]) == {"uci-acquirer", "route-researcher", "day-key-reader", "editorial", "ops-triage"}
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
    assert enabled(a["uci-acquirer"]) == {"bash", "read", "glob"}              # deterministic CLI runner: no write, no web
    # route research (chip Z1): the web, one file, and no bash — a page that tries to instruct it
    # cannot run a command or reach the vaulted Supabase key
    assert enabled(a["route-researcher"]) == {"web_search", "web_fetch", "write", "read"}
    coord = enabled(a["nightly-coordinator"])
    assert "bash" in coord and "web_fetch" not in coord and "web_search" not in coord
    # judgment agents on Opus 5.5; the one-command UCI runner on Sonnet 5.5 (2026-10-02)
    expected = {"uci-acquirer": "claude-sonnet-5-5"}
    for name, spec in a.items():
        assert spec["model"]["id"] == expected.get(name, "claude-opus-5-5"), name


def test_no_agent_can_fetch_procyclingstats(pv, env):
    """Chip X (2026-09-22): PCS has 403ed Anthropic's fetcher since 2026-09-06. The cloud roster
    no longer carries an agent that could try, and the coordinator prompt no longer mentions it —
    a dead path described as live cost the 2026-09-22 coordinator ten tool calls."""
    p = pv.plan(env)
    assert "pcs-acquirer" not in p["agents"]
    roster = p["agents"]["nightly-coordinator"]["multiagent"]["agents"]
    assert "pcs-acquirer" not in roster
    # The only place the domain may appear is a blocklist (route-researcher, chip Z1): it keeps
    # the web tools from spending budget on a wall, it never enables anything.
    def without_blocklists(node):
        if isinstance(node, dict):
            return {k: without_blocklists(v) for k, v in node.items() if k != "blocked_domains"}
        if isinstance(node, list):
            return [without_blocklists(v) for v in node]
        return node
    blob = json.dumps(without_blocklists(p["agents"]), default=str).lower()
    assert "procyclingstats" not in blob
    for spec in p["agents"].values():
        for ts in spec.get("tools") or []:
            for cfg in ts.get("configs") or []:
                assert not any("procyclingstats" in d for d in cfg.get("allowed_domains") or [])
    coord = p["agents"]["nightly-coordinator"]["system"].lower()
    assert "pcs" not in coord and "procyclingstats" not in coord
    assert "uci is the only results source" in coord
    assert "uci_url_needed" in p["agents"]["nightly-coordinator"]["system"]
    # the yaml survives outside the provisioned directory, for the attended Mac path
    retired = MANAGED / "retired" / "pcs-acquirer.agent.yaml"
    assert retired.exists() and "RETIRED 2026-09-22" in retired.read_text()
    assert not (MANAGED / "agents" / "pcs-acquirer.agent.yaml").exists()


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
    assert d["budget"] == {"type": "limit", "max_list_cost": {"amount": "2500", "currency": "USD"}}
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
