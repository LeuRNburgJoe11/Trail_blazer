"""Tests for prediction exports."""

import csv

from railpulse.core.submission import INTERVAL_COLUMNS, write_intervals


def test_interval_export_uses_required_columns(tmp_path) -> None:
	output = tmp_path / "predictions.csv"
	write_intervals(output, [{"segment_id": "segment_001", "status": "Normal"}])
	with output.open(newline="", encoding="utf-8") as handle:
		row = next(csv.reader(handle))
	assert tuple(row) == INTERVAL_COLUMNS
