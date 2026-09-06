"""
Win-market calibration corrector for the contender cascade.

Why: under the gated arm-C stack the contender's one-day win book runs
under-confident (win_cal_ratio ~0.93 vs baseline ~1.02). The integration
experiment's temperature refit was buggy — it renormalized each race's win
book to sum to exactly 1, which mechanically pins the calibration ratio at
the pool's winner-recall level regardless of T (that is why a near-identity
T appeared to move cal 0.93 -> 1.2). The production corrector therefore
operates on the win market as an INDEPENDENT BINARY market (exactly how
MarketProbabilityEvaluator scores it) with NO per-race renormalization, so
it can actually move the book level.

Two candidate scalar correctors, both fit on the validation (early-stop)
contender pool by binary NLL:

  power        q = p^(1/T)            (T > 1 lifts the whole book)
  logit_shift  q = sigmoid(logit(p) + b)   (b > 0 lifts the whole book)

Selection rule (the must-fix contract): a candidate qualifies only if, on
the validation pool, it moves win_cal_ratio strictly toward 1.0 AND does not
worsen win log loss. Among qualifiers the lower log loss wins; if neither
qualifies the corrector is the identity (and serving applies a no-op).

The corrector is persisted to models/production/win_calibration.json and
applied at serving time to the contender rows' win-market probability
(after softmax temperature, before display / blend / DNF adjustment).
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
from scipy.optimize import minimize_scalar

from cycling_project.webscrape_tools.logging_config import get_logger
from cycling_project.prediction_tools.production_release import write_release_manifest

logger = get_logger(__name__)

ARTIFACT_NAME = "win_calibration.json"
EPS = 1e-12
POWER_BOUNDS = (0.25, 4.0)
SHIFT_BOUNDS = (-2.0, 2.0)


def _clip(p: np.ndarray) -> np.ndarray:
    return np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS)


def _binary_nll(p: np.ndarray, y: np.ndarray) -> float:
    p = _clip(p)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def _cal_ratio(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.asarray(p, dtype=float).sum() / max(np.asarray(y).sum(), 1.0))


def _apply_power(p: np.ndarray, T: float) -> np.ndarray:
    return _clip(_clip(p) ** (1.0 / T))


def _apply_logit_shift(p: np.ndarray, b: float) -> np.ndarray:
    p = _clip(p)
    logit = np.log(p / (1 - p))
    return _clip(1.0 / (1.0 + np.exp(-(logit + b))))


def apply_corrector(p: np.ndarray, corrector: Optional[Dict[str, Any]]) -> np.ndarray:
    """Apply a persisted corrector to win-market probabilities (no-op safe)."""
    if not corrector:
        return np.asarray(p, dtype=float)
    method = corrector.get("method", "identity")
    if method == "power":
        return _apply_power(p, float(corrector["param"]))
    if method == "logit_shift":
        return _apply_logit_shift(p, float(corrector["param"]))
    return np.asarray(p, dtype=float)


def fit_win_corrector(win_p: np.ndarray, y_win: np.ndarray) -> Dict[str, Any]:
    """Fit + select the win-market corrector on a validation pool.

    Args:
        win_p: contender win-market probabilities (post-temperature).
        y_win: binary winner outcomes for the same rows.

    Returns the corrector dict (persistable as-is) including before/after
    validation metrics for every candidate and the selection rationale.
    """
    win_p = np.asarray(win_p, dtype=float)
    y_win = np.asarray(y_win, dtype=float)

    before = {"win_log_loss": _binary_nll(win_p, y_win), "win_cal_ratio": _cal_ratio(win_p, y_win)}

    res_t = minimize_scalar(
        lambda T: _binary_nll(_apply_power(win_p, T), y_win),
        bounds=POWER_BOUNDS, method="bounded",
    )
    T = float(res_t.x)
    q_t = _apply_power(win_p, T)
    power_metrics = {"win_log_loss": _binary_nll(q_t, y_win), "win_cal_ratio": _cal_ratio(q_t, y_win)}

    res_b = minimize_scalar(
        lambda b: _binary_nll(_apply_logit_shift(win_p, b), y_win),
        bounds=SHIFT_BOUNDS, method="bounded",
    )
    b = float(res_b.x)
    q_b = _apply_logit_shift(win_p, b)
    shift_metrics = {"win_log_loss": _binary_nll(q_b, y_win), "win_cal_ratio": _cal_ratio(q_b, y_win)}

    def qualifies(after: Dict[str, float]) -> bool:
        moves_toward_1 = abs(after["win_cal_ratio"] - 1.0) < abs(before["win_cal_ratio"] - 1.0)
        no_worse_ll = after["win_log_loss"] <= before["win_log_loss"] + 1e-9
        return moves_toward_1 and no_worse_ll

    candidates = [
        ("power", T, power_metrics),
        ("logit_shift", b, shift_metrics),
    ]
    qualified = [(m, p_, a) for m, p_, a in candidates if qualifies(a)]
    if qualified:
        method, param, after = min(qualified, key=lambda c: c[2]["win_log_loss"])
    else:
        method, param, after = "identity", None, dict(before)

    corrector = {
        "method": method,
        "param": param,
        "fitted_at": datetime.now().isoformat(timespec="seconds"),
        "n_val_rows": int(len(win_p)),
        "n_val_winners": int(y_win.sum()),
        "val_before": before,
        "val_after": after,
        "candidates": {
            "power": {"param": T, **power_metrics},
            "logit_shift": {"param": b, **shift_metrics},
        },
        "notes": (
            "Fit on the early-stop contender pool as an independent binary win "
            "market (no per-race renormalization — renormalizing pins the book "
            "sum, the bug in the integration experiment's refit). Selection: "
            "must move val win_cal_ratio toward 1.0 without worsening val win "
            "log loss; identity when neither candidate qualifies."
        ),
    }
    logger.info(
        "Win corrector: %s (param=%s)  val cal %.3f -> %.3f  ll %.5f -> %.5f",
        method, f"{param:.4f}" if param is not None else "-",
        before["win_cal_ratio"], after["win_cal_ratio"],
        before["win_log_loss"], after["win_log_loss"],
    )
    return corrector


def save_corrector(corrector: Dict[str, Any], model_dir: Path) -> Path:
    path = Path(model_dir) / ARTIFACT_NAME
    path.write_text(json.dumps(corrector, indent=2))
    write_release_manifest(model_dir)
    return path


def load_corrector(model_dir: Path) -> Optional[Dict[str, Any]]:
    """Load the persisted corrector; None when absent (callers no-op)."""
    path = Path(model_dir) / ARTIFACT_NAME
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load win corrector (%s) — ignoring", exc)
        return None
