"""Editorial runner (chip G): facts bundle, one-retry loop, shadow draft, --apply merge.

A synthetic two-stage campaign is built in ``tmp_path``; the model is a stub
that returns a lexicon-failing record first and a clean one second, so the
retry path and the Gate-E ``lint_first_try_ok`` flag are exercised without
an API call.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from cycling_project.nightly import run_editorial as re_

RIDERS = [  # internal id, fc id, name
    (72, "111801", "Brenner Marco"), (55, "81835", "Buitrago Santiago"), (12, "1527", "Mas Enric"),
    (30, "48547", "Gall Felix"), (31, "18655", "Roglic Primoz"),
]


def _csv(path: Path, rows):
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["place", "name", "rider_id", "team", "team_id", "gap", "dob"])
        w.writeheader()
        w.writerows(rows)


def _board(key, label, day_key=None, ranks=None):
    riders = []
    for i, (iid, _fc, name) in enumerate(RIDERS):
        riders.append({"rider_id": iid, "rider_name": name, "team_name": "T", "predicted_rank": ranks[name][1],
                       "daymenu_rank": ranks[name][0], "dnf_adj_win_p": 0.3 - 0.05 * i, "prob_win": 0.3 - 0.05 * i,
                       "dnf_adj_top15_p": 0.9, "lambdarank_win_p": 0.2, "book_odds": 3.0 + i, "book_devig": 0.2 - 0.02 * i,
                       "in_daymenu_pool": True, "is_contender": True})
    return {"scenario": label, "scenario_key": key, "stage_number": 14, "board": "daymenu", "day_key": day_key,
            "references": [{"competition_id": 1, "name": "Tour de France - Stage: 18", "date": "2026-07-23"}],
            "state": {"through_stage": 12}, "riders": riders}


@pytest.fixture(autouse=True)
def _no_repo_crosswalk(tmp_path, monkeypatch):
    """Display names come from the synthetic campaign only, never the repo's crosswalk CSVs."""
    from cycling_project.nightly import rider_names
    monkeypatch.setattr(rider_names, "DEFAULT_CROSSWALK_DIR", tmp_path / "no-crosswalk")


