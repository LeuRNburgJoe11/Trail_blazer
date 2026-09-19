"""Official export contracts shared by batch inference and the application."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re

import numpy as np
import pandas as pd

from railpulse.door.loader import parse_timestamp

SCHEMAS = {
    "door": ["start_time", "end_time", "prediction"],
    "acv": ["file_id", "ranked_cars"],
    "rail": ["file_id", "prediction"],
    "shm": ["file_id", "prediction"],
}


@dataclass
class PredictionResult:
    frame: pd.DataFrame
    evidence: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def validate_predictions(subsystem, frame, *, expected_ids=None, expected_cars=None):
    if list(frame.columns) != SCHEMAS[subsystem] or (frame.empty and subsystem != "door") or frame.isna().any().any():
        raise ValueError(f"{subsystem}: empty predictions, missing values, or incorrect column order")
    if subsystem == "door":
        if not frame.prediction.isin(["Normal", "Abnormal resistance"]).all():
            raise ValueError("Invalid Door status")
        starts = frame.start_time.map(parse_timestamp).to_numpy()
        ends = frame.end_time.map(parse_timestamp).to_numpy()
        if np.any(ends <= starts) or np.any(starts[1:] <= ends[:-1]):
            raise ValueError("Door intervals must have positive duration, be ordered and nonoverlapping")
        return
    ids = frame.file_id.tolist()
    if len(ids) != len(set(ids)) or any(Path(name).name != name for name in ids):
        raise ValueError("Duplicate or invalid prediction IDs")
    if expected_ids is not None and (set(ids) != set(expected_ids) or len(ids) != len(expected_ids)):
        raise ValueError("Predictions do not cover exactly the expected input files")
    if subsystem == "rail" and not frame.prediction.isin(["Normal", "Side I", "Side II"]).all():
        raise ValueError("Invalid Rail class")
    if subsystem == "shm":
        values = pd.to_numeric(frame.prediction, errors="raise").to_numpy()
        if not np.isfinite(values).all() or np.any(values < 0):
            raise ValueError("SHM predictions must be finite and nonnegative")
    if subsystem == "acv":
        for row in frame.itertuples():
            cars = row.ranked_cars.split("|")
            if len(cars) != len(set(cars)) or not all(re.fullmatch(r"\d{2}", car) for car in cars):
                raise ValueError("ACV rankings must contain unique, native two-digit car IDs")
            if expected_cars is not None and set(cars) != set(expected_cars[row.file_id]):
                raise ValueError("ACV ranking does not contain every car exactly once")


def csv_bytes(subsystem, frame, **checks):
    validate_predictions(subsystem, frame, **checks)
    return frame.to_csv(index=False, float_format="%.17g", lineterminator="\n").encode()
