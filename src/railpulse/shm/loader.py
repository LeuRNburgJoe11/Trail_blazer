"""Strict loading of the organiser's headerless, single-point stress recordings.

Stress units and sampling frequency are not supplied; values remain in source units.
Reject missing/non-finite data rather than inventing stresses or joining gaps.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class StressRecording:
    file_id: str
    stress: np.ndarray
    sha256: str


def load_recording(path: str | Path) -> StressRecording:
    path = Path(path)
    if path.suffix.lower() != ".csv":
        raise ValueError(f"Expected a stress CSV: {path}")
    try:
        frame = pd.read_csv(path, header=None, skip_blank_lines=False, dtype=np.float64)
    except (ValueError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise ValueError(f"{path.name}: expected one headerless numeric stress column") from exc
    if frame.shape[1] != 1 or len(frame) < 3:
        raise ValueError(f"{path.name}: expected one column and at least three samples; got {frame.shape}")
    values = frame.iloc[:, 0].to_numpy()
    if not np.isfinite(values).all():
        raise ValueError(f"{path.name}: missing or non-finite stress values")
    return StressRecording(path.name, values, hashlib.sha256(path.read_bytes()).hexdigest())


def list_recordings(path: str | Path) -> list[Path]:
    path = Path(path)
    files = [path] if path.is_file() else sorted(path.glob("*.csv"))
    if not files:
        raise ValueError(f"No stress CSV files found: {path}")
    if any(p.name.lower() == "train_labels.csv" for p in files):
        raise ValueError("Pass the Train or Test recording folder, not the folder containing labels")
    return files


def load_labels(path: str | Path, filenames: list[str]) -> np.ndarray:
    frame = pd.read_csv(path, dtype={"filename": str})
    if list(frame.columns) != ["filename", "damage"]:
        raise ValueError("Labels must have exactly filename,damage columns")
    if frame.filename.isna().any() or frame.filename.duplicated().any():
        raise ValueError("Missing or duplicate label filenames")
    if set(frame.filename) != set(filenames) or len(set(filenames)) != len(filenames):
        raise ValueError("Labels and training recordings must have exactly matching unique filenames")
    values = frame.set_index("filename").loc[filenames, "damage"].to_numpy(dtype=float)
    if not np.isfinite(values).all() or np.any(values <= 0):
        raise ValueError("MAPE requires positive finite training damage; zero-target handling is unspecified")
    return values
