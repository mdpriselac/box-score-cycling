"""One rule for a campaign's public page filenames (chip W, 2026-09-22).

Before this module the rule lived in three places and disagreed: the page
builders (``build_stage_page.py`` / ``build_gc_tracker.py`` /
``build_site_index.py``) derived a filename prefix from the campaign
directory name, while the driver read ``campaign.json`` ``site.prefix`` and
fell back to ``""`` — the Tour de France's prefix — for every campaign that
had none.  On 2026-09-21 Okolo Slovenska stage 5 therefore staged the Tour's
``stage05.html`` under its own run (hosted task 113).

Every caller — builders, site index, driver — now asks here.  The rule:

1. an explicit ``site.prefix`` (a per-stage config's ``site`` over the
   campaign's ``campaign.json`` ``site``) wins, even when it is ``""``;
2. otherwise the two campaigns published before campaign.json carried a
   ``site`` block keep their historical prefixes (``LEGACY_PREFIXES``), so
   nothing already published moves;
3. otherwise a stage race is namespaced by its campaign directory name
   (``cro-race-2026-stage01.html``) and a one-day race has no prefix at all —
   its single page is ``<route slug>-<year>.html`` (``oneday_page_name``).

Pure functions over plain dicts, so the builders (which run as scripts with
only ``PROJECT_ROOT`` on ``sys.path``) and the driver share them verbatim.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

# Campaigns published before campaign.json carried a `site` block. Their
# pages are live under these names; the rule must keep producing them even
# when the registry file is absent (an old archive, a trimmed test fixture).
LEGACY_PREFIXES: Dict[str, str] = {
    "tour-de-france-2026": "",
    "vuelta-2026": "vuelta-",
}

SITE_INDEX_NAME = "site-index.json"
FRAME_DIR = "_frame"


def _site(block: Any) -> Mapping[str, Any]:
    return block if isinstance(block, Mapping) else {}


def site_prefix(campaign_dir_name: str, registry: Optional[Mapping[str, Any]] = None,
                config: Optional[Mapping[str, Any]] = None, *,
                is_stage_race: Optional[bool] = None) -> str:
    """The filename prefix every page of this campaign carries.

    ``registry`` is the parsed ``campaign.json`` (may be ``None``/empty);
    ``config`` is an optional per-unit scenarios config whose own ``site``
    block overrides the registry's.  ``is_stage_race`` defaults to the
    registry's flag, and to ``True`` when neither says.
    """
    registry = registry or {}
    config = config or {}
    for block in (_site(config.get("site")), _site(registry.get("site"))):
        if block.get("prefix") is not None:
            return str(block["prefix"])
    if campaign_dir_name in LEGACY_PREFIXES:
        return LEGACY_PREFIXES[campaign_dir_name]
    if is_stage_race is None:
        is_stage_race = bool(registry.get("is_stage_race", True))
    return f"{campaign_dir_name}-" if is_stage_race else ""


def stage_page_name(prefix: str, stage: int) -> str:
    """``<prefix>stageNN.html``."""
    return f"{prefix}stage{int(stage):02d}.html"


def stages_index_name(prefix: str) -> str:
    """``<prefix>stages.html`` — the campaign's stage-by-stage hub."""
    return f"{prefix}stages.html"


def gc_tracker_name(prefix: str) -> str:
    """``<prefix>gc.html``."""
    return f"{prefix}gc.html"


def route_slug(campaign_dir_name: str, registry: Optional[Mapping[str, Any]] = None,
               config: Optional[Mapping[str, Any]] = None) -> str:
    """The slug in ``/race/<slug>/<year>`` and in a one-day page's filename.

    ``site.route_slug`` when set; else the campaign slug with its ``-<year>``
    suffix removed.
    """
    registry = registry or {}
    config = config or {}
    for block in (_site(config.get("site")), _site(registry.get("site"))):
        if block.get("route_slug"):
            return str(block["route_slug"])
    slug = str(registry.get("slug") or campaign_dir_name)
    year = registry.get("year") or config.get("year")
    if year and slug.endswith(f"-{year}"):
        slug = slug[: -len(f"-{year}")]
    return slug


def oneday_page_name(campaign_dir_name: str, registry: Optional[Mapping[str, Any]] = None,
                     config: Optional[Mapping[str, Any]] = None, *,
                     year: Optional[int] = None) -> str:
    """``<route slug>-<year>.html`` — a one-day race's single page."""
    registry = registry or {}
    config = config or {}
    y = year if year is not None else (config.get("year") or registry.get("year") or 0)
    return f"{route_slug(campaign_dir_name, registry, config)}-{int(y)}.html"


def is_frame_path(rel_posix: str) -> bool:
    """Pages shared by every campaign: the site index and the frame directory."""
    return rel_posix == SITE_INDEX_NAME or rel_posix.startswith(f"{FRAME_DIR}/")
