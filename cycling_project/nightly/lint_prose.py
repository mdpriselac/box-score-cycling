"""Deterministic prose linter for editorial drafts (AGENT_DESIGN.md §3.3 / §5.2).

Three checks, all offline:

(a) **Lexicon** — betting / advice vocabulary is forbidden in campaign prose
    (user directive 2026-08-31: market odds are an information-capture
    yardstick, never gambling advice). The list lives in
    ``agents/skills/editorial/lexicon.txt`` and is versioned beside the
    skill. Terms match case-insensitively on word boundaries; ``allow``
    phrases are masked before the scan so "in play" cannot trip "play".
(b) **Numerals** — every number token in the prose (integers, decimals,
    percentages, m:ss / h:mm:ss times, distances) must be present in the
    facts bundle: every numeric value in the bundle is indexed at 0–3
    decimal places, as a percentage at 0–1 dp when it is a probability,
    and as m:ss / h:mm:ss when it could be a duration; number tokens inside
    bundle strings count verbatim. Allowed without a fact: years, dates,
    small integers up to the stage count (stage numbers, top-N, ranks
    "#1".."#21") and climb statistics when a ``route.json`` is supplied
    (it is simply indexed as more facts).
(c) **Key consistency** — any menu item quoted with a weight ("gc_day 0.6",
    "res_2 at a real 0.40") must match the config's ``day_key`` or one of
    its scenario-level keys; the ``day_key_note`` section may only restate
    the root key.

``lint_sections`` returns a JSON-serialisable report with ``ok``; the CLI
exits 0 when clean and 1 when any check fails. ``--regress`` walks every
campaign config under ``performance_eval`` and lists lexicon hits in the
human-written prose without editing anything.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = PROJECT_ROOT / "agents" / "skills" / "editorial"
LEXICON_PATH = SKILL_DIR / "lexicon.txt"

MENU_ITEMS = ("itt", "bunch", "gc_day", "res_0", "res_1", "res_2", "res_3",
              "res_4", "res_5", "res_6", "res_7")

YEAR_RANGE = (1990, 2035)
DEFAULT_MAX_STAGE = 21

# Prose fields of a campaign scenarios.json, in the order they are linted.
CONFIG_PROSE_FIELDS = ("day_key_note", "scenarios.*.label", "scenarios.*.note",
                       "reflection[]", "analysis[].title", "analysis[].note")


# --------------------------------------------------------------------------
# lexicon
# --------------------------------------------------------------------------

def load_lexicon(path: Path = LEXICON_PATH) -> Dict[str, Any]:
    """Parse the lexicon file into ``{"deny": [...], "allow": [...], "version": str}``."""
    deny: List[str] = []
    allow: List[str] = []
    version = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            m = re.match(r"#\s*version:\s*(\S+)", line)
            if m:
                version = m.group(1)
            continue
        if line.lower().startswith("allow "):
            allow.append(line[6:].strip())
        else:
            deny.append(line)
    return {"deny": deny, "allow": allow, "version": version or "unversioned", "path": str(path)}


def term_pattern(term: str) -> re.Pattern:
    """Word-boundary, case-insensitive; words may be joined by spaces or hyphens."""
    words = [re.escape(w) for w in re.split(r"[\s\-]+", term.strip()) if w]
    body = r"[\s\-]+".join(words)
    return re.compile(r"(?<![\w])" + body + r"(?![\w])", re.IGNORECASE)


def mask_allowed(text: str, allow: Sequence[str]) -> str:
    """Replace allowed phrases with same-length filler so offsets survive."""
    out = text
    for phrase in sorted(allow, key=len, reverse=True):
        out = term_pattern(phrase).sub(lambda m: "§" * (m.end() - m.start()), out)
    return out


def lexicon_hits(text: str, lexicon: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Non-overlapping hits (longest term wins on overlap)."""
    masked = mask_allowed(text, lexicon["allow"])
    found: List[Tuple[int, int, str]] = []
    for term in lexicon["deny"]:
        for m in term_pattern(term).finditer(masked):
            found.append((m.start(), m.end(), term))
    found.sort(key=lambda t: (t[0], -(t[1] - t[0])))
    kept: List[Tuple[int, int, str]] = []
    last_end = -1
    for start, end, term in found:
        if start < last_end:
            continue
        kept.append((start, end, term))
        last_end = end
    return [{"term": term, "match": text[s:e], "start": s, "context": _context(text, s, e)}
            for s, e, term in kept]


