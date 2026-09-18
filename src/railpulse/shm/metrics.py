"""Official fraction-MAPE score; no arbitrary epsilon for undefined zero targets."""
import numpy as np


def regression_metrics(y_true, y_pred) -> dict[str, float]:
    truth, prediction = np.asarray(y_true, dtype=float), np.asarray(y_pred, dtype=float)
    if truth.ndim != 1 or truth.size == 0 or truth.shape != prediction.shape:
        raise ValueError("Expected nonempty, matching 1D target and prediction arrays")
    if not np.isfinite(truth).all() or np.any(truth <= 0):
        raise ValueError("True damage must be positive and finite; zero-target scoring is unspecified")
    if not np.isfinite(prediction).all() or np.any(prediction < 0):
        raise ValueError("Predictions must be finite and nonnegative")
    ape = np.abs(truth - prediction) / truth
    return {"mape": float(ape.mean()), "score": float(max(0.0, 1 - ape.mean())),
            "mae": float(np.abs(truth - prediction).mean()),
            "rmse": float(np.sqrt(np.mean((truth - prediction) ** 2))),
            "median_ape": float(np.median(ape)), "worst_ape": float(ape.max())}

