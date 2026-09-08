"""UCI results bridge (UCI_MANAGED_AGENT_BUILD_BRIEF.md): acquisition, ingest, identity, driver.

Fixtures (captured ONCE from the Mac with plain ``requests`` on 2026-09-06, 3.5 s apart):
``fixtures/uci/vuelta-2026-stage14/`` = competition page 76942 + Stage 14 Stage Classification
(``D2EV374857``) + Stage 14 General Classification (``D2EV375761``) shaped like a real capture with a
generated ``uci_raw.json``; ``fixtures/uci/stage15_stage_D2EV374856.json`` = a second event-code case;
``fixtures/uci/uci_aliases.csv`` = the five human-confirmed aliases the roster cannot resolve
deterministically (nicknames, a spelling variant, a Danish middle-name order, a dropped surname).
No test touches the network.
"""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from cycling_project.nightly import driver as drv
from cycling_project.nightly import uci_acquire as ua
from cycling_project.nightly import uci_identity as ident
from cycling_project.nightly import uci_ingest as ui
from cycling_project.nightly.store import FakeStore

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
UCI = FIXTURES / "uci" / "vuelta-2026-stage14"
ALIASES = FIXTURES / "uci" / "uci_aliases.csv"
STAGE15 = FIXTURES / "uci" / "stage15_stage_D2EV374856.json"
CAMPAIGN = FIXTURES / "nightly" / "driver_stage14"
PCS = FIXTURES / "pcs" / "vuelta-2026-stage14"
COMP_URL = "https://www.uci.org/competition-details/2026/ROA/76942"


@pytest.fixture
def campaign(tmp_path):
    dst = tmp_path / "vuelta-2026"
    shutil.copytree(CAMPAIGN, dst)
    shutil.copytree(UCI, dst / "results" / "stage_14" / "uci")
    shutil.copy(ALIASES, dst / "uci_aliases.csv")
    return dst


def _ingest(campaign, **kw):
    kw.setdefault("aliases_csv", campaign / "uci_aliases.csv")
    return ui.ingest(campaign, "stage_14", crosswalk_csv=campaign / "rider_crosswalk.csv", **kw)


def _edit_json(path: Path, fn) -> None:
    doc = json.loads(path.read_text(encoding="utf-8"))
    fn(doc)
    path.write_text(json.dumps(doc), encoding="utf-8")


# ---------------------------------------------------------------------------
# acquisition primitives (pure)
# ---------------------------------------------------------------------------

def test_data_props_decodes_and_selects_event_codes():
    props = ua.extract_data_props((UCI / "competition.html").read_text(encoding="utf-8"))
    assert props["competitionDetails"]["name"] == "La Vuelta Ciclista a España"
    st = ua.find_stage(props, "stage_14")
    assert st["label"] == "Stage 14" and st["schedule_date"] == "05 Sep 2026"
    sel = ua.select_classifications(st["accordion"])
    assert sel["stage"] == {"title": "Stage Classification", "event_code": "D2EV374857", "race_type": "A"}
    assert sel["gc"]["event_code"] == "D2EV375761"
    assert sel["points"]["event_code"] == "D2EV380944" and sel["kom"]["event_code"] == "D2EV381280"
    assert "teams" not in sel                                       # not published for this stage
    st15 = ua.find_stage(props, "stage_15")
    assert ua.select_classifications(st15["accordion"])["stage"]["event_code"] == "D2EV374856"
    with pytest.raises(ua.AcquireError):
        ua.find_stage(props, "stage_16")                              # in the schedule, no results yet
    with pytest.raises(ua.AcquireError):
        ua.extract_data_props("<html><body>rendered text without the attribute</body></html>")


def test_competition_url_validation():
    assert ua.parse_competition_url(COMP_URL) == {"url": COMP_URL, "year": 2026, "discipline": "ROA", "id": "76942"}
    assert ua.parse_competition_url("https://uci.org/competition-details/2026/ROA/76942/")["url"] == COMP_URL
    for bad in ("https://www.uci.org/competition-details/2026/ROA", "https://www.procyclingstats.com/race/x", "http://www.uci.org/competition-details/2026/ROA/1"):
        with pytest.raises(ua.AcquireError):
            ua.parse_competition_url(bad)