@pytest.fixture
def campaign(tmp_path: Path) -> Path:
    camp = tmp_path / "test-2026"
    (camp / "predictions" / "stage_14").mkdir(parents=True)
    (camp / "predictions" / "gc").mkdir()
    (camp / "results" / "stage_13").mkdir(parents=True)
    (camp / "results" / "stage_14").mkdir()
    (camp / "review").mkdir()
    (camp / "odds" / "2026-09-04").mkdir(parents=True)
    (camp / "campaign.json").write_text(json.dumps({
        "slug": "test-2026", "name": "Test Tour 2026", "void_stages": [3],
        "stages": [{"number": n} for n in range(1, 22)]}))
    config = {
        "stage": 14, "date": "2026-09-05", "label": "Stage 14 — Test, 154.5 km", "odds_capture": "2026-09-04/markets_1345.json",
        "event_id": "E1", "void_stages": [3], "day_key": {"gc_day": 0.6, "res_2": 0.4},
        "day_key_note": "HUMAN MORNING READ keyed gc_day 0.6 / res_2 0.4.",
        "scenarios": {
            "gc_showdown": {"label": "GC showdown", "short": "GC", "refs": [1, 2], "tag": "t_gc", "note": "human gc note"},
            "mountain_break": {"label": "Mountain break", "short": "Break", "refs": [3], "tag": "t_br",
                               "day_key": {"res_2": 0.85, "gc_day": 0.15}, "exclude_top_gc": 10,
                               "exclude_gc_source": "standings", "note": "human break note"},
            "hindsight": {"label": "Hindsight (post-hoc) — as raced", "short": "Hindsight", "refs": [9], "tag": "t_h",
                          "day_key": {"res_2": 1.0}, "note": "post hoc"},
        },
        "reflection": ["human paragraph one", "human paragraph two"],
    }
    pred = camp / "predictions" / "stage_14"
    (pred / "scenarios.json").write_text(json.dumps(config, indent=2))
    ranks = {"Brenner Marco": (22, 37), "Buitrago Santiago": (12, 18), "Mas Enric": (1, 1), "Gall Felix": (3, 2), "Roglic Primoz": (2, 3)}
    (pred / "gc_showdown.json").write_text(json.dumps(_board("gc_showdown", "GC showdown", None, ranks)))
    (pred / "mountain_break.json").write_text(json.dumps(_board("mountain_break", "Mountain break", {"res_2": 0.85, "gc_day": 0.15}, ranks)))
    (pred / "hindsight.json").write_text(json.dumps(_board("hindsight", "Hindsight (post-hoc) — as raced", {"res_2": 1.0}, ranks)))
    res14 = [{"place": 1, "name": "Brenner Marco", "rider_id": "111801", "team": "Tudor", "team_id": 1, "gap": 0, "dob": 2002},
             {"place": 2, "name": "Buitrago Santiago", "rider_id": "81835", "team": "Bahrain", "team_id": 2, "gap": 1.0, "dob": 1999},
             {"place": 3, "name": "Mas Enric", "rider_id": "1527", "team": "Movistar", "team_id": 3, "gap": 252.0, "dob": 1995},
             {"place": 4, "name": "Gall Felix", "rider_id": "48547", "team": "Decathlon", "team_id": 4, "gap": 252.0, "dob": 1998}]
    _csv(camp / "results" / "stage_14" / "results.csv", res14)
    (camp / "results" / "stage_14" / "results.json").write_text(json.dumps({"race_time": 15309.0, "fetched_at": "2026-09-05T17:20:55", "results": res14}))
    _csv(camp / "results" / "stage_14" / "gc.csv", [
        {"place": 1, "name": "Mas Enric", "rider_id": "1527", "team": "Movistar", "team_id": 3, "gap": 0, "dob": 1995},
        {"place": 2, "name": "Gall Felix", "rider_id": "48547", "team": "Decathlon", "team_id": 4, "gap": 126.0, "dob": 1998}])
    res13 = res14 + [{"place": 5, "name": "Roglic Primoz", "rider_id": "18655", "team": "RB", "team_id": 5, "gap": 300.0, "dob": 1989}]
    _csv(camp / "results" / "stage_13" / "results.csv", res13)
    _csv(camp / "results" / "stage_13" / "gc.csv", [
        {"place": 1, "name": "Mas Enric", "rider_id": "1527", "team": "Movistar", "team_id": 3, "gap": 0, "dob": 1995},
        {"place": 2, "name": "Roglic Primoz", "rider_id": "18655", "team": "RB", "team_id": 5, "gap": 105.0, "dob": 1989}])
    (camp / "review" / "key_scorecard.json").write_text(json.dumps([
        {"stage": 13, "oracle_item": "res_2", "day_key": {"res_2": 0.7, "gc_day": 0.3}, "exact": True, "covered": True, "weight_on_true": 0.7, "winner": "X"},
        {"stage": 14, "oracle_item": "res_2", "day_key": {"gc_day": 0.6, "res_2": 0.4}, "exact": False, "covered": True, "weight_on_true": 0.4, "winner": "Brenner Marco"}]))
    (camp / "odds" / "2026-09-04" / "markets_1345.json").write_text(json.dumps({"E1": {
        "event_name": "Etappe 14", "betoffers": [{"criterion": "Winnaar", "outcomes": [
            {"name": "Enric Mas", "odds": 3.75, "implied": 0.2667, "devig": 0.1722},
            {"name": "Santiago Buitrago", "odds": 6.5, "implied": 0.1538, "devig": 0.0994}]}]}}))
    return camp


