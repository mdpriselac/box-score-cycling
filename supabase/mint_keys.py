#!/usr/bin/env python3
"""Mint the nightly_agent / release_reader / operator keys.

    uv run python supabase/mint_keys.py nightly_agent --jwk ~/.config/cycling-project/supabase_signing_key.json
    uv run python supabase/mint_keys.py nightly_agent --hs256                 # hosted, legacy JWT secret
    uv run python supabase/mint_keys.py nightly_agent --local --valid-for 12h # local `supabase start`
    … | pbcopy         # the token is printed ONCE on stdout; everything else goes to stderr

Then store it (Keychain / the Anthropic vault) and, for the Mac's own copy,
paste it into ~/.config/cycling-project/secrets.env as SUPABASE_NIGHTLY_KEY
or SUPABASE_RELEASE_READER_KEY. Nothing here writes to disk. With --verify the
script calls public.whoami() and refuses to print a token that does not run
as the requested role.

Mechanics: see cycling_project/nightly/keys.py and supabase/README.md.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cycling_project.nightly import keys  # noqa: E402
from cycling_project.nightly.secrets import load_local_env  # noqa: E402


def _err(msg: str) -> None:
    print(msg, file=sys.stderr)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("role", choices=keys.ROLES)
    ap.add_argument("--valid-for", default="365d", help="365d (default), 90d, 12h, …")
    how = ap.add_mutually_exclusive_group()
    how.add_argument("--jwk", type=Path, help="ES256 private JWK from `supabase gen signing-key` (imported in the project)")
    how.add_argument("--hs256", action="store_true", help="sign with SUPABASE_JWT_SECRET (legacy secret)")
    how.add_argument("--local", action="store_true", help="sign for the local stack (`supabase status` JWT secret)")
    ap.add_argument("--verify", action="store_true", help="call public.whoami() before printing")
    ap.add_argument("--url", help="override SUPABASE_URL (local defaults to the stack's API_URL)")
    ap.add_argument("--apikey", help="override the publishable key used for --verify")
    args = ap.parse_args(argv)

    load_local_env()
    url = args.url or os.environ.get("SUPABASE_URL", "")
    apikey = args.apikey or os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")

    try:
        if args.local:
            env = keys.local_stack_env(ROOT)
            if not env.get("JWT_SECRET"):
                _err("no local stack: run `supabase start` in the repo first")
                return 2
            url = args.url or env.get("API_URL", url)
            apikey = args.apikey or env.get("PUBLISHABLE_KEY") or env.get("ANON_KEY", apikey)
            token = keys.mint_hs256(args.role, env["JWT_SECRET"], args.valid_for)
            how_signed = "HS256 (local stack secret)"
        elif args.hs256:
            secret = os.environ.get("SUPABASE_JWT_SECRET", "")
            if not secret:
                _err("SUPABASE_JWT_SECRET is empty: copy the legacy JWT secret from "
                     "Project Settings → API → JWT Settings into secrets.env, or use --jwk")
                return 2
            token = keys.mint_hs256(args.role, secret, args.valid_for,
                                    issuer="supabase", project_ref=os.environ.get("SUPABASE_PROJECT_REF") or None)
            how_signed = "HS256 (legacy project secret)"
        else:
            jwk = args.jwk or Path(os.environ.get("SUPABASE_SIGNING_KEY_PATH",
                                                  "~/.config/cycling-project/supabase_signing_key.json"))
            token = keys.mint_es256_with_cli(args.role, jwk, args.valid_for)
            how_signed = f"ES256 ({Path(jwk).expanduser()})"
    except keys.KeyError_ as exc:
        _err(f"error: {exc}")
        return 2

    _, claims = keys.decode_unverified(token)
    exp = dt.datetime.fromtimestamp(claims["exp"], dt.timezone.utc)
    _err(f"role={claims['role']}  signed={how_signed}  expires={exp:%Y-%m-%d %H:%MZ}")

    if args.verify:
        if not url or not apikey:
            _err("--verify needs SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY (or --url/--apikey)")
            return 2
        try:
            ran_as = keys.whoami(url, token, apikey)
        except keys.KeyError_ as exc:
            _err(f"verify failed: {exc}")
            return 3
        if ran_as != args.role:
            _err(f"verify failed: the API ran the token as {ran_as!r}, not {args.role!r} — "
                 "is the signing key imported and 0002_roles.sql applied?")
            return 3
        _err(f"verified: whoami() = {ran_as}")

    print(token)
    _err("store it now (Keychain / Anthropic vault); it will not be shown again")
    return 0


if __name__ == "__main__":
    sys.exit(main())
