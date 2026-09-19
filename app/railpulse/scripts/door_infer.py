#!/usr/bin/env python3
"""Run Door inference with the canonical root pipeline, in its own process.

Why a subprocess rather than an import: this prototype ships its own
`railpulse` package, and the repository-root runtime ships another. Only one
can own that name in a single interpreter, and app/railpulse/README.md warns
against mixing them. Running the canonical stack behind a process boundary
means the Door panel gets the real segmentation, the real model and the real
evidence without either package shadowing the other.

Reads one Door CSV, writes one JSON document to --output:

    {"rows": [{start_time, end_time, prediction, confidence, evidence}, ...]}
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import warnings

PROTOTYPE = Path(__file__).resolve().parents[1]
REPO = PROTOTYPE.parents[1]
# The canonical runtime first; this prototype's own package must not be on the
# path at all here, or `railpulse` resolves to the wrong tree.
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(PROTOTYPE / "backend"))

FEATURE_NAMES = ("duration", "current_peak", "current_mean", "current_rms", "current_integral",
                 "current_std", "energy_proxy", "position_change", "position_stagnation", "velocity")
# Preferred first: the audited bundle the root README names as canonical.
BUNDLES = ("architecture-audit-final", "merged-main")


def default_model() -> Path:
    for name in BUNDLES:
        candidate = REPO / "outputs/combined" / name / "models/door.joblib"
        if candidate.exists():
            return candidate
    raise SystemExit("No Door model bundle found; run scripts/run_all.py at the repository root first")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--reference", type=Path, default=PROTOTYPE / "registry/door/normal_reference.json")
    parser.add_argument("--source-name", default=None, help="Name to report instead of the temp file's")
    args = parser.parse_args()

    warnings.filterwarnings("ignore")
    import joblib
    from door_evidence import cycle_evidence, load_reference
    from railpulse.door.features import extract_features
    from railpulse.door.loader import load_stream
    from railpulse.door.segmentation import detect_intervals

    model = joblib.load(args.model or default_model())
    reference = load_reference(args.reference)
    samples = load_stream(args.input)
    intervals = detect_intervals(samples)

    rows = []
    if intervals:
        features = [extract_features(samples, interval) for interval in intervals]
        matrix = [[float(row[name]) for name in FEATURE_NAMES] for row in features]
        predictions = [str(value) for value in model.classifier.predict(matrix)]
        # Uncalibrated class votes; the UI keeps them behind an opt-in and says so.
        probabilities = model.classifier.predict_proba(matrix)
        classes = [str(value) for value in model.classifier.classes_]
        for interval, prediction, votes in zip(intervals, predictions, probabilities):
            evidence = cycle_evidence(samples, interval, prediction, reference)
            rows.append({
                "source_file": args.source_name or args.input.name,
                "start_time": evidence["start_time"],
                "end_time": evidence["end_time"],
                "prediction": prediction,
                "confidence": float(votes[classes.index(prediction)]),
                "evidence": evidence,
            })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"rows": rows}, allow_nan=False), encoding="utf-8")
    print(f"{len(rows)} cycles -> {args.output}")


if __name__ == "__main__":
    main()
