"""Train and run the Door operation detector/classifier."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .features import extract_features
from .loader import DoorSample, load_stream
from .segmentation import DoorInterval, detect_intervals


FEATURE_NAMES = (
	"duration", "current_peak", "current_mean", "current_rms", "current_integral",
	"current_std", "energy_proxy", "position_change", "position_stagnation", "velocity",
)


@dataclass
class DoorModel:
	classifier: object | None = None
	majority_status: str = "Normal"

	def fit(self, feature_rows: Sequence[dict[str, float | str]], labels: Sequence[str]) -> "DoorModel":
		self.majority_status = max(set(labels), key=labels.count) if labels else "Normal"
		try:
			from sklearn.ensemble import ExtraTreesClassifier
		except ImportError:
			return self
		if len(set(labels)) < 2 or len(labels) < 4:
			return self
		matrix = [[float(row[name]) for name in FEATURE_NAMES] for row in feature_rows]
		self.classifier = ExtraTreesClassifier(n_estimators=200, random_state=42, class_weight="balanced")
		self.classifier.fit(matrix, labels)
		return self

	def predict(self, feature_rows: Sequence[dict[str, float | str]]) -> list[str]:
		if not feature_rows:
			return []
		if self.classifier is None:
			return [self.majority_status] * len(feature_rows)
		matrix = [[float(row[name]) for name in FEATURE_NAMES] for row in feature_rows]
		return list(self.classifier.predict(matrix))


def labelled_training_rows(
	samples: Sequence[DoorSample], labels_path: str | Path
) -> tuple[list[dict[str, float | str]], list[str]]:
	detected = detect_intervals(samples)
	by_start: dict[str, dict[str, str]] = {}
	with Path(labels_path).open(newline="", encoding="utf-8-sig") as handle:
		for row in csv.DictReader(handle):
			by_start[row["start_time"]] = row
	features, labels = [], []
	for interval in detected:
		start_time = samples[interval.start_index].timestamp
		label = by_start.get(start_time)
		if label is not None:
			features.append(extract_features(samples, interval))
			labels.append(label["status"])
	return features, labels


def predict_intervals(samples: Sequence[DoorSample], model: DoorModel) -> list[dict[str, float | str]]:
	intervals = detect_intervals(samples)
	features = [extract_features(samples, interval) for interval in intervals]
	statuses = model.predict(features)
	return [
		{
			"segment_id": f"segment_{index:03d}",
			"start_time": samples[interval.start_index].timestamp,
			"end_time": samples[interval.end_index].timestamp,
			"operation": interval.operation,
			"status": str(status),
			"n_rows": interval.n_rows,
		}
		for index, (interval, status) in enumerate(zip(intervals, statuses), 1)
	]


def run(train_path: str | Path, labels_path: str | Path, test_path: str | Path) -> list[dict[str, float | str]]:
	train_samples = load_stream(train_path)
	feature_rows, labels = labelled_training_rows(train_samples, labels_path)
	model = DoorModel().fit(feature_rows, labels)
	return predict_intervals(load_stream(test_path), model)
