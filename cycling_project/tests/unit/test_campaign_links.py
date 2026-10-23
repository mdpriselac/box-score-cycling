"""The /model race-diary block (netlify_site/build/campaign_links.py).

Every campaign build used to append its own unlabeled "Race diary:" strip to
the explainer; the block now holds two Grand Tour cards and one archive line,
whatever campaign last ran.
"""

from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BUILD = PROJECT_ROOT / "netlify_site" / "build"


def _links():
    sys.path.insert(0, str(BUILD))
    try:
        return runpy.run_path(str(BUILD / "campaign_links.py"), run_name="_for_tests")
    finally:
        sys.path.remove(str(BUILD))


ANCHOR = "<!-- ================= HEADS VIEW ================= -->"


def _legacy(marker, label):
    return (f"<!-- {marker}:START -->\n<style>.stage-strip{{}}</style>\n"
            f'<div class="stage-strip"><b>{label}:</b> <a href="x.html">Stage 1</a></div>\n'
            f"<!-- {marker}:END -->\n\n")


def test_legacy_strips_fold_into_one_block_and_other_markers_survive():
    cl = _links()
    src = ("<p>toggle</p>\n" + _legacy("STAGES", "Tour diary") + _legacy("VUELTA-STAGES", "Vuelta diary")
           + _legacy("CRO-RACE-2026", "Race diary")
           + "<!-- HEADS:START -->heads<!-- HEADS:END -->\n" + ANCHOR)
    out = cl["replace_block"](src, "NEW")
    assert 'class="stage-strip"' not in out and "Race diary" not in out
    assert out.count("<!-- CAMPAIGN-LINKS:START -->") == 1
    assert out.index("<p>toggle</p>") < out.index("NEW") < out.index("<!-- HEADS:START -->heads")
    # idempotent: a second build replaces the block in place
    again = cl["replace_block"](out, "NEWER")
    assert "NEW\n" not in again and again.count("NEWER") == 1 and again.index("NEWER") == out.index("NEW")


def test_block_goes_before_heads_view_when_nothing_to_replace():
    out = _links()["replace_block"]("<p>a</p>\n" + ANCHOR, "NEW")
    assert out.index("NEW") < out.index(ANCHOR)


def test_cards_link_existing_pages_mark_cancelled_and_point_the_rest_at_races(tmp_path):
    cl = _links()
    for name in ["stage02.html", "gc.html", "review.html", "stages.html",
                 "vuelta-stage01.html", "vuelta-stage03.html", "vuelta-gc.html"]:
        (tmp_path / name).write_text("x")
    (tmp_path / "site-index.json").write_text(json.dumps({"races": [
        {"slug": "tour-de-france", "year": 2026, "start_date": "2026-07-04", "end_date": "2026-07-26",
         "pages": {"review": {"url": "/race/tour-de-france/2026/review"}},
         "stages": [{"stage": 2, "status": "settled", "url": "/race/tour-de-france/2026/stage-02"}]},
        {"slug": "vuelta-a-espana", "year": 2026, "stages": [{"stage": 3, "status": "cancelled"}]},
        {"slug": "cro-race", "year": 2026}, {"slug": "paris-tours", "year": 2026},
    ]}))
    html = cl["render"](tmp_path)
    assert 'href="/race/tour-de-france/2026/review"' in html      # clean route when indexed
    assert 'href="gc.html"' in html and 'href="vuelta-gc.html"' in html  # flat fallback
    assert 'href="vuelta-review.html"' not in html                # no page, no link
    assert 'href="/race/tour-de-france/2026/stage-02"' in html
    assert 'href="stage01.html"' not in html and 'title="No page for stage 1">1</span>' in html
    assert '<span class="cancelled" title="Stage 3 was cancelled">3</span>' in html
    assert "stage 3 cancelled" in html and "4–26 July" in html
    assert 'href="/races"' in html and "(2 races so far)" in html
    assert "cro-race" not in html  # automated campaigns get no per-race links here
