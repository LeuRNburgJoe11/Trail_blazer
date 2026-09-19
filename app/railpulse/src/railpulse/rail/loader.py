"""
Rail Corrugation data loading (Rail_Corrugation_Info_Kit.md Section 2.1).

Each file: 10,000 rows x 129 columns, 10 kHz sampling, 1 second duration.
Column 0 = raw speed-sensor pulse train (0/1 toggle, NOT decoded speed).
Columns 1-128 = 64 axle boxes x (vibration, shock), ordered Car 1 Position 1
vibration, Car 1 Position 1 shock, Car 1 Position 2 vibration, ... Car 8
Position 8 shock.

Positions 1,3,5,7 -> Side I. Positions 2,4,6,8 -> Side II.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

FS_HZ = 10_000
WHEEL_DIAMETER_M = 0.85
TEETH_PER_REV = 90

SIDE_I_POSITIONS = {1, 3, 5, 7}
SIDE_II_POSITIONS = {2, 4, 6, 8}


@dataclass
class RailFile:
    speed_pulse: np.ndarray          # shape (10000,)
    channels: dict                    # (car:int, position:int, kind:str) -> np.ndarray, kind in {"vibration","shock"}


def _channel_columns() -> list[tuple[int, int, str]]:
    """The fixed, documented column order for columns 1..128 (cars 1-8, positions 1-8, vibration then shock)."""
    order = []
    for car in range(1, 9):
        for pos in range(1, 9):
            order.append((car, pos, "vibration"))
            order.append((car, pos, "shock"))
    return order


_CHANNEL_ORDER = _channel_columns()


def load_file(path: str) -> RailFile:
    df = pd.read_csv(path, dtype="float32")
    arr = df.to_numpy()
    if arr.shape[1] != 129:
        raise ValueError(f"{path}: expected 129 columns, got {arr.shape[1]}")
    speed_pulse = arr[:, 0]
    channels = {}
    for i, (car, pos, kind) in enumerate(_CHANNEL_ORDER):
        channels[(car, pos, kind)] = arr[:, 1 + i]
    return RailFile(speed_pulse=speed_pulse, channels=channels)


def side_channels(rf: RailFile, side: str, kind: str | None = None):
    """Yield (car, position, kind, signal) for every axle box on `side`
    ("Side I" or "Side II"), optionally filtered to one signal kind."""
    positions = SIDE_I_POSITIONS if side == "Side I" else SIDE_II_POSITIONS
    for (car, pos, k), sig in rf.channels.items():
        if pos in positions and (kind is None or k == kind):
            yield car, pos, k, sig
