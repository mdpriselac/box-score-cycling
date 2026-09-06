"""Content-addressed manifest for the production prediction artifact set.

The production directory is assembled by several independent trainers.  This
module gives that directory one release identity: every known serving artifact
is inventoried with its size and SHA-256 digest, grouped by the head or
auxiliary system that owns it.  The manifest is written atomically and is
deliberately independent of model classes so validators and deployment tooling
can use it without importing LightGBM or pandas.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional


MANIFEST_FILENAME = "production_release_manifest.json"
MANIFEST_SCHEMA_VERSION = 1


class ProductionReleaseError(RuntimeError):
    """Raised when a production artifact release is unsafe to serve."""


@dataclass(frozen=True)
class ReleaseValidationReport:
    """Successful validation details for logging and deployment checks."""

    release_id: str
    artifact_count: int
    total_size: int
    component_count: int


@dataclass(frozen=True)
class ComponentSpec:
    """Files that must be published together for one serving component."""

    name: str
    files: tuple[str, ...]
    metadata_flag: Optional[str] = None


# Keep this explicit.  A newly introduced serving artifact should require an
# intentional manifest change rather than silently escaping release tracking.
COMPONENT_SPECS: tuple[ComponentSpec, ...] = (
    ComponentSpec("registry_metadata", ("metadata.json",)),
    ComponentSpec("main_bucket", ("bucket_model.txt", "bucket_feature_engineer.pkl")),
    ComponentSpec(
        "time_gap",
        ("time_gap_model.txt", "time_gap_feature_engineer.pkl"),
        "has_time_gap_model",
    ),
    ComponentSpec(
        "probability_weighted",
        ("probability_model_weighted.txt", "probability_feature_engineer_weighted.pkl"),
        "has_probability_model",
    ),
    ComponentSpec(
        "probability_calibrated",
        ("probability_model_calibrated.txt", "probability_feature_engineer_calibrated.pkl"),
        "has_calibrated_model",
    ),
    ComponentSpec(
        "probability_contender",
        ("probability_model_contender.txt", "probability_feature_engineer_contender.pkl"),
        "has_contender_model",
    ),
    ComponentSpec(
        "lambdarank",
        ("lambdarank_model.txt", "lambdarank_feature_engineer.pkl"),
        "has_lambdarank_model",
    ),
    ComponentSpec(
        "day_menu_ranker",
        ("bucket_model_daymenu.txt", "bucket_feature_engineer_daymenu.pkl"),
        "has_bucket_daymenu",
    ),
    ComponentSpec(
        "gc_outlook",
        (
            "gc_outlook_bucket_model.txt",
            "gc_outlook_bucket_feature_engineer.pkl",
            "gc_outlook_contender_model.txt",
            "gc_outlook_contender_feature_engineer.pkl",
            "gc_outlook_metadata.json",
        ),
    ),
    ComponentSpec(
        "dnf",
        ("dnf_model.txt", "dnf_model_features.json", "dnf_events.parquet", "dnf_head_metadata.json"),
    ),
    ComponentSpec("win_calibration", ("win_calibration.json",)),
    ComponentSpec(
        "contested_elo",
        ("contested_rating_snapshots.parquet", "contested_rating_snapshots.meta.json"),
    ),
    ComponentSpec("day_menu", ("day_menu_v1.json", "day_menu_kernels.parquet")),
)


def _sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _component_required(spec: ComponentSpec, model_dir: Path, metadata: Mapping[str, Any]) -> bool:
    if spec.name in {"registry_metadata", "main_bucket"}:
        return True
    if spec.metadata_flag is not None:
        return bool(metadata.get(spec.metadata_flag, False))
    # Auxiliary systems pre-date registry flags.  Once any file in their
    # group exists, the whole group becomes required; this exposes interrupted
    # or partial publication instead of quietly omitting it from the release.
    return any((model_dir / filename).exists() for filename in spec.files)


def _generation_metadata(model_dir: Path) -> dict[str, Any]:
    registry = _read_json(model_dir / "metadata.json")
    gc = _read_json(model_dir / "gc_outlook_metadata.json")
    dnf = _read_json(model_dir / "dnf_head_metadata.json")
    elo = _read_json(model_dir / "contested_rating_snapshots.meta.json")
    menu = _read_json(model_dir / "day_menu_v1.json")
    win = _read_json(model_dir / "win_calibration.json")
    return {
        "registry_saved_at": registry.get("saved_at"),
        "registry_training_timestamp": registry.get("training_info", {}).get("timestamp")
        if isinstance(registry.get("training_info"), dict)
        else None,
        "gc_saved_at": gc.get("saved_at"),
        "dnf_trained_at": dnf.get("trained_at"),
        "elo_updated_at": elo.get("updated_at"),
        "day_menu_version": menu.get("version"),
        "day_menu_frozen_at": menu.get("frozen_at"),
        "win_calibration_fitted_at": win.get("fitted_at"),
    }


def _observed_at(files: Iterable[Path]) -> str:
    mtimes = [path.stat().st_mtime for path in files if path.exists()]
    timestamp = max(mtimes, default=0.0)
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def _release_id(components: Mapping[str, Any]) -> str:
    identity = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "components": components,
    }
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def build_release_manifest(model_dir: Path | str) -> dict[str, Any]:
    """Build a deterministic manifest for the current artifact directory.

    Missing expected paths remain in the inventory with ``exists=false``.
    Consequently the manifest itself can be generated for a partial/legacy
    registry and a later validator can provide precise diagnostics.
    """

    model_dir = Path(model_dir)
    metadata = _read_json(model_dir / "metadata.json")
    components: dict[str, Any] = {}
    existing_paths: list[Path] = []
    artifact_count = 0
    total_size = 0

    for spec in COMPONENT_SPECS:
        files = []
        for filename in spec.files:
            path = model_dir / filename
            exists = path.is_file()
            entry: dict[str, Any] = {"path": filename, "exists": exists}
            if exists:
                size = path.stat().st_size
                entry.update({"size": size, "sha256": _sha256(path)})
                existing_paths.append(path)
                artifact_count += 1
                total_size += size
            else:
                entry.update({"size": None, "sha256": None})
            files.append(entry)

        required = _component_required(spec, model_dir, metadata)
        components[spec.name] = {
            "required": required,
            "complete": all(item["exists"] for item in files),
            "files": files,
        }

    release_id = _release_id(components)
    required_components = [name for name, item in components.items() if item["required"]]
    incomplete_required = [
        name for name in required_components if not components[name]["complete"]
    ]

    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "release_id": release_id,
        "observed_at": _observed_at(existing_paths),
        "artifact_count": artifact_count,
        "total_size": total_size,
        "complete": not incomplete_required,
        "incomplete_required_components": incomplete_required,
        "generation": _generation_metadata(model_dir),
        "components": components,
    }


def write_release_manifest(model_dir: Path | str) -> Path:
    """Atomically refresh and return the production manifest path."""

    model_dir = Path(model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)
    destination = model_dir / MANIFEST_FILENAME
    payload = json.dumps(build_release_manifest(model_dir), indent=2, sort_keys=True) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{MANIFEST_FILENAME}.", suffix=".tmp", dir=model_dir
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return destination


def load_release_manifest(model_dir: Path | str) -> dict[str, Any]:
    """Load a previously published manifest."""

    path = Path(model_dir) / MANIFEST_FILENAME
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"Production release manifest must be a JSON object: {path}")
    return value


def tracked_artifact_paths() -> tuple[str, ...]:
    """Return every serving artifact path known to the manifest schema."""

    return tuple(filename for spec in COMPONENT_SPECS for filename in spec.files)


def validate_release_manifest(model_dir: Path | str) -> ReleaseValidationReport:
    """Verify that the published manifest exactly matches bytes on disk.

    Validation is intentionally strict and content-based.  A trainer that
    writes only part of a component, a hand-edited model, or a stale manifest
    all fail before serving imports or deserializes a model.  JSON artifacts
    receive a syntax check as well, catching a coherently re-manifested but
    unreadable sidecar.
    """

    model_dir = Path(model_dir)
    manifest_path = model_dir / MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise ProductionReleaseError(
            f"Production release manifest is missing: {manifest_path}. "
            "Refresh or retrain the production artifacts before serving."
        )

    try:
        manifest = load_release_manifest(model_dir)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ProductionReleaseError(
            f"Production release manifest is unreadable: {manifest_path}: {exc}"
        ) from exc

    schema_version = manifest.get("schema_version")
    if schema_version != MANIFEST_SCHEMA_VERSION:
        raise ProductionReleaseError(
            "Unsupported production release manifest schema "
            f"{schema_version!r}; expected {MANIFEST_SCHEMA_VERSION}."
        )

    components = manifest.get("components")
    if not isinstance(components, dict):
        raise ProductionReleaseError("Production release manifest has no component map.")
    expected_components = {spec.name for spec in COMPONENT_SPECS}
    actual_components = set(components)
    if actual_components != expected_components:
        missing = sorted(expected_components - actual_components)
        unknown = sorted(actual_components - expected_components)
        raise ProductionReleaseError(
            f"Production release component schema mismatch; missing={missing}, "
            f"unknown={unknown}."
        )

    recorded_release_id = manifest.get("release_id")
    if recorded_release_id != _release_id(components):
        raise ProductionReleaseError(
            "Production release manifest identity does not match its component inventory."
        )

    current = build_release_manifest(model_dir)
    if not current["complete"]:
        missing = ", ".join(current["incomplete_required_components"])
        raise ProductionReleaseError(
            f"Production release has incomplete required components: {missing}."
        )
    if not manifest.get("complete", False):
        missing = ", ".join(manifest.get("incomplete_required_components", []))
        raise ProductionReleaseError(
            f"Published production release is marked incomplete: {missing}."
        )
    if recorded_release_id != current["release_id"]:
        raise ProductionReleaseError(
            "Production artifacts do not match the published release manifest "
            f"(published {recorded_release_id}, observed {current['release_id']})."
        )

    for filename in tracked_artifact_paths():
        if not filename.endswith(".json"):
            continue
        path = model_dir / filename
        if not path.is_file():
            continue
        try:
            json.loads(path.read_text())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProductionReleaseError(
                f"Production JSON artifact is unreadable: {path}: {exc}"
            ) from exc

    return ReleaseValidationReport(
        release_id=str(recorded_release_id),
        artifact_count=int(current["artifact_count"]),
        total_size=int(current["total_size"]),
        component_count=len(current["components"]),
    )
