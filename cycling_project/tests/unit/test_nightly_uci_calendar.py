"""UCI calendar → ``uci_competition_url`` resolution (``nightly/uci_calendar.py``).

Fixtures, captured ONCE on 2026-09-07 with the module's own rate-limited fetcher
(browser UA, no cookies, ≥ 3 s apart — two requests for the whole road calendar):

``fixtures/uci/calendar/``  ``upcoming_ROA.json`` + ``past_ROA.json`` + the
                            ``calendar_raw.json`` index (1018 competitions).
``fixtures/uci/oneday-gp-industria-78396/``
                            a one-day capture (GP Industria & Artigianato, 1.Pro,
                            2026-09-06): accordion label "Final Classification",
                            single classification titled "General Classification".

No test touches the network.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from cycling_project.nightly import registry
from cycling_project.nightly import uci_acquire as ua
from cycling_project.nightly import uci_calendar as uc
from cycling_project.nightly.store_local import JsonlStore

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
CALENDAR = FIXTURES / "uci" / "calendar"
ONEDAY = FIXTURES / "uci" / "oneday-gp-industria-78396"
REPO = Path(__file__).resolve().parents[3]

VUELTA_URL = "https://www.uci.org/competition-details/2026/ROA/76942"


@pytest.fixture(scope="module")
def entries():
    rows, _index = uc.load_snapshot(CALENDAR)
    return rows


@pytest.fixture(scope="module")
def provenance():
    _rows, index = uc.load_snapshot(CALENDAR)
    return uc.snapshot_provenance(index)


def _campaign(**overrides):
    row = {"slug": "test-race-2026", "name": "Test Race", "fc_race_id": "99", "year": 2026,
           "category": "pro", "is_stage_race": False,
           "start_date": "2026-09-13", "end_date": "2026-09-13",
           "uci_competition_url": None, "uci_competition_id": None, "uci_discipline": None}
    row.update(overrides)
    return row


# ---------------------------------------------------------------------------
# the endpoints
# ---------------------------------------------------------------------------

def test_listing_url_is_built_by_urllib_and_validated():
    url = uc.listing_url("upcoming")
    assert url == "https://www.uci.org/api/calendar/upcoming?discipline=ROA"
    uc.assert_well_formed_listing_url(url)
    with pytest.raises(ua.AcquireError):
        uc.listing_url("everything")
    with pytest.raises(ua.AcquireError):
        uc.listing_url("upcoming", "road")
    for bad in ("https://example.org/api/calendar/upcoming?discipline=ROA",
                "https://www.uci.org/api/calendar/results/D2EV1?discipline=ROA",
                "https://www.uci.org/api/calendar/everything?discipline=ROA"):
        with pytest.raises(ua.AcquireError):
            uc.assert_well_formed_listing_url(bad)


def test_capture_makes_one_request_per_listing_and_records_sha256(tmp_path):
    class FakeResponse:
        status_code = 200
        headers = {"Content-Type": "application/json"}
        content = json.dumps({"items": [{"month": 9, "year": 2026, "items": [
            {"competitionDate": "2026-09-13T00:00:00Z", "items": [
                {"name": "Test Race", "country": "FRA", "dates": "13 Sep 2026",
                 "detailsLink": {"url": "/competition-details/2026/ROA/99999"}}]}]}]}).encode()

    class FakeFetcher:
        def __init__(self):
            self.urls = []
            self.requests_made = 0

        def get(self, url, *, accept):
            self.urls.append(url)
            self.requests_made += 1
            return FakeResponse(), None

    fetcher = FakeFetcher()
    index = uc.capture(out_dir=tmp_path, fetcher=fetcher)

    assert fetcher.urls == ["https://www.uci.org/api/calendar/upcoming?discipline=ROA",
                            "https://www.uci.org/api/calendar/past?discipline=ROA"]
    assert index["complete"] and index["requests_made"] == 2
    assert index["listings"]["upcoming"]["competitions"] == 1
    assert (tmp_path / "upcoming_ROA.json").read_bytes() == FakeResponse.content
    assert index["listings"]["past"]["sha256"] == ua.sha256_bytes(FakeResponse.content)


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("09 Sep 2026", ("2026-09-09", "2026-09-09")),
    ("22 Aug - 13 Sep 2026", ("2026-08-22", "2026-09-13")),
    ("16 Sep - 20 Sep 2026", ("2026-09-16", "2026-09-20")),
    ("28 Dec 2026 - 03 Jan 2027", ("2026-12-28", "2027-01-03")),
    ("28 Dec - 03 Jan 2027", ("2026-12-28", "2027-01-03")),
    ("", (None, None)),
    ("sometime in September", (None, None)),
    ("31 Feb 2026", (None, None)),
])
def test_parse_dates_text(text, expected):
    assert uc.parse_dates_text(text) == expected


def test_parse_listing_dedupes_a_stage_race_across_its_days(entries):
    vuelta = [e for e in entries if e.competition_id == "76942"]
    assert len(vuelta) == 1
    entry = vuelta[0]
    assert entry.name == "La Vuelta Ciclista a España"
    assert (entry.start_date, entry.end_date) == ("2026-08-22", "2026-09-13")
    assert entry.country == "ESP" and entry.discipline == "ROA" and entry.year == 2026
    assert entry.full_url == VUELTA_URL
    assert len(entry.observed_days) > 1          # it was listed on every day it spans


def test_snapshot_holds_both_listings_and_over_a_thousand_road_competitions(entries):
    _rows, index = uc.load_snapshot(CALENDAR)
    assert set(index["listings"]) == {"upcoming", "past"} and index["complete"]
    assert len(entries) > 1000
    assert all(e.discipline == "ROA" for e in entries)


def test_parse_listing_rejects_a_document_that_is_not_a_listing():
    with pytest.raises(ua.AcquireError):
        uc.parse_listing({"results": []})


# ---------------------------------------------------------------------------
# names
# ---------------------------------------------------------------------------

def test_normalisation_expands_gp_and_drops_the_year():
    assert uc.normalise_name("GP Québec 2026") == "grand prix quebec"
    assert uc.normalise_name("Kamp. van Vlaanderen") == "kampioenschap van vlaanderen"


def test_head_and_tail_variants_carry_sponsor_and_memorial_suffixes():
    assert uc.name_similarity("Coppa Sabatini",
                              "Gran Premio città di Peccioli - Coppa Sabatini") == (1.0, "full~tail")
    assert uc.name_similarity("Giro della Toscana",
                              "Giro della Toscana - Memorial Alfredo Martini") == (1.0, "full~head")


def test_mens_and_womens_editions_are_not_normalised_together():
    """The same race often runs both; the word must lower the score, not vanish."""
    mens = uc.name_similarity("Grand Prix de Wallonie", "Lotto Grand Prix de Wallonie")[0]
    womens = uc.name_similarity("Grand Prix de Wallonie", "Lotto Grand Prix de Wallonie Dames")[0]
    assert womens < mens
    assert "women" in uc.normalise_name("Tour of Britain Women")


# ---------------------------------------------------------------------------
# matching
# ---------------------------------------------------------------------------

def test_matcher_reproduces_the_hand_set_vuelta_url(entries, provenance):
    """The Vuelta's URL was set by hand; the calendar must find the same competition."""
    campaign = json.loads((REPO / "performance_eval" / "vuelta-2026" / "campaign.json").read_text())
    assert campaign["uci_competition_url"] == VUELTA_URL      # the hand-set value, still there

    match = uc.match_campaign(campaign, entries)

    assert match.best.entry.competition_id == "76942"
    assert match.best.dates_verdict == "exact"
    assert match.existing_agrees is True
    # "Vuelta a España 2026" vs "La Vuelta Ciclista a España" is below the name bar,
    # so the matcher would have asked a human rather than writing this URL itself.
    assert match.decision == "operator_confirm" and not match.needs_operator


