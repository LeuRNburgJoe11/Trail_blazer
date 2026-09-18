"""
Recover linear train speed from the raw 0/1 tooth-sensor pulse train
(Rail_Corrugation_Info_Kit.md Section 2.1): 90 teeth/revolution, 0.85 m
wheel diameter. Needed because corrugation's characteristic vibration
frequency is speed-dependent (frequency ~ speed / corrugation wavelength);
without this, the same physical defect looks like a different frequency in
every file.
"""
from __future__ import annotations

import numpy as np

from railpulse.rail.loader import FS_HZ, TEETH_PER_REV, WHEEL_DIAMETER_M


def estimate_speed_mps(speed_pulse: np.ndarray, fs: int = FS_HZ) -> float:
    """Average speed over the whole 1-second window, from rising-edge count.

    revolutions = rising_edges / TEETH_PER_REV
    speed = revolutions * (pi * wheel_diameter) / duration_seconds
    """
    edges = np.diff((speed_pulse > 0.5).astype(int))
    rising_edges = int((edges == 1).sum())
    duration_s = len(speed_pulse) / fs
    if duration_s <= 0 or rising_edges == 0:
        return 0.0
    revolutions = rising_edges / TEETH_PER_REV
    circumference_m = np.pi * WHEEL_DIAMETER_M
    return revolutions * circumference_m / duration_s
