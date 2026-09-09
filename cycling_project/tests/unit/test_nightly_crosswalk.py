"""Rider crosswalk: matcher confidence rules, CSV mirror, trust boundary.

The rules under test (NIGHTLY_AGENT_WORKFLOW.md §2.8, AGENT_DESIGN.md §3.4):
auto-accept ≥ 0.97 only for (exact normalised name + birth year) or (exact
name unique in the DB + same team); everything else is a proposal; the
agent-facing functions never confirm.
"""

import ast
import inspect
import sqlite3
from pathlib import Path

import pytest

from cycling_project.nightly import crosswalk as cw
from cycling_project.nightly.crosswalk import (
    AUTO_ACCEPT, MatchResult, PcsRow, RiderIndex, RiderRecord, coverage_report, derive_pcs_slug,
    load_pcs_startlist_html, match_row, merge_crosswalk, name_key, propose_matches,
    read_crosswalk_csv, write_crosswalk_csv,
)
from cycling_project.nightly.store_local import JsonlStore

FIXTURE_STARTLIST = Path(__file__).resolve().parents[1] / "fixtures" / "pcs" / "vuelta-2026-startlist.html"


def rider(i, fc, name, by=None, teams=()):
    return RiderRecord(i, str(fc), name, by, frozenset(teams))


@pytest.fixture
def index():
    return RiderIndex([
        rider(1, 18655, "Roglic Primoz", 1989, {"Red Bull-BORA-hansgrohe"}),
        rider(2, 75998, "Fisher-Black Finn", 2001, {"Red Bull-BORA-hansgrohe"}),
        rider(3, 37421, "Gee Derek", 1997, {"Israel-Premier Tech"}),
        rider(4, 10990, "Martin Guillaume", 1993, {"Groupama-FDJ"}),
        rider(5, 76065, "Plapp Lucas", 2000, {"Team Jayco AlUla"}),
        # homonyms: two riders with the same name
        rider(6, 501, "Garcia Carlos", 1998, {"Movistar Team"}),
        rider(7, 502, "Garcia Carlos", 1991, {"Equipo Kern Pharma"}),
        # rider with no birth year in the DB
        rider(8, 601, "Novak Domen", None, {"UAE Team Emirates-XRG"}),
        rider(9, 701, "Barta William", 1996, {"Tudor Pro Cycling Team"}),
        rider(10, 801, "Sosa Ivan", 1997, {"Equipo Kern Pharma"}),
    ])


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

def test_name_key_strips_accents_case_hyphens_and_order():
    assert name_key("ROGLIČ Primož") == name_key("Roglic Primoz") == "primoz roglic"
    assert name_key("FISHER-BLACK Finn") == name_key("Fisher Black Finn")
    assert name_key("Wærenskjold Søren") == "soren waerenskjold"


def test_derive_pcs_slug_is_first_last():
    assert derive_pcs_slug("Roglic Primoz") == "primoz-roglic"
    assert derive_pcs_slug("Fisher-Black Finn") == "finn-fisher-black"
    assert derive_pcs_slug("Martin Muñoz Jose Maria") == "jose-maria-martin-munoz"


# ---------------------------------------------------------------------------
# Confidence rules
# ---------------------------------------------------------------------------

def test_exact_name_plus_birth_year_auto_accepts(index):
    m = match_row(PcsRow("primoz-roglic", "ROGLIČ Primož", "Some Other Team", birth_year=1989), index)
    assert m.rider.fc_rider_id == "18655" and m.auto_accept and m.confidence >= AUTO_ACCEPT


def test_exact_unique_name_plus_team_auto_accepts_without_birth_year(index):
    m = match_row(PcsRow("finn-fisher-black", "FISHER-BLACK Finn", "Red Bull - BORA - hansgrohe (WT)"), index)
    assert m.rider.fc_rider_id == "75998" and m.auto_accept and m.confidence == pytest.approx(0.97)


def test_exact_unique_name_without_team_or_year_is_a_proposal(index):
    m = match_row(PcsRow("domen-novak", "NOVAK Domen"), index)
    assert m.rider.fc_rider_id == "601" and not m.auto_accept and m.confidence == pytest.approx(0.90)


