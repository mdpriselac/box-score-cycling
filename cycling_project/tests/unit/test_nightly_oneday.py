"""The one-day race path (build queue chip K, NIGHTLY_AGENT_WORKFLOW.md §2.6).

Covers the four pieces a one-day race needs that a stage race does not: the
``target: one_day`` config shape and its loader, the ``results/race/`` archive,
the UCI one-day capture (one classification, no general classification), and
the page + site-frame renderers.

Fixtures: ``fixtures/uci/oneday-gp-industria-78396/`` (the real capture chip N
archived — GP Industria & Artigianato 2026, 161 rows, won by Pidcock). The
serving database is synthesised per test from that capture, so nothing here
touches the real database or the network.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

from cycling_project.nightly import oneday
from cycling_project.nightly import uci_ingest as ui

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
ONEDAY_UCI = FIXTURES / "uci" / "oneday-gp-industria-78396"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
SITE_BUILD = PROJECT_ROOT / "netlify_site" / "build"


def _load_script(name):
    """Site builders run as scripts, not as package modules."""
    spec = importlib.util.spec_from_file_location(f"{name}_under_test", SITE_BUILD / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# helpers: a synthetic serving database
# ---------------------------------------------------------------------------

def _make_db(path: Path, *, riders=(), races=(), competitions=(), field_features=(), results=()):
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE riders (id INTEGER PRIMARY KEY, fc_rider_id TEXT UNIQUE NOT NULL,
                             name TEXT NOT NULL, birth_year INTEGER);
        CREATE TABLE teams (id INTEGER PRIMARY KEY, name TEXT, fc_team_id TEXT);
        CREATE TABLE races (id INTEGER PRIMARY KEY, fc_race_id TEXT, name TEXT, year INTEGER);
        CREATE TABLE competitions (id INTEGER PRIMARY KEY, race_id INTEGER, name TEXT,
                                   stage_number INTEGER, competition_type TEXT, date TEXT,
                                   winning_time REAL, url TEXT);
        CREATE TABLE competition_field_features (competition_id INTEGER PRIMARY KEY);
        CREATE TABLE rider_results (competition_id INTEGER, rider_id INTEGER, team_id INTEGER,
                                    place INTEGER, time_gap REAL);
        """
    )
    con.executemany("INSERT INTO riders (id, fc_rider_id, name, birth_year) VALUES (?,?,?,?)", riders)
    con.executemany("INSERT INTO races (id, fc_race_id, name, year) VALUES (?,?,?,?)", races)
    con.executemany(
        "INSERT INTO competitions (id, race_id, name, stage_number, competition_type, date, "
        "winning_time, url) VALUES (?,?,?,?,?,?,?,?)", competitions)
    con.executemany("INSERT INTO competition_field_features (competition_id) VALUES (?)",
                    [(c,) for c in field_features])
    con.executemany("INSERT INTO rider_results (competition_id, rider_id, team_id, place, time_gap) "
                    "VALUES (?,?,?,?,?)", results)
    con.commit()
    con.close()
    return path


@pytest.fixture
def refs_db(tmp_path):
    """Five usable editions of race 54, one without field features, one in the target year."""
    return _make_db(
        tmp_path / "refs.db",
        races=[(i, "54", "Strade Bianche", y) for i, y in enumerate(range(2020, 2027), start=1)],
        competitions=[(100 + i, i, "Strade Bianche", None, "one_day", f"{y}-03-07", None, "")
                      for i, y in enumerate(range(2020, 2027), start=1)],
        # 2021 (id 102) has no field-features row, so it cannot be a reference
        field_features=[101, 103, 104, 105, 106, 107],
    )


# ---------------------------------------------------------------------------
# own-history references
# ---------------------------------------------------------------------------

def test_own_edition_refs_are_the_race_s_own_usable_editions_newest_first(refs_db):
    refs = oneday.own_edition_refs("54", 2026, db_path=refs_db)

    assert refs == [106, 105, 104, 103, 101]        # 2025..2022 then 2020; 2021 has no features
    assert 107 not in refs                          # the edition being predicted is excluded
    assert oneday.own_edition_refs("54", 2026, limit=2, db_path=refs_db) == [106, 105]
    assert oneday.own_edition_refs("99", 2026, db_path=refs_db) == []
    assert oneday.own_edition_refs("54", 2026, db_path=refs_db.parent / "missing.db") == []


def test_own_edition_detail_carries_the_year_of_each_reference(refs_db):
    detail = oneday.own_edition_detail("54", 2026, limit=3, db_path=refs_db)

    assert [d["year"] for d in detail] == [2025, 2024, 2023]
    assert [d["competition_id"] for d in detail] == [106, 105, 104]


# ---------------------------------------------------------------------------
# the config loader
# ---------------------------------------------------------------------------

def _config(**over):
    cfg = oneday.build_config(fc_race_id="54", year=2026, date="2026-03-07",
                              label="Strade Bianche 2026", refs=[9703, 100, 271],
                              tag_prefix="strade_2026")
    cfg.update(over)
    return cfg


