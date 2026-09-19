"""Train and run the Rail speed- and side-aware baseline."""

from __future__ import annotations

import csv
from pathlib import Path

from .loader import list_recordings, load_labels, load_recording
from .side_model import RailClassifier
from .spectral_features import extract_features


def train(train_directory: str | Path, labels_path: str | Path) -> RailClassifier:
	labels = load_labels(labels_path)
	paths = list_recordings(train_directory)
	if {path.name for path in paths} != set(labels):
		raise ValueError("Rail training files and labels must match exactly")
	rows, targets = [], []
	for path in paths:
		rows.append(extract_features(load_recording(path).values))
		targets.append(labels[path.name])
	if not rows:
		raise ValueError("No labelled Rail recordings found")
	return RailClassifier().fit(rows, targets)


def predict(model: RailClassifier, test_directory: str | Path) -> list[dict[str, str]]:
	results = []
	for path in list_recordings(test_directory):
		row = extract_features(load_recording(path).values)
		results.append({"file_id": path.name, "prediction": model.predict([row])[0]})
	return results


def write_predictions(path: str | Path, predictions: list[dict[str, str]]) -> None:
	with Path(path).open("w", newline="", encoding="utf-8") as handle:
		writer = csv.DictWriter(handle, fieldnames=("file_id", "prediction"))
		writer.writeheader()
		writer.writerows(predictions)
