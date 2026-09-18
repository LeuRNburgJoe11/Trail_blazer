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

	command_present = any(command_operation(sample) is not None for sample in samples)
	starts = [0]
	for index in range(1, len(samples)):
		previous_command = command_operation(samples[index - 1])
		current_command = command_operation(samples[index])
		command_changed = current_command is not None and current_command != previous_command
		previous_current = samples[index - 1].values.get("Motor current(mA)", 0.0)
		current = samples[index].values.get("Motor current(mA)", 0.0)
		previous_position = samples[index - 1].values.get("Door leaf position", 0.0)
		position = samples[index].values.get("Door leaf position", 0.0)
		effort_reset = (
			previous_current >= 500
			and current <= 500
			and current <= previous_current * 0.75
			and abs(position - previous_position) >= 100
		)
		if command_changed or (effort_reset and current_command is not None):
			starts.append(index)

	intervals: list[DoorInterval] = []
	for position, start in enumerate(starts):
		end = starts[position + 1] - 1 if position + 1 < len(starts) else len(samples) - 1
		duration = samples[end].time_seconds - samples[start].time_seconds
		if duration < min_duration_seconds:
			continue
		operation = command_operation(samples[start])
		if operation is None:
			operation = operation_for(samples[start])
		intervals.append(DoorInterval(start, end, operation))
	return intervals
