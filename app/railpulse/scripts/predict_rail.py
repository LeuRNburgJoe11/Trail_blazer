#!/usr/bin/env python3
"""
Run the registered Rail model on one or more test files and write the
exact rail_predictions.csv submission format.

Usage:
    python scripts/predict_rail.py --input-dir path/to/Rail_Corrugation/Test \
        --registry-dir ./registry --output rail_predictions.csv
"""
import argparse
import glob

import pandas as pd

from railpulse.core.registry import ModelRegistry
from railpulse.rail.pipeline import RailPipeline


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", help="A single test CSV")
    ap.add_argument("--input-dir", help="A folder of test CSVs")
    ap.add_argument("--registry-dir", default="./registry")
    ap.add_argument("--version", default=None)
    ap.add_argument("--output", default="rail_predictions.csv")
    args = ap.parse_args()

    if not args.input and not args.input_dir:
        raise SystemExit("Provide --input or --input-dir")
    paths = [args.input] if args.input else sorted(glob.glob(f"{args.input_dir}/*.csv"))

    registry = ModelRegistry(args.registry_dir)
    version = args.version or registry.latest_version("rail")
    if version is None:
        raise SystemExit("No registered rail model found -- run scripts/train_rail.py first.")
    model, record = registry.load("rail", version)
    print(f"Loaded rail/{version} (fold scores: {record.fold_scores})")

    pipeline = RailPipeline(model=model)
    pipeline.feature_cols = record.feature_columns

    rows = []
    for p in paths:
        result = pipeline.predict_file(p)
        rows.append({"file_id": result.file_id, "prediction": result.prediction})
        print(f"{result.file_id}: {result.prediction}  (scores={result.side_scores})")

    pd.DataFrame(rows).to_csv(args.output, index=False)
    print(f"\nWrote {args.output} with {len(rows)} file(s).")


if __name__ == "__main__":
    main()