def _context(text: str, start: int, end: int, width: int = 40) -> str:
    lo, hi = max(0, start - width), min(len(text), end + width)
    return ("…" if lo else "") + text[lo:hi].replace("\n", " ") + ("…" if hi < len(text) else "")


# --------------------------------------------------------------------------
# numerals
# --------------------------------------------------------------------------

NUMBER_TOKEN = re.compile(
    r"(?<![\w.])"                 # not glued to a word or a decimal point
    r"#?"                          # optional rank marker
    r"(\d[\d,]*(?::\d{2}){1,2}"    # 4:12 / 4:15:09 (commas never in times, harmless)
    r"|\d[\d,]*(?:\.\d+)?\s?%"     # 17.2% / 60 %
    r"|\d[\d,]*(?:\.\d+)?)"        # 154.5 / 4,338 / 44
    r"(?![\w]|\.\d)"
)
PLACEHOLDER = re.compile(r"\{\{[^}]*\}\}")
ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
DAY_MONTH = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(January|February|March|April|May|June|July|August|September|October|November|December)\b", re.IGNORECASE)
MONTH_DAY = re.compile(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})(?:st|nd|rd|th)?\b", re.IGNORECASE)


def fmt_mss(seconds: float) -> str:
    s = int(round(seconds))
    if s >= 3600:
        return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"
    return f"{s // 60}:{s % 60:02d}"


def _walk_numbers(node: Any, values: List[float], strings: List[str]) -> None:
    if isinstance(node, bool):
        return
    if isinstance(node, (int, float)):
        if node == node and abs(node) != float("inf"):  # skip NaN/inf
            values.append(float(node))
    elif isinstance(node, str):
        strings.append(node)
    elif isinstance(node, dict):
        for v in node.values():
            _walk_numbers(v, values, strings)
    elif isinstance(node, (list, tuple)):
        for v in node:
            _walk_numbers(v, values, strings)


def _normalise_token(tok: str) -> Tuple[str, str]:
    """Return (kind, canonical) for a raw token: kind in {time, percent, number}."""
    t = tok.lstrip("#").replace(",", "").replace(" ", "")
    if ":" in t:
        return "time", t
    if t.endswith("%"):
        return "percent", t[:-1]
    return "number", t


class FactIndex:
    """Every way a bundle number may legitimately be written."""

    def __init__(self, *facts: Any, max_stage: int = DEFAULT_MAX_STAGE):
        values: List[float] = []
        strings: List[str] = []
        for f in facts:
            if f is not None:
                _walk_numbers(f, values, strings)
        self.max_stage = max_stage
        self.by_dp: Dict[int, set] = {dp: set() for dp in range(0, 4)}
        self.pct_by_dp: Dict[int, set] = {dp: set() for dp in range(0, 3)}
        self.times: set = set()
        self.string_tokens: set = set()
        for v in values:
            for dp in self.by_dp:
                if dp == 0 and abs(v) < 1:
                    continue  # 0.0x probabilities must not license "0"
                self.by_dp[dp].add(round(v, dp))
            if 0 <= v <= 1:
                for dp in self.pct_by_dp:
                    self.pct_by_dp[dp].add(round(v * 100, dp))
            if v >= 0:
                self.times.add(fmt_mss(v))
                if v >= 60:
                    # a bare minute count is also a valid way to write a gap
                    self.by_dp[0].add(round(v / 60, 0))
        for s in strings:
            for m in NUMBER_TOKEN.finditer(s):
                kind, canon = _normalise_token(m.group(0))
                self.string_tokens.add((kind, canon))
                if kind == "number":
                    try:
                        self.by_dp[0].add(round(float(canon), 0))
                    except ValueError:
                        pass

    def allowed_without_fact(self, kind: str, canon: str) -> bool:
        if kind != "number":
            return False
        try:
            v = float(canon)
        except ValueError:
            return False
        if "." in canon:
            return False
        iv = int(v)
        if YEAR_RANGE[0] <= iv <= YEAR_RANGE[1]:
            return True
        return 0 <= iv <= self.max_stage

    def has(self, kind: str, canon: str) -> bool:
        if (kind, canon) in self.string_tokens:
            return True
        if kind == "time":
            return canon in self.times
        dp = len(canon.split(".")[1]) if "." in canon else 0
        try:
            v = float(canon)
        except ValueError:
            return False
        if kind == "percent":
            d = min(dp, 2)
            return round(v, d) in self.pct_by_dp[d] or round(v, min(dp, 3)) in self.by_dp[min(dp, 3)]
        d = min(dp, 3)
        return round(v, d) in self.by_dp[d]


