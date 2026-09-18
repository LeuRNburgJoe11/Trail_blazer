#!/usr/bin/env python3
"""
Run the registered Door model end-to-end on Test.csv (or any --input stream)
and write the exact submission CSV. Same DoorPipeline.predict() code path
the app uses.

Usage:
    python scripts/predict_door.py --input path/to/Door/Test.csv \
        --registry-dir ./registry --version v0_baseline --output door_predictions.csv
"""
import argparse

from railpulse.core.registry import ModelRegistry
from railpulse.core.submission import write_door_predictions
from railpulse.door.loader import load_stream
from railpulse.door.pipeline import DoorPipeline


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Continuous stream CSV, e.g. Test.csv")
    ap.add_argument("--registry-dir", default="./registry")
    ap.add_argument("--version", default=None, help="Defaults to latest registered version")
    ap.add_argument("--output", default="door_predictions.csv")
    args = ap.parse_args()

    registry = ModelRegistry(args.registry_dir)
    version = args.version or registry.latest_version("door")
    if version is None:
        raise SystemExit("No registered door model found -- run scripts/train_door.py first.")
    model, record = registry.load("door", version)
    print(f"Loaded door/{version} (fold scores: {record.fold_scores})")

    pipeline = DoorPipeline(model=model)
    stream = load_stream(args.input)
    result = pipeline.predict(stream)
    write_door_predictions(result, args.output)
    print(f"Wrote {args.output} with {len(result.segments)} predicted segments.")


if __name__ == "__main__":
    main()
