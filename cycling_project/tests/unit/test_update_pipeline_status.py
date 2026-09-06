"""Process-status and publication-order tests for the update pipeline."""

from argparse import Namespace

from cycling_project import update_pipeline
from cycling_project.update_pipeline import PipelineConfig, StepResult


def _args():
    return Namespace(
        dry_run=False,
        only=None,
        skip_scrape=False,
        skip_migrate=False,
        skip_features=False,
        skip_train=False,
        skip_lambdarank=False,
    )


def _config(tmp_path):
    return PipelineConfig(
        project_root=tmp_path,
        scraped_data_dir=tmp_path / "scraped",
        db_path=tmp_path / "db.sqlite",
        model_dir=tmp_path / "models",
    )


def test_failed_main_training_stops_dependent_publication(tmp_path, monkeypatch):
    calls = []

    monkeypatch.setattr(
        update_pipeline.PipelineConfig, "from_defaults",
        classmethod(lambda cls: _config(tmp_path)),
    )
    monkeypatch.setattr(update_pipeline, "determine_scrape_targets", lambda _: [])
    monkeypatch.setattr(update_pipeline, "print_summary", lambda _: None)

    def fake_run_step(name, _func, *_args, **_kwargs):
        calls.append(name)
        return StepResult(
            name=name,
            success=name != "Train Production Model",
            duration=0.0,
            summary="test",
            error="failed" if name == "Train Production Model" else None,
        )

    monkeypatch.setattr(update_pipeline, "run_step", fake_run_step)

    assert update_pipeline.run_pipeline(_args()) is False
    assert calls[-1] == "Train Production Model"
    assert "Train LambdaRank Head" not in calls
    assert "Train GC Outlook Head" not in calls
    assert "Train DNF Head" not in calls


def test_noncritical_failure_continues_but_reports_unsuccessful(
    tmp_path, monkeypatch
):
    calls = []

    monkeypatch.setattr(
        update_pipeline.PipelineConfig, "from_defaults",
        classmethod(lambda cls: _config(tmp_path)),
    )
    monkeypatch.setattr(update_pipeline, "determine_scrape_targets", lambda _: [])
    monkeypatch.setattr(update_pipeline, "print_summary", lambda _: None)

    def fake_run_step(name, _func, *_args, **_kwargs):
        calls.append(name)
        return StepResult(
            name=name,
            success=name != "Stage-Race State",
            duration=0.0,
            summary="test",
            error="failed" if name == "Stage-Race State" else None,
        )

    monkeypatch.setattr(update_pipeline, "run_step", fake_run_step)

    assert update_pipeline.run_pipeline(_args()) is False
    assert "Train DNF Head" in calls
    assert "Validate Production Release" in calls


def test_release_validation_failure_makes_pipeline_unsuccessful(
    tmp_path, monkeypatch
):
    calls = []
    monkeypatch.setattr(
        update_pipeline.PipelineConfig, "from_defaults",
        classmethod(lambda cls: _config(tmp_path)),
    )
    monkeypatch.setattr(update_pipeline, "determine_scrape_targets", lambda _: [])
    monkeypatch.setattr(update_pipeline, "print_summary", lambda _: None)

    def fake_run_step(name, _func, *_args, **_kwargs):
        calls.append(name)
        failed = name == "Validate Production Release"
        return StepResult(
            name=name,
            success=not failed,
            duration=0.0,
            summary="test",
            error="invalid release" if failed else None,
        )

    monkeypatch.setattr(update_pipeline, "run_step", fake_run_step)

    assert update_pipeline.run_pipeline(_args()) is False
    assert calls[-1] == "Validate Production Release"