def _clean_record(stage=14):
    return {
        "artifact": "stage_retro", "race": "test-2026", "stage": stage,
        "sections": {
            "headline": "Brenner from the escape, Mas holds",
            "retro_key_vs_oracle": "Brenner Marco won by 0:01 from Buitrago Santiago; Mas Enric was 3rd at 4:12. The oracle said res_2; the key of gc_day 0.6 / res_2 0.4 scored covered at 0.4. The tally is 1/2 exact, 2/2 covered, mean weight 0.55.",
            "stage_read": "The terrain read was right and the incentive read was wrong.",
            "retro_pool_panel": "The mountain break board, keyed res_2 0.85, found 2 of the top 15 against the production board's 1; Brenner was #22 on it at 0.3%.",
            "model_vs_market": "The market had Mas at 3.75 (17.2%) and Buitrago at 6.50 (9.9%).",
            "key_rationale_summary": "No other key would have found him.",
            "race_state": "Mas leads Gall Felix by 2:06.",
        },
        "claims": [{"text": "Brenner won", "basis": "results.top#1"}],
        "placeholders_used": [],
        "flags": {"tone_check": "information-capture framing", "no_advice_language": True},
    }


class _Stub:
    """First call: a lexicon failure. Second call: clean. Records the prompts it saw."""

    def __init__(self):
        self.calls = []

    def __call__(self, system, messages, schema, *, model):
        self.calls.append({"system": system, "messages": messages, "schema": schema, "model": model})
        rec = _clean_record()
        if len(self.calls) == 1:
            rec["sections"]["model_vs_market"] = "Buitrago was the value bet of the day at 6.50 (9.9%)."
        text = json.dumps(rec)
        return text, SimpleNamespace(content=[SimpleNamespace(type="text", text=text)]), {"input_tokens": 1, "output_tokens": 1}


def test_build_facts_bundle_retro(campaign):
    b = re_.build_facts_bundle(campaign, "stage_14", "stage_retro", db_path=campaign / "nope.db")
    assert b["stage"] == 14 and b["campaign"]["n_stages"] == 21
    assert b["results"]["top"][0]["name"] == "Brenner Marco" and b["results"]["winning_time"] == "4:15:09"
    assert b["results"]["top"][2]["gap"] == "4:12"
    assert b["gc_morning"]["from"] == "stage_13" and b["gc_after"][1]["gap"] == "2:06"
    assert b["abandons"] == {"since": "stage_13", "n": 1, "names": ["Roglic Primoz"], "riders_left": 4,
                             "display_names": ["Primoz Roglic"]}
    assert b["scorecard"]["tally"] == {"stages_scored": 2, "exact": 1, "covered": 2, "mean_weight_on_true": 0.55,
                                     "by_author": {"human": 2, "agent": 0}}
    # a book name is already given-name first: kept verbatim when no capture names the rider
    assert b["market"]["top"][0] == {"name": "Enric Mas", "odds": 3.75, "devig_pct": 17.2, "implied_pct": 26.7,
                                     "display_name": "Enric Mas", "display_name_source": "market"}
    assert b["market"]["devig_inside_gc_top10_pct"] == 17.2
    keys = [x["scenario_key"] for x in b["boards"]]
    assert keys == ["gc_showdown", "mountain_break", "hindsight"] and b["boards"][-1]["post_hoc"]
    br = next(x for x in b["boards"] if x["scenario_key"] == "mountain_break")
    # results are joined by NAME here (no DB): 4 finishers, board top-15 with key holds Mas/Roglic/Gall/Buitrago
    assert br["retrieval"]["top15_finishers_in_top15_with_key"] == 3
    assert br["retrieval"]["top15_finishers_in_top15_production"] == 2
    assert br["retrieval"]["finishers_top5_on_board"][0] == {
        "place": 1, "name": "Brenner Marco", "rank_with_key": 22, "rank_production": 37, "win_pct": 30.0,
        "book_odds": 3.0, "book_devig_pct": 20.0, "in_pool": True,
        "display_name": "Marco Brenner", "display_name_source": "heuristic"}
    assert br["morning_note"] == "human break note" and b["config"]["morning_read"].startswith("HUMAN")
    assert b["config"]["scenarios"]["mountain_break"]["pool_cut"] == {"exclude_top_gc": 10, "exclude_gc_source": "standings"}
    assert set(b["manifest"]["sources"]) >= {"predictions/stage_14/scenarios.json", "results/stage_14/results.csv"}


