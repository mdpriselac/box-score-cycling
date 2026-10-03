"""Bundle builder + driver for the day-key agent, on a trimmed stage-14 campaign.

The fixture is Vuelta 2026 stage 14 (2026-09-05, Jaén -> Sierra de la
Pandera) cut down from the real archive: the 2026-09-04 13:45 Kambi snapshot
(the one the morning read used), a synthetic earlier snapshot for movement,
a synthetic snapshot captured AFTER the stage start that must be ignored,
results for stages 12-14, scenario configs for 12 (keyed), 13 (post_hoc) and
14 (keyed, with sentinel text that must never reach the bundle), and the
scorecard rows for those stages.
"""

import json
import shutil
from pathlib import Path

import pytest

from cycling_project.nightly import day_key_record as rec
from cycling_project.nightly import run_day_key as rdk

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "nightly" / "day_key_stage14"


@pytest.fixture
def campaign(tmp_path):
    dst = tmp_path / "vuelta-2026"
    shutil.copytree(FIXTURE, dst)
    return dst


def _bundle_text(bundle_dir: Path) -> str:
    return "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in bundle_dir.rglob("*") if p.is_file())


def test_bundle_selects_newest_snapshot_before_start_and_freezes(campaign):
    m = rdk.build_bundle(campaign, 14)
    paths = {e["path"] for e in m["entries"]}
    assert m["odds"] == "present" and "odds/win_odds_1345.csv" in paths and "odds/markets_1345.json" in paths
    # the 09-05 12:00Z snapshot is after the 11:33Z start -> never chosen
    assert not any("0500" in p for p in paths)
    # movement against the synthetic prior snapshot
    assert "odds/movement.json" in paths
    mv = json.loads((campaign / "predictions/stage_14/bundle/odds/movement.json").read_text())
    mas = next(x for x in mv["moves"] if x["rider"] == "Enric Mas")
    assert mas["odds_prior"] == 4.5 and mas["odds_now"] == 3.75 and mas["devig_delta"] > 0
    assert m["gc_state_through_stage"] == 13 and m["route_facts"] == "missing"
    assert any("route_facts: missing" in n for n in m["notes"])
    assert m["manifest_sha256"] == rec.sha256_of(rec.canonical_json(m["entries"]).encode())
    manifest_path = campaign / "predictions/stage_14/bundle/manifest.json"
    assert manifest_path.exists()
    # frozen: changing the inputs does not change an existing bundle
    (campaign / "results/stage_13/gc.csv").write_text("place,name,rider_id,team,team_id,gap,dob\n1,Nobody,0,-,0,0,2000\n")
    m2 = rdk.build_bundle(campaign, 14)
    assert m2["manifest_sha256"] == m["manifest_sha256"]
    m3 = rdk.build_bundle(campaign, 14, force=True)
    assert m3["manifest_sha256"] != m["manifest_sha256"]


def test_bundle_never_sees_the_keyed_stage(campaign):
    m = rdk.build_bundle(campaign, 14)
    bundle_dir = campaign / "predictions/stage_14/bundle"
    text = _bundle_text(bundle_dir)
    assert "FIXTURE-SENTINEL" not in text                  # human note + hindsight scenario key
    assert not any("results/stage_14" in str(e.get("source")) for e in m["entries"])  # no source is the keyed stage's results
    ledger = json.loads((bundle_dir / "settled_stages.json").read_text())
    assert [e["stage"] for e in ledger] == [12, 13]
    card = json.loads((bundle_dir / "scorecard.json").read_text())
    assert [r["stage"] for r in card] == [12, 13]
    ctx = json.loads((bundle_dir / "stage_context.json").read_text())
    assert ctx["label"].startswith("Stage 14") and "day_key" not in ctx
    # the stage-14 winner (Brenner, 'Brenner Marco' in FirstCycling results format) only
    # appears via pre-stage sources: GC file and the book, never a results row
    results_row = "1,Brenner Marco"
    assert results_row not in text
    assert (bundle_dir / "gc.csv").read_text() == (campaign / "results/stage_13/gc.csv").read_text()


