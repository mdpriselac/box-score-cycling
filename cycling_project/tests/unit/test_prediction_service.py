from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from cycling_project.prediction_tools import prediction_service as serving


class FakeLambdaRank:
    config = SimpleNamespace(temperature=1.7)

    def predict_win_probabilities(self, frame):
        values = np.arange(1, len(frame) + 1, dtype=float)
        return values / values.sum()

    def predict_topk_probabilities(self, frame, k, n_samples):
        assert (k, n_samples) == (3, 2000)
        return np.full(len(frame), 0.5)


class FakeRanker:
    def __init__(self):
        self.extra_contender_ids = None

    def predict_race(self, frame, return_details, extra_contender_ids):
        assert return_details is True
        self.extra_contender_ids = extra_contender_ids
        return pd.DataFrame({
            "rider_id": frame["rider_id"].to_numpy(),
            "rider_name": frame["rider_name"].to_numpy(),
            "predicted_rank": np.arange(1, len(frame) + 1),
            "predicted_time_gap": np.arange(len(frame), dtype=float),
            "prob_win": np.full(len(frame), 0.1),
            "prob_podium": np.full(len(frame), 0.2),
            "prob_top5": np.full(len(frame), 0.3),
            "prob_top15": np.full(len(frame), 0.8),
        })


class FakeGCHead:
    def predict(self, frame):
        assert frame["state_attached"].all()
        return pd.DataFrame({
            "rider_id": frame["rider_id"],
            "gc_outlook_win_p": [0.7, 0.3],
        })


@pytest.fixture
def frames():
    matched = pd.DataFrame({
        "rider_id": [11, 22],
        "rider_name": ["A", "B"],
        "team_name": ["Red", "Blue"],
    })
    return {
        "snapshots": pd.DataFrame({"rider_id": [11, 22]}),
        "matched": matched,
        "state": pd.DataFrame({"rider_id": [11, 22]}),
    }


@pytest.fixture
def patched_pipeline(monkeypatch):
    state_calls = []

    def assemble(snapshots, matched, field_features, profile, form_status, asof_date=None):
        form_status["assembled"] = True
        return matched[["rider_id", "rider_name"]].copy()

    def attach_state(frame, state):
        state_calls.append(state)
        out = frame.copy()
        out["state_attached"] = state is not None
        return out

    def attach_stack(
        frame, time_gap, lambdarank, rating_snapshots, signature_context, asof_date
    ):
        out = frame.copy()
        out["oof_time_gap_pred"] = [4.0, 8.0]
        out["oof_lambdarank_win_p"] = [0.4, 0.6]
        out["contested_rating"] = [1501.0, 1499.0]
        out["contested_rating_n"] = [20, 12]
        out["signature_seen"] = signature_context is not None
        return out

    def pricing(result, pred_df, profile, **kwargs):
        out = result.copy()
        out["dnf_p"] = [0.05, 0.1]
        out["blend_win_p"] = out["lambdarank_win_p"]
        return out, []

    monkeypatch.setattr(serving, "assemble_prediction_df", assemble)
    monkeypatch.setattr(serving, "attach_race_state", attach_state)
    monkeypatch.setattr(serving, "attach_stack_features", attach_stack)
    monkeypatch.setattr(serving, "apply_pricing_layer", pricing)
    return state_calls


def make_service(ranker=None, **overrides):
    values = dict(
        time_gap_predictor=object(),
        race_ranker=ranker or FakeRanker(),
        lambdarank_predictor=FakeLambdaRank(),
        model_version="release-1",
    )
    values.update(overrides)
    return serving.PredictionService(serving.ServingArtifacts(**values), "/db.sqlite")


def make_request(frames, **overrides):
    values = dict(
        snapshots=frames["snapshots"],
        matched_riders=frames["matched"],
        field_features={"field_size": 2},
        profile={"competition_type": "stage", "race_category": "wt"},
        target_type="stage",
        stage_number=4,
        race_state=frames["state"],
    )
    values.update(overrides)
    return serving.PredictionRequest(**values)