def test_results_url_is_built_with_three_encoded_parameters():
    url = ua.results_url("D2EV374857", "ROA", "A", "Stage Classification")
    assert url == "https://www.uci.org/api/calendar/results/D2EV374857?discipline=ROA&raceType=A&raceName=Stage%20Classification"
    params = ua.assert_well_formed_results_url(url)
    assert params == {"discipline": "ROA", "raceType": "A", "raceName": "Stage Classification"}
    assert ua.assert_well_formed_results_url(ua.results_url("D2EV375761", "ROA", "A", "Stage General Classification"))["raceName"] == "Stage General Classification"


def test_regression_literal_percent26_is_rejected():
    """A literal %26 between parameters produces ONE malformed parameter — must never reach UCI."""
    bad = "https://www.uci.org/api/calendar/results/D2EV374857?discipline=ROA%26raceType=A%26raceName=Stage%20Classification"
    assert dict(__import__("urllib.parse").parse.parse_qsl(urlsplit(bad).query)) == {"discipline": "ROA&raceType=A&raceName=Stage Classification"}
    with pytest.raises(ua.AcquireError):
        ua.assert_well_formed_results_url(bad)
    with pytest.raises(ua.AcquireError):
        ua.results_url("D2EV374857", "ROA", "B", "Stage Classification")    # unsupported raceType


# ---------------------------------------------------------------------------
# acquisition with a fake HTTP session (no network)
# ---------------------------------------------------------------------------

class _Resp:
    def __init__(self, status, body: bytes, ctype):
        self.status_code, self.content, self.headers = status, body, {"Content-Type": ctype}


class _FakeSession:
    """Serves the fixture files by URL; records every request."""

    def __init__(self, fail_kind=None, status=200):
        self.calls = []
        self.fail_kind, self.status = fail_kind, status

    def get(self, url, timeout=None, headers=None):
        self.calls.append(url)
        if url == COMP_URL:
            return _Resp(200, (UCI / "competition.html").read_bytes(), "text/html; charset=utf-8")
        params = ua.assert_well_formed_results_url(url)
        code = urlsplit(url).path.rsplit("/", 1)[1]
        files = {"D2EV374857": UCI / "stage.json", "D2EV375761": UCI / "gc.json", "D2EV374856": STAGE15}
        if code in files:
            kind = {"D2EV374857": "stage", "D2EV375761": "gc", "D2EV374856": "stage"}[code]
            if self.fail_kind == kind:
                return _Resp(self.status, b'{"error":"boom"}', "application/json")
            assert params["raceName"] in ("Stage Classification", "Stage General Classification")
            return _Resp(200, files[code].read_bytes(), "application/json; charset=utf-8")
        return _Resp(404, b"not found", "text/plain")


def _fetcher(session):
    return ua.Fetcher(session=session, min_interval=0.0, jitter=0.0, retries=2, sleep=lambda s: None)


def test_acquire_saves_raw_bytes_index_and_is_idempotent(tmp_path):
    out = tmp_path / "uci"
    sess = _FakeSession()
    index = ua.acquire(competition_url=COMP_URL, unit="stage_14", out_dir=out, campaign_slug="vuelta-2026",
                       kinds=["stage", "gc"], fetcher=_fetcher(sess))
    assert index["complete"] and index["requests_made"] == 3 and len(sess.calls) == 3
    assert (out / "stage.json").read_bytes() == (UCI / "stage.json").read_bytes()            # verbatim
    assert (out / "competition.html").read_bytes() == (UCI / "competition.html").read_bytes()
    st = index["pages"]["stage"]
    assert st["event_code"] == "D2EV374857" and st["row_count"] == 155 and st["http_status"] == 200
    assert st["sha256"] == __import__("hashlib").sha256((UCI / "stage.json").read_bytes()).hexdigest()
    assert st["source_url"].endswith("raceName=Stage%20Classification") and st["content_type"].startswith("application/json")
    assert index["stage"]["label"] == "Stage 14" and index["competition"]["name"] == "La Vuelta Ciclista a España"
    assert ua.capture_is_complete(ua.read_index(out))
    # rerun: reused, zero requests
    sess2 = _FakeSession()
    again = ua.acquire(competition_url=COMP_URL, unit="stage_14", out_dir=out, kinds=["stage", "gc"], fetcher=_fetcher(sess2))
    assert again["reused"] is True and sess2.calls == []
    # refresh refuses to overwrite a differing capture unless superseded
    (out / "stage.json").write_bytes(b'{"results": [], "podium": {}, "headers": []}')
    with pytest.raises(ua.AcquireError):
        ua.acquire(competition_url=COMP_URL, unit="stage_14", out_dir=out, kinds=["stage", "gc"], fetcher=_fetcher(_FakeSession()), refresh=True)
    idx3 = ua.acquire(competition_url=COMP_URL, unit="stage_14", out_dir=out, kinds=["stage", "gc"], fetcher=_fetcher(_FakeSession()),
                      refresh=True, supersede=True)
    prev = [p for p in out.iterdir() if p.name.startswith("previous_")]
    assert len(prev) == 1 and (prev[0] / "stage.json").read_bytes().startswith(b'{"results": []')
    assert idx3["complete"] and (out / "stage.json").read_bytes() == (UCI / "stage.json").read_bytes()