def test_ledger_entries_carry_measured_outcomes_and_reads(campaign):
    ledger = rdk.settled_ledger(campaign, 14)
    st12 = next(e for e in ledger if e["stage"] == 12)
    assert st12["key_as_logged"] == {"res_2": 0.55, "gc_day": 0.45} and st12["key_source"] == "config-root"
    assert st12["oracle_item"] == "gc_day" and st12["winner"] == "Omrzel Jakob"
    assert st12["winner_group_size"] == 1 and st12["morning_read"].startswith("OFFICIAL MORNING READ")
    assert st12["front_group"][0]["place"] == 1 and len(st12["front_group"]) <= rdk.FRONT_GROUP_N
    st13 = next(e for e in ledger if e["stage"] == 13)
    assert st13["key_as_logged"] is None and st13["key_source"].startswith("post_hoc")
    assert st13["morning_read"] is None and st13["oracle_item"] == "res_2"


def test_ledger_names_an_agent_key_and_carries_its_own_read(campaign):
    """A board priced from the reader's record (raw `key_items` shape, as the coordinator saves it)
    reaches the next morning's ledger as the agent's key, with its primary_mechanism as the read."""
    pred = campaign / "predictions" / "stage_12"
    cfg = json.loads((pred / "scenarios.json").read_text())
    cfg.update(day_key={"res_2": 0.6, "gc_day": 0.4}, day_key_author="agent",
               day_key_source="agent:agent_key.json")
    cfg.pop("day_key_note", None)
    (pred / "scenarios.json").write_text(json.dumps(cfg))
    (pred / "agent_key.json").write_text(json.dumps({
        "key_items": [{"item": "res_2", "weight": 0.6}, {"item": "gc_day", "weight": 0.4}],
        "primary_mechanism": "Inference: a break of climbers stays clear of a marking GC group."}))
    st12 = next(e for e in rdk.settled_ledger(campaign, 14) if e["stage"] == 12)
    assert st12["key_source"] == "agent" and st12["key_as_logged"] == {"res_2": 0.6, "gc_day": 0.4}
    assert st12["morning_read"].startswith("[day-key agent's own morning read] Inference: a break")


def test_missing_odds_is_recorded_not_fatal(campaign):
    shutil.rmtree(campaign / "odds")
    m = rdk.build_bundle(campaign, 14)
    assert m["odds"] == "missing" and not any(e["path"].startswith("odds/") for e in m["entries"])
    assert any(n.startswith("odds missing") for n in m["notes"])


def _strip_market(campaign: Path, category: str = "pro") -> None:
    """A race Kambi never listed: no odds dir, no event ids, no event_id/odds_capture."""
    shutil.rmtree(campaign / "odds")
    cfg = json.loads((campaign / "campaign.json").read_text())
    cfg["kambi_event_ids"] = {}
    cfg["category"] = category
    (campaign / "campaign.json").write_text(json.dumps(cfg))
    for p in (campaign / "predictions").glob("stage_*/scenarios.json"):
        sc = json.loads(p.read_text())
        sc.pop("event_id", None)
        sc.pop("odds_capture", None)
        p.write_text(json.dumps(sc))


def test_no_market_configured_is_not_offered(campaign):
    _strip_market(campaign)
    assert rdk.market_expected(campaign, 14) == []
    m = rdk.build_bundle(campaign, 14)
    assert m["odds"] == "not_offered" and not any(e["path"].startswith("odds/") for e in m["entries"])
    assert any(n.startswith("odds not_offered") for n in m["notes"])
    assert not any(n.startswith("odds missing") for n in m["notes"])
    ctx = json.loads((campaign / "predictions/stage_14/bundle/stage_context.json").read_text())
    assert ctx["odds"] == "not_offered"


