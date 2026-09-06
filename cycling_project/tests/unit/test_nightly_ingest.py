"""``nightly ingest``: PCS pages → FirstCycling-shaped archive, validated (chip H).

Fixtures: the Vuelta 2026 stage-14 PCS pages fetched ONCE from the Mac with a
plain ``requests`` client on 2026-09-06 (``fixtures/pcs/vuelta-2026-stage14``)
and a trimmed campaign (``fixtures/nightly/driver_stage14``) whose
``expected/stage_14`` holds the committed FirstCycling capture of the same
stage. The crosswalk fixture is the repo CSV plus the 12 pending proposals
marked human-confirmed (fixture only).
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest

from cycling_project.nightly import driver as drv
from cycling_project.nightly import pcs_ingest as pi

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
PCS = FIXTURES / "pcs" / "vuelta-2026-stage14"
CAMPAIGN = FIXTURES / "nightly" / "driver_stage14"


@pytest.fixture
def campaign(tmp_path):
    dst = tmp_path / "vuelta-2026"
    shutil.copytree(CAMPAIGN, dst)
    pcs = dst / "results" / "stage_14" / "pcs"
    shutil.copytree(PCS, pcs)
    return dst


def _ingest(campaign, **kw):
    return pi.ingest(campaign, "stage_14", crosswalk_csv=campaign / "rider_crosswalk.csv", **kw)


def _edit(path: Path, old: str, new: str, count: int = 1) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, old
    path.write_text(text.replace(old, new, count), encoding="utf-8")


def _resub(path: Path, pattern: str, repl: str, count: int = 1) -> None:
    """Regex edit of a verbatim PCS page (attribute whitespace varies: ``class="time ar " >``)."""
    text = path.read_text(encoding="utf-8")
    new_text, n = re.subn(pattern, repl, text, count=count, flags=re.S)
    assert n == count, pattern
    path.write_text(new_text, encoding="utf-8")


# ---------------------------------------------------------------------------
# the happy path: byte-compatible with the FirstCycling capture
# ---------------------------------------------------------------------------

def test_ingest_reproduces_committed_archive_bytewise(campaign):
    rep = _ingest(campaign)
    assert rep.ok, rep.failing
    assert [c.name for c in rep.checks if not c.ok] == []
    out = campaign / "results" / "stage_14"
    for name in ("results.csv", "gc.csv"):
        assert (out / name).read_bytes() == (CAMPAIGN / "expected" / "stage_14" / name).read_bytes(), name
    live = CAMPAIGN.parents[3] / "performance_eval" / "vuelta-2026" / "results" / "stage_14"
    if (live / "results.csv").exists():                      # the committed Vuelta archive itself
        assert (out / "results.csv").read_bytes() == (live / "results.csv").read_bytes()
        assert (out / "gc.csv").read_bytes() == (live / "gc.csv").read_bytes()
    rj = json.loads((out / "results.json").read_text())
    assert rj["race_time"] == 15309.0 and rj["n_results"] == 155 and rj["date"] == "2026-09-05"
    assert rj["results"][0]["name"] == "Brenner Marco" and rj["results"][0]["gap"] == 0
    assert rj["results"][1]["gap"] == 1.0 and rj["results"][-1]["place"] == "DNF" and rj["results"][-1]["gap"] == ""
    cl = json.loads((out / "classifications.json").read_text())
    assert {k: len(v) for k, v in cl["tables"].items()} == {"sta": 155, "gc": 150, "point": 86, "mountain": 52, "youth": 50, "team": 23}
    assert rep.n_classified == 150 and rep.n_abandons == 5 and rep.winner == "Brenner Marco"


def test_transposed_rider_links_are_resolved_from_bib_and_team(campaign):
    """PCS rendered GC rows 6/7, 15/16 and 29/30 with swapped rider links; bib + team column fix them."""
    rep = _ingest(campaign)
    assert rep.ok
    corrected = next(c for c in rep.checks if c.name == "rider_links").detail["transposed_corrected"]
    assert corrected == ["gc 6", "gc 7", "gc 15", "gc 16", "gc 29", "gc 30"]
    gc = (campaign / "results/stage_14/gc.csv").read_text().splitlines()
    assert gc[6].startswith("6,Omrzel Jakob,208369") and gc[7].startswith("7,Skjelmose Mattias,77103")


def test_dom_map_primitives():
    soup = pi._soup((PCS / "stage.html").read_text())
    tabs = pi.result_tabs(soup)
    assert pi.active_tab_label(soup) == "STAGE" and set(tabs) == {"STAGE", "GC", "POINTS", "KOM", "YOUTH", "TEAMS"}
    rows = pi.parse_rider_table(tabs["STAGE"]["table"])
    assert rows[0].rider_slug == "marco-brenner" and rows[0].gap_seconds == 0.0 and rows[0].team_slug == "tudor-pro-cycling-team-2026"
    same = next(r for r in rows if r.same_time)
    assert same.time_visible.startswith(",,") and same.gap_seconds == rows[same.index - 1].gap_seconds
    assert [r.status for r in rows[-5:]] == ["DNF", "DNF", "DNF", "DNF", "DNS"]
    start = pi.parse_startlist((PCS / "startlist.html").read_text())
    assert len(start) == 184 and sum(1 for s in start if s.status) == 34
    pog = next(s for s in start if s.rider_slug == "tadej-pogacar")
    assert (pog.status, pog.status_stage, pog.bib) == ("DNF", 8, "11")
    embed = pi.parse_embed_tables((PCS / "embed_top10.html").read_text())
    assert [r["name"] for r in embed[0][:3]] == ["BRENNER Marco", "BUITRAGO Santiago", "RODRÍGUEZ Cristián"]
    assert pi.parse_time_to_seconds("4:15:09") == 15309.0 and pi.parse_time_to_seconds("+1:02") == 62.0
    assert pi.parse_time_to_seconds(",,") is None and pi.parse_time_to_seconds("") is None


# ---------------------------------------------------------------------------
# validator fault cases — each rejected, nothing written
# ---------------------------------------------------------------------------

def _assert_rejected(campaign, rep, check_name):
    assert not rep.ok
    assert check_name in {c["name"] for c in rep.failing}, rep.failing
    out = campaign / "results" / "stage_14"
    assert not (out / "results.csv").exists() and not (out / "gc.csv").exists() and not (out / "results.json").exists()


def test_missing_rider_row_fails_row_count(campaign):
    page = campaign / "results/stage_14/pcs/stage.html"
    html = page.read_text(encoding="utf-8")
    # drop the 7th-placed rider's row from the STAGE table (Nordhagen)
    m = re.search(r"<tr>\s*<td[^>]*>7</td>.*?</tr>", html, flags=re.S)
    assert m and "jorgen-nordhagen" in m.group(0), (m.group(0)[:200] if m else None)
    page.write_text(html.replace(m.group(0), "", 1), encoding="utf-8")
    rep = _ingest(campaign)
    _assert_rejected(campaign, rep, "row_count")
    detail = next(c for c in rep.failing if c["name"] == "row_count")["detail"]
    assert detail["rows"] == 154 and detail["expected"] == 155


def test_non_monotone_gap_fails(campaign):
    page = campaign / "results/stage_14/pcs/stage.html"
    # 3rd place Rodríguez: 0:11 → 0:00 (behind a 0:01 second place)
    _resub(page, r'<font>0:11</font>\s*<span class="hide">0:11</span>', '<font>0:00</font><span class="hide">0:00</span>')
    rep = _ingest(campaign)
    _assert_rejected(campaign, rep, "gaps")
    assert any("place 3" in p for p in next(c for c in rep.failing if c["name"] == "gaps")["detail"]["problems"])


def test_podium_mismatch_fails(campaign):
    page = campaign / "results/stage_14/pcs/embed_top10.html"
    _edit(page, "BRENNER Marco", "BUITRAGO Santiago")
    rep = _ingest(campaign)
    _assert_rejected(campaign, rep, "podium")


def test_sub_threshold_crosswalk_fails_top15(campaign):
    """Sosa (4th) only has a 0.94 proposal once the fixture's confirmations are removed."""
    xw = campaign / "rider_crosswalk.csv"
    lines = [ln for ln in xw.read_text().splitlines() if "test_fixture_confirmed" not in ln]
    xw.write_text("\n".join(lines) + "\n")
    rep = _ingest(campaign)
    _assert_rejected(campaign, rep, "crosswalk_top")
    detail = next(c for c in rep.failing if c["name"] == "crosswalk_top")["detail"]
    assert any(u["pcs_slug"] == "ivan-ramiro-sosa" and u["place"] == "4" for u in detail["stage_top15_unresolved"])
    assert detail["threshold"] == pytest.approx(0.97)
    assert rep.unresolved and all("pcs_slug" in u for u in rep.unresolved)


