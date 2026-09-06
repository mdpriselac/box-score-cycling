"""Route facts: validate a verbatim transcription, merge an override, grade it.

The canonical case is Vuelta 2026 stage 15. The acquisition thread transcribed
the original 189.7 km Palma del Río -> Córdoba stage; on the afternoon of
2026-09-05 the organisers cut it to 110.2 km under the extreme-heat protocol,
which removed the western loop and both of the original climbs and left
Puerto de la Forestal (cat 3, km 34.5, 6.7 km at 4.1%) and Puerto Artafi
(cat 3, km 73.6, 5.9 km at 5.5%). That rewrite is the override fixture.

The FirstCycling fixture reproduces the Information sideBox exactly as the
committed archive carries it (``15th stage | 110.2 km``, ``Palma del Rio ->
Cordoba``, the bare ``GT2`` profile code).
"""

import json
from pathlib import Path

import pytest

from cycling_project.nightly.route_facts import (
    RouteFactsError,
    ingest_route,
    main,
    parse_fc_stage_page,
    parse_number,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "nightly"
RAW = json.loads((FIXTURES / "route_raw_stage15.json").read_text())
OVERRIDE = json.loads((FIXTURES / "route_override_stage15.json").read_text())
FC_PAGE = (FIXTURES / "firstcycling_stage_page.html").read_text()


@pytest.fixture
def campaign(tmp_path):
    """An empty campaign; each test lays down only the layers it needs."""
    (tmp_path / "predictions" / "stage_15").mkdir(parents=True)
    (tmp_path / "results" / "stage_15").mkdir(parents=True)
    return tmp_path


def write_raw(campaign, payload):
    (campaign / "predictions" / "stage_15" / "route_raw.json").write_text(
        json.dumps(payload, ensure_ascii=False))


def write_override(campaign, payload):
    (campaign / "predictions" / "stage_15" / "route.override.json").write_text(
        json.dumps(payload, ensure_ascii=False))


def write_fc(campaign, html=FC_PAGE):
    (campaign / "results" / "stage_15" / "stage_page_2026-09-05.html").write_text(html)


# --------------------------------------------------------------------------
# Number parsing — lenient about units, never inventive


@pytest.mark.unit
@pytest.mark.parametrize("value,expected", [
    (110.2, 110.2), (189, 189.0), ("110.2", 110.2), ("110.2 km", 110.2),
    ("2,350 m", 2350.0), ("4.1%", 4.1), ("  6.7 km  ", 6.7), (None, None), ("", None),
])
def test_numbers_parse_with_or_without_units(value, expected):
    number, error = parse_number(value, field="x")
    assert error is None
    assert number == expected


@pytest.mark.unit
@pytest.mark.parametrize("value", ["about 110 km", "n/a", "TBC", "110 km to 120 km",
                                   True, ["110.2"]])
def test_unreadable_numbers_are_errors_not_defaults(value):
    number, error = parse_number(value, field="distance_km")
    assert number is None
    assert error and "distance_km" in error


# --------------------------------------------------------------------------
# FirstCycling stage page


@pytest.mark.unit
def test_firstcycling_sidebox_yields_distance_towns_and_profile_code():
    facts = parse_fc_stage_page(FC_PAGE)
    assert facts["distance_km"] == 110.2
    assert facts["start"] == "Palma del Rio"
    assert facts["finish"] == "Cordoba"
    assert facts["fc_profile_code"] == "GT2"
    assert "profile_class" not in facts, \
        "GT2 is FirstCycling's own code — recorded, never translated"


@pytest.mark.unit
def test_a_page_without_the_sidebox_yields_nothing_rather_than_guesses():
    assert parse_fc_stage_page("<html><body><p>No data</p></body></html>") == {}


@pytest.mark.unit
def test_an_unparseable_page_is_a_warning_not_a_crash(campaign):
    write_fc(campaign, "<html><body><div class='sideBox'>")
    write_override(campaign, OVERRIDE)
    route = ingest_route(campaign, "stage_15")
    assert route["distance_km"] == 110.2


# --------------------------------------------------------------------------
# The canonical stage-15 override


@pytest.mark.unit
def test_the_heat_rewrite_replaces_distance_and_the_whole_climb_list(campaign):
    write_raw(campaign, RAW)
    write_override(campaign, OVERRIDE)
    route = ingest_route(campaign, "stage_15")

    assert route["distance_km"] == 110.2
    assert route["field_sources"]["distance_km"] == "override"
    assert [c["name"] for c in route["climbs"]] == ["Puerto de la Forestal",
                                                    "Puerto Artafi"]
    assert route["climbs"][0] == {"name": "Puerto de la Forestal", "category": "3",
                                  "km_mark": 34.5, "length_km": 6.7,
                                  "gradient_pct": 4.1}
    assert route["climbs"][1]["km_mark"] == 73.6
    assert route["climbs"][1]["gradient_pct"] == 5.5
    assert set(route["overrides_applied"]) >= {"distance_km", "climbs"}
    assert route["override"]["recorded_by"] == "operator"
    assert "heat" in route["override"]["reason"].lower()


@pytest.mark.unit
def test_fields_the_override_does_not_touch_survive_from_the_transcription(campaign):
    write_raw(campaign, RAW)
    write_override(campaign, OVERRIDE)
    route = ingest_route(campaign, "stage_15")
    assert route["vertical_metres"] == 2350.0
    assert route["profile_class"] == "medium mountains"
    assert route["start"] == "Palma del Río"
    assert route["field_sources"]["profile_class"] == "route_raw"


@pytest.mark.unit
def test_the_original_climbs_do_not_survive_the_rewrite(campaign):
    write_raw(campaign, RAW)
    write_override(campaign, OVERRIDE)
    names = [c["name"] for c in ingest_route(campaign, "stage_15")["climbs"]]
    assert "Alto del Ochavillo" not in names
    assert "Puerto del Madí" not in names


@pytest.mark.unit
def test_the_override_alone_is_enough(campaign):
    write_override(campaign, OVERRIDE)
    route = ingest_route(campaign, "stage_15")
    assert route["distance_km"] == 110.2
    assert len(route["climbs"]) == 2
    assert route["route_facts"] == "partial"
    assert set(route["missing_fields"]) == {"vertical_metres", "profile_class"}


# --------------------------------------------------------------------------
# Cross-check against the FirstCycling archive


@pytest.mark.unit
def test_firstcycling_agreement_is_recorded(campaign):
    write_fc(campaign)
    write_override(campaign, OVERRIDE)
    route = ingest_route(campaign, "stage_15")
    check = next(c for c in route["cross_checks"] if c["field"] == "distance_km")
    assert check["agrees"] is True
    assert check["firstcycling"] == 110.2
    assert route["warnings"] == []


@pytest.mark.unit
def test_a_stale_transcription_disagreeing_with_firstcycling_is_flagged(campaign):
    """The morning transcription still says 189.7 km; the archived stage page
    already says 110.2. The disagreement is surfaced, not silently resolved."""
    write_fc(campaign)
    write_raw(campaign, RAW)
    route = ingest_route(campaign, "stage_15")
    check = next(c for c in route["cross_checks"] if c["field"] == "distance_km")
    assert check["agrees"] is False
    assert check["delta_km"] == pytest.approx(79.5)
    assert route["distance_km"] == 189.7, "the transcription is still what we hold"
    assert any("disagrees with FirstCycling" in w for w in route["warnings"])
    assert route["route_facts"] == "partial"


@pytest.mark.unit
def test_firstcycling_fills_towns_the_transcription_lacks(campaign):
    write_fc(campaign)
    write_override(campaign, OVERRIDE)
    route = ingest_route(campaign, "stage_15")
    assert route["start"] == "Palma del Rio"
    assert route["field_sources"]["start"] == "firstcycling"
    assert route["fc_profile_code"] == "GT2"


# --------------------------------------------------------------------------
# Validation


@pytest.mark.unit
def test_a_climb_past_the_finish_is_rejected(campaign):
    write_override(campaign, {**OVERRIDE, "climbs": [
        {"name": "Puerto Imaginario", "category": "2", "km_mark": 150.0,
         "length_km": 5.0, "gradient_pct": 6.0}]})
    route = ingest_route(campaign, "stage_15")
    assert route["climbs"][0]["km_mark"] is None
    assert any("past the finish" in e for e in route["errors"])
    assert route["route_facts"] == "partial"
    assert route["rejected"][0]["reason"]


@pytest.mark.unit
def test_a_climb_longer_than_its_km_mark_is_flagged(campaign):
    write_override(campaign, {**OVERRIDE, "climbs": [
        {"name": "Puerto Largo", "category": "1", "km_mark": 5.0,
         "length_km": 12.0, "gradient_pct": 6.0}]})
    route = ingest_route(campaign, "stage_15")
    assert any("would start before the start" in e for e in route["errors"])


@pytest.mark.unit
def test_an_implausible_gradient_is_rejected(campaign):
    write_override(campaign, {**OVERRIDE, "climbs": [
        {"name": "Puerto Vertical", "category": "1", "km_mark": 40.0,
         "length_km": 5.0, "gradient_pct": 410.0}]})
    route = ingest_route(campaign, "stage_15")
    assert route["climbs"][0]["gradient_pct"] is None
    assert any("plausible maximum" in e for e in route["errors"])


@pytest.mark.unit
def test_out_of_order_climbs_are_kept_as_transcribed_and_flagged(campaign):
    write_override(campaign, {**OVERRIDE, "climbs": list(reversed(OVERRIDE["climbs"]))})
    route = ingest_route(campaign, "stage_15")
    assert [c["name"] for c in route["climbs"]] == ["Puerto Artafi",
                                                    "Puerto de la Forestal"]
    assert route["climbs_ordered"] is False
    assert any("ascending km order" in e for e in route["errors"])
    assert route["route_facts"] == "partial"


@pytest.mark.unit
def test_an_implausible_distance_is_rejected_not_carried(campaign):
    write_override(campaign, {**OVERRIDE, "distance_km": 1102.0})
    route = ingest_route(campaign, "stage_15")
    assert route["distance_km"] is None
    assert any("outside" in e for e in route["errors"])


@pytest.mark.unit
def test_a_climb_without_a_name_is_dropped_with_a_reason(campaign):
    write_override(campaign, {**OVERRIDE, "climbs": [
        {"category": "3", "km_mark": 34.5, "length_km": 6.7, "gradient_pct": 4.1}]})
    route = ingest_route(campaign, "stage_15")
    assert route["climbs"] == []
    assert any("no climb name" in e for e in route["errors"])


@pytest.mark.unit
def test_broken_json_is_reported_not_swallowed(campaign):
    (campaign / "predictions" / "stage_15" / "route_raw.json").write_text("{oops")
    route = ingest_route(campaign, "stage_15")
    assert any("not valid JSON" in e for e in route["errors"])
    assert route["route_facts"] in ("missing", "partial")


# --------------------------------------------------------------------------
# Grading


@pytest.mark.unit
def test_nothing_present_is_missing_and_invents_nothing(campaign):
    route = ingest_route(campaign, "stage_15")
    assert route["route_facts"] == "missing"
    for field in ("distance_km", "vertical_metres", "profile_class", "start",
                  "finish"):
        assert route[field] is None
    assert route["climbs"] == []
    assert route["inputs"] == []


@pytest.mark.unit
def test_a_full_clean_transcription_is_complete(campaign):
    write_raw(campaign, RAW)
    route = ingest_route(campaign, "stage_15")
    assert route["route_facts"] == "complete"
    assert route["missing_fields"] == []
    assert route["errors"] == []
    assert route["distance_km"] == 189.7
    assert route["vertical_metres"] == 2350.0
    assert [c["km_mark"] for c in route["climbs"]] == [96.4, 141.8]


@pytest.mark.unit
def test_an_explicit_empty_climb_list_still_counts_as_complete(campaign):
    write_raw(campaign, {**RAW, "climbs_listed": False, "climbs": []})
    route = ingest_route(campaign, "stage_15")
    assert route["route_facts"] == "complete"
    assert route["climbs"] == []
    assert route["climbs_listed"] is False


@pytest.mark.unit
def test_climbs_not_listed_at_all_is_partial_not_complete(campaign):
    payload = {k: v for k, v in RAW.items() if k not in ("climbs", "climbs_listed")}
    route = ingest_route(campaign, "stage_15")  # nothing written yet
    write_raw(campaign, payload)
    route = ingest_route(campaign, "stage_15")
    assert route["route_facts"] == "partial"
    assert "climbs" in route["missing_fields"]


# --------------------------------------------------------------------------
# Output and CLI


@pytest.mark.unit
def test_route_json_is_written_beside_the_config(campaign):
    write_raw(campaign, RAW)
    write_override(campaign, OVERRIDE)
    ingest_route(campaign, "stage_15")
    written = json.loads(
        (campaign / "predictions" / "stage_15" / "route.json").read_text())
    assert written["route_facts"] == "complete"
    assert written["unit"] == "stage_15"
    assert written["source_urls"], "the transcription's source URLs are carried"


@pytest.mark.unit
def test_dry_run_writes_nothing(campaign):
    write_override(campaign, OVERRIDE)
    assert main(["ingest-route", str(campaign), "stage_15", "--dry-run"]) == 0
    assert not (campaign / "predictions" / "stage_15" / "route.json").exists()


@pytest.mark.unit
def test_cli_writes_route_json_and_reports_the_grade(campaign, capsys):
    write_raw(campaign, RAW)
    assert main(["ingest-route", str(campaign), "stage_15"]) == 0
    assert "route_facts=complete" in capsys.readouterr().out
    assert (campaign / "predictions" / "stage_15" / "route.json").exists()


@pytest.mark.unit
def test_cli_exits_one_when_a_value_had_to_be_rejected(campaign):
    write_override(campaign, {**OVERRIDE, "distance_km": "sometime around 110"})
    assert main(["ingest-route", str(campaign), "stage_15"]) == 1


@pytest.mark.unit
def test_a_missing_campaign_directory_is_an_error(tmp_path):
    with pytest.raises(RouteFactsError):
        ingest_route(tmp_path / "nope", "stage_15")