def test_exact_name_birth_year_mismatch_is_flagged_not_accepted(index):
    m = match_row(PcsRow("primoz-roglic", "ROGLIČ Primož", "Red Bull - BORA - hansgrohe", birth_year=1990), index)
    assert not m.auto_accept and m.confidence < 0.5
    assert any("MISMATCH" in r for r in m.reasons)


@pytest.mark.parametrize("pcs_name,expected_fc", [
    ("GEE-WEST Derek", "37421"),            # FirstCycling drift Gee → Gee-West
    ("MARTIN-GUYONNET Guillaume", "10990"),  # Martin → Martin-Guyonnet
    ("PLAPP Luke", "76065"),                 # Plapp Lucas / Luke
])
def test_known_drift_aliases_count_as_exact(index, pcs_name, expected_fc):
    m = match_row(PcsRow("x", pcs_name, birth_year={"37421": 1997, "10990": 1993, "76065": 2000}[expected_fc]), index)
    assert m.rider.fc_rider_id == expected_fc and m.auto_accept


def test_unknown_hyphen_drift_is_only_a_proposal(index):
    # A subset overlap that is NOT in the alias table: same birth year and
    # team still do not clear the bar.
    m = match_row(PcsRow("ivan-ramiro-sosa", "SOSA Iván Ramiro", "Equipo Kern Pharma (PRT)", birth_year=1997), index)
    assert m.rider.fc_rider_id == "801" and not m.auto_accept and m.confidence < AUTO_ACCEPT
    assert any("partial" in r for r in m.reasons)


def test_homonym_without_discriminator_has_no_pick(index):
    m = match_row(PcsRow("carlos-garcia", "GARCÍA Carlos"), index)
    assert m.rider is None and not m.auto_accept and len(m.alternates) == 2


def test_homonym_resolved_by_birth_year_auto_accepts(index):
    m = match_row(PcsRow("carlos-garcia", "GARCÍA Carlos", birth_year=1991), index)
    assert m.rider.fc_rider_id == "502" and m.auto_accept


def test_homonym_resolved_by_team_only_is_a_proposal(index):
    # Spec: the team rule requires the name to be unique in the DB.
    m = match_row(PcsRow("carlos-garcia", "GARCÍA Carlos", "Movistar Team"), index)
    assert m.rider.fc_rider_id == "501" and not m.auto_accept and m.confidence == pytest.approx(0.85)


def test_nickname_never_auto_accepts(index):
    m = match_row(PcsRow("william-barta", "BARTA Will", "Tudor Pro Cycling Team", birth_year=1996), index)
    assert m.rider.fc_rider_id == "701" and not m.auto_accept and m.confidence <= 0.95


def test_bib_team_hint_yields_named_proposal_only(index):
    m = match_row(PcsRow("edward-dunbar", "DUNBAR Eddie", "Team Jayco AlUla", hint_fc_id="76065"), index)
    assert m.rider.fc_rider_id == "76065" and not m.auto_accept and m.confidence < 0.9
    assert m.confidence > 0  # a proposal with a candidate, not "no candidate"


def test_no_candidate(index):
    m = match_row(PcsRow("nobody", "NOBODY Anyone"), index)
    assert m.rider is None and m.confidence == 0.0


# ---------------------------------------------------------------------------
# PCS startlist fixture (fetched once from this Mac, 2026-09-05)
# ---------------------------------------------------------------------------

def test_pcs_startlist_fixture_parses_184_riders():
    rows = load_pcs_startlist_html(FIXTURE_STARTLIST)
    assert len(rows) == 184
    roglic = next(r for r in rows if r.slug == "primoz-roglic")
    assert roglic.name == "ROGLIČ Primož" and roglic.bib == "1"
    assert "Red Bull" in roglic.team
    assert len({r.slug for r in rows}) == 184


# ---------------------------------------------------------------------------
# CSV mirror + merge
# ---------------------------------------------------------------------------

def _row(slug, fc, conf="0.99", confirmed=""):
    return {"pcs_slug": slug, "fc_rider_id": fc, "internal_rider_id": 1, "pcs_name": "X", "fc_name": "Y",
            "birth_year": 1990, "confidence": conf, "source": "pcs_startlist", "confirmed_by": confirmed,
            "created_at": "2026-09-05T00:00:00+00:00"}


