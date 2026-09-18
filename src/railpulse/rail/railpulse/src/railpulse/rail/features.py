"""Ties loader + speed + spectral_features together into one feature
vector per (file, side) pair -- the unit the pooled side classifier trains
and predicts on."""
from __future__ import annotations

import numpy as np

from railpulse.rail.loader import RailFile, side_channels
from railpulse.rail.spectral_features import extract_side_feature_vector
from railpulse.rail.speed import estimate_speed_mps


def side_feature_vector(rf: RailFile, side: str) -> dict:
    speed = estimate_speed_mps(rf.speed_pulse)
    sigs = [sig for _, _, _, sig in side_channels(rf, side)]
    matrix = np.stack(sigs, axis=1)  # (n_samples, n_channels) -- vibration+shock pooled
    return extract_side_feature_vector(matrix, speed)


def file_feature_row(rf: RailFile, filename: str) -> dict:
    """Both sides' feature vectors for one file, prefixed so they can sit
    side by side in one wide row for inspection/caching -- the pooled
    classifier itself is trained on the long-format (one row per side, see
    rail/pipeline.py), not this wide row."""
    row = {"filename": filename}
    for side, prefix in [("Side I", "s1"), ("Side II", "s2")]:
        for k, v in side_feature_vector(rf, side).items():
            row[f"{prefix}_{k}"] = v
    return row
