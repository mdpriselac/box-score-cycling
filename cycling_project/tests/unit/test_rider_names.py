"""Chip EE (2026-10-03): prose names riders given-name first, decided deterministically.

The owner's example from the Langkawi stage 8 preview: "Syritsa Gleb and Gate Aaron on the main
read board … Modern Adventure Pro Cycling won stage 6 with Pickrell Riley". FirstCycling's one
``name`` field is surname first; the split comes from the UCI capture (surname in capitals) and,
without one, from a particle-aware heuristic recorded as such.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cycling_project.nightly import lint_prose
from cycling_project.nightly import rider_names as rn

pytestmark = pytest.mark.unit

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "editorial" / "langkawi_stage_05"


@pytest.mark.parametrize("fc_name, uci_name, expected, source", [
    ("Syritsa Gleb", None, "Gleb Syritsa", "heuristic"),
    ("van der Poel Mathieu", None, "Mathieu van der Poel", "heuristic"),
    ("De Bod Stefan", None, "Stefan De Bod", "heuristic"),
    ("Van Den Boer Seppe", None, "Seppe Van Den Boer", "heuristic"),
    ("Sierra Juan David", None, "Juan David Sierra", "heuristic"),     # two given names
    ("Pogacar", None, "Pogacar", "heuristic"),
    # (a) the UCI form, accents as the UCI gives them
    (None, "LOPEZ SEVILLA Diego Pablo", "Diego Pablo Lopez Sevilla", "uci"),
    ("Lopez Sevilla Diego Pablo", "LOPEZ SEVILLA Diego Pablo", "Diego Pablo Lopez Sevilla", "uci"),
    ("Smit Willem Jakobus", "SMIT Willem Jakobus", "Willem Jakobus Smit", "uci"),
    ("Pezzo Rosola Kevin", "PEZZO ROSOLA Kevin", "Kevin Pezzo Rosola", "uci"),   # the heuristic's miss, fixed
    ("Bregnhoj Mathias", "BREGNHØJ Mathias", "Mathias Bregnhøj", "uci"),
    ("McGill Scott", "MCGILL Scott", "Scott McGill", "uci"),            # FirstCycling's letter case kept
    (None, "VAN ENGELEN Adne", "Adne van Engelen", "uci"),
    # the token set stays FirstCycling's: no legal middle names or second surnames in prose
    ("Gate Aaron", "GATE Aaron Murray", "Aaron Gate", "uci"),
    ("Balderstone Abel", "BALDERSTONE ROUMENS Abel", "Abel Balderstone", "uci"),
    # a UCI form that does not split the FirstCycling tokens falls back, and says so
    ("Pidcock Tom", "PIDCOCK Thomas", "Tom Pidcock", "heuristic"),
    ("Skjelmose Mattias", "JENSEN Mattias Skjelmose Jennow", "Mattias Skjelmose", "heuristic"),
])
def test_display_name(fc_name, uci_name, expected, source):
    assert rn.display_name_with_source(fc_name, uci_name=uci_name) == (expected, source)
    assert rn.display_name(fc_name, uci_name=uci_name) == expected


def test_split_uci_name():
    assert rn.split_uci_name("LOPEZ SEVILLA Diego Pablo") == ("LOPEZ SEVILLA", "Diego Pablo")
    assert rn.split_uci_name("ARRIOLA-BENGOA BEITIA Julen") == ("ARRIOLA-BENGOA BEITIA", "Julen")
    assert rn.split_uci_name("Diego Pablo") is None and rn.split_uci_name("LOPEZ") is None


def _capture(tmp_path: Path) -> Path:
    camp = tmp_path / "camp"
    res = camp / "results" / "stage_01"
    res.mkdir(parents=True)
    (res / "results.json").write_text(json.dumps({
        "results": [{"place": "1", "name": "Lopez Diego", "rider_id": "1"},
                    {"place": "2", "name": "Magli Filippo", "rider_id": "2"},     # mis-joined row: no shared surname
                    {"place": "3", "name": "Someone Else", "rider_id": "uci:x"}],
        "uci": {"raw_results": [{"rank": "1", "lastname": "LOPEZ SEVILLA", "firstname": "Diego Pablo"},
                                {"rank": "2", "lastname": "MODESTI", "firstname": "Filippo"},
                                {"rank": "3", "lastname": "ELSE", "firstname": "Someone"}]}}))
    return camp


def test_name_book_joins_the_campaign_capture_on_place_and_surname(tmp_path):
    book = rn.campaign_name_book(_capture(tmp_path), crosswalk_dir=tmp_path / "none")
    assert book.display("Lopez Diego") == ("Diego Lopez", "uci")
    assert book.lookup("Magli Filippo") is None                       # never borrows another rider's split
    assert book.display("Magli Filippo") == ("Filippo Magli", "heuristic")
    assert book.lookup("Else Someone") is None                        # provisional uci: ids are skipped
    # a preview never reads the unit it previews
    assert len(rn.campaign_name_book(_capture(tmp_path / "b"), exclude_units=("stage_01",),
                                     crosswalk_dir=tmp_path / "none")) == 0


def test_name_book_reads_confirmed_aliases_and_drops_homonyms(tmp_path):
    xw = tmp_path / "xw"
    xw.mkdir()
    (xw / "uci_aliases.csv").write_text("uci_key,uci_name,fc_rider_id,fc_name\nk,JENSEN Mattias Skjelmose Jennow,77103,Skjelmose Mattias\n"
                                        "k2,SMIT Willem Jakobus,1,Smit Willem\nk3,SMIT Willem Hendrik,2,Smit Willem\n")
    (xw / "rider_crosswalk.csv").write_text("pcs_slug,fc_rider_id,pcs_name,fc_name\ns,5,ROGLIČ Primož,Roglic Primoz\n")
    book = rn.campaign_name_book(tmp_path / "no-campaign", crosswalk_dir=xw)
    assert book.display("Roglic Primoz") == ("Primož Roglič", "crosswalk")
    assert book.lookup("Smit Willem") is None
    assert book.display("Skjelmose Mattias") == ("Mattias Skjelmose", "heuristic")


def test_annotate_adds_display_names_and_never_touches_name():
    bundle = {
        "campaign": {"slug": "x", "name": "Tour de Langkawi"},
        "boards": [{"references": [{"name": "Tour of the Alps - Stage: 03", "date": "2026-04-22"}],
                    "top15_with_key": [{"rank": 1, "name": "Syritsa Gleb", "rider_id": 9}]}],
        "market": {"top": [{"name": "Gleb Syritsa", "odds": 4.0}, {"name": "Nobody Known", "odds": 9.0}],
                   "all": {"Gleb Syritsa": 20.0}},
        "abandons": {"names": ["van der Poel Mathieu"], "n": 1},
        "scorecard": {"ledger": [{"stage": 1, "winner": "Pickrell Riley"}], "stage": None},
    }
    book = rn.NameBook()
    book.add("Syritsa Gleb", "SYRITSA Gleb", rn.SOURCE_UCI)
    rn.annotate_bundle(bundle, book)
    row = bundle["boards"][0]["top15_with_key"][0]
    assert row["name"] == "Syritsa Gleb" and row["display_name"] == "Gleb Syritsa" and row["display_name_source"] == "uci"
    assert "display_name" not in bundle["campaign"] and "display_name" not in bundle["boards"][0]["references"][0]
    mk = bundle["market"]["top"]
    assert mk[0]["display_name"] == "Gleb Syritsa" and mk[0]["display_name_source"] == "uci"
    assert mk[1]["display_name"] == "Nobody Known" and mk[1]["display_name_source"] == "market"
    assert bundle["abandons"]["display_names"] == ["Mathieu van der Poel"]
    assert bundle["scorecard"]["ledger"][0]["winner_display_name"] == "Riley Pickrell"
    assert rn.name_pairs(bundle) == {"Syritsa Gleb": "Gleb Syritsa"}


def test_the_langkawi_fixture_bundle_carries_display_names():
    facts = json.loads((FIXTURE / "editorial_facts_stage_preview.json").read_text())
    rows = [r for b in facts["boards"] for r in b.get("top15_with_key", []) + b.get("top15_production", [])]
    assert rows and all(r["display_name"] and r["display_name_source"] for r in rows)
    jasch = next(r for r in rows if r["name"] == "Jasch Lennart")
    assert jasch["display_name"] == "Lennart Jasch" and jasch["display_name_source"] == "uci"
    assert facts["gc_morning"]["top"][1]["display_name"] == "Abel Balderstone"


def test_name_order_is_advisory_and_reaches_the_retry_report():
    facts = {"boards": [{"top15_with_key": [{"rank": 4, "name": "Syritsa Gleb", "display_name": "Gleb Syritsa",
                                             "display_name_source": "uci"}]}],
             "market": {"top": [{"name": "Aaron Gate", "odds": 9.0, "display_name": "Aaron Gate",
                                 "display_name_source": "market"}]}}
    sections = {"stage_read": "Syritsa Gleb sits #4 on the main read board; Gleb Syritsa is the same man.",
                "model_vs_market": "Nothing else."}
    rep = lint_prose.lint_sections(sections, facts=facts, check_numerals=False)
    assert rep["ok"] is True and rep["counts"]["lexicon"] == 0             # never fails a draft
    assert rep["advisory_counts"] == {"name_order": 1} and rep["checks"]["name_order"] is True
    assert rep["name_order"][0]["token"] == "Syritsa Gleb" and rep["name_order"][0]["use"] == "Gleb Syritsa"
    compact = lint_prose.retry_report(rep)
    assert compact == {"name_order": [{"section": "stage_read", "token": "Syritsa Gleb", "use": "Gleb Syritsa"}]}


def test_the_retry_report_is_compact_and_folds_duplicates():
    rep = lint_prose.lint_sections({"stage_read": "A value bet at {{route.distance_km}} and {{route.distance_km}}.",
                                    "headline": "gc_day 0.7"},
                                   config={"day_key": {"gc_day": 0.6, "res_2": 0.4}}, check_numerals=False)
    compact = lint_prose.retry_report(rep, validation_errors=["claims: missing"])
    assert compact["lexicon"] == [{"section": "stage_read", "token": "value bet"}]
    assert compact["placeholders"] == [{"section": "stage_read", "token": "{{route.distance_km}}", "n": 2}]
    assert compact["key"][0]["token"] == "gc_day 0.7" and compact["key"][0]["approved"] == {"root": 0.6}
    assert compact["schema"] == ["claims: missing"]
