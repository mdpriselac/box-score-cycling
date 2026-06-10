"""
Train the production GC outlook head on all checkpoint data.

Mirrors train_production_model.py conventions: trains on everything, with
the chronologically-last 5% of checkpoint groups held out purely for
LightGBM early stopping. Saves gc_outlook_* files alongside the main
ensemble in models/production (GCOutlookHead.load picks them up; the main
ModelRegistry is untouched).

Run directly or via the pipeline step:
    uv run python -m cycling_project.prediction_tools.train_gc_outlook_production
    uv run python -m cycling_project.update_pipeline --only train-gc-outlook
"""

from datetime import datetime
from pathlib import Path

from cycling_project.prediction_tools.gc_outlook import (
    GCOutlookHead,
    load_training_frame,
)
from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

MODEL_DIR = Path(__file__).parent.parent.parent / "models" / "production"


def main():
    print("=" * 70)
    print("GC OUTLOOK HEAD — PRODUCTION TRAINING (ALL CHECKPOINT DATA)")
    print("=" * 70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    df = load_training_frame()
    print(f"Checkpoint rows: {len(df):,}")
    print(f"Checkpoint groups: {df['competition_id'].nunique():,}")
    print(
        f"Date range: {df['competition_date'].min().date()} "
        f"to {df['competition_date'].max().date()}"
    )

    # Last 5% of dates for early stopping only (same convention as
    # train_production_model.py — all data informs the model).
    comp_dates = (
        df.groupby('competition_id')['competition_date'].first().sort_values()
    )
    cutoff_date = comp_dates.iloc[int(len(comp_dates) * 0.95)]
    train = df[df['competition_date'] < cutoff_date].copy()
    early_stop = df[df['competition_date'] >= cutoff_date].copy()
    print(
        f"\nTrain:      {len(train):>8,} rows "
        f"({train['competition_id'].nunique():,} checkpoint groups)"
    )
    print(
        f"Early-stop: {len(early_stop):>8,} rows "
        f"({early_stop['competition_id'].nunique():,} checkpoint groups)"
    )

    head, info = GCOutlookHead.train(train, early_stop)
    print(f"\nBucket best iteration:    {info['bucket_best_iteration']}")
    print(f"Contender best iteration: {info['contender_best_iteration']}")

    head.save(str(MODEL_DIR))
    print(f"\nGC outlook head saved to {MODEL_DIR}")
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == '__main__':
    main()