def _date_spans(text: str) -> List[Tuple[int, int]]:
    spans = []
    for rx in (ISO_DATE, DAY_MONTH, MONTH_DAY):
        spans.extend((m.start(), m.end()) for m in rx.finditer(text))
    return spans


def numeral_misses(text: str, index: FactIndex) -> List[Dict[str, Any]]:
    misses = []
    dates = _date_spans(text)
    for m in NUMBER_TOKEN.finditer(text):
        s, e = m.start(), m.end()
        if any(a <= s and e <= b for a, b in dates):
            continue
        kind, canon = _normalise_token(m.group(0))
        if index.allowed_without_fact(kind, canon):
            continue
        if index.has(kind, canon):
            continue
        misses.append({"token": m.group(0), "kind": kind, "start": s, "context": _context(text, s, e)})
    return misses


# --------------------------------------------------------------------------
# key consistency
# --------------------------------------------------------------------------

KEY_MENTION = re.compile(
    r"(?<![\w])(itt|bunch|gc_day|res_[0-7])(?![\w])"
    r"(?:\s+(?:at|of|=|:|to|weighted|weight)\s+(?:a\s+(?:real|full|hard)\s+)?|\s*[:=]\s*|\s+)"
    r"(1\.0+|1|0\.\d+|0)(?!\w|\.\d)",
    re.IGNORECASE,
)


