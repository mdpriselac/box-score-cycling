"""Editorial feedback digest — the owner's verdicts and notes, collected for the next skill revision.

    uv run python -m cycling_project.nightly.editorial_feedback                    # hosted, operator key
    uv run python -m cycling_project.nightly.editorial_feedback --since 2026-10-01
    uv run python -m cycling_project.nightly.editorial_feedback --store fake --store-root <dir>

Reads every reviewed ``editorial_drafts`` row (``review_status`` approved / revise /
rejected, migration ``0009_editorial_review.sql``) and writes
``performance_eval/editorial/feedback_<date>.md``: a tally, the recurring words in the
notes, then each draft grouped by verdict — the owner's notes, the lint findings and the
prose itself. Chip ED, 2026-10-02.

It is read-only and runs as the operator role (the Mac's key). Nothing here feeds the
notes back into the live editorial agent: the digest is the input a human (or a session)
reads when revising ``agents/skills/editorial/SKILL.md`` and its lexicon.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from cycling_project.nightly.secrets import redact

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = PROJECT_ROOT / "performance_eval" / "editorial"
DEFAULT_FAKE_ROOT = PROJECT_ROOT / "performance_eval" / "runs" / "fakestore"

#: Most actionable first.
VERDICT_ORDER = ("revise", "rejected", "approved")
VERDICT_TITLES = {"revise": "Changes requested", "rejected": "Rejected", "approved": "Approved"}

STOPWORDS = frozenset("""
a about above after again against all also am an and any are as at be because been before being
below between both but by can could did do does doing down during each few for from further had
has have having he her here hers him his how i if in into is it its itself just like more most
much must my no nor not now of off on once only or other our out over own same she should so some
such than that the their them then there these they this those through to too under until up very
was we were what when where which while who whom why will with would you your yours draft drafts
one two get got make made says said need needs needed still really want wants
""".split())


def _reviewed_at(row: Dict[str, Any]) -> str:
    return str(row.get("reviewed_at") or row.get("created_at") or "")


def select_reviewed(rows: Iterable[Dict[str, Any]], since: Optional[str] = None) -> List[Dict[str, Any]]:
    out = [r for r in rows if (r.get("review_status") or "pending") in VERDICT_ORDER]
    if since:
        out = [r for r in out if _reviewed_at(r)[:10] >= since]
    return sorted(out, key=_reviewed_at, reverse=True)


def note_themes(rows: Iterable[Dict[str, Any]], top: int = 12) -> List[tuple]:
    """(word, number of notes that use it) — a deliberately dumb keyword count."""
    counts: Counter = Counter()
    for r in rows:
        words = {w for w in re.findall(r"[a-z][a-z'\-]{3,}", str(r.get("review_notes") or "").lower())
                 if w not in STOPWORDS}
        counts.update(words)
    return [(w, n) for w, n in counts.most_common() if n >= 1][:top]


def lint_summary(lint: Any) -> str:
    if not isinstance(lint, dict) or not lint:
        return "no lint report"
    bits: List[str] = []
    counts = lint.get("counts") or {}
    if any(counts.values()):
        bits.append(", ".join(f"{k} {v}" for k, v in counts.items()))
    for hit in (lint.get("lexicon") or [])[:8]:
        bits.append(f"lexicon '{hit.get('match') or hit.get('term')}' in {hit.get('section')}")
    for miss in (lint.get("numerals") or [])[:8]:
        bits.append(f"numeral {miss.get('token')} not in the bundle ({miss.get('section')})")
    for prob in (lint.get("key") or [])[:4]:
        bits.append(f"key restated as {prob.get('item')} {prob.get('stated')} in {prob.get('section')} "
                    f"(approved: {prob.get('allowed')})")
    validation = lint.get("validation") or {}
    for err in (validation.get("errors") or [])[:8]:
        bits.append(f"schema: {err}")
    if lint.get("error"):
        bits.append(f"lint error: {lint['error']}")
    if (lint.get("checks") or {}).get("numerals") is False:
        bits.append("numerals not checked (no facts bundle beside the draft)")
    return "; ".join(bits) if bits else "clean"


def _quote(text: str) -> str:
    return "\n".join(("> " + line) if line.strip() else ">" for line in str(text or "").splitlines())


def render(rows: List[Dict[str, Any]], *, pending: int, since: Optional[str], today: str) -> str:
    tally = Counter(r.get("review_status") for r in rows)
    lines = [f"# Editorial feedback digest — {today}", ""]
    lines.append(f"Reviewed drafts{f' since {since}' if since else ''}: **{len(rows)}** — "
                 + " · ".join(f"{VERDICT_TITLES[v].lower()} {tally.get(v, 0)}" for v in VERDICT_ORDER)
                 + f". Still waiting for a review: {pending}.")
    lines += ["", "Written by `python -m cycling_project.nightly.editorial_feedback` from `editorial_drafts`. "
              "This is the input to the next revision of `agents/skills/editorial/SKILL.md` and its lexicon; "
              "nothing here reaches the live agent on its own.", ""]
    themes = note_themes(rows)
    if themes:
        lines += ["## Recurring words in the notes", "", "| word | notes using it |", "|---|---|"]
        lines += [f"| {w} | {n} |" for w, n in themes]
        lines.append("")
    for verdict in VERDICT_ORDER:
        group = [r for r in rows if r.get("review_status") == verdict]
        if not group:
            continue
        lines += [f"## {VERDICT_TITLES[verdict]} ({len(group)})", ""]
        for r in group:
            artifact = r.get("artifact") or ((r.get("record") or {}).get("artifact") if isinstance(r.get("record"), dict) else None)
            lines.append(f"### {r.get('campaign_slug')} · {r.get('unit')} · {artifact or r.get('phase')} — draft #{r.get('id')}")
            lines.append("")
            lines.append(f"Written {str(r.get('created_at') or '')[:16].replace('T', ' ')}; reviewed by "
                         f"{r.get('reviewed_by') or '—'} on {str(r.get('reviewed_at') or '')[:16].replace('T', ' ')}; "
                         f"lint {'ok' if r.get('lint_ok') else 'FAILED'}.")
            lines += ["", f"**Notes:** {r.get('review_notes') or '(none)'}", "",
                      f"**Lint:** {lint_summary(r.get('lint'))}", "", "**Prose:**", "",
                      _quote(r.get("body_md") or ""), ""]
    if not rows:
        lines += ["Nothing has been reviewed yet.", ""]
    return "\n".join(lines).rstrip() + "\n"


def open_store(kind: str, root: Optional[Path]):
    from cycling_project.nightly import store as _store
    if kind == "fake":
        return _store.FakeStore(Path(root or DEFAULT_FAKE_ROOT), role="operator")
    return _store.SupabaseStore(role="operator")


def run(store, *, since: Optional[str] = None, out_dir: Path = OUT_DIR, today: Optional[str] = None) -> Path:
    from cycling_project.nightly.store import StoreError
    today = today or dt.datetime.now(dt.timezone.utc).date().isoformat()
    try:
        everything = store.editorial_drafts(limit=5000)
    except StoreError as exc:
        raise SystemExit(redact(f"could not read editorial_drafts: {exc}"))
    if everything and "review_status" not in everything[0]:
        raise SystemExit("editorial_drafts has no review_status column: push "
                         "supabase/migrations/0009_editorial_review.sql first (`supabase db push`)")
    rows = select_reviewed(everything, since)
    pending = sum(1 for r in everything if (r.get("review_status") or "pending") == "pending")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"feedback_{today}.md"
    path.write_text(render(rows, pending=pending, since=since, today=today), encoding="utf-8")
    return path


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--since", default=None, help="only drafts reviewed on or after YYYY-MM-DD")
    ap.add_argument("--store", choices=("supabase", "fake"), default="supabase",
                    help="supabase = the hosted ledger, read with the operator key (default); fake = a FakeStore")
    ap.add_argument("--store-root", type=Path, default=None, help="FakeStore root for --store fake")
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = ap.parse_args(argv)
    if args.since:
        dt.date.fromisoformat(args.since)
    path = run(open_store(args.store, args.store_root), since=args.since, out_dir=args.out_dir)
    try:
        shown = path.relative_to(PROJECT_ROOT)
    except ValueError:
        shown = path
    print(f"wrote {shown}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
