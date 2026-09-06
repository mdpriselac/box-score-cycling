"""Editorial prose linter (chip G): lexicon, numerals, key consistency.

Fixtures: a clean paragraph in the house style, a "value bet" paragraph, a
paragraph with an invented percentage, and the minimal facts bundle in
``tests/fixtures/editorial/facts_min.json`` (numbers lifted from Vuelta 2026
stage 14).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cycling_project.nightly import lint_prose as lp

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "editorial"
FACTS = json.loads((FIXTURES / "facts_min.json").read_text())
CONFIG = {"day_key": {"gc_day": 0.6, "res_2": 0.4},
          "scenarios": {"gc_showdown": {"label": "GC showdown", "refs": [1], "tag": "t1", "note": ""},
                        "mountain_break": {"label": "Mountain break", "refs": [2], "tag": "t2",
                                           "day_key": {"res_2": 0.85, "gc_day": 0.15}, "note": ""}}}

CLEAN = ("The escape won for the third time in four mountain stages. Marco Brenner beat Santiago Buitrago "
         "by a second, and the first GC rider home, Enric Mas, was 21st at 4:12. The oracle labelled the day "
         "res_2 and the key of gc_day 0.6 / res_2 0.4 scored covered at 0.40; the record stands at 6/12 exact, "
         "11/12 covered, mean weight 0.53. The market had Mas at 3.75 (17.2%) and Buitrago at 6.50 (9.9%) over "
         "154.5 km with 11.4 km at 7.2% to finish. The 'mountain break' board, keyed res_2 0.85, surfaced five of "
         "the top 15 against the production board's two; Brenner was #22 on it at 0.2%, a 201.0 shot on the book.")

VALUE_BET = ("Buitrago at 6.50 was the value bet of the day and the smart money knew it; anyone who staked units "
             "on him got paid. Mas was odds-on to crack.")

INVENTED = ("Brenner won at 4:12 ahead of the GC group. The model had him at 23.4% on the mountain break board, "
            "and Buitrago at 9.9%.")


@pytest.fixture(scope="module")
def lexicon():
    return lp.load_lexicon()


def test_lexicon_file_is_versioned(lexicon):
    assert lexicon["version"] == "1.0.0"
    assert "bet" in lexicon["deny"] and "value bet" in lexicon["deny"]
    assert {"book", "market", "devig"} <= set(lexicon["allow"])


def test_clean_paragraph_passes(lexicon):
    report = lp.lint_sections({"retro_key_vs_oracle": CLEAN}, facts=FACTS, config=CONFIG, lexicon=lexicon)
    assert report["ok"], report
    assert report["checks"] == {"lexicon": True, "numerals": True, "key": True}


def test_value_bet_paragraph_fails_lexicon(lexicon):
    report = lp.lint_sections({"p": VALUE_BET}, facts=FACTS, config=CONFIG, lexicon=lexicon)
    assert not report["ok"]
    terms = [h["term"] for h in report["lexicon"]]
    assert "value bet" in terms            # longest match wins over "value" + "bet"
    assert "smart money" in terms and "staked" in terms and "units" in terms and "odds-on" in terms
    assert "value" not in terms and "bet" not in terms   # no double counting of the overlapped span
    # the numbers themselves are fine — only the language failed
    assert report["counts"]["numerals"] == 0


def test_invented_percentage_is_caught(lexicon):
    report = lp.lint_sections({"p": INVENTED}, facts=FACTS, config=CONFIG, lexicon=lexicon)
    assert not report["ok"]
    assert [m["token"] for m in report["numerals"]] == ["23.4%"]


def test_time_and_distance_tokens():
    idx = lp.FactIndex(FACTS)
    assert idx.has("time", "4:12") and idx.has("time", "4:15:09")
    assert not idx.has("time", "4:13")
    assert idx.has("number", "154.5") and idx.has("number", "0.53")
    assert idx.has("percent", "17.2") and idx.has("percent", "17")   # 0 dp rounding of 17.2
    assert not idx.has("number", "4338")


def test_allowlist_years_stage_numbers_dates(lexicon):
    text = "Stage 14 on 2026-09-05, the 5th of September, in the 2026 edition; top 15 by rank #1 to #21."
    report = lp.lint_sections({"p": text}, facts={}, config=None, lexicon=lexicon, max_stage=21)
    assert report["ok"], report
    report = lp.lint_sections({"p": "a 44-man escape"}, facts={}, config=None, lexicon=lexicon, max_stage=21)
    assert [m["token"] for m in report["numerals"]] == ["44"]


def test_thousands_separator_and_route_climb_stats(lexicon):
    route = {"climbs": [{"vertical_metres": 4338, "gradient_pct": 21}]}
    report = lp.lint_sections({"p": "4,338 m of climbing with pitches of 21%."}, facts={}, route=route,
                              config=None, lexicon=lexicon)
    assert report["ok"], report


def test_allowed_phrases_are_masked(lexicon):
    text = "The read was in play all day; the book priced the favourite and the market agreed; it tips it to res_2."
    report = lp.lint_sections({"p": text}, facts=None, config=None, lexicon=lexicon, check_numerals=False)
    assert report["ok"], report


def test_key_restated_with_wrong_weight(lexicon):
    ok = lp.lint_sections({"p": "the key of gc_day 0.6 / res_2 0.4 and the branch keyed res_2 0.85."},
                          config=CONFIG, lexicon=lexicon, check_numerals=False)
    assert ok["ok"], ok
    bad = lp.lint_sections({"p": "the key of gc_day 0.7 / res_2 0.3."}, config=CONFIG, lexicon=lexicon,
                           check_numerals=False)
    assert [(k["item"], k["stated"]) for k in bad["key"]] == [("gc_day", 0.7), ("res_2", 0.3)]
    # a weight the config never had, on an item it never keyed
    bad2 = lp.lint_sections({"p": "bunch at 0.5 was never on the table."}, config=CONFIG, lexicon=lexicon,
                            check_numerals=False)
    assert bad2["key"][0]["item"] == "bunch"


def test_day_key_note_may_only_restate_root_key(lexicon):
    r = lp.lint_sections({"day_key_note": "keyed res_2 0.85 / gc_day 0.15"}, config=CONFIG, lexicon=lexicon,
                         check_numerals=False)
    assert not r["ok"] and {k["item"] for k in r["key"]} == {"res_2", "gc_day"}
    r2 = lp.lint_sections({"scenario_notes": [{"scenario_key": "mountain_break", "note": "keyed res_2 0.85 / gc_day 0.15"}]},
                          config=CONFIG, lexicon=lexicon, check_numerals=False)
    assert r2["ok"] and r2["sections_checked"] == ["scenario_notes.mountain_break"]


def test_placeholders_are_rejected(lexicon):
    r = lp.lint_sections({"p": "Mas at {{p:12:win}} on the board."}, facts=FACTS, config=None, lexicon=lexicon)
    assert r["counts"]["placeholders"] == 1


def test_config_prose_fields_and_cli(tmp_path):
    cfg = json.loads(json.dumps(CONFIG))
    cfg["day_key_note"] = "A clean morning read keyed gc_day 0.6 / res_2 0.4."
    cfg["scenarios"]["gc_showdown"]["note"] = "This is the banker of the day."
    cfg["reflection"] = ["Fine paragraph.", "Anyone who punts on him."]
    path = tmp_path / "scenarios.json"
    path.write_text(json.dumps(cfg))
    prose = lp.config_prose(cfg)
    assert set(prose) >= {"day_key_note", "scenario_note.gc_showdown", "reflection"}
    report_path = tmp_path / "report.json"
    rc = lp.main(["--config", str(path), "--quiet", "--report", str(report_path)])
    assert rc == 1
    rep = json.loads(report_path.read_text())
    assert sorted(h["term"] for h in rep["lexicon"]) == ["banker", "punts"]
    assert rep["key"] == []


def test_regress_walks_campaign_roots(tmp_path):
    root = tmp_path / "camp" / "predictions" / "stage_01"
    root.mkdir(parents=True)
    (root / "scenarios.json").write_text(json.dumps({"day_key_note": "value pick here", "scenarios": {}}))
    summary = lp.regress([tmp_path])
    assert summary["files"] == 1 and summary["lexicon_hits"] == 1
    assert summary["hits_by_term"] == {"value pick": 1}
    assert not summary["ok"]