def test_a_built_one_day_config_validates_and_names_its_own_history_scenario():
    cfg = _config()

    assert oneday.validate_config(cfg) == []
    assert cfg["target"] == "one_day" and "stage" not in cfg and "day_key" not in cfg
    spec = cfg["scenarios"][oneday.OWN_HISTORY_KEY]
    assert spec["refs"] == [9703, 100, 271]
    assert spec["tag"] == "strade_2026_own_history"


def test_build_config_adds_archetype_alternates_and_the_post_hoc_mark():
    cfg = oneday.build_config(
        fc_race_id="54", year=2026, date="2026-03-07", label="Strade Bianche 2026",
        refs=[9703, 100], tag_prefix="strade_2026", post_hoc=True,
        alternates={"ardennes": {"refs": [9768, 965], "note": "a hilly classic"}})

    assert oneday.validate_config(cfg) == []
    assert cfg["post_hoc"] is True
    assert set(cfg["scenarios"]) == {"own_history", "ardennes"}
    assert cfg["scenarios"]["ardennes"]["tag"] == "strade_2026_ardennes"
    assert all(s["post_hoc"] for s in cfg["scenarios"].values())


@pytest.mark.parametrize("mutate, expected", [
    (lambda c: c.update(target="stage"), "not 'one_day'"),
    (lambda c: c.update(stage=4), "must not carry a stage number"),
    (lambda c: c.update(void_stages=[3]), "no stages to void"),
    (lambda c: c.update(day_key={"res_2": 1.0}), "skips the day-menu channel"),
    (lambda c: c["scenarios"]["own_history"].update(day_key={"res_2": 1.0}), "skips the day-menu channel"),
    (lambda c: c["scenarios"]["own_history"].update(refs=[0]), "placeholder/missing refs"),
    (lambda c: c["scenarios"]["own_history"].pop("tag"), "no tag"),
    (lambda c: c.update(date=None), "config lacks date"),
    (lambda c: c.update(scenarios={}), "config lacks scenarios"),
    (lambda c: c["scenarios"]["own_history"].update(scores={"hilly": 0.9}), "need base_refs"),
])
def test_the_loader_names_every_way_a_one_day_config_can_be_wrong(mutate, expected):
    cfg = _config()
    mutate(cfg)

    problems = oneday.validate_config(cfg)

    assert any(expected in p for p in problems), problems


def test_load_config_reads_the_file_and_reports_the_problems_in_one_error(tmp_path):
    good, bad = tmp_path / "good.json", tmp_path / "bad.json"
    good.write_text(json.dumps(_config()))
    bad.write_text(json.dumps(_config(stage=4, day_key={"res_2": 1.0})))

    assert oneday.load_config(good)["label"] == "Strade Bianche 2026"
    with pytest.raises(oneday.OneDayConfigError) as exc:
        oneday.load_config(bad)
    assert "stage number" in str(exc.value) and "day-menu" in str(exc.value)
    (tmp_path / "broken.json").write_text("{not json")
    with pytest.raises(oneday.OneDayConfigError):
        oneday.load_config(tmp_path / "broken.json")


def test_strip_stage_keys_clears_what_a_stage_template_carries():
    cfg = _config(stage=4, void_stages=[3], day_key={"res_2": 1.0}, day_key_note="x")
    cfg["scenarios"]["own_history"]["day_key"] = {"res_1": 1.0}

    assert oneday.validate_config(oneday.strip_stage_keys(cfg)) == []


# ---------------------------------------------------------------------------
# the start-list handover the cloud container gets
# ---------------------------------------------------------------------------

def test_a_handover_start_list_becomes_the_team_objects_serving_expects(tmp_path):
    path = oneday.startlist_path(tmp_path)
    path.write_text(json.dumps({
        "fc_race_id": "54", "year": 2026, "teams": [
            {"name": "UAE Team Emirates-XRG", "team_id": "25778", "riders": [
                {"name": "Pogacar Tadej", "rider_id": "45992", "number": "1"},
                {"rider_name": "del Toro Isaac", "rider_fc_id": "155993", "bib": "2"}]}]}))

    teams = oneday.load_startlist_file(path)

    assert [t.name for t in teams] == ["UAE Team Emirates-XRG"]
    assert [r.rider_id for r in teams[0].riders] == ["45992", "155993"]
    assert teams[0].riders[0].team_id == "25778" and teams[0].riders[1].number == "2"


def test_a_handover_rider_without_a_firstcycling_id_is_refused(tmp_path):
    path = oneday.startlist_path(tmp_path)
    path.write_text(json.dumps({"teams": [{"name": "T", "riders": [{"name": "Nobody"}]}]}))

    with pytest.raises(oneday.OneDayConfigError) as exc:
        oneday.load_startlist_file(path)
    assert "names are never ids" in str(exc.value)


def test_an_empty_handover_start_list_is_refused(tmp_path):
    path = oneday.startlist_path(tmp_path)
    path.write_text(json.dumps({"teams": []}))

    with pytest.raises(oneday.OneDayConfigError):
        oneday.load_startlist_file(path)


