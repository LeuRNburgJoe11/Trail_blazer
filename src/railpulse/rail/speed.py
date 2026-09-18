"""Speed decoding from the documented toothed-wheel channel."""

from __future__ import annotations

import numpy as np


def estimate_speed(speed_signal: np.ndarray, sampling_rate: float = 10_000.0) -> float:
	"""Estimate linear m/s from 90-tooth wheel transitions; return zero if stopped."""
	if speed_signal.size < 2:
		return 0.0
	levels = speed_signal > np.nanmedian(speed_signal)
	transitions = int(np.count_nonzero(levels[1:] != levels[:-1]))
	duration = speed_signal.size / sampling_rate
	return (transitions / 2.0) * (np.pi * 0.85 / 90.0) / duration
