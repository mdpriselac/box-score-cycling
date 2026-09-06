"""
Daily Kambi odds capture for a stage-race or one-day campaign.

Run each morning BEFORE the stage starts — once a stage goes live/settles it
drops out of Kambi's pre-match feed and that day's stage odds are gone. The
next stage's ``Stage N`` win market is posted only around **11:00-12:40 local**
the day before, so an early run may see the classifications and nothing else;
``--wait-for-stage`` exists for exactly that.

    # campaign-driven (reads performance_eval/vuelta-2026/campaign.json)
    uv run python performance_eval/tour-de-france-2026/capture_odds.py \
        --campaign performance_eval/vuelta-2026

    # explicit, as before campaign.json existed
    uv run python performance_eval/tour-de-france-2026/capture_odds.py \
        --match "vuelta a espa" --out-root performance_eval/vuelta-2026/odds

    # wait for tomorrow's stage market to post, then capture
    uv run python performance_eval/tour-de-france-2026/capture_odds.py \
        --campaign performance_eval/vuelta-2026 --wait-for-stage 15 --until 13:00

    # just tell me the event id (cache first, network only if unknown)
    uv run python performance_eval/tour-de-france-2026/capture_odds.py \
        --campaign performance_eval/vuelta-2026 --stage 15 --print-event-id

Discovers the campaign's live events (next stage, GC, jerseys, stage-win
specials) from the Kambi cycling listView, fetches every betoffer for each,
and writes a timestamped snapshot under ``<out-root>/YYYY-MM-DD/``:

    raw/listview_HHMM.json           full cycling listView response
    raw/event_{id}_{slug}_HHMM.json  full betoffer response per event
    markets_HHMM.json                parsed markets (all betoffers, all events)
    provenance_HHMM.json             URLs, timestamps, brand, event map, overrounds
    win_odds_HHMM.csv                flat CSV of full-field win/podium/top-N
                                     markets with devigged probabilities
    degraded.json                    written only when every brand blocked

Safe to run multiple times a day (files are timestamped, nothing overwritten).
Uses stdlib only.

BRAND FALLBACK. Each Kambi brand can be geo-fenced independently, so the
brands in ``--brands`` are tried in order and the first one that answers with
a usable cycling feed wins; the brand that served the snapshot is recorded in
``provenance_*.json`` and in a ``brand`` column on the CSV. A 403, 451, 429 or
404 on the listView, or an empty event list, moves on to the next brand; 5xx
and network errors are retried with exponential backoff first. When *every*
brand blocks the run writes ``degraded.json`` into the day directory and exits
0 with ``degraded: true`` — a degraded night is a recorded fact, not a crash.

Verified live from a NL-resident home network on 2026-09-05 (Vuelta stage 15):
``ubnl``, ``ubuk`` and ``ubse`` all answer and all carry event 1028797735;
``rivers`` answers **HTTP 429 "No access"** for every lang/market tried, and
no ``na-*`` Kambi host resolves, so ``rivers`` is a dead link in the chain as
a brand code. The live BetRivers codes are per-state — ``rsiuspa`` (market PA)
and ``rsiusil`` (market IL) both returned the same Vuelta events from the same
EU host — so ``rsiuspa`` is appended after ``rivers`` in the default chain to
keep a real last resort behind the three Unibet brands.

DISCOVERY. Event names are localised per brand (the Vuelta is "Ronde van
Spanje 2026" on ``ubnl``, "Etapp 15 (Vuelta a España 2026)" on ``ubse``), so
matching runs against BOTH ``name`` and ``englishName``, accent- and
case-insensitively. If no substring matches, a fuzzy pass scores every event
in the feed against the campaign's names; a score at or above
``FUZZY_ACCEPT`` (0.95) is taken as a match, and anything below is *proposed
only* — written to ``kambi_candidates`` in campaign.json and in the run's
provenance for a human to confirm. The script never auto-accepts a fuzzy
match below the threshold.

EXIT CODES
    0  snapshot written (or degraded: every brand blocked)
    1  a brand answered with a usable feed but no event matched the campaign
       (candidates, if any, are recorded), or a bad invocation
    2  --wait-for-stage deadline passed and the stage market never posted
"""

