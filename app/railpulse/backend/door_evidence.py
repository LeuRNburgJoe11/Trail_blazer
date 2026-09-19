"""Explain a Door call: when in the cycle, and on which indicator.

The classifier decides Normal vs Abnormal resistance. Nothing here changes that
decision or the official CSV -- it only reports what the cycle did against the
Normal reference built by scripts/build_door_reference.py, so an engineer gets a
timeframe to inspect instead of a bare label.

Phrasing note: on the labelled training cycles, peak current does NOT separate
the classes (ratio 1.00 Open / 0.93 Close) while sustained draw does -- mean
current 1.27-1.40x Normal and energy proxy 1.51-1.55x. The wording here is
therefore "sustained elevated current", never "spike", which would send an
engineer looking at the wrong part of the stroke.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import json
from pathlib import Path

import numpy as np

CURRENT = "Motor current(mA)"
# A window shorter than this is not worth sending someone to inspect.
MIN_REGION_SECONDS = 0.15
MAX_TRACE_POINTS = 400
INDICATOR_LABELS = {
    "energy_proxy": "Energy proxy (current x voltage)",
    "current_integral": "Current integral over the cycle",
    "current_mean": "Mean motor current",
    "current_rms": "RMS motor current",
    "position_stagnation": "Fraction of the cycle with no leaf movement",
}
INDICATOR_UNITS = {"current_mean": " mA", "current_rms": " mA"}


def load_reference(path):
    reference = json.loads(Path(path).read_text(encoding="utf-8"))
    if reference.get("version") != 1 or not reference.get("operations"):
        raise ValueError("Unsupported or empty Door reference; rebuild with scripts/build_door_reference.py")
    return reference


def parse_native(timestamp: str) -> datetime:
    """Parse the dataset's "Y-M-D-H-M-S-ms" stamp without an epoch round trip."""
    parts = timestamp.split("-")
    if len(parts) != 7:
        raise ValueError(f"Unsupported Door timestamp: {timestamp!r}")
    year, month, day, hour, minute, second, milliseconds = map(int, parts)
    return datetime(year, month, day, hour, minute, second, milliseconds * 1000)


def clock(moment: datetime) -> str:
    """Wall clock to hundredths, the resolution an inspection window needs."""
    return f"{moment:%H:%M:%S}.{moment.microsecond // 10000:02d}"


def _regions(above, duration: float, started: datetime) -> list:
    """Contiguous runs where the cycle exceeds the Normal envelope."""
    bins = len(above)
    regions, index = [], 0
    while index < bins:
        if not above[index]:
            index += 1
            continue
        end = index
        while end + 1 < bins and above[end + 1]:
            end += 1
        start_offset = index / (bins - 1) * duration
        end_offset = end / (bins - 1) * duration
        if end_offset - start_offset >= MIN_REGION_SECONDS:
            regions.append({
                "start_offset": round(start_offset, 3),
                "end_offset": round(end_offset, 3),
                "seconds": round(end_offset - start_offset, 3),
                "start_clock": clock(started + timedelta(seconds=start_offset)),
                "end_clock": clock(started + timedelta(seconds=end_offset)),
            })
        index = end + 1
    return regions


def _indicators(features: dict, medians: dict) -> list:
    """Each reference indicator with its Normal yardstick, strongest first."""
    rows = []
    for name, median in medians.items():
        value = features.get(name)
        if value is None:
            continue
        rows.append({
            "name": name,
            "label": INDICATOR_LABELS.get(name, name),
            "value": round(float(value), 4),
            "normal_median": median,
            "ratio": round(float(value) / median, 3) if median else None,
            "unit": INDICATOR_UNITS.get(name, ""),
        })
    rows.sort(key=lambda row: row["ratio"] if row["ratio"] is not None else 0, reverse=True)
    return rows