def test_a_set_url_is_never_overwritten_even_when_the_calendar_disagrees(entries, provenance):
    campaign = _campaign(name="GP Montreal", start_date="2026-09-13", end_date="2026-09-13",
                         uci_competition_url="https://www.uci.org/competition-details/2026/ROA/11111",
                         uci_competition_id="11111", uci_discipline="ROA")
    match = uc.match_campaign(campaign, entries)
    updated = uc.apply_match(campaign, match, provenance)

    assert match.existing_agrees is False
    assert updated["uci_competition_url"].endswith("/11111")
    assert updated["uci_competition_id"] == "11111"
    assert any("DISAGREES" in reason for reason in match.reasons)
    assert updated["uci_match_evidence"]["existing_url_conflict"] is True


def test_exact_dates_and_a_clear_name_are_auto_accepted(entries, provenance):
    campaign = _campaign(name="Trofeo Matteotti", start_date="2026-09-13", end_date="2026-09-13")
    match = uc.match_campaign(campaign, entries)
    updated = uc.apply_match(campaign, match, provenance)

    assert match.decision == "auto_accepted" and match.best.similarity >= uc.AUTO_ACCEPT_SIMILARITY
    assert updated["uci_competition_url"] == "https://www.uci.org/competition-details/2026/ROA/78411"
    assert updated["uci_competition_id"] == "78411" and updated["uci_discipline"] == "ROA"
    evidence = updated["uci_match_evidence"]
    assert evidence["decision"] == "auto_accepted" and evidence["score"] == match.best.similarity
    assert evidence["fields_compared"]["dates"]["verdict"] == "exact"
    assert evidence["fields_compared"]["country"]["verdict"] == "not_compared"
    assert evidence["snapshot"]["listings"]["upcoming"]["sha256"]