@pytest.mark.parametrize("restore", ["category_wt", "event_ids", "stage_event_id", "degraded"])
def test_any_sign_of_a_market_keeps_missing(campaign, restore):
    _strip_market(campaign, category="wt" if restore == "category_wt" else "pro")
    if restore == "event_ids":
        cfg = json.loads((campaign / "campaign.json").read_text())
        cfg["kambi_event_ids"] = {"stage_14": "1028797734"}
        (campaign / "campaign.json").write_text(json.dumps(cfg))
    elif restore == "stage_event_id":
        p = campaign / "predictions/stage_14/scenarios.json"
        sc = json.loads(p.read_text())
        sc["event_id"] = "1028797734"
        p.write_text(json.dumps(sc))
    elif restore == "degraded":
        d = campaign / "odds" / "2026-09-05"
        d.mkdir(parents=True)
        (d / "degraded.json").write_text("{}")
    assert rdk.market_expected(campaign, 14)
    m = rdk.build_bundle(campaign, 14)
    assert m["odds"] == "missing" and any(n.startswith("odds missing") for n in m["notes"])


def test_template_sentinels_do_not_count_as_a_market(campaign):
    _strip_market(campaign)
    p = campaign / "predictions/stage_14/scenarios.json"
    sc = json.loads(p.read_text())
    sc.update(event_id="FILL_FROM_ODDS_PROVENANCE", odds_capture="YYYY-MM-DD/markets_HHMM.json")
    p.write_text(json.dumps(sc))
    assert rdk.build_bundle(campaign, 14)["odds"] == "not_offered"


def test_render_inlines_only_inline_entries(campaign):
    m = rdk.build_bundle(campaign, 14)
    blocks = rdk.render_bundle(campaign / "predictions/stage_14/bundle", m)
    assert blocks[0]["text"].startswith("<bundle_manifest>")
    inlined = [b["text"].split('"')[1] for b in blocks[1:]]
    assert "odds/markets_1345.json" not in inlined and "odds/win_odds_1345.csv" in inlined
    assert "day_menu_v1_reference.md" in inlined and "settled_stages.json" in inlined


class _Block:
    def __init__(self, text):
        self.type, self.text = "text", text


class _Msg:
    def __init__(self, payload, stop="end_turn"):
        self.content = [_Block(json.dumps(payload))]
        self.stop_reason = stop
        self.model = "claude-opus-5-5"
        self._request_id = "req_test"
        self.usage = {"input_tokens": 10, "output_tokens": 5}


class _Stream:
    def __init__(self, msg):
        self.msg = msg

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return self.msg


class FakeClient:
    """Captures the single request and returns a canned structured output."""

    def __init__(self, payload, stop="end_turn"):
        self.payload, self.stop, self.calls = payload, stop, []
        self.messages = self

    def stream(self, **kw):
        self.calls.append(kw)
        return _Stream(_Msg(self.payload, self.stop))


def _model_output(**over):
    out = {
        "key_items": [{"item": "res_2", "weight": 0.65}, {"item": "gc_day", "weight": 0.35}],
        "family": "escape",
        "macro_routing": {"itt": False, "bunch_considered": False, "gc_day_considered": True,
                          "bunch_rejected_because": "", "gc_day_rejected_because": "the leader's team will ride the break"},
        "primary_mechanism": "A large escape forms on the flat opening and is given a lead nobody chases.",
        "credible_alternative": "The Pandera shatters the group and Mas contests the win.",
        "chase_incentive": {"who_has_reason_to_spend": [{"team": "Movistar", "why": "defend red"}],
                            "verdict": "nobody_pays", "consequence_for_key": "res_2 majority"},
        "comparables_used": [{"stage": 12, "argument": "Calar Alto: escape survived a racing GC group",
                              "measured_outcome": "Omrzel won solo, GC at 2:56"}],
        "evidence": [{"claim": "Mas 3.75 (17.2%), Buitrago 6.50", "ref": "odds/win_odds_1345.csv"},
                     {"claim": "st12 escape held", "ref": "settled_stages.json"}],
        "missing_evidence": ["route facts missing"], "conflicts": [],
        "confidence": 0.6, "human_review_required": False, "review_reason": "none",
    }
    out.update(over)
    return out