import argparse
import csv
import difflib
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = "https://eu-offering-api.kambicdn.com/offering/v2018"
OUT_ROOT = Path(__file__).resolve().parent / "odds"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
FETCH_SLEEP_S = 1.5

# Brand code -> (lang, market) the feed expects. --lang/--market override.
BRAND_LOCALE = {
    "ubnl": ("nl_NL", "NL"),
    "ubuk": ("en_GB", "GB"),
    "ubse": ("sv_SE", "SE"),
    "rivers": ("en_US", "US"),
    "rsiuspa": ("en_US", "PA"),
    "rsiusil": ("en_US", "IL"),
}
DEFAULT_BRANDS = "ubnl,ubuk,ubse,rivers,rsiuspa"

# HTTP statuses that mean "this brand will not serve us" — move to the next.
BLOCK_STATUSES = (403, 404, 429, 451)
RETRY_ATTEMPTS = 3
RETRY_BACKOFF_S = 2.0

# At or above this a fuzzy name match is taken; below it the event is only
# ever PROPOSED for a human to confirm. Never lower this silently.
FUZZY_ACCEPT = 0.95
FUZZY_PROPOSE = 0.55

STAGE_WORDS = r"(?:stage|etappe|etapp|etape|etapa|tappa|etap)"
CLASSIFICATION_KEYS = (
    ("general classification", "gc"),
    ("points classification", "points"),
    ("mountains classification", "mountains"),
    ("young rider classification", "youth"),
    ("team classification", "teams"),
)


class BrandBlocked(Exception):
    """The brand refused us (geo-fence / unknown brand code)."""

    def __init__(self, status: int, body: str = ""):
        super().__init__(f"HTTP {status}")
        self.status = status
        self.body = body


class FetchFailed(Exception):
    """Transport or server error that survived the retries."""


# --------------------------------------------------------------------------
# HTTP


def fetch_json(url: str, *, attempts: int = RETRY_ATTEMPTS, sleep=time.sleep) -> dict:
    """GET JSON, retrying 5xx and transport errors with exponential backoff.

    A 403/404/429/451 is not retried — it is a decision by the operator, not a
    blip — and raises ``BrandBlocked`` so the caller can try the next brand.
    """
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read()[:200].decode("utf-8", "replace")
            except Exception:  # pragma: no cover - body is best-effort only
                pass
            if e.code in BLOCK_STATUSES:
                raise BrandBlocked(e.code, body) from e
            last = e
            if e.code < 500:
                raise FetchFailed(f"HTTP {e.code} {body}") from e
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
            last = e
        if attempt < attempts - 1:
            sleep(RETRY_BACKOFF_S * (2**attempt))
    raise FetchFailed(str(last))


# --------------------------------------------------------------------------
# Name handling


def normalise(text: str) -> str:
    """Casefold, strip accents and collapse whitespace, for name matching."""
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", stripped).strip().casefold()


def slugify(name: str) -> str:
    ascii_name = "".join(
        c for c in unicodedata.normalize("NFKD", name) if not unicodedata.combining(c)
    )
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]", "_", ascii_name.lower())).strip("_")


def race_token(event: dict) -> str:
    """The race part of an event name: 'Etappe 15 (Ronde van Spanje 2026)'
    -> 'Ronde van Spanje 2026'. Falls back to the whole name."""
    for field in ("name", "englishName"):
        value = event.get(field) or ""
        m = re.search(r"\(([^)]+)\)\s*$", value)
        if m:
            return m.group(1)
    return event.get("name") or event.get("englishName") or ""


def years_in(text: str) -> set[str]:
    return set(re.findall(r"\b(?:19|20)\d{2}\b", text or ""))


def year_conflict(probe: str, target: str) -> bool:
    """True when both names carry a season and they disagree.

    A one-character year difference scores about 0.95 on any string metric —
    'Ronde van Spanje 2026' against 'Ronde van Spanje 2027' — and the feed
    really does carry next season's races beside this one's (Tour de France
    2027 sat in the same listView on 2026-09-05). A season mismatch is never
    a fuzzy match, whatever it scores.
    """
    p, t = years_in(probe), years_in(target)
    return bool(p and t and not (p & t))