# ---------------------------------------------------------------------------
# the results/race/ archive
# ---------------------------------------------------------------------------

@pytest.fixture
def settled_db(tmp_path):
    return _make_db(
        tmp_path / "settled.db",
        riders=[(1, "45992", "Pogacar Tadej", 1998), (2, "199233", "Seixas Paul", 2006),
                (3, "155993", "del Toro Isaac", 2003)],
        races=[(1, "54", "Strade Bianche", 2026)],
        competitions=[(10293, 1, "Strade Bianche", None, "one_day", "2026-03-07", 17115.0,
                       "https://firstcycling.com/race.php?r=54&y=2026")],
        field_features=[10293],
        results=[(10293, 1, None, 1, 0.0), (10293, 2, None, 2, 60.0), (10293, 3, None, 3, 69.0)],
    )


def test_a_settled_one_day_race_exports_the_same_archive_a_stage_ingest_writes(tmp_path, settled_db):
    camp = tmp_path / "strade-bianche-2026"

    out = oneday.export_results_from_db(camp, "54", 2026, db_path=settled_db)

    assert out["written"] == ["results.json", "results.csv", "classifications.json"]
    assert oneday.is_settled(camp)
    header = (camp / "results" / "race" / "results.csv").read_text().splitlines()[0]
    assert header == "place,name,rider_id,team,team_id,gap,dob"
    payload = oneday.read_results(camp)
    assert payload["stage"] == "race" and payload["source"] == "db"
    assert payload["race_time"] == 17115.0 and payload["n_results"] == 3
    rows = oneday.classified(payload)
    assert [r["place"] for r in rows] == ["1", "2", "3"]
    assert rows[0] == {"place": "1", "name": "Pogacar Tadej", "rider_id": "45992", "team": "",
                       "team_id": "", "gap": 0, "dob": "1998"}
    assert rows[1]["gap"] == 60.0


def test_read_results_is_none_until_the_race_is_settled(tmp_path):
    camp = tmp_path / "empty-campaign"

    assert oneday.read_results(camp) is None
    assert oneday.classified(None) == []
    assert not oneday.is_settled(camp)


def test_exporting_a_race_the_database_does_not_hold_is_an_error(tmp_path, settled_db):
    with pytest.raises(oneday.OneDayConfigError):
        oneday.export_results_from_db(tmp_path / "c", "999", 2026, db_path=settled_db)


# ---------------------------------------------------------------------------
# the UCI one-day capture: one classification, no general classification
# ---------------------------------------------------------------------------

@pytest.fixture
def uci_campaign(tmp_path):
    """The GP Industria capture, with a database holding exactly its field."""
    camp = tmp_path / "gp-industria-artigianato-2026"
    (camp / "results" / "race").mkdir(parents=True)
    shutil.copytree(ONEDAY_UCI, camp / "results" / "race" / "uci")
    (camp / "campaign.json").write_text(json.dumps({
        "slug": "gp-industria-artigianato-2026", "name": "GP Industria & Artigianato",
        "fc_race_id": "263", "year": 2026, "is_stage_race": False,
        "start_date": "2026-09-06", "end_date": "2026-09-06",
        "stages": [{"number": None, "date": "2026-09-06", "kind": "one_day"}]}))

    doc = json.loads((ONEDAY_UCI / "gc.json").read_text())
    riders, seen = [], set()
    for i, entry in enumerate(doc["results"], start=1):
        v = entry["values"]
        name = f"{v['lastname'].title()} {v['firstname'].title()}"
        if name in seen:
            continue
        seen.add(name)
        riders.append((i, str(900000 + i), name, 2026 - int(v["age"]) if v.get("age") else None))
    db = _make_db(tmp_path / "field.db", riders=riders)
    return camp, db


def test_a_one_day_uci_capture_ingests_from_its_single_classification(uci_campaign):
    camp, db = uci_campaign

    report = ui.ingest(camp, "race", db_path=db)

    assert report.verdict == "accepted", report.failing
    assert report.winner == "PIDCOCK Thomas" and report.winning_time == 16388.0
    assert (report.n_classified, report.n_abandons) == (82, 79)
    names = [c.name for c in report.checks]
    assert "one_day_single_classification" in names
    assert "gc_winner_and_gaps" not in names and "row_counts_plausible" not in names
    capture = next(c for c in report.checks if c.name == "capture_present")
    assert capture.detail["unit_kind"] == "one_day" and capture.detail["required"] == ["gc"]


def test_a_one_day_race_settles_on_the_following_local_day(uci_campaign, tmp_path, capsys):
    camp, db = uci_campaign

    assert _drv_run(camp, tmp_path, "plan", today="2026-09-06", db_path=db) == 0
    race_day = json.loads(capsys.readouterr().out)
    assert race_day["settle"] == []

    assert _drv_run(camp, tmp_path, "plan", today="2026-09-07", db_path=db) == 0
    next_day = json.loads(capsys.readouterr().out)
    assert next_day["settle"] == ["race"]
    unit = next(u for u in next_day["units"] if u["unit"] == "race")
    assert "settle_late" in unit["flags"]