def test_unresolvable_transposition_fails_closed(campaign):
    """Break the bib of a transposed GC row so the startlist cannot resolve it → no rider → rejected."""
    page = campaign / "results/stage_14/pcs/gc.html"
    html = page.read_text(encoding="utf-8")
    gc_start = html.rfind('data-id="340295"')                       # the GC resTab div (every page carries every tab)
    assert gc_start > 0
    m = re.compile(r'<tr>\s*<td[^>]*>6</td>.*?<td class="bibs[^"]*"\s*>76</td>', re.S).search(html, gc_start)
    assert m and "mattias-skjelmose" in html[m.end():m.end() + 1500]
    bib_cell = re.search(r'<td class="bibs[^"]*"\s*>76</td>', m.group(0)).group(0)
    page.write_text(html[:m.start()] + m.group(0).replace(bib_cell, bib_cell.replace(">76<", ">999<")) + html[m.end():],
                    encoding="utf-8")
    rep = _ingest(campaign)
    _assert_rejected(campaign, rep, "rider_links")


def test_missing_page_fails_closed(campaign):
    (campaign / "results/stage_14/pcs/embed_top10.html").unlink()
    rep = _ingest(campaign)
    _assert_rejected(campaign, rep, "pages_present")


# ---------------------------------------------------------------------------
# through the driver: exit 10 with the failing checks in the operator task
# ---------------------------------------------------------------------------