def test_a_name_below_the_bar_leaves_the_url_null(entries, provenance):
    campaign = _campaign(name="Giro della Romagna", start_date="2026-09-20", end_date="2026-09-20")
    match = uc.match_campaign(campaign, entries)
    updated = uc.apply_match(campaign, match, provenance)

    assert match.decision == "operator_confirm" and match.needs_operator
    assert updated["uci_competition_url"] is None
    assert updated["uci_match_evidence"]["candidate"]["competition_id"]        # still recorded
    assert any("below" in reason for reason in match.reasons)


def test_dates_that_only_overlap_are_never_auto_accepted(entries):
    """Same race name, one day out: a stage race shifted by a day is a different edition."""
    campaign = _campaign(name="Tour of Taihu Lake", start_date="2026-09-13", end_date="2026-09-16")
    match = uc.match_campaign(campaign, entries)
    assert match.best.entry.competition_id == "78408"
    assert match.best.dates_verdict == "overlap" and match.decision == "operator_confirm"


def test_two_equally_good_exact_date_candidates_are_refused(provenance):
    twin = [uc.CalendarEntry(competition_id=str(cid), discipline="ROA", year=2026,
                             url=f"/competition-details/2026/ROA/{cid}", name="Test Race",
                             country="FRA", dates_text="13 Sep 2026",
                             start_date="2026-09-13", end_date="2026-09-13")
            for cid in (11111, 22222)]
    match = uc.match_campaign(_campaign(), twin)
    assert match.decision == "operator_confirm"
    assert any("more than one exact-date candidate" in reason for reason in match.reasons)
    assert uc.apply_match(_campaign(), match, provenance)["uci_competition_url"] is None


def test_a_campaign_with_no_calendar_entry_at_all(entries, provenance):
    match = uc.match_campaign(_campaign(start_date="2031-01-01", end_date="2031-01-01", year=2031), entries)
    assert match.decision == "no_candidate" and match.best is None
    assert uc.apply_match(_campaign(), match, provenance)["uci_competition_url"] is None


def test_evidence_keeps_its_timestamp_when_the_verdict_is_unchanged(entries, provenance):
    campaign = _campaign(name="Trofeo Matteotti", start_date="2026-09-13", end_date="2026-09-13")
    first = uc.apply_match(campaign, uc.match_campaign(campaign, entries), provenance)
    second = uc.apply_match(first, uc.match_campaign(first, entries), provenance)
    assert second["uci_match_evidence"]["matched_at"] == first["uci_match_evidence"]["matched_at"]
    assert second == first


# ---------------------------------------------------------------------------
# writing
# ---------------------------------------------------------------------------

def test_a_hand_formatted_campaign_file_keeps_every_existing_byte():
    original_text = ('{\n  "slug": "vuelta-2026",\n'
                     '  "stages": [\n'
                     '    {"number": 1, "date": "2026-08-22"},\n'
                     '    {"number": 2, "date": "2026-08-23"}\n'
                     '  ]\n}\n')
    original = json.loads(original_text)
    updated = dict(original, uci_match_evidence={"decision": "auto_accepted"})

    text = uc.render_campaign(original_text, original, updated)

    assert text.startswith(original_text[:-3])                       # everything before the closing brace
    assert '{"number": 1, "date": "2026-08-22"},' in text            # compact rows untouched
    assert json.loads(text) == updated