def similarity(probe: str, target: str) -> float:
    """Ratio in [0, 1] tolerant of a probe that is a fragment of the target.

    ``difflib``'s plain ratio punishes 'vuelta a espa' against 'Vuelta a
    España 2026' for being short, so also score the probe against the best
    same-length window of the target and take the better of the two.
    """
    p, t = normalise(probe), normalise(target)
    if not p or not t:
        return 0.0
    best = difflib.SequenceMatcher(None, p, t).ratio()
    if len(p) < len(t):
        for start in range(0, len(t) - len(p) + 1):
            window = t[start : start + len(p)]
            best = max(best, difflib.SequenceMatcher(None, p, window).ratio())
    return best


def stage_number(event: dict) -> int | None:
    for field in ("englishName", "name"):
        m = re.search(rf"\b{STAGE_WORDS}\s*(\d{{1,2}})\b", normalise(event.get(field) or ""))
        if m:
            return int(m.group(1))
    return None


def event_key(event: dict) -> str | None:
    """Stable campaign.json key for an event: 'stage_15', 'gc', 'points', ..."""
    n = stage_number(event)
    if n is not None:
        return f"stage_{n:02d}"
    english = normalise(event.get("englishName") or event.get("name") or "")
    for needle, key in CLASSIFICATION_KEYS:
        if needle in english:
            return key
    if "special" in english:
        return "specials"
    return None


def extract_events(listview: dict) -> list[dict]:
    return [item.get("event", item) for item in listview.get("events", [])]


def discover(events: list[dict], probes: list[str]) -> tuple[list[dict], list[dict]]:
    """Split the feed into (matched, proposed candidates).

    The substring pass runs first: a normalised (accent- and case-folded) hit
    on ``name`` or ``englishName`` for any probe. **Fuzzy matching is only a
    fallback** — it runs when the substring pass found nothing at all, so a
    healthy day never accumulates proposals for the other races in the feed.
    In the fallback, a score >= FUZZY_ACCEPT is taken as a match and anything
    from FUZZY_PROPOSE up is *proposed only*, for a human to confirm.
    """
    probes = [p for p in probes if p and p.strip()]
    matched = [
        ev for ev in events
        if any(normalise(p) in normalise(f"{ev.get('name', '')} | "
                                         f"{ev.get('englishName', '')}")
               for p in probes)
    ]
    if matched:
        return matched, []

    candidates = []
    for ev in events:
        token = race_token(ev)
        score, probe = max(((similarity(p, token), p) for p in probes),
                           default=(0.0, ""))
        if score >= FUZZY_ACCEPT and not year_conflict(probe, token):
            ev = dict(ev)
            ev["_fuzzy_score"] = round(score, 4)
            matched.append(ev)
        elif score >= FUZZY_PROPOSE or year_conflict(probe, token):
            candidates.append(
                {
                    "reason": ("season mismatch" if year_conflict(probe, token)
                               else "below the accept threshold"),
                    "event_id": str(ev.get("id")),
                    "name": ev.get("name"),
                    "english_name": ev.get("englishName"),
                    "race_token": token,
                    "start": ev.get("start"),
                    "stage": stage_number(ev),
                    "score": round(score, 4),
                    "probe": probe,
                }
            )
    if matched:
        # A fuzzy acceptance is worth a human glance even though it was used.
        return matched, candidates
    candidates.sort(key=lambda c: c["score"], reverse=True)
    return matched, candidates


# --------------------------------------------------------------------------
# campaign.json


def load_campaign(path: Path) -> dict:
    campaign_file = path / "campaign.json"
    if not campaign_file.exists():
        raise SystemExit(f"ERROR: no campaign.json in {path}")
    return json.loads(campaign_file.read_text())


def save_campaign(path: Path, data: dict) -> None:
    """Atomic rewrite so a concurrent reader never sees a half file."""
    campaign_file = path / "campaign.json"
    tmp = campaign_file.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    os.replace(tmp, campaign_file)


