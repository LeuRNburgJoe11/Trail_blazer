"""Load one-second rail vibration recordings and their file labels."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


EXPECTED_COLUMNS = 129


@dataclass(frozen=True)
class RailRecording:
	file_id: str
	values: np.ndarray


def load_recording(path: str | Path) -> RailRecording:
	path = Path(path)
	frame = pd.read_csv(path, header=None)
	if frame.shape[1] != EXPECTED_COLUMNS:
		raise ValueError(f"{path.name} has {frame.shape[1]} columns; expected {EXPECTED_COLUMNS}")
	numeric = frame.apply(pd.to_numeric, errors="coerce")
	if numeric.iloc[0].isna().all():
		numeric = numeric.iloc[1:].reset_index(drop=True)
	values = numeric.to_numpy(dtype=float)
	if np.isnan(values).any():
		values = np.nan_to_num(values, nan=0.0)
	return RailRecording(path.name, values)


def list_recordings(directory: str | Path) -> list[Path]:
	return sorted(Path(directory).glob("*.csv"))


def load_labels(path: str | Path) -> dict[str, str]:
	labels = pd.read_csv(path)
	required = {"filename", "label"}
	if not required.issubset(labels.columns):
		raise ValueError("Rail labels must contain filename and label columns")
	return dict(zip(labels["filename"].astype(str), labels["label"].astype(str)))