def test_key_stage_end_to_end_with_fake_client(campaign):
    client = FakeClient(_model_output())
    record = rdk.key_stage(campaign, 14, client=client, store_kind="none", replay=True)
    # one call, skill as system prompt, bundle + instruction as user content, schema attached, no tools
    assert len(client.calls) == 1
    kw = client.calls[0]
    assert kw["model"] == "claude-opus-5-5" and kw["thinking"] == {"type": "adaptive"}
    assert kw["output_config"]["format"]["schema"] == rec.RECORD_SCHEMA and "tools" not in kw
    assert kw["system"][0]["text"].startswith("# Day-key read") and len(kw["messages"]) == 1
    assert kw["messages"][0]["role"] == "user" and kw["messages"][0]["content"][-1]["text"].startswith("Key stage 14")
    assert "FIXTURE-SENTINEL" not in json.dumps(kw["messages"])

    assert record["key"] == {"res_2": 0.65, "gc_day": 0.35} and record["schema_valid"] is True
    assert record["replay"] is True and record["human_review_required"] is False
    assert record["provenance"]["model_id"] == "claude-opus-5-5" and record["provenance"]["skill_version"] == rec.skill_version()
    assert record["provenance"]["bundle_manifest_sha256"] == json.loads(
        (campaign / "predictions/stage_14/bundle/manifest.json").read_text())["manifest_sha256"]
    written = json.loads((campaign / "predictions/stage_14/agent_key.json").read_text())
    assert written["key"] == record["key"] and written["provenance"]["request_id"] == "req_test"
    assert (campaign / "predictions/stage_14/agent_key_response.json").exists()


def test_key_stage_flags_low_confidence_and_invalid_refs(campaign):
    client = FakeClient(_model_output(confidence=0.4, evidence=[{"claim": "x", "ref": "results/stage_14/results.json"}]))
    record = rdk.key_stage(campaign, 14, client=client, store_kind="none")
    assert record["human_review_required"] is True and record["review_forced_by"][0].startswith("low confidence")
    assert record["schema_valid"] is False
    assert any("not a bundle file" in e for e in record["validation_errors"])
    assert any("results for the stage" in e for e in record["validation_errors"])


def test_key_stage_not_offered_market_is_not_forced_to_review(campaign):
    """Driver policy 2026-10-02 (chip Z3): no market for the race is not by itself a review flag;
    a degraded/absent configured market still is."""
    _strip_market(campaign)
    ev = [{"claim": "st12 escape held", "ref": "settled_stages.json"}]
    record = rdk.key_stage(campaign, 14, client=FakeClient(_model_output(evidence=ev)), store_kind="none", replay=True)
    assert record["schema_valid"] is True and record["human_review_required"] is False
    assert record["review_forced_by"] == []

    shutil.copytree(FIXTURE / "odds", campaign / "odds")      # a market existed ...
    for day in ("2026-09-03", "2026-09-04"):                    # ... but no pre-start snapshot survives
        shutil.rmtree(campaign / "odds" / day)
    record = rdk.key_stage(campaign, 14, client=FakeClient(_model_output(evidence=ev)), store_kind="none",
                           replay=True, rebuild_bundle=True)
    assert record["review_forced_by"] == ["missing odds"] and record["human_review_required"] is True


def test_key_stage_refusal_raises(campaign):
    client = FakeClient(_model_output(), stop="refusal")
    with pytest.raises(RuntimeError):
        rdk.key_stage(campaign, 14, client=client, store_kind="none")


def test_dry_run_builds_bundle_without_calling(campaign):
    client = FakeClient(_model_output())
    assert rdk.key_stage(campaign, 14, client=client, dry_run=True) is None
    assert client.calls == [] and (campaign / "predictions/stage_14/bundle/manifest.json").exists()


def test_parse_stages():
    assert rdk._parse_stages("2-4,7") == [2, 3, 4, 7]
