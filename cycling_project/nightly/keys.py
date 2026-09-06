"""Mint role-scoped JWTs for the Supabase control plane (spec §1a / §2.12).

Why JWTs and not Supabase API keys
----------------------------------
Under the current Supabase key model (docs checked 2026-09) a project has
publishable keys (``sb_publishable_…`` → role ``anon``/``authenticated``) and
secret keys (``sb_secret_…`` → ``service_role``, bypasses RLS). Neither can be
bound to a custom Postgres role. PostgREST and Storage, however, ``SET ROLE``
to the ``role`` claim of the JWT on ``Authorization: Bearer`` as long as that
role is granted to ``authenticator`` (0002_roles.sql does that). So a key for
``nightly_agent`` / ``release_reader`` / ``operator`` is a JWT whose payload is
``{"role": <role>, "iat": …, "exp": …}`` signed with one of the project's
signing keys. The gateway still wants a publishable key on the ``apikey``
header alongside it (store.py sends both).

Two signing paths:

* **ES256 (recommended for the hosted project)** — a private key generated
  with ``supabase gen signing-key --algorithm ES256`` and imported in the
  dashboard (Project Settings → JWT Signing Keys → import as standby, then
  rotate to current). Signing is delegated to ``supabase gen bearer-jwt`` so
  this package needs no cryptography dependency. The JWK never leaves the
  Mac; keep it in ``~/.config/cycling-project/``.
* **HS256 (local stack, or hosted projects still on the legacy JWT secret)**
  — signed here with ``hmac`` from the standard library. The local stack
  started by ``supabase start`` accepts HS256 with the JWT secret printed by
  ``supabase status -o env``.

Nothing in this module writes a token to disk or logs one.
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

ROLES = ("nightly_agent", "release_reader", "operator")

_DURATION_RE = re.compile(r"^\s*(\d+)\s*([smhdwy]?)\s*$", re.IGNORECASE)
_UNIT_SECONDS = {"": 1, "s": 1, "m": 60, "h": 3600, "d": 86400, "w": 7 * 86400, "y": 365 * 86400}


class KeyError_(RuntimeError):
    """Minting failed (bad input, missing tool); never carries a secret."""


def parse_duration(text: str | int | float | dt.timedelta) -> dt.timedelta:
    """``'365d'``, ``'12h'``, ``'30m'``, ``'3600'`` (seconds) → timedelta."""
    if isinstance(text, dt.timedelta):
        return text
    if isinstance(text, (int, float)):
        return dt.timedelta(seconds=float(text))
    m = _DURATION_RE.match(str(text))
    if not m:
        raise KeyError_(f"bad duration {text!r}: use e.g. 365d, 12h, 30m or seconds")
    return dt.timedelta(seconds=int(m.group(1)) * _UNIT_SECONDS[m.group(2).lower()])


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def build_claims(role: str, valid_for: str | dt.timedelta = "365d", *,
                 issuer: Optional[str] = None, project_ref: Optional[str] = None,
                 extra: Optional[Dict[str, Any]] = None,
                 now: Optional[dt.datetime] = None) -> Dict[str, Any]:
    """The payload every minted key carries. ``role`` must be one of ROLES."""
    if role not in ROLES:
        raise KeyError_(f"role must be one of {ROLES}, not {role!r}")
    now = now or dt.datetime.now(dt.timezone.utc)
    claims: Dict[str, Any] = {
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + parse_duration(valid_for)).timestamp()),
    }
    if issuer:
        claims["iss"] = issuer
    if project_ref:
        claims["ref"] = project_ref
    if extra:
        for k in ("role", "exp", "iat"):
            if k in extra:
                raise KeyError_(f"extra claims may not override {k!r}")
        claims.update(extra)
    return claims


def mint_hs256(role: str, secret: str, valid_for: str | dt.timedelta = "365d", **claim_kw: Any) -> str:
    """Sign a role JWT with the project's (legacy / local) HS256 JWT secret."""
    if not secret or len(secret) < 32:
        raise KeyError_("JWT secret missing or shorter than 32 characters")
    header = {"alg": "HS256", "typ": "JWT"}
    payload = build_claims(role, valid_for, **claim_kw)
    signing_input = _b64url(json.dumps(header, separators=(",", ":")).encode()) + "." + \
        _b64url(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    sig = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    return signing_input + "." + _b64url(sig)


def verify_hs256(token: str, secret: str) -> Dict[str, Any]:
    """Check the signature and expiry of an HS256 token; returns its claims."""
    try:
        h, p, s = token.split(".")
    except ValueError as exc:
        raise KeyError_("not a JWT") from exc
    expected = hmac.new(secret.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(_b64url(expected), s):
        raise KeyError_("signature mismatch")
    claims = json.loads(_b64url_decode(p))
    if claims.get("exp", 0) < dt.datetime.now(dt.timezone.utc).timestamp():
        raise KeyError_("token expired")
    return claims


def decode_unverified(token: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Header and payload without signature verification (for display only)."""
    parts = token.split(".")
    if len(parts) != 3:
        raise KeyError_("not a JWT")
    return json.loads(_b64url_decode(parts[0])), json.loads(_b64url_decode(parts[1]))


def mint_es256_with_cli(role: str, jwk_path: Path, valid_for: str | dt.timedelta = "365d",
                        *, extra: Optional[Dict[str, Any]] = None,
                        supabase_bin: Optional[str] = None) -> str:
    """Sign with an ES256 private JWK via ``supabase gen bearer-jwt``.

    The CLI reads the JWK from stdin ("Enter your signing key in JWK format")
    and prints the token. ``jwk_path`` is the file written from
    ``supabase gen signing-key --algorithm ES256``; it must already be
    imported into the project (README "Minting keys").
    """
    if role not in ROLES:
        raise KeyError_(f"role must be one of {ROLES}, not {role!r}")
    exe = supabase_bin or shutil.which("supabase")
    if not exe:
        raise KeyError_("supabase CLI not on PATH (brew install supabase/tap/supabase)")
    jwk_path = Path(jwk_path).expanduser()
    if not jwk_path.is_file():
        raise KeyError_(f"signing key file not found: {jwk_path}")
    jwk = json.loads(jwk_path.read_text())
    if isinstance(jwk, list):                       # `gen signing-key --append` writes a list
        jwk = jwk[0]
    if jwk.get("alg") != "ES256" or "d" not in jwk:
        raise KeyError_("JWK is not an ES256 private key")
    hours = max(1, int(parse_duration(valid_for).total_seconds() // 3600))
    cmd = [exe, "gen", "bearer-jwt", "--role", role, "--valid-for", f"{hours}h"]
    if extra:
        cmd += ["--payload", json.dumps(extra)]
    proc = subprocess.run(cmd, input=json.dumps(jwk) + "\n", capture_output=True, text=True,
                          cwd=str(jwk_path.parent), env={**os.environ, "NO_COLOR": "1"})
    token = next((tok for tok in re.findall(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+",
                                            proc.stdout + "\n" + proc.stderr)), None)
    if proc.returncode != 0 or not token:
        raise KeyError_(f"supabase gen bearer-jwt failed (exit {proc.returncode}); "
                        "run it by hand to see the prompt")
    header, payload = decode_unverified(token)
    if header.get("alg") != "ES256" or payload.get("role") != role:
        raise KeyError_("CLI returned an unexpected token")
    return token


def whoami(url: str, token: str, apikey: str, timeout: float = 20.0) -> str:
    """Ask the API which Postgres role a token runs as (public.whoami())."""
    import requests  # local import: keys.py must stay importable without network deps

    headers = {"apikey": apikey, "Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = requests.post(url.rstrip("/") + "/rest/v1/rpc/whoami", headers=headers, json={}, timeout=timeout)
    if r.status_code >= 400:
        raise KeyError_(f"whoami failed: HTTP {r.status_code} {r.text[:200]}")
    return r.json()


def local_stack_env(workdir: Optional[Path] = None) -> Dict[str, str]:
    """``supabase status -o env`` as a dict, or {} when no local stack runs."""
    exe = shutil.which("supabase")
    if not exe:
        return {}
    cmd = [exe, "status", "-o", "env"]
    if workdir:
        cmd += ["--workdir", str(workdir)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except (subprocess.TimeoutExpired, OSError):
        return {}
    if proc.returncode != 0:
        return {}
    out: Dict[str, str] = {}
    for line in proc.stdout.splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"')
    return out