def test_the_one_day_archive_has_no_gc_csv(uci_campaign):
    camp, db = uci_campaign

    report = ui.ingest(camp, "race", db_path=db)

    assert report.written == ["results.json", "results.csv", "classifications.json"]
    unit_dir = camp / "results" / "race"
    assert not (unit_dir / "gc.csv").exists()
    tables = json.loads((unit_dir / "classifications.json").read_text())["tables"]
    assert list(tables) == ["sta"]
    payload = json.loads((unit_dir / "results.json").read_text())
    assert payload["stage"] == "race" and payload["stage_name"] == "GP Industria & Artigianato"
    assert payload["date"] == "2026-09-06" and payload["source"] == "uci"
    assert payload["results"][0]["name"].endswith("Thomas") or "Pidcock" in payload["results"][0]["name"]


def test_the_one_day_archive_is_the_shape_the_page_builder_reads(uci_campaign):
    camp, db = uci_campaign
    ui.ingest(camp, "race", db_path=db)

    payload = oneday.read_results(camp)
    rows = oneday.classified(payload)

    assert oneday.is_settled(camp)
    assert len(rows) == 82 and rows[0]["gap"] == 0
    assert set(rows[0]) == {"place", "name", "rider_id", "team", "team_id", "gap", "dob"}


def test_the_pcs_fallback_refuses_a_one_day_capture_rather_than_half_writing_one(tmp_path):
    """PCS is still stage-shaped. It must reject, never produce a partial archive."""
    from cycling_project.nightly import pcs_ingest

    camp = tmp_path / "gpia"
    pcs = camp / "results" / "race" / "pcs"
    pcs.mkdir(parents=True)
    (pcs / "stage.html").write_text("<html></html>")
    (pcs / "startlist.html").write_text("<html></html>")

    report = pcs_ingest.ingest(camp, "race")

    assert report.verdict == "rejected" and report.written == []
    assert "gc" in report.checks[0].detail["missing"]
    assert not (camp / "results" / "race" / "results.csv").exists()


def test_a_stage_capture_still_needs_both_classifications():
    from cycling_project.nightly import uci_acquire as ua

    assert ua.required_kinds("race") == ("gc",)
    assert ua.required_kinds("stage_14") == ("stage", "gc")


# ---------------------------------------------------------------------------
# the page builder
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def page_mod():
    return _load_script("build_oneday_page")


def _board(key="own_history", **over):
    board = {
        "scenario": "Strade Bianche 2026 on its own recent editions",
        "scenario_key": key, "stage_number": None, "target": "one_day",
        "references": [{"competition_id": 9703, "name": "Strade Bianche - Strade Bianche",
                        "date": "2025-03-08"}],
        "model_version": "d911de60f75ca053|strade_2026_own_history",
        "day_key": None, "board": "production", "book_source": None, "state": None,
        "form_status": {"mode": "live", "asof_date": "2026-09-08", "error": None},
        "avg_profile": {"race_sprint_score": 0.0, "race_rolling_score": 0.74},
        "riders": [
            {"rider_id": 1, "rider_name": "Pogacar Tadej", "team_name": "UAE", "blend_win_p": 0.59,
             "prob_win": 0.57, "lambdarank_win_p": 0.42, "prob_podium": 0.8, "prob_top15": 0.95,
             "book_odds": None, "book_devig": None},
            {"rider_id": 2, "rider_name": "Seixas Paul", "team_name": "Decathlon", "blend_win_p": 0.38,
             "prob_win": 0.39, "lambdarank_win_p": 0.27, "prob_podium": 0.6, "prob_top15": 0.9,
             "book_odds": None, "book_devig": None},
        ],
    }
    board.update(over)
    return board


@pytest.fixture
def page_campaign(tmp_path):
    camp = tmp_path / "strade-bianche-2026"
    pred = camp / "predictions" / "race"
    pred.mkdir(parents=True)
    (camp / "campaign.json").write_text(json.dumps({
        "slug": "strade-bianche-2026", "name": "Strade Bianche 2026", "year": 2026,
        "site": {"route_slug": "strade-bianche"}}))
    cfg = oneday.build_config(fc_race_id="54", year=2026, date="2026-03-07",
                              label="Strade Bianche 2026", refs=[9703],
                              tag_prefix="strade_2026", post_hoc=True)
    (pred / "scenarios.json").write_text(json.dumps(cfg))
    (pred / "own_history.json").write_text(json.dumps(_board()))
    return camp


def test_the_page_identity_comes_from_the_campaign_registry(page_mod, page_campaign):
    config = json.loads((page_campaign / "predictions/race/scenarios.json").read_text())

    ident = page_mod.campaign_identity(page_campaign, config)

    assert ident["slug"] == "strade-bianche" and ident["year"] == 2026
    assert ident["page"] == "strade-bianche-2026.html"
    assert ident["hub_url"] == "/race/strade-bianche/2026"


