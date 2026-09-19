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
		from sklearn.ensemble import ExtraTreesClassifier
		if not rows or len(rows) != len(labels):
			raise ValueError("Rail fit requires matching nonempty features and labels")
		if not set(labels) <= {"Normal", "Side I", "Side II"}:
			raise ValueError("Unknown Rail class")
		self.feature_names = tuple(rows[0])
		self.majority_label = max(sorted(set(labels)), key=labels.count)
		self.model = ExtraTreesClassifier(n_estimators=300, class_weight="balanced", random_state=42, n_jobs=-1)
		self.model.fit([[row[name] for name in self.feature_names] for row in rows], labels)
		return self

	def predict(self, rows: Sequence[dict[str, float]]) -> list[str]:
		if not rows:
			return []
		if self.model is None:
			raise ValueError("Rail model is not fitted")
		return [str(value) for value in self.model.predict([[row[name] for name in self.feature_names] for row in rows])]
