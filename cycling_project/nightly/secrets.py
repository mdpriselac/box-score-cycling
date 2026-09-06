"""Local credential loading for nightly tooling and the weekly Mac run.

Convention (see CLAUDE.md "Credentials"):

* ``~/.config/cycling-project/env``          non-secret shared settings
  (a copy of the repo ``.env``: DB_PATH, SCRAPER_*), so git worktrees that
  lack the gitignored ``.env`` still work.
* ``~/.config/cycling-project/secrets.env``  secrets (chmod 600). Never
  committed, never copied into the repo, never printed.

Precedence: an already-exported environment variable wins; then the repo
``.env`` next to the project root; then the two files above. Nothing here
ever writes a value back to disk.

In the Managed Agents cloud container the secret values are vault
placeholders injected by Anthropic, so the same variable names are used and
``load_local_env`` is a harmless no-op there (the files do not exist).
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

CONFIG_DIR = Path(os.environ.get("CYCLING_CONFIG_DIR", Path.home() / ".config" / "cycling-project"))
PROJECT_ROOT = Path(__file__).resolve().parents[2]

_SECRET_NAMES = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_WEBHOOK_SIGNING_KEY",
    "SUPABASE_SECRET_KEY",
    "SUPABASE_DB_PASSWORD",
    "SUPABASE_JWT_SECRET",
    "SUPABASE_NIGHTLY_KEY",
    "SUPABASE_RELEASE_READER_KEY",
    "CLOUDFLARE_API_TOKEN",
    "PUSHOVER_TOKEN",
)


def load_local_env(*, require: tuple[str, ...] = ()) -> dict[str, str]:
    """Load settings + secrets into ``os.environ`` without overriding
    anything already set. Returns the names that were loaded (never values).

    ``require`` lists variables that must be non-empty afterwards; a
    ``RuntimeError`` names the missing ones (values are never echoed).
    """
    loaded: dict[str, str] = {}
    for path in (PROJECT_ROOT / ".env", CONFIG_DIR / "env", CONFIG_DIR / "secrets.env"):
        if path.exists():
            before = set(os.environ)
            load_dotenv(path, override=False)
            for name in set(os.environ) - before:
                loaded[name] = str(path)
    missing = [n for n in require if not os.environ.get(n)]
    if missing:
        raise RuntimeError(
            "missing credentials: " + ", ".join(missing)
            + f" — fill them in {CONFIG_DIR / 'secrets.env'} (see CLAUDE.md 'Credentials')"
        )
    return loaded


def redact(text: str) -> str:
    """Replace any known secret value appearing in ``text`` with ``***``."""
    for name in _SECRET_NAMES:
        value = os.environ.get(name)
        if value and len(value) >= 8:
            text = text.replace(value, "***")
    return text


if __name__ == "__main__":  # `uv run python -m cycling_project.nightly.secrets`
    names = load_local_env()
    present = sorted(n for n in os.environ if n.startswith(("ANTHROPIC_", "SUPABASE_", "CLOUDFLARE_", "NTFY_", "PUSHOVER_")))
    for n in present:
        print(f"{n:<32} {'set' if os.environ.get(n) else 'EMPTY'}")
    print(f"config dir: {CONFIG_DIR}")
