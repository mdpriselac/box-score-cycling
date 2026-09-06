"""
LambdaRank Probability Predictor for Cycling Race Predictions

Full-field LightGBM LambdaRank model that converts ranking scores to
per-race win probabilities via temperature-scaled softmax. This is the
probability head described in the Step A experiment (see experiment_log.md):
LambdaRank softmax gives near-perfect win calibration (~1.007) vs the
multiclass head's 0.866, at the cost of worse podium discrimination.

Scope: used as a *second* probability head alongside the existing
multiclass contender model. Not a replacement. Disagreements between the
two heads are surfaced in the UI and logged to `prediction_log` for
long-term book-comparison analysis.

Key design choices:
- **Full field**, not contender-filtered. Softmax normalization assumes
  the denominator is the actual field — any pre-filter biases implied
  probabilities against riders excluded from the top-N.
- **Relevance = 6 - place_bucket** (winner=6, podium=5, ..., finisher=0),
  matching the Step A experiment config.
- **Groups by competition_id** at training and inference time.
- **Temperature fit on held-out data** via NLL minimization over per-race
  softmax of ranking scores. Default T=1.0 if not fit.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Tuple, List
import warnings

import numpy as np
import pandas as pd

try:
    import lightgbm as lgb
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False
    warnings.warn("LightGBM not installed. Install with: pip install lightgbm")

from .feature_engineering import FeatureEngineer
from .lambdarank_feature_contract import (
    assert_stateless_feature_columns,
    build_lambdarank_feature_view,
    make_lambdarank_contract_metadata,
)


# ---------------------------------------------------------------------------
# Production config (single source of truth)
# ---------------------------------------------------------------------------
#
# These are the exact hyperparameters that back the shipped production
# LambdaRank head. Locked in 2026-04-18 after the 3-fold CV LR sweep
# (see experiment_log.md + experiments/lambdarank_cv.py); LR=0.01 was
# tested and gave indistinguishable metrics at 3.6x more iterations, so
# we keep LR=0.05.
#
# To adjust production hyperparameters, change these constants and
# retrain via `uv run python -m cycling_project.update_pipeline --only train-lambdarank`.

PRODUCTION_LGB_PARAMS: Dict[str, Any] = {
    'objective': 'lambdarank',
    'metric': 'ndcg',
    'ndcg_eval_at': [1, 3, 5, 10],
    'label_gain': [0, 1, 3, 7, 15, 31, 63],  # 2^rel - 1 for relevance 0..6
    'boosting_type': 'gbdt',
    'num_leaves': 63,
    'learning_rate': 0.05,
    'feature_fraction': 0.8,
    'bagging_fraction': 0.8,
    'bagging_freq': 5,
    'min_child_samples': 50,
    'verbose': -1,
    'seed': 42,
}

PRODUCTION_N_ESTIMATORS: int = 2000
PRODUCTION_EARLY_STOPPING: int = 300


@dataclass
class LambdaRankPredictorConfig:
    """Configuration for full-field LambdaRank probability head.

    Defaults match the shipped production config (see PRODUCTION_LGB_PARAMS).
    Override individual fields for experiments; for a strictly production-
    matching run, use the default.
    """

    lgb_params: Dict[str, Any] = field(
        default_factory=lambda: dict(PRODUCTION_LGB_PARAMS)
    )

    n_estimators: int = PRODUCTION_N_ESTIMATORS
    early_stopping_rounds: int = PRODUCTION_EARLY_STOPPING

    # Softmax temperature for score-to-probability conversion. Fit via
    # `calibrate_temperature` on held-out data; stored alongside the model.
    temperature: float = 1.0


def _relevance_from_bucket(place_bucket: np.ndarray) -> np.ndarray:
    """Map place_bucket (0=winner, 6=finisher, 7=DNF) to LambdaRank relevance.

    We keep DNF (bucket 7) at relevance 0 (same as bucket 6 finishers).
    Buckets 0..6 map to relevance 6..0 respectively.
    """
    clipped = np.clip(place_bucket.astype(int), 0, 7)
    rel = np.where(clipped == 7, 0, 6 - clipped)
    return rel.astype(int)


def _softmax_by_group(
    scores: np.ndarray,
    group_ids: np.ndarray,
    temperature: float = 1.0,
) -> np.ndarray:
    """Per-group softmax with temperature.

    Numerically stable: subtracts max within group before exp.
    """
    scaled = scores / temperature
    out = np.empty_like(scaled, dtype=float)

    # Group by contiguous runs when sorted; we don't assume sorting, so use
    # pandas for grouped max/sum.
    df = pd.DataFrame({'g': group_ids, 's': scaled})
    df['_idx'] = np.arange(len(df))
    max_per_group = df.groupby('g')['s'].transform('max')
    shifted = df['s'].values - max_per_group.values
    exp_shifted = np.exp(shifted)
    df['_exp'] = exp_shifted
    sum_per_group = df.groupby('g')['_exp'].transform('sum')
    out[df['_idx'].values] = exp_shifted / sum_per_group.values
    return out


class LambdaRankProbabilityPredictor:
    """
    LightGBM LambdaRank scorer → per-race softmax probability head.

    Trained on full fields (no contender pre-filter). Produces a raw
    ranking score per rider; per-race softmax over these scores yields
    a proper probability distribution that sums to 1 over the actual
    field — directly comparable to sportsbook implied odds after vig
    removal.

    Example usage:
        pred = LambdaRankProbabilityPredictor()
        pred.train(train_df, val_df)
        pred.calibrate_temperature(val_df)

        # At inference, `df` must contain 'competition_id' so scores can
        # be softmaxed per race.
        win_probs = pred.predict_win_probabilities(df)
        podium_probs = pred.predict_topk_probabilities(df, k=3)
    """

    def __init__(self, config: Optional[LambdaRankPredictorConfig] = None):
        if not HAS_LIGHTGBM:
            raise ImportError("LightGBM is required. Install with: pip install lightgbm")

        self.config = config or LambdaRankPredictorConfig()
        self.model: Optional[lgb.Booster] = None
        self.feature_engineer = FeatureEngineer()
        self.feature_columns: Optional[List[str]] = None
        self._fitted = False

    # ------------------------------------------------------------------
    # Feature prep
    # ------------------------------------------------------------------

    def prepare_features(
        self,
        df: pd.DataFrame,
        fit: bool = True,
    ) -> Tuple[pd.DataFrame, Optional[np.ndarray], np.ndarray]:
        """Prepare features plus LambdaRank groups.

        Returns:
            (X, y_relevance_or_None, group_sizes_in_row_order)
        """
        if 'competition_id' not in df.columns:
            raise ValueError(
                "LambdaRank predictor requires 'competition_id' in input to form groups"
            )

        # Serving commonly receives the stateful frame used by downstream
        # heads. Enforce the stateless contract at the model boundary too.
        df = build_lambdarank_feature_view(df)

        # Sort by competition_id so LightGBM `group` arrays align with rows.
        df_sorted = df.sort_values('competition_id', kind='stable').reset_index(drop=True)

        if fit:
            df_transformed = self.feature_engineer.fit_transform(df_sorted)
            self.feature_columns = self.feature_engineer.get_feature_columns()
        else:
            df_transformed = self.feature_engineer.transform(df_sorted)

        X, y_bucket = self.feature_engineer.get_feature_matrix(
            df_transformed, include_target=True
        )

        y = None
        if y_bucket is not None:
            y = _relevance_from_bucket(y_bucket.values)

        # Group sizes in the order rows appear.
        group_sizes = (
            df_sorted.groupby('competition_id', sort=False)
            .size()
            .to_numpy()
        )
        # Attach the sorted comp_id alongside X so callers can re-align.
        X = X.copy()
        X.attrs['competition_id'] = df_sorted['competition_id'].to_numpy()

        return X, y, group_sizes

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(
        self,
        train_df: pd.DataFrame,
        val_df: Optional[pd.DataFrame] = None,
        verbose: bool = True,
    ) -> Dict[str, Any]:
        """Train the LambdaRank scorer.

        Both train_df and val_df must contain 'competition_id' and
        'place_bucket'. Rows are sorted by competition_id internally to
        align with the `group` parameter.
        """
        X_train, y_train, g_train = self.prepare_features(train_df, fit=True)
        if y_train is None:
            raise ValueError("Training data must contain 'place_bucket' column")

        comp_ids_train = X_train.attrs['competition_id']

        train_data = lgb.Dataset(
            X_train,
            y_train,
            group=g_train,
            feature_name=self.feature_columns,
        )

        valid_sets = [train_data]
        valid_names = ['train']

        if val_df is not None:
            X_val, y_val, g_val = self.prepare_features(val_df, fit=False)
            val_data = lgb.Dataset(
                X_val, y_val, group=g_val, reference=train_data
            )
            valid_sets.append(val_data)
            valid_names.append('val')

        callbacks = []
        if verbose:
            callbacks.append(lgb.log_evaluation(period=50))
        if self.config.early_stopping_rounds:
            callbacks.append(
                lgb.early_stopping(
                    stopping_rounds=self.config.early_stopping_rounds,
                    verbose=verbose,
                )
            )

        self.model = lgb.train(
            self.config.lgb_params,
            train_data,
            num_boost_round=self.config.n_estimators,
            valid_sets=valid_sets,
            valid_names=valid_names,
            callbacks=callbacks,
        )

        self._fitted = True
        assert_stateless_feature_columns(self.feature_columns)

        return {
            'feature_importance': self.get_feature_importance(),
            'best_iteration': self.model.best_iteration,
            'n_features': len(self.feature_columns),
            'n_train_groups': len(g_train),
            'n_train_rows': len(X_train),
        }

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def predict_scores(self, df: pd.DataFrame) -> pd.Series:
        """Raw ranking scores indexed to match df (after internal sort).

        The returned Series has the same index as df; values are the
        LambdaRank scores (higher = predicted better finish).
        """
        if not self._fitted:
            raise ValueError("Model must be trained before prediction")

        X, _, _ = self.prepare_features(df, fit=False)
        raw_scores = self.model.predict(X)

        # Re-align to df's original index.
        original_index = df.index
        sorted_comp_ids = X.attrs['competition_id']
        # The sort was by competition_id, stable — we need the inverse permutation.
        # Easiest: rebuild via merging on (competition_id, rider_id) if available,
        # else rely on the fact that prepare_features sorted df and we saved the
        # sort order implicitly. Use the same sort here to recover positions.
        df_sort_order = df.sort_values('competition_id', kind='stable').index
        scores = pd.Series(raw_scores, index=df_sort_order, name='lambdarank_score')
        return scores.reindex(original_index)

    def predict_win_probabilities(self, df: pd.DataFrame) -> pd.Series:
        """Per-race win probability via temperature-scaled softmax.

        Probabilities sum to 1 within each competition_id group. Returned
        Series is indexed to match df.
        """
        if 'competition_id' not in df.columns:
            raise ValueError("Input must contain 'competition_id' for per-race softmax")

        scores = self.predict_scores(df)
        probs = _softmax_by_group(
            scores.values,
            df['competition_id'].to_numpy(),
            temperature=self.config.temperature,
        )
        return pd.Series(probs, index=df.index, name='lambdarank_win_p')

    def predict_topk_probabilities(
        self,
        df: pd.DataFrame,
        k: int = 3,
        n_samples: int = 4000,
        random_state: int = 42,
    ) -> pd.Series:
        """Per-race top-K probability via Plackett-Luce sampling.

        For K=1 this equals `predict_win_probabilities`. For K>1 we sample
        from the PL model (equivalent to softmax-then-remove-then-softmax)
        and count how often each rider finishes in the top K.

        Sampling is per-race; n_samples applies per race independently.
        """
        if k < 1:
            raise ValueError("k must be >= 1")
        if k == 1:
            return self.predict_win_probabilities(df).rename(f'lambdarank_top{k}_p')

        scores = self.predict_scores(df).values / self.config.temperature
        out = np.zeros(len(df))

        rng = np.random.default_rng(random_state)
        for comp_id, idx in df.groupby('competition_id').groups.items():
            rows = np.array(idx)
            s = scores[rows]
            # Stable softmax for sampling weights.
            s_shift = s - s.max()
            weights = np.exp(s_shift)
            weights = weights / weights.sum()

            field_size = len(rows)
            k_use = min(k, field_size)

            counts = np.zeros(field_size)
            for _ in range(n_samples):
                # Plackett-Luce sampling: successive weighted draws without replacement.
                w = weights.copy()
                chosen = set()
                for _k in range(k_use):
                    w_sum = w.sum()
                    if w_sum <= 0:
                        break
                    p = w / w_sum
                    pick = rng.choice(field_size, p=p)
                    chosen.add(pick)
                    w[pick] = 0.0
                for c in chosen:
                    counts[c] += 1

            out[rows] = counts / n_samples

        return pd.Series(out, index=df.index, name=f'lambdarank_top{k}_p')

    # ------------------------------------------------------------------
    # Temperature calibration
    # ------------------------------------------------------------------

    def calibrate_temperature(self, val_df: pd.DataFrame) -> float:
        """Fit temperature by minimizing per-race winner NLL on val_df.

        The winner (place_bucket==0) of each race is the positive class;
        NLL is computed over the per-race softmax.
        """
        from scipy.optimize import minimize_scalar

        if 'place_bucket' not in val_df.columns:
            raise ValueError("Validation data must contain 'place_bucket'")
        if 'competition_id' not in val_df.columns:
            raise ValueError("Validation data must contain 'competition_id'")

        scores = self.predict_scores(val_df).values
        comp_ids = val_df['competition_id'].to_numpy()
        is_winner = (val_df['place_bucket'].values == 0).astype(float)

        def nll(T: float) -> float:
            if T <= 0:
                return np.inf
            probs = _softmax_by_group(scores, comp_ids, temperature=T)
            # Log-likelihood of winners only.
            winner_probs = probs[is_winner == 1.0]
            if len(winner_probs) == 0:
                return 0.0
            return -np.mean(np.log(winner_probs + 1e-12))

        result = minimize_scalar(nll, bounds=(0.05, 20.0), method='bounded')
        self.config.temperature = float(result.x)
        return self.config.temperature

    # ------------------------------------------------------------------
    # Eval / introspection
    # ------------------------------------------------------------------

    def evaluate(self, df: pd.DataFrame) -> Dict[str, float]:
        """Compute discrimination AND calibration metrics.

        Metrics reported:
        - winner_capture: fraction of races where argmax pred is actual winner
        - podium_capture: mean fraction of predicted-top-3 that were actual podium (buckets 0-1)
        - win_log_loss: mean -log(p) over actual winners
        - discrimination_ratio: mean(p for winners) / (1/avg_field_size)
          -> 1.0 = no skill, higher = better separation of winners
        - win_cal_ratio: Step-A-style mean(predicted_win_p) / actual_winner_frequency
          over ALL rider-rows. 1.0 = perfectly calibrated. Note: softmax-normalized
          probabilities yield this by construction, so it's a sanity check rather
          than a discrimination signal.
        - win_ece: Expected Calibration Error on win probability (10 bins, weighted by bin size)
        """
        if 'place_bucket' not in df.columns:
            raise ValueError("Data must contain 'place_bucket' for evaluation")
        if 'competition_id' not in df.columns:
            raise ValueError("Data must contain 'competition_id' for evaluation")

        scores = self.predict_scores(df)
        probs = _softmax_by_group(
            scores.values,
            df['competition_id'].to_numpy(),
            temperature=self.config.temperature,
        )

        eval_df = df[['competition_id', 'place_bucket']].copy()
        eval_df['_p'] = probs
        eval_df['_score'] = scores.values
        eval_df['_is_winner'] = (eval_df['place_bucket'] == 0).astype(float)

        # Winner capture: fraction of races where argmax score has place_bucket==0.
        winner_hits = 0
        podium_hits = 0
        n_races = 0
        winner_ps: List[float] = []

        for _comp, g in eval_df.groupby('competition_id', sort=False):
            if (g['place_bucket'] == 0).sum() == 0:
                continue
            n_races += 1
            predicted_winner_idx = g['_score'].idxmax()
            if g.loc[predicted_winner_idx, 'place_bucket'] == 0:
                winner_hits += 1

            top3 = g.sort_values('_score', ascending=False).head(3)
            actual_podium = g[g['place_bucket'] <= 1]
            podium_hits += len(set(top3.index) & set(actual_podium.index))

            actual_winner_row = g[g['place_bucket'] == 0].iloc[0]
            winner_ps.append(float(actual_winner_row['_p']))

        winner_capture = winner_hits / max(n_races, 1)
        avg_podium_overlap = podium_hits / max(n_races, 1) / 3.0
        win_nll = -np.mean(np.log(np.asarray(winner_ps) + 1e-12)) if winner_ps else np.nan

        avg_field_size = float(eval_df.groupby('competition_id').size().mean())
        if winner_ps:
            discrimination_ratio = float(np.mean(winner_ps)) / (1.0 / avg_field_size)
        else:
            discrimination_ratio = np.nan

        # Step-A-style row-wise calibration ratio: mean(predicted) / actual_frequency
        # across ALL rider rows. For a per-race softmax this is identically 1.0.
        mean_predicted = float(eval_df['_p'].mean())
        actual_freq = float(eval_df['_is_winner'].mean())
        win_cal_ratio = mean_predicted / actual_freq if actual_freq > 0 else np.nan

        # Expected Calibration Error (ECE): bin rows by predicted win probability,
        # compare mean predicted prob vs actual winner frequency in each bin.
        n_bins = 10
        bin_edges = np.linspace(0, 1, n_bins + 1)
        p = eval_df['_p'].values
        y = eval_df['_is_winner'].values
        ece = 0.0
        n = len(p)
        for i in range(n_bins):
            mask = (p > bin_edges[i]) & (p <= bin_edges[i + 1])
            if mask.sum() >= 10:
                bin_p = p[mask].mean()
                bin_y = y[mask].mean()
                ece += (mask.sum() / n) * abs(bin_p - bin_y)

        return {
            'winner_capture': winner_capture,
            'podium_capture': avg_podium_overlap,
            'win_log_loss': win_nll,
            'discrimination_ratio': discrimination_ratio,
            'win_cal_ratio': win_cal_ratio,
            'win_ece': ece,
            'n_races': n_races,
            'avg_field_size': avg_field_size,
            'temperature': self.config.temperature,
        }

    def get_feature_importance(self, importance_type: str = 'gain') -> pd.DataFrame:
        if not self._fitted:
            raise ValueError("Model must be trained before getting importance")
        importance = self.model.feature_importance(importance_type=importance_type)
        return pd.DataFrame({
            'feature': self.feature_columns,
            'importance': importance,
        }).sort_values('importance', ascending=False)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str):
        if not self._fitted:
            raise ValueError("Model must be trained before saving")
        assert_stateless_feature_columns(self.feature_columns or [])
        self.model.save_model(path)

    def load(self, path: str):
        self.model = lgb.Booster(model_file=path)
        self._fitted = True

    def feature_contract_metadata(self) -> Dict[str, Any]:
        """Return the feature contract persisted beside this model."""
        if self.feature_columns is None:
            raise ValueError("LambdaRank feature columns are not available")
        return make_lambdarank_contract_metadata(self.feature_columns)


def train_lambdarank_predictor(
    train_df: pd.DataFrame,
    val_df: Optional[pd.DataFrame] = None,
    config: Optional[LambdaRankPredictorConfig] = None,
    verbose: bool = True,
) -> Tuple[LambdaRankProbabilityPredictor, Dict[str, Any]]:
    """Convenience function: train a LambdaRank predictor."""
    predictor = LambdaRankProbabilityPredictor(config)
    info = predictor.train(train_df, val_df, verbose)
    return predictor, info
