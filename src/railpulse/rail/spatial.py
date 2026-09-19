"""Canonical version of the Rail branch's pooled, speed-normalized side model.

Both side vectors from one file always stay together during cross-validation.
Vibration and shock features are kept separate because their units differ.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import welch
from sklearn.ensemble import GradientBoostingClassifier

from .speed import estimate_speed


def extract_spatial_features(values: np.ndarray) -> dict[str, float]:
    if values.ndim != 2 or values.shape != (10_000, 129) or not np.isfinite(values).all():
        raise ValueError("Spatial Rail features require 10,000 finite samples x 129 channels")
    speed = estimate_speed(values[:, 0])
    result = {}
    for side in range(2):
        for kind in range(2):
            channels = values[:, 1 + 2 * side + kind::4]
            centered = channels - channels.mean(axis=0)
            rms = np.sqrt(np.mean(channels ** 2, axis=0))
            variance = np.mean(centered ** 2, axis=0)
            stats = {
                "rms": rms,
                "crest": np.max(np.abs(channels), axis=0) / np.maximum(rms, 1e-12),
                "kurtosis": np.mean(centered ** 4, axis=0) / np.maximum(variance ** 2, 1e-24),
            }
            frequencies, psd = welch(channels, fs=10_000, axis=0, nperseg=2048)
            edges = np.array([2, 4, 8, 16, 32, 50]) * speed
            for band, (low, high) in enumerate(zip(edges[:-1], edges[1:])):
                mask = (frequencies >= low) & (frequencies < high)
                stats[f"band_{band}"] = psd[mask].sum(axis=0) * (frequencies[1] - frequencies[0])
            for name, vector in stats.items():
                for reducer in ("mean", "max"):
                    result[f"s{side}_{kind}_{name}_{reducer}"] = float(getattr(np, reducer)(vector))
        result[f"s{side}_speed"] = speed
    return result


class PooledSideClassifier:
    def __init__(self):
        self.model = GradientBoostingClassifier(random_state=42)

    def fit(self, rows, labels):
        if not rows or len(rows) != len(labels) or not set(labels) <= {"Normal", "Side I", "Side II"}:
            raise ValueError("Pooled Rail fit requires matching nonempty rows and valid labels")
        self.feature_names = [name[3:] for name in rows[0] if name.startswith("s0_")]
        matrix, targets = [], []
        for row, label in zip(rows, labels):
            for side, name in enumerate(("Side I", "Side II")):
                matrix.append([row[f"s{side}_{key}"] for key in self.feature_names])
                targets.append(int(label == name))
        self.model.fit(matrix, targets)
        return self

    def predict(self, rows):
        if not rows:
            return []
        if not hasattr(self, "feature_names"):
            raise ValueError("Pooled Rail model is not fitted")
        scores = [self.model.predict_proba(
            [[row[f"s{side}_{key}"] for key in self.feature_names] for row in rows]
        )[:, 1] for side in range(2)]
        return ["Normal" if max(a, b) < 0.5 else "Side I" if a >= b else "Side II"
                for a, b in zip(*scores)]