def test_csv_round_trip(tmp_path):
    path = tmp_path / "rider_crosswalk.csv"
    rows = [_row("b-rider", "2"), _row("a-rider", "1", confirmed="matt")]
    write_crosswalk_csv(rows, path)
    back = read_crosswalk_csv(path)
    assert [r["pcs_slug"] for r in back] == ["a-rider", "b-rider"]  # deterministic order
    assert back[0]["confirmed_by"] == "matt" and back[1]["fc_rider_id"] == "2"
    assert list(back[0].keys()) == cw.CSV_FIELDS
    assert b"\r\n" not in path.read_bytes()
    # idempotent
    write_crosswalk_csv(back, path)
    assert read_crosswalk_csv(path) == back


def test_merge_repo_copy_wins_on_conflict():
    repo = [_row("a", "1")]
    incoming = [_row("a", "999", conf="1.00", confirmed="someone"), _row("b", "2")]
    merged, conflicts = merge_crosswalk(repo, incoming, repo_wins=True)
    by = {r["pcs_slug"]: r for r in merged}
    assert by["a"]["fc_rider_id"] == "1" and by["b"]["fc_rider_id"] == "2"
    assert conflicts and conflicts[0]["pcs_slug"] == "a"


def test_merge_same_rider_refreshes_on_confirmation():
    merged, conflicts = merge_crosswalk([_row("a", "1", conf="0.97")], [_row("a", "1", conf="0.90", confirmed="matt")])
    assert not conflicts and merged[0]["confirmed_by"] == "matt"


# ---------------------------------------------------------------------------
# Proposals, coverage, sqlite loader
# ---------------------------------------------------------------------------

def test_propose_inserts_only_non_accepted_rows_and_one_task(index, tmp_path):
    store = JsonlStore(runs_dir=tmp_path, role="agent")
    results = [
        match_row(PcsRow("primoz-roglic", "ROGLIČ Primož", birth_year=1989), index),   # accepted
        match_row(PcsRow("carlos-garcia", "GARCÍA Carlos"), index),                   # homonym → proposal
        match_row(PcsRow("domen-novak", "NOVAK Domen"), index),                        # 0.90 → proposal
    ]
    inserted, task = propose_matches(results, store, campaign="vuelta-2026")
    assert len(inserted) == 2 and task["kind"] == "crosswalk_proposals"
    assert {p["pcs_slug"] for p in store.rows["crosswalk_proposals"]} == {"carlos-garcia", "domen-novak"}
    assert (tmp_path / "operator_tasks.jsonl").exists() and (tmp_path / "crosswalk_proposals.jsonl").exists()
    assert "crosswalk" not in store.rows  # nothing confirmed


def test_agent_store_cannot_confirm(tmp_path):
    store = JsonlStore(runs_dir=tmp_path, role="agent")
    with pytest.raises(PermissionError):
        store.upsert_crosswalk({"pcs_slug": "x", "fc_rider_id": "1"})
    with pytest.raises(PermissionError):
        store.insert("crosswalk", {"pcs_slug": "x"})


def test_confirm_refuses_under_agent_role(index, tmp_path, monkeypatch):
    monkeypatch.setenv("NIGHTLY_ROLE", "agent")
    store = JsonlStore(runs_dir=tmp_path, role="operator")
    with pytest.raises(PermissionError):
        cw.confirm("primoz-roglic", "18655", "matt", index=index, store=store, csv_path=tmp_path / "x.csv")


def test_confirm_writes_csv_and_operator_store(index, tmp_path, monkeypatch):
    monkeypatch.delenv("NIGHTLY_ROLE", raising=False)
    store = JsonlStore(runs_dir=tmp_path, role="operator")
    csv_path = tmp_path / "rider_crosswalk.csv"
    row = cw.confirm("carlos-garcia", "502", "matt", index=index, store=store, csv_path=csv_path)
    assert row["confirmed_by"] == "matt" and row["source"] == "human"
    assert read_crosswalk_csv(csv_path)[0]["fc_rider_id"] == "502"
    assert store.rows["crosswalk"][0]["pcs_slug"] == "carlos-garcia"


