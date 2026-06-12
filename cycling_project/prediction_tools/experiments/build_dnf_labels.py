"""
Build per-(competition_id, rider_id) DNF labels from the legacy scraped pickles.

rider_results contains ONLY finishers: migrate_races.insert_results skips any
result row whose place is not numeric ('DNF', 'DNS', 'OOT', 'DSQ', ...). The
pickles therefore remain the only per-rider source of non-finisher records.
This script walks the pickle corpus read-only, matches every result row back
to DB ids, and writes a label table:

    started=1, dnf=0   numeric place (official finisher)
    started=1, dnf=1   DNF / OTL / OOT / DSQ / other non-DNS status
    started=0, dnf=NA  DNS (never started -> excluded from model labels,
                       kept in the file for auditability)

Semantics per competition_type:
    one_day  row = that day's race sheet (DNS = skipped the race)
    stage    row = that stage's sheet (DNS = started the race but not
                   this stage -> not a starter OF THIS competition)
    gc       row = the race-level sheet (DNF = abandoned the stage race at
                   any point; duplicates the per-stage DNF events, so
                   rider-history features must use one_day+stage rows only)

Matching:
    competitions: by exact URL (unique, non-null in DB) + competition_type
    riders:       by fc_rider_id (migration's 'unknown_<name>' fallback
                   replicated for rows without an id)

Output: experiments/dnf_labels_<ts>.csv.gz + coverage report JSON.

Usage:
    uv run python -m cycling_project.prediction_tools.experiments.build_dnf_labels
"""

import gzip
import json
import os
import pickle
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd

from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

DB_PATH = (
    Path(__file__).parent.parent.parent
    / "webscrape_tools" / "database" / "database" / "cycling_races.db"
)
OUT_DIR = Path("experiments")

# Statuses observed on FirstCycling result sheets. Anything non-numeric and
# not DNS is treated as started-but-not-classified (positive label). The raw
# status is kept in the file so this decision is auditable.
DNS_STATUSES = {"DNS"}


def _scraped_dir() -> Path:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    return Path(os.getenv("SCRAPED_DATA_DIR") or os.getenv("DB_PATH")
                or str(Path.home() / "cycling_data" / "scraped_data"))


def _load_lookups(conn):
    comp_by_url = {}
    for cid, url, ctype, date, stage_no in conn.execute(
        "SELECT id, url, competition_type, date, stage_number FROM competitions"
    ):
        comp_by_url[(url, ctype)] = (cid, date, stage_no)
    rider_by_fc = {fc: rid for rid, fc in conn.execute("SELECT id, fc_rider_id FROM riders")}
    race_meta = {}
    for rid, fc, year, cat in conn.execute("SELECT id, fc_race_id, year, category FROM races"):
        race_meta[(str(fc), int(year), cat)] = rid
    return comp_by_url, rider_by_fc, race_meta


def _classify(place_raw) -> tuple:
    """-> (status_raw, started, dnf, place) ; started/dnf None = unknown row."""
    if place_raw is None:
        return ("NONE", None, None, None)
    s = str(place_raw).strip()
    if s == "":
        return ("EMPTY", None, None, None)
    if s.isdigit():
        return ("FIN", 1, 0, int(s))
    su = s.upper()
    if su in DNS_STATUSES:
        return (su, 0, None, None)
    return (su, 1, 1, None)


def _rider_key(row: dict) -> str:
    fc = row.get("rider_id")
    if fc:
        return str(fc)
    name = row.get("name") or ""
    return f"unknown_{name.replace(' ', '_')}"  # migration fallback convention


def extract_rows(results, comp_key, comp_by_url, rider_by_fc, counters,
                 fc_race_id, year, category):
    cid_info = comp_by_url.get(comp_key)
    if cid_info is None:
        counters["unmatched_competitions"] += 1
        return []
    cid, date, stage_no = cid_info
    ctype = comp_key[1]
    rows = []
    for r in results:
        if not isinstance(r, dict):
            counters["non_dict_result_rows"] += 1
            continue
        status, started, dnf, place = _classify(r.get("place"))
        counters["status_" + status] += 1
        fc_rid = _rider_key(r)
        rid = rider_by_fc.get(fc_rid)
        if rid is None:
            counters["unmatched_riders"] += 1
            if started == 1 and dnf == 1:
                counters["unmatched_dnf_riders"] += 1
        rows.append((cid, rid, fc_rid, status, started, dnf, place,
                     ctype, date, category, str(fc_race_id), year, stage_no))
    return rows


