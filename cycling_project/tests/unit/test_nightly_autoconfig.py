"""Chip R (2026-09-16): a stage race needs no human-written scenario config.

Until this chip the cloud driver stopped at ``scenarios_needed`` for every stage race with
no ``predictions/TEMPLATE_scenarios.json`` — only the Vuelta ever had one, and Giro
d'Abruzzo, Tour de Luxembourg, Okolo Slovenska and Tour of Huangshan all died there in one
week.  The driver now writes the stage config from ``campaign.json``, derives each
scenario's references from the resolved day key (menu item → canonical signature →
``refs.ARCHETYPES``), adds the alternate branch for the key's second-weighted family, and
creates the GC config the settle step re-stamps.
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import sqlite3
from pathlib import Path

import pytest

from cycling_project.nightly import autoconfig, driver as drv

TODAY = "2026-09-15"
STAGE_DATE = "2026-09-16"
UNIT = "stage_02"

SIG_COLS = ["comp_id", "race_name", "year", "date", "stage_number", "category", "competition_type", "rule_type",
            "wg_size", "winner_margin", "chase_gap", "frac_120s", "winner_archetype", "dominant_archetype",
            "top15_sprint", "top15_mountain", "top15_hilly", "top15_rolling", "top15_breakaway", "top15_time_trial"]


def _row(comp_id, *, kind, year, category="wt", race_name="Some Race", stage_number=3, competition_type="stage"):
    base = dict.fromkeys(SIG_COLS, 0)
    base.update({"comp_id": comp_id, "race_name": race_name, "year": year, "date": f"{year}-05-01",
                 "stage_number": stage_number, "category": category, "competition_type": competition_type,
                 "chase_gap": 0, "winner_margin": 0})
    if kind == "mass_sprint":
        base.update({"rule_type": "mass_sprint", "wg_size": 60, "frac_120s": 1.0, "top15_sprint": 0.7,
                     "winner_archetype": "sprint", "dominant_archetype": "sprint"})
    elif kind == "gc_from_two":
        base.update({"rule_type": "tiny_group", "wg_size": 2, "frac_120s": 0.2, "top15_mountain": 0.6,
                     "winner_archetype": "mountain", "dominant_archetype": "mountain"})
    elif kind == "gc":                      # a general-classification competition, not a stage
        base.update({"rule_type": "itt_like", "wg_size": 1, "competition_type": "gc", "top15_mountain": 0.4,
                     "stage_number": 0, "winner_archetype": "mountain", "dominant_archetype": "mountain"})
    return base


@pytest.fixture
def signatures(tmp_path):
    rows = [_row(1000 + i, kind="mass_sprint", year=2025 - i) for i in range(6)]
    rows += [_row(2000 + i, kind="gc_from_two", year=2025 - i) for i in range(6)]
    rows += [_row(3000 + i, kind="gc", year=2025 - i) for i in range(4)]
    rows += [_row(4000 + i, kind="mass_sprint", year=2024 - i, category="d1") for i in range(3)]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=SIG_COLS)
    w.writeheader()
    w.writerows(rows)
    path = tmp_path / "selection_signatures_20260916_000000.csv.gz"
    with gzip.open(path, "wt") as fh:
        fh.write(buf.getvalue())
    return path


@pytest.fixture
def campaign(tmp_path):
    """A .1 stage race with nothing but campaign.json: no template, no configs, no odds."""
    d = tmp_path / "okolo-slovenska-2026"
    d.mkdir()
    (d / "campaign.json").write_text(json.dumps({
        "slug": "okolo-slovenska-2026", "name": "Okolo Slovenska", "fc_race_id": "700", "year": 2026,
        "category": "d1", "is_stage_race": True, "start_date": "2026-09-15", "end_date": "2026-09-19",
        "timezone": "UTC", "void_stages": [],
        "stages": [{"number": 1, "date": "2026-09-15", "towns": None, "distance_km": None},
                   {"number": 2, "date": STAGE_DATE, "towns": "Nitra → Trnava", "distance_km": 178.4},
                   {"number": 3, "date": "2026-09-17", "towns": None, "distance_km": None}],
    }, indent=1))
    (d / "rider_crosswalk.csv").write_text("fc_rider_id,internal_rider_id,name\n")
    # the field, as horizon hands it over — since chip V every preview unit is gated on it
    (d / "predictions" / "stage_01").mkdir(parents=True)
    (d / "predictions" / "stage_01" / "startlist.json").write_text(json.dumps(
        {"teams": [{"name": "T", "team_id": "1", "riders": [{"name": "R", "rider_id": "9"}]}]}))
    return d


def _preview(campaign, tmp_path, signatures, key, *extra, unit=UNIT):
    rec_path = tmp_path / "agent_key.json"
    rec_path.write_text(json.dumps({"key": key}))
    return drv.main(["preview", "--unit", unit, "--campaign", str(campaign), "--store", "fake",
                     "--store-root", str(tmp_path / "store"), "--crosswalk", str(campaign / "rider_crosswalk.csv"),
                     "--today", TODAY, "--db-path", str(tmp_path / "none.db"), "--signatures", str(signatures),
                     "--agent-key", str(rec_path), "--dry-run", *extra])


def _config(campaign, unit=UNIT):
    return json.loads((campaign / "predictions" / unit / "scenarios.json").read_text())


def _steps(tmp_path):
    p = tmp_path / "store" / "ledger" / "run_steps.jsonl"
    return [json.loads(ln) for ln in p.read_text().splitlines()] if p.exists() else []


# ---------------------------------------------------------------------------
# the item → archetype mapping
# ---------------------------------------------------------------------------

def test_every_menu_item_maps_to_a_known_archetype():
    from cycling_project.nightly import day_key_record as rec
    from cycling_project.nightly.refs import ARCHETYPES

    table = {r["item"]: r["archetype"] for r in autoconfig.describe_mapping()}
    assert set(table) == set(rec.MENU_ITEMS)
    assert set(table.values()) <= set(ARCHETYPES)
    # the frozen menu v1 signatures produce exactly this mapping
    assert table == {"bunch": "bunch_sprint", "itt": "itt_like", "gc_day": "gc_from_two",
                     "res_0": "solo", "res_1": "small_group", "res_2": "gc_from_two",
                     "res_3": "reduced_sprint", "res_4": "mountain_break", "res_6": "solo",
                     "res_7": "punchy_select"}


def test_the_alternate_branch_is_the_second_family_not_the_second_item():
    key = {"bunch": 0.55, "res_3": 0.30, "res_1": 0.15}          # res_3 is the runner-up item…
    assert autoconfig.dominant_item(key) == "bunch"
    assert autoconfig.second_family_item(key) == "res_3"          # …and it is also a different family
    key = {"bunch": 0.6, "itt": 0.4}                              # both macro: no alternate branch
    assert autoconfig.second_family_item(key) is None
    assert autoconfig.alternate_scenario(key, slug="x", stage=4) is None
    name, spec = autoconfig.alternate_scenario({"gc_day": 0.6, "res_4": 0.4}, slug="x", stage=4)
    assert name == "alt_res_4" and spec["day_key"] == {"res_4": 1.0} and spec["tag"] == "x_st04_alt_res_4"


# ---------------------------------------------------------------------------
# the config, end to end
# ---------------------------------------------------------------------------

def test_a_stage_race_with_no_template_gets_a_valid_machine_written_config(campaign, tmp_path, signatures, capsys):
    assert not (campaign / "predictions" / drv.TEMPLATE_NAME).exists()
    code = _preview(campaign, tmp_path, signatures, {"bunch": 0.6, "res_2": 0.4})
    out = json.loads(capsys.readouterr().out)
    assert code == drv.EXIT_DONE, out

    cfg = _config(campaign)
    assert cfg["stage"] == 2 and cfg["fc_race_id"] == "700" and cfg["year"] == 2026 and cfg["date"] == STAGE_DATE
    assert cfg["label"] == "Stage 2 — Nitra → Trnava, 178.4 km"
    assert cfg["config_source"] == autoconfig.CONFIG_SOURCE
    # the odds fields stay absent: this is a .1 race and Kambi lists no market
    assert cfg.get("event_id") is None and cfg.get("odds_capture") is None
    assert cfg["day_key"] == {"bunch": 0.6, "res_2": 0.4} and cfg["day_key_author"] == "agent"

    # main read + one alternate, for the key's second family
    assert sorted(cfg["scenarios"]) == ["alt_res_2", autoconfig.MAIN_SCENARIO]
    main = cfg["scenarios"][autoconfig.MAIN_SCENARIO]
    alt = cfg["scenarios"]["alt_res_2"]
    assert main["refs_archetype"] == "bunch_sprint" and alt["refs_archetype"] == "gc_from_two"
    assert alt["day_key"] == {"res_2": 1.0}
    assert len(main["refs"]) == 5 and len(alt["refs"]) == 5
    assert set(main["refs"]).isdisjoint(alt["refs"])              # a reference is never spent twice
    assert all(r >= 1000 for r in main["refs"]) and all(2000 <= r < 3000 for r in alt["refs"])
    # the derivation is recorded so the page and the retro can say the refs were machine-chosen
    for spec in (main, alt):
        assert spec["refs_source"] == autoconfig.REFS_SOURCE
        assert "not by a human" in spec["refs_note"]
    assert cfg["refs_source"] == autoconfig.REFS_SOURCE

    # the driver's own validator passes on what it generated
    assert out["validate"]["ok"] and out["refs"]["alternate"] == "alt_res_2"
    steps = [(s["step"], s["state"]) for s in _steps(tmp_path)]
    assert ("stage_config", "ok") in steps and ("scenario_refs", "ok") in steps and ("gc_config", "ok") in steps


def test_the_category_tier_and_the_races_own_editions_are_preferred(campaign, tmp_path, signatures):
    """A d1 campaign prefers d1 reference days over the WorldTour ones at the same archetype."""
    ids, meta = autoconfig.pick_refs("bunch_sprint", campaign_dir=campaign, signatures=signatures,
                                     category="d1", own_ids={1003}, count=3)
    assert ids[0] == 1003                                        # own edition first
    assert set(ids[1:]) <= {4000, 4001, 4002}                    # then the campaign's own tier
    assert meta["archetype"] == "bunch_sprint" and meta["n_same_category"] == 2


def test_references_already_in_the_config_are_never_re_chosen(campaign, tmp_path, signatures):
    cfg = autoconfig.build_stage_skeleton(slug="s", stage=2, fc_race_id="700", year=2026, date=STAGE_DATE,
                                          label="Stage 2")
    cfg["scenarios"]["hand_written"] = {"label": "Human", "short": "H", "tag": "s_st02_h", "refs": [1000, 1001]}
    report = autoconfig.fill_scenario_refs(cfg, key={"bunch": 1.0}, slug="s", campaign_dir=campaign,
                                           signatures=signatures, category="wt")
    assert report["scenarios"] == [autoconfig.MAIN_SCENARIO]      # the human scenario is left alone
    assert cfg["scenarios"]["hand_written"]["refs"] == [1000, 1001]
    assert set(cfg["scenarios"][autoconfig.MAIN_SCENARIO]["refs"]).isdisjoint({1000, 1001})


def test_no_signature_table_is_the_one_case_that_still_asks_a_human(campaign, tmp_path, capsys):
    missing = tmp_path / "selection_signatures_nowhere.csv.gz"
    code = _preview(campaign, tmp_path, missing, {"bunch": 1.0})
    out = json.loads(capsys.readouterr().out)
    assert code == drv.EXIT_WAITING
    assert out["operator_task"]["kind"] == "scenarios_needed"
    assert "selection_signatures" in out["operator_task"]["summary"]
    # the helper itself is explicit about why
    with pytest.raises(autoconfig.AutoConfigError):
        autoconfig.pick_refs("bunch_sprint", signatures=missing)


# ---------------------------------------------------------------------------
# the GC config
# ---------------------------------------------------------------------------

def _db_with_editions(path: Path, fc_race_id="700", years=(2023, 2024, 2025)) -> Path:
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE races (id INTEGER PRIMARY KEY, fc_race_id TEXT, year INTEGER, name TEXT);
        CREATE TABLE competitions (id INTEGER PRIMARY KEY, race_id INTEGER, competition_type TEXT, date TEXT, name TEXT);
        CREATE TABLE competition_field_features (competition_id INTEGER);
    """)
    for i, y in enumerate(years):
        con.execute("INSERT INTO races VALUES (?,?,?,?)", (i + 1, fc_race_id, y, "Okolo Slovenska"))
        con.execute("INSERT INTO competitions VALUES (?,?,?,?,?)", (500 + i, i + 1, "gc", f"{y}-09-19", "GC"))
        con.execute("INSERT INTO competition_field_features VALUES (?)", (500 + i,))
    # every day in the ``signatures`` fixture is servable (chip V filters on this table)
    con.executemany("INSERT INTO competition_field_features VALUES (?)",
                    [(b + i,) for b in (1000, 2000, 4000) for i in range(6)])
    con.commit()
    con.close()
    return path