def test_a_machine_written_campaign_file_is_re_dumped_in_place():
    original = {"slug": "x", "uci_competition_url": None}
    original_text = json.dumps(original, indent=2, ensure_ascii=False) + "\n"
    updated = dict(original, uci_competition_url="https://www.uci.org/competition-details/2026/ROA/1")
    text = uc.render_campaign(original_text, original, updated)
    assert text == json.dumps(updated, indent=2, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------------------
# resolve end to end
# ---------------------------------------------------------------------------

def _perf_dir(tmp_path, *campaigns):
    perf = tmp_path / "performance_eval"
    for campaign in campaigns:
        path = perf / campaign["slug"] / "campaign.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(campaign, indent=2, ensure_ascii=False) + "\n")
    return perf


def test_resolve_writes_clear_matches_asks_about_the_rest_and_does_not_repeat_itself(tmp_path):
    perf = _perf_dir(tmp_path,
                     _campaign(slug="trofeo-matteotti-2026", name="Trofeo Matteotti"),
                     _campaign(slug="gooikse-pijl-2026", name="Gooikse Pijl",
                               start_date="2026-09-20", end_date="2026-09-20"))
    runs = tmp_path / "runs"
    now = date(2026, 9, 7)

    result = uc.resolve(perf, snapshot_dir=CALENDAR, now=now, runs_dir=runs)

    assert result["auto_accepted"] == 1 and result["operator_confirm"] == 1
    assert result["tasks_written"] == 1
    matteotti = json.loads((perf / "trofeo-matteotti-2026" / "campaign.json").read_text())
    gooikse = json.loads((perf / "gooikse-pijl-2026" / "campaign.json").read_text())
    assert matteotti["uci_competition_url"].endswith("/78411")
    assert gooikse["uci_competition_url"] is None
    assert gooikse["uci_match_evidence"]["candidate"]["competition_id"] == "78434"

    task = json.loads((runs / "operator_tasks.jsonl").read_text().splitlines()[0])
    assert task["kind"] == "uci_competition_confirm" and task["campaign"] == "gooikse-pijl-2026"
    assert task["detail"]["candidate"]["competition_id"] == "78434"
    assert task["detail"]["field"] == "uci_competition_url" and task["resolved"] is None

    again = uc.resolve(perf, snapshot_dir=CALENDAR, now=now, runs_dir=runs)
    assert again["tasks_written"] == 0                                   # no duplicate inbox rows
    assert len((runs / "operator_tasks.jsonl").read_text().splitlines()) == 1


def _operator_evidence(decision, competition_id, name, reason=None):
    ev = {"matcher": "uci_calendar 1.0.0", "decision": decision, "decided_at": "2026-09-07T17:00:00+00:00",
          "decided_by": "operator", "candidate": {"competition_id": competition_id, "discipline": "ROA",
          "url": f"https://www.uci.org/competition-details/2026/ROA/{competition_id}", "name": name}}
    if reason:
        ev["reason"] = reason
    return ev


def test_an_operator_confirmed_url_and_its_record_survive_the_matcher(entries, provenance):
    # gooikse-pijl: the calendar alone scores it below the bar (an operator_confirm case)
    campaign = _campaign(slug="gooikse-pijl-2026", name="Gooikse Pijl", start_date="2026-09-20",
                         end_date="2026-09-20", uci_competition_url="https://www.uci.org/competition-details/2026/ROA/78434",
                         uci_competition_id="78434", uci_discipline="ROA",
                         uci_match_evidence=_operator_evidence("operator_confirmed", "78434", "Gooikse pijl p/b Lotto"))
    match = uc.match_campaign(campaign, entries)
    assert not match.needs_operator
    updated = uc.apply_match(campaign, match, provenance)
    assert updated["uci_match_evidence"] == campaign["uci_match_evidence"]     # verbatim, not the matcher's block
    assert updated["uci_competition_url"].endswith("/78434")


def test_a_rejected_candidate_is_not_asked_again_and_the_rejection_stays_on_file(tmp_path):
    # giro-della-romagna: no 2026 listing; the best candidate (Giro di Campania) is a different race
    romagna = _campaign(slug="giro-della-romagna-2026", name="Giro della Romagna", start_date="2026-09-20",
                        end_date="2026-09-20",
                        uci_match_evidence=_operator_evidence("operator_rejected", "78436", "Giro di Campania",
                                                              reason="different race on the same date"))
    perf = _perf_dir(tmp_path, romagna)
    runs = tmp_path / "runs"
    result = uc.resolve(perf, snapshot_dir=CALENDAR, now=date(2026, 9, 7), runs_dir=runs)
    assert result["tasks_written"] == 0 and result["operator_confirm"] == 0
    assert not (runs / "operator_tasks.jsonl").exists()
    after = json.loads((perf / "giro-della-romagna-2026" / "campaign.json").read_text())
    assert after["uci_competition_url"] is None
    assert after["uci_match_evidence"] == romagna["uci_match_evidence"]


def test_a_rejection_of_a_different_candidate_reopens_the_question(entries, provenance):
    campaign = _campaign(slug="gooikse-pijl-2026", name="Gooikse Pijl", start_date="2026-09-20",
                         end_date="2026-09-20",
                         uci_match_evidence=_operator_evidence("operator_rejected", "11111", "Some Other Race"))
    match = uc.match_campaign(campaign, entries)
    assert match.decision == "operator_confirm" and match.needs_operator
    assert match.best.entry.competition_id == "78434"
    updated = uc.apply_match(campaign, match, provenance)
    assert updated["uci_match_evidence"]["decision"] == "operator_confirm"   # fresh matcher evidence replaces it
    assert any("asking again" in r for r in match.reasons)


def test_resolve_dry_run_writes_nothing(tmp_path):
    perf = _perf_dir(tmp_path, _campaign(slug="trofeo-matteotti-2026", name="Trofeo Matteotti"))
    runs = tmp_path / "runs"
    before = (perf / "trofeo-matteotti-2026" / "campaign.json").read_text()

    result = uc.resolve(perf, snapshot_dir=CALENDAR, now=date(2026, 9, 7), runs_dir=runs, dry_run=True)

    assert result["auto_accepted"] == 1 and result["tasks_written"] == 0
    assert (perf / "trofeo-matteotti-2026" / "campaign.json").read_text() == before
    assert not runs.exists()


def test_resolve_needs_a_snapshot(tmp_path):
    with pytest.raises(ua.AcquireError):
        uc.resolve(_perf_dir(tmp_path), snapshot_dir=tmp_path / "nothing")


def test_tasks_reach_a_store_as_agent_rows(tmp_path):
    store = JsonlStore(runs_dir=None, role="agent")
    perf = _perf_dir(tmp_path, _campaign(slug="gooikse-pijl-2026", name="Gooikse Pijl",
                                         start_date="2026-09-20", end_date="2026-09-20"))
    uc.resolve(perf, snapshot_dir=CALENDAR, now=date(2026, 9, 7), store=store, runs_dir=None)
    assert [row["kind"] for row in store.rows["operator_tasks"]] == ["uci_competition_confirm"]


# ---------------------------------------------------------------------------
# registry.sync integration
# ---------------------------------------------------------------------------

def _calendar_file(perf, **row):
    entry = {"fc_race_id": "99", "year": 2026, "name": "Trofeo Matteotti", "category": "pro",
             "is_stage_race": False, "start_date": "2026-09-13", "end_date": "2026-09-13",
             "url": "https://firstcycling.com/race.php?r=99&y=2026"}
    entry.update(row)
    path = perf / "calendar" / "2026.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema_version": 1, "year": 2026, "races": [entry]}))
    return perf