def campaign_probes(campaign: dict, explicit_match: str | None) -> list[str]:
    """The names discovery matches on.

    An explicit ``--match`` OVERRIDES the campaign's names rather than joining
    them — otherwise steering the run at one race would silently keep matching
    the campaign's own, which is the opposite of what the flag is for.
    """
    if explicit_match:
        return [explicit_match]
    probes: list[str] = []
    for value in (campaign.get("kambi_match"),
                  campaign.get("kambi_localised_name"),
                  campaign.get("name")):
        if value and value not in probes:
            probes.append(value)
    return probes


# --------------------------------------------------------------------------
# Betoffer parsing (unchanged semantics)


def book_sum_for(bet_offer_type_name: str) -> float | None:
    """Number of 'winning' places a full-field market pays — the devig target.

    'Winnaar'/'Winner' pays 1 place; '(1-3)' pays 3; '(1-10)' pays 10. Returns
    None for market types we shouldn't devig (head-to-heads, yes/no specials).
    """
    name = bet_offer_type_name.strip()
    if normalise(name) in ("winnaar", "winner", "vinnare", "vainqueur", "sieger"):
        return 1.0
    m = re.fullmatch(r"\(1-(\d+)\)", name)
    return float(m.group(1)) if m else None


def parse_betoffer(bo: dict) -> dict:
    outcomes = []
    for o in bo.get("outcomes", []):
        if o.get("odds") is None:
            continue
        outcomes.append(
            {
                "name": o.get("participant") or o.get("label"),
                "label": o.get("label"),
                "odds": o["odds"] / 1000.0,
                "implied": 1000.0 / o["odds"],
            }
        )
    parsed = {
        "betoffer_id": bo.get("id"),
        "criterion": bo.get("criterion", {}).get("label"),
        "bet_offer_type": bo.get("betOfferType", {}).get("name"),
        "outcomes": outcomes,
    }
    book_sum = book_sum_for(parsed["bet_offer_type"] or "")
    if book_sum is not None and outcomes:
        implied_sum = sum(o["implied"] for o in outcomes)
        parsed["book_sum"] = book_sum
        parsed["overround"] = round(implied_sum / book_sum, 4)
        for o in outcomes:
            o["devig"] = o["implied"] / implied_sum * book_sum
    return parsed


# --------------------------------------------------------------------------
# Brand loop


def brand_locale(brand: str, lang: str | None, market: str | None) -> tuple[str, str]:
    default_lang, default_market = BRAND_LOCALE.get(brand, ("en_GB", "GB"))
    return lang or default_lang, market or default_market


def listview_url_for(brand: str, lang: str, market: str) -> str:
    return (
        f"{BASE}/{brand}/listView/cycling.json"
        f"?lang={lang}&market={market}&useCombined=true"
    )


def try_brands(
    brands: list[str],
    probes: list[str],
    *,
    lang: str | None,
    market: str | None,
    log=print,
    sleep=time.sleep,
) -> dict:
    """Walk the brand chain. Returns a result dict with, at most, one hit.

    ``status`` is one of: ``matched`` (events found), ``no_match`` (a feed
    answered but nothing was the campaign's race) or ``degraded`` (every
    brand blocked or returned nothing at all).
    """
    attempts: list[dict] = []
    fallback: dict | None = None  # richest answering feed, for candidates
    for brand in brands:
        blang, bmarket = brand_locale(brand, lang, market)
        url = listview_url_for(brand, blang, bmarket)
        log(f"Fetching cycling listView ({brand}, {blang}/{bmarket}) ...")
        try:
            listview = fetch_json(url, sleep=sleep)
        except BrandBlocked as e:
            log(f"  blocked: HTTP {e.status} {e.body.strip()!r} — trying the next brand")
            attempts.append({"brand": brand, "outcome": "blocked", "status": e.status,
                             "body": e.body.strip()[:120]})
            continue
        except FetchFailed as e:
            log(f"  failed: {e} — trying the next brand")
            attempts.append({"brand": brand, "outcome": "error", "error": str(e)[:200]})
            continue

        events = extract_events(listview)
        if not events:
            log("  empty event list — trying the next brand")
            attempts.append({"brand": brand, "outcome": "empty_listview"})
            continue

        matched, candidates = discover(events, probes)
        if matched:
            attempts.append({"brand": brand, "outcome": "matched",
                             "events_in_feed": len(events), "matched": len(matched)})
            return {
                "status": "matched",
                "brand": brand,
                "lang": blang,
                "market": bmarket,
                "listview": listview,
                "listview_url": url,
                "events": matched,
                "candidates": candidates,
                "attempts": attempts,
            }

        best = candidates[0]["score"] if candidates else 0.0
        log(f"  {len(events)} cycling events, none matching (best fuzzy {best:.2f})")
        attempts.append({"brand": brand, "outcome": "no_match",
                         "events_in_feed": len(events), "best_score": round(best, 4)})
        if fallback is None or len(events) > len(extract_events(fallback["listview"])):
            fallback = {
                "status": "no_match",
                "brand": brand,
                "lang": blang,
                "market": bmarket,
                "listview": listview,
                "listview_url": url,
                "events": [],
                "candidates": candidates,
            }

    if fallback is not None:
        fallback["attempts"] = attempts
        return fallback
    return {"status": "degraded", "attempts": attempts, "candidates": [], "events": []}