def test_driver_ingest_command_exits_10_listing_checks(campaign, tmp_path, capsys):
    page = campaign / "results/stage_14/pcs/embed_top10.html"
    _edit(page, "BRENNER Marco", "BUITRAGO Santiago")
    code = drv.main(["ingest", "--campaign", str(campaign), "--unit", "stage_14", "--dry-run",
                     "--store-root", str(tmp_path / "store"), "--crosswalk", str(campaign / "rider_crosswalk.csv")])
    out = json.loads(capsys.readouterr().out)
    assert code == 10 and out["status"] == "waiting_for_input"
    task = out["operator_task"]
    assert task["kind"] == "ingest_failed" and task["author"] == "agent"
    assert "podium" in {c["name"] for c in task["detail"]["checks"]}
    assert not (campaign / "results/stage_14/results.csv").exists()
    ledger = json.loads("[" + ",".join((tmp_path / "store/ledger/pcs_raw.jsonl").read_text().splitlines()) + "]")
    assert len(ledger) == 6 and {r["ingest_verdict"] for r in ledger} == {"rejected"}


def test_driver_ingest_command_accepts_and_records_pcs_raw(campaign, tmp_path, capsys):
    code = drv.main(["ingest", "--campaign", str(campaign), "--unit", "stage_14", "--dry-run",
                     "--store-root", str(tmp_path / "store"), "--crosswalk", str(campaign / "rider_crosswalk.csv")])
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and out["status"] == "done" and out["ingest"]["winner"] == "Brenner Marco"
    ledger = [json.loads(ln) for ln in (tmp_path / "store/ledger/pcs_raw.jsonl").read_text().splitlines()]
    assert {r["kind"] for r in ledger} == set(pi.PAGE_FILES) - {"youth"}
    assert {r["ingest_verdict"] for r in ledger} == {"accepted"}
    assert all(r["source_url"].startswith("https://www.procyclingstats.com/") for r in ledger)
