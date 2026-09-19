"""Deterministic, hysteretic operation boundary detection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .loader import DoorSample


@dataclass(frozen=True)
class DoorInterval:
	start_index: int
	end_index: int
	operation: str

	@property
	def n_rows(self) -> int:
		return self.end_index - self.start_index + 1


def detect_intervals(
	samples: Sequence[DoorSample],
	*,
	min_duration_seconds: float = 0.5,
	close_gap_seconds: float = 0.25,
) -> list[DoorInterval]:
	"""Detect command/movement intervals while retaining powered-stalled phases.

	Start is the first asserted command or movement sample. End is the last
	sample before both command and movement remain inactive for the gap.
	"""
	if not samples:
		return []
	def command_operation(sample: DoorSample) -> str | None:
		values = sample.values
		if values.get("Close command", 0) > 0:
			return "Close"
		if values.get("Open command", 0) > 0:
			return "Open"
		return None

	def movement_active(sample: DoorSample) -> bool:
		values = sample.values
		return any(values.get(name, 0) > 0 for name in ("Door is opening", "Door is closing"))

	def operation_for(sample: DoorSample) -> str:
		values = sample.values
		if values.get("Close command", 0) > 0 or values.get("Door is closing", 0) > 0:
			return "Close"
		return "Open"

	intervals: list[DoorInterval] = []
	if min_duration_seconds < 0 or close_gap_seconds < 0:
		raise ValueError("Door segmentation durations must be nonnegative")
	start = last_active = None
	operation = None
	def finish(end):
		if start is not None and samples[end].time_seconds - samples[start].time_seconds >= min_duration_seconds:
			intervals.append(DoorInterval(start, end, operation))
	for index, sample in enumerate(samples):
		command = command_operation(sample)
		active = command is not None or movement_active(sample)
		if start is not None and not active:
			if sample.time_seconds - samples[last_active].time_seconds > close_gap_seconds:
				finish(last_active)
				start = None
			continue
		if not active:
			continue
		current_operation = command or operation_for(sample)
		previous = samples[index - 1].values if index else {}
		current = sample.values.get("Motor current(mA)", 0.0)
		prior_current = previous.get("Motor current(mA)", 0.0)
		effort_reset = (prior_current >= 500 and current <= 500 and current <= prior_current * .75
			and abs(sample.values.get("Door leaf position", 0.0) - previous.get("Door leaf position", 0.0)) >= 100)
		if start is not None and (current_operation != operation or effort_reset and command is not None):
			finish(last_active)
			start = None
		if start is None:
			start, operation = index, current_operation
		last_active = index
	if start is not None:
		finish(last_active)
	return intervals