def test_gc_config_is_created_from_the_races_own_earlier_editions(campaign, tmp_path, signatures, capsys):
    db = _db_with_editions(tmp_path / "own.db")
    rec_path = tmp_path / "agent_key.json"
    rec_path.write_text(json.dumps({"key": {"bunch": 1.0}}))
    code = drv.main(["preview", "--unit", UNIT, "--campaign", str(campaign), "--store", "fake",
                     "--store-root", str(tmp_path / "store"), "--crosswalk", str(campaign / "rider_crosswalk.csv"),
                     "--today", TODAY, "--db-path", str(db), "--signatures", str(signatures),
                     "--agent-key", str(rec_path), "--dry-run"])
    out = json.loads(capsys.readouterr().out)
    assert code == drv.EXIT_DONE, out
    gc = json.loads((campaign / "predictions" / "gc" / "scenarios.json").read_text())
    assert gc["target"] == "gc" and gc["scenarios"]["gc"]["refs"] == [502, 501, 500]
    assert gc["scenarios"]["gc"]["refs_source"] == "auto:own_editions"
    assert autoconfig.validate_gc_config(gc) == []
    assert out["gc_config"]["created"] and out["gc_config"]["refs_source"] == "own_editions"


def test_gc_config_falls_back_to_recent_gcs_from_the_database(campaign, tmp_path, signatures, capsys):
    # this race has ONE earlier edition (under the two-edition bar); other races' GCs fill in,
    # same category tier first, newest first, the own edition never among them
    db = _db_with_editions(tmp_path / "own.db", years=(2025,))
    con = sqlite3.connect(db)
    con.execute("ALTER TABLE races ADD COLUMN category TEXT")
    con.execute("UPDATE races SET category = 'pro'")
    others = [(3000, "wt", "2026-06-01"), (3001, "pro", "2026-05-01"), (3002, "pro", "2026-04-01"),
              (3003, "d1", "2026-07-01"), (3004, "pro", "2025-03-01"), (3005, "pro", "2026-08-30")]
    for i, (cid, cat, date) in enumerate(others, start=10):
        con.execute("INSERT INTO races VALUES (?,?,?,?,?)", (i, str(9000 + i), 2026, f"Race {i}", cat))
        con.execute("INSERT INTO competitions VALUES (?,?,?,?,?)", (cid, i, "gc", date, "GC"))
        con.execute("INSERT INTO competition_field_features VALUES (?)", (cid,))
    con.execute("INSERT INTO competitions VALUES (?,?,?,?,?)", (3999, 10, "gc", "2026-06-02", "GC no features"))
    con.commit(); con.close()
    rec_path = tmp_path / "agent_key.json"
    rec_path.write_text(json.dumps({"key": {"bunch": 1.0}}))
    cj = json.loads((campaign / "campaign.json").read_text()); cj["category"] = "pro"
    (campaign / "campaign.json").write_text(json.dumps(cj))
    code = drv.main(["preview", "--unit", UNIT, "--campaign", str(campaign), "--store", "fake",
                     "--store-root", str(tmp_path / "store"), "--crosswalk", str(campaign / "rider_crosswalk.csv"),
                     "--today", TODAY, "--db-path", str(db), "--signatures", str(signatures),
                     "--agent-key", str(rec_path), "--dry-run"])
    assert code == drv.EXIT_DONE, capsys.readouterr().out
    gc = json.loads((campaign / "predictions" / "gc" / "scenarios.json").read_text())
    assert gc["scenarios"]["gc"]["refs"] == [3005, 3001, 3002, 3004, 3003]
    assert gc["scenarios"]["gc"]["refs_source"] == autoconfig.GC_REFS_SOURCE
    assert autoconfig.validate_gc_config(gc) == []