def test_a_slug_without_a_registry_falls_back_to_the_campaign_directory(page_mod, tmp_path):
    camp = tmp_path / "milano-sanremo-2027"

    ident = page_mod.campaign_identity(camp, {"year": 2027, "label": "Milano-Sanremo 2027"})

    assert ident["slug"] == "milano-sanremo" and ident["page"] == "milano-sanremo-2027.html"


def test_the_page_builder_refuses_a_stage_config(page_mod, tmp_path):
    cfg = tmp_path / "scenarios.json"
    cfg.write_text(json.dumps({"stage": 4, "scenarios": {}}))

    with pytest.raises(SystemExit) as exc:
        page_mod.load_race(cfg)
    assert "build_stage_page" in str(exc.value)


def test_an_unsettled_page_says_so_and_a_post_hoc_board_names_the_form_leak(page_mod, page_campaign):
    config, boards, results, root = page_mod.load_race(page_campaign / "predictions/race/scenarios.json")
    ident = page_mod.campaign_identity(root, config)

    html = page_mod.render(config, boards, results, ident)

    assert results is None
    assert "hasn't been settled yet" in html
    assert "Post-hoc reconstruction, not a published prediction" in html
    assert "re-aged to 8 September 2026" in html          # form asof is after race day
    assert "Strade Bianche - Strade Bianche" not in html  # de-duplicated reference name
    assert "Strade Bianche (2025)" in html
    for column in ("Blend", "Cascade", "LambdaRank", "Market odds", "Market devig", "Max edge"):
        assert f'<th class="num">{column}</th>' in html


def test_a_settled_page_scores_the_winner_and_joins_the_result_by_rider_id(
        page_mod, page_campaign, monkeypatch, tmp_path):
    res = page_campaign / "results" / "race"
    res.mkdir(parents=True)
    res.joinpath("results.json").write_text(json.dumps({
        "stage": "race", "results": [
            {"place": "1", "name": "Pogacar Tadej", "rider_id": "45992", "team": "UAE", "gap": 0},
            {"place": "2", "name": "Seixas Paul", "rider_id": "199233", "team": "Decathlon", "gap": 60.0},
        ]}))
    res.joinpath("results.csv").write_text("place,name,rider_id,team,team_id,gap,dob\n")
    db = _make_db(tmp_path / "join.db",
                  riders=[(1, "45992", "Pogacar Tadej", 1998), (2, "199233", "Seixas Paul", 2006)])
    monkeypatch.setattr(page_mod, "DB_PATH", db)

    config, boards, results, root = page_mod.load_race(page_campaign / "predictions/race/scenarios.json")
    html = page_mod.render(config, boards, results, page_mod.campaign_identity(root, config))

    assert "Result — won by Pogacar Tadej" in html
    assert "Scoring — probability given to the actual winner" in html
    assert "59.00%" in html                                  # blend on the winner, two decimals
    assert "normalised-name fallback" not in html            # every row joined on the fc id


def test_the_name_fallback_is_reported_when_the_id_join_misses(page_mod, page_campaign, monkeypatch, tmp_path):
    res = page_campaign / "results" / "race"
    res.mkdir(parents=True)
    res.joinpath("results.json").write_text(json.dumps({
        "stage": "race", "results": [
            {"place": "1", "name": "Pogacar Tadej", "rider_id": "uci:pogacar|tadej", "team": "UAE", "gap": 0}]}))
    monkeypatch.setattr(page_mod, "DB_PATH", tmp_path / "absent.db")

    config, boards, results, root = page_mod.load_race(page_campaign / "predictions/race/scenarios.json")
    html = page_mod.render(config, boards, results, page_mod.campaign_identity(root, config))

    assert "1 row(s) needed the normalised-name fallback" in html


def test_reference_names_lose_the_duplicated_half(page_mod):
    assert page_mod.ref_name("Strade Bianche - Strade Bianche") == "Strade Bianche"
    assert page_mod.ref_name("Tour de France - Stage 4") == "Tour de France - Stage 4"
    assert page_mod.ref_name(None) == ""


# ---------------------------------------------------------------------------
# the site index and frame
# ---------------------------------------------------------------------------

@pytest.fixture
def index_mod(tmp_path, monkeypatch):
    mod = _load_script("build_site_index")
    site, perf = tmp_path / "site", tmp_path / "perf"
    (site / "_frame").mkdir(parents=True)
    perf.mkdir()
    monkeypatch.setattr(mod, "SITE_DIR", site)
    monkeypatch.setattr(mod, "PERF_ROOT", perf)
    return mod, site, perf


ONE_DAY_CAMP = {
    "dir": "strade-bianche-2026", "slug": "strade-bianche", "year": 2026,
    "name": "Strade Bianche 2026", "short_name": "Strade Bianche 2026", "type": "one_day",
    "prefix": "", "n_stages": 1, "start_date": "2026-03-07", "end_date": "2026-03-07",
    "blurb": "b", "extra_pages": {},
}


