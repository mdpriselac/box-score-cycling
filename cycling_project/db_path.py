"""Single resolver for the SQLite database path.

Every module that used to compute
``<repo>/cycling_project/webscrape_tools/database/database/cycling_races.db``
on its own now asks :func:`default_db_path`, so one environment variable
redirects the whole serving stack:

* ``CYCLING_DB_PATH`` — absolute (or cwd-relative) path to a SQLite file.
  Set by ``nightly bootstrap`` to point serving at ``inference_slice.db``
  in the cloud container, and by the slice parity check on the Mac.

``DB_PATH`` is deliberately NOT consulted here: in the repo ``.env`` it names
the scraped-pickle directory, and several legacy ``_find_database`` helpers
already treat it as a file-or-directory fallback. ``CYCLING_DB_PATH`` is
file-only and wins over every other rule.

Resolution is lazy (a function, not an import-time constant) so tests can
set the variable after import; module-level defaults that call it at import
time still see the value when the process started with it exported.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Union

ENV_VAR = "CYCLING_DB_PATH"

_REPO_DEFAULT = (
    Path(__file__).resolve().parent
    / "webscrape_tools" / "database" / "database" / "cycling_races.db"
)


def repo_default_db_path() -> Path:
    """The checked-out repository's database location (ignores the env)."""
    return _REPO_DEFAULT


def default_db_path() -> Path:
    """``CYCLING_DB_PATH`` when set and non-empty, else the repo default."""
    override = os.environ.get(ENV_VAR)
    if override:
        return Path(override).expanduser()
    return _REPO_DEFAULT


def resolve_db_path(explicit: Optional[Union[str, Path]] = None) -> str:
    """An explicit caller-supplied path wins; otherwise :func:`default_db_path`.

    Returns a ``str`` because every ``sqlite3.connect`` call site in the
    project passes strings.
    """
    if explicit:
        return str(explicit)
    return str(default_db_path())
