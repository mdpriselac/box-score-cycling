"""
GC outlook head — state-aware final-GC prediction for ongoing stage races.

Predicts each rider's FINAL GC bucket from the within-race state after k
completed stages. Validated 2026-06-09 (experiment_log.md "Mid-race GC
head"): vs carry-forward (final GC = current GC) +18.3pp winner capture
early-race / +5.8pp mid (5/5 folds), parity late; vs the blind pre-race
prediction +19.8pp winner with log loss 1.69 -> 1.11. Carry-forward cannot
produce probabilities, so this head is the in-play GC-market product.

Architecture mirrors the validated experiment exactly: training rows are
(rider x gc competition x checkpoint k=1..N-1) — the state after k stages
is the rider_race_state row keyed to stage k+1 — with the final GC bucket
as target, trained through the production contender-cascade machinery.
The head only predicts riders WITH state (riders in the reconstructed
standings); it deliberately does not handle pre-race GC prediction, which
remains the main production stack's job.

Persistence is registry-style but self-contained (gc_outlook_* files in
the same models directory; GCOutlookHead.load returns None when absent),
so ModelRegistry and the main ensemble are untouched.

Training entry point: train_gc_outlook_production.py (pipeline step
'train-gc-outlook'). Inference: web/app.py attaches live state via
prediction_tools.live_race_state and calls GCOutlookHead.predict.
"""

import json
import pickle
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

from cycling_project.prediction_tools.bucket_predictor import OrdinalBucketPredictor
from cycling_project.prediction_tools.data_pipeline import (
    CyclingDataPipeline,
    DataConfig,
)
from cycling_project.prediction_tools.probability_predictor import ProbabilityPredictor
from cycling_project.prediction_tools.production_release import write_release_manifest
from cycling_project.prediction_tools.training import ModelTrainer, TrainingConfig
from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

START_DATE = '2016-01-01'

# Production contender-cascade config — identical to the validated
# experiment (experiments/gc_checkpoint_head_cv.py) except n_estimators,
# which follows production training convention (2000 with early stopping)
# rather than the cross-experiment comparable cap of 500.
TRAIN_CONFIG = {
    'n_estimators': 2000,
    'early_stopping': 100,
    'contender_top_n': 15,
    'contender_learning_rate': 0.01,
    'contender_use_oof': True,
    'contender_n_classes': 5,
    'include_gradient_features': True,
}

# Synthetic group id = gc_comp_id * GROUP_FACTOR + checkpoint k (must match
# the experiment so numbers stay comparable).
GROUP_FACTOR = 1000

MODEL_FILES = {
    'bucket_model': 'gc_outlook_bucket_model.txt',
    'bucket_fe': 'gc_outlook_bucket_feature_engineer.pkl',
    'contender_model': 'gc_outlook_contender_model.txt',
    'contender_fe': 'gc_outlook_contender_feature_engineer.pkl',
    'metadata': 'gc_outlook_metadata.json',
}


# ---------------------------------------------------------------------------
# Training data assembly (canonical production copy of the validated
# experiment's assembly — gc_checkpoint_head_cv.py keeps its own copy as a
# frozen record of what was tested)
# ---------------------------------------------------------------------------

def _default_db_path() -> Path:
    return (
        Path(__file__).parent.parent
        / "webscrape_tools" / "database" / "database" / "cycling_races.db"
    )


def load_gc_base(db_path: Optional[str] = None) -> pd.DataFrame:
    """One row per (rider, gc competition): pre-race features + final bucket."""
    cfg = DataConfig(
        db_path=str(db_path or _default_db_path()),
        start_date=START_DATE,
        min_races_career=10,
        include_gradient_features=True,
    )
    pipeline = CyclingDataPipeline(cfg)
    df = pipeline.load_training_data(competition_types=['gc'])
    df['competition_date'] = pd.to_datetime(df['competition_date'])
    return df


def load_checkpoint_states(db_path: Optional[str] = None) -> pd.DataFrame:
    """Checkpoint states (k=1..N-1) joined to their race's GC competition."""
    state_cols_sql = ', '.join(
        f'rrs.{c}' for c in CyclingDataPipeline.RACE_STATE_FEATURE_COLS
    )
    query = f"""
        SELECT rrs.rider_id, gc.id AS gc_competition_id, {state_cols_sql}
        FROM rider_race_state rrs
        JOIN competitions c
            ON c.id = rrs.competition_id AND c.competition_type = 'stage'
        JOIN competitions gc
            ON gc.race_id = rrs.race_id AND gc.competition_type = 'gc'
    """
    conn = sqlite3.connect(str(db_path or _default_db_path()))
    try:
        return pd.read_sql_query(query, conn)
    finally:
        conn.close()