# --------------------------------------------------------------------------
# Snapshot


def capture_snapshot(hit: dict, out_dir: Path, hhmm: str, *, log=print,
                     sleep=time.sleep) -> dict:
    """Fetch every matched event's betoffers and write the day's files."""
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / f"listview_{hhmm}.json").write_text(json.dumps(hit["listview"]))

    brand = hit["brand"]
    events = hit["events"]
    log(f"Found {len(events)} matching events on {brand}:")
    for ev in events:
        log(f"  {ev['id']}  {str(ev.get('start', '?')):>22}  {ev['name']}")

    prov = {
        "source": f"Kambi CDN, brand={brand}, lang={hit['lang']}, market={hit['market']}",
        "brand": brand,
        "lang": hit["lang"],
        "market": hit["market"],
        "brands_tried": hit["attempts"],
        "listview_url": hit["listview_url"],
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "events": {
            str(ev["id"]): {
                "name": ev["name"],
                "english_name": ev.get("englishName"),
                "start": ev.get("start"),
                "group": ev.get("group"),
                "key": event_key(ev),
                "fuzzy_score": ev.get("_fuzzy_score"),
            }
            for ev in events
        },
        "overrounds": {},
    }
    if hit.get("candidates"):
        prov["kambi_candidates"] = hit["candidates"]

    markets: dict[str, dict] = {}
    for ev in events:
        eid = ev["id"]
        slug = slugify(ev.get("englishName") or ev["name"])
        url = (f"{BASE}/{brand}/betoffer/event/{eid}.json"
               f"?lang={hit['lang']}&market={hit['market']}")
        log(f"Fetching betoffers for {ev['name']} ...")
        try:
            data = fetch_json(url, sleep=sleep)
        except (BrandBlocked, FetchFailed) as e:
            log(f"  WARNING: {e} for event {eid}, skipping")
            prov.setdefault("event_errors", {})[str(eid)] = str(e)
            continue
        (raw_dir / f"event_{eid}_{slug}_{hhmm}.json").write_text(json.dumps(data))

        parsed = [parse_betoffer(bo) for bo in data.get("betOffers", [])]
        markets[str(eid)] = {"event_name": ev["name"], "start": ev.get("start"),
                             "betoffers": parsed}
        for p in parsed:
            if "overround" in p:
                prov["overrounds"][f"{slug} | {p['criterion']} | {p['bet_offer_type']}"] = \
                    p["overround"]
        sleep(FETCH_SLEEP_S)

    (out_dir / f"markets_{hhmm}.json").write_text(json.dumps(markets, indent=1))
    (out_dir / f"provenance_{hhmm}.json").write_text(json.dumps(prov, indent=1))

    csv_path = out_dir / f"win_odds_{hhmm}.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["event", "market", "rider", "odds", "implied", "devig", "brand"])
        for _eid, m in markets.items():
            for p in m["betoffers"]:
                if "overround" not in p:
                    continue
                market_label = f"{p['criterion']} {p['bet_offer_type']}".strip()
                for o in sorted(p["outcomes"], key=lambda x: x["odds"]):
                    w.writerow([m["event_name"], market_label, o["name"], o["odds"],
                                round(o["implied"], 5), round(o["devig"], 5), brand])

    log(f"\nSaved snapshot to {out_dir}  (timestamp {hhmm}, brand {brand})")
    if prov["overrounds"]:
        log("Overrounds:")
        for k, v in prov["overrounds"].items():
            log(f"  {v:6.3f}  {k}")

    return {
        "markets_file": f"markets_{hhmm}.json",
        "provenance_file": f"provenance_{hhmm}.json",
        "csv_file": f"win_odds_{hhmm}.csv",
        "event_ids": {k: v for k, v in
                      ((event_key(ev), str(ev["id"])) for ev in events) if k},
        "events": len(markets),
        "overrounds": prov["overrounds"],
    }


