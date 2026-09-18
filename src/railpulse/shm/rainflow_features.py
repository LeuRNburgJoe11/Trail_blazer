"""Cycle features retaining absolute stress amplitudes and residual half cycles.

Uses rainflow 3.2.0 (ASTM E1049 implementation). No smoothing, resampling,
per-file normalisation, assumed material constants or invented sampling rate.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd
import rainflow

from .loader import load_recording, list_recordings

FEATURE_VERSION = "shm-rainflow-v1"
EXPONENTS = np.round(np.arange(2.0, 8.01, 0.1), 1)
STAT_FEATURES = ["stress_mean", "stress_std", "stress_rms", "stress_min", "stress_max",
                 "stress_abs_q50", "stress_abs_q90", "stress_abs_q99", "stress_abs_q999",
                 "stress_kurtosis", "difference_rms", "n_samples"]
CYCLE_FEATURES = ["cycle_count", "half_cycle_fraction", "amplitude_mean", "amplitude_q50",
                  "amplitude_q90", "amplitude_q99", "amplitude_max", "cycle_mean_abs"]


def power_column(exponent: float) -> str:
    return f"rf_power_{exponent:.1f}"


FEATURE_COLUMNS = STAT_FEATURES + CYCLE_FEATURES + [power_column(p) for p in EXPONENTS]


def cycle_arrays(stress: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    stress = np.asarray(stress, dtype=float)
    if stress.ndim != 1 or stress.size < 3 or not np.isfinite(stress).all():
        raise ValueError("Rainflow input must be a finite 1D signal with at least three samples")
    # Compress plateaus/monotonic stretches without changing cycle amplitudes.
    distinct = stress[np.r_[True, np.diff(stress) != 0]]
    if distinct.size <= 1:
        return (np.array([], dtype=float),) * 3
    if distinct.size == 2:
        return np.array([abs(distinct[1] - distinct[0]) / 2]), np.array([distinct.mean()]), np.array([0.5])
    delta = np.diff(distinct)
    turning = distinct[np.r_[True, (delta[:-1] > 0) != (delta[1:] > 0), True]]
    # Library 3.2.0 requires >=3 points to yield a terminal reversal.
    if turning.size == 2:
        return np.array([abs(turning[1] - turning[0]) / 2]), np.array([turning.mean()]), np.array([0.5])
    cycles = np.array([(rng / 2.0, mean, count) for rng, mean, count, _, _ in rainflow.extract_cycles(turning)])
    return cycles[:, 0], cycles[:, 1], cycles[:, 2]


def extract_features(stress: np.ndarray) -> dict[str, float]:
    amplitude, means, counts = cycle_arrays(stress)
    stress = np.asarray(stress, dtype=float)
    std = float(np.std(stress))
    absolute = np.abs(stress)
    features = dict(zip(STAT_FEATURES, [
        float(np.mean(stress)), std, float(np.sqrt(np.mean(stress ** 2))),
        float(np.min(stress)), float(np.max(stress)),
        *np.quantile(absolute, [0.5, 0.9, 0.99, 0.999]).tolist(),
        float(np.mean(((stress - stress.mean()) / std) ** 4)) if std else 0.0,
        float(np.sqrt(np.mean(np.diff(stress) ** 2))), float(stress.size),
    ]))
    total = float(counts.sum())
    if total:
        order = np.argsort(amplitude)
        quantiles = np.interp([0.5, 0.9, 0.99], np.cumsum(counts[order]) / total, amplitude[order])
        cycle_values = [total, float(counts[counts == 0.5].sum() / total),
                        float(np.average(amplitude, weights=counts)), *quantiles.tolist(),
                        float(amplitude.max()), float(np.average(np.abs(means), weights=counts))]
    else:
        cycle_values = [0.0] * len(CYCLE_FEATURES)
    features.update(zip(CYCLE_FEATURES, cycle_values))
    for exponent in EXPONENTS:
        features[power_column(exponent)] = float(np.dot(counts, amplitude ** exponent))
    if not np.isfinite(list(features.values())).all():
        raise ValueError("Stress magnitude overflowed feature extraction; check input units")
    return features


def build_features(directory: str | Path, cache_dir: str | Path | None = None):
    """Return filename-indexed feature table and manifest. Cache is deterministic and label-free."""
    rows, manifest = [], []
    for path in list_recordings(directory):
        started = time.perf_counter()
        recording = load_recording(path)
        key = hashlib.sha256(f"{FEATURE_VERSION}:{rainflow.__version__}:{recording.sha256}".encode()).hexdigest()
        cache = Path(cache_dir) / f"{key}.json" if cache_dir else None
        cached = bool(cache and cache.exists())
        if cached:
            features = json.loads(cache.read_text())
        else:
            features = extract_features(recording.stress)
            if cache:
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_text(json.dumps(features, sort_keys=True, allow_nan=False) + "\n")
        if set(features) != set(FEATURE_COLUMNS) or not np.isfinite(list(features.values())).all():
            raise ValueError(f"Invalid feature cache for {path.name}; remove the matching cache entry and retry")
        rows.append({"file_id": recording.file_id, **features})
        manifest.append({"file_id": recording.file_id, "sha256": recording.sha256,
                         "n_samples": recording.stress.size, "bytes": path.stat().st_size,
                         "feature_version": FEATURE_VERSION, "cached": cached,
                         "seconds": time.perf_counter() - started})
    return pd.DataFrame(rows).set_index("file_id")[FEATURE_COLUMNS], pd.DataFrame(manifest)
