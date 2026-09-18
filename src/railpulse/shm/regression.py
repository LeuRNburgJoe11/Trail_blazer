"""Small-sample regressors, including a scale fitted directly to relative error."""
from __future__ import annotations

import numpy as np
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .rainflow_features import EXPONENTS, STAT_FEATURES, CYCLE_FEATURES, power_column


def weighted_median(values, weights) -> float:
    values, weights = np.asarray(values), np.asarray(weights)
    order = np.argsort(values, kind="stable")
    i = np.searchsorted(np.cumsum(weights[order]), weights.sum() / 2)
    return float(values[order[min(i, len(values) - 1)]])


class DamageRegressor:
    """All calibration/scaling learns only from the fit call's training files."""

    def __init__(self, kind: str):
        self.kind = kind

    def fit(self, frame, target):
        y = np.asarray(target, dtype=float)
        if len(y) != len(frame) or len(y) == 0 or not np.isfinite(y).all() or np.any(y <= 0):
            raise ValueError("Expected positive finite targets matching feature rows")
        if self.kind == "constant_mape":
            self.constant_ = weighted_median(y, 1 / y)
        elif self.kind.startswith("physics_"):
            exponents = EXPONENTS if self.kind == "physics_fitted" else [float(self.kind.split("_")[1])]
            best = None
            for exponent in exponents:
                proxy = frame[power_column(exponent)].to_numpy()
                if np.any(proxy <= 0):
                    raise ValueError("Cannot calibrate a positive damage target from a zero-cycle recording")
                # min_a sum |y_i - a*p_i|/y_i is a weighted median of y_i/p_i.
                scale = weighted_median(y / proxy, proxy / y)
                error = float(np.mean(np.abs(y - scale * proxy) / y))
                if best is None or error < best[0]:
                    best = (error, float(exponent), scale)
            _, self.exponent_, self.scale_ = best
            self.columns_ = [power_column(self.exponent_)]
        else:
            if self.kind == "ridge_stats":
                self.columns_ = list(STAT_FEATURES)
            else:
                self.columns_ = STAT_FEATURES + CYCLE_FEATURES + [power_column(p) for p in (2, 3, 4, 5, 6, 8)]
            matrix = self._matrix(frame)
            if self.kind in ("ridge_stats", "ridge_cycles"):
                self.model_ = make_pipeline(StandardScaler(), Ridge(alpha=10.0))
            elif self.kind == "extra_trees":
                self.model_ = ExtraTreesRegressor(n_estimators=128, min_samples_leaf=3, max_features=0.8,
                                                 random_state=42, n_jobs=1)
            else:
                raise ValueError(f"Unknown regressor: {self.kind}")
            self.model_.fit(matrix, np.log(y))
        return self

    def _matrix(self, frame):
        raw = frame[self.columns_].to_numpy(dtype=float)
        # Signed log compresses scale without losing amplitude; fitted scaler is fold-local.
        return np.sign(raw) * np.log1p(np.abs(raw))

    def predict(self, frame) -> np.ndarray:
        if self.kind == "constant_mape":
            prediction = np.full(len(frame), self.constant_)
        elif self.kind.startswith("physics_"):
            prediction = self.scale_ * frame[power_column(self.exponent_)].to_numpy()
        else:
            prediction = np.exp(self.model_.predict(self._matrix(frame)))
        if not np.isfinite(prediction).all() or np.any(prediction < 0):
            raise ValueError("Model produced invalid damage; input is outside supported numerical range")
        return prediction


CANDIDATES = ("constant_mape", "physics_3", "physics_5", "physics_fitted",
              "ridge_stats", "ridge_cycles", "extra_trees")