def write_degraded(out_dir: Path, attempts: list[dict], probes: list[str],
                   hhmm: str) -> Path:
    """Every brand blocked. Record it; the night continues without a book."""
    out_dir.mkdir(parents=True, exist_ok=True)
    prior = sorted(p.name for p in out_dir.glob("markets_*.json"))
    payload = {
        "degraded": True,
        "reason": "every brand blocked or returned an empty cycling feed",
        "at_local": datetime.now().isoformat(timespec="seconds"),
        "at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "timestamp": hhmm,
        "probes": probes,
        "brands_tried": attempts,
        "prior_snapshots_today": prior,
    }
    path = out_dir / "degraded.json"
    path.write_text(json.dumps(payload, indent=1) + "\n")
    return path


# --------------------------------------------------------------------------
# CLI


def parse_until(value: str) -> datetime:
    """``HH:MM`` local (rolling to tomorrow when it has already passed, which
    is what an evening tick waiting for the late-morning market wants), or a
    full ISO datetime taken exactly as given."""
    if "-" in value or "T" in value:
        try:
            return datetime.fromisoformat(value)
        except ValueError as e:
            raise SystemExit(f"ERROR: --until could not read {value!r}") from e
    try:
        hh, mm = value.split(":")
        target = datetime.now().replace(hour=int(hh), minute=int(mm), second=0,
                                        microsecond=0)
    except (ValueError, TypeError) as e:
        raise SystemExit(f"ERROR: --until wants HH:MM or an ISO datetime, "
                         f"got {value!r}") from e
    if target < datetime.now():
        target += timedelta(days=1)
    return target


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--campaign", help="campaign directory holding campaign.json "
                                       "(e.g. performance_eval/vuelta-2026); supplies "
                                       "the match strings and out-root, and receives "
                                       "discovered event ids")
    ap.add_argument("--brands", default=DEFAULT_BRANDS,
                    help=f"comma-separated brand chain, tried in order (default {DEFAULT_BRANDS})")
    ap.add_argument("--brand", help="force a single brand (disables the fallback chain)")
    ap.add_argument("--lang", help="override the brand's default lang")
    ap.add_argument("--market", help="override the brand's default market")
    ap.add_argument("--match",
                    help="case-insensitive substring an event name must contain; "
                         "matched against BOTH the localised name and englishName, "
                         "so 'vuelta a espa' finds the Dutch 'Ronde van Spanje'. "
                         "Defaults to the campaign's kambi_match.")
    ap.add_argument("--out-root",
                    help="odds archive root (default: the campaign's odds/, else "
                         "this campaign directory's odds/)")
    ap.add_argument("--stage", type=int, help="stage number, for --print-event-id")
    ap.add_argument("--print-event-id", action="store_true",
                    help="print the event id for --stage and exit (cache first)")
    ap.add_argument("--refresh", action="store_true",
                    help="with --print-event-id, ignore the cached id and rediscover")
    ap.add_argument("--wait-for-stage", type=int, metavar="N",
                    help="poll until stage N's market is posted, then capture")
    ap.add_argument("--until", metavar="HH:MM",
                    help="local deadline for --wait-for-stage (default 13:00); "
                         "a full ISO datetime is taken as-is")
    ap.add_argument("--poll-minutes", type=float, default=15.0,
                    help="poll interval for --wait-for-stage (default 15)")
    ap.add_argument("--no-write-campaign", action="store_true",
                    help="do not write discovered ids/candidates back to campaign.json")
    ap.add_argument("--json", action="store_true",
                    help="print only a JSON summary on stdout (progress goes to stderr)")
    return ap