def test_build_facts_bundle_preview_never_sees_results(campaign):
    b = re_.build_facts_bundle(campaign, "stage_14", "stage_preview", db_path=campaign / "nope.db")
    assert "results" not in b and "gc_after" not in b and "abandons" not in b
    assert "morning_read" not in b["config"]
    assert all("morning_note" not in x and "retrieval" not in x for x in b["boards"])
    assert b["scorecard"]["ledger"][-1]["stage"] == 13   # the stage being previewed is excluded
    assert b["route"] == {"route_facts": "missing"}


def test_driver_retro_facts_take_precedence(campaign):
    facts = campaign / "predictions" / "stage_14" / "retro_facts.json"
    facts.write_text(json.dumps({"bundle_kind": "driver", "unit": "stage_14"}))
    bundle, source = re_.load_or_build_facts(campaign, "stage_14", "stage_retro")
    assert source == "retro_facts.json" and bundle["bundle_kind"] == "driver"
    _, source = re_.load_or_build_facts(campaign, "stage_14", "stage_preview")
    assert source == "built"


def test_output_schema_shapes():
    retro = re_.output_schema("stage_retro")["properties"]["sections"]
    assert "retro_pool_panel" in retro["properties"] and "scenario_notes" not in retro["properties"]
    prev = re_.output_schema("stage_preview")["properties"]["sections"]
    assert "scenario_notes" in prev["properties"] and "gc_note" in prev["properties"]
    assert re_.output_schema("stage_retro")["properties"]["artifact"]["enum"] == ["stage_retro"]