def main():
    started_at = datetime.now()
    src = _scraped_dir()
    print(f"Scraped pickle dir: {src}", flush=True)
    conn = sqlite3.connect(str(DB_PATH))
    comp_by_url, rider_by_fc, race_meta = _load_lookups(conn)
    print(f"Lookups: {len(comp_by_url):,} competitions, {len(rider_by_fc):,} riders",
          flush=True)

    counters = Counter()
    all_rows = []
    year_dirs = sorted(d for d in src.iterdir() if d.is_dir() and d.name.isdigit())
    for ydir in year_dirs:
        year = int(ydir.name)
        n_files = 0
        for cat in ("wt", "pro", "d1"):
            cdir = ydir / cat
            if not cdir.exists():
                continue
            for pkl in sorted(cdir.glob("*.pkl")):
                n_files += 1
                try:
                    with open(pkl, "rb") as f:
                        race = pickle.load(f)
                except Exception as exc:
                    counters["pickle_errors"] += 1
                    logger.warning(f"Failed to load {pkl}: {exc}")
                    continue
                if race.stage_race:
                    if race.results:
                        all_rows += extract_rows(
                            race.results, (race.url, "gc"), comp_by_url,
                            rider_by_fc, counters, race.fc_race_id, year, cat)
                    for st in race.stages or []:
                        if st.name.strip().upper() == "GC":
                            continue
                        if st.results:
                            all_rows += extract_rows(
                                st.results, (st.url, "stage"), comp_by_url,
                                rider_by_fc, counters, race.fc_race_id, year, cat)
                else:
                    if race.results:
                        all_rows += extract_rows(
                            race.results, (race.url, "one_day"), comp_by_url,
                            rider_by_fc, counters, race.fc_race_id, year, cat)
        print(f"  {year}: {n_files} pickles -> {len(all_rows):,} rows total", flush=True)

    df = pd.DataFrame(all_rows, columns=[
        "competition_id", "rider_id", "rider_fc_id", "status_raw", "started",
        "dnf", "place", "competition_type", "competition_date", "race_category",
        "fc_race_id", "year", "stage_number",
    ])
    n_dupes = int(df.duplicated(subset=["competition_id", "rider_id", "rider_fc_id"]).sum())
    df = df.drop_duplicates(subset=["competition_id", "rider_id", "rider_fc_id"], keep="first")

    ts = started_at.strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(exist_ok=True)
    out_csv = OUT_DIR / f"dnf_labels_{ts}.csv.gz"
    with gzip.open(out_csv, "wt") as f:
        df.to_csv(f, index=False)
    print(f"\nWrote {len(df):,} rows ({n_dupes} dupes dropped) -> {out_csv}", flush=True)

    # ---------------- coverage report ----------------
    report = {"generated_at": started_at.isoformat(), "rows": int(len(df)),
              "dupes_dropped": n_dupes, "counters": dict(counters)}

    db_comps = pd.read_sql_query(
        """SELECT c.id AS competition_id, c.competition_type, c.date, r.category
           FROM competitions c JOIN races r ON c.race_id = r.id
           WHERE c.competition_type IN ('one_day','stage','gc')""", conn)
    db_comps["year"] = pd.to_datetime(db_comps["date"]).dt.year
    covered = set(df["competition_id"].unique())
    db_comps["covered"] = db_comps["competition_id"].isin(covered)

    cov = {}
    for lo in (2010, 2016):
        sub = db_comps[db_comps["year"] >= lo]
        cov[f"since_{lo}"] = {
            "db_competitions": int(len(sub)),
            "covered": int(sub["covered"].sum()),
            "pct": round(100 * sub["covered"].mean(), 2),
            "by_type": {
                t: round(100 * g["covered"].mean(), 2)
                for t, g in sub.groupby("competition_type")
            },
        }
    report["competition_coverage"] = cov

    lab = df[df["started"] == 1].copy()
    lab["dnf"] = lab["dnf"].astype(int)
    report["dnf_rate_by_type"] = {
        t: {"starters": int(len(g)), "dnf": int(g["dnf"].sum()),
            "rate": round(g["dnf"].mean(), 4)}
        for t, g in lab.groupby("competition_type")
    }
    report["dnf_rate_by_category"] = {
        t: {"starters": int(len(g)), "dnf": int(g["dnf"].sum()),
            "rate": round(g["dnf"].mean(), 4)}
        for t, g in lab.groupby("race_category")
    }
    report["dnf_rate_by_year"] = {
        int(y): round(g["dnf"].mean(), 4) for y, g in lab.groupby("year")
    }
    report["dns_rows"] = int((df["started"] == 0).sum())
    report["unknown_status_rows"] = int(df["started"].isna().sum())
    report["rider_match_pct"] = round(100 * df["rider_id"].notna().mean(), 2)

    # Cross-check: finisher counts per competition vs rider_results
    rr = pd.read_sql_query(
        "SELECT competition_id, COUNT(*) AS n_rr FROM rider_results GROUP BY competition_id",
        conn)
    fin = (lab[lab["dnf"] == 0].groupby("competition_id").size()
           .rename("n_lab").reset_index())
    chk = fin.merge(rr, on="competition_id", how="inner")
    report["finisher_crosscheck"] = {
        "comps_compared": int(len(chk)),
        "exact_match_pct": round(100 * (chk["n_lab"] == chk["n_rr"]).mean(), 2),
        "median_abs_diff": float((chk["n_lab"] - chk["n_rr"]).abs().median()),
    }
    conn.close()

    out_json = OUT_DIR / f"dnf_labels_report_{ts}.json"
    out_json.write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(report, indent=2, default=str), flush=True)
    print(f"\nReport -> {out_json}", flush=True)
    print(f"Labels -> {out_csv}", flush=True)


if __name__ == "__main__":
    main()