def test_coverage_report_counts_only_accepted_or_confirmed():
    field_rows = [{"fc_rider_id": "1", "fc_name": "A", "team": "T", "bib": "1"},
                  {"fc_rider_id": "2", "fc_name": "B", "team": "T", "bib": "2"},
                  {"fc_rider_id": "3", "fc_name": "C", "team": "T", "bib": "3"}]
    xw = [_row("a", "1", conf="0.99"), _row("b", "2", conf="0.90"), _row("c", "3", conf="0.50", confirmed="matt")]
    rep = coverage_report(field_rows, xw, [PcsRow("a", "A"), PcsRow("b", "B"), PcsRow("z", "Z")])
    assert rep["matched"] == 2 and rep["unmatched"] == 1
    assert rep["unmatched_riders"][0]["fc_rider_id"] == "2"
    assert {p["pcs_slug"] for p in rep["pcs_unmatched"]} == {"b", "z"}


def test_rider_index_from_sqlite_uses_cached_startlist_teams(tmp_path):
    db = tmp_path / "t.db"
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE riders (id INTEGER PRIMARY KEY, fc_rider_id TEXT UNIQUE NOT NULL, name TEXT NOT NULL, birth_year INTEGER);
        CREATE TABLE teams (id INTEGER PRIMARY KEY, fc_team_id TEXT, name TEXT);
        CREATE TABLE rider_team_history (id INTEGER PRIMARY KEY, rider_id INTEGER, team_id INTEGER, year INTEGER);
        CREATE TABLE cached_start_lists (id INTEGER PRIMARY KEY, fc_race_id TEXT, year INTEGER, rider_fc_id TEXT,
            rider_name TEXT, team_name TEXT, team_fc_id TEXT, bib_number TEXT);
        INSERT INTO riders VALUES (1, '18655', 'Roglic Primoz', 1989), (2, '999', 'Roglic Primoz', NULL);
        INSERT INTO teams VALUES (1, 't1', 'Old Team');
        INSERT INTO rider_team_history VALUES (1, 2, 1, 2024);
        INSERT INTO cached_start_lists VALUES (1, '23', 2026, '18655', 'Roglic Primoz', 'Red Bull-BORA-hansgrohe', 'x', '1');
    """)
    conn.commit(); conn.close()
    idx = RiderIndex.from_sqlite(db, fc_race_id="23", year=2026)
    assert len(idx) == 2
    assert "Red Bull-BORA-hansgrohe" in idx.by_fc_id["18655"].teams
    assert "Old Team" in idx.by_fc_id["999"].teams
    # homonym pair without birth-year discriminator → proposal, not accept
    m = match_row(PcsRow("primoz-roglic", "ROGLIČ Primož", "Red Bull - BORA - hansgrohe"), idx)
    assert not m.auto_accept


# ---------------------------------------------------------------------------
# Trust boundary: agent-facing code never calls confirm
# ---------------------------------------------------------------------------

AGENT_FACING = ("cmd_seed", "cmd_propose", "cmd_coverage", "cmd_export", "cmd_import", "match_row",
                "match_startlist", "propose_matches", "load_startlist", "coverage_report", "seed",
                "propose", "coverage")
FORBIDDEN_CALLS = {"confirm", "upsert_crosswalk", "_require_operator_context"}


def _called_names(fn_node: ast.FunctionDef) -> set[str]:
    out = set()
    for node in ast.walk(fn_node):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name):
                out.add(f.id)
            elif isinstance(f, ast.Attribute):
                out.add(f.attr)
    return out


def test_agent_facing_functions_never_confirm():
    from cycling_project.nightly import reconcile
    for module in (cw, reconcile):
        tree = ast.parse(inspect.getsource(module))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name not in {"confirm", "cmd_confirm"}:
                hit = _called_names(node) & FORBIDDEN_CALLS
                assert not hit, f"{module.__name__}.{node.name} calls {hit}"
    # and the agent-facing names actually exist
    for name in AGENT_FACING:
        assert hasattr(cw, name) or name in {"seed", "propose", "coverage"}


def test_reconcile_module_only_uses_agent_store_role():
    from cycling_project.nightly import reconcile
    src = inspect.getsource(reconcile)
    assert 'role="operator"' not in src and "upsert_crosswalk" not in src
