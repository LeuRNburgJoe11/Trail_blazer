"""Exact prediction export formats."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, Mapping


INTERVAL_COLUMNS = ("segment_id", "start_time", "end_time", "operation", "status", "n_rows")


def write_intervals(path: str | Path, intervals: Iterable[Mapping[str, object]]) -> None:
	"""Write interval predictions with the required stable column order."""
	with Path(path).open("w", newline="", encoding="utf-8") as handle:
		writer = csv.DictWriter(handle, fieldnames=INTERVAL_COLUMNS, extrasaction="ignore")
		writer.writeheader()
		for interval in intervals:
			writer.writerow({column: interval.get(column, "") for column in INTERVAL_COLUMNS})
