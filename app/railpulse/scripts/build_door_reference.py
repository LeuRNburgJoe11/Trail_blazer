#!/usr/bin/env python3
"""Derive the Normal-cycle reference the Doors panel explains its calls against.

Two things come out of the labelled training segments, per operation:

  * a current envelope -- the 90th percentile of Normal cycles at each point of
    cycle progress, which marks where a cycle is drawing more than Normal ones do;
  * median feature values, so an indicator can be quoted as "1.4x Normal" instead
    of a bare number an engineer has no yardstick for.

This is reference data for explanation only. It never feeds the classifier, so
regenerating it cannot change a single prediction or the official Door CSV.

Run:
    python scripts/build_door_reference.py \
        --stream ../../data/Door/Train.csv \
        --answers ../../data/Door/Train_Segments_Answer.csv \
        --output registry/door/normal_reference.json
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from railpulse.door.features import extract_features
from railpulse.door.loader import load_stream
from railpulse.door.segmentation import detect_intervals

BINS = 50
ENVELOPE_PERCENTILE = 90
# Quoted in the panel. Peak current is deliberately absent: on the labelled data
# it is the same for both classes (ratio 1.00 Open / 0.93 Close), so leading with
# it would point engineers at the wrong part of the cycle.
INDICATORS = ("energy_proxy", "current_integral", "current_mean", "current_rms", "position_stagnation")
CURRENT = "Motor current(mA)"


def current_profile(samples, interval, bins: int = BINS) -> np.ndarray:
    """Motor current resampled onto `bins` points of cycle progress (0 to 1).

    Cycles differ in duration, so comparing them point-by-point in seconds would
    misalign their phases; progress puts the same part of the stroke together.
    """
    window = samples[interval.start_index : interval.end_index + 1]
    current = np.array([s.values.get(CURRENT, 0.0) for s in window], dtype=float)
    seconds = np.array([s.time_seconds for s in window], dtype=float)
    span = max(seconds[-1] - seconds[0], 1e-9)
    return np.interp(np.linspace(0, 1, bins), (seconds - seconds[0]) / span, current)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stream", type=Path, default=ROOT / "data/Door/Train.csv")
    parser.add_argument("--answers", type=Path, default=ROOT / "data/Door/Train_Segments_Answer.csv")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "registry/door/normal_reference.json")
    args = parser.parse_args()

    samples = load_stream(args.stream)
    intervals = detect_intervals(samples)
    with args.answers.open(newline="", encoding="utf-8-sig") as handle:
        answers = {row["start_time"]: row for row in csv.DictReader(handle)}

    labelled = []
    for interval in intervals:
        answer = answers.get(samples[interval.start_index].timestamp)
        if answer is not None:
            labelled.append((answer["status"], answer["operation"], interval))
    if not labelled:
        raise SystemExit("No detected interval matched a labelled segment; check the answer file")

    operations = {}
    for operation in sorted({op for _, op, _ in labelled}):
        normal = [iv for status, op, iv in labelled if op == operation and status == "Normal"]
        if not normal:
            continue
        profiles = np.array([current_profile(samples, iv) for iv in normal])
        features = [extract_features(samples, iv) for iv in normal]
        envelope = np.percentile(profiles, ENVELOPE_PERCENTILE, axis=0)
        # How much of a Normal cycle typically sits above the envelope. Without
        # this yardstick the panel cannot say whether a Normal-classified cycle
        # is ordinary or unusually close to the abnormal ones.
        normal_above = [float((profile > envelope).mean()) for profile in profiles]
        abnormal = [iv for status, op, iv in labelled if op == operation and status != "Normal"]
        abnormal_above = [float((current_profile(samples, iv) > envelope).mean()) for iv in abnormal]
        operations[operation] = {
            "n_normal_cycles": len(normal),
            "envelope": envelope.round(2).tolist(),
            "median_profile": np.median(profiles, axis=0).round(2).tolist(),
            "normal_fraction_above_median": round(float(np.median(normal_above)), 3),
            "normal_fraction_above_p90": round(float(np.percentile(normal_above, 90)), 3),
            "abnormal_fraction_above_median": round(float(np.median(abnormal_above)), 3) if abnormal_above else None,
            "feature_medians": {
                name: round(float(np.median([f[name] for f in features])), 4) for name in INDICATORS
            },
        }

    reference = {
        "version": 1,
        "bins": BINS,
        "envelope_percentile": ENVELOPE_PERCENTILE,
        "indicators": list(INDICATORS),
        "source": {
            "stream": args.stream.name,
            "stream_sha256": hashlib.sha256(args.stream.read_bytes()).hexdigest(),
            "answers_sha256": hashlib.sha256(args.answers.read_bytes()).hexdigest(),
            "labelled_cycles": len(labelled),
            "normal_cycles": sum(1 for status, _, _ in labelled if status == "Normal"),
        },
        "operations": operations,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(reference, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")
    for operation, entry in operations.items():
        print(f"  {operation}: {entry['n_normal_cycles']} Normal cycles, envelope peak {max(entry['envelope']):.0f} mA")


if __name__ == "__main__":
    main()
