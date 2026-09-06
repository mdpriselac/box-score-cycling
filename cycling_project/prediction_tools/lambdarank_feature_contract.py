"""Feature contract for the production LambdaRank probability head.

LambdaRank is intentionally a pre-race, stateless base head. The bucket and
contender heads may consume within-race state directly, but the LambdaRank
prediction used as their meta-feature must have the same meaning during OOF
training and serving.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterable, Mapping, Optional

import pandas as pd

from .data_pipeline import CyclingDataPipeline


LAMBDARANK_FEATURE_CONTRACT = "stateless-pre-race"
LAMBDARANK_FEATURE_CONTRACT_VERSION = 1
LAMBDARANK_EXCLUDED_COLUMNS = tuple(
    CyclingDataPipeline.RACE_STATE_FEATURE_COLS + ["race_state_missing"]
)


def build_lambdarank_feature_view(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy containing no within-race state fields."""
    present = [column for column in LAMBDARANK_EXCLUDED_COLUMNS if column in df.columns]
    return df.drop(columns=present).copy()


def feature_schema_sha256(feature_columns: Iterable[str]) -> str:
    """Return a stable hash of an ordered, post-engineering schema."""
    payload = json.dumps(list(feature_columns), separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def assert_stateless_feature_columns(feature_columns: Iterable[str]) -> None:
    """Reject a learned or loaded LambdaRank schema containing race state."""
    leaked = sorted(set(feature_columns).intersection(LAMBDARANK_EXCLUDED_COLUMNS))
    if leaked:
        raise ValueError(
            "LambdaRank feature contract violation: within-race state fields "
            f"must not reach this head: {leaked}"
        )


def make_lambdarank_contract_metadata(
    feature_columns: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """Build persisted contract metadata, including the learned schema hash."""
    metadata: Dict[str, Any] = {
        "name": LAMBDARANK_FEATURE_CONTRACT,
        "version": LAMBDARANK_FEATURE_CONTRACT_VERSION,
        "excluded_columns": list(LAMBDARANK_EXCLUDED_COLUMNS),
    }
    if feature_columns is not None:
        columns = list(feature_columns)
        assert_stateless_feature_columns(columns)
        metadata["feature_count"] = len(columns)
        metadata["feature_schema_sha256"] = feature_schema_sha256(columns)
    return metadata


def assert_lambdarank_contract_compatible(
    expected: Mapping[str, Any],
    actual: Mapping[str, Any],
    *,
    context: str = "LambdaRank artifact",
) -> None:
    """Fail closed when a replacement head changes downstream semantics."""
    keys = ("name", "version", "excluded_columns", "feature_schema_sha256")
    mismatches = {
        key: (expected.get(key), actual.get(key))
        for key in keys
        if expected.get(key) != actual.get(key)
    }
    if mismatches:
        detail = "; ".join(
            f"{key}: expected {values[0]!r}, got {values[1]!r}"
            for key, values in mismatches.items()
        )
        raise ValueError(f"{context} feature contract mismatch ({detail})")
