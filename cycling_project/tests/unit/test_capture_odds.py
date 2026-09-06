"""Kambi odds capture: localised discovery, brand fallback, degraded mode.

Fixtures are trimmed from live captures taken on 2026-09-05 (Vuelta stage 15
evening), so the names, ids and shapes are the feed's own:

* ``kambi_listview_ubnl.json``    — Dutch naming ("Etappe 15 (Ronde van
  Spanje 2026)"), plus a Tour of Britain stage and next season's Tour de
  France sitting in the same cycling feed.
* ``kambi_listview_rsiuspa.json`` — the US-brand variant of the same feed,
  English throughout. ``rivers`` itself answers HTTP 429 "No access" from
  every egress tried; ``rsiuspa`` is the BetRivers code that serves.
* ``kambi_betoffer_*.json``       — one win market with hand-checkable odds
  (implied 1.25, devigged 0.4/0.2/0.2/0.2) under the Dutch ``Winnaar`` and
  the English ``Winner`` type names, plus a head-to-head that must not devig.
"""

import csv
import importlib.util
import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = PROJECT_ROOT / "performance_eval" / "tour-de-france-2026" / "capture_odds.py"
FIXTURES = PROJECT_ROOT / "cycling_project" / "tests" / "fixtures" / "nightly"


def _load_module():
    spec = importlib.util.spec_from_file_location("capture_odds_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


co = _load_module()

VUELTA_PROBES = ["vuelta a espa", "Ronde van Spanje 2026"]


def _listview(name):
    return json.loads((FIXTURES / name).read_text())


def _events(name):
    return co.extract_events(_listview(name))


# --------------------------------------------------------------------------
# Discovery: localised names, both fields


@pytest.mark.unit
@pytest.mark.parametrize("fixture", ["kambi_listview_ubnl.json",
                                     "kambi_listview_rsiuspa.json"])
def test_discovery_finds_the_localised_race_on_either_brand(fixture):
    matched, candidates = co.discover(_events(fixture), VUELTA_PROBES)
    assert {str(e["id"]) for e in matched} == {"1028797735", "1028635359",
                                               "1028797615"}
    # A clean substring hit must not drag the rest of the feed in as proposals.
    assert candidates == []


@pytest.mark.unit
def test_dutch_only_probe_still_finds_the_race_through_english_name():
    matched, _ = co.discover(_events("kambi_listview_ubnl.json"),
                             ["Vuelta a España 2026"])
    assert len(matched) == 3


@pytest.mark.unit
def test_accents_and_case_do_not_defeat_the_substring_match():
    matched, _ = co.discover(_events("kambi_listview_ubnl.json"),
                             ["VUELTA A ESPAÑA"])
    assert len(matched) == 3


@pytest.mark.unit
def test_other_races_in_the_same_feed_are_not_matched():
    matched, _ = co.discover(_events("kambi_listview_ubnl.json"), VUELTA_PROBES)
    ids = {str(e["id"]) for e in matched}
    assert "1028980441" not in ids   # Tour of Britain stage 5
    assert "1028531560" not in ids   # Tour de France 2027


# --------------------------------------------------------------------------
# Fuzzy fallback: proposes, never auto-accepts below the threshold


@pytest.mark.unit
def test_fuzzy_below_threshold_proposes_and_never_matches():
    matched, candidates = co.discover(_events("kambi_listview_ubnl.json"),
                                      ["Giro d'Italia 2026"])
    assert matched == []
    assert candidates, "a near miss should be proposed for a human"
    assert all(c["score"] < co.FUZZY_ACCEPT for c in candidates)
    assert candidates == sorted(candidates, key=lambda c: c["score"], reverse=True)


@pytest.mark.unit
def test_fuzzy_at_or_above_threshold_is_accepted():
    drifted = [{"id": 99, "name": "Etappe 15 (Ronde van Spanie 2026)",
                "englishName": "Stage 15 (Vuelta Espana 2026)"}]
    matched, _ = co.discover(drifted, ["Ronde van Spanje 2026"])
    assert len(matched) == 1
    assert matched[0]["_fuzzy_score"] >= co.FUZZY_ACCEPT


@pytest.mark.unit
def test_a_season_mismatch_is_never_a_fuzzy_match():
    """'Ronde van Spanje 2027' scores above 0.95 against the 2026 probe on
    any string metric. It is a different race and must only be proposed."""
    next_year = [{"id": 1, "name": "Algemeen Klassement (Ronde van Spanje 2027)",
                  "englishName": "General Classification (Vuelta a España 2027)"}]
    assert co.similarity("Ronde van Spanje 2026",
                         "Ronde van Spanje 2027") >= co.FUZZY_ACCEPT
    matched, candidates = co.discover(next_year, ["Ronde van Spanje 2026"])
    assert matched == []
    assert candidates[0]["reason"] == "season mismatch"


# --------------------------------------------------------------------------
# Event keys


@pytest.mark.unit
@pytest.mark.parametrize("name,english,expected", [
    ("Etappe 15 (Ronde van Spanje 2026)", "Stage 15 (Vuelta a España 2026)", "stage_15"),
    ("Etapp 15 (Vuelta a España 2026)", "Stage 15 (Vuelta a España 2026)", "stage_15"),
    ("Stage 5 (Tour of Britain 2026)", "Stage 5 (Tour of Britain 2026)", "stage_05"),
    ("Algemeen Klassement (Ronde van Spanje 2026)",
     "General Classification (Vuelta a España 2026)", "gc"),
    ("Puntenklassement (Ronde van Spanje 2026)",
     "Points Classification (Vuelta a España 2026)", "points"),
    ("Bergklassement (Ronde van Spanje 2026)",
     "Mountains Classification (Vuelta a España 2026)", "mountains"),
    ("Jongerenklassement (Ronde van Spanje 2026)",
     "Young Rider Classification (Vuelta a España 2026)", "youth"),
    ("Ploegenklassement (Ronde van Spanje 2026)",
     "Team Classification (Vuelta a España 2026)", "teams"),
    ("Etappewinnaar specials", "Stage Win Specials", "specials"),
    ("Ronde van Vlaanderen 2026", "Tour of Flanders 2026", None),
])
def test_event_key(name, english, expected):
    assert co.event_key({"name": name, "englishName": english}) == expected


# --------------------------------------------------------------------------
# Devig, in both languages


@pytest.mark.unit
@pytest.mark.parametrize("fixture,type_name", [
    ("kambi_betoffer_ubnl_stage15.json", "Winnaar"),
    ("kambi_betoffer_rsiuspa_stage15.json", "Winner"),
])
def test_win_market_devigs_under_either_brand_language(fixture, type_name):
    """The UK/US brands call the market 'Winner'. Before the brand fallback
    only 'Winnaar' was recognised, so a fallback capture would have written a
    CSV with no devigged rows at all."""
    data = json.loads((FIXTURES / fixture).read_text())
    win = next(bo for bo in data["betOffers"]
               if bo["betOfferType"]["name"] == type_name)
    parsed = co.parse_betoffer(win)
    assert parsed["book_sum"] == 1.0
    assert parsed["overround"] == pytest.approx(1.25)
    assert sum(o["devig"] for o in parsed["outcomes"]) == pytest.approx(1.0)
    brennan = next(o for o in parsed["outcomes"] if o["name"] == "Matthew Brennan")
    assert brennan["odds"] == pytest.approx(2.0)
    assert brennan["devig"] == pytest.approx(0.4)


@pytest.mark.unit
def test_head_to_head_is_not_devigged():
    data = json.loads((FIXTURES / "kambi_betoffer_ubnl_stage15.json").read_text())
    h2h = next(bo for bo in data["betOffers"]
               if bo["betOfferType"]["name"] == "Hoofd tot hoofd")
    assert "overround" not in co.parse_betoffer(h2h)


@pytest.mark.unit
def test_place_markets_devig_to_their_place_count():
    assert co.book_sum_for("(1-3)") == 3.0
    assert co.book_sum_for("(1-10)") == 10.0
    assert co.book_sum_for("Head to Head") is None


# --------------------------------------------------------------------------
# Brand fallback


class FakeFeed:
    """Stands in for ``fetch_json``: a scripted answer per brand."""

    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    def __call__(self, url, **kwargs):
        self.calls.append(url)
        brand = url.split("/offering/v2018/")[1].split("/")[0]
        answer = self.answers[brand]
        if isinstance(answer, Exception):
            raise answer
        if "betoffer/event" in url:
            return json.loads(
                (FIXTURES / "kambi_betoffer_ubnl_stage15.json").read_text())
        return answer


@pytest.mark.unit
def test_brand_fallback_walks_past_blocked_and_empty_brands(monkeypatch):
    feed = FakeFeed({
        "ubnl": co.BrandBlocked(451, "geo"),
        "ubuk": co.BrandBlocked(429, "No access"),
        "ubse": {"events": []},
        "rivers": _listview("kambi_listview_rsiuspa.json"),
    })
    monkeypatch.setattr(co, "fetch_json", feed)
    hit = co.try_brands(["ubnl", "ubuk", "ubse", "rivers"], VUELTA_PROBES,
                        lang=None, market=None, log=lambda *a, **k: None,
                        sleep=lambda s: None)
    assert hit["status"] == "matched"
    assert hit["brand"] == "rivers"
    assert [a["outcome"] for a in hit["attempts"]] == [
        "blocked", "blocked", "empty_listview", "matched"]
    assert hit["attempts"][1]["status"] == 429


@pytest.mark.unit
def test_every_brand_blocked_is_degraded_not_an_error(monkeypatch):
    feed = FakeFeed({b: co.BrandBlocked(403, "blocked") for b in ("ubnl", "ubuk")})
    monkeypatch.setattr(co, "fetch_json", feed)
    hit = co.try_brands(["ubnl", "ubuk"], VUELTA_PROBES, lang=None, market=None,
                        log=lambda *a, **k: None, sleep=lambda s: None)
    assert hit["status"] == "degraded"
    assert len(hit["attempts"]) == 2


@pytest.mark.unit
def test_a_feed_that_answers_without_the_race_is_no_match_not_degraded(monkeypatch):
    feed = FakeFeed({"ubnl": _listview("kambi_listview_ubnl.json")})
    monkeypatch.setattr(co, "fetch_json", feed)
    hit = co.try_brands(["ubnl"], ["Giro d'Italia 2026"], lang=None, market=None,
                        log=lambda *a, **k: None, sleep=lambda s: None)
    assert hit["status"] == "no_match"
    assert hit["candidates"]


@pytest.mark.unit
def test_each_brand_is_asked_with_its_own_locale(monkeypatch):
    feed = FakeFeed({"ubnl": co.BrandBlocked(451, ""),
                     "ubse": _listview("kambi_listview_ubnl.json")})
    monkeypatch.setattr(co, "fetch_json", feed)
    co.try_brands(["ubnl", "ubse"], VUELTA_PROBES, lang=None, market=None,
                  log=lambda *a, **k: None, sleep=lambda s: None)
    assert "lang=nl_NL&market=NL" in feed.calls[0]
    assert "lang=sv_SE&market=SE" in feed.calls[1]


# --------------------------------------------------------------------------
# Retries


@pytest.mark.unit
def test_5xx_is_retried_with_backoff_then_gives_up():
    import urllib.error

    attempts = {"n": 0}
    slept = []

    def flaky(url, timeout=None):
        attempts["n"] += 1
        raise urllib.error.URLError("connection reset")

    import urllib.request
    original = urllib.request.urlopen
    urllib.request.urlopen = flaky
    try:
        with pytest.raises(co.FetchFailed):
            co.fetch_json("https://example.test/x", sleep=slept.append)
    finally:
        urllib.request.urlopen = original
    assert attempts["n"] == co.RETRY_ATTEMPTS
    assert slept == [co.RETRY_BACKOFF_S, co.RETRY_BACKOFF_S * 2]


@pytest.mark.unit
def test_a_block_is_not_retried():
    import urllib.error
    import urllib.request

    attempts = {"n": 0}

    def blocked(url, timeout=None):
        attempts["n"] += 1
        raise urllib.error.HTTPError("u", 451, "Unavailable", {}, None)

    original = urllib.request.urlopen
    urllib.request.urlopen = blocked
    try:
        with pytest.raises(co.BrandBlocked) as excinfo:
            co.fetch_json("https://example.test/x", sleep=lambda s: None)
    finally:
        urllib.request.urlopen = original
    assert excinfo.value.status == 451
    assert attempts["n"] == 1


# --------------------------------------------------------------------------
# End to end through main()


@pytest.fixture
def campaign(tmp_path):
    directory = tmp_path / "vuelta-2026"
    directory.mkdir()
    (directory / "campaign.json").write_text(json.dumps({
        "slug": "vuelta-2026",
        "name": "Vuelta a España 2026",
        "kambi_match": "vuelta a espa",
        "kambi_localised_name": "Ronde van Spanje 2026",
        "kambi_event_ids": {"stage_14": "1028797734"},
    }, ensure_ascii=False))
    return directory


def _campaign_json(directory):
    return json.loads((directory / "campaign.json").read_text())


@pytest.mark.unit
def test_capture_writes_the_snapshot_and_records_the_brand(campaign, monkeypatch):
    feed = FakeFeed({"ubnl": co.BrandBlocked(451, "geo"),
                     "ubuk": _listview("kambi_listview_rsiuspa.json")})
    monkeypatch.setattr(co, "fetch_json", feed)
    rc = co.main(["--campaign", str(campaign), "--brands", "ubnl,ubuk", "--json"],
                 sleep=lambda s: None)
    assert rc == 0

    day_dir = next((campaign / "odds").iterdir())
    provenance = json.loads(next(day_dir.glob("provenance_*.json")).read_text())
    assert provenance["brand"] == "ubuk"
    assert [a["outcome"] for a in provenance["brands_tried"]] == ["blocked", "matched"]

    rows = list(csv.DictReader(next(day_dir.glob("win_odds_*.csv")).open()))
    assert rows, "the win market should reach the CSV"
    assert {r["brand"] for r in rows} == {"ubuk"}
    assert float(rows[0]["devig"]) == pytest.approx(0.4)

    markets = json.loads(next(day_dir.glob("markets_*.json")).read_text())
    assert set(markets) == {"1028797735", "1028635359", "1028797615"}
    assert all(key.isdigit() for key in markets), \
        "markets_*.json stays keyed by event id only — its readers iterate it"


@pytest.mark.unit
def test_discovered_event_ids_are_written_back_to_the_campaign(campaign, monkeypatch):
    monkeypatch.setattr(co, "fetch_json",
                        FakeFeed({"ubnl": _listview("kambi_listview_ubnl.json")}))
    co.main(["--campaign", str(campaign), "--brands", "ubnl", "--json"],
            sleep=lambda s: None)
    ids = _campaign_json(campaign)["kambi_event_ids"]
    assert ids["stage_15"] == "1028797735"
    assert ids["gc"] == "1028635359"
    assert ids["points"] == "1028797615"
    assert ids["stage_14"] == "1028797734", "existing ids survive"


@pytest.mark.unit
def test_no_write_campaign_leaves_the_file_alone(campaign, monkeypatch):
    before = (campaign / "campaign.json").read_text()
    monkeypatch.setattr(co, "fetch_json",
                        FakeFeed({"ubnl": _listview("kambi_listview_ubnl.json")}))
    co.main(["--campaign", str(campaign), "--brands", "ubnl", "--json",
             "--no-write-campaign"], sleep=lambda s: None)
    assert (campaign / "campaign.json").read_text() == before


@pytest.mark.unit
def test_every_brand_blocked_writes_degraded_and_exits_zero(campaign, monkeypatch,
                                                            capsys):
    monkeypatch.setattr(co, "fetch_json",
                        FakeFeed({b: co.BrandBlocked(451, "geo")
                                  for b in ("ubnl", "ubuk")}))
    rc = co.main(["--campaign", str(campaign), "--brands", "ubnl,ubuk", "--json"],
                 sleep=lambda s: None)
    assert rc == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["degraded"] is True
    degraded = json.loads((Path(summary["degraded_file"])).read_text())
    assert degraded["degraded"] is True
    assert [a["status"] for a in degraded["brands_tried"]] == [451, 451]
    assert degraded["prior_snapshots_today"] == []


@pytest.mark.unit
def test_no_match_proposes_candidates_and_exits_one(campaign, monkeypatch, capsys):
    monkeypatch.setattr(co, "fetch_json",
                        FakeFeed({"ubnl": _listview("kambi_listview_ubnl.json")}))
    rc = co.main(["--campaign", str(campaign), "--brands", "ubnl", "--json",
                  "--match", "Giro d'Italia 2026"], sleep=lambda s: None)
    assert rc == 1
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "no_match"
    assert summary["kambi_candidates"]

    proposals = _campaign_json(campaign)["kambi_candidates"]
    assert proposals["accept_threshold"] == co.FUZZY_ACCEPT
    assert all(c["score"] < co.FUZZY_ACCEPT for c in proposals["candidates"])
    assert "PROPOSALS ONLY" in proposals["note"]
    assert "kambi_event_ids" in _campaign_json(campaign), "nothing auto-accepted"


@pytest.mark.unit
def test_explicit_match_overrides_the_campaign_names(campaign, monkeypatch):
    """--match steers the run; it must not be joined with the campaign's own
    names, or pointing the script at another race silently keeps matching
    the campaign's."""
    assert co.campaign_probes(_campaign_json(campaign), "tour of britain") == \
        ["tour of britain"]
    monkeypatch.setattr(co, "fetch_json",
                        FakeFeed({"ubnl": _listview("kambi_listview_ubnl.json")}))
    co.main(["--campaign", str(campaign), "--brands", "ubnl", "--json",
             "--match", "tour of britain", "--no-write-campaign"],
            sleep=lambda s: None)
    day_dir = next((campaign / "odds").iterdir())
    markets = json.loads(next(day_dir.glob("markets_*.json")).read_text())
    assert set(markets) == {"1028980441"}


@pytest.mark.unit
def test_print_event_id_reads_the_cache_without_the_network(campaign, monkeypatch,
                                                            capsys):
    def explode(*a, **k):
        raise AssertionError("the cached id must not need a fetch")

    monkeypatch.setattr(co, "fetch_json", explode)
    rc = co.main(["--campaign", str(campaign), "--stage", "14",
                  "--print-event-id"], sleep=lambda s: None)
    assert rc == 0
    assert capsys.readouterr().out.strip() == "1028797734"


@pytest.mark.unit
def test_print_event_id_discovers_and_caches_an_unknown_stage(campaign, monkeypatch,
                                                              capsys):
    monkeypatch.setattr(co, "fetch_json",
                        FakeFeed({"ubnl": _listview("kambi_listview_ubnl.json")}))
    rc = co.main(["--campaign", str(campaign), "--brands", "ubnl", "--stage", "15",
                  "--print-event-id"], sleep=lambda s: None)
    assert rc == 0
    assert capsys.readouterr().out.strip() == "1028797735"
    assert _campaign_json(campaign)["kambi_event_ids"]["stage_15"] == "1028797735"


@pytest.mark.unit
def test_print_event_id_for_a_stage_the_feed_does_not_carry(campaign, monkeypatch):
    monkeypatch.setattr(co, "fetch_json",
                        FakeFeed({"ubnl": _listview("kambi_listview_ubnl.json")}))
    rc = co.main(["--campaign", str(campaign), "--brands", "ubnl", "--stage", "21",
                  "--print-event-id"], sleep=lambda s: None)
    assert rc == 1


# --------------------------------------------------------------------------
# --wait-for-stage


@pytest.mark.unit
def test_wait_for_stage_captures_as_soon_as_the_market_is_up(campaign, monkeypatch):
    monkeypatch.setattr(co, "fetch_json",
                        FakeFeed({"ubnl": _listview("kambi_listview_ubnl.json")}))
    slept = []
    rc = co.main(["--campaign", str(campaign), "--brands", "ubnl", "--json",
                  "--wait-for-stage", "15", "--until", "23:59"],
                 sleep=slept.append)
    assert rc == 0
    assert co.FETCH_SLEEP_S in slept, "only the polite inter-fetch pause"
    assert not any(s > co.FETCH_SLEEP_S for s in slept), "no poll wait"


@pytest.mark.unit
def test_wait_for_stage_gives_up_at_the_deadline_with_exit_two(campaign, monkeypatch,
                                                               capsys):
    monkeypatch.setattr(co, "fetch_json",
                        FakeFeed({"ubnl": _listview("kambi_listview_ubnl.json")}))
    rc = co.main(["--campaign", str(campaign), "--brands", "ubnl", "--json",
                  "--wait-for-stage", "21", "--until", "2020-01-01T00:00:00"],
                 sleep=lambda s: None)
    assert rc == 2
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "stage_never_posted"
    assert summary["waited_for"] == "stage_21"
    assert not (campaign / "odds").exists(), "a timeout writes no snapshot"


@pytest.mark.unit
def test_wait_for_stage_polls_until_the_market_posts(campaign, monkeypatch):
    """The stage market is posted between two polls; the run then captures."""
    without = _listview("kambi_listview_ubnl.json")
    without["events"] = [e for e in without["events"]
                         if str(e["event"]["id"]) != "1028797735"]
    feeds = [without, _listview("kambi_listview_ubnl.json")]

    def answer(url, **kwargs):
        if "betoffer/event" in url:
            return json.loads(
                (FIXTURES / "kambi_betoffer_ubnl_stage15.json").read_text())
        return feeds.pop(0) if len(feeds) > 1 else feeds[0]

    monkeypatch.setattr(co, "fetch_json", answer)
    slept = []
    rc = co.main(["--campaign", str(campaign), "--brands", "ubnl", "--json",
                  "--wait-for-stage", "15", "--until", "23:59",
                  "--poll-minutes", "15"], sleep=slept.append)
    assert rc == 0
    assert 15 * 60 in slept, "one 15-minute poll wait before the market posted"
