"""Class-weighted file-level rail classifier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass
class RailClassifier:
	model: object | None = None
	feature_names: tuple[str, ...] = ()
	majority_label: str = "Normal"

	def fit(self, rows: Sequence[dict[str, float]], labels: Sequence[str]) -> "RailClassifier":
		if not rows:
			return self
		self.feature_names = tuple(rows[0])
		self.majority_label = max(set(labels), key=labels.count)
		try:
			from sklearn.ensemble import ExtraTreesClassifier
		except ImportError:
			return self
		if len(set(labels)) < 2:
			return self
		self.model = ExtraTreesClassifier(n_estimators=300, class_weight="balanced", random_state=42, n_jobs=-1)
		self.model.fit([[row[name] for name in self.feature_names] for row in rows], labels)
		return self

	def predict(self, rows: Sequence[dict[str, float]]) -> list[str]:
		if not rows:
			return []
		if self.model is None:
			return [self.majority_label] * len(rows)
		return [str(value) for value in self.model.predict([[row[name] for name in self.feature_names] for row in rows])]
