"""
Cycle representation (architecture review Section 02): a deliberately small
feature set, retaining original duration, peak current and other physically
meaningful scales -- no per-cycle normalisation that would erase fault
magnitude.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FEATURE_COLS = [
    "duration_s",
    "n_rows",
    "current_peak",
    "current_mean",
    "current_std",
    "current_integral",
    "voltage_peak",
    "voltage_mean",
    "emf_peak",
    "emf_mean",
    "position_travel",
    "position_start",
    "position_end",
    "is_open",
]


def cycle_features(seg_df: pd.DataFrame, start_ts, end_ts) -> dict:
    current = seg_df["Motor current(mA)"].to_numpy(dtype=float)
    voltage = seg_df["Motor Voltage(10mV)"].to_numpy(dtype=float)
    emf = seg_df["Motor electrodynamic force"].to_numpy(dtype=float)
    pos = seg_df["Door leaf position"].to_numpy(dtype=float)
    return {
        "duration_s": (end_ts - start_ts).total_seconds(),
        "n_rows": len(seg_df),
        "current_peak": current.max(),
        "current_mean": current.mean(),
        "current_std": current.std(),
        "current_integral": np.trapezoid(current) if len(current) > 1 else 0.0,
        "voltage_peak": voltage.max(),
        "voltage_mean": voltage.mean(),
        "emf_peak": emf.max(),
        "emf_mean": emf.mean(),
        "position_travel": abs(pos[-1] - pos[0]),
        "position_start": pos[0],
        "position_end": pos[-1],
        "is_open": float(seg_df["Door is opening"].mean() > 0.5),
    }


def build_feature_table(cycles) -> pd.DataFrame:
    rows = []
    for start_ts, end_ts, seg_df in cycles:
        feat = cycle_features(seg_df, start_ts, end_ts)
        feat["start_ts"] = start_ts
        feat["end_ts"] = end_ts
        rows.append(feat)
    return pd.DataFrame(rows)
