"""Load and normalize the continuous Door stream."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


REQUIRED_COLUMNS = ("Datetime", "Close command", "Open command", "Door leaf position")


@dataclass(frozen=True)
class DoorSample:
	timestamp: str
	time_seconds: float
	values: dict[str, float]


def parse_timestamp(value: str) -> float:
	"""Parse the dataset's hyphen-separated timestamp into epoch seconds."""
	parts = value.split("-")
	if len(parts) != 7:
		raise ValueError(f"Unsupported Door timestamp: {value!r}")
	year, month, day, hour, minute, second, milliseconds = map(int, parts)
	return datetime(year, month, day, hour, minute, second, milliseconds * 1000).timestamp()


def load_stream(path: str | Path) -> list[DoorSample]:
	"""Read a Door CSV without changing its original timestamp strings."""
	with Path(path).open(newline="", encoding="utf-8-sig") as handle:
		reader = csv.DictReader(handle)
		fields = reader.fieldnames or []
		missing = [column for column in REQUIRED_COLUMNS if column not in fields]
		if missing:
			raise ValueError(f"Door CSV is missing columns: {', '.join(missing)}")
		samples = []
		for row in reader:
			timestamp = row["Datetime"]
			values = {
				field: float(value)
				for field, value in row.items()
				if field != "Datetime" and value not in (None, "")
			}
			samples.append(DoorSample(timestamp, parse_timestamp(timestamp), values))
	if not samples:
		raise ValueError(f"Door CSV contains no samples: {path}")
	return samples


def samples_to_rows(samples: Iterable[DoorSample]) -> list[dict[str, float | str]]:
	"""Convert samples to plain rows for feature and pipeline code."""
	return [{"Datetime": sample.timestamp, **sample.values} for sample in samples]
