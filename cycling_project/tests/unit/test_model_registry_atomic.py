"""Transactional publication tests for :mod:`model_registry`."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from cycling_project.prediction_tools import model_registry as registry_module
from cycling_project.prediction_tools.model_registry import ModelRegistry
from cycling_project.prediction_tools.lambdarank_feature_contract import (
    make_lambdarank_contract_metadata,
)


class FakePredictor:
    def __init__(self, payload: str, *, fail: bool = False):
        self.payload = payload
        self.fail = fail
        self.feature_columns = ['feature_a']
        self.feature_engineer = {'kind': 'fake'}
        self.config = SimpleNamespace(temperature=1.25)

    def save(self, path: str) -> None:
        Path(path).write_text(self.payload)
        if self.fail:
            raise RuntimeError('simulated model serialization failure')

    def feature_contract_metadata(self):
        return make_lambdarank_contract_metadata(self.feature_columns)


def snapshot(directory: Path):
    return {
        path.relative_to(directory): path.read_bytes()
        for path in directory.rglob('*')
        if path.is_file()
    }


def seed_registry(path: Path) -> ModelRegistry:
    registry = ModelRegistry(str(path))
    registry.save(FakePredictor('original'), training_info={'seed': True})
    return registry


def test_failed_full_save_leaves_published_registry_unchanged(tmp_path):
    path = tmp_path / 'production'
    registry = seed_registry(path)
    before = snapshot(path)

    with pytest.raises(RuntimeError, match='serialization failure'):
        registry.save(FakePredictor('partial replacement', fail=True))

    assert snapshot(path) == before


def test_full_save_preserves_independently_managed_artifacts(tmp_path):
    path = tmp_path / "production"
    registry = seed_registry(path)
    auxiliary = path / "gc_outlook_metadata.json"
    auxiliary.write_text('{"saved_at": "separate-head"}')

    registry.save(FakePredictor("replacement"), training_info={"new": True})

    assert auxiliary.read_text() == '{"saved_at": "separate-head"}'
    assert (path / "bucket_model.txt").read_text() == "replacement"
    assert not list(tmp_path.glob('.production.staging-*'))


def test_failed_incremental_head_leaves_registry_unchanged(tmp_path):
    path = tmp_path / 'production'
    registry = seed_registry(path)
    metadata_path = path / 'metadata.json'
    metadata = json.loads(metadata_path.read_text())
    metadata['lambdarank_feature_contract'] = (
        make_lambdarank_contract_metadata(['feature_a'])
    )
    metadata_path.write_text(json.dumps(metadata))
    before = snapshot(path)

    with pytest.raises(RuntimeError, match='serialization failure'):
        registry.add_lambdarank(FakePredictor('partial head', fail=True))

    assert snapshot(path) == before
    assert not list(tmp_path.glob('.production.staging-*'))


def test_incremental_variant_publishes_files_and_metadata_together(tmp_path):
    path = tmp_path / 'production'
    registry = seed_registry(path)
    (path / 'unrelated-sidecar.dat').write_text('preserve me')

    registry.add_bucket_variant(
        FakePredictor('variant model'),
        'daymenu',
        training_info={'variant_run': 7},
    )

    metadata = json.loads((path / 'metadata.json').read_text())
    assert (path / 'bucket_model_daymenu.txt').read_text() == 'variant model'
    assert (path / 'bucket_feature_engineer_daymenu.pkl').exists()
    assert (path / 'unrelated-sidecar.dat').read_text() == 'preserve me'
    assert metadata['has_bucket_daymenu'] is True
    assert metadata['bucket_daymenu_feature_columns'] == ['feature_a']
    assert metadata['training_info']['variant_run'] == 7


def test_publish_failure_rolls_back_previous_registry(tmp_path, monkeypatch):
    path = tmp_path / 'production'
    registry = seed_registry(path)
    before = snapshot(path)
    real_replace = registry_module.os.replace

    def fail_install(source, destination):
        source = Path(source)
        destination = Path(destination)
        if '.production.staging-' in source.name and destination == path:
            raise OSError('simulated install failure')
        return real_replace(source, destination)

    monkeypatch.setattr(registry_module.os, 'replace', fail_install)

    with pytest.raises(OSError, match='install failure'):
        registry.add_bucket_variant(FakePredictor('new'), 'daymenu')

    assert snapshot(path) == before
    assert not list(tmp_path.glob('.production.staging-*'))
    assert not list(tmp_path.glob('.production.rollback-*'))