def test_sync_gives_a_new_campaign_its_uci_url_when_the_match_is_exact(tmp_path):
    perf = _calendar_file(tmp_path / "performance_eval")

    result = registry.sync(perf, now=date(2026, 9, 7), store_mode="none", uci_snapshot=CALENDAR)

    assert result["uci_matched"] and result["uci_urls_resolved"] == 1
    config = json.loads((perf / "trofeo-matteotti-2026" / "campaign.json").read_text())
    assert config["uci_competition_url"] == "https://www.uci.org/competition-details/2026/ROA/78411"
    assert config["uci_competition_id"] == "78411" and config["uci_discipline"] == "ROA"
    assert config["uci_match_evidence"]["decision"] == "auto_accepted"


def test_sync_refuses_to_guess_and_is_stable_on_a_second_run(tmp_path):
    perf = _calendar_file(tmp_path / "performance_eval", name="Giro della Romagna",
                          start_date="2026-09-20", end_date="2026-09-20")

    first = registry.sync(perf, now=date(2026, 9, 7), store_mode="none", uci_snapshot=CALENDAR)
    written = (perf / "giro-della-romagna-2026" / "campaign.json").read_text()
    second = registry.sync(perf, now=date(2026, 9, 7), store_mode="none", uci_snapshot=CALENDAR)

    assert first["uci_urls_resolved"] == 0
    assert json.loads(written)["uci_competition_url"] is None
    assert json.loads(written)["uci_match_evidence"]["decision"] == "operator_confirm"
    assert [c for c in second["campaigns"] if c["changed"]] == []
    assert (perf / "giro-della-romagna-2026" / "campaign.json").read_text() == written


