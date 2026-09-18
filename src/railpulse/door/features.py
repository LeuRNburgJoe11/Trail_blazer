"""Small, operation-aware feature vectors for Door cycles."""

from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Sequence

from .loader import DoorSample
from .segmentation import DoorInterval


def extract_features(samples: Sequence[DoorSample], interval: DoorInterval) -> dict[str, float | str]:
	window = samples[interval.start_index : interval.end_index + 1]
	current = [sample.values.get("Motor current(mA)", 0.0) for sample in window]
	voltage = [sample.values.get("Motor Voltage(10mV)", 0.0) for sample in window]
	positions = [sample.values.get("Door leaf position", 0.0) for sample in window]
	duration = max(samples[interval.end_index].time_seconds - samples[interval.start_index].time_seconds, 1e-9)
	absolute_current = sum(abs(value) for value in current)
	velocity = (positions[-1] - positions[0]) / duration
	return {
		"operation": interval.operation,
		"duration": duration,
		"current_peak": max(current, default=0.0),
		"current_mean": mean(current) if current else 0.0,
		"current_rms": math.sqrt(mean(value * value for value in current)) if current else 0.0,
		"current_integral": absolute_current * duration / max(len(current), 1),
		"current_std": pstdev(current) if len(current) > 1 else 0.0,
		"energy_proxy": mean(a * b for a, b in zip(current, voltage)) if current else 0.0,
		"position_change": positions[-1] - positions[0] if positions else 0.0,
		"position_stagnation": sum(a == b for a, b in zip(positions, positions[1:])) / max(len(positions) - 1, 1),
		"velocity": velocity,
	}
