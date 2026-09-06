import hashlib
import json

from cycling_project.prediction_tools.production_release import (
    COMPONENT_SPECS,
    MANIFEST_FILENAME,
    build_release_manifest,
    load_release_manifest,
    tracked_artifact_paths,
    write_release_manifest,
)


def _seed_complete_release(path):
    path.mkdir()
    flags = {
        spec.metadata_flag: True
        for spec in COMPONENT_SPECS
        if spec.metadata_flag is not None
    }
    (path / "metadata.json").write_text(json.dumps({"saved_at": "2026-08-29", **flags}))
    for filename in tracked_artifact_paths():
        artifact = path / filename
        if not artifact.exists():
            artifact.write_bytes(f"payload:{filename}".encode())


def test_manifest_inventories_every_production_serving_artifact(tmp_path):
    model_dir = tmp_path / "production"
    _seed_complete_release(model_dir)

    manifest = build_release_manifest(model_dir)

    entries = {
        item["path"]: item
        for component in manifest["components"].values()
        for item in component["files"]
    }
    assert set(entries) == set(tracked_artifact_paths())
    assert manifest["complete"] is True
    assert manifest["artifact_count"] == len(tracked_artifact_paths())
    expected = hashlib.sha256((model_dir / "dnf_model.txt").read_bytes()).hexdigest()
    assert entries["dnf_model.txt"]["sha256"] == expected


def test_release_identity_is_deterministic_and_content_addressed(tmp_path):
    model_dir = tmp_path / "production"
    _seed_complete_release(model_dir)

    first = build_release_manifest(model_dir)
    second = build_release_manifest(model_dir)
    assert first == second

    (model_dir / "win_calibration.json").write_text("changed")
    changed = build_release_manifest(model_dir)
    assert changed["release_id"] != first["release_id"]


def test_partial_auxiliary_component_is_required_and_reported(tmp_path):
    model_dir = tmp_path / "production"
    model_dir.mkdir()
    (model_dir / "metadata.json").write_text("{}")
    (model_dir / "bucket_model.txt").write_text("bucket")
    (model_dir / "bucket_feature_engineer.pkl").write_text("features")
    (model_dir / "dnf_model.txt").write_text("partial")

    manifest = build_release_manifest(model_dir)

    assert manifest["components"]["dnf"]["required"] is True
    assert manifest["components"]["dnf"]["complete"] is False
    assert manifest["complete"] is False
    assert manifest["incomplete_required_components"] == ["dnf"]


def test_metadata_flag_makes_missing_optional_head_a_release_error(tmp_path):
    model_dir = tmp_path / "production"
    model_dir.mkdir()
    (model_dir / "metadata.json").write_text('{"has_lambdarank_model": true}')
    (model_dir / "bucket_model.txt").write_text("bucket")
    (model_dir / "bucket_feature_engineer.pkl").write_text("features")

    manifest = build_release_manifest(model_dir)

    assert manifest["components"]["lambdarank"]["required"] is True
    assert "lambdarank" in manifest["incomplete_required_components"]


def test_write_and_load_manifest_leave_no_staging_file(tmp_path):
    model_dir = tmp_path / "production"
    _seed_complete_release(model_dir)

    destination = write_release_manifest(model_dir)

    assert destination.name == MANIFEST_FILENAME
    assert load_release_manifest(model_dir) == build_release_manifest(model_dir)
    assert not list(model_dir.glob(f".{MANIFEST_FILENAME}.*.tmp"))
