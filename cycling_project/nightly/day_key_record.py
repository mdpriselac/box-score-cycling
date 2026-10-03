"""Day-key decision record: schema, validator, driver rules, provenance.

The day-key agent (``agents/skills/day-key-read/SKILL.md``) returns the
AGENT_DESIGN §5.1 record as structured output. This module is the contract
around that record:

* :data:`RECORD_SCHEMA` — the JSON schema handed to the API as
  ``output_config.format`` (the model emits ``key_items`` as a list; the
  driver folds it into the §5.1 ``key`` mapping via :func:`normalise_record`).
* :func:`validate_record` — weights sum to 1 ± 0.001, items ∈ menu v1 (never
  ``res_5``), no cross-family hedging, family matches the argmax, evidence
  refs resolve to ``bundle/manifest.json`` entries, no results for the stage
  being keyed.
* :func:`apply_driver_rules` — ``human_review_required`` is forced true when
  odds are missing or ``confidence`` is under the threshold, whatever the
  agent set; the agent's own flag is kept as ``agent_self_flag`` so the gate
  can measure its calibration.
* :func:`stamp_provenance` — skill version + git sha of SKILL.md, model id,
  bundle manifest sha256, ``generated_at``.
* :func:`score_agent_key` — the paired-scorecard fields
  ``score_day_keys.py --also agent`` adds.

Pure functions, no I/O beyond reading SKILL.md and asking git for its sha.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SKILL_PATH = PROJECT_ROOT / "agents" / "skills" / "day-key-read" / "SKILL.md"

MACRO_ITEMS = ("itt", "bunch", "gc_day")
RESIDUAL_ITEMS = ("res_0", "res_1", "res_2", "res_3", "res_4", "res_6", "res_7")
FORBIDDEN_ITEMS = ("res_5",)          # degenerate twin of res_7 — never keyed
DISCOURAGED_ITEMS = ("res_0",)        # chaos — weight the family candidates instead
MENU_ITEMS = MACRO_ITEMS + RESIDUAL_ITEMS

FAMILY_OF = {
    "itt": "macro", "bunch": "macro", "gc_day": "macro",
    "res_2": "escape", "res_4": "escape", "res_6": "escape",
    "res_3": "power_sprint", "res_7": "power_sprint", "res_5": "power_sprint",
    "res_1": "bridge", "res_0": "bridge",
}
FAMILIES = ("macro", "escape", "power_sprint", "bridge")
CHASE_VERDICTS = ("nobody_pays", "contested", "controlled")

WEIGHT_TOLERANCE = 0.001
DEFAULT_CONFIDENCE_THRESHOLD = 0.55


class RecordValidationError(ValueError):
    def __init__(self, errors: list[str]):
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


# ---------------------------------------------------------------------------
# schema (model-facing)
# ---------------------------------------------------------------------------

def _obj(properties: dict, required: Optional[list] = None) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": list(required if required is not None else properties.keys()),
        "additionalProperties": False,
    }


RECORD_SCHEMA: dict = _obj({
    "key_items": {
        "type": "array",
        "items": _obj({
            "item": {"type": "string", "enum": list(MENU_ITEMS)},
            "weight": {"type": "number"},
        }),
        "description": "1-3 menu items with weights summing to 1 (the API rejects minItems/maxItems; the validator enforces the count).",
    },
    "family": {"type": "string", "enum": list(FAMILIES)},
    "macro_routing": _obj({
        "itt": {"type": "boolean"},
        "bunch_considered": {"type": "boolean"},
        "gc_day_considered": {"type": "boolean"},
        "bunch_rejected_because": {"type": "string"},
        "gc_day_rejected_because": {"type": "string"},
    }),
    "primary_mechanism": {"type": "string"},
    "credible_alternative": {"type": "string"},
    "chase_incentive": _obj({
        "who_has_reason_to_spend": {
            "type": "array",
            "items": _obj({"team": {"type": "string"}, "why": {"type": "string"}}),
        },
        "verdict": {"type": "string", "enum": list(CHASE_VERDICTS)},
        "consequence_for_key": {"type": "string"},
    }),
    "comparables_used": {
        "type": "array",
        "items": _obj({
            "stage": {"type": "integer"},
            "argument": {"type": "string"},
            "measured_outcome": {"type": "string"},
        }),
    },
    "evidence": {
        "type": "array",
        "items": _obj({"claim": {"type": "string"}, "ref": {"type": "string"}}),
        "description": "ref is the exact path of a bundle file listed in manifest.json.",
    },
    "missing_evidence": {"type": "array", "items": {"type": "string"}},
    "conflicts": {"type": "array", "items": {"type": "string"}},
    "confidence": {"type": "number"},
    "human_review_required": {"type": "boolean"},
    "review_reason": {"type": "string"},
})


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def family_of(item: str) -> Optional[str]:
    return FAMILY_OF.get(item)


def argmax_item(key: dict[str, float]) -> Optional[str]:
    if not key:
        return None
    return max(key, key=lambda k: (float(key[k]), k))


def normalise_key(key: Any) -> dict[str, float]:
    """Accept the schema's ``key_items`` list or a §5.1 mapping; return a mapping.

    Weights are kept as given (the validator judges the sum); duplicate items
    are summed so a duplicated entry is visible as a bad total, not hidden.
    """
    out: dict[str, float] = {}
    if isinstance(key, dict):
        for k, v in key.items():
            out[str(k)] = out.get(str(k), 0.0) + float(v)
    elif isinstance(key, list):
        for entry in key:
            item = str(entry.get("item")) if isinstance(entry, dict) else str(entry)
            weight = float(entry.get("weight", 0.0)) if isinstance(entry, dict) else 0.0
            out[item] = out.get(item, 0.0) + weight
    return out


def normalise_record(model_output: dict, *, race: str, stage: int, stage_date: Optional[str]) -> dict:
    """Fold the model's structured output into the §5.1 record shape."""
    rec = dict(model_output)
    key = normalise_key(rec.pop("key_items", rec.get("key", {})))
    ordered = {"race": race, "stage": int(stage), "stage_date": stage_date,
               "key": {k: round(v, 4) for k, v in key.items()}}
    ordered.update({k: v for k, v in rec.items() if k not in ("race", "stage", "stage_date", "key")})
    return ordered