def test_two_own_editions_are_enough_for_a_gc_board(tmp_path):
    db = _db_with_editions(tmp_path / "own.db", years=(2024, 2025))
    refs, source = autoconfig.gc_refs(fc_race_id="700", year=2026, campaign_dir=None, db_path=db, signatures=None)
    assert (refs, source) == ([501, 500], "own_editions")


def test_a_second_preview_leaves_the_written_config_alone(campaign, tmp_path, signatures, capsys):
    assert _preview(campaign, tmp_path, signatures, {"bunch": 0.6, "res_2": 0.4}) == drv.EXIT_DONE
    capsys.readouterr()
    before = _config(campaign)
    assert _preview(campaign, tmp_path, signatures, {"bunch": 0.6, "res_2": 0.4}, "--force") == drv.EXIT_DONE
    out = json.loads(capsys.readouterr().out)
    assert _config(campaign) == before
    assert next(s for s in _steps(tmp_path) if s["step"] == "scenario_refs" and s["state"] == "skipped")
    assert out["validate"]["ok"]


# ---------------------------------------------------------------------------
# chip V (2026-09-18) — a machine-chosen reference must be servable
# ---------------------------------------------------------------------------

def _itt_signatures(tmp_path):
    """Three time-separated days (one of them with no feature row) plus a pool of ordinary stages."""
    rows = []
    for cid, cat, year in ((9878, "pro", 2025), (9001, "wt", 2024), (9002, "pro", 2023)):
        r = _row(cid, kind="mass_sprint", year=year, category=cat)
        r.update({"rule_type": "itt_like", "wg_size": 1, "top15_sprint": 0, "top15_time_trial": 0.6})
        rows.append(r)
    rows += [_row(1000 + i, kind="mass_sprint", year=2025 - i) for i in range(4)]
    rows += [_row(4000 + i, kind="mass_sprint", year=2024 - i, category="pro") for i in range(3)]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=SIG_COLS)
    w.writeheader()
    w.writerows(rows)
    path = tmp_path / "selection_signatures_20260918_000000.csv.gz"
    with gzip.open(path, "wt") as fh:
        fh.write(buf.getvalue())
    return path