def test_stage_runs_all_heads_and_attaches_state(
    frames, patched_pipeline
):
    result = make_service().predict(make_request(frames))

    assert patched_pipeline == [frames["state"]]
    assert result.model_version == "release-1"
    assert result.form_status == {"assembled": True}
    assert result.board == "production"
    assert result.gc_outlook is None
    assert result.lambdarank_temperature == 1.7
    assert result.riders["team"].tolist() == ["Red", "Blue"]
    assert result.riders["dnf_p"].tolist() == [0.05, 0.1]
    assert result.riders["predicted_time_gap"].tolist() == [0.0, 1.0]
    assert result.riders["contested_rating"].tolist() == [1501.0, 1499.0]


def test_gc_keeps_main_models_prerace_and_uses_state_only_for_outlook(
    frames, patched_pipeline
):
    result = make_service(gc_outlook_head=FakeGCHead()).predict(
        make_request(
            frames,
            target_type="gc",
            stage_number=None,
            profile={"competition_type": "gc", "race_category": "wt"},
        )
    )

    assert patched_pipeline == [None, frames["state"]]
    assert not result.feature_frame["state_attached"].any()
    assert result.gc_outlook["gc_outlook_win_p"].tolist() == [0.7, 0.3]
    assert result.gc_outlook["team"].tolist() == ["Red", "Blue"]


def test_day_menu_controls_board_and_expands_contender_pool(
    monkeypatch, frames, patched_pipeline
):
    menu = SimpleNamespace(items=["res_2"])
    day_artifacts = serving.DayMenuArtifacts(object(), menu, pd.DataFrame())
    monkeypatch.setattr(
        serving.day_menu_mod,
        "serving_board_scores",
        lambda *args, **kwargs: np.array([9.0, 1.0]),
    )
    ranker = FakeRanker()
    result = make_service(ranker=ranker, day_menu=day_artifacts).predict(
        make_request(frames, day_key={"res_2": 1.0}, race_date="2026-08-30")
    )

    assert result.board == "daymenu"
    assert result.day_key == {"res_2": 1.0}
    assert result.riders["rider_id"].tolist() == [22, 11]
    assert result.riders["daymenu_rank"].tolist() == [1, 2]
    assert ranker.extra_contender_ids == {11, 22}


def test_one_day_signature_context_is_built_in_service(
    monkeypatch, frames, patched_pipeline
):
    seen = {}

    def build(refs, field_features, db_path):
        seen.update(refs=refs, field=field_features, db=db_path)
        return {"signature": "context"}

    monkeypatch.setattr(serving, "build_serving_signature_context", build)
    result = make_service().predict(
        make_request(
            frames,
            target_type="one_day",
            stage_number=None,
            race_state=None,
            reference_competition_ids=[101, 102],
            profile={"competition_type": "one_day", "race_category": "wt"},
        )
    )

    assert seen == {
        "refs": [101, 102],
        "field": {"field_size": 2},
        "db": "/db.sqlite",
    }
    assert result.feature_frame["signature_seen"].all()


def test_request_rejects_incoherent_target_fields(frames):
    with pytest.raises(ValueError, match="stage_number is required"):
        make_request(frames, stage_number=None)
    with pytest.raises(ValueError, match="only valid"):
        make_request(frames, target_type="gc")
    with pytest.raises(ValueError, match="race_date"):
        make_request(frames, day_key={"res_2": 1.0}, race_date=None)


def test_from_production_validates_before_loading_models(monkeypatch, tmp_path):
    calls = []

    def reject(path):
        calls.append(path)
        raise RuntimeError("invalid release")

    monkeypatch.setattr(serving, "validate_release_manifest", reject)
    monkeypatch.setattr(
        serving,
        "ModelRegistry",
        lambda *_: pytest.fail("registry loaded before release validation"),
    )

    with pytest.raises(RuntimeError, match="invalid release"):
        serving.PredictionService.from_production(tmp_path)
    assert calls == [tmp_path]
