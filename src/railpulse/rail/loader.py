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
	# Official recordings have a header; headerless uploads remain supported.
	with path.open(encoding="utf-8-sig") as handle:
		first = handle.readline().strip().split(",")
	try:
		[float(value) for value in first]
		header = None
	except ValueError:
		from railpulse.core.data_validation import RAIL_COLUMNS
		if first != RAIL_COLUMNS:
			raise ValueError(f"{path.name}: unexpected Rail header or channel order")
		header = 0
	frame = pd.read_csv(path, header=header, dtype=float, skip_blank_lines=False)
	if frame.shape[1] != EXPECTED_COLUMNS:
		raise ValueError(f"{path.name} has {frame.shape[1]} columns; expected {EXPECTED_COLUMNS}")
	values = frame.to_numpy(dtype=float)
	if values.shape[0] != 10_000 or not np.isfinite(values).all():
		raise ValueError(f"{path.name}: expected 10,000 finite samples")
	if not np.isin(values[:, 0], [0, 1]).all():
		raise ValueError(f"{path.name}: speed channel must contain binary pulses")
	return RailRecording(path.name, values)


def list_recordings(directory: str | Path) -> list[Path]:
	return sorted(Path(directory).glob("*.csv"))


def load_labels(path: str | Path) -> dict[str, str]:
	labels = pd.read_csv(path)
	required = {"filename", "label"}
	if not required.issubset(labels.columns):
		raise ValueError("Rail labels must contain filename and label columns")
	if labels.empty or labels.isna().any().any() or labels.filename.duplicated().any():
		raise ValueError("Rail labels must be nonempty, complete and unique")
	if not set(labels.label) <= {"Normal", "Side I", "Side II"}:
		raise ValueError("Unknown Rail class")
	return dict(zip(labels["filename"].astype(str), labels["label"].astype(str)))