def main(argv: list[str] | None = None, *, sleep=time.sleep) -> int:
    args = build_parser().parse_args(argv)
    # --json and --print-event-id both promise a clean stdout (the second is
    # meant for EVENT_ID=$(... --print-event-id)), so progress goes to stderr.
    quiet_stdout = args.json or args.print_event_id
    log = (lambda *a, **k: print(*a, file=sys.stderr, **k)) if quiet_stdout else print

    campaign_dir = Path(args.campaign) if args.campaign else None
    campaign = load_campaign(campaign_dir) if campaign_dir else {}
    probes = campaign_probes(campaign, args.match)
    if not probes:
        probes = ["(tour de france 2026)"]

    if args.out_root:
        out_root = Path(args.out_root)
    elif campaign_dir:
        out_root = campaign_dir / "odds"
    else:
        out_root = OUT_ROOT

    brands = ([args.brand] if args.brand
              else [b.strip() for b in args.brands.split(",") if b.strip()])

    summary: dict = {"probes": probes, "brands": brands, "degraded": False}

    # --- --stage N --print-event-id ---------------------------------------
    if args.print_event_id:
        if args.stage is None:
            log("ERROR: --print-event-id needs --stage N")
            return 1
        key = f"stage_{args.stage:02d}"
        cached = (campaign.get("kambi_event_ids") or {}).get(key)
        if cached and not args.refresh:
            print(cached)
            return 0
        hit = try_brands(brands, probes, lang=args.lang, market=args.market,
                         log=log, sleep=sleep)
        found = next((str(ev["id"]) for ev in hit.get("events", [])
                      if event_key(ev) == key), None)
        if not found:
            log(f"No event for {key} in the feed "
                f"({hit['status']}, brands: {[a['brand'] for a in hit['attempts']]})")
            return 1
        if campaign_dir and not args.no_write_campaign:
            record_ids(campaign_dir, campaign, {key: found}, log=log)
        print(found)
        return 0

    # --- --wait-for-stage N ----------------------------------------------
    hit: dict | None = None
    if args.wait_for_stage is not None:
        deadline = parse_until(args.until or "13:00")
        want = f"stage_{args.wait_for_stage:02d}"
        log(f"Waiting for {want} to post, deadline {deadline:%Y-%m-%d %H:%M} local, "
            f"polling every {args.poll_minutes:g} min")
        while True:
            probe_hit = try_brands(brands, probes, lang=args.lang, market=args.market,
                                   log=log, sleep=sleep)
            if any(event_key(ev) == want for ev in probe_hit.get("events", [])):
                log(f"{want} is up — capturing")
                hit = probe_hit
                break
            now = datetime.now()
            if now >= deadline:
                log(f"Deadline {deadline:%H:%M} passed and {want} never posted.")
                summary.update({"status": "stage_never_posted", "waited_for": want,
                                "deadline": deadline.isoformat(timespec="minutes"),
                                "brands_tried": probe_hit.get("attempts", [])})
                if args.json:
                    print(json.dumps(summary, indent=1))
                return 2
            wait_s = min(args.poll_minutes * 60, max(0.0, (deadline - now).total_seconds()))
            log(f"  not up yet at {now:%H:%M}; sleeping {wait_s / 60:.0f} min")
            if wait_s > 0:
                sleep(wait_s)
    else:
        hit = try_brands(brands, probes, lang=args.lang, market=args.market,
                         log=log, sleep=sleep)

    day = datetime.now().strftime("%Y-%m-%d")
    hhmm = datetime.now().strftime("%H%M")
    out_dir = out_root / day
    summary.update({"day": day, "timestamp": hhmm, "out_dir": str(out_dir)})

    # --- every brand blocked: degraded, not a failure ---------------------
    if hit["status"] == "degraded":
        path = write_degraded(out_dir, hit["attempts"], probes, hhmm)
        log(f"DEGRADED: every brand blocked. Recorded in {path}")
        summary.update({"status": "degraded", "degraded": True,
                        "degraded_file": str(path), "brands_tried": hit["attempts"]})
        if args.json:
            print(json.dumps(summary, indent=1))
        return 0

    # --- a feed answered but the campaign was not in it --------------------
    if hit["status"] == "no_match":
        out_dir.mkdir(parents=True, exist_ok=True)
        prov = {
            "brand": hit["brand"],
            "listview_url": hit["listview_url"],
            "fetched_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "probes": probes,
            "events": {},
            "matched": [],
            "brands_tried": hit["attempts"],
            "kambi_candidates": hit["candidates"],
        }
        (out_dir / f"provenance_{hhmm}.json").write_text(json.dumps(prov, indent=1))
        if campaign_dir and not args.no_write_campaign:
            record_candidates(campaign_dir, campaign, hit, probes, log=log)
        log(f"No events matching {probes} in the {hit['brand']} feed.")
        log("Either all its markets are live/settled right now (run earlier in the day),")
        log("or the race name drifted — see kambi_candidates in "
            f"provenance_{hhmm}.json and confirm one by hand.")
        for c in hit["candidates"][:5]:
            log(f"  candidate {c['score']:.2f}  {c['event_id']}  {c['name']}")
        summary.update({"status": "no_match", "brand": hit["brand"],
                        "kambi_candidates": hit["candidates"],
                        "brands_tried": hit["attempts"]})
        if args.json:
            print(json.dumps(summary, indent=1))
        return 1

    # --- normal path -------------------------------------------------------
    result = capture_snapshot(hit, out_dir, hhmm, log=log, sleep=sleep)
    summary.update({"status": "ok", "brand": hit["brand"], **result})
    if campaign_dir and not args.no_write_campaign:
        record_ids(campaign_dir, campaign, result["event_ids"], log=log)
        record_candidates(campaign_dir, campaign, hit, probes, log=log)
    if args.json:
        print(json.dumps(summary, indent=1))
    return 0


