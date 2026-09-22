"""Which campaigns the unattended nightly covers — one rule, one place.

Owner decision, 2026-09-22.  The automation covers **WorldTour and .Pro**
races.  A `.1` race (``category: d1``) stays registerable, bundled and
runnable by hand on the Mac, but it is not *due* for the cloud tick unless the
owner opts it in.

The evidence: of the eleven races that caused trouble in the first week of
unattended running, eight were `.1`, and every `.1` failure was about the
outside world rather than the code — FirstCycling never published a start list
(Giro della Romagna, Kampioenschap van Vlaanderen), no earlier edition existed
in the database (Giro di Campania), no UCI calendar listing (Romagna), riders
nobody could identify (Matteotti, Okolo Slovenska, Huangshan).  `.1` races are
18 of the 31 campaigns on disk and 9 of October's 20 calendar rows, so the rule
roughly halves the nightly workload and the cloud spend.

The one escape hatch is per campaign, in ``campaign.json``::

    "automation": "on"    # cover this .1 race anyway
    "automation": "off"   # leave this WT/.Pro race to a human

A campaign with no ``category`` at all is NOT automated: the registry always
writes one, so a missing category means a hand-made or half-written file and
the honest answer is "a human should look at this".
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

# The canonical spellings live in registry.CATEGORIES — ("wt", "pro", "d1").
# They are repeated as a literal here on purpose: importing the registry would
# drag the whole calendar merge into the driver's import graph.
KNOWN_TIERS: Tuple[str, ...] = ("wt", "pro", "d1")

#: Tiers the unattended nightly covers by default.
AUTOMATION_TIERS: Tuple[str, ...] = ("wt", "pro")

#: Everything else — registerable, runnable by hand, never due on its own.
ATTENDED_TIERS: Tuple[str, ...] = tuple(t for t in KNOWN_TIERS if t not in AUTOMATION_TIERS)

_OVERRIDE_ON = {"on", "yes", "true", "1", "always"}
_OVERRIDE_OFF = {"off", "no", "false", "0", "never"}


def _cfg(campaign_cfg: Any) -> Dict[str, Any]:
    """Accept a campaign.json dict or anything carrying one as ``.cfg``."""
    if campaign_cfg is None:
        return {}
    if isinstance(campaign_cfg, Mapping):
        return dict(campaign_cfg)
    inner = getattr(campaign_cfg, "cfg", None)
    return dict(inner) if isinstance(inner, Mapping) else {}


def category_of(campaign_cfg: Any) -> Optional[str]:
    """The campaign's tier in canonical spelling, or None when it has none."""
    raw = _cfg(campaign_cfg).get("category")
    value = str(raw).strip().lower() if raw not in (None, "") else ""
    return value or None


def automation_override(campaign_cfg: Any) -> Optional[bool]:
    """``campaign.json``'s explicit ``automation`` flag, or None when absent.

    Anything unrecognised is treated as absent: a typo must not silently switch a
    race on or off.  It is not logged either — the shared logger writes to stdout,
    which is ``nightly plan``'s JSON channel — so ``override_note`` carries it into
    the plan payload instead.
    """
    raw = _cfg(campaign_cfg).get("automation")
    if raw is None or raw == "":
        return None
    if isinstance(raw, bool):
        return raw
    value = str(raw).strip().lower()
    if value in _OVERRIDE_ON:
        return True
    if value in _OVERRIDE_OFF:
        return False
    return None


def override_note(campaign_cfg: Any) -> Optional[str]:
    """A one-line warning when ``automation`` is present but unreadable, else None."""
    raw = _cfg(campaign_cfg).get("automation")
    if raw in (None, "") or automation_override(campaign_cfg) is not None:
        return None
    return (f"campaign.json automation={raw!r} is not on/off; the override was ignored "
            f"and the category decides")


def is_automated(campaign_cfg: Any, *, tiers: Optional[Sequence[str]] = None) -> bool:
    """True when the unattended nightly should treat this campaign as due.

    ``tiers`` widens the covered set for an attended Mac run (``--all-tiers``
    passes every known tier).
    """
    override = automation_override(campaign_cfg)
    if override is not None:
        return override
    category = category_of(campaign_cfg)
    if category is None:
        # Deliberately silent: the driver's `plan` prints JSON on stdout and the shared
        # logger writes there too, so a log line here would corrupt the plan the
        # coordinator parses.  The reason travels in `skip_reason` instead.
        return False
    covered = tuple(tiers) if tiers is not None else AUTOMATION_TIERS
    return category in covered


def skip_reason(campaign_cfg: Any, *, tiers: Optional[Sequence[str]] = None) -> Optional[str]:
    """Why this campaign is not automated, in one line, or None when it is.

    The string lands in the plan JSON as ``skipped``, so the coordinator's
    per-campaign ``plan`` call says why nothing is due without a prompt change.
    """
    if is_automated(campaign_cfg, tiers=tiers):
        return None
    if automation_override(campaign_cfg) is False:
        return "not_automated: automation off in campaign.json"
    category = category_of(campaign_cfg)
    if category is None:
        return "not_automated: campaign.json has no category"
    return f"not_automated: category {category}"


def resolve_tiers(*, include: Optional[Sequence[str]] = None,
                  all_tiers: bool = False) -> Tuple[str, ...]:
    """The covered tier set for one invocation: default, ``--include-tier`` or all."""
    if all_tiers:
        return KNOWN_TIERS
    extra = tuple(str(t).strip().lower() for t in (include or ()) if str(t).strip())
    return AUTOMATION_TIERS + tuple(t for t in extra if t not in AUTOMATION_TIERS)


def add_tier_flags(parser: Any) -> Any:
    """``--include-tier`` / ``--all-tiers`` on an argparse parser (Mac use)."""
    parser.add_argument("--include-tier", action="append", default=None, metavar="TIER",
                        help="also treat this category as automated (repeatable; e.g. d1)")
    parser.add_argument("--all-tiers", action="store_true",
                        help="treat every category as automated (attended Mac runs)")
    return parser


def tiers_from_args(args: Any) -> Tuple[str, ...]:
    return resolve_tiers(include=getattr(args, "include_tier", None),
                         all_tiers=bool(getattr(args, "all_tiers", False)))