def test_sync_without_a_snapshot_still_creates_campaigns_with_a_null_url(tmp_path):
    perf = _calendar_file(tmp_path / "performance_eval")

    result = registry.sync(perf, now=date(2026, 9, 7), store_mode="none",
                           uci_snapshot=tmp_path / "no-snapshot-here")

    assert result["uci_matched"] is False and result["uci_urls_resolved"] == 0
    config = json.loads((perf / "trofeo-matteotti-2026" / "campaign.json").read_text())
    assert config["uci_competition_url"] is None and "uci_match_evidence" not in config


def test_sync_can_be_told_not_to_consult_the_calendar(tmp_path):
    perf = _calendar_file(tmp_path / "performance_eval")
    result = registry.sync(perf, now=date(2026, 9, 7), store_mode="none", match_uci=False)
    assert result["uci_matched"] is False
    config = json.loads((perf / "trofeo-matteotti-2026" / "campaign.json").read_text())
    assert config["uci_competition_url"] is None


# ---------------------------------------------------------------------------
# one-day acquisition (the title variants this capture proved)
# ---------------------------------------------------------------------------

def test_one_day_units_name_the_single_accordion_entry():
    assert ua.stage_label_for("race") == "race"
    assert ua.stage_label_for("one_day") == "race"          # the unit name the registry writes
    assert ua.stage_label_for("stage_14") == "Stage 14"
    assert ua.is_one_day_unit("one_day") and not ua.is_one_day_unit("stage_14")
    with pytest.raises(ua.AcquireError):
        ua.stage_label_for("prologue")


def test_a_one_day_capture_is_complete_with_its_single_classification():
    index = json.loads((ONEDAY / "uci_raw.json").read_text())

    assert ua.required_kinds("one_day") == ("gc",)
    assert ua.required_kinds("stage_14") == ("stage", "gc")
    assert ua.capture_is_complete(index)                    # would be False under the stage-race rule
    assert not ua.capture_is_complete(index, required=("stage", "gc"))


def test_the_one_day_classification_titles_seen_on_the_uci_site():
    index = json.loads((ONEDAY / "uci_raw.json").read_text())
    stage = index["stage"]

    assert stage["label"] == "Final Classification"              # the accordion entry
    assert stage["accordion_titles"] == ["General Classification"]   # the single classification
    assert stage["race_type"] == "Individual Road Race"
    assert stage["race_class"] == "1.Pro - 1 day - UCI ProSeries"
    assert index["pages"]["gc"]["race_name"] == "General Classification"
    assert index["pages"]["gc"]["race_type"] == "A"              # the API parameter, not the schedule word
    assert "Final Classification" in ua.CLASSIFICATIONS["gc"][0]
    assert index["pages"]["stage"]["available"] is False


def test_the_one_day_capture_holds_the_real_result():
    doc = json.loads((ONEDAY / "gc.json").read_text())
    index = json.loads((ONEDAY / "uci_raw.json").read_text())

    assert index["pages"]["gc"]["row_count"] == len(doc["results"]) == 161
    winner = doc["results"][0]["values"]
    assert (winner["rank"], winner["lastname"], winner["result"]) == ("1", "PIDCOCK", "04:33:08")
    assert index["competition"]["name"] == "GP Industria & Artigianato"
