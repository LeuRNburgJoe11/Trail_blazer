"""
Context-aware peer ranking features (architecture review Section 03):
peer_residual_i(t) = T_i(t) - median(T_j(t)), j != i, comparable peers.

With only 6 independent labelled cases, this stays a transparent,
non-learned residual rather than a large fitted model -- "begin with robust
peer scoring before introducing learned unsupervised models."
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from railpulse.acv.loader import car_series, pick_param

TEMP_PARAM_CANDIDATES = [
    "Indoor Average Temperature",
    "Passenger Cabin Temperature Detected Value",
    "Observation Area Temperature Detected Value",
]
PRESSURE_PARAM_CANDIDATES = [
    "Refrigeration System 1 Low Pressure Value",
    "Refrigeration System 2 Low Pressure Value",
]


def _row_peer_residual(sig_df: pd.DataFrame) -> pd.DataFrame:
    """
    Vectorised, per-row (per-timestamp) robust residual of each car against
    the median of the other cars at that same row. Using the row's own
    median/MAD naturally adapts to whatever ambient/operating conditions
    apply at that moment, rather than a fixed global "normal" template.

    Approximation note: uses the full-row median (not a strict leave-one-out
    peer median) for speed; with 8 cars/case this shifts the median
    negligibly. Tighten this if you move to fewer cars per case.
    """
    row_median = sig_df.median(axis=1)
    row_mad = sig_df.sub(row_median, axis=0).abs().median(axis=1) + 1e-6
    return sig_df.sub(row_median, axis=0).div(row_mad, axis=0)


def peer_residual_score(df: pd.DataFrame, cars: list[str]) -> pd.Series:
    """One transparent ranking score per car -- higher = more suspicious."""
    temp_param = pick_param(df, cars, TEMP_PARAM_CANDIDATES)
    pressure_param = pick_param(df, cars, PRESSURE_PARAM_CANDIDATES)

    signals = {}
    if temp_param:
        signals["temp"] = pd.DataFrame({c: car_series(df, c, temp_param) for c in cars})
    if pressure_param:
        signals["pressure"] = pd.DataFrame({c: car_series(df, c, pressure_param) for c in cars})

    if not signals:
        return pd.Series(0.0, index=cars)

    per_signal_scores = []
    for name, sig_df in signals.items():
        residual = _row_peer_residual(sig_df)
        if name == "pressure":
            # low pressure is the fault direction -- flip so higher = more suspicious
            residual = -residual
        per_signal_scores.append(residual.mean(axis=0, skipna=True))

    combined = pd.concat(per_signal_scores, axis=1).mean(axis=1, skipna=True)
    return combined.reindex(cars).fillna(0.0)
