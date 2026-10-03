"""Route research (chip Z1, 2026-10-02): sourced route facts into route_raw.json.

Offline: the Messages API is a fake client replaying a transcript shaped like the
real one. The record is the one the paid smoke returned for CRO Race 2026
stage 3 (Krk -> Labin, a 2-rider finish keyed as a bunch day without route
facts): the organiser's road book PDF, four climbs, Skitača 3,5 km at 10,8%.
"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from cycling_project.nightly import route_facts, route_research as rr
from cycling_project.nightly.route_facts import ingest_route, parse_number, towns_agree

FIXTURE = json.loads((Path(__file__).resolve().parents[1] / "fixtures" / "nightly"
                      / "route_research_cro_st3.json").read_text())
RECORD = FIXTURE["record"]
ROADBOOK = "https://d3g42de5vbfx19.cloudfront.net/races/roadbooks/2026 - CRO Race.pdf"
FC_PAGE = ('<html><body><div class="sideBox"><p>CRO Race</p><p>3rd stage | 174.5 km</p>'
           '<p>Krk -> Labin</p></div></body></html>')


@pytest.fixture
def campaign(tmp_path):
    root = tmp_path / "cro-race-2026"
    cfg = {"slug": "cro-race-2026", "name": "CRO Race", "year": 2026, "category": "pro",
           "is_stage_race": True, "void_stages": [], "organiser_stage_urls": {},
           "stages": [
               {"number": 2, "date": "2026-09-23", "towns": "Biograd na Moru → Novalja", "distance_km": 114.5},
               {"number": 3, "date": "2026-09-24", "towns": "Krk → Labin", "distance_km": 174.5},
               {"number": 4, "date": "2026-09-25", "towns": "Pula → Rijeka", "distance_km": 160.0, "kind": "itt"},
           ]}
    (root / "predictions" / "stage_03").mkdir(parents=True)
    (root / "results" / "stage_03").mkdir(parents=True)
    (root / "campaign.json").write_text(json.dumps(cfg, ensure_ascii=False))
    (root / "results" / "stage_03" / "stage_page_2026-09-23.html").write_text(FC_PAGE)
    ingest_route(root, "stage_03")                      # the horizon's partial route.json
    return root


# ---------------------------------------------------------------------------
# a fake Messages client replaying a transcript


def transcript(record=RECORD, urls=(ROADBOOK,), search_urls=()):
    blocks = [{"type": "server_tool_use", "id": "s1", "name": "web_search", "input": {"query": "CRO Race 2026 stage 3"}},
              {"type": "web_search_tool_result", "tool_use_id": "s1",
               "content": [{"type": "web_search_result", "url": u, "title": "t"} for u in search_urls]}]
    for i, u in enumerate(urls):
        blocks += [{"type": "server_tool_use", "id": f"f{i}", "name": "web_fetch", "input": {"url": u}},
                   {"type": "web_fetch_tool_result", "tool_use_id": f"f{i}",
                    "content": {"type": "web_fetch_result", "url": u, "retrieved_at": "2026-10-02T15:58:00Z",
                                "content": {"type": "document", "source": {"type": "text", "data": "..."}}}}]
    if record is not None:
        blocks.append({"type": "tool_use", "id": "t1", "name": rr.TOOL_NAME, "input": record})
    return blocks


class FakeStream:
    def __init__(self, msg):
        self.msg = msg

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return self.msg


class FakeClient:
    """``client.messages.stream(**kw)`` returning queued messages, recording each request."""

    def __init__(self, *messages):
        self.queue = list(messages)
        self.requests = []
        self.messages = self

    def stream(self, **kw):
        self.requests.append(kw)
        return FakeStream(self.queue.pop(0))


def message(blocks, stop="tool_use", searches=1, fetches=1):
    return SimpleNamespace(content=blocks, stop_reason=stop, _request_id="req_test",
                           usage={"input_tokens": 1000, "output_tokens": 100,
                                  "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
                                  "server_tool_use": {"web_search_requests": searches,
                                                      "web_fetch_requests": fetches}})


ALL_URLS = tuple(s["url"] for s in RECORD["sources"])


# ---------------------------------------------------------------------------
# route_facts: the research-layer rules


@pytest.mark.unit
@pytest.mark.parametrize("value,expected", [("174,5 km", 174.5), ("10,8%", 10.8), ("109,0", 109.0),
                                            ("2,350 m", 2350.0), ("3300 m", 3300.0), ("1,234,567", 1234567.0)])
def test_a_decimal_comma_is_a_decimal_and_three_digits_are_thousands(value, expected):
    assert parse_number(value, field="x") == (expected, None)


@pytest.mark.unit
def test_place_names_match_leniently_but_not_across_towns():
    assert towns_agree("Luxembourg-Limpertsberg", "Luxembourg (Limpertsberg)")
    assert towns_agree("Škitača", "Skitaca") and towns_agree("Krk", "Krk")
    assert not towns_agree("Labin", "Rijeka")


def _write_raw(campaign, raw):
    (campaign / "predictions" / "stage_03" / "route_raw.json").write_text(json.dumps(raw, ensure_ascii=False))


@pytest.mark.unit
def test_a_research_layer_without_a_source_is_rejected_whole(campaign):
    _write_raw(campaign, {"researched_by": "route-researcher agent", "vertical_metres": "3300 m",
                          "profile_class": "hilly", "climbs": [{"name": "Skitača", "km_mark": "153"}],
                          "sources": [{"url": "not a url", "fetched_at": "2026-10-02"}]})
    route = ingest_route(campaign, "stage_03")
    assert route["route_facts"] == "partial"
    assert route["vertical_metres"] is None and route["climbs"] == [] and route["profile_class"] is None
    assert any("whole layer is rejected" in e for e in route["errors"])
    assert route["field_sources"]["distance_km"] == "firstcycling"      # FirstCycling stands alone


@pytest.mark.unit
def test_a_source_needs_a_fetch_time(campaign):
    _write_raw(campaign, {"researched_by": "x", "vertical_metres": "3300 m", "sources": [{"url": ROADBOOK}]})
    route = ingest_route(campaign, "stage_03")
    assert route["vertical_metres"] is None and any("no fetched_at" in e for e in route["errors"])


@pytest.mark.unit
def test_a_climb_citing_an_unlisted_page_is_an_error(campaign):
    _write_raw(campaign, {"researched_by": "x", "sources": [{"url": ROADBOOK, "fetched_at": "t"}],
                          "climbs": [{"name": "Skitača", "km_mark": "153,0", "source_url": "https://elsewhere.example/x"}]})
    route = ingest_route(campaign, "stage_03")
    assert route["route_facts"] == "partial"
    assert any("not one of the layer's sources" in e for e in route["errors"])


@pytest.mark.unit
def test_a_research_layer_naming_other_towns_is_a_warning(campaign):
    _write_raw(campaign, {"researched_by": "x", "start": "Pula", "finish": "Rijeka",
                          "sources": [{"url": ROADBOOK, "fetched_at": "t"}]})
    route = ingest_route(campaign, "stage_03")
    assert route["route_facts"] == "partial"
    assert any("start disagrees with FirstCycling" in w for w in route["warnings"])
    assert any("finish disagrees with FirstCycling" in w for w in route["warnings"])


@pytest.mark.unit
def test_an_overlong_finale_is_rejected_not_cut(campaign):
    _write_raw(campaign, {"researched_by": "x", "finale": "x" * 900,
                          "sources": [{"url": ROADBOOK, "fetched_at": "t"}]})
    route = ingest_route(campaign, "stage_03")
    assert route["finale"] is None and any("above the 800 cap" in e for e in route["errors"])


# ---------------------------------------------------------------------------
# which units need research


@pytest.mark.unit
def test_a_partial_pro_stage_needs_research_and_nothing_else_does(campaign):
    assert rr.needs_research(campaign, "stage_03") == (True, "route_facts partial")
    assert rr.needs_research(campaign, "stage_04")[1] == "time trial (itt)"
    assert rr.needs_research(campaign, "race")[0] is False
    cfg = json.loads((campaign / "campaign.json").read_text())
    assert rr.needs_research(campaign, "stage_03", {**cfg, "category": "d1"})[0] is False
    assert rr.needs_research(campaign, "stage_03", {**cfg, "void_stages": [3]})[1] == "void stage"
    route = json.loads((campaign / "predictions" / "stage_03" / "route.json").read_text())
    (campaign / "predictions" / "stage_03" / "route.json").write_text(json.dumps({**route, "route_facts": "complete"}))
    assert rr.needs_research(campaign, "stage_03")[1] == "route_facts complete"


@pytest.mark.unit
@pytest.mark.parametrize("name", ["route_raw.json", "route.override.json", "route_research.json"])
def test_one_attempt_per_unit(campaign, name):
    (campaign / "predictions" / "stage_03" / name).write_text("{}")
    assert rr.needs_research(campaign, "stage_03")[0] is False


@pytest.mark.unit
def test_a_unit_with_no_route_json_yet_needs_research(campaign):
    (campaign / "predictions" / "stage_02").mkdir()
    assert rr.needs_research(campaign, "stage_02") == (True, "route_facts missing")


# ---------------------------------------------------------------------------
# provenance


@pytest.mark.unit
def test_only_retrieved_sources_survive_and_their_climbs_with_them():
    seen = rr.seen_urls(transcript(urls=(ROADBOOK,), search_urls=(ALL_URLS[3],)))
    assert seen[rr._norm_url(ROADBOOK)]["seen_via"] == "web_fetch"
    assert seen[rr._norm_url(ROADBOOK)]["fetched_at"] == "2026-10-02T15:58:00Z"
    ctx = {"unit": "stage_03", "stage": 3, "campaign": "cro-race-2026"}
    record = json.loads(json.dumps(RECORD))
    record["climbs"][0]["source_url"] = "https://never-fetched.example/page"
    raw, info = rr.assemble_raw(ctx, record, seen, model="m")
    assert [s["url"] for s in raw["sources"]] == [ROADBOOK, ALL_URLS[3]]
    assert {d["url"] for d in info["sources_dropped"]} == {ALL_URLS[1], ALL_URLS[2]}
    assert [c["name"] for c in raw["climbs"]] == [c["name"] for c in RECORD["climbs"][1:]]
    assert raw["provenance_dropped"]["climbs"][0]["name"] == "Sv. Jelena"
    assert raw["climbs"][1]["km_to_go"] == "21,5"            # verbatim, never converted
    assert raw["researched_by"] == rr.RESEARCHER


@pytest.mark.unit
def test_no_stage_page_or_no_retrieved_source_writes_nothing():
    ctx = {"unit": "stage_03", "stage": 3, "campaign": "c"}
    assert rr.assemble_raw(ctx, {**RECORD, "found_stage_page": False}, {}, model="m")[0] is None
    raw, info = rr.assemble_raw(ctx, RECORD, {}, model="m")
    assert raw is None and "no cited source" in info["reason"]
    assert rr.assemble_raw(ctx, None, {}, model="m")[1]["reason"] == "no record_route_facts call"


# ---------------------------------------------------------------------------
# the unit: files written, ingest run


@pytest.mark.unit
def test_research_unit_writes_raw_and_log_and_grades_complete(campaign):
    client = FakeClient(message(transcript(urls=ALL_URLS), fetches=4))
    out = rr.research_unit(campaign, "stage_03", client=client)
    pred = campaign / "predictions" / "stage_03"
    raw = json.loads((pred / "route_raw.json").read_text())
    route = json.loads((pred / "route.json").read_text())
    log = json.loads((pred / "route_research.json").read_text())
    assert out["status"] == "written" and out["climbs"] == 4
    assert route["route_facts"] == "complete", route["errors"] + route["warnings"]
    assert route["distance_km"] == 174.5 and route["vertical_metres"] == 3300.0
    assert [c["gradient_pct"] for c in route["climbs"]][2] == 10.8
    assert route["finale"].startswith("Official roadbook")
    assert route["source_urls"] == list(ALL_URLS) and route["researched_by"] == rr.RESEARCHER
    assert raw["distance_km"] == "174,5 km"                    # the raw layer stays verbatim
    assert log["cost_usd"] == pytest.approx((1000 * 4 + 100 * 20) / 1e6 + 0.01)
    req = client.requests[0]
    assert req["model"] == "claude-opus-5-5" and req["thinking"] == {"type": "adaptive"}
    types = {t.get("type") for t in req["tools"]}
    assert {"web_search_20260209", "web_fetch_20260209"} <= types
    assert all(t.get("blocked_domains") == rr.BLOCKED_DOMAINS for t in req["tools"] if "type" in t)
    assert req["tools"][-1]["strict"] is True
    assert "Krk → Labin" in req["messages"][0]["content"]
    # one attempt: a second run does not call the model
    assert rr.research_unit(campaign, "stage_03", client=FakeClient())["status"] == "skipped"


@pytest.mark.unit
def test_nothing_found_leaves_the_horizon_facts_and_logs_the_attempt(campaign):
    client = FakeClient(message(transcript(record={**RECORD, "found_stage_page": False}), fetches=1))
    out = rr.research_unit(campaign, "stage_03", client=client)
    pred = campaign / "predictions" / "stage_03"
    assert out["status"] == "nothing_found" and not (pred / "route_raw.json").exists()
    assert json.loads((pred / "route.json").read_text())["route_facts"] == "partial"
    assert (pred / "route_research.json").exists()
    assert rr.needs_research(campaign, "stage_03")[0] is False


@pytest.mark.unit
def test_pause_turn_resumes_without_an_extra_user_turn(campaign):
    first = transcript(record=None, urls=ALL_URLS[:2])
    second = transcript(urls=ALL_URLS[2:])
    client = FakeClient(message(first, stop="pause_turn"), message(second))
    out = rr.research_unit(campaign, "stage_03", client=client)
    assert out["status"] == "written" and len(client.requests) == 2
    resumed = client.requests[1]["messages"]
    assert [m["role"] for m in resumed] == ["user", "assistant"]


@pytest.mark.unit
def test_a_force_rerun_keeps_the_old_layer_beside_the_new(campaign):
    rr.research_unit(campaign, "stage_03", client=FakeClient(message(transcript(urls=ALL_URLS))))
    rr.research_unit(campaign, "stage_03", client=FakeClient(message(transcript(urls=ALL_URLS))), force=True)
    pred = campaign / "predictions" / "stage_03"
    assert len(list(pred.glob("route_raw.json.superseded-*"))) == 1
    # a superseded copy is not .json, so the driver never mistakes it for a board
    from cycling_project.nightly.driver import _has_scenario_boards
    assert not _has_scenario_boards(pred)


@pytest.mark.unit
def test_pages_that_served_another_stage_are_offered_first(campaign):
    rr.research_unit(campaign, "stage_03", client=FakeClient(message(transcript(urls=ALL_URLS))))
    (campaign / "predictions" / "stage_02").mkdir()
    ctx = rr.stage_context(campaign, "stage_02")
    assert ctx["known_sources"][0] == ROADBOOK
    assert ROADBOOK in rr.user_message(ctx)


@pytest.mark.unit
def test_dry_run_calls_nothing_and_writes_nothing(campaign):
    out = rr.research_unit(campaign, "stage_03", client=FakeClient(), dry_run=True)
    assert out["status"] == "planned" and "Krk → Labin" in out["prompt"]
    assert not (campaign / "predictions" / "stage_03" / "route_research.json").exists()


@pytest.mark.unit
def test_cli_needs_lists_every_stage(campaign, capsys):
    assert rr.main(["needs", str(campaign)]) == 0
    rows = {r["unit"]: r for r in json.loads(capsys.readouterr().out)}
    assert rows["stage_03"]["needed"] and not rows["stage_04"]["needed"]


@pytest.mark.unit
def test_the_research_log_is_not_a_rendered_board(campaign):
    from cycling_project.nightly.driver import NON_BOARD_JSON
    assert {"route_research.json", "route_raw.json"} <= NON_BOARD_JSON
    assert route_facts.SCALAR_FIELDS[-2:] == ("finale", "notes")


# ---------------------------------------------------------------------------
# per-race mode (round 2): gather once, cache verbatim, transcribe per stage


PDF_BYTES = b"%PDF-1.4 CRO Race 2026 road book (fixture)\n%%EOF"
STAGE_PAGE = "https://crorace.com/en/etape/stage-3/"


def gather_blocks(record=None, docs=None):
    import base64

    docs = docs if docs is not None else [
        (ROADBOOK, {"type": "base64", "media_type": "application/pdf",
                    "data": base64.b64encode(PDF_BYTES).decode()}),
        (STAGE_PAGE, {"type": "text", "media_type": "text/plain", "data": "Stage 3 Krk - Labin 174,5 km"}),
    ]
    blocks = []
    for i, (url, source) in enumerate(docs):
        blocks += [{"type": "server_tool_use", "id": f"f{i}", "name": "web_fetch", "input": {"url": url}},
                   {"type": "web_fetch_tool_result", "tool_use_id": f"f{i}",
                    "content": {"type": "web_fetch_result", "url": url, "retrieved_at": "2026-09-27T12:07:51Z",
                                "content": {"type": "document", "title": "t", "source": source}}}]
    record = record if record is not None else {
        "found": True, "notes": None,
        "sources": [{"url": ROADBOOK, "title": "Road book", "kind": "road_book", "stages": []},
                    {"url": STAGE_PAGE, "title": "Stage 3", "kind": "stage_page", "stages": [3]}]}
    blocks.append({"type": "tool_use", "id": "g1", "name": rr.GATHER_TOOL_NAME, "input": record})
    return blocks


def stage_record(stage, found=True):
    return {"found_stage_page": found, "distance_km": "174,5 km" if stage == 3 else "114,5 km",
            "vertical_metres": "3300 m", "profile_class": None,
            "start": "Krk" if stage == 3 else "Biograd na Moru",
            "finish": "Labin" if stage == 3 else "Novalja", "climbs_listed": True,
            "climbs": [{"name": "Skitača", "category": "1", "km_mark": "153,0", "km_to_go": "21,5",
                        "length_km": None, "gradient_pct": None, "source_url": ROADBOOK}],
            "finale": "Uphill finish.", "notes": None,
            "sources": [{"url": ROADBOOK, "title": "Road book", "supports": "all"}]}


def text_message(payload):
    return SimpleNamespace(content=[{"type": "text", "text": json.dumps(payload)}], stop_reason="end_turn",
                           _request_id="req_t", usage={"input_tokens": 50, "output_tokens": 1000,
                                                       "cache_creation_input_tokens": 0,
                                                       "cache_read_input_tokens": 49000})


class FilesClient(FakeClient):
    def __init__(self, *messages):
        super().__init__(*messages)
        self.uploads = []
        self.files = SimpleNamespace(upload=self._upload)

    def _upload(self, file):
        self.uploads.append(file[0])
        return SimpleNamespace(id=f"file_{len(self.uploads)}")


@pytest.mark.unit
def test_per_race_gathers_once_caches_verbatim_and_transcribes_each_stage(campaign):
    client = FilesClient(message(gather_blocks(), searches=2, fetches=2),
                         text_message(stage_record(2)), text_message(stage_record(3)))
    out = rr.research_race(campaign, ["stage_02", "stage_03"], client=client)
    assert [r["mode"] for r in out] == ["gather", "per_race", "per_race"]
    index = rr.load_sources(campaign)
    roadbook = next(s for s in index["sources"] if s["url"] == ROADBOOK)
    assert (rr.sources_dir(campaign) / roadbook["file"]).read_bytes() == PDF_BYTES      # verbatim
    assert roadbook["retrieved_at"] == "2026-09-27T12:07:51Z" and roadbook["media_type"] == "application/pdf"
    raw = json.loads((campaign / "predictions" / "stage_03" / "route_raw.json").read_text())
    assert raw["mode"] == "per_race" and raw["sources"][0]["seen_via"] == "route_sources_cache"
    assert raw["sources"][0]["fetched_at"] == "2026-09-27T12:07:51Z"
    route = json.loads((campaign / "predictions" / "stage_03" / "route.json").read_text())
    assert route["climbs"][0]["name"] == "Skitača" and route["distance_km"] == 174.5
    # the gather has the web tools; the transcriptions have none and share one document prefix
    gather, t2, t3 = client.requests
    assert {t.get("type") for t in gather["tools"]} >= {"web_search_20260209", "web_fetch_20250910"}
    assert "tools" not in t2 and t2["output_config"]["format"]["type"] == "json_schema"
    docs2 = [b for b in t2["messages"][0]["content"] if b["type"] == "document"]
    docs3 = [b for b in t3["messages"][0]["content"] if b["type"] == "document"]
    assert docs2 == docs3 and docs2[-1]["cache_control"] == {"type": "ephemeral"}
    assert client.uploads == []                                   # small PDFs go inline
    # the cache is not a unit and not a board
    assert rr.needs_research(campaign, "route_sources")[0] is False


@pytest.mark.unit
def test_a_second_run_reads_the_cache_and_never_searches(campaign):
    rr.research_race(campaign, ["stage_03"], client=FilesClient(message(gather_blocks()),
                                                               text_message(stage_record(3))))
    (campaign / "predictions" / "stage_02").mkdir(exist_ok=True)
    client = FilesClient(text_message(stage_record(2)))
    out = rr.research_race(campaign, ["stage_02"], client=client)
    assert [r["mode"] for r in out] == ["per_race"] and len(client.requests) == 1
    assert "tools" not in client.requests[0]


@pytest.mark.unit
def test_a_stage_the_cache_misses_falls_back_to_the_per_stage_conversation(campaign):
    client = FilesClient(message(gather_blocks()), text_message(stage_record(3, found=False)),
                         message(transcript(urls=ALL_URLS)))
    out = rr.research_race(campaign, ["stage_03"], client=client)
    res = out[-1]
    assert res["mode"] == "per_stage" and res["status"] == "written"
    assert res["fallback_from_per_race"]["transcribe_reason"].startswith("the researcher found no page")
    assert {t.get("type") for t in client.requests[-1]["tools"]} >= {"web_search_20260209"}


@pytest.mark.unit
def test_without_fallback_a_miss_is_logged_once(campaign):
    client = FilesClient(message(gather_blocks()), text_message(stage_record(3, found=False)))
    out = rr.research_race(campaign, ["stage_03"], client=client, fallback=False)
    assert out[-1]["status"] == "nothing_found" and out[-1]["mode"] == "per_race"
    assert rr.needs_research(campaign, "stage_03")[0] is False


@pytest.mark.unit
def test_a_listed_page_that_was_never_fetched_is_not_cached(campaign):
    record = {"found": True, "notes": None,
              "sources": [{"url": ROADBOOK, "title": "rb", "kind": "road_book", "stages": []},
                          {"url": "https://never.example/x", "title": None, "kind": "other", "stages": []}]}
    rr.research_race(campaign, ["stage_03"], client=FilesClient(message(gather_blocks(record=record)),
                                                               text_message(stage_record(3))))
    index = rr.load_sources(campaign)
    assert [s["url"] for s in index["sources"]] == [ROADBOOK]
    assert index["uncached"] == [{"url": "https://never.example/x", "reason": "not fetched in this conversation",
                                  "shape": {}}]


@pytest.mark.unit
def test_a_large_pdf_goes_through_the_files_api_once_per_run(campaign, monkeypatch):
    monkeypatch.setattr(rr, "INLINE_PDF_MAX_BYTES", 10)
    (campaign / "predictions" / "stage_02").mkdir()
    client = FilesClient(message(gather_blocks()), text_message(stage_record(2)), text_message(stage_record(3)))
    rr.research_race(campaign, ["stage_02", "stage_03"], client=client)
    assert len(client.uploads) == 1
    sources = [[b["source"] for b in r["messages"][0]["content"] if b["type"] == "document"][0]
               for r in client.requests[1:]]
    assert sources[0] == sources[1] == {"type": "file", "file_id": "file_1"}


@pytest.mark.unit
def test_auto_mode_prefers_per_race_when_several_stages_qualify(campaign):
    client = FilesClient(message(gather_blocks()), text_message(stage_record(3)))
    (campaign / "predictions" / "stage_02").mkdir()             # stage 2 qualifies too
    out = rr.research_auto(campaign, "stage_03", client=client)
    assert out["mode"] == "per_race" and out["gather"]["mode"] == "gather"
    assert out["cost_usd"] == pytest.approx(out["gather"]["cost_usd"] + rr.cost_usd(
        {"input_tokens": 50, "output_tokens": 1000, "cache_read_input_tokens": 49000}), abs=1e-4)


@pytest.mark.unit
def test_auto_mode_uses_one_conversation_for_a_lone_stage(campaign):
    cfg = json.loads((campaign / "campaign.json").read_text())
    cfg["stages"] = [s for s in cfg["stages"] if s["number"] != 2]
    (campaign / "campaign.json").write_text(json.dumps(cfg, ensure_ascii=False))
    out = rr.research_auto(campaign, "stage_03", client=FilesClient(message(transcript(urls=ALL_URLS))))
    assert out["mode"] == "per_stage" and rr.load_sources(campaign) is None


@pytest.mark.unit
def test_a_cached_road_book_stage_without_a_label_grades_complete(campaign):
    """Owner decision (chip Z1 round 3): CRO st3 from the road book has distance, 3300 m and
    four climbs but no printed stage-type label; that is complete, the label listed as absent."""
    client = FilesClient(message(gather_blocks()), text_message(stage_record(3)))
    rr.research_race(campaign, ["stage_03"], client=client)
    route = json.loads((campaign / "predictions" / "stage_03" / "route.json").read_text())
    assert route["route_facts"] == "complete", route["missing_fields"] + route["errors"] + route["warnings"]
    assert route["profile_class"] is None
    assert route["missing_fields"] == [] and route["optional_missing"] == ["profile_class"]


def _grade(campaign, raw):
    _write_raw(campaign, raw)
    return ingest_route(campaign, "stage_03")


SOURCED = {"researched_by": "x", "sources": [{"url": ROADBOOK, "fetched_at": "t"}],
           "vertical_metres": "3300 m",
           "climbs": [{"name": "Sv. Jelena", "km_mark": "109,0", "source_url": ROADBOOK},
                      {"name": "Skitača", "km_mark": "153,0", "source_url": ROADBOOK}]}


@pytest.mark.unit
def test_profile_class_is_optional_only_for_a_sourced_research_layer(campaign):
    route = _grade(campaign, SOURCED)
    assert route["route_facts"] == "complete" and route["optional_missing"] == ["profile_class"]
    # a legacy transcription (no researched_by) still needs the label
    legacy = {k: v for k, v in SOURCED.items() if k != "researched_by"}
    route = _grade(campaign, legacy)
    assert route["route_facts"] == "partial" and route["missing_fields"] == ["profile_class"]
    assert route["optional_missing"] == []


@pytest.mark.unit
def test_a_sourced_layer_still_needs_vertical_and_climbs(campaign):
    route = _grade(campaign, {**SOURCED, "vertical_metres": None})
    assert route["route_facts"] == "partial" and route["missing_fields"] == ["vertical_metres"]
    route = _grade(campaign, {k: v for k, v in SOURCED.items() if k != "climbs"})
    assert route["route_facts"] == "partial" and "climbs" in route["missing_fields"]
    route = _grade(campaign, {**{k: v for k, v in SOURCED.items() if k != "climbs"}, "climbs_listed": False})
    assert route["route_facts"] == "complete"                    # known-empty counts


@pytest.mark.unit
def test_disorder_and_errors_still_downgrade_a_sourced_layer(campaign):
    route = _grade(campaign, {**SOURCED, "climbs": list(reversed(SOURCED["climbs"]))})
    assert route["route_facts"] == "partial" and route["climbs_ordered"] is False
    route = _grade(campaign, {**SOURCED, "climbs": [{"name": "Skitača", "km_mark": "153,0",
                                                     "source_url": "https://elsewhere.example/x"}]})
    assert route["route_facts"] == "partial"


@pytest.mark.unit
def test_a_firstcycling_only_stage_is_still_partial(campaign):
    route = json.loads((campaign / "predictions" / "stage_03" / "route.json").read_text())
    assert route["route_facts"] == "partial" and "profile_class" in route["missing_fields"]
    assert route["optional_missing"] == []


@pytest.mark.unit
def test_french_road_book_climbing_notation_parses():
    assert parse_number("3083m D+", field="v") == (3083.0, None)
    assert parse_number("3083 m d+", field="v") == (3083.0, None)
