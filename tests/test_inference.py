"""Regression tests for Door interval inference."""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from railpulse.door.loader import load_stream
from railpulse.door.segmentation import detect_intervals


def test_door_boundaries_match_reference_intervals() -> None:
	data_dir = Path(__file__).parents[1] / "FOR PARTICIPANTS" / "02_Datasets" / "Door"
	samples = load_stream(data_dir / "Train.csv")
	intervals = detect_intervals(samples)
	with (data_dir / "Train_Segments_Answer.csv").open(encoding="utf-8") as handle:
		reference = list(csv.DictReader(handle))
	assert len(intervals) == len(reference)
	assert [samples[item.start_index].timestamp for item in intervals] == [item["start_time"] for item in reference]
	assert [samples[item.end_index].timestamp for item in intervals] == [item["end_time"] for item in reference]