def test_a_one_day_campaign_indexes_as_one_unit(index_mod):
    mod, site, perf = index_mod
    pred = perf / "strade-bianche-2026" / "predictions" / "race"
    pred.mkdir(parents=True)
    cfg = oneday.build_config(fc_race_id="54", year=2026, date="2026-03-07",
                              label="Strade Bianche 2026", refs=[9703],
                              tag_prefix="strade_2026", post_hoc=True)
    (pred / "scenarios.json").write_text(json.dumps(cfg))
    (pred / "own_history.json").write_text("{}")
    (perf / "strade-bianche-2026" / "results" / "race").mkdir(parents=True)
    (perf / "strade-bianche-2026" / "results" / "race" / "results.csv").write_text("place\n")
    (site / "strade-bianche-2026.html").write_text("<html>")

    race = mod.build_campaign(ONE_DAY_CAMP, __import__("datetime").date(2026, 9, 8))

    assert race["n_stages"] == 1 and race["n_settled"] == 1 and race["post_hoc"] is True
    entry = race["stages"][0]
    assert entry["kind"] == "race" and entry["unit"] == "race" and entry["stage"] is None
    assert entry["status"] == "settled" and entry["url"] == "/race/strade-bianche/2026/prediction"
    assert entry["asset"] == "/strade-bianche-2026.html"


def test_a_one_day_race_never_claims_the_gc_or_diary_pages(index_mod):
    """An empty prefix would otherwise match the Tour's own gc.html / stages.html."""
    mod, site, perf = index_mod
    (perf / "strade-bianche-2026").mkdir()
    (site / "gc.html").write_text("<html>")
    (site / "stages.html").write_text("<html>")

    race = mod.build_campaign(ONE_DAY_CAMP, __import__("datetime").date(2026, 9, 8))

    assert race["pages"] == {}
    aliases, clean = mod.build_routes([race])
    assert "/gc.html" not in aliases and "/stages.html" not in aliases


def test_the_one_day_prediction_page_gets_a_clean_url_and_a_redirect(index_mod):
    mod, site, perf = index_mod
    (perf / "strade-bianche-2026").mkdir()
    (site / "strade-bianche-2026.html").write_text("<html>")

    race = mod.build_campaign(ONE_DAY_CAMP, __import__("datetime").date(2026, 9, 8))
    aliases, clean = mod.build_routes([race])

    assert aliases["/strade-bianche-2026.html"] == "/race/strade-bianche/2026/prediction"
    assert clean["/race/strade-bianche/2026/prediction"] == {
        "asset": "/strade-bianche-2026.html", "base": True,
        "chrome": True, "active": "races"}
    assert clean["/race/strade-bianche/2026"]["asset"] == "/_frame/race/strade-bianche-2026.html"


@pytest.fixture(scope="module")
def frame_mod():
    return _load_script("build_site_frame")


def _index_race(**over):
    race = {
        "slug": "strade-bianche", "year": 2026, "name": "Strade Bianche 2026",
        "short_name": "Strade Bianche 2026", "type": "one_day", "status": "settled",
        "start_date": "2026-03-07", "end_date": "2026-03-07", "blurb": "The first one-day race.",
        "url": "/race/strade-bianche/2026", "pages": {}, "n_stages": 1, "n_settled": 1,
        "n_predicted": 1, "post_hoc": True,
        "stages": [{"stage": None, "unit": "race", "kind": "race", "date": "2026-03-07",
                    "label": "Strade Bianche 2026", "status": "settled", "predicted": True,
                    "post_hoc": True, "url": "/race/strade-bianche/2026/prediction",
                    "asset": "/strade-bianche-2026.html"}],
    }
    race.update(over)
    return race


def test_the_one_day_hub_shows_the_single_page_and_its_status(frame_mod):
    html = frame_mod.render_race_hub({}, _index_race())

    assert "One-day race · 2026" in html
    assert 'class="chip settled"' in html and 'class="chip post_hoc"' in html
    assert 'href="/race/strade-bianche/2026/prediction"' in html
    assert '<div class="stage-strip">' not in html and "GC tracker" not in html
    assert "The single unit" in html


def test_an_unpublished_one_day_hub_says_the_board_is_not_out_yet(frame_mod):
    race = _index_race(status="upcoming", n_settled=0, post_hoc=False)
    race["stages"][0].update(status="upcoming", url=None, predicted=False, post_hoc=False)

    html = frame_mod.render_race_hub({}, race)

    assert "Not published yet" in html and "Board <b>not published</b>" in html
    assert 'class="chip post_hoc"' not in html


def test_one_day_races_read_as_single_rows_in_the_lists(frame_mod):
    race = _index_race()
    entry = race["stages"][0]

    line = frame_mod.entry_line(race, entry)

    assert "One-day race" in line and "Stage" not in line
    assert frame_mod.unit_name(race, entry, short=True) == "Strade Bianche 2026"
    assert frame_mod.race_progress(race) == "result in, scored"
    assert frame_mod.race_progress({"type": "stage_race", "n_settled": 14, "n_stages": 21}) == \
        "14/21 stages settled"