def build_checkpoint_frame(
    gc_base: pd.DataFrame, states: pd.DataFrame
) -> pd.DataFrame:
    """Replicate each (rider, gc) row once per checkpoint and attach state."""
    merged = gc_base.merge(
        states,
        left_on=['rider_id', 'competition_id'],
        right_on=['rider_id', 'gc_competition_id'],
        how='inner',
    )
    merged['stages_completed'] = merged['stages_completed'].astype(int)
    merged['competition_id'] = (
        merged['gc_competition_id'] * GROUP_FACTOR + merged['stages_completed']
    )
    merged['race_state_missing'] = 0
    return merged.drop(columns=['gc_competition_id'])


def load_training_frame(db_path: Optional[str] = None) -> pd.DataFrame:
    """Full checkpoint training frame (the production training set)."""
    gc_base = load_gc_base(db_path)
    states = load_checkpoint_states(db_path)
    frame = build_checkpoint_frame(gc_base, states)
    if frame.empty:
        raise RuntimeError(
            "No GC checkpoint rows — is rider_race_state built? "
            "Run: uv run python -m cycling_project.engineering_tools.stage_race_state"
        )
    return frame


# ---------------------------------------------------------------------------
# The head
# ---------------------------------------------------------------------------

class GCOutlookHead:
    """Bucket + contender pair predicting final GC from mid-race state."""

    def __init__(
        self,
        bucket_predictor: Optional[OrdinalBucketPredictor] = None,
        contender_predictor: Optional[ProbabilityPredictor] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.bucket_predictor = bucket_predictor
        self.contender_predictor = contender_predictor
        self.metadata = metadata or {}

    # ----- training -----

    @classmethod
    def train(
        cls,
        train_df: pd.DataFrame,
        early_stop_df: pd.DataFrame,
    ) -> Tuple['GCOutlookHead', Dict[str, Any]]:
        cfg = TrainingConfig(
            start_date=START_DATE,
            train_end_date=train_df['competition_date'].max().strftime('%Y-%m-%d'),
            val_end_date=early_stop_df['competition_date'].max().strftime('%Y-%m-%d'),
            bucket_n_estimators=TRAIN_CONFIG['n_estimators'],
            bucket_early_stopping=TRAIN_CONFIG['early_stopping'],
            probability_n_estimators=TRAIN_CONFIG['n_estimators'],
            probability_early_stopping=TRAIN_CONFIG['early_stopping'],
            time_gap_n_estimators=TRAIN_CONFIG['n_estimators'],
            time_gap_early_stopping=TRAIN_CONFIG['early_stopping'],
            contender_top_n=TRAIN_CONFIG['contender_top_n'],
            contender_learning_rate=TRAIN_CONFIG['contender_learning_rate'],
            contender_use_oof=TRAIN_CONFIG['contender_use_oof'],
            contender_n_classes=TRAIN_CONFIG['contender_n_classes'],
            include_gradient_features=TRAIN_CONFIG['include_gradient_features'],
            train_time_gap=False,
            train_probability=False,
            train_calibrated_probability=False,
            train_contender_probability=True,
            verbose=False,
        )
        trainer = ModelTrainer(cfg)
        bucket_pred, bucket_info = trainer.train_bucket_predictor(
            train_df, early_stop_df
        )
        contender_pred, contender_info = trainer.train_contender_predictor(
            train_df, early_stop_df, bucket_pred
        )
        info = {
            'bucket_best_iteration': bucket_info.get('best_iteration'),
            'contender_best_iteration': contender_info.get('best_iteration'),
            'n_train_rows': int(len(train_df)),
            'n_checkpoint_groups': int(train_df['competition_id'].nunique()),
        }
        head = cls(bucket_pred, contender_pred, metadata=info)
        return head, info

    # ----- persistence (registry-style file mechanics) -----

    def save(self, model_dir: str) -> None:
        base = Path(model_dir)
        base.mkdir(parents=True, exist_ok=True)

        self.bucket_predictor.save(str(base / MODEL_FILES['bucket_model']))
        with open(base / MODEL_FILES['bucket_fe'], 'wb') as f:
            pickle.dump({
                'feature_columns': self.bucket_predictor.feature_columns,
                'feature_engineer': self.bucket_predictor.feature_engineer,
            }, f)

        self.contender_predictor.save(str(base / MODEL_FILES['contender_model']))
        with open(base / MODEL_FILES['contender_fe'], 'wb') as f:
            pickle.dump({
                'feature_columns': self.contender_predictor.feature_columns,
                'feature_engineer': self.contender_predictor.feature_engineer,
                'temperature': self.contender_predictor.config.temperature,
            }, f)

        metadata = dict(self.metadata)
        metadata['saved_at'] = datetime.now().isoformat()
        metadata['train_config'] = TRAIN_CONFIG
        with open(base / MODEL_FILES['metadata'], 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
        write_release_manifest(base)
        logger.info("GC outlook head saved to %s", base)

    @classmethod
    def load(cls, model_dir: str) -> Optional['GCOutlookHead']:
        """Load the head from a models directory, or None if not present."""
        base = Path(model_dir)
        bucket_path = base / MODEL_FILES['bucket_model']
        contender_path = base / MODEL_FILES['contender_model']
        if not bucket_path.exists() or not contender_path.exists():
            return None

        bucket = OrdinalBucketPredictor()
        bucket.load(str(bucket_path))
        with open(base / MODEL_FILES['bucket_fe'], 'rb') as f:
            fe = pickle.load(f)
            bucket.feature_columns = fe['feature_columns']
            bucket.feature_engineer = fe['feature_engineer']

        contender = ProbabilityPredictor()
        contender.load(str(contender_path))
        with open(base / MODEL_FILES['contender_fe'], 'rb') as f:
            fe = pickle.load(f)
            contender.feature_columns = fe['feature_columns']
            contender.feature_engineer = fe['feature_engineer']
            if 'temperature' in fe:
                contender.config.temperature = fe['temperature']

        metadata: Dict[str, Any] = {}
        meta_path = base / MODEL_FILES['metadata']
        if meta_path.exists():
            with open(meta_path) as f:
                metadata = json.load(f)
        return cls(bucket, contender, metadata)

    # ----- inference -----

    def predict(self, frame: pd.DataFrame, top_n: int = 15) -> pd.DataFrame:
        """
        Predict final-GC outlook for a state-attached prediction frame.

        Only riders WITH state (race_state_missing == 0, i.e. present in the
        reconstructed standings) are predicted — the head never trained on
        missing-state rows; pre-race GC prediction stays with the main stack.

        Returns one row per predicted rider: outlook_rank (1 = best),
        cumulative gc_outlook_{win,podium,top5,top15}_p for the top-n
        contenders (NaN beyond), plus current standings passthrough columns.
        """
        df = frame
        if 'race_state_missing' in df.columns:
            df = df[df['race_state_missing'] == 0]
        df = df.copy()
        if df.empty:
            return pd.DataFrame()

        expected = self.bucket_predictor.predict_continuous(df)

        out = df[['rider_id']].copy()
        if 'rider_name' in df.columns:
            out['rider_name'] = df['rider_name'].values
        for col in ('gc_rank_current', 'gc_gap_to_leader_s', 'stages_completed'):
            if col in df.columns:
                out[col] = df[col].values
        out['expected_bucket'] = expected

        contender_mask = pd.Series(expected).rank(method='first').values <= top_n
        out['is_contender'] = contender_mask

        prob_cols = {
            'gc_outlook_win_p': 1,
            'gc_outlook_podium_p': 2,
            'gc_outlook_top5_p': 3,
            'gc_outlook_top15_p': 4,
        }
        for col in prob_cols:
            out[col] = np.nan
        if contender_mask.any():
            cont_df = df[contender_mask].copy()
            cont_df['classifier_expected_bucket'] = expected[contender_mask]
            proba = self.contender_predictor.predict_proba(cont_df)  # padded to 8
            for col, n_classes in prob_cols.items():
                out.loc[contender_mask, col] = proba[:, :n_classes].sum(axis=1)

        out = out.sort_values('expected_bucket').reset_index(drop=True)
        out['outlook_rank'] = np.arange(1, len(out) + 1)
        return out
