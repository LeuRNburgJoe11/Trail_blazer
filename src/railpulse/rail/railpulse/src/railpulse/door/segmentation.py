"""
Boundary detection (architecture review Section 02): start with a
deterministic state machine, add hysteresis and controlled gap merging.

Current signal: 'Door is opening' | 'Door is closing' == 1.
This is a first-pass baseline, explicitly NOT the final word -- the Door
Info Kit deliberately warns against assuming any one column (including this
one) is the most robust boundary signal. Swap in a smarter detector (e.g.
one also conditioned on current/position derivative to catch powered-but-
stalled phases) by changing only this module; loader/features/pipeline
don't need to change.
"""
from __future__ import annotations

import pandas as pd

DEFAULT_MIN_GAP = pd.Timedelta("0.4s")
DEFAULT_MIN_DURATION = pd.Timedelta("0.3s")


def segment_stream(df: pd.DataFrame, min_gap=DEFAULT_MIN_GAP, min_duration=DEFAULT_MIN_DURATION):
    """Returns a list of (start_ts, end_ts, row_slice) candidate cycles."""
    if isinstance(min_gap, str):
        min_gap = pd.Timedelta(min_gap)
    if isinstance(min_duration, str):
        min_duration = pd.Timedelta(min_duration)

    active = (df["Door is opening"] == 1) | (df["Door is closing"] == 1)

    segments = []
    seg_start_idx = None
    last_active_idx = None
    for i, is_active in enumerate(active):
        if is_active:
            if seg_start_idx is None:
                seg_start_idx = i
            elif last_active_idx is not None:
                gap = df["ts"].iloc[i] - df["ts"].iloc[last_active_idx]
                if gap > min_gap:
                    segments.append((seg_start_idx, last_active_idx))
                    seg_start_idx = i
            last_active_idx = i
    if seg_start_idx is not None:
        segments.append((seg_start_idx, last_active_idx))

    cycles = []
    for s, e in segments:
        start_ts, end_ts = df["ts"].iloc[s], df["ts"].iloc[e]
        if end_ts - start_ts >= min_duration:
            cycles.append((start_ts, end_ts, df.iloc[s : e + 1]))
    return cycles