def test_the_home_standfirst_exempts_a_published_reconstruction(frame_mod):
    idx = {"races": [_index_race()], "generated_at": "2026-09-08 08:00", "months": ["2026-03"]}

    html = frame_mod.render_home(idx, __import__("datetime").date(2026, 9, 8))

    assert "The exceptions are the pages marked post-hoc" in html


def test_the_calendar_names_a_one_day_race_without_a_stage_number(frame_mod):
    idx = {"races": [_index_race()], "generated_at": "2026-09-08 08:00", "months": ["2026-03"]}

    html = frame_mod.render_calendar_month(idx, "2026-03", __import__("datetime").date(2026, 9, 8))

    assert "Strade Bianche 2026</a>" in html and "· st " not in html


# ---------------------------------------------------------------------------
# the driver: a one-day campaign settles and previews on the same commands
# ---------------------------------------------------------------------------

def _drv_run(campaign, tmp_path, *argv, today, db_path=None):
    from cycling_project.nightly import driver as drv

    base = ["--campaign", str(campaign), "--store", "fake", "--store-root", str(tmp_path / "store"),
            "--today", today, "--dry-run"]
    if db_path:
        base += ["--db-path", str(db_path)]
    return drv.main([argv[0], *base, *argv[1:]])


def _steps(tmp_path):
    p = tmp_path / "store" / "ledger" / "run_steps.jsonl"
    rows = [json.loads(ln) for ln in p.read_text().splitlines()] if p.exists() else []
    return [(r["step"], r["state"]) for r in rows]


def test_a_one_day_preview_writes_its_own_config_from_the_race_s_history(
        tmp_path, refs_db, capsys, monkeypatch):
    camp = tmp_path / "strade-bianche-2026"
    camp.mkdir()
    (camp / "campaign.json").write_text(json.dumps({
        "slug": "strade-bianche-2026", "name": "Strade Bianche 2026", "fc_race_id": "54",
        "year": 2026, "category": "wt", "is_stage_race": False,
        "start_date": "2026-03-07", "end_date": "2026-03-07",
        "stages": [{"number": None, "date": "2026-03-07", "kind": "one_day"}],
        "site": {"route_slug": "strade-bianche"}}))
    # The field is a precondition since 2026-09-17: a one-day board is built on the start list the
    # Mac horizon capture hands over, and the driver refuses to let the runner scrape for one.
    (camp / "predictions" / "race").mkdir(parents=True)
    (camp / "predictions" / "race" / "startlist.json").write_text(json.dumps(
        {"fc_race_id": "54", "year": 2026, "teams": [
            {"name": "Team", "team_id": "1", "riders": [{"name": "Rider", "rider_id": "1"}]}]}))

    code = _drv_run(camp, tmp_path, "preview", "--unit", "race", today="2026-03-06", db_path=refs_db)
    out = json.loads(capsys.readouterr().out)

    assert code == 0, out
    assert out["startlist"]["source"] == "handover:startlist.json"
    cfg = oneday.load_config(camp / "predictions" / "race" / "scenarios.json")
    assert out["config"]["created"] is True
    assert cfg["scenarios"]["own_history"]["refs"] == [106, 105, 104, 103, 101]
    assert cfg["scenarios"]["own_history"]["tag"] == "strade-bianche-2026_race_own_history"
    # no day key is asked for, and no bundle is frozen: both are stage-race instruments
    assert out["key"] == {"source": "one_day", "day_key": None}
    assert ("bundle", "skipped") in _steps(tmp_path)


def test_a_one_day_settle_ingests_and_builds_the_one_day_page(uci_campaign, tmp_path, capsys):
    camp, db = uci_campaign
    pred = camp / "predictions" / "race"
    pred.mkdir(parents=True)
    (pred / "scenarios.json").write_text(json.dumps(oneday.build_config(
        fc_race_id="263", year=2026, date="2026-09-06", label="GP Industria & Artigianato",
        refs=[9703], tag_prefix="gpia_race")))

    code = _drv_run(camp, tmp_path, "settle", "--unit", "race", today="2026-09-07", db_path=db)
    out = json.loads(capsys.readouterr().out)

    assert code == 0, out
    assert out["ingest"]["provider"] == "uci" and out["ingest"]["winner"] == "PIDCOCK Thomas"
    assert "gc.csv" not in out["ingest"]["written"]
    steps = _steps(tmp_path)
    assert ("seed_state_cache", "skipped") in steps      # no within-race state to reconstruct
    assert ("gc_config", "skipped") in steps and ("retro_facts", "skipped") in steps
    assert ("oneday_page", "skipped") in steps           # dry run records scripts, never runs them
    assert not any(step == "stage_page" for step, _ in steps)