def config_keys(config: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    """``{"root": {...}, "scenario:<key>": {...}}`` for every key in a config."""
    out: Dict[str, Dict[str, float]] = {}
    if not config:
        return out
    if isinstance(config.get("day_key"), dict):
        out["root"] = {k: float(v) for k, v in config["day_key"].items()}
    for name, spec in (config.get("scenarios") or {}).items():
        if isinstance(spec, dict) and isinstance(spec.get("day_key"), dict):
            out[f"scenario:{name}"] = {k: float(v) for k, v in spec["day_key"].items()}
    return out


def key_mismatches(text: str, allowed: Dict[str, Dict[str, float]], *, tol: float = 0.0051) -> List[Dict[str, Any]]:
    problems = []
    for m in KEY_MENTION.finditer(text):
        item, stated = m.group(1).lower(), float(m.group(2))
        matched = [name for name, key in allowed.items()
                   if item in key and abs(key[item] - stated) < tol]
        if not matched:
            problems.append({"item": item, "stated": stated, "start": m.start(),
                             "allowed": {n: k.get(item) for n, k in allowed.items() if item in k},
                             "context": _context(text, m.start(), m.end())})
    return problems


# --------------------------------------------------------------------------
# orchestration
# --------------------------------------------------------------------------

SectionText = Union[str, List[str]]


def flatten_sections(sections: Dict[str, Any]) -> Dict[str, str]:
    """``{"reflection": [p1, p2]}`` → ``{"reflection[0]": p1, ...}``;
    ``{"scenario_notes": [{"scenario_key": k, "note": t}]}`` → ``scenario_notes.k``."""
    flat: Dict[str, str] = {}
    for name, val in sections.items():
        if isinstance(val, str):
            flat[name] = val
        elif isinstance(val, list):
            for i, item in enumerate(val):
                if isinstance(item, str):
                    flat[f"{name}[{i}]"] = item
                elif isinstance(item, dict):
                    key = item.get("scenario_key") or item.get("key") or str(i)
                    text = item.get("note") or item.get("text") or ""
                    flat[f"{name}.{key}"] = text
        elif isinstance(val, dict):
            for k, v in val.items():
                if isinstance(v, str):
                    flat[f"{name}.{k}"] = v
    return flat


def lint_sections(sections: Dict[str, Any], *, facts: Any = None, config: Optional[Dict[str, Any]] = None,
                  route: Any = None, lexicon: Optional[Dict[str, Any]] = None,
                  check_numerals: bool = True, max_stage: int = DEFAULT_MAX_STAGE) -> Dict[str, Any]:
    """Lint every prose section. Returns a JSON-serialisable report with ``ok``."""
    lex = lexicon or load_lexicon()
    flat = flatten_sections(sections)
    index = FactIndex(facts, route, max_stage=max_stage) if check_numerals else None
    keys = config_keys(config)
    root_only = {"root": keys["root"]} if "root" in keys else {}
    report: Dict[str, Any] = {
        "ok": True,
        "lexicon_version": lex["version"],
        "checks": {"lexicon": True, "numerals": bool(check_numerals and facts is not None),
                   "key": bool(keys)},
        "sections_checked": list(flat),
        "lexicon": [], "numerals": [], "key": [], "placeholders": [],
    }
    for name, text in flat.items():
        if not isinstance(text, str) or not text.strip():
            continue
        for hit in lexicon_hits(text, lex):
            report["lexicon"].append({"section": name, **hit})
        for m in PLACEHOLDER.finditer(text):
            report["placeholders"].append({"section": name, "token": m.group(0), "start": m.start()})
        if report["checks"]["numerals"]:
            for miss in numeral_misses(text, index):
                report["numerals"].append({"section": name, **miss})
        if keys:
            allowed = root_only if name.split(".")[0].split("[")[0] == "day_key_note" and root_only else keys
            for prob in key_mismatches(text, allowed):
                report["key"].append({"section": name, **prob})
    report["counts"] = {k: len(report[k]) for k in ("lexicon", "numerals", "key", "placeholders")}
    report["ok"] = not any(report["counts"].values())
    return report


def config_prose(config: Dict[str, Any]) -> Dict[str, Any]:
    """The human-written prose fields of a scenarios.json, keyed like the draft sections."""
    out: Dict[str, Any] = {}
    if isinstance(config.get("day_key_note"), str):
        out["day_key_note"] = config["day_key_note"]
    for name, spec in (config.get("scenarios") or {}).items():
        if not isinstance(spec, dict):
            continue
        if isinstance(spec.get("label"), str):
            out[f"scenario_label.{name}"] = spec["label"]
        if isinstance(spec.get("note"), str):
            out[f"scenario_note.{name}"] = spec["note"]
    if isinstance(config.get("reflection"), list):
        out["reflection"] = [p for p in config["reflection"] if isinstance(p, str)]
    for i, block in enumerate(config.get("analysis") or []):
        if isinstance(block, dict):
            for fld in ("title", "note"):
                if isinstance(block.get(fld), str):
                    out[f"analysis[{i}].{fld}"] = block[fld]
    return out


def lint_config_file(path: Path, *, facts: Any = None, route: Any = None,
                     lexicon: Optional[Dict[str, Any]] = None, check_numerals: bool = False) -> Dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    report = lint_sections(config_prose(config), facts=facts, config=config, route=route,
                           lexicon=lexicon, check_numerals=check_numerals and facts is not None)
    report["file"] = str(path)
    return report


def regress(roots: Iterable[Path], *, lexicon: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Lexicon + key check over every ``predictions/*/scenarios.json`` under each root."""
    lex = lexicon or load_lexicon()
    files: List[Path] = []
    for root in roots:
        files.extend(sorted(root.glob("*/predictions/*/scenarios.json")))
        files.extend(sorted(root.glob("predictions/*/scenarios.json")))
    reports = []
    for f in files:
        if f.name.startswith("TEMPLATE"):
            continue
        r = lint_config_file(f, lexicon=lex, check_numerals=False)
        reports.append(r)
    total_lex = sum(r["counts"]["lexicon"] for r in reports)
    total_key = sum(r["counts"]["key"] for r in reports)
    by_term: Dict[str, int] = {}
    for r in reports:
        for h in r["lexicon"]:
            by_term[h["term"]] = by_term.get(h["term"], 0) + 1
    return {"ok": total_lex == 0 and total_key == 0, "files": len(reports),
            "lexicon_version": lex["version"], "lexicon_hits": total_lex, "key_mismatches": total_key,
            "hits_by_term": dict(sorted(by_term.items(), key=lambda kv: -kv[1])),
            "reports": [r for r in reports if not r["ok"]]}


def print_regress_summary(summary: Dict[str, Any], stream=sys.stdout) -> None:
    print(f"lexicon {summary['lexicon_version']}: {summary['files']} configs, "
          f"{summary['lexicon_hits']} lexicon hits, {summary['key_mismatches']} key mismatches", file=stream)
    if summary["hits_by_term"]:
        print("  by term: " + ", ".join(f"{t}×{n}" for t, n in summary["hits_by_term"].items()), file=stream)
    for r in summary["reports"]:
        rel = r["file"]
        for h in r["lexicon"]:
            print(f"  {rel} :: {h['section']} :: '{h['match']}' ({h['term']}) — {h['context']}", file=stream)
        for k in r["key"]:
            print(f"  {rel} :: {k['section']} :: key {k['item']} {k['stated']} not in "
                  f"{k['allowed']} — {k['context']}", file=stream)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Lint campaign prose: lexicon, numerals, key consistency.")
    p.add_argument("--config", type=Path, help="scenarios.json (human prose is linted unless --draft is given)")
    p.add_argument("--draft", type=Path, help="editorial draft JSON (§5.2 record or its 'record' wrapper)")
    p.add_argument("--facts", type=Path, help="facts bundle JSON — enables the numeral check")
    p.add_argument("--route", type=Path, help="route.json to whitelist climb statistics")
    p.add_argument("--lexicon", type=Path, default=LEXICON_PATH)
    p.add_argument("--max-stage", type=int, default=DEFAULT_MAX_STAGE)
    p.add_argument("--regress", type=Path, nargs="*", metavar="DIR",
                   help="walk performance_eval-style roots and report lexicon hits in human prose")
    p.add_argument("--report", type=Path, help="write the JSON report here (stdout otherwise)")
    p.add_argument("--quiet", action="store_true", help="suppress the JSON on stdout")
    return p


def _emit(report: Dict[str, Any], args: argparse.Namespace) -> None:
    text = json.dumps(report, indent=1, ensure_ascii=False)
    if args.report:
        args.report.write_text(text + "\n", encoding="utf-8")
    if not args.quiet:
        print(text)


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    lex = load_lexicon(args.lexicon)
    if args.regress is not None:
        roots = args.regress or [PROJECT_ROOT / "performance_eval"]
        summary = regress(roots, lexicon=lex)
        print_regress_summary(summary, stream=sys.stderr)
        _emit(summary, args)
        return 0 if summary["ok"] else 1
    if not args.config and not args.draft:
        print("need --config, --draft or --regress", file=sys.stderr)
        return 2
    facts = json.loads(args.facts.read_text(encoding="utf-8")) if args.facts else None
    route = json.loads(args.route.read_text(encoding="utf-8")) if args.route else None
    config = json.loads(args.config.read_text(encoding="utf-8")) if args.config else None
    if args.draft:
        draft = json.loads(args.draft.read_text(encoding="utf-8"))
        record = draft.get("record", draft)
        report = lint_sections(record.get("sections", {}), facts=facts, config=config, route=route,
                               lexicon=lex, check_numerals=facts is not None, max_stage=args.max_stage)
        report["file"] = str(args.draft)
    else:
        report = lint_sections(config_prose(config), facts=facts, config=config, route=route, lexicon=lex,
                               check_numerals=facts is not None, max_stage=args.max_stage)
        report["file"] = str(args.config)
    _emit(report, args)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