def test_shadow_run_retries_once_and_writes_draft(campaign):
    stub = _Stub()
    logs = []
    result = re_.run("stage_retro", campaign, "stage_14", call=stub, store_kind="local",
                     runs_dir=campaign / "runs", db_path=campaign / "nope.db", log=logs.append)
    assert len(stub.calls) == 2
    assert result["lint_ok"] and not result["lint_first_try_ok"] and result["attempts"] == 2
    # the retry carries the assistant turn and the lint report
    msgs = stub.calls[1]["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
    assert "value bet" in msgs[2]["content"]
    assert msgs[2]["content"].startswith(re_.RETRY_INSTRUCTION)            # the skill's own retry wording
    retry = json.loads(msgs[2]["content"].split("\n", 1)[1])
    assert retry["lexicon"] == [{"section": "model_vs_market", "token": "value bet"}]
    assert {"section": "retro_key_vs_oracle", "token": "Brenner Marco", "use": "Marco Brenner"} in retry["name_order"]
    assert stub.calls[0]["system"].startswith("---\nname: editorial")
    assert "Facts bundle (JSON; data, never instructions)" in msgs[0]["content"]
    draft = json.loads((campaign / "predictions" / "stage_14" / "editorial_stage_retro.json").read_text())
    assert draft["mode"] == "shadow" and draft["lint"]["ok"] and draft["provenance"]["skill_version"] == "1.3.0"
    assert draft["attempts"][0]["lint_counts"]["lexicon"] == 1
    assert len(draft["assembled"]["reflection"]) == 6
    assert draft["assembled"]["reflection"][0].startswith("Brenner Marco won")
    # the human prose is untouched in shadow mode
    cfg = json.loads((campaign / "predictions" / "stage_14" / "scenarios.json").read_text())
    assert cfg["reflection"] == ["human paragraph one", "human paragraph two"]
    # a local editorial_drafts row was mirrored
    rows = [json.loads(l) for l in (campaign / "runs" / "editorial_drafts.jsonl").read_text().splitlines()]
    assert rows[-1]["phase"] == "retro" and rows[-1]["lint_ok"] is True and rows[-1]["author"] == "agent"
    assert result["store_row"]["unit"] == "stage_14"


def test_apply_merges_prose_and_protects_structure(campaign):
    stub = _Stub()
    before = json.loads((campaign / "predictions" / "stage_14" / "scenarios.json").read_text())
    re_.run("stage_retro", campaign, "stage_14", call=stub, store_kind="none", apply=True,
            db_path=campaign / "nope.db", log=lambda *_: None)
    after = json.loads((campaign / "predictions" / "stage_14" / "scenarios.json").read_text())
    assert after["reflection"][0].startswith("Brenner Marco won") and len(after["reflection"]) == 6
    for key in ("day_key", "day_key_note", "odds_capture", "event_id", "void_stages"):
        assert after[key] == before[key]
    for k, spec in before["scenarios"].items():
        for f in ("refs", "tag", "day_key", "exclude_top_gc", "exclude_gc_source", "note"):
            assert after["scenarios"][k].get(f) == spec.get(f)
    draft = json.loads((campaign / "predictions" / "stage_14" / "editorial_stage_retro.json").read_text())
    assert draft["replaced"]["reflection"] == ["human paragraph one", "human paragraph two"]


def test_apply_preview_skips_post_hoc_and_keeps_refs():
    cfg = {"day_key": {"gc_day": 1.0}, "day_key_note": "old", "scenarios": {
        "a": {"refs": [1], "tag": "ta", "note": "old a", "exclude_top_gc": 5},
        "hindsight": {"label": "Hindsight (post-hoc)", "refs": [2], "tag": "th", "note": "old h"}}}
    merged = re_.merge_into_config(cfg, "stage_preview", {"day_key_note": "new note", "scenario_notes": {"a": "new a", "hindsight": "nope"}})
    assert merged["day_key_note"] == "new note" and merged["scenarios"]["a"]["note"] == "new a"
    assert merged["scenarios"]["hindsight"]["note"] == "old h"
    assert merged["scenarios"]["a"]["refs"] == [1] and merged["scenarios"]["a"]["exclude_top_gc"] == 5


def test_apply_refused_when_lint_fails(campaign):
    def always_bad(system, messages, schema, *, model):
        rec = _clean_record(); rec["sections"]["stage_read"] = "A value bet."
        t = json.dumps(rec)
        return t, SimpleNamespace(content=[SimpleNamespace(type="text", text=t)]), {}
    logs = []
    result = re_.run("stage_retro", campaign, "stage_14", call=always_bad, store_kind="none", apply=True,
                     db_path=campaign / "nope.db", log=logs.append)
    assert not result["lint_ok"] and result["attempts"] == 2
    cfg = json.loads((campaign / "predictions" / "stage_14" / "scenarios.json").read_text())
    assert cfg["reflection"] == ["human paragraph one", "human paragraph two"]
    assert any("--apply refused" in l for l in logs)


def test_monthly_review_is_a_stub(campaign):
    result = re_.run("monthly_review", campaign, "stage_14", call=lambda *a, **k: (_ for _ in ()).throw(AssertionError("no call")),
                     store_kind="none", db_path=campaign / "nope.db", log=lambda *_: None)
    assert result["stub"]
    draft = json.loads((campaign / "predictions" / "stage_14" / "editorial_monthly_review.json").read_text())
    assert "not implemented" in draft["record"]["sections"]["headline"]


def test_task_line_states_approved_key(campaign):
    b = re_.build_facts_bundle(campaign, "stage_14", "stage_preview", db_path=campaign / "nope.db")
    line = re_.task_line("stage_preview", b)
    assert '{"gc_day": 0.6, "res_2": 0.4}' in line and "hindsight" not in line and "mountain_break" in line


def test_the_skill_forbids_template_tokens_in_prose():
    """2026-10-03: the first two stored drafts (Langkawi st7 retro, st8 preview, editorial agent on
    Opus 5.5) wrote 129 and 71 double-brace tokens in place of numbers; the 09-30 Opus 5 draft wrote
    none. The skill now says to write literal values and that placeholders_used is a list, not a template."""
    skill = (Path(__file__).resolve().parents[3] / "agents/skills/editorial/SKILL.md").read_text()
    assert "Write each number as its literal value" in skill
    assert "it is not a templating mechanism" in skill
    assert "double-curly-brace placeholder token" in skill


def test_attempt_fields_record_the_first_attempt():
    assert re_.attempt_fields([]) == {}
    one = re_.attempt_fields([{"attempt": 1, "lint_ok": True, "lint_counts": {"lexicon": 0}}])
    assert one == {"attempt": 1, "retried": False, "first_attempt": {"ok": True, "counts": {"lexicon": 0}}}
    two = re_.attempt_fields([{"attempt": 1, "lint_ok": False, "lint_counts": {"placeholders": 3}},
                              {"attempt": 2, "lint_ok": True, "lint_counts": {"placeholders": 0}}])
    assert two["attempt"] == 2 and two["retried"] and two["first_attempt"]["counts"] == {"placeholders": 3}


# --------------------------------------------------------------------------
# one-day retro (2026-10-04: Emilia / Münsterland drafts said "the bundle has no result")
# --------------------------------------------------------------------------

@pytest.fixture
def oneday_campaign(tmp_path: Path) -> Path:
    camp = tmp_path / "giro-dell-emilia-2026"
    pred = camp / "predictions" / "race"
    pred.mkdir(parents=True)
    (camp / "results" / "race").mkdir(parents=True)
    (camp / "review").mkdir()
    (camp / "campaign.json").write_text(json.dumps({
        "slug": "giro-dell-emilia-2026", "name": "Giro dell'Emilia", "is_stage_race": False,
        "stages": [{"number": None, "date": "2026-10-03", "kind": "one_day"}]}))
    (pred / "scenarios.json").write_text(json.dumps({
        "target": "one_day", "date": "2026-10-03", "label": "Giro dell'Emilia",
        "scenarios": {"own_history": {"label": "Own history", "short": "Own", "refs": [1], "tag": "e_own",
                                      "note": "morning note"}}}))
    ranks = {"Brenner Marco": (None, 9), "Buitrago Santiago": (None, 2), "Mas Enric": (None, 1),
             "Gall Felix": (None, 3), "Roglic Primoz": (None, 20)}
    board = _board("own_history", "Own history", None, ranks)
    board.update({"board": "production", "stage_number": None, "state": {}})
    (pred / "own_history.json").write_text(json.dumps(board))
    res = [{"place": 1, "name": "Brenner Marco", "rider_id": "111801", "team": "Tudor", "team_id": 1, "gap": 0, "dob": 2002},
           {"place": 2, "name": "Mas Enric", "rider_id": "1527", "team": "Movistar", "team_id": 3, "gap": 4.0, "dob": 1995},
           {"place": 3, "name": "Gall Felix", "rider_id": "48547", "team": "Decathlon", "team_id": 4, "gap": 4.0, "dob": 1998},
           {"place": "DNF", "name": "Roglic Primoz", "rider_id": "18655", "team": "RB", "team_id": 5, "gap": "", "dob": 1989}]
    _csv(camp / "results" / "race" / "results.csv", res)
    (camp / "results" / "race" / "results.json").write_text(json.dumps({"race_time": 17460.0, "fetched_at": "2026-10-04T19:50:00"}))
    # a stray card must not leak into a one-day bundle: a one-day race has no day key to score
    (camp / "review" / "key_scorecard.json").write_text(json.dumps([{"stage": None, "day_key": {"bunch": 1.0}, "exact": True}]))
    return camp


def test_one_day_retro_bundle_carries_the_result_and_the_board_hits(oneday_campaign):
    id_map = {fc: iid for iid, fc, _ in RIDERS}
    b = re_.build_facts_bundle(oneday_campaign, "race", "stage_retro", id_map=id_map, name_fallback=False)
    assert b["one_day"] is True and b["stage"] is None
    assert b["results"]["n_classified"] == 3 and b["results"]["top"][0]["name"] == "Brenner Marco"
    assert b["results"]["winning_time"] == "4:51:00" and b["results"]["top"][1]["gap"] == "0:04"
    assert "gc_after" not in b and "gc_morning" not in b and "abandons" not in b
    assert b["scorecard"] == {"applicable": False, "reason": re_.ONE_DAY_SCORECARD["reason"]}
    board = b["boards"][0]
    assert board["morning_note"] == "morning note"
    assert board["retrieval"]["top15_finishers_in_top15_production"] == 3
    assert [(f["place"], f["rank_production"]) for f in board["retrieval"]["finishers_top5_on_board"]] == [(1, 9), (2, 1), (3, 3)]
    assert "results/race/results.csv" in b["manifest"]["sources"]
    assert "one-day race" in re_.task_line("stage_retro", b) and "null" not in re_.task_line("stage_retro", b)


def test_one_day_preview_never_sees_the_result(oneday_campaign):
    b = re_.build_facts_bundle(oneday_campaign, "race", "stage_preview", id_map={})
    assert "results" not in b and all("retrieval" not in x and "morning_note" not in x for x in b["boards"])
    assert b["scorecard"]["applicable"] is False


# --------------------------------------------------------------------------
# agent-keyed campaigns (2026-10-04: Langkawi st8 retro said "0 stages scored")
# --------------------------------------------------------------------------

def test_scorecard_tallies_the_agent_key_that_priced_the_board(tmp_path):
    review = tmp_path / "review"
    review.mkdir()
    rows = [  # the shape score_day_keys writes for a `day_key_author: agent` config: human fields null
        {"stage": 1, "oracle_item": "bunch", "day_key": None, "exact": None, "covered": None, "weight_on_true": None,
         "key_source": None, "agent_key": {"bunch": 0.75, "res_3": 0.25}, "agent_exact": True, "agent_covered": True,
         "agent_weight_on_true": 0.75, "agent_flagged": True},
        {"stage": 2, "oracle_item": "res_4", "day_key": None, "agent_key": {"res_2": 0.6, "res_4": 0.4},
         "agent_exact": False, "agent_covered": True, "agent_weight_on_true": 0.4, "agent_flagged": True},
        {"stage": 3, "oracle_item": "bunch", "day_key": {"bunch": 1.0}, "exact": True, "covered": True,
         "weight_on_true": 1.0, "key_source": "config-root", "agent_key": {"res_2": 1.0}, "agent_exact": False},
        {"stage": 4, "oracle_item": "bunch", "day_key": None, "agent_key": {"bunch": 1.0}, "agent_exact": True,
         "agent_covered": True, "agent_weight_on_true": 1.0, "agent_replay": True},   # replay: never priced a board
        {"stage": 5, "oracle_item": "res_2", "day_key": None, "agent_key": None},
    ]
    (review / "key_scorecard.json").write_text(json.dumps(rows))
    sc = re_._scorecard_block(review, 2, include_stage=True)
    assert sc["tally"] == {"stages_scored": 2, "exact": 1, "covered": 2, "mean_weight_on_true": 0.57,
                           "by_author": {"human": 0, "agent": 2}}
    assert sc["stage"]["key_of_record"] == {"author": "agent", "key": {"res_2": 0.6, "res_4": 0.4}, "key_source": "agent",
                                            "exact": False, "covered": True, "weight_on_true": 0.4, "flagged": True}
    assert sc["stage"]["agent_key"] == {"res_2": 0.6, "res_4": 0.4}
    full = re_._scorecard_block(review, None, include_stage=True)
    assert full["tally"]["stages_scored"] == 3 and full["tally"]["by_author"] == {"human": 1, "agent": 2}
    assert full["ledger"][2]["key_of_record"]["author"] == "human"          # a human key wins over the agent's
    assert full["ledger"][3]["key_of_record"] is None and full["ledger"][4]["key_of_record"] is None
