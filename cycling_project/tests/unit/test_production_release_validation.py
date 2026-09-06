import json

import pytest

from cycling_project.prediction_tools.production_release import (
    COMPONENT_SPECS,
    MANIFEST_FILENAME,
    MANIFEST_SCHEMA_VERSION,
    ProductionReleaseError,
    tracked_artifact_paths,
    validate_release_manifest,
    write_release_manifest,
)


def _complete_release(path):
    path.mkdir()
    flags = {
        spec.metadata_flag: True
        for spec in COMPONENT_SPECS
        if spec.metadata_flag is not None
    }
    for filename in tracked_artifact_paths():
        artifact = path / filename
        if artifact.exists():
            continue
        if filename == "metadata.json":
            artifact.write_text(json.dumps(flags))
        elif filename.endswith(".json"):
            artifact.write_text("{}")
        else:
            artifact.write_bytes(f"artifact:{filename}".encode())
    write_release_manifest(path)
    return path


def test_valid_release_returns_content_identity(tmp_path):
    model_dir = _complete_release(tmp_path / "production")

    report = validate_release_manifest(model_dir)

    assert len(report.release_id) == 64
    assert report.artifact_count == len(tracked_artifact_paths())
    assert report.component_count == len(COMPONENT_SPECS)


def test_missing_manifest_fails_before_serving(tmp_path):
    model_dir = tmp_path / "production"
    model_dir.mkdir()

    with pytest.raises(ProductionReleaseError, match="manifest is missing"):
        validate_release_manifest(model_dir)


def test_changed_artifact_rejects_stale_manifest(tmp_path):
    model_dir = _complete_release(tmp_path / "production")
    (model_dir / "bucket_model.txt").write_text("changed after publication")

    with pytest.raises(ProductionReleaseError, match="do not match"):
        validate_release_manifest(model_dir)


def test_incomplete_required_component_is_rejected(tmp_path):
    model_dir = _complete_release(tmp_path / "production")
    (model_dir / "dnf_events.parquet").unlink()

    with pytest.raises(ProductionReleaseError, match="incomplete required"):
        validate_release_manifest(model_dir)


def test_manifest_schema_drift_is_rejected(tmp_path):
    model_dir = _complete_release(tmp_path / "production")
    manifest_path = model_dir / MANIFEST_FILENAME
    manifest = json.loads(manifest_path.read_text())
    manifest["schema_version"] = MANIFEST_SCHEMA_VERSION + 1
    manifest_path.write_text(json.dumps(manifest))

    with pytest.raises(ProductionReleaseError, match="Unsupported"):
        validate_release_manifest(model_dir)


def test_malformed_json_is_rejected_even_when_re_manifested(tmp_path):
    model_dir = _complete_release(tmp_path / "production")
    (model_dir / "win_calibration.json").write_text("{not-json")
    write_release_manifest(model_dir)

    with pytest.raises(ProductionReleaseError, match="JSON artifact"):
        validate_release_manifest(model_dir)
