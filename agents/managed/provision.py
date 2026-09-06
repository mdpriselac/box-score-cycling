#!/usr/bin/env python3
"""Provision the nightly Managed Agents deployment from the YAML in this directory.

Create-or-update by name, in dependency order: environment → vault (+ credential) → leaf agents →
coordinator (roster pinned to the leaf versions) → deployment (pinned to the coordinator version,
created PAUSED, never unpaused here). Every resource carries ``metadata.spec_sha256``; a resource
whose stored hash equals the rendered spec's hash is skipped, so re-running is a no-op (``--force``
re-applies). Agents are never archived; the user's original agent (PROTECTED_AGENT_IDS) is never
touched.

Credentials: the ``ant auth login`` profile by default. ``ANTHROPIC_API_KEY`` from the environment
or ``~/.config/cycling-project/secrets.env`` is deliberately IGNORED unless ``--api-key`` is passed,
because that key is scoped to a different workspace than the profile (it cannot see the existing
agent). The Supabase nightly key is read from ``SUPABASE_NIGHTLY_KEY`` (secrets.env) at provision
time, sent write-only to the Vaults API, and never written anywhere. A leak check refuses to send any
rendered document that contains a known secret value.

Usage::

    uv run --group agents python agents/managed/provision.py --dry-run     # render + plan, no API calls
    uv run --group agents python agents/managed/provision.py               # apply, writes ids.json
    uv run --group agents python agents/managed/provision.py --rotate-key  # push the current SUPABASE_NIGHTLY_KEY
    uv run --group agents python agents/managed/provision.py --only agents # one resource class
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

import yaml

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from cycling_project.nightly import secrets as _secrets  # noqa: E402

PROTECTED_AGENT_IDS = frozenset({"agent_01EXAMPLE466A1EFA1DEDA25"})   # "Procycling Stats Extractor"
VAULT_SECRET_ENV = "SUPABASE_NIGHTLY_KEY"
NEVER_VAULT = ("SUPABASE_SECRET_KEY", "SUPABASE_DB_PASSWORD", "SUPABASE_JWT_SECRET", "ANTHROPIC_API_KEY",
               "CLOUDFLARE_API_TOKEN", "SUPABASE_RELEASE_READER_KEY")
TEMPLATE_KEYS = ("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_HOST", "STAGE0")
MANAGED_BY = "agents/managed/provision.py"
IDS_PATH = HERE / "ids.json"
FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.S)
PLACEHOLDER_RE = re.compile(r"\{\{([A-Z0-9_]+)\}\}")


class ProvisionError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------

def spec_hash(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:32]


def template_context(env: Dict[str, str]) -> Dict[str, str]:
    url = env.get("SUPABASE_URL", "").rstrip("/")
    return {
        "SUPABASE_URL": url,
        "SUPABASE_PUBLISHABLE_KEY": env.get("SUPABASE_PUBLISHABLE_KEY", ""),
        "SUPABASE_HOST": urlsplit(url).hostname or "",
        "STAGE0": (HERE / "stage0.sh").read_text().rstrip("\n"),
    }


def render_text(text: str, ctx: Dict[str, str]) -> str:
    def sub(m: re.Match) -> str:
        key = m.group(1)
        if key not in TEMPLATE_KEYS:
            raise ProvisionError(f"unknown template placeholder {{{{{key}}}}} (allowed: {', '.join(TEMPLATE_KEYS)})")
        if not ctx.get(key):
            raise ProvisionError(f"template value for {key} is empty — fill it in secrets.env / env")
        return ctx[key]
    return PLACEHOLDER_RE.sub(sub, text)


def strip_frontmatter(text: str) -> str:
    return FRONTMATTER_RE.sub("", text, count=1)


def leak_check(doc: Any, env: Dict[str, str], *, label: str) -> None:
    """Refuse to send a rendered document that contains a secret value."""
    blob = json.dumps(doc, sort_keys=True, default=str) if not isinstance(doc, str) else doc
    for name in set(_secrets._SECRET_NAMES) | set(NEVER_VAULT):
        value = env.get(name)
        if value and len(value) >= 8 and value in blob:
            raise ProvisionError(f"{label}: rendered document contains the value of {name}; refusing")


def load_yaml(path: Path) -> dict:
    with open(path) as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ProvisionError(f"{path}: top level must be a mapping")
    return data


def cents(usd: str) -> str:
    """'12.00' -> '1200' (the API wants an integer minor-unit string, no float rounding)."""
    whole, _, frac = str(usd).partition(".")
    frac = (frac + "00")[:2]
    value = int(whole or "0") * 100 + int(frac)
    if value <= 0:
        raise ProvisionError(f"budget must be positive, got {usd!r}")
    return str(value)


# ---------------------------------------------------------------------------
# spec loading (pure — no API)
# ---------------------------------------------------------------------------

def load_environment_spec(path: Path = HERE / "environment.yaml") -> dict:
    spec = load_yaml(path)
    return {"name": spec["name"], "description": spec.get("description"), "config": spec["config"]}


def load_vault_spec(path: Path = HERE / "vault.yaml") -> dict:
    spec = load_yaml(path)
    creds = []
    for c in spec.get("credentials", []):
        auth = dict(c["auth"])
        if auth.get("type") != "environment_variable":
            raise ProvisionError("only environment_variable credentials are supported here")
        source = auth.pop("secret_value_from_env", None) or auth["secret_name"]
        if "secret_value" in auth:
            raise ProvisionError("vault.yaml must not carry secret_value; use secret_value_from_env")
        if source != VAULT_SECRET_ENV or auth["secret_name"] != VAULT_SECRET_ENV:
            raise ProvisionError(f"the only vaultable Supabase key is {VAULT_SECRET_ENV}")
        creds.append({"display_name": c.get("display_name"), "auth": auth, "source_env": source})
    return {"display_name": spec["display_name"], "credentials": creds}


def load_agent_specs(ctx: Dict[str, str], agents_dir: Path = HERE / "agents") -> Dict[str, dict]:
    """name -> rendered agent spec (system inlined, roster still by NAME)."""
    out: Dict[str, dict] = {}
    for path in sorted(agents_dir.glob("*.agent.yaml")):
        raw = load_yaml(path)
        system = raw.get("system")
        if raw.get("system_file"):
            sys_path = (path.parent / raw["system_file"]).resolve()
            system = sys_path.read_text()
            if raw.get("strip_frontmatter"):
                system = strip_frontmatter(system)
        if system is not None:
            system = render_text(system, ctx)
        model = raw["model"] if isinstance(raw["model"], dict) else {"id": raw["model"]}
        spec = {
            "name": raw["name"],
            "description": render_text(raw.get("description", "") or "", ctx).strip() or None,
            "model": {k: v for k, v in model.items() if k in ("id", "effort", "speed", "inference_geo")},
            "system": system,
            "tools": raw.get("tools"),
            "multiagent": raw.get("multiagent"),
            "source": str(path.relative_to(PROJECT_ROOT)),
        }
        if spec["multiagent"] and spec["multiagent"].get("type") != "coordinator":
            raise ProvisionError(f"{path}: multiagent.type must be coordinator")
        out[spec["name"]] = spec
    if not out:
        raise ProvisionError(f"no *.agent.yaml under {agents_dir}")
    return out


def agent_apply_order(specs: Dict[str, dict]) -> List[str]:
    """Leaf agents first; a coordinator after every agent its roster names."""
    leaves = [n for n, s in specs.items() if not s.get("multiagent")]
    coords = [n for n, s in specs.items() if s.get("multiagent")]
    for c in coords:
        for entry in specs[c]["multiagent"]["agents"]:
            if isinstance(entry, str) and entry not in specs:
                raise ProvisionError(f"{c}: roster names unknown agent {entry!r}")
            if isinstance(entry, str) and specs[entry].get("multiagent"):
                raise ProvisionError(f"{c}: roster member {entry!r} is itself a coordinator (depth limit 1)")
    return leaves + coords


def resolve_roster(spec: dict, ids: Dict[str, dict]) -> Optional[dict]:
    if not spec.get("multiagent"):
        return None
    roster = []
    for entry in spec["multiagent"]["agents"]:
        if isinstance(entry, dict):
            roster.append(entry)                              # {type: self}
        else:
            ref = ids[entry]
            roster.append({"type": "agent", "id": ref["id"], "version": ref["version"]})
    return {"type": "coordinator", "agents": roster}


def load_deployment_specs(path: Path = HERE / "deployments.yaml") -> dict:
    spec = load_yaml(path)
    deployments = []
    for d in spec.get("deployments", []):
        events = []
        for ev in d.get("initial_events", []):
            if ev.get("type") not in ("user.message", "system.message"):
                raise ProvisionError(f"deployment {d['name']}: unsupported initial event {ev.get('type')}")
            events.append({"type": ev["type"], "content": [{"type": "text", "text": ev["text"]}]})
        if not events:
            raise ProvisionError(f"deployment {d['name']}: initial_events must not be empty")
        if d.get("resources"):
            raise ProvisionError(f"deployment {d['name']}: resources are not allowed (no github_repository, no files)")
        deployments.append({
            "name": d["name"],
            "description": d.get("description"),
            "agent": d["agent"],
            "environment": d["environment"],
            "vaults": list(d.get("vaults", [])),
            "schedule": {"type": "cron", "expression": d["schedule"]["expression"], "timezone": d["schedule"]["timezone"]},
            "budget": {"type": "limit", "max_list_cost": {"amount": cents(d["budget_usd"]), "currency": "USD"}},
            "initial_events": events,
            "create_paused": bool(d.get("create_paused", True)),
        })
    return {"workspace_id": spec.get("workspace_id"), "deployments": deployments}


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def make_client(*, use_api_key: bool, workspace_id: Optional[str]):
    import anthropic
    if not use_api_key:
        os.environ.pop("ANTHROPIC_API_KEY", None)
    headers = {"anthropic-workspace-id": workspace_id} if workspace_id else {}
    return anthropic.Anthropic(default_headers=headers)


def _find(page_iter, key: str, value: str):
    for item in page_iter:
        if getattr(item, key, None) == value and getattr(item, "archived_at", None) is None:
            return item
    return None


def _meta(spec_sha: str, source: str, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    m = {"managed_by": MANAGED_BY, "spec_sha256": spec_sha, "source": source}
    if extra:
        m.update(extra)
    return m


def _upcoming(d) -> List[str]:
    runs = getattr(getattr(d, "schedule", None), "upcoming_runs_at", None) or []
    return [r.isoformat() if hasattr(r, "isoformat") else str(r) for r in runs]


def _stored_hash(obj) -> Optional[str]:
    meta = getattr(obj, "metadata", None) or {}
    return meta.get("spec_sha256")


class Provisioner:
    def __init__(self, client, *, dry_run: bool, force: bool, env: Dict[str, str]):
        self.client = client
        self.dry_run = dry_run
        self.force = force
        self.env = env
        self.log: List[str] = []

    def say(self, msg: str) -> None:
        self.log.append(msg)
        print(_secrets.redact(msg), flush=True)

    # -- environment --------------------------------------------------------
    def environment(self, spec: dict) -> dict:
        sha = spec_hash({"config": spec["config"], "description": spec["description"]})
        leak_check(spec, self.env, label="environment")
        existing = None if self.dry_run else _find(self.client.beta.environments.list(), "name", spec["name"])
        if existing is None:
            self.say(f"environment {spec['name']}: create")
            if self.dry_run:
                return {"id": "env_DRYRUN", "name": spec["name"], "action": "create"}
            env = self.client.beta.environments.create(
                name=spec["name"], description=spec["description"], config=spec["config"],
                metadata=_meta(sha, "agents/managed/environment.yaml"))
            return {"id": env.id, "name": env.name, "action": "create"}
        if _stored_hash(existing) == sha and not self.force:
            self.say(f"environment {spec['name']}: unchanged ({existing.id})")
            return {"id": existing.id, "name": existing.name, "action": "unchanged"}
        self.say(f"environment {spec['name']}: update ({existing.id})")
        env = self.client.beta.environments.update(
            existing.id, description=spec["description"], config=spec["config"],
            metadata=_meta(sha, "agents/managed/environment.yaml"))
        return {"id": env.id, "name": env.name, "action": "update"}

    # -- vault + credential ---------------------------------------------------
    def vault(self, spec: dict, *, rotate: bool) -> dict:
        existing = None if self.dry_run else _find(self.client.beta.vaults.list(), "display_name", spec["display_name"])
        if existing is None:
            self.say(f"vault {spec['display_name']}: create")
            vault_id = "vlt_DRYRUN"
            if not self.dry_run:
                vault_id = self.client.beta.vaults.create(
                    display_name=spec["display_name"], metadata={"managed_by": MANAGED_BY}).id
            action = "create"
        else:
            vault_id, action = existing.id, "unchanged"
            self.say(f"vault {spec['display_name']}: exists ({vault_id})")

        creds: Dict[str, dict] = {}
        for c in spec["credentials"]:
            value = self.env.get(c["source_env"], "")
            if not value:
                raise ProvisionError(f"{c['source_env']} is empty — mint it (supabase/README.md §4) and fill secrets.env")
            for name in NEVER_VAULT:
                if self.env.get(name) and self.env[name] == value:
                    raise ProvisionError(f"refusing: {c['source_env']} has the same value as {name}")
            fingerprint = hashlib.sha256(value.encode()).hexdigest()[:16]
            secret_name = c["auth"]["secret_name"]
            cur = None
            if not self.dry_run and action != "create":
                for item in self.client.beta.vaults.credentials.list(vault_id):
                    auth = getattr(item, "auth", None)
                    if getattr(auth, "secret_name", None) == secret_name and getattr(item, "archived_at", None) is None:
                        cur = item
                        break
            cred_meta = {"managed_by": MANAGED_BY, "secret_fingerprint": fingerprint,
                         "role": "nightly_agent", "source": "agents/managed/vault.yaml"}
            if cur is None:
                self.say(f"credential {secret_name}: create (header-only, hosts {c['auth']['networking']['allowed_hosts']})")
                cred_id = "cred_DRYRUN"
                if not self.dry_run:
                    cred_id = self.client.beta.vaults.credentials.create(
                        vault_id, auth={**c["auth"], "secret_value": value},
                        display_name=c["display_name"], metadata=cred_meta).id
                creds[secret_name] = {"id": cred_id, "action": "create"}
                continue
            stored = (getattr(cur, "metadata", None) or {}).get("secret_fingerprint")
            if rotate or stored != fingerprint:
                self.say(f"credential {secret_name}: rotate value ({cur.id})" if stored != fingerprint
                         else f"credential {secret_name}: --rotate-key ({cur.id})")
                if not self.dry_run:
                    self.client.beta.vaults.credentials.update(
                        cur.id, vault_id=vault_id,
                        auth={"type": "environment_variable", "secret_value": value,
                              "networking": c["auth"]["networking"],
                              "injection_location": c["auth"]["injection_location"]},
                        metadata=cred_meta)
                creds[secret_name] = {"id": cur.id, "action": "rotate"}
            else:
                self.say(f"credential {secret_name}: unchanged ({cur.id})")
                creds[secret_name] = {"id": cur.id, "action": "unchanged"}
        return {"id": vault_id, "display_name": spec["display_name"], "action": action, "credentials": creds}

    # -- agents ---------------------------------------------------------------
    def agent(self, spec: dict, roster: Optional[dict]) -> dict:
        body: Dict[str, Any] = {"name": spec["name"], "model": spec["model"], "system": spec["system"],
                                "description": spec["description"]}
        if spec.get("tools") is not None:
            body["tools"] = spec["tools"]
        if roster is not None:
            body["multiagent"] = roster
        leak_check(body, self.env, label=f"agent {spec['name']}")
        sha = spec_hash(body)
        existing = None if self.dry_run else _find(self.client.beta.agents.list(), "name", spec["name"])
        if existing is not None and existing.id in PROTECTED_AGENT_IDS:
            raise ProvisionError(f"agent {spec['name']} resolves to protected agent {existing.id}; refusing")
        meta = _meta(sha, spec["source"], {"system_sha256": hashlib.sha256((spec["system"] or "").encode()).hexdigest()[:16]})
        if existing is None:
            self.say(f"agent {spec['name']}: create ({spec['model']['id']}, effort {spec['model'].get('effort', 'default')})")
            if self.dry_run:
                return {"id": f"agent_DRYRUN_{spec['name']}", "version": 1, "action": "create"}
            a = self.client.beta.agents.create(**body, metadata=meta)
            return {"id": a.id, "version": a.version, "action": "create"}
        if _stored_hash(existing) == sha and not self.force:
            self.say(f"agent {spec['name']}: unchanged ({existing.id} v{existing.version})")
            return {"id": existing.id, "version": existing.version, "action": "unchanged"}
        self.say(f"agent {spec['name']}: update ({existing.id} v{existing.version} → v{existing.version + 1})")
        a = self.client.beta.agents.update(existing.id, version=existing.version, **body, metadata=meta)
        return {"id": a.id, "version": a.version, "action": "update"}

    # -- deployment -------------------------------------------------------------
    def deployment(self, spec: dict, *, agent_ref: dict, environment_id: str, vault_ids: List[str]) -> dict:
        body: Dict[str, Any] = {
            "name": spec["name"], "description": spec["description"],
            "agent": {"type": "agent", "id": agent_ref["id"], "version": agent_ref["version"]},
            "environment_id": environment_id, "vault_ids": vault_ids,
            "schedule": spec["schedule"], "budget": spec["budget"], "initial_events": spec["initial_events"],
        }
        leak_check(body, self.env, label=f"deployment {spec['name']}")
        sha = spec_hash(body)
        existing = None if self.dry_run else _find(self.client.beta.deployments.list(), "name", spec["name"])
        meta = _meta(sha, "agents/managed/deployments.yaml")
        if existing is None:
            self.say(f"deployment {spec['name']}: create ({spec['schedule']['expression']} {spec['schedule']['timezone']}, "
                     f"budget {spec['budget']['max_list_cost']['amount']} cents){' + pause' if spec['create_paused'] else ''}")
            if self.dry_run:
                return {"id": "depl_DRYRUN", "status": "paused" if spec["create_paused"] else "active", "action": "create"}
            d = self.client.beta.deployments.create(**body, metadata=meta)
            if spec["create_paused"]:
                d = self.client.beta.deployments.pause(d.id)
            return {"id": d.id, "status": d.status, "action": "create", "upcoming_runs_at": _upcoming(d)}
        if _stored_hash(existing) == sha and not self.force:
            self.say(f"deployment {spec['name']}: unchanged ({existing.id}, {existing.status})")
            return {"id": existing.id, "status": existing.status, "action": "unchanged",
                    "upcoming_runs_at": _upcoming(existing)}
        self.say(f"deployment {spec['name']}: update ({existing.id}, stays {existing.status})")
        d = self.client.beta.deployments.update(existing.id, **body, metadata=meta)
        return {"id": d.id, "status": d.status, "action": "update", "upcoming_runs_at": _upcoming(d)}


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def plan(env: Dict[str, str]) -> dict:
    """Everything that can be computed without the API (used by --dry-run and the tests)."""
    ctx = template_context(env)
    agents = load_agent_specs(ctx)
    return {
        "environment": load_environment_spec(),
        "vault": load_vault_spec(),
        "agents": agents,
        "agent_order": agent_apply_order(agents),
        "deployments": load_deployment_specs(),
    }


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="render and plan; no API calls, no ids.json")
    ap.add_argument("--force", action="store_true", help="re-apply even when the stored spec hash matches")
    ap.add_argument("--rotate-key", action="store_true", help="push the current SUPABASE_NIGHTLY_KEY into the credential")
    ap.add_argument("--api-key", action="store_true", help="authenticate with ANTHROPIC_API_KEY instead of the ant profile")
    ap.add_argument("--workspace-id", default=None, help="override deployments.yaml workspace_id")
    ap.add_argument("--only", choices=["environment", "vault", "agents", "deployment"], default=None)
    args = ap.parse_args(argv)

    _secrets.load_local_env()
    env = dict(os.environ)
    p = plan(env)
    workspace_id = args.workspace_id or p["deployments"].get("workspace_id")

    client = None if args.dry_run else make_client(use_api_key=args.api_key, workspace_id=workspace_id)
    prov = Provisioner(client, dry_run=args.dry_run, force=args.force, env=env)
    prov.say(f"{'DRY RUN — ' if args.dry_run else ''}workspace {workspace_id or '(profile default)'}; "
             f"auth {'ANTHROPIC_API_KEY' if args.api_key else 'ant profile'}")

    ids: Dict[str, Any] = json.loads(IDS_PATH.read_text()) if IDS_PATH.exists() and not args.dry_run else {}
    ids.setdefault("agents", {})
    want = lambda k: args.only in (None, k)  # noqa: E731

    if want("environment"):
        ids["environment"] = prov.environment(p["environment"])
    if want("vault"):
        ids["vault"] = prov.vault(p["vault"], rotate=args.rotate_key)
    if want("agents"):
        for name in p["agent_order"]:
            spec = p["agents"][name]
            roster = resolve_roster(spec, ids["agents"])
            ids["agents"][name] = prov.agent(spec, roster)
    if want("deployment"):
        for d in p["deployments"]["deployments"]:
            missing = [k for k in ("environment", "vault") if k not in ids]
            if d["agent"] not in ids["agents"]:
                missing.append(d["agent"])
            if missing:
                raise ProvisionError(f"deployment {d['name']}: provision {missing} first (ids.json lacks them)")
            if ids["environment"]["name"] != d["environment"]:
                raise ProvisionError(f"deployment {d['name']}: environment {d['environment']!r} is not the provisioned one")
            vault_ids = [ids["vault"]["id"]] if d["vaults"] == [ids["vault"]["display_name"]] else None
            if vault_ids is None:
                raise ProvisionError(f"deployment {d['name']}: vaults {d['vaults']} ≠ provisioned vault")
            ids.setdefault("deployments", {})[d["name"]] = prov.deployment(
                d, agent_ref=ids["agents"][d["agent"]], environment_id=ids["environment"]["id"], vault_ids=vault_ids)

    ids["workspace_id"] = workspace_id
    ids["provisioned_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    ids["protected_agent_ids"] = sorted(PROTECTED_AGENT_IDS)
    if args.dry_run:
        print(json.dumps({k: v for k, v in ids.items()}, indent=2))
        print("dry run: nothing created; ids.json not written")
        return 0
    leak_check(ids, env, label="ids.json")
    IDS_PATH.write_text(json.dumps(ids, indent=2, sort_keys=True, default=str) + "\n")
    prov.say(f"wrote {IDS_PATH.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ProvisionError as e:
        print(f"provision: {_secrets.redact(str(e))}", file=sys.stderr)
        sys.exit(2)