def manifest_paths(manifest: dict) -> set[str]:
    return {str(e.get("path")) for e in (manifest or {}).get("entries", []) if e.get("path")}


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------

def validate_record(record: dict, manifest: Optional[dict] = None, *,
                    results_marker: Optional[str] = None) -> list[str]:
    """Return a list of problems (empty == valid). Never raises."""
    errors: list[str] = []
    key = record.get("key")
    if not isinstance(key, dict) or not key:
        return ["key must be a non-empty mapping item -> weight"]

    if len(key) > 3:
        errors.append(f"key has {len(key)} items; at most 3 allowed")
    total = 0.0
    for item, weight in key.items():
        if item not in MENU_ITEMS and item not in FORBIDDEN_ITEMS:
            errors.append(f"unknown menu item {item!r}")
            continue
        if item in FORBIDDEN_ITEMS:
            errors.append(f"{item} is never keyed (degenerate res_7)")
        try:
            w = float(weight)
        except (TypeError, ValueError):
            errors.append(f"weight for {item} is not a number")
            continue
        if not (0.0 < w <= 1.0 + WEIGHT_TOLERANCE):
            errors.append(f"weight for {item} must be in (0, 1], got {w}")
        total += w
    if abs(total - 1.0) > WEIGHT_TOLERANCE:
        errors.append(f"weights sum to {total:.4f}, not 1 ± {WEIGHT_TOLERANCE}")

    # families: never hedge across escape and power_sprint
    families = {family_of(i) for i in key if family_of(i)}
    if "escape" in families and "power_sprint" in families:
        errors.append("key spreads weight across both residual families (escape + power_sprint)")
    top = argmax_item(key)
    expected_family = family_of(top) if top else None
    declared = record.get("family")
    if declared not in FAMILIES:
        errors.append(f"family must be one of {FAMILIES}, got {declared!r}")
    elif expected_family and declared != expected_family:
        errors.append(f"family {declared!r} does not match argmax item {top} ({expected_family})")

    # mechanism + evidence
    if not str(record.get("primary_mechanism", "")).strip():
        errors.append("primary_mechanism is empty")
    evidence = record.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        errors.append("evidence must be a non-empty list of {claim, ref}")
    else:
        allowed = manifest_paths(manifest) if manifest is not None else None
        for i, ev in enumerate(evidence):
            if not isinstance(ev, dict) or not str(ev.get("claim", "")).strip() or not str(ev.get("ref", "")).strip():
                errors.append(f"evidence[{i}] needs a non-empty claim and ref")
                continue
            ref = str(ev["ref"])
            if allowed is not None and ref not in allowed:
                errors.append(f"evidence[{i}].ref {ref!r} is not a bundle file in manifest.json")
            if results_marker and results_marker in ref:
                errors.append(f"evidence[{i}].ref {ref!r} points at results for the stage being keyed")

    ci = record.get("chase_incentive")
    if not isinstance(ci, dict) or ci.get("verdict") not in CHASE_VERDICTS:
        errors.append(f"chase_incentive.verdict must be one of {CHASE_VERDICTS}")

    try:
        conf = float(record.get("confidence"))
        if not (0.0 <= conf <= 1.0):
            errors.append(f"confidence must be in [0, 1], got {conf}")
    except (TypeError, ValueError):
        errors.append("confidence must be a number in [0, 1]")

    if not isinstance(record.get("human_review_required"), bool):
        errors.append("human_review_required must be a boolean")

    return errors