def _feature_db(path: Path, ids) -> Path:
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE competition_field_features (competition_id INTEGER)")
    con.executemany("INSERT INTO competition_field_features VALUES (?)", [(i,) for i in ids])
    con.commit(); con.close()
    return path


def test_a_reference_the_serving_db_cannot_profile_is_never_chosen(campaign, tmp_path):
    """Tour de Luxembourg stage 4 (2026-09-18): 9878 came from the signature table, had no
    competition_field_features row, and predict died.  An ITT still gets five, same tier first."""
    sig = _itt_signatures(tmp_path)
    db = _feature_db(tmp_path / "serving.db", [9001, 9002, 1000, 1001, 1002, 4000, 4001])
    ids, meta = autoconfig.pick_refs("itt_like", campaign_dir=campaign, signatures=sig, db_path=db, category="pro")
    assert 9878 not in ids and meta["unusable_dropped"] and 9878 in meta["unusable_dropped"]
    assert len(ids) == 5 and meta["short"] == 0
    assert ids[:2] == [9002, 9001]                     # the archetype's own days, campaign tier first
    assert ids[2:4] == [4000, 4001]                    # the top-up prefers the campaign tier too
    assert meta["topped_up"] == 3 and all(i in {9001, 9002, 1000, 1001, 1002, 4000, 4001} for i in ids)


