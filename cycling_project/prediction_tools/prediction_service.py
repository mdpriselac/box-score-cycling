"""Canonical, UI-independent production prediction service.

This module owns the multi-head inference path shared by interactive and
headless callers.  Acquisition (startlists, odds and live results), rendering,
and prediction logging intentionally remain outside this boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from cycling_project.prediction_tools import day_menu as day_menu_mod
from cycling_project.prediction_tools.contest_signature_features import (
    build_serving_signature_context,
)
from cycling_project.prediction_tools.dnf_predictor import load_production_dnf_head
from cycling_project.prediction_tools.future_race_loader import (
    assemble_prediction_df,
    attach_stack_features,
    load_production_rating_snapshots,
)
from cycling_project.prediction_tools.gc_outlook import GCOutlookHead
from cycling_project.prediction_tools.live_race_state import attach_race_state
from cycling_project.prediction_tools.model_registry import ModelRegistry
from cycling_project.prediction_tools.pricing_layer import apply_pricing_layer
from cycling_project.prediction_tools.production_release import validate_release_manifest
from cycling_project.prediction_tools.win_calibration import load_corrector

TargetType = Literal["one_day", "stage", "gc"]


@dataclass(frozen=True)
class DayMenuArtifacts:
    """The optional retrieval-only ranking channel."""

    bucket_predictor: Any
    menu: day_menu_mod.DayMenu
    kernels: pd.DataFrame


@dataclass(frozen=True)
class ServingArtifacts:
    """Loaded model objects used by :class:`PredictionService`."""

    time_gap_predictor: Any
    race_ranker: Any
    lambdarank_predictor: Any = None
    win_corrector: Optional[Dict[str, Any]] = None
    dnf_bundle: Optional[Tuple] = None
    rating_snapshots: Optional[pd.DataFrame] = None
    gc_outlook_head: Optional[GCOutlookHead] = None
    day_menu: Optional[DayMenuArtifacts] = None
    model_version: str = ""
    load_warnings: Tuple[str, ...] = ()


@dataclass(frozen=True)
class PredictionRequest:
    """Inputs already acquired for one profile/field prediction.

    ``race_state`` is attached to the main models only for stage targets.  For
    GC targets it is reserved for the separately trained state-aware outlook
    head, matching training and current production serving semantics.
    """

    snapshots: pd.DataFrame
    matched_riders: pd.DataFrame
    field_features: Mapping[str, Any]
    profile: Mapping[str, Any]
    target_type: TargetType = "one_day"
    stage_number: Optional[int] = None
    race_state: Optional[pd.DataFrame] = None
    reference_competition_ids: Sequence[int] = ()
    signature_context: Optional[Mapping[str, Any]] = None
    day_key: Optional[Mapping[str, float]] = None
    race_date: Optional[Any] = None
    asof_date: Optional[str] = None

    def __post_init__(self) -> None:
        if self.target_type not in ("one_day", "stage", "gc"):
            raise ValueError(f"unsupported target_type: {self.target_type!r}")
        if self.target_type == "stage" and self.stage_number is None:
            raise ValueError("stage_number is required for a stage target")
        if self.target_type != "stage" and self.stage_number is not None:
            raise ValueError("stage_number is only valid for a stage target")
        if self.day_key and self.race_date is None:
            raise ValueError("race_date is required when day_key is set")


@dataclass
class PredictionResult:
    """Structured output from all applicable production heads."""

    riders: pd.DataFrame
    feature_frame: pd.DataFrame
    gc_outlook: Optional[pd.DataFrame]
    warnings: List[str] = field(default_factory=list)
    board: Literal["production", "daymenu"] = "production"
    day_key: Optional[Dict[str, float]] = None
    form_status: Dict[str, Any] = field(default_factory=dict)
    model_version: str = ""
    lambdarank_temperature: Optional[float] = None


class PredictionService:
    """Run the canonical advanced serving path without UI or CLI concerns."""

    def __init__(self, artifacts: ServingArtifacts, db_path: Optional[str] = None):
        self.artifacts = artifacts
        self.db_path = db_path

    @classmethod
    def from_production(
        cls,
        model_dir: str | Path,
        db_path: Optional[str] = None,
    ) -> "PredictionService":
        """Load the complete production stack, degrading optional heads safely."""
        model_dir = Path(model_dir)
        release = validate_release_manifest(model_dir)
        registry = ModelRegistry(str(model_dir))
        _, time_gap, ranker, lambdarank = registry.load_with_ranker(
            ranking_method="ensemble"
        )
        warnings: List[str] = []

        day_menu = None
        try:
            day_bucket = registry.load_bucket_variant("daymenu")
            if day_bucket is not None:
                day_menu = DayMenuArtifacts(
                    bucket_predictor=day_bucket,
                    menu=day_menu_mod.load_menu(model_dir / "day_menu_v1.json"),
                    kernels=day_menu_mod.load_kernels(
                        model_dir / "day_menu_kernels.parquet"
                    ),
                )
        except Exception as exc:  # optional serving channel
            warnings.append(f"Day-menu channel unavailable: {exc}")

        return cls(
            ServingArtifacts(
                time_gap_predictor=time_gap,
                race_ranker=ranker,
                lambdarank_predictor=lambdarank,
                win_corrector=load_corrector(model_dir),
                dnf_bundle=load_production_dnf_head(model_dir),
                rating_snapshots=load_production_rating_snapshots(),
                gc_outlook_head=GCOutlookHead.load(str(model_dir)),
                day_menu=day_menu,
                model_version=release.release_id,
                load_warnings=tuple(warnings),
            ),
            db_path=db_path,
        )

    def predict(self, request: PredictionRequest) -> PredictionResult:
        """Run base ranking, stack heads, pricing, DNF and optional GC outlook."""
        artifacts = self.artifacts
        warnings = list(artifacts.load_warnings)
        form_status: Dict[str, Any] = {}

        # Signature conditioning was gated only for one-day races.  Keep the
        # service boundary responsible for that invariant so callers cannot
        # accidentally feed reference signatures to stage/GC heads.
        signature_context = (
            request.signature_context if request.target_type == "one_day" else None
        )
        if (
            request.target_type == "one_day"
            and signature_context is None
            and request.reference_competition_ids
        ):
            try:
                signature_context = build_serving_signature_context(
                    [int(c) for c in request.reference_competition_ids],
                    dict(request.field_features),
                    self.db_path,
                )
            except Exception as exc:
                warnings.append(f"Signature features unavailable: {exc}")

        pred_df = assemble_prediction_df(
            request.snapshots,
            request.matched_riders,
            dict(request.field_features),
            dict(request.profile),
            form_status=form_status,
        )
        main_state = request.race_state if request.target_type == "stage" else None
        pred_df = attach_race_state(pred_df, main_state)
        pred_df = attach_stack_features(
            pred_df,
            artifacts.time_gap_predictor,
            artifacts.lambdarank_predictor,
            rating_snapshots=artifacts.rating_snapshots,
            signature_context=signature_context,
            asof_date=request.asof_date,
        )

        day_scores = None
        day_pool: Optional[set[int]] = None
        if request.day_key:
            if artifacts.day_menu is None:
                warnings.append(
                    "day_key set but day-menu channel unavailable; production board used"
                )
            else:
                dm = artifacts.day_menu
                day_scores = day_menu_mod.serving_board_scores(
                    pred_df,
                    dm.bucket_predictor,
                    dict(request.day_key),
                    dm.menu,
                    dm.kernels,
                    dict(request.field_features),
                    request.race_date,
                )
                order = np.argsort(np.argsort(day_scores))
                day_pool = set(
                    pred_df.loc[order < 15, "rider_id"].astype(int).tolist()
                )

        result = artifacts.race_ranker.predict_race(
            pred_df,
            return_details=True,
            extra_contender_ids=day_pool,
        )
        if day_scores is not None:
            score_map = dict(zip(pred_df["rider_id"].astype(int), day_scores))
            result["daymenu_score"] = result["rider_id"].astype(int).map(score_map)
            day_ranks = result["daymenu_score"].rank(method="first")
            result["daymenu_rank"] = day_ranks.astype(int)
            result["in_daymenu_pool"] = day_ranks <= 15

        lr_temperature = self._attach_lambdarank(result, pred_df)
        self._attach_elo(result, pred_df)
        self._attach_teams(result, request.matched_riders)

        result, pricing_warnings = apply_pricing_layer(
            result,
            pred_df,
            dict(request.profile),
            win_corrector=artifacts.win_corrector,
            dnf_bundle=artifacts.dnf_bundle,
            stage_number=request.stage_number,
            db_path=self.db_path,
            asof_date=request.asof_date,
        )
        warnings.extend(pricing_warnings)
        if day_scores is not None:
            result = result.sort_values("daymenu_rank", kind="stable").reset_index(
                drop=True
            )

        gc_outlook = self._predict_gc_outlook(request, form_status)
        if request.target_type == "gc" and request.race_state is not None:
            if artifacts.gc_outlook_head is None:
                warnings.append("GC outlook head not installed")
            elif gc_outlook is not None and gc_outlook.empty:
                warnings.append("GC outlook head produced no rows")

        return PredictionResult(
            riders=result,
            feature_frame=pred_df,
            gc_outlook=gc_outlook,
            warnings=warnings,
            board="daymenu" if day_scores is not None else "production",
            day_key=dict(request.day_key) if day_scores is not None else None,
            form_status=form_status,
            model_version=artifacts.model_version,
            lambdarank_temperature=lr_temperature,
        )

    def _attach_lambdarank(
        self, result: pd.DataFrame, pred_df: pd.DataFrame
    ) -> Optional[float]:
        head = self.artifacts.lambdarank_predictor
        if head is None:
            return None
        win_p = np.asarray(head.predict_win_probabilities(pred_df), dtype=float)
        podium_p = np.asarray(
            head.predict_topk_probabilities(pred_df, k=3, n_samples=2000),
            dtype=float,
        )
        rider_ids = pred_df["rider_id"].astype(int)
        result_ids = result["rider_id"].astype(int)
        result["lambdarank_win_p"] = result_ids.map(dict(zip(rider_ids, win_p)))
        result["lambdarank_podium_p"] = result_ids.map(
            dict(zip(rider_ids, podium_p))
        )
        config = getattr(head, "config", None)
        return getattr(config, "temperature", getattr(head, "temperature", None))

    @staticmethod
    def _attach_elo(result: pd.DataFrame, pred_df: pd.DataFrame) -> None:
        result_ids = result["rider_id"].astype(int)
        for column in ("contested_rating", "contested_rating_n"):
            if column in pred_df:
                values = dict(zip(pred_df["rider_id"].astype(int), pred_df[column]))
                result[column] = result_ids.map(values)

    @staticmethod
    def _attach_teams(result: pd.DataFrame, matched: pd.DataFrame) -> None:
        if "team_name" not in matched:
            return
        teams = dict(zip(matched["rider_id"].astype(int), matched["team_name"]))
        result["team"] = result["rider_id"].astype(int).map(teams).fillna("")

    def _predict_gc_outlook(
        self,
        request: PredictionRequest,
        form_status: Dict[str, Any],
    ) -> Optional[pd.DataFrame]:
        head = self.artifacts.gc_outlook_head
        if request.target_type != "gc" or request.race_state is None or head is None:
            return None
        frame = assemble_prediction_df(
            request.snapshots,
            request.matched_riders,
            dict(request.field_features),
            dict(request.profile),
            form_status=form_status,
        )
        frame = attach_race_state(frame, request.race_state)
        outlook = head.predict(frame)
        if outlook is not None and not outlook.empty:
            self._attach_teams(outlook, request.matched_riders)
        return outlook