def test_the_driver_names_the_one_day_page_the_builder_writes(uci_campaign):
    from cycling_project.nightly.driver import Campaign

    c = Campaign.load(uci_campaign[0])

    assert c.unit_for(None) == "race"
    assert c.oneday_page_name() == "gp-industria-artigianato-2026.html"


def test_a_one_day_config_that_carries_a_day_key_fails_validation(uci_campaign, tmp_path, capsys):
    camp, db = uci_campaign
    pred = camp / "predictions" / "race"
    pred.mkdir(parents=True)
    cfg = oneday.build_config(fc_race_id="263", year=2026, date="2026-09-06",
                              label="GP Industria & Artigianato", refs=[9703],
                              tag_prefix="gpia_race")
    cfg["day_key"] = {"res_2": 1.0}
    (pred / "scenarios.json").write_text(json.dumps(cfg))

    code = _drv_run(camp, tmp_path, "validate", "--unit", "race", today="2026-09-06", db_path=db)
    out = json.loads(capsys.readouterr().out)

    assert code == 10
    assert any("day-menu channel" in p for p in out["operator_task"]["detail"]["problems"])


def test_the_service_re_ages_form_to_the_request_date_not_today():
    """Chip K finding (2026-09-08): asof_date reached the stack features and pricing but never the
    form re-aging, so any board rebuilt after race day saw the season after the race."""
    import inspect
    import re as _re
    from cycling_project.prediction_tools import prediction_service as ps
    src = inspect.getsource(ps.PredictionService)
    calls = list(_re.finditer(r"assemble_prediction_df\((.*?)\n\s*\)", src, _re.S))
    assert len(calls) == 2, "expected the board and the GC-outlook call"
    for m in calls:
        assert "asof_date=request.asof_date" in m.group(1), m.group(0)[:200]


# ---------------------------------------------------------------------------
# chip V (2026-09-18) — one race, one field: a sibling unit's start list serves
# ---------------------------------------------------------------------------

def _startlist_doc():
    return {"teams": [{"name": "T", "team_id": "1", "riders": [{"name": "R", "rider_id": "9", "number": "1"}]}]}


def test_find_startlist_prefers_the_units_own_file_then_the_newest_sibling(tmp_path):
    import os

    pred = tmp_path / "camp" / "predictions"
    for unit in ("stage_02", "stage_03", "stage_04"):
        (pred / unit).mkdir(parents=True)
    assert oneday.find_startlist(pred / "stage_02") is None
    for i, unit in enumerate(("stage_03", "stage_04")):
        p = pred / unit / "startlist.json"
        p.write_text(json.dumps(_startlist_doc()))
        os.utime(p, (1_000_000 + i, 1_000_000 + i))
    path, label = oneday.find_startlist(pred / "stage_02")
    assert path == pred / "stage_04" / "startlist.json" and label == "handover:stage_04/startlist.json"
    (pred / "stage_02" / "startlist.json").write_text(json.dumps(_startlist_doc()))
    assert oneday.find_startlist(pred / "stage_02")[1] == "handover:startlist.json"


def test_the_serving_runner_reads_a_sibling_units_start_list(tmp_path):
    """Tour of Huangshan stage 2 (2026-09-18): the list sat beside stage 3 and predict exited 1."""
    spec = importlib.util.spec_from_file_location(
        "predict_stage_scenarios_v", Path(__file__).resolve().parents[3] / "netlify_site/build/predict_stage_scenarios.py")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(Path(spec.origin).parent))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.pop(0)
    pred = tmp_path / "camp" / "predictions"
    (pred / "stage_02").mkdir(parents=True)
    (pred / "stage_03").mkdir()
    (pred / "stage_03" / "startlist.json").write_text(json.dumps(_startlist_doc()))
    teams, source = mod.resolve_startlist({"fc_race_id": "20780", "year": 2026}, pred / "stage_02" / "scenarios.json",
                                          str(tmp_path / "none.db"), allow_scrape=False)
    assert source == "handover:stage_03/startlist.json" and teams[0].riders[0].rider_id == "9"


def test_an_unconfigured_stage_shows_the_campaigns_own_route_and_date(index_mod):
    """2026-09-18: horizon had filled campaign.json's stage rows, but the hub read only
    scenarios.json, so a stage nobody had configured yet showed "TBC" and a blank route."""
    mod, site, perf = index_mod
    d = perf / "huangshan-2026"
    d.mkdir()
    (d / "campaign.json").write_text(json.dumps({"stages": [
        {"number": 1, "date": "2026-09-18", "towns": "A → B", "distance_km": 121.0},
        {"number": 2, "date": "2026-09-19", "towns": None, "distance_km": None}]}))
    camp = {"dir": "huangshan-2026", "slug": "huangshan", "year": 2026, "prefix": "huangshan-", "n_stages": 2,
            "start_date": "2026-09-18", "type": "stage_race"}
    st1, st2 = mod.build_stage_entries(camp, None)
    assert st1["date"] == "2026-09-18" and st1["label"] == "Stage 1 — A → B, 121 km"
    assert st2["date"] == "2026-09-19" and st2["label"] == "Stage 2"