def assert_valid(record: dict, manifest: Optional[dict] = None, **kw) -> None:
    errors = validate_record(record, manifest, **kw)
    if errors:
        raise RecordValidationError(errors)


def warnings_for(record: dict) -> list[str]:
    """Non-fatal advisories (discouraged items)."""
    out = []
    for item in record.get("key", {}):
        if item in DISCOURAGED_ITEMS:
            out.append(f"{item} keyed — the skill says to weight the family candidates instead")
    return out


# ---------------------------------------------------------------------------
# driver rules
# ---------------------------------------------------------------------------

def apply_driver_rules(record: dict, *, odds_present: bool,
                       confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD) -> dict:
    """Force ``human_review_required`` per §5.1, keeping the agent's own flag.

    Adds ``agent_self_flag`` (what the model set) and ``review_forced_by``
    (which driver rules fired). ``review_reason`` gains the forced reasons.
    """
    rec = dict(record)
    self_flag = bool(rec.get("human_review_required", False))
    forced: list[str] = []
    if not odds_present:
        forced.append("missing odds")
    try:
        conf = float(rec.get("confidence", 0.0))
    except (TypeError, ValueError):
        conf = 0.0
    if conf < confidence_threshold:
        forced.append(f"low confidence ({conf:.2f} < {confidence_threshold:.2f})")
    rec["agent_self_flag"] = self_flag
    rec["review_forced_by"] = forced
    rec["human_review_required"] = self_flag or bool(forced)
    if forced:
        reason = str(rec.get("review_reason", "") or "").strip()
        extra = "; ".join(forced)
        rec["review_reason"] = f"{reason}; driver: {extra}" if reason and reason != "none" else f"driver: {extra}"
    return rec


# ---------------------------------------------------------------------------
# provenance
# ---------------------------------------------------------------------------

def skill_version(skill_path: Path = SKILL_PATH) -> str:
    text = Path(skill_path).read_text(encoding="utf-8")
    m = re.search(r"^version:\s*([0-9]+\.[0-9]+\.[0-9]+)\s*$", text, flags=re.M)
    if not m:
        raise ValueError(f"{skill_path} has no 'version: X.Y.Z' header")
    return m.group(1)