def _reason(status: str, operation: str, fraction: float, regions: list, indicators: list,
            typical: float | None = None) -> str:
    percent = round(fraction * 100)
    verb = operation.lower()
    if status == "Normal":
        # A Normal call on a cycle that behaves like an abnormal one is exactly
        # what an engineer needs told, so compare it with typical Normal cycles
        # rather than reporting the bare percentage.
        unusual = typical is not None and fraction > max(2 * typical, 0.25)
        if unusual:
            text = (f"Called Normal, but motor current runs above the Normal envelope for {percent}% of the "
                    f"{verb} cycle, against {round(typical * 100)}% for a typical Normal cycle.")
            if regions:
                longest = max(regions, key=lambda region: region["seconds"])
                text += (f" Longest elevated window {longest['start_clock']} to {longest['end_clock']} "
                         f"({longest['seconds']:.2f} s).")
            return text + " Worth a look despite the Normal call."
        return (f"Motor current stays within the Normal envelope for {100 - percent}% of the {verb} cycle, "
                "so no sustained elevated-effort interval was isolated. A Normal prediction is not a "
                "safety clearance.")
    parts = [f"Motor current runs above the Normal envelope for {percent}% of the {verb} cycle, "
             "sustained rather than a brief spike."]
    top = [row for row in indicators if row["ratio"] and row["ratio"] > 1.05][:2]
    if top:
        clause = "; ".join(f"{row['label'].lower()} is {row['ratio']:.2f}x the Normal median" for row in top)
        parts.append(" " + clause[0].upper() + clause[1:] + ".")
    if regions:
        longest = max(regions, key=lambda region: region["seconds"])
        parts.append(f" Longest elevated window {longest['start_clock']} to {longest['end_clock']} "
                     f"({longest['seconds']:.2f} s) -- inspect there for binding or an obstruction.")
    return "".join(parts)


def cycle_evidence(samples, interval, status: str, reference: dict) -> dict:
    """Timeframe, indicators and current trace behind one Door cycle's call."""
    from railpulse.door.features import extract_features

    operation = interval.operation
    entry = reference["operations"].get(operation)
    window = samples[interval.start_index : interval.end_index + 1]
    started, ended = parse_native(window[0].timestamp), parse_native(window[-1].timestamp)
    duration = (ended - started).total_seconds()
    current = np.array([s.values.get(CURRENT, 0.0) for s in window], dtype=float)
    seconds = np.array([(parse_native(s.timestamp) - started).total_seconds() for s in window], dtype=float)

    evidence = {
        "operation": operation,
        "start_time": window[0].timestamp,
        "end_time": window[-1].timestamp,
        "start_clock": clock(started),
        "end_clock": clock(ended),
        "duration_seconds": round(duration, 3),
        "n_samples": len(window),
    }
    if entry is None:
        # An operation the reference has never seen: report the cycle, claim nothing.
        evidence.update(envelope_available=False, fraction_above_envelope=None, regions=[],
                        indicators=[], trace=[],
                        reason=f"No Normal reference exists for {verb_of(operation)} cycles, so this call "
                               "cannot be explained against a Normal envelope.")
        return evidence

    bins = reference["bins"]
    progress = np.linspace(0, 1, bins)
    resampled = np.interp(progress, seconds / max(duration, 1e-9), current)
    envelope = np.array(entry["envelope"], dtype=float)
    above = resampled > envelope
    regions = _regions(above, duration, started)
    indicators = _indicators(extract_features(samples, interval), entry["feature_medians"])

    step = max(1, len(window) // MAX_TRACE_POINTS)
    envelope_at = np.interp(seconds[::step] / max(duration, 1e-9), progress, envelope)
    evidence.update(
        envelope_available=True,
        fraction_above_envelope=round(float(above.mean()), 3),
        regions=regions,
        indicators=indicators,
        trace=[{"t": round(float(t), 3), "current": round(float(c), 1), "envelope": round(float(e), 1)}
               for t, c, e in zip(seconds[::step], current[::step], envelope_at)],
        reason=_reason(status, operation, float(above.mean()), regions, indicators,
                       entry.get("normal_fraction_above_median")),
        typical_fraction_above=entry.get("normal_fraction_above_median"),
    )
    return evidence


def verb_of(operation: str) -> str:
    return operation.lower()