def test_a_short_reference_set_is_recorded(campaign, tmp_path):
    sig = _itt_signatures(tmp_path)
    db = _feature_db(tmp_path / "serving.db", [9001, 1000])
    ids, meta = autoconfig.pick_refs("itt_like", campaign_dir=campaign, signatures=sig, db_path=db)
    assert sorted(ids) == [1000, 9001] and meta["short"] == 3
    assert "servable" in autoconfig.refs_note("itt", meta)


def test_without_a_database_nothing_is_filtered(campaign, tmp_path):
    ids, meta = autoconfig.pick_refs("itt_like", campaign_dir=campaign, signatures=_itt_signatures(tmp_path))
    assert 9878 in ids and meta["unusable_dropped"] == []


def test_the_driver_heals_a_machine_written_bad_ref_and_names_a_humans(campaign, tmp_path, capsys):
    sig = _itt_signatures(tmp_path)
    db = _feature_db(tmp_path / "serving.db", [9001, 9002, 1000, 1001, 1002, 1003, 4000, 4001, 4002])
    cfg = autoconfig.build_stage_skeleton(slug="okolo-slovenska-2026", stage=2, fc_race_id="700", year=2026,
                                          date=STAGE_DATE, label="Stage 2")
    cfg["scenarios"][autoconfig.MAIN_SCENARIO].update({"refs": [9878, 9001], "refs_source": autoconfig.REFS_SOURCE})
    pred = campaign / "predictions" / UNIT
    pred.mkdir(parents=True)
    (pred / "scenarios.json").write_text(json.dumps(cfg))
    healed, blocking = autoconfig.drop_unservable_auto_refs(cfg, db)
    assert healed == {autoconfig.MAIN_SCENARIO: [9878]} and not blocking
    assert cfg["scenarios"][autoconfig.MAIN_SCENARIO]["refs"] == []

    # a human's set is never edited: the preview waits and names the id
    cfg["scenarios"]["hand"] = {"label": "Human", "short": "H", "tag": "x_h", "refs": [9878, 1000]}
    (pred / "scenarios.json").write_text(json.dumps(cfg))
    rec_path = tmp_path / "agent_key.json"
    rec_path.write_text(json.dumps({"key": {"itt": 1.0}}))
    code = drv.main(["preview", "--unit", UNIT, "--campaign", str(campaign), "--store", "fake",
                     "--store-root", str(tmp_path / "store"), "--crosswalk", str(campaign / "rider_crosswalk.csv"),
                     "--today", TODAY, "--db-path", str(db), "--signatures", str(sig),
                     "--agent-key", str(rec_path), "--dry-run"])
    out = json.loads(capsys.readouterr().out)
    assert code == drv.EXIT_WAITING, out
    assert out["operator_task"]["kind"] == "scenarios_needed" and "9878" in out["operator_task"]["summary"]
    assert cfg["scenarios"]["hand"]["refs"] == [9878, 1000]