def skill_body(skill_path: Path = SKILL_PATH) -> str:
    """The skill text without its YAML front-matter (the system prompt)."""
    text = Path(skill_path).read_text(encoding="utf-8")
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4:].lstrip("\n")
    return text


def _git(args: list[str], cwd: Path) -> Optional[str]:
    try:
        out = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip() or None


def skill_git_sha(skill_path: Path = SKILL_PATH) -> dict[str, Optional[str]]:
    """``commit`` = last commit touching SKILL.md (None until committed);
    ``blob`` = git's blob id of the working copy; ``sha256`` always."""
    p = Path(skill_path)
    data = p.read_bytes()
    return {
        "commit": _git(["log", "-1", "--format=%H", "--", str(p)], p.parent),
        "blob": _git(["hash-object", str(p)], p.parent),
        "sha256": hashlib.sha256(data).hexdigest(),
        "dirty": (_git(["status", "--porcelain", "--", str(p)], p.parent) or "") != "",
    }


def stamp_provenance(record: dict, *, model_id: str, manifest_sha256: str,
                     skill_path: Path = SKILL_PATH, generated_at: Optional[str] = None,
                     replay: bool = False, extra: Optional[dict] = None) -> dict:
    rec = dict(record)
    sha = skill_git_sha(skill_path)
    prov = {
        "skill": skill_path.name if isinstance(skill_path, Path) else str(skill_path),
        "skill_version": skill_version(skill_path),
        "skill_git_sha": sha["commit"],
        "skill_blob_sha": sha["blob"],
        "skill_sha256": sha["sha256"],
        "skill_dirty": sha["dirty"],
        "model_id": model_id,
        "bundle_manifest_sha256": manifest_sha256,
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if extra:
        prov.update(extra)
    rec["provenance"] = prov
    rec["replay"] = bool(replay)
    return rec


# ---------------------------------------------------------------------------
# scoring (paired scorecard fields)
# ---------------------------------------------------------------------------

def score_agent_key(agent_record: Optional[dict], oracle_item: str) -> dict:
    """The ``agent_*`` fields for one scorecard row (None record -> nulls)."""
    # The coordinator sometimes saves the reader's raw answer (`key_items`, a list) instead of the
    # folded record; the driver prices from either shape (6a456d9), so the scorer must read both.
    # Before 2026-10-02 it read only `key`, and 11 cloud-keyed stages (CRO Race 3-6, Langkawi 1-7)
    # scored as "no agent key" (performance_eval/runs/day_key_no_odds_review_2026-10-02.md).
    key = normalise_key((agent_record or {}).get("key") or (agent_record or {}).get("key_items") or {})
    if not key:
        return {"agent_key": None, "agent_exact": None, "agent_covered": None,
                "agent_weight_on_true": None, "agent_flagged": None,
                "agent_family_covered": None, "agent_confidence": None, "agent_replay": None}
    tot = sum(key.values()) or 1.0
    key = {k: v / tot for k, v in key.items()}
    top = argmax_item(key)
    fam_true = family_of(oracle_item)
    return {
        "agent_key": {k: round(v, 3) for k, v in key.items()},
        "agent_exact": top == oracle_item,
        "agent_covered": oracle_item in key,
        "agent_weight_on_true": round(key.get(oracle_item, 0.0), 3),
        "agent_flagged": bool(agent_record.get("human_review_required", False)),
        "agent_self_flag": bool(agent_record.get("agent_self_flag", agent_record.get("human_review_required", False))),
        "agent_family_covered": fam_true in {family_of(i) for i in key},
        "agent_confidence": agent_record.get("confidence"),
        "agent_replay": bool(agent_record.get("replay", False)),
    }


def family_covered(key: Optional[dict], oracle_item: str) -> Optional[bool]:
    if not key:
        return None
    return family_of(oracle_item) in {family_of(i) for i in key}


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def iter_items(keys: Iterable[str]) -> list[str]:
    return [k for k in keys if k in MENU_ITEMS]