def record_ids(campaign_dir: Path, campaign: dict, ids: dict[str, str], *,
               log=print) -> None:
    """Merge discovered event ids into campaign.json (atomic, order-preserving)."""
    if not ids:
        return
    existing = dict(campaign.get("kambi_event_ids") or {})
    changed = False
    for key, value in ids.items():
        if existing.get(key) == value:
            continue
        if key in existing:
            log(f"NOTE: {key} event id changed {existing[key]} -> {value}")
        existing[key] = value
        changed = True
    if not changed:
        return
    campaign["kambi_event_ids"] = dict(sorted(existing.items()))
    save_campaign(campaign_dir, campaign)
    log(f"Wrote {len(ids)} event id(s) into {campaign_dir / 'campaign.json'}")


def record_candidates(campaign_dir: Path, campaign: dict, hit: dict,
                      probes: list[str], *, log=print) -> None:
    """Record fuzzy proposals for a human; clear them once a match is clean."""
    candidates = hit.get("candidates") or []
    had = bool(campaign.get("kambi_candidates"))
    if hit["status"] == "matched" and not candidates:
        if had:
            campaign.pop("kambi_candidates", None)
            save_campaign(campaign_dir, campaign)
        return
    if not candidates:
        return
    campaign["kambi_candidates"] = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "brand": hit.get("brand"),
        "probes": probes,
        "accept_threshold": FUZZY_ACCEPT,
        "note": "PROPOSALS ONLY — below the accept threshold. Confirm by hand and "
                "set kambi_match / kambi_localised_name; nothing here is used "
                "automatically.",
        "candidates": candidates,
    }
    save_campaign(campaign_dir, campaign)
    log(f"Recorded {len(candidates)} fuzzy candidate(s) in campaign.json for review")


if __name__ == "__main__":
    sys.exit(main())