def test_acquire_incomplete_when_a_required_classification_fails(tmp_path):
    out = tmp_path / "uci"
    index = ua.acquire(competition_url=COMP_URL, unit="stage_14", out_dir=out, kinds=["stage", "gc"],
                       fetcher=_fetcher(_FakeSession(fail_kind="gc", status=503)))
    assert not index["complete"] and index["pages"]["gc"]["error"] == "HTTP 503" and index["pages"]["stage"]["row_count"] == 155
    assert (out / "gc.json").exists()                                                          # the error body is kept verbatim
    assert not ua.capture_is_complete(index)
    with pytest.raises(ua.AcquireError):
        ua.acquire(competition_url=COMP_URL, unit="stage_16", out_dir=tmp_path / "u16", fetcher=_fetcher(_FakeSession()))


def test_cli_exit_codes(tmp_path, monkeypatch, capsys):
    real = ua.Fetcher
    monkeypatch.setattr(ua, "Fetcher", lambda **kw: real(session=_FakeSession(), min_interval=0.0, jitter=0.0, retries=2, sleep=lambda s: None))
    code = ua.main(["--competition-url", COMP_URL, "--unit", "stage_14", "--out", str(tmp_path / "u"), "--kinds", "stage,gc"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and out["status"] == "ok" and out["pages"]["stage"]["rows"] == 155
    monkeypatch.setattr(ua, "Fetcher", lambda **kw: real(session=_FakeSession(fail_kind="stage", status=500), min_interval=0.0, jitter=0.0, retries=2, sleep=lambda s: None))
    assert ua.main(["--competition-url", COMP_URL, "--unit", "stage_14", "--out", str(tmp_path / "u2"), "--kinds", "stage,gc"]) == 10
    assert ua.main(["--competition-url", "https://example.com/x", "--unit", "stage_14", "--out", str(tmp_path / "u3")]) == 20


# ---------------------------------------------------------------------------
# ingest: parity + accounting
# ---------------------------------------------------------------------------

def test_ingest_reproduces_committed_archive_bytewise(campaign):
    rep = _ingest(campaign)
    assert rep.ok, rep.failing
    out = campaign / "results" / "stage_14"
    for name in ("results.csv", "gc.csv"):
        assert (out / name).read_bytes() == (CAMPAIGN / "expected" / "stage_14" / name).read_bytes(), name
    live = CAMPAIGN.parents[3] / "performance_eval" / "vuelta-2026" / "results" / "stage_14"
    if (live / "results.csv").exists():
        assert (out / "results.csv").read_bytes() == (live / "results.csv").read_bytes()
        assert (out / "gc.csv").read_bytes() == (live / "gc.csv").read_bytes()
    rj = json.loads((out / "results.json").read_text())
    assert rj["source"] == "uci" and rj["race_time"] == 15309.0 and rj["n_results"] == 155 and rj["date"] == "2026-09-05"
    assert rj["url"].startswith("https://www.uci.org/api/calendar/results/D2EV374857?")
    assert rj["uci"]["pages"]["stage"]["event_code"] == "D2EV374857" and rj["uci"]["raw_results"][1]["result"] == "+1"
    assert rj["results"][0]["name"] == "Brenner Marco" and rj["results"][0]["gap"] == 0 and rj["results"][1]["gap"] == 1.0
    assert rj["results"][-1]["place"] == "DNF" and rj["results"][-1]["gap"] == ""
    cl = json.loads((out / "classifications.json").read_text())
    assert cl["source"] == "uci" and {k: len(v) for k, v in cl["tables"].items()} == {"sta": 155, "gc": 150}
    assert rep.n_classified == 150 and rep.n_abandons == 5 and rep.winner == "BRENNER Marco"
    assert rep.provider == "uci" and rep.pages["stage"]["event_code"] == "D2EV374857"


def test_stage14_accounting_and_gap_parsing(campaign):
    rows = ui.parse_rider_results(json.loads((UCI / "stage.json").read_text()), "stage")
    statuses = [r.status for r in rows]
    assert statuses.count("classified") == 150 and statuses.count("DNF") == 4 and statuses.count("DNS") == 1
    assert rows[0].absolute_seconds == 15309.0 and rows[0].gap_seconds == 0.0
    assert rows[1].gap_seconds == 1.0 and rows[1].result_raw == "+1"                 # one-second gap
    assert rows[149].gap_seconds == 2446.0 and rows[149].result_raw == "+40:46"      # multi-minute gap
    gc = ui.parse_rider_results(json.loads((UCI / "gc.json").read_text()), "gc")
    assert gc[0].absolute_seconds == 49 * 3600 + 28 * 60 + 12 and gc[1].gap_seconds == 126.0 and gc[-1].gap_seconds == 4 * 3600 + 40 * 60 + 59
    assert ui.parse_result_value("") == (None, None, True)
    assert ui.parse_result_value("+1:02:03") == (3723.0, None, False)
    assert ui.parse_result_value("4:15:09") == (None, 15309.0, False)
    assert ui.parse_result_value("DNF") == (None, None, False)
    assert ui._status_of(None, "OTL") == ("OTL", None) and ui._status_of("7", "+3") == ("classified", 7)
    assert ui._status_of(None, "DSQ") == ("DSQ", None) and ui._status_of(None, "wat") == ("?", None)


def test_identity_policy(campaign):
    rep = _ingest(campaign, write=False)
    by_name = {i["uci_name"]: i for i in rep.identities}
    exact = by_name["BRENNER Marco"]
    assert exact["accepted"] and exact["confidence"] == 0.99 and "exact normalised name" in exact["evidence"]
    ext = by_name["BUITRAGO SANCHEZ Santiago"]
    assert ext["accepted"] and ext["confidence"] == 0.97 and "surname extended" in ext["evidence"] and ext["fc_rider_id"] == "81835"
    assert by_name["SAMITIER SAMITIER Sergio"]["accepted"] and by_name["SOSA CUERVO Ivan Ramiro"]["fc_rider_id"] == "61639"
    assert by_name["NORSGAARD Mathias"]["accepted"] and by_name["NORSGAARD Mathias"]["fc_rider_id"] == "38481"
    for n in ("HAMILTON Christopher", "SCHULTZ Nicholas", "NIELSEN Magnus", "MULUEBERHAN Henok", "JENSEN Mattias Skjelmose Jennow"):
        assert by_name[n]["accepted"] and by_name[n]["via_alias"]
    # without the aliases those five are proposals, never acceptances, and the ingest rejects
    rep2 = ui.ingest(campaign, "stage_14", crosswalk_csv=campaign / "rider_crosswalk.csv", aliases_csv=campaign / "nope.csv", write=False)
    assert not rep2.ok and {c["name"] for c in rep2.failing} == {"crosswalk_top", "crosswalk_all_rows"}   # Skjelmose sits in the GC top 20
    unres = {u["uci_name"]: u for u in rep2.unresolved}
    assert set(unres) == {"HAMILTON Christopher", "SCHULTZ Nicholas", "NIELSEN Magnus", "MULUEBERHAN Henok", "JENSEN Mattias Skjelmose Jennow"}
    assert unres["HAMILTON Christopher"]["best"]["fc_name"] == "Hamilton Chris" and unres["HAMILTON Christopher"]["best"]["confidence"] < 0.97
    assert unres["NIELSEN Magnus"]["best"]["fc_rider_id"] is None            # given name + team only is never enough
    props = {p["pcs_name"]: p for p in rep2.proposals}
    assert props["HAMILTON Christopher"]["pcs_slug"] == "uci:hamilton|christopher" and props["HAMILTON Christopher"]["status"] == "proposed"
    assert props["HAMILTON Christopher"]["evidence"].startswith("source=uci;") and props["HAMILTON Christopher"]["author"] == "agent"
    assert not (campaign / "results" / "stage_14" / "results.csv").exists()   # nothing partial written


def _rename_rider(campaign, old_last: str, new_last: str) -> None:
    """Rename a rider consistently in stage.json (results + podium) and gc.json."""
    for f in ("stage.json", "gc.json"):
        def fn(d):
            for r in d["results"]:
                if r["values"].get("lastname") == old_last:
                    r["values"]["lastname"] = new_last
            for p in (d.get("podium") or {}).get("podium") or []:
                if p.get("lastname") == old_last:
                    p["lastname"] = new_last
        _edit_json(campaign / "results/stage_14/uci" / f, fn)


def test_identity_top15_gate_and_confirm_cli(campaign, tmp_path):
    """A top-15 rider whose surname the roster does not know fails crosswalk_top; a human alias fixes it."""
    _rename_rider(campaign, "SOSA CUERVO", "SOMEONEELSE")            # stage place 4
    rep = _ingest(campaign, write=False)
    assert not rep.ok and "crosswalk_top" in [c["name"] for c in rep.failing]
    top = next(c for c in rep.failing if c["name"] == "crosswalk_top")["detail"]["stage_top15_unresolved"]
    assert top[0]["uci_name"] == "SOMEONEELSE Ivan Ramiro" and top[0]["best"]["fc_rider_id"] is None
    assert ident.main(["confirm", "--lastname", "SOMEONEELSE", "--firstname", "Ivan Ramiro", "--fc-rider-id", "61639",
                       "--fc-name", "Sosa Ivan", "--birth-year", "1997", "--by", "test", "--aliases", str(campaign / "uci_aliases.csv")]) == 0
    rep = _ingest(campaign)
    assert rep.ok, rep.failing
    assert (campaign / "results/stage_14/results.csv").read_bytes() == (CAMPAIGN / "expected/stage_14/results.csv").read_bytes()


@pytest.mark.parametrize("name,mutate,check", [
    ("podium_mismatch", lambda d: d["podium"]["podium"][0].update({"lastname": "NOBODY"}), "podium"),
    ("duplicate_rank", lambda d: d["results"][5]["values"].update({"rank": "5"}), "ranks_contiguous_unique"),
    ("missing_winner_time", lambda d: d["results"][0]["values"].update({"result": "+0"}), "winner_time"),
    ("non_monotone_gap", lambda d: d["results"][10]["values"].update({"result": "+0:30"}), "gaps"),
    ("unknown_status", lambda d: d["results"][152]["values"].update({"result": "ABANDONED"}), "statuses"),
    ("duplicate_rider", lambda d: d["results"][7]["values"].update({"firstname": "Marco", "lastname": "BRENNER"}), "riders_unique"),
])
def test_validator_fault_cases(campaign, name, mutate, check):
    _edit_json(campaign / "results/stage_14/uci/stage.json", mutate)
    rep = _ingest(campaign)
    assert not rep.ok and check in [c["name"] for c in rep.failing], (name, rep.failing)
    assert not (campaign / "results/stage_14/results.csv").exists()


def test_a_bad_optional_classification_page_is_a_warning_not_a_rejection(campaign):
    uci_dir = campaign / "results/stage_14/uci"
    (uci_dir / "kom.json").write_text("<html>502 Bad Gateway</html>", encoding="utf-8")
    _edit_json(uci_dir / "uci_raw.json", lambda d: d["pages"]["kom"].update({"file": "kom.json", "http_status": 502}))
    rep = _ingest(campaign)
    assert rep.ok, rep.failing
    assert any(w.startswith("kom: optional classification page unusable") for w in rep.warnings)
    checks = {c.name: c for c in rep.checks}
    assert checks["responses_ok"].detail["dropped_optional"] == ["kom"]
    # the required pages still reject
    (uci_dir / "stage.json").write_text("<html>502</html>", encoding="utf-8")
    rep = _ingest(campaign)
    assert not rep.ok and "responses_ok" in [c["name"] for c in rep.failing]


def test_malformed_json_missing_required_and_wrong_competition(campaign):
    (campaign / "results/stage_14/uci/gc.json").write_text("{not json", encoding="utf-8")
    rep = _ingest(campaign)
    assert not rep.ok and "responses_ok" in [c["name"] for c in rep.failing]
    (campaign / "results/stage_14/uci/gc.json").unlink()
    rep = _ingest(campaign)
    assert not rep.ok and rep.failing[0]["name"] == "capture_present" and rep.failing[0]["detail"]["missing_required"] == ["gc"]
    shutil.rmtree(campaign / "results/stage_14/uci")
    shutil.copytree(UCI, campaign / "results/stage_14/uci")
    _edit_json(campaign / "results/stage_14/uci/uci_raw.json", lambda d: d["competition"].update({"year": 2025}))
    rep = _ingest(campaign)
    assert not rep.ok and "competition_matches_campaign" in [c["name"] for c in rep.failing]
    _edit_json(campaign / "results/stage_14/uci/uci_raw.json", lambda d: d["competition"].update({"year": 2026}) or d["stage"].update({"label": "Stage 13"}))
    rep = _ingest(campaign)
    assert not rep.ok and "stage_in_schedule_and_results" in [c["name"] for c in rep.failing]


# ---------------------------------------------------------------------------
# driver: provider selection, provenance, fallback
# ---------------------------------------------------------------------------

def _run(campaign, tmp_path, *argv, today="2026-09-05"):
    base = ["--campaign", str(campaign), "--store", "fake", "--store-root", str(tmp_path / "store"),
            "--crosswalk", str(campaign / "rider_crosswalk.csv"), "--aliases", str(campaign / "uci_aliases.csv"), "--today", today]
    return drv.main([argv[0], *base, *argv[1:]])


def _out(capsys):
    return json.loads(capsys.readouterr().out)


def _ledger(tmp_path, table):
    p = tmp_path / "store" / "ledger" / f"{table}.jsonl"
    return [json.loads(ln) for ln in p.read_text().splitlines()] if p.exists() else []


def test_driver_plan_sees_uci_capture(campaign, tmp_path, capsys):
    assert _run(campaign, tmp_path, "plan") == 0
    st14 = next(u for u in _out(capsys)["units"] if u["unit"] == "stage_14")
    assert st14["has_uci"] and not st14["has_pcs"] and st14["due"] == ["settle"] and st14["flags"] == []
    assert st14["uci_competition_url"] == COMP_URL


def test_driver_ingest_uses_uci_and_records_provenance(campaign, tmp_path, capsys):
    assert _run(campaign, tmp_path, "ingest", "--unit", "stage_14") == 0
    out = _out(capsys)
    assert out["ingest"]["provider"] == "uci" and out["ingest"]["winner"] == "BRENNER Marco"
    rows = _ledger(tmp_path, "pcs_raw")
    assert {r["kind"] for r in rows} == {"uci:competition", "uci:stage", "uci:gc"}
    assert all(r["ingest_detail"]["provider"] == "uci" and r["ingest_verdict"] == "accepted" for r in rows)
    assert next(r for r in rows if r["kind"] == "uci:stage")["ingest_detail"]["event_code"] == "D2EV374857"
    steps = _ledger(tmp_path, "run_steps")
    assert any(s["step"] == "ingest" and s["detail"].get("provider") == "uci" for s in steps)
    assert (campaign / "results/stage_14/results.csv").read_bytes() == (CAMPAIGN / "expected/stage_14/results.csv").read_bytes()


def test_driver_settle_dry_run_prefers_uci_and_uploads_capture(campaign, tmp_path, capsys):
    shutil.copytree(PCS, campaign / "results" / "stage_14" / "pcs")            # both present: UCI wins, PCS untouched
    assert _run(campaign, tmp_path, "settle", "--unit", "stage_14", "--dry-run") == 0
    out = _out(capsys)
    assert out["acquire"]["provider"] == "uci" and out["acquire"]["fallback_reason"] is None and out["acquire"]["ran"] is False
    assert out["ingest"]["provider"] == "uci"
    assert any(k.endswith("results/stage_14/uci/stage.json") for k in out["upload"]["artifacts"])
    record = json.loads(Path(out["record"]).read_text())
    assert record["provider"] == "uci"


def test_driver_falls_back_to_pcs_with_a_recorded_reason(campaign, tmp_path, capsys):
    shutil.rmtree(campaign / "results" / "stage_14" / "uci")
    shutil.copytree(PCS, campaign / "results" / "stage_14" / "pcs")
    assert _run(campaign, tmp_path, "settle", "--unit", "stage_14", "--dry-run") == 0
    out = _out(capsys)
    assert out["acquire"]["provider"] == "pcs" and out["acquire"]["fallback_reason"] == "fallback: no uci capture"
    assert out["ingest"]["provider"] == "pcs"
    rows = _ledger(tmp_path, "pcs_raw")
    assert rows and all(r["ingest_detail"]["provider"] == "pcs" and ":" not in r["kind"] for r in rows)
    assert rows[0]["ingest_detail"]["fallback_reason"] == "fallback: no uci capture"


def test_driver_without_any_capture_asks_for_acquisition(campaign, tmp_path, capsys):
    shutil.rmtree(campaign / "results" / "stage_14" / "uci")
    assert _run(campaign, tmp_path, "settle", "--unit", "stage_14", "--dry-run") == 10
    out = _out(capsys)
    assert out["operator_task"]["kind"] == "acquisition_needed"
    assert "uci_acquire --competition-url " + COMP_URL in out["operator_task"]["detail"]["expected"]["uci"]
    # forcing pcs with no pages is also a waiting state, never an error
    assert _run(campaign, tmp_path, "settle", "--unit", "stage_14", "--dry-run", "--provider", "pcs") == 10


def test_driver_never_blends_providers_and_reports_uci_rejection(campaign, tmp_path, capsys):
    shutil.copytree(PCS, campaign / "results" / "stage_14" / "pcs")
    _edit_json(campaign / "results/stage_14/uci/stage.json", lambda d: d["podium"]["podium"][0].update({"lastname": "NOBODY"}))
    assert _run(campaign, tmp_path, "ingest", "--unit", "stage_14") == 10
    out = _out(capsys)
    task = out["operator_task"]
    assert task["kind"] == "ingest_failed" and task["detail"]["provider"] == "uci"
    assert [c["name"] for c in task["detail"]["checks"]] == ["podium"]
    assert not (campaign / "results/stage_14/results.csv").exists()        # no silent PCS blend after a UCI rejection


def test_uci_proposals_reach_the_store_as_agent_rows(campaign, tmp_path, capsys):
    (campaign / "uci_aliases.csv").unlink()
    assert _run(campaign, tmp_path, "ingest", "--unit", "stage_14") == 10
    props = _ledger(tmp_path, "crosswalk_proposals")
    assert len(props) == 5 and {p["status"] for p in props} == {"proposed"} and all(p["pcs_slug"].startswith("uci:") for p in props)
    assert {p["pcs_name"] for p in props} >= {"NIELSEN Magnus", "HAMILTON Christopher"}
    store = FakeStore(tmp_path / "store", role="agent")
    with pytest.raises(Exception):
        store.insert_crosswalk_proposals([{**props[0], "status": "confirmed"}])   # the agent can never confirm


def test_agent_specs_keep_the_boundary():
    root = Path(__file__).resolve().parents[3]
    import yaml
    spec = yaml.safe_load((root / "agents/managed/agents/uci-acquirer.agent.yaml").read_text())
    cfg = {c["name"]: c.get("enabled") for c in spec["tools"][0]["configs"]}
    assert spec["tools"][0]["default_config"]["enabled"] is False
    assert cfg == {"bash": True, "read": True, "glob": True}                     # no write, no web tools
    prompt = (root / "agents/managed/prompts/uci-acquirer.md").read_text()
    for phrase in ("never parse", "never guess", "no git", "publish nothing", "Do not use `curl`"):
        assert phrase.lower() in prompt.lower(), phrase
    coord = yaml.safe_load((root / "agents/managed/agents/nightly-coordinator.agent.yaml").read_text())
    assert "uci-acquirer" in coord["multiagent"]["agents"]
    env = yaml.safe_load((root / "agents/managed/environment.yaml").read_text())
    hosts = env["config"]["networking"]["allowed_hosts"]
    assert "www.uci.org" in hosts and env["config"]["networking"]["type"] == "limited"
    # the driver's UCI path contains no git invocation
    src = (root / "cycling_project/nightly/uci_acquire.py").read_text() + (root / "cycling_project/nightly/uci_ingest.py").read_text()
    assert "subprocess" not in src and "git" not in src.replace("digit", "").replace("legit", "")
